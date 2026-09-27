# Work left

The open work, and only that: a finished item leaves this file (its commit records it). GitHub has no issues or merge requests for this repository; this list is the queue. Counts that move (partial articles, `UNK` facts, ledger entries) are commands here, not numbers.

## Layout: all knowledge under `kb/`

Code at the root (`_tools/`, `.claude/`, `.claude-plugin/`, CI), knowledge under `kb/`: `kb/_self/` (these docs, searched only with `--index`), `kb/public/` (the domains and ledgers) and any roots a team adds beside it (e.g. `kb/mdm-intune/`), so one kb answers questions across a team's systems. The target:

- **A root** is a `kb/<dir>/` with a `_root.md` (name, `id_prefix`, `visibility: public|internal`, description) and the full layout: its domains, `_sources.csv`, `_answers.md`, `_gaps.md`, `_conflicts.md`, `_coverage.csv`, `_coverage.md`, `_fetch_state.csv`, `_artifacts.csv`, `_census/`, and `_retrieval/` (`signals.csv`, `lookup_eval.csv`, `index_extra.csv`, `doc2query/`, moved from `_tools/`; `_tools/aliases.csv` stays shared). `public/`, not `_public/`: a leading `_` marks what pack skips.
- **Paths inside a root are relative to the root** (`used_in`, artifact paths, doc2query keys, links); `_tools/kbcommon.py` is the one place that says where the roots sit.
- **Own ledger, own id prefix per root:** `public` keeps `S` (legacy `S123` and hash `S-...`); a team root declares another (e.g. `I-k3f7q2zd`); `kbid` builds its patterns from the declared prefixes and refuses a taken one.
- **One federated server:** `kb_pack`, search, audit and facts search every root, with an optional `root` filter; key-word frequency counts across roots; output paths are relative to `kb/` (`public/intune/x.md:12`). `KB_ROOTS` (extra root paths) replaces `KB_ROOT`, and `kb/_self/plugin.md` §6 is rewritten around roots inside `kb/`.
- **Placeholders-only** applies to `visibility: public` roots; a team keeps its internal roots in its fork, which pulls tools and `public/` from upstream and serves as its plugin marketplace.
- **Fetch and census** take a root; census tags cover `public`.
- **Left, each commit through the full gate:** federation (a `_root.md` per root, multi-root pack, `root` filter, `KB_ROOTS`, per-root `kbid`/`check`/`fetch`/census, a coverage page per root instead of `kb/_self/coverage.md`, a `/kb-add-root` skill, tests with a temporary second root); the docs (`/kb-self`: README, maintaining, design, tools, content rules, `kb/_self/plugin.md` §6 around roots inside `kb/`); `/kb-verify`, stress, `rag.py eval` with no verdict change, one host-plugin lookup.
- Later: a skill that ingests knowledge from a team's other repositories into its roots.

## Lookup quality

- **False `good` on common words.** The `check:` line catches a missing product name and key words spread across unrelated facts, but not a question whose every word is common and present in one unrelated fact: "password reset link", "email attachment size", "page file size", "remote desktop gateway ports" still come out `good` without a `check:` line. Every verdict rule tried so far demoted true `good` eval rows (`kb/_self/reports/token-usage.md`, "Retrieval quality").
- **Off-domain questions come out `weak`, not `none`** (Horizon, SAP GUI, ServiceNow), though the `check:` line fires on them. The model then reads the pack and says the kb does not cover it, at one extra lookup.
- **Real misses into the eval set.** Add every failed real-world lookup (a `kb-gap` report, a wrong `kb:` answer) to `kb/public/_retrieval/lookup_eval.csv` (`python3 _tools/kbid.py eval "<question>"` for the id). When the misses are paraphrase, expand only those articles (`kb/_self/doc2query.md`).

## Token cost

- **Trim the plugin's always-on cost** (about 1.45k tokens per host session, most of it the `kb_pack` schema, about 1.5k characters, and the server instructions, about 1.4k; `kb/_self/reports/token-usage.md`, "Always-on cost") after the `kb/` layout settles; then `rag.py eval`, one host lookup, and re-measure.
- **`AGENTS.md` is 4,091 of its 4,096 bytes** (the cap is tested and stays): the `kb/` paths and any addition need cuts elsewhere.
- **Re-measure the `kb-lookup` agent's start context.** 3.9k was measured when the skill it preloads was 3.0 KB; the skill is 4.3 KB now.
- **Watch `claude -p` defaults.** If `--bare` becomes the default for `claude -p`, `_tools/agent_bench.py` configs that rely on the clone's plugins and settings must load them explicitly; `_tools/kb_ask.py` already passes its servers.
- **Watch native citations.** The Messages API's `search_result` blocks give citations from tool results, but MCP does not carry them and the Agent SDK drops them from MCP tool results; revisit when MCP or Claude Code supports them.

## Content

- **Partial articles and unconfirmed facts:** `python3 _tools/rag.py audit --status partial` lists them, with their `UNK` counts and linked `_gaps.md` entries; most need a vendor pricing or licence page, a JS-rendered page (NVD, EPSS) or an undocumented log path. Read JS-rendered pages with Claude in Chrome during `/kb-refresh`; only pages behind a login or paths on a device go to a person.
- **Real disagreements between sources** stay in `_conflicts.md` until a source settles them (Win32 supersedence limits, Recall default, PowerShell lifecycle dates, ...): `python3 _tools/rag.py audit --entries` shows them per article.
- **Header sources no fact cites:** the kb-verify lint warns about them (`python3 .claude/skills/kb-verify/lint.py`). Per article with `/kb-refresh`: cite the source in a fact it supports, else drop it from the front matter (removing one can empty its `used_in`).
## Distribution

- **Triage of gap reports is manual.** Maintainers turn `/it-ops-kb:kb-gap` reports into `_gaps.md` entries and eval rows, then `/kb-research` or `/kb-add-topic` (`kb/_self/plugin.md`, the triage paragraph). It stays manual: no scheduled agent pushes unreviewed research to `main`.
