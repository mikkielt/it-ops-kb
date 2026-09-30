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
    assert [f for f in testmap.select(["_tools/kb_http.py"])[0] if f != own] == ["_tools/test_kb_http.py"]


def test_a_test_file_change_selects_itself():
    assert testmap.select(["_tools/test_redact.py"])[0] == ["_tools/test_redact.py"]


def test_kb_content_selects_the_content_classes_only():
    sel, why = testmap.select(["kb/public/python/pytest.md", "kb/public/_sources.csv", "AGENTS.md"])
    assert sel == sorted(testmap.CONTENT_TESTS), sel
    assert all(r == "kb content: the content checks" for _, r in why)


def test_a_whole_file_absorbs_its_classes():
    sel, _ = testmap.select(["kb/public/python/pytest.md", "_tools/test_kb.py"])
    assert sel == ["_tools/test_kb.py"], sel


@pytest.mark.parametrize("path", ["_tools/conftest.py", "pyproject.toml", "uv.lock", "_tools/tests.py", "_tools/testmap.py",
                                  "somewhere/new.bin"])
def test_shared_setup_and_unknown_paths_select_everything(path):
    assert testmap.select([path])[0] == testmap.ALL


def test_backlog_items_and_the_query_log_store_select_no_test():
    assert testmap.select(["kb/_self/backlog/ST-x.json", "kb/_querylog/runs/2026/r.jsonl"])[0] == testmap.NONE


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
    monkeypatch.setattr(testmap, "changed", lambda rev: ["kb/_self/backlog/ST-x.json"])
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


def test_gate_without_a_base_runs_every_check():
    assert ran(None) == {"check", "fetch", "doc2query", "selfdoc", "backlog", "querylog"}
