#!/usr/bin/env python3
"""Roots: the read tools serve every root at once (kb/public and a second root, here a team's own facts added with
KB_ROOTS from a temporary directory, never committed).

The second root's article is found by pack with its qualified path and its own source's url, and left out by
--root public; its ledger entries, signals and eval set are read and qualified in that root; kb_status and kb_show
know it; the server's always-on texts do not change; a root that reuses a taken id prefix is refused; and its index
shares CLAUDE_PLUGIN_DATA with this repository's without either pruning the other's file.
"""
import csv, glob, json, os, subprocess, sys

import kbid
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
