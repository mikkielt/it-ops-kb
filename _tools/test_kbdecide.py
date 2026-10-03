#!/usr/bin/env python3
"""kbdecide.py: propose, confirm, supersede, invalidate, restore, relink, sweep, makers and list, over a small repository of its own.

The repository is a copy of the five modules the tool imports with three stores: the public root (not internal: it
keeps no names), an internal root `team`, and kb/_self with its central register of decision makers. Every command
runs as a process; every success is followed by check.py over the whole repository, and every refusal plants the
failure it names and finds the file as it was.
"""
import base64, hashlib, json, os, re, shutil, subprocess, sys
from pathlib import Path

import pytest

import kbcommon, kbfacts, kbid
from conftest import git_env, requires_git

TOOLS = Path(__file__).resolve().parent
URL = "https://docs.example.com/runbooks/patching"
ALPHA = "abcdefghijklmnopqrstuvwxyz234567"
DAY = "2026-10-01"
HEADERS = {
    "_sources.csv": "id,url,title,publisher,licence,reuse,retrieved_utc,version_or_date,artifact_sha256,used_in,superseded_by\n",
    "_artifacts.csv": "path,source_id,sha256\n",
}


def article(sid):
    return (f"---\ntopic: ops/patching\npriority: P1\nretrieved_utc: 2026-09-27\nsources: [{sid}]\nstatus: complete\n---\n\n"
            f"# Patching\n\n## Summary\n\nHow the team patches.\n\n## Facts\n\n- Servers patch on the second Tuesday. [DOC {sid}]\n\n"
            f"## Reference\n\n- runbook\n\n## Examples\n\n- none\n")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def make_root(base, name, prefix, visibility):
    sid = kbid.source_id(URL, prefix)
    write(base / "_root.md", f"---\nroot: {name}\nid_prefix: {prefix}\nvisibility: {visibility}\ndescription: test root\n---\n")
    write(base / "_sources.csv", HEADERS["_sources.csv"]
          + f"{sid},{URL},Patching runbook,Example team,internal,quote,2026-09-27,,,ops/patching.md,\n")
    write(base / "_artifacts.csv", HEADERS["_artifacts.csv"])
    for ledger, text in (("_answers.md", "# Answers\n"), ("_gaps.md", "# Gaps\n"), ("_conflicts.md", "# Conflicts\n")):
        write(base / ledger, text)
    write(base / "ops" / "patching.md", article(sid))
    write(base / kbcommon.DECISIONS, ",".join(kbcommon.DECISION_COLS) + "\n")
    return sid


def bl_imports(tools, start="backlog.py"):
    """The bl_ modules START imports, at any depth, as file names: read from the import lines, so a new bl_ module
    backlog.py comes to import needs no edit here."""
    import ast
    seen, todo = set(), [start]
    while todo:
        tree = ast.parse((Path(tools) / todo.pop()).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            for n in names:
                f = f"{n.split('.')[0]}.py"
                if f.startswith("bl_") and f not in seen and (Path(tools) / f).exists():
                    seen.add(f)
                    todo.append(f)
    return sorted(seen)


def copied_tools(tools=TOOLS):
    """The _tools files the temp repository needs: kbdecide.py and what it imports, and backlog.py with every bl_
    module it imports."""
    return ["kbdecide.py", "check.py", "kbcommon.py", "kbid.py", "kbfacts.py", "backlog.py", *bl_imports(tools)]


def test_make_root_copies_all_bl_modules(tmp_path):
    (tmp_path / "backlog.py").write_text("import bl_base\nfrom bl_new_module import x\n", encoding="utf-8")
    (tmp_path / "bl_base.py").write_text("", encoding="utf-8")
    (tmp_path / "bl_new_module.py").write_text("import bl_deeper\n", encoding="utf-8")  # planted: no list names it
    (tmp_path / "bl_deeper.py").write_text("", encoding="utf-8")
    (tmp_path / "bl_unused.py").write_text("", encoding="utf-8")  # nothing imports it: not needed
    assert bl_imports(tmp_path) == ["bl_base.py", "bl_deeper.py", "bl_new_module.py"]
    assert "bl_base.py" in copied_tools() and "bl_land.py" in copied_tools()  # the real backlog.py's, read the same way


@pytest.fixture(scope="module")
def template(tmp_path_factory):
    """The repository every test starts from."""
    repo = tmp_path_factory.mktemp("kbdecide") / "repo"
    for name in copied_tools():
        (repo / "_tools").mkdir(parents=True, exist_ok=True)
        shutil.copy(TOOLS / name, repo / "_tools" / name)
    make_root(repo / "kb" / "public", "public", "S", "public")
    make_root(repo / "kb" / "team", "team", "T", "internal")
    write(repo / "kb" / "public" / kbcommon.DECISION_MAKERS, ",".join(kbcommon.MAKER_COLS) + "\n"
          + f"{kbcommon.POLICY_ROW},role-only,,\npublic-lead,public lead,,\n")
    write(repo / "kb" / "team" / kbcommon.DECISION_MAKERS, ",".join(kbcommon.MAKER_COLS) + "\n"
          + f"{kbcommon.POLICY_ROW},role-and-name,,\nlead,team lead,Jan Kowalski,{kbid.source_id(URL, 'T')}\n")
    write(repo / "kb" / "_self" / kbcommon.DECISIONS, ",".join(kbcommon.DECISION_COLS) + "\n")
    write(repo / "kb" / "_self" / kbcommon.DECISION_MAKERS, ",".join(kbcommon.MAKER_COLS)
          + "\nowner,operations owner,,\noperator,operator,,\nautopilot,autopilot,,\n")
    return repo


class Repo:
    def __init__(self, path):
        self.path = path

    def run(self, tool, *args):
        env = {k: v for k, v in os.environ.items() if k != "KB_ROOTS"}
        p = subprocess.run([sys.executable, str(self.path / "_tools" / tool), *args], cwd=self.path, env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        assert "Traceback" not in p.stderr + p.stdout, p.stderr + p.stdout
        return p.returncode, p.stdout + p.stderr

    def decide(self, *args):
        return self.run("kbdecide.py", *args)

    def file(self, store="public"):
        return self.path / "kb" / ("_self" if store == "_self" else store) / kbcommon.DECISIONS

    def rows(self, store="public"):
        return kbcommon.load_csv(str(self.file(store)))[1]

    def row(self, did, store="public"):
        return next(r for r in self.rows(store) if r["id"] == did)

    def check(self):
        code, out = self.run("check.py")
        assert code == 0 and "errors=0" in out, out[-1500:]


@pytest.fixture
def repo(template, tmp_path):
    shutil.copytree(template, tmp_path / "repo")
    return Repo(tmp_path / "repo")


def sid(prefix="S"):
    return kbid.source_id(URL, prefix)


CONTEXT = "article:ops/patching; domain:ops; item:TK-abcd2345"


def propose(repo, store="public", text="Servers patch on the second Tuesday."):
    code, out = repo.decide("propose", "--root", store, text, "--source", sid("T" if store == "team" else "S"),
                            "--context", CONTEXT.replace("article:ops", f"article:{'public/' if store == '_self' else ''}ops")
                            .replace("domain:ops", f"domain:{'public/' if store == '_self' else ''}ops"),
                            "--date", DAY)
    assert code == 0, out
    return out.split("\t")[0]


def refused(repo, store, *args, says):
    """A refused command: exit 2, the message names the rule, and no decision file changed."""
    before = {s: (repo.file(s).read_bytes() if repo.file(s).exists() else None) for s in ("public", "team", "_self")}
    code, out = repo.decide(*args)
    assert code == 2 and says in out, (args, code, out)
    after = {s: (repo.file(s).read_bytes() if repo.file(s).exists() else None) for s in ("public", "team", "_self")}
    assert before == after, (args, "a refused command changed a file")


def test_kbdecide_propose_adds_a_proposed_row_that_passes_check(repo):
    did = propose(repo)
    row = repo.row(did)
    assert kbcommon.DECISION_ID.fullmatch(did)
    assert (row["status"], row["by"], row["by_ref"], row["date"]) == ("proposed", "", "", DAY)
    assert row["source"] == sid() and row["context"] == CONTEXT and row["text"] == "Servers patch on the second Tuesday."
    repo.check()


def test_kbdecide_propose_takes_review_by_and_links(repo):
    code, out = repo.decide("propose", "--root", "public", "Reboot after patching.", "--source", sid(), "--context",
                            "domain:ops", "--review-by", "2027-01-01", "--links", "https://corp.example.com/notes",
                            "--date", DAY)
    assert code == 0, out
    row = repo.row(out.split("\t")[0])
    assert (row["review_by"], row["links"]) == ("2027-01-01", "https://corp.example.com/notes")
    repo.check()


def test_kbdecide_propose_in_a_second_root_and_in_kb_self(repo):
    propose(repo, "team")
    propose(repo, "_self")
    assert len(repo.rows("team")) == 1 and len(repo.rows("_self")) == 1 and not repo.rows("public")
    repo.check()


def test_kbdecide_propose_ids_follow_text_and_context(repo):
    a = propose(repo, "public", "One decision.")
    b = propose(repo, "public", "Another decision.")
    assert a != b
    assert len(repo.rows()) == 2
    sys.path.insert(0, str(TOOLS))
    import kbdecide
    assert kbdecide.decision_id("x", "domain:ops") == kbdecide.decision_id("x", "domain:ops")
    assert kbdecide.decision_id("x", "domain:ops") != kbdecide.decision_id("x", "domain:print")
    digest = hashlib.sha256(b"x\ndomain:ops").digest()
    assert kbdecide.decision_id("x", "domain:ops") == "D-" + base64.b32encode(digest).decode().lower()[:8]


@pytest.mark.parametrize("args,says", [
    (("propose", "--root", "public", "Text.", "--context", "domain:ops"), "--source"),  # no source at all
    (("propose", "--root", "public", "Text.", "--source", "", "--context", "domain:ops"), "needs --source"),
    (("propose", "--root", "public", "Text.", "--source", "S-zzzzzzzz", "--context", "domain:ops"), "cites unknown source S-zzzzzzzz"),
    (("propose", "--root", "public", "Text.", "--source", "a talk", "--context", "table:ops"), "context part 'table:ops'"),
    (("propose", "--root", "public", "Text.", "--source", "a talk", "--context", "article:ops/nope"), "names no article ops/nope"),
    (("propose", "--root", "public", "Text.", "--source", "a talk", "--context", "domain:nope"), "names no domain nope"),
    (("propose", "--root", "public", "Text.", "--source", "a talk", "--context", "item:tk-1"), "not a valid item reference"),
    (("propose", "--root", "public", "Text.", "--source", "a talk", "--context", " ; "), "needs --context"),
    (("propose", "--root", "public", "   ", "--source", "a talk", "--context", "domain:ops"), "needs text"),
    (("propose", "--root", "public", "Text.", "--source", "a talk", "--context", "domain:ops", "--date", "2026-13-40"), "is not YYYY-MM-DD"),
    (("propose", "--root", "public", "Text.", "--source", "a talk", "--context", "domain:ops", "--review-by", "soon"), "review_by 'soon'"),
    (("propose", "--root", "nope", "Text.", "--source", "a talk", "--context", "domain:ops"), "no root 'nope'"),
    (("propose", "--root", "public", "Text.", "--source", "a talk", "--context", "domain:ops", "--date", "2026-1-1"), "is not YYYY-MM-DD"),
])
def test_kbdecide_propose_refusals(repo, args, says):
    if says == "--source":  # argparse's own refusal: exit 2 and usage, never a row
        code, out = repo.decide(*args)
        assert code == 2 and "--source" in out and not repo.rows()
        return
    refused(repo, "public", *args, says=says)


def test_kbdecide_propose_needs_a_root(repo):
    code, out = repo.decide("propose", "Text.", "--source", "a talk", "--context", "domain:ops")
    assert code == 2 and "--root" in out and not repo.rows()


def test_kbdecide_propose_refuses_the_same_decision_twice(repo):
    propose(repo)
    refused(repo, "public", "propose", "--root", "public", "Servers patch on the second Tuesday.", "--source", sid(),
            "--context", CONTEXT, says="is already in public/_decisions.csv")


def test_kbdecide_propose_in_kb_self_names_the_root_in_an_article_context(repo):
    refused(repo, "_self", "propose", "--root", "_self", "Text.", "--source", "a talk", "--context", "article:ops/patching",
            says="names no root; kb/_self decisions write article:<root>/<path>")


def test_kbdecide_a_failed_write_leaves_no_file_behind(repo):
    repo.file("public").unlink()
    code, out = repo.decide("propose", "--root", "public", "Text.", "--source", "S-zzzzzzzz", "--context", "domain:ops")
    assert code == 2 and "would fail check.py" in out
    assert not repo.file("public").exists()


def test_kbdecide_propose_asks_the_policy_first(repo):
    """policy_refusal is the one place a root's storage rule plugs in: a reason it returns refuses the proposal."""
    code = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, '_tools'); import kbdecide; "
         "kbdecide.policy_refusal = lambda store, rows: 'set how makers are saved first'; "
         "sys.exit(kbdecide.main(['propose', '--root', 'public', 'Text.', '--source', 'a talk', '--context', 'domain:ops']))"],
        cwd=repo.path, capture_output=True, text=True, encoding="utf-8").returncode
    assert code == 2 and not repo.rows()


def test_kbdecide_confirm_needs_by_operator(repo):
    did = propose(repo, "team")
    refused(repo, "team", "confirm", did, "--root", "team", says="only the operator confirms")
    refused(repo, "team", "confirm", did, "--root", "team", "--by", "agent", says="only the operator confirms")
    refused(repo, "team", "confirm", did, "--root", "team", "--by", "Operator", says="only the operator confirms")
    assert repo.row(did, "team")["status"] == "proposed"


def test_kbdecide_confirm_in_an_internal_root_records_the_operator_or_a_name(repo):
    one, two = propose(repo, "team", "One."), propose(repo, "team", "Two.")
    code, out = repo.decide("confirm", one, "--root", "team", "--by", "operator", "--date", "2026-10-02")
    assert code == 0 and out.startswith(f"{one}\tactive"), out
    row = repo.row(one, "team")
    assert (row["status"], row["by"], row["by_ref"], row["date"]) == ("active", "operator", "", "2026-10-02")
    code, out = repo.decide("confirm", two, "--root", "team", "--by", "operator", "--maker", "lead", "--name", "Jan Kowalski")
    assert code == 0, out
    row = repo.row(two, "team")
    assert (row["by"], row["by_ref"]) == ("Jan Kowalski", "lead")
    repo.check()


def test_kbdecide_confirm_names_a_maker_by_reference_where_no_names_are_kept(repo):
    did = propose(repo, "public")
    refused(repo, "public", "confirm", did, "--root", "public", "--by", "operator", says="keeps decision makers by reference")
    refused(repo, "public", "confirm", did, "--root", "public", "--by", "operator", "--maker", "nobody", says="no decision maker 'nobody'")
    refused(repo, "public", "confirm", did, "--root", "public", "--by", "operator", "--maker", "owner", "--name", "Jan Kowalski",
            says="keeps no names")
    code, out = repo.decide("confirm", did, "--root", "public", "--by", "operator", "--maker", "public-lead")
    assert code == 0, out
    row = repo.row(did)
    assert (row["status"], row["by"], row["by_ref"]) == ("active", "public lead", "public-lead")
    repo.check()


def test_kbdecide_confirm_takes_a_maker_of_the_central_register(repo):
    did = propose(repo, "public")
    code, out = repo.decide("confirm", did, "--root", "public", "--by", "operator", "--maker", "owner")
    assert code == 0, out
    assert repo.row(did)["by"] == "operations owner"
    kb_self = propose(repo, "_self")
    assert repo.decide("confirm", kb_self, "--root", "_self", "--by", "operator", "--maker", "owner")[0] == 0
    assert repo.row(kb_self, "_self")["by"] == "operations owner"
    repo.check()


def test_kbdecide_confirm_refuses_what_is_not_proposed_or_not_there(repo):
    did = propose(repo, "team")
    assert repo.decide("confirm", did, "--root", "team", "--by", "operator")[0] == 0
    refused(repo, "team", "confirm", did, "--root", "team", "--by", "operator", says="is active: only proposed decisions")
    refused(repo, "team", "confirm", "D-aaaaaaaa", "--root", "team", "--by", "operator", says="no decision D-aaaaaaaa")
    refused(repo, "team", "confirm", "x1", "--root", "team", "--by", "operator", says="is not a decision id")


def test_kbdecide_record_writes_an_active_decision_in_one_step(repo):
    code, out = repo.decide("record", "--root", "_self", "Patch on the second Tuesday.", "--source", "backlog gate answer",
                            "--context", "item:TK-abcd2345", "--by", "operator", "--maker", "owner", "--date", DAY)
    assert code == 0 and "\tactive\t_self" in out, out
    row = repo.row(out.split("\t")[0], "_self")
    assert (row["status"], row["by"], row["by_ref"], row["date"]) == ("active", "operations owner", "owner", DAY)
    assert row["source"] == "backlog gate answer" and row["context"] == "item:TK-abcd2345"
    repo.check()


def test_kbdecide_record_refusals_leave_no_row(repo):
    base = ("record", "--root", "_self", "Text.", "--source", "a talk", "--context", "item:TK-abcd2345", "--maker", "owner")
    refused(repo, "_self", *base, says="only the operator records a decision")
    refused(repo, "_self", *base, "--by", "agent", says="only the operator records a decision")
    refused(repo, "_self", *base[:-2], "--by", "operator", says="keeps decision makers by reference")
    refused(repo, "_self", *base[:-1], "nobody", "--by", "operator", says="no decision maker 'nobody'")
    refused(repo, "_self", *base[:3], "  ", *base[4:], "--by", "operator", says="needs text")
    assert not repo.rows("_self")
    assert repo.decide(*base, "--by", "operator")[0] == 0
    refused(repo, "_self", *base, "--by", "operator", says="is already in kb/_self/_decisions.csv")


def active(repo, store="team", text="Servers patch on the second Tuesday."):
    did = propose(repo, store, text)
    maker = ["--maker", "public-lead"] if store == "public" else []
    assert repo.decide("confirm", did, "--root", store, "--by", "operator", *maker)[0] == 0
    return did


def test_kbdecide_supersede_marks_the_old_one_and_lists_it_in_the_new(repo):
    old, new = active(repo, "team", "Old."), active(repo, "team", "New.")
    code, out = repo.decide("supersede", old, new, "--root", "team", "--by", "operator")
    assert code == 0 and f"superseded by {new}" in out, out
    assert repo.row(old, "team")["status"] == "superseded"
    assert repo.row(new, "team")["supersedes"] == old and repo.row(new, "team")["status"] == "active"
    assert len(repo.rows("team")) == 2
    third = active(repo, "team", "Third.")
    assert repo.decide("supersede", new, third, "--root", "team", "--by", "operator")[0] == 0
    assert repo.row(third, "team")["supersedes"] == new
    repo.check()


def test_kbdecide_supersede_refusals(repo):
    one, two = active(repo, "team", "One."), active(repo, "team", "Two.")
    proposed = propose(repo, "team", "Proposed.")
    refused(repo, "team", "supersede", one, one, "--root", "team", "--by", "operator", says="cannot supersede itself")
    refused(repo, "team", "supersede", one, proposed, "--root", "team", "--by", "operator", says=f"{proposed} is proposed")
    refused(repo, "team", "supersede", proposed, one, "--root", "team", "--by", "operator", says=f"{proposed} is proposed")
    refused(repo, "team", "supersede", one, "D-aaaaaaaa", "--root", "team", "--by", "operator", says="no decision D-aaaaaaaa")
    assert repo.decide("supersede", one, two, "--root", "team", "--by", "operator")[0] == 0
    refused(repo, "team", "supersede", one, two, "--root", "team", "--by", "operator", says=f"{one} is superseded")


def test_kbdecide_invalidate_keeps_the_row_and_records_why(repo):
    did = active(repo, "team")
    code, out = repo.decide("invalidate", did, "--root", "team", "--reason", "the runbook changed", "--date", "2026-10-03")
    assert code == 0 and out.startswith(f"{did}\tinvalidated"), out
    row = repo.row(did, "team")
    assert (row["status"], row["invalidated_reason"], row["invalidated_date"]) == ("invalidated", "the runbook changed", "2026-10-03")
    assert row["text"] == "Servers patch on the second Tuesday." and row["by"] == "operator"
    assert len(repo.rows("team")) == 1
    repo.check()


def test_kbdecide_invalidate_refusals(repo):
    did = active(repo, "team")
    code, out = repo.decide("invalidate", did, "--root", "team")
    assert code == 2 and "--reason" in out and repo.row(did, "team")["status"] == "active"
    refused(repo, "team", "invalidate", did, "--root", "team", "--reason", "  ", says="--reason is empty")
    refused(repo, "team", "invalidate", "D-aaaaaaaa", "--root", "team", "--reason", "x", says="no decision D-aaaaaaaa")
    refused(repo, "team", "invalidate", did, "--root", "team", "--reason", "x", "--date", "tomorrow", says="is not YYYY-MM-DD")
    assert repo.decide("invalidate", did, "--root", "team", "--reason", "x")[0] == 0
    refused(repo, "team", "invalidate", did, "--root", "team", "--reason", "again", says="is invalidated: only proposed or active decisions")
    other, newer = active(repo, "team", "Other."), active(repo, "team", "Newer.")
    assert repo.decide("supersede", other, newer, "--root", "team", "--by", "operator")[0] == 0
    refused(repo, "team", "invalidate", other, "--root", "team", "--reason", "x", says="is superseded: only proposed or active decisions")


def test_kbdecide_restore_brings_back_what_it_was_and_keeps_the_row(repo):
    confirmed = active(repo, "team")
    assert repo.decide("invalidate", confirmed, "--root", "team", "--reason", "by mistake", "--date", "2026-10-03")[0] == 0
    code, out = repo.decide("restore", confirmed, "--root", "team", "--by", "operator")
    assert code == 0 and out.startswith(f"{confirmed}\tactive"), out
    row = repo.row(confirmed, "team")
    assert (row["status"], row["invalidated_reason"], row["invalidated_date"], row["by"]) == ("active", "", "", "operator")
    assert row["links"] == "was invalidated 2026-10-03: by mistake"
    assert len(repo.rows("team")) == 1
    repo.check()


def test_kbdecide_restore_never_confirms_a_decision_that_names_no_maker(repo):
    """A row written by hand as invalidated with no maker comes back proposed: restoring is not the operator's yes."""
    did = propose(repo, "team")
    rows = repo.rows("team")
    rows[0].update(status="invalidated", invalidated_reason="x", invalidated_date=DAY)
    kbcommon.write_csv(str(repo.file("team")), kbcommon.DECISION_COLS, rows)
    assert repo.decide("restore", did, "--root", "team", "--by", "operator")[0] == 0
    assert repo.row(did, "team")["status"] == "proposed"


def test_kbdecide_restore_refuses_what_is_not_invalidated(repo):
    did = active(repo, "team")
    refused(repo, "team", "restore", did, "--root", "team", "--by", "operator", says="is active: only invalidated decisions")
    refused(repo, "team", "restore", "D-aaaaaaaa", "--root", "team", "--by", "operator", says="no decision D-aaaaaaaa")
    refused(repo, "team", "restore", "nope", "--root", "team", "--by", "operator", says="is not a decision id")


def test_kbdecide_withdraw_invalidate_rejects_a_proposal_and_needs_no_maker(repo):
    """An agent may invalidate a proposal nobody should confirm: the row stays, names no maker, and passes check.py."""
    did = propose(repo, "team", "Nobody should confirm this.")
    code, out = repo.decide("invalidate", did, "--root", "team", "--reason", "the operator declined it", "--date", "2026-10-03")
    assert code == 0 and out.startswith(f"{did}\tinvalidated"), out
    row = repo.row(did, "team")
    assert (row["status"], row["invalidated_reason"], row["invalidated_date"]) == ("invalidated", "the operator declined it", "2026-10-03")
    assert (row["by"], row["by_ref"]) == ("", "")
    assert len(repo.rows("team")) == 1
    repo.check()
    refused(repo, "team", "invalidate", did, "--root", "team", "--reason", "again", says="is invalidated: only proposed or active")
    refused(repo, "team", "confirm", did, "--root", "team", "--by", "operator", says="is invalidated: only proposed decisions")
    did2 = propose(repo, "team", "Asked for no reason.")
    refused(repo, "team", "invalidate", did2, "--root", "team", "--reason", " ", says="--reason is empty")
    assert repo.row(did2, "team")["status"] == "proposed"


def test_kbdecide_withdraw_invalidate_is_open_to_an_agent_for_a_proposal_in_every_store(repo):
    for store in ("public", "team", "_self"):
        did = propose(repo, store, f"Rejected in {store}.")
        assert repo.decide("invalidate", did, "--root", store, "--reason", "swept")[0] == 0
        assert repo.row(did, store)["status"] == "invalidated"
    repo.check()


def test_kbdecide_withdraw_supersede_and_restore_refuse_without_by_operator(repo):
    old, new = active(repo, "team", "Old."), active(repo, "team", "New.")
    for by in ((), ("--by", "agent"), ("--by", "")):
        refused(repo, "team", "supersede", old, new, "--root", "team", *by, says="only the operator supersedes a decision")
    assert repo.row(old, "team")["status"] == "active" and repo.row(new, "team")["supersedes"] == ""
    assert repo.decide("invalidate", old, "--root", "team", "--reason", "x")[0] == 0
    rejected = propose(repo, "team", "Rejected.")
    assert repo.decide("invalidate", rejected, "--root", "team", "--reason", "x")[0] == 0
    for did in (old, rejected):
        for by in ((), ("--by", "agent")):
            refused(repo, "team", "restore", did, "--root", "team", *by, says="only the operator restores a decision")
        assert repo.row(did, "team")["status"] == "invalidated"
    # the same refusals hold in the other stores, and an unknown id is not what is refused first
    refused(repo, "team", "restore", "D-aaaaaaaa", "--root", "team", says="only the operator restores a decision")
    refused(repo, "team", "supersede", "D-aaaaaaaa", "D-bbbbbbbb", "--root", "team", says="only the operator supersedes")


def test_kbdecide_withdraw_restore_returns_a_rejected_proposal_to_proposed_not_active(repo):
    """A proposal that was rejected comes back as the proposal it was: restoring is not the operator's yes to it."""
    did = propose(repo, "team", "Rejected once.")
    assert repo.decide("invalidate", did, "--root", "team", "--reason", "too early", "--date", "2026-10-03")[0] == 0
    code, out = repo.decide("restore", did, "--root", "team", "--by", "operator")
    assert code == 0 and out.startswith(f"{did}\tproposed"), out
    row = repo.row(did, "team")
    assert (row["status"], row["by"], row["by_ref"], row["invalidated_reason"], row["invalidated_date"]) == ("proposed", "", "", "", "")
    assert row["links"] == "was invalidated 2026-10-03: too early"
    repo.check()
    assert repo.decide("confirm", did, "--root", "team", "--by", "operator")[0] == 0  # only a confirm makes it active
    assert repo.row(did, "team")["status"] == "active"


def test_kbdecide_withdraw_restore_returns_a_confirmed_decision_to_active(repo):
    did = active(repo, "team")
    assert repo.decide("invalidate", did, "--root", "team", "--reason", "x")[0] == 0
    assert repo.decide("restore", did, "--root", "team", "--by", "operator")[0] == 0
    row = repo.row(did, "team")
    assert (row["status"], row["by"]) == ("active", "operator")
    repo.check()


def test_kbdecide_list_reads_one_root_or_all_and_filters(repo):
    a = active(repo, "team", "Active one.")
    b = propose(repo, "team", "Proposed one.")
    c = propose(repo, "public", "Public one.")
    d = propose(repo, "_self", "Self one.")
    code, out = repo.decide("list", "--root", "team")
    assert code == 0 and out.splitlines()[-1] == "decisions=2", out
    lines = [ln.split("\t") for ln in out.splitlines()[:-1]]
    assert [ln[:3] for ln in lines] == [["team", a, "active"], ["team", b, "proposed"]]
    assert lines[0][4] == "operator" and lines[0][6] == "Active one."
    out = repo.decide("list")[1]
    assert [ln.split("\t")[1] for ln in out.splitlines()[:-1]] == [c, a, b, d] and out.endswith("decisions=4\n"), out
    out = repo.decide("list", "--status", "proposed")[1]
    assert {ln.split("\t")[1] for ln in out.splitlines()[:-1]} == {b, c, d}
    out = repo.decide("list", "--root", "team", "--status", "active")[1]
    assert out == "\t".join(lines[0]) + "\ndecisions=1\n"
    assert repo.decide("list", "--context", "item:TK-abcd2345")[1].endswith("decisions=4\n")
    assert repo.decide("list", "--context", "TK-abcd2345")[1].endswith("decisions=4\n")
    assert repo.decide("list", "--context", "item:TK-zzzzzzzz")[1] == "decisions=0\n"
    assert repo.decide("list", "--root", "team", "--status", "invalidated")[1] == "decisions=0\n"


def test_kbdecide_list_refusals(repo):
    code, out = repo.decide("list", "--status", "accepted")
    assert code == 2 and "invalid choice" in out
    code, out = repo.decide("list", "--root", "nope")
    assert code == 2 and "no root 'nope'" in out
    repo.file("team").write_text("id,text\nD-aaaaaaaa,x\n", encoding="utf-8", newline="\n")
    code, out = repo.decide("list", "--root", "team")
    assert code == 2 and "header is 'id,text'" in out


def test_kbdecide_refuses_a_file_that_is_not_the_format_for_every_command(repo):
    did = propose(repo, "team")
    repo.file("team").write_text("id,text\nD-aaaaaaaa,x\n", encoding="utf-8", newline="\n")
    for args in (("propose", "--root", "team", "Text.", "--source", "a talk", "--context", "domain:ops"),
                 ("confirm", did, "--root", "team", "--by", "operator"),
                 ("invalidate", did, "--root", "team", "--reason", "x"),
                 ("restore", did, "--root", "team", "--by", "operator")):
        code, out = repo.decide(*args)
        assert code == 2 and "header is 'id,text'" in out, (args, out)


def test_kbdecide_leaves_rows_it_did_not_touch_as_they_were(repo):
    first = propose(repo, "team", "First.")
    second = propose(repo, "team", "Second.")
    before = repo.row(first, "team")
    assert repo.decide("confirm", second, "--root", "team", "--by", "operator")[0] == 0
    assert repo.row(first, "team") == before
    assert [r["id"] for r in repo.rows("team")] == [first, second]


def test_kbdecide_a_change_does_not_hide_an_error_the_file_already_had(repo):
    """An error check.py already finds in another row is not the new row's: the new row is still written."""
    first = propose(repo, "team", "First.")
    rows = repo.rows("team")
    rows[0]["review_by"] = "soon"
    kbcommon.write_csv(str(repo.file("team")), kbcommon.DECISION_COLS, rows)
    second = propose(repo, "team", "Second.")
    assert [r["id"] for r in repo.rows("team")] == [first, second]
    code, out = repo.run("check.py")
    assert code == 1 and "review_by 'soon'" in out and "errors=1" in out, out[-600:]


# --- the storage policy for decision makers: `makers R --policy P --by operator` ---


def makers_file(repo, store):
    return repo.path / "kb" / ("_self" if store == "_self" else store) / kbcommon.DECISION_MAKERS


def policy_of(repo, store):
    rows = kbcommon.load_csv(str(makers_file(repo, store)))[1]
    return next((r["role"] for r in rows if r["id"] == kbcommon.POLICY_ROW), "")


def unset_policy(repo, store):
    """The root as kbroot.py leaves it: its decision-makers.csv without a policy row."""
    path = makers_file(repo, store)
    kept = [r for r in kbcommon.load_csv(str(path))[1] if r["id"] != kbcommon.POLICY_ROW]
    kbcommon.write_csv(str(path), kbcommon.MAKER_COLS, kept)


def set_policy(repo, store, policy, *extra):
    return repo.decide("makers", store, "--policy", policy, "--by", "operator", *extra)


def propose_args(store):
    return ("propose", "--root", store, "Text.", "--source", "a talk", "--context", "domain:ops")


def test_kbdecide_makers_propose_in_a_root_without_a_policy_asks_the_question(repo):
    unset_policy(repo, "team")
    unset_policy(repo, "public")
    for store, options in (("team", ("role-only", "role-and-name", "central-register")),
                           ("public", ("role-only", "central-register"))):
        before = repo.file(store).read_bytes()
        code, out = repo.decide(*propose_args(store))
        assert code == 2 and out.startswith("refused: "), out
        assert f"{store} has no storage policy for decision makers. How is a decision maker saved there?" in out, out
        assert all(o in out for o in options), out
        assert ("role-and-name" in out) == (store == "team"), out  # a root that keeps no names is not offered names
        assert f"python3 _tools/kbdecide.py makers {store} --policy <option> --by operator" in out, out
        assert repo.file(store).read_bytes() == before
    unset_policy(repo, "public")  # a second refusal, with the file gone: the question comes before any file is made
    repo.file("public").unlink()
    assert repo.decide(*propose_args("public"))[0] == 2 and not repo.file("public").exists()


def test_kbdecide_makers_a_root_with_a_policy_takes_its_first_decision(repo):
    unset_policy(repo, "team")
    assert repo.decide(*propose_args("team"))[0] == 2
    code, out = set_policy(repo, "team", "role-and-name")
    assert code == 0 and out.strip() == "policy=role-and-name\tteam", out
    assert repo.decide(*propose_args("team"))[0] == 0
    repo.check()


def test_kbdecide_makers_kb_self_needs_no_policy_and_takes_none(repo):
    propose(repo, "_self")
    refused(repo, "_self", "makers", "_self", "--policy", "role-only", "--by", "operator", says="has no storage policy to set")
    repo.check()


def test_kbdecide_makers_set_the_policy_needs_by_operator(repo):
    unset_policy(repo, "team")
    before = makers_file(repo, "team").read_bytes()
    for by in ((), ("--by", "agent"), ("--by", "Operator")):
        code, out = repo.decide("makers", "team", "--policy", "role-only", *by)
        assert code == 2 and "only the operator sets how a root saves its decision makers" in out, (by, out)
        assert makers_file(repo, "team").read_bytes() == before


def test_kbdecide_makers_sets_one_policy_row_and_keeps_the_makers(repo):
    code, out = set_policy(repo, "public", "role-only")  # the same policy again: one row, not two
    assert code == 0, out
    rows = kbcommon.load_csv(str(makers_file(repo, "public")))[1]
    assert [(r["id"], r["role"]) for r in rows] == [(kbcommon.POLICY_ROW, "role-only"), ("public-lead", "public lead")], rows
    assert policy_of(repo, "public") == "role-only"
    repo.check()


def test_kbdecide_makers_refuses_a_policy_the_makers_file_breaks(repo):
    """role-only in an internal root keeps no names, so the team's maker with a name would fail check.py: the change
    is undone and refused. With the name gone it goes through, and a confirmation then takes no --name."""
    before = makers_file(repo, "team").read_bytes()
    code, out = repo.decide("makers", "team", "--policy", "role-only", "--by", "operator")
    assert code == 2 and "would fail check.py" in out and "its decision-maker policy is role-only" in out, out
    assert makers_file(repo, "team").read_bytes() == before
    rows = [{"id": "lead", "role": "team lead", "name": "", "source": ""}]
    kbcommon.write_csv(str(makers_file(repo, "team")), kbcommon.MAKER_COLS, rows)
    assert set_policy(repo, "team", "role-only")[0] == 0
    did = propose(repo, "team")
    refused(repo, "team", "confirm", did, "--root", "team", "--by", "operator", "--name", "Jan Kowalski", says="keeps no names")
    refused(repo, "team", "confirm", did, "--root", "team", "--by", "operator", says="keeps decision makers by reference")
    assert repo.decide("confirm", did, "--root", "team", "--by", "operator", "--maker", "lead")[0] == 0
    assert (repo.row(did, "team")["by"], repo.row(did, "team")["by_ref"]) == ("team lead", "lead")
    repo.check()


def test_kbdecide_makers_refuses_role_and_name_where_no_names_are_kept(repo):
    """role-and-name is impossible where kbcommon.maker_names_allowed says no: a root that is not internal."""
    before = makers_file(repo, "public").read_bytes()
    code, out = set_policy(repo, "public", "role-and-name")
    assert code == 2 and "may not keep decision makers by role-and-name" in out and "not an internal root" in out, out
    assert makers_file(repo, "public").read_bytes() == before
    assert policy_of(repo, "public") == "role-only"


def test_kbdecide_makers_central_register_keeps_no_makers_of_its_own(repo):
    """The policy that references the central register is refused while the root holds a maker of its own; a
    confirmation then names a maker of kb/_self/decision-makers.csv only."""
    before = makers_file(repo, "public").read_bytes()
    code, out = set_policy(repo, "public", "central-register")
    assert code == 2 and "a maker of its own in a root whose policy is central-register" in out, out
    assert makers_file(repo, "public").read_bytes() == before
    kbcommon.write_csv(str(makers_file(repo, "public")), kbcommon.MAKER_COLS, [])
    assert set_policy(repo, "public", "central-register")[0] == 0
    did = propose(repo, "public")
    refused(repo, "public", "confirm", did, "--root", "public", "--by", "operator", "--maker", "public-lead",
            says="no decision maker 'public-lead' in the central register")
    assert repo.decide("confirm", did, "--root", "public", "--by", "operator", "--maker", "owner")[0] == 0
    assert (repo.row(did)["by"], repo.row(did)["by_ref"]) == ("operations owner", "owner")
    repo.check()


def test_kbdecide_makers_creates_the_file_when_the_root_has_none(repo):
    makers_file(repo, "team").unlink()
    assert set_policy(repo, "team", "role-and-name")[0] == 0
    assert kbcommon.load_csv(str(makers_file(repo, "team")))[1] == [
        {"id": kbcommon.POLICY_ROW, "role": "role-and-name", "name": "", "source": ""}]
    repo.check()


def test_kbdecide_makers_refusals(repo):
    refused(repo, "public", "makers", "public", "--policy", "everyone", "--by", "operator", says="not one of role-only")
    refused(repo, "public", "makers", "nowhere", "--policy", "role-only", "--by", "operator", says="no root 'nowhere'")
    makers_file(repo, "team").write_text("id,role\nlead,x\n", encoding="utf-8", newline="\n")
    refused(repo, "team", "makers", "team", "--policy", "role-only", "--by", "operator", says="header is 'id,role'")


def test_kbdecide_makers_without_a_policy_argument_shows_it(repo):
    code, out = repo.decide("makers", "public")
    assert code == 0 and out.splitlines()[0] == "policy=role-only\tpublic" and "public-lead\tpublic lead\t" in out, out
    unset_policy(repo, "public")
    assert repo.decide("makers", "public")[1].splitlines()[0] == "policy=unset\tpublic"


def test_kbdecide_makers_kb_self_holds_no_policy_row(repo):
    """check.py plants the failure: a policy row in the central register, which holds roles only and has no policy."""
    write(makers_file(repo, "_self"), ",".join(kbcommon.MAKER_COLS) + f"\n{kbcommon.POLICY_ROW},role-only,,\nowner,operations owner,,\n")
    code, out = repo.run("check.py")
    assert code == 1 and "ERROR kb/_self/decision-makers.csv:2 a storage policy in kb/_self" in out, out[-600:]


# ---- sweep: a decision whose context no longer holds is invalidated, with the context named in the reason

NEW_URL = "https://docs.example.com/runbooks/patching-v2"
SWEEP_DAY = "2026-10-05"
MAKER = {"public": ["--maker", "public-lead"], "team": [], "_self": ["--maker", "owner"]}


def swept(repo, *args):
    """sweep as of SWEEP_DAY: (exit code, output)."""
    return repo.decide("sweep", "--date", SWEEP_DAY, *args)


def sweep_propose(repo, context, store="public", text="Servers patch on the second Tuesday.", review_by=None, confirm=False):
    args = ["propose", "--root", store, text, "--source", sid("T" if store == "team" else "S"), "--context", context, "--date", DAY]
    if review_by:
        args += ["--review-by", review_by]
    code, out = repo.decide(*args)
    assert code == 0, out
    did = out.split("\t")[0]
    if confirm:
        code, out = repo.decide("confirm", did, "--root", store, "--by", "operator", *MAKER[store])
        assert code == 0, out
    return did


def put_item(repo, iid, status):
    write(repo.path / "kb" / "_self" / "backlog" / f"{iid}.json", json.dumps({"id": iid, "status": status}) + "\n")


def git(repo, *args):
    p = subprocess.run(["git", *args], cwd=repo.path, env=git_env(), capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0, p.stderr
    return p.stdout


def commit_all(repo, message):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


def invalidated(repo, did, store="public"):
    row = repo.row(did, store)
    assert row["status"] == "invalidated" and row["invalidated_date"] == SWEEP_DAY, row
    return row["invalidated_reason"]


def test_decision_sweep_invalidates_on_a_dropped_item(repo):
    put_item(repo, "TK-dropped1", "dropped")
    proposed = sweep_propose(repo, "item:TK-dropped1")
    active = sweep_propose(repo, "item:TK-dropped1; domain:ops", "team", confirm=True)
    code, out = swept(repo)
    assert code == 0 and "invalidated=2" in out, out
    assert invalidated(repo, proposed) == "item:TK-dropped1 dropped"
    assert invalidated(repo, active, "team") == "item:TK-dropped1 dropped"
    row = repo.row(active, "team")
    assert (row["by"], row["text"]) == ("operator", "Servers patch on the second Tuesday."), row  # the maker stays
    assert len(repo.rows()) == 1 and len(repo.rows("team")) == 1  # nothing is deleted
    repo.check()


def test_decision_sweep_keeps_a_decision_of_a_done_or_an_open_item(repo):
    put_item(repo, "TK-donedone", "done")
    put_item(repo, "TK-stilldoi", "doing")
    ids = [sweep_propose(repo, f"item:{i}", text=f"About {i}.") for i in ("TK-donedone", "TK-stilldoi")]
    code, out = swept(repo)
    assert code == 0 and "invalidated=0" in out, out
    assert [repo.row(d)["status"] for d in ids] == ["proposed", "proposed"]


@requires_git
def test_decision_sweep_tells_a_dropped_item_from_one_deleted_at_close_by_its_last_version(repo):
    """Sprint close deletes the item files: git history keeps the last version, which says dropped or done."""
    history = (("TK-closedrp", ("todo", "dropped")), ("TK-closedon", ("todo", "done")), ("TK-flipflop", ("dropped", "done")))
    for iid, statuses in history:
        put_item(repo, iid, statuses[0])
    git(repo, "init", "-q")
    commit_all(repo, "files")
    for iid, statuses in history:
        put_item(repo, iid, statuses[1])
    commit_all(repo, "last versions")
    for iid, _ in history:
        (repo.path / "kb" / "_self" / "backlog" / f"{iid}.json").unlink()
    commit_all(repo, "close the sprint")
    dropped, done, flip, never = (sweep_propose(repo, f"item:{i}", text=f"About {i}.")
                                  for i in ("TK-closedrp", "TK-closedon", "TK-flipflop", "TK-neverhad"))
    code, out = swept(repo)
    assert code == 0 and "invalidated=1" in out, out
    assert invalidated(repo, dropped) == "item:TK-closedrp dropped"
    assert [repo.row(d)["status"] for d in (done, flip, never)] == ["proposed"] * 3  # done at close, done last, no history
    repo.check()


@requires_git
def test_decision_sweep_invalidates_an_item_dropped_outside_a_sprint_and_keeps_the_others(repo):
    """`backlog.py drop` outside a sprint deletes the file at its last status (not dropped): git history says it was
    never done. A deleted item whose last version was done, and an item still present, keep their decisions."""
    for iid, status in (("TK-droppedo", "todo"), ("TK-gonedone", "done"), ("TK-stillhre", "todo")):
        put_item(repo, iid, status)
    git(repo, "init", "-q")
    commit_all(repo, "files")
    for iid in ("TK-droppedo", "TK-gonedone"):
        (repo.path / "kb" / "_self" / "backlog" / f"{iid}.json").unlink()
    commit_all(repo, "drop outside a sprint")
    dropped, done, here = (sweep_propose(repo, f"item:{i}", text=f"About {i}.")
                           for i in ("TK-droppedo", "TK-gonedone", "TK-stillhre"))
    code, out = swept(repo, "--dry-run")
    assert code == 0 and "would_invalidate=1" in out, out  # the planted failure: the sweep left it active
    code, out = swept(repo)
    assert code == 0 and "invalidated=1" in out, out
    assert invalidated(repo, dropped) == "item:TK-droppedo dropped"
    assert [repo.row(d)["status"] for d in (done, here)] == ["proposed"] * 2
    repo.check()


def test_decision_sweep_says_nothing_of_an_item_with_no_git_history(repo):
    """Outside a git repository a missing item file proves nothing: the decision stays."""
    did = sweep_propose(repo, "item:TK-neverhad")
    code, out = swept(repo)
    assert code == 0 and "invalidated=0" in out and repo.row(did)["status"] == "proposed", out


def add_superseding_source(repo):
    path = repo.path / "kb" / "public" / kbcommon.SOURCES
    header, rows = kbcommon.load_csv(str(path))
    new = dict(rows[0], id=kbid.source_id(NEW_URL, "S"), url=NEW_URL, title="Patching runbook v2")
    rows[0]["superseded_by"] = new["id"]
    kbcommon.write_csv(str(path), header, rows + [new])
    return new["id"]


def test_decision_sweep_invalidates_on_a_superseded_source(repo):
    kept = sweep_propose(repo, "domain:ops", text="No source of this one is replaced.")
    did = sweep_propose(repo, f"source:{sid()}")
    repo.check()
    newer = add_superseding_source(repo)
    code, out = swept(repo)
    assert code == 0 and "invalidated=1" in out, out
    assert invalidated(repo, did) == f"source:{sid()} superseded by {newer}"
    assert repo.row(kept)["status"] == "proposed"
    repo.check()


def test_decision_sweep_invalidates_on_a_gone_article_or_domain(repo):
    article_d = sweep_propose(repo, "article:ops/patching", text="About the article.")
    domain_d = sweep_propose(repo, "domain:ops", text="About the domain.")
    other = sweep_propose(repo, "article:ops/patching", "team", text="Another root's.")
    self_d = sweep_propose(repo, "article:public/ops/patching", "_self", text="Of kb/_self, about public.")
    (repo.path / "kb" / "public" / "ops" / "patching.md").unlink()
    code, out = swept(repo, "--root", "public")
    assert code == 0 and "invalidated=1" in out, out  # the domain still has its directory
    assert invalidated(repo, article_d) == "article:ops/patching is gone"
    assert repo.row(domain_d)["status"] == "proposed"
    shutil.rmtree(repo.path / "kb" / "public" / "ops")
    code, out = swept(repo)  # every root and kb/_self
    assert code == 0 and "invalidated=2" in out, out
    assert invalidated(repo, domain_d) == "domain:ops is gone"
    assert invalidated(repo, self_d, "_self") == "article:public/ops/patching is gone"
    assert repo.row(other, "team")["status"] == "proposed"
    repo.check()


def test_decision_sweep_invalidates_on_a_review_by_that_passed(repo):
    late = sweep_propose(repo, "domain:ops", text="Late.", review_by="2026-10-04")
    today = sweep_propose(repo, "domain:ops", text="Today.", review_by=SWEEP_DAY)
    none = sweep_propose(repo, "domain:ops", text="No review date.")
    code, out = swept(repo)
    assert code == 0 and "invalidated=1" in out, out
    assert invalidated(repo, late) == "review_by 2026-10-04 passed"
    assert [repo.row(d)["status"] for d in (today, none)] == ["proposed", "proposed"]  # due today is not yet passed
    repo.check()


def test_decision_sweep_does_not_invalidate_on_a_fact_that_is_gone(repo):
    """A missing fact is for relink to flag, not for sweep to withdraw."""
    did = sweep_propose(repo, "fact:0123456789ab", confirm=True)
    code, out = swept(repo)
    assert code == 0 and "invalidated=0" in out, out
    assert repo.row(did)["status"] == "active"


def test_decision_sweep_names_every_broken_reference(repo):
    put_item(repo, "TK-dropped1", "dropped")
    did = sweep_propose(repo, "item:TK-dropped1; domain:ops", review_by="2026-10-01")
    code, out = swept(repo)
    assert code == 0, out
    assert invalidated(repo, did) == "item:TK-dropped1 dropped; review_by 2026-10-01 passed"


def test_decision_sweep_leaves_invalidated_and_superseded_decisions_as_they_are(repo):
    old = sweep_propose(repo, "domain:ops", text="Old.", review_by="2026-10-01", confirm=True)
    new = sweep_propose(repo, "domain:ops", text="New.", confirm=True)
    assert repo.decide("supersede", old, new, "--root", "public", "--by", "operator")[0] == 0
    withdrawn = sweep_propose(repo, "domain:ops", text="Withdrawn.", review_by="2026-10-01")
    assert repo.decide("invalidate", withdrawn, "--root", "public", "--reason", "by hand", "--date", DAY)[0] == 0
    before = repo.file().read_bytes()
    code, out = swept(repo)
    assert code == 0 and "invalidated=0" in out and repo.file().read_bytes() == before, out


def test_decision_sweep_dry_run_prints_and_writes_nothing(repo):
    put_item(repo, "TK-dropped1", "dropped")
    did = sweep_propose(repo, "item:TK-dropped1")
    before = repo.file().read_bytes()
    code, out = swept(repo, "--dry-run")
    assert code == 0 and f"{did}\twould invalidate\tpublic\titem:TK-dropped1 dropped" in out and "would_invalidate=1" in out, out
    assert repo.file().read_bytes() == before
    code, out = swept(repo)  # a run that is not a dry one does it, and the next finds nothing left
    assert code == 0 and f"{did}\tinvalidated\tpublic\titem:TK-dropped1 dropped" in out, out
    code, out = swept(repo)
    assert code == 0 and "invalidated=0" in out, out


def test_decision_sweep_takes_a_root_and_refuses_what_it_cannot_sweep(repo):
    put_item(repo, "TK-dropped1", "dropped")
    one = sweep_propose(repo, "item:TK-dropped1")
    two = sweep_propose(repo, "item:TK-dropped1", "team")
    assert swept(repo, "--root", "team")[0] == 0
    assert (repo.row(one)["status"], repo.row(two, "team")["status"]) == ("proposed", "invalidated")
    refused(repo, "public", "sweep", "--root", "nowhere", says="no root 'nowhere'")
    refused(repo, "public", "sweep", "--date", "2026-13-40", says="is not YYYY-MM-DD")


# ---- relink: sweep flags a decision whose fact is gone with the likeliest current fact; relink repoints it

OLD_FACT, NEW_FACT = "Servers patch on the second Tuesday.", "Servers are patched on the second Tuesday of each month."
OTHER_FACT = "Laptops reboot after the Friday maintenance window."
GONE_TOO = "Another fact that is gone."
ARTICLE = "public/ops/patching.md"


def set_facts(repo, *facts, store="public"):
    """Replace the facts of the store's article with these sentences, each cited to the store's source."""
    path = repo.path / "kb" / store / "ops" / "patching.md"
    head, _, rest = path.read_text(encoding="utf-8").partition("## Facts\n\n")
    cite = sid("T" if store == "team" else "S")
    write(path, head + "## Facts\n\n" + "".join(f"- {f} [DOC {cite}]\n" for f in facts) + rest[rest.index("\n## Reference"):])


def key_of(sentence, store="public"):
    return kbfacts.fact_key(f"{sentence} [DOC {sid('T' if store == 'team' else 'S')}]")


def relink_lines(out):
    return [ln.split("\t") for ln in out.splitlines() if "\trelink\t" in ln]


def flagged_decision(repo, old=OLD_FACT, store="public", context=None, text=OLD_FACT, confirm=False):
    """A decision about the fact `old`, which the caller then rewrites out of the article."""
    return sweep_propose(repo, context or f"fact:{key_of(old, store)}; article:ops/patching", store, text=text, confirm=confirm)


def suggested(out):
    """[(decision id, suggested PATH:LINE)] of the relink lines of a sweep."""
    return [(ln[0], ln[4]) for ln in relink_lines(out)]


@requires_git
def test_decision_sweep_relink_flags_a_reworded_fact_with_the_likeliest_current_one(repo):
    """The old text is read back from git history, and the reworded fact beats the unrelated one on its wording."""
    set_facts(repo, OTHER_FACT, OLD_FACT)
    did = flagged_decision(repo, confirm=True)
    git(repo, "init", "-q")
    commit_all(repo, "the facts as decided")
    set_facts(repo, OTHER_FACT, NEW_FACT)
    before = repo.file().read_bytes()
    code, out = swept(repo)
    assert code == 0 and "invalidated=0" in out and "relink=1" in out, out
    assert relink_lines(out) == [[did, "relink", "public", f"fact:{key_of(OLD_FACT)}", f"{ARTICLE}:18",
                                  f"{NEW_FACT} [DOC {sid()}]"]], out
    assert repo.file().read_bytes() == before and repo.row(did)["status"] == "active"  # the flag changes no row
    repo.check()


@requires_git
def test_decision_sweep_relink_finds_a_fact_that_moved_to_another_article(repo):
    """The files the fact was in hold nothing near it any more, so the facts of the whole root are scored."""
    set_facts(repo, OTHER_FACT, OLD_FACT)
    did = flagged_decision(repo)
    git(repo, "init", "-q")
    commit_all(repo, "the facts as decided")
    set_facts(repo, OTHER_FACT)
    moved = article(sid()).replace(OLD_FACT, NEW_FACT).replace("topic: ops/patching", "topic: ops/schedule")
    write(repo.path / "kb" / "public" / "ops" / "schedule.md", moved)
    code, out = swept(repo)
    assert code == 0 and suggested(out) == [(did, "public/ops/schedule.md:17")], out


def test_decision_sweep_relink_scores_by_the_key_terms_its_anchors_kept_when_git_has_no_history(repo):
    anchor = dict.fromkeys(kbcommon.ANCHOR_COLS, "")
    anchor.update(fact=key_of(OLD_FACT), path="ops/patching.md", source_id=sid(), status="located", heading="Facts",
                  terms="server;patch;second;tuesday", sha="0123456789abcdef", verified_utc=DAY)
    kbcommon.write_csv(str(repo.path / "kb" / "public" / kbcommon.ANCHORS), kbcommon.ANCHOR_COLS, [anchor])
    set_facts(repo, OTHER_FACT, OLD_FACT)
    did = flagged_decision(repo, text="Decided without the words of the fact.")
    set_facts(repo, OTHER_FACT, NEW_FACT)
    repo.check()
    code, out = swept(repo)
    assert code == 0 and suggested(out) == [(did, f"{ARTICLE}:18")], out


def test_decision_sweep_relink_scores_by_the_questions_doc2query_generated_for_the_fact(repo):
    write(repo.path / "kb" / "public" / kbcommon.DATA_DIR / "doc2query" / "expansions.csv",
          f"key,question\n{key_of(OLD_FACT)},When do servers get patched on Tuesday?\n")
    set_facts(repo, OTHER_FACT, OLD_FACT)
    did = flagged_decision(repo, text="Decided without the words of the fact.")
    set_facts(repo, OTHER_FACT, NEW_FACT)
    code, out = swept(repo)
    assert code == 0 and suggested(out) == [(did, f"{ARTICLE}:18")], out


def test_decision_sweep_relink_falls_back_to_the_words_of_the_decision(repo):
    set_facts(repo, OTHER_FACT, OLD_FACT)
    did = flagged_decision(repo)
    set_facts(repo, OTHER_FACT, NEW_FACT)
    code, out = swept(repo)
    assert code == 0 and suggested(out) == [(did, f"{ARTICLE}:18")], out


def test_decision_sweep_relink_names_no_fact_when_none_is_likely_enough(repo):
    """Nothing is guessed: below the cut the line says so, and the decision is flagged all the same."""
    set_facts(repo, OLD_FACT)
    did = flagged_decision(repo)
    set_facts(repo, OTHER_FACT)
    code, out = swept(repo)
    assert code == 0 and "relink=1" in out, out
    assert relink_lines(out) == [[did, "relink", "public", f"fact:{key_of(OLD_FACT)}", "-", "(no current fact is likely enough)"]], out


def test_decision_sweep_relink_says_nothing_of_a_fact_that_is_there(repo):
    set_facts(repo, OTHER_FACT, OLD_FACT)
    flagged_decision(repo, confirm=True)
    before = repo.file().read_bytes()
    code, out = swept(repo)
    assert code == 0 and "relink=0" in out and not relink_lines(out), out
    set_facts(repo, OTHER_FACT)
    code, out = swept(repo)  # gone: flagged, and no row changes
    assert code == 0 and "relink=1" in out and "invalidated=0" in out and repo.file().read_bytes() == before, out


def test_decision_sweep_relink_leaves_a_decision_that_is_invalidated_to_the_invalidation(repo):
    """A decision whose other context broke is invalidated, and not flagged for its fact as well."""
    put_item(repo, "TK-dropped1", "dropped")
    did = flagged_decision(repo, context=f"fact:{key_of(OLD_FACT)}; item:TK-dropped1")
    code, out = swept(repo)
    assert code == 0 and "relink=0" in out and not relink_lines(out), out
    assert invalidated(repo, did) == "item:TK-dropped1 dropped"
    code, out = swept(repo)  # an invalidated decision is not flagged either
    assert code == 0 and "relink=0" in out, out


def test_decision_sweep_relink_dry_run_prints_the_same_flag_and_writes_nothing(repo):
    set_facts(repo, OTHER_FACT, OLD_FACT)
    did = flagged_decision(repo)
    set_facts(repo, OTHER_FACT, NEW_FACT)
    before = repo.file().read_bytes()
    dry, real = swept(repo, "--dry-run"), swept(repo)
    assert dry[0] == real[0] == 0 and suggested(dry[1]) == suggested(real[1]) == [(did, f"{ARTICLE}:18")], (dry, real)
    assert repo.file().read_bytes() == before


def test_decision_sweep_relink_covers_every_root_and_kb_self(repo):
    set_facts(repo, OTHER_FACT, OLD_FACT, store="team")
    team = flagged_decision(repo, store="team")
    set_facts(repo, OTHER_FACT, OLD_FACT)
    mine = sweep_propose(repo, f"fact:{key_of(OLD_FACT)}", "_self", text=OLD_FACT)  # kb/_self scores the facts of every root
    set_facts(repo, OTHER_FACT, NEW_FACT)
    set_facts(repo, OTHER_FACT, NEW_FACT, store="team")
    code, out = swept(repo)
    assert code == 0 and "relink=2" in out, out
    assert sorted((ln[0], ln[2], ln[4]) for ln in relink_lines(out)) == sorted(
        [(team, "team", "team/ops/patching.md:18"), (mine, "_self", f"{ARTICLE}:18")]), out


def relink(repo, did, store, line, *extra):
    return repo.decide("relink", did, "--root", store, "--fact", line, "--date", SWEEP_DAY, *extra)


def test_decision_sweep_relink_repoints_the_gone_fact_and_keeps_the_row(repo):
    set_facts(repo, OTHER_FACT, OLD_FACT)
    did = flagged_decision(repo, confirm=True)
    before = repo.row(did)
    set_facts(repo, OTHER_FACT, NEW_FACT)
    new = key_of(NEW_FACT)
    code, out = relink(repo, did, "public", f"{ARTICLE}:18")  # no --by: open to agents
    assert code == 0 and out.split("\t")[:2] == [did, "relinked"], out
    row = repo.row(did)
    assert row["context"] == f"fact:{new}; article:ops/patching", row
    assert row["links"] == f"relinked fact:{key_of(OLD_FACT)} to fact:{new} ({ARTICLE}:18) on {SWEEP_DAY}", row
    assert {k: v for k, v in row.items() if k not in ("context", "links")} == {k: v for k, v in before.items() if k not in ("context", "links")}
    assert row["status"] == "active" and row["by_ref"] == "public-lead" and len(repo.rows()) == 1  # nothing else changes
    repo.check()
    code, out = swept(repo)  # the flag is gone
    assert code == 0 and "relink=0" in out, out


def test_decision_sweep_relink_takes_a_path_inside_the_root_and_drops_a_reference_the_decision_has_twice(repo):
    set_facts(repo, OTHER_FACT, NEW_FACT)
    did = flagged_decision(repo, context=f"fact:{key_of(OLD_FACT)}; fact:{key_of(NEW_FACT)}; domain:ops")
    code, out = relink(repo, did, "public", "ops/patching.md:18")
    assert code == 0, out
    assert repo.row(did)["context"] == f"fact:{key_of(NEW_FACT)}; domain:ops"
    repo.check()


def test_decision_sweep_relink_in_kb_self_takes_a_qualified_path_only(repo):
    set_facts(repo, NEW_FACT)
    did = sweep_propose(repo, f"fact:{key_of(OLD_FACT)}", "_self", text="Of kb/_self, about public.")
    refused(repo, "_self", "relink", did, "--root", "_self", "--fact", "ops/patching.md:17", says="is no fact")
    code, out = relink(repo, did, "_self", f"{ARTICLE}:17")
    assert code == 0 and repo.row(did, "_self")["context"] == f"fact:{key_of(NEW_FACT)}", out
    repo.check()


def test_decision_sweep_relink_refusals(repo):
    set_facts(repo, OTHER_FACT, NEW_FACT)
    set_facts(repo, OTHER_FACT, NEW_FACT, store="team")
    other = key_of(OTHER_FACT)
    did = flagged_decision(repo)
    two = flagged_decision(repo, context=f"fact:{key_of(OLD_FACT)}; fact:{key_of(GONE_TOO)}", text="About two.")
    live = flagged_decision(repo, context=f"fact:{other}", text="About a fact that is there.")
    nofact = flagged_decision(repo, context="domain:ops", text="About no fact.")
    team = flagged_decision(repo, store="team")
    for line, says in ((f"{ARTICLE}:11", "is no fact"),  # a heading, not a fact
                       (f"{ARTICLE}:1", "is no fact"), (f"{ARTICLE}:99", "is no fact"), ("public/ops/nowhere.md:3", "is no fact"),
                       ("patching.md", "is not PATH:LINE"), (f"{ARTICLE}:x", "is not PATH:LINE"), (":18", "is not PATH:LINE"),
                       ("team/ops/patching.md:18", "points only at its own facts")):
        refused(repo, "public", "relink", did, "--root", "public", "--fact", line, says=says)
    at = f"{ARTICLE}:18"
    refused(repo, "public", "relink", live, "--root", "public", "--fact", at, says="nothing to relink")
    refused(repo, "public", "relink", nofact, "--root", "public", "--fact", at, says="nothing to relink")
    refused(repo, "public", "relink", two, "--root", "public", "--fact", at, says="name the one to repoint with --old")
    refused(repo, "public", "relink", two, "--root", "public", "--fact", at, "--old", "0" * 12, says="has no context fact:")
    refused(repo, "public", "relink", live, "--root", "public", "--fact", at, "--old", other, says="still exists")
    refused(repo, "public", "relink", "nosuchid", "--root", "public", "--fact", at, says="is not a decision id")
    refused(repo, "public", "relink", "D-aaaaaaaa", "--root", "public", "--fact", at, says="no decision D-aaaaaaaa")
    refused(repo, "public", "relink", team, "--root", "team", "--fact", at, says="points only at its own facts")
    refused(repo, "public", "relink", did, "--root", "nowhere", "--fact", at, says="no root 'nowhere'")
    refused(repo, "public", "relink", did, "--root", "public", "--fact", at, "--date", "2026-13-40", says="is not YYYY-MM-DD")
    code, out = relink(repo, two, "public", at, "--old", key_of(OLD_FACT))  # the one named is repointed, the other stays
    assert code == 0 and repo.row(two)["context"] == f"fact:{key_of(NEW_FACT)}; fact:{key_of(GONE_TOO)}", out


def test_decision_sweep_relink_refuses_a_decision_that_is_no_longer_proposed_or_active(repo):
    set_facts(repo, OTHER_FACT, NEW_FACT)
    did = flagged_decision(repo)
    assert repo.decide("invalidate", did, "--root", "public", "--reason", "by hand", "--date", DAY)[0] == 0
    refused(repo, "public", "relink", did, "--root", "public", "--fact", f"{ARTICLE}:18", says="only proposed or active")


def test_decision_sweep_relink_finds_a_reworded_fact_of_the_kb_itself():
    """Real inputs: a fact of the public root, reworded (a word changed, one dropped), is the likeliest of its own
    article's facts and of the root's, and nothing is offered for a text that is none of them."""
    import kbdecide
    facts = [u for u in kbfacts.units("public") if u["tags"] and u["path"].endswith(".md")]
    texts = [u["text"] for u in facts]
    target = next(u for u in facts if len(u["text"].split()) >= 14 and texts.count(u["text"]) == 1)
    words = target["text"].split()
    reworded = " ".join(words[:2] + ["indeed"] + words[3:6] + words[7:])
    score = kbdecide.text_scorer(target["text"])
    assert score(reworded) >= 0.8, reworded
    assert kbdecide.closest([u for u in facts if u["path"] == target["path"]], kbdecide.text_scorer(reworded)) is target
    assert kbdecide.closest(facts, kbdecide.text_scorer(reworded)) is target
    assert kbdecide.closest(facts, kbdecide.text_scorer("zzqx wvvk plorp")) is None


PILOT_TITLE = "Delete the retired runbooks"


def item_file(repo, iid, gate_question="Delete the retired runbooks?", touches=("kb/public/ops/old.md",)):
    """A backlog item with one gate the autopilot answered, in the scratch repo."""
    item = {"id": iid, "kind": "story", "title": PILOT_TITLE, "status": "todo", "priority": "P2", "rank": 0,
            "goal": "The retired runbooks are gone.", "touches": list(touches),
            "gates": [{"id": "g1", "kind": "blocking", "question": gate_question, "options": ["yes", "no"],
                       "recommendation": "yes", "answer": "yes", "by": "autopilot"}]}
    write(repo.path / "kb" / "_self" / "backlog" / f"{iid}.json", json.dumps(item, indent=2) + "\n")


def autopilot_decision(repo, iid="ST-aaaaaaaa", text="yes, delete them", day="2026-10-01", question="Delete the retired runbooks?",
                       touches=("kb/public/ops/old.md",)):
    item_file(repo, iid, question, touches)
    code, out = repo.decide("record", "--root", "_self", "--by", "autopilot", "--source", f"backlog item {iid} gate g1",
                            "--context", f"item:{iid}", "--review-by", "2026-11-01", "--date", day, "--", text)
    assert code == 0, out
    return out.split("\t")[0]


def stories(repo):
    return sorted((repo.path / "kb" / "_self" / "backlog").glob("ST-*.json"))


def test_autopilot_ratify_makes_the_decision_the_operators(repo):
    did = autopilot_decision(repo)
    assert repo.row(did, "_self")["by"] == "autopilot"
    code, out = repo.decide("ratify", did, "--by", "operator", "--date", "2026-10-05")
    assert code == 0 and out.startswith(f"{did}\tratified"), out
    row = repo.row(did, "_self")
    assert (row["status"], row["by"], row["by_ref"], row["date"], row["review_by"]) == ("active", "operator", "operator", "2026-10-05", "")
    assert "ratified 2026-10-05" in row["links"] and row["text"] == "yes, delete them"
    repo.check()
    code, out = repo.decide("digest")  # a ratified decision is no longer listed
    assert code == 0 and "0 unratified" in out
    refused(repo, "_self", "ratify", did, "--by", "operator", says="is not an autopilot decision")  # nothing to ratify twice


@pytest.mark.parametrize("by", [None, "autopilot", "agent", "Operator", ""])
def test_autopilot_ratify_and_revert_refuse_any_by_but_operator(repo, by):
    did = autopilot_decision(repo)
    before = len(stories(repo))
    for cmd in (("ratify", did), ("revert", did, "--why", "wrong")):
        refused(repo, "_self", *cmd, *(("--by", by) if by is not None else ()), says="only the operator")
    assert len(stories(repo)) == before and repo.row(did, "_self")["by"] == "autopilot"


def test_autopilot_ratify_refuses_what_is_not_an_active_autopilot_decision(repo):
    refused(repo, "_self", "ratify", "D-aaaaaaaa", "--by", "operator", says="no decision D-aaaaaaaa")
    did = autopilot_decision(repo)
    assert repo.decide("invalidate", did, "--root", "_self", "--reason", "by hand", "--date", DAY)[0] == 0
    refused(repo, "_self", "ratify", did, "--by", "operator", says="only active")
    refused(repo, "_self", "revert", did, "--by", "operator", "--why", "x", says="only active")
    own = propose(repo, "_self")
    assert repo.decide("confirm", own, "--root", "_self", "--by", "operator", "--maker", "operator")[0] == 0
    refused(repo, "_self", "ratify", own, "--by", "operator", says="is not an autopilot decision")
    refused(repo, "_self", "revert", own, "--by", "operator", "--why", "x", says="is not an autopilot decision")


def test_autopilot_ratify_revert_invalidates_and_files_a_story_naming_what_to_undo(repo):
    did = autopilot_decision(repo)
    before = set(stories(repo))
    code, out = repo.decide("revert", did, "--by", "operator", "--why", "the runbooks are still used", "--date", "2026-10-06")
    assert code == 0 and out.startswith(f"{did}\tinvalidated") and "story ST-" in out, out
    row = repo.row(did, "_self")
    assert row["status"] == "invalidated" and row["invalidated_date"] == "2026-10-06"
    assert "reverted by the operator: the runbooks are still used" in row["invalidated_reason"]
    new = [f for f in stories(repo) if f not in before]
    assert len(new) == 1 and new[0].stem == out.split("story ")[1].strip()
    story = json.loads(new[0].read_text(encoding="utf-8"))
    for needle in (did, "ST-aaaaaaaa", PILOT_TITLE, "yes, delete them", "the runbooks are still used", "kb/public/ops/old.md"):
        assert needle in story["title"] + story["goal"], (needle, story)
    assert story["touches"] == ["kb/public/ops/old.md"]
    repo.check()


def test_autopilot_ratify_revert_with_no_reason_files_nothing(repo):
    did = autopilot_decision(repo)
    before = set(stories(repo))
    refused(repo, "_self", "revert", did, "--by", "operator", "--why", "  ", says="--why is empty")
    assert set(stories(repo)) == before


def read_digest(repo):
    out = repo.path / "digest.md"
    code, msg = repo.decide("digest", "--out", str(out))
    assert code == 0, msg
    return out.read_text(encoding="utf-8"), msg


def test_autopilot_ratify_digest_is_empty_without_autopilot_decisions(repo):
    text, msg = read_digest(repo)
    assert "0 unratified" in msg and "No unratified autopilot decisions." in text and "- D-" not in text
    propose(repo, "_self")  # a proposal is not an autopilot decision either
    assert "No unratified autopilot decisions." in read_digest(repo)[0]


def test_autopilot_ratify_digest_lists_restricted_classes_first_then_oldest_first(repo):
    plain = autopilot_decision(repo, "ST-bbbbbbbb", "plain, old", "2026-09-01", "Which name does it take?", ())
    query = autopilot_decision(repo, "ST-cccccccc", "querylog, newer", "2026-09-20", "Keep the query log on?", ())
    newer = autopilot_decision(repo, "ST-dddddddd", "plain, newer", "2026-09-25", "Which name does it take?", ())
    delete = autopilot_decision(repo, "ST-eeeeeeee", "delete, newest", "2026-09-30")
    assert repo.decide("ratify", newer, "--by", "operator")[0] == 0
    text, msg = read_digest(repo)
    assert "3 unratified" in msg
    order = [text.index(d) for d in (query, delete, plain)]
    assert order == sorted(order), text  # restricted (oldest first), then the rest
    assert newer not in text
    assert text.index("## Restricted") < text.index(query) < text.index(delete) < text.index("## Other") < text.index(plain)
    line = next(ln for ln in text.splitlines() if delete in ln)
    for needle in ("(delete)", "ST-eeeeeeee", PILOT_TITLE, "gate g1", "delete, newest", "review_by 2026-11-01"):
        assert needle in line, (needle, line)
    assert "(querylog)" in next(ln for ln in text.splitlines() if query in ln)
    assert "(design)" in next(ln for ln in text.splitlines() if plain in ln)


def test_autopilot_ratify_digest_rewrites_the_default_file(repo):
    autopilot_decision(repo)
    code, out = repo.decide("digest")
    assert code == 0, out
    assert "ST-aaaaaaaa" in (repo.path / "kb" / "_self" / "reports" / "autopilot-digest.md").read_text(encoding="utf-8")


def disagreement_lines(repo):
    text = read_digest(repo)[0]
    return [ln for ln in text.splitlines() if ln.startswith("- Reverted") or ln.startswith("- Contradicting")], text


def test_autopilot_rot_metrics_digest_counts_reverts_and_contradictions_exactly(repo):
    first = autopilot_decision(repo, "ST-aaaaaaaa", "yes, delete them", "2026-09-01")
    second = autopilot_decision(repo, "ST-bbbbbbbb", "no, keep them", "2026-09-02")  # same gate id and class, another answer
    other = autopilot_decision(repo, "ST-cccccccc", "use the short name", "2026-09-03", "Which name does it take?", ())  # another class
    own = propose(repo, "_self")  # a decision of the operator's is none of the autopilot's
    assert repo.decide("confirm", own, "--root", "_self", "--by", "operator", "--maker", "operator")[0] == 0
    lines, _ = disagreement_lines(repo)
    assert lines == ["- Reverted by the operator: 0 of 3 (0%) autopilot decisions",
                     "- Contradicting an earlier decision of the same gate and class: 1 of 3 (33%) autopilot decisions"], lines
    assert repo.decide("revert", first, "--by", "operator", "--why", "wrong", "--date", "2026-10-06")[0] == 0
    assert repo.decide("ratify", other, "--by", "operator", "--date", "2026-10-07")[0] == 0  # ratified: still one the autopilot made
    lines, text = disagreement_lines(repo)
    assert lines == ["- Reverted by the operator: 1 of 3 (33%) autopilot decisions",
                     "- Contradicting an earlier decision of the same gate and class: 1 of 3 (33%) autopilot decisions"], lines
    assert "1 unratified" not in text and second in text  # the section sits above the list, which keeps its entries


def counts(repo):
    """(made, reverted, contradicting) as the digest's two lines print them."""
    lines, _ = disagreement_lines(repo)
    got = [tuple(map(int, re.search(r"(\d+) of (\d+)", ln).groups())) for ln in lines]
    assert got[0][1] == got[1][1]
    return got[1][1], got[0][0], got[1][0]


def test_autopilot_rot_metrics_contradiction_rule(repo):
    """A later decision counts once when any earlier one of its gate id and class has another answer; the order is the day
    made; whitespace and case of an answer do not make another answer; another class never contradicts."""
    autopilot_decision(repo, "ST-aaaaaaaa", "Yes, delete them", "2026-09-01")
    autopilot_decision(repo, "ST-bbbbbbbb", "yes,   DELETE them", "2026-09-02")
    assert counts(repo) == (2, 0, 0), "same answer apart from case and spacing"
    autopilot_decision(repo, "ST-cccccccc", "no", "2026-09-03")
    autopilot_decision(repo, "ST-dddddddd", "no", "2026-09-04")  # differs from the first two: once, not twice
    autopilot_decision(repo, "ST-eeeeeeee", "maybe", "2026-09-05", "Which name does it take?", ())
    assert counts(repo) == (5, 0, 2)
    autopilot_decision(repo, "ST-ffffffff", "yes", "2026-08-01")  # made first: it is the earlier one the rest differ from
    assert counts(repo) == (6, 0, 4)


def test_autopilot_rot_metrics_empty_ledger_prints_zero_of_zero(repo):
    lines, text = disagreement_lines(repo)
    assert lines == ["- Reverted by the operator: 0 of 0 autopilot decisions",
                     "- Contradicting an earlier decision of the same gate and class: 0 of 0 autopilot decisions"], text
