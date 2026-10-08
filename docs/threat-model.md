# Threat model

| Threat | Control | Residual boundary |
|---|---|---|
| Tool metadata tampering or malicious descriptions | Separate hashed risk manifest and strict schema | Manifest issuer authentication is demo-local |
| Manifest rollback, expiry, or same-version conflict | Version, freshness, integrity, rollback and conflict checks | No remote authority service |
| Stale or replayed consent | Expiry, session/tool/argument scope, one invocation | Demo owner identity is a label |
| Argument drift | Canonical hash plus human-readable material-field diff | Non-material note is not execution-authoritative |
| Duplicate execution after retry | Mandatory idempotency key and completed `ActivityRef` | SQLite is single-node |
| Crash between effect and finalization | Append-only events and deterministic replay | OS-level disk loss is out of scope |
| Forged/orphaned result | Result-to-bound-action/activity/hold verification | No external attestation |
| Trace confusion | Explicit parent and workflow references; trace is non-authoritative | UI is a projection |
| Event replay abuse or corruption | Dedupe keys and monotonic sequence checks | No cryptographic event log signature |
| Idempotency collision/conflicting reuse | Stable action-derived key and argument conflict rejection | SHA-256 assumptions apply |
| Origin abuse | Explicit allowlist and localhost default | Production authentication is deferred |
| Simulator-to-real confusion | Persistent UI and docs disclaimers; no external adapter exists | Forks may change code and must reassess safety |
