# Safe Action MCP

AI agents increasingly discover and call tools, but a human's approval can drift from the arguments that reach execution. Safe Action MCP governs that boundary.

Our custom Alexa+-style web client connects to a real self-hosted MCP `2025-11-25` server over Streamable HTTP. It discovers a simulated appointment-hold tool and displays its risk manifest. Evidence and freshness checks must pass before the owner can approve the exact provider, service, date, time, price, currency, and location.

If an agent changes the approved price or time, Safe Action MCP explains the changed field and rejects the invocation. The approved call creates one reversible local SQLite hold. We then inject a crash after that effect but before workflow finalization. Deterministic replay recognizes the completed activity and suppresses a duplicate hold. The result is bound back to the approved action, reconciled, traced, and recorded in a decision receipt.

This is not a booking product or generic MCP wrapper. It is an execution control plane for consequential agent tools. The same pattern can protect purchases, account changes, access grants, and internal operations. The demo has no external provider integration, no payment, no wallet, and no irreversible effect.
