---
name: kb-item
description: Use when the user asks to work on one item of it-ops-kb's own backlog (an id such as ST-xxxxxxxx, "the next task", "fix bug BG-..."): claims it, works it within its scope, proves it done with backlog.py done and lands it.
argument-hint: "[ID | next]"
---

# Work one backlog item

Read `kb/_self/backlog.md` first (the item file, the definition of done, gates), then `kb/_self/maintaining.md`. The item's own change may also need its skill (a new topic: `/kb-add-topic`; facts: `/kb-refresh` or `/kb-research`; tools and docs: `/kb-self`).

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): the shared permission rules match single commands, so a chained command asks for approval or is refused in a headless run.

Whenever you name an item (in chat, a question, a commit), give its id and its title together, never a bare id.

1. **Pick.** Use the given id, or `python3 _tools/backlog.py next --any`. Then run `python3 _tools/backlog.py show ID` and say in one line which item and why.
   - If it waits on something, say what and stop. Offer the operator's answer to a blocking gate, or `python3 _tools/backlog.py fire ID` for a trigger that has happened.
2. **Claim.** `python3 _tools/backlog.py claim ID --by <session or agent name>`.
3. **Goal.** `python3 _tools/backlog.py goal ID` prints the condition. Keep it in view; the operator may set it as `/goal`.
4. **Break down if needed.**
   - A story or bug with no tasks: add tasks (`new task --parent ID`, with `touches` and `checks`), one commit each.
   - A task with several distinct steps may get subtasks.
   - Work the children first, each through steps 2 to 6.
5. **Work.**
   - Change only files matching `touches`. If the work needs another file, widen `touches` in the item and say so in the commit body.
   - A defect outside the item becomes a bug (`/kb-backlog bug`), not a fix.
   - A question only the operator can settle becomes a gate with options and a recommendation:
     - blocking: stop this item and pick the next;
     - provisional: `python3 _tools/backlog.py answer ID GATE --provisional` and go on.
     In an interactive session, ask the operator at once as well.
6. **Prove.**
   1. Commit the work with the trailer `KB-Work: ID`.
   2. Run `python3 _tools/backlog.py done ID` and show its output. On refusal, fix what it names and run it again. Never edit `status` or `evidence` by hand.
   3. Commit the item file with the same trailer.
7. **Land.**
   1. `/kb-verify` on the changed files (and `/kb-self` if tools, skills, hooks or rules changed).
   2. `python3 _tools/kbgit.py sync --push` (`/kb-git-sync` when it stops).
   3. Report the item's id and title, the commit, the checks that passed and the new horizon (`python3 _tools/backlog.py horizon`).

When all its siblings are done, the parent story or bug is ready. Its own `done` runs its checks over the whole.
