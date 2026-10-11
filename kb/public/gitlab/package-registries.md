---
topic: gitlab/package-registries
priority: P3
applies_to: "GitLab 19.x docs (gitlab-org/gitlab master @9f1632e2, 2026-09-27); PyPI, generic packages and container registry; Free, Premium and Ultimate"
retrieved_utc: 2026-10-11
sources: [S-v25mipeh, S-fo6cckzx, S-5lpubwd5, S-gqpmeuse, S-owkwtkdm, S-n3qvicph, S-ocjsmgvx, S-jk4rtq6g, S-cx5yd4ae, S-sxp3exzp, S1507]
status: partial
---

# GitLab PyPI, generic and container registries: publishing, pinning and visibility

## Summary
All three registries are project-scoped for publishing: a PyPI package or a generic package goes to `projects/<id>/packages/...`, an image to a path that equals the project path. Reading is wider for PyPI only, which has a group index (`groups/<id>/-/packages/pypi/simple`) that lists every project's packages; generic packages have no group endpoint, and the container registry lists a group's repositories through the API but pushes per project. Credentials are a personal or project access token with `api`, a deploy token with the package or registry scopes, or the CI job token. A PyPI file is fixed by its SHA256 (and MD5), a generic file by its SHA256, an image by the `digest` the tag API returns; none of the pages says how to pull the image by that digest, which is the standard `name@sha256:...` form. Visibility follows the project's visibility and its own feature level, not the repository's.

## Facts
### PyPI
- PyPI packages in the package registry are generally available. [DOC S-ocjsmgvx]
- A package is published with twine to `.../projects/<project_id>/packages/pypi` using `TWINE_USERNAME` and `TWINE_PASSWORD`; the credentials are a personal access token with `api`, a deploy token with `read_package_registry`, `write_package_registry` or both, or the CI job token (username `gitlab-ci-token`). [DOC S-v25mipeh]
- A package of at most 5 GB with a valid version string is accepted; its `description` over 4000 characters is truncated; publishing a name and version that already exist answers `400 Bad Request` and the existing package must be deleted first (Maintainer or Owner role). [DOC S-v25mipeh]
- Packages cannot be published to a group or the instance; packages published to a project are also available in the group registry, which can be pulled from. [DOC S-ocjsmgvx, S-v25mipeh]
- The group index is `.../api/v4/groups/<group_id>/-/packages/pypi/simple`; pip authenticates with a personal access token name and token with the `read_api` scope, or with the job token in CI (username `gitlab-ci-token`). [DOC S-v25mipeh]
- A job token also reaches the PyPI packages of other projects in the same top-level group, if each such project allows the job token of the calling project. [DOC S-v25mipeh]
- A request for a package not found in the GitLab registry is forwarded to `pypi.org` by default, even with `--index-url`; a group Owner turns this off in **Settings > Packages and registries** (**Forward PyPI package requests**), an administrator globally. [DOC S-v25mipeh]
- The page advises turning forwarding off or using `--index-url` and `--no-index` together for private packages, and calls `--extra-index-url` more open to dependency confusion because pip checks the default index and the extra one. [DOC S-v25mipeh]
- Package names are matched by the PEP 503 normalized name (`-`, `_` and `.` equal, repeats collapsed). [DOC S-v25mipeh]
- The package registry supports MD5 and SHA256 hashes for PyPI packages, and SHA256 for generic packages; they can be read in the interface or with the Packages API. [DOC S-ocjsmgvx]
### Generic packages
- A file is published with `PUT /projects/:id/packages/generic/:package_name/:package_version/:file_name`; the success status is `201 Created`. [DOC S-fo6cckzx]
- Authentication: a personal access token with `api`, a project access token with `api` and the Developer, Maintainer or Owner role, the CI job token (`JOB-TOKEN` header or `gitlab-ci-token` as basic-auth user) or a deploy token (`DEPLOY-TOKEN` header or basic auth) with `write_package_registry`. HTTP basic auth ignores the username but requires one. [DOC S-fo6cckzx]
- Generic packages can be published and pulled at project level only; there is no group or instance endpoint. [DOC S-ocjsmgvx]
- SHA256 checksums are calculated and stored for uploaded files and listed as `file_sha256` by `GET /projects/:id/packages/:package_id/package_files`; the `X-Checksum-SHA256` response header is present only when files are served through Workhorse, not when object storage direct download redirects the client. [DOC S-fo6cckzx]
- By default a second upload with the same name and version adds its files to the existing package; a group Owner can turn **Allow duplicates** off for generic packages in **Settings > Packages and registries** (the required role moved to Owner in 17.0) and list exceptions by regular expression. [DOC S-fo6cckzx, S-ocjsmgvx]
- A file name may use letters, digits and `. _ - + ~ @ /`, must not start or end with `~` or `@` and must not contain spaces. [DOC S-fo6cckzx]
- A single object-storage PUT is limited to 5 GB; with signature version 2 a larger file can answer `500`. [DOC S-fo6cckzx]
### Container registry
- An image is named `<registry server>/<namespace>/<project>[/<optional path>]` with up to two further name levels; the path of a repository always matches its project's path, so a registry cannot be moved or renamed apart from the project. [DOC S-5lpubwd5]
- Pushing is per project; `GET /groups/:id/registry/repositories` lists the registry repositories of a group and `GET /projects/:id/registry/repositories` those of a project. [DOC S-gqpmeuse]
- `GET /projects/:id/registry/repositories/:repository_id/tags/:tag_name` returns the tag's `digest` (`sha256:...`), `revision`, `short_revision`, `location`, `created_at` and `total_size`; the Tag Details page also shows the manifest and configuration digests. [DOC S-gqpmeuse, S-5lpubwd5]
- The page documents no pull by digest; Docker documents `NAME[:TAG|@DIGEST]` and GitLab's pipeline security guidance asks for `image: <name>@sha256:<digest>` instead of a mutable tag. [DOC S-cx5yd4ae, S-sxp3exzp]
- Authentication: GitLab username and password (not with 2FA), a personal, deploy, project or group access token, or the GitLab CLI; a token needs `read_registry` to pull and `write_registry` together with `read_registry` to push. [DOC S-owkwtkdm, S-jk4rtq6g]
- In CI, `CI_REGISTRY_USER` and `CI_REGISTRY_PASSWORD` hold a per-job user with read-write access, or the job token logs in with `gitlab-ci-token`; the job token reads and writes the running project's registry and, for others, the job token allowlist decides. [DOC S-owkwtkdm]
- Registry JWTs from a login last 5 minutes by default on GitLab Self-Managed and 15 minutes on GitLab.com, so a push that outlasts them fails with `unauthorized: authentication required`. [DOC S-owkwtkdm]
- The registry accepts Docker V2 and OCI images, and an OCI 1.1 manifest `subject` field links Cosign signatures to an image; the OCI 1.1 Referrers API is not fully implemented. [DOC S-5lpubwd5]
- Open: whether `--index-url` with `--no-index` installs from the GitLab index as the page advises, and whether an image can be pulled by `@sha256:` digest from the GitLab registry, are not shown on any GitLab page read. [UNK: the PyPI page states the advice only; no registry page shows a digest pull]
### Visibility
- `container_registry_access_level` is `enabled` (default: visible to everyone with access to the project, public if the project is public), `private` (project members with Reporter or higher) or `disabled`. [DOC S-gqpmeuse, S-5lpubwd5]
- With `private`, anonymous users and Guests can neither view the registry nor pull, in a public, internal or private project; with `enabled`, a public project's registry is open to anonymous users, an internal project's to Guests and above, and a private project's to Reporter and above. [DOC S-5lpubwd5]
- The package registry's visibility is independent of the repository's: Public lets anyone pull and view and a Developer publish; Internal needs Guest to view or pull; Private needs Reporter to view or pull; publishing always needs Developer. [DOC S-n3qvicph]
- **Allow anyone to pull from package registry** (a project setting, which an administrator can hide through `package_registry_allow_anyone_to_pull_option`) opens pulls for private and internal projects; the page lists project endpoints, NuGet group endpoints (not anonymously), the Maven group endpoint and Terraform namespace endpoints as supported, and calls other group and instance endpoints not fully supported. [DOC S-n3qvicph]
- So the PyPI group index is not among the endpoints for which anonymous pulls are documented, and a registry that must stay out of reach of anonymous users needs the project private or the feature level `private`. [DER S-n3qvicph, S-v25mipeh, S-5lpubwd5: the group endpoint support list and the visibility tables]
- So pinning for an agent estate: a PyPI dependency by SHA256 (`pip install --require-hashes` puts pip into hash-checking mode), a generic file by the `file_sha256` it published, an image by the `digest` of the tag at build time; each is read from the registry at release, and the group index stays an index, not a pin. [DER S1507, S-ocjsmgvx, S-fo6cckzx, S-gqpmeuse, S-cx5yd4ae: stored hashes and digests, pip's hash-checking mode, the standard digest pull form]

## Reference
| Registry | Publish | Pull | Fixed by | Group level |
|---|---|---|---|---|
| PyPI | twine to the project endpoint | project or group index | SHA256, MD5 | pull only |
| Generic | `PUT` of one file | project | SHA256 | none |
| Container | `docker push` to the project path | project path | tag `digest` | list only |

See also `gitlab/deploy-keys-and-tokens.md` (deploy tokens and access tokens), `gitlab/project-settings-api.md` (`container_registry_access_level`), `security/supply-chain.md` (hash and digest pinning), `agents/api-tokens-issue-and-store.md`.

## Examples
- SNIPPET: read an image tag's digest to pin it; context: GitLab 19.x, a token that may read the project's registry, ids from the repository list call; checked: no [DER S-gqpmeuse: endpoint and the `digest` response field]
```bash
curl --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  --url "https://gitlab.corp.example.com/api/v4/projects/<project_id>/registry/repositories/<repository_id>/tags/<tag_name>"
```
