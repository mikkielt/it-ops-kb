"""backlog.py check and selectors: the rules every item file must meet, the knowledge an item names and its state, the
host and user names a check withholds, the repro and no-op warnings and the selector counts (bl_check.py).

Each rule has a planted failure: a non-canonical file, a cycle, a stale touches path, a worked item of a planned sprint,
an item that holds a piece of this host's name, a reference the kb does not hold or reworded, a source that is
superseded or an article with an open conflict, a check that runs nothing, a repro that only matches text in a file, a
state that changes in more ways than its checks name, a gate option with no command, and a selector that collects
nothing. The patches name the module where the code looks the name up, `bl_check`.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import backlog
import bl_base
import bl_check
import bl_testkit
from bl_testkit import SOURCE_REPRO, TEXT_REPRO, PASS, TOOLS, argstr, b, commit, edit, is_file, item, sh

bl_testkit.bind(backlog)

repo, sprint, no_git_location, gate_jobs = bl_testkit.repo, bl_testkit.sprint, bl_testkit.no_git_location, bl_testkit.gate_jobs


def test_new_items_validate(sprint):
    code, out = b(sprint["repo"], "check")
    assert code == 0 and "errors=0" in out, out


def test_check_finds_planted_errors(sprint):
    repo = sprint["repo"]
    f = Path(repo) / backlog.REL_DIR / f"{sprint['tk']}.json"
    f.write_text(json.dumps(json.loads(f.read_text(encoding="utf-8"))) + "\n", encoding="utf-8")
    edit(repo, sprint["bg"], depends_on=[sprint["st"]])
    edit(repo, sprint["st"], depends_on=[sprint["bg"]])
    code, out = b(repo, "check")
    assert code == 1
    assert "canonical form" in out and "cycle" in out
    assert f"{sprint['tk']} “Task”" in out  # an id is never printed without its title


def test_check_errors_on_refused_item_command(sprint):
    """An open item's repro or check that check_program_refusal refuses (a shell) or trivial_command flags (code that
    only passes) is a check error, so the item file fails its own push; a done item's is history and passes."""
    repo = sprint["repo"]
    assert b(repo, "check")[0] == 0
    edit(repo, sprint["bg"], repro={"run": ["sh", "-c", "test -f src/c.txt"]})
    edit(repo, sprint["tk"], checks=[{"run": PASS}])
    code, out = b(repo, "check")
    assert code == 1 and "errors=2" in out, out
    assert f"{sprint['bg']} “Bug”: repro is refused: its program is not python3" in out, out
    assert f"{sprint['tk']} “Task”: check is refused: it runs no test or tool code" in out, out
    assert "src/c.txt" not in out, out  # the command is never printed: it may hold a value the leak scan withholds
    edit(repo, sprint["bg"], status="dropped")
    edit(repo, sprint["tk"], checks=[{"run": is_file("src/b.txt")}])
    code, out = b(repo, "check")
    assert code == 0 and "errors=0" in out, out


def tests_check(*args):
    return {"run": ["python3", "_tools/tests.py", *args]}


def test_backlog_selectors_parse_the_selector_of_a_check():
    """Only a tests.py run with -k is a selector; its targets and -m ride along, --changed and other tools are none."""
    sel = bl_check.selector_of
    assert sel(["python3", "_tools/tests.py", "-k", "a or b"]) == ("-k 'a or b'", [], "a or b", "not stress")
    assert sel(["python3", "C:\\kb\\_tools\\tests.py", "-k", "x"])[2] == "x"
    assert sel(["python3", "_tools/tests.py", "_tools/test_x.py", "-k", "x", "-m", "git"]) == \
        ("_tools/test_x.py -k x -m git", ["_tools/test_x.py"], "x", "git")
    assert sel(["python3", "_tools/tests.py", "--changed", "origin/main", "-k", "x"]) is None
    assert sel(["python3", "_tools/tests.py"]) is None
    assert sel(["grep", "-c", "-k ruff", "f"]) is None and sel(["python3", "-c", "pass"]) is None


def test_backlog_selectors_count_the_tests_each_k_collects(sprint):
    """Planted: a selector that collects two known tests, one that collects nothing and one pytest cannot parse, on
    open items; selectors prints each with its count, item id and title, marks the zero and the error, lists them
    first, and exits 0. A done item's selector, a --changed run and a check that is no tests.py run are left out."""
    repo, tk, st, bg = sprint["repo"], sprint["tk"], sprint["st"], sprint["bg"]
    (repo / "_tools").mkdir()
    (repo / "_tools" / "test_planted.py").write_text(
        "def test_known_thing_one():\n    pass\n\n\ndef test_known_thing_two():\n    pass\n", encoding="utf-8")
    edit(repo, tk, checks=[tests_check("-k", "known_thing"), tests_check("-k", "no_such_planted_test"),
                           tests_check("--changed", "origin/main", "-k", "no_such_planted_test"), is_file("src/b.txt")])
    edit(repo, st, checks=[tests_check("-k", "known_thing_one"), tests_check("-k", "(")])
    edit(repo, bg, status="done", checks=[tests_check("-k", "done_items_never_listed")])
    code, out = b(repo, "selectors")
    assert code == 0, out
    lines = out.splitlines()
    assert len(lines) == 5, out
    assert lines[0].split()[:2] == ["?", "error"] and "-k '('" in lines[0] and "pytest exit 4" in lines[0] and f"{st} “Story”" in lines[0], out
    assert lines[1].split()[:2] == ["0", "NONE"] and "-k no_such_planted_test" in lines[1] \
        and f"{tk} “Task”" in lines[1], out
    assert lines[2].split()[0] == "1" and "NONE" not in lines[2] and "-k known_thing_one  " in lines[2] \
        and f"{st} “Story”" in lines[2], out
    assert lines[3].split()[0] == "2" and "NONE" not in lines[3] and "-k known_thing  " in lines[3] \
        and f"{tk} “Task”" in lines[3], out
    assert "done_items_never_listed" not in out and "src/b.txt" not in out and "--changed" not in out, out
    assert lines[4] == "backlog selectors: checks=4 selectors=4 none=1 errors=1", out


def test_task_needs_parent_and_touches(repo):
    b(repo, "new", "epic", "--title", "E", "--goal", "g")
    code, out = b(repo, "new", "task", "--title", "Orphan", "--goal", "g")
    assert "needs a parent" in out and "touches missing" in out


def test_done_flags_noop_check_classifier():
    """noop_output, trivial_command and is_test_run on outputs and commands of each kind, the BG-uqmjlqfl output
    (publish --dry-run in a clone with no public remote) first."""
    f, t, tr = bl_check.noop_output, bl_check.trivial_command, bl_check.is_test_run
    assert "no public remote" in f("note: no public remote (git config kb.publishRemote <remote>); nothing published\n")
    assert "nothing published" in f("bridge: nothing published\n")
    assert "no test can be affected" in f("tests.py --changed HEAD: no test can be affected by the changed paths\n")
    assert "skipped" in f("ss\n2 skipped in 0.03s\n") and "skipped" in f("===== 3 skipped, 1 deselected in 0.10s =====\n")
    for out in ("..s\n2 passed, 1 skipped in 0.20s\n", "1 failed, 1 skipped in 0.20s\n", "red-pipeline: nothing to file",
                "", "ok\n"):
        assert f(out) is None, out
    for argv in (["true"], ["/usr/bin/echo", "ok"], PASS, ["python3", "-c", "import sys; sys.exit(0)"],
                 ["python3", "-c", "print('ok')"], ["sh", "-c", "exit 0"], ["cmd", "/c", "exit 0"]):
        assert t(argv), argv
    for argv in (is_file("x"), ["python3", "-c", "import sys; sys.exit(not 1)"], ["python3", "_tools/tests.py", "-k", "x"],
                 ["git", "grep", "-q", "-e", "x", "--", "f"], ["sh", "-c", "set -e; python3 t.py"]):
        assert t(argv) is None, argv
    assert tr(["python3", "_tools/tests.py", "-k", "x"]) and tr(["python3", "-m", "pytest", "t.py"]) and tr(["pytest"])
    assert not tr(["python3", "_tools/kbgit.py", "publish", "--dry-run"]) and not tr(["python3", "-c", "import tests"])


def test_done_flags_noop_check_real_publish_output(repo, capsys):
    """The real code: publish --dry-run in a clone with no public remote passes doing nothing, and its own output is
    what noop_output flags."""
    import kbpublic
    assert kbpublic.cmd_publish(argparse.Namespace(remote=None, dry_run=True), str(repo)) == 0
    out = capsys.readouterr().out
    assert "no public remote" in bl_check.noop_output(out), out


def trivial_live(items):
    """(id, argv) of each check or repro that trivial_command flags among ITEMS, open ones only: the items backlog.py
    check reads for the same rule (refused_command_errors), so a done item, whose checks set refuses to change and
    done only warns of, never turns this test red where check passed (BG-4zpv4iol)."""
    return [(it["id"], c["run"]) for it in items if it.get("status") in bl_check.OPEN_STATUSES
            for c in it.get("checks", []) + ([it["repro"]] if it.get("repro") else []) if bl_check.trivial_command(c["run"])]


def test_done_flags_noop_check_real_backlog_commands():
    """Real inputs: no check or repro of the repository's open items runs nothing (trivial_command flags none), the
    items check refuses such a command on; planted: an open item with `python3 -c pass` is flagged, a done one is not,
    and check agrees on both."""
    items = [json.loads(f.read_text(encoding="utf-8")) for f in (Path(TOOLS).parent / backlog.REL_DIR).glob("*.json")]
    assert not trivial_live(items), trivial_live(items)
    planted = [{"id": f"TK-{s}aaaaaaa", "kind": "task", "title": s, "status": s,
                "checks": [{"run": ["python3", "-c", "pass"]}]} for s in ("t", "d")]
    planted[0]["status"], planted[1]["status"] = "todo", "done"
    assert [i for i, _ in trivial_live(planted)] == ["TK-taaaaaaa"]
    bl = bl_base.Backlog(Path(TOOLS).parent)
    bl.items = {it["id"]: it for it in planted}
    assert [e.split(" ", 1)[0] for e in bl_check.refused_command_errors(bl)] == ["TK-taaaaaaa"]


def test_done_flags_noop_check_new_and_done_warn_of_a_trivial_check(sprint):
    """A check that runs no test or tool code is warned of by new and by done; done still passes on it."""
    repo, tk = sprint["repo"], sprint["tk"]
    code, out = b(repo, "set", tk, "--add", "--check", argstr(PASS))
    assert code == 0, out
    code, out = b(repo, "new", "story", "--title", "Trivial", "--goal", "g", "--check", argstr(PASS))
    assert code == 0 and "warning:" in out and "proves nothing" in out, out
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    commit(repo, "write b", tk)
    code, out = b(repo, "done", tk)
    assert code == 0 and "passed without doing its work" in out and "only passes" in out, out


def test_repro_needs_behaviour_or_reason_classifier():
    """text_only_repro flags a grep, a shell of greps and a python -c that only reads a file and tests its text
    (BG-qtphqxt2's literal, BG-g6qpxe5x's regex over a test's text); a test run, a tool, a script, a planted-input
    command and python code that runs other code are behaviour."""
    t = bl_check.text_only_repro
    for argv in (["grep", "-q", "worktrees", "_tools/backlog.py"], ["git", "grep", "-q", "-e", "x", "--", "f.md"],
                 ["/usr/bin/git", "grep", "x"], ["rg", "x"], ["findstr", "x", "f"],
                 ["sh", "-c", "set -e; grep -q x f && ! grep -q y g"], ["python3", "-c", TEXT_REPRO],
                 ["python3", "-c", SOURCE_REPRO],
                 ["python3", "-c", "import re,sys; sys.exit(not re.search(r'>\\s*&2', open('_tools/test_x.py').read()))"]):
        assert t(argv), argv
    assert "reading source of _tools/tool.py" in t(["python3", "-c", SOURCE_REPRO])
    assert "reading source of _tools/backlog.py" in t(["grep", "-q", "worktrees", "_tools/backlog.py"])
    assert "reading source" not in t(["python3", "-c", TEXT_REPRO])
    for argv in ([], PASS, is_file("x"), ["python3", "_tools/tests.py", "-k", "x"], ["python3", "_tools/backlog.py",
                 "red-pipeline", "--status"], ["python3", "repro.py"], ["sh", "-c", "set -e; python3 t.py"],
                 ["sh", "-c", "grep -q x f; python3 t.py"],
                 ["python3", "-c", "import subprocess, sys; sys.exit(subprocess.call(['x'], stdin=open('in.txt')))"],
                 ["python3", "-c", "import sys; sys.path.insert(0, '_tools'); import backlog; open('x')"],
                 ["python3", "-c", "import backlog, sys; sys.exit(backlog.main(['check']) or 'x' in open('f').read())"]):
        assert t(argv) is None, argv


PIPED_GREP = ["sh", "-c", "cat _tools/x.py | grep -q foo"]
AWK_OVER_SOURCE = ["awk", "/foo/{f=1} END{exit !f}", "_tools/x.py"]
TEST_OF_GREP = ["sh", "-c", 'test -z "$(grep -n foo _tools/x.py)"']
TEST_N_OF_GREP = ["sh", "-c", 'test -n "$(grep -n foo _tools/x.py)"']  # fails in the planted repository, as a repro must


def test_text_only_repro_flags_pipes_awk_sed_and_test_of_grep(repo):
    """text_only_repro also flags a pipeline of text filters feeding grep, awk or sed, awk or sed run over a file, and a
    test -z / -n over a grep's output (BG-pg75dexf: SP-5cwekumc's review found them passing as behaviour); a pipeline
    that runs a tool, a filter with no matcher, an awk or sed over no file and a test of a tool's output are behaviour;
    new refuses a flagged repro without a reason, and check warns of an open bug that keeps one."""
    t = bl_check.text_only_repro
    for argv in (PIPED_GREP, AWK_OVER_SOURCE, TEST_OF_GREP, TEST_N_OF_GREP, ["sh", "-c", '[ -n "$(git grep -n foo -- f.py)" ]'],
                 ["sed", "-n", "/foo/p", "_tools/x.py"], ["sh", "-c", "head -n 5 f.py | sed -n /x/p | grep -q y"],
                 ["bash", "-c", "set -e; cat f.md | awk '/x/{f=1} END{exit !f}'"]):
        assert t(argv), argv
    assert "reading source of _tools/x.py" in t(PIPED_GREP) and "reading source of _tools/x.py" in t(AWK_OVER_SOURCE)
    for argv in (["sh", "-c", "python3 _tools/backlog.py check | grep -q ok"], ["sh", "-c", "cat f | python3 t.py"],
                 ["sh", "-c", "cat f | wc -l"], ["awk", "BEGIN{exit 1}"], ["sed", "-n", "/x/p"],
                 ["sh", "-c", 'test -z "$(python3 _tools/x.py)"'], ["sh", "-c", "python3 t.py | awk '/ok/'"],
                 ["sh", "-c", "grep -q x f; python3 t.py"]):
        assert t(argv) is None, argv
    for argv in (PIPED_GREP, AWK_OVER_SOURCE, TEST_N_OF_GREP):
        code, out = b(repo, "new", "bug", "--title", "Text only", "--severity", "S3", "--goal", "x", "--repro", argstr(argv))
        assert code == 2 and "only matches text in a file" in out and "--repro-reason" in out, (argv, out)
        assert not list((Path(repo) / backlog.REL_DIR).glob("*.json")), "a refused repro files nothing"


def test_repro_reads_source_check_warns(repo):
    """check warns of an open bug whose repro only reads a _tools/ source file for a string and states no reason
    (BG-rrht7uts planted); a reason, or the bug done, clears it; a malformed reason, or one on a story, is an error."""
    (repo / "_tools").mkdir()
    (repo / "_tools" / "tool.py").write_text("ROOT = 'checkout'\n", encoding="utf-8")
    code, out = b(repo, "new", "bug", "--title", "Grep fix", "--severity", "S3", "--goal", "x",
                  "--repro", argstr(["python3", "-c", SOURCE_REPRO]), "--repro-reason", "planted")
    assert code == 0, out
    bg = item(repo, "Grep fix")["id"]
    it = item(repo, "Grep fix")
    del it["repro_reason"]
    (Path(repo) / backlog.REL_DIR / f"{bg}.json").write_text(backlog.canonical(it), encoding="utf-8", newline="\n")
    code, out = b(repo, "check")
    assert code == 0 and "warnings=1" in out and bg in out and "reading source of _tools/tool.py" in out, out
    assert "repro_reason" in out, out
    edit(repo, bg, repro_reason="the defect is a constant's spelling, read by no test")
    code, out = b(repo, "check")
    assert code == 0 and "warnings=0" in out, out
    edit(repo, bg, repro_reason=" ")
    code, out = b(repo, "check")
    assert code == 1 and "repro_reason must be text" in out, out
    it = item(repo, "Grep fix")
    del it["repro_reason"]
    it["status"] = "done"
    (Path(repo) / backlog.REL_DIR / f"{bg}.json").write_text(backlog.canonical(it), encoding="utf-8", newline="\n")
    code, out = b(repo, "check")
    assert "warnings=0" in out, out  # a done bug's repro is history
    assert b(repo, "new", "story", "--title", "Story", "--goal", "g", "--check", argstr(is_file("src/a.txt")))[0] == 0
    edit(repo, item(repo, "Story")["id"], repro_reason="x")
    code, out = b(repo, "check")
    assert code == 1 and "for bugs only" in out, out


def test_repro_reads_source_real_backlog():
    """Real inputs: no repro or check of the repository's own items that runs tests or a tool script is read as
    text-only, and every warning check gives names an open bug with no repro_reason."""
    real = backlog.Backlog(Path(TOOLS).parent)
    for f in (Path(TOOLS).parent / backlog.REL_DIR).glob("*.json"):
        it = json.loads(f.read_text(encoding="utf-8"))
        for c in it.get("checks", []) + ([it["repro"]] if it.get("repro") else []):
            run = c["run"]
            if bl_check.is_test_run(run) or (len(run) > 1 and run[1].endswith(".py")):
                assert bl_check.text_only_repro(run) is None, (it["id"], run)
    for w in bl_check.repro_text_warnings(real):
        it = real.items[w.split()[0]]
        assert it["kind"] == "bug" and it.get("status") in bl_check.OPEN_STATUSES and not it.get("repro_reason"), w


def test_started_sprint_check_refuses_worked_item_of_planned_sprint(repo):
    """A planned sprint's items stay draft until start: a task under its story is created draft, and check reports a
    todo, doing or done item of it (planted: the story set to todo)."""
    b(repo, "new", "sprint", "--title", "Planned", "--goal", "g")
    sp = item(repo, "Planned")["id"]
    b(repo, "new", "story", "--title", "S", "--sprint", sp, "--goal", "g", "--check", argstr(is_file("src/b.txt")))
    st = item(repo, "S")["id"]
    b(repo, "new", "task", "--title", "T", "--parent", st, "--goal", "g", "--touch", "src/**", "--check", argstr(is_file("src/b.txt")))
    assert item(repo, "T")["status"] == "draft"
    assert b(repo, "check")[0] == 0
    edit(repo, st, status="todo")
    code, out = b(repo, "check")
    assert code == 1 and f"{st} “S”: status todo while its sprint {sp} “Planned” is planned" in out, out
    assert "not in a started sprint" in out


def test_repository_backlog_is_valid():
    code, out = b(os.path.dirname(TOOLS), "check")
    assert code == 0, out


# ---- host and user names: read from the environment, planted here as placeholders, never printed

PLANTED_HOST, PLANTED_USER = "PL-LT-00123", "jan.kowalski"
PLANTED_PIECES = ("pl-lt-00123", "pllt00123", "pllt00~", "jan.kowalski", "jankowalski", "jankow~", "kowalski")


@pytest.fixture
def planted_names(monkeypatch):
    """This host is PL-LT-00123 and its user jan.kowalski, in this process and in the backlog.py it starts."""
    for k in bl_base.HOST_ENV + bl_base.USER_ENV + bl_base.PROFILE_ENV:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("COMPUTERNAME", PLANTED_HOST)
    monkeypatch.setenv("USERNAME", PLANTED_USER)
    monkeypatch.setattr(bl_base.socket, "gethostname", lambda: PLANTED_HOST)


def no_planted_piece(out):
    low = out.lower()
    return not any(p in low for p in PLANTED_PIECES)


def test_item_holds_host_names_pieces_of_a_name():
    assert bl_base.name_pieces(PLANTED_HOST) == {"pl-lt-00123", "pllt00123", "pllt00~"}  # pl, lt: too short; 00123: no letter
    assert bl_base.name_pieces(PLANTED_USER) == {"jan.kowalski", "jankowalski", "jankow~", "kowalski"}
    assert bl_base.name_pieces("JanKowalskiCorp") == {"jankowalskicorp", "jankow~", "kowalski"}  # CamelCase parts
    assert bl_base.name_pieces("PL-SRV-0042") == {"pl-srv-0042", "plsrv0042", "plsrv0~"}
    assert bl_base.name_pieces("XYZ-PC01") == {"xyz-pc01", "xyzpc01", "pc01"}  # 4 characters with a digit
    for generic in ("runner", "root", "user", "admin", "container", "localhost", "DESKTOP"):
        assert bl_base.name_pieces(generic) == set(), generic
    # a GitLab runner's host name: only its token and the whole name are pieces, not project or concurrent
    assert bl_base.name_pieces("runner-ab12cd34-project-42-concurrent-0") == {
        "runner-ab12cd34-project-42-concurrent-0", "runnerab12cd34project42concurrent0", "ab12cd34"}


CI_POD = "runner-ab12cd34-project-42-concurrent-0-x7k2p"  # a Kubernetes executor's pod: its random suffix last


def test_item_holds_host_names_ci_accounts_give_no_piece(sprint, monkeypatch, capsys):
    """BG-72dbkic3: the names CI gives every machine (gitlab-runner on a shell executor, ContainerAdministrator and
    ContainerUser in Windows containers, a pod's random suffix) give no piece, so check never refuses kb text that
    spells them; a person's name made of a generic part and another (JanAdmin) still does."""
    for generic in ("gitlab-runner", "ContainerAdministrator", "ContainerUser", "GitLab-Runner"):
        assert bl_base.name_pieces(generic) == set(), generic
    assert bl_base.name_pieces(CI_POD) == {CI_POD, "runnerab12cd34project42concurrent0x7k2p", "ab12cd34"}
    assert "pc001" in bl_base.name_pieces("abc-pc001")  # 0 and 1 are not of the pod alphabet: a serial stays
    assert bl_base.name_pieces("JanAdmin") == {"janadmin"}
    for env in ({"USER": "gitlab-runner", "HOSTNAME": CI_POD}, {"USERNAME": "ContainerAdministrator", "COMPUTERNAME": CI_POD},
                {"USERNAME": "ContainerUser", "COMPUTERNAME": CI_POD}):  # the profile folder is named as the user
        for k in bl_base.HOST_ENV + bl_base.USER_ENV + bl_base.PROFILE_ENV:
            monkeypatch.delenv(k, raising=False)
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        monkeypatch.setattr(bl_base.socket, "gethostname", lambda: CI_POD)
        edit(sprint["repo"], sprint["st"], goal="b exists under /builds/gitlab-runner/x7k2p as ContainerAdministrator "
                                                "or ContainerUser")
        assert backlog.main(["--root", str(sprint["repo"]), "check"]) == 0, (env, capsys.readouterr().out)
        capsys.readouterr()


def test_item_holds_host_names_read_from_the_environment(planted_names):
    pieces = bl_base.host_user_pieces()
    assert set(pieces) == set(PLANTED_PIECES)
    assert pieces["kowalski"] == "user" and pieces["pllt00123"] == "host"
    assert bl_base.host_user_pieces({"COMPUTERNAME": "runner", "USERNAME": "root"}) == {"pl-lt-00123": "host",
                                                                                        "pllt00123": "host", "pllt00~": "host"}


def test_item_holds_host_names_refused_without_the_piece(sprint, planted_names, capsys):
    repo = sprint["repo"]
    edit(repo, sprint["st"], goal="b exists on \\\\PL-LT-00123\\share")
    edit(repo, sprint["tk"], title="Task for Kowalski", gates=[{"id": "g", "kind": "blocking",
                                                                "question": "ask jan.kowalski first"}])
    assert backlog.main(["--root", str(repo), "check"]) == 1
    out = capsys.readouterr().out
    assert no_planted_piece(out), "a planted name was printed"
    # the id with its title withheld, which may hold the name too, and the field
    assert f"{sprint['st']} (title withheld" in out and "“Story”" not in out, out
    assert "field goal holds a piece of this host's computer name" in out
    assert f"{sprint['tk']} (title withheld" in out and "field title holds a piece of this host's user name" in out
    assert "field gates[0].question holds a piece of this host's user name" in out
    code, out = b(repo, "check")  # the command line, the push gate's form
    assert code == 1 and "errors=3" in out and no_planted_piece(out), "a planted name was printed"


def test_item_holds_host_names_clean_item_passes(sprint, planted_names, capsys):
    edit(sprint["repo"], sprint["st"], goal="b exists on \\\\PL-SRV-0042\\share for kowal")  # other names, a short one
    assert backlog.main(["--root", str(sprint["repo"]), "check"]) == 0, capsys.readouterr().out
    assert b(sprint["repo"], "check")[0] == 0


def test_item_holds_host_names_short_form(planted_names):
    """Windows' 8.3 form of a long profile name (a TEMP path's JANKOW~1 profile folder) is a piece too, and
    the profile folder's name counts as the user's."""
    assert "jankow~" in bl_base.name_pieces("jan.kowalski") and "jankow~" in bl_base.name_pieces("JanKowalskiCorp")
    assert not any("~" in p for p in bl_base.name_pieces("kowal12"))  # 8 characters or fewer: never shortened
    pieces = bl_base.host_user_pieces({"USERNAME": "x", "USERPROFILE": "C:/Users/<profile>/jan.kowalski"})
    assert "kowalski" in pieces and any(p in "c:/users/jankow~1/appdata/local/temp" for p in pieces)


def test_item_holds_host_names_never_printed_by_any_command(sprint, planted_names):
    """list, tree, show and claim print a named item's title and fields with the name withheld, not only check."""
    repo = sprint["repo"]
    edit(repo, sprint["tk"], title="Task for Kowalski on PL-LT-00123")
    for argv in (["list"], ["tree"], ["show", sprint["tk"]], ["claim", sprint["tk"], "--by", "w"]):
        code, out = b(repo, *argv)
        assert sprint["tk"] in out and no_planted_piece(out), (argv, out)


def test_check_flags_gone_repro_paths(sprint):
    """ST-huye4kew planted (BG-57n4r577, ST-tbi3rras): an open item whose check reads a file that git moved away
    is warned of by check, naming the item, the part and the path; a path git never had (a file the work will
    create) and a done item's gone path are not."""
    repo, tk = sprint["repo"], sprint["tk"]
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "old.txt").write_text("x\n", encoding="utf-8")
    commit(repo, "a file")
    edit(repo, tk, checks=[{"run": is_file("src/old.txt")}, {"run": is_file("src/new_by_work.txt")}])
    commit(repo, "checks")
    code, out = b(repo, "check")
    assert code == 0 and "is gone" not in out, out
    sh(repo, "git", "mv", "src/old.txt", "src/moved.txt")
    commit(repo, "move it")
    code, out = b(repo, "check")
    assert code == 0 and f"{tk} " in out and "check 1 names src/old.txt, which is gone" in out, out
    assert "new_by_work.txt" not in out, out
    edit(repo, tk, status="done")
    code, out = b(repo, "check")
    assert "is gone" not in out, out


def test_check_gone_path_a_removal_check_is_no_finding(sprint):
    """BG-gvryjkwc planted: an open removal item whose checks assert a removed file is absent (python exiting with its
    existence, `assert not os.path.exists`; an item's checks run no shell) is not told the path is gone, since
    its absence is the proof; a check that reads the same gone file still is."""
    repo, tk = sprint["repo"], sprint["tk"]
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "old.txt").write_text("x\n", encoding="utf-8")
    commit(repo, "a file")
    sh(repo, "git", "rm", "-q", "src/old.txt")
    commit(repo, "remove it")
    absent = [["python3", "-c", "import pathlib,sys; sys.exit(pathlib.Path('src/old.txt').exists())"],
              ["python3", "-c", "import os; assert not os.path.exists('src/old.txt')"]]
    edit(repo, tk, checks=[{"run": r} for r in absent])
    commit(repo, "removal checks")
    code, out = b(repo, "check")
    assert code == 0 and "is gone" not in out, out
    edit(repo, tk, checks=[{"run": r} for r in absent] + [{"run": is_file("src/old.txt")}])
    code, out = b(repo, "check")
    assert code == 0 and "names src/old.txt, which is gone" in out, out


def test_project_paths_scp_and_non_ascii(tmp_path):
    """BG-m5qbkmgp planted: git's scp-like host:path remote with no user is read like user@host:path, a one-letter
    host is a Windows drive and no remote, and a remote whose URL is not valid UTF-8 (git prints its bytes) is read
    with replacement instead of crashing the read."""
    repo = tmp_path / "r"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    for name, url in (("o", "gitlab.example.com:grp/proj.git"), ("d", "C:/repos/local/x"),
                      ("n", b"https://gitlab.example.com/gr\xfcp/p\xc3\xb8j.git")):
        subprocess.run([b"git", b"-C", bytes(repo), b"remote", b"add", name.encode(), url if isinstance(url, bytes)
                        else url.encode()], check=True)
    got = bl_base.project_paths(repo)
    assert {"grp/proj", "grp%2fproj"} <= got, got
    assert not any(p.startswith("repos/") for p in got), got
    assert "gr\ufffdp/p\u00f8j" in got, got


def test_name_check_exempts_project_path(sprint, planted_names, capsys):
    """A namespace equal to the user's name: the repository path (read from the remotes) is no hit, the name
    elsewhere still is."""
    repo = sprint["repo"]
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", "git@gitlab.com:jan.kowalski/it-ops-kb.git"], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "pub", "https://github.com/Jan.Kowalski/it-ops-kb"], check=True)
    assert bl_base.project_paths(repo) == {"jan.kowalski/it-ops-kb", "jan.kowalski%2fit-ops-kb"}
    edit(repo, sprint["st"], goal="glab api projects/jan.kowalski%2Fit-ops-kb/runners, see Jan.Kowalski/it-ops-kb")
    assert backlog.main(["--root", str(repo), "check"]) == 0, capsys.readouterr().out
    edit(repo, sprint["st"], goal="projects/jan.kowalski%2Fit-ops-kb, ask jan.kowalski")
    assert backlog.main(["--root", str(repo), "check"]) == 1
    out = capsys.readouterr().out
    assert "field goal holds a piece of this host's user name" in out and no_planted_piece(out)


def test_item_holds_host_names_real_backlog_passes_on_this_host():
    """The names of the host running the tests, never spelled here: the real backlog holds no piece of them. (Not
    the planted ones: the backlog writes those placeholders on purpose.)"""
    assert bl_base.items_holding_names(backlog.Backlog(os.path.dirname(TOOLS))) == {}
    code, out = b(os.path.dirname(TOOLS), "check")
    assert code == 0, out


# ---- knowledge: an item's asks and kb references, resolved against the kb of the clone

FACT = "Demo tools print their version. [DOC S100]"


ARTICLE = f"---\ntopic: demo/tool\nstatus: partial\n---\n\n# Demo tool\n\n## Facts\n- {FACT}\n"


CSV = "name,source,tag\nalpha,S100,DOC\n"


def worked_carrier(repo, title="Carrier", sprint_title="Carrier sprint", start=True):
    """A story in a sprint (started unless START is false) to carry `knowledge`: check validates the refs of a todo or
    doing item of an active sprint only (bl_check.knowledge_worked). Returns the story's id."""
    b(repo, "new", "sprint", "--title", sprint_title, "--goal", "carry knowledge")
    sp = item(repo, sprint_title)["id"]
    edit(repo, item(repo, f"Research sprint goal: {sprint_title}")["id"], status="dropped")
    b(repo, "new", "story", "--title", title, "--sprint", sp, "--goal", "carries knowledge", "--touch", "src/**",
      "--check", argstr(is_file("src/b.txt")))
    if start:
        assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
        code, out = b(repo, "start", sp)
        assert code == 0, out
    return item(repo, title)["id"]


@pytest.fixture
def kb(repo):
    """The repository gets a public kb root: a source, a QK answer, an article with one fact and a data file; a
    story of a started sprint to carry `knowledge`."""
    root = repo / "kb" / "public"
    (root / "demo").mkdir(parents=True)
    (root / "_root.md").write_text("---\nroot: public\nid_prefix: S\nvisibility: public\n---\n\n# public\n",
                                   encoding="utf-8", newline="\n")
    (root / "_sources.csv").write_text("id,url\nS100,https://example.com/a\nS-abcdefgh,https://example.com/b\n",
                                       encoding="utf-8", newline="\n")
    (root / "_answers.md").write_text("# Answers\n\n## QK-demo-question. What does the demo print?\n- It prints. "
                                      "[DOC S100]\n", encoding="utf-8", newline="\n")
    (root / "demo" / "tool.md").write_text(ARTICLE, encoding="utf-8", newline="\n")
    (root / "demo" / "rows.csv").write_text(CSV, encoding="utf-8", newline="\n")
    carrier = worked_carrier(repo)
    commit(repo, "kb")
    return repo, carrier


def key(text=FACT):
    import kbfacts
    return kbfacts.fact_key(text)


def test_knowledge_refs_of_every_kind_resolve(kb):
    repo, iid = kb
    refs = ["demo/tool", "public/demo/tool", "QK-demo-question", "public:QK-demo-question", "S100", "S-abcdefgh",
            f"public/demo/tool.md#{key()}", f"demo/tool.md#{key()}"]
    edit(repo, iid, knowledge={"ask": ["What does the demo print?"], "refs": refs})
    code, out = b(repo, "check")
    assert code == 0 and "errors=0 stale=0" in out, out


@pytest.mark.parametrize("ref, why", [
    ("demo/absent", "no such topic"),
    ("demo/tool.md", "no such topic"),  # a topic id has no extension
    ("public/_answers", "no such topic"),  # a ledger is no article
    ("QK-no-such-answer", "no such answer"),
    ("other:QK-demo-question", "no kb root"),
    ("S999", "no such source id"),
    ("S-zzzzzzzz", "no such source id"),
    ("public/demo/absent.md#" + "0" * 12, "no article or data file"),
    ("public/demo/tool.md#abc", "12 lowercase hex"),
    ("free text", "not a topic id"),
])
def test_knowledge_refs_missing_from_the_kb_are_refused(kb, ref, why):
    repo, iid = kb
    edit(repo, iid, knowledge={"refs": [ref]})
    code, out = b(repo, "check")
    assert code == 1 and why in out and f"{iid} “Carrier”: knowledge ref" in out, out


def test_knowledge_refs_fact_of_a_data_file_and_a_reworded_fact(kb):
    """A csv row's key resolves; the article's fact reworded (planted) is stale: printed, counted apart, exit 0."""
    repo, iid = kb
    csv_key = key("name=alpha; source=S100; tag=DOC")
    edit(repo, iid, knowledge={"refs": [f"public/demo/rows.csv#{csv_key}", f"public/demo/tool.md#{key()}"]})
    assert b(repo, "check")[0] == 0
    art = repo / "kb" / "public" / "demo" / "tool.md"
    art.write_text(ARTICLE.replace("print their version", "print their build"), encoding="utf-8", newline="\n")
    commit(repo, "reword")  # refs are read at HEAD
    code, out = b(repo, "check")
    assert code == 0 and "errors=0 stale=1" in out, out
    assert f"{iid} “Carrier”: stale knowledge: fact {key()} is no longer in public/demo/tool.md" in out
    art.unlink()  # planted: the article removed is missing, not stale
    commit(repo, "remove")
    code, out = b(repo, "check")
    assert code == 1 and "no article or data file" in out, out


def test_knowledge_refs_read_from_head(kb):
    """BG-xicqvm4t: refs are resolved at HEAD, not in the working tree. A fact reworded but not committed is not stale
    (HEAD still holds it) and is once committed; a ref to an article written but not committed is missing, and
    resolves once committed."""
    repo, iid = kb
    art = repo / "kb" / "public" / "demo" / "tool.md"
    edit(repo, iid, knowledge={"refs": [f"public/demo/tool.md#{key()}"]})
    art.write_text(ARTICLE.replace("print their version", "print their build"), encoding="utf-8", newline="\n")
    code, out = b(repo, "check")
    assert code == 0 and "stale=0" in out, out  # planted: an uncommitted rewording
    commit(repo, "reword")
    code, out = b(repo, "check")
    assert code == 0 and "stale=1" in out, out
    new = repo / "kb" / "public" / "demo" / "fresh.md"
    new.write_text(ARTICLE.replace("demo/tool", "demo/fresh"), encoding="utf-8", newline="\n")
    edit(repo, iid, knowledge={"refs": ["demo/fresh"]})
    code, out = b(repo, "check")
    assert code == 1 and "no such topic" in out, out  # planted: an uncommitted article
    commit(repo, "fresh")
    code, out = b(repo, "check")
    assert code == 0 and "no such topic" not in out, out


def test_knowledge_refs_shape_is_checked(kb):
    repo, iid = kb
    for bad in ("text", {"asks": []}, {"ask": "one question"}, {"ask": [""]}, {"refs": [1]}):
        edit(repo, iid, knowledge=bad)
        code, out = b(repo, "check")
        assert code == 1 and "knowledge" in out, (bad, out)
    edit(repo, iid, knowledge={"ask": ["What does the demo print?"], "refs": []})
    assert b(repo, "check")[0] == 0


def test_knowledge_shape_checked_on_every_item(kb):
    """BG-74435353 planted: a malformed knowledge field fails check on a draft, done or dropped item, one of a planned
    sprint and an epic outside any sprint, not only on a worked item; an absent ref on those items still passes, since
    only the refs wait until the item is worked."""
    repo, iid = kb
    waiting = worked_carrier(repo, "Waiting", "Planned sprint", start=False)
    epic = b(repo, "new", "epic", "--title", "Outcome", "--goal", "an outcome")[0] == 0 and item(repo, "Outcome")["id"]
    for who, status in ((iid, "draft"), (iid, "done"), (iid, "dropped"), (waiting, None), (epic, None)):
        if status:
            edit(repo, who, status=status)
        edit(repo, who, knowledge="text")
        code, out = b(repo, "check")
        assert code == 1 and "knowledge must be {ask" in out, (who, status, out)
        edit(repo, who, knowledge={"refs": ["demo/absent"]})
        code, out = b(repo, "check")
        assert "knowledge" not in out.split("backlog check:")[0], (who, status, out)  # refs wait for a worked item
        edit(repo, who, knowledge={"ask": ["What does the demo print?"]})


def test_knowledge_refs_active_items_only(kb):
    """check validates knowledge refs, and counts a reworded fact as stale, only on an item that is todo or doing in an
    active sprint: a done, dropped or draft item, an item of a planned sprint and an epic outside any sprint keep
    theirs unchecked, so a kb refresh that renames an article they cite does not turn the gate red."""
    repo, iid = kb
    waiting = worked_carrier(repo, "Waiting", "Planned sprint", start=False)
    epic = b(repo, "new", "epic", "--title", "Outcome", "--goal", "an outcome")[0] == 0 and item(repo, "Outcome")["id"]
    for who in (iid, waiting, epic):
        edit(repo, who, knowledge={"refs": ["demo/absent"]})
    code, out = b(repo, "check")
    assert code == 1 and out.count("knowledge ref") == 1 and f"{iid} “Carrier”: knowledge ref" in out, out  # planted
    for status in ("done", "dropped", "draft"):
        edit(repo, iid, status=status)
        code, out = b(repo, "check")
        assert "knowledge ref" not in out and "no such topic" not in out, (status, out)
    edit(repo, iid, status="doing")
    assert "no such topic" in b(repo, "check")[1]  # doing counts as worked
    edit(repo, iid, knowledge={"refs": [f"public/demo/tool.md#{key()}"]}, status="todo")
    (repo / "kb" / "public" / "demo" / "tool.md").write_text(ARTICLE.replace("print their version", "print their build"),
                                                              encoding="utf-8", newline="\n")
    commit(repo, "reword")  # refs are read at HEAD
    code, out = b(repo, "check")
    assert code == 0 and "errors=0 stale=1" in out, out  # the worked item's reworded fact is counted; the others' refs are not
    edit(repo, iid, status="dropped")
    code, out = b(repo, "check")
    assert "stale=0" in out, out


def test_knowledge_refs_without_a_kb_are_refused(repo):
    carrier = worked_carrier(repo)
    edit(repo, carrier, knowledge={"refs": ["S100"]})
    code, out = b(repo, "check")
    assert code == 1 and "no such source id" in out, out


# ---- knowledge state: show, next and horizon run the pack on each ask and ref of an item's `knowledge`

# every bl_ module is copied, so a new one never needs an edit here
KS_TOOLS = ("backlog.py",) + tuple(sorted(f.name for f in Path(TOOLS).glob("bl_*.py"))) + ("kbcommon.py", "kbfacts.py", "kbid.py", "ql_base.py", "aliases.csv")


KS_SOURCES = ("id,url,title,superseded_by,used_in\n"
              "S100,https://example.com/a,Zorbex agent guide,,demo/tool.md\n"
              "S101,https://example.com/b,Plimt gadget firmware notes,,demo/gadget.md\n")


KS_SUPERSEDED = KS_SOURCES.replace("Zorbex agent guide,,", "Zorbex agent guide,S101,")


KS_FACTS = ["The zorbex agent prints its build number at startup.", "The zorbex agent retries failed uploads three times."]


KS_GOOD = "How many times does the zorbex agent retry failed uploads?"


KS_CHECK = KS_GOOD[:-1] + " for Plimt?"  # `good`, with a `check:` line: the lead article never mentions Plimt


KS_WEAK = "Does the zorbex agent retry uploads with plimt firmware in quasar flash?"


KS_NONE = "How do I configure the wumpus frobnicator?"


def ks_article(topic, title, facts, source="S100"):
    return (f"---\ntopic: {topic}\nstatus: partial\n---\n\n# {title}\n\n## Facts\n"
            + "".join(f"- {f} [DOC {source}]\n" for f in facts))


def ks_fact(n):
    """The `<root>/<path>#<key>` ref of the n-th fact of the zorbex article."""
    return f"public/demo/tool.md#{key(KS_FACTS[n] + ' [DOC S100]')}"


def ks_states(out):
    """{text: state} of the `knowledge <state> ask|ref: <text>` lines of an output (a trailing `(why)` cut off)."""
    found = {}
    for ln in out.splitlines():
        m = re.match(r"\s*knowledge (\w+)\s+(?:ask|ref): (.*)$", ln)
        if m:
            found[re.sub(r" \([^()]*\)$", "", m.group(2))] = m.group(1)
    return found


class Ks:
    """A started sprint (the `sprint` fixture) with its own copy of the tools and a small kb of invented words, so the
    pack that show, next and horizon run answers from a corpus the test controls: two articles (zorbex, plimt) among
    twelve filler ones, one QK answer, two sources and an empty conflicts ledger."""

    def __init__(self, sprint):
        self.repo, self.tk, self.bg, self.sp = sprint["repo"], sprint["tk"], sprint["bg"], sprint["sp"]
        self.root = self.repo / "kb" / "public"
        (self.repo / "_tools").mkdir()
        for f in KS_TOOLS:
            shutil.copy(os.path.join(TOOLS, f), self.repo / "_tools" / f)
        (self.root / "demo").mkdir(parents=True)
        files = {
            "_root.md": "---\nroot: public\nid_prefix: S\nvisibility: public\n---\n\n# public\n",
            "_sources.csv": KS_SOURCES,
            "_answers.md": f"# Answers\n\n## QK-zorbex-retries. {KS_GOOD}\n- Three times. [DOC S100]\n",
            "_conflicts.md": "# Conflicts\n",
            "demo/tool.md": ks_article("demo/tool", "Zorbex sync agent", KS_FACTS),
            "demo/gadget.md": ks_article("demo/gadget", "Plimt gadget", [
                "The plimt gadget stores firmware in quasar flash.", "The plimt gadget resets after a wobble timeout."],
                                         "S101"),
            **{f"demo/filler{i}.md": ks_article(f"demo/filler{i}", f"Filler {i}", [
                f"Filler{i}a widget{i}b gizmo{i}c runs {i}d.", f"Sprocket{i}e flange{i}f."]) for i in range(12)},
        }
        for rel, text in files.items():
            self.write(rel, text)
        self.env = {k: v for k, v in os.environ.items() if k not in ("KB_ROOTS", "CLAUDE_PLUGIN_DATA")} | {
            "KB_INDEX": "0"}

    def write(self, rel, text):
        """Write a kb file and commit it: knowledge refs are read at HEAD (BG-xicqvm4t)."""
        (self.root / rel).write_text(text, encoding="utf-8", newline="\n")
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-q", "--allow-empty", "-m", f"kb {rel}")

    def run(self, *a):
        """The copy of backlog.py in the repository, whose own kb is the one its pack reads."""
        p = subprocess.run([sys.executable, str(self.repo / "_tools" / "backlog.py"), *a], cwd=self.repo,
                           capture_output=True, text=True, encoding="utf-8", env=self.env)
        return p.returncode, p.stdout + p.stderr

    def know(self, asks=(), refs=(), item=None):
        edit(self.repo, item or self.tk, knowledge={"ask": list(asks), "refs": list(refs)})

    def show(self):
        code, out = self.run("show", self.tk)
        assert code == 0, out
        return out


@pytest.fixture
def ks(sprint):
    return Ks(sprint)


def test_knowledge_state_each_ask_has_one_of_five_states(ks):
    """A planted ask for each coverage: good, a good with a check line, weak and none."""
    ks.know(asks=[KS_GOOD, KS_CHECK, KS_WEAK, KS_NONE])
    out = ks.show()
    assert ks_states(out) == {KS_GOOD: "sufficient", KS_CHECK: "partial", KS_WEAK: "partial", KS_NONE: "unknown"}, out
    assert "check: line flags a possible false good" in out and "coverage weak" in out
    assert "the kb does not cover it" in out


def test_knowledge_state_refs_of_every_kind_are_sufficient_when_the_kb_covers_them(ks):
    refs = ["demo/tool", "public/demo/tool", "QK-zorbex-retries", "S100", ks_fact(1)]
    ks.know(refs=refs)
    out = ks.show()
    assert ks_states(out) == dict.fromkeys(refs, "sufficient"), out


def test_knowledge_state_reworded_fact_is_stale_and_a_missing_ref_is_unknown(ks):
    """The fact reworded (planted) is stale; an article, answer or source the kb lacks is unknown, never stale."""
    ks.know(refs=[ks_fact(1), "demo/absent", "QK-no-answer", "S999"])
    assert ks_states(ks.show())[ks_fact(1)] == "sufficient"
    art = ks.root / "demo" / "tool.md"
    ks.write("demo/tool.md", art.read_text(encoding="utf-8").replace("three times", "five times"))
    out = ks.show()
    assert ks_states(out) == {ks_fact(1): "stale", "demo/absent": "unknown", "QK-no-answer": "unknown",
                              "S999": "unknown"}, out
    assert f"fact {ks_fact(1).rpartition('#')[2]} is no longer in public/demo/tool.md" in out


def test_knowledge_state_superseded_source_makes_refs_and_asks_stale(ks):
    """S100 superseded (planted): the source, a fact citing it and an ask whose pack cites it are stale; the source
    S101 that nothing supersedes is not."""
    ks.know(asks=[KS_GOOD], refs=["S100", "S101", ks_fact(0)])
    assert set(ks_states(ks.show()).values()) == {"sufficient"}
    ks.write("_sources.csv", KS_SUPERSEDED)
    out = ks.show()
    assert ks_states(out) == {KS_GOOD: "stale", "S100": "stale", "S101": "sufficient", ks_fact(0): "stale"}, out
    assert "source S100 is superseded by S101" in out


def test_knowledge_state_open_conflict_entry_makes_the_article_conflicting_until_settled(ks):
    """An open `_conflicts.md` entry naming demo/tool (planted): the topic, its fact, an ask its article answers and
    a source the entry names are conflicting, another article is not. A `Resolved` note closes the entry."""
    ks.know(asks=[KS_GOOD], refs=["demo/tool", ks_fact(0), "S100", "demo/gadget"])
    entry = "- The two pages disagree on the retry count (S100). (topic: demo/tool)\n"
    ks.write("_conflicts.md", "# Conflicts\n\n" + entry)
    out = ks.show()
    assert ks_states(out) == {KS_GOOD: "conflicting", "demo/tool": "conflicting", ks_fact(0): "conflicting",
                              "S100": "conflicting", "demo/gadget": "sufficient"}, out
    assert "open entry at public/_conflicts.md:3" in out
    ks.write("_conflicts.md", "# Conflicts\n\n" + entry + "  - Resolved 2026-09-29: the later page settles it.\n")
    assert set(ks_states(ks.show()).values()) == {"sufficient"}


def test_knowledge_state_reviewed_note_closes_only_when_not_a_source_disagreement(ks):
    """A `Reviewed <date>, not a source disagreement` note closes an entry like `Resolved`; a `Reviewed <date>, still
    open` note leaves it open (both planted)."""
    ks.know(refs=["demo/tool"])
    entry = "- The two pages disagree on the retry count (S100). (topic: demo/tool)\n"
    ks.write("_conflicts.md", "# Conflicts\n\n" + entry + "  - Reviewed 2026-09-28, still open: not re-read.\n")
    assert ks_states(ks.show()) == {"demo/tool": "conflicting"}
    ks.write("_conflicts.md", "# Conflicts\n\n" + entry
             + "  - Reviewed 2026-09-28, not a source disagreement: two quantities; closed.\n")
    assert ks_states(ks.show()) == {"demo/tool": "sufficient"}


def test_knowledge_state_stale_wins_over_conflicting_and_both_over_coverage(ks):
    ks.know(refs=["demo/tool", ks_fact(0)])
    ks.write("_conflicts.md", "# Conflicts\n\n- Disagreement. (topic: demo/tool)\n")
    assert set(ks_states(ks.show()).values()) == {"conflicting"}
    ks.write("_sources.csv", KS_SUPERSEDED)
    assert set(ks_states(ks.show()).values()) == {"stale"}


def test_knowledge_state_next_and_horizon_print_it_and_the_hook_runs_no_pack(ks, monkeypatch, capsys):
    ks.know(asks=[KS_GOOD, KS_NONE], refs=["demo/tool"])
    ks.know(asks=[KS_GOOD, KS_NONE], refs=["demo/tool"], item=ks.bg)  # whichever of the two is next
    want = {KS_GOOD: "sufficient", KS_NONE: "unknown", "demo/tool": "sufficient"}
    for cmd in (("next", "--sprint", ks.sp, "--all"), ("horizon", "--sprint", ks.sp)):
        code, out = ks.run(*cmd)
        assert code == 0 and ks_states(out) == want, (cmd, out)
    code, out = ks.run("horizon", "--sprint", ks.sp, "--hook")
    assert code == 0 and "knowledge" not in out, out
    # in this process with the pack counted: the hook asks it nothing, horizon asks it once per ask and ref
    calls = []

    def canned(self, question):
        calls.append(question)
        return {"verdict": "good", "sources": [], "paths": [], "unmatched": [], "spread": None}

    monkeypatch.setattr(bl_check.KnowledgeState, "pack", canned)
    monkeypatch.setattr(bl_check, "KB_HOME", ks.repo.resolve())  # this process reads ks.repo's kb as its own
    bl = backlog.Backlog(ks.repo)
    backlog.cmd_horizon(bl, argparse.Namespace(sprint=ks.sp, hook=True))
    assert calls == [] and "knowledge" not in capsys.readouterr().out
    backlog.cmd_horizon(bl, argparse.Namespace(sprint=ks.sp, hook=False))
    assert len(calls) == 3, calls
    assert "knowledge sufficient" in capsys.readouterr().out


def test_knowledge_state_root_uses_its_own_refs(ks, tmp_path):
    """BG-aycs7kml: a conflict on demo/tool closed only in DIR (planted: open in the other clone). DIR's own
    backlog.py derives the state from DIR's kb; another clone's backlog.py with --root DIR, whose pack and ledgers
    read its own kb, derives none and says so, in show, next and horizon, never a state mixed from the two."""
    entry = "- The two pages disagree on the retry count (S100). (topic: demo/tool)\n"
    ks.know(refs=["demo/tool"])
    ks.know(refs=["demo/tool"], item=ks.bg)
    other = tmp_path / "other"
    shutil.copytree(ks.repo, other)
    (other / "kb" / "public" / "_conflicts.md").write_text("# Conflicts\n\n" + entry, encoding="utf-8", newline="\n")
    ks.write("_conflicts.md", "# Conflicts\n\n" + entry + "  - Resolved 2026-09-29: the later page settles it.\n")
    assert ks_states(ks.show()) == {"demo/tool": "sufficient"}
    for cmd in (("show", ks.tk), ("next", "--sprint", ks.sp, "--all"), ("horizon", "--sprint", ks.sp)):
        p = subprocess.run([sys.executable, str(other / "_tools" / "backlog.py"), "--root", str(ks.repo), *cmd],
                           cwd=other, capture_output=True, text=True, encoding="utf-8", env=ks.env)
        out = p.stdout + p.stderr
        assert p.returncode == 0 and ks_states(out) == {}, (cmd, out)
        assert bl_check.OTHER_CLONE in out, (cmd, out)
    code, out = ks.run("--root", str(ks.repo), "show", ks.tk)  # --root naming the clone itself still derives it
    assert code == 0 and ks_states(out) == {"demo/tool": "sufficient"}, out


def test_knowledge_state_is_reported_never_stored_and_never_changes_readiness(ks):
    ready = ks.run("next", "--sprint", ks.sp, "--all")[1]
    ks.know(asks=[KS_NONE], refs=["demo/absent"])  # every state a non-sufficient one: still nothing it waits on
    before = {p.name: p.read_bytes() for p in (ks.repo / backlog.REL_DIR).glob("*.json")}
    with_state = ks.run("next", "--sprint", ks.sp, "--all")[1]
    assert [ln for ln in with_state.splitlines() if not ln.strip().startswith("knowledge")] == ready.splitlines()
    assert ks_states(with_state) == {KS_NONE: "unknown", "demo/absent": "unknown"}
    assert ks.show().rstrip().endswith("ready")
    ks.run("horizon")
    assert {p.name: p.read_bytes() for p in (ks.repo / backlog.REL_DIR).glob("*.json")} == before


def test_knowledge_state_costs_nothing_for_items_without_knowledge(sprint):
    """No item carries knowledge: next and horizon never load the pack (kbfacts stays unimported)."""
    code = ("import sys; sys.path.insert(0, %r); import backlog\n"
            "for cmd in (['next', '--all'], ['horizon']):\n"
            "    backlog.main(['--root', %r] + cmd)\n"
            "print('LOADED' if 'kbfacts' in sys.modules else 'NOT LOADED')\n") % (TOOLS, str(sprint["repo"]))
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0 and p.stdout.strip().endswith("NOT LOADED"), p.stdout + p.stderr


def test_knowledge_state_against_the_repositorys_own_kb():
    """The real pack of this clone, for an item of this clone (another clone's state is not derived:
    test_knowledge_state_root_uses_its_own_refs): an eval-set question it answers `good` with no check line, in an
    article with no open conflict entry, is sufficient; one about nothing the kb holds is unknown. The ledger entries
    are the kb's own state, so the question is picked, not named."""
    import rag

    class Clone:
        root, items = backlog.ROOT, {}

    state = bl_check.KnowledgeState(Clone())
    good = next(c["question"] for _, c in rag.eval_cases() if c["expect_verdict"] == "good"
                and state.of_ask(c["question"])[0] == "sufficient")
    Clone.items = {"TK-aaaaaaaa": {"knowledge": {"ask": [good, KS_NONE]}}}
    out = "\n".join(bl_check.knowledge_lines(Clone(), "TK-aaaaaaaa"))
    assert ks_states(out) == {good: "sufficient", KS_NONE: "unknown"}, out


def test_knowledge_state_judge_maps_every_verdict(monkeypatch):
    """The mapping alone, the pack canned: none -> unknown, weak -> partial, good -> sufficient, and a good with a
    check line (an unmatched name, or facts spread apart) -> partial."""
    class Empty:
        root, items = "/nonexistent", {}

    ks = bl_check.KnowledgeState(Empty())
    base = {"sources": [], "paths": [], "unmatched": [], "spread": None}
    table = [({"verdict": "none"}, "unknown"), ({"verdict": "weak"}, "partial"), ({"verdict": "good"}, "sufficient"),
             ({"verdict": "good", "unmatched": ["plimt"]}, "partial"),
             ({"verdict": "good", "spread": (1, 4)}, "partial")]
    for res, state in table:
        monkeypatch.setattr(ks, "pack", lambda q, res=res: base | res)
        assert ks.of_ask("q")[0] == state, res
    assert {s for _, s in table} == set(bl_check.STATES) - {"stale", "conflicting"}


def test_backlog_state_paths_check_warns_of_unchecked_ways_state_changes(repo):
    """check warns of an open item whose goal reads an item's status or presence when its checks name fewer than
    every way the state changes (BG-qks4ikyr planted: a sweep checked only done); naming all five, a goal that reads no
    state, and a done item are quiet."""
    cmd = lambda k: argstr(["python3", "_tools/tests.py", "-k", k])  # noqa: E731
    goal = "A sweep reads each item's status and presence"
    assert b(repo, "new", "story", "--title", "Sweep", "--goal", goal, "--check", cmd("sweep_done"))[0] == 0
    sw = item(repo, "Sweep")["id"]
    code, out = b(repo, "check")
    assert code == 0 and "warnings=1" in out and sw in out, out
    for way in ("drop inside a sprint", "drop outside a sprint", "close", "release"):
        assert way in out, out
    assert "state changes: done," not in out, out  # the path its check names is not listed missing
    edit(repo, sw, checks=[{"run": ["python3", "_tools/tests.py", "-k",
                                    "sweep_done or sweep_drop_in_sprint or sweep_drop_outside or sweep_close "
                                    "or sweep_release"]}])
    code, out = b(repo, "check")
    assert code == 0 and "warnings=0" in out, out
    edit(repo, sw, checks=[{"run": ["python3", "_tools/tests.py", "-k", "sweep_done or sweep_close"]}])
    code, out = b(repo, "check")
    assert "warnings=1" in out and "drop inside a sprint" in out and "release" in out, out
    edit(repo, sw, goal="A sweep prints a table")
    code, out = b(repo, "check")
    assert "warnings=0" in out, out
    edit(repo, sw, goal=goal, status="done")
    code, out = b(repo, "check")
    assert "warnings=0" in out and "state changes" not in out, out


def test_facade_touch_warning():
    """ST-clsddgen: an open item whose touches name a facade and none of its modules is warned of, naming the prefix
    the map gives; a module named beside it, a glob that covers one, a module still to be created, a done item and a
    touch of no facade are quiet."""
    import types
    root = Path(TOOLS).parent

    def warns(touches, status="todo"):
        bl = types.SimpleNamespace(root=root, label=lambda i: i,
                                   items={"ST-aaaaaaaa": {"kind": "story", "status": status, "touches": touches}})
        return bl_check.facade_touch_warnings(bl)

    (w,) = warns(["_tools/backlog.py", "kb/_self/backlog.md"])
    assert "facade _tools/backlog.py" in w and "_tools/bl_*.py" in w, w
    (w,) = warns(["_tools/kbgit.py"])
    assert "_tools/kg_*.py" in w, w
    assert len(warns(["_tools/querylog.py", "_tools/benchmarks.py"])) == 2
    for quiet in (["_tools/backlog.py", "_tools/bl_check.py"], ["_tools/backlog.py", "_tools/bl_*.py"],
                  ["_tools/backlog.py", "_tools/**"], ["_tools/kbgit.py", "_tools/kg_new.py"], ["_tools/rag.py"]):
        assert warns(quiet) == [], quiet
    assert warns(["_tools/backlog.py"], status="done") == []


def test_gate_do_warns_per_option():
    """BG-ynaowysf: a blocking gate with two options and a do for one warns once, for the other option; with a do
    for both it is quiet."""
    import types
    gate = {"id": "g1", "kind": "blocking", "options": ["a", "b"], "do": {"a": ["git", "status"]}}
    bl = types.SimpleNamespace(items={"ST-aaaaaaaa": {"status": "todo", "gates": [gate]}}, label=lambda i: i)
    warns = bl_check.gate_do_warnings(bl)
    assert len(warns) == 1 and "option 'b'" in warns[0], warns
    gate["do"]["b"] = ["git", "log"]
    assert bl_check.gate_do_warnings(bl) == []


def test_gate_option_names_its_command(repo):
    """check warns of each option of an unanswered blocking gate of an open item that carries no do; an argv or an
    item id on every option, an answer, a provisional gate and a done item are quiet; do is validated against the
    options."""
    assert b(repo, "new", "story", "--title", "Decide", "--goal", "Pick a name", "--touch", "src/**",
             "--check", argstr(is_file("src/b.txt")))[0] == 0
    sid = item(repo, "Decide")["id"]
    args = ("gate", "add", sid, "--question", "Which name?", "--option", "keep", "--option", "rename",
            "--recommendation", "keep")
    assert b(repo, *args)[0] == 0
    code, out = b(repo, "check")
    assert code == 0 and "warnings=2" in out and "blocking gate g1 has no `do` for option 'keep'" in out and sid in out, out
    # a do naming no option is refused, as is one with neither an argv nor an existing item
    assert b(repo, "gate", "add", sid, "--id", "g2", "--question", "Other?", "--option", "a", "--option", "b",
             "--recommendation", "a", "--do", "c=echo hi")[0] == 2
    assert b(repo, "gate", "add", sid, "--id", "g2", "--question", "Other?", "--option", "a", "--option", "b",
             "--recommendation", "a", "--do", "a=")[0] == 2
    gates = item(repo, "Decide")["gates"]
    edit(repo, sid, gates=[dict(gates[0], do={"rename": "ST-aaaaaaaa"})])
    code, out = b(repo, "check")
    assert code == 1 and "needs an argv" in out, out
    edit(repo, sid, gates=[dict(gates[0], do={"rename": ["git", "mv", "a", "b"]})])
    code, out = b(repo, "check")
    assert code == 0 and "warnings=1" in out and "has no `do` for option 'keep'" in out, out  # one do silences no other
    edit(repo, sid, gates=[dict(gates[0], do={"rename": ["git", "mv", "a", "b"], "keep": "ST-aaaaaaaa"})])
    code, out = b(repo, "check")
    assert code == 1 and "warnings=0" in out, out  # ST-aaaaaaaa is no item: needs an argv, but no do is missing
    edit(repo, sid, gates=[dict(gates[0], do={"rename": ["git", "mv", "a", "b"], "keep": ["git", "status"]})])
    code, out = b(repo, "check")
    assert code == 0 and "warnings=0" in out, out
    # the same gate given its do by gate add on a fresh item
    assert b(repo, "new", "story", "--title", "Decide two", "--goal", "Pick again", "--touch", "src/**",
             "--check", argstr(is_file("src/b.txt")))[0] == 0
    two = item(repo, "Decide two")["id"]
    assert b(repo, "gate", "add", two, "--question", "Which?", "--option", "keep", "--option", "drop",
             "--recommendation", "keep", "--do", f"drop={sid}", "--do", "keep=echo ok")[0] == 0
    assert item(repo, "Decide two")["gates"][0]["do"] == {"drop": sid, "keep": ["echo", "ok"]}
    code, out = b(repo, "check")
    assert "warnings=0" in out, out
    # provisional, answered and done are quiet
    edit(repo, sid, gates=[dict(gates[0], kind="provisional")])
    assert "warnings=0" in b(repo, "check")[1]
    edit(repo, sid, gates=[dict(gates[0], answer="keep", by="operator")])
    assert "warnings=0" in b(repo, "check")[1]
    edit(repo, sid, gates=[gates[0]], status="done")
    assert "warnings=0" in b(repo, "check")[1]
