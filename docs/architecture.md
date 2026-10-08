# Architecture

The browser sends real MCP JSON-RPC calls to one FastAPI endpoint. Protocol handling is separated from `SafetyEngine`, deterministic contracts, and `LocalStore`. The safety engine evaluates evidence and manifest trust before creating consent. Consent binds a canonical argument hash to one action and expiry. The simulator accepts only that bound action and requires its idempotency key.

SQLite contains local simulated holds and immutable workflow events. Derived workflow state is rebuilt by folding events. Replay never calls an effect when `ACTIVITY_COMPLETED` is already present. Result verification binds the hold to the approved action, then reconciliation and the receipt record what happened. Trace context references this lineage without becoming an authority.

Trust, admission, consent, execution, verification, and observability remain separate boundaries. No trace or receipt grants execution authority.
