---
topic: security/gentoo-emerge-make-conf-etc-portage
priority: P3
applies_to: "Gentoo Linux Portage: how emerge resolves, installs, updates and removes packages, the make.conf variables and defaults, and the files under /etc/portage"
retrieved_utc: 2026-10-15
sources: [S-5hbh6sac, S-cvsv6e4z, S-c5iscbp4, S-hfgxhfhm, S-5lblcwaf, S-5dnrfnng, S-uhuj7vad, S-jcuv5ggt, S-cl6ijk7g, S-3v7thb2n, S-5rih6fam]
status: complete
---

# Gentoo emerge, make.conf and /etc/portage

## Summary
`emerge` is the command-line interface to Portage: it resolves dependencies from the ebuilds of the configured repositories under the profile, the USE flags and the keywords, then builds and installs (or fetches binary packages). Without `--ask` or `--pretend` it acts at once. A routine update is a repository sync followed by `emerge --update --deep --newuse @world`. Global settings live in `/etc/portage/make.conf` (a file or a directory), per-package ones in the `package.*` files, and the defaults under them come from the profile and Portage's own `make.globals`. Many `/etc/portage` entries can be directories, which lets a configuration tool own named files.

## Facts
- `emerge` is the main command-line interface to Portage and is used to download, install, update and maintain packages; it can also build from source, fetch binary packages, create binary packages, search and report system information. [DOC S-5hbh6sac]
- Given a package and no other option, `emerge` immediately tries to install it without asking; `--ask` (`-a`) shows the planned changes and asks, `--pretend` (`-p`) shows them and stops and needs no superuser privileges, and `--verbose` adds flags, download size and repository name. [DOC S-5hbh6sac]
- With `--ask`, an accidental Enter key press during processing skips the confirmation prompt. [DOC S-5hbh6sac]
- In the plan output `N` marks a new package, `U` an upgrade, `D` a downgrade and `R` a re-emerge; packages in the world file are shown in bold, the others are dependencies or from the system set. [DOC S-5hbh6sac]
- The Handbook's update procedure syncs the repository first, since Portage only reads the ebuilds on the system, then runs `emerge --update --deep @world`; without `--deep` only explicitly installed packages, those listed in `/var/lib/portage/world`, are checked and not their dependencies. [DOC S-cvsv6e4z]
- The standard update should include `--changed-use` or `--newuse` because profile changes or altered USE settings can require new or rebuilt packages. [DOC S-cvsv6e4z]
- A dependency that must be reinstalled should be emerged with `--oneshot` (`-1`), because `emerge <package>` otherwise adds it to the world file and may lead to issues. [DOC S-5hbh6sac]
- To uninstall, `emerge --deselect` marks a package as no longer wanted and `emerge --depclean` removes what is no longer needed; depclean keeps dependencies of installed packages and the `@system` and `@profile` sets, and its list should be reviewed with `--ask` or `--pretend`. [DOC S-5hbh6sac]
- The wiki warns not to use `--unmerge` (`-C`) unless its behaviour is specifically needed, because it removes important packages without warning, and that depclean after an update can try to remove current kernel sources or a required GCC. [DOC S-5hbh6sac]
- An interrupted multi-package emerge can continue from the failed package with `--resume`; `--keep-going` and `--skipfirst` are related. [DOC S-5hbh6sac]
- Sources are downloaded to `/var/cache/distfiles/` by default, and `--fetchonly` downloads without installing. [DOC S-cvsv6e4z]
- `emerge --info` prints system information that support requests and bug reports usually need. [DOC S-5hbh6sac]
- Environment variables set on the command line (`USE=svg emerge ...`) change one invocation only and are reverted by routine maintenance such as a system update; the wiki says they should not usually be used to install or update. [DOC S-5hbh6sac]
- Blocking packages appear as `[blocks B]` and are cleared by not installing one of the pair or deselecting the other; a fetch failure continues with the other packages and the wiki suggests retrying after an hour. [DOC S-cvsv6e4z]
- `/etc/portage/make.conf` is the main configuration file for the Portage environment at global level; it was `/etc/make.conf` before, and when both exist the `/etc/portage` one takes precedence. [DOC S-c5iscbp4]
- `make.conf` can be a directory, whose contents are summed as if it were one file; most variables are optional, may span lines and must not appear twice. [DOC S-c5iscbp4]
- A basic `make.conf` is installed when the stage file is unpacked, and `/usr/share/portage/config/make.conf.example` shows the variables; `man make.conf` is the full reference. [DOC S-c5iscbp4]
- The final configuration is not only `make.conf`: per-package files and environment variables refine it, and defaults come from Portage's package defaults and the profile. [DOC S-c5iscbp4]
- The `make.conf(5)` page at the pinned commit says `/etc/portage/make.conf` overwrites the values of the profile's `make.defaults`. [DOC S-5lblcwaf]
- The `portage(5)` page says `/usr/share/portage/config/make.globals` holds Portage's global default settings, which `make.conf` or `package.env` override. [DOC S-5dnrfnng]
- In `cnf/make.globals` at that commit the defaults include `DISTDIR="/var/cache/distfiles"`, `PKGDIR="/var/cache/binpkgs"`, `PORTAGE_TMPDIR="/var/tmp"`, `BINPKG_COMPRESS="zstd"` and `BINPKG_FORMAT="gpkg"`. [CODE S-uhuj7vad: cnf/make.globals#DISTDIR]
- The default `FEATURES` in the same file includes `sandbox`, `userpriv`, `usersandbox`, `network-sandbox`, `pid-sandbox`, `ipc-sandbox`, `parallel-fetch`, `news`, `preserve-libs`, `strict` and `binpkg-multi-instance`, and does not include `getbinpkg`, `buildpkg` or `binpkg-request-signature`. [CODE S-uhuj7vad: cnf/make.globals#FEATURES]
- `MAKEOPTS` is passed to `make` and defaults to `-j$(nproc) -l$(nproc)` when unset; the wiki recommends the smaller of the thread count or RAM divided by 2 GB for the job count. [DOC S-c5iscbp4]
- `CFLAGS` and `CXXFLAGS` apply to all packages (some filter flags that break them); with profile version 23.0 the wiki recommends not listing `CHOST`, since the profile already sets it. [DOC S-c5iscbp4]
- Options can be made default for every `emerge` through `EMERGE_DEFAULT_OPTS`, and a command-line option such as `--ask=n` overrides them. [DOC S-5hbh6sac]
- `PORTAGE_TMPDIR` defaults to `/var/tmp` (build in `/var/tmp/portage`); if it is mounted `noexec`, `emerge` fails with "Can not execute files in /var/tmp/portage" and the variable must point elsewhere. [DOC S-c5iscbp4]
- `ACCEPT_LICENSE` controls which licenses may be installed; the Handbook's default is `-* @FREE`, a per-package exception goes in `/etc/portage/package.license`, and `* -@EULA` accepts everything except End User License Agreements. [DOC S-cvsv6e4z]
- `CPU_FLAGS_X86` (and `_ARM`, `_PPC`) tell Portage which CPU features may be used; `cpuid2cpuflags` prints the value, which the wiki writes as `*/* CPU_FLAGS_X86: ...` in `/etc/portage/package.use/00cpu-flags`. [DOC S-c5iscbp4]
- `/etc/portage` is the primary configuration directory of Portage; its entries include `bashrc`, `binrepos.conf`, `categories`, `color.map`, `env`, `license_groups`, `make.conf`, `make.profile`, `mirrors`, `modules`, `package.accept_keywords`, `package.env`, `package.license`, `package.mask`, `package.properties`, `package.unmask`, `package.use`, `patches`, `postsync.d`, `profile/`, `repo.postsync.d`, `repos.conf`, `savedconfig` and `sets`. [DOC S-hfgxhfhm]
- Some of these names are optional or conventional, and the portage(5) manual page is the complete list. [DOC S-hfgxhfhm]
- The portage(5) page at the pinned commit says site-specific overrides of `make.profile/` go in `/etc/portage/profile/`, user-defined sets in `/etc/portage/sets/` and user patches in `/etc/portage/patches/`. [DOC S-5dnrfnng]
- Portage's shipped defaults for `binrepos.conf`, `make.globals`, `repos.conf` and `sets` are in `/usr/share/portage/config/`, and the files in `/etc/portage` override them. [DOC S-5dnrfnng]
- The installed-package database is `/var/db/pkg/`, the world file and config hashes are under `/var/lib/portage/`, and `/var/cache/edb/` can be deleted safely though regenerating it is slow. [DOC S-5dnrfnng]
- To find where a flag was set, `grep --recursive "<flag>" /etc/portage/` lists the file that holds it, including files such as `zz-automask`. [DOC S-jcuv5ggt]
- `package.use`, `package.accept_keywords`, `repos.conf` and `binrepos.conf` can each be a directory and `make.conf` can be one too, so an automation tool can own a named file in each instead of editing a shared one. [DER S-jcuv5ggt, S-cl6ijk7g, S-3v7thb2n, S-5rih6fam, S-c5iscbp4: each page states the directory form]
- A read-only plan for a change is `emerge --pretend --verbose --update --deep --newuse @world` (needs no root); the same line without `--pretend` applies it and should be run only after a repository sync. [DER S-5hbh6sac, S-cvsv6e4z: option semantics of pretend and the Handbook's update command]

## Reference
| need | command or file | source |
|---|---|---|
| plan without acting | `emerge --pretend ...` | S-5hbh6sac |
| update the system | `emerge --update --deep --newuse @world` | S-cvsv6e4z |
| install a dependency without the world file | `emerge --oneshot <pkg>` | S-5hbh6sac |
| remove | `emerge --deselect <pkg>`, then `emerge --ask --depclean` | S-cvsv6e4z |
| global config | `/etc/portage/make.conf` | S-c5iscbp4 |
| shipped defaults | `/usr/share/portage/config/make.globals` | S-5dnrfnng, S-uhuj7vad |
| all entries | `/etc/portage/` and `man 5 portage` | S-hfgxhfhm |

Related: `security/gentoo-use-flags-profiles-keywords.md`, `security/gentoo-ebuild-repositories-overlays.md`, `security/gentoo-binary-packages-binhost.md`, `security/linux-patching-and-pins.md`.

## Examples
- SNIPPET: a small `make.conf` kept to what a host needs; context: Gentoo amd64 with profile 23.0, `CHOST` left to the profile; checked: no [DER S-c5iscbp4, S-cvsv6e4z: variables and values from the make.conf and Handbook pages]
```
# /etc/portage/make.conf
COMMON_FLAGS="-march=native -O2 -pipe"
CFLAGS="${COMMON_FLAGS}"
CXXFLAGS="${COMMON_FLAGS}"
MAKEOPTS="-j4 -l4"
ACCEPT_LICENSE="-* @FREE"
EMERGE_DEFAULT_OPTS="--verbose"
```
