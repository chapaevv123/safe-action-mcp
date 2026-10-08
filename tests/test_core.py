from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError
from safe_action_mcp.core import *
from safe_action_mcp.models import *

def test_deterministic_serialization_and_hash(args): assert stable_hash(args)==stable_hash(args.model_dump(mode="json"))
def test_schema_rejects_extra(args):
    with pytest.raises(ValidationError): AppointmentArgs(**args.model_dump(), surprise=True)
def test_evidence_passes(args):
    r=validate_evidence(make_manifest(),args); assert r.verdict=="PASS" and admit(r).verdict=="ADMIT"
def test_missing_manifest_is_insufficient(args): assert admit(validate_evidence(None,args)).verdict=="INSUFFICIENT"
def test_external_adapter_rejected(args): assert validate_evidence(make_manifest(),args,True).verdict=="FAIL"
def test_stale_manifest_rejected(args):
    old=datetime.now(timezone.utc)-timedelta(days=40); assert validate_evidence(make_manifest(old),args).verdict=="FAIL"
def test_manifest_hash_tamper_rejected():
    m=make_manifest(); assert trust_manifest(m.model_copy(update={"manifest_hash":"0"*64})).verdict=="REJECT"
def test_manifest_rollback_rejected(): assert trust_manifest(make_manifest(version=1),current_version=2).rollback_state=="ROLLBACK"
def test_same_version_conflict_rejected(): assert trust_manifest(make_manifest(),current_hash="f"*64).conflict_state=="CONFLICT"
def test_material_price_diff(args):
    d=materiality_diff(args,args.model_copy(update={"quoted_price":args.quoted_price+10})); assert d.material_changed and d.changes[0].field=="quoted_price"
@pytest.mark.parametrize("field,value",[("time","15:30"),("provider","Other Provider"),("service","Plumbing"),("date","2026-10-21"),("currency","EUR"),("service_location_label","Office")])
def test_each_material_field_detected(args,field,value): assert materiality_diff(args,args.model_copy(update={field:value})).changes[0].field==field
def test_same_args_bind(args): assert bind_action(grant_consent("s","owner",args),args).arguments_hash==stable_hash(args)
def test_changed_args_reject(args):
    with pytest.raises(ValueError,match="MATERIAL_ARGUMENTS_CHANGED"): bind_action(grant_consent("s","owner",args),args.model_copy(update={"time":"15:30"}))
def test_expired_consent_reject(args):
    c=grant_consent("s","owner",args).model_copy(update={"expires_at":"2000-01-01T00:00:00Z"})
    with pytest.raises(ValueError,match="CONSENT_EXPIRED"): bind_action(c,args)
def test_duplicate_event_fold_ignored():
    e=new_event("w",1,"REQUEST_RECEIVED",{}); assert len(fold_events("w",[e,e]).seen_dedupe_keys)==1
def test_corrupt_sequence_detected():
    with pytest.raises(ValueError,match="CORRUPT"): fold_events("w",[new_event("w",2,"REQUEST_RECEIVED",{}),new_event("w",1,"TOOL_DISCOVERED",{})])
def test_partial_history_explicit(): assert fold_events("w",[new_event("w",1,"ACTIVITY_STARTED",{})]).partial_history
