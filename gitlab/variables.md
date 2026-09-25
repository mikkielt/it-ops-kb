---
topic: gitlab/variables
priority: P0
applies_to: "GitLab 19.5 docs (master @56c82a97)"
retrieved_utc: 2026-09-25
sources: [S449, S446]
status: complete
---

# CI/CD variables: protected, masked, hidden

## Summary
- Variables are Free tier. Environment scope for variables is Premium/Ultimate.
- A **protected** variable reaches only pipelines on protected branches or protected tags. MR pipelines get it only through an opt-in project setting.
- Masking doesn't guarantee secrecy (GitLab's own warning). Hidden variables have been GA since 17.6.

## Facts
- The variables page tier is Free, Premium, Ultimate. The "Environment scope" subsection is Premium, Ultimate. [DOC S449]
- Project, group and instance variables can be protected: then they are available only to pipelines on protected branches or protected tags. [DOC S449]
- MR and merged results pipelines can optionally get protected variables. Settings > CI/CD > Variables > "Allow merge request pipelines to access protected variables and runners" (18.1). It needs both branches protected, push/merge access to the target, and the same project. Forks are excluded. [DOC S446]
- GitLab warns that masking a variable isn't a guaranteed way to stop malicious users reading it. [DOC S449]
- Hidden variables came in 17.4 and became GA in 17.6. A hidden value isn't revealed on the CI/CD settings page. You can hide a variable only when you create it (**Masked and hidden**), and the value must meet the masking requirements. [DOC S449]

## Reference
| Property | Effect | Source |
|---|---|---|
| Protected | only protected branches and tags (plus opt-in MR access) | S449,S446 |
| Masked | redacted in job logs, not guaranteed | S449 |
| Masked and hidden | not shown on the settings page; set only at creation (GA 17.6) | S449 |

## Examples
Variable `APP_SQL_CONN` (fixture): Protected + Masked, used only by the tag pipeline for `release-*`.
