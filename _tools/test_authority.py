"""What only the operator may answer cannot be answered, confirmed or lowered by an agent: the gate classes of
bl_authority, the refusals of backlog.py's `answer`, `gate add`, `set --delegate` and `check`, and of kbdecide.py.

The backlog and the decision root are throwaway directories under tmp_path; every refusal asserts the files are
byte-identical afterwards."""
import ast, json, os, shlex, shutil, subprocess, sys
from pathlib import Path


import bl_authority as ba
from conftest import TOOLS

BACKLOG = os.path.join(TOOLS, "backlog.py")
ITEMS = Path("_backlog")  # the default item_dir: the throwaway roots have no backlog.json
REPRO = shlex.join(["python3", "-c", "import sys; sys.exit(1)"])  # fails: the bug stays open


def bl(root, *args):
    p = subprocess.run([sys.executable, BACKLOG, "--root", str(root), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert "Traceback" not in p.stderr, p.stderr
    return p.returncode, p.stdout + p.stderr


def new_item(root, kind="bug", touch="src/a.py"):
    extra = ["--severity", "S3", "--repro", REPRO] if kind == "bug" else []
    code, out = bl(root, "new", kind, "--title", "Subject", "--goal", "goal", "--touch", touch, *extra)
    assert code == 0, out
    return out.split()[2]


def add_gate(root, iid, question, *extra):
    return bl(root, "gate", "add", iid, "--id", "g", "--question", question, "--option", "a", "--option", "b",
              "--recommendation", "a", *extra)


def path(root, iid):
    return Path(root) / ITEMS / f"{iid}.json"


def gate(root, iid):
    return json.loads(path(root, iid).read_text(encoding="utf-8"))["gates"][0]


def edit_gate(root, iid, **kw):
    f = path(root, iid)
    it = json.loads(f.read_text(encoding="utf-8"))
    it["gates"][0].update(kw)
    f.write_text(json.dumps(it, indent=2) + "\n", encoding="utf-8", newline="\n")


def test_operator_class_is_derived_from_touches_and_question_and_a_lower_stored_class_changes_nothing():
    plain = {"id": "g", "question": "Which name?", "options": ["a", "b"]}
    for touches, cls in ((["_tools/kbgit.py"], "push"), ([".claude/skills/*.md"], "agents-rule"),
                         ([".claude"], "agents-rule"), (["_tools/"], "push"),(["src/credentials.json"], "secrets"),
                         (["skills/sprint/SKILL.md"], "agents-rule"), (["agents/worker.md"], "agents-rule"),
                         (["src/skills/a.py", "kb/public/agents/a.md"], "design"), (["src/a.py"], "design")):
        assert ba.derived_class({"touches": touches}, plain) == cls, touches
    pushing = {**plain, "question": "May we publish the tree?"}
    assert ba.derived_class({"touches": ["src/a.py"]}, pushing) == "push"
    item = {"touches": ["_tools/kbgit.py"]}
    low = {**plain, "class": "design"}
    assert ba.gate_class(item, low) == "push" and ba.lowered(item, low) == "design"
    assert ba.lowered(item, {**plain, "class": "push"}) is None
    assert {"secrets", "push", "agents-rule"} == set(ba.OPERATOR_CLASSES)
    # the bare word `rule` classes agents-rule only beside a rule-guarding touch or path; `release` classes push anywhere
    for touches, question, cls in ((["kb/public/x.md"], "Which distill rows count by rule?", "design"),
                                   (["kb/public/x.md"], "Do the agents follow which rule?", "design"),
                                   (["kb/public/x.md"], "Which rule does AGENTS.md carry?", "agents-rule"),
                                   (["kb/public/x.md"], "Which rule is in _tools/bl_items.py?", "agents-rule"),
                                   ([".claude/skills/kb-sprint/SKILL.md"], "Which rule?", "agents-rule"),
                                   (["kb/public/x.md"], "How is the Sonnet 5.5 release question dispositioned?", "push")):
        got = ba.class_reasons({"touches": touches}, {**plain, "question": question})
        assert got[0] == cls, (question, got)
    named = ba.class_reasons({"touches": []}, {**plain, "question": "Which rule in AGENTS.md?"})[1]
    assert any("'rule'" in r for r in named), named


def test_gate_add_makes_an_operator_class_gate_blocking_whatever_kind_says(tmp_path):
    iid = new_item(tmp_path, touch="src/a.py")
    code, out = add_gate(tmp_path, iid, "Which password do we rotate?", "--kind", "provisional")
    assert code == 0, out
    g = gate(tmp_path, iid)
    assert (g["kind"], g["class"]) == ("blocking", "secrets")


def test_an_agent_cannot_answer_or_provisionally_answer_an_operator_gate_the_operator_can(tmp_path):
    iid = new_item(tmp_path, touch="_tools/kbgit.py")
    assert add_gate(tmp_path, iid, "Which name?")[0] == 0
    before = path(tmp_path, iid).read_bytes()
    for args in (("--answer", "a", "--by", "agent"), ("--provisional",)):
        code, out = bl(tmp_path, "answer", iid, "g", *args)
        assert code in (1, 2) and "push" in out, (args, out)
        assert path(tmp_path, iid).read_bytes() == before, args
    code, out = bl(tmp_path, "answer", iid, "g", "--answer", "c", "--by", "operator")  # none of the options a, b
    assert code == 2 and "'a'" in out and "'b'" in out and "--free" in out, out
    assert path(tmp_path, iid).read_bytes() == before
    code, out = bl(tmp_path, "answer", iid, "g", "--answer", "a", "--by", "operator")
    assert code == 0, out
    assert (gate(tmp_path, iid)["answer"], gate(tmp_path, iid)["by"]) == ("a", "operator")
    code, out = bl(tmp_path, "answer", iid, "g", "--answer", "c", "--free", "--by", "operator")
    assert code == 0, out
    assert gate(tmp_path, iid)["answer"] == "c"
    # `gate remove` of the same class: an agent cannot clear it, the operator can, and an answered gate stays
    code, out = bl(tmp_path, "gate", "add", iid, "--id", "g2", "--question", "Which other name?", "--option", "a",
                   "--option", "b", "--recommendation", "a")
    assert code == 0, out
    before = path(tmp_path, iid).read_bytes()
    code, out = bl(tmp_path, "gate", "remove", iid, "g2")
    assert code == 2 and "push" in out and "--by operator" in out, out
    assert path(tmp_path, iid).read_bytes() == before
    code, out = bl(tmp_path, "gate", "remove", iid, "g", "--by", "operator")
    assert code == 2 and "answered" in out, out
    assert path(tmp_path, iid).read_bytes() == before
    code, out = bl(tmp_path, "gate", "remove", iid, "g2", "--by", "operator")
    assert code == 0, out
    assert [g["id"] for g in json.loads(path(tmp_path, iid).read_text(encoding="utf-8"))["gates"]] == ["g"]


def test_an_agent_cannot_confirm_an_operator_gate(tmp_path):
    iid = new_item(tmp_path, touch="AGENTS.md")
    assert add_gate(tmp_path, iid, "Which name?")[0] == 0
    edit_gate(tmp_path, iid, answer="a", provisional=True)  # an agent's hand-written provisional answer
    before = path(tmp_path, iid).read_bytes()
    for by in ("agent", "delegate:mgr"):
        code, out = bl(tmp_path, "answer", iid, "g", "--confirm", "--by", by)
        assert code in (1, 2), out
        assert path(tmp_path, iid).read_bytes() == before, by


def test_check_reports_an_operator_gate_an_agent_answered_as_an_error(tmp_path):
    iid = new_item(tmp_path, touch="src/a.py")
    assert add_gate(tmp_path, iid, "Push to which remote?")[0] == 0
    assert bl(tmp_path, "check")[0] == 0
    edit_gate(tmp_path, iid, answer="a", by="agent")
    code, out = bl(tmp_path, "check")
    assert code == 1 and iid in out and "operator" in out, out


def test_a_gate_class_an_agent_wrote_lower_is_reported_by_check_and_still_refused(tmp_path):
    iid = new_item(tmp_path, touch="src/a.py")
    assert add_gate(tmp_path, iid, "Which password do we rotate?")[0] == 0
    edit_gate(tmp_path, iid, **{"class": "design"})
    code, out = bl(tmp_path, "check")
    assert code == 1 and "design is lower than secrets" in out, out
    before = path(tmp_path, iid).read_bytes()
    code, out = bl(tmp_path, "answer", iid, "g", "--answer", "a", "--by", "agent")
    assert code in (1, 2) and path(tmp_path, iid).read_bytes() == before, out


def test_a_delegate_grant_needs_the_operator(tmp_path):
    iid = new_item(tmp_path, kind="sprint", touch="src/a.py")
    before = path(tmp_path, iid).read_bytes()
    code, out = bl(tmp_path, "set", iid, "--delegate", "mgr")
    assert code == 2 and "without --by operator" in out, out
    assert path(tmp_path, iid).read_bytes() == before
    code, out = bl(tmp_path, "set", iid, "--delegate", "mgr", "--by", "operator")
    assert code == 0 and json.loads(path(tmp_path, iid).read_text(encoding="utf-8"))["delegates"] == [
        {"name": "mgr", "by": "operator"}], out


def import_closure(*roots):
    seen, todo = set(), list(roots)
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        for node in ast.walk(ast.parse(Path(TOOLS, name).read_text(encoding="utf-8"))):
            mods = ([a.name for a in node.names] if isinstance(node, ast.Import)
                    else [node.module or ""] if isinstance(node, ast.ImportFrom) and not node.level else [])
            todo += [f for f in (f"{m.split('.')[0]}.py" for m in mods) if f not in seen and Path(TOOLS, f).is_file()]
    return sorted(seen)


def test_kbdecide_confirm_record_supersede_restore_are_refused_without_the_operator(tmp_path):
    for name in import_closure("kbdecide.py"):
        (tmp_path / "_tools").mkdir(exist_ok=True)
        shutil.copy(os.path.join(TOOLS, name), tmp_path / "_tools" / name)
    selfdir = tmp_path / "kb" / "_self"
    selfdir.mkdir(parents=True)
    import kbcommon
    (selfdir / kbcommon.DECISIONS).write_text(",".join(kbcommon.DECISION_COLS) + "\n", encoding="utf-8", newline="\n")
    (selfdir / kbcommon.DECISION_MAKERS).write_text(",".join(kbcommon.MAKER_COLS) + "\noperator,operator,,\n",
                                                    encoding="utf-8", newline="\n")
    snap = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file() and p.suffix == ".csv"}
    cmds = (("confirm", "D-aaaaaaaa"), ("restore", "D-aaaaaaaa"), ("supersede", "D-aaaaaaaa", "D-bbbbbbbb"),
            ("record", "--source", "s", "--context", "item:BG-aaaaaaaa", "--", "left"))
    for cmd, by in [(c, ()) for c in cmds] + [(cmds[0], ("--by", "agent"))]:
        p = subprocess.run([sys.executable, str(tmp_path / "_tools" / "kbdecide.py"), cmd[0], "--root", "_self",
                            *by, *cmd[1:]], cwd=tmp_path, capture_output=True, text=True, encoding="utf-8",
                           env={k: v for k, v in os.environ.items() if k != "KB_ROOTS"})
        assert p.returncode == 2 and "operator" in p.stdout + p.stderr, (cmd, by, p.stdout + p.stderr)
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file() and p.suffix == ".csv"} == snap
