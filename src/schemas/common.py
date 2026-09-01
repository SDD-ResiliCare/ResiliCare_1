"""Shared API schemas."""

from datetime import datetime
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
