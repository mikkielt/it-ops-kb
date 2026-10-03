"""The statements about a headless run in kb/_self/backlog.md, kb/_self/git.md and kg_sync.headless_target_refusal's
docstring match the code: Edit and Write are not "allowed outright" (a permission rule allows them and the headless
guard denies an edit of the settings), a headless sync pushes main only (the code/<id> lane branches come from sync's own
internal push), and a check is not always a python3 script under _tools/ (inline python3 -c stays allowed).

Planted failure: each predicate fails on the old wording, so the assertions over the real text would fail on it."""
from pathlib import Path

import kg_sync

ROOT = Path(__file__).resolve().parent.parent
SELF = ROOT / "kb" / "_self"
OLD_WORDING = ("allowed outright", "every check is a python3 script", "its `code/<id>` lane branches")
MAIN_ONLY_DOC = "its sync pushes main only"
MAIN_ONLY_GIT = "pushes `main` of the integration remote only"


def read(name):
    return (SELF / name).read_text(encoding="utf-8")


def says_old(text):
    return any(w in text for w in OLD_WORDING)


def names_main_only(text, phrase):
    return phrase in text and "its `code/<id>` lane branches" not in text


def test_docs_headless_statements_match_code():
    backlog, git = read("backlog.md"), read("git.md")
    assert not says_old(backlog) and not says_old(git)
    assert names_main_only(git, MAIN_ONLY_GIT)
    assert names_main_only(kg_sync.headless_target_refusal.__doc__, MAIN_ONLY_DOC)
    assert "allows `Edit` and `Write`" in backlog
    # planted failure: the old wording trips the same predicates
    assert says_old("`Edit` and `Write` are allowed outright in settings")
    assert says_old("every check is a python3 script under _tools/")
    assert not names_main_only("the run pushes only to main and its `code/<id>` lane branches", MAIN_ONLY_GIT)
