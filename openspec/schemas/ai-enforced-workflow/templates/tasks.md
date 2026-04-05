## 1. <!-- Task Group Name -->

- [ ] 1.1 <!-- Task description -->
- [ ] 1.2 <!-- For STANDARD/STRICT independent verify: reference shared sequence `verify-sequence/default`, declare minimal bundle (`change/mode/risk_tier/evidence_paths_or_diff_scope/findings_contract/retry_policy`), require verifier invocation via built-in subagent API using template id `verify-reviewer-inline-v1`, authoritative verifier-subagent findings JSON path, verifier execution evidence JSON path, Gemini policy (`STRICT` or explicit dual gate), runner contract `gemini-capture`, raw/report paths, fallback (`input_raw_path -> report_path`), originating phase (`artifact_gate|apply|implementation_verify`), continuation target, routing target, supported continuation overrides (`verify-only|dry-run|manual_pause`), and skill entry point -->
- [ ] 1.3 [Checkpoint] Run verifier-subagent review for <!-- schema diff / skill output / verification report --> using `verify-sequence/default`; write authoritative verifier-subagent findings JSON and verifier execution evidence JSON, and ensure each rerun uses a fresh verifier instance (no inherited memory). If Gemini is required by risk tier or explicit dual gate, run logical runner contract `gemini-capture`, write both raw and normalized reports, and if primary execution fails after writing raw, run recovery (`input_raw_path -> report_path`) before blocking. Record verifier invocation metadata (`agent_id/start_at/end_at/final_state`) and Gemini resolved Linux/Windows command (when Gemini runs) in execution evidence, not in task policy prose. Only `verify-only`, `dry-run`, and `manual_pause` may override automatic continuation.

## 2. <!-- Task Group Name -->

- [ ] 2.1 <!-- Task description -->
- [ ] 2.2 <!-- Task description -->
