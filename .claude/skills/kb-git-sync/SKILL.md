---
name: kb-git-sync
description: Bring local it-ops-kb commits onto origin/main when `kbgit.py sync` cannot finish alone - resolve article, tool and doc conflicts by meaning (keep both sides' facts, newer confirmed evidence wins a changed fact, record real disagreements in _conflicts.md), fix a red gate at its cause, and push only when asked. Use when the user asks to sync, pull or push the kb, or sync stopped with exit 1 or 3.
disable-model-invocation: true
argument-hint: "[--push]"
---

# Sync it-ops-kb with origin/main

Arguments: $ARGUMENTS. Push only if they contain `--push` or the user asked to push; otherwise sync without pushing.

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): the shared permission rules match single commands, so a chained command asks for approval or is refused in a headless run.

Never `git push --force`, never `--no-verify`, never `git rebase --skip` a commit that carries the user's work, never rewrite pushed history. When a rule below says "ask", stop, leave the repository as it is (a rebase stays in progress) and explain what is decided and what is open.

## 1. Look, then sync
1. `python3 _tools/kbgit.py sync --dry-run`: incoming commits, and the files both sides changed (`needs a human if it conflicts` marks articles, tools and docs).
2. `python3 _tools/kbgit.py sync` (with `--push` only as allowed above). Read its report and branch on the exit code:
   - 0: done. Go to 5.
   - 1: gate failed, or the push was rejected twice. Go to 3.
   - 2: refused. Go to 4.
   - 3: needs judgment. Go to 2.

A branch from before the sync tooling (no `_tools/kbgit.py` in the checkout): sync cannot run there, and untracked copies of the tools block the checkout. Run `git fetch origin`, then `git rebase origin/main`, and treat a stop as exit 3 with `base` = `git merge-base origin/main ORIG_HEAD`, `upstream` = `origin/main`, `orig_head` = the branch's old tip (`git rev-parse ORIG_HEAD`). Its `_sources.csv` rows lack `superseded_by`, its `QK<n>` answer ids and hand-edited `_coverage.csv`/README rows are pre-regime: `fix` pads, renames and rebuilds them; do not patch them by hand.

## 2. Exit 3: resolve the conflict
Sync printed `needs-human: PATH` lines, `mechanical: PATH` lines, a `sync-state: base=… upstream=… orig_head=…` line and a `fix --base … --upstream … --side …` command. The rebase is in progress, stopped at one local commit (`git log -1 REBASE_HEAD`). Leave `mechanical:` paths to `fix`.

For each `needs-human` path, read the three versions: `git show :1:PATH` (base), `git show :2:PATH` (upstream, already pushed), `git show :3:PATH` (the local commit being replayed; in a rebase "theirs" is yours). Then edit the working file so no conflict markers remain.

**Articles** (`<domain>/<topic>.md`): resolve by meaning, never by taking one side for the whole article.
- Different facts added on both sides: keep both. Drop exact duplicates, keep the Facts section's structure (headings, order: upstream's first, then the local ones), one tag per fact.
- The same fact changed on both sides: keep the version backed by newer confirmed evidence. Compare the cited sources' rows in `_sources.csv`: later `retrieved_utc` wins; a source with `superseded_by` loses to its successor; a DOC source beats COMMUNITY. If neither clearly wins, keep upstream's wording in the article, append a bullet under the topic's `## <domain>/<topic>` heading in `_conflicts.md` quoting both versions with their tags (`[DOC S1 vs S2, unresolved]`), and list it for the user.
- Front matter: `sources:` = the union of the ids the resolved text actually cites; `retrieved_utc` = the later date; `status: partial` if any `[UNK]` remains, else the stricter of the two; `files:` = the union; other keys: upstream's unless the local commit's change is the point of that commit.
- Deleted on one side, edited on the other (`git status` shows `DU`/`UD`): ask the user.

**Tools, docs, skills, config** (`_tools/*`, `*.md` outside the domain directories, `.claude/*`, `.gitattributes`, `.gitlab-ci.yml`): merge conservatively so both sides' intents survive (both new flags, both fixes). If the two changes contradict each other, or you cannot tell what one side meant, ask.

Then, one command at a time:
1. The printed `python3 _tools/kbgit.py fix --base … --upstream … --side …` command. It merges the ledgers, renumbers local ids that collide with pushed ones (citations follow), renames `QK<n>` and colliding answer ids to `QK-<slug>` and rebuilds the index. Exit 2 lists what it cannot decide (e.g. `cannot tell which url S2205 means here`: the line exists on both sides or on neither; edit that line so it is clearly one side's, or ask), nothing written; fix and rerun.
2. `git add` the resolved paths and what fix wrote (`git status` lists them).
3. `git rebase --continue` (`GIT_EDITOR=true` keeps the message). A later local commit may stop again: repeat this section for it.
4. When the rebase has ended: `python3 _tools/kbgit.py sync` again, to reach a green gate.

Exit 3 with "the rebase is complete" means `fix` itself needs a decision (e.g. one answer heading twice with different bodies): make it, commit it (`fix(kb): …`), rerun sync.

## 3. Exit 1: gate failed
- Read the failing check's output in the report. Fix the cause in the files the user's commits touched (`git diff --name-only origin/main...HEAD`): an unknown source id, a missing front-matter key, a stale index (`python3 _tools/build_index.py`), a new lint error, a leak-scan hit.
- Never silence a check by editing `_tools/lint_baseline.txt`, `_tools/tests_allowlist.txt` or a test, unless the user agrees after you explain why.
- Commit the fix as its own commit (`fix(kb): …`), then rerun `python3 _tools/kbgit.py sync`. Bad trailers are repaired by sync itself.
- Push rejected twice: someone keeps pushing; wait, then rerun.

## 4. Exit 2: refused
Explain the reason sync printed and stop. Uncommitted changes: ask whether to commit them (one logical change per commit) or `git stash` them. An operation in progress: finish it (section 2 if it is this sync's rebase) or ask before `git rebase --abort`. Fetch failed: report it; do not retry in a loop.

## 5. Report
- Commits rebased and the final `git log --oneline origin/main..HEAD`.
- Per conflicted file: how it was resolved (facts kept from each side, which changed fact won and why).
- Ids renumbered and answer ids renamed (`old -> new`, from sync's `ids renumbered:` line and fix's output).
- Entries added to `_conflicts.md`, and every decision left to the user.
- Gate result per check; pushed or not (and why not).
