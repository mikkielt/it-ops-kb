---
name: kb-refresh
description: Use when the user asks to refresh, re-verify, update or fix facts in an existing it-ops-kb topic, directory, file or source id, or says a source changed: diffs the sources and updates the facts, source rows and logs.
argument-hint: "<topic | directory | file | S-id>"
---

# Refresh part of it-ops-kb

Target: $ARGUMENTS. If empty, ask which topic, directory or file. Never refresh the whole kb unasked: a full run is about 20 minutes of network traffic.

Read these sections of the `kb/_self/` docs first, not the whole docs, in one command (`selfdoc.py section` prints the section under each heading with its line numbers). The commands are spelled out in the steps below:

```
python3 _tools/selfdoc.py section maintaining "Conduct for changes" content-rules "Facts and tags" content-rules "Ids" content-rules "Ledgers and retrieval data" content-rules "Licensing and privacy" git "Workflow" git "Commit trailers"
```

What each gives: `maintaining "Conduct for changes"` the gate, commit messages; `content-rules "Ids"` source ids, replaced sources, CSV writing; `git "Workflow"` commits and pushes; `git "Commit trailers"` `KB-Verified`.

`AGENTS.md` covers lookups only.

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): the shared permission rules match single commands, so a chained command asks for approval or is refused in a headless run.

## 1. Pick the selection flag
- Topic id (e.g. `auth/kerberos`): `--topic auth/kerberos`
- Directory (e.g. `dsc`): `--dir dsc`
- File: `--file auth/kerberos.md`
- Source id: `--source S1208` or `--source S-k3f7q2zd`
Flags repeat and combine. `--older-than DAYS` skips recently fetched sources.

## 2. See what changed
1. `python3 _tools/fetch.py --status <selection>`: last fetch and change dates.
2. Fact diff first (no model): `python3 _tools/factdiff.py detect <selection>` checks each source by its provider's cheapest signal and resolves every fact of a changed, moved or gone source against its anchor. Then `python3 _tools/factdiff.py apply kb/public/_census/factdiff-<today>.csv --dry-run` and, when it shows what you expect, without `--dry-run`: unchanged sources and facts found word for word are confirmed and dated, facts found word for word on another page are re-pointed. `python3 _tools/factdiff.py review kb/public/_census/factdiff-<today>.csv` prints what is left, each fact with its old and new passage: judge each as supported, contradicted or not enough information from those passages (step 3 says what to do), and read the page only when they do not settle it. A source gone with no successor: `python3 _tools/factdiff.py dead <log> --source <id>` (facts that cited only it become `[UNK]`, `_gaps.md` entries, the row marked dead with its last Wayback capture).
3. The low-level text diff, when a passage needs its context: `python3 _tools/fetch.py --diff <selection> --full --max-lines 200`
   - Exit 0: nothing changed. 1: something changed. 2: a fetch or the selection failed.
   - `NEW` is the first fetch: baseline only, unless the source row recorded a hash at retrieval. Such a live page usually reports `CHANGED` with "no earlier snapshot"; then compare the page with the kb facts by reading it (`docs_fetch` with `server` `microsoft-learn` for Learn pages: the `kb` server's cached tool, `kb/_self/tools.md`).
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
- Decisions whose context this broke (a superseded source, a removed article, a reworded fact): `python3 _tools/kbdecide.py sweep --dry-run`, then `sweep` without `--dry-run`. It invalidates them and prints `ID relink ROOT fact:KEY PATH:LINE text` for a fact that was reworded; report each invalidation and relink line (`kbdecide.py relink ID --fact PATH:LINE` repoints a decision once the fact is the right one).
- Update the article's `retrieved_utc`, and its `status` if it changed. Then run `python3 _tools/build_index.py`: it regenerates `_coverage.csv`, the `_coverage.md` row and `used_in` (never edit those by hand).
- A reworded or new fact needs its anchor: `python3 _tools/factdiff.py anchor --file <path>` for each file you edited (`python3 _tools/factdiff.py anchors --stale` must print `stale=0`).
- Rewording a fact changes its doc2query key: `python3 _tools/doc2query.py stale` lists the orphaned keys; `python3 _tools/doc2query.py prune` removes their rows (regenerate only where real lookups miss, `kb/_self/doc2query.md`).
Follow the "Licensing and privacy" section: each source row's `reuse` class says what its text allows (quotes of 25 words or fewer from `quote`, verbatim copies only from `copy`). A new row carries `licence` and `reuse`: copy an existing row's pair for the same host or repository (`python3 _tools/rag.py src <id>`), else read the licence where it is stated (the repository's LICENSE, the page footer, the terms page) and pick the class by that section. Write rows with Python's `csv` module; a new row's `used_in` and `superseded_by` are empty.

## 4. Check and report
- `python3 _tools/check.py` must end `errors=0`. Run `python3 .claude/skills/kb-verify/lint.py <paths you edited>`.
- When facts changed: `python3 _tools/doc2query.py stale` prints `stale=0`, `python3 _tools/rag.py eval` passes every question, and `python3 _tools/tests.py` passes.
- A targeted `--diff` or `detect` writes `_fetch_state.csv` for the sources it checked (`detect` also its log in `_census/` and the snapshots of changed `copy` sources). Commit them with the refresh they explain, even when no fact changed: it records when those sources were last verified. (Only a whole-kb baseline is left to the maintainer.)
- When the user asks you to commit: one commit per refreshed selection, with the source rows, the facts citing them and `_fetch_state.csv` together. If the refresh re-read the sources and confirmed the facts current (changed or not), mark it: `git commit --trailer "KB-Verified: <today, YYYY-MM-DD>"`; the hook (`python3 _tools/kbgit.py install-hooks`) adds the other KB-* trailers. Check them with `git log -1 --format=%B`. A whole-kb verification is `/kb-census`, which ends with the census tag.
- To see when a fact or source last changed: `python3 _tools/kbgit.py log S1234` and `python3 _tools/kbgit.py blame <path:line>`.
- Report: sources checked, changed, errors; the facts you edited (`path:line`, old -> new); anything left for a human. Do not commit unless asked.
