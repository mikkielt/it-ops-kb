# Plan: smaller and faster `_tools/` with every capability kept (researched 2026-09-26)

**Status (2026-09-26): implemented except R5 (blocked) and R3's engine switch (needs acceptance).** Researched on
`main` at `9f60edc` (Python 3.11, this container); implemented on top of `7483cfc`. What was done, measured and left
is under "Implementation status" at the end; the research below is unchanged.

The question was: shrink the code without losing any capability, find improvements, and decide whether moving from
stdlib-only to a proper Python project with dependencies (FastAPI? tokenizers?) would make it more efficient.

## Short answer

1. **The big win needs no dependency.** Today a CLI `rag.py pack`, every `kb:` prompt hook and the MCP server's first
   call each rebuild the whole BM25 corpus from about 3 MB of Markdown and CSV, which takes about 2 s. A persisted
   SQLite index (`sqlite3` is stdlib, FTS5 not needed) brings a cold `pack` process to **97 ms, 21x faster, with
   byte-identical output** on all 85 eval questions plus 5 extra probes. Memoizing `stem()` and using postings lists
   also keep output identical and make the server's warm path cheaper.
2. **FastAPI: no.** The kb server speaks MCP over stdio, the transport the plugin launches. FastAPI would add an HTTP
   daemon with ports and auth, and give nothing for a local stdio tool. If a shared remote kb server is ever wanted,
   use the MCP SDK's Streamable HTTP transport, not a hand-built FastAPI app.
3. **tokenizers: no.** Hugging Face `tokenizers` builds subword vocabularies for neural models. It cannot give Claude's
   token counts (that tokenizer is not published for offline use), and BM25 over technical identifiers needs exactly
   what `kbfacts.terms()` already does: camelCase, `US_NPI` and `what-if` splitting plus a light stemmer. The
   `budget` of about 3.5 characters per token is an estimate by design.
4. **MCP Python SDK (`mcp` 2.2, `MCPServer`, formerly FastMCP): possible but not worth it now.** A prototype
   reproduced the tool list, `_meta` `anthropic/alwaysLoad`, annotations and `isError` handling, and would remove
   about 150 lines (hand-written JSON schemas and the protocol loop). It costs a 665 ms server start (39 ms today),
   136 MB of dependencies, Python 3.10 or later, and an install step on every host (see "Dependencies"). The stdlib
   server is already dual-era 2026-07-28 and tested.
5. **The code shrinks by consolidating, not by using libraries.** About 200-250 lines (~6%) are duplicated helpers
   across 8 modules. There are two separate retrieval engines (`rag.search` and `kbfacts.pack`), about 55 lines of
   retirable legacy migration paths, and repeated test scaffolding (below). None of the library swaps checked
   (bm25s, PyStemmer, pandas or polars, PyYAML, GitPython or pygit2, trafilatura, typer) keeps behaviour identical
   and also pays for itself.
6. **Recommended project shape:** add a `pyproject.toml` for tooling (ruff, pytest as a dev group) and keep the
   runtime stdlib-only. The git hooks and the plugin run whatever `python3` the machine has.

## Where the time goes (measured)

| path | today | cause |
|---|---|---|
| `rag.py pack "<q>"` (CLI, `kb:` hook) | 2.05 s | `kbfacts._corpus()` stems ~23k units every process: 632k `stem()` calls, 4.8 s of 5.8 s under cProfile |
| kb MCP server, first `kb_pack` | 1.73-1.78 s | same corpus build, then cached in memory for `TTL = 30` s |
| kb MCP server, later `kb_pack` | ~50-64 ms | a linear scan over all 23k units for df, `has()`/kdf and scoring |
| kb MCP server after 30 s idle | ~1.8 s again | the TTL cache rebuilds even when no file changed |
| `rag.py eval` (85 questions) | 8.4 s | 2 s build + 85 × 64 ms |
| `rag.py search` | 0.29 s | its own chunker and unstemmed BM25 (a second engine) |
| `check.py` / `build_index.py --check` / `kbgit.py fix --check` | 0.17 / 0.15 / 0.31-0.43 s | fine; details under "kbgit, census, fetch" |
| `kbgit.py check-trailers` (30 commits) | 0.75 s | ~4.2 git subprocesses per commit (126 calls) |

## Recommendations, in order of value

### R1. Persisted retrieval index (stdlib `sqlite3`), keyed by a file fingerprint

- Build: `kbfacts.corpus()` as today, then write `unit(id, path, line, section, text, tags, len, title)`,
  `tf(term, unit, tf)` and `own(term, unit)` with indexes on `term`, plus `meta(fp, n, avg)`. The fingerprint is a
  sha1 of `(path, mtime_ns, size)` over the kb files, `aliases.csv`, `doc2query/expansions.csv` and `_sources.csv`.
  Computing it takes 4 ms.
- Query: read only the postings of the question's terms, alias variant words and key words. Compute df, kdf, `has()`
  and BM25 from those rows with the same arithmetic in the same order, then run pack's verdict, grouping and footer
  code unchanged.
- Measured with the prototype:

  | | today | prototype |
  |---|---|---|
  | cold `pack` process | 2,048 ms | **97 ms** |
  | build (once per kb change) | - | 3.5 s |
  | identical output (85 eval + 5 probes) | - | 90 / 90 |
  | index size | - | 58.9 MB (20 MB gzipped); shrinkable with integer term ids and `WITHOUT ROWID` |

- Location: `_cache/kbindex.sqlite` in a clone (already git-ignored), `${CLAUDE_PLUGIN_DATA}` for an installed plugin
  (per-plugin, survives updates: `claude/plugins.md:61`), and a temp directory as the fallback. If the fingerprint
  differs, rebuild. If the directory is not writable, build in memory as today. Nothing is committed.
- Who gains: the `kb:` hook (it runs `pack` inside a UserPromptSubmit hook, so 2 s is felt on every `kb:` prompt),
  `rag.py pack`/`facts`/`eval`, tests that call `pack` in subprocesses, and the MCP server's first call.
- Alternative: `pickle` of the corpus loads in 300 ms (17.6 MB) with identical output. It is simpler, but loads
  everything on every run, so it is 3x slower cold than SQLite.

### R2. In-memory speedups for the long-running MCP server (identical output)

- `functools.lru_cache` on `kbfacts.stem`: the corpus build drops from 2.16 s to 1.25 s. One line.
- Postings lists (`term -> [unit index]`) built with the corpus (0.2 s):
  - df and kdf come from set sizes and intersections instead of a scan: 19 ms becomes 0.03 ms per question;
  - scoring visits only the units that hold a query term: 19 ms becomes 15 ms (common words still touch many units);
  - `rag.py eval` gains the same way.
- Replace the 30 s TTL with the R1 fingerprint check: the server stops rebuilding after idle time and picks up edits
  within one call.
- Optional: warm the corpus in a background thread at server start, so the first `kb_pack` does not pay the build.

### R3. One retrieval engine instead of two (about 115 lines)

`rag.py` has its own `kb_files`, `front_matter`, `chunks`, `tokens`, `search` and `source_rows` (rag.py:63-166 and
192-200, 113 lines) beside `kbfacts`' units, `terms` and BM25. Make `search` a view over the same index: units,
`terms` without stemming, or the index's stemmed postings. **This changes search output** (unit boundaries instead of
900-character chunks), so it needs acceptance. Add search cases to `lookup_eval.csv` first, then switch. `rag show`
(rag.py:449-464) and `kb_mcp.kb_show` (kb_mcp.py:222-246) also check paths the same way twice. Share one function.

### R4. One shared helper module (about 200-250 lines, identical behaviour)

A read-only survey of all eight modules found these copies. All paths are under `_tools/`.

| helper | copies |
|---|---|
| read a CSV and require columns | check.py:23-36, fetch.py:73-84, build_index.py:52-64 |
| read `_sources.csv` | kbid.py:121, census.py:493, kbfacts.py:313, rag.py:192, kb_mcp.py:303 |
| write canonical CSV text | kbgit.py:214 and 786, build_index.py:154, census.py:547/629/637, fetch.py:182, doc2query.py:196 |
| `read(rel)` | kbgit.py:140, build_index.py:44, kbfacts.py:73, rag.py:46 |
| front matter | build_index.py:82, kbfacts.py:81, rag.py:71, check.py:98, census.py:608 (end-of-block rules differ slightly) |
| walk content files | build_index.content_files, kbfacts.kb_files, rag.kb_files, rag.py:170, fetch.py:220 |
| source-id regex | kbid.SOURCE_ID, build_index.CITE, kbfacts.ID, rag.CITED, census.py:611, kbgit.py:397/430/662/1356 |
| HTTP GET | fetch.py:51-62, census.py:344-365 |
| git wrappers in kbgit | git_run/git 153-164, gitx 1550, plus 1674; `rev-list --parents -n1` parsed four times |

The regexes have drifted. `kbfacts.ID` and `rag.CITED` accept `S\d{3,4}`, `kbid.SOURCE_ID` accepts `S\d+`, and
census.py:611 has no `\b`. Unifying them is a small correctness fix as well as a size cut. Fold these helpers into
`kbid.py` or a new `kbcommon.py`. Tests call `kbgit.resolve_sources`, `resolve_md`, `answer_plan`,
`census.check_pin`, `check_ref`, `newer_tags` and `kbid.source_id` directly, so those names stay.

### R5. Retire legacy paths once no old branch or clone is live (about 55 lines)

- Older `_sources.csv` layouts in kbgit (LATER_COLUMNS, `layouts`, padding in parse_csv, `older` handling:
  kbgit.py:222-271, 283-312 and 322-328). All 1,892 rows have 10 columns, and `superseded_by` arrived in `369beef`.
- `QK<n>` to `QK-<slug>` migration (kbgit.py:516-533, check.py:65-66): no answer id uses the old form.
- `kbgit.py fmt` is a subset of `fix`. It could become `fix --fmt-only`.
- Keep `TRAILERS_SINCE`: pushed history is never rewritten.

### R6. kbgit, census and fetch speedups (stdlib)

- `trailer_audit` (kbgit.py:1306-1333): one `git log --format=%H%x00%P --name-only -z` plus one long-lived
  `git cat-file --batch` instead of about 4 subprocesses per commit (estimated 0.75 s to about 0.2 s for 30 commits).
  `sync` audits the same range twice (1686 and 1715), so memoize by sha.
- `kbgit fix` reads every content file twice: after `build()`, again only to check for markers (kbgit.py:919-924).
  Return the texts from `build()`.
- `normalize_url` runs 3,784 times (75 ms): add `lru_cache`. `build_index.py:126` makes 133k `rsplit` calls:
  group files by directory once.
- census:
  - cache `repo_tags` per repo;
  - one `ls-tree` instead of up to four `cat-file` calls in `check_learn`;
  - use a per-host sitemap lock instead of the global one (one 30 MB sitemap blocks every thread);
  - drop the extra HTTP GET that fills `http_status` on 438 raw sources;
  - close the files at 581, 619, 633 and 635, and make `confirm` write atomically like `fetch.write_state`.
- `ids.count` inside a comprehension is O(n²) at check.py:42 and 64 and kbgit.py:737: use `Counter`.

### R7. Tests

Today:
- `tests.py` is stdlib unittest and imports the other `test_*.py` classes: 117 tests in 55.5 s, or 27.2 s with
  `KB_TESTS_FAST=1`.
- `stress_test.py` has its own harness: 181 checks in 41 s, 31 s of it in tool subprocesses. It copies the kb about
  50 times.
- Slowest classes: Lookup 18.2 s (`rag.py eval` 10.7 s, `kb_hook` 6.4 s), SyncInGit 15.9 s, ResearchMergeInGit
  8.5 s, KbServer 4.6 s.

Changes:
- **Speed without pytest:** R1 alone removes most of the Lookup and KbServer time, because each of those processes
  rebuilds the corpus for 2 s. Also call `rag.run_eval`, `kb_hook.answer` and `kb_mcp.handle()` in-process, and keep
  one subprocess smoke test each for the stdin/JSON wiring (tests.py:348-365). Expected: Lookup plus KbServer drop
  from about 23 s to about 9 s.
- **pytest as a dev dependency** (optional):
  - a `conftest.py` of about 50 lines (`git_env`, `git()`, `tool()`, a `kb_copy` factory on `tmp_path`,
    `read`/`write`/`append`, `requires_git`, `rows`/`HEADER`) replaces scaffolding copied 5-7 times across the
    suites: about 170 lines;
  - stress cases become `parametrize` tables: about 60 lines;
  - the `tests.py` import block and `__main__` stanzas: about 25 lines;
  - with `pytest-xdist --dist loadscope`, the full suite takes about as long as the slowest class, about 16-18 s
    instead of 55 s.

  Constraints:
  - keep a `tests.py` shim or change `kbgit.py:1705`, which runs `tests.py` with `KB_TESTS_FAST=1` inside the sync
    gate;
  - mark the git scenarios (`-m "not git"`);
  - pytest would also collect `stress_test.py` (it matches `*_test.py`);
  - `Cohesion.test_documented_flags_exist` pins the documented flags such as `--scale`.
- **Leaks:** `test_no_secrets` makes 13 passes over 565 files, and `authored()` runs `git ls-files` per call, once
  per DOCS entry at tests.py:165. One cached `{path: text}` and one combined regex save about 2 s.
- **Redundant checks to fold:**
  - lint.py:47-51 repeats `build_index.py --check`;
  - `Ids.test_answer_ids` (tests.py:418) repeats check.py;
  - `lint.SID` re-implements `kbid.SOURCE_ID`, and tests.py:405-408 exists only to keep them equal; import the
    regex instead;
  - the same hash-collision url pair is tested at tests.py:397 and stress_test.py:288;
  - the BitLocker `good` lookup is asserted 3 times (eval row, tests.py:353, test_kb_mcp.py:130);
  - stress re-runs the pristine-kb baseline checks that `tests.py` already runs.
- **Coverage gap:** CI's `python:3.12-slim` has no git, so the 33 git-scenario tests (merge, history, sync,
  research merge, census) always skip there. The sync gate also sets `KB_TESTS_FAST`, so they run only when a
  developer runs the full `tests.py`. Run them in the `kb-trailers` job's `python:3.12` image, which has git.
- **Stale text:**
  - tests.py:474 names a leak_allowlist.txt; the file is `_tools/tests_allowlist.txt`;
  - "about 20 s" for stress (`stress_test.py:4`, `README.md:88`) is now 41 s.

## Dependencies: what each candidate would buy (checked, and why not)

| candidate | would replace | verdict |
|---|---|---|
| FastAPI / uvicorn | nothing: there is no HTTP surface | no. stdio is the plugin's transport; a remote server would use the MCP SDK's Streamable HTTP |
| `tokenizers` / tiktoken | the 3.5 chars/token estimate, `terms()` | no. Neither has Claude's tokenizer; BM25 over identifiers needs the current splitter |
| `mcp` 2.2 (`MCPServer`) | kb_mcp.py schemas and protocol loop (~150 of 459 lines) | not now: +626 ms start, 136 MB of dependencies, Python 3.10+, and every host must install it. Revisit if the spec moves faster than the server can follow |
| `bm25s` (+ scipy/numpy) | the BM25 loops | no. Fractional weights (title ×2, Summary 0.1, doc2query 1.0, alias 0.5, part 0.2, untagged 0.8) and the verdict's `own` sets do not fit; rankings would change. The stdlib postings of R1/R2 get the speed |
| PyStemmer (Snowball) | `stem()` (15 lines) | no. Different stems change every ranking; the `lru_cache` already takes stemming off the hot path |
| numpy | scoring loop | not needed: the index removes the full scan. Also adds 121 ms of import |
| pandas / polars / sqlite for ledgers | CSV ledger code | no. It would break the byte-exact canonical CSV that `fmt`, union merges and the test fixtures rely on |
| PyYAML / python-frontmatter | front-matter parsers | no. YAML turns `retrieved_utc: 2026-09-25` into a date and parses inline lists differently |
| GitPython / pygit2 / dulwich | kbgit's git subprocesses | no. None covers rebase with diff3, interpret-trailers, `blame -M -C` or hooks; GitPython shells out anyway |
| trafilatura / selectolax | fetch.py HTML to text (~80 lines) | only together with a planned baseline reset: every stored `text_sha256` would change |
| httpx / requests | fetch/census HTTP (~20 lines) | low gain; rate limits and per-host semaphores stay hand-written |
| typer / click | argparse boilerplate | ~15 lines per file; not worth a dependency |
| sentence-transformers / fastembed | none (a new dense-retrieval capability) | not now. doc2query plus aliases already cover paraphrases at no runtime cost; revisit only if `lookup_eval.csv` gathers misses that lexical retrieval cannot fix |

Why runtime dependencies are expensive here:
- `plugin.json` starts the server and the `kb:` hook as `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/...`;
- `.githooks/commit-msg` runs whatever `python3` or `python` is on the machine;
- a dependency would need every host and clone to have uv, for example `uv run --script` with PEP 723 inline
  metadata, or a venv, or the hook would silently stop adding KB-* trailers;
- CI (`python:3.12-slim`) would need an install step.

The only runtime dependency seriously considered is `mcp`. Leave it out, or put it behind an optional extra
(`[mcp-sdk]`) while the stdlib server stays the default.

## Proposed project shape

- `pyproject.toml` at the root with no runtime dependencies:
  - `requires-python = ">=3.9"`;
  - a `dev` dependency group (PEP 735: pytest, ruff; uv includes it by default, `arch/python-single-package-extras.md:30`);
  - `[tool.ruff]` in place of part of the kb-verify lint baseline for the Python files.
- Keep the scripts in `_tools/` and the `python3 _tools/x.py` entry points. They are part of the docs, the skills,
  the plugin manifest and the hooks. Moving to a `src/` package would touch all of them for no runtime gain.
- `.gitignore` already covers `_cache/`, where the index goes.

## How to prove "100% of capabilities"

- Before each refactor, record golden outputs:
  - `rag.py pack` over `lookup_eval.csv` plus probes, `search`, `facts`, `audit --entries`, `src --cited`;
  - every MCP tool through `test_kb_mcp.py`;
  - `kbgit fix --check`, `check.py`, `build_index.py --check`.
- After the refactor, diff byte for byte.
- R1, R2, R4, R5 and R6 must be identical. R3 is the one intended change and needs acceptance.
- The gate in `MAINTAINING.md` still applies to every commit: `check.py`, `build_index.py --check`,
  `kbgit.py fix --check`, `tests.py`, `stress_test.py`, `fetch.py --offline`, `rag.py eval` at 100%.

## Suggested order

1. R2's `lru_cache` on `stem` and on `normalize_url`: two lines, identical output, 40% off every cold build.
2. R1, the persisted index, with R2's postings: the 20x cold-path win for `kb:`, the CLI and the first MCP call.
3. R4, the shared helpers, and the regex unification.
4. R7: run the git scenarios in CI and fix the stale text first (small), then the pytest move if wanted.
5. R6, kbgit and census batching.
6. R5 retirements, when no pre-`369beef` branch remains.
7. R3, one engine, after search eval cases exist.

## Implementation status (2026-09-26)

Method: golden output of every tool surface was recorded before the first change and diffed byte for byte after
each step. The golden set covered:
- 255 in-process packs: the 85 eval questions plus 5 probes, each in three formats;
- domain and batch packs;
- `search`, `facts`, `audit`, `src --cited`, `topics-for` and `show`;
- the `kb:` hook, an MCP session over all tools;
- `check.py`, `build_index.py --check`, `kbgit.py fix --check`, lint, `fetch.py`, `trailers`, `check-trailers`, `log`,
  `blame` and `asof`.

All stayed identical, except `rag.py topics` listing the new root file `pyproject.toml`.

| step | status | result |
|---|---|---|
| R1 persisted index | done | a Store of postings lists, in memory or in a sqlite3 file named after the fingerprint (`_cache/`, `CLAUDE_PLUGIN_DATA`, temp dir; `KB_INDEX`) |
| R2 in-memory speedups | done | `lru_cache` on `stem`/`normalize_url`; the fingerprint replaces the 30 s TTL; the MCP server warms the index at start |
| R4 shared helpers | done, narrower | `_tools/kbcommon.py` (read, CSV read/write, `_sources.csv`); one citation regex (`kbid.SOURCE_ID`). Front-matter parsers, content walkers and census's HTTP client stay separate (their rules differ; not testable offline) |
| R6 kbgit/census speedups | done, one item left | batched trailer audit (74/74 commits identical), `fix` reads each file once, census git calls, per-host sitemap locks, closed files, `Counter` duplicate checks. The GET that fills `http_status` stays (decided 2026-09-26) |
| R7 tests and CI | done, pytest move not done | CI's kb-tests job has git (33 git scenarios run); `pyproject.toml` with a dev group (pytest, ruff); ruff clean and checked by tests.py; one-pass leak scan; stale text fixed. The conftest/parametrize rewrite was not done: tests.py stays the runner the sync gate calls, and pytest runs the same suite |
| R5 legacy retirements | done | the research branches are gone (confirmed 2026-09-26): kbgit's older-`_sources.csv`-layout padding and the `QK<n>` renames are removed with their tests and the pre-`kbgit.py` procedure docs; `test_research_merge.py` now merges two branches in today's layout (sync exit 3, `/kb-git-sync`, fix, sync). Census keeps the `http_status` GET (decided) |
| R3 one engine | done | `search` is `kbfacts.search`: the pack's ranking over the same index, at most 2 hits per file (hits are lines now). The corpus gained untagged prose paragraphs (pack ranks them as `(no tag)`) and, at its end, the root index files, which only `search --index` sees (the pack's view is a prefix). rag.py's chunker, tokenizer and BM25 are gone. The 8 search regression queries pass; `eval` 85/85; 275 golden packs keep their verdicts (185 rerank). Search 0.29 s to 0.05 s; index 27 MB |

Measured (cold processes, same container):

| path | before | after |
|---|---|---|
| `rag.py pack` (CLI) | 3.93 s | 0.06 s |
| `kb:` hook | 2.05-2.15 s | 0.05-0.09 s |
| `rag.py eval` (85 questions) | 8.63 s | 0.71 s |
| MCP session (12 calls incl. search, audit) | 4.04 s | 1.63 s |
| `kbgit.py check-trailers` (30 commits) | 0.77-0.95 s | 0.41 s |
| `tests.py` (full) | 55.5 s | 43 s |
| index build (once per kb change) | - | about 3 s, 24 MB |

