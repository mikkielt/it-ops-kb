---
topic: auth/gitlab-ci-identity
priority: P0
applies_to: "GitLab CI/CD (docs current 2026-09-24)"
retrieved_utc: 2026-09-24
sources: [S1276, S1277]
status: partial
---

# GitLab CI/CD identity: ID tokens for OIDC federation

See also `kb/gitlab/variables.md`, `kb/gitlab/protected-branches-tags.md` (read but not duplicated here).

## Summary
- GitLab CI/CD jobs can carry one or more `id_tokens`, JWTs signed by GitLab, usable as OIDC federation credentials with no stored secret. [DOC S1276]
- The default `sub` claim format is `project_path:{group}/{project}:ref_type:{type}:ref:{name}`, where `ref_type` is `branch`, `tag`, or `merge_request`. [DOC S1276]
- An immutable-subject option (`ci_id_token_sub_claim_components`) can lead the `sub` with the numeric, never-reused `project_id` instead of the renameable project path. [DOC S1276]

## Facts
- `id_tokens` are configured per job in `.gitlab-ci.yml` with an `aud` claim the relying party (here, Entra's federated credential) must match. [DOC S1276]
- Default `sub` for a tag pipeline: `project_path:<group>/<project>:ref_type:tag:ref:<tag_name>`; for a branch pipeline: `project_path:<group>/<project>:ref_type:branch:ref:<branch_name>`. [DOC S1276]
- `ref_type` can also be `merge_request` for merge-request pipelines. [DOC S1276]
- A `ci: only tags start pipelines` rule plus a protected-tag `ref_type:tag` subject lets a CI instance's federated credential be scoped to exactly the tag pattern that triggers a pipeline (e.g. `release-*`), without a wildcard: Entra federated credentials match a `sub` by exact string or by a small set of built-in patterns, so protecting the tag in GitLab and matching that literal ref name (or a small enumerated set) in the federated credential subject is the safe pairing. [DER S1276]
- The GitLab-recommended immutable pattern (`project_id` first) survives project renames/path reuse, which the path-based default does not. [DOC S1276]
- The federated-credential per-app-registration limit and the status of wildcard ("flexible") federated identity credentials are documented on the Entra side, not the GitLab side; see `auth/workload-identity.md`. [UNK — GitLab docs don't state Entra-side limits]

## Reference
| Claim | Example value | Source |
|---|---|---|
| `sub` (branch) | `project_path:corp/example-project:ref_type:branch:ref:main` | S1276 |
| `sub` (tag) | `project_path:corp/example-project:ref_type:tag:ref:release-2026.09.24.1` | S1276 |
| `sub` (immutable, project_id-first) | `project_id:57382910:ref_type:tag:ref:release-2026.09.24.1` | S1276 |
| `iss` | `https://gitlab.com` (or the self-managed GitLab instance URL) | S1276 |

## Examples
- An example repo, project path `corp/example-project`, protected tag pattern `release-*`: federated credential subject enumerates one entry per pattern GitLab supports, or uses the immutable `project_id:` form to avoid path-rename risk.

## Open items
- QA4 exact `sub` for protected tag pipelines: answered (`ref_type:tag`) above.
- Per-app federated-credential count limit and flexible/wildcard FIC status: see `auth/workload-identity.md`.
