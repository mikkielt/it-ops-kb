---
description: Use when the user asks to plan or break down work on the project (an epic, stories, tasks, subtasks), to file or triage a bug in the project, to reprioritise the backlog or to see what is planned: writes items in the directory backlog.json names with the backlog tool and checks them.
argument-hint: "[epic \"<outcome>\" | \"<what to plan>\" | bug \"<defect>\" | triage | show]"
---

# Plan the backlog

`${CLAUDE_PLUGIN_ROOT}` is the directory that holds the tool scripts: the plugin's, or, where this text runs from a clone's own copy and still shows the variable, that clone's top directory. The Bash tool does not set it: write the path where a command below shows it.

The project's `backlog.json` names the steps only some projects have (`python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py config` prints each setting). A step that depends on one (`kb_root`, `docs_map`) runs when the setting is set and is skipped, said so in one line, when it is empty. When `kb_root` is set, rules are asked for, not read up front: `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/rag.py pack --root KB_ROOT --set <name>` prints a step's tested rule questions, with the sets `kb-backlog:plan` (before the Plan steps, also the Epic steps), `kb-backlog:bug`, `kb-backlog:triage` and `kb-backlog:finish`. A rule you needed and no set gave you is a miss: say so in your report.

`python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py` with `-h` is the command reference.

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): permission rules match single commands, so a chained command asks for approval or is refused in a headless run.

Whenever you name an item (in chat, a question, a commit), give its id and its title together, never a bare id.

## Plan ("<what to plan>")
1. See what exists: `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py find WORDS` first (open items whose title or goal hold every word, with parent chains; exit 1 when none), then `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py tree --open` and `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py horizon`. Extend an epic or story that already covers the request rather than adding a parallel one.
2. Find the facts the work rests on, and name them in the items' `links` or `notes` (`python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py set ID --link L --notes N` replaces, `--add-link L --add-notes N` appends).
3. Interview the operator on anything the request leaves open: scope, what must not change, the checks that prove it, and gates. Ask with AskUserQuestion, a recommendation first, before writing items. Do not invent requirements.
4. Write the items top down with `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py new KIND --title ...` (`--goal`, `--touch`, `--check`, `--depends` and `--priority` fill those fields as it creates the item; a story needs its `--goal` and checks that run real test or tool code), then add or change the rest with `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py set ID` (`--touch`, `--check`, `--link`, `--depends`, `--relates` and `--notes` replace the whole field and their twins `--add-touch`, `--add-check`, `--add-link`, `--add-depends`, `--add-relates` and `--add-notes` append to it; `--priority`, `--rank`, `--sprint`; `--clear FIELD`) and `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py gate add ID`, never by editing the item's JSON (`status`, `claimed_by` and `evidence` come only from `claim` and `done`); a planning commit's `KB-Work` names only items whose files it changes:
   - an epic states the outcome;
   - each story is one verifiable capability that lands in one push, with a `goal` and `checks` (argv lists, no shell);
   - a goal that names a step order (done, a push to the integration branch) keeps the lane rules' order: for an item with a code-lane commit (`lane_module`), `done` and the push to `main` come after its merge request merges;
   - a story that claims current behaviour is wrong records its premise in its `notes`: one command that shows that behaviour now, run before the sprint commits it; a premise that does not reproduce reshapes the story or drops it;
   - a story or task that adds a check or a gate rule runs it, or a draft of it, over the live repository before a sprint commits it, and records what it finds: the files that hold findings go in the item's `touches`;
   - each task is one commit, with `touches` globs as narrow as the work allows;
   - an item's `touches` are planned, not guessed: the files its change edits, each moved or renamed path or symbol's referrers (`python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py referrers PATH|SYMBOL... --item ID`, which marks each outside the item's scope, exit 1) and, when `docs_map` is set, the docs the map names for its code; a docs warning `check` gives for the item is acted on then, by adding the docs it names (`set ID --add-touch DOC`), in the same task, never a later docs task;
   - the same list covers every symbol or constant the goal changes (by name) and a new subcommand's facade registration: each file `referrers` lists is in `touches` before the claim, so a worker neither stops on a reader outside them nor widens them itself; a removed or renamed flag is run through `referrers` as a term, and each file that prints or documents it goes in too; a task adding a new tool module names the docs map's csv, and one adding a flag names its command facade and the readers it calls; an item that moves the figures of the benchmarks results file or the report code has `README.md` in its touches;
   - `depends_on` wherever order matters;
   - a gate for each question only the operator can settle, with options and a recommendation: `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py gate add ID --question Q --option O --option O --recommendation R [--kind blocking|provisional] [--do OPTION=CMD|ID] [--host-check CMD]`, the recommendation one of the options; `--do` names, for an option, the command that carries it out or the item whose work adds that command; `--host-check` is the command that exits 0 when the host setup an answer will name holds.
5. New stories and bugs stay `draft` and outside any sprint unless the operator says which sprint.
6. `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py fmt`, then `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py check` must print `errors=0`, and no warning about a new item's docs.
7. Show the result with `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py tree <epic>` and say what is still open.

## Epic ("<outcome>")
An outcome that takes several pushes. Plan it as above, with these steps first:
1. `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py find WORDS` and `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py tree --open` show whether an epic already covers the outcome. If one does, extend it and say so.
2. Interview the operator before writing anything, in one AskUserQuestion batch, a recommendation first: the outcome as a fact about the repository once done; what is out of scope and what must not change; which command would prove the whole epic; the decisions only the operator can make.
3. `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py new epic --title T --goal "<outcome>"`. Add the epic's own checks, if any, with `--check` on `new` or `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py set EP-... --check "CMD"`.
4. Write its first stories, only the ones whose goal and checks are clear now, each with `--parent EP-...`. Everything else stays in the epic's `notes` until it is refined in a later pass.
5. Put each open decision as a gate on the story it blocks (`python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py gate add ID --question Q --option O --option O --recommendation R`).
6. `fmt`, `check`, then `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py tree EP-...`. Report the epic's id and title, its stories, and the gates waiting on the operator.

## Bug ("<defect>")
1. Reproduce it with one command that fails now and will pass once it is fixed, running the failing behaviour: a tool call on a planted input, a command with a match, or, only when no log can show the defect, a test. A repro that only matches text in a file proves the text, not the fix; `new` refuses one without `--repro-reason TEXT` saying why the behaviour cannot run.
2. Pick a severity by the table in the project's backlog rules and a priority. An `S1` goes into the active sprint (`--sprint`), and you tell the operator at once.
3. A goal that names a fix mechanism (a hook, a capture point, a file to write, a command to call) is run through the project's rules (when `kb_root` is set: `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/rag.py pack --root KB_ROOT "<mechanism>"`) before `new` writes it: a rule it meets is named in the goal, or the mechanism is left open.
4. `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py new bug --title T --severity S --repro "CMD" --goal G [--parent EP] [--sprint SP]`. `new` refuses a repro that passes: then the defect is not reproduced yet. A bug's `touches` are planned as in Plan step 4: `referrers` on each symbol, constant or flag its fix changes, every file it lists in `touches` before the claim.
5. Add tasks only if the fix is known. Otherwise the bug stays one item, and the item skill breaks it down.

## Triage
List what needs deciding, intake's drafts first:
- the uncommitted drafts the SessionStart hook (`python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py intake --file --hook`; `red-pipeline --hook` files a red main's bug the same way) wrote: the new item files in `git status --porcelain -uall <item_dir>` (`??`) whose `links` carry `fingerprint <12 hex>` and `detector <name>` (`python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py show ID`). Show each with its detector, kind, title and goal. A kept one is committed with the rest of the triage (item files only, `KB-Work` naming them); a dropped one is deleted, since it was never committed;
- `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py list --status draft`;
- the parked drafts among them (`parked: SP-... review` or `parked: SP-... close`): propose a sprint for one only when its `notes` name the fitness test it blocks or a real user's report; list one that names neither as parked and leave it a draft in no sprint;
- bugs without a sprint;
- items whose trigger may have fired (fire them with `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py fire ID` once the event is confirmed).

Propose priority, severity, sprint or drop for each, in one AskUserQuestion batch. Apply the answers (`python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py set ID --priority P`, `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py move ID --sprint SP|none`, `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py drop ID --why W`, `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py reopen ID --why W`), then run `fmt` and `check`.

## Finish
Commit the item files with a `KB-Work:` trailer naming the items, in the message's last paragraph with `Co-Authored-By` and the other trailers. Commit only when the user asked. Then push through the project's route.
