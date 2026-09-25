---
name: kb-census
description: Confirm that every source in it-ops-kb is still current - mechanical checks of all sources with census.py (pins by git, releases, Learn source files, sitemap dates, links), reading every source they cannot decide, updating or re-sourcing the facts that changed, dating only what was really confirmed, an independent sample check, then the census tag. Use when the user asks for a census, a full re-verification or to "refresh all sources".
disable-model-invocation: true
argument-hint: "[YYYY-MM-DD, default today] [--resume]"
---

# Census of it-ops-kb

Census date: the argument, else today (`YYYY-MM-DD`). `--resume`: continue from the existing `_census/<date>.csv` (skip phases done: its `outcome` column shows what phase 2 already read).

Read `MAINTAINING.md` first: the content rules, tools, git workflow and commit rules this skill relies on (`AGENTS.md` covers lookups only).

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): the shared permission rules match single commands.

Rules that hold throughout:
- "Refreshed" means **confirmed up to date**: a source's `retrieved_utc` moves only after its content was compared (phase 1 OK) or read in full and matched against the facts citing it (phase 2). Never bump a date to make the census look complete.
- A pinned source whose upstream changed gets a **new source row** (the file at the new commit or release; id from `python3 _tools/kbid.py url <URL>`), the re-verified citations point to it, and the old row's `superseded_by` names it. Old rows are never edited in place or deleted.
- `MicrosoftDocs/memdocs` is archived: its pins are re-sourced to the live Learn page (new row with the Learn url, `version_or_date` recording the page's `git_commit_id`/`updated_at`).
- Read the full page before confirming or changing a fact (`microsoft_docs_fetch` for Learn, the `.mdx` page for Claude Code docs, git for pinned files). Paraphrase Learn text (quotes of 25 words or fewer). Placeholders only.
- Never call `submit_feedback`. Never `--force` or `--no-verify`. One commit per logical step, with `KB_VERIFIED=<date>` on commits that confirm sources.

## Phase 0-1: mechanical verdicts (no judgment)
1. `python3 _tools/census.py check --date <date>` (about a minute with warm clones; clones go to `_cache/census/repos/`). It writes `_census/<date>.csv` with one bucket per source: OK, CHANGED, GONE, NEWER-VERSION, NEEDS-READING, and the evidence (commit ids, dates, versions). The method per kind is in `census.py`'s docstring.
2. `python3 _tools/census.py summary _census/<date>.csv`. NEEDS-READING with note `blocked` means this environment's network policy denied the host: tell the user which hosts (the environment's network settings can allow them) and continue with the rest; those sources stay unconfirmed.
3. Look at the non-OK rows for mechanical false positives before any reading (a monorepo tag family, a moved url, a shallow clone). Fix `census.py` if the rule is wrong (with a test in `_tools/test_census.py`), never the log by hand, and rerun check.
4. Commit the log: `python3 _tools/build_index.py`, the gate, then `git add _census/<date>.csv` and commit `docs(kb): census <date> phase 1 verdicts`.

## Phase 2: read what the checks could not decide
Scope: every row whose bucket is not OK and whose note is not `blocked`.
1. Group the rows by the domain of the files citing them (`used_in`), so each group owns a disjoint set of article files (a source cited in two groups goes to the group with most of its citations; its other files are listed as foreign).
2. Start one subagent per group, in parallel, with this brief (fill in the group's rows and files):
   > You re-verify it-ops-kb sources for the census of <date>. Your files (edit only these): <list>. Sources: <rows: id, url, bucket, evidence, used_in>.
   > For each source: read it in full as it is now (for a pinned file, `git -C _cache/census/repos/<repo>.git show <tip>:<path>` and `git diff <pin> <tip> -- <path>`; for a page, fetch it; for Learn, microsoft_docs_fetch). Then check every fact in your files that cites it (`python3 _tools/rag.py src <id> --cited`).
   > - All facts still hold: outcome `confirmed`.
   > - A fact changed: rewrite it from the new text (same tag). A live page: keep the id, outcome `updated`. A pinned file or release: propose a new row for the new pinned url (id from `python3 _tools/kbid.py url <URL>`), re-point the facts you re-verified, outcome `superseded` with the new id in the note.
   > - Gone or withdrawn: mark the facts `[UNK]`, outcome `gone`, and give a `_gaps.md` bullet (what, where you looked, ending `(topic: <domain>/<slug>)`).
   > - Cannot read it: outcome `unconfirmed` with the reason; change nothing.
   > - Sources that now disagree with a kb fact you cannot settle: give a `_conflicts.md` bullet ending `(topic: <domain>/<slug>)`.
   > Update each edited article's `sources:` header and `status`. Do not touch `_sources.csv`, `_gaps.md`, `_conflicts.md`, the index or any file outside your list, and do not commit. Facts in foreign files that need an edit: describe them.
   > Return JSON only: {"outcomes": [{"id", "outcome", "note"}], "new_rows": [{all _sources.csv columns}], "superseded": {"old id": "new id"}, "gaps": [{"topic", "text"}], "conflicts": [{"topic", "text"}], "foreign_edits": [{"file", "line", "change"}]}.
3. Apply the results yourself, one group at a time: append `new_rows` to `_sources.csv` with a CSV writer (`retrieved_utc` = the census date), set `superseded_by` on the old rows, add the gap and conflict bullets under the topic headings, make the foreign edits, then `python3 _tools/census.py record _census/<date>.csv --from <outcomes.json>`.
4. Per group: `python3 _tools/build_index.py`, `python3 _tools/doc2query.py stale` (reworded facts orphan their expansion keys: `python3 _tools/doc2query.py prune` removes them), the gate (`check.py`, `build_index.py --check`, `kbgit.py fix --check`, `tests.py`, which runs `rag.py eval`), and a commit (`docs(kb): census <date>: <group>`, `KB_VERIFIED=<date>`). Sources with hash ids never collide across groups; `_sources.csv` is only ever written by you.

## Phase 3: dates, by script
1. `python3 _tools/census.py confirm _census/<date>.csv --date <date> --dry-run`, then without `--dry-run`. It sets `retrieved_utc` and a `confirmed <date>: <proof>` suffix in `version_or_date` for confirmed sources (bucket OK, or outcome confirmed/updated), `checked_utc` in `_fetch_state.csv`, and `retrieved_utc` of every article whose sources all carry the date.
2. `python3 _tools/build_index.py`, the gate, and commit `docs(kb): census <date>: confirmed dates` with `KB_VERIFIED=<date>`.

## Phase 4: independent check, then the tag
1. `python3 _tools/census.py sample _census/<date>.csv --changed 0.10 --ok 0.05 --seed <any>`.
2. Give the sample to a fresh subagent that did not do phase 2: for each row it reads the source and the citing facts and answers agree/disagree with a reason. It changes nothing.
3. Every disagreement is a finding: fix it (and look for the same mistake in its group), then rerun this phase's sample with another seed.
4. Report the counts: checked, agreed, disagreed, fixed.
5. The tag means "the kb was confirmed current as of <date>". Create it only when no source is left unconfirmed (summary: no `blocked`, no `unconfirmed`, no unread NEEDS-READING): `python3 _tools/kbgit.py tag-census <date>`, then `git push origin census-<date>` if the user asked to push. Otherwise do not tag: report what is left and why, and put it in `work-left.md`.

## Report
The bucket counts, the phase 2 outcomes per group (confirmed, updated, superseded with old -> new ids, gone, unconfirmed), the sample result, the hosts that were blocked, the commits, and whether the tag was created.
