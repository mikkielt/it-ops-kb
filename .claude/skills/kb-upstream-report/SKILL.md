---
description: Use when the user asks to report a clone's findings, bugs or wishes to the upstream (the public it-ops-kb copy the clone deploys from): turns the findings into items of this clone as user stories and writes them as one issue body in the upstream-report issue form's sections; posts nothing.
argument-hint: "[<findings to report> | ID...]"
disable-model-invocation: true
---

# Report a clone's findings upstream

A clone (git config `kb.upstreamRemote`, scope `kb.scope`) deploys from the public copy and only fetches from it. What the clone finds in that copy goes back as one GitHub issue, whose form is `.github/ISSUE_TEMPLATE/upstream-report.yml`: each finding is a user story with a title, a goal, a premise or repro, the local change the clone made meanwhile, and the clone's scope once. This skill writes the issue body to a file; the operator adds it to GitHub.

`${CLAUDE_PLUGIN_ROOT}` is the directory that holds the tool scripts: the plugin's, or, where this text runs from a clone's own copy and still shows the variable, that clone's top directory. The Bash tool does not set it: write the path where a command below shows it.

**Nothing here posts to GitHub.** Never run `gh issue create`, `gh api`, `kbgit.py publish` or any command that sends text to a forge; never call a docs server's `submit_feedback`. The last step names the commands for the operator to run themselves.

1. **Collect the findings.** Take them from the operator's words (and from `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py list` for items of this clone that already state one: ids given as the argument go to step 3). One finding is one story. A finding that is a defect of an upstream item is still a story of this clone: the upstream's items are read-only here (`list --all` shows them).
2. **Write each finding as an item of this clone**, so the file is built from items and nothing is retyped:
   - `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py new story --title T --goal G` (a defect with a command that fails now: `new bug --title T --severity S --repro "CMD" --goal G`; the repro must fail now and for the defect).
   - Title: the outcome, one line. Goal: what a tool, rule or doc should do, stated so that a check can tell done from not done.
   - Premise: `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py set ID --add-notes "Premise: <one command or observation that shows it now, and what it printed>"` (a bug's repro takes its place).
   - The local change: `set ID --add-notes "Local change: <what this clone changed meanwhile, or none>"`.
   - Placeholders only (`PL-LT-00123`, `corp.example.com`, `jan.kowalski`, tenant `00000000-0000-0000-0000-000000000000`): never a real host, tenant or object id, address, person or token. Put no operator decision or development-environment detail in an item meant for the upstream.
3. **Write the file.** `python3 ${CLAUDE_PLUGIN_ROOT}/_tools/backlog.py upstream-report ID... --out FILE` (a path outside the tracked files, such as under `_cache/`). It refuses an item that arrived from the upstream and a text with a leak-scan hit (it names the kind, never the value): fix the item and run it again. Read the file once: one `### Clone scope` section, then each story's `### Title`, `### Goal`, `### Premise or repro` and `### Local change made meanwhile`, a rule between stories. A section that says `none recorded` is a finding without its premise or its local change: ask the operator or fix the item (step 2), then write the file again.
4. **Hand it over.** Tell the operator the file's path and that nothing was posted. They add it themselves, in one of two ways:
   - paste the file into a new issue made from the "Upstream report" form on the upstream's issue page;
   - run `gh issue create --repo OWNER/REPO --title "Upstream report: <clone name>" --label upstream-report --body-file FILE` (OWNER/REPO is the upstream's, from `git remote get-url <kb.upstreamRemote>`).
   Report the stories by id and title (`ST-xxxxxxxx “title”`), and the file.
