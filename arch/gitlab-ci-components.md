---
topic: arch/gitlab-ci-components
priority: P1
applies_to: [gitlab-ci]
retrieved_utc: 2026-09-26
sources: [S1700, S1701, S1702, S1512, S1704, S446]
status: complete
---

# GitLab CI/CD components and catalog

## Summary
Components are versioned, reusable pipeline configuration published from a project's `templates/`
directory and pinned by tag, SHA or `~latest`. The CI/CD Catalog has been GA since GitLab 17.0
(GitLab.com and self-managed). Whether a component job runs on Windows is decided the same way any
job picks a runner (`tags:`), not by anything component-specific. A repository that already protects
a release tag pattern (e.g. `cfg-*`) fits the "release on protected tag" model components also require.

## Facts
- A component project stores components under `templates/`, either as `templates/<name>.yml` or
  `templates/<name>/template.yml`; only `template.yml` is read by consumers when a subdirectory is
  used. [DOC S1700]
- Components declare configurable parameters in a `spec:inputs` block (e.g.
  `spec: inputs: stage: default: test`), referenced in job bodies as `$[[ inputs.stage ]]`. [DOC S1700]
- `include: - component: <fqdn>/<path>@<version>` pins by commit SHA, tag, branch name, or `~latest`
  (latest published Catalog release matching the given pattern). [DOC S1700]
- Versions released to the CI/CD Catalog must use semantic versioning (e.g. `1.0.0`, `1.0.0-alpha`).
  [DOC S1700]
- GitLab's backend issue to enforce semantic versioning for catalog resources (#427286) was closed on
  2024-02-19 (milestone 16.10, label `workflow::complete`); its related merged merge requests include
  one adding semantic-version validation to catalog resource versions (merged 2024-02-15). [DOC S1701]
- Publishing to the Catalog is done with the `release` keyword in a CI job, not the Releases API
  directly. [DOC S1700]
- The CI/CD Catalog became generally available in GitLab 17.0 (2024-05-16), for GitLab.com,
  GitLab Dedicated and GitLab Self-Managed alike — no separate self-managed lag. [DOC S1702][DOC S1700]
- Catalog visibility follows the source project's visibility: public components are visible to
  anyone with access to the instance, internal ones to signed-in users, and private ones only to
  users with at least the Guest role on the source project; *using* a component additionally
  requires at least the Reporter role. [DOC S1700]
- A community forum thread reports the same split in practice: a Guest on a private component
  project sees the component in the Catalog but gets a permission error when a pipeline includes
  it, while Developer works. [COMMUNITY S1704]
- `include: - project: '<group/project>' file: '/path/to/file.yml'` imports a plain CI/CD config file
  from another project's repository; this is a distinct mechanism from `include: component:` — it has
  no `spec:inputs`, no semantic-version pin, and no Catalog listing. [DOC S1512]
- `tags:` on a job is the ordinary runner-selection keyword (e.g. `tags: [windows]`); a component's
  own job definitions carry `tags:` exactly like any other job, so a component can target a Windows
  runner the same way any other job in the consuming pipeline would. [DOC S1512]
- A repository can protect a release tag pattern (e.g. `cfg-*`, Maintainers only) and gate pipelines on
  a `$CI_COMMIT_TAG` regex match. [DOC S446]

## Reference
- `include: - component: $CI_SERVER_FQDN/<group>/ci-components/checks@1.0.0` (per S1700 pattern).
- `include: - project: '<group>/<project>' file: '/ci/checks.yml'` (per S1512 pattern).

## Examples
- If a team published a reusable `checks` component from one repository, a second repository's
  pipeline could pin it as `include: - component: $CI_SERVER_FQDN/<group>/ci-components/checks@1.2.0`
  and set `tags: [windows]` inside the component's job to run on a lab host that builds
  device-baseline content.

## Derivations
- A GitLab CI/CD component is pipeline-YAML reuse with inputs and versioning; it does not replace a
  shared CI script. A team that runs one CI job (`checks`) invoking the same command a laptop runs
  already gets cross-repo, cross-machine reuse without adopting a second file format (a "new file
  format" simplicity-minded rules would flag). A component only earns its keep when multiple
  *unrelated* repositories need to call the same CI logic without vendoring it; two repositories under
  one team, where `include:project` already covers cross-repo YAML reuse, do not need a Catalog
  release cadence for that. [DER S1700,S1512: components add semver-release overhead include:project
  does not need]
