from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .models import *

EXPECTATIONS = (
    "manifest_exists", "tool_name_matches", "manifest_fresh", "version_recognized",
    "simulator_only", "material_fields_complete", "currency_present", "quote_valid",
    "date_time_valid", "no_external_adapter",
)


def make_manifest(now: datetime | None = None, version: int = 1) -> MCPToolRiskManifest:
    now = now or datetime.now(timezone.utc)
    body = dict(tool_name=TOOL_NAME, risk_class="HIGH_IMPACT_SIMULATED", material_fields=MATERIAL_FIELDS,
                consent_required=True, simulator_only=True, version=version,
                issued_at=now.isoformat().replace("+00:00", "Z"),
                expires_at=(now + timedelta(days=30)).isoformat().replace("+00:00", "Z"),
                source_refs=("local://risk-policy/appointment-v1",))
    return MCPToolRiskManifest(**body, manifest_hash=stable_hash(body))


def validate_evidence(manifest: MCPToolRiskManifest | None, args: AppointmentArgs | None,
                      external_adapter: bool = False, now: datetime | None = None) -> EvidenceValidationResult:
    now = now or datetime.now(timezone.utc)
    checks: list[tuple[str, bool | None, str]] = [
        ("manifest_exists", True if manifest is not None else None, "MANIFEST_PRESENT"),
        ("tool_name_matches", None if not manifest else manifest.tool_name == TOOL_NAME, "TOOL_NAME_MATCH"),
        ("manifest_fresh", None if not manifest else datetime.fromisoformat(manifest.expires_at.replace("Z", "+00:00")) > now, "MANIFEST_FRESH"),
        ("version_recognized", None if not manifest else manifest.version == 1, "VERSION_RECOGNIZED"),
        ("simulator_only", None if not manifest else manifest.simulator_only, "SIMULATOR_ONLY"),
        ("material_fields_complete", None if not manifest else set(MATERIAL_FIELDS).issubset(manifest.material_fields), "MATERIAL_FIELDS_COMPLETE"),
        ("currency_present", None if not args else bool(args.currency), "CURRENCY_PRESENT"),
        ("quote_valid", None if not args else args.quoted_price > 0, "QUOTE_VALID"),
        ("date_time_valid", None if not args else bool(args.date and args.time), "DATE_TIME_VALID"),
        ("no_external_adapter", not external_adapter, "NO_EXTERNAL_ADAPTER"),
    ]
    findings = tuple(EvidenceFinding(expectation=k, status="INSUFFICIENT" if ok is None else "PASS" if ok else "FAIL",
                                     reason_code=code if ok else f"{code}_FAILED") for k, ok, code in checks)
    statuses = {f.status for f in findings}
    verdict = "FAIL" if "FAIL" in statuses else "INSUFFICIENT" if "INSUFFICIENT" in statuses else "PASS"
    body = {"verdict": verdict, "findings": [f.model_dump() for f in findings], "evaluated_at": utcnow()}
    return EvidenceValidationResult(**body, result_hash=stable_hash(body))


def admit(result: EvidenceValidationResult) -> EvidenceAdmissionResult:
    verdict = "ADMIT" if result.verdict == "PASS" else "INSUFFICIENT" if result.verdict in {"INSUFFICIENT", "PARTIAL"} else "REJECT"
    return EvidenceAdmissionResult(verdict=verdict, validation_hash=result.result_hash,
                                   reason_codes=tuple(f.reason_code for f in result.findings if f.status != "PASS") or ("ALL_EXPECTATIONS_PASS",))


def trust_manifest(manifest: MCPToolRiskManifest, current_version: int = 1,
                   current_hash: str | None = None, now: datetime | None = None) -> ReleaseTrustDecision:
    now = now or datetime.now(timezone.utc); reasons=[]
    raw = manifest.model_dump(exclude={"manifest_hash"})
    integrity = stable_hash(raw) == manifest.manifest_hash
    fresh = datetime.fromisoformat(manifest.expires_at.replace("Z", "+00:00")) > now
    rollback = manifest.version < current_version
    conflict = manifest.version == current_version and current_hash is not None and current_hash != manifest.manifest_hash
    if not integrity: reasons.append("MANIFEST_HASH_INVALID")
    if not fresh: reasons.append("MANIFEST_EXPIRED")
    if rollback: reasons.append("VERSION_ROLLBACK")
    if conflict: reasons.append("SAME_VERSION_HASH_CONFLICT")
    verdict = "REJECT" if reasons else "ACCEPT"
    body = dict(verdict=verdict, freshness_state="FRESH" if fresh else "STALE", rollback_state="ROLLBACK" if rollback else "MONOTONIC",
                conflict_state="CONFLICT" if conflict else "NONE", reason_codes=tuple(reasons or ["TRUST_CHECKS_PASS"]), observed_at=utcnow())
    return ReleaseTrustDecision(**body, decision_hash=stable_hash(body))


def grant_consent(session_id: str, owner_label: str, args: AppointmentArgs, ttl_minutes: int = 10) -> ConsentRecord:
    now = datetime.now(timezone.utc); ah=stable_hash(args)
    action_hash=stable_hash({"tool":TOOL_NAME,"arguments_hash":ah,"session_id":session_id})
    return ConsentRecord(consent_id="consent_"+action_hash[:20], session_id=session_id, owner_label=owner_label,
        tool_name=TOOL_NAME, arguments_hash=ah, action_hash=action_hash, granted_at=now.isoformat().replace("+00:00","Z"),
        expires_at=(now+timedelta(minutes=ttl_minutes)).isoformat().replace("+00:00","Z"))


def bind_action(consent: ConsentRecord, args: AppointmentArgs) -> BoundActionRef:
    if datetime.fromisoformat(consent.expires_at.replace("Z", "+00:00")) <= datetime.now(timezone.utc): raise ValueError("CONSENT_EXPIRED")
    if stable_hash(args) != consent.arguments_hash: raise ValueError("MATERIAL_ARGUMENTS_CHANGED")
    bid="action_"+stable_hash({"consent":consent.consent_id,"args":consent.arguments_hash})[:20]
    return BoundActionRef(bound_action_id=bid, consent_id=consent.consent_id, tool_name=TOOL_NAME,
                          arguments_hash=consent.arguments_hash, idempotency_key=bid, expires_at=consent.expires_at)


def materiality_diff(approved: AppointmentArgs, proposed: AppointmentArgs) -> ToolArgumentMaterialityDiff:
    a=approved.model_dump(mode="json"); b=proposed.model_dump(mode="json"); changes=[]
    for field in MATERIAL_FIELDS:
        if a[field] != b[field]: changes.append(MaterialChange(field=field,before=a[field],after=b[field]))
    return ToolArgumentMaterialityDiff(material_changed=bool(changes), changes=tuple(changes),
        reason_codes=tuple(f"FIELD_CHANGED:{x.field}" for x in changes) or ("NO_MATERIAL_CHANGE",))


EVENT_ORDER = ["REQUEST_RECEIVED","TOOL_DISCOVERED","MANIFEST_VALIDATED","EVIDENCE_VALIDATED","TRUST_CHECKED",
 "CONSENT_GRANTED","ACTION_BOUND","ACTIVITY_STARTED","ACTIVITY_COMPLETED","CRASH_INJECTED","WORKFLOW_REPLAYED",
 "DUPLICATE_SUPPRESSED","RESULT_VERIFIED","RECONCILED","RECEIPT_ISSUED"]


def fold_events(workflow_id: str, events: list[WorkflowEvent]) -> DurableWorkflowState:
    seen=set(); completed=[]; hold=None; last=0
    for e in events:
        if e.workflow_id != workflow_id: raise ValueError("CROSS_WORKFLOW_EVENT")
        if e.dedupe_key in seen: continue
        if e.sequence <= last: raise ValueError("CORRUPT_EVENT_SEQUENCE")
        seen.add(e.dedupe_key); last=e.sequence
        if e.event_type == "ACTIVITY_COMPLETED":
            completed.append(e.payload["activity_id"]); hold=e.payload["hold_id"]
    phase=events[-1].event_type if events else "EMPTY"
    return DurableWorkflowState(workflow_id=workflow_id, phase=phase, seen_dedupe_keys=tuple(sorted(seen)),
        completed_activity_ids=tuple(completed), hold_id=hold, terminal=phase=="RECEIPT_ISSUED",
        partial_history=bool(events and events[0].event_type != "REQUEST_RECEIVED"))


def new_event(workflow_id: str, sequence: int, event_type: str, payload: dict[str, Any]) -> WorkflowEvent:
    ph=stable_hash(payload); key=f"{workflow_id}:{event_type}:{ph}"
    return WorkflowEvent(event_id="event_"+stable_hash({"key":key,"seq":sequence})[:20],workflow_id=workflow_id,
        sequence=sequence,event_type=event_type,occurred_at=utcnow(),payload_hash=ph,payload=payload,dedupe_key=key)
