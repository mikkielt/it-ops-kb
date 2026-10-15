---
topic: security/almalinux-repositories-vault-pins
priority: P3
applies_to: "AlmaLinux 8, 9 and 10 repositories (ids, enabling, mirrorlist and baseurl), the vault layout for old minor releases, and holding a host on one minor with dnf releasever or versionlock"
retrieved_utc: 2026-10-15
sources: [S-46pbwuai, S-abrr4vdk, S-radwxzmz, S-k5qsqa2h, S-ecy4u4kc, S-7dwilv5i, S-gyovlkot, S-sjuiftqx, S-5z37fswu, S-b3frgffj, S-mhtf6uy4, S-il5vgghs]
status: partial
---

# AlmaLinux repositories, the vault and minor-release pins

## Summary
An AlmaLinux host reads BaseOS, AppStream and Extras by default and enables the other repositories by id with `dnf config-manager --set-enabled`. Old minor releases are not served from the normal tree: their `repo.almalinux.org` directory holds a README that points to `vault.almalinux.org`, where each minor has its own directory with the same repository names. No official how-to for holding a host on one minor was found; the mechanism follows from the repository files and the dnf documentation (`releasever` variable, `/etc/dnf/vars`, `versionlock`). The vault's 2024 move is in `security/linux-patching-and-pins.md`; lifecycle dates are in `security/almalinux-lifecycle-rhel-relation.md`.

## Facts
- BaseOS, AppStream and Extras are enabled by default on AlmaLinux 8 and 9; every other repository on the wiki's list is enabled by hand. [DOC S-46pbwuai]
- The wiki enables the optional repositories with `dnf config-manager --set-enabled <id>`: `crb` on 9 (`powertools` on 8), `highavailability` on 9 (`ha` on 8), and `plus`, `rt`, `nfv`, `resilientstorage`, `sap` and `saphana` on both. [DOC S-46pbwuai]
- Testing and Devel are installed as release packages instead (`dnf install almalinux-release-testing`, `almalinux-release-devel`); the page says not to install from Testing on production machines and that Devel is not for runtime dependencies or long-term use. [DOC S-46pbwuai]
- `plus` holds packages that replace a core component with patched functionality, marked `.plus` in the version tag and not available upstream; CRB is the AlmaLinux name for the PowerTools or CodeReady Builder repository. [DOC S-46pbwuai]
- Any repository intended for RHEL or CentOS can be used on AlmaLinux; the project also hosts CentOS SIG, EPEL and ELRepo instructions and its own Synergy repository for packages not in RHEL or EPEL. [DOC S-abrr4vdk]
- In the `almalinux-release` package's `almalinux-baseos.repo` (a9 branch, pinned commit), the `[baseos]` section is enabled with `gpgcheck=1` and reads a mirrorlist `https://mirrors.almalinux.org/mirrorlist/$releasever/baseos`; the `baseurl` `https://repo.almalinux.org/almalinux/$releasever/BaseOS/$basearch/os/` is commented out. [CODE S-radwxzmz: almalinux-baseos.repo#baseos]
- The same file's `[baseos-debuginfo]` and `[baseos-source]` sections are `enabled=0`, and their commented `baseurl` lines point at `https://vault.almalinux.org/$releasever/BaseOS/debug/$basearch/` and `.../BaseOS/Source/`. [CODE S-radwxzmz: almalinux-baseos.repo#baseos-debuginfo]
- `almalinux-crb.repo` has the same shape with the repository id `crb` and `enabled=0` for `[crb]`, `[crb-debuginfo]` and `[crb-source]`. [CODE S-k5qsqa2h: almalinux-crb.repo#crb]
- The `repo.almalinux.org/almalinux/9.4/` directory, read on 2026-10-15, held only a README: it calls the directory deprecated, tells normal users to use `/9/` and not `/9.4/`, and sends anyone who must stay at 9.4 to `https://vault.almalinux.org/9.4/`. [DOC S-ecy4u4kc]
- The vault index lists one directory per minor release (8.3 to 8.10, 9.0 to 9.8, 10.0 to 10.2), a `-beta` directory for most, the rolling `8`, `9` and `10`, `10-kitten`, `almalinux-epel`, `almalinux-nvidia` and release RPMs; the listing was read on 2026-10-15. [DOC S-7dwilv5i]
- A minor directory of the vault (9.4, read 2026-10-15) holds `AppStream`, `BaseOS`, `CRB`, `HighAvailability`, `NFV`, `RT`, `ResilientStorage`, `SAP`, `SAPHANA`, `devel`, `extras`, `plus`, `synergy`, `testing`, `isos`, `live`, `cloud` and `metadata`, among others. [DOC S-gyovlkot]
- Under it `9.4/BaseOS/` has `x86_64`, `aarch64`, `ppc64le`, `s390x`, `i686`, `debug` and `Source`; the listing was read on 2026-10-15. [DOC S-sjuiftqx]
- `9.4/BaseOS/x86_64/` has `os` and `kickstart`; the listing was read on 2026-10-15. [DOC S-5z37fswu]
- The vault path of a repository is therefore `<minor>/<Repo>/<arch>/os/`, the shape of the commented `baseurl` lines in the repo files. [DER S-sjuiftqx, S-5z37fswu, S-radwxzmz: the vault listings against the repo file's path pattern]
- The wiki describes the vault as holding packages and ISOs for previous AlmaLinux OS versions, plus 32-bit packages for the latest stable version; the redirect from `repo.almalinux.org/vault` is in `security/linux-patching-and-pins.md`. [DOC S-46pbwuai]
- dnf's `releasever` option is used to substitute `$releasever` in repository configuration; `$releasever_major` and `$releasever_minor` are derived from it by splitting on the first `.`. [DOC S-b3frgffj]
- `dnf --releasever=<release>` configures dnf as if the distribution release was `<release>`, which can change cache paths, values in configuration files and mirrorlist URLs. [DOC S-mhtf6uy4]
- Any file in `/etc/dnf/vars` (default `varsdir`: `/etc/dnf/vars` and `/etc/yum/vars`) becomes a variable named after the file, or overrides the built-in variables except those set on the command line. [DOC S-b3frgffj]
- The `versionlock` plugin keeps only the listed name-version pairs available for transactions; `dnf versionlock add <spec>` writes the lock, `add --raw 'bash-5.*'` locks a pattern, and the list file named by `locklist` in `/etc/dnf/plugins/versionlock.conf` must exist, though it may be empty. [DOC S-il5vgghs]
- The plugin does not apply excludes to non-transactional commands such as `repoquery`, `list` or `info`, and does not affect packages passed to dnf as local files. [DOC S-il5vgghs]
- A minor pin on an AlmaLinux 9 host has two parts: dnf's `releasever` set to the minor (`9.4`, through `--releasever` or an `/etc/dnf/vars/releasever` file) and each repository's `baseurl` set to the vault, as `https://vault.almalinux.org/$releasever/<Repo>/$basearch/os/`; the `$releasever` of an unpinned host is the major, because the normal tree is addressed as `/9/`. [DER S-radwxzmz, S-ecy4u4kc, S-b3frgffj, S-mhtf6uy4, S-5z37fswu: the repo file's path pattern, the 9.4 README, the variable rules and the vault listing]
- A pin by package version instead of by minor is `dnf versionlock add` for named packages; it leaves the rest of the host on the major's current content, and the plugin's own page does not tie it to a release or repository. [DER S-il5vgghs: lock scope is a package name and version]
- A pull agent that holds a host on a minor should write the repository `baseurl` and `releasever` itself (the files `/etc/yum.repos.d/almalinux-*.repo` and `/etc/dnf/vars/releasever`) and keep `dnf-automatic*.timer` off, as for the other families in `security/linux-patching-and-pins.md`. [DER S-radwxzmz, S-b3frgffj, S-ecy4u4kc: a minor in the vault no longer gets updates, so a fixed `baseurl` replaces the mirrorlist]
- Whether `mirrors.almalinux.org` answers a mirrorlist request for a minor such as `9.4`, and the AlmaLinux-side recommendation for pinning, were not found in the pages read. [UNK: logged in `_gaps.md`]

## Reference
| need | where | source |
|---|---|---|
| current content of a major | `https://repo.almalinux.org/almalinux/<major>/<Repo>/<arch>/os/` | S-radwxzmz, S-ecy4u4kc |
| old minor release | `https://vault.almalinux.org/<minor>/<Repo>/<arch>/os/` | S-ecy4u4kc, S-5z37fswu, S-sjuiftqx |
| enable CRB (9 / 8) | `dnf config-manager --set-enabled crb` / `powertools` | S-46pbwuai |
| repo files | `/etc/yum.repos.d/almalinux-*.repo` from `almalinux-release` | S-radwxzmz |
| hold one package | `dnf versionlock add <spec>` | S-il5vgghs |

Related: `security/almalinux-lifecycle-rhel-relation.md`, `security/almalinux-elevate.md`, `security/linux-patching-and-pins.md`.

## Examples
- SNIPPET: a vault repository file for a host held at 9.4; context: AlmaLinux 9, `/etc/dnf/vars/releasever` containing `9.4`; checked: no [DER S-radwxzmz, S-5z37fswu, S-b3frgffj: path shape from the repo file and the vault listing, variable from the dnf variable-file rule]
```
# /etc/yum.repos.d/almalinux-baseos.repo  (BaseOS only; repeat for AppStream, CRB, extras)
[baseos]
name=AlmaLinux $releasever - BaseOS (vault)
baseurl=https://vault.almalinux.org/$releasever/BaseOS/$basearch/os/
enabled=1
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-AlmaLinux-9
```
