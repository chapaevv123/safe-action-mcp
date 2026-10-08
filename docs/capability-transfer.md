# Capability transfer

Safe Action MCP independently adapts eleven Pulse-validated patterns: `EvidenceContract`, `EvidenceValidationResult`, `EvidenceAdmissionResult`, `ReleaseTrustDecision`, `DecisionReceipt`, `BoundActionRef`, `DurableWorkflowState`, `WorkflowEvent`, `ActivityRef`, `PulseTraceContext`, and `ReconcileDecision`.

The target implementation is reference-oriented and non-authoritative: evidence does not execute, a receipt does not approve, trace context does not redefine identity, replay performs no effects, and reconciliation cannot repair state. The project-specific adapters are MCP tool policy, demo owner consent, and the reversible appointment simulator.

New target capabilities are `MCPToolRiskManifest`, `CapabilityScopedConsent`, `ToolArgumentMaterialityDiff`, `ReversibleToolSimulator`, and `MCPResultBoundActionVerifier`.

Status: implemented and tested in target. Real hackathon use, reuse, and proven maturity remain pending owner publication/submission and Evolution Core review.
