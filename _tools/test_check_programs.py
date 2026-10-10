"""The check-program allowlist: an item's checks and a bug's repro are data an agent or a merge can write, so only
python3 on a _tools/ script (or inline code) may run, and drift's detector runs only its read-only scripts. A refused
command is reported and never started. Also here: check.py's refusal of a kb citation in a tool's comment that a
fact inserted above has moved."""
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

import bl_base
import bl_intake
import check
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


def test_run_check_exit_code_is_the_result():
    code = "import sys; sys.exit(3)"
    ok, got, _ = bl_base.run_check(".", {"run": [sys.executable, "-c", code], "exit": 3})
    assert ok and got == 3
    ok, got, _ = bl_base.run_check(".", {"run": [sys.executable, "-c", code]})
    assert not ok and got == 3


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
               ["git", "push", "origin", "HEAD:main"]]
    allowed = [["python3", "_tools/check.py"], ["python3", "-c", "import sys; sys.exit(0 if sys.argv else 1)"]]
    assert b("new", "epic", "--title", "Epic", "--goal", "outcome")[0] == 0
    epic = next(w for w in b("list")[1].split() if w.startswith("EP-"))
    args = ["new", "story", "--title", "Story", "--parent", epic, "--goal", "g", "--touch", "src/**"]
    for argv in refused + allowed:
        args += ["--check", shlex.join(argv)]
    assert b(*args)[0] == 0
    code, out = b("check")
    assert code == 1 and f"errors={len(refused)} " in out
    assert out.count("is refused") == len(refused)
    assert not marker.exists()


def test_check_names_code_kb_citations_that_a_fact_inserted_above_has_moved(tmp_path):
    kb = tmp_path / "kb"
    (kb / "fx" / "api").mkdir(parents=True)
    (kb / "fx" / "_root.md").write_text("---\nroot: fx\n---\n", encoding="utf-8")
    (kb / "_self").mkdir()
    (kb / "_self" / "rules.md").write_text("Rule one.\n\nRule two.\n", encoding="utf-8")
    article = ["---", "topic: api/prices", "---", "", "## Facts",
               "- Sonnet 5.5 costs $2 per MTok of input. [DOC S1]", "- Haiku 4.5 costs $1 per MTok of input. [DOC S1]"]
    art = kb / "fx" / "api" / "prices.md"
    art.write_text("\n".join(article) + "\n", encoding="utf-8")
    tools = tmp_path / "_tools"
    tools.mkdir()
    cite = "kb/fx/api/prices.md"
    (tools / "price.py").write_text(
        f'"""Prices ({cite}:7 "Haiku 4.5")."""\n'
        f'PRICE = {{"sonnet": 2.0}}  # {cite}:6 "Sonnet 5.5 costs $2"\n'
        f'# {cite}:6-7 "Haiku 4.5 costs" and :7 "Haiku 4.5", but {cite}:5 "Facts" is a heading\n'
        f'FIXTURE = "{cite}:99 \\"nothing\\""\n'
        f'# {cite}:6 "Sonnet 5" is not Sonnet 5.5; kb/fx/gone.md:1 is no file; kb/_self/rules.md:2 is blank\n',
        encoding="utf-8")
    got = check.code_citation_errors(tmp_path)
    assert [e.split(" cites ")[1].split(",")[0] for e in got] == [
        f'{cite}:5 "Facts"', f'{cite}:6 "Sonnet 5"', "kb/fx/gone.md:1", "kb/_self/rules.md:2"], got
    assert all(e.startswith("_tools/price.py:") for e in got)
    art.write_text("\n".join([*article[:5], "- A fact inserted above. [DOC S1]", *article[5:]]) + "\n", encoding="utf-8")
    moved = [e.split(" cites ")[1].split(",")[0] for e in check.code_citation_errors(tmp_path)]  # :6 holds the new fact
    assert f'{cite}:6 "Sonnet 5.5 costs $2"' in moved and moved.count(f'{cite}:7 "Haiku 4.5"') == 2, moved


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


def test_drift_never_runs_the_whole_suite(tmp_path, monkeypatch):
    whole = [["python3", "_tools/tests.py"], ["python3", "-m", "pytest"], ["python3", "_tools/tests.py", "-n", "2"]]
    part = ["python3", "_tools/tests.py", "-k", "check_programs"]
    assert all(bl_intake.heavy_check({"run": run}) for run in whole)
    assert not bl_intake.heavy_check({"run": part})
    drift, started, ids = drift_run(monkeypatch, tmp_path, [*whole, part])
    assert started == [part]
    assert drift.heavy == sorted(ids[:3]) and not drift.refused
