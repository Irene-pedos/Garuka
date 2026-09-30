import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import get_current_user, require_roles
from app.db.session import get_db
from app.models.geo import District, School, Sector
from app.models.user import RoleEnum, User
from app.schemas.geo import (
    DistrictCreate,
    DistrictResponse,
    SchoolCreate,
    SchoolResponse,
    SchoolUpdate,
    SectorCreate,
    SectorResponse,
)

router = APIRouter(tags=["geography"])


# --- Districts ---

@router.get("/districts", response_model=list[DistrictResponse], operation_id="list_districts")
async def list_districts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(District).order_by(District.name)
    if current_user.role == RoleEnum.district_director and current_user.district_id:
        query = query.where(District.id == current_user.district_id)
    elif current_user.role == RoleEnum.sector_officer and current_user.sector_id:
        # Sector officer can see district containing their sector
        subq = select(Sector.district_id).where(Sector.id == current_user.sector_id)
        query = query.where(District.id.in_(subq))
    result = await db.execute(query)
    return result.scalars().all()


@router.post(
    "/districts",
    response_model=DistrictResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_district",
)
async def create_district(
    req: DistrictCreate,
    current_user: User = Depends(require_roles(RoleEnum.admin)),
    db: AsyncSession = Depends(get_db),
):
    district = District(name=req.name.strip())
    db.add(district)
    await db.commit()
    await db.refresh(district)
    return district


# --- Sectors ---

@router.get("/sectors", response_model=list[SectorResponse], operation_id="list_sectors")
async def list_sectors(
    district_id: uuid.UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Sector).order_by(Sector.name)
    if current_user.role == RoleEnum.district_director and current_user.district_id:
        query = query.where(Sector.district_id == current_user.district_id)
    elif current_user.role == RoleEnum.sector_officer and current_user.sector_id:
        query = query.where(Sector.id == current_user.sector_id)
    elif district_id:
        query = query.where(Sector.district_id == district_id)

    result = await db.execute(query)
    return result.scalars().all()


@router.post(
    "/sectors",
    response_model=SectorResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_sector",
)
async def create_sector(
    req: SectorCreate,
    current_user: User = Depends(require_roles(RoleEnum.admin)),
    db: AsyncSession = Depends(get_db),
):
    sector = Sector(district_id=req.district_id, name=req.name.strip())
    db.add(sector)
    await db.commit()
    await db.refresh(sector)
    return sector


# --- Schools ---

@router.get("/schools", response_model=list[SchoolResponse], operation_id="list_schools")
async def list_schools(
    sector_id: uuid.UUID | None = Query(None),
    q: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(School).order_by(School.name)

    # Scoping
    if current_user.role == RoleEnum.head_teacher and current_user.school_id:
        query = query.where(School.id == current_user.school_id)
    elif current_user.role == RoleEnum.sector_officer and current_user.sector_id:
        query = query.where(School.sector_id == current_user.sector_id)
    elif current_user.role == RoleEnum.district_director and current_user.district_id:
        sectors_in_district = select(Sector.id).where(Sector.district_id == current_user.district_id)
        query = query.where(School.sector_id.in_(sectors_in_district))
    elif sector_id:
        query = query.where(School.sector_id == sector_id)

    if q:
        query = query.where(School.name.ilike(f"%{q.strip()}%"))

    result = await db.execute(query)
    return result.scalars().all()


@router.post(
    "/schools",
    response_model=SchoolResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_school",
)
async def create_school(
    req: SchoolCreate,
    current_user: User = Depends(require_roles(RoleEnum.admin)),
    db: AsyncSession = Depends(get_db),
):
    school = School(
        sector_id=req.sector_id,
        name=req.name.strip(),
        code=req.code.strip() if req.code else None,
        level=req.level,
        is_active=True,
    )
    db.add(school)
    await db.commit()
    await db.refresh(school)
    return school


@router.patch("/schools/{id}", response_model=SchoolResponse, operation_id="update_school")
async def update_school(
    id: uuid.UUID,
    req: SchoolUpdate,
    current_user: User = Depends(require_roles(RoleEnum.admin)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(School).where(School.id == id))
    school = result.scalar_one_or_none()
    if not school:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="School not found")

    if req.name is not None:
        school.name = req.name.strip()
    if req.code is not None:
        school.code = req.code.strip() if req.code else None
    if req.level is not None:
        school.level = req.level
    if req.is_active is not None:
        school.is_active = req.is_active

    await db.commit()
    await db.refresh(school)
    return school
