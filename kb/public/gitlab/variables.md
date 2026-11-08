---
topic: gitlab/variables
priority: P0
applies_to: "GitLab 19.5 docs (master @56c82a97)"
retrieved_utc: 2026-11-08
sources: [S449, S446, S-k5jbt3xk]
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
- **Minimum role to use pipeline variables** (GitLab 17.1+, project setting `ci_pipeline_variables_minimum_override_role`) limits who may run a pipeline with pipeline variables: `no_one_allowed` lets no pipeline run with them, and the other values name the lowest role allowed, down to `developer`. [DOC S-k5jbt3xk]
- Since GitLab 17.7 new projects in new namespaces on GitLab.com default to `no_one_allowed`, and once a project is at that value only the Owner role can change it. [DOC S-k5jbt3xk]
- The setting leaves variables from project or group settings and the `variables` keyword in the YAML alone. For a trigger job, the downstream project's setting and the user's role there apply, and a role below the minimum fails the job with `Insufficient permissions to set pipeline variables`, creating no pipeline. [DOC S-k5jbt3xk]

## Reference
| Property | Effect | Source |
|---|---|---|
| Protected | only protected branches and tags (plus opt-in MR access) | S449,S446 |
| Masked | redacted in job logs, not guaranteed | S449 |
| Masked and hidden | not shown on the settings page; set only at creation (GA 17.6) | S449 |

## Examples
Variable `APP_SQL_CONN` (fixture): Protected + Masked, used only by the tag pipeline for `release-*`.

See also: `claude/ci-and-headless.md` — a Claude Code GitLab CI job that reads `ANTHROPIC_API_KEY` as a masked
CI/CD variable of the kind documented here.
