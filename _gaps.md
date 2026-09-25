# Gaps (UNK items: what was tried, where)

Merged from `_parts/<agent>/gaps.md`.

## agents-a2a-cache

- **A2A v1.0.0 exact release date and "Agentic AI Foundation" naming.** The fetched spec page (S2120) surfaced a reference to an "A2A joins the Agentic AI Foundation" post dated 2026-08-27, which may signal a further governance rename beyond the original Linux Foundation "Agent2Agent Protocol Project" (S2123). Not independently confirmed with a direct fetch of that post (1 attempt: relied on the spec page's own summary, did not separately fetch the referenced post). [UNK]
- **Whether any Anthropic product speaks A2A natively.** Checked: A2A GitHub repo listing (no Anthropic in supporting orgs list, S2121), WebSearch for "Claude Agent SDK A2A support" (found only community wrapper projects and one Anthropic+Google Cloud joint webinar demonstrating Claude *inside* an A2A system via Vertex AI, not first-party support, S2129). Did not find an Anthropic docs page stating support or non-support either way. 2 search/fetch attempts; stopping per budget. [UNK]
- **A2A SDK language list beyond Python.** The claim that Go/JavaScript/Java/.NET/Rust SDKs exist under `a2aproject` came from one WebFetch summary of the main A2A repo page (S2121) and was not verified by listing each sub-repository individually. [DER, low confidence — treat as needing reconfirmation before citing precisely]
- **`anthropics/courses` repository contents.** Found only via WebSearch snippet, not independently WebFetched in this session (1 attempt, then treated as sufficient given the more pressing budget spent on caching detail). Row is present in `anthropic-materials.csv` marked accordingly. [COMMUNITY-tier evidence for an official repo]
- **Exact cache-read price multiplier for the newest Anthropic model tier.** The fetched prompt-caching page (S2130) states 0.025x-0.05x for "Opus 5.5, Fable 5.1, Mythos 5.1" versus 0.1x for "other models," which conflicts in precision with the separately fetched pricing page's worked example implying 0.05x for Opus 5.5 specifically (S2131). Recorded as a conflict below rather than resolved. [DOC, conflicting]
- **JSON Schema (non-proto) artifact for A2A.** Searched the pinned commit's tree for a `.json` schema alongside `a2a.proto` and found none at `specification/`; the spec itself says JSON artifacts are generated, non-normative build outputs, so only the proto was saved as the pinned artifact. Not a gap in effort, but noting no separate JSON schema file exists to pin. [DOC S2120]

## agents-authz

- **Closed this pass:** PIM-for-Groups activation-to-effect latency now has numbers — see `answers.md` QG26 deepening (S2052): 2-10 min SCIM provisioning for the first 5 activations/10s per app, else the 40-min sync cycle; the active-assignment write itself remains "within seconds" (S1282, reused). Three distinct latency regimes are now named rather than one partial figure.
- **Closed this pass:** HashiCorp Vault dynamic secrets / database secrets engine — TTL (1h default / 24h max), supported engines, lease-revocation mechanics fetched. See `answers.md` QG27 deepening (S2054) and `agents/api-tokens.csv`.
- **Closed this pass:** GitLab CI native secrets manager (`ci/secrets/`) and its `id_tokens`-based auth to Vault/Key Vault/GCP/AWS — fetched (S2055, S2056). See `answers.md` QG27/28 deepening and `agents/secret-storage-options.csv`.
- **Closed this pass:** Claude Code `apiKeyHelper`'s hot-reload behaviour (no restart needed on settings change) — fetched (S2057). See `answers.md` QG28 deepening.
- **Closed this pass:** App roles vs group claims for a service principal specifically — Microsoft's own documented gap ("Entra ID doesn't add the roles claim" when an app role is assigned to a group containing a service principal) fetched (S2053). See `answers.md` QG25 deepening.
- **Closed this pass (partially):** OWASP-specific guidance on agent/NHI identity separation and least privilege — the OWASP NHI Top 10 list (S2058) was fetched and mapped to this part's own findings (NHI7, NHI10). The OWASP "Agentic AI – Threats and Mitigations" PDF remains unfetchable by WebFetch (content is inside a PDF, not rendered); still [UNK] for that specific document's threat-ID text.
- **Still open: Microsoft Entra Agent ID — PIM support for agent identities specifically.** Neither the agent-identities overview (S2040), the PIM-for-Groups page (S2052, this pass), nor the announcement (S2051) states whether an agent identity can be an eligible PIM member/owner of a role-assignable group the way a human or service principal can. Tried across two passes: S2040, S2051, S2052 (no mention in any); WebSearch budget for this session was exhausted before a further targeted search could be attempted this pass. [UNK]
- **Still open: S2051 (Microsoft Entra Agent ID announcement) was read only as a WebSearch synthesis in the prior pass, not independently WebFetched.** Not re-attempted this pass (WebSearch budget exhausted; WebFetch of the same URL was not separately retried since S2040 already carries the load-bearing mechanics). Treated as DOC per the prior pass's reasoning; flagged for a direct fetch in a future pass. [DOC, flagged]
- **Narrowed, not closed: HashiCorp Vault's own numeric SLA or default TTL for a *SQL Server* (MSSQL) dynamic role specifically** — the database-secrets-engine page (S2054) gives the *engine's* default (1h/24h TTL) but no MSSQL-specific example or caveat distinct from the generic default; not pursued further this pass (the generic default answers the design-relevance question adequately per the fact already recorded in `answers.md`). [DOC S2054 for the generic default; UNK for an MSSQL-specific worked example]

## agents-copilot

- **Exact wording and trigger condition of Copilot Studio's "instructions limit exceeded" / topic
  count exceeded errors** was not confirmed beyond the numeric limits themselves (8,000 characters
  for agent instructions, 1,000 topics per agent in Dataverse environments, 500 knowledge sources,
  100 skills — all S1960). No error-string text was found on S1960 or S1980 within budget. Tried:
  requirements-quotas (S1960), faq-billing-licensing (S1980, search-summary only). This belongs
  properly to Topic 2 (`agents-errors`); flagged here because QG17's quota inventory surfaces the
  numbers but not the error text. [UNK]
- **Teams AI library current status** (`microsoft.github.io/teams-ai`) returned HTTP 404 on fetch;
  a second candidate path was not tried within budget. Tried: 1 WebFetch attempt. The Microsoft 365
  Agents SDK docs (S1968) do not mention Teams AI library by name, and GitHub search for
  `microsoft/teams-ai` was not run as a fallback. QG18/QG19's Teams AI library coverage rests on
  general knowledge, not a fetched source, and is marked `[UNK]` in the topic file. [UNK]
- **Azure Bot Service SDK overview page** (`learn.microsoft.com/en-us/azure/bot-service/bot-service-overview-introduction`)
  returned HTTP 404 on fetch. The Bot Framework SDK retirement statement is instead sourced from the
  GitHub README (S1976) via WebSearch summary rather than a direct WebFetch of the README file
  itself; the exact retirement date (Dec 31, 2025) was not independently cross-checked against a
  second Microsoft Learn page. [UNK, low confidence in exact day-of-month]
- **Copilot Credits pricing rates (currency amounts) and the "billing rates" table** referenced by
  S1961 (`requirements-messages-management#copilot-credits-billing-rates`) were not fetched; only
  the mechanism (pay-as-you-go, prepurchase, prepaid pack) is confirmed, not the actual credit
  price. Tried: 0 direct fetch attempts (out of the ~40-page budget spent on breadth over this one
  page). [UNK]
- **A2A protocol support inside Copilot Studio specifically** (as opposed to Foundry Agent Service,
  which explicitly states A2A v1.0 GA and v0.3 preview per S1970) was not confirmed either way for
  Copilot Studio connected agents. Topic 9 (`agents-a2a-cache`) owns A2A depth; flagged here only
  because QG17's "connected agents" line needed it. [UNK]
- **Solution export file format details (topic YAML inside a solution .zip, component schema)**
  were not fetched beyond the code-editor YAML sample (S1963) and the ALM overview (S1967); no page
  was fetched that documents the exact solution .zip layout for a Copilot Studio agent (that lives
  under Power Platform ALM docs, `/power-platform/alm/`, not fetched). [UNK]

## agents-errors

Closed in the deepening pass (2026-09-25, second session): the Copilot Studio error-codes page is now exhaustively
parsed into the CSV; stdout pollution in stdio MCP servers, MCP timeout defaults, headless permission denials,
compaction effects, and `stop_reason` values are now researched with direct source fetches; the CLAUDE.md
"~40KB warning" claim is resolved (refuted, replaced with the confirmed 200-line/4MiB figures); Chroma's Context Rot
study closes part of the QG7 "published measurements" request. See `answers.md` and the CSVs for the detail.

Remaining gaps:

- **OpenAI Assistants/Responses API's exact `instructions` field character limit and its exact save/validation error
  text** is still unconfirmed from an official numeric page. Tried in this pass: direct WebFetch of
  `developers.openai.com/api/docs/guides/function-calling` and `.../structured-outputs` (the current successor pages
  to `platform.openai.com/docs/guides/*`) — neither states a character/token ceiling for `instructions`. Community
  forum posts (S1844, S1845) remain the only figures (8,000 for the ChatGPT custom-GPT UI; up to 256,000 cited for a
  different field, message content). [UNK]
- **The commonly cited "128 tools" limit for OpenAI function calling** was not found on either fetched OpenAI page in
  this pass; the pages instead give a soft, non-enforced recommendation ("fewer than 20 functions... at the start of
  a turn"). Whether "128" is a real, separately documented ceiling (for example on the Assistants API specifically,
  which was not directly re-fetched) is unresolved. [UNK]
- **Gemini's official `systemInstruction` length limit and its exact documented error schema** remain unconfirmed
  from an official page: `ai.google.dev/gemini-api/docs/function-calling` was fetched directly in this pass and
  documents neither a `systemInstruction` character/token ceiling nor an enumerated list of unsupported
  OpenAPI-schema keywords for function declarations. The community-reported ~85-90K-token observed boundary (S1846)
  remains the best available number. [UNK]
- **Gemini function-declaration count limit and function-name pattern/length restriction** were not found on the
  fetched function-calling guide (style guidance only: "underscores or camelCase"). [UNK]
- **A single canonical Claude API reference page enumerating all `stop_reason` values** (including `pause_turn`,
  `refusal`, `model_context_window_exceeded`) was not independently re-fetched in this pass; the three deepening-pass
  additions are tagged `DER` rather than `DOC` for that reason, derived from the tool-use documentation set rather
  than quoted from one authoritative stop-reason table. A follow-up should fetch a page specifically titled around
  "handling stop reasons" (linked from `platform.claude.com/docs/en/agents-and-tools/tool-use/overview` as
  `handling-stop-reasons`) and requote each value's exact definition as `DOC`.
- **The full "supported JSON Schema subset" reference pages** linked from both Anthropic's strict-tool-use page
  (`build-with-claude/structured-outputs#json-schema-limitations`) and OpenAI's structured-outputs guide were not
  independently fetched in this pass; both parent pages state restrictions exist without enumerating every excluded
  keyword on the page actually fetched. [UNK, partial — the headline restrictions that were confirmed are recorded]
- **Copilot Studio / M365 Copilot MCP server support limitations and Copilot Studio's own MCP-tool JSON-Schema
  restrictions** (as distinct from generative-orchestration limits) were not researched in this pass; out of the
  budget after the error-codes and instruction-limit lines of inquiry. [UNK]
- **No official OpenAI, Google, or Microsoft first-party publication of an instruction-count or context-length
  adherence degradation study** (analogous to IFScale or Chroma's Context Rot) was found; both measurement studies
  surfaced in this part remain third-party. [UNK]

## agents-eval

- **Whether Inspect (`inspect_ai`) has a documented, native MCP stdio target.** Tried: the GitHub
  repository README (S1886), the docs home inspect.aisi.org.uk (S1887), and a WebSearch for
  "inspect_ai MCP tool server". Found only an "MCP Registry" reference in unrelated GitHub navigation
  chrome, no MCP-target class documented in the fetched pages. [UNK, recorded in
  `agents/agent-evaluation.md`]
- **No vendor (Anthropic/OpenAI/UK AISI) tool or guidance names ConfigMgr, AdminService or a similarly
  shaped internal MCP server specifically.** Every mapping in `agents/mcp-stress-testing.md` from a QG11 stress dimension to
  a concrete tool is therefore `DER`, not `DOC`. This is expected (such a server is not a public product) and is not
  treated as a failed source attempt.
- **No published number for how many fetched pages state a licence for promptfoo's or garak's *documentation
  site* content separately from the code repository.** garak's own GitHub README states GPL-3.0 for the
  code; a secondary claim ("Apache 2.0 License" for site content) came from a WebSearch synthesis of
  garak.ai and was not independently re-fetched from garak.ai itself within the 3-attempt/40-page budget for
  this sub-question. Recorded as a soft confirmation gap, not blocking, since the code licence (GPL-3.0,
  S1891) is what would govern any local re-use.
- **DeepEval's exact latest released version/date** was not visible in the fetched GitHub README excerpt
  (only commit count). Not pursued further (budget); the licence (Apache-2.0) and MCP metric names were
  the load-bearing facts for QG9 and were confirmed. [UNK]
- **No vendor page was found publishing a numeric contamination-control cadence** (e.g. "rotate golden-set
  questions every N days") beyond Anthropic's qualitative "run continuously" / "nearly 100% pass rate"
  guidance (S1896); a specific regression cadence number is therefore left to the adopting
  task, per QG12's instruction that this baseline is a draft, not a decision.

## agents-extra

- QG23: could not retrieve `github.com/modelcontextprotocol/registry`'s `server.json` schema file itself (repo
  overview fetched instead; the raw schema file path was not resolved in the budget for this part) or a pinned
  commit/sha256 artifact of it. The repo's preview/API-freeze status and field names (name, version, packages,
  remotes) are recorded from the overview page (S2012) only; exact schema types and required/optional markers are
  not confirmed. 2 fetch attempts made (repo root + one guessed raw path that 404'd); stopped short of the 3-attempt
  ceiling to conserve budget for the other three topics.
- QG23: "how clients react to a changed tool description (cache, permissions)" is answered only from the MCP spec's
  `listChanged` mechanics (S2135 (reused id, already recorded elsewhere in this kb)) and Claude Code's own cache-invalidation notes already
  in `claude/otel-monitoring.md`/other parts' `agent-caching.md` (topic 9); no vendor doc found stating whether a
  changed tool description silently re-triggers a user permission prompt in Claude Code specifically. Recorded as
  `UNK` in `mcp-server-lifecycle.md`.
- QG21: could not fetch the full PDF text of arXiv 2506.08837 with attribution-quality precision beyond WebFetch's
  own extraction; pattern names and one-line trade-offs are taken from that extraction (S2005) and are not verified
  against the original section headings word-for-word.
- QG24: per-engineer cost attribution specific to a *stdio MCP server tool* (rather than whole-session cost) is not
  published anywhere found; Claude Code's MCP-attribution feature in `/usage` attributes by MCP *server*, not by
  individual MCP *tool* within a server. Recorded as a gap in `agent-cost-governance.md`.

## agents-mcp

- **No published per-call latency number for Claude subagent spawn overhead** (only qualitative "fresh context, higher latency" from S1923). Tried: code.claude.com/docs/en/sub-agents (S1923, qualitative only), WebSearch for "claude code subagent spawn latency milliseconds" style queries returned no vendor number. [UNK]
- **No vendor-published success-rate/eval-pass-rate threshold for "replace this subagent with a tool."** Anthropic's evals guidance (S1935) describes *how* to measure tool-use quality (task success, tool-call count, token count, error rate) but does not publish a numeric threshold at which a workflow step should convert from agent-driven to hard-coded. Tried: S1920, S1935, S1936; no vendor number found. Recorded as `DER` in answers.md instead. [UNK]
- **No official Anthropic or Microsoft page stating an exact percentage figure for cost escalation from a runaway/recursive subagent** beyond the "another 10x or more" figure from a secondary (COMMUNITY) source (S1930). Anthropic's own multi-agent post (S1921) describes the failure mode (excessive subagent spawning) but not a cost multiplier for it. Tried: S1921 (qualitative), S1930 (COMMUNITY, has the number). [COMMUNITY only, tagged as such]
- **MCP "tasks" capability (`execution.taskSupport`) details** were found only via a WebSearch summary (S1929-adjacent search, not independently re-fetched from the modelcontextprotocol.io tasks page) — not fetched directly in this session; the fetched tools page (S1928) is the 2025-06-18 revision and does not itself describe `taskSupport`. Tried: one WebSearch, one WebFetch of the tools page only (budget stopped after the outputSchema/annotations facts were confirmed there). Recorded as `UNK` for the exact task-support default value beyond the search snippet. [UNK]

## agents-ner

- No throughput number (requests/sec, documents/minute, or p95 latency) for a shared PII-detection
  endpoint was found for any of Presidio, Azure AI Language, Amazon Comprehend or Google Sensitive Data
  Protection. Presidio's own Kubernetes/App Service samples give only qualitative scaling advice
  ("set resource limits and autoscaling"). 3 search attempts made across the four vendors; none surfaced
  a published number. [UNK — `agents/shared-ner-service.md` QG30]
- Exact Azure AI Language PII pricing (dollar amounts per 1,000 text records at each volume tier, and for
  the disconnected-container annual licence) was not retrieved — the pricing calculator's per-tier rates
  are not rendered in the fetched page content and require the interactive calculator or a sales contact.
  [UNK — `agents/shared-ner-service.md` QG30]
- Google Sensitive Data Protection's per-GB rates ($1.00/$1.50/$0.05 for discovery/storage/streaming) come
  from a fetched third-party-style summary of the pricing page, not a direct table read from
  `cloud.google.com/sensitive-data-protection/pricing`; treat as approximate pending a direct re-check.
  [UNK/needs confirmation — `agents/shared-ner-service.md` QG30]
- No on-premises or disconnected container deployment was found for either Amazon Comprehend or Google
  Sensitive Data Protection (both presented as cloud-hosted APIs only in every source checked); this is
  recorded as an absence, not a confirmed "does not exist," since only public vendor docs were searched
  (3 attempts each). [UNK — `agents/shared-ner-service.md` QG30]
- No GDPR controller/processor analysis specific to an internal shared NER/PII-detection endpoint (as
  opposed to pseudonymisation and identifiability generally, already covered in
  `privacy/gdpr-pseudonymisation.md`) was found in any EDPB or Microsoft/AWS/Google compliance page
  fetched this session. [UNK — `_answers.md` QG31]
- No published numeric trigger (consumer count, detection-gap percentage, or maintenance-hour figure) for
  when to centralize a shared NER service was found from any vendor or community source. [UNK —
  `_answers.md` QG32]
- Presidio's own caller-authentication story for a shared analyzer/anonymizer deployment (e.g. built-in
  API-key support) was not found in the fetched docker/k8s/app-service samples; only Azure's container
  documents an API-key requirement. [UNK — `agents/shared-ner-service.md` QG31]

## agents-overuse

- **Google's "Agents Companion" whitepaper and Cloud Architecture Center agentic-architecture page were
  not independently fetched.** `docs.cloud.google.com/architecture/choose-agentic-ai-architecture-
  components` returned HTTP 403 to WebFetch, and the Kaggle-hosted whitepaper page was only summarized via
  WebSearch, not fetched directly. Tried: one WebFetch attempt on the Cloud Architecture Center page (403),
  one WebSearch covering both pages. Facts from these are tagged `DOC` (they describe Google's own
  published position) but are recorded here as **not independently re-verified against the primary text**
  in this session. [UNK — verification gap, not a content gap]
- **Two Microsoft Community Hub blog posts' bodies could not be retrieved.** "Three tiers of Agentic AI -
  and when to use none of them" and "Stop Letting Agents Run the Workflow" both returned only their page
  title to WebFetch (no body content), and the session's WebSearch budget was exhausted (200/200) before a
  second search could pull a fuller summary. Tried: one WebFetch per URL (title-only response), the prior
  WebSearch that first surfaced the "three tiers" title. No numeric or quoted content from either post is
  used beyond the title itself. [UNK]
- **No official vendor benchmark comparing agent vs. deterministic-tool cost, latency and error rate on
  the same task exists in what was fetched.** The two numeric figures used (cost-per-token-volume,
  per-model latency spread) are both COMMUNITY (Stevens Online blog, a DEV Community post), not
  vendor-published. Tried: one WebSearch for "'AI agent' cost latency error rate compared to deterministic
  script published numbers postmortem" (returned only community sources); the session's WebSearch budget
  was then exhausted for further attempts. [COMMUNITY only, tagged as such — see `agent-overuse-patterns.md`]
- **No specific published "post-mortem" of an agent used where a deterministic tool would have sufficed**
  was found from an official source. Tried: the OpenAI/Microsoft/Google/Anthropic pages already fetched
  for QG37 (none names a specific named incident); one WebSearch for cost/latency/error numbers (returned
  general cost-modelling posts, not an incident writeup). [UNK]
- **Thoughtworks Technology Radar's exact ring placement (Adopt/Trial/Assess/Hold) for a broader
  "agent overuse" or "coding-agent antipattern" entry beyond "Agent Skills"** was not confirmed by direct
  fetch of the Radar PDF's relevant pages; the facts used come from a WebSearch summary of Volume 34, and
  a second WebSearch to fetch the PDF's own text for the specific ring assignment could not be run because
  the session's WebSearch budget (200 calls, shared across this session's agents) was exhausted after the
  first four queries in this part. Tried: one WebSearch specifically for Radar coding-agent entries
  (blocked by budget exhaustion before it ran). [UNK]
- **Session-wide WebSearch budget (200 calls) was exhausted partway through this part's research**, which
  is why several facts above rely on the initial WebSearch summaries rather than a WebFetch of primary
  text, and why no further searches (e.g. for additional Thoughtworks Radar entries, more published
  cost/latency numbers, or a second Google source) could be run. This is a session-level constraint, not a
  per-topic 3-attempt stop. [UNK — recorded as the governing constraint on this part's remaining gaps]

## agents-wiki

- **DeepWiki's automatic refresh cadence** (cron vs. webhook vs. purely on-demand) remains undocumented after a second attempt this session against `docs.devin.ai/work-with-devin/deepwiki`. The only confirmed trigger is the explicit, human-initiated one: commit `.devin/wiki.json` and ask Devin/DeepWiki to regenerate. Not pursued further under the 3-failed-attempt budget rule. [UNK]
- **`CognitionAI/deepwiki` GitHub repository's licence and actual contents** remain unverified (only its existence surfaced via search in the first pass; not re-attempted this session). [UNK]
- **Mintlify's code-diff "agent API"** for auto-updating documentation from code changes (as opposed to the always-on `llms.txt` deploy-time export, which is confirmed `DOC`) is recorded only as a `COMMUNITY`-sourced search-engine synopsis; the specific how-to page describing its trigger, auth, and review-gate mechanics was not independently fetched in either pass. [UNK: exact mechanism, not the existence of the feature]
- **`lychee` (link checker)**: the URL used this session (`lychee.cc`) did not resolve (`ENOTFOUND`); the tool's correct current site/repo and licence were not independently confirmed. Its role as a deterministic link-check guardrail is stated in the deepening-pass brief but not vendor-verified here. [UNK]
- **`doc-detective`**: not fetched at all this session (outside the URL list given); remains an unresearched community tool candidate for doc-drift detection. [UNK]
- **GitHub Copilot coding agent's own scheduled/issue-triggered documentation-update workflow** (as distinct from Copilot Spaces, a context store, and from `.github/copilot-instructions.md`/`AGENTS.md` support, both now confirmed `DOC`) was not found as a named, distinct product feature in the one official page fetched (`best-practices-for-using-copilot-to-work-on-tasks`). GitHub's own equivalent scheduled-drift pattern instead appears to live in the separate `gh-aw` project (now confirmed `DOC`), not in Copilot coding agent itself. [UNK, narrowed from the first pass's broader "no docs-update feature found"]

## arch

- **No Microsoft-documented way for Linux (Python gssapi/pyspnego/requests-gssapi, adutil, mssql-conf) to retrieve a gMSA's `msDS-ManagedPassword` and turn it into a keytab.** Tried: `adutil keytab createauto` (requires explicit `--password`, built for conventional AD accounts per S1606), Microsoft Learn search for "gMSA Linux", MIT Kerberos docs. Only AWS's `credentials-fetcher` (S1607/S1608, COMMUNITY, Apache-2.0, AWS open source) claims to fetch gMSA credentials over LDAP for Linux. Verification: could be checked by running `credentials-fetcher` against a lab AD gMSA and a lab Linux host, watching whether it produces a usable keytab/ticket — out of scope for this research pass.
- **No stated Windows-Server-version floor specific to Kubernetes gMSA** beyond the general Windows-container gMSA fix history (2019 fixes for hostname/race-condition issues); kubernetes.io doesn't restate a minimum OS build. Tried: kubernetes.io gmsa page (S1600) — silent on this; would need a targeted Microsoft Learn "Windows container OS compatibility" cross-reference. [UNK, recorded in arch/k8s-gmsa-windows.md]
- **No GA date for Azure Arc-enabled Kubernetes workload identity federation** — page (S1609) still labelled preview at retrieval (updated 2025-11-18). No separate GA announcement found via search. Verification: not checkable without a live Azure subscription; recheck by re-reading S1609 periodically for a status change.
- **`Authentication=ActiveDirectoryDefault` behavior for msodbcsql18 against on-prem/Arc-enabled SQL Server specifically** was not confirmed by a fetched page (search summary only, centered on Azure SQL DB/MI). Tried: WebSearch only, did not fetch the full ODBC Entra ID page content beyond the search summary. Could be closed with one more WebFetch of S1610 if this specific mode becomes load-bearing.


- Whether Power BI "field parameters" or a report-bound SQL/CSV table (as opposed to Analysis
  Services metadata translations) is a realistic, officially documented mechanism to localize
  report label text was not confirmed against official Microsoft Learn docs within the fetch
  budget. `arch/texts-catalogue-formats.md` [UNK]
- No official PowerShell or Power BI Fluent (FTL) runtime was found; absence was inferred from
  search results, not from an exhaustive official-docs negative confirmation. `arch/texts-catalogue-formats.md` [UNK]
- GitLab's semantic-versioning requirement for Catalog releases: found stated in prose docs plus a
  still-open backend enforcement issue (#427286) — unclear from official docs alone whether
  non-semver tags are currently rejected at release time or only informally required. `arch/gitlab-ci-components.md` [UNK]

## auth

### on-prem / Windows / ConfigMgr / SQL

Closed this pass (see kerberos.md, ntlm-deprecation.md, ad-jit-membership.md, configmgr-rbac-auth.md):
- RC4-in-Kerberos deprecation dates — found and dated (S1215, S1216, S1217).
- AD PAM TTL vs Kerberos ticket lifetime — found (S1219): TTL propagates directly into TGT lifetime.
- ConfigMgr RBAC mechanics (QA2) — read 3 official pages (S1218 + 2 more); no provider-cache statement exists, confirmed UNK, LAB line recorded.

Still open:
- ConfigMgr-specific provider/role cache behaviour on top of Kerberos PAC group SIDs (QA2): confirmed UNK after 3 official-source attempts (role-based administration fundamentals, configure role-based administration, plan for the SMS Provider, `SMS_Admin` WMI class reference).
  Verification: on an isolated ConfigMgr lab site, add a test admin to a role-granting AD group, call AdminService with an existing ticket, then again after `klist purge`+re-logon → proves whether the SMS Provider adds delay beyond the Kerberos PAC refresh.
- Mid-ticket TTL group removal (QA10 edge case): does an already-issued, TTL-capped TGT survive an admin's early removal of the membership, or is it invalidated immediately? Not stated in S1219.
  Verification: in an isolated PAM-enabled forest, add then early-remove a TTL group membership and observe whether the already-issued TGT is honoured until its original (TTL-capped) expiry.
- `python-ldap` on Windows: does it negotiate SASL sign/seal against a signing-enforced DC over plain `ldap://`? API is documented (S1220) but its Windows sign/seal behaviour is not stated by the docs.
  Verification: attempt `ldap3` vs `python-ldap` vs pywin32/ADSI (`ADS_USE_SIGNING|ADS_USE_SEALING`) GSSAPI binds over plain `ldap://` against a Server 2025 DC with LDAP signing enforced → settles QA15 fully.
- DPoP (RFC 9449) GA status for general Entra ID access tokens (beyond MSAL PoP and Windows Token Protection/PRT binding specifically): not confirmed as GA vs preview from an official source.
- RFC 8693 Token Exchange support in Entra ID: no official Microsoft statement found either confirming or denying; only community sources describe it as unsupported (OBO/client-credentials offered instead). Tried: Microsoft Learn identity-platform search, RFC 8693 + Entra web search.
- SMB 3.1.1 cipher negotiation specifics (AES-128-GCM vs AES-256-GCM) beyond the signing/encryption defaults: not researched.
- MIM PAM product support status in 2026: not researched.

### Entra / Graph / MSAL / GitLab

- Per-app-registration numeric limit on federated identity credentials (QA4): three-search budget not
  spent hunting the exact limits page; tried general searches, found the mutable-subjects feature page
  but not the limits page directly. Verification: not applicable (this is a docs lookup, not a lab check) —
  needs one more targeted fetch of an Entra app-registration/FIC "limits" or "known issues" page.
- Headless/jump-host-specific WAM caveats beyond "Windows 10+/Server 2019+ supported" (QA5): not found
  in the two WAM pages fetched. Verification: run `msal[broker]` interactive acquisition on a Windows Server
  2025 jump host with no interactive console session (e.g. RDP disconnected) -> proves whether WAM's
  window-handle requirement fails outside an active session.
- Whether Token Protection covers a bespoke MSAL Python public client's Graph calls, not just
  EXO/SPO desktop apps (QA6): deployment guide scopes examples to Microsoft first-party apps only.
  Verification: enable a Token Protection Conditional Access policy scoped to Microsoft Graph in a test tenant,
  target a test MSAL Python public client, and check whether the refresh token issued is
  proof-of-possession bound and whether Graph rejects it without a matching device.
- Whether nested-group membership counts toward an app-role assignment made to a group (QA7,
  `roles` claim path specifically, as opposed to the `groups`-assigned-to-application claim which is
  documented as excluding nesting): not stated in the two group-claims pages fetched.
  Verification: nest a child group inside a parent group, assign the app role to the parent only,
  sign in as a user who is only a member of the child group, inspect the `roles` claim.
- Call-specific throttling and caching guidance for `checkMemberGroups`/`getMemberGroups`, and whether
  they honour CAE (QA18): the two API reference pages carry no throttling/CAE note specific to these
  calls. Verification: none — needs a documentation-only follow-up fetch of the Graph throttling guidance page
  cross-referenced against these two methods.
- `delegation-kcd-obo.md` now researched (round 2). Remaining gap: the MCP Enterprise-Managed
  Authorization / ID-JAG "stable June 2026" date and "Entra native ID-JAG not GA" claim come from a
  vendor/community blog (S1300), not modelcontextprotocol.io itself or a Microsoft Learn "what's new"
  page. Verification: none (docs lookup) — needs a direct fetch of
  `modelcontextprotocol.io/extensions/auth/enterprise-managed-authorization` and an Entra Identity
  Platform "what's new" page to upgrade this from COMMUNITY to DOC.
- Whether MSAL Python's `client_assertion` callable parameter (supplying a pre-built JWT) is the
  supported way to back a confidential-client credential with a non-exportable CNG/TPM key (i.e. a
  custom signer calls CNG/TPM and MSAL just transports the resulting assertion): documented
  `client_credential` dict/PFX options all need MSAL to read the private key directly; the
  `client_assertion` escape hatch's suitability for this wasn't independently confirmed against a
  CNG/TPM example in this pass. Verification: build a minimal custom assertion signer using
  `ncrypt`/`cryptography` against a non-exportable CNG-backed cert, pass its output via MSAL's
  `client_assertion`, and confirm Entra accepts it -> proves the escape hatch works end-to-end.
- Token Protection: no source names MSAL Python or a CLI/console app by name as in- or out-of-scope;
  the "native client" framing is the closest documented anchor. Verification: in a test tenant, apply a Token
  Protection Conditional Access policy scoped to Microsoft Graph + "Mobile apps and desktop clients",
  authenticate a test MSAL Python public client (WAM broker) against a test resource, and check
  whether the token is proof-of-possession bound / whether Graph enforces it -> proves whether Token
  Protection reaches a Python CLI in practice.

### keys, propagation, revocation, audit, threats

- DPAPI-NG `SID=` descriptor: no Microsoft page found stating (a) the KDS root key propagation delay before a newly created descriptor's key is retrievable domain-wide, (b) the minimum DC functional level/version required, (c) behaviour when the user leaves the group without a new logon, (d) recovery path if the group is deleted. Tried: `learn.microsoft.com/windows/win32/seccng/protection-descriptors`, `cng-dpapi-constants`, general web search. 3 attempts, stopped per budget rule.
  Verification: On a lab DC + lab client, create a DPAPI-NG blob with `SID=<test group>`, remove the encrypting user from the group without logging off, then attempt `NCryptUnprotectSecret` from a cached logon session vs. a fresh logon -> proves whether group removal is enforced at unprotect time or only at next logon.
- PIM for Groups activation latency into tokens and `checkMemberGroups`, and whether it reaches on-prem AD groups (QA9): not researched by this agent (overlaps role-source-options.md territory); left `[UNK]` in propagation-latency.csv.
  Verification: Activate a PIM-for-Groups membership in a lab tenant, immediately request a token and call `checkMemberGroups`, time the delay.
- ConfigMgr AdminService's exact trigger for honouring an AD security-role group change (new logon vs SMS Provider cache) (QA2): left `[UNK]`, owned by `configmgr-rbac-auth.md`.
  Verification: in a disposable lab collection, add a test admin account to a ConfigMgr-RBAC-holding AD group, call AdminService immediately, then after a new Kerberos ticket, then after an SMS Provider service restart -> isolates the cache boundary.
- Cloud Sync's exact documented sync-interval ceiling (this agent found only secondary/community figures of ~2 minutes / 10-20 minutes; no primary Learn citation was fetched due to a wrong guessed file path in MicrosoftDocs/entra-docs for the Cloud Sync FAQ page). Tried: direct raw-GitHub path guess (failed), GitHub tree search for "cloud-sync"+"faq" (no match), general web search (secondary sources only). 3 attempts, stopped per budget rule.
- Kerberoasting detection detail (event 4769 ticket-encryption-type field values 0x12/0x17) is stated only from secondary sources in this agent's research; no primary Microsoft Learn/Support page was fetched and cited for it (see threats.csv note). Left without a DOC-tagged source rather than mis-cited.

### Added at merge

- Verification: add a test account to an AD group, then `klist tgt` renew (not purge) and `whoami /groups` + an AdminService call → proves whether a TGT renewal refreshes PAC group SIDs (bounds AD group-change latency: renewal interval vs. new logon).
- Verification: from a Windows 11 24H2 client, call the AdminService by FQDN and by short name / IP, with `klist` before and after → proves Kerberos-only behaviour since 2509 and what error a non-FQDN call returns.
- Verification: put a lab engineer account in Protected Users; run the `client` flows (AdminService, SQL, Graph via WAM) for >4 h → proves the 4-hour non-renewable TGT effect and any NTLM-dependent leg.

## dsc

- **Windows-host execution not done.** Q20 behaviour (Service/FirewallRuleList native what-if; elevation check in what-if) is from code and manifests (S105, S114, S138, S139). Tried: macOS arm64 binaries (S116/S117), which do not include Windows resources. Needs a Windows 11 lab run. [UNK]
- **What-if for group resources and adapters in a config.** The "error (pretest, no what-if)" classification for Microsoft.DSC/Group, Assertion, Include and the PowerShell adapters is derived from their manifest flags plus `invoke_set` (S105). Not run. [UNK]
- **MCP `what_if` on 3.3.0 ignored at runtime.** The conclusion is from source (no field, no `deny_unknown_fields`; S108) and binary strings (S114). An MCP stdio call was not captured in this session. [DER only]
- **Official directives documentation.** No Learn or repo doc page for `directives` was found. Tried: MicrosoftDocs/PowerShell-Docs-DSC `dsc/docs-conceptual/dsc-3.0/reference/schemas/config/document.md` (S145), repo `docs/reference/schemas/config/*.md` on release/v3.3, and a grep of all repo docs for "directives". Only code and tests document it.
- **Learn docs lag behind 3.2/3.3.** The Learn CLI pages (dsc-3.0 moniker) are dated 2025; there are no pages for `function`, `server`/`mcp`, directives, `secret()` or settings/policy. Facts come from code at the pinned commits.
- **Trace leakage at `debug` level for adapters.** Tested only with `Microsoft.DSC.Debug/Echo`. Adapter paths (PowerShell) were not tested.
- **Generated schemas and help text** (`schemas/generated-*`, `cli/help-*.txt`, `functions-3.3.0.csv`) are outputs of running the release binaries (sources S116/S117 = the tarballs). They cannot be re-downloaded byte-for-byte from a URL. `fetch.py --verify` should verify the tarball hash only.

## ident

- Q9 explicit equality "Entra deviceId == AD objectGUID": searched entra-docs (`objectguid` + device id), graph docs-contrib v1.0, memdocs, windowsserverdocs, SupportArticles (entra, mem). Found mapping statements only (S549, S550). Status UNK for explicit equality and for the AD FS-only path.
- objectGUID vs deviceId string/byte-order comparison rules: not found in win32 ADSchema a-objectguid.md, search-filter-syntax.md, entra-docs. UNK.
- Q10 Autopilot `id` vs ZTDId: searched memdocs (all), entra-docs, graph docs-contrib v1.0 for `ztdid`; no statement linking them. UNK.
- Throttling limit for `windowsAutopilotDeviceIdentity`: not listed in any `includes/throttling-intune-*.md` in docs-contrib (grep of all includes). UNK.
- Intune RBAC needed for delegated Graph calls on managedDevices / Autopilot identities: API pages S518-S523 state only Graph permissions. Not searched further in memdocs (budget). UNK.
- `dsregcmd /status` Tenant details fields: documented only through sample output on S544; not extracted.
- `msDS-LogonTimeSyncInterval` default value when unset: not on schema page S563. Not searched further (budget). UNK.
- managedDevice beta List/Delete API pages don't exist under `intune-devices-manageddevice-*` in beta (only Get); beta permissions for list/delete not captured.

## infra

- **gMSA scheduled task registration syntax** (LogonType, `-UserId DOMAIN\name$`): not found in windowsserverdocs gMSA pages (S400-S403), win32 TaskSchd `principal-logontype.md` (S404, which only lists LocalSystem/LocalService/NetworkService for SERVICE_ACCOUNT), or `New-ScheduledTaskPrincipal` (S405). There was also a repo-wide grep for gmsa+scheduled task across all clones. 3 attempts; stopped. [UNK]
- **GitLab Runner as gMSA, official statement**: runner docs install/windows.md, advanced-configuration.md, shells, faq, security (S406-S408), a grep of all runner `docs/` for "gmsa"/"managed service", and the issue API. Only COMMUNITY issue text was found (S414); issue 30963 is open. Issue notes need a login (HTTP 401), so they weren't read. [UNK for official support]
- **`safe_directory_checkout` documentation**: the option is in the runner source (S410), but a grep of runner `docs/` at 49138a48 finds no mention. [UNK in docs]
- **mssql/server digest pinning policy**: containers/deploy.md, quickstart-install-docker.md and environment-variables.md (S473, S474, S477) have no `@sha256` or digest guidance. MCR tag list saved (S478). [UNK]
- **S478 artifact hash is not stable**: `tags/list` is a live endpoint, so `fetch.py --verify` will report a mismatch once new tags appear.
- **Ownership chaining vs DENY for the audit table**: not read (sql-docs ownership-chains page not checked). [UNK]
- **Free-tier author self-approval**: approvals `_index.md` (S441) says Free approvals are optional. Whether a Free author can approve their own MR is not stated on the pages read. [UNK]

## later

- Power BI docs source repo: `MicrosoftDocs/powerbi-docs` and `MicrosoftDocs/data-integration` are not public (clone: "Repository not found"); learn pages point to private `powerbi-docs-pr`. Used throttled learn.microsoft.com HTML instead; no pinned raw URL possible for S900-S910 (only ms.date recorded).
- GPO backup on-disk layout (folder contents such as Backup.xml / gpreport.xml): not in the GroupPolicy cmdlet reference (S921); grep of MicrosoftDocs_windowsserverdocs, SupportArticles-docs, win32 clones for "bkupInfo.xml" / "gpreport.xml" found nothing. [UNK]
- DSC v3 GroupPolicyTemplate adapter: which released version first ships it is left to dsc/ (only the main-branch manifest was checked, S924). [UNK]
- `ansible.windows.win_dsc` check-mode support: the docs page as fetched shows no attributes table; not confirmed. [UNK]
- powerbi/configmgr-views.md depends on mecm/sql-views-compliance.md (other agent); that file did not exist at time of writing.

## mcp

- Claude Code form-mode elicitation over 2026-07-28 (MRTR) connections: searched code.claude.com/docs/en/mcp.md, hooks.md, env-vars.md, changelog.md (grep elicit/2026-07-28/InputRequired). Only URL-mode-on-2026 entry (2.1.281) found. UNK.
- Claude Code use of MCP tool annotations (readOnlyHint/destructiveHint) for permission decisions: searched mcp.md, permissions.md, changelog.md. Only "annotations display in /mcp" (1.0.44). UNK.
- Claude Code support for the Tasks extension (io.modelcontextprotocol/tasks): searched mcp.md, changelog.md, MCP client-matrix.mdx (no Tasks column). UNK.
- OWASP LLM Top 10 2026 item ids/titles: tried genai.owasp.org/llm-top-10/ (2025 list only), /resource/owasp-genai-llm-top-10-2026/ (no list in HTML), 2026-09-01 announcement (no list in HTML). Stopped after 3 attempts; list is in a PDF not fetched.
- OWASP Agentic 2026 resource page HTML does not carry ASI titles; titles taken from the OWASP GenAI announcement blog (S762). Licence of genai.owasp.org content not verified on page.
- OWASP MCP Top 10 index.md fetched from `main` (not sha-pinned); commit sha not recorded.
- privacy.claude.com / support.claude.com commercial-terms pages not fetched (time budget); retention facts come from code.claude.com data-usage/ZDR and platform.claude.com API retention pages.
- MCP spec repo is a shallow clone: git history for 2026-07-28 release date not available; release date inferred only from the version string and SDK v2.0.0 release date (2026-07-28).

## mecm1

- Minimum baseline evaluation interval (Q19): searched memdocs compliance/*, about-client-settings.md, develop/compliance/*, schedule token classes; SupportArticles-docs support/mem/configmgr (no compliance-settings troubleshooting articles). Not documented.
- CI script output size limit (Q19): searched memdocs (compliance, apps, client settings, develop) for "output", "size", "maximum"; SupportArticles-docs. Not documented.
- Full column lists of compliance SQL views: SQL views docs (compliance-settings-views, status-alert-views, sql-server-views) give descriptions and join columns only. Column lists only available from sample queries and WMI classes.
- SQL view behind SMS_DCMDeploymentCompliantDetailsPerAsset: not in develop/reference/compliance or sqlviews docs.
- Enumeration of CI setting data types (String, Integer, ... ) and a 32-bit/64-bit host option for script settings: not in create-custom-configuration-items doc or create-global-conditions doc; only "Floating point supports three decimals" is stated.
- Execution account of a CI script without "logged on user credentials": not stated.
- Scope of Script Execution Timeout beyond compliance settings (app detection, global conditions): not stated.
- CCM log format: no formal spec; `type` values and time-bias semantics not defined (only examples in memdocs osd doc and SupportArticles state-messaging article).
- Collect client logs programmatic retrieval (WMI class / AdminService route for Support_*.zip): not documented.
- learn.microsoft.com URLs were derived from repo paths (intune/configmgr/...) and not fetched; historic URL form was learn.microsoft.com/mem/configmgr/... . Raw pinned URLs in sources.csv are authoritative.

## mecm2

- CMPivot `CcmLog()`, `WinEvent()` and per-entity columns. Tried: grep of the memdocs clone (4b5429df) for CcmLog/WinEvent (only examples found), cmpivot*.md, the tenant-attach cmpivot pages, and the cmpivot-samples include. Not documented. Only columns used in examples are recorded in mecm/cmpivot-entities.csv.
- InitiateClientOperation Type values (policy, HW inventory, app eval, SU eval). Tried: the SDK reference (develop/reference/protect/*clientoperation*), grep of memdocs, SupportArticles-docs and windows-powershell-docs for "client operation <n>", and the Learn Invoke-CMClientAction page (names only). Only 135/145 from log samples.
- InitiateClientOperationEx. Tried: grep of all clones (no hits) and a web search (only the older InitiateClientOperation pages and community posts). Not in the current SDK docs.
- Invoke-CMClientAction ActionType numeric values. The Learn page lists names only. The sccm-docs-powershell repo is private.
- AdminService per-route support through CMG and delegated tokens. Tried: set-up.md, usage.md, faq.yml, azure-services-wizard.md, whats-new 2207, and the Microsoft TokenSample.ps1. None lists routes. Fetching the other configmgr-hub samples was declined this session and not retried.
- AdminService v1.0 Run Script action. Tried: the adminservice docs folder, a grep of all memdocs for v1.0 routes, and Learn Invoke-CMScript. Only a community sample was found (search result, not fetched).
- Run Scripts maximum script size. Tried: create-deploy-scripts.md, learn-script-security.md, and a grep for script size/length. Not documented.
- RBAC bit positions for Notify Resource, Run Script and Run CMPivot. Tried: SMS_ARoleOperation, SMS_RbacSecuredObject, and the security views doc. Not listed.
- Full built-in role × permission matrix. The docs point to the RBA Viewer tool (a live site) and give no static table.
- Response schemas of AdminService.RunCMPivot / CMPivotResult. Not documented, and there is no Swagger document (S305).
- Learn URL invoke-cmclientnotification returned 404. It is an alias of Invoke-CMClientAction (S334).

## ops

- **Q11: Defender aadDeviceId for hybrid join.** No official statement found. Tried: learn defender-endpoint/api/machine, get-machines and get-machine-by-id; defender-xdr/advanced-hunting-deviceinfo-table; defender-endpoint/machines-view-overview; exposed-apis-odata-samples; microsoft-graph-docs-contrib security-deviceevidence; the microsoft-365-docs clone (it has no defender-endpoint content because that moved to the private defender-docs repo); 2 WebSearch queries. Stopped after 3+ attempts.
- **DeviceInfo JoinType values.** The advanced-hunting-deviceinfo-table page does not list them.
- **Remediations script size limit and timeout.** Not in deploy-remediations.md or management-extension-windows.md (memdocs). The 200 KB and 30-minute figures cover platform scripts only (run-powershell-scripts-windows.md).
- **Full `-area` list for MDMDiagnosticsTool.** learn windows/client-management/diagnose-mdm-failures-in-windows-10 shows only DeviceEnrollment, DeviceProvisioning and Autopilot. memdocs and SupportArticles add TPM. No complete list found. The Windows client-management repo was not cloned.
- **Co-management workload flags (CoManagementFlags).** A grep of the memdocs and SupportArticles clones found nothing.
- **Channel `Microsoft-Windows-DeviceManagement-Enterprise-Diagnostics-Provider/Operational`.** Not found in the memdocs, SupportArticles, entra or windowsserverdocs clones.
- **Exact channel string for ModernDeployment-Diagnostics-Provider/Autopilot.** Only the Event Viewer path is documented (autopilot/troubleshooting-faq.yml). The channel name in this kb is derived (DER).
- **ConfigMgr-specific Windows event channels.** None are documented in the clones. ConfigMgr writes log files instead (see mecm/log-files.csv).
- **Query length limit for multi-device query.** Not stated.
- **ECS base fields (@timestamp, message).** base.yml was not fetched.
- **Licence of the Defender learn pages.** The MicrosoftDocs/defender-docs repo is private, so the licence could not be checked. That content is summarised only.

## priorart

### mcp-microsoft-endpoint-mgmt
- Tried: `microsoft/mcp` GitHub repository + its `servers/` directory listing (found: only
  Azure.Mcp.Server, Fabric.Mcp.Server, Template.Mcp.Server, no ConfigMgr/Intune/Graph-device/Entra
  server). Community MCP servers for these Microsoft endpoint-management surfaces were not searched
  beyond this — stopped after confirming the official catalog has no match, within session budget.
  Recorded as `status: partial`, not `unknown`, because the official-catalog absence is itself a
  confirmed fact.

### device-identity-correlation
- Tried: GLPI, Snipe-IT, NetBox, Fleet repository metadata (GitHub API `repos/<org>/<repo>` only).
  ServiceNow CMDB's Identification and Reconciliation Engine (IRE) public docs — the brief's named
  reference for merge-key/precedence/duplicate-handling facts — were not fetched: ServiceNow's docs
  site is not in this agent's official-source allowlist and was not fetched via HTTP this session.
  Wazuh was fetched for repository metadata only (language C++, licence unresolved by GitHub API);
  its device-identity-correlation mechanism specifically (agent/manager enrollment, not asset CMDB)
  was not documented in depth — stopped after repo-metadata level, 1 attempt, given Wazuh is a weaker
  fit for "device identity correlation" than the CMDB-style tools already covered.

### drift-detection
- Tried: Puppet, Chef InSpec, Microsoft365DSC repository metadata + brief README passages (Puppet
  README, general project description text). Ansible check-mode facts were stated from general
  project knowledge of `ansible-core` docs structure but not independently re-fetched from
  docs.ansible.com this session (docs.ansible.com is on the allowed list but was not called — time
  budget); Azure Machine Configuration, Intune tenant configuration management, and osquery/Fleet
  policies (all named in the brief for this mechanism) were not fetched at all this session — no
  attempts made, explicit scope cut to stay near the ~40-fetch budget.

### log-collection-normalization
- Tried: OpenTelemetry Collector and Fluent Bit repository metadata only (no docs-site fetch for
  either project's receiver/parser plugin catalog, so "no built-in CMTrace parser" is stated from
  repository-description-level evidence, not an exhaustive plugin-list check). NXLog CE: no public
  GitHub repository exists to fetch from; nxlog.co was not fetched (not on this agent's official-
  source allowlist as configured in this session). No CMTrace-specific open-source parser project
  (e.g. a standalone CMTrace log parser library) was searched for independently.

### secret-vault-encryption
- Tried: sops, age, Vault, cryptography, git-crypt repository metadata + one README/doc page each.
  Vault's licence is recorded as BUSL-1.1 from general knowledge of Vault's 2023 licence change
  (GitHub API itself only reports "NOASSERTION," it does not identify BUSL-1.1) — this fact carries a
  weaker evidentiary basis than the other DOC-tagged facts in that file and should be reconfirmed
  against Vault's own LICENSE file if precision matters.

### tiered-approval-ops
- Tried: Rundeck, StackStorm, Teleport, Ansible AWX repository metadata only. None of the four
  projects' README/docs content (ACL policy syntax, RBAC role definitions, Access Request workflow
  steps, AWX approval-node configuration) was fetched — repository-description-level facts only, by
  design given the ~40-fetch budget for this agent.

## privacy

- Next Presidio release date / version: not announced. Tried GitHub releases API (S801), PyPI JSON (S802), CHANGELOG `[unreleased]` (S800).
- spaCy `en_core_web_lg` training-data source licences (`LICENSES_SOURCES`): not read. The fetch of https://huggingface.co/spacy/en_core_web_lg/raw/557bf75.../LICENSES_SOURCES was declined during the session. spacy.io/models/en (S852) renders details client-side, so the static HTML has no licence text. The model licence itself (MIT) is confirmed by S850 and S851.
- nvidia/gliner-PII full label list (55+): not in the model card (S860) or the HF API (S859). The dataset card and NVIDIA licence text were not fetched (the nvidia.com licence is not on an allowed host).
- EDPB Guidelines 01/2025 final (post-consultation) version: not found. Tried the consultation page (S872), the news item (S873), the topic page (S874), and two WebSearch queries restricted to edpb.europa.eu. Only the "version for public consultation" exists.
- CJEU C-413/23 P full judgment text: not fetched. Used press release 107/25 (S875) only.
- `surrogate_ahds` operator behaviour over REST: not checked.

## reuse

- Exact commit SHAs for the 5 LICENSE fetches (hashicorp/vault, pyca/cryptography, inspec/inspec,
  fleetdm/fleet, ansible/awx) were not pinned: `raw.githubusercontent.com/.../HEAD/...` was used and
  the GitHub API `commits/HEAD` calls to resolve a sha were rate-limited (403) after ~30 total fetches
  across all kb agents sharing the throttle. URLs are recorded as `HEAD` with `retrieved_utc` as the
  pin instead. Tried: `api.github.com/repos/<org>/<repo>/commits/HEAD` for all five, all 403'd once.
- LLM Guard's `Vault` class was assessed from the prior-art agent's summary of its own docs (S1006),
  not by reading `llm_guard`'s source directly this session (budget); the "port the class shape" logic
  verdict should be re-verified against the actual `vault.py` source before any code is written.
- Teleport's "Access Requests" approval-workflow mechanics and AWX's workflow-approval-node mechanics
  were not fetched this session (inherited gap from prior-art); the `no` verdict here rests on licence
  (AGPL-3.0) and deployment-model (always-on service) grounds, which do not depend on those mechanics,
  so this gap does not change the verdict but is noted for completeness.
- A reference age+sops Python wrapper's `store.py` was checked by grep for `ttl`/`TTL`/`expir` only (no match), not read
  in full; a full read would be needed before relying on "no TTL support" as a hard fact rather than a
  grep-based inference.

## security

### coordinator (crosswalk, coverage, precedence, candidates)

- **Windows 11 25H2 and Server 2025 v2602 Microsoft baseline packages.**
  - The Download Center page (id 55319) is a script-driven file picker that answers `curl`/WebFetch with a bot page. The Chrome extension was not connected.
  - Guessed file names under `download.microsoft.com/download/8/5/C/85C25433-…/` returned 404 for 25H2 and Server 2025. The 24H2 zip, LGPO.zip and PolicyAnalyzer.zip resolved (3 attempts).
  - Verification: download "Windows 11 version 25H2 Security Baseline.zip" and "Windows Server 2025 Security Baseline" (v2602) from https://www.microsoft.com/download/details.aspx?id=55319 into `_private/sct/` (not published). A follow-up pass can then rerun the crosswalk builder.
- **CIS ids in `settings-crosswalk.csv`:** empty. Verification: download CIS Microsoft Windows 11 Enterprise Benchmark (current version, see `baselines-catalog.md`) into `_private/cis/` (not published) and map ids offline.
- **Tattooing of `Policies` keys and security-settings-extension periodic reapply:** not found in the Group Policy processing page (S1592). No other official page was fetched this pass.
- **Windows 11 defaults for `wuauserv`, `RemoteRegistry` start type and `fDenyTSConnections`:** not confirmed from an official page.
  Verification: on a fresh Windows 11 25H2 VM, run `dsc resource get` for `Microsoft.Windows/Service` (`wuauserv`, `RemoteRegistry`) and `Microsoft.Windows/Registry` (`Terminal Server!fDenyTSConnections`). This proves the defaults a drift report compares against.
- **`OptionalFeatureList` behaviour for a feature name removed from the OS (PowerShell 2.0 on patched 24H2):** not documented.
  Verification: `dsc resource get -r Microsoft.Windows/OptionalFeatureList` with `MicrosoftWindowsPowerShellV2Root` on a patched 24H2 VM shows whether the result is absent, not found or an error.
- **SecurityPolicyDsc / AuditPolicyDsc under DSC 3.3.0 `Microsoft.Adapter/WindowsPowerShell`:** no official statement.
  Verification: run `dsc config test` with one `UserRightsAssignment` and one `AuditPolicySubcategory` on a lab VM as SYSTEM. This proves whether the non-registry 13% of the Microsoft baseline is testable at all.
- **Intune column:** matching is by setting name, so `no_name_match` is not proof of absence. It could be closed by parsing the CSP links in the pinned page.

### A: device settings catalog

- ~~Verification: download the Microsoft SCT Windows 11 24H2/25H2 baseline zip~~ — **superseded**: the
  coordinator obtained a direct zip URL
  (`https://download.microsoft.com/download/8/5/C/85C25433-A1B0-4FFA-9429-7E023E7DA8D8/Windows%2011%20v24H2%20Security%20Baseline.zip`)
  and is populating `settings-crosswalk.csv`, `dsc-coverage.md` and QS2 directly; Part A does not
  duplicate that work.
- **Verification: download the Windows Server 2025 baseline zips (versions 2506 and 2602) from the SCT
  download page (id 55319) into `_private/sct/` (not published), or locate their direct
  download.microsoft.com URLs the same way the coordinator did for the Windows 11 24H2 zip.** Not
  attempted by Part A this pass.
- **Verification: open the `microsoft/osconfig` GitHub repository (or the OSConfig Learn docs' schema
  reference, if any) to confirm whether Server 2025 baseline definitions are published as
  structured data (JSON/YAML) versus only exposed through the PowerShell module's cmdlets** (QS7,
  needed for a real `dsc_v3_path` mapping of OSConfig-covered settings).
- ~~Verification: download the current Windows 11 and Server 2025 STIG zips~~ — **resolved**: the
  coordinator obtained both (Windows 11 V2R9, Server 2025 V1R3, registered as S1470/S1471). Residual
  item: extract the XCCDF from each zip and parse rule ids/registry paths/values into
  `settings-crosswalk.csv`'s `stig_id`/`stig_value` columns — not yet done by either Part A or the
  coordinator as of this message (QS6/QS20).
- CIS terms-of-use text for reuse of recommendation IDs/titles was not opened directly (search
  returned explainer articles, not the terms page itself). `settings-crosswalk.csv` therefore
  carries no CIS IDs or paraphrases this pass (QS1).
- OSConfig Server 2025 baseline machine-readability was not researched (QS7).
- Microsoft baseline vs. Intune baseline setting-level comparison was not performed; needs both
  machine-readable sources above plus an Intune baseline JSON export (QS5).
- ACSC Essential Eight/Windows guidance, NCSC (UK) device guidance, BSI IT-Grundschutz/SiSyPHuS, and
  ANSSI English-language recommendations were not researched beyond placeholder rows in
  `baselines-catalog.csv`.
- QS19 (LSA protection / Credential Guard defaults) rests on a search-engine digest of vendor blogs
  rather than a directly re-opened Microsoft Learn page (S1417 is recorded but its content was not
  independently re-extracted); tagged `COMMUNITY` pending confirmation.
- Exact registry paths/value names for "long paths enabled" and "RDP disabled" in
  `settings-crosswalk.csv` are widely known but were not verified against an official machine-
  readable source this pass; tagged `UNK` rather than `DOC`.
- GP refresh interval, registry-CSE reapplication default, and Policies-key tattooing behaviour in
  `policy-precedence.md` were not re-fetched from an official Microsoft Learn page this pass, despite
  being long-standing documented behaviour; tagged `UNK` for this pass's evidence standard.

### B: management plane

- QS9: exact **current** CIS Microsoft SQL Server benchmark version/date and CIS GitLab Benchmark version/date were seen only via secondary blog posts and a third-party scanner project, not a direct fetch of the cisecurity.org benchmark listing page's version field. `Verification: confirm current CIS Microsoft SQL Server 2022/2025 Benchmark version and CIS GitLab Benchmark version directly on cisecurity.org/benchmark/microsoft_sql_server and the CIS Software Supply Chain Security Benchmarks page (no registration needed for the listing, only for the PDF).`
- QS8: no page was found that explicitly classifies ConfigMgr/MECM as "Tier 0" in Microsoft's own enterprise access model docs. Only the general control-plane/management-plane/data-workload-plane tiering principle (Microsoft cloud security benchmark, privileged access) was confirmed; applying it to ConfigMgr is a derivation (`security/management-plane-hardening.md`), not a documented Microsoft statement.
- QS17: exact GitLab **subscription tier** (Free/Premium/Ultimate) gating for Dependency Scanning vs. SLSA attestation vs. artifact signing was not confirmed against `docs.gitlab.com/subscriptions/features/` in this pass — only the existence and mechanics of the features (`security/supply-chain.md`) were confirmed, not their tier gate. `Verification: cross-check docs.gitlab.com/subscriptions/features/ for the tier of Dependency Scanning, SLSA provenance attestation, and container/artifact signing before using this for a purchasing or gate decision.`
- QS18 (Run Scripts + AllSigned): confirmed Run Scripts has no signing gate of its own and the client-side AllSigned policy is the enforcement point, but did not find an official page describing whether ConfigMgr's CI (compliance) script deployment path differs from Run Scripts on this point — assumed identical based on both using the same client-side PowerShell execution policy setting (already documented in `windows/execution-policy-signing.md`).
- No official Microsoft page was found specifically discussing `dsc.exe` (or DSC v3 resource executables) under WDAC/App Control; general PowerShell WDAC script-enforcement mechanics were confirmed but not a DSC-specific statement. Community source only (S1519), not used as sole evidence for any `DOC` fact.
- PyPI Trusted Publishing's self-managed-GitLab support status is unresolved: the official `docs.pypi.org` page (S1509) does not list self-managed GitLab as supported, while a third-party (Socket) report (S1510, COMMUNITY) claims PyPI expanded support to self-managed GitLab. Recorded as a conflict-worthy discrepancy in `security/supply-chain.md` rather than asserted either way as `DOC`.
- NIST AI RMF "Agentic Profile" (if any, beyond the Generative AI Profile SP 800-218A/AI 600-1) was not found on nist.gov directly; a third-party (Cloud Security Alliance) reference to such a profile was not treated as authoritative and is not cited.

### C: frameworks, regulation, AI

- ISO/IEC 42001:2023 and ISO/IEC 27001:2022/27002:2022 full clause text is paid; only public metadata (numbers,
  titles) was captured. `Verification: obtain ISO/IEC 27001:2022, 27002:2022 and 42001:2023 full text under
  organisational licence if clause-level detail beyond Annex A numbers/titles is needed.`
- MITRE ATLAS technique-level detail (specific technique ids/mitigations for tool-using agents) was not
  enumerated; only the catalog's existence and licensing note were captured. Three-attempt budget on ATLAS
  technique enumeration was not exhausted, but time was allocated to higher-priority QS10-QS14 items first.
- (Resolved 2026-09-24) MITRE ATT&CK mitigation (M-id) and detection-strategy (DET-id) values for
  T1072/T1484/T1098/T1558/T1078/T1219/T1562 are now extracted from the pinned v19.2 STIX bundle into
  `security/artifacts/mitre/attack-subset.csv` and summarized in `threat-model-inputs.md` and QS15.
- UODO's DPIA list (S1551) is in Polish; only the fact that such a list exists and its URL were captured, not a
  translated enumeration of its entries.
- Whether a given device-log/AI-processing system's specific processing meets two or more EDPB DPIA criteria, and
  whether its use case falls under EU AI Act Annex III, are open questions this research pass deliberately left as
  facts-only / UNK, per the brief's instruction not to decide policy questions.

