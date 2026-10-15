---
topic: security/gentoo-use-flags-profiles-keywords
priority: P3
applies_to: "Gentoo Linux Portage: what a USE flag, a profile and a keyword do, where each is set (make.conf, package.use, package.accept_keywords, the profile) and the order they are layered in"
retrieved_utc: 2026-10-15
sources: [S-dkzzajvo, S-w323r75a, S-jcuv5ggt, S-c5iscbp4, S-6egnea5f, S-rnjsi3xg, S-cl6ijk7g, S-cvsv6e4z, S-5rih6fam, S-5lblcwaf, S-uhuj7vad]
status: complete
---

# Gentoo USE flags, profiles and keywords

## Summary
Three Portage mechanisms decide what is built and which versions are visible. A USE flag switches an optional feature or dependency of one package on or off; it has three states (set, unset, default) and is layered from the environment, `package.use`, `make.conf`, the profile and the ebuild, in the order `USE_ORDER` names. A profile is the baseline chosen at install time: it sets default USE flags, `make.conf` defaults, the system set and the init system variant (systemd profiles carry a `systemd` qualifier). A keyword decides stable or testing visibility: `ACCEPT_KEYWORDS` is set by the profile and refined in `make.conf` or per package in `package.accept_keywords`. The wiki's `USE_ORDER` article lists a default without `features`, which the Portage source at the pinned commit includes (recorded in `_conflicts.md`). Emerge's update flow and the `/etc/portage` files are in `security/gentoo-emerge-make-conf-etc-portage.md`.

## Facts
- USE flags are keywords that embody support and dependency information for one concept; they configure Portage on how each package is built on installation or update, and which flags exist depends on each package. [DOC S-dkzzajvo]
- Flags can change compile-time options, which optional libraries or utilities are linked (so often the dependencies) and which files are installed, such as documentation; which options become flags is the package maintainer's decision. [DOC S-dkzzajvo]
- A USE flag has three states, set, unset or default: its presence in `USE` of `make.conf` or in `package.use` sets it, a leading minus unsets it, and a flag named in neither falls back to the default. [DOC S-dkzzajvo]
- Defaults are layered: the Gentoo ebuild repository ships a small default set, the selected profile refines it, and each package has its own available flags with default states; each layer overrides the previous. [DOC S-dkzzajvo]
- The wiki prefers setting flags per package in `package.use` over the system-wide `USE` variable, because defaults are usually sane and a global flag affects every package. [DOC S-dkzzajvo]
- Setting `USE` in the environment of one `emerge` call is lost on the next upgrade or re-emerge of the package, and the wiki warns against using it to install packages. [DOC S-dkzzajvo]
- `portageq envvar USE | xargs -n 1` lists the flags enabled now, and `emerge --nodeps --pretend <package>` shows the flags one package would be built with without calculating its dependencies. [DOC S-dkzzajvo]
- A flag shown in parentheses in the emerge output is forced, masked or removed, which can come from the profile or the architecture (for example `profiles/base/package.use.stable.mask`); the wiki says to unmask by adding the package with no flags to `package.accept_keywords` only if the mask was in error. [DOC S-dkzzajvo]
- A "global" and a "local" flag differ only in where their description is stored in the repository: global ones in a profile's `use.desc`, local ones in a package's `metadata.xml`; for the user the difference has little importance. [DOC S-dkzzajvo]
- `USE_ORDER` is a colon-delimited list of where flags are pulled from, and when a flag appears in several sources the first listed has the highest priority; the wiki's table names `env` (environment `USE` and `USE_EXPAND` variables), `pkg` (`package.use`), `conf` (`make.conf`), `defaults` (profile `make.defaults` and `package.use`), `pkginternal` (the ebuild), `repo` (the repository's `profiles/` top directory) and `env.d` (`/etc/env.d`). [DOC S-w323r75a]
- The wiki states the default as `env:pkg:conf:defaults:pkginternal:repo:env.d`. [DOC S-w323r75a]
- The `make.conf(5)` manual page at the pinned Portage commit gives the default as `env:pkg:conf:defaults:pkginternal:features:repo:env.d`, where `features` stands for flags implied by `FEATURES` (currently `USE=test` for `FEATURES=test`), and warns developers-only against changing it. [DOC S-5lblcwaf]
- `cnf/make.globals` at the same commit sets `USE_ORDER="env:pkg:conf:defaults:pkginternal:features:repo:env.d"`, so the implementation has the `features` layer the wiki article omits. [CODE S-uhuj7vad: cnf/make.globals#USE_ORDER]
- `/etc/portage/package.use` may be one file or a directory of files; with the default order it overrides package settings from every location except the `USE` environment variable. [DOC S-jcuv5ggt]
- A `package.use` line is one dependency atom followed by space-delimited flags, `#` starts a comment, and a version in the atom needs a comparison operator; `*/*` applies a flag to all packages and a `USE_EXPAND` value is written `NAME: value`. [DOC S-jcuv5ggt]
- `emerge` has `--autounmask` on by default and can write `package.use` changes to satisfy dependencies; when `package.use` is a directory it appends to the lexicographically last file, which can put one package's change in another package's file. [DOC S-jcuv5ggt]
- The wiki now writes `USE_EXPAND` flags (`CPU_FLAGS_X86`, `L10N`, `VIDEO_CARDS`) in `package.use` as `*/* NAME: value` instead of `make.conf`, because setting them in `make.conf` can lead to ordering issues. [DOC S-c5iscbp4]
- After a flag or profile change the Handbook's update command carries `--changed-use` or `--newuse`, so Portage rebuilds packages whose flags changed (`emerge --update --deep --newuse @world`). [DOC S-cvsv6e4z]
- A profile is a core Portage feature that gives a minimal workable baseline for a system's use; it can determine package availability, default USE flags, default `make.conf` values, the system package set, toolchains and core libraries. [DOC S-6egnea5f]
- A profile also locks the system to a range of package versions, and the Handbook has the administrator choose it with `eselect profile list` and `eselect profile set <n>`. [DOC S-5rih6fam]
- Profiles are split by init system: systemd profiles include a `systemd` qualifier and OpenRC profiles have no init-system qualifier; the basic ones are `default/linux/<architecture>/23.0` and `default/linux/<architecture>/23.0/systemd`, and version 23.0 is the current one for most architectures. [DOC S-6egnea5f]
- Desktop profiles carry a `desktop` qualifier, with GNOME and Plasma variants; the wiki says that skipping a desktop profile on a graphical system leads to a heavy setup and maintenance burden. [DOC S-6egnea5f]
- Profile stability is stable, in-development (`dev`) or experimental (`exp`); general use should take a stable one; Gentoo's CI checks that stable profiles have a sound dependency graph, while a problem in a `dev` one raises only a warning. [DOC S-6egnea5f]
- Some profile switches are easy, some take extra steps, and changing to a profile with a different ABI (pure LLVM or musl) is not possible without a reinstall. [DOC S-6egnea5f]
- A new profile version is announced by a news item after a repository sync, and the wiki says to change profile versions only after reading and following that item; 23.0 came almost six years after 17.1. [DOC S-6egnea5f]
- The Handbook says to pick the initial profile of the same version as the stage file used, and to choose a profile with `systemd` in its name to use systemd. [DOC S-5rih6fam]
- Profiles are defined per ebuild repository; those of the main repository are maintained by Gentoo developers and users can define their own. [DOC S-6egnea5f]
- `ACCEPT_KEYWORDS` tells Portage which ebuilds' `KEYWORDS` it may accept, which selects the stable or testing branch; it is usually set by the profile and can be overridden system-wide in `make.conf`, per package in `package.accept_keywords`, or on the command line (not recommended, as it is not persistent). [DOC S-rnjsi3xg]
- The profile default is the architecture itself (`amd64`); adding `~amd64` accepts testing ebuilds, and the stable keyword should not be listed beside it because the variable is incremental. [DOC S-rnjsi3xg]
- The wiki warns that `ACCEPT_KEYWORDS="~amd64"` in `make.conf` applies to all packages and may cause conflicts in later updates and breakage when downgrading glibc. [DOC S-rnjsi3xg]
- Once a system has been switched to testing it cannot simply be downgraded back to stable; the `package.accept_keywords` article highly recommends reinstalling instead. [DOC S-cl6ijk7g]
- `package.accept_keywords` takes one atom per line followed by extra keywords, `#` comment lines with no inline comments, and an atom with no keywords means the unstable keyword of the host architecture. [DOC S-cl6ijk7g]
- Its special tokens are `*` (visible if stable on any architecture), `~*` (visible if testing on any architecture) and `**` (always visible, `KEYWORDS` ignored, useful for live ebuilds); a `-*` keyword in an ebuild means broken on every architecture not listed. [DOC S-cl6ijk7g, S-rnjsi3xg]
- Appending `-~amd64` to an atom keeps a package on the stable branch of a testing system, and a `=` atom with a version pins a testing version until stable catches up. [DOC S-cl6ijk7g]
- The wiki treats a `package.accept_keywords` of over about 100 entries as a sign that the system should run `~ARCH` globally, because Portage is then much more likely to run into conflicts. [DOC S-cl6ijk7g]
- `package.keywords` is the older location; when both exist both are used and `package.accept_keywords` overrides it, since profiles use a `package.keywords` that changes effective `KEYWORDS`. [DOC S-cl6ijk7g]
- When no ebuild can be installed Portage gives a mask reason: a `~arch` keyword (testing), `-arch` or `-*` (does not work there), a missing keyword (untested there), `package.mask` (deliberately marked do-not-use), the profile, or a license not accepted by `ACCEPT_LICENSE`. [DOC S-cvsv6e4z]
- A required USE change is reported as "The following USE changes are necessary to proceed"; the remedy is to set the flag globally in `make.conf` or for the package in `package.use`. [DOC S-cvsv6e4z]
- For an agent that owns host configuration, flags and keywords belong in its own named files under `/etc/portage/package.use/` and `/etc/portage/package.accept_keywords/`, not in `USE` of `make.conf` or in an environment variable. [DER S-dkzzajvo, S-jcuv5ggt, S-cl6ijk7g: per-package files are preferred and an environment `USE` is lost on re-emerge]
- The init system is therefore a profile property fixed at install time with the stage file; changing it later is a profile change with its own migration steps. [DER S-6egnea5f, S-5rih6fam: profile names carry the `systemd` qualifier and the Handbook ties the stage and profile choice together]

## Reference
| need | where | source |
|---|---|---|
| global flags | `USE="-kde ldap"` in `/etc/portage/make.conf` | S-c5iscbp4 |
| per-package flags | `/etc/portage/package.use` (file or directory) | S-jcuv5ggt |
| layer order | `USE_ORDER` | S-w323r75a, S-5lblcwaf |
| flags in effect | `portageq envvar USE`, `emerge --nodeps --pretend <pkg>` | S-dkzzajvo |
| profile list and set | `eselect profile list`, `eselect profile set <n>` | S-5rih6fam |
| per-package keyword | `/etc/portage/package.accept_keywords` | S-cl6ijk7g |
| global keyword | `ACCEPT_KEYWORDS` in `make.conf` | S-rnjsi3xg |

Related: `security/gentoo-emerge-make-conf-etc-portage.md`, `security/gentoo-ebuild-repositories-overlays.md`, `security/gentoo-stage-files-init-systems.md`, `security/gentoo-binary-packages-binhost.md`, `security/linux-patching-and-pins.md`.

## Examples
- SNIPPET: per-package USE flags and a keyword in drop-in files; context: Gentoo with Portage, `package.use` and `package.accept_keywords` as directories; checked: no [DER S-jcuv5ggt, S-cl6ijk7g: line formats from the two wiki pages]
```
# /etc/portage/package.use/50-local
# enable the offensive flag for sudo
app-admin/sudo offensive
# turn off mysql support in php
dev-lang/php -mysql

# /etc/portage/package.accept_keywords/50-local
# keep the kernel on the stable branch of a testing system
sys-kernel/gentoo-kernel -~amd64
# take one testing version until stable catches up
=net-analyzer/netcat-110.20180111-r2
```
