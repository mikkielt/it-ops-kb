---
name: kb-item
description: Use when the user asks to work on one item of it-ops-kb's own backlog (an id such as ST-xxxxxxxx, "the next task", "fix bug BG-..."): claims it, works it within its scope, proves it done with backlog.py done and lands it.
argument-hint: "[ID | next]"
---

# Work one backlog item

Read these sections of the `kb/_self/` docs first, not the whole docs, in one command (`selfdoc.py section` prints the section under each heading with its line numbers):

```
python3 _tools/selfdoc.py section backlog "The item file" backlog "Dependencies, gates and triggers" backlog "Definition of done" backlog "Working on items" backlog "Git" maintaining "Conduct for changes"
```

What each gives: `backlog "Working on items"` the steps and the test tier; `backlog "Git"` the `KB-Work` trailer; `maintaining "Conduct for changes"` the gate, commit messages.

The item's own change may also need its skill (a new topic: `/kb-add-topic`; facts: `/kb-refresh` or `/kb-research`; tools and docs: `/kb-self`).

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): the shared permission rules match single commands, so a chained command asks for approval or is refused in a headless run.

Whenever you name an item (in chat, a question, a commit), give its id and its title together, never a bare id.

1. **Pick.** Use the given id, or `python3 _tools/backlog.py next --any`. Then run `python3 _tools/backlog.py show ID` and say in one line which item and why.
   - If it waits on something, say what and stop. Offer the operator's answer to a blocking gate, or `python3 _tools/backlog.py fire ID` for a trigger that has happened.
   - Work lands only once the item is claimed in a started sprint (`kb/_self/backlog.md`, Git): `check-trailers` refuses the push otherwise. `next --any` may pick an item outside one: its `sprint` (or its nearest parent's) is missing, or not `active` in `python3 _tools/backlog.py list --kind sprint`. Before any work commit, a bug joins a started sprint: `python3 _tools/backlog.py move ID --sprint SP` with an active sprint's id (`set --sprint` refuses a draft item into an active sprint; `move` makes it `todo` there), committed with the claim. A story (or a task or subtask, which follows its story), or no active sprint, is the operator's call: ask, and stop until they answer.
2. **Claim.**
   1. `python3 _tools/backlog.py claim ID --by <session or agent name> --commit --trailer 'Co-Authored-By: ...'`: it writes the claim and commits it at once (below). Work in your own worktree from the first command: each session works in its own git worktree from its first command (`git worktree add`), never a checkout another session works in: `claim` records the claims made in a working tree in its own git dir and refuses (exit 1, naming the other session) a claim by a second session while one of them is still doing there (`tests.py -k claim_refuses_a_shared_checkout`).
   2. The claim commit is made before any work: `--commit` stages only the item's file in `kb/_self/backlog/` and commits it on its own with the trailer `KB-Work: ID` (a backlog-planning commit); without `--commit` stage and commit it by hand the same way. `check-trailers` reads the item as each commit has it, so work committed while the claim is uncommitted counts as unclaimed and its push is refused (`kb/_self/backlog.md`, Git).
3. **Goal.** `python3 _tools/backlog.py goal ID` prints the condition. Keep it in view; the operator may set it as `/goal`.
4. **Break down if needed.**
   - A story or bug with no tasks: add tasks (`new task --parent ID --touch G --check CMD`, later `set ID --touch G --add` or `--check CMD --add`), one commit each.
   - A task with several distinct steps may get subtasks.
   - Work the children first, each through steps 2 to 7.
5. **Work.**
   - Change only files matching `touches`. If the work needs another file, widen `touches` with `python3 _tools/backlog.py set ID --touch PATH --add` and say so in the commit body.
   - A defect outside the item becomes a bug (`/kb-backlog bug`), not a fix.
   - Before any code: a choice the goal leaves open on an item whose `touches` name a rule-guarding path (the `agents-rule` paths of `_tools/bl_authority.py`: `_tools/bl_*`, `_tools/backlog.py`, `.claude/skills/`, `.claude/settings.json`, `AGENTS.md` and the others) is a blocking operator gate, added and asked before any code is written, never settled by the worker and held after the work; and a provisional answer about a shared map or naming rule (a map such as `kb/_self/map.csv`, an id or name scheme other items follow) is put to the operator when it is recorded, not left for the review.
   - A question only the operator can settle becomes a gate: `python3 _tools/backlog.py gate add ID --question Q --option O --option O --recommendation R [--kind blocking|provisional]`, the recommendation one of the options:
     - blocking: stop this item and pick the next;
     - provisional: `python3 _tools/backlog.py answer ID GATE --provisional` and go on.
     In an interactive session, ask the operator at once as well.
6. **Commit.** Before committing, plant one case per clause of the goal (a planted input, or the fix reverted for the run) and see each fail: a clause with no planted case can go unmet while the item's tests pass. Commit the work with the trailer `KB-Work: ID` in the message's last paragraph, with `Co-Authored-By` and the other trailers (no blank line between them). Then `/kb-verify` on the changed files (and `/kb-self` if tools, skills, hooks or rules changed). Before landing run only the narrow tier of the three test tiers (`kb/_self/backlog.md`, Working on items): the item's own checks, `-k "ruff or tools_map"` and the focused tests of the files you changed, never `tests.py --changed` (the sync gate runs it once per landing), the full `tests.py` or `stress_test.py` (the sprint's review story runs them once).
7. **Prove and land** with one command, never the steps by hand: `python3 _tools/backlog.py land ID --branch <your branch> --trailer 'Co-Authored-By: ...'` (the branch defaults to `work/ID`; `main` if you worked there). A landing is a long command: start it in the background with the Bash tool's longest `timeout`, 7200000 ms, never in the foreground, which is lost at the 10-minute limit; wait for its completion notice, then show its output. From a clean tree it fetches, rebases the branch on the integration `main`, then:
   - a content-only item: `backlog.py done ID --commit` (`status`, `claimed_by` and `evidence` are written only by `claim` and `done`, never edited; `set` refuses them), `selfdoc.py stale --since origin/main`, the lookup eval and the contract lint when the landing changed `_tools/` (`stress_test.py` runs once, with the full `tests.py`, at the sprint's review story), and `kbgit.py sync --push`, straight to `main`;
   - an item with a code-lane commit (`_tools/kblane.py`) not yet on the integration `main`: the same checks, then `sync --push`, which sends the range as a `code/<id>` merge request; `main` does not move and the item is not done yet. Then read the request: `glab mr view code/<id> -F json -R <project url>`. `state` `opened` with a `merge_error` is an auto-merge that failed: retry once with `python3 _tools/backlog.py merge <id>` and name the error in your report; a retry that fails too is reported with its error and left to the operator, never tried a third time. Report that and stop; on a later pass, once the request has merged, run the same `land` again: it rebases onto the merged `main`, runs `done --commit` and pushes the item file (a content-lane commit). To finish in one run, start it as `land ID --wait-merge 1800 ...` instead: it waits up to that many seconds for the merge, read from git, then does the second pass; never write a poll loop of your own.

   It stops at the first failing step and names it (`land stopped at step <step>`); fix the cause and run it again:
   - `clean tree`: commit or stash your own changes (`git status --short`);
   - `rebase` (aborted, nothing changed): rebase by hand, resolving by meaning as `/kb-git-sync` does;
   - `done`: fix what it names (for an unmerged `code/<id>` request, merge it first) and commit;
   - `checks` (a code item): its check or repro failed before anything was pushed; fix the cause and commit;
   - `stale`: `land` ran `selfdoc.py stale --since origin/main` over the rebased range before the lookup eval; read each doc it lists, edit it or name it in the `Self-Reviewed` trailer (amend the message whole with `git commit --amend -F`), then run it again;
   - `rag.py eval`, `lint`: fix the cause, never the baseline;
   - `kbgit.py sync --push`: `/kb-git-sync`.

   A bug filed while landing is filed with `--sprint SP` (an active sprint; or `backlog.py move ID --sprint SP`, which makes a draft bug `todo` there), committed on its own, then claimed, before the commit that fixes it: `check-trailers` refuses a `KB-Work` id not in a started sprint (`kb/_self/backlog.md`, Working on items).
8. **Report** the item's id and title, the commit, the checks that passed and the new horizon (`python3 _tools/backlog.py horizon`). Then stop: one session works one item, and the next item starts in a fresh session (`/clear` or a new one), so this item's reading and output do not stay in its context.

When all its siblings are done, the parent story or bug is ready. Its own `done` runs its checks over the whole.
