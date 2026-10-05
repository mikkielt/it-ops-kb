"""testmap.py (which tests a change can break), tests.py --changed, and the path-driven checks of kbgit.py's gate.
Each lane has a planted change; `python3 _tools/tests.py -k testmap`."""
import os

import pytest

import kg_sync
import testmap
import tests as tests_py


@pytest.fixture(autouse=True)
def fresh_graph():
    testmap.graph.cache_clear()
    yield
    testmap.graph.cache_clear()


def test_a_tool_change_selects_the_test_files_that_reach_it():
    sel, _ = testmap.select(["_tools/kbingest.py"])
    assert "_tools/test_kbingest.py" in sel and "_tools/test_kb_http.py" not in sel, sel
    own = "_tools/test_testmap.py"  # names every tool it plants, so it reaches them too
    assert [f for f in testmap.select(["_tools/kb_http.py"])[0] if f != own] ==         sorted(["_tools/test_kb_http.py", testmap.LEAKS, testmap.TOOLS_MAP] + testmap.TOOL_SCANS)


def test_a_test_file_change_selects_itself():
    assert testmap.select(["_tools/test_redact.py"])[0] == [testmap.LEAKS, "_tools/test_redact.py", testmap.TOOLS_MAP]


def test_testmap_selects_tools_map_for_any_tool(monkeypatch):
    """Planted: a change to a tool module no test imports, a test file and a runner each select the class that checks
    selfdoc's tools map, and not the whole of test_selfdoc.py; without the declaration the tool and the runner miss it."""
    assert testmap.TOOLS_MAP == "_tools/test_selfdoc.py::TestSelfdocToolsMap"
    assert testmap.TOOLS_MAP in testmap.select(["_tools/kbroot.py"])[0]
    name = "zz_" + "planted"  # built at run time: a literal would make this file reach it
    monkeypatch.setattr(testmap, "graph", lambda: ({"test_x.py": {name}}, {name: set()}))
    for path in ("_tools/test_kb_mcp.py", "_tools/stress_test.py", f"_tools/{name}.py"):
        sel, _ = testmap.select([path])
        assert testmap.TOOLS_MAP in sel and "_tools/test_selfdoc.py" not in sel, (path, sel)
    monkeypatch.setattr(testmap, "TOOLS_MAP", "_tools/test_none.py::Gone")
    for path in ("_tools/test_kb_mcp.py", "_tools/stress_test.py", f"_tools/{name}.py"):
        assert "_tools/test_selfdoc.py::TestSelfdocToolsMap" not in testmap.select([path])[0], path


def test_a_changed_selfdoc_test_file_runs_the_whole_file():
    sel, _ = testmap.select(["_tools/test_selfdoc.py"])
    assert "_tools/test_selfdoc.py" in sel and testmap.TOOLS_MAP not in sel, sel


def test_kb_content_selects_the_content_classes_only():
    sel, why = testmap.select(["kb/public/python/pytest.md", "kb/public/_sources.csv", "AGENTS.md"])
    assert sel == sorted(testmap.CONTENT_TESTS), sel
    assert all(r == "kb content: the content checks" for _, r in why)


def test_testmap_selects_skill_section_headings_for_a_self_doc(monkeypatch):
    """Planted (BG-rskbmulj): a kb/_self doc change, where a skill's `selfdoc.py section` heading lives, selects the
    class holding the skill_section_headings tests, not test_selfdoc.py whole and not all; an article or a backlog
    item does not; without the declaration the doc change misses it."""
    assert testmap.SELF_SECTIONS == "_tools/test_selfdoc.py::TestSelfdocSection"
    with open(os.path.join(testmap.TOOLS, "test_selfdoc.py"), encoding="utf-8") as f:
        src = f.read()
    assert "class TestSelfdocSection:" in src and "def test_skill_section_headings_resolve" in src
    for path in ("kb/_self/backlog.md", "kb/_self/maintaining.md", "kb/_self/reports/test-suite-speed.md"):
        sel, _ = testmap.select([path])
        assert sel != testmap.ALL and testmap.SELF_SECTIONS in sel and "_tools/test_selfdoc.py" not in sel, (path, sel)
        assert set(testmap.CONTENT_TESTS) <= set(sel), (path, sel)
    for path in ("kb/public/python/pytest.md", "kb/_self/backlog/ST-x.json", "AGENTS.md"):
        assert testmap.SELF_SECTIONS not in testmap.select([path])[0], path
    monkeypatch.setattr(testmap, "SELF_SECTIONS", "_tools/test_none.py::Gone")
    assert "_tools/test_selfdoc.py::TestSelfdocSection" not in testmap.select(["kb/_self/backlog.md"])[0]


def test_a_whole_file_absorbs_its_classes():
    sel, _ = testmap.select(["kb/public/python/pytest.md", "_tools/test_kb_cohesion.py"])
    assert "_tools/test_kb_cohesion.py" in sel and not any(n.startswith("_tools/test_kb_cohesion.py::") for n in sel), sel


@pytest.mark.parametrize("path", ["_tools/conftest.py", "pyproject.toml", "uv.lock", "_tools/tests.py", "_tools/testmap.py",
                                  "somewhere/new.bin"])
def test_shared_setup_and_unknown_paths_select_everything(path):
    assert testmap.select([path])[0] == testmap.ALL


def test_backlog_items_and_the_query_log_store_select_only_the_leak_scan():
    assert testmap.select(["kb/_self/backlog/ST-x.json", "kb/_querylog/runs/2026/r.jsonl"])[0] == [testmap.LEAKS]


def test_no_change_selects_no_test():
    assert testmap.select([])[0] == testmap.NONE


def test_a_fixture_selects_the_tests_that_name_its_directory():
    sel, _ = testmap.select(["_tools/fixtures/querylog/e2e.json"])
    assert "_tools/test_querylog_e2e.py" in sel and "_tools/test_redact.py" not in sel, sel


def test_prose_is_not_a_dependency(tmp_path):
    """Planted: a docstring, an f-string and a message naming a script are prose; a bare name or a path is a use."""
    f = tmp_path / "x.py"
    f.write_text('"""Run python3 _tools/backlog.py check."""\n'
                 'import os\n'
                 'def g(n):\n'
                 '    print(f"see _tools/census.py {n}")\n'
                 '    print("then run python3 _tools/redact.py")\n'
                 '    return [os.path.join("_tools", "check.py"), "_tools/fetch.py"]\n', encoding="utf-8")
    testmap.strings_and_imports.cache_clear()
    assert testmap.direct_refs(str(f), set(testmap.modules())) == {"check", "fetch"}


def test_the_repository_has_no_orphan_module():
    assert testmap.orphans() == []


def test_a_module_no_test_reaches_is_an_orphan(monkeypatch):
    """Planted: a new tool module that no test file imports or runs."""
    real, name = testmap.modules(), "zz_" + "planted"  # built at run time: a literal would make this file reach it
    monkeypatch.setattr(testmap, "modules", lambda: real + [name])
    assert testmap.orphans() == [name]
    assert testmap.select([f"_tools/{name}.py"])[0] == testmap.ALL  # untested: everything runs


def test_tests_py_changed_runs_nothing_when_no_test_can_be_affected(monkeypatch, capsys):
    monkeypatch.setattr(testmap, "changed", lambda rev: [])
    monkeypatch.setattr(tests_py, "run_pytest", lambda *a, **k: pytest.fail("pytest must not start"))
    assert tests_py.main(["--changed", "HEAD"]) == 0
    assert "no test can be affected" in capsys.readouterr().out


def test_tests_py_changed_passes_the_selection_to_pytest(monkeypatch):
    monkeypatch.setattr(testmap, "changed", lambda rev: ["_tools/kb_http.py"])
    seen = {}
    monkeypatch.setattr(tests_py, "run_pytest", lambda args, **k: seen.setdefault("args", args) and 0)
    assert tests_py.main(["--changed", "origin/main", "-q"]) == 0
    targets = [a for a in seen["args"] if a.endswith(".py") or "::" in a]
    assert "test_kb_http.py" in [os.path.basename(t) for t in targets] and "-q" in seen["args"], seen
    assert not any(os.path.basename(t) == "test_backlog.py" for t in targets), seen


def test_tests_py_file_argument_runs_only_that_file(monkeypatch):
    seen = []
    monkeypatch.setattr(tests_py, "run_pytest", lambda args, **k: seen.append(args) or 0)
    assert tests_py.main(["_tools/test_testmap.py"]) == 0
    assert tests_py.TOOLS not in seen[-1] and "_tools/test_testmap.py" in seen[-1]
    assert tests_py.main(["-k", "x", "_tools/test_testmap.py", "_tools/test_backlog.py::Foo", "-q"]) == 0
    assert tests_py.TOOLS not in seen[-1] and "-q" in seen[-1] and "_tools/test_backlog.py::Foo" in seen[-1]
    assert tests_py.main(["-k", "testmap"]) == 0  # an -k value is no path: every test file
    assert tests_py.TOOLS in seen[-1]
    assert tests_py.main(["-q"]) == 0
    assert tests_py.TOOLS in seen[-1]


def test_tests_py_changed_treats_all_selected_tests_deselected_as_a_pass(monkeypatch):
    """Exit 5 (nothing left after -m) is a pass for a selection, never for the whole suite."""
    monkeypatch.setattr(testmap, "changed", lambda rev: ["_tools/kb_http.py"])
    monkeypatch.setattr(tests_py, "run_pytest", lambda args, **k: 5)
    assert tests_py.main(["--changed", "HEAD"]) == 0
    assert tests_py.main([]) == 5


def ran(paths):
    return {k for k, v in kg_sync.gate_needs(paths).items() if v}


def test_gate_content_change_runs_the_content_checks_only():
    assert ran(["kb/public/python/pytest.md"]) == {"check", "doc2query"}


def test_gate_backlog_item_runs_the_backlog_check_only():
    assert ran(["kb/_self/backlog/ST-x.json"]) == {"backlog"}


def test_gate_query_log_store_runs_its_check_only():
    assert ran(["kb/_querylog/runs/2026/r.jsonl"]) == {"querylog"}


def test_gate_tool_change_runs_check_and_selfdoc():
    assert ran(["_tools/testmap.py"]) == {"check", "selfdoc"}


def test_gate_pinned_artifact_runs_fetch():
    art = sorted(kg_sync.artifact_paths())[0]
    assert "fetch" in ran([art]) and "fetch" in ran(["kb/public/_sources.csv"])


def test_testmap_review_gaps_live_kb_tests_are_in_the_content_lane():
    """Planted (the sprint review's gaps): a kb article change selects every test that reads the live kb."""
    sel, _ = testmap.select(["kb/public/auth/kerberos.md"])
    for node in ("_tools/test_route.py::TestRouteEvalSet", "_tools/test_kb_mcp.py::TestKbServer",
                 "_tools/test_kbfacts_imports.py", "_tools/test_kb_cohesion.py::TestToolChecks", testmap.LEAKS):
        assert node in sel, (node, sel)


def test_testmap_review_gaps_repository_scans_reach_every_change():
    assert testmap.LEAKS in testmap.select(["kb/_self/backlog/ST-x.json"])[0]
    assert set(testmap.TOOL_SCANS) <= set(testmap.select(["_tools/kbroot.py"])[0])


def test_a_tool_change_selects_the_tests_that_read_every_module_by_glob(monkeypatch):
    """Planted: a module one test imports, and test_layout.py, which globs every module and so reaches none by the graph;
    the declared glob readers (TOOL_SCANS) select it, and without that declaration the graph alone misses it."""
    layout, name = "_tools/test_layout.py", "zz_" + "planted"  # built at run time: a literal would make this file reach it
    assert layout in testmap.TOOL_SCANS and layout in testmap.select(["_tools/kbfacts.py"])[0]
    monkeypatch.setattr(testmap, "graph", lambda: ({"test_x.py": {name}, "test_layout.py": set()}, {name: set()}))
    assert layout in testmap.select([f"_tools/{name}.py"])[0]
    monkeypatch.setattr(testmap, "TOOL_SCANS", [n for n in testmap.TOOL_SCANS if n != layout])
    assert layout not in testmap.select([f"_tools/{name}.py"])[0]


def test_testmap_review_gaps_a_deleted_test_file_selects_no_missing_path(tmp_path):
    gone = "_tools/test_" + "long_gone.py"  # built at run time, as a deleted file's name would arrive from git
    sel, why = testmap.select([gone])
    assert gone not in sel and why[0][1].startswith("a deleted test file"), (sel, why)


def test_testmap_review_gaps_settings_json_selects_the_router_test():
    assert "_tools/test_change_router.py" in testmap.select([".claude/settings.json"])[0]


def test_testmap_review_gaps_root_files_run_check_py():
    assert "check" in ran(["README.md"]) and "check" in ran(["AGENTS.md"])


def test_gate_without_a_base_runs_every_check():
    assert ran(None) == {"check", "fetch", "doc2query", "selfdoc", "backlog", "querylog", "dropped"}


JUNIT = """<?xml version="1.0"?><testsuites><testsuite>
<testcase classname="_tools.test_a.TestX" name="t1" time="1.5"/>
<testcase classname="_tools.test_a" name="t2" time="0.25"><failure message="a free text, with a path /x/y"/></testcase>
<testcase classname="_tools.test_b" name="t3" time="3"><skipped/></testcase>
<testcase classname="_tools.test_b" name="t4" time="2"/>
<testcase classname="free text here" name="t5" time="9"/>
<testcase classname="_tools.test_Weird-Name" name="t6" time="9"/>
</testsuite></testsuites>"""


@pytest.fixture
def spool(tmp_path, monkeypatch):
    import ql_capture
    monkeypatch.setattr(tests_py, "inside_test", lambda: False)  # the guard has its own test
    monkeypatch.setattr(ql_capture, "spool_dir", lambda: tmp_path / "spool")
    return tmp_path / "spool"


def ops_rows(spool):
    import json
    return [json.loads(ln) for f in spool.glob("*.jsonl") for ln in f.read_text(encoding="utf-8").splitlines()]


def test_ops_test_run_row_records_scope_counts_and_per_file_times(tmp_path, spool):
    import ql_capture
    xml = tmp_path / "r.xml"
    xml.write_text(JUNIT, encoding="utf-8")
    files = tests_py.junit_files(str(xml))
    assert files == {"test_a.py": [1750, 1, 1, 0], "test_b.py": [5000, 1, 0, 1]}, files  # no free text, no odd name
    row = tests_py.record_run("full", [{"exit": 1, "ms": 7, "files": files}], [], 4321)
    assert row is not None and ops_rows(spool) == [row]
    fields = {k: v for k, v in row.items() if k not in ("id", "ts", "surface", "v")}
    assert ql_capture.ops_problems(fields) == [], fields
    assert (fields["mode"], fields["ms"], fields["exit"], fields["selected"]) == ("full", 4321, 1, 2), fields
    assert (fields["passed"], fields["failed"], fields["skipped"]) == (2, 1, 1), fields
    assert fields["failed_files"] == ["test_a.py"] and fields["workers"] >= 1, fields
    assert fields["slow"] == [{"file": "test_b.py", "ms": 5000}, {"file": "test_a.py", "ms": 1750}], fields
    assert fields["files"] == [{"file": "test_a.py", "ms": 1750}, {"file": "test_b.py", "ms": 5000}], fields
    assert "files" not in tests_py.run_fields("changed", [{"exit": 0, "files": files}], None, 2, False, 1)
    assert "files" not in tests_py.record_run("full", [{"exit": 0, "ms": 1, "files": files}], ["-k", "x"], 1)


def test_ops_test_run_row_refuses_an_unknown_key_and_free_text(spool):
    """Planted: the row's closed shape, which the writer meets, refuses a key the event lacks and free text where a test
    file name goes (a node id, a message, a path)."""
    import ql_capture
    good = {"mode": "full", "ms": 1, "exit": 0}
    assert ql_capture.record("ops", event="test.run", **good) is not None
    for bad in ({"note": "free text"}, {"failed_files": ["test_a.py::TestX::test_t1"]},
                {"failed_files": ["a free text message"]}, {"slow": [{"file": "/abs/test_a.py", "ms": 1}]},
                {"mode": "everything"}):
        assert ql_capture.record("ops", event="test.run", **{**good, **bad}) is None, bad
        assert ql_capture.ops_problems({"event": "test.run", **good, **bad}), bad
    assert len(ops_rows(spool)) == 1


def test_ops_test_run_row_never_breaks_a_run(tmp_path, spool, monkeypatch):
    """Best effort: capture off, a failing writer and a run inside a test (a scenario clone's) raise nothing, and the
    last two write nothing."""
    import ql_capture
    entry = {"exit": 0, "ms": 1, "files": {"test_a.py": [1, 1, 0, 0]}}
    monkeypatch.setattr(ql_capture, "spool_dir", lambda: None)  # logging off
    assert tests_py.record_run("full", [entry], [], 1) is None
    monkeypatch.setattr(ql_capture, "spool_dir", lambda: tmp_path / "spool")

    def boom(*a, **k):
        raise OSError("disk")
    monkeypatch.setattr(ql_capture, "record", boom)
    assert tests_py.record_run("full", [entry], [], 1) is None
    monkeypatch.undo()
    monkeypatch.setattr(ql_capture, "spool_dir", lambda: tmp_path / "spool")
    assert tests_py.inside_test()  # this very test: pytest's variable, which a scenario clone's subprocess inherits
    assert tests_py.record_run("full", [entry], [], 1) is None and ops_rows(tmp_path / "spool") == []
    assert tests_py.junit_files(str(tmp_path / "missing.xml")) == {}
    (tmp_path / "bad.xml").write_text("<a", encoding="utf-8")
    assert tests_py.junit_files(str(tmp_path / "bad.xml")) == {}


# The host lock (tests.host_lock): a second full gate on one host waits for the first. Real processes, a lock directory of
# their own (KB_HOST_LOCK_DIR), so no test touches the host's lock.
HOLD = ("import sys, time, pathlib; sys.path.insert(0, sys.argv[1]); import tests\n"
        "stop = pathlib.Path(sys.argv[2])\n"
        "with tests.host_lock('holder', poll=0.05):\n"
        "    print('held', flush=True)\n"
        "    while not stop.exists():\n"
        "        time.sleep(0.05)\n")
TAKE = ("import sys; sys.path.insert(0, sys.argv[1]); import tests\n"
        "with tests.host_lock('second', poll=0.05):\n"
        "    print('got it', flush=True)\n")


def lock_env(tmp_path):
    return {**os.environ, "KB_HOST_LOCK_DIR": str(tmp_path / "lock")}


def spawn(code, tmp_path, *extra):
    import subprocess, sys
    return subprocess.Popen([sys.executable, "-c", code, tests_py.TOOLS, *extra], env=lock_env(tmp_path),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")


def test_host_test_lock_waits_second_run_waits_for_the_first(tmp_path):
    import time
    stop = tmp_path / "stop"
    first = spawn(HOLD, tmp_path, str(stop))
    try:
        assert first.stdout.readline().strip() == "held"
        held = (tmp_path / "lock" / tests_py.HOST_LOCK_NAME).read_text(encoding="utf-8")
        assert f"pid={first.pid}" in held and f"clone={tests_py.KB}" in held and "started=" in held
        second = spawn(TAKE, tmp_path)
        time.sleep(1)
        assert second.poll() is None  # still waiting while the first holds the lock
        stop.write_text("x", encoding="utf-8")
        out, _ = second.communicate(timeout=60)
        assert f"waiting for the host test lock held by pid {first.pid}" in out and "got it" in out
        assert first.wait(timeout=60) == 0
        assert not (tmp_path / "lock" / tests_py.HOST_LOCK_NAME).exists()  # released on exit
    finally:
        stop.write_text("x", encoding="utf-8")
        first.kill()
        first.wait()


def test_host_test_lock_waits_clears_a_stale_holder(tmp_path):
    import subprocess, sys
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    lock = tmp_path / "lock"
    lock.mkdir()
    (lock / tests_py.HOST_LOCK_NAME).write_text(f"pid={dead.pid}\nclone=/gone\nstarted=2000-01-01T00:00:00Z\n", encoding="utf-8")
    p = spawn(TAKE, tmp_path)
    out, _ = p.communicate(timeout=60)
    assert "clearing a stale host test lock" in out and "got it" in out and p.returncode == 0
    assert not (lock / tests_py.HOST_LOCK_NAME).exists()


def test_host_test_lock_waits_is_released_on_an_error(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(tmp_path))
    with pytest.raises(RuntimeError):
        with tests_py.host_lock(poll=0.01):
            assert (tmp_path / tests_py.HOST_LOCK_NAME).exists()
            raise RuntimeError("planted")
    assert not (tmp_path / tests_py.HOST_LOCK_NAME).exists()


def test_host_test_lock_waits_applies_to_full_and_many_worker_runs_only(monkeypatch):
    monkeypatch.setenv("KB_TEST_WORKERS", "4")  # the default count, not this host's load
    monkeypatch.setattr(tests_py, "inside_test", lambda: False)
    assert tests_py.wants_host_lock([]) and tests_py.wants_host_lock(["--changed", "-n", "4"])
    assert not tests_py.wants_host_lock(["--changed", "-n", "1"]) and not tests_py.wants_host_lock(["-n0"])
    assert not tests_py.wants_host_lock(["-k", "ruff"])
    monkeypatch.setattr(tests_py, "inside_test", lambda: True)
    assert not tests_py.wants_host_lock([])  # a run inside a test never takes the host's lock


def test_host_test_lock_waits_planted_failure_a_live_foreign_holder_is_not_cleared(tmp_path, monkeypatch):
    """The gate's planted failure: with the holder's pid alive and no release, a second run must not get the lock."""
    import threading
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(tmp_path))
    (tmp_path / tests_py.HOST_LOCK_NAME).write_text(f"pid={os.getpid()}\nclone=/other\nstarted=x\n", encoding="utf-8")
    got = []

    def second():
        with tests_py.host_lock(poll=0.02):
            got.append(1)

    t = threading.Thread(target=second, daemon=True)
    t.start()
    t.join(1)
    assert t.is_alive() and not got  # waiting, not cleared
    (tmp_path / tests_py.HOST_LOCK_NAME).unlink()  # the holder releases
    t.join(30)
    assert got


def dead_pid():
    import subprocess, sys
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    return dead.pid


def plant_stale_lock(tmp_path, monkeypatch):
    """A lock file of a pid that no longer runs, in a lock directory of the test's own."""
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(tmp_path))
    monkeypatch.setenv("KB_HOST_LOCK_GRACE", "60")
    lock = tmp_path / tests_py.HOST_LOCK_NAME
    lock.write_text(f"pid={dead_pid()}\nclone=/gone\nstarted=2000-01-01T00:00:00Z\n", encoding="utf-8")
    return lock


def two_waiters_on_one_stale_lock():
    """Waiter b judges the stale lock first and is held in the on_stale hook until waiter a has cleared it and holds the
    lock, then goes on to clear what it judged. Returns the most waiters inside the lock at once (threads, no host timing:
    a holds for a bounded wait that ends early when b gets in)."""
    import threading
    b_judged, a_in, both = threading.Event(), threading.Event(), threading.Event()
    guard = threading.Lock()
    inside, most, errors = [0], [0], []

    def hook(label):
        if label == "b":
            b_judged.set()
            a_in.wait(10)

    def waiter(label):
        try:
            with tests_py.host_lock(label, poll=0.02, on_stale=hook):
                with guard:
                    inside[0] += 1
                    most[0] = max(most[0], inside[0])
                    if inside[0] > 1:
                        both.set()
                if label == "a":
                    a_in.set()
                    both.wait(0.5)
                with guard:
                    inside[0] -= 1
        except Exception as e:  # noqa: BLE001 - reported by the test
            errors.append(e)

    b = threading.Thread(target=waiter, args=("b",), daemon=True)
    b.start()
    assert b_judged.wait(10)
    a = threading.Thread(target=waiter, args=("a",), daemon=True)
    a.start()
    a.join(30)
    b.join(30)
    assert not errors and not a.is_alive() and not b.is_alive()
    return most[0]


def test_host_test_lock_two_waiters_only_one_holds_a_stale_lock(tmp_path, monkeypatch):
    plant_stale_lock(tmp_path, monkeypatch)
    assert two_waiters_on_one_stale_lock() == 1
    assert not (tmp_path / tests_py.HOST_LOCK_NAME).exists()  # released


def test_host_test_lock_two_waiters_planted_failure_an_unconditional_unlink_lets_both_hold(tmp_path, monkeypatch):
    """The gate's planted failure: with the stale lock cleared by a plain unlink, the second waiter removes the first's
    fresh lock and both hold it."""
    import contextlib
    plant_stale_lock(tmp_path, monkeypatch)

    def unlink(path, judged):
        with contextlib.suppress(OSError):
            os.unlink(path)
        return True

    monkeypatch.setattr(tests_py, "clear_stale", unlink)
    assert two_waiters_on_one_stale_lock() == 2


def test_host_test_lock_two_waiters_clear_stale_leaves_a_lock_it_did_not_judge(tmp_path, monkeypatch):
    lock = tmp_path / tests_py.HOST_LOCK_NAME
    fresh = f"pid={os.getpid()}\nclone=/other\nstarted=x\n"
    lock.write_text(fresh, encoding="utf-8")
    assert tests_py.clear_stale(str(lock), "pid=1\n") is False  # judged another text: not claimed
    assert lock.read_text(encoding="utf-8") == fresh
    reads = []
    real = tests_py.read_lock

    def racing(path):  # the lock changes between the judgement and the claim: the first look still sees the old text
        reads.append(path)
        return "pid=1\n" if len(reads) == 1 else real(path)

    monkeypatch.setattr(tests_py, "read_lock", racing)
    assert tests_py.clear_stale(str(lock), "pid=1\n") is False  # claimed a lock it did not judge: put back
    assert lock.read_text(encoding="utf-8") == fresh and [f.name for f in tmp_path.iterdir()] == [lock.name]
    monkeypatch.setattr(tests_py, "read_lock", real)
    lock.write_text("pid=1\n", encoding="utf-8")
    assert tests_py.clear_stale(str(lock), "pid=1\n") is True and not lock.exists()  # judged and claimed: cleared
    assert tests_py.clear_stale(str(lock), "pid=1\n") is False  # nothing left to claim


def waiter_on_an_empty_lock(tmp_path, monkeypatch, grace):
    """An empty lock file (its holder created it and has not written yet) and a waiter on it; the waiter's thread and
    whether it got the lock within a moment."""
    import threading
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(tmp_path))
    monkeypatch.setenv("KB_HOST_LOCK_GRACE", grace)
    lock = tmp_path / tests_py.HOST_LOCK_NAME
    lock.write_text("", encoding="utf-8")
    got = []

    def waiter():
        with tests_py.host_lock(poll=0.02):
            got.append(1)

    t = threading.Thread(target=waiter, daemon=True)
    t.start()
    t.join(1)
    return lock, t, got


def test_host_test_lock_two_waiters_an_empty_lock_younger_than_the_grace_is_waited_on(tmp_path, monkeypatch):
    lock, t, got = waiter_on_an_empty_lock(tmp_path, monkeypatch, "60")
    assert t.is_alive() and not got and lock.exists()  # waiting, the file not cleared
    lock.write_text(f"pid={os.getpid()}\nclone=/other\nstarted=x\n", encoding="utf-8")  # the holder writes its record
    t.join(0.3)
    assert t.is_alive() and not got  # a live holder: still waited on
    lock.unlink()
    t.join(30)
    assert got


def test_host_test_lock_two_waiters_planted_failure_an_empty_lock_past_the_grace_is_cleared(tmp_path, monkeypatch):
    """The gate's planted failure: a grace of zero (the old behaviour) clears the empty lock at once."""
    lock, t, got = waiter_on_an_empty_lock(tmp_path, monkeypatch, "0")
    t.join(30)
    assert got and not t.is_alive()


def test_host_test_lock_two_waiters_an_empty_lock_older_than_the_grace_is_cleared(tmp_path, monkeypatch):
    """A holder that died before writing leaves an empty file: it is cleared once it is older than the grace."""
    import threading, time
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(tmp_path))
    monkeypatch.setenv("KB_HOST_LOCK_GRACE", "60")
    lock = tmp_path / tests_py.HOST_LOCK_NAME
    lock.write_text("", encoding="utf-8")
    old = time.time() - 3600
    os.utime(lock, (old, old))
    got = []

    def waiter():
        with tests_py.host_lock(poll=0.02):
            got.append(1)

    t = threading.Thread(target=waiter, daemon=True)
    t.start()
    t.join(30)
    assert got and not t.is_alive()


def test_workers_capped_env_override_wins_over_the_share(monkeypatch):
    monkeypatch.setenv("KB_TEST_WORKERS", "3")
    assert tests_py.default_workers(others=5, cpus=16) == 3 and tests_py.worker_count([], others=5) == 3
    monkeypatch.setenv("KB_TEST_WORKERS", "junk")  # not a number: the share applies
    assert tests_py.default_workers(others=1, cpus=16) == 8


def test_workers_capped_default_is_a_share_of_the_cpus_among_live_runs(monkeypatch):
    monkeypatch.delenv("KB_TEST_WORKERS", raising=False)
    assert tests_py.default_workers(others=0, cpus=6) == 6  # alone: every CPU up to the cap
    assert tests_py.default_workers(others=1, cpus=12) == 6 and tests_py.default_workers(others=3, cpus=12) == 3
    assert tests_py.worker_count([], others=2) == max(min((os.cpu_count() or 1) // 3, tests_py.DEFAULT_WORKER_CAP), 1)
    assert tests_py.xdist_args()[0] == "-n"


def test_workers_capped_explicit_n_wins_and_the_lock_follows_the_count(monkeypatch):
    monkeypatch.setenv("KB_TEST_WORKERS", "2")
    assert tests_py.worker_count(["-n", "5"]) == 5 and tests_py.worker_count(["-n7"]) == 7
    assert tests_py.worker_count(["-n", "auto"]) == (os.cpu_count() or 1)
    monkeypatch.setattr(tests_py, "inside_test", lambda: False)
    assert tests_py.wants_host_lock([])  # two workers: a full run takes the lock
    monkeypatch.setenv("KB_TEST_WORKERS", "1")
    assert not tests_py.wants_host_lock([]) and tests_py.wants_host_lock(["-n", "3"])


def test_workers_capped_never_below_one(monkeypatch):
    monkeypatch.delenv("KB_TEST_WORKERS", raising=False)
    assert tests_py.default_workers(others=99, cpus=4) == 1 and tests_py.default_workers(others=0, cpus=0) == 1
    monkeypatch.setenv("KB_TEST_WORKERS", "0")
    assert tests_py.default_workers(others=0, cpus=8) == 1
    assert tests_py.worker_count(["-n", "0"]) == 1


def test_workers_capped_counts_only_live_other_runs(tmp_path, monkeypatch):
    import subprocess, sys
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(tmp_path))
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    for pid in (os.getpid(), dead.pid):
        (tmp_path / f"{tests_py.RUN_PREFIX}{pid}").write_text("x", encoding="utf-8")
    (tmp_path / f"{tests_py.RUN_PREFIX}notapid").write_text("x", encoding="utf-8")
    monkeypatch.setattr(tests_py, "pid_alive", lambda pid: pid == os.getpid() or pid == 1)
    assert tests_py.live_runs() == 0 and not (tmp_path / f"{tests_py.RUN_PREFIX}{dead.pid}").exists()  # self is not "other"
    (tmp_path / f"{tests_py.RUN_PREFIX}1").write_text("x", encoding="utf-8")
    assert tests_py.live_runs() == 1
    monkeypatch.setattr(tests_py, "inside_test", lambda: False)
    with tests_py.run_registered():
        assert (tmp_path / f"{tests_py.RUN_PREFIX}{os.getpid()}").exists()
    assert not (tmp_path / f"{tests_py.RUN_PREFIX}{os.getpid()}").exists()


def test_workers_capped_planted_failure_a_one_per_cpu_default_is_caught(monkeypatch):
    """The gate's planted failure: were the default one worker per CPU whatever else runs, three other live runs on
    twelve CPUs would still get twelve workers; the share must give three."""
    monkeypatch.delenv("KB_TEST_WORKERS", raising=False)
    assert tests_py.default_workers(others=3, cpus=12) != 12


def test_testmap_select_bl_land_stays_under_the_bound():
    """ST-ufpxla7r: a change to bl_land.py selects fewer than 60 test files (it was 84 while ql_deliver imported the
    backlog facade, bl_ci took run_check from bl_land and a script a module only names was followed through its
    imports); a file that really imports bl_land, and one that imports the facade, are still selected."""
    sel, _ = testmap.select(["_tools/bl_land.py"])
    tests = [f for f in sel if os.path.basename(f).startswith("test_")]
    assert len(tests) < 60, len(tests)
    assert "_tools/test_bl_land.py" in sel and "_tools/test_backlog.py" in sel, sel


def test_testmap_a_script_a_module_names_is_reached_not_followed(monkeypatch):
    """Planted: kg_sync names backlog.py (the gate runs `backlog.py check`): a test of kg_sync reaches backlog, so a
    change to backlog.py selects it, but not bl_land, which only backlog imports; a test importing backlog reaches
    both."""
    reach, _ = testmap.graph()
    imported, scripts = testmap.split_refs(os.path.join(testmap.TOOLS, "kg_sync.py"), set(testmap.modules()))
    assert "backlog" in scripts and "backlog" not in imported
    assert "bl_land" in reach["test_bl_land.py"] and "bl_land" in reach["test_backlog.py"]
    only_sync = [t for t, r in reach.items() if "kg_sync" in r and "backlog" in r and "bl_land" not in r]
    assert only_sync, "a test that reaches backlog only as a script kg_sync names does not reach bl_land"


def test_gate_dropped_ids_file_runs_perfcheck_dropped():
    """ST-vxi7drn2: a change to the dropped test ids (or to perfcheck.py) runs `perfcheck.py dropped --since` in
    sync's gate, beside the checks that file's path runs anyway; another tool's change does not."""
    assert "dropped" in ran(["_tools/test_ids_dropped.txt"]) and "dropped" in ran(["_tools/perfcheck.py"])
    assert "dropped" not in ran(["_tools/kb_http.py"]) and "dropped" not in ran(["kb/public/python/pytest.md"])
