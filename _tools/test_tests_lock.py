"""Which tests.py runs take the host lock and which record a full run: named test files without -k are a cheap
targeted run (no lock, no per-file full-run times); a bare run, a -k run and a named directory keep their behaviour."""
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
