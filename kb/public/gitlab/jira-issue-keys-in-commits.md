---
topic: gitlab/jira-issue-keys-in-commits
priority: P3
applies_to: "Jira Cloud support pages Process work items with smart commits (modified 2025-10-07) and Reference work items in your development spaces (modified 2026-05-29); GitLab Jira issues integration (doc/ of gitlab-org/gitlab master at a9490a0e, 2026-10-10); the trailer reading was run with git 2.50.1 on macOS, not against a Jira site"
retrieved_utc: 2026-10-10
sources: [S-kzztizwv, S-hmqwtvjy, S-pnktrw4x]
status: partial
---

# Jira issue keys in commit messages: links, smart commits and GitLab's Jira integration

## Summary
A Jira work item key (two or more uppercase letters, a hyphen, a number, such as `PROJ-123`) anywhere in a commit message links the commit to that work item's development panel once the repository is connected to Jira; GitLab does the same on its side when its Jira integration is on. Lowercase keys are not recognised. A smart commit goes further: on one line of the message, the key followed (after any text) by `#comment`, `#time` or a `#<transition>` command makes Jira act on the work item. The documented unit is a line of the message text; the two Atlassian pages say nothing about git trailers, so a trailer line such as `KB-Ref: PROJ-123` is read by the line rule, not by a trailer rule: it links the commit and, without a `#command` on the same line, triggers nothing. Smart commits need the committer's email to match exactly one Jira user. GitLab separately closes a Jira issue from a keyword plus key on the default branch when transitions are configured. For GitLab's own issue references see `gitlab/issue-closing-patterns.md`.

## Facts
- Smart commits support only the default Jira key format: two or more uppercase letters, a hyphen and the work item number, for example `JRA-123`. [DOC S-kzztizwv]
- A key must be written with capital letters (`JRA-123`, not `jra-123`) or the development information does not appear in Jira; the Cloud pages call an issue a work item and its key a work item key. [DOC S-hmqwtvjy]
- Including the key in a commit message (`git commit -m "JRA-123 <summary>"`) links the commit to the work item's development panel; the same works for a branch name (`JRA-123-<branch-name>`) and a pull request title. This works by default for connected Bitbucket, GitLab, GitHub, GitHub Enterprise and Fisheye. [DOC S-hmqwtvjy]
- The link needs a Jira admin to have connected the development tool, the **View development tools** space permission for whoever looks, and a push to the connected repository; a full sync can take a few minutes. [DOC S-hmqwtvjy]
- A pull request links to the work item through the key in its title, or in its source branch name, or (Bitbucket Cloud only) through a non-merge commit in it that holds the key. [DOC S-hmqwtvjy]
- The basic smart commit syntax is `<ignored text> <ISSUE_KEY> <ignored text> #<COMMAND> <optional COMMAND_ARGUMENTS>`; any text between the key and the command is ignored. [DOC S-kzztizwv]
- Three commands exist: `#comment <text>` adds a comment, `#time <value>w <value>d <value>h <value>m <text>` logs work (decimals allowed, the text goes into the work log), and `#<transition_name>` moves the work item to a workflow status. [DOC S-kzztizwv]
- A smart commit command must not span more than one line, but several commands can share a line (`JRA-123 #time 2d 5h #comment Task completed #resolve`). [DOC S-kzztizwv]
- Each line of the message must carry the key to be read as a command: in a comment wrapped onto a second line, the part on the second line and a `#time` after it are dropped because that line has no key. [DOC S-kzztizwv]
- Several keys on one line, separated by whitespace or commas, make one command apply to all of them (`JRA-123 JRA-234 JRA-345 #resolve`). [DOC S-kzztizwv]
- A transition command uses only the part of the transition name before its first space (`#finish` for `finish work`); an ambiguous prefix must be written fully with hyphens (`#start-review`). [DOC S-kzztizwv]
- `#resolve` through a smart commit cannot set the Resolution field, a transition fails silently when another field is required, and `#comment` must be left out when the Jira admin made the comment field required. [DOC S-kzztizwv]
- The committer's email in the commit data must match exactly one Jira user with the permission for the action; on a mismatch the action fails but the commit still succeeds and shows on the work item, and Jira emails the user (rarely nobody, a silent failure). [DOC S-kzztizwv]
- A history rewrite (`git push --force`, `git merge --squash`) creates new commits whose same smart commit commands run again, so they appear duplicated. [DOC S-kzztizwv]
- Smart commit commands should not be put in a pull request title that ends up in the merge commit message; the page advises editing the merge commit message by hand instead. [DOC S-kzztizwv]
- The two Atlassian pages define the reference as the key somewhere in the commit message and a smart commit as a line of text; neither page mentions git trailers or a trailer block. [UNK: what Jira does with a trailer line is documented only by the line rule; no Jira site was available to test it]
- A trailer line such as `KB-Ref: PROJ-123` holds a well-formed key, so by the documented rule it links the commit to `PROJ-123`; with no `#command` after the key on that line it triggers no smart commit action, while `KB-Ref: PROJ-123 #close` would be a transition command line. [DER S-kzztizwv, S-hmqwtvjy: the key-anywhere and one-line command rules applied to a trailer line; not tested against Jira]
- `git interpret-trailers --parse` returns `KB-Ref: PROJ-123` as a trailer when the line sits in the message's last paragraph, so a reader that wants only the key can take it from there. [DER S-kzztizwv: observed by running `--parse` with git 2.50.1 on macOS on a message whose last paragraph holds `KB-Ref` and `KB-Work` lines]
- On the GitLab side, Jira issue IDs written in GitLab commits and merge requests must be uppercase, and a mention of a Jira issue in a GitLab issue, merge request, comment or commit makes GitLab link to the Jira issue and add a formatted comment and a web link back on it. [DOC S-pnktrw4x]
- Only one cross-reference appears in Jira per GitLab issue, merge request or commit, however many comments mention the key; **Enable comments** cleared on the integration turns the comment off while the cross-link stays. [DOC S-pnktrw4x]
- With GitLab transition IDs configured, a trigger word plus a Jira key (`Resolves PROJECT-1`, `Closes PROJECT-1`, `Fixes PROJECT-1`) in a commit or merge request closes the Jira issue when it targets the project's default branch; a branch name that matches the key appends `Closes <JIRA-ID>` to the merge request template. [DOC S-pnktrw4x]
- GitLab's key matching can be changed per project under **Settings** > **Integrations** > **Jira issues**: a regular expression (RE2 syntax) or a prefix, so that with the prefix `JIRA#` the key `ALPHA-1` is matched as `JIRA#ALPHA-1`. [DOC S-pnktrw4x]
- On Ultimate, the merge check **Require an associated issue from Jira** blocks a merge request that mentions no Jira key in its title or description, with the message that a key must be mentioned there. [DOC S-pnktrw4x]

## Reference
| Need | Text | Effect | Source |
|---|---|---|---|
| link a commit to a work item | `PROJ-123 message` or `KB-Ref: PROJ-123` | development panel link | S-hmqwtvjy, S-kzztizwv |
| comment | `PROJ-123 #comment text` | comment added | S-kzztizwv |
| log time | `PROJ-123 #time 1w 2d 4h 30m text` | work logged | S-kzztizwv |
| transition | `PROJ-123 #close #comment text` | status change | S-kzztizwv |
| several work items | `PROJ-1 PROJ-2 #resolve` | each is resolved | S-kzztizwv |
| close from GitLab | `Closes PROJ-123` on the default branch | Jira issue closed (transitions configured) | S-pnktrw4x |

See also `gitlab/issue-closing-patterns.md`, `gitlab/git-trailers-and-hooks.md` (what git reads as a trailer) and `gitlab/automated-merge-requests.md` (the merge check **Jira link**).

## Examples
- SNIPPET: a commit message that references a Jira work item in a trailer; context: any git with `interpret-trailers --parse`, `PROJ-123` a placeholder key; checked: run (git 2.50.1 on macOS: `--parse` printed both trailer lines; the Jira side is not tested) [DER S-kzztizwv, S-hmqwtvjy: a key anywhere in the message links the commit]
```text
fix(kb): subject

body

KB-Ref: PROJ-123
KB-Work: ST-00000000
```
- SNIPPET: a smart commit line that comments on a work item and moves it to a status; context: Jira smart commits enabled, committer email matching one Jira user, a transition named `close`; checked: no [DOC S-kzztizwv: the transition syntax `<ISSUE_KEY> #<transition_name> #comment <text>`]
```text
PROJ-123 #close #comment corrected the indent
```
