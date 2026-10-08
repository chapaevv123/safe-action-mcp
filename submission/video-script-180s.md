# Video script — target 2:35

**0:00–0:15 — Problem**  
“AI agents can call powerful tools, but what a person approves can drift from what finally executes. Safe Action MCP makes that boundary explicit.”

**0:15–0:35 — Architecture**  
“This simulated Alexa+ client talks to a real self-hosted MCP 2025-11-25 server. Every call passes through risk metadata, evidence, freshness, exact consent, a bound action, a reversible simulator, replay, verification, and trace.”

**0:35–1:05 — Normal preparation**  
Connect. Show `initialize`, `tools/list`, and the appointment tool. Prepare an $89 heating inspection. Show the high-impact-simulated manifest, evidence checks, fresh trust decision, and exact owner consent.

**1:05–1:35 — Mutation defense**  
Click “Try +$40 mutation.” “The agent changed $89 to $129 after approval. We show the exact changed field and reject the call. A matching hash alone would be opaque; this diff is useful to the owner.”

**1:35–2:05 — Safe execution and crash**  
Execute the approved request with crash injection. “The local simulator creates one reversible hold, then the workflow crashes before finalization.” Replay. “The completed activity is reconstructed, so retry does not create a second hold.”

**2:05–2:30 — Proof**  
Show `DUPLICATE_SUPPRESSED`, result verification, `NOOP` reconciliation, trace, and decision receipt. Cancel the hold.

**2:30–2:35 — Close**  
“One simulated effect, exact consent, safe recovery, and a complete explanation. That is Safe Action MCP.”
