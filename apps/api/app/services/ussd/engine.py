import logging
import time
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import hash_phone
from app.core.security import get_pin_hash, verify_pin
from app.models.attendance import (
    Absence,
    AbsenceStatusEnum,
    AttendanceSubmission,
    SubmissionSourceEnum,
)
from app.models.base import utc_now
from app.models.messaging import UssdRequest, UssdSession
from app.models.student import Class, Student, StudentStatusEnum
from app.models.user import LanguageEnum, User
from app.services.sms.outbox_worker import enqueue_sms
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
    if clean_text:
        # Strip trailing asterisks
        clean_text = clean_text.rstrip("*")
        inputs = [p.strip() for p in clean_text.split("*") if p.strip()]
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
            # Parent flow (Milestone M4)
            rendered = render_ussd_response("END", "Parent flow coming soon in M4.")
            await save_request_cache(
                db, session_id, n_inputs, "P_MENU", "END", rendered, start_time
            )
            return "END", rendered
        elif choice != "1":
            body = get_msg("S_INVALID", lang) + get_msg("S_ROLE_PICK", lang)
            rendered = render_ussd_response("CON", body)
            await save_request_cache(
                db, session_id, n_inputs, "S_ROLE_PICK", "CON", rendered, start_time
            )
            return "CON", rendered

    user = identity.user
    if not user:
        # Guardian only -> parent flow
        rendered = render_ussd_response("END", "Parent flow coming soon in M4.")
        await save_request_cache(db, session_id, n_inputs, "P_MENU", "END", rendered, start_time)
        return "END", rendered

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

    # 6. Authenticated Staff Navigation (Teacher Flow)
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
    body = get_msg("T_FLAGGED", lang, lines="No flagged students currently.")
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
    # 1. Select Class
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
        if inp_idx >= n_inputs:
            options = "\n".join([f"{idx + 1}. {c.name}" for idx, c in enumerate(classes)])
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
            if c_idx < 0 or c_idx >= len(classes):
                raise ValueError
            selected_class = classes[c_idx]
        except ValueError:
            options = "\n".join([f"{idx + 1}. {c.name}" for idx, c in enumerate(classes)])
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
    # Upsert AttendanceSubmission
    if existing_sub:
        existing_sub.absent_count = len(sorted_rolls)
        existing_sub.submitted_by = user.id
        existing_sub.submitted_at = utc_now()
        submission = existing_sub
    else:
        submission = AttendanceSubmission(
            class_id=selected_class.id,
            date=selected_date,
            submitted_by=user.id,
            source=SubmissionSourceEnum.ussd,
            absent_count=len(sorted_rolls),
            submitted_at=utc_now(),
        )
        db.add(submission)
        await db.flush()

    # Void absences not in the new list if replacing
    absent_students = [students_by_roll[r] for r in sorted_rolls]
    absent_student_ids = {s.id for s in absent_students}

    if is_replacing:
        existing_absences_res = await db.execute(
            select(Absence).where(
                Absence.submission_id == submission.id,
                Absence.date == selected_date,
            )
        )
        for old_abs in existing_absences_res.scalars().all():
            if old_abs.student_id not in absent_student_ids:
                old_abs.status = AbsenceStatusEnum.voided

    # Insert newly absent students and enqueue parent SMS
    for student in absent_students:
        abs_check = await db.execute(
            select(Absence).where(
                Absence.student_id == student.id,
                Absence.date == selected_date,
            )
        )
        existing_abs = abs_check.scalar_one_or_none()
        if not existing_abs:
            abs_record = Absence(
                student_id=student.id,
                date=selected_date,
                submission_id=submission.id,
                status=AbsenceStatusEnum.active,
            )
            db.add(abs_record)

            # Enqueue parent SMS to primary guardian
            if student.guardians:
                primary_guardian = student.guardians[0]
                if not primary_guardian.sms_opt_out:
                    sms_body = (
                        f"Garuka: {student.full_name.split()[0]} was marked absent at "
                        f"{selected_class.name} on {selected_date.strftime('%d/%m')}. "
                        f"Dial {settings.USSD_SERVICE_CODE_DISPLAY} to tell us why."
                    )
                    await enqueue_sms(
                        db=db,
                        to_e164=primary_guardian.phone_e164,
                        template_key="parent_absence",
                        params={"child": student.full_name, "date": str(selected_date)},
                        body=sms_body,
                        dedupe_key=f"absence:{student.id}:{selected_date}",
                        related_student_id=student.id,
                    )

    await db.commit()

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
    db.add(req)
    try:
        await db.commit()
    except Exception:  # noqa: BLE001
        await db.rollback()
