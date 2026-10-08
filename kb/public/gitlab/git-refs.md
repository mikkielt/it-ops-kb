---
topic: gitlab/git-refs
priority: P3
applies_to: "git v2.55.0 documentation (git/git tag v2.55.0): git-update-ref and git-for-each-ref with its included options page; the observed exit statuses and outputs were run with git 2.50.1 (Apple Git-155) on macOS"
retrieved_utc: 2026-10-08
sources: [S-sgbkwka4, S-cacomkjs, S-xahbgevi]
status: complete
---

# Git refs from scripts: update-ref to create and delete, for-each-ref to list

## Summary
A tool that keeps markers as refs under its own namespace (for example `refs/kb-reopened/<id>`) needs
two plumbing commands. `git update-ref` writes and deletes one ref safely: `git update-ref -d <ref>`
deletes it, and `git update-ref -d <ref> <old-oid>` deletes it only if it still holds `<old-oid>`;
the create form takes an all-zeroes or empty old value to require that the ref does not exist yet, and
`--stdin` applies several updates all together or not at all. `git for-each-ref` lists the refs that
match a pattern, where a pattern matches by `fnmatch` or literally from the start up to a slash, so
`refs/kb-reopened/` lists the whole namespace; `--format=%(refname:lstrip=2)` prints each name
without its first two components. The git pages state no exit status for either command; the observed
ones below come from one local run. Facts are from the git 2.55.0 documentation;
`gitlab/git-trailers-and-hooks.md` covers pushing refs and the hooks.

## Facts
- `git update-ref -d <ref> [<old-oid>]` deletes the named ref after verifying that it still contains `<old-oid>`; the synopsis also accepts `-m <reason>` and `--no-deref` with `-d`. [DOC S-sgbkwka4]
- `git update-ref <ref> <new-oid> <old-oid>` stores `<new-oid>` only if the ref's current value matches `<old-oid>`; 40 `0` characters or an empty string as `<old-oid>` makes sure the ref being created does not exist. With two arguments it stores `<new-oid>` without a check. [DOC S-sgbkwka4]
- `update-ref` follows symbolic refs by default; with `--no-deref` the named ref itself is overwritten instead of the ref it points to. Without options it does not repoint a symbolic ref (that is `git symbolic-ref`, or the `symref-*` commands of `--stdin`). [DOC S-sgbkwka4]
- With `--stdin`, `update-ref` reads one command per line (`update`, `create`, `delete`, `verify`, `symref-*`, `option`, `start`, `prepare`, `commit`, `abort`); `delete SP <ref> [SP <old-oid>]` deletes the ref after verifying that it exists with `<old-oid>` when given, and a given `<old-oid>` may not be zero. `-z` switches to NUL-terminated fields without quoting. [DOC S-sgbkwka4]
- In `--stdin` mode, `verify` checks a ref against `<old-oid>` without changing it, and a zero or missing `<old-oid>` means the ref must not exist; `create` requires the ref not to exist and a non-zero `<new-oid>`; a repeated ref or a malformed command is an error. [DOC S-sgbkwka4]
- In `--stdin` mode all modifications are performed only if every ref can be locked with its matching `<old-oid>` at the same time, otherwise none is; each ref changes atomically, but a concurrent reader may still see a subset of the changes. `start`, `prepare` (takes the lock files), `commit` and `abort` make an explicit transaction, which aborts when the session ends without `commit`. [DOC S-sgbkwka4]
- `--batch-updates` instead lets individual updates fail on invalid or incorrect input and applies the rest, reporting each failure as a `rejected` line; a system error (I/O, memory) still fails the whole batch. [DOC S-sgbkwka4]
- `update-ref` appends to the reflog `$GIT_DIR/logs/<ref>` only when `core.logAllRefUpdates` is true and the ref is under `refs/heads/`, `refs/remotes/`, `refs/notes/` or is a pseudoref such as `HEAD`, or when that log file already exists; `--create-reflog` creates one anyway, and `-m <reason>` adds a message to the log line. An update fails without changing the ref if the log cannot be written or no committer identity is available. [DOC S-sgbkwka4]
- A ref under a namespace of its own such as `refs/kb-reopened/` is outside the three directories that the logging rule names, so `update-ref` keeps no reflog for it unless `--create-reflog` is given or the log file exists. [DER S-sgbkwka4: the logging rule names only `refs/heads/`, `refs/remotes/`, `refs/notes/` and pseudorefs]
- The git-update-ref page states no exit status. With git 2.50.1 (Apple Git-155) on macOS, run 2026-10-08 in a scratch repository: `git update-ref -d <ref> <old-oid>` with a wrong `<old-oid>` exited 1 with `error: cannot lock ref '<ref>': is at <oid> but expected <old-oid>` and kept the ref; with the right `<old-oid>` it exited 0; `git update-ref -d <ref>` without an old value exited 0 both for an existing ref and again for the same ref once deleted; the create form `git update-ref <ref> <oid> ""` on a ref that already existed exited 128 with `fatal: update_ref failed for ref '<ref>': cannot lock ref '<ref>': reference already exists`. Other git versions and operating systems were not run. [DER S-sgbkwka4: observed by running the documented `-d` forms with git 2.50.1]
- `git for-each-ref` shows every ref that matches at least one `<pattern>`, matched either with `fnmatch(3)` or literally, a literal pattern matching completely or from the beginning up to a slash; with no pattern it shows all refs. `--exclude=<pattern>` drops matching refs by the same rules, and `--stdin` reads the patterns from standard input. [DOC S-xahbgevi, S-cacomkjs]
- So `refs/kb-reopened/` and `refs/kb-reopened` both list every ref in that namespace, while `refs/kb-re` lists none of them because it does not end at a slash; with git 2.50.1 (Apple Git-155) on macOS, run 2026-10-08, exactly that was printed, and a namespace with no refs printed nothing and exited 0. [DER S-xahbgevi: literal patterns match completely or up to a slash; observed by running the three patterns with git 2.50.1]
- `--format=<format>` interpolates `%(fieldname)` for each ref and the object it points at; `%%` is a literal `%` and `%xx` the character with hex code `xx` (`%00` NUL, `%09` TAB, `%0a` LF). The default format is `%(objectname) SPC %(objecttype) TAB %(refname)`. [DOC S-xahbgevi]
- `%(refname)` is the ref's name after `$GIT_DIR/` (the full `refs/...` name); `:short` gives a non-ambiguous short name, and `:lstrip=<n>` (`:rstrip=<n>`) strips `<n>` slash-separated components from the front (back), so `%(refname:lstrip=2)` turns `refs/tags/foo` into `foo`; `strip` is a synonym of `lstrip`. [DOC S-cacomkjs]
- A negative `<n>` keeps `-<n>` components from the stripped end (`%(refname:lstrip=-2)` turns `refs/tags/foo` into `tags/foo`); when the ref has too few components, a positive `<n>` gives an empty string and a negative one the full refname, and neither is an error. [DOC S-cacomkjs]
- `--sort=<key>` sorts on a field (prefix `-` for descending), defaults to `refname`, and when repeated the last key is the primary one; `--count=<n>` stops after `<n>` refs; `--shell`, `--perl`, `--python` and `--tcl` quote each interpolated value as a string literal of that language for `eval`. [DOC S-xahbgevi]
- A field that does not apply to the object a ref points at expands to an empty string instead of causing an error; `--omit-empty` prints no newline for a ref whose format expands to an empty string. [DOC S-cacomkjs, S-xahbgevi]
- `--start-after=<marker>` pages through the output by skipping refs up to and including the marker, and cannot be combined with `--sort`, `--stdin` or pattern arguments. [DOC S-xahbgevi]
- A tool that keeps one marker ref per item under its own namespace can create it with `git update-ref <ref> <oid> ""` (fails if it already exists), list the ids with `git for-each-ref --format=%(refname:lstrip=2) refs/<namespace>/`, and delete it with `git update-ref -d <ref> <oid>` so that a marker someone moved in the meantime is not removed; a plain `-d <ref>` also succeeded on an already deleted ref with git 2.50.1, so a cleanup that must stay quiet on a missing ref need not pass the old value (unconfirmed for other versions, see `_gaps.md`). [DER S-sgbkwka4, S-xahbgevi, S-cacomkjs: composed from the create, delete and pattern rules above and the 2026-10-08 run with git 2.50.1]

## Reference
| Need | Command | Source |
|---|---|---|
| delete a ref | `git update-ref -d <ref>` | S-sgbkwka4 |
| delete only if unchanged | `git update-ref -d <ref> <old-oid>` | S-sgbkwka4 |
| create only if absent | `git update-ref <ref> <new-oid> ""` | S-sgbkwka4 |
| several updates, all or none | `git update-ref --stdin` | S-sgbkwka4 |
| list a namespace | `git for-each-ref refs/<namespace>/` | S-xahbgevi |
| names without the prefix | `--format=%(refname:lstrip=2)` | S-cacomkjs |

See also `gitlab/git-trailers-and-hooks.md` (pushing refs, `--force-with-lease`, the hooks) and `gitlab/git-test-repositories.md` (scratch repositories for such runs).

## Examples
- SNIPPET: keep, list and remove one marker ref per item under a namespace of its own; context: git 2.x, POSIX shell, inside a repository with at least one commit; checked: run (git 2.50.1, Apple Git-155, macOS, 2026-10-08, scratch repository) [DER S-sgbkwka4, S-cacomkjs: the create, `-d` and `lstrip` forms as documented]
```console
$ git update-ref refs/kb-reopened/ST-00000000 HEAD ""
$ git for-each-ref --format='%(refname:lstrip=2)' refs/kb-reopened/
ST-00000000
$ git update-ref -d refs/kb-reopened/ST-00000000
```
