# Content rules

What a fact, an article, a source row and a ledger entry look like, and how to add them. This file is authoritative; `check.py`, `build_index.py`, the kb-verify lint and `tests.py` enforce most of it.

## Layout

- `<domain>/<topic>.md` is one topic. Its front matter has `topic` (equal to the path without `.md`), `priority` (P0-P3: the research order it was gathered in, not importance), `applies_to`, `retrieved_utc`, `sources` and `status`, and optionally `files`. Its body has four sections: Summary, Facts, Reference and Examples. Large tables sit beside it as `.csv` or `.yaml`.
- A topic's files are the `.md` plus sibling files sharing its stem (`auth/flows.csv`), plus any extras in `files: [dsc/cli/, graph/csdl/device.v1.0.xml]` (kb-root paths, directories end in `/`). An article named in another article's `files:` (an artifact digest) is part of that topic. A topic with no `.md` (a CSV-only table) is a row of `kb/public/_retrieval/index_extra.csv` (`topic,priority,status,files`).
- `_sources.csv`: every source, `id,url,title,publisher,licence,retrieved_utc,version_or_date,artifact_sha256,used_in,superseded_by`. `used_in` is generated (the domain files that cite the id). `superseded_by` is empty unless a newer row replaced this one; it then names that row's id.
- `_artifacts.csv`: every pinned structured artifact (JSON schemas, DSC manifests, Graph CSDL, the MCP `schema.ts`, the A2A `.proto`, baseline exports, semantic-convention registries), with its sha256 and a Markdown digest beside it.
- `_answers.md` (research answers with evidence), `_gaps.md` (what could not be confirmed and where it was looked for), `_conflicts.md` (where sources disagree, both sides linked).
- Generated, never edited by hand: `_coverage.csv`, the table in `kb/_self/coverage.md`, `n_sources` and `used_in`. After any content change run `python3 _tools/build_index.py` (CI runs `--check`). Rows are ordered by domain, priority, topic id.
- `kb/public/_census/<date>.csv`: a census verdict log, one row per source with its mechanical bucket (OK, CHANGED, GONE, NEWER-VERSION, NEEDS-READING), the evidence and what reading decided. `_fetch_state.csv`: per source, when `fetch.py --diff` last checked and fetched it, when it last changed, and the hashes compared; snapshots of the last fetch sit in `_cache/snapshots/` (never committed). Search skips both.

## Facts and tags

- Every fact ends in exactly one tag with ids from `_sources.csv`: `DOC` (an official document states it), `CODE` (source code states it, read at a pinned commit), `DER` (derived from DOC or CODE facts, derivation shown), `COMMUNITY` (a non-official source; never the only evidence for a DOC fact), `UNK` (not confirmed).
- Canonical forms: `[DOC <id>, <id>]`, `[CODE <id>: path#symbol]` (or `path#L10-L20`), `[DER <id>: how]`, `[COMMUNITY <id>]`, `[UNK]` or `[UNK: why]`. `_tools/kbfacts.py` parses them for every tool (grammar in its docstring); the kb-verify lint reports a DOC or COMMUNITY tag without an id.
- Numbers, dates, versions and table rows come from the source's own text or image, never from a fetch tool's summary of it: a summary can invent rows that the page does not have.
- `UNK` and `COMMUNITY` facts are leads to verify, not a basis to build on.

## CODE: what the implementation does

- Use `CODE` when the evidence is source code rather than documentation (a default read from a settings file, a limit in a validator, undocumented behaviour). It is implementation, not a promise: it can change in any release, and an answer built on it must say so. When the documentation states the same thing, the fact is `DOC`.
- A published contract is `DOC`, not `CODE`: a machine-readable schema or API definition (JSON Schema, Graph CSDL metadata, MCP `schema.ts`, OpenAPI/swagger, `.proto`, ECS or OTel metadata, a STIX bundle) is the promise itself. Build files and example configs next to it (`schemas.config.yaml`, `example_recognizers.yaml`) are `CODE`. `kbfacts.contract_source` draws this line for `lint.py --candidates`.
- The source row must be pinned: a repository file url at a release tag or commit (`raw.githubusercontent.com/<owner>/<repo>/<tag>/...`, `github.com/.../blob/<sha>/...`, `gitlab.com/.../-/raw/<tag>/...`) or a pinned artifact (`artifact_sha256`), never a branch. When upstream moves, add a new pinned row and set `superseded_by` (as for any replaced source).
- The note is a pointer into that file: `path#symbol` (a function, class, constant or key) or `path#L10-L20`. The lint rejects a CODE part without an id, without a pointer, or citing an unpinned source.
- Borderline evidence: a release binary's own `--help` output is `DOC` (the published interface); a doc comment in source (rustdoc, docstrings) is `CODE`; that something is absent from a release archive is `DER`, with the derivation.
- In `kb/_self/` only, a CODE part may point into this repository without a source row: `[CODE _tools/kbfacts.py#pack]`. A test checks that the file and the symbol exist; `kb/_self/` never enters the pack.

## SNIPPET: a code example with evidence

- A code example is a bullet that starts `SNIPPET:`, directly above its fenced block: `- SNIPPET: <what it does>; context: <versions, prerequisites>; checked: no|syntax|run [DER <id>, <id>: parameters from the cmdlet page]`.
- The bullet carries an evidence tag other than `UNK`: a snippet nobody can back stays out. `checked:` says what was verified: `no`, `syntax` (parsed: the lint re-parses json, toml and python blocks), or `run` (executed in the stated context; say where in the note).
- Placeholders only, as in every example. The pack shows the bullet with `path:line`; `rag.py show` prints the block.
- A block without a `SNIPPET:` bullet is illustration only (Reference and Examples may keep them) and carries no evidence.
- A reader checking a snippet reads each parameter's reference page before dropping it: an article's own sources not showing a parameter does not mean it does not exist.

## Ids

- **Sources.** Add the source row before the fact. A new source's id is `S-` + 8 characters from `python3 _tools/kbid.py url <URL>` (a hash of the url, so parallel writers converge); never invent one or take "the next number". Legacy `S<number>` ids (`S100` ... `S2204`) stay valid and are never renumbered; reuse the existing id when the url already has a row. `check.py` rejects a hash id that does not match its url.
- **Replaced sources.** When a source is replaced (e.g. a pinned commit url whose upstream changed), add a new row, set the old row's `superseded_by` to the new id, and re-point the citations of the facts you re-verified. Ids are never deleted or reused.
- **Answers.** New `_answers.md` entries are headed `## QK-<slug>. <question>` (`python3 _tools/kbid.py answer "<question>"`); an id never appears twice.
- Write CSVs with a real CSV writer (Python's `csv` module, `lineterminator="\n"`: its default ends rows with `\r\n`), one record per line: an unquoted comma breaks the row. The ledgers, the `_tools/` data and `kb/_self/` must stay `\n`-only (tested).

## Ledgers and retrieval data

- Failed lookups go in `_gaps.md`, disagreements in `_conflicts.md`. Each new entry ends with `(topic: <domain>/<slug>)` so `rag.py audit` links it to its article (`check.py` rejects a marker naming no topic).
- Retrieval data in `_tools/` (CSV writer, one row per line):
  - a topic about code with distinctive names (classes, API routes, libraries, scopes) gets `signals.csv` rows (`signal,topic`) for `topics-for`;
  - a product known by other names gets `aliases.csv` rows (`term,canonical`, term lowercase);
  - a real lookup that missed an article the kb has becomes a `lookup_eval.csv` row, id `python3 _tools/kbid.py eval "<question>"` (`EV-<slug>`). `python3 _tools/rag.py eval` must pass every question.
- After rewording or removing facts, `python3 _tools/doc2query.py stale` lists orphaned expansion keys (exit 1); `doc2query.py prune` removes their rows (regenerate only where real lookups miss; `kb/_self/doc2query.md`).
- Save structured data as a pinned artifact, with a row in `_artifacts.csv` and a digest.

## Licensing and privacy

- Each source's licence is recorded in `_sources.csv`. Facts are in our own words; quotes of 25 words or fewer. Verbatim copies only under permissive licences (MIT, Apache-2.0, CC BY 4.0, which covers most Microsoft Learn prose), with attribution. Never copy CIS Benchmark or ISO text; reference their ids only. Microsoft Learn content fetched through MCP is paraphrased.
- Placeholders only in examples: hosts `PL-LT-00123` and `PL-SRV-0042`, domain `corp.example.com`, tenant `00000000-0000-0000-0000-000000000000`, user `jan.kowalski`. Never real hostnames, tenants, people or secrets. Organisation-specific knowledge belongs in a team's own kb (`kb/_self/plugin.md`, "A team's own facts").
