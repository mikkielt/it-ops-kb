"""Redaction and the query log's privacy guards: redact.py's rules, what distill stores of a captured prompt, the closed
shape of an ops row, and the store check that blocks a leak. Planted values are assembled at run time."""
import json, os, shutil, subprocess, sys
from pathlib import Path

import pytest

import ql_capture, ql_distill, ql_store, redact
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


def test_redact_replaces_every_class_of_value_and_a_second_pass_changes_nothing():
    out = redact.redact(TEXT)
    for kind, value in PLANTED.items():
        assert value not in out, kind
    for placeholder in ("<secret>", "jan.kowalski@corp.example.com", redact.PLACEHOLDERS["ipv4"],
                        redact.PLACEHOLDERS["guid"], redact.PLACEHOLDERS["host"], redact.PLACEHOLDERS["computer"]):
        assert placeholder in out, placeholder
    assert redact.redact(out) == out
    assert redact.scan(out) == []


def test_redact_leaves_ordinary_text_and_placeholders_as_they_are():
    assert redact.redact(ORDINARY) == ORDINARY


def test_redact_scan_exits_1_on_a_leak_and_0_on_ordinary_text(tmp_path, capsys):
    f = tmp_path / "in.txt"
    f.write_text(TEXT, encoding="utf-8", newline="\n")
    assert redact.main(["--scan", str(f)]) == 1
    assert "email\t" + EMAIL in capsys.readouterr().out
    f.write_text(ORDINARY, encoding="utf-8", newline="\n")
    assert redact.main(["--scan", str(f)]) == 0


def test_distill_stores_a_captured_prompt_and_answer_redacted(tmp_path, monkeypatch):
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
         "tool_response": [{"type": "text", "text": PACK}]},
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


def test_an_ops_row_has_a_closed_shape_and_a_free_text_value_is_refused(tmp_path, monkeypatch):
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
    finally:
        ql_capture.spool_dir.cache_clear()


def test_store_check_passes_a_clean_store_and_names_the_run_file_with_a_leak(tmp_path, capsys):
    store = tmp_path / "store"
    shutil.copytree(FIXTURE_STORE, store)
    assert ql_store.check(str(store)) == 0  # `querylog.py check DIR` is this function
    assert capsys.readouterr().out == "querylog check: problems=0\n"
    run = store / RUN_REL
    lines = run.read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[1])
    entry["question"] = f"How long is the LAPS password for {EMAIL}?"
    lines[1] = json.dumps(entry)
    run.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    assert ql_store.check(str(store)) == 1
    out = capsys.readouterr().out
    assert RUN_REL in out and "question" in out and EMAIL not in out, out
