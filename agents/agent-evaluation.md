---
topic: agents/agent-evaluation
priority: P1
applies_to: "MCP Inspector v2, Inspect 0.x (AISI), DeepEval, promptfoo, PyRIT 0.11.0, garak, OpenAI evals (deprecating), tau-bench/tau2-bench v1.0.1, Anthropic eval guidance 2026-01"
retrieved_utc: 2026-09-25
sources: [S1880, S1881, S1883, S1884, S1885, S1886, S1887, S1888, S1889, S1890, S1891, S1892, S1893, S1894, S1895, S1896, S1898, S1899, S1900, S1901, S1902, S1903, S1904, S1905, S1935]
status: partial
---

# Evaluating and stress-testing an agent against a self-hosted MCP server

## Summary
Six tool families cover evaluating an agent through a self-hosted MCP server: a protocol-level inspector
(MCP Inspector), general LLM/agent eval frameworks that added MCP support (DeepEval, Inspect, OpenAI evals),
an MCP-aware red-team/load tool (promptfoo), and pure security fuzzers (garak, PyRIT) that can point at an
MCP-exposed target. Vendor guidance (Anthropic, OpenAI) converges on: start with a small (20-50 row) golden
set drawn from real failures, prefer deterministic graders, use LLM graders only where necessary, and run
regression suites continuously once a task earns a place there.

## Facts
### QG9: tools and methods
- **MCP Inspector** is the protocol team's own visual and CLI tool: a Vite/React web UI plus a Node proxy
  that connects to a server over stdio, SSE or streamable HTTP; the CLI mode (`--cli`) is "a scriptable
  command-line client for automation, CI, and fast agent feedback loops" and supports `--format json` for
  scripting. [DOC S1880, S1881]
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
  pre-built evaluations. [DOC S1886, S1887] Explicit stdio-MCP-target support was not confirmed in the
  fetched pages beyond a UI reference to an "MCP Registry." [UNK]
- **DeepEval** (Apache-2.0) ships three MCP-specific metrics — `MCPTaskCompletion` (did the agent finish
  the task), `MCPUseMetric`/"MCP Use" (how well the agent used the servers available to it), and
  `MultiTurnMCPUseMetric` for multi-turn MCP use — plus a `ToolCorrectnessMetric` that also matches on
  whether a call was an MCP tool call vs. a plain function call. [DOC S1888, S1889] Its `MCPServer` config
  object accepts `transport="stdio"` for connecting to a local stdio server, though the transport value
  itself "does not affect the evaluation." [DOC S1888]
- **OpenAI evals**: the `openai/evals` repository (MIT) is the open-source registry/framework; OpenAI's own
  cookbook has a worked MCP-evaluation notebook using its Evals API. [DOC S1893, S1895] As of the retrieval
  date, OpenAI states its hosted **Evals platform becomes read-only 2026-10-31 and shuts down 2026-11-30**
  — a live deprecation relevant to any plan that depends on it going forward. [DOC S1894]
- **garak** (NVIDIA) is an Apache-2.0 LLM vulnerability scanner (its LICENSE file) that probes
  for hallucination, data leakage, prompt injection, misinformation, toxicity and jailbreaks against a
  configured generator/target; MCP-specific target support exists only through third-party wrappers
  (e.g. a community "Garak-MCP" MCP server exposing garak, and an open NVIDIA/garak issue tracking native
  MCP/OWASP-MCP-Top-10 scanning) rather than a garak-shipped MCP client. [DOC S1890, S1891; COMMUNITY S1903]
- **PyRIT** (Microsoft, MIT, v0.11.0/2026-02) is a red-teaming orchestration framework whose built-in
  targets are OpenAI/Azure/Anthropic/Google/HuggingFace, custom HTTP/WebSocket endpoints, and Playwright
  web-app targets, plus a documented "build your own" target interface; it ships `XPIAOrchestrator` for
  cross-domain/indirect prompt-injection attacks (injecting instructions via a data source the model later
  reads), which is the relevant mechanism for testing injection via MCP tool results even without a
  built-in MCP target class. [DOC S1892]
- **MCP fuzzers/load tools** exist only as community projects at this date: `mcp-fuzz` (launches a command
  as a stdio MCP server, lists its tools, and fires schema-derived inputs at each), `mcp-server-fuzzer`
  (stdio/HTTP/SSE/streamable-HTTP), `mcp-guard` and `mcpsec` (adversarial/runtime-probe fuzzers covering
  shell injection, SSRF, overflow, type confusion). None are vendor/official; treat as `COMMUNITY` evidence
  only. [COMMUNITY S1901, S1902, S1904, S1905]

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
  development" (evaluate early and often, write scoped tests at every stage), grade with a different (and
  ideally stronger) model than the one being graded, and validate model-graded results against human
  evaluation before scaling up, since model grading carries its own error rate. [DOC S1894]
- τ-bench (Sierra) is the origin of the `pass^k` metric applied to tool-agent-user interaction tasks and
  reported a reliability gap (e.g. GPT-4o at 61% pass@1 but 25% pass@8 on retail tasks in the original
  2024 paper); τ2-bench/τ3-bench (MIT-licensed repository, v1.0.1, 2026-07) continue the line and define
  task grading via `evaluation_criteria.actions` and a `reward_basis` gate. [DOC S1899, S1900]

## Reference
| Tool | Licence | Stdio MCP target | What it measures | Source |
|---|---|---|---|---|
| MCP Inspector | Apache-2.0 (new)/MIT (legacy)/CC-BY-4.0 (docs) | native (launches/attaches over stdio) | protocol-level tool/resource/prompt listing and manual invocation | S1880, S1881 |
| promptfoo (MCP provider + red team) | MIT | native (`command`/`args`/`path`) | assertion pass/fail per call; red-team plugin findings (MCP, jailbreak, bfla/bola, pii, sql-injection) | S1883, S1884, S1885 |
| Inspect (`inspect_ai`) | MIT | not confirmed for MCP specifically [UNK] | scored evals via built-in/ReAct agents and model-graded scorers | S1886, S1887 |
| DeepEval | Apache-2.0 | yes (`MCPServer(transport="stdio")`) | MCPTaskCompletion, MCPUse, MultiTurnMCPUse, ToolCorrectness | S1888, S1889 |
| OpenAI evals / Evals API | MIT (repo) | via custom completion functions, not MCP-native | correctness/regression across a dataset; hosted platform deprecating Oct-Nov 2026 | S1893, S1894, S1895 |
| garak | Apache-2.0 | no native MCP client; third-party wrapper only | hallucination, leakage, injection, jailbreak, toxicity probes against a generator | S1890, S1891, S1903 |
| PyRIT | MIT | no native MCP target class; custom-target interface + XPIAOrchestrator for indirect injection | red-team attack orchestration and scoring against a configured target | S1892 |
| mcp-fuzz / mcp-server-fuzzer / mcp-guard / mcpsec | unverified (community) | yes (stdio launch) | schema-derived fuzz calls, protocol/security fault-finding | S1901, S1902, S1904, S1905 |

## Examples
A DeepEval-style test case for a device-management MCP server would launch the server's stdio target, call
a device-lookup tool for `PL-LT-00123`, and grade with `MCPTaskCompletion` against the rubric "returns the identity
graph record for PL-LT-00123 without exposing an un-pseudonymized `jan.kowalski` UPN to the model."
