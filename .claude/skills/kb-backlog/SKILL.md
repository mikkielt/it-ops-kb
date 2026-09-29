---
name: kb-backlog
description: Use when the user asks to plan or break down work on it-ops-kb itself (an epic, stories, tasks, subtasks), to file or triage a bug in the project, to reprioritise the backlog or to see what is planned: writes items in kb/_self/backlog/ with backlog.py and checks them.
argument-hint: "[epic \"<outcome>\" | \"<what to plan>\" | bug \"<defect>\" | triage | show]"
---

# Plan the backlog

Read `kb/_self/backlog.md` first, the whole runbook (levels, fields, priority and severity, gates, the definition of done: planning uses nearly all of it), then this section, with its own command (`selfdoc.py section` prints the section under a heading with its line numbers):
- `python3 _tools/selfdoc.py section maintaining "Conduct for changes"` (the gate, commit messages)

`python3 _tools/backlog.py` with `-h` is the command reference.

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): the shared permission rules match single commands, so a chained command asks for approval or is refused in a headless run.

Whenever you name an item (in chat, a question, a commit), give its id and its title together, never a bare id.

## Plan ("<what to plan>")
1. See what exists: `python3 _tools/backlog.py tree` and `python3 _tools/backlog.py horizon`. Extend an epic or story that already covers the request rather than adding a parallel one.
2. Find the facts the work rests on: `python3 _tools/rag.py pack -q "<part>" -q "<part>"` for the product side, and `kb/_self/` for how the kb works. Name them in the items' `links` or `notes`.
3. Interview the operator on anything the request leaves open: scope, what must not change, the checks that prove it, and gates. Ask with AskUserQuestion, a recommendation first, before writing items. Do not invent requirements.
4. Write the items top down with `python3 _tools/backlog.py new KIND --title ...`, then edit their JSON:
   - an epic states the outcome;
   - each story is one verifiable capability that lands in one push, with a `goal` and `checks` (argv lists, no shell);
   - each task is one commit, with `touches` globs as narrow as the work allows;
   - `depends_on` wherever order matters;
   - a gate for each question only the operator can settle (the always-blocking list is in the runbook), with options and a recommendation.
5. New stories and bugs stay `draft` and outside any sprint unless the operator says which sprint.
6. `python3 _tools/backlog.py fmt`, then `python3 _tools/backlog.py check` must print `errors=0`.
7. Show the result with `python3 _tools/backlog.py tree <epic>` and say what is still open.

## Epic ("<outcome>")
An outcome that takes several pushes. Plan it as below, with these steps first:
1. `python3 _tools/backlog.py tree` shows whether an epic already covers the outcome. If one does, extend it and say so.
2. Interview the operator before writing anything, in one AskUserQuestion batch, a recommendation first:
   - the outcome as a fact about the repository once done;
   - what is out of scope, and what must not change;
   - which command would prove the whole epic;
   - the decisions only the operator can make.
3. `python3 _tools/backlog.py new epic --title T --goal "<outcome>"`. Add the epic's own checks, if any.
4. Write its first stories, only the ones whose goal and checks are clear now, each with `--parent EP-...`. Everything else stays in the epic's `notes` until it is refined in a later `/kb-backlog` or `/kb-sprint plan`.
5. Put each open decision as a gate on the story it blocks, with options and a recommendation.
6. `fmt`, `check`, then `python3 _tools/backlog.py tree EP-...`. Report the epic's id and title, its stories, and the gates waiting on the operator.

## Bug ("<defect>")
1. Reproduce it with one command that fails now and will pass once it is fixed (a test with `-k`, a tool call with `match`).
2. Pick a severity by the runbook's table and a priority. An `S1` goes into the active sprint (`--sprint`), and you tell the operator at once.
3. `python3 _tools/backlog.py new bug --title T --severity S --repro "CMD" --goal G [--parent EP] [--sprint SP]`. `new` refuses a repro that passes: then the defect is not reproduced yet.
4. Add tasks only if the fix is known. Otherwise the bug stays one item, and `/kb-item` breaks it down.

## Triage
List what needs deciding:
- `python3 _tools/backlog.py list --status draft`;
- bugs without a sprint;
- items whose trigger may have fired (fire them with `python3 _tools/backlog.py fire ID` once the event is confirmed).

Propose priority, severity, sprint or drop for each, in one AskUserQuestion batch. Apply the answers, then run `fmt` and `check`.

## Finish
Commit the item files with a `KB-Work:` trailer naming the items, in the message's last paragraph with `Co-Authored-By` and the other trailers. Commit only when the user asked. Then run `python3 _tools/kbgit.py sync --push` (`/kb-git-sync` when it stops).
