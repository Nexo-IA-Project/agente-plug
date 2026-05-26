from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

HUBLA_EVENT_TYPES: tuple[str, ...] = (
    "subscription.activated",
    "subscription.created",
    "lead.abandoned",
    "subscription.deactivated",
    "subscription.expiring",
    "invoice.refunded",
)

HublaEventType = Literal[
    "subscription.activated",
    "subscription.created",
    "lead.abandoned",
    "subscription.deactivated",
    "subscription.expiring",
    "invoice.refunded",
]


class StepVariableBindingDto(BaseModel):
    source: Literal["customer_name", "product_name", "contact_phone", "contact_email", "static"]
    value: str | None = None

    @model_validator(mode="after")
    def _check_value(self) -> StepVariableBindingDto:
        if self.source == "static" and not self.value:
            raise ValueError("static binding requires non-empty value")
        if self.source != "static" and self.value is not None:
            raise ValueError("non-static binding must not include value")
        return self


class OnboardingStepResponse(BaseModel):
    id: UUID
    flow_id: UUID
    position: int
    delay_from_purchase_minutes: int
    meta_template_name: str | None
    template_variables: dict
    message_text: str | None
    created_at: datetime


class ProductSummary(BaseModel):
    id: UUID
    name: str
    hubla_id: str


class OnboardingFlowStats(BaseModel):
    enrollments_active: int = 0
    enrollments_completed: int = 0


class OnboardingFlowResponse(BaseModel):
    id: UUID
    name: str
    is_active: bool
    trigger_event_type: HublaEventType
    product: ProductSummary
    steps_count: int
    created_at: datetime
    updated_at: datetime
    stats: OnboardingFlowStats = Field(default_factory=OnboardingFlowStats)


class CreateFlowRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    product_id: UUID
    trigger_event_type: HublaEventType = "subscription.activated"
    is_active: bool = True


class UpdateFlowRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    product_id: UUID | None = None
    trigger_event_type: HublaEventType | None = None
    is_active: bool | None = None


class CreateStepRequest(BaseModel):
    delay_from_purchase_minutes: int = Field(ge=0)
    meta_template_name: str | None = None
    template_variables: dict[str, StepVariableBindingDto] = Field(default_factory=dict)
    message_text: str | None = None
    position: int | None = None

    @model_validator(mode="after")
    def _check_oneof(self) -> CreateStepRequest:
        has_template = bool(self.meta_template_name)
        has_text = bool(self.message_text)
        if has_template == has_text:
            raise ValueError("exactly one of meta_template_name or message_text must be provided")
        return self


class UpdateStepRequest(BaseModel):
    position: int | None = None
    delay_from_purchase_minutes: int | None = Field(default=None, ge=0)
    meta_template_name: str | None = None
    template_variables: dict[str, StepVariableBindingDto] | None = None
    message_text: str | None = None


class ReorderItem(BaseModel):
    id: UUID
    position: int


class ReorderStepsRequest(BaseModel):
    steps: list[ReorderItem]
