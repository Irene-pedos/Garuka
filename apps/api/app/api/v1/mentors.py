import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.rbac import require_roles
from app.db.session import get_db
from app.models.case import Case, CaseStatusEnum, MentorVisit
from app.models.user import RoleEnum, User
from app.schemas.mentor import MentorRead

router = APIRouter(prefix="/mentors", tags=["mentors"])


@router.get("", response_model=list[MentorRead], operation_id="list_mentors")
async def list_mentors(
    sector_id: uuid.UUID | None = Query(None),
    current_user: User = Depends(
        require_roles(
            RoleEnum.admin,
            RoleEnum.district_director,
            RoleEnum.sector_officer,
            RoleEnum.head_teacher,
        )
    ),
    db: AsyncSession = Depends(get_db),
) -> list[MentorRead]:
    query = (
        select(User)
        .options(selectinload(User.sector))
        .where(User.role == RoleEnum.mentor)
        .order_by(User.full_name)
    )

    if current_user.role == RoleEnum.sector_officer:
        if current_user.sector_id:
            query = query.where(User.sector_id == current_user.sector_id)
    elif sector_id:
        query = query.where(User.sector_id == sector_id)

    result = await db.execute(query)
    mentors = result.scalars().all()

    now = datetime.now(UTC)
    thirty_days_ago = now - timedelta(days=30)

    # Active cases per mentor
    active_statuses = [
        CaseStatusEnum.open,
        CaseStatusEnum.mentor_assigned,
        CaseStatusEnum.escalated_sector,
    ]
    active_cases_query = (
        select(Case.mentor_id, func.count(Case.id))
        .where(Case.mentor_id.is_not(None), Case.status.in_(active_statuses))
        .group_by(Case.mentor_id)
    )
    active_cases_res = await db.execute(active_cases_query)
    active_cases_map = dict(active_cases_res.fetchall())

    # Visits in last 30d per mentor
    visits_query = (
        select(
            MentorVisit.mentor_id,
            func.count(MentorVisit.id).label("total_visits"),
            func.count().filter(MentorVisit.verified.is_(True)).label("verified_visits"),
        )
        .where(MentorVisit.started_at >= thirty_days_ago)
        .group_by(MentorVisit.mentor_id)
    )
    visits_res = await db.execute(visits_query)
    visits_map = {row[0]: (row[1], row[2]) for row in visits_res.fetchall()}

    items: list[MentorRead] = []
    for m in mentors:
        active_cnt = active_cases_map.get(m.id, 0)
        v_total, v_ver = visits_map.get(m.id, (0, 0))
        ver_rate = round((v_ver / v_total * 100), 1) if v_total > 0 else 0.0

        items.append(
            MentorRead(
                id=m.id,
                name=m.full_name,
                email=m.email,
                phone_e164=m.phone_e164,
                sector_id=m.sector_id,
                sector_name=m.sector.name if m.sector else None,
                active_cases=active_cnt,
                visits_30d=v_total,
                verified_rate=ver_rate,
                is_active=m.is_active,
            )
        )
    return items
