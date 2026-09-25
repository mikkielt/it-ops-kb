---
name: kb-add-topic
description: Research and write a new it-ops-kb topic that follows the repository's contract (front matter, four sections, one tag per fact, source rows, coverage index). Use when the user asks to add or document a new topic in the kb.
disable-model-invocation: true
argument-hint: "<domain>/<topic-slug> and what it should cover"
---

# Add a kb topic

Request: $ARGUMENTS. If the domain, slug or scope is unclear, ask before researching.

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): the shared permission rules match single commands, so a chained command asks for approval or is refused in a headless run.

## 1. Avoid duplicates
- `python3 _tools/rag.py search "<key terms>" -k 10` and `python3 _tools/rag.py topics <domain>`.
- If an existing topic covers it, propose extending that topic instead, and stop until the user decides. The rules for extending versus a new topic, and for where a new one goes, are in `/kb-research` step 2.
- Use an existing domain directory when one fits: the domain of the article that will link to the new topic. Never create a new top-level directory without the user's decision. Slug: lowercase, hyphenated.

## 2. Research official sources
- Microsoft: `microsoft_docs_search` then `microsoft_docs_fetch`. Claude Code: `search_claude_code_docs`. MCP: `search_model_context_protocol`. Otherwise vendor docs, release notes, source repos. See `agents/doc-lookup-sources.md` for what is stable.
- Never call `submit_feedback`.
- Prefer a url pinned at a commit or version when one exists.
- Read the full page before citing it (`microsoft_docs_fetch` for Learn; for other sites, fetch the page and keep the key sentence verbatim, at most 25 words, for the report). Cite the page the sentence is on; a fact whose sentence you cannot find is `[UNK]`, logged in `_gaps.md`.
- Official sources give `DOC` facts. A non-official source is `COMMUNITY` and is never the only evidence for a DOC fact. Unconfirmed items are `UNK`.

## 3. Add sources first
Append rows to `_sources.csv`: `id,url,title,publisher,licence,retrieved_utc,version_or_date,artifact_sha256,used_in,superseded_by`.
- Id: run `python3 _tools/kbid.py url <URL>` (several urls at once are fine) and use the `S-xxxxxxxx` it prints. Never invent an id or take "the next number": the id is a hash of the url, so parallel writers do not collide. If it says the url is already in `_sources.csv`, reuse that id (legacy `S<number>` ids stay valid).
- `superseded_by` is empty for a new row.
- `retrieved_utc` is today (`YYYY-MM-DD`). Leave `used_in` empty: `build_index.py` fills it (step 5).
- `licence`, by source type (reuse an existing row's wording for the same publisher when there is one):
  - Microsoft Learn page (incl. fetched through the MCP server): `Microsoft Learn terms of use (paraphrased; quote <=25 words)`
  - MicrosoftDocs GitHub file at a commit: the repo's licence, usually `CC BY 4.0 (MicrosoftDocs prose)`
  - Anthropic docs: `Anthropic docs (summarize; quote <=25 words)`
  - Open-source repo or spec: its SPDX id (`MIT`, `Apache-2.0`, ...)
  - Anything else: `not verified (summarized only)`
- `version_or_date`: the page's own version or date when shown (`ms.date`, release tag), else `retrieved <date>`.
- Write the CSV with Python's `csv` module (or quote every field that contains a comma). An unquoted comma breaks the row and `check.py` rejects it.

## 4. Write `<domain>/<slug>.md`
```
---
topic: <domain>/<slug>
priority: P0|P1|P2|P3
applies_to: "<product/version scope>"
retrieved_utc: <today>
sources: [S..., S...]
status: complete|partial|unknown
files: [<path>, <dir>/]    # optional: only files beyond <slug>.md and <slug>.* siblings
---

# <Title>

## Summary
## Facts
## Reference
## Examples
```
- `topic` equals the path without `.md`. `sources` lists exactly the ids the body cites.
- Each Facts bullet ends in exactly one tag: `[DOC S-k3f7q2zd]`, `[DER S1, S-k3f7q2zd]` (show the derivation), `[COMMUNITY S9]` or `[UNK]`.
- Our own words. Quotes of 25 words or fewer unless the licence permits copying (MIT, Apache-2.0, CC BY 4.0), with attribution. Never copy CIS or ISO text.
- Placeholders only: `PL-LT-00123`, `PL-SRV-0042`, `corp.example.com`, tenant `00000000-0000-0000-0000-000000000000`, `jan.kowalski`.
- Large tables go in `<domain>/<slug>.csv` beside the article (listed automatically). Data under another name or in a subdirectory goes in `files:` (kb-root paths; a directory ends in `/`).
- `status: partial` when anything is `UNK`.
- `priority`: the research order, not importance (see README). A new topic gets the priority the user gives, else `P3`.

## 5. Register and log
- Run `python3 _tools/build_index.py`. It adds the topic's row to `_coverage.csv` and the README coverage table (ordered by domain, priority, topic id; `n_sources` = ids in the `sources:` header) and fills `used_in` in `_sources.csv`. Never edit those by hand.
- Failed lookups go to `_gaps.md` (what, where you looked). Disagreements go to `_conflicts.md` with both sources.

## 6. Check and report
- `python3 _tools/check.py` must end `errors=0`. Then `python3 .claude/skills/kb-verify/lint.py <domain>/<slug>` must report `errors=0`.
- Report the files created, the fact count by tag, and the open `UNK` items. Do not commit unless asked.
