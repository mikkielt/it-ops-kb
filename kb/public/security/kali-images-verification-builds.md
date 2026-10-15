---
topic: security/kali-images-verification-builds
priority: P3
applies_to: "Kali Linux image types (Installer, NetInstaller, Live, Everything, VM, ARM), verifying a download with SHA256SUMS and the archive signing key, and building a custom or last-release ISO with the kali-live and kali-installer build scripts"
retrieved_utc: 2026-10-15
sources: [S-h46mfwhy, S-2sdbla22, S-dxg7xu5h, S-a3rz5fyq, S-2p6jllwx, S-o5qyuho5]
status: partial
---

# Kali images, download verification and image builds

## Summary
Kali is distributed as an Installer image (the recommended one, with an offline copy of the default tool sets), a small NetInstaller, a Live image and an "Everything" flavour, plus pre-built VM and ARM images. A download is checked against a `SHA256SUMS` file whose detached signature `SHA256SUMS.gpg` is made with the Kali archive signing key. Images are produced by build scripts in GitLab: `kali-live` (live-build) and `kali-installer` (simple-cdd), and the same scripts re-create the latest release from `kali-last-snapshot`. Package sources are in `security/kali-apt-sources-metapackages.md`, accounts and VMs in `security/kali-default-account-vm-containers.md`. Read from kali.org on 2026-10-15.

## Facts
- The download page offers Installer, NetInstaller and Live images for x86-64, and an "Everything" flavour of Installer and Live; the docs' advice is "if in doubt, use the Installer image". [DOC S-h46mfwhy]
- The Installer image holds a local copy of the `top10`, `default` and `large` metapackages, so it installs offline, and it cannot boot a live system; the NetInstaller holds none and downloads all packages during installation. [DOC S-h46mfwhy]
- The Live image installs only the default configuration: it does not let the user choose a desktop environment or extra metapackages, which the installer images do. [DOC S-h46mfwhy]
- The Everything flavour is for offline use, is larger than 9 GB, contains nearly all tools and is available by BitTorrent only. [DOC S-h46mfwhy]
- The installer defaults are Xfce with `kali-linux-top10` and `kali-linux-default`; choosing no desktop environment gives a headless system used for servers, dropboxes, ARM devices and the cloud. [DOC S-h46mfwhy]
- Pre-built VM images for VMware and VirtualBox come with guest tools installed, and ARM images exist per device because the architectures vary too much for one image. [DOC S-2sdbla22]
- The download must be verified: the page warns never to use an image from anywhere but the official sources and to compare the SHA256 against the official value, because a modified Kali image is easy to host. [DOC S-2sdbla22]
- The strongest check uses three files from the download server: the ISO, `SHA256SUMS` and the detached signature `SHA256SUMS.gpg`, verified with `gpg --verify SHA256SUMS.gpg SHA256SUMS` after importing the Kali key. [DOC S-dxg7xu5h, S-2sdbla22]
- The key is fetched from `https://archive.kali.org/archive-key.asc`; the fingerprint to compare is `827C 8569 F251 8CC6 77FE CA1A ED65 462E C8D5 E4C5` ("Kali Linux Archive Automatic Signing Key (2025)", created 2025-04-17, expires 2028-04-17). [DOC S-dxg7xu5h, S-2sdbla22]
- Even a good signature prints the GPG warning that the key is not certified with a trusted signature, and the page says to stop if the "Good signature" message or the key id is missing. [DOC S-dxg7xu5h]
- The weaker checks are a hash compared by eye with the web page (open to DNS poisoning) and a torrent's `.txt.sha256sum` file (unsigned): each is rated lower than the signed file. [DOC S-2sdbla22]
- The keyring package `kali-archive-keyring` carried the new Automatic Archive Signing Key from 2025.1c (28 April 2025), which is why that point release exists. [DOC S-2p6jllwx]
- Kali also produces weekly builds with the latest packages at download time, which means fewer updates on first boot; they are automated, not QA'd like the standard release images. [DOC S-a3rz5fyq]
- A custom live image is built with live-build from `kalilinux/build-scripts/kali-live`, an installer image with simple-cdd and debian-cd from `kali-installer`; both are driven by `./build.sh`, and the original `live-build-config` URL redirects to `kali-live`. [DOC S-o5qyuho5]
- `build.sh` takes `--distribution`, `--variant` (xfce, gnome, kde, mate, e17, lxde, i3), `--arch`, `--version`, `--subdir`, `--verbose`, `--debug` and, for Live ISOs only, `--proposed-updates`; the build writes `./images/kali-linux-rolling-live-amd64.iso` by default. [DOC S-o5qyuho5]
- `./build.sh --distribution kali-last-snapshot --version 2026.2 --subdir kali-2026.2` re-creates the latest distributed image, and a local mirror is set by writing its URL into a `.mirror` file. [DOC S-o5qyuho5]
- Package lists live in `kali-config/` (`installer-default/packages`, `variant-default/package-lists/kali.list.chroot`), whose default includes `kali-linux-default`; files are overlaid with `includes.chroot`, `includes.binary` or `includes.installer`, and hooks run from `kali-config/common/hooks/`. [DOC S-o5qyuho5]
- The Kali team builds Base (installer and live), ARM, Cloud, Container, VM, WSL and NetHunter images from separate repositories, and announced a consistency pass over all of them for 2026.3. [DOC S-a3rz5fyq]
- For a fleet, an image pipeline should verify `SHA256SUMS.gpg` against the pinned fingerprint before an image enters the library, and build from `kali-last-snapshot` with an explicit `--version` when it needs the same content again. [DER S-dxg7xu5h, S-o5qyuho5: signed checksum file, snapshot rebuild flags]
- Which image a given date's weekly build corresponds to, and the build scripts' repository contents beyond the build page, were not read. [UNK: logged in `_gaps.md`]

## Reference
| image | contains | live boot | offline install |
|---|---|---|---|
| Installer | local copy of top10, default, large | no | yes |
| NetInstaller | nothing; downloads everything | no | no |
| Live | default configuration | yes | default config only |
| Everything (Installer or Live) | nearly all tools, >9 GB, torrent only | per flavour | yes |

Related: `security/kali-releases-rolling-model.md`, `security/kali-apt-sources-metapackages.md`, `security/kali-default-account-vm-containers.md`.

## Examples
- SNIPPET: verify a downloaded ISO against the signed checksum file; context: Linux workstation with `gpg`, `SHA256SUMS` and `SHA256SUMS.gpg` from the same directory as the image; checked: no [DER S-dxg7xu5h: the page's key import, fingerprint check and verify commands]
```
wget -q -O - https://archive.kali.org/archive-key.asc | gpg --import
gpg --fingerprint 827C8569F2518CC677FECA1AED65462EC8D5E4C5
gpg --verify SHA256SUMS.gpg SHA256SUMS
grep kali-linux-2026.2-live-amd64.iso SHA256SUMS | shasum -a 256 -c
```
