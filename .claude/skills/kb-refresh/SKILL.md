---
name: kb-refresh
description: Check whether the sources behind a kb topic, directory or file have changed, and update the affected facts, source rows and logs. Use when the user asks to refresh, re-verify or update part of it-ops-kb.
disable-model-invocation: true
argument-hint: "<topic | directory | file | S-id>"
---

# Refresh part of it-ops-kb

Target: $ARGUMENTS. If empty, ask which topic, directory or file. Never refresh the whole kb unasked: a full run is about 20 minutes of network traffic.

## 1. Pick the selection flag
- Topic id (e.g. `auth/kerberos`): `--topic auth/kerberos`
- Directory (e.g. `dsc`): `--dir dsc`
- File: `--file auth/kerberos.md`
- Source id: `--source S1208`
Flags repeat and combine. `--older-than DAYS` skips recently fetched sources.

## 2. See what changed
1. `python3 _tools/fetch.py --status <selection>`: last fetch and change dates.
2. `python3 _tools/fetch.py --diff <selection> --full --max-lines 200`
   - Exit 0: nothing changed. 1: something changed. 2: a fetch or the selection failed.
   - `NEW` is the first fetch: baseline only, unless the source row recorded a hash at retrieval. Such a live page usually reports `CHANGED` with "no earlier snapshot"; then compare the page with the kb facts by reading it (`microsoft_docs_fetch` for Learn pages).
   - This saves the fetch date to `_fetch_state.csv` and snapshots to `_cache/` (not committed). Use `--no-save` to look without moving the baseline.
3. For pinned artifacts (rows with `artifact_sha256`), use `python3 _tools/fetch.py --verify` only if the user asks; those urls are fixed commits and do not drift.

## 3. Update the kb
For every changed source, find the facts citing it: `python3 _tools/rag.py search "S1234" -k 20` or grep the id.
- Fact still true: leave it.
- Fact changed: rewrite it from the new text, same tag, same id. Update that source's `retrieved_utc` and `version_or_date` in `_sources.csv`.
- New page or url: add a new source row (next free `S` id, never reuse) and cite it.
- Sources now disagree: record both sides in `_conflicts.md`.
- Page gone (404) or content withdrawn: mark the fact `[UNK]`, and log what was tried in `_gaps.md`.
- Update the article's `retrieved_utc`, and its `status` if it changed. Keep `_coverage.csv` and the README coverage row in step (status, source count).
Follow the README licensing rules: Microsoft Learn text is paraphrased (quotes of 25 words or fewer); verbatim copies only for permissive licences.

## 4. Check and report
- `python3 _tools/check.py` must end `errors=0`. Run `python3 .claude/skills/kb-verify/lint.py <paths you edited>`.
- `_fetch_state.csv` changes belong in the same commit as the facts they explain.
- Report: sources checked, changed, errors; the facts you edited (`path:line`, old -> new); anything left for a human. Do not commit unless asked.
