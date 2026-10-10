---
description: Use when the user asks to work on one item of the project's backlog (an id such as ST-xxxxxxxx, "the next task", "fix bug BG-..."): claims it, works it within its scope, proves it done and lands it.
argument-hint: "[ID | next]"
---

# Work one backlog item

`${CLAUDE_PLUGIN_ROOT}` is the directory that holds the tool scripts: the plugin's, or, where this text runs from a clone's own copy and still shows the variable, that clone's top directory. The Bash tool does not set it: write the path where a command below shows it.

The project's `backlog.json` names the steps only some projects have (`python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py config` prints each setting). A step that depends on one (`kb_root`, `docs_map`, `land_stale`, `land_eval`, `land_lint`, `lane_module`) runs when the setting is set and is skipped, said so in one line, when it is empty or `[]`. When `kb_root` is set, rules are asked for, not read up front: `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/rag.py pack --root KB_ROOT --set <name>` prints a step's tested rule questions, with the sets `kb-item:claim` (before step 1 and 2), `kb-item:work` (before step 5), `kb-item:done` (before step 6) and `kb-item:land` (before step 7); once the item is claimed, `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/rag.py pack --root KB_ROOT --item ID --budget 600` prints the rules of the docs its touches map to. A rule you needed and no set gave you is a miss: say so in your report, with the question as you asked it.

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): permission rules match single commands, so a chained command asks for approval or is refused in a headless run.

Whenever you name an item (in chat, a question, a commit), give its id and its title together, never a bare id.

1. **Pick.** Use the given id, or `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py next --any`. Then run `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py show ID` and say in one line which item and why.
   - If it waits on something, say what and stop. Offer the operator's answer to a blocking gate, or `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py fire ID` for a trigger that has happened.
   - Work lands only once the item is claimed in a started sprint: `check-trailers` refuses the push otherwise. `next --any` may pick an item outside one. Before any work commit, a bug joins a started sprint: `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py move ID --sprint SP` with an active sprint's id, committed with the claim. A story (or a task or subtask, which follows its story), or no active sprint, is the operator's call: ask, and stop until they answer.
2. **Claim.**
   1. `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py claim ID --by <session or agent name> --commit --trailer 'Co-Authored-By: ...'` writes the claim and commits it at once. Work in your own git worktree from the first command: `claim` refuses a claim by a second session while one of them is still doing there.
   2. The claim commit is made before any work: `--commit` stages only the item's file and commits it on its own with the trailer `KB-Work: ID`; without `--commit` stage and commit it by hand the same way, since work committed while the claim is uncommitted counts as unclaimed and its push is refused.
3. **Goal.** `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py goal ID` prints the condition. Keep it in view.
4. **Break down if needed.**
   - A story or bug with no tasks: add tasks (`new task --parent ID --touch G --check CMD`, later `set ID --add-touch G` or `--add-check CMD`; `set --touch` replaces the whole list), one commit each.
   - A task with several distinct steps may get subtasks.
   - Work the children first, each through steps 2 to 7.
5. **Work.**
   - Change only files matching `touches`. If the work needs another file, widen `touches` with `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py set ID --add-touch PATH` and say so in the commit body.
   - A defect outside the item becomes a bug (`python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py new bug --title T --severity S --repro CMD --goal G`), not a fix.
   - Before any code: a choice the goal leaves open on an item whose touches guard a rule is a blocking operator gate, added and asked before any code is written, never settled by the worker and held after the work.
   - A question only the operator can settle becomes a gate: `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py gate add ID --question Q --option O --option O --recommendation R [--kind blocking|provisional]`, the recommendation one of the options:
     - blocking: stop this item and pick the next;
     - provisional: `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py answer ID GATE --provisional` and go on.
     In an interactive session, ask the operator at once as well.
6. **Commit.** Before committing, run the item's checks. A test is written only for one command's main path, one planted failure per gate, a machine-read format or a secret, leak or untrusted-code guard; a bug is proven by its `repro` and gets a retrospective finding, not a test, unless no log or gate output can show the defect. Commit the work with the trailer `KB-Work: ID` in the message's last paragraph, with `Co-Authored-By` and the other trailers (no blank line between them). Then run the project's verification, if it has one, on the changed files.
7. **Prove and land.** Use one command, never the steps by hand: `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py land ID --branch <your branch> --trailer 'Co-Authored-By: ...'` (the branch defaults to `work/ID`). A landing is a long command: start it in the background with the Bash tool's longest `timeout`, 7200000 ms, and wait for its completion notice, then show its output. From a clean tree it fetches, rebases the branch on the integration main, then:
   - an item with no code-lane commit: `done ID --commit`, then each landing step the project's settings name (`land_stale`, `land_eval`, `land_lint`; `[]` is skipped), then the push;
   - an item with a code-lane commit (`lane_module` names the module that says which lane a path belongs to): the same checks, then the push sends the range as a merge request, `main` does not move and the item is not done yet. Report that and stop; on a later pass, once the request has merged, run the same `land` again, or start it as `land ID --wait-merge 1800 ...`, which waits up to that many seconds for the merge, read from git; never write a poll loop of your own.

   It stops at the first failing step and names it (`land stopped at step <step>`); fix the cause and run it again: `clean tree` (commit or stash your own changes), `rebase` (aborted, nothing changed: rebase by hand, resolving by meaning; a resolved conflict in a source file must parse and keep every definition either side added), `done` (fix what it names), `checks` (a code item's check or repro failed before anything was pushed), `stale` (a doc the range leaves stale: read it, then edit it or name it in the `Self-Reviewed` trailer, amending the message whole with `git commit --amend -F`), `eval`, `lint` (fix the cause, never the baseline), or the push.

   A bug filed while landing is filed with `--sprint SP` (an active sprint; or `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py move ID --sprint SP`), committed on its own, then claimed, before the commit that fixes it: `check-trailers` refuses a `KB-Work` id not in a started sprint.
8. **Report** the item's id and title, the commit, the checks that passed and the new horizon (`python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py horizon`). Then stop: one session works one item, and the next item starts in a fresh session, so this item's reading and output do not stay in its context.

When all its siblings are done, the parent story or bug is ready. Its own `done` runs its checks over the whole.
