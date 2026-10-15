---
topic: security/gentoo-in-wsl
priority: P3
applies_to: "Gentoo Linux run under Windows Subsystem for Linux (WSL 2): importing a stage file or WSL tarball, .wslconfig and /etc/wsl.conf, init systems, drives and graphical programs"
retrieved_utc: 2026-10-15
sources: [S-lxqjpj53, S-qfnocjvf]
status: complete
---

# Gentoo in WSL on a Windows host

## Summary
Gentoo can run under Windows through WSL, which runs a real Linux kernel on a hypervisor, and it is installed from the Windows side with `wsl.exe`: Gentoo is not an official WSL distribution, so a stage file or a Gentoo WSL tarball is imported by hand. Windows settings for all WSL 2 distributions live in `.wslconfig` in the Windows user home, and per-distribution ones in `/etc/wsl.conf` inside Gentoo, where OpenRC or systemd is started from the `[boot]` section. The Handbook's installation steps apply with the `/mnt/gentoo` prefix dropped. The stage file itself is described in `security/gentoo-stage-files-init-systems.md`.

## Facts
- The wiki documents getting Gentoo running on WSL, which it describes as effectively running Gentoo under Windows. [DOC S-lxqjpj53]
- WSL uses a real Linux kernel on a hypervisor, so Linux is run within Windows, and the page assumes WSL version 2. [DOC S-lxqjpj53]
- WSL must be enabled in Windows first, and `wsl --install --no-distribution` leaves out the default Ubuntu distribution. [DOC S-lxqjpj53]
- The page points to Microsoft's documentation for Windows 10 build 19041 or above and Windows 11. [DOC S-lxqjpj53]
- `.wslconfig`, in the Windows user home directory, configures settings globally for all WSL 2 distributions, such as RAM, swap and processor count. [DOC S-lxqjpj53]
- A change to `.wslconfig` needs `wsl --shutdown` and a restart of the distributions on the Windows host. [DOC S-lxqjpj53]
- Gentoo is not among the official WSL distributions listed by `wsl --list --online`, so it needs a manual import and not the Microsoft Store install. [DOC S-lxqjpj53]
- WSL supports x64 and Arm CPUs, so the stage file taken from the downloads page must match the Windows machine's CPU. [DOC S-lxqjpj53]
- The import runs `wsl --import <Distro> <InstallLocation> <FileName>` from PowerShell or Terminal on Windows, with `--version 2` for WSL 2. [DOC S-lxqjpj53]
- The file passed to `wsl --import` should have a `.tar` extension, so the `.xz` stage archive is unpacked first, on Windows with a tool that reads `.xz`. [DOC S-lxqjpj53]
- With WSL 2.4.10 or later, a Gentoo `.wsl` tarball from `distfiles.gentoo.org/releases/` installs with `wsl --install --from-file` on Windows. [DOC S-lxqjpj53]
- Older WSL versions may use the stage 4 WSL tarball but must run the out-of-box script by hand or create users manually; a plain stage 3 is discouraged. [DOC S-lxqjpj53]
- On first start of a modern WSL import the `oobe` script configures a non-root user and sets the root password, so Windows users need no manual step. [DOC S-lxqjpj53]
- A Gentoo WSL image is, like a stage 3, a blank slate for customisation, and the Handbook is followed with the `/mnt/gentoo` prefix dropped from paths because there is no chroot. [DOC S-lxqjpj53]
- Because WSL runs a container, some Handbook features such as networking need no configuration on the Windows host, and configuring them can break them. [DOC S-lxqjpj53]
- The kernel can be customised on WSL, but this is not required and should only be done for a feature that is not enabled. [DOC S-lxqjpj53]
- Gentoo starts as `root` by default under WSL, which the wiki calls neither secure nor preferable, and a non-root default user is set in `/etc/wsl.conf`. [DOC S-lxqjpj53]
- `/etc/wsl.conf` is provided by `sys-apps/gentoo-wsl-config`, is included in stage 4 WSL tarballs and uses `ini` syntax. [DOC S-lxqjpj53]
- Its `[automount]` section mounts Windows fixed drives such as `C:` with DrvFs under `/mnt/` when the distribution starts. [DOC S-lxqjpj53]
- Its `[interop]` section lets Gentoo launch Windows programs and add the Windows `PATH`; setting it to false blocks Windows processes. [DOC S-lxqjpj53]
- Its `[network]` section defaults the hostname to the Windows hostname and can stop WSL generating `/etc/hosts` and `/etc/resolv.conf`. [DOC S-lxqjpj53]
- OpenRC runs on WSL start with `command = "/sbin/openrc default"` in the `[boot]` section of `/etc/wsl.conf`. [DOC S-lxqjpj53]
- systemd starts with `systemd=true` in `[boot]`, and that is not needed with a stage 4 WSL image. [DOC S-lxqjpj53]
- If systemd fails at boot because of its first boot detection, `kernelCommandLine = systemd.firstboot=0` in the Windows `.wslconfig` is the wiki's workaround. [DOC S-lxqjpj53]
- Users need to wait for WSL distributions to shut down completely, about eight seconds, before configuration changes appear on Windows. [DOC S-lxqjpj53]
- `wsl --terminate Gentoo` stops one distribution and `wsl --shutdown` terminates all WSL processes on the Windows host. [DOC S-lxqjpj53]
- Performance suffers when working in Windows directories such as `/mnt/c/`, so the wiki recommends the WSL filesystem, for example the home directory. [DOC S-lxqjpj53]
- A USB drive mounted on the Windows host is given to WSL with `usbip`, which uses the IP protocol. [DOC S-lxqjpj53]
- WSLg runs Linux graphical programs (X11 and Wayland) on Windows. [DOC S-lxqjpj53]
- The WSL tarballs are stage 4 style images, and the stage file page calls stage 4 a loosely defined term for a stage 3 with extra parts. [DER S-lxqjpj53, S-qfnocjvf: file names like `stage4-amd64-wsl-openrc` against the stage 4 definition]
- Since every step above is a `wsl.exe` call or a Windows-side file, a Windows endpoint tool can create, restart and remove a Gentoo instance without logging in to it. [DER S-lxqjpj53: import, terminate and shutdown are commands run from PowerShell on the Windows host]

## Reference
| need on the Windows host | command or file | source |
|---|---|---|
| enable WSL without Ubuntu | `wsl --install --no-distribution` | S-lxqjpj53 |
| import a stage tarball | `wsl --import Gentoo <dir> <file>.tar --version 2` | S-lxqjpj53 |
| install a `.wsl` tarball | `wsl --install --from-file <file>.wsl` | S-lxqjpj53 |
| global WSL settings | `%UserProfile%\.wslconfig` | S-lxqjpj53 |
| per-distribution settings | `/etc/wsl.conf` | S-lxqjpj53 |
| restart after a change | `wsl --terminate Gentoo`, `wsl --shutdown` | S-lxqjpj53 |

Related: `security/gentoo-stage-files-init-systems.md`, `security/gentoo-use-flags-profiles-keywords.md`.

## Examples
- SNIPPET: start OpenRC when a Gentoo WSL distribution starts on a Windows host; context: Gentoo imported into WSL 2 from a stage file; checked: no [DER S-lxqjpj53: the `[boot]` key from the wiki's `/etc/wsl.conf` example]
```
# /etc/wsl.conf  (inside the Gentoo distribution)
[boot]
command = "/sbin/openrc default"

# on the Windows host, then:
#   wsl --terminate Gentoo
```
