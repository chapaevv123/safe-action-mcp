# Security boundary

**THIS PROJECT DOES NOT EXECUTE REAL BOOKINGS OR PAYMENTS.**

The server binds to `127.0.0.1` by default, validates browser origins, rejects missing protocol-version headers after initialization, uses strict data models, and keeps effects in local SQLite. It has no outbound booking/payment adapter, wallet code, secrets, or production authentication claim.

Tool metadata is treated as untrusted. A separate risk manifest defines material fields and simulator-only policy. Missing evidence is `INSUFFICIENT`, never admitted. Owner consent covers an exact canonical argument hash, expires, and permits one idempotent activity. Changed material arguments reject before the simulator.

The demo is not a production authorization service. Production deployment would require authenticated owner identity, TLS, secure session storage, key management, multi-tenant isolation, rate limiting, audit retention policy, and independent security review.
