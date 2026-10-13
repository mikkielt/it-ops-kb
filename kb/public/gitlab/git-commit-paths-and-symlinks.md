---
topic: gitlab/git-commit-paths-and-symlinks
priority: P3
applies_to: "Git 2.55.0 (documentation and source at the v2.55.0 tag): `git commit` with named paths (`--only`, `--include`), and how `git add`, `git commit` and `git log` treat a path under a symbolic link; the observed exit statuses and outputs were run with git 2.50.1 (Apple Git-155) on macOS"
retrieved_utc: 2026-10-13
sources: [S-ziyhuwyc, S-kg2qicnp, S-piib4adi, S-eud6nij7, S-xixlwvap, S-4aovy2cm, S-zflhytlw]
status: complete
---

# Committing named paths, and paths under a symbolic link

## Summary
A tool that commits its own files into a checkout where a person has other work staged passes the paths to
`git commit`: with paths, git commits the named paths' working tree contents and leaves everything else staged
(`--only`, the default whenever paths are given). It must name tracked or already staged paths, and git refuses a
partial commit during a merge, a cherry-pick or a rebase. A symbolic link is an entry of its own, so a change made
through a link is recorded on the file the link resolves to; a path whose leading directory is a link is refused
by `git add` and matches nothing in `git commit` and `git log`. Facts below are from the git 2.55.0
documentation and source, plus one run on git 2.50.1; `gitlab/git-test-repositories.md` covers throwaway
repositories and the index, and `gitlab/git-history-queries.md` the path limiter of `git log`.

## Facts
### Committing named paths: `git commit -- <paths>` and `--only`
- `git commit <pathspec>...` commits the contents of the files that match the pathspecs "without recording the changes already added to the index", and stages those contents as well; this is `--only`, the default mode whenever paths are given, so the option may be left out. [DOC S-ziyhuwyc]
- `--only` takes "the updated working tree contents" of the named paths and disregards what is staged for other paths; with `--amend` no path is needed, and the docs name that as the way to amend without committing what is staged. [DOC S-ziyhuwyc]
- `--only` or `--include` with no path dies with "No paths with --include/--only does not make sense." unless the commit is an `--amend` (not a `--fixup` of another kind) or has `--allow-empty`. [CODE S-kg2qicnp: builtin/commit.c#prepare_index]
- A partial commit builds the commit from a second, temporary index that holds HEAD with only the named paths applied, and applies the same paths to the real index, so paths staged elsewhere stay staged and uncommitted; it is refused during a merge, a cherry-pick and a rebase ("cannot do a partial commit during a merge."). [CODE S-kg2qicnp: builtin/commit.c#prepare_index]
- The paths a pathspec names are looked up in the union of the index and HEAD's tree (`list_paths`), so a file that is neither staged nor tracked matches nothing. [CODE S-kg2qicnp: builtin/commit.c#list_paths]
- Observed with git 2.50.1 (Apple Git-155) on macOS, a throwaway repository with the user and system configuration off, 2026-10-13: with `a.txt` modified and unstaged, `b.txt` staged and `c.txt` modified and unstaged, `git commit -m x a.txt` committed `a.txt` only and left `M  b.txt` staged and ` M c.txt` unstaged; a directory named as the path committed the tracked changes under it only; a tracked file deleted in the working tree and named recorded its deletion; naming a path with no change while another path was staged exited 1 with "no changes added to commit" and kept the staged path staged; naming an untracked file exited 1 with "pathspec 'new.txt' did not match any file(s) known to git", and the same file after `git add` committed; `--only` with no path exited 128 with the message above, and a path-limited commit during a conflicted merge exited 128 with "cannot do a partial commit during a merge." [DER S-ziyhuwyc, S-kg2qicnp: the documented mode and the code above; other git versions and Windows not run]
- So a tool that must commit its own files while the person has other paths staged names them after `--` (`git commit -m MSG -- <path>...`): nothing else staged goes into the commit and it stays staged; the tool first `git add`s a new file it names, and a conflicted merge, cherry-pick or rebase refuses the call. [DER S-ziyhuwyc, S-kg2qicnp: the facts above]

### A path under a symbolic link
- Git records a symbolic link as an entry of its own: in a tree and in `git fast-import` it is mode `120000` and the object's content is the link target. [DOC S-4aovy2cm]
- In the index file a symbolic link has the object type "symbolic link" and a zero value in the permission field. [DOC S-xixlwvap]
- With `core.symlinks=false` (the default is true, but creating a repository probes the file system and sets it false where links are unsupported) a link is checked out as a small plain file holding the link text, and `git update-index` and `git add` do not change its recorded type to a regular file. [DOC S-zflhytlw]
- A pathspec whose leading directory is a symbolic link is refused when it is parsed with the symlink-leading-path flag: `pathspec '%s' is beyond a symbolic link`. [CODE S-piib4adi: pathspec.c#parse_pathspec]
- `git add` parses its pathspec with that flag, in `interactive_add` and in `cmd_add`. [CODE S-eud6nij7: builtin/add.c#interactive_add, cmd_add]
- `git commit` parses its pathspec with `PATHSPEC_PREFER_FULL` alone, without that flag. [CODE S-kg2qicnp: builtin/commit.c#prepare_index]
- Observed with git 2.50.1 (Apple Git-155) on macOS, throwaway repository, user and system configuration off, 2026-10-13, with a directory `real/` holding `f.txt`, a directory link `link` to `real` and a file link `flink` to `real/f.txt`: after appending a line through `flink`, `git status --short` and `git diff --name-only` printed `real/f.txt` and nothing for `flink`, so the change is recorded on the file the link resolves to and the link's own entry stays as it was; `git commit --only flink` exited 1 with "no changes added to commit" and `real/f.txt` still unstaged, while naming `real/f.txt` committed it. [DER S-4aovy2cm, S-ziyhuwyc: the link-as-entry and named-path facts above; Windows and `core.symlinks=false` not run]
- In the same run on git 2.50.1 a path beyond the directory link was refused in two ways: `git add link/f.txt` exited 128 with "pathspec 'link/f.txt' is beyond a symbolic link", and `git commit -- link/f.txt` exited 1 with "pathspec 'link/f.txt' did not match any file(s) known to git"; `git log --name-status -- link/f.txt` exited 0 and printed nothing, while `-- real/f.txt` listed the file's commits and `-- flink` the commit that added the link. Replacing `flink` by a regular file showed as `T flink` in `git status --short`. [DER S-piib4adi, S-eud6nij7, S-kg2qicnp: the code above; other git versions and Windows not run]
- So a change under a symlinked path belongs to the path it resolves to, never to the link's path: a tool that reads, stages or commits "what changed at a link path" must resolve the link itself (the link entry changes only when its target text or its type does), and a pathspec that names the link alone commits nothing of the target's change. [DER S-4aovy2cm, S-ziyhuwyc: the facts and the run above]

## Reference
- Related: `gitlab/git-test-repositories.md` (index bits, a temporary index, worktree links), `gitlab/git-history-queries.md` (the path limiter of `git log` and merged-away branches), `gitlab/git-trailers-and-hooks.md` (what `git commit` runs).
- SNIPPET: commit only the named paths and leave other staged work staged; context: POSIX shell, git 2.x; checked: run on a throwaway repository, git 2.50.1 on macOS, 2026-10-13 [DER S-ziyhuwyc: the documented `--only` default and `--`]
```console
$ git add src/new.txt
$ git commit -m "add the new file" -- src/new.txt
$ git status --short
```

## Examples
- The person has `b.txt` staged and a tool must commit its own `item.json` alone: `git commit -m "update item" -- item.json` records `item.json` only, and `b.txt` is still staged afterwards.
- A scope list names `tools/guide.md`, a file link to `plugin/guide.md`: an edit made through the link shows in `git status` as `plugin/guide.md`, and `git commit -- tools/guide.md` finds no change to record while `plugin/guide.md` stays unstaged.
