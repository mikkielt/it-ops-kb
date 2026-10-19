---
name: kb-add-root
description: Use when the user asks to add a new knowledge root to it-ops-kb (a directory under kb/ beside public/, e.g. a team's internal knowledge of its own systems or repositories): picks the name, id prefix, visibility and where it is kept (a directory here, or a fetch or submodule root in the team's own repository), creates the root with kbroot.py add, or add-remote and fetch, and checks it.
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
- **Where it is kept:** a root with internal knowledge belongs in the team's own fork or clone of it-ops-kb, never pushed to the upstream remotes; say so and confirm the remote before any push. Ask which of three it is:
  - **A directory here:** `kb/<name>/` in this clone (step 2, A).
  - **A fetch root:** the team's own repository holds the root; this clone keeps a pointer file and a clone of it in `_cache/roots/<name>/` (step 2, B). `--access` defaults to `fetch`; a plugin host fills it too, each user with the credentials they have.
  - **A submodule root:** the same, checked out as a git submodule at `kb/<name>/`, so this repository's commit is the pin (step 2, B).
  For a remote root also ask: the repository's `url`, the team that owns it (`--team`), and a branch (`--ref`; empty follows the remote's default branch). The repository must already hold the root (`_root.md` with the same name, id prefix and visibility): create it first with step 2, A in a clone of that repository and push it there.

## 2. Create and check
**A. A directory here**
1. `python3 _tools/kbroot.py add <name> --prefix <P> --visibility <v> --description "<one line>"`.

**B. A remote root**
1. `python3 _tools/kbroot.py add-remote <name> --url <URL> --prefix <P> --team <team> --visibility <v> --access fetch|submodule [--ref <branch>] --description "<one line>"` writes the pointer `kb/_roots/<name>.md`; with `--access submodule` it also runs `git submodule add` at `kb/<name>/` (exit 1 and no pointer when that fails).
2. A fetch root: `python3 _tools/kbroot.py fetch <name>` clones it; `--pin` writes the fetched commit into the pointer so the root stays there, else it follows `ref` on each fetch. A failed fetch (no access, wrong url) is not fatal: `kbroot.py list` shows the root as `missing` with the reason. A submodule root is on disk once `git submodule add` ran; a clone of this repository gets it with `git submodule update --init`.
3. Commit the pointer (and `.gitmodules` with `kb/<name>` for a submodule); a fetch root's clone in `_cache/` is never committed.

**Then, for both**
1. `python3 _tools/check.py` -> `errors=0`, `python3 _tools/build_index.py --check` -> up to date, `python3 _tools/kbroot.py list` shows the root (a remote one not `missing`).
2. Add its first topics with `/kb-add-topic <name>/<domain>/<slug>`; each root cites only its own sources (add a public source again under the root's prefix when its facts need it). A remote root's topics are committed and pushed in its own repository, not here.

## 3. Finish
Rules of this step: `python3 _tools/rag.py pack --root _self --set kb-commit`.

`/kb-verify`, then commit (`feat(kb): add the <name> root`) and push with `python3 _tools/kbgit.py sync --push` only to the remote the user confirmed.

## 4. Give shared-root changes back
A team that follows an upstream keeps its `internal` root private and gives only its changes to shared roots (`kb/public`, other `public` roots) and tools back. Tell the user this when the root is `internal`, and do not push the root, its pointer file or its gitlink upstream. To give changes back, run `python3 _tools/kbgit.py contribute --upstream <remote>` (`--branch <name>` names the local branch; default `contribute/<remote>`). It writes a local branch at the upstream `main` that holds only the commits touching shared files and adding no private name, names each commit it left out and why, and pushes nothing. A person then reviews that branch, pushes it and opens the merge request on the upstream's host; upstream's gate and review take it from there. A commit left out is split or reworded by the team, then `contribute` is run again (`kb/_self/git.md`, "Contributing upstream").
