"""The check-program allowlist: an item's checks and a bug's repro are data an agent or a merge can write, so only
python3 on a _tools/ script (or inline code) may run, and drift's detector runs only its read-only scripts. A refused
command is reported and never started."""
import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

import bl_base
import bl_intake
from conftest import requires_git

pytestmark = [pytest.mark.git, requires_git]

TOOL = str(Path(__file__).resolve().parent / "backlog.py")


def writer(tmp_path, name="marker"):
    """A script outside the clone that writes a marker file when it runs, and the marker's path."""
    marker = tmp_path / name
    script = tmp_path / "outside" / f"{name}.py"
    script.parent.mkdir(exist_ok=True)
    script.write_text(f"import pathlib; pathlib.Path({str(marker)!r}).write_text('ran')\n", encoding="utf-8")
    return script, marker


def test_backlog_check_refuses_programs_outside_the_allowlist(tmp_path):
    root = tmp_path / "clone"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)

    def b(*args):
        p = subprocess.run([sys.executable, TOOL, "--root", str(root), *args], cwd=root, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        return p.returncode, p.stdout + p.stderr

    _, marker = writer(tmp_path)  # a relative path in the items: an absolute one holds this host's user name
    refused = [["sh", "-c", "python3 ../outside/marker.py"],  # a shell string
               ["python3", "../outside/marker.py"],  # a script that leaves the clone
               ["python3", "_tools/../outside/x.py"],  # a path that climbs out of _tools/
               ["python3", "_tools/kbgit.py", "publish"],  # a form that pushes
               ["python3", "-I", "-c", "pass"],  # an interpreter flag in front of the code
               ["git", "push", "origin", "HEAD:main"]]
    allowed = [["python3", "_tools/check.py"], ["python3", "-c", "import sys; sys.exit(0 if sys.argv else 1)"]]
    assert b("new", "epic", "--title", "Epic", "--goal", "outcome")[0] == 0
    epic = next(w for w in b("list")[1].split() if w.startswith("EP-"))
    args = ["new", "story", "--title", "Story", "--parent", epic, "--goal", "g", "--touch", "src/**"]
    for argv in allowed:
        args += ["--check", shlex.join(argv)]
    code, out = b(*args)
    assert code == 0, out
    story = out.split()[2]
    files = next(root.rglob(f"{story}.json")).parent
    held = {p.name: p.read_text(encoding="utf-8") for p in files.iterdir()}
    for argv in refused:  # filing refuses what check refuses, with its reason, and writes nothing
        for filing in (["new", "story", "--title", "Refused", "--goal", "g", "--check", shlex.join(argv)],
                       ["set", story, "--add-check", shlex.join(argv)]):
            code, out = b(*filing)
            assert code == 2 and "check is refused: " in out, (filing, out)
    assert {p.name: p.read_text(encoding="utf-8") for p in files.iterdir()} == held
    code, out = b("new", "story", "--title", "Quote", "--goal", "g", "--check", "echo it's")
    assert code == 2 and "--check is not a command line" in out and "Traceback" not in out, out
    path = files / f"{story}.json"  # the item a merge brings: a file `new` and `set` would not have written
    item = json.loads(path.read_text(encoding="utf-8"))
    item["checks"] += [{"run": argv} for argv in refused]
    path.write_text(bl_base.canonical(item), encoding="utf-8")
    code, out = b("check")
    assert code == 1 and f"errors={len(refused)} " in out
    assert out.count("is refused") == len(refused)
    assert not marker.exists()


def drift_run(monkeypatch, tmp_path, runs):
    """passing_open over one planted item per `runs` entry, with check_result recording what would have started."""
    started = []
    found = [(f"BG-{n:08d}", [{"run": run}]) for n, run in enumerate(runs)]
    monkeypatch.setattr(bl_intake, "check_result", lambda root, c, t: started.append(c["run"]) or "pass")
    monkeypatch.setattr(bl_intake, "eligible", lambda root, items: found)
    monkeypatch.setattr(bl_intake, "rotation", lambda root: 0)
    monkeypatch.setattr(bl_intake, "read_cursor", lambda root: None)
    drift = bl_intake.Drift()
    bl_intake.passing_open(str(tmp_path), {}, 30, drift, 60)
    return drift, started, [i for i, _ in found]


def test_drift_runs_only_read_only_forms(tmp_path, monkeypatch):
    _, marker = writer(tmp_path)
    ok = ["python3", "_tools/check.py"]
    refused = [["sh", "-c", "python3 ../outside/marker.py"], ["python3", "-c", "pass"],
               ["python3", "../outside/marker.py"], ["python3", "_tools/kbgit.py", "sync", "--push"],
               ["python3", "_tools/backlog.py", "answer", "ST-aaaaaaaa", "x"], ["git", "push", "origin", "HEAD:main"]]
    drift, started, ids = drift_run(monkeypatch, tmp_path, [ok, *refused])
    assert started == [ok] and drift.ran == 1
    assert drift.refused == sorted(ids[1:]) and not drift.heavy and drift.passing == {ids[0]: 1}
    assert not marker.exists()
