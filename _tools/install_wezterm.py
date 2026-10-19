#!/usr/bin/env python3
"""install_wezterm: install the pinned WezTerm release for this user (stdlib only). Docs: kb/_self/tools.md.

WezTerm is an optional dependency: it shows `kbmon` live in a pane beside the chat. Nothing in the kb needs it.

  install_wezterm.py --plan [--os OS]   print each OS's (or OS's) pinned URL, SHA-256 and per-user target; installs nothing
  install_wezterm.py --declined         print the saved text for a person who declines the install
  install_wezterm.py --yes [--from FILE] [--os OS] [--replace]
                                        install the pin for this OS, after the person agreed: download the pinned file
                                        (or take FILE), refuse it unless its SHA-256 is the pin, then put it in the
                                        per-user target. Without --yes it prints the plan and installs nothing

Per-user targets: macOS `~/Applications/WezTerm.app`; Windows `%LOCALAPPDATA%\\Programs\\WezTerm`; Linux
`$XDG_DATA_HOME/wezterm/WezTerm-<release>.AppImage` (default `~/.local/share`). PATH, shell profiles, the registry and
every other file stay as they are: the script prints the path to start it by. A file whose SHA-256 is not the pin is
deleted and nothing is created; a target that already exists is left alone unless --replace.

The pin: RELEASE and PINS below, the newest stable release at the time, each SHA-256 from the release's own `.sha256`
asset (https://github.com/wezterm/wezterm/releases/tag/20240203-110809-5046fc22). Moving it: take the release tag and the
three assets' `.sha256` files.

Exit codes: 0 installed (or --plan, --declined), 1 download, checksum or extraction error, 2 a bad argument or an OS or
CPU with no pinned file, 3 the target exists (nothing changed).
"""
import argparse
import hashlib
import os
import platform
import shutil
import stat
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

RELEASE = "20240203-110809-5046fc22"
BASE_URL = "https://github.com/wezterm/wezterm/releases/download/" + RELEASE + "/"
PINS = {
    "macos": {
        "file": "WezTerm-macos-" + RELEASE + ".zip",
        "sha256": "e77388cad55f2e9da95a220a89206a6c58f865874a629b7c3ea3c162f5692224",
    },
    "windows": {
        "file": "WezTerm-windows-" + RELEASE + ".zip",
        "sha256": "57e5d03b585303d81e8b8e96d1230362852eb39aca92b3b29c7a42cfb82f9ac4",
    },
    "linux": {
        "file": "WezTerm-" + RELEASE + "-Ubuntu20.04.AppImage",
        "sha256": "34010a07076d2272c4d4f94b5e0dae608a679599e8d729446323f88f956c60f0",
    },
}

TARGET_TEXT = {
    "macos": "~/Applications/WezTerm.app",
    "windows": "%LOCALAPPDATA%\\Programs\\WezTerm",
    "linux": "$XDG_DATA_HOME/wezterm/WezTerm-" + RELEASE + ".AppImage (default ~/.local/share)",
}

DECLINED ="""WezTerm is optional. Without it nothing in the kb changes: the chat pane still works.
kbmon, the live view of the kb, coord, sessions, query log and host, then runs by hand in any terminal:
  python3 _tools/kbmon.py
or Claude reads it for you when you ask, with:
  python3 _tools/kbmon.py --once
Install it later with: python3 _tools/install_wezterm.py --plan, then --yes."""


def host_os():
    return {"darwin": "macos", "win32": "windows"}.get(sys.platform, "linux")


def target(os_name):
    """The per-user path the pin installs to on `os_name`, read from the environment of this process."""
    home = Path(os.path.expanduser("~"))
    if os_name == "macos":
        return home / "Applications" / "WezTerm.app"
    if os_name == "windows":
        base = os.environ.get("LOCALAPPDATA") or str(home / "AppData" / "Local")
        return Path(base) / "Programs" / "WezTerm"
    data = os.environ.get("XDG_DATA_HOME") or str(home / ".local" / "share")
    return Path(data) / "wezterm" / ("WezTerm-" + RELEASE + ".AppImage")


def launcher(os_name):
    dest = target(os_name)
    if os_name == "macos":
        return dest / "Contents" / "MacOS" / "wezterm-gui"
    if os_name == "windows":
        return dest / "wezterm-gui.exe"
    return dest


def print_plan(os_names):
    for name in os_names:
        pin = PINS[name]
        print("%-8s %s" % (name, BASE_URL + pin["file"]))
        print("%-8s sha256 %s" % ("", pin["sha256"]))
        print("%-8s installs to %s" % ("", TARGET_TEXT[name]))


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url, dest):
    request = urllib.request.Request(url, headers={"User-Agent": "it-ops-kb-install-wezterm"})
    with urllib.request.urlopen(request, timeout=60) as response, open(dest, "wb") as out:
        shutil.copyfileobj(response, out, 1 << 20)


def unzip(archive, into):
    """Extract `archive` under `into`, refusing a member that would leave it, and keep the execute bits."""
    root = Path(into).resolve()
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            out = (root / info.filename).resolve()
            if out != root and root not in out.parents:
                raise ValueError("archive member outside the target: " + info.filename)
            if info.is_dir():
                out.mkdir(parents=True, exist_ok=True)
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(out, "wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
            mode = info.external_attr >> 16
            if mode & 0o111:
                out.chmod(stat.S_IMODE(mode) | stat.S_IRUSR | stat.S_IWUSR)


def only_dir(path):
    entries = [p for p in Path(path).iterdir() if p.is_dir()]
    if len(entries) != 1:
        raise ValueError("expected one folder in the archive, found %d" % len(entries))
    return entries[0]


def install(os_name, archive, dest):
    """Put the verified `archive` at `dest`. Nothing exists at `dest` or above it before this call is made."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if os_name == "linux":
        staged = dest.with_name(dest.name + ".part")
        shutil.copyfile(archive, staged)
        staged.chmod(0o755)
        os.replace(staged, dest)
        return
    with tempfile.TemporaryDirectory(prefix="wezterm-unzip-") as scratch:
        unzip(archive, scratch)
        top = only_dir(scratch)
        source = top / "WezTerm.app" if os_name == "macos" else top
        if not source.is_dir():
            raise ValueError("the archive holds no " + source.name)
        shutil.copytree(source, dest, symlinks=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Install the pinned WezTerm release for this user.")
    parser.add_argument("--plan", action="store_true", help="print the pinned URL, SHA-256 and target; install nothing")
    parser.add_argument("--declined", action="store_true", help="print the text for a person who declines")
    parser.add_argument("--yes", action="store_true", help="the person agreed: install")
    parser.add_argument("--os", choices=sorted(PINS), help="the OS whose pin to use (default: this host)")
    parser.add_argument("--from", dest="source", metavar="FILE", help="use this file instead of downloading the pin")
    parser.add_argument("--replace", action="store_true", help="replace a target that already exists")
    args = parser.parse_args(argv)

    if args.declined:
        print(DECLINED)
        return 0
    if args.plan:
        print_plan([args.os] if args.os else sorted(PINS))
        return 0

    os_name = args.os or host_os()
    if os_name != host_os():
        print("install_wezterm: --os %s is not this host (%s); --plan shows its pin" % (os_name, host_os()), file=sys.stderr)
        return 2
    if os_name == "linux" and platform.machine().lower() not in ("x86_64", "amd64"):
        print("install_wezterm: the pinned Linux file is x86_64 only, this host is %s" % platform.machine(), file=sys.stderr)
        return 2
    if not args.yes:
        print_plan([os_name])
        print("Nothing installed: ask the person, then run again with --yes.")
        return 2

    pin = PINS[os_name]
    dest = target(os_name)
    if os.path.lexists(dest) and not args.replace:
        print("install_wezterm: %s already exists; nothing changed (--replace overwrites it)" % dest, file=sys.stderr)
        return 3

    with tempfile.TemporaryDirectory(prefix="wezterm-dl-") as scratch:
        if args.source:
            archive = Path(args.source)
            if not archive.is_file():
                print("install_wezterm: no such file: " + args.source, file=sys.stderr)
                return 1
        else:
            archive = Path(scratch) / pin["file"]
            url = BASE_URL + pin["file"]
            print("Downloading " + url)
            try:
                download(url, archive)
            except OSError as exc:
                print("install_wezterm: download failed: %s" % exc, file=sys.stderr)
                return 1
        actual = sha256_of(archive)
        if actual != pin["sha256"]:
            print("install_wezterm: SHA-256 mismatch for %s: expected %s, got %s. Nothing installed." % (
                archive.name, pin["sha256"], actual), file=sys.stderr)
            return 1
        print("SHA-256 OK: " + actual)
        try:
            if os.path.lexists(dest):
                shutil.rmtree(dest) if dest.is_dir() and not dest.is_symlink() else dest.unlink()
            install(os_name, archive, dest)
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            print("install_wezterm: install failed: %s" % exc, file=sys.stderr)
            return 1
    print("Installed WezTerm %s at %s" % (RELEASE, dest))
    print("Start it with: " + str(launcher(os_name)))
    print("PATH, shell profiles and the registry are unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
