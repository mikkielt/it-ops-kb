---
topic: standards/owasp
priority: P2
applies_to: "OWASP Agentic Top 10 2026; OWASP MCP Top 10 (2025 beta); OWASP LLM Top 10 2025 and 2026"
retrieved_utc: 2026-09-27
sources: [S-s3hkw2h4, S761, S762, S763, S764, S765, S1540, S-mq77ii5m]
status: complete
---
# OWASP lists for agentic, MCP and LLM applications (identifiers and titles)

## Summary
Identifiers and titles only; full table in `owasp.csv`. Agentic Applications 2026 (ASI01-ASI10) published 2025-12-09.
OWASP MCP Top 10 uses `MCPnn:2025` ids and is in beta ("Phase 3"), next release planned October 2026.
LLM Top 10: both the 2025 list (LLM01-LLM10:2025) and the 2026 edition (LLM01-LLM10:2026, resource page dated
2026-08-03, PDF licensed CC BY-SA 4.0) are captured.

## Facts
- OWASP Top 10 for Agentic Applications for 2026 resource page dated December 9, 2025. [DOC S761]
- ASI01-ASI10 titles as listed in the OWASP GenAI announcement of 2025-12-09 (see csv). [DOC S762]
- OWASP MCP Top 10 ids MCP01:2025-MCP10:2025; project status "Phase 3 – Beta Release and Pilot Testing"; "Next Release in October 2026" (index.md at commit 165fe0f, main HEAD on 2026-09-27). [DOC S-s3hkw2h4]
- OWASP MCP Top 10 licence stated as CC BY-NC-SA 4.0. [DOC S-s3hkw2h4]
- OWASP Top 10 for LLM Applications 2025: LLM01:2025-LLM10:2025 (see csv). [DOC S763]
- "OWASP GenAI LLM Top 10 2026" resource page is dated August 3, 2026. [DOC S764]
- The OWASP GenAI project announced the 2026 Top 10 for LLM Applications on 2026-09-01. [DOC S765]
- OWASP Top 10 for LLM Applications 2026 (PDF, "Version 2026", cover date August 4th, 2026), in order: LLM01:2026 Prompt Injection, LLM02:2026 Sensitive Information Disclosure, LLM03:2026 Excessive Agency, LLM04:2026 Supply Chain, LLM05:2026 Data and Model Poisoning, LLM06:2026 Unbounded Consumption, LLM07:2026 Misinformation, LLM08:2026 Hidden Context Exposure, LLM09:2026 Vector and Embedding Weaknesses, LLM10:2026 Improper Output Handling. The document is licensed CC BY-SA 4.0. [DOC S-mq77ii5m]
- What changed from 2025, per the project leads' letter: Excessive Agency climbed to third, Unbounded Consumption rose four places, Improper Output Handling fell from fifth to tenth, Prompt Injection and Sensitive Information Disclosure held first and second, and System Prompt Leakage became Hidden Context Exposure, a broader entry. The ranking weights the community vote at three-quarters and incident data at one quarter. [DOC S-mq77ii5m]
- Scope boundary stated in the 2026 list: it covers the model as a component of an application; once the model acts with tools, memory and downstream consequences, the risk moves to the OWASP Agentic Top 10, and the two should be read together. [DOC S-mq77ii5m]

## Reference
See `owasp.csv` (columns: list, id, title, url, source_id).

| List | Ids | Edition captured |
|---|---|---|
| Agentic Applications | ASI01-ASI10 | 2026 |
| MCP Top 10 | MCP01:2025-MCP10:2025 | 2025 (beta) |
| LLM Applications | LLM01:2025-LLM10:2025; LLM01:2026-LLM10:2026 | 2025 and 2026 |

## Examples
Not applicable (reference list).

## Update 2026-09-24 (part security C)
- Re-checked OWASP MCP Top 10 status: still "Phase 3 – Beta Release and Pilot Testing", ids unchanged
  (`MCP01:2025`-`MCP10:2025`); the project page (re-read 2026-09-26) states no release date. [DOC S1540]
- See `security/ai-agent-guidelines.md` for a mapping of these lists to concrete controls (tiers, confirmation,
  agent device limits, a model boundary, an audit table, an MCP allowlist), tagged `DER`.
