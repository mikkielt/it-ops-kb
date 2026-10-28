#!/usr/bin/env python3
"""install_7z: install the pinned 7-Zip release for this user (stdlib only). Docs: kb/_self/tools.md.

7-Zip is an optional dependency: `fetch.py text` runs its `7z` over a downloaded MSI, CAB or WIM file to read the text
inside (_tools/fetch_extractors.csv). Nothing else in the kb needs it.

  install_7z.py --plan [--os OS]   print each OS's (or OS's) pinned URL, SHA-256 and per-user target; installs nothing
  install_7z.py --declined         print the saved text for a person who declines the install
  install_7z.py --yes [--from FILE] [--os OS] [--replace]
                                   install the pin for this host, after the person agreed: download the pinned file (or
                                   take FILE), refuse it unless its SHA-256 is the pin, then put the program in the
                                   per-user target. Without --yes it prints the plan and installs nothing

Per-user targets: macOS `~/Library/Application Support/7zip/<release>/7z`; Linux `$XDG_DATA_HOME/7zip/<release>/7z`
(default `~/.local/share`); Windows `%LOCALAPPDATA%\\Programs\\7-Zip\\7z.exe` (the release's own installer, started
silently with `/S /D=` that folder). PATH, shell profiles and every other file stay as they are: the script prints the
path of the program, and `fetch.py text` finds a program installed here without PATH (`installed`). A file whose SHA-256
is not the pin is deleted and nothing is created; a target that already exists is left alone unless --replace.

The pin: RELEASE and PINS below, the 7-Zip release at the time, each SHA-256 the digest GitHub shows for the release
asset (https://github.com/ip7z/7zip/releases/tag/26.05). Moving it: take the release tag and the five assets' digests.

Exit codes: 0 installed (or --plan, --declined), 1 download, checksum or extraction error, 2 a bad argument or an OS or
CPU with no pinned file, 3 the target exists (nothing changed).

Answers: how to install the pinned 7-Zip release that fetch.py text uses for MSI, CAB and WIM files
Use: python3 _tools/install_7z.py --plan|--declined|--yes
"""
import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

RELEASE = "26.05"
BASE_URL = "https://github.com/ip7z/7zip/releases/download/" + RELEASE + "/"
PINS = {
    "macos": {
        "file": "7z2605-mac.tar.xz",
        "sha256": "12ef6830317743cfd3f0ab1724bde43fcc270d8b6d8564f8c12c2a2b7f993570",
    },
    "linux-x64": {
        "file": "7z2605-linux-x64.tar.xz",
        "sha256": "22cf82fcc6eb7474f1d5bb4f02c0f8ebd573a718089d6833dc30f8350a3b232e",
    },
    "linux-arm64": {
        "file": "7z2605-linux-arm64.tar.xz",
        "sha256": "0b71f6cfc34669b3bf69f2347efd3429f77020665003a13b9cdc53b784270421",
    },
    "windows-x64": {
        "file": "7z2605-x64.exe",
        "sha256": "fd99e86f57d8f429ef5ed045bf98315af962e2309b0f1ba87a147a44c71647d0",
    },
    "windows-arm64": {
        "file": "7z2605-arm64.exe",
        "sha256": "86d5790d5dd84cab4636c3bb7fab10d3ed7cd3e57e6119401bd2769e28165268",
    },
}
FAMILIES = ("macos", "windows", "linux")
KEEP = {"7zz": "7z", "License.txt": "License.txt", "readme.txt": "readme.txt"}  # tar members kept, by the name they get

TARGET_TEXT = {
    "macos": "~/Library/Application Support/7zip/" + RELEASE + "/7z",
    "windows": "%LOCALAPPDATA%\\Programs\\7-Zip\\7z.exe",
    "linux": "$XDG_DATA_HOME/7zip/" + RELEASE + "/7z (default ~/.local/share)",
}

DECLINED = """7-Zip is optional. Without it nothing else in the kb changes: fetch.py text still reads pages, PDFs,
zip, tar and gzip files and spreadsheets, and exits 2 on an MSI, CAB or WIM file, naming 7z and this installer.
Install it later with: python3 _tools/install_7z.py --plan, then --yes."""


def host_os():
    return {"darwin": "macos", "win32": "windows"}.get(sys.platform, "linux")


def host_key():
    """The PINS key for this host, or None when no file is pinned for its CPU."""
    name, cpu = host_os(), platform.machine().lower()
    if name == "macos":
        return "macos"
    if cpu in ("x86_64", "amd64"):
        return name + "-x64"
    return name + "-arm64" if cpu in ("arm64", "aarch64") else None


def target(os_name):
    """The per-user path of the program on `os_name`, read from the environment of this process."""
    home = Path(os.path.expanduser("~"))
    if os_name == "macos":
        return home / "Library" / "Application Support" / "7zip" / RELEASE / "7z"
    if os_name == "windows":
        base = os.environ.get("LOCALAPPDATA") or str(home / "AppData" / "Local")
        return Path(base) / "Programs" / "7-Zip" / "7z.exe"
    data = os.environ.get("XDG_DATA_HOME") or str(home / ".local" / "share")
    return Path(data) / "7zip" / RELEASE / "7z"


def installed():
    """The per-user program this installer put on this host as a path string, or None when it is not there."""
    exe = target(host_os())
    return str(exe) if exe.is_file() else None


def print_plan(os_names):
    for name in os_names:
        for key in sorted(k for k in PINS if k.split("-")[0] == name):
            pin = PINS[key]
            print("%-13s %s" % (key, BASE_URL + pin["file"]))
            print("%-13s sha256 %s" % ("", pin["sha256"]))
        print("%-13s installs to %s" % ("", TARGET_TEXT[name]))


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url, dest):
    request = urllib.request.Request(url, headers={"User-Agent": "it-ops-kb-install-7z"})
    with urllib.request.urlopen(request, timeout=60) as response, open(dest, "wb") as out:
        shutil.copyfileobj(response, out, 1 << 20)


def install_tar(archive, dest):
    """Put the program and its licence files from the verified tar `archive` in the folder of `dest`: only the members
    KEEP names, written under the name it gives, never a path from the archive."""
    folder = dest.parent
    folder.mkdir(parents=True, exist_ok=True)
    found = set()
    with tarfile.open(archive, mode="r:*") as tar:
        for info in tar:
            name = KEEP.get(info.name)
            if name is None or not info.isfile():
                continue
            src = tar.extractfile(info)
            with open(folder / name, "wb") as out:
                shutil.copyfileobj(src, out, 1 << 20)
            found.add(info.name)
    if "7zz" not in found:
        raise ValueError("the archive holds no 7zz")
    dest.chmod(0o755)


def install_exe(installer, dest):
    """Run the verified Windows installer silently into the folder of `dest` (7-Zip's `/S` and `/D=`, the last argument)."""
    p = subprocess.run([str(installer), "/S", "/D=" + str(dest.parent)], capture_output=True, timeout=300)
    if p.returncode or not dest.is_file():
        raise ValueError("the installer exited %s and left no %s" % (p.returncode, dest.name))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Install the pinned 7-Zip release for this user.")
    parser.add_argument("--plan", action="store_true", help="print the pinned URL, SHA-256 and target; install nothing")
    parser.add_argument("--declined", action="store_true", help="print the text for a person who declines")
    parser.add_argument("--yes", action="store_true", help="the person agreed: install")
    parser.add_argument("--os", choices=FAMILIES, help="the OS whose pin to show or use (default: this host)")
    parser.add_argument("--from", dest="source", metavar="FILE", help="use this file instead of downloading the pin")
    parser.add_argument("--replace", action="store_true", help="replace a target that already exists")
    args = parser.parse_args(argv)

    if args.declined:
        print(DECLINED)
        return 0
    if args.plan:
        print_plan([args.os] if args.os else list(FAMILIES))
        return 0

    os_name = args.os or host_os()
    if os_name != host_os():
        print("install_7z: --os %s is not this host (%s); --plan shows its pin" % (os_name, host_os()), file=sys.stderr)
        return 2
    key = host_key()
    if key is None:
        print("install_7z: no pinned file for this CPU (%s)" % platform.machine(), file=sys.stderr)
        return 2
    if not args.yes:
        print_plan([os_name])
        print("Nothing installed: ask the person, then run again with --yes.")
        return 2

    pin = PINS[key]
    dest = target(os_name)
    if os.path.lexists(dest) and not args.replace:
        print("install_7z: %s already exists; nothing changed (--replace overwrites it)" % dest, file=sys.stderr)
        return 3

    with tempfile.TemporaryDirectory(prefix="7z-dl-") as scratch:
        if args.source:
            archive = Path(args.source)
            if not archive.is_file():
                print("install_7z: no such file: " + args.source, file=sys.stderr)
                return 1
        else:
            archive = Path(scratch) / pin["file"]
            url = BASE_URL + pin["file"]
            print("Downloading " + url)
            try:
                download(url, archive)
            except OSError as exc:
                print("install_7z: download failed: %s" % exc, file=sys.stderr)
                return 1
        actual = sha256_of(archive)
        if actual != pin["sha256"]:
            print("install_7z: SHA-256 mismatch for %s: expected %s, got %s. Nothing installed." % (
                archive.name, pin["sha256"], actual), file=sys.stderr)
            return 1
        print("SHA-256 OK: " + actual)
        try:
            if os.path.lexists(dest):
                dest.unlink()
            if os_name == "windows":
                installer = Path(scratch) / pin["file"]
                if archive != installer:
                    shutil.copyfile(archive, installer)
                install_exe(installer, dest)
            else:
                install_tar(archive, dest)
        except (OSError, ValueError, tarfile.TarError, subprocess.SubprocessError) as exc:
            print("install_7z: install failed: %s" % exc, file=sys.stderr)
            return 1
    print("Installed 7-Zip %s at %s" % (RELEASE, dest))
    print("fetch.py text finds it there; PATH and shell profiles are unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
