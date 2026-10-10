"""The census's reading queue and its phase rows (kb/_self/tools.md, census.py and factdiff.py): `census.py summary`
sizes what phase 2 must read with no network and no model, and each census phase appends one ops row `census.phase`
that the digest's ops block counts."""
import csv
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import census
import factdiff
import kbcommon
import kbfacts
import ql_capture
import ql_report
import ql_store

TOOLS = Path(__file__).resolve().parent


def log_row(sid, **kw):
    return {**{c: "" for c in census.COLS}, "id": sid, "url": f"https://docs.example.com/{sid}", "bucket": "CHANGED", **kw}


def cached(cache, sid, text):
    path = cache / "public" / f"{sid}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"id": sid, "url": "https://docs.example.com/", "text": text}), encoding="utf-8")


def test_census_queue_sizes_what_phase_2_reads_without_network(tmp_path, monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("the queue touched the network")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(factdiff, "ROOT", kbcommon.root("public"))
    monkeypatch.setattr(factdiff, "CACHE", str(tmp_path / "cache"))
    monkeypatch.setattr(kbfacts, "clone_home", lambda: str(tmp_path / "no-clone"))
    facts = factdiff.cited_facts()
    ids = sorted(facts)[:6]
    key, rel, line, text = facts[ids[5]][0]
    claim = factdiff.fact_text(text)
    cached(tmp_path / "cache", ids[3], "x" * 400)
    cached(tmp_path / "cache", ids[5], claim + " A second sentence the fact does not rest on.")
    rows = [log_row(ids[0], bucket="OK"),  # nothing to read
            log_row(ids[1], bucket="NEEDS-READING", note="blocked"),  # no model reads a denied host
            log_row(ids[2], outcome="confirmed"),  # already read
            log_row(ids[3]),  # a whole document, cached
            log_row(ids[4], bucket="GONE"),  # a whole document, not cached
            log_row(ids[5])]  # a review item
    review = [{**{c: "" for c in factdiff.LOG_COLS}, "source_id": ids[5], "url": rows[5]["url"], "verdict": "changed",
               "fact": key, "path": rel, "line": str(line), "outcome": "modified"}]
    queue = {q["id"]: q for q in census.reading_queue(rows, review)}
    assert sorted(queue) == sorted(ids[3:])
    assert (queue[ids[3]]["mode"], queue[ids[3]]["chars"], queue[ids[3]]["cached"]) == ("document", 400, True)
    assert (queue[ids[4]]["mode"], queue[ids[4]]["chars"], queue[ids[4]]["cached"]) == ("document", 0, False)
    assert (queue[ids[5]]["mode"], queue[ids[5]]["items"]) == ("review", 1) and queue[ids[5]]["chars"] >= len(claim)
    assert all(q["facts"] >= 1 for q in queue.values())
    lines = census.queue_lines(list(queue.values()))
    assert lines[0].startswith("queue (phase 2 reads; no network, no model): rows=3 ")
    assert f"chars={400 + queue[ids[5]]['chars']} tokens={(400 + queue[ids[5]]['chars']) // 4}" in lines[0]
    assert "whole documents: rows=2 not cached=1 chars=400" in lines[2]
    assert lines[3].startswith("  docs.example.com: rows=3 ") and "not cached=1" in lines[3]


def test_census_queue_phases_each_write_one_ops_row_the_digest_counts(tmp_path):
    data = tmp_path / "data"
    (data / "querylog").mkdir(parents=True)
    (data / "querylog" / "config.json").write_text('{"mode": "local"}', encoding="utf-8")
    env = {**os.environ, "CLAUDE_PLUGIN_DATA": str(data), "CLAUDE_PLUGIN_ROOT": str(TOOLS.parent)}
    log = tmp_path / "2026-10-10.csv"
    with open(log, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, census.COLS, lineterminator="\n")
        w.writeheader()
        w.writerow(log_row("S9990001"))
    flog = tmp_path / "factdiff-2026-10-10.csv"
    flog.write_text(",".join(factdiff.LOG_COLS) + "\n", encoding="utf-8")

    def run(tool, *args):
        return subprocess.run([sys.executable, str(TOOLS / tool), *args], capture_output=True, text=True, encoding="utf-8",
                              env=env).returncode

    assert run("census.py", "record", str(log), "--id", "S9990001", "--outcome", "updated") == 0
    assert run("census.py", "record", str(log), "--id", "S9990002", "--outcome", "gone") == 1
    assert run("factdiff.py", "review", str(flog)) == 0
    spool = [json.loads(ln) for p in sorted((data / "querylog" / "spool").glob("*.jsonl"))
             for ln in p.read_text(encoding="utf-8").splitlines()]
    assert [(r["event"], r["phase"], r["date"], r["exit"]) for r in spool] == [
        ("census.phase", "record", "2026-10-10", 0), ("census.phase", "record", "2026-10-10", 1),
        ("census.phase", "review", "2026-10-10", 0)]
    assert spool[0]["rows"] == [{"name": "updated", "n": 1}] and spool[1]["rows"] == [{"name": "skipped", "n": 1}]
    assert "rows" not in spool[2] and all(isinstance(r["ms"], int) for r in spool)
    assert not any(ql_capture.ops_problems({k: v for k, v in r.items() if k not in ("id", "ts", "surface", "v")}) for r in spool)
    bad = {**{k: v for k, v in spool[0].items() if k not in ("id", "ts", "surface", "v")}, "rows": [{"name": "Needs Reading", "n": 1}]}
    assert ql_capture.ops_problems(bad)  # a row whose name is no closed token is refused, not written
    store = tmp_path / "store"
    path = ql_store.write_ops(store, "20261010T000000Z-aaaaaaaa", [ql_store.ops_line(r) for r in spool])
    out = ql_report.ops_lines([path], lambda day: True)
    assert out[0] == "ops: 3 rows (census.phase 3)" and out[1].startswith("  census.phase: 3, failed 1, median ")
