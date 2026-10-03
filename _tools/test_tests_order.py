"""How tests.py hands out its loadscope units: the scopes with a class fixture first, and the plumbing that makes
the scheduler keep that order (conftest.longest_scopes_first, pytest_collection_modifyitems, --no-loadscope-reorder)."""
import os
import subprocess
import sys

import conftest
import tests as tests_py


def test_tests_py_longest_scopes_first_class_fixture_scopes_lead_by_size():
    units = [("a.py", 9, False), ("a.py::TestSmall", 2, True), ("b.py::TestBig", 5, True), ("c.py::TestPlain", 7, False)]
    want = ["b.py::TestBig", "a.py::TestSmall", "a.py", "c.py::TestPlain"]
    assert [u[0] for u in conftest.longest_scopes_first(units)] == want
    assert conftest.longest_scopes_first(units) == conftest.longest_scopes_first(list(reversed(units)))  # same in every worker


def test_tests_py_longest_scopes_first_scope_is_the_xdist_unit():
    assert conftest.scope_of("m.py::TestX::test_a") == "m.py::TestX" and conftest.scope_of("m.py::test_a") == "m.py"


def test_tests_py_longest_scopes_first_run_orders_a_collection(tmp_path):
    """A planted collection: a module of plain tests then a class with a class fixture. Under --no-loadscope-reorder
    the class comes first; without the option the file order stays."""
    (tmp_path / "conftest.py").write_text(
        "import importlib.util\nspec = importlib.util.spec_from_file_location('kb_conftest', %r)\n"
        "mod = importlib.util.module_from_spec(spec)\nspec.loader.exec_module(mod)\n"
        "pytest_collection_modifyitems = mod.pytest_collection_modifyitems\n" % os.path.join(tests_py.TOOLS, "conftest.py"),
        encoding="utf-8")
    (tmp_path / "test_a.py").write_text(
        "import pytest\n\n\ndef test_1(): pass\n\n\ndef test_2(): pass\n\n\ndef test_3(): pass\n\n\n"
        "class TestScenario:\n    @pytest.fixture(scope='class', autouse=True)\n    def built(self): yield\n\n"
        "    def test_x(self): pass\n", encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": tests_py.TOOLS}

    def collected(*extra):
        out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *extra],
                             cwd=tmp_path, env=env, capture_output=True, text=True).stdout
        return [ln.split("::", 1)[1] for ln in out.splitlines() if "::" in ln]

    assert collected("--no-loadscope-reorder") == ["TestScenario::test_x", "test_1", "test_2", "test_3"]
    assert collected()[0] == "test_1"  # the option off: collection order untouched


def test_tests_py_longest_scopes_first_loadscope_run_passes_no_reorder(monkeypatch):
    seen = []
    monkeypatch.setattr(tests_py, "pytest_cmd", lambda: ["pytest"])
    monkeypatch.setattr(tests_py, "record_run", lambda *a, **k: None)
    real = subprocess.run
    monkeypatch.setattr(tests_py.subprocess, "run", lambda cmd, **k: seen.append(cmd) or subprocess.CompletedProcess(cmd, 0)
                        if cmd[0] == "pytest" else real(cmd, **k))
    tests_py.run_pytest(["x"], dist="loadscope")
    tests_py.run_pytest(["x"], dist="load")
    assert "--no-loadscope-reorder" in seen[0] and "--no-loadscope-reorder" not in seen[1]


def test_tests_py_worker_count_default_is_the_cpu_share_capped_at_the_best_measured_count(monkeypatch):
    monkeypatch.delenv("KB_TESTS_FAST", raising=False)
    monkeypatch.delenv("KB_TEST_WORKERS", raising=False)
    cap = tests_py.DEFAULT_WORKER_CAP
    assert cap == 8
    pick = lambda cpus, others=0: tests_py.default_workers(others=others, cpus=cpus)
    assert pick(4) == 4 and pick(8) == 8  # alone: every CPU up to the cap
    assert pick(14) == cap and pick(64) == cap  # more CPUs than measured: the cap
    assert pick(14, others=1) == 7 and pick(64, others=1) == cap  # the share first, then the cap
    assert pick(1) == 1 and pick(4, others=9) == 1  # never below one
    monkeypatch.setenv("KB_TEST_WORKERS", "12")
    assert pick(4) == 12 and pick(64) == 12  # the override wins, even above the cap
    monkeypatch.setenv("KB_TEST_WORKERS", "junk")
    assert pick(14) == cap and pick(14, others=1) == 7  # not a number: the share applies
