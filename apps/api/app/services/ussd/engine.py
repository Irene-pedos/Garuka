import logging
import time
from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import hash_phone
from app.core.security import get_pin_hash, hash_visit_code, verify_pin, verify_visit_code
from app.models.attendance import (
    Absence,
    AbsenceStatusEnum,
    AttendanceSubmission,
    ReasonCodeEnum,
    ReasonSourceEnum,
    SubmissionSourceEnum,
)
from app.models.base import utc_now
from app.models.case import (
    BarrierCodeEnum,
    Case,
    CaseEvent,
    CaseStatusEnum,
    HelpRequest,
    MentorVisit,
    VerifiedMethodEnum,
    VisitCode,
    VisitOutcomeEnum,
)
from app.models.messaging import UssdRequest, UssdSession
from app.models.student import (
    Class,
    ConsentSourceEnum,
    Guardian,
    Student,
    StudentStatusEnum,
    class_teachers,
    student_guardians,
)
from app.models.user import LanguageEnum, RoleEnum, User
from app.services.attendance_service import record_class_attendance
from app.services.rules_engine import evaluate_student
from app.services.sms.outbox_worker import enqueue_sms, process_outbox_batch
from app.services.ussd.calendar_helper import get_available_attendance_dates, get_kigali_today
from app.services.ussd.i18n import get_msg
from app.services.ussd.identity import IdentityRole, resolve_identity
from app.services.ussd.render import render_ussd_response

logger = logging.getLogger("garuka.ussd.engine")


def validate_pin_rules(pin: str) -> bool:
    """PIN rules: exactly 4 digits, reject 0000, 1234, and repeating digits."""
    if len(pin) != 4 or not pin.isdigit():
        return False
    if pin in ("0000", "1234"):
        return False
    return len(set(pin)) != 1


async def get_primary_guardian(student: Student, db: AsyncSession) -> Guardian | None:
    """Returns primary guardian for student, or first linked guardian as fallback."""
    if not student or not student.guardians:
        return None
    primary_link = await db.execute(
        select(student_guardians.c.guardian_id).where(
            student_guardians.c.student_id == student.id,
            student_guardians.c.is_primary.is_(True),
        )
    )
    p_id = primary_link.scalar_one_or_none()
    return next((g for g in student.guardians if g.id == p_id), student.guardians[0])


async def handle_ussd_request(
    session_id: str,
    service_code: str,
    phone_number: str,
    raw_text: str,
    db: AsyncSession,
) -> tuple[str, str]:
    start_time = time.time()

    # 1. Parse cumulative inputs
    clean_text = raw_text.strip()
    is_malformed = False
    if clean_text:
        # Check for malformed delimiters (empty segments like 1**2 or leading *)
        trimmed = clean_text.rstrip("*")
        raw_parts = trimmed.split("*")
        if any(p == "" for p in raw_parts) or clean_text.startswith("*"):
            is_malformed = True
            inputs = raw_parts
        else:
            inputs = [p.strip() for p in raw_parts]
    else:
        inputs = []
    n_inputs = len(inputs)

    # 2. Check Idempotency Cache
    cached_res = await db.execute(
        select(UssdRequest).where(
            UssdRequest.session_id == session_id,
            UssdRequest.n_inputs == n_inputs,
        )
    )
    cached = cached_res.scalar_one_or_none()
    if cached:
        return cached.response_kind, cached.response_body

    # 3. Session lookup / creation
    sess_res = await db.execute(select(UssdSession).where(UssdSession.session_id == session_id))
    session = sess_res.scalar_one_or_none()
    if not session:
        session = UssdSession(
            session_id=session_id,
            phone_hash=hash_phone(phone_number),
            authed=False,
            created_at=utc_now(),
            last_seen_at=utc_now(),
        )
        db.add(session)
        await db.flush()
    else:
        session.last_seen_at = utc_now()

    # 4. Identity Resolution
    identity = await resolve_identity(phone_number, db)
    lang = identity.language

    # Handle Malformed Delimiters (return short localized retry screen)
    if is_malformed:
        body = get_msg("S_INVALID_INPUT", lang)
        rendered = render_ussd_response("CON", body)
        await save_request_cache(
            db, session_id, n_inputs, "S_INVALID_INPUT", "CON", rendered, start_time
        )
        return "CON", rendered

    # Handle Unregistered Subscriber
    if identity.role_type == IdentityRole.UNREGISTERED:
        body = get_msg("S_UNREGISTERED", lang)
        rendered = render_ussd_response("END", body)
        await save_request_cache(
            db, session_id, n_inputs, "S_UNREGISTERED", "END", rendered, start_time
        )
        return "END", rendered

    # Current replay input pointer
    inp_idx = 0

    # Role Picker if both staff and guardian
    if identity.role_type == IdentityRole.ROLE_PICK:
        if inp_idx >= n_inputs:
            body = get_msg("S_ROLE_PICK", lang)
            rendered = render_ussd_response("CON", body)
            await save_request_cache(
                db, session_id, n_inputs, "S_ROLE_PICK", "CON", rendered, start_time
            )
            return "CON", rendered

        choice = inputs[inp_idx]
        inp_idx += 1
        if choice == "2":
            # Guardian (parent) branch — dual-registered caller chose parent menu
            return await execute_guardian_flow(
                inputs=inputs,
                inp_idx=inp_idx,
                n_inputs=n_inputs,
                guardian=identity.guardian,
                lang=lang,
                session_id=session_id,
                start_time=start_time,
                db=db,
            )
        elif choice != "1":
            body = get_msg("S_INVALID", lang) + get_msg("S_ROLE_PICK", lang)
            rendered = render_ussd_response("CON", body)
            await save_request_cache(
                db, session_id, n_inputs, "S_ROLE_PICK", "CON", rendered, start_time
            )
            return "CON", rendered

    user = identity.user
    if not user:
        # Guardian-only caller → parent flow
        return await execute_guardian_flow(
            inputs=inputs,
            inp_idx=inp_idx,
            n_inputs=n_inputs,
            guardian=identity.guardian,
            lang=lang,
            session_id=session_id,
            start_time=start_time,
            db=db,
        )

    # 5. Staff PIN Authentication / Setup Flow
    if user.pin_hash is None:
        # --- PIN SETUP FLOW ---
        if inp_idx >= n_inputs:
            body = get_msg("T_PIN_SETUP1", lang)
            rendered = render_ussd_response("CON", body)
            await save_request_cache(
                db, session_id, n_inputs, "T_PIN_SETUP1", "CON", rendered, start_time
            )
            return "CON", rendered

        pin1 = inputs[inp_idx]
        inp_idx += 1
        if not validate_pin_rules(pin1):
            body = get_msg("T_PIN_INVALID_RULES", lang)
            rendered = render_ussd_response("END", body)
            await save_request_cache(
                db, session_id, n_inputs, "T_PIN_SETUP1", "END", rendered, start_time
            )
            return "END", rendered

        if inp_idx >= n_inputs:
            body = get_msg("T_PIN_SETUP2", lang)
            rendered = render_ussd_response("CON", body)
            await save_request_cache(
                db, session_id, n_inputs, "T_PIN_SETUP2", "CON", rendered, start_time
            )
            return "CON", rendered

        pin2 = inputs[inp_idx]
        inp_idx += 1
        if pin1 != pin2:
            body = get_msg("T_PIN_MISMATCH", lang)
            rendered = render_ussd_response("END", body)
            await save_request_cache(
                db, session_id, n_inputs, "T_PIN_SETUP2", "END", rendered, start_time
            )
            return "END", rendered

        # Save PIN
        user.pin_hash = get_pin_hash(pin1)
        await db.commit()
        body = get_msg("T_PIN_SAVED", lang)
        rendered = render_ussd_response("END", body)
        await save_request_cache(
            db, session_id, n_inputs, "T_PIN_SAVED", "END", rendered, start_time
        )
        return "END", rendered

    else:
        # --- PIN VERIFICATION FLOW ---
        # Check lockout
        if user.pin_locked_until and user.pin_locked_until > utc_now():
            body = get_msg("T_PIN_LOCKED", lang)
            rendered = render_ussd_response("END", body)
            await save_request_cache(
                db, session_id, n_inputs, "T_PIN_LOCKED", "END", rendered, start_time
            )
            return "END", rendered

        if not session.authed:
            if inp_idx >= n_inputs:
                body = get_msg("T_PIN", lang)
                rendered = render_ussd_response("CON", body)
                await save_request_cache(
                    db, session_id, n_inputs, "T_PIN", "CON", rendered, start_time
                )
                return "CON", rendered

            pin_attempt = inputs[inp_idx]
            inp_idx += 1

            if not verify_pin(pin_attempt, user.pin_hash):
                user.pin_failed_count += 1
                if user.pin_failed_count >= 3:
                    user.pin_locked_until = utc_now() + timedelta(minutes=30)
                    await db.commit()
                    body = get_msg("T_PIN_LOCKED", lang)
                    rendered = render_ussd_response("END", body)
                    await save_request_cache(
                        db, session_id, n_inputs, "T_PIN_LOCKED", "END", rendered, start_time
                    )
                    return "END", rendered

                await db.commit()
                body = get_msg("T_PIN_WRONG", lang)
                rendered = render_ussd_response("END", body)
                await save_request_cache(
                    db, session_id, n_inputs, "T_PIN_WRONG", "END", rendered, start_time
                )
                return "END", rendered

            # Correct PIN!
            session.authed = True
            session.user_id = user.id
            user.pin_failed_count = 0
            user.pin_locked_until = None
            await db.commit()
        else:
            # Already authed in this session, consume the PIN without re-verifying
            if inp_idx < n_inputs:
                inp_idx += 1

    # 6. Authenticated Staff Navigation (Mentor vs Teacher Flow)
    if user.role == RoleEnum.mentor:
        return await execute_mentor_flow(
            inputs=inputs,
            inp_idx=inp_idx,
            n_inputs=n_inputs,
            user=user,
            lang=lang,
            session_id=session_id,
            start_time=start_time,
            db=db,
        )
    return await execute_teacher_flow(
        inputs=inputs,
        inp_idx=inp_idx,
        n_inputs=n_inputs,
        user=user,
        lang=lang,
        session_id=session_id,
        start_time=start_time,
        db=db,
    )


async def execute_guardian_flow(
    inputs: list[str],
    inp_idx: int,
    n_inputs: int,
    guardian: Guardian | None,
    lang: LanguageEnum,
    session_id: str,
    start_time: float,
    db: AsyncSession,
) -> tuple[str, str]:
    """Full parent / guardian USSD flow per SPEC §7.2.

    Parent identity is the phone number only (no PIN in MVP).  The guardian
    record is passed in from the identity resolver.

    Screens implemented:
    - P_CHILD   — multi-child picker (skipped if guardian has exactly one child)
    - P_MENU    — Garuka - {child}: 1.Attendance 2.Explain 3.Help 4.Language
    - P_ATT     — attendance summary (last 30 days)
    - P_ABS_PICK — which absence to explain (latest 3 without a reason)
    - P_REASON  — reason code picker → saves reason, END
    - P_HELP    — barrier picker → creates help_request, END
    - S_LANG / S_LANG_SAVED — reuse existing language change flow
    """
    if not guardian:
        # Should not happen: guardian is always set when role_type is PARENT
        body = get_msg("S_ERROR", lang)
        rendered = render_ussd_response("END", body)
        await save_request_cache(db, session_id, n_inputs, "P_ERROR", "END", rendered, start_time)
        return "END", rendered

    # Load children (students) for this guardian
    from sqlalchemy.orm import selectinload as _sil
    guard_res = await db.execute(
        select(Guardian)
        .options(_sil(Guardian.students).selectinload(Student.class_group))
        .where(Guardian.id == guardian.id)
    )
    full_guardian = guard_res.scalar_one_or_none()
    if full_guardian and full_guardian.consent_at is None:
        full_guardian.consent_at = utc_now()
        full_guardian.consent_source = ConsentSourceEnum.ussd
        await db.commit()

    children = [s for s in (full_guardian.students if full_guardian else [])
                if s.status == StudentStatusEnum.active]

    if not children:
        body = get_msg("S_UNREGISTERED", lang)
        rendered = render_ussd_response("END", body)
        await save_request_cache(db, session_id, n_inputs, "P_NO_CHILD", "END", rendered, start_time)
        return "END", rendered

    # --- P_CHILD: multi-child picker (skip if only one child) ---
    selected_student: Student
    if len(children) == 1:
        selected_student = children[0]
    else:
        child_lines = []
        for i, s in enumerate(children[:5], 1):
            parts = s.full_name.split()
            short = f"{parts[0]} {parts[1][0]}." if len(parts) > 1 else parts[0]
            child_lines.append(f"{i}. {short}")

        if inp_idx >= n_inputs:
            body = get_msg("P_CHILD", lang, lines="\n".join(child_lines))
            rendered = render_ussd_response("CON", body)
            await save_request_cache(
                db, session_id, n_inputs, "P_CHILD", "CON", rendered, start_time
            )
            return "CON", rendered

        child_choice = inputs[inp_idx]
        inp_idx += 1
        try:
            c_idx = int(child_choice) - 1
            if c_idx < 0 or c_idx >= len(children[:5]):
                raise ValueError
            selected_student = children[c_idx]
        except ValueError:
            child_lines_str = "\n".join(child_lines)
            body = get_msg("S_INVALID", lang) + get_msg("P_CHILD", lang, lines=child_lines_str)
            rendered = render_ussd_response("CON", body)
            await save_request_cache(
                db, session_id, n_inputs, "P_CHILD", "CON", rendered, start_time
            )
            return "CON", rendered

    # Short child name for screen headers (First L.)
    name_parts = selected_student.full_name.split()
    child_short = f"{name_parts[0]} {name_parts[1][0]}." if len(name_parts) > 1 else name_parts[0]
    # Cap at 20 chars to keep screens within 160
    child_short = child_short[:20]

    # --- P_MENU ---
    if inp_idx >= n_inputs:
        body = get_msg("P_MENU", lang, child=child_short)
        rendered = render_ussd_response("CON", body)
        await save_request_cache(
            db, session_id, n_inputs, "P_MENU", "CON", rendered, start_time
        )
        return "CON", rendered

    menu_choice = inputs[inp_idx]
    inp_idx += 1

    # --- Option 4: Language ---
    if menu_choice == "4":
        if inp_idx >= n_inputs:
            body = get_msg("S_LANG", lang)
            rendered = render_ussd_response("CON", body)
            await save_request_cache(
                db, session_id, n_inputs, "S_LANG", "CON", rendered, start_time
            )
            return "CON", rendered

        lang_choice = inputs[inp_idx]
        lang_map = {"1": LanguageEnum.rw, "2": LanguageEnum.en, "3": LanguageEnum.fr}
        new_lang = lang_map.get(lang_choice, LanguageEnum.rw)
        guardian.language = new_lang
        await db.commit()

        body = get_msg("S_LANG_SAVED", new_lang)
        rendered = render_ussd_response("END", body)
        await save_request_cache(
            db, session_id, n_inputs, "S_LANG_SAVED", "END", rendered, start_time
        )
        return "END", rendered

    # --- Option 1: Attendance summary ---
    if menu_choice == "1":
        today = get_kigali_today()
        thirty_ago = today - timedelta(days=30)
        abs_res = await db.execute(
            select(Absence)
            .where(
                Absence.student_id == selected_student.id,
                Absence.status == AbsenceStatusEnum.active,
                Absence.date >= thirty_ago,
            )
            .order_by(Absence.date.desc())
        )
        recent_absences = abs_res.scalars().all()
        n_abs = len(recent_absences)
        if n_abs == 0:
            body = get_msg("P_ATT_NONE", lang, child=child_short)
        else:
            last_date = recent_absences[0].date.strftime("%d/%m")
            body = get_msg("P_ATT", lang, child=child_short, n=n_abs, last_date=last_date)
        rendered = render_ussd_response("END", body)
        await save_request_cache(
            db, session_id, n_inputs, "P_ATT", "END", rendered, start_time
        )
        return "END", rendered

    # --- Option 2: Explain an absence ---
    if menu_choice == "2":
        # Find latest 3 active absences without a reason
        abs_res = await db.execute(
            select(Absence)
            .where(
                Absence.student_id == selected_student.id,
                Absence.status == AbsenceStatusEnum.active,
                Absence.reason_code.is_(None),
            )
            .order_by(Absence.date.desc())
            .limit(3)
        )
        unexplained = abs_res.scalars().all()

        if not unexplained:
            body = get_msg("P_ABS_NONE", lang)
            rendered = render_ussd_response("END", body)
            await save_request_cache(
                db, session_id, n_inputs, "P_ABS_NONE", "END", rendered, start_time
            )
            return "END", rendered

        abs_lines = [f"{i}. {ab.date.strftime('%d/%m')}" for i, ab in enumerate(unexplained, 1)]

        if inp_idx >= n_inputs:
            body = get_msg("P_ABS_PICK", lang, lines="\n".join(abs_lines))
            rendered = render_ussd_response("CON", body)
            await save_request_cache(
                db, session_id, n_inputs, "P_ABS_PICK", "CON", rendered, start_time
            )
            return "CON", rendered

        abs_choice = inputs[inp_idx]
        inp_idx += 1
        try:
            a_idx = int(abs_choice) - 1
            if a_idx < 0 or a_idx >= len(unexplained):
                raise ValueError
            chosen_absence = unexplained[a_idx]
        except ValueError:
            body = get_msg("S_INVALID", lang) + get_msg(
                "P_ABS_PICK", lang, lines="\n".join(abs_lines)
            )
            rendered = render_ussd_response("CON", body)
            await save_request_cache(
                db, session_id, n_inputs, "P_ABS_PICK", "CON", rendered, start_time
            )
            return "CON", rendered

        # P_REASON
        if inp_idx >= n_inputs:
            body = get_msg("P_REASON", lang)
            rendered = render_ussd_response("CON", body)
            await save_request_cache(
                db, session_id, n_inputs, "P_REASON", "CON", rendered, start_time
            )
            return "CON", rendered

        reason_choice = inputs[inp_idx]
        inp_idx += 1
        reason_map = {
            "1": ReasonCodeEnum.SICK,
            "2": ReasonCodeEnum.WORK,
            "3": ReasonCodeEnum.COST,
            "4": ReasonCodeEnum.DISTANCE,
            "5": ReasonCodeEnum.OTHER,
        }
        if reason_choice not in reason_map:
            body = get_msg("S_INVALID", lang) + get_msg("P_REASON", lang)
            rendered = render_ussd_response("CON", body)
            await save_request_cache(
                db, session_id, n_inputs, "P_REASON", "CON", rendered, start_time
            )
            return "CON", rendered

        # Commit: save reason on the absence record
        chosen_absence.reason_code = reason_map[reason_choice]
        chosen_absence.reason_source = ReasonSourceEnum.parent
        chosen_absence.reason_at = utc_now()
        await db.commit()

        body = get_msg("P_REASON_SAVED", lang)
        rendered = render_ussd_response("END", body)
        await save_request_cache(
            db, session_id, n_inputs, "P_REASON_SAVED", "END", rendered, start_time
        )
        return "END", rendered

    # --- Option 3: Ask for help ---
    if menu_choice == "3":
        if inp_idx >= n_inputs:
            body = get_msg("P_HELP", lang)
            rendered = render_ussd_response("CON", body)
            await save_request_cache(
                db, session_id, n_inputs, "P_HELP", "CON", rendered, start_time
            )
            return "CON", rendered

        help_choice = inputs[inp_idx]
        inp_idx += 1
        barrier_map = {
            "1": BarrierCodeEnum.COST,
            "2": BarrierCodeEnum.HUNGER,
            "3": BarrierCodeEnum.HEALTH,
            "4": BarrierCodeEnum.DISTANCE,
            "5": BarrierCodeEnum.FAMILY,
            "6": BarrierCodeEnum.OTHER,
        }
        if help_choice not in barrier_map:
            body = get_msg("S_INVALID", lang) + get_msg("P_HELP", lang)
            rendered = render_ussd_response("CON", body)
            await save_request_cache(
                db, session_id, n_inputs, "P_HELP", "CON", rendered, start_time
            )
            return "CON", rendered

        # Commit: create help_request
        help_req = HelpRequest(
            student_id=selected_student.id,
            guardian_id=guardian.id,
            barrier_code=barrier_map[help_choice],
        )
        db.add(help_req)
        await db.commit()

        body = get_msg("P_HELP_SENT", lang)
        rendered = render_ussd_response("END", body)
        await save_request_cache(
            db, session_id, n_inputs, "P_HELP_SENT", "END", rendered, start_time
        )
        return "END", rendered

    # --- Invalid menu choice ---
    body = get_msg("S_INVALID", lang) + get_msg("P_MENU", lang, child=child_short)
    rendered = render_ussd_response("CON", body)
    await save_request_cache(db, session_id, n_inputs, "P_MENU", "CON", rendered, start_time)
    return "CON", rendered


async def execute_mentor_flow(
    inputs: list[str],
    inp_idx: int,
    n_inputs: int,
    user: User,
    lang: LanguageEnum,
    session_id: str,
    start_time: float,
    db: AsyncSession,
) -> tuple[str, str]:
    """Replays and evaluates Mentor USSD screens."""
    # 1. Main Mentor Menu
    if inp_idx >= n_inputs:
        body = get_msg("M_MENU", lang)
        rendered = render_ussd_response("CON", body)
        await save_request_cache(db, session_id, n_inputs, "M_MENU", "CON", rendered, start_time)
        return "CON", rendered

    menu_choice = inputs[inp_idx]
    inp_idx += 1

    if menu_choice == "2":
        return await execute_language_flow(
            inputs=inputs,
            inp_idx=inp_idx,
            n_inputs=n_inputs,
            user=user,
            lang=lang,
            session_id=session_id,
            start_time=start_time,
            db=db,
        )
    elif menu_choice != "1":
        body = get_msg("S_INVALID", lang) + get_msg("M_MENU", lang)
        rendered = render_ussd_response("CON", body)
        await save_request_cache(db, session_id, n_inputs, "M_MENU", "CON", rendered, start_time)
        return "CON", rendered

    # 2. My Cases (M_CASES)
    active_statuses = [
        CaseStatusEnum.open,
        CaseStatusEnum.mentor_assigned,
        CaseStatusEnum.visited,
        CaseStatusEnum.escalated_sector,
    ]
    cases_res = await db.execute(
        select(Case)
        .options(
            selectinload(Case.student).selectinload(Student.class_group),
            selectinload(Case.student).selectinload(Student.guardians),
            selectinload(Case.school),
        )
        .where(
            Case.mentor_id == user.id,
            Case.status.in_(active_statuses),
        )
        .order_by(Case.opened_at.asc())
    )
    cases = cases_res.scalars().all()

    if not cases:
        body = get_msg("M_NO_CASES", lang)
        rendered = render_ussd_response("END", body)
        await save_request_cache(db, session_id, n_inputs, "M_CASES", "END", rendered, start_time)
        return "END", rendered

    # Display up to 4 cases
    displayed_cases = cases[:4]
    case_lines = []
    for idx, c in enumerate(displayed_cases, 1):
        st_name = c.student.full_name.split() if c.student else ["Student"]
        short_name = f"{st_name[0]} {st_name[1][0]}." if len(st_name) > 1 else st_name[0]
        case_lines.append(f"{idx}. {short_name} L{c.level}")

    if inp_idx >= n_inputs:
        body = get_msg("M_CASES", lang, n=len(cases), lines="\n".join(case_lines))
        rendered = render_ussd_response("CON", body)
        await save_request_cache(db, session_id, n_inputs, "M_CASES", "CON", rendered, start_time)
        return "CON", rendered

    case_choice = inputs[inp_idx]
    inp_idx += 1

    if case_choice == "0":
        # Back to mentor menu
        body = get_msg("M_MENU", lang)
        rendered = render_ussd_response("CON", body)
        await save_request_cache(db, session_id, n_inputs, "M_MENU", "CON", rendered, start_time)
        return "CON", rendered

    try:
        case_idx = int(case_choice) - 1
        if case_idx < 0 or case_idx >= len(displayed_cases):
            raise ValueError
        selected_case = displayed_cases[case_idx]
    except (ValueError, IndexError):
        body = get_msg("S_INVALID", lang) + get_msg("M_CASES", lang, n=len(cases), lines="\n".join(case_lines))
        rendered = render_ussd_response("CON", body)
        await save_request_cache(db, session_id, n_inputs, "M_CASES", "CON", rendered, start_time)
        return "CON", rendered

    # 3. Case Detail (M_CASE)
    st = selected_case.student
    today = get_kigali_today()
    abs_res = await db.execute(
        select(Absence).where(
            Absence.student_id == st.id,
            Absence.status == AbsenceStatusEnum.active,
            Absence.date >= today - timedelta(days=14),
        ).order_by(Absence.date.desc())
    )
    absences = abs_res.scalars().all()
    abs_count = len(absences)
    latest_reason = "none"
    for ab in absences:
        if ab.reason_code:
            latest_reason = ab.reason_code.value
            break

    st_name_parts = st.full_name.split() if st else ["Student"]
    short_st_name = f"{st_name_parts[0]} {st_name_parts[1][0]}." if len(st_name_parts) > 1 else st_name_parts[0]

    if inp_idx >= n_inputs:
        body = get_msg(
            "M_CASE_DETAIL",
            lang,
            child=short_st_name,
            class_name=st.class_group.name if st and st.class_group else "",
            school_name=selected_case.school.name if selected_case.school else "",
            absent_10d=abs_count,
            reason=latest_reason,
        )
        rendered = render_ussd_response("CON", body)
        await save_request_cache(db, session_id, n_inputs, "M_CASE", "CON", rendered, start_time)
        return "CON", rendered

    detail_choice = inputs[inp_idx]
    inp_idx += 1

    if detail_choice == "0":
        # Back to cases list
        body = get_msg("M_CASES", lang, n=len(cases), lines="\n".join(case_lines))
        rendered = render_ussd_response("CON", body)
        await save_request_cache(db, session_id, n_inputs, "M_CASES", "CON", rendered, start_time)
        return "CON", rendered

    if detail_choice != "1":
        body = get_msg("S_INVALID", lang) + get_msg(
            "M_CASE_DETAIL",
            lang,
            child=short_st_name,
            class_name=st.class_group.name if st and st.class_group else "",
            school_name=selected_case.school.name if selected_case.school else "",
            absent_10d=abs_count,
            reason=latest_reason,
        )
        rendered = render_ussd_response("CON", body)
        await save_request_cache(db, session_id, n_inputs, "M_CASE", "CON", rendered, start_time)
        return "CON", rendered

    # 4. Start Visit & Code Prompt (M_CODE)
    now = utc_now()
    active_vc_res = await db.execute(
        select(VisitCode).where(
            VisitCode.case_id == selected_case.id,
            VisitCode.mentor_id == user.id,
            VisitCode.expires_at > now,
            VisitCode.used_at.is_(None),
        ).order_by(VisitCode.created_at.desc()).limit(1)
    )
    active_vc = active_vc_res.scalar_one_or_none()

    # Spec approved fix: Side-effect happens only on terminal arrival of M_CODE screen
    if inp_idx >= n_inputs:
        if not active_vc:
            import random
            generated_code = f"{random.randint(1000, 9999)}"
            code_hash = hash_visit_code(generated_code)
            new_vc = VisitCode(
                case_id=selected_case.id,
                mentor_id=user.id,
                code_hash=code_hash,
                expires_at=now + timedelta(minutes=30),
            )
            db.add(new_vc)
            await db.flush()

            # Find primary guardian
            guardian = await get_primary_guardian(st, db) if st else None
            if guardian and guardian.phone_e164:
                    code_sms = (
                        f"Garuka visit code: {generated_code}. "
                        f"Give it only to mentor {user.full_name.split()[0]} at your home. Valid 30 min."
                    )
                    await enqueue_sms(
                        db=db,
                        to_e164=guardian.phone_e164,
                        template_key="parent_visit_code",
                        params={"vcode": generated_code, "mentor": user.full_name},
                        body=code_sms,
                        dedupe_key=f"visit_code:{new_vc.id}",
                        related_case_id=selected_case.id,
                        related_student_id=st.id,
                    )
            await db.commit()

        body = get_msg("M_CODE_PROMPT", lang)
        rendered = render_ussd_response("CON", body)
        await save_request_cache(db, session_id, n_inputs, "M_CODE", "CON", rendered, start_time)
        return "CON", rendered

    # Verification
    code_input = inputs[inp_idx]
    inp_idx += 1

    verified = False
    verified_method = VerifiedMethodEnum.unverified

    if code_input == "0":
        # Unverified visit (no code presented)
        verified = False
        verified_method = VerifiedMethodEnum.unverified
    else:
        # Check submitted code
        if not active_vc:
            body = get_msg("M_CODE_WRONG", lang)
            rendered = render_ussd_response("END", body)
            await save_request_cache(db, session_id, n_inputs, "M_CODE", "END", rendered, start_time)
            return "END", rendered

        if active_vc.attempts >= 3:
            body = get_msg("M_CODE_LOCKED", lang)
            rendered = render_ussd_response("END", body)
            await save_request_cache(db, session_id, n_inputs, "M_CODE", "END", rendered, start_time)
            return "END", rendered

        if verify_visit_code(code_input, active_vc.code_hash):
            verified = True
            verified_method = VerifiedMethodEnum.parent_code
            active_vc.used_at = utc_now()
            await db.commit()
        else:
            active_vc.attempts += 1
            await db.commit()
            if active_vc.attempts >= 3:
                body = get_msg("M_CODE_LOCKED", lang)
            else:
                body = get_msg("M_CODE_WRONG", lang)
            rendered = render_ussd_response("END", body)
            await save_request_cache(db, session_id, n_inputs, "M_CODE", "END", rendered, start_time)
            return "END", rendered

    # 5. Visit Outcome (M_OUTCOME)
    if inp_idx >= n_inputs:
        body = get_msg("M_OUTCOME", lang)
        rendered = render_ussd_response("CON", body)
        await save_request_cache(db, session_id, n_inputs, "M_OUTCOME", "CON", rendered, start_time)
        return "CON", rendered

    outcome_choice = inputs[inp_idx]
    inp_idx += 1

    outcome_map = {
        "1": VisitOutcomeEnum.will_return,
        "2": VisitOutcomeEnum.plan_agreed,
        "3": VisitOutcomeEnum.needs_sector_help,
        "4": VisitOutcomeEnum.moved_away,
    }
    if outcome_choice not in outcome_map:
        body = get_msg("S_INVALID", lang) + get_msg("M_OUTCOME", lang)
        rendered = render_ussd_response("CON", body)
        await save_request_cache(db, session_id, n_inputs, "M_OUTCOME", "CON", rendered, start_time)
        return "CON", rendered

    selected_outcome = outcome_map[outcome_choice]

    # 6. Barrier Choice (M_BARRIER) if outcome != will_return
    selected_barrier: BarrierCodeEnum | None = None
    if selected_outcome != VisitOutcomeEnum.will_return:
        if inp_idx >= n_inputs:
            body = get_msg("M_BARRIER", lang)
            rendered = render_ussd_response("CON", body)
            await save_request_cache(db, session_id, n_inputs, "M_BARRIER", "CON", rendered, start_time)
            return "CON", rendered

        barrier_choice = inputs[inp_idx]
        inp_idx += 1
        barrier_map = {
            "1": BarrierCodeEnum.COST,
            "2": BarrierCodeEnum.HUNGER,
            "3": BarrierCodeEnum.HEALTH,
            "4": BarrierCodeEnum.DISTANCE,
            "5": BarrierCodeEnum.FAMILY,
            "6": BarrierCodeEnum.OTHER,
        }
        selected_barrier = barrier_map.get(barrier_choice, BarrierCodeEnum.OTHER)

    # 7. Commit Node
    visit = MentorVisit(
        case_id=selected_case.id,
        mentor_id=user.id,
        started_at=utc_now(),
        verified=verified,
        verified_method=verified_method,
        outcome=selected_outcome,
        barrier_code=selected_barrier,
    )
    db.add(visit)

    if selected_outcome == VisitOutcomeEnum.needs_sector_help:
        selected_case.level = 3
        selected_case.status = CaseStatusEnum.escalated_sector
        # Find SEO
        if selected_case.school and selected_case.school.sector_id:
            seo_res = await db.execute(
                select(User).where(
                    User.role == RoleEnum.sector_officer,
                    User.sector_id == selected_case.school.sector_id,
                    User.is_active.is_(True),
                ).limit(1)
            )
            seo = seo_res.scalar_one_or_none()
            if seo:
                selected_case.sector_officer_id = seo.id
                if seo.phone_e164:
                    await enqueue_sms(
                        db=db,
                        to_e164=seo.phone_e164,
                        template_key="seo_escalation",
                        params={"ref": selected_case.ref, "school": selected_case.school.name},
                        body=f"Garuka: case {selected_case.ref} escalated at {selected_case.school.name}. Open the dashboard to review.",
                        dedupe_key=f"seo_esc:{selected_case.id}",
                        related_case_id=selected_case.id,
                    )
        db.add(
            CaseEvent(
                case_id=selected_case.id,
                type="escalated",
                actor_user_id=user.id,
                payload={"to_level": 3, "outcome": selected_outcome.value},
            )
        )
    else:
        selected_case.status = CaseStatusEnum.visited

    db.add(
        CaseEvent(
            case_id=selected_case.id,
            type="visit_logged",
            actor_user_id=user.id,
            payload={
                "verified": verified,
                "verified_method": verified_method.value,
                "outcome": selected_outcome.value,
                "barrier": selected_barrier.value if selected_barrier else None,
            },
        )
    )

    await db.commit()

    body = get_msg("M_COMMIT_SUCCESS", lang)
    rendered = render_ussd_response("END", body)
    await save_request_cache(db, session_id, n_inputs, "M_COMMIT", "END", rendered, start_time)
    return "END", rendered



async def execute_teacher_flow(
    inputs: list[str],
    inp_idx: int,
    n_inputs: int,
    user: User,
    lang: LanguageEnum,
    session_id: str,
    start_time: float,
    db: AsyncSession,
) -> tuple[str, str]:
    """Replays and evaluates Teacher USSD screens."""

    # Screen: Teacher Main Menu
    if inp_idx >= n_inputs:
        body = get_msg("T_MENU", lang)
        rendered = render_ussd_response("CON", body)
        await save_request_cache(db, session_id, n_inputs, "T_MENU", "CON", rendered, start_time)
        return "CON", rendered

    menu_choice = inputs[inp_idx]
    inp_idx += 1

    if menu_choice == "4":
        # Language flow
        return await execute_language_flow(
            inputs, inp_idx, n_inputs, user, lang, session_id, start_time, db
        )
    elif menu_choice == "2":
        # Today's Summary
        return await execute_summary_flow(user, lang, session_id, n_inputs, start_time, db)
    elif menu_choice == "3":
        # Flagged Students
        return await execute_flagged_flow(user, lang, session_id, n_inputs, start_time, db)
    elif menu_choice == "1":
        # Mark Absences Flow
        return await execute_mark_absences_flow(
            inputs, inp_idx, n_inputs, user, lang, session_id, start_time, db
        )
    else:
        body = get_msg("S_INVALID", lang) + get_msg("T_MENU", lang)
        rendered = render_ussd_response("CON", body)
        await save_request_cache(db, session_id, n_inputs, "T_MENU", "CON", rendered, start_time)
        return "CON", rendered


async def execute_language_flow(
    inputs: list[str],
    inp_idx: int,
    n_inputs: int,
    user: User,
    lang: LanguageEnum,
    session_id: str,
    start_time: float,
    db: AsyncSession,
) -> tuple[str, str]:
    if inp_idx >= n_inputs:
        body = get_msg("S_LANG", lang)
        rendered = render_ussd_response("CON", body)
        await save_request_cache(db, session_id, n_inputs, "S_LANG", "CON", rendered, start_time)
        return "CON", rendered

    lang_choice = inputs[inp_idx]
    lang_map = {"1": LanguageEnum.rw, "2": LanguageEnum.en, "3": LanguageEnum.fr}
    new_lang = lang_map.get(lang_choice, LanguageEnum.rw)

    user.language = new_lang
    await db.commit()

    body = get_msg("S_LANG_SAVED", new_lang)
    rendered = render_ussd_response("END", body)
    await save_request_cache(db, session_id, n_inputs, "S_LANG_SAVED", "END", rendered, start_time)
    return "END", rendered


async def execute_summary_flow(
    user: User,
    lang: LanguageEnum,
    session_id: str,
    n_inputs: int,
    start_time: float,
    db: AsyncSession,
) -> tuple[str, str]:
    today = get_kigali_today()
    classes_res = await db.execute(
        select(Class).where(Class.school_id == user.school_id).order_by(Class.name)
    )
    classes = classes_res.scalars().all()

    lines = []
    for c in classes:
        sub_res = await db.execute(
            select(AttendanceSubmission).where(
                AttendanceSubmission.class_id == c.id,
                AttendanceSubmission.date == today,
            )
        )
        sub = sub_res.scalar_one_or_none()
        if sub:
            lines.append(f"{c.name}: {sub.absent_count} absent")
        else:
            lines.append(f"{c.name}: not saved yet")

    body = get_msg(
        "T_SUMMARY",
        lang,
        date_str=today.strftime("%d/%m"),
        lines="\n".join(lines) if lines else "No classes.",
    )
    rendered = render_ussd_response("END", body)
    await save_request_cache(db, session_id, n_inputs, "T_SUMMARY", "END", rendered, start_time)
    return "END", rendered


async def execute_flagged_flow(
    user: User,
    lang: LanguageEnum,
    session_id: str,
    n_inputs: int,
    start_time: float,
    db: AsyncSession,
) -> tuple[str, str]:
    active_cases_res = await db.execute(
        select(Case)
        .options(selectinload(Case.student).selectinload(Student.class_group))
        .where(
            Case.school_id == user.school_id,
            Case.status.in_([
                CaseStatusEnum.open,
                CaseStatusEnum.mentor_assigned,
                CaseStatusEnum.visited,
                CaseStatusEnum.escalated_sector,
            ]),
        )
        .order_by(Case.opened_at.desc())
        .limit(5)
    )
    cases = active_cases_res.scalars().all()
    if cases:
        lines = []
        for c in cases:
            st = c.student
            st_name = st.full_name.split()[0] if st else "Student"
            cls_name = st.class_group.name if st and st.class_group else ""
            lines.append(f"{c.ref}: {st_name} ({cls_name})")
        lines_str = "\n".join(lines)
    else:
        lines_str = "No flagged students." if lang == LanguageEnum.en else "Nta bafite ikibazo."

    body = get_msg("T_FLAGGED", lang, lines=lines_str)
    rendered = render_ussd_response("END", body)
    await save_request_cache(db, session_id, n_inputs, "T_FLAGGED", "END", rendered, start_time)
    return "END", rendered


async def execute_mark_absences_flow(
    inputs: list[str],
    inp_idx: int,
    n_inputs: int,
    user: User,
    lang: LanguageEnum,
    session_id: str,
    start_time: float,
    db: AsyncSession,
) -> tuple[str, str]:
    # 1. Select Class: Check classes assigned to this teacher first
    teacher_classes_res = await db.execute(
        select(Class)
        .where(
            or_(
                Class.class_teacher_id == user.id,
                Class.id.in_(
                    select(class_teachers.c.class_id).where(class_teachers.c.user_id == user.id)
                ),
            )
        )
        .order_by(Class.name)
    )
    classes = teacher_classes_res.scalars().all()
    if not classes and user.school_id:
        classes_res = await db.execute(
            select(Class).where(Class.school_id == user.school_id).order_by(Class.name)
        )
        classes = classes_res.scalars().all()

    if not classes:
        rendered = render_ussd_response("END", "No classes registered for your school.")
        await save_request_cache(db, session_id, n_inputs, "T_CLASS", "END", rendered, start_time)
        return "END", rendered

    if len(classes) == 1:
        selected_class = classes[0]
    else:
        displayed_classes = classes[:5]
        options = "\n".join([f"{idx + 1}. {c.name}" for idx, c in enumerate(displayed_classes)])
        if inp_idx >= n_inputs:
            body = f"Select class:\n{options}"
            rendered = render_ussd_response("CON", body)
            await save_request_cache(
                db, session_id, n_inputs, "T_CLASS", "CON", rendered, start_time
            )
            return "CON", rendered

        class_choice = inputs[inp_idx]
        inp_idx += 1
        try:
            c_idx = int(class_choice) - 1
            if c_idx < 0 or c_idx >= len(displayed_classes):
                raise ValueError
            selected_class = displayed_classes[c_idx]
        except ValueError:
            body = get_msg("S_INVALID", lang) + f"Select class:\n{options}"
            rendered = render_ussd_response("CON", body)
            await save_request_cache(
                db, session_id, n_inputs, "T_CLASS", "CON", rendered, start_time
            )
            return "CON", rendered

    # 2. Select Date
    available_dates = await get_available_attendance_dates(
        db, max_backdate_days=settings.RULE_MAX_BACKDATE_SCHOOL_DAYS
    )
    today_kigali = get_kigali_today()
    if not available_dates:
        available_dates = [today_kigali]

    date_options = []
    for d_idx, d in enumerate(available_dates):
        label = "Today" if d == today_kigali else "Yesterday" if d_idx == 1 else d.strftime("%d/%m")
        date_options.append(f"{d_idx + 1}. {label} ({d.strftime('%d/%m')})")
    date_options.append("0. Back")

    if inp_idx >= n_inputs:
        body = "Date:\n" + "\n".join(date_options)
        rendered = render_ussd_response("CON", body)
        await save_request_cache(db, session_id, n_inputs, "T_DATE", "CON", rendered, start_time)
        return "CON", rendered

    date_choice = inputs[inp_idx]
    inp_idx += 1
    if date_choice == "0":
        # Back to Main Menu
        body = get_msg("T_MENU", lang)
        rendered = render_ussd_response("CON", body)
        await save_request_cache(db, session_id, n_inputs, "T_MENU", "CON", rendered, start_time)
        return "CON", rendered

    try:
        d_idx = int(date_choice) - 1
        if d_idx < 0 or d_idx >= len(available_dates):
            raise ValueError
        selected_date = available_dates[d_idx]
    except ValueError:
        body = get_msg("S_INVALID", lang) + "Date:\n" + "\n".join(date_options)
        rendered = render_ussd_response("CON", body)
        await save_request_cache(db, session_id, n_inputs, "T_DATE", "CON", rendered, start_time)
        return "CON", rendered

    # 3. Check Existing Submission
    sub_res = await db.execute(
        select(AttendanceSubmission).where(
            AttendanceSubmission.class_id == selected_class.id,
            AttendanceSubmission.date == selected_date,
        )
    )
    existing_sub = sub_res.scalar_one_or_none()
    is_replacing = False

    if existing_sub:
        if inp_idx >= n_inputs:
            body = get_msg(
                "T_ALREADY",
                lang,
                class_name=selected_class.name,
                date_str=selected_date.strftime("%d/%m"),
                n=existing_sub.absent_count,
            )
            rendered = render_ussd_response("CON", body)
            await save_request_cache(
                db, session_id, n_inputs, "T_ALREADY", "CON", rendered, start_time
            )
            return "CON", rendered

        already_choice = inputs[inp_idx]
        inp_idx += 1
        if already_choice == "0":
            # Back
            body = get_msg("T_MENU", lang)
            rendered = render_ussd_response("CON", body)
            await save_request_cache(
                db, session_id, n_inputs, "T_MENU", "CON", rendered, start_time
            )
            return "CON", rendered
        elif already_choice == "1":
            is_replacing = True
        else:
            body = get_msg("S_INVALID", lang) + get_msg(
                "T_ALREADY",
                lang,
                class_name=selected_class.name,
                date_str=selected_date.strftime("%d/%m"),
                n=existing_sub.absent_count,
            )
            rendered = render_ussd_response("CON", body)
            await save_request_cache(
                db, session_id, n_inputs, "T_ALREADY", "CON", rendered, start_time
            )
            return "CON", rendered

    # 4. Roll Number Entry Loop
    students_res = await db.execute(
        select(Student)
        .options(selectinload(Student.guardians))
        .where(Student.class_id == selected_class.id, Student.status == StudentStatusEnum.active)
        .order_by(Student.roll_number)
    )
    students = students_res.scalars().all()
    students_by_roll = {s.roll_number: s for s in students}
    min_roll = min(students_by_roll.keys()) if students_by_roll else 1
    max_roll = max(students_by_roll.keys()) if students_by_roll else 50

    absent_rolls: set[int] = set()
    prefix = ""

    while inp_idx < n_inputs:
        roll_inp = inputs[inp_idx]
        inp_idx += 1

        if roll_inp == "00":
            # Cancel to menu
            body = get_msg("T_MENU", lang)
            rendered = render_ussd_response("CON", body)
            await save_request_cache(
                db, session_id, n_inputs, "T_MENU", "CON", rendered, start_time
            )
            return "CON", rendered

        if roll_inp == "0":
            # Finish entry, proceed to confirmation
            break

        try:
            r = int(roll_inp)
            if r in students_by_roll:
                absent_rolls.add(r)
                s_name = students_by_roll[r].full_name.split()
                short_name = f"{s_name[0]} {s_name[1][0]}." if len(s_name) > 1 else s_name[0]
                prefix = f"Added {r} {short_name}.\n"
            else:
                prefix = f"Roll {r} not found.\n"
        except ValueError:
            prefix = f"Roll {roll_inp} not found.\n"

    # If user hasn't pressed 0 to finish yet, continue showing entry prompt
    if inp_idx >= n_inputs and (n_inputs == 0 or inputs[-1] != "0"):
        body = get_msg(
            "T_ROLL",
            lang,
            prefix=prefix,
            n=len(absent_rolls),
            min_roll=min_roll,
            max_roll=max_roll,
        )
        rendered = render_ussd_response("CON", body)
        await save_request_cache(db, session_id, n_inputs, "T_ROLL", "CON", rendered, start_time)
        return "CON", rendered

    # 5. Confirmation Screen
    sorted_rolls = sorted(absent_rolls)
    if len(sorted_rolls) > 8:
        rolls_str = f"{len(sorted_rolls)} students"
    else:
        rolls_str = ", ".join(map(str, sorted_rolls))

    if inp_idx >= n_inputs:
        if len(sorted_rolls) > 0:
            body = get_msg("T_CONFIRM", lang, n=len(sorted_rolls), rolls=rolls_str)
        else:
            body = get_msg("T_CONFIRM_ALL_PRESENT", lang)
        rendered = render_ussd_response("CON", body)
        await save_request_cache(db, session_id, n_inputs, "T_CONFIRM", "CON", rendered, start_time)
        return "CON", rendered

    confirm_choice = inputs[inp_idx]
    inp_idx += 1

    if confirm_choice == "2":
        # Cancel
        body = get_msg("T_MENU", lang)
        rendered = render_ussd_response("CON", body)
        await save_request_cache(db, session_id, n_inputs, "T_MENU", "CON", rendered, start_time)
        return "CON", rendered
    elif confirm_choice != "1":
        if len(sorted_rolls) > 0:
            body = get_msg("S_INVALID", lang) + get_msg(
                "T_CONFIRM", lang, n=len(sorted_rolls), rolls=rolls_str
            )
        else:
            body = get_msg("S_INVALID", lang) + get_msg("T_CONFIRM_ALL_PRESENT", lang)
        rendered = render_ussd_response("CON", body)
        await save_request_cache(db, session_id, n_inputs, "T_CONFIRM", "CON", rendered, start_time)
        return "CON", rendered

    # 6. Commit Node (Terminal Screen)
    absent_students = [students_by_roll[r] for r in sorted_rolls]
    absent_student_ids = {s.id for s in absent_students}

    await record_class_attendance(
        db=db,
        class_id=selected_class.id,
        target_date=selected_date,
        absent_student_ids=absent_student_ids,
        submitted_by_user_id=user.id,
        submitted_by_role=user.role.value,
        source=SubmissionSourceEnum.ussd,
        class_name=selected_class.name,
    )

    # Proactively dispatch pending outbox so SMS is delivered immediately
    try:
        await process_outbox_batch(db)
    except Exception as e:  # noqa: BLE001
        logger.warning("Proactive outbox dispatch failed: %s", e)

    body = get_msg(
        "T_COMMIT_SUCCESS",
        lang,
        n=len(sorted_rolls),
        class_name=selected_class.name,
        date_str=selected_date.strftime("%d/%m"),
    )
    rendered = render_ussd_response("END", body)
    await save_request_cache(db, session_id, n_inputs, "T_COMMIT", "END", rendered, start_time)
    return "END", rendered


async def save_request_cache(
    db: AsyncSession,
    session_id: str,
    n_inputs: int,
    screen_key: str,
    kind: str,
    body: str,
    start_time: float,
):
    latency_ms = int((time.time() - start_time) * 1000)
    req = UssdRequest(
        session_id=session_id,
        n_inputs=n_inputs,
        screen_key=screen_key,
        response_kind=kind,
        response_body=body,
        latency_ms=latency_ms,
        created_at=utc_now(),
    )
    try:
        async with db.begin_nested():
            db.add(req)
        await db.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to save USSD request cache: %s", e)
