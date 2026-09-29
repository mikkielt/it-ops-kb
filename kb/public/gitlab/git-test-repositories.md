---
topic: gitlab/git-test-repositories
priority: P3
applies_to: "Git 2.55.0 (documentation at the v2.55.0 tag): throwaway repositories built by test suites (local clones, templates, fast-import, automatic maintenance, per-process configuration)"
retrieved_utc: 2026-09-29
sources: [S-k2jlpd4u, S-nv6io42x, S-miw74ti3, S-zflhytlw, S-waqn37nq, S-4aovy2cm, S-kzv2kznr, S-dcbs6vpj]
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
