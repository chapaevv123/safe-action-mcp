# Friction log

| Date | Task | Expected | Actual | Severity | Workaround | Suggestion |
|---|---|---|---|---|---|---|
| 2026-10-08 | Interpret Streamable HTTP minimum | A small explicit server compliance profile | The specification supports JSON or SSE responses while the event requires Streamable HTTP, leaving first-time builders to assemble the minimum across lifecycle, transport, and tools pages | LOW | Implement POST JSON and explicit GET 405, with a real initialize/list/call client | Publish an Alexa+ hackathon conformance checklist and example transcript |
| 2026-10-08 | Local Python bootstrap | Standard Windows `py` launcher available | `py` was absent on the build machine | LOW | Used an existing Python executable to create an isolated project virtual environment | Document both `python` and `py` setup variants |
| 2026-10-08 | Test-client dependency warning | Compatible test client without warnings | Current FastAPI/Starlette emits an `httpx` deprecation warning | LOW | Tests remain deterministic; pinned compatible major ranges | Publish a tested dependency matrix for samples |
| 2026-10-08 | Default demo port | Port 8765 available | Another local process already owned the port | LOW | Exercised the documented environment override on port 8877 | Examples should show a one-line port override |
