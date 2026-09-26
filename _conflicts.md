# Conflicts (both sources linked)

Merged from `_parts/<agent>/conflicts.md`.

## agents-a2a-cache

- **Anthropic cache-read price multiplier for the newest model tier.** `platform.claude.com/docs/en/build-with-claude/prompt-caching` (S2130) states a range of "0.05x-0.025x" base input price for "Claude Opus 5.5, Fable 5.1, Mythos 5.1" reads, distinct from "0.1x" for other models. The same page's own worked example for Opus 5.5 computes cache read at "$0.20/MTok" against a "$4/MTok" base input, which is exactly 0.05x, not the lower bound of the stated range (0.025x). `platform.claude.com/docs/en/about-claude/pricing` (S2131) was fetched to cross-check but the exact per-model read multiplier was not independently re-extracted from it in this session. Recorded here rather than resolved; a task that needs the exact number should re-fetch S2131 directly for the model in question. [DOC S2130 vs itself; S2131 unconfirmed] (topic: agents/agent-caching)
- **A2A v1.0.0 timeline vs Linux Foundation transfer date.** The Linux Foundation press release (S2123) dates the protocol's transfer to Linux Foundation governance at 2025-06-23, describing it then as the "Agent2Agent Protocol Project." The spec site (S2120), fetched in 2026, references a 2026-08-27 post titled "A2A joins the Agentic AI Foundation," which reads as a distinct, later governance event or rename not described in S2123. Whether "Agentic AI Foundation" is the same body as the original Agent2Agent Protocol Project under a new name, a sibling foundation, or an unrelated grouping was not resolved (see gaps.md). [DOC S2120 vs S2123, unresolved]

## agents-authz

- **MCP authorization spec: scope-selection strategy is new since the pinned 2026-07-28 revision.** `mcp/authorization.md` (S707) reflects the 2026-07-28 revision (DCR deprecation, `iss` validation, CIMD) and does not mention a `WWW-Authenticate: scope=` challenge, `scopes_supported` least-privilege guidance, or the step-up authorization flow. The draft revision fetched for this part (S2045) adds all three. Not a contradiction — S2045 is a **later draft** than S707's pinned revision — but a reader of `mcp/authorization.md` alone would not know per-scope/per-tool authorization exists at all in the spec lineage. Recorded here rather than edited into `mcp/authorization.md` (not this agent's file to edit). [DOC S707, S2045]
- **PIM-for-Groups latency: two different numbers for two different things, easily conflated.** S1282 (prior pass) states the PIM active-assignment write itself is "within seconds." S2052 (this pass, same Microsoft product surface) states downstream SCIM provisioning of that membership into an application takes "2-10 minutes" for the first five activations per 10 seconds, else 40 minutes. Not a contradiction — they measure different steps of the same activation — but a reader citing only one page would get an incomplete and potentially wrong latency estimate for "how long until PIM activation takes effect," since the answer depends on which consumer (Entra role engine vs a SCIM-provisioned app vs a token-caching client) is asked. [DOC S1282, S2052] (topic: agents/agent-rbac)
- **GitLab PAT maximum lifetime**: this part's WebFetch summary of S2046 states the 400-day maximum "extended... in GitLab 17.6 (feature flag controlled)"; a separate, unrelated data-retention policy can independently specify keeping temporal history for "400 days". No actual disagreement between sources — noted only because the same number (400) can appear in two unrelated contexts and a future reader should not conflate them. (topic: agents/api-tokens-issue-and-store)

## agents-copilot

### Billing unit: "messages" vs "Copilot Credits"

Older Copilot Studio pages (release-plan archive S1967, some Q&A/troubleshooting pages found in search)
describe usage in *messages* and *message packs*. The current billing page (S1961, ms.date
2026-08-03) states: "Starting on September 1, 2025, the common currency for agents changed from
*messages* to Copilot Credits. There's no change in the quantity per prepaid pack or to the
pay-as-you-go rate." This is not a contradiction — S1961 is the vendor's own note that the unit
was renamed, and the quotas page (S1960) still uses "prepaid message packs" as the capacity-tier
label even while credits are the billed unit. Treat "message pack" as the tier name and "Copilot
Credit" as the metered unit; both are current per S1960/S1961. [DOC S1960, S1961]

### MCP transport support

S1964 (ms.date 2026-05-28) states Copilot Studio "supports the Streamable transport type" and "no
longer supports SSE for MCP after August 2025." No conflicting page was found; this is included
here only because a search snippet independently surfaced the same claim, confirming it is not a
one-off wording accident. [DOC S1964]

No other direct factual conflicts between official sources were found in this part's source set.

## agents-errors

### Resolved: the "~40KB CLAUDE.md warning" was a misattribution, not a live conflict
The first pass of this part recorded a COMMUNITY/UNK claim that Claude Code warns at roughly 40KB for `CLAUDE.md`.
Directly fetching `code.claude.com/docs/en/memory` in this deepening pass finds no such number anywhere in the
official docs: the documented mechanism is a 200-line soft target ("Files over 200 lines consume more context and
may reduce adherence") and a 4 MiB hard skip threshold, plus a *separate* 200-line/25KB read window that applies only
to the auto-generated `MEMORY.md`, not `CLAUDE.md`. The two-part gate (line-count target vs. flat KB warning) means
the earlier community claim likely conflated `MEMORY.md`'s limit with `CLAUDE.md`'s. Not a DOC-vs-DOC conflict — the
community claim never had a first-party source — but recorded here so a future session does not re-cite the 40KB
figure. See `agents/instruction-and-context-limits.csv` (superseded row retained for the audit trail) and S1863.

### Copilot Studio instructions limit: documented 8,000-character field cap vs. observed lower effective ceiling
Microsoft's own product surfaces present agent/generative-answer-node instructions as capped at 8,000 characters per
field [COMMUNITY S1841, S1843 — these are Microsoft Community Hub / community-digest sources, not a directly fetched
learn.microsoft.com instructions-limit page, so this is not yet a confirmed DOC-vs-DOC conflict]. A community report
(S1843) describes agents failing at combined lengths well under any single field's 8,000-character cap, via
`OpenAIAdditionalInstructionsLengthExceededLimit`, because the limit that actually fires is on the *combined* prompt
sent to the underlying model, not on any one field. This is not a contradiction between two official statements (no
second official statement was fetched), but it is a documented-vs-observed gap worth flagging: an author who stays
under the visible 8,000-character counter can still hit a hard failure. Recorded as a conflict-shaped finding rather
than a strict DOC/DOC conflict, since one side (the internal threshold) has no official page describing its exact
value.

### GitHub Copilot custom-instructions limit: "silently ignored" (docs) vs. "no limit now" (changelog) are not in
tension — sequential, not contradictory
The removal of the 4,000-character limit (S1852, dated 2026-06-12) supersedes the earlier documented behavior (S1851
describes the pre-removal silent-truncation behavior). Not a conflict, but flagged because a session reading only the
older cached version of S1851 could believe the limit still applies; both sources' dates should be checked before
citing GitHub Copilot's instructions handling. (topic: agents/instruction-and-context-limits)

## agents-eval

### OpenAI evals: framework vs. hosted platform lifecycle
`developers.openai.com/api/docs/guides/evaluation-best-practices` (S1894), read on 2026-09-25, states the
hosted Evals **platform** goes read-only 2026-10-31 and shuts down 2026-11-30, while the open-source
`openai/evals` **repository** (S1893) shows no such deprecation notice and remains a live GitHub project.
These are two different things under one brand name (a hosted product being sunset vs. an open-source
framework/registry that is not), not a genuine disagreement — flagged here so a later reader does not
conflate "OpenAI evals is being deprecated" with the open-source framework used in QG9's tool list. (topic: agents/agent-evaluation)

### garak's licence: code vs. site content
The garak GitHub repository's own `LICENSE` file (S1891) is GPL-3.0. A WebSearch summary separately
described "content on the garak site" (garak.ai) as Apache-2.0. Both claims can be true at once (dual
licensing of code vs. marketing/docs site prose is common), but the Apache-2.0 claim was not independently
re-fetched from garak.ai in this pass — see `gaps.md`. Not treated as a contradiction, but flagged so the
Apache-2.0 claim is not repeated as a `DOC` fact about the *code*.
Resolved in the census of 2026-09-25: the LICENSE file at `main` is the Apache License 2.0, as are the README badge
and `pyproject.toml`; the repository moved from a brief GPLv3 licence to Apache-2.0 in June 2023. The GPL-3.0 reading
was wrong and the kb now says Apache-2.0. [DOC S1891]

## agents-extra

- `opentelemetry.io/docs/specs/semconv/gen-ai/` and its `gen-ai-agent-spans`/`gen-ai-spans` sub-pages now display a
  "moved" notice pointing at a new, separate repository `open-telemetry/semantic-conventions-genai`
  (retrieved 2026-09-25), superseding the GenAI section that previously lived inside
  `open-telemetry/semantic-conventions` (used by `claude/otel-monitoring.md` and `logs/` for the general
  logs/code conventions, which have not moved). Cite the new repo (S2001-S2004) for GenAI-specific spans/metrics;
  the old repo commits already in `_sources.csv` (S639-S646) remain correct for logs/code conventions only.
- CaMeL's own paper title on arXiv is "Defeating Prompt Injections by Design" (S2006); the PROMPT-agents brief
  refers to it by the informal name "CaMeL" only. No factual conflict, just a naming note. (topic: agents/prompt-injection-design-patterns)

## agents-mcp

### Cognition's own position on multi-agents shifted between its two posts
- "Don't Build Multi-Agents" (S1926, 2025-06-12) argues against multi-agent designs in general, citing context fragmentation and implicit decision conflicts, and recommends single-threaded linear agents as the default. (topic: agents/subagents-vs-deterministic-tools)
- "Multi-Agents: What's Actually Working" (S1927, undated follow-up) walks this back: Cognition has since shipped multi-agent setups where multiple agents contribute intelligence but writes stay single-threaded. This is the same vendor revising its own earlier absolute claim, not two vendors disagreeing — recorded per PROMPT.md rule 6 (page contradicts an older one). [DOC/COMMUNITY S1926, S1927] (topic: agents/subagents-vs-deterministic-tools)

### Token multiplier for multi-agent vs chat is a single number, but its downstream restatement varies
- Anthropic's own post (S1921) states multi-agent systems use "about 15×" the tokens of a chat interaction, and agents alone use "about 4×." Secondary community sources (S1929, S1934) restate the 15× figure faithfully, but none of the fetched sources gave a chat-relative token multiplier specifically for a **single non-multi-agent tool-using agent with a deterministic step removed** — that comparison (subagent-with-tool vs same task solved by one deterministic MCP tool call) is not published anywhere found in this pass and is treated as `DER` in answers.md, not a sourced number. [DOC S1921; DER]

## agents-ner

- **Presidio's registry rename.** Search results and the docs site still show older material under
  `microsoft/presidio` (e.g. `microsoft/presidio-analyzer` on Docker Hub, `github.com/microsoft/presidio`
  samples), while `privacy/presidio.md` (part `privacy`, already in the kb) establishes the canonical
  current repository as `data-privacy-stack/presidio` with legacy `mcr.microsoft.com/presidio-*` images
  "no longer updated." This file follows the existing kb precedent and cites `data-privacy-stack/*` URLs
  where possible (S2085, S2086, S2090), but two Docker Hub / GitHub samples fetched via search (S2087,
  S2088) still resolve under the `microsoft/*` namespace — recorded as the same fork/rename lag already
  noted in `privacy/presidio.md`'s own sources, not a new conflict.
- **Azure Text PII character-limit figures.** The on-premises **container** doc (S2091, directly fetched)
  states a synchronous limit of 5,120 characters per document, up to 10 documents per call. A search-index
  summary of the cloud (non-container) service (cited as S2093) reports a different limit — the first
  50,000 characters of an over-length input are analyzed with a warning, rather than a hard per-call cap.
  These are not contradictory once read as two different feature paths (on-prem container vs. cloud Text
  PII API), but S2093 was not independently re-fetched and verified against the live
  `concepts/data-limits` page in this session — flagged so a future session re-checks the exact figure
  before relying on it. (topic: agents/shared-ner-service)
- **Google Sensitive Data Protection per-GB pricing.** One fetched search summary (S2101) gives three
  specific rates (~$1.00/$1.50/$0.05 per GB for discovery/storage inspection/streaming); a second summary
  reviewed while forming the same answer instead described pricing only as "$1-3 per GB depending on the
  number of InfoTypes scanned," a materially different structure (flat per-GB vs. InfoType-count-scaled).
  Both are search-engine paraphrases of the same underlying pricing page, not independently confirmed
  against the raw page tables — recorded as unresolved rather than picking one. (topic: agents/shared-ner-service)

## agents-overuse

No direct conflicts were found between sources fetched for this part. All four major vendors (Anthropic,
OpenAI, Microsoft, Google) converge on the same first-order rule — try the simplest, non-agentic solution
first — stated in different words but not in tension with each other (see `answers.md` QG37).

One point of terminology to note, not a disagreement: OpenAI's practical guide defines "agent" narrowly
enough to exclude a single-turn LLM call, a simple chatbot, or a sentiment classifier from the category at
all [DOC S1924], while Anthropic's "Building Effective Agents" (reused from topic 4, S1920) uses "agentic
systems" more broadly to include its own "workflow" category (predefined code paths orchestrating LLM
calls) alongside true agents. This is a difference in where each vendor draws the workflow/agent boundary,
not a factual disagreement about when complexity is warranted — both vendors still tell the reader to
prefer the simpler end of whichever spectrum they draw. Recorded here for completeness rather than as a
`_conflicts.md`-style contradiction.

## agents-wiki

### routine "next run time" bug window
`code.claude.com/docs/en/routines` documents its own now-fixed bug: before Claude Code v2.1.211, the CLI reported a routine with no schedule trigger (API/GitHub-only) as having a next run time "in the year 1"; v2.1.211 or later shows none. This is a self-reported vendor changelog note inside the current page, not a disagreement between two sources, but is recorded here because a session reading an older cached copy of this page or an older Claude Code build could see the stale behaviour. [DOC S1803] (topic: agents/headless-agent-runtimes)

### routine fire-payload trust framing changed
The same page states that before Claude Code v2.1.213, a routine's saved prompt was delivered to the session framed as an *untrusted background notification* (and could be refused), whereas v2.1.213+ delivers it as the session's *assigned task*. An agent-runtime description written against a pre-2026-04 build of Claude Code would describe the opposite trust behaviour from what ships now. [DOC S1803] (topic: agents/headless-agent-runtimes)

### no cost-cap flag despite brief expecting one
The deepening-pass brief asked to cover a `--max-budget-usd` flag "if exists" for Claude Code headless mode. The current `headless.md`, `github-actions.md`, and `gitlab-ci-cd.md` pages (retrieved 2026-09-25) name no such flag; the only cost controls are `--max-turns`, job/workflow timeouts, concurrency limits, and post-hoc `total_cost_usd` reporting via `--output-format json`. This is not a disagreement between sources but a documented absence — recorded here so a future session doesn't assume the flag exists from the brief's phrasing. [DOC S1800,S1801,S1802] (topic: agents/headless-agent-runtimes)

### GitHub's own doc-drift pattern lives outside Copilot coding agent
GitHub's official Copilot coding-agent best-practices page names no scheduled/issue-triggered documentation-update feature, while GitHub Next's separate `gh-aw` project ships a "Documentation Maintenance" sample workflow doing exactly that. A session reading only the Copilot coding-agent docs would conclude GitHub has no such capability; it exists, but under a different GitHub-affiliated project with its own trigger/guardrail model (`schedule:` frontmatter + safe-outputs, not Copilot's issue-assignment model). [DOC S1818,S1819,S1821]

## arch

### containers, gMSA, workload identity

None found. AWS's `credentials-fetcher` (COMMUNITY, S1607/S1608) does not contradict Microsoft's own Linux Kerberos docs (S1605, S1606) — it fills a gap Microsoft's own docs leave open (gMSA-to-Linux-keytab) rather than disagreeing with them. Flagging as a gap, not a conflict, since Microsoft makes no claim in either direction about gMSA-on-Linux beyond silence.

### tooling, texts, readiness

No direct factual conflicts found between official sources in this batch.

- `arch/twelve-factor-readiness.md`: Kubernetes official docs treat Secrets-as-env-vars and
  Secrets-as-mounted-files as equally valid (S1725, S1729), which is weaker than a stricter
  no-secrets-in-env-of-child-processes policy some teams adopt. This is not a conflict between sources — it is
  a stricter house policy going further than the platform requires — but is worth flagging since a reader
  might expect K8s docs to mandate the stricter file-based pattern and they do not.

## auth

### on-prem / Windows / ConfigMgr / SQL

- None identified this session for the topics researched (kerberos, ntlm-deprecation, ldap-smb-signing, gmsa-dmsa, configmgr-rbac-auth, sql-authz, ad-jit-membership). No two official sources were found to disagree; the ConfigMgr-NTLM community forum report (S1213) is consistent with, not contradicting, the official 2509 release note (S307) — it just adds real-world fallout detail.

### Entra / Graph / MSAL / GitLab

None found this pass. No direct contradiction surfaced between the sources fetched (S1270-S1292);
several items are simply undocumented (see gaps.md) rather than disagreeing.

### keys, propagation, revocation, audit, threats

- CAE scope wording: the CAE concept page (S1347) says the initial implementation covers Exchange Online, Teams and SharePoint Online, while the CAE developer guidance and claims-challenge pages (S1354, S1355) say Microsoft Graph sends claims challenges and honours critical events for clients that declare `cp1`. Reading both: automatic critical-event enforcement is documented for the three services; Graph enforcement is opt-in per client. [DER S1347,S1354,S1355]
- No source-vs-source factual conflicts were found in this agent's own research (key management, propagation latency, revocation, audit events, threats).

## dsc

- **3.3.0 release notes vs 3.3.0 binaries.** S118 lists MCP `--what-if` (#1697), the Group Policy template adapter (#1686), the environment variable resource (#1675), File/Content (#1676), UpdateList `--what-if` (#1616) and the `--required-version` rename (#1610). None of these are in the 3.3.0 zip or binary (S114, S116); all except the GP adapter are in 3.4.0-preview.1 (S115, S117).
- **Git tag `v3.3.0` vs the shipped 3.3.0 source.** The tag points at main 4b49240, where `dsc/Cargo.toml` = `3.4.0-preview.1` (S110). The 3.3.0 binaries match `release/v3.3` ea572fa, `3.3.0` (S111, S144). The release has `target_commitish: main` (S113).
- **3.4.0-preview.1 release notes vs zip.** S119 lists "Add Group Policy template adapter"; the adapter is in source (S121) but absent from `data.build.json` (S120) and from the zip (S115).
- **PROMPT.md premise vs evidence.** The prompt says the Group Policy adapter shipped in 3.4.0-preview.1. The zip (S115) and packaging list (S120) show it did not.
- **`directives.version` docs/tests vs behaviour.** The CLI help (S116) and the type docs (S104) imply matching against the dsc version. The engine compares against the dsc-lib crate version 3.2.0 (S102, S112), so `'>=3.3, <3.4'` fails on dsc 3.3.0 (observed, S116). The tests (S123) do not catch it.
- **SemanticVersionReq type docs vs binary.** S104 says bare versions without an operator, `x` wildcards and build metadata are forbidden. The 3.3.0 binary accepts `'3.3'`, `'1.x'`, `'3.3.0+abc'` in `directives.version` (S116).
- **Static published schemas vs engine schemas.** Repo bundled `config/document.json` (S146; build config `version: v3.1.0`, S137) has no `directives` property. `dsc schema -t configuration` from the 3.3.0 binary (S116) has it. The binary's `$schema` enum also has no v3.3 URI.
- **Learn CLI exit codes vs code.** The Learn page (S135, ms.date 2025-03-25) documents exit codes 0 to 6. The code (S101) defines 0 to 10 (7 resource not found, 8 assertion failed, 9 server failed, 10 Bicep failed).
- **Repo doc title vs CLI.** `docs/reference/cli/server/index.md` (S136) documents `dsc mcp`. The 3.3.0 command is `dsc server` with alias `mcp` (S100, S116).
- **3.3.0 UpdateList manifest key.** The 3.3.0 `windowsupdate.dsc.resource.json` uses `preTest: true` (S114); the engine's field is `implementsPretest` (S105). 3.4.0-preview.1 uses `implementsPretest` (S115).

## ident

- Graph device `extensionAttributes`: listed on the v1.0 resource page (S504) but not declared on the v1.0 CSDL `device` EntityType (S500); declared in beta CSDL (S501).
- managedDevice `$filter` notes: out-of-line CSDL Annotations (S500) state `$filter` for `azureADDeviceId`, `serialNumber`, `deviceName`, `model`, `manufacturer`, `operatingSystem`, `userPrincipalName` and others; the inline CSDL descriptions and the v1.0 resource page (S506) don't. Flagged per row in graph/csdl-managedDevice.properties.csv.
- managedDevice entity set description (S500) says combinations "must use 'and', not 'or'", while property annotations (S500) state "Supports $filter operator 'eq' and 'or'".
- Graph device `id`: `$filter` support stated on resource page (S504), not in CSDL (S500).
- Device deletion: manage-device-identities (S546, ms.date 2026-06-17) calls deletion "a nonrecoverable activity"; device soft delete preview (S547, ms.date 2026-04-05) keeps deleted devices recoverable for 30 days.
- Hybrid device ID origin: sync references map objectGUID to deviceID (S549, S550); the registration flow says DRS "creates a device ID" (S548) and Graph says deviceId is set by DRS at registration (S504).
- LDAP MaxValRange: ntdsutil article (S569) gives default 1,500; S570 says Windows Server 2008 R2+ hard-codes a maximum of 5,000 overriding higher policy values (different quantities, not a direct contradiction; listed for clarity).
- Licence of microsoftgraph/microsoft-graph-docs-contrib: `LICENSE` is CC BY 4.0, `LICENSE.md` is CC BY-NC-ND 3.0 US (both at commit 4ad99fd37a9e). Only facts and short quotes from this repo are stored in kb.

## infra

- gMSA host support: S400 (manage gMSA) says gMSA works on "Any Windows Server domain-joined server". S403 (understand service accounts, choosing table) shows gMSA "No" for "App runs on Windows Server". One of the two cells is wrong.
- PowerShell `Default` execution policy: S420 (about_Execution_Policies 7.5) says `Default` = RemoteSigned for Windows clients and servers, yet the same page says all-Undefined gives Restricted on clients. S421 (5.1) says Default = Restricted on clients and RemoteSigned on servers.
- ConfigMgr PowerShell execution policy values: S423 (client settings) documents three values (Bypass, Restricted, All Signed; default All Signed). S425 (SMS_ConfigMgrClientAgentConfig WMI, ms.date 2016) lists only 0=Bypass and 1=Restricted.
- sp_cleanup_temporal_history scope: S462's front matter monikerRange is Azure SQL DB / Fabric only, but its applies-to include (`sqlserver2017-asdb-asdbmi-fabricsqldb`) names SQL Server 2017+ and MI.
- GitLab Runner licence: S416 (runner repo LICENSE) is MIT for the whole repo with no docs exception. The GitLab monorepo LICENSE (S452) puts `doc/` under CC BY-SA 4.0, and docs.gitlab.com is published under CC BY-SA. Runner docs were treated as CC BY-SA (summarized only).
- GitLab Runner `--password`: the CLI help (S413) says "(required)". Issue 27895 (S414, COMMUNITY) says it isn't required for a gMSA.

## later

- Graph TCM `configurationMonitor.status`: beta reference page (S945) lists only `active`, `unknownFutureValue`; v1.0 page (S944) and both CSDLs (S956, S957) include `inactive`.
- Graph TCM `snapshotJobStatus`: reference page (S946) says `partiallySuccessful` is an evolvable member after `unknownFutureValue` needing `Prefer: include-unknown-enum-members`; CSDL (S956) orders `partiallySuccessful`=4 before `unknownFutureValue`=5.
- Graph TCM `monitorMode` enum values differ between v1.0 CSDL (`monitorOnly`=0, `unknownFutureValue`=1) and beta CSDL (`monitorOnly`=1, `unknownFutureValue`=5) (S956 vs S957).
- Graph TCM delegated permissions: setup page (S941) says delegated monitor management needs "any privileged role"; per-API permission tables (S951, S952) name delegated scopes `ConfigurationMonitoring.Read.All`/`ReadWrite.All`. Likely both apply; not stated together.
- Get-GPOReport (S920): OUTPUTS says "None", but description and example 3 say the report is written to the display without `-Path`.
- Gateway service account page (S909): recommends the gateway app over services.msc for changing the account, but the gMSA procedure on the same page uses services.msc.
- Power BI refresh limit wording: S901 says "Power BI Pro: up to 8"; S900 says "shared capacity: eight". Same number, different basis (licence vs capacity).
- RLS page (S910): says RLS can be configured in Desktop or the service, but also says roles previously defined in the service must be re-created in Desktop.

## mcp

- ZDR scope for Claude Code: code.claude.com ZDR page (S748) says ZDR for Claude Code is "available to qualified accounts on Claude for Enterprise"; platform.claude.com API retention page (S749) also lists Claude Code with API keys from a Commercial organization as covered. Differs in whether non-Enterprise API-key use is in scope (S748 mentions existing pay-as-you-go ZDR only as a migration path).
- Claude Code docs (S740) confirm a default MCP output cap of 25,000 tokens, and add a fixed 10,000-token warning and per-tool `anthropic/maxResultSizeChars` override (not a conflict, recorded for completeness). (topic: mcp/python-sdk)
- A project pinning `mcp>=2.2,<2.3` would need to note: SDK docs (S720/S728) state `ctx.elicit()` fails on 2026-07-28 connections, while Claude Code (S740) connects stdio servers on the earlier protocol by default: behaviour depends on the client's negotiation setting (`MCP_PROTOCOL_NEGOTIATION`), not on the SDK alone.
- Claude Code changelog 2.1.76 (S746) says elicitation was added for "form fields or browser URL"; 2.1.281 (S746) says URL-mode elicitation was "Added ... on 2026-07-28 protocol connections" — URL mode existed on legacy connections before, and was only added for the new protocol later.
- MCP extensions overview (S714) links `/specification/draft/...` for `_meta` rules and `server/discover`, while the spec pages are versioned 2026-07-28 (link target mismatch, no normative conflict found). (topic: mcp/tasks-extension)

## mecm1

- Client log level values: registry doc says LogLevel 0 Verbose / 1 Default / 2 Warnings and errors / 3 Errors only (S214 about-log-files.md); SDK SetGlobalLoggingConfiguration says 0 Verbose / 1 Normal / 2 No logging (S225).
- Collect client logs permission holders: current doc names Full Administrator and Infrastructure Administrator (S221); 1912 preview note names Full Administrator and Operations Administrator (S224).
- Collected file versions: Delete Aged Collected Files / software inventory doc keep "five most-recent copies" in sinv.box\FileCol (S223, S204); client diagnostics section says "no defined limit to the number of versions" for collected client logs (S221).
- Enforcement grace period range: client settings says 0-120 hours (S204); deploy applications says 1-120 hours (S229).
- SMS_DCMDeploymentCompliantDetailsPerAsset (a "compliant details" class) describes DiscoveredValue/InstanceData as reported "when the rule is non-compliant" (S209); internal inconsistency within one page.
- Version-support pages: updates.md front matter ms.date 2024-12-04 yet it lists 2603 (May 2026) (S217); content newer than its date stamp. Not a factual disagreement, noted for freshness checks.

## mecm2

- Built-in roles with Notify Resource: client-notification.md "Client notification" section (S326) says Full Administrator + Operations Administrator. The same page's "Client diagnostics" section (S326) and whats-new 1810 (S340) say Full Administrator + Infrastructure Administrator.
- AdminService class-name case: overview.md (S300) says class names are case-sensitive. release-notes.md (S306) says the wmi route is case-insensitive from 2006.
- SMS_ClientOperation.Priority is "1 Highest, 50 Lowest" (S328), but SMS_ClientOperationStatus.Priority is "1 highest, 10 lowest" (S330).
- Value 8 RequestPolicyNow is listed under PrimaryActionType in SMS_ClientOperation (S328) but under PrimaryActionTargetObjectType in SMS_ClientOperationStatus (S330).
- Invoke-CMScript (S335): -ScheduleTime is shown as Mandatory:True for all parameter sets, yet it is absent from both syntax blocks and the examples omit it.
- Tenant-attach troubleshooting pages say "IIS must be installed on provider machine" (e.g. troubleshoot-cmpivot.md), but set-up.md (S301) says IIS is not required from 2010.
- CMPivot permission for a failed AdminService path: cmpivot.md (S315) names HTTP 503 fallback to the SMS Provider (needs SMS Scripts Read). The 2603 KB (S312) also describes a fallback on HTTP 400 parse errors, fixed in 2603.

## ops

- **Remediations schedule.** deploy-remediations.md offers Once, Hourly and Daily schedules, but the same page says custom script packages "are rerun every 24 hours" (S609). https://raw.githubusercontent.com/MicrosoftDocs/memdocs/4b5429df8b47046c6b251e572ee61199fb5d4a5d/intune/device-management/tools/deploy-remediations.md
- **Collect diagnostics and Graph.** collect-diagnostics.md says diagnostics "can't be collected or downloaded by calling Microsoft Graph directly". Its reference links still list the Graph actions createDeviceLogCollectionRequest and createDownloadUrl (S616).
- **MDE machine $filter.** get-machines (S621) lists 14 filterable properties, including aadDeviceId, id, version, deviceValue, machineTags and lastIpAddress. exposed-apis-odata-samples (S628) lists only 8 for Machine and leaves out aadDeviceId. https://learn.microsoft.com/defender-endpoint/api/get-machines vs https://learn.microsoft.com/defender-endpoint/api/exposed-apis-odata-samples
- **MDE permissions.** get-machines (S621) accepts Machine.Read.All and Machine.Read. get-machine-by-id (S622) lists only Machine.ReadWrite.All and Machine.ReadWrite.
- **MDE property table vs examples.** rbacGroupId is typed String (S620), but the examples show the number 140 (S621, S622). isAadJoined appears in the examples but not in the property table.
- **Device query operators.** The single-device table operators (S612) do not include `summarize`, yet the same page says its aggregation functions work with it. The multi-device page (S613) does list `summarize`.
- **Co-management query.** how-to-monitor (S603) lists four SMS_Client_ComanagementState fields: MachineId, MDMEnrolled, Authority and ComgmtPolicyPresent. The WQL in create-queries (S647) also filters on MDMProvisioned, which is not in that list.

## priorart

- **Presidio org rename.** The brief's clone list and this agent's initial fetch used
  `microsoft/presidio`; the GitHub API now resolves that path to `data-privacy-stack/presidio` (the
  project moved out of the `microsoft` org). Both `prior-art/pseudonymization-tokenization.md` and
  `_sources.csv` (S1005) record the current org (`data-privacy-stack`) while noting
  the fetch was made via the `microsoft/presidio` URL, which GitHub transparently redirects. No
  factual disagreement, just a naming/ownership change worth flagging to other agents citing Presidio
  under the `microsoft` org.
- **Snipe-IT org rename.** Same pattern: `snipeio`/`snipe` org references resolve to
  `grokability/snipe-it` in the current GitHub API response (S1012).
- **Licence ambiguity via GitHub API.** hashicorp/vault, pyca/cryptography, inspec/inspec,
  fleetdm/fleet and ansible/awx all report `license.spdx_id: NOASSERTION` from the GitHub API despite
  each project publishing a licence file/statement on its own site or repo (Vault: BUSL-1.1 since
  2023; cryptography: dual Apache-2.0/BSD-3-Clause; AWX: Apache-2.0 per project docs). This agent
  recorded the GitHub API's literal answer as UNK/NOASSERTION rather than asserting the believed
  licence without re-fetching each project's own LICENSE file — treat these as needing a LICENSE-file
  check, not as confirmed licences.

## privacy

- Presidio CHANGELOG vs release 2.2.364: the CHANGELOG (S800) has no `[2.2.364]` section. Items that shipped in 2.2.364 per the release notes (S801), e.g. the threshold flag (#2114), PH_UMID (#2045) and the cryptography bump (#2144), sit under `[unreleased]` together with post-release items such as UuidRecognizer (S807).
- EDPB Guidelines 01/2025 consultation end: the news item (S873) says "until 28 February 2025". The consultation page (S872) shows the feedback period "17 January - 14 March 2025". (topic: privacy/gdpr-pseudonymisation)
- spaCy en_core_web_lg versions: GitHub releases have 3.8.0 (2024-09-30, S850). The Hugging Face repo was last modified 2023-11-21 with 3.7.1 (S851). Both say MIT. (topic: privacy/spacy-model-licence)
- NIST SP 800-38G: the page at /pubs/sp/800/38/g/final is the 2016-03-29 version, marked withdrawn (S865). The current final is /upd1/final (S866). Both carry the same number, "SP 800-38G". (topic: privacy/nist-sp800-38g)

## reuse

- **Licence "NOASSERTION" (GitHub API) vs. actual repository LICENSE file.** The prior-art agent
  (`prior-art/*.md`, S1002/S1009/S1014/S1018) recorded HashiCorp Vault, Chef InSpec, Fleet and
  Ansible AWX as licence `UNK` because the GitHub API reported `NOASSERTION`. Direct fetch of each
  repository's `LICENSE`/`LICENSE.md` this session resolves all four: Vault is BUSL-1.1 (not OSI
  open source — GitHub's NOASSERTION was effectively correct that it isn't a recognised OSS licence);
  InSpec and AWX are both plain Apache-2.0 (GitHub's NOASSERTION was a false negative, likely a
  non-standard LICENSE file heading/format); Fleet is MIT for its core with three carve-outs (`docs/`
  CC BY-SA 4.0, `ee/` its own licence, client JS "MIT Expat") — GitHub's NOASSERTION reflects that
  mixed-licence structure rather than an absence of licensing. [S1002,S1009,S1014,S1018 vs S1102,S1103,S1104,S1105,S1106]
- No other disagreements found between sources this session.

## security

### coordinator (crosswalk, coverage, precedence, candidates)

- **Group Policy reapplication vs common belief (and the first draft of `policy-precedence.md`):**
  - The Group Policy processing page states that a client-side extension reapplies settings only when its GPOs or GPO list change (S1592). The Part A first draft had said registry-based policy reapplies at every refresh "by default" [UNK].
  - The official text wins. So DSC drift on a GPO-managed value can persist until the next GPO change or forced refresh.
- **LSA protection value meaning:**
  - The Microsoft 24H2 baseline sets `Lsa\RunAsPPL=1` (S1472). The LSA page defines `1` as "with a UEFI variable" and `2` as "without" (S1477).
  - The Windows 11 22H2+ default enablement is without a UEFI variable (S1477). A baseline-conformant device is therefore locked in firmware, and reverting needs the opt-out tool.
  - Not a factual conflict. It is a difference between the default and the baseline that affects rollback.
- **Intune baseline vs GPO baseline as two writers:** Intune's Windows baseline 24H2 is derived from the same SCT baseline (S1475), and `MDMWinsOverGP` defaults to 0 (S1412). Estates that deploy both have two sources for many values; GP wins for mapped Policy CSP settings.
- **Microsoft baseline vs STIG on account lockout:** baseline `LockoutBadCount=10`; STIG `WN11-AC-000010` requires 3 or less. Baseline `LockoutDuration=10`; STIG `WN11-AC-000005` requires 15 minutes or more. (S1472, S1470)

### A: device settings catalog

- **CIS Windows 11 Enterprise Benchmark version vs. tested OS release.** Public digests describe
  v5.0.0/v5.0.1 as tested against Windows 11 release 23H2, which matters for any estate targeting
  24H2/25H2. Whether v5.1.0's front matter updates the tested release was not confirmed this pass
  (the CIS PDF itself is behind registration). Flag before citing CIS L1 items as validated for
  24H2/25H2 without checking v5.1.0's own applicability statement.
- No other cross-source disagreement was established this pass (most rows are UNK rather than
  conflicting DOC facts, since the machine-readable sources needed for a real crosswalk were not
  downloaded — see `gaps.A.md`).

### B: management plane

- **Device-log retention below CIS minimum, audit retention above it.** A design that keeps a 400-day audit table comfortably clears CIS Controls v8.1 Safeguard 8.10 (90-day minimum retention for audit logs), but normalized device logs kept only 30 days (diagnostic rather than security logs) sit below that minimum. See `security/logging-monitoring.md` § Conflicts. [DER S1492]
- **PyPI Trusted Publishing and self-managed GitLab.** A third-party blog (S1510, COMMUNITY) claims PyPI supports self-managed GitLab. The official *Adding a Trusted Publisher* page (S1597, retrieved 2026-09-24) says only gitlab.com projects are supported, and the official page wins. (topic: security/supply-chain)

### C: frameworks, regulation, AI

- (Resolved 2026-09-24) CIS Controls v8.1 licence (CC BY-NC-ND 4.0, no derivatives) [DOC S1563]: the
  `framework-control-map.csv` rows now use safeguard IDs plus a short own-words paraphrase instead of the
  official safeguard titles, matching the treatment of CIS Benchmark recommendation IDs elsewhere in the kb
  (part A). (topic: security/framework-control-map)
- No direct DOC-vs-DOC factual conflicts found in Part C's sources; the EU AI Act Digital Omnibus deferral dates
  come from law-firm/community summaries (S1558, S1559) rather than the consolidated regulation text itself,
  since EUR-Lex had not yet published a consolidated version reflecting Regulation (EU) 2026/1744 at retrieval
  time — flagged as `COMMUNITY`, not `DOC`, for that reason, not because sources disagree. (topic: security/privacy-compliance)

## prior-art/drift-detection

- Puppet latest_release: `prior-art/projects.csv` says 7.34.0 (2024-10-22) [S1008], but puppetlabs/puppet also has tag 8.10.0 (2024-10-18) and RubyGems published 7.34.0 and 8.10.0 on the same day, 2024-10-22. The recorded value is presumably GitHub's latest-release marker, which could not be re-read on 2026-09-25 (api.github.com blocked). Decide whether the column means GitHub's marker or the highest released version. (census 2026-09-25)
- Chef InSpec latest_release: `prior-art/projects.csv` says v5.24.24 (2026-06-25) [S1009], while the repo has tags v7.2.2, v7.3.0 and v7.3.1 (2026-09-22 to 2026-09-24). RubyGems' newest 7.x is 7.2.1 (2026-09-02) under LicenseRef-Chef-EULA, while 5.x gems are Apache-2.0. GitHub's latest-release marker could not be re-read (api.github.com blocked). (census 2026-09-25)
- The Ansible check-mode fact in `prior-art/drift-detection.md` is tagged [DOC S1009], but S1009 is the inspec/inspec repository metadata, which says nothing about Ansible. The fact needs an Ansible documentation source, or should become [UNK]. (census 2026-09-25)

## prior-art/tiered-approval-ops

- Teleport latest_release: `prior-art/projects.csv` says v18.10.0 (2026-07-09) [S1017], but gravitational/teleport has tags v18.10.7, v18.11.0 and v18.11.1 (2026-09-16), all older than the kb's 2026-09-24 retrieval. The value is presumably GitHub's latest-release marker, which could not be re-read on 2026-09-25 (api.github.com blocked). (census 2026-09-25)

## prior-art/mcp-microsoft-endpoint-mgmt

- The fact that the modelcontextprotocol/modelcontextprotocol and python-sdk repositories do not list Microsoft endpoint-management servers is tagged [DOC S1019], but S1019 is microsoft/mcp's metadata and servers/ listing, which cannot support it. It needs its own source, or should become [UNK]. (census 2026-09-25)

## intune/win32-apps

- Win32 supersedence graph limit: `add-win32` (ms.date 2026-04-14) says a maximum of 10 nodes / 10 updated or replaced apps [DOC S-wc6e3fba], while `configure-win32-supersedence` says a maximum of 11 nodes in a single supersedence graph [DOC S-vywsads7]. The dependency limit on `add-win32` is also internally inconsistent: "maximum of 100 dependencies ... as well as the app itself" versus the example "100 dependencies ... total size of 101". Treat 10 and 100 (including the parent) as the safe limits until Microsoft reconciles the pages. (topic: intune/win32-apps)

## intune/compliance-policies

- `windows10CompliancePolicy` Graph resource shape: the v1.0 resource page lists only 19 settable properties (password rules, `bitLockerEnabled`, `secureBootEnabled`, `codeIntegrityEnabled`, `earlyLaunchAntiMalwareDriverEnabled`, OS version bounds, `storageRequireEncryption`) [DOC S-taatt73w], while the beta resource page for the same type name adds `tpmRequired`, `activeFirewallRequired`, `defenderEnabled`, `defenderVersion`, `signatureOutOfDate`, `rtpEnabled`, `antivirusRequired`, `antiSpywareRequired`, `deviceThreatProtectionEnabled`, `deviceThreatProtectionRequiredSecurityLevel`, `configurationManagerComplianceRequired`, `validOperatingSystemBuildRanges`, `memoryIntegrityEnabled`, `kernelDmaProtectionEnabled`, `virtualizationBasedSecurityEnabled`, `firmwareProtectionEnabled`, `deviceCompliancePolicyScript`, `wslDistributions` and `roleScopeTagIds` [DOC S-2hhj3k5f]. Every one of these beta-only properties corresponds to a setting the admin center UI exposes today (`compliance-policy-create-windows`, S-qjd54t3z), so v1.0 cannot express most Windows System Security / Defender / Configuration Manager compliance settings via Graph; automation needs the beta endpoint (or the UI) for those settings until Microsoft ships them to v1.0. (topic: intune/compliance-policies)

## entra/agent-id

- Copilot Studio automatic-Agent-ID cutover date: "Recreate Copilot Studio agents in Microsoft Entra Agent
  ID" states agents created before **2026-03-18** use legacy app registrations, while "Microsoft Entra
  Agent IDs for Copilot Studio agents" states the cutover was **"May 2026"**. Both are current Microsoft
  Learn pages; which date is authoritative is unresolved. (topic: entra/agent-id)

## agents/windows-agentic-platform

- Recall availability default: Policy CSP `WindowsAI\AllowRecallEnablement` documents its own **default
  value as 1 (Recall available)**, but the same Microsoft Learn domain's "Manage Recall" admin guide states
  "By default, Recall is disabled for managed commercial devices... individual users can't enable Recall on
  their own." The CSP's declared default and the operational behavior on managed devices disagree; treat
  Recall as off-by-default on any Intune/GPO-managed device regardless of the CSP table's stated default.
  (topic: agents/windows-agentic-platform)
- `DisableClickToDo` applicability: the Policy CSP page lists this policy as **Windows Insider Preview only**
  (no stable OS/KB build given), while the companion "Manage Click to Do" admin article documents it and its
  Settings UI toggle without a preview caveat, alongside the Copilot+ PC hardware requirements that are
  themselves GA. Until the CSP page adds a stable-build requirement, treat `DisableClickToDo` itself as
  preview even though Click to Do the feature is GA on Copilot+ PCs. (topic: agents/windows-agentic-platform)

## security/vulnerability-prioritization

- BOD 22-01 status: CISA's KEV catalog page (fetched 2026-09-26) states the catalog now implements
  **BOD 26-04**, and the BOD 22-01 directive page itself states BOD 22-01 "has been revoked as of June 10, 2026,
  and is superseded by BOD 26-04." The research brief that requested this topic named BOD 22-01 as the
  remediation-timeline authority; that is now historical, not current. Both the historical BOD 22-01 timelines
  (2 weeks / 6 months) and the current pointer to BOD 26-04 are recorded in the article; BOD 26-04's own
  remediation timelines were not separately researched. (topic: security/vulnerability-prioritization)

## intune/linux-management

- Linux platform-support version lists disagree across current Microsoft Learn pages (all fetched 2026-09-26):
  the custom Bash script article ("Use custom Bash scripts to configure Linux devices in Microsoft Intune")
  lists prerequisites as Ubuntu Desktop, RHEL 8, or RHEL 9; the enrollment, compliance-settings, and
  custom-compliance-settings articles all list Ubuntu Desktop 24.04 LTS/26.04 LTS, RHEL 9, and RHEL 10 (with
  RHEL 8 support ending July 2026 per the What's new page). The Bash-script article appears stale. Both
  version lists are recorded in the article's Facts. (topic: intune/linux-management)

## windows/powershell-7

- PowerShell end-of-support dates: the Microsoft Lifecycle "Products" page for PowerShell gives retirement
  timestamps one calendar day later than the PowerShell Support Lifecycle page for the same releases (PT
  vs a plain date, e.g. 7.4/7.5 "11/11/2026 6:59:59 AM" vs "10-Nov-2026"; 7.2 "11/9/2024" vs "08-Nov-2024";
  7.0 "12/4/2022" vs "03-Dec-2022"). Both are current Microsoft pages; the article uses the Support
  Lifecycle page's plain dates in its Reference table and CSV, and records both. (topic: windows/powershell-7)
