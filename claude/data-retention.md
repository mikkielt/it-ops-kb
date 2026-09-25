---
topic: claude/data-retention
priority: P1
applies_to: "Claude Code docs and Claude API retention page (retrieved 2026-09-23)"
retrieved_utc: 2026-09-23
sources: [S747, S748, S749]
status: partial
---
# Claude data retention and ZDR scope per surface

## Summary
Commercial (Team, Enterprise, API): 30-day standard retention. Consumer: 5 years if model-improvement use allowed,
else 30 days. ZDR is per organization, enabled by Anthropic for qualified accounts; for Claude Code it covers
inference on Claude for Enterprise with ZDR and API keys from a Commercial organization; it does not cover claude.ai
chat, Cowork, analytics metadata, or data processed by MCP servers. Local transcripts stay 30 days by default.

## Facts
- Consumer (Free/Pro/Max): 5-year retention if data use for model improvement is allowed, 30 days otherwise. [DOC S747]
- Commercial (Team, Enterprise, API): standard 30-day retention. [DOC S747]
- Claude Code stores transcripts locally in plaintext under `~/.claude/projects/` for 30 days by default (`cleanupPeriodDays`). [DOC S747]
- `/feedback`, `/bug`, `/share` transcripts are retained for 5 years. [DOC S747]
- ZDR for Claude Code: available to qualified accounts on Claude for Enterprise; not in the standard plan; enabled per organization by Anthropic; new organizations need separate enablement. [DOC S748]
- ZDR for Claude Code applies only to Anthropic's direct platform; Bedrock/Vertex (Agent Platform)/Foundry follow their own policies. [DOC S748]
- ZDR applies to requests authenticating into the ZDR organization; personal accounts or other-org API keys are not covered (`forceLoginMethod`, `forceLoginOrgUUID` enforce login org). [DOC S748]
- Not covered by ZDR: claude.ai chat, Cowork, Claude Code Analytics metadata, user/seat admin data, and data processed by third-party tools or MCP servers. [DOC S748]
- Disabled under ZDR: cloud sessions, Claude Tag, Artifacts, feedback submission, Remote Control. [DOC S748]
- Under ZDR, flagged policy-violation sessions may be retained up to 2 years. [DOC S748]
- API page: ZDR covers Messages and Token Counting APIs for eligible features, Claude Code with API keys from a Commercial organization or Claude Enterprise with ZDR, and Claude Platform on AWS on request. [DOC S749]
- API page: Claude Teams and Enterprise product interfaces are not ZDR-eligible (except Claude Code via Enterprise with ZDR); Claude for Excel not eligible. [DOC S749]
- Covered Models (Fable 5.1, Mythos 5.1, Fable 5, Mythos 5) require 30-day retention and are not available under ZDR unless expressly authorized. [DOC S749]
- Under ZDR the API does not block non-eligible features; using one steps outside ZDR for that data. [DOC S749]
- privacy.claude.com / support.claude.com pages for consumer/commercial terms were not fetched in this pass. [UNK]

## Reference
| Surface | Standard retention | ZDR possible |
|---|---|---|
| Claude API (first party) | 30 days (commercial) | yes, per org, eligible features |
| Claude Code, Enterprise org | 30 days | yes, qualified accounts, per org |
| Claude Code, Commercial API key | 30 days | yes (API page) |
| Claude Code on Bedrock/Agent Platform/Foundry | provider policy | provider policy |
| claude.ai chat (Team/Enterprise) | 30 days | no |
| Cowork | standard | no |
| Consumer plans | 30 days or 5 years | no |
| Local transcripts | 30 days local | n/a |

## Examples
A jan.kowalski session signed in to a non-ZDR personal account on PL-LT-00123 is not covered by the organization's ZDR. [DER S748: ZDR applies only to requests authenticating into the ZDR org]
