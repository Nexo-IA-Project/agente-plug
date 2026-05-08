from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FollowupStepResponse(BaseModel):
    id: UUID
    flow_id: UUID
    position: int
    delay_from_purchase_hours: int
    meta_template_name: str | None
    template_variables: dict
    message_text: str | None
    created_at: datetime


class FollowupFlowResponse(BaseModel):
    id: UUID
    account_id: UUID
    name: str
    product_tags: list[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CreateFlowRequest(BaseModel):
    name: str
    product_tags: list[str]


class UpdateFlowRequest(BaseModel):
    name: str | None = None
    product_tags: list[str] | None = None
    is_active: bool | None = None


class CreateStepRequest(BaseModel):
    position: int
    delay_from_purchase_hours: int
    meta_template_name: str | None = None
    template_variables: dict = {}
    message_text: str | None = None


class UpdateStepRequest(BaseModel):
    position: int | None = None
    delay_from_purchase_hours: int | None = None
    meta_template_name: str | None = None
    template_variables: dict | None = None
    message_text: str | None = None


class ReorderItem(BaseModel):
    id: UUID
    position: int


class ReorderStepsRequest(BaseModel):
    steps: list[ReorderItem]
