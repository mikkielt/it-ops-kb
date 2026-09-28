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

## Fact diff

- **Bulk snapshots of `copy` sources wait for a decision on size.** Only the `entra` domain's are committed; the rest would be 758 files, 11.4 MB of text, about 2.4 MB compressed ("Snapshots of copy sources" in `kb/_self/reports/fact-diff.md`). Until then their old text comes from the previous fetch in `_cache/` or a Wayback capture. `python3 _tools/factdiff.py snapshot` writes them.
- **The first census after anchoring bootstraps the dates.** A detection baseline taken after a source's last confirmation proves nothing about the days between, so `apply` holds such sources back (Learn pages pass on their own `updated_at`); run `/kb-census` with its phase 0 once to start the chain.
- **Unanchored facts** (`python3 _tools/factdiff.py anchors --unlocated`): 52% of fact-source pairs, derivations and section summaries above all. Splitting such facts, or anchoring a DER fact to the DOC facts it derives from, would shrink what a model reads when their source changes.
- **Old text from a Learn page's public mirror at its `git_commit_id`** is not wired into `review` (it uses the snapshot, the previous fetch, a Wayback capture, then the anchor's quote); the census's clones of the MicrosoftDocs repositories could serve it.

## Distribution

- **Triage of gap reports is manual.** Maintainers turn `/it-ops-kb:kb-gap` reports into `_gaps.md` entries and eval rows, then `/kb-research` or `/kb-add-topic` (`kb/_self/plugin.md`, the triage paragraph). It stays manual: no scheduled agent pushes unreviewed research to `main`.
