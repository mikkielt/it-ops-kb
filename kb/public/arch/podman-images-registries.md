---
topic: arch/podman-images-registries
priority: P3
applies_to: "Podman 6.1.x on Linux: registries.conf (container-libs image library), short-name resolution, podman login credentials"
retrieved_utc: 2026-10-15
sources: [S-ef6jtpqs, S-pfoyirmn, S-rylxmcjm]
status: partial
---

# Podman images and registries: registries.conf, short names and login

## Summary
Which registries Podman pulls from is set in `registries.conf` (TOML, shared by Podman, Buildah and Skopeo). A fully qualified image name needs no lookup; an unqualified ("short") name is resolved through aliases and the `unqualified-search-registries` list, under the `short-name-mode` policy. Credentials go to an `auth.json` under the runtime directory unless `--authfile` says otherwise.

## Facts
- `registries.conf` is read from `$XDG_CONFIG_HOME/containers/registries.conf` (else `$HOME/.config/containers/registries.conf`) if it exists, otherwise from `/etc/containers/registries.conf`, otherwise from `/usr/share/containers/registries.conf`; the format is TOML. [DOC S-ef6jtpqs]
- Drop-in `.conf` files come from `registries.conf.d`, `registries.rootful.conf.d` (uid 0) and `registries.rootless.conf.d` (uid above 0, with `$UID` subdirectory) under the user, `/etc/containers` and `/usr/share/containers` trees; they are read sorted by base name regardless of directory, and a later setting overwrites an earlier one. [DOC S-ef6jtpqs]
- `[[registry]]` tables from several files are merged by `prefix`: a table with the same prefix replaces the earlier one and a new prefix is added. [DOC S-ef6jtpqs]
- `CONTAINERS_REGISTRIES_CONF` names the file to use and, when set, the drop-in directories are not read; `CONTAINERS_REGISTRIES_CONF_OVERRIDE` names a file read last. [DOC S-ef6jtpqs]
- `unqualified-search-registries` is an ordered array of `host[:port]` registries tried when an image name is unqualified. [DOC S-ef6jtpqs]
- For a given image name only the `[[registry]]` table with the longest matching `prefix` applies; a prefix may start with a wildcard such as `*.example.com`, but a wildcard anywhere else does not work. [DOC S-ef6jtpqs]
- A registry is contacted with TLS by default; `insecure = true` on its table allows plain HTTP and untrusted certificates. [DOC S-ef6jtpqs]
- Short-name resolution first consults aliases, then follows `short-name-mode`: `enforcing` prompts on a terminal when several search registries exist and fails without one, `permissive` falls back to trying all search registries, and `disabled` uses all of them without prompting. [DOC S-ef6jtpqs]
- When `short-name-mode` is absent or empty the page says the default is `permissive`; a short name resolved after a prompt is recorded as an alias after a successful pull. [DOC S-ef6jtpqs]
- Recorded aliases are written to `/var/cache/containers/short-name-aliases.conf` for root and under `$HOME/.cache` for rootless users, and that machine-written file wins over an alias in `registries.conf`. [DOC S-ef6jtpqs]
- `podman login` stores credentials by default in `${XDG_RUNTIME_DIR}/containers/auth.json` as a base64 string, falls back to existing credentials in `$HOME/.docker/config.json`, and takes the file path from `--authfile`; without a registry argument it uses the first registry in the registries search list. [DOC S-pfoyirmn]
- `credential-helpers` in `registries.conf` defaults to `["containers-auth.json"]`, meaning auth files are used. [DOC S-ef6jtpqs]
- Podman's own page describes `${XDG_RUNTIME_DIR}/containers` as the place for temporary rootless configuration data. [DOC S-rylxmcjm]
- A registry credential that a unit or a CI job must still find after logout or reboot belongs in an explicit `--authfile` outside the runtime directory (the login page's own example uses `~/.config/containers/auth.json`), not in the default path; the file is a secret and stays out of argv and out of git. [DER S-pfoyirmn, S-rylxmcjm: default path under the runtime directory described as temporary; `--authfile` override]
- A script or unit that pulls a bare name such as `postgres:16` is only reproducible when the name is fully qualified, or when `unqualified-search-registries` and `short-name-mode` are set deliberately; with `enforcing` and several search registries, a job without a terminal fails instead of guessing. [DER S-ef6jtpqs: short-name modes and non-terminal behaviour]
- Which registries the distribution's shipped `registries.conf` lists, and which `short-name-mode` it sets, are not in the upstream pages read and differ by distribution. [UNK: logged in `_gaps.md`]

## Reference
| setting | meaning | source |
|---|---|---|
| `unqualified-search-registries` | ordered registries for short names | S-ef6jtpqs |
| `short-name-mode` | `enforcing`, `permissive` (default when empty), `disabled` | S-ef6jtpqs |
| `[[registry]] prefix`, `location`, `insecure`, `blocked` | per registry or namespace policy | S-ef6jtpqs |
| `podman login --authfile` | credential file instead of the runtime-directory default | S-pfoyirmn |
- `arch/podman-rootless-config.md` — where the other Podman configuration files live.
- `arch/podman-quadlet-systemd.md` — `AutoUpdate=registry` needs a fully qualified image name.
- `gitlab/package-registries.md` — GitLab's container registry as the pull target.

## Examples
- SNIPPET: registries drop-in with one search registry and a mirror-less private registry that needs HTTP; context: Podman registries.conf drop-in, placeholder hosts; checked: syntax [DOC S-ef6jtpqs: `unqualified-search-registries`, `[[registry]]` with `location` and `insecure`]
```toml
# /etc/containers/registries.conf.d/50-corp.conf
unqualified-search-registries = ["registry.corp.example.com"]

[[registry]]
location = "lab-registry.corp.example.com:5000"
insecure = true
```
