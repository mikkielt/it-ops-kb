"""The sync gate keeps the whole output of a failed check (`python3 _tools/tests.py -k gate_keeps_failed_output`).

`kbgit.py sync` and `land` print the last 25 lines of a failed check; the whole output goes to a new file under
`_cache/gate`, whose path and count of FAILED and ERROR test ids the gate prints too, so a failure that scrolled out of
the tail, or one a retry would have overwritten, is still there. The gate runs here in this process over fake checks
(its `tool` replaced), the repository directory a temporary one.

  planted    a failing check of 60 lines with the failing test id on line 3: the file holds all 60, the tail shows
             the last 25; two failures give two files; a retry keeps the first file; files past the keep count are
             removed; a directory that cannot be written changes neither the exit nor the output but for one note
  sample     the count over a recorded pytest short summary
  land       a failed step's output is shown whole, the path line included
"""
import datetime, os, time
from pathlib import Path

import pytest

import bl_land
import kbgit
import kg_sync
from bl_base import Refused

# A recorded `pytest -q` run: two failures and an error in the short summary, a traceback above it.
PYTEST_SAMPLE = """\
E
==================================== ERRORS ====================================
___________________________ ERROR at setup of test_c ___________________________

    @pytest.fixture
    def broken():
>       raise RuntimeError("setup")
E       RuntimeError: setup

test_sample.py:11: RuntimeError
=================================== FAILURES ===================================
____________________________________ test_a ____________________________________

    def test_a():
>       assert 1 == 2
E       assert 1 == 2

test_sample.py:4: AssertionError
____________________________________ test_d ____________________________________

    def test_d():
>       assert "x" == "y"
E       AssertionError: assert 'x' == 'y'
E
E         - y
E         + x

test_sample.py:17: AssertionError
=========================== short test summary info ============================
FAILED test_sample.py::test_a - assert 1 == 2
FAILED test_sample.py::test_d - AssertionError: assert 'x' == 'y'
ERROR test_sample.py::test_c - RuntimeError: setup
2 failed, 1 passed, 1 error in 0.01s
"""


def sixty(failed_line=3, n=60):
    """N numbered lines of a check's output with the failing test id on line FAILED_LINE."""
    lines = [f"output line {i}" for i in range(1, n + 1)]
    if failed_line <= n:
        lines[failed_line - 1] = "FAILED test_widget.py::test_it_breaks - AssertionError: planted"
    return "\n".join(lines) + "\n"


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A gate over fake checks: `checks` maps a tool name to its (exit, output), any other tool passes. The
    repository directory is tmp_path, so the files land in tmp_path/_cache/gate."""
    for k in ("KB_SYNC_NO_TESTS", "KB_GATE_DONE"):
        monkeypatch.delenv(k, raising=False)
    checks = {}

    def tool(name, *args, env=None):
        return checks.get(name, (0, "ok\n"))
    monkeypatch.setattr(kg_sync, "KB", str(tmp_path))
    monkeypatch.setattr(kg_sync, "tool", tool)
    monkeypatch.setattr(kg_sync, "gate_paths", lambda _up: None)  # no path filter: every check runs
    monkeypatch.setattr(kbgit, "trailer_audit", lambda *_a, **_k: (0, 0, []))

    class World:
        dir = tmp_path / "_cache" / "gate"

        def gate(self, capsys):
            """(passed, stdout, stderr, the report dict) of one gate run."""
            capsys.readouterr()
            r = {"target": "origin"}
            ok = kbgit.gate(r, None)
            cap = capsys.readouterr()
            return ok, cap.out, cap.err, r

        def files(self):
            return sorted(self.dir.glob("*.txt")) if self.dir.exists() else []
    w = World()
    w.checks = checks
    return w


def printed_path(out):
    """The path the gate printed on its `whole output` line."""
    line = next(ln for ln in out.splitlines() if "whole output:" in ln)
    return Path(line.split("whole output: ", 1)[1].rsplit(" (", 1)[0])


def test_gate_keeps_failed_output_whole_in_a_file_and_prints_the_tail(world, capsys):
    """Planted: 60 lines, the failing id on line 3: the tail shows lines 36 to 60 only, the file all 60, and the path
    and the test id count are printed."""
    world.checks["tests.py"] = (1, sixty())
    ok, out, err, r = world.gate(capsys)
    assert not ok and err == ""
    assert "output line 60" in out and "output line 36" in out and "output line 35" not in out
    assert "test_it_breaks" not in out  # scrolled past the tail
    path = printed_path(out)
    assert path.parent == world.dir and path.name.endswith("-tests.py-fast.txt"), path
    assert path.read_text(encoding="utf-8") == sixty()
    assert path.read_text(encoding="utf-8").splitlines()[2].startswith("FAILED test_widget.py::test_it_breaks")
    assert f"whole output: {path} (1 test ids)" in out
    assert r["gate_outputs"] == [("tests.py (fast)", f"{path} (1 test ids)")]


@pytest.mark.parametrize("n", [1, 2, 24, 25, 26, 30, 50, 60, 75, 100, 250])
def test_gate_keeps_failed_output_for_any_length(world, capsys, n):
    """Whatever the length (shorter than the tail, its exact size, a multiple of it or not), the file is the whole output
    and the tail its last 25 lines."""
    text = sixty(failed_line=1, n=n)
    world.checks["check.py"] = (1, text)
    ok, out, _, _ = world.gate(capsys)
    assert not ok
    (only,) = world.files()
    assert only.read_text(encoding="utf-8") == text
    shown = out.split("--- check.py output (last lines)\n", 1)[1].split("\n--- check.py whole output", 1)[0].splitlines()
    assert shown == text.splitlines()[-25:]


def test_gate_keeps_failed_output_counts_failed_and_error_ids(world, capsys):
    """A recorded pytest summary holds two FAILED and one ERROR id; a non-pytest check holds none; a line that only
    mentions the word does not count."""
    world.checks["tests.py"] = (1, PYTEST_SAMPLE)
    world.checks["check.py"] = (1, "ERROR windows/laps.md cites S9\nthe test FAILED earlier\n  FAILED indented\n")
    world.checks["doc2query.py"] = (1, "stale: 3 articles\n")
    _, out, _, _ = world.gate(capsys)
    assert "tests.py (fast) whole output:" in out
    counts = {ln.split(" whole output")[0].split("--- ")[1]: ln.rsplit("(", 1)[1] for ln in out.splitlines()
              if ln.startswith("--- ") and "whole output:" in ln}
    assert counts == {"check.py": "1 test ids)", "doc2query.py stale": "0 test ids)", "tests.py (fast)": "3 test ids)"}
    planted = kg_sync.FAILED_ID.findall("passed 3\n")  # planted: a clean output has no id
    assert planted == []


def test_gate_keeps_failed_output_of_two_failures_in_two_files(world, capsys):
    """Two checks fail in one gate: each has its file, each the whole output of its own check."""
    world.checks["check.py"] = (1, "ERROR first problem\n" + "x\n" * 40)
    world.checks["tests.py"] = (1, sixty())
    ok, out, _, _ = world.gate(capsys)
    assert not ok
    files = world.files()
    assert len(files) == 2 and len({f.name for f in files}) == 2
    by = {f.name.split("-", 2)[2]: f.read_text(encoding="utf-8") for f in files}
    assert by == {"check.py.txt": "ERROR first problem\n" + "x\n" * 40, "tests.py-fast.txt": sixty()}


def test_gate_keeps_failed_output_on_a_retry(world, capsys):
    """A second run of the gate (a retry) writes a second file and leaves the first as it was, in the same second
    too: the earlier text is never lost."""
    world.checks["tests.py"] = (1, sixty())
    world.gate(capsys)
    (first,) = world.files()
    before = first.read_bytes()
    world.checks["tests.py"] = (1, "FAILED test_other.py::test_two - planted\n")
    world.gate(capsys)
    files = world.files()
    assert len(files) == 2 and first in files and first.read_bytes() == before
    (second,) = [f for f in files if f != first]
    assert second.read_text(encoding="utf-8") == "FAILED test_other.py::test_two - planted\n"


def test_gate_keeps_failed_output_never_overwrites_in_one_second(world, capsys, monkeypatch):
    """With the clock frozen, many retries still write one file each: the counter in the name keeps them apart."""
    class Frozen:  # kg_sync's datetime module, at one instant
        timezone = datetime.timezone

        class datetime:  # noqa: N801 - the module's own name
            @staticmethod
            def now(tz=None):
                return datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=tz)
    monkeypatch.setattr(kg_sync, "datetime", Frozen)
    monkeypatch.setattr(kg_sync, "GATE_KEEP", 100)
    for i in range(12):
        world.checks["tests.py"] = (1, f"FAILED a{i} - b\n")
        world.gate(capsys)
        assert len(world.files()) == i + 1
    assert {f.name.split("-")[0] for f in world.files()} == {"20260101T120000Z"}
    assert sorted(f.read_text(encoding="utf-8") for f in world.files()) == sorted(f"FAILED a{i} - b\n" for i in range(12))


@pytest.mark.parametrize("have", [0, 9, 10, 11, 14, 25])
def test_gate_keeps_failed_output_removes_the_oldest_beyond_the_keep_count(world, capsys, have):
    """The newest GATE_KEEP files stay, the older ones go, whatever the count that was there; the new file stays."""
    world.dir.mkdir(parents=True)
    now = time.time()
    old = []
    for i in range(have):
        f = world.dir / f"2020010{i % 10}T000000Z-{i:03d}-check.py.txt"
        f.write_text(f"old {i}\n", encoding="utf-8")
        os.utime(f, (now - 1000 + i, now - 1000 + i))  # file i is older than file i + 1
        old.append(f)
    world.checks["tests.py"] = (1, "FAILED a - b\n")
    world.gate(capsys)
    kept = world.files()
    assert len(kept) == min(have + 1, kg_sync.GATE_KEEP)
    survivors = old[max(0, have - (kg_sync.GATE_KEEP - 1)):]
    assert {f.name for f in kept} - {f.name for f in survivors} and set(survivors) <= set(kept)
    assert any(f.read_text(encoding="utf-8") == "FAILED a - b\n" for f in kept)


def test_gate_keeps_failed_output_when_the_directory_cannot_be_written(world, capsys, tmp_path):
    """Planted: `_cache` is a file, so the directory cannot be made. The exit and the printed output are those of a
    gate that wrote its file, but for the path line, and stderr has one note."""
    world.checks["tests.py"] = (1, sixty())
    ok_w, out_w, err_w, _ = world.gate(capsys)
    for f in world.files():
        f.unlink()
    (tmp_path / "_cache" / "gate").rmdir()
    (tmp_path / "_cache").rmdir()
    (tmp_path / "_cache").write_text("not a directory\n", encoding="utf-8")
    ok_n, out_n, err_n, r = world.gate(capsys)
    assert ok_n == ok_w is False
    assert err_w == "" and err_n.startswith("note: could not keep the output of tests.py (fast)")
    assert len(err_n.splitlines()) == 1
    assert out_n == "\n".join(ln for ln in out_w.splitlines() if "whole output:" not in ln) + "\n"
    assert r["gate_outputs"] == []


def test_gate_keeps_failed_output_leaves_a_passing_gate_alone(world, capsys):
    """No failed check, no file and no path line."""
    ok, out, err, _ = world.gate(capsys)
    assert ok and "whole output" not in out and err == "" and world.files() == []


def test_gate_keeps_failed_output_path_survives_the_land_display(tmp_path, capsys, monkeypatch):
    """land shows a failed step whole (a passing step's last 30 lines only), so the path line the sync prints before
    its report, far above the last 30 lines, is in land's output. Planted: the same output from a passing step is cut."""
    script = tmp_path / "step.py"
    script.write_text(
        "import sys\n"
        "print('--- tests.py (changed) whole output: _cache/gate/20260101T000000Z-001-tests.py-changed.txt (4 test ids)')\n"
        "print('\\n'.join(f'line {i}' for i in range(80)))\n"
        "sys.exit(int(sys.argv[1]))\n", encoding="utf-8")
    monkeypatch.setattr(bl_land, "ops_mark", lambda *_a, **_k: None)
    monkeypatch.setitem(bl_land.LAND_OPS, "exit", 0)  # land_run records the step's exit there
    with pytest.raises(Refused, match="land stopped at step kbgit.py sync --push"):
        bl_land.land_run(tmp_path, "kbgit.py sync --push", [str(script), "1"])
    out = capsys.readouterr().out
    assert "(4 test ids)" in out and "line 79" in out
    bl_land.land_run(tmp_path, "kbgit.py sync --push", [str(script), "0"])
    out = capsys.readouterr().out
    assert "(4 test ids)" not in out and "line 79" in out  # planted: a step that passed shows the tail only
