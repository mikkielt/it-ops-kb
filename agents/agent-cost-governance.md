---
topic: agents/agent-cost-governance
priority: P2
applies_to: "Claude Code docs (code.claude.com, retrieved 2026-09-25); Anthropic Usage & Cost Admin API (platform.claude.com, retrieved 2026-09-25)"
retrieved_utc: 2026-09-25
sources: [S2013, S2132]
status: complete
---

# Cost governance for a team using Claude Code

## Summary
Anthropic publishes an enterprise cost baseline (~$13/developer/active-day, $150-250/developer/month, <$30/active-
day for 90% of users) and per-team-size TPM/RPM recommendations that shrink as headcount grows. Managed settings
(`modelPricing`) let contracted rates replace list-price estimates in `/usage` and telemetry. Visibility and spend
caps differ by purchase path (Teams/Enterprise seat allowance vs. Console workspace limits vs. cloud-provider
billing), with OpenTelemetry export as the one path available on every setup. The Admin Usage & Cost API gives
token/cost data by model/workspace/key at up to per-minute granularity; per-user Claude Code cost is better served
by the separate Claude Code Analytics API. Attribution is per MCP *server*, not per tool within a server — a gap
for any team running a multi-operation MCP tool set that wants per-operation cost.

## Facts
- Published baseline: ~$13/developer/active-day, $150-250/developer/month; <$30/active-day for 90% of users.
  [DOC S2132]
- `modelPricing` (managed-settings-only key, Claude Code v2.1.242+) rewrites the price basis used by `/usage`, the
  status line, and OTel cost figures to an org's contracted rates (`multiplier` and/or per-model `overrides`); a
  markup (`multiplier`>1) requires v2.1.271+; the setting changes reporting only, not Anthropic's actual charge.
  [DOC S2132]
- TPM/RPM per-user recommendations fall as team size grows (fewer users are concurrently active in larger teams):
  200-300k TPM / 5-7 RPM per user at 1-5 users, down to 10-15k TPM / 0.25-0.35 RPM per user at 500+ users. [DOC
  S2132]
- Three purchase paths differ in visibility/caps: (a) Claude for Teams/Enterprise — per-seat allowance on a rolling
  5-hour + weekly window, daily spend-report CSV, adoption dashboard, and for Enterprise the Enterprise Analytics
  API (`read:analytics` scope) for per-user usage/cost; (b) Claude Console (API) — workspace spend limits, workspace
  rate limits, Console usage/cost pages, and the Claude Code Analytics API (Admin API key) for daily per-user
  metrics; (c) cloud providers (Bedrock, Google Cloud Agent Platform, Microsoft Foundry) — billed to the cloud
  account with no Anthropic-side dashboard; per-user attribution there requires OpenTelemetry export, a self-hosted
  "Claude apps gateway," or a third-party LLM gateway (e.g. LiteLLM, unaffiliated with Anthropic, not security-
  audited). OpenTelemetry export is stated to be "the only option" giving per-user token/cost metrics in near real
  time on every setup. [DOC S2132]
- Admin Usage & Cost API (`platform.claude.com`, Admin API key or `org:admin` OAuth scope; workspace-scoped keys
  do not work): `/v1/organizations/usage_report/messages` returns token counts groupable by model, workspace, API
  key, service tier, context window, data residency (`inference_geo`), or speed; bucket widths `1m` (up to 1,440
  buckets), `1h` (up to 168), `1d` (up to 31). `/v1/organizations/cost_report` returns USD cost by workspace or
  description, daily buckets only; Priority Tier billing is excluded from the cost endpoint (tracked via the usage
  endpoint's `service_tier` instead). Data lands within ~5 minutes of the API call; sustained polling of once per
  minute is supported. Claude Enterprise orgs use a separate Analytics API key instead of an Admin API key for the
  equivalent Enterprise Analytics API. [DOC S2013]
- Per-user Claude Code cost specifically: the docs recommend the dedicated Claude Code Analytics API over slicing
  the general Usage API by many API keys, "without the performance limitations of breaking down costs by many API
  keys." [DOC S2013]
- Model-choice cost guidance: default to Sonnet for coding, reserve Opus for complex architecture/reasoning;
  subagents can be pinned to a cheaper model independently (e.g. `model: haiku`); multi-instance "agent teams" use
  roughly 7x more tokens than a standard session when teammates run in plan mode, because each teammate holds its
  own context window; agent teams are opt-in (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`). [DOC S2132]
- `/usage`'s attribution breakdown covers skills, subagents, plugins, and MCP servers — but attribution is per MCP
  *server*, not per individual tool inside a server (a server's share counts requests that consumed any one of its
  tool results). [DOC S2132; gap: no per-tool attribution documented, see `gaps.md`]

## Reference
| Purchase path | See spend | Cap spend | Per-user reporting |
|---|---|---|---|
| Teams/Enterprise | org analytics spend report (CSV, daily) | admin spend limits (org/group/member) | Enterprise Analytics API / Teams CSV |
| Claude Console (API) | Console usage/cost pages | workspace spend + rate limits | Claude Code Analytics API |
| Cloud provider (Bedrock/Vertex/Foundry) | cloud billing console | cloud budget controls | OpenTelemetry export / apps gateway / LLM gateway |

Each teammate or subagent is a separate Claude Code request stream billed the same way as the main session; see
`claude/skills-and-subagents.md` for how subagents and agent teams are configured and spawned (frontmatter fields,
model-selection order, agent-teams token cost being "significantly more" than a single session).

## Examples
A team of 20-30 engineers running Claude Code as their CLI front end would sit in the
"5-20 users" TPM/RPM band (100-150k TPM, 2.5-3.5 RPM per user) per Anthropic's published sizing table. For a
system whose policy runs each instance on the engineer's own workstation rather than through a shared gateway,
per-engineer cost attribution has to come from each engineer's own Claude Console/Enterprise account reporting,
not from a central mechanism [DER S2132].

### General implication
A "no always-on service, no container, no broker" policy rules out a central LLM gateway as the cost-attribution
mechanism; the compatible paths are each engineer's own Claude Console/Enterprise reporting, or OpenTelemetry
export from the workstation (compatible with a "logs as JSON lines on stderr" model). Cost governance is
therefore an organizational Claude Code admin concern, not something the tool itself needs to own.
