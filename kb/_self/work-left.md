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
- **Benchmark scenarios for any re-measurement** (`_tools/agent_bench.py`), beyond covered and off-kb questions:
  - **Partial knowledge:** the kb covers part of a question and the agent must search the web for the rest. Does it skip urls the pack already cites as fetched and fact-checked, or fetch them again? Does it keep the kb's facts and only fill the gap?
  - **A newer version upstream:** a cited source has a newer release or a changed page since its `retrieved_utc`. Does the agent notice (the fact's date, a version in the question), check the source, and say which version its answer is for?
  - **An older kb than `origin`:** the installed copy is behind the kb's remote. Does `kb_status` show it, and does the agent say so or suggest updating the plugin?
- **Re-measure the `kb-lookup` agent's start context.** The 3.9k in `kb/_self/reports/token-usage.md` predates the growth of the skill it preloads.
- **Watch `claude -p` defaults.** If `--bare` becomes the default for `claude -p`, `_tools/agent_bench.py` configs that rely on the clone's plugins and settings must load them explicitly; `_tools/kb_ask.py` already passes its servers.
- **Watch native citations.** The Messages API's `search_result` blocks give citations from tool results, but MCP does not carry them and the Agent SDK drops them from MCP tool results; revisit when MCP or Claude Code supports them. The block format is in `agents/hybrid-retrieval.md`.

## Content

- **Partial articles and unconfirmed facts:** `python3 _tools/rag.py audit --status partial` lists them, with their `UNK` counts and linked `_gaps.md` entries; most need a vendor pricing or licence page, a JS-rendered page (NVD, EPSS) or an undocumented log path. Read JS-rendered pages with Claude in Chrome during `/kb-refresh`; only pages behind a login or paths on a device go to a person.
- **Real disagreements between sources** stay in `_conflicts.md` until a source settles them (Win32 supersedence limits, Recall default, PowerShell lifecycle dates, ...): `python3 _tools/rag.py audit --entries` shows them per article.
- **Resolve `kb/public/_gaps.md` and `kb/public/_conflicts.md` with deeper web research.** Take as many entries as possible, each with an advanced lookup beyond the first search (vendor release notes, product changelogs, source repositories, support articles, JS-rendered pages through Claude in Chrome). Turn each resolved entry into confirmed facts with `/kb-research` or `/kb-refresh`, and close the entry. An entry that stays open records what was tried. `python3 _tools/rag.py audit --entries` lists the entries per article.
- **Licence census of every source.** Classify each source by what its licence allows with its content: read and paraphrase only, quote briefly, or copy and redistribute (keep a verbatim copy, with attribution). Record it in a checkable form, since the `licence` column of `_sources.csv` is free text today, with variant spellings of one licence and "not verified" rows; `check.py` can then test it. Where a source's terms are unclear, read its terms page or LICENSE file. This comes before a later task: decide which source documents may be kept locally and diffed in git, instead of only being hashed in `_fetch_state.csv`. Provider terms are in `agents/doc-lookup-sources.md`: the Learn terms defer to a repository's explicit licence, which differs per MicrosoftDocs mirror (memdocs CC BY 4.0, entra-docs MIT), and Anthropic docs carry no open licence.
- **Header sources no fact cites:** the kb-verify lint warns about them (`python3 .claude/skills/kb-verify/lint.py`). Per article with `/kb-refresh`: cite the source in a fact it supports, else drop it from the front matter (removing one can empty its `used_in`).

## Fact diff: resolving source changes into fact updates (draft design)

**Before building: interview the user in depth.** This draft comes from one research pass and a short interview. Build it only after the other open items here are done, and re-interview first on every open question below. The goal is to turn "a source changed" into "these facts still hold, these changed, these are gone" deterministically: from a single edited page to a documentation overhaul that splits, merges, moves or retires pages, including links that go dead or turn into zombies (200 OK with unrelated content). **Token efficiency comes first**, as for the whole kb: detection, matching and most re-confirmation cost no model tokens, and a model reads only the few facts whose backing passage actually changed, each with its old and new passage, never whole pages.

- **Provider registry and a probe skill.** A data file of knowledge providers (per host or site: Microsoft Learn, raw GitHub files at a commit, github.com, code.claude.com, modelcontextprotocol.io, GitLab docs, a generic fallback for the long tail). It records each provider's properties, with the date they were probed:
  - version signals: page metadata, a git commit per page, ETag or Last-Modified, and whether each is usable;
  - stable ids that survive moves;
  - a raw or markdown endpoint;
  - sitemap and `lastmod`;
  - redirect records;
  - a public source repository and its history API;
  - a search API;
  - how its MCP server reports freshness;
  - rate limits and licence class.

  A skill probes a provider (live requests, deterministic checks) and updates its row. The fetch tools read the row to pick the cheapest reliable signal per source. Teams add rows for their internal providers (wikis, repositories).
- **Detection, cheapest signal first, no model.**
  - HTTP validators first where they work: Learn answers `If-None-Match` with `304` (`agents/doc-change-detection.md`; whether its ETag moves on template rebuilds is an open gap). Then a per-source version id: on Learn, `git_commit_id`, `updated_at` and `document_id` from the page's `<head>` or the front matter of its `?accept=text/markdown` form. Learn's MCP server returns bare markdown with no date or version. For pinned raw files: a newer commit on the branch.
  - Then the text hash `fetch.py` keeps today.
  - Site-level changes: diff the provider's sitemap for added and removed URLs (on Learn its `lastmod` disagreed with the page's `updated_at`, so not per page) and redirect records (Learn's `.openpublishing.redirection*.json`; `redirect_document_id` tells a rename from a partial merge). 301 chains are followed and recorded.
  - Zombies and soft 404s: a sibling-URL test (fetch a bogus path on the same site and compare), and a similarity fingerprint of the page (MinHash or simhash, stdlib). A 200 page whose fingerprint collapses toward the site's landing or error page is dead.
- **Fact anchors.** Each fact records where its evidence sits, without copying licence-restricted text. The draft stores the section heading path, the fact's key terms and a hash of the normalized backing sentence. The heading is only a hint for ranking candidates, never a constraint. Matching searches the whole new page. If the page has no match, it searches the pages the provider links it to: the redirect target, pages added in the same sitemap diff, and the provider's search. So a passage that moved to another section or another page is still found. Open: whether to also keep a short quote where the licence census allows copying.
- **Resolution per fact after a source changes.**
  - Anchor found verbatim: re-date the fact with no model (decided).
  - Found with changed numbers, versions or names: flag the fact with the old and new passage.
  - Not found: search across pages.
  - Still nothing: the fact goes to a model check (supported, contradicted, or not enough information, as in FEVER and AIS), or becomes `[UNK]` with a `_gaps.md` entry.
  - Every outcome is logged like a census verdict, and the commit carries `KB-Verified`.
- **Old versions come from upstream, not the kb** (decided). The kb commits hashes, version ids and anchors, never licence-restricted text. When a diff needs the old text, it comes from the provider's history: the public docs repository at the stored commit (a Learn page's `git_commit_id` resolves in its public mirror while the mirror is live; `memdocs` is archived), or a Wayback or Memento snapshot at the fact's date (CDX API, not the Availability API, which can answer empty). Local `_cache/snapshots/` is a bonus. The licence census (Content, above) decides whether any text may be committed.
- **Learn first, then the other providers** (decided): Learn exposes the richest signals and has the most sources.
- **Research recorded** in `agents/doc-change-detection.md` (2026-09-27): Learn meta tags, ETag, markdown form, sitemaps, redirection files, public-mirror commits, Memento, Wayback Availability and CDX APIs, soft-404 detection.
- **Research leads (not in the kb yet):**
  - Learn's undocumented search API with `lastUpdatedDate`.
  - Reference rot and content drift (Klein, Jones, Van de Sompel et al.).
  - changedetection.io and urlwatch as filter-chain designs.
  - trafilatura and htmldate as extraction and date rules to port.
  - AIS and FEVER for claim checks.
  - None of the docs MCP servers probed offers resource subscriptions or a change feed.

  Record the confirmed ones as kb facts (`/kb-research`) when the work starts.
- **Open questions for the interview:**
  - Anchor contents, and quotes where licences allow.
  - Where the provider registry lives: per root, or shared.
  - Thresholds for "changed" and "dead".
  - How a split page's facts are reassigned to the new pages.
  - How often detection runs: on demand, before a census, or scheduled.
  - How results reach the user: a report, or direct commits.
  - Interplay with the census and `fetch.py --diff`, whether to replace or extend them.
  - What happens when a source is gone and no successor exists.

## Distribution

- **Triage of gap reports is manual.** Maintainers turn `/it-ops-kb:kb-gap` reports into `_gaps.md` entries and eval rows, then `/kb-research` or `/kb-add-topic` (`kb/_self/plugin.md`, the triage paragraph). It stays manual: no scheduled agent pushes unreviewed research to `main`.
