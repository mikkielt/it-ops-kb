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

What each gives: `backlog "Git"` the `KB-Work` trailer; `maintaining "Conduct for changes"` the gate, commit messages.

The item's own change may also need its skill (a new topic: `/kb-add-topic`; facts: `/kb-refresh` or `/kb-research`; tools and docs: `/kb-self`).

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): the shared permission rules match single commands, so a chained command asks for approval or is refused in a headless run.

Whenever you name an item (in chat, a question, a commit), give its id and its title together, never a bare id.

1. **Pick.** Use the given id, or `python3 _tools/backlog.py next --any`. Then run `python3 _tools/backlog.py show ID` and say in one line which item and why.
   - If it waits on something, say what and stop. Offer the operator's answer to a blocking gate, or `python3 _tools/backlog.py fire ID` for a trigger that has happened.
   - Work lands only once the item is claimed in a started sprint (`kb/_self/backlog.md`, Git): `check-trailers` refuses the push otherwise. `next --any` may pick an item outside one: its `sprint` (or its nearest parent's) is missing, or not `active` in `python3 _tools/backlog.py list --kind sprint`. Before any work commit, a bug joins a started sprint: set its `"sprint"` to an active sprint's id and commit that with the claim. A story (or a task or subtask, which follows its story), or no active sprint, is the operator's call: ask, and stop until they answer.
2. **Claim.**
   1. `python3 _tools/backlog.py claim ID --by <session or agent name>`.
   2. Commit the claim at once, before any work: stage only the item's file in `kb/_self/backlog/` and commit it on its own with the trailer `KB-Work: ID` (a backlog-planning commit). `check-trailers` reads the item as each commit has it, so work committed while the claim is uncommitted counts as unclaimed and its push is refused (`kb/_self/backlog.md`, Git).
3. **Goal.** `python3 _tools/backlog.py goal ID` prints the condition. Keep it in view; the operator may set it as `/goal`.
4. **Break down if needed.**
   - A story or bug with no tasks: add tasks (`new task --parent ID`, with `touches` and `checks`), one commit each.
   - A task with several distinct steps may get subtasks.
   - Work the children first, each through steps 2 to 7.
5. **Work.**
   - Change only files matching `touches`. If the work needs another file, widen `touches` in the item and say so in the commit body.
   - A defect outside the item becomes a bug (`/kb-backlog bug`), not a fix.
   - A question only the operator can settle becomes a gate with options and a recommendation:
     - blocking: stop this item and pick the next;
     - provisional: `python3 _tools/backlog.py answer ID GATE --provisional` and go on.
     In an interactive session, ask the operator at once as well.
6. **Commit.** Commit the work with the trailer `KB-Work: ID` in the message's last paragraph, with `Co-Authored-By` and the other trailers (no blank line between them). Then `/kb-verify` on the changed files (and `/kb-self` if tools, skills, hooks or rules changed).
7. **Prove and land** with one command, never the steps by hand: `python3 _tools/backlog.py land ID --branch <your branch> --trailer 'Co-Authored-By: ...'` (the branch defaults to `work/ID`; `main` if you worked there). Show its output. From a clean tree it fetches, rebases the branch on the integration `main`, then:
   - a content-only item: `backlog.py done ID --commit` (never edit `status` or `evidence` by hand), `stress_test.py`, the lookup eval and the contract lint when the landing changed `_tools/`, and `kbgit.py sync --push`, straight to `main`;
   - an item with a code-lane commit (`_tools/kblane.py`) not yet on the integration `main`: the same checks, then `sync --push`, which sends the range as a `code/<id>` merge request; `main` does not move and the item is not done yet. Report that and stop; on a later pass, once the request has merged, run the same `land` again: it rebases onto the merged `main`, runs `done --commit` and pushes the item file (a content-lane commit).

   It stops at the first failing step and names it (`land stopped at step <step>`); fix the cause and run it again:
   - `clean tree`: commit or stash your own changes (`git status --short`);
   - `rebase` (aborted, nothing changed): rebase by hand, resolving by meaning as `/kb-git-sync` does;
   - `done`: fix what it names (for an unmerged `code/<id>` request, merge it first) and commit;
   - `stress_test.py`, `rag.py eval`, `lint`: fix the cause, never the baseline;
   - `kbgit.py sync --push`: `/kb-git-sync`.

   A bug filed while landing is committed on its own, then claimed, before the commit that fixes it (`kb/_self/backlog.md`, Working on items).
8. **Report** the item's id and title, the commit, the checks that passed and the new horizon (`python3 _tools/backlog.py horizon`).

When all its siblings are done, the parent story or bug is ready. Its own `done` runs its checks over the whole.
