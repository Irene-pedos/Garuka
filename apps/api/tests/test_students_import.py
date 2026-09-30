import io

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

    csv_data = (
        "student_code,full_name,sex,birth_year,class_name,roll_number,guardian_name,guardian_phone,guardian_relationship\n"
        "SDMS-9901,Test Student One,F,2014,P5 B,1,Mama Test,+250789999001,mother\n"
        "SDMS-9902,Test Student Two,M,2013,P5 B,2,Papa Test,+250789999002,father\n"
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
    assert dry_data["created"] == 0  # not committed

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
    )

    files = {"file": ("students.csv", io.BytesIO(invalid_csv.encode("utf-8")), "text/csv")}
    res = await async_client.post(
        f"/api/v1/students/import?school_id={school_id}&dry_run=true",
        files=files,
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["errors"]) > 0
    assert any("full_name" in e["message"] for e in data["errors"])
