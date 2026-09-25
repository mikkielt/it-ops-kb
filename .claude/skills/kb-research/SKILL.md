---
name: kb-research
description: Research a question on the web in the context of what it-ops-kb already covers - map the related topics, gaps and conflicts first, research only what is missing from official sources, then extend the existing topics (or add one), record a tagged answer in _answers.md and pass the checks. Use when the user asks to research, investigate or compare something related to topics in the kb.
disable-model-invocation: true
argument-hint: "<question or subject, optionally with the angle, e.g. 'X and how agents can use it'>"
---

# Research within the kb's context

Question: $ARGUMENTS. If it is empty or too broad to answer in one pass, ask for the angle before starting.

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): the shared permission rules match single commands, so a chained command asks for approval or is refused in a headless run.

## 1. Map what the kb already knows (before any web search)
- Split the question into its subjects and angles (e.g. product, sync/integration, use by agents, security).
- For each, run `python3 _tools/rag.py search "<keywords>" -k 8 -u` with 2-3 phrasings, then once with `--index` to include `_answers.md`, `_gaps.md` and `_conflicts.md`. Note the `note:` lines: words "not found anywhere" are what the kb lacks.
- `python3 _tools/rag.py topics <domain>` for the likely domains. Read the anchor articles in full (`python3 _tools/rag.py show <path>:1 -n 200`).
- Write down a short context map in your notes, and keep it for the report:
  - anchor topics (the existing articles the answer belongs to) and the facts in them that already answer parts of the question, with ids and tags;
  - related `UNK` items, gaps and conflicts;
  - the kb's own frame for this subject: the recurring design constraints in those articles (e.g. on-prem plus cloud estate, tiered approval, secrets never in argv/env, placeholders only). The research must answer inside that frame.

## 2. Plan
- List at most 8 sub-questions, each tied to an anchor topic (or to a proposed new topic when none fits) and each answering something the map shows is missing, `UNK`, stale or contested.
- Leave out what the kb already answers with `DOC` facts unless you suspect it is outdated; then re-verify it rather than re-research it.

## 3. Research
- Official sources first, most specific first:
  - Microsoft: `microsoft_docs_search` then `microsoft_docs_fetch`. Claude Code: `search_claude_code_docs`. MCP spec: `search_model_context_protocol`.
  - Other vendors and open-source projects: WebSearch to find the vendor's own docs, release notes, API reference or repository, then WebFetch the page. Prefer a url pinned to a version, tag or commit.
  - `agents/doc-lookup-sources.md` lists the stable lookup sources.
- Record each product's or feature's status as the vendor states it (GA, preview, beta, deprecated, end of support) in the fact itself. A preview feature can be recorded, but say "preview" in the fact and never present it as the recommended path.
- Blogs, forums, vendor marketing and AI-generated wikis are `COMMUNITY`: a lead, never the only evidence for a `DOC` fact. Integrations that a third party claims but the vendor does not document are `COMMUNITY` or `UNK`.
- Compare what you find with the existing facts. A disagreement goes to `_conflicts.md` with both sources. Do not overwrite an older fact without recording why.
- Never call `submit_feedback`, sign up for anything, install software, or run a vendor CLI that changes state. Reading public docs only.

## 4. Write
Follow the contract in README.md and `.claude/skills/kb-add-topic/SKILL.md` (source rows first, written with Python's `csv` module; one tag per fact; licence strings; placeholders only).
- Extending an anchor topic: add bullets to its Facts section, add the new ids to its `sources:` header, update `retrieved_utc` and, if it changed, `status`; update its row in `_coverage.csv` and the README table (`n_sources` = ids in the header).
- New subject with no anchor: create the topic as `/kb-add-topic` describes (priority `P3` unless the user gives one), and link it from the anchor's Reference section.
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
- New source rows take their id from `python3 _tools/kbid.py url <URL>`; never invent one.
- Failed lookups go to `_gaps.md` under the anchor topic's heading: what you looked for and where.

## 5. Check
- `python3 _tools/check.py` must end `errors=0`.
- `python3 .claude/skills/kb-verify/lint.py <each topic you edited or created>` must add no errors.
- `python3 _tools/tests.py` must end `OK`. It includes the leak scan: no real tenant ids, hostnames, addresses or tokens.

## 6. Report
- The context map in brief: anchor topics and what the kb already knew.
- What is new: facts added per topic, with a count by tag, new source ids, the `QK-<slug>` answer id.
- The answer to the question in a few lines, with the vendor status (GA/preview) of every product or feature it relies on.
- Open items (`UNK`), conflicts found, and anything the user must decide.
- Do not commit unless asked.
