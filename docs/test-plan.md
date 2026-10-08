# Test plan

Unit tests cover serialization, validation, trust, consent and diffs. Protocol tests cover lifecycle, discovery, invocation errors, IDs, version headers, origins and UI delivery. Integration tests cover hold create/inspect/cancel, conflicting idempotency, crash replay, exactly-one effect, result binding, reconciliation, receipts and trace. The demo smoke script exercises the full MCP path against a live local server.

Critical tests may not be skipped. A release candidate requires zero failures and a clean-environment install.
