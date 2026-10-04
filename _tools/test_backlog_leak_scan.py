"""`backlog.py check` refuses a leak-scan hit in an item's text (kb/_self/backlog.md, Writing about items;
kb/_self/tools.md, the `check` row): the planted hits are built from parts here, so this file holds no address,
id or path shape for the tracked-file scan to find, and the planted failure turns the scan off to prove the test
would notice its removal."""
import pytest

import backlog
import bl_check
import bl_testkit
from bl_testkit import argstr, b, edit, is_file, item

bl_testkit.bind(backlog)

repo, no_git_location, gate_jobs = bl_testkit.repo, bl_testkit.no_git_location, bl_testkit.gate_jobs

# each planted value, joined from fragments; the ip and the email are not in _tools/tests_allowlist.txt
VALUES = {
    "guid": "-".join(("1a2b3c4d", "5e6f", "7a8b", "9c0d", "1e2f3a4b5c6d")),
    "ip": ".".join(("10", "77", "88", "99")),
    "email": "@".join(("real.person", "corp-mail.net")),
    "home": "/".join(("", "Users", "realperson", "docs")),
    "secret": "".join(("AKIA", "ABCDEFGH", "IJKLMNOP")),
}
ALLOWED = ("guid", "ip", "email", "secret")  # the kinds the allowlist can except (a home path has none)
FIELDS = ("title", "goal", "notes", "repro", "gate question", "gate answer")


@pytest.fixture
def lone(repo):
    """An epic and a bug in a repository, each valid and holding no hit."""
    assert b(repo, "new", "epic", "--title", "Epic", "--goal", "outcome")[0] == 0
    code, out = b(repo, "new", "bug", "--title", "Bug", "--severity", "S3", "--parent", item(repo, "Epic")["id"],
                  "--repro", argstr(is_file("src/c.txt")), "--goal", "c exists", "--touch", "src/**")
    assert code == 0, out
    return {"repo": repo, "ep": item(repo, "Epic")["id"], "bg": item(repo, "Bug")["id"]}


def gate(**kw):
    return [{"id": "g", "kind": "blocking", "question": "Which tool?", "options": ["one", "two"],
             "recommendation": "one", "answer": "one", "by": "operator", **kw}]


def plant(lone, field, text):
    """Write TEXT into FIELD of the epic (the bug for repro); the id and the path the error must name."""
    repo, ep, bg = lone["repo"], lone["ep"], lone["bg"]
    if field == "repro":
        edit(repo, bg, repro={"run": ["python3", "-c", f"print({text!r})"]})
        return bg, "repro.run[2]"
    if field in ("gate question", "gate answer"):
        key = field.split()[1]
        edit(repo, ep, gates=gate(**{key: text}))
        return ep, f"gates[0].{key}"
    edit(repo, ep, **{field: text})
    return ep, field


def checked(repo, capsys):
    code = backlog.main(["--root", str(repo), "check"])
    return code, capsys.readouterr().out


@pytest.mark.parametrize("kind", sorted(VALUES))
@pytest.mark.parametrize("field", FIELDS)
def test_backlog_check_refuses_leak_in_item_text(lone, capsys, monkeypatch, field, kind):
    repo, value = lone["repo"], VALUES[kind]
    assert checked(repo, capsys)[0] == 0  # the lone items are clean
    iid, path = plant(lone, field, f"see {value} here")
    code, out = checked(repo, capsys)
    assert code == 1 and f"{iid}: field {path} has a leak-scan hit ({kind}" in out, out
    assert value not in out and value.split("@")[0] not in out and "errors=1" in out, out
    # the same through the command line: the push gate's form and its exit code
    code, out = b(repo, "check")
    assert code == 1 and f"{iid}: field {path} has a leak-scan hit ({kind}" in out and value not in out, out
    # the planted failure: with the scan reporting nothing the item passes, so removing the scan fails this test
    monkeypatch.setattr(bl_check, "item_leak_hits", lambda text, allow: [])
    assert checked(repo, capsys)[0] == 0


def test_backlog_check_leak_in_title_never_prints_the_title(lone, capsys):
    """A hit in a title is named by id and field only: no later error prints the title that holds it."""
    value = VALUES["guid"]
    edit(lone["repo"], lone["ep"], title=f"Epic {value}", goal="")  # a second error that prints the item's label
    code, out = checked(lone["repo"], capsys)
    assert code == 1 and f"{lone['ep']}: field title has a leak-scan hit (guid" in out and value not in out, out
    assert f"{lone['ep']} (title withheld" in out, out


def test_backlog_check_leak_kinds_are_all_named_once_per_field(lone, capsys):
    edit(lone["repo"], lone["ep"], notes=f"{VALUES['ip']} and {VALUES['ip']} and {VALUES['email']}")
    code, out = checked(lone["repo"], capsys)
    assert code == 1 and out.count("field notes has a leak-scan hit (email, ip;") == 1, out
    assert "errors=1" in out and VALUES["ip"] not in out and VALUES["email"] not in out, out


@pytest.mark.parametrize("kind", ALLOWED)
def test_backlog_check_leak_allowlisted_value_passes(lone, capsys, kind):
    """A value on the clone's _tools/tests_allowlist.txt, read by the reader the scan of tracked files uses, passes;
    the same value without its entry is refused."""
    repo, value = lone["repo"], VALUES[kind]
    edit(repo, lone["ep"], goal=f"quotes {value.upper()} once")
    assert checked(repo, capsys)[0] == 1
    (repo / "_tools").mkdir()
    (repo / "_tools" / "tests_allowlist.txt").write_text(f"# reviewed\n{kind}  {value.lower()}  # a planted example\n",
                                                         encoding="utf-8")
    code, out = checked(repo, capsys)
    assert code == 0 and "errors=0" in out, out
    (repo / "_tools" / "tests_allowlist.txt").write_text(f"{kind}  other-value\n", encoding="utf-8")
    assert checked(repo, capsys)[0] == 1  # an entry for another value excepts nothing


@pytest.mark.parametrize("text", ["see 192.0.2.7 and jan.kowalski@example.com", "tenant 00000000-0000-0000-0000-000000000000",
                                  "PL-LT-00123 and PL-SRV-0042 in /home/<user>/x", "a sentence with no shape at all"])
def test_backlog_check_leak_placeholders_pass(lone, capsys, text):
    edit(lone["repo"], lone["ep"], notes=text)
    code, out = checked(lone["repo"], capsys)
    assert code == 0 and "errors=0" in out, out


def test_backlog_check_leak_in_a_new_item_is_reported_and_check_then_fails(lone, capsys):
    """`new` writes its item and lists what is still to fix, a quoted address among it, without printing the address;
    `check` then refuses the item before it is committed."""
    repo = lone["repo"]
    code, out = b(repo, "new", "bug", "--title", "Quoted", "--severity", "S3", "--repro", argstr(is_file("src/c.txt")),
                  "--goal", f"host {VALUES['ip']} fails", "--touch", "src/**")
    assert "field goal has a leak-scan hit (ip" in out and VALUES["ip"] not in out, out
    iid = item(repo, "Quoted")["id"]
    code, out = checked(repo, capsys)
    assert code == 1 and f"{iid}: field goal has a leak-scan hit (ip" in out and VALUES["ip"] not in out, out
