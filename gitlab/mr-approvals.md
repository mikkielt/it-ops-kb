---
topic: gitlab/mr-approvals
priority: P0
applies_to: "GitLab 19.5 docs (gitlab-org/gitlab master @56c82a97, 2026-09-23); GitLab.com, Self-Managed, Dedicated"
retrieved_utc: 2026-09-24
sources: [S440, S441, S442, S443, S444, S450, S452]
status: complete
---

# Merge request approvals and tiers

GitLab docs are CC BY-SA 4.0 (S452): summarized here, not copied.

## Summary
- Free: any user with the Developer role or higher can approve, but approvals are **optional** and don't block merging.
- Premium or Ultimate is needed for required approvals, approval rules, CODEOWNERS approval, and every approval **setting**: *Prevent approval by merge request creator*, *Prevent approvals by users who add commits*, *Prevent editing approval rules*, re-authentication, and approval removal on new commits.
- Instance-level enforcement of these settings is Premium/Ultimate and only on Self-Managed or Dedicated. On GitLab.com, the top-level group is the highest level where they cascade.
- Current default: the author **cannot** approve their own MR. Committers **can** approve unless *Prevent approvals by users who add commits* is on.

## Facts
- The approvals page tier is Free, Premium, Ultimate. Free lets users with Developer or higher approve, but approvals are optional and don't prevent merging. [DOC S441]
- Premium/Ultimate add required approval rules, code owners, instance-wide approval configuration, and group approval settings. [DOC S441]
- "Required approvals" (merging blocked until met) is Premium, Ultimate. [DOC S441]
- The approval rules page is Premium, Ultimate. The "Security Approvals" section is Ultimate. [DOC S442]
- The approval settings page is Premium, Ultimate. Offerings: GitLab.com, Self-Managed, Dedicated. [DOC S440]
- Settings on that page: Prevent approval by merge request creator; Prevent approvals by users who add commits; Prevent editing approval rules in merge requests; Require user re-authentication (password or SAML) to approve; code owner approval removal (Keep approvals / Remove all approvals / Remove approvals by Code Owners if their files changed). [DOC S440]
- By default the MR creator (author) cannot approve. Clearing **Prevent approval by merge request creator (author)** allows it. [DOC S440]
- Authors can override that per MR by editing the approval rule, unless *Prevent editing approval rules in merge requests* is set at project level, or the instance setting is set (Self-Managed only). [DOC S440]
- By default committers can approve. **Prevent approvals by users who add commits** stops them. [DOC S440,S442]
- Code owners who commit to an MR can't approve it if the MR touches files they own. [DOC S440]
- Warning: if someone other than the original committer rebases the MR, the commit history gets a new committer. Earlier committers may then become able to approve. [DOC S440]
- An instance setting locks the equivalent setting for all groups and projects. When a top-level group enables a prevention setting, the project setting is locked. [DOC S440]
- Instance approval settings (Admin > Push rules > Merge request approvals) are Premium, Ultimate on Self-Managed and Dedicated only. They are: prevent creator approval, prevent committer approval, prevent editing approval rules in projects and MRs. The last one also locks the project rule list. [DOC S443]
- "Remove all approvals when commits are added to the source branch" is on by default. GitLab uses `git patch-id` to decide whether to reset approvals. [DOC S440]
- Re-authentication to approve is set only on top-level groups. Its feature flag was removed in GitLab 18.3. [DOC S440]
- MR authors don't count as eligible approvers on their own MRs by default. [DOC S442]
- "Require Code Owner approval" on protected branches is Premium, Ultimate. [DOC S444]
- CODEOWNERS is Premium, Ultimate. [DOC S450]

## Reference
| Capability | Tier | Offering | Source |
|---|---|---|---|
| Optional approvals (non-blocking) | Free+ | all | S441 |
| Required approvals / approval rules | Premium, Ultimate | all | S441,S442 |
| Prevent approval by MR creator (project/group) | Premium, Ultimate | all | S440 |
| Prevent approvals by users who add commits | Premium, Ultimate | all | S440 |
| Prevent editing approval rules | Premium, Ultimate | all | S440 |
| Instance-level approval settings | Premium, Ultimate | Self-Managed, Dedicated | S443 |
| CODEOWNERS / Require Code Owner approval | Premium, Ultimate | all | S450,S444 |
| Security Approvals (policies) | Ultimate | all | S442 |

## Examples
Project (Premium): Settings > Merge requests > Approvals. Add rule "reviewers", 1 approval. Tick *Prevent approval by merge request creator*, *Prevent approvals by users who add commits* and *Prevent editing approval rules in merge requests*.
