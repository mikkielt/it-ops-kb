---
topic: arch/docker-secrets-run-secrets
priority: P3
applies_to: "Docker secrets (Swarm and Compose) mounted under /run/secrets in Linux containers"
retrieved_utc: 2026-10-11
sources: [S-5wya5dr3, S-tu43jdaj]
status: complete
---

# Docker secrets under /run/secrets, never environment variables

## Summary
Docker delivers a secret to a Linux container as a file under `/run/secrets/<name>`, not as an environment variable. Swarm keeps the secret encrypted and mounts it in an in-memory filesystem; Compose bind-mounts a file. Applications read the file, or a `*_FILE` variable that names the path.

## Facts
- Swarm secrets are encrypted in transit and at rest, are accessible only to services granted explicit access, and only while those services' tasks run. [DOC S-5wya5dr3]
- A granted secret is mounted decrypted into the container's in-memory filesystem, by default at `/run/secrets/<secret_name>` in Linux containers; the location can be changed with the `target` option. [DOC S-5wya5dr3]
- When a task stops, its decrypted secrets are unmounted and flushed from the node's memory; a secret mounted into a container is absent from an image committed from that container. [DOC S-5wya5dr3]
- A secret in use by a running service cannot be removed; to rotate, add a version or date to the secret's name, grant the new one and revoke the old with `docker service update --secret-rm`. [DOC S-5wya5dr3]
- In Compose a secret is mounted as a file at `/run/secrets/<secret_name>` inside the container, supported for Linux containers only because Compose bind-mounts a single file and Windows containers can only bind-mount directories. [DOC S-tu43jdaj]
- Getting a secret into a Compose container takes two steps: define it in the top-level `secrets` element (from a `file:` or an `environment:` source on the host), then list it in the service's `secrets` attribute; access is granted per service. [DOC S-tu43jdaj]
- Compose's own page gives the reason for files over variables: environment variables are often available to all processes, access is hard to track, and they can be printed in debug logs. [DOC S-tu43jdaj]
- Secrets in Compose allow granular access control inside the container through ordinary filesystem permissions; some images accept `*_FILE` variables (for example `MYSQL_PASSWORD_FILE=/run/secrets/db_password`) that point at the secret file. [DOC S-tu43jdaj]
- A Swarm service secret needs a swarm (secrets are stored in the swarm's encrypted Raft log); for a single host without Swarm the Compose form, a file bind-mounted from the host, is the available one. [DER S-5wya5dr3, S-tu43jdaj: Raft-log storage versus Compose file bind mount]
- On a host managed by a pull agent the source file belongs under a root-owned directory outside the git checkout, and the agent never writes the value into an `environment:` entry or a command line. [DER S-tu43jdaj: environment variables visible to all processes and logs]

## Reference
| form | where the secret appears | source |
|---|---|---|
| Swarm service secret | `/run/secrets/<name>` (in-memory), `target` to rename | S-5wya5dr3 |
| Compose `secrets:` with `file:` | `/run/secrets/<name>` (bind mount) | S-tu43jdaj |
| `*_FILE` variable | holds the path, not the value | S-tu43jdaj |

## Examples
- SNIPPET: Compose service reading a secret from a file; context: Docker Compose on Linux; checked: no [DOC S-tu43jdaj: single-service secret injection pattern]
```yaml
services:
  myapp:
    image: myapp:latest
    secrets:
      - db_password
secrets:
  db_password:
    file: /etc/myapp/secrets/db_password
```
