# Work left

The open work, and only that: a finished item leaves this file (its commit records it). GitHub has no issues or merge requests for this repository; this list is the queue. Counts that move (partial articles, `UNK` facts, ledger entries) are commands here, not numbers.

## Roots

- **Check a host-plugin lookup across roots.** The tests cover a second root through `KB_ROOTS` and a copy of the repository; no installed plugin has served a team root yet. With a fork that has one: install it as a plugin in a host project, ask a question spanning both roots, and check the pack carries both roots' lines.
- **Design a skill that ingests a team's repositories into its roots.** Sources are repository files at a pinned commit (`CODE` tags) and the repositories' own docs, so the kb answers questions across a team's services. Two modes:
  - **From a host project:** the kb is installed as a plugin in another code repository, and an agent working there turns that repository's knowledge into facts of a root. The plugin copy is read-only, so the design has to say where the facts land (the team's fork, a clone, a root under `KB_ROOTS`) and how they get committed.
  - **From this clone:** "source `<repo>` and put it here", run inside this repository.
  - Both modes need the agent to reason and guide the user rather than follow a fixed script: which root the knowledge belongs to or whether to create one (`/kb-add-root`), its visibility, which parts of the repository are worth facts, how to split them into topics, and what to leave out (secrets, generated code, vendored copies).

## Lookup quality

- **False `good` on common words.** The `check:` line catches a missing product name and key words spread across unrelated facts, but not a question whose every word is common and present in one unrelated fact: "password reset link", "email attachment size", "page file size", "remote desktop gateway ports" still come out `good` without a `check:` line. Every verdict rule tried so far demoted true `good` eval rows (`kb/_self/reports/token-usage.md`, "Retrieval quality").
- **Off-domain questions come out `weak`, not `none`** (Horizon, SAP GUI, ServiceNow), though the `check:` line fires on them. The model then reads the pack and says the kb does not cover it, at one extra lookup.
- **Real misses into the eval set.** Add every failed real-world lookup (a `kb-gap` report, a wrong `kb:` answer) to `kb/public/_retrieval/lookup_eval.csv` (`python3 _tools/kbid.py eval "<question>"` for the id). When the misses are paraphrase, expand only those articles (`kb/_self/doc2query.md`).

## Token cost

- **`AGENTS.md` is within a few bytes of its 4 KB cap** (tested; `wc -c AGENTS.md`): any addition needs a cut elsewhere.
- **Re-measure the `kb-lookup` agent's start context.** The 3.9k in `kb/_self/reports/token-usage.md` predates the growth of the skill it preloads.
- **Watch `claude -p` defaults.** If `--bare` becomes the default for `claude -p`, `_tools/agent_bench.py` configs that rely on the clone's plugins and settings must load them explicitly; `_tools/kb_ask.py` already passes its servers.
- **Watch native citations.** The Messages API's `search_result` blocks give citations from tool results, but MCP does not carry them and the Agent SDK drops them from MCP tool results; revisit when MCP or Claude Code supports them.

## Content

- **Partial articles and unconfirmed facts:** `python3 _tools/rag.py audit --status partial` lists them, with their `UNK` counts and linked `_gaps.md` entries; most need a vendor pricing or licence page, a JS-rendered page (NVD, EPSS) or an undocumented log path. Read JS-rendered pages with Claude in Chrome during `/kb-refresh`; only pages behind a login or paths on a device go to a person.
- **Real disagreements between sources** stay in `_conflicts.md` until a source settles them (Win32 supersedence limits, Recall default, PowerShell lifecycle dates, ...): `python3 _tools/rag.py audit --entries` shows them per article.
- **Resolve `kb/public/_gaps.md` and `kb/public/_conflicts.md` with deeper web research.** Take as many entries as possible, each with an advanced lookup beyond the first search (vendor release notes, product changelogs, source repositories, support articles, JS-rendered pages through Claude in Chrome). Turn each resolved entry into confirmed facts with `/kb-research` or `/kb-refresh`, and close the entry. An entry that stays open records what was tried. `python3 _tools/rag.py audit --entries` lists the entries per article.
- **Licence census of every source.** Classify each source by what its licence allows with its content: read and paraphrase only, quote briefly, or copy and redistribute (keep a verbatim copy, with attribution). Record it in a checkable form, since the `licence` column of `_sources.csv` is free text today, with variant spellings of one licence and "not verified" rows; `check.py` can then test it. Where a source's terms are unclear, read its terms page or LICENSE file. This comes before a later task: decide which source documents may be kept locally and diffed in git, instead of only being hashed in `_fetch_state.csv`.
- **Header sources no fact cites:** the kb-verify lint warns about them (`python3 .claude/skills/kb-verify/lint.py`). Per article with `/kb-refresh`: cite the source in a fact it supports, else drop it from the front matter (removing one can empty its `used_in`).

## Distribution

- **Triage of gap reports is manual.** Maintainers turn `/it-ops-kb:kb-gap` reports into `_gaps.md` entries and eval rows, then `/kb-research` or `/kb-add-topic` (`kb/_self/plugin.md`, the triage paragraph). It stays manual: no scheduled agent pushes unreviewed research to `main`.
