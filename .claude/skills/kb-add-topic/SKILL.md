---
name: kb-add-topic
description: Research and write a new it-ops-kb topic that follows the repository's contract (front matter, four sections, one tag per fact, source rows, coverage index). Use when the user asks to add or document a new topic in the kb.
disable-model-invocation: true
argument-hint: "<domain>/<topic-slug> and what it should cover"
---

# Add a kb topic

Request: $ARGUMENTS. If the domain, slug or scope is unclear, ask before researching.

## 1. Avoid duplicates
- `python3 _tools/rag.py search "<key terms>" -k 10` and `python3 _tools/rag.py topics <domain>`.
- If an existing topic covers it, propose extending that topic instead, and stop until the user decides.
- Use an existing domain directory when one fits. Slug: lowercase, hyphenated.

## 2. Research official sources
- Microsoft: `microsoft_docs_search` then `microsoft_docs_fetch`. Claude Code: `search_claude_code_docs`. MCP: `search_model_context_protocol`. Otherwise vendor docs, release notes, source repos. See `agents/doc-lookup-sources.md` for what is stable.
- Never call `submit_feedback`.
- Prefer a url pinned at a commit or version when one exists.
- Official sources give `DOC` facts. A non-official source is `COMMUNITY` and is never the only evidence for a DOC fact. Unconfirmed items are `UNK`.

## 3. Add sources first
Append rows to `_sources.csv`: `id,url,title,publisher,licence,retrieved_utc,version_or_date,artifact_sha256,used_in`.
- Next id: one above the highest existing `S` number. Never reuse an id. Reuse the existing id if the url is already there.
- `retrieved_utc` is today (`YYYY-MM-DD`). `used_in` lists the new files, separated by `;`.
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
---

# <Title>

## Summary
## Facts
## Reference
## Examples
```
- `topic` equals the path without `.md`. `sources` lists exactly the ids the body cites.
- Each Facts bullet ends in exactly one tag: `[DOC S123]`, `[DER S1, S2]` (show the derivation), `[COMMUNITY S9]` or `[UNK]`.
- Our own words. Quotes of 25 words or fewer unless the licence permits copying (MIT, Apache-2.0, CC BY 4.0), with attribution. Never copy CIS or ISO text.
- Placeholders only: `PL-LT-00123`, `PL-SRV-0042`, `corp.example.com`, tenant `00000000-0000-0000-0000-000000000000`, `jan.kowalski`.
- Large tables go in `<domain>/<slug>.csv` beside the article.
- `status: partial` when anything is `UNK`.

## 5. Register and log
- Add a row to `_coverage.csv` (`topic,priority,status,files,n_sources`) and the same row to the README coverage table, keeping their order.
- Failed lookups go to `_gaps.md` (what, where you looked). Disagreements go to `_conflicts.md` with both sources.

## 6. Check and report
- `python3 _tools/check.py` must end `errors=0`. Then `python3 .claude/skills/kb-verify/lint.py <domain>/<slug>` must report `errors=0`.
- Report the files created, the fact count by tag, and the open `UNK` items. Do not commit unless asked.
