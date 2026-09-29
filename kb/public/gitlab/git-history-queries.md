---
topic: gitlab/git-history-queries
priority: P3
applies_to: [git]
retrieved_utc: 2026-09-29
sources: [S-45u5kgbq, S-kr4uocm7, S-hpl22yvu, S-gpllp4ih, S-vk5alhjj, S-dwkxab7d, S-zktixf2a]
status: complete
---

# Git history queries: co-change, renames and line ranges

## Summary
Which files change together, whether a path ever existed, and how one function evolved are all
answered from `git log` with a few options: `--name-only` and `--name-status` for per-commit file
lists, `--diff-filter` to keep one kind of change, `-M` for rename detection in each commit,
`--follow` for one file across renames, and `-L` for a line range or function. The limits of each
matter when a large file is split or moved: git stores no rename record, and history follows a rename
only where a diff finds it. Facts below are from the git 2.55.0 documentation; `gitlab/git-trailers-and-hooks.md`
covers commit trailers, and `python/imports-and-modules.md` the module side of a split.

## Facts
- `--name-only` prints only the name of each changed file (post-image tree); `--name-status` adds the status letter of each. [DOC S-kr4uocm7]
- `--diff-filter=` keeps only paths whose change is one of A (added), C (copied), D (deleted), M (modified), R (renamed), T (type changed), U, X or B; an upper-case letter selects and a lower-case one excludes (`--diff-filter=ad`). Copied and renamed entries cannot appear when detection for them is off. [DOC S-kr4uocm7]
- `-M[<n>]` / `--find-renames[=<n>]` detects renames in each commit's diff; `<n>` is the similarity threshold (default 50%; `-M90%` needs more than 90% unchanged; `-M100%` only exact renames). `-C` also detects copies, and by default only when the copy's source was modified in the same commit unless `--find-copies-harder` is given; `--no-renames` turns detection off. [DOC S-kr4uocm7]
- For `git log`, `-M` only reports renames in the diffs it shows; following a file across renames while walking history is `--follow`, which works for a single file only. [DOC S-kr4uocm7, S-45u5kgbq]
- Rename detection is a diff transformation (diffcore-rename): a deleted file and an added file whose contents are similar enough are merged into one rename entry, with a first pass that pairs a same-named file moved between directories. Each commit is analysed alone; the number of files considered in the exhaustive pass is limited by `diff.renameLimit` (default 1000), and it has no effect when detection is off. [DOC S-vk5alhjj, S-zktixf2a]
- Splitting one file into several therefore shows, per commit, at best one rename (a deleted file pairs with its most similar added file) and the rest as additions; the history of the moved-out parts is read at the old path (`git log -- <old path>` still works), and `--follow`, which takes one file, does not merge the parts' histories. [DER S-vk5alhjj, S-45u5kgbq: rename pairing is by best similarity, and `--follow` is documented for a single file]
- `-L<start>,<end>:<file>` or `-L:<funcname>:<file>` traces the evolution of a line range or function in one file; no pathspec limiters may be given, at most one positive revision may be given, and the range must exist in the starting revision. `-L` may be repeated, implies `--patch` (suppress with `--no-patch`), supports `--name-only`, `--name-status`, `--summary`, pickaxe options and `--diff-filter`, but not `--stat`, `--numstat`, `--shortstat` or `--dirstat`. [DOC S-hpl22yvu]
- A range's `<start>` and `<end>` are a line number, a `/regex/` (searched from the end of the previous `-L` range, or from the file start when `^/regex/`), or, for `<end>`, `+offset` or `-offset`; `:<funcname>` runs from the first function line matching the regex to the next function line, using the same function-name detection as `git diff` hunk headers. [DOC S-gpllp4ih]
- Merge commits show no diff, so no file list, unless `-m`, `-c`, `--cc`, `--dd` or `--first-parent` is used; `--no-merges` prints no commit with more than one parent. A per-commit file list for co-change counts is therefore a list over non-merge commits, or over the first-parent line. [DOC S-45u5kgbq, S-dwkxab7d]
- With a path limiter, the default history mode includes a commit unless it is TREESAME to a parent (its tree at that path is identical), and follows only one parent of a merge that is TREESAME to it. [DOC S-dwkxab7d]
- A path that no longer exists in the working tree can still be given as a path limiter: on this repository `git log --oneline -- _tools/index_extra.csv` (a file moved out of `_tools/`) lists its commits, and `git log --diff-filter=D --name-only --format= -- _tools` lists paths deleted from `_tools/`. So "named in a plan but gone from HEAD, with history" is answered by `git log -1 --format=%h -- <path>` printing a hash while the file is missing. [DER S-kr4uocm7, S-dwkxab7d: run 2026-09-29 with git 2.x on this repository]
- With a path limiter, `--name-only` lists only the files that match the limiter, so a co-change count over all files of a commit needs the unrestricted list (`git log --no-merges --name-only --format=%x00%h`, one block per commit) filtered afterwards. [DER S-kr4uocm7: observed by running `git log --no-merges --name-only --format=%x00%h -- _tools/kbgit.py`, which printed only that file per commit]
- A method for co-change of sections inside one file: take each commit's hunk ranges for the file (`git log -p -U0 --no-merges -- <file>`, `@@` headers), map each range to the function containing it at that commit, and count how often two sections appear in the same commit versus alone; `-L :<funcname>:<file>` gives one section's own history for a cross-check. [DER S-hpl22yvu, S-kr4uocm7: composed from the documented `-L` and diff options]

## Reference
- SNIPPET: the per-commit file lists a co-change count starts from; context: git 2.x, POSIX shell; checked: run on this repository [DER S-kr4uocm7, S-dwkxab7d: `--no-merges`, `--name-only`, `--format=%x00%h` as documented]
```console
$ git log --no-merges --name-only --format=%x00%h
$ git log --diff-filter=D --name-only --format= -- _tools
$ git log -L :main:_tools/kbgit.py --no-patch --format=%h
```
- Related: `gitlab/git-trailers-and-hooks.md`, `python/imports-and-modules.md`, `agents/codebase-mapping.md`.

## Examples
- Counting how often `kbgit.py` and another file changed in the same commit: list every non-merge commit's files once, keep the commits that name `_tools/kbgit.py`, and count how many also name the other file.
- `git log --follow --oneline --name-status -M -- _tools/test_kb.py` lists the commits of one file across renames, each with its status letter.
