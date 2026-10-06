import io
import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_csv_import_dry_run_and_commit(async_client: AsyncClient):
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "head@gsdemo1.rw", "password": "ChangeMe123!"},
    )
    token = login_res.json()["access_token"]
    school_id = login_res.json()["user"]["school_id"]
    headers = {"Authorization": f"Bearer {token}"}

    rand_suffix = uuid.uuid4().hex[:4].upper()
    c_name = f"P5 {rand_suffix}"
    code1 = f"SDMS-{uuid.uuid4().hex[:6]}"
    code2 = f"SDMS-{uuid.uuid4().hex[:6]}"
    phone1 = f"+25078{uuid.uuid4().int % 10000000:07d}"
    phone2 = f"+25078{(uuid.uuid4().int + 1) % 10000000:07d}"

    csv_data = (
        "student_code,full_name,sex,birth_year,class_name,roll_number,guardian_name,guardian_phone,guardian_relationship\n"
        f"{code1},Test Student One,F,2014,{c_name},1,Mama Test,{phone1},mother\n"
        f"{code2},Test Student Two,M,2013,{c_name},2,Papa Test,{phone2},father\n"
    )

    # 1. Dry run
    files = {"file": ("students.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    dry_run_res = await async_client.post(
        f"/api/v1/students/import?school_id={school_id}&dry_run=true",
        files=files,
        headers=headers,
    )
    assert dry_run_res.status_code == 200
    dry_data = dry_run_res.json()
    assert dry_data["errors"] == []
    assert dry_data["created"] == 2  # dry run returns would-create count

    # 2. Actual import
    files = {"file": ("students.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    import_res = await async_client.post(
        f"/api/v1/students/import?school_id={school_id}&dry_run=false",
        files=files,
        headers=headers,
    )
    assert import_res.status_code == 200
    data = import_res.json()
    assert data["errors"] == []
    assert data["created"] == 2


@pytest.mark.asyncio
async def test_csv_import_validation_errors(async_client: AsyncClient):
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "head@gsdemo1.rw", "password": "ChangeMe123!"},
    )
    token = login_res.json()["access_token"]
    school_id = login_res.json()["user"]["school_id"]
    headers = {"Authorization": f"Bearer {token}"}

    invalid_csv = (
        "student_code,full_name,sex,birth_year,class_name,roll_number,guardian_name,guardian_phone,guardian_relationship\n"
        ",,F,2014,P5 B,-5,Mama Test,not-a-phone,mother\n"
        "SDMS-BAD1,Student Invalid Birth,F,not-a-year,P5 B,1,Mama Test,+250780000001,mother\n"
        "SDMS-BAD2,Student Invalid Sex,X,2014,P5 B,2,Mama Test,+250780000002,mother\n"
    )

    files = {"file": ("students.csv", io.BytesIO(invalid_csv.encode("utf-8")), "text/csv")}
    res = await async_client.post(
        f"/api/v1/students/import?school_id={school_id}&dry_run=true",
        files=files,
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["errors"]) >= 3
    assert any("full_name" in e["message"] for e in data["errors"])
    assert any("birth_year" in e["message"] for e in data["errors"])
    assert any("sex" in e["message"] for e in data["errors"])


@pytest.mark.asyncio
async def test_csv_import_sets_dynamic_academic_year(async_client: AsyncClient, db_session):
    from sqlalchemy import select
    from app.models.student import Class
    from app.services.ussd.calendar_helper import get_kigali_today

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "head@gsdemo1.rw", "password": "ChangeMe123!"},
    )
    token = login_res.json()["access_token"]
    school_id = login_res.json()["user"]["school_id"]
    headers = {"Authorization": f"Bearer {token}"}

    rand_suffix = uuid.uuid4().hex[:5].upper()
    c_name = f"P6 {rand_suffix}"
    code = f"SDMS-{uuid.uuid4().hex[:6]}"
    phone = f"+25078{uuid.uuid4().int % 10000000:07d}"

    csv_data = (
        "student_code,full_name,sex,birth_year,class_name,roll_number,guardian_name,guardian_phone,guardian_relationship\n"
        f"{code},Year Test Student,M,2014,{c_name},1,Parent Year,{phone},father\n"
    )

    files = {"file": ("students.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    res = await async_client.post(
        f"/api/v1/students/import?school_id={school_id}&dry_run=false",
        files=files,
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["created"] == 1

    # Verify Class academic_year matches current Kigali year
    cls_res = await db_session.execute(
        select(Class).where(Class.name == c_name)
    )
    created_cls = cls_res.scalar_one()
    current_year = get_kigali_today().year
    assert created_cls.academic_year == current_year


@pytest.mark.asyncio
async def test_csv_import_captures_guardian_consent(async_client: AsyncClient, db_session):
    from sqlalchemy import select
    from app.models.student import ConsentSourceEnum, Guardian

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "head@gsdemo1.rw", "password": "ChangeMe123!"},
    )
    token = login_res.json()["access_token"]
    school_id = login_res.json()["user"]["school_id"]
    headers = {"Authorization": f"Bearer {token}"}

    phone_yes = f"+25078{uuid.uuid4().int % 10000000:07d}"
    phone_no = f"+25078{(uuid.uuid4().int + 1) % 10000000:07d}"
    code1 = f"SDMS-{uuid.uuid4().hex[:6]}"
    code2 = f"SDMS-{uuid.uuid4().hex[:6]}"
    c_name = f"P5 {uuid.uuid4().hex[:4].upper()}"

    csv_data = (
        "student_code,full_name,sex,birth_year,class_name,roll_number,guardian_name,guardian_phone,guardian_relationship,consent\n"
        f"{code1},Consented Student,F,2014,{c_name},1,Consented Parent,{phone_yes},mother,yes\n"
        f"{code2},Unconsented Student,M,2014,{c_name},2,Unconsented Parent,{phone_no},father,false\n"
    )

    files = {"file": ("students.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    res = await async_client.post(
        f"/api/v1/students/import?school_id={school_id}&dry_run=false",
        files=files,
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["created"] == 2

    # Verify consented guardian has consent recorded
    g1_res = await db_session.execute(select(Guardian).where(Guardian.phone_e164 == phone_yes))
    g1 = g1_res.scalar_one()
    assert g1.consent_at is not None
    assert g1.consent_source == ConsentSourceEnum.school_form

    # Verify unconsented guardian has consent_at None
    g2_res = await db_session.execute(select(Guardian).where(Guardian.phone_e164 == phone_no))
    g2 = g2_res.scalar_one()
    assert g2.consent_at is None

