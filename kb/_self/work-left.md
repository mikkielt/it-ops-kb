# Work left

The open work, and only that: a finished item leaves this file (its commit records it). GitHub has no issues or merge requests for this repository; this list is the queue. Counts that move (partial articles, `UNK` facts, ledger entries) are commands here, not numbers.

## Roots

- **Check a host-plugin lookup across roots.** The tests cover a second root through `KB_ROOTS` and a copy of the repository; no installed plugin has served a team root yet. With a fork that has one: install it as a plugin in a host project, ask a question spanning both roots, and check the pack carries both roots' lines.
- **Ingest from a team's other repositories.** A skill that turns a team's repositories and service docs into articles of its roots (sources as repository files at a pinned commit, `CODE` tags), so the kb answers questions across the team's services.

## Lookup quality

- **False `good` on common words.** The `check:` line catches a missing product name and key words spread across unrelated facts, but not a question whose every word is common and present in one unrelated fact: "password reset link", "email attachment size", "page file size", "remote desktop gateway ports" still come out `good` without a `check:` line. Every verdict rule tried so far demoted true `good` eval rows (`kb/_self/reports/token-usage.md`, "Retrieval quality").
- **Off-domain questions come out `weak`, not `none`** (Horizon, SAP GUI, ServiceNow), though the `check:` line fires on them. The model then reads the pack and says the kb does not cover it, at one extra lookup.
- **Real misses into the eval set.** Add every failed real-world lookup (a `kb-gap` report, a wrong `kb:` answer) to `kb/public/_retrieval/lookup_eval.csv` (`python3 _tools/kbid.py eval "<question>"` for the id). When the misses are paraphrase, expand only those articles (`kb/_self/doc2query.md`).

## Token cost

- **`AGENTS.md` is 4,088 of its 4,096 bytes** (the cap is tested and stays): any addition needs a cut elsewhere.
- **Re-measure the `kb-lookup` agent's start context.** 3.9k was measured when the skill it preloads was 3.0 KB; the skill is 4.2 KB now.
- **Watch `claude -p` defaults.** If `--bare` becomes the default for `claude -p`, `_tools/agent_bench.py` configs that rely on the clone's plugins and settings must load them explicitly; `_tools/kb_ask.py` already passes its servers.
- **Watch native citations.** The Messages API's `search_result` blocks give citations from tool results, but MCP does not carry them and the Agent SDK drops them from MCP tool results; revisit when MCP or Claude Code supports them.

## Content

- **Partial articles and unconfirmed facts:** `python3 _tools/rag.py audit --status partial` lists them, with their `UNK` counts and linked `_gaps.md` entries; most need a vendor pricing or licence page, a JS-rendered page (NVD, EPSS) or an undocumented log path. Read JS-rendered pages with Claude in Chrome during `/kb-refresh`; only pages behind a login or paths on a device go to a person.
- **Real disagreements between sources** stay in `_conflicts.md` until a source settles them (Win32 supersedence limits, Recall default, PowerShell lifecycle dates, ...): `python3 _tools/rag.py audit --entries` shows them per article.
- **Header sources no fact cites:** the kb-verify lint warns about them (`python3 .claude/skills/kb-verify/lint.py`). Per article with `/kb-refresh`: cite the source in a fact it supports, else drop it from the front matter (removing one can empty its `used_in`).
## Distribution

- **Triage of gap reports is manual.** Maintainers turn `/it-ops-kb:kb-gap` reports into `_gaps.md` entries and eval rows, then `/kb-research` or `/kb-add-topic` (`kb/_self/plugin.md`, the triage paragraph). It stays manual: no scheduled agent pushes unreviewed research to `main`.
