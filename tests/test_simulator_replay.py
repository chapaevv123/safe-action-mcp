import pytest
from safe_action_mcp.engine import InjectedCrash, SafetyEngine
from safe_action_mcp.store import LocalStore

def setup(tmp_path,args):
    store=LocalStore(str(tmp_path/"test.db")); e=SafetyEngine(store); p=e.prepare("session",args); c,b=e.approve(p["workflow_id"],"session","owner",args); return store,e,p["workflow_id"],c,b
def test_create_inspect_cancel(tmp_path,args):
    store,e,w,c,b=setup(tmp_path,args); r=e.execute(w,args,c,b)["result"]; assert store.get_hold(r.hold_id).status=="HELD"; assert store.cancel_hold(r.hold_id).status=="CANCELLED"
def test_same_idempotency_returns_same_hold(tmp_path,args):
    store,e,w,c,b=setup(tmp_path,args); a=store.create_hold(args,b); z=store.create_hold(args,b); assert a.hold_id==z.hold_id and z.duplicate_suppressed
def test_idempotency_conflict_rejected(tmp_path,args):
    store,e,w,c,b=setup(tmp_path,args); store.create_hold(args,b)
    with pytest.raises(ValueError,match="CONFLICT"): store.create_hold(args.model_copy(update={"time":"15:30"}),b)
def test_crash_replay_one_effect(tmp_path,args):
    store,e,w,c,b=setup(tmp_path,args)
    with pytest.raises(InjectedCrash): e.execute(w,args,c,b,inject_crash=True)
    restarted_engine=SafetyEngine(store)
    assert store.hold_count()==1; out=restarted_engine.replay(w,args,c,b); assert store.hold_count()==1 and out["workflow"].terminal
    kinds=[x.event_type for x in store.events(w)]; assert "DUPLICATE_SUPPRESSED" in kinds and "RECEIPT_ISSUED" in kinds
def test_mutated_execution_rejected(tmp_path,args):
    store,e,w,c,b=setup(tmp_path,args); out=e.execute(w,args.model_copy(update={"provider":"Attacker"}),c,b); assert out["status"]=="REJECTED" and store.hold_count()==0
def test_result_verification_detects_mismatch(tmp_path,args):
    store,e,w,c,b=setup(tmp_path,args); r=store.create_hold(args,b).model_copy(update={"bound_action_id":"wrong"})
    with pytest.raises(ValueError,match="RESULT_BINDING_FAILED"): e.finalize(w,args,c,b,r,"activity")
