# Work left

The open work, and only that: a finished item leaves this file (its commit records it). GitHub has no issues or merge requests for this repository; this list is the queue. Counts that move (partial articles, `UNK` facts, ledger entries) are commands here, not numbers.

## Query log: a self-improving lookup pipeline

Every kb lookup leaves a redacted, judged record in the repository (`kb/_querylog/`). `learn` turns the records into findings, and `apply` turns accepted findings into eval rows, aliases, expansions and `_gaps.md` entries, pushed straight to `main` once the local gate passes. The aim is better knowledge handling by agents, not an approval workflow for people to run: no merge requests unless a conflict needs one. Stages: capture (hooks, local spool) -> distill (stdlib rules, then Haiku in batches) -> learn (deterministic findings) -> apply (local gate, then a direct push). Standard library only, plus the `claude` CLI for Haiku. It must run on macOS, Linux and Windows.

**Definition of done.** Every item below is done when its own three parts hold, never on a model's say-so (`agents/agent-planning-and-done.md`):
- the end state it names exists;
- the command it names proves it, and its output is in the session or the commit body (a transcript-only judge such as `/goal` must be able to see it);
- nothing outside its constraints changed.

The shared minimum for every item:
- the gate in `kb/_self/maintaining.md` passes, and the tests pass on Linux and Windows;
- every new gate has a test with a planted failure that makes it fail;
- no new dependency;
- portability: every file read or written passes `encoding="utf-8"` (and `newline="\n"` when writing), paths go through `pathlib`, and subprocesses take argument lists (never `shell=True` or a command string);
- `/kb-self` has run when `_tools/`, `.claude/`, `.claude-plugin/` or `.gitlab-ci.yml` changed;
- the commit carries its KB-* trailers and went through `kbgit.py sync --push`.

Work one item at a time, in this order; an item leaves this list in the commit that meets its definition.

Kb facts the build rests on: `claude/hooks.md` (async hooks, `prompt_id`, `Stop`'s `last_assistant_message`, the `SessionEnd` budget), `gitlab/automated-merge-requests.md` (push options for the conflict MR), `reuse/pseudonymization-tokenization.md` (SID and UPN shapes), `agents/docs-maintenance-agents.md` (committing machine-written data), `agents/agent-planning-and-done.md`, and the answers `QK-kb-need-know-build-query-log` and `QK-self-improving-lookup-pipeline-query-logging` in `kb/public/_answers.md`.

**Decisions** (from the draft design and the maintainer's interview; the draft itself is not in the repository; `kb/_self/querylog.md` is the design doc built from them):
- Rules:
  - One owner per truth: the store owns logged lookups, and everything else derives from it and the kb.
  - Run metadata goes once per run file, never per entry.
  - Derived state converges: a second run on unchanged inputs changes nothing, and a test checks it.
  - Miss, candidate gap, gap, candidate fact and claim stay separate stages, each promotion recorded on the finding.
  - `learn` writes findings; `apply` turns accepted findings into changes.
  - Deterministic code first. Haiku only extracts questions, replaces names, summarises, and judges among candidate articles that code listed.
  - Every gate's failure path is tested.
- Surfaces logged:
  - `kb:`/`kb+:` hook prompts;
  - kb MCP tool calls (`PostToolUse` matchers `mcp__kb__.*` and `mcp__plugin_it-ops-kb_kb__.*`);
  - `kb_ask.py` runs, and the answer's outcome (`Stop`);
  - web and docs-server fetches, only in prompts that also used the kb or a kb change skill;
  - `fetch.py` and `census.py`, which write their own spool rows from inside, since Bash command-text parsing undercounts (and that undercount is accepted for other commands).

  The MCP server does not log (it never sees `session_id` or `prompt_id`). Rows join on `prompt_id`.
- Spool:
  - `_cache/querylog/spool/<session_id>.jsonl` in a clone, on every OS (short UUID names keep Windows paths short), and `${CLAUDE_PLUGIN_DATA}/querylog/spool/` in a host;
  - never committed; deleted once its distilled entry is pushed or dropped;
  - every `claude -p` the pipeline starts runs with `--settings '{"disableAllHooks": true}'`, so it never logs itself.
- Redaction:
  - stdlib rules, then Haiku on rule-redacted text only, then the rules and the leak scan again;
  - person and organisation names rest on Haiku, with no NER layer; the test corpus includes names, and an entry Haiku flags as still identifying is dropped with only its counts kept;
  - the redactor keeps well-known SIDs (`S-1-5-32-*`, `S-1-5-18`, ...) and any identifier a public root already contains (Graph app ids, CSP GUIDs), and redacts down-level `DOMAIN\name` as well as UPNs;
  - Haiku runs batched at distill (`claude -p --model haiku --tools ""`, no plugins or MCP), with per-batch and daily caps per machine; its output is stored once per entry id and never regenerated.
- Fetch outcomes: only facts are classified (HTTP status, empty, cross-host redirect, truncated); "bot page" and "the summary lacked it" stay `unknown`. Source signals (hosts to stage, routes misused) are report-only.
- A host's staging level comes from its provider-registry row (`_tools/providers.csv`, or a root's `_providers.csv`) when it has one, else from the routes table in `kb/_self/web-sources.md`; a test keeps the two in agreement.
- Store `kb/_querylog/`:
  - files: `<yyyy-mm>/<run-id>.jsonl` (a header line, then entries) and `findings/<yyyy-mm>/<run-id>.jsonl`, one file per run, so parallel pushes never touch the same file;
  - not a root: `pack` and `search` skip it, and the leak scan covers it;
  - never committed: the raw prompt or answer, `session_id`, `prompt_id`, `transcript_path`, user, host;
  - no `merge=union` re-check is needed, since nothing depends on it.
- Delivery:
  - Automatic changes (run files, findings, eval rows, aliases, expansions, gap entries and opt-in research) are pushed straight to `main` on `origin`, the repository the clone came from, once the local gate passes and a rebase on `origin/main` is clean.
  - Each commit carries a `KB-Auto: querylog|eval|alias|expansion|gap|research|revert` trailer.
  - Pushes go to `origin` only; mirroring to other remotes stays a person's job.
  - Every GitLab host name comes from `origin`'s url, with GitLab.com as the fallback; nothing is hard-coded.
  - A conflict that `kbgit.py sync` cannot resolve pushes a branch with `-o merge_request.create -o merge_request.target=main` (no auto-merge, no token) for a person or `/kb-git-sync`, and the findings stay pending.
  - Before any new push, distill checks the CI status of the last automatic commit (`glab api` on GitLab, `gh` on GitHub, skipped when neither is signed in); on red it pushes a revert commit and records `apply failed`, and a failed finding is never retried.
  - No CI job writes to the repository.
- Configuration: no environment variables. Program defaults are constants stated in the design doc. Per-user choices (`mode`: `auto`, `local`, `off`; `research`; `research_daily`) live in one uncommitted file, written by `/kb-setup`: `_private/querylog.json` in a clone, `${CLAUDE_PLUGIN_DATA}/querylog/config.json` in a host.
- The default is `auto`, and `/kb-setup` says plainly that colleagues' redacted questions are recorded in the repository and that rule-redacted text is sent to the API for Haiku (`claude/data-retention.md`). Items 3 to 6 run with the default `local` until the switch-on item.
- Research is opt-in per user with their own daily cap: add-only, quote-verified facts, and a disagreement goes to `_conflicts.md`. Its commits go to `main` directly like the rest; the gate and the quote check are its review.
- Plugin hosts distill in a managed clone under `${CLAUDE_PLUGIN_DATA}`; the first push refused for want of rights turns logging off for good (a `DISABLED` marker). Cloud sessions distill in the container and push to their own `origin`.
- Portability:
  - Hooks call one Python entry point that finds the interpreter on each OS (`python3`, `python` or `py -3`).
  - The per-machine lock uses no `fcntl` (atomic `mkdir` or an `O_EXCL` file with a stale-PID check).
  - The `SessionEnd` launcher detaches with `start_new_session` on POSIX and `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP` on Windows.
  - The tests pass on Linux, Windows and macOS.
- Reporting: a weekly digest from the committed store; `git log --format='%h %(trailers:key=KB-Auto,valueonly)'` is the audit trail.

**GitLab project state** (read with `glab api`; `glab` is signed in as the project Owner on the maintainer's machine):
- `origin` is a private project on GitLab.com (19.5), and the design must hold for any GitLab `origin`;
- merge method `merge`; **Pipelines must succeed** is off; remove source branch after merge is on;
- `main` is protected, with push and merge for Maintainers;
- **Allow Git push requests to the repository** is off (no CI job pushes);
- `.gitlab-ci.yml` runs branch and tag pipelines only (a direct-push model), which fits this design unchanged.

7. **Direct push, on the real `origin`:** once, `python3 _tools/querylog.py apply --push` lands one automatic commit on `main`, and one planted conflict ends as an open MR.
10. **Plugin hosts and cloud sessions.** Done: a host distills in a managed clone under `${CLAUDE_PLUGIN_DATA}`; a push refused for want of rights writes `DISABLED` and deletes the spool, while a network error or a red gate does not; a cloud session pushes to its own `origin`. Check: tests with a fake remote for each refusal kind, and the always-on measurement in `kb/_self/reports/token-usage.md` (not `claude plugin details`, which undercounts), which must show no rise from the new hooks.
11. **End-to-end run and switch-on.**

    Done:
    - end-to-end tests drive a temporary clone with a bare remote through capture (hook commands fed recorded stdin), distill (recorded Haiku), learn, apply and the push. After each scenario they check the store, the findings, the eval file, the ledgers, the spool and the gate. One test per scenario:
      - a `kb:` answer with `good` coverage: an entry, no finding, nothing pushed but the run file;
      - a miss fixed by an alias, one fixed by an expansion, and a miss with no accepted fix that ends as a `_gaps.md` entry under its topic;
      - a miss that passes on `HEAD` by the time `learn` runs (`fixed-since`, no change);
      - web and docs-server fetches beside a kb lookup (host and path only) and a fetch in a prompt without kb use (no row);
      - `kb_ask.py`, `fetch.py` and `census.py` rows joined to their prompt;
      - an identifier in a prompt (redacted in the run file), and an entry Haiku flags as still identifying (dropped, only counted);
      - more entries than the Haiku caps allow (the rest wait, and the next run takes them);
      - two clones distilling against one remote (separate run files, no duplicate id, no conflict);
      - a conflict with `origin/main` (the `querylog/<run-id>` branch with the MR push options, findings pending, held on the next run);
      - red CI on the last automatic commit (a revert, `apply-failed`, never retried), and `manual`, `skipped` or unfinished CI (not red);
      - research on, within its daily cap (a quote-checked fact added, a disagreement as a `_conflicts.md` entry), research over its cap, and research off;
      - modes `off`, `local` and `auto`, a `DISABLED` marker, and an unreadable config;
      - a session still open (not distilled), one closed by `SessionEnd`, and one closed by idle time;
      - a failed push (the spool stays) and a successful one (the spool goes only once its run file is on the remote);
      - a second run on unchanged inputs changes nothing.
    - `/kb-setup` states the default (logging, fixes, gap entries and pushes automatic; research off; what is recorded and what is sent to the API) and asks whether to keep it;
    - the program default becomes `auto`.

    Check: those tests on Linux, Windows and macOS, `/kb-verify`, and `selfdoc.py stale` with no stale doc. Unchanged: the `kb:` hook's answers, and people's `kbgit.py sync --push`.
12. **Benchmarks: one report, re-run and extended.** `kb/_self/reports/benchmark-bare-vs-kb.md` and `kb/_self/reports/token-usage.md` become one new report, `benchmarks.md`, in the same folder.

    Done:
    - every scenario of both old reports is run again with the current tools and models, by the method its setup section states, and each result sits beside its historical records (date, commit, model, value, change);
    - the historical records and the new runs are data in one committed results file beside the report, one row per scenario, run and metric, and the report's comparison tables are generated from it, not typed;
    - new scenarios cover what changed since the last runs, at least: the query-log hooks (always-on cost, per-prompt latency of capture, the `SessionEnd` launcher), distill, learn and apply (run time, Haiku tokens per entry, the adoption gates' effect on eval pass rate, mean pack and off-kb `good`), redaction speed, research cost per accepted fact, `/kb-ingest` on a sample repository, a host plugin with team roots, and the hook launcher's start-up on each OS;
    - one command re-runs every scenario (or one named scenario), and each section names its command;
    - every doc that cites the old reports (`design.md`, `token-efficiency.md`, `doc2query.md`, `plugin.md`, `querylog.md`, `tools.md`, `map.csv`, `README.md`, ...) points at the new sections, and the old files are gone;
    - `README.md` carries the new results: its opening comparison, the cost table and the benchmark section give the re-run numbers with their Claude Code version, kb size and date, name the new scenarios in a line each, and link the new report.

    Check: `grep -rn "benchmark-bare-vs-kb\|reports/token-usage" kb/ _tools/ .claude/ .claude-plugin/ README.md AGENTS.md` prints nothing; `python3 _tools/tests.py` (doc cohesion and links) and `selfdoc.py stale` pass; every number in `README.md` matches a row of the results file; re-running one old and one new scenario with its section's command reproduces its row within the noise the report states. Unchanged: each measurement's method, unless the report states the change beside its numbers.

## Watch

Triggers, not tasks: act when one fires.

- **`claude -p` defaults.** If `--bare` becomes the default for `claude -p`, `_tools/agent_bench.py` configs that rely on the clone's plugins and settings must load them explicitly; `_tools/kb_ask.py` already passes its servers.
- **Native citations.** The Messages API's `search_result` blocks give citations from tool results, but MCP does not carry them and the Agent SDK drops them from MCP tool results; revisit when MCP or Claude Code supports them. The block format is in `agents/hybrid-retrieval.md`.
