import logging
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.attendance import (
    Absence,
    AbsenceStatusEnum,
    AttendanceSubmission,
    ReasonSourceEnum,
    SubmissionSourceEnum,
)
from app.models.base import utc_now
from app.models.messaging import AuditLog
from app.models.student import Class, Student, student_guardians
from app.services.rules_engine import evaluate_student
from app.services.sms.outbox_worker import enqueue_sms

logger = logging.getLogger("garuka.attendance_service")


class AttendanceValidationError(Exception):
    pass


class AttendanceNotFoundError(Exception):
    pass


async def record_class_attendance(
    db: AsyncSession,
    class_id: uuid.UUID,
    target_date: date,
    absent_student_ids: set[uuid.UUID],
    submitted_by_user_id: uuid.UUID,
    submitted_by_role: str,
    source: SubmissionSourceEnum = SubmissionSourceEnum.dashboard,
    class_name: str | None = None,
) -> AttendanceSubmission:
    """
    Service function managing class attendance recording and absence replacement
    with an explicit atomic transaction boundary.

    Steps:
    1. Validates absent student IDs belong to this class.
    2. Upserts the AttendanceSubmission record.
    3. Reconciles absences: voids removed absences, creates/reactivates present absences.
    4. Enqueues SMS alert to primary guardian for newly marked absent students (with consent check).
    5. Writes an immutable audit log record.
    6. Triggers dropout rules engine evaluation for marked absent students.
    7. Atomically commits all changes; rolls back on any unhandled failure.
    """
    try:
        # 1. Validate absent student IDs belong to class
        if absent_student_ids:
            valid_res = await db.execute(
                select(Student.id).where(
                    Student.id.in_(absent_student_ids),
                    Student.class_id == class_id,
                )
            )
            found_ids = set(valid_res.scalars().all())
            invalid_ids = absent_student_ids - found_ids
            if invalid_ids:
                raise AttendanceValidationError(
                    f"Students not in this class: {[str(i) for i in invalid_ids]}"
                )

        if not class_name:
            cls = await db.get(Class, class_id)
            if cls:
                class_name = cls.name

        # 2. Upsert AttendanceSubmission
        sub_res = await db.execute(
            select(AttendanceSubmission).where(
                AttendanceSubmission.class_id == class_id,
                AttendanceSubmission.date == target_date,
            )
        )
        submission = sub_res.scalar_one_or_none()

        if not submission:
            submission = AttendanceSubmission(
                class_id=class_id,
                date=target_date,
                submitted_by=submitted_by_user_id,
                source=source,
                absent_count=len(absent_student_ids),
                submitted_at=utc_now(),
            )
            db.add(submission)
            await db.flush()
        else:
            submission.submitted_by = submitted_by_user_id
            submission.source = source
            submission.absent_count = len(absent_student_ids)
            submission.submitted_at = utc_now()
            await db.flush()

        # 3. Reconcile absences
        existing_abs_res = await db.execute(
            select(Absence).where(
                Absence.submission_id == submission.id,
            )
        )
        existing_absences = {ab.student_id: ab for ab in existing_abs_res.scalars().all()}

        # Void absences not in payload
        for sid, ab in existing_absences.items():
            if sid not in absent_student_ids and ab.status == AbsenceStatusEnum.active:
                ab.status = AbsenceStatusEnum.voided

        # Add or un-void absences in payload
        for sid in absent_student_ids:
            if sid in existing_absences:
                ab = existing_absences[sid]
                if ab.status == AbsenceStatusEnum.voided:
                    ab.status = AbsenceStatusEnum.active
            else:
                new_ab = Absence(
                    student_id=sid,
                    date=target_date,
                    submission_id=submission.id,
                    status=AbsenceStatusEnum.active,
                    reason_source=ReasonSourceEnum.teacher,
                )
                db.add(new_ab)

                # Enqueue SMS for newly marked absent student with consent check
                st_res = await db.execute(
                    select(Student).options(selectinload(Student.guardians)).where(Student.id == sid)
                )
                st = st_res.scalar_one_or_none()
                if st and st.guardians:
                    primary_link = await db.execute(
                        select(student_guardians.c.guardian_id).where(
                            student_guardians.c.student_id == sid,
                            student_guardians.c.is_primary.is_(True),
                        )
                    )
                    p_id = primary_link.scalar_one_or_none()
                    guardian = next((g for g in st.guardians if g.id == p_id), st.guardians[0])
                    if guardian and guardian.phone_e164 and not guardian.sms_opt_out and (guardian.consent_at is not None):
                        class_label = f" at {class_name}" if class_name else ""
                        sms_body = (
                            f"Garuka: {st.full_name.split()[0]} was marked absent{class_label} on "
                            f"{target_date.strftime('%d/%m')}. Dial {settings.USSD_SERVICE_CODE_DISPLAY} to tell us why."
                        )
                        await enqueue_sms(
                            db=db,
                            to_e164=guardian.phone_e164,
                            template_key="parent_absence",
                            params={"child": st.full_name, "date": str(target_date)},
                            body=sms_body,
                            dedupe_key=f"absence:{st.id}:{target_date}",
                            related_student_id=st.id,
                        )

        # 4. Audit Log
        audit = AuditLog(
            actor_user_id=submitted_by_user_id,
            actor_role=submitted_by_role,
            action="submit_attendance",
            entity_type="attendance_submission",
            entity_id=str(submission.id),
            meta={
                "class_id": str(class_id),
                "date": str(target_date),
                "absent_count": len(absent_student_ids),
                "source": source.value,
            },
            created_at=utc_now(),
        )
        db.add(audit)

        # 5. Dropout rules engine evaluation
        for sid in absent_student_ids:
            try:
                await evaluate_student(sid, db)
            except Exception as e:  # noqa: BLE001
                logger.error("Error evaluating student %s during attendance submission: %s", sid, e)

        # 6. Explicit transaction commit
        await db.commit()
        await db.refresh(submission)
        return submission

    except Exception:
        await db.rollback()
        raise


async def void_absence_record(
    db: AsyncSession,
    absence_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: str,
) -> dict:
    """
    Void an absence record and adjust attendance submission counts within an explicit transaction boundary.
    """
    try:
        ab_res = await db.execute(select(Absence).where(Absence.id == absence_id))
        absence = ab_res.scalar_one_or_none()
        if not absence:
            raise AttendanceNotFoundError("Absence record not found")

        if absence.status == AbsenceStatusEnum.voided:
            return {"status": "already_voided", "id": str(absence.id)}

        absence.status = AbsenceStatusEnum.voided

        if absence.submission_id:
            sub = await db.get(AttendanceSubmission, absence.submission_id)
            if sub and sub.absent_count > 0:
                sub.absent_count -= 1

        audit = AuditLog(
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action="void_absence",
            entity_type="absence",
            entity_id=str(absence.id),
            meta={"student_id": str(absence.student_id), "date": str(absence.date)},
            created_at=utc_now(),
        )
        db.add(audit)

        await db.commit()
        return {"status": "voided", "id": str(absence.id)}

    except Exception:
        await db.rollback()
        raise
