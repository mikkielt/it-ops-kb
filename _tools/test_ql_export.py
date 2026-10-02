"""Query log tests, export (kb/_self/querylog.md, Reporting; `python3 _tools/tests.py -k ql_export`).

  ops_export_otlp_names   one planted store row and one planted ops row come out under the OTLP-JSON field names
                          (timeUnixNano as a decimal string, severityNumber, severityText, eventName, an empty body,
                          attributes as key and value pairs, resource attributes) and flat event names with no dot
  ops_export_unified      the store's entries, findings, usage, work and ops rows come out as records of one shape in
                          a fixed order, the question only with --with-question, --since and --event narrowing
                          them; the store's files are not changed; the facade runs the same
  ops_export_redacts_at_read   a planted failure for each gate: an unknown key is dropped, a leak-scan hit, a free-text
                          value and a value outside its shape leave the row out (counted by file and line, never by a
                          value), and a store with an unreadable line, a file that is no JSON and a row of no known
                          shape does not crash the export; refusals exit 2
"""
import hashlib, json, subprocess, sys
from pathlib import Path

import ql_export, ql_store
from ql_testkit import QL, RUN_ID, golden_store

ENTRY = "22222222-0000-4000-8000-0000000000a1"
QUESTION = "presidio pesel recognizer"
OPUS = {"requests": 2, "in": 5, "cw": 1200, "cw1h": 1200, "cr": 11000, "out": 170}
OPS_ROWS = [
    {"id": "11111111-1111-4111-8111-111111111111", "ts": "2026-09-28T11:00:00.000Z", "event": "land.step",
     "item": "ST-aaaaaaaa", "step": "rebase", "exit": 0, "ms": 1200},
    {"id": "33333333-3333-4333-8333-333333333333", "ts": "2026-09-29T11:00:09.000Z", "event": "done.refused",
     "item": "ST-aaaaaaaa", "reasons": ["check-failed", "uncommitted"], "ms": 30},
    {"id": "44444444-4444-4444-8444-444444444444", "ts": "2026-09-29T12:00:00.000Z", "event": "land.end",
     "item": "ST-aaaaaaaa", "exit": 1, "ms": 5},
]
FINDING = {"id": "F-0123456789ab", "kind": "gap", "state": "open", "stage": "miss", "entry": ENTRY}


def planted_store(tmp_path):
    """The golden run file with a findings file, a usage, a work and an ops sidecar, all of the run RUN_ID."""
    store = golden_store(tmp_path / "store")
    ql_store.write_findings(store, ql_store.store_entries(store), [FINDING], ql_store.LEARN_STATES, "0" * 40)
    ql_store.write_usage(store, RUN_ID, [{"id": ENTRY, "main": {"claude-opus-5-5": OPUS}, "start": 7}], 0, 1)
    ql_store.write_work(store, RUN_ID, [{"item": "TK-aaaaaaaa", "prompts": 3, "main": {"claude-opus-5-5": OPUS}},
                                        {"items": ["TK-aaaaaaaa"], "prompts": 2, "main": {"claude-opus-5-5": OPUS}}],
                        0, 1)
    ql_store.write_ops(store, RUN_ID, [ql_store.ops_line(r) for r in OPS_ROWS])
    return store


def attrs(rec):
    """The attributes of an OTLP-JSON record as {key: the value's one field}, an int back as an int."""
    got = {}
    for kv in rec["attributes"]:
        (kind, v), = kv["value"].items()
        got[kv["key"]] = int(v) if kind == "intValue" else v
    return got


def rid(rec):
    return attrs(rec)["kb.id"]


def run(store, **kw):
    """(exit code, records, stderr lines) of ql_export.export over `store`."""
    out, err = [], []
    code = ql_export.export(store, out=out.append, err=err.append, **kw)
    return code, [json.loads(x) for x in out], err


def digest(store):
    return {p.relative_to(store).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(store).rglob("*")) if p.is_file()}


def rewrite(path, change):
    """The JSON lines of `path` with `change(list of objects)` applied."""
    objs = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    change(objs)
    path.write_text("".join(json.dumps(o) + "\n" for o in objs), encoding="utf-8", newline="\n")


class TestExport:
    def test_ops_export_otlp_names(self, tmp_path):
        store = planted_store(tmp_path)
        code, recs, err = run(store)
        assert (code, err) == (0, []), err
        keys = ["timeUnixNano", "severityNumber", "severityText", "eventName", "body", "attributes", "resource"]
        for r in recs:
            assert list(r) == keys and r["body"] == {}, r
            assert r["timeUnixNano"].isdigit() and len(r["timeUnixNano"]) == 19
            assert not {"timestamp", "severity_text", "event_name", "record_id"} & set(r)
            assert "." not in r["eventName"] and r["eventName"] in ql_export.EVENTS
            assert all(list(kv) == ["key", "value"] and len(kv["value"]) == 1 for kv in r["attributes"])
            res = r["resource"]["attributes"]
            assert [kv["key"] for kv in res] == ["service.name", "kb.run"] and list(r["resource"]) == ["attributes"]
            assert res[0]["value"] == {"stringValue": "it-ops-kb"} and list(res[1]["value"]) == ["stringValue"]
        ops = next(r for r in recs if rid(r) == OPS_ROWS[0]["id"])  # the planted ops row
        assert ops["eventName"] == "ops_land_step" and ops["timeUnixNano"] == "1790593200000000000"
        assert (ops["severityNumber"], ops["severityText"]) == (9, "INFO")
        assert ops["attributes"] == [
            {"key": "kb.record", "value": {"stringValue": "ops"}},
            {"key": "kb.type", "value": {"stringValue": "land.step"}},
            {"key": "kb.id", "value": {"stringValue": OPS_ROWS[0]["id"]}},
            {"key": "item", "value": {"stringValue": "ST-aaaaaaaa"}},
            {"key": "step", "value": {"stringValue": "rebase"}},
            {"key": "exit", "value": {"intValue": "0"}},
            {"key": "ms", "value": {"intValue": "1200"}}]
        row = next(r for r in recs if rid(r) == ENTRY)  # the planted store row
        a = attrs(row)
        assert row["eventName"] == "entry_prompt" and (a["kb.record"], a["kb.type"]) == ("entry", "prompt")
        assert a["day"] and "question" not in a and "id" not in a
        assert row["timeUnixNano"] == str(ql_export.calendar.timegm(
            ql_export.datetime.date.fromisoformat(a["day"]).timetuple()) * 10**9)
        refused = next(r for r in recs if rid(r) == OPS_ROWS[1]["id"])
        assert refused["eventName"] == "ops_done_refused" and (refused["severityNumber"], refused["severityText"]) == (13, "WARN")
        assert {"key": "reasons", "value": {"arrayValue": {"values": [
            {"stringValue": "check-failed"}, {"stringValue": "uncommitted"}]}}} in refused["attributes"]
        assert ql_export.any_value(True) == {"boolValue": True} and ql_export.any_value(None) == {}
        assert ql_export.any_value(7) == {"intValue": "7"} and ql_export.any_value({"a": 1}) == {
            "kvlistValue": {"values": [{"key": "a", "value": {"intValue": "1"}}]}}
        assert len(set(ql_export.EVENTS)) == len(ql_export.EVENTS)  # one flat namespace, no name twice

    def test_ops_export_unified(self, tmp_path):
        store = planted_store(tmp_path)
        before = digest(store)
        code, recs, err = run(store)
        assert (code, err) == (0, []), err
        assert digest(store) == before  # the store's own files are not changed
        names = [r["eventName"] for r in recs]
        for kind in ("entry_prompt", "entry_tool_fetch", "finding_gap", "usage", "work_item", "work_shared",
                     "ops_land_step", "ops_done_refused", "ops_land_end"):
            assert kind in names, names
        for r in recs:
            assert attrs(r)["kb.record"] in ("entry", "finding", "usage", "work", "ops")
            assert r["severityText"] in ("INFO", "WARN") and r["resource"]["attributes"][1]["key"] == "kb.run"
        order = [(r["timeUnixNano"], r["eventName"], rid(r)) for r in recs]
        assert order == sorted(order)
        sev = {r["eventName"]: r["severityText"] for r in recs if r["eventName"].startswith("ops_")}
        assert sev == {"ops_land_step": "INFO", "ops_done_refused": "WARN", "ops_land_end": "WARN"}
        assert "question" not in json.dumps(recs) and QUESTION not in json.dumps(recs)
        assert code == run(store)[0] and recs == run(store)[1]  # the same input, the same records
        _, asked, _ = run(store, with_question=True)
        assert any(attrs(r).get("question") == QUESTION for r in asked)
        _, day, _ = run(store, since="2026-09-29")
        assert day and all(int(r["timeUnixNano"]) >= 1790640000 * 10**9 for r in day) and len(day) < len(recs)
        _, one, _ = run(store, event="ops_land_end")
        assert [rid(r) for r in one] == [OPS_ROWS[2]["id"]]
        ops = next(r for r in recs if r["eventName"] == "ops_land_step")
        assert {k: v for k, v in attrs(ops).items() if not k.startswith("kb.")} == {
            "item": "ST-aaaaaaaa", "step": "rebase", "exit": 0, "ms": 1200}
        assert rid(ops) == OPS_ROWS[0]["id"]

    def test_ops_export_unified_through_the_facade(self, tmp_path):
        store = planted_store(tmp_path)
        p = subprocess.run([sys.executable, QL, "export", "--format", "jsonl", "--event", "ops_land_end", "--store",
                            str(store)], capture_output=True, text=True, encoding="utf-8", timeout=120)
        assert p.returncode == 0 and p.stderr == "", p.stderr
        lines = p.stdout.splitlines()
        assert len(lines) == 1 and rid(json.loads(lines[0])) == OPS_ROWS[2]["id"]

    def test_ops_export_redacts_at_read(self, tmp_path):
        store = planted_store(tmp_path)
        ops = ql_store.ops_files(store)[0]
        run_file = ql_store.run_files(store)[0]

        def plant(objs):
            objs[1]["secret"] = "x"  # an unknown key: dropped, the row stays
            objs[2]["reasons"] = ["please look at the dev server"]  # free text in a closed list: refused
            objs[3]["item"] = "jan.kowalski" + "@" + "corp.contoso.org"  # a leak and not an item id: refused
        rewrite(ops, plant)
        rewrite(run_file, lambda o: (o[1].update(hostname="pl-lt-00999"), o[2].update(summary="a free text")))
        code, recs, err = run(store)
        assert code == 0
        by = {rid(r): r for r in recs}
        assert "secret" not in json.dumps(recs)
        assert OPS_ROWS[0]["id"] in by and "secret" not in attrs(by[OPS_ROWS[0]["id"]])
        assert OPS_ROWS[1]["id"] not in by and OPS_ROWS[2]["id"] not in by
        assert ENTRY in by and "hostname" not in attrs(by[ENTRY])  # an unknown key of an entry is dropped
        assert any("left out" in e for e in err) and not any("kowalski" in e or "dev server" in e for e in err), err

    def test_ops_export_redacts_at_read_a_leak_scan_hit(self, tmp_path):
        store = planted_store(tmp_path)
        rewrite(ql_store.findings_files(store)[0], lambda o: o[1].update(terms=["10.20.30.40"]))
        rewrite(ql_store.run_files(store)[0], lambda o: o[1].update(question="the host 10.20.30.40"))
        _, recs, err = run(store, with_question=True)
        ids = {(r["eventName"], rid(r)) for r in recs}
        assert ("entry_prompt", ENTRY) not in ids and ("finding_gap", f"{FINDING['id']}/{RUN_ID}") not in ids  # refused
        assert not any("10.20.30.40" in json.dumps(r) for r in recs) and not any("10.20.30" in e for e in err)
        _, plain, _ = run(store)  # without the question there is nothing to flag
        assert ("entry_prompt", ENTRY) in {(r["eventName"], rid(r)) for r in plain}

    def test_ops_export_redacts_at_read_a_bad_store_does_not_crash(self, tmp_path):
        store = planted_store(tmp_path)
        ops = ql_store.ops_files(store)[0]
        ops.write_text(ops.read_text(encoding="utf-8") + "not json\n[1, 2]\n"
                       + json.dumps({"id": "1", "ts": 5, "event": ["x"]}) + "\n", encoding="utf-8", newline="\n")
        usage = ql_store.usage_files(store)[0]
        usage.write_text(usage.read_text(encoding="utf-8") + json.dumps({"id": ENTRY, "main": 3, "steps": "x"}) + "\n",
                         encoding="utf-8", newline="\n")
        ql_store.work_files(store)[0].write_bytes(b"\xff\xfe\x00 not text")
        code, recs, err = run(store)
        assert code == 0 and OPS_ROWS[0]["id"] in {rid(r) for r in recs}
        assert any("ops/" in e and "unreadable" in e for e in err) and any("shape" in e for e in err), err
        assert not any(r["eventName"].startswith("work_") for r in recs)

    def test_ops_export_redacts_at_read_refusals(self, tmp_path):
        store = planted_store(tmp_path)
        for kw, word in (({"fmt": "otlp"}, "--format"), ({"since": "yesterday"}, "--since"),
                         ({"event": "ops_nothing"}, "--event")):
            out, err = [], []
            assert ql_export.export(store, out=out.append, err=err.append, **kw) == 2 and out == []
            assert word in err[0], err
        err = []
        assert ql_export.export(tmp_path / "missing", out=print, err=err.append) == 2 and "not a directory" in err[0]
