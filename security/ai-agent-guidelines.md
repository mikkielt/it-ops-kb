---
topic: security/ai-agent-guidelines
priority: P2
applies_to: "OWASP GenAI 2025-2026 lists; NIST AI RMF 1.0 / AI 600-1; MITRE ATLAS; ISO/IEC 42001:2023; Claude Code / MCP current; a tool-using agent with a tiered confirm gate, a model boundary and an audit table"
retrieved_utc: 2026-09-24
sources: [S760, S761, S762, S763, S764, S765, S1540, S1541, S1542, S1543, S1544, S1545, S1862, S1547, S1548, S1575]
status: partial
---

# AI-agent and MCP security guidelines, mapped to representative controls

## Summary
Identifiers for the OWASP Agentic/LLM/MCP lists are already captured in `standards/owasp.md`; this file adds
NIST AI RMF/600-1, MITRE ATLAS, ISO/IEC 42001 metadata, Microsoft/Anthropic agent-security guidance, and maps
each item to a concrete control example for a tool-using agent (tags `DER`). The OWASP MCP Top 10 is still beta
(`MCP01:2025`-`MCP10:2025`, phase 3, next release planned October 2026) [DOC S1540] — matches `standards/owasp.md`.
Control examples referenced: a risk-tier scheme, always-confirm at the higher tiers, per-role device limits, a
model boundary (a pseudonymization vault with a short TTL and strict restore), an audit table, and an MCP-server
allowlist.

## Facts
- NIST AI RMF 1.0 was published 2023-01-26; it defines four functions (Govern, Map, Measure, Manage) and is public domain as a US government work. [DOC S1541]
- NIST AI 600-1 (Generative AI Profile) was published 2024-07 and lists suggested actions organized under the RMF functions, including "maintain human oversight of AI-enabled decisions" and "establish incident response processes for GAI-specific risks." [DOC S1542]
- NIST AI 600-1 actions relevant to a tool-using agent operating on production systems: restrict and monitor tool/plugin access granted to the model, log agent actions and their outcomes, apply least-privilege to any credentials the agent can reach, and require human review before consequential actions. [DER S1542: read against a generic tier/confirm design]
- MITRE ATLAS catalogs adversarial-ML and AI-system tactics/techniques (its own matrix, separate from enterprise ATT&CK); it is maintained by MITRE with attribution required for reuse. [DOC S1543]
- ISO/IEC 42001:2023 is a management-system standard ("Information technology — Artificial intelligence — Management system") that an organization can certify against; full text is paid, only scope/title are public. [DOC S1544]
- Microsoft's Zero Trust guidance for AI workloads recommends identity-scoped access for agents, data-boundary controls between the model and sensitive stores, and monitoring of agent-issued calls. [DOC S1545]
- Claude Code's MCP documentation points organizations needing central control to managed MCP configuration: a fixed, exclusive server set via `managed-mcp.json`, servers provided to every user via `managedMcpServers`, and `allowedMcpServers`/`deniedMcpServers` filtering, distinct from servers users add at local, project or user scope. [DOC S1862]
- Claude Code's security documentation describes permission modes and confirmation prompts for tool calls, which is the same class of control a tiered confirm gate provides for higher-risk actions. [DOC S1547]
- Anthropic introduced MCP (2024-11-25) as an open protocol so that AI applications can connect to external tools and data through a single interface; the design separates the tool-calling client from the tools themselves, which is the boundary a workstation CLI/MCP role sits on. [DOC S1548]
- Microsoft's ConfigMgr security best-practices documentation recommends restricting AdminService, CMPivot and Run Scripts to least-privilege roles and enabling audit logging for administrative actions — the same source referenced in `security/management-plane-hardening.md` (part B). [DOC S1575]

### Mapping to representative controls
- OWASP LLM06:2025 Excessive Agency / ASI02 Tool Misuse → a risk-tier table that restricts what an MCP call may do without confirmation, with the higher tiers always confirmed regardless of caller. [DER S763,S762: OWASP items describe unchecked agent action; a tier/confirm gate is the corresponding control]
- OWASP MCP07:2025 Insufficient Authentication & Authorization / ASI03 Identity & Privilege Abuse → using the engineer's own Kerberos/delegated identity for interactive calls, and narrowing agent-driven device limits below human ones in the tier configuration. [DER S1540,S762]
- OWASP MCP09:2025 Shadow MCP Servers → an MCP-server allowlist (such as Claude Code's `managed-mcp.json`) restricting which MCP server binary may run, with deny rules for any invoke-style tool that could reach unreviewed servers. [DER S1540,S1862]
- OWASP LLM02:2025 Sensitive Information Disclosure / MCP10:2025 Context Injection & Over-Sharing → a model boundary: a pseudonymization step (e.g. Presidio) before the model sees data, a short-TTL vault, and a strict restore (unknown placeholders refuse the call). [DER S763,S1540: a generic model-boundary design]
- OWASP MCP08:2025 Lack of Audit and Telemetry → every call writes an audit row (principal, tool, operation, tier, decision, targets, result) with a long retention period. [DER S1540]
- NIST AI 600-1 "restrict tool access, log outcomes, require human review" → a tier ≥2 confirm gate plus an audit table. [DER S1542]

## Reference
See `owasp.csv` (existing, `standards/`) for OWASP list ids/titles; not duplicated here.

`agents/windows-agentic-platform.md` — Windows-specific implementation of agent containment (Copilot Actions
agent accounts, agent workspace isolation, MCP-server containment via the on-device agent registry).

| Framework | Item(s) | Control example | Tag |
|---|---|---|---|
| NIST AI 600-1 | tool-access restriction, human review | tier ≥2 confirm gate | DER |
| NIST AI 600-1 | logging of agent actions | audit table (long retention) | DER |
| OWASP MCP Top 10 (beta) | MCP07, MCP09 | engineer identity + MCP-server allowlist | DER |
| OWASP LLM/Agentic 2025-2026 | LLM02, LLM06, ASI02, ASI03 | pseudonymization model boundary, tier table | DER |
| MITRE ATLAS | (catalog, not itemized here) | out of scope for a tool with no model training/serving | DER |
| ISO/IEC 42001 | management-system scope | not adopted; noted for future evidence mapping only | UNK |

## Examples
An MCP call `logs.collect` for device `PL-LT-00123` is tier 2: it is always confirmed and limited to a lower device
count when invoked by an agent than when invoked directly by `jan.kowalski`, per a representative tier table.
