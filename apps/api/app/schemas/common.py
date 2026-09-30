from typing import Any

from pydantic import BaseModel


class PaginatedResponse[T](BaseModel):
    items: list[T]
    page: int
    page_size: int
    total: int


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class StandardErrorResponse(BaseModel):
    error: ErrorDetail
