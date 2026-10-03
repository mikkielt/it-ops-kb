"""kb-verify lint: a CODE pointer's path must match the pinned path of its source (as kbingest drift does)."""
import importlib.util
from pathlib import Path

from conftest import TOOLS

import kbfacts

LINT = Path(TOOLS).parent / ".claude" / "skills" / "kb-verify" / "lint.py"
spec = importlib.util.spec_from_file_location("kbverify_lint", LINT)
lint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lint)

PIN = "https://github.com/contoso/web/blob/0123456789abcdef0123456789abcdef01234567/Contoso.Web.App/Program.cs"
SOURCES = {"S1": {"id": "S1", "url": PIN}, "S2": {"id": "S2", "url": "https://learn.microsoft.com/en-us/x"}}


def off_pin(note, ids=("S1",)):
    part = kbfacts.parse_tag(f"[CODE {ids[0]}: {note}]")[0]
    ptr = kbfacts.code_pointer(part)
    return ptr is not None and lint.pointer_off_pin(ptr, list(ids), SOURCES, part["note"])


def test_lint_code_pointer_matches_source_path_fails_docs_url_note():
    for note in ("learn.microsoft.com/en-us/x#y", "github.com/contoso/web/x.py#sym",
                 "raw.githubusercontent.com/contoso/web/main/x.py#sym", "Contoso.Web.Other/Startup.cs#Main"):
        part = kbfacts.parse_tag(f"[CODE S1: {note}]")[0]
        ptr = kbfacts.code_pointer(part)
        assert ptr is None or lint.pointer_off_pin(ptr, ["S1"], SOURCES, part["note"]), note


def test_lint_code_pointer_matches_source_path_passes_valid_path():
    assert not off_pin("Contoso.Web.App/Program.cs#Main")
    assert not off_pin("Program.cs#Main")  # trailing segments of the pinned path
    assert not off_pin("Contoso.Web.Other/Startup.cs#Main", ids=("S1", "S2"))  # a page source is not judged


def test_lint_code_pointer_matches_source_path_accepts_a_named_file_beside_a_pointer():
    part = kbfacts.parse_tag("[CODE S1: Contoso.Web.App/Program.cs doc comment; the default is in Contoso.Web.Other/Startup.cs#Main]")[0]
    ptr = kbfacts.code_pointer(part)
    assert not lint.pointer_off_pin(ptr, ["S1"], SOURCES, part["note"])
