# Conflicts (both sources linked)

Merged from `_parts/<agent>/conflicts.md`.

## agents-a2a-cache

- **Anthropic cache-read price multiplier for the newest model tier.** `platform.claude.com/docs/en/build-with-claude/prompt-caching` (S2130) states a range of "0.05x-0.025x" base input price for "Claude Opus 5.5, Fable 5.1, Mythos 5.1" reads, distinct from "0.1x" for other models. The same page's own worked example for Opus 5.5 computes cache read at "$0.20/MTok" against a "$4/MTok" base input, which is exactly 0.05x, not the lower bound of the stated range (0.025x). `platform.claude.com/docs/en/about-claude/pricing` (S2131) was fetched to cross-check but the exact per-model read multiplier was not independently re-extracted from it in this session. Recorded here rather than resolved; a task that needs the exact number should re-fetch S2131 directly for the model in question. [DOC S2130 vs itself; S2131 unconfirmed] (topic: agents/agent-caching)
  - Resolved 2026-10-08: both pages, read raw, state the same per-model multipliers in a footnote: 0.05x on Claude Opus 5.5 and Claude Sonnet 5.5 ($0.20 and $0.10 per MTok), 0.025x on Claude Fable 5.1 and Claude Mythos 5.1, 0.1x for all other models. [DOC S2130, S2131] (topic: agents/agent-caching)
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
  - Reviewed 2026-10-21, not a source disagreement: S1961 states the unit rename to Copilot Credits and S1960 keeps "message pack" as the capacity-tier label, so both names are current for different things. [DOC S1960, S1961]

### MCP transport support

S1964 (ms.date 2026-05-28) states Copilot Studio "supports the Streamable transport type" and "no
longer supports SSE for MCP after August 2025." No conflicting page was found; this is included
here only because a search snippet independently surfaced the same claim, confirming it is not a
one-off wording accident. [DOC S1964]

No other direct factual conflicts between official sources were found in this part's source set. (topic: agents/copilot-studio-inventory)
  - Reviewed 2026-10-21, not a source disagreement: one source (S1964) states the Streamable-only transport and no page read contradicts it; a record of a corroborating search snippet, not a conflict. [DOC S1964]

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
  - Resolved 2026-10-21: the memory page (S1863, read in full in the census of 2026-10-21) documents the 200-line target and the 4 MiB skip and no kilobyte warning; the kb states the ~40KB figure as refuted in `agents/instruction-and-context-limits` and keeps the old csv row superseded. [DOC S1863]

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
  - Still open 2026-10-21: re-checked the Copilot Studio prompt-modification page (S-jexpr3gv; a Learn search of 2026-10-21 returns "Prompt instructions are limited to 8,000 characters") and found no Microsoft page that names the combined-prompt ceiling the failures report (S-f3chtt24 about 5,300 characters). A Microsoft page naming that ceiling, or a deployed Copilot Studio test agent with instructions near 5,000 characters, would settle it.

### GitHub Copilot custom-instructions limit: "silently ignored" (docs) vs. "no limit now" (changelog) are not in
tension — sequential, not contradictory
The removal of the 4,000-character limit (S1852, dated 2026-06-12) supersedes the earlier documented behavior (S1851
describes the pre-removal silent-truncation behavior). Not a conflict, but flagged because a session reading only the
older cached version of S1851 could believe the limit still applies; both sources' dates should be checked before
citing GitHub Copilot's instructions handling. (topic: agents/instruction-and-context-limits)
  - Reviewed 2026-10-21, not a source disagreement: the changelog (S1852, 2026-06-12) removes the limit that the older page (S1851) describes, so the two statements are sequential; the article carries both dates. [DOC S1851, S1852]

## agents-eval

### OpenAI evals: framework vs. hosted platform lifecycle
`developers.openai.com/api/docs/guides/evaluation-best-practices` (S1894), read on 2026-09-25, states the
hosted Evals **platform** goes read-only 2026-10-31 and shuts down 2026-11-30, while the open-source
`openai/evals` **repository** (S1893) shows no such deprecation notice and remains a live GitHub project.
These are two different things under one brand name (a hosted product being sunset vs. an open-source
framework/registry that is not), not a genuine disagreement — flagged here so a later reader does not
conflate "OpenAI evals is being deprecated" with the open-source framework used in QG9's tool list. (topic: agents/agent-evaluation)
  - Reviewed 2026-10-21, not a source disagreement: S1894 describes the hosted Evals platform and S1893 the open-source repository, two different things under one brand; the article keeps them apart. [DOC S1893, S1894]

### garak's licence: code vs. site content
The garak GitHub repository's own `LICENSE` file (S1891) is GPL-3.0. A WebSearch summary separately
described "content on the garak site" (garak.ai) as Apache-2.0. Both claims can be true at once (dual
licensing of code vs. marketing/docs site prose is common), but the Apache-2.0 claim was not independently
re-fetched from garak.ai in this pass — see `gaps.md`. Not treated as a contradiction, but flagged so the
Apache-2.0 claim is not repeated as a `DOC` fact about the *code*.
Resolved in the census of 2026-09-25: the LICENSE file at `main` is the Apache License 2.0, as are the README badge
and `pyproject.toml`; the repository moved from a brief GPLv3 licence to Apache-2.0 in June 2023. The GPL-3.0 reading
was wrong and the kb now says Apache-2.0. [DOC S1891] (topic: agents/agent-evaluation)
  - Resolved 2026-10-21: the LICENSE file of the repository (S1891) is the Apache License 2.0 and `agents/agent-evaluation` states Apache-2.0 for the code; the GPL-3.0 reading was wrong. [DOC S1891]

## agents-extra

- `opentelemetry.io/docs/specs/semconv/gen-ai/` and its `gen-ai-agent-spans`/`gen-ai-spans` sub-pages now display a
  "moved" notice pointing at a new, separate repository `open-telemetry/semantic-conventions-genai`
  (retrieved 2026-09-25), superseding the GenAI section that previously lived inside
  `open-telemetry/semantic-conventions` (used by `claude/otel-monitoring.md` and `logs/` for the general
  logs/code conventions, which have not moved). Cite the new repo (S2001-S2004) for GenAI-specific spans/metrics;
  the old repo commits already in `_sources.csv` (S639-S646) remain correct for logs/code conventions only.
  - Reviewed 2026-10-21, not a source disagreement: a repository move for the GenAI conventions only; `agents/genai-telemetry` cites the new repository (S2000, S2001) and the old one stays correct for logs and code conventions. [DOC S2000, S2001]
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
  - Resolved 2026-10-21: the cloud service's limits are on the Azure Language data-limits page (S2093, confirmed in the census of 2026-10-21): 5,120 characters per synchronous document and 125,000 characters across up to 25 documents asynchronously; the container limit (S2091) is a separate feature path, and the 50,000-character figure belongs to the Azure AI Search PII skill (S-ulqlpnc5). [DOC S2091, S2093, S-ulqlpnc5]
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
  - Reviewed 2026-10-21, not a source disagreement: a fixed bug the routines page itself reports for builds before v2.1.211, kept so an older cached copy is not misread; no second source differs. [DOC S1803]

### routine fire-payload trust framing changed
The same page states that before Claude Code v2.1.213, a routine's saved prompt was delivered to the session framed as an *untrusted background notification* (and could be refused), whereas v2.1.213+ delivers it as the session's *assigned task*. An agent-runtime description written against a pre-2026-04 build of Claude Code would describe the opposite trust behaviour from what ships now. [DOC S1803] (topic: agents/headless-agent-runtimes)
  - Reviewed 2026-10-21, not a source disagreement: the routines page itself dates the change of framing to v2.1.213; a version difference, not two sources differing. [DOC S1803]

### no cost-cap flag despite brief expecting one
The deepening-pass brief asked to cover a `--max-budget-usd` flag "if exists" for Claude Code headless mode. The `headless.md`, `github-actions.md`, and `gitlab-ci-cd.md` pages (retrieved 2026-09-25) named no such flag; the only cost controls they named were `--max-turns`, job/workflow timeouts, concurrency limits, and post-hoc `total_cost_usd` reporting via `--output-format json`. This was not a disagreement between sources but an absence on those three pages. [DOC S1800,S1801,S1802] Resolved 2026-10-12: the CLI reference page (S1824) documents `--max-budget-usd` (print mode only): it stops the run once estimated spend reaches the amount, counts subagent spend, can be passed by spend (the page advises leaving headroom) and from v2.1.217 fails a further subagent spawn with `Budget limit reached`; the headless page (S1800) now names it too. The GitHub Actions and GitLab CI/CD pages (S1801, S1802) still do not. The kb states it in `agents/headless-agent-runtimes.md:52`. [DOC S1824,S1800] (topic: agents/headless-agent-runtimes)
  - Resolved 2026-10-21: the CLI reference (S1824, read in full in the census of 2026-10-21) documents `--max-budget-usd` for print mode and the kb states it in `agents/headless-agent-runtimes`; the absence was a gap of three pages, not a disagreement. [DOC S1824, S1800]

### GitHub's own doc-drift pattern lives outside Copilot coding agent
GitHub's official Copilot coding-agent best-practices page names no scheduled/issue-triggered documentation-update feature, while GitHub Next's separate `gh-aw` project ships a "Documentation Maintenance" sample workflow doing exactly that. A session reading only the Copilot coding-agent docs would conclude GitHub has no such capability; it exists, but under a different GitHub-affiliated project with its own trigger/guardrail model (`schedule:` frontmatter + safe-outputs, not Copilot's issue-assignment model). [DOC S1818, S-qso27noq, S1821] (topic: agents/docs-maintenance-agents)
  - Resolved 2026-09-27: GitHub's Copilot docs now include "About GitHub Agentic Workflows" (S-h6jpev6e, public preview), with documentation upkeep as a listed use case, so the pattern is now documented by GitHub itself. (topic: agents/docs-maintenance-agents)

## arch

### containers, gMSA, workload identity

None found. AWS's `credentials-fetcher` (COMMUNITY, S1607/S1608) does not contradict Microsoft's own Linux Kerberos docs (S1605, S1606) — it fills a gap Microsoft's own docs leave open (gMSA-to-Linux-keytab) rather than disagreeing with them. Flagging as a gap, not a conflict, since Microsoft makes no claim in either direction about gMSA-on-Linux beyond silence.
  - Reviewed 2026-10-21, not a source disagreement: the entry records a gap (Microsoft's Linux Kerberos pages are silent on gMSA-to-keytab; the AWS tool is COMMUNITY), so no two sources differ and none can settle it. [COMMUNITY S1607, S1608; DOC S1605, S1606]

### tooling, texts, readiness

No direct factual conflicts found between official sources in this batch.
  - Closed 2026-10-21: a record that no two sources disagree in this batch, with no claim to settle.

- `arch/twelve-factor-readiness.md`: Kubernetes official docs treat Secrets-as-env-vars and
  Secrets-as-mounted-files as equally valid (S1725, S1729), which is weaker than a stricter
  no-secrets-in-env-of-child-processes policy some teams adopt. This is not a conflict between sources — it is
  a stricter house policy going further than the platform requires — but is worth flagging since a reader
  might expect K8s docs to mandate the stricter file-based pattern and they do not.
  - Reviewed 2026-10-21, not a source disagreement: the entry itself says a stricter house policy goes further than the platform; the Kubernetes pages (S1725, S1729) treat both secret delivery forms as valid and no page says otherwise. [DOC S1725, S1729]

## auth

### on-prem / Windows / ConfigMgr / SQL

- None identified this session for the topics researched (kerberos, ntlm-deprecation, ldap-smb-signing, gmsa-dmsa, configmgr-rbac-auth, sql-authz, ad-jit-membership). No two official sources were found to disagree; the ConfigMgr-NTLM community forum report (S1213) is consistent with, not contradicting, the official 2509 release note (S307) — it just adds real-world fallout detail.
  - Closed 2026-09-28: a no-conflict record for an old session.

### Entra / Graph / MSAL / GitLab

None found this pass. No direct contradiction surfaced between the sources fetched (S1270-S1292);
several items are simply undocumented (see gaps.md) rather than disagreeing.
  - Closed 2026-10-21: a record that no two sources disagree in this batch; the undocumented items it mentions are gaps in `_gaps.md`, not conflicts.

### keys, propagation, revocation, audit, threats

- CAE scope wording: the CAE concept page (S1347) says the initial implementation covers Exchange Online, Teams and SharePoint Online, while the CAE developer guidance and claims-challenge pages (S1354, S1355) say Microsoft Graph sends claims challenges and honours critical events for clients that declare `cp1`. Reading both: automatic critical-event enforcement is documented for the three services; Graph enforcement is opt-in per client. [DER S1347,S1354,S1355] (topic: auth/token-lifetimes-cae)
  - Resolved 2026-09-27: the same pinned page (still the live commit) also says Exchange Online, SharePoint Online, Teams and MS Graph evaluate key Conditional Access policies themselves, and the Zero Trust CAE page (S-yc5geeul) describes Graph checking Entra's token events; "initial implementation" is history, not a limit, so the pages agree. (topic: auth/token-lifetimes-cae)
- No source-vs-source factual conflicts were found in this agent's own research (key management, propagation latency, revocation, audit events, threats).
  - Closed 2026-09-28: a no-conflict record for an old session.

## dsc

- **3.3.0 release notes vs 3.3.0 binaries.** S118 lists MCP `--what-if` (#1697), the Group Policy template adapter (#1686), the environment variable resource (#1675), File/Content (#1676), UpdateList `--what-if` (#1616) and the `--required-version` rename (#1610). None of these are in the 3.3.0 zip or binary (S114, S116); all except the GP adapter are in 3.4.0-preview.1 (S115, S117). (topic: dsc/releases-feature-matrix)
  - Reviewed 2026-09-28, still open: fixed release artifacts; the kb follows the binaries. Closes only if the release notes are edited.
  - Still open 2026-10-21: re-read the v3.3.0 release (S118, GitHub releases API, published 2026-09-17, last updated the same day): its notes still list #1697, #1686, #1675, #1676, #1616 and #1610 and its `target_commitish` is still `main`. The zip and binary (S114, S116) are fixed artifacts. Only an edit of the release notes or a rebuilt 3.3.0 artifact would settle it; the kb follows the binaries.
- **Git tag `v3.3.0` vs the shipped 3.3.0 source.** The tag points at main 4b49240, where `dsc/Cargo.toml` = `3.4.0-preview.1` (S110). The 3.3.0 binaries match `release/v3.3` ea572fa, `3.3.0` (S111, S144). The release has `target_commitish: main` (S113). (topic: dsc/releases-feature-matrix)
  - Reviewed 2026-09-28, still open: the tag and the release branch are fixed history; the kb follows `release/v3.3`.
  - Still open 2026-10-21: re-read the GitHub releases list (S113): v3.3.0 still has `target_commitish: main` and was published 2026-09-17, and the `release/v3.3` branch head is still `ea572fa` (S144, branch API). A release retargeted at `release/v3.3` or a moved tag would settle it; the kb follows `release/v3.3`.
- **3.4.0-preview.1 release notes vs zip.** S119 lists "Add Group Policy template adapter"; the adapter is in source (S121) but absent from `data.build.json` (S120) and from the zip (S115). (topic: dsc/releases-feature-matrix)
  - Reviewed 2026-09-28, still open: fixed release artifacts; the kb follows the zip.
  - Still open 2026-10-21: re-read the v3.4.0-preview.1 release (S119, published 2026-09-10, not updated since): its notes still list "Add Group Policy template adapter" (#1686). `data.build.json` on current main names no Group Policy adapter either, as the pinned copy (S120) does not. An edit of the notes or a packaging entry for the adapter would settle it; the kb follows the zip.
- **PROMPT.md premise vs evidence.** The prompt says the Group Policy adapter shipped in 3.4.0-preview.1. The zip (S115) and packaging list (S120) show it did not. (topic: dsc/releases-feature-matrix)
  - Reviewed 2026-09-28, not a source disagreement: a brief's premise, not a source; the kb follows the zip. Closed.
- **`directives.version` docs/tests vs behaviour.** The CLI help (S116) and the type docs (S104) imply matching against the dsc version. The engine compares against the dsc-lib crate version 3.2.0 (S102, S112), so `'>=3.3, <3.4'` fails on dsc 3.3.0 (observed, S116). The tests (S123) do not catch it. (topic: dsc/directives)
  - Reviewed 2026-09-28, still open: behaviour observed on 3.3.0; needs a lab run on a later release to see whether it is fixed.
  - Still open 2026-10-21: re-read the engine on current main. `lib/dsc-lib/src/configure/mod.rs` (S102) now has `Configurator::new_with_dsc_version`, whose comment says the version validates the `version` directive, while `Configurator::new` still uses the `dsc-lib` crate version; commit b1105122 of 2026-10-14, "(GH-1735) Fix directives version against running dsc version (#1744)", made the change, and the Pester test file on main (S123) now checks the directive against `dsc --version`. Both released builds (v3.3.0 published 2026-09-17, v3.4.0-preview.1 published 2026-09-10) predate that commit, and the releases list shows no later release, so no released build is known to carry the fix. Running a release built after 2026-10-14 with `directives.version: '>=3.3, <3.4'` on a 3.3.x host would settle it for that release; the kb follows the 3.3.0 behaviour.
- **SemanticVersionReq type docs vs binary.** S104 says bare versions without an operator, `x` wildcards and build metadata are forbidden. The 3.3.0 binary accepts `'3.3'`, `'1.x'`, `'3.3.0+abc'` in `directives.version` (S116). (topic: dsc/directives)
  - Reviewed 2026-09-28, still open: needs a lab run on a later release.
  - Still open 2026-10-21: re-read the type docs on current main (`semantic_version_req.rs`, S104; last commit 2026-09-16): they still say build metadata, a wildcard-only requirement and a comparator without an operator are forbidden. The 3.3.0 binary result (S116) stands as observed, and the releases list shows no release after v3.3.0 to run. Running a build from main with `'3.3'`, `'1.x'` and `'3.3.0+abc'` in `directives.version` would settle it.
- **Static published schemas vs engine schemas.** Repo bundled `config/document.json` (S146; build config `version: v3.1.0`, S137) has no `directives` property. `dsc schema -t configuration` from the 3.3.0 binary (S116) has it. The binary's `$schema` enum also has no v3.3 URI. (topic: dsc/schemas)
  - Reviewed 2026-09-28, still open: the published schema is still the v3.1.0 build per the pinned sources; recheck at the next schema publish.
  - Still open 2026-10-21: re-read the repo schema on current main: `schemas/v3/bundled/config/document.json` (S146; last commit 2025-08-22) still has the top-level properties `$schema`, `parameters`, `variables`, `resources` and `metadata` and no `directives`, and the schema build config (S137) still says `version: v3.1.0`. The 3.3.0 binary's own schema (S116) is unchanged. A schema regeneration that adds `directives` would settle it.
- **Learn CLI exit codes vs code.** The Learn page (S135, ms.date 2025-03-25) documents exit codes 0 to 6. The code (S101) defines 0 to 10 (7 resource not found, 8 assertion failed, 9 server failed, 10 Bicep failed). (topic: dsc/cli-reference)
  - Reviewed 2026-09-28, still open: Learn search (dsc-3.0 view) still lists exit codes 0 to 6.
  - Still open 2026-10-21: re-read both: the Learn source (S135, PowerShell-Docs-DSC main, last commit 2026-05-20) still documents exit codes 0 to 6, and `dsc/src/util.rs` on current main (S101) still defines 0 to 10 (`EXIT_DSC_RESOURCE_NOT_FOUND` 7, `EXIT_DSC_ASSERTION_FAILED` 8, `EXIT_SERVER_FAILED` 9, `EXIT_BICEP_FAILED` 10). An edit of the Learn exit code table would settle it.
- **Repo doc title vs CLI.** `docs/reference/cli/server/index.md` (S136) documents `dsc mcp`. The 3.3.0 command is `dsc server` with alias `mcp` (S100, S116). (topic: dsc/mcp-server)
  - Reviewed 2026-09-28, still open: not re-read; the kb follows the binary (`dsc server`, alias `mcp`).
  - Still open 2026-10-21: re-read both on current main: `docs/reference/cli/server/index.md` (S136, ms.date 06/17/2026) is still titled and written for `dsc mcp`, and `dsc/src/args.rs` (S100) still defines the command as `name = "server"` with `alias = "mcp"`. A rename of the doc page would settle it; the kb follows the binary.
- **3.3.0 UpdateList manifest key.** The 3.3.0 `windowsupdate.dsc.resource.json` uses `preTest: true` (S114); the engine's field is `implementsPretest` (S105). 3.4.0-preview.1 uses `implementsPretest` (S115). (topic: dsc/manifests-diff)
  - Reviewed 2026-09-28, still open: fixed in 3.4.0-preview.1; a 3.3.0 artifact that stays as shipped.
  - Narrowed 2026-10-21: the `windowsupdate.dsc.resource.json` on current main (`resources/WindowsUpdate`) uses `implementsPretest`, as 3.4.0-preview.1 (S115) does, so the mismatch is confined to the 3.3.0 artifact (S114), which stays as shipped; the kb states each version's key.

## ident

- Graph device `extensionAttributes`: listed on the v1.0 resource page (S504) but not declared on the v1.0 CSDL `device` EntityType (S500); declared in beta CSDL (S501). (topic: graph/csdl-device)
  - Reviewed 2026-09-28, still open: CSDL not re-downloaded; needs a fresh `$metadata` read.
  - Still open 2026-10-21: re-read the sources: the v1.0 annotated CSDL (S500, msgraph-metadata master, repository head of 2026-10-20) still declares no `extensionAttributes` on the `device` EntityType, the beta CSDL (S501) still declares it, and the v1.0 resource page (S504, docs-contrib main) still lists `extensionAttributes` ("Contains extension attributes 1-15 for the device"). A v1.0 `$metadata` that declares the property, or the page dropping it, would settle it.
- managedDevice `$filter` notes: out-of-line CSDL Annotations (S500) state `$filter` for `azureADDeviceId`, `serialNumber`, `deviceName`, `model`, `manufacturer`, `operatingSystem`, `userPrincipalName` and others; the inline CSDL descriptions and the v1.0 resource page (S506) don't. Flagged per row in graph/csdl-managedDevice.properties.csv.
  - Reviewed 2026-09-28, still open: CSDL not re-downloaded; per-row flags stay in the CSV.
  - Still open 2026-10-21: re-read the sources: the v1.0 annotated CSDL (S500, master of 2026-10-20) still carries out-of-line `$filter` annotations on many `managedDevice` properties (for example `azureADDeviceId` 'eq', `serialNumber` 'eq' and 'or', `deviceName` 'eq' and 'contains', `userPrincipalName` 'eq' and 'ne'), while the v1.0 resource page (S506, docs-contrib main) states `$filter` on only 6 of its property rows and on none of those four. A live `GET /deviceManagement/managedDevices` with each filter would show which properties accept one; per-row flags stay in the CSV.
- managedDevice entity set description (S500) says combinations "must use 'and', not 'or'", while property annotations (S500) state "Supports $filter operator 'eq' and 'or'". (topic: graph/csdl-managedDevice)
  - Reviewed 2026-09-28, still open: CSDL not re-downloaded; test with a live tenant query to settle.
  - Still open 2026-10-21: re-read the v1.0 annotated CSDL (S500, master of 2026-10-20): the `microsoft.graph.managedDevice` description still says combinations of filtered properties "must use 'and', not 'or'", while property annotations (for example `serialNumber`, `manufacturer`, `operatingSystem`, `complianceState`) still say "$filter operator 'eq' and 'or'". A live query with two filtered properties joined by `or` in a lab tenant would settle it.
- Graph device `id`: `$filter` support stated on resource page (S504), not in CSDL (S500). (topic: graph/csdl-device)
  - Reviewed 2026-09-28, still open: CSDL not re-downloaded.
  - Still open 2026-10-21: re-read the sources: the v1.0 resource page (S504, docs-contrib main) still says `id` "Supports `$filter` (`eq`, `ne`, `not`, `in`)", and the v1.0 annotated CSDL (S500, master of 2026-10-20) has no annotation targeting `device/id`, `directoryObject/id` or `entity/id`. A live `GET /devices?$filter=id eq '<id>'` in a lab tenant would settle it.
- Device deletion: manage-device-identities (S546, ms.date 2026-06-17) calls deletion "a nonrecoverable activity"; device soft delete preview (S547, ms.date 2026-04-05) keeps deleted devices recoverable for 30 days. (topic: entra/stale-devices)
  - Re-read 2026-09-27, still open: manage-device-identities (updated_at 2026-08-25) still calls deletion a nonrecoverable activity and does not mention the soft-delete preview. (topic: entra/stale-devices)
  - Narrowed 2026-10-21: re-read both live pages. manage-device-identities (S546) still says deleting a device "Is a nonrecoverable activity" and does not mention soft delete. The soft delete page (S547) is still labelled preview, keeps a deleted device recoverable for up to 30 days, and lists its limits: no portal experience during the preview, restore through PowerShell or Microsoft Graph, and older Azure AD Graph APIs that can still hard delete. The pages read as describing the general behaviour and the preview behaviour, and neither says which one a tenant gets. Deleting a test device in a lab tenant and listing deleted devices through Microsoft Graph would settle it.
- Hybrid device ID origin: sync references map objectGUID to deviceID (S549, S550); the registration flow says DRS "creates a device ID" (S548) and Graph says deviceId is set by DRS at registration (S504). (topic: entra/hybrid-deviceid-objectguid)
  - Re-checked 2026-09-27 (Learn search): no page reconciles the sync mapping with DRS 'creates a device ID'. Still open. (topic: entra/hybrid-deviceid-objectguid)
  - Still open 2026-10-21: re-read the device registration page (S548) and the Connect attribute page (S549). The managed hybrid join flow still says Connect sends userCertificate, object GUID and computer SID to Azure DRS, which creates the device object, and later that Azure DRS "creates a device ID"; the attribute table still lists objectGUID as "Also called deviceID"; the federated flow adds that writeback returns a device object "that includes the object GUID". No page says whether the DRS-created device ID equals the AD objectGUID. Comparing the objectGUID of a hybrid joined lab computer in AD with the DeviceId in `dsregcmd /status` and the deviceId in Microsoft Graph would settle it.
- LDAP MaxValRange: ntdsutil article (S569) gives default 1,500; S570 says Windows Server 2008 R2+ hard-codes a maximum of 5,000 overriding higher policy values (different quantities, not a direct contradiction; listed for clarity). (topic: ad/ldap-paging-filters)
  - Reviewed 2026-09-28, not a source disagreement: different quantities (default vs hard cap); closed.
- Licence of microsoftgraph/microsoft-graph-docs-contrib: `LICENSE` is CC BY 4.0, `LICENSE.md` is CC BY-NC-ND 3.0 US (both at commit 4ad99fd37a9e). Only facts and short quotes from this repo are stored in kb.
  - Reviewed 2026-09-28, still open: two licence files in one repository; the kb keeps facts and short quotes only.
  - Still open 2026-10-21: re-read the repository on its main branch: `LICENSE` is still "Attribution 4.0 International" (CC BY 4.0) and `LICENSE.md` still says the repository is licensed under Creative Commons Attribution-NonCommercial-NoDerivs 3.0 United States; the GitHub API licence field of the repository reads `cc-by-4.0`. A single licence file or a statement from the maintainers would settle it; the kb keeps facts and short quotes only.

## infra

- gMSA host support: S400 (manage gMSA) says gMSA works on "Any Windows Server domain-joined server". S403 (understand service accounts, choosing table) shows gMSA "No" for "App runs on Windows Server". One of the two cells is wrong. (topic: windows/gmsa)
  - Reviewed 2026-09-28, still open: Learn search shows the understand-service-accounts table still has gMSA 'No' for 'App runs on Windows Server' while the manage-gMSA page says any Windows Server domain-joined server.
  - Still open 2026-10-21: re-read both pages on current main of the Windows Server docs repo: manage gMSA (S400) still lists a gMSA as usable on "Any Windows Server domain-joined server", and understand service accounts (S403) still has "App runs on Windows Server" = No for gMSA (Yes for sMSA and virtual accounts, No for dMSA), while its own gMSA paragraph describes server farms. A correction of the S403 table cell would settle it.
- PowerShell `Default` execution policy: S420 (about_Execution_Policies 7.5) says `Default` = RemoteSigned for Windows clients and servers, yet the same page says all-Undefined gives Restricted on clients. S421 (5.1) says Default = Restricted on clients and RemoteSigned on servers. (topic: windows/execution-policy-signing)
  - Reviewed 2026-09-28, still open: Learn search (about_Execution_Policies, 7.6 view) still says `Default` is RemoteSigned for clients and servers and all-Undefined gives Restricted on clients.
  - Still open 2026-10-21: re-read both pages on current main of the PowerShell docs repo: about_Execution_Policies 7.5 (S420) still says `Default` is RemoteSigned for Windows clients and servers and, in its `Undefined` item, that all-Undefined gives Restricted on clients and RemoteSigned on Windows Server; the 5.1 page (S421) still says `Default` is Restricted for clients and RemoteSigned for servers. Running `Set-ExecutionPolicy Default -Scope LocalMachine` and then `Get-ExecutionPolicy` in PowerShell 7.5 on a Windows client in a lab would settle it.
- ConfigMgr PowerShell execution policy values: S423 (client settings) documents three values (Bypass, Restricted, All Signed; default All Signed). S425 (SMS_ConfigMgrClientAgentConfig WMI, ms.date 2016) lists only 0=Bypass and 1=Restricted. (topic: windows/execution-policy-signing)
  - Reviewed 2026-09-28, still open: not re-read; the WMI class page is dated 2016.
  - Still open 2026-10-21: re-read both on Learn (the repo paths of the pinned rows now return 404 on main, so the live pages were read): About client settings (S423, last updated 2025-12-08) still lists Bypass, Restricted and All Signed with the default All Signed, and the `SMS_ConfigMgrClientAgentConfig` page (S425, last updated 2022-10-04) still lists only 0 Bypass and 1 Restricted for `PowerShellExecutionPolicy`. Setting All Signed in a lab hierarchy and reading the property would settle it.
- sp_cleanup_temporal_history scope: S462's front matter monikerRange is Azure SQL DB / Fabric only, but its applies-to include (`sqlserver2017-asdb-asdbmi-fabricsqldb`) names SQL Server 2017+ and MI. (topic: sqlserver/temporal-tables)
  - Reviewed 2026-09-28, still open: not re-read; a front-matter metadata mismatch.
  - Still open 2026-10-21: re-read `sys.sp_cleanup_temporal_history` on the live branch of the SQL docs repo (S462, ms.date 06/19/2026): the front matter `monikerRange` is still `=azuresqldb-current || =fabric-sqldb`, and the applies-to include is still `sqlserver2017-asdb-asdbmi-fabricsqldb`. A metadata edit of one of the two would settle it.
- GitLab Runner licence: S416 (runner repo LICENSE) is MIT for the whole repo with no docs exception. The GitLab monorepo LICENSE (S452) puts `doc/` under CC BY-SA 4.0, and docs.gitlab.com is published under CC BY-SA. Runner docs were treated as CC BY-SA (summarized only). (topic: windows/gitlab-runner-windows)
  - Reviewed 2026-09-28, still open: two licence statements; the kb keeps summaries only.
  - Still open 2026-10-21: re-read both licence files: the runner repository `LICENSE` (S416, main) still opens as MIT with no docs exception, and the GitLab repository `LICENSE` (S452, master) still puts `doc/` under CC BY-SA 4.0. No source says which applies to the runner's documentation pages; the kb keeps summaries only.
- GitLab Runner `--password`: the CLI help (S413) says "(required)". Issue 27895 (S414, COMMUNITY) says it isn't required for a gMSA. (topic: windows/gitlab-runner-windows)
  - Reviewed 2026-09-28, still open: official help vs a community issue; a lab registration with a gMSA would settle it.
  - Still open 2026-10-21: re-read both: `commands/service.go` on the runner main branch (S413) still describes the install `--password` flag as "Specify user password to install service (required)", and the issue API (S414) shows issue 27895 closed, last updated 2023-09-21, with no statement of a change to that flag. A registration with a gMSA in a lab would settle it.

## later

- Graph TCM `configurationMonitor.status`: beta reference page (S945) lists only `active`, `unknownFutureValue`; v1.0 page (S944) and both CSDLs (S956, S957) include `inactive`. (topic: graph/tcm-apis)
  - Reviewed 2026-09-28, still open: the v1.0 page still lists `active`, `inactive`, `unknownFutureValue`; the beta page was not re-read.
  - Still open 2026-10-21: re-read the sources: the v1.0 page (S944, docs-contrib main) lists `active`, `inactive`, `unknownFutureValue`; the beta page (S945) still lists only `active`, `unknownFutureValue`; both CSDLs (S956, S957, master) list `active`=0, `inactive`=1, `unknownFutureValue`=2. An edit of the beta page would settle it.
- Graph TCM `snapshotJobStatus`: reference page (S946) says `partiallySuccessful` is an evolvable member after `unknownFutureValue` needing `Prefer: include-unknown-enum-members`; CSDL (S956) orders `partiallySuccessful`=4 before `unknownFutureValue`=5. (topic: graph/tcm-apis)
  - Reviewed 2026-09-28, still open: not re-read; enum order in CSDL vs page text.
  - Still open 2026-10-21: re-read the sources: the `snapshotJobStatus` text on the v1.0 page (S946, docs-contrib main) still lists `partiallySuccessful` after `unknownFutureValue` and says to send `Prefer: include-unknown-enum-members` to get it, while both CSDLs (S956, S957, master) still order `partiallySuccessful`=4 before `unknownFutureValue`=5. A live job-status read with and without the header would settle whether the member is returned by default.
- Graph TCM `monitorMode` enum values differ between v1.0 CSDL (`monitorOnly`=0, `unknownFutureValue`=1) and beta CSDL (`monitorOnly`=1, `unknownFutureValue`=5) (S956 vs S957). (topic: graph/tcm-apis)
  - Reviewed 2026-09-28, still open: CSDLs not re-downloaded; v1.0 page still lists `monitorOnly`, `unknownFutureValue`.
  - Still open 2026-10-21: re-read the CSDLs on master: v1.0 (S956) still has `monitorOnly`=0, `unknownFutureValue`=1 and beta (S957) `monitorOnly`=1, `unknownFutureValue`=5, while the v1.0 and beta pages (S944, S945) both list `monitorOnly`, `unknownFutureValue` with no numbers. A change to one CSDL would settle it.
- Graph TCM delegated permissions: setup page (S941) says delegated monitor management needs "any privileged role"; per-API permission tables (S951, S952) name delegated scopes `ConfigurationMonitoring.Read.All`/`ReadWrite.All`. Likely both apply; not stated together. (topic: graph/tcm-apis)
  - Reviewed 2026-09-28, still open: the Get and Update pages still list delegated `ConfigurationMonitoring.*` scopes; the setup page's role requirement was not re-read.
  - Still open 2026-10-21: re-read the sources on docs-contrib main: the setup page (S941) still lists "Any privileged role" for delegated monitor management and snapshots, and the permission includes (S951, S952) still list delegated `ConfigurationMonitoring.Read.All` / `ReadWrite.All` for work or school accounts; no page says whether a delegated call needs both. A delegated call with the scope and no privileged role in a lab would settle it.
- Get-GPOReport (S920): OUTPUTS says "None", but description and example 3 say the report is written to the display without `-Path`. (topic: gpo/gpo-export)
  - Re-read 2026-09-27, still open: the live windowsserver2025-ps page still says Outputs None / 'This cmdlet does not generate any output'. (topic: gpo/gpo-export)
  - Still open 2026-10-21: re-read the live Get-GPOReport page (S920): OUTPUTS still says "None", while the description and example 3 still say that without `-Path` the report is written to the display. No other page says what the cmdlet returns without `-Path`; running `$r = Get-GPOReport -Name <gpo> -ReportType Xml` with the GroupPolicy module and checking `$r.GetType()` would settle it.
- Gateway service account page (S909): recommends the gateway app over services.msc for changing the account, but the gMSA procedure on the same page uses services.msc. (topic: powerbi/on-prem-gateway-sql)
  - Reviewed 2026-09-28, still open: not re-read; an internal inconsistency on one page.
  - Still open 2026-10-21: re-read the page (S909, last updated 2025-06-30): it still recommends the gateway app over the Windows Services app for changing the service account, and its gMSA procedure still has you open `services.msc`. Only a page edit would settle it.
- Power BI refresh limit wording: S901 says "Power BI Pro: up to 8"; S900 says "shared capacity: eight". Same number, different basis (licence vs capacity). (topic: powerbi/scheduled-refresh)
  - Reviewed 2026-09-28, not a source disagreement: same number on two bases; closed.
- RLS page (S910): says RLS can be configured in Desktop or the service, but also says roles previously defined in the service must be re-created in Desktop. (topic: powerbi/row-level-security)
  - Reviewed 2026-09-28, still open: not re-read; an internal inconsistency on one page.
  - Still open 2026-10-21: re-read the page (S910, last updated 2026-05-13): it still says RLS for imported semantic models can be configured in Desktop or the service, and its limitations still say roles defined in the service must be re-created in Desktop. Defining a role in the service and opening the published model in Desktop in a lab would settle it.

## mcp

- ZDR scope for Claude Code: code.claude.com ZDR page (S748) says ZDR for Claude Code is "available to qualified accounts on Claude for Enterprise"; platform.claude.com API retention page (S749) also lists Claude Code with API keys from a Commercial organization as covered. Differs in whether non-Enterprise API-key use is in scope (S748 mentions existing pay-as-you-go ZDR only as a migration path). (topic: claude/data-retention)
  - Resolved 2026-09-28: not a disagreement. The Privacy Center ZDR article (S-qrxvz4ph, 2026-06-09) lists both routes: products that use a Commercial organization's API key, including Claude Code through the API, and Claude Code for Enterprise plans. The code.claude.com page describes the Enterprise route and names pay-as-you-go API-key ZDR as a migration source. (topic: claude/data-retention)
- Claude Code docs (S740) confirm a default MCP output cap of 25,000 tokens, and add a fixed 10,000-token warning and per-tool `anthropic/maxResultSizeChars` override (not a conflict, recorded for completeness). (topic: mcp/python-sdk)
  - Reviewed 2026-10-21, not a source disagreement: the entry itself says it records an addition to the 25,000-token cap, not a conflict. [DOC S740]
- A project pinning `mcp>=2.2,<2.3` would need to note: SDK docs (S720/S728) state `ctx.elicit()` fails on 2026-07-28 connections, while Claude Code (S740) connects stdio servers on the earlier protocol by default: behaviour depends on the client's negotiation setting (`MCP_PROTOCOL_NEGOTIATION`), not on the SDK alone. (topic: claude/elicitation)
  - Reviewed 2026-09-28, not a source disagreement: a negotiation-dependent behaviour, not two sources disagreeing.
- Claude Code changelog 2.1.76 (S746) says elicitation was added for "form fields or browser URL"; 2.1.281 (S746) says URL-mode elicitation was "Added ... on 2026-07-28 protocol connections" — URL mode existed on legacy connections before, and was only added for the new protocol later. (topic: claude/elicitation)
  - Reviewed 2026-09-28, not a source disagreement: two changelog entries for two protocol versions; closed.
- MCP extensions overview (S714) links `/specification/draft/...` for `_meta` rules and `server/discover`, while the spec pages are versioned 2026-07-28 (link target mismatch, no normative conflict found). (topic: mcp/tasks-extension)
  - Reviewed 2026-09-28, not a source disagreement: a link-target mismatch with no normative conflict.

## mecm1

- Client log level values: registry doc says LogLevel 0 Verbose / 1 Default / 2 Warnings and errors / 3 Errors only (S214 about-log-files.md); SDK SetGlobalLoggingConfiguration says 0 Verbose / 1 Normal / 2 No logging (S225). (topic: mecm/log-files)
  - Re-read 2026-09-27, still open: about-log-files (updated_at 2026-08-31) still lists 0 Verbose among four levels, and the SetGlobalLoggingConfiguration page still lists Verbose, Normal and No logging. (topic: mecm/log-files)
  - Still open 2026-10-21: re-read both pages. S214 still lists the registry value LogLevel (`HKLM\SOFTWARE\Microsoft\CCM\Logging\@Global`) as 0 Verbose, 1 Default, 2 Warnings and errors, 3 Errors only; S225 still lists the method argument as 0 Verbose, 1 Normal, 2 No logging (default 1) and says the method writes the keys under `HKLM/Software/Microsoft/CCM/logging/@GLOBAL`. No page maps the method's values to the registry's. Calling SetGlobalLoggingConfiguration with LogLevel 2 on a lab client and reading the registry value and the log output would settle it.
- Collect client logs permission holders: current doc names Full Administrator and Infrastructure Administrator (S221); 1912 preview note names Full Administrator and Operations Administrator (S-pzvndq5z). (topic: mecm/collect-client-logs)
  - Re-read 2026-09-27, still open: the live client-notification page's Client diagnostics prerequisites still name Full Administrator and Infrastructure Administrator, while its Client notification section names Full Administrator and Operations Administrator. (topic: mecm/collect-client-logs)
  - Narrowed 2026-10-21: the technical preview 1912 note (S-pzvndq5z) is a preview page; the current Client notification page (S221), re-read, still names Full Administrator and Infrastructure Administrator in its Client diagnostics prerequisites, while the same page's Client notification section names Full Administrator and Operations Administrator for Notify Resource, so the live disagreement is inside the current page (see the Notify Resource entry below). The role overview page describes the built-in roles in prose, not per permission. Reading the Notify Resource permission of each built-in role in the console's Security Roles node would settle it.
- Collected file versions: Delete Aged Collected Files / software inventory doc keep "five most-recent copies" in sinv.box\FileCol (S223, S204); client diagnostics section says "no defined limit to the number of versions" for collected client logs (S221). (topic: mecm/collect-client-logs)
  - Re-read 2026-09-27, still open: the live client-notification page still says there's no defined limit to the number of versions of collected diagnostics. (topic: mecm/collect-client-logs)
  - Narrowed 2026-10-21: re-read. S223 and S204 still say the five most-recent copies of collected files are kept in `Inboxes\sinv.box\FileCol`; the client diagnostics section (S221) still says collected client logs are stored there per the software inventory file collection settings with "no defined limit to the number of versions". The five is stated for software inventory collected files and the maintenance task, the no-limit sentence for client log bundles; no page says whether log bundles are also kept to five. Collecting client logs from one lab client more than five times and counting the `Support_<guid>.zip` versions in FileCol would settle it.
- Enforcement grace period range: client settings says 0-120 hours (S204); deploy applications says 1-120 hours (S229). (topic: mecm/client-settings)
  - Re-read 2026-09-27, still open: both live pages (updated_at 2026-08-31) keep 0 to 120 hours (about-client-settings) and 1 to 120 hours (deploy-applications). (topic: mecm/client-settings)
  - Still open 2026-10-21: re-read. S204 still says "Set a grace period of 0 to 120 hours"; S229 still says "Specify a value between 1 and 120 hours". Entering 0 in the Computer Agent client setting Grace period for enforcement after deployment deadline (hours) in a lab console would show which range holds.
- SMS_DCMDeploymentCompliantDetailsPerAsset (a "compliant details" class) describes DiscoveredValue/InstanceData as reported "when the rule is non-compliant" (S209); internal inconsistency within one page. (topic: mecm/sql-views-compliance)
  - Re-read 2026-09-27, still open: the live class page (updated_at 2026-08-28) still describes DiscoveredValue and InstanceData in non-compliant terms. (topic: mecm/sql-views-compliance)
  - Still open 2026-10-21: re-read S209: the class summary still says it represents the compliant asset details, while DiscoveredValue is still described as reported "when the rule is non-compliant" and InstanceData as the path referenced "by the non-compliant rule". Querying the class on a lab site with a compliant baseline rule and reading DiscoveredValue would settle it.
- Version-support pages: updates.md front matter ms.date 2024-12-04 yet it lists 2603 (May 2026) (S217); content newer than its date stamp. Not a factual disagreement, noted for freshness checks. (topic: mecm/versions-lifecycle)
  - Not a factual disagreement; left as a freshness note. (topic: mecm/versions-lifecycle)
  - Reviewed 2026-09-28, not a source disagreement: a stale date stamp; closed.

## mecm2

- Built-in roles with Notify Resource: client-notification.md "Client notification" section (S326) says Full Administrator + Operations Administrator. The same page's "Client diagnostics" section (S326) and whats-new 1810 (S340) say Full Administrator + Infrastructure Administrator. (topic: mecm/client-notification)
  - Re-read 2026-09-27, still open: the live page (updated_at 2026-08-31) still names Full Administrator + Operations Administrator under Client notification and Full Administrator + Infrastructure Administrator under Client diagnostics. (topic: mecm/client-notification)
  - Still open 2026-10-21: re-read the Client notification page (S326, S221) and whats-new 1810 (S340). The Client notification section still names Full Administrator and Operations Administrator for Notify Resource; the Client diagnostics section and whats-new 1810 ("Client notification actions now require the Notify Resource permission on the SMS_Collection class") still name Full Administrator and Infrastructure Administrator. The role overview page lists no per-permission defaults. Reading Notify Resource on the Collection object in the Operations Administrator and Infrastructure Administrator roles in a lab console would settle it.
- AdminService class-name case: overview.md (S300) says class names are case-sensitive. release-notes.md (S306) says the wmi route is case-insensitive from 2006. (topic: mecm/adminservice)
  - Re-read 2026-09-27, still open: the live overview still says class names are case-sensitive and the release notes still say the wmi route is case-insensitive from 2006. (topic: mecm/adminservice)
  - Still open 2026-10-21: re-read. S300 still says "The administration service class names are case-sensitive" for the `<ClassName>` of the wmi route; S306 still says that from version 2006 "the WMI route is now case-insensitive" (`AdminService/wmi/sms_site` works besides `SMS_Site`). S306 is the dated, version-specific statement and S300 the undated one, and neither page narrows its claim to another route. Requesting `AdminService/wmi/sms_site` on a lab site of version 2006 or later would settle it.
- SMS_ClientOperation.Priority is "1 Highest, 50 Lowest" (S328), but SMS_ClientOperationStatus.Priority is "1 highest, 10 lowest" (S330). (topic: mecm/client-notification)
  - Re-read 2026-09-27, still open: both live class pages (updated_at 2026-08-28) keep 1-50 and 1-10. (topic: mecm/client-notification)
  - Still open 2026-10-21: re-read. S328 still says "1 Highest, 50 Lowest" for SMS_ClientOperation.Priority; S330 still says "1 highest, 10 lowest" for SMS_ClientOperationStatus.Priority. They are two classes (operation and operation status) and no page explains a different range. Reading both Priority values of one client operation from a lab SMS Provider would settle it.
- Value 8 RequestPolicyNow is listed under PrimaryActionType in SMS_ClientOperation (S328) but under PrimaryActionTargetObjectType in SMS_ClientOperationStatus (S330). (topic: mecm/client-notification)
  - Re-read 2026-09-27, still open: SMS_ClientOperationStatus still lists 8 RequestPolicyNow under PrimaryActionTargetObjectType. (topic: mecm/client-notification)
  - Narrowed 2026-10-21: re-read. S328 lists 8 RequestPolicyNow in its PrimaryActionType table after actions 1 to 7 (Full Scan to Restore Quarantine Items); S330 lists 8 RequestPolicyNow in its PrimaryActionTargetObjectType table, after 1 Threat, and its PrimaryActionType table ends at 7. The target object type table of S328 holds only Threat, so S330's row looks misplaced, but no page says so. Querying SMS_ClientOperationStatus for a Request Policy Now operation and reading which property holds 8 would settle it.
- Invoke-CMScript (S335): -ScheduleTime is shown as Mandatory:True for all parameter sets, yet it is absent from both syntax blocks and the examples omit it. (topic: mecm/run-scripts)
  - Re-read 2026-09-27, still open: the live page (updated_at 2023-09-20) still marks -ScheduleTime Mandatory: True for (All) parameter sets while neither syntax block lists it. (topic: mecm/run-scripts)
  - Still open 2026-10-21: re-read S335: -ScheduleTime is still listed Mandatory: True for the (All) parameter sets, described as a UTC DateTime to schedule the script's execution for a later time, and is still absent from the By Input Object and By Guid syntax blocks and from the three examples. Running `Invoke-CMScript -ScriptGuid <id> -CollectionId <id>` without it on a lab site, or `Get-Help Invoke-CMScript -Parameter ScheduleTime`, would settle it.
- Tenant-attach troubleshooting pages say "IIS must be installed on provider machine" (e.g. troubleshoot-cmpivot.md), but set-up.md (S301) says IIS is not required from 2010. (topic: mecm/adminservice)
  - Re-read 2026-09-27, still open: tenant-attach/troubleshoot-cmpivot (updated_at 2026-08-31) still says IIS must be installed; set-up (updated_at 2026-08-28) still says IIS is not needed from 2010. Follow set-up.md for 2010 and later. (topic: mecm/adminservice)
  - Still open 2026-10-21: re-read. S301 still says that starting in version 2010 IIS is no longer needed on the SMS Provider for the administration service and that the SMS Provider role doesn't require IIS; the live tenant-attach pages troubleshoot-cmpivot and troubleshoot-resource-explorer (not kb sources) still say "IIS must be installed on provider machine", with no version qualifier. Running CMPivot from the admin center against a version 2010 or later lab site whose SMS Provider has no IIS would settle it.
- CMPivot permission for a failed AdminService path: cmpivot.md (S315) names HTTP 503 fallback to the SMS Provider (needs SMS Scripts Read). The 2603 KB (S312) also describes a fallback on HTTP 400 parse errors, fixed in 2603. (topic: mecm/cmpivot)
  - Re-read 2026-09-27, still open: the live cmpivot page (updated_at 2026-08-31) still names only the 503 fallback; the 2603 KB (S312) adds the 400 parse-error fallback. Both paths need SMS Scripts Read on the SMS Provider when the fallback happens. (topic: mecm/cmpivot)
  - Reviewed 2026-10-21, not a source disagreement: the 2603 summary of changes (S312) says CMPivot queries through the AdminService no longer fail with a 400 Bad Request error from a query parsing issue and that CMPivot "would fall back to the SMS Provider path requiring additional Script Read permissions" before; cmpivot.md (S315) says the SMS Provider still needs Read on SMS Scripts when the AdminService falls back because of a 503 (Service Unavailable) error. There are two fallback triggers; the 400 one is fixed from 2603 and the 503 one is still described.

## ops

- **Remediations schedule.** deploy-remediations.md offers Once, Hourly and Daily schedules, but the same page says custom script packages "are rerun every 24 hours" (S609). https://raw.githubusercontent.com/MicrosoftDocs/memdocs/4b5429df8b47046c6b251e572ee61199fb5d4a5d/intune/device-management/tools/deploy-remediations.md (topic: intune/remediations)
  - Re-read 2026-09-27, still open: the live page still offers Once, Hourly (less than 24 hours) and Daily and still says custom script packages are rerun every 24 hours. (topic: intune/remediations)
  - Narrowed 2026-10-21: re-read S609. The schedule options are still Once, Hourly (less than 24 hours) and Daily, and the page still recommends less frequent schedules such as every 7 days for heavy scripts, while the custom script packages paragraph still says "The scripts are rerun every 24 hours". The 24-hour sentence reads as the default of the Daily schedule, but no page says so. A lab remediation set to a 7-day schedule, with its runs read from the device's Intune management extension logs, would settle it.
- **Collect diagnostics and Graph.** collect-diagnostics.md says diagnostics "can't be collected or downloaded by calling Microsoft Graph directly". Its reference links still list the Graph actions createDeviceLogCollectionRequest and createDownloadUrl (S616). (topic: intune/collect-diagnostics)
  - Re-read 2026-09-27, still open: the live page (updated_at 2026-08-05) still says diagnostics can't be collected or downloaded through Graph directly and still lists createDeviceLogCollectionRequest, createDownloadUrl, downloadAppDiagnostics and appDiagnostics under Reference links. (topic: intune/collect-diagnostics)
  - Still open 2026-10-21: re-read S616: it still says diagnostics "can't be collected or downloaded by calling Microsoft Graph directly" and its reference list still names the Graph actions createDeviceLogCollectionRequest and createDownloadUrl. Calling createDeviceLogCollectionRequest against a lab tenant's managed device would settle it.
- **MDE machine $filter.** get-machines (S621) lists 14 filterable properties, including aadDeviceId, id, version, deviceValue, machineTags and lastIpAddress. exposed-apis-odata-samples (S628) lists only 8 for Machine and leaves out aadDeviceId. https://learn.microsoft.com/defender-endpoint/api/get-machines vs https://learn.microsoft.com/defender-endpoint/api/exposed-apis-odata-samples (topic: defender/machine-resource)
  - Reviewed 2026-09-28, still open: not re-read; Defender pages stay `quote`.
  - Still open 2026-10-21: re-read both pages: get-machines (S621, last updated 2026-06-28) still lists 14 `$filter` properties including `aadDeviceId`, `id`, `version`, `deviceValue`, `machineTags` and `lastIpAddress`, and the OData page (S628, last updated 2026-01-08) still lists 8 for Machine (ComputerDnsName, LastSeen, exposureLevel, HealthStatus, OsPlatform, onboardingStatus, RiskScore, RbacGroupId). A `$filter=aadDeviceId eq '<id>'` call in a lab tenant would settle it; the pages stay `quote`.
- **MDE permissions.** get-machines (S621) accepts Machine.Read.All and Machine.Read. get-machine-by-id (S622) lists only Machine.ReadWrite.All and Machine.ReadWrite. (topic: defender/machine-resource)
  - Re-read 2026-09-27, still open: get-machine-by-id still lists only the ReadWrite permissions. (topic: defender/machine-resource)
  - Still open 2026-10-21: re-read get-machine-by-id (S622): its permissions table still lists only Machine.ReadWrite.All (application) and Machine.ReadWrite (delegated). get-machines (S621) was not re-read in this pass. Calling GET /api/machines/{id} in a lab tenant with a token that holds only Machine.Read.All would show which permission the call accepts.
- **MDE property table vs examples.** rbacGroupId is typed String (S620), but the examples show the number 140 (S621, S622). isAadJoined appears in the examples but not in the property table. (topic: defender/machine-resource)
  - Re-read 2026-09-27, still open: the get-machine-by-id example still shows `"rbacGroupId": 140` and `isAadJoined`. (topic: defender/machine-resource)
  - Still open 2026-10-21: re-read the machine resource page (S620) and the get-machine-by-id example (S622). rbacGroupId is still typed String and the example still shows the number 140; isAadJoined is still in the example and still absent from the property table, which lists aadDeviceId. Calling GET /api/machines/{id} in a lab tenant and reading the JSON type of rbacGroupId and whether isAadJoined is returned would settle it.
- **Device query operators.** The single-device table operators (S612) do not include `summarize`, yet the same page says its aggregation functions work with it. The multi-device page (S613) does list `summarize`. (topic: intune/device-query)
  - Re-read the multi-device side only, 2026-09-27: it still uses summarize in its examples and Known limitations; the single-device page was not re-read. (topic: intune/device-query)
  - Narrowed 2026-10-21: re-read S612: its table operators list (count, distinct, join, order by, project, take, top, where) still has no summarize, while the page still says table operators summarize data, that aggregation functions work with the summarize table operator, and that maxif and minif work with summarize from 2107; S613 lists summarize and uses it in its examples. The omission reads as a missing table row. Running a `summarize` query against a single device in the admin center would settle it.
- **Co-management query.** how-to-monitor (S603) lists four SMS_Client_ComanagementState fields: MachineId, MDMEnrolled, Authority and ComgmtPolicyPresent. The WQL in create-queries (S647) also filters on MDMProvisioned, which is not in that list. (topic: intune/co-management)
  - Re-read the how-to-monitor side 2026-09-27 (Learn search): it still lists MachineId, MDMEnrolled, Authority and ComgmtPolicyPresent only. (topic: intune/co-management)
  - Narrowed 2026-10-21: re-read S603 (four fields) and S647 (the co-managed WQL still filters `MDMProvisioned = 1`, unqualified). The SMS_R_System class page, read 2026-10-21, defines no MDMProvisioned property (it lists MDMDeviceCategory). The class reference of SMS_Client_ComanagementState, which is not a kb source, or a WMI dump of that class on a lab site would show whether MDMProvisioned is a fifth field.

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
  - Still open 2026-10-21: re-read the sources: the CHANGELOG on main (S800) still goes from `[unreleased]` to `[2.2.363] - 2026-06-28` with no `[2.2.364]` section, the GitHub releases (S801) list 2.2.364 published 2026-07-22 as the newest, and PyPI's newest presidio-analyzer is still 2.2.364. A CHANGELOG section for 2.2.364 or a later release with its own section would settle it.
- EDPB Guidelines 01/2025 consultation end: the news item (S873) says "until 28 February 2025". The consultation page (S872) shows the feedback period "17 January - 14 March 2025". (topic: privacy/gdpr-pseudonymisation)
  - Re-read 2026-09-27, still open: the consultation page and the EDPB consultations list both show 17 January - 14 March 2025 (23:59 CET); the news item keeps 28 February 2025. The consultation page is the operative record. (topic: privacy/gdpr-pseudonymisation)
  - Resolved 2026-10-21: the EDPB consultation page (S872) is the EDPB's record of the feedback period itself; read again in the census of 2026-10-21 it still shows 17 January - 14 March 2025 and marks it closed, while the news item (S873) is the older statement of 2025-01-17 ("until 28 February 2025"). `privacy/gdpr-pseudonymisation` states the consultation page's period. [DOC S872, S873]
- spaCy en_core_web_lg versions: GitHub releases have 3.8.0 (2024-09-30, S850). The Hugging Face repo was last modified 2023-11-21 with 3.7.1 (S851). Both say MIT. (topic: privacy/spacy-model-licence)
  - Reviewed 2026-09-28, still open: two distribution channels at different versions; the kb follows GitHub releases.
  - Still open 2026-10-21: re-read the sources: the GitHub release `en_core_web_lg-3.8.0` (S850) is still dated 2024-09-30 and no newer en_core_web_lg release is among the five newest spacy-models releases, and the Hugging Face API for `spacy/en_core_web_lg` (S851) still shows last modified 2023-11-21, license `mit`. An update of the Hugging Face repository or a statement from the publisher would settle it; the kb follows GitHub releases.
- Nemotron-PII size: the dataset card (S-dcu4qhyp) says 100,000 records, 50k train and 50k test; the Hugging Face datasets-server `size` endpoint (read 2026-09-27) reports 100,000 rows in each of the train and test splits (200,000 in all). The kb states the card's figure. (topic: privacy/gliner-models)
  - Still open 2026-10-21: re-read the live datasets-server `size` endpoint (not partial: 100,000 rows in `train` and 100,000 in `test`) against the dataset card (S-dcu4qhyp, last modified 2025-12-17), which still says 100,000 records, 50k train and 50k test; the kb states the card's figure and says so. Counting the rows of the train and test Parquet files in the dataset repository, or a corrected card, would settle which count the files hold.
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
  - Closed 2026-10-21: a record that no other disagreement was found for that session, with no claim to settle.

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
  - Still open 2026-10-21: both values are pinned publications (the Windows 11 24H2 baseline S1472 and STIG V2R9 S1470); this pass downloaded no newer release of either. The baseline's `LockoutBadCount=10` and `LockoutDuration=10` and the STIG's 3 or less and 15 minutes or more are requirements of two publishers, not an error of one. A new STIG release or baseline that aligns them would settle it.

### A: device settings catalog

- **CIS Windows 11 Enterprise Benchmark version vs. tested OS release.** Public digests describe
  v5.0.0/v5.0.1 as tested against Windows 11 release 23H2, which matters for any estate targeting
  24H2/25H2. Whether v5.1.0's front matter updates the tested release was not confirmed this pass
  (the CIS PDF itself is behind registration). Flag before citing CIS L1 items as validated for
  24H2/25H2 without checking v5.1.0's own applicability statement. (topic: security/baselines-catalog)
  - Re-read 2026-09-27, still open: CIS's September 2026 update (S-m3qbkeev) lists v5.1.0's changes (Defender AV recommendations moved to their own benchmark, 3 updated, 1 removed) but no tested release; the PDF is behind registration. (topic: security/baselines-catalog)
  - Still open 2026-10-21: the CIS September 2026 update (S-m3qbkeev, confirmed in the census of 2026-10-21) still lists v5.1.0's changes without a tested Windows 11 release, and the Benchmark PDF is behind CIS registration. Reading the applicability statement in the v5.1.0 PDF after a free CIS login would settle it.
- No other cross-source disagreement was established this pass (most rows are UNK rather than
  conflicting DOC facts, since the machine-readable sources needed for a real crosswalk were not
  downloaded — see `gaps.A.md`).
  - Closed 2026-10-21: a record that no other cross-source disagreement was established, with no claim to settle.

### B: management plane

- **Device-log retention below CIS minimum, audit retention above it.** A design that keeps a 400-day audit table comfortably clears CIS Controls v8.1 Safeguard 8.10 (90-day minimum retention for audit logs), but normalized device logs kept only 30 days (diagnostic rather than security logs) sit below that minimum. See `security/logging-monitoring.md` § Conflicts. [DER S1492]
  - Reviewed 2026-09-28, not a source disagreement: a design check, not a source conflict.
- **PyPI Trusted Publishing and self-managed GitLab.** A third-party blog (S1510, COMMUNITY) claims PyPI supports self-managed GitLab. The official *Adding a Trusted Publisher* page (S1597, retrieved 2026-09-24) says only gitlab.com projects are supported, and the official page wins. (topic: security/supply-chain)
  - Re-read 2026-09-27, now a PyPI-internal disagreement: PyPI's own blog (S-5ry5zerr, 2025-11-10) and 2025 review (S-cos7wdpw) confirm the GitLab Self-Managed beta, and Warehouse supports custom GitLab issuers (CODE S-5t26tmbz); the user docs (S1597) and troubleshooting page still say gitlab.com only. The article states both; the blog is the newer statement. (topic: security/supply-chain)
  - Narrowed 2026-10-21: re-read the PyPI user docs (S1597), which still say "Currently, only projects hosted on https://gitlab.com are supported. Self-managed instances are not supported."; the PyPI blog (S-5ry5zerr, 2025-11-10) and 2025 review (S-cos7wdpw) report the GitLab Self-Managed beta and the Warehouse code (CODE S-5t26tmbz, main HEAD 02dae5a1510b) accepts custom GitLab issuers, so the disagreement is inside PyPI's own pages and the docs page is the older statement. A PyPI docs update, or registering a publisher from a self-managed instance during the beta, would settle whether the page is stale. [DOC S1597, S-5ry5zerr, S-cos7wdpw; COMMUNITY S1510]

### C: frameworks, regulation, AI

- (Resolved 2026-09-24) CIS Controls v8.1 licence (CC BY-NC-ND 4.0, no derivatives) [DOC S1563]: the
  `framework-control-map.csv` rows now use safeguard IDs plus a short own-words paraphrase instead of the
  official safeguard titles, matching the treatment of CIS Benchmark recommendation IDs elsewhere in the kb
  (part A). (topic: security/framework-control-map)
  - Resolved 2026-10-21: the CIS Controls v8.1 licence (S1563) is unchanged and the `framework-control-map.csv` rows already carry safeguard IDs and an own-words paraphrase, not the official titles; no source disagrees. [DOC S1563]
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
  - Narrowed 2026-10-21: re-read both pages. `add-win32` (S-wc6e3fba) says "a maximum of 10 updated or replaced apps" and "a maximum of 10 nodes in a supersedence relationship"; `configure-win32-supersedence` (S-vywsads7) says "a maximum of 10 nodes in a supersedence relationship" near its top and later "a maximum of 11 nodes in a single supersedence graph. The nodes include the superseding app, the superseded apps, and all subsequent related apps". Counting the superseding app, ten superseded apps make eleven graph nodes, so the 10 (apps updated or replaced) and the 11 (graph nodes) can both hold; only the "10 nodes in a supersedence relationship" sentence stays unreconciled. The dependency limit is unchanged (100, graph size 101). The kb keeps 10 as the safe limit; a lab app superseding 11 apps would settle it.

## intune/compliance-policies

- `windows10CompliancePolicy` Graph resource shape: the v1.0 resource page (rechecked 2026-09-26) lists exactly 19 settable properties (password rules, `bitLockerEnabled`, `secureBootEnabled`, `codeIntegrityEnabled`, `earlyLaunchAntiMalwareDriverEnabled`, OS version bounds, `storageRequireEncryption`) [DOC S-taatt73w], while the beta resource page for the same type name (rechecked 2026-09-26) still adds `tpmRequired`, `activeFirewallRequired`, `defenderEnabled`, `defenderVersion`, `signatureOutOfDate`, `rtpEnabled`, `antivirusRequired`, `antiSpywareRequired`, `deviceThreatProtectionEnabled`, `deviceThreatProtectionRequiredSecurityLevel`, `configurationManagerComplianceRequired`, `validOperatingSystemBuildRanges`, `memoryIntegrityEnabled`, `kernelDmaProtectionEnabled`, `virtualizationBasedSecurityEnabled`, `firmwareProtectionEnabled`, `deviceCompliancePolicyScript`, `wslDistributions` and `roleScopeTagIds` [DOC S-2hhj3k5f]. Every one of these beta-only properties corresponds to a setting the admin center UI exposes today (`compliance-policy-create-windows`, S-qjd54t3z), so v1.0 cannot express most Windows System Security / Defender / Configuration Manager compliance settings via Graph; automation needs the beta endpoint (or the UI) for those settings until Microsoft ships them to v1.0. Still a live gap on recheck — no v1.0 update found. (rechecked 2026-09-26, kept) (topic: intune/compliance-policies)
  - Reviewed 2026-10-21, not a source disagreement: the v1.0 page (S-taatt73w) still lacks every beta-only property named here (tpmRequired, defenderEnabled, memoryIntegrityEnabled, wslDistributions, roleScopeTagIds and the rest) and the beta page (S-2hhj3k5f) still lists them. Graph stages properties in beta before v1.0, each page is right for its version, and the article already tells automation to use the beta endpoint for those settings. The difference ends when the v1.0 page gains the properties.

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
  - Narrowed 2026-10-21: re-read the live pages. The recreate page (migrate-copilot-studio-agents-to-agent-id) says Copilot Studio began automatically creating agent identities for all new agents on March 18, 2026, and that older agents may also come from an organization that opted out. admin-use-entra-agent-identities says "Starting May 2026, all new agents have Microsoft Entra Agent IDs, and you can no longer opt out", and govern-agents-identities-overview says Entra Agent ID "was available in May 2026". What's new in Copilot Studio lists "(Preview) Automatically create Microsoft Entra Agent IDs" under May 2026 and "Starting in July 2026 ... you can no longer opt out at the environment level" under July 2026. March 18 reads as the start of automatic creation with an opt-out, but the admin page's May 2026 and What's new's July 2026 still date the end of the opt-out differently. The Copilot Studio release notes naming the build that removed the environment-level opt-out, or creating an agent in a tenant that had opted out, would settle it.
- Microsoft Learn search index (2026-09-27) still returns the overview page with the PREVIEW banner, while the live page and What's new (S-ifhonpv7) say Entra Agent ID is generally available; the Entra what's-new lists 'General Availability - Microsoft Entra Agent ID platform' in April 2026. (topic: entra/agent-id)
  - Resolved 2026-10-21: the live page (S-fdnhk2tn, fetched 2026-10-21) opens without the PREVIEW banner, so the banner came from a stale search-index copy. What's new in Microsoft Entra Agent ID (S-ifhonpv7) says Entra Agent ID "is now generally available", and the Entra what's-new (fundamentals/whats-new, April 2026) lists "General Availability - Microsoft Entra Agent ID platform".

## agents/agent-rbac
- Which Microsoft Entra directory roles an agent identity can hold: "Agent identities, service principals, and applications" (S-2iq53pkf, read 2026-10-15) says agent identities can be assigned Azure RBAC roles and Microsoft Entra built-in roles "the same as standard service principals", while the authorization page and FAQ (S-fwzaxe7i, S-pmj4jc4f) say they can't hold highly privileged directory roles or custom roles and only lower-privileged roles such as readers. The kb states both; the narrower pages are the specific statement, so plan on the restriction. [DOC S-2iq53pkf vs DOC S-fwzaxe7i, S-pmj4jc4f, unresolved] (topic: agents/agent-rbac)
  - Narrowed 2026-10-21: the authorization page (S-fwzaxe7i) and the FAQ (S-pmj4jc4f), read 2026-10-21, both still say Global Administrator, Privileged Role Administrator and User Administrator are blocked and only lower-privileged roles can be assigned, and the authorization page lists the allowed built-in roles; S-2iq53pkf still says "the same as standard service principals" in general terms. No Microsoft page reconciles the wording; the kb plans on the restriction, which the two specific pages state. Settles when Microsoft aligns the service principals page. [DOC S-2iq53pkf, S-fwzaxe7i, S-pmj4jc4f]
- The Entra Agent ID authorization page (S-fwzaxe7i) now says custom roles can be assigned to agent identities; kb line 89 also cites S-pmj4jc4f for the older claim that they cannot. Check whether S-pmj4jc4f still says so (topic: agents/agent-rbac)
  - Resolved 2026-10-21: the FAQ (S-pmj4jc4f, read 2026-10-21) names only the blocked highly privileged roles and says only lower-privileged roles can be assigned, with no statement on custom roles, and the authorization page (S-fwzaxe7i) says "Custom roles can be assigned to agents"; `agents/agent-rbac` states the custom-role change from the authorization page. [DOC S-fwzaxe7i, S-pmj4jc4f]

## agents/windows-agentic-platform

- Recall availability default: Policy CSP `WindowsAI\AllowRecallEnablement` (rechecked 2026-09-26) still
  documents, in its own descriptive text, "By default, Recall is disabled for managed commercial devices.
  Recall isn't available on managed devices by default, and individual users can't enable Recall on their
  own," while the same page's **Description framework properties** table still states "Default Value: 1"
  and "1 (Default) | Recall is available." — the CSP page now contradicts itself directly (not just against
  the separate "Manage Recall" guide, which repeats the same "disabled by default" wording). Still a live
  disagreement; treat Recall as off-by-default on any Intune/GPO-managed device regardless of the table's
  stated default value. (rechecked 2026-09-26, kept) (topic: agents/windows-agentic-platform)
  - Still open 2026-10-21: re-read the Policy CSP page (S-2ypn2ron): its text still says "By default, Recall is disabled for managed commercial devices" while the properties table still says Default Value 1 and "1 (Default) Recall is available". No source reconciles them; a managed Windows 11 24H2 device with the policy unset (state of the Recall optional component) or a change of the page would settle it.
- `DisableClickToDo` applicability: rechecked 2026-09-26 — the Policy CSP page still lists this policy's
  **Applicable OS** as "Windows Insider Preview" only (no stable OS/KB build given), while the companion
  "Manage Click to Do" admin article (rechecked 2026-09-26) still documents it and its Settings UI toggle
  ("By default, Click to Do is enabled for users") without a preview caveat, alongside Copilot+ PC hardware
  requirements that are themselves GA. Until the CSP page adds a stable-build requirement, treat
  `DisableClickToDo` itself as preview even though Click to Do the feature is GA on Copilot+ PCs. (rechecked
  2026-09-26, kept) (topic: agents/windows-agentic-platform)
  - Still open 2026-10-21: re-read the Policy CSP page (S-2ypn2ron): `DisableClickToDo` still lists "Windows Insider Preview" as its applicable OS. It settles when Microsoft adds a stable build to the page, or by a test of the policy on a stable Copilot+ PC build.

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
  - Narrowed 2026-10-21: re-read. The custom Bash script article (S-vbmaayv5) still lists "Linux Ubuntu Desktop, RedHat Enterprise Linux 8, or RedHat Enterprise Linux 9" and sends the reader to the supported operating systems page for the versions; the compliance reference (S-dvnl6gdu) and the platform guide (S-nvad3j6y) still agree on Ubuntu 24.04 LTS and 26.04 LTS with RHEL 9 and 10. The Bash script article is the one outlier and settles when Microsoft updates it.

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
  - Reviewed 2026-10-21: not a source disagreement. The Lifecycle Products page (S-7rfzq5p7, fetched) states "Support dates are shown in the Pacific Time Zone (PT)" and lists 7.4 and 7.5 as "11/11/2026 6:59:59 AM" and 7.6 as "11/15/2028 6:59:59 AM"; the PowerShell Support Lifecycle page still lists 10-Nov-2026 and 14-Nov-2028; the Learn "Ending Support in 2026" page lists PowerShell 7.4 (LTS) with end of servicing November 10, 2026. The Products page timestamps sit one calendar day after the plain dates because that page states Pacific Time and the other two give plain dates; no page gives a different support window, and the Support Lifecycle page's plain dates are the ones the article quotes.
- Telemetry opt-out: the Differences page (S-awsrthdz) says telemetry can only be disabled with POWERSHELL_TELEMETRY_OPTOUT, while about_Telemetry (S-62djuv2f) adds the Windows "Send optional diagnostic data" setting from PowerShell 7.6.2. The kb now states both, each with its own source. (topic: windows/powershell-7)
  - Reviewed 2026-09-28, still open: not re-read; the kb states both with their sources.
  - Still open 2026-10-21: re-read both pages: the Differences page (S-awsrthdz) still headlines "Telemetry can only be disabled with an environment variable", and about_Telemetry (S-62djuv2f) still lists two ways to disable it, the `POWERSHELL_TELEMETRY_OPTOUT` variable and, beginning with PowerShell 7.6.2 on Windows, the Diagnostics & feedback setting "Send optional diagnostic data". An edit of the Differences page would settle it; the kb states both with their sources.

## auth/ntlm-deprecation

- S1200's _sources.csv row says 'published 2025-09-24'; the fetched page's postTime is 2026-01-29 (read 2026-09-27). Row date should be corrected by the census owner. (topic: auth/ntlm-deprecation)
  - Reviewed 2026-10-21, not a source disagreement: the entry records a metadata date in S1200's `_sources.csv` row against the page's own post time (2026-01-29, read in the census); the row now carries both and no fact in `auth/ntlm-deprecation` states the post date. [DOC S1200]

## agents/agent-overuse-patterns

- S2174 (dev.to decision matrix) disagrees with itself: it puts the pipeline at 50,000 runs/day at ~$1.50/day for 3,000 tokens/run and ~$15/day for 30,000 tokens/run (10x), but later calls the 30,000-token case 'roughly 15x more'. Re-read 2026-09-27. (topic: agents/agent-overuse-patterns)
  - Reviewed 2026-10-21, not a disagreement between sources: one community post's own wording; its table gives 3,000 to 30,000 tokens per run as $1.50 to $15 a day, which is 10x, and the article states the 10x figures with the post's "15x" passage as the post's own. [COMMUNITY S2174]

## agents/azure-openai-deployments

- S-pntdruql (azure/ai-foundry/openai/concepts/provisioned-throughput, fetched 2026-09-27) no longer contains the utilization / leaky-bucket section that Learn search still indexes under azure/foundry/.../provisioned-throughput#monitor-utilization-and-performance; the same content is now on how-to/provisioned-get-started (S-gueirwxw). Facts re-cited there. (topic: agents/azure-openai-deployments)
  - Resolved 2026-10-21: the utilization and leaky-bucket section now stands on the provisioned-get-started page (S-gueirwxw, confirmed in the census of 2026-10-21), where `agents/azure-openai-deployments` cites it. [DOC S-gueirwxw]

## agents/content-safety-prompt-shields

- Blocklist matching: the kb said exact-match or regex; the custom-categories page (S-plv2ekwg) says blocklists allow only exact text matching and no image matching. Corrected to exact-match only. (topic: agents/content-safety-prompt-shields)
  - Resolved 2026-09-28: a kb correction already made; closed.

## agents/shared-ner-service

- Resolves the 'Azure Text PII character-limit figures' entry: S2093 (concepts/data-limits) re-read 2026-09-27 states no 50,000-character analyze-with-warning behaviour and no 10 MB document limit. It gives 5,120 characters per document for synchronous requests (over-length documents get an invalid-document error, others still processed), 5 PII documents and 1 MB per request, and 125,000 characters across up to 25 documents asynchronously (one over-length document fails the whole request with 400). The 50,000 figure is now an UNK line in the article. (topic: agents/shared-ner-service)
  - Resolved 2026-10-21: the data-limits page (S2093, confirmed in the census of 2026-10-21) is the source of the figures; the article states them and keeps the 50,000-character figure as UNK. [DOC S2093]

## auth/sql-authz

- auth/sql-authz.md:14 says on-prem SQL Server Entra authentication 'requires the instance to be Arc-enabled'; S1207 (Microsoft Entra authentication for SQL Server overview, re-read 2026-09-27) has a section 'Setting up Microsoft Entra authentication without Azure Arc' for SQL Server on Windows (manual certificates, registry, app registration). Arc remains required for SQL Server 2025's primary managed identity (S1206). arch/sql-auth-containers.md and arch/workload-identity-onprem-k8s.md were corrected; auth/sql-authz.md was outside this unit. (topic: auth/sql-authz)
  - Closed 2026-09-27: auth/sql-authz.md now says Arc is not required on Windows (manual setup exists) and is required for the SQL Server 2025 primary managed identity. (topic: auth/sql-authz)

## agents/instruction-and-context-limits

- Copilot Studio instructions limit: Microsoft documents 8,000 characters (S1960, S-jexpr3gv); a community article (S1843) says some configurations enforce 2,000 characters after deployment, citing a Microsoft Q&A thread. (topic: agents/instruction-and-context-limits)
  - Reviewed 2026-09-28, still open: official limit vs a community report; a deployed agent test would settle it.
  - Still open 2026-10-21: re-read the sources: the prompt modification page (S-jexpr3gv) and the quotas page (S1960) still state 8,000 characters, and the community article (S1843) still says 2,000 after deployment in some configurations. The Q&A thread it cites is dated 2024-06-19: a user reports the field limited to 2,000 characters after creation, and the one answer calls it "a bug" worth reporting, without a Microsoft statement of a limit. A test on a deployed agent in a current tenant would settle it.

## agents/a2a-protocol

- A2A Agent Card well-known path: the A2A spec (S2120) registers `/.well-known/agent-card.json`, while Microsoft Copilot Studio's A2A connector docs (S2126, re-read 2026-09-27) tell makers to find the card at the endpoint plus `/.well-known/agent.json`. (topic: agents/a2a-protocol)
  - Explained 2026-09-27, still open: the A2A v0.3.0 release notes (S-xasyjfgi, 2025-07-30) changed the well-known URI from `agent.json` to `agent-card.json`, so the Copilot Studio page gives the pre-v0.3.0 path; the Learn page, re-read 2026-09-27, still says `agent.json`. Kept until Microsoft updates it. (topic: agents/a2a-protocol)
  - Still open 2026-10-21: the Copilot Studio page (S2126) was fetched again on 2026-10-21 and still says the card is at the endpoint plus `/.well-known/agent.json`, while the A2A specification (S2120) registers `agent-card.json` and the v0.3.0 notes (S-xasyjfgi) record the rename. It settles when Microsoft updates the page; the kb states both.

## agents/docs-maintenance-agents

- S1808 (cognition.com/blog/deepwiki) now shows the date 05.05.25 and only a short launch note; the article's applies_to and the _sources.csv row say a 2025-04-25 launch post. The detailed claims once cited to it (LLM + code analysis, graph representation, PR/git history/team discussions, 'cycle of implementing code from documentation') are no longer on the page and are now UNK leads. (topic: agents/docs-maintenance-agents)
  - Closed 2026-09-27: the unsupported claims were removed from the article; the graph and scoring description now rests on a COMMUNITY summary of a Cognition talk (S-rqjvl632), and the PR/team-discussion and code-docs cycle claims were dropped (no first-party source; the Cognition blog renders no body without JavaScript). (topic: agents/docs-maintenance-agents)

## agents/foundry-agent-service

- The Foundry capability reference (S-eh6okx77) marks Browser automation, Computer use, Image generation, SharePoint and Fabric connectors, Fabric IQ and Work IQ as preview; the kb table had them as GA. The capability reference says preview status can vary by feature, region and API version, so per-tool pages remain the authority. (topic: agents/foundry-agent-service)
  - Reviewed 2026-09-28, still open: not re-read; per-tool pages remain the authority.
  - Still open 2026-10-21: re-read the capability reference (S-eh6okx77): Browser automation, Computer use, Image generation, SharePoint and Fabric connectors, Fabric IQ and Work IQ are still marked (preview), and the page still says preview status can vary by feature, region and API version and points to each linked article. The per-tool pages were not re-read in this pass; a tool page that states GA for one of these would settle that tool.

## auth/configmgr-rbac-auth

- The kb derived that Microsoft's enterprise access model treats ConfigMgr-like estate-wide device/config control as control-plane (Tier 0) equivalent; re-read 2026-09-27, S1210 defines the control plane as access control based on centralized enterprise identity systems and the management plane as enterprise-wide IT management functions, which on its wording places ConfigMgr in the management plane. The articles now call control-plane treatment a local judgement; _answers.md QA17 still carries the old derivation. (topic: auth/configmgr-rbac-auth)
  - Resolved 2026-09-27: the AD DS tier model (S-7nbamxyc) puts systems that patch or run agents on Tier 0 identity systems in Tier 0 and IT management of Tier 1 servers in Tier 1; the articles and QA17 now apply that test (DER). (topic: auth/configmgr-rbac-auth)

## auth/ldap-smb-signing

- SMB signing default on Windows Server 2025: S1202 (Control SMB signing behavior) says Windows Server 2025 requires outbound signing only; S1228 (SMB security hardening, HEAD 2026-09) says starting with Windows 11 24H2 and Windows Server 2025 all outbound and inbound SMB connections must be signed by default. Kb keeps S1202's outbound-only for Server 2025. (topic: auth/ldap-smb-signing)
  - Re-read 2026-09-27, still open: S1203 (Microsoft blog) and S-77zvblfr (SMB features, updated 2025-11-27) also say outbound only for Server 2025; S1228 alone says outbound and inbound. The kb keeps outbound-only. (topic: auth/ldap-smb-signing)
  - Resolved 2026-10-21: read raw at main, the signing page S1202 (ms.date 2025-08-13) says Windows 11 24H2 Enterprise, Pro and Education require outbound and inbound signing and Windows Server 2025 "requires outbound SMB signing only"; the hardening page S1228 (ms.date 2024-10-25) is the older page and itself points to S1202 for signing behaviour, and S1203 and S-77zvblfr agree with S1202. The kb keeps outbound-only for Server 2025. [DOC S1202, S1228, S1203, S-77zvblfr]
- SMB encryption default on Windows Server 2025 / Windows 11 24H2: the SMB features page (S-77zvblfr, updated 2025-11-27) has a table row saying encryption is required by default for all outbound client connections, while S1228 says encryption isn't mandatory by default and S1203 says it is not required by default. The kb keeps not-mandatory. Found 2026-09-27. (topic: auth/ldap-smb-signing)
  - Still open 2026-10-21: re-read the raw SMB features page (S-77zvblfr, ms.date 2025-11-27): its encryption table still says "Encryption required by default" for Windows Server 2025 / Windows 11 24H2 on outbound client connections, while the hardening page (S1228) only says the client "can now mandate encryption" and the blog (S1203) says it is not required by default. No page reconciles them. On a 24H2 lab client with default settings, `(Get-SmbClientConfiguration).RequireEncryption` and a connection to a share on a server without encryption would settle it.

## auth/propagation-latency

- Cloud Sync interval: the Cloud Sync FAQ (S1280) says user and group provisioning is scheduled approximately every 10 to 20 minutes, while What is Cloud Sync (S-2vza23mx) says the provisioning service synchronizes every two minutes. Both read 2026-09-27; the kb table states both. (topic: auth/propagation-latency)
  - Still open 2026-10-21: re-read both live pages: the FAQ (S1280, updated 2026-06-15) still says user and group provisioning is scheduled "approximately every 10 to 20 minutes" and the overview (S-2vza23mx, ms.date 2026-10-06) still says the provisioning service synchronizes "every two minutes" as its scheduler model; they may describe the scheduler tick and the end-to-end latency, but neither page says so. Timing a user change from AD to Entra ID with the provisioning logs of a lab Cloud Sync agent would settle it.
- TGT renewal window: the VPN group-membership support article (S-ffrzumip) says a TGT can be renewed for 10 days, while the Kerberos policy page (S-fn2rot77) gives 7 days as the default for Maximum lifetime for user ticket renewal. Both read 2026-09-27; the kb keeps 7 days as the policy default. (topic: auth/propagation-latency)
  - Still open 2026-10-21: re-read both pages: the VPN support article (S-ffrzumip, updated 2026-02-12) still says "A TGT can be renewed for 10 days" while the Kerberos policy page (S-fn2rot77, last updated 2017-04-19) lists 7 days as the Default Domain Policy value; no page ties the 10 days to a setting. `klist tgt` on a lab domain-joined client (its `Renew Time` against the start time) with the domain's policy value would settle it.

## auth/group-claims

- Implicit-flow group limit: S1284 (Configure group claims) says five groups and hasgroups only above five; S1285 (Zero Trust: group claims and app roles) says six groups for the implicit flow. (topic: auth/group-claims)
  - Re-read 2026-09-27, still open: a third Microsoft page, Customize tokens (S-azppyixp), says six for implicit grant in a hybrid flow; S1284 still says five. (topic: auth/group-claims)
  - Still open 2026-10-21: re-read all three pages: S1284 (updated 2025-04-09) says five groups and `hasgroups` only above five; S1285 (updated 2025-10-24) and Customize tokens (S-azppyixp, updated 2024-03-14) say six for the implicit flow, the latter "as part of a hybrid flow". The newest page says six but none explains the difference. An Entra test app with implicit grant enabled and a user in six groups, checking whether the ID token carries `groups` or `hasgroups`, would settle it.

## entra/connect-and-cloud-sync

- Cloud Sync device synchronization: the decision guide (S-6q5tyxki, updated 2026-06-15) marks device synchronization / hybrid join as not currently supported in Cloud Sync, while device-sync.md (S550, ms.date 2026-07-21) documents Cloud Sync device sync in preview (AD2AADDeviceSync job, disabled by default, devices can become hybrid joined). Likely the guide predates the preview; lines 14/24 (S-6q5tyxki) and 37 (S550) now state each source as written. (topic: entra/connect-and-cloud-sync)
  - Re-read 2026-09-27, still open: the decision guide (updated_at 2026-06-15, unchanged) still lists Device Synchronization among Connect-only capabilities and routes hybrid-join device sync to Connect, while the device sync page documents the preview. (topic: entra/connect-and-cloud-sync)
  - Resolved 2026-10-21: the decision guide (S-6q5tyxki) was updated after the reading above. Its comparison table now lists Device Synchronization as supported by both Connect Sync and Cloud Sync ("enable device sync separately in Cloud Sync"), its readiness list tells hybrid join users to include device sync in the migration plan, and the hybrid scenarios page lists Microsoft Entra hybrid join as supported by Cloud Sync. That agrees with the device sync page (S550); the article lines already state the updated guide.

## gitlab/protected-branches-tags

- S444 (protected.md @56c82a97) is internally inconsistent on an unconfigured 'Allowed to push and merge': the Push and merge permissions table says 'No one can push' (and the Developer table shows no direct push), but a note on the same page says an unconfigured setting 'does not restrict push access' and must be set to 'No one' explicitly. protected-branches-tags.md line 22 follows the table. (topic: gitlab/protected-branches-tags)
  - Resolved 2026-10-21: S444's source row pins `56c82a97` (the wording this entry quotes) and records the census read of 2026-10-21 at `a1faf261a899`. Read raw at `a1faf261a899`, the table row for **Allowed to push and merge** still says "No one can push" as its default, and the note under the protection strategies now reads "When you clear every selection in **Allowed to push and merge** on an existing rule, no one can push. When you create a branch rule, GitLab selects **Maintainers** for **Allowed to push and merge**. To prevent direct pushes, set **Allowed to push and merge** to **No one**." The "does not restrict push access" note of the pinned text is gone, so the later text agrees with the table; `gitlab/protected-branches-tags` follows the table. [DOC S444]

## auth/workload-identity

- GitLab flexible federated identity credential claims: the flexible FIC page (S1294) lists only `sub` (eq, matches) and `project_id` (eq) as supported and requires sub plus project_id for mutable subjects; the mutable-subjects page (S1278) says a GitLab flexible FIC must match sub and one or more of project_id, namespace_id, user_id, and shows examples using namespace_id and user_id. Both re-read 2026-09-27. (topic: auth/workload-identity)
  - Re-read 2026-09-27: unchanged on both live pages (S1294 updated 2026-09-23; S1278 updated 2026-07-30). (topic: auth/workload-identity)
  - Still open 2026-10-21: re-read both live pages: S1294 (updated 2026-09-23) still lists only `sub` and `project_id` for GitLab and requires both; S1278 (updated 2026-07-30) still says `sub` plus one or more of `project_id`, `namespace_id`, `user_id`, though every example it shows also matches `project_id`. Creating a flexible federated identity credential with `sub` and `namespace_id` only, and checking whether Entra ID accepts it, would settle it.

## intune/platform-scripts

- S-p4fis3e4 (run-powershell-scripts-windows) says devices only registered with Microsoft Entra ID don't receive scripts, while S-ta4g5get (management-extension-windows) lists Microsoft Entra registered/workplace-joined devices among IME prerequisites; both re-read 2026-09-27. (topic: intune/platform-scripts)
  - Still open 2026-10-21: re-read. S-p4fis3e4 still says in its prerequisites that devices "only registered with your workplace or organization in Microsoft Entra ID don't receive the scripts", yet its targeting section still says that for workplace joined (WPJ) devices only Entra device security groups can be used; S-ta4g5get still lists Microsoft Entra registered/Workplace joined devices among the Intune management extension prerequisites. Assigning a PowerShell script to a lab device that is Entra registered and Intune enrolled would settle it.

## graph/permissions

- Permissions reference (S524) says application Device.ReadWrite.All does not allow device deletion, but the Delete device permissions include (S515) lists Device.ReadWrite.All as the application permission for DELETE /devices/{id}. Recorded in graph/permissions.md:24. (topic: graph/permissions)
  - Reviewed 2026-09-28, still open: not re-read; a tenant test of DELETE with Device.ReadWrite.All would settle it.
  - Still open 2026-10-21: re-read both: the permissions reference (S524, docs-contrib main) still describes application `Device.ReadWrite.All` as not allowing "device creation, device deletion or update of device alternative security identifiers", and the Delete device permissions include (S515) still lists `Device.ReadWrite.All` as the application permission. A `DELETE /devices/{id}` with an app that holds only that permission in a lab tenant would settle it.

## graph/microsoft365dsc

- Microsoft365DSC release 1.26.909.1 ships MOF-based function resources (S-3aphi7n2), while the Dev branch at 2026-09-26 has converted resources to class-based [DscResource()] classes without .schema.mof (S-omyb2en3); facts about resource shape depend on version. (topic: graph/microsoft365dsc)
  - Re-checked 2026-09-28, still stands: 1.26.909.1 is still the latest release, and `MSFT_AADUser` on Dev (70a46e5b) still has no `.schema.mof`. Settles when a release ships the class-based resources. (topic: graph/microsoft365dsc)
  - Resolved 2026-10-21: the shape depends on the version, and a release now carries the class-based shape. At release tag 2.26.1015.1 (GitHub, 2026-10-14, now the latest release) `MSFT_AADUser` holds only MSFT_AADUser.psm1, readme.md and settings.json, with no .schema.mof, and its psm1 declares `[DscResource()]` and `class AADUser : M365DSCResourceBase`; at release tag 1.26.909.1 the same directory still holds MSFT_AADUser.schema.mof. MOF-based for 1.x, class-based for 2.x. The article's hedge that the shape at a release tag was not confirmed is recorded as a gap.

## intune/ios-android-management

- Minimum iOS version for account driven user enrollment: the Apple enrollment guide (S-wdoafrjc) says "Starting with iOS 13 and newer", while the Apple User Enrollment overview (S-7synnxi2) and the account-driven setup page (S-fdtw5sil) say iOS/iPadOS 15 or later (14.9 and earlier fall back to user enrollment with Company Portal). Kb follows 15+. (topic: intune/ios-android-management)
  - Reviewed 2026-09-28, still open: not re-read; the kb follows 15+.
  - Still open 2026-10-21: re-read the three pages: the enrollment guide (S-wdoafrjc) still says "Account driven user enrollment: Starting with iOS 13 and newer", while the Apple User Enrollment overview (S-7synnxi2) still lists account-driven enrollment as iOS/iPadOS 15 or later, and the account-driven setup page (S-fdtw5sil) still says 15 or later with an automatic fall back to user enrollment with Company Portal for 14.9 and earlier. An edit of the guide would settle it; the kb follows 15+.
- End of Intune support for Android device administrator on GMS devices: the Android enrollment guide (S-3v22wodo) says August 2024; the device administrator page (S-pcr6rjdl) says end of 2024. Both re-read 2026-09-27. (topic: intune/ios-android-management)
  - Narrowed 2026-10-21: Microsoft's Intune blog post "Intune ending support for Android device administrator on devices with GMS in December 2024" (techcommunity.microsoft.com/t5/intune-customer-success/microsoft-intune-ending-support-for-android-device-administrator/ba-p/3915443, linked from the device administrator page, last modified 2024-11-13; not a kb source row) says support ends beginning December 31, 2024, and its change log shows an earlier August 30, 2024 date replaced. So "end of 2024" (S-pcr6rjdl, re-read 2026-10-21) is the current date and "August 2024" (S-3v22wodo, re-read 2026-10-21, unchanged) is the stale one. It settles in the enrollment guide when Microsoft updates it.

## prior-art/secret-vault-encryption

- reuse/secret-vault-encryption.md:22 (outside this unit) still states age has no expiry/revocation/audit log as confirmed by its own README; S1001 README re-read 2026-09-27 does not state it (now UNK in prior-art/secret-vault-encryption.md). (topic: prior-art/secret-vault-encryption)
  - Resolved 2026-10-21: `reuse/secret-vault-encryption` and `prior-art/secret-vault-encryption` now state it as derived from the age format specification (a header of recipient stanzas, a header MAC and a payload, no field for expiry, revocation or audit), not as the README's own statement. [DER S-f4s2xnfz]

## security/policy-precedence

- Policies-key cleanup: the FSLogix Group Policy page (S-z4y7mew3) says settings under `HKLM\SOFTWARE\Policies\FSLogix\ODFC` reset themselves when the GPO is removed or set to *Not Configured*; the `Remove-GPRegistryValue` page (S-is2wluoa) says removing a registry-based policy setting (example under `...\Policies\...`) from a GPO does not delete the value on clients, and the setting must be disabled to delete it. Both read 2026-09-27; the pages describe different actions (GPO removed vs one setting removed from a GPO that still applies) but no page states the general rule. (topic: security/policy-precedence)
  - Still open 2026-10-21: both pages were confirmed unchanged in the census of 2026-10-21 (FSLogix S-z4y7mew3, updated 2026-03-30; Remove-GPRegistryValue S-is2wluoa): one says ODFC values under `Policies\FSLogix\ODFC` reset when the GPO is removed or set to Not Configured, the other that removing one setting from a still-applied GPO leaves the client value. They describe different actions and no page states the general rule. In a lab, removing one `Policies` registry setting from an applied GPO and checking the client value after `gpupdate` would settle it.

## security/privacy-compliance

- AI Omnibus political agreement date: privacy-compliance.md:74-76 (COMMUNITY S1558) says provisional agreement 2026-05-06; the Commission page S1557 re-read 2026-09-27 says a political agreement was reached on 7 May 2026 (and entry into force 27 July 2026). (topic: security/privacy-compliance)
  - Re-read 2026-09-27, still open: the Commission press release IP/26/1024 (S-tzbutlvs, published 2026-05-07 07:59 CEST) says the agreement was "reached today"; the Council release (dated 2026-05-07 in its url, a search snippet says 6 May) could not be read past its browser check. The article now leads with the Commission's date and keeps S1558's 6 May as COMMUNITY. (topic: security/privacy-compliance)
  - Resolved 2026-10-21: the Commission press release IP/26/1024 (S-tzbutlvs, published 2026-05-07) says the agreement was reached "today", and the Commission page S1557 gives 7 May 2026; both are the primary record and `privacy-compliance` leads with that date. S1558 (COMMUNITY) keeps 6 May as a lead only; the Council release stayed unreadable behind its browser check. [DOC S1557, S-tzbutlvs; COMMUNITY S1558]

## windows/azure-arc-servers

- The Azure SDK AgentConfiguration model (S-75xvev6g) describes agent configuration properties as settable 'locally via the azcmagent config command, or remotely via ARM', while Extensions security for Azure Arc-enabled servers (S-efadnhwv) says the local agent security controls can only be set on the server itself and can't be modified from Azure. (topic: windows/azure-arc-servers)
  - Re-checked 2026-09-28, still stands: the Az.ConnectedMachine models mark `guestConfigurationEnabled` read-only (no create or update) and the security pages (S-efadnhwv, S-wvoeevrw) say the controls are set only on the machine, while the Python SDK docstring still says ARM can set them. (topic: windows/azure-arc-servers)
  - Still open 2026-10-21: re-read. Extensions security (S-efadnhwv) still says the local agent security controls "can only be configured by running a command on the server itself, and they can't be modified from Azure", and Configuration and remote access (S-wvoeevrw) gives the commands as "run locally on each machine". The azcmagent FAQ says the Azure CLI changes "certain settings of the Arc server remotely" without naming them, and the Python SDK AgentConfiguration docstring still reads "set locally via the azcmagent config command, or remotely via ARM". Two security pages against one SDK docstring. Updating the Arc machine resource through ARM in a lab to set an agent configuration property and then reading `azcmagent config list` on the machine would settle it.
- Machine Configuration parameter types: S-nibv7ci5 says Azure Policy parameters passed to guest assignments must be string (no arrays); S-lkmpjpnp (create-policy-definition) lists String, Boolean, Double and Float as supported parameter value types. Re-read 2026-09-27. (topic: windows/azure-arc-servers)
  - Narrowed 2026-10-21: re-read both live pages. The behaviour-changes page (S-nibv7ci5) still says parameters in Azure Policy that pass values to machine configuration assignments "must be string type" and that "It isn't possible to pass arrays"; the create-policy-definition page (S-lkmpjpnp) still lists String, Boolean, Double and Float as supported parameter value types and lists no array type. Both therefore agree that arrays are not supported; the open point is only whether Boolean, Double and Float values reach the assignment as such or as strings. Assigning a custom policy that defines a Boolean parameter in a lab and reading the configurationParameter value of the guest assignment would settle it.
- Azure Arc gateway status: S-wwbtoald (agent-overview) still calls it 'Limited preview'; the kb had stated GA with no source (now UNK). S-szyeetyp only says it reduces required endpoints. Re-read 2026-09-27. (topic: windows/azure-arc-servers)
  - Resolved 2026-09-28 in favour of GA: agent release notes version 1.58 (November 2025, S-jduwmt53) remove the Preview flag because the gateway was promoted to General Availability, and the Arc gateway page (updated 2026-05-19) carries no preview label; agent-overview (updated 2026-07-28) still says "Limited preview", a stale label. (topic: windows/azure-arc-servers)

## security/supply-chain

- PyPI's Adding a Trusted Publisher page (S1597) says GitLab self-managed instances are not supported, while Socket (S1510, 2025-11-14) reports PyPI opened a beta for GitLab Self-Managed with manual onboarding. (topic: security/supply-chain)
  - See the re-read note above: the beta is confirmed by PyPI itself (S-5ry5zerr); the docs page is out of date. (topic: security/supply-chain)
  - Reviewed 2026-09-28, not a source disagreement: duplicate of the supply-chain entry above, which records PyPI's own blog confirming the beta.

## windows/bitlocker

- BitLocker CSP ConfigureRecoveryPasswordRotation default (S-pfrwongj): prose says not configured = rotation on for Entra ID only and off on hybrid; the value list labels 2 as 'Default value'; the description-framework table gives Default Value 0. Re-read 2026-09-27. (topic: windows/bitlocker)
  - Still open 2026-10-21: re-read the BitLocker CSP page (S-pfrwongj). The prose still says that when not configured "Rotation is turned on by default for Entra ID only and off on hybrid", the supported-values list still puts "Default value" on value 2, and the description framework table still gives Default Value 0 with "0 (Default) Refresh off". The Intune disk encryption settings reference additionally says Not configured (default) means "The client won't rotate BitLocker recovery keys". Reading the node with a Get on an Entra joined lab device with the policy unset, and checking whether the recovery password rotates after a recovery, would settle it.
- Automatic device encryption prerequisite: S-sr7tk6jz requires Modern Standby AND HSTI compliance (1703+); S-jdytzqlj and S-7qrbvran say Modern Standby OR HSTI (removed entirely in Windows 11 24H2 per S-7qrbvran). Re-read 2026-09-27. (topic: windows/bitlocker)
  - Narrowed 2026-10-21: re-read. The OEM page (BitLocker drive encryption in Windows 11 for OEMs) and the BitLocker overview (S-7qrbvran) both say Modern Standby or HSTI, and both say the requirement is removed from Windows 11 24H2. The AND in the Intune known-issues page (S-sr7tk6jz) sits in its list of requirements for the Intune setting that enables automatic device encryption for Autopilot devices with standard users, which also names Windows 10 1803 or later, not in a statement of the general automatic device encryption prerequisite; S-jdytzqlj states the general prerequisite as Modern Standby or HSTI. What remains open is whether the Autopilot standard-user setting still needs both on 24H2, which a lab Autopilot enrolment of a standard user on a 24H2 device without HSTI would show.

## windows/delivery-optimization

- DOCacheHost with several Connected Cache servers: the DO reference (S-7olkz3h6) says clients round-robin across connection attempts and can download from several cache servers simultaneously; the Policy CSP note (S-3dmxye5u) says clients don't talk to several servers at once and round-robin until one connects; the configure page (S-kyd2lkfv) says clients connect in list order. (topic: windows/delivery-optimization)
  - Reviewed 2026-09-28, still open: not re-read; three pages describe the behaviour differently. A lab capture would settle it.
  - Still open 2026-10-21: re-read the three pages: the Delivery Optimization reference (S-7olkz3h6) still says clients select Connected Cache servers round-robin across connection attempts and can download from several at once, the Policy CSP page (S-3dmxye5u) still says clients don't talk to several at the same time and round-robin until one connects, and the configure page (S-kyd2lkfv) still says clients connect in list order. A capture of a client with two `DOCacheHost` servers in a lab would settle it.
- MCC HTTPS: the secure-content-delivery page (S-s4n26zjf) still says nodes use HTTP and HTTPS support is planned; the HTTPS overview (S-umnfbn5b) says since GA nodes can be configured for HTTPS (Intune Win32 apps and Teams). (topic: windows/delivery-optimization)
  - Reviewed 2026-09-28, still open: Learn search shows the secure-content-delivery page still says HTTPS support is planned, while the HTTPS overview describes GA HTTPS for Win32 apps and Teams.
  - Still open 2026-10-21: re-read both pages: the secure content delivery page (S-s4n26zjf) still says Connected Cache nodes use HTTP and that HTTPS is planned, and the HTTPS overview (S-umnfbn5b) still says that with the general availability release nodes can be configured for HTTPS. An edit of the secure content delivery page would settle it.

## windows/laps

- Invalid ADPasswordEncryptionPrincipal: Configure policy settings for Windows LAPS (S-twjwzzdw) says the Domain Admins default applies only when unset and an invalid name causes a policy processing failure with no backup; the LAPS CSP page (S-jmzxsdjr) says the device falls back to Domain Admins. (topic: windows/laps)
  - Reviewed 2026-09-28, still open: Learn search shows both pages unchanged: the LAPS CSP page says the device falls back to Domain Admins; the policy settings page says a policy processing failure occurs.
  - Still open 2026-10-21: re-read both pages: the policy settings page (S-twjwzzdw) still says an invalid `ADPasswordEncryptionPrincipal` causes a policy processing failure and the password isn't backed up, and the LAPS CSP page (S-jmzxsdjr) still says the device falls back to the Domain Admins group. Setting an invalid principal on a lab device and reading the LAPS event log would settle it.

## windows/windows-update-management

- Windows 10 consumer ESU end date: the kb said security updates through 2026-10-13; the consumer ESU page (S-fllu73v2, re-read 2026-09-27) now says the program and coverage run through 2027-10-12. Fact corrected from the source; the Learn ESU page (S-hdprezk3) gives no consumer end date. (topic: windows/windows-update-management)
  - Resolved 2026-10-21: the consumer ESU page (S-fllu73v2, fetched 2026-10-21) says "the program ends on October 12, 2027" and that both enrollment options provide updates "through October 12, 2027"; the Lifecycle FAQ for Extended Security Updates lists the Windows 10 ESU year 2 end date as October 12, 2027. The fact is already corrected to that date; the Learn ESU page (S-hdprezk3) still gives no consumer end date and points consumers to the consumer page.

## intune

- Endpoint analytics in Adoption Score: the Intune page (S-m5aovwzr, updated_at 2026-04-09) still describes the Adoption Score Endpoint analytics page (score, 180-day trend, startup performance), while the Microsoft 365 Adoption Score page (S-3l57sxrb, updated_at 2026-09-23) says Endpoint analytics was retired from Adoption Score starting 2026-01-22, complete February 2026. The newer M365 page is the likelier current state. (topic: intune/device-inventory-analytics)
  - Reviewed 2026-09-28, still open: not re-read; the newer Microsoft 365 page is followed.
  - Still open 2026-10-21: re-read both pages: the Microsoft 365 Adoption Score page (S-3l57sxrb, last updated 2026-06-23) still says that starting 2026-01-22 the Technology experiences score and its categories, Endpoint analytics among them, are retired from Adoption Score, completing in February 2026, and the Intune page (S-m5aovwzr, last updated 2025-12-11) still describes the Endpoint analytics page in Adoption Score with no retirement note. An edit of the Intune page would settle it; the newer Microsoft 365 page is followed.
- Linux personal devices: the end-user page Enroll Linux device in Intune (S-dnply3ya, updated_at 2026-04-29) says enrolled Linux devices are corporate-owned and personal devices aren't supported, while the admin deployment guide (S-5vopvhhm) and platform guide (S-nvad3j6y) say employees can enroll their personal Linux devices. (topic: intune/linux-management)
  - Reviewed 2026-09-28, still open: not re-read.
  - Still open 2026-10-21: re-read the pages: the end-user page (S-dnply3ya) still says enrolled Linux devices are corporate-owned and that device enrollment isn't supported with personal devices, while the enrollment guide (S-5vopvhhm) says "Use for personal/BYOD and organization-owned devices running Linux" and the platform guide (S-nvad3j6y) says employees can enroll their personal Linux devices. An edit of the end-user page would settle it.

## entra

- Blueprints per pro-code agent: the Agent 365 Copilot Studio identity page (S-ketmxnue, updated_at 2026-05-19) says each pro-code agent has its own blueprint, while Entra's planning guide (S-3tt3ywvk, updated_at 2026-08-14) defaults to one blueprint per trust boundary with several agent identities under it. Follow the Entra guide for design; the Agent 365 sentence reads as a simplification. (topic: entra/agent-id)
  - Reviewed 2026-09-28, still open: not re-read; the Entra guide is followed for design.
  - Still open 2026-10-21: re-read both pages: the Agent 365 Copilot Studio page (S-ketmxnue) still says "Unlike pro-code agents where each agent has its own blueprint", and the Entra planning guide (S-3tt3ywvk) still defaults to "one blueprint per trust boundary". An edit of the Agent 365 page would settle it; the Entra guide is followed for design.

## windows/smart-app-control

- Smart App Control re-enable path: the Learn developer pages say SAC can only be enabled on a clean install (S2198) and that Off and On are one-way in Settings (S2199), while the March 2026 update note KB5079391 (S-5zawgrph) and the consumer FAQ (S-n2kx46hd) say SAC can now be turned on or off without a clean install. The rollout is gradual, so both hold on different builds until the Learn pages are updated. Read 2026-09-28. (topic: windows/smart-app-control)
  - Still open 2026-10-21: re-read. The consumer FAQ (S-n2kx46hd, fetched) still says "Recent Windows updates allow Smart App Control to be enabled without requiring a clean installation" and that it can be re-enabled the same way; the Learn test-your-app page (S2199) still says configuring Smart App Control to Off or On "is a one-way operation. You can't change modes by using Windows Settings unless the current setting is Evaluation". No page names the build from which the change applies or dates the Learn page against it. Toggling Smart App Control off and on in Windows Security on a build before and after KB5079391 in a lab would settle it.

## arch/sql-auth-containers

- ODBC `ActiveDirectoryDefault`: the Microsoft SQL driver feature matrix (S-g2zvqta5) marks "Microsoft Entra default Azure authentication" as not supported by the ODBC driver on Windows or Linux/macOS, and the ODBC `Authentication` keyword list (S1610) has no `ActiveDirectoryDefault`, while the mssql-django Entra page (S-67zasdym) shows `Authentication=ActiveDirectoryDefault` with ODBC Driver 18 and says mssql-django 1.7.3+ passes it through to the driver. Read 2026-09-28; a driver test settles it. (topic: arch/sql-auth-containers)
  - Narrowed 2026-10-21: re-read the driver feature matrix (S-g2zvqta5, updated 2026-09-30), which still lists "Microsoft Entra default Azure authentication" as No for the ODBC driver on Windows and on Linux and macOS; the ODBC Entra page (S1610, updated 2026-10-20) names no `ActiveDirectoryDefault`; the mssql-django page (S-67zasdym, updated 2026-09-29) says 1.7.3+ passes the mode through "when the installed Microsoft ODBC Driver for SQL Server supports that mode", so it does not claim ODBC support. Connecting with ODBC Driver 18 and `Authentication=ActiveDirectoryDefault` would settle whether the driver accepts it.

## windows/windows-sandbox

- Printer redirection and video input defaults in the WindowsSandbox Policy CSP: the page (S-bgz3uymb) says that when `AllowPrinterRedirection` or `AllowVideoInput` is not configured the capability is disabled, and the .wsb page (S-hlmmxoye) agrees for a default sandbox, yet the same CSP page lists `Default Value` 1 (allowed) for both. It also maps `AllowWriteToMappedFolders` to the Group Policy name and registry value `AllowMappedFolders`. Read 2026-09-28; a device test (registry and sandbox behaviour with the policy unset) settles it. (topic: windows/windows-sandbox)
  - Still open 2026-10-21: re-read the WindowsSandbox Policy CSP page (S-bgz3uymb) for AllowPrinterRedirection and AllowVideoInput: the prose still says that when the policy is not configured printer redirection and video input are disabled, while the description framework table still gives Default Value 1 and "1 (Default)" for Allowed. The .wsb page (S-hlmmxoye) and the AllowWriteToMappedFolders mapping were not re-read in this pass. Reading the registry and the sandbox behaviour on a lab device with the policy unset would settle it.

## agents/codebase-mapping

- **`tsc` with files named on the command line and a `tsconfig.json` present.** The TypeScript handbook page on tsconfig (S-3e3kl7vi) says `tsconfig.json` is ignored when input files are named on the command line; the TypeScript 7.0.2 native compiler source (S-gfjnysog, tag typescript/v7.0.2) reports an error in that case and offers `--ignoreConfig` to skip it. Both read 2026-09-29; the handbook is not versioned by release, so this may be a 7.0 behaviour change rather than a doc error; a run of `tsc 5.x` and `tsc 7.x` in a lab settles it. (topic: agents/codebase-mapping)
  - Resolved 2026-10-15: the TypeScript 6.0 announcement (S-sp2a6svk) documents it as a 6.0 behaviour change, error TS5112 with `--ignoreConfig` to skip, and the 7.0 announcement (S-eq3gt72a) says 7.0 keeps it; the handbook text describes 5.x and earlier. (topic: agents/codebase-mapping)

## claude/cross-session-messaging

- Native Windows minimum version: the cross-session messaging page (S-sdxhnx3i) says native Windows needs Claude Code v2.1.234 or later, while the changelog (S746) lists "Windows: cross-session messaging is now available" under v2.1.239 (August 21, 2026). The v2.1.234 entry has no Windows line. Read 2026-09-30; a `/list-agents` check on native Windows with v2.1.234 settles it. [DOC S-sdxhnx3i vs S746, unresolved] (topic: claude/cross-session-messaging)
  - Resolved 2026-09-30: the week 34 digest (S-d3ythwgb, releases v2.1.234 to v2.1.239) also announces native Windows support, agreeing with the changelog's v2.1.239 entry; no release note puts it in v2.1.234. The article keeps both DOC statements and recommends v2.1.239+ on native Windows (DER), which satisfies either reading; v2.1.234 to v2.1.238 on Windows stay unverified. (topic: claude/cross-session-messaging)

## agents/decision-records

- Editing an accepted decision record: AWS (S-jqks66nz) says a record is immutable once accepted and a change needs a new record that supersedes it, and Azure (S-efm54uef) calls the log append-only and says not to edit accepted records, while Google's overview (S-l52pzhgp) says to revisit the ADR as the team learns and, when adjusting, to include the previous decision and why it changed in the same record. Read 2026-10-01. Not settled by a source: the article records both, and the append-only form is the one two of three cloud vendors and Nygard (S-neg7qqfq) give. [DOC S-jqks66nz, S-efm54uef vs S-l52pzhgp] (topic: agents/decision-records)
  - Reviewed 2026-10-21, not a source disagreement: the sources give differing advice on practice (an accepted record is immutable or may be revised in place), not differing facts; the article records both and names which form two of three cloud vendors and Nygard give. [DOC S-jqks66nz, S-efm54uef, S-l52pzhgp]

## agents/agent-caching

- **Sonnet 5.5 cache-read price: documented $0.10 per MTok, billed $0.20.** The pricing page (S2131), read raw 2026-10-09, lists Sonnet 5.5 cache hits at "$0.10 / MTok" with the footnote "Cache hits and refreshes on Claude Opus 5.5 and Claude Sonnet 5.5 are priced at 0.05x the base input price" and says in its caching section "$0.10 USD on Claude Sonnet 5.5"; the prompt-caching page (S2130) gives the same multiplier. The kb states it in `claude/ci-and-headless` (the Sonnet 5.5 list-price fact) and `agents/agent-caching` (the cache-read pricing fact and the per-model price table). `claude -p` runs of Sonnet 5.5 are billed as if cache reads cost $0.20 per MTok (0.1x the $2 input price, the rate of Sonnet 5 and the one S2131 listed for Sonnet 5.5 when read 2026-09-28): on the pool smoke record of 2026-10-08, the cost `claude -p` reported (`total_cost_usd`) was more than 20% above the list price of the run's counted tokens at $0.10 for 25 of 30 runs of each of the two Sonnet 5.5 session labels and 2 of 11 `web-sonnet-5-5` runs, and for none of those 30, 30 and 11 at $0.20 (the two fresh-shape labels, 32 runs each, are within 20% at both), and a `claude -p` probe of 2026-10-09 showed the same. Whether the billing runs a rate other than the page, the page is ahead of or behind the billing, or Claude Code reports a cost on a different basis was not settled. Recorded here, not resolved: a figure that must match what a run is billed uses $0.20, one that must match the page uses $0.10. A re-read of S2131 that states $0.20 or a billing statement for Sonnet 5.5 cache reads settles it. [DOC S2131 vs DER billed cost of `claude -p` runs, unresolved] (topic: agents/agent-caching)
  - Resolved 2026-10-12, as to what `claude -p` reports: the Claude Code changelog entry of v2.1.296 says `/cost`, the status line, `--max-budget-usd` and the SDK's cost figures now price Sonnet 5.5 cache reads at $0.10 per million tokens, "was $0.20", so the $0.20 was the rate of the client's own price table (the result's cost is a client-side estimate, `claude/agent-sdk`), which the release changed to the page's rate. The pricing page, read raw 2026-10-12, still lists $0.10 and "$0.10 USD on Claude Sonnet 5.5". Two `claude -p` runs on Claude Code 2.1.296 (macOS, headless, 2026-10-12, `--model claude-sonnet-5-5 --effort low`) reported `total_cost_usd` $0.0034668 for 34,228 cache-read, 2 input and 4 output tokens and $0.0861351 for 13,031 cache-read, 21,197 1-hour cache-write, 2 input and 4 output tokens, each equal to the counts priced at $0.10, $4 (1-hour write), $2 and $10 per million tokens. A record run on Claude Code 2.1.295 or older that reports a Sonnet 5.5 cost counts cache reads at $0.20, and the harness keeps pricing such a run at $0.20 (`READ_BEFORE` in `bench_core.py`, which also prices a run whose version is empty or unknown at $0.20), so its figure is compared with the cost the run reported and not with the page's $0.10; what Anthropic invoiced for Sonnet 5.5 cache reads on those versions is stated by no document read. [DOC S1864, S2131] (topic: agents/agent-caching)

## gitlab/protected-branches-tags

- Re-read 2026-10-11 at master @9f1632e2 of the conflict recorded above under this heading: the Push and merge permissions table and the note under the protection strategies of S444 are unchanged and still disagree on an unset **Allowed to push and merge**; the Protected branches API page (S-ozrs7es3) gives `40` as the default `push_access_level` of a rule created without one and does not say how that default relates to an unset list in the interface. (topic: gitlab/protected-branches-tags)
  - Resolved 2026-10-21: read raw at `a1faf261a899`, the commit S444's source row records for the census of 2026-10-21 (the row's pin is `56c82a97`), the table and the note under the protection strategies now agree that clearing every selection in **Allowed to push and merge** leaves no one able to push, and the note adds that creating a branch rule selects **Maintainers** for it. That is the same role as the `40` the API page gives as the default `push_access_level` (S-ozrs7es3, as the entry above reads it); neither page says the interface default and the API default are the same setting. See the entry above. [DOC S444, S-ozrs7es3]

## privacy/coreference-resolution-options

- **Licence of the Polish Coreference Corpus: CC BY-NC 4.0 or CC BY 3.0.** The IPI PAN corpus page (S-kdsj7amh, last edited 2023-04-24) says it "offers the official Creative Commons Attribution-NonCommercial 4.0 International License release" and lists `License: CC BY-NC 4.0`. The CorefUD v1.4 licence page (S-el226szq, dated 2026-02-18) lists `CorefUD_Polish-PCC` as CC BY 3.0, with each corpus under its own licence in its directory. Read 2026-10-11. The pages describe two distributions (the IPI PAN release and its CorefUD conversion), so both may be right for their own copy; no source states which terms govern models trained on either. Not settled by a source: the article records both. [DOC S-kdsj7amh vs S-el226szq] (topic: privacy/coreference-resolution-options)
  - Narrowed 2026-10-21: both pages were re-read in the census of 2026-10-21 and are unchanged (S-kdsj7amh last edited 2023-04-24; S-el226szq dated 2026-02-18); they describe two distributions, so the two licences are not a contradiction. What stays open is only which terms govern a model trained on either copy, which no source states; a statement from the corpus authors at IPI PAN would settle it. [DOC S-kdsj7amh, S-el226szq]

## arch/fluent-rust-typescript

- **fluent-bundle README example vs the 0.16.0 API.** The README at tag `fluent-bundle@0.16.0` (S-pz6n3xzv) reads the message value as a field, `msg.value.expect(...)`, while `message.rs` at the same tag (S-2xwgfues) defines `FluentMessage` with a private `node` field and a `value()` method, and the crate-level and `FluentBundle` doc examples (S-vktfavae) call `msg.value()`. Read 2026-10-11. The code is the API; the README snippet does not compile against 0.16.0. [CODE S-2xwgfues, S-vktfavae vs DOC S-pz6n3xzv] (topic: arch/fluent-rust-typescript)
  - Resolved 2026-10-21: `fluent-bundle@0.16.0` is the newest tag (census of 2026-10-21); its code defines `FluentMessage` with a private `node` field and a `value()` method (S-2xwgfues) and its own doc examples call `msg.value()` (S-vktfavae), so the code is the API and the README's `msg.value.expect(...)` snippet (S-pz6n3xzv) is the stale statement; the article states `value()`. [CODE S-2xwgfues, S-vktfavae; DOC S-pz6n3xzv]
- **`eslint-plugin-i18next` licence.** The repository LICENSE file at tag `v6.1.5` is the MIT text, while `package.json` at the same tag (S-nmwvmitf) and the npm registry metadata declare `ISC`. Read 2026-10-11. Not settled by the project; the article records MIT from the LICENSE file and notes the mismatch. [COMMUNITY S-l53lrqoz vs S-nmwvmitf] (topic: arch/fluent-rust-typescript)
  - Still open 2026-10-21: `v6.1.5` is still the newest tag (census of 2026-10-21); its LICENSE file is the MIT text and `package.json` (S-nmwvmitf) says `ISC`, and the project states no rule for which governs. A maintainer statement or a corrected `package.json` or LICENSE file would settle it; the article keeps recording MIT from the LICENSE file and the mismatch. [COMMUNITY S-l53lrqoz vs S-nmwvmitf]

## privacy
- GLiREL licence: the README at v1.2.1 and the `jackboyla/glirel-large-v0` card text say CC BY-NC-SA 4.0 (S-ngy65th6, S-w6u6mtcx), while `pyproject.toml` at v1.2.1 and the PyPI metadata say Apache-2.0 (S-uu7ov3pw, S-pjp4rzor); the repository has no `LICENSE` file at v1.2.1 or on main and the model card has no licence field. The kb states both and does not choose. (topic: privacy/gliner-glirel-zero-shot)
  - Still open 2026-10-21: v1.2.1 is still the newest tag (census of 2026-10-21); the README and the model card still say CC BY-NC-SA 4.0 while `pyproject.toml` and PyPI say Apache-2.0, with no `LICENSE` file at the tag. A `LICENSE` file or a maintainer statement from the GLiREL authors would settle it; until then the article states both. [DOC S-ngy65th6, S-w6u6mtcx vs S-uu7ov3pw, S-pjp4rzor]
- `urchade/gliner_large-v2.1` language: the card front matter (and HF tags) say `multilingual`, while the same card's model table lists it as English and its config names `microsoft/deberta-v3-large`, not the multilingual mDeBERTa encoder of `gliner_multi-v2.1` (S-dwg2wis7, S-2fmzqhdr). The kb reports the table and the encoder, and the front matter as a tag only. (topic: privacy/gliner-glirel-zero-shot)
  - Resolved 2026-10-21: the `gliner_large-v2.1` config (S-2fmzqhdr) names `microsoft/deberta-v3-large`, an English-only encoder, so the model is English by construction; the card's front matter `multilingual` (S-dwg2wis7) is a tag that contradicts the card's own table, and the article reports the table and the encoder. [DER S-dwg2wis7, S-2fmzqhdr]
- `urchade/gliner_multi-v2.1` size: the card table gives 209M parameters (S-7ke3sttd), the HF API safetensors metadata gives 288,949,504 F32 parameters in a 1,155,830,112-byte file (S-wrx2q5ya). The kb states both; the API parameter count is consistent with the file size (see the note below). (topic: privacy/gliner-glirel-zero-shot)
  - Resolved 2026-10-21: the Hugging Face API metadata (S-wrx2q5ya) reports 288,949,504 F32 parameters and a 1,155,830,112-byte `model.safetensors`. At 4 bytes per F32 parameter the parameters take 1,155,798,016 bytes, which leaves 32,096 bytes of the file; that remainder is arithmetic from the two API figures, not a header size any source states or this pass measured, so the file size is consistent with about 289M parameters plus a small non-parameter remainder. The card's 209M (S-7ke3sttd) is the author's stated figure and is not consistent with the file's size. The article (`privacy/gliner-glirel-zero-shot`, line 32) states both figures and marks neither as the one that matches. [DOC S-wrx2q5ya, S-7ke3sttd; DER the subtraction]

## arch/gorules-zen-engine

- **`passThrough` default on table, expression and decision nodes: docs say true, the Rust struct reads as false.** The node-types page (S-cdmzxvsn, read raw 2026-10-11) lists `passThrough` with default `true`; `TransformAttributes` at zen-engine-v2.1.3 (S-heikuvcn) declares `#[serde(default)] pub pass_through: bool`, which is false when the key is absent, and the handlers branch on `self.pass_through`. Files saved by the editor write the key, so the difference shows only for hand-written JDM. Not run, so not settled: a hand-written file should set `passThrough` explicitly. [DOC S-cdmzxvsn vs CODE S-heikuvcn: core/types/src/decision/mod.rs#TransformAttributes] (topic: arch/gorules-zen-engine)
  - Still open 2026-10-21: the census of 2026-10-21 re-read the docs page (S-cdmzxvsn, `passThrough` default `true`); the code at zen-engine-v2.1.3 (S-heikuvcn) still reads as `false` for an absent key, and no newer tag was checked. Running a hand-written JDM file without `passThrough` through the engine (`zen-engine` Python or Node binding) would settle it; the article advises setting the key explicitly. [DOC S-cdmzxvsn vs CODE S-heikuvcn]

## arch/python-single-package-extras

- **Workspace members "always" editable vs editable by default with an opt-out (arch/python-single-package-extras and python/uv-projects).** uv's dependencies page (S1706, read raw 2026-10-13; the 0.12.19 `dependencies.md` matches) says in its workspace-member section "Workspace members are always editable", and in its editable-dependencies section "uv uses editable installation for workspace packages by default" with `uv add --no-editable ./path/foo` to opt out in a workspace. The locking and syncing page (S-wmmyfoun) says `uv sync` installs the project and other members as editable packages and `--no-editable` opts out. The page's own two sentences differ; not settled by a source. `arch/python-single-package-extras.md` states editable by default with the opt-out and gives "always editable" as the page's dependency-source wording; `python/uv-projects.md` (editable lines) states editable with the opt-out and has no "always editable" text. [DOC S1706 vs itself; DOC S-wmmyfoun] (topic: arch/python-single-package-extras)
  - Narrowed 2026-10-21: re-read uv's dependencies page at main: the workspace-member section still says members "are always editable" and the editable-dependencies section still says editable by default with `uv add --no-editable ./path/foo` to opt out in a workspace, so the page still differs from itself. The first sentence sits in the section on declaring a member with `{ workspace = true }`, which reads as the source declaration, not the install mode; no page says so. Running `uv add --no-editable` for a member and checking `uv pip show` for an editable location would settle it. [DOC S1706, S-wmmyfoun]

## agents/mmlw-e5-polish-embeddings

- **Reported PIRB NDCG@10 of the `mmlw-e5-large` distilled model.** The model card (S-pxbj347n, repo sha a7d9af002b46) states NDCG@10 of 56.09 on the Polish Information Retrieval Benchmark; the PIRB paper's Table 3 (S-sbuv7mtf, arXiv v2) lists 56.00 for the distilled multilingual-e5 (large) student with `bge-large-en` as teacher before fine-tuning. For small (47.64) and base (53.56) card and paper agree to the digit. Not settled which run the card's figure comes from; a difference of 0.09. [DOC S-pxbj347n vs DOC S-sbuv7mtf, unresolved] (topic: agents/mmlw-e5-polish-embeddings)
  - Still open 2026-10-21: the model card (S-pxbj347n), re-read 2026-10-21, still says NDCG@10 of 56.09 and the PIRB paper's Table 3 (S-sbuv7mtf) lists 56.00; neither names the run behind its figure. The PIRB leaderboard entry for the model or its authors would settle which run the card reports.

## privacy
- spaCy `pl_core_news_*` versions: GitHub releases have 3.8.0 (2024-09-30, S-haoeqge5, S-pxcitvg3, S-sirpm4j2, spaCy `>=3.8.0,<3.9.0`). The Hugging Face repos were last modified 2023-10-10 with card version 3.7.0 (spaCy `>=3.7.0,<3.8.0`, S-tzw22ffl for sm). Both say GPL-3.0. (topic: privacy/morfeusz-polish-lemmatisation)
  - Reviewed 2026-10-21, not a source disagreement: the GitHub releases (3.8.0, 2024-09-30) and the Hugging Face repos (last modified 2023-10-10, card 3.7.0) are two distribution channels with different dates, both GPL-3.0; the article states each with its date. [DOC S-haoeqge5, S-pxcitvg3, S-sirpm4j2, S-tzw22ffl]

## agents/onnx-runtime-rust-ort

- The default API level of `ort` 2.0.0-rc.13. The Multiversioning page (S-o3nqheje) says the latest API version, `api-28`, "is enabled by default"; the manifest at the same tag (S-pwbxp7jw) lists `api-27` in `default` and carries `api-28` as an opt-in feature. The source at the tag decides what a build gets (`api-27`), so a build that needs a method marked `api-28` sets that feature itself; a later release or a docs fix settles which one is meant. [DOC S-o3nqheje vs CODE S-pwbxp7jw, unresolved] (topic: agents/onnx-runtime-rust-ort)
  - Narrowed 2026-10-21: the disagreement is specific to `rc.13`; the manifest of tag `v2.0.0-rc.15` (read 2026-10-21 from the repository; not a source row) lists `api-31` in `default`, so neither the `api-27` of the `rc.13` manifest nor the `api-28` of the docs holds for the newest release. The article pins its facts to `rc.13`; rc.15 docs and manifest stay a gap. [DOC S-o3nqheje vs CODE S-pwbxp7jw]
- The `default-features = false` example. The Multiversioning page (S-o3nqheje) shows features `std`, `ndarray`, `download-binaries` and `api-20`; the build script of `ort-sys` at the same tag (S-7srl2gyq) stops with a `compile_error!` when `download-binaries` is on and no `tls-*` feature is, and the Cargo features page (S-m5r2fcso) says a TLS feature is required. By the code the example as printed stops at that check (not built here); the code is the authority. [DOC S-o3nqheje vs CODE S-7srl2gyq, unresolved] (topic: agents/onnx-runtime-rust-ort)
  - Narrowed 2026-10-21: the example and the build script are both `rc.13` facts and the code is the authority there; the `rc.15` build script and docs example were not read (gap), and a build of the printed example on `rc.13` would show the `compile_error!`. [DOC S-o3nqheje vs CODE S-7srl2gyq]
- The review item for S-msk5qtcf shows crates.io `newest_version` `2.0.0-rc.15` where the kb (line 19, and the rc.13 pin advice at lines 20 and 95) says `2.0.0-rc.13` is the highest. The census run could not fetch the crates.io API (curl returned empty), so the version list, MSRV per version and the rc.13 pin were not re-checked. (topic: agents/onnx-runtime-rust-ort)
  - Resolved 2026-10-21: the crates.io API (S-msk5qtcf) was fetched again on 2026-10-21 and lists `2.0.0-rc.15` (2026-10-19) as newest after `rc.14` (2026-10-12), with MSRV 1.92 for both; `agents/onnx-runtime-rust-ort` now states the version list and MSRVs from it and says its docs and manifest facts were read at `rc.13`. [DOC S-msk5qtcf]
- S-msk5qtcf (crates.io API for ort) now shows newest_version 2.0.0-rc.15 (the cache had rc.14), while the article says rc.13 (published 2026-07-28) is the highest version and pins =2.0.0-rc.13. The page could not be fetched in this run (empty response), so the highest-version claim at line 19, the MSRV list at line 22 and the pin advice at line 95 are not re-verified. The next run should read the full API output and decide whether to pin rc.13 or move to a newer rc. (topic: agents/onnx-runtime-rust-ort)
  - Resolved 2026-10-21: see the entry above; the highest version, the MSRV list and the pin advice of the article now name `rc.15` as the highest and `rc.13` as the version whose docs and manifest were read, and the rc.14 and rc.15 docs stay a gap. [DOC S-msk5qtcf]

## logs/otel-collector-otlp-pipeline
- **Number of official Collector distributions: five or six.** The opentelemetry.io page on building a custom Collector (S-iylg5wv4, site vers 0.162.0) says the Collector "has five official distributions", while the distributions repository README at v0.162.0 (S-vnjcetlc) lists six: `otelcol`, `otelcol-contrib`, `otelcol-k8s`, `otelcol-otlp`, `otelcol-prometheus` and `otelcol-ebpf-profiler`. The kb states the repository list as the current one in `logs/otel-collector-otlp-pipeline`; the page's count is probably stale. (topic: logs/otel-collector-otlp-pipeline)
  - Resolved 2026-10-21: the repository that builds the distributions lists six (S-vnjcetlc, identical at v0.163.1 and, read 2026-10-21, at main), while the ocb page still says "five official distributions" in prose (S-iylg5wv4; the live site page read 2026-10-21 still says so); the repository README is the list itself, so the page's count is the stale statement and the article states the six. [DOC S-vnjcetlc, S-iylg5wv4]

## logs/otel-python-sdk
- **Unit of the OTLP exporter timeout variables.** The OpenTelemetry specification v1.61.0 (S-rcmsm2rb, S-56w77twg) types `OTEL_EXPORTER_OTLP_TIMEOUT` and its per-signal forms as a Timeout, an integer number of milliseconds (`12000` is 12 seconds); the Python `_resolve_timeout` at v1.45.1 (S-4kd2fl7f) parses the same variables as a float and hands it to the HTTP client as seconds, with 10 as the default. By the code a Python process given `10000` waits 10000 seconds; the code is the authority for Python until a release changes it. Both read 2026-10-18. [DOC S-rcmsm2rb, S-56w77twg vs CODE S-4kd2fl7f, unresolved] (topic: logs/otel-python-sdk)
  - Narrowed 2026-10-21: re-read `_resolve_timeout` at main of opentelemetry-python: it still parses `OTEL_EXPORTER_OTLP_TIMEOUT` and the per-signal forms as a float number of seconds with default 10 and warns "using default of 10 seconds", while the specification types them in milliseconds, so the disagreement stands; the code is the authority for Python's behaviour. An upstream release that changes the parsing, or running the exporter with `10000` against a silent endpoint, would settle whether it waits 10000 seconds. [DOC S-rcmsm2rb, S-56w77twg vs CODE S-4kd2fl7f]

## privacy/spacy-pipeline-pinning
- spaCy `download --url` at release-v3.8.16: the CLI table describes the option as "Download from a mirror repository at the given url" (S-pmc3phpi), but `download_model` in `spacy/cli/download.py` (S-kmhasvx6) raises `ValueError` when the joined URL does not start with `about.__download_url__` (the GitHub releases prefix), and replaces a `--url` value without a trailing slash by that prefix, so a mirror on another host is not reachable through it in the code read. Both read 2026-10-11 at the same tag; installing a mirrored wheel with a direct `pip install <url>` is unaffected. (topic: privacy/spacy-pipeline-pinning)
  - Narrowed 2026-10-21: re-read `download_model` at master of spaCy: it still builds the URL from the given `--url` and raises `ValueError` unless the result starts with the GitHub releases prefix (`about.__download_url__`), so the code still does not reach a mirror on another host while the CLI table calls it a mirror option (S-pmc3phpi); the code is the authority for behaviour. A spaCy release that accepts other hosts or a docs fix would settle it. [DOC S-pmc3phpi vs CODE S-kmhasvx6]

## ad/fsmo-roles
- Group needed for the schema master: the transfer-or-seize page (S-hnfdk22k, read 2026-10-12) names Enterprise Administrators for transferring the schema master and domain naming master, while the forest-recovery seize page (S-uyoeu33z, read 2026-10-12) lists Schema Admins for `seize schema master` and Enterprise Admins for the domain naming master. The two pages cover transfer and seizure in different scenarios; the kb states both and does not choose. (topic: ad/fsmo-roles)
  - Reviewed 2026-10-21, not a source disagreement: re-read both pages. The transfer page (S-hnfdk22k) states a requirement for transferring the schema master and domain naming master (Enterprise Administrators group); the forest recovery page (S-uyoeu33z) states one for seizing them (Schema Admins for `seize schema master`, Enterprise Admins for the domain naming master). They cover different operations and neither says the other's group is wrong or insufficient for its own; the kb states both.

## windows/dhcp-failover
- Minimum Windows Server version for failover partners: the overview page (S-45mj3bt5, read 2026-10-12) says both partners must run at least Windows Server 2016, while the management page (S-xl2d4tuq, read 2026-10-12) lists at least Windows Server 2012 as the prerequisite. The kb states both and does not choose. (topic: windows/dhcp-failover)
  - Still open 2026-10-21: re-read. The overview (S-45mj3bt5) still says "DHCP failover partners must both be running at least Windows Server 2016"; the manage page (S-xl2d4tuq) still lists "At least Windows Server 2012" as a prerequisite, and the replicate and migrate-existing pages also list at least Windows Server 2012. The overview is the only page that says 2016. Creating a failover relationship between a Windows Server 2012 R2 and a newer lab server would settle it.
- Which server is the standby: the management page (S-xl2d4tuq) runs `Add-DhcpServerv4Failover -ComputerName dhcp1 ... -ServerRole Standby` and says dhcp2 (the partner) is the standby; the cmdlet reference (S-x2hxgchj) defines `-ServerRole` as the role of the local server and its example 2 with `-ServerRole Standby` makes the local server the standby. The kb follows the cmdlet reference for the parameter and states the page's reading as the page's. Not run, so not settled. (topic: windows/dhcp-failover)
  - Still open 2026-10-21: re-read. The manage page (S-xl2d4tuq) still runs `Add-DhcpServerv4Failover -ComputerName "dhcp1.contoso.com" ... -ServerRole Standby` and says dhcp2.contoso.com is the standby. The cmdlet reference (S-x2hxgchj) example 2 (`-ComputerName dhcpserver.contoso.com ... -ServerRole Standby`) says the DHCP server service on dhcpserver.contoso.com, the computer named by -ComputerName, is the standby, and its example 4 without -ServerRole says the partner is the standby. Creating a hot standby relationship with -ServerRole Standby in a lab and reading Get-DhcpServerv4Failover on both servers would settle it.

## sqlserver/availability-group-seeding
- Threading of automatic seeding: the concept page (S-7u5iv73w, read 2026-10-12) calls it a single-threaded process that can handle up to five databases, while the how-to page (S-bvigwggq, read 2026-10-12) says SQL Server uses one thread per LUN on the primary and on the secondary. The kb states both and does not choose. (topic: sqlserver/availability-group-seeding)
  - Still open 2026-10-21: re-read. S-7u5iv73w still says automatic seeding "is a single-threaded process that can handle up to five databases"; S-bvigwggq still says SQL Server "uses a fixed number of threads" with one thread per LUN on the primary and on the secondary. The pages may describe the seeding scheduler and the I/O threads, but neither says so. Seeding many databases in a lab availability group and reading the threads and `sys.dm_hadr_physical_seeding_stats` would settle it.

## auth/postgres-column-encryption
- CipherSweet FIPS fast blind index: the security page (S-qt7piebc, read 2026-10-13) says fast blind indexes under FIPSCrypto calculate a hash using HMAC-SHA384 and truncate it, while the blind-index internals page (S-rqc6efd7, read 2026-10-13) lists the FIPSCrypto fast index as PBKDF2-SHA384 with 1 iteration (three arguments: plaintext, key, bit length). Both pages name PBKDF2-SHA384 for the slow index (the internals page adds a default of 50,000 iterations). The kb states both and does not choose. (topic: auth/postgres-column-encryption)
  - Narrowed 2026-10-21: the CipherSweet source at master (`src/Backend/FIPSCrypto.php`, read 2026-10-21) documents `blindIndexFast` as "PBKDF2-SHA384 with only 1 iteration" and calls `hash_pbkdf2('sha384', ...)`, which matches the internals page (S-rqc6efd7) and not the security page's "HMAC-SHA384 ... truncated" wording (S-qt7piebc, unchanged in the census of 2026-10-21); the security page is the one out of line. The article states both until the docs are corrected. [CODE paragonie/ciphersweet master; DOC S-rqc6efd7, S-qt7piebc]

## agents/agent-sandboxes
- Default access of the Docker Sandboxes shared agent skills store: the security model page (S-qfhwf42v, read 2026-10-15) says supported agents mount the host-side store read-only by default, and the architecture page (S-4kmihytd) says the same, while the security page's own isolation diagram says supported agents mount it read-write unless the user opts out, and the isolation layers page (S-5hrbuirw) says it is shared for agents that have not opted out. The kb states both and does not choose; `--skills` or `skills.defaultMode` sets the mode at creation either way. (topic: agents/agent-sandboxes)
  - Still open 2026-10-21: the security model page (S-qfhwf42v) was read again on 2026-10-21 and still says read-only by default in its summary and read-write unless the user opts out in its isolation overview. Inspecting the mount mode of the skills store in a default sandbox with `sbx` would settle it.
- Value spelling in a Windows Sandbox configuration: the CLI page (S-5hntws7z, read 2026-10-15) passes `<Networking>Disabled</Networking>` to `wsb start --config`, while the .wsb configuration page (S-hlmmxoye) lists `Enable`, `Disable` and `Default` as the values. Not run here; the kb's example follows the configuration page. (topic: agents/agent-sandboxes)
  - Still open 2026-10-21: the Windows Sandbox CLI page (S-5hntws7z) still passes `<Networking>Disabled</Networking>` and the configuration page (S-hlmmxoye) still lists `Enable`, `Disable` and `Default`, read 2026-10-21. Running `wsb start --config` with `Disabled` on a Windows 11 host would settle it.

## arch/podman-rootless-config
- Storage drivers usable by a rootless user: the project's `rootless.md` (S-rif3pi6x, read 2026-10-15 at v6.1.4) says the only supported storage drivers are overlay (optionally through `fuse-overlayfs`) and VFS, while the `containers-storage.conf(5)` page (S-b2bqmd6c, container-libs commit 7eac5c25c6b6) says the valid rootless drivers are btrfs, overlay and vfs. The kb states both and does not choose; the two pages are in different repositories and the storage page is the more specific one for the option's values. (topic: arch/podman-rootless-config)
  - Narrowed 2026-10-21: re-read both pages at main: `rootless.md` (S-rif3pi6x) still says "Only supported storage drivers are overlay (optionally using `fuse-overlayfs`) and VFS" while `containers-storage.conf(5)` (S-b2bqmd6c) still says "Valid rootless drivers are btrfs, overlay, and vfs"; the storage page is the reference for the option's values, and `rootless.md` is a summary of limits in another repository. Running `podman --storage-driver btrfs info` as a rootless user on a btrfs path would settle it.

## arch/puppet-language-resources-types
- `ordering` setting: the Puppet Core 8 resources page (S-3nlx3lke, read 2026-10-15) says the default manifest order can be customised "with the ordering setting" and points to the configuration page, but the configuration reference (S-cttzm2qq) and `lib/puppet/defaults.rb` (S-se4kjnw2), both at commit e227c27, define no such setting (the word occurs only in the deferred-function text). The kb states both and does not choose. (topic: arch/puppet-language-resources-types)
  - Narrowed 2026-10-21: `lib/puppet/defaults.rb` at main still defines no `ordering` setting (the word appears only in the deferred-function text), while the Puppet Core 8 resources page (S-3nlx3lke, published 2026-10-12, confirmed in the census of 2026-10-21) still points to "the ordering setting"; the code is the authority for what a user can set. A docs correction, or `puppet config print ordering` on a Puppet 8 agent, would settle it. [DOC S-3nlx3lke vs CODE S-se4kjnw2]

## arch/puppet-windows-nodes
- Running a Windows service as a specific user: the type reference's `windows` service provider text (S-ef4b5npw, read 2026-10-15) says running services as a specific user is not supported, while the same provider's supported features include `manages_logon_credentials` (the provider can specify the logon credentials of a service). The kb states both and does not choose. (topic: arch/puppet-windows-nodes)
  - Narrowed 2026-10-21: the provider's own file at main holds both statements: its `desc` still says services cannot be run "as a specific user", and the same file declares `has_feature ... :manages_logon_credentials` and implements `logonaccount` and `logonpassword` handling (`logonaccount_insync?`), so the code supports setting a service's logon account and the `desc` sentence reads as the older one. Setting `logonaccount` on a `service` resource on a Windows lab node would settle it. [DOC S-ef4b5npw; CODE puppetlabs/puppet main, `provider/service/windows.rb`]

## arch/chef-windows-nodes
- Chef Infra Client install location on Windows: the Chef for Windows page (S-3x3s2jec, read 2026-10-15) says in one place that after installation the client is located at `C:\opscode` and in the next line at `C:\hab`, and its PATH section names `C:\opscode\chef\bin`; the 19.3.15 release notes (S-qdnvehti) say Habitat-related paths follow `SYSTEMDRIVE` and Omnibus-related paths stay at `C:\opscode`. The kb states both and does not choose; which distribution uses which root is open. (topic: arch/chef-windows-nodes)
  - Still open 2026-10-21: the Chef for Windows page (S-3x3s2jec) and the 19.3.15 release notes (S-qdnvehti) were re-read in the census of 2026-10-21 and are unchanged; the page still names both `C:\opscode` and `C:\hab` and no page says which installer uses which root. Installing the Omnibus MSI and the Habitat package on a lab Windows node and reading the install paths would settle it.

## security/gentoo-use-flags-profiles-keywords
- Default `USE_ORDER`: the Gentoo wiki page for the variable (S-w323r75a, read 2026-10-15) gives `env:pkg:conf:defaults:pkginternal:repo:env.d`, while the `make.conf(5)` manual page (S-5lblcwaf) and `cnf/make.globals` (S-uhuj7vad), both at Portage commit `27abd048bffa`, give `env:pkg:conf:defaults:pkginternal:features:repo:env.d`, with `features` for flags implied by `FEATURES` (currently `test`). The kb states both and prefers the implementation, since the wiki page lists the same table without a `features` row; the wiki page is likely older. (topic: security/gentoo-use-flags-profiles-keywords)
  - Resolved 2026-10-21: `make.conf(5)` and `cnf/make.globals` at the same Portage commit (S-5lblcwaf, S-uhuj7vad) are the implementation and give `USE_ORDER` with `features`; the wiki page (S-w323r75a, unchanged in the census of 2026-10-21) lists the same table without the `features` row and is the older statement; the article states both and prefers the implementation. [CODE S-5lblcwaf, S-uhuj7vad; COMMUNITY S-w323r75a]

## security/fish-syntax-bash-differences
- Which commands expand a failed glob to nothing: the language chapter at tag 4.9.3 (S-irnsu4to, read 2026-10-15) names `set`, `path`, `count`, `for` and variable overrides, while the "fish for Bash users" page of the same tag (S-2l7kac72) names `for`, `set`, `count` and variable overrides, without `path`. The kb states both and prefers the language chapter, the fuller list of the two. (topic: security/fish-syntax-bash-differences)
  - Reviewed 2026-10-21, not a source disagreement: both pages are at tag 4.9.3 and differ only in how many commands they list (the language chapter adds `path`, so the Bash-users list is the shorter of the two and neither page says the other's list is wrong); the article states both and prefers the fuller language chapter. [DOC S-irnsu4to, S-2l7kac72]
- Braces as grouping: the "fish for Bash users" page (S-2l7kac72) shows `{ ... }` becoming `begin ... end` and lists no brace form, while the 4.1.0 release notes (S-eg4rjgcz) say compound commands can be written with braces. The kb states both and prefers the release notes, which are the later statement. (topic: security/fish-syntax-bash-differences)
  - Reviewed 2026-10-21, not a source disagreement: the Bash-users page (S-2l7kac72) lists only `begin ... end` and the 4.1.0 release notes (S-eg4rjgcz) add brace-delimited compound commands; the later statement adds a form the older page does not list, and the article states both. [DOC S-2l7kac72, S-eg4rjgcz]

## windows/cmd-exe-syntax-quoting-redirection
- Size of an individual environment variable under cmd: the command-line string limitation article (S-e4zz24dq, read 2026-10-15) gives 8191 characters for the string `cmd` processes and for each inherited variable, while the `cmd` page (S-yna7gijv, read 2026-10-15) says the maximum individual variable is 8,192 bytes and all variables of a process 65,536 characters. The kb states both and does not choose; the first is an old KB article that names Windows 7 and Server 2008 R2 / 2012 R2, the second is the current reference page, and whether the two figures are the same limit is open. (topic: windows/cmd-exe-syntax-quoting-redirection)
  - Still open 2026-10-21: re-read both pages. The command-line string limitation article (S-e4zz24dq) still gives 8191 characters for the command line and for individual inherited environment variables, and still applies to Windows Server 2012 R2, Windows Server 2008 R2 SP1 and Windows 7 SP1; the cmd page (S-yna7gijv) still says the maximum individual environment variable size is 8,192 bytes and the total for a process 65,536 characters. No page says whether 8191 characters and 8,192 bytes are the same limit or whether the older article still holds on current Windows. Setting variables of 8191, 8192 and 8193 characters in cmd on a current Windows lab machine and reading them back with `set` would settle it.

## agents/typescript-tsconfig-and-compiler-options

- **Defaults of `strict`, `module`, `target`, `moduleResolution`, `types` and `rootDir`.** The live TSConfig reference (S-lq5mn2bc, read 2026-10-15) and the pinned website data (S-34pqpd75, commit 6556b08) print the 5.x defaults: `module` is CommonJS if `target` is ES5 and ES6/ES2015 otherwise, `target` is ES5, `moduleResolution` is `Classic` unless `module` selects another, and the page gives no default for `strict` itself (it is listed as "Recommended"), with the strict-family options "true if strict; false otherwise". The TypeScript 6.0 announcement (S-sp2a6svk) says `strict` is true, `module` esnext, `target` the current-year ES version, `rootDir` the config directory and `types` `[]`; the 7.0 announcement (S-eq3gt72a) adopts them, and the 7.0.2 source (S-sipjyeoi) declares `strict` true and `moduleResolution` bundler by default. The kb states the 6.0 and 7.0 defaults as the current ones and records the reference page as stale; the website's reference pages describe 5.x. (topic: agents/typescript-tsconfig-and-compiler-options)
  - Resolved 2026-10-21: the 6.0 and 7.0 announcements (S-sp2a6svk, S-eq3gt72a, both read in full in the census of 2026-10-21) state the new defaults, which the kb gives as current; the reference pages (S-lq5mn2bc, S-34pqpd75) describe 5.x and are recorded as stale. [DOC S-sp2a6svk, S-eq3gt72a]

## agents/typescript-native-compiler

- **Watch mode of the native compiler.** The typescript-go README at tag `typescript/v7.0.2` (S-mtnr5emw) marks watch mode "prototype" ("no incremental rechecking. Not optimized"), while the 7.0 announcement (S-eq3gt72a, 2026-07-08) says 7.0 ships a "completely rebuilt" `--watch` on a Parcel-watcher foundation. Both read 2026-10-15; the README text appears not to have been updated for the release, and no measurement of 7.0.2's watch mode was made. (topic: agents/typescript-native-compiler)
  - Resolved 2026-10-21: the README of the repository at `main` (read 2026-10-21) now lists watch mode as done, so the README at tag `typescript/v7.0.2` (S-mtnr5emw) is the stale side and the 7.0 announcement (S-eq3gt72a) stands; the article records both and says the README is behind. Watch mode itself was not measured. [DOC S-eq3gt72a, S-mtnr5emw]

## gitlab/git-trailers-and-hooks

- **Whether a trailer configured with only `trailer.<alias>.cmd` is added without a `--trailer` argument.** The trailer configuration page at `v2.55.0` (S-wjfrtzpf, read 2026-10-19) says `.cmd` "will be called once to automatically add a trailer"; `parse_trailers_from_config` in `trailer.c` at the same tag (S-kbwvfzcv) adds a configured trailer by itself only when the alias has a `.command`, and a run of git 2.50.1 printed a message unchanged for a `.cmd`-only alias and added the trailer for `.command` or for `--trailer <alias>`. The kb states the code's behaviour; the page's sentence is read as describing the call for a named alias. Not settled: the pages and code of later releases, and git 2.55.0 itself, were not run. (topic: gitlab/git-trailers-and-hooks)
  - Still open 2026-10-21: read `parse_trailers_from_config` in `trailer.c` at master (ahead of v2.55.0 and the v2.56.0 release candidates): it still adds a configured trailer by itself only when the alias has a `.command`, while the trailer config page at master still says `.cmd` is "called once to automatically add a trailer". Running git 2.55.0 or a v2.56 build with a `.cmd`-only alias (as on 2.50.1) would settle whether a later release changed the behaviour. [DOC S-wjfrtzpf vs CODE S-kbwvfzcv]

## agents/headless-agent-runtimes

- kb/public/agents/headless-agent-runtimes.md lines 41 and 45 say the cloud-environment GitHub proxy's push protection lets `git push` work only against the session's current working branch. The cloud-environments page (S-gu5aqnrl, 'GitHub proxy', read 2026-10-21) says the proxy only rejects branch deletions and pushes of anything other than a branch (such as a tag), and states it does not limit which branches a push can update; it mentions no working-branch restriction. Unresolved: lines 41 and 45 contradict the page; line 45's conclusion about reaching `main` also rests on that claim. (topic: agents/headless-agent-runtimes)
  - Resolved 2026-10-21: `agents/headless-agent-runtimes` now says, from the cloud-environments page (S-gu5aqnrl, read in the census of 2026-10-21), that the proxy rejects branch deletions and non-branch pushes and does not limit which branches a push can update, and its conclusion about reaching `main` rests on that. [DOC S-gu5aqnrl]

## privacy/gliner-models

- gliner-models.csv row urchade/gliner_multi_pii-v1 says base_model 'not stated in card', but the card (S856) says it was fine-tuned from urchade/gliner_multi-v2.1. The csv cell is not in a cited fact; left unedited pending a decision on whether to fill it in. (topic: privacy/gliner-models)
  - Resolved 2026-10-21: the card (S856) says "trained by fine-tuning `urchade/gliner_multi-v2.1`", so the `base_model` cell of the `urchade/gliner_multi_pii-v1` row in `gliner-models.csv` now reads `urchade/gliner_multi-v2.1`. [DOC S856]

## auth/audit-log-apis

- audit-log-apis.md line 83 lists `serviceFilters` (a collection) for the auditLogQuery body, but the Create auditLogQuery page (S-wsetw6to, read 2026-10-21) lists `serviceFilter` as a String; confirm against the resource page S-ojti56n4 and fix the property name/type. (topic: auth/audit-log-apis)
  - Resolved 2026-10-21: the resource page (S-ojti56n4, updated 2026-10-10) types the property `serviceFilters` (a string collection) and `audit-log-apis.md` line 83 already states `serviceFilters` as a collection; the Create page (S-wsetw6to, updated 2026-09-18) still shows the older `serviceFilter` string in its request body, so the resource-type page is the newer statement. [DOC S-ojti56n4, S-wsetw6to]

## python/testcontainers-postgres-pytest

- testcontainers-python v4.15.0 configuration.md is internally inconsistent on precedence: 'Configuration Locations' says environment variables are read before ~/.testcontainers.properties, but the 'Docker Host Detection' list reads the tc.host property (step 1) before TC_HOST / DOCKER_HOST (steps 2-3). The kb line 70 says env vars win over the properties file; this holds for the general rule but not for tc.host in the detection order. (topic: python/testcontainers-postgres-pytest)
  - Narrowed 2026-10-21: the code at v4.15.0 explains both orders without settling the doc's wording: `get_docker_host()` in `core/docker_client.py` (S-pgxen5ty) returns the `tc.host` property, else `DOCKER_HOST`, else the Docker context, never `TC_HOST`, which matches the detection list's `tc.host` first; `TC_HOST` (`tc_host_override`) is read only by the `host` property; and the generic setting reader in `core/config.py` (S-x7ub2eqf) checks the environment variable before the property, as 'Configuration Locations' says (S-ld5hflyc). The pinned configuration page itself still reads inconsistently, and the code's `get_docker_host()` does not read `TC_HOST`, which the page's list names as step 2 (the article states the page's list); a doc edit would settle it.
