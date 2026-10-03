"""Tests of perfcheck.py's moved ids (kb/_self/tools.md): a test whose class and name live on in another file is moved, not removed.

TestPerfcheckMoved  a moved test is reported as moved and passes; a really removed test still fails and the allow list still
                    names it; a name in two new files is found (moved) once per missing id; a name that still exists in a file
                    the baseline held does not hide a removed copy; the split is the same for any order and any number of ids.
"""
import perfcheck


def ids_of(*pairs):
    return [f"_tools/{f}::{k}" for f, k in pairs]


def fake_collect(ids):
    return lambda root, cmd=None: sorted(ids)


def run(argv, head, capsys):
    code = perfcheck.main(argv, collect=fake_collect(head))
    return code, capsys.readouterr().out


def baseline_file(tmp_path, ids):
    p = tmp_path / "base.txt"
    p.write_text("".join(i + "\n" for i in ids), encoding="utf-8", newline="\n")
    return str(p)


class TestPerfcheckMoved:
    def test_perfcheck_ids_moved(self, tmp_path, capsys):
        base = ids_of(("test_old.py", "TestLand::test_a"), ("test_old.py", "test_plain[x y]"), ("test_old.py", "test_gone"), ("test_keep.py", "test_k"))
        against = baseline_file(tmp_path, base)
        # moved: same class and name in another file; not removed
        head = ids_of(("test_land.py", "TestLand::test_a"), ("test_land.py", "test_plain[x y]"), ("test_old.py", "test_gone"), ("test_keep.py", "test_k"))
        code, out = run(["ids", "--against", against], head, capsys)
        assert code == 0, out
        assert "moved: _tools/test_old.py::TestLand::test_a -> _tools/test_land.py::TestLand::test_a" in out
        assert "moved: _tools/test_old.py::test_plain[x y] -> _tools/test_land.py::test_plain[x y]" in out
        assert "MISSING" not in out and "added:" not in out
        assert "0 missing, 0 added, 2 moved to another file" in out
        # removed: no id with that class and name anywhere; still exit 1, and only that id is missing
        head = ids_of(("test_land.py", "TestLand::test_a"), ("test_keep.py", "test_k"))
        code, out = run(["ids", "--against", against], head, capsys)
        assert code == 1 and "MISSING: _tools/test_old.py::test_gone" in out and out.count("MISSING:") == 2
        # the allow list still names a removed id
        allow = tmp_path / "allow.txt"
        allow.write_text("# removed on purpose\n_tools/test_old.py::test_gone\n_tools/test_old.py::test_plain[x y]\n", encoding="utf-8", newline="\n")
        code, out = run(["ids", "--against", against, "--allow-removed", str(allow)], head, capsys)
        assert code == 0 and "removed (allowed): _tools/test_old.py::test_gone" in out and "MISSING" not in out

    def test_perfcheck_moved_class_must_match_not_only_the_name(self, tmp_path, capsys):
        against = baseline_file(tmp_path, ids_of(("test_old.py", "TestA::test_x")))
        code, out = run(["ids", "--against", against], ids_of(("test_new.py", "TestB::test_x")), capsys)
        assert code == 1 and "MISSING: _tools/test_old.py::TestA::test_x" in out and "added: _tools/test_new.py::TestB::test_x" in out
        code, out = run(["ids", "--against", against], ids_of(("test_new.py", "test_x")), capsys)
        assert code == 1  # a module-level test is not the class's test

    def test_perfcheck_moved_name_in_two_new_files_is_found(self, tmp_path, capsys):
        against = baseline_file(tmp_path, ids_of(("test_old.py", "TestLand::test_a")))
        head = ids_of(("test_one.py", "TestLand::test_a"), ("test_two.py", "TestLand::test_a"))
        code, out = run(["ids", "--against", against], head, capsys)
        assert code == 0 and out.count("moved:") == 1 and out.count("added:") == 1, out
        assert "1 missing" not in out and "0 missing, 1 added, 1 moved" in out

    def test_perfcheck_moved_each_added_id_answers_one_missing_id(self, tmp_path, capsys):
        base = ids_of(("test_old.py", "T::test_a"), ("test_other.py", "T::test_a"))
        against = baseline_file(tmp_path, base)
        code, out = run(["ids", "--against", against], ids_of(("test_new.py", "T::test_a")), capsys)
        assert code == 1 and out.count("moved:") == 1 and out.count("MISSING:") == 1, out
        code, out = run(["ids", "--against", against], ids_of(("test_new.py", "T::test_a"), ("test_new2.py", "T::test_a")), capsys)
        assert code == 0 and out.count("moved:") == 2

    def test_perfcheck_moved_a_name_kept_in_a_baseline_file_does_not_hide_a_removed_copy(self, tmp_path, capsys):
        base = ids_of(("test_a.py", "test_x"), ("test_b.py", "test_x"))
        against = baseline_file(tmp_path, base)
        code, out = run(["ids", "--against", against], ids_of(("test_a.py", "test_x")), capsys)
        assert code == 1 and "MISSING: _tools/test_b.py::test_x" in out and "moved:" not in out

    def test_perfcheck_moved_split_is_the_same_for_any_size_and_order(self, tmp_path, capsys):
        for n in (1, 2, 3, 4, 6, 12):
            for copies in (1, 2, 3):  # the same class and name in this many old files, so counts and steps share factors
                names = [f"Test{k % 3}::test_{k // 3}" for k in range(n)]
                total = n * copies
                base = ids_of(*[(f"test_old{c}.py", k) for c in range(copies) for k in names])
                against = baseline_file(tmp_path, base)
                moved_head = ids_of(*[(f"test_new{c}.py", k) for c in range(copies) for k in names])
                code, out = run(["ids", "--against", against], list(reversed(moved_head)), capsys)
                assert code == 0 and out.count("moved:") == total and "MISSING" not in out, (n, copies, out)
                code, again = run(["ids", "--against", against], moved_head, capsys)
                assert again == out, (n, copies)  # the same output whatever the collection order
                code, out = run(["ids", "--against", against], moved_head[1:], capsys)
                assert code == 1 and out.count("MISSING:") == 1 and out.count("moved:") == total - 1, (n, copies, out)

    def test_perfcheck_moved_compare_and_match(self):
        removed, added, allowed, moved = perfcheck.compare(
            ids_of(("a.py", "T::x"), ("a.py", "y"), ("a.py", "z")), ids_of(("b.py", "T::x"), ("c.py", "n")), allowed=ids_of(("a.py", "z")))
        assert removed == ids_of(("a.py", "y"))
        assert added == sorted(ids_of(("b.py", "T::x"), ("c.py", "n"))) and allowed == ids_of(("a.py", "z"))
        assert moved == [("_tools/a.py::T::x", "_tools/b.py::T::x")]
        assert perfcheck.test_key("_tools/a.py::T::x[p::q]") == "T::x[p::q]" and perfcheck.test_key("_tools/a.py::y") == "y"
        assert perfcheck.match_moved([], []) == ([], [], [])
