# Conflicts (both sources linked)

Merged from `_parts/<agent>/conflicts.md`.

## agents-a2a-cache

- **Anthropic cache-read price multiplier for the newest model tier.** `platform.claude.com/docs/en/build-with-claude/prompt-caching` (S2130) states a range of "0.05x-0.025x" base input price for "Claude Opus 5.5, Fable 5.1, Mythos 5.1" reads, distinct from "0.1x" for other models. The same page's own worked example for Opus 5.5 computes cache read at "$0.20/MTok" against a "$4/MTok" base input, which is exactly 0.05x, not the lower bound of the stated range (0.025x). `platform.claude.com/docs/en/about-claude/pricing` (S2131) was fetched to cross-check but the exact per-model read multiplier was not independently re-extracted from it in this session. Recorded here rather than resolved; a task that needs the exact number should re-fetch S2131 directly for the model in question. [DOC S2130 vs itself; S2131 unconfirmed] (topic: agents/agent-caching)
- **A2A v1.0.0 timeline vs Linux Foundation transfer date.** The Linux Foundation press release (S2123) dates the protocol's transfer to Linux Foundation governance at 2025-06-23, describing it then as the "Agent2Agent Protocol Project." The spec site (S2120), fetched in 2026, references a 2026-08-27 post titled "A2A joins the Agentic AI Foundation," which reads as a distinct, later governance event or rename not described in S2123. Whether "Agentic AI Foundation" is the same body as the original Agent2Agent Protocol Project under a new name, a sibling foundation, or an unrelated grouping was not resolved (see gaps.md). [DOC S2120 vs S2123, unresolved] (topic: agents/a2a-protocol)
  - Resolved 2026-09-27: not a conflict but two sequential events. The 2026-08-27 post (S-2jevtssc) says A2A was accepted as a Growth Stage project of the Agentic AI Foundation (AAIF), which the Linux Foundation directs, alongside MCP, goose and AGENTS.md; the 2025 transfer (S2123) stands. v1.0.0 itself was released 2026-03-12 (S-xasyjfgi). (topic: agents/a2a-protocol)

## agents-authz

- **MCP authorization spec: scope-selection strategy is new since the pinned 2026-07-28 revision.** `mcp/authorization.md` (S707) reflects the 2026-07-28 revision (DCR deprecation, `iss` validation, CIMD) and does not mention a `WWW-Authenticate: scope=` challenge, `scopes_supported` least-privilege guidance, or the step-up authorization flow. The draft revision fetched for this part (S2045) adds all three. Not a contradiction — S2045 is a **later draft** than S707's pinned revision — but a reader of `mcp/authorization.md` alone would not know per-scope/per-tool authorization exists at all in the spec lineage. Recorded here rather than edited into `mcp/authorization.md` (not this agent's file to edit). [DOC S707, S2045]
  - Reviewed 2026-09-28, not a source disagreement: a later draft adds scope guidance to the pinned 2026-07-28 revision; stays as a reader warning until the next spec release.
- **PIM-for-Groups latency: two different numbers for two different things, easily conflated.** S1282 (prior pass) states the PIM active-assignment write itself is "within seconds." S2052 (this pass, same Microsoft product surface) states downstream SCIM provisioning of that membership into an application takes "2-10 minutes" for the first five activations per 10 seconds, else 40 minutes. Not a contradiction — they measure different steps of the same activation — but a reader citing only one page would get an incomplete and potentially wrong latency estimate for "how long until PIM activation takes effect," since the answer depends on which consumer (Entra role engine vs a SCIM-provisioned app vs a token-caching client) is asked. [DOC S1282, S2052] (topic: agents/agent-rbac)
  - Reviewed 2026-09-28, not a source disagreement: two steps of one activation; `auth/propagation-latency.md` gives both.
- **GitLab PAT maximum lifetime**: this part's WebFetch summary of S2046 states the 400-day maximum "extended... in GitLab 17.6 (feature flag controlled)"; a separate, unrelated data-retention policy can independently specify keeping temporal history for "400 days". No actual disagreement between sources — noted only because the same number (400) can appear in two unrelated contexts and a future reader should not conflate them. (topic: agents/api-tokens-issue-and-store)
  - Reviewed 2026-09-28, not a source disagreement: the same number in unrelated contexts; closed.

## agents-copilot

### Billing unit: "messages" vs "Copilot Credits"

Older Copilot Studio pages (release-plan archive S1967, some Q&A/troubleshooting pages found in search)
describe usage in *messages* and *message packs*. The current billing page (S1961, ms.date
2026-08-03) states: "Starting on September 1, 2025, the common currency for agents changed from
*messages* to Copilot Credits. There's no change in the quantity per prepaid pack or to the
pay-as-you-go rate." This is not a contradiction — S1961 is the vendor's own note that the unit
was renamed, and the quotas page (S1960) still uses "prepaid message packs" as the capacity-tier
label even while credits are the billed unit. Treat "message pack" as the tier name and "Copilot
Credit" as the metered unit; both are current per S1960/S1961. [DOC S1960, S1961] (topic: agents/copilot-studio-inventory)

### MCP transport support

S1964 (ms.date 2026-05-28) states Copilot Studio "supports the Streamable transport type" and "no
longer supports SSE for MCP after August 2025." No conflicting page was found; this is included
here only because a search snippet independently surfaced the same claim, confirming it is not a
one-off wording accident. [DOC S1964]

No other direct factual conflicts between official sources were found in this part's source set. (topic: agents/copilot-studio-inventory)

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
field [COMMUNITY S1841, S1843 — S1841 is an unanswered user question (2025-11-07) reporting 8,000 characters under an M365 Copilot licence, and S1843 a community digest, not a directly fetched
learn.microsoft.com instructions-limit page, so this is not yet a confirmed DOC-vs-DOC conflict]. A community report
(S1843) describes agents failing at combined lengths well under any single field's 8,000-character cap, via
`OpenAIAdditionalInstructionsLengthExceededLimit`, because the limit that actually fires is on the *combined* prompt
sent to the underlying model, not on any one field. This is not a contradiction between two official statements (no
second official statement was fetched), but it is a documented-vs-observed gap worth flagging: an author who stays
under the visible 8,000-character counter can still hit a hard failure. Recorded as a conflict-shaped finding rather
than a strict DOC/DOC conflict, since one side (the internal threshold) has no official page describing its exact
value. (topic: agents/instruction-and-context-limits)
  - Update 2026-09-27: a Microsoft Q&A user report (S-f3chtt24) adds an observed failure at about 5,300 combined characters with `OpenAIAdditionalInstructionsLengthExceededLimit`; still documented-vs-observed, kept open. (topic: agents/instruction-and-context-limits)

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
was wrong and the kb now says Apache-2.0. [DOC S1891] (topic: agents/agent-evaluation)

## agents-extra

- `opentelemetry.io/docs/specs/semconv/gen-ai/` and its `gen-ai-agent-spans`/`gen-ai-spans` sub-pages now display a
  "moved" notice pointing at a new, separate repository `open-telemetry/semantic-conventions-genai`
  (retrieved 2026-09-25), superseding the GenAI section that previously lived inside
  `open-telemetry/semantic-conventions` (used by `claude/otel-monitoring.md` and `logs/` for the general
  logs/code conventions, which have not moved). Cite the new repo (S2001-S2004) for GenAI-specific spans/metrics;
  the old repo commits already in `_sources.csv` (S639-S646) remain correct for logs/code conventions only.
- CaMeL's own paper title on arXiv is "Defeating Prompt Injections by Design" (S2006); the PROMPT-agents brief
  refers to it by the informal name "CaMeL" only. No factual conflict, just a naming note. (topic: agents/prompt-injection-design-patterns)
  - Reviewed 2026-09-28, not a source disagreement: a naming note; closed.

## agents-mcp

### Cognition's own position on multi-agents shifted between its two posts
- "Don't Build Multi-Agents" (S1926, 2025-06-12) argues against multi-agent designs in general, citing context fragmentation and implicit decision conflicts, and recommends single-threaded linear agents as the default. (topic: agents/subagents-vs-deterministic-tools)
  - Reviewed 2026-09-28, not a source disagreement: the same vendor revising its own position; the newer post is the current view.
- "Multi-Agents: What's Actually Working" (S1927, undated follow-up) walks this back: Cognition has since shipped multi-agent setups where multiple agents contribute intelligence but writes stay single-threaded. This is the same vendor revising its own earlier absolute claim, not two vendors disagreeing — recorded per PROMPT.md rule 6 (page contradicts an older one). [DOC/COMMUNITY S1926, S1927] (topic: agents/subagents-vs-deterministic-tools)
  - Reviewed 2026-09-28, not a source disagreement: see the entry above; closed.

### Token multiplier for multi-agent vs chat is a single number, but its downstream restatement varies
- Anthropic's own post (S1921) states multi-agent systems use "about 15×" the tokens of a chat interaction, and agents alone use "about 4×." Secondary community sources (S1929, S1934) restate the 15× figure faithfully, but none of the fetched sources gave a chat-relative token multiplier specifically for a **single non-multi-agent tool-using agent with a deterministic step removed** — that comparison (subagent-with-tool vs same task solved by one deterministic MCP tool call) is not published anywhere found in this pass and is treated as `DER` in answers.md, not a sourced number. [DOC S1921; DER] (topic: agents/agent-overuse-patterns)
  - Reviewed 2026-09-28, not a source disagreement: restatements agree with the source; the missing single-agent multiplier is unpublished, so it stays DER.

## agents-ner

- **Presidio's registry rename.** Search results and the docs site still show older material under
  `microsoft/presidio` (e.g. `microsoft/presidio-analyzer` on Docker Hub, `github.com/microsoft/presidio`
  samples), while `privacy/presidio.md` (part `privacy`, already in the kb) establishes the canonical
  current repository as `data-privacy-stack/presidio` with legacy `mcr.microsoft.com/presidio-*` images
  "no longer updated." This file follows the existing kb precedent and cites `data-privacy-stack/*` URLs
  where possible (S-tks3v5p5, S2086, S2090; S-tks3v5p5, which supersedes S2085, no longer mentions registries, so the ghcr/MCR evidence is now S2087, the Docker Hub description read via the v2 API, and S-g33kybfp, whose Helm sample defaults to `ghcr.io/data-privacy-stack`), but two Docker Hub / GitHub samples fetched via search (S2087,
  S2088) still resolve under the `microsoft/*` namespace — recorded as the same fork/rename lag already
  noted in `privacy/presidio.md`'s own sources, not a new conflict.
  - Reviewed 2026-09-28, not a source disagreement: a repository move; `privacy/presidio.md` cites the current org.
- **Azure Text PII character-limit figures.** The on-premises **container** doc (S2091, directly fetched)
  states a synchronous limit of 5,120 characters per document, up to 10 documents per call. A search-index
  summary of the cloud (non-container) service (cited as S2093) reports a different limit — the first
  50,000 characters of an over-length input are analyzed with a warning, rather than a hard per-call cap.
  These are not contradictory once read as two different feature paths (on-prem container vs. cloud Text
  PII API), but S2093 was not independently re-fetched and verified against the live
  `concepts/data-limits` page in this session — flagged so a future session re-checks the exact figure
  before relying on it. (topic: agents/shared-ner-service)
  - Explained 2026-09-27: the 50,000-character figure is the Azure AI Search PII skill (S-ulqlpnc5) and 10 MB the Document-based PII request limit (S-alyohfil); neither is cloud Text PII. (topic: agents/shared-ner-service)
- **Google Sensitive Data Protection per-GB pricing.** One fetched search summary (S2101) gives three
  specific rates (~$1.00/$1.50/$0.05 per GB for discovery/storage inspection/streaming); a second summary
  reviewed while forming the same answer instead described pricing only as "$1-3 per GB depending on the
  number of InfoTypes scanned," a materially different structure (flat per-GB vs. InfoType-count-scaled).
  Both are search-engine paraphrases of the same underlying pricing page, not independently confirmed
  against the raw page tables — recorded as unresolved rather than picking one. (topic: agents/shared-ner-service)
  - Resolved 2026-09-27: the live pricing page (S2101) was read; the article's figures stand and the "$1.50"/"$0.05" summary figures do not appear on it. (topic: agents/shared-ner-service)

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
GitHub's official Copilot coding-agent best-practices page names no scheduled/issue-triggered documentation-update feature, while GitHub Next's separate `gh-aw` project ships a "Documentation Maintenance" sample workflow doing exactly that. A session reading only the Copilot coding-agent docs would conclude GitHub has no such capability; it exists, but under a different GitHub-affiliated project with its own trigger/guardrail model (`schedule:` frontmatter + safe-outputs, not Copilot's issue-assignment model). [DOC S1818, S-qso27noq, S1821] (topic: agents/docs-maintenance-agents)
  - Resolved 2026-09-27: GitHub's Copilot docs now include "About GitHub Agentic Workflows" (S-h6jpev6e, public preview), with documentation upkeep as a listed use case, so the pattern is now documented by GitHub itself. (topic: agents/docs-maintenance-agents)

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
  - Closed 2026-09-28: a no-conflict record for an old session.

### Entra / Graph / MSAL / GitLab

None found this pass. No direct contradiction surfaced between the sources fetched (S1270-S1292);
several items are simply undocumented (see gaps.md) rather than disagreeing.

### keys, propagation, revocation, audit, threats

- CAE scope wording: the CAE concept page (S1347) says the initial implementation covers Exchange Online, Teams and SharePoint Online, while the CAE developer guidance and claims-challenge pages (S1354, S1355) say Microsoft Graph sends claims challenges and honours critical events for clients that declare `cp1`. Reading both: automatic critical-event enforcement is documented for the three services; Graph enforcement is opt-in per client. [DER S1347,S1354,S1355] (topic: auth/token-lifetimes-cae)
  - Resolved 2026-09-27: the same pinned page (still the live commit) also says Exchange Online, SharePoint Online, Teams and MS Graph evaluate key Conditional Access policies themselves, and the Zero Trust CAE page (S-yc5geeul) describes Graph checking Entra's token events; "initial implementation" is history, not a limit, so the pages agree. (topic: auth/token-lifetimes-cae)
- No source-vs-source factual conflicts were found in this agent's own research (key management, propagation latency, revocation, audit events, threats).
  - Closed 2026-09-28: a no-conflict record for an old session.

## dsc

- **3.3.0 release notes vs 3.3.0 binaries.** S118 lists MCP `--what-if` (#1697), the Group Policy template adapter (#1686), the environment variable resource (#1675), File/Content (#1676), UpdateList `--what-if` (#1616) and the `--required-version` rename (#1610). None of these are in the 3.3.0 zip or binary (S114, S116); all except the GP adapter are in 3.4.0-preview.1 (S115, S117). (topic: dsc/releases-feature-matrix)
  - Reviewed 2026-09-28, still open: fixed release artifacts; the kb follows the binaries. Closes only if the release notes are edited.
- **Git tag `v3.3.0` vs the shipped 3.3.0 source.** The tag points at main 4b49240, where `dsc/Cargo.toml` = `3.4.0-preview.1` (S110). The 3.3.0 binaries match `release/v3.3` ea572fa, `3.3.0` (S111, S144). The release has `target_commitish: main` (S113). (topic: dsc/releases-feature-matrix)
  - Reviewed 2026-09-28, still open: the tag and the release branch are fixed history; the kb follows `release/v3.3`.
- **3.4.0-preview.1 release notes vs zip.** S119 lists "Add Group Policy template adapter"; the adapter is in source (S121) but absent from `data.build.json` (S120) and from the zip (S115). (topic: dsc/releases-feature-matrix)
  - Reviewed 2026-09-28, still open: fixed release artifacts; the kb follows the zip.
- **PROMPT.md premise vs evidence.** The prompt says the Group Policy adapter shipped in 3.4.0-preview.1. The zip (S115) and packaging list (S120) show it did not. (topic: dsc/releases-feature-matrix)
  - Reviewed 2026-09-28, not a source disagreement: a brief's premise, not a source; the kb follows the zip. Closed.
- **`directives.version` docs/tests vs behaviour.** The CLI help (S116) and the type docs (S104) imply matching against the dsc version. The engine compares against the dsc-lib crate version 3.2.0 (S102, S112), so `'>=3.3, <3.4'` fails on dsc 3.3.0 (observed, S116). The tests (S123) do not catch it. (topic: dsc/directives)
  - Reviewed 2026-09-28, still open: behaviour observed on 3.3.0; needs a lab run on a later release to see whether it is fixed.
- **SemanticVersionReq type docs vs binary.** S104 says bare versions without an operator, `x` wildcards and build metadata are forbidden. The 3.3.0 binary accepts `'3.3'`, `'1.x'`, `'3.3.0+abc'` in `directives.version` (S116). (topic: dsc/directives)
  - Reviewed 2026-09-28, still open: needs a lab run on a later release.
- **Static published schemas vs engine schemas.** Repo bundled `config/document.json` (S146; build config `version: v3.1.0`, S137) has no `directives` property. `dsc schema -t configuration` from the 3.3.0 binary (S116) has it. The binary's `$schema` enum also has no v3.3 URI. (topic: dsc/schemas)
  - Reviewed 2026-09-28, still open: the published schema is still the v3.1.0 build per the pinned sources; recheck at the next schema publish.
- **Learn CLI exit codes vs code.** The Learn page (S135, ms.date 2025-03-25) documents exit codes 0 to 6. The code (S101) defines 0 to 10 (7 resource not found, 8 assertion failed, 9 server failed, 10 Bicep failed). (topic: dsc/cli-reference)
  - Reviewed 2026-09-28, still open: Learn search (dsc-3.0 view) still lists exit codes 0 to 6.
- **Repo doc title vs CLI.** `docs/reference/cli/server/index.md` (S136) documents `dsc mcp`. The 3.3.0 command is `dsc server` with alias `mcp` (S100, S116). (topic: dsc/mcp-server)
  - Reviewed 2026-09-28, still open: not re-read; the kb follows the binary (`dsc server`, alias `mcp`).
- **3.3.0 UpdateList manifest key.** The 3.3.0 `windowsupdate.dsc.resource.json` uses `preTest: true` (S114); the engine's field is `implementsPretest` (S105). 3.4.0-preview.1 uses `implementsPretest` (S115). (topic: dsc/manifests-diff)
  - Reviewed 2026-09-28, still open: fixed in 3.4.0-preview.1; a 3.3.0 artifact that stays as shipped.

## ident

- Graph device `extensionAttributes`: listed on the v1.0 resource page (S504) but not declared on the v1.0 CSDL `device` EntityType (S500); declared in beta CSDL (S501). (topic: graph/csdl-device)
  - Reviewed 2026-09-28, still open: CSDL not re-downloaded; needs a fresh `$metadata` read.
- managedDevice `$filter` notes: out-of-line CSDL Annotations (S500) state `$filter` for `azureADDeviceId`, `serialNumber`, `deviceName`, `model`, `manufacturer`, `operatingSystem`, `userPrincipalName` and others; the inline CSDL descriptions and the v1.0 resource page (S506) don't. Flagged per row in graph/csdl-managedDevice.properties.csv.
  - Reviewed 2026-09-28, still open: CSDL not re-downloaded; per-row flags stay in the CSV.
- managedDevice entity set description (S500) says combinations "must use 'and', not 'or'", while property annotations (S500) state "Supports $filter operator 'eq' and 'or'". (topic: graph/csdl-managedDevice)
  - Reviewed 2026-09-28, still open: CSDL not re-downloaded; test with a live tenant query to settle.
- Graph device `id`: `$filter` support stated on resource page (S504), not in CSDL (S500). (topic: graph/csdl-device)
  - Reviewed 2026-09-28, still open: CSDL not re-downloaded.
- Device deletion: manage-device-identities (S546, ms.date 2026-06-17) calls deletion "a nonrecoverable activity"; device soft delete preview (S547, ms.date 2026-04-05) keeps deleted devices recoverable for 30 days. (topic: entra/stale-devices)
  - Re-read 2026-09-27, still open: manage-device-identities (updated_at 2026-08-25) still calls deletion a nonrecoverable activity and does not mention the soft-delete preview. (topic: entra/stale-devices)
- Hybrid device ID origin: sync references map objectGUID to deviceID (S549, S550); the registration flow says DRS "creates a device ID" (S548) and Graph says deviceId is set by DRS at registration (S504). (topic: entra/hybrid-deviceid-objectguid)
  - Re-checked 2026-09-27 (Learn search): no page reconciles the sync mapping with DRS 'creates a device ID'. Still open. (topic: entra/hybrid-deviceid-objectguid)
- LDAP MaxValRange: ntdsutil article (S569) gives default 1,500; S570 says Windows Server 2008 R2+ hard-codes a maximum of 5,000 overriding higher policy values (different quantities, not a direct contradiction; listed for clarity). (topic: ad/ldap-paging-filters)
  - Reviewed 2026-09-28, not a source disagreement: different quantities (default vs hard cap); closed.
- Licence of microsoftgraph/microsoft-graph-docs-contrib: `LICENSE` is CC BY 4.0, `LICENSE.md` is CC BY-NC-ND 3.0 US (both at commit 4ad99fd37a9e). Only facts and short quotes from this repo are stored in kb.
  - Reviewed 2026-09-28, still open: two licence files in one repository; the kb keeps facts and short quotes only.

## infra

- gMSA host support: S400 (manage gMSA) says gMSA works on "Any Windows Server domain-joined server". S403 (understand service accounts, choosing table) shows gMSA "No" for "App runs on Windows Server". One of the two cells is wrong. (topic: windows/gmsa)
  - Reviewed 2026-09-28, still open: Learn search shows the understand-service-accounts table still has gMSA 'No' for 'App runs on Windows Server' while the manage-gMSA page says any Windows Server domain-joined server.
- PowerShell `Default` execution policy: S420 (about_Execution_Policies 7.5) says `Default` = RemoteSigned for Windows clients and servers, yet the same page says all-Undefined gives Restricted on clients. S421 (5.1) says Default = Restricted on clients and RemoteSigned on servers. (topic: windows/execution-policy-signing)
  - Reviewed 2026-09-28, still open: Learn search (about_Execution_Policies, 7.6 view) still says `Default` is RemoteSigned for clients and servers and all-Undefined gives Restricted on clients.
- ConfigMgr PowerShell execution policy values: S423 (client settings) documents three values (Bypass, Restricted, All Signed; default All Signed). S425 (SMS_ConfigMgrClientAgentConfig WMI, ms.date 2016) lists only 0=Bypass and 1=Restricted. (topic: windows/execution-policy-signing)
  - Reviewed 2026-09-28, still open: not re-read; the WMI class page is dated 2016.
- sp_cleanup_temporal_history scope: S462's front matter monikerRange is Azure SQL DB / Fabric only, but its applies-to include (`sqlserver2017-asdb-asdbmi-fabricsqldb`) names SQL Server 2017+ and MI. (topic: sqlserver/temporal-tables)
  - Reviewed 2026-09-28, still open: not re-read; a front-matter metadata mismatch.
- GitLab Runner licence: S416 (runner repo LICENSE) is MIT for the whole repo with no docs exception. The GitLab monorepo LICENSE (S452) puts `doc/` under CC BY-SA 4.0, and docs.gitlab.com is published under CC BY-SA. Runner docs were treated as CC BY-SA (summarized only). (topic: windows/gitlab-runner-windows)
  - Reviewed 2026-09-28, still open: two licence statements; the kb keeps summaries only.
- GitLab Runner `--password`: the CLI help (S413) says "(required)". Issue 27895 (S414, COMMUNITY) says it isn't required for a gMSA. (topic: windows/gitlab-runner-windows)
  - Reviewed 2026-09-28, still open: official help vs a community issue; a lab registration with a gMSA would settle it.

## later

- Graph TCM `configurationMonitor.status`: beta reference page (S945) lists only `active`, `unknownFutureValue`; v1.0 page (S944) and both CSDLs (S956, S957) include `inactive`. (topic: graph/tcm-apis)
  - Reviewed 2026-09-28, still open: the v1.0 page still lists `active`, `inactive`, `unknownFutureValue`; the beta page was not re-read.
- Graph TCM `snapshotJobStatus`: reference page (S946) says `partiallySuccessful` is an evolvable member after `unknownFutureValue` needing `Prefer: include-unknown-enum-members`; CSDL (S956) orders `partiallySuccessful`=4 before `unknownFutureValue`=5. (topic: graph/tcm-apis)
  - Reviewed 2026-09-28, still open: not re-read; enum order in CSDL vs page text.
- Graph TCM `monitorMode` enum values differ between v1.0 CSDL (`monitorOnly`=0, `unknownFutureValue`=1) and beta CSDL (`monitorOnly`=1, `unknownFutureValue`=5) (S956 vs S957). (topic: graph/tcm-apis)
  - Reviewed 2026-09-28, still open: CSDLs not re-downloaded; v1.0 page still lists `monitorOnly`, `unknownFutureValue`.
- Graph TCM delegated permissions: setup page (S941) says delegated monitor management needs "any privileged role"; per-API permission tables (S951, S952) name delegated scopes `ConfigurationMonitoring.Read.All`/`ReadWrite.All`. Likely both apply; not stated together. (topic: graph/tcm-apis)
  - Reviewed 2026-09-28, still open: the Get and Update pages still list delegated `ConfigurationMonitoring.*` scopes; the setup page's role requirement was not re-read.
- Get-GPOReport (S920): OUTPUTS says "None", but description and example 3 say the report is written to the display without `-Path`. (topic: gpo/gpo-export)
  - Re-read 2026-09-27, still open: the live windowsserver2025-ps page still says Outputs None / 'This cmdlet does not generate any output'. (topic: gpo/gpo-export)
- Gateway service account page (S909): recommends the gateway app over services.msc for changing the account, but the gMSA procedure on the same page uses services.msc. (topic: powerbi/on-prem-gateway-sql)
  - Reviewed 2026-09-28, still open: not re-read; an internal inconsistency on one page.
- Power BI refresh limit wording: S901 says "Power BI Pro: up to 8"; S900 says "shared capacity: eight". Same number, different basis (licence vs capacity). (topic: powerbi/scheduled-refresh)
  - Reviewed 2026-09-28, not a source disagreement: same number on two bases; closed.
- RLS page (S910): says RLS can be configured in Desktop or the service, but also says roles previously defined in the service must be re-created in Desktop. (topic: powerbi/row-level-security)
  - Reviewed 2026-09-28, still open: not re-read; an internal inconsistency on one page.

## mcp

- ZDR scope for Claude Code: code.claude.com ZDR page (S748) says ZDR for Claude Code is "available to qualified accounts on Claude for Enterprise"; platform.claude.com API retention page (S749) also lists Claude Code with API keys from a Commercial organization as covered. Differs in whether non-Enterprise API-key use is in scope (S748 mentions existing pay-as-you-go ZDR only as a migration path). (topic: claude/data-retention)
  - Resolved 2026-09-28: not a disagreement. The Privacy Center ZDR article (S-qrxvz4ph, 2026-06-09) lists both routes: products that use a Commercial organization's API key, including Claude Code through the API, and Claude Code for Enterprise plans. The code.claude.com page describes the Enterprise route and names pay-as-you-go API-key ZDR as a migration source. (topic: claude/data-retention)
- Claude Code docs (S740) confirm a default MCP output cap of 25,000 tokens, and add a fixed 10,000-token warning and per-tool `anthropic/maxResultSizeChars` override (not a conflict, recorded for completeness). (topic: mcp/python-sdk)
- A project pinning `mcp>=2.2,<2.3` would need to note: SDK docs (S720/S728) state `ctx.elicit()` fails on 2026-07-28 connections, while Claude Code (S740) connects stdio servers on the earlier protocol by default: behaviour depends on the client's negotiation setting (`MCP_PROTOCOL_NEGOTIATION`), not on the SDK alone. (topic: claude/elicitation)
  - Reviewed 2026-09-28, not a source disagreement: a negotiation-dependent behaviour, not two sources disagreeing.
- Claude Code changelog 2.1.76 (S746) says elicitation was added for "form fields or browser URL"; 2.1.281 (S746) says URL-mode elicitation was "Added ... on 2026-07-28 protocol connections" — URL mode existed on legacy connections before, and was only added for the new protocol later. (topic: claude/elicitation)
  - Reviewed 2026-09-28, not a source disagreement: two changelog entries for two protocol versions; closed.
- MCP extensions overview (S714) links `/specification/draft/...` for `_meta` rules and `server/discover`, while the spec pages are versioned 2026-07-28 (link target mismatch, no normative conflict found). (topic: mcp/tasks-extension)
  - Reviewed 2026-09-28, not a source disagreement: a link-target mismatch with no normative conflict.

## mecm1

- Client log level values: registry doc says LogLevel 0 Verbose / 1 Default / 2 Warnings and errors / 3 Errors only (S214 about-log-files.md); SDK SetGlobalLoggingConfiguration says 0 Verbose / 1 Normal / 2 No logging (S225). (topic: mecm/log-files)
  - Re-read 2026-09-27, still open: about-log-files (updated_at 2026-08-31) still lists 0 Verbose among four levels, and the SetGlobalLoggingConfiguration page still lists Verbose, Normal and No logging. (topic: mecm/log-files)
- Collect client logs permission holders: current doc names Full Administrator and Infrastructure Administrator (S221); 1912 preview note names Full Administrator and Operations Administrator (S-pzvndq5z). (topic: mecm/collect-client-logs)
  - Re-read 2026-09-27, still open: the live client-notification page's Client diagnostics prerequisites still name Full Administrator and Infrastructure Administrator, while its Client notification section names Full Administrator and Operations Administrator. (topic: mecm/collect-client-logs)
- Collected file versions: Delete Aged Collected Files / software inventory doc keep "five most-recent copies" in sinv.box\FileCol (S223, S204); client diagnostics section says "no defined limit to the number of versions" for collected client logs (S221). (topic: mecm/collect-client-logs)
  - Re-read 2026-09-27, still open: the live client-notification page still says there's no defined limit to the number of versions of collected diagnostics. (topic: mecm/collect-client-logs)
- Enforcement grace period range: client settings says 0-120 hours (S204); deploy applications says 1-120 hours (S229). (topic: mecm/client-settings)
  - Re-read 2026-09-27, still open: both live pages (updated_at 2026-08-31) keep 0 to 120 hours (about-client-settings) and 1 to 120 hours (deploy-applications). (topic: mecm/client-settings)
- SMS_DCMDeploymentCompliantDetailsPerAsset (a "compliant details" class) describes DiscoveredValue/InstanceData as reported "when the rule is non-compliant" (S209); internal inconsistency within one page. (topic: mecm/sql-views-compliance)
  - Re-read 2026-09-27, still open: the live class page (updated_at 2026-08-28) still describes DiscoveredValue and InstanceData in non-compliant terms. (topic: mecm/sql-views-compliance)
- Version-support pages: updates.md front matter ms.date 2024-12-04 yet it lists 2603 (May 2026) (S217); content newer than its date stamp. Not a factual disagreement, noted for freshness checks. (topic: mecm/versions-lifecycle)
  - Not a factual disagreement; left as a freshness note. (topic: mecm/versions-lifecycle)
  - Reviewed 2026-09-28, not a source disagreement: a stale date stamp; closed.

## mecm2

- Built-in roles with Notify Resource: client-notification.md "Client notification" section (S326) says Full Administrator + Operations Administrator. The same page's "Client diagnostics" section (S326) and whats-new 1810 (S340) say Full Administrator + Infrastructure Administrator. (topic: mecm/client-notification)
  - Re-read 2026-09-27, still open: the live page (updated_at 2026-08-31) still names Full Administrator + Operations Administrator under Client notification and Full Administrator + Infrastructure Administrator under Client diagnostics. (topic: mecm/client-notification)
- AdminService class-name case: overview.md (S300) says class names are case-sensitive. release-notes.md (S306) says the wmi route is case-insensitive from 2006. (topic: mecm/adminservice)
  - Re-read 2026-09-27, still open: the live overview still says class names are case-sensitive and the release notes still say the wmi route is case-insensitive from 2006. (topic: mecm/adminservice)
- SMS_ClientOperation.Priority is "1 Highest, 50 Lowest" (S328), but SMS_ClientOperationStatus.Priority is "1 highest, 10 lowest" (S330). (topic: mecm/client-notification)
  - Re-read 2026-09-27, still open: both live class pages (updated_at 2026-08-28) keep 1-50 and 1-10. (topic: mecm/client-notification)
- Value 8 RequestPolicyNow is listed under PrimaryActionType in SMS_ClientOperation (S328) but under PrimaryActionTargetObjectType in SMS_ClientOperationStatus (S330). (topic: mecm/client-notification)
  - Re-read 2026-09-27, still open: SMS_ClientOperationStatus still lists 8 RequestPolicyNow under PrimaryActionTargetObjectType. (topic: mecm/client-notification)
- Invoke-CMScript (S335): -ScheduleTime is shown as Mandatory:True for all parameter sets, yet it is absent from both syntax blocks and the examples omit it. (topic: mecm/run-scripts)
  - Re-read 2026-09-27, still open: the live page (updated_at 2023-09-20) still marks -ScheduleTime Mandatory: True for (All) parameter sets while neither syntax block lists it. (topic: mecm/run-scripts)
- Tenant-attach troubleshooting pages say "IIS must be installed on provider machine" (e.g. troubleshoot-cmpivot.md), but set-up.md (S301) says IIS is not required from 2010. (topic: mecm/adminservice)
  - Re-read 2026-09-27, still open: tenant-attach/troubleshoot-cmpivot (updated_at 2026-08-31) still says IIS must be installed; set-up (updated_at 2026-08-28) still says IIS is not needed from 2010. Follow set-up.md for 2010 and later. (topic: mecm/adminservice)
- CMPivot permission for a failed AdminService path: cmpivot.md (S315) names HTTP 503 fallback to the SMS Provider (needs SMS Scripts Read). The 2603 KB (S312) also describes a fallback on HTTP 400 parse errors, fixed in 2603. (topic: mecm/cmpivot)
  - Re-read 2026-09-27, still open: the live cmpivot page (updated_at 2026-08-31) still names only the 503 fallback; the 2603 KB (S312) adds the 400 parse-error fallback. Both paths need SMS Scripts Read on the SMS Provider when the fallback happens. (topic: mecm/cmpivot)

## ops

- **Remediations schedule.** deploy-remediations.md offers Once, Hourly and Daily schedules, but the same page says custom script packages "are rerun every 24 hours" (S609). https://raw.githubusercontent.com/MicrosoftDocs/memdocs/4b5429df8b47046c6b251e572ee61199fb5d4a5d/intune/device-management/tools/deploy-remediations.md (topic: intune/remediations)
  - Re-read 2026-09-27, still open: the live page still offers Once, Hourly (less than 24 hours) and Daily and still says custom script packages are rerun every 24 hours. (topic: intune/remediations)
- **Collect diagnostics and Graph.** collect-diagnostics.md says diagnostics "can't be collected or downloaded by calling Microsoft Graph directly". Its reference links still list the Graph actions createDeviceLogCollectionRequest and createDownloadUrl (S616). (topic: intune/collect-diagnostics)
  - Re-read 2026-09-27, still open: the live page (updated_at 2026-08-05) still says diagnostics can't be collected or downloaded through Graph directly and still lists createDeviceLogCollectionRequest, createDownloadUrl, downloadAppDiagnostics and appDiagnostics under Reference links. (topic: intune/collect-diagnostics)
- **MDE machine $filter.** get-machines (S621) lists 14 filterable properties, including aadDeviceId, id, version, deviceValue, machineTags and lastIpAddress. exposed-apis-odata-samples (S628) lists only 8 for Machine and leaves out aadDeviceId. https://learn.microsoft.com/defender-endpoint/api/get-machines vs https://learn.microsoft.com/defender-endpoint/api/exposed-apis-odata-samples (topic: defender/machine-resource)
  - Reviewed 2026-09-28, still open: not re-read; Defender pages stay `quote`.
- **MDE permissions.** get-machines (S621) accepts Machine.Read.All and Machine.Read. get-machine-by-id (S622) lists only Machine.ReadWrite.All and Machine.ReadWrite. (topic: defender/machine-resource)
  - Re-read 2026-09-27, still open: get-machine-by-id still lists only the ReadWrite permissions. (topic: defender/machine-resource)
- **MDE property table vs examples.** rbacGroupId is typed String (S620), but the examples show the number 140 (S621, S622). isAadJoined appears in the examples but not in the property table. (topic: defender/machine-resource)
  - Re-read 2026-09-27, still open: the get-machine-by-id example still shows `"rbacGroupId": 140` and `isAadJoined`. (topic: defender/machine-resource)
- **Device query operators.** The single-device table operators (S612) do not include `summarize`, yet the same page says its aggregation functions work with it. The multi-device page (S613) does list `summarize`. (topic: intune/device-query)
  - Re-read the multi-device side only, 2026-09-27: it still uses summarize in its examples and Known limitations; the single-device page was not re-read. (topic: intune/device-query)
- **Co-management query.** how-to-monitor (S603) lists four SMS_Client_ComanagementState fields: MachineId, MDMEnrolled, Authority and ComgmtPolicyPresent. The WQL in create-queries (S647) also filters on MDMProvisioned, which is not in that list. (topic: intune/co-management)
  - Re-read the how-to-monitor side 2026-09-27 (Learn search): it still lists MachineId, MDMEnrolled, Authority and ComgmtPolicyPresent only. (topic: intune/co-management)

## priorart

- **Presidio org rename.** The brief's clone list and this agent's initial fetch used
  `microsoft/presidio`; the GitHub API now resolves that path to `data-privacy-stack/presidio` (the
  project moved out of the `microsoft` org). Both `prior-art/pseudonymization-tokenization.md` and
  `_sources.csv` (S1005) record the current org (`data-privacy-stack`) while noting
  the fetch was made via the `microsoft/presidio` URL, which GitHub transparently redirects. No
  factual disagreement, just a naming/ownership change worth flagging to other agents citing Presidio
  under the `microsoft` org.
  - Reviewed 2026-09-28, not a source disagreement: a repository move; closed.
- **Snipe-IT org rename.** Same pattern: `snipeio`/`snipe` org references resolve to
  `grokability/snipe-it` in the current GitHub API response (S1012). (topic: prior-art/device-identity-correlation)
  - Reviewed 2026-09-28, not a source disagreement: a repository move; closed.
- **Licence ambiguity via GitHub API.** hashicorp/vault, pyca/cryptography, inspec/inspec,
  fleetdm/fleet and ansible/awx all report `license.spdx_id: NOASSERTION` from the GitHub API despite
  each project publishing a licence file/statement on its own site or repo (Vault: BUSL-1.1 since
  2023; cryptography: dual Apache-2.0/BSD-3-Clause; AWX: Apache-2.0 per project docs). This agent
  recorded the GitHub API's literal answer as UNK/NOASSERTION rather than asserting the believed
  licence without re-fetching each project's own LICENSE file — treat these as needing a LICENSE-file
  check, not as confirmed licences.
  - Resolved 2026-09-28: the LICENSE files were read at pinned commits (S-b43o3ma3, S-6onf7joh, S-tvp7vziq, S-y47upe33, S-lscdap53); see the `reuse` entry below.

## privacy

- Presidio CHANGELOG vs release 2.2.364: the CHANGELOG (S800) has no `[2.2.364]` section. Items that shipped in 2.2.364 per the release notes (S801), e.g. the threshold flag (#2114), PH_UMID (#2045) and the cryptography bump (#2144), sit under `[unreleased]` together with post-release items such as UuidRecognizer (S807). (topic: privacy/presidio)
  - Reviewed 2026-09-28, still open: no new release since 2.2.364 (PyPI, 2026-09-28), so the CHANGELOG still has no section for it.
- EDPB Guidelines 01/2025 consultation end: the news item (S873) says "until 28 February 2025". The consultation page (S872) shows the feedback period "17 January - 14 March 2025". (topic: privacy/gdpr-pseudonymisation)
  - Re-read 2026-09-27, still open: the consultation page and the EDPB consultations list both show 17 January - 14 March 2025 (23:59 CET); the news item keeps 28 February 2025. The consultation page is the operative record. (topic: privacy/gdpr-pseudonymisation)
- spaCy en_core_web_lg versions: GitHub releases have 3.8.0 (2024-09-30, S850). The Hugging Face repo was last modified 2023-11-21 with 3.7.1 (S851). Both say MIT. (topic: privacy/spacy-model-licence)
  - Reviewed 2026-09-28, still open: two distribution channels at different versions; the kb follows GitHub releases.
- Nemotron-PII size: the dataset card (S-dcu4qhyp) says 100,000 records, 50k train and 50k test; the Hugging Face datasets-server `size` endpoint (read 2026-09-27) reports 100,000 rows in each of the train and test splits (200,000 in all). The kb states the card's figure. (topic: privacy/gliner-models)
- NIST SP 800-38G: the page at /pubs/sp/800/38/g/final is the 2016-03-29 version, marked withdrawn (S865). The current final is /upd1/final (S866). Both carry the same number, "SP 800-38G". (topic: privacy/nist-sp800-38g)
  - Reviewed 2026-09-28, not a source disagreement: a withdrawn edition and its update; the kb cites the update. Closed.

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
  - Resolved 2026-09-28: settled by the LICENSE files, now pinned at commits in `_sources.csv`.
- No other disagreements found between sources this session.

## security

### coordinator (crosswalk, coverage, precedence, candidates)

- **Group Policy reapplication vs common belief (and the first draft of `policy-precedence.md`):**
  - The Group Policy processing page states that a client-side extension reapplies settings only when its GPOs or GPO list change (S1592). The Part A first draft had said registry-based policy reapplies at every refresh "by default" [UNK].
  - The official text wins. So DSC drift on a GPO-managed value can persist until the next GPO change or forced refresh. (topic: security/policy-precedence)
  - Reviewed 2026-09-28, not a source disagreement: a corrected draft; the official text is in the article. Closed.
- **LSA protection value meaning:**
  - The Microsoft 24H2 baseline sets `Lsa\RunAsPPL=1` (S1472). The LSA page defines `1` as "with a UEFI variable" and `2` as "without" (S1477).
  - The Windows 11 22H2+ default enablement is without a UEFI variable (S1477). A baseline-conformant device is therefore locked in firmware, and reverting needs the opt-out tool.
  - Not a factual conflict. It is a difference between the default and the baseline that affects rollback. (topic: security/first-baseline-candidates)
  - Reviewed 2026-09-28, not a source disagreement: a default-vs-baseline difference; closed.
- **Intune baseline vs GPO baseline as two writers:** Intune's Windows baseline 24H2 is derived from the same SCT baseline (S1475), and `MDMWinsOverGP` defaults to 0 (S1412). Estates that deploy both have two sources for many values; GP wins for mapped Policy CSP settings. (topic: security/policy-precedence)
  - Reviewed 2026-09-28, not a source disagreement: a design note; closed.
- **Microsoft baseline vs STIG on account lockout:** baseline `LockoutBadCount=10`; STIG `WN11-AC-000010` requires 3 or less. Baseline `LockoutDuration=10`; STIG `WN11-AC-000005` requires 15 minutes or more. (S1472, S1470) (topic: security/settings-crosswalk)
  - Reviewed 2026-09-28, still open: a real policy difference between publishers; the 25H2 and WS2025 2602 baselines keep the same lockout values (crosswalk columns `ms_25h2`, `ms_ws2025`).

### A: device settings catalog

- **CIS Windows 11 Enterprise Benchmark version vs. tested OS release.** Public digests describe
  v5.0.0/v5.0.1 as tested against Windows 11 release 23H2, which matters for any estate targeting
  24H2/25H2. Whether v5.1.0's front matter updates the tested release was not confirmed this pass
  (the CIS PDF itself is behind registration). Flag before citing CIS L1 items as validated for
  24H2/25H2 without checking v5.1.0's own applicability statement. (topic: security/baselines-catalog)
  - Re-read 2026-09-27, still open: CIS's September 2026 update (S-m3qbkeev) lists v5.1.0's changes (Defender AV recommendations moved to their own benchmark, 3 updated, 1 removed) but no tested release; the PDF is behind registration. (topic: security/baselines-catalog)
- No other cross-source disagreement was established this pass (most rows are UNK rather than
  conflicting DOC facts, since the machine-readable sources needed for a real crosswalk were not
  downloaded — see `gaps.A.md`).

### B: management plane

- **Device-log retention below CIS minimum, audit retention above it.** A design that keeps a 400-day audit table comfortably clears CIS Controls v8.1 Safeguard 8.10 (90-day minimum retention for audit logs), but normalized device logs kept only 30 days (diagnostic rather than security logs) sit below that minimum. See `security/logging-monitoring.md` § Conflicts. [DER S1492]
  - Reviewed 2026-09-28, not a source disagreement: a design check, not a source conflict.
- **PyPI Trusted Publishing and self-managed GitLab.** A third-party blog (S1510, COMMUNITY) claims PyPI supports self-managed GitLab. The official *Adding a Trusted Publisher* page (S1597, retrieved 2026-09-24) says only gitlab.com projects are supported, and the official page wins. (topic: security/supply-chain)
  - Re-read 2026-09-27, now a PyPI-internal disagreement: PyPI's own blog (S-5ry5zerr, 2025-11-10) and 2025 review (S-cos7wdpw) confirm the GitLab Self-Managed beta, and Warehouse supports custom GitLab issuers (CODE S-5t26tmbz); the user docs (S1597) and troubleshooting page still say gitlab.com only. The article states both; the blog is the newer statement. (topic: security/supply-chain)

### C: frameworks, regulation, AI

- (Resolved 2026-09-24) CIS Controls v8.1 licence (CC BY-NC-ND 4.0, no derivatives) [DOC S1563]: the
  `framework-control-map.csv` rows now use safeguard IDs plus a short own-words paraphrase instead of the
  official safeguard titles, matching the treatment of CIS Benchmark recommendation IDs elsewhere in the kb
  (part A). (topic: security/framework-control-map)
- No direct DOC-vs-DOC factual conflicts found in Part C's sources; the EU AI Act Digital Omnibus deferral dates
  come from law-firm/community summaries (S1558, S1559) rather than the consolidated regulation text itself,
  since EUR-Lex had not yet published a consolidated version reflecting Regulation (EU) 2026/1744 at retrieval
  time — flagged as `COMMUNITY`, not `DOC`, for that reason, not because sources disagree. (topic: security/privacy-compliance)
  - Resolved 2026-09-26: EUR-Lex now publishes Regulation (EU) 2026/1744 (S-qzdkyvqx) and a consolidated AI Act dated 2026-07-27; the deferral dates are cited as DOC S-qzdkyvqx. (topic: security/privacy-compliance)

## prior-art/drift-detection

- Puppet latest_release: `prior-art/projects.csv` says 7.34.0 (2024-10-22) [S1008], but puppetlabs/puppet also has tag 8.10.0 (2024-10-18) and RubyGems published 7.34.0 and 8.10.0 on the same day, 2024-10-22. The recorded value is presumably GitHub's latest-release marker, which could not be re-read on 2026-09-25 (api.github.com blocked). Decide whether the column means GitHub's marker or the highest released version. (census 2026-09-25)
  - Resolved 2026-09-26: `latest_release` is GitHub's latest-release marker (api.github.com `releases/latest`), which still reads 7.34.0 (published 2024-10-22); newer tags on other release lines do not change it. Value confirmed. (topic: prior-art/drift-detection)
- Chef InSpec latest_release: `prior-art/projects.csv` says v5.24.24 (2026-06-25) [S1009], while the repo has tags v7.2.2, v7.3.0 and v7.3.1 (2026-09-22 to 2026-09-24). RubyGems' newest 7.x is 7.2.1 (2026-09-02) under LicenseRef-Chef-EULA, while 5.x gems are Apache-2.0. GitHub's latest-release marker could not be re-read (api.github.com blocked). (census 2026-09-25)
  - Resolved 2026-09-26: GitHub's latest-release marker still reads v5.24.24 (2026-06-25); the v7.x tags are not marked latest. Value confirmed. (topic: prior-art/drift-detection)
- The Ansible check-mode fact in `prior-art/drift-detection.md` is tagged [DOC S1009], but S1009 is the inspec/inspec repository metadata, which says nothing about Ansible. The fact needs an Ansible documentation source, or should become [UNK]. (census 2026-09-25)
  - Resolved 2026-09-26: re-sourced to Ansible's check-mode page (S-e4iemhin) and corrected: modules without check-mode support report nothing and do nothing (not "skipped or run for real"). (topic: prior-art/drift-detection)
- reuse/drift-detection.md:37 (outside this unit) lists Test-DSCConfiguration as Microsoft365DSC's drift-only mode; not stated by S1010 or S-2fvvbt5t (the M365DSC drift page describes LCM drift checks logged to the M365DSC event log). (topic: prior-art/drift-detection)
  - Resolved 2026-09-28: Microsoft365DSC's own docs name `Test-DSCConfiguration` for self-orchestrated drift monitoring (S-qlnd73w2), and the Learn page says it only tests and returns True/False (S-fylt7wwn); `prior-art/drift-detection.md` carries both as DOC, so the table row stands. (topic: prior-art/drift-detection)

## prior-art/tiered-approval-ops

- Teleport latest_release: `prior-art/projects.csv` says v18.10.0 (2026-07-09) [S1017], but gravitational/teleport has tags v18.10.7, v18.11.0 and v18.11.1 (2026-09-16), all older than the kb's 2026-09-24 retrieval. The value is presumably GitHub's latest-release marker, which could not be re-read on 2026-09-25 (api.github.com blocked). (census 2026-09-25)
  - Resolved 2026-09-26: GitHub's latest-release marker still reads v18.10.0 (2026-07-09); v18.10.7 to v18.11.1 are tags without the marker. Value confirmed. (topic: prior-art/tiered-approval-ops)

## prior-art/mcp-microsoft-endpoint-mgmt

- The fact that the modelcontextprotocol/modelcontextprotocol and python-sdk repositories do not list Microsoft endpoint-management servers is tagged [DOC S1019], but S1019 is microsoft/mcp's metadata and servers/ listing, which cannot support it. It needs its own source, or should become [UNK]. (census 2026-09-25)
  - Resolved 2026-09-26: the fact is tagged `[UNK]` until a source reads those two repositories. (topic: prior-art/mcp-microsoft-endpoint-mgmt)

## intune/win32-apps

- Win32 supersedence graph limit: `add-win32` (rechecked 2026-09-26) says both "There's a maximum of 10 updated or replaced apps, including references to other apps" and, in a Note, "a maximum of 10 nodes in a supersedence relationship" [DOC S-wc6e3fba], while `configure-win32-supersedence` (rechecked 2026-09-26) says "There can only be a maximum of 11 nodes in a single supersedence graph" [DOC S-vywsads7]. Still a live disagreement — both pages are current and neither has been reconciled. The dependency limit on `add-win32` is internally consistent on recheck: "a maximum of 100 dependencies, which include the dependencies of any included dependencies, as well as the app itself" matches the worked example "100 dependency apps + 1 parent app = graph size 101" (the graph size is 101, not the dependency count). Treat 10 and 100 (including the parent) as the safe limits until Microsoft reconciles the pages. (rechecked 2026-09-26, kept) (topic: intune/win32-apps)

## intune/compliance-policies

- `windows10CompliancePolicy` Graph resource shape: the v1.0 resource page (rechecked 2026-09-26) lists exactly 19 settable properties (password rules, `bitLockerEnabled`, `secureBootEnabled`, `codeIntegrityEnabled`, `earlyLaunchAntiMalwareDriverEnabled`, OS version bounds, `storageRequireEncryption`) [DOC S-taatt73w], while the beta resource page for the same type name (rechecked 2026-09-26) still adds `tpmRequired`, `activeFirewallRequired`, `defenderEnabled`, `defenderVersion`, `signatureOutOfDate`, `rtpEnabled`, `antivirusRequired`, `antiSpywareRequired`, `deviceThreatProtectionEnabled`, `deviceThreatProtectionRequiredSecurityLevel`, `configurationManagerComplianceRequired`, `validOperatingSystemBuildRanges`, `memoryIntegrityEnabled`, `kernelDmaProtectionEnabled`, `virtualizationBasedSecurityEnabled`, `firmwareProtectionEnabled`, `deviceCompliancePolicyScript`, `wslDistributions` and `roleScopeTagIds` [DOC S-2hhj3k5f]. Every one of these beta-only properties corresponds to a setting the admin center UI exposes today (`compliance-policy-create-windows`, S-qjd54t3z), so v1.0 cannot express most Windows System Security / Defender / Configuration Manager compliance settings via Graph; automation needs the beta endpoint (or the UI) for those settings until Microsoft ships them to v1.0. Still a live gap on recheck — no v1.0 update found. (rechecked 2026-09-26, kept) (topic: intune/compliance-policies)

## entra/agent-id

- Copilot Studio automatic-Agent-ID cutover date: "Recreate Copilot Studio agents in Microsoft Entra Agent
  ID" states agents created before **2026-03-18** use legacy app registrations, while "Microsoft Entra
  Agent IDs for Copilot Studio agents" (`admin-use-entra-agent-identities`) and "Migrate Copilot Studio
  agents to Microsoft Entra Agent ID" (`govern-migrate-api-entra-agent-identity`) both state the cutover
  for automatic creation (opt-out removed) was **"May 2026"** — re-confirmed 2026-09-26 on both pages. A
  third page, "What's new in Copilot Studio" (`whats-new`), separately states "Starting in July 2026,
  Copilot Studio automatically creates a Microsoft Entra Agent ID for every new agent, and you can no
  longer opt out at the environment level" — a third distinct date for what reads as the same "opt-out
  removed" milestone. All three are current Microsoft Learn pages; which date is authoritative (or
  whether they describe staged/ring-based rollout rather than one cutover) is unresolved. Re-searched
  2026-09-26: `admin-use-entra-agent-identities` also now separately states, under "Opt out of automatic
  agent identity creation," "Starting May 2026, all new agents have Microsoft Entra Agent IDs, and you can
  no longer opt out of automatic agent identity creation" — the same page therefore repeats "May 2026" for
  the opt-out-removed milestone while `whats-new` still says "July 2026"; no reconciling What's new/release
  note for either date was found. (rechecked 2026-09-26, kept unresolved) (topic: entra/agent-id)
  - Re-checked 2026-09-27 (Learn search): admin-use-entra-agent-identities still says 'Starting May 2026, all new agents have Microsoft Entra Agent IDs'; no release note reconciles the three dates. Still open. (topic: entra/agent-id)
- Microsoft Learn search index (2026-09-27) still returns the overview page with the PREVIEW banner, while the live page and What's new (S-ifhonpv7) say Entra Agent ID is generally available; the Entra what's-new lists 'General Availability - Microsoft Entra Agent ID platform' in April 2026. (topic: entra/agent-id)

## agents/windows-agentic-platform

- Recall availability default: Policy CSP `WindowsAI\AllowRecallEnablement` (rechecked 2026-09-26) still
  documents, in its own descriptive text, "By default, Recall is disabled for managed commercial devices.
  Recall isn't available on managed devices by default, and individual users can't enable Recall on their
  own," while the same page's **Description framework properties** table still states "Default Value: 1"
  and "1 (Default) | Recall is available." — the CSP page now contradicts itself directly (not just against
  the separate "Manage Recall" guide, which repeats the same "disabled by default" wording). Still a live
  disagreement; treat Recall as off-by-default on any Intune/GPO-managed device regardless of the table's
  stated default value. (rechecked 2026-09-26, kept) (topic: agents/windows-agentic-platform)
- `DisableClickToDo` applicability: rechecked 2026-09-26 — the Policy CSP page still lists this policy's
  **Applicable OS** as "Windows Insider Preview" only (no stable OS/KB build given), while the companion
  "Manage Click to Do" admin article (rechecked 2026-09-26) still documents it and its Settings UI toggle
  ("By default, Click to Do is enabled for users") without a preview caveat, alongside Copilot+ PC hardware
  requirements that are themselves GA. Until the CSP page adds a stable-build requirement, treat
  `DisableClickToDo` itself as preview even though Click to Do the feature is GA on Copilot+ PCs. (rechecked
  2026-09-26, kept) (topic: agents/windows-agentic-platform)

## security/vulnerability-prioritization

- BOD 22-01 status: CISA's KEV catalog page (fetched 2026-09-26) states the catalog now implements
  **BOD 26-04**, and the BOD 22-01 directive page itself states BOD 22-01 "has been revoked as of June 10, 2026,
  and is superseded by BOD 26-04." The research brief that requested this topic named BOD 22-01 as the
  remediation-timeline authority; that is now historical, not current. Both the historical BOD 22-01 timelines
  (2 weeks / 6 months) and the current pointer to BOD 26-04 are recorded in the article; BOD 26-04's own
  remediation timelines were not separately researched. (topic: security/vulnerability-prioritization)
  - Resolved 2026-09-26: BOD 26-04 Table 1 read from the directive (S-c22robk5) and added to the article; its tiers are 3 days plus forensic triage, 3, 14 and 60 calendar days, and fix on system upgrade (read from the Table 1 image by the census; a first attempt that day through a page summarizer gave invented 7/30/90-day rows, committed in cd847fa and replaced). The BOD 22-01 timelines stay as history. (topic: security/vulnerability-prioritization)

## intune/linux-management

- Linux platform-support version lists disagree across current Microsoft Learn pages (rechecked 2026-09-26 by
  full-page fetch, not just search snippets — a search-index snippet for the custom-compliance-settings page
  briefly appeared to show a third, older list of "Ubuntu Desktop 22.04/24.04 LTS, RHEL 8/9," but a direct
  fetch of that same live URL confirms it currently reads "Ubuntu Desktop, version 24.04 LTS or 26.04 LTS;
  RedHat Enterprise Linux 9; RedHat Enterprise Linux 10," matching the enrollment/compliance-settings/
  custom-compliance-discovery-scripts pages — the search snippet was stale, not a real second source): the
  custom Bash script article ("Use custom Bash scripts to configure Linux devices in Microsoft Intune") still
  lists prerequisites verbatim as "Linux Ubuntu Desktop, RedHat Enterprise Linux 8, or RedHat Enterprise Linux
  9," while the enrollment, compliance-settings, and custom-compliance-settings articles all currently agree
  on Ubuntu Desktop 24.04 LTS/26.04 LTS, RHEL 9, RHEL 10 (RHEL 8 support ending July 2026 per the What's new
  page). The Bash-script article remains the stale outlier. (rechecked 2026-09-26, kept) (topic:
  intune/linux-management)

## windows/powershell-7

- PowerShell end-of-support dates: the Microsoft Lifecycle "Products" page for PowerShell gives retirement
  timestamps one calendar day later than the PowerShell Support Lifecycle page for the same releases (PT
  vs a plain date, e.g. 7.4/7.5 "11/11/2026 6:59:59 AM" vs "10-Nov-2026"; 7.2 "11/9/2024" vs "08-Nov-2024";
  7.0 "12/4/2022" vs "03-Dec-2022"). Rechecked 2026-09-26: the Support Lifecycle page (`powershell-support-lifecycle`)
  still lists 7.4 and 7.5 end-of-support as "10-Nov-2026" with no time zone stated in the table itself, while the
  article records (per S-7rfzq5p7) that the Lifecycle Products page states its dates are shown in Pacific Time
  (PT); "11/11/2026 6:59:59 AM" PT converts to 2026-11-11 14:59:59 UTC, i.e. just after midnight UTC on
  2026-11-11 — one calendar day later than the Support Lifecycle page's plain "10-Nov-2026" because the two
  pages are using different time zones/rounding for what is otherwise the same underlying end-of-support
  instant, not necessarily a factual disagreement about the support window itself. Both are current Microsoft
  pages; the article uses the Support Lifecycle page's plain dates in its Reference table and CSV, and records
  both along with the PT explanation. (rechecked 2026-09-26, kept — explained as a TZ/rounding artifact, not
  resolved to a single date) (topic: windows/powershell-7)
- Telemetry opt-out: the Differences page (S-awsrthdz) says telemetry can only be disabled with POWERSHELL_TELEMETRY_OPTOUT, while about_Telemetry (S-62djuv2f) adds the Windows "Send optional diagnostic data" setting from PowerShell 7.6.2. The kb now states both, each with its own source. (topic: windows/powershell-7)
  - Reviewed 2026-09-28, still open: not re-read; the kb states both with their sources.

## auth/ntlm-deprecation

- S1200's _sources.csv row says 'published 2025-09-24'; the fetched page's postTime is 2026-01-29 (read 2026-09-27). Row date should be corrected by the census owner. (topic: auth/ntlm-deprecation)

## agents/agent-overuse-patterns

- S2174 (dev.to decision matrix) disagrees with itself: it puts the pipeline at 50,000 runs/day at ~$1.50/day for 3,000 tokens/run and ~$15/day for 30,000 tokens/run (10x), but later calls the 30,000-token case 'roughly 15x more'. Re-read 2026-09-27. (topic: agents/agent-overuse-patterns)

## agents/azure-openai-deployments

- S-pntdruql (azure/ai-foundry/openai/concepts/provisioned-throughput, fetched 2026-09-27) no longer contains the utilization / leaky-bucket section that Learn search still indexes under azure/foundry/.../provisioned-throughput#monitor-utilization-and-performance; the same content is now on how-to/provisioned-get-started (S-gueirwxw). Facts re-cited there. (topic: agents/azure-openai-deployments)

## agents/content-safety-prompt-shields

- Blocklist matching: the kb said exact-match or regex; the custom-categories page (S-plv2ekwg) says blocklists allow only exact text matching and no image matching. Corrected to exact-match only. (topic: agents/content-safety-prompt-shields)
  - Resolved 2026-09-28: a kb correction already made; closed.

## agents/shared-ner-service

- Resolves the 'Azure Text PII character-limit figures' entry: S2093 (concepts/data-limits) re-read 2026-09-27 states no 50,000-character analyze-with-warning behaviour and no 10 MB document limit. It gives 5,120 characters per document for synchronous requests (over-length documents get an invalid-document error, others still processed), 5 PII documents and 1 MB per request, and 125,000 characters across up to 25 documents asynchronously (one over-length document fails the whole request with 400). The 50,000 figure is now an UNK line in the article. (topic: agents/shared-ner-service)

## auth/sql-authz

- auth/sql-authz.md:14 says on-prem SQL Server Entra authentication 'requires the instance to be Arc-enabled'; S1207 (Microsoft Entra authentication for SQL Server overview, re-read 2026-09-27) has a section 'Setting up Microsoft Entra authentication without Azure Arc' for SQL Server on Windows (manual certificates, registry, app registration). Arc remains required for SQL Server 2025's primary managed identity (S1206). arch/sql-auth-containers.md and arch/workload-identity-onprem-k8s.md were corrected; auth/sql-authz.md was outside this unit. (topic: auth/sql-authz)
  - Closed 2026-09-27: auth/sql-authz.md now says Arc is not required on Windows (manual setup exists) and is required for the SQL Server 2025 primary managed identity. (topic: auth/sql-authz)

## agents/instruction-and-context-limits

- Copilot Studio instructions limit: Microsoft documents 8,000 characters (S1960, S-jexpr3gv); a community article (S1843) says some configurations enforce 2,000 characters after deployment, citing a Microsoft Q&A thread. (topic: agents/instruction-and-context-limits)
  - Reviewed 2026-09-28, still open: official limit vs a community report; a deployed agent test would settle it.

## agents/a2a-protocol

- A2A Agent Card well-known path: the A2A spec (S2120) registers `/.well-known/agent-card.json`, while Microsoft Copilot Studio's A2A connector docs (S2126, re-read 2026-09-27) tell makers to find the card at the endpoint plus `/.well-known/agent.json`. (topic: agents/a2a-protocol)
  - Explained 2026-09-27, still open: the A2A v0.3.0 release notes (S-xasyjfgi, 2025-07-30) changed the well-known URI from `agent.json` to `agent-card.json`, so the Copilot Studio page gives the pre-v0.3.0 path; the Learn page, re-read 2026-09-27, still says `agent.json`. Kept until Microsoft updates it. (topic: agents/a2a-protocol)

## agents/docs-maintenance-agents

- S1808 (cognition.com/blog/deepwiki) now shows the date 05.05.25 and only a short launch note; the article's applies_to and the _sources.csv row say a 2025-04-25 launch post. The detailed claims once cited to it (LLM + code analysis, graph representation, PR/git history/team discussions, 'cycle of implementing code from documentation') are no longer on the page and are now UNK leads. (topic: agents/docs-maintenance-agents)
  - Closed 2026-09-27: the unsupported claims were removed from the article; the graph and scoring description now rests on a COMMUNITY summary of a Cognition talk (S-rqjvl632), and the PR/team-discussion and code-docs cycle claims were dropped (no first-party source; the Cognition blog renders no body without JavaScript). (topic: agents/docs-maintenance-agents)

## agents/foundry-agent-service

- The Foundry capability reference (S-eh6okx77) marks Browser automation, Computer use, Image generation, SharePoint and Fabric connectors, Fabric IQ and Work IQ as preview; the kb table had them as GA. The capability reference says preview status can vary by feature, region and API version, so per-tool pages remain the authority. (topic: agents/foundry-agent-service)
  - Reviewed 2026-09-28, still open: not re-read; per-tool pages remain the authority.

## auth/configmgr-rbac-auth

- The kb derived that Microsoft's enterprise access model treats ConfigMgr-like estate-wide device/config control as control-plane (Tier 0) equivalent; re-read 2026-09-27, S1210 defines the control plane as access control based on centralized enterprise identity systems and the management plane as enterprise-wide IT management functions, which on its wording places ConfigMgr in the management plane. The articles now call control-plane treatment a local judgement; _answers.md QA17 still carries the old derivation. (topic: auth/configmgr-rbac-auth)
  - Resolved 2026-09-27: the AD DS tier model (S-7nbamxyc) puts systems that patch or run agents on Tier 0 identity systems in Tier 0 and IT management of Tier 1 servers in Tier 1; the articles and QA17 now apply that test (DER). (topic: auth/configmgr-rbac-auth)

## auth/ldap-smb-signing

- SMB signing default on Windows Server 2025: S1202 (Control SMB signing behavior) says Windows Server 2025 requires outbound signing only; S1228 (SMB security hardening, HEAD 2026-09) says starting with Windows 11 24H2 and Windows Server 2025 all outbound and inbound SMB connections must be signed by default. Kb keeps S1202's outbound-only for Server 2025. (topic: auth/ldap-smb-signing)
  - Re-read 2026-09-27, still open: S1203 (Microsoft blog) and S-77zvblfr (SMB features, updated 2025-11-27) also say outbound only for Server 2025; S1228 alone says outbound and inbound. The kb keeps outbound-only. (topic: auth/ldap-smb-signing)
- SMB encryption default on Windows Server 2025 / Windows 11 24H2: the SMB features page (S-77zvblfr, updated 2025-11-27) has a table row saying encryption is required by default for all outbound client connections, while S1228 says encryption isn't mandatory by default and S1203 says it is not required by default. The kb keeps not-mandatory. Found 2026-09-27. (topic: auth/ldap-smb-signing)

## auth/propagation-latency

- Cloud Sync interval: the Cloud Sync FAQ (S1280) says user and group provisioning is scheduled approximately every 10 to 20 minutes, while What is Cloud Sync (S-2vza23mx) says the provisioning service synchronizes every two minutes. Both read 2026-09-27; the kb table states both. (topic: auth/propagation-latency)
- TGT renewal window: the VPN group-membership support article (S-ffrzumip) says a TGT can be renewed for 10 days, while the Kerberos policy page (S-fn2rot77) gives 7 days as the default for Maximum lifetime for user ticket renewal. Both read 2026-09-27; the kb keeps 7 days as the policy default. (topic: auth/propagation-latency)

## auth/group-claims

- Implicit-flow group limit: S1284 (Configure group claims) says five groups and hasgroups only above five; S1285 (Zero Trust: group claims and app roles) says six groups for the implicit flow. (topic: auth/group-claims)
  - Re-read 2026-09-27, still open: a third Microsoft page, Customize tokens (S-azppyixp), says six for implicit grant in a hybrid flow; S1284 still says five. (topic: auth/group-claims)

## entra/connect-and-cloud-sync

- Cloud Sync device synchronization: the decision guide (S-6q5tyxki, updated 2026-06-15) marks device synchronization / hybrid join as not currently supported in Cloud Sync, while device-sync.md (S550, ms.date 2026-07-21) documents Cloud Sync device sync in preview (AD2AADDeviceSync job, disabled by default, devices can become hybrid joined). Likely the guide predates the preview; lines 14/24 (S-6q5tyxki) and 37 (S550) now state each source as written. (topic: entra/connect-and-cloud-sync)
  - Re-read 2026-09-27, still open: the decision guide (updated_at 2026-06-15, unchanged) still lists Device Synchronization among Connect-only capabilities and routes hybrid-join device sync to Connect, while the device sync page documents the preview. (topic: entra/connect-and-cloud-sync)

## gitlab/protected-branches-tags

- S444 (protected.md @56c82a97) is internally inconsistent on an unconfigured 'Allowed to push and merge': the Push and merge permissions table says 'No one can push' (and the Developer table shows no direct push), but a note on the same page says an unconfigured setting 'does not restrict push access' and must be set to 'No one' explicitly. protected-branches-tags.md line 22 follows the table. (topic: gitlab/protected-branches-tags)

## auth/workload-identity

- GitLab flexible federated identity credential claims: the flexible FIC page (S1294) lists only `sub` (eq, matches) and `project_id` (eq) as supported and requires sub plus project_id for mutable subjects; the mutable-subjects page (S1278) says a GitLab flexible FIC must match sub and one or more of project_id, namespace_id, user_id, and shows examples using namespace_id and user_id. Both re-read 2026-09-27. (topic: auth/workload-identity)
  - Re-read 2026-09-27: unchanged on both live pages (S1294 updated 2026-09-23; S1278 updated 2026-07-30). (topic: auth/workload-identity)

## intune/platform-scripts

- S-p4fis3e4 (run-powershell-scripts-windows) says devices only registered with Microsoft Entra ID don't receive scripts, while S-ta4g5get (management-extension-windows) lists Microsoft Entra registered/workplace-joined devices among IME prerequisites; both re-read 2026-09-27. (topic: intune/platform-scripts)

## graph/permissions

- Permissions reference (S524) says application Device.ReadWrite.All does not allow device deletion, but the Delete device permissions include (S515) lists Device.ReadWrite.All as the application permission for DELETE /devices/{id}. Recorded in graph/permissions.md:24. (topic: graph/permissions)
  - Reviewed 2026-09-28, still open: not re-read; a tenant test of DELETE with Device.ReadWrite.All would settle it.

## graph/microsoft365dsc

- Microsoft365DSC release 1.26.909.1 ships MOF-based function resources (S-3aphi7n2), while the Dev branch at 2026-09-26 has converted resources to class-based [DscResource()] classes without .schema.mof (S-omyb2en3); facts about resource shape depend on version. (topic: graph/microsoft365dsc)
  - Re-checked 2026-09-28, still stands: 1.26.909.1 is still the latest release, and `MSFT_AADUser` on Dev (70a46e5b) still has no `.schema.mof`. Settles when a release ships the class-based resources. (topic: graph/microsoft365dsc)

## intune/ios-android-management

- Minimum iOS version for account driven user enrollment: the Apple enrollment guide (S-wdoafrjc) says "Starting with iOS 13 and newer", while the Apple User Enrollment overview (S-7synnxi2) and the account-driven setup page (S-fdtw5sil) say iOS/iPadOS 15 or later (14.9 and earlier fall back to user enrollment with Company Portal). Kb follows 15+. (topic: intune/ios-android-management)
  - Reviewed 2026-09-28, still open: not re-read; the kb follows 15+.
- End of Intune support for Android device administrator on GMS devices: the Android enrollment guide (S-3v22wodo) says August 2024; the device administrator page (S-pcr6rjdl) says end of 2024. Both re-read 2026-09-27. (topic: intune/ios-android-management)

## prior-art/secret-vault-encryption

- reuse/secret-vault-encryption.md:22 (outside this unit) still states age has no expiry/revocation/audit log as confirmed by its own README; S1001 README re-read 2026-09-27 does not state it (now UNK in prior-art/secret-vault-encryption.md). (topic: prior-art/secret-vault-encryption)

## security/policy-precedence

- Policies-key cleanup: the FSLogix Group Policy page (S-z4y7mew3) says settings under `HKLM\SOFTWARE\Policies\FSLogix\ODFC` reset themselves when the GPO is removed or set to *Not Configured*; the `Remove-GPRegistryValue` page (S-is2wluoa) says removing a registry-based policy setting (example under `...\Policies\...`) from a GPO does not delete the value on clients, and the setting must be disabled to delete it. Both read 2026-09-27; the pages describe different actions (GPO removed vs one setting removed from a GPO that still applies) but no page states the general rule. (topic: security/policy-precedence)

## security/privacy-compliance

- AI Omnibus political agreement date: privacy-compliance.md:74-76 (COMMUNITY S1558) says provisional agreement 2026-05-06; the Commission page S1557 re-read 2026-09-27 says a political agreement was reached on 7 May 2026 (and entry into force 27 July 2026). (topic: security/privacy-compliance)
  - Re-read 2026-09-27, still open: the Commission press release IP/26/1024 (S-tzbutlvs, published 2026-05-07 07:59 CEST) says the agreement was "reached today"; the Council release (dated 2026-05-07 in its url, a search snippet says 6 May) could not be read past its browser check. The article now leads with the Commission's date and keeps S1558's 6 May as COMMUNITY. (topic: security/privacy-compliance)

## windows/azure-arc-servers

- The Azure SDK AgentConfiguration model (S-75xvev6g) describes agent configuration properties as settable 'locally via the azcmagent config command, or remotely via ARM', while Extensions security for Azure Arc-enabled servers (S-efadnhwv) says the local agent security controls can only be set on the server itself and can't be modified from Azure. (topic: windows/azure-arc-servers)
  - Re-checked 2026-09-28, still stands: the Az.ConnectedMachine models mark `guestConfigurationEnabled` read-only (no create or update) and the security pages (S-efadnhwv, S-wvoeevrw) say the controls are set only on the machine, while the Python SDK docstring still says ARM can set them. (topic: windows/azure-arc-servers)
- Machine Configuration parameter types: S-nibv7ci5 says Azure Policy parameters passed to guest assignments must be string (no arrays); S-lkmpjpnp (create-policy-definition) lists String, Boolean, Double and Float as supported parameter value types. Re-read 2026-09-27. (topic: windows/azure-arc-servers)
- Azure Arc gateway status: S-wwbtoald (agent-overview) still calls it 'Limited preview'; the kb had stated GA with no source (now UNK). S-szyeetyp only says it reduces required endpoints. Re-read 2026-09-27. (topic: windows/azure-arc-servers)
  - Resolved 2026-09-28 in favour of GA: agent release notes version 1.58 (November 2025, S-jduwmt53) remove the Preview flag because the gateway was promoted to General Availability, and the Arc gateway page (updated 2026-05-19) carries no preview label; agent-overview (updated 2026-07-28) still says "Limited preview", a stale label. (topic: windows/azure-arc-servers)

## security/supply-chain

- PyPI's Adding a Trusted Publisher page (S1597) says GitLab self-managed instances are not supported, while Socket (S1510, 2025-11-14) reports PyPI opened a beta for GitLab Self-Managed with manual onboarding. (topic: security/supply-chain)
  - See the re-read note above: the beta is confirmed by PyPI itself (S-5ry5zerr); the docs page is out of date. (topic: security/supply-chain)
  - Reviewed 2026-09-28, not a source disagreement: duplicate of the supply-chain entry above, which records PyPI's own blog confirming the beta.

## windows/bitlocker

- BitLocker CSP ConfigureRecoveryPasswordRotation default (S-pfrwongj): prose says not configured = rotation on for Entra ID only and off on hybrid; the value list labels 2 as 'Default value'; the description-framework table gives Default Value 0. Re-read 2026-09-27. (topic: windows/bitlocker)
- Automatic device encryption prerequisite: S-sr7tk6jz requires Modern Standby AND HSTI compliance (1703+); S-jdytzqlj and S-7qrbvran say Modern Standby OR HSTI (removed entirely in Windows 11 24H2 per S-7qrbvran). Re-read 2026-09-27. (topic: windows/bitlocker)

## windows/delivery-optimization

- DOCacheHost with several Connected Cache servers: the DO reference (S-7olkz3h6) says clients round-robin across connection attempts and can download from several cache servers simultaneously; the Policy CSP note (S-3dmxye5u) says clients don't talk to several servers at once and round-robin until one connects; the configure page (S-kyd2lkfv) says clients connect in list order. (topic: windows/delivery-optimization)
  - Reviewed 2026-09-28, still open: not re-read; three pages describe the behaviour differently. A lab capture would settle it.
- MCC HTTPS: the secure-content-delivery page (S-s4n26zjf) still says nodes use HTTP and HTTPS support is planned; the HTTPS overview (S-umnfbn5b) says since GA nodes can be configured for HTTPS (Intune Win32 apps and Teams). (topic: windows/delivery-optimization)
  - Reviewed 2026-09-28, still open: Learn search shows the secure-content-delivery page still says HTTPS support is planned, while the HTTPS overview describes GA HTTPS for Win32 apps and Teams.

## windows/laps

- Invalid ADPasswordEncryptionPrincipal: Configure policy settings for Windows LAPS (S-twjwzzdw) says the Domain Admins default applies only when unset and an invalid name causes a policy processing failure with no backup; the LAPS CSP page (S-jmzxsdjr) says the device falls back to Domain Admins. (topic: windows/laps)
  - Reviewed 2026-09-28, still open: Learn search shows both pages unchanged: the LAPS CSP page says the device falls back to Domain Admins; the policy settings page says a policy processing failure occurs.

## windows/windows-update-management

- Windows 10 consumer ESU end date: the kb said security updates through 2026-10-13; the consumer ESU page (S-fllu73v2, re-read 2026-09-27) now says the program and coverage run through 2027-10-12. Fact corrected from the source; the Learn ESU page (S-hdprezk3) gives no consumer end date. (topic: windows/windows-update-management)

## intune

- Endpoint analytics in Adoption Score: the Intune page (S-m5aovwzr, updated_at 2026-04-09) still describes the Adoption Score Endpoint analytics page (score, 180-day trend, startup performance), while the Microsoft 365 Adoption Score page (S-3l57sxrb, updated_at 2026-09-23) says Endpoint analytics was retired from Adoption Score starting 2026-01-22, complete February 2026. The newer M365 page is the likelier current state. (topic: intune/device-inventory-analytics)
  - Reviewed 2026-09-28, still open: not re-read; the newer Microsoft 365 page is followed.
- Linux personal devices: the end-user page Enroll Linux device in Intune (S-dnply3ya, updated_at 2026-04-29) says enrolled Linux devices are corporate-owned and personal devices aren't supported, while the admin deployment guide (S-5vopvhhm) and platform guide (S-nvad3j6y) say employees can enroll their personal Linux devices. (topic: intune/linux-management)
  - Reviewed 2026-09-28, still open: not re-read.

## entra

- Blueprints per pro-code agent: the Agent 365 Copilot Studio identity page (S-ketmxnue, updated_at 2026-05-19) says each pro-code agent has its own blueprint, while Entra's planning guide (S-3tt3ywvk, updated_at 2026-08-14) defaults to one blueprint per trust boundary with several agent identities under it. Follow the Entra guide for design; the Agent 365 sentence reads as a simplification. (topic: entra/agent-id)
  - Reviewed 2026-09-28, still open: not re-read; the Entra guide is followed for design.

## windows/smart-app-control

- Smart App Control re-enable path: the Learn developer pages say SAC can only be enabled on a clean install (S2198) and that Off and On are one-way in Settings (S2199), while the March 2026 update note KB5079391 (S-5zawgrph) and the consumer FAQ (S-n2kx46hd) say SAC can now be turned on or off without a clean install. The rollout is gradual, so both hold on different builds until the Learn pages are updated. Read 2026-09-28. (topic: windows/smart-app-control)

## arch/sql-auth-containers

- ODBC `ActiveDirectoryDefault`: the Microsoft SQL driver feature matrix (S-g2zvqta5) marks "Microsoft Entra default Azure authentication" as not supported by the ODBC driver on Windows or Linux/macOS, and the ODBC `Authentication` keyword list (S1610) has no `ActiveDirectoryDefault`, while the mssql-django Entra page (S-67zasdym) shows `Authentication=ActiveDirectoryDefault` with ODBC Driver 18 and says mssql-django 1.7.3+ passes it through to the driver. Read 2026-09-28; a driver test settles it. (topic: arch/sql-auth-containers)

## windows/windows-sandbox

- Printer redirection and video input defaults in the WindowsSandbox Policy CSP: the page (S-bgz3uymb) says that when `AllowPrinterRedirection` or `AllowVideoInput` is not configured the capability is disabled, and the .wsb page (S-hlmmxoye) agrees for a default sandbox, yet the same CSP page lists `Default Value` 1 (allowed) for both. It also maps `AllowWriteToMappedFolders` to the Group Policy name and registry value `AllowMappedFolders`. Read 2026-09-28; a device test (registry and sandbox behaviour with the policy unset) settles it. (topic: windows/windows-sandbox)
