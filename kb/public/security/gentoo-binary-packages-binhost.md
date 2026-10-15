---
topic: security/gentoo-binary-packages-binhost
priority: P3
applies_to: "Gentoo Linux binary packages with Portage: GPKG and XPAK formats, using the official binhost or your own through binrepos.conf, signature verification, building and maintaining a package directory"
retrieved_utc: 2026-10-15
sources: [S-vr4evhob, S-rzs2uo4g, S-ch2quvvc, S-5rih6fam, S-5lblcwaf, S-5dnrfnng, S-uhuj7vad]
status: partial
---

# Gentoo binary packages and binhosts

## Summary
Portage can build binary packages next to its source builds, install them, and fetch them from a binary package host. Gentoo runs an official binhost (since December 2023, amd64 and arm64 refreshed daily) and recent stage files point at it. A client uses a binary package only when its USE flags and the other build parameters match, and builds from source otherwise unless told to use binaries only. Clients are configured in `/etc/portage/binrepos.conf` (the older `PORTAGE_BINHOST` variable is deprecated); remote packages are verified against OpenPGP signatures by default, a change the 2026-05-03 news item announces. Which Portage release made verification the default is not stated in the pages read.

## Facts
- Portage supports binary packages in addition to source builds: it can create them, install them, update installed packages from them and fetch them from binary package hosts. [DOC S-vr4evhob]
- Two formats exist, legacy XPAK and GPKG; GPKG is supported from Portage 3.0.31, is not backward compatible with XPAK, and current Portage versions use it by default. [DOC S-vr4evhob]
- `BINPKG_FORMAT` takes `xpak` or `gpkg`; XPAK packages end in `.tbz2` (or `.xpak` with `binpkg-multi-instance`) and GPKG packages in `.gpkg.tar`. [DOC S-5lblcwaf]
- `cnf/make.globals` at the pinned commit sets `BINPKG_FORMAT="gpkg"`, `BINPKG_COMPRESS="zstd"` and `PKGDIR="/var/cache/binpkgs"`, and its default `FEATURES` has `binpkg-multi-instance`, `pkgdir-index-trusted` and `binpkg-logs`. [CODE S-uhuj7vad: cnf/make.globals#BINPKG_FORMAT]
- A GPKG file holds an empty `gpkg-1` marker, a `metadata.tar` (package metadata, ebuild, environment), an `image.tar` of the files to install, a `Manifest` of checksums and optional `.sig` OpenPGP signatures, and can be unpacked with `tar`. [DOC S-vr4evhob]
- Supported compressions are bzip2, gzip, lz4, lzip, lzop, xz and zstd, chosen with `BINPKG_COMPRESS` (default zstd). [DOC S-vr4evhob]
- For packages built on one system to work on another, builder and client need the same architecture and `CHOST`, compatible `CFLAGS` and `CXXFLAGS`, and processor-feature USE flags that all clients support; the wiki says Portage cannot validate this and it is the administrator's responsibility. [DOC S-vr4evhob]
- The client's compiler must be the same version or newer than the builder's GCC or clang, or builds can fail with undefined-reference errors; a oneshot update of the system compiler is the suggested fix. [DOC S-vr4evhob]
- Unless `--usepkgonly` or `--getbinpkgonly` is given, a package built with a different USE flag combination is either ignored (and built from source) or makes the emerge fail, depending on the options passed. [DOC S-vr4evhob]
- By default Portage accepts a binary package only if its USE flags match the request exactly and compiles from source otherwise, logging that binaries were ignored for non-matching USE. [DOC S-rzs2uo4g]
- The `emerge` options are `--usepkg` (`-k`, the local `packages` directory, falls back to source), `--usepkgonly` (`-K`, fails if absent), `--getbinpkg` (`-g`, a remote host, falls back to source) and `--getbinpkgonly` (`-G`, fails if not downloadable). [DOC S-vr4evhob]
- To use binaries by default, either `--getbinpkg` goes into `EMERGE_DEFAULT_OPTS` or `FEATURES="getbinpkg"` is set in `make.conf`, which forces emerge to try the binary package host. [DOC S-vr4evhob]
- The `getbinpkg` feature uses the remote hosts configured in `binrepos.conf` (or deprecated `PORTAGE_BINHOST`) and cannot be set through `package.env`. [DOC S-5lblcwaf]
- `--usepkg-exclude "<atoms>"` keeps matching packages on source builds; the wiki warns that a package with user patches in `/etc/portage/patches` is still fetched as a binary (bug 917047) unless excluded this way. [DOC S-vr4evhob]
- The binhost quickstart says there is no way to prefer the binary for one package; `--binpkg-respect-use=n` makes Portage install a binary whatever its USE flags and is described as dangerous. [DOC S-rzs2uo4g]
- Since December 2023 Gentoo's Release Engineering team offers an official binary package host; it provides cryptographically signed, compiled packages and can greatly decrease the time to install, mostly on older, slower or low-power systems. [DOC S-5rih6fam]
- The official binhost updates amd64 and arm64 daily with commonly installed desktop packages and other architectures about weekly with core packages, and an `x86-64-v3` directory exists for CPUs that support that level. [DOC S-rzs2uo4g]
- Packages from the official binhost use a minimum instruction set and conservative compiler settings, for amd64 `-march=x86-64 -mtune=generic`. [DOC S-vr4evhob]
- It can serve a package only when the requested USE combination equals the default the binary was built with; otherwise Portage compiles locally. [DOC S-rzs2uo4g]
- Builds start about 5am EST and take a couple of hours, so a binary available yesterday may be missing until the run ends; some packages are built "by lottery" each day. [DOC S-rzs2uo4g]
- Hosts are configured in `/etc/portage/binrepos.conf`: a section `[name]` with `sync-uri` (the repository URI used by `emerge --getbinpkg`), `priority` (higher is preferred), `verify-signature` (from Portage 3.0.74) and `location` (default `/var/cache/binhost/<name>` from 3.0.77). [DOC S-5dnrfnng]
- The Handbook's official binhost `sync-uri` has the form `https://distfiles.gentoo.org/releases/<arch>/binpackages/<variant>`, for example `.../amd64/binpackages/23.0/x86-64/`, and its architecture and profile parts must match the system. [DOC S-5rih6fam]
- For hardened, musl or LLVM profiles, x32 or another architecture the example paths are not correct; matching directories exist but hold only the package set found in the stage 3. [DOC S-rzs2uo4g]
- More recent installations use stage 3 files that come with the Gentoo binhost preconfigured. [DOC S-rzs2uo4g]
- Many Gentoo stages already ship an `/etc/portage/binrepos.conf` pointing to the binary packages generated during the stage builds. [DOC S-vr4evhob]
- With several hosts serving one package version only the first is considered, which can matter when their USE settings differ. [DOC S-vr4evhob]
- `verify-signature` controls whether PGP signatures of binary packages from a repository are verified and defaults to true in `binrepos.conf`. [DOC S-5dnrfnng]
- `FEATURES=binpkg-request-signature` (reject any package without a valid signature) and `binpkg-ignore-signature` (disable the check, dangerous with remote or third-party packages) take precedence over `binrepos.conf`. [DOC S-5lblcwaf]
- OpenPGP signing and verification exist only for GPKG; `getuto` sets up a local trust anchor in `/etc/portage/gnupg` with the Gentoo release keys and Portage runs it automatically with `--getbinpkg`; added keys must be signed and trusted fully, since marginal trust does not work. [DOC S-vr4evhob]
- The 2026-05-03 news item says binary package signatures are now verified by default, and that fetched packages are cached apart from locally built ones in `/var/cache/binhost/NAME` (name from `binrepos.conf`, path set with `location`). [DOC S-ch2quvvc]
- Per that news item, official-binhost users need no action and `FEATURES="binpkg-request-signature"` is no longer needed for them; people who host their own binpkgs must sign them or set `verify-signature = false` for that host, or fetched packages fail verification. [DOC S-ch2quvvc]
- The same item names `/root/.gnupg` as the default signing key location and `/etc/portage/gnupg` as the verification keyring, `FEATURES="binpkg-signing"` as the switch, `gpkg-sign` for packages already built, and `eclean-pkg` to clean the old mixed location. [DOC S-ch2quvvc]
- Signing uses `BINPKG_GPG_SIGNING_GPG_HOME` and `BINPKG_GPG_SIGNING_KEY`; `gpg-keepalive` helps long sessions, and gpg-agent's default cache expiry of two hours can still fail a longer emerge unless `max-cache-ttl` is raised. [DOC S-vr4evhob]
- Packages are created with `quickpkg` (from installed files), `--buildpkg` (`-b`), `--buildpkgonly` (`-B`, needs build dependencies installed) or `FEATURES=buildpkg` (all) and `buildsyspkg` (system set), into `PKGDIR`, default `/var/cache/binpkgs`. [DOC S-vr4evhob]
- `quickpkg` by default leaves out files protected by `CONFIG_PROTECT`, because administrators edit configuration after install and it could leak confidential data; `--include-config` or `--include-unmodified-config` adds them. [DOC S-vr4evhob]
- The `Packages` file in `PKGDIR` is a cache of the metadata of all binary packages; after manual changes `emaint binhost --fix` recreates it, and since Portage 3.0.52 `pkgdir-index-trusted` makes Portage rely on it. [DOC S-vr4evhob]
- `eclean packages` removes binaries without a matching ebuild; on the build host `--changed-use` should not be used, since packages with added or removed flags would be skipped, so `--newuse` is used to keep binaries in step with ebuilds. [DOC S-vr4evhob]
- Portage can fetch from FTP, FTPS, HTTP, HTTPS and SSH/SFTP, so a host is any file server that exposes `PKGDIR` or a snapshot of it. [DOC S-vr4evhob]
- A build host for several machines should build with the common subset of `CFLAGS` and `CPU_FLAGS_*`, sign every package, and publish a `PKGDIR` that clients verify with `verify-signature = true` in a named `binrepos.conf` file. [DER S-vr4evhob, S-5dnrfnng, S-ch2quvvc: compatibility rules, per-repository verification and signing steps]
- The wiki's guidance and the news item differ in wording, not in effect: the Handbook and quickstart still show `FEATURES="${FEATURES} binpkg-request-signature"`, which the news item says is no longer needed for the official binhost and which is harmless. [DER S-5rih6fam, S-rzs2uo4g, S-ch2quvvc: both settings require signatures]
- The Portage release in which signature verification became the default for remote hosts is not stated by the news item (it says "newer versions of Portage") or the wiki articles read. [UNK: logged in `_gaps.md`]

## Reference
| need | setting | source |
|---|---|---|
| use binaries when present | `FEATURES="getbinpkg"` or `--getbinpkg` | S-rzs2uo4g |
| binaries only | `--usepkgonly --getbinpkg` | S-rzs2uo4g |
| host definition | `/etc/portage/binrepos.conf` | S-5dnrfnng |
| require signatures | `verify-signature = true`; `binpkg-request-signature` | S-5lblcwaf |
| build packages | `FEATURES="buildpkg"`, `quickpkg` | S-vr4evhob |
| sign packages | `FEATURES="binpkg-signing"`, `BINPKG_GPG_SIGNING_KEY` | S-vr4evhob |
| rebuild the index | `emaint binhost --fix` | S-vr4evhob |

Related: `security/gentoo-emerge-make-conf-etc-portage.md`, `security/gentoo-stage-files-init-systems.md`, `security/gentoo-use-flags-profiles-keywords.md`.

## Examples
- SNIPPET: a client configured for the official binhost with signature verification; context: Gentoo amd64, profile 23.0, generic x86-64 build; checked: no [DER S-rzs2uo4g, S-5dnrfnng: section keys and the sync-uri form]
```
# /etc/portage/binrepos.conf/gentoo.conf
[gentoo]
priority = 9999
sync-uri = https://distfiles.gentoo.org/releases/amd64/binpackages/23.0/x86-64/
verify-signature = true

# /etc/portage/make.conf
FEATURES="${FEATURES} getbinpkg"
```
