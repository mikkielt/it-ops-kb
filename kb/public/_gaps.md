# Gaps (UNK items: what was tried, where)

Merged from `_parts/<agent>/gaps.md`.

## agents-a2a-cache

- **A2A v1.0.0 exact release date and "Agentic AI Foundation" naming.** The fetched spec page (S2120) surfaced a reference to an "A2A joins the Agentic AI Foundation" post dated 2026-08-27, which may signal a further governance rename beyond the original Linux Foundation "Agent2Agent Protocol Project" (S2123). Not independently confirmed with a direct fetch of that post (1 attempt: relied on the spec page's own summary, did not separately fetch the referenced post). [UNK] (topic: agents/a2a-protocol)
  - Resolved 2026-09-27: v1.0.0 released 2026-03-12, v1.0.1 published 2026-05-28 with bug fixes only (GitHub releases API, S-xasyjfgi); AAIF is the Linux Foundation-directed Agentic AI Foundation that accepted A2A as a Growth Stage project on 2026-08-27 (S-2jevtssc). (topic: agents/a2a-protocol)
- **Whether any Anthropic product speaks A2A natively.** Checked: A2A GitHub repo listing (no Anthropic in supporting orgs list, S2121), WebSearch for "Claude Agent SDK A2A support" (found only community wrapper projects and one Anthropic+Google Cloud joint webinar demonstrating Claude *inside* an A2A system via Vertex AI, not first-party support, S2129). Did not find an Anthropic docs page stating support or non-support either way. 2 search/fetch attempts; stopping per budget. [UNK] (topic: agents/a2a-protocol)
  - Tried 2026-09-27: searched the Claude Code docs (claude-code-docs server, `a2a|agent2agent`: 0 hits), platform.claude.com `llms.txt` (no A2A mention), a WebSearch on anthropic.com and platform.claude.com (only the S2129 webinar), and the AAIF adopter list in S-2jevtssc (no Anthropic product). Recorded as a documented absence (DER) in the article; a positive statement from Anthropic either way is still missing. (topic: agents/a2a-protocol)
- **A2A SDK language list beyond Python.** The claim that Go/JavaScript/Java/.NET/Rust SDKs exist under `a2aproject` came from one WebFetch summary of the main A2A repo page (S2121) and was not verified by listing each sub-repository individually. [DER, low confidence — treat as needing reconfirmation before citing precisely] (topic: agents/a2a-protocol)
  - Resolved 2026-09-27: the a2aproject organisation listing (GitHub API, S-t24szuu4) shows `a2a-python`, `a2a-js`, `a2a-java`, `a2a-go`, `a2a-dotnet` and `a2a-rs`, plus `a2a-tck`, `a2a-inspector` and `a2a-cli`. (topic: agents/a2a-protocol)
- **`anthropics/courses` repository contents.** Found only via WebSearch snippet, not independently WebFetched in this session (1 attempt, then treated as sufficient given the more pressing budget spent on caching detail). Row is present in `anthropic-materials.csv` marked accordingly. [COMMUNITY-tier evidence for an official repo] (topic: agents/anthropic-materials)
  - Resolved 2026-09-26: repository read directly (S2156): five courses, archived by the owner 2026-09-15 (read-only) (topic: agents/anthropic-materials)
- **Exact cache-read price multiplier for the newest Anthropic model tier.** The fetched prompt-caching page (S2130) states 0.025x-0.05x for "Opus 5.5, Fable 5.1, Mythos 5.1" versus 0.1x for "other models," which conflicts in precision with the separately fetched pricing page's worked example implying 0.05x for Opus 5.5 specifically (S2131). Recorded as a conflict below rather than resolved. [DOC, conflicting] (topic: agents/agent-caching)
- **JSON Schema (non-proto) artifact for A2A.** Searched the pinned commit's tree for a `.json` schema alongside `a2a.proto` and found none at `specification/`; the spec itself says JSON artifacts are generated, non-normative build outputs, so only the proto was saved as the pinned artifact. Not a gap in effort, but noting no separate JSON schema file exists to pin. [DOC S2120] (topic: agents/a2a-protocol)
  - Resolved 2026-09-27: `specification/json/README.md` at v1.0.1 (S-byrq57yo) says `a2a.json` is a non-normative build artifact generated from the proto and not committed; the site serves it at `a2a-protocol.org/latest/spec/a2a.json`. (topic: agents/a2a-protocol)

## agents-authz

- **Closed this pass:** PIM-for-Groups activation-to-effect latency now has numbers — see `answers.md` QG26 deepening (S2052): 2-10 min SCIM provisioning for the first 5 activations/10s per app, else the 40-min sync cycle; the active-assignment write itself remains "within seconds" (S1282, reused). Three distinct latency regimes are now named rather than one partial figure. (topic: agents/agent-rbac)
- **Closed this pass:** HashiCorp Vault dynamic secrets / database secrets engine — TTL (1h default / 24h max), supported engines, lease-revocation mechanics fetched. See `answers.md` QG27 deepening (S2054) and `agents/api-tokens.csv`. (topic: agents/api-tokens-issue-and-store)
- **Closed this pass:** GitLab CI native secrets manager (`ci/secrets/`) and its `id_tokens`-based auth to Vault/Key Vault/GCP/AWS — fetched (S2055, S2056). See `answers.md` QG27/28 deepening and `agents/secret-storage-options.csv`. (topic: agents/api-tokens-issue-and-store)
- **Closed this pass:** Claude Code `apiKeyHelper`'s hot-reload behaviour (no restart needed on settings change) — fetched (S2057). See `answers.md` QG28 deepening. (topic: agents/api-tokens-issue-and-store)
- **Closed this pass:** App roles vs group claims for a service principal specifically — Microsoft's own documented gap ("Entra ID doesn't add the roles claim" when an app role is assigned to a group containing a service principal) fetched (S2053). See `answers.md` QG25 deepening. (topic: agents/agent-rbac)
- **Closed this pass (partially):** OWASP-specific guidance on agent/NHI identity separation and least privilege — the OWASP NHI Top 10 list (S2058) was fetched and mapped to this part's own findings (NHI7, NHI10). The OWASP "Agentic AI – Threats and Mitigations" PDF remains unfetchable by WebFetch (content is inside a PDF, not rendered); still [UNK] for that specific document's threat-ID text. (topic: agents/agent-rbac)
- **Still open: Microsoft Entra Agent ID — PIM support for agent identities specifically.** Neither the agent-identities overview (S2040), the PIM-for-Groups page (S2052, this pass), nor the announcement (S2051) states whether an agent identity can be an eligible PIM member/owner of a role-assignable group the way a human or service principal can. Tried across two passes: S2040, S2051, S2052 (no mention in any); WebSearch budget for this session was exhausted before a further targeted search could be attempted this pass. [UNK] (topic: agents/agent-rbac)
  - Resolved 2026-09-28: the Agent ID authorization page and FAQ (S-fwzaxe7i, S-pmj4jc4f) say agent identities can't be members of role-assignable groups, so PIM-eligible membership there is ruled out (recorded as DOC plus DER in `agents/agent-rbac.md`). (topic: agents/agent-rbac)
- **Still open: S2051 (Microsoft Entra Agent ID announcement) was read only as a WebSearch synthesis in the prior pass, not independently WebFetched.** Not re-attempted this pass (WebSearch budget exhausted; WebFetch of the same URL was not separately retried since S2040 already carries the load-bearing mechanics). Treated as DOC per the prior pass's reasoning; flagged for a direct fetch in a future pass. [DOC, flagged] (topic: agents/agent-rbac)
  - Superseded 2026-09-28: the availability claim now rests on the Entra licensing page (S-ooc6gvno: Agent ID for all Entra customers, Agent 365 licence for security features) and the Agent ID overview (S-4zkj3ag3), not on S2051. (topic: agents/agent-rbac)
- **Narrowed, not closed: HashiCorp Vault's own numeric SLA or default TTL for a *SQL Server* (MSSQL) dynamic role specifically** — the database-secrets-engine page (S2054) gives the *engine's* default (1h/24h TTL) but no MSSQL-specific example or caveat distinct from the generic default; not pursued further this pass (the generic default answers the design-relevance question adequately per the fact already recorded in `answers.md`). [DOC S2054 for the generic default; UNK for an MSSQL-specific worked example] (topic: agents/api-tokens-issue-and-store)
  - Resolved 2026-09-28: Vault's MSSQL plugin page (S-2spmezqp) shows `default_ttl="1h"`/`max_ttl="24h"` for SQL Server and Azure SQL roles and the default revocation procedure; no SLA is published. (topic: agents/api-tokens-issue-and-store)

## agents-copilot

- **Exact wording and trigger condition of Copilot Studio's "instructions limit exceeded" / topic
  count exceeded errors** was not confirmed beyond the numeric limits themselves (8,000 characters
  for agent instructions, 1,000 topics per agent in Dataverse environments, 500 knowledge sources,
  100 skills — all S1960). No error-string text was found on S1960 or S1980 within budget. Tried:
  requirements-quotas (S1960), faq-billing-licensing (S1980, search-summary only). This belongs
  properly to Topic 2 (`agents-errors`); flagged here because QG17's quota inventory surfaces the
  numbers but not the error text. [UNK] (topic: agents/copilot-studio-inventory)
  - Partly resolved 2026-09-27: a Microsoft Q&A user report (S-f3chtt24, 2026-04-29) gives the message "The length of the prompt instructions exceeds the threshold" with code `OpenAIAdditionalInstructionsLengthExceededLimit` at about 5,300 combined characters on a generative-answers node; COMMUNITY only, no Microsoft page confirms the trigger. Topic-count error text still not found. (topic: agents/instruction-and-context-limits)
- **Teams AI library current status** (`microsoft.github.io/teams-ai`) returned HTTP 404 on fetch;
  a second candidate path was not tried within budget. Tried: 1 WebFetch attempt. The Microsoft 365
  Agents SDK docs (S1968) do not mention Teams AI library by name, and GitHub search for
  `microsoft/teams-ai` was not run as a fallback. QG18/QG19's Teams AI library coverage rests on
  general knowledge, not a fetched source, and is marked `[UNK]` in the topic file. [UNK] (topic: agents/own-chatbot-architecture)
  - Resolved 2026-09-28: `microsoft/teams-ai` README at a pinned commit (S-2rginmyk) says Teams AI is now Teams SDK (site microsoft.github.io/teams-sdk). (topic: agents/own-chatbot-architecture)
- **Azure Bot Service SDK overview page** (`learn.microsoft.com/en-us/azure/bot-service/bot-service-overview-introduction`)
  returned HTTP 404 on fetch. The Bot Framework SDK retirement statement is instead sourced from the
  GitHub README (S1976) via WebSearch summary rather than a direct WebFetch of the README file
  itself; the exact retirement date (Dec 31, 2025) was not independently cross-checked against a
  second Microsoft Learn page. [UNK, low confidence in exact day-of-month] (topic: agents/own-chatbot-architecture)
  - Resolved 2026-09-28: the archived botbuilder-dotnet README read directly at a pinned commit (S-cwgzp4nu) states that support tickets are no longer serviced as of December 31, 2025, and points to the Agents SDK. (topic: agents/own-chatbot-architecture)
- **Copilot Credits pricing rates (currency amounts) and the "billing rates" table** referenced by
  S1961 (`requirements-messages-management#copilot-credits-billing-rates`) were not fetched; only
  the mechanism (pay-as-you-go, prepurchase, prepaid pack) is confirmed, not the actual credit
  price. Tried: 0 direct fetch attempts (out of the ~40-page budget spent on breadth over this one
  page). [UNK] (topic: agents/copilot-studio-inventory)
  - Partly resolved 2026-09-28: the billing rates table in credits (S-vyhrpdjp) is now DOC; currency prices per credit sit on the commercial pricing page and licensing guide, not on Learn, and stay out of the kb. (topic: agents/copilot-studio-inventory)
- **A2A protocol support inside Copilot Studio specifically** (as opposed to Foundry Agent Service,
  which explicitly states A2A v1.0 GA and v0.3 preview per S1970) was not confirmed either way for
  Copilot Studio connected agents. Topic 9 (`agents-a2a-cache`) owns A2A depth; flagged here only
  because QG17's "connected agents" line needed it. [UNK] (topic: agents/copilot-studio-inventory)
  - Resolved 2026-09-28: Copilot Studio documents connecting an A2A agent (S2126); recorded in `agents/copilot-studio-inventory.md`. (topic: agents/copilot-studio-inventory)
- **Solution export file format details (topic YAML inside a solution .zip, component schema)**
  were not fetched beyond the code-editor YAML sample (S1963) and the ALM overview (S1967); no page
  was fetched that documents the exact solution .zip layout for a Copilot Studio agent (that lives
  under Power Platform ALM docs, `/power-platform/alm/`, not fetched). [UNK] (topic: agents/copilot-studio-inventory)
  - Tried 2026-09-28, still open: Learn search surfaced no Copilot Studio page documenting the solution .zip layout; the Power Platform solution file format is only described generically. Reading an exported solution in a lab would settle it. (topic: agents/copilot-studio-inventory)

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
  different field, message content). [UNK] (topic: agents/instruction-and-context-limits)
  - Resolved for Assistants 2026-09-27: the OpenAI OpenAPI specification at a pinned commit (S-hcl5uw5c) caps `instructions` at 256,000 characters (Assistants operations marked deprecated). Still open: error text, and any limit on the Responses API `instructions` field (not checked). (topic: agents/instruction-and-context-limits)
- **The commonly cited "128 tools" limit for OpenAI function calling** was not found on either fetched OpenAI page in
  this pass; the pages instead give a soft, non-enforced recommendation ("fewer than 20 functions... at the start of
  a turn"). Whether "128" is a real, separately documented ceiling (for example on the Assistants API specifically,
  which was not directly re-fetched) is unresolved. [UNK] (topic: agents/agent-error-catalogue)
  - Resolved 2026-09-27: 128 is the Assistants API tools-per-assistant limit and the deprecated Chat Completions `functions` cap; the current `tools` array has no `maxItems` (S-hcl5uw5c). (topic: agents/agent-error-catalogue)
- **Gemini's official `systemInstruction` length limit and its exact documented error schema** remain unconfirmed
  from an official page: `ai.google.dev/gemini-api/docs/function-calling` was fetched directly in this pass and
  documents neither a `systemInstruction` character/token ceiling nor an enumerated list of unsupported
  OpenAPI-schema keywords for function declarations. The community-reported ~85-90K-token observed boundary (S1846)
  remains the best available number. [UNK] (topic: agents/instruction-and-context-limits)
  - Partly resolved 2026-09-27: the API reference (S-xxd6fl45) gives `systemInstruction` as a text-only Content object with no stated limit; the API errors page (S-5lgjpf27) documents the error object and codes, none for instruction length. A numeric limit is still unpublished. (topic: agents/instruction-and-context-limits)
- **Gemini function-declaration count limit and function-name pattern/length restriction** were not found on the
  fetched function-calling guide (style guidance only: "underscores or camelCase"). [UNK] (topic: agents/agent-error-catalogue)
  - Partly resolved 2026-09-27: name pattern and 128-character limit from the Gemini API reference (S-xxd6fl45); Vertex AI advises at most 64 (S-hzgoj7bh); the guide (S1866) advises 10-20 active tools. No hard cap on declarations is published. (topic: agents/agent-error-catalogue)
- **A single canonical Claude API reference page enumerating all `stop_reason` values** (including `pause_turn`,
  `refusal`, `model_context_window_exceeded`) was not independently re-fetched in this pass; the three deepening-pass
  additions are tagged `DER` rather than `DOC` for that reason, derived from the tool-use documentation set rather
  than quoted from one authoritative stop-reason table. A follow-up should fetch a page specifically titled around
  "handling stop reasons" (linked from `platform.claude.com/docs/en/agents-and-tools/tool-use/overview` as
  `handling-stop-reasons`) and requote each value's exact definition as `DOC`. Resolved in the census of
  2026-09-25: the page was fetched and the three values are now `DOC` facts citing S-qso6o6wu. (topic: agents/agent-error-catalogue)
  - Resolved (already by 2026-09-26, re-read 2026-09-27): the "Stop reasons and fallback" page (S-qso6o6wu) has a quick-reference table of all seven values; the article's fact cites it as DOC. (topic: agents/agent-error-catalogue)
- **The full "supported JSON Schema subset" reference pages** linked from both Anthropic's strict-tool-use page
  (`build-with-claude/structured-outputs#json-schema-limitations`) and OpenAI's structured-outputs guide were not
  independently fetched in this pass; both parent pages state restrictions exist without enumerating every excluded
  keyword on the page actually fetched. [UNK, partial — the headline restrictions that were confirmed are recorded] (topic: agents/agent-error-catalogue)
  - Resolved 2026-09-27: Anthropic structured outputs (S-dorcmamy: unsupported features, 20 strict tools / 24 optional / 16 union-type parameters) and OpenAI structured outputs (S1867: unsupported composition keywords, 5000 properties, 10 nesting levels) now in the article. (topic: agents/agent-error-catalogue)
- **Copilot Studio / M365 Copilot MCP server support limitations and Copilot Studio's own MCP-tool JSON-Schema
  restrictions** (as distinct from generative-orchestration limits) were not researched in this pass; out of the
  budget after the error-codes and instruction-limit lines of inquiry. [UNK] (topic: agents/agent-error-catalogue)
  - Resolved 2026-09-27: Copilot Studio's MCP troubleshooting page (S-rvnsf5ty, updated 2026-08-19) lists the known schema issues (integer `exclusiveMinimum`, multi-type `type`, reference types filtered, enums as strings, full-URI SSE endpoint); now in the article. (topic: agents/agent-error-catalogue)
- **No official OpenAI, Google, or Microsoft first-party publication of an instruction-count or context-length
  adherence degradation study** (analogous to IFScale or Chroma's Context Rot) was found; both measurement studies
  surfaced in this part remain third-party. [UNK] (topic: agents/instruction-and-context-limits)
  - Partly resolved 2026-09-27: Google's long-context guide (S-uyp3vgvo) states qualitatively that multi-needle retrieval loses accuracy; Thoughtworks Radar Vol 34 (S2164) puts "Agent instruction bloat" in Caution. No numeric first-party study found. (topic: agents/instruction-and-context-limits)

## agents-eval

- **Whether Inspect (`inspect_ai`) has a documented, native MCP stdio target.** Tried: the GitHub
  repository README (S1886), the docs home inspect.aisi.org.uk (S1887), and a WebSearch for
  "inspect_ai MCP tool server". Found only an "MCP Registry" reference in unrelated GitHub navigation
  chrome, no MCP-target class documented in the fetched pages. [UNK, recorded in
  `agents/agent-evaluation.md`]
  - Resolved 2026-09-28 (already covered by S-wwrpen3s): the Inspect docs `tools-mcp.qmd` at main f87b57a5 list `mcp_server_stdio()`, `mcp_server_http()` and `mcp_server_sandbox()`. (topic: agents/agent-evaluation)
- **No vendor (Anthropic/OpenAI/UK AISI) tool or guidance names ConfigMgr, AdminService or a similarly
  shaped internal MCP server specifically.** Every mapping in `agents/mcp-stress-testing.md` from a QG11 stress dimension to
  a concrete tool is therefore `DER`, not `DOC`. This is expected (such a server is not a public product) and is not
  treated as a failed source attempt.
  - Closed 2026-09-27: not a failed lookup. The mappings are DER by design (no vendor documents a private device-management MCP server), as the entry itself says. (topic: agents/mcp-stress-testing)
- **No published number for how many fetched pages state a licence for promptfoo's or garak's *documentation
  site* content separately from the code repository.** (Census 2026-09-25: garak's code is Apache-2.0 per its LICENSE,
  README and pyproject.toml; the GPL-3.0 statement below was wrong.) garak's own GitHub README states GPL-3.0 for the
  code; a secondary claim ("Apache 2.0 License" for site content) came from a WebSearch synthesis of
  garak.ai and was not independently re-fetched from garak.ai itself within the 3-attempt/40-page budget for
  this sub-question. Recorded as a soft confirmation gap, not blocking, since the code licence (GPL-3.0,
  S1891) is what would govern any local re-use. (topic: agents/agent-evaluation)
  - Tried 2026-09-27: garak's reference docs are built from `docs/source` in NVIDIA/garak (docs README: `make -C docs/source clean doc`), a repository whose GitHub licence field is Apache-2.0, so the docs text falls under that licence (DER); reference.garak.ai itself carries no licence statement. promptfoo's docs site not re-checked. (topic: agents/agent-evaluation)
- **DeepEval's exact latest released version/date** was not visible in the fetched GitHub README excerpt
  (only commit count). Not pursued further (budget); the licence (Apache-2.0) and MCP metric names were
  the load-bearing facts for QG9 and were confirmed. [UNK] (topic: agents/agent-evaluation)
  - Resolved 2026-09-28: PyPI shows DeepEval 4.2.6 uploaded 2026-09-24; kept out of the article because it moves weekly. (topic: agents/agent-evaluation)
- **No vendor page was found publishing a numeric contamination-control cadence** (e.g. "rotate golden-set
  questions every N days") beyond Anthropic's qualitative "run continuously" / "nearly 100% pass rate"
  guidance (S1896); a specific regression cadence number is therefore left to the adopting
  task, per QG12's instruction that this baseline is a draft, not a decision. (topic: agents/eval-question-baseline)
  - Tried 2026-09-27: re-read S1896. It gives cadences for running evals (every commit), reading transcripts (weekly) and graduating saturated capability evals into a continuously run regression suite, now in the article; still no cadence for rotating golden-set questions. Recorded as a documented absence; article marked complete. (topic: agents/eval-question-baseline)

## agents-extra

- QG23: could not retrieve `github.com/modelcontextprotocol/registry`'s `server.json` schema file itself (repo
  overview fetched instead; the raw schema file path was not resolved in the budget for this part) or a pinned
  commit/sha256 artifact of it. The repo's preview/API-freeze status and field names (name, version, packages,
  remotes) are recorded from the overview page (S2012) only; exact schema types and required/optional markers are
  not confirmed. 2 fetch attempts made (repo root + one guessed raw path that 404'd); stopped short of the 3-attempt
  ceiling to conserve budget for the other three topics. (topic: agents/mcp-server-lifecycle)
  - Resolved 2026-09-27: the 2025-12-11 `server.json` schema read at registry commit bf4e88cb (S-7xsfc3ct): `name`, `description`, `version` required; package entries require `registryType`, `identifier`, `transport`; version ranges rejected. Facts in the article. (topic: agents/mcp-server-lifecycle)
- QG23: "how clients react to a changed tool description (cache, permissions)" is answered only from the MCP spec's
  `listChanged` mechanics (S2135 (reused id, already recorded elsewhere in this kb)) and Claude Code's own cache-invalidation notes already
  in `claude/otel-monitoring.md`/other parts' `agent-caching.md` (topic 9); no vendor doc found stating whether a
  changed tool description silently re-triggers a user permission prompt in Claude Code specifically. Recorded as
  `UNK` in `mcp-server-lifecycle.md`.
  - Partly resolved 2026-09-27: Claude Code refreshes a server's tools on `list_changed` without reconnecting (S1862), and the Claude API MCP connector beta `mcp-client-2026-09-15` lets a caller pin a server's tool list (S-qpqoaaqj); both now in `mcp-server-lifecycle.md`. Still undocumented: whether a changed description re-triggers a Claude Code permission prompt (claude-code-docs server searched 2026-09-27). (topic: agents/mcp-server-lifecycle)
- QG21: could not fetch the full PDF text of arXiv 2506.08837 with attribution-quality precision beyond WebFetch's
  own extraction; pattern names and one-line trade-offs are taken from that extraction (S2005) and are not verified
  against the original section headings word-for-word. (topic: agents/prompt-injection-design-patterns)
  - Tried 2026-09-28, not re-attempted: the facts cite the abstract page; a full-text read is only needed for exact quotations. (topic: agents/prompt-injection-design-patterns)
- QG24: per-engineer cost attribution specific to a *stdio MCP server tool* (rather than whole-session cost) is not
  published anywhere found; Claude Code's MCP-attribution feature in `/usage` attributes by MCP *server*, not by
  individual MCP *tool* within a server. Recorded as a gap in `agent-cost-governance.md`. (topic: agents/agent-cost-governance)
  - Tried 2026-09-28, still undocumented: the Claude Code MCP and analytics pages give session-level cost only; per-tool attribution would need the server's own logging. (topic: agents/agent-cost-governance)

## agents-mcp

- **No published per-call latency number for Claude subagent spawn overhead** (only qualitative "fresh context, higher latency" from S1923). Tried: code.claude.com/docs/en/sub-agents (S1923, qualitative only), WebSearch for "claude code subagent spawn latency milliseconds" style queries returned no vendor number. [UNK] (topic: agents/subagents-vs-deterministic-tools)
  - Tried 2026-09-28, still none published: the Claude Code subagent docs describe fresh context only; a number needs a measurement. (topic: agents/subagents-vs-deterministic-tools)
- **No vendor-published success-rate/eval-pass-rate threshold for "replace this subagent with a tool."** Anthropic's evals guidance (S1935) describes *how* to measure tool-use quality (task success, tool-call count, token count, error rate) but does not publish a numeric threshold at which a workflow step should convert from agent-driven to hard-coded. Tried: S1920, S1935, S1936; no vendor number found. Recorded as `DER` in answers.md instead. [UNK] (topic: agents/subagents-vs-deterministic-tools)
  - Tried 2026-09-27: re-read S1896 and a WebSearch; the guidance says an eval at 100% tracks regressions but gives no improvement signal, and publishes no numeric threshold for replacing a subagent with a tool. Still open. (topic: agents/subagents-vs-deterministic-tools)
  - Tried 2026-09-28, still none published: recorded as a DER absence in `agents/subagents-vs-deterministic-tools.md`; a threshold would have to come from the operator's own eval baseline. (topic: agents/subagents-vs-deterministic-tools)
- **No official Anthropic or Microsoft page stating an exact percentage figure for cost escalation from a runaway/recursive subagent** beyond the "another 10x or more" figure from a secondary (COMMUNITY) source (S1930). Anthropic's own multi-agent post (S1921) describes the failure mode (excessive subagent spawning) but not a cost multiplier for it. Tried: S1921 (qualitative), S1930 (COMMUNITY, has the number). [COMMUNITY only, tagged as such] (topic: agents/agent-overuse-patterns)
  - Tried 2026-09-27: the only vendor multiplier found is Claude Code's "about 7x more tokens" for agent teams in plan mode (S2132, already in `agent-cost-governance.md`); no vendor figure for runaway or recursive spawning. Still open. (topic: agents/agent-overuse-patterns)
- **MCP "tasks" capability (`execution.taskSupport`) details** were found only via a WebSearch summary (S1929-adjacent search, not independently re-fetched from the modelcontextprotocol.io tasks page) — not fetched directly in this session; the fetched tools page (S1928) is the 2025-06-18 revision and does not itself describe `taskSupport`. Tried: one WebSearch, one WebFetch of the tools page only (budget stopped after the outputSchema/annotations facts were confirmed there). Recorded as `UNK` for the exact task-support default value beyond the search snippet. [UNK] (topic: mcp/tasks-extension)
  - Found 2026-09-27 (for the mcp wave to write up): MCP schema 2025-11-25 `ToolExecution.taskSupport` takes "forbidden" | "optional" | "required" and "forbidden" is the default when absent (modelcontextprotocol/modelcontextprotocol@ab3a39c1 `schema/2025-11-25/schema.ts`); the 2026-07-28 schema drops it and tasks move to the ext-tasks extension (S718). (topic: mcp/tasks-extension)

## agents-ner

- No throughput number (requests/sec, documents/minute, or p95 latency) for a shared PII-detection
  endpoint was found for any of Presidio, Azure AI Language, Amazon Comprehend or Google Sensitive Data
  Protection. Presidio's own Kubernetes/App Service samples give only qualitative scaling advice
  ("set resource limits and autoscaling"). 3 search attempts made across the four vendors; none surfaced
  a published number. [UNK — `agents/shared-ner-service.md` QG30]
  - Partly resolved 2026-09-27: Azure Language publishes rate quotas (S / multi-service 1,000 requests per second, S0/F0 100 per second; S2093), now in the article. No latency or throughput benchmark found for any of the four; Comprehend per-operation TPS sits in the AWS Service Quotas console (not read). (topic: agents/shared-ner-service)
- Exact Azure AI Language PII pricing (dollar amounts per 1,000 text records at each volume tier, and for
  the disconnected-container annual licence) was not retrieved — the pricing calculator's per-tier rates
  are not rendered in the fetched page content and require the interactive calculator or a sales contact.
  [UNK — `agents/shared-ner-service.md` QG30]
  - Partly resolved 2026-09-27: Azure Retail Prices API (S-g6nzyems): Standard Text Records $1.00 / $0.75 / $0.30 / $0.25 per 1,000 records at 0 / 500K / 2.5M / 10M; mapping PII to that meter is DER from S2095. Disconnected-container annual licence prices still not found. (topic: agents/shared-ner-service)
- Google Sensitive Data Protection's per-GB rates ($1.00/$1.50/$0.05 for discovery/storage/streaming) come
  from a fetched third-party-style summary of the pricing page, not a direct table read from
  `cloud.google.com/sensitive-data-protection/pricing`; treat as approximate pending a direct re-check.
  [UNK/needs confirmation — `agents/shared-ner-service.md` QG30]
  - Resolved 2026-09-27: the live pricing page (S2101, re-read) has the article's figures ($3.00 hybrid inspection, $0.03/GB consumption discovery, $2,500 per subscription unit); "$1.50" and "$0.05" appear nowhere on it, so the old summary was wrong. (topic: agents/shared-ner-service)
- No on-premises or disconnected container deployment was found for either Amazon Comprehend or Google
  Sensitive Data Protection (both presented as cloud-hosted APIs only in every source checked); this is
  recorded as an absence, not a confirmed "does not exist," since only public vendor docs were searched
  (3 attempts each). [UNK — `agents/shared-ner-service.md` QG30]
  - Partly resolved 2026-09-27: Google documents only hybrid jobs, which stream on-premises data into the cloud service and keep findings in Google Cloud (S-hfymbj4j); recorded as a DER absence. Comprehend not re-searched. (topic: agents/shared-ner-service)
- No GDPR controller/processor analysis specific to an internal shared NER/PII-detection endpoint (as
  opposed to pseudonymisation and identifiability generally, already covered in
  `privacy/gdpr-pseudonymisation.md`) was found in any EDPB or Microsoft/AWS/Google compliance page
  fetched this session. [UNK — `_answers.md` QG31]
  - Resolved 2026-09-27: EDPB Guidelines 07/2020 v2.0 (S-zg4p62eo): a processor must be a separate entity, a department cannot be a processor to another department of the same entity; added to `security/privacy-compliance.md` with the DER for an internal shared endpoint. (topic: security/privacy-compliance)
- No published numeric trigger (consumer count, detection-gap percentage, or maintenance-hour figure) for
  when to centralize a shared NER service was found from any vendor or community source. [UNK —
  `_answers.md` QG32] (topic: agents/shared-ner-service)
  - Not re-researched 2026-09-27 (no candidate source identified); still open. (topic: agents/shared-ner-service)
- Presidio's own caller-authentication story for a shared analyzer/anonymizer deployment (e.g. built-in
  API-key support) was not found in the fetched docker/k8s/app-service samples; only Azure's container
  documents an API-key requirement. [UNK — `agents/shared-ner-service.md` QG31]
  - Resolved 2026-09-27 (CODE): the analyzer and anonymizer REST servers at commit e9895a51 (S-5gpkixnx, S830) are Flask apps with no authentication check; caller auth must be added in front. (topic: agents/shared-ner-service)

## agents-overuse

- **Google's "Agents Companion" whitepaper and Cloud Architecture Center agentic-architecture page were
  not independently fetched.** `docs.cloud.google.com/architecture/choose-agentic-ai-architecture-
  components` returned HTTP 403 to WebFetch, and the Kaggle-hosted whitepaper page was only summarized via
  WebSearch, not fetched directly. Tried: one WebFetch attempt on the Cloud Architecture Center page (403),
  one WebSearch covering both pages. Facts from these are tagged `DOC` (they describe Google's own
  published position) but are recorded here as **not independently re-verified against the primary text**
  in this session. [UNK — verification gap, not a content gap] (topic: agents/agent-overuse-patterns)
  - Partly resolved 2026-09-27: the Cloud Architecture Center page read directly (S2160, HTTP 200, last updated 2026-04-21); its wording is now quoted in the article and the stable-logic wording it lacked was removed. The Kaggle whitepaper page (S2161) renders no text without JavaScript and Claude in Chrome was unavailable: still unread. (topic: agents/agent-overuse-patterns)
- **Two Microsoft Community Hub blog posts' bodies could not be retrieved.** "Three tiers of Agentic AI -
  and when to use none of them" and "Stop Letting Agents Run the Workflow" both returned only their page
  title to WebFetch (no body content), and the session's WebSearch budget was exhausted (200/200) before a
  second search could pull a fuller summary. Tried: one WebFetch per URL (title-only response), the prior
  WebSearch that first surfaced the "three tiers" title. No numeric or quoted content from either post is
  used beyond the title itself. [UNK] (topic: agents/agent-overuse-patterns)
  - Resolved 2026-09-27: S2162's body read from the page's embedded JSON (curl with a pinned resolve), confirming its first-tier question; S2163 was already readable. (topic: agents/agent-overuse-patterns)
- **No official vendor benchmark comparing agent vs. deterministic-tool cost, latency and error rate on
  the same task exists in what was fetched.** The two numeric figures used (cost-per-token-volume,
  per-model latency spread) are both COMMUNITY (Stevens Online blog, a DEV Community post), not
  vendor-published. Tried: one WebSearch for "'AI agent' cost latency error rate compared to deterministic
  script published numbers postmortem" (returned only community sources); the session's WebSearch budget
  was then exhausted for further attempts. [COMMUNITY only, tagged as such — see `agent-overuse-patterns.md`] (topic: agents/agent-overuse-patterns)
  - Tried 2026-09-27: one WebSearch for official benchmarks; found only a Microsoft Open Source Blog post on Conductor (S-3zepbhux) arguing that dynamic orchestration adds cost, latency and unpredictability, with no numbers. Still open. (topic: agents/agent-overuse-patterns)
- **No specific published "post-mortem" of an agent used where a deterministic tool would have sufficed**
  was found from an official source. Tried: the OpenAI/Microsoft/Google/Anthropic pages already fetched
  for QG37 (none names a specific named incident); one WebSearch for cost/latency/error numbers (returned
  general cost-modelling posts, not an incident writeup). [UNK] (topic: agents/agent-overuse-patterns)
  - Tried 2026-09-27: WebSearch for official post-mortems returned community pages and arXiv only. Still open. (topic: agents/agent-overuse-patterns)
- **Thoughtworks Technology Radar's exact ring placement (Adopt/Trial/Assess/Hold) for a broader
  "agent overuse" or "coding-agent antipattern" entry beyond "Agent Skills"** was not confirmed by direct
  fetch of the Radar PDF's relevant pages; the facts used come from a WebSearch summary of Volume 34, and
  a second WebSearch to fetch the PDF's own text for the specific ring assignment could not be run because
  the session's WebSearch budget (200 calls, shared across this session's agents) was exhausted after the
  first four queries in this part. Tried: one WebSearch specifically for Radar coding-agent entries
  (blocked by budget exhaustion before it ran). [UNK] (topic: agents/agent-overuse-patterns)
  - Resolved 2026-09-27: read from the Vol 34 PDF text (S2164): rings are Adopt, Trial, Assess and Caution; Caution blips include Agent instruction bloat, Coding agent swarms, Ignoring durability in agent workflows and MCP by default; Agent Skills and Sandboxed execution for coding agents are Trial. (topic: agents/agent-overuse-patterns)
- **Session-wide WebSearch budget (200 calls) was exhausted partway through this part's research**, which
  is why several facts above rely on the initial WebSearch summaries rather than a WebFetch of primary
  text, and why no further searches (e.g. for additional Thoughtworks Radar entries, more published
  cost/latency numbers, or a second Google source) could be run. This is a session-level constraint, not a
  per-topic 3-attempt stop. [UNK — recorded as the governing constraint on this part's remaining gaps]
  - Closed 2026-09-28: a note about an old session's budget, not a knowledge gap; the affected items were revisited in later waves.

## agents-wiki

- **DeepWiki's automatic refresh cadence** (cron vs. webhook vs. purely on-demand) remains undocumented after a second attempt this session against `docs.devin.ai/work-with-devin/deepwiki`. The only confirmed trigger is the explicit, human-initiated one: commit `.devin/wiki.json` and ask Devin/DeepWiki to regenerate. Not pursued further under the 3-failed-attempt budget rule. [UNK] (topic: agents/docs-maintenance-agents)
  - Partly resolved 2026-09-27: the deepwiki README (S-tpvi7ohn) says repositories with a DeepWiki badge are auto-refreshed, and Devin indexes each repository's default branch (S-k527bca2). No cadence is published (docs.devin.ai llms.txt and index-repo page read). (topic: agents/docs-maintenance-agents)
- **`CognitionAI/deepwiki` GitHub repository's licence and actual contents** remain unverified (only its existence surfaced via search in the first pass; not re-attempted this session). [UNK] (topic: agents/docs-maintenance-agents)
  - Resolved 2026-09-27: at its last commit 10f554ce (2025-05-22) the repository holds only a README (MCP tools and endpoints, badge auto-refresh) and no licence (S-tpvi7ohn). (topic: agents/docs-maintenance-agents)
- **Mintlify's code-diff "agent API"** for auto-updating documentation from code changes (as opposed to the always-on `llms.txt` deploy-time export, which is confirmed `DOC`) is recorded only as a `COMMUNITY`-sourced search-engine synopsis; the specific how-to page describing its trigger, auth, and review-gate mechanics was not independently fetched in either pass. [UNK: exact mechanism, not the existence of the feature] (topic: agents/docs-maintenance-agents)
  - Resolved 2026-09-27: Mintlify docs (S-jgplbv5j) list automation triggers (content update, code change, schedule, integration) and two modes (merge directly or open a PR for review); auto-merge needs the app on every ruleset's bypass list (S-f2vfcma6). (topic: agents/docs-maintenance-agents)
- **`lychee` (link checker)**: the URL used this session (`lychee.cc`) did not resolve (`ENOTFOUND`); the tool's correct current site/repo and licence were not independently confirmed. Its role as a deterministic link-check guardrail is stated in the deepening-pass brief but not vendor-verified here. [UNK] (topic: agents/docs-maintenance-agents)
  - Resolved 2026-09-27: README at tag lychee-v0.24.2 (S-xote3xa2): Rust async link checker, GitHub Action and pre-commit hook, Apache-2.0 or MIT; homepage lychee.cli.rs. (topic: agents/docs-maintenance-agents)
- **`doc-detective`**: not fetched at all this session (outside the URL list given); remains an unresearched community tool candidate for doc-drift detection. [UNK] (topic: agents/docs-maintenance-agents)
  - Resolved 2026-09-27: README at tag v4.38.1 (S-sit75nzz): AGPL-3.0 documentation-testing framework that runs doc-derived tests in a browser or against APIs and outputs PASS/FAIL JSON. (topic: agents/docs-maintenance-agents)
- **GitHub Copilot coding agent's own scheduled/issue-triggered documentation-update workflow** (as distinct from Copilot Spaces, a context store, and from `.github/copilot-instructions.md`/`AGENTS.md` support, both now confirmed `DOC`) was not found as a named, distinct product feature in the one official page fetched (`best-practices-for-using-copilot-to-work-on-tasks`). GitHub's own equivalent scheduled-drift pattern instead appears to live in the separate `gh-aw` project (now confirmed `DOC`), not in Copilot coding agent itself. [UNK, narrowed from the first pass's broader "no docs-update feature found"] (topic: agents/docs-maintenance-agents)
  - Resolved 2026-09-27: GitHub's Copilot docs now cover GitHub Agentic Workflows (public preview; S-h6jpev6e), which lists keeping documentation up to date with code changes as a use case, with writes only through `safe-outputs`. (topic: agents/docs-maintenance-agents)

## arch

- **No Microsoft-documented way for Linux (Python gssapi/pyspnego/requests-gssapi, adutil, mssql-conf) to retrieve a gMSA's `msDS-ManagedPassword` and turn it into a keytab.** Tried: `adutil keytab createauto` (requires explicit `--password`, built for conventional AD accounts per S1606), Microsoft Learn search for "gMSA Linux", MIT Kerberos docs. Only AWS's `credentials-fetcher` (S1607/S1608, COMMUNITY, Apache-2.0, AWS open source) claims to fetch gMSA credentials over LDAP for Linux. Verification: could be checked by running `credentials-fetcher` against a lab AD gMSA and a lab Linux host, watching whether it produces a usable keytab/ticket — out of scope for this research pass. (topic: arch/kerberos-linux-containers)
  - Tried 2026-09-28, still none: recorded as a DER absence (adutil options, AWS daemon only). Needs Microsoft to document it; not resolvable by web research. (topic: arch/kerberos-linux-containers)
- **No stated Windows-Server-version floor specific to Kubernetes gMSA** beyond the general Windows-container gMSA fix history (2019 fixes for hostname/race-condition issues); kubernetes.io doesn't restate a minimum OS build. Tried: kubernetes.io gmsa page (S1600) — silent on this; would need a targeted Microsoft Learn "Windows container OS compatibility" cross-reference. [UNK, recorded in arch/k8s-gmsa-windows.md]
  - Tried 2026-09-28, still none: the kubernetes.io gMSA task page (main) marks the feature stable since v1.18 and uses an ltsc2019 image in examples, but states no Windows Server minimum. (topic: arch/k8s-gmsa-windows)
- **No GA date for Azure Arc-enabled Kubernetes workload identity federation** — page (S1609) still labelled preview at retrieval (updated 2025-11-18). No separate GA announcement found via search. Verification: not checkable without a live Azure subscription; recheck by re-reading S1609 periodically for a status change. (topic: arch/workload-identity-onprem-k8s)
  - Resolved 2026-09-28: the Arc-enabled Kubernetes release notes (S-vspquxtf) announce general availability with agent 1.32.7 (February 2026); the conceptual page title still says preview. (topic: arch/workload-identity-onprem-k8s)
- **`Authentication=ActiveDirectoryDefault` behavior for msodbcsql18 against on-prem/Arc-enabled SQL Server specifically** was not confirmed by a fetched page (search summary only, centered on Azure SQL DB/MI). Tried: WebSearch only, did not fetch the full ODBC Entra ID page content beyond the search summary. Could be closed with one more WebFetch of S1610 if this specific mode becomes load-bearing. (topic: arch/sql-auth-containers)
  - Resolved 2026-09-28 into a conflict: the driver feature matrix (S-g2zvqta5) says the ODBC driver doesn't support default Azure authentication and the keyword list (S1610) omits it, while the mssql-django page (S-67zasdym) shows it with ODBC Driver 18; recorded in `_conflicts.md`. (topic: arch/sql-auth-containers)


- Whether Power BI "field parameters" or a report-bound SQL/CSV table (as opposed to Analysis
  Services metadata translations) is a realistic, officially documented mechanism to localize
  report label text was not confirmed against official Microsoft Learn docs within the fetch
  budget. `arch/texts-catalogue-formats.md` [UNK]
  - Resolved 2026-09-28: Power BI's multiple-language guidance (S-u6o4ef53, S-r4s5o7eh) says layout text can't be localized and report labels go into a Localized Labels table of measures; field parameters aren't named. (topic: arch/texts-catalogue-formats)
- No official PowerShell or Power BI Fluent (FTL) runtime was found; absence was inferred from
  search results, not from an exhaustive official-docs negative confirmation. `arch/texts-catalogue-formats.md` [UNK]
  - Resolved 2026-09-28: Project Fluent's active repositories (S-7sn3nxho) are the JavaScript, Python and Rust runtimes; recorded as DER, and the old "Python and Rust" wording is corrected. (topic: arch/texts-catalogue-formats)
- GitLab's semantic-versioning requirement for Catalog releases: found stated in prose docs plus a
  still-open backend enforcement issue (#427286) — unclear from official docs alone whether
  non-semver tags are currently rejected at release time or only informally required. `arch/gitlab-ci-components.md` [UNK]
  - Closed 2026-09-28: a found item recorded for completeness, no open question.

## auth

### on-prem / Windows / ConfigMgr / SQL

Closed this pass (see kerberos.md, ntlm-deprecation.md, ad-jit-membership.md, configmgr-rbac-auth.md):
- RC4-in-Kerberos deprecation dates — found and dated (S1215, S1216, S1217). (topic: auth/kerberos)
  - Closed 2026-09-28: found item, no open question. (topic: auth/kerberos)
- AD PAM TTL vs Kerberos ticket lifetime — found (S1219): TTL propagates directly into TGT lifetime. (topic: auth/ad-jit-membership)
  - Closed 2026-09-28: found item; the early-removal edge case is tracked in its own entry. (topic: auth/ad-jit-membership)
- ConfigMgr RBAC mechanics (QA2) — read 3 official pages (S1218 + 2 more); no provider-cache statement exists, confirmed UNK, LAB line recorded.
  - Partly resolved 2026-09-27: the Kerberos part is now DOC (S-ffrzumip: a group change does not affect the current TGT or its service tickets); no ConfigMgr page documents a provider cache (Configure role-based administration S-iqal4gqk read in full), recorded as a DER absence. (topic: auth/configmgr-rbac-auth)

Still open: (topic: auth/configmgr-rbac-auth)
- ConfigMgr-specific provider/role cache behaviour on top of Kerberos PAC group SIDs (QA2): confirmed UNK after 3 official-source attempts (role-based administration fundamentals, configure role-based administration, plan for the SMS Provider, `SMS_Admin` WMI class reference).
  Verification: on an isolated ConfigMgr lab site, add a test admin to a role-granting AD group, call AdminService with an existing ticket, then again after `klist purge`+re-logon → proves whether the SMS Provider adds delay beyond the Kerberos PAC refresh. (topic: auth/configmgr-rbac-auth)
  - Tried 2026-09-27: Learn searches for SMS Provider membership refresh and token cache, Configure role-based administration (S-iqal4gqk), Plan for the SMS Provider, Accounts, AdminService pages, web search: no provider cache documented. The article records the TGT rule (DOC) and the absence (DER); the lab check stays open. (topic: auth/configmgr-rbac-auth)
- Mid-ticket TTL group removal (QA10 edge case): does an already-issued, TTL-capped TGT survive an admin's early removal of the membership, or is it invalidated immediately? Not stated in S1219.
  Verification: in an isolated PAM-enabled forest, add then early-remove a TTL group membership and observe whether the already-issued TGT is honoured until its original (TTL-capped) expiry. (topic: auth/ad-jit-membership)
  - Narrowed 2026-09-28: by the documented Kerberos rule that membership changes don't touch an existing TGT or its service tickets (S-ffrzumip, S-v5wjmc3h), an early removal is kept in tickets until they expire; recorded as DER. The lab check stays to confirm it for PAM TTL links. (topic: auth/ad-jit-membership)
- `python-ldap` on Windows: does it negotiate SASL sign/seal against a signing-enforced DC over plain `ldap://`? API is documented (S1220) but its Windows sign/seal behaviour is not stated by the docs.
  Verification: attempt `ldap3` vs `python-ldap` vs pywin32/ADSI (`ADS_USE_SIGNING|ADS_USE_SEALING`) GSSAPI binds over plain `ldap://` against a Server 2025 DC with LDAP signing enforced → settles QA15 fully. (topic: auth/ldap-smb-signing)
  - Partly resolved 2026-09-27: python-ldap 3.4.8 builds on OpenLDAP + Cyrus SASL and ships no wheels; Windows builds are unofficial (S-mc5jjnfr); the SSF options are documented (S-qscera6a); pywin32 b312 wraps ADsOpenObject with the flags DWORD (CODE S-eu32xfgv, S-lzhs4uhl); ldap3 2.9.1 raises on a required security layer (CODE S-63f6rimh). Windows sign/seal behaviour against an enforcing DC still needs the lab. (topic: auth/ldap-smb-signing)
- DPoP (RFC 9449) GA status for general Entra ID access tokens (beyond MSAL PoP and Windows Token Protection/PRT binding specifically): not confirmed as GA vs preview from an official source. (topic: auth/transport-crypto)
  - Tried 2026-09-27: Learn search for DPoP / RFC 9449 GA (none); MSAL.NET PoP page (S1223, 'aims to support'); Microsoft Identity Web token binding: mTLS PoP in private preview (S-furaoufn); Entra discovery document advertises mTLS-bound tokens and no DPoP algorithms (S-btl752nc). Recorded as a DER absence; still no GA statement. (topic: auth/transport-crypto)
- RFC 8693 Token Exchange support in Entra ID: no official Microsoft statement found either confirming or denying; only community sources describe it as unsupported (OBO/client-credentials offered instead). Tried: Microsoft Learn identity-platform search, RFC 8693 + Entra web search. (topic: auth/delegation-kcd-obo)
  - Tried 2026-09-27: Entra Agent ID protocols page lists client_credentials, jwt-bearer and refresh_token only, for agent apps (S-ygq2kmmq); discovery document has no grant_types_supported (S-btl752nc). No product page confirms or denies RFC 8693; recorded as a DER absence, the Q&A denial stays COMMUNITY. (topic: auth/delegation-kcd-obo)
- SMB 3.1.1 cipher negotiation specifics (AES-128-GCM vs AES-256-GCM) beyond the signing/encryption defaults: not researched. (topic: auth/ldap-smb-signing)
  - Resolved 2026-09-27: AES-128-GCM default for SMB 3.1.1, AES-256-CCM/GCM from Server 2022 and Windows 11, strongest common cipher negotiated, mandatable by Group Policy (S-77zvblfr). (topic: auth/ldap-smb-signing)
- MIM PAM product support status in 2026: not researched. (topic: auth/ad-jit-membership)
  - Resolved 2026-09-28: MIM 2016 end of support extended to 2029-01-09, SP3 current (S-a3advgfv). (topic: auth/ad-jit-membership)

### Entra / Graph / MSAL / GitLab

- Per-app-registration numeric limit on federated identity credentials (QA4): three-search budget not
  spent hunting the exact limits page; tried general searches, found the mutable-subjects feature page
  but not the limits page directly. Verification: not applicable (this is a docs lookup, not a lab check) —
  needs one more targeted fetch of an Entra app-registration/FIC "limits" or "known issues" page. (topic: auth/workload-identity)
  - Resolved 2026-09-27: at most 20 federated identity credentials per application or user-assigned managed identity (S1293, live page re-read); already in the article and now in gitlab-ci-identity.md. (topic: auth/workload-identity)
- Headless/jump-host-specific WAM caveats beyond "Windows 10+/Server 2019+ supported" (QA5): not found
  in the two WAM pages fetched. Verification: run `msal[broker]` interactive acquisition on a Windows Server
  2025 jump host with no interactive console session (e.g. RDP disconnected) -> proves whether WAM's
  window-handle requirement fails outside an active session. (topic: auth/msal-public-client)
  - Tried 2026-09-27: S1270 re-read (no session caveat); MSAL 1.39.0 falls back to the console, then the desktop window, when no handle is given (CODE S-2tlwkw6u). Recorded as a DER absence; the lab check stays. (topic: auth/msal-public-client)
- Whether Token Protection covers a bespoke MSAL Python public client's Graph calls, not just
  EXO/SPO desktop apps (QA6): deployment guide scopes examples to Microsoft first-party apps only.
  Verification: enable a Token Protection Conditional Access policy scoped to Microsoft Graph in a test tenant,
  target a test MSAL Python public client, and check whether the refresh token issued is
  proof-of-possession bound and whether Graph rejects it without a matching device. (topic: auth/msal-public-client)
  - Resolved 2026-09-27 (negative): S1227 re-read lists Exchange Online, SharePoint Online, Teams, AVD and Windows 365 as native-app resources; Graph is not one, so Token Protection does not bind Graph calls (DER S1227). (topic: auth/msal-public-client)
- Whether nested-group membership counts toward an app-role assignment made to a group (QA7,
  `roles` claim path specifically, as opposed to the `groups`-assigned-to-application claim which is
  documented as excluding nesting): not stated in the two group-claims pages fetched.
  Verification: nest a child group inside a parent group, assign the app role to the parent only,
  sign in as a user who is only a member of the child group, inspect the `roles` claim. (topic: auth/group-claims)
  - Resolved 2026-09-27: S1310 says the assignment doesn't cascade to nested groups; only direct members get the role. (topic: auth/group-claims)
- Call-specific throttling and caching guidance for `checkMemberGroups`/`getMemberGroups`, and whether
  they honour CAE (QA18): the two API reference pages carry no throttling/CAE note specific to these
  calls. Verification: none — needs a documentation-only follow-up fetch of the Graph throttling guidance page
  cross-referenced against these two methods. (topic: auth/role-source-options)
  - Resolved 2026-09-27: me/checkMemberGroups costs 4 resource units and me/getMemberGroups 2, same for users/{id} (S526); CAE follows Graph's cp1 rule (DER S1355). No caching guidance exists on S1286, S1287 or S526. (topic: auth/role-source-options)
- `delegation-kcd-obo.md` now researched (round 2). Remaining gap: the MCP Enterprise-Managed
  Authorization / ID-JAG "stable June 2026" date and "Entra native ID-JAG not GA" claim come from a
  vendor/community blog (S1300), not modelcontextprotocol.io itself or a Microsoft Learn "what's new"
  page. Verification: none (docs lookup) — needs a direct fetch of
  `modelcontextprotocol.io/extensions/auth/enterprise-managed-authorization` and an Entra Identity
  Platform "what's new" page to upgrade this from COMMUNITY to DOC. (topic: auth/delegation-kcd-obo)
  - Resolved 2026-09-27: the ext-auth repository marks Enterprise-Managed Authorization Stable, promoted by PR #29 merged 2026-06-18 (S-hrri7kcy); Entra ID-JAG issuance is undocumented (DER S-uw3gpx3u); "Okta only at launch" stays COMMUNITY S1300. (topic: auth/delegation-kcd-obo)
- Whether MSAL Python's `client_assertion` callable parameter (supplying a pre-built JWT) is the
  supported way to back a confidential-client credential with a non-exportable CNG/TPM key (i.e. a
  custom signer calls CNG/TPM and MSAL just transports the resulting assertion): documented
  `client_credential` dict/PFX options all need MSAL to read the private key directly; the
  `client_assertion` escape hatch's suitability for this wasn't independently confirmed against a
  CNG/TPM example in this pass. Verification: build a minimal custom assertion signer using
  `ncrypt`/`cryptography` against a non-exportable CNG-backed cert, pass its output via MSAL's
  `client_assertion`, and confirm Entra accepts it -> proves the escape hatch works end-to-end. (topic: auth/key-management-options)
  - Mostly resolved 2026-09-27: pre-signed client_assertion documented since 1.13.0 (S-ftk5lzj7), callable in 1.39.0 (CODE S-wk6ahp72), Entra assertion format any JWT library can build (S-zb4abl74). End-to-end acceptance with a non-exportable CNG/TPM key is still a lab check. (topic: auth/key-management-options)
- Token Protection: no source names MSAL Python or a CLI/console app by name as in- or out-of-scope;
  the "native client" framing is the closest documented anchor. Verification: in a test tenant, apply a Token
  Protection Conditional Access policy scoped to Microsoft Graph + "Mobile apps and desktop clients",
  authenticate a test MSAL Python public client (WAM broker) against a test resource, and check
  whether the token is proof-of-possession bound / whether Graph enforces it -> proves whether Token
  Protection reaches a Python CLI in practice. (topic: auth/msal-public-client)
  - Tried 2026-09-27: S1274 re-read (updated 2026-09-24) still names no MSAL Python or CLI app; Graph is outside Token Protection's resource list (S1227), so only EXO/SPO/Teams calls could be bound. Lab check stays. (topic: auth/msal-public-client)

### keys, propagation, revocation, audit, threats

- DPAPI-NG `SID=` descriptor: no Microsoft page found stating (a) the KDS root key propagation delay before a newly created descriptor's key is retrievable domain-wide, (b) the minimum DC functional level/version required, (c) behaviour when the user leaves the group without a new logon, (d) recovery path if the group is deleted. Tried: `learn.microsoft.com/windows/win32/seccng/protection-descriptors`, `cng-dpapi-constants`, general web search. 3 attempts, stopped per budget rule.
  Verification: On a lab DC + lab client, create a DPAPI-NG blob with `SID=<test group>`, remove the encrypting user from the group without logging off, then attempt `NCryptUnprotectSecret` from a cached logon session vs. a fresh logon -> proves whether group removal is enforced at unprotect time or only at next logon. (topic: auth/key-management-options)
  - Partly resolved 2026-09-27: (b) GKDI servers are DCs at DS_BEHAVIOR_WIN2012 or higher and the access check is on the DC (MS-GKDI, S-53ajdzoj); (a) KDS root key 10-hour wait from S402 (gMSA page, DER for DPAPI-NG); (c) clients SHOULD cache group keys, so a removed user may decrypt with a cached key (DER). Still open: Windows cache lifetime and (d) group deletion. (topic: auth/key-management-options)
- PIM for Groups activation latency into tokens and `checkMemberGroups`, and whether it reaches on-prem AD groups (QA9): not researched by this agent (overlaps role-source-options.md territory); left `[UNK]` in propagation-latency.csv.
  Verification: Activate a PIM-for-Groups membership in a lab tenant, immediately request a token and call `checkMemberGroups`, time the delay. (topic: auth/propagation-latency)
  - Resolved 2026-09-27: membership within seconds with app-side caching (S1282), Intune roles via PIM for Groups up to 15 minutes (S-ljhugmcx), on-prem only through Cloud Sync group writeback (S1281); now in propagation-latency.csv. (topic: auth/propagation-latency)
- ConfigMgr AdminService's exact trigger for honouring an AD security-role group change (new logon vs SMS Provider cache) (QA2): left `[UNK]`, owned by `configmgr-rbac-auth.md`.
  Verification: in a disposable lab collection, add a test admin account to a ConfigMgr-RBAC-holding AD group, call AdminService immediately, then after a new Kerberos ticket, then after an SMS Provider service restart -> isolates the cache boundary. (topic: auth/configmgr-rbac-auth)
  - Partly resolved 2026-09-27: the Kerberos trigger is DOC (new TGT at lock, sign-out or expiry; S-ffrzumip); the SMS Provider cache is undocumented (DER absence); lab check stays. (topic: auth/configmgr-rbac-auth)
- Cloud Sync's exact documented sync-interval ceiling (this agent found only secondary/community figures of ~2 minutes / 10-20 minutes; no primary Learn citation was fetched due to a wrong guessed file path in MicrosoftDocs/entra-docs for the Cloud Sync FAQ page). Tried: direct raw-GitHub path guess (failed), GitHub tree search for "cloud-sync"+"faq" (no match), general web search (secondary sources only). 3 attempts, stopped per budget rule. (topic: entra/connect-and-cloud-sync)
  - Resolved 2026-09-27 (noted from the auth wave): the Cloud Sync FAQ (S1280) says users and groups approximately every 10 to 20 minutes, while What is Cloud Sync (S-2vza23mx) says every two minutes; Restart sync forces a run (S-h6idpd4a). Recorded in _conflicts.md under auth/propagation-latency. (topic: entra/connect-and-cloud-sync)
- Kerberoasting detection detail (event 4769 ticket-encryption-type field values 0x12/0x17) is stated only from secondary sources in this agent's research; no primary Microsoft Learn/Support page was fetched and cited for it (see threats.csv note). Left without a DOC-tagged source rather than mis-cited. (topic: auth/kerberos)
  - Resolved 2026-09-27: event 4769 page (S-7bjorbzz: 0x11/0x12 AES, 0x17 RC4-HMAC; monitor types other than 0x11 and 0x12) and Microsoft's Kerberoasting guidance (S-ffangyfp) with Defender alert 2410 (S-6ca4b7bg). (topic: auth/kerberos)

### Added at merge

- Verification: add a test account to an AD group, then `klist tgt` renew (not purge) and `whoami /groups` + an AdminService call → proves whether a TGT renewal refreshes PAC group SIDs (bounds AD group-change latency: renewal interval vs. new logon). (topic: auth/propagation-latency)
  - Resolved 2026-09-27 from documentation: the TGS copies the TGT's PAC into service tickets (MS-KILE, S-ltkr37vz) and renewal leaves ticket fields other than the times and session key unchanged (RFC 4120, S-r6vi3iik), so renewal does not refresh global/universal group SIDs; domain-local groups are added per service ticket (S-v5wjmc3h). (topic: auth/propagation-latency)
- Verification: from a Windows 11 24H2 client, call the AdminService by FQDN and by short name / IP, with `klist` before and after → proves Kerberos-only behaviour since 2509 and what error a non-FQDN call returns. (topic: auth/kerberos)
  - Partly resolved 2026-09-27: Windows does not try Kerberos for an IP host name and falls back to NTLM (S-5yckwasl); short-name behaviour still needs the lab. (topic: auth/kerberos)
- Verification: put a lab engineer account in Protected Users; run the `client` flows (AdminService, SQL, Graph via WAM) for >4 h → proves the 4-hour non-renewable TGT effect and any NTLM-dependent leg. (topic: auth/kerberos)
  - Partly resolved 2026-09-27: a Protected Users admin can run the ConfigMgr console for only 4 hours at a time (S-iqal4gqk); the AdminService, SQL and WAM legs still need the lab. (topic: auth/kerberos)
- **GitLab account block and non-PAT credentials.** The moderate-users doc (S-dhnetmt7) says a blocked user cannot sign in or access repositories and a deactivated user cannot use the API, and S1377 covers PAT auto-revocation only for Enterprise users; neither states what a block does to CI/CD job tokens, runner authentication tokens (`glrt-`) or open web sessions. Tried 2026-09-27: moderate_users.md and personal_access_tokens.md at pinned commits. (topic: auth/revocation)
- **Windows cache lifetime of DPAPI-NG group keys.** MS-GKDI (S-53ajdzoj) says clients SHOULD cache group keys per domain and security descriptor but gives no lifetime, and no page covers a deleted group. Verification: remove a user from the SID= group, then call NCryptUnprotectSecret on the same machine without and after a reboot. (topic: auth/key-management-options)
  - Tried 2026-09-28, still open: MS-GKDI gives only the SHOULD-cache rule; no page states a lifetime. Needs a lab measurement or a protocol clarification. (topic: auth/key-management-options)

## dsc

- **Windows-host execution not done.** Q20 behaviour (Service/FirewallRuleList native what-if; elevation check in what-if) is from code and manifests (S105, S114, S138, S139). Tried: macOS arm64 binaries (S116/S117), which do not include Windows resources. Needs a Windows 11 lab run. [UNK] (topic: dsc/what-if)
  - Still open 2026-09-28: needs a Windows host run of dsc 3.3.0; not answerable by web research. (topic: dsc/what-if)
- **What-if for group resources and adapters in a config.** The "error (pretest, no what-if)" classification for Microsoft.DSC/Group, Assertion, Include and the PowerShell adapters is derived from their manifest flags plus `invoke_set` (S105). Not run. [UNK] (topic: dsc/what-if)
  - Still open 2026-09-28: needs a lab run; the source-based classification stands. (topic: dsc/what-if)
- **MCP `what_if` on 3.3.0 ignored at runtime.** The conclusion is from source (no field, no `deny_unknown_fields`; S108) and binary strings (S114). An MCP stdio call was not captured in this session. [DER only] (topic: dsc/mcp-server)
  - Still open 2026-09-28: runtime confirmation needs a lab MCP session against dsc 3.3.0. (topic: dsc/mcp-server)
- **Official directives documentation.** No Learn or repo doc page for `directives` was found. Tried: MicrosoftDocs/PowerShell-Docs-DSC `dsc/docs-conceptual/dsc-3.0/reference/schemas/config/document.md` (S145), repo `docs/reference/schemas/config/*.md` on release/v3.3, and a grep of all repo docs for "directives". Only code and tests document it. (topic: dsc/schemas)
  - Tried 2026-09-28, still none: Learn has no dsc-3.x page for `directives`; the facts rest on the schema and CLI help. (topic: dsc/schemas)
- **Learn docs lag behind 3.2/3.3.** The Learn CLI pages (dsc-3.0 moniker) are dated 2025; there are no pages for `function`, `server`/`mcp`, directives, `secret()` or settings/policy. Facts come from code at the pinned commits. (topic: dsc/cli-reference)
  - Re-checked 2026-09-28: still true of the Learn CLI pages; facts rest on the release binaries and repo docs. (topic: dsc/cli-reference)
- **Trace leakage at `debug` level for adapters.** Tested only with `Microsoft.DSC.Debug/Echo`. Adapter paths (PowerShell) were not tested. (topic: dsc/secrets)
  - Still open 2026-09-28: needs a lab run with a PowerShell adapter resource. (topic: dsc/secrets)
- **Generated schemas and help text** (`schemas/generated-*`, `cli/help-*.txt`, `functions-3.3.0.csv`) are outputs of running the release binaries (sources S116/S117 = the tarballs). They cannot be re-downloaded byte-for-byte from a URL. `fetch.py --verify` should verify the tarball hash only. (topic: dsc/schemas)
  - Closed 2026-09-28: a provenance note (outputs of running the release binaries), not a knowledge gap. (topic: dsc/schemas)

## ident

- Q9 explicit equality "Entra deviceId == AD objectGUID": searched entra-docs (`objectguid` + device id), graph docs-contrib v1.0, memdocs, windowsserverdocs, SupportArticles (entra, mem). Found mapping statements only (S549, S550). Status UNK for explicit equality and for the AD FS-only path. (topic: entra/hybrid-deviceid-objectguid)
  - Tried 2026-09-27, still open: Learn search (Connect design concepts sourceAnchor, attributes synchronized, hybrid join manual configuration claims, device registration how it works, device disappearance) repeats the objectGUID-deviceID mapping for synced devices only; no statement covers the AD FS-only path. Recorded as DER. (topic: entra/hybrid-deviceid-objectguid)
- objectGUID vs deviceId string/byte-order comparison rules: not found in win32 ADSchema a-objectguid.md, search-filter-syntax.md, entra-docs. UNK. (topic: entra/hybrid-deviceid-objectguid)
  - Tried 2026-09-27, still open: same searches; no encoding rule found. Recorded as DER with a lab check. (topic: entra/hybrid-deviceid-objectguid)
- Q10 Autopilot `id` vs ZTDId: searched memdocs (all), entra-docs, graph docs-contrib v1.0 for `ztdid`; no statement linking them. UNK. (topic: autopilot/device-identity)
  - Tried 2026-09-27, still open: Graph v1.0 and beta windowsAutopilotDeviceIdentity pages at microsoft-graph-docs-contrib 4ad99fd3 (id = 'The GUID for the object'), Learn search (Autopilot device groups, CA device filters, known issues, dynamic membership rules) name ZTDId only in physicalIds. The article records the absence as DER. Verification: compare GET windowsAutopilotDeviceIdentities/{id} with the Entra device's physicalIds on a lab device. (topic: autopilot/device-identity)
- Throttling limit for `windowsAutopilotDeviceIdentity`: not listed in any `includes/throttling-intune-*.md` in docs-contrib (grep of all includes). UNK. (topic: graph/throttling)
  - Resolved 2026-09-28 as a documented absence: the live throttling page (S-ma3wej5u, updated 2026-09-17) lists only Autopilot events, policy status details and deployment-profile policy set items; recorded as DER. (topic: graph/throttling)
- Intune RBAC needed for delegated Graph calls on managedDevices / Autopilot identities: API pages S518-S523 state only Graph permissions. Not searched further in memdocs (budget). UNK. (topic: graph/permissions)
  - Resolved 2026-09-28: Intune's Graph-access guide (S-ilovbr2g) gives the Intune Service Administrator and licence requirement; per-call RBAC permissions are still not on the API pages. (topic: graph/permissions)
- `dsregcmd /status` Tenant details fields: documented only through sample output on S544; not extracted. (topic: entra/dsregcmd)
  - Resolved 2026-09-27: the section's visibility rule, MDM URL note and sample field names are now DOC in entra/dsregcmd.md (S544); the page still has no per-field descriptions, so the CSV stays without them. (topic: entra/dsregcmd)
- `msDS-LogonTimeSyncInterval` default value when unset: not on schema page S563. Not searched further (budget). UNK. (topic: ad/computer-attributes)
  - Resolved 2026-09-28: the lastLogonTimestamp schema page (S-7365hqko: 14 days minus a random percentage of 5 days) and KB 2679653 (S-gv5dk5hs: default updates only at 9 to 14 days) give the effective default. (topic: ad/computer-attributes)
- managedDevice beta List/Delete API pages don't exist under `intune-devices-manageddevice-*` in beta (only Get); beta permissions for list/delete not captured. (topic: graph/permissions)
  - Tried 2026-09-28, unchanged: the v1.0 pages carry the permissions; no beta list/delete pages were found. (topic: graph/permissions)

## infra

- **gMSA scheduled task registration syntax** (LogonType, `-UserId DOMAIN\name$`): not found in windowsserverdocs gMSA pages (S400-S403), win32 TaskSchd `principal-logontype.md` (S404, which only lists LocalSystem/LocalService/NetworkService for SERVICE_ACCOUNT), or `New-ScheduledTaskPrincipal` (S405). There was also a repo-wide grep for gmsa+scheduled task across all clones. 3 attempts; stopped. [UNK] (topic: windows/gmsa)
  - Resolved 2026-09-28: Microsoft's Engage Center guide (S-sav2ixtw, found with the Learn code-sample search) sets a task's principal with `New-ScheduledTaskPrincipal -UserId <DOMAIN>\<gmsa>$ -LogonType Password`; recorded in `windows/gmsa.md`. (topic: windows/gmsa)
- **GitLab Runner as gMSA, official statement**: runner docs install/windows.md, advanced-configuration.md, shells, faq, security (S406-S408), a grep of all runner `docs/` for "gmsa"/"managed service", and the issue API. Only COMMUNITY issue text was found (S414); issue 30963 is open. Issue notes need a login (HTTP 401), so they weren't read. [UNK for official support] (topic: windows/gitlab-runner-windows)
  - Tried 2026-09-28, still open: the runner `docs/` at main 0e3fe7d3 (S-kw4zko43) has no gMSA or managed-service-account mention; only the COMMUNITY issue text (S414) says it works. Needs GitLab to document it; not answerable by web research. (topic: windows/gitlab-runner-windows)
- **`safe_directory_checkout` documentation**: the option is in the runner source (S410), but a grep of runner `docs/` at 49138a48 finds no mention. [UNK in docs] (topic: windows/gitlab-runner-windows)
  - Resolved 2026-09-28 as a documented absence: still in no file of the runner `docs/` at main 0e3fe7d3 (S-kw4zko43) nor on the published advanced-configuration page; the per-executor defaults are now read from source (CODE). (topic: windows/gitlab-runner-windows)
- **mssql/server digest pinning policy**: containers/deploy.md, quickstart-install-docker.md and environment-variables.md (S473, S474, S477) have no `@sha256` or digest guidance. MCR tag list saved (S478). [UNK] (topic: sqlserver/linux-container)
  - Resolved 2026-09-28 as a documented absence: the three pages at sql-docs live 2e21fb07 still have no digest guidance and a GitHub code search finds no `mssql/server@` reference in the repository; recorded as DER. (topic: sqlserver/linux-container)
- **S478 artifact hash is not stable**: `tags/list` is a live endpoint, so `fetch.py --verify` will report a mismatch once new tags appear. (topic: sqlserver/linux-container)
  - Closed 2026-09-28: a property of the source, not missing knowledge. The saved copy stays pinned by its sha256 (`fetch.py --offline` passes); a `--verify` mismatch on this live endpoint means new tags, and the article says so. (topic: sqlserver/linux-container)
- **Ownership chaining vs DENY for the audit table**: not read (sql-docs ownership-chains page not checked). [UNK] (topic: sqlserver/insert-only-audit)
  - Resolved 2026-09-28: the current Ownership Chains page is gone (404); the archived 2008 R2 page (S-qkecle6c) states that permissions on a same-owner referenced object are not evaluated, and the current tutorial (S-yjcvd3to) shows access through a procedure; the DENY consequence is recorded as DER. (topic: sqlserver/insert-only-audit)
- **Free-tier author self-approval**: approvals `_index.md` (S441) says Free approvals are optional. Whether a Free author can approve their own MR is not stated on the pages read. [UNK] (topic: gitlab/mr-approvals)
  - Tried 2026-09-28, still open: the approval settings that stop author approval are Premium settings; no Free-tier statement found. A test project on GitLab Free would settle it. (topic: gitlab/mr-approvals)

## later

- Power BI docs source repo: `MicrosoftDocs/powerbi-docs` and `MicrosoftDocs/data-integration` are not public (clone: "Repository not found"); learn pages point to private `powerbi-docs-pr`. Used throttled learn.microsoft.com HTML instead; no pinned raw URL possible for S900-S910 (only ms.date recorded).
  - Re-checked 2026-09-28: still not public; Power BI pages stay `quote` under the Learn terms.
- GPO backup on-disk layout (folder contents such as Backup.xml / gpreport.xml): not in the GroupPolicy cmdlet reference (S921); grep of MicrosoftDocs_windowsserverdocs, SupportArticles-docs, win32 clones for "bkupInfo.xml" / "gpreport.xml" found nothing. [UNK] (topic: gpo/gpo-export)
  - Tried 2026-09-27, still open: Learn search (Backup-GPO, IGPMGPO::Backup, Entra Domain Services GPO backup preview) describes backup contents (settings, GPO ID, ACLs) but not the folder layout; recorded as DER, with the IGPMGPO::Backup contents as DOC. (topic: gpo/gpo-export)
- DSC v3 GroupPolicyTemplate adapter: which released version first ships it is left to dsc/ (only the main-branch manifest was checked, S924). [UNK] (topic: gpo/dsc-group-policy-adapter)
  - Resolved 2026-09-27: the v3.3.0 release notes (S118) list the adapter (PR #1686), and the manifest exists at tag v3.3.0 (pinned in S-3yuoi2qa) but returns 404 at v3.3.0-rc.2, rc.1, preview.1 and preview.4 and v3.2.3. (topic: gpo/dsc-group-policy-adapter)
- `ansible.windows.win_dsc` check-mode support: the docs page as fetched shows no attributes table; not confirmed. [UNK] (topic: ansible/dsc3-module)
  - Resolved 2026-09-28: `win_dsc.ps1` at tag 3.8.0 (S-g5j4nkll) sets `supports_check_mode` and skips `Set` in check mode; recorded as CODE. (topic: ansible/dsc3-module)
- powerbi/configmgr-views.md depends on mecm/sql-views-compliance.md (other agent); that file did not exist at time of writing.
  - Resolved 2026-09-27: mecm/sql-views-compliance.md exists; the dependency is satisfied. (topic: mecm/sql-views-compliance)
  - Closed 2026-09-28: the article now also carries the Power BI Report Server integration facts (S-djtnspkg) and moves to complete. (topic: powerbi/configmgr-views)

## mcp

- Claude Code form-mode elicitation over 2026-07-28 (MRTR) connections: searched code.claude.com/docs/en/mcp.md, hooks.md, env-vars.md, changelog.md (grep elicit/2026-07-28/InputRequired). Only URL-mode-on-2026 entry (2.1.281) found. UNK. (topic: claude/elicitation)
  - Resolved 2026-09-28: the MCP page now says Claude Code declares `elicitation: {form: {}, url: {}}` on 2026-07-28 connections (S740); MRTR as the transport is DER from the revision (S710). Non-interactive `-p` without a hook stays undocumented (DER absence). (topic: claude/elicitation)
- Claude Code use of MCP tool annotations (readOnlyHint/destructiveHint) for permission decisions: searched mcp.md, permissions.md, changelog.md. Only "annotations display in /mcp" (1.0.44). UNK. (topic: claude/permissions-mcp)
  - Resolved 2026-09-28: the Agent SDK custom-tools page (S-vrff4evh) documents `readOnlyHint` as the parallel-execution switch and `destructiveHint` as informational; the permissions and MCP pages name only `anthropic/requiresUserInteraction` (DER absence). (topic: claude/permissions-mcp)
- Claude Code support for the Tasks extension (io.modelcontextprotocol/tasks): searched mcp.md, changelog.md, MCP client-matrix.mdx (no Tasks column). UNK. (topic: mcp/tasks-extension)
  - Tried 2026-09-28, recorded as a documented absence: the MCP page lists only the elicitation capabilities Claude Code declares on 2026-07-28 connections, and the changelog has no Tasks entry. A positive statement needs Anthropic docs or a protocol trace. (topic: mcp/tasks-extension)
- OWASP LLM Top 10 2026 item ids/titles: tried genai.owasp.org/llm-top-10/ (2025 list only), /resource/owasp-genai-llm-top-10-2026/ (no list in HTML), 2026-09-01 announcement (no list in HTML). Stopped after 3 attempts; list is in a PDF not fetched. (topic: standards/owasp)
  - Resolved 2026-09-27: the resource page's download link (genai.owasp.org/download/56857/) serves the PDF; LLM01:2026-LLM10:2026 and its CC BY-SA 4.0 licence are now in owasp.md and owasp.csv (S-mq77ii5m). (topic: standards/owasp)
- OWASP Agentic 2026 resource page HTML does not carry ASI titles; titles taken from the OWASP GenAI announcement blog (S762). Licence of genai.owasp.org content not verified on page. (topic: standards/owasp)
  - Partly resolved 2026-09-27: the genai.owasp.org footer says all content is CC BY-SA 4.0 unless otherwise specified (read on S764), and the 2026 LLM PDF states CC BY-SA 4.0; the ASI titles still come from the announcement (S762). (topic: standards/owasp)
- OWASP MCP Top 10 index.md fetched from `main` (not sha-pinned); commit sha not recorded. (topic: standards/owasp)
  - Resolved 2026-09-27: pinned at commit 165fe0f78ef1 (S-s3hkw2h4, main HEAD on 2026-09-27); S760 now superseded, citations re-pointed. (topic: standards/owasp)
- privacy.claude.com / support.claude.com commercial-terms pages not fetched (time budget); retention facts come from code.claude.com data-usage/ZDR and platform.claude.com API retention pages. (topic: claude/data-retention)
  - Resolved 2026-09-28: the Privacy Center consumer, commercial and ZDR-scope articles read directly (S-6lfftobj, S-nqy6npap, S-qrxvz4ph); facts added. (topic: claude/data-retention)
- MCP spec repo is a shallow clone: git history for 2026-07-28 release date not available; release date inferred only from the version string and SDK v2.0.0 release date (2026-07-28). (topic: mcp/spec-overview)
  - Resolved 2026-09-28: the repository's GitHub releases (S-q6ob42dw) show `2026-07-28` published 2026-07-28 and the RC on 2026-05-29. (topic: mcp/spec-overview)
- Enterprise-Managed Authorization's stable date is not in `mcp/registry-and-extensions.md`: the ext-auth file at commit fb374c7d (S-hrri7kcy, added in the auth wave 2026-09-27) marks it Stable, promoted by PR #29 merged 2026-06-18. For the mcp wave to write up. (topic: mcp/registry-and-extensions)

## mecm1

- Minimum baseline evaluation interval (Q19): searched memdocs compliance/*, about-client-settings.md, develop/compliance/*, schedule token classes; SupportArticles-docs support/mem/configmgr (no compliance-settings troubleshooting articles). Not documented. (topic: mecm/baselines)
  - Tried 2026-09-27, still open: live Learn search (deploy/create/monitor baseline pages, about-client-settings, the Orchestrator Deploy Configuration Baseline activity) found no floor; the common-tasks walkthrough gives only a 7-day default (S-g5gii62f). The article records the absence as DER. Verification: in a lab console, try a 1-minute custom schedule on a baseline deployment and read the stored EvaluationSchedule token. (topic: mecm/baselines)
- CI script output size limit (Q19): searched memdocs (compliance, apps, client settings, develop) for "output", "size", "maximum"; SupportArticles-docs. Not documented. (topic: mecm/compliance-script-ci)
  - Tried 2026-09-27, still open: live Learn search and a re-grep of the memdocs archive (compliance, apps, client settings) found no output size limit for CI scripts. The article records the absence as DER. (topic: mecm/compliance-script-ci)
- Full column lists of compliance SQL views: SQL views docs (compliance-settings-views, status-alert-views, sql-server-views) give descriptions and join columns only. Column lists only available from sample queries and WMI classes. (topic: mecm/sql-views-compliance)
  - Not retried 2026-09-27: the views pages still describe joins only; the column lists would come from a lab site database (sp_columns on the views). (topic: mecm/sql-views-compliance)
- SQL view behind SMS_DCMDeploymentCompliantDetailsPerAsset: not in develop/reference/compliance or sqlviews docs. (topic: mecm/sql-views-compliance)
  - Tried 2026-09-27, still open: a re-grep of the memdocs archive finds the class only in the WMI reference (class page, error-status cross-links, TOC); no SQL view page names it. The article records the absence as DER. (topic: mecm/sql-views-compliance)
- Enumeration of CI setting data types (String, Integer, ... ) and a 32-bit/64-bit host option for script settings: not in create-custom-configuration-items doc or create-global-conditions doc; only "Floating point supports three decimals" is stated. (topic: mecm/compliance-script-ci)
  - Partly resolved 2026-09-27: the macOS CI page (S-lojuttbo) names Floating point, Boolean and Integer; no page gives the full list or a 32/64-bit host option for script settings. (topic: mecm/compliance-script-ci)
- Execution account of a CI script without "logged on user credentials": not stated. (topic: mecm/compliance-script-ci)
  - Tried 2026-09-27, still open: CI, global-conditions and client-settings pages re-read, Learn search for the local system account with compliance scripts; no account named. (topic: mecm/compliance-script-ci)
- Scope of Script Execution Timeout beyond compliance settings (app detection, global conditions): not stated. (topic: mecm/compliance-script-ci)
  - Tried 2026-09-27, still open: client-settings (Compliance settings group), create-applications and create-global-conditions re-read; only configuration items are named. (topic: mecm/compliance-script-ci)
- CCM log format: no formal spec; `type` values and time-bias semantics not defined (only examples in memdocs osd doc and SupportArticles state-messaging article). (topic: mecm/log-files)
  - Partly resolved 2026-09-27: the Windows PE peer cache page (S-3ed5gfct) shows a full line with time="14:24:33.329+420" and date="06-26-2015", so the value forms are now DOC by example (mecm/logging.md). The type values and the bias sign/unit remain undefined. (topic: mecm/logging)
- Collect client logs programmatic retrieval (WMI class / AdminService route for Support_*.zip): not documented. (topic: mecm/collect-client-logs)
  - Tried 2026-09-27, still open: re-grep of the memdocs archive for Support_ and diagnostic files (only Resource Explorer and client-notification pages), live Learn search; no WMI class, SQL view or AdminService route is tied to diagnostic files. The article records the absence as DER. (topic: mecm/collect-client-logs)
- learn.microsoft.com URLs were derived from repo paths (intune/configmgr/...) and not fetched; historic URL form was learn.microsoft.com/mem/configmgr/... . Raw pinned URLs in sources.csv are authoritative.
  - Closed 2026-09-28: the ConfigMgr sources were re-read at the census and in the mecm wave; a provenance note only.

## mecm2

- CMPivot `CcmLog()`, `WinEvent()` and per-entity columns. Tried: grep of the memdocs clone (4b5429df) for CcmLog/WinEvent (only examples found), cmpivot*.md, the tenant-attach cmpivot pages, and the cmpivot-samples include. Not documented. Only columns used in examples are recorded in mecm/cmpivot-entities.csv. (topic: mecm/cmpivot)
  - Tried 2026-09-27, still open: live Learn search (CMPivot overview, samples, changes, tenant-attach CMPivot) and a re-grep of the memdocs archive (4b5429df) show CcmLog only as a call form; no column list for CcmLog, WinEvent or the entities. The article records the absences as DER. Verification: run `CcmLog('Scripts',1h)` against a lab client (PL-LT-00123) and record the result header. (topic: mecm/cmpivot)
- InitiateClientOperation Type values (policy, HW inventory, app eval, SU eval). Tried: the SDK reference (develop/reference/protect/*clientoperation*), grep of memdocs, SupportArticles-docs and windows-powershell-docs for "client operation <n>", and the Learn Invoke-CMClientAction page (names only). Only 135/145 from log samples. (topic: mecm/client-notification)
  - Tried 2026-09-27, still open: live Learn search (SMS_ClientOperation, InitiateClientOperation, Get-CMClientOperation pages) and a GitHub code search; only community modules (e.g. ansible-collections/microsoft.mecm, SharpSCCM) carry numbers. The Invoke-CMClientAction page (S334, updated_at 2022-01-03) still lists ActionType names only, and its public source repo MicrosoftDocs/sccm-docs-powershell-ref is archived (CC BY 4.0) with no enum values. (topic: mecm/client-notification)
- InitiateClientOperationEx. Tried: grep of all clones (no hits) and a web search (only the older InitiateClientOperation pages and community posts). Not in the current SDK docs. (topic: mecm/client-notification)
  - Tried 2026-09-27, still open: the live SMS_ClientOperation methods table (updated_at 2026-08-28) has no Ex method, a Learn search returns only InitiateClientOperation, and a GitHub code search finds it only in community tools (SharpSCCM, MECM7). The article now records the absence as DER. (topic: mecm/client-notification)
- Invoke-CMClientAction ActionType numeric values. The Learn page lists names only. The sccm-docs-powershell repo is private. (topic: mecm/client-notification)
  - Tried 2026-09-27, still open: the live page still gives names only; the page's feedback repo MicrosoftDocs/sccm-docs-powershell-ref is public but archived (2026-05-12) and holds the same Markdown, so the numbers exist only in the module's compiled enum. (topic: mecm/client-notification)
- AdminService per-route support through CMG and delegated tokens. Tried: set-up.md, usage.md, faq.yml, azure-services-wizard.md, whats-new 2207, and the Microsoft TokenSample.ps1. None lists routes. Fetching the other configmgr-hub samples was declined this session and not retried. (topic: mecm/adminservice)
  - Tried 2026-09-27, still open: live set-up (updated_at 2026-08-28) and FAQ pages still describe only the CMG endpoint form and the SMS Provider checkbox, with no per-route list; a GitHub code search of the microsoft and MicrosoftDocs orgs for AdminService samples found none. (topic: mecm/adminservice)
- AdminService v1.0 Run Script action. Tried: the adminservice docs folder, a grep of all memdocs for v1.0 routes, and Learn Invoke-CMScript. Only a community sample was found (search result, not fetched). (topic: mecm/adminservice)
  - Tried 2026-09-27, still open: Learn search for AdminService.RunScript / ScriptResult returns only Invoke-CMScript and Intune Graph script cmdlets; GitHub code search in the microsoft and MicrosoftDocs orgs finds no RunScript route. Only community tools use it (the article keeps them as COMMUNITY S350). (topic: mecm/adminservice)
- Run Scripts maximum script size. Tried: create-deploy-scripts.md, learn-script-security.md, and a grep for script size/length. Not documented. (topic: mecm/run-scripts)
  - Tried 2026-09-27, still open: live create-deploy-scripts (updated_at 2026-08-31) Limitations section and Learn search; only the 4 KB output truncation is stated. The article records the absence as DER. (topic: mecm/run-scripts)
- RBAC bit positions for Notify Resource, Run Script and Run CMPivot. Tried: SMS_ARoleOperation, SMS_RbacSecuredObject, and the security views doc. Not listed. (topic: mecm/rbac)
  - Tried 2026-09-27, still open: Learn search (GrantedOperations, the three permission names) returns only console and CMPivot permission text; the article records the absence as DER. (topic: mecm/rbac)
- Full built-in role × permission matrix. The docs point to the RBA Viewer tool (a live site) and give no static table. (topic: mecm/rbac)
  - Tried 2026-09-27, still open: no static matrix on Learn; the kb keeps the documented rows in mecm/rbac-permissions.csv. (topic: mecm/rbac)
- Response schemas of AdminService.RunCMPivot / CMPivotResult. Not documented, and there is no Swagger document (S305). (topic: mecm/adminservice)
  - Tried 2026-09-27, still open: the FAQ still says no OpenAPI (Swagger) document is published, and a GitHub code search of the microsoft and MicrosoftDocs orgs for RunCMPivot finds nothing. (topic: mecm/adminservice)
- Learn URL invoke-cmclientnotification returned 404. It is an alias of Invoke-CMClientAction (S334). (topic: mecm/client-notification)
  - Re-checked 2026-09-27: the URL still returns 404; nothing to change, the alias fact stays on S334. (topic: mecm/client-notification)

## ops

- **Q11: Defender aadDeviceId for hybrid join.** No official statement found. Tried: learn defender-endpoint/api/machine, get-machines and get-machine-by-id; defender-xdr/advanced-hunting-deviceinfo-table; defender-endpoint/machines-view-overview; exposed-apis-odata-samples; microsoft-graph-docs-contrib security-deviceevidence; the microsoft-365-docs clone (it has no defender-endpoint content because that moved to the private defender-docs repo); 2 WebSearch queries. Stopped after 3+ attempts. (topic: defender/machine-resource)
  - Tried 2026-09-27, still open: Learn searches (Machine resource, device inventory, device entity page, Entra device identity pages) and a web search found no hybrid statement; the article now records the absence as DER and a `computerDnsName` fallback. Verification: on a hybrid joined lab device, compare `GET /api/machines/{id}` `aadDeviceId` with `dsregcmd /status` DeviceId. (topic: defender/machine-resource)
- **DeviceInfo JoinType values.** The advanced-hunting-deviceinfo-table page does not list them. (topic: defender/advanced-hunting)
  - Tried 2026-09-27, still open: Learn page and code-sample search, web search, GitHub code search; Microsoft's Azure-Sentinel hunting queries (S-axmpfgwf) match JoinType with `has_any ("Hybrid", "Azure AD", "Entra")`, so no exact value set is published. (topic: defender/machine-resource)
- **Remediations script size limit and timeout.** Not in deploy-remediations.md or management-extension-windows.md (memdocs). The 200 KB and 30-minute figures cover platform scripts only (run-powershell-scripts-windows.md). (topic: intune/remediations)
  - Tried 2026-09-27, still open: live Remediations page (script requirements), IME page and the Win32 troubleshooting page (HealthScripts.log covers remediations, custom compliance scripts and on-demand runs) name no size or timeout; Learn search for HealthScripts timeouts found none. The article records the absence as DER. (topic: intune/remediations)
- **Full `-area` list for MDMDiagnosticsTool.** learn windows/client-management/diagnose-mdm-failures-in-windows-10 shows only DeviceEnrollment, DeviceProvisioning and Autopilot. memdocs and SupportArticles add TPM. No complete list found. The Windows client-management repo was not cloned. (topic: intune/mdmdiagnosticstool)
  - Tried 2026-09-27, still open: Learn searches (mdm-collect-logs, DiagnosticLog CSP, Autopilot known issues and device association FAQ, co-management Autopilot enrollment, a registry-area query) show only DeviceEnrollment, DeviceProvisioning, Autopilot and TPM. The article records the absence as DER. Verification: run `mdmdiagnosticstool.exe /?` on a lab device (PL-LT-00123). (topic: intune/mdmdiagnosticstool)
- **Co-management workload flags (CoManagementFlags).** A grep of the memdocs and SupportArticles clones found nothing. (topic: intune/co-management)
  - Partly resolved 2026-09-27: the SupportArticles co-management troubleshooting page (S-wnwinphx) shows log samples testing workloadFlags 7 against workload 2 (compliance), 4 (resource access) and 16 (Windows Update for Business); the other workloads' bits are still undocumented. (topic: intune/co-management)
- **Channel `Microsoft-Windows-DeviceManagement-Enterprise-Diagnostics-Provider/Operational`.** Not found in the memdocs, SupportArticles, entra or windowsserverdocs clones. (topic: logs/sources)
  - Resolved 2026-09-28: the Windows declared configuration protocol page (S-77gkdi7q) logs processing errors to `DeviceManagement-Enterprise-Diagnostics-Provider\Operational` and `\Admin`; added to `logs/sources.csv`. (topic: logs/sources)
- **Exact channel string for ModernDeployment-Diagnostics-Provider/Autopilot.** Only the Event Viewer path is documented (autopilot/troubleshooting-faq.yml). The channel name in this kb is derived (DER). (topic: logs/sources)
  - Narrowed 2026-09-28: the Autopilot device-registration troubleshooting article (S-6lmczs32) collects `microsoft-windows-moderndeployment-diagnostics-provider-autopilot.evtx`, which matches the derived channel name; no page spells the channel string itself, so it stays DER. (topic: logs/sources)
- **ConfigMgr-specific Windows event channels.** None are documented in the clones. ConfigMgr writes log files instead (see mecm/log-files.csv).
  - Tried 2026-09-28, still none documented: ConfigMgr logs to files (`mecm/log-files.csv`); recorded as an absence.
- **Query length limit for multi-device query.** Not stated. (topic: intune/device-query)
  - Tried 2026-09-27, still open: the live multi-device page (updated_at 2026-09-02) Known limitations list joins, records, rate and export limits but no query length; the 2,048-character limit is stated only for single-device query. (topic: intune/device-query)
- **ECS base fields (@timestamp, message).** base.yml was not fetched. (topic: logs/ecs-log-fields)
  - Resolved 2026-09-28: `schemas/base.yml` and `schemas/event.yml` read at the same commit (S-okri4cz3, S-gho2sfjp). (topic: logs/ecs-log-fields)
- **Licence of the Defender learn pages.** The MicrosoftDocs/defender-docs repo is private, so the licence could not be checked. That content is summarised only.
  - Re-checked 2026-09-28: `MicrosoftDocs/defender-docs` still returns 404, so Defender pages stay `quote`.

## priorart

### mcp-microsoft-endpoint-mgmt
- Tried: `microsoft/mcp` GitHub repository + its `servers/` directory listing (found: only
  Azure.Mcp.Server, Fabric.Mcp.Server, Template.Mcp.Server, no ConfigMgr/Intune/Graph-device/Entra
  server). Community MCP servers for these Microsoft endpoint-management surfaces were not searched
  beyond this — stopped after confirming the official catalog has no match, within session budget.
  Recorded as `status: partial`, not `unknown`, because the official-catalog absence is itself a
  confirmed fact. (topic: prior-art/mcp-microsoft-endpoint-mgmt)
  - Resolved 2026-09-28: `servers/` re-read (still the three entries); the official MCP Registry API (S-eiluqiui) searched for intune, configmgr, sccm, endpoint, entra, microsoft graph and defender: no ConfigMgr or Intune device-management server; Microsoft's read-only Entra MCP Server for Enterprise (preview, S2190) recorded as the nearest official server. (topic: prior-art/mcp-microsoft-endpoint-mgmt)

### device-identity-correlation
- Tried: GLPI, Snipe-IT, NetBox, Fleet repository metadata (GitHub API `repos/<org>/<repo>` only).
  ServiceNow CMDB's Identification and Reconciliation Engine (IRE) public docs — the brief's named
  reference for merge-key/precedence/duplicate-handling facts — were not fetched: ServiceNow's docs
  site is not in this agent's official-source allowlist and was not fetched via HTTP this session.
  Wazuh was fetched for repository metadata only (language C++, licence unresolved by GitHub API);
  its device-identity-correlation mechanism specifically (agent/manager enrollment, not asset CMDB)
  was not documented in depth — stopped after repo-metadata level, 1 attempt, given Wazuh is a weaker
  fit for "device identity correlation" than the CMDB-style tools already covered. (topic: prior-art/device-identity-correlation)
  - Resolved 2026-09-28: GLPI's import-and-link rules (Help Center, S-awv4qk3v) and Fleet's `osquery_host_identifier` (docs at a pinned commit, S-53yzqgkc) are now DOC; ServiceNow's IRE pages were not fetched (the comparison uses the kb's own description of it) and Wazuh stays at metadata level. (topic: prior-art/device-identity-correlation)

### drift-detection
- Tried: Puppet, Chef InSpec, Microsoft365DSC repository metadata + brief README passages (Puppet
  README, general project description text). Ansible check-mode facts were stated from general
  project knowledge of `ansible-core` docs structure but not independently re-fetched from
  docs.ansible.com this session (docs.ansible.com is on the allowed list but was not called — time
  budget); Azure Machine Configuration, Intune tenant configuration management, and osquery/Fleet
  policies (all named in the brief for this mechanism) were not fetched at all this session — no
  attempts made, explicit scope cut to stay near the ~40-fetch budget. (topic: prior-art/drift-detection)
  - Resolved 2026-09-28: Ansible check mode is DOC (S-e4iemhin, earlier pass); Microsoft365DSC's drift-only call is `Test-DscConfiguration` (M365DSC docs S-qlnd73w2, Learn S-fylt7wwn) and `New-M365DSCDeltaReport` compares files (S-c6kla37l). Machine Configuration and the Graph TCM APIs are covered in `windows/azure-arc-servers.md` and `graph/tcm-apis.md`; osquery/Fleet policies were not added. (topic: prior-art/drift-detection)

### log-collection-normalization
- Tried: OpenTelemetry Collector and Fluent Bit repository metadata only (no docs-site fetch for
  either project's receiver/parser plugin catalog, so "no built-in CMTrace parser" is stated from
  repository-description-level evidence, not an exhaustive plugin-list check). NXLog CE: no public
  GitHub repository exists to fetch from; nxlog.co was not fetched (not on this agent's official-
  source allowlist as configured in this session). No CMTrace-specific open-source parser project
  (e.g. a standalone CMTrace log parser library) was searched for independently. (topic: prior-art/log-collection-normalization)
  - Resolved 2026-09-28: the full, untruncated repository trees at pinned commits (S-unpitz6t, S-mblcg5ds) list Windows Event Log inputs and generic parsers and no path mentioning CMTrace; NXLog CE's reference manual v3.2 (S-d7pjd3ma) documents `im_msvistalog` and no CMTrace parser. No standalone CMTrace parser library was searched. (topic: prior-art/log-collection-normalization)

### secret-vault-encryption
- Tried: sops, age, Vault, cryptography, git-crypt repository metadata + one README/doc page each.
  Vault's licence is recorded as BUSL-1.1 from general knowledge of Vault's 2023 licence change
  (GitHub API itself only reports "NOASSERTION," it does not identify BUSL-1.1) — this fact carries a
  weaker evidentiary basis than the other DOC-tagged facts in that file and should be reconfirmed
  against Vault's own LICENSE file if precision matters. (topic: prior-art/secret-vault-encryption)
  - Resolved 2026-09-28: Vault's BUSL-1.1 is read from its LICENSE pinned at a commit (S-b43o3ma3: Licensed Work Vault 1.15.0 or later, Additional Use Grant, Change License MPL 2.0 after four years). (topic: prior-art/secret-vault-encryption)

### tiered-approval-ops
- Tried: Rundeck, StackStorm, Teleport, Ansible AWX repository metadata only. None of the four
  projects' README/docs content (ACL policy syntax, RBAC role definitions, Access Request workflow
  steps, AWX approval-node configuration) was fetched — repository-description-level facts only, by
  design given the ~40-fetch budget for this agent. (topic: prior-art/tiered-approval-ops)
  - Resolved 2026-09-28: Rundeck and StackStorm RBAC were DOC already (S-p6qlnhra, S-nnzeoxyh); Teleport Access Requests (S-bmjfyz5c, S-uh67gxyw) and AWX approval nodes and RBAC (S-smmzgplg, S-askzkdnt) are now read from docs pinned at commits. (topic: prior-art/tiered-approval-ops)

## privacy

- Next Presidio release date / version: not announced. Tried GitHub releases API (S801), PyPI JSON (S802), CHANGELOG `[unreleased]` (S800). (topic: privacy/presidio)
  - Re-checked 2026-09-28: PyPI still shows presidio-analyzer 2.2.364 (2026-07-22); no next release announced. (topic: privacy/presidio)
- spaCy `en_core_web_lg` training-data source licences (`LICENSES_SOURCES`): not read. The fetch of https://huggingface.co/spacy/en_core_web_lg/raw/557bf75.../LICENSES_SOURCES was declined during the session. spacy.io/models/en (S852) renders details client-side, so the static HTML has no licence text. The model licence itself (MIT) is confirmed by S850 and S851. (topic: privacy/spacy-model-licence)
  - Resolved 2026-09-27: LICENSES_SOURCES read at sha 557bf75 (S-kujx3zxn): OntoNotes 5 commercial (licensed by Explosion), ClearNLP citation only, WordNet 3.0 License, Explosion Vectors CC0. (topic: privacy/spacy-model-licence)
- nvidia/gliner-PII full label list (55+): not in the model card (S860) or the HF API (S859). The dataset card and NVIDIA licence text were not fetched (the nvidia.com licence is not on an allowed host). (topic: privacy/gliner-models)
  - Resolved 2026-09-27: the NVIDIA Open Model License (last modified 2025-10-24) was read directly (S-zw4luelo). The label list stays unpublished: the Nemotron-PII dataset card (S-dcu4qhyp) says only 55+ categories with examples; distinct labels could be counted from its parquet `spans` column, which needs a parquet reader. (topic: privacy/gliner-models)
- EDPB Guidelines 01/2025 final (post-consultation) version: not found. Tried the consultation page (S872), the news item (S873), the topic page (S874), and two WebSearch queries restricted to edpb.europa.eu. Only the "version for public consultation" exists. (topic: privacy/gdpr-pseudonymisation)
  - Tried 2026-09-27, still open: consultation page (S872, still only the January 2025 PDFs), EDPB guidelines listing (01/2025 shown under closed consultations), topic page (S874) and the 2026-07-08 news (S-eickk3hp: separate anonymisation guidelines adopted, consultation to 2026-10-30). The article records the absence as DER. (topic: privacy/gdpr-pseudonymisation)
- CJEU C-413/23 P full judgment text: not fetched. Used press release 107/25 (S875) only. (topic: privacy/gdpr-pseudonymisation)
  - Resolved 2026-09-27: the full judgment was read on EUR-Lex (S-2s2xlwgf; operative part, paras 80-86 and 111). (topic: privacy/gdpr-pseudonymisation)
- `surrogate_ahds` operator behaviour over REST: not checked. (topic: privacy/presidio-operators-deanonymize)
  - Still open 2026-09-28: needs a running presidio-anonymizer container with the AHDS operator configured; the docs describe only the Python API. (topic: privacy/presidio-operators-deanonymize)

## reuse

- Exact commit SHAs for the 5 LICENSE fetches (hashicorp/vault, pyca/cryptography, inspec/inspec,
  fleetdm/fleet, ansible/awx) were not pinned: `raw.githubusercontent.com/.../HEAD/...` was used and
  the GitHub API `commits/HEAD` calls to resolve a sha were rate-limited (403) after ~30 total fetches
  across all kb agents sharing the throttle. URLs are recorded as `HEAD` with `retrieved_utc` as the
  pin instead. Tried: `api.github.com/repos/<org>/<repo>/commits/HEAD` for all five, all 403'd once.
  - Resolved 2026-09-28: all five pinned at commits (S-b43o3ma3, S-6onf7joh, S-tvp7vziq, S-y47upe33, S-lscdap53); the HEAD rows S1102-S1106 point to them through `superseded_by` and the citations were re-pointed. (topic: reuse/secret-vault-encryption)
- LLM Guard's `Vault` class was assessed from the prior-art agent's summary of its own docs (S1006),
  not by reading `llm_guard`'s source directly this session (budget); the "port the class shape" logic
  verdict should be re-verified against the actual `vault.py` source before any code is written. (topic: reuse/pseudonymization-tokenization)
  - Resolved 2026-09-28: `llm_guard/vault.py` read at a pinned commit (S-7t5ulcii): an in-memory tuple list with no persistence, expiry or encryption. (topic: reuse/pseudonymization-tokenization)
- Teleport's "Access Requests" approval-workflow mechanics and AWX's workflow-approval-node mechanics
  were not fetched this session (inherited gap from prior-art); the `no` verdict here rests on licence
  (AGPL-3.0) and deployment-model (always-on service) grounds, which do not depend on those mechanics,
  so this gap does not change the verdict but is noted for completeness. (topic: reuse/tiered-approval-ops)
  - Resolved 2026-09-28: both read from repository docs at pinned commits (S-bmjfyz5c, S-uh67gxyw, S-smmzgplg); the verdict is unchanged. (topic: reuse/tiered-approval-ops)
- A reference age+sops Python wrapper's `store.py` was checked by grep for `ttl`/`TTL`/`expir` only (no match), not read
  in full; a full read would be needed before relying on "no TTL support" as a hard fact rather than a
  grep-based inference. (topic: reuse/secret-vault-encryption)
  - Closed 2026-09-28: no article or source row names this wrapper, so it cannot be re-read; the kb's no-TTL facts rest on the sops docs (S-3eg2zeqb) and the age format specification (S-f4s2xnfz), not on the wrapper. (topic: reuse/secret-vault-encryption)

## security

### coordinator (crosswalk, coverage, precedence, candidates)

- **Windows 11 25H2 and Server 2025 v2602 Microsoft baseline packages.**
  - The Download Center page (id 55319) is a script-driven file picker that answers `curl`/WebFetch with a bot page. The Chrome extension was not connected.
  - Guessed file names under `download.microsoft.com/download/8/5/C/85C25433-…/` returned 404 for 25H2 and Server 2025. The 24H2 zip, LGPO.zip and PolicyAnalyzer.zip resolved (3 attempts).
  - Verification: download "Windows 11 version 25H2 Security Baseline.zip" and "Windows Server 2025 Security Baseline" (v2602) from https://www.microsoft.com/download/details.aspx?id=55319 into `_private/sct/` (not published). A follow-up pass can then rerun the crosswalk builder. (topic: security/baselines-catalog)
  - Tried 2026-09-27: the Download Center page (S1400) now answers a browser user agent with direct download.microsoft.com links, among them "Windows 11 v25H2 Security Baseline.zip" and "Windows Server 2025 Security Baseline - 2602.zip" (plus Edge v151 and Microsoft 365 Apps 2512). The zips were not downloaded or parsed this pass; the crosswalk rerun stays open. (topic: security/baselines-catalog)
  - Resolved 2026-09-28: both zips downloaded from the S1400 links and parsed with the 24H2 method (S-bzyxqg37, S-p6phzp72; extracts pinned in `security/artifacts/microsoft/`); `settings-crosswalk.csv` now carries `ms_25h2` and `ms_ws2025`. (topic: security/settings-crosswalk)
- **CIS ids in `settings-crosswalk.csv`:** empty. Verification: download CIS Microsoft Windows 11 Enterprise Benchmark (current version, see `baselines-catalog.md`) into `_private/cis/` (not published) and map ids offline. (topic: security/settings-crosswalk)
  - Tried 2026-09-28, still open: the Windows 11 benchmark PDF and its machine-readable forms stay behind CIS's download form and SecureSuite membership (S-li2s6pgb terms); no public list of Windows 11 v5.1.0 ids exists to map. Needs a registered download, not web research. Server 2025 CIS ids remain available through OSConfig (S1598). (topic: security/settings-crosswalk)
- **Tattooing of `Policies` keys and security-settings-extension periodic reapply:** not found in the Group Policy processing page (S1592). No other official page was fetched this pass. (topic: security/policy-precedence)
  - Mostly resolved 2026-09-27: the process-even-if-unchanged option (S-d24ri6px, S-vzmmy23x), preference removal (S-37hjm3ml), FSLogix Policies vs non-Policies keys (S-z4y7mew3) and `Remove-GPRegistryValue` (S-is2wluoa) are now DOC; no page gives a security-CSE periodic interval (recorded as DER absence) or a general Policies-key cleanup rule (in _conflicts.md). Verification: link a GPO setting a `Policies` value, unlink it, `gpupdate /force`, check the value; repeat with the setting removed from a still-linked GPO. (topic: security/policy-precedence)
- **Windows 11 defaults for `wuauserv`, `RemoteRegistry` start type and `fDenyTSConnections`:** not confirmed from an official page.
  Verification: on a fresh Windows 11 25H2 VM, run `dsc resource get` for `Microsoft.Windows/Service` (`wuauserv`, `RemoteRegistry`) and `Microsoft.Windows/Registry` (`Terminal Server!fDenyTSConnections`). This proves the defaults a drift report compares against. (topic: security/first-baseline-candidates)
  - Partly resolved 2026-09-27: `fDenyTSConnections` defaults to denied (unattend S-ww7anzs7; Policy CSP S-dwvazjaq). For `wuauserv` and `RemoteRegistry` the only Microsoft table is the Windows 11 IoT Enterprise service guide (S-6iulw4eo: Manual, Automatic); the Enterprise defaults still need the VM reading. (topic: security/first-baseline-candidates)
- **`OptionalFeatureList` behaviour for a feature name removed from the OS (PowerShell 2.0 on patched 24H2):** not documented.
  Verification: `dsc resource get -r Microsoft.Windows/OptionalFeatureList` with `MicrosoftWindowsPowerShellV2Root` on a patched 24H2 VM shows whether the result is absent, not found or an error. (topic: security/dsc-coverage)
  - Resolved 2026-09-27: the 3.3.0 manifest schema (S-xol3qgin) documents `_exist: false` for a feature name DISM does not recognise, and `dism.rs` returns it on `DISMAPI_E_UNKNOWN_FEATURE` (CODE S-cxyrrhvv); recorded in `first-baseline-candidates.md`. (topic: security/dsc-coverage)
- **SecurityPolicyDsc / AuditPolicyDsc under DSC 3.3.0 `Microsoft.Adapter/WindowsPowerShell`:** no official statement.
  Verification: run `dsc config test` with one `UserRightsAssignment` and one `AuditPolicySubcategory` on a lab VM as SYSTEM. This proves whether the non-registry 13% of the Microsoft baseline is testable at all. (topic: security/dsc-coverage)
  - Tried 2026-09-27, still open: no Microsoft or DSC Community statement; one user report (DSC issue #1545, S-ylqrt4md, COMMUNITY) ran both modules under the DSC 3.2.1 adapter on Server 2022, its crash caused by other modules. The lab run stays. (topic: security/dsc-coverage)
- **Intune column:** matching is by setting name, so `no_name_match` is not proof of absence. It could be closed by parsing the CSP links in the pinned page. (topic: security/settings-crosswalk)
  - Resolved 2026-09-28: the CSP links of the 24H2 pivot were followed and the ADMX mapping tables of the 45 linked Policy CSP pages parsed (S-4krq7dui); 28 more rows match by registry key and value (`yes_csp`). Non-ADMX CSP policies carry no registry mapping, so the remaining `no_name_match` rows still do not prove absence. (topic: security/settings-crosswalk)

### A: device settings catalog

- ~~Verification: download the Microsoft SCT Windows 11 24H2/25H2 baseline zip~~ — **superseded**: the
  coordinator obtained a direct zip URL
  (`https://download.microsoft.com/download/8/5/C/85C25433-A1B0-4FFA-9429-7E023E7DA8D8/Windows%2011%20v24H2%20Security%20Baseline.zip`)
  and is populating `settings-crosswalk.csv`, `dsc-coverage.md` and QS2 directly; Part A does not
  duplicate that work. (topic: security/settings-crosswalk)
- **Verification: download the Windows Server 2025 baseline zips (versions 2506 and 2602) from the SCT
  download page (id 55319) into `_private/sct/` (not published), or locate their direct
  download.microsoft.com URLs the same way the coordinator did for the Windows 11 24H2 zip.** Not
  attempted by Part A this pass. (topic: security/baselines-catalog)
  - Resolved 2026-09-28 for 2602 (S-p6phzp72, parsed into the crosswalk); the SCT page (S1400) no longer offers the 2506 zip, so 2602 is the only Server 2025 package parsed. (topic: security/baselines-catalog)
- ~~**Verification: open the `microsoft/osconfig` GitHub repository (or the OSConfig Learn docs' schema
  reference, if any) to confirm whether Server 2025 baseline definitions are published as
  structured data (JSON/YAML) versus only exposed through the PowerShell module's cmdlets** (QS7,
  needed for a real `dsc_v3_path` mapping of OSConfig-covered settings).~~ — **resolved** in QS7a:
  the repo publishes one CSV per baseline version (S1598). (topic: security/settings-crosswalk)
- ~~Verification: download the current Windows 11 and Server 2025 STIG zips~~ — **resolved**: the
  coordinator obtained both (Windows 11 V2R9, Server 2025 V1R3, registered as S1470/S1471). Residual
  item: extract the XCCDF from each zip and parse rule ids/registry paths/values into
  `settings-crosswalk.csv`'s `stig_id`/`stig_value` columns — not yet done by either Part A or the
  coordinator as of this message (QS6/QS20). (topic: security/settings-crosswalk)
  - Resolved 2026-09-28 (checked): `stig_id`, `stig_value` and `stig_server2025_id` are filled from the parsed XCCDF files (`security/artifacts/disa/stig-*-rules.csv`). (topic: security/settings-crosswalk)
- CIS terms-of-use text for reuse of recommendation IDs/titles was not opened directly (search
  returned explainer articles, not the terms page itself). `settings-crosswalk.csv` therefore
  carries no CIS IDs or paraphrases this pass (QS1). Partly addressed in QS1a: CIS rule ids reach
  `settings-crosswalk.csv` through Microsoft's MIT-licensed OSConfig CSV (S1598); the terms page itself
  is still unread. (topic: security/settings-crosswalk)
  - Resolved 2026-09-27: the non-member terms (S-ycjlut3h, CC BY-NC-SA 4.0) and the end-user member agreement (S-li2s6pgb: no redistribution or derivative images, internal Customized Benchmarks only) are both read; see `baselines-catalog.md`. Loading CIS ids still needs the registered PDF. (topic: security/settings-crosswalk)
- ~~OSConfig Server 2025 baseline machine-readability was not researched (QS7).~~ — **resolved** in QS7a. (topic: security/baselines-catalog)
- Microsoft baseline vs. Intune baseline setting-level comparison was not performed; needs both
  machine-readable sources above plus an Intune baseline JSON export (QS5). Partly addressed in QS5a:
  164 of 335 GPO-baseline registry settings match the Intune 24H2 pivot by name (S1472, S1475);
  a setting-level comparison through CSP names is still open. (topic: security/settings-crosswalk)
  - Partly resolved 2026-09-28: the CSP registry join adds 28 rows (192 of 335 now matched, `yes_csp`); comparing values still needs each ADMX element's value mapping (the pivot gives *Enabled*/*Disabled* and option labels, the baseline gives registry data) and stays open. (topic: security/settings-crosswalk)
- ACSC Essential Eight/Windows guidance, NCSC (UK) device guidance, BSI IT-Grundschutz/SiSyPHuS, and
  ANSSI English-language recommendations were not researched beyond placeholder rows in
  `baselines-catalog.csv`. (topic: security/baselines-catalog)
  - Resolved 2026-09-27: NCSC Windows guide v2.1 and its Intune packs (S-aljzuasy, S-cwnwnkri), BSI SiSyPHuS Win10 GPOs v1.1 (S-vxnukaep) and ANSSI's Windows server Essentials (S-cvu2vf7c) are now in `baselines-catalog.md` and its CSV. (topic: security/baselines-catalog)
- QS19 (LSA protection / Credential Guard defaults) rests on a search-engine digest of vendor blogs
  rather than a directly re-opened Microsoft Learn page (S1417 is recorded but its content was not
  independently re-extracted); tagged `COMMUNITY` pending confirmation. (topic: security/first-baseline-candidates)
  - Resolved 2026-09-27: re-read on the Configure added LSA protection page (S1477): automatic enablement on new 22H2+ installs that are enterprise joined and HVCI-capable, no UEFI variable, audit mode on by default; the article's LSA and Credential Guard lines cite S1477/S1478 as DOC, none rests on the digest. (topic: security/first-baseline-candidates)
- Exact registry paths/value names for "long paths enabled" and "RDP disabled" in
  `settings-crosswalk.csv` are widely known but were not verified against an official machine-
  readable source this pass; tagged `UNK` rather than `DOC`. (topic: security/settings-crosswalk)
  - Resolved 2026-09-27: `LongPathsEnabled` under `HKLM\SYSTEM\CurrentControlSet\Control\FileSystem` (S1591) and `fDenyTSConnections` under `HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server` (S-3yywfx4r, default denied S-ww7anzs7) are now DOC in the csv rows. (topic: security/settings-crosswalk)
- GP refresh interval, registry-CSE reapplication default, and Policies-key tattooing behaviour in
  `policy-precedence.md` were not re-fetched from an official Microsoft Learn page this pass, despite
  being long-standing documented behaviour; tagged `UNK` for this pass's evidence standard. (topic: security/policy-precedence)
  - Resolved 2026-09-27: the refresh interval and change-driven reapply are DOC S1592; see the entry above for reapply options and tattooing. (topic: security/policy-precedence)

### B: management plane

- QS9: exact **current** CIS Microsoft SQL Server benchmark version/date and CIS GitLab Benchmark version/date were seen only via secondary blog posts and a third-party scanner project, not a direct fetch of the cisecurity.org benchmark listing page's version field. `Verification: confirm current CIS Microsoft SQL Server 2022/2025 Benchmark version and CIS GitLab Benchmark version directly on cisecurity.org/benchmark/microsoft_sql_server and the CIS Software Supply Chain Security Benchmarks page (no registration needed for the listing, only for the PDF).` (topic: security/baselines-catalog)
  - Resolved 2026-09-27: the CIS listing pages give SQL Server 2025 1.0.0, 2022 1.3.0, 2019 1.6.0, and GitLab 1.0.1 beside GitHub 1.2.0 under Software Supply Chain Security; `management-plane-hardening.md` already cites the list (S1485). (topic: security/baselines-catalog)
- QS8: no page was found that explicitly classifies ConfigMgr/MECM as "Tier 0" in Microsoft's own enterprise access model docs. Only the general control-plane/management-plane/data-workload-plane tiering principle (Microsoft cloud security benchmark, privileged access) was confirmed; applying it to ConfigMgr is a derivation (`security/management-plane-hardening.md`), not a documented Microsoft statement.
  - Resolved 2026-09-27 (as in the auth wave): the AD DS tier model (S-7nbamxyc) puts systems that patch or run agents on Tier 0 identity systems in Tier 0; the article applies it (DER). Still no page names ConfigMgr itself. (topic: security/management-plane-hardening)
- Client push NTLM coercion to an attacker-chosen host (the old UNK line in `management-plane-hardening.md`, dropped 2026-09-27): Microsoft's pages (KB15498768 S1484, KB15599094 S-uixd54ua, CVE-2022-37972 in the SUG API S-56n7jfkc) describe the push account's NTLM use and link NTLM relay mitigations but never describe coercion; the technique is only in community research. Tried: Learn search, both KBs, the MSRC SUG API. (topic: security/management-plane-hardening)
- QS17: exact GitLab **subscription tier** (Free/Premium/Ultimate) gating for Dependency Scanning vs. SLSA attestation vs. artifact signing was not confirmed against `docs.gitlab.com/subscriptions/features/` in this pass — only the existence and mechanics of the features (`security/supply-chain.md`) were confirmed, not their tier gate. `Verification: cross-check docs.gitlab.com/subscriptions/features/ for the tier of Dependency Scanning, SLSA provenance attestation, and container/artifact signing before using this for a purchasing or gate decision.`
  - Resolved 2026-09-27: GitLab docs at commit 9f1632e: dependency scanning by SBOM Ultimate on all offerings (S1511); SLSA level 3 attestations Ultimate, GitLab.com only, Experiment (S-l6ia2wz4); Sigstore keyless signing all tiers, GitLab.com only (S-7d4nrwpk); runner artifact provenance metadata all tiers and offerings (S-hvhro6n5). (topic: security/supply-chain)
- QS18 (Run Scripts + AllSigned): confirmed Run Scripts has no signing gate of its own and the client-side AllSigned policy is the enforcement point, but did not find an official page describing whether ConfigMgr's CI (compliance) script deployment path differs from Run Scripts on this point — assumed identical based on both using the same client-side PowerShell execution policy setting (already documented in `windows/execution-policy-signing.md`).
  - Closed 2026-09-28: a confirmed item, no open question.
- No official Microsoft page was found specifically discussing `dsc.exe` (or DSC v3 resource executables) under WDAC/App Control; general PowerShell WDAC script-enforcement mechanics were confirmed but not a DSC-specific statement. Community source only (S1519), not used as sole evidence for any `DOC` fact. (topic: security/script-and-code-signing)
  - Tried 2026-09-27, partly resolved: Microsoft's script-enforcement page (S-i4uarhme) now backs the PowerShell rules (option 11, .ps1/.psm1/.psd1, WinVerifyTrust root) and says unenlightened hosts are not controlled; no Microsoft page names `dsc.exe`, so its treatment as an executable is DER. DSC manifest signing is open issue #327 (S-zokdk7aw). (topic: security/script-and-code-signing)
- PyPI Trusted Publishing's self-managed-GitLab support status is unresolved: the official `docs.pypi.org` page (S1509) does not list self-managed GitLab as supported, while a third-party (Socket) report (S1510, COMMUNITY) claims PyPI expanded support to self-managed GitLab. Recorded as a conflict-worthy discrepancy in `security/supply-chain.md` rather than asserted either way as `DOC`.
  - Resolved 2026-09-27: PyPI's own blog (S-5ry5zerr) confirms a hand-onboarded beta for GitLab Self-Managed and Warehouse supports custom GitLab issuers (CODE S-5t26tmbz); the user docs still lag (see _conflicts.md). (topic: security/supply-chain)
- NIST AI RMF "Agentic Profile" (if any, beyond the Generative AI Profile SP 800-218A/AI 600-1) was not found on nist.gov directly; a third-party (Cloud Security Alliance) reference to such a profile was not treated as authoritative and is not cited. (topic: security/framework-control-map)
  - Resolved 2026-09-27 (negative): NIST's AI RMF page (S1541) lists only the GenAI profile and a Critical Infrastructure profile concept note (2026-04-07); agent work is the CAISI AI Agent Standards Initiative (S-m6uptfmu). Recorded in `security/ai-agent-guidelines.md`. (topic: security/framework-control-map)

### C: frameworks, regulation, AI

- ISO/IEC 42001:2023 and ISO/IEC 27001:2022/27002:2022 full clause text is paid; only public metadata (numbers,
  titles) was captured. `Verification: obtain ISO/IEC 27001:2022, 27002:2022 and 42001:2023 full text under
  organisational licence if clause-level detail beyond Annex A numbers/titles is needed.` (topic: security/framework-control-map)
  - Tried 2026-09-27, still open: iso.org returns 403 to scripted requests and Claude in Chrome did not respond; the csv titles are now labelled own-words (DER) instead of UNK. (topic: security/framework-control-map)
- MITRE ATLAS technique-level detail (specific technique ids/mitigations for tool-using agents) was not
  enumerated; only the catalog's existence and licensing note were captured. Three-attempt budget on ATLAS
  technique enumeration was not exhausted, but time was allocated to higher-priority QS10-QS14 items first. (topic: security/ai-agent-guidelines)
  - Resolved 2026-09-27: agent techniques and mitigations read from ATLAS-2026.09.yaml at commit 3259f38 (S-txcdv36f) and added to the article. (topic: security/ai-agent-guidelines)
- (Resolved 2026-09-24) MITRE ATT&CK mitigation (M-id) and detection-strategy (DET-id) values for
  T1072/T1484/T1098/T1558/T1078/T1219/T1562 are now extracted from the pinned v19.2 STIX bundle into
  `security/artifacts/mitre/attack-subset.csv` and summarized in `threat-model-inputs.md` and QS15. (topic: security/threat-model-inputs)
- UODO's DPIA list (S-5jbvhlmx; M.P. 2019 poz. 666, communication of 2019-06-17) is in Polish; only the fact that such a list exists and its URL were captured, not a
  translated enumeration of its entries. (topic: security/privacy-compliance)
  - Resolved 2026-09-27: the list was read in the Monitor Polski PDF (S-k3lipqns); its 12 criteria and the workplace-monitoring example are now in the article. (topic: security/privacy-compliance)
- Whether a given device-log/AI-processing system's specific processing meets two or more EDPB DPIA criteria, and
  whether its use case falls under EU AI Act Annex III, are open questions this research pass deliberately left as
  facts-only / UNK, per the brief's instruction not to decide policy questions. (topic: security/privacy-compliance)
  - Partly resolved 2026-09-27: the Commission's AI system definition guidelines (S-twztbg3z) now back the split between rule-based tooling and the model (DER); Annex III and the DPIA count stay per-deployment questions by design. (topic: security/privacy-compliance)


## agents/doc-lookup-sources

- Anthropic docs terms for storing fetched page text offline: not found on platform.claude.com or code.claude.com
  (2026-09-25). Until found, Anthropic docs stay summarized with quotes of at most 25 words.
  - Tried 2026-09-27: WebSearch of anthropic.com/legal (Consumer and Commercial Terms) and the docs footers already cited; no docs-specific licence found. Still open. (topic: agents/doc-lookup-sources)
- No stable (GA) docs MCP server or documented API was found for Windows security baselines (Security Compliance
  Toolkit and DISA STIG are zip downloads; CIS is licensed) or for Ansible (docs.ansible.com answered scripted
  requests with HTTP 429; the GitHub repos `ansible/ansible-documentation` and `ansible-collections/ansible.windows`
  remain readable through GitHub).
  - Re-checked 2026-09-28: still none; the baselines were read from the SCT zips (S-bzyxqg37, S-p6phzp72) instead. (topic: agents/doc-lookup-sources)
- The Claude Code Docs and MCP docs MCP servers carry no explicit GA statement; they are kept because Anthropic's
  own quickstart documents the first and both report version 1.0.0 with no preview label.
  - Tried 2026-09-27: `code.claude.com/docs/en/mcp-quickstart` and `/en/agent-sdk/mcp` use `https://code.claude.com/docs/mcp` as their first example server, but neither page carries a GA label. Still open. (topic: agents/doc-lookup-sources)
- Context7's refresh cadence ("based on popularity"), its rate-limit numbers with and without an API key, and
  whether `query-docs` results carry source urls: not read (2026-09-27; only the pinned README and
  context7.com/docs/adding-libraries were read). (topic: agents/doc-lookup-sources)
  - Resolved 2026-09-27: popularity thresholds 1/15/30/45 days (S-gupervu4); no published rate numbers, 429 with `Retry-After` (S-ke227men); Free 1,000 calls a month, Pro 2,000 per seat then $5 per 1,000 (S-fqi6xbbc); results carry source URLs (S-autbwi4y). (topic: agents/doc-lookup-sources)
- Which documentation domains Claude Code's `WebFetch` preapproves (whether Microsoft Learn, the Claude Code docs and the MCP docs hosts are in the set), and any result-size cap of the Mintlify docs servers' search and filesystem tools: the tools reference says a built-in set exists but does not list it; looked in en/tools-reference, en/permissions and en/data-usage of the Claude Code docs (2026-09-29). (topic: agents/doc-lookup-sources)
- Whether `claude -p --output-format json` prints the SDK result message field for field: the headless page names `result`, session id, `total_cost_usd`, a per-model breakdown and `structured_output` but no full object; a run of the CLI would show it (2026-09-29). (topic: claude/ci-and-headless)

## windows/smart-app-control

- No documented Intune setting, ADMX/Group Policy setting or CSP node for Smart App Control's own mode (Off/On/Evaluation) was found. Tried (2026-09-25, Microsoft Learn MCP search): "Smart App Control policy CSP VerifiedAndReputablePolicyState ApplicationControl Intune configure"; "Smart App Control App Control for Business policy Intune Group Policy manage"; fetched the SAC overview, the test-your-app page and the App Control for Windows page. Only the `VerifiedAndReputablePolicyState` registry value (turn off) and App Control for Business policies surfaced.
  - Tried 2026-09-28, still none: Learn search of Policy CSP, ApplicationControl CSP and the Intune App Control pages, plus the KB5079391 note (S-5zawgrph) that adds a user switch; recorded as a DER absence. (topic: windows/smart-app-control)
- "Enterprise managed" (48-hour evaluation rule) is not defined on the pages read. Tried: same searches plus "enterprise managed devices turned off evaluation 48 hours domain joined Intune enrolled".
  - Tried 2026-09-28, still undefined: the consumer FAQ (S-n2kx46hd) lists enterprise-managed as a reason SAC is off without defining it; recorded as a DER absence. (topic: windows/smart-app-control)
- The consumer FAQ at support.microsoft.com (linked from S2200) was not read: the Learn MCP server does not serve it. It may state the re-enable path and region list.
  - Resolved 2026-09-28: read directly with curl (S-n2kx46hd): reasons SAC is off, and recent updates allow turning it on without a clean install, confirmed by KB5079391 (S-5zawgrph); no region list. (topic: windows/smart-app-control)

## security/vulnerability-prioritization

- NVD API 2.0 exact base endpoint path (e.g. `/rest/json/cves/2.0`), the `lastModStartDate`/`lastModEndDate`
  120-day maximum window, and `resultsPerPage` maximum: the NVD "Start Here"/API reference pages are
  JS-rendered and returned only rate-limit and API-key text through the available fetch tools (2026-09-26).
  (topic: security/vulnerability-prioritization)
  - Resolved 2026-09-27: Claude in Chrome did not respond, and nvd.nist.gov serves an Angular app behind a bot challenge, so the values were read from the API itself (S-rzvfq3ba): base path `/rest/json/cves/2.0`, `resultsPerPage` above 2000 and `lastMod*` ranges over 120 days are rejected with those limits in the error message. (topic: security/vulnerability-prioritization)
- EPSS API documented rate limit (if any) beyond the default page size: not found on `first.org/epss/api` (the
  page returned 404) or the API's own JSON response (2026-09-26). (topic: security/vulnerability-prioritization)
  - Resolved 2026-09-27: the FIRST.Org API docs (api.first.org, S-o6hwt2kg) give 1,000 requests per minute for unauthenticated public endpoints; the /epss page moved to api.first.org/epss/ (S-7uk5ui7z). (topic: security/vulnerability-prioritization)
- MSRC CVRF API authentication: the Swagger definition lists no `api-key` header, but whether the interactive
  portal or a production integration still requires a subscription key was not confirmed (2026-09-26).
  (topic: security/vulnerability-prioritization)
  - Resolved 2026-09-27: an anonymous GET /updates returns 200 (S-vtximkx6) and the module release notes record the Api-key requirement removed on 2021-02-03 (CODE S-difowozj). (topic: security/vulnerability-prioritization)
- Whether Azure Linux / Azure Container Linux advisories are published as VEX and also surfaced through the MSRC CVRF API: the MSRC Security Updates API repository (S-n7obrzja) does not say so (re-read 2026-09-26); needs an MSRC or Azure Linux source. (topic: security/vulnerability-prioritization)
  - Resolved 2026-09-27: /updates lists 64 'Mariner Release Notes' documents (S-vtximkx6), and MSRC's CSAF provider metadata (S-6jreovk7) has a `csaf/vex` distribution whose files cover CBL Mariner / Azure Linux packages (S-m6mns3xp). (topic: security/vulnerability-prioritization)

## agents/agent-evaluation

- Whether Amazon Bedrock AgentCore Evaluation (`inspect_ai`) has native stdio-MCP-target support, and whether Azure AI Foundry's evaluation SDK has explicit stdio-MCP-target support beyond a UI "MCP Registry" reference, were not confirmed on the fetched pages (2 lookups: product overview + evaluation-harness pages). (topic: agents/agent-evaluation)
  - Partly resolved 2026-09-28: Inspect itself has `mcp_server_stdio()` (S-wwrpen3s); AgentCore Evaluation and Foundry's evaluation SDK were not re-read. (topic: agents/agent-evaluation)

## agents/coding-agents-mcp

- OpenAI Codex CLI's exact approval-mode policy key names (beyond the described `auto`/`prompt`/`writes`/`approve` values) were not found on a primary Codex config-reference page in this pass (1 WebFetch of the Codex CLI docs config page, no dedicated key-name table found). (topic: agents/coding-agents-mcp)
  - Resolved 2026-09-27: Codex configuration reference (S-4fmcb5i2): `approval_policy` = `on-request` | `never` | `granular` table ("untrusted" retired); per-server `default_tools_approval_mode` and per-tool `approval_mode` take `auto`/`prompt`/`writes`/`approve`; commands from S-zqlgscwv. (topic: agents/coding-agents-mcp)

## agents/content-safety-prompt-shields

- Azure AI Content Safety's current supported-region list for Prompt Shields was not captured; it lives on a separate, frequently-updated Azure regions page not fetched in this pass (1 lookup: Microsoft Learn search for "Azure AI Content Safety region availability"). (topic: agents/content-safety-prompt-shields)
  - Resolved 2026-09-27: region availability page (S-47nwz53u, updated 2026-09-18) read; the Prompt Shields region list and its 10K-character input limits are now in the article. (topic: agents/content-safety-prompt-shields)

## agents/github-copilot-admin

- Exact field-level schema of GitHub Copilot's downloaded usage-metrics report files, the premium-request monthly allowance per plan/per-model multipliers and overage billing rate, and IDE proxy/TLS-interception certificate + data-retention settings were not found on docs.github.com pages fetched (billing-overview and org-request-allowance pages 404'd or lacked the figures; 2 lookups attempted). (topic: agents/github-copilot-admin)
  - Mostly resolved 2026-09-27: report fields (S-z7qwhjoa), AI-credit billing that replaced premium requests for Business/Enterprise (S-5mca3vxo, S-kvkn5bq2, S-7vu7gftp) and proxy/certificate settings (S-hjnsjtb6) are in the article. Still open: GitHub's own prompt-retention periods; the Trust Center FAQ is JavaScript-rendered, Claude in Chrome was unavailable, and docs.github.com states only provider ZDR agreements (S-5yxttqw4). (topic: agents/github-copilot-admin)

## agents/langgraph

- LangSmith Deployment current pricing tiers and self-hosted licensing terms are not documented on the fetched LangGraph platform overview page; `docs.langchain.com/langsmith/deployments` was not independently fetched this pass (1 lookup). The exact `langchain-mcp-adapters` → `langchain[mcp]` step-by-step migration guide referenced by the docs was likewise not located on a fetched page (1 lookup). (topic: agents/langgraph)
  - Resolved 2026-09-27: LangChain pricing page (S-woho7bmc: Developer $0, Plus $39 per seat with Deployment access, Enterprise with self-hosted options), self-hosting needs an Enterprise plan and licence key (S-ujkfhzif), and the MCP adapters migration guide (S-bygurlbr). (topic: agents/langgraph)

## agents/microsoft-agent-framework

- Exact licence terms for the Microsoft Agent Framework .NET/Go SDK packages (as distinct from the GitHub repository root MIT licence) were not confirmed on a package-registry (NuGet/pkg.go.dev) page in this pass (1 lookup: Microsoft Learn search for "Microsoft Agent Framework license NuGet"). (topic: agents/microsoft-agent-framework)
  - Resolved 2026-09-27: NuGet `Microsoft.Agents.AI` declares MIT for 1.0.0-1.22.0 (S-y76ymaxp); `microsoft/agent-framework-go` is MIT (S-a3n34lxa). (topic: agents/microsoft-agent-framework)

## agents/security-copilot-endpoint

- Whether the Security Copilot Device Offboarding Agent has its own dedicated Learn article (licensing/role/identity detail beyond the overview page's one-paragraph description) was not found (1 Microsoft Learn search for "Device Offboarding Agent Security Copilot"). (topic: agents/security-copilot-endpoint)
  - Resolved 2026-09-27: it has (S-nizafwvn); the agent could not be set up after 2026-04-30 and was removed on 2026-06-01. Requirements, identity and limits now in the article. (topic: agents/security-copilot-endpoint)

## defender/advanced-hunting

(Resolved 2026-09-26: confirmed no distinct retention/refresh cycle is documented for KB-suffixed tables; both are TVM tables not ingested into Microsoft Sentinel [S-elscbjku]. Article status flipped to complete.)

## defender/response-actions-api

- No Microsoft Graph security API equivalent for MDE machine response actions (isolate/unisolate/restrict/scan/quarantine/live response) was found this session either: `security.deviceEvidence` remains read-only, and the only Graph action found for a similarly-named operation, `windowsDefenderScan` (`POST /deviceManagement/managedDevices/{id}/windowsDefenderScan`, v1.0), is an **Intune-managed-device** action, not an MDE machine action, and does not cover isolate/restrict/scan-via-MDE or live response. Confirmed distinct scope via Microsoft Learn search (2026-09-26); MDE's own `api.securitycenter.microsoft.com`/Graph `security` machineAction surface remains the only documented path for these specific actions. (topic: defender/response-actions-api)
  - Resolved 2026-09-27: Graph beta does carry device actions, but only as custom detection rule `automatedActions` (deviceAction, isolateDeviceAction, stopAndQuarantineFileAction; S-bxbx2kp5, S-mx6w5ffh); the per-incident-task `incidentTaskResponseAction` family is deprecated and removed 2026-10-01 (S-x6wwggq6). On-demand isolate/scan/live response stays on the MDE API; the article says so. (topic: defender/response-actions-api)

## entra/conditional-access-devices

(Resolved 2026-09-26: `conditionalAccessDevices`/`conditionalAccessFilter` JSON [S-ac6jmj3f, S-qu7z6wlo] and full `builtInControls` enum [S-nuh4ep7w] fetched verbatim. Article status flipped to complete.)

## entra/pim-and-governance

- Exact end-to-end timing (seconds) for an Entra-role (not Azure-resource-role) PIM activation to be reflected in a fresh Graph token was not independently confirmed on a fetched page this pass (1 Microsoft Learn search for "PIM Entra role activation token propagation seconds"); the Azure-resource-role figure is treated as consistent but not verbatim-confirmed for Entra roles. (topic: entra/pim-and-governance)
  - Tried 2026-09-27, still open: Learn search (activate Entra role, Azure resource roles, role settings) repeats 'within seconds' plus application caching; the only timed case found is the PRT renewal every four hours for the Device Local Administrator role (support article, now DOC). The article records the rest as DER. (topic: entra/pim-and-governance)

## graph/microsoft365dsc

- `New-M365DSCDeltaReport`/`Test-M365DSCAgent` parameter-level syntax (dedicated cmdlet page 404s) and the individual `Intune*`-prefixed resource names were not confirmed on a working page this pass (1 lookup: Microsoft Learn/GitHub search for "Microsoft365DSC New-M365DSCDeltaReport cmdlet reference"). (topic: graph/microsoft365dsc)
  - Resolved 2026-09-28: both read from source at tag 1.26.909.1 (S-dlzkqwix, S-fbhq2yc2); `Test-M365DSCAgent` turns out to check the agent machine, not drift, and the article is corrected. The 166 `MSFT_Intune*` resources are counted from the release tree (S-qkxsdf32). The docs site still has no cmdlet pages. (topic: graph/microsoft365dsc)

## intune/app-protection-mam

(Resolved 2026-09-26: `windowsInformationProtectionPolicy`/`mdmWindowsInformationProtectionPolicy` [S-2jxyk3ra, S-j6tphfq3] and `androidManagedAppProtection` [S-gqqrls57] full property references fetched. Article status flipped to complete.)
- Windows MAM on Home edition, blocking Edge sign-in via Conditional Access, and the Authenticator check (three UNK lines, 2026-09-27): Home is now DER (Windows MAM page S-rvpreeft points to the supported-platforms list S-d4yd34s7, which lists Windows 11 Home); the broker requirement is DOC (S-hkj4rbxk). The Edge sign-in block claim (itself inconsistent: Windows, iOS and Android, but not iOS) was found on no current page (Learn searches on Edge MAM, the Windows app protection CA policy and the Edge iOS/Android pages) and was removed. (topic: intune/app-protection-mam)

## intune/certificates-pki

- Imported-PFX certificate profile field-by-field configuration, DigiCert/third-party SCEP partner-specific SAN mapping tables, and the Graph `deviceManagementConfigurationPolicy`/certificate-profile REST bodies were named out of scope for this pass and not fetched (0 lookups spent, explicitly deferred at authoring time). (topic: intune/certificates-pki)
  - Not researched 2026-09-27 (a scope note, not a failed lookup). Corrected the same day: the 6.2101.13.0 connector deprecation fact, marked UNK as missing from S-hxbyw5pm, is on that page's What's new for the Certificate Connector section and is now DOC. (topic: intune/certificates-pki)

## intune/configuration-policies

- Whether the settings-catalog policy create/update body must set `technologies`/`platforms` explicitly, with a full worked JSON example, and whether there is a dedicated event-log ID range for configuration-policy (Policy CSP) apply failures distinct from the general DeviceManagement-Enterprise-Diagnostics-Provider channel, were not found on the fetched Graph reference and diagnostics pages (2 lookups: Graph settings-catalog create page, DM diagnostics-provider event ID list). (topic: intune/configuration-policies)
  - Resolved 2026-09-27: the create page (S-4gg3zmhr, read at microsoft-graph-docs-contrib 4ad99fd3) lists platforms and technologies in its request-body table and sets both in its example; no Windows JSON example exists, so the article says to set both explicitly (DER). No event ID range is documented; failures appear as 'MDM ConfigurationManager: Command failure status' in the Admin channel (S-77gkdi7q, S-jicw45tl), recorded as DER. (topic: intune/configuration-policies)

## intune/device-inventory-analytics

(Resolved 2026-09-26: re-confirmed no v1.0 `userExperienceAnalytics*` resource/method pages exist on Microsoft Learn — every page found resolves to `view=graph-rest-beta` only [S-nwf5cf5q]. Article status flipped to complete.)
- Six UNK lines (claims no longer on the cited pages) re-checked 2026-09-27: all six are now DOC from other current pages: Advanced Analytics FAQ (S-3itrgwhj: no export connector; high event volume needed for anomalies), App inventory for Windows (S-vdrnoalt: optional properties; collect wins over don't collect), the Intune Adoption Score page (S-m5aovwzr, now contradicted by S-3l57sxrb, see _conflicts.md) and the Graph beta reference at 4ad99fd3 (S-6i4enlqz). (topic: intune/device-inventory-analytics)

## intune/endpoint-privilege-management

- EPM Agent's own log file names/paths and Windows Event Log channel were not found on the EPM troubleshooting/known-issues/deployment-planning pages fetched this session (2 lookups, 2026-09-26); only the client install folder (`C:\Program Files\Microsoft EPM Agent`) and service name are documented on those pages. (topic: intune/endpoint-privilege-management)
  - Partly resolved 2026-09-27: the Collect diagnostics page (S-6epv7qzl) collects %ProgramFiles%\Microsoft EPM Agent\Logs\*.* and HKLM\SOFTWARE\Microsoft\EPMAgent; file names and an event channel remain undocumented (Learn search on EPM logs found none). The Approve-/Deny-/Revoke-MgBetaDeviceManagementElevationRequest cmdlets are confirmed from the PowerShell Gallery listing (S-hepxqkky) because their Learn pages return 404. (topic: intune/endpoint-privilege-management)
  - Tried 2026-09-28, still open: Learn search of the EPM deployment-planning, known-issues and elevation-settings pages gives the agent folder, service and the EpmTools cmdlets (`Get-Policies`, `Get-ClientSettings`, ...) but no log file names or event channel. Needs a lab device reading `%ProgramFiles%\Microsoft EPM Agent\Logs`. (topic: intune/endpoint-privilege-management)

## intune/network-profiles

- Full Entra Private Access/Global Secure Access configuration (Quick Access setup steps, per-app segmentation, private DNS, Private Network Connector) was named out of scope for this pass and not fetched (0 lookups spent, explicitly deferred at authoring time; a dedicated `auth/` topic would need its own research pass). (topic: intune/network-profiles)
  - Scope note, not a failed lookup (re-checked 2026-09-27): the article's UNK line restating it was removed from Facts; the Reference section keeps the out-of-scope list. A dedicated Global Secure Access topic would need its own research pass. (topic: intune/network-profiles)

## intune/remote-actions

(Resolved 2026-09-26: Multi Admin Approval's protectable resource list confirmed via `intune/fundamentals/role-based-access-control/multi-admin-approval` [S-cunjuxe3] — Apps, Compliance policies, Configuration policies, Device actions (wipe/retire/delete only), RBAC, Scripts, Access Policies, Tenant Configuration. Article status flipped to complete.)

## logs/microsoft-sentinel

- Whether the Defender-portal Table insights view (ingestion volume/cost estimates) is billing-grade vs advisory, and its exact refresh cadence, was not covered on the pages read for this topic (1 Microsoft Learn search for "Defender portal table insights billing cost refresh"). (topic: logs/microsoft-sentinel)
  - Resolved 2026-09-28: Table insights is a visualization surface, not billing-grade or alerting (S-btmphtyp, S-bxionmbk); cost estimates use public list price; 30-day lookback; no refresh cadence is published (recorded as DER). (topic: logs/microsoft-sentinel)

## mecm/osd-task-sequences

- The full per-step-type property list (success codes, continue-on-error, per-step settings) and complete `Get/New/Remove/Set-CMTSStep*` cmdlet set were reviewed only for the step types already named in the article, not exhaustively (budget-limited at authoring time). Windows 11 in-place-upgrade task sequence specifics (`SetupCompletePause` timing variable, `_SMSTSOSUpgradeActionReturnCode`) were found in the variable reference but not cross-checked against a dedicated in-place-upgrade walkthrough page (1 lookup). (topic: mecm/osd-task-sequences)
  - Resolved 2026-09-27: the steps page's Common settings (S-dz6j2643) give the properties and options shared by every step, and the in-place upgrade recommendations (S-4eqz4ngg) and 1910 what's new (S-gppz6zvr) confirm the _SMSTSOSUpgradeActionReturnCode check and SetupCompletePause; per-step CMTSStep cmdlets remain reviewed only for the steps the article names (a scope note, DER). (topic: mecm/osd-task-sequences)

## mecm/software-updates

(Resolved 2026-09-26: `SMS_AutoDeployment`/`SMS_ADRDeploymentSettings` WMI class properties [S-fq4xtwh3] and `Set-CMOrchestrationGroup` cmdlet reference, confirming orchestration groups are PowerShell/WMI/console-only with no Graph surface [S-ix237xay]. Per-version ADR wizard-page history and a distinct `SMS_SUPComponent` class remain unconfirmed — no such class was found on Learn. Article status flipped to complete.)

## windows/app-control

(Resolved 2026-09-26: confirmed the AppLocker CSP reboots on any policy apply/delete, not just OOBE, and the "improved Intune App Control experience" remains public preview with no GA date published [S-oartdvpr]. Article status flipped to complete.)

## windows/azure-arc-servers

(Resolved 2026-09-26: `--enable-automatic-upgrade`/automatic agent upgrade confirmed still public-preview via agent-release-notes and manage-agent pages [S-nofzkxdn]; SSH-over-Arc and Run Command fully documented [S-vetttstu, S-obkcr6hb]; Azure Machine Configuration confirmed to use DSC v3 on Linux / DSC v2 on Windows [S-xjcjnwtx].)
- The specific DSC v3 build/version number bundled with a given Azure Machine Configuration agent release is not published on Microsoft Learn (machine-configuration and Connected Machine agents version independently); whether it matches this kb's `dsc/` 3.3.0 coverage remains unconfirmed after 1 lookup (2026-09-26). (topic: windows/azure-arc-servers)
  - Tried 2026-09-28, still unpublished: the agent release notes (S-jduwmt53) list Guest Config agent versions only; recorded as a DER absence. Needs Microsoft to publish it or a lab reading of the agent folder. (topic: windows/azure-arc-servers)

## windows/delivery-optimization

(Resolved 2026-09-26: DHCP Option 235 (cache host source, `DOCacheHostSource`) and Option 234 (Group ID source, `DOGroupIDSource`) mechanics, values, and precedence fully documented from `waas-delivery-optimization-reference` [S-7olkz3h6]. Article status flipped to complete.)

## windows/kiosk-assigned-access

(Resolved 2026-09-26: confirmed Intune's Multi app kiosk template is Windows 10-only; Windows 11 multi-app kiosk uses the separate, non-template `lock-down-windows-11-to-specific-apps` mechanism [S-pjgeqktu]. Article status flipped to complete.)

## windows/laps

(Resolved 2026-09-26: fetched the official Windows LAPS troubleshooting guidance [S-tn4hpddq] and legacy-migration page [S-4as52t5e] — event-ID-to-cause/resolution table and legacy-client removal steps now cited. Article status flipped to complete.)

## windows/windows-update-management

(Resolved 2026-09-26: Policy CSP - Update `learn.microsoft.com/windows/client-management/mdm/policy-csp-update` for AllowAutoUpdate/ManagePreviewBuilds/SetPolicyDrivenUpdateSourceFor*/ConfigureFeatureUpdateUninstallPeriod allowed-values and defaults [S-2z6lunfo]; Extended Security Updates (ESU) program for Windows 10 `learn.microsoft.com/windows/whats-new/extended-security-updates` for commercial ESU pricing [S-hdprezk3]; Windows Autopatch Prerequisites/groups-overview/RBAC pages for the feature-entitlement matrix, Autopatch groups, and RBAC role list [S-4oi245yf, S-bujcbcpv, S-m6wsqtyu]. Article status flipped to complete.)

## ad/krbtgt-password-reset

- **Whether `New-KrbtgtKeys.ps1` is still actively maintained/recommended as of 2026, and its current exact parameters/behavior.** Microsoft's ransomware incident-response playbook (S-4cv3kd2v) links to `github.com/microsoft/New-KrbtgtKeys.ps1` as a recommended scripted process but the kb has not fetched the script repository itself (1 attempt: only the linking Learn page was fetched via MCP). [UNK] (topic: ad/krbtgt-password-reset)
  - Tried 2026-09-28: `microsoft/New-KrbtgtKeys.ps1` is archived on GitHub (last push 2024-03-07), so it is not maintained; whether Microsoft still recommends it is not stated. (topic: ad/krbtgt-password-reset)
- **A documented, Microsoft-stated minimum recommended KRBTGT reset cadence outside of a compromise response.** The fetched pages give the 180-day posture-assessment threshold (S-6mj4jpce) and the twice/10-hour compromise procedure (S-4ikiakpi), but no general "reset every N days as routine hygiene" policy statement was found in the pages searched. [UNK] (topic: ad/krbtgt-password-reset)
  - Tried 2026-09-28, still none beyond the pages already cited; a routine cadence is not published. (topic: ad/krbtgt-password-reset)
- **Closed 2026-09-26:** `New-KrbtgtKeys.ps1` status: the repository was archived on 2024-03-08 (S-vhwb6zo5); routine cadence: Microsoft says "on a regular schedule" with no fixed interval (S-nl7th7fi), 180 days only as the Defender for Identity check (S-6mj4jpce). (topic: ad/krbtgt-password-reset)

## gpo/admx-central-store

- Whether GPMC/the Group Policy Editor chooses the Central Store over the local `C:\Windows\PolicyDefinitions` store by comparing file versions, or simply prefers the Central Store whenever present (subject only to `EnableLocalStoreOverride`), is not stated on `create-and-manage-central-store` or `group-policy-settings-show-as-extra-registry-settings`. Searched Microsoft Learn for "GPMC central store versus local store precedence"; no page found describing a version-comparison step. (topic: gpo/admx-central-store)
  - Closed 2026-09-28: answered by the 2026-09-26 closing note below (`EnableLocalStoreOverride`, presence not version). (topic: gpo/admx-central-store)
- Whether SYSVOL/Central Store replication specifically uses DFSR (versus legacy FRS on domains not yet migrated) is not stated on any fetched page for this topic; the DFSR mechanism is inferred, not confirmed, for this article. Searched Microsoft Learn for "Central Store DFSR replication SYSVOL"; no page directly names the replication engine in the Central Store context. (topic: gpo/admx-central-store)
  - Closed 2026-09-28: answered by the 2026-09-26 closing note below (DFSR at 2008+ DFL). (topic: gpo/admx-central-store)
- **Closed 2026-09-26:** no version comparison; `EnableLocalStoreOverride` 0 (default) uses the SYSVOL store when present, 1 the local one (S-xtwd545o); SYSVOL replicates with DFSR at the 2008+ domain functional level, FRS deprecated and blocked for new DCs from Windows Server 2019 (S-6glsfens, S-gvgapsup). (topic: gpo/admx-central-store)

## arch/kerberos-linux-containers

- **Whether `requests-gssapi` (or python-gssapi underneath) acquires credentials from a client keytab on its own (MIT `KRB5_CLIENT_KTNAME` / `KRB5_KTNAME`) without a prior `kinit`.** The kb earlier said it does and quoted 'having a keytab is sufficient'. The requests-gssapi README and repo (HEAD 2025-10-16, S1604) contain no keytab text and require a TGT already in the ccache. Verify against the python-gssapi / MIT Kerberos client-keytab docs or in a lab; until then, run `kinit -kt` first. (topic: arch/kerberos-linux-containers)
  - Resolved 2026-09-28: MIT Kerberos documents the default client keytab (`KRB5_CLIENT_KTNAME`) as used automatically by GSSAPI client applications; `KRB5_KTNAME` is the server keytab (S-n4ns4gdd). The article now says so. (topic: arch/kerberos-linux-containers)

## auth/delegation-kcd-obo

- **Interim Entra ID pattern for MCP Enterprise-Managed Authorization (ID-JAG)**: the kb said Microsoft shows Entra ID + Azure App Service as the authorization boundary in front of MCP servers, but S1300 (the only source) does not say this; the claim is now [UNK]. Needs a Microsoft Learn or modelcontextprotocol.io source on Entra support for ID-JAG, or on the recommended interim pattern. (topic: auth/delegation-kcd-obo)
  - Resolved 2026-09-27: Microsoft documents Entra ID as the plain OAuth authorization server for MCP servers, with App Service Easy Auth as an option (S-uw3gpx3u); it is not presented as an ID-JAG interim, and no Entra ID-JAG issuance is documented. (topic: auth/delegation-kcd-obo)

## agents/doc-change-detection

- **Is Learn's `?accept=text/markdown` form a supported interface?** It works (query parameter or `Accept` header) and returns front matter with `updated_at` and `git_commit_id`, but no Learn page found documents it (searched Learn 2026-09-27). Needs a Microsoft Learn platform page or release note. (topic: agents/doc-change-detection)
  - Partly resolved 2026-09-27: the documented Markdown routes are the Learn MCP fetch tool (S2176) and `mslearn fetch` (S-lylm4eqz); `learn.microsoft.com/en-us/llms.txt` returns 404 and no page documents the query or header form. Recorded as a DER in the article; a Microsoft statement on the form itself is still missing. (topic: agents/doc-change-detection)
- **Does a Learn page's ETag change on a site-template rebuild with no content change?** Stable across repeated requests on 2026-09-27; needs the same page observed before and after a Learn build (`x-buildversion` header) to know whether ETag alone can signal content changes. (topic: agents/doc-change-detection)
  - Resolved 2026-09-27: Wayback captures of the ConfigMgr introduction page (S-qvogwadn) share `Last-Modified` 2025-12-11 but carry different `x-buildversion` values and different ETags, so the ETag also changes on a rebuild without a content change. (topic: agents/doc-change-detection)

## agents/hybrid-retrieval

- **Does any MCP client turn MCP tool results into Claude `search_result` blocks?** The MCP 2026-07-28 tool result has no citation content type; the Claude Code docs mention `search_result` only for web search errors. Looked in code.claude.com docs (rg `search_result`, `citations`) 2026-09-27. Needs Claude Code or Agent SDK release notes. (topic: agents/hybrid-retrieval)
  - Tried 2026-09-27: platform.claude.com search-results page (S-4c46o537: blocks come only from the caller's own `tool_result`, no MCP mention), the MCP connector page (S-qpqoaaqj: `mcp_tool_result` example is text only), claude-code-docs rg `search_result`. No conversion documented; recorded in the article as a DER absence. (topic: agents/hybrid-retrieval)
- **How Model2Vec pools token vectors at inference, and whether a shipped vector table can be evaluated without `numpy`.** The v0.9.0 README (S-aqnin65g) describes distillation into per-token static embeddings but not the pooling step or the model file format. Looked in the README 2026-09-27. Needs minish.ai inference docs or `model2vec/model.py` at v0.9.0 (a CODE source). (topic: agents/hybrid-retrieval)

## agents/instruction-and-context-limits

- **Character limit of the Claude Projects instructions field.** The support article (S1859, re-read 2026-09-27) publishes no number; the field shows a live counter only inside the signed-in claude.ai UI. Tried 2026-09-27: S1859 re-read; Claude in Chrome was unavailable, and the counter is only visible in the signed-in UI, so reading it stays with a person. (topic: agents/instruction-and-context-limits)
  - Tried 2026-09-28, still open: S1859 re-read with curl, still no number; the article now records only that absence. Reading the counter needs a signed-in claude.ai session. (topic: agents/instruction-and-context-limits)
- **how do I limit Windows Sandbox memory allocation through a wsb configuration file** The kb was asked this in a logged lookup of 2026-09-28, and no article answered it (query log finding F-23ff28af78ac). Looked in the kb 2026-09-28: `rag.py pack` gives `weak`, with this topic in the lead. Needs an official source that states it (`/kb-research`, or the query log's opt-in research). (topic: agents/instruction-and-context-limits)
  - Resolved 2026-09-28: `<MemoryInMB>` in the `.wsb` file sets the sandbox memory (raised to 2048 MB when too small to boot; a default sandbox gets at most 4 GB), and no WindowsSandbox policy sets memory (S-hlmmxoye, S-bgz3uymb); written in the new topic windows/windows-sandbox, answer QK-i-limit-windows-sandbox-memory-control. The entry sat under this topic by a mismatch of the pack. (topic: windows/windows-sandbox)

## intune (complete articles)

- Remaining UNK lines in complete intune articles, re-checked 2026-09-27: macOS Managed Apple ID, EnrollMyMac, DEM 1,000 and direct enrollment now DOC (S-fxcmmurx, S-gjyh2735, S-ischppkc; no USB statement found, the claim was dropped); Linux Azure VM and GNOME DOC (S-dnply3ya, which also contradicts BYOD support, see _conflicts.md), packages.microsoft.com DOC (S-kakqvkfa), custom compliance join-state prerequisites absent from the current page (DER); Data Warehouse connector v1 timing DOC from the what's new entry (S-7x2lmxhr); remote help CA for unattended sessions and iOS ACME re-enrollment remain undocumented (DER absences); the reports generalisation is now tagged DER. (topic: intune/macos-management)

## entra/agent-id

- Four UNK lines re-checked 2026-09-27: report-only support for agent CA policies is DOC (S-sxxqhpa2); the Copilot Studio vs pro-code blueprint model is DOC on the Agent 365 page but contradicted by Entra planning guidance (S-ketmxnue vs S-3tt3ywvk, see _conflicts.md); 'risk signals feed the Agent Registry with automatic remediation' is found only in the Learn search index copy of the Agent ID overview, not the live page (recorded as DER); the cutover-date line is now DER pointing to _conflicts.md. (topic: entra/agent-id)

## defender/mde-onboarding

- **Microsoft Purview endpoint DLP onboarding requirements for Windows devices** (supported Windows versions, how onboarding relates to Defender for Endpoint onboarding, the licence): a benchmark lookup found no fact on it; the pack came back `weak` with a `check:` line (`mde-onboarding.md` never mentions DLP or Purview), and a keyword form of it a false `good`. Looked in the kb 2026-09-28 (`rag.py pack`, `rag.py search` for Purview and DLP). Needs the Microsoft Learn Purview endpoint DLP onboarding pages. (topic: defender/mde-onboarding)

## python/uv-projects

- **Installing Python packages behind a corporate proxy or from an internal package index** (pip and uv index settings, proxy variables, custom CA certificates, offline installs): a real lookup came back `weak` with only unrelated supply-chain facts. Looked in the kb 2026-09-28 (`rag.py pack`, grep for index-url, PIP_INDEX_URL, UV_INDEX, proxy in `python/`). Needs the pip configuration and uv index and network docs. (topic: python/uv-projects)

## python/stdlib-windows-portability

- **Whether a detached child started by a Claude Code hook on Windows survives the hook's exit** (a job object that kills children on close, and whether `CREATE_BREAKAWAY_FROM_JOB` is needed): not in the Claude Code hooks reference or the Python subprocess docs, looked 2026-09-28. Needs a Windows test of the `SessionEnd` launcher (query-log item 4). (topic: python/stdlib-windows-portability)
  - Tried 2026-09-28: the launcher (`_tools/querylog.py launch`) now adds `CREATE_BREAKAWAY_FROM_JOB` and falls back without it when the job refuses breakaway. On macOS the detached distill wrote its run file after the launcher exited and after its process group was killed (`_tools/test_querylog.py`, TestLaunch). The Windows test, which runs the launcher inside a kill-on-close job that allows breakaway, has not run on Windows yet; still missing: that run, and what job, if any, Claude Code puts hook processes in on Windows. (topic: python/stdlib-windows-portability)

## claude/hooks

- **The shape of `tool_response` for an MCP tool call in `PostToolUse`.** The hooks reference documents `tool_response` as "the result it returned" with a per-tool schema, and shows it for Write, Bash, Agent and ExitPlanMode, but not for an MCP tool (searched `code.claude.com/docs/en/hooks.md` for `tool_response` and `MCP`, 2026-09-28). The query log capture reads it defensively (a string, a content-block list or an object). [UNK] (topic: claude/hooks)
- **Which hook input fields identify a subagent (agent_id, agent_type) in PostToolUse?** The kb was asked this in a logged lookup of 2026-09-28, and no article answered it (query log finding F-6c75fa8a8950). Looked in the kb 2026-09-28: `rag.py pack` gives `weak`, with this topic in the lead. Needs an official source that states it (`/kb-research`, or the query log's opt-in research). (topic: claude/hooks)
  - Resolved 2026-09-28: common input fields `agent_id` (only inside a subagent) and `agent_type` identify the subagent in `PostToolUse` and other tool events (S743), and the Agent SDK sets them per language (S-av5665nf); answer QK-hook-input-fields-identify-subagent-posttooluse. (topic: claude/hooks)

## gitlab/automated-merge-requests

- The exit code of `glab auth status` when the host is not signed in: the generated command page (S-d6wuvfpd, gitlab-org/cli @37ebe99d `docs/source/auth/status.md`) describes the checks and flags but no exit status (2026-09-28). [UNK] (topic: gitlab/automated-merge-requests)
- A failure fingerprint for deduplicating automatic bugs from red pipelines: GitLab's and GitHub's docs describe the job and check-run status fields (already cited here) but neither documents a signature or grouping key for a repeated CI failure, so the fingerprint scheme is the project's own design, not a vendor fact. Looked in docs.gitlab.com and the kb 2026-09-29. [UNK] (topic: gitlab/automated-merge-requests)

## security/management-plane-hardening

- **what benchmarks tell us?** The kb was asked this in a logged lookup of 2026-09-28, and no article answered it (query log finding F-27b9b6ccd368). Looked in the kb 2026-09-28: `rag.py pack` gives `weak`, with this topic in the lead. Needs an official source that states it (`/kb-research`, or the query log's opt-in research). (topic: security/management-plane-hardening)
  - Superseded 2026-09-28: not a gap: the judge found the logged lookup answered, and a weak pack with such a judgement is not a miss. (topic: security/management-plane-hardening)

## claude/plugins

- **CLAUDE_PLUGIN_DATA directory location plugin-dir inline** The kb was asked this in a logged lookup of 2026-09-28, and no article answered it (query log finding F-b3b7f7b7c766). Looked in the kb 2026-09-28: `rag.py pack` gives `good`, with this topic in the lead. Needs an official source that states it (`/kb-research`, or the query log's opt-in research). (topic: claude/plugins)
  - Resolved 2026-09-28: `${CLAUDE_PLUGIN_DATA}` is `~/.claude/plugins/data/<id>/` with non-alphanumeric characters other than `_` and `-` replaced by `-` (S-i7if5i7z), so a `--plugin-dir` plugin (`<name>@inline`, S-toe7z3kj) uses `data/<name>-inline/`; answer QK-claude-plugin-data-plugin-loaded-plugin. (topic: claude/plugins)

## agents/codebase-mapping

- **Machine-readable Gradle dependency output.** The Gradle 9.8.0 Viewing Dependencies page documents only the text tree of `gradle dependencies` (searched for "json" and "machine", 2026-09-28); a JSON map likely needs the Tooling API or a custom task, not read yet. (topic: agents/codebase-mapping)
- **`go vet -json` output schema.** cmd/go at go1.27.1 documents the flag ("emit JSON output") but not the schema; the cmd/vet or `golang.org/x/tools/go/analysis/unitchecker` docs were not read (2026-09-28). (topic: agents/codebase-mapping)
- **`npm ls --json` output shape.** The npm-ls page at v11.20.0 describes the tree but no JSON schema (2026-09-28). (topic: agents/codebase-mapping)
- **TypeScript 7 native `tsc` and `--showConfig`/`--listFilesOnly`/`--explainFiles`.** The TypeScript website pages (commit 6556b08) are not versioned by release; whether the native 7.x compiler supports the same flags was not checked (2026-09-28). (topic: agents/codebase-mapping)
- **Dev container `image` pinned by digest.** The devcontainer.json reference (spec @c95ffee) names a registry image but says nothing about `@sha256:` digests for `image`; only Features have digests in the lock file (2026-09-28). (topic: agents/codebase-mapping)
- **Minimum SDK for `dotnet package list --vulnerable`.** The dotnet-package-list page ties "9.0.300" to `<AuditSources>` in a sentence that may or may not date the option itself (2026-09-28). (topic: agents/codebase-mapping)

## windows/powershell-static-analysis

- **Explicit statement that `Parser.ParseFile` does not run the script.** The Parser, ParseFile and ParseInput API pages describe parsing only; no sentence says in so many words that nothing executes (Learn, 2026-09-28). (topic: windows/powershell-static-analysis)
- **Full `DiagnosticRecord` field list.** Invoke-ScriptAnalyzer and Using PSScriptAnalyzer show `RuleName`, `Severity`, `ScriptName`, `Line`, `Message` and `SuggestedCorrections` in examples, not a field reference (2026-09-28). (topic: windows/powershell-static-analysis)

## agents/coding-agent-codebase-context

- **Gemini CLI: just-in-time ancestor loading versus an eager subdirectory scan.** At v0.61.0 `docs/cli/gemini-md.md` describes GEMINI.md files loaded when a tool touches a directory (ancestors up to a trusted root), while `docs/reference/configuration.md` describes a scan below the working directory limited to 200 directories; which one current builds do, or both, was not settled from the docs (2026-09-28). (topic: agents/coding-agent-codebase-context)
- **Cursor embeddings-based codebase indexing.** Older Cursor docs URLs for codebase indexing and semantic search now redirect to the Search page, which describes a local Instant Grep index with no stored embeddings; no current official page describes an embeddings index (checked cursor.com docs, security and data-use pages, 2026-09-28). (topic: agents/coding-agent-codebase-context)
- **VS Code local workspace index size limits.** The workspace-context page (DateApproved 9/16/2026) states no file-count limits for a local index (2026-09-28). (topic: agents/coding-agent-codebase-context)

## agents/copilot-studio-mcp-client

- **MCP connectors over the delegated subnet or the on-premises data gateway.** Custom connectors are VNet-supported (S-kyrgum3q) and gateway-capable in Power Automate (S-6x6bb2f3), but no page states that a connector with `x-ms-agentic-protocol: mcp-streamable-1.0` runs through either; checked the Copilot Studio MCP pages (S1964, S-rstajp7g, S-m75y4u2y, S-rvnsf5ty), the Copilot Studio VNet page (S-gcbkqdo3) and the custom connector overview (S-nt2bmgtl) on 2026-09-29. Needs a lab test or a Microsoft statement. (topic: agents/copilot-studio-mcp-client)
- **Copilot Studio's MCP client protocol details.** The protocol version it sends in `initialize`, whether it keeps `Mcp-Session-Id` sessions, whether it reads server `instructions` or tool annotations, and which tool-result content types (text, image, embedded resource, `structuredContent`) it shows are not documented on the Copilot Studio MCP pages, the GitHub Copilot harness MCP page (S-adugdkcv) or the Azure MCP Server guide (S-wpjbqofq), read 2026-09-29. Needs a request log from a test server. (topic: agents/copilot-studio-mcp-client)
