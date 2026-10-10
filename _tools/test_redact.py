"""Redaction and the query log's privacy guards: redact.py's rules, what distill stores of a captured prompt, the closed
shape of an ops row, the store check that blocks a leak, and apply's rule for a weak rules miss over the fixture store.
Planted values are assembled at run time."""
import argparse, csv, hashlib, json, os, re, shutil, socket, subprocess, sys, types, urllib.error
from collections import Counter
from pathlib import Path

import pytest

import census, factdiff, kbcommon, kbfacts, kbid, provider, ql_apply, ql_capture, ql_distill, ql_learn, ql_report, ql_store, redact
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
        return {"n": 1, "passed": 1, "failed": [], "chars": {"EV-x": 100}, "offkb_good": 0}

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


def test_apply_keeps_a_lead_that_does_not_answer_no_fix_and_cuts_the_anchor_from_the_printed_text(tmp_path):
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
    # the lead that answers is applied, its phrase cut from what the pack prints of the line, not from the whole line
    rec, human = ql_apply.rules_one(weak, {"question": asked}, gate, {"chars": {"EV-x": 100}, "offkb_good": 0})
    assert not human and rec["state"] == "applied"
    with open(gate.eval, encoding="utf-8", newline="") as f:
        phrase = list(csv.reader(f))[1][5]
    assert phrase in shown and phrase in line
    # a failed row names why it failed
    gate.eval.unlink()
    gate.measure = lambda: {"n": 2, "passed": 1, "failed": ["SQ-x"], "why": {"SQ-x": ["text"]}, "chars": {"EV-x": 100}, "offkb_good": 0}
    rec, _ = ql_apply.rules_one(weak, {"question": asked}, gate, {"chars": {"EV-x": 100}, "offkb_good": 0})
    assert rec["state"] == "no-fix" and rec["observed"] == {"gate": ["eval fails: SQ-x (text)"]}


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
        m.setattr(census, "reading_queue", lambda rows, fd_rows: [])  # the queue block is another test's
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


def test_census_queue_and_census_groups_are_sized_without_network_each_phase_writes_one_ops_row_and_census_run_and_finish_stop_at_a_failing_step_and_census_apply_refuses_a_bad_result_and_census_retry_tries_a_name_resolution_or_connection_error_once_and_census_baseline_decides_a_page_with_no_date_and_census_repin_writes_the_new_row_only_when_every_cited_fact_is_word_for_word_and_census_github_page_signals_decide_a_page_without_a_reader(tmp_path, monkeypatch, capsys):
    census_github_page_signals_decide_a_page_without_a_reader(tmp_path / "ghpage", monkeypatch)
    census_repin_writes_the_new_row_only_when_every_cited_fact_is_word_for_word_at_the_newer_commit(tmp_path / "repin", monkeypatch, capsys)
    census_retry_tries_a_name_resolution_or_connection_error_once_and_notes_it_apart_from_blocked(tmp_path, monkeypatch, capsys)
    census_queue_is_sized_without_network(tmp_path, monkeypatch)
    census_groups_split_the_queue_by_owner_and_brief_fills_each_group_in(tmp_path, monkeypatch, capsys)
    census_phases_write_one_ops_row_each(tmp_path)
    census_apply_refuses_a_bad_result_and_writes_a_good_one_through_kbid(tmp_path / "apply", monkeypatch, capsys)
    census_baseline_is_written_from_a_compared_document_and_decides_a_page_with_no_date_at_the_next_census(tmp_path / "baseline", monkeypatch, capsys)
    census_run_and_finish_stop_at_a_failing_step_and_refuse_a_foreign_change(tmp_path, monkeypatch, capsys)
