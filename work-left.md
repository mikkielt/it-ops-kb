# Work left (as of 2026-09-25)

Branch `claude/relaxed-keller-e8qyl3` on GitHub, not yet merged into GitLab `main`. Done and committed: task 6 (sync fixes, the 6b replay as a test), task 7 (plugin, `kb` MCP server, runbook), the research-skill fixes, and the census tooling (`/kb-census`, `_tools/census.py`); see `git log`. Still open:

## 1. Census 2026-09-25: finish what this environment could not reach
Log: `_census/2026-09-25.csv` (`python3 _tools/census.py summary _census/2026-09-25.csv`).
- **Phase 1 (mechanical):** OK=450, CHANGED=20, GONE=1, NEWER-VERSION=12, NEEDS-READING=601.
- **Phase 2:** the 68 readable non-OK sources were read in full by one subagent per domain group. Outcomes: 42 confirmed, 10 updated, 5 superseded, 11 unconfirmed. The superseded ones:
  - S1500 -> S743;
  - S1546 -> S1862;
  - S1868 -> S-qso6o6wu (new row);
  - S1882 -> S1935;
  - S1897 -> S1898.
  New rows: S-mmshotst, S-qso6o6wu.
- **Phase 3:** 502 confirmed sources and 77 articles were dated 2026-09-25, with `confirmed 2026-09-25: <proof>` in `version_or_date` and `checked_utc` in `_fetch_state.csv`.
- **Phase 4:** an independent subagent re-read a sample of 27 sources (2 of 15 changed, 25 of 492 confirmed): 24 agreed, 3 disagreed. All 3 were old fact errors in sources the census correctly found unchanged: garak's licence, the log that events 1006/1007 go to, and an unsupported KSP+TPM row. All three are fixed in `351f00b`. The follow-up sample with another seed, which `/kb-census` calls for after a disagreement, was **not run**.

**Unconfirmed after reading (11); their dates were not moved:**
- S1508, S1509, S1525, S1597: docs.pypi.org and blog.pypi.org answer 403 here.
- S838, S1008, S1009, S1017, S1019, S2196, S2197: GitHub repository metadata, a latest-release marker or an api.github.com redirect. None is observable here, and GitHub MCP search was deliberately not used as evidence (this session's GitHub access is scoped to mikkielt/it-ops-kb).
- To decide (`_conflicts.md`):
  - what `prior-art/projects.csv` `latest_release` means: newer tags exist for Puppet 8.10.0, InSpec v7.3.1 and Teleport v18.11.1;
  - two mis-cited facts: the Ansible check-mode fact on S1009 (`prior-art/drift-detection.md`) and the modelcontextprotocol-repos fact on S1019 (`prior-art/mcp-microsoft-endpoint-mgmt.md`).

**Blocked by this environment's network policy (566); not confirmed and not dated:**
- **Hosts denied:** learn.microsoft.com (also through WebFetch and the Microsoft Learn MCP server), github.com pages, api.github.com, modelcontextprotocol.io, docs.gitlab.com, csrc.nist.gov, huggingface.co, docs.pypi.org and about 110 other hosts.
- **What is left:**
  - 399 pages on denied hosts (note `blocked`);
  - 45 github.com pages;
  - 8 Learn pages whose source repos are not public (defender-docs, powerbi-docs);
  - 114 `MicrosoftDocs/memdocs` pins. The repo is archived (last commit 2026-09-02). Each pin is re-sourced to its live Learn page: a new row with the Learn url and its `git_commit_id`, `superseded_by` on the pin, and the citations re-pointed.
- **To finish:** in an environment that allows those hosts (Network access in the environment settings), run `/kb-census 2026-09-25 --resume`. It reads the rows whose outcome is empty or `unconfirmed`; then `census.py confirm` dates them.

**Census tag: not created.** `census-2026-09-25` would state that the whole kb was confirmed current, but more than half of the sources could not be read here. Create and push it once the list above is done: `python3 _tools/kbgit.py tag-census <date>`, then `git push origin census-<date>`.

## 2. Plugin: install from the real GitLab remote
The plugin was installed and tested end to end from a local bare repo reached through the SSH url (`git@gitlab.com:mikkielt/it-ops-kb.git`, rewritten by git's `insteadOf`). `claude mcp list` showed `plugin:it-ops-kb:kb` connected, and `claude -p` answered from the kb tools with `path:line` citations and urls.

Not done here:
- an install from gitlab.com itself (no SSH key for it in this session);
- pushing to the GitLab remote (this session pushes to GitHub `mikkielt/it-ops-kb`).

### Docs the plugin was built to (read 2026-09-25 through the claude-code-docs MCP server)
- https://code.claude.com/docs/en/plugins/create-marketplace: marketplace layout, entry name = manifest name, relative sources from the marketplace root, `claude plugin validate`.
- https://code.claude.com/docs/en/plugins/marketplace-reference: `marketplace.json` fields; `"."` as a relative source is the root itself; marketplace source type `git` for `git@host:path` (used in `extraKnownMarketplaces`).
- https://code.claude.com/docs/en/plugins/manifest-reference covers `plugin.json`:
  - `skills` adds to the default scan and accepts a folder holding `SKILL.md`;
  - `agents` replaces the default `agents/` scan;
  - `mcpServers` merges with the root `.mcp.json`;
  - `${CLAUDE_PLUGIN_ROOT}`;
  - plugin `settings` honours only `agent` and `subagentStatusLine`, so a plugin cannot ship permission rules;
  - no `version` means the version tracks commits.
- https://code.claude.com/docs/en/plugins/loading: the computed version (the commit SHA of the installed directory for a relative path in a git-hosted marketplace); cached copies in `cache/<marketplace>/<plugin>/<version>/`.
- https://code.claude.com/docs/en/plugins/host-marketplace and https://code.claude.com/docs/en/plugins/install: private marketplaces over SSH (key in `ssh-agent`, host in `known_hosts`, no prompts); auto-update is off by default; `/plugin marketplace update`; `claude plugin update`.
- https://code.claude.com/docs/en/mcp (Plugin-provided MCP servers): tool names are `mcp__plugin_<plugin>_<server>__<tool>`.
- https://code.claude.com/docs/en/hooks: a PreToolUse hook's exit code 2 blocks the call; exec form with `args`.
- https://code.claude.com/docs/en/skills: the `allowed-tools` and `disallowed-tools` frontmatter.
- https://code.claude.com/docs/en/plugins/org and https://code.claude.com/docs/en/plugins/cli-reference: `extraKnownMarketplaces` + `enabledPlugins`, `--scope project`.

## 3. Known debt
- 25 lint errors are recorded in `_tools/lint_baseline.txt` (untagged facts, tags with no source id). Several articles also list header ids their body never cites (lint warnings), left alone because removing them could empty a source's `used_in`.
- `_gaps.md` still refers to the old ids QS1, QS5 and QS7, whose second copies were renamed QS1a, QS5a and QS7a.
- **Task D, not done:** the Sonnet research branches (`scratch/research-a`, `scratch/research-b`) were not on the remote, so they were not merged. If they turn up:
  1. Re-verify research-a's three unsupported facts against the pages that actually state them: the gateway 2 MB/8 MB caps (S2219), Fabric's 15-45 min latency (S2214) and the Export to Data Lake end date 2026-11-30 (S2213).
  2. Spot-check five facts per branch.
  3. Bring them in with `kbgit.py sync` and `/kb-git-sync`. The procedure is tested on synthetic copies in `_tools/test_research_merge.py`.

## 4. Token usage: make lookups deterministic
**`plan-token-optimization.md` T1-T14: done** (see `token-usage-report.md`, "Measurement in a host project").
- **Plugin split:** two plugins, `it-ops-kb` and `it-ops-kb-docs`. There is no root `.mcp.json`: a clone runs `python3 _tools/kb_mcp.py --register-local` once (`/kb-setup` and the web SessionStart hook do it).
- **Six questions, fresh Sonnet sessions:** 13 turns and 312k input in a clone, 14 turns and 306k in a host project. On 2026-09-25 it was 19 turns and 691k.
- **Subagent startup:** `kb-lookup` starts at 3.9k tokens.
- **Review:** `/kb-review-workspace` found all five planted problems in the test host, each with the host line and the kb citation.
- **Fixed on the way:** the kb server lacked `resultType` (MCP 2026-07-28), so no kb tool loaded from the plugin.
- **Not done:** an install from gitlab.com itself (see section 2) and a push to GitLab `main`.
- **Retrieval audit done** (`token-usage-report.md`, "Retrieval quality audit"): untagged content and code blocks are searchable now, there is no false `none` on the blind questions, and line recall is 94%.
- **doc2query pilot done** (`token-usage-report.md`, "doc2query pilot"): pilot line recall 90% -> 97.5%, control unchanged.
  - **Next:** confirm on a fresh blind set with new arms, then expand the whole kb (protocol: `_tools/doc2query/README.md`).

Earlier; see `token-usage-report.md`, "Re-measurement after the changes":
- The six measured questions in fresh sessions: -74% input tokens, -72% output tokens, 351 -> 118 s.
- A `kb:` prompt the kb covers costs no model tokens.

Still open:
- 233 ledger entries have no explicit topic link and need a `(topic: <domain>/<slug>)` marker. 125 of them are not even linked through their sources. List them with `python3 _tools/rag.py audit --unlinked [DOMAIN]`.
- 13 DOC/COMMUNITY tags without a source id (kb-verify lint, in `_tools/lint_baseline.txt`).
- Add failed real-world lookups to `_tools/lookup_eval.csv`.
