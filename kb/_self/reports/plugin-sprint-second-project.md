# The plugin's sprint skill on a second project

One item of a project other than the kb was run end to end on the plugin's `/it-ops-kb:sprint`, on 2026-10-10, as the fitness test of EP-4fawjprq (ST-tyzcqzfo, TK-ew6dsm2l). The findings about the tooling are kb items whose titles end in `(second-project run)`; each item's notes quote the output line from the run that shows it.

## The project

- A throwaway git project in the kb orchestrator's scratch directory: a one-function Python library (`src/greet.py`), its `unittest` test, a `README.md`, and a local bare repository as its `origin`. No forge, no merge requests, no CI.
- The plugin was loaded per session with `claude --plugin-dir <kb clone>`, never installed at user or project scope.
- The project's `backlog.json`, as the run ended:
  - `always_in_scope`: `["_backlog/**"]`; `item_dir` left at its default, `_backlog`;
  - `review_checks`: the project's `unittest` run; `research_checks`, `land_stale`, `land_eval`, `land_lint`: `[]`;
  - `docs_map`, `kb_root`: `""`;
  - `lane_module`: `""` and `land_push`: `["git", "push", "origin", "HEAD:main"]`, both added once BG-rqxspwtb had landed;
  - `forge` left at its default: an empty value is refused.
- The project's `.claude/settings.json`: `defaultMode` `acceptEdits`, allow rules for `python3` and the git commands the skill runs, a deny of `git push`, and, from the second pass, `permissions.additionalDirectories` naming the plugin root.

## Install steps that turned out to be needed

1. Trust the project's workspace once (an interactive session's trust dialog): a headless session in an untrusted workspace ignores the project's allow rules, and every `backlog.py` call was held for approval. The run set the trust of the scratch path in the user's Claude configuration and removed it afterwards.
2. Name the plugin root in `permissions.additionalDirectories` (and `--add-dir` for the orchestrator's session): a headless worker could not read the plugin's role file without it.
3. List `__pycache__/` in `.gitignore`: a premise run's bytecode made `land` stop at its clean-tree step.
4. Set `land_push` and an empty `lane_module` (after BG-rqxspwtb): before it, `land` stopped at `kbgit.py sync --push`, and `kblane` classed `src/` as code.

## The run

The project's orchestrator was a headless Sonnet session that followed the plugin's sprint skill under a written operator policy (each gate answered with its recommendation); it was resumed three times as the steps above were put in place.

| Step | Outcome |
|---|---|
| plan | one story, "greet takes an optional greeting word", in sprint SP-fispeumc with its goal research and review stories |
| start | the start gate approved by the delegated operator, drafts made `todo` |
| claim | the research story and the story claimed; the claims reached `origin` with the first landing's push |
| dispatch | the first worker could not read the plugin's role file and returned no commit; after step 2 of the install list a re-dispatch in the same worktree committed the change and both checks passed |
| land | stopped at `kbgit.py sync --push` until BG-rqxspwtb; then `done --commit` and `git push origin HEAD:main` in one pass |
| review | a headless reviewer on the review story found no gap; `done` re-ran the sprint's checks and was pushed |
| close | `close --summary` named the story for the goal clause; `close --commit` deleted the items; the close commit stayed local, since no tool push step takes a closed sprint's commit |

## Findings and their items

- In this sprint: BG-rqxspwtb (land's push and lane for a host project), done before the run's landing.
- Filed as drafts under EP-4fawjprq:
  - bugs: BG-urlbsgsr (commands read the plugin's own `backlog.json` without `--root`), BG-cmvwrpbr (defaults are the kb's values), BG-5gqy7hln (selfcheck's kb-only checks), BG-duzrzr2d (dispatch's `--add-dir` omits the plugin root), BG-c7pjl3mi (no way to name no forge);
  - stories: ST-bl7kxfh6 (research story check), ST-2yxoml3e (plan and start commit), ST-uvtnm3kj (`held` before the first push), ST-m7uk3zpu (docs check with no `docs_map`), ST-tuc2zmio (resuming a worker), ST-siqol7pe (Agent fallback under `.claude/`), ST-ba6ueynq (install steps in `kb/_self/plugin.md`), ST-iviphkbm (worktree kept until the push), ST-hlpvqc2h (Session trailer), ST-hs26y4qr (claim and close pushes), ST-vybjfqvj (local `main` after the push), ST-glfq7qjt (`cost` in a host), ST-lptsjyip (a reviewer brief).
- No change: the precheck warning that the story's plain test run passed before the work (the planning rule it states held), and the skill's "never answer the start gate yourself" against the run's written policy (an operator's delegation, not a tool defect).
