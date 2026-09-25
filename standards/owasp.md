---
topic: standards/owasp
priority: P2
applies_to: "OWASP Agentic Top 10 2026; OWASP MCP Top 10 (2025 beta); OWASP LLM Top 10 2025 (2026 edition exists, items not captured)"
retrieved_utc: 2026-09-23
sources: [S760, S761, S762, S763, S764, S765]
status: partial
---
# OWASP lists for agentic, MCP and LLM applications (identifiers and titles)

## Summary
Identifiers and titles only; full table in `owasp.csv`. Agentic Applications 2026 (ASI01-ASI10) published 2025-12-09.
OWASP MCP Top 10 uses `MCPnn:2025` ids and is in beta ("Phase 3"), next release planned October 2026.
LLM Top 10: the 2025 list (LLM01-LLM10:2025) was captured; a 2026 edition was published 2026-08-03, but its item
identifiers and titles were not in the HTML pages fetched.

## Facts
- OWASP Top 10 for Agentic Applications for 2026 resource page dated December 9, 2025. [DOC S761]
- ASI01-ASI10 titles as listed in the OWASP GenAI announcement of 2025-12-09 (see csv). [DOC S762]
- OWASP MCP Top 10 ids MCP01:2025-MCP10:2025; project status "Phase 3 – Beta Release and Pilot Testing"; "Next Release in October 2026". [DOC S760]
- OWASP MCP Top 10 licence stated as CC BY-NC-SA 4.0. [DOC S760]
- OWASP Top 10 for LLM Applications 2025: LLM01:2025-LLM10:2025 (see csv). [DOC S763]
- "OWASP GenAI LLM Top 10 2026" resource page is dated August 3, 2026. [DOC S764]
- The OWASP GenAI project announced the 2026 Top 10 for LLM Applications on 2026-09-01. [DOC S765]
- LLM Top 10 2026 identifiers and titles: not present in the fetched HTML (list is in the PDF). [UNK]

## Reference
See `owasp.csv` (columns: list, id, title, url, source_id).

| List | Ids | Edition captured |
|---|---|---|
| Agentic Applications | ASI01-ASI10 | 2026 |
| MCP Top 10 | MCP01:2025-MCP10:2025 | 2025 (beta) |
| LLM Applications | LLM01:2025-LLM10:2025 | 2025 (2026 exists, not captured) |

## Examples
Not applicable (reference list).

## Update 2026-09-24 (part security C)
- Re-checked OWASP MCP Top 10 status: still "Phase 3 – Beta Release and Pilot Testing", ids unchanged
  (`MCP01:2025`-`MCP10:2025`), next release planned October 2026 — consistent with the facts above. [DOC S1540]
- See `security/ai-agent-guidelines.md` for a mapping of these lists to concrete controls (tiers, confirmation,
  agent device limits, a model boundary, an audit table, an MCP allowlist), tagged `DER`.
