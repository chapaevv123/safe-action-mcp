# Public demo deployment

Safe Action MCP deploys as one Docker service: FastAPI serves both the MCP endpoint and static judge client, while SQLite uses ephemeral local storage. This avoids CORS, split-session, and multi-service failure modes. The demo requires no secrets, AWS account, payment API, provider integration, or persistent disk.

## Render Blueprint — free tier

1. Sign in to Render and choose **New → Blueprint**.
2. Connect `https://github.com/chapaevv123/safe-action-mcp`.
3. Select `render.yaml` and confirm the **Free** plan. Do not add billing or a paid disk.
4. Deploy the current `master` commit.
5. Render supplies `PORT` and `RENDER_EXTERNAL_URL`; the app uses the latter as its exact allowed browser Origin.
6. Verify `GET /health`, then run the public smoke sequence below.

The database lives at `/tmp/safe-action.db`. Free-service restarts intentionally clear demo state. Each initialized MCP session receives a cryptographically random ID, workflow IDs incorporate that session, and reset is restricted to the owning session.

## Required public smoke sequence

Page load → initialize → initialized notification → `tools/list` → prepare → approve → mutation block → approved crash → replay → one effect → trace/receipt → cancel → reset → fresh browser session.

## Environment

- `SAFE_ACTION_HOST=0.0.0.0`
- `SAFE_ACTION_DB=/tmp/safe-action.db`
- `PORT` is supplied by the provider.
- `RENDER_EXTERNAL_URL` is supplied by Render and added to the Origin allowlist.
- For another provider, set `SAFE_ACTION_PUBLIC_ORIGIN` to its exact HTTPS origin.

No public URL is recorded until a deployment has passed the smoke sequence.
