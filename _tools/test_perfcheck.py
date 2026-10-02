"""Tests of perfcheck.py (kb/_self/tools.md): the id comparison that proves a speed-up lost no test, and the timed suite run.

TestPerfcheckIds      parsing pytest's collect-only output, the comparison and its planted failures (a dropped id fails, an
                      allow list names only what it names, an added id is listed and passes), the baseline file written
                      whole and sorted, and the exit codes; a fake collector stands in for pytest.
TestPerfcheckTime     a fake runner and clock: over the bound fails, a failed run fails, a run within the bound passes.
TestPerfcheckSelections  the two selections are the ones tests.py and stress_test.py run.
TestPerfcheckGit      (marker git) --base collects at a revision in a temporary worktree that is gone afterwards, over a
                      throwaway repository with its own pytest collection.
"""
import subprocess, sys
from pathlib import Path

import pytest

import perfcheck
from conftest import Repo, git_env, requires_git

HEAD_IDS = ["_tools/test_a.py::test_one", "_tools/test_a.py::TestB::test_two[x y]", "_tools/test_stress.py::test_three"]


def fake_collect(ids):
    return lambda root, cmd=None: sorted(ids)


def run_main(argv, ids, capsys):
    code = perfcheck.main(argv, collect=fake_collect(ids))
    return code, capsys.readouterr()


@pytest.fixture
def baseline(tmp_path):
    p = tmp_path / "base.txt"
    p.write_text("".join(i + "\n" for i in HEAD_IDS), encoding="utf-8", newline="\n")
    return p


class TestPerfcheckIds:
    def test_perfcheck_parse_keeps_ids_and_drops_summary_and_errors(self):
        out = ("_tools/test_a.py::test_one\n_tools\\test_b.py::TestB::test_two[x y]\n\n"
               "2/9 tests collected (7 deselected) in 0.5s\nERROR _tools/test_c.py - ImportError\n"
               "E   ImportError: no module\n=== warnings summary ===\n  _tools/w.py::x warning\n")
        assert perfcheck.parse_collected(out) == {"_tools/test_a.py::test_one", "_tools/test_b.py::TestB::test_two[x y]"}

    def test_perfcheck_same_ids_pass_and_print_a_summary(self, baseline, capsys):
        code, out = run_main(["ids", "--against", str(baseline)], HEAD_IDS, capsys)
        assert code == 0 and "0 missing, 0 added" in out.out

    def test_perfcheck_planted_dropped_test_id_fails(self, baseline, capsys):
        code, out = run_main(["ids", "--against", str(baseline)], HEAD_IDS[:1] + HEAD_IDS[2:], capsys)
        assert code == 1
        assert "MISSING: _tools/test_a.py::TestB::test_two[x y]" in out.out
        assert "MISSING: _tools/test_a.py::test_one" not in out.out

    def test_perfcheck_renamed_test_is_a_drop_and_an_addition(self, baseline, capsys):
        code, out = run_main(["ids", "--against", str(baseline)], [HEAD_IDS[0], "_tools/test_a.py::TestB::test_2", HEAD_IDS[2]], capsys)
        assert code == 1 and "added: _tools/test_a.py::TestB::test_2" in out.out and "MISSING" in out.out

    def test_perfcheck_added_ids_are_listed_and_pass(self, baseline, capsys):
        code, out = run_main(["ids", "--against", str(baseline)], HEAD_IDS + ["_tools/test_new.py::test_n"], capsys)
        assert code == 0 and "added: _tools/test_new.py::test_n" in out.out and "1 added" in out.out

    def test_perfcheck_allow_removed_names_only_what_it_names(self, baseline, tmp_path, capsys):
        allow = tmp_path / "allow.txt"
        allow.write_text("# why\n_tools/test_a.py::test_one\n\n", encoding="utf-8", newline="\n")
        argv = ["ids", "--against", str(baseline), "--allow-removed", str(allow)]
        code, out = run_main(argv, HEAD_IDS[1:], capsys)
        assert code == 0 and "removed (allowed): _tools/test_a.py::test_one" in out.out
        code, out = run_main(argv, HEAD_IDS[2:], capsys)  # a second id is gone and not named
        assert code == 1 and "MISSING: _tools/test_a.py::TestB::test_two[x y]" in out.out

    def test_perfcheck_ids_alone_prints_sorted_lines(self, capsys):
        code, out = run_main(["ids"], list(reversed(HEAD_IDS)), capsys)
        assert code == 0 and out.out.splitlines() == sorted(HEAD_IDS)

    def test_perfcheck_write_is_sorted_whole_and_converges(self, tmp_path, capsys):
        target = tmp_path / "b.txt"
        assert run_main(["ids", "--write", str(target)], list(reversed(HEAD_IDS)), capsys)[0] == 0
        first = target.read_bytes()
        assert first == "".join(i + "\n" for i in sorted(HEAD_IDS)).encode("utf-8") and b"\r" not in first
        assert run_main(["ids", "--write", str(target)], HEAD_IDS, capsys)[0] == 0
        assert target.read_bytes() == first and not list(tmp_path.glob("*.tmp"))
        assert run_main(["ids", "--write", str(target), "--against", str(target)], HEAD_IDS, capsys)[0] == 0

    def test_perfcheck_unreadable_baseline_and_bad_arguments_exit_2(self, baseline, tmp_path, capsys):
        code, out = run_main(["ids", "--against", str(tmp_path / "none.txt")], HEAD_IDS, capsys)
        assert code == 2 and "cannot read" in out.err
        for argv in (["ids", "--against", str(baseline), "--base", "HEAD"], ["ids", "--allow-removed", str(baseline)], ["ids", "extra"], ["time"]):
            with pytest.raises(SystemExit) as e:
                perfcheck.main(argv, collect=fake_collect(HEAD_IDS))
            assert e.value.code == 2, argv

    def test_perfcheck_ids_with_a_root_path_are_equal_from_two_roots(self, tmp_path):
        a, b = tmp_path / "clone-a", tmp_path / "clone-b"
        a.mkdir(), b.mkdir()
        tail = "/_tools/fixtures/kbusage/session.jsonl-None]"
        got = {perfcheck.normalize(f"_tools/test_k.py::T::test_none[{r}{tail}", r) for r in (a, b, a.as_posix())}
        assert got == {"_tools/test_k.py::T::test_none[<root>" + tail}
        win = "C:\\work\\kb"
        assert perfcheck.normalize("t.py::x[C:\\work\\kb\\_tools\\f\\s.jsonl-1]", win) == "t.py::x[<root>/_tools/f/s.jsonl-1]"
        assert perfcheck.normalize("t.py::x[C:/work/kb/_tools/s-1]", win) == "t.py::x[<root>/_tools/s-1]"

    def test_perfcheck_collect_normalizes_every_collected_id(self, tmp_path, monkeypatch):
        class Out:
            returncode, stderr = 0, ""
            stdout = f"_tools/test_a.py::t[{tmp_path}/_tools/f.jsonl-1]\n"
        monkeypatch.setattr(perfcheck.subprocess, "run", lambda *a, **k: Out())
        (tmp_path / "_tools").mkdir()
        assert perfcheck.collect_ids(tmp_path, cmd=["x"]) == ["_tools/test_a.py::t[<root>/_tools/f.jsonl-1]"]

    def test_perfcheck_baseline_with_an_absolute_path_is_refused(self, tmp_path, capsys):
        p = tmp_path / "base.txt"
        p.write_text("_tools/test_k.py::T::test_none[/" + "home" + "/someone/kb/_tools/f.jsonl-None]\n", encoding="utf-8", newline="\n")
        code, out = run_main(["ids", "--against", str(p)], HEAD_IDS, capsys)
        assert code == 2 and "absolute path" in out.err
        p.write_text("t.py::x[C:\\" + "Users" + "\\someone\\f]\n", encoding="utf-8", newline="\n")
        assert run_main(["ids", "--against", str(p)], HEAD_IDS, capsys)[0] == 2
        p.write_text("_tools/test_k.py::T::test_none[<root>/_tools/f.jsonl-None]\nt.py::x[a/b/c]\n", encoding="utf-8", newline="\n")
        assert run_main(["ids", "--against", str(p)], HEAD_IDS, capsys)[0] == 1  # read fine; its ids are just not collected

    def test_perfcheck_failed_collection_exits_2(self, baseline, capsys):
        def broken(root, cmd=None):
            raise perfcheck.PerfError("collecting x failed")
        assert perfcheck.main(["ids", "--against", str(baseline)], collect=broken) == 2
        assert "collecting x failed" in capsys.readouterr().err

    def test_perfcheck_base_collects_at_the_revision_not_the_working_tree(self, tmp_path, capsys, monkeypatch):
        seen = []

        def collect(root, cmd=None):
            seen.append(Path(root))
            return sorted(HEAD_IDS[:2]) if Path(root).name == "wt" else sorted(HEAD_IDS)

        monkeypatch.setattr(perfcheck, "collect_at", lambda rev, coll, repo: coll(Path(repo) / "wt"))
        assert perfcheck.main(["ids", "--base", "REV"], collect=collect, root=tmp_path) == 0
        out = capsys.readouterr().out
        assert seen == [tmp_path, tmp_path / "wt"] and "added: _tools/test_stress.py::test_three" in out and "revision REV" in out


class TestPerfcheckTime:
    @staticmethod
    def fake(seconds, code=0):
        ticks = iter([100.0, 100.0 + seconds])
        calls = []

        def runner(args, stress):
            calls.append((args, stress))
            return code
        return runner, lambda: next(ticks), calls

    def test_perfcheck_time_over_the_bound_fails(self, capsys):
        runner, clock, _ = self.fake(61.5)
        assert perfcheck.main(["time", "--max-seconds", "60"], runner=runner, clock=clock) == 1
        assert "61.5 s is over the bound of 60 s" in capsys.readouterr().out

    def test_perfcheck_time_within_the_bound_passes(self, capsys):
        runner, clock, _ = self.fake(59.0)
        assert perfcheck.main(["time", "--max-seconds", "60"], runner=runner, clock=clock) == 0
        assert "within the bound" in capsys.readouterr().out

    def test_perfcheck_time_a_failed_run_fails_even_when_fast(self, capsys):
        runner, clock, _ = self.fake(1.0, code=1)
        assert perfcheck.main(["time", "--max-seconds", "60"], runner=runner, clock=clock) == 1
        assert "failed (exit 1)" in capsys.readouterr().out

    def test_perfcheck_time_passes_other_arguments_and_stress_through(self):
        runner, clock, calls = self.fake(1.0)
        assert perfcheck.main(["time", "--max-seconds", "9", "-k", "x", "--stress"], runner=runner, clock=clock) == 0
        assert calls == [(["-k", "x"], True)]

    def test_perfcheck_time_needs_a_bound(self):
        with pytest.raises(SystemExit) as e:
            perfcheck.main(["time", "-k", "x"], runner=lambda a, s: 0)
        assert e.value.code == 2


class TestPerfcheckSelections:
    def test_perfcheck_selections_are_the_ones_the_runners_use(self):
        import stress_test, tests
        assert ["_tools", "-m", tests.FULL_M] == perfcheck.SELECTIONS[0][0]
        src = Path(stress_test.__file__).read_text(encoding="utf-8")
        assert 'os.path.join(tests.TOOLS, "test_stress.py"), "-m", "stress"' in src
        assert perfcheck.SELECTIONS[1][0] == ["_tools/test_stress.py", "-m", "stress"]

    def test_perfcheck_baseline_file_is_sorted_unique_one_id_per_line(self):
        text = (Path(perfcheck.TOOLS) / "test_ids_baseline.txt").read_text(encoding="utf-8")
        ids = text.splitlines()
        assert ids == sorted(set(ids)) and text.endswith("\n") and "\r" not in text
        assert all("::" in i and i.startswith("_tools/") for i in ids)
        assert not [i for i in ids if perfcheck.ABSOLUTE.search(i.split("::", 1)[1])], "no absolute path in the baseline"


def needs_pytest():
    if not perfcheck.pytest_command():
        pytest.skip("pytest is not available to start")


@pytest.mark.git
@requires_git
class TestPerfcheckGit:
    @pytest.fixture
    def repo(self, tmp_path):
        r = Repo(tmp_path / "r", git_env())
        (tmp_path / "r").mkdir()
        r.git("init", "-q")
        r.write("_tools/test_a.py", "def test_one():\n    pass\n\n\ndef test_two():\n    pass\n")
        r.git("add", "-A")
        r.git("commit", "-q", "-m", "base")
        return r

    def test_perfcheck_collect_at_reads_the_revision_and_removes_its_worktree(self, repo):
        needs_pytest()
        base = repo.rev("HEAD")
        repo.write("_tools/test_a.py", "def test_one():\n    pass\n")  # a test dropped in the working tree
        ids = perfcheck.collect_at(base, repo=Path(repo.path))
        assert ids == ["_tools/test_a.py::test_one", "_tools/test_a.py::test_two"]
        assert perfcheck.collect_ids(Path(repo.path)) == ["_tools/test_a.py::test_one"]
        assert repo.git("worktree", "list").count("\n") == 1, "the temporary worktree is removed"
        assert repo.read("_tools/test_a.py") == "def test_one():\n    pass\n", "the working tree is untouched"

    def test_perfcheck_base_fails_on_a_planted_dropped_test(self, repo):
        needs_pytest()
        base = repo.rev("HEAD")
        repo.write("_tools/test_a.py", "def test_one():\n    pass\n")
        r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, %r); import perfcheck; from pathlib import Path; "
                            "sys.exit(perfcheck.main(['ids', '--base', %r], root=Path(%r)))" % (str(perfcheck.TOOLS), base, repo.path)],
                           cwd=repo.path, env=git_env(), capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 1 and "MISSING: _tools/test_a.py::test_two" in r.stdout, r.stdout + r.stderr
        assert repo.git("worktree", "list").count("\n") == 1

    def test_perfcheck_unknown_revision_exits_2(self, repo, capsys):
        needs_pytest()
        assert perfcheck.main(["ids", "--base", "no-such-rev"], root=Path(repo.path)) == 2
        assert "cannot check out" in capsys.readouterr().err
