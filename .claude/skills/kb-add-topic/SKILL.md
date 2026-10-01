---
name: kb-add-topic
description: Use when the user asks to add, write or document a new topic, article or data table in it-ops-kb (<domain>/<slug>): researches official sources and writes it to the kb contract (source rows, one tag per fact, four sections, index).
argument-hint: "<domain>/<topic-slug> and what it should cover"
---

# Add a kb topic

Request: $ARGUMENTS. If the domain, slug or scope is unclear, ask before researching.

Read these sections of the `kb/_self/` docs first, not the whole docs, in one command (`selfdoc.py section` prints the section under each heading with its line numbers). The layout, ids and licence table are in the steps below; the commands are spelled out there too:

```
python3 _tools/selfdoc.py section maintaining "Conduct for changes" content-rules "Facts and tags" content-rules "CODE: what the implementation does" content-rules "SNIPPET: a code example with evidence" content-rules "Ledgers and retrieval data" content-rules "Licensing and privacy" git.md "Workflow"
```

What each gives: `maintaining "Conduct for changes"` the gate, commit messages; `git "Workflow"` commits and pushes.

`AGENTS.md` covers lookups only.

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): the shared permission rules match single commands, so a chained command asks for approval or is refused in a headless run.

## 1. Avoid duplicates
- `python3 _tools/rag.py pack "<what the topic covers>"` (a `good` verdict names the article that already has it), `python3 _tools/rag.py search "<key terms>" -k 10` and `python3 _tools/rag.py topics <domain>`.
- If an existing topic covers it, propose extending that topic instead, and stop until the user decides. The rules for extending versus a new topic, and for where a new one goes, are in `/kb-research` step 2.
- Use an existing domain directory when one fits: the domain of the article that will link to the new topic. Never create a new top-level directory without the user's decision. Slug: lowercase, hyphenated.

## 2. Research official sources
- Microsoft: `microsoft_docs_search` then `microsoft_docs_fetch`. Claude Code: `search_claude_code_docs`. MCP: `search_model_context_protocol`. Otherwise vendor docs, release notes, source repos. See `agents/doc-lookup-sources.md` for what is stable.
- Never call `submit_feedback`.
- Prefer a url pinned at a commit or version when one exists.
- Read the full page before citing it (`microsoft_docs_fetch` for Learn; for other sites, fetch the page and keep the key sentence verbatim, at most 25 words, for the report). Cite the page the sentence is on; a fact whose sentence you cannot find is `[UNK]`, logged in `_gaps.md`.
- Official sources give `DOC` facts. What you read in source code rather than documentation is `CODE`, cited at a tag or commit url with a `path#symbol` pointer (`[CODE S-id: src/settings.rs#DEFAULT_SELECTORS]`): implementation, which can change in any release. A non-official source is `COMMUNITY` and is never the only evidence for a DOC fact. Unconfirmed items are `UNK`.
- A code example is a `SNIPPET:` bullet right above its fenced block: `- SNIPPET: <what it does>; context: <versions, prerequisites>; checked: no|syntax|run [DER S1: parameters from ...]`. It needs an evidence tag (not `UNK`), placeholders only, and `checked: syntax` only when you parsed it (json, toml and python blocks are parsed by the lint).

## 3. Add sources first
Add one row per source to `_sources.csv` (`id,url,title,publisher,licence,reuse,retrieved_utc,version_or_date,artifact_sha256,used_in,superseded_by`) with `python3 _tools/kbid.py add <URL> --title T --publisher P --licence L --reuse R [--version V] [--sha256 H] [--root NAME]`. Never append a row with a CSV writer or by hand.
- `add` computes the id, writes the row through a CSV writer (quoting commas), sets `retrieved_utc` to today (`YYYY-MM-DD`), leaves `used_in` (`build_index.py` fills it, step 5) and `superseded_by` empty, and prints the `S-xxxxxxxx` id to cite. Never invent an id or take "the next number": the id is a hash of the url, so parallel writers do not collide. A url already in the root with the same fields changes nothing and prints its id; one with different fields exits 2 (legacy `S<number>` ids stay valid): reuse the existing row's id.
- `python3 _tools/kbid.py url <URL>` only prints the id, and says if the url has a row; use it to look an id up before writing.
- `--licence` and `--reuse` are required (`check.py` rejects an empty licence or a `reuse` outside `copy`, `quote`, `paraphrase`, `unknown`; meanings in `kb/_self/content-rules.md`). Copy an existing row's pair for the same host or repository (`python3 _tools/rag.py src <id>`); else read the licence where it is stated (the repository's LICENSE, the page footer, the site's terms page), not a fetch tool's summary of it:
  - Microsoft Learn page (incl. fetched through the MCP server): the page's `github_feedback_content_git_url` meta tag names its public mirror. A live mirror with a LICENSE: `CC BY 4.0 (public mirror MicrosoftDocs/<repo>)` (or its licence), `copy`. None, private or archived: `Microsoft Learn terms of use (...why...)`, `quote`.
  - MicrosoftDocs GitHub file at a commit: `CC BY 4.0 (MicrosoftDocs/<repo> LICENSE; code MIT)` (entra-docs: `MIT`), `copy`.
  - Anthropic docs and site: `Anthropic terms (no open licence)`, `quote`.
  - Open-source repository or spec: its SPDX id (`MIT`, `Apache-2.0`, ...), `copy`; NC, ND or source-available licences (BUSL-1.1): `quote`.
  - Vendor pages, blogs, forums, registries with no open licence: the terms' name, `quote`. CIS and ISO: `paraphrase`.
  - Terms you could not read (blocked, JS-only, no statement found and no default applies): say so in `licence`, `unknown`.
- `--version` is the row's `version_or_date`: the page's own version or date when shown (`ms.date`, release tag), else `retrieved <date>`. `--sha256` is `artifact_sha256`, for a pinned artifact.

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
- Each Facts bullet ends in exactly one tag: `[DOC S-k3f7q2zd]`, `[CODE S-k3f7q2zd: path#symbol]`, `[DER S1, S-k3f7q2zd]` (show the derivation), `[COMMUNITY S9]` or `[UNK]`.
- Our own words. Quotes of 25 words or fewer; a longer verbatim copy only from a `copy` source, with attribution. No quotes from a `paraphrase` or `unknown` source (CIS, ISO).
- Placeholders only: `PL-LT-00123`, `PL-SRV-0042`, `corp.example.com`, tenant `00000000-0000-0000-0000-000000000000`, `jan.kowalski`.
- Large tables go in `<domain>/<slug>.csv` beside the article (listed automatically). Data under another name or in a subdirectory goes in `files:` (kb-root paths; a directory ends in `/`).
- `status: partial` when anything is `UNK`.
- `priority`: the research order, not importance (`kb/_self/content-rules.md`). A new topic gets the priority the user gives, else `P3`.

## 5. Register and log
- Run `python3 _tools/build_index.py`. It adds the topic's row to `_coverage.csv` and the root's `_coverage.md` table (ordered by domain, priority, topic id; `n_sources` = ids in the `sources:` header) and fills `used_in` in `_sources.csv`. Never edit those by hand.
- Failed lookups go to `_gaps.md` (what, where you looked). Disagreements go to `_conflicts.md` with both sources. End each new entry with `(topic: <domain>/<slug>)`.
- Retrieval data (`kb/_self/content-rules.md`): if code that uses the product has distinctive names (class names, API routes, library or package names, permission scopes), add `signal,<domain>/<slug>` rows to `kb/public/_retrieval/signals.csv`, so `topics-for` maps code to the topic; if the product has other names or abbreviations, add `term,canonical` rows to `_tools/aliases.csv` (term lowercase; reuse an existing canonical). Check with `python3 _tools/rag.py topics-for --keywords "<a signal>"`.

## 6. Check and report
- `python3 _tools/check.py` must end `errors=0`. Then `python3 .claude/skills/kb-verify/lint.py <domain>/<slug>` must report `errors=0`.
- `python3 _tools/rag.py pack "<a question the topic answers>"` finds the new article, and `python3 _tools/rag.py eval` still passes every question (a new article can outrank the expected one).
- `python3 _tools/tests.py` must pass (leak scan, signals and aliases tables).
- Report the files created, the fact count by tag, the signal and alias rows added, and the open `UNK` items. Do not commit unless asked.
