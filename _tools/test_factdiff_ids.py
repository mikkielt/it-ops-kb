"""factdiff.drop_citation keeps the id of every tag part it rewrites (`python3 _tools/tests.py -k drop_citation`).

A DECISION or LOG part carries its id in `decision` or `log` (parse_tag leaves `ids` empty), so a rewrite from kind,
ids and note alone wrote them as a bare kind. Each case runs in a subprocess on a throwaway root named by KB_ROOTS, so
the suite's own roots are never touched and no process state is shared.
"""
import os
import subprocess
import sys

import pytest

from conftest import TOOLS

ROOT_MD = "---\nroot: fixture\nid_prefix: FXT\nvisibility: internal\ndescription: x\n---\n"

RUN = r"""
import os, sys
sys.path.insert(0, sys.argv[1])
import factdiff, kbcommon, kbfacts
d, sid, why = sys.argv[2:5]
factdiff.ROOT = kbcommon.root("fixture")
key = next(kbfacts.fact_key(u["text"]) for u in kbfacts.units("fixture") if "14 days" in u["text"])
print(factdiff.drop_citation("print/queues.md", key, sid, why))
"""


def drop(tmp_path, tag, sid, why="gone"):
    """The fact line after drop_citation(sid) on a one-fact article tagged `tag`, and what the call returned."""
    (tmp_path / "print").mkdir()
    (tmp_path / "_root.md").write_text(ROOT_MD, encoding="utf-8", newline="\n")
    art = tmp_path / "print" / "queues.md"
    art.write_text(f"---\ntopic: print/queues\n---\n\n## Facts\n- Jobs are kept 14 days. {tag}\n", encoding="utf-8", newline="\n")
    env = {**os.environ, "KB_ROOTS": str(tmp_path)}
    p = subprocess.run([sys.executable, "-c", RUN, TOOLS, str(tmp_path), sid, why], capture_output=True, text=True,
                       encoding="utf-8", env=env)
    assert p.returncode == 0, p.stderr
    line = next(ln for ln in art.read_text(encoding="utf-8").split("\n") if "14 days" in ln)
    return line, p.stdout.strip()


# a decision id and a log id built to the shapes kbcommon.DECISION_ID and kbfacts.LOG_ID accept
DEC = "D-" + "k3f7q2zd"
LOG = "L-" + "aaaaaaaa"


def test_drop_citation_keeps_decision_and_log_ids(tmp_path_factory):
    line, done = drop(tmp_path_factory.mktemp("log"), f"[DOC S1208, S1209; LOG {LOG}]", "S1208")
    assert done == "True" and line == f"- Jobs are kept 14 days. [DOC S1209; LOG {LOG}]"

    line, done = drop(tmp_path_factory.mktemp("logn"), f"[DOC S1208, S1209; LOG {LOG}: seen twice]", "S1209")
    assert line == f"- Jobs are kept 14 days. [DOC S1208; LOG {LOG}: seen twice]"

    line, done = drop(tmp_path_factory.mktemp("dec"), f"[DOC S1208, S1209; DECISION {DEC}]", "S1208")
    assert line == f"- Jobs are kept 14 days. [DOC S1209; DECISION {DEC}]"

    line, done = drop(tmp_path_factory.mktemp("decn"), f"[DECISION {DEC}: operator call; DOC S1208, S1209]", "S1209")
    assert line == f"- Jobs are kept 14 days. [DECISION {DEC}: operator call; DOC S1208]"

    # the only source of the tag goes: that part becomes UNK, the LOG and DECISION ids stay
    line, done = drop(tmp_path_factory.mktemp("only"), f"[DOC S1208; LOG {LOG}; DECISION {DEC}]", "S1208", "source S1208 gone")
    assert line == f"- Jobs are kept 14 days. [UNK: source S1208 gone; LOG {LOG}; DECISION {DEC}]"


def test_drop_citation_planted_failures_still_behave(tmp_path_factory):
    """A tag of DOC ids only, a note on the rewritten part, a part with no id and a source the tag lacks."""
    line, done = drop(tmp_path_factory.mktemp("doc"), "[DOC S1208, S1209]", "S1208")
    assert done == "True" and line == "- Jobs are kept 14 days. [DOC S1209]"

    line, done = drop(tmp_path_factory.mktemp("only"), "[DOC S1208]", "S1208", "source S1208 gone")
    assert done == "True" and line == "- Jobs are kept 14 days. [UNK: source S1208 gone]"

    line, done = drop(tmp_path_factory.mktemp("note"), "[DOC S1208, S1209: see the table; UNK: not confirmed]", "S1208")
    assert line == "- Jobs are kept 14 days. [DOC S1209: see the table; UNK: not confirmed]"

    line, done = drop(tmp_path_factory.mktemp("absent"), f"[DOC S1209; LOG {LOG}]", "S1208")
    assert done == "False" and line == f"- Jobs are kept 14 days. [DOC S1209; LOG {LOG}]"


@pytest.mark.parametrize("tag,sid", [
    (f"[LOG {LOG}; DOC S1208, S1209]", "S1209"),
    (f"[DOC S1208, S1209; LOG {LOG}: a; DECISION {DEC}: b]", "S1208"),
])
def test_drop_citation_is_idempotent_on_the_ids(tmp_path_factory, tag, sid):
    """A second drop of the same source changes nothing: the ids survive the first rewrite intact."""
    first, _ = drop(tmp_path_factory.mktemp("a"), tag, sid)
    second, done = drop(tmp_path_factory.mktemp("b"), first.split("14 days. ", 1)[1], sid)
    assert done == "False" and second == first
