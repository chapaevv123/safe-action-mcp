from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest

from safe_action_mcp.core import *
from safe_action_mcp.engine import InjectedCrash, SafetyEngine
from safe_action_mcp.models import SimulatorResult, utcnow
from safe_action_mcp.store import LocalStore

def prepared(tmp_path,args,label="one"):
    store=LocalStore(str(tmp_path/f"{label}.db")); engine=SafetyEngine(store); p=engine.prepare(label,args)
    return store,engine,p

def rejected_without_effect(store,engine,p,args,admission,trust):
    with pytest.raises(ValueError): engine.approve(p["workflow_id"],"session","owner",args,admission,trust)
    assert store.hold_count()==0

def test_missing_evidence_blocks_end_to_end(tmp_path,args):
    store,e,p=prepared(tmp_path,args); rejected_without_effect(store,e,p,args,None,p["trust"])

def test_failed_evidence_blocks_end_to_end(tmp_path,args):
    store,e,p=prepared(tmp_path,args); failed=admit(validate_evidence(evidence_contract(),p["manifest"],args,external_adapter=True)); rejected_without_effect(store,e,p,args,failed,p["trust"])

@pytest.mark.parametrize("kind",["stale","rollback","conflict"])
def test_untrusted_release_blocks_end_to_end(tmp_path,args,kind):
    store,e,p=prepared(tmp_path,args,kind)
    if kind=="stale": manifest=make_manifest(datetime.now(timezone.utc)-timedelta(days=40)); trust=trust_manifest(manifest,current_hash=manifest.manifest_hash)
    elif kind=="rollback": manifest=make_manifest(version=1); trust=trust_manifest(manifest,current_version=2,current_hash=manifest.manifest_hash)
    else: manifest=make_manifest(); trust=trust_manifest(manifest,current_hash="different")
    rejected_without_effect(store,e,p,args,p["admission"],trust)

def test_valid_gate_allows_execution(tmp_path,args):
    store,e,p=prepared(tmp_path,args); c,b=e.approve(p["workflow_id"],"s","owner",args,p["admission"],p["trust"]); out=e.execute(p["workflow_id"],args,c,b,p["admission"],p["trust"]); assert out["status"]=="EXECUTED_SIMULATION" and store.hold_count()==1

def completed(tmp_path,args,label="result"):
    store,e,p=prepared(tmp_path,args,label); c,b=e.approve(p["workflow_id"],label,"owner",args,p["admission"],p["trust"])
    out=e.execute(p["workflow_id"],args,c,b,p["admission"],p["trust"]); activity=store.get_activity(out["trace"].activity_id)
    return store,e,p,c,b,out["result"],activity,out

def test_fabricated_hold_rejected(tmp_path,args):
    store,e,p,c,b,r,a,out=completed(tmp_path,args); forged=r.model_copy(update={"hold_id":"hold_fabricated"})
    with pytest.raises(ValueError,match="PERSISTED_HOLD_MISSING"): e.finalize(p["workflow_id"],args,c,b,forged,a.activity_id,p["admission"],p["trust"])

def test_fabricated_activity_rejected(tmp_path,args):
    store,e,p,c,b,r,a,out=completed(tmp_path,args)
    with pytest.raises(ValueError,match="PERSISTED_ACTIVITY_MISSING"): e.finalize(p["workflow_id"],args,c,b,r,"activity_fabricated",p["admission"],p["trust"])

def test_valid_hold_wrong_activity_rejected(tmp_path,args):
    store,e,p,c,b,r,a,out=completed(tmp_path,args); other=b.model_copy(update={"bound_action_id":"action_other","idempotency_key":"other"}); wrong=store.start_activity("other_workflow",other)
    with pytest.raises(ValueError,match="BINDING_MISMATCH"): e.finalize(p["workflow_id"],args,c,b,r,wrong.activity_id,p["admission"],p["trust"])

def test_valid_activity_wrong_hold_rejected(tmp_path,args):
    store,e,p,c,b,r,a,out=completed(tmp_path,args); forged=r.model_copy(update={"hold_id":"wrong"})
    with pytest.raises(ValueError): e.finalize(p["workflow_id"],args,c,b,forged,a.activity_id,p["admission"],p["trust"])

def test_hold_from_another_workflow_rejected(tmp_path,args):
    store,e,p,c,b,r,a,out=completed(tmp_path,args); other_args=args.model_copy(update={"time":"15:30"}); p2=e.prepare("other",other_args); c2,b2=e.approve(p2["workflow_id"],"other","owner",other_args,p2["admission"],p2["trust"]); out2=e.execute(p2["workflow_id"],other_args,c2,b2,p2["admission"],p2["trust"])
    with pytest.raises(ValueError): e.finalize(p["workflow_id"],args,c,b,out2["result"],a.activity_id,p["admission"],p["trust"])

@pytest.mark.parametrize("field,value",[("quoted_price",Decimal("120.00")),("provider","Changed"),("time","16:00")])
def test_persisted_result_argument_change_rejected(tmp_path,args,field,value):
    store,e,p,c,b,r,a,out=completed(tmp_path,args,field)
    with pytest.raises(ValueError,match="ARGUMENTS_MISMATCH"): e.finalize(p["workflow_id"],args.model_copy(update={field:value}),c,b,r,a.activity_id,p["admission"],p["trust"])

def test_valid_persisted_result_accepted(tmp_path,args): assert completed(tmp_path,args)[-1]["status"]=="EXECUTED_SIMULATION"

def test_receipt_identity_is_material(tmp_path,args):
    store,e,p,c,b,r,a,out=completed(tmp_path,args,"receipt"); first=out["receipt"]; second=e.finalize(p["workflow_id"],args,c,b,r,a.activity_id,p["admission"],p["trust"])["receipt"]
    assert first.receipt_id==second.receipt_id and first.created_at!=second.created_at
    rejected=e.finalize(p["workflow_id"],args,c,b,r,a.activity_id,p["admission"],p["trust"],verdict="REJECTED")["receipt"]
    assert rejected.receipt_id!=first.receipt_id
    other_args=args.model_copy(update={"time":"16:00"}); *_,other_out=completed(tmp_path,other_args,"receipt-other"); assert other_out["receipt"].receipt_id!=first.receipt_id and other_out["receipt"].result_ref!=first.result_ref

def test_activityref_completion_and_binding(tmp_path,args):
    store,e,p=prepared(tmp_path,args); c,b=e.approve(p["workflow_id"],"s","owner",args,p["admission"],p["trust"]); activity=store.start_activity(p["workflow_id"],b); assert activity.status=="STARTED" and activity.result_ref is None
    with pytest.raises(ValueError,match="MISMATCH"): store.start_activity("wrong",b)

def test_consent_scope_and_invocation_limit(tmp_path,args):
    store,e,p=prepared(tmp_path,args); c,b=e.approve(p["workflow_id"],"s","owner",args,p["admission"],p["trust"]); store.claim_consent(c,b)
    with pytest.raises(ValueError,match="LIMIT"): store.claim_consent(c,b)
    with pytest.raises(ValueError,match="TOOL_MISMATCH"): bind_action(c.model_copy(update={"tool_name":"other"}),args,p["admission"],p["trust"])
    with pytest.raises(ValueError,match="ACTION_HASH_INVALID"): bind_action(c.model_copy(update={"action_hash":"bad"}),args,p["admission"],p["trust"])

def test_trace_contains_full_links(tmp_path,args):
    *_,out=completed(tmp_path,args,"trace"); trace=out["trace"]; assert all((trace.consent_id,trace.bound_action_id,trace.activity_id,trace.result_ref,trace.decision_receipt_id))

@pytest.mark.parametrize("observed,action",[("HELD","NOOP"),(None,"WAIT"),("INVALID","BLOCKED"),("CANCELLED","PROPOSE_OWNER_ACTION")])
def test_reconciliation_matrix(observed,action): assert reconcile("HELD",observed).action==action

def test_contract_controls_evaluation(args):
    manifest=make_manifest(); full=validate_evidence(evidence_contract(),manifest,args,external_adapter=True)
    reduced=evidence_contract(tuple(x for x in EXPECTATIONS if x!="no_external_adapter")); without=validate_evidence(reduced,manifest,args,external_adapter=True)
    assert full.verdict=="FAIL" and without.verdict=="PASS" and len(without.findings)==len(full.findings)-1
