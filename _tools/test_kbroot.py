"""A second root beside kb/public, made with kbroot.py in a copy of the kb: the per-root checks see it.

kbroot.py add refuses a taken name or prefix and creates a root that build_index.py and check.py accept; an article
of that root cites the root's own source ids (`T-...`); a citation of another root's id is an error that names the
root; two roots with one prefix are an error; kbid.py url --root gives the root's id; lint.py names findings by
their qualified path.
"""
import os, shutil, subprocess, sys

import pytest

from conftest import copy_kb

import kbid

URL = "https://docs.example.com/runbooks/patching"
SID = kbid.source_id(URL, "T")


def run(d, tool, *args):
    path = os.path.join(d, ".claude", "skills", "kb-verify", "lint.py") if tool == "lint.py" else os.path.join(d, "_tools", tool)
    p = subprocess.run([sys.executable, path, *args], cwd=d, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=300, env={k: v for k, v in os.environ.items() if k != "KB_ROOTS"})
    return p.returncode, p.stdout + p.stderr


def write(d, rel, text):
    os.makedirs(os.path.dirname(os.path.join(d, rel)), exist_ok=True)
    with open(os.path.join(d, rel), "w", encoding="utf-8", newline="") as f:
        f.write(text)


def article(sid, extra=""):
    return (f"---\ntopic: ops/patching\npriority: P1\nretrieved_utc: 2026-09-27\nsources: [{sid}]\nstatus: complete\n---\n\n"
            f"# Patching\n\n## Summary\n\nHow the team patches.\n\n## Facts\n\n- Servers patch on the second Tuesday. [DOC {sid}]\n"
            f"{extra}\n## Reference\n\n- runbook\n\n## Examples\n\n- none\n")


@pytest.fixture(scope="module")
def kb(tmp_path_factory):
    """A kb copy with a root `team` (prefix T) holding one article that cites the root's own source."""
    d = copy_kb(str(tmp_path_factory.mktemp("roots") / "kb"))
    for name in os.listdir(os.path.join(d, "kb")):  # a fork's own roots (even one named team) stay out of the copy
        if name != "public" and os.path.isfile(os.path.join(d, "kb", name, "_root.md")):
            shutil.rmtree(os.path.join(d, "kb", name))
    code, out = run(d, "kbroot.py", "add", "team", "--prefix", "T", "--description", "the team's runbooks")
    assert code == 0, out
    with open(os.path.join(d, "kb", "team", "_sources.csv"), "a", encoding="utf-8", newline="") as f:
        f.write(f"{SID},{URL},Patching runbook,Example team,internal,quote,2026-09-27,,,,\n")
    write(d, "kb/team/ops/patching.md", article(SID))
    code, out = run(d, "build_index.py")
    assert code == 0 and "wrote team/_coverage.csv" in out, out
    return d


def test_add_refuses_taken_or_bad(kb):
    for args in (("team", "--prefix", "X"), ("other", "--prefix", "T"), ("other", "--prefix", "S"),
                 ("other", "--prefix", "QK"), ("Bad_Name", "--prefix", "B"), ("kb", "--prefix", "B")):
        code, out = run(kb, "kbroot.py", "add", *args)
        assert code == 2 and "refused" in out, (args, out)
    code, out = run(kb, "kbroot.py", "list")
    assert code == 0 and "team\tprefix=T\tinternal" in out and "roots=2" in out, out


def test_new_root_passes_the_checks(kb):
    sid = SID
    assert sid.startswith("T-")
    assert run(kb, "build_index.py", "--check")[0] == 0
    code, out = run(kb, "check.py")
    assert code == 0, out
    with open(os.path.join(kb, "kb", "team", "_sources.csv"), encoding="utf-8") as f:
        assert "ops/patching.md" in f.read()  # used_in is relative to the root
    with open(os.path.join(kb, "kb", "team", "_coverage.md"), encoding="utf-8") as f:
        assert "`ops/patching`" in f.read()
    code, out = run(kb, "kbid.py", "url", URL, "--root", "team")
    assert code == 0 and out.startswith(sid) and "already in team/_sources.csv" in out, out
    assert run(kb, "kbid.py", "check")[1].startswith("roots=2 ")
    code, out = run(kb, "lint.py", "team/ops")
    assert code == 0 and "errors=0" in out, out


def test_cross_root_citation_is_an_error(kb):
    sid = SID
    with open(os.path.join(kb, "kb", "public", "_sources.csv"), encoding="utf-8") as f:
        public_id = f.read().splitlines()[1].split(",")[0]
    write(kb, "kb/team/ops/patching.md", article(sid, f"- A vendor fact. [DOC {public_id}]\n"))
    code, out = run(kb, "check.py")
    assert code == 1 and f"team/ops/patching.md cites {public_id} of root public" in out, out
    write(kb, "kb/team/ops/patching.md", article(sid, "- A made-up id. [DOC T-zzzzzzzz]\n"))
    code, out = run(kb, "check.py")
    assert code == 1 and "cites unknown source T-zzzzzzzz" in out, out
    write(kb, "kb/team/ops/patching.md", article(sid))


def test_clashing_or_malformed_root_is_an_error(kb):
    write(kb, "kb/twin/_root.md", "---\nroot: twin\nid_prefix: T\nvisibility: internal\n---\n")
    code, out = run(kb, "check.py")
    assert code == 1 and "share the id_prefix 'T'" in out, out
    write(kb, "kb/twin/_root.md", "---\nroot: twin\nid_prefix: lower\n---\n")
    code, out = run(kb, "check.py")
    assert code == 1 and "id_prefix" in out, out
    os.remove(os.path.join(kb, "kb", "twin", "_root.md"))
    assert run(kb, "check.py")[0] == 0
