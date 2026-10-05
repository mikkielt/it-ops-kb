---
topic: agents/agent-evaluation
priority: P1
applies_to: "MCP Inspector v2, Inspect 0.x (AISI), DeepEval, promptfoo, PyRIT 1.1.0, garak, OpenAI evals (deprecating), tau-bench/tau2-bench v1.0.1, Anthropic eval guidance 2026-01, azure-ai-evaluation SDK + AI Red Teaming Agent (preview), OpenAI cookbook self-evolving agents (commit 2182005b), promptfoo assertions (commit e6b46046), Claude Code plugin evals (2026-09)"
retrieved_utc: 2026-10-06
sources: [S-w2g2bnsw, S-h7tjbts3, S1880, S1881, S1883, S1884, S1885, S1886, S1887, S1888, S1889, S1890, S1891, S1892, S1893, S1894, S1895, S1896, S1898, S1899, S1900, S1901, S1902, S1903, S1904, S1905, S1935, S-zfg6jhgr, S-onkwuwst, S-p7dq3fku, S-6jcocxnl, S-wwrpen3s, S1920, S-lkcsn2fs, S-m2glighe, S-ll5srdcw]
status: complete
---

# Evaluating and stress-testing an agent against a self-hosted MCP server

## Summary
Six tool families cover evaluating an agent through a self-hosted MCP server: a protocol-level inspector
(MCP Inspector), general LLM/agent eval frameworks that added MCP support (DeepEval, Inspect, OpenAI evals),
an MCP-aware red-team/load tool (promptfoo), and pure security fuzzers (garak, PyRIT) that can point at an
MCP-exposed target. Vendor guidance (Anthropic, OpenAI) converges on: start with a small (20-50 row) golden
set drawn from real failures, prefer deterministic graders, use LLM graders only where necessary, and run
regression suites continuously once a task earns a place there. A seventh family is vendor-hosted rather than
self-run against the MCP server directly: Microsoft's **Azure AI Evaluation SDK** (`azure-ai-evaluation`)
ships agentic evaluators (IntentResolution, ToolCallAccuracy, TaskAdherence, Relevance, Groundedness) and an
`evaluate()` batch runner, plus a PyRIT-based **AI Red Teaming Agent** for automated adversarial scanning
scored by Attack Success Rate — both are Foundry-project tools, not MCP-native, but cover the same
capability/safety-eval ground for an agent that happens to be hosted in Azure AI Foundry.

## Facts
### QG9: tools and methods
- **MCP Inspector** is the protocol's reference tool for testing and debugging MCP servers: one package,
  `@modelcontextprotocol/inspector` (Node 22.19.0 or newer), with three clients on a shared core — a web UI
  (default), `--cli` (a scriptable, machine-readable client for CI, shell pipelines and coding agents, with
  `--format json`) and `--tui` (terminal UI); it launches a local stdio server from a command or connects to
  a remote server over HTTP. [DOC S1880, S1881]
- MCP Inspector's licence is mixed: new code is Apache-2.0, documentation (excluding the spec) is
  CC-BY-4.0, and code contributed under the original MIT terms without relicensing consent stays MIT. [DOC S1881]
- MCP Inspector measures **protocol-level correctness**: it lists a server's tools/resources/prompts and
  lets a human or script invoke them; it does not itself grade task success. [DOC S1880, S1881]
- **Anthropic's "Writing effective tools for agents"** (2025-09-11) is guidance for authoring tools, not a
  test harness, but its principles (clear namespacing, meaningful context in responses, token-efficient
  output, pagination/filtering/truncation with sensible defaults) are the properties a stress-test should
  check for. [DOC S1935]
- **promptfoo**'s MCP provider calls MCP tools directly against a `command`/`args` (stdio) or `path`
  target, and asserts on the tool's response (contains, valid-JSON, which tool was routed to); it does not
  compute a benchmark-style pass rate on its own — assertions are configured per test case. [DOC S1883]
  Promptfoo itself is MIT-licensed. [DOC S1885]
- promptfoo's red-team mode adds MCP-specific plugins (an "mcp" plugin for protocol vulnerabilities),
  general jailbreak/multi-turn strategies, authorization probes (`bfla`, `bola`), `pii` and `sql-injection`
  plugins, with "Tool Poisoning Attacks" (hidden instructions in tool descriptions) called out as a primary
  MCP-specific concern. [DOC S1884]
- **Inspect (`inspect_ai`)**, from the UK AI Security Institute, is MIT-licensed and built for "prompt
  engineering, tool usage, multi-turn dialog, and model graded evaluations," including a built-in ReAct
  agent and bridges to run externally-built agents (e.g. LangChain) inside its eval harness; it ships 200+
  pre-built evaluations. [DOC S1886, S1887]
- Inspect consumes MCP servers as tool sources for the agent under evaluation: `mcp_server_stdio()`
  launches a local server from a command and args, alongside `mcp_server_http()`, `mcp_server_sandbox()`
  (a server running inside an Inspect sandbox) and a deprecated `mcp_server_sse()`; the server object is
  passed wherever a `tools` list is accepted, for example `react(tools=[server])`. [DOC S-wwrpen3s, S1887]
- **DeepEval** (Apache-2.0) lists three MCP metrics in its README: MCP Task Completion (how well an MCP-based
  agent accomplishes a task), MCP Use (how well it uses its available MCP servers) and Multi-Turn MCP Use
  (MCP use across conversation turns). [DOC S1889]
- DeepEval's MCP page imports `MCPUseMetric` for single-turn `LLMTestCase`s and `MultiTurnMCPMetric` for
  multi-turn `ConversationalTestCase`s; its `ToolCorrectnessMetric` matches a call's type as well as its name,
  so an MCP tool call does not pass against an expected plain function call of the same name. [DOC S1888] Its `MCPServer` config
  object accepts `transport="stdio"` for connecting to a local stdio server, though the transport value
  itself "does not affect the evaluation." [DOC S1888]
- **OpenAI evals**: the `openai/evals` repository (MIT) is the open-source registry/framework; OpenAI's own
  cookbook has a worked MCP-evaluation notebook using its Evals API. [DOC S1893, S1895] As of the retrieval
  date, OpenAI states its hosted **Evals platform becomes read-only 2026-10-31 and shuts down 2026-11-30**
  — a live deprecation relevant to any plan that depends on it going forward. [DOC S1894]
- **garak** (NVIDIA) is an Apache-2.0 LLM vulnerability scanner (its LICENSE file) that probes
  for hallucination, data leakage, prompt injection, misinformation, toxicity and jailbreaks against a
  configured generator/target; MCP-specific target support exists only through third-party wrappers
  (e.g. a community "Garak-MCP" MCP server exposing garak) rather than a garak-shipped MCP client; a
  community NVIDIA/garak issue proposing native MCP/OWASP-MCP-Top-10 scanning was closed by its author on
  2026-05-12 without an MCP probe or generator shipping in garak. [DOC S1890, S1891; COMMUNITY S1903]
- **PyRIT** (Microsoft, MIT, v1.1.0/2026-09-04) is a red-teaming framework whose built-in targets are
  OpenAI-family and Azure ML chat targets, a LiteLLM chat target (for other providers), Hugging Face,
  custom HTTP/WebSocket endpoints and Playwright web-app targets, plus a "build your own" `PromptTarget`
  interface. The 1.x line removed the `pyrit.orchestrator` module: cross-domain/indirect prompt injection
  (instructions planted in a data source the model later reads) is now `XPIAWorkflow` in
  `pyrit.executor.workflow`, the relevant mechanism for testing injection via MCP tool results. The
  v1.1.0 release has no MCP target class; the unreleased main branch (1.2.0.dev0) adds an
  `MCPToolProvider` that gives a target the tools of one stdio or streamable-HTTP MCP server. [DOC S1892]
- **MCP fuzzers/load tools** exist only as community projects at this date: `mcp-fuzz` (launches a command
  as a stdio MCP server, lists its tools, and fires schema-derived inputs at each), `mcp-server-fuzzer`
  (stdio/HTTP/SSE/streamable-HTTP), `mcp-guard` and `mcpsec` (adversarial/runtime-probe fuzzers covering
  shell injection, SSRF, overflow, type confusion). None are vendor/official; treat as `COMMUNITY` evidence
  only. [COMMUNITY S1901, S1902, S1904, S1905]

### QG13: Azure AI Foundry evaluation SDK and AI Red Teaming Agent (vendor-hosted alternative to the self-hosted tools above)
- The **Azure AI Evaluation SDK** is a separate pip package, `azure-ai-evaluation` (`pip install azure-ai-evaluation`); its agentic evaluators
  (`IntentResolutionEvaluator`, `ToolCallAccuracyEvaluator`, `TaskAdherenceEvaluator`) plus `RelevanceEvaluator` and `GroundednessEvaluator`
  are the agent-focused subset of a larger catalogue that also has quality (Coherence/Fluency/QA), textual-similarity/NLP
  (Similarity/F1/BLEU/GLEU/ROUGE/METEOR), RAG (Retrieval/DocumentRetrieval/Groundedness/GroundednessPro/Relevance/ResponseCompleteness),
  risk-and-safety (Violence/Sexual/SelfHarm/HateUnfairness/IndirectAttack/ProtectedMaterial/UngroundedAttributes/CodeVulnerability/ContentSafety)
  and Azure OpenAI grader (Label/StringCheck/TextSimilarity/Grader) categories. [DOC S-zfg6jhgr]
- `ToolCallAccuracyEvaluator` requires `tool_definitions` and either `response` or `tool_calls`; `GroundednessEvaluator` requires
  `tool_definitions` when scoring an agent's groundedness against the tool outputs it received; both, plus `IntentResolutionEvaluator` and
  `TaskAdherenceEvaluator`, accept either simple `query`/`response` strings or full OpenAI-style message lists (`query` must start with the
  agent's system message). All built-in AI-assisted quality/agentic evaluators output a numeric score plus a `pass`/`fail` result against a
  configurable threshold and a natural-language reason. [DOC S-zfg6jhgr, S-6jcocxnl]
- AI-assisted evaluators need a GPT judge model (`gpt-35-turbo`, `gpt-4`, `gpt-4-turbo`, `gpt-4o` or `gpt-4o-mini` in `model_config`) except
  risk-and-safety evaluators and `GroundednessProEvaluator`, which instead take `azure_ai_project` and call a Foundry backend service;
  reasoning-model judges (e.g. Azure OpenAI/OpenAI o-series) are supported for the agentic/quality evaluators by passing
  `is_reasoning_model=True`. Token budget for evaluator generation is `max_token=800` for most AI-assisted evaluators, 1600 for
  `RetrievalEvaluator`, and 3000 for `ToolCallAccuracyEvaluator` (to fit longer tool-call inputs). [DOC S-zfg6jhgr, S-6jcocxnl]
- `ToolCallAccuracyEvaluator` in Foundry Agent Service evaluation supports scoring these tool types: File Search, Azure AI Search, Bing
  Grounding, Bing Custom Search, SharePoint Grounding, Code Interpreter, Fabric Data Agent, OpenAPI, and user-defined Function Tools; an
  unsupported tool type in the run is scored `pass` with a reason noting the tool isn't evaluated, so wrapping it as a Function Tool is the
  way to force evaluation. [DOC S-6jcocxnl]
- The `evaluate()` API runs a set of evaluators over a JSONL dataset (or against a callable `target` that is queried first) and needs an
  explicit `evaluator_config` `column_mapping` (e.g. `${data.queries}`, `${outputs.response}`) per evaluator or via `"default"`; results
  return aggregate `metrics` plus per-row `rows`, and an `output_path` writes a JSON metrics/rows/Foundry-URL summary; passing
  `azure_ai_project` also logs the run and returns a `result.studio_url` link. [DOC S-zfg6jhgr]
- The **AI Red Teaming Agent** (preview) is Foundry's PyRIT-based adversarial-scan tool, installed as the `redteam` extra —
  `pip install "azure-ai-evaluation[redteam]"` — and requires Python 3.10-3.13 (3.9 unsupported); it instantiates as
  `RedTeam(azure_ai_project=..., credential=DefaultAzureCredential())` and scans a target via `.scan(target=...)`, where `target` can be an
  Azure OpenAI model config, a simple string-in/string-out callback, an OpenAI-Chat-Protocol-shaped async callback, or (for PyRIT users) a
  PyRIT `PromptChatTarget`. It supports only single-turn, text-only interactions. [DOC S-onkwuwst, S-p7dq3fku]
- Default scan scope without parameters: 4 risk categories (`Violence`, `HateUnfairness`, `Sexual`, `SelfHarm`) x 10 attack objectives each
  = 40 attack prompts (`num_objectives` default 10, `risk_categories` default all four); maximum attack objectives per risk category are
  `Violence`/`HateUnfairness`/`Sexual`/`SelfHarm` 100, `ProtectedMaterial` 200, `UngroundedAttributes` 200, `CodeVulnerability` 389. Custom
  attack seed prompts (JSON, one risk type per entry: `violence`/`sexual`/`hate_unfairness`/`self_harm`) can replace the curated set via
  `custom_attack_seed_prompts=`. [DOC S-onkwuwst]
- Attack strategies wrap the baseline adversarial query in an encoding/obfuscation to test past safety alignment; grouped by complexity —
  `EASY` (`Base64`, `Flip`, `Morse`), `MODERATE` (`Tense`), `DIFFICULT` (a composition of `Tense`+`Base64`) — or specified individually from a
  larger list (`AnsiAttack`, `AsciiArt`, `AsciiSmuggler`, `Atbash`, `Base64`, `Binary`, `Caesar`, `CharacterSpace`, `CharSwap`, `Diacritic`,
  `Flip`, `Leetspeak`, `Morse`, `ROT13`, `SuffixAppend`, `StringJoin`, `UnicodeConfusable`, `UnicodeSubstitution`, `Url`, `Jailbreak` (UPIA),
  `IndirectAttack` (XPIA via tool/context outputs), `Tense`, `Multiturn`, `Crescendo`); `AttackStrategy.Compose([a, b])` chains exactly two
  strategies (e.g. Base64 then ROT13). Supported non-English scan languages: Spanish, Italian, French, Japanese, Portuguese, Simplified
  Chinese, via `SupportedLanguages`. [DOC S-onkwuwst, S-p7dq3fku]
- The reported metric is **Attack Success Rate (ASR)** — percent of attacks that elicited an undesirable response — broken out per risk
  category and per attack-complexity tier in an `output_path` JSON scorecard, plus row-level `redteaming_data` with each conversation,
  `attack_success`, `attack_technique`, `attack_complexity` and per-category `risk_assessment` (severity label + reason, e.g. "Refusal
  message detected"). [DOC S-onkwuwst]
- The AI Red Teaming Agent is region-restricted (only some Foundry-project regions support it) and its "local" mode (installed via the
  `redteam` extra and run outside the Foundry portal) is explicitly **not compatible with the new Foundry portal and SDK**; the page's
  setup takes either a Foundry Hub project (subscription/resource group/project dictionary) or a Foundry project endpoint. [DOC S-onkwuwst]
- Microsoft's AI Red Teaming Agent concept page frames the tool within NIST's Map/Measure/Manage functions, recommends automated scans
  at design, development, pre-deployment and (as scheduled runs) post-deployment, and states that the most effective risk assessment
  combines automated tools with expert human analysis; agent-specific risk categories (prohibited actions, sensitive data leakage, task
  adherence) run only in cloud red teaming. [DOC S-p7dq3fku]

### QG10: building a question baseline (golden set)
- Anthropic: start small — "20-50 simple tasks drawn from real failures is a great start" — because
  early-stage agents show large effect sizes from changes; three grader types are named: code-based (fast,
  cheap, objective — string match, static analysis, outcome checks), model-based (rubric scoring, natural
  language assertions), and human (SME review, crowdsourced judgment, spot-check sampling); the guidance is
  to prefer deterministic graders where possible and LLM graders only where necessary. [DOC S1896]
- Anthropic names `pass@k` (probability of ≥1 success across k attempts) and `pass^k` (probability all k
  trials succeed) as agent metrics, alongside token usage, latency, cost per task and error rates. [DOC S1896]
- Anthropic: regression suites should hold "nearly 100% pass rate" and run continuously to catch drift;
  tasks that graduate from a capability eval become part of the ongoing regression suite. [DOC S1896]
- Anthropic: contamination/flakiness control — "each trial should be isolated by starting from a clean
  environment. Unnecessary shared state... can cause correlated failures." [DOC S1896]
- Anthropic's platform docs on defining success criteria recommend detailed rubrics with hard pass/fail
  language (e.g. a required phrase, otherwise automatically "incorrect"), and for LLM-based grading, asking
  the grading model to reason first and then discarding the reasoning before emitting the score, which the
  docs state increases grading accuracy on complex judgment tasks. [DOC S1898]
- OpenAI's evaluation best-practices guidance: combine metrics with human judgment, adopt "eval-driven
  development" (evaluate early and often, write scoped tests at every stage), grade with the most capable
  model available, prefer pairwise or pass/fail judgments and control for length bias, and validate the
  judge's agreement with human labels before scaling up, since model grading carries its own error rate. [DOC S1894]
- τ-bench (Sierra) is the origin of the `pass^k` metric applied to tool-agent-user interaction tasks and
  reported a reliability gap (e.g. GPT-4o at 61% pass@1 but 25% pass@8 on retail tasks in the original
  2024 paper); τ2-bench/τ3-bench (MIT-licensed repository, v1.0.1, 2026-07) continue the line and define
  task grading via `evaluation_criteria.actions` and a `reward_basis` gate. [DOC S1899, S1900]

### Judging a retriever against labelled queries
- The BEIR benchmark's evaluation data format is a corpus, queries and qrels (relevance judgements), so a retriever is judged against queries whose relevant documents are known [DOC S-w2g2bnsw].
- BEIR's toolkit provides the standard IR metrics for any top-k cutoff: precision, recall, MAP, MRR and nDCG [DOC S-w2g2bnsw].
- BEIR chose nDCG@k because it gives a good balance for tasks with binary as well as graded relevance judgements [DOC S-w2g2bnsw].
- Microsoft Foundry's document-retrieval evaluator describes its Fidelity metric as the number of good documents returned out of the total number of known good documents in a dataset, a recall-style score against labelled ground truth [DOC S-h7tjbts3].
- The same evaluator reports Holes, the number of documents with missing query relevance judgments (ground truth), so a labelled set has to judge the documents the retriever returns [DOC S-h7tjbts3].

### Rule-based and code-based checks before a model judge (graders, evals, self-improving pipelines)
- Anthropic's eval guidance names the methods of a **code-based grader**: string-match checks (exact, regex, fuzzy),
  binary tests (fail-to-pass, pass-to-pass), static analysis (lint, type, security), outcome verification,
  tool-call verification (tools used, parameters) and transcript analysis (turns taken, token usage). It lists them as
  fast, cheap, objective, reproducible and easy to debug, and as brittle to valid variations, lacking in nuance and
  limited for subjective tasks. [DOC S1896]
- The same guidance lists **model-based graders** (rubric scoring, natural-language assertions, pairwise comparison,
  reference-based evaluation, multi-judge consensus) as flexible and able to handle open-ended, freeform output, but
  non-deterministic, more expensive than code, and needing calibration against human graders. [DOC S1896]
- Anthropic advises "deterministic graders where possible, LLM graders where necessary or for additional flexibility",
  with human graders used judiciously for validation. For a coding agent it says evaluations typically rely on unit
  tests for correctness and an LLM rubric for overall code quality, with further graders added only as needed. [DOC S1896]
- Anthropic warns that checking a fixed sequence of tool calls is too rigid, because agents find valid approaches the eval
  designer did not expect; it is often better to grade what the agent produced than the path it took. A rule that rejects
  valid output is a grading bug: Opus 4.5 first scored 42% on CORE-Bench and reached 95% once the grading, task-spec and
  reproducibility problems were fixed, among them rigid grading that penalised "96.12" where "96.124991..." was expected. [DOC S1896]
- Per task, Anthropic describes three ways to combine graders: weighted (the combined score must reach a threshold), binary
  (every grader must pass) or a hybrid. Automated evals are the first line of defence before launch and in CI/CD on each
  agent change; systematic human studies are reserved for calibrating LLM graders or judging subjective output. [DOC S1896]
- Anthropic's platform docs rank grading methods by "fastest, most reliable, most scalable": code-based grading (exact
  match, string match) first, as fastest and most reliable but lacking nuance; LLM-based grading is fast, flexible and suited
  to complex judgment but to be tested for reliability before scaling; human grading is flexible and high quality but slow and
  expensive, "avoid if possible". [DOC S1898]
- OpenAI's evaluation guidance calls exact match, string match, ROUGE/BLEU, function-call accuracy and executable evals
  "metric-based evals": numerical scores for filtering, ranking and automated regression testing, which may not fit a use
  case and may miss nuance; it notes model judges are cheaper and more scalable than human evaluation. [DOC S1894]
- `claude plugin eval` splits its graders by cost. `regex`, `tool_used`, `tool_order` and `file_exists` are computed from the
  transcript and files and cost nothing; `llm` and `baseline` call a judge model (a small fast model by default) and add to
  the run's cost, three short judge calls per such grader per run, with an `llm` grader passing on at least two of three
  PASS votes. [DOC S-lkcsn2fs]
- The plugin-eval page says an `llm` grader can answer differently between runs, more so the longer the text it reads: grade a
  long output such as a generated file with a `regex` grader over its contents, and keep `llm` graders for short output. It
  also advises one grader on the result (final message or produced file) and one on the steps (`tool_used`, `tool_order`). [DOC S-lkcsn2fs]
- For predictable CI cost the plugin-eval page says to give quick every-change suites only graders that call no judge. With
  `--max-cost-usd` set, nothing further starts once the ceiling is spent, and a run whose judge graders were skipped is
  flagged `skippedPaidGraders`, its score not comparable and to be left out of trend charts. [DOC S-lkcsn2fs]
- promptfoo groups its assertions into "deterministic eval metrics" (programmatic tests run on the output, such as `equals`,
  `contains`, `regex`, `is-json`, `is-sql`, function-call schema checks, `latency`, `cost`) and "model-assisted eval metrics"
  (which rely on LLMs or other models, such as `llm-rubric`, `factuality` and embedding-based `similar`); the page says some
  assertions (`similar`, `llm-rubric`, `model-graded-*`) require an LLM provider. Each assertion takes a `weight`, and some a
  `threshold`. [DOC S-ll5srdcw]
- For agent traces promptfoo has both kinds: `trajectory:tool-used`, `trajectory:tool-args-match` and
  `trajectory:tool-sequence` are deterministic checks on the traced tool calls, while `trajectory:goal-success` uses an LLM
  judge to decide whether the run achieved its goal. [DOC S-ll5srdcw]
- Anthropic's "Building effective agents" says a prompt-chaining workflow can add programmatic checks (a "gate") on any
  intermediate step to ensure the process is still on track, and that the workflow trades latency for accuracy by making each
  LLM call an easier task. Its evaluator-optimizer workflow (one LLM call generates, another evaluates and gives feedback in a
  loop) fits when there are clear evaluation criteria and iterative refinement gives measurable value. [DOC S1920]
- OpenAI's self-evolving agents cookbook describes a self-improving loop: a baseline agent's output gets feedback from human
  reviewers or an LLM-as-a-judge, new prompts are tested through evals, and the outcomes are combined into an aggregated
  score; the loop runs until the score passes a target (its example: 0.8) or the retries run out (its example: 10), and at
  the limit engineers are alerted that manual improvement is needed. [DOC S-m2glighe]
- That cookbook's eval balances "deterministic checks with semantic judgment" in four graders, each with its own pass
  threshold: two `python` graders (exact chemical names from the source appear in the summary; length close to 100 words),
  a `text_similarity` grader (cosine similarity to the source) and a rubric-driven `score_model` LLM judge. It says the
  Python graders catch domain fidelity and length discipline early, which stabilizes optimization before semantic tuning,
  and the LLM judge is a failsafe when edge cases slip past the deterministic checks. [DOC S-m2glighe]
- The cookbook's own takeaways from that loop: optimization is not always successful, so being able to roll back the prompt
  version matters, and the fidelity of the graders' information is crucial to a quality optimization. It keeps the prompt with
  the highest cumulative grader score (ties go to the latest), not merely the last one that passed. [DOC S-m2glighe]
- Derived order for a self-improving pipeline in this kb's frame (a lookup pipeline whose findings come from logged
  questions, or a docs-maintenance job): run the deterministic rules first (contract and id checks, link and lint checks,
  exact-match and outcome checks) and send only what passes them, or what no rule can decide, to a model judge. The sources
  give a cost and reliability ranking and a gate between model steps, and they combine graders by weight or threshold; none
  states a run order for rule graders and judge graders, so the order is a design choice, not a vendor rule. [DER S1896, S1898, S-lkcsn2fs, S1920, S-m2glighe: code-based graders are cheaper and reproducible, judge calls cost and vary, programmatic gates sit between model steps]
- Derived limits of that order: a rule is brittle and can fail good output (the CORE-Bench case), so each rule needs a planted
  failing input and a planted valid variation, and the model judge stays as the check for what rules cannot express; the
  judge itself is calibrated against human review, and a loop that edits its own prompt or rules needs a rollback and a
  retry cap, as the cookbook does. [DER S1896, S-m2glighe: brittleness of code graders, judge calibration, rollback and retry limit]

## Reference
| Tool | Licence | Stdio MCP target | What it measures | Source |
|---|---|---|---|---|
| MCP Inspector | Apache-2.0 (new)/MIT (legacy)/CC-BY-4.0 (docs) | native (launches/attaches over stdio) | protocol-level tool/resource/prompt listing and manual invocation | S1880, S1881 |
| promptfoo (MCP provider + red team) | MIT | native (`command`/`args`/`path`) | assertion pass/fail per call; red-team plugin findings (MCP, jailbreak, bfla/bola, pii, sql-injection) | S1883, S1884, S1885 |
| Inspect (`inspect_ai`) | MIT | yes, as agent tools (`mcp_server_stdio()`; also http/sandbox) | scored evals via built-in/ReAct agents and model-graded scorers | S1886, S1887, S-wwrpen3s |
| DeepEval | Apache-2.0 | yes (`MCPServer(transport="stdio")`) | MCP Task Completion, MCP Use (`MCPUseMetric`), Multi-Turn MCP Use (`MultiTurnMCPMetric`), ToolCorrectness | S1888, S1889 |
| OpenAI evals / Evals API | MIT (repo) | via custom completion functions, not MCP-native | correctness/regression across a dataset; hosted platform deprecating Oct-Nov 2026 | S1893, S1894, S1895 |
| garak | Apache-2.0 | no native MCP client; third-party wrapper only | hallucination, leakage, injection, jailbreak, toxicity probes against a generator | S1890, S1891, S1903 |
| PyRIT | MIT | no MCP target class in v1.1.0 (MCPToolProvider on unreleased main); custom-target interface + XPIAWorkflow for indirect injection | red-team attack orchestration and scoring against a configured target | S1892 |
| mcp-fuzz / mcp-server-fuzzer / mcp-guard / mcpsec | unverified (community) | yes (stdio launch) | schema-derived fuzz calls, protocol/security fault-finding | S1901, S1902, S1904, S1905 |
| Azure AI Evaluation SDK (`azure-ai-evaluation`) | Microsoft (vendor-hosted judge/backend) | not MCP-specific; agent inputs via query/response or OpenAI-style messages | IntentResolution, ToolCallAccuracy, TaskAdherence, Relevance, Groundedness (+ quality/RAG/safety/NLP evaluators); `evaluate()` batch runner | S-zfg6jhgr, S-6jcocxnl |
| AI Red Teaming Agent (`azure-ai-evaluation[redteam]`, preview) | Microsoft (PyRIT-based; local mode not compatible with the new Foundry portal/SDK) | no MCP target; scans a model config, callback, or PyRIT `PromptChatTarget` | Attack Success Rate per risk category (violence/sexual/self-harm/hate-unfairness/+) and attack-complexity tier | S-onkwuwst, S-p7dq3fku |

See also `agents/agent-planning-and-done.md` (definition of done, verification gates and task lists for agent work) and `agents/docs-maintenance-agents.md` (deterministic guardrails that run before a model reviews a documentation change).

## Examples
A DeepEval-style test case for a device-management MCP server would launch the server's stdio target, call
a device-lookup tool for `PL-LT-00123`, and grade with `MCPTaskCompletion` against the rubric "returns the identity
graph record for PL-LT-00123 without exposing an un-pseudonymized `jan.kowalski` UPN to the model."
