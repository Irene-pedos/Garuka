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
        print("[*] Seeding Garuka database...")

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

        # 3. Schools
        schools = {}
        for sname, scode in [("GS Demo 1", "GSD1"), ("GS Demo 2", "GSD2")]:
            sch_res = await db.execute(
                select(School).where(School.sector_id == sector.id, School.name == sname)
            )
            sch = sch_res.scalar_one_or_none()
            if not sch:
                sch = School(
                    sector_id=sector.id,
                    name=sname,
                    code=scode,
                    level=SchoolLevelEnum.both,
                    is_active=True,
                )
                db.add(sch)
                await db.flush()
                print(f"  Created School: {sname}")
            schools[sname] = sch

        school1 = schools["GS Demo 1"]

        # 4. Users
        default_pwd = get_password_hash("ChangeMe123!")
        default_pin = get_pin_hash("4821")

        users_data = [
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
            (
                "Head Teacher",
                "head@gsdemo1.rw",
                "+250780000000",
                RoleEnum.head_teacher,
                default_pwd,
                default_pin,
                school1.id,
                None,
                None,
            ),
            (
                "Teacher Uwimana",
                "teacher1@gsdemo1.rw",
                "+250780000001",
                RoleEnum.teacher,
                default_pwd,
                default_pin,
                school1.id,
                None,
                None,
            ),
            (
                "Teacher Mugisha",
                "teacher2@gsdemo1.rw",
                "+250780000002",
                RoleEnum.teacher,
                default_pwd,
                default_pin,
                school1.id,
                None,
                None,
            ),
            (
                "Mentor Keza",
                None,
                "+250780000011",
                RoleEnum.mentor,
                None,
                default_pin,
                None,
                sector.id,
                None,
            ),
            (
                "Mentor Gasana",
                None,
                "+250780000012",
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
                seeded_users[name] = u
                print(f"  Created User: {name} ({role.value})")
            else:
                seeded_users[name] = existing

        # 5. Classes for GS Demo 1
        t1 = seeded_users.get("Teacher Uwimana")
        t2 = seeded_users.get("Teacher Mugisha")

        classes = {}
        for cname, grade, teacher in [("P5 A", 5, t1), ("P6 A", 6, t2)]:
            c_res = await db.execute(
                select(Class).where(
                    Class.school_id == school1.id,
                    Class.name == cname,
                    Class.academic_year == 2026,
                )
            )
            c = c_res.scalar_one_or_none()
            if not c:
                c = Class(
                    school_id=school1.id,
                    name=cname,
                    grade=grade,
                    academic_year=2026,
                    class_teacher_id=teacher.id if teacher else None,
                )
                db.add(c)
                await db.flush()
                # Link class_teachers
                if teacher:
                    await db.execute(
                        class_teachers.insert().values(class_id=c.id, user_id=teacher.id)
                    )
                print(f"  Created Class: {cname}")
            classes[cname] = c

        class_p5a = classes["P5 A"]

        # 6. Students & Guardians (30 students)
        guardians = []
        for i in range(1, 21):
            g_phone = f"+25078000{100 + i:04d}"
            g_res = await db.execute(select(Guardian).where(Guardian.phone_e164 == g_phone))
            g = g_res.scalar_one_or_none()
            if not g:
                g = Guardian(
                    full_name=f"Parent {i}",
                    phone_e164=g_phone,
                    language=LanguageEnum.rw,
                    consent_source=ConsentSourceEnum.school_form,
                    sms_opt_out=False,
                )
                db.add(g)
                await db.flush()
            guardians.append(g)

        first_names = [
            "Uwase",
            "Kamana",
            "Mugabo",
            "Keza",
            "Habimana",
            "Tuyishime",
            "Kagabo",
            "Ineza",
            "Hirwa",
            "Manzi",
        ]
        last_names = [
            "Jeanne",
            "Eric",
            "Fabrice",
            "Aline",
            "Patrick",
            "Grace",
            "David",
            "Chantal",
            "Jean",
            "Marie",
        ]

        for roll in range(1, 31):
            s_res = await db.execute(
                select(Student).where(Student.class_id == class_p5a.id, Student.roll_number == roll)
            )
            s = s_res.scalar_one_or_none()
            if not s:
                fname = f"{first_names[(roll - 1) % len(first_names)]} {last_names[(roll - 1) % len(last_names)]}"
                s = Student(
                    school_id=school1.id,
                    class_id=class_p5a.id,
                    roll_number=roll,
                    full_name=fname,
                    student_code=f"SDMS-{2026000 + roll}",
                    sex=SexEnum.F if roll % 2 == 0 else SexEnum.M,
                    birth_year=2014,
                    status=StudentStatusEnum.active,
                    enrolled_at=date(2026, 1, 5),
                )
                db.add(s)
                await db.flush()

                # Assign guardian (guardians 1..10 share 2 kids)
                g_idx = (roll - 1) % len(guardians)
                assigned_guardian = guardians[g_idx]
                await db.execute(
                    student_guardians.insert().values(
                        student_id=s.id,
                        guardian_id=assigned_guardian.id,
                        relationship="mother" if roll % 2 == 0 else "father",
                        is_primary=True,
                    )
                )

        print("  Created 30 students and linked guardians in P5 A")

        # 7. Terms & Holidays
        t_res = await db.execute(select(Term).where(Term.academic_year == 2026, Term.term_no == 1))
        if not t_res.scalar_one_or_none():
            t1 = Term(
                academic_year=2026,
                term_no=1,
                start_date=date(2026, 1, 5),
                end_date=date(2026, 4, 3),
            )
            t2 = Term(
                academic_year=2026,
                term_no=2,
                start_date=date(2026, 4, 20),
                end_date=date(2026, 7, 10),
            )
            t3 = Term(
                academic_year=2026,
                term_no=3,
                start_date=date(2026, 8, 3),
                end_date=date(2026, 11, 6),
            )
            db.add_all([t1, t2, t3])
            print("  Created 2026 Terms (T1, T2, T3)")

        h_res = await db.execute(select(Holiday).where(Holiday.date == date(2026, 2, 1)))
        if not h_res.scalar_one_or_none():
            h1 = Holiday(date=date(2026, 2, 1), name="National Heroes Day")
            h2 = Holiday(date=date(2026, 4, 7), name="Genocide Memorial Day")
            h3 = Holiday(date=date(2026, 7, 1), name="Independence Day")
            h4 = Holiday(date=date(2026, 7, 4), name="Liberation Day")
            db.add_all([h1, h2, h3, h4])
            print("  Created Holidays")

        await db.commit()
        print("[OK] Seeding completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
