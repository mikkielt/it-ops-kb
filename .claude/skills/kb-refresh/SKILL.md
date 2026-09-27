---
name: kb-refresh
description: Use when the user asks to refresh, re-verify, update or fix facts in an existing it-ops-kb topic, directory, file or source id, or says a source changed: diffs the sources and updates the facts, source rows and logs.
argument-hint: "<topic | directory | file | S-id>"
---

# Refresh part of it-ops-kb

Target: $ARGUMENTS. If empty, ask which topic, directory or file. Never refresh the whole kb unasked: a full run is about 20 minutes of network traffic.

Read `kb/_self/maintaining.md` first, then the `kb/_self/` files this skill relies on: `kb/_self/content-rules.md` (what to write), `kb/_self/tools.md` (the commands) and `kb/_self/git.md` (commits and pushes). `AGENTS.md` covers lookups only.

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): the shared permission rules match single commands, so a chained command asks for approval or is refused in a headless run.

## 1. Pick the selection flag
- Topic id (e.g. `auth/kerberos`): `--topic auth/kerberos`
- Directory (e.g. `dsc`): `--dir dsc`
- File: `--file auth/kerberos.md`
- Source id: `--source S1208` or `--source S-k3f7q2zd`
Flags repeat and combine. `--older-than DAYS` skips recently fetched sources.

## 2. See what changed
1. `python3 _tools/fetch.py --status <selection>`: last fetch and change dates.
2. `python3 _tools/fetch.py --diff <selection> --full --max-lines 200`
   - Exit 0: nothing changed. 1: something changed. 2: a fetch or the selection failed.
   - `NEW` is the first fetch: baseline only, unless the source row recorded a hash at retrieval. Such a live page usually reports `CHANGED` with "no earlier snapshot"; then compare the page with the kb facts by reading it (`microsoft_docs_fetch` for Learn pages).
   - A url pinned to a commit or release (e.g. `raw.githubusercontent.com/.../<sha>/...`) never changes, so `--diff` can only say `NEW` or `UNCHANGED`. To learn whether the facts are still current, read the live page it was taken from (for MicrosoftDocs files, the matching learn.microsoft.com page) and compare. If the upstream file changed, add a new source row for the new url (e.g. the file at the new commit), set the old row's `superseded_by` to the new id, and re-point the citations of the facts you re-verified to the new id. Keep the old row as the historical source; never edit its url.
   - This saves the fetch date to `_fetch_state.csv` and snapshots to `_cache/` (not committed). Use `--no-save` to look without moving the baseline.
3. For pinned artifacts (rows with `artifact_sha256`), use `python3 _tools/fetch.py --verify` only if the user asks; those urls are fixed commits and do not drift.

## 3. Update the kb
For every changed source, find the facts citing it: `python3 _tools/rag.py src S1234 --cited` (the row and every line that names the id).
- Fact still true: leave it.
- Fact changed: rewrite it from the new text, same tag, same id. Update that source's `retrieved_utc` and `version_or_date` in `_sources.csv`.
- New page or url: add a new source row with the id from `python3 _tools/kbid.py url <URL>` (a hash of the url; never invent one or take the next number; reuse the existing id if the url is already there) and cite it.
- Replaced source (new commit or moved page): new row as above, old row's `superseded_by` = the new id, citations re-pointed. `check.py` rejects an unknown `superseded_by` id or a cycle.
- Sources now disagree: record both sides in `_conflicts.md`, ending `(topic: <domain>/<slug>)`.
- Page gone (404) or content withdrawn: mark the fact `[UNK]`, and log what was tried in `_gaps.md`, ending `(topic: <domain>/<slug>)`.
- Update the article's `retrieved_utc`, and its `status` if it changed. Then run `python3 _tools/build_index.py`: it regenerates `_coverage.csv`, the `_coverage.md` row and `used_in` (never edit those by hand).
- Rewording a fact changes its doc2query key: `python3 _tools/doc2query.py stale` lists the orphaned keys; `python3 _tools/doc2query.py prune` removes their rows (regenerate only where real lookups miss, `kb/_self/doc2query.md`).
Follow the licensing rules in `kb/_self/content-rules.md`: each source row's `reuse` class says what its text allows (quotes of 25 words or fewer from `quote`, verbatim copies only from `copy`); a new row carries `licence` and `reuse` as `/kb-add-topic` step 3 describes.

## 4. Check and report
- `python3 _tools/check.py` must end `errors=0`. Run `python3 .claude/skills/kb-verify/lint.py <paths you edited>`.
- When facts changed: `python3 _tools/doc2query.py stale` prints `stale=0`, `python3 _tools/rag.py eval` passes every question, and `python3 _tools/tests.py` passes.
- A targeted `--diff` writes `_fetch_state.csv` for the sources it checked. Commit that file with the refresh it explains, even when no fact changed: it records when those sources were last verified. (Only a whole-kb baseline is left to the maintainer.)
- When the user asks you to commit: one commit per refreshed selection, with the source rows, the facts citing them and `_fetch_state.csv` together. If the refresh re-read the sources and confirmed the facts current (changed or not), mark it: `KB_VERIFIED=<today, YYYY-MM-DD> git commit ...` (or `git commit --trailer "KB-Verified: <today>"`); the hook (`python3 _tools/kbgit.py install-hooks`) adds the other KB-* trailers. Check them with `git log -1 --format=%B`. A whole-kb verification is `/kb-census`, which ends with the census tag.
- To see when a fact or source last changed: `python3 _tools/kbgit.py log S1234` and `python3 _tools/kbgit.py blame <path:line>`.
- Report: sources checked, changed, errors; the facts you edited (`path:line`, old -> new); anything left for a human. Do not commit unless asked.
