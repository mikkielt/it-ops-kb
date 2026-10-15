---
topic: security/gentoo-ebuild-repositories-overlays
priority: P3
applies_to: "Gentoo Linux ebuild repositories (the main ::gentoo tree and overlays): repos.conf, priority, synchronization with emaint, eselect repository and masking an overlay"
retrieved_utc: 2026-10-15
sources: [S-aguccvdb, S-3v7thb2n, S-46ys6oow, S-cvsv6e4z, S-5rih6fam, S-5dnrfnng]
status: complete
---

# Gentoo ebuild repositories and overlays

## Summary
An ebuild repository is a directory tree of ebuilds, eclasses, profiles and news items. The main one, `::gentoo`, is synchronized to `/var/db/repos/gentoo` and also carries the profiles; additional ones are the "overlays". Each is declared in `/etc/portage/repos.conf` with a location, a sync type and URI, and a priority (the main repository defaults to `-1000`, others to `0`). `emaint sync` updates them, `eselect repository` edits `repos.conf`, and a package present in several repositories is taken from the highest priority. The repository carries no trust beyond its maintainers, so the wiki suggests masking a large overlay as a whole and unmasking single packages.

## Facts
- An ebuild repository is a file structure that supplies Portage with packages, news items and profile targets: it holds ebuilds, eclasses and other descriptive metadata files. [DOC S-aguccvdb]
- The Gentoo ebuild repository is the primary and official one, kept on `gitweb.gentoo.org`, synchronized to `/var/db/repos/gentoo`; it holds the ebuilds with their metadata and dependencies, the official profiles, and the news items. [DOC S-aguccvdb]
- It is also called the Gentoo repository, `::gentoo`, `gentoo.git`, or historically the Portage tree or rsync tree. [DOC S-aguccvdb]
- Portage installs the latest available version of a package from any configured repository; when several provide it the order of priority decides, which is the origin of the name "overlay". [DOC S-aguccvdb]
- Repositories are usually under `/var/db/repos/`, but their locations are set in `/etc/portage/repos.conf`, and a repository can sit on any accessible filesystem, including NFS or SSHFS. [DOC S-aguccvdb]
- Synchronization copies files from a remote location; rsync is the default method, git is also popular, and the method and its parameters are specified in `repos.conf`. [DOC S-aguccvdb]
- `/etc/portage/repos.conf` is a directory of files that specify the location and settings of every configured repository, and Portage adds some missing values such as `priority`. [DOC S-3v7thb2n]
- Portage's shipped default `repos.conf` is in `/usr/share/portage/config/`, and the files in `/etc/portage/repos.conf` override it. [DOC S-5dnrfnng]
- `portageq repos_config /` prints every configured repository; the wiki's example shows `[gentoo]` with `location = /var/db/repos/gentoo`, `sync-type = rsync`, `sync-uri = rsync://rsync.gentoo.org/gentoo-portage`, `priority = -1000` and an OpenPGP key path for sync verification, beside a git-synced overlay. [DOC S-3v7thb2n]
- `emerge --info` and `portageq repos_config /` both list the active repositories. [DOC S-aguccvdb]
- A repository's priority can be set in `repos.conf`; the repository with the highest priority is used for a package, one without a priority has `0`, the Gentoo repository `-1000`, and several repositories with the same priority give an undetermined order. [DOC S-aguccvdb]
- A package from a given repository is selected with `category/atom::repository-name`, which also works with `--depclean`; the `::name` in the plan output shows where a package comes from. [DOC S-aguccvdb]
- If a newly added repository provides a newer version of an installed package, the next system update replaces that package with the overlay's version; the wiki points to masking the whole repository to avoid blanket upgrades. [DOC S-aguccvdb]
- Repository synchronization is done with `emaint sync`, configured in `repos.conf`: `emaint sync --auto` syncs the repositories with `auto-sync` true, `--repo <name>` one repository, and `--allrepos` every one with a sync type and URI. [DOC S-aguccvdb]
- `auto-sync` defaults to true, so a repository that should not be synced by `--auto` needs `auto-sync = no`; `emerge --sync` is only a compatibility command that calls `emaint sync --auto`. [DOC S-aguccvdb]
- `emerge-webrsync` fetches the daily snapshot of the Gentoo repository over HTTP or FTP and is recommended behind restrictive firewalls; the Handbook uses it for the first sync during installation. [DOC S-5rih6fam]
- The wiki asks that the Gentoo repository be synced no more than once a day, to avoid strain on the servers. [DOC S-aguccvdb]
- The Handbook adds that users who sync too often are soft-banned from further syncs for a time and repeat abusers hard-banned from the rsync mirrors. [DOC S-cvsv6e4z]
- Large repositories without a metadata cache make dependency resolution slow; `emerge --regen` after `emaint sync --allrepos` (or `egencache`) generates one, and rsync-synced `::gentoo` already includes it. [DOC S-aguccvdb]
- Only the Gentoo repository is written or reviewed by Gentoo developers; GURU has some developer oversight and other repositories can contain vulnerable, badly broken or malicious software. [DOC S-aguccvdb]
- GURU is an official, user-maintained repository complementary to `::gentoo`, and it avoids providing versions that would replace packages from the Gentoo repository. [DOC S-aguccvdb]
- To restrict a large or low-trust overlay, hard-mask all of it in `package.mask` (`*/*::repository-foobar`) and unmask chosen packages in `package.unmask` (`foo-category/bar::repository-foobar`). [DOC S-aguccvdb]
- `eselect repository` (package `app-eselect/eselect-repository`) adds, enables, disables, removes and creates repositories and lists those registered on `repos.gentoo.org`; it writes to `/etc/portage/repos.conf` and supersedes layman. [DOC S-46ys6oow]
- Its `repos.conf` (or `REPOS_CONF` from `/etc/eselect/repository.conf`) must exist first, and the Handbook prefers it as a directory, so `mkdir -p /etc/portage/repos.conf` comes first. [DOC S-46ys6oow]
- `eselect repository enable <name>` takes a name from `repos.gentoo.org`, and `eselect repository add <name> <sync-type> <sync-uri>` takes any location; the sync types are `git`, `rsync`, `cvs`, `mercurial`, `svn`, `websync` and `zipfile`. [DOC S-46ys6oow]
- A repository configured by `eselect repository` is synced afterwards with `emaint sync -r <name>`; `disable` keeps the files and `remove` deletes them. [DOC S-46ys6oow]
- The wiki's priority example edits the `eselect-repo.conf` file that `eselect repository` created, setting `priority = 100` for the `[guru]` section. [DOC S-3v7thb2n]
- An overlay's trust and priority are decisions of the host's owner, so an agent that adds one should set `priority` explicitly, use `auto-sync` deliberately and mask all but the packages it needs. [DER S-aguccvdb, S-3v7thb2n: undetermined order at equal priority, replacement on update and the mask-all pattern]

## Reference
| need | command or file | source |
|---|---|---|
| repository settings | `/etc/portage/repos.conf/*.conf` | S-3v7thb2n |
| list configured | `portageq repos_config /` | S-3v7thb2n |
| sync all `auto-sync` | `emaint sync --auto` | S-aguccvdb |
| sync one | `emaint sync --repo <name>` | S-aguccvdb |
| add an overlay | `eselect repository add <name> <type> <uri>` | S-46ys6oow |
| restrict an overlay | `*/*::<name>` in `package.mask` | S-aguccvdb |

Related: `security/gentoo-emerge-make-conf-etc-portage.md`, `security/gentoo-use-flags-profiles-keywords.md`, `security/gentoo-binary-packages-binhost.md`.

## Examples
- SNIPPET: an overlay declared by hand with a priority and masked except for one package; context: Gentoo with Portage, git available, overlay name `example-overlay`, URI is a placeholder; checked: no [DER S-3v7thb2n, S-aguccvdb: section keys from the repos.conf example, mask pattern from the repository page]
```
# /etc/portage/repos.conf/example-overlay.conf
[example-overlay]
location = /var/db/repos/example-overlay
sync-type = git
sync-uri = https://git.example.com/overlay.git
priority = 50
auto-sync = yes

# /etc/portage/package.mask/example-overlay
*/*::example-overlay

# /etc/portage/package.unmask/example-overlay
app-misc/example-tool::example-overlay
```
