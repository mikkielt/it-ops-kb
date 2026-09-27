# Token efficiency: every technique and where it lives

The catalogue of what this kb does to spend fewer tokens, turns and model calls, each with the file that does it and the measurement behind it. The reasoning and the headline numbers (when the kb pays off and when it does not) are in `_self/design.md`; the measurements are in `_self/reports/token-usage.md` and `_self/reports/benchmark-2026-09-27.md` (section names in quotes). Change a technique here only together with its code (`/kb-self`).

The cost model all of them follow: a lookup costs the agent's fixed start context times its turns, plus what the tools return. The facts are small (a fact line is under 100 tokens); the context around them is not ("Findings" 1-2). So each technique does one of five things: skip the model, cut turns, shrink tool output, shrink the always-loaded context, or send the work to a cheaper model.

## 1. Skip the model

- **The `kb:` hook answers without a model call.** A `good` pack with no `check:` line blocks the prompt and shows the pack as the answer: 0 tokens, about 0.4 s. A `weak` pack goes to the model as context, so it does not search again; `kb+:` always does. `_tools/kb_hook.py` [CODE _tools/kb_hook.py#answer] ("Re-measurement after the changes", 1).
- **`none` costs one line.** For `coverage: none` the hook adds one line naming the missing words ("say so and add nothing from memory") instead of the pack (plan T9).
- **Structural questions are tools, not reading.** Counts, lists and joins are `rag.py audit`, `facts` and `src --cited` (MCP `kb_audit`, `kb_facts`, `kb_source` with `cited`): 1 call and about 1k tokens, exact, against 28 calls and 363k effective input for an agent reading files ("Results", T6; recommendation B).
- **`kb_ask.py` answers counts and "who cites" with no model.** It detects them before routing and calls the audit and source tools: $0, 0.5 s [CODE _tools/kb_ask.py#tool_answer] ("Router second pass").
- **The model runs at write time, not at lookup time.** doc2query expansions are generated once per fact and indexed; `pack` stays deterministic (`_self/doc2query.md`).

## 2. Fewer turns

- **One call, one verdict, one stop rule.** `pack` returns `coverage: good|weak|none`, the best fact lines by article and one url footer; the verdict tells the agent when to stop: `good` answer, `weak` one reworded pack or one show, `none` say so [CODE _tools/kbfacts.py#pack] (recommendations D and E). The same rule is in `AGENTS.md`, the `/kb-lookup` skill and the MCP server instructions [CODE _tools/kb_mcp.py#INSTRUCTIONS].
- **Batch pack.** Up to 6 parts in one call (`questions`, `rag.py pack -q PART -q PART`), a verdict each and one shared footer [CODE _tools/kbfacts.py#pack_many] (plan T4).
- **`kb_pack` is always loaded.** `_meta` `anthropic/alwaysLoad` on `kb_pack` only, so the first lookup needs no tool-search round trip; the other kb tools stay deferred [CODE _tools/kb_mcp.py#TOOL_LIST] (plan T3).
- **`kb_pack` defaults to `detailed`.** The urls come in the same call; making the agent resolve them would cost a turn (plan T5).
- **Parts are split before routing.** `kb_ask.py` splits numbered parts and several questions, one pack each, so a three-part question stays on the cheap route: $0.013 instead of $0.121 [CODE _tools/kb_ask.py#split_parts] ("Router second pass").
- **Change requests are routed by a hook, not by the model's reading.** `.claude/hooks/kb_change_router.py` adds one line naming the skill when a prompt asks for a change, and nothing otherwise.

## 3. Smaller tool output

- **Fact lines, not pages.** One fact per line with its tag, so a tool returns just the lines that answer, with provenance (`_self/content-rules.md`).
- **A token budget per pack.** `budget` (default 1200 tokens, 200-6000) caps each pack; with 3 or more parts each gets 2 x budget / n, at least 800, which keeps 98% of the expected fact lines and cut a 6-part pack from 21.4k to 16.4k characters ("Changes made from these measurements").
- **One deduplicated url footer.** Urls per hit were 25-46% of search output, many repeated ("Findings" 3); pack prints one footer of only the cited ids, and `search` adds urls only with `-u`.
- **`response_format`.** `concise` (fact lines with `path:line` and tag, no urls) is the default for `kb_facts`, `kb_audit` and `kb_search`; `detailed` on request [CODE _tools/rag.py#FORMATS] (plan T5).
- **Capped listings.** `search` returns at most 2 hits per file [CODE _tools/kbfacts.py#SEARCH_PER_FILE]; `kb_show` prints at most 400 lines [CODE _tools/kb_mcp.py#MAX_LINES]; a cut fact keeps its tag and a listing says how many lines were cut and how to get them ("Retrieval quality audit").
- **Request words are stop words.** "answer", "citation", "please", "explain" no longer count as missing key words, so a covered question is not pushed to the `weak` route [CODE _tools/kbfacts.py#STOP].
- **Retrieval quality is token efficiency.** A false `none` makes the agent give up, a false `good` makes it answer wrongly, a miss makes it search again. So: untagged content ranked at 0.8 [CODE _tools/kbfacts.py#UNTAGGED_WEIGHT], compound identifiers split, product aliases (`_tools/aliases.csv`) that never count as key words, doc2query expansions [CODE _tools/kbfacts.py#EXPANSION_WEIGHT], and the `check:` line for a possible false `good` (`_self/tools.md`, "How the lookup tools decide").
- **`_self/` stays out of the pack.** Its words (hook, skill, plugin) would crowd real answers in `claude/`, `mcp/` and `agents/`; `search --index` reaches it on purpose [CODE _tools/kbfacts.py#index_files].

## 4. Smaller always-loaded context

- **`AGENTS.md` holds only the lookup rules**, at most 4 KB (tested). It loads in every session and subagent; the split took it from 15.9 KB to 3.2 KB (recommendation F). Maintainer rules sit in `_self/`, one file per job, read by the skills that need them (`_self/README.md`).
- **The plugin ships little.** In a host only the `kb` server's instructions and tool descriptions and the skill and agent names reach every session: about 312 tokens (`_self/plugin.md`; "Always-on cost in a host").
- **Descriptions stay out of listings.** `/kb-review-workspace` and `/kb-gap` set `disable-model-invocation: true`, so they cost nothing until run; the clone-only change skills are never in `plugin.json` (`_self/plugin.md`).
- **The plugin is split.** The documentation servers are a second plugin (`.claude-plugin/it-ops-kb-docs/.mcp.json`), so a host that needs only the kb does not carry three more servers' instructions (plan T7).
- **The hooks cost nothing when not used.** The `kb:` hook returns before loading the kb for a prompt without the prefix; the change router adds nothing to questions and harness messages; `.claude/hooks/session-start.sh` runs only in Claude Code on the web and prints a short status.
- **Tool descriptions say what the tools are not.** Every kb tool starts "Documentation facts from it-ops-kb (not live device or directory data)" [CODE _tools/kb_mcp.py#DOCS], so a host with live MECM or AD tools does not call the wrong one and retry (plan T2).

## 5. A cheaper model, or none

- **Answer inline, never in a fresh general-purpose subagent.** A subagent pays its start context (13.5-50k tokens) before reading a line and re-sends it each turn; a one-fact lookup in one cost 120-136k effective input (recommendation A). The rule is in `AGENTS.md`, the `/kb-lookup` skill and the server instructions.
- **The lean `kb-lookup` agent**, only for long research whose output would fill the caller's context: kb tools only, Haiku, `effort: low`, `maxTurns: 6`, `omitClaudeMd: true`, the lookup skill preloaded, 3.9k tokens of start context (`.claude/agents/kb-lookup.md`; "Agent benchmark and routing"). `effort: low` is on the agent, never on the skill, where it would lower a host session's effort (plan T8).
- **The review runs in its own context.** `/kb-review-workspace` forks into `kb-reviewer` (Sonnet, read-only), so reading a host's code stays out of the main session (`.claude/agents/kb-reviewer.md`).
- **`kb_ask.py` routes by verdict, not by a model.** `good` goes to Haiku with the packs and no tools; the reader answers `INSUFFICIENT` when the facts are only related, and the question escalates to Sonnet at `--effort low` with only the kb and docs servers. $0.004-0.014 per covered question against $0.18-0.29 for Opus alone [CODE _tools/kb_ask.py#READER] ("Routing by verdict", "Router second pass").
- **A lean headless start.** The router's `claude -p` skips user plugins and MCP servers (`--setting-sources project,local --strict-mcp-config`), and the reader gets no tools: start context 29.9k, then 24.8k, then 9.8k [CODE _tools/kb_ask.py#LEAN] [CODE _tools/kb_ask.py#claude_argv] ("Router second pass").

## Speed that keeps turns short

- **A persisted index.** Postings lists in a stdlib `sqlite3` file keyed by a fingerprint of the kb files: a cold `pack` in about 0.1 s instead of 2 s, output unchanged [CODE _tools/kbfacts.py#store] (`_self/reports/plan-tooling-efficiency.md`, R1).
- **A warm server.** `kb_mcp.py` builds or loads the index while the client connects, so the first `kb_pack` does not wait [CODE _tools/kb_mcp.py#warm].

## Measured, not assumed

- **The deterministic eval.** `rag.py eval` runs `_tools/lookup_eval.csv` (recall, verdict, output bytes) in `tests.py`, so a ranking or output change is caught with no agent (recommendation G).
- **The paid benchmark.** `_tools/agent_bench.py` runs `claude -p` per model and hand-off pattern and records cost, cache tokens, tool calls and checks; every conclusion in `_self/design.md` cites a dated section.
- **Method rules from the runs.** Compare tokens, not dollars (the run that pays the cache write varies); start each batch from a fresh session; leave the prompt cache lifetime at its default unless lookups repeat more than five minutes apart ("Router second pass").
- **Tried and dropped.** RM3 query expansion, case-sensitive names, a phrase rule for false `good`, rerankers and embeddings, a direct Messages API reader ("Retrieval quality audit", "Not solved", "Router second pass").
