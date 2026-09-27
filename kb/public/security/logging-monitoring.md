---
topic: security/logging-monitoring
priority: P1
applies_to: "an audit table (SQL Server, temporal); normalized device logs via ConfigMgr; Claude Code OTel"
retrieved_utc: 2026-09-27
sources: [S1492, S1493, S1494, S1495, S1496, S1497, S1498, S1499, S743, S1526, S1527, S1528, S1529]
status: partial
---

# Logging and monitoring: retention guidance vs. example retention values

## Summary
CIS Controls v8.1 sets a 90-day minimum for audit-log retention (Safeguard 8.10); an audit table set to 400 days exceeds it, but a normalized device-log retention of 30 days sits **below** it — see Conflicts. NIST SP 800-92 is still the unrevised 2006 edition; a Revision 1 exists only as a 2023 draft. Microsoft's Windows audit-policy guidance recommends *what* to audit more than *how long* to keep it. AI-agent interaction logging guidance (OWASP Agentic 2026, Claude Code's own OTel events) converges on: log every tool call, its inputs/outputs and the decision path, tamper-evidently; NIST AI 600-1 frames logging more generally as provenance and incident documentation.

## Facts
- CIS Controls v8.1, Control 8 "Audit Log Management", has 12 safeguards (8.1-8.12). Safeguard **8.10, "Retain Audit Logs"**, recommends retaining audit logs across enterprise assets for a **minimum of 90 days**. [DOC S1492]
- Other Control 8 safeguards by ID and short paraphrase: 8.1 establish a log-management process; 8.2 collect audit logs; 8.3 ensure adequate log storage; 8.5 collect detailed audit logs; 8.9 centralize audit logs; 8.11 conduct audit log reviews; 8.12 collect service-provider logs. [DOC S1492]
- NIST SP 800-92, "Guide to Computer Security Log Management," remains the **2006 original** as the current, final publication. A Revision 1 (retitled "Cybersecurity Log Management Planning Guide") exists only as an **Initial Public Draft**, posted 2023-10-11 for comment, and had not been finalized as of 2026-09-24. [DOC S1493,S1494]
- Microsoft's Windows Server audit-policy recommendations (the advanced audit policy categories: account logon, account management, logon/logoff, object access, etc.) state *which* event categories to enable, but do **not state an explicit day-count retention requirement**. [DOC S1528]
- Microsoft's OSConfig Windows Server 2025 baseline guidance says the baseline hardens event log sizes and retention, with the Security log sized to at least 192 MB; it gives no retention period in days. [DOC S1529]
- That Windows event log rotation is size-based by default, not time-based. [UNK: not in S1529 as re-read 2026-09-27]
- A vendor summary (ISMS.online) describes ISO/IEC 27001:2022 Annex A control **8.15 "Logging"** as logging system events to support security, breach detection and investigations, with log protection and regular review; it supersedes the 2013 controls 12.4.1-12.4.3. It describes control **8.16 "Monitoring activities"** as proactive and reactive monitoring of IT and security operations to prevent incidents and detect anomalies, a control newly added versus the 2013 edition. Titles only; the standard's clause text is paid and not reproduced here. [COMMUNITY S1495,S1496]
- OWASP's Top 10 for Agentic Applications (2026 edition, published 2025-12-09) calls for **strong observability**: comprehensive, tamper-evident, signed audit logs of agent actions, tool-use patterns, decision pathways and inter-agent communication, for forensic analysis — paired with authentication/authorization as defense in depth, not a substitute for it. [DOC S1526]
- The OWASP GenAI LLM Top 10 index page (read 2026-09-27) still presents the 2025 list, `LLM01:2025` Prompt Injection to `LLM10:2025` Unbounded Consumption, including `LLM06:2025` Excessive Agency. [DOC S1497]
- NIST AI 600-1 (the Generative AI profile of the AI RMF, July 2024) treats logging as provenance and incident documentation rather than agent tool-call tracing: keep records of third-party changes to content with sources, timestamps and metadata (GV-6.1-008); use real-time auditing tools, where shown to help, to track the lineage and authenticity of AI-generated data (MG-2.2-007); and use logging, change-management records, version history and metadata, including documentation of third-party inputs and plugins, to support GAI incident response (Appendix A). It does not address agent tool calls specifically and mandates no log format or retention period. [DOC S1527]
- Claude Code's own OpenTelemetry integration emits structured events per action — `claude_code.api_request`, `claude_code.tool_result` among them — enabled via `CLAUDE_CODE_ENABLE_TELEMETRY` and `OTEL_LOGS_EXPORTER`, with an `OTEL_LOG_TOOL_DETAILS` flag specifically for security/audit use, in addition to hooks that can capture lifecycle events for a custom audit trail. Session transcripts are also written locally regardless of OTel configuration. [DOC S1498,S743]
- Claude Code's security page says all operations in Anthropic-hosted cloud sessions are logged for compliance and audit, and for teams recommends monitoring usage through OpenTelemetry metrics, auditing or blocking settings changes during sessions with `ConfigChange` hooks, and regularly auditing permission settings with `/permissions`. [DOC S1499]
- No single official Microsoft page specifically covering "logging Copilot/agent actions" (as distinct from general Microsoft 365/Purview audit-log collection) was found in this pass. [UNK]

## Conflicts
- **A device-log retention of 30 days is below CIS Safeguard 8.10's 90-day minimum.** Treating normalized device logs pulled via ConfigMgr as *diagnostic*, not *security*, logs is one reason a 30-day figure may not be the value CIS 8.10 is meant to constrain — but if any of that log content is later relied on for security investigation, a 30-day window falls short of the CIS baseline. [DER S1492: CIS 8.10 minimum compared against an example device-log retention]
- An audit table retention of 400 days comfortably exceeds the CIS 90-day minimum and is not in conflict with any retention figure found in this research. [DER S1492]

## Reference
| Guidance | Minimum retention or requirement | Example value | Conflict? |
|---|---|---|---|
| CIS Controls v8.1 Safeguard 8.10 | 90 days | audit table: 400 days | no |
| CIS Controls v8.1 Safeguard 8.10 | 90 days | device logs: 30 days | **yes, below minimum** |
| NIST SP 800-92 | no retention figure stated (2006 edition current; Rev.1 still draft) | n/a | n/a |
| Microsoft audit-policy guidance | no day-count; log sized ~192 MB minimum | n/a | n/a |
| ISO/IEC 27001:2022 A.8.15/8.16 | no retention figure in public summary | n/a | n/a |

## Examples
No fixture-specific configuration; these are retention-policy and log-content facts independent of device or tenant fixtures.
