---
topic: arch/podman-rootless-config
priority: P3
applies_to: "Podman 6.1.x (man pages at tag v6.1.4) on Linux: rootless and rootful runs, state and configuration files (containers.conf, storage.conf)"
retrieved_utc: 2026-10-15
sources: [S-rylxmcjm, S-rif3pi6x, S-l5z3fi2w, S-b2bqmd6c]
status: complete
---

# Podman rootless and rootful runs, and where its state and configuration live

## Summary
Podman is a daemonless container engine with a Docker-comparable command line. The same binary runs rootful (as uid 0) or rootless (as a user, inside a user namespace built from `/etc/subuid` and `/etc/subgid`), and the two modes keep separate containers, images, storage and configuration. Defaults for flags come from `containers.conf`, image and container storage from `storage.conf`, and registries from `registries.conf` (see `arch/podman-images-registries.md`). Rootless mode is bounded by kernel rules, not by Podman: low ports, UID range, device nodes, NFS homes.

## Facts
- Podman describes itself as a daemonless container engine with a command line comparable to Docker's (the page says `alias docker=podman`), and most commands run as a regular user without extra privileges. [DOC S-rylxmcjm]
- Podman uses Buildah internally to build images; the two tools share image storage but not container storage. [DOC S-rylxmcjm]
- In rootless mode Podman creates a user namespace for the user from the ranges in `/etc/subuid` and `/etc/subgid`; the user must have an entry in both files, and whitespace in a row (trailing blanks included) can produce "no entry" failures. [DOC S-rylxmcjm]
- Containers created by a non-root user are not visible to other users and are not seen or managed by Podman running as root. [DOC S-rylxmcjm]
- Rootless Podman reads configuration under `$XDG_CONFIG_HOME` (else `$HOME/.config/containers`), pulls images under `$XDG_DATA_HOME` (else `$HOME/.local/share/containers/storage`), and keeps temporary configuration data under `${XDG_RUNTIME_DIR}/containers`. [DOC S-rylxmcjm]
- Rootless containers cannot bind ports below 1024 because the kernel refuses it without `CAP_NET_BIND_SERVICE`; the sysctl `net.ipv4.ip_unprivileged_port_start` lowers the limit (a value of 443 allows ports from 443). [DOC S-rif3pi6x]
- Since Podman 5.0 pasta is the default rootless network tool. [DOC S-rif3pi6x]
- Because pasta copies the host's main interface address into the container, a connection from one container to that address does not work, so container-to-container traffic through a published host port needs an explicit pasta configuration unless the host has more than one interface. [DOC S-rif3pi6x]
- Rootless bridge networks forward ports through `rootlessport`, a userspace proxy that does not preserve client source addresses; `rootless_port_forwarder="pasta"` in the `[network]` table of `containers.conf` switches to pasta forwarding and is marked experimental. [DOC S-rif3pi6x]
- A standard rootless setup maps only 65536 UIDs and GIDs, so images that use higher ids cannot be used or built; a user without `/etc/subuid` and `/etc/subgid` entries makes Podman commands fail. [DOC S-rif3pi6x]
- In an environment without extra subuids (HPC homes), rootless Podman can run with a single UID if `ignore_chown_errors` is set in `storage.conf`, which makes image pulls ignore chown errors. [DOC S-rylxmcjm]
- Rootless limits listed by the project: no resource limits on cgroup v1 hosts, no `podman container checkpoint` or `restore` (CRIU needs root), no creating device nodes (needs `CAP_MKNOD`, even for privileged containers), and directories from `podman mount` are visible only inside `podman unshare`. [DOC S-rif3pi6x]
- Rootless homes must be writable and not mounted `noexec` or `nodev`, and NFS or parallel-filesystem homes do not work because the server enforces file creation by UID and does not understand user namespaces. [DOC S-rif3pi6x]
- Native overlayfs for an unprivileged user needs Podman 3.1 or later and a Linux kernel 5.12 or later; otherwise the slower `fuse-overlayfs` is used. [DOC S-rif3pi6x]
- The default cgroup manager is `systemd`; `cgroupfs` does not work in rootless mode. [DOC S-rylxmcjm]
- `containers.conf` is read from `$XDG_CONFIG_HOME/containers/containers.conf` (else `$HOME/.config/containers/containers.conf`) if it exists, otherwise from `/etc/containers/containers.conf`, otherwise from `/usr/share/containers/containers.conf`. [DOC S-l5z3fi2w]
- Drop-in `.conf` files are also read from `containers.conf.d`, `containers.rootful.conf.d` (uid 0 only) and `containers.rootless.conf.d` (uid above 0, with a `$UID` subdirectory) under `$XDG_CONFIG_HOME/containers`, `/etc/containers` and `/usr/share/containers`; they are sorted by file name, the first directory wins for a repeated name, and later files override earlier values. [DOC S-l5z3fi2w]
- Setting `CONTAINERS_CONF` makes Podman ignore all system and user config files and load only that file; `CONTAINERS_CONF_OVERRIDE` names a file loaded last even then. [DOC S-l5z3fi2w]
- A `containers.conf` module sits in a `containers.conf.modules` directory, is not loaded by default, and is loaded on demand with `podman --module`. [DOC S-l5z3fi2w]
- Under `podman machine` (macOS and Windows hosts) the configuration files are edited inside the virtual machine through `podman machine ssh`. [DOC S-l5z3fi2w]
- `storage.conf` is searched in `/usr/share/containers/storage.conf`, then `/etc/containers/storage.conf`, then `$XDG_CONFIG_HOME/containers/storage.conf` (else `$HOME/.config/containers/storage.conf`), each with `storage.conf.d` and rootful or rootless drop-in directories. [DOC S-b2bqmd6c]
- The default storage root (`graphroot`) is `/var/lib/containers/storage` for root and `$XDG_DATA_HOME/containers/storage` (else `$HOME/.local/share/containers/storage`) rootless; the default `runroot` is `/run/containers/storage` or `$XDG_RUNTIME_DIR/containers` (else `/tmp/storage-run-$UID/containers`). [DOC S-b2bqmd6c]
- `rootless_storage_path` in `storage.conf` is deprecated in favour of `graphroot`; to move storage for every rootless user, place a file with `graphroot` under a `storage.rootless.conf.d` directory. [DOC S-b2bqmd6c]
- Currently pasta must be installed to create a network device for a rootless container; without it rootless containers run in the host's network namespace. [DOC S-rylxmcjm]
- Rootless Podman can use an NFS home directory if `graphroot` in `$HOME/.config/containers/storage.conf` points at local (non-NFS) storage. [DOC S-rylxmcjm]
- Because the rootful and the rootless stores are separate paths, `podman ps` as a user and `sudo podman ps` list different containers, and an image pulled in one mode is not present in the other. [DER S-rylxmcjm, S-b2bqmd6c: containers not visible across users; separate graphroot per mode]
- A host agent that manages Podman for several accounts has to address each account's Podman separately (its own `XDG_RUNTIME_DIR`, config and subuid range), and a rootless service account needs `/etc/subuid` and `/etc/subgid` entries before its first container. [DER S-rylxmcjm, S-rif3pi6x: per-user namespace and stores; subuid requirement]
- The rootless documentation gives one set of storage drivers as "overlay (optionally `fuse-overlayfs`) and VFS", while the `storage.conf` page lists "btrfs, overlay and vfs" as valid rootless drivers; the two pages were read at different repositories and the disagreement is recorded in `_conflicts.md`. [DER S-rif3pi6x, S-b2bqmd6c: the two driver lists differ]

## Reference
| need | where | source |
|---|---|---|
| engine defaults | `containers.conf` (user, `/etc`, `/usr/share`, drop-ins) | S-l5z3fi2w |
| storage root and driver | `storage.conf`, `graphroot`, `runroot` | S-b2bqmd6c |
| rootless id ranges | `/etc/subuid`, `/etc/subgid` | S-rylxmcjm |
| rootless limits | kernel rules listed in `rootless.md` | S-rif3pi6x |
- `arch/podman-images-registries.md`, `arch/podman-volumes-networks-pods.md`, `arch/podman-quadlet-systemd.md`, `arch/podman-api-socket.md` — the rest of the Podman area.
- `intune/network-profiles.md` — Microsoft Tunnel runs in a rootful or rootless Podman container on RHEL.
- `windows/delivery-optimization.md` — Connected Cache on RHEL requires replacing the default Podman engine.
- `arch/docker-secrets-run-secrets.md` — the Docker form of file-based secrets, for comparison.

## Examples
- SNIPPET: grant a service account a subuid and subgid range; context: rootless Podman on a Linux host, run as root, placeholder account name; checked: no [DOC S-rylxmcjm: usermod options as the man page gives them]
```
usermod --add-subuids 10000-75535 jan.kowalski
usermod --add-subgids 10000-75535 jan.kowalski
```
- SNIPPET: a user-level containers.conf drop-in that switches rootless port forwarding to pasta; context: rootless Podman, option marked experimental; checked: syntax [DER S-rif3pi6x, S-l5z3fi2w: `rootless_port_forwarder` in `[network]`; `containers.conf.d` drop-in directory]
```toml
# ~/.config/containers/containers.conf.d/10-network.conf
[network]
rootless_port_forwarder = "pasta"
```
