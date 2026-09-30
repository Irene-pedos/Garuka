import asyncio
from datetime import date

from sqlalchemy import select

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


async def seed():
    async with AsyncSessionLocal() as db:
        print("[*] Seeding Garuka database (minimal test set)...")

        # 1. District
        dist_res = await db.execute(select(District).where(District.name == "Huye"))
        district = dist_res.scalar_one_or_none()
        if not district:
            district = District(name="Huye")
            db.add(district)
            await db.flush()
            print("  Created District: Huye")

        # 2. Sector
        sec_res = await db.execute(
            select(Sector).where(Sector.district_id == district.id, Sector.name == "Tumba")
        )
        sector = sec_res.scalar_one_or_none()
        if not sector:
            sector = Sector(district_id=district.id, name="Tumba")
            db.add(sector)
            await db.flush()
            print("  Created Sector: Tumba")

        # 3. Only 1 School: GS Demo 1
        sch_res = await db.execute(
            select(School).where(School.sector_id == sector.id, School.name == "GS Demo 1")
        )
        school = sch_res.scalar_one_or_none()
        if not school:
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

        # 4. Users: Exactly 1 user per role
        default_pwd = get_password_hash("ChangeMe123!")
        default_pin = get_pin_hash("4821")

        users_data = [
            # 1 Admin
            (
                "Admin User",
                "admin@garuka.rw",
                None,
                RoleEnum.admin,
                default_pwd,
                None,
                None,
                None,
                None,
            ),
            # 1 District Director
            (
                "District Director",
                "director@huye.gov.rw",
                None,
                RoleEnum.district_director,
                default_pwd,
                None,
                None,
                None,
                district.id,
            ),
            # 1 Sector Officer
            (
                "Sector Officer",
                "seo@tumba.gov.rw",
                None,
                RoleEnum.sector_officer,
                default_pwd,
                None,
                None,
                sector.id,
                None,
            ),
            # 1 Head Teacher
            (
                "Head Teacher",
                "head@gsdemo1.rw",
                "+250788100001",
                RoleEnum.head_teacher,
                default_pwd,
                default_pin,
                school.id,
                None,
                None,
            ),
            # 1 Teacher
            (
                "Teacher Uwimana",
                "teacher1@gsdemo1.rw",
                "+250736200001",
                RoleEnum.teacher,
                default_pwd,
                default_pin,
                school.id,
                None,
                None,
            ),
            # 1 Mentor
            (
                "Mentor Keza",
                None,
                "+250736300001",
                RoleEnum.mentor,
                None,
                default_pin,
                None,
                sector.id,
                None,
            ),
        ]

        seeded_users = {}
        for name, email, phone, role, pwd, pin, sch_id, sec_id, dist_id in users_data:
            existing = None
            if email:
                res = await db.execute(select(User).where(User.email == email))
                existing = res.scalar_one_or_none()
            elif phone:
                res = await db.execute(select(User).where(User.phone_e164 == phone))
                existing = res.scalar_one_or_none()

            if not existing:
                u = User(
                    full_name=name,
                    email=email,
                    phone_e164=phone,
                    role=role,
                    password_hash=pwd,
                    pin_hash=pin,
                    language=LanguageEnum.rw,
                    school_id=sch_id,
                    sector_id=sec_id,
                    district_id=dist_id,
                    is_active=True,
                )
                db.add(u)
                await db.flush()
                seeded_users[role] = u
                print(f"  Created User ({role.value}): {name}")
            else:
                seeded_users[role] = existing

        teacher = seeded_users[RoleEnum.teacher]

        # 5. Only 1 Class: P5 A
        c_res = await db.execute(
            select(Class).where(
                Class.school_id == school.id,
                Class.name == "P5 A",
                Class.academic_year == 2026,
            )
        )
        class_p5a = c_res.scalar_one_or_none()
        if not class_p5a:
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
            print("  Created Class: P5 A")

        # 6. Exactly 5 Students & 5 Guardians
        students_data = [
            ("Uwase Jeanne", 1, SexEnum.F, "Uwimana Claudine", "+250788401001", "mother"),
            ("Kamana Eric", 2, SexEnum.M, "Habimana Jean", "+250736401002", "father"),
            ("Mugabo Fabrice", 3, SexEnum.M, "Mukamana Dancille", "+250788401003", "mother"),
            ("Keza Aline", 4, SexEnum.F, "Nshimiyimana Eric", "+250736401004", "father"),
            ("Habimana Patrick", 5, SexEnum.M, "Umubyeyi Berthe", "+250788401005", "mother"),
        ]

        for s_name, roll, sex, g_name, g_phone, rel in students_data:
            g_res = await db.execute(select(Guardian).where(Guardian.phone_e164 == g_phone))
            guardian = g_res.scalar_one_or_none()
            if not guardian:
                guardian = Guardian(
                    full_name=g_name,
                    phone_e164=g_phone,
                    language=LanguageEnum.rw,
                    consent_source=ConsentSourceEnum.school_form,
                    sms_opt_out=False,
                )
                db.add(guardian)
                await db.flush()

            st_res = await db.execute(
                select(Student).where(
                    Student.class_id == class_p5a.id, Student.roll_number == roll
                )
            )
            student = st_res.scalar_one_or_none()
            if not student:
                student = Student(
                    school_id=school.id,
                    class_id=class_p5a.id,
                    roll_number=roll,
                    full_name=s_name,
                    student_code=f"SDMS-2026{roll:03d}",
                    sex=sex,
                    birth_year=2014,
                    status=StudentStatusEnum.active,
                    enrolled_at=date(2026, 1, 5),
                )
                db.add(student)
                await db.flush()

                await db.execute(
                    student_guardians.insert().values(
                        student_id=student.id,
                        guardian_id=guardian.id,
                        relationship=rel,
                        is_primary=True,
                    )
                )

        print("  Created 5 students and 5 linked guardians in P5 A")

        # 7. Terms & Holidays
        t_res = await db.execute(select(Term).where(Term.academic_year == 2026, Term.term_no == 1))
        if not t_res.scalar_one_or_none():
            t1 = Term(academic_year=2026, term_no=1, start_date=date(2026, 1, 5), end_date=date(2026, 4, 3))
            t2 = Term(academic_year=2026, term_no=2, start_date=date(2026, 4, 20), end_date=date(2026, 7, 10))
            t3 = Term(academic_year=2026, term_no=3, start_date=date(2026, 8, 3), end_date=date(2026, 11, 6))
            db.add_all([t1, t2, t3])

        h_res = await db.execute(select(Holiday).where(Holiday.date == date(2026, 2, 1)))
        if not h_res.scalar_one_or_none():
            h1 = Holiday(date=date(2026, 2, 1), name="National Heroes Day")
            h2 = Holiday(date=date(2026, 4, 7), name="Genocide Memorial Day")
            h3 = Holiday(date=date(2026, 7, 1), name="Independence Day")
            h4 = Holiday(date=date(2026, 7, 4), name="Liberation Day")
            db.add_all([h1, h2, h3, h4])

        await db.commit()
        print("[OK] Seeding completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
