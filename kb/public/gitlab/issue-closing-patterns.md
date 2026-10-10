---
topic: gitlab/issue-closing-patterns
priority: P3
applies_to: "GitLab (GitLab.com, Self-Managed, Dedicated; Free, Premium, Ultimate): doc/ of gitlab-org/gitlab master at a9490a0e (2026-10-10), the pages Manage issues, Crosslinking issues, Issue closing pattern and GitLab Flavored Markdown; the pattern checks were run with Python 3.13.2's re module on macOS"
retrieved_utc: 2026-10-10
sources: [S-qxksc6ah, S-a57i2q6g, S-xdfirawc, S-ww5ecjfc, S-pnktrw4x]
status: complete
---

# GitLab issue references and closing patterns in commits and merge request descriptions

## Summary
A commit message or a merge request description closes an issue only when it holds a closing keyword (`Close`, `Fix`, `Resolve` or `Implement` in their listed forms) followed by an issue reference, and only when the commit is pushed to, or the merge request is merged into, the project's default branch. A bare mention (`#17`, `Related to #5`) links the issue and the merge request but never closes it. The reference after the keyword is local (`#123`), cross-project (`group/project#123`) or a full URL. The matching is a regular expression over the text, so it has no sense of negation. A project can switch auto-closing off; only an instance administrator of a Self-Managed install can change the pattern. Jira issue keys have their own article: `gitlab/jira-issue-keys-in-commits.md`.

## Facts
- A commit message or merge request description that contains text matching the closing pattern closes every issue referenced in the matched text when the commit is pushed to the default branch or the commit or merge request is merged into it. [DOC S-qxksc6ah]
- The documented keywords are `Close`, `Fix`, `Resolve` and `Implement`, each with its `-s`, `-d` (or `-ed`) and `-ing` forms, written either all lowercase or with the first letter capitalised. [DOC S-qxksc6ah]
- A keyword takes an issue reference in one of these forms: a local issue (`#123`), a cross-project issue (`group/project#123`), the full URL of an issue, or the full URL of a work item (task, objective, key result) in a project or in a group; work item references were introduced in GitLab 17.3. [DOC S-qxksc6ah]
- One merge request description line `Closes #4, #6, Related to #5` closes `#4` and `#6` when the merge request is merged, and marks `#5` as a related issue without closing it. [DOC S-qxksc6ah]
- One commit message with `Fix #20, Fixes #21 and Closes group/otherproject#22`, `fixes #18, #19` and a full issue URL closes the local issues `#18` to `#21` and the issues in `group/otherproject`; a `#17` that follows no keyword is not closed. [DOC S-qxksc6ah]
- The pattern works in multi-line commit messages and in one-liners given to `git commit -m`. [DOC S-qxksc6ah]
- For performance reasons, automatic issue closing is turned off for the very first push of an existing repository. [DOC S-qxksc6ah]
- Users can put closing patterns in the merge request description and in a commit message body; the merge request widget shows the issues that will close on merge in both cases, and the user who merges is responsible for checking that closing them is appropriate. [DOC S-qxksc6ah]
- When a merge request is merged, GitLab checks that the merging user may close the issues a closing pattern targets; the check matters in public repositories because external users can create merge requests and commits that carry closing patterns. [DOC S-qxksc6ah]
- An issue can be linked to a merge request for closing without a closing pattern, through the GraphQL API or the merge request's **Work items** widget; the permission is checked when the link is created, and the link persists even if the user later loses access to the issue's project. [DOC S-qxksc6ah]
- When auto-merge is turned on for a merge request, the list of issues it closes can no longer be changed. [DOC S-qxksc6ah]
- Automatic issue closing is turned off per project under **Settings** > **Repository** > **Branch defaults** (checkbox **Auto-close referenced issues on default branch**; Maintainer or Owner role); it applies only to issues of that project, whose merge requests and commits can still close another project's issues. [DOC S-qxksc6ah]
- Only an administrator of a GitLab Self-Managed or Dedicated instance can change the default closing pattern: `gitlab_rails['gitlab_issue_closing_pattern']` (Linux package, Docker), `global.appConfig.issueClosingPattern` (Helm chart) or `issue_closing_pattern` in `gitlab.yml` (self-compiled). [DOC S-xdfirawc, S-qxksc6ah]
- The documented default regular expression contains `%{issue_ref}` for the issue reference and a second alternative `([A-Z][A-Z0-9_]+-\d+)`; to test a pattern with Rubular, the admin page says to replace `%{issue_ref}` with `#\d+`, which matches local references only. [DOC S-qxksc6ah, S-xdfirawc]
- A keyword followed by a key of the form `PROJ-123` (letters, hyphen, digits) matches the default pattern, so `Closes PROJ-7` is a closing text for GitLab as well as the form its Jira integration documents. [DER S-qxksc6ah, S-pnktrw4x: the second alternative of the regex; the Jira page lists `Closes PROJECT-1` as a trigger]
- A line that holds a reference but no keyword, such as `KB-Ref: #12`, `KB-Ref: PROJ-123` or `Related to #17`, matches nothing, and a keyword with an all-caps spelling (`CLOSES #3`) is not in the documented list and did not match. [DER S-qxksc6ah, S-xdfirawc: the default regex with `%{issue_ref}` replaced by `#\d+`, run with Python 3.13.2's `re` on macOS, 2026-10-10]
- The match is on the text, not its sense: `this does not fix #12` contains the matched text `fix #12`, so a description or commit that mentions a keyword and a reference in a negation still matches. [DER S-qxksc6ah, S-xdfirawc: same run of the default regex]
- Mentioning an issue in a commit message creates a link between the issue and the first commit that mentions it: `#xxx` in the same project, `projectname#xxx` in the same group, and the full issue URL otherwise. [DOC S-a57i2q6g]
- A commit message cannot usually begin with `#`, so the alternative notation `GL-xxx` (for example `GL-12: message`) is accepted for a local issue. [DOC S-a57i2q6g]
- For performance, GitLab turns only the first 1,000 full URLs of a commit message into links. [DOC S-a57i2q6g]
- A mention of an issue in a merge request description links the issue and the merge request, and a mention in a merge request comment behaves like a mention in an issue; a mention in either shows in the issue's activity as `mentioned in merge request !(number)`. [DOC S-a57i2q6g]
- A branch created in the same project whose name starts with the issue number and a hyphen links the issue and the merge request. [DOC S-a57i2q6g]
- GitLab Flavored Markdown links an issue as `#123`, `GL-123` or `[issue:123]`, a cross-project issue as `namespace/project#123` (shortcut inside the same namespace `project#123`), and a merge request as `!123`, `namespace/project!123` (shortcut `project!123`); a leading backslash (`\#123`) keeps `#123` from linking. [DOC S-ww5ecjfc]
- A merge request description that must only point at an issue (a reference to a ticket that stays open) uses a reference with no closing keyword; one that should close it at merge puts the keyword and reference on a line of the description, the form the widget previews before the merge. [DER S-qxksc6ah, S-a57i2q6g: closing needs keyword plus reference; a bare mention only links]

## Reference
| Need | Text | Closes on merge | Source |
|---|---|---|---|
| close a local issue | `Closes #123` | yes | S-qxksc6ah |
| close an issue of another project | `Closes group/project#123` | yes | S-qxksc6ah |
| close by URL | `Closes https://gitlab.example.com/group/project/-/issues/123` | yes | S-qxksc6ah |
| link without closing | `Related to #123`, `Ref #123`, `GL-123` | no | S-qxksc6ah, S-a57i2q6g |
| reference a merge request in another project | `group/project!45` | no | S-ww5ecjfc |
| link by branch name | branch `123-short-name` | no | S-a57i2q6g |
| switch auto-close off | **Settings** > **Repository** > **Branch defaults** | none | S-qxksc6ah |
| change the pattern | `gitlab_rails['gitlab_issue_closing_pattern']` (administrator) | n/a | S-xdfirawc |

See also `gitlab/jira-issue-keys-in-commits.md` (Jira keys in commits and merge requests), `gitlab/automated-merge-requests.md` (opening and merging merge requests from automation, `merge_request.description` push option) and `gitlab/git-trailers-and-hooks.md` (trailer lines).

## Examples
- SNIPPET: a merge request description that closes one issue, closes an issue of another project and only references a third; context: GitLab, project in the group `group`, merge into the default branch; checked: no [DER S-qxksc6ah, S-a57i2q6g: keyword plus reference closes, a bare mention links]
```text
Closes #12
Closes group/otherproject#7
Related to #20
```
