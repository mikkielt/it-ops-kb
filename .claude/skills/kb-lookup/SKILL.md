---
name: kb-lookup
description: Answer a question from the it-ops-kb knowledge base with cited sources (Windows endpoint management - DSC v3, ConfigMgr/MECM, Intune, Autopilot, Entra ID, Active Directory, Graph, GPO, Defender, SQL Server, Power BI, GitLab CI, Ansible, security baselines, identity/auth, Presidio/privacy, MCP, Claude Code, AI agents). Use whenever a question in this repo touches those domains, or the user asks what the kb says. Read-only.
---

# Look up facts in it-ops-kb

Read-only: change no file.

## 1. Search the kb first
- `python3 _tools/rag.py search "<3-8 keywords>" -k 8 -u` returns chunks with `path:line`, the heading, the text and the source urls of each cited id.
- Narrow with `-d <domain>` (e.g. `-d auth`), and try a synonym or the product's own term if the first query misses. `python3 _tools/rag.py topics [DOMAIN]` lists articles.
- The search leaves out root files. Add `--index` to include `_answers.md` (research answers with evidence), `_gaps.md` and `_conflicts.md` when the question is about open items or disagreements.
- Read around a hit before quoting it: `python3 _tools/rag.py show <path>:<line> -n 30`.
- Resolve ids: `python3 _tools/rag.py src S1234`.

## 2. Weigh what you found
Each fact ends in one tag:
- `DOC` official document; `DER` derived from DOC facts (the derivation is shown); `COMMUNITY` non-official; `UNK` not confirmed.
- `UNK` and `COMMUNITY` are leads, never the answer by themselves. Say so.
- Check `_conflicts.md` when sources disagree, and the article's `status` (`partial` means known gaps) and `retrieved_utc`.
- Freshness: `python3 _tools/fetch.py --status --file <path>` shows when its sources were last fetched (`never` is normal).

## 3. Go live only when needed
If the kb has no answer, only `UNK`/`COMMUNITY`, or the user needs the current state, check the official docs through the shared MCP servers:
- Microsoft products: `microsoft_docs_search`, then `microsoft_docs_fetch` on the best url.
- Claude Code: `search_claude_code_docs`. MCP spec: `search_model_context_protocol`.
- Never call `submit_feedback`.
Label that part of the answer "live docs, not in the kb" with the url and today's date. Do not add it to the kb here: suggest `/kb-add-topic` or `/kb-refresh`.

## 4. Answer
- Lead with the answer. Then the supporting facts, each with `path:line`, tag and source id + url.
- State what is unknown or unverified. If neither the kb nor the live docs answer it, say that plainly: no guessing.
- Examples use placeholder names only (`PL-LT-00123`, `corp.example.com`, `jan.kowalski`, tenant `00000000-0000-0000-0000-000000000000`).
