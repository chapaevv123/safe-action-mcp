from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import AppointmentArgs, BoundActionRef, SimulatorResult, WorkflowEvent, stable_hash, utcnow


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
          bound_action_id TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE);
        CREATE TABLE IF NOT EXISTS events(
          event_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, sequence INTEGER NOT NULL,
          event_type TEXT NOT NULL, occurred_at TEXT NOT NULL, payload_hash TEXT NOT NULL,
          payload_json TEXT NOT NULL, dedupe_key TEXT NOT NULL, UNIQUE(workflow_id,dedupe_key),
          UNIQUE(workflow_id,sequence));
        """)
        self.db.commit()

    def create_hold(self, args: AppointmentArgs, bound: BoundActionRef) -> SimulatorResult:
        ah=stable_hash(args)
        existing=self.db.execute("SELECT * FROM holds WHERE idempotency_key=?",(bound.idempotency_key,)).fetchone()
        if existing:
            if existing["arguments_hash"] != ah or existing["bound_action_id"] != bound.bound_action_id:
                raise ValueError("IDEMPOTENCY_KEY_CONFLICT")
            return self._result(existing, True)
        hid="hold_"+stable_hash({"action":bound.bound_action_id,"args":ah})[:20]; now=utcnow()
        self.db.execute("INSERT INTO holds VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(hid,json.dumps(args.model_dump(mode="json"),sort_keys=True),ah,args.provider,args.service,args.date,args.time,str(args.quoted_price),args.currency,args.service_location_label,"HELD",now,bound.bound_action_id,bound.idempotency_key)); self.db.commit()
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
