from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import ActivityRef, AppointmentArgs, BoundActionRef, ConsentRecord, SimulatorResult, WorkflowEvent, canonical, stable_hash, utcnow


class LocalStore:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS holds(
          hold_id TEXT PRIMARY KEY, arguments_json TEXT NOT NULL, arguments_hash TEXT NOT NULL,
          provider TEXT NOT NULL, service TEXT NOT NULL, date TEXT NOT NULL, time TEXT NOT NULL,
          quoted_price TEXT NOT NULL, currency TEXT NOT NULL, location TEXT NOT NULL,
          status TEXT NOT NULL CHECK(status IN ('HELD','CANCELLED')), created_at TEXT NOT NULL,
          bound_action_id TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE, workflow_id TEXT);
        CREATE TABLE IF NOT EXISTS events(
          event_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, sequence INTEGER NOT NULL,
          event_type TEXT NOT NULL, occurred_at TEXT NOT NULL, payload_hash TEXT NOT NULL,
          payload_json TEXT NOT NULL, dedupe_key TEXT NOT NULL, UNIQUE(workflow_id,dedupe_key),
          UNIQUE(workflow_id,sequence));
        CREATE TABLE IF NOT EXISTS activities(
          activity_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, bound_action_id TEXT NOT NULL,
          idempotency_key TEXT NOT NULL UNIQUE, status TEXT NOT NULL CHECK(status IN ('STARTED','COMPLETED')),
          result_ref TEXT);
        CREATE TABLE IF NOT EXISTS consent_usage(
          consent_id TEXT PRIMARY KEY, bound_action_id TEXT NOT NULL, invocation_count INTEGER NOT NULL);
        """)
        hold_columns={r[1] for r in self.db.execute("PRAGMA table_info(holds)")}
        if "workflow_id" not in hold_columns:
            self.db.execute("ALTER TABLE holds ADD COLUMN workflow_id TEXT")
        self.db.commit()

    def claim_consent(self, consent: ConsentRecord, bound: BoundActionRef) -> None:
        row=self.db.execute("SELECT * FROM consent_usage WHERE consent_id=?",(consent.consent_id,)).fetchone()
        if row: raise ValueError("CONSENT_INVOCATION_LIMIT_REACHED")
        if consent.max_invocations != 1: raise ValueError("UNSUPPORTED_CONSENT_INVOCATION_SCOPE")
        self.db.execute("INSERT INTO consent_usage VALUES(?,?,1)",(consent.consent_id,bound.bound_action_id)); self.db.commit()

    def start_activity(self, workflow_id: str, bound: BoundActionRef) -> ActivityRef:
        activity_id="activity_"+bound.bound_action_id.removeprefix("action_")
        row=self.db.execute("SELECT * FROM activities WHERE activity_id=?",(activity_id,)).fetchone()
        if row:
            if row["workflow_id"] != workflow_id or row["bound_action_id"] != bound.bound_action_id or row["idempotency_key"] != bound.idempotency_key:
                raise ValueError("ACTIVITY_BOUND_ACTION_MISMATCH")
            return self._activity(row)
        self.db.execute("INSERT INTO activities VALUES(?,?,?,?,?,NULL)",(activity_id,workflow_id,bound.bound_action_id,bound.idempotency_key,"STARTED")); self.db.commit()
        return self.get_activity(activity_id)

    def complete_activity(self, activity_id: str, result_ref: str) -> ActivityRef:
        self.get_activity(activity_id)
        self.db.execute("UPDATE activities SET status='COMPLETED',result_ref=? WHERE activity_id=?",(result_ref,activity_id)); self.db.commit()
        return self.get_activity(activity_id)

    def _activity(self,row) -> ActivityRef:
        return ActivityRef(activity_id=row["activity_id"],workflow_id=row["workflow_id"],bound_action_id=row["bound_action_id"],idempotency_key=row["idempotency_key"],status=row["status"],result_ref=row["result_ref"])

    def get_activity(self, activity_id: str) -> ActivityRef:
        row=self.db.execute("SELECT * FROM activities WHERE activity_id=?",(activity_id,)).fetchone()
        if not row: raise KeyError("ACTIVITY_NOT_FOUND")
        return self._activity(row)

    def create_hold(self, workflow_id: str, args: AppointmentArgs, bound: BoundActionRef) -> SimulatorResult:
        ah=stable_hash(args)
        existing=self.db.execute("SELECT * FROM holds WHERE idempotency_key=?",(bound.idempotency_key,)).fetchone()
        if existing:
            if existing["arguments_hash"] != ah or existing["bound_action_id"] != bound.bound_action_id:
                raise ValueError("IDEMPOTENCY_KEY_CONFLICT")
            return self._result(existing, True)
        hid="hold_"+stable_hash({"action":bound.bound_action_id,"args":ah})[:20]; now=utcnow()
        self.db.execute("INSERT INTO holds VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(hid,json.dumps(args.model_dump(mode="json"),sort_keys=True),ah,args.provider,args.service,args.date,args.time,str(args.quoted_price),args.currency,args.service_location_label,"HELD",now,bound.bound_action_id,bound.idempotency_key,workflow_id)); self.db.commit()
        return self.get_hold(hid)

    def _result(self, row, duplicate=False):
        return SimulatorResult(hold_id=row["hold_id"],status=row["status"],bound_action_id=row["bound_action_id"],
            idempotency_key=row["idempotency_key"],arguments_hash=row["arguments_hash"],created_at=row["created_at"],duplicate_suppressed=duplicate)

    def get_hold(self, hold_id: str) -> SimulatorResult:
        row=self.db.execute("SELECT * FROM holds WHERE hold_id=?",(hold_id,)).fetchone()
        if not row: raise KeyError("HOLD_NOT_FOUND")
        return self._result(row)

    def cancel_hold(self, hold_id: str) -> SimulatorResult:
        self.get_hold(hold_id); self.db.execute("UPDATE holds SET status='CANCELLED' WHERE hold_id=?",(hold_id,)); self.db.commit(); return self.get_hold(hold_id)

    def append_event(self, event: WorkflowEvent) -> bool:
        try:
            self.db.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?,?)",(event.event_id,event.workflow_id,event.sequence,event.event_type,event.occurred_at,event.payload_hash,json.dumps(event.payload,sort_keys=True),event.dedupe_key)); self.db.commit(); return True
        except sqlite3.IntegrityError:
            return False

    def events(self, workflow_id: str) -> list[WorkflowEvent]:
        rows=self.db.execute("SELECT * FROM events WHERE workflow_id=? ORDER BY sequence",(workflow_id,)).fetchall()
        return [WorkflowEvent(event_id=r["event_id"],workflow_id=r["workflow_id"],sequence=r["sequence"],event_type=r["event_type"],occurred_at=r["occurred_at"],payload_hash=r["payload_hash"],payload=json.loads(r["payload_json"]),dedupe_key=r["dedupe_key"]) for r in rows]

    def hold_count(self) -> int:
        return self.db.execute("SELECT count(*) FROM holds").fetchone()[0]

    def verify_result(self, workflow_id: str, args: AppointmentArgs, bound: BoundActionRef,
                      result: SimulatorResult, activity_id: str) -> ActivityRef:
        try:
            hold=self.db.execute("SELECT * FROM holds WHERE hold_id=?",(result.hold_id,)).fetchone()
            activity=self.get_activity(activity_id)
        except KeyError as exc:
            raise ValueError("PERSISTED_ACTIVITY_MISSING") from exc
        if hold is None: raise ValueError("PERSISTED_HOLD_MISSING")
        expected={
            "workflow_id":workflow_id,"bound_action_id":bound.bound_action_id,"idempotency_key":bound.idempotency_key,
            "arguments_hash":bound.arguments_hash,"hold_id":hold["hold_id"],"status":hold["status"]}
        observed={
            "workflow_id":hold["workflow_id"],"bound_action_id":hold["bound_action_id"],"idempotency_key":hold["idempotency_key"],
            "arguments_hash":hold["arguments_hash"],"hold_id":result.hold_id,"status":result.status}
        if expected != observed: raise ValueError("PERSISTED_RESULT_BINDING_MISMATCH")
        if canonical(json.loads(hold["arguments_json"])) != canonical(args.model_dump(mode="json")):
            raise ValueError("PERSISTED_ARGUMENTS_MISMATCH")
        if result.bound_action_id != hold["bound_action_id"] or result.idempotency_key != hold["idempotency_key"] or result.arguments_hash != hold["arguments_hash"]:
            raise ValueError("CALLER_RESULT_MISMATCH")
        if activity.workflow_id != workflow_id or activity.bound_action_id != bound.bound_action_id or activity.idempotency_key != bound.idempotency_key:
            raise ValueError("PERSISTED_ACTIVITY_BINDING_MISMATCH")
        if activity.status != "COMPLETED" or activity.result_ref != result.hold_id:
            raise ValueError("ACTIVITY_NOT_COMPLETED_FOR_RESULT")
        event=self.db.execute("SELECT 1 FROM events WHERE workflow_id=? AND event_type='ACTIVITY_COMPLETED' AND json_extract(payload_json,'$.activity_id')=? AND json_extract(payload_json,'$.hold_id')=?",(workflow_id,activity_id,result.hold_id)).fetchone()
        if not event: raise ValueError("ACTIVITY_COMPLETION_EVENT_MISSING")
        return activity
