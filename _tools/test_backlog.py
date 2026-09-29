"""backlog.py in a throwaway git repository: items are created, validated, scheduled, finished and deleted.

Each refusal has a planted failure: a bug whose repro passes, a non-canonical file, a cycle, a blocking gate an
agent answers, a sprint started without the operator, a failing check, a commit outside `touches` (and the revert
that clears it), a review with an unconfirmed provisional answer, a malformed KB-Work trailer, a worked item of a
planned sprint, a KB-Work id whose item is unclaimed or not in a started sprint (work committed before its claim
commit included), and red pipelines that fail
the same way (one bug) or differently (a second), or the same way as a closed bug (a new one). The repository's
own backlog must pass `backlog.py check`.
"""
import argparse, json, os, re, shutil, subprocess, sys
from pathlib import Path

import pytest

import backlog
import kbgit
import ql_deliver

TOOLS = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(TOOLS, "backlog.py")


def sh(root, *a):
    subprocess.run(list(a), cwd=root, check=True, capture_output=True)


def b(root, *a):
    p = subprocess.run([sys.executable, TOOL, "--root", str(root), *a], cwd=root, capture_output=True, text=True,
                       encoding="utf-8")
    return p.returncode, p.stdout + p.stderr


def item(root, title):
    for f in (Path(root) / backlog.REL_DIR).glob("*.json"):
        it = json.loads(f.read_text(encoding="utf-8"))
        if it["title"] == title:
            return it
    raise AssertionError(title)


def edit(root, iid, **kw):
    f = Path(root) / backlog.REL_DIR / f"{iid}.json"
    it = json.loads(f.read_text(encoding="utf-8"))
    it.update(kw)
    f.write_text(backlog.canonical(it), encoding="utf-8", newline="\n")


def commit(root, msg, work=None):
    sh(root, "git", "add", "-A")
    sh(root, "git", "commit", "-qm", msg, *(["-m", f"KB-Work: {work}"] if work else []))


@pytest.fixture(autouse=True)
def no_git_location(monkeypatch):
    """A pre-push hook in a worktree sets these; inherited, git init and commit would act on the real repository."""
    for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture(autouse=True)
def gate_jobs(monkeypatch):
    """No job is a gate by default (every CI job is manual); these tests read pipelines with the two once-gate jobs
    named, and the default is proved in test_querylog.py's TestNoGateJobs."""
    monkeypatch.setattr(ql_deliver, "GATE_JOBS", ("kb-tests", "kb-trailers"))


@pytest.fixture
def repo(tmp_path):
    sh(tmp_path, "git", "init", "-q")
    sh(tmp_path, "git", "config", "user.email", "agent@example.com")
    sh(tmp_path, "git", "config", "user.name", "agent")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.txt").write_text("a\n", encoding="utf-8")
    commit(tmp_path, "init")
    return tmp_path


@pytest.fixture
def sprint(repo):
    """An approved, started sprint with a story, its task and a bug."""
    assert b(repo, "new", "epic", "--title", "Epic", "--goal", "outcome")[0] == 0
    ep = item(repo, "Epic")["id"]
    b(repo, "new", "sprint", "--title", "Sprint", "--goal", "ship b")
    sp = item(repo, "Sprint")["id"]
    b(repo, "new", "story", "--title", "Story", "--parent", ep, "--sprint", sp, "--goal", "b exists",
      "--check", "test -f src/b.txt")
    st = item(repo, "Story")["id"]
    b(repo, "new", "task", "--title", "Task", "--parent", st, "--goal", "b written", "--touch", "src/**",
      "--check", "test -f src/b.txt")
    b(repo, "new", "bug", "--title", "Bug", "--sprint", sp, "--severity", "S3", "--repro", "test -f src/c.txt",
      "--goal", "c exists")
    assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
    code, out = b(repo, "start", sp)
    assert code == 0, out
    return {"repo": repo, "ep": ep, "sp": sp, "st": st, "tk": item(repo, "Task")["id"], "bg": item(repo, "Bug")["id"],
            "rv": item(repo, "Review sprint: Sprint")["id"]}


def test_new_items_validate(sprint):
    code, out = b(sprint["repo"], "check")
    assert code == 0 and "errors=0" in out, out


def test_bug_repro_must_fail_now(repo):
    code, out = b(repo, "new", "bug", "--title", "Not a bug", "--severity", "S4", "--repro", "true", "--goal", "x")
    assert code == 1 and "must fail" in out


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


def test_task_needs_parent_and_touches(repo):
    b(repo, "new", "epic", "--title", "E", "--goal", "g")
    code, out = b(repo, "new", "task", "--title", "Orphan", "--goal", "g")
    assert "needs a parent" in out and "touches missing" in out


def test_only_operator_answers_blocking_gates_and_starts_sprints(repo):
    b(repo, "new", "sprint", "--title", "S", "--goal", "g")
    sp = item(repo, "S")["id"]
    assert b(repo, "start", sp)[0] == 1
    code, out = b(repo, "answer", sp, "start", "--answer", "approve", "--by", "agent")
    assert code == 1 and "only the operator" in out
    assert b(repo, "answer", sp, "start", "--provisional")[0] == 1


def test_next_orders_s1_bugs_first(sprint):
    repo = sprint["repo"]
    edit(repo, sprint["bg"], severity="S1")
    code, out = b(repo, "next", "--all")
    assert code == 0
    assert out.splitlines()[0].startswith(sprint["bg"])
    assert sprint["st"] not in out  # a story with an open task is not ready itself
    assert sprint["rv"] not in out  # the review waits on every other item


def test_done_refuses_failing_check_and_scope_then_passes(sprint):
    repo, tk = sprint["repo"], sprint["tk"]
    assert b(repo, "claim", tk, "--by", "agent-1")[0] == 0
    (repo / "src" / "x.txt").write_text("x\n", encoding="utf-8")
    commit(repo, "start", tk)
    code, out = b(repo, "done", tk)
    assert code == 1 and "check(s) failed" in out
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    (repo / "stray.txt").write_text("x\n", encoding="utf-8")
    commit(repo, "write b", tk)
    code, out = b(repo, "done", tk)
    assert code == 1 and "stray.txt, outside touches" in out
    sh(repo, "git", "rm", "-q", "stray.txt")
    commit(repo, "revert stray", tk)
    code, out = b(repo, "done", tk)
    assert code == 0, out
    it = item(repo, "Task")
    assert it["status"] == "done" and it["evidence"]["commit"] and "claimed_by" not in it


def test_done_refuses_kb_work_outside_trailers(sprint):
    """A KB-Work line in a paragraph before Co-Authored-By is no trailer for git: done sees no commit and refuses."""
    repo, tk = sprint["repo"], sprint["tk"]
    assert b(repo, "claim", tk, "--by", "agent-1")[0] == 0
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-qm", f"write b\n\nKB-Work: {tk}\n\nCo-Authored-By: A <a@example.com>")
    code, out = b(repo, "done", tk)
    assert code == 1 and "no commit on HEAD carries the trailer" in out
    (repo / "src" / "y.txt").write_text("y\n", encoding="utf-8")
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-qm", f"more\n\nCo-Authored-By: A <a@example.com>\nKB-Work: {tk}")
    code, out = b(repo, "done", tk)
    assert code == 0, out


def test_check_interpreter_argv(monkeypatch, tmp_path):
    """run_check starts a python3 or python check with sys.executable (on Windows the venv launcher's base interpreter
    directory holds a python3.exe, so the PATH plant below cannot fail there); other commands are left as they are."""
    seen = []
    monkeypatch.setattr(backlog.subprocess, "run", lambda argv, **k: seen.append(argv) or subprocess.CompletedProcess(argv, 0, "", ""))
    for cmd in ("python3", "python", "git"):
        assert backlog.run_check(tmp_path, {"run": [cmd, "x"]})[0]
    assert seen == [[sys.executable, "x"], [sys.executable, "x"], ["git", "x"]]


def test_check_interpreter_is_the_one_running_backlog(sprint, tmp_path):
    """A check naming python3 runs with backlog.py's own interpreter: a python3 on PATH that fails (the Windows Store
    alias exits 49) or none at all does not fail the item."""
    import shutil
    repo, tk = sprint["repo"], sprint["tk"]
    edit(repo, tk, checks=[{"run": ["python3", "-c", "import os, sys; sys.exit(0 if os.path.isfile('src/b.txt') else 1)"]}])
    commit(repo, "a python3 check")
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    commit(repo, "write b", tk)
    bad = tmp_path / "bad-python"
    bad.mkdir()
    for name in ("python3", "python"):
        (bad / name).write_text("#!/bin/sh\nexit 49\n", encoding="utf-8", newline="\n")
        (bad / name).chmod(0o755)
    # Windows cannot start the planted scripts: there PATH holds git's directory and no Python at all
    path = os.path.dirname(shutil.which("git")) if os.name == "nt" else str(bad) + os.pathsep + os.environ["PATH"]
    env = {**os.environ, "PATH": path}
    run = lambda *a: subprocess.run([sys.executable, TOOL, "--root", str(repo), *a], cwd=repo, capture_output=True,  # noqa: E731
                                    text=True, encoding="utf-8", env=env)
    assert run("claim", tk, "--by", "agent-1").returncode == 0
    p = run("done", tk)
    assert p.returncode == 0, p.stdout + p.stderr
    assert item(repo, "Task")["status"] == "done"


def test_done_refuses_uncommitted_changes_in_scope(sprint):
    repo = sprint["repo"]
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    code, out = b(repo, "done", sprint["tk"])
    assert code == 1 and "uncommitted" in out


def test_horizon_splits_reachable_from_gated(sprint):
    repo = sprint["repo"]
    edit(repo, sprint["bg"], gates=[{"id": "G1", "kind": "blocking", "question": "Fix or drop?",
                                     "recommendation": "fix"}])
    code, out = b(repo, "horizon")
    assert code == 0
    assert "2 more reachable" in out and "2 wait on the operator" in out
    assert "Fix or drop?" in out and "critical path (2 steps" in out
    code, out = b(repo, "horizon", "--hook")
    hook = json.loads(out)
    assert "Fix or drop?" in hook["hookSpecificOutput"]["additionalContext"]


def test_review_needs_confirmed_provisional_answers_and_close_deletes(sprint):
    repo, bg = sprint["repo"], sprint["bg"]
    edit(repo, bg, gates=[{"id": "G1", "kind": "provisional", "question": "Name c?", "recommendation": "c.txt"}])
    assert b(repo, "answer", bg, "G1", "--provisional")[0] == 0
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    (repo / "src" / "c.txt").write_text("c\n", encoding="utf-8")
    commit(repo, "b and c", f"{sprint['tk']}, {bg}")
    for iid in (sprint["tk"], sprint["st"], bg):
        code, out = b(repo, "done", iid)
        assert code == 0, out
    edit(repo, sprint["rv"], checks=[{"run": ["true"]}])
    commit(repo, "state")
    code, out = b(repo, "done", sprint["rv"])
    assert code == 1 and "provisional answer to confirm" in out
    assert b(repo, "answer", bg, "G1", "--confirm")[0] == 0
    assert b(repo, "done", sprint["rv"])[0] == 0
    assert b(repo, "done", sprint["ep"])[0] == 0
    code, out = b(repo, "close", sprint["sp"])
    assert code == 0, out
    assert not list((Path(repo) / backlog.REL_DIR).glob("*.json"))


def test_close_refuses_open_items(sprint):
    code, out = b(sprint["repo"], "close", sprint["sp"])
    assert code == 1 and "not finished" in out


def test_goal_condition_names_checks_and_scope(sprint):
    code, out = b(sprint["repo"], "goal", sprint["tk"])
    assert "`test -f src/b.txt` exits 0" in out and "src/**" in out and f"backlog.py done {sprint['tk']}" in out


def test_glob_scope():
    assert backlog.in_scope("_tools/backlog.py", ["_tools/*.py"])
    assert not backlog.in_scope("_tools/sub/x.py", ["_tools/*.py"])
    assert backlog.in_scope("_tools/sub/x.py", ["_tools/**"])
    assert backlog.in_scope("kb/public/_coverage.csv", [])


def test_work_trailer(monkeypatch):
    have = {("abc", "kb/_self/backlog/TK-aaaaaaaa.json")}
    monkeypatch.setattr(kbgit, "blob", lambda rev, rel: "{}" if (rev, rel) in have else None)
    assert kbgit.work_ok("abc", ["TK-aaaaaaaa"])
    assert not kbgit.work_ok("abc", ["TK-bbbbbbbb"])  # no such item
    assert not kbgit.work_ok("abc", ["task 7"])  # not an id
    assert not kbgit.work_ok("abc", ["TK-aaaaaaaa", "TK-aaaaaaaa"])  # a second line


def test_started_sprint_check_refuses_worked_item_of_planned_sprint(repo):
    """A planned sprint's items stay draft until start: a task under its story is created draft, and check reports a
    todo, doing or done item of it (planted: the story set to todo)."""
    b(repo, "new", "sprint", "--title", "Planned", "--goal", "g")
    sp = item(repo, "Planned")["id"]
    b(repo, "new", "story", "--title", "S", "--sprint", sp, "--goal", "g", "--check", "true")
    st = item(repo, "S")["id"]
    b(repo, "new", "task", "--title", "T", "--parent", st, "--goal", "g", "--touch", "src/**", "--check", "true")
    assert item(repo, "T")["status"] == "draft"
    assert b(repo, "check")[0] == 0
    edit(repo, st, status="todo")
    code, out = b(repo, "check")
    assert code == 1 and f"{st} “S”: status todo while its sprint {sp} “Planned” is planned" in out, out
    assert "not in a started sprint" in out


def test_started_sprint_work_state():
    """kbgit.work_state judges a KB-Work id by its item at the commit: claimed, in an active sprint."""
    files = {
        "SP-aaaaaaaa": {"kind": "sprint", "status": "active"},
        "SP-bbbbbbbb": {"kind": "sprint", "status": "planned"},
        "ST-aaaaaaaa": {"kind": "story", "status": "doing", "sprint": "SP-aaaaaaaa"},
        "TK-aaaaaaaa": {"kind": "task", "status": "doing", "parent": "ST-aaaaaaaa"},
        "TK-bbbbbbbb": {"kind": "task", "status": "todo", "parent": "ST-aaaaaaaa"},
        "ST-bbbbbbbb": {"kind": "story", "status": "doing", "sprint": "SP-bbbbbbbb"},
        "BG-aaaaaaaa": {"kind": "bug", "status": "doing"},
        "BG-bbbbbbbb": {"kind": "bug", "status": "done", "sprint": "SP-aaaaaaaa"},
        "ST-cccccccc": {"kind": "story", "status": "todo", "sprint": "SP-aaaaaaaa", "review": True},
    }
    load = lambda rel: json.dumps(files[Path(rel).stem]) if Path(rel).stem in files else None  # noqa: E731
    code = ["src/a.txt", "kb/_self/backlog/TK-aaaaaaaa.json"]
    state = lambda ids, paths=code: kbgit.work_state([ids], paths, load)  # noqa: E731
    assert state("TK-aaaaaaaa, BG-bbbbbbbb") == []  # claimed or done, in an active sprint (the task through its story)
    assert state("SP-aaaaaaaa, SP-bbbbbbbb, ST-cccccccc") == []  # the sprint and review items themselves
    assert ["not claimed" in x for x in state("TK-bbbbbbbb")] == [True]  # planted: unclaimed
    assert state("ST-bbbbbbbb") == ["ST-bbbbbbbb is not in a started sprint (SP-bbbbbbbb is planned)"]  # planted
    assert state("BG-aaaaaaaa") == ["BG-aaaaaaaa is not in a started sprint (no sprint)"]  # planted: no sprint
    assert state("TK-bbbbbbbb, ST-bbbbbbbb", ["kb/_self/backlog/TK-bbbbbbbb.json"]) == []  # a backlog-planning commit


def test_started_sprint_check_trailers_refuses_unclaimed_work(sprint, monkeypatch):
    """check-trailers (trailer_audit, which the pre-push hook and sync's gate run) refuses a commit not yet on
    origin/main whose KB-Work item is not claimed, and leaves one already on origin/main alone."""
    repo, tk = sprint["repo"], sprint["tk"]
    commit(repo, "plan")
    monkeypatch.setattr(kbgit, "KB", str(repo))
    kbgit._WANT.clear()
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    commit(repo, "write b", tk)  # planted: the task is todo, not claimed
    _, _, bad = kbgit.trailer_audit("HEAD", quiet=True)
    assert len(bad) == 1 and any("not claimed" in ln for ln in bad[0][1]), bad
    assert kbgit.trailer_audit("HEAD", quiet=True, work_state_on=False)[2] == []
    sh(repo, "git", "update-ref", "refs/remotes/origin/main", "HEAD")
    assert kbgit.trailer_audit("HEAD", quiet=True)[2] == []  # history stays as it is
    assert b(repo, "claim", tk, "--by", "agent-1")[0] == 0
    commit(repo, "claim", tk)  # a backlog-planning commit
    (repo / "src" / "b.txt").write_text("b2\n", encoding="utf-8")
    commit(repo, "write b again", tk)
    assert kbgit.trailer_audit("origin/main..HEAD", quiet=True)[2] == []


def test_claim_committed_before_work(sprint, monkeypatch):
    """/kb-item commits the claimed item file on its own right after `claim`, before any work commit: check-trailers
    reads the item as each commit has it, so a work commit made while the claim is uncommitted is refused (planted:
    the claim commit left out) and the same work after a claim commit passes."""
    repo, tk = sprint["repo"], sprint["tk"]
    rel = f"{backlog.REL_DIR}/{tk}.json"
    commit(repo, "plan")
    sh(repo, "git", "update-ref", "refs/remotes/origin/main", "HEAD")
    monkeypatch.setattr(kbgit, "KB", str(repo))
    kbgit._WANT.clear()

    def only(path, msg):
        sh(repo, "git", "add", "--", path)
        sh(repo, "git", "commit", "-qm", msg, "-m", f"KB-Work: {tk}")

    assert b(repo, "claim", tk, "--by", "agent-1")[0] == 0
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    only("src/b.txt", "write b")  # planted: the claim is still uncommitted
    _, _, bad = kbgit.trailer_audit("origin/main..HEAD", quiet=True)
    assert len(bad) == 1 and any("not claimed" in ln for ln in bad[0][1]), bad

    sh(repo, "git", "reset", "-q", "origin/main")  # keeps the claim and the work in the working tree
    kbgit._WANT.clear()
    only(rel, "claim")  # the claim commit: a backlog-planning commit
    only("src/b.txt", "write b")
    assert kbgit.trailer_audit("origin/main..HEAD", quiet=True)[2] == []


def test_repository_backlog_is_valid():
    code, out = b(os.path.dirname(TOOLS), "check")
    assert code == 0, out


# ---- knowledge: an item's asks and kb references, resolved against the kb of the clone

FACT = "Demo tools print their version. [DOC S100]"
ARTICLE = f"---\ntopic: demo/tool\nstatus: partial\n---\n\n# Demo tool\n\n## Facts\n- {FACT}\n"
CSV = "name,source,tag\nalpha,S100,DOC\n"


@pytest.fixture
def kb(repo):
    """The repository gets a public kb root: a source, a QK answer, an article with one fact and a data file; a
    story to carry `knowledge`."""
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
    b(repo, "new", "epic", "--title", "Carrier", "--goal", "carries knowledge")
    commit(repo, "kb")
    return repo, item(repo, "Carrier")["id"]


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
    code, out = b(repo, "check")
    assert code == 0 and "errors=0 stale=1" in out, out
    assert f"{iid} “Carrier”: stale knowledge: fact {key()} is no longer in public/demo/tool.md" in out
    art.unlink()  # planted: the article removed is missing, not stale
    code, out = b(repo, "check")
    assert code == 1 and "no article or data file" in out, out


def test_knowledge_refs_shape_is_checked(kb):
    repo, iid = kb
    for bad in ("text", {"asks": []}, {"ask": "one question"}, {"ask": [""]}, {"refs": [1]}):
        edit(repo, iid, knowledge=bad)
        code, out = b(repo, "check")
        assert code == 1 and "knowledge" in out, (bad, out)
    edit(repo, iid, knowledge={"ask": ["What does the demo print?"], "refs": []})
    assert b(repo, "check")[0] == 0


def test_knowledge_refs_without_a_kb_are_refused(repo):
    b(repo, "new", "epic", "--title", "Carrier", "--goal", "g")
    edit(repo, item(repo, "Carrier")["id"], knowledge={"refs": ["S100"]})
    code, out = b(repo, "check")
    assert code == 1 and "no such source id" in out, out


# ---- knowledge state: show, next and horizon run the pack on each ask and ref of an item's `knowledge`

KS_TOOLS = ("backlog.py", "kbcommon.py", "kbfacts.py", "kbid.py", "ql_base.py", "aliases.csv")
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
        (self.root / rel).write_text(text, encoding="utf-8", newline="\n")

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

    monkeypatch.setattr(backlog.KnowledgeState, "pack", canned)
    bl = backlog.Backlog(ks.repo)
    backlog.cmd_horizon(bl, argparse.Namespace(sprint=ks.sp, hook=True))
    assert calls == [] and "knowledge" not in capsys.readouterr().out
    backlog.cmd_horizon(bl, argparse.Namespace(sprint=ks.sp, hook=False))
    assert len(calls) == 3, calls
    assert "knowledge sufficient" in capsys.readouterr().out


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


def test_knowledge_state_against_the_repositorys_own_kb(sprint):
    """The real pack of this clone (`--root` names only where the backlog is): an eval-set question it answers `good`
    with no check line, in an article with no open conflict entry, is sufficient; one about nothing the kb holds is
    unknown. The ledger entries are the kb's own state, so the question is picked, not named."""
    import rag

    class Clone:
        root, items = backlog.ROOT, {}

    state = backlog.KnowledgeState(Clone())
    good = next(c["question"] for _, c in rag.eval_cases() if c["expect_verdict"] == "good"
                and state.of_ask(c["question"])[0] == "sufficient")
    edit(sprint["repo"], sprint["tk"], knowledge={"ask": [good, KS_NONE]})
    code, out = b(sprint["repo"], "show", sprint["tk"])
    assert code == 0 and ks_states(out) == {good: "sufficient", KS_NONE: "unknown"}, out


def test_knowledge_state_judge_maps_every_verdict(monkeypatch):
    """The mapping alone, the pack canned: none -> unknown, weak -> partial, good -> sufficient, and a good with a
    check line (an unmatched name, or facts spread apart) -> partial."""
    class Empty:
        root, items = "/nonexistent", {}

    ks = backlog.KnowledgeState(Empty())
    base = {"sources": [], "paths": [], "unmatched": [], "spread": None}
    table = [({"verdict": "none"}, "unknown"), ({"verdict": "weak"}, "partial"), ({"verdict": "good"}, "sufficient"),
             ({"verdict": "good", "unmatched": ["plimt"]}, "partial"),
             ({"verdict": "good", "spread": (1, 4)}, "partial")]
    for res, state in table:
        monkeypatch.setattr(ks, "pack", lambda q, res=res: base | res)
        assert ks.of_ask("q")[0] == state, res
    assert {s for _, s in table} == set(backlog.STATES) - {"stale", "conflicting"}


# ---- red-pipeline: a planted red and a green pipeline on origin's main, glab and gh replaced (no network)

def forge(monkeypatch, repo, pipelines, jobs=(), signed_in=True, logs=None):
    """origin is a GitLab project; `glab` answers the given pipelines (newest first), failed jobs and job logs
    (`logs`: job id -> trace text). The lists and the dict are read on every call: a test changes them in place."""
    sh(repo, "git", "remote", "add", "origin", "https://gitlab.example.com/team/kb.git")
    sh(repo, "git", "update-ref", "refs/remotes/origin/main", "HEAD")
    real = backlog.run

    def fake(argv, cwd=None):
        if argv[:2] == ["git", "fetch"]:
            return 0, "", ""
        if argv[0] in ("glab", "gh"):
            if argv[1] == "auth":
                return (0, "", "") if signed_in else (1, "", "not logged in")
            if argv[-1].endswith("/trace"):
                jid = int(argv[-1].split("/")[-2])
                return (0, logs[jid], "") if logs and jid in logs else (1, "", "404 Not Found")
            if "/jobs?" in argv[-1] and jobs is None:
                return 1, "", "500 Internal Server Error"
            return 0, json.dumps(jobs if "/jobs?" in argv[-1] else pipelines), ""
        return real(argv, cwd=cwd)

    monkeypatch.setattr(backlog, "run", fake)
    monkeypatch.setattr(backlog, "run_check", lambda root, c: (False, 1, ""))  # the repro fails: main is red


def head(repo):
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()


def bugs(repo):
    return [it for it in backlog.Backlog(repo).items.values() if it["kind"] == "bug"]


def red_pipeline(repo, *a):
    return backlog.main(["--root", str(repo), "red-pipeline", *a])


def test_red_pipeline_files_one_s2_bug_per_pipeline(repo, monkeypatch, capsys):
    sha = head(repo)
    forge(monkeypatch, repo, [{"id": 902, "sha": sha, "status": "running"},
                              {"id": 901, "sha": sha, "status": "failed", "web_url": "https://x/901"},
                              {"id": 900, "sha": sha, "status": "success"}],
          jobs=[{"name": "kb-tests-windows", "status": "failed"}])
    assert red_pipeline(repo) == 0
    (bug,) = bugs(repo)
    assert bug["severity"] == "S2" and bug["status"] == "draft" and "pipeline 901" in bug["title"]
    assert bug["repro"]["run"] == backlog.STATUS_REPRO
    assert backlog.validate(backlog.Backlog(repo)) == []
    capsys.readouterr()
    assert red_pipeline(repo) == 0  # the same pipeline again: named by the bug, nothing filed
    assert "already filed" in capsys.readouterr().out
    assert len(bugs(repo)) == 1


def test_red_pipeline_gate_job_is_s1_and_joins_the_active_sprint(sprint, monkeypatch):
    repo = sprint["repo"]
    forge(monkeypatch, repo, [{"id": 77, "sha": head(repo), "status": "failed"}],
          jobs=[{"name": "kb-tests", "status": "failed"}])
    assert red_pipeline(repo) == 0
    (bug,) = [x for x in bugs(repo) if "pipeline 77" in x["title"]]
    assert bug["severity"] == "S1" and bug["sprint"] == sprint["sp"] and bug["status"] == "todo"


GATE_PASSED = [{"id": 3, "name": "kb-trailers", "status": "success"}, {"id": 2, "name": "kb-tests", "status": "success"}]


def test_red_pipeline_green_files_nothing(repo, monkeypatch, capsys):
    forge(monkeypatch, repo, [{"id": 5, "sha": head(repo), "status": "success"},
                              {"id": 4, "sha": head(repo), "status": "failed"}], jobs=GATE_PASSED)
    assert red_pipeline(repo) == 0
    assert bugs(repo) == [] and "green" in capsys.readouterr().out
    assert red_pipeline(repo, "--status") == 0


def test_red_pipeline_unrun_gate_is_not_green(repo, monkeypatch, capsys):
    """The job list of a main pipeline whose status says success while no job ran (every job manual with
    allow_failure, the CI minutes quota spent): unverified, never green; each planted gate state keeps it so."""
    quota = {"status": "failed", "failure_reason": "ci_quota_exceeded", "allow_failure": True}
    pipelines = [{"id": 61, "sha": head(repo), "status": "success"}]
    jobs = [{"id": 15, "name": "kb-tests-windows", "status": "manual", "allow_failure": True},
            {"id": 14, "name": "kb-trailers", **quota}, {"id": 13, "name": "tool-stress", **quota},
            {"id": 12, "name": "kb-tests-floor", **quota}, {"id": 11, "name": "kb-tests", **quota}]
    forge(monkeypatch, repo, pipelines, jobs=jobs)
    capsys.readouterr()
    assert red_pipeline(repo, "--status") == 1
    out = capsys.readouterr().out
    assert "pipeline 61 of main is unverified" in out, out
    assert "kb-tests failed (ci_quota_exceeded), kb-trailers failed (ci_quota_exceeded)" in out, out
    assert "kb-tests-floor" not in out and "tool-stress" not in out and "kb-tests-windows" not in out, out
    assert red_pipeline(repo) == 0 and bugs(repo) == []  # unverified is not red: nothing filed
    assert "unverified" in capsys.readouterr().out
    # planted: every other way a gate job does not pass, on a pipeline whose status is no failure
    for status, gate, said in (
            ("manual", [{"name": "kb-tests", "status": "manual"}, {"name": "kb-trailers", "status": "manual"}],
             "kb-tests manual, kb-trailers manual"),
            ("success", [{"name": "kb-tests", "status": "skipped"}, {"name": "kb-trailers", "status": "success"}],
             "kb-tests skipped"),
            ("canceled", [{"name": "kb-tests", "status": "canceled"}, {"name": "kb-trailers", "status": "success"}],
             "kb-tests canceled"),
            ("success", [{"name": "kb-tests", "status": "success"}], "kb-trailers not in the pipeline"),
            ("success", [{"name": "kb-tests", "status": "running"}, {"name": "kb-trailers", "status": "success"}],
             "kb-tests running")):
        pipelines[0]["status"] = status
        jobs[:] = [{"id": i, **j} for i, j in enumerate(gate)]
        assert red_pipeline(repo, "--status") == 1, (status, gate)
        out = capsys.readouterr().out
        assert "is unverified" in out and said in out, out
    assert red_pipeline(repo) == 0 and bugs(repo) == []
    # the gate ran and passed: the other jobs, manual or never started, leave main green
    pipelines[0]["status"] = "success"
    jobs[:] = [{"id": 15, "name": "kb-tests-windows", "status": "manual"}, {"id": 13, "name": "tool-stress", **quota},
               {"id": 14, "name": "kb-trailers", "status": "success"}, {"id": 11, "name": "kb-tests", "status": "success"}]
    capsys.readouterr()
    assert red_pipeline(repo, "--status") == 0
    assert "pipeline 61 of main is green" in capsys.readouterr().out
    # planted: a job list glab cannot read is no proof either
    monkeypatch.undo()
    sh(repo, "git", "remote", "remove", "origin")
    forge(monkeypatch, repo, pipelines, jobs=None)
    assert red_pipeline(repo, "--status") == 1
    assert "the pipeline's jobs could not be read" in capsys.readouterr().out


def test_red_pipeline_failed_script_under_allow_failure_is_red(sprint, monkeypatch):
    """A job whose script ran and failed under allow_failure leaves the pipeline's status success: its job list makes
    it red, S1 when it is kb-tests, and the fingerprint names that job, not the one that never started."""
    repo = sprint["repo"]
    forge(monkeypatch, repo, [{"id": 62, "sha": head(repo), "status": "success"}],
          jobs=[{"id": 14, "name": "kb-trailers", "status": "success"},
                {"id": 12, "name": "kb-tests-floor", "status": "failed", "failure_reason": "ci_quota_exceeded"},
                {"id": 11, "name": "kb-tests", "status": "failed", "failure_reason": "script_failure",
                 "allow_failure": True}],
          logs={11: "FAILED _tools/test_x.py::test_a - assert 1 == 2\n"})
    assert red_pipeline(repo, "--status") == 1
    assert red_pipeline(repo) == 0
    (bug,) = [x for x in bugs(repo) if "pipeline 62" in x["title"]]
    assert bug["severity"] == "S1" and bug["title"].endswith(": kb-tests"), bug["title"]
    assert f"fingerprint {backlog.failure_fingerprint('kb-tests', '_tools/test_x.py::test_a')}" in bug["links"]


def test_red_pipeline_status_is_the_repro_of_a_red_main(repo, monkeypatch):
    forge(monkeypatch, repo, [{"id": 5, "sha": head(repo), "status": "failed"}])
    assert red_pipeline(repo, "--status") == 1


def test_red_pipeline_automatic_revert_covers_it(repo, monkeypatch):
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", "query log", "-m", "KB-Auto: apply")
    auto = head(repo)
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", "revert: query log commit",
       "-m", f"This reverts commit {auto}.", "-m", "KB-Auto: revert")
    forge(monkeypatch, repo, [{"id": 8, "sha": auto, "status": "failed"}])
    assert red_pipeline(repo) == 0
    assert bugs(repo) == []


def test_red_pipeline_revert_of_another_commit_does_not_cover_it(repo, monkeypatch):
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", "query log", "-m", "KB-Auto: apply")
    auto = head(repo)
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", "a human commit")
    human = head(repo)
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", "revert: query log commit",
       "-m", f"This reverts commit {auto}.", "-m", "KB-Auto: revert")
    forge(monkeypatch, repo, [{"id": 9, "sha": human, "status": "failed"}])
    assert red_pipeline(repo) == 0
    assert "pipeline 9" in bugs(repo)[0]["title"]


def test_red_pipeline_notes_when_not_signed_in(repo, monkeypatch, capsys):
    forge(monkeypatch, repo, [{"id": 5, "sha": head(repo), "status": "failed"}], signed_in=False)
    assert red_pipeline(repo) == 0
    assert "not signed in" in capsys.readouterr().out and bugs(repo) == []
    assert red_pipeline(repo, "--status") == 1


# ---- failure fingerprint: planted logs of red pipelines, the same failure twice and a different one

def test_fingerprint_names_the_first_failing_test_or_normalised_error_line():
    log = ("2026-09-01T10:00:00.1234567Z \x1b[31msection_start:1700000000:tests\x1b[0m\n"
           "_tools/test_a.py::test_one PASSED\n"
           "_tools/test_b.py::test_two FAILED\n"
           "FAILED _tools/test_c.py::test_three - assert 1 == 2\n")
    assert backlog.first_failure(log) == "_tools/test_b.py::test_two"
    a = backlog.first_failure("2026-09-01T10:00:00Z check: error in kb/x.md:12 (sha 0123abcd9)\nERROR: Job failed\n")
    b_ = backlog.first_failure("2026-09-02T11:30:01Z check: error in kb/x.md:57 (sha fedcba987)\nERROR: Job failed\n")
    assert a == b_ == "check: error in kb/x.md:<n> (sha <hex>)"
    assert backlog.first_failure("all good\n") == "" and backlog.first_failure(None) == ""
    fp = backlog.failure_fingerprint("kb-tests", a)
    assert len(fp) == 12 and int(fp, 16) >= 0
    assert fp == backlog.failure_fingerprint("kb-tests", b_)
    assert fp != backlog.failure_fingerprint("kb-tests-windows", a)  # another job
    assert fp != backlog.failure_fingerprint("kb-tests", "_tools/test_b.py::test_two")  # another failure


def test_fingerprint_same_failure_one_bug_different_failure_a_second(repo, monkeypatch, capsys):
    sha = head(repo)
    pipelines = [{"id": 901, "sha": sha, "status": "failed"}]
    jobs = [{"id": 11, "name": "lint", "status": "failed"}, {"id": 10, "name": "check", "status": "failed"}]
    logs = {10: "2026-09-01T10:00:00Z FAILED _tools/test_x.py::test_a - assert 3 == 4\n", 11: "lint error\n"}
    forge(monkeypatch, repo, pipelines, jobs=jobs, logs=logs)
    assert red_pipeline(repo) == 0
    (first,) = bugs(repo)
    fp = backlog.failure_fingerprint("check", "_tools/test_x.py::test_a")  # the first failed job by name
    assert first["links"] == ["pipeline 901", f"fingerprint {fp}"]
    assert "_tools/test_x.py::test_a" in first["notes"]
    # a later pipeline failing the same way (other job ids, times and numbers): no second bug, its pipeline is added
    pipelines[:] = [{"id": 902, "sha": sha, "status": "failed"}]
    jobs[:] = [{"id": 20, "name": "check", "status": "failed"}]
    logs.clear()
    logs[20] = "2026-09-03T08:15:42Z FAILED _tools/test_x.py::test_a - assert 7 == 9\n"
    capsys.readouterr()
    assert red_pipeline(repo) == 0
    assert "fails the same way" in capsys.readouterr().out
    (same,) = bugs(repo)
    assert same["id"] == first["id"] and same["links"] == ["pipeline 901", f"fingerprint {fp}", "pipeline 902"]
    assert backlog.validate(backlog.Backlog(repo)) == []
    assert red_pipeline(repo) == 0 and len(bugs(repo)) == 1  # 902 again: named in the links, nothing filed
    # a different failure: a second bug with its own fingerprint
    pipelines[:] = [{"id": 903, "sha": sha, "status": "failed"}]
    logs[20] = "FAILED _tools/test_y.py::test_b - KeyError\n"
    assert red_pipeline(repo) == 0
    second = [x for x in bugs(repo) if x["id"] != first["id"]]
    assert len(second) == 1
    assert second[0]["links"] == ["pipeline 903", f"fingerprint {backlog.failure_fingerprint('check', '_tools/test_y.py::test_b')}"]


def test_fingerprint_of_a_closed_bug_files_a_new_one(repo, monkeypatch):
    sha = head(repo)
    pipelines = [{"id": 31, "sha": sha, "status": "failed"}]
    forge(monkeypatch, repo, pipelines, jobs=[{"id": 5, "name": "check", "status": "failed"}],
          logs={5: "Traceback (most recent call last):\n"})
    assert red_pipeline(repo) == 0
    (old,) = bugs(repo)
    edit(repo, old["id"], status="dropped")  # planted: only an open bug takes the pipeline
    pipelines[:] = [{"id": 32, "sha": sha, "status": "failed"}]
    assert red_pipeline(repo) == 0
    new = [x for x in bugs(repo) if x["id"] != old["id"]]
    assert len(new) == 1 and "pipeline 32" in new[0]["links"] and new[0]["links"][1] == old["links"][1]
