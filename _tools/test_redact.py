"""Redaction and the query log's privacy guards: redact.py's rules, what distill stores of a captured prompt, the closed
shape of an ops row and the store check that blocks a leak.
Planted values are assembled at run time."""
import csv, json, os, re, shutil, subprocess, sys
from pathlib import Path

import pytest

import kb_hook, kb_mcp, kbcommon, kbfacts, ql_capture, ql_distill, ql_learn, ql_store, redact
from conftest import KB, TOOLS

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
VALUE = "Fake" + "Pass12345x"
SHORT = "Fk" + "12ab"
Q = chr(34)
BS = chr(92)
ASSIGNMENTS = ["password=" + VALUE, "passwd: " + VALUE, "pwd=" + SHORT, "secret=" + VALUE,
               "{" + Q + "client_secret" + Q + ": " + Q + VALUE + Q + "}", "DB_PASSWORD=" + VALUE, "api_key=" + VALUE,
               "apikey: " + VALUE, "x-api-key: " + VALUE, "https://api.example.com/v1?api_key=" + VALUE + "&page=2",
               "aws_secret_access_key=" + VALUE + "/x+y", "access_key=" + VALUE,
               "Server=db.example.com;Password=" + VALUE + ";"]
PLACEHOLDER_VALUES = ["password=<secret>", "password=${DB_PASS}", "password=%DB_PASS%", "password=***",
                      "Authorization: Bearer <token>", "postgres://fakeuser:${DB_PASS}@db.example.com/app"]
BASIC = "ZmFr" + "ZTpmYWtl"
KEY_BODY = "MIIfake" + "FAKEfake"
KEY_BLOCK = "-----BEGIN " + "PRIVATE KEY-----\n" + KEY_BODY + "\n-----END " + "PRIVATE KEY-----"
SHAPES = {"bearer": ("Authorization: Bearer " + VALUE, VALUE), "basic": ("Authorization: Basic " + BASIC, BASIC),
          "userinfo": ("postgres://fakeuser:" + VALUE + "@db.example.com:5432/app", VALUE),
          "$word bearer": ("Authorization: Bearer $" + VALUE, VALUE),
          "$word userinfo": ("postgres://fakeuser:$" + VALUE + "@db.example.com/app", VALUE),
          "$word assignment": ("password=$" + VALUE, VALUE),
          "placeholder-prefixed assignments": ("password=%x%y" + VALUE + "\npassword=***" + VALUE + "\npassword=<a>" + VALUE, VALUE),
          "escaped JSON assignment": ("{" + BS + Q + "password" + BS + Q + ": " + BS + Q + VALUE + BS + Q + "}", VALUE),
          "escaped JSON header": ("{" + BS + Q + "Authorization" + BS + Q + ": " + BS + Q + "Bearer " + VALUE + BS + Q + "}", VALUE),
          "subscripted header": ("headers['Authorization'] = 'Bearer " + VALUE + "'", VALUE),
          "escaped quote in a value": ("password=" + Q + "Fa" + BS + Q + "kePass12345x" + Q, "kePass12345x"),
          "key body": ("before\n" + KEY_BLOCK + "\nafter", KEY_BODY),
          "cut-off key": ("before\n-----BEGIN " + "PRIVATE KEY-----\n" + KEY_BODY + "\nmore lines", KEY_BODY)}
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
    done = redact.redact("\n".join(ASSIGNMENTS))  # each assignment form loses its value, whatever its length, and keeps its key
    assert VALUE not in done and SHORT not in done and done.count("<secret>") == len(ASSIGNMENTS), done
    for key in ("passwd", "client_secret", "x-api-key", "aws_secret_access_key", "Password=", "DB_PASSWORD"):
        assert key in done, key
    assert redact.redact(done) == done
    for kind, (text, value) in SHAPES.items():  # header credentials, a URL's password and a key block's body go, whatever the length
        shaped = redact.redact(text)
        assert value not in shaped and "<secret>" in shaped, kind
        assert redact.redact(shaped) == shaped, kind
    assert "fakeuser:<secret>@db.example.com" in redact.redact(SHAPES["userinfo"][0])
    assert redact.redact(SHAPES["key body"][0]) == "before\n<secret>\nafter"
    assert redact.redact(SHAPES["cut-off key"][0]) == "before\n<secret>"
    assert redact.redact("\n".join(PLACEHOLDER_VALUES)) == "\n".join(PLACEHOLDER_VALUES)
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
    monkeypatch.setenv("KB_COORD_TOOLS", "1")  # the coord_ tools are listed only when the server is started with it
    listed = kb_mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
    tool = next(t for t in listed if t["name"] == "kb_feedback")
    assert tool["annotations"] == {"title": tool["title"], "readOnlyHint": False, "destructiveHint": False,
                                   "idempotentHint": True, "openWorldHint": False}
    assert all(t["annotations"]["readOnlyHint"] for t in listed if t["name"] != "kb_feedback" and not t["name"].startswith("coord_"))
    assert next(t for t in listed if t["name"] == "coord_digest")["annotations"]["readOnlyHint"]
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
    # a server limited to named roots lists no kb_feedback, so its pack prints no call for it; the hook's web route keeps both lines
    with monkeypatch.context() as limited:
        limited.setattr(kbcommon, "_SERVED", ["public"])
        bare = kbfacts.pack_many(["zqxv wlkj nmbp qrtz"], revalidate=False)
        assert bare["verdict"] == "none" and "feedback:" not in bare["text"], bare["text"]
        assert bare["text"].splitlines()[-1] == f"pack: {bare['pack']}"
    out, row = kb_hook.respond("kb: zqxv wlkj nmbp qrtz")
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert row["verdict"] == "none" and "route: web" in ctx, ctx
    assert ctx.splitlines()[-2:] == [f'feedback: kb_feedback(pack="{none["pack"]}", outcome="missed")',
                                     f"pack: {none['pack']}"], ctx


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
    prose = "note=the+docs+are+wrong+free+text"
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
              question="How do I rotate the LAPS password?", source_url=f"https://docs.example.net/laps/rotate?{prose}#{prose}")
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
    assert "free+text" not in text  # a source_url's query and fragment are dropped before the gate
    assert not list(spool.glob("*.jsonl")) and not list(spool.glob("*.end"))  # delivered rows go, as other rows
    # the gates: one planted failure for each open field of a stored report
    good = second["feedback"][1]
    assert ql_store.feedback_problems([good, alone[1]["feedback"][0]], "e") == []
    for bad in ({**good, "comment": comment}, {**good, "claim": claim}, {**good, "lines": [{"line": line, "issue": "bogus"}]},
                {**good, "lines": [{"line": "see the docs", "issue": "wrong"}]}, {**good, "best": "../outside.md"},
                {**good, "lead": "http://pl-srv-0042.corp/page"}, {**good, "outcome": "fine"}, {**good, "judged_by": "bot"},
                {**good, "lead": f"https://learn.microsoft.com/en-us/intune/page?{prose}#more+free+text"},
                {**good, "lead": "https://learn.microsoft.com/en-us/intune/page#more"},
                {**good, "lead": "https://docs.example.net/p/api_" + "key=" + "hunter" + "2xFake"}):  # a secret in the path
        assert ql_store.feedback_problems([bad], "e"), bad
    secret_url = "https://docs.example.net/p/api_" + "key=" + "hunter" + "2xFake"
    kept = ql_distill.feedback_report({"outcome": "misled", "source_url": secret_url}, None, ql_learn.KbPages())
    assert kept["lead"] is None and "2xFake" not in str(kept)  # distill keeps no lead redact would change
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
