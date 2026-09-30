import csv
import io
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.student import (
    Class,
    Guardian,
    SexEnum,
    Student,
    StudentStatusEnum,
    student_guardians,
)
from app.models.user import LanguageEnum
from app.schemas.student import CSVImportResult, CSVImportRowError

PHONE_REGEX = re.compile(r"^\+2507\d{8}$")


def validate_e164(phone: str) -> bool:
    return bool(PHONE_REGEX.match(phone.strip()))


async def import_students_csv(
    db: AsyncSession,
    school_id: uuid.UUID,
    csv_content: str,
    dry_run: bool = False,
) -> CSVImportResult:
    f = io.StringIO(csv_content.strip())
    reader = csv.DictReader(f)

    if not reader.fieldnames:
        return CSVImportResult(
            created=0,
            updated=0,
            skipped=0,
            errors=[CSVImportRowError(row=1, message="Empty CSV file or missing headers")],
        )

    # Normalize header names (lowercase and stripped)
    headers = [h.strip().lower() for h in reader.fieldnames if h]
    required_headers = {"full_name", "class_name", "roll_number", "guardian_name", "guardian_phone"}
    missing = required_headers - set(headers)
    if missing:
        return CSVImportResult(
            created=0,
            updated=0,
            skipped=0,
            errors=[CSVImportRowError(row=1, message=f"Missing required columns: {', '.join(sorted(missing))}")],
        )

    errors: list[CSVImportRowError] = []
    created_count = 0
    updated_count = 0
    skipped_count = 0

    # Cache classes for this school
    class_res = await db.execute(select(Class).where(Class.school_id == school_id))
    classes_by_name = {c.name.strip().lower(): c for c in class_res.scalars().all()}

    row_index = 1  # 1-indexed, row 1 is header
    for raw_row in reader:
        row_index += 1
        row = {k.strip().lower(): (v.strip() if v else "") for k, v in raw_row.items() if k}

        full_name = row.get("full_name")
        class_name = row.get("class_name")
        roll_str = row.get("roll_number")
        guardian_name = row.get("guardian_name")
        guardian_phone = row.get("guardian_phone")

        if not full_name:
            errors.append(CSVImportRowError(row=row_index, message="Student full_name is required"))
            continue
        if not class_name:
            errors.append(CSVImportRowError(row=row_index, message="class_name is required"))
            continue
        if not roll_str:
            errors.append(CSVImportRowError(row=row_index, message="roll_number is required"))
            continue

        try:
            roll_number = int(roll_str)
            if roll_number <= 0:
                raise ValueError
        except ValueError:
            errors.append(CSVImportRowError(row=row_index, message=f"Invalid roll_number '{roll_str}', positive integer expected"))
            continue

        if not guardian_phone or not validate_e164(guardian_phone):
            errors.append(CSVImportRowError(row=row_index, message=f"Invalid Rwanda phone number '{guardian_phone}' (must be +2507XXXXXXXX)"))
            continue

        if not guardian_name:
            guardian_name = "Parent / Guardian"

        # Check / create class
        class_key = class_name.strip().lower()
        target_class = classes_by_name.get(class_key)
        if not target_class:
            # Parse grade from name e.g. "P5 A" -> grade 5
            grade = 1
            grade_match = re.search(r"\d+", class_name)
            if grade_match:
                grade = int(grade_match.group(0))

            target_class = Class(
                school_id=school_id,
                name=class_name.strip(),
                grade=grade,
                academic_year=2026,
            )
            db.add(target_class)
            await db.flush()
            classes_by_name[class_key] = target_class

        # Parse sex & birth year
        sex_str = row.get("sex", "").upper()
        sex = SexEnum.F if sex_str == "F" else (SexEnum.M if sex_str == "M" else None)
        birth_year = None
        birth_str = row.get("birth_year")
        if birth_str:
            try:
                birth_year = int(birth_str)
            except ValueError:
                pass

        student_code = row.get("student_code") or None

        # Find or create guardian
        guard_res = await db.execute(select(Guardian).where(Guardian.phone_e164 == guardian_phone))
        guardian = guard_res.scalar_one_or_none()
        if not guardian:
            guardian = Guardian(
                full_name=guardian_name,
                phone_e164=guardian_phone,
                language=LanguageEnum.rw,
            )
            db.add(guardian)
            await db.flush()

        # Check existing student in class with roll_number
        stud_res = await db.execute(
            select(Student).where(Student.class_id == target_class.id, Student.roll_number == roll_number)
        )
        existing_student = stud_res.scalar_one_or_none()

        if existing_student:
            existing_student.full_name = full_name
            if sex:
                existing_student.sex = sex
            if birth_year:
                existing_student.birth_year = birth_year
            if student_code:
                existing_student.student_code = student_code
            updated_count += 1
            student = existing_student
        else:
            student = Student(
                school_id=school_id,
                class_id=target_class.id,
                roll_number=roll_number,
                full_name=full_name,
                sex=sex,
                birth_year=birth_year,
                student_code=student_code,
                status=StudentStatusEnum.active,
            )
            db.add(student)
            await db.flush()
            created_count += 1

        # Link guardian
        link_res = await db.execute(
            select(student_guardians).where(
                student_guardians.c.student_id == student.id,
                student_guardians.c.guardian_id == guardian.id,
            )
        )
        if not link_res.first():
            rel = row.get("guardian_relationship") or "guardian"
            await db.execute(
                student_guardians.insert().values(
                    student_id=student.id,
                    guardian_id=guardian.id,
                    relationship=rel,
                    is_primary=True,
                )
            )

    if dry_run or errors:
        await db.rollback()
    else:
        await db.commit()

    return CSVImportResult(
        created=created_count if not dry_run and not errors else 0,
        updated=updated_count if not dry_run and not errors else 0,
        skipped=skipped_count,
        errors=errors,
    )
