---
name: kb-research
description: Use when the user asks to research, investigate or compare something for it-ops-kb, or to extend what the kb says about a subject, or to work the query log's gaps (--queue): maps existing topics and gaps first, researches only what is missing from official sources, extends topics, records a tagged answer.
argument-hint: "<question or subject, optionally with the angle, e.g. 'X and how agents can use it'> | --queue [N]"
---

# Research within the kb's context

Question: $ARGUMENTS. If it is empty or too broad to answer in one pass, ask for the angle before starting. `--queue [N]` works the query log's gaps instead (next section).

Read these sections of the `kb/_self/` docs first, not the whole docs, in one command (`selfdoc.py section` prints the section under each heading with its line numbers). The commands are spelled out in the steps below:

```
python3 _tools/selfdoc.py section maintaining "Conduct for changes" content-rules "Facts and tags" content-rules "Ids" content-rules "Ledgers and retrieval data" content-rules "Licensing and privacy" git "Workflow"
```

What each gives: `maintaining "Conduct for changes"` the gate, commit messages; `content-rules "Ids"` source and answer ids, CSV writing; `git "Workflow"` commits and pushes.

`AGENTS.md` covers lookups only.

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): the shared permission rules match single commands, so a chained command asks for approval or is refused in a headless run.

## The query log's queue (`--queue [N]`)
- `python3 _tools/querylog.py queue N` (default 1): the open gap findings of `kb/_querylog`, each re-run with `pack` first (one that passes now is recorded `fixed-since` and left out), by topic, most-asked first. Each gap prints its question, its `_gaps.md` entry (`path:line`) and its finding id (`F-...`). Nothing listed: say so and stop.
- Each gap is one question: run steps 1 to 6 below on it, within its topic (the entry's `(topic: ...)`).
- Then close its `_gaps.md` entry by the content rules and record it (the queue's rules: `python3 _tools/selfdoc.py section querylog "The research queue"`):
  - settled: a `  - Resolved <date>: <what settles it, with source ids> (topic: <domain>/<slug>)` line under the entry, then `python3 _tools/querylog.py close F-... --claim`;
  - not settled by official sources: `python3 _tools/querylog.py close F-... --tried "<what was tried, where, and what it still needs>"`, which writes the dated `Tried` note under the entry; the gap stays out of the queue until the note is older than `QUEUE_TRIED_DAYS`.
- `python3 _tools/querylog.py check` must print `problems=0`. The report lists each gap's finding id and how it closed.

## 1. Map what the kb already knows (before any web search)
- Split the question into its subjects and angles (e.g. product, sync/integration, use by agents, security).
- Pack them in one batch: `python3 _tools/rag.py pack -q "<sub-question>" -q "<sub-question>"` (up to 6 parts; each part's `coverage:` line and "not in the kb" words show what the kb lacks; `(no tag)` lines are untagged article content). Then once `python3 _tools/rag.py search "<keywords>" --index` to include `_answers.md`, `_gaps.md` and `_conflicts.md`. `python3 _tools/rag.py audit <domain> --entries` lists the open gaps and conflicts already linked to the anchor topics.
- `python3 _tools/rag.py topics <domain>` for the likely domains. Read the anchor articles in full (`python3 _tools/rag.py show <path>:1 -n 200`).
- Write down a short context map in your notes, and keep it for the report:
  - anchor topics (the existing articles the answer belongs to) and the facts in them that already answer parts of the question, with ids and tags;
  - related `UNK` items, gaps and conflicts;
  - the kb's own frame for this subject: the recurring design constraints in those articles (e.g. on-prem plus cloud estate, tiered approval, secrets never in argv/env, placeholders only). The research must answer inside that frame.

## 2. Plan
- List at most 8 sub-questions, each tied to an anchor topic (or to a proposed new topic when none fits) and each answering something the map shows is missing, `UNK`, stale or contested.
- Leave out what the kb already answers with `DOC` facts unless you suspect it is outdated; then re-verify it rather than re-research it.
- Decide per sub-question where its facts will live, with these rules:
  - **Extend** the anchor topic when the facts are about the product or feature the article is about (its title and `applies_to`), close one of its `UNK` items or gaps, or number fewer than about five. Most research extends.
  - **New topic** only for a distinct product, feature or protocol with its own official documentation, when no article's scope covers it, you expect at least five `DOC` facts, and folding it in would make an article cover two subjects. Link it from the anchor's Reference section, and the anchor from it.
  - **Where a new topic goes**: in the domain directory of the anchor that will link to it (a Dataverse sync topic reached from the Power BI gateway articles goes in `powerbi/`). If no existing domain fits, do not create a new top-level directory: a new domain changes the README's domain list, `AGENTS.md` and the index. Propose one to the user and stop for that sub-question (record it under "Open" in the answer).
  - Never create a topic that only restates facts the kb already has elsewhere; cite those facts from the answer instead.

## 3. Research
- Official sources first, most specific first:
  - The three docs servers through the `kb` server's cached tools, so a search or page read in the last 7 days costs no second call: `docs_search` with `server` `microsoft-learn`, `claude-code-docs` or `mcp-docs`, then `docs_fetch` on the page (`kb/_self/tools.md`, the `kb_mcp.py` row). Only when those tools are missing (a server started with `--roots`, or `KB_LIVE_DOCS=0`) call the servers directly: Microsoft `microsoft_docs_search` then `microsoft_docs_fetch`, Claude Code `search_claude_code_docs`, MCP spec `search_model_context_protocol`.
  - Other vendors and open-source projects: WebSearch to find the vendor's own docs, release notes, API reference or repository, then read the page by its family's route. Prefer a url pinned to a version, tag or commit.
  - Read by route, not by the HTML page (`kb/_self/web-sources.md`, "Routes by family"): a GitHub or GitLab blob as the raw file at the same ref; a site's `.md` page or `llms.txt` where it publishes them; PyPI as its JSON; a PDF with `curl` and the Read tool. A host that keeps failing (403, bot page, empty result) goes in the report as a staging candidate for that file's runbook.
  - `agents/doc-lookup-sources.md` lists the stable lookup sources.
- **Read the full page before you cite it.** A search result is a pointer, not evidence: its snippet may come from another page, an older version or a neighbouring section.
  - Microsoft Learn: `docs_fetch` (`server` `microsoft-learn`, `target` the url you will cite), and find the sentence in the fetched text.
  - Claude Code and MCP docs: read the section, not just the search hit: `docs_fetch` (`server` `claude-code-docs` or `mcp-docs`) with `target` `rg -n -C 8 "<words>" <page>.mdx` (or `sed -n` a line range); `cat` the whole page only when the section cannot be found.
  - Any other site: curl the page (WebFetch only to locate the passage: it returns a summary, not the text) and copy the key sentence verbatim, at most 25 words, into your notes with its url; the report lists each new fact with that quote.
  - The source row is the page where the sentence is, not the page that linked to it. If you cannot find the sentence on any page you can cite, the fact is not `DOC`: drop it, or keep it as `[UNK]` and log where you looked in `_gaps.md`. Numbers (limits, sizes, latencies, dates) need the exact sentence every time.
- Record each product's or feature's status as the vendor states it (GA, preview, beta, deprecated, end of support) in the fact itself. A preview feature can be recorded, but say "preview" in the fact and never present it as the recommended path.
- Blogs, forums, vendor marketing and AI-generated wikis are `COMMUNITY`: a lead, never the only evidence for a `DOC` fact. Integrations that a third party claims but the vendor does not document are `COMMUNITY` or `UNK`.
- Compare what you find with the existing facts. A disagreement goes to `_conflicts.md` with both sources. Do not overwrite an older fact without recording why.
- Never call `submit_feedback`, sign up for anything, install software, or run a vendor CLI that changes state. Reading public docs only.

## 4. Write
The contract in brief (the sections read above hold the rest):
- Source rows first, in `_sources.csv` (`id,url,title,publisher,licence,reuse,retrieved_utc,version_or_date,artifact_sha256,used_in,superseded_by`), each written with `python3 _tools/kbid.py add <URL> --title T --publisher P --licence L --reuse R [--version V] [--sha256 H] [--root NAME]`, never appended with a CSV writer: it sets `retrieved_utc` to today and leaves `used_in` and `superseded_by` empty; `--version` is the page's own version or date (else `retrieved <date>`).
- `licence` and `reuse` on every row: copy an existing row's pair for the same host or repository (`python3 _tools/rag.py src <id>`), else read the licence where it is stated (the repository's LICENSE, the page footer, the terms page). Microsoft Learn by the "Licensing and privacy" section; Anthropic docs `Anthropic terms (no open licence)`, `quote`; an open-source repository or spec its SPDX id, `copy` (NC, ND or source-available: `quote`); vendor pages, blogs and forums with no open licence the terms' name, `quote`; terms you could not read: say so, `unknown`.
- Each Facts bullet ends in exactly one tag; our own words, quotes of 25 words or fewer; placeholders only; `status: partial` when anything is `UNK`.
- Extending an anchor topic: add bullets to its Facts section, add the new ids to its `sources:` header, update `retrieved_utc` and, if it changed, `status`. Do not edit `_coverage.csv`, the root's `_coverage.md` table or `used_in`: step 5 regenerates them.
- New topic, only where step 2 decided one: create it with `/kb-add-topic <domain>/<slug>` (priority `P3` unless the user gives one) in the domain step 2 chose, and link it from the anchor's Reference section and back.
- "How it fits": implications for this kb's frame (e.g. how an agent should call it, where secrets live, what tier an operation needs) are `DER` facts. State the derivation and the facts it rests on. Do not present a design choice as a vendor fact.
- Add one answer to `_answers.md`, after the last `QK` entry (or at the end, before the `R` sections if there are none):
  ```
  ## QK-<slug>. <the question>
  - <answer bullet> [DOC S...]
  - ...
  - Conclusion: <two or three sentences> [DER S..., S...]
  - Open: <what could not be confirmed> [UNK]
  - See <topic>.md, <topic>.md.

  _Agent: kb-research_
  ```
  `QK-<slug>`: a short lowercase hyphenated slug of the question (e.g. `QK-dataverse-onprem-sync`); `python3 _tools/kbid.py answer "<question>"` suggests one and says if it is taken. Never number answers: parallel writers would pick the same number. `check.py` rejects a duplicate answer id.
- New source rows take their id from `python3 _tools/kbid.py add` (it prints it); `kbid.py url <URL>` looks one up; never invent one.
- Failed lookups go to `_gaps.md` under the anchor topic's heading: what you looked for and where, ending `(topic: <domain>/<slug>)`.
- Retrieval data (the "Ledgers and retrieval data" section): `kb/public/_retrieval/signals.csv` rows for a new topic's code names, `_tools/aliases.csv` rows for a product's other names, and a `kb/public/_retrieval/lookup_eval.csv` row for each step-1 pack that missed an article the kb already had (`none` or `weak` although an article answered it).

## 5. Check
- `python3 _tools/build_index.py` regenerates `_coverage.csv`, the root's `_coverage.md` table and `used_in` from what you wrote.
- `python3 _tools/check.py` must end `errors=0`.
- `python3 .claude/skills/kb-verify/lint.py <each topic you edited or created>` must add no errors.
- `python3 _tools/doc2query.py stale` must print `stale=0`: if you reworded facts that had expansions, `python3 _tools/doc2query.py prune` removes their rows.
- `python3 _tools/rag.py eval`: every question passes (`passed` = `questions`).
- `python3 _tools/tests.py` must pass. It includes the leak scan: no real tenant ids, hostnames, addresses or tokens.

## 6. Report
- The context map in brief: anchor topics and what the kb already knew.
- What is new: facts added per topic, with a count by tag, new source ids, the `QK-<slug>` answer id, and for each new `DOC` fact from a non-Microsoft page the verbatim quote it rests on; rows added to `signals.csv`, `aliases.csv` or `lookup_eval.csv`.
- Where each fact went (extended topic or new topic) and why, per step 2's rules.
- The answer to the question in a few lines, with the vendor status (GA/preview) of every product or feature it relies on.
- Open items (`UNK`), conflicts found, and anything the user must decide.
- Do not commit unless asked.
