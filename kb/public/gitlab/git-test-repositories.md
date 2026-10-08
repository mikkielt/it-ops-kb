---
topic: gitlab/git-test-repositories
priority: P3
applies_to: "Git 2.55.0 (documentation and source at the v2.55.0 tag): throwaway repositories built by test suites (local clones, templates, fast-import, automatic maintenance, per-process configuration), and how tools read revisions, worktree links and index bits; Git for Windows v2.56.0.windows.2 (core.longpaths)"
retrieved_utc: 2026-10-08
sources: [S-k2jlpd4u, S-nv6io42x, S-miw74ti3, S-zflhytlw, S-waqn37nq, S-4aovy2cm, S-kzv2kznr, S-dcbs6vpj, S-vupwsv3m, S-fqaj6jn5, S-wyfuoqs5, S-lnlroicz, S-j4qkzgvv, S-rscocily, S-b6uvvu45, S-nftrmgem, S-nxowyi4h, S-zwbgb73y, S-tdddef3t, S-qovha7ae, S-y5k6dlda, S-slmllv74, S-6foknrbi, S-3yfc6nj7, S-tx5lxmr3, S-lr3jwdq2, S-4h6wi6hb]
status: complete
---

# Throwaway git repositories in tests: local clones, templates, fast-import and automatic maintenance

## Summary
A test suite that builds a fresh git repository for each test pays for `git init`, one process per commit, and
whatever automatic housekeeping those commands trigger. Git documents cheaper ways to do the same: a local
clone of a repository built once (hard-linked objects, or `--shared` alternates), a template directory for
`git init`, one `git fast-import` process that writes a whole history as a pack, `gc.auto=0` and
`maintenance.auto=false` to stop housekeeping in repositories that live for seconds, and `GIT_CONFIG_COUNT`
to hand all of this to every git child process without a config file. `core.fsmonitor` is the opposite case:
it starts a daemon per working directory, which helps a large long-lived checkout, not a throwaway one.
Tools that read such repositories also meet three details: `git show REV:PATH` stats its argument in the working
tree (which fails on a deep Windows path without `core.longpaths`) while `git cat-file blob REV:PATH` does not;
a relative `gitdir:` path resolves against the directory of the file that holds it; and the assume-unchanged
and skip-worktree index bits make git skip checks a tool might rely on.
This repository's own suites (`_tools/tests.py`, `_tools/stress_test.py`) build such repositories; see
`python/pytest.md` and `python/pytest-xdist.md` for the test runner side.

## Facts
### Local clones
- `git clone --local` (`-l`) from a repository on the same machine skips the git transport and copies `HEAD` and everything under the objects and refs directories, hard-linking the files under `.git/objects/` when possible. [DOC S-k2jlpd4u]
- When the source is given as a local path, `--local` is the default (the flag is then a no-op); given as a URL it is ignored, and `--no-local` forces the normal transport. [DOC S-k2jlpd4u]
- A local clone fails when the source's `$GIT_DIR/objects` holds or is a symbolic link, and does not work on a repository owned by another user unless `--no-local` is given; it can race with concurrent changes to the source, like `cp -r`. [DOC S-k2jlpd4u]
- `--no-hardlinks` copies the files under `.git/objects` instead of hard-linking them. [DOC S-k2jlpd4u]
- `--shared` (`-s`) writes `.git/objects/info/alternates` so the clone uses the source's objects and starts with none of its own; the docs call it possibly dangerous: if the source later loses a commit and its objects are pruned (for example by the `git maintenance run --auto` that `git commit` triggers), the clone becomes corrupt. `git repack -a` in the clone breaks the dependency. [DOC S-k2jlpd4u]
- A template repository built once per test session and cloned locally per test gives each test its own refs, index and working tree while the object files are hard links; a test that deletes branches or rewrites history in its copy cannot damage the template, which `--shared` does not guarantee in the other direction (pruning in the template corrupts the clones). [DER S-k2jlpd4u: from the `--local` and `--shared` semantics above]

### Templates and configuration without files
- `git init` copies the files and directories of a template directory whose names do not start with a dot into the new `$GIT_DIR`; the directory is, in order, `--template`, `$GIT_TEMPLATE_DIR`, `init.templateDir`, else the built-in default (sample hooks and exclude patterns). [DOC S-nv6io42x]
- `GIT_CONFIG_COUNT` with `GIT_CONFIG_KEY_<n>` and `GIT_CONFIG_VALUE_<n>` adds configuration pairs to every git process that inherits the environment; they override configuration files but lose to `git -c`, and the docs name spawning many git commands with a common configuration as the use. [DOC S-kzv2kznr]
- `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_SYSTEM` point git at other files instead of the user's and the system's configuration (`/dev/null` skips a level); `GIT_CONFIG_NOSYSTEM` skips the system file, for a predictable environment in scripts. [DOC S-dcbs6vpj]

### Automatic maintenance
- `gc.auto` (default 6700) is the approximate count of loose objects above which `git gc --auto` packs them; some porcelain commands run `git gc --auto` now and then. Setting it to 0 turns off both the loose-object trigger and the other `gc --auto` heuristics such as `gc.autoPackLimit`. [DOC S-miw74ti3]
- `gc.autoDetach` (default true) makes `git gc --auto` return at once and continue in the background where the system supports it; it is the fallback when `maintenance.autoDetach` is unset. [DOC S-miw74ti3]
- `maintenance.auto` (default true) decides whether some commands run `git maintenance run --auto` after their normal work; `maintenance.autoDetach` decides whether that automatic maintenance runs in the background. [DOC S-waqn37nq]
- A repository that exists for one test gains nothing from housekeeping; setting `gc.auto=0` and `maintenance.auto=false` (through `GIT_CONFIG_COUNT` for every child, or in the template's config) removes the check and any detached background work that could still hold files when the test deletes its directory. [DER S-miw74ti3, S-waqn37nq, S-kzv2kznr: the defaults and the per-process configuration above]

### Index and status helpers
- `core.fsmonitor=true` starts git's built-in file system monitor daemon for that working directory, which speeds up commands that refresh the index (such as `git status`) in a working directory with many files; the built-in monitor is available only on Windows and macOS. [DOC S-zflhytlw]
- `core.untrackedCache` controls the index's untracked cache (`keep` by default, `true` adds it, `false` removes it); the docs say to check that mtime works on the system before setting `true`, and `feature.manyFiles` turns it on. [DOC S-zflhytlw]
- For a repository of a few files that lives for one test, `core.fsmonitor` adds a daemon process per working directory rather than saving time, so it stays off; its documented benefit is for large, long-lived checkouts. [DER S-zflhytlw: the daemon is per working directory and the benefit is stated for many files]

### Building history in one process
- `git fast-import` reads a command and data stream on stdin and writes one or more packfiles straight into the repository, updating branch and tag refs at EOF; it can import into an empty repository created by `git init`. [DOC S-4aovy2cm]
- The fast-import docs say its design imports large projects with minimal memory and processing time, that most bottlenecks are source access or disk IO, and that its packfiles are suboptimal until repacked, so benchmarks should not run on a fresh import before a repack. [DOC S-4aovy2cm]
- A test fixture that needs N commits can write them as one fast-import stream (one process) instead of N `git add` plus `git commit` pairs (2N processes and N automatic-maintenance checks); a test that checks commit hooks or trailers still needs real `git commit` calls. [DER S-4aovy2cm, S-waqn37nq: one process for the whole stream; `git commit` runs the hooks and the automatic maintenance]
- Git also accepts an scp-like syntax for the ssh protocol, `[<user>@]<host>:/<path-to-git-repo>`, so
  the user part is optional, and the syntax "is only recognized if there are no slashes before the first
  colon", which tells it from a local path that contains a colon. [DOC S-vupwsv3m]
- So a tool that reads a project path from `git remote -v` must accept `host:group/project` with no
  `user@` as well as `git@host:group/project` and the `ssh://` and `https://` forms. [DER S-vupwsv3m]
- `git branch -d` deletes a branch only when it is "fully merged in its upstream branch, or in HEAD if no
  upstream was set"; `-D` is "Shortcut for --delete --force" and deletes it whatever its merge state.
  [DOC S-fqaj6jn5]
- `git worktree remove` removes only a clean worktree ("no untracked files and no modification in tracked
  files"); an unclean one needs `--force`, a locked one `--force` twice, and the main worktree cannot be
  removed. [DOC S-wyfuoqs5]
- `git worktree list --porcelain` prints a format that "will remain stable across Git versions and
  regardless of user configuration", so a tool that reads which branch each worktree holds parses it.
  [DOC S-wyfuoqs5]
- Within a linked worktree, `$GIT_DIR` points to the worktree's private directory under the main
  repository's `$GIT_DIR/worktrees/` (named after the worktree's base name, a number appended when taken),
  and `$GIT_COMMON_DIR` points back to the main worktree's `$GIT_DIR`; both are set by a `.git` file at
  the linked worktree's top directory. [DOC S-j4qkzgvv]
- `git rev-parse --git-dir` shows `$GIT_DIR` (a relative path is relative to the current directory) and
  exits non-zero with a message on stderr outside a repository; `--git-common-dir` shows
  `$GIT_COMMON_DIR` if defined, else `$GIT_DIR`; `--absolute-git-dir` always prints the canonical
  absolute path. [DOC S-rscocily]
- So a tool tells a linked worktree from the main working tree by comparing `git rev-parse
  --absolute-git-dir` with the absolute form of `--git-common-dir`: they differ only in a linked
  worktree, whatever directory the worktree was created in. [DER S-j4qkzgvv, S-rscocily]
- So a cleanup that may only remove what is safe keeps `git branch -d` semantics (a branch whose every
  commit is on the integration branch) and removes a worktree without `--force`, leaving a dirty or locked
  one in place with the reason. [DER S-fqaj6jn5, S-wyfuoqs5]
- `git merge-file --union` resolves each conflict "favouring ... lines from both" sides instead of leaving
  markers (`--ours` and `--theirs` take one side). [DOC S-lnlroicz]
- So a union resolution of a source file keeps both sides' lines but not a working program: the two sides'
  definitions can still collide or break the syntax, and a resolved tool file needs a parse check that it
  keeps both sides' definitions. [DER S-lnlroicz]

### Reading a file at a revision: `git cat-file blob` and `git show`
- `git cat-file <type> <object>` prints the raw (uncompressed) contents of the object, and `<object>` takes any
  revision spelling of gitrevisions(7), so `git cat-file blob REV:PATH` prints the file at PATH in REV;
  `--textconv` and `--filters` (smudge filters, end-of-line conversion) apply only when given. [DOC S-b6uvvu45]
- `git cat-file -e <object>` prints nothing and exits zero when the object exists and is valid, non-zero with
  an error on stderr when it is malformed. [DOC S-b6uvvu45]
- `git show` on a plain blob prints its plain contents; on a commit it prints the log message and diff, on a
  tree the names in it. [DOC S-nftrmgem]
- `git cat-file` resolves its object name with `get_oid_with_context` and makes no working-tree check of the
  argument, while `git show` parses its arguments through `setup_revisions`, whose revision handling calls
  `verify_non_filename` on each revision argument not marked as one (no `--` after it). [CODE S-tdddef3t:
  builtin/cat-file.c#cat_one_file; CODE S-xcnkwrn4: builtin/log.c#cmd_show; CODE S-zwbgb73y:
  revision.c#handle_revision_arg_1]
- Inside a working tree, `verify_non_filename` runs `lstat` on the whole argument (`HEAD:kb/x.md`, prefixed
  with the current subdirectory) to refuse a revision that is also a file name; `check_filename` treats only
  `ENOENT` and `ENOTDIR` as "no such file" and dies with `failed to stat '<arg>'` on any other error.
  [CODE S-nxowyi4h: setup.c#check_filename; CODE S-qovha7ae: git-compat-util.h#is_missing_file_error]
- `core.longpaths` is a Git for Windows setting that enables long path (more than 260 characters) support for
  builtin commands; it is off by default because Windows Explorer, `cmd.exe` and the Git for Windows tool chain
  (msys, bash, tcl, perl) do not support long paths. [DOC S-y5k6dlda]
- In Git for Windows, `lstat` converts its path with `xutftowcs_long_path`: a path whose length plus the
  current directory's reaches `MAX_PATH` (260) is turned into a `\\?\` absolute path only when
  `core.longpaths` is on, and fails with `ENAMETOOLONG` ("Filename too long") when it is off. [CODE
  S-hnrqsiz4: compat/mingw.c#mingw_lstat; CODE S-slmllv74: compat/mingw.h#xutftowcs_long_path]
- So in a deep Windows checkout without `core.longpaths`, `git show REV:PATH` can die before reading any
  object, because its `lstat` of the argument fails with `ENAMETOOLONG`, while `git cat-file blob REV:PATH`
  reads the same blob from the object database without touching the working tree; a tool that reads a file
  at a revision uses `cat-file blob` (or puts `--` after the revision for commands that take one). [DER
  S-tdddef3t, S-zwbgb73y, S-nxowyi4h, S-slmllv74: no filename check in cat-file; the lstat and its
  long-path failure in show]

### Worktree links: `gitdir:` files
- A plain text `.git` file at the root of a working tree containing `gitdir: <path>` points at the real
  repository directory (a "gitfile"), usually managed by `git submodule` and `git worktree`. [DOC S-6foknrbi]
- When reading a `.git` file, git resolves a relative `gitdir:` path against the directory that holds the
  `.git` file (the path up to its last `/`), checks that the result is a git directory, and then uses its
  real path. [CODE S-nxowyi4h: setup.c#read_gitfile_gently]
- `$GIT_DIR/commondir`, when present, sets `$GIT_COMMON_DIR` unless it is set explicitly, and a relative path
  in it is relative to `$GIT_DIR`. [DOC S-6foknrbi]
- `worktrees/<id>/gitdir` points back to the linked worktree's `.git` file and is used to tell whether the
  worktree was removed by hand; gitrepository-layout(5) at v2.55.0 still describes it as an absolute path.
  [DOC S-6foknrbi]
- `git worktree add --relative-paths` (or `worktree.useRelativePaths=true`, default false) links worktrees
  with relative paths, which implies `extensions.relativeWorktrees` and makes the repository unusable by older
  Git versions; `git worktree repair` rewrites the links when they do not match the absolute/relative
  setting. [DOC S-j4qkzgvv, S-3yfc6nj7]
- When `worktrees/<id>/gitdir` holds a relative path, git resolves it against the `worktrees/<id>/`
  directory that holds the file (not the current directory and not the worktree), then strips `/.git` to get
  the worktree's path. [CODE S-tx5lxmr3: worktree.c#get_linked_worktree]
- So a tool that reads these files itself resolves a relative `gitdir:` in a worktree's `.git` file against
  that file's directory and a relative path in `worktrees/<id>/gitdir` against `worktrees/<id>/`; asking git
  (`git rev-parse --absolute-git-dir`, `git worktree list --porcelain`) avoids both rules. [DER S-nxowyi4h,
  S-tx5lxmr3, S-rscocily, S-wyfuoqs5]

### Index bits: `--assume-unchanged` and `--skip-worktree`
- `git update-index --assume-unchanged` leaves the paths' recorded object names alone and sets their "assume
  unchanged" bit: the user promises not to change the file, and git may assume the working tree file matches
  the index; changing the file needs the bit unset (`--no-assume-unchanged`). [DOC S-lr3jwdq2]
- With the assume-unchanged bit set git omits checking the file and assumes it has not changed, so a later
  edit can go unnoticed (it is free to record a change it can see without stat'ing the file); git fails
  gracefully when it must change such a file in the index, as in a merge. [DOC S-lr3jwdq2]
- `--really-refresh` checks stat information regardless of the assume-unchanged bit; `core.ignorestat=true`
  sets the bit automatically on paths that `git update-index`, `git apply --index`, `git checkout-index -u`
  or `git read-tree -u` update. [DOC S-lr3jwdq2]
- `--skip-worktree` likewise leaves the object names alone and sets the skip-worktree bit: git avoids writing
  the file to the working directory when reasonably possible and treats it as unchanged when it is absent, so
  `git add -u` and `git commit -a` do not record its deletion; not all commands honour the bit, and merges or
  rebases with conflicts may write the file anyway. [DOC S-lr3jwdq2]
- The skip-worktree bit exists for sparse checkouts, for which `git sparse-checkout` is the recommended
  interface; in a sparse checkout, a skip-worktree file found present in the working tree has its bit
  cleared. [DOC S-lr3jwdq2]
- The docs warn that neither bit is a way to ignore changes to tracked files, since git may still compare
  working tree files with the index in some operations, and say git provides no such way. [DOC S-lr3jwdq2]
- `git ls-files -t` tags a skip-worktree file `S` (a plain tracked file `H`), and `git ls-files -v` prints
  lowercase tags for files marked assume unchanged. [DOC S-4h6wi6hb]
- So a check that compares the working tree with the index or a revision cannot rely on `git status` or `git
  diff` to report an edit to an assume-unchanged path or the absence of a skip-worktree path; it lists such
  paths with `git ls-files -v` (lowercase or `S` tags) or compares content directly. [DER S-lr3jwdq2,
  S-4h6wi6hb]

## Reference
- Related: `python/pytest.md` (session fixtures, `tmp_path_factory`, `--durations`), `python/pytest-xdist.md` (a session fixture runs once per worker), `python/stdlib-windows-portability.md` (process start on Windows), `gitlab/git-trailers-and-hooks.md` (what `git commit` runs), `windows/dev-drive.md` (where the repositories live on Windows).
- SNIPPET: give every git child of a test the same throwaway-repository settings without writing a config file; context: Python `subprocess`, Git as documented at v2.55.0; checked: syntax [DOC S-kzv2kznr: `GIT_CONFIG_COUNT`/`KEY`/`VALUE` pairs; DOC S-miw74ti3, S-waqn37nq: `gc.auto=0`, `maintenance.auto=false`]
```python
import os

def git_env(base=None):
    env = dict(base or os.environ)
    pairs = [("gc.auto", "0"), ("maintenance.auto", "false"), ("core.fsmonitor", "false")]
    env["GIT_CONFIG_COUNT"] = str(len(pairs))
    for i, (k, v) in enumerate(pairs):
        env[f"GIT_CONFIG_KEY_{i}"], env[f"GIT_CONFIG_VALUE_{i}"] = k, v
    return env
```

## Examples
- A session-scoped fixture builds `template/` once (init, three commits, a hook), then each test runs `git clone -q template <tmp_path>/repo`; the objects are hard links, and the test's commits land only in its copy.
- A fixture that needs a 50-commit history writes a fast-import stream (`commit refs/heads/main`, `mark`, `committer jan.kowalski <jan.kowalski@corp.example.com> ...`, `data`, `M 100644 inline file.txt`) and runs `git fast-import --quiet` once, then `git checkout main`.
