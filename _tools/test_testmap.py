"""testmap.py (which tests a change can break), tests.py --changed, and the path-driven checks of kbgit.py's gate.
Each lane has a planted change; `python3 _tools/tests.py -k testmap`."""
import os

import pytest

import kbgit
import testmap
import tests as tests_py


@pytest.fixture(autouse=True)
def fresh_graph():
    testmap.graph.cache_clear()
    yield
    testmap.graph.cache_clear()


def test_a_tool_change_selects_the_test_files_that_reach_it():
    sel, _ = testmap.select(["_tools/backlog.py"])
    assert "_tools/test_backlog.py" in sel and "_tools/test_kb_http.py" not in sel, sel
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


def test_tests_py_changed_treats_all_selected_tests_deselected_as_a_pass(monkeypatch):
    """Exit 5 (nothing left after -m) is a pass for a selection, never for the whole suite."""
    monkeypatch.setattr(testmap, "changed", lambda rev: ["_tools/kb_http.py"])
    monkeypatch.setattr(tests_py, "run_pytest", lambda args, **k: 5)
    assert tests_py.main(["--changed", "HEAD"]) == 0
    assert tests_py.main([]) == 5


def ran(paths):
    return {k for k, v in kbgit.gate_needs(paths).items() if v}


def test_gate_content_change_runs_the_content_checks_only():
    assert ran(["kb/public/python/pytest.md"]) == {"check", "doc2query"}


def test_gate_backlog_item_runs_the_backlog_check_only():
    assert ran(["kb/_self/backlog/ST-x.json"]) == {"backlog"}


def test_gate_query_log_store_runs_its_check_only():
    assert ran(["kb/_querylog/runs/2026/r.jsonl"]) == {"querylog"}


def test_gate_tool_change_runs_check_and_selfdoc():
    assert ran(["_tools/testmap.py"]) == {"check", "selfdoc"}


def test_gate_pinned_artifact_runs_fetch():
    art = sorted(kbgit.artifact_paths())[0]
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
    assert ran(None) == {"check", "fetch", "doc2query", "selfdoc", "backlog", "querylog"}
