# Work left (as of 2026-09-25)

Branch `chore/kb-tools-hardening`, not pushed. Git-regime tasks 1-5 are done and committed (369beef, 82aeefb, e5dadde, ae3c67f, 47c5568). Task 6 was stopped partway through. Task 7 was never started.

## Task 6: `/kb-git-sync` skill, tested on a real parallel merge (partly done)

### Already committed by agent 6
- `0c32883` fix(kb): `kbgit.py fix` handles pre-regime branches and keeps ids that are already pushed.
- `5519660` feat(kb): `.claude/skills/kb-git-sync/SKILL.md`.
- `0c0978a` fix(kb): `kbgit.py fix` renames an answer id only in its own side's lines.

### Uncommitted in the working tree
The edits were in progress when it stopped. Review them before keeping them.
- `.claude/skills/kb-git-sync/SKILL.md`
- `_tools/kbgit.py`
- `_tools/test_sync.py`

### Two issues it was investigating when stopped
1. One test fails when the full `tests.py` suite runs in a fresh clone of the scratch remote (`sync-test/verify`).
2. B's commit trailers also list A's answer id. The trailer diff after a rebase or fix is taken against the wrong base.

### What task 6 had to do

**6a. Write the skill.**
It is user-invoked, the intelligent layer for when `kbgit.py sync` exits with code 3:
- Start with `sync --dry-run`, then `sync`, and branch on the exit code.
- Exit 3, articles: resolve by meaning, not by taking one side.
  - Different facts added on both sides: keep both.
  - The same fact changed on both sides: newer confirmed evidence wins, and DOC beats COMMUNITY. Otherwise record both sides in `_conflicts.md` and tell the user.
  - Deleted on one side, edited on the other: ask the user.
  - Front matter: `sources` = the ids actually cited after resolving; `retrieved_utc` = the later of the two; `status` = partial if any UNK remains; `files` = the union of both.
- Exit 3, tools and docs: merge conservatively, or ask. Then run the printed `fix` command, `git add`, `git rebase --continue`, repeat until the rebase ends, and rerun `sync`.
- Exit 1: fix the cause of the failed check. Don't silence it through the lint baseline or the allowlist.
- Exit 2: explain and stop.
- Push only if the user asked. Never use `--force` or `--no-verify`.
- End with a report.
- Mention the skill in AGENTS.md and README.

**6b. Test it on a real case, in scratch only.**
- The inputs are two Sonnet research branches, both created from 6bc0981 before the redesign:
  - `scratchpad/research-runs/kb-a`, branch `research-a` (Dataverse topic);
  - `scratchpad/research-runs/kb-b`, branch `research-b` (Keeper facts);
  - both used the same legacy ids (S2205 upward) and the same answer id `QK1`.
- Push the real branch HEAD as `main` into the bare repo `scratchpad/sync-test/remote.git`.
- Person A syncs `research-a`, then person B syncs `research-b`.
- The collisions must then be resolved: the colliding ids get hash ids with their citations rewritten, and the answers get distinct `QK-<slug>` ids.
- Verify in a fresh clone:
  - `check.py`, `build_index.py --check`, `kbgit.py fix --check`, `tests.py` and `check-trailers` all pass;
  - both research results are present;
  - there are no duplicate ids;
  - `kbgit.py log <new hash id>` finds the commit.
- The scratch state so far is in `scratchpad/sync-test/`: remote.git and remote2.git, the clones a, b, b2 and c, probe, probe2 and probe3 (the last two are stuck with conflicts), and verify.

### To finish
1. Review the three uncommitted files, then fix issues 1 and 2.
2. Rerun 6b from a clean scratch dir.
3. Run the gate: `kbgit.py fix --check`, `build_index.py --check`, `check.py`, `tests.py`, `stress_test.py`, `fetch.py --offline`, `kbgit.py check-trailers 47c5568..HEAD`.
4. Commit.

## Task 7: plugin and runbook for other projects (not started)
- The goal: another project "subscribes" to this KB.
- It must use the GitLab SSH remote `git@gitlab.com:mikkielt/it-ops-kb.git`. Consumers need an SSH key with access to the project.
- Package this repo as a Claude Code plugin marketplace plus plugin, installed with `/plugin marketplace add git@gitlab.com:mikkielt/it-ops-kb.git` then `/plugin install it-ops-kb@...`.
- Before building, confirm the current `.claude-plugin/marketplace.json` and `plugin.json` formats, the plugin-root variable and the update behaviour against the docs.
- **What the plugin contains:**
  - **A small stdlib stdio MCP server `kb`**, wrapping `rag.py`. Its tools:
    - `kb_search`: returns source urls plus the weak-match and not-found notes;
    - `kb_show`;
    - `kb_source`;
    - `kb_status`: the KB commit, its date and the latest `census-*` tag, so consumers can see how current it is.
  - **The `/kb-lookup` skill**, switched to call these tools; still read-only and auto-invocable.
  - **The three docs MCP servers**, with `submit_feedback` still denied.
  - **No writing skills.** Research, refresh, add-topic and git-sync stay in a clone of this repo, because the plugin copy is replaced on every update.
- **README additions:**
  - a runbook "Use from another project": install, check `kb_status`, ask a question, update with `/plugin marketplace update`;
  - a paste-ready operator prompt for people who don't use plugins: clone to a fixed path, add it as an additional directory, add a CLAUDE.md note on how to query it with `rag.py ... -u`, and add the three docs servers;
  - a contributor section: clone, `/kb-setup`, `kbgit.py install-hooks`, work, `kbgit.py sync --push`, and `/kb-git-sync` on exit 3.
- Test it end to end in a scratch project: install from a local marketplace path, ask one question, and check that the answer is cited.

## Other pending work (decided, not started)
- **Research-skill fixes**, from the Sonnet research review:
  - read the full page before citing (MCP fetch for Learn; for other sites, a short verbatim quote of the key sentence);
  - rules for extending an existing topic versus creating a new one, and where a topic with no home goes;
  - `/kb-verify` should compare against the branch the work started from, not `main`.
- **Sonnet research A (Dataverse):** three facts are not found on their cited pages: the gateway 2 MB/8 MB caps (S2219), Fabric's 15-45 minute latency (S2214) and the 2026-11-30 Data Lake export end (S2213). Re-source or drop them before merging.
- **Census (plan agreed; phases 0-4 in the conversation):**
  - "refreshed" means "confirmed up to date";
  - a pinned source that changed upstream gets a new row, with `superseded_by` on the old one;
  - memdocs pins are re-sourced to live Learn pages, recording `git_commit_id`;
  - phase 1 is mechanical: compare Learn `updated_at`/`git_commit_id` metadata, run `git log <pin>..HEAD -- <path>` on blobless clones of the 27 repos, check for newer releases, check URL liveness;
  - phase 2: one subagent per domain group, reviewing only the sources that aren't OK;
  - phase 3: set the dates by script;
  - phase 4: an independent sample check, then `kbgit.py tag-census 2026-09-25`.
- **Known debt:**
  - 25 lint errors are in `_tools/lint_baseline.txt` (untagged facts, tags with no source id);
  - `_gaps.md` still refers to the old ids QS1/QS5/QS7, whose second copies were renamed QS1a/QS5a/QS7a.
