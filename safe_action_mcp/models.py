from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PROTOCOL_VERSION = "2025-11-25"
TOOL_NAME = "hold_service_appointment"
MATERIAL_FIELDS = ("provider", "service", "date", "time", "quoted_price", "currency", "service_location_label")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AppointmentArgs(StrictModel):
    provider: str = Field(min_length=2, max_length=100)
    service: str = Field(min_length=2, max_length=100)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    quoted_price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    service_location_label: str = Field(min_length=2, max_length=120)
    note: str | None = Field(default=None, max_length=300)

    @field_validator("quoted_price")
    @classmethod
    def normalize_price(cls, value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"))


class EvidenceFinding(StrictModel):
    expectation: str
    status: Literal["PASS", "FAIL", "INSUFFICIENT"]
    reason_code: str
    evidence_ref: str | None = None


class EvidenceContract(StrictModel):
    contract_id: str = "appointment-evidence-v1"
    version: str = "1.0.0"
    expectations: tuple[str, ...]


class EvidenceValidationResult(StrictModel):
    verdict: Literal["PASS", "FAIL", "PARTIAL", "INSUFFICIENT"]
    findings: tuple[EvidenceFinding, ...]
    evaluated_at: str
    result_hash: str


class EvidenceAdmissionResult(StrictModel):
    verdict: Literal["ADMIT", "REJECT", "INSUFFICIENT"]
    validation_hash: str
    reason_codes: tuple[str, ...]


class MCPToolRiskManifest(StrictModel):
    tool_name: str
    risk_class: Literal["HIGH_IMPACT_SIMULATED"]
    material_fields: tuple[str, ...]
    consent_required: bool
    simulator_only: bool
    version: int = Field(ge=1)
    issued_at: str
    expires_at: str
    source_refs: tuple[str, ...]
    manifest_hash: str


class ReleaseTrustDecision(StrictModel):
    verdict: Literal["ACCEPT", "REVIEW", "REJECT"]
    freshness_state: str
    rollback_state: str
    conflict_state: str
    reason_codes: tuple[str, ...]
    observed_at: str
    decision_hash: str


class ConsentRecord(StrictModel):
    consent_id: str
    session_id: str
    owner_label: str
    tool_name: str
    arguments_hash: str
    action_hash: str
    granted_at: str
    expires_at: str
    max_invocations: int = 1


class BoundActionRef(StrictModel):
    bound_action_id: str
    consent_id: str
    tool_name: str
    arguments_hash: str
    idempotency_key: str
    expires_at: str


class MaterialChange(StrictModel):
    field: str
    before: Any
    after: Any
    reason_code: str = "FIELD_CHANGED"


class ToolArgumentMaterialityDiff(StrictModel):
    material_changed: bool
    changes: tuple[MaterialChange, ...]
    reason_codes: tuple[str, ...]


class WorkflowEvent(StrictModel):
    event_id: str
    workflow_id: str
    sequence: int = Field(ge=1)
    event_type: str
    occurred_at: str
    payload_hash: str
    payload: dict[str, Any]
    dedupe_key: str


class DurableWorkflowState(StrictModel):
    workflow_id: str
    phase: str
    seen_dedupe_keys: tuple[str, ...]
    completed_activity_ids: tuple[str, ...]
    hold_id: str | None = None
    terminal: bool = False
    partial_history: bool = False


class ActivityRef(StrictModel):
    activity_id: str
    bound_action_id: str
    status: Literal["STARTED", "COMPLETED"]
    result_ref: str | None = None


class SimulatorResult(StrictModel):
    hold_id: str
    status: Literal["HELD", "CANCELLED"]
    bound_action_id: str
    idempotency_key: str
    arguments_hash: str
    created_at: str
    duplicate_suppressed: bool = False


class PulseTraceContext(StrictModel):
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    workflow_id: str
    bound_action_id: str | None = None
    decision_receipt_id: str | None = None


class ReconcileDecision(StrictModel):
    action: Literal["NOOP", "WAIT", "BLOCKED", "PROPOSE_OWNER_ACTION"]
    desired_status: str
    observed_status: str | None
    reason_codes: tuple[str, ...]


class DecisionReceipt(StrictModel):
    receipt_id: str
    verdict: Literal["EXECUTED_SIMULATION", "REJECTED"]
    workflow_id: str
    consent_id: str
    bound_action_id: str
    result_ref: str
    trace_id: str
    reason_codes: tuple[str, ...]
    created_at: str
    receipt_hash: str
