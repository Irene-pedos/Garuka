import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rbac import require_roles
from app.db.session import get_db
from app.models.base import utc_now
from app.models.messaging import AppSetting, AuditLog, SmsOutbox, SmsStatusEnum
from app.models.user import RoleEnum, User
from app.schemas.admin import (
    AppSettingsRead,
    AppSettingsUpdate,
    AuditLogListItem,
    SmsOutboxListItem,
)

router = APIRouter(tags=["admin"])


# ---------------------------------------------------------------------------
# Settings & Thresholds Endpoints
# ---------------------------------------------------------------------------


@router.get("/settings", response_model=AppSettingsRead, operation_id="get_app_settings")
async def get_app_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.admin)),
):
    # Fetch from app_settings table or fallback to environment settings
    res = await db.execute(select(AppSetting).where(AppSetting.key == "rules_thresholds"))
    db_setting = res.scalar_one_or_none()

    vals = db_setting.value if db_setting and isinstance(db_setting.value, dict) else {}

    return AppSettingsRead(
        rule_consecutive_days=vals.get("rule_consecutive_days", settings.RULE_CONSECUTIVE_DAYS),
        rule_monthly_absences=vals.get("rule_monthly_absences", settings.RULE_MONTHLY_ABSENCES),
        rule_escalate_term_absences=vals.get(
            "rule_escalate_term_absences", settings.RULE_ESCALATE_TERM_ABSENCES
        ),
        rule_visit_sla_school_days=vals.get(
            "rule_visit_sla_school_days", settings.RULE_VISIT_SLA_SCHOOL_DAYS
        ),
        rule_return_streak_school_days=vals.get(
            "rule_return_streak_school_days", settings.RULE_RETURN_STREAK_SCHOOL_DAYS
        ),
        rule_district_escalation_days=vals.get(
            "rule_district_escalation_days", settings.RULE_DISTRICT_ESCALATION_DAYS
        ),
        mentor_max_active_cases=vals.get(
            "mentor_max_active_cases", settings.MENTOR_MAX_ACTIVE_CASES
        ),
        sms_quiet_hours_start=vals.get("sms_quiet_hours_start", settings.SMS_QUIET_HOURS_START),
        sms_quiet_hours_end=vals.get("sms_quiet_hours_end", settings.SMS_QUIET_HOURS_END),
        updated_at=db_setting.updated_at if db_setting else None,
    )


@router.patch("/settings", response_model=AppSettingsRead, operation_id="update_app_settings")
async def update_app_settings(
    payload: AppSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.admin)),
):
    res = await db.execute(select(AppSetting).where(AppSetting.key == "rules_thresholds"))
    db_setting = res.scalar_one_or_none()

    current_vals = db_setting.value if db_setting and isinstance(db_setting.value, dict) else {}
    update_data = payload.model_dump(exclude_unset=True)

    for k, v in update_data.items():
        if v is not None:
            current_vals[k] = v

    now = utc_now()
    if not db_setting:
        db_setting = AppSetting(
            key="rules_thresholds",
            value=current_vals,
            updated_by=current_user.id,
            updated_at=now,
        )
        db.add(db_setting)
    else:
        db_setting.value = current_vals
        db_setting.updated_by = current_user.id
        db_setting.updated_at = now

    # Also sync in-memory config thresholds for current process
    if "rule_consecutive_days" in current_vals:
        settings.RULE_CONSECUTIVE_DAYS = current_vals["rule_consecutive_days"]
    if "rule_monthly_absences" in current_vals:
        settings.RULE_MONTHLY_ABSENCES = current_vals["rule_monthly_absences"]
    if "rule_escalate_term_absences" in current_vals:
        settings.RULE_ESCALATE_TERM_ABSENCES = current_vals["rule_escalate_term_absences"]
    if "rule_visit_sla_school_days" in current_vals:
        settings.RULE_VISIT_SLA_SCHOOL_DAYS = current_vals["rule_visit_sla_school_days"]
    if "rule_return_streak_school_days" in current_vals:
        settings.RULE_RETURN_STREAK_SCHOOL_DAYS = current_vals["rule_return_streak_school_days"]
    if "rule_district_escalation_days" in current_vals:
        settings.RULE_DISTRICT_ESCALATION_DAYS = current_vals["rule_district_escalation_days"]
    if "mentor_max_active_cases" in current_vals:
        settings.MENTOR_MAX_ACTIVE_CASES = current_vals["mentor_max_active_cases"]

    # Log audit event
    audit = AuditLog(
        actor_user_id=current_user.id,
        actor_role=current_user.role.value,
        action="update_settings",
        entity_type="app_settings",
        entity_id="rules_thresholds",
        meta=update_data,
        created_at=now,
    )
    db.add(audit)
    await db.commit()
    await db.refresh(db_setting)

    return await get_app_settings(db, current_user)


# ---------------------------------------------------------------------------
# SMS Outbox Management
# ---------------------------------------------------------------------------


@router.get("/sms/outbox", response_model=list[SmsOutboxListItem], operation_id="list_sms_outbox")
async def list_sms_outbox(
    status_filter: SmsStatusEnum | None = Query(None, alias="status"),
    template_key: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.admin)),
):
    q = select(SmsOutbox).order_by(desc(SmsOutbox.scheduled_at)).limit(limit)
    if status_filter:
        q = q.where(SmsOutbox.status == status_filter)
    if template_key:
        q = q.where(SmsOutbox.template_key == template_key)

    res = await db.execute(q)
    return res.scalars().all()


@router.post("/sms/outbox/{id}/retry", response_model=SmsOutboxListItem, operation_id="retry_sms_outbox")
async def retry_sms_outbox(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.admin)),
):
    res = await db.execute(select(SmsOutbox).where(SmsOutbox.id == id))
    sms = res.scalar_one_or_none()
    if not sms:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"SMS {id} not found")

    sms.status = SmsStatusEnum.pending
    sms.attempts = 0
    sms.last_error = None
    sms.scheduled_at = utc_now()

    # Log audit event
    audit = AuditLog(
        actor_user_id=current_user.id,
        actor_role=current_user.role.value,
        action="retry_sms",
        entity_type="sms_outbox",
        entity_id=str(sms.id),
        meta={"to_e164": sms.to_e164, "template_key": sms.template_key},
        created_at=utc_now(),
    )
    db.add(audit)
    await db.commit()
    await db.refresh(sms)
    return sms


# ---------------------------------------------------------------------------
# Audit Logs
# ---------------------------------------------------------------------------


@router.get("/audit", response_model=list[AuditLogListItem], operation_id="list_audit_logs")
async def list_audit_logs(
    action: str | None = Query(None),
    entity_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.admin)),
):
    q = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
    if action:
        q = q.where(AuditLog.action == action)
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)

    res = await db.execute(q)
    return res.scalars().all()
