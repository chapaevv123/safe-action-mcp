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
        manifest=make_manifest(); validation=validate_evidence(manifest,args); admission=admit(validation); trust=trust_manifest(manifest,current_hash=manifest.manifest_hash)
        for kind,obj in (("MANIFEST_VALIDATED",manifest),("EVIDENCE_VALIDATED",validation),("TRUST_CHECKED",trust)):
            self._record(workflow_id,kind,{"ref_hash":stable_hash(obj),"verdict":getattr(obj,"verdict",None)})
        return {"workflow_id":workflow_id,"manifest":manifest,"validation":validation,"admission":admission,"trust":trust}

    def approve(self, workflow_id: str, session_id: str, owner_label: str, args: AppointmentArgs) -> tuple[ConsentRecord,BoundActionRef]:
        consent=grant_consent(session_id,owner_label,args); bound=bind_action(consent,args)
        self._record(workflow_id,"CONSENT_GRANTED",{"consent_id":consent.consent_id,"arguments_hash":consent.arguments_hash})
        self._record(workflow_id,"ACTION_BOUND",{"bound_action_id":bound.bound_action_id,"arguments_hash":bound.arguments_hash})
        return consent,bound

    def execute(self, workflow_id: str, args: AppointmentArgs, consent: ConsentRecord, bound: BoundActionRef,
                inject_crash: bool=False) -> dict[str,Any]:
        diff_reason=None
        try: checked=bind_action(consent,args)
        except ValueError as exc: diff_reason=str(exc); checked=None
        if checked is None or checked.bound_action_id != bound.bound_action_id:
            return {"status":"REJECTED","reason":diff_reason or "BOUND_ACTION_MISMATCH"}
        state=fold_events(workflow_id,self.store.events(workflow_id))
        activity_id="activity_"+bound.bound_action_id.removeprefix("action_")
        if activity_id in state.completed_activity_ids:
            result=self.store.get_hold(state.hold_id)
            self._record(workflow_id,"DUPLICATE_SUPPRESSED",{"activity_id":activity_id,"hold_id":result.hold_id})
        else:
            self._record(workflow_id,"ACTIVITY_STARTED",{"activity_id":activity_id,"bound_action_id":bound.bound_action_id})
            result=self.store.create_hold(args,bound)
            self._record(workflow_id,"ACTIVITY_COMPLETED",{"activity_id":activity_id,"hold_id":result.hold_id,"result_hash":stable_hash(result)})
            if inject_crash:
                self._record(workflow_id,"CRASH_INJECTED",{"point":"AFTER_ACTIVITY_COMPLETED"})
                raise InjectedCrash("INJECTED_AFTER_ACTIVITY_COMPLETED")
        return self.finalize(workflow_id,args,consent,bound,result,activity_id)

    def replay(self, workflow_id: str, args: AppointmentArgs, consent: ConsentRecord, bound: BoundActionRef) -> dict[str,Any]:
        state=fold_events(workflow_id,self.store.events(workflow_id)); self._record(workflow_id,"WORKFLOW_REPLAYED",{"phase":state.phase,"hold_id":state.hold_id})
        return self.execute(workflow_id,args,consent,bound)

    def finalize(self, workflow_id: str, args: AppointmentArgs, consent: ConsentRecord, bound: BoundActionRef,
                 result: SimulatorResult, activity_id: str) -> dict[str,Any]:
        verified=(result.bound_action_id==bound.bound_action_id and result.arguments_hash==bound.arguments_hash and result.status in {"HELD","CANCELLED"})
        if not verified: raise ValueError("RESULT_BINDING_FAILED")
        self._record(workflow_id,"RESULT_VERIFIED",{"result_ref":result.hold_id,"activity_id":activity_id})
        reconciliation=ReconcileDecision(action="NOOP" if result.status=="HELD" else "PROPOSE_OWNER_ACTION",desired_status="HELD",observed_status=result.status,reason_codes=("DESIRED_STATE_OBSERVED",) if result.status=="HELD" else ("HOLD_CANCELLED",))
        self._record(workflow_id,"RECONCILED",reconciliation.model_dump())
        trace_id="trace_"+stable_hash({"workflow":workflow_id})[:20]
        rb=dict(verdict="EXECUTED_SIMULATION",workflow_id=workflow_id,consent_id=consent.consent_id,bound_action_id=bound.bound_action_id,result_ref=result.hold_id,trace_id=trace_id,reason_codes=("SIMULATED_ONLY","RESULT_BOUND","NO_EXTERNAL_SIDE_EFFECT"),created_at=utcnow())
        receipt_id="receipt_"+stable_hash(rb)[:20]; receipt=DecisionReceipt(receipt_id=receipt_id,**rb,receipt_hash=stable_hash({**rb,"receipt_id":receipt_id}))
        self._record(workflow_id,"RECEIPT_ISSUED",{"receipt_id":receipt.receipt_id,"receipt_hash":receipt.receipt_hash})
        trace=PulseTraceContext(trace_id=trace_id,span_id="span_"+stable_hash(receipt)[:16],workflow_id=workflow_id,bound_action_id=bound.bound_action_id,decision_receipt_id=receipt.receipt_id)
        return {"status":"EXECUTED_SIMULATION","result":result,"reconciliation":reconciliation,"receipt":receipt,"trace":trace,"workflow":fold_events(workflow_id,self.store.events(workflow_id))}
