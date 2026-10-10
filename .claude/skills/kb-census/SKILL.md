---
name: kb-census
description: Use when the user asks for a census, a full re-verification or to confirm or refresh all it-ops-kb sources: mechanical checks of every source, reading the undecided ones, dating only what was confirmed, a sample check, the census tag.
argument-hint: "[YYYY-MM-DD, default today] [--resume]"
---

# Census of it-ops-kb

Census date: the argument, else today (`YYYY-MM-DD`). `--resume`: continue from the existing `kb/public/_census/<date>.csv` (skip phases done: its `outcome` column shows what phase 2 already read). Below, `<log>` is `kb/public/_census/<date>.csv` and `<flog>` is `kb/public/_census/factdiff-<date>.csv`.

Read the conduct rules first (`selfdoc.py section` prints one section with its line numbers):

```
python3 _tools/selfdoc.py section maintaining "Conduct for changes"
```

Every other rule of `kb/_self/` is asked for, not read up front. When a step below is reached, run its set: `python3 _tools/rag.py pack --root _self --set <name>` prints that step's tested rule questions, the line that answers each (`path:line`) and the decisions tied to them. The sets of this skill:
- `kb-census:phase0`: before Phase 0, the fact diff
- `kb-census:phase1`: before Phase 1, the mechanical verdicts
- `kb-census:phase2`: before Phase 2, reading what the checks could not decide
- `kb-census:phase3`: before Phase 3, dates
- `kb-census:phase4`: before Phase 4, the independent check and the tag

Any other rule: `python3 _tools/rag.py pack --root _self "<question>"` (`-q` for several parts, `--budget 400`). `coverage: good` names a tested question: follow its line. `weak` or `none`: `python3 _tools/kb_ask.py --root _self "<question>"` has a reader quote the answering lines from the sections, or read the section it names with `python3 _tools/selfdoc.py section DOC HEADING`. A rule you needed and no set or question gave you is a miss: say so in your report, with the question as you asked it.

`AGENTS.md` covers lookups only.

Run each command on its own (no `;`, `&&`, pipes into other tools or loops): the shared permission rules match single commands.

Rules that hold throughout:
- "Refreshed" means **confirmed up to date**: a source's `retrieved_utc` moves only after its content was compared (phase 0: unchanged by its provider's signal, or every fact citing it found word for word in its anchor's passage; phase 1 OK) or read and matched against the facts citing it (phase 2). Never bump a date to make the census look complete.
- A pinned source whose upstream changed gets a **new source row** (the file at the new commit or release), the re-verified citations point to it, and the old row's `superseded_by` names it. Old rows are never edited in place or deleted; `census.py apply` writes the new row and the pointer.
- `MicrosoftDocs/memdocs` is archived: its pins are re-sourced to the live Learn page (new row with the Learn url, `version_or_date` recording the page's `git_commit_id`/`updated_at`).
- Read the full page before confirming or changing a fact (`microsoft_docs_fetch` for Learn, the `.mdx` page for Claude Code docs, git for pinned files). Paraphrase Learn text (quotes of 25 words or fewer). Placeholders only.
- Never call `submit_feedback`. Never `--force` or `--no-verify`. One commit per logical step, with `--trailer "KB-Verified: <date>"` on commits that confirm sources.

## Phases 0 and 1: fact diff and mechanical verdicts (no model)
Rules: `python3 _tools/rag.py pack --root _self --set kb-census:phase0`, then `--set kb-census:phase1`.

1. `python3 _tools/census.py run --date <date>` (about 45 minutes, Learn being most of it). It chains the fact diff (`detect`, `apply --commit`), `check`, the index and the commit `docs(kb): census <date> phase 1 verdicts`, then prints the summary. `--resume` skips the steps whose output exists; `--dry-run` prints the steps and runs none. A failing step stops it and names the command that resumes it. Run the gate before pushing, as for any commit.
2. Summary: NEEDS-READING with note `blocked` means this environment's network policy denied the host: tell the user which hosts (the environment's network settings can allow them) and continue with the rest; those sources stay unconfirmed.
3. Look at the non-OK rows for mechanical false positives (a monorepo tag family, a moved url, a shallow clone). Fix `census.py` if the rule is wrong, never the log by hand, then `census.py check --date <date> --factdiff <flog>` and `census.py run --date <date> --resume`.

## Phase 2: read what the checks could not decide
Rules: `python3 _tools/rag.py pack --root _self --set kb-census:phase2`.

Scope: every row whose bucket is not OK, whose note is not `blocked` and that has no outcome yet.
1. `python3 _tools/census.py summary <log> --factdiff <flog>`: read its queue block (rows, facts, review items, characters and tokens a model will read, by host) and report it to the user before any subagent starts.
2. `python3 _tools/census.py groups <log> --factdiff <flog>` prints the groups as JSON, each with its rows, owned and foreign files and number of brief parts. Start one subagent per group, in parallel, with `python3 _tools/census.py brief <log> --group G --factdiff <flog>` as its prompt (`--part N` for a group of several parts, which run one after another). It returns JSON only, valid against `_tools/census_result.schema.json`.
3. Per group, save the result to a file under `_cache/census/` and run `python3 _tools/census.py apply <log> --group G --from <result>` (`--dry-run` first prints every write). Exit 2 names each problem and writes nothing: have the subagent correct its result. Foreign edits are printed, not applied: make them yourself. A source it reports gone with no successor: `python3 _tools/factdiff.py dead <log> --source <id>`.
4. Per group: the gate (`check.py`, `build_index.py --check`, `kbgit.py fix --check`, `tests.py`, which runs `rag.py eval`; `python3 _tools/doc2query.py prune` removes the expansion keys that reworded facts orphaned) and a commit (`docs(kb): census <date>: <group>`, `git commit --trailer "KB-Verified: <date>"`).

## Phase 3: dates, by script
Rules: `python3 _tools/rag.py pack --root _self --set kb-census:phase3`.

`python3 _tools/census.py finish <log> --date <date>` chains `confirm`, `kbdecide.py sweep`, the index and the commit `docs(kb): census <date>: confirmed dates`; it prints each invalidation and relink line for the report (`kbdecide.py relink ID --fact PATH:LINE` repoints a decision once the fact is the right one). `--dry-run` prints the steps and runs none. Run the gate before pushing.

## Phase 4: independent check, then the tag
Rules: `python3 _tools/rag.py pack --root _self --set kb-census:phase4`.

1. `python3 _tools/census.py sample <log> --changed 0.10 --ok 0.05 --seed <any>`.
2. Give the sample to a fresh subagent that did not do phase 2: for each row it reads the source and the citing facts and answers agree/disagree with a reason. It changes nothing.
3. Every disagreement is a finding: fix it (and look for the same mistake in its group), then rerun this phase's sample with another seed.
4. Report the counts: checked, agreed, disagreed, fixed.
5. The tag means "the kb was confirmed current as of <date>". Create it only when no source that a fact cites is left unconfirmed (summary: no `blocked`, no `unconfirmed`, no unread NEEDS-READING, except rows `python3 _tools/rag.py src <id> --cited` shows cited by no article or data line, only in front matter or ledger notes; file those as one backlog story with `/kb-backlog`): `python3 _tools/kbgit.py tag-census <date>`, then `git push origin census-<date>` if the user asked to push. Otherwise do not tag: report what is left and why, and file it as backlog items with `/kb-backlog`.

## Report
The queue block, the bucket counts, the phase 2 outcomes per group (confirmed, updated, superseded with old -> new ids, gone, unconfirmed), the decisions the sweep invalidated and its relink lines, the sample result, the hosts that were blocked, the commits, and whether the tag was created.
