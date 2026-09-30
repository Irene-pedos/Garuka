from fastapi import APIRouter
from pydantic import BaseModel

from app.db.session import check_db_health

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    db: str
    version: str


@router.get("/health", response_model=HealthResponse, operation_id="get_health")
async def health_check():
    db_ok = await check_db_health()
    return HealthResponse(
        status="ok",
        db="ok" if db_ok else "unreachable",
        version="0.1.0",
    )
