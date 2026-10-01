---
name: kb-git-sync
description: Use when the user asks to commit and push, sync, pull or merge it-ops-kb, or `kbgit.py sync` stopped with exit 1 or 3: resolves conflicts by meaning, fixes a red gate at its cause, pushes only when asked.
argument-hint: "[--push]"
---

# Sync it-ops-kb with origin/main

Arguments: $ARGUMENTS. Push only if they contain `--push` or the user asked to push; otherwise sync without pushing.

Read these sections of the `kb/_self/` docs first, not the whole docs, in one command (`selfdoc.py section` prints the section under each heading with its line numbers). The commands are spelled out in the steps below:

```
python3 _tools/selfdoc.py section maintaining "Conduct for changes" content-rules "Facts and tags" content-rules "Ledgers and retrieval data" git.md "Workflow" git.md "Merging (what sync automates)" git.md "Commit trailers"
```

What each gives: `maintaining "Conduct for changes"` the gate, commit messages; `content-rules "Facts and tags"` resolving articles; `content-rules "Ledgers and retrieval data"` resolving ledgers and tool data; `git "Workflow"` sync, the gate, exit codes.

`AGENTS.md` covers lookups only.

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): the shared permission rules match single commands, so a chained command asks for approval or is refused in a headless run.

Never `git push --force`, never `--no-verify`, never `git rebase --skip` a commit that carries the user's work, never rewrite pushed history. When a rule below says "ask", stop, leave the repository as it is (a rebase stays in progress) and explain what is decided and what is open.

## 1. Look, then sync
1. `python3 _tools/kbgit.py sync --dry-run`: incoming commits, and the files both sides changed (`needs a human if it conflicts` marks articles, tools and docs).
2. `python3 _tools/kbgit.py sync` (with `--push` only as allowed above). Read its report and branch on the exit code:
   - 0: done. Go to 5.
   - 1: gate failed, or the push was rejected twice. Go to 3.
   - 2: refused. Go to 4.
   - 3: needs judgment. Go to 2.

Always rebase with `-c merge.conflictStyle=diff3` (sync does). Without it git merges the ledgers "zealously": two answers added at one place that both end in `_Agent: kb-research_` interleave, the second spliced into the first above its footer, and the rebased commit then edits the other side's answer (its `KB-Answers` trailer names it). `fix` repairs such a splice when it knows the sides, but only in the working tree, not in the commit that made it.

## 2. Exit 3: resolve the conflict
Sync printed `needs-human: PATH` lines, `mechanical: PATH` lines, a `sync-state: base=… upstream=… orig_head=…` line and a `fix --base … --upstream … --side …` command. The rebase is in progress, stopped at one local commit (`git log -1 REBASE_HEAD`). Leave `mechanical:` paths to `fix`.

For each `needs-human` path, read the three versions: `git show :1:PATH` (base), `git show :2:PATH` (upstream, already pushed), `git show :3:PATH` (the local commit being replayed; in a rebase "theirs" is yours). Then edit the working file so no conflict markers remain; with diff3 each region also has a `||||||| base` part: remove it too.

**Articles** (`<domain>/<topic>.md`): resolve by meaning, never by taking one side for the whole article.
- Different facts added on both sides: keep both. Drop exact duplicates, keep the Facts section's structure (headings, order: upstream's first, then the local ones), one tag per fact.
- The same fact changed on both sides: if both versions say the same thing, keep one wording (upstream's) and the union of their tags' ids. Otherwise keep the version backed by newer confirmed evidence. Compare the cited sources' rows in `_sources.csv`: later `retrieved_utc` wins; a source with `superseded_by` loses to its successor; a DOC source beats COMMUNITY. If neither clearly wins, keep upstream's wording in the article, append a bullet under the topic's `## <domain>/<topic>` heading in `_conflicts.md` quoting both versions with their tags (`[DOC S1 vs S2, unresolved]`), and list it for the user.
- Front matter: `sources:` = the union of the ids the resolved text actually cites; `retrieved_utc` = the later date; `status: partial` if any `[UNK]` remains, else the stricter of the two; `files:` = the union; other keys: upstream's unless the local commit's change is the point of that commit.
- Ids: write both sides' ids exactly as each side has them, even a legacy id both sides took (`S2205`): `fix` renumbers the local side's afterwards. It attributes a line to the side that has it verbatim, and a new line you wrote (a merged `sources:` line) to the one side whose version of the file cites that id at all. If both sides' versions of this file cite the colliding id, keep each side's lines verbatim instead of merging them into one line.
- Deleted on one side, edited on the other (`git status` shows `DU`/`UD`): ask the user.

**Tool data** (`kb/public/_retrieval/signals.csv`, `_tools/aliases.csv`, `kb/public/_retrieval/lookup_eval.csv`, `kb/public/_retrieval/doc2query/expansions.csv`): union-merged like the ledgers, so they rarely stop a rebase, but `fix` does not clean them. After the rebase (or on a conflict made without `.gitattributes`): keep both sides' rows and drop exact duplicates. A key both sides changed (a signal, an alias term, an eval id) keeps one row: upstream's, unless the local change is the point of its commit. Two different eval rows under one id (two questions with one slug): add `-2` to the local one's id. Then `python3 _tools/doc2query.py stale` (a fact reworded on either side orphans its expansion rows: remove the listed keys' rows) and `python3 _tools/rag.py eval` (every question must pass).

**Tools, docs, skills, config** (`_tools/*`, `*.md` outside the domain directories, `.claude/*`, `.gitattributes`, `.gitlab-ci.yml`): merge conservatively so both sides' intents survive (both new flags, both fixes). If the two changes contradict each other, or you cannot tell what one side meant, ask.

Then, one command at a time:
1. The printed `python3 _tools/kbgit.py fix --base … --upstream … --side …` command. It merges the ledgers, renumbers local ids that collide with pushed ones (citations follow; the pushed side keeps its ids, legacy ones included), renames colliding answer ids to `QK-<slug>` and rebuilds the index. Exit 2 lists what it cannot decide (e.g. `cannot tell which url S2205 means here`: the line is on both sides, or it is new in a file both sides cite the id in; edit that line so it is clearly one side's, or ask), nothing written; fix and rerun.
2. `git add` the resolved paths and what fix wrote (`git status` lists them).
3. `git -c core.editor=true -c merge.conflictStyle=diff3 rebase --continue` (keeps the message; diff3 for the commits still to replay). A later local commit may stop again: repeat this section for it. `rebase --continue` does not run the commit-msg hook, so the replayed commit may lack its KB-* trailers or carry stale ones: sync rewrites them in step 4; never type them by hand.
4. When the rebase has ended: `python3 _tools/kbgit.py sync` again (with `--push` only as allowed above), to reach a green gate.

Exit 3 with "the rebase is complete" means `fix` itself needs a decision (e.g. one answer heading twice with different bodies): make it, commit it (`fix(kb): …`), rerun sync.

## 3. Exit 1: gate failed
- Read the failing check's output in the report. Fix the cause in the files the user's commits touched (`git diff --name-only origin/main...HEAD`): an unknown source id, a missing front-matter key, a stale index (`python3 _tools/build_index.py`), a new lint error, a leak-scan hit, a duplicate row in the tool data or a failing `rag.py eval` question (see Tool data in section 2).
- Never silence a check by editing `_tools/lint_baseline.txt`, `_tools/tests_allowlist.txt` or a test, unless the user agrees after you explain why.
- Commit the fix as its own commit (`fix(kb): …`), then rerun `python3 _tools/kbgit.py sync`. Bad trailers are repaired by sync itself.
- Push rejected twice: someone keeps pushing; wait, then rerun.
- A `code/<id>` push refused (the branch moved on the remote, exit 1, nothing overwritten): `git fetch`, look at what moved (`git log origin/code/<id>`), rebase onto it or rerun sync, which replaces `code/<id>` with `--force-with-lease`. Never force outside `code/*`.
- The remote takes no push options: open the merge or pull request by hand from the `code/<id>` branch sync pushed.
- The pre-push hook refuses a direct push of a code-lane commit to the integration `main`: use `python3 _tools/kbgit.py sync --push`, which sends it as `code/<id>`.

## 4. Exit 2: refused
Explain the reason sync printed and stop. Uncommitted changes: ask whether to commit them (one logical change per commit) or `git stash` them. An operation in progress: finish it (section 2 if it is this sync's rebase) or ask before `git rebase --abort`. Fetch failed: report it; do not retry in a loop.

## 5. Report
- Commits rebased and the final `git log --oneline origin/main..HEAD`.
- Per conflicted file: how it was resolved (facts kept from each side, which changed fact won and why).
- Ids renumbered and answer ids renamed (`old -> new`, from sync's `ids renumbered:` line and fix's output), and one `python3 _tools/kbgit.py log <new id>` showing the commit that carries it.
- Entries added to `_conflicts.md`, and every decision left to the user.
- Gate result per check; pushed or not (and why not).
