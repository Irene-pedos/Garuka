import csv
import io
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.rbac import get_current_user, require_roles
from app.db.session import get_db
from app.models.attendance import (
    Absence,
    AbsenceStatusEnum,
    AttendanceSubmission,
    ReasonSourceEnum,
    SubmissionSourceEnum,
)
from app.models.base import utc_now
from app.models.geo import School
from app.models.messaging import AuditLog
from app.models.student import Class, Student, StudentStatusEnum, student_guardians
from app.models.user import RoleEnum, User
from app.schemas.attendance import (
    AttendanceSubmissionResponse,
    ClassAttendanceResponse,
    ClassCompliance,
    DayCompliance,
    SchoolComplianceResponse,
    StudentAttendanceItem,
    SubmitAttendanceRequest,
)
from app.services.rules_engine import evaluate_student
from app.services.sms.outbox_worker import enqueue_sms
from app.services.ussd.calendar_helper import get_kigali_today, is_school_day

router = APIRouter(tags=["attendance"])


async def check_school_access(school: School, user: User) -> None:
    if user.role == RoleEnum.admin:
        return
    if user.role == RoleEnum.district_director:
        # Check district via sector
        if school.sector and school.sector.district_id != user.district_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Outside your district"
            )
        return
    if user.role == RoleEnum.sector_officer:
        if school.sector_id != user.sector_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Outside your sector")
        return
    if user.role in (RoleEnum.head_teacher, RoleEnum.teacher):
        if school.id != user.school_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Outside your school")
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


@router.get(
    "/classes/{class_id}/attendance",
    response_model=ClassAttendanceResponse,
    operation_id="get_class_attendance",
    summary="Get attendance and student list for class on date",
)
async def get_class_attendance(
    class_id: uuid.UUID,
    date_val: date | None = Query(None, alias="date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_date = date_val or get_kigali_today()

    cls = await db.get(Class, class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    school = await db.get(School, cls.school_id, options=[selectinload(School.sector)])
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    await check_school_access(school, current_user)

    # 1. Fetch submission for class and date
    sub_res = await db.execute(
        select(AttendanceSubmission).where(
            AttendanceSubmission.class_id == class_id,
            AttendanceSubmission.date == target_date,
        )
    )
    submission = sub_res.scalar_one_or_none()

    # 2. Fetch all active students in class
    students_res = await db.execute(
        select(Student)
        .where(Student.class_id == class_id, Student.status == StudentStatusEnum.active)
        .order_by(Student.roll_number)
    )
    students = students_res.scalars().all()

    # 3. Fetch active absences for this date
    student_ids = [s.id for s in students]
    absences_map = {}
    if student_ids:
        abs_res = await db.execute(
            select(Absence).where(
                Absence.student_id.in_(student_ids),
                Absence.date == target_date,
            )
        )
        for ab in abs_res.scalars().all():
            absences_map[ab.student_id] = ab

    student_items: list[StudentAttendanceItem] = []
    for s in students:
        ab = absences_map.get(s.id)
        is_abs = ab is not None and ab.status == AbsenceStatusEnum.active
        student_items.append(
            StudentAttendanceItem(
                id=s.id,
                roll_number=s.roll_number,
                full_name=s.full_name,
                is_absent=is_abs,
                absence_id=ab.id if ab else None,
                reason_code=ab.reason_code if ab else None,
                status=ab.status if ab else None,
            )
        )

    sub_resp = AttendanceSubmissionResponse.model_validate(submission) if submission else None

    return ClassAttendanceResponse(
        class_id=cls.id,
        class_name=cls.name,
        date=target_date,
        submission=sub_resp,
        students=student_items,
    )


@router.post(
    "/classes/{class_id}/attendance",
    response_model=AttendanceSubmissionResponse,
    operation_id="submit_class_attendance",
    summary="Submit or update attendance for class on date",
)
async def submit_class_attendance(
    class_id: uuid.UUID,
    payload: SubmitAttendanceRequest,
    current_user: User = Depends(
        require_roles(RoleEnum.admin, RoleEnum.head_teacher, RoleEnum.teacher)
    ),
    db: AsyncSession = Depends(get_db),
):
    cls = await db.get(Class, class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    school = await db.get(School, cls.school_id, options=[selectinload(School.sector)])
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    await check_school_access(school, current_user)

    target_date = payload.date
    absent_ids_set = set(payload.absent_student_ids)

    # Validate that absent students belong to this class
    if absent_ids_set:
        valid_res = await db.execute(
            select(Student.id).where(
                Student.id.in_(absent_ids_set),
                Student.class_id == class_id,
            )
        )
        found_ids = set(valid_res.scalars().all())
        invalid_ids = absent_ids_set - found_ids
        if invalid_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Students not in this class: {[str(i) for i in invalid_ids]}",
            )

    # 1. Upsert AttendanceSubmission
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
            submitted_by=current_user.id,
            source=SubmissionSourceEnum.dashboard,
            absent_count=len(absent_ids_set),
            submitted_at=utc_now(),
        )
        db.add(submission)
        await db.flush()
    else:
        submission.submitted_by = current_user.id
        submission.source = SubmissionSourceEnum.dashboard
        submission.absent_count = len(absent_ids_set)
        submission.submitted_at = utc_now()
        await db.flush()

    # 2. Reconcile absences
    existing_abs_res = await db.execute(
        select(Absence).where(
            Absence.submission_id == submission.id,
        )
    )
    existing_absences = {ab.student_id: ab for ab in existing_abs_res.scalars().all()}

    # Void absences not in payload
    for sid, ab in existing_absences.items():
        if sid not in absent_ids_set and ab.status == AbsenceStatusEnum.active:
            ab.status = AbsenceStatusEnum.voided

    # Add or un-void absences in payload
    for sid in absent_ids_set:
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

            # Enqueue SMS for newly marked absent student
            st_res = await db.execute(
                select(Student).options(selectinload(Student.guardians)).where(Student.id == sid)
            )
            st = st_res.scalar_one_or_none()
            if st and st.guardians:
                # Find primary guardian
                primary_link = await db.execute(
                    select(student_guardians.c.guardian_id).where(
                        student_guardians.c.student_id == sid,
                        student_guardians.c.is_primary.is_(True),
                    )
                )
                p_id = primary_link.scalar_one_or_none()
                guardian = next((g for g in st.guardians if g.id == p_id), st.guardians[0])
                if guardian and guardian.phone_e164 and not guardian.sms_opt_out:
                    sms_body = (
                        f"Muraho, {st.full_name} ntiyabonetse ku ishuri uyu munsi "
                        f"({target_date.strftime('%d/%m')}). Kanda *384*1234# usobanure impamvu."
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

    # 3. Create Audit Log
    audit = AuditLog(
        actor_user_id=current_user.id,
        actor_role=current_user.role.value,
        action="submit_attendance",
        entity_type="attendance_submission",
        entity_id=str(submission.id),
        meta={
            "class_id": str(class_id),
            "date": str(target_date),
            "absent_count": len(absent_ids_set),
            "source": "dashboard",
        },
    )
    db.add(audit)

    # 4. Trigger dropout rules evaluation
    for sid in absent_ids_set:
        await evaluate_student(sid, db)

    await db.commit()
    await db.refresh(submission)
    return submission



@router.delete(
    "/absences/{absence_id}",
    operation_id="void_absence",
    summary="Void an absence record",
)
async def void_absence(
    absence_id: uuid.UUID,
    current_user: User = Depends(require_roles(RoleEnum.admin, RoleEnum.head_teacher)),
    db: AsyncSession = Depends(get_db),
):
    ab_res = await db.execute(select(Absence).where(Absence.id == absence_id))
    absence = ab_res.scalar_one_or_none()
    if not absence:
        raise HTTPException(status_code=404, detail="Absence record not found")

    student = await db.get(Student, absence.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if current_user.role == RoleEnum.head_teacher and student.school_id != current_user.school_id:
        raise HTTPException(status_code=403, detail="Cannot void absence for another school")

    if absence.status == AbsenceStatusEnum.voided:
        return {"status": "already_voided", "id": str(absence.id)}

    absence.status = AbsenceStatusEnum.voided

    # Update submission absent_count if linked
    if absence.submission_id:
        sub = await db.get(AttendanceSubmission, absence.submission_id)
        if sub and sub.absent_count > 0:
            sub.absent_count -= 1

    audit = AuditLog(
        actor_user_id=current_user.id,
        actor_role=current_user.role.value,
        action="void_absence",
        entity_type="absence",
        entity_id=str(absence.id),
        meta={"student_id": str(absence.student_id), "date": str(absence.date)},
    )
    db.add(audit)

    await db.commit()
    return {"status": "voided", "id": str(absence.id)}


@router.get(
    "/attendance/compliance",
    response_model=SchoolComplianceResponse,
    operation_id="get_attendance_compliance",
    summary="Get class compliance grid for school and date range",
)
async def get_attendance_compliance(
    school_id: uuid.UUID,
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    format: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    school = await db.get(School, school_id, options=[selectinload(School.sector)])
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    await check_school_access(school, current_user)

    today = get_kigali_today()
    end_d = to_date or today
    start_d = from_date or (end_d - timedelta(days=14))

    # Generate dates list
    curr = start_d
    dates_list: list[date] = []
    while curr <= end_d:
        dates_list.append(curr)
        curr += timedelta(days=1)

    # Pre-check school days for these dates
    school_day_flags = {}
    for d in dates_list:
        school_day_flags[d] = await is_school_day(d, db)

    # Fetch classes for school
    classes_res = await db.execute(
        select(Class).where(Class.school_id == school_id).order_by(Class.grade, Class.name)
    )
    classes = classes_res.scalars().all()

    # Fetch submissions in date range
    sub_res = await db.execute(
        select(AttendanceSubmission).where(
            AttendanceSubmission.class_id.in_([c.id for c in classes]),
            AttendanceSubmission.date >= start_d,
            AttendanceSubmission.date <= end_d,
        )
    )
    submissions_by_class_date = {(sub.class_id, sub.date): sub for sub in sub_res.scalars().all()}

    class_compliances: list[ClassCompliance] = []
    total_school_day_slots = 0
    total_submitted_slots = 0

    for c in classes:
        days: list[DayCompliance] = []
        for d in dates_list:
            if not school_day_flags[d]:
                days.append(DayCompliance(date=d, status="non_school_day", absent_count=None))
            else:
                total_school_day_slots += 1
                sub = submissions_by_class_date.get((c.id, d))
                if sub:
                    total_submitted_slots += 1
                    days.append(
                        DayCompliance(date=d, status="submitted", absent_count=sub.absent_count)
                    )
                else:
                    days.append(DayCompliance(date=d, status="missing", absent_count=None))
        class_compliances.append(
            ClassCompliance(
                class_id=c.id,
                class_name=c.name,
                grade=c.grade,
                days=days,
            )
        )

    compliance_pct = (
        round((total_submitted_slots / total_school_day_slots) * 100.0, 1)
        if total_school_day_slots > 0
        else 100.0
    )

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Class", "Grade", "Date", "Status", "AbsentCount"])
        for cc in class_compliances:
            for day in cc.days:
                writer.writerow(
                    [
                        cc.class_name,
                        cc.grade,
                        day.date.isoformat(),
                        day.status,
                        day.absent_count or 0,
                    ]
                )
        csv_bytes = output.getvalue().encode("utf-8")
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="compliance_{school.name}_{start_d}_{end_d}.csv"'
            },
        )

    return SchoolComplianceResponse(
        school_id=school.id,
        school_name=school.name,
        from_date=start_d,
        to_date=end_d,
        compliance_pct=compliance_pct,
        classes=class_compliances,
    )
