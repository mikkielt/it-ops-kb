#!/usr/bin/env python3
"""kbdecide.py: propose, confirm, supersede, invalidate, restore, sweep, makers and list, over a small repository of its own.

The repository is a copy of the four modules the tool imports with three stores: the public root (not internal: it
keeps no names), an internal root `team`, and kb/_self with its central register of decision makers. Every command
runs as a process; every success is followed by check.py over the whole repository, and every refusal plants the
failure it names and finds the file as it was.
"""
import base64, hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

import pytest

import kbcommon, kbid
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
          + f"{kbcommon.POLICY_ROW},role-only,,\npublic-lead,public lead,,\n")
    write(repo / "kb" / "team" / kbcommon.DECISION_MAKERS, ",".join(kbcommon.MAKER_COLS) + "\n"
          + f"{kbcommon.POLICY_ROW},role-and-name,,\nlead,team lead,Jan Kowalski,{kbid.source_id(URL, 'T')}\n")
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
