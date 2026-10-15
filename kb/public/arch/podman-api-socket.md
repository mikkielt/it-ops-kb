---
topic: arch/podman-api-socket
priority: P3
applies_to: "Podman 6.1.x on Linux: podman system service, podman.socket and podman.service, Docker-compatible API for DOCKER_HOST clients"
retrieved_utc: 2026-10-15
sources: [S-noii6ew2, S-rylxmcjm, S742]
status: partial
---

# Podman's API service and the Docker-compatible socket

## Summary
`podman system service` serves a REST API on a Unix socket (or TCP). One layer imitates the Docker Engine API, so tools that read `DOCKER_HOST` (docker CLI, docker-compose, Testcontainers) can talk to Podman; the other is Podman's own Libpod API. Packaged systemd units start it on demand through socket activation: a user unit for rootless and a system unit for rootful, each with its own socket path. The API gives its caller everything Podman can do, so the socket is a credential.

## Facts
- `podman system service` answers API calls; it is available on Linux and is usually run from systemd, and is not available when the Podman command runs directly on a Windows or macOS host or otherwise talks to a remote service. [DOC S-noii6ew2]
- The REST API has two parts: a compatibility layer for the Docker v1.40 API and the Podman-native Libpod layer; both are versioned and the server does not reject a request that sets an unsupported version. [DOC S-noii6ew2]
- The command supports systemd socket activation: the service starts when a client first connects, and exits after the `--time` inactivity period, after which `podman.service` is inactive until the next connection. [DOC S-noii6ew2]
- `--time` / `-t` is the session timeout in seconds, 5 by default, and `0` means no timeout; the default can be changed with `service_timeout` in `containers.conf`. [DOC S-noii6ew2]
- The user units are `/usr/lib/systemd/user/podman.service` and `podman.socket`; the socket listens on `%t/podman/podman.sock`, where `%t` expands to `XDG_RUNTIME_DIR`. [DOC S-noii6ew2]
- The system units `/usr/lib/systemd/system/podman.service` and `podman.socket` run rootful Podman on `/run/podman/podman.sock`. [DOC S-noii6ew2]
- The command supports only one listening socket, and the default unit files change the log level from `error` to `info`, which adds information on each API call. [DOC S-noii6ew2]
- Run directly, the command takes an endpoint URI such as `unix:///tmp/foobar.sock` or `tcp://localhost:8080`; the default is `unix:///run/podman/podman.sock` for rootful and `unix://$XDG_RUNTIME_DIR/podman/podman.sock` for rootless (for example `/run/user/1000/podman/podman.sock`). [DOC S-noii6ew2]
- Starting the rootless socket is `systemctl --user start podman.socket`; keeping it across reboots uses `systemctl --user enable podman.socket` together with `loginctl enable-linger USER`; the rootful form is `sudo systemctl start|enable podman.socket`. [DOC S-noii6ew2]
- Docker API tools are pointed at the socket with `DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock`; the page's example runs `docker-compose up` that way. [DOC S-noii6ew2]
- To use the socket from inside a container, mount it as a volume and run the container with `--security-opt label=disable`. [DOC S-noii6ew2]
- The API grants full access to all Podman functionality and so arbitrary code execution as the user running it, with no way to limit or audit it; the model relies on Unix socket file permissions so only that user can connect. [DOC S-noii6ew2]
- TLS can protect the socket (`--tls-cert`, `--tls-key`, and `--tls-client-ca` to require client certificates); the page strongly recommends against a `tcp` endpoint without mutual TLS, notes that localhost access still lets anyone on the host in, and recommends forwarding the socket over SSH; with `tcp` and no TLS, `--cors` is advised. [DOC S-noii6ew2]
- The `podman` client's `--url` (default from `containers.conf`; rootless `unix:///run/user/$UID/podman/podman.sock`, root `unix:///run/podman/podman.sock`) switches it to remote mode, as does `--connection` (a saved connection, default from `containers.conf`); saved connections are kept in `~/.config/containers/podman-connections.json` unless `PODMAN_CONNECTIONS_CONF` says otherwise. [DOC S-rylxmcjm]
- Defaults of most flags on a remote call come from the server's `containers.conf`. [DOC S-rylxmcjm]
- Handing the socket to a container, a CI job or an agent hands over the right to run any container as that user (root for the rootful socket), so it is held to the same tier as a root or service-account credential: a rootless socket owned by a dedicated account, a path not shared between accounts, and no `tcp` endpoint. [DER S-noii6ew2: full access, no limits or audit; Unix permissions are the only barrier]
- Testcontainers, which the kb's Postgres test article documents as needing a Docker-API runtime with Podman reached through `DOCKER_HOST`, therefore needs `podman.socket` started in the same account as the tests and `DOCKER_HOST` set to that account's socket path; because socket activation is on demand, the first connection starts the service. [DER S-noii6ew2: socket path and activation; Testcontainers' documented `DOCKER_HOST` use is in `python/testcontainers-postgres-pytest.md`]
- Claude Code's read-only command set prompts for `docker` with a flag that selects another daemon and lists Podman's `--url` and `--connection` among them, which matches the client switching to a remote service. [DER S742, S-rylxmcjm: `claude/powershell-tool.md` permission rule; `--url` and `--connection` in `podman(1)`]
- How completely the compatibility layer covers Docker features that newer Docker API versions added, and which docker-compose features work, are not stated on the page read. [UNK: logged in `_gaps.md`]

## Reference
| mode | socket | unit | source |
|---|---|---|---|
| rootless | `$XDG_RUNTIME_DIR/podman/podman.sock` | `podman.socket` (user) | S-noii6ew2 |
| rootful | `/run/podman/podman.sock` | `podman.socket` (system) | S-noii6ew2 |
| custom | `podman system service --time 0 unix:///path` | none (foreground) | S-noii6ew2 |
- `python/testcontainers-postgres-pytest.md` — Testcontainers with Podman through `DOCKER_HOST`.
- `claude/powershell-tool.md` — the Manual-mode prompt for flags that select another daemon.
- `arch/podman-rootless-config.md` — rootless runtime directories the socket lives under.
- `arch/podman-quadlet-systemd.md` — Quadlet units, a different systemd integration.

## Examples
- SNIPPET: start the rootless Podman API socket and point a Docker-API client at it; context: Podman with systemd user session, run as the account that owns the containers; checked: no [DOC S-noii6ew2: `systemctl --user start podman.socket`, `DOCKER_HOST` path]
```
systemctl --user start podman.socket
export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock
docker-compose up
```
