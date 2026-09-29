---
topic: gitlab/repository-mirroring
priority: P3
applies_to: "GitLab 19.x docs (gitlab-org/gitlab master @9f1632e2, 2026-09-27): repository mirroring, push and pull mirroring, bidirectional mirroring, remote mirrors API, GitHub importer; GitLab.com, Self-Managed and Dedicated"
retrieved_utc: 2026-09-29
sources: [S-7iutmaw5, S-4o7kkuoi, S-5qb34k6p, S-ci4g3efd, S-7i4mq2ge, S-d24ftlvy, S-sg3osg2z, S-7zthwzzb, S-fa7zbfwo]
status: complete
---

# GitLab repository mirroring: push and pull mirrors, tiers and limits

## Summary
Push mirroring (GitLab to another repository) is in every tier, on GitLab.com, Self-Managed and Dedicated. Pull mirroring (another repository into GitLab) and bidirectional mirroring are Premium and Ultimate only, so a Free or Free self-managed project cannot pull branches from a public GitHub repository by mirroring; it has to fetch them with a Git client. A pull mirror never brings pull requests, and a push mirror sends everything the project holds on the mirrored branches: the documented options choose branches (all protected branches, or an RE2 branch regex in Premium), not paths. The importer for GitHub projects is Free but is a one-time copy that also does not keep pull requests in sync.

## Facts
- The repository mirroring page is Free, Premium and Ultimate on GitLab.com, GitLab Self-Managed and GitLab Dedicated; it names three methods: push, pull (Premium and Ultimate only) and bidirectional (available, but can cause conflicts). [DOC S-7iutmaw5]
- Push mirroring is Free, Premium and Ultimate on GitLab.com, Self-Managed and Dedicated. [DOC S-4o7kkuoi]
- Pull mirroring is Premium and Ultimate on GitLab.com, Self-Managed and Dedicated (moved to Premium in 13.9); bidirectional mirroring is Premium and Ultimate too. [DOC S-5qb34k6p, S-ci4g3efd]
- A mirror is created in **Settings > Repository > Mirroring repositories** by a Maintainer or Owner; the url must be reachable over `http://`, `https://`, `ssh://` or `git://`. SCP-style urls (`git@host:path`) are not supported, and neither are dumb HTTP or mirroring between SHA-1 and SHA-256 repositories. [DOC S-7iutmaw5]
- A push mirror is a downstream copy that passively receives the commits of the upstream GitLab repository; the docs say not to push commits directly to the downstream mirror, so it does not diverge. [DOC S-4o7kkuoi]
- A push mirror receives a change five minutes after the push to the upstream repository, or one minute with **Only mirror protected branches** on; it also updates when an administrator force-updates the mirror. [DOC S-4o7kkuoi]
- A branch merged into the default branch and deleted in the source project is deleted from the push mirror on the next push; branches with unmerged changes are kept; a diverged branch shows an error in **Mirroring repositories**. [DOC S-4o7kkuoi]
- By default, if a ref on the push mirror has diverged from the local repository, the upstream repository overwrites the remote change. With **Keep divergent refs**, the diverged ref on the mirror is left as it is and the update is marked failed; after creation the value can be changed only through the remote mirrors API. [DOC S-4o7kkuoi]
- Each project can have at most 10 enabled push mirrors (limit introduced in GitLab 18.9); the docs suggest disabling unused mirrors or consolidating destinations. [DOC S-4o7kkuoi, S-d24ftlvy]
- **Only mirror protected branches** limits a mirror, in either direction, to the project's protected branches; for a pull mirror the unprotected branches of the mirroring project are not mirrored and can diverge. **Mirror specific branches** (an RE2 regular expression on branch names) is Premium and Ultimate. [DOC S-7iutmaw5]
- To push to GitHub the docs use a fine-grained personal access token with read and write on repository contents, plus read and write on Workflows when the repository has a `.github/workflows` directory; the url is `https://github.com/GROUP/PROJECT.git`, the username is the token's owner and the password is the token. GitHub attributes commits by email address. [DOC S-4o7kkuoi]
- Mirror authentication is SSH (public key or password, with a host key verified by fingerprint) or username and password; for a project or group access token, use any non-blank username and the token as password. [DOC S-7iutmaw5]
- A pull mirror pulls automatically 30 minutes after the previous pull (this cannot be disabled); UI and API triggers are limited by a 5-minute default interval that Self-Managed administrators can configure. [DOC S-5qb34k6p]
- By default a pull mirror stops updating a branch or tag that diverged from the local repository; **Overwrite diverged branches** replaces local changes. Branches and tags deleted upstream are not deleted downstream, and items deleted only downstream come back at the next pull. [DOC S-5qb34k6p]
- After 14 consecutive failed retries a pull mirror is a hard failure and stops until an update is forced; an update can be started with the pull mirroring API. [DOC S-5qb34k6p]
- A pull mirror can trigger pipelines for mirror updates; those pipelines run with the credentials of the user who set the mirror up, which the docs call a risk for untrusted upstreams. [DOC S-5qb34k6p]
- The docs warn against turning on the job-token push setting **Allow Git push requests to the repository** in a project that is a pull mirror. [DOC S-7zthwzzb, S-5qb34k6p]
- The remote mirrors API (Free, all offerings) lists (`GET /projects/:id/remote_mirrors`) and changes push mirrors; a mirror has `enabled`, `only_protected_branches`, `keep_divergent_refs`, `last_error`, `last_successful_update_at` and `update_status` (`none`, `scheduled`, `started`, `finished` or `failed`); the `url` is always returned without credentials. Pull mirrors use a different endpoint (project pull mirroring API). [DOC S-7i4mq2ge]
- Bidirectional mirroring gives no guarantee that either side updates without errors; the docs advise mirroring only protected branches, protecting them on both sides, a push webhook to shorten the race window, and a `pre-receive` hook that makes one repository authoritative. [DOC S-ci4g3efd]
- The GitHub importer (Free, Premium, Ultimate; needs the Maintainer or Owner role on the target group) imports a GitHub project, its pull requests as merge requests, comments and reviews, once. [DOC S-sg3osg2z]
- After an import, **repository mirroring can keep the imported repository in sync with its GitHub copy** only where the tier has it (the section is Premium and Ultimate), and the docs state that mirroring does not sync new or updated pull requests from the GitHub project. [DOC S-sg3osg2z]
- The importer maps the GitHub rule "Require a pull request before merging" to **No one** in **Allowed to push and merge**, "Require signed commits" to the Premium push rule **Reject unsigned commits**, and does not import the rule "Require status checks to pass before merging". [DOC S-sg3osg2z]
- A push mirror has no documented filter by path or content: the options are protected branches only, a branch regex (Premium), keep divergent refs and the branch protections of the mirror itself, so a directory that must stay off the copy (an internal root, `_private/`) cannot be excluded by a mirror; a projection made before the push is needed. [DER S-4o7kkuoi, S-7iutmaw5: the complete option lists]
- On Free (including Free self-managed) a GitHub repository that people push branches to reaches GitLab merge requests only through a Git client: fetch the branch from the GitHub remote and push it to a GitLab branch with the merge-request push options; a pull mirror would not bring the pull requests even where the tier has it. [DER S-5qb34k6p, S-sg3osg2z, S-7iutmaw5: pull mirroring is Premium; mirroring does not sync pull requests]

## Reference
| Mirror | Tier | Direction | Trigger and interval | Source |
|---|---|---|---|---|
| Push | Free, Premium, Ultimate | GitLab to remote | on upstream push: 5 min (1 min protected only); max 10 enabled per project | S-4o7kkuoi, S-d24ftlvy |
| Pull | Premium, Ultimate | remote to GitLab | every 30 min, forced update min 5 min (configurable Self-Managed); hard failure after 14 retries | S-5qb34k6p |
| Bidirectional | Premium, Ultimate | both | both of the above; may conflict | S-ci4g3efd |
| GitHub importer | Free, Premium, Ultimate | GitHub to new GitLab project, once | one-time; pull requests not kept in sync | S-sg3osg2z |
| Mirror specific branches (regex) | Premium, Ultimate | either | RE2 on branch names | S-7iutmaw5 |

See also `gitlab/automated-merge-requests.md` (push options that open the merge request, job-token pushes), `gitlab/protected-branches-tags.md` (what a mirror of protected branches means), `gitlab/github-branch-rules-and-auto-merge.md` (the GitHub side).

## Examples
- SNIPPET: list a project's push mirrors and their status through the API with the GitLab CLI; context: `glab` authenticated to the instance, run inside the project's clone, Maintainer or Owner role; checked: no [DER S-7i4mq2ge: the endpoint and response fields; S-fa7zbfwo: `glab api` sends an authenticated request to a REST v4 path and fills `:id` from the repository of the current directory]
```bash
glab api projects/:id/remote_mirrors
```
