---
name: kb-sprint
description: Use when the user asks to plan, start, run, review or close a sprint of it-ops-kb's own backlog, or to orchestrate the backlog's work end to end: runs the sprint from kb/_self/backlog/ with backlog.py, dispatching ready items to subagents in worktrees and landing them one at a time.
argument-hint: "plan \"<goal>\" | start SP-... | run [SP-...] | review SP-... | close SP-..."
---

# Run a sprint

Read these sections of the `kb/_self/` docs first, not the whole docs, each with its own command (`selfdoc.py section` prints the section under a heading with its line numbers):
- `python3 _tools/selfdoc.py section backlog "Sprints"`
- `python3 _tools/selfdoc.py section backlog "Dependencies, gates and triggers"`
- `python3 _tools/selfdoc.py section backlog "Definition of done"`
- `python3 _tools/selfdoc.py section backlog "Working on items"`
- `python3 _tools/selfdoc.py section backlog "Git"` (the `KB-Work` trailer)
- `python3 _tools/selfdoc.py section maintaining "Conduct for changes"` (the gate, commit messages)
- `python3 _tools/selfdoc.py section git "Workflow"` (sync and the gate)

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): the shared permission rules match single commands, so a chained command asks for approval or is refused in a headless run.

Whenever you name an item (in chat, a question, a subagent brief, a commit), give its id and its title together, never a bare id.

## plan "<goal>"
1. Run `python3 _tools/backlog.py new sprint --title T --goal G`. It creates the sprint, its blocking `start` gate and its review story.
2. Pick the stories and bugs with `python3 _tools/backlog.py tree` and `python3 _tools/backlog.py list --kind bug`: every `S1` and `P1`, then by priority and rank, as far as the goal needs. Set `"sprint"` on each. Break stories into tasks as `/kb-backlog` does, with `touches` and `checks`.
3. `fmt` and `check`, then `python3 _tools/backlog.py horizon --sprint SP` (it shows the start gate as the one thing everything waits on).
4. Ask the operator to approve the goal and the committed items (AskUserQuestion: approve / change / cancel). Show each item's id and title and the gates they will meet.

## start SP
Only on the operator's approval in this conversation:
1. `python3 _tools/backlog.py answer SP start --answer approve --by operator`.
2. `python3 _tools/backlog.py start SP`.

Never answer the start gate yourself.

## run [SP]
You are the orchestrator. Loop:
1. Run `python3 _tools/backlog.py horizon --sprint SP` and `python3 _tools/backlog.py next --sprint SP --all`.
2. From the ready list, take up to four items whose `touches` do not overlap each other or any item in flight. Claim each: `python3 _tools/backlog.py claim ID --by <subagent name>`.
3. Start one subagent per item with `isolation: "worktree"`, on the agent its kind takes:
   - a task or subtask: `subagent_type: "kb-worker"` (`.claude/agents/kb-worker.md`, the newest Sonnet at high effort);
   - an `S1` or `S2` bug and its tasks and subtasks, and a story or bug with no tasks yet (its breakdown): a subagent on the session model (`subagent_type: "general-purpose"`).
   Never pass the Agent tool's `model`: it replaces the agent's own model.
   Brief it with:
   - the item's JSON and its `/goal` text (`python3 _tools/backlog.py goal ID`);
   - the runbook's Working on items;
   - "commit on a local branch `work/<id>` with `KB-Work: <id>` in the message's last paragraph, with `Co-Authored-By` and the other trailers; never push";
   - "file a bug for any defect outside the item, do not fix it";
   - "record a gate with a recommendation instead of guessing, and stop";
   - "never write the operator's decisions into docs or code".
   An item with a single commit and a narrow `touches` may be done in this session instead.
4. When a subagent returns, land its branch yourself, one at a time:
   1. rebase it on `main`;
   2. `python3 _tools/backlog.py done ID`;
   3. commit the item file with the same trailer;
   4. `/kb-verify` on the changed files;
   5. `python3 _tools/kbgit.py sync --push` (`/kb-git-sync` when it stops).
   If `done` refuses, send the reasons back to the same subagent (SendMessage) or release the item (`python3 _tools/backlog.py release ID`) and file what blocks it.
5. A provisional gate: take the recommendation (`answer ID GATE --provisional`) and go on. A blocking gate: its items wait. In an interactive session ask the operator now, in one batch with the recommendations.
6. Stop when `next` prints nothing ready. Report the horizon: what landed, and what waits on which gate or trigger (each with its question).

## review SP
The review story is ready once every other item is done or dropped. Its work:
1. Confirm or change each provisional answer with the operator (`answer ID GATE --confirm`, or a new answer plus a task or bug for the change).
2. Start a fresh-context reviewer subagent on the session model (`subagent_type: "general-purpose"`, no `model`) on the sprint's diff (`git log --grep "KB-Work"` over the sprint's items). Give it each item's goal. It reports only gaps that affect correctness or a goal.
3. File each gap as a bug (`/kb-backlog bug`): `S1` into this sprint, others to the backlog.
4. `python3 _tools/backlog.py done <review id>`.

## close SP
1. `python3 _tools/backlog.py close SP` deletes the sprint, its items and the epics they finished. It refuses while anything is open.
2. **Retrospective.** From this sprint's evidence, list what went wrong in the process, not in the product:
   - a `done` that refused;
   - a check that passed although the item did not work;
   - a gate that should have been asked earlier;
   - a subagent brief that missed something;
   - a rule in `kb/_self/backlog.md` or a skill that got in the way.
   Show the list to the operator. Each change they accept becomes a backlog story (`/kb-backlog`) naming the failure it answers. Write nothing into the docs directly.
3. Commit with `KB-Work: SP-...` in the last trailer paragraph and a body that lists:
   - each closed item's id and title and what it delivered;
   - the retrospective's findings, each with the story it became or "no change".
4. `python3 _tools/kbgit.py sync --push`.
