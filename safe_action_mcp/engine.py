from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .core import *
from .models import *
from .store import LocalStore


class InjectedCrash(RuntimeError):
    pass


class SafetyEngine:
    def __init__(self, store: LocalStore):
        self.store=store

    def _record(self, workflow_id: str, kind: str, payload: dict[str,Any]) -> WorkflowEvent:
        existing=self.store.events(workflow_id)
        event=new_event(workflow_id,len(existing)+1,kind,payload)
        self.store.append_event(event)
        return event

    def prepare(self, session_id: str, args: AppointmentArgs) -> dict[str,Any]:
        workflow_id="workflow_"+stable_hash({"session":session_id,"args":stable_hash(args)})[:20]
        if not self.store.events(workflow_id):
            self._record(workflow_id,"REQUEST_RECEIVED",{"arguments_hash":stable_hash(args)})
            self._record(workflow_id,"TOOL_DISCOVERED",{"tool":TOOL_NAME})
        contract=evidence_contract(); manifest=make_manifest(); validation=validate_evidence(contract,manifest,args); admission=admit(validation); trust=trust_manifest(manifest,current_hash=manifest.manifest_hash)
        for kind,obj in (("MANIFEST_VALIDATED",manifest),("EVIDENCE_VALIDATED",validation),("TRUST_CHECKED",trust)):
            self._record(workflow_id,kind,{"ref_hash":stable_hash(obj),"verdict":getattr(obj,"verdict",None)})
        return {"workflow_id":workflow_id,"contract":contract,"manifest":manifest,"validation":validation,"admission":admission,"trust":trust}

    def approve(self, workflow_id: str, session_id: str, owner_label: str, args: AppointmentArgs,
                admission: EvidenceAdmissionResult | None, trust: ReleaseTrustDecision | None) -> tuple[ConsentRecord,BoundActionRef]:
        enforce_gate(admission,trust)
        consent=grant_consent(session_id,owner_label,args); bound=bind_action(consent,args,admission,trust)
        self._record(workflow_id,"CONSENT_GRANTED",{"consent_id":consent.consent_id,"arguments_hash":consent.arguments_hash})
        self._record(workflow_id,"ACTION_BOUND",{"bound_action_id":bound.bound_action_id,"arguments_hash":bound.arguments_hash})
        return consent,bound

    def execute(self, workflow_id: str, args: AppointmentArgs, consent: ConsentRecord, bound: BoundActionRef,
                admission: EvidenceAdmissionResult | None, trust: ReleaseTrustDecision | None,
                inject_crash: bool=False) -> dict[str,Any]:
        diff_reason=None
        try:
            checked=bind_action(consent,args,admission,trust)
            if checked.evidence_admission_ref != bound.evidence_admission_ref or checked.trust_decision_ref != bound.trust_decision_ref:
                raise ValueError("BOUND_GATE_REFERENCE_MISMATCH")
        except ValueError as exc: diff_reason=str(exc); checked=None
        if checked is None or checked.bound_action_id != bound.bound_action_id:
            return {"status":"REJECTED","reason":diff_reason or "BOUND_ACTION_MISMATCH"}
        state=fold_events(workflow_id,self.store.events(workflow_id))
        activity_id="activity_"+bound.bound_action_id.removeprefix("action_")
        try: persisted_activity=self.store.get_activity(activity_id)
        except KeyError: persisted_activity=None
        if persisted_activity and persisted_activity.status == "COMPLETED":
            result=self.store.get_hold(state.hold_id)
            self._record(workflow_id,"DUPLICATE_SUPPRESSED",{"activity":persisted_activity.model_dump(mode="json"),"activity_id":activity_id,"hold_id":result.hold_id})
        else:
            self.store.claim_consent(consent,bound)
            activity=self.store.start_activity(workflow_id,bound)
            self._record(workflow_id,"ACTIVITY_STARTED",{"activity":activity.model_dump(mode="json"),"activity_id":activity.activity_id,"bound_action_id":bound.bound_action_id})
            result=self.store.create_hold(workflow_id,args,bound)
            activity=self.store.complete_activity(activity.activity_id,result.hold_id)
            self._record(workflow_id,"ACTIVITY_COMPLETED",{"activity":activity.model_dump(mode="json"),"activity_id":activity.activity_id,"hold_id":result.hold_id,"result_hash":stable_hash(result)})
            if inject_crash:
                self._record(workflow_id,"CRASH_INJECTED",{"point":"AFTER_ACTIVITY_COMPLETED"})
                raise InjectedCrash("INJECTED_AFTER_ACTIVITY_COMPLETED")
        return self.finalize(workflow_id,args,consent,bound,result,activity_id,admission,trust)

    def replay(self, workflow_id: str, args: AppointmentArgs, consent: ConsentRecord, bound: BoundActionRef,
               admission: EvidenceAdmissionResult | None, trust: ReleaseTrustDecision | None) -> dict[str,Any]:
        state=fold_events(workflow_id,self.store.events(workflow_id)); self._record(workflow_id,"WORKFLOW_REPLAYED",{"phase":state.phase,"hold_id":state.hold_id})
        return self.execute(workflow_id,args,consent,bound,admission,trust)

    def finalize(self, workflow_id: str, args: AppointmentArgs, consent: ConsentRecord, bound: BoundActionRef,
                 result: SimulatorResult, activity_id: str, admission: EvidenceAdmissionResult,
                 trust: ReleaseTrustDecision, verdict: str="EXECUTED_SIMULATION") -> dict[str,Any]:
        enforce_gate(admission,trust)
        activity=self.store.verify_result(workflow_id,args,bound,result,activity_id)
        self._record(workflow_id,"RESULT_VERIFIED",{"result_ref":result.hold_id,"activity_id":activity_id})
        reconciliation=reconcile("HELD",result.status)
        self._record(workflow_id,"RECONCILED",reconciliation.model_dump())
        trace_id="trace_"+stable_hash({"workflow":workflow_id})[:20]
        material=dict(verdict=verdict,workflow_id=workflow_id,consent_id=consent.consent_id,bound_action_id=bound.bound_action_id,
            evidence_admission_ref=bound.evidence_admission_ref,trust_decision_ref=bound.trust_decision_ref,activity_id=activity.activity_id,
            result_ref=result.hold_id,reconcile_action=reconciliation.action,trace_id=trace_id,reason_codes=("SIMULATED_ONLY","RESULT_BOUND","NO_EXTERNAL_SIDE_EFFECT"))
        receipt_hash=stable_hash(material); receipt_id="receipt_"+receipt_hash[:20]
        receipt=DecisionReceipt(receipt_id=receipt_id,**material,created_at=utcnow(),receipt_hash=receipt_hash)
        self._record(workflow_id,"RECEIPT_ISSUED",{"receipt_id":receipt.receipt_id,"receipt_hash":receipt.receipt_hash})
        trace=PulseTraceContext(trace_id=trace_id,span_id="span_"+receipt_hash[:16],workflow_id=workflow_id,consent_id=consent.consent_id,
            bound_action_id=bound.bound_action_id,activity_id=activity.activity_id,result_ref=result.hold_id,decision_receipt_id=receipt.receipt_id)
        return {"status":"EXECUTED_SIMULATION","result":result,"reconciliation":reconciliation,"receipt":receipt,"trace":trace,"workflow":fold_events(workflow_id,self.store.events(workflow_id))}
