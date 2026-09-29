---
topic: gitlab/github-branch-rules-and-auto-merge
priority: P3
applies_to: "GitHub Docs (github/docs @aff94963b07a8) for github.com plans; GitHub CLI manual read 2026-09-29; rulesets, branch protection rules, required status checks, pull request auto-merge, merge methods, CODEOWNERS; the counterpart of gitlab/protected-branches-tags.md for a public GitHub repository"
retrieved_utc: 2026-09-29
sources: [S-owfsdkff, S-o766dsv5, S-kyamdmco, S-ai4fbdo7, S-dqd2wyad, S-bhojoaw6, S-fuytyyvw, S-t7yg2o2s, S-dzbnhthc, S-6xcdstb3, S-vf2dvnlt, S-ldxeltib, S-gifxe3nj, S-le6auopv, S-ra4wu36u, S-g6kufkad, S-uhi2oo32, S-54krfv6d]
status: complete
---

# GitHub rulesets, branch protection and auto-merge on a public repository

## Summary
On github.com a public repository with the Free plan has rulesets, branch protection rules, required status checks, pull request auto-merge and CODEOWNERS. It does not have push rulesets, which are the only rules that restrict pushes by file path and apply without a branch target: they are for private and internal repositories on the Team plan and above. Commit-metadata (commit message and email pattern) rules are documented for Enterprise plans. So a public repository can require a pull request on `main` (with a bypass list for chosen roles, teams or apps) but cannot say "pull request only for these paths, direct push for the rest"; that split has to be detected after the push, in CI. Auto-merge merges a pull request once required reviews and status checks pass, and needs a branch protection rule or ruleset that makes the pull request wait.

## Facts
- Rulesets are available in public repositories with GitHub Free (and Free for organizations), and in public and private repositories with Pro, Team and Enterprise Cloud. [DOC S-kyamdmco]
- Push rulesets are available for the Team plan in internal and private repositories (and forks of repositories that have them enabled) on github.com, and for the Enterprise Cloud plan; they block pushes to a private or internal repository and its whole fork network. [DOC S-kyamdmco, S-ai4fbdo7]
- Push rulesets block pushes by file extension, file path length, file and folder path (`fnmatch` patterns such as `test/demo/**/*`) and file size, need no branch targeting because they apply to every push, and offer **Restrict file paths**: commits that change the listed paths cannot be pushed. [DOC S-ai4fbdo7]
- A ruleset is a named list of rules, up to 75 rulesets per repository; branch and tag rulesets target refs with `fnmatch` patterns (`releases/**/*`), and a ruleset can let chosen roles (such as repository administrator), teams or GitHub Apps bypass it. [DOC S-owfsdkff]
- Rulesets and branch protection rules both apply and layer: rules from all rulesets that target a ref are aggregated (a ruleset has no priority, the most restrictive version of a rule wins) and also layer with branch protection rules on the same branch. Anyone with read access can see a repository's rulesets. [DOC S-owfsdkff]
- Ruleset rules include: restrict creations, restrict updates and restrict deletions (only bypass actors may), require linear history (no merge commits; pull requests must be squash or rebase merged), require a pull request before merging (the pull request need not be approved), require status checks, block force pushes (on by default), require signed commits, and a merge queue rule (not available in organization-level rulesets). [DOC S-o766dsv5]
- Commit-metadata rules (regular expressions on commit messages, author and committer emails, branch and tag names) are documented as additional rules for organizations on an Enterprise plan; they block the ref update, not the upload, so rejected commits stay in the repository unreachable, and a squash merge is checked against the single merge commit only. [DOC S-o766dsv5]
- Required status checks can be checks or commit statuses; anyone or any integration with write permission can set any status, but a rule can name a GitHub App as the only accepted source. Checks are "strict" (branch must be up to date with the base; the default) or "loose". [DOC S-o766dsv5]
- A ruleset rule requiring a pull request can also require approvals, code owner review, resolved conversations and a merge type; the "require workflows to pass" rule blocks direct pushes because those workflows run as part of the pull request and merge queue experience, so it belongs only on branches changed only by pull request. [DOC S-o766dsv5]
- Protected branches (branch protection rules) are available in public repositories with GitHub Free and Free for organizations, and in public and private repositories with Pro, Team, Enterprise Cloud and Enterprise Server. [DOC S-bhojoaw6]
- A branch protection rule covers a name or `fnmatch` pattern and does not need the branch to exist; only one rule applies at a time, and the one that names a specific branch has the highest priority. Actors can be added to bypass lists only when the repository belongs to an organization. [DOC S-dqd2wyad]
- By default a branch protection rule turns off force pushes and deletion of the matching branches, and its restrictions do not apply to people with admin permission unless **Do not allow bypassing the above settings** is on. [DOC S-fuytyyvw]
- Required status checks under branch protection must be `successful`, `skipped` or `neutral`; after they pass, commits must be pushed to another branch and merged or pushed directly to the protected branch. [DOC S-fuytyyvw]
- **Restrict who can push to matching branches** is documented for public repositories owned by a Free organization and for all repositories of Team and Enterprise Cloud organizations; people and apps with admin permission can always push to a protected branch. [DOC S-fuytyyvw]
- A push that a branch protection rule refuses ends `remote: error: GH006: Protected branch update failed for refs/heads/main.` and names the failed rule. [DOC S-fuytyyvw]
- Pull request auto-merge is available in public repositories with GitHub Free and Free for organizations, and in public and private repositories with Pro, Team, Enterprise Cloud and Enterprise Server. [DOC S-dzbnhthc]
- Auto-merge must be allowed for the repository first (**Settings > General > Pull Requests > Allow auto-merge**, maintainer permission); it needs a branch protection rule, and the option to enable it appears only on a pull request that cannot be merged yet, for example while required reviews or status checks are outstanding. [DOC S-vf2dvnlt, S-6xcdstb3]
- People with write permission can enable auto-merge on a pull request, optionally choosing the merge method; it merges once required reviews and status checks pass. Write permission holders and the author can disable it, and it is disabled when someone without write permission pushes to the head branch or the base branch is switched. [DOC S-t7yg2o2s, S-vf2dvnlt]
- `gh pr merge --auto` merges only after the requirements are met; `--squash`, `--merge` and `--rebase` choose the method, `--delete-branch` deletes the branch, `--match-head-commit <SHA>` requires the head to match, `--disable-auto` turns auto-merge off and `--admin` merges a pull request that does not meet the requirements. For a branch that requires a merge queue no method is given: with required checks pending it enables auto-merge, with them passed it enqueues the pull request. [DOC S-uhi2oo32]
- Merge commit adds the branch commits plus a merge commit (`--no-ff`); squash and merge produces one commit and is merged with the fast-forward option; rebase and merge adds each commit without a merge commit but always updates the committer information and creates new commit SHAs, and drops commits that were empty to begin with. [DOC S-ldxeltib, S-le6auopv, S-gifxe3nj]
- A pull request is marked `merged` when its head commits become reachable from the base branch outside it (the same commits merged by another pull request or pushed directly to the default branch), even if the branch protection rules on that pull request were not satisfied. [DOC S-ldxeltib]
- Code owners can be defined in public repositories with GitHub Free; a `CODEOWNERS` file in `.github/`, the root or `docs/` (the first found is used) assigns one branch's owners, must stay under 3 MB, and its owners are requested on pull requests that change their files; an administrator can additionally require code owner approval within required reviews. [DOC S-ra4wu36u, S-g6kufkad]
- On a public repository with the Free plan nothing documented enforces "pull request only for some paths": push rulesets (path restrictions) are for private and internal repositories, metadata rules are for Enterprise, and code owner approval applies only to pull requests, so it would not stop a direct push unless a rule requires a pull request for the whole branch; the workable server-side rules are a pull-request requirement on the whole branch with a bypass list, and restrict updates, both per ref. [DER S-kyamdmco, S-ai4fbdo7, S-o766dsv5, S-ra4wu36u, S-owfsdkff: plan availability and rule scope]
- A public repository used as a public home that only a publish job writes to can therefore block every other writer with restrict updates plus a bypass for the publisher, and it can require a pull request for everything else; the rules are per ref and per actor, never per path or per commit content. [DER S-o766dsv5, S-owfsdkff: rule scope; bypass by role, team or app]

## Reference
| Control | Public repo, Free plan | Path scoped | Source |
|---|---|---|---|
| Ruleset (branch or tag) | yes | no, ref patterns only | S-kyamdmco, S-owfsdkff |
| Push ruleset (file paths, extensions, size) | no: private and internal, Team and above | yes | S-kyamdmco, S-ai4fbdo7 |
| Commit-metadata rules | Enterprise plans | no | S-o766dsv5 |
| Branch protection rule | yes | no | S-bhojoaw6 |
| Restrict who can push (branch protection) | only in an organization's repository (Free org public repos included) | no | S-fuytyyvw |
| Required status checks | yes | no | S-o766dsv5, S-fuytyyvw |
| Pull request auto-merge | yes, needs a protection rule | no | S-dzbnhthc, S-6xcdstb3 |
| CODEOWNERS review requirement | yes | yes, within pull requests only | S-g6kufkad, S-ra4wu36u |

See also `gitlab/protected-branches-tags.md` (the GitLab side: per branch, Free), `gitlab/automated-merge-requests.md` (`gh` and `glab` flags), `gitlab/detecting-mr-merges-in-ci.md` (telling a pull request merge from a direct push).

## Examples
- SNIPPET: open a pull request for the current branch and set it to auto-merge with a squash once required checks pass; context: GitHub CLI authenticated to the repository, auto-merge allowed in the repository settings, a protection rule that makes the pull request wait; checked: no [DER S-uhi2oo32, S-54krfv6d: `--auto`, `--squash`, `--delete-branch`; `--base`, `--title`, `--body`]
```bash
gh pr create --base main --title "Change PL-0001" --body "Details"
gh pr merge --auto --squash --delete-branch
```
