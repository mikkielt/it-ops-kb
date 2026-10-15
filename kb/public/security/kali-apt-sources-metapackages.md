---
topic: security/kali-apt-sources-metapackages
priority: P3
applies_to: "Kali Linux package sources (/etc/apt/sources.list.d/kali.sources, suites, components, mirrors, offline media) and the kali-meta metapackages that decide which tools an image installs"
retrieved_utc: 2026-10-15
sources: [S-o6curntz, S-2wfzjaxj, S-b6k54ngi, S-yehas5kt]
status: partial
---

# Kali package sources and metapackages

## Summary
A Kali host takes everything from one APT repository, `http://http.kali.org/kali/`, through one suite (a branch) at a time. Since Kali 2026.2 a fresh install keeps that in the deb822 file `/etc/apt/sources.list.d/kali.sources`; older installs keep one line in `/etc/apt/sources.list`. What a host contains is decided by metapackages built from the `kali-meta` source: `kali-linux-core` ⊂ `kali-linux-headless` ⊂ `kali-linux-default` ⊂ `kali-linux-large` ⊂ `kali-linux-everything`, plus per-area `kali-tools-*` sets. Branch semantics are in `security/kali-releases-rolling-model.md`. Read from kali.org docs and the `kali-meta` source at commit `e86f126b` on 2026-10-15.

## Facts
- On a clean install `/etc/apt/sources.list.d/kali.sources` holds `Types: deb`, `URIs: http://http.kali.org/kali/`, `Suites: kali-rolling`, `Components: main contrib non-free non-free-firmware` and `Signed-By: /usr/share/keyrings/kali-archive-keyring.gpg`. [DOC S-o6curntz]
- Before Kali 2026.2 that file did not exist and the same data was one line in `/etc/apt/sources.list`; `apt modernize-sources` converts the legacy file to the `.sources` format and keeps the old one as a `.list.bak`. [DOC S-o6curntz]
- `http.kali.org` is a load balancer that sends the client to the best mirror; the `Components` default takes everything, and `Types` can add `deb-src` to download package sources. [DOC S-o6curntz]
- The branch is the `Suites:` value: the docs switch it with `sed -i 's/^Suites: .*/Suites: kali-rolling/'` (or `kali-last-snapshot`), and the change takes effect only after `apt update`. [DOC S-o6curntz]
- `kali-experimental` and `kali-bleeding-edge` are enabled by listing them after `kali-rolling` in `Suites:` (or with `kali-tweaks`, Network Repositories); the docs discourage them next to `kali-last-snapshot`. [DOC S-o6curntz]
- Since Kali 2020.3 the network repositories are enabled after setup even if there was no network during installation; an offline install keeps the install medium (`deb cdrom:`) as the only source and gets no updates until that is changed. [DOC S-o6curntz]
- Extra software goes in its own file under `/etc/apt/sources.list.d/`, never in `kali.sources`; adding Kali's repository to another OS, or another OS's repository to Kali, is called the most common reason Kali systems break. [DOC S-o6curntz]
- The page states that an output different from the default may mean a switched branch or a hardcoded mirror, and that then new packages or updates may not install. [DOC S-o6curntz]
- A metapackage is a package that is only a list of dependencies; the docs install one with `apt install -y kali-linux-default` after `apt update` and `apt full-upgrade -y`, or through the Metapackages tab of `kali-tweaks`. [DOC S-2wfzjaxj]
- The docs' system sets are `kali-linux-core` (always included), `kali-linux-headless` (no GUI), `kali-linux-default` (the tools of default desktop images), `kali-linux-arm`, plus `kali-linux-large` ("our previous default tools") and `kali-linux-everything` ("every metapackage and tool"). [DOC S-2wfzjaxj]
- The page lists per-area tool sets such as `kali-tools-web`, `kali-tools-passwords`, `kali-tools-wireless`, `kali-tools-forensics`, `kali-tools-802-11`, `kali-tools-gpu` and `kali-linux-labs`, and desktop sets `kali-desktop-xfce`, `-gnome`, `-kde`, `-i3`, `-mate`, `-lxde`, `-e17` and `-core`. [DOC S-2wfzjaxj]
- In the `kali-meta` source `kali-system-core` depends on `kali-defaults`, `sudo`, `openssh-server`, `zsh`, `tmux`, `curl` and `wget`, and recommends `kali-tweaks` and `git`; `kali-linux-core` adds `netcat-traditional` and `tcpdump` to it. [CODE S-b6k54ngi: debian/control#kali-system-core, kali-linux-core]
- `kali-linux-headless` depends on `kali-linux-core` and `kali-system-cli` plus the command-line tools, and `kali-linux-default` depends on `kali-system-gui`, `kali-linux-headless` and `kali-tools-top10` plus a short list of GUI tools (such as `autopsy`, `zenmap`, `faraday`, `hydra-gtk`). [CODE S-b6k54ngi: debian/control#kali-linux-headless, kali-linux-default]
- `kali-linux-large` depends on `kali-linux-core` and `kali-linux-default`; `kali-linux-everything` depends on core, default, headless, large, `kali-linux-wsl`, `kali-tools-top10`, the menu sets and the tool sets, plus `kali-linux-arm` on `arm64` and `armhf`. [CODE S-b6k54ngi: debian/control#kali-linux-large, kali-linux-everything]
- The `kali-meta` source has menu sets the docs page does not list: `kali-tools-identify`, `-protect`, `-detect`, `-respond` and `-recover`, all pulled in by `kali-linux-everything`. [CODE S-b6k54ngi: debian/control#kali-linux-everything]
- `kali-linux-wsl` depends on `kali-system-cli` and `kali-linux-core` with a few network utilities, and `kali-linux-firmware-graphics` (AMD, Intel and NVIDIA firmware) is described as installed on bare metal but not in virtualised environments. [CODE S-b6k54ngi: debian/control#kali-linux-wsl, kali-linux-firmware-graphics]
- `kali-linux-nethunter` is marked as a transitional package depending on `kali-nethunter-full`, which can safely be removed; the docs page still lists it as the NetHunter tool set. [CODE S-b6k54ngi: debian/control#kali-linux-nethunter]
- `kali-linux-labs` pulls intentionally vulnerable applications (`dvwa`, `juice-shop` on `amd64`), so installing it adds targets, not tools. [CODE S-b6k54ngi: debian/control#kali-linux-labs]
- The `kali-meta` source package is maintained by "Kali Developers" in a public GitLab repository, and its `debian/control` header lists the tool, platform, menu and miscellaneous metapackage families. [CODE S-b6k54ngi: debian/control#Source]
- For an unattended build, name the metapackage explicitly instead of relying on an image: a Docker image carries no default metapackage (`apt -y install kali-linux-headless` is the docs' advice), and `kali-linux-default` includes GUI tools that a server-class host does not need. [DER S-2wfzjaxj, S-b6k54ngi, S-yehas5kt: headless vs default composition, Docker note]
- The kb read no package list of any metapackage in full (several hundred names) and no per-tool version. [UNK: logged in `_gaps.md`]

## Reference
| metapackage | depends on (at `e86f126b`) | typical use |
|---|---|---|
| `kali-system-core` | `kali-defaults`, `sudo`, `openssh-server`, `zsh`, `tmux` … | every Kali system |
| `kali-linux-core` | `kali-system-core`, `netcat-traditional`, `tcpdump` | minimal offensive base |
| `kali-linux-headless` | core, `kali-system-cli`, CLI tools | VMs and base images without GUI |
| `kali-linux-default` | `kali-system-gui`, headless, `kali-tools-top10`, GUI tools | default desktop image |
| `kali-linux-large` | core, default, more tools | optional installer set |
| `kali-linux-everything` | core, default, headless, large, `kali-linux-wsl`, (arm), menu and tool sets | everything |

Related: `security/kali-releases-rolling-model.md`, `security/kali-images-verification-builds.md`, `security/kali-default-account-vm-containers.md`, `security/linux-patching-and-pins.md`.

## Examples
- SNIPPET: the deb822 file of a default Kali install and the commands that add one tool set; context: Kali 2026.2 or later, as a sudo user; checked: no [DER S-o6curntz, S-2wfzjaxj: the docs' file content and install commands]
```
# /etc/apt/sources.list.d/kali.sources
Types: deb
URIs: http://http.kali.org/kali/
Suites: kali-rolling
Components: main contrib non-free non-free-firmware
Signed-By: /usr/share/keyrings/kali-archive-keyring.gpg
```
```
sudo apt update
sudo apt install -y kali-tools-web
```
