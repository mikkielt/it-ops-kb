---
topic: arch/podman-volumes-networks-pods
priority: P3
applies_to: "Podman 6.1.x on Linux: podman run --volume, podman network create and --network modes (netavark, pasta), podman pod create"
retrieved_utc: 2026-10-15
sources: [S-mpuaxmzf, S-tzyfmscm, S-hy3fameh, S-v4l2d5bl, S-l5z3fi2w, S-y4qlxukm]
status: complete
---

# Podman volumes, networks and pods

## Summary
`-v` mounts a bind path or a named volume (created on first use); the `:z`, `:Z` and `:U` suffixes change SELinux labels or ownership of the source, so they act on the host filesystem. Networking is netavark-based bridge networks for root and pasta for rootless by default; user-defined bridge networks get container-name DNS. A pod is a group of containers sharing namespaces through an infra container, the same shape as a Kubernetes pod.

## Facts
- `-v SOURCE:DEST` bind-mounts a host directory when the source is a path and mounts a named volume when it is a name; a missing named volume is created, unless the `nocreate` option is given, which makes the run fail instead. [DOC S-mpuaxmzf]
- A `-v` without a source makes an anonymous volume with a random name, removed with the container by `--rm` or by `podman rm --volumes`. [DOC S-mpuaxmzf]
- Volumes mount read-write by default, `:ro` makes one read-only; with the remote client (including macOS and Windows hosts outside WSL2) a volume is mounted from the remote server, not the client machine. [DOC S-mpuaxmzf]
- The first time a named volume is mounted, Podman chowns its mount point to the container's process user when the volume is unused, empty and not managed by an external volume driver. [DOC S-mpuaxmzf]
- The `:U` suffix recursively changes the owner and group of the source to the host UID and GID that map to the container's user; it can delay start for volumes with many files and modifies the host filesystem. [DOC S-mpuaxmzf]
- By default Podman does not change SELinux labels set by the OS; `:z` relabels the source with a shared label that several containers can use, and `:Z` with a private label that only this container (or the containers of a pod) can use. [DOC S-mpuaxmzf]
- Relabelling walks the whole file tree under the source, so `:z` or `:Z` on a large or system directory such as a home directory is a broad change, not a per-mount tweak. [DER S-mpuaxmzf: relabelling and `:U` chown walk the file system under the volume]
- `podman network create` creates a bridge network by default; `-d macvlan` creates a macvlan network, with the parent device given by `-o parent=DEVICE` or `--interface-name`, and with no options Podman picks a free subnet and a name. [DOC S-hy3fameh]
- Container-to-container name resolution through the DNS plugin works only with the `bridge` driver, and `--disable-dns` turns it off for a network. [DOC S-v4l2d5bl]
- The only supported `network_backend` is netavark; an empty value means netavark. [DOC S-l5z3fi2w]
- The default network is named `podman` with a `/16` subnet in the 10.88 range (`default_subnet`); it is the default for rootful containers and not for rootless ones, and neither value should change while containers use it. [DOC S-l5z3fi2w]
- `--network private` uses `bridge` for rootful containers and `pasta` for rootless ones; `pasta` is only supported in rootless mode and copies the host's addresses and routes into the container. [DOC S-tzyfmscm]
- Other `--network` modes are `none` (a namespace with no interfaces), `host` (the host's namespace, which also exposes abstract Unix sockets and localhost TCP and UDP sockets to the container), `container:ID` and `ns:PATH`; options not recognised in bridge mode are passed to netavark without validation. [DOC S-tzyfmscm]
- Pasta options can be given inline (`--network pasta:--map-gw`) or through `pasta_options` in the `[network]` table of `containers.conf`. [DOC S-tzyfmscm]
- Rootless bridge networks forward published ports through `rootlessport`, which does not keep the client's source address; pasta forwarding does. [DOC S-tzyfmscm]
- `podman pod create` makes an empty pod; containers join with `podman create --pod NAME` and `podman pod start NAME` starts it. [DOC S-y4qlxukm]
- A pod has an infra container by default (`--infra=true`), a lightweight container that holds the pod's shared kernel namespaces; without `--infra-image` Podman builds a local image for it, so nothing is pulled. [DOC S-y4qlxukm]
- `--share` takes a list of namespaces from cgroup, ipc, net, pid and uts; an empty value shares none and then no infra container is created unless `--infra=true` is given. [DOC S-y4qlxukm]
- The pod exit policy is `continue` by default (the infra container keeps the pod alive after the last container exits); `stop` stops the whole pod, and is the policy used for `kube play` and for Quadlet pods. [DOC S-y4qlxukm]
- Pod-level resource flags set limits on the pod's cgroup parent; a container joining the pod may set a lower limit of its own, and a container with its own cgroup namespace (`--cgroupns=host`) does not get the pod's limits. [DOC S-y4qlxukm]
- Ports of a pod are published on the pod itself with `podman pod create --publish`, not on its member containers, and the set cannot be changed after the pod is created. [DOC S-y4qlxukm]
- Because the member containers of a pod share the `net` namespace held by the infra container, two of them cannot listen on the same port. [DER S-y4qlxukm: `--share` list includes net; infra container coordinates the shared namespaces]

## Reference
| need | form | source |
|---|---|---|
| shared volume, SELinux | `-v SRC:/dst:z`; private `:Z` | S-mpuaxmzf |
| fix owner of a bind source | `-v SRC:/dst:U` | S-mpuaxmzf |
| user-defined bridge with DNS | `podman network create NAME` then `--network NAME` | S-hy3fameh, S-v4l2d5bl |
| rootless default network | `pasta` | S-tzyfmscm |
| pod without infra | `podman pod create --infra=false` | S-y4qlxukm |
- `arch/podman-rootless-config.md` — rootless limits that shape these options (ports below 1024, pasta self-connection).
- `arch/podman-quadlet-systemd.md` — `.volume`, `.network` and `.pod` Quadlet files map to these objects.
- `python/testcontainers-postgres-pytest.md` — a Postgres container with a published port, run through Podman's Docker-compatible socket.

## Examples
- SNIPPET: a user-defined network and a container attached to it with a private SELinux label on a data directory; context: Podman 6.x rootful or rootless on a SELinux host, placeholder names and registry; checked: no [DER S-hy3fameh, S-mpuaxmzf, S-tzyfmscm: network create, `--network NAME`, `:Z` suffix]
```
podman network create app-net
podman run -d --name db --network app-net -v /srv/db:/var/lib/data:Z registry.corp.example.com/db:1
```
