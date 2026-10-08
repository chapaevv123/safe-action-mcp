# Safe Action MCP

> A self-hosted Alexa+ MCP execution firewall that binds high-impact tool calls to fresh evidence, exact owner consent, deterministic replay, and inspectable outcomes.

**Hackathon:** Amazon Build, Ship, Shape — Alexa+ track

**Repository:** https://github.com/chapaevv123/safe-action-mcp

**Public demo:** Pending free-host deployment and public smoke verification.

This is an **Alexa+-style simulated experience for the Amazon Developer Hackathon**. It is not an official Amazon or Alexa+ product and does not claim access to gated Alexa+ preview tooling.

Safe Action MCP addresses the gap between what a person approved and what an AI agent eventually sends to a tool. It demonstrates one consequential but harmless operation: a **simulated paid home-service appointment hold**. It never contacts a provider, books an appointment, or transfers money.

## The demo

The browser is a real MCP client. It initializes MCP `2025-11-25`, discovers `hold_service_appointment`, validates a versioned risk manifest, shows the exact material arguments, and binds one owner approval to those arguments. A changed price is rejected with a field-level explanation. The approved call creates one local SQLite hold; an injected crash occurs immediately afterward. Replay observes the completed activity, suppresses a duplicate effect, verifies the result, reconciles desired and observed state, and emits a traceable decision receipt.

### Judge flow

Click **Run demo · connect MCP**, then follow the numbered buttons: prepare, approve, mutate price, execute with crash, replay, and inspect the trace. The visible effect counter must remain at one. See the [60-second judge guide](docs/judge-quick-start.md).

## Architecture

```text
Web MCP client
  → Streamable HTTP / JSON-RPC 2.0
  → risk manifest → evidence → trust
  → exact consent → bound action
  → local reversible simulator
  → append-only workflow replay
  → result verification → reconciliation
  → trace + decision receipt
```

See [architecture](docs/architecture.md), [security boundary](docs/security.md), and [threat model](docs/threat-model.md).

## Why Alexa+

Voice and agentic interfaces make actions convenient, but a short conversation can hide consequential details. Safe Action MCP makes the exact tool, price, provider, time, currency, and location visible and consent-bound while retaining a natural Alexa-style flow. This is a self-hosted MCP submission and does not claim access to gated Alexa+ preview tooling.

## MCP compliance

- Protocol version `2025-11-25`
- JSON-RPC 2.0 over Streamable HTTP
- `initialize` and `notifications/initialized`
- `tools/list` and `tools/call`
- Request ID correlation and separate protocol/tool errors
- `MCP-Protocol-Version` enforcement after initialization
- Origin validation and localhost binding by default
- JSON Schema input contract

GET `/mcp` deliberately returns 405 because SSE streaming is unnecessary for this bounded demo.

## Run locally

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m safe_action_mcp.app
```

Open `http://127.0.0.1:8765`. Follow the numbered controls from Connect through Replay, then optionally cancel the simulated hold.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts\demo_smoke.py
```

The suite covers models, protocol behavior, security gates, manifest trust, exact consent, field-level mutation, SQLite idempotency, crash replay, duplicate suppression, result binding, reconciliation, UI delivery, and submission assets.

Current audited baseline: **71/71 tests passing** at commit `f2283c73af7a26808ac09a5dbd69699bb8e8e28b`. Deployment work adds additional regression coverage and must preserve that baseline.

## Public deployment

The repository includes a provider-neutral `Dockerfile` and a free-tier `render.yaml`. FastAPI serves the client and MCP endpoint from one origin; ephemeral SQLite keeps the public demo reversible and disposable. See [deployment instructions](docs/deployment.md). The verified URL will be inserted here only after deployment succeeds.

## Safety boundary

**THIS PROJECT DOES NOT EXECUTE REAL BOOKINGS OR PAYMENTS.** It contains no provider adapter, payment adapter, wallet integration, credentials, outbound HTTP client, or autonomous repair action. Effects are reversible rows in a local SQLite database.

## Capability transfer

The project adapts independently implemented control patterns validated in Pulse: evidence contracts/admission, release trust, decision receipts, exact action binding, durable workflows, activity references, trace context, and reconciliation. It adds MCP risk manifests, scoped consent, materiality diffs, a reversible simulator, and result-to-action verification. No private Pulse code, configuration, credentials, or authoritative production state is included. See [capability transfer](docs/capability-transfer.md).

## Judging alignment

The working MCP integration, explainable consent UX, visible adversarial rejection, crash-safe replay, and broad applicability map directly to technical implementation, design, impact, and quality of idea. See [judging map](docs/judging-map.md).

## Media

- Screenshot: `screenshots/demo-main.png` *(capture during video preparation)*
- Video: `VIDEO_URL_PENDING`
- Devpost: `DEVPOST_URL_PENDING`

## License

MIT
