---
name: kb-add-root
description: Use when the user asks to add a new knowledge root to it-ops-kb (a directory under kb/ beside public/, e.g. a team's internal knowledge of its own systems or repositories): picks the name, id prefix and visibility, creates the root with kbroot.py, and checks it.
argument-hint: "<root-name> and what knowledge it will hold"
---

# Add a kb root

Request: $ARGUMENTS. A root is a directory under `kb/` beside `kb/public/`, with its own articles, ledgers and source ids; the read tools serve every root together (`_tools/kbcommon.py`, "Roots"). A new topic inside an existing root is `/kb-add-topic`, not this.

Read the conduct rules first (`selfdoc.py section` prints one section with its line numbers):

```
python3 _tools/selfdoc.py section maintaining "Conduct for changes"
```

Every other rule of `kb/_self/` is asked for, not read up front. When a step below is reached, run its set: `python3 _tools/rag.py pack --root _self --set <name>` prints that step's tested rule questions, the line that answers each (`path:line`) and the decisions tied to them. The sets of this skill:
- `kb-add-root`: before the first step
- `kb-commit`: before committing or pushing

Any other rule: `python3 _tools/rag.py pack --root _self "<question>"` (`-q` for several parts, `--budget 400`). `coverage: good` names a tested question: follow its line. `weak` or `none`: `python3 _tools/kb_ask.py --root _self "<question>"` has a reader quote the answering lines from the sections, or read the section it names with `python3 _tools/selfdoc.py section DOC HEADING`. A rule you needed and no set or question gave you is a miss: say so in your report, with the question as you asked it.

Run each command on its own (no `;`, `&&`, pipes or loops).

## 1. Decide with the user
Ask before creating anything when any of these is unclear:
- **Name:** lowercase, `a-z`, `0-9`, `-`; it becomes the first part of every path and topic the tools print (`<name>/<domain>/<slug>.md`). Not `kb`, and not the name of an existing root (`python3 _tools/kbroot.py list`).
- **Id prefix:** 1-4 capital letters, unique among the roots, not `S` (public) nor a reserved word (`DOC`, `CODE`, `DER`, `UNK`, `QK`, `EV`, `PL`). Its sources get ids `<prefix>-<8 characters>` from `python3 _tools/kbid.py url <URL> --root <name>`.
- **Visibility:** `internal` (the default) for knowledge with real hostnames, tenants, people or runbooks; `public` only for knowledge that follows the placeholders rule (`AGENTS.md`, "Agent conduct"), which the leak tests then enforce.
- **Where it is kept:** a root with internal knowledge belongs in the team's own fork or clone of it-ops-kb, never pushed to the upstream remotes; say so and confirm the remote before any push.

## 2. Create and check
1. `python3 _tools/kbroot.py add <name> --prefix <P> --visibility <v> --description "<one line>"`.
2. `python3 _tools/check.py` -> `errors=0`, `python3 _tools/build_index.py --check` -> up to date, `python3 _tools/kbroot.py list` shows the root.
3. Add its first topics with `/kb-add-topic <name>/<domain>/<slug>`; each root cites only its own sources (add a public source again under the root's prefix when its facts need it).

## 3. Finish
Rules of this step: `python3 _tools/rag.py pack --root _self --set kb-commit`.

`/kb-verify`, then commit (`feat(kb): add the <name> root`) and push with `python3 _tools/kbgit.py sync --push` only to the remote the user confirmed.
