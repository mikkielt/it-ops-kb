# Work left

The open work, and only that: a finished item leaves this file (its commit records it). GitHub has no issues or merge requests for this repository; this list is the queue. Counts that move (partial articles, `UNK` facts, ledger entries) are commands here, not numbers.

## Remotes and CI

- **GitHub Actions results are unchecked.** `.github/workflows/kb.yml` runs on every push, but no session here could read its runs (the repository is private and `gh` is not installed): look at the Actions tab.
- **Branch protection for GitHub `main`:** undecided. Pushes go straight to `main` by design (`_self/git.md`); required status checks would still block a push that fails CI. Read GitHub's live docs on required status checks before deciding.

## Lookup quality

- **False `good` on common words.** The `check:` line catches a missing product name and key words spread across unrelated facts, but not a question whose every word is common and present in one unrelated fact: "password reset link", "email attachment size", "page file size", "remote desktop gateway ports" still come out `good` without a `check:` line. Every verdict rule tried so far demoted true `good` eval rows (`_self/reports/token-usage.md`, "Retrieval quality").
- **Off-domain questions come out `weak`, not `none`** (Horizon, SAP GUI, ServiceNow), though the `check:` line fires on them. The model then reads the pack and says the kb does not cover it, at one extra lookup.
- **Real misses into the eval set.** Add every failed real-world lookup (a `kb-gap` report, a wrong `kb:` answer) to `_tools/lookup_eval.csv` (`python3 _tools/kbid.py eval "<question>"` for the id). When the misses are paraphrase, expand only those articles (`_self/doc2query.md`).

## Token cost

- **The plugin's always-on cost** is about 1.45k tokens per host session, most of it the `kb_pack` schema (about 1.5k characters) and the server instructions (about 1.4k) (`_self/reports/token-usage.md`, "Always-on cost"). Decide whether to trim them; after any cut run `rag.py eval` and one host lookup, and re-measure.
- **`AGENTS.md` is 4,091 of its 4,096 bytes** (the cap is tested): the next addition needs a cut elsewhere.
- **Re-measure the `kb-lookup` agent's start context.** 3.9k was measured when the skill it preloads was 3.0 KB; the skill is 4.3 KB now.
- **Watch `claude -p` defaults.** If `--bare` becomes the default for `claude -p`, `_tools/agent_bench.py` configs that rely on the clone's plugins and settings must load them explicitly; `_tools/kb_ask.py` already passes its servers.
- **Watch native citations.** The Messages API's `search_result` blocks give citations from tool results, but MCP does not carry them and the Agent SDK drops them from MCP tool results; revisit when MCP or Claude Code supports them.

## Content

- **Partial articles and unconfirmed facts:** `python3 _tools/rag.py audit --status partial` lists them, with their `UNK` counts and linked `_gaps.md` entries; most need a vendor pricing or licence page, a JS-rendered page (NVD, EPSS) or an undocumented log path read by hand.
- **Real disagreements between sources** stay in `_conflicts.md` until a source settles them (Win32 supersedence limits, Recall default, PowerShell lifecycle dates, ...): `python3 _tools/rag.py audit --entries` shows them per article.
- **Header sources no fact cites:** the kb-verify lint warns about them (`python3 .claude/skills/kb-verify/lint.py`). They are left alone because removing one can empty a source's `used_in`; decide per source whether to cite it or drop it.
- **Two unconfirmed census sources** (S1929 on x.com, S1933 on Medium) are cited by no fact: drop them from their articles' front matter, or leave them as unconfirmed.

## Distribution

- **Triage of gap reports is manual.** Maintainers turn `/it-ops-kb:kb-gap` reports into `_gaps.md` entries and eval rows, then `/kb-research` or `/kb-add-topic` (`_self/plugin.md`, the triage paragraph). Optional: a scheduled cloud agent (`/schedule`) that runs `/kb-research` on open reports and pushes verified topics.
