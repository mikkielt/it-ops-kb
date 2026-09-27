---
name: kb-self
description: Use after changing it-ops-kb's tools, skills, hooks, plugin, config or rules, or when the user asks to update the kb's own docs (_self/, AGENTS.md, README.md) or record a measurement: finds stale docs with selfdoc.py and brings them in line.
argument-hint: "[--since REV | <doc path, e.g. _self/tools.md> | all | --report \"<title>\"] [--check]"
---

# Update the kb's own docs

Read `_self/README.md` first (what each doc is for and the rules for keeping them current), then `_self/maintaining.md` (conduct and the gate). The docs describe the code as it is now; the code, the tools' docstrings and the config files are the source of truth.

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): the shared permission rules match single commands, so a chained command asks for approval or is refused in a headless run.

## Arguments

| argument | scope |
|---|---|
| none, or `--since REV` | the docs `python3 _tools/selfdoc.py stale --since REV` lists: what this work changed. Default REV: `@{upstream}` when the branch tracks one, else `origin/main`. Say which. |
| a doc path (`_self/tools.md`, `AGENTS.md`, ...) | that doc only, checked against every file `_self/map.csv` gives it |
| `all` | every doc in `_self/map.csv`: `python3 _tools/selfdoc.py stale` (each doc against its own last commit), then a read-through of each doc against its files, stale or not |
| `--report "<title>"` | a measurement was just made (e.g. `_tools/agent_bench.py`, a timing, an eval): add it as a new dated section to `_self/reports/token-usage.md` (or a new file in `_self/reports/`), then update the conclusions and numbers in `_self/design.md` (and the README table if a headline number moved), each citing the new section |
| `--check` (with any of the above) | report only: what is stale, what would change and why; write nothing |

## 1. Find what is stale

1. `python3 _tools/selfdoc.py check` must say `problems=0`. Fix the map first:
   - a new tool, skill, hook or top-level `_self/` doc needs rows in `_self/map.csv` (`doc,pattern`, CSV writer, one row per line; pattern `-` for a doc that describes no file, such as `work-left.md`);
   - a pattern that matches no file names a renamed or removed file: point it at the new path or drop the row.
2. `python3 _tools/selfdoc.py stale --since <REV>` (or without `--since` for `all`): one `STALE <doc> (since <ref>): <files>` line per doc.
3. For each listed file, see what changed: `git diff <ref> -- <file>`. For a tool, also read its docstring and flags (`python3 _tools/<tool> --help`). For a skill or hook, read the file. Note only changes a reader of the doc would act on: a new or renamed command, flag, exit code, rule, file, skill or default; a changed behaviour or number.
4. `python3 _tools/selfdoc.py map <path>` answers the reverse question: which docs describe a file you are about to change.

## 2. Update each doc

Change only what the code change made wrong or missing; keep each doc's scope.

| doc | holds | never |
|---|---|---|
| `AGENTS.md` | the lookup procedure, tag meanings, docs servers table, the skills list, conduct; at most 4096 bytes (tested) | maintainer detail (it loads into every session and subagent) |
| `README.md` | the overview for people: what, why, how it works, when it pays off, where things are; at most 8 KB (tested) | commands, flags, rules |
| `_self/tools.md` | one table row per command (flags, what it does, exit codes, from the docstring and argparse); "How the lookup tools decide" when pack, search, the hook or `kb_ask.py` routing changed | the whole docstring |
| `_self/content-rules.md` | what `check.py`, `kbid.py`, `kbfacts.py`, `build_index.py` and the kb-verify lint enforce | tool usage |
| `_self/git.md` | `kbgit.py` commands, sync and fix behaviour, the hooks, `.gitattributes`, CI | |
| `_self/plugin.md` | what each plugin ships, the plugin rules, the install and team-kb runbook | |
| `_self/maintaining.md` | setup, the table of skills that change the kb (a new or renamed skill), conduct and the gate | |
| `_self/design.md` | the current conclusions and each number's report section | a number with no dated source |
| `_self/README.md` | the file table and the keeping-current rules | |
| `_self/work-left.md` | the open work: mark items done with the date and commit, add new ones | |
| `_self/coverage.md` | nothing by hand: `python3 _tools/build_index.py` | edits |
| `_self/reports/*` | dated records: add a section or file | rewriting an old measurement |

Rules for every doc:
- One fact in one place; elsewhere point to it (e.g. "`_self/git.md`").
- Describe what the code does now, checked by running it (`--help`, a sample call), not what a plan intended.
- Write flags exactly as the tool spells them next to the tool's path: the cohesion test fails on a flag the tool lacks. Every backtick path must exist.
- A skill added or renamed: the skill table in `_self/maintaining.md`, the skills line in `AGENTS.md` (the test requires every skill there), and `_self/plugin.md` if it ships in the plugin.

## 3. Verify

1. `python3 _tools/selfdoc.py stale --since <REV>`: `stale=0` (an edited doc counts as updated).
2. `python3 _tools/selfdoc.py check`: `problems=0`.
3. `python3 _tools/tests.py -k "Cohesion or SelfDocs"`: flags, backtick paths, links, size caps, the map, skills listed.
4. `python3 _tools/build_index.py --check` when `coverage.md` or an article's front matter was touched.
5. For a doc change that came with a code change, the full gate in `_self/maintaining.md` before committing.

## 4. Commit and report

- The docs go in the same commit as the code change they describe (`_self/git.md`); a docs-only catch-up is `docs(kb): bring _self in line with <what changed>`. Commit only when asked; push with `python3 _tools/kbgit.py sync --push`.
- Report: each doc updated with one line on what changed and which file made it stale; docs still stale and why (e.g. a behaviour you could not confirm by running the tool).
