# Git: commits, sync, merging and history

## Commands (`_tools/kbgit.py`)

| command | does |
|---|---|
| `python3 _tools/kbgit.py sync [--push] [--dry-run] [--remote R] [--branch B]` | the way to push: fetch, rebase onto `origin/main`, fix, gate, push (exit 0 done, 1 gate red or push rejected, 2 refused, 3 conflict needs `/kb-git-sync` or a human) |
| `python3 _tools/kbgit.py fix [--check] [--base REV] [--upstream REV]` | after any merge or pull: dedupe/merge the union-merged ledgers, renumber colliding legacy ids (the `--upstream` side, already pushed, keeps its ids), rename colliding answer ids to `QK-<slug>`, rebuild the index (exit 1 `--check` stale, 2 needs a human); `fmt` only canonicalises the CSV ledgers |
| `python3 _tools/kbgit.py install-hooks [--uninstall]` | once per clone: `core.hooksPath=.githooks`, so commits get their KB-* trailers and a plain `git push` runs the gate |
| `python3 _tools/kbgit.py trailers [--staged] [REV] [--verified YYYY-MM-DD]` | print the KB-* trailers of the staged change or of a commit; `--amend` rewrites HEAD's message with them |
| `python3 _tools/kbgit.py check-trailers [A..B]` | exit 1 listing kb commits whose trailers are missing or wrong (default: CI's push range, else `@{upstream}..HEAD`) |
| `python3 _tools/kbgit.py log <S-id, topic, QK-id or path> [-n N]` | commits that touched it: by trailer, else by diff (`git log -G`) or path history |
| `python3 _tools/kbgit.py blame PATH:LINE` / `asof <YYYY-MM-DD or tag> PATH` / `tag-census YYYY-MM-DD` | the commit that wrote a line plus its sources' urls / a file as of a date or tag / annotated tag `census-YYYY-MM-DD` on HEAD (not pushed) |

History commands exit 0 on success, 1 when check-trailers finds a bad commit or log/blame/asof find nothing, 2 on bad arguments or outside a git clone.

## Workflow

- Small team, direct push: work on `main` or a short local branch and push straight to `main`. There are no merge requests and no protected-branch process; CI runs on every push and tag as a safety net: `.gitlab-ci.yml` on GitLab, `.github/workflows/kb.yml` on GitHub (the same tests, the stress suite, trailers, `_self/` docs, doc2query keys, artifacts). With direct pushes CI detects a bad push after the fact; only a merge-request workflow could prevent one (decided 2026-09-27: not worth it here).
- One logical change per commit, and every commit passes `python3 _tools/check.py` and `python3 _tools/build_index.py --check`. A source row goes in the same commit as the facts that cite it; a `superseded_by` goes in the same commit as the re-pointed citations; a change to the tools or skills goes with the `_self/` docs that describe it.
- Before pushing: `python3 _tools/kbgit.py sync --push`. It refuses a dirty tree (commit or stash first), fetches, rebases your commits onto `origin/main`, resolves the ledgers and generated files mechanically (`kbgit.py fix`, committed as `chore(kb): kbgit fix after sync`), refreshes stale trailers, runs the gate (`build_index.py --check`, `check.py`, `fetch.py --offline`, `doc2query.py stale`, `selfdoc.py stale --since origin/main`, fast `tests.py`, `check-trailers`) and pushes only when it is green. `--dry-run` shows what would happen.
- **The pre-push hook** (`.githooks/pre-push`, installed with the commit hooks) runs the same gate plus `kbgit.py fix --check` before a plain `git push` of the checked-out branch, and refuses the push when a check fails. It skips sync's own push (`KB_GATE_DONE=1`: sync gated already), tags and deletes, and says so for a pushed ref that is not HEAD (the checks read the working tree). `git push --no-verify` skips it; CI then reports what it would have caught. Prefer `sync --push`: it also rebases and fixes the ledgers.
- Never `git push --force`, never push with a red gate, never rewrite pushed history.
- Exit 3 means a conflict in an article, tool or doc: the rebase is left in progress with the paths listed. Resolve it with `/kb-git-sync` (by meaning: both sides' facts kept, newer confirmed evidence wins a changed fact, real disagreements go to `_conflicts.md`), or by hand the same way, or back out with `git rebase --abort`. Exit 1 (red gate): `/kb-git-sync` fixes the cause, never the baseline.
- Census tags: `python3 _tools/kbgit.py tag-census YYYY-MM-DD`, then `git push origin census-YYYY-MM-DD`. A census tag says "the kb was confirmed current as of this date" (the tag message counts the sources and the `_fetch_state.csv` checks); create it only after a full verification.

## Merging (what sync automates)

- `.gitattributes` merges the append-only ledgers (`_sources.csv`, `_fetch_state.csv`, `_answers.md`, `_gaps.md`, `_conflicts.md`) and the generated `_coverage.csv` and `_tools/lint_baseline.txt` with git's built-in union driver: parallel additions merge without conflict markers, but git keeps both sides' lines, so a row both sides touched may appear twice. Nothing to configure per clone.
- The append-style tool data (`_tools/signals.csv`, `_tools/aliases.csv`, `_tools/lookup_eval.csv`, `_tools/doc2query/expansions.csv`) merges with union too, but `fix` does not clean it: keep both sides' rows, one row per signal, alias term or eval id (tests.py fails on a duplicate signal or alias), then `doc2query.py stale` and `rag.py eval` (`/kb-git-sync`, Tool data).
- Writers: append rows and blocks, keep each CSV record on one line, never reorder or rewrap existing lines.
- Merge and rebase with `-c merge.conflictStyle=diff3` (sync does; by hand: `git -c merge.conflictStyle=diff3 pull --rebase`). Without it git keeps lines that two added blocks both end with only once, so two answers ending in `_Agent: kb-research_` interleave and the commit edits the other side's answer. fix restores such a section in the working tree when it knows the sides.
- `sync` runs fix for you. After a merge or pull made by hand: `python3 _tools/kbgit.py fix`, then `python3 _tools/tests.py`. If two branches took the same legacy id, fix asks for `--base $(git merge-base A B)` and renumbers the new rows to hash ids; add `--upstream origin/main` when one side is already pushed, so its ids stay. An answer id both sides took is renamed to `QK-<slug>` on the local side, mentions included. Exit 2 means a human decision (listed); nothing was written.
- `_self/coverage.md` merges normally; a conflict inside its coverage table is rebuilt by fix (then `git add _self/coverage.md`). Conflict markers anywhere else in it stop fix.

## Commit trailers

- Run `python3 _tools/kbgit.py install-hooks` once per clone. The commit-msg hook appends trailers computed from the staged diff against the first parent: `KB-Topics` (topics whose article or data files changed), `KB-Sources-Added`/`-Changed`/`-Superseded` (`_sources.csv` rows), `KB-Answers` (`_answers.md` ids). Only non-empty ones, sorted and `, `-joined; more than 40 values become `N ids (see diff)`. Never type them by hand; the hook replaces them on `--amend` and never blocks a commit. Merge commits get none.
- `KB-Verified: YYYY-MM-DD` only when the commit confirms its sources are current (e.g. a `/kb-refresh` that re-read them): `KB_VERIFIED=2026-09-25 git commit ...` or `git commit --trailer "KB-Verified: 2026-09-25"`.
- `git commit --no-verify` skips the hook; the CI job `kb-trailers` then fails for the push. `sync` checks them before it pushes and rewrites stale ones on the unpushed commits; repair unpushed commits yourself with `python3 _tools/kbgit.py trailers --amend` (HEAD) or `git rebase --exec "python3 _tools/kbgit.py trailers --amend" @{upstream}`. Pushed history is never rewritten; commits up to `e5dadde` (before trailers existed) are exempt.
- `Self-Reviewed: <doc>, <doc>` is typed by hand: it names kb docs (`_self/`, `AGENTS.md`, `README.md`) that were checked against the commit's change and needed no edit, so `selfdoc.py stale` stops listing them (`/kb-self`).
- Reading them: `kbgit.py log S-k3f7q2zd` / `log auth/kerberos` / `log QK-...`, `kbgit.py blame auth/kerberos.md:42`, `kbgit.py asof 2026-06-30 auth/kerberos.md`, or `git log --format='%h %(trailers:key=KB-Topics,valueonly)'`.
