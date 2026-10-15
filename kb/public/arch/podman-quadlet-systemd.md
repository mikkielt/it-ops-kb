---
topic: arch/podman-quadlet-systemd
priority: P3
applies_to: "Podman 6.1.x Quadlet (podman-systemd.unit(5)) on Linux with systemd: .container, .pod, .volume, .network and .kube units, podman auto-update"
retrieved_utc: 2026-10-15
sources: [S-bw3wuvly, S-62kbyvpm, S-h4qvlvgv, S-rylxmcjm]
status: partial
---

# Podman Quadlet: systemd units for containers, pods, volumes and networks

## Summary
Quadlet is Podman's systemd generator. You write a `name.container` (or `.pod`, `.volume`, `.network`, `.build`, `.image`, `.kube`, `.artifact`) file in a search directory; at boot and on `systemctl daemon-reload` the generator turns it into a normal `.service` unit whose `ExecStart` is a `podman run` (or the matching command). Rootful and rootless use different search directories. `podman generate systemd` is deprecated in favour of it.

## Facts
- Quadlet files are read by a systemd generator at boot and on `systemctl daemon-reload` and produce regular `.service` unit files; both system and user units are supported. [DOC S-bw3wuvly]
- The generator reads `.container`, `.volume`, `.network`, `.build`, `.pod`, `.kube`, `.image` and `.artifact` files and writes a similarly named `.service` for each; a generated unit replaces a vendor service of the same name under `/usr`. [DOC S-bw3wuvly]
- Rootful search path, highest precedence first: `/run/containers/systemd/` (temporary), `/etc/containers/systemd/` (administrator), `/usr/share/containers/systemd/` (distribution). [DOC S-bw3wuvly]
- Rootless search path: `$XDG_RUNTIME_DIR/containers/systemd/`, `$XDG_CONFIG_HOME/containers/systemd/` or `~/.config/containers/systemd/`, `/etc/containers/systemd/users/${UID}`, `/etc/containers/systemd/users/`, and the same two under `/usr/share/containers/systemd/users/`. [DOC S-bw3wuvly]
- A file in `/etc/containers/systemd/users/` runs in every user's session at login, one in `.../users/${UID}/` only for that UID; subdirectories are searched recursively. [DOC S-bw3wuvly]
- Quadlet units do not run as another user through `User=`, `Group=` or `DynamicUser=`; to run rootless, create the user and put the file in a rootless search path. [DOC S-bw3wuvly]
- Keys of the custom section (`[Container]`, `[Pod]`, `[Volume]`, `[Network]`, `[Kube]`) are handled by Podman; every other section such as `[Unit]`, `[Service]` and `[Install]` passes to systemd unchanged. [DOC S-bw3wuvly]
- Drop-ins work as in systemd: `foo.container.d/*.conf` is merged in alphabetical order, and a dash in the name also searches the truncated names (`foo-.container.d`) and the type-wide `container.d`. [DOC S-bw3wuvly]
- A `[Container]` section needs only `Image=`; most keys map to a `podman run` flag (`PublishPort`, `Volume`, `Environment`, `Network`, `Exec`, `AutoUpdate` and so on), and `PodmanArgs=` and `GlobalArgs=` pass extra arguments. [DOC S-bw3wuvly]
- A `foo.container` creates `foo.service` and a Podman container named `systemd-foo`; `ContainerName=` overrides the name. [DOC S-bw3wuvly]
- `foo.volume` creates `foo-volume.service` and a volume `systemd-foo`, `foo.network` creates `foo-network.service` and a network `systemd-foo`, and `foo.pod` creates `foo-pod.service` and a pod `systemd-foo`; `VolumeName=`, `NetworkName=` and `PodName=` override the names. [DOC S-bw3wuvly]
- A `Volume=`, `Network=` or `Pod=` value that ends in `.volume`, `.network` or `.pod` links the container to that Quadlet unit and adds the systemd dependency between the two services. [DOC S-bw3wuvly]
- `Type=` need not be set: Quadlet uses `notify` for `.container` and `.kube`, `forking` for `.pod`, and `oneshot` for `.volume`, `.network`, `.build`, `.image` and `.artifact`. [DOC S-bw3wuvly]
- A generated service is transient, so `systemctl enable` does not work on it; the generator applies the `[Install]` section itself, and only `Alias`, `WantedBy`, `RequiredBy` and `UpheldBy` are honoured. [DOC S-bw3wuvly]
- Pulling or building an image can exceed systemd's default 90-second start limit; pre-pull the image or set `TimeoutStartSec` in `[Service]` (a `Type=oneshot` unit has the start timeout disabled by default). [DOC S-bw3wuvly]
- Quadlet requires cgroup v2; `podman info --format {{.Host.CgroupsVersion}}` shows the host's version. [DOC S-bw3wuvly]
- Quadlet adds `After=` and `Wants=` on `network-online.target` (root) or on `podman-user-wait-network-online.service` (user units), because user units cannot wait on system targets; `DefaultDependencies=false` in a `[Quadlet]` section turns this off. [DOC S-bw3wuvly]
- Dependencies written in `[Unit]` (`Requires`, `After`, `Wants`, `BindsTo`, `PartOf` and others) between Quadlet files are translated to the generated service names. [DOC S-bw3wuvly]
- Template and instance files work as in systemd: `foo@.container` generates `foo@.service`, and a symlink named `foo@` plus an instance name plus `.container` produces an instance that also reads the drop-ins of its own `.container.d` directory and of the template's. [DOC S-bw3wuvly]
- A unit that fails with "Unit example.service not found" may have a syntax error or an option from a newer Podman than the generator; `podman-system-generator --dryrun` (with `--user` for rootless) prints the generated files and errors, and `systemd-analyze --generators=true verify example.service` shows the errors. [DOC S-bw3wuvly]
- `QUADLET_UNIT_DIRS` set to a directory makes the generator read only that directory, which limits a dry run to the files under test. [DOC S-bw3wuvly]
- `podman auto-update` pulls new images and restarts the systemd units of containers whose `io.containers.autoupdate` label (or `AutoUpdate=` in a Quadlet file) is `registry` or `local`; the container must run inside a systemd unit. [DOC S-62kbyvpm]
- With `registry` the image is compared by digest with the registry and needs a fully qualified image name; with `local` the container's digest is compared with local storage; the default policy is disabled. [DOC S-62kbyvpm]
- Podman ships `podman-auto-update.service`, started daily at midnight by `podman-auto-update.timer`; the timer can be changed and the service started by hand or by another unit. [DOC S-62kbyvpm]
- `podman generate systemd` is marked deprecated in favour of Quadlet; the page says there are no plans to remove it, and that it gets urgent bug fixes only, no new features. [DOC S-h4qvlvgv]
- The `podman(1)` page points to Quadlet files as the way to manage containers, pods, volumes, networks and images declaratively through systemd. [DOC S-rylxmcjm]
- For a pull-based configuration agent, a Quadlet file in `/etc/containers/systemd/` is the unit of change: the agent writes the file, runs `systemctl daemon-reload`, and checks the generated unit with the generator's dry run or `systemd-analyze verify` before it starts the service. [DER S-bw3wuvly: generator runs at boot and on daemon-reload; dry run and verify as debugging tools]
- A container that must start without a login session needs a rootful unit or a lingering user; the Quadlet page does not state the lingering requirement for rootless units, and the socket page's own example uses `loginctl enable-linger` for a user socket. [UNK: Quadlet page silent; logged in `_gaps.md`]

## Reference
| file | generated service | Podman object | source |
|---|---|---|---|
| `foo.container` | `foo.service` | container `systemd-foo` | S-bw3wuvly |
| `foo.pod` | `foo-pod.service` | pod `systemd-foo` | S-bw3wuvly |
| `foo.volume` | `foo-volume.service` | volume `systemd-foo` | S-bw3wuvly |
| `foo.network` | `foo-network.service` | network `systemd-foo` | S-bw3wuvly |
- `arch/podman-volumes-networks-pods.md` — the objects these files create.
- `arch/podman-images-registries.md` — `AutoUpdate=registry` and registry credentials for pulls from a unit.
- `arch/podman-api-socket.md` — the `podman.socket` unit, a packaged (not Quadlet) systemd unit.
- `security/linux-patching-and-pins.md` — systemd timers for unattended upgrades on the host, a different layer.

## Examples
- SNIPPET: a rootful Quadlet container that starts at boot and is updated from its registry; context: Podman 6.x with systemd, file in `/etc/containers/systemd/`, placeholder registry; checked: no [DOC S-bw3wuvly: `Image`, `AutoUpdate`, `PublishPort`, `[Install] WantedBy`]
```
# /etc/containers/systemd/web.container
[Unit]
Description=Web front end

[Container]
Image=registry.corp.example.com/web:1
AutoUpdate=registry
PublishPort=8080:80

[Service]
Restart=always

[Install]
WantedBy=multi-user.target
```
