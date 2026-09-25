# AGENTS.md

Instructions for AI coding agents working in this repository. Human-oriented overview and the coverage table: `README.md`.

## What this repo is

An offline knowledge base of facts from official sources about Windows endpoint management and the AI agents that operate it. Content is Markdown articles plus CSV/YAML/JSON data; there is no application to build. Python tools in `_tools/` (stdlib only) search and check it.

## Setup (first session in a fresh clone)

Run `/kb-setup` (Claude Code), or do the same by hand:

1. **Python 3.9+** as `python3`. Nothing to install: the tools use the standard library only.
2. **Checks pass on a clean tree:**
   - `python3 _tools/check.py` -> `errors=0`
   - `python3 _tools/fetch.py --offline` -> `mismatch=0 unknown=0`
   - `python3 _tools/stress_test.py` -> `0 failed`
3. **Documentation MCP servers are in place.** `.mcp.json` shares three remote servers that need no authentication:

   | name | url | use for |
   |---|---|---|
   | `microsoft-learn` | `https://learn.microsoft.com/api/mcp` | every Microsoft product in the kb |
   | `claude-code-docs` | `https://code.claude.com/docs/mcp` | Claude Code |
   | `mcp-docs` | `https://modelcontextprotocol.io/mcp` | the MCP specification |

   - `claude mcp list` must show all three `Connected`.
   - `Pending approval`: `.claude/settings.json` pre-approves them, but Claude Code honours that only once the folder is trusted. Accept the trust prompt and restart, or approve them in `/mcp`.
   - `Failed`: check network or proxy access to the url; the servers need no credentials.
   - Other agents (not Claude Code): register the same three urls as streamable-HTTP MCP servers in your client.
   - Optional, per user: GitHub's read-only repository server needs a personal token. Add it at user scope, never in a repo file:
     `claude mcp add --scope user --transport http github-repos-ro https://api.githubcopilot.com/mcp/x/repos/readonly --header "Authorization: Bearer $GITHUB_PAT"`
4. **Commit hook:** `python3 _tools/kbgit.py install-hooks`, once per clone. It only sets the local `git config core.hooksPath .githooks`; the versioned commit-msg hook then adds the KB-* trailers to every kb commit (see Commits and history).
5. **Do not** run `python3 _tools/fetch.py --diff` over the whole kb as part of setup: it is a long network job that writes `_fetch_state.csv`. A whole-kb baseline is the maintainer's decision; a targeted `--diff` from `/kb-refresh` is committed with that refresh.

## Tools

| command | does |
|---|---|
| `python3 _tools/rag.py search "<query>" -k 8 [-d DOMAIN] [-u] [--index]` | BM25 search; `-u` adds source urls; root index files only with `--index` |
| `python3 _tools/rag.py show PATH:LINE -n 30` / `src S123` / `topics [DOMAIN]` | read lines / resolve a source id (`S123` or `S-k3f7q2zd`) / list articles |
| `python3 _tools/kbid.py url <URL>` / `answer "<question>"` / `check` | id for a new source / `QK-<slug>` for a new answer / hash-id consistency |
| `python3 _tools/build_index.py [--check]` | regenerate `_coverage.csv`, the README coverage table and `used_in` from the articles (`--check`: report only, exit 1 if stale) |
| `python3 _tools/kbgit.py fix [--check] [--base REV]` | after any merge or pull: dedupe/merge the union-merged ledgers, renumber colliding legacy ids, rebuild the index (exit 1 `--check` stale, 2 needs a human); `fmt` only canonicalises the CSV ledgers |
| `python3 _tools/kbgit.py install-hooks [--uninstall]` | once per clone: `core.hooksPath=.githooks`, so commits get their KB-* trailers |
| `python3 _tools/kbgit.py trailers [--staged] [REV] [--verified YYYY-MM-DD]` | print the KB-* trailers of the staged change or of a commit; `--amend` rewrites HEAD's message with them |
| `python3 _tools/kbgit.py check-trailers [A..B]` | exit 1 listing kb commits whose trailers are missing or wrong (default: CI's push range, else `@{upstream}..HEAD`) |
| `python3 _tools/kbgit.py log <S-id, topic, QK-id or path> [-n N]` | commits that touched it: by trailer, else by diff (`git log -G`) or path history |
| `python3 _tools/kbgit.py blame PATH:LINE` / `asof <YYYY-MM-DD or tag> PATH` / `tag-census YYYY-MM-DD` | the commit that wrote a line plus its sources' urls / a file as of a date or tag / annotated tag `census-YYYY-MM-DD` on HEAD (not pushed) |
| `python3 _tools/check.py` | source ids, superseded_by, answer ids, citations, artifacts, front matter, CSV shape |
| `python3 _tools/fetch.py --offline` | pinned artifacts vs their sha256 |
| `python3 _tools/fetch.py --status --topic T` | offline: when a topic's sources were last fetched or changed |
| `python3 _tools/fetch.py --diff --topic T [--full] [--json]` | re-fetch a topic's sources and diff against the last fetch (exit 0 same, 1 changed, 2 error) |
| `python3 _tools/stress_test.py` | robustness tests on throwaway copies of the kb |
| `python3 _tools/tests.py` | what CI (`.gitlab-ci.yml`) runs: docs cohesion and leak scan; `--write-lint-baseline` accepts current lint errors as known debt |
| `python3 .claude/skills/kb-verify/lint.py [PREFIX...]` | contract checks beyond check.py (report only) |

## Skills (`.claude/skills/`)

- `/kb-setup`: the setup above, with a pass/fail report.
- `/kb-lookup`: answer from the kb with citations; Claude may invoke it on its own.
- `/kb-research <question>`: research a question in the context of the topics the kb already has, then extend them.
- `/kb-refresh <topic|dir|file|S-id>`: diff sources and update the facts.
- `/kb-add-topic <domain>/<slug>`: research and write a new topic.
- `/kb-verify [prefixes]`: quality gate before a commit or merge request.

## Content rules (summary; `README.md` is authoritative)

- One topic = `<domain>/<topic>.md` with front matter `topic, priority, applies_to, retrieved_utc, sources, status` and sections Summary, Facts, Reference, Examples. `topic` equals the path.
- Every fact ends in exactly one tag with ids from `_sources.csv`: `DOC`, `DER` (show the derivation), `COMMUNITY` (never the only evidence for a DOC fact), `UNK`.
- Add the source row before the fact. A new source's id is `S-` + 8 characters from `python3 _tools/kbid.py url <URL>` (a hash of the url, so parallel writers converge); never invent one or take "the next number". Legacy `S<number>` ids stay valid; reuse the existing id when the url already has a row. Write CSVs with a real CSV writer: an unquoted comma breaks the row.
- A replaced source (e.g. a pinned commit url whose upstream changed) gets a new row; the old row's `superseded_by` names the new id. Ids are never deleted or reused.
- New `_answers.md` entries are `## QK-<slug>. <question>` (`python3 _tools/kbid.py answer "<question>"`); answer ids are unique.
- `_coverage.csv`, the README coverage table, `n_sources` and `used_in` are generated: after any content change run `python3 _tools/build_index.py`, never edit them by hand (CI fails when they are stale). Extra files of a topic go in its front matter `files: [...]`; a topic with no `.md` goes in `_tools/index_extra.csv`. Failed lookups go in `_gaps.md`, disagreements in `_conflicts.md`.
- Licensing: our own words, quotes of 25 words or fewer; verbatim only under permissive licences (MIT, Apache-2.0, CC BY 4.0) with attribution; never copy CIS or ISO text. Microsoft Learn content fetched through MCP is paraphrased.
- Placeholders only in examples: `PL-LT-00123`, `PL-SRV-0042`, `corp.example.com`, tenant `00000000-0000-0000-0000-000000000000`, `jan.kowalski`. Never real hostnames, tenants, people or secrets.
- `UNK` and `COMMUNITY` facts are leads to verify, not a basis to build on.

## Merging

- `.gitattributes` merges the append-only ledgers (`_sources.csv`, `_fetch_state.csv`, `_answers.md`, `_gaps.md`, `_conflicts.md`) and the generated `_coverage.csv` and `_tools/lint_baseline.txt` with git's built-in union driver: parallel additions merge without conflict markers, but git keeps both sides' lines, so a row both sides touched may appear twice. Nothing to configure per clone.
- Writers: append rows and blocks, keep each CSV record on one line, never reorder or rewrap existing lines.
- After any merge or pull: `python3 _tools/kbgit.py fix`, then `python3 _tools/tests.py`. If two branches took the same legacy id, fix asks for `--base $(git merge-base A B)` and renumbers the new rows to hash ids. Exit 2 means a human decision (listed); nothing was written.
- `README.md` merges normally; a conflict inside its coverage table is rebuilt by fix (then `git add README.md`).

## Commits and history

- One logical change per commit, and every commit passes `python3 _tools/check.py` and `python3 _tools/build_index.py --check`.
- A source row goes in the same commit as the facts that cite it; a `superseded_by` goes in the same commit as the re-pointed citations.
- Run `python3 _tools/kbgit.py install-hooks` once per clone. The commit-msg hook appends trailers computed from the staged diff: `KB-Topics` (topics whose article or data files changed), `KB-Sources-Added`/`-Changed`/`-Superseded` (`_sources.csv` rows), `KB-Answers` (`_answers.md` ids). More than 40 values become `N ids (see diff)`. Never type them by hand; the hook replaces them on `--amend` and never blocks a commit. Merge commits get none.
- `KB-Verified: YYYY-MM-DD` only when the commit confirms its sources are current (e.g. a `/kb-refresh` that re-read them): `KB_VERIFIED=2026-09-25 git commit ...` or `git commit --trailer "KB-Verified: 2026-09-25"`.
- `git commit --no-verify` skips the hook; the CI job `kb-trailers` then fails for the push. Before pushing, `python3 _tools/kbgit.py check-trailers`; repair unpushed commits with `python3 _tools/kbgit.py trailers --amend` (HEAD) or `git rebase --exec "python3 _tools/kbgit.py trailers --amend" @{upstream}`. Pushed history is never rewritten; commits up to `e5dadde` (before trailers existed) are exempt.
- Lookups: `kbgit.py log S-k3f7q2zd` / `log auth/kerberos` / `log QK-...`, `kbgit.py blame auth/kerberos.md:42`, `kbgit.py asof 2026-06-30 auth/kerberos.md`. `kbgit.py tag-census YYYY-MM-DD` tags HEAD `census-YYYY-MM-DD` ("the kb was confirmed current as of this date") after a full verification; push the tag explicitly (`git push origin census-YYYY-MM-DD`).

## Agent conduct

- Never call a docs server's `submit_feedback` tool (denied in settings): it posts text outside the repo.
- Do not edit files listed in `_artifacts.csv` by hand; they are pinned by sha256 (`fetch.py --refresh` rewrites them).
- `_cache/` and `_private/` are local only; never commit them. Never add tenant ids, object ids, real hostnames, addresses or tokens; the CI leak scan fails on them. Add a value to `_tools/tests_allowlist.txt` only when it is public or a placeholder, with the reason.
- Run shell commands one at a time: the shared permission rules match single commands, so `a; b`, `a && b` and loops need approval (or are refused in headless runs).
- Before proposing a commit: `python3 _tools/tests.py` passes (CI runs it; lint errors in `_tools/lint_baseline.txt` are known debt, new ones fail), `stress_test.py` passes if `_tools/` changed, and `/kb-verify` shows no new errors in the files you touched.
- Commit messages: conventional prefix (`docs(kb):`, `fix(kb):`, `feat(kb):`, `chore:`), imperative, body explaining why; your own trailers (e.g. `Co-Authored-By`) in the last paragraph, and the hook appends the KB-* ones after them. Commit only when asked.
