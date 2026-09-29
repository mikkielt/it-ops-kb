---
topic: python/uv-windows-install
priority: P3
applies_to: "uv 0.12.19 on Windows (x86_64, aarch64): official release archives, per-archive SHA-256 files, the standalone install.ps1 / uv-installer.ps1; release assets read 2026-09-29"
retrieved_utc: 2026-09-29
sources: [S-xkajf5v5, S-kqisz7ri, S-tqxtar5b]
status: partial
---

# Installing a pinned uv on Windows from the official release

## Summary
uv publishes each Windows build as a zip on its GitHub release (`uv-x86_64-pc-windows-msvc.zip`, `uv-aarch64-pc-windows-msvc.zip`, `uv-i686-pc-windows-msvc.zip`) holding `uv.exe`, `uvx.exe` and `uvw.exe` at the archive root, with a `.sha256` file per archive and one combined `sha256.sum`. A script that pins a version downloads the archive for the machine's architecture, compares the SHA-256 with its own pin, and puts the three executables in a per-user directory on the user `PATH`. The official standalone installer (`https://astral.sh/uv/<version>/install.ps1`, the release's `uv-installer.ps1`) does the same to `$HOME\.local\bin` but embeds no checksum check.

## Facts
### Release archives and checksums (uv 0.12.19, published 2026-09-25)
- The release's Windows archives are `uv-x86_64-pc-windows-msvc.zip` (17,955,780 bytes), `uv-aarch64-pc-windows-msvc.zip` (19,273,809 bytes) and `uv-i686-pc-windows-msvc.zip` (19,898,790 bytes). [DOC S-kqisz7ri]
- The x86_64 archive holds `uv.exe`, `uvw.exe` and `uvx.exe` at its root, no subdirectory. [DER S-kqisz7ri: listing of the downloaded `uv-x86_64-pc-windows-msvc.zip`; `uv-installer.ps1` names the same three `bins` for every Windows target]
- Each archive has a sibling `<archive>.sha256` asset holding `<sha256>  <archive name>`, and the release has one `sha256.sum` listing every archive as `<sha256> *<archive name>`; the two agree for the Windows zips. [DOC S-kqisz7ri]
- SHA-256 of `uv-x86_64-pc-windows-msvc.zip`: `6dbb02d79e419522f1c500f0adb1cddcff0cda7d59b0d66ea7f5e3b4a1b2f5f0`. [DOC S-kqisz7ri]
- SHA-256 of `uv-aarch64-pc-windows-msvc.zip`: `115b54cb823bc48260670f5782001add6067ac8d98d18c8263a833704e287de9`. [DOC S-kqisz7ri]
- SHA-256 of `uv-i686-pc-windows-msvc.zip`: `e1c2d19d1173a0e9f81ba3f95881ad741808133e372610889ff6870629218c7f`. [DOC S-kqisz7ri]
- The GitHub release API also reports a `digest` (`sha256:...`) per asset, equal to these values for the Windows zips, and marks the 0.12.19 release `immutable`. [DOC S-kqisz7ri]
- Download url form: `https://github.com/astral-sh/uv/releases/download/<version>/<archive name>`; the installer script's own header names `https://releases.astral.sh/github/uv/releases/download/<version>` as the source it fetches from. [DOC S-kqisz7ri, S-tqxtar5b]
- The release notes list each archive with a checksum link on the `releases.astral.sh` mirror (`https://releases.astral.sh/github/uv/releases/download/0.12.19/<archive>` and `<archive>.sha256`), labelling `uv-x86_64-pc-windows-msvc.zip` "x64 Windows" and `uv-aarch64-pc-windows-msvc.zip` "ARM64 Windows". [DOC S-kqisz7ri]
- The release notes state "The artifacts in this release have attestations generated with GitHub Artifact Attestations", verified with `gh attestation verify <file> --repo astral-sh/uv`, or offline against a downloaded bundle with `--bundle <file>`. [DOC S-kqisz7ri]
- For each Windows zip's digest, GitHub's attestations API returns two sigstore bundles: SLSA provenance v1 from `.github/workflows/release.yml` in `astral-sh/uv`, and an in-toto release v0.2 attestation for `pkg:github/astral-sh/uv@0.12.19` whose subjects include every archive and its `.sha256` file. [DER S-kqisz7ri: `GET /repos/astral-sh/uv/attestations/sha256:<digest>` for the x86_64 and aarch64 digests, decoded 2026-09-29]
- `uv.exe`, `uvx.exe` and `uvw.exe` in the 0.12.19 x86_64 zip carry a valid Authenticode signature (`Get-AuthenticodeSignature` status `Valid`, signer `CN="OpenAI OpCo, LLC"`); neither the install docs nor the release notes mention Authenticode, so the signer is not a documented promise. [DER S-kqisz7ri: the downloaded archive's files checked on Windows 11, 2026-09-29]
- On 2026-09-29 the newest release was 0.12.20 (published 2026-09-28), so a pin at 0.12.19 is one patch release behind; a pin is a chosen value, not the latest. [DOC S-kqisz7ri: release API `latest`]

### The standalone installer
- The documented Windows install is `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`, and a version is requested by putting it in the url: `https://astral.sh/uv/0.12.19/install.ps1`. [DOC S-xkajf5v5]
- The docs recommend inspecting the script first (`irm https://astral.sh/uv/install.ps1 | more`). [DOC S-xkajf5v5]
- The script installs `uv.exe`, `uvx.exe` and `uvw.exe` into the first existing choice of `$env:XDG_BIN_HOME`, `$env:XDG_DATA_HOME/../bin`, or `$HOME/.local/bin`, then adds that directory to the user `PATH` by editing the `HKEY_CURRENT_USER\Environment` `Path` value. [DER S-tqxtar5b: header and `Add-Path` of the release's script text]
- The docs' uninstall steps remove `$HOME\.local\bin\uv.exe`, `uvx.exe` and `uvw.exe`; before uv 0.5.0 the binaries went to `~/.cargo/bin`, and an upgrade does not remove those. [DOC S-xkajf5v5]
- `UV_INSTALL_DIR` (or `CARGO_DIST_FORCE_INSTALL_DIR`) forces the install directory; `UV_UNMANAGED_INSTALL` does the same and also turns off the `PATH` edit and the updater; `UV_NO_MODIFY_PATH=1` alone skips the `PATH` edit; `UV_DISABLE_UPDATE` skips installing the updater. [DER S-tqxtar5b: variables read at the top of the release's script and in its install-directory selection]
- The install writes a receipt under `%LOCALAPPDATA%\uv` (or `%XDG_CONFIG_HOME%\uv`), which `uv self update` uses; `uv self update` re-runs the installer and may change shell profiles unless `UV_NO_MODIFY_PATH=1`. [DER S-tqxtar5b, S-xkajf5v5: `$receipt_home` in the script; the docs' self-update tip]
- Self-update is disabled when uv came from another method such as `pip install uv`; the package manager upgrades it instead. [DOC S-xkajf5v5]
- The script picks the archive from `RuntimeInformation.OSArchitecture` (X64 to x86_64, Arm64 to aarch64, X86 to i686) and notes it may report X64 on Arm64 Windows, where emulation works. [DER S-tqxtar5b: `Get-Arch` in the release's script]
- The script downloads with `Net.Webclient` and unpacks with `Expand-Archive`; it contains no SHA-256 or checksum comparison, so a pinned install verifies the archive itself. [DER S-tqxtar5b: `Download` in the release's script, and no checksum code anywhere in the 0.12.19 script text]
- A script that installs uv itself (not through `install.ps1`) and treats another `uv.exe` on `PATH`, one in `$HOME\.local\bin`, or one in `%USERPROFILE%\.cargo\bin` as a conflict follows from the documented locations. [DER S-xkajf5v5, S-tqxtar5b: default and legacy install directories]

## Reference
| Need | Value | Source |
|---|---|---|
| x86_64 archive | `uv-x86_64-pc-windows-msvc.zip` | S-kqisz7ri |
| Arm64 archive | `uv-aarch64-pc-windows-msvc.zip` | S-kqisz7ri |
| Checksum files | `<archive>.sha256`, `sha256.sum` (release assets) | S-kqisz7ri |
| Contents | `uv.exe`, `uvx.exe`, `uvw.exe` | S-kqisz7ri |
| Provenance check | `gh attestation verify <file> --repo astral-sh/uv` | S-kqisz7ri |
| Default per-user directory | `$HOME\.local\bin` | S-tqxtar5b, S-xkajf5v5 |
| PATH registry key | `HKCU\Environment`, value `Path` | S-tqxtar5b |
| Skip PATH edit | `UV_NO_MODIFY_PATH=1` | S-tqxtar5b, S-xkajf5v5 |

Related: `python/uv-projects.md` (the project workflow), `python/windows-python-install.md` (the Python installer).

## Examples
- SNIPPET: download a pinned uv Windows archive and compare its SHA-256; context: Windows PowerShell 5.1 or 7, uv 0.12.19; checked: no [DER S-kqisz7ri: asset names, url form and the x86_64 digest]
```powershell
$ver = '0.12.19'
$zip = 'uv-x86_64-pc-windows-msvc.zip'
$want = '6dbb02d79e419522f1c500f0adb1cddcff0cda7d59b0d66ea7f5e3b4a1b2f5f0'
$out = Join-Path $env:TEMP $zip
Invoke-WebRequest "https://github.com/astral-sh/uv/releases/download/$ver/$zip" -OutFile $out
if ((Get-FileHash $out -Algorithm SHA256).Hash -ne $want.ToUpper()) { throw 'uv checksum mismatch' }
Expand-Archive $out -DestinationPath "$HOME\.local\bin" -Force
```
