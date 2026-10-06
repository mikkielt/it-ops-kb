# Rules retrieval for kb/_self: what a sprint session reads before and after

Measured on 2026-10-06 on the macOS host, Python 3 from the clone's `.venv`, warm pack index. Before: the tree at commit 55a7f3f3e (the skills read whole sections). After: the work of ST-dvf3xf52 (`rag.py pack --root _self`, anchors, sets) and ST-reit3qmw (the skills and the kb-worker agent switched to the route), on branch work/ST-reit3qmw before its landing.

## 1. Bytes each skill's prescribed reading prints

Setup: for each skill under `.claude/skills/` and the agent `.claude/agents/kb-worker.md`, run every reading command the file prescribes and sum the bytes printed. Before, that is the one `selfdoc.py section ...` command at the top of the file. After, it is the Conduct section read, every set the file names (`rag.py pack --root _self --set NAME`, an agent that reaches every step) and, where the file has one, the item brief (`--item ST-reit3qmw --budget 600`). Both columns are bytes of stdout; the Conduct section is 4190 bytes in every after row.

| skill or agent | before: sections | before bytes | after: sets | after bytes (Conduct + sets + item) | change |
|---|---|---|---|---|---|
| kb-worker | 5 | 24027 | 1 | 11302 (4190 + 5108 + 2004) | -53% |
| kb-sprint | 12 | 73282 | 6 | 27612 (4190 + 21418 + 2004) | -62% |
| kb-item | 6 | 28412 | 4 | 21526 (4190 + 15332 + 2004) | -24% |
| kb-backlog | 6 | 18178 | 4 | 17452 | -4% |
| kb-git-sync | 6 | 28158 | 3 | 14588 | -48% |
| kb-verify | 3 | 8236 | 1 | 7448 | -10% |
| kb-self | 1 (+ README) | not measured | 3 | 8090 | |
| kb-research | 6 | 25467 | 4 | 16447 | -35% |
| kb-refresh | 7 | 30567 | 3 | 14118 | -54% |
| kb-add-topic | 7 | 27363 | 5 | 19354 | -29% |
| kb-add-root | 3 | 17936 | 2 | 10880 | -39% |
| kb-census | 6 | 29036 | 5 | 16466 | -43% |
| kb-ingest | 6 | 28602 | 4 | 15333 | -46% |
| kb-probe | 4 | 20473 | 2 | 11076 | -46% |
| all | | 359737 | | 211692 | -41% |

The after figure is an upper bound: a set is read when its step is reached, so a session that stops early reads less; before, the whole section read came first.

## 2. A headless worker session, the same task before and after

Setup: `claude -p --model sonnet` with the same prompt both times, in the before tree and in the after tree. The prompt: read `AGENTS.md` and `.claude/agents/kb-worker.md`, do the up-front reading that file prescribes (item ST-reit3qmw), then answer ten rule questions, each with a `kb/_self/<doc>.md:<line>` citation, looking up what the reading did not cover the way the two files say. Tools: Read, Grep, Glob and the `selfdoc.py`, `rag.py`, `backlog.py show`, `kbdecide.py list` commands (after: `kb_ask.py` too). Two runs each. `tool_result_bytes` is the sum of all tool outputs the session read; `tokens_in` is the sum of input tokens over all turns (cache reads included), `fresh` the part not served from the cache; answers graded by hand against the docs.

| run | tool calls | tool result bytes | turns | wall s | tokens_in (fresh) | output tokens | cost USD | correct answers |
|---|---|---|---|---|---|---|---|---|
| before 1 | 9 | 76067 | 10 | 19 | 160603 (32442) | 2372 | 0.179 | 10/10 |
| before 2 | 13 | 51247 | 14 | 25 | 312669 (21386) | 2896 | 0.173 | 10/10 |
| after 1 | 9 | 34295 | 10 | 20 | 202139 (18642) | 2193 | 0.133 | 10/10 |
| after 2 | 8 | 38707 | 9 | 18 | 181456 (16494) | 2112 | 0.120 | 10/10 |

Before, the session read 24 KB of sections and then grepped the docs for the four questions outside them (`grep -n`, `sed -n` on multi-KB lines). After, it read the Conduct section, the `kb-worker` set and the item brief, then asked the ten questions in two or three `-q` batches. Tool output fell by about half (63 KB to 36 KB on average), fresh input tokens by a third; wall time and the answers did not change. The after sessions chose `--budget 900` for their batches where the skill says `--budget 400`.

## 3. The eval of the route

Setup: `python3 _tools/rag.py eval --root _self` over `kb/_self/_retrieval/lookup_eval.csv`; `free` (`eval --free`) is the leave-one-out rate: each row's pack run without that row's own expansion and pin, so it measures a paraphrased question an agent has not asked before.

| state | rows | passed | free |
|---|---|---|---|
| first run, sentence passages only | 37 | 19 | |
| passage context (lead, parent intro) and passage-level verdict | 37 | 24 | |
| passages ranked across docs, title weight, named-word verdict rule | 37 | 26 | |
| opening passage of a table row, decisions tied to docs | 37 | 28 | |
| tested questions as anchors and expansions, aliases, `good` only on a tested question | 38 | 38 | 26/36 |
| the skills' curated sets added (SS rows) | 271 | 271 | 234/269 |

Held-out: 20 rule questions written after the tuning and never added to the file, run once with `rag.py eval --file --root _self`: the answering passage was printed for 14 of 20 before the anchors and for 15 of 20 after them; the verdict was `good` on all 20 before the tested-question rule and `weak` on all 20 after it (no held-out question matched a tested one).

## 4. Output sizes of the route

| call | bytes |
|---|---|
| `pack --root _self "which steps does backlog.py land run and what does it refuse"` (default budget) | 4319 |
| `pack --root _self -q ... -q ... -q ...` three parts, `--budget 300` | 3311 |
| `pack --root _self --set kb-item:land` | 1455 (before the set grew to 11 rows) |
| `pack --root _self --item ST-dvf3xf52 --budget 600` | 2257 |
| one warm `pack --root _self` call | 0.07 s |
| `kb_ask.py --root _self` Haiku reader on a `weak` pack | 0.034 USD |

## 5. Cost of the delegated sessions that built this

Headless `claude -p` sessions, by model, read from each result's `modelUsage`: Sonnet (claude-sonnet-5-5) for every session: 28 sessions plus the four measurement runs, 22.20 USD in total, of which the measurement runs are 0.61 USD; no Haiku or Opus session. The manager session's own cost is not in this figure.

## 6. A tested answer costs less (2026-10-06)

Setup: `len(stdout.encode())` of `python3 _tools/rag.py pack --root _self "<tested question>"` at the default budget, on the base (origin/main) and on the change; a pack with a tested match prints its pinned passages and at most three further ones, the tied decisions as before; a weak pack keeps the full budget.

| tested question | before | after |
|---|---|---|
| SE-002 who may answer a sprint's start gate | 4255 | 1774 |
| SE-005 which commit trailer makes a commit count as work on a backlog item | 4365 | 1743 |
| SE-001 what does backlog.py land refuse when the tree has uncommitted or untracked files | 1166 | 1166 |

The planted bound of the item (one pinned passage plus three, 4 x 450 bytes, plus 561 bytes of header, decision and footer: 2361, rounded to 2400) holds for SE-002 with 1774 bytes; `rag.py eval --root _self` passes 271 of 271.
