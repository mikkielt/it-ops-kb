---
topic: arch/buildkit-build-secrets
priority: P3
applies_to: "BuildKit and Docker Buildx build-time secrets: RUN --mount=type=secret against ARG and ENV, and what image history and provenance keep"
retrieved_utc: 2026-10-11
sources: [S-k2cfmmuo, S-wt5ys5zb, S-iuwgvvo2, S-5wya5dr3]
status: complete
---

# BuildKit build secrets: secret mounts against build arguments

## Summary
A secret needed only while an image builds goes in through `docker build --secret` and a `RUN --mount=type=secret` mount, which exists for that one instruction and is not committed to a layer. A `--build-arg` or `ENV` value is the wrong carrier: an `ARG` is readable in `docker history` and, in `max` provenance, in the attestation, and an `ENV` persists in every container. Runtime secrets are a separate mechanism (`arch/docker-secrets-run-secrets.md`).

## Facts
- Docker's build docs call build arguments and environment variables inappropriate for secrets because they persist in the final image; secret mounts and SSH mounts expose secrets to a build without that. [DOC S-k2cfmmuo]
- A secret is passed with `docker build --secret id=<id>,src=<file>` (or an `env=<VAR>` source, or the equivalent Bake `secret` attribute) and consumed with `RUN --mount=type=secret,id=<id>`; the secret exists in the build container only for the duration of that instruction. [DOC S-k2cfmmuo]
- By default the secret is a file at `/run/secrets/<id>`; `target` (also `dst`, `destination`) sets another path and `env` mounts it as an environment variable of that `RUN` instead of, or as well as, a file. [DOC S-k2cfmmuo, S-iuwgvvo2]
- A secret taken from an environment variable of the build client with `--secret id=API_TOKEN` is bound to a file of the same name; the value never appears in the Dockerfile or the command line. [DOC S-k2cfmmuo]
- Mount options are `id`, `target`, `env` (Dockerfile v1.10.0 and later), `required` (default `false`), `mode` (default `0400`), `uid` and `gid` (default `0`). [DOC S-iuwgvvo2]
- With `required` unset an unavailable secret does not fail the instruction, so the command runs with the secret missing; `required=true` makes it an error. [DOC S-iuwgvvo2]
- The secret value is mounted, not copied into the image: the reference describes the mount type as letting the build container read tokens or private keys "without baking them into the image". [DOC S-iuwgvvo2]
- On Windows containers the secret is a single read-only bind-mounted file with an ACL (`mode`, `uid` and `gid` are ignored), written in clear text on the builder and removed after the step, and an empty placeholder directory can remain at the target path in the layer. [DOC S-iuwgvvo2]
- SSH mounts forward an agent socket or key for steps such as cloning a private repository (`docker buildx build --ssh default`, `RUN --mount=type=ssh`, socket mode `0600`). [DOC S-k2cfmmuo, S-iuwgvvo2]
- BuildKit has two pre-defined secrets for private Git contexts and `ADD`: `GIT_AUTH_TOKEN` (Basic auth with the fixed user `x-access-token`) and `GIT_AUTH_HEADER` (a raw `Authorization` value, usable with GitLab through `gitlab-ci-token` and `CI_JOB_TOKEN`); a host suffix on the secret id sets them per host. [DOC S-k2cfmmuo]
- A build argument has no effect unless an instruction uses it and is not present in containers started from the image, but it may persist in the image metadata, in provenance attestations and in the image history. [DOC S-wt5ys5zb]
- Unlike `ENV`, an `ARG` is not embedded in the image's environment, yet it is visible in `docker history` and in `max` mode provenance attestations; the reference notes the Buildx GitHub Actions attach them by default for a public repository. [DOC S-iuwgvvo2]
- Environment variables set with `ENV` persist in containers instantiated from the image. [DOC S-wt5ys5zb]
- The pre-defined proxy arguments (for example `HTTP_PROXY`) are left out of `docker history` and the cache key unless the Dockerfile redeclares them with `ARG`, which puts the value in the history again. [DOC S-iuwgvvo2]
- `BUILDX_METADATA_PROVENANCE` sets only the provenance information in the metadata file written through the `--metadata-file` flag: `min` (the default), `max`, or `disabled`, `false` or `0` for none. [DOC S-wt5ys5zb]
- BuildKit v0.11 and later adds provenance attestations to the images it builds by default, and `BUILDX_NO_DEFAULT_ATTESTATIONS=1` turns those default attestations off. [DOC S-wt5ys5zb]
- A value that was ever passed as a build argument or `ENV` and then pushed is readable by anyone who can pull the image or its attestation, so the fix is to revoke or roll it at its issuer (`auth/issuer-token-rotation.md`), not to rebuild without it. [DER S-wt5ys5zb, S-iuwgvvo2: history, attestation and image metadata keep the value]
- For a private GitLab context the Docker example builds the `GIT_AUTH_HEADER` secret from the CI job's own token (`CI_JOB_TOKEN`), so the build needs no stored personal token. [DER S-k2cfmmuo: the GIT_AUTH_HEADER example]

## Reference
| Carrier | In `docker history` | In the final image or containers | In provenance | Use for a secret |
|---|---|---|---|---|
| `--build-arg` + `ARG` | yes (used values) | not in the image environment | yes in `max` mode | no |
| `ENV` | yes (config) | yes, in every container | n/a | no |
| `--secret` + `RUN --mount=type=secret` | no | no (placeholder dir on Windows) | no | yes |
| `--ssh` + `RUN --mount=type=ssh` | no | no | no | yes (keys, agent) |

## Examples
- SNIPPET: install from a private index with a secret mounted for one step; context: Dockerfile frontend 1.10 or later, token in the client's environment as `API_TOKEN`; checked: no [DOC S-iuwgvvo2: `RUN --mount=type=secret` with `env`]
```dockerfile
# syntax=docker/dockerfile:1
FROM python:3
RUN --mount=type=secret,id=API_TOKEN,env=API_TOKEN,required=true \
    pip install --index-url "https://__token__:${API_TOKEN}@packages.corp.example.com/simple" mypackage
```
```console
$ API_TOKEN=<token> docker build --secret id=API_TOKEN .
```
