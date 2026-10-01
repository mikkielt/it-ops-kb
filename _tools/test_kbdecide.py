#!/usr/bin/env python3
"""kbdecide.py: propose, confirm, supersede, invalidate, restore and list, over a small repository of its own.

The repository is a copy of the four modules the tool imports with three stores: the public root (not internal: it
keeps no names), an internal root `team`, and kb/_self with its central register of decision makers. Every command
runs as a process; every success is followed by check.py over the whole repository, and every refusal plants the
failure it names and finds the file as it was.
"""
import base64, hashlib, os, shutil, subprocess, sys
from pathlib import Path

import pytest

import kbcommon, kbid

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


@pytest.fixture(scope="module")
def template(tmp_path_factory):
    """The repository every test starts from."""
    repo = tmp_path_factory.mktemp("kbdecide") / "repo"
    for name in ("kbdecide.py", "check.py", "kbcommon.py", "kbid.py"):
        (repo / "_tools").mkdir(parents=True, exist_ok=True)
        shutil.copy(TOOLS / name, repo / "_tools" / name)
    make_root(repo / "kb" / "public", "public", "S", "public")
    make_root(repo / "kb" / "team", "team", "T", "internal")
    write(repo / "kb" / "public" / kbcommon.DECISION_MAKERS, ",".join(kbcommon.MAKER_COLS) + "\n"
          + "public-lead,public lead,,\n")
    write(repo / "kb" / "team" / kbcommon.DECISION_MAKERS, ",".join(kbcommon.MAKER_COLS) + "\n"
          + f"lead,team lead,Jan Kowalski,{kbid.source_id(URL, 'T')}\n")
    write(repo / "kb" / "_self" / kbcommon.DECISIONS, ",".join(kbcommon.DECISION_COLS) + "\n")
    write(repo / "kb" / "_self" / kbcommon.DECISION_MAKERS, ",".join(kbcommon.MAKER_COLS) + "\nowner,operations owner,,\n")
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


def active(repo, store="team", text="Servers patch on the second Tuesday."):
    did = propose(repo, store, text)
    maker = ["--maker", "public-lead"] if store == "public" else []
    assert repo.decide("confirm", did, "--root", store, "--by", "operator", *maker)[0] == 0
    return did


def test_kbdecide_supersede_marks_the_old_one_and_lists_it_in_the_new(repo):
    old, new = active(repo, "team", "Old."), active(repo, "team", "New.")
    code, out = repo.decide("supersede", old, new, "--root", "team")
    assert code == 0 and f"superseded by {new}" in out, out
    assert repo.row(old, "team")["status"] == "superseded"
    assert repo.row(new, "team")["supersedes"] == old and repo.row(new, "team")["status"] == "active"
    assert len(repo.rows("team")) == 2
    third = active(repo, "team", "Third.")
    assert repo.decide("supersede", new, third, "--root", "team")[0] == 0
    assert repo.row(third, "team")["supersedes"] == new
    repo.check()


def test_kbdecide_supersede_refusals(repo):
    one, two = active(repo, "team", "One."), active(repo, "team", "Two.")
    proposed = propose(repo, "team", "Proposed.")
    refused(repo, "team", "supersede", one, one, "--root", "team", says="cannot supersede itself")
    refused(repo, "team", "supersede", one, proposed, "--root", "team", says=f"{proposed} is proposed")
    refused(repo, "team", "supersede", proposed, one, "--root", "team", says=f"{proposed} is proposed")
    refused(repo, "team", "supersede", one, "D-aaaaaaaa", "--root", "team", says="no decision D-aaaaaaaa")
    assert repo.decide("supersede", one, two, "--root", "team")[0] == 0
    refused(repo, "team", "supersede", one, two, "--root", "team", says=f"{one} is superseded")


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
    proposed = propose(repo, "team", "Never confirmed.")
    refused(repo, "team", "invalidate", proposed, "--root", "team", "--reason", "x", says="is proposed: only active decisions")
    refused(repo, "team", "invalidate", did, "--root", "team", "--reason", "x", "--date", "tomorrow", says="is not YYYY-MM-DD")
    assert repo.decide("invalidate", did, "--root", "team", "--reason", "x")[0] == 0
    refused(repo, "team", "invalidate", did, "--root", "team", "--reason", "again", says="is invalidated: only active decisions")
    other, newer = active(repo, "team", "Other."), active(repo, "team", "Newer.")
    assert repo.decide("supersede", other, newer, "--root", "team")[0] == 0
    refused(repo, "team", "invalidate", other, "--root", "team", "--reason", "x", says="is superseded: only active decisions")


def test_kbdecide_restore_brings_back_what_it_was_and_keeps_the_row(repo):
    confirmed = active(repo, "team")
    assert repo.decide("invalidate", confirmed, "--root", "team", "--reason", "by mistake", "--date", "2026-10-03")[0] == 0
    code, out = repo.decide("restore", confirmed, "--root", "team")
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
    assert repo.decide("restore", did, "--root", "team")[0] == 0
    assert repo.row(did, "team")["status"] == "proposed"


def test_kbdecide_restore_refuses_what_is_not_invalidated(repo):
    did = active(repo, "team")
    refused(repo, "team", "restore", did, "--root", "team", says="is active: only invalidated decisions")
    refused(repo, "team", "restore", "D-aaaaaaaa", "--root", "team", says="no decision D-aaaaaaaa")
    refused(repo, "team", "restore", "nope", "--root", "team", says="is not a decision id")


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
                 ("restore", did, "--root", "team")):
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
