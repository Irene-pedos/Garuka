import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import utc_now
from app.models.case import Case, CaseEvent, CaseStatusEnum
from app.models.user import RoleEnum, User

logger = logging.getLogger("garuka.case_service")


class CaseNotFoundError(Exception):
    pass


class CaseValidationError(Exception):
    pass


async def assign_case_mentor(
    db: AsyncSession,
    case_id: uuid.UUID,
    mentor_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> Case:
    """
    Assign or reassign a mentor to a case with an explicit transaction boundary.
    """
    try:
        case = await db.get(Case, case_id)
        if not case:
            raise CaseNotFoundError("Case not found")

        mentor = await db.get(User, mentor_id)
        if not mentor or mentor.role != RoleEnum.mentor or not mentor.is_active:
            raise CaseValidationError("Designated user is not an active mentor")

        case.mentor_id = mentor.id
        if case.status == CaseStatusEnum.open:
            case.status = CaseStatusEnum.mentor_assigned

        event = CaseEvent(
            case_id=case.id,
            type="mentor_reassigned",
            actor_user_id=actor_user_id,
            payload={"mentor_id": str(mentor.id), "mentor_name": mentor.full_name},
        )
        db.add(event)
        await db.commit()
        await db.refresh(case)
        return case

    except Exception:
        await db.rollback()
        raise


async def escalate_case(
    db: AsyncSession,
    case_id: uuid.UUID,
    to_level: int,
    note: str | None,
    actor_user_id: uuid.UUID,
) -> Case:
    """
    Escalate a case to a higher level (e.g. Level 3 sector escalation) with an explicit transaction boundary.
    """
    try:
        case = await db.get(Case, case_id)
        if not case:
            raise CaseNotFoundError("Case not found")

        case.level = to_level
        if to_level == 3:
            case.status = CaseStatusEnum.escalated_sector

        event = CaseEvent(
            case_id=case.id,
            type="escalated",
            actor_user_id=actor_user_id,
            payload={"to_level": to_level, "note": note or ""},
        )
        db.add(event)
        await db.commit()
        await db.refresh(case)
        return case

    except Exception:
        await db.rollback()
        raise


async def add_case_note(
    db: AsyncSession,
    case_id: uuid.UUID,
    text: str,
    actor_user_id: uuid.UUID,
) -> Case:
    """
    Add a case progress note with an explicit transaction boundary.
    """
    try:
        case = await db.get(Case, case_id)
        if not case:
            raise CaseNotFoundError("Case not found")

        event = CaseEvent(
            case_id=case.id,
            type="note_added",
            actor_user_id=actor_user_id,
            payload={"note": text},
        )
        db.add(event)
        await db.commit()
        await db.refresh(case)
        return case

    except Exception:
        await db.rollback()
        raise


async def resolve_case(
    db: AsyncSession,
    case_id: uuid.UUID,
    outcome: str,
    note: str | None,
    actor_user_id: uuid.UUID,
) -> Case:
    """
    Resolve a case with an explicit transaction boundary.
    """
    try:
        case = await db.get(Case, case_id)
        if not case:
            raise CaseNotFoundError("Case not found")

        try:
            new_status = CaseStatusEnum(outcome)
        except ValueError:
            raise CaseValidationError(f"Invalid resolution outcome: {outcome}")

        case.status = new_status
        case.resolved_at = utc_now()

        event = CaseEvent(
            case_id=case.id,
            type="resolved",
            actor_user_id=actor_user_id,
            payload={"outcome": outcome, "note": note or ""},
        )
        db.add(event)
        await db.commit()
        await db.refresh(case)
        return case

    except Exception:
        await db.rollback()
        raise
