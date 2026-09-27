# Work left (as of 2026-09-27)

## W. Next up: CODE and SNIPPET migration (approved 2026-09-27; for a local session)

Start here once `main` on GitHub has the commit "feat(kb): enforce the gate on push; add CODE and SNIPPET" (check with `git log origin/main --oneline -5` after `git pull --ff-only`). Done in that commit: the stricter push gate, the pre-push hook, `.github/workflows/kb.yml`, the `CODE` kind and `SNIPPET:` units in the grammar, lint and tests, and every text that lists the tags. Rules: `_self/content-rules.md` ("CODE" and "SNIPPET" sections). What is left is converting existing content, in this order. Decided: all of it now, not gradually during refreshes.

**W0. Check the setup (a few minutes).**
- `python3 _tools/kbgit.py install-hooks` (adds the new `pre-push` hook; `git config core.hooksPath` must print `.githooks`), then `python3 _tools/tests.py` and `python3 _tools/stress_test.py`: green.
- The first GitHub Actions run of `kb.yml` on that commit: green (GitHub, Actions tab). If a step fails only on GitHub (container, permissions, the `before` sha), fix the workflow, not the checks.
- Decide separately: GitHub branch protection for `main` (the kb does not cover GitHub's required status checks; read the live docs first). The workflow stays a detective control either way.

**W1. CODE migration (B3): about 129 facts.**
- Candidates: `python3 .claude/skills/kb-verify/lint.py --candidates` (`CODE-CANDIDATE path:line ids text`): DOC facts whose every cited source is a source-code or config file. Also check the about 50 facts that cite a code file next to a documentation page: `rag.py src <id> --cited` for each code-file source.
- Group by domain; one reader subagent per group (`/kb-refresh` procedure, Sonnet, several groups in parallel). For each fact: open the cited file at its pinned url and find the line. Then:
  - the documentation also states it: keep `DOC` and add the documentation source (or re-point to it);
  - only the code states it: `[CODE <id>: <path>#<symbol or L10-L20>]`;
  - the source url is not pinned (a branch such as `main`): add a new row at a tag or commit (`kbid.py url`), set `superseded_by` on the old row, re-point the fact. The lint rejects an unpinned CODE source.
- A fact whose text changes needs `python3 _tools/doc2query.py stale`, then `prune`. Then `build_index.py`, `check.py`, `lint.py` (errors=0), `rag.py eval`, and one commit per domain group (`/kb-verify`, `kbgit.py sync --push`).
- Done when `lint.py --candidates` lists no CODE-CANDIDATE that is not a deliberate DOC (note such cases in the commit body).

**W2. SNIPPET migration (C2): 191 code blocks in 99 articles (47 PowerShell, 30 JSON, 21 HTTP).**
- Candidates: `SNIPPET-CANDIDATE path:line lang` from the same command.
- For each block decide: (a) a how-to someone would run or copy: add the `- SNIPPET: <what>; context: <versions, prerequisites>; checked: no|syntax|run [DOC|CODE|DER ids: ...]` bullet directly above it, with evidence for the cmdlet, parameters or fields it uses (the reader checks each parameter against its source; a wrong or unbacked one is fixed or the block becomes an illustration); (b) an illustration (a payload shape, a config excerpt, output): leave it without a bullet, in Reference or Examples.
- `checked: syntax` only after parsing (the lint re-parses json, toml and python; there is no `pwsh` in the cloud container, so PowerShell is `no` unless someone ran it, then `run` with where in the note).
- Placeholders only (`PL-LT-00123`, `corp.example.com`, `jan.kowalski`; the leak tests run on staged files: `git add` first).
- One reader per domain group, one commit per group, as in W1. Done when every remaining SNIPPET-CANDIDATE is a deliberate illustration.

**W3. Measure (D).**
- Add 5-10 `lookup_eval.csv` rows for how-to questions a snippet answers (`kbid.py eval`) and 3-5 for CODE facts ("what is ruff's default rule set"); `rag.py eval` passes.
- An `agent_bench.py` run (a few how-to scenarios, Haiku and Sonnet) before W2 and after it; record it with `/kb-self --report "CODE and SNIPPET migration"`, which updates `_self/design.md`.
- Then trim this section to one "done" line.

**Other open items from 2026-09-27 (independent of W):**
- `pyproject.toml` says `requires-python = ">=3.9"`, but Python 3.9 reached end of life on 2025-10-31 (`python/version-lifecycle.md`). Decide whether to raise the floor; the tools' stdlib-only rule is unaffected either way.

**2026-09-27: the kb's own docs moved to `_self/`.** Agents read `_self/` (see `_self/README.md`); people read the short root `README.md`; `AGENTS.md` stays the lookup rules. `MAINTAINING.md` became `_self/maintaining.md` plus `_self/content-rules.md`, `_self/tools.md`, `_self/git.md` and `_self/plugin.md`; the coverage table moved from the README to `_self/coverage.md`; the plans and the token report are dated records in `_self/reports/`; `_self/design.md` holds the current conclusions on when the kb is token-efficient. `_self/` is out of `pack` and the default search (`rag.py search --index` finds it). `_tools/selfdoc.py` lists docs behind the files they describe (`_self/map.csv`); `/kb-self` updates them, and `/kb-verify` reports them. Open:
- The remote branch `claude/relaxed-keller-e8qyl3` on GitHub is merged but not deleted (this session's git proxy refused the delete): `git push origin --delete claude/relaxed-keller-e8qyl3` from a clone with push rights.
- `_self/reports/` still carries the old section names and some superseded numbers by design (dated records); `_self/design.md` is where current numbers go (`/kb-self --report`).

**2026-09-26, later session (branch `claude/relaxed-keller-e8qyl3`):** GitHub had no open issues or merge requests; this list was the work queue. Done there: P.2 (`/kb-gap`), P.5 (consumer runbook), P.6 (`KB_ROOT`), P.7 / B (the `check:` line for a possible false `good`; the `kb:` hook forwards such packs), the QS ids in `_gaps.md`, five fresh negative controls, and topic markers on 217 of the 233 unlinked ledger entries. Still open: P.1, P.3 (optional scheduled agent), P.4, sections 1-3 and the rest of 4 below.

`main` on GitHub (remote `claude`) now holds everything below plus the 2026-09-26 expansion (section 0); the session branch `claude/relaxed-keller-e8qyl3` was merged and deleted. GitLab `origin/main` has not received these commits. Done and committed: task 6 (sync fixes, the 6b replay as a test), task 7 (plugin, `kb` MCP server, runbook), the research-skill fixes, and the census tooling (`/kb-census`, `_tools/census.py`); see `git log`. Still open:

## P. Plugin for other codebases: distribution and updates (planned 2026-09-26)
Goal: another team installs `it-ops-kb` into their own repository, reads current facts, and can report what the kb
lacks; only maintainers write. Do in this order:
1. **Done 2026-09-26: GitLab `origin/main` pushed level with GitHub (96 commits, `kbgit.py sync --push --remote origin`); GitLab stays the install url.** Keep both in step with `sync --push` then `sync --push --remote claude`. Was: **One canonical remote.** GitLab `origin/main` is 89 commits behind GitHub `claude/main` (2026-09-26), and the
   README install steps and `extraKnownMarketplaces` example point at GitLab, so an install today gets a stale kb.
   Decide: push GitLab (`python3 _tools/kbgit.py sync --push`, remote `origin`) and keep both in step, or move the
   README, the marketplace example and `plugin.json` `homepage`/`repository` to GitHub.
2. **Done 2026-09-26.** `/it-ops-kb:kb-gap` (`.claude/skills/kb-gap/`, in `plugin.json`, README, plugin tests). Was: **Gap reports from consumers.** A read-only skill `/it-ops-kb:kb-gap` (plugin-shipped, no Write/Bash): it runs
   `kb_pack`, then drafts an issue text for the user to paste (question, verdict, the nearest articles with
   `path:line`, what was missing). Nothing is written or sent by the skill. Add it to `plugin.json` `skills`, the
   README runbook and the plugin tests (read-only tools only).
3. **Triage loop: written down in README "Contribute back" (2026-09-26); the optional scheduled agent is not set up.** Maintainers turn reports into `_gaps.md` entries and `lookup_eval.csv` rows, then
   `/kb-research` or `/kb-add-topic` in a clone, then `kbgit.py sync --push`. Optional later: a scheduled cloud agent
   (`/schedule`) that runs `/kb-research` on open reports and pushes verified topics.
4. **Done 2026-09-26: the census tags are the stable channel** (README "Pin a confirmed copy"; release-channel facts in `claude/plugins.md`). No `version` field; teams pin `#census-YYYY-MM-DD` or `"ref"` in `extraKnownMarketplaces`. Was: **Release channel.** Today every commit on `main` is a plugin version (no `version` field). Add a stable channel
   for cautious teams: tag releases (for example `kb-YYYY.MM.DD`, or with each census tag) and document pinning a
   marketplace to a tag; or add `version` to `plugin.json` and bump it on purpose. Decide which.
5. **Done 2026-09-26** (README "What it costs and what to watch"; cold index build measured 3-5 s, not 1.4 s). **Consumer runbook additions (README, "Use from another project").**
   - Start with "call kb_status": commit, date, latest census (none completed yet: section 1).
   - Team setup through the project's `.claude/settings.json` (`extraKnownMarketplaces` + `enabledPlugins`); add
     `it-ops-kb-docs` only for docs servers the team does not already have.
   - Cost: about 312 always-on tokens per session (`claude plugin details it-ops-kb`), about 10 MB clone, Python 3.9+
     stdlib, index build about 1.4 s after each update.
   - Known limit: a `good` pack can be about something related (section B, false `good`); check that the cited fact
     answers the question.
   - `kb_ask.py` stays a clone/CI tool (needs the `claude` CLI); in a consumer session the path is `kb_pack` or
     `/it-ops-kb:kb-lookup`.
6. **Done 2026-09-26:** `KB_ROOT` in `kbcommon` (read tools and checks; not git/census/fetch), per-root index names in a shared `CLAUDE_PLUGIN_DATA`, labelled server texts, `test_kb_root.py`, README "A team's own facts". A kb of one or two articles cannot reach `good` (key words need df under 20%). **Organisation-specific knowledge stays out of this kb** (placeholders-only rule). For a team's own facts, design a
   second private kb with the same layout: make the tools take the kb root from an environment variable (for example
   `KB_ROOT`, default the repository) so `kb_mcp.py` can serve a second root as its own server; check that ids,
   index cache paths (`_cache/`, `CLAUDE_PLUGIN_DATA`) and `kb_status` stay per root.
7. **Done 2026-09-26** (see B). **Fix the false `good` for plugin users first** (section B, open item): consumers see `kb_pack` and the `kb:` hook,
   not `kb_ask.py`.

## B. Agent benchmark and routing (2026-09-26)
Done: 76 headless runs across 7 scenarios and 6 configs (`_self/reports/token-usage.md`, "Agent benchmark and routing");
`_tools/kb_ask.py` routes by the pack verdict (good: Haiku, weak/none: Sonnet), request words are stop words,
3+ part packs share the budget, two new articles (`ad/krbtgt-password-reset`, `gpo/admx-central-store`).
Status:
- Done 2026-09-26, partly: when a name the question uses (capital or digit, 3+ letters) is nowhere in the lead article (its lines, title or `applies_to`), the pack prints a `check:` line under the verdict; the verdict is unchanged, because each verdict rule tried (named words in the best article; tie-breaks by named words) demoted true `good` eval rows (NTLMv1, sp_getapplock, Kerberos). The `kb:` hook forwards such a pack to the model; AGENTS.md, `/kb-lookup`, the server instructions say how to read it. On the eval set the line shows once in 88 (Python in the Kerberos article). Done 2026-09-26 (later): a false `good` with no product named gets a second `check:` line when no tagged fact among the top hits holds half of 4+ key words ("migrate mailboxes between tenants", "retention for deleted chat messages"); none of the 79 eval `good` rows gets it. It caught 2 of about 10 hand-made common-word false goods (password reset link, email attachment size, page file size, remote desktop gateway ports still pass): still open. Still open: off-domain questions often come out `weak` rather than `none` (Horizon, SAP GUI, ServiceNow), though the `check:` line fires on them. Was: false `good` verdicts reach MCP (`kb_pack`) and `kb:` hook users unchecked. Only `kb_ask.py` catches them (its Haiku reader answers `INSUFFICIENT` and escalates; tested on the Purview DLP case). The verdict counts key words anywhere in the best article, not meaning, and a lexical phrase rule failed (report). Options: a note in the pack header when the best article matches its key words only across separate lines; the `kb:` hook forwarding a `good` pack to the model (like `kb+:`) instead of answering alone; or `lookup_eval.csv` rows for known false goods first.
- Done 2026-09-26 (second pass): count/cite questions by the tools, part splitting, tool-less Haiku reader with `INSUFFICIENT` escalation, lean `claude -p`, Sonnet at low effort. The plugin has no `kb_ask` path (it needs the `claude` CLI: a clone/shell tool). The kb does not call the Anthropic API (decided 2026-09-26).
- Closed 2026-09-26: the 4 `UNK` items of the two new articles (both `complete` now).

## T. `_tools` efficiency plan (`_self/reports/plan-tooling-efficiency.md`)
Done 2026-09-26: persisted pack index (cold `pack` and the `kb:` hook about 0.06 s, `eval` 0.7 s), one engine
(`search` on the same index, 0.05 s), shared helpers, batched trailer audit, legacy merge paths retired, pytest suite
run by uv in parallel (`tests.py` 16 s). Nothing open; the census `http_status` GET stays by decision.

## 0. Expansion 2026-09-26: 69 new articles
One manager session mapped gaps with `rag.py pack` (many answers were a false `good` from an unrelated article), then ran one Sonnet writer per topic following `/kb-add-topic` / `/kb-research`, and pushed each verified topic to GitHub `main`.
- **Added:** 69 articles, 43 data CSVs, 785 source rows (almost all Microsoft Learn, Claude Code, MCP spec, vendor docs), `lookup_eval.csv` 37 -> 85 rows, new signals/aliases.
- **Domains:** Windows (LAPS, BitLocker, App Control, Windows Update/Autopatch/hotpatch, Delivery Optimization, WinGet, WEF/Sysmon, kiosk, PowerShell 7, remoting/JEA, Windows 365, Arc, Update Manager); Intune (Win32 apps, compliance, configuration policies, filters/RBAC, EPM, remote actions, Remote Help, platform scripts, reports export, certificates/Cloud PKI, network profiles, MAM, macOS, iOS/Android, Linux, Endpoint analytics); Autopilot v2; MECM software updates and OSD; Defender hunting, ASR/AV, response API, onboarding; Entra CA for devices, Connect/Cloud Sync, PIM, Agent ID; WHfB; audit log APIs; Graph batching and PowerShell SDK; Microsoft365DSC; Claude Code skills/subagents, plugins, settings, Agent SDK, CI/headless, Messages API, enterprise admin; MCP resources/prompts, streamable HTTP, registry/extensions; Microsoft Agent Framework, Foundry Agent Service, Azure OpenAI deployments, Security Copilot, Prompt Shields, M365 Copilot extensibility, Windows agentic platform, coding-agent MCP configs, GitHub Copilot admin, LangGraph, hybrid retrieval, Azure AI evaluation (in `agents/agent-evaluation.md`); AMA/DCRs, Sentinel; vulnerability prioritization.
- **Open:**
  - After two fix passes: 20 of the new articles are still `partial`, with 28 `[UNK]` facts and 6 unconfirmed CSV values (mostly vendor pricing/licence pages, JS-rendered NVD/EPSS pages, undocumented log paths); each is logged in `_gaps.md`. List: `python3 _tools/rag.py audit --status partial`.
  - 9 new `_conflicts.md` entries, all rechecked 2026-09-26; 8 still real disagreements (e.g. Win32 supersedence 10 vs 11 nodes, Copilot Studio Agent ID cutover date, Recall default, BOD 22-01 superseded by BOD 26-04, PowerShell lifecycle dates).
  - Done 2026-09-26: five fresh negative controls (Meraki, Kafka, Proxmox/Ceph, FortiGate, YubiKey Bio in Okta Verify), all `none`; eval 93 of 93.
  - `tests.py` leak/cohesion checks scan tracked files only: stage new articles (`git add`) before running them, or they pass unchecked. Public ids found this round are in `_tools/tests_allowlist.txt` with reasons.
  - Not yet pushed to GitLab `origin/main` (`python3 _tools/kbgit.py sync --push` when GitLab should get it).

## 1a. Census 2026-09-26 (supersedes the 2026-09-25 remainder below)
Log: `_census/2026-09-26.csv`. Network allowed learn.microsoft.com, github.com and api.github.com this time.
- **Phase 1:** OK=1438 (Learn pages without a public repo are now dated by their `updated_at` meta, `8c07300`), CHANGED=42, GONE=14, NEWER-VERSION=13, NEEDS-READING=400.
- **memdocs:** 102 of 114 archived pins re-sourced mechanically to their live Learn pages (content provably identical); the other 12 read in phase 2.
- **Phase 2:** nine readers plus one retry reader; outcomes 254 confirmed, 68 updated, 136 superseded, 11 unconfirmed. Readers' edits to other groups' files applied (`ece4bf7`).
- **Phase 3:** 1760 sources and 181 articles dated 2026-09-26 (`fef64c9`).
- **Phase 4:** two samples of about 100 sources each, each read by two fresh checkers: 80/105 and 73/100 agreed, 0 unreadable. Every disagreement was a fact its cited source never stated (a mis-citation, an added detail or a merged quote), not a source change; all 52 were fixed (`bd5dc70` and the next commit), with the same-claim lines in each article checked too.
- **Done 2026-09-27: citation-support audit of the whole kb.** 31 readers re-read every cited source not already read by the census against every line citing it: 1,901 source/file pairs, 1,167 lines fixed (re-cited, reworded or split into UNK), 192 new rows, 52 answers aligned (`047a8c2`, `b4762cf`, `231da44`). S1425 was read from its Internet Archive capture of 2026-08-27 (cyber.gov.au times out here); S2175 (paywalled, cited by no fact) left the front matter.
- **Done 2026-09-27:** the four memdocs excerpt CSVs in `mecm/` are unpinned and audited as data files (252 rows, 223 fixed).
- **Done 2026-09-27: census tag `census-2026-09-26`** created under the updated `/kb-census` rule. The only census rows left unconfirmed, S1929 (x.com) and S1933 (Medium), are cited by no fact; S1409, S1411, S1560, S1561 and S2161 are superseded.
- **check.py** now reads tags that wrap after DOC/DER/COMMUNITY (`1761643`) and the source columns of data CSVs (`d47352a`).
- **Network note:** techcommunity.microsoft.com is NXDOMAIN on this machine's resolver; `dig @1.1.1.1` + `curl --resolve` reads it.
- **Lesson:** a WebFetch summary invented BOD 26-04 Table 1 rows (`cd847fa`); the census reader caught it. Read numbers from the page text or the image.

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

Done 2026-09-26: `claude plugin marketplace add git@gitlab.com:mikkielt/it-ops-kb.git` and `plugin install it-ops-kb@it-ops-kb` in a fresh `CLAUDE_CONFIG_DIR` installed version `015468544e24` (the pushed HEAD); `claude mcp list` showed `plugin:it-ops-kb:kb` connected and `kb_mcp.py --status` ran from the cached copy.

Was not done:
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
- Stress suite disk use (fixed 2026-09-26, `0154685`): `test_stress.py` copied the whole `_cache/` (census clones, 2.6 GB) into each of 14 workers' kb copies, and pytest kept every run: 74 GB filled the disk. Copies now take only the `kbindex-*` files and pytest keeps failed tests' temp dirs only; a full run leaves 37 MB. Old runs may still sit in `$TMPDIR/pytest-of-<user>/` (pytest keeps the last three).
- Done 2026-09-26: the lint baseline is empty (34 errors fixed in `f9caf47`). Was: 25 lint errors are recorded in `_tools/lint_baseline.txt` (untagged facts, tags with no source id). Several articles also list header ids their body never cites (lint warnings), left alone because removing them could empty a source's `used_in`.
- Done 2026-09-26: the `_gaps.md` entries naming QS1, QS5 and QS7 now say what QS1a, QS5a and QS7a resolved.

## 4. Token usage: make lookups deterministic
**`_self/reports/plan-token-optimization.md` T1-T14: done** (see `_self/reports/token-usage.md`, "Measurement in a host project").
- **Plugin split:** two plugins, `it-ops-kb` and `it-ops-kb-docs`. There is no root `.mcp.json`: a clone runs `python3 _tools/kb_mcp.py --register-local` once (`/kb-setup` and the web SessionStart hook do it).
- **Six questions, fresh Sonnet sessions:** 13 turns and 312k input in a clone, 14 turns and 306k in a host project. On 2026-09-25 it was 19 turns and 691k.
- **Subagent startup:** `kb-lookup` starts at 3.9k tokens.
- **Review:** `/kb-review-workspace` found all five planted problems in the test host, each with the host line and the kb citation.
- **Fixed on the way:** the kb server lacked `resultType` (MCP 2026-07-28), so no kb tool loaded from the plugin.
- **Done 2026-09-26:** an install from gitlab.com itself (see section 2) and a push to GitLab `main`.
- **Retrieval audit done** (`_self/reports/token-usage.md`, "Retrieval quality audit"): untagged content and code blocks are searchable now, there is no false `none` on the blind questions, and line recall is 94%.
- **doc2query pilot done** (`_self/reports/token-usage.md`, "doc2query pilot"): pilot line recall 90% -> 97.5%, control unchanged.
  - **Confirmation round (seed 29, fresh arms):** no gain, 95% both ways. The baseline is already 95-98%.
  - **Whole-kb expansion: not done.** Decision in `_self/reports/token-usage.md`: expand only articles where real lookups miss.

Earlier; see `_self/reports/token-usage.md`, "Re-measurement after the changes":
- The six measured questions in fresh sessions: -74% input tokens, -72% output tokens, 351 -> 118 s.
- A `kb:` prompt the kb covers costs no model tokens.

Still open:
- Done 2026-09-26: 217 of the 233 unlinked ledger entries carry a `(topic: ...)` marker. The other 16 are headers, "no conflicts found" notes, budget notes and multi-project licence notes, left unlinked on purpose (`python3 _tools/rag.py audit --unlinked`).
- Done 2026-09-26: no DOC/COMMUNITY tag without a source id is left (lint baseline empty).
- Add failed real-world lookups to `_tools/lookup_eval.csv`.
