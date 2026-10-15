---
topic: security/kali-default-account-vm-containers
priority: P3
applies_to: "Kali Linux default account and sudo policy, default tool credentials, the network service policy, and Kali as a VM image, a WSL distribution, and a Docker or LXC/LXD container"
retrieved_utc: 2026-10-15
sources: [S-mvp5ewqd, S-kn4vg3wc, S-pggydvhj, S-phypzuod, S-a3rz5fyq, S-xvu7hlvs, S-exxf6zgf, S-yehas5kt, S-lovosk2r, S-drkvieff, S-b6k54ngi]
status: partial
---

# Kali's default account, services, VMs and containers

## Summary
Since Kali 2020.1 there is no root password: pre-built images (live, VM, ARM) ship a `kali` user with the password `kali` that has `sudo`, and the installer asks for a user. Network services are deliberately not started at boot. Kali also runs as a pre-built VM, a WSL distribution and Docker or LXC/LXD images; a container image is a bare `kali-rolling` rootfs with no tool set until a metapackage is installed. Branches are in `security/kali-releases-rolling-model.md`, metapackages in `security/kali-apt-sources-metapackages.md`, images in `security/kali-images-verification-builds.md`. Read from kali.org on 2026-10-15.

## Facts
- Kali has used a non-root user policy by default since 2020.1: the installer of amd64 images prompts for a standard user account. [DOC S-mvp5ewqd]
- On such a system root has no password set, and the account created during installation, which has administrative privileges, is the one to use through `sudo`. [DOC S-kn4vg3wc]
- The credentials of live boot and pre-created images (VMs, ARM) are user `kali`, password `kali`; the Vagrant image uses `vagrant`/`vagrant`, and Amazon EC2 uses user `kali` with an SSH key. [DOC S-mvp5ewqd]
- The docs list tools that ship their own hardcoded or generated defaults, among them BeEF (`beef`/`beef`, `/etc/beef-xss/config.yaml`), Metasploit's database (`postgres`/`postgres`), Bloodhound (`admin`/`admin`), MySQL (root, blank) and OpenVAS (`admin`, generated at setup). [DOC S-mvp5ewqd]
- Privileged commands run through `pkexec` (GUI and CLI) or `sudo` (CLI). [DOC S-pggydvhj]
- Installing `kali-grant-root` and running `dpkg-reconfigure kali-grant-root` makes `sudo` passwordless for a trusted group, which the docs call a security risk and say does not bring back root. [DOC S-kn4vg3wc]
- The user policy notes that tools behave differently without root: Nmap defaults to a SYN scan (`-sS`) for root and a connect scan (`-sT`) otherwise, and the page offers `kali-grant-root` to restore the older behaviour. [DOC S-pggydvhj]
- Kali enables no externally listening service by default and disallows network services from persisting across reboots: an install of a daemon such as `apt-cacher-ng` has `update-rc.d` print that it looks like a network service and disable it. [DOC S-phypzuod]
- A service is allowed to start at boot with `systemctl enable <service>`; the allow and block lists are the `__DATA__` section of `/usr/sbin/update-rc.d`, whose blocklist names `apache2`, `avahi-daemon`, `bluetooth`, `cups`, `dictd` and `ssh`. [DOC S-phypzuod]
- Since 2026.2 Kali packages that include a service are to use `<tool>-start` and `<tool>-stop` command names, which start or stop it, check it is not already running, show status, show default credentials and show how to reach it. [DOC S-a3rz5fyq]
- `kali-system-core` depends on `openssh-server`, so sshd is installed on every Kali system; combined with the policy that blocklists `ssh`, a fresh host does not listen on port 22 until the service is enabled. [DER S-b6k54ngi, S-phypzuod: the package dependency and the blocklist entry, read in documents only]
- The pre-made VirtualBox image is a `7z` archive of a `.vbox` machine (`kali-linux-2026.2-virtualbox-amd64.7z`), added with VirtualBox's "Add" and used with `kali`/`kali`. [DOC S-xvu7hlvs]
- Since 2026.2 pre-built VM images and installs detected as VMs have no graphics firmware, so the initrd is about 60 MB instead of about 200 MB and a QEMU boot is about three times faster; a VM with GPU passthrough may need it back, and bare metal is unchanged. [DOC S-a3rz5fyq]
- WSL: `wsl --install kali-linux` (or `--distribution kali-linux`) installs Kali Rolling; WSL 2 is the default and preferred (a real kernel in a Hyper-V VM), WSL 1 is a translation layer, and the first run asks for a new UNIX user. [DOC S-exxf6zgf]
- Since November 2024 WSL can import `.wsl` tar root filesystems, which Kali publishes on its `kali.download` mirror, and this needs the pre-release WSL (`wsl --update --pre-release`). [DOC S-exxf6zgf]
- Windows 10 needs build 18362.1049 (1903) for WSL 2 on x64 and build 19041 (2004) is recommended; a nested VM needs nested virtualization. [DOC S-exxf6zgf]
- Official Docker images are updated once a week on Docker Hub: `kalilinux/kali-rolling` (tracks `kali-rolling`), `kali-last-release` (from `kali-last-snapshot`), and the special-purpose `kali-bleeding-edge`, `kali-experimental` and `kali-dev`. [DOC S-yehas5kt]
- The Docker images carry no default tool metapackage: `apt update && apt -y install kali-linux-headless` is the docs' step. [DOC S-yehas5kt]
- A plain `docker run` of the image does not give systemd, so `systemctl` does not work in it; getting systemd to work needs a modified Dockerfile and `docker run` flags, which the page does not cover. [DOC S-lovosk2r]
- The container shell of `docker run --tty --interactive kalilinux/kali-rolling` opens a root prompt inside the container, with the container id as its host name; the page shows no `kali` login. [DOC S-lovosk2r]
- The Docker images are built by GitLab CI from the `kali-docker` project. [DOC S-yehas5kt]
- The team's preference is Docker for applications and LXC/LXD for whole systems, with LXC preferred inside Kali because it is supported natively and needs no snapd. [DOC S-drkvieff]
- LXC/LXD images are on the `images:` server (`lxc launch images:kali/current/amd64 my-kali`) for amd64 and arm64; the docs then install `kali-linux-default` and `kali-desktop-xfce` in it and create a non-root user with `adduser` and `usermod -aG sudo`. [DOC S-drkvieff]
- For automation: a container or WSL instance is a throwaway root environment that installs a named metapackage on demand, while a VM image carries the `kali` account with a known password, so a lab pipeline should change that password or the account at first boot and keep the host off shared networks until then. [DER S-mvp5ewqd, S-yehas5kt, S-xvu7hlvs: documented default password, bare container image]
- Whether the Podman page, the Vagrant, Proxmox and cloud images (AWS, Azure) and the NetHunter paths differ from the above was not read. [UNK: logged in `_gaps.md`]

## Reference
| platform | account at first use | tools installed | notes |
|---|---|---|---|
| installer image | user chosen in installer | `top10` + `default` | root has no password |
| live / pre-made VM / ARM | `kali` / `kali` | image's set | sudo, `kali-grant-root` optional |
| Vagrant | `vagrant` / `vagrant` | per box | Vagrant policy |
| Amazon EC2 | `kali` + SSH key | per image | no password |
| WSL | user created at first run | `kali-linux-wsl` base | WSL 2 preferred |
| Docker `kalilinux/kali-rolling` | root | none; add `kali-linux-headless` | weekly, no systemd |
| LXC/LXD `images:kali/current` | root | none; add metapackage | create user by hand |

Related: `security/kali-releases-rolling-model.md`, `security/kali-apt-sources-metapackages.md`, `security/kali-images-verification-builds.md`, `arch/incus-test-bed.md`.

## Examples
- SNIPPET: start a Kali container and add the headless tool set; context: host with Docker; checked: no [DER S-lovosk2r, S-yehas5kt: the docs' pull and run commands and the headless metapackage advice]
```
docker pull docker.io/kalilinux/kali-rolling
docker run --tty --interactive kalilinux/kali-rolling
# inside the container, as root:
apt update && apt -y install kali-linux-headless
```
