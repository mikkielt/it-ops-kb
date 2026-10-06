---
name: kb-backlog
description: Use when the user asks to plan or break down work on it-ops-kb itself (an epic, stories, tasks, subtasks), to file or triage a bug in the project, to reprioritise the backlog or to see what is planned: writes items in kb/_self/backlog/ with backlog.py and checks them.
argument-hint: "[epic \"<outcome>\" | \"<what to plan>\" | bug \"<defect>\" | triage | show]"
---

# Plan the backlog

Read the conduct rules first (`selfdoc.py section` prints one section with its line numbers):

```
python3 _tools/selfdoc.py section maintaining "Conduct for changes"
```

Every other rule of `kb/_self/` is asked for, not read up front. When a step below is reached, run its set: `python3 _tools/rag.py pack --root _self --set <name>` prints that step's tested rule questions, the line that answers each (`path:line`) and the decisions tied to them. The sets of this skill:
- `kb-backlog:plan`: before the Plan steps (also the Epic steps, which plan as the Plan does)
- `kb-backlog:bug`: before the Bug steps
- `kb-backlog:triage`: before the Triage steps
- `kb-backlog:finish`: before the Finish step

Any other rule: `python3 _tools/rag.py pack --root _self "<question>"` (`-q` for several parts, `--budget 400`). `coverage: good` names a tested question: follow its line. `weak` or `none`: `python3 _tools/kb_ask.py --root _self "<question>"` has a reader quote the answering lines from the sections, or read the section it names with `python3 _tools/selfdoc.py section DOC HEADING`. A rule you needed and no set or question gave you is a miss: say so in your report, with the question as you asked it.

`python3 _tools/backlog.py` with `-h` is the command reference.

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): the shared permission rules match single commands, so a chained command asks for approval or is refused in a headless run.

Whenever you name an item (in chat, a question, a commit), give its id and its title together, never a bare id.

## Plan ("<what to plan>")
Rules of this step: `python3 _tools/rag.py pack --root _self --set kb-backlog:plan`.

1. See what exists: `python3 _tools/backlog.py find WORDS` first (open items whose title or goal hold every word, with parent chains; exit 1 when none), then `python3 _tools/backlog.py tree --open` and `python3 _tools/backlog.py horizon`. Extend an epic or story that already covers the request rather than adding a parallel one.
2. Find the facts the work rests on: `python3 _tools/rag.py pack -q "<part>" -q "<part>"` for the product side, and `kb/_self/` for how the kb works. Name them in the items' `links` or `notes` (`backlog.py set ID --link L --notes N`, `--add` appends).
3. Interview the operator on anything the request leaves open: scope, what must not change, the checks that prove it, and gates. Ask with AskUserQuestion, a recommendation first, before writing items. Do not invent requirements.
4. Write the items top down with `python3 _tools/backlog.py new KIND --title ...` (`--goal`, `--touch`, `--check`, `--depends` and `--priority` fill those fields as it creates the item), then add or change the rest with `python3 _tools/backlog.py set ID` (`--touch`, `--check`, `--link`, `--depends`, `--relates` replace a list and `--add` appends to it; `--notes`, `--priority`, `--rank`, `--sprint`; `--clear FIELD`) and `python3 _tools/backlog.py gate add ID`, never by editing the item's JSON (`status`, `claimed_by` and `evidence` come only from `claim` and `done`, and `set` refuses them with the rule); a planning commit's `KB-Work` names only items whose files it changes:
   - an epic states the outcome;
   - each story is one verifiable capability that lands in one push, with a `goal` and `checks` (argv lists, no shell);
   - a goal that names a step order (done, `sync --push`, a push to `main`) keeps the lane rules' order: for an item with a code-lane commit, `done` and a push to `main` come after its `code/<id>` merge request merges;
   - a story that claims current behaviour is wrong records its premise in its `notes`: one command that shows that behaviour now (a failing check or a tool run), run before the sprint commits it. A premise that does not reproduce reshapes the story or drops it;
   - a story or task that adds a check or a gate rule (a `selfdoc.py`, `backlog.py` or `check.py` rule, a test that scans the repository) runs it, or a draft of it, over the live repository before a sprint commits it, and records what it finds: the files that hold findings go in the item's `touches`, or a bug the item depends on fixes them, so the check lands green;
   - a story or task that adds a check guarding a push (publish, a pre-push refusal, a mirror) asks what the push carries and records the answer in its `goal`: every commit of the pushed range, not only the final tree, and one planted failure for a bad commit that a later commit removes;
   - each task is one commit, with `touches` globs as narrow as the work allows;
   - an item's `touches` are planned, not guessed, when it is filed or scheduled: the files its change edits, each moved or renamed path or symbol's referrers (`python3 _tools/backlog.py referrers PATH|SYMBOL... --item ID`) and the `kb/_self/` docs `kb/_self/map.csv` maps its code to (`python3 _tools/selfdoc.py map <file>`), never a glob wider than those files (a `_tools/bl_*.py` glob meets every other worker's item, BG-ncpteupy); a docs warning `backlog.py check` gives for the item is acted on then, by adding the docs it names (`set ID --touch DOC --add`), so the warnings stay few enough to act on;
   - a task that moves, renames or deletes a file or a symbol holds the files that name it in its `touches`: `python3 _tools/backlog.py referrers PATH|SYMBOL... --item ID` lists them and marks each outside the item's scope (exit 1);
   - a task whose `touches` name code (`_tools/`, `.claude/`, `.claude-plugin/`, `.gitlab-ci.yml`) also names the `kb/_self/` docs that `kb/_self/map.csv` maps to that code (`python3 _tools/selfdoc.py map <file>` lists them), in the same task, never a later docs task that depends on it; a task that changes a tool's commands or flags writes their rows in the same commit. `kb/_self/git.md` asks for them in the same commit, so the landing needs no hand-written `Self-Reviewed` trailer, and sync's `selfdoc stale` gate refuses the push without them. `backlog.py check` warns about both misses, naming the docs;
   - a task whose code runs a program from or against a repository (a build tool, an SDK, a script) gets one guard test within the ceiling (`_tools/tests_ceiling.json`) for the untrusted-code risk: files the program reads on its own, toolchain or SDK redirects the repository can set, targets or scripts it runs as a side effect, PATH and current-directory program lookup, and what the environment passes to the child;
   - a task that adds a read-only command a skill or subagent runs also adds its `Bash(...)` and `PowerShell(...)` allow rules to `.claude/settings.json` in its `touches`, and a check that the command refuses a path argument outside the repository, so the rule allows nothing beyond the clone;
   - a task that changes a gap-step rule of the query log (`domain_article`, `weak_off_topic`, `held_article`) runs `python3 _tools/querylog.py gap-replay` before and after the change over the committed store's real gap findings, and names the findings whose decision flips (`kb/_self/querylog.md`, Apply);
   - a change to how agents read docs or call a tool (a route) lists every consumer of it in the plan: the skills, the `.claude/agents/` definitions, `AGENTS.md` and headless runs such as `_tools/ql_research.py` (`grep -rn` the command or doc it changes over `.claude/`, `AGENTS.md` and `_tools/`), and each consumer is in some item's `touches`;
   - `depends_on` wherever order matters;
   - a gate for each question only the operator can settle (the always-blocking list is in "Dependencies, gates and triggers"), with options and a recommendation: `python3 _tools/backlog.py gate add ID --question Q --option O --option O --recommendation R [--kind blocking|provisional] [--do OPTION=CMD|ID] [--host-check CMD]`, the recommendation one of the options; a gate whose options change a capped file (`AGENTS.md`, `README.md`) states in each option the file's size after it, measured with `wc -c` on the edited file (`gate add` refuses one without); `--do` names, for an option, the command that carries it out or the item whose work adds that command (`check` warns of each option of a blocking gate with none); `--host-check` is the command that exits 0 when the host setup an answer will name (a Windows feature, an account type, a tool) holds, which `/kb-sprint plan` runs on the host and `start` runs again; a gate whose question or options name a host setup (host, service, daemon, credential, login, installed, enabled) carries one, or the reason it cannot be checked as the gate's `host_unchecked` (written in the file, then `backlog.py fmt`), else `start` warns.
5. New stories and bugs stay `draft` and outside any sprint unless the operator says which sprint.
6. `python3 _tools/backlog.py fmt`, then `python3 _tools/backlog.py check` must print `errors=0`, and no warning about a new item's docs.
7. Show the result with `python3 _tools/backlog.py tree <epic>` and say what is still open.

## Epic ("<outcome>")
An outcome that takes several pushes. Plan it as below, with these steps first:
1. `python3 _tools/backlog.py find WORDS` and `python3 _tools/backlog.py tree --open` show whether an epic already covers the outcome. If one does, extend it and say so.
2. Interview the operator before writing anything, in one AskUserQuestion batch, a recommendation first:
   - the outcome as a fact about the repository once done;
   - what is out of scope, and what must not change;
   - which command would prove the whole epic;
   - the decisions only the operator can make.
3. `python3 _tools/backlog.py new epic --title T --goal "<outcome>"`. Add the epic's own checks, if any, with `--check` on `new` or `python3 _tools/backlog.py set EP-... --check "CMD"`.
4. Write its first stories, only the ones whose goal and checks are clear now, each with `--parent EP-...`. Everything else stays in the epic's `notes` until it is refined in a later `/kb-backlog` or `/kb-sprint plan`.
5. Put each open decision as a gate on the story it blocks (`python3 _tools/backlog.py gate add ID --question Q --option O --option O --recommendation R`).
6. `fmt`, `check`, then `python3 _tools/backlog.py tree EP-...`. Report the epic's id and title, its stories, and the gates waiting on the operator.

## Bug ("<defect>")
Rules of this step: `python3 _tools/rag.py pack --root _self --set kb-backlog:bug`.

1. Reproduce it with one command that fails now and will pass once it is fixed, running the failing behaviour: a tool call on a planted input, a command with a match, or, only when no log can show the defect, a test (`kb/_self/code.md`, Checks and their tests). A repro that only matches text in a file (a grep, a `python -c` reading source) proves the text, not the fix; `new` refuses one without `--repro-reason TEXT` saying why the behaviour cannot run (such as a defect in a doc's wording).
2. Pick a severity by the table in "Priority and severity" and a priority. An `S1` goes into the active sprint (`--sprint`), and you tell the operator at once.
3. `python3 _tools/backlog.py new bug --title T --severity S --repro "CMD" --goal G [--parent EP] [--sprint SP]`. `new` refuses a repro that passes: then the defect is not reproduced yet.
4. Add tasks only if the fix is known. Otherwise the bug stays one item, and `/kb-item` breaks it down.

## Triage
Rules of this step: `python3 _tools/rag.py pack --root _self --set kb-backlog:triage`.

List what needs deciding, intake's drafts first:
- the uncommitted drafts the SessionStart hook (`backlog.py intake --file --hook`; `red-pipeline --hook` files a red main's bug the same way) wrote: the new item files in `git status --porcelain -uall kb/_self/backlog/` (`??`) whose `links` carry `fingerprint <12 hex>` and `detector <name>` (`python3 _tools/backlog.py show ID`). Show each with its detector, kind, title and goal. A kept one is committed with the rest of the triage (item files only, `KB-Work` naming them); a dropped one is deleted, since it was never committed, (intake files it again at a later session while a detector still reports it);
- `python3 _tools/backlog.py list --status draft`;
- bugs without a sprint;
- items whose trigger may have fired (fire them with `python3 _tools/backlog.py fire ID` once the event is confirmed).

Propose priority, severity, sprint or drop for each, in one AskUserQuestion batch. Apply the answers (`python3 _tools/backlog.py set ID --priority P`, `python3 _tools/backlog.py move ID --sprint SP|none` for a sprint, since it writes the status that sprint gives (todo in an active sprint), where `set --sprint` refuses a draft item into an active sprint, `python3 _tools/backlog.py drop ID --why W`, `python3 _tools/backlog.py reopen ID --why W` to take a done item back to work; a bug's severity is set by `new`), then run `fmt` and `check`.

## Finish
Rules of this step: `python3 _tools/rag.py pack --root _self --set kb-backlog:finish`.

Commit the item files with a `KB-Work:` trailer naming the items, in the message's last paragraph with `Co-Authored-By` and the other trailers. Commit only when the user asked. Then run `python3 _tools/kbgit.py sync --push` (`/kb-git-sync` when it stops).
