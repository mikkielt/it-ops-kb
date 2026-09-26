# MAINTAINING.md

Rules for changing the kb: setup, tools, content rules, git, merging, commits. Read it before any edit, research, refresh, census or commit; a lookup needs only `AGENTS.md`. Kept out of `AGENTS.md` because that file loads into every session and every subagent.

## Setup (first session in a fresh clone)

Run `/kb-setup` (Claude Code), or do the same by hand. In Claude Code on the web, `.claude/hooks/session-start.sh` (a SessionStart hook in `.claude/settings.json`) already installs the commit hooks, runs `check.py` and points the new session to `work-left.md`, on every start, resume and `/clear`.

1. **Python 3.9+** as `python3`. Nothing to install: the tools use the standard library only.
2. **Checks pass on a clean tree:**
   - `python3 _tools/check.py` -> `errors=0`
   - `python3 _tools/fetch.py --offline` -> `mismatch=0 unknown=0`
   - `python3 _tools/stress_test.py` -> no failures
3. **MCP servers are in place.** `python3 _tools/kb_mcp.py --register-local` registers, at local scope (this machine and this clone only), the `kb` server and the three documentation servers of `.claude-plugin/it-ops-kb-docs/.mcp.json` (listed in `AGENTS.md`). The root has no `.mcp.json` on purpose: the `it-ops-kb` plugin is sourced from the root, and a plugin loads its root `.mcp.json` whatever `plugin.json` says, so the docs servers live in their own plugin.

   - `claude mcp list` must show `kb` and the three docs servers `Connected`. Their tools keep the names `.claude/settings.json` allows (`mcp__kb`, `mcp__microsoft-learn__...`).
   - `Failed`: check network or proxy access to the url; the servers need no credentials.
   - Do not load the plugin in a clone (`--plugin-dir .`): the project skills and agents and the local servers would load a second time under plugin names.
   - Other agents (not Claude Code): register the same three urls as streamable-HTTP MCP servers in your client.
   - Optional, per user: GitHub's read-only repository server needs a personal token. Add it at user scope, never in a repo file:
     `claude mcp add --scope user --transport http github-repos-ro https://api.githubcopilot.com/mcp/x/repos/readonly --header "Authorization: Bearer $GITHUB_PAT"`
4. **Commit hook:** `python3 _tools/kbgit.py install-hooks`, once per clone. It only sets the local `git config core.hooksPath .githooks`; the versioned commit-msg hook then adds the KB-* trailers to every kb commit (see Commits and history).
5. **Do not** run `python3 _tools/fetch.py --diff` over the whole kb as part of setup: it is a long network job that writes `_fetch_state.csv`. A whole-kb baseline is the maintainer's decision; a targeted `--diff` from `/kb-refresh` is committed with that refresh.

## Tools

| command | does |
|---|---|
| `python3 _tools/rag.py pack "<question>" [--budget 1200] [-d DOMAIN] [--format concise]` | the evidence pack: `coverage: good/weak/none`, the best fact lines by article, one source footer (start lookups here); `-q PART -q PART` batches up to 6 parts, a verdict each and one footer. Product aliases (`_tools/aliases.csv`: sccm, memcm, configmgr, ...) match each other but never count as key words |
| `python3 _tools/rag.py facts PREFIX [--tag UNK,COMMUNITY] [--format detailed]` / `audit [PREFIX] [--status partial] [--entries] [--unlinked]` | fact lines by tag kind / per-article status, tag counts and linked gap and conflict entries (`--unlinked`: entries no topic links yet); both concise unless `--format detailed` |
| `python3 _tools/rag.py topics-for PATH... [--keywords TEXT]` | kb topics that code touches, from the curated signals in `_tools/signals.csv` (`signal,topic`; a test checks every topic exists) |
| `python3 _tools/rag.py src S123 [--cited]` / `eval` | resolve a source id, with every line that cites it / run the lookup eval set `_tools/lookup_eval.csv` |
| `python3 _tools/rag.py search "<query>" -k 8 [-d DOMAIN] [-u] [--index]` | line search on the pack index (facts, prose, data rows; at most 2 hits per file); `-u` adds a footer of source urls; root index files only with `--index` |
| `python3 _tools/rag.py show PATH:LINE -n 30` / `src S123` / `topics [DOMAIN]` | read lines / resolve a source id (`S123` or `S-k3f7q2zd`) / list articles |
| `python3 _tools/census.py check` / `record LOG` / `confirm LOG` / `sample LOG` / `summary LOG` | the census (`/kb-census`): a mechanical verdict per source in `_census/<date>.csv`, phase-2 outcomes, dates only for confirmed sources, the phase-4 sample |
| `python3 _tools/kb_mcp.py [--status] [--register-local]` | the read-only `kb` MCP server over stdio (`kb_pack`, `kb_facts`, `kb_audit`, `kb_search`, `kb_show`, `kb_source`, `kb_status`, `kb_topics_for`); the plugin starts it; `--status` prints kb_status once; `--register-local` sets up a clone's local-scope servers |
| `python3 _tools/doc2query.py split [--exclude ARMS]` / `batch ARM\|--path PREFIX [--out FILE]` / `ingest FILE` / `evaluate FILE` / `stale` / `prune` | document expansion for pack: generated questions per fact in `_tools/doc2query/expansions.csv` (Doc2Query-- filtered), pilot arms and evaluation; `stale` lists keys whose fact text changed (exit 1; tested), `prune` removes them. Protocol: `_tools/doc2query/README.md` |
| `python3 _tools/kb_ask.py "<question>" [--route] [--no-model] [--model M]` | a headless answer routed by the pack's verdict, not by a model: good -> Haiku with the pack in the prompt (one turn, no tool call), weak/none -> Sonnet with the live-docs tools; `--route` prints the choice, `--no-model` prints a good pack |
| `python3 _tools/agent_bench.py OUT.jsonl CONFIG[,..] SCENARIO[,..] [REPS]` / `--summary OUT.jsonl` | paid headless `claude -p` benchmark of lookups per model and hand-off pattern: cost, time, cache tokens, tool calls, answer checks (results: `token-usage-report.md`) |
| `python3 _tools/kb_hook.py --test "kb: <question>"` | the UserPromptSubmit hook behind `kb:` prompts (settings.json and the plugin): prints what it would answer |
| `python3 _tools/kbid.py url <URL>` / `answer "<question>"` / `eval "<question>"` / `check` | id for a new source / `QK-<slug>` for a new answer / `EV-<slug>` for a new `lookup_eval.csv` row / hash-id consistency |
| `python3 _tools/build_index.py [--check]` | regenerate `_coverage.csv`, the README coverage table and `used_in` from the articles (`--check`: report only, exit 1 if stale) |
| `python3 _tools/kbgit.py fix [--check] [--base REV] [--upstream REV]` | after any merge or pull: dedupe/merge the union-merged ledgers, renumber colliding legacy ids (the `--upstream` side, already pushed, keeps its ids), rename colliding answer ids to `QK-<slug>`, rebuild the index (exit 1 `--check` stale, 2 needs a human); `fmt` only canonicalises the CSV ledgers |
| `python3 _tools/kbgit.py sync [--push] [--dry-run] [--remote R] [--branch B]` | the way to push: fetch, rebase onto `origin/main`, fix, gate, push (exit 0 done, 1 gate red or push rejected, 2 refused, 3 conflict needs `/kb-git-sync` or a human) |
| `python3 _tools/kbgit.py install-hooks [--uninstall]` | once per clone: `core.hooksPath=.githooks`, so commits get their KB-* trailers |
| `python3 _tools/kbgit.py trailers [--staged] [REV] [--verified YYYY-MM-DD]` | print the KB-* trailers of the staged change or of a commit; `--amend` rewrites HEAD's message with them |
| `python3 _tools/kbgit.py check-trailers [A..B]` | exit 1 listing kb commits whose trailers are missing or wrong (default: CI's push range, else `@{upstream}..HEAD`) |
| `python3 _tools/kbgit.py log <S-id, topic, QK-id or path> [-n N]` | commits that touched it: by trailer, else by diff (`git log -G`) or path history |
| `python3 _tools/kbgit.py blame PATH:LINE` / `asof <YYYY-MM-DD or tag> PATH` / `tag-census YYYY-MM-DD` | the commit that wrote a line plus its sources' urls / a file as of a date or tag / annotated tag `census-YYYY-MM-DD` on HEAD (not pushed) |
| `python3 _tools/check.py` | source ids, superseded_by, answer ids, citations, artifacts, front matter, CSV shape |
| `python3 _tools/fetch.py --offline` | pinned artifacts vs their sha256 |
| `python3 _tools/fetch.py --status --topic T` | offline: when a topic's sources were last fetched or changed |
| `python3 _tools/fetch.py --diff --topic T [--full] [--json]` | re-fetch a topic's sources and diff against the last fetch (exit 0 same, 1 changed, 2 error) |
| `python3 _tools/stress_test.py [--scale N] [-k NAME]` | robustness tests on throwaway copies of the kb (`test_stress.py`, parametrized cases, in parallel) |
| `python3 _tools/tests.py [-k NAME]` | what CI (`.gitlab-ci.yml`) runs: every `_tools/test_*.py` but the stress suite, with pytest and pytest-xdist through `uv run --frozen` (`KB_TESTS_FAST=1`: without the `git` scenarios, the sync gate); `--write-lint-baseline` accepts current lint errors as known debt |
| `pyproject.toml`, `uv.lock` (dev group: pytest, pytest-xdist, ruff) | the test environment, installed by uv (`uv sync`, or on the first `tests.py`); the tools stay stdlib-only. Shared fixtures and helpers live in `_tools/conftest.py` (`Repo`, `git_env`, `copy_kb`, markers `git` and `stress`). `ruff check` (pyflakes rules) must stay clean: `tests.py` runs it. `uv run pytest` runs everything, stress included. After changing the dev group: `uv lock` |
| `python3 .claude/skills/kb-verify/lint.py [PREFIX...]` | contract checks beyond check.py (report only) |

## Plugin (`.claude-plugin/`)

- The repo root is a Claude Code marketplace with two plugins. `it-ops-kb` (the root): the `kb` server, `/kb-lookup`, `/kb-review-workspace`, the `kb-lookup` and `kb-reviewer` agents (`.claude/agents/`) and the `kb:` hook. `it-ops-kb-docs` (`.claude-plugin/it-ops-kb-docs/`): the three docs servers and a PreToolUse hook blocking `submit_feedback`. Install and runbook: README, "Use from another project".
- What reaches a host project: only the `kb` server's instructions and tool descriptions, the skill and agent names and descriptions, and their bodies when used. `AGENTS.md` and `MAINTAINING.md` never load there, and `rag.py` is not on its path: a rule a host must follow goes into those texts, and they name `rag.py` only as the clone form (tested).
- Keep it read-only: `plugin.json` lists the two skills and the two agent files by path (the kb's `agents/` domain is articles, so never the default `agents/` scan). No `Write`, `Edit`, `Bash` or git in a plugin skill's `allowed-tools` or an agent's `tools`. Never add a root `skills/`, `commands/`, `hooks/`, `bin/` or similar directory, or a root `.mcp.json`: the plugin would load it. No `version` field: users get each commit. `python3 _tools/test_kb_mcp.py` checks these and runs `claude plugin validate` on both plugins when the CLI is installed.
- Plugin agents honour `model`, `effort`, `maxTurns`, `tools`, `skills`, `omitClaudeMd` and a few more, and ignore `permissionMode`, `hooks` and `mcpServers`. `effort` goes in an agent, never in a skill: a skill's effort overrides the host session's while it runs. The agents list the kb tools under both names, `mcp__plugin_it-ops-kb_kb__*` (a host) and `mcp__kb__*` (a clone's local server).
- `/kb-lookup` is the only skill Claude may invoke on its own; every other skill sets `disable-model-invocation: true`, which keeps its description out of every session (tested).

## Skills that change the kb (`.claude/skills/`)

- `/kb-setup`: the setup above, with a pass/fail report.
- `/kb-research <question>`: research a question in the context of the topics the kb already has, then extend them.
- `/kb-refresh <topic|dir|file|S-id>`: diff sources and update the facts.
- `/kb-add-topic <domain>/<slug>`: research and write a new topic.
- `/kb-census [date]`: confirm every source is current (census.py checks, reading the undecided ones, dates only for what was confirmed, sample check, census tag).
- `/kb-verify [prefixes]`: quality gate before a commit or a push.
- `/kb-git-sync [--push]`: sync with `origin/main` when `kbgit.py sync` stops (exit 1 or 3): resolves article, tool and doc conflicts by meaning, fixes a red gate, pushes only when asked.

## Content rules (summary; `README.md` is authoritative)

- One topic = `<domain>/<topic>.md` with front matter `topic, priority, applies_to, retrieved_utc, sources, status` and sections Summary, Facts, Reference, Examples. `topic` equals the path.
- Every fact ends in exactly one tag with ids from `_sources.csv`: `DOC`, `DER` (show the derivation), `COMMUNITY` (never the only evidence for a DOC fact), `UNK`. Canonical forms: `[DOC <id>, <id>]`, `[DER <id>: how]`, `[COMMUNITY <id>]`, `[UNK]` or `[UNK: why]`; `_tools/kbfacts.py` parses them for every tool (grammar in its docstring), and the kb-verify lint reports a DOC or COMMUNITY tag without an id.
- Add the source row before the fact. A new source's id is `S-` + 8 characters from `python3 _tools/kbid.py url <URL>` (a hash of the url, so parallel writers converge); never invent one or take "the next number". Legacy `S<number>` ids stay valid; reuse the existing id when the url already has a row. Write CSVs with a real CSV writer: an unquoted comma breaks the row.
- A replaced source (e.g. a pinned commit url whose upstream changed) gets a new row; the old row's `superseded_by` names the new id. Ids are never deleted or reused.
- New `_answers.md` entries are `## QK-<slug>. <question>` (`python3 _tools/kbid.py answer "<question>"`); answer ids are unique.
- `_coverage.csv`, the README coverage table, `n_sources` and `used_in` are generated: after any content change run `python3 _tools/build_index.py`, never edit them by hand (CI fails when they are stale). Extra files of a topic go in its front matter `files: [...]`; a topic with no `.md` goes in `_tools/index_extra.csv`. Failed lookups go in `_gaps.md`, disagreements in `_conflicts.md`; each new entry ends with `(topic: <domain>/<slug>)` so `rag.py audit` links it to its article (check.py rejects a marker naming no topic).
- Retrieval data in `_tools/` (CSV writer, one row per line): a topic about code with distinctive names (classes, API routes, libraries, scopes) gets `signals.csv` rows (`signal,topic`) for `topics-for`; a product known by other names gets `aliases.csv` rows (`term,canonical`, term lowercase). A real lookup that missed an article the kb has becomes a `lookup_eval.csv` row, id `python3 _tools/kbid.py eval "<question>"` (`EV-<slug>`). After rewording or removing facts, `python3 _tools/doc2query.py stale` lists orphaned expansion keys (exit 1); `doc2query.py prune` removes their rows (regenerate only where real lookups miss; `_tools/doc2query/README.md`). `python3 _tools/rag.py eval` must pass every question.
- Licensing: our own words, quotes of 25 words or fewer; verbatim only under permissive licences (MIT, Apache-2.0, CC BY 4.0) with attribution; never copy CIS or ISO text. Microsoft Learn content fetched through MCP is paraphrased.
- Placeholders only in examples: `PL-LT-00123`, `PL-SRV-0042`, `corp.example.com`, tenant `00000000-0000-0000-0000-000000000000`, `jan.kowalski`. Never real hostnames, tenants, people or secrets.
- `UNK` and `COMMUNITY` facts are leads to verify, not a basis to build on.

## Git workflow

- Small team, direct push: work on `main` or a short local branch and push straight to `main`. There are no merge requests and no protected-branch process; CI (`.gitlab-ci.yml`) runs on every push and tag as a safety net.
- One logical change per commit. Run `python3 _tools/kbgit.py install-hooks` once per clone (KB-* trailers).
- Before pushing: `python3 _tools/kbgit.py sync --push`. It refuses a dirty tree (commit or stash first), fetches, rebases your commits onto `origin/main`, resolves the ledgers and generated files mechanically (`kbgit.py fix`, committed as `chore(kb): kbgit fix after sync`), refreshes stale trailers, runs the gate (`build_index.py --check`, `check.py`, fast `tests.py`, `check-trailers`) and pushes only when it is green. `--dry-run` shows what would happen.
- Never `git push --force`, never push with a red gate, never rewrite pushed history.
- Exit 3 means a conflict in an article, tool or doc: the rebase is left in progress with the paths listed. Resolve it with `/kb-git-sync` (by meaning: both sides' facts kept, newer confirmed evidence wins a changed fact, real disagreements go to `_conflicts.md`), or by hand the same way, or back out with `git rebase --abort`. Exit 1 (red gate): `/kb-git-sync` fixes the cause, never the baseline.
- Census tags: `python3 _tools/kbgit.py tag-census YYYY-MM-DD`, then `git push origin census-YYYY-MM-DD`.

## Merging (what sync automates)

- `.gitattributes` merges the append-only ledgers (`_sources.csv`, `_fetch_state.csv`, `_answers.md`, `_gaps.md`, `_conflicts.md`) and the generated `_coverage.csv` and `_tools/lint_baseline.txt` with git's built-in union driver: parallel additions merge without conflict markers, but git keeps both sides' lines, so a row both sides touched may appear twice. Nothing to configure per clone.
- The append-style tool data (`_tools/signals.csv`, `_tools/aliases.csv`, `_tools/lookup_eval.csv`, `_tools/doc2query/expansions.csv`) merges with union too, but `fix` does not clean it: keep both sides' rows, one row per signal, alias term or eval id (tests.py fails on a duplicate signal or alias), then `doc2query.py stale` and `rag.py eval` (`/kb-git-sync`, Tool data).
- Writers: append rows and blocks, keep each CSV record on one line, never reorder or rewrap existing lines.
- Merge and rebase with `-c merge.conflictStyle=diff3` (sync does; by hand: `git -c merge.conflictStyle=diff3 pull --rebase`). Without it git keeps lines that two added blocks both end with only once, so two answers ending in `_Agent: kb-research_` interleave and the commit edits the other side's answer. fix restores such a section in the working tree when it knows the sides.
- `sync` runs fix for you. After a merge or pull made by hand: `python3 _tools/kbgit.py fix`, then `python3 _tools/tests.py`. If two branches took the same legacy id, fix asks for `--base $(git merge-base A B)` and renumbers the new rows to hash ids; add `--upstream origin/main` when one side is already pushed, so its ids stay. An answer id both sides took is renamed to `QK-<slug>` on the local side, mentions included. Exit 2 means a human decision (listed); nothing was written.
- `README.md` merges normally; a conflict inside its coverage table is rebuilt by fix (then `git add README.md`).

## Commits and history

- One logical change per commit, and every commit passes `python3 _tools/check.py` and `python3 _tools/build_index.py --check`.
- A source row goes in the same commit as the facts that cite it; a `superseded_by` goes in the same commit as the re-pointed citations.
- Run `python3 _tools/kbgit.py install-hooks` once per clone. The commit-msg hook appends trailers computed from the staged diff: `KB-Topics` (topics whose article or data files changed), `KB-Sources-Added`/`-Changed`/`-Superseded` (`_sources.csv` rows), `KB-Answers` (`_answers.md` ids). More than 40 values become `N ids (see diff)`. Never type them by hand; the hook replaces them on `--amend` and never blocks a commit. Merge commits get none.
- `KB-Verified: YYYY-MM-DD` only when the commit confirms its sources are current (e.g. a `/kb-refresh` that re-read them): `KB_VERIFIED=2026-09-25 git commit ...` or `git commit --trailer "KB-Verified: 2026-09-25"`.
- `git commit --no-verify` skips the hook; the CI job `kb-trailers` then fails for the push. `sync` checks them before it pushes (`python3 _tools/kbgit.py check-trailers` by hand) and rewrites stale ones on the unpushed commits; repair unpushed commits yourself with `python3 _tools/kbgit.py trailers --amend` (HEAD) or `git rebase --exec "python3 _tools/kbgit.py trailers --amend" @{upstream}`. Pushed history is never rewritten; commits up to `e5dadde` (before trailers existed) are exempt.
- Lookups: `kbgit.py log S-k3f7q2zd` / `log auth/kerberos` / `log QK-...`, `kbgit.py blame auth/kerberos.md:42`, `kbgit.py asof 2026-06-30 auth/kerberos.md`. `kbgit.py tag-census YYYY-MM-DD` tags HEAD `census-YYYY-MM-DD` ("the kb was confirmed current as of this date") after a full verification; push the tag explicitly (`git push origin census-YYYY-MM-DD`).

## Conduct for changes

- Do not edit files listed in `_artifacts.csv` by hand; they are pinned by sha256 (`fetch.py --refresh` rewrites them).
- Before proposing a commit: `python3 _tools/tests.py` passes (CI runs it; lint errors in `_tools/lint_baseline.txt` are known debt, new ones fail), `stress_test.py` passes if `_tools/` changed, and `/kb-verify` shows no new errors in the files you touched.
- Commit messages: conventional prefix (`docs(kb):`, `fix(kb):`, `feat(kb):`, `chore:`), imperative, body explaining why; your own trailers (e.g. `Co-Authored-By`) in the last paragraph, and the hook appends the KB-* ones after them. Commit only when asked.
