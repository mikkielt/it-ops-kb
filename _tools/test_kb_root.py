#!/usr/bin/env python3
"""Roots: the read tools serve every root at once (kb/public and a second root, here a team's own facts added with
KB_ROOTS from a temporary directory, never committed).

The second root's article is found by pack with its qualified path and its own source's url, and left out by
--root public; its ledger entries, signals and eval set are read and qualified in that root; kb_status and kb_show
know it; the server's always-on texts do not change; a root that reuses a taken id prefix is refused; and its index
shares CLAUDE_PLUGIN_DATA with this repository's without either pruning the other's file; and a server limited to
that root alone (kb_mcp.py --roots) still answers its question `good`.
"""
import csv, glob, json, os, subprocess, sys

import kbcommon, kbid
from conftest import KB, TOOLS

URL = "https://docs.example.com/print/queue-retention"
SID = kbid.source_id(URL, "FXT")  # the fixture root's prefix: a name and prefix a fork's own roots do not take
ROOT_MD = """---
root: fixture
id_prefix: FXT
visibility: internal
description: the team's print and office notes
---
"""
ARTICLE = f"""---
topic: print/queues
priority: P1
applies_to: "PL-SRV-0042 print servers"
retrieved_utc: 2026-09-26
sources: [{SID}]
status: partial
---

# Print queue retention on the team's print servers

## Summary
How long the team's print servers keep finished jobs.

## Facts
- Finished print jobs are kept for 14 days on the spooler of PL-SRV-0042, then purged by a nightly task. [DOC {SID}]
- Queue names follow the pattern `PQ-<floor>-<room>`. [DOC {SID}]

## Reference

## Examples
"""
QUESTION = "How long are finished print jobs kept on the spooler?"


def make_root(path, prefix="FXT"):
    """A root in a temporary directory: its ROOT_FILE, one article, its ledgers and its retrieval data."""
    os.makedirs(os.path.join(path, "print"))
    os.makedirs(os.path.join(path, "_retrieval"))
    files = {
        "_root.md": ROOT_MD.replace("id_prefix: FXT", f"id_prefix: {prefix}"),
        "print/queues.md": ARTICLE,
        "_answers.md": "# Answers\n",
        "_gaps.md": "# Gaps\n\n- Which task purges the queues is not documented. (topic: print/queues)\n",
        "_conflicts.md": "# Conflicts\n",
        "_retrieval/signals.csv": "signal,topic\nspooler,print/queues\n",
        "_retrieval/lookup_eval.csv": ("id,question,expect_paths,expect_verdict,allow_weak\n"
                                       f"EV-print-retention,{QUESTION},print/queues.md,good,\n"),
    }
    for rel, text in files.items():
        with open(os.path.join(path, rel), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    with open(os.path.join(path, "_sources.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["id", "url", "title", "publisher", "licence", "reuse", "retrieved_utc", "version_or_date",
                    "artifact_sha256", "used_in", "superseded_by"])
        w.writerow([SID, URL, "Print queue retention", "corp.example.com", "internal", "quote", "2026-09-26", "", "",
                    "print/queues.md", ""])


def run(tool, *args, roots=None, data=None):
    env = {k: v for k, v in os.environ.items() if k not in ("KB_ROOTS", "KB_INDEX", "CLAUDE_PLUGIN_DATA")}
    if roots:
        env["KB_ROOTS"] = roots
    if data:
        env["CLAUDE_PLUGIN_DATA"] = data
    else:
        env["KB_INDEX"] = "0"
    p = subprocess.run([sys.executable, os.path.join(TOOLS, tool), *args], capture_output=True, text=True, encoding="utf-8", cwd=KB,
                       env=env, timeout=180)
    return p.returncode, p.stdout + p.stderr


def test_second_root_is_packed_filtered_and_shown(tmp_path):
    root = str(tmp_path / "team-kb")
    make_root(root)
    code, out = run("rag.py", "pack", QUESTION, roots=root)
    assert out.startswith("coverage: good") and "fixture/print/queues.md:" in out and URL in out, out[:600]
    assert f"-> {SID}  {URL}" in out, "the source footer resolves the second root's id"
    code, out = run("rag.py", "pack", QUESTION, "--root", "public", roots=root)
    assert "fixture/print/queues.md" not in out, "--root public leaves the fixture root out: " + out[:300]
    code, out = run("rag.py", "pack", "What is the default Windows LAPS password length?", "--root", "fixture", roots=root)
    assert out.startswith("coverage: none"), "--root fixture holds only its own facts: " + out[:300]
    line = next(n for n, ln in enumerate(ARTICLE.splitlines(), start=1) if "14 days" in ln)
    code, out = run("rag.py", "show", f"fixture/print/queues.md:{line}", "-n", "1", roots=root)
    assert code == 0 and "14 days" in out, out
    code, out = run("rag.py", "src", SID, "--cited", roots=root)
    assert URL in out and "cited at fixture/print/queues.md:" in out, out


def test_second_root_ledgers_signals_and_eval(tmp_path):
    root = str(tmp_path / "team-kb")
    make_root(root)
    code, out = run("rag.py", "audit", "--root", "fixture", "--entries", roots=root)
    assert "| fixture/print/queues.md | partial |" in out and "fixture/print/queues  gaps: fixture/_gaps.md:3" in out, out
    code, out = run("rag.py", "topics-for", "--keywords", "the spooler service", roots=root)
    assert "- fixture/print/queues  spooler" in out, "a root's signals name its own topics: " + out
    code, out = run("rag.py", "facts", "print", roots=root)
    assert "fixture/print/queues.md" in out and "facts=2" in out, "a bare prefix covers the domain in every root: " + out
    code, out = run("rag.py", "--json", "eval", "--file", os.path.join(root, "_retrieval", "lookup_eval.csv"), roots=root)
    res = json.loads(out[out.index("{"):])
    assert res["passed"] == 1 and res["rows"][0]["found"] == ["fixture/print/queues.md"], res["rows"]
    code, out = run("rag.py", "search", "purges queues task", "--index", "--root", "fixture", roots=root)
    assert "fixture/_gaps.md:3" in out, "--index searches the root's own ledgers: " + out


def test_status_and_server_texts(tmp_path):
    root = str(tmp_path / "team-kb")
    make_root(root)
    code, out = run("kb_mcp.py", "--status", roots=root)
    assert "roots: public (prefix S, public," in out and "; fixture (prefix FXT, internal," in out, out
    code = ("import json, kb_mcp; print(json.dumps([kb_mcp.INSTRUCTIONS, kb_mcp.server_info()['title'], "
            "[t['description'] for t in kb_mcp.TOOL_LIST]]))")
    texts = []
    for extra in ({}, {"KB_ROOTS": root}):
        env = {**{k: v for k, v in os.environ.items() if k != "KB_ROOTS"}, **extra}
        p = subprocess.run([sys.executable, "-c", code], cwd=TOOLS, capture_output=True, text=True, encoding="utf-8", env=env, timeout=60)
        texts.append(json.loads(p.stdout))
    assert texts[0] == texts[1], "one server serves every root: its always-on texts do not depend on the roots"
    assert texts[0][1] == "it-ops-kb"


def test_a_root_with_a_taken_prefix_is_refused(tmp_path):
    root = str(tmp_path / "clash")
    make_root(root, prefix="S")
    code, out = run("rag.py", "pack", QUESTION, roots=root)
    assert code != 0 and "share the id_prefix 'S'" in out and "Traceback" not in out, out[-400:]


def test_index_files_of_two_root_sets_share_a_directory(tmp_path):
    root, data = str(tmp_path / "team-kb"), str(tmp_path / "plugin-data")
    make_root(root)
    os.makedirs(data)
    q = "print job retention"
    run("rag.py", "pack", q, roots=root, data=data)
    run("rag.py", "pack", q, data=data)
    names = sorted(os.path.basename(p) for p in glob.glob(os.path.join(data, "kbindex-*.sqlite")))
    assert len(names) == 2 and sum(n.startswith("kbindex-r") for n in names) == 1, names
    with open(os.path.join(root, "print", "queues.md"), "a", encoding="utf-8", newline="\n") as f:
        f.write("\n")  # a new fingerprint: that root set rebuilds and prunes only its own old file
    run("rag.py", "pack", q, roots=root, data=data)
    after = sorted(os.path.basename(p) for p in glob.glob(os.path.join(data, "kbindex-*.sqlite")))
    assert len(after) == 2 and [n for n in names if not n.startswith("kbindex-r")][0] in after, (names, after)


def test_embed_roots_small_root_is_good(tmp_path):
    """kb_mcp.py --roots fixture serves a root of one article: its own question is `good`, since the informative-word
    cut of a small index does not empty the question's key words (kbfacts.pack); another product's stays `none`."""
    from test_kb_mcp import _embedded
    root = str(tmp_path / "team-kb")
    make_root(root)
    p, out = _embedded(root, "--roots", "fixture", calls=[
        ("kb_pack", {"question": QUESTION}),
        ("kb_pack", {"question": "What is the default Windows LAPS password length?"})])
    assert p.returncode == 0, p.stderr
    assert out[1][1].startswith("coverage: good") and "fixture/print/queues.md:" in out[1][1], out[1][1][:600]
    assert out[2][1].startswith("coverage: none"), out[2][1][:300]


# --- decisions_store: a root's _decisions.csv and decision-makers.csv (kbcommon.DECISION_COLS, MAKER_COLS) ---
ALPHA = "abcdefghijklmnopqrstuvwxyz234567"
DEC, MAK = "_decisions.csv", "decision-makers.csv"


def did(i):
    return "D-aaaaaa" + ALPHA[i // 32] + ALPHA[i % 32]


def decision(i, **over):
    """A valid decision row of the fixture root, with the fields in `over` replaced."""
    row = {"id": did(i), "text": "Keep finished print jobs for 14 days.", "by": "operator", "by_ref": "", "source": SID,
           "date": "2026-10-01", "context": f"source:{SID}; article:print/queues; domain:print; item:TK-abcd2345; "
           "fact:0123456789ab", "status": "active", "invalidated_reason": "", "invalidated_date": "", "supersedes": "",
           "review_by": "2027-01-01", "links": ""}
    row.update(over)
    return row


def checked_root(tmp_path, decisions=None, makers=None, visibility="internal", header=None):
    """check.py over a fixture root holding these decision rows and maker rows (dicts; None: no such file):
    (exit code, {"<file>:<line>": [errors]} of the errors naming a decision file, the whole output)."""
    root = tmp_path / "team-kb"
    make_root(str(root))
    meta = root / "_root.md"
    meta.write_text(meta.read_text(encoding="utf-8").replace("visibility: internal", f"visibility: {visibility}"),
                    encoding="utf-8", newline="\n")
    (root / "_artifacts.csv").write_text("path,source_id,sha256\n", encoding="utf-8", newline="\n")  # check.py wants the ledger
    if decisions is not None:
        kbcommon.write_csv(str(root / DEC), header or kbcommon.DECISION_COLS, decisions)
    if makers is not None:
        kbcommon.write_csv(str(root / MAK), kbcommon.MAKER_COLS, makers)
    code, out = run("check.py", "--root", "fixture", roots=str(root))
    found = {}
    for ln in out.splitlines():
        name, _, msg = ln[len("ERROR fixture/"):].partition(" ")
        if ln.startswith("ERROR fixture/") and name.startswith((DEC, MAK)):
            found.setdefault(name, []).append(msg)
    assert "Traceback" not in out, out[-800:]
    return code, found, out


def assert_planted(found, file, cases, first_line):
    """Each planted case is the row at its line and has exactly one error, which names its rule."""
    for n, (rule, _) in enumerate(cases, start=first_line):
        msgs = found.get(f"{file}:{n}", [])
        assert len(msgs) == 1 and rule in msgs[0], (n, rule, msgs)
    assert len(found) == len(cases), sorted(found)  # no other row has an error


def test_decisions_store_valid_files_pass(tmp_path):
    """Every shape the format allows is clean: every kind of context, a superseded decision named by its successor, an
    invalidated one whose article is gone, a proposed one with no maker yet, and a maker kept with its name."""
    rows = [decision(0, by_ref="owner"),
            decision(1, status="superseded"),
            decision(2, supersedes=did(1) + "; " + did(0), links="https://corp.example.com/notes"),
            decision(3, status="invalidated", invalidated_reason="the article was removed",
                     invalidated_date="2026-10-02", context="article:print/gone; domain:gone"),
            decision(4, status="proposed", by="", review_by="")]
    makers = [{"id": "owner", "role": "print owner", "name": "Jan Kowalski", "source": SID}]
    code, found, out = checked_root(tmp_path, rows, makers)
    assert code == 0 and not found and "errors=0" in out, out[-1500:]


def test_decisions_store_a_root_without_the_files_passes(tmp_path):
    code, found, out = checked_root(tmp_path)
    assert code == 0 and "errors=0" in out, out[-800:]


def test_decisions_store_plants_one_failure_per_decision_rule(tmp_path):
    cases = [  # (the error's rule, the replaced fields of a valid row or a function of its index)
        ("is not D-<8 base32>", {"id": "D-AAAA"}),
        ("no text", {"text": ""}),
        ("is not one of proposed|active|invalidated|superseded", {"status": "accepted"}),
        ("date '2026-13-40' is not YYYY-MM-DD", {"date": "2026-13-40"}),
        ("date '' is not YYYY-MM-DD", {"date": ""}),
        ("no source", {"source": ""}),
        ("cites unknown source FXT-zzzzzzzz", {"source": "FXT-zzzzzzzz"}),
        ("names no decision maker (by or by_ref)", {"by": ""}),
        ("by_ref 'nobody' names no decision maker", {"by_ref": "nobody"}),
        ("no context", {"context": ""}),
        ("context part 'print/queues' is not <kind>:<value>", {"context": "print/queues"}),
        ("context part 'table:print' is not <kind>:<value>", {"context": "table:print"}),
        ("context fact:xyz is not a valid fact reference", {"context": "fact:xyz"}),
        ("context item:tk-1 is not a valid item reference", {"context": "item:tk-1"}),
        ("context article:print/nope names no article print/nope", {"context": "article:print/nope"}),
        ("context article:../x/y is not a valid article reference", {"context": "article:../x/y"}),
        ("context domain:nope names no domain nope", {"context": "domain:nope"}),
        ("context source:FXT-zzzzzzzz cites unknown source FXT-zzzzzzzz", {"context": "source:FXT-zzzzzzzz"}),
        ("invalidated without an invalidated_reason", {"status": "invalidated", "invalidated_date": "2026-10-02"}),
        ("invalidated_date '' is not YYYY-MM-DD", {"status": "invalidated", "invalidated_reason": "gone"}),
        ("on a decision that is active, not invalidated", {"invalidated_reason": "gone"}),
        ("supersedes 'D-zzzzzzzz': not another decision", {"supersedes": "D-zzzzzzzz"}),
        ("not another decision", lambda i: {"supersedes": did(i)}),
        ("no decision names it in supersedes", {"status": "superseded"}),
        ("review_by 'soon' is not YYYY-MM-DD", {"review_by": "soon"}),
    ]
    rows = [decision(0)] + [decision(i, **(over(i) if callable(over) else over)) for i, (_, over) in enumerate(cases, start=1)]
    code, found, out = checked_root(tmp_path, rows, [])
    assert code == 1
    assert_planted(found, DEC, cases, 3)


def test_decisions_store_refuses_a_duplicate_decision_id(tmp_path):
    code, found, out = checked_root(tmp_path, [decision(0), decision(0)])
    assert code == 1 and found == {f"{DEC}:2": [f"duplicate decision id {did(0)}"],
                                   f"{DEC}:3": [f"duplicate decision id {did(0)}"]}, found


def test_decisions_store_refuses_a_header_that_is_not_the_format(tmp_path):
    code, found, out = checked_root(tmp_path, [{"id": "D-aaaaaaaa", "text": "x"}], header=["id", "text"])
    assert code == 1 and "_decisions.csv: header is 'id,text', not 'id,text,by," in out, out[-800:]


def test_decisions_store_plants_one_failure_per_maker_rule(tmp_path):
    cases = [("id 'Owner 2' is not a lowercase slug", {"id": "Owner 2"}),
             ("duplicate decision maker id owner", {"id": "owner"}),
             ("no role", {"id": "lead", "role": ""})]
    makers = [{"id": "owner", "role": "print owner", "name": "", "source": ""}]
    makers += [{"id": "x", "role": "x", "name": "", "source": "", **over} for _, over in cases]
    code, found, out = checked_root(tmp_path, [], makers)
    assert code == 1
    assert_planted(found, MAK, cases, 3)


def test_decisions_store_a_maker_source_must_be_a_known_source(tmp_path):
    code, found, out = checked_root(tmp_path, [], [{"id": "owner", "role": "x", "name": "", "source": "FXT-zzzzzzzz"}])
    assert code == 1 and "ERROR fixture/decision-makers.csv:2 cites unknown source FXT-zzzzzzzz" in out, out[-800:]


def test_decisions_store_a_root_that_is_not_internal_keeps_no_names(tmp_path):
    makers = [{"id": "owner", "role": "print owner", "name": "", "source": ""},
              {"id": "named", "role": "lead", "name": "Jan Kowalski", "source": ""}]
    cases = [("by 'Jan Kowalski' is not the role 'print owner' of owner", {"by": "Jan Kowalski", "by_ref": "owner"}),
             ("by_ref is empty: a root that is public, not internal, keeps no names", {"by": "print owner"}),
             ("by_ref is empty: a root that is public, not internal, keeps no names", {"by": "jan.kowalski"})]
    rows = [decision(0, by="print owner", by_ref="owner")] + [decision(i, **over) for i, (_, over) in enumerate(cases, start=1)]
    code, found, out = checked_root(tmp_path, rows, makers, visibility="public")
    assert code == 1
    assert found.pop(f"{MAK}:3") == ["a name in a root that is public, not internal: keep the role only"], found
    assert_planted(found, DEC, cases, 3)
    # the same names in an internal root are clean
    rows = [decision(0, by="print owner", by_ref="owner"), decision(1, by="Jan Kowalski", by_ref="named")]
    code, found, out = checked_root(tmp_path / "again", rows, makers)
    assert code == 0 and not found, out[-800:]


def test_decisions_store_d_is_a_reserved_id_prefix(tmp_path):
    root = str(tmp_path / "clash")
    make_root(root, prefix="D")
    code, out = run("check.py", roots=root)
    assert code == 1 and "id_prefix" in out and "not one of" in out and "Traceback" not in out, out[-400:]
