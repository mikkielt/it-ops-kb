"""Which tests.py runs take the host lock and which record a full run: named test files without -k are a cheap
targeted run (no lock, no per-file full-run times) up to NAMED_FILES_LOCK_FREE files, more is a full run; a bare run,
a -k run and a named directory keep their behaviour."""
import os

import ql_capture
import tests as tests_py

FILE = os.path.join("_tools", "test_kb_http.py")


def _setup(monkeypatch, tmp_path):
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(tmp_path))
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(tests_py, "worker_count", lambda args, others=None: 4)


def _full_flags(monkeypatch, runs):
    """The `full_files` flag record_run passes for each of `runs` (a list of (mode, args)), with no row written."""
    seen = []
    monkeypatch.setattr(tests_py, "inside_test", lambda: False)
    monkeypatch.setattr(tests_py, "run_fields",
                        lambda mode, entries, total, workers, full, ms: seen.append(full) or {})
    monkeypatch.setattr(ql_capture, "record", lambda *a, **k: None)
    entries = [{"exit": 0, "files": {}}]
    for mode, args in runs:
        tests_py.record_run(mode, entries, args, 5)
    return seen


def test_tests_py_named_file_no_lock(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert not tests_py.wants_host_lock([FILE, "-q"])
    assert not tests_py.wants_host_lock([FILE + "::test_x", "--tb", "short"])
    assert tests_py.named_files_only([FILE, "-q"])
    assert _full_flags(monkeypatch, [("full", [FILE, "-q"])]) == [False]


def test_tests_py_named_file_no_lock_bare_k_and_directory_keep_behaviour(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert tests_py.wants_host_lock([])
    assert tests_py.wants_host_lock(["-q"])
    assert not tests_py.wants_host_lock(["-k", "x"])
    assert tests_py.wants_host_lock(["_tools"])
    assert tests_py.wants_host_lock([FILE, "_tools"])  # a directory among the files is a full-scope run
    assert tests_py.wants_host_lock([FILE, "--changed"])
    assert not tests_py.named_files_only(["_tools"])
    assert _full_flags(monkeypatch, [("full", []), ("full", ["_tools"]), ("full", ["-k", "x"])]) == [True, True, False]


def test_tests_py_named_file_no_lock_value_options_are_not_paths():
    assert tests_py.path_args(["--basetemp", FILE, "-W", FILE, "--tb", FILE]) == []


def _recorded_modes(monkeypatch, tmp_path, argv):
    """The modes main hands record_run for `argv`, with pytest planted out."""
    _setup(monkeypatch, tmp_path)
    got = []
    monkeypatch.setattr(tests_py, "wants_host_lock", lambda a: False)
    monkeypatch.setattr(tests_py, "run_pytest", lambda a, report=None: 0)
    monkeypatch.setattr(tests_py, "record_run", lambda mode, *rest: got.append(mode))
    tests_py.main(argv)
    return got


def test_tests_py_named_files_mode_is_not_full(monkeypatch, tmp_path):
    for argv in ([FILE], [FILE, "-q"], [FILE + "::test_x"], [FILE, os.path.join("_tools", "test_tests_lock.py")]):
        assert _recorded_modes(monkeypatch, tmp_path, argv) == ["files"], argv
    row = {"event": "test.run", "mode": "files", "ms": 1, "exit": 0}
    assert ql_capture.ops_problems(row) == []


def test_tests_py_named_files_mode_keeps_other_modes(monkeypatch, tmp_path):
    monkeypatch.delenv("KB_TESTS_FAST", raising=False)  # the sync gate runs the suite with it set
    assert _recorded_modes(monkeypatch, tmp_path, []) == ["full"]
    assert _recorded_modes(monkeypatch, tmp_path, ["_tools"]) == ["full"]
    monkeypatch.setenv("KB_TESTS_FAST", "1")
    assert _recorded_modes(monkeypatch, tmp_path, []) == ["fast"]


def _many_files(n):
    """`n` distinct existing test files, as a shell glob would hand them over."""
    import glob
    files = sorted(glob.glob(os.path.join(tests_py.TOOLS, "test_*.py")))
    assert len(files) >= n
    return files[:n]


def test_tests_py_named_files_glob_takes_lock(monkeypatch, tmp_path):
    for name in ("KB_TESTS_FAST", "KB_TEST_WORKERS", "KB_HOST_LOCK_DIR"):
        monkeypatch.delenv(name, raising=False)  # the sync gate runs the suite with KB_TESTS_FAST=1
    _setup(monkeypatch, tmp_path)
    few = _many_files(tests_py.NAMED_FILES_LOCK_FREE)
    many = _many_files(tests_py.NAMED_FILES_LOCK_FREE + 1)
    assert not tests_py.wants_host_lock(few)
    assert tests_py.named_files_only(few)
    assert tests_py.wants_host_lock(many)
    assert not tests_py.named_files_only(many)
    assert tests_py.wants_host_lock(many + ["-q"])
    assert not tests_py.wants_host_lock(many + ["-k", "x"])  # -k stays lock free
    assert _full_flags(monkeypatch, [("full", many), ("full", few)]) == [True, False]
    assert _recorded_modes(monkeypatch, tmp_path, few) == ["files"]
    assert _recorded_modes(monkeypatch, tmp_path, many) == ["full"]
    monkeypatch.setenv("KB_TESTS_FAST", "1")
    assert _recorded_modes(monkeypatch, tmp_path, many) == ["fast"]
    assert _recorded_modes(monkeypatch, tmp_path, few) == ["files"]


def test_run_row_selects_nothing(monkeypatch, tmp_path):
    """BG-nf6gcqsz: a `-k` run is recorded as mode `keyword`, never `full` (with or without KB_TESTS_FAST), and the
    mode is one ops_problems accepts; the digest side is test_ql_report's test_run_row_selects_nothing_in_digest."""
    monkeypatch.delenv("KB_TESTS_FAST", raising=False)
    for argv in (["-k", "no_such_test_name"], ["-kfoo"], ["-q", "-k", "x"]):
        assert _recorded_modes(monkeypatch, tmp_path, argv) == ["keyword"], argv
    monkeypatch.setenv("KB_TESTS_FAST", "1")
    assert _recorded_modes(monkeypatch, tmp_path, ["-k", "x"]) == ["keyword"]
    assert ql_capture.ops_problems({"event": "test.run", "mode": "keyword", "ms": 1, "exit": 5}) == []
