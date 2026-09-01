"""Shared API schemas."""

from datetime import datetime
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ResourceResponse(ORMModel):
    id: UUID
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


ItemT = TypeVar("ItemT")


class Page[ItemT](BaseModel):
    items: list[ItemT]
    page: int
    page_size: int
    total: int
    has_next: bool


class StatusUpdate(BaseModel):
    status: str
    reason: str | None = None


class ReasonAction(BaseModel):
    reason: str
