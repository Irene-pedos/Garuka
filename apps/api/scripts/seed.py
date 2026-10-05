import asyncio
from datetime import date

from sqlalchemy import select, text

from app.core.security import get_password_hash, get_pin_hash
from app.db.session import AsyncSessionLocal
from app.models.calendar import Holiday, Term
from app.models.geo import District, School, SchoolLevelEnum, Sector
from app.models.student import (
    Class,
    ConsentSourceEnum,
    Guardian,
    SexEnum,
    Student,
    StudentStatusEnum,
    class_teachers,
    student_guardians,
)
from app.models.user import LanguageEnum, RoleEnum, User


async def reset_and_seed():
    async with AsyncSessionLocal() as db:
        print("[*] Resetting and cleaning Garuka database...")

        # 0. Truncate all tables cleanly with CASCADE
        tables_to_truncate = [
            "ussd_requests",
            "ussd_sessions",
            "sms_outbox",
            "audit_logs",
            "help_requests",
            "mentor_visits",
            "visit_codes",
            "case_events",
            "cases",
            "absences",
            "attendance_submissions",
            "student_guardians",
            "students",
            "class_teachers",
            "classes",
            "users",
            "guardians",
            "schools",
            "sectors",
            "districts",
            "holidays",
            "terms",
            "app_settings",
        ]
        await db.execute(text(f"TRUNCATE TABLE {', '.join(tables_to_truncate)} RESTART IDENTITY CASCADE;"))
        await db.commit()
        print("[*] All tables cleared successfully.")

        print("[*] Inserting minimal, clean test dataset...")

        # 1. District
        district = District(name="Huye")
        db.add(district)
        await db.flush()
        print("  Created District: Huye")

        # 2. Sector
        sector = Sector(district_id=district.id, name="Tumba")
        db.add(sector)
        await db.flush()
        print("  Created Sector: Tumba")

        # 3. Exactly 1 School: GS Demo 1
        school = School(
            sector_id=sector.id,
            name="GS Demo 1",
            code="GSD1",
            level=SchoolLevelEnum.both,
            is_active=True,
        )
        db.add(school)
        await db.flush()
        print("  Created School: GS Demo 1")

        # 4. Users: 1 Admin, 1 Sector Officer, 1 Head Teacher, 1 Teacher, 1 Mentor
        default_pwd = get_password_hash("ChangeMe123!")
        default_pin = get_pin_hash("4821")

        # Admin
        admin = User(
            full_name="Admin User",
            email="admin@garuka.rw",
            phone_e164=None,
            role=RoleEnum.admin,
            password_hash=default_pwd,
            pin_hash=None,
            language=LanguageEnum.en,
            is_active=True,
        )
        db.add(admin)

        # Sector Officer
        seo = User(
            full_name="Sector Officer",
            email="seo@tumba.gov.rw",
            phone_e164=None,
            role=RoleEnum.sector_officer,
            password_hash=default_pwd,
            pin_hash=None,
            language=LanguageEnum.rw,
            sector_id=sector.id,
            is_active=True,
        )
        db.add(seo)

        # Head Teacher
        head_teacher = User(
            full_name="Head Teacher",
            email="head@gsdemo1.rw",
            phone_e164="+250788100001",
            role=RoleEnum.head_teacher,
            password_hash=default_pwd,
            pin_hash=default_pin,
            language=LanguageEnum.rw,
            school_id=school.id,
            is_active=True,
        )
        db.add(head_teacher)

        # Teacher
        teacher = User(
            full_name="Teacher Uwimana",
            email="teacher1@gsdemo1.rw",
            phone_e164="+250736200001",
            role=RoleEnum.teacher,
            password_hash=default_pwd,
            pin_hash=default_pin,
            language=LanguageEnum.rw,
            school_id=school.id,
            is_active=True,
        )
        db.add(teacher)

        # Mentor
        mentor = User(
            full_name="Mentor Keza",
            email=None,
            phone_e164="+250736300001",
            role=RoleEnum.mentor,
            password_hash=None,
            pin_hash=default_pin,
            language=LanguageEnum.rw,
            sector_id=sector.id,
            is_active=True,
        )
        db.add(mentor)
        await db.flush()
        print("  Created 5 Users: Admin, Sector Officer, Head Teacher, Teacher, Mentor")

        # 5. Exactly 1 Class: P5 A
        class_p5a = Class(
            school_id=school.id,
            name="P5 A",
            grade=5,
            academic_year=2026,
            class_teacher_id=teacher.id,
        )
        db.add(class_p5a)
        await db.flush()

        await db.execute(
            class_teachers.insert().values(class_id=class_p5a.id, user_id=teacher.id)
        )
        print("  Created 1 Class: P5 A (assigned to Teacher Uwimana)")

        # 6. Exactly 2 Guardians & 2 Students in P5 A
        # Guardian 1 & Student 1
        g1 = Guardian(
            full_name="Uwimana Claudine",
            phone_e164="+250788401001",
            language=LanguageEnum.rw,
            consent_source=ConsentSourceEnum.school_form,
            sms_opt_out=False,
        )
        # Guardian 2 & Student 2
        g2 = Guardian(
            full_name="Habimana Jean",
            phone_e164="+250736401002",
            language=LanguageEnum.rw,
            consent_source=ConsentSourceEnum.school_form,
            sms_opt_out=False,
        )
        db.add_all([g1, g2])
        await db.flush()

        s1 = Student(
            school_id=school.id,
            class_id=class_p5a.id,
            roll_number=1,
            full_name="Uwase Jeanne",
            student_code="SDMS-2026001",
            sex=SexEnum.F,
            birth_year=2014,
            status=StudentStatusEnum.active,
            enrolled_at=date(2026, 1, 5),
        )
        s2 = Student(
            school_id=school.id,
            class_id=class_p5a.id,
            roll_number=2,
            full_name="Kamana Eric",
            student_code="SDMS-2026002",
            sex=SexEnum.M,
            birth_year=2014,
            status=StudentStatusEnum.active,
            enrolled_at=date(2026, 1, 5),
        )
        db.add_all([s1, s2])
        await db.flush()

        # Link students to guardians
        await db.execute(
            student_guardians.insert().values([
                {
                    "student_id": s1.id,
                    "guardian_id": g1.id,
                    "relationship": "mother",
                    "is_primary": True,
                },
                {
                    "student_id": s2.id,
                    "guardian_id": g2.id,
                    "relationship": "father",
                    "is_primary": True,
                },
            ])
        )
        print("  Created 2 Guardians and 2 Students (Uwase Jeanne, Kamana Eric) in P5 A")

        # 7. Terms & Holidays (2026 calendar for attendance calculations)
        t1 = Term(academic_year=2026, term_no=1, start_date=date(2026, 1, 5), end_date=date(2026, 4, 3))
        t2 = Term(academic_year=2026, term_no=2, start_date=date(2026, 4, 20), end_date=date(2026, 7, 10))
        t3 = Term(academic_year=2026, term_no=3, start_date=date(2026, 8, 3), end_date=date(2026, 11, 6))
        db.add_all([t1, t2, t3])

        h1 = Holiday(date=date(2026, 2, 1), name="National Heroes Day")
        h2 = Holiday(date=date(2026, 4, 7), name="Genocide Memorial Day")
        h3 = Holiday(date=date(2026, 7, 1), name="Independence Day")
        h4 = Holiday(date=date(2026, 7, 4), name="Liberation Day")
        db.add_all([h1, h2, h3, h4])

        await db.commit()
        print("[OK] Database successfully reset and seeded!")


if __name__ == "__main__":
    asyncio.run(reset_and_seed())
