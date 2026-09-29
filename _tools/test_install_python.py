"""Tests of _tools/install-python.ps1, the pinned python.org installer for a Windows clone without Python
(`python3 _tools/tests.py -k install_python`).

  test_pin_matches_the_project      every OS: the pinned version's minor is .python-version's, both SHA-256 pins are
                                    64 hex digits (planted: a pin text with a short hash is refused)
  test_uv_pin_is_complete           every OS: the uv pin names a version and a 64-hex SHA-256 per architecture, and the
                                    script downloads from uv's official GitHub release
  test_conflicts_stop_before_any_download
                                    Windows: a planted PYTHONHOME and a foreign python3.exe in the target folder stop
                                    the script with exit 3 and a CONFLICT line each, and nothing is downloaded. It runs
                                    with -DownloadOnly into an empty folder, so a preflight that misses them could at
                                    worst download there, never install.
  test_uv_conflicts_stop_before_any_download
                                    Windows: a foreign uv.exe in %USERPROFILE%\.local\bin (the install would replace
                                    it) and one in %USERPROFILE%\.cargo\bin stop the script the same way.
"""
import os, re, shutil, subprocess

import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
KB = os.path.dirname(TOOLS)
SCRIPT = os.path.join(TOOLS, "install-python.ps1")
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")


def pin(text, name="Pin"):
    """(version, {arch: sha256}) of the script's $Pin (or $UvPin) block."""
    text = re.search(rf"^\${name} = @\{{.*?^\}}", text, re.M | re.S).group(0)
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


def test_uv_pin_is_complete():
    with open(SCRIPT, encoding="utf-8") as f:
        text = f.read()
    version, hashes = pin(text, "UvPin")
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), version
    assert sorted(hashes) == ["amd64", "arm64"] and all(re.fullmatch(r"[0-9a-f]{64}", h) for h in hashes.values()), hashes
    assert "https://github.com/astral-sh/uv/releases/download/" in text


def run_script(tmp_path, env, *args):
    out = tmp_path / "out"
    out.mkdir()
    p = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", SCRIPT,
                        "-DownloadOnly", "-OutDir", str(out), "-Arch", "amd64", *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env={**os.environ, **env}, timeout=300)
    said = p.stdout + p.stderr
    return p.returncode, said, [ln for ln in said.splitlines() if ln.strip().startswith("CONFLICT")], list(out.iterdir())


@pytest.mark.skipif(os.name != "nt" or not POWERSHELL, reason="the script runs on Windows only")
def test_user_path_keeps_its_variables():
    """Add-UserPathDir, run from the script's own text on a scratch HKCU key: a %VAR% entry stays unexpanded, the
    value stays ExpandString, and a second call adds nothing. ([Environment]::SetEnvironmentVariable would write the
    expanded text as a plain string.)"""
    with open(SCRIPT, encoding="utf-8") as f:
        text = f.read()
    funcs = text[text.index("function Test-SameDir"):text.index("\n# Every python.exe")]
    sub = "Software\\it-ops-kb-test-" + os.urandom(4).hex()
    ps = funcs + f"""
$sub = '{sub}'
$k = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($sub)
$k.SetValue('Path', '%SystemRoot%\\kb-a;C:\\kb-b', [Microsoft.Win32.RegistryValueKind]::ExpandString)
$k.Close()
try {{
  Add-UserPathDir 'C:\\kb-new' $sub | Out-Null
  Add-UserPathDir 'C:\\kb-new\\' $sub | Out-Null
  $k = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($sub)
  $k.GetValue('Path', '', [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
  $k.GetValueKind('Path')
  $k.Close()
}} finally {{
  [Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($sub, $false)
}}
"""
    p = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    said = [ln for ln in p.stdout.split("\n") if ln.strip() and not ln.startswith("Added ")]
    assert [ln.strip() for ln in said] == ["%SystemRoot%\\kb-a;C:\\kb-b;C:\\kb-new", "ExpandString"], p.stdout + p.stderr
    assert p.stdout.count("Added ") == 1, "the second call finds the folder and adds nothing"


@pytest.mark.skipif(os.name != "nt" or not POWERSHELL, reason="the script runs on Windows only")
def test_uv_conflicts_stop_before_any_download(tmp_path):
    home = tmp_path / "home"
    for rel in (".local/bin", ".cargo/bin"):
        (home / rel).mkdir(parents=True)
        (home / rel / "uv.exe").write_bytes(b"not uv")
    rc, said, conflicts, downloaded = run_script(tmp_path, {"USERPROFILE": str(home)})
    assert rc == 3, said
    assert any(str(home / ".local" / "bin" / "uv.exe") in ln and "replace" in ln for ln in conflicts), said
    assert any(str(home / ".cargo" / "bin" / "uv.exe") in ln for ln in conflicts), said
    assert downloaded == [], "nothing is downloaded when the preflight finds a conflict"


@pytest.mark.skipif(os.name != "nt" or not POWERSHELL, reason="the script runs on Windows only")
def test_conflicts_stop_before_any_download(tmp_path):
    local = tmp_path / "LocalAppData"
    with open(SCRIPT, encoding="utf-8") as f:
        minor = "".join(pin(f.read())[0].split(".")[:2])
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
