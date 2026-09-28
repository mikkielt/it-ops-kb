# Work left

The open work, and only that: a finished item leaves this file (its commit records it). GitHub has no issues or merge requests for this repository; this list is the queue. Counts that move (partial articles, `UNK` facts, ledger entries) are commands here, not numbers.

## Roots

- **Design a skill that ingests a team's repositories into its roots.** Sources are repository files at a pinned commit (`CODE` tags) and the repositories' own docs, so the kb answers questions across a team's services. Two modes:
  - **From a host project:** the kb is installed as a plugin in another code repository, and an agent working there turns that repository's knowledge into facts of a root. The plugin copy is read-only, so the design has to say where the facts land (the team's fork, a clone, a root under `KB_ROOTS`) and how they get committed.
  - **From this clone:** "source `<repo>` and put it here", run inside this repository.
  - Both modes need the agent to reason and guide the user rather than follow a fixed script: which root the knowledge belongs to or whether to create one (`/kb-add-root`), its visibility, which parts of the repository are worth facts, how to split them into topics, and what to leave out (secrets, generated code, vendored copies).

## Lookup quality

- **False `good` left after the verdict corrections.** The corrections (`kb/_self/tools.md`, "Two corrections to the verdict") need a question with nothing specific whose key words no single fact holds, or a rare product name no printed line holds. What passes them, all on the off-kb list (`kb/public/_retrieval/doc2query/offkb_questions.txt`), none in `lookup_eval.csv`:
  - common words one unrelated fact holds together: "password reset link" (the KRBTGT article), "page file size" (a remediations fact that says "script file size" and "page"), "web proxy port", "desktop wallpaper setting". A lexical rule would need to know which word is the subject; requiring two question words side by side, or the words in the fact's text rather than its title, fixed 1-3 of them and demoted 2 more true goods ("Verdict corrections" in `kb/_self/reports/token-usage.md`);
  - a capitalised generic name the lead article happens to hold: "Which ports does Remote Desktop Gateway use?" (Power BI Desktop, the data gateway), "kerberos armoring requirement";
  - another product the kb mentions on a printable line: "How do I integrate ServiceNow with Intune?" (`good` with a `check:` line), "How does ServiceNow discovery find Windows servers?" (`weak`: the kb has ServiceNow's IRE in `prior-art/`).
  - One true good is lost: "client log upload size limit" is `weak` (its fact lacks "upload"), an `allow_weak` eval row.

## Token cost

- **`AGENTS.md` is within a few bytes of its 4 KB cap** (tested; `wc -c AGENTS.md`): any addition needs a cut elsewhere.
- **Watch `claude -p` defaults.** If `--bare` becomes the default for `claude -p`, `_tools/agent_bench.py` configs that rely on the clone's plugins and settings must load them explicitly; `_tools/kb_ask.py` already passes its servers.
- **Watch native citations.** The Messages API's `search_result` blocks give citations from tool results, but MCP does not carry them and the Agent SDK drops them from MCP tool results; revisit when MCP or Claude Code supports them. The block format is in `agents/hybrid-retrieval.md`.

## Content

- **Real disagreements between sources** stay in `_conflicts.md` until a source settles them (Win32 supersedence limits, Recall default, PowerShell lifecycle dates, ...): `python3 _tools/rag.py audit --entries` shows them per article.
- **Open ledger entries need a lab, a login or unpublished information.** Every open `_gaps.md` and `_conflicts.md` entry carries a dated note of what was tried, and what it still needs: a Windows or DSC lab run, a tenant or vendor login, or a number the vendor has not published, which web research cannot supply. `python3 _tools/rag.py audit --entries` lists them.
- **Sources with `reuse` `unknown`** (treated as paraphrase): their `licence` says what was tried; the terms pages are blocked from the maintainer's network (cyber.gov.au) or refuse scripted reads (iso.org). Read them in a browser (Claude in Chrome during `/kb-refresh`, or a person) and set the class.

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
- **Fact anchors.** Each fact records where its evidence sits, without copying licence-restricted text. The draft stores the section heading path, the fact's key terms and a hash of the normalized backing sentence. The heading is only a hint for ranking candidates, never a constraint. Matching searches the whole new page. If the page has no match, it searches the pages the provider links it to: the redirect target, pages added in the same sitemap diff, and the provider's search. So a passage that moved to another section or another page is still found. Open: whether to also keep a short quote where the source's `reuse` class allows it.
- **Resolution per fact after a source changes.**
  - Anchor found verbatim: re-date the fact with no model (decided).
  - Found with changed numbers, versions or names: flag the fact with the old and new passage.
  - Not found: search across pages.
  - Still nothing: the fact goes to a model check (supported, contradicted, or not enough information, as in FEVER and AIS), or becomes `[UNK]` with a `_gaps.md` entry.
  - Every outcome is logged like a census verdict, and the commit carries `KB-Verified`.
- **Old versions come from upstream, not the kb** (decided). The kb commits hashes, version ids and anchors, never licence-restricted text. When a diff needs the old text, it comes from the provider's history: the public docs repository at the stored commit (a Learn page's `git_commit_id` resolves in its public mirror while the mirror is live; `memdocs` is archived), or a Wayback or Memento snapshot at the fact's date (CDX API, not the Availability API, which can answer empty). Local `_cache/snapshots/` is a bonus. The `reuse` class decides whether any text may be committed (next item).
- **Keep `copy` source documents in git?** The `reuse` column of `_sources.csv` classes every source by what its licence allows (`copy`, `quote`, `paraphrase`, `unknown`; `kb/_self/content-rules.md`, "Licensing and privacy"). Decide whether the documents of `copy` sources are kept in the repository and diffed in git, instead of only being hashed in `_fetch_state.csv`, and how their attribution is kept.
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
