"""Tests of _tools/install-python.ps1, the pinned python.org installer for a Windows clone without Python
(`python3 _tools/tests.py -k install_python`).

  test_pin_matches_the_project      every OS: the pinned version's minor is .python-version's, both SHA-256 pins are
                                    64 hex digits (planted: a pin text with a short hash is refused)
  test_conflicts_stop_before_any_download
                                    Windows: a planted PYTHONHOME and a foreign python3.exe in the target folder stop
                                    the script with exit 3 and a CONFLICT line each, and nothing is downloaded. It runs
                                    with -DownloadOnly into an empty folder, so a preflight that misses them could at
                                    worst download there, never install.
"""
import os, re, shutil, subprocess

import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
KB = os.path.dirname(TOOLS)
SCRIPT = os.path.join(TOOLS, "install-python.ps1")
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")


def pin(text):
    """(version, {arch: sha256}) of the script's $Pin block."""
    version = re.search(r"^\s*Version\s*=\s*'([\d.]+)'", text, re.M).group(1)
    hashes = dict(re.findall(r"^\s*(amd64|arm64)\s*=\s*'([0-9a-fA-F]*)'", text, re.M))
    return version, hashes


def pin_problems(text, python_version):
    version, hashes = pin(text)
    bad = [] if version.split(".")[:2] == python_version.split(".")[:2] else [f"pinned {version}, project {python_version}"]
    bad += [f"{arch}: not a SHA-256" for arch, h in sorted(hashes.items()) if not re.fullmatch(r"[0-9a-fA-F]{64}", h)]
    return bad + ([] if set(hashes) == {"amd64", "arm64"} else [f"arches {sorted(hashes)}"])


def test_pin_matches_the_project():
    with open(SCRIPT, encoding="utf-8") as f:
        text = f.read()
    with open(os.path.join(KB, ".python-version"), encoding="utf-8") as f:
        project = f.read().strip()
    assert pin_problems(text, project) == []
    planted = re.sub(r"(amd64\s*=\s*')[0-9a-fA-F]{64}", r"\g<1>abc", text, count=1)
    assert pin_problems(planted, project) == ["amd64: not a SHA-256"]


@pytest.mark.skipif(os.name != "nt" or not POWERSHELL, reason="the script runs on Windows only")
def test_conflicts_stop_before_any_download(tmp_path):
    local = tmp_path / "LocalAppData"
    minor = "".join(pin(open(SCRIPT, encoding="utf-8").read())[0].split(".")[:2])
    target = local / "Programs" / "Python" / f"Python{minor}"
    target.mkdir(parents=True)
    (target / "python3.exe").write_bytes(b"not python")  # a python3.exe with no python.exe beside it
    out = tmp_path / "out"
    out.mkdir()
    env = {**os.environ, "LOCALAPPDATA": str(local), "PYTHONHOME": str(tmp_path / "elsewhere")}
    p = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", SCRIPT,
                        "-DownloadOnly", "-OutDir", str(out), "-Arch", "amd64"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=300)
    said = p.stdout + p.stderr
    conflicts = [ln for ln in said.splitlines() if ln.strip().startswith("CONFLICT")]
    assert p.returncode == 3, said
    assert any("PYTHONHOME" in ln for ln in conflicts), said
    assert any("python3.exe" in ln for ln in conflicts), said
    assert list(out.iterdir()) == [], "nothing is downloaded when the preflight finds a conflict"
