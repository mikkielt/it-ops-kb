"""Redaction and the query log's privacy guards: redact.py's rules, what distill stores of a captured prompt, the closed
shape of an ops row, the store check that blocks a leak, and apply's rule for a weak rules miss over the fixture store.
Planted values are assembled at run time."""
import csv, json, os, shutil, socket, subprocess, sys
from pathlib import Path

import pytest

import census, factdiff, kbcommon, kbfacts, ql_apply, ql_capture, ql_distill, ql_learn, ql_report, ql_store, redact
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
        "step 1/6 detect", "step 2/6 apply", "step 3/6 check", "step 4/6 index", "step 5/6 commit", "step 6/6 summary"]
    assert "factdiff.py detect --date 2099-01-02 --sitemaps" in text and "apply kb/public/_census/factdiff-2099-01-02.csv" in text
    assert "--factdiff kb/public/_census/factdiff-2099-01-02.csv" in text and "--trailer" not in text
    # every step runs in order; detect's exit 1 is no failure; the run ends with the summary
    go("run", "--date", "2099-01-02")
    assert seen == ["detect", "apply", "check", "index", "commit", "summary"]
    # planted failure: check exits 3: the run stops with that code and names the step and the command that resumes it
    text = go("run", "--date", "2099-01-02", code=3, check=3)
    assert seen == ["detect", "apply", "check"]
    assert "step 3/6 check failed with exit 3; resume from it:" in text and "run --date 2099-01-02 --resume" in text
    # --resume skips the steps whose output exists
    monkeypatch.setattr(census, "output_exists", lambda rel: "factdiff-" in rel)
    monkeypatch.setattr(census, "apply_committed", lambda log, date: True)
    text = go("run", "--date", "2099-01-02", "--resume")
    assert seen == ["check", "index", "commit", "summary"] and "step 1/6 detect: skipped" in text
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


def test_census_queue_is_sized_without_network_each_phase_writes_one_ops_row_and_census_run_and_finish_stop_at_a_failing_step(tmp_path, monkeypatch, capsys):
    census_queue_is_sized_without_network(tmp_path, monkeypatch)
    census_phases_write_one_ops_row_each(tmp_path)
    census_run_and_finish_stop_at_a_failing_step_and_refuse_a_foreign_change(tmp_path, monkeypatch, capsys)
