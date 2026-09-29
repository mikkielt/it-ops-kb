---
topic: python/windows-python-install
priority: P3
applies_to: "CPython 3.14.7 for Windows: the python.org full installer (deprecated since 3.14), the Python install manager, the py launcher, PEP 514 registry entries and the Microsoft Store python alias; python.org release API read 2026-09-29"
retrieved_utc: 2026-09-29
sources: [S-sjuwcuhk, S-lkt7o42d, S-jzqdphnx, S-srwea6un, S-4jodaif5, S-omr5o3jv]
status: partial
---

# Installing Python on Windows unattended: python.org installer, launcher, registry, Store alias

## Summary
A scripted per-user install of the pinned CPython from python.org uses the full installer (`python-<version>-<arch>.exe`) with `/quiet` and `name=value` options; its defaults are `InstallAllUsers=0`, `PrependPath=0`, `Include_launcher=1`, `InstallLauncherAllUsers=1`, `Include_test=1`, `Shortcuts=1`. That installer is deprecated since 3.14 and not produced for 3.16 and later, when the Python install manager (`python`, `py`, `pymanager`, MSIX) is the only route. What is already on a host is found through `PATH` (the Store shortcut lives in `WindowsApps`), the `py` launcher (`py -0p`) and the PEP 514 registry keys under `Software\Python`. The python.org release API publishes each file's SHA-256 and Sigstore files.

## Facts
### The full installer and its unattended options
- The full installer is deprecated since Python 3.14 and will not be produced for Python 3.16 or later; the Python install manager is the modern installer. [DOC S-sjuwcuhk]
- Python 3.14.7 still publishes Windows installers for 32-bit, 64-bit and ARM64 (`python-3.14.7.exe`, `python-3.14.7-amd64.exe`, `python-3.14.7-arm64.exe`) under `https://www.python.org/ftp/python/3.14.7/`. [DOC S-lkt7o42d]
- Installer command-line switches (from `/?`): `/passive` (progress, no interaction), `/quiet` (no UI, also for uninstall), `/simple` (no customisation), `/uninstall` (remove without confirmation), `/layout [directory]` (pre-download every component), `/log [filename]`. [DOC S-sjuwcuhk]
- Every other option is `name=value`, usually `0` to disable, `1` to enable, or a path. [DOC S-sjuwcuhk]
- `InstallAllUsers` (default 0) makes a system-wide install; `TargetDir` sets the directory and by default follows `InstallAllUsers`. [DOC S-sjuwcuhk]
- Default directories: `DefaultJustForMeTargetDir` is `%LocalAppData%\Programs\Python\PythonXY` (with `-32` or `-64` suffix variants); `DefaultAllUsersTargetDir` is `%ProgramFiles%\Python X.Y` (or under `%ProgramFiles(x86)%`). [DOC S-sjuwcuhk]
- `PrependPath` (default 0) prepends the install and `Scripts` directories to `PATH` and adds `.PY` to `PATHEXT`; `AppendPath` (default 0) appends them instead. [DOC S-sjuwcuhk]
- `Include_launcher` (default 1) installs the launcher; `InstallLauncherAllUsers` (default 1) installs it for all users and also requires `Include_launcher=1`; `LauncherOnly` (default 0) installs only the launcher and overrides most other options. [DOC S-sjuwcuhk]
- `Include_test` (default 1) installs the standard library test suite; `Include_pip`, `Include_doc`, `Include_tcltk`, `Include_tools`, `Include_dev`, `Include_lib` and `Include_exe` default to 1, `Include_debug` and `Include_symbols` to 0. Omitting `Include_dev`, `Include_exe` or `Include_lib` may leave an unusable installation. [DOC S-sjuwcuhk]
- `Shortcuts` (default 1) creates shortcuts for the interpreter, documentation and IDLE; `AssociateFiles` (default 1) creates file associations when the launcher is also installed; `CompileAll` (default 0) compiles `.py` to `.pyc`; `SimpleInstall` (default 0) disables most UI. [DOC S-sjuwcuhk]
- The same options can sit in a file named `unattend.xml` next to the installer executable, as `<Option Name="..." Value="..."/>` elements under `<Options>`. [DOC S-sjuwcuhk]
- The documented silent examples are `python-3.9.0.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0` (system-wide, elevated prompt) and a per-user form with `InstallAllUsers=0 Include_launcher=0 Include_test=0`; omitting the launcher also omits file associations. [DOC S-sjuwcuhk]
- A "just for me" install (`Install Now`) needs no administrator, unless a C runtime system update is required or the launcher is installed for all users; an all-users install goes to Program Files and puts the launcher in the Windows directory. [DOC S-sjuwcuhk]
- A per-user quiet install that must never ask for elevation therefore passes `InstallAllUsers=0` and `InstallLauncherAllUsers=0` explicitly, since the launcher's all-users default is 1. [DER S-sjuwcuhk: the two defaults and the administrator sentence above]
- Whether a quiet `InstallAllUsers=0` run with the default `InstallLauncherAllUsers=1` elevates or fails is not stated. [UNK: not in the Windows usage page; a lab run decides]
- The installer's maintenance mode (Programs and Features, Uninstall/Change) offers Modify, Repair and Uninstall; Uninstall leaves the launcher, which has its own entry. [DOC S-sjuwcuhk]
- The Python docs do not state whether the full installer installs a `python3.exe`; they name `python.exe`, and a `python3` command only for the install manager. [DOC S-sjuwcuhk]
- In the 3.14.7 installer sources, the `exe_python` component group of the executables MSI installs `python.exe` and `pythonw.exe` (plus `vcruntime140.dll`) into the install directory and writes their paths to the PEP 514 `InstallPath` key. [CODE S-srwea6un: Tools/msi/exe/exe_files.wxs#exe_python]
- The python.org full installer (3.14.7) therefore ships no `python3.exe`: none of the 89 build files under `Tools/msi/` at the `v3.14.7` tag names one (the only `python3` entry is `python3.lib`), so `python3` on such a host reaches whatever else is on `PATH`, often the Store shortcut. [DER S-srwea6un: the exe_python component list, and a search of every `Tools/msi/` file at v3.14.7 on 2026-09-29]

### Release API: checksums and signatures
- `https://www.python.org/api/v2/downloads/release_file/?release=<id>` returns one JSON object per release file with `name`, `url`, `sha256_sum`, `md5_sum`, `filesize`, `sigstore_bundle_file`, `sigstore_cert_file`, `sigstore_signature_file`, `gpg_signature_file` and `sbom_spdx2_file`; release id 1116 is Python 3.14.7 (released 2026-08-05). [DOC S-lkt7o42d]
- The Windows files of 3.14.7 in that listing are the embeddable packages (32-bit, 64-bit, ARM64), the three installers and a `windows-3.14.7.json` release manifest; each has a `.sigstore` bundle, `.crt` and `.sig` beside it and an empty `gpg_signature_file`. [DOC S-lkt7o42d]
- `sha256_sum` of `python-3.14.7-amd64.exe` is `9d9eb2709ef81bf5cd30db3c2096bdbc4ea10087c22e62f27d356b36f6ae9649` (33,258,168 bytes) and of `python-3.14.7-arm64.exe` `9a3fe120cc81bc2cb099550f794d8356811f96a86c7f438519243c3485db928d` (32,570,072 bytes); the 32-bit installer is `097fc03d4ac2de66ee1d73a0c5d2d323b5c0f14923f7207686ce93149a80f0a6`. [DOC S-lkt7o42d]
- The pins in `_tools/install-python.ps1` (3.14.7, amd64 and arm64) equal these API values on 2026-09-29. [DER S-lkt7o42d: the two hashes above compared with the script]
- CPython release artifacts are signed with Sigstore; from Python 3.14 Sigstore is the only signing and verification method, and OpenPGP signatures remain only for releases older than the 3.14 series (PEP 761). [DOC S-jzqdphnx]
- Verifying needs the artifact, its `.sigstore` bundle, the expected signer identity (the release manager's email for that version, listed on the page) and OIDC issuer; for 3.14 the issuer is `https://github.com/login/oauth`. [DOC S-jzqdphnx]
- python.org recommends the `sigstore` client from PyPI: `python -m sigstore verify identity --bundle <file>.sigstore --cert-identity <email> --cert-oidc-issuer <issuer> <file>`, which prints `OK: <file>` on success; `cosign` is the suggested standalone binary. [DOC S-jzqdphnx]
- A pinned sha256 value can be checked against the bundle instead of the file (`sha256:<hex>` in place of the path), which needs sigstore-python 3.3.0 or later; verifying a bundle is offline by default, and `--offline` also stops TUF metadata updates. [DOC S-jzqdphnx]
- A script that pins the release API's sha256 and then checks the installer's Windows Authenticode signature does not use the Sigstore bundle; the Python docs pages read here do not describe Authenticode signing of the installer. [DER S-jzqdphnx, S-sjuwcuhk: Sigstore is the documented release signature; the Windows usage page names Authenticode only for install manager index signatures]

### py launcher and the Python install manager
- The Python install manager is installed from the Microsoft Store or from an MSIX downloaded from python.org (`Add-AppxPackage <path to MSIX>`); the two are identical, and Store, WinGet, MSIX and MSI installs can coexist and share configuration and runtimes. [DOC S-sjuwcuhk]
- After installing it, `python`, `py` and `pymanager` should work; `pymanager` is the unambiguous name for scripts because `py` may already belong to an older launcher. [DOC S-sjuwcuhk]
- A `python3` command is included that mimics `python`, to catch accidental POSIX-style calls; it is not meant to be widely used. [DOC S-sjuwcuhk]
- With no runtime installed, a launch command installs the current latest release automatically when `automatic_install` (environment variable `PYTHON_MANAGER_AUTOMATIC_INSTALL`) is on, which is the default. [DOC S-sjuwcuhk]
- The versioned aliases such as `python3.14.exe` live in `%LocalAppData%\Python\bin` by default and are on `PATH` only if the user adds that directory. [DOC S-sjuwcuhk]
- `py --list`, `--list-paths`, `-0` and `-0p` are kept for compatibility with the old launcher; the listing includes runtimes discovered through PEP 514. [DOC S-sjuwcuhk]
- A `py` that gives "can't open file" errors usually means the legacy launcher is installed and has priority over the install manager; the legacy launcher's `py` overrides the manager's by default. [DOC S-sjuwcuhk]
- The install manager's troubleshooting table expects `%UserProfile%\AppData\Local\Microsoft\WindowsApps` on `PATH`, after the other user paths, and tells the user to check "Manage app execution aliases" for "Python (default)", "Python (default windowed)" and "Python install manager". [DOC S-sjuwcuhk]

### PEP 514 registry entries (how installs are found)
- Environments are registered under `HKEY_CURRENT_USER\Software\Python\<Company>\<Tag>`, `HKEY_LOCAL_MACHINE\Software\Python\<Company>\<Tag>` and, for 32-bit interpreters on 64-bit Windows, `HKEY_LOCAL_MACHINE\Software\Wow6432Node\Python\<Company>\<Tag>`. [DOC S-4jodaif5]
- Official releases use `PythonCore` as Company and `sys.winver` as Tag; Company-Tag pairs are case-insensitive and unique; `PyLauncher` is a reserved Company. [DOC S-4jodaif5]
- A tool that selects one environment, such as `py.exe`, should prefer the `HKEY_CURRENT_USER` registration over a matching `HKEY_LOCAL_MACHINE` one. [DOC S-4jodaif5]
- Each environment key has an `InstallPath` subkey whose default value equals `sys.prefix`; an optional `ExecutablePath` value is the full path to `python.exe`, and for `PythonCore` its default is `python.exe` in the `InstallPath` directory. [DOC S-4jodaif5]
- A preflight for "is this minor version already installed for this user or for the machine" reads `Software\Python\PythonCore\3.14\InstallPath` in `HKCU`, `HKLM` and `HKLM\...\Wow6432Node`, or runs `py -0p`. [DER S-4jodaif5, S-sjuwcuhk: registry layout and the retained `-0p` listing]

### The Microsoft Store `python` and `python3` shortcut
- Windows ships a shortcut (an app execution alias) that sends `python.exe` and `python3.exe` typed in a terminal to the Store's Python package; installing that package replaces them with the real commands. [DOC S-omr5o3jv]
- Run with any command-line arguments, the shortcut returns an error code saying Python is not installed, so batch files and scripts do not open the Store; the page does not give the code. [DOC S-omr5o3jv]
- A python.org install with "add to PATH" makes the new `python` win over the shortcut; installers that add `python` at lower priority than the built-in shortcut lose to it. [DOC S-omr5o3jv]
- To switch the shortcut off without installing Python: Start, "Manage app execution aliases", set the "App Installer" Python entries to Off. [DOC S-omr5o3jv]
- The shortcut files sit in the per-user `WindowsApps` directory, which the operating system puts on `PATH` after the other user paths. [DER S-omr5o3jv, S-sjuwcuhk: the `WindowsApps` directory named in the install manager's troubleshooting rows]
- A `python3` on `PATH` that resolves inside `...\Microsoft\WindowsApps\` is therefore the Store shortcut or an install manager alias, not a runtime from python.org; a `-c` probe that runs it tells which. [DER S-omr5o3jv, S-sjuwcuhk: WindowsApps location and the shortcut's behaviour]
- The pages do not state the shortcut's exit code, or whether the Store shortcut and the install manager's `python3` share one alias entry. [UNK: not in the Learn FAQ or the Python docs; a Windows lab run decides]

## Reference
| Need | Command or key | Source |
|---|---|---|
| Silent per-user install | `python-3.14.7-amd64.exe /quiet InstallAllUsers=0 InstallLauncherAllUsers=0 PrependPath=1 Include_test=0 Shortcuts=0` | S-sjuwcuhk |
| Pre-download components | `python-3.14.7-amd64.exe /layout <dir>` | S-sjuwcuhk |
| Default per-user directory | `%LocalAppData%\Programs\Python\PythonXY` | S-sjuwcuhk |
| Installer SHA-256 and Sigstore | `sha256_sum`, `sigstore_bundle_file` of the release file API | S-lkt7o42d |
| Verify a Sigstore bundle | `python -m sigstore verify identity --bundle <file>.sigstore --cert-identity <email> --cert-oidc-issuer <issuer> <file>` | S-jzqdphnx |
| List installs | `py -0p` | S-sjuwcuhk |
| Registry roots | `HKCU\Software\Python`, `HKLM\Software\Python`, `HKLM\Software\Wow6432Node\Python` | S-4jodaif5 |
| Store shortcut off | Settings, "Manage app execution aliases", "App Installer" Python entries Off | S-omr5o3jv |

Related: `python/stdlib-windows-portability.md` (interpreter names and command-line limits), `python/uv-windows-install.md` (uv), `claude/hooks.md` (hooks on Windows).

## Examples
- SNIPPET: list per-user and per-machine CPython registrations from PowerShell; context: Windows PowerShell 5.1 or 7, PEP 514 keys; checked: no [DER S-4jodaif5: key paths and the `InstallPath` default value]
```powershell
$roots = 'HKCU:\Software\Python\PythonCore',
         'HKLM:\Software\Python\PythonCore',
         'HKLM:\Software\Wow6432Node\Python\PythonCore'
foreach ($r in $roots) {
    if (Test-Path $r) {
        Get-ChildItem $r | ForEach-Object {
            $ip = Join-Path $_.PSPath 'InstallPath'
            [pscustomobject]@{ Root = $r; Tag = $_.PSChildName
                               Path = (Get-ItemProperty $ip -ErrorAction SilentlyContinue).'(default)' }
        }
    }
}
```
