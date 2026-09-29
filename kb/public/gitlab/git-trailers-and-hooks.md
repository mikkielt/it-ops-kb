---
topic: gitlab/git-trailers-and-hooks
priority: P3
applies_to: "git v2.55.0 documentation (git/git tag v2.55.0): git-interpret-trailers, pretty-formats, git-commit, git-push, githooks, trailer.* configuration; the parse examples were run with a local git; behaviour is the same on GitHub and GitLab remotes because the trailer rules are client-side"
retrieved_utc: 2026-09-29
sources: [S-wtbq3lvm, S-d6iv4nbm, S-ziyhuwyc, S-wjfrtzpf, S-7dwkyip6, S-l6s4hfqp]
status: complete
---

# Git commit trailers and the commit-msg and pre-push hooks

## Summary
Git reads a trailer only inside the trailer block: the last group of lines of the commit message, set off from the text above it by a blank line. A `Key: value` line in an earlier paragraph is plain text: `git interpret-trailers --parse` and `git log --format=%(trailers)` do not return it. A group that mixes prose and trailers counts only when it holds a trailer git generates itself (`Signed-off-by`) or one the user configured, and at least a quarter of its lines are trailers; a `Co-Authored-By`, `Claude-Session` or `KB-Work` line is neither, so such a mixed group is not a trailer block. Adding a trailer with `--trailer` skips an identical neighbouring one by default, so repeating the command leaves the message unchanged. The `commit-msg` hook runs with the message file as its one argument and is skipped by `git commit --no-verify`; the `pre-push` hook receives the remote's name and location as arguments and one line per ref on standard input, and is skipped by `git push --no-verify`. A check that must hold for every push therefore cannot rest on these hooks alone.

## Facts
- A trailer is a key-value pair with a colon as the separator; the key is ASCII alphanumerics and hyphens, and a trailer block is one or more trailers preceded by a blank line (empty or whitespace-only). [DOC S-wtbq3lvm]
- Existing trailers are the last group of lines of the message that is all trailers, or that holds at least one Git-generated or user-configured trailer and is at least 25% trailers. [DOC S-wtbq3lvm]
- The trailer group must be preceded by one or more empty or whitespace-only lines, and must be at the end of the input or the last non-whitespace lines before a line that starts with `---`. [DOC S-wtbq3lvm]
- When reading, no whitespace may stand before or inside the key, spaces and tabs are allowed between the key and the separator, and a value may continue on following lines that start with whitespace (folding). [DOC S-wtbq3lvm]
- `--parse` is an alias for `--only-trailers --only-input --unfold`: it prints only the trailers found in the input, unaffected by command-line trailers or `trailer.*` configuration, one line per trailer. [DOC S-wtbq3lvm]
- `git log --format` placeholder `%(trailers)` shows the trailers of the body as `git interpret-trailers` interprets them; options after a colon include `key=<key>` (case-insensitive, trailing colon optional, implies `only`), `only`, `unfold=true`, `valueonly`, `keyonly` and `separator=<sep>`. [DOC S-d6iv4nbm]
- `git interpret-trailers --trailer <key>:<value>` appends the new trailer after the existing ones, adds a blank line before it when there is none, and starts a new trailer block when the message has none. [DOC S-wtbq3lvm]
- `git commit --trailer <token>[(=|:)<value>]` adds a trailer to the commit message; the `trailer.*` configuration decides whether a duplicate is omitted and where in the run of trailers it goes. [DOC S-ziyhuwyc]
- `trailer.ifexists` defaults to `addIfDifferentNeighbor`: a new trailer is added only when no trailer with the same key and value sits directly above or below the place it would go; `addIfDifferent` checks the whole block, `add` always adds, `replace` swaps the closest same-key trailer, `doNothing` adds nothing when the key exists. [DOC S-wjfrtzpf]
- A `commit-msg` hook takes one argument, the name of the file holding the proposed message, aborts the commit on a non-zero exit, may edit the file in place, and can be bypassed with `--no-verify`. [DOC S-7dwkyip6]
- `prepare-commit-msg` is not suppressed by `--no-verify`, but its non-zero exit only aborts the commit and it is not meant to replace `pre-commit`. [DOC S-7dwkyip6]
- Hooks are read from `$GIT_DIR/hooks/` or from the directory `core.hooksPath` names; git commit hooks run with `GIT_EDITOR=:` when no editor will open. [DOC S-7dwkyip6]
- A `pre-push` hook gets two arguments, the destination remote's name and location (both the same when no named remote is used), and for each ref to push one stdin line `<local-ref> <local-object-name> <remote-ref> <remote-object-name>`. [DOC S-7dwkyip6]
- In a `pre-push` stdin line the remote object name is all zeroes when the remote ref does not exist yet, and a deleted ref shows `(delete)` as the local ref with an all-zeroes local object name. [DOC S-7dwkyip6]
- A non-zero exit of `pre-push` stops `git push` before anything is sent, and the reason can be written to standard error. [DOC S-7dwkyip6]
- `git push --no-verify` bypasses the `pre-push` hook completely. [DOC S-l6s4hfqp]
- A mixed group is not a trailer block when its only trailers are `KB-Work`, `Co-Authored-By` or `Claude-Session`, because none is Git-generated and none is configured; `git interpret-trailers --parse` on such a group prints nothing. [DER S-wtbq3lvm: the 25% rule requires a Git-generated or user-configured trailer; confirmed by running `--parse` on three messages with git]
- A `KB-Work:` line followed by a blank line and a `Co-Authored-By:` paragraph is read as trailers only for the last paragraph: `--parse` prints the `Co-Authored-By` and `Claude-Session` lines and omits `KB-Work`. [DER S-wtbq3lvm: the group must be at the end of the message, preceded by a blank line; confirmed by running `--parse`]
- A check that reads trailers should call `git interpret-trailers --parse` (or `git log --format=%(trailers:key=<Key>,valueonly)`) instead of matching lines with a regular expression, so its verdict is the one git gives. [DER S-wtbq3lvm, S-d6iv4nbm: both apply the same parsing rules]
- A rule enforced only in `commit-msg` and `pre-push` is skipped by `--no-verify`, so the same rule must also run where the bypass does not reach (a CI job, or the tool that pushes). [DER S-7dwkyip6, S-ziyhuwyc, S-l6s4hfqp: each names `--no-verify` as bypassing the hook]
- To judge only commits not yet on the remote's main, a `pre-push` hook reads the remote object name from its stdin lines (all zeroes for a new ref) and lists `<remote-object>..<local-object>`, or `origin/main..<local-object>` for a new ref. [DER S-7dwkyip6: stdin line format and the zero name for a missing remote ref]
- Repeated automation that adds a trailer stays convergent with the default `addIfDifferentNeighbor` only while the value is the same: a changing value (a new date or run id) adds another trailer each run, so an idempotent writer uses `--if-exists replace` or `doNothing`. [DER S-wjfrtzpf: the four `ifexists` actions and their conditions]

## Reference
| Need | Command | Source |
|---|---|---|
| list a message's trailers | `git interpret-trailers --parse < msg` | S-wtbq3lvm |
| trailers of one commit | `git log -1 --format=%(trailers) <rev>` | S-d6iv4nbm |
| one trailer's values | `git log --format=%(trailers:key=KB-Work,valueonly)` | S-d6iv4nbm |
| add a trailer at commit | `git commit --trailer "Key: value"` | S-ziyhuwyc |
| replace instead of append | `--if-exists replace` / `trailer.ifexists` | S-wjfrtzpf |
| skip commit hooks | `git commit --no-verify` | S-ziyhuwyc |
| skip pre-push | `git push --no-verify` | S-l6s4hfqp |

See also `gitlab/automated-merge-requests.md` (push refusals, server-side hooks, `git push -o`), `gitlab/protected-branches-tags.md`.

## Examples
- SNIPPET: read the trailers of a commit message exactly as git does; context: git 2.55 (any release with `--parse`), message on stdin; checked: run (local git; prints the two trailers of the last paragraph and omits the `KB-Work` line above them) [DER S-wtbq3lvm: `--parse` is `--only-trailers --only-input --unfold`]
```bash
printf 'subject\n\nbody\n\nKB-Work: ST-00000000\n\nCo-Authored-By: Jan Kowalski <jan.kowalski@corp.example.com>\nClaude-Session: https://example.com/session\n' | git interpret-trailers --parse
```
