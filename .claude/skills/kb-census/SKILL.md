---
name: kb-census
description: Use when the user asks for a census, a full re-verification or to confirm or refresh all it-ops-kb sources: mechanical checks of every source, reading the undecided ones, dating only what was confirmed, a sample check, the census tag.
argument-hint: "[YYYY-MM-DD, default today] [--resume]"
---

# Census of it-ops-kb

Census date: the argument, else today (`YYYY-MM-DD`). `--resume`: continue from the existing `kb/public/_census/<date>.csv` (skip phases done: its `outcome` column shows what phase 2 already read).

Read these sections of the `kb/_self/` docs first, not the whole docs, in one command (`selfdoc.py section` prints the section under each heading with its line numbers). The commands are spelled out in the phases below:

```
python3 _tools/selfdoc.py section maintaining "Conduct for changes" content-rules "Facts and tags" content-rules "Ledgers and retrieval data" content-rules "Licensing and privacy" git "Workflow" git "Commit trailers"
```

What each gives: `maintaining "Conduct for changes"` the gate, commit messages; `git "Workflow"` the gate, the census tag; `git "Commit trailers"` `KB-Verified`.

`AGENTS.md` covers lookups only.

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): the shared permission rules match single commands.

Rules that hold throughout:
- "Refreshed" means **confirmed up to date**: a source's `retrieved_utc` moves only after its content was compared (phase 0: unchanged by its provider's signal, or every fact citing it found word for word in its anchor's passage; phase 1 OK) or read and matched against the facts citing it (phase 2). Never bump a date to make the census look complete.
- A pinned source whose upstream changed gets a **new source row** (the file at the new commit or release; written with `python3 _tools/kbid.py add <URL> --title T --publisher P --licence L --reuse R --version V`, which prints the id), the re-verified citations point to it, and the old row's `superseded_by` names it. Old rows are never edited in place or deleted.
- `MicrosoftDocs/memdocs` is archived: its pins are re-sourced to the live Learn page (new row with the Learn url, `version_or_date` recording the page's `git_commit_id`/`updated_at`).
- Read the full page before confirming or changing a fact (`microsoft_docs_fetch` for Learn, the `.mdx` page for Claude Code docs, git for pinned files). Paraphrase Learn text (quotes of 25 words or fewer). Placeholders only.
- Never call `submit_feedback`. Never `--force` or `--no-verify`. One commit per logical step, with `--trailer "KB-Verified: <date>"` on commits that confirm sources.

## Phase 0: fact diff (no model)
1. `python3 _tools/factdiff.py detect --date <date> --sitemaps` (every source; about 45 minutes at one request per 1.1 s per host, Learn being most of it). Each source is checked by its provider's cheapest reliable signal (`_tools/providers.csv`), then each fact of a changed, moved or gone source is resolved against its anchor. It writes `kb/public/_census/factdiff-<date>.csv`, the detection state in `_fetch_state.csv` and the snapshots of changed `copy` sources. Exit 1 only means some facts need review.
2. `python3 _tools/factdiff.py apply kb/public/_census/factdiff-<date>.csv --date <date> --dry-run`, then with `--commit` instead of `--dry-run`: sources that did not change, or whose every fact was found word for word, are confirmed and dated, facts found word for word on another page are re-pointed to a new source row, and the result is committed with `KB-Verified: <date>`. No model reads any of it. Run the gate before pushing, as for any commit.
3. `python3 _tools/factdiff.py review kb/public/_census/factdiff-<date>.csv` lists what is left for phase 2: each fact with its old and new passage (never the whole page).

## Phase 1: mechanical verdicts for the rest (no judgment)
1. `python3 _tools/census.py check --date <date> --factdiff kb/public/_census/factdiff-<date>.csv` (about a minute with warm clones; clones go to `_cache/census/repos/`). It writes `kb/public/_census/<date>.csv` with one bucket per source: OK, CHANGED, GONE, NEWER-VERSION, NEEDS-READING, and the evidence (commit ids, dates, versions). The method per kind is in `census.py`'s docstring.
2. `python3 _tools/census.py summary kb/public/_census/<date>.csv`. NEEDS-READING with note `blocked` means this environment's network policy denied the host: tell the user which hosts (the environment's network settings can allow them) and continue with the rest; those sources stay unconfirmed.
3. Look at the non-OK rows for mechanical false positives before any reading (a monorepo tag family, a moved url, a shallow clone). Fix `census.py` if the rule is wrong (with a test in `_tools/test_census.py`), never the log by hand, and rerun check.
4. Commit the log: `python3 _tools/build_index.py`, the gate, then `git add kb/public/_census/<date>.csv` and commit `docs(kb): census <date> phase 1 verdicts`.

## Phase 2: read what the checks could not decide
Scope: every row whose bucket is not OK and whose note is not `blocked`.
1. Group the rows by the domain of the files citing them (`used_in`), so each group owns a disjoint set of article files (a source cited in two groups goes to the group with most of its citations; its other files are listed as foreign).
2. Start one subagent per group, in parallel, with this brief (fill in the group's rows and files):
   > You re-verify it-ops-kb sources for the census of <date>. Your files (edit only these): <list>. Sources: <rows: id, url, bucket, evidence, used_in>.
   > For each source whose evidence names `factdiff.py review`, start from `python3 _tools/factdiff.py review kb/public/_census/factdiff-<date>.csv --source <id>`: each fact with its old and new passage; judge each as supported, contradicted or not enough information from those passages, and read the page only when they do not settle it. For a source gone with no successor (`dead` facts, nothing moved), report it: the orchestrator runs `python3 _tools/factdiff.py dead <log> --source <id>`, which turns the facts that cited only it into `[UNK]`, adds the `_gaps.md` entries and marks the row dead with its last Wayback capture.
   > For each other source: read it in full as it is now (for a pinned file, `git -C _cache/census/repos/<repo>.git show <tip>:<path>` and `git diff <pin> <tip> -- <path>`; for a page, fetch it; for Learn, microsoft_docs_fetch). Then check every fact in your files that cites it (`python3 _tools/rag.py src <id> --cited`).
   > - All facts still hold: outcome `confirmed`.
   > - A fact changed: rewrite it from the new text (same tag). A live page: keep the id, outcome `updated`. A pinned file or release: propose a new row for the new pinned url (the orchestrator writes it with `python3 _tools/kbid.py add`; `python3 _tools/kbid.py url <URL>` gives its id), re-point the facts you re-verified, outcome `superseded` with the new id in the note.
   > - Gone or withdrawn: mark the facts `[UNK]`, outcome `gone`, and give a `_gaps.md` bullet (what, where you looked, ending `(topic: <domain>/<slug>)`).
   > - Cannot read it: outcome `unconfirmed` with the reason; change nothing.
   > - Sources that now disagree with a kb fact you cannot settle: give a `_conflicts.md` bullet ending `(topic: <domain>/<slug>)`.
   > Update each edited article's `sources:` header and `status`. Do not touch `_sources.csv`, `_gaps.md`, `_conflicts.md`, the index or any file outside your list, and do not commit. Facts in foreign files that need an edit: describe them.
   > Return JSON only: {"outcomes": [{"id", "outcome", "note"}], "new_rows": [{all _sources.csv columns}], "superseded": {"old id": "new id"}, "gaps": [{"topic", "text"}], "conflicts": [{"topic", "text"}], "foreign_edits": [{"file", "line", "change"}]}.
3. Apply the results yourself, one group at a time: add each of `new_rows` with `python3 _tools/kbid.py add <url> --title T --publisher P --licence L --reuse R [--version V] [--sha256 H]` (never a CSV writer; it sets `retrieved_utc` to today, the census day), set `superseded_by` on the old rows, add the gap and conflict bullets under the topic headings, make the foreign edits, then `python3 _tools/census.py record kb/public/_census/<date>.csv --from <outcomes.json>`.
4. Re-anchor what phase 2 rewrote: `python3 _tools/factdiff.py anchor --file <each edited file>` (a reworded fact has a new key).
5. Per group: `python3 _tools/build_index.py`, `python3 _tools/doc2query.py stale` (reworded facts orphan their expansion keys: `python3 _tools/doc2query.py prune` removes them), the gate (`check.py`, `build_index.py --check`, `kbgit.py fix --check`, `tests.py`, which runs `rag.py eval`), and a commit (`docs(kb): census <date>: <group>`, `git commit --trailer "KB-Verified: <date>"`). Sources with hash ids never collide across groups; `_sources.csv` is only ever written by you.

## Phase 3: dates, by script
1. `python3 _tools/census.py confirm kb/public/_census/<date>.csv --date <date> --dry-run`, then without `--dry-run`. It sets `retrieved_utc` and a `confirmed <date>: <proof>` suffix in `version_or_date` for confirmed sources (bucket OK, or outcome confirmed/updated), `checked_utc` in `_fetch_state.csv`, and `retrieved_utc` of every article whose sources all carry the date.
2. Decisions whose context the census broke: `python3 _tools/kbdecide.py sweep --dry-run --date <date>`, then `sweep --date <date>` without `--dry-run`. It invalidates them and prints `ID relink ROOT fact:KEY PATH:LINE text` for a reworded fact; report each invalidation and relink line in the census report (`kbdecide.py relink ID --fact PATH:LINE` repoints a decision once the fact is the right one).
3. `python3 _tools/build_index.py`, the gate, and commit `docs(kb): census <date>: confirmed dates` with `git commit --trailer "KB-Verified: <date>"`.

## Phase 4: independent check, then the tag
1. `python3 _tools/census.py sample kb/public/_census/<date>.csv --changed 0.10 --ok 0.05 --seed <any>`.
2. Give the sample to a fresh subagent that did not do phase 2: for each row it reads the source and the citing facts and answers agree/disagree with a reason. It changes nothing.
3. Every disagreement is a finding: fix it (and look for the same mistake in its group), then rerun this phase's sample with another seed.
4. Report the counts: checked, agreed, disagreed, fixed.
5. The tag means "the kb was confirmed current as of <date>". Create it only when no source that a fact cites is left unconfirmed (summary: no `blocked`, no `unconfirmed`, no unread NEEDS-READING, except rows `python3 _tools/rag.py src <id> --cited` shows cited by no article or data line, only in front matter or ledger notes; file those as one backlog story with `/kb-backlog`): `python3 _tools/kbgit.py tag-census <date>`, then `git push origin census-<date>` if the user asked to push. Otherwise do not tag: report what is left and why, and file it as backlog items with `/kb-backlog`.

## Report
The bucket counts, the phase 2 outcomes per group (confirmed, updated, superseded with old -> new ids, gone, unconfirmed), the decisions the sweep invalidated and its relink lines, the sample result, the hosts that were blocked, the commits, and whether the tag was created.
