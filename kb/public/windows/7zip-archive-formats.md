---
topic: windows/7zip-archive-formats
priority: P3
applies_to: "7-Zip 26.05 (released 2026-10-21): formats it unpacks, the download packages for Windows, Linux and macOS, licence"
retrieved_utc: 2026-10-27
sources: [S-3jko5ux3, S-e46qx3w3, S-wcdfw5eg]
status: partial
---

# 7-Zip: which archives it unpacks (MSI, CAB, WIM), what ships per OS, and the release checksums

## Summary
7-Zip unpacks the Windows installer package formats `.msi`, `.cab` and `.wim` without Windows tools, and its console
version ships for Windows, Linux and macOS. The release on GitHub lists a SHA-256 digest for every file, so a tool that
installs it for one user can pin each OS's file. What the console build inside the "Extra" package unpacks is not stated.

## Facts
- 7-Zip packs and unpacks 7z, XZ, BZIP2, GZIP, TAR, ZIP and WIM. [DOC S-3jko5ux3]
- 7-Zip unpacks only (no packing) a long list of formats that includes CAB, MSI, NSIS, ISO, VHD, VHDX and RPM. [DOC S-3jko5ux3]
- So WIM can be written as well as read, while MSI and CAB can only be read. [DER S-3jko5ux3: WIM is in the packing and unpacking list, MSI and CAB in the unpacking-only list]
- The download page offers 7-Zip 26.05 (2026-10-21) for Windows as `.exe` installers (x64, x86 and arm64), alternative `.msi` installers (x64 and x86), and "7-Zip Extra", a `.7z` with the standalone console version, the 7z DLL and a plugin for Far Manager. [DOC S-e46qx3w3]
- The same page offers a console version for Linux as `.tar.xz` files (x86, x64, arm64 and arm) and one for macOS as a `.tar.xz`, and recommends the `.exe` installer over the `.msi` one. [DOC S-e46qx3w3]
- The code is free software with open source, mostly under the GNU LGPL, and some parts are under the BSD 3-clause licence. [DOC S-3jko5ux3]
- The GitHub repository `ip7z/7zip` lists release 26.05 with its files and a `digest` field on each in the form `sha256:<hex>`; the file `7z2605-linux-x64.tar.xz` has `22cf82fcc6eb7474f1d5bb4f02c0f8ebd573a718089d6833dc30f8350a3b232e`, `7z2605-mac.tar.xz` has `12ef6830317743cfd3f0ab1724bde43fcc270d8b6d8564f8c12c2a2b7f993570` and `7z2605-x64.exe` has `fd99e86f57d8f429ef5ed045bf98315af962e2309b0f1ba87a147a44c71647d0`. [DOC S-wcdfw5eg]
- A tool that installs 7-Zip for one user can therefore pin the release file and its digest of each OS from the release's API entry, as the WezTerm installer pins its files. [DER S-wcdfw5eg, S-e46qx3w3: the digest field and the per-OS files]
- Which of MSI, CAB and WIM the standalone console build in the Extra package unpacks, the name of the console program on each OS, and the command line that unpacks into a chosen folder were not read from a 7-Zip page. [UNK: the help file shipped in the package was not read]

## Reference
- 7-Zip home: https://www.7-zip.org/
- Download: https://www.7-zip.org/download.html
- Release 26.05 (API): https://api.github.com/repos/ip7z/7zip/releases/latest

## Examples
