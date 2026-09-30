# Backlog briefs

Whether a compact brief of the kb facts an item rests on saves the agent that works the item some of its work. The comparison is one backlog task, carrying a knowledge field, worked by fresh subagents with the brief and without it. This report holds the setup: the task, its field, the brief and how each arm's subagent is started and read. The runs and their reading are recorded below the setup once they are made, and a reader may not take a result from the setup alone. `kb/_self/usage.md` says how tokens are read and `kb/_self/reports/benchmarks.md` how the other reports count and isolate their runs.

## Setup

### The task

`TK-yittxcs5` "kb_mcp returns kb_pack results as search_result blocks" (task, under `ST-we3h5s5n` "Native citations from kb tool results"). Its goal: `kb_mcp.py` returns `kb_pack` results as `search_result` content blocks (source url, title, fact lines) in the format of `agents/hybrid-retrieval.md`, and tests named `search_result_citations` prove the shape. Its check is `python3 _tools/tests.py -k search_result_citations`, and it touches `_tools/kb_mcp.py` and `_tools/test_kb_mcp.py` only.

Why this one:
- **It leans on kb facts.** The block's required fields, the rule that a `tool_result` holding a `search_result` holds only those, and what MCP's tool result can carry are documentation facts in `public/agents/hybrid-retrieval.md`. An agent that does not know them guesses the shape or looks them up.
- **The facts have a catch.** MCP has no search-result content type (`public/agents/hybrid-retrieval.md:67`), so a task that returns such blocks from an MCP server has to decide how, and the facts say why.
- **Its check is a test of the agent's own writing.** A `-k` selector that matches nothing exits non-zero, so the check passes only when the agent wrote tests of that name and they pass. It is repeatable in a throwaway clone.
- **It is small and open.** It waits on a trigger outside the repository, so nobody works it for real while the runs use it. The runs happen in throwaway clones and land nothing, so the item in the backlog itself stays as it is.

### Its knowledge field

The field the item would carry (the format of `ST-ireqmpda` "A knowledge field on items: questions and stable kb references"). Fact keys are `kbfacts.fact_key` of the fact's text (12 hex); line numbers are never stored.

```json
"knowledge": {
  "ask": [
    "What fields does a Claude API search_result content block need, and can a tool_result mix search_result blocks with other block types?",
    "What content block types can an MCP tools/call result carry, and does MCP define a search-result or citation type?",
    "How does a kb fact line (path:line, tag, source url) map onto a search_result block, and what does a citation carry back?"
  ],
  "refs": [
    "public/agents/hybrid-retrieval.md#ed17f31bc97e",
    "public/agents/hybrid-retrieval.md#82fe5f3fd974",
    "public/agents/hybrid-retrieval.md#2930cee6d7c9",
    "public/agents/hybrid-retrieval.md#83f6d96bbc83",
    "public/agents/hybrid-retrieval.md#17558b4064fc",
    "public/agents/hybrid-retrieval.md#7cda7bcad38f",
    "QK-kb-need-know-before-licence-census",
    "S-4c46o537",
    "S2135",
    "S-qpqoaaqj"
  ]
}
```

The fact keys are the six facts at `public/agents/hybrid-retrieval.md:63`, `:64`, `:65`, `:67`, `:68` and `:69` (tags DOC, DOC, DOC, DOC, DER, DER). The QK answer is `public/_answers.md`, whose bullets at `:1803` (DOC) and `:1805` (UNK) concern citations. The three source ids are the ones the packs' footer names. A topic id is left out on purpose: it would put the whole article in the brief, and the facts are named.

### The compact brief

Built with no model from the field, as the packs of the asks and then the referenced facts no pack printed, with no prose of its own:

```text
python3 _tools/rag.py pack --format detailed -q "<ask 1>" -q "<ask 2>" -q "<ask 3>"
python3 _tools/rag.py show public/_answers.md:1803 -n 1
python3 _tools/rag.py show public/_answers.md:1805 -n 1
```

The six referenced facts of `agents/hybrid-retrieval` are already in the packs, so no command prints them again. The output as printed, at the commit the field was written against (a line in two parts is printed in both; the line numbers are those of that commit, so the run builds the brief again from the field at its base commit, and a fact key that no longer resolves stops the run):

```text
# Q1: What fields does a Claude API search_result content block need, and can a tool_result mix search_result blocks with other block types?
coverage: good (best article matches 8 of 10 key words: api, block, claud, content, field, search_result, tool_result, type)

## public/agents/hybrid-retrieval.md  Hybrid retrieval for agents and RAG  [complete, retrieved 2026-09-29]
- public/agents/hybrid-retrieval.md:62 `search_result` content blocks let Claude cite an application's own retrieved content like web search results; they are part of the standard Messages API (no beta header) and every active model supports them except Claude Haiku 3 [DOC S-4c46o537].
- public/agents/hybrid-retrieval.md:63 A `search_result` block needs `type`, `source` (any stable string: a URL or an internal id such as `kb://article-1234`), `title` and `content` (an array of non-empty text blocks, text only); `citations` and `cache_control` are optional, and citations are off unless `citations.enabled` is `true`, with one setting for all search results in a request [DOC S-4c46o537].
- public/agents/hybrid-retrieval.md:64 Search results can come from a custom tool's `tool_result` or be placed directly in a user message; a `tool_result` that contains any `search_result` block must contain only `search_result` blocks, and assistant messages cannot carry them [DOC S-4c46o537].
- public/agents/hybrid-retrieval.md:67 MCP's tool result content types are text, image, audio, resource links and embedded resources (2026-07-28 revision); the protocol has no search-result or citation content type [DOC S2135].
- public/agents/hybrid-retrieval.md:68 A client that wants citations from an MCP server's results has to convert them into `search_result` blocks itself: the search-results page takes such blocks only from the caller's own `tool_result` content and never mentions MCP, the MCP connector page's `mcp_tool_result` example carries only a text block, and no Claude Code or Agent SDK page read on 2026-09-27 documents a conversion [DER S-4c46o537, S-qpqoaaqj, ... [DER S-4c46o537, S-qpqoaaqj, S2135: documented block sources compared; absence on the pages read]
- public/agents/hybrid-retrieval.md:69 A kb fact line (path:line, tag, source url) maps directly onto one `search_result` block (`source` = the source url, `title` = the article, one text block per fact), which would let an API client get per-fact citations from `rag.py pack` output [DER S-4c46o537: block fields compared with the pack's line format].
  (+2 more matching lines in public/agents/hybrid-retrieval.md: kb_search with more words, or kb_show)

# Q2: What content block types can an MCP tools/call result carry, and does MCP define a search-result or citation type?
coverage: good (best article matches 8 of 10 key words: block, carry, content, mcp, result, search-result, tool, type)

## public/agents/hybrid-retrieval.md  Hybrid retrieval for agents and RAG  [complete, retrieved 2026-09-29]
- public/agents/hybrid-retrieval.md:62 `search_result` content blocks let Claude cite an application's own retrieved content like web search results; they are part of the standard Messages API (no beta header) and every active model supports them except Claude Haiku 3 [DOC S-4c46o537].
- public/agents/hybrid-retrieval.md:63 A `search_result` block needs `type`, `source` (any stable string: a URL or an internal id such as `kb://article-1234`), `title` and `content` (an array of non-empty text blocks, text only); `citations` and `cache_control` are optional, and citations are off unless `citations.enabled` is `true`, with one setting for all search results in a request [DOC S-4c46o537].
- public/agents/hybrid-retrieval.md:64 Search results can come from a custom tool's `tool_result` or be placed directly in a user message; a `tool_result` that contains any `search_result` block must contain only `search_result` blocks, and assistant messages cannot carry them [DOC S-4c46o537].
- public/agents/hybrid-retrieval.md:65 Each citation is a `search_result_location` with `source`, `title`, `cited_text` (not counted as output tokens), `search_result_index` (0-based across all search results in the request) and `start_block_index`/`end_block_index`; Claude cites whole text blocks, so smaller blocks give finer citations [DOC S-4c46o537].
- public/agents/hybrid-retrieval.md:67 MCP's tool result content types are text, image, audio, resource links and embedded resources (2026-07-28 revision); the protocol has no search-result or citation content type [DOC S2135].
- public/agents/hybrid-retrieval.md:68 A client that wants citations from an MCP server's results has to convert them into `search_result` blocks itself: the search-results page takes such blocks only from the caller's own `tool_result` content and never mentions MCP, the MCP connector page's `mcp_tool_result` example carries only a text block, and no Claude Code or Agent SDK page read on 2026-09-27 documents a conversion [DER S-4c46o537, S-qpqoaaqj, ... [DER S-4c46o537, S-qpqoaaqj, S2135: documented block sources compared; absence on the pages read]
  (+4 more matching lines in public/agents/hybrid-retrieval.md: kb_search with more words, or kb_show)

# Q3: How does a kb fact line (path:line, tag, source url) map onto a search_result block, and what does a citation carry back?
coverage: good (best article matches 9 of 10 key words: block, carry, line, map, onto, path, search_result, tag, url)

## public/agents/hybrid-retrieval.md  Hybrid retrieval for agents and RAG  [complete, retrieved 2026-09-29]
- public/agents/hybrid-retrieval.md:63 A `search_result` block needs `type`, `source` (any stable string: a URL or an internal id such as `kb://article-1234`), `title` and `content` (an array of non-empty text blocks, text only); `citations` and `cache_control` are optional, and citations are off unless `citations.enabled` is `true`, with one setting for all search results in a request [DOC S-4c46o537].
- public/agents/hybrid-retrieval.md:64 Search results can come from a custom tool's `tool_result` or be placed directly in a user message; a `tool_result` that contains any `search_result` block must contain only `search_result` blocks, and assistant messages cannot carry them [DOC S-4c46o537].
- public/agents/hybrid-retrieval.md:68 A client that wants citations from an MCP server's results has to convert them into `search_result` blocks itself: the search-results page takes such blocks only from the caller's own `tool_result` content and never mentions MCP, the MCP connector page's `mcp_tool_result` example carries only a text block, and no Claude Code or Agent SDK page read on 2026-09-27 documents a conversion [DER S-4c46o537, S-qpqoaaqj, ... [DER S-4c46o537, S-qpqoaaqj, S2135: documented block sources compared; absence on the pages read]
- public/agents/hybrid-retrieval.md:69 A kb fact line (path:line, tag, source url) maps directly onto one `search_result` block (`source` = the source url, `title` = the article, one text block per fact), which would let an API client get per-fact citations from `rag.py pack` output [DER S-4c46o537: block fields compared with the pack's line format].

sources:
  -> S-4c46o537  https://platform.claude.com/docs/en/build-with-claude/search-results
  -> S2135  https://modelcontextprotocol.io/specification/2026-07-28/server/tools
  -> S-qpqoaaqj  https://platform.claude.com/docs/en/agents-and-tools/mcp-connector

 1803  - Citations: Claude API `search_result` blocks (GA, standard Messages API) give per-block citations from tool results; MCP defines no such content type. [DOC S-4c46o537, S2135]
 1805  - Open: whether the `?accept=text/markdown` form is a supported interface; whether the ETag changes on template rebuilds; whether any MCP client converts results to `search_result` blocks. [UNK]
```

### The two arms

Same task, same base commit, same prompt, same kb tools. Only the brief differs.

| arm | the subagent's prompt |
|---|---|
| **brief** | the item's `/goal` condition (`python3 _tools/backlog.py goal TK-yittxcs5`), the item's id, title and JSON (the knowledge field included), then the brief above under the heading `Brief`, its lines cited as `path:line` with their tags |
| **plain** | the same, without the brief. The field is in the item JSON, and the agent may run `rag.py pack` or `kb_pack` itself: what it spends looking the facts up is what the brief is meant to save |

The brief's own build costs no model call. Its text is in the arm's prompt, so its tokens are in the arm's counts.

### Starting each arm's subagent

Each run is one fresh headless session that starts one fresh subagent, the way the earlier subagent scenarios do (`kb/_self/reports/benchmarks.md`, Reading files without the lookup tools):

1. **A throwaway clone per run**, made from the base commit (the commit is recorded with the runs), with the isolation of `kb/_self/reports/benchmarks.md`: hooks off, the query log `off`, `origin` a local bare repository, the kb server registered at local scope for the clone and removed afterwards. In the clone, this report is removed in a first commit of its own (it holds the brief, and the plain arm must not find it). `backlog.py fire ST-we3h5s5n` and a started sprint for the story `ST-we3h5s5n` leave nothing waiting: the sprint is one created in the clone, named by the story's `sprint` (a task follows its parent's sprint and `backlog.py check` refuses one on the task), its start gate answered in the clone, then `backlog.py start`. the knowledge field is added to the task's item file only when `backlog.py check` accepts it, and `backlog.py show TK-yittxcs5` must print `ready` before the run. The harness claims the item there (`backlog.py claim TK-yittxcs5 --by bench-<arm>-<n>`) and commits the claim with `KB-Work: TK-yittxcs5`, as the runbook says (`kb/_self/backlog.md`, Working on items).
2. **The prompt is written to a file** by the harness: the arm's text and nothing else. The typographic quotes of the `/goal` condition (`backlog.py goal` prints them curly) are written as straight quotes: the Haiku runner rewrote them when it relayed the text, which made the first run fail step 4.
3. **The runner** is `claude -p --model haiku --output-format json` in the clone with hooks off, told to start exactly one subagent of type `kb-worker` (`.claude/agents/kb-worker.md`: Sonnet at high effort) with the prompt file's text verbatim, no `model` override, and to reply with the subagent's report. The runner's own prompt is that instruction with the prompt file's text between two marker lines, and it runs with `--permission-mode bypassPermissions` (a throwaway clone with a local `origin`). Its `session_id` in the JSON result names the runner's transcript. Claude Code starts the subagent in the background, so the runner's transcript holds two prompts: the first starts the subagent, and its `sub` counts are the subagent's whole work (they equal the sums of the subagent's own transcript, checked on one run); the second, when the subagent's report arrives, has none.
4. **The run is kept only if the subagent's first record equals the prompt file.** The runner relays the prompt, and a relay that dropped or changed a line would change the arm. A run that fails this comparison is discarded and made again.
5. **After the report** the harness runs `python3 _tools/backlog.py done TK-yittxcs5` once in the clone, records its exit code, and does not resume or repair the agent: a refused `done` is the run's result, so each run is one worked attempt. The item's `/goal` condition asks the agent to run `done` and show its output, so an agent may run it before the harness does. Then the item is already `done`, and the harness's own call is refused with `status done`, which says nothing about the work. A run's `done` result is therefore the agent's last `backlog.py done` when it ran one, else the harness's call. Arms are interleaved (brief, plain, brief, ...) so drift in the service or the cache spreads over both.

### Where each run is read

- **The transcripts.** Claude Code writes the runner's transcript to `~/.claude/projects/<the clone's project directory>/<session_id>.jsonl` and the subagent's beside it as `<session_id>/subagents/agent-<id>.jsonl`, with `agent-<id>.meta.json` naming its `agentType` (`kb/_self/usage.md`, How tokens are measured).
- **Turns, tokens and requests:** `python3 _tools/kbusage.py <session_id>.jsonl` on the runner's transcript. The `sub` counts of its one prompt are the subagent's (`requests` are its turns; `in`, `cw`, `cr` and `out` its tokens, per model), and `main` is the runner's own overhead, kept apart and the same in both arms. Pointing `kbusage.py` at the subagent's own file prints nothing, because the reader leaves sidechain records out of a main transcript's counts (checked on the reader's fixture `_tools/fixtures/kbusage/session/subagents/agent-a1.jsonl`).
- **Tool calls:** the `tool_use` blocks of the subagent's own transcript. The reader keeps a step list for the main chain only, so this count is read from the file, once per block.
- **Whether checks passed first time:** the result of the run's `backlog.py done` (see step 5), and whether the first run of `python3 _tools/tests.py -k search_result_citations` in the subagent's transcript passed. A run whose agent stopped without writing tests has no such run.
- **Tokens of a run:** the subagent's `in`, `cw`, `cr` and `out` added together, from the `sub` counts. Effective input (`in` + 2 `cw` + 0.1 `cr`, the weights of `kb/_self/reports/benchmarks.md`) is given beside it, since cache reads make up nearly all of the total.
- **Every run's row** gives the arm, the clone's base commit, Claude Code's version and the model ids the counts name, so that a change of model between two runs shows.

### What the setup does not settle

- The `-k` check proves the tests the agent wrote itself, so a passing check says the agent's tests pass, not that the block shape is right. The reading of each run may note whether its tests assert the fields of `public/agents/hybrid-retrieval.md:63`, without changing the run's pass or fail.
- A brief that is right cannot save tokens on a task the agent already knows how to do; that is the cost of choosing one task, and it is why the plain arm may look things up.

## Runs

Made on 2026-09-30, three runs per arm, in the order brief, plain, brief, plain, brief, plain. Every clone was made from `a95f358`, on Claude Code 2.1.285. The runner is Haiku 4.5 (`claude-haiku-4-5-20251001`) and the `kb-worker` subagent Sonnet 5.5 (`claude-sonnet-5-5`) in all six kept runs, so no run changed model. Each kept run's first subagent record equals its prompt file. One run was discarded and made again (see the end of this section).

### Usage of the subagent

Read with `python3 _tools/kbusage.py` from each run's main transcript: the `sub` counts of its first prompt. Turns are the subagent's requests; tool calls are the `tool_use` blocks of its own transcript.

| run | turns | tool calls | in | cw | cr | out | tokens | effective input |
|---|---|---|---|---|---|---|---|---|
| brief 1 | 37 | 43 | 74 | 118,737 | 3,323,313 | 26,308 | 3,468,432 | 569,879 |
| plain 1 | 18 | 33 | 36 | 104,973 | 1,382,922 | 15,587 | 1,503,518 | 348,274 |
| brief 2 | 26 | 40 | 52 | 143,767 | 2,966,969 | 39,449 | 3,150,237 | 584,283 |
| plain 2 | 29 | 44 | 58 | 133,916 | 3,022,352 | 30,045 | 3,186,371 | 570,125 |
| brief 3 | 32 | 44 | 64 | 124,275 | 3,150,753 | 35,320 | 3,310,412 | 563,689 |
| plain 3 | 29 | 39 | 58 | 134,592 | 2,895,741 | 31,185 | 3,061,576 | 558,816 |

The runner's own overhead (`main`, both prompts, Haiku) was 91,354 to 105,443 tokens a run over 3 requests, and about 13,000 higher in the brief arm than in the plain arm (the runner relays the brief). The runner's start context (`start` of its first prompt) was 30,470 in the brief arm and 28,199 in the plain arm: the brief is about 2.3k tokens of every request of the subagent, which re-reads its prompt from the cache on each turn.

### Outcome of each run

| run | first run of the `-k` check | `backlog.py done` | what the agent did |
|---|---|---|---|
| brief 1 | failed (3 of 10 tests) | exit 0, run by the agent | implemented it; the blocks are opt-in by an environment variable |
| plain 1 | none (wrote no tests) | exit 1, run by the harness | stopped and recorded a gate on the item asking which shape `kb_pack` returns, since a `tool_result` with `search_result` blocks may hold nothing else and other tests read the first text block |
| brief 2 | failed (1 of 15) | exit 0, run by the agent | implemented it, blocks opt-in by an environment variable, and filed a bug for tests that fail in the clone |
| plain 2 | failed (2 of 16) | exit 0, run by the agent | implemented it, blocks opt-in by a flag, and filed a bug for the same tests |
| brief 3 | failed (1 of 21) | exit 0, run by the harness | implemented it, blocks opt-in by an environment variable |
| plain 3 | passed (8 of 8) | exit 0, run by the harness | implemented it as a second tool, `kb_pack_cited`, leaving `kb_pack` as it was |

In brief 2 and plain 2 the agent ran `done` itself and the harness's own call was refused with `status done` (see the setup, step 5); that refusal is not counted. Every agent's last run of the `-k` check passed where it wrote tests, and the harness's own run of it after the agent finished exited 0 in the five runs that implemented the task.

Tool calls by kind: the two arms read the same number of files (8, 8 and 10 `Read` calls in runs 1, 2 and 3, in each arm). The subagent called `kb_pack` once in brief 2 and once in plain 2 and never in the other four runs, so the plain arm did not spend its calls looking the facts up either. It searched the live docs in three runs (one call in plain 1 and plain 2, two in plain 3); the brief arm in none.

### The comparison

| run | tokens, brief | tokens, plain | brief against plain | effective input, brief against plain | refused `done`, brief | refused `done`, plain |
|---|---|---|---|---|---|---|
| 1 | 3,468,432 | 1,503,518 | +1,964,914 (+131%) | +221,605 | 0 | 1 |
| 2 | 3,150,237 | 3,186,371 | -36,134 (-1.1%) | +14,158 | 0 | 0 |
| 3 | 3,310,412 | 3,061,576 | +248,836 (+8.1%) | +4,873 | 0 | 0 |

The rule of the story `ST-zptutwlf` "Measure whether a knowledge brief saves an agent work": build only when the with-brief arm used fewer tokens and had no more refused dones than the arm without it, in every run. The brief arm had no more refused dones in any run (none, against one in plain 1). It used fewer tokens in one run of three (run 2, by 1.1%), and more in runs 1 and 3. Effective input, which weights the cache the way the earlier reports do, was higher in the brief arm in all three runs, and so was output (26,308, 39,449 and 35,320 tokens against 15,587, 30,045 and 31,185). So the rule's first condition fails.

Reading, not part of the rule:
- Run 1 is not a like-for-like pair: plain 1 stopped on a gate after 18 turns without implementing, so its count is low for the wrong reason. Left out, the brief arm still used more in run 3 and saved 1.1% in run 2, so the verdict does not depend on it.
- The brief did not replace any work: both arms read the same number of files, and in every one of the six runs the agent read the article's fact lines itself (`rag.py show` or `sed -n` on `public/agents/hybrid-retrieval.md`), the brief arm as well. What the brief cost is its own tokens, on every request.
- The gate of plain 1 is the catch that `Why this one` names (MCP has no search-result type). Five of the six agents met it and went ahead with the blocks opt-in or as a second tool; one plain agent stopped on it. One run in one arm does not show that the brief prevents the stall.

### Tokens spent

The six kept runs spent 18,272,352 tokens: 17,680,546 by the subagents and 591,806 by the runners. The discarded run spent 2,390,276 more (2,285,070 by its subagent), so all runs together spent 20,662,628 tokens.

The discarded run was the first brief run. Its subagent's first record differed from the prompt file in one line: the runner had written the `/goal` condition's curly quotes as straight ones. It is not counted anywhere above; the setup now writes them straight in the prompt file. Its subagent made 24 requests and its work was accepted by `done`, so it would have been a brief run of 2,285,070 tokens.

Verdict: drop
