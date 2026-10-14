"""Redaction and the query log's privacy guards: redact.py's rules, what distill stores of a captured prompt, the closed
shape of an ops row, the store check that blocks a leak, and apply's rule for a weak rules miss over the fixture store.
Planted values are assembled at run time."""
import argparse, csv, hashlib, json, os, re, shutil, socket, subprocess, sys, types, urllib.error
from collections import Counter
from pathlib import Path

import pytest

import census, factdiff, kb_mcp, kbcommon, kbfacts, kbid, provider, ql_apply, ql_capture, ql_distill, ql_learn, ql_report, ql_store, redact
from conftest import KB, TOOLS, git_env

FIXTURE_STORE = Path(TOOLS) / "fixtures" / "querylog" / "store"
RUN_REL = "2026-09/20260928T130000Z-0000beef.jsonl"
PACK = ("coverage: good (best article matches 3 of 3 key words)\n\n## public/windows/laps.md  Windows LAPS\n"
        "- public/windows/laps.md:24 The default length is 14. [DOC S-jmzxsdjr]\n")
SID = "3f2a4c1e-0000-4000-8000-00000000abcd"
QL = os.path.join(TOOLS, "querylog.py")

TOKEN = "gh" + "p_" + "a1B2c3D4e5" * 4
EMAIL = "anna.nowak" + "@" + "acme-corp.pl"
IP = "10." + "1.20.33"
HOME = "/Users/" + "anna.nowak" + "/notes/plan.txt"
GUID = "-".join(("3f2a4c1e", "9b7d", "4e21", "8c55", "1a2b3c4d5e6f"))  # assembled: the leak scan reads this file
HOST = "fs01." + "acme-corp.pl"
COMPUTER = "DESKTOP-" + "AB12CD3"
PLANTED = {"token": TOKEN, "email": EMAIL, "ip": IP, "home": "anna.nowak", "guid": GUID, "host": HOST,
           "computer": COMPUTER}
TEXT = f"key {TOKEN}, mail {EMAIL}, ip {IP}, file {HOME}, tenant {GUID}, share {HOST}, laptop {COMPUTER}"
ORDINARY = ("Set the Windows LAPS password length to 14 in Intune. See https://learn.microsoft.com/windows/laps and "
            "t@example.com, 192.0.2.10, 00000000-0000-0000-0000-000000000000, PL-LT-00123, corp.example.com.")


@pytest.fixture(autouse=True)
def small_known(monkeypatch):
    """What the public root contains, reduced to the fixture store's own text and the ordinary sample: reading the whole
    root (redact.known) costs seconds, and no test here depends on it."""
    texts = [ORDINARY] + [f.read_text(encoding="utf-8") for f in FIXTURE_STORE.rglob("*.jsonl")]
    k = redact.scan_known(texts)
    monkeypatch.setattr(redact, "known", lambda root=None: k)
    return k


def test_redact_replaces_every_class_of_value_leaves_ordinary_text_and_a_second_pass_changes_nothing_and_scan_exits_1_on_a_leak(tmp_path, capsys):
    assert redact.redact(ORDINARY) == ORDINARY
    out = redact.redact(TEXT)
    for kind, value in PLANTED.items():
        assert value not in out, kind
    for placeholder in ("<secret>", "jan.kowalski@corp.example.com", redact.PLACEHOLDERS["ipv4"],
                        redact.PLACEHOLDERS["guid"], redact.PLACEHOLDERS["host"], redact.PLACEHOLDERS["computer"]):
        assert placeholder in out, placeholder
    assert redact.redact(out) == out
    assert redact.scan(out) == []
    f = tmp_path / "in.txt"
    f.write_text(TEXT, encoding="utf-8", newline="\n")
    assert redact.main(["--scan", str(f)]) == 1
    assert "email\t" + EMAIL in capsys.readouterr().out
    f.write_text(ORDINARY, encoding="utf-8", newline="\n")
    assert redact.main(["--scan", str(f)]) == 0


def test_distill_stores_a_captured_prompt_and_answer_redacted_and_the_capture_row_of_a_kb_pack_keeps_its_pack_handle(tmp_path, monkeypatch):
    qdir = tmp_path / "querylog"
    qdir.mkdir()
    (qdir / "config.json").write_text(json.dumps({"mode": "local"}), encoding="utf-8", newline="\n")
    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": KB, "CLAUDE_PLUGIN_DATA": str(tmp_path)}
    answer = f"The laptop {COMPUTER} at {IP} keeps it; ask {EMAIL}; key {TOKEN}; tenant {GUID}."
    events = [
        {"hook_event_name": "UserPromptSubmit", "session_id": SID, "prompt_id": "p1",
         "prompt": f"kb: what is the Windows LAPS password length on {COMPUTER} at {IP} for {EMAIL} ({GUID}, {TOKEN})?"},
        {"hook_event_name": "PostToolUse", "session_id": SID, "prompt_id": "p1", "tool_name": "mcp__kb__kb_pack",
         "tool_use_id": "toolu_01", "tool_input": {"questions": [f"Windows LAPS password length on {COMPUTER} for {EMAIL}"]},
         "tool_response": [{"type": "text", "text": PACK + "pack: P-0a1b2c3d\n"}]},
        {"hook_event_name": "Stop", "session_id": SID, "prompt_id": "p1", "stop_hook_active": False,
         "last_assistant_message": answer},
    ]
    for ev in events:
        p = subprocess.run([sys.executable, QL, "capture"], input=json.dumps(ev).encode("utf-8"), env=env,
                           capture_output=True, timeout=60)
        assert p.returncode == 0
    spool = qdir / "spool"
    assert (spool / f"{SID}.jsonl").exists()
    assert EMAIL in (spool / f"{SID}.jsonl").read_text(encoding="utf-8")  # capture keeps the spool raw: distill redacts
    rows = [json.loads(ln) for ln in (spool / f"{SID}.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["pack"] for r in rows if r["surface"] == "mcp"] == ["P-0a1b2c3d"]
    assert ql_capture.pack_handle(PACK) is None and ql_capture.pack_handle(PACK + "pack: P-0a1b2c3d") == "P-0a1b2c3d"
    (spool / f"{SID}.end").touch()

    def judge(prompt):  # the Haiku stub: judges every entry answered; its input is the rule-redacted text only
        for value in (COMPUTER, IP, EMAIL, TOKEN, GUID):
            assert value not in prompt, value
        items = json.loads(prompt[prompt.index("\n\n[") + 2:])
        return json.dumps([{"i": i["i"], "judged": "answered", "best": None, "identifying": False} for i in items])

    rc = ql_distill.distill(qdir=qdir, cfg=qdir / "config.json", haiku=judge, kb_commit="0" * 40, out=lambda s: None)
    assert rc == 0
    runs = sorted((qdir / "store").rglob("*.jsonl"))
    assert runs
    stored = "".join(r.read_text(encoding="utf-8") for r in runs)
    for kind, value in PLANTED.items():
        assert value not in stored, kind
    assert "jan.kowalski@corp.example.com" in stored and "Windows LAPS password length" in stored
    assert ql_store.store_problems(qdir / "store") == []


def test_an_ops_row_has_a_closed_shape_and_a_free_text_value_is_refused_and_kb_feedback_spools_one_closed_row_once_refuses_each_open_field_and_prints_its_call_on_a_weak_or_none_pack_only(tmp_path, monkeypatch):
    ok = {"event": "land.step", "item": "ST-px3y26ti", "step": "gate", "exit": 0, "ms": 1200}
    assert ql_capture.ops_problems(ok) == []
    free = f"failed for {EMAIL} on {COMPUTER}"
    assert ql_capture.ops_problems({**ok, "step": free})
    assert ql_capture.ops_problems({**ok, "note": free})
    assert ql_capture.ops_problems({**ok, "item": TOKEN})
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", KB)
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))
    (tmp_path / "querylog").mkdir()
    (tmp_path / "querylog" / "config.json").write_text(json.dumps({"mode": "local"}), encoding="utf-8", newline="\n")
    ql_capture.spool_dir.cache_clear()
    try:
        assert ql_capture.record("ops", **{**ok, "step": free}) is None
        assert ql_capture.record("ops", **{**ok, "note": free}) is None
        assert not (tmp_path / "querylog" / "spool").exists()
        assert ql_capture.record("ops", **ok)["step"] == "gate"  # planted counterpart: the closed shape is written
        text = "".join(f.read_text(encoding="utf-8") for f in (tmp_path / "querylog" / "spool").glob("*.jsonl"))
        assert EMAIL not in text and COMPUTER not in text
        feedback_is_spooled_once_and_refuses_open_fields(tmp_path, monkeypatch)
    finally:
        ql_capture.spool_dir.cache_clear()


def feedback_is_spooled_once_and_refuses_open_fields(tmp_path, monkeypatch):
    """kb_feedback over the tools/call protocol path: one `feedback` row in the tools file for a report made twice, no
    row for a refused field, the annotations and the instructions, and its footer line on a weak or none pack only."""
    def call(**args):
        res = kb_mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                             "params": {"name": "kb_feedback", "arguments": args}})
        if "error" in res:
            return res["error"]["message"], True
        return res["result"]["content"][0]["text"], res["result"]["isError"]

    def spooled():
        return [json.loads(ln) for f in (tmp_path / "querylog" / "spool").glob("tools-*.jsonl")
                for ln in f.read_text(encoding="utf-8").splitlines() if '"surface":"feedback"' in ln]

    art = sorted(kbfacts.articles())[0]
    report = {"pack": "P-0a1b2c3d", "outcome": "misled", "lines": [{"line": f"{art}:1", "issue": "wrong"}], "best": art,
              "source_url": "https://learn.microsoft.com/windows/laps", "claim": "The default length is 14.",
              "tool_issue": "too-long"}
    text, is_error = call(**report)
    assert not is_error and re.fullmatch(r"recorded FB-[0-9a-f]{8}", text), text
    assert call(**report) == (text, False)  # the same report again: the same id, nothing new
    rows = spooled()
    assert len(rows) == 1 and rows[0]["fb"] == text.split()[1] and rows[0]["lines"] == report["lines"], rows
    assert set(rows[0]) == {"id", "ts", "surface", "v", "fb", *report}  # the closed fields, nothing else
    assert call(**{**report, "outcome": "partly"})[0] != text and len(spooled()) == 2
    refused = [{**report, "lines": [{"line": f"{art}:99999", "issue": "wrong"}]},  # a line no kb file has
               {**report, "lines": [{"line": "public/no/such-article.md:1", "issue": "stale"}]},
               {**report, "best": "public/_sources.csv"},  # a file that is no article
               {**report, "source_url": "http://pl-srv-0042.corp/page"},  # outside the research candidate url gate
               {**report, "claim": f"Ask {EMAIL} for it."},  # the leak scan flags it
               {**report, "claim": "word " * 41},
               {"outcome": "missed", "claim": "The default length is 14."},  # neither pack nor question
               {**report, "outcome": "fine"}, {**report, "tool_issue": "slow"}]
    for bad in refused:
        assert call(**bad)[1] is True, bad
    assert len(spooled()) == 2
    listed = kb_mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
    tool = next(t for t in listed if t["name"] == "kb_feedback")
    assert tool["annotations"] == {"title": tool["title"], "readOnlyHint": False, "destructiveHint": False,
                                   "idempotentHint": True, "openWorldHint": False}
    assert all(t["annotations"]["readOnlyHint"] for t in listed if t["name"] != "kb_feedback")
    assert "kb_feedback" in kb_mcp.instructions()
    with monkeypatch.context() as limited:  # --roots, and kb_http.py always: no such tool
        limited.setattr(kb_mcp, "limited", lambda: True)
        assert "kb_feedback" not in {t["name"] for t in kb_mcp.handle(
            {"jsonrpc": "2.0", "id": 3, "method": "tools/list"})["result"]["tools"]}
        assert call(**report)[1] is True and "kb_feedback" not in kb_mcp.instructions() and len(spooled()) == 2
    # the footer: a ready call on a weak or none pack, above the handle that stays last; a good pack prints none
    monkeypatch.setattr(kbfacts, "pack_store", lambda: str(tmp_path / "packs"))
    monkeypatch.setenv("KB_NO_UPSTREAM", "1")
    with open(os.path.join(kbcommon.PUBLIC, kbcommon.DATA_DIR, "lookup_eval.csv"), encoding="utf-8", newline="") as f:
        good = next(r for r in csv.DictReader(f) if r["expect_verdict"] == "good" and not r["allow_weak"])["question"]
    none = kbfacts.pack_many(["zqxv wlkj nmbp qrtz"], revalidate=False)
    assert none["verdict"] == "none"
    assert none["text"].splitlines()[-2:] == [f'feedback: kb_feedback(pack="{none["pack"]}", outcome="missed")',
                                              f"pack: {none['pack']}"]
    ok = kbfacts.pack_many([good], revalidate=False)
    assert ok["verdict"] == "good" and "feedback:" not in ok["text"] and ok["text"].splitlines()[-1] == f"pack: {ok['pack']}"


def feedback_rows_join_their_lookups_and_the_store_refuses_open_fields(tmp, monkeypatch):
    """distill over a spool of two lookups and six feedback rows: a pack handle joins a tools row (across prompt
    windows), a session's own row joins its prompt, a tools row in a window joins that window's lookup, and the two
    rows that join none are entries of their own; Haiku maps the person's comment, whose text, and the agent's claim,
    reach no store file; the spool is empty once delivered; and the store gates refuse each open feedback field."""
    import datetime
    qdir = tmp / "querylog"
    spool = qdir / "spool"
    spool.mkdir(parents=True)
    (qdir / "config.json").write_text(json.dumps({"mode": "local"}), encoding="utf-8", newline="\n")
    art = "public/windows/laps.md"
    line = f"{art}:24"
    comment, claim = "the length shown is stale and the pack was too long", "The default length is 14."
    n = iter(range(1, 100))

    def row(surface, ts, **f):
        return {"id": f"{next(n):08x}-0000-4000-8000-000000000000", "ts": f"2026-10-01T{ts}Z", "surface": surface,
                "v": 1, **f}

    def lookup(pid, t0, handle):
        return [row("prompt", f"{t0}:00.000", session_id=SID, prompt_id=pid, prompt="kb: LAPS length?", kb_intent="lookup"),
                row("mcp", f"{t0}:05.000", session_id=SID, prompt_id=pid, tool="kb_pack", verdict="good", pack=handle,
                    args={"question": "Windows LAPS password length"}, articles=[art],
                    lines=[{"line": line, "tag": "DOC", "verdict": "good"}]),
                row("stop", f"{t0}:30.000", session_id=SID, prompt_id=pid, answer=f"It is 14 ({line}).")]
    report = {"outcome": "misled", "lines": [{"line": line, "issue": "wrong"}], "best": art,
              "source_url": "https://learn.microsoft.com/windows/laps", "claim": claim, "tool_issue": "too-long"}
    own = row("feedback", "10:40:00.000", fb="FB-0000000a", pack="P-ffffffff", outcome="missed",
              question="How do I rotate the LAPS password?", source_url="https://docs.example.net/laps/rotate")
    rows = lookup("p1", "10:00", "P-0a1b2c3d") + lookup("p2", "10:10", "P-1b2c3d4e") + [
        row("feedback", "10:12:00.000", session_id=SID, prompt_id="p2", judged_by="user", comment=comment),
        row("feedback", "10:05:00.000", fb="FB-00000001", pack="P-0a1b2c3d", **report)]
    tools = [rows.pop(), row("feedback", "10:10:20.000", fb="FB-00000002", outcome="answered", tool_issue="error"), own,
             row("feedback", "10:50:00.000", fb="FB-0000000b", judged_by="agent", comment=comment)]
    (spool / f"{SID}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8", newline="\n")
    (spool / f"{SID}.end").touch()
    (spool / "tools-2026-10-01.jsonl").write_text("".join(json.dumps(r) + "\n" for r in tools), encoding="utf-8",
                                                  newline="\n")
    monkeypatch.setattr("ql_learn.KbPages.named_ids", lambda self, text: ["S-jmzxsdjr"] if "learn.microsoft" in text else [])
    asked = []

    def haiku(prompt):
        items = json.loads(prompt[prompt.index("\n\n[") + 2:])
        if prompt.startswith(ql_distill.FEEDBACK_TASK):
            asked.append(items)
            return json.dumps([{"i": i["i"], "outcome": "partly", "lines": [{"line": line, "issue": "stale"}],
                                "tool_issue": "too-long", "text": comment} for i in items])
        return json.dumps([{"i": i["i"], "judged": "answered", "best": None, "identifying": False} for i in items])

    rc = ql_distill.distill(qdir=qdir, cfg=qdir / "config.json", haiku=haiku, kb_commit="0" * 40, out=lambda s: None,
                            now_dt=datetime.datetime(2026, 10, 5, tzinfo=datetime.timezone.utc))
    assert rc == 0 and len(asked) == 1 and [i["lines"] for i in asked[0]] == [[line], []]  # one batch, the comments only; a row with no lookup has none to classify
    store = qdir / "store"
    assert ql_store.store_problems(store) == []
    entries = [e for _, e in ql_store.store_entries(store)]
    by_surface = {s: [e for e in entries if e["surface"] == s] for s in ("prompt", "feedback")}
    first, second = sorted(by_surface["prompt"], key=lambda e: e["id"])
    assert first["feedback"] == [{"outcome": "misled", "judged_by": "agent", "lines": [{"line": line, "issue": "wrong"}],
                                  "best": art, "sources": ["S-jmzxsdjr"], "tool_issue": "too-long"}]  # by its handle
    assert second["feedback"] == [  # the tools row of its window, then its own session's row (mapped), by time
        {"outcome": "answered", "judged_by": "agent", "tool_issue": "error"},
        {"outcome": "partly", "judged_by": "user", "lines": [{"line": line, "issue": "stale"}], "tool_issue": "too-long"}]
    alone = sorted(by_surface["feedback"], key=lambda e: e.get("question", ""))
    assert [e["feedback"] for e in alone] == [
        [{"outcome": "partly", "judged_by": "agent", "tool_issue": "too-long"}],  # Haiku named a line it was not given
        [{"outcome": "missed", "judged_by": "agent", "lead": "https://docs.example.net/laps/rotate"}]]
    assert alone[1]["question"] == "How do I rotate the LAPS password?" and "question" not in alone[0]
    text = "".join(f.read_text(encoding="utf-8") for f in store.rglob("*.jsonl"))
    assert comment not in text and claim not in text and "comment" not in text and "claim" not in text
    assert not list(spool.glob("*.jsonl")) and not list(spool.glob("*.end"))  # delivered rows go, as other rows
    # the gates: one planted failure for each open field of a stored report
    good = second["feedback"][1]
    assert ql_store.feedback_problems([good, alone[1]["feedback"][0]], "e") == []
    for bad in ({**good, "comment": comment}, {**good, "claim": claim}, {**good, "lines": [{"line": line, "issue": "bogus"}]},
                {**good, "lines": [{"line": "see the docs", "issue": "wrong"}]}, {**good, "best": "../outside.md"},
                {**good, "lead": "http://pl-srv-0042.corp/page"}, {**good, "outcome": "fine"}, {**good, "judged_by": "bot"}):
        assert ql_store.feedback_problems([bad], "e"), bad
    planted = {**first, "feedback": [{**good, "comment": comment}]}
    assert any("free text" in p for p in ql_store.entry_problems(planted, "e", None))
    assert ql_store.entry_problems({k: v for k, v in alone[0].items() if k != "feedback"}, "e", None)  # none of its own


def test_store_check_passes_a_clean_store_and_names_the_run_file_with_a_leak_and_distill_joins_feedback_rows_to_their_lookups_and_the_feedback_store_gates_refuse_each_open_field(tmp_path, capsys, monkeypatch):
    feedback_rows_join_their_lookups_and_the_store_refuses_open_fields(tmp_path / "fb", monkeypatch)
    store = tmp_path / "store"
    shutil.copytree(FIXTURE_STORE, store)
    assert ql_store.check(str(store)) == 0  # `querylog.py check DIR` is this function
    assert capsys.readouterr().out == "querylog check: problems=0\n"
    run = store / RUN_REL
    lines = run.read_text(encoding="utf-8").splitlines()
    # learn's rules guard: a `pack --item` lookup (an entry with `item`) asks the item's text, not a question
    planted = next(e for e in map(json.loads, lines[1:]) if e.get("item"))
    assert planted["verdict"] == "weak" and not ql_learn.rules_miss(planted)
    asked = {k: v for k, v in planted.items() if k != "item"}
    assert ql_learn.rules_miss(asked)  # the same lookup without its item is a rules miss
    assert ql_learn.rules_miss({**asked, "question": "word " * ql_learn.RULES_QUESTION_WORDS})
    assert not ql_learn.rules_miss({**asked, "question": "word " * (ql_learn.RULES_QUESTION_WORDS + 1)})
    assert not any(planted["id"] == json.loads(ln).get("entry") for f in FIXTURE_STORE.glob("findings/*/*.jsonl")
                   for ln in f.read_text(encoding="utf-8").splitlines()[1:])  # and the committed findings hold none of it
    entry = json.loads(lines[1])
    entry["question"] = f"How long is the LAPS password for {EMAIL}?"
    lines[1] = json.dumps(entry)
    run.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    assert ql_store.check(str(store)) == 1
    out = capsys.readouterr().out
    assert RUN_REL in out and "question" in out and EMAIL not in out, out


class LeadGate(ql_apply.Gate):
    """apply's kb gates for a rules finding with the kb out of it: `pack --root _self` prints a canned passage list per
    question, the eval file is a temporary one, and the eval, pack-size and off-kb gates hold."""

    def __init__(self, tmp, packs, lines):
        self.eval, self.aliases, self.packs, self.lines = tmp / "lookup_eval.csv", tmp / "aliases.csv", packs, lines

    def fresh(self):
        pass

    def measure(self):
        return {"n": 1, "passed": 1, "noted": 0, "failed": [], "chars": {"EV-x": 100}, "offkb_good": 0}

    def rules_eval(self):
        return self.eval

    def rules_aliases(self):
        return self.aliases

    def rules_pack(self, question):
        return {"text": self.packs[question]}

    def rule_line(self, ref):
        return self.lines.get(ref)

    def token_counts(self):
        return {}

    def anchored(self, row):
        return any(row[5] in text for doc, text in self.lines.values() if doc == row[2])


def test_apply_anchors_a_weak_rules_miss_on_the_lead_passage_and_the_committed_outcome_converges(tmp_path):
    store = tmp_path / "store"
    shutil.copytree(FIXTURE_STORE, store)
    lead, short = (e for _, e in ql_store.store_entries(store) if ql_learn.rules_miss(e) and not e.get("key_missing"))
    ids = {ql_store.finding_id("rules", e["id"]): e for e in (lead, short)}
    held = {i for i, r in ql_store.finding_states(store).items() if r["kind"] != "rules"}
    for f in store.glob("findings/*/*.jsonl"):  # the committed outcome: no row, the kb's own pack prints no passage for their words
        recs = [json.loads(ln) for ln in f.read_text(encoding="utf-8").splitlines()[1:]]
        if any(r["id"] in ids and r["state"] == "no-fix" for r in recs):
            assert {r["id"]: r["observed"]["gate"] for r in recs if r["id"] in ids} == {i: ["no anchor phrase in the lead passage"] for i in ids}
            f.unlink()
    assert {r["state"] for i, r in ql_store.finding_states(store).items() if i in ids} == {"open"}
    first = "The zqxwidget plomkinator frobnicator quuxifies every plomkin on commit."
    other = "Another passage that would anchor as well."
    packs = {lead["question"]: f"coverage: weak\n\n## kb/_self/widgets.md\n- kb/_self/widgets.md:7 {first}\n- kb/_self/other.md:3 {other}\n",
             short["question"]: f"coverage: weak\n\n## kb/_self/short.md\n- kb/_self/short.md:9 Too short here.\n- kb/_self/other.md:3 {other}\n"}
    lines = {"kb/_self/widgets.md:7": ("widgets.md", first), "kb/_self/short.md:9": ("short.md", "Too short here."),
             "kb/_self/other.md:3": ("other.md", other)}
    gate, said = LeadGate(tmp_path, packs, lines), []
    assert ql_apply.apply(store=store, gate=gate, hold=held, out=said.append, kb_commit="0" * 40) == 0
    states = ql_store.finding_states(store)
    done = next(i for i, e in ids.items() if e is lead)
    assert states[done]["state"] == "applied" and states[done]["observed"] == {"eval": states[done]["observed"]["eval"], "line": "kb/_self/widgets.md:7", "lead": True}
    with open(gate.eval, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))[1:]
    assert len(rows) == 1  # the first passage only: the second would have anchored, the short lead gives no row
    eid, question, doc, verdict, weak, phrase, sets = rows[0]
    assert eid == states[done]["observed"]["eval"] and eid.startswith(ql_apply.RULES_ID) and question == lead["question"]
    assert (doc, verdict, weak, sets) == ("widgets.md", "good", "yes", "") and phrase in first and 4 <= len(phrase.split()) <= 6
    failed = next(i for i in ids if i != done)
    assert states[failed]["state"] == "no-fix" and states[failed]["observed"] == {"gate": ["the lead passage holds 0 of 3 key words of the question"]}
    # a finding with a missing key word, a none verdict, a route miss or an answer line is no lead finding: it waits for a person
    miss = {"id": "F-0", "observed": {"verdict": "weak", "key_missing": ["kbfacts"]}}
    assert ql_apply.rules_one(miss, lead, gate, None) == (None, True)
    assert not ql_apply.from_lead({"observed": {"verdict": "none"}}) and ql_apply.from_lead({"observed": {"verdict": "weak"}})
    assert not ql_apply.from_lead({"observed": {"verdict": "weak", "route": "miss"}})
    said.clear()
    assert ql_apply.apply(store=store, gate=gate, hold=held, out=said.append, kb_commit="0" * 40) == 0 and said == ["apply: nothing to apply"]


def test_apply_keeps_a_lead_that_does_not_answer_no_fix_cuts_the_anchor_and_apply_gap_guard_all_check_errors(tmp_path):
    line = "The zqxwidget plomkinator frobnicator quuxifies every plomkin on commit."
    shown = "The zqxwidget plomkinator frobnicator quuxifies every"
    asked, off = "which zqxwidget plomkinator frobnicator quuxifies every", "how are laptops enrolled into autopilot at provisioning"
    printed = f"coverage: weak\n\n## kb/_self/widgets.md\n- kb/_self/widgets.md:7 {shown}\n"
    gate = LeadGate(tmp_path, {asked: printed, off: printed}, {"kb/_self/widgets.md:7": ("widgets.md", line)})
    gate.token_counts = lambda: {w.lower(): 50 for w in shown.split()}  # the words past the clip are the rarest
    weak = {"id": "F-1", "kind": "rules", "observed": {"verdict": "weak"}}
    # planted failure: the lead passes the gates (anchor in its doc, phrase in the pack) and answers none of the question
    rec, human = ql_apply.rules_one(weak, {"question": off}, gate, {"chars": {"EV-x": 100}, "offkb_good": 0})
    assert not human and rec["state"] == "no-fix" and rec["observed"] == {"gate": ["the lead passage holds 0 of 4 key words of the question"]}
    assert not gate.eval.exists()
    # key words the whole line holds past the pack's clip do not make the printed passage answer
    gate.packs["which plomkin is quuxified on commit"] = printed
    rec, human = ql_apply.rules_one(weak, {"question": "which plomkin is quuxified on commit"}, gate, {"chars": {"EV-x": 100}, "offkb_good": 0})
    assert not human and rec["state"] == "no-fix" and rec["observed"] == {"gate": ["the lead passage holds 0 of 3 key words of the question"]}
    # the lead that answers is applied, its phrase cut from what the pack prints of the line, not from the whole line
    rec, human = ql_apply.rules_one(weak, {"question": asked}, gate, {"chars": {"EV-x": 100}, "offkb_good": 0})
    assert not human and rec["state"] == "applied"
    with open(gate.eval, encoding="utf-8", newline="") as f:
        phrase = list(csv.reader(f))[1][5]
    assert phrase in shown and phrase in line
    # a failed row names why it failed
    gate.eval.unlink()
    gate.measure = lambda: {"n": 2, "passed": 1, "noted": 0, "failed": ["SQ-x"], "why": {"SQ-x": ["text"]}, "chars": {"EV-x": 100}, "offkb_good": 0}
    rec, _ = ql_apply.rules_one(weak, {"question": asked}, gate, {"chars": {"EV-x": 100}, "offkb_good": 0})
    assert rec["state"] == "no-fix" and rec["observed"] == {"gate": ["eval fails: SQ-x (text)"]}
    # an expansion finding for a data file: doc2query keys the facts of .md articles only, so no expansion row is
    # written (it would leave `doc2query.py stale` red) and the eval row alone is tried
    class CsvGate(LeadGate):
        def pack(self, question):
            return {"verdict": "weak", "paths": []}

        def targets(self, article):
            return {"root": "public", "eval": tmp_path / "csv_eval.csv", "expansions": tmp_path / "expansions.csv"}

        def facts(self, article):
            return [(1, "haiku resolves to the newest Haiku model [DOC S1]")]

    csv_gate = CsvGate(tmp_path, {}, {})
    ev = {"id": "F-e", "kind": "eval", "state": "open", "stage": "miss", "expect": "public/claude/models.csv"}
    fix = {"id": "F-x", "kind": "expansion", "state": "open", "article": "public/claude/models.csv"}
    entry, base = {"question": "which model does the haiku alias resolve to"}, {"chars": {"EV-x": 100}, "offkb_good": 0}
    assert ql_apply.expansion_fixes(fix, entry, csv_gate) == []
    done, fixed = ql_apply.apply_one(ev, fix, entry, csv_gate, base)
    assert (done["state"], fixed["state"], fixed["observed"]) == ("applied", "applied", {"rows": 0})
    assert not (tmp_path / "expansions.csv").exists() and len(ql_apply.csv_rows(tmp_path / "csv_eval.csv")) == 1
    # planted: the eval row fails alone, so the pair is no-fix and rejected, the eval file put back
    (tmp_path / "csv_eval.csv").unlink()
    csv_gate.measure = lambda: {"n": 2, "passed": 1, "noted": 0, "failed": ["EV-y"], "chars": {"EV-x": 100}, "offkb_good": 0}
    gone, rejected = ql_apply.apply_one(ev, fix, entry, csv_gate, base)
    assert (gone["state"], rejected["state"]) == ("no-fix", "rejected") and not (tmp_path / "csv_eval.csv").exists()
    # planted: every question passes and a pack note now fires on one more answered question than rag.py eval allows
    import rag
    over = rag.NOTED_BASELINE + 1
    csv_gate.measure = lambda: {"n": 1, "passed": 1, "noted": over, "failed": [], "chars": {"EV-x": 100}, "offkb_good": 0}
    gone, rejected = ql_apply.apply_one(ev, fix, entry, csv_gate, base)
    assert (gone["state"], rejected["state"]) == ("no-fix", "rejected") and not (tmp_path / "csv_eval.csv").exists()
    assert rejected["observed"] == {"gate": [f"pack notes rise: noted={over} is above NOTED_BASELINE={over - 1}"]}
    # the gap step: no entry for pasted text (a backlog goal), none that check.py refuses (a citation, a topic mark or a
    # source or decision tag the question quotes)
    class GapGate(LeadGate):
        def pack(self, question):
            return {"verdict": "none", "paths": ["public/python/stdlib.md"], "matched": ["a", "b"], "known": ["a", "b"]}

        def article_of(self, path):
            return path

        def topic(self, article):
            return "python/stdlib"

        def root(self, article):
            return types.SimpleNamespace(path=str(tmp_path), name="public", visibility="public")

        def ledger(self, article, name):
            return tmp_path / name

    gap, ledger = GapGate(tmp_path, {}, {}), tmp_path / "_gaps.md"
    (tmp_path / "python").mkdir()
    (tmp_path / "python" / "stdlib.md").write_text("---\ntopic: python/stdlib\n---\n# stdlib\n", encoding="utf-8")
    cand = {"id": "F-9", "kind": "gap", "state": "open", "stage": "candidate-gap", "promotions": []}
    goal = "Close gap F-1 (kb/public/_gaps.md:1058) " + "and research the platform docs " * 6
    rec, = ql_apply.gap_one(cand, {"question": goal}, gap, "2026-10-12")
    assert rec["state"] == "rejected" and rec["observed"] == {"gate": ["pasted text, not a question"]} and not ledger.exists()
    asked = "what does os.link raise across volumes, see kb/public/_gaps.md:1058"
    rec, = ql_apply.gap_one(cand, {"question": asked}, gap, "2026-10-12")
    text = ledger.read_text(encoding="utf-8")
    assert rec["state"] == "applied" and "see kb/public/_gaps.md**" in text and ":1058" not in text
    assert gap.ledger_errors("public/python/stdlib.md") == []
    ledger.write_text("", encoding="utf-8")
    with pytest.MonkeyPatch.context() as m:  # planted: the entry quotes the citation whole, and the ledger is put back
        m.setattr(ql_apply, "plain_question", lambda t: t)
        rec, = ql_apply.gap_one(cand, {"question": asked}, gap, "2026-10-12")
    assert rec["state"] == "rejected" and rec["observed"]["gate"] == ["a ledger entry check.py refuses"]
    assert ledger.read_text(encoding="utf-8") == ""
    for carried in ("topic: no/such-topic", "[DOC S99999]", "[DECISION D-aaaaaaaa]"):  # planted: what else check.py refuses
        rec, = ql_apply.gap_one(cand, {"question": f"what does os.link raise {carried} across volumes"}, gap, "2026-10-12")
        assert rec["state"] == "rejected" and rec["observed"]["gate"] == ["a ledger entry check.py refuses"], carried
        assert ledger.read_text(encoding="utf-8") == ""


def census_row(sid, **kw):
    return {**{c: "" for c in census.COLS}, "id": sid, "url": f"https://docs.example.com/{sid}", "bucket": "CHANGED", **kw}


def cached_doc(cache, sid, text):
    path = cache / "public" / f"{sid}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"id": sid, "url": "https://docs.example.com/", "text": text}), encoding="utf-8")


def census_queue_is_sized_without_network(tmp_path, monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("the queue touched the network")

    with monkeypatch.context() as m:
        m.setattr(socket.socket, "connect", refuse)
        m.setattr(factdiff, "ROOT", kbcommon.root("public"))
        m.setattr(factdiff, "CACHE", str(tmp_path / "cache"))
        m.setattr(kbfacts, "clone_home", lambda: str(tmp_path / "no-clone"))
        facts = factdiff.cited_facts()
        ids = sorted(facts)[:6]
        key, rel, line, text = facts[ids[5]][0]
        claim = factdiff.fact_text(text)
        cached_doc(tmp_path / "cache", ids[3], "x" * 400)
        cached_doc(tmp_path / "cache", ids[5], claim + " A second sentence the fact does not rest on.")
        rows = [census_row(ids[0], bucket="OK"),  # nothing to read
                census_row(ids[1], bucket="NEEDS-READING", note="blocked"),  # no model reads a denied host
                census_row(ids[2], outcome="confirmed"),  # already read
                census_row(ids[3]),  # a whole document, cached
                census_row(ids[4], bucket="GONE"),  # a whole document, not cached
                census_row(ids[5])]  # a review item
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


def census_groups_split_the_queue_by_owner_and_brief_fills_each_group_in(tmp_path, monkeypatch, capsys):
    pin, tip = "a" * 40, "0123456789ab"
    cited = {"S9990001": [("public/auth/a.md", 3), ("public/auth/a.md", 5), ("public/mecm/b.md", 7)],  # most lines in auth
             "S9990002": [("public/mecm/b.md", 9), ("public/auth/a.md", 8)],  # a tie: the first domain by name
             "S9990003": [("public/_gaps.md", 4)],  # a ledger names it: the log's used_in decides
             "S9990004": [], "S9990005": [("public/dsc/d.md", 2)], "S9990006": [("public/dsc/d.md", 6)],
             "S9990007": [("public/dsc/d.md", 10)], "S9990008": [("public/dsc/d.md", 12)]}
    page = {"public/auth/a.md": ["", "", "- A fact. [DOC S9990001]", "", "- Another. [DOC S9990001]", "", "", "- Both. [DOC S9990002]"],
            "public/mecm/b.md": ["", "", "", "", "", "", "- Foreign fact. [DOC S9990001]", "", "- Cited once. [DOC S9990002]"],
            "public/dsc/d.md": ["", "sources: [S9990005, S9990006]", "", "", "", "- Pinned. [CODE S9990006]", "", "", "",
                                "- Learn. [DOC S9990007]", "", "- Docs. [DOC S9990008]"]}
    item = {"outcome": "modified", "source_id": "S9990005", "url": "https://docs.example.com/S9990005", "verdict": "changed",
            "note": "n", "fact": "- Fact text. [DOC S9990005]", "where": "public/dsc/d.md:2", "key": "k", "path": "dsc/d.md",
            "old": "the old passage", "old_from": "snapshot at HEAD", "new": "the new passage", "new_from": "https://docs.example.com/"}
    rows = [census_row("S9990001", used_in="auth/a.md;mecm/b.md"), census_row("S9990002", used_in="auth/a.md;mecm/b.md"),
            census_row("S9990003", used_in="windows/w.md", bucket="NEEDS-READING"),
            census_row("S9990004", bucket="GONE"),
            census_row("S9990005", evidence="fact diff: changed; review modified=1 (factdiff.py review factdiff-2099-01-02.csv)"),
            census_row("S9990006", kind="raw-pin", repo="github.com/Org/Repo", pin=pin, path="src/f.rs",
                       evidence=f"file differs at main@{tip}; latest change", proof=f"main@{tip}"),
            census_row("S9990007", url="https://learn.microsoft.com/en-us/entra/x"),
            census_row("S9990008", url="https://code.claude.com/docs/en/hooks"),
            census_row("S9990009", bucket="OK"), census_row("S9990010", outcome="confirmed"),
            census_row("S9990011", bucket="NEEDS-READING", note="blocked")]  # the last three are no phase-2 rows
    log = tmp_path / "2099-01-02.csv"
    kbcommon.write_csv(str(log), census.COLS, rows)
    with monkeypatch.context() as m:
        m.setattr(socket.socket, "connect", lambda *a, **k: (_ for _ in ()).throw(AssertionError("groups used the network")))
        m.setattr(factdiff, "ROOT", kbcommon.root("public"))
        m.setattr(factdiff, "CACHE", str(tmp_path / "cache"))
        m.setattr(kbfacts, "clone_home", lambda: str(tmp_path / "no-clone"))
        m.setattr(kbfacts, "cited_lines", lambda ids: {i: cited[i] for i in ids if i in cited})
        m.setattr(kbfacts, "read", lambda qpath: "\n".join(page.get(qpath, [])))
        m.setattr(census, "review_by_source", lambda ids, fd: {"S9990005": [item]})
        ctx = census.phase2_context(rows, str(log))
        groups = {g["group"]: g for g in census.group_records(ctx)}
        assert list(groups) == ["_uncited", "auth", "dsc", "windows"]  # sorted; a ledger's lines count for no domain
        assert [r["id"] for r in groups["auth"]["rows"]] == ["S9990001", "S9990002"]  # a tie goes to the first by name
        assert groups["auth"]["files"] == ["auth/a.md"]
        assert groups["auth"]["foreign"] == [{"file": "mecm/b.md", "domain": "mecm", "rows": ["S9990001", "S9990002"]}]
        assert groups["windows"]["files"] == ["windows/w.md"] and groups["_uncited"]["rows"][0]["id"] == "S9990004"
        assert groups["dsc"]["queue"]["rows"] == 4 and groups["dsc"]["queue"]["items"] == 1
        assert [r["mode"] for r in groups["dsc"]["rows"]] == ["review", "document", "document", "document"]
        assert census.group_records(census.phase2_context(rows, str(log))) == list(groups.values())  # same log and tree
        text = census.brief_parts("dsc", ctx["members"]["dsc"], ctx)[0]
        assert "census of 2099-01-02" in text and "Your files (edit only these): kb/public/dsc/d.md" in text
        assert "- kb/public/dsc/d.md:2 (front matter `sources:`" in text and "kb/public/dsc/d.md:6 - Pinned." in text
        assert "old (snapshot at HEAD): the old passage" in text and "new (https://docs.example.com/): the new passage" in text
        assert f"git -C _cache/census/repos/github.com__Org__Repo.git show {tip}:src/f.rs" in text
        assert f"git -C _cache/census/repos/github.com__Org__Repo.git diff {pin} {tip} -- src/f.rs" in text
        assert "microsoft_docs_fetch https://learn.microsoft.com/en-us/entra/x" in text
        assert "fetch https://code.claude.com/docs/en/hooks.md" in text and 'Return JSON only: {"outcomes"' in text
        assert f"valid against the JSON Schema `{census.SCHEMA_REL}`" in text and "census.py apply " in text
        assert "kb/public/mecm/b.md:7 (foreign) - Foreign fact." in census.brief_parts("auth", ctx["members"]["auth"], ctx)[0]
        # the rules that hold throughout phase 2 are in the brief, as the skill states them
        for rule in ("Read the full page before confirming or changing a fact", "Paraphrase Learn text; a quote is 25 words or fewer",
                     "Placeholders only", "Never call a docs server's `submit_feedback` tool"):
            assert rule in text
        # a group over the bound is split by whole rows into numbered parts, each within the bound
        m.setattr(census, "BRIEF_CHARS", len(text) - 200)
        parts = census.brief_parts("dsc", ctx["members"]["dsc"], ctx)
        assert len(parts) == 2 and all(len(p) <= len(text) - 200 for p in parts)
        assert "part 1 of 2" in parts[0] and "part 2 of 2" in parts[1]
        assert [i for p in parts for i in re.findall(r"### (S\d+)", p)] == ["S9990005", "S9990006", "S9990007", "S9990008"]
        # planted failures: an unknown group and a part out of range exit 2 and name what exists
        for group, part, said in (("nope", 1, "groups: "), ("dsc", 3, "has 2 part(s)")):
            code = census.cmd_brief(argparse.Namespace(log=str(log), group=group, part=part, factdiff=None), Counter())
            assert code == 2 and said in capsys.readouterr().out
        assert census.cmd_groups(argparse.Namespace(log=str(tmp_path / "none.csv"), factdiff=None), Counter()) == 2
        capsys.readouterr()
        assert census.cmd_groups(argparse.Namespace(log=str(log), factdiff=None), Counter()) == 0
        assert [g["group"] for g in json.loads(capsys.readouterr().out)["groups"]] == list(groups)


def census_dispatch_runs_a_group_as_a_capped_headless_session_and_writes_the_result_apply_takes(tmp_path, monkeypatch, capsys):
    """`census.py dispatch` with a stub `claude` on PATH: no test makes a paid run."""
    pin, tip = "a" * 40, "0123456789ab"
    cited = {"S9990005": [("public/dsc/d.md", 2)], "S9990006": [("public/dsc/d.md", 6)], "S9990007": [("public/dsc/d.md", 10)],
             "S9990008": [("public/dsc/d.md", 12), ("public/mecm/b.md", 3)]}
    page = {"public/dsc/d.md": ["", "sources: [S9990005, S9990006]", "", "", "", "- Pinned. [CODE S9990006]", "", "", "",
                                "- Learn. [DOC S9990007]", "", "- Docs. [DOC S9990008]"],
            "public/mecm/b.md": ["", "", "- Foreign fact. [DOC S9990008]"]}
    rows = [census_row("S9990005"), census_row("S9990006", kind="raw-pin", repo="github.com/Org/Repo", pin=pin, path="src/f.rs",
                                              evidence=f"file differs at main@{tip}; latest change", proof=f"main@{tip}"),
            census_row("S9990007", url="https://learn.microsoft.com/en-us/entra/x"),
            census_row("S9990008", url="https://code.claude.com/docs/en/hooks")]
    log = tmp_path / "2099-01-02.csv"
    log.parent.mkdir(parents=True, exist_ok=True)
    kbcommon.write_csv(str(log), census.COLS, rows)
    owned = os.path.join(census.KB, "dsc", "d.md")
    foreign_file = os.path.join(census.KB, "mecm", "b.md")
    clone = os.path.join(kbcommon.HOME, "_cache", "census", "repos", "github.com__Org__Repo.git")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    stub = bin_dir / "claude"
    stub.write_text(f"#!{sys.executable}\n" + "import json, os, sys\nhere = os.path.dirname(os.path.abspath(__file__))\n"
                    "rec = {'argv': sys.argv[1:], 'stdin': sys.stdin.read(), 'cwd': os.getcwd(), 'env': dict(os.environ)}\n"
                    "open(os.path.join(here, 'seen.json'), 'w', encoding='utf-8').write(json.dumps(rec))\n"
                    "sys.stdout.write(open(os.path.join(here, 'reply.json'), encoding='utf-8').read())\n"
                    "sys.exit(int(open(os.path.join(here, 'code'), encoding='utf-8').read()))\n", encoding="utf-8")
    stub.chmod(0o755)
    good = {"outcomes": [{"id": "S9990005", "outcome": "confirmed", "note": "n"}], "new_rows": [], "superseded": {}, "gaps": [],
            "conflicts": [], "foreign_edits": [], "edited_files": []}

    def reply(body, code=0):
        (bin_dir / "reply.json").write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")
        (bin_dir / "code").write_text(str(code), encoding="utf-8")
        (bin_dir / "seen.json").unlink(missing_ok=True)

    def ok(**kw):
        return {"type": "result", "subtype": "success", "is_error": False, "num_turns": 7, "total_cost_usd": 0.0123,
                "usage": {"input_tokens": 1000, "output_tokens": 200}, "modelUsage": {census.DISPATCH_MODEL: {}}, **kw}

    def args(**kw):
        return argparse.Namespace(**{"log": str(log), "group": "dsc", "part": 1, "factdiff": None, "model": census.DISPATCH_MODEL,
                                     "max_turns": census.DISPATCH_TURNS, "max_budget_usd": census.DISPATCH_BUDGET_USD,
                                     "dry_run": False, **kw})

    results = tmp_path / "dispatch" / "2099-01-02" / "dsc" / "RESULTS.json"
    with monkeypatch.context() as m:
        m.setattr(socket.socket, "connect", lambda *a, **k: (_ for _ in ()).throw(AssertionError("dispatch used the network")))
        m.setattr(factdiff, "ROOT", kbcommon.root("public"))
        m.setattr(factdiff, "CACHE", str(tmp_path / "cache"))
        m.setattr(kbfacts, "clone_home", lambda: str(tmp_path / "no-clone"))
        m.setattr(kbfacts, "cited_lines", lambda ids: {i: cited[i] for i in ids if i in cited})
        m.setattr(kbfacts, "read", lambda qpath: "\n".join(page.get(qpath, [])))
        m.setattr(census, "review_by_source", lambda ids, fd: {})
        m.setattr(census, "DISPATCH_DIR", str(tmp_path / "dispatch"))
        m.setattr(census, "worktrees_file", lambda files: None)  # this checkout may itself be one under .claude/worktrees
        m.setenv("PATH", str(bin_dir))
        m.setenv("CLAUDE_PLUGIN_ROOT", "/plugin")
        # the model is not the orchestrator's: the default is pinned, the caps are set, and a dry run starts nothing
        assert (census.DISPATCH_MODEL, census.DISPATCH_TURNS, census.DISPATCH_BUDGET_USD) == ("claude-sonnet-5-5", 150, 5.0)
        assert census.PHASES["dispatch"] is census.cmd_dispatch
        reply(ok(structured_output=good))
        assert census.cmd_dispatch(args(dry_run=True), Counter()) == 0
        text = capsys.readouterr().out
        assert "dispatch dry run (nothing started): group dsc part 1 of 1: model=claude-sonnet-5-5 max-turns=150" in text
        assert "max-budget-usd=5.00" in text and not (bin_dir / "seen.json").exists() and not results.exists()
        if sys.platform != "win32":  # the stub is a script with a shebang line
            # a valid result is written for apply, and the run's cost, tokens and turns reach the ops row's tally
            tally = Counter()
            assert census.cmd_dispatch(args(), tally) == 0
            text = capsys.readouterr().out
            assert json.loads(results.read_text(encoding="utf-8")) == good
            assert "total_cost_usd=0.0123" in text and "turns=7" in text and f"apply {log} --group dsc --from " in text
            assert dict(tally) == {"runs": 1, "ok": 1, "input-tokens": 1000, "output-tokens": 200, "turns": 7, "cost-usd-micro": 12300}
            seen = json.loads((bin_dir / "seen.json").read_text(encoding="utf-8"))
            argv = seen["argv"]
            flag = lambda name: argv[argv.index(name) + 1]  # noqa: E731
            assert flag("--model") == "claude-sonnet-5-5" and flag("--output-format") == "json"
            assert flag("--max-turns") == "150" and flag("--max-budget-usd") == "5.00" and flag("--permission-mode") == "dontAsk"
            assert json.loads(flag("--json-schema")) == json.loads(Path(census.RESULT_SCHEMA).read_text(encoding="utf-8"))
            assert "--no-session-persistence" in argv and "--strict-mcp-config" in argv and flag("--mcp-config").count("microsoft-learn") == 1
            assert flag("--tools") == "Read,Edit,Write,Grep,Bash"
            allow = argv[argv.index("--allowedTools") + 1:]  # the rules are the last flag: it takes every argument after it
            slash = lambda p: p.replace(os.sep, "/").lstrip("/")  # noqa: E731
            assert f"Read(//{slash(owned)})" in allow and f"Edit(//{slash(owned)})" in allow
            assert not any(slash(foreign_file) in r for r in allow), allow  # a foreign file is no file of the group's
            assert f"Write(//{slash(owned)})" not in allow
            assert f"Bash(git -C {clone} show *)" in allow and f"Bash(git -C {clone} diff *)" in allow
            assert "Bash(curl -sSL https://code.claude.com/docs/en/hooks.md)" in allow and census.LEARN_TOOL in allow
            assert not any(r.startswith("Bash(curl -sSL https://learn.") for r in allow)
            assert [r for r in allow if r.startswith("Bash(") and "git" not in r and "curl" not in r] == [
                f"Bash(python3 {os.path.join(kbcommon.TOOLS, 'kbid.py')} url *)"]
            # the brief is on stdin behind the run context; the child's cwd is a scratch directory of its own, gone
            # after the run, outside the repository and the stub's directory; the plugin variables are not passed on
            assert seen["stdin"].startswith("Run context (census.py dispatch") and "Group dsc, part 1 of 1" in seen["stdin"]
            assert f"git -C {clone} show" in seen["stdin"] and "Your files (edit only these): kb/public/dsc/d.md" in seen["stdin"]
            assert not os.path.exists(seen["cwd"]) and not seen["cwd"].startswith((kbcommon.HOME, str(bin_dir)))
            assert "CLAUDE_PLUGIN_ROOT" not in seen["env"] and seen["env"].get("PATH") == str(bin_dir)
            # planted failures: a cap, an error result, a result off the schema, no JSON, a failed process: each leaves the
            # group unapplied, says so, and removes the result of the earlier run
            bad = dict(good, outcomes=[{"id": "S9990005", "outcome": "bogus", "note": ""}])
            for body, code, said in ((ok(subtype="error_max_turns", is_error=True), 1, "hit the turn cap (--max-turns)"),
                                     (ok(subtype="error_max_budget_usd", is_error=True), 1, "hit the dollar cap"),
                                     (ok(subtype="error_during_execution", is_error=True, errors=["boom"]), 1, "boom"),
                                     (ok(structured_output=bad), 0, "breaks the schema"),
                                     ("not json", 0, "stdout is no JSON result"),
                                     ("", 3, "claude -p exited 3"), (ok(structured_output=good), 3, "not taken")):
                results.write_text("{}", encoding="utf-8")
                reply(body, code)
                tally = Counter()
                assert census.cmd_dispatch(args(), tally) == 1
                text = capsys.readouterr().out
                assert "group dsc part 1 of 1 UNAPPLIED: " in text and said in text and not results.exists(), (said, text)
                assert tally["failed"] == 1 and "ok" not in tally
            # the Learn tool and its server are given only when the docs plugin's config names them
            m.setattr(census, "DOCS_MCP", str(tmp_path / "no-mcp.json"))
            reply(ok(structured_output=good))
            assert census.cmd_dispatch(args(), Counter()) == 0
            seen = json.loads((bin_dir / "seen.json").read_text(encoding="utf-8"))
            assert "--mcp-config" not in seen["argv"] and census.LEARN_TOOL not in seen["argv"]
            assert "No command can read these sources here" in seen["stdin"] and "S9990007" in seen["stdin"].split("No command")[1]
        # guards: the group and part are checked first; claude is taken from PATH only, never from the working directory
        reply(ok(structured_output=good))
        assert census.cmd_dispatch(args(group="nope"), Counter()) == 2 and "groups: dsc" in capsys.readouterr().out
        assert census.cmd_dispatch(args(part=2), Counter()) == 2 and "has 1 part(s)" in capsys.readouterr().out
        assert census.cmd_dispatch(args(max_turns=0), Counter()) == 2
        capsys.readouterr()
        m.chdir(bin_dir)
        m.setenv("PATH", os.pathsep.join(["", ".", "bin", str(bin_dir)]))
        assert census.claude_exe() is None  # empty, `.`, a relative entry and the working directory itself
        assert census.cmd_dispatch(args(), Counter()) == 2 and "claude is not on PATH" in capsys.readouterr().out
        assert not (bin_dir / "seen.json").exists()
        m.chdir(tmp_path)
        assert census.claude_exe(str(bin_dir)) == str(bin_dir / "claude") or sys.platform == "win32"
    # the ops row of a run: the phase, the cost in millionths of a dollar, the tokens and the turns; a closed shape
    seen_rows = []
    with monkeypatch.context() as m:
        m.setattr(ql_capture, "record", lambda surface, **row: seen_rows.append(row))
        assert ql_capture.census_phase("dispatch", lambda t: t.update({"runs": 1, "ok": 1, "input-tokens": 1000, "turns": 7,
                                                                        "cost-usd-micro": 12300}) or 0, "2099-01-02") == 0
    assert seen_rows[0]["phase"] == "dispatch" and {"name": "cost-usd-micro", "n": 12300} in seen_rows[0]["rows"]
    assert not ql_capture.ops_problems({"event": "census.phase", **seen_rows[0]})


def census_dispatch_refuses_in_a_worktrees_checkout(tmp_path, monkeypatch, capsys):
    """A checkout whose path holds `.claude/worktrees` is where the claude CLI denies the Edit rules of the group's files:
    a run is refused before the session starts, a dry run prints the line and exits 0, and a checkout outside edits."""
    log = tmp_path / "2099-01-02.csv"
    log.parent.mkdir(parents=True, exist_ok=True)
    kbcommon.write_csv(str(log), census.COLS, [census_row("S9990005")])
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    stub = bin_dir / "claude"
    stub.write_text(f"#!{sys.executable}\nopen({str(bin_dir / 'seen')!r}, 'w').write('started')\n", encoding="utf-8")
    stub.chmod(0o755)

    def args(**kw):
        return argparse.Namespace(**{"log": str(log), "group": "dsc", "part": 1, "factdiff": None, "model": census.DISPATCH_MODEL,
                                     "max_turns": census.DISPATCH_TURNS, "max_budget_usd": census.DISPATCH_BUDGET_USD,
                                     "dry_run": False, **kw})

    with monkeypatch.context() as m:
        m.setattr(factdiff, "ROOT", kbcommon.root("public"))
        m.setattr(factdiff, "CACHE", str(tmp_path / "cache"))
        m.setattr(kbfacts, "clone_home", lambda: str(tmp_path / "no-clone"))
        m.setattr(kbfacts, "cited_lines", lambda ids: {"S9990005": [("public/dsc/d.md", 2)]})
        m.setattr(kbfacts, "read", lambda qpath: "\nsources: [S9990005]\n- Fact. [DOC S9990005]")
        m.setattr(census, "review_by_source", lambda ids, fd: {})
        m.setattr(census, "DISPATCH_DIR", str(tmp_path / "dispatch"))
        m.setenv("PATH", str(bin_dir))
        under = tmp_path / "repo" / ".claude" / "worktrees" / "w" / "kb" / "public"
        owned = os.path.join(str(under), "dsc", "d.md")
        m.setattr(census, "KB", str(under))
        assert census.worktrees_file([owned]) == owned
        assert census.worktrees_file([os.path.join(str(tmp_path), "worktrees", ".claude", "d.md")]) is None
        assert census.cmd_dispatch(args(), Counter()) == 2
        said = capsys.readouterr().out
        assert f"{owned} is under .claude/worktrees" in said and "outside .claude/worktrees" in said
        assert not (bin_dir / "seen").exists() and not (tmp_path / "dispatch").exists()
        assert census.cmd_dispatch(args(dry_run=True), Counter()) == 0
        dry = capsys.readouterr().out
        assert said.strip() in dry and "dispatch dry run (nothing started)" in dry
        # outside .claude/worktrees the group's Edit rules name its owned file, so the session itself makes the rewrites
        plain = tmp_path / "plain" / "kb" / "public"
        m.setattr(census, "KB", str(plain))
        assert census.cmd_dispatch(args(dry_run=True), Counter()) == 0
        dry = capsys.readouterr().out
        slash = os.path.join(str(plain), "dsc", "d.md").replace(os.sep, "/").lstrip("/")
        assert "refuses to run from here" not in dry and f"Edit(//{slash})" in dry


def census_judge_confirms_a_source_whose_facts_are_all_supported_and_leaves_the_rest_to_groups(tmp_path, monkeypatch, capsys):
    """`census.py judge` with a stub in place of the model call: no test makes a paid call."""
    def item(sid, mark, new="The service restarts on the second Tuesday of each month.", n=1):
        return {"outcome": "modified", "source_id": sid, "url": f"https://docs.example.com/{sid}", "verdict": "changed",
                "note": "n", "fact": f"- Fact {n} {mark}. [DOC {sid}]", "where": f"public/dsc/d.md:{n}", "key": f"k{sid[-1]}{n}",
                "path": "dsc/d.md", "old": "the old passage", "old_from": "snapshot at HEAD", "new": new, "new_from": "https://docs.example.com/"}

    by = {"S9990001": [item("S9990001", "HOLDS", n=1), item("S9990001", "HOLDS", n=2)],  # every fact supported: confirmed
          "S9990002": [item("S9990002", "HOLDS", n=1), item("S9990002", "CONFLICT", n=2)],  # one is left to a reader
          "S9990003": [item("S9990003", "HOLDS", new=None)],  # no new passage: never sent
          "S9990004": [item("S9990004", "VAGUE")]}  # supported with a sentence the page lacks: not believed
    rows = [census_row(sid, evidence="fact diff: changed; review modified=1 (factdiff.py review factdiff-2099-01-03.csv)")
            for sid in by] + [census_row("S9990005", kind="raw-pin", repo="github.com/Org/Repo")]  # a pinned file is never sent
    tmp_path.mkdir(parents=True, exist_ok=True)
    log = tmp_path / "2099-01-03.csv"
    kbcommon.write_csv(str(log), census.COLS, rows)
    sent = []

    def stub(prompt, model, cap):
        sent.append((prompt, model, cap))
        out = []
        for n, block in enumerate(prompt.split("### ")[1:], 1):
            fact, new = re.search(r"fact: (.*)", block).group(1), re.search(r"new: (.*)", block).group(1)
            out.append({"n": n, "verdict": "contradicted" if "CONFLICT" in fact else "supported",
                        "sentence": new if "VAGUE" not in fact else "A sentence the page never had."})
        return {"verdicts": out, "cost_usd": 0.0123, "usage": {"input-tokens": 100, "output-tokens": 20}, "error": ""}

    def args(**kw):
        return argparse.Namespace(log=str(log), factdiff=None, model=factdiff.JUDGE_MODEL, batch_size=2, max_budget_usd=None, jobs=1,
                                  dry_run=False, **kw)

    def refuse(*a, **k):
        raise AssertionError("a test made a model call")

    with monkeypatch.context() as m:
        m.setattr(socket.socket, "connect", refuse)
        m.setattr(subprocess, "run", refuse)  # the real call is a subprocess: only the stub answers
        m.setattr(factdiff, "judge_call", stub)
        m.setattr(factdiff, "ROOT", kbcommon.root("public"))
        m.setattr(kbfacts, "cited_lines", lambda ids: {i: [("public/dsc/d.md", 2)] for i in ids})
        m.setattr(kbfacts, "read", lambda qpath: "\n".join(["", "- A fact. [DOC S9990002]"]))
        m.setattr(census, "review_by_source", lambda ids, fd: {i: by[i] for i in ids if i in by})
        # the dry run asks nothing and says the batches, the tokens and the USD (the queue's passages, a call's own overhead)
        assert census.cmd_judge(argparse.Namespace(**{**vars(args()), "dry_run": True}), Counter()) == 0
        said = capsys.readouterr().out
        assert "batches=3 items=5 " in said and f"model={factdiff.JUDGE_MODEL}" in said and "usd~0." in said and not sent
        # no batch is a line, not an error, and a model with no rate in factdiff.JUDGE_PRICE has no USD estimate
        assert "batches=0 items=0 " in factdiff.estimate_lines(factdiff.judge_estimate([]), factdiff.JUDGE_MODEL, "none")[0]
        assert "no rate for other-model" in factdiff.estimate_lines(factdiff.judge_estimate([[by["S9990001"][0]]], "other-model"),
                                                                    "other-model", "one")[0]
        # the run: three calls of at most two items, the verdicts counted, the cost and tokens summed into the ops row
        tally = Counter()
        assert census.cmd_judge(args(), tally) == 0
        assert len(sent) == 3 and all(p.count("### ") <= 2 and mod == factdiff.JUDGE_MODEL and cap >= 0.05 for p, mod, cap in sent)
        assert all("old: the old passage" in p and "fact: - Fact " in p for p, _, _ in sent)
        assert (tally["supported"], tally["contradicted"], tally["not enough information"]) == (3, 1, 1)
        assert (tally["calls"], tally["failed"], tally["input-tokens"], tally["output-tokens"], tally["cost-usd-micro"]) == (3, 0, 300, 60, 36900)
        out = census.read_log(str(log))
        assert {r["id"]: r["outcome"] for r in out} == {"S9990001": "confirmed", "S9990002": "", "S9990003": "", "S9990004": "",
                                                        "S9990005": ""}
        assert f"2 fact(s) judged supported by {factdiff.JUDGE_MODEL}" in out[0]["outcome_note"]
        kept = {(r["source_id"], r["fact"]): (r["verdict"], r["note"]) for r in census.kbcommon.load_csv(census.judge_path(str(log)), census.JUDGE_COLS)[1]}
        assert kept[("S9990004", "k41")] == ("not enough information", "supported without a sentence of the new passage")
        assert kept[("S9990002", "k22")][0] == "contradicted" and ("S9990003", "k31") not in kept
        # groups and the brief read only what is left: the supported fact of a source is out, the confirmed source is gone
        ctx = census.phase2_context(out, str(log))
        assert [i["key"] for i in ctx["items"]["S9990002"]] == ["k22"] and "S9990001" not in ctx["items"]
        assert sorted(r["id"] for ms in ctx["members"].values() for r, _, _ in ms) == ["S9990002", "S9990003", "S9990004", "S9990005"]
        assert "1 more were judged supported by a model call and are left out" in census.brief_parts("dsc", ctx["members"]["dsc"], ctx)[0]
        capsys.readouterr()
        census.cmd_summary(argparse.Namespace(log=str(log), factdiff=None), Counter())
        assert "review passages: rows=3 items=3 without a passage=1 " in capsys.readouterr().out
        # a second run asks for nothing and writes the same bytes
        before = (log.read_bytes(), Path(census.judge_path(str(log))).read_bytes())
        sent.clear()
        assert census.cmd_judge(args(), Counter()) == 0 and not sent
        assert before == (log.read_bytes(), Path(census.judge_path(str(log))).read_bytes())
        # planted failure: a call that errors leaves its items unjudged, exits 1 and names why; nothing is confirmed
        Path(census.judge_path(str(log))).unlink()
        kbcommon.write_csv(str(log), census.COLS, rows)
        m.setattr(factdiff, "judge_call", lambda *a: {"verdicts": None, "cost_usd": 0.0, "usage": {}, "error": "Budget limit reached"})
        tally = Counter()
        assert census.cmd_judge(args(), tally) == 1 and "call 1 failed: Budget limit reached" in capsys.readouterr().out
        assert tally["failed"] == 3 and not any(r["outcome"] for r in census.read_log(str(log))) and not os.path.exists(census.judge_path(str(log)))
        # the ops row of the phase names only closed tokens
        seen = []
        m.setattr(ql_capture, "record", lambda surface, **kw: seen.append(kw))
        m.setattr(factdiff, "judge_call", stub)
        assert ql_capture.census_phase("judge", lambda t: census.cmd_judge(args(), t), "2099-01-03") == 0
        row = seen[0]
        assert (row["event"], row["phase"], row["exit"]) == ("census.phase", "judge", 0) and not ql_capture.ops_problems(row)
        assert {"name": "cost-usd-micro", "n": 36900} in row["rows"] and {"name": "not-enough-information", "n": 1} in row["rows"]
    # the call itself: no tools, a schema, a cap; a result is read from structured_output, else from its text; an error names why
    argv = factdiff.judge_argv("claude-sonnet-5-5", 0.12)
    assert argv[argv.index("--tools") + 1] == "" and argv[argv.index("--max-budget-usd") + 1] == "0.12"
    assert argv[argv.index("--output-format") + 1] == "json" and json.loads(argv[argv.index("--json-schema") + 1]) == factdiff.JUDGE_SCHEMA
    ok = {"type": "result", "subtype": "success", "total_cost_usd": 0.5, "usage": {"input_tokens": 7, "output_tokens": 3, "cache_read_input_tokens": 0}}
    v = [{"n": 1, "verdict": "supported", "sentence": "x"}]
    got = factdiff.judge_result(json.dumps({**ok, "result": "", "structured_output": {"verdicts": v}}))
    assert got == {"verdicts": v, "cost_usd": 0.5, "usage": {"input-tokens": 7, "output-tokens": 3}, "error": ""}
    assert factdiff.judge_result(json.dumps({**ok, "result": 'Here: {"verdicts": ' + json.dumps(v) + "}"}))["verdicts"] == v
    err = factdiff.judge_result(json.dumps({**ok, "subtype": "error_max_budget_usd", "is_error": True, "errors": ["Budget limit reached"]}))
    assert err["verdicts"] is None and err["error"] == "Budget limit reached" and err["cost_usd"] == 0.5
    assert factdiff.judge_result("not json")["error"] and factdiff.judge_result(json.dumps(ok))["error"] == "the result holds no verdicts"
    # factdiff.py review --judge judges the same items, a dry run asks nothing
    flog = tmp_path / "factdiff-2099-01-03.csv"
    flog.write_text(",".join(factdiff.LOG_COLS) + "\n", encoding="utf-8")
    with monkeypatch.context() as m:
        m.setattr(factdiff, "review_items", lambda *a, **k: iter(by["S9990002"]))
        m.setattr(factdiff, "sources", lambda: {})
        m.setattr(factdiff, "judge_call", stub)
        sent.clear()
        ns = argparse.Namespace(log=str(flog), source=[], json=False, judge=True, model=factdiff.JUDGE_MODEL, batch_size=None,
                                max_budget_usd=None, dry_run=False)
        assert factdiff.cmd_review(ns, Counter()) == 0
        shown = capsys.readouterr().out
        assert "- judged: supported (The service restarts" in shown and "- judged: contradicted (" in shown and len(sent) == 1
        assert factdiff.cmd_review(argparse.Namespace(**{**vars(ns), "dry_run": True}), Counter()) == 0 and len(sent) == 1
        assert "batches=1 items=2 " in capsys.readouterr().out


def census_phases_write_one_ops_row_each(tmp_path):
    data = tmp_path / "data"
    (data / "querylog").mkdir(parents=True)
    (data / "querylog" / "config.json").write_text('{"mode": "local"}', encoding="utf-8")
    env = {**os.environ, "CLAUDE_PLUGIN_DATA": str(data), "CLAUDE_PLUGIN_ROOT": KB}
    log = tmp_path / "2026-10-10.csv"
    with open(log, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, census.COLS, lineterminator="\n")
        w.writeheader()
        w.writerow(census_row("S9990001"))
    flog = tmp_path / "factdiff-2026-10-10.csv"
    flog.write_text(",".join(factdiff.LOG_COLS) + "\n", encoding="utf-8")

    def run(tool, *args):
        return subprocess.run([sys.executable, os.path.join(TOOLS, tool), *args], capture_output=True, text=True, encoding="utf-8",
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
    path = ql_store.write_ops(tmp_path / "store", "20261010T000000Z-aaaaaaaa", [ql_store.ops_line(r) for r in spool])
    out = ql_report.ops_lines([path], lambda day: True)
    assert out[0] == "ops: 3 rows (census.phase 3)" and out[1].startswith("  census.phase: 3, failed 1, median ")


def census_run_and_finish_stop_at_a_failing_step_and_refuse_a_foreign_change(tmp_path, monkeypatch, capsys):
    seen = []
    for mod, name in ((census, "KB"), (kbcommon, "KB"), (factdiff, "ROOT")):  # main() sets them: restored after the test
        monkeypatch.setattr(mod, name, getattr(mod, name))

    def go(*argv, code=0, **patch):
        """Run census.py ARGV in this process with its steps replaced, so no tool, git or network is touched."""
        seen.clear()
        codes = {"detect": 1, **patch}  # detect exits 1 when facts need review: no failure

        def run_step(s):
            seen.append(s["name"])
            return codes.get(s["name"], 0), "D-1\tinvalidated\tpublic\tsource S1 superseded\nD-2\trelink\tpublic\tfact:K\tkb/public/x.md:3\ttext\n"

        monkeypatch.setattr(census, "run_step", run_step)
        monkeypatch.setattr(census, "run_commit", lambda s, root_rel, finish: (seen.append("commit") or 0, ""))
        monkeypatch.setattr(sys, "argv", ["census.py", *argv])
        with pytest.raises(SystemExit) as e:
            census.main()
        out = capsys.readouterr()
        assert e.value.code == code
        return out.out + out.err

    monkeypatch.setattr(census, "tracked_dirty", lambda: [])
    monkeypatch.setattr(census, "output_exists", lambda rel: False)
    monkeypatch.setattr(census, "apply_committed", lambda log, date: False)
    # a dry run prints each step's argv, in order, and runs nothing
    text = go("run", "--date", "2099-01-02", "--dry-run")
    assert seen == []
    assert [ln.split(":")[0] for ln in text.splitlines() if ln.startswith("step ")] == [
        "step 1/7 detect", "step 2/7 apply", "step 3/7 check", "step 4/7 repin", "step 5/7 index", "step 6/7 commit",
        "step 7/7 summary"]
    assert "factdiff.py detect --date 2099-01-02 --sitemaps" in text and "apply kb/public/_census/factdiff-2099-01-02.csv" in text
    assert "--factdiff kb/public/_census/factdiff-2099-01-02.csv" in text and "--trailer" not in text
    assert "repin kb/public/_census/2099-01-02.csv --date 2099-01-02 --commit" in text
    # every step runs in order; detect's exit 1 is no failure; the run ends with the summary
    go("run", "--date", "2099-01-02")
    assert seen == ["detect", "apply", "check", "repin", "index", "commit", "summary"]
    # planted failure: check exits 3: the run stops with that code and names the step and the command that resumes it
    text = go("run", "--date", "2099-01-02", code=3, check=3)
    assert seen == ["detect", "apply", "check"]
    assert "step 3/7 check failed with exit 3; resume from it:" in text and "run --date 2099-01-02 --resume" in text
    # --resume skips the steps whose output exists
    monkeypatch.setattr(census, "output_exists", lambda rel: "factdiff-" in rel)
    monkeypatch.setattr(census, "apply_committed", lambda log, date: True)
    text = go("run", "--date", "2099-01-02", "--resume")
    assert seen == ["check", "repin", "index", "commit", "summary"] and "step 1/7 detect: skipped" in text
    # a log that holds phase-2 outcomes is not overwritten without --resume
    log = tmp_path / "2099-01-02.csv"
    log.write_text(",".join(census.COLS) + "\n", encoding="utf-8")
    monkeypatch.setattr(census, "output_exists", lambda rel: True)
    monkeypatch.setattr(census, "read_log", lambda path: [census_row("S9990001", outcome="confirmed")])
    text = go("run", "--date", "2099-01-02", code=2)
    assert seen == [] and "holds 1 phase-2 outcome" in text
    # finish: confirm, sweep, index, commit; it prints the sweep's invalidation and relink lines for the report
    text = go("finish", str(log), "--date", "2099-01-02")
    assert seen == ["confirm", "sweep", "index", "commit"]
    assert text.index("for the report") < text.index("D-1\tinvalidated") < text.index("D-2\trelink")
    assert "--trailer" in go("finish", str(log), "--date", "2099-01-02", "--dry-run")
    text = go("finish", str(log), "--date", "2099-01-02", code=1, sweep=1)
    assert seen == ["confirm", "sweep"] and "step 2/4 sweep failed with exit 1" in text
    # planted failure: a tracked change outside the root refuses the run before its first step; a decision ledger
    # is one finish writes, run does not
    assert census.foreign(["kb/public/_sources.csv", "kb/_self/_decisions.csv", "kb/_self/code.md"], "kb/public", True) == ["kb/_self/code.md"]
    monkeypatch.setattr(census, "tracked_dirty", lambda: ["kb/_self/_decisions.csv"])
    text = go("run", "--date", "2099-01-02", "--resume", code=2)
    assert seen == [] and "refused: tracked changes outside kb/public/: kb/_self/_decisions.csv" in text
    go("finish", str(log), "--date", "2099-01-02")
    assert seen == ["confirm", "sweep", "index", "commit"]


def census_apply_refuses_a_bad_result_and_writes_a_good_one_through_kbid(tmp_path, monkeypatch, capsys):
    root = tmp_path / "public"
    for rel, text in (("dsc/d.md", "- Pinned. [CODE S9990001]\n"), ("auth/a.md", "- Other. [DOC S9990003]\n"),
                      ("_gaps.md", "# Gaps\n\n## dsc/d\n\n- An old gap. (topic: dsc/d)\n\n## auth/a\n\n- Auth gap. (topic: auth/a)\n"),
                      ("_conflicts.md", "# Conflicts\n")):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    cols = ["id", "url", "title", "publisher", "licence", "reuse", "retrieved_utc", "version_or_date", "artifact_sha256",
            "used_in", "superseded_by"]
    rows = [{c: "" for c in cols} | {"id": f"S999000{n}", "url": f"https://docs.example.com/p{n}", "title": f"Page {n}",
                                     "publisher": "Example", "licence": "MIT", "reuse": "copy", "retrieved_utc": "2026-09-26"}
            for n in range(1, 5)]
    kbcommon.write_csv(str(root / "_sources.csv"), cols, rows)
    log = tmp_path / "2099-01-02.csv"
    kbcommon.write_csv(str(log), census.COLS, [census_row(f"S999000{n}", used_in="dsc/d.md") for n in (1, 2, 3)]
                       + [census_row("S9990004", bucket="OK")])
    cited = {"S9990001": [("public/dsc/d.md", 1), ("public/dsc/d.md", 2), ("public/auth/a.md", 1)],
             "S9990002": [("public/dsc/d.md", 3)], "S9990003": [("public/auth/a.md", 1)]}
    steps = []
    monkeypatch.setattr(census, "head_cited_lines", lambda ids: {i: cited[i] for i in ids if i in cited})
    monkeypatch.setattr(census, "run_step", lambda s: (steps.append((s["name"], s["argv"])) or (3 if s["name"] == "stale" and fail else 0), ""))
    for mod, name, value in ((census, "KB", str(root)), (kbcommon, "KB", str(root)),
                             (factdiff, "ROOT", types.SimpleNamespace(path=str(root), name="public", id_prefix="S"))):
        monkeypatch.setattr(mod, name, value)
    fail = False
    pin = "https://raw.githubusercontent.com/Org/Repo/" + "a" * 40 + "/f.md"
    new_id = kbid.source_id(pin)
    good = {"outcomes": [{"id": "S9990001", "outcome": "superseded", "note": f"re-pinned: {new_id}"},
                         {"id": "S9990002", "outcome": "gone", "note": "withdrawn"}],
            "new_rows": [{"url": pin, "title": "File at the new commit", "publisher": "Org", "licence": "MIT", "reuse": "copy",
                          "version_or_date": "main@aaaaaaaaaaaa", "used_in": "dsc/d.md"}],
            "superseded": {"S9990001": new_id},
            "gaps": [{"topic": "dsc/d", "text": "Nobody states the limit."}, {"topic": "dsc/d", "text": "A second gap (topic: dsc/d)"}],
            "conflicts": [{"topic": "auth/a", "text": "Two pages disagree.\nSecond line."}],
            "foreign_edits": [{"file": "kb/public/auth/a.md", "line": 1, "change": "reword the fact"}],
            "edited_files": [kbcommon.repo_rel("dsc/d.md")]}
    result = tmp_path / "result.json"

    def apply(res, *, dry=False, group="dsc"):
        result.write_text(json.dumps(res), encoding="utf-8")
        steps.clear()
        code = census.cmd_apply(argparse.Namespace(log=str(log), group=group, from_json=str(result), dry_run=dry), Counter())
        out = capsys.readouterr()
        return code, out.out + out.err

    def state():
        return {p.name: p.read_bytes() for p in (root / "_sources.csv", root / "_gaps.md", root / "_conflicts.md", log)}

    before = state()
    schema = json.loads(Path(census.RESULT_SCHEMA).read_text(encoding="utf-8"))
    assert schema["properties"]["outcomes"]["items"]["properties"]["outcome"]["enum"] == list(census.OUTCOMES)
    # --dry-run prints every write and step, runs no step and changes nothing
    code, text = apply(good, dry=True)
    assert code == 0 and steps == [] and state() == before, text
    for said in (f"would add source {new_id} {pin}", f"would set superseded_by of S9990001 to {new_id}",
                 "would write under `## dsc/d` in _gaps.md: - Nobody states the limit. (topic: dsc/d)",
                 "would write under `## auth/a` in _conflicts.md: - Two pages disagree. Second line. (topic: auth/a)",
                 "would record 2 outcome(s)", "(not taken from the row: used_in)",
                 "foreign edit (not applied): kb/public/auth/a.md:1 reword the fact"):
        assert said in text
    assert "step 1/3 anchor: python3 _tools/factdiff.py anchor --file dsc/d.md" in text
    # planted failures: each problem is named, nothing is written
    bad = {**good, "outcomes": [{"id": "S9990009", "outcome": "confirmed", "note": ""},
                                {"id": "S9990003", "outcome": "confirmed", "note": ""},
                                {"id": "S9990004", "outcome": "confirmed", "note": ""},
                                {"id": "S9990002", "outcome": "kept", "note": ""}],
           "new_rows": [{"url": "https://docs.example.com/p2", "title": "Other title", "publisher": "Example", "licence": "MIT",
                         "reuse": "copy"},
                        {"url": "https://docs.example.com/new", "title": "T", "publisher": "P", "licence": "L", "reuse": "bogus"}],
           "superseded": {"S9990001": "S-aaaaaaaa"}, "edited_files": ["auth/a.md"],
           "gaps": [{"topic": "dsc/nope", "text": "x"}]}
    code, text = apply(bad)
    assert code == 2 and state() == before and steps == []
    for said in ("outcomes[3].outcome: 'kept' is not one of confirmed, updated, superseded, gone, unconfirmed",):
        assert said in text
    code, text = apply({**bad, "outcomes": bad["outcomes"][:3]})
    assert code == 2 and state() == before
    for said in ("outcomes[0]: unknown source id S9990009", "outcomes[1]: S9990003 is a row of group auth, not of dsc",
                 "outcomes[2]: S9990004 is no phase-2 row", "new_rows[0] https://docs.example.com/p2: refused: S9990002 is already",
                 "new_rows[1] https://docs.example.com/new: refused: reuse 'bogus' is not one of",
                 "superseded S9990001: unknown source id S-aaaaaaaa", "edited_files: auth/a.md is outside the files group dsc owns",
                 "gaps[0]: topic dsc/nope is no article"):
        assert said in text
    code, text = apply({**good, "extra": 1, "gaps": [{"topic": "Bad Topic", "text": ""}]})
    assert code == 2 and "$: unexpected extra" in text and "$.gaps[0].topic" in text and "$.gaps[0].text: is empty" in text
    code, text = apply(good, group="nope")
    assert code == 2 and "no group 'nope'" in text and "groups: auth, dsc" in text
    # the write: the row through kbid, superseded_by, the bullets under their headings, the outcomes, the steps
    code, text = apply(good)
    assert code == 0 and [n for n, _ in steps] == ["anchor", "index", "stale"] and "foreign edit (not applied)" in text
    assert steps[0][1][-2:] == ["--file", "dsc/d.md"]
    srcs = {r["id"]: r for r in csv.DictReader(open(root / "_sources.csv", encoding="utf-8", newline=""))}
    assert srcs["S9990001"]["superseded_by"] == new_id and srcs[new_id]["url"] == pin and srcs[new_id]["used_in"] == ""
    assert srcs[new_id]["version_or_date"] == "main@aaaaaaaaaaaa" and srcs[new_id]["retrieved_utc"] != ""
    assert list(srcs)[-1] == new_id and len(srcs) == 5
    gaps = (root / "_gaps.md").read_text(encoding="utf-8")
    assert gaps.index("- An old gap.") < gaps.index("- Nobody states the limit. (topic: dsc/d)") < gaps.index("## auth/a")
    assert gaps.count("A second gap (topic: dsc/d)") == 1
    assert (root / "_conflicts.md").read_text(encoding="utf-8").endswith("\n## auth/a\n\n- Two pages disagree. Second line. (topic: auth/a)\n")
    got = {r["id"]: (r["outcome"], r["outcome_note"]) for r in census.read_log(str(log))}
    assert got["S9990001"][0] == "superseded" and got["S9990002"] == ("gone", "withdrawn") and got["S9990003"] == ("", "")
    # a second apply writes the same bytes; a failing step stops the run with its code and names the step
    done = state()
    assert apply(good)[0] == 0 and state() == done
    fail = True
    code, text = apply(good)
    assert code == 3 and "step 3/3 stale failed with exit 3; resume from it: python3 _tools/census.py apply" in text
    fail = False


def census_retry_tries_a_name_resolution_or_connection_error_once_and_notes_it_apart_from_blocked(tmp_path, monkeypatch, capsys):
    url = "https://docs.example.com/page"
    errors = {
        "dns": urllib.error.URLError(socket.gaierror(8, "nodename nor servname provided, or not known")),
        "connect": urllib.error.URLError(ConnectionRefusedError(61, "Connection refused")),
        "slow": TimeoutError("timed out"),
        "blocked": urllib.error.URLError(OSError("Tunnel connection failed: 403 Forbidden")),
        "http": urllib.error.HTTPError(url, 503, "unavailable", None, None),
    }
    tries, pauses = [], []

    class Page:
        status = 200
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, n=-1):
            return b"<html>Last updated: 2026-01-02</html>"

        def geturl(self):
            return url

    def urlopen(req, **kw):
        step = script.pop(0)
        tries.append(step)
        if step == "page":
            return Page()
        raise errors[step]

    with monkeypatch.context() as m:
        m.setattr(census.urllib.request, "urlopen", urlopen)
        m.setattr(census.time, "sleep", pauses.append)
        m.setattr(ql_capture, "record_request", lambda *a, **k: None)
        m.setattr(census, "sitemap_lastmod", lambda u: None)
        m.setattr(census, "_ctx", object())

        def check(*steps):
            script[:] = steps
            tries.clear()
            pauses.clear()
            return census.check_live(url, "2026-01-01", "")

        script = []
        st, res = check("dns", "page")  # a transient resolver failure: the second try answers
        assert (st, res["bucket"], res["note"]) == (200, "CHANGED", "") and tries == ["dns", "page"] and pauses == [census.RETRY_PAUSE]
        for kind in ("dns", "connect", "slow"):  # failing twice: noted apart, in the same run, tried exactly twice
            st, res = check(kind, kind)
            note = "dns" if kind == "dns" else "connect"
            assert res["bucket"] == "NEEDS-READING" and res["note"] == note and st.startswith(f"{note}: "), (kind, st, res)
            assert tries == [kind, kind] and pauses == [census.RETRY_PAUSE] and res["evidence"].endswith("(tried twice)")
        for kind, note in (("blocked", "blocked"), ("http", "")):  # a denied host and an HTTP error are not retried
            st, res = check(kind)
            assert (res["bucket"], res["note"], tries, pauses) == ("NEEDS-READING", note, [kind], []), (kind, st, res)
        script[:] = ["dns", "dns"]  # a Learn page without a source repo goes through the same fetch
        assert census.check_learn_page(url, "2026-01-01")[1]["note"] == "dns"

    rows = [census_row(f"S999000{n}", bucket="NEEDS-READING", note=note, url=u, http_status=hs)
            for n, (note, u, hs) in enumerate([
                ("dns", "https://a.example.com/1", "dns: x"), ("dns", "https://a.example.com/2", "dns: x"),
                ("connect", "https://b.example.com/1", "connect: x"), ("blocked", "https://c.example.com/1", "blocked"),
                ("", "https://d.example.com/1", "503"), ("", "https://d.example.com/2", "200")], 1)]
    log = tmp_path / "retry.csv"
    kbcommon.write_csv(str(log), census.COLS, rows)
    with monkeypatch.context() as m:
        m.setattr(census, "reading_queue", lambda rows, fd_rows, *a: [])  # the queue block is another test's
        assert census.cmd_summary(argparse.Namespace(log=str(log), factdiff=None), Counter()) == 0
    out = capsys.readouterr().out
    assert "needs-reading by note: -=2 blocked=1 connect=1 dns=2\n" in out
    assert "blocked hosts (denied by this environment's network policy, their sources stay unconfirmed): c.example.com=1\n" in out
    assert "dns hosts (name resolution failed twice, a pause apart): a.example.com=2\n" in out
    assert "connect hosts (connection failed twice, a pause apart): b.example.com=1\n" in out
    assert "HTTP errors (a status other than 200 that left the source to read): 1\n" in out


def census_baseline_is_written_from_a_compared_document_and_decides_a_page_with_no_date_at_the_next_census(tmp_path, monkeypatch, capsys):
    with monkeypatch.context() as m:
        root = tmp_path / "public"
        root.mkdir(parents=True)
        cols = ["id", "url", "title", "publisher", "licence", "reuse", "retrieved_utc", "version_or_date", "artifact_sha256",
                "used_in", "superseded_by"]
        pin = "https://raw.githubusercontent.com/Org/Repo/" + "a" * 40 + "/f.md"
        page = lambda n: f"https://docs.example.com/p{n}"  # noqa: E731
        urls = {1: page(1), 2: page(2), 3: page(3), 4: page(4), 5: pin, 6: page(6), 7: page(7), 8: page(8)}
        kbcommon.write_csv(str(root / "_sources.csv"), cols, [
            {c: "" for c in cols} | {"id": f"S999000{n}", "url": u, "reuse": "copy", "retrieved_utc": "2099-01-01",
                                      "superseded_by": "S9990001" if n == 8 else ""} for n, u in urls.items()])
        kbcommon.write_csv(str(root / "_fetch_state.csv"), kbcommon.STATE_COLS,
                           [{c: "" for c in kbcommon.STATE_COLS} | {"id": "S9990007", "url": page(7), "etag": '"v1"'}])
        cache = tmp_path / "cache" / "public"
        cache.mkdir(parents=True)
        text = "A page with no last-updated date. It states one fact."

        def fetched(n, when, status=200):
            (cache / f"S999000{n}.json").write_text(json.dumps({"id": f"S999000{n}", "url": urls[n], "status": status, "text": text,
                                                                "final": urls[n], "version": {}, "fetched_utc": when}), encoding="utf-8")

        fetched(1, "2099-01-03T10:00:00+00:00")  # inside the census: its log's date to the confirmation date
        fetched(2, "2099-01-05T10:00:00+00:00")  # after the confirmation: no step compared it
        fetched(3, "2099-01-01T10:00:00+00:00")  # before the census began
        fetched(4, "2099-01-03T10:00:00+00:00", status=429)  # an error page is no document
        fetched(5, "2099-01-03T10:00:00+00:00")  # a pinned url needs no baseline
        fetched(6, "2099-01-03T10:00:00+00:00")  # not confirmed by this census
        fetched(7, "2099-01-03T10:00:00+00:00")  # already holds one: left as it is
        log = tmp_path / "2099-01-02.csv"
        rows = [census_row(f"S999000{n}", url=u, bucket="OK") for n, u in urls.items() if n in (1, 2, 3, 4, 5, 7)]
        rows.append(census_row("S9990006", url=urls[6], bucket="NEEDS-READING"))
        kbcommon.write_csv(str(log), census.COLS, rows)
        for mod, name, value in ((census, "KB", str(root)), (kbcommon, "KB", str(root)), (factdiff, "CACHE", str(tmp_path / "cache")),
                                 (factdiff, "ROOT", types.SimpleNamespace(path=str(root), name="public", id_prefix="S")),
                                 (kbfacts, "clone_home", lambda: str(tmp_path / "no-clone"))):
            m.setattr(mod, name, value)
        # the gap before the census: live (S9990008 is superseded) and unpinned (S9990005 is) with no baseline (S9990007 has one)
        assert census.cmd_baselines(argparse.Namespace(list=False), Counter()) == 1
        out = capsys.readouterr().out
        assert out.startswith("baselines: 5 of 6 live unpinned source(s) hold no detection baseline") and "  docs.example.com: 5\n" in out
        assert census.cmd_baselines(argparse.Namespace(list=True), Counter()) == 1
        assert f"    S9990001 {page(1)}\n" in capsys.readouterr().out
        # confirm writes it from the one document inside the census, and from no other
        assert census.cmd_confirm(argparse.Namespace(log=str(log), date="2099-01-04", dry_run=False), Counter()) == 0
        assert "1 detection baseline(s) written" in capsys.readouterr().out
        state = {r["id"]: r for r in csv.DictReader(open(root / "_fetch_state.csv", encoding="utf-8", newline=""))}
        assert state["S9990001"]["doc_sha256"] == hashlib.sha256(text.encode()).hexdigest()
        assert state["S9990001"]["detected_utc"] == "2099-01-03T10:00:00Z" and state["S9990001"]["checked_utc"] == "2099-01-04T00:00:00Z"
        assert [n for n in (2, 3, 4, 5, 6) if state.get(f"S999000{n}", {}).get("doc_sha256")] == []
        assert state["S9990007"]["etag"] == '"v1"' and state["S9990007"]["doc_sha256"] == ""
        assert census.cmd_baselines(argparse.Namespace(list=False), Counter()) == 1
        assert capsys.readouterr().out.startswith("baselines: 4 of 6 ")
        # the next census: factdiff's unchanged verdict (baseline taken inside the last confirmation) decides the page with no
        # date; a source with no baseline in the log (planted failure) is checked here and goes to a reader
        flog = tmp_path / "factdiff-2099-02-01.csv"
        head = {c: "" for c in factdiff.LOG_COLS} | {"verdict": "unchanged", "signal": "hash", "evidence": "document text identical"}
        kbcommon.write_csv(str(flog), factdiff.LOG_COLS, [
            head | {"source_id": "S9990001", "url": page(1), "baseline_utc": state["S9990001"]["detected_utc"]},
            head | {"source_id": "S9990002", "url": page(2), "baseline_utc": "2099-01-05T10:00:00Z"}])
        asked = []

        def check_one(r, c):
            asked.append(r["id"])
            return "200", census.verdict("NEEDS-READING", "HTTP 200, no last-updated date")

        m.setattr(census, "check_one", check_one)
        out_log = tmp_path / "2099-02-01.csv"
        a = argparse.Namespace(date="2099-02-01", out=str(out_log), jobs=1, source=["S9990001", "S9990002"], factdiff=str(flog))
        assert census.cmd_check(a, Counter()) == 0
        got = {r["id"]: r for r in csv.DictReader(open(out_log, encoding="utf-8", newline=""))}
        assert asked == ["S9990002"] and got["S9990001"]["bucket"] == "OK" and got["S9990001"]["evidence"].startswith("fact diff: unchanged")
        assert got["S9990002"]["bucket"] == "NEEDS-READING"


def census_repin_writes_the_new_row_only_when_every_cited_fact_is_word_for_word_at_the_newer_commit(tmp_path, monkeypatch, capsys):
    def git(cwd, *args):
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", env=git_env(),
                              check=True).stdout.strip()

    up = tmp_path / "up"
    up.mkdir(parents=True)
    git(up, "init", "-q", "-b", "main")
    files = {"f.md": "# Nightly jobs\n\nThe Orion scheduler restarts every night at three o'clock. The restart takes about five minutes.\n\n"
                     "Quartz retention defaults to thirty days on new installs.\n",
             "g.md": "# Limits\n\nThe Falcon gateway accepts at most forty connections per node.\n\nCobalt tokens expire after twelve hours.\n",
             "h.md": "# Cache\n\nNimbus caches answers for ten minutes.\n",
             "i.md": "# Logs\n\nHelium logs rotate daily.\n"}
    (up / "docs").mkdir()
    for name, text in files.items():
        (up / "docs" / name).write_text(text, encoding="utf-8")
    git(up, "add", ".")
    git(up, "commit", "-q", "-m", "one")
    c1 = git(up, "rev-parse", "HEAD")
    git(up, "tag", "1.0.0")
    (up / "docs" / "f.md").write_text(files["f.md"] + "\nA later paragraph about Zephyr exports.\n", encoding="utf-8")
    (up / "docs" / "g.md").write_text(files["g.md"].replace("twelve", "six"), encoding="utf-8")
    (up / "docs" / "i.md").write_text(files["i.md"] + "\nUnrelated note.\n", encoding="utf-8")
    git(up, "commit", "-q", "-am", "two")
    c2 = git(up, "rev-parse", "HEAD")
    git(up, "tag", "1.0.1")
    repos = tmp_path / "repos"
    clone = repos / "github.com__Org__Repo.git"
    repos.mkdir()
    git(tmp_path, "clone", "-q", "--bare", str(up), str(clone))

    root = tmp_path / "public"
    (root / "dsc").mkdir(parents=True)
    (root / "_retrieval" / "doc2query").mkdir(parents=True)
    (root / "_root.md").write_text("---\nroot: public\nid_prefix: S\nvisibility: public\ndescription: scratch\n---\n", encoding="utf-8")
    raw = "https://raw.githubusercontent.com/Org/Repo/"
    urls = {"S9001": f"{raw}{c1}/docs/f.md", "S9002": f"{raw}{c1}/docs/g.md", "S9003": f"{raw}{c1}/docs/h.md",
            "S9004": f"{raw}1.0.0/docs/i.md", "S9005": "https://github.com/Org/Repo/releases/tag/1.0.0"}
    cols = ["id", "url", "title", "publisher", "licence", "reuse", "retrieved_utc", "version_or_date", "artifact_sha256", "used_in",
            "superseded_by"]
    kbcommon.write_csv(str(root / "_sources.csv"), cols, [
        {c: "" for c in cols} | {"id": sid, "url": u, "title": f"{Path(u).name} at {c1[:12]}", "publisher": "Org", "licence": "MIT",
                                 "reuse": "copy", "retrieved_utc": "2026-09-26", "used_in": "dsc/d.md"} for sid, u in urls.items()])
    facts = {"fA": ("The Orion scheduler restarts every night at three o'clock.", "S9001"),
             "fB": ("Quartz retention defaults to thirty days on new installs.", "S9001"),
             "gA": ("The Falcon gateway accepts at most forty connections per node.", "S9002"),
             "gB": ("Cobalt tokens expire after twelve hours.", "S9002"),
             "hA": ("Nimbus caches answers for ten minutes.", "S9003"),
             "iA": ("Helium logs rotate daily.", "S9004"), "iB": ("Helium logs rotate daily since 1.0.0.", "S9004")}
    article = root / "dsc" / "d.md"
    article.write_text("---\ntopic: dsc/d\npriority: P1\nretrieved_utc: 2026-09-26\nsources: [S9001, S9002, S9003, S9004, S9005]\n"
                       "status: complete\n---\n# D\n\n## Facts\n"
                       + "".join(f"- {t} [CODE {sid}]\n" for t, sid in facts.values()), encoding="utf-8")
    keys = {n: kbfacts.fact_key(f"{t} [CODE {sid}]") for n, (t, sid) in facts.items()}
    (root / "_retrieval" / "doc2query" / "expansions.csv").write_text(f"key,question\n{keys['fA']},When does Orion restart\n",
                                                                       encoding="utf-8")
    log_rows = []
    for sid, u in urls.items():
        c = census.classify(u)
        log_rows.append(census_row(sid, url=u, kind=c["kind"], repo=c["repo"], pin=c["pin"], path=c["path"], used_in="dsc/d.md",
                                   bucket="NEWER-VERSION" if sid in ("S9004", "S9005") else "CHANGED",
                                   proof=f"main@{c2[:12]}" if sid in ("S9001", "S9002", "S9003") else "",
                                   note="newer=1.0.1" if sid in ("S9004", "S9005") else f"latest={c2}"))
    log = tmp_path / "2099-01-02.csv"
    kbcommon.write_csv(str(log), census.COLS, log_rows)
    new_url = f"{raw}{c2}/docs/f.md"
    new_id = kbid.source_id(new_url)
    committed = []
    real_git = census.g

    def fake_git(d, *args, **kw):  # the commit goes to a record, never to this repository
        if d == kbcommon.HOME and args[:1] in (("add",), ("commit",)):
            committed.append(args)
            return 0, "", ""
        return real_git(d, *args, **kw)

    def no_network(*a, **k):
        raise AssertionError("repin touched the network")

    with monkeypatch.context() as m:
        public = kbcommon.load_root(str(root))
        for mod, name, value in ((kbcommon, "_ROOTS", [public]), (kbcommon, "KB", str(root)), (census, "KB", str(root)),
                                 (factdiff, "ROOT", public), (factdiff, "CACHE", str(tmp_path / "cache")),
                                 (census, "REPOS", str(repos)), (census, "repo_dir", lambda repo, base=None: (str(clone), "")),
                                 (census, "g", fake_git), (kbfacts, "clone_home", lambda: str(tmp_path / "no-clone"))):
            m.setattr(mod, name, value)
        m.setattr(socket.socket, "connect", no_network)
        anchors = {}
        for sid, name in (("S9001", "f.md"), ("S9002", "g.md"), ("S9004", "i.md")):
            old = provider.doc_text(files[name].encode(), "text/plain", urls[sid])  # the file as it was at the pin
            for r in factdiff.anchor_rows(sid, [(keys[n], "dsc/d.md", 0, f"{t} [CODE {s}]") for n, (t, s) in facts.items() if s == sid],
                                          {"status": 200, "text": old}, "copy", "2026-09-26"):
                assert r["status"] == "located", r
                anchors[(r["fact"], r["path"], r["source_id"])] = r
        factdiff.write_anchors(anchors)  # S9003 has none: nothing was ever located in it
        rows = census.read_log(str(log))
        # before: the pinned file with a fact not found, and the one whose fact names the pinned tag, queue only those facts
        items = census.repin_items(census.phase2_rows(rows))
        assert sorted(items) == ["S9002", "S9004"] and [i["fact"].split(" [")[0] for i in items["S9002"]] == [facts["gB"][0]]
        assert "twelve hours" in items["S9002"][0]["old"] and "six hours" in items["S9002"][0]["new"]
        assert items["S9004"][0]["note"].startswith("the fact names the pinned version at ")
        queue = {q["id"]: q for q in census.reading_queue(rows, [])}
        assert [(i, queue[i]["mode"], queue[i]["items"]) for i in sorted(queue)] == [
            ("S9001", "document", 0), ("S9002", "review", 1), ("S9003", "document", 0), ("S9004", "review", 1), ("S9005", "document", 0)]

        def state():
            return {p.name: p.read_bytes() for p in (root / "_sources.csv", root / "_anchors.csv", article, log,
                                                      root / "_retrieval" / "doc2query" / "expansions.csv")}

        def repin(dry=False, commit=False):
            code = census.cmd_repin(argparse.Namespace(log=str(log), date="2099-01-03", dry_run=dry, commit=commit), Counter())
            return code, capsys.readouterr().out

        before = state()
        code, text = repin(dry=True)
        assert code == 0 and state() == before and committed == []
        assert f"would add source {new_id} {new_url}" in text and "would re-point 2 fact(s) of S9001" in text
        assert "repin S9002: stays in the queue: 1 of 2 fact(s) not found word for word" in text
        assert "repin S9003: stays in the queue: no located anchors" in text
        assert "repin S9004: stays in the queue: 1 of 2 fact(s) not found word for word" in text
        assert "repin S9005: stays in the queue: the url names a release, not a file" in text
        code, text = repin(commit=True)
        assert code == 0 and f"repin S9001: re-pinned to {new_id}: {c1[:12]} -> {c2[:12]}, 2 fact(s) found word for word" in text
        srcs = {r["id"]: r for r in csv.DictReader(open(root / "_sources.csv", encoding="utf-8", newline=""))}
        assert srcs["S9001"]["superseded_by"] == new_id and srcs[new_id]["url"] == new_url and srcs[new_id]["used_in"] == "dsc/d.md"
        assert srcs[new_id]["retrieved_utc"] == "2099-01-03" and srcs[new_id]["title"] == f"f.md at {c2[:12]}"
        assert srcs[new_id]["version_or_date"].startswith(f"commit {c2}; re-pinned 2099-01-03 from S9001")
        assert [srcs[i]["superseded_by"] for i in ("S9002", "S9003", "S9004", "S9005")] == [""] * 4
        body = article.read_text(encoding="utf-8")
        assert f"sources: [S9002, S9003, S9004, S9005, {new_id}]" in body and body.count(f"[CODE {new_id}]") == 2
        assert "[CODE S9001]" not in body and body.count("[CODE S9002]") == 2
        moved = {k: kbfacts.fact_key(f"{facts[n][0]} [CODE {new_id}]") for n, k in (("fA", "fA"), ("fB", "fB"))}
        got = factdiff.read_anchors()
        assert {(moved[n], "dsc/d.md", new_id) for n in moved} <= set(got) and got[(moved["fA"], "dsc/d.md", new_id)]["verified_utc"] == "2099-01-03"
        assert not any(k[2] == "S9001" for k in got) and len(got) == len(anchors)
        assert (root / "_retrieval" / "doc2query" / "expansions.csv").read_text(encoding="utf-8") == \
            f"key,question\n{moved['fA']},When does Orion restart\n"
        out = {r["id"]: (r["outcome"], r["outcome_note"]) for r in census.read_log(str(log))}
        assert out["S9001"] == ("superseded", f"re-pinned to {new_id}: {c1[:12]} -> {c2[:12]}, 2 fact(s) found word for word")
        assert [out[i] for i in ("S9002", "S9003", "S9004", "S9005")] == [("", "")] * 4
        assert [a[0] for a in committed] == ["add", "commit"] and "KB-Verified: 2099-01-03" in committed[1]
        assert any(x.endswith("d.md") for x in committed[0]) and "re-pin 1 source(s)" in committed[1][committed[1].index("-m") + 1]
        # a second run finds no candidate for the row it settled and writes the same bytes
        done = state()
        code, text = repin(commit=True)
        assert code == 0 and state() == done and len(committed) == 2 and "superseded=0" in text
        rows = census.read_log(str(log))
        assert sorted(q["id"] for q in census.reading_queue(rows, [])) == ["S9002", "S9003", "S9004", "S9005"]


def census_github_page_signals_decide_a_page_without_a_reader(tmp_path, monkeypatch):
    def git(cwd, *args, when=""):
        env = git_env(**({"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when} if when else {}))
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", env=env, check=True).stdout.strip()

    def write(d, files):
        for name, text in files.items():
            (d / name).write_text(text, encoding="utf-8")

    home, wiki = tmp_path / "home", tmp_path / "wiki"
    for d, files in ((home, {"README.md": "# Repo\n", "LICENSE": "MIT\n"}),
                     (wiki, {"Home.md": "# Wiki\n", "Page-One.md": "One.\n", "Page-Two.md": "Two.\n"})):
        d.mkdir(parents=True)
        git(d, "init", "-q", "-b", "main")
        write(d, files)
        git(d, "add", ".")
        git(d, "commit", "-q", "-m", "one", when="2026-01-01T10:00:00Z")
    write(home, {"src.txt": "code\n"})  # a commit after retrieval that touches neither the README nor the licence
    git(home, "add", ".")
    git(home, "commit", "-q", "-m", "two", when="2026-09-01T10:00:00Z")
    write(wiki, {"Page-Two.md": "Two, edited.\n"})
    git(wiki, "commit", "-q", "-am", "two", when="2026-09-01T10:00:00Z")
    clones = {}

    def clone(name, src):
        dest = tmp_path / f"{name}.git"
        git(tmp_path, "clone", "-q", "--bare", str(src), str(dest))
        return str(dest)

    clones["github.com/Org/Repo"], clones["github.com/Org/Repo.wiki"] = clone("home1", home), clone("wiki1", wiki)
    pages, asked = {}, []

    def fetch(url, **kw):
        asked.append(url)
        status, body, final = pages.get(url, (404, "", url))
        return status, body, final

    html = lambda *stamps: "<html><body>" + "".join(f'<relative-time datetime="{t}"></relative-time>' for t in stamps) + "</body></html>"  # noqa: E731
    base = "https://github.com/Org/Repo"
    since = "2026-06-01"

    def verdict(url, **kw):
        asked.clear()
        c = census.classify(url)
        st, res = census.check_one({"url": url, "retrieved_utc": since}, c)
        return res

    with monkeypatch.context() as m:
        m.setattr(census, "repo_dir", lambda repo, base=None: (clones[repo], "") if repo in clones else (None, f"clone failed: {repo}"))
        m.setattr(census, "fetch", fetch)
        m.setattr(provider, "request", lambda *a, **k: (_ for _ in ()).throw(AssertionError("a github page was fetched by a signal that needs no page")))
        # a repository home: the README and the licence have no commit since retrieval, though HEAD moved
        pages[base] = (200, "<html><p>Repo</p></html>", base)
        res = verdict(base)
        assert res["bucket"] == "OK" and "README README.md and the licence have no commit since 2026-06-01" in res["evidence"], res
        # ... the archived banner dated after retrieval, and one dated before it
        pages[base] = (200, "<p>This repository has been archived by the owner on Aug 5, 2026. It is now read-only.</p>", base)
        assert verdict(base)["bucket"] == "CHANGED"
        pages[base] = (200, "<p>This repository has been archived by the owner on Jan 5, 2026. It is now read-only.</p>", base)
        assert verdict(base)["bucket"] == "OK"
        pages[base] = (200, "<p>Repo</p>", base)
        # ... a release tag after retrieval, a README commit after it (a planted failure for each), a page that moved
        git(home, "tag", "v1.0.0")
        clones["github.com/Org/Repo"] = clone("home2", home)
        res = verdict(base)
        assert res["bucket"] == "CHANGED" and "release tag(s) created on or after retrieval 2026-06-01: v1.0.0" in res["evidence"], res
        write(home, {"README.md": "# Repo, rewritten\n"})
        git(home, "commit", "-q", "-am", "three", when="2026-09-02T10:00:00Z")
        clones["github.com/Org/Repo"] = clone("home3", home)
        res = verdict(base)
        assert res["bucket"] == "CHANGED" and res["evidence"].startswith("README README.md: 1 commit(s) since 2026-06-01"), res
        pages[base] = (200, "<p>Repo</p>", "https://github.com/Org/Other")
        assert verdict(base)["evidence"] == "redirected to https://github.com/Org/Other"
        # a wiki page by the commits of its file in the wiki's repository; a wiki's own git url by its newest commit
        for page, want in (("Page-One", "OK"), ("Page-Two", "CHANGED"), ("Home", "OK"), ("Missing", "NEEDS-READING")):
            url = f"{base}/wiki/{page}"
            pages[url] = (200, "<p>page</p>", url)
            assert verdict(url)["bucket"] == want, (page, verdict(url))
        pages[f"{base}/wiki"] = (200, "<p>page</p>", f"{base}/wiki")
        assert verdict(f"{base}/wiki")["bucket"] == "OK"
        assert verdict(f"{base}.wiki.git")["bucket"] == "CHANGED" and asked == []
        # an issue or a discussion by the latest timestamp of its timeline
        for url, stamps, want in ((f"{base}/issues/7", ("2026-03-01T10:00:00Z", "2026-05-01T10:00:00Z"), "OK"),
                                  (f"{base}/issues/8", ("2026-03-01T10:00:00Z", "2026-07-01T10:00:00Z"), "CHANGED"),
                                  (f"{base}/issues/9", (), "NEEDS-READING"),
                                  ("https://github.com/orgs/Org/discussions/3", ("2026-04-02T10:00:00Z",), "OK")):
            pages[url] = (200, html(*stamps), url)
            assert verdict(url)["bucket"] == want, (url, verdict(url))
        pages[f"{base}/issues/10"] = (404, "", f"{base}/issues/10")
        assert verdict(f"{base}/issues/10")["bucket"] == "GONE"
        # api.github.com is not called, and a page no signal fits goes to reading
        res = verdict("https://api.github.com/repos/Org/Repo/issues?state=open")
        assert (res["bucket"], res["note"], asked) == ("NEEDS-READING", "github page", [])
        assert verdict(f"{base}/releases")["bucket"] == "NEEDS-READING"
        # factdiff.detect: the stored version id decides; a baseline of the text alone is dated against the signal
        m.setattr(factdiff, "ROOT", kbcommon.root("public"))
        m.setattr(factdiff, "CACHE", str(tmp_path / "cache"))
        m.setattr(factdiff, "madeup_text", lambda url: None)

        def document(url, row=None, etag="", lastmod=""):
            raw = pages[url][1]
            keys = [k for k in (row.get("version_meta") or "").split(",") if k.strip() and k != "-"]
            text = provider.doc_text(raw.encode(), "text/html", url)
            return {"status": 200, "final": url, "hops": [], "etag": "", "lastmod": "", "error": "", "bytes": len(raw), "raw": raw,
                    "version": provider.version_of(raw, keys), "text": text, "ctype": "text/html",
                    "sha": hashlib.sha256(text.encode()).hexdigest()}

        m.setattr(provider, "document", document)
        rows = provider.providers()

        def detect(url, **state):
            return factdiff.detect_source("S9990001", {"url": url}, state, rows)

        page = f"{base}/wiki/Page-One"
        verdict_, signal, ev, new, _, _ = detect(page)
        assert (verdict_, new["version"]) == ("new", census.gh_page_id(page, "")) and len(new["version"]) == 16
        assert detect(page, version=new["version"])[:2] == ("unchanged", "version")
        assert detect(page, version="0" * 16, doc_sha256="x")[:2] == ("changed", "version")
        old = {"doc_sha256": "x", "detected_utc": "2026-06-01T00:00:00Z"}
        assert detect(page, **old)[:2] == ("unchanged", "git")
        assert detect(f"{base}/wiki/Page-Two", **old)[:2] == ("changed", "version")
        issue = f"{base}/issues/7"
        v, signal, ev, new, _, _ = detect(issue, **old)
        assert (v, signal, new["version"]) == ("unchanged", "version", "2026-05-01T10:00:00Z") and ev.startswith("timeline 2026-05-01")
        assert detect(f"{base}/issues/8", **old)[:2] == ("changed", "version")
        assert factdiff.content_date({"version": {"timeline": "2026-05-01T10:00:00Z"}}) == "2026-05-01"


def factdiff_learn_git_decides_a_mapped_learn_page_by_its_repository_history_and_asks_learn_for_the_rest(tmp_path, monkeypatch):
    def git(cwd, *args, when=""):
        env = git_env(**({"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when} if when else {}))
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", env=env, check=True).stdout.strip()

    docs = tmp_path / "docs"
    (docs / "docs" / "identity").mkdir(parents=True)
    git(docs, "init", "-q", "-b", "main")
    for name in ("quiet", "busy", "same-day"):
        (docs / "docs" / "identity" / f"{name}.md").write_text(f"# {name}\n", encoding="utf-8")
    git(docs, "add", ".")
    git(docs, "commit", "-q", "-m", "one", when="2026-01-01T10:00:00Z")
    (docs / "docs" / "identity" / "busy.md").write_text("# busy, edited\n", encoding="utf-8")
    (docs / "docs" / "identity" / "same-day.md").write_text("# same-day, edited\n", encoding="utf-8")
    git(docs, "commit", "-q", "-am", "two", when="2026-09-01T10:00:00Z")
    bare = tmp_path / "entra-docs.git"
    git(tmp_path, "clone", "-q", "--bare", str(docs), str(bare))
    cloned = []

    def repo_dir(repo, base=None):
        cloned.append(repo)
        return (str(bare), "") if repo == "github.com/MicrosoftDocs/entra-docs" else (None, f"clone failed: {repo}")

    asked = []

    def document(url, row=None, etag="", lastmod=""):
        asked.append(url)
        return {"status": 304, "error": "", "final": url, "hops": []}

    monkeypatch.setattr(census, "repo_dir", repo_dir)
    monkeypatch.setattr(provider, "document", document)
    monkeypatch.setattr(factdiff, "ROOT", kbcommon.root("public"))
    monkeypatch.setattr(factdiff, "CACHE", str(tmp_path / "cache"))
    rows = provider.providers()
    page = lambda name, docset="entra/identity": f"https://learn.microsoft.com/en-us/{docset}/{name}"  # noqa: E731
    old = {"doc_sha256": "x", "detected_utc": "2026-06-01T00:00:00Z", "http_status": "200"}

    def detect(url, **state):
        asked.clear()
        v, signal, ev, new, _, _ = factdiff.detect_source("S9990002", {"url": url}, state, rows)
        return v, signal, ev, new, list(asked)

    # the map is census's: classify and learn_source answer alike, and factdiff holds no copy of it
    c = census.classify(page("quiet"))
    assert (c["repo"], c["path"]) == census.learn_source(page("quiet")) == ("github.com/MicrosoftDocs/entra-docs", "docs/identity/quiet")
    assert census.learn_source("https://example.com/en-us/entra/x") == ("", "") and not hasattr(factdiff, "LEARN_MAP")
    # a file with no commit since the baseline is unchanged with no request to Learn, and the baseline moves up
    v, signal, ev, new, got = detect(page("quiet"), **old)
    assert (v, signal, got) == ("unchanged", "git", []) and ev.startswith("source file docs/identity/quiet.md has no commit since 2026-06-01")
    assert new["detected_utc"] > old["detected_utc"] and new["doc_sha256"] == "x" and new["http_status"] == "200"
    # a planted failure for each way to the HTTP route: a commit since, a commit on the baseline's day, no baseline, no file,
    # no repository to clone, a page no map covers
    v, signal, _, _, got = detect(page("busy"), **old)
    assert (v, signal, got) == ("unchanged", "lastmod", [page("busy")])
    assert detect(page("same-day"), **{**old, "detected_utc": "2026-09-01T12:00:00Z"})[4] == [page("same-day")]
    assert detect(page("quiet"))[4] == [page("quiet")]
    assert detect(page("quiet", "entra/missing"), **old)[4] == [page("quiet", "entra/missing")]
    assert detect(page("quiet", "sql/t-sql"), **old)[4] == [page("quiet", "sql/t-sql")]
    assert detect(page("quiet", "intune/mem"), **old)[4] == [page("quiet", "intune/mem")]
    # each repository is fetched once, in parallel, before the per-host jobs
    cloned.clear()
    assert census.learn_repos([page("quiet"), page("busy"), page("x", "intune/mem")]) == ["github.com/MicrosoftDocs/entra-docs"]
    assert cloned == ["github.com/MicrosoftDocs/entra-docs"]


def census_sample_brief_agrees_a_row_of_word_for_word_facts_by_tool_and_hands_the_checker_the_rest(tmp_path, monkeypatch, capsys):
    """`census.py sample --brief` with the documents cached or stubbed: nothing reaches the network."""
    sentences = ["The service restarts on the second Tuesday of each month.", "The agent writes every restart to the event log.",
                 "An administrator may defer one restart by a week."]
    text = " ".join(sentences)
    fetched = "2099-01-02T10:00:00+00:00"
    urls = {n: f"https://docs.example.com/S999000{n}" for n in range(1, 7)}
    rows = [{**{c: "" for c in census.COLS}, "id": f"S999000{n}", "url": urls[n], "bucket": b, "outcome": o}
            for n, b, o in ((1, "OK", ""), (2, "CHANGED", "updated"), (3, "CHANGED", "superseded"), (5, "GONE", "gone"),
                            (6, "OK", "confirmed"))]
    rows[-1]["outcome_note"] = f"2 {census.JUDGED_NOTE} claude-haiku-5-5 (judge-2099-01-02.csv)"  # a source `judge` confirmed
    srcs = [{"id": f"S999000{n}", "url": urls[n], "superseded_by": "S9990004" if n == 3 else ""} for n in range(1, 7)]
    doc = factdiff.Doc(text)
    found = {s: factdiff.sha(s) for s in sentences}
    assert all(found[s] in doc.shas for s in sentences)

    def fact(n, sentence):
        return (f"k{n}", "dsc/d.md", 10 + n, f"- {sentence} [DOC S999000{n}]")

    facts = {"S9990001": [fact(1, sentences[0]), ("k1b", "dsc/d.md", 20, f"- {sentences[1]} [DOC S9990001]")],
             "S9990002": [fact(2, sentences[0]), ("k2b", "dsc/d.md", 21, "- A restart is deferred for a month. [DOC S9990002]")],
             "S9990004": [fact(4, sentences[2])],  # what replaced S9990003
             "S9990006": [fact(6, sentences[0])]}
    anchors = {(k, rel, sid): {"status": "located", "sha": found[sentences[i]], "verified_utc": "2099-01-01"}
               for sid, k, rel, i in (("S9990001", "k1", "dsc/d.md", 0), ("S9990001", "k1b", "dsc/d.md", 1),
                                      ("S9990002", "k2", "dsc/d.md", 0), ("S9990004", "k4", "dsc/d.md", 2),
                                      ("S9990006", "k6", "dsc/d.md", 0))}
    anchors[("k2b", "dsc/d.md", "S9990002")] = {"status": "located", "sha": factdiff.sha("A restart may be deferred for a month."),
                                                "verified_utc": "2099-01-01"}
    tmp_path.mkdir(parents=True, exist_ok=True)
    cache = tmp_path / "cache"
    for sid in ("S9990001", "S9990002", "S9990004"):
        path = cache / "public" / f"{sid}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"id": sid, "url": urls[int(sid[-1])], "status": 200, "text": text, "fetched_utc": fetched}), encoding="utf-8")
    log = tmp_path / "2099-01-02.csv"
    kbcommon.write_csv(str(log), census.COLS, rows)
    asked = []

    def document(url, row=None, **kw):
        asked.append(url)
        return {"status": 404, "text": None, "error": ""}

    def args(**kw):
        return argparse.Namespace(log=str(log), changed=1.0, judged=1.0, ok=1.0, seed=1, brief=True, max_age=7, **kw)

    with monkeypatch.context() as m:
        m.setattr(socket.socket, "connect", lambda *a, **k: (_ for _ in ()).throw(AssertionError("sample used the network")))
        m.setattr(kbcommon, "KB", kbcommon.PUBLIC)  # earlier steps of this test left it on a scratch root
        m.setattr(factdiff, "ROOT", kbcommon.root("public"))
        m.setattr(factdiff, "CACHE", str(cache))
        m.setattr(factdiff, "cited_facts", lambda *a: facts)
        m.setattr(factdiff, "read_anchors", lambda: anchors)
        m.setattr(census, "read_sources", lambda: srcs)
        m.setattr(census, "g", lambda *a, **k: (0, "", ""))  # no phase-1 commit: the anchors' dates decide
        m.setattr(provider, "document", document)
        capsys.readouterr()  # what the steps before printed
        tally = Counter()
        assert census.cmd_sample(args(), tally) == 0
        out = capsys.readouterr().out
        agreed, _, left = out.partition("## For the checker")
        assert "checked=5 agreed by tool=2 for the checker=3" in out and dict(tally) == {"checked": 5, "agreed by tool": 2, "for the checker": 3}
        # each group's counts apart, the judge's confirms among them: the report states their agreement on their own
        assert ("by group, each stated apart in the report: changed checked=3 agreed by tool=1 for the checker=2; "
                "judged checked=1 agreed by tool=0 for the checker=1; ok checked=1 agreed by tool=1 for the checker=0") in out
        assert "S9990006  judged, outcome confirmed, bucket OK" in left
        # every fact word for word: agreed by tool with the proof (the facts, the document read, when it was fetched); a
        # superseded row is judged by the facts of the row that replaced it, against that row's document
        assert ("S9990001  ok, outcome -, bucket OK: 2 fact(s) found word for word in the current text of https://docs.example.com/S9990001 "
                "(document S9990001, fetched 2099-01-02T10:00:00): kb/public/dsc/d.md:11, kb/public/dsc/d.md:20") in agreed
        assert "S9990003  changed, outcome superseded, bucket CHANGED: 1 fact(s) found word for word in the current text of " \
               "https://docs.example.com/S9990004 (document S9990004" in agreed
        assert "### S9990001" not in out and "### S9990003" not in out
        # one fact not found word for word keeps the row from the tool: the checker gets each fact, its passage, how it was found
        two = left.split("### ")[1]
        assert two.startswith("S9990002  changed, outcome updated, bucket CHANGED") and "(located anchor)" in two
        assert f"passage (word for word): {sentences[0]}" in two and "passage (best match): " in two
        assert "fact: - A restart is deferred for a month." in two and f"fetch {urls[2]}" in two
        # a row no fact cites (a source gone) and a page that cannot be read go to the checker whole, never agreed by tool
        assert "cited by: no fact (outcome gone)" in left and "current text: not read (HTTP 404)" in left
        assert asked == [urls[6]]  # the cache held the rest; the one fetch was of the row with no document
        assert left.count("### ") == 3
        # without --brief the same rows are a CSV of ids, as before; a missing log is exit 2
        assert census.cmd_sample(argparse.Namespace(**{**vars(args()), "brief": False}), Counter()) == 0
        listed = list(csv.DictReader(capsys.readouterr().out.splitlines()))
        assert [(r["group"], r["id"]) for r in listed] == [("changed", "S9990002"), ("changed", "S9990003"), ("changed", "S9990005"),
                                                          ("judged", "S9990006"), ("ok", "S9990001")]
        assert census.cmd_sample(argparse.Namespace(**{**vars(args()), "log": str(tmp_path / "none.csv")}), Counter()) == 2


def census_sample_brief_agrees_by_tool_only_before_phase2_edits(tmp_path, monkeypatch, capsys):
    """An anchor dated the census day agrees a fact by tool only when the phase-1 commit held the fact's line; a rewrite
    of phase 2 goes to the checker with its passage, whatever its anchor finds."""
    sentence = "The service restarts on the second Tuesday of each month."
    rewrite = "- The service restarts on the second Tuesday of every month. [DOC S9990003]"
    text = f"{sentence} The agent writes every restart to the event log."
    urls = {n: f"https://docs.example.com/S999000{n}" for n in (1, 2, 3)}
    held = f"- {sentence} [DOC S9990002]\n"  # the article as the phase-1 commit held it
    key_held = {kbfacts.fact_key(u["text"]) for u in kbfacts.md_units("dsc/d.md", held)}
    assert len(key_held) == 1
    facts = {"S9990001": [("k1", "dsc/d.md", 3, f"- {sentence} [DOC S9990001]")],
             "S9990002": [(next(iter(key_held)), "dsc/d.md", 4, held.strip())],
             "S9990003": [(kbfacts.fact_key(rewrite), "dsc/d.md", 5, rewrite)]}
    on = {"S9990001": "2099-01-01", "S9990002": "2099-01-02", "S9990003": "2099-01-02"}
    anchors = {(f[0][0], "dsc/d.md", sid): {"status": "located", "sha": factdiff.sha(sentence), "verified_utc": on[sid]}
               for sid, f in facts.items()}
    cache = tmp_path / "cache"
    for n, url in urls.items():
        path = cache / "public" / f"S999000{n}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"id": f"S999000{n}", "url": url, "status": 200, "text": text,
                                    "fetched_utc": "2099-01-02T10:00:00+00:00"}), encoding="utf-8")
    log = tmp_path / "2099-01-02.csv"
    kbcommon.write_csv(str(log), census.COLS, [{**{c: "" for c in census.COLS}, "id": f"S999000{n}", "url": url, "bucket": "OK"}
                                              for n, url in urls.items()])
    srcs = [{"id": f"S999000{n}", "url": url, "superseded_by": ""} for n, url in urls.items()]
    asked, commit = [], ["c0ffee"]

    def git(d, *argv, **kw):
        asked.append(argv)
        if argv[0] == "log":
            return 0, commit[0], ""
        return (0, held, "") if argv[:2] == ("cat-file", "blob") and argv[2].startswith("c0ffee:") else (128, "", "bad object")

    def brief():
        asked.clear()
        capsys.readouterr()
        assert census.cmd_sample(argparse.Namespace(log=str(log), changed=1.0, judged=1.0, ok=1.0, seed=1, brief=True, max_age=7),
                                 Counter()) == 0
        return capsys.readouterr().out

    with monkeypatch.context() as m:
        m.setattr(socket.socket, "connect", lambda *a, **k: (_ for _ in ()).throw(AssertionError("sample used the network")))
        m.setattr(kbcommon, "KB", kbcommon.PUBLIC)
        m.setattr(factdiff, "ROOT", kbcommon.root("public"))
        m.setattr(factdiff, "CACHE", str(cache))
        m.setattr(factdiff, "cited_facts", lambda *a: facts)
        m.setattr(factdiff, "read_anchors", lambda: anchors)
        m.setattr(census, "read_sources", lambda: srcs)
        m.setattr(census, "g", git)
        # a day-old anchor and a same-day anchor of a line the phase-1 commit held agree by tool; the rewrite goes to the
        # checker with the passage its anchor names, which is no proof
        out = brief()
        agreed, _, left = out.partition("## For the checker")
        assert "checked=3 agreed by tool=2 for the checker=1" in out
        assert "S9990001  ok" in agreed and "S9990002  ok" in agreed and "S9990003" not in agreed
        assert left.count("### ") == 1 and left.split("### ")[1].startswith("S9990003  ok")
        assert f"fact: {rewrite.split(' [')[0]}" in left and f"passage (anchor placed in phase 2): {sentence}" in left
        assert ("log", "-1", "--format=%H", "--fixed-strings", "--grep=census 2099-01-02 phase 1 verdicts") in asked
        assert [a for a in asked if a[0] == "cat-file"] == [("cat-file", "blob", "c0ffee:kb/public/dsc/d.md")]
        # no phase-1 commit in the history: only the anchor of an earlier day is a tool's proof
        commit[0] = ""
        out = brief()
        assert "checked=3 agreed by tool=1 for the checker=2" in out
        assert "S9990001  ok" in out.partition("## For the checker")[0] and out.count("passage (anchor placed in phase 2)") == 2


def census_sample_draws_judged_confirms_as_a_group_of_their_own_at_the_changed_rate(tmp_path, capsys):
    """The sources `judge` confirmed are a sample group of their own (`judged`) at `--judged`, apart from `ok`."""
    note = f"3 {census.JUDGED_NOTE} claude-haiku-5-5 (judge-2099-01-02.csv)"
    spec = [("J", "CHANGED", "confirmed", note, 100), ("K", "OK", "confirmed", "read in full", 20), ("O", "OK", "", "", 20),
            ("C", "CHANGED", "updated", "", 30)]
    rows = [{**{c: "" for c in census.COLS}, "id": f"S9{kind}{n:04d}", "url": f"https://docs.example.com/{kind}{n}", "bucket": b,
             "outcome": o, "outcome_note": nt} for kind, b, o, nt, count in spec for n in range(count)]
    tmp_path.mkdir(parents=True, exist_ok=True)
    log = tmp_path / "2099-01-02.csv"
    kbcommon.write_csv(str(log), census.COLS, rows)
    args = argparse.Namespace(log=str(log), changed=0.10, judged=0.10, ok=0.05, seed=1, brief=False)
    got = census.sampled(rows, args)
    by = Counter(g for g, _ in got)
    # a judged confirm is drawn at 0.10 of its own, never from the ok group: 10 of 100 judged, 3 of 30 changed, and 0.05 of the
    # 40 other confirmed and unchanged rows
    assert by == {"changed": 3, "judged": 10, "ok": 2}
    assert all(r["id"].startswith("S9J") for g, r in got if g == "judged")
    assert not any(r["id"].startswith("S9J") for g, r in got if g == "ok")
    # the flag sets the rate, and a group is never empty while it has a row
    assert Counter(g for g, _ in census.sampled(rows, argparse.Namespace(**{**vars(args), "judged": 0.5, "ok": 0.0}))) \
        == {"changed": 3, "judged": 50, "ok": 1}
    capsys.readouterr()
    assert census.cmd_sample(args, Counter()) == 0
    listed = list(csv.DictReader(capsys.readouterr().out.splitlines()))
    assert Counter(r["group"] for r in listed) == by and list(by) == ["changed", "judged", "ok"]


PARALLEL_ADD = (
    "import os, sys, time, types\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "import kbid\n"
    "root = types.SimpleNamespace(path=sys.argv[2], name='public', id_prefix='S')\n"
    "while not os.path.exists(sys.argv[3]):\n"
    "    time.sleep(0.001)\n"
    "for n in range(int(sys.argv[5])):\n"
    "    kbid.add_source(root, f'https://docs.example.com/w{sys.argv[4]}/p{n}', 'Page', 'Example', 'MIT', 'copy',\n"
    "                    today='2026-10-13')\n")


def kbid_parallel_add_keeps_every_row_and_leaves_no_torn_one(tmp_path):
    """Writers started at one signal each add several sources to one _sources.csv: every row is there once, the file
    parses whole and in id order, and no lock or temporary file is left; a lock a crashed add left is cleared."""
    root = tmp_path / "public"
    root.mkdir(parents=True)
    cols = ["id", "url", "title", "publisher", "licence", "reuse", "retrieved_utc", "version_or_date", "artifact_sha256",
            "used_in", "superseded_by"]
    old = {c: "" for c in cols} | {"id": "S100", "url": "https://docs.example.com/old", "title": "Old",
                                   "publisher": "Example", "licence": "MIT", "reuse": "copy", "retrieved_utc": "2026-09-26"}
    sources = root / "_sources.csv"
    kbcommon.write_csv(str(sources), cols, [old])
    go, writers, each = tmp_path / "go", 6, 8  # `go` is outside the root: the root lists only its own files
    procs = [subprocess.Popen([sys.executable, "-c", PARALLEL_ADD, TOOLS, str(root), str(go), str(w), str(each)],
                              stderr=subprocess.PIPE, text=True, encoding="utf-8") for w in range(writers)]
    go.write_text("go", encoding="utf-8")
    for p in procs:
        assert p.wait(timeout=120) == 0, p.stderr.read()
    rows = list(csv.DictReader(sources.open(encoding="utf-8", newline="")))
    want = {"https://docs.example.com/old"} | {f"https://docs.example.com/w{w}/p{n}" for w in range(writers) for n in range(each)}
    assert len(rows) == len(want) and {r["url"] for r in rows} == want
    assert all(r["id"] and r["title"] and r["retrieved_utc"] and None not in r for r in rows)
    assert kbid.check_sources(rows) == [] and [r["id"] for r in rows] == sorted((r["id"] for r in rows), key=kbid.sort_key)
    assert sorted(f.name for f in root.iterdir()) == ["_sources.csv"]
    # a lock file a crashed add left, older than the bound, is cleared; a lock nobody holds is no reason to refuse
    stale = root / "_sources.csv.lock"
    stale.write_text("pid=1\nstarted=2026-10-01T00:00:00Z\n", encoding="utf-8")
    os.utime(stale, (1, 1))
    ns = types.SimpleNamespace(path=str(root), name="public", id_prefix="S")
    assert kbid.add_source(ns, "https://docs.example.com/after", "Page", "Example", "MIT", "copy")[1] is True
    assert not stale.exists() and len(list(csv.DictReader(sources.open(encoding="utf-8", newline="")))) == len(want) + 1


def test_census_queue_and_census_groups_are_sized_without_network_each_phase_writes_one_ops_row_and_census_run_and_finish_stop_at_a_failing_step_and_census_apply_refuses_a_bad_result_and_census_retry_tries_a_name_resolution_or_connection_error_once_and_census_baseline_decides_a_page_with_no_date_and_census_repin_writes_the_new_row_only_when_every_cited_fact_is_word_for_word_and_census_judge_confirms_a_source_whose_facts_are_all_supported_and_leaves_the_rest_to_groups_and_census_github_page_signals_decide_a_page_without_a_reader_and_factdiff_learn_git_decides_a_mapped_learn_page_by_its_repository_history_and_factdiff_anchor_locates_a_data_row_on_its_values_not_its_column_names_and_census_sample_brief_agrees_a_row_of_word_for_word_facts_by_tool_and_hands_the_checker_the_rest_and_census_sample_brief_agrees_by_tool_only_before_phase2_edits_and_census_sample_draws_judged_confirms_as_a_group_of_their_own_at_the_changed_rate_and_census_dispatch_runs_a_group_as_a_capped_headless_session_and_writes_the_result_apply_takes_and_census_dispatch_refuses_in_a_worktrees_checkout_and_census_brief_carries_phase2_rules_that_hold_throughout_and_kbid_parallel_add_keeps_every_row_and_leaves_no_torn_one(tmp_path, monkeypatch, capsys):
    kbid_parallel_add_keeps_every_row_and_leaves_no_torn_one(tmp_path / "kbid_parallel")
    census_github_page_signals_decide_a_page_without_a_reader(tmp_path / "ghpage", monkeypatch)
    census_dispatch_runs_a_group_as_a_capped_headless_session_and_writes_the_result_apply_takes(tmp_path / "dispatch", monkeypatch, capsys)
    census_dispatch_refuses_in_a_worktrees_checkout(tmp_path / "worktrees", monkeypatch, capsys)
    factdiff_learn_git_decides_a_mapped_learn_page_by_its_repository_history_and_asks_learn_for_the_rest(tmp_path / "learngit", monkeypatch)
    census_repin_writes_the_new_row_only_when_every_cited_fact_is_word_for_word_at_the_newer_commit(tmp_path / "repin", monkeypatch, capsys)
    census_retry_tries_a_name_resolution_or_connection_error_once_and_notes_it_apart_from_blocked(tmp_path, monkeypatch, capsys)
    census_queue_is_sized_without_network(tmp_path, monkeypatch)
    census_groups_split_the_queue_by_owner_and_brief_fills_each_group_in(tmp_path, monkeypatch, capsys)
    census_phases_write_one_ops_row_each(tmp_path)
    census_judge_confirms_a_source_whose_facts_are_all_supported_and_leaves_the_rest_to_groups(tmp_path / "judge", monkeypatch, capsys)
    census_apply_refuses_a_bad_result_and_writes_a_good_one_through_kbid(tmp_path / "apply", monkeypatch, capsys)
    census_baseline_is_written_from_a_compared_document_and_decides_a_page_with_no_date_at_the_next_census(tmp_path / "baseline", monkeypatch, capsys)
    census_sample_brief_agrees_a_row_of_word_for_word_facts_by_tool_and_hands_the_checker_the_rest(tmp_path / "sample", monkeypatch, capsys)
    census_sample_brief_agrees_by_tool_only_before_phase2_edits(tmp_path / "phase2", monkeypatch, capsys)
    census_sample_draws_judged_confirms_as_a_group_of_their_own_at_the_changed_rate(tmp_path / "judged", capsys)
    census_run_and_finish_stop_at_a_failing_step_and_refuse_a_foreign_change(tmp_path, monkeypatch, capsys)

    # a data row is anchored on its values, never its column names; a row whose own name is not on the page stays unlocated
    page = factdiff.Doc("## Variables\n\n### SMSInstallUpdateTarget\n\nApplies to the Install Software Updates step.\n\n"
                        "Specifies whether the step installs all updates or only the mandatory ones.\n\n"
                        "## Other\n\n" + " ".join(f"word{i}" for i in range(80)) + " target install updates mandatory.")
    row = ("variable=SMSInstallUpdateTarget; read_only_or_settable=settable (input); type=string; default=(none); "
           "purpose=Install Software Updates step target: All or Mandatory.; source_id=S-lydse5ww")
    assert factdiff.row_parts("a plain sentence; not a row") is None
    values, ident = factdiff.row_parts(row)
    assert "settable" in values and "read_only_or_settable" not in values and "S-lydse5ww" not in values
    win, _cover, _shared = page.locate(row, 1)
    assert win is not None and "SMSInstallUpdateTarget" in page.units[win[0]][0] + " ".join(u for _, u in page.units[win[0]:win[0] + win[1]])
    other = row.replace("SMSInstallUpdateTarget", "OSDDomainName")
    assert page.locate(other, 1)[0] is None  # the row's own name is not on the page: no anchor, never a guess
