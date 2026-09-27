---
topic: auth/gitlab-ci-identity
priority: P0
applies_to: "GitLab CI/CD (docs current 2026-09-26)"
retrieved_utc: 2026-09-27
sources: [S1276, S1277, S1293, S1294]
status: complete
---

# GitLab CI/CD identity: ID tokens for OIDC federation

See also `gitlab/variables.md`, `gitlab/protected-branches-tags.md` (read but not duplicated here).

## Summary
- GitLab CI/CD jobs can carry one or more `id_tokens`, JWTs signed by GitLab, usable as OIDC federation credentials with no stored secret. [DOC S1276]
- The default `sub` claim format is `project_path:{group}/{project}:ref_type:{type}:ref:{name}`, where `ref_type` is the Git ref type, `branch` or `tag`. [DOC S1276, S1277]
- An immutable-subject option (`ci_id_token_sub_claim_components`) can lead the `sub` with the numeric, never-reused `project_id` instead of the renameable project path. [DOC S1276]

## Facts
- `id_tokens` are configured per job in `.gitlab-ci.yml` with an `aud` claim the relying party (here, Entra's federated credential) must match. [DOC S1276]
- Default `sub` for a tag pipeline: `project_path:<group>/<project>:ref_type:tag:ref:<tag_name>`; for a branch pipeline: `project_path:<group>/<project>:ref_type:branch:ref:<branch_name>`. [DOC S1276]
- The ID token claims table lists `ref_type` as `branch` or `tag` only (no `merge_request` value); in a merge request pipeline the `ref_path` claim holds the source branch ref path. [DOC S1277]
- A `ci: only tags start pipelines` rule plus a protected-tag `ref_type:tag` subject lets a CI instance's federated credential be scoped to exactly the tag pattern that triggers a pipeline (e.g. `release-*`), without a wildcard: a standard Entra federated credential matches `sub` by exact string, and flexible federated credentials (preview) add `matches` expressions with wildcards for GitLab's `sub`, so protecting the tag in GitLab and matching that literal ref name (or a small enumerated set) in exact-match credentials is the safe, GA pairing. [DER S1276, S1294]
- The `project_id`-first subject keeps cloud access stable when a project is renamed or moved. With a `project_path` subject, GitLab refuses to issue ID tokens ("ID token issuance is disabled") when the project's path was previously used by a different project, so a new project cannot inherit the old one's trust policies; the documented fix is `ci_id_token_sub_claim_components` with `project_id` first. [DOC S1276, S1277]
- GitLab advises trust policies to also check stable identifiers (`project_id`, and `namespace_id` while the project stays in its namespace) next to path-based claims like `sub`, where the cloud provider and GitLab offering support them. [DOC S1276, S1277]
- An ID token expires with the job's timeout, or after 5 minutes when no timeout is set. [DOC S1277]
- Entra limits an application or user-assigned managed identity to at most 20 federated identity credentials, and flexible (wildcard) federated identity credentials are in preview with GitLab as a supported issuer; details in `auth/workload-identity.md`. [DOC S1293, S1294]

## Reference
| Claim | Example value | Source |
|---|---|---|
| `sub` (branch) | `project_path:corp/example-project:ref_type:branch:ref:main` | S1276 |
| `sub` (tag) | `project_path:corp/example-project:ref_type:tag:ref:release-2026.09.24.1` | S1276 |
| `sub` (immutable, project_id-first) | `project_id:57382910:ref_type:tag:ref:release-2026.09.24.1` | S1276 |
| `iss` | `https://gitlab.com` (or the self-managed GitLab instance URL) | S1277 |

## Examples
- An example repo, project path `corp/example-project`, protected tag pattern `release-*`: federated credential subject enumerates one entry per pattern GitLab supports, or uses the immutable `project_id:` form to avoid path-rename risk.

## Open items
- QA4 exact `sub` for protected tag pipelines: answered (`ref_type:tag`) above.
- Per-app federated-credential count limit (20) and flexible/wildcard FIC status (preview): answered above; see `auth/workload-identity.md`.
