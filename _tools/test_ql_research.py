"""Query log tests, research (kb/_self/querylog.md, Research; `python3 _tools/tests.py -k TestGapStep`, and the
other classes below).

  TestGapStep      a reproduced gap candidate with an article in the pack's lead becomes a dated _gaps.md entry at
                    the end of its topic's section (or a new section), once, the finding promoted candidate-gap ->
                    gap, a none pack's too when its lead holds more than half the key words; off the kb's domains
                    (no lead, a lead no article holds, a stray none lead) it is rejected; a pass now, or a none lead
                    that holds the words the pack lacks, is left to learn, which makes the second an eval finding, so
                    no gap candidate is stranded and the digest's open gaps are what the queue reaches
  TestQueue         the research queue on the gap step's entries (two topics): one item per question, ranked by the
                    logged lookups that asked it, then by age, grouped by topic, the top N; two copies of one store print the
                    same queue; a gap the pack answers now is recorded `fixed-since` and leaves it (learn leaves that
                    record); a second queue after `close --claim` omits the closed gap and changes nothing; planted: a
                    later record reopening a closed gap (check and queue fail), a closed gap whose entry lost its
                    Resolved note, `--claim` without one; a tried note younger than QUEUE_TRIED_DAYS waits and an
                    older one is queued; the close records pass `check`; close refuses what is no open gap; `close
                    --reject` refuses an entry still in the ledger, then records a gap whose entry was removed
                    rejected at candidate-gap, no longer open, and the gap step and queue leave it
  TestCloseCommit   `close --commit` commits the findings record alone, with the session's trailers and no KB-Work
                    trailer, leaving the _gaps.md note and what was staged out of it; planted: the record committed
                    the old way under a research task's KB-Work trailer, and a KB-* or malformed --trailer, or one
                    without --commit, refused before anything is written
  TestQuoteCheck    quotecheck on a recorded page: entities, no-break spaces, curly quotes, links and emphasis
                    normalized; planted: a quote not on its page, page chrome, over 25 or under 5 words, a page that
                    cannot be fetched; the default fetcher is fetch.py's; the command line
  TestResearchConfig  research is off without the config file and fails closed on a bad one; the daily cap counts
                    runs per day, and mode off or the DISABLED marker turns research off
  TestResearch      with stub gates on a one-article root: facts and source rows added, a disagreement to
                    _conflicts.md, the finding promoted gap -> candidate-fact -> claim; planted: a quote not on its
                    page, research editing an existing fact line, a red check.py (every file put back); at most the
                    runs left; a failed call writes nothing; a reply that is not the JSON; candidate and edit gates
  TestResearchInKbCopy  in a kb copy, learn then apply with research off (the gap entry only), then on at one run a day
                    (recorded reply and page): a fact, a source row and a conflict entry, check.py errors=0 and
                    build_index --check after it, and a second run changes nothing
Every run writes under a temporary plugin data directory (conftest.querylog_env), never the clone's own spool, and no
test calls the real `claude`: Haiku is the recorded reply file or a stub. The helpers the classes share are in
ql_testkit.py.
"""
import datetime, json, os, re, shutil, subprocess, sys
from pathlib import Path

import pytest

import querylog, ql_apply, ql_base, ql_learn, ql_report, ql_research, ql_store
from conftest import copy_kb, git_env, KB, querylog_env, Repo, requires_git
from ql_testkit import (BAD_QUOTE, by_id, cand, E, failing, findings, GOOD_QUOTE, jsonl, LAPS, LAPS_GAP_Q, learn_store,
                        LEGACY_QUOTE, none_entry, PAGE, PAGE_URL, passing, plant_entries, QL, reply, run_learn,
                        tree)
from ql_testkit import staging_planted  # noqa: F401  (autouse: the planted registry and routes table)


DAY = "2026-09-28"
GAP_ID = ql_store.finding_id("gap", E("a4"))
ARTICLE_MD = """---
topic: windows/laps
priority: P1
applies_to: [windows]
retrieved_utc: 2026-09-01
sources: [S100, S101]
status: complete
---

# Windows LAPS

## Summary

A test article.

## Facts

- Windows LAPS keeps the managed account's password in the directory. [DOC S100]
- The default password length is 14 characters. [DOC S101]

## Reference

- None.
"""
SOURCES_CSV = ("id,url,title,publisher,licence,reuse,retrieved_utc,version_or_date,artifact_sha256,used_in,superseded_by\n"
               "S100,https://docs.example.com/laps/overview,LAPS overview,Example Docs,CC BY 4.0,copy,2026-09-01,,,"
               "windows/laps.md,\n"
               "S101,https://docs.example.com/laps/policy,LAPS policy,Example Docs,CC BY 4.0,copy,2026-09-01,,,"
               "windows/laps.md,\n")
GAPS_MD = ("# Gaps\n\n## windows/laps\n\n- **An older entry.** Looked somewhere. (topic: windows/laps)\n\n"
           "## other/topic\n\n- **Another entry.** Elsewhere. (topic: other/topic)\n")


def pages(url):
    if url != PAGE_URL:
        raise OSError(f"no recorded page for {url}")
    return PAGE.read_bytes(), "text/html; charset=utf-8"


class KbGate(ql_apply.Gate):
    """The gap step's and research's gate on a one-article root in a temporary directory: pack leads with that
    article (`res`), build_index and check.py stubbed (`checks` are their problems), the eval set unchanged."""

    def __init__(self, root, res=None, checks=()):
        self.dir, self.checks, self.indexed = Path(root), list(checks), 0
        self.res = res or {"verdict": "weak", "paths": [LAPS, "public/windows/gmsa.md"], "missing": []}

    def fresh(self):
        pass

    def pack(self, question):
        return self.res

    def article_of(self, path):
        return path if path == LAPS else None

    def topic(self, article):
        return "windows/laps"

    def unit_words(self, article, words):
        """The words of `words` each fact of the stubbed `facts` holds, with the stubbed title in every one (as the
        pack's units hold their article's file name and title)."""
        import kbfacts
        title = set(kbfacts.terms(self.title(article)))
        return [(title | set(kbfacts.terms(text))) & set(words) for _, text in self.facts(article)]

    def ledger(self, article, name):
        return self.dir / name

    def file(self, article):
        return self.dir / "windows" / "laps.md"

    def id_prefix(self, article):
        return "S"

    def index_and_check(self):
        self.indexed += 1
        return list(self.checks)

    def measure(self):
        return {"n": 1, "passed": 1, "failed": [], "chars": {"EV-a": 100}, "offkb_good": 0}


def kb_root(d, gaps=GAPS_MD):
    d = Path(d)
    (d / "windows").mkdir(parents=True, exist_ok=True)
    for name, text in (("windows/laps.md", ARTICLE_MD), ("_sources.csv", SOURCES_CSV), ("_gaps.md", gaps),
                       ("_conflicts.md", "# Conflicts\n")):
        (d / name).write_text(text, encoding="utf-8", newline="\n")
    return d


def root_files(d):
    return {p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(Path(d).rglob("*")) if p.is_file()}


def gap_store(tmp_path, extra=()):
    """The fixture store after one learn in which only a4 (and the `extra` entries, copies of a4 with other ids, each
    `n` or `(n, question, day)`) still fail: open gap candidates, the evals fixed since."""
    store = learn_store(tmp_path)
    (p,) = ql_store.run_files(store)
    objs = jsonl(p)
    a4 = next(o for o in objs if o.get("id") == E("a4"))
    for x in extra:
        n, q, day = (x, None, None) if isinstance(x, str) else x
        objs.append({**a4, "id": E(n), "question": q or f"{a4['question']} ({n})", "day": day or a4["day"]})
    objs[0]["counts"]["entries"] = len(objs) - 1
    p.write_text("".join(json.dumps(o, separators=(",", ":")) + "\n" for o in objs), encoding="utf-8", newline="\n")
    run_learn(store, lambda q: failing(q) if "VMware" in q else passing(q))
    return store


def run_gap_apply(store, gate, research=None):
    said = []
    rc = ql_apply.apply(store, gate=gate, kb_commit="0" * 40, out=said.append, research=research, day=DAY)
    return rc, said


class TestGapStep:
    def test_a_reproduced_gap_becomes_an_entry_under_its_topic(self, tmp_path):
        root = kb_root(tmp_path / "root")
        store = gap_store(tmp_path)
        rc, said = run_gap_apply(store, KbGate(root))
        assert rc == 0 and "gaps=1" in said[0] and "applied=1" in said[0], said
        text = (root / "_gaps.md").read_text(encoding="utf-8")
        lines = text.split("\n")
        at = lines.index("- **An older entry.** Looked somewhere. (topic: windows/laps)")
        new = lines[at + 1]  # at the end of its topic's section, before the next section
        assert new.startswith("- **How do I configure VMware Horizon instant clone pools?** ") and lines[at + 3] == \
            "## other/topic"
        assert new.endswith("(topic: windows/laps)") and f"Looked in the kb {DAY}" in new and GAP_ID in new
        assert ql_research.edit_problems("_gaps.md", GAPS_MD, text) == []  # added, nothing edited
        rec = by_id(store)[GAP_ID]
        assert (rec["state"], rec["stage"], rec["article"]) == ("applied", "gap", LAPS)
        assert rec["promotions"] == [{"from": "miss", "to": "candidate-gap", "by": "learn"},
                                     {"from": "candidate-gap", "to": "gap", "by": "apply"}]
        assert ql_store.store_problems(store) == []
        first = tree(store), root_files(root)
        assert run_gap_apply(store, KbGate(root)) == (0, ["apply: nothing to apply"])  # converges
        assert (tree(store), root_files(root)) == first

    def test_a_topic_without_a_section_gets_one(self, tmp_path):
        old = "# Gaps\n\n## other/topic\n\n- **Another entry.** x. (topic: other/topic)\n"
        root = kb_root(tmp_path / "root", gaps=old)
        run_gap_apply(gap_store(tmp_path), KbGate(root))
        text = (root / "_gaps.md").read_text(encoding="utf-8")
        assert text.startswith(old + "\n## windows/laps\n\n- **How do I configure VMware Horizon instant clone pools?**")
        assert text.endswith("(topic: windows/laps)\n") and text.count("\n") == old.count("\n") + 4

    def test_an_entry_is_written_once(self, tmp_path):
        root = kb_root(tmp_path / "root")
        store = gap_store(tmp_path)
        run_gap_apply(store, KbGate(root))
        text = (root / "_gaps.md").read_bytes()
        ql_store.findings_files(store)[-1].unlink()  # the record is gone (a lost run), the entry is there
        run_gap_apply(store, KbGate(root))
        assert (root / "_gaps.md").read_bytes() == text

    @pytest.mark.parametrize("res", [
        {"verdict": "none", "paths": [], "missing": ["horizon"]},  # no lead
        {"verdict": "weak", "paths": ["public/nowhere/x.csv"], "missing": []},  # a lead no article holds
        {"verdict": "none", "paths": [LAPS], "matched": ["configur", "instant", "pool"],  # a stray none lead: 3 of 6
         "known": ["clon", "configur", "horizon", "instant", "pool", "vmwar"], "lacks": ["VMware", "Horizon", "clone"]},
    ])
    def test_a_gap_off_the_kb_is_rejected(self, tmp_path, res):
        root = kb_root(tmp_path / "root")
        store = gap_store(tmp_path)
        before = root_files(root)
        rc, said = run_gap_apply(store, KbGate(root, res=res))
        assert rc == 0 and "applied=0 rejected=1 no-fix=0" in said[0] and "gaps=" not in said[0], said
        assert root_files(root) == before  # no topic takes its entry
        rec = by_id(store)[GAP_ID]
        assert (rec["state"], rec["stage"], rec["observed"]["gate"]) == ("rejected", "candidate-gap",
                                                                          ["off the kb's domains"])
        assert ql_store.store_problems(store) == []
        assert run_gap_apply(store, KbGate(root, res=res)) == (0, ["apply: nothing to apply"])  # converges

    @pytest.mark.parametrize("res", [
        {"verdict": "good", "paths": [LAPS], "missing": []},  # passes now: learn records it
        {"verdict": "none", "paths": [LAPS], "matched": ["budget", "hook", "sessionend"],  # the lead holds `1.5`:
         "known": ["1.5", "budget", "hook", "sessionend"], "lacks": ["1.5"]},  # learn makes it an eval finding
    ])
    def test_a_gap_fixed_or_held_is_left_to_learn(self, tmp_path, res):
        root = kb_root(tmp_path / "root")
        store = gap_store(tmp_path)
        gate = KbGate(root, res=res)
        gate.facts = lambda article: [(9, "`SessionEnd` hooks share a 1.5-second budget on exit. [DOC S100]")]
        before = root_files(root), tree(store)
        assert run_gap_apply(store, gate) == (0, ["apply: nothing to apply"])
        assert (root_files(root), tree(store)) == before
        assert (by_id(store)[GAP_ID]["state"], by_id(store)[GAP_ID]["stage"]) == ("open", "candidate-gap")

    # The weak-lead rule on the lead articles' own lines as the pack's index holds them (file name and title in each):
    # the pack result and the lines are those of the live kb when the SP-4slunkaj review found each case.

    @staticmethod
    def weak_gate(root, res, title, *lines):
        gate = KbGate(root, res={**res, "paths": [LAPS, GMSA]})
        gate.title = lambda article: title
        gate.facts = lambda article: [(n, text) for n, text in enumerate(lines, 9)]
        return gate

    @staticmethod
    def assert_weak_rejected(store, root, gate):
        before = root_files(root)
        rc, said = run_gap_apply(store, gate)
        assert rc == 0 and "applied=0 rejected=1 no-fix=0" in said[0] and "gaps=" not in said[0], said
        assert root_files(root) == before  # no topic takes its entry
        rec = by_id(store)[GAP_ID]
        assert (rec["state"], rec["stage"], rec["observed"]["gate"]) == ("rejected", "candidate-gap",
                                                                          ["off the kb's domains"])
        assert ql_store.store_problems(store) == []

    @staticmethod
    def assert_weak_taken(store, root, gate):
        rc, said = run_gap_apply(store, gate)
        assert rc == 0 and "gaps=1" in said[0], said
        assert "gives `weak`, with this topic in the lead" in (root / "_gaps.md").read_text(encoding="utf-8")
        assert (by_id(store)[GAP_ID]["state"], by_id(store)[GAP_ID]["stage"]) == ("applied", "gap")

    def test_gap_step_weak_rejects_qualifiers_only(self, tmp_path):
        """F-bd7367a45f3a: 'What is the maximum email attachment size?' packs `weak` with 3 of 4 key words, led by
        mecm/collect-client-logs, whose best line holds only `size` of attachment, email, maximum, size: off the kb's
        domains, no _gaps.md entry."""
        res = {"verdict": "weak", "matched": ["attachment", "maximum", "size"],
               "known": ["attachment", "email", "maximum", "size"], "lacks": ["email"], "missing": []}
        gate = self.weak_gate(kb_root(tmp_path / "root"), res, "collect-client-logs mecm/collect-client-logs",
                              "Size limit for the compressed client logs: 100 MB. [DOC S100]",
                              "Collected files in general: SMS Provider class `SMS_G_System_CollectedFile` (FileSize, "
                              "FileName). [DOC S100]")
        self.assert_weak_rejected(gap_store(tmp_path), tmp_path / "root", gate)

    def test_gap_step_weak_keeps_subject_in_lead_body(self, tmp_path):
        """F-68c59a20a679: the lead agents/codebase-mapping covers cargo metadata --no-deps in a Rust fact of its body,
        not in its title: the fact holds 3 of the 5 key words the kb knows, the subject, so the gap is the lead's."""
        res = {"verdict": "weak", "matched": ["cargo", "metadata", "no-dep"],
               "known": ["cargo", "config.toml", "invok", "metadata", "no-dep"],
               "lacks": ["invokes", "rustc", "config.toml", "build.rustc"], "missing": ["build.rustc", "rustc"]}
        gate = self.weak_gate(kb_root(tmp_path / "root"), res,
                              "codebase-mapping Mapping a codebase deterministically: toolchain pins and the "
                              "language's own tools",
                              "`cargo metadata --no-deps` reports only the workspace members, fetches no dependencies "
                              "and sets `resolve` to null. [DOC S100]",
                              "Maven's `help:evaluate` runs the plugin in the project. [DOC S100]")
        self.assert_weak_taken(gap_store(tmp_path), tmp_path / "root", gate)

    def test_gap_step_weak_rejects_qualifier_title_words(self, tmp_path):
        """F-f3230e66064f: 'architecture decision records ADR format status superseded' led by privacy/nist-sp800-38g,
        whose title holds the qualifiers format and status: its best line holds 3 of 7 key words, not the subject."""
        res = {"verdict": "weak", "matched": ["format", "status", "supers"],
               "known": ["adr", "architectur", "decision", "format", "record", "status", "supers"],
               "lacks": ["architecture", "decision", "records", "ADR"], "missing": []}
        gate = self.weak_gate(kb_root(tmp_path / "root"), res,
                              "nist-sp800-38g NIST SP 800-38G (format-preserving encryption) status",
                              "SP 800-38G (03/29/2016) is marked \"Withdrawn on August 04, 2016\" and superseded by "
                              "SP 800-38G `upd1`. [DOC S100]")
        self.assert_weak_rejected(gap_store(tmp_path), tmp_path / "root", gate)

    def test_gap_step_weak_rejects_slug_stem(self, tmp_path):
        """'How long do deleted emails stay in the recycle bin?' led by entra/bitlocker-key-deletion: the file name's
        `deletion` stems to the matched `delet`, yet no line holds more than delet and stay of 5 key words."""
        res = {"verdict": "weak", "matched": ["delet", "email", "recycl"],
               "known": ["bin", "delet", "email", "recycl", "stay"], "lacks": ["stay", "bin"], "missing": []}
        gate = self.weak_gate(kb_root(tmp_path / "root"), res,
                              "bitlocker-key-deletion Deleting an Entra device deletes its BitLocker keys",
                              "Soft-deleted devices are hidden from portal, Intune and Graph queries (HTTP 404); their "
                              "DeviceId stays reserved. [DOC S100]")
        self.assert_weak_rejected(gap_store(tmp_path), tmp_path / "root", gate)

    def test_gap_step_weak_rejects_one_lacked_word_in_a_fact(self, tmp_path):
        """'How long do deleted emails stay recoverable in Exchange Online?' led by entra/stale-devices: one fact holds
        the lacked word `recoverable` (of devices), and no line holds more than 2 of the 6 key words."""
        res = {"verdict": "weak", "matched": ["delet", "exchang", "onlin"],
               "known": ["delet", "email", "exchang", "onlin", "recoverabl", "stay"],
               "lacks": ["emails", "stay", "recoverable"], "missing": []}
        gate = self.weak_gate(kb_root(tmp_path / "root"), res, "stale-devices Stale device guidance (Entra)",
                              "Device soft delete (preview) keeps deleted devices recoverable for 30 days. [DOC S100]")
        self.assert_weak_rejected(gap_store(tmp_path), tmp_path / "root", gate)

    def test_gap_step_weak_takes_the_leads_subject(self, tmp_path):
        """A `weak` lead with a line holding more than half the key words the kb knows is the question's topic."""
        res = {"verdict": "weak", "matched": ["laps", "maximum", "password"],
               "known": ["azur", "laps", "maximum", "password"], "lacks": ["Azure"], "missing": []}
        gate = self.weak_gate(kb_root(tmp_path / "root"), res, "laps Windows LAPS",
                              "The maximum password age is 365 days. [DOC S100]")
        self.assert_weak_taken(gap_store(tmp_path), tmp_path / "root", gate)

    @pytest.mark.parametrize("finding,lead,off", [
        ("F-68c59a20a679", "public/agents/codebase-mapping.md", False),
        ("F-f3230e66064f", "public/privacy/nist-sp800-38g.md", True),
        ("F-bd7367a45f3a", "public/mecm/collect-client-logs.md", True),
    ])
    def test_gap_step_weak_live_findings(self, finding, lead, off):
        """The rule on the live kb and the committed store's real gap questions: each named finding's question, packed
        on the working tree, is kept or rejected as pinned. While the kb has moved on (its pack is no longer `weak`, or
        another article leads), the case no longer reaches the rule and is skipped, not failed."""
        store = Path(KB) / "kb" / "_querylog"
        rec = ql_store.finding_states(store).get(finding)
        entry = next((e for _, e in ql_store.store_entries(store) if rec and e.get("id") == rec.get("entry")), None)
        if not entry or not entry.get("question"):
            pytest.skip(f"{finding}: not in the committed store")
        gate = ql_apply.Gate()
        res = gate.pack(entry["question"])
        article = ql_learn.domain_article(res, gate.article_of)
        if res.get("verdict") != "weak" or article != lead:
            pytest.skip(f"{finding}: the kb moved on ({res.get('verdict')}, lead {article})")
        assert ql_apply.weak_off_topic(res, article, gate) is off, (entry["question"], res.get("known"),
                                                                    gate.unit_words(article, res.get("known")))

    def test_gap_step_weak_counts_product_aliases(self):
        """A key word that is a product alias (sccm for ConfigMgr) is held where its product's other names are."""
        gate = ql_apply.Gate()
        held = set().union(*gate.unit_words("public/mecm/collect-client-logs.md", ["sccm", "zqxlapsor"]))
        assert held == {"sccm"}

    def test_a_none_gap_under_its_article_becomes_an_entry(self, tmp_path):
        root = kb_root(tmp_path / "root")
        store = gap_store(tmp_path)
        res = {"verdict": "none", "paths": [LAPS], "matched": ["backup", "laps", "password"],
               "known": ["azur", "backup", "laps", "password"], "lacks": ["Azure"]}  # 3 of 4: the LAPS topic
        gate = KbGate(root, res=res)
        gate.facts = lambda article: [(9, "Windows LAPS backs up the password to Active Directory. [DOC S100]")]
        rc, said = run_gap_apply(store, gate)
        assert rc == 0 and "gaps=1" in said[0], said
        assert "gives `none`, with this topic in the lead" in (root / "_gaps.md").read_text(encoding="utf-8")
        assert (by_id(store)[GAP_ID]["state"], by_id(store)[GAP_ID]["stage"]) == ("applied", "gap")

    def test_none_candidate_gap_is_not_stranded(self, tmp_path, monkeypatch):
        """Every open gap candidate reaches a next state (F-6298df20a337: a none pack whose lead article holds the
        answer): learn turns the one the lead article holds into an eval finding, apply the one the kb lacks under
        its article into a _gaps.md entry the queue lists, and the stray none into a rejection, so the digest's open
        gaps are none but what the queue reaches."""
        held_q, lacks_q, stray_q = ("SessionEnd hook input fields reason budget 1.5 seconds",
                                    "Does SessionEnd hook input carry a zorblax field?", VMWARE_Q)
        store = learn_store(tmp_path)
        plant_entries(store, none_entry("ca", held_q), none_entry("cb", lacks_q))
        packs = {held_q: {"verdict": "none", "paths": [LAPS], "matched": ["budget", "hook", "reason", "sessionend"],
                          "known": ["1.5", "budget", "hook", "reason", "sessionend"], "lacks": ["1.5"], "missing": []},
                 lacks_q: {"verdict": "none", "paths": [LAPS], "matched": ["hook", "input", "sessionend"],
                           "known": ["field", "hook", "input", "sessionend"], "lacks": ["zorblax"],
                           "missing": ["zorblax"]},
                 stray_q: {"verdict": "none", "paths": [LAPS], "matched": ["configur", "instant", "pool"],
                           "known": ["clon", "configur", "horizon", "instant", "pool", "vmwar"],
                           "lacks": ["VMware", "Horizon", "clone"], "missing": []}}
        pack = lambda q: packs.get(q) or passing(q)  # noqa: E731
        facts = [(64, "`SessionEnd` hooks share a 1.5-second budget on exit, `/clear` and `/resume`. [DOC S100]")]
        monkeypatch.setattr(ql_learn, "article_of", lambda path: path if path == LAPS else None)
        monkeypatch.setattr(ql_learn, "article_facts", lambda article: facts if article == LAPS else [])
        gap = {n: ql_store.finding_id("gap", E(n)) for n in ("ca", "cb", "a4")}
        ev = ql_store.finding_id("eval", E("ca"))

        def open_gaps():
            week, lines_, _ = ql_report.digest(store, "2026-W40")
            line = next((ln for ln in lines_ if ln.startswith("  gap: ")), "")
            m = re.search(r"\bopen (\d+)", line)
            return int(m.group(1)) if m else 0

        # the store as it stood: three none misses, each an open gap candidate (the planted stranded state)
        run_learn(store, lambda q: {**packs[q], "lacks": ["zorblax"]} if q in packs else passing(q))
        assert {by_id(store)[gap[n]]["stage"] for n in gap} == {"candidate-gap"} and open_gaps() == 3
        root = kb_root(tmp_path / "root")
        gate = KbGate(root)
        gate.pack, gate.facts = pack, ql_learn.article_facts
        assert run_queue(store, gate)[1][0].startswith("queue: gaps=0 ")  # the digest counts 3 the queue cannot reach

        rc, said = run_learn(store, pack)  # the lead article holds `1.5`: an eval finding, the gap candidate gone
        assert rc == 0, said
        now = by_id(store)
        assert (now[ev]["kind"], now[ev]["state"], now[ev]["stage"], now[ev]["expect"]) == ("eval", "open", "miss", LAPS)
        assert now[gap["ca"]]["state"] == "fixed-since"  # no longer an open candidate: it left candidate-gap
        assert now[ql_store.finding_id("expansion", E("ca"))]["article"] == LAPS  # its fix, as for any eval miss

        hold = {i for i, r in now.items() if r["kind"] in ("eval",) + ql_store.FIX_KINDS}  # the gap step alone
        said = []
        rc = ql_apply.apply(store, gate=gate, kb_commit="0" * 40, out=said.append, hold=hold, day=DAY)
        assert rc == 0 and "applied=1 rejected=1" in said[0] and "gaps=1" in said[0], said
        now = by_id(store)
        assert (now[gap["cb"]]["state"], now[gap["cb"]]["stage"]) == ("applied", "gap")  # the kb lacks it
        assert (now[gap["a4"]]["state"], now[gap["a4"]]["stage"]) == ("rejected", "candidate-gap")  # the stray lead
        text = (root / "_gaps.md").read_text(encoding="utf-8")
        assert gap["cb"] in text and gap["ca"] not in text and gap["a4"] not in text
        rc, said = run_queue(store, gate)
        assert rc == 0 and said[0].startswith("queue: gaps=1 queued=1 ") and listed(said) == [gap["cb"]], said
        assert open_gaps() == 0  # no open gap the queue cannot reach
        assert ql_store.store_problems(store) == []
        before = tree(store), root_files(root)
        assert run_learn(store, pack)[1][0].startswith("learn: nothing new")  # converges
        assert ql_apply.apply(store, gate=gate, kb_commit="0" * 40, out=lambda _: None, hold=hold, day=DAY) == 0
        assert (tree(store), root_files(root)) == before

    def test_holds_word(self):
        assert ql_learn.holds_word("1.5", "hooks share a 1.5-second budget") and ql_learn.holds_word("1.5", "is 1.5.")
        assert not ql_learn.holds_word("1.5", "since v2.1.5 it") and not ql_learn.holds_word("1.5", "a 1.50 s wait")
        assert ql_learn.holds_word("Azure", "backs up to azure.") and not ql_learn.holds_word("log", "a catalog")

    def test_add_under(self):
        assert ql_research.add_under("", "a/b", "- x") == "## a/b\n\n- x\n"
        assert ql_research.add_under("# T\n\n## a/b\n", "a/b", "- x") == "# T\n\n## a/b\n\n- x\n"
        assert ql_research.add_under("# T\n\n## a/b\n\n- y\n\n\n## c/d\n\n- z\n", "a/b", "- x") == \
            "# T\n\n## a/b\n\n- y\n- x\n\n\n## c/d\n\n- z\n"


GMSA = "public/windows/gmsa.md"
VMWARE_Q = "How do I configure VMware Horizon instant clone pools?"  # a4's question
LATER = "2026-10-28"  # QUEUE_TRIED_DAYS after DAY


class TwoTopicGate(KbGate):
    """KbGate with a second article: a question naming gMSA leads with windows/gmsa, any other with windows/laps."""

    def pack(self, question):
        if self.res.get("verdict") == "good":
            return self.res
        return {"verdict": "weak", "paths": [GMSA if "gMSA" in question else LAPS], "missing": []}

    def article_of(self, path):
        return path if path in (LAPS, GMSA) else None

    def topic(self, article):
        return {LAPS: "windows/laps", GMSA: "windows/gmsa"}[article]


def queued(tmp_path, extra=()):
    """(root, store, gate): the gap store after the gap step wrote its _gaps.md entries in a one-article root."""
    root = kb_root(tmp_path / "root")
    store = gap_store(tmp_path, extra)
    gate = TwoTopicGate(root)
    run_gap_apply(store, gate)
    return root, store, gate


def run_queue(store, gate, limit=None, day=DAY):
    said = []
    rc = ql_research.queue(store, limit, gate=gate, day=day, kb_commit="0" * 40, out=said.append)
    return rc, said


def run_close(store, gate, fid, **kw):
    said = []
    rc = ql_research.close(fid, store=store, gate=gate, day=DAY, kb_commit="0" * 40, out=said.append, **kw)
    return rc, said


def resolve(root, fid, note="the vendor's page states it (S100)"):
    """The _gaps.md entry of `fid` closed by the content rules: a `Resolved <day>:` note under it."""
    p = root / "_gaps.md"
    lines = p.read_text(encoding="utf-8").split("\n")
    _, end = ql_research.entry_block(lines, fid)
    lines[end:end] = [f"  - Resolved {DAY}: {note}. (topic: windows/laps)"]
    p.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def listed(said):
    """The finding ids a queue printed, in order."""
    return re.findall(r"^     (F-[0-9a-f]{12}) ", "\n".join(said), re.M)


class TestQueue:
    def test_ranked_by_lookups_then_age_and_grouped_by_topic(self, tmp_path):
        _, store, gate = queued(tmp_path, extra=(("d1", VMWARE_Q, None),  # asked twice with a4
                                                 ("d2", "Can VMware Horizon run as a gMSA?", "2026-09-20"),  # older
                                                 ("d3", "VMware Horizon pool sizes?", None)))
        gap = {n: ql_store.finding_id("gap", E(n)) for n in ("a4", "d1", "d2", "d3")}
        rc, said = run_queue(store, gate)
        assert rc == 0 and said[0].startswith("queue: gaps=4 queued=3 listed=3 waiting=0 fixed-since=0"), said
        # one item per question: a4 and d1 asked the same one; grouped by topic, laps (d3 too), then gmsa (d2)
        assert listed(said) == sorted([gap["a4"], gap["d1"]]) + [gap["d3"], gap["d2"]]
        assert [s for s in said if s.startswith("topic ")] == ["topic windows/laps", "topic windows/gmsa"]
        first = said.index("  1. asked=2 since=2026-09-27")
        assert said[first + 1] == f"     question: {VMWARE_Q}"
        assert re.fullmatch(rf"     {sorted([gap['a4'], gap['d1']])[0]} .*_gaps\.md:\d+", said[first + 2])
        rc, top = run_queue(store, gate, limit=2)  # the top two by rank: the question asked twice, then the oldest
        assert listed(top) == sorted([gap["a4"], gap["d1"]]) + [gap["d2"]]
        assert "listed=2" in top[0] and top.count("topic windows/gmsa") == 1

    def test_the_same_store_and_head_give_the_same_queue(self, tmp_path):
        _, store, gate = queued(tmp_path, extra=("d1",))
        other = tmp_path / "copy"
        shutil.copytree(store, other)
        assert run_queue(store, gate) == run_queue(other, gate) and tree(store) == tree(other)

    def test_a_gap_that_passes_now_is_recorded_fixed_since(self, tmp_path):
        root, store, gate = queued(tmp_path, extra=("d1",))
        gate.res = {"verdict": "good", "paths": [LAPS], "missing": []}
        rc, said = run_queue(store, gate)
        assert rc == 0 and "queued=0" in said[0] and "fixed-since=2" in said[0], said
        recs = findings(store)[-1][1]
        assert {r["state"] for r in recs} == {"fixed-since"} and {r["stage"] for r in recs} == {"gap"}
        assert ql_store.store_problems(store) == []
        gate.res = {}  # the kb fails it again: it stays fixed-since, learn leaves it
        before = tree(store)
        assert run_queue(store, gate)[1][0].startswith("queue: gaps=0 ")
        rc, said = run_learn(store, lambda q: failing(q) if "VMware" in q else passing(q))
        assert said[0].startswith("learn: nothing new") and tree(store) == before, said

    def test_a_second_queue_after_a_closing_run_omits_the_closed_gap(self, tmp_path):
        root, store, gate = queued(tmp_path, extra=("d1",))
        fid = listed(run_queue(store, gate)[1])[0]
        assert run_close(store, gate, fid, claim=True) == (1, [
            f"close: {root.as_posix()}/_gaps.md:{ql_research.ledger_entry(gate, by_id(store)[fid])[1]} has no "
            "`Resolved <date>:` note under it; close the entry by the content rules first"])
        resolve(root, fid)
        rc, said = run_close(store, gate, fid, claim=True)
        assert rc == 0 and said[0].startswith(f"close: {fid} claim run="), said
        rec = by_id(store)[fid]
        assert (rec["state"], rec["stage"], rec["promotions"][-1]) == (
            "applied", "claim", {"from": "gap", "to": "claim", "by": "kb-research"})
        assert querylog.main(["check", str(store)]) == 0
        rc, again = run_queue(store, gate)
        assert rc == 0 and fid not in "\n".join(again) and len(listed(again)) == 1
        before = tree(store), root_files(root)
        assert run_queue(store, gate) == (rc, again) and (tree(store), root_files(root)) == before  # converges
        assert run_close(store, gate, fid, claim=True)[0] == 1  # closed: no second record

    def test_a_planted_closed_gap_that_reappears_fails(self, tmp_path):
        root, store, gate = queued(tmp_path)
        fid = listed(run_queue(store, gate)[1])[0]
        resolve(root, fid)
        run_close(store, gate, fid, claim=True)
        entries = ql_store.store_entries(store)
        back = {**by_id(store)[fid], "stage": "gap", "promotions": by_id(store)[fid]["promotions"][:2]}
        ql_store.write_findings(store, entries, [back], ("applied",), "0" * 40)  # a later record reopens it
        assert any("reappears at stage gap" in p for p in ql_store.store_problems(store))
        rc, said = run_queue(store, gate)
        assert rc == 1 and listed(said) == [] and any("reappears at stage gap" in s for s in said), said

    def test_a_closed_gap_whose_entry_reopens_fails(self, tmp_path):
        root, store, gate = queued(tmp_path)
        fid = listed(run_queue(store, gate)[1])[0]
        text = (root / "_gaps.md").read_text(encoding="utf-8")
        _, line, _ = ql_research.ledger_entry(gate, by_id(store)[fid])
        resolve(root, fid)
        run_close(store, gate, fid, claim=True)
        assert run_queue(store, gate)[0] == 0
        (root / "_gaps.md").write_text(text, encoding="utf-8", newline="\n")  # the Resolved note is gone
        rc, said = run_queue(store, gate)
        assert rc == 1 and said[-1] == (f"problem: {fid}: closed at claim, but its entry {root.as_posix()}/_gaps.md:"
                                        f"{line} has no Resolved note"), said

    def test_a_recent_tried_note_waits_and_an_old_one_is_queued(self, tmp_path):
        root, store, gate = queued(tmp_path)
        fid = listed(run_queue(store, gate)[1])[0]
        assert run_close(store, gate, fid, tried="   ")[0] == 1
        rc, said = run_close(store, gate, fid, tried="Searched the vendor docs; no page states it. (topic: x/y)")
        assert rc == 0 and said[0].startswith(f"close: {fid} tried {DAY} run="), said
        lines = (root / "_gaps.md").read_text(encoding="utf-8").split("\n")
        i, end = ql_research.entry_block(lines, fid)
        assert lines[end - 1] == f"  - Tried {DAY}: Searched the vendor docs; no page states it. (topic: windows/laps)"
        assert by_id(store)[fid]["tried"] == DAY and querylog.main(["check", str(store)]) == 0
        day_before = (datetime.date.fromisoformat(LATER) - datetime.timedelta(days=1)).isoformat()
        rc, said = run_queue(store, gate, day=day_before)
        assert listed(said) == [] and f"waiting {fid}: tried {DAY}, back in the queue {LATER}" in said, said
        assert listed(run_queue(store, gate, day=LATER)[1]) == [fid]

    def test_close_refuses_what_is_no_open_gap(self, tmp_path):
        root, store, gate = queued(tmp_path)
        assert run_close(store, gate, "F-000000000000", claim=True)[0] == 1
        other = next(r["id"] for r in by_id(store).values() if r["kind"] == "eval")
        assert run_close(store, gate, other, tried="x")[0] == 1
        (root / "_gaps.md").write_text(GAPS_MD, encoding="utf-8", newline="\n")  # the entry is gone
        fid = next(r["id"] for r in by_id(store).values() if r["kind"] == "gap")
        assert run_close(store, gate, fid, tried="x") == (1, [f"close: no _gaps.md entry names {fid}"])

    def test_reject_records_a_gap_whose_entry_was_removed(self, tmp_path):
        """An open gap finding whose _gaps.md entry an operator removed as off the kb's domains: the queue skips it
        (no entry), so without --reject it stays open for good. --reject refuses while the entry is there, then puts
        the finding back to candidate-gap, rejected with the gap step's reason, and a second one is refused."""
        root, store, gate = queued(tmp_path)
        fid = listed(run_queue(store, gate)[1])[0]
        _, line, _ = ql_research.ledger_entry(gate, by_id(store)[fid])
        assert run_close(store, gate, fid, reject=True) == (1, [
            f"close: {root.as_posix()}/_gaps.md:{line} still names {fid}; --reject records an entry already removed "
            "as off the kb's domains (remove it first, or use --claim or --tried)"])
        other = next(r["id"] for r in by_id(store).values() if r["kind"] == "eval")
        assert run_close(store, gate, other, reject=True)[0] == 1  # no gap finding
        p = root / "_gaps.md"
        lines = p.read_text(encoding="utf-8").split("\n")
        i, end = ql_research.entry_block(lines, fid)
        p.write_text("\n".join(lines[:i] + lines[end:]), encoding="utf-8", newline="\n")  # the operator removes it
        last = ql_store.finding_states(store)
        assert fid in {g["id"] for g in ql_research.open_gaps(store, last)}  # open, though the queue skips it
        rc, said = run_close(store, gate, fid, reject=True)
        assert rc == 0 and said[0].startswith(f"close: {fid} rejected run="), said
        rec = by_id(store)[fid]
        assert (rec["state"], rec["stage"], rec["observed"]["gate"], rec["promotions"][-1]) == (
            "rejected", "candidate-gap", ["off the kb's domains"],
            {"from": "gap", "to": "candidate-gap", "by": "kb-research"})
        assert rec["article"] == LAPS and querylog.main(["check", str(store)]) == 0
        last = ql_store.finding_states(store)
        assert fid not in {g["id"] for g in ql_research.open_gaps(store, last)}
        before = tree(store)
        assert run_close(store, gate, fid, reject=True)[0] == 1  # no longer open: no second record
        run_gap_apply(store, gate)  # the gap step leaves a rejected candidate alone
        assert run_queue(store, gate)[0] == 0 and tree(store) == before

    def test_cli(self, tmp_path):
        store = learn_store(tmp_path)
        out = subprocess.run([sys.executable, QL, "queue", "2", "--store", str(store)], capture_output=True, text=True,
                             encoding="utf-8", cwd=KB, env=querylog_env(tmp_path / "data"))
        assert out.returncode == 0 and out.stdout.startswith("queue: gaps=0 "), out.stdout + out.stderr
        out = subprocess.run([sys.executable, QL, "close", "F-000000000000", "--claim", "--store", str(store)],
                             capture_output=True, text=True, encoding="utf-8", cwd=KB,
                             env=querylog_env(tmp_path / "data"))
        assert out.returncode == 1 and "no open gap finding" in out.stdout, out.stdout + out.stderr


def record_work(repo, path):
    """The KB-Work trailers git reads on the commits that changed `path`: the work items `backlog.py done` would count
    them to, so a story whose touches never name the store refuses them."""
    log = repo.git("log", "--format=%(trailers:key=KB-Work,valueonly)%x1e", "--", str(path))
    return [v.strip() for v in log.split("\x1e") if v.strip()]


@requires_git
class TestCloseCommit:
    """`close --commit` commits the findings record alone and never with a work item's KB-Work trailer: the record is
    the query log's, so `backlog.py done` never refuses the story whose research answered the gap over a path outside
    its touches (SP-jtfo4ael's retrospective, ST-ej3iqwdo). Planted: the old way, the record committed by hand under
    the research task's KB-Work trailer, which `record_work` sees; a KB-Work --trailer is refused."""

    def repo(self, tmp_path, monkeypatch):
        env = git_env()
        for k in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM", "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
                  "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
            monkeypatch.setenv(k, env[k])
        root, store, gate = queued(tmp_path)
        repo = Repo(tmp_path, env)
        repo.git("init", "-q", "-b", "main")
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "base")
        fid = listed(run_queue(store, gate)[1])[0]
        resolve(root, fid)  # the research's own change: stays for its commit
        (tmp_path / "staged.txt").write_text("x\n", encoding="utf-8")
        repo.git("add", "staged.txt")  # staged before close: stays staged and out of its commit
        return repo, root, store, gate, fid

    def test_querylog_close_trailer_commits_the_record_alone_without_kb_work(self, tmp_path, monkeypatch):
        repo, root, store, gate, fid = self.repo(tmp_path, monkeypatch)
        base = repo.rev("HEAD")
        said = []
        rc = querylog.close([fid], claim=True, store=store, gate=gate, day=DAY, kb_commit="0" * 40, out=said.append,
                            commit=True, trailers=["Co-Authored-By: t <t@example.com>"])
        assert rc == 0 and said[-1] == "close: committed 1 findings file(s), with no KB-Work trailer", said
        (changed,) = repo.git("show", "--name-only", "--format=", "HEAD").split()  # the record alone
        rec = tmp_path / changed
        assert changed.startswith(f"{store.relative_to(tmp_path).as_posix()}/findings/") and rec.is_file()
        assert repo.rev("HEAD~1") == base
        assert repo.git("log", "-1", "--format=%s", "HEAD") == f"chore(querylog): close {fid} (claim)\n"
        assert repo.git("log", "-1", "--format=%(trailers:key=Co-Authored-By,valueonly)").strip() == "t <t@example.com>"
        assert record_work(repo, rec) == []
        status = repo.git("status", "--porcelain")
        assert "M root/_gaps.md" in status and "A  staged.txt" in status, status
        assert by_id(store)[fid]["stage"] == "claim" and querylog.main(["check", str(store)]) == 0

    def test_querylog_close_trailer_planted_old_way_and_kb_work_refused(self, tmp_path, monkeypatch):
        repo, root, store, gate, fid = self.repo(tmp_path, monkeypatch)
        before = tree(store)
        said = []
        for trailers, commit in ((["KB-Work: TK-s7c63awy"], True), (["kb-work:TK-x"], True), (["no trailer"], True),
                                 (["Co-Authored-By: t <t@example.com>"], False)):
            assert querylog.close([fid], claim=True, store=store, gate=gate, day=DAY, out=said.append,
                                  commit=commit, trailers=trailers) == 1
        assert tree(store) == before and said[0].startswith("close: refused --trailer 'KB-Work: TK-s7c63awy'"), said
        assert said[-1] == "close: --trailer needs --commit"
        written = []  # the old way: close writes, the research task commits the record under its own trailer
        assert ql_research.close(fid, claim=True, store=store, gate=gate, day=DAY, out=said.append,
                                 written=written) == 0
        repo.git("add", "--", str(written[0]))
        repo.git("commit", "-q", "-m", "chore(querylog): close", "-m", "KB-Work: TK-s7c63awy", "--only", "--",
                 str(written[0]))
        assert record_work(repo, written[0]) == ["TK-s7c63awy"]  # what done counts to the item: it fails


class TestQuoteCheck:
    @pytest.mark.parametrize("quote", [
        GOOD_QUOTE,  # an entity and a no-break space on the page
        f"\u201c{LEGACY_QUOTE}.\u201d",  # a link and emphasis on the page, the quote in curly quotes
        "Windows LAPS backs up passwords to Microsoft Entra ID only from devices",  # spread over lines
        "WINDOWS SERVER 2012 R2 & EARLIER RELEASES",  # &amp; on the page
    ])
    def test_a_quote_on_its_page(self, quote):
        assert ql_research.quotecheck(PAGE_URL, quote, pages) == (True, "quote is on the page")

    @pytest.mark.parametrize("quote,why", [
        (BAD_QUOTE, "quote is not on the page"),  # planted: a quote not on its page
        ("Docs > Identity > LAPS is the path", "quote is not on the page"),  # page chrome is not the page's text
        (" ".join(["word"] * 26), "quote has 26 words, over 25"),
        ("Windows LAPS", "quote has 2 words, under 5"),
    ])
    def test_a_quote_not_accepted(self, quote, why):
        assert ql_research.quotecheck(PAGE_URL, quote, pages) == (False, why)

    def test_a_page_that_cannot_be_fetched(self):
        ok, why = ql_research.quotecheck("https://docs.example.com/other", GOOD_QUOTE, pages)
        assert not ok and why.startswith("page not fetched: OSError")

    def test_a_markdown_page(self):
        md = b"See the [LAPS overview](https://docs.example.com/o) for **supported** platforms and more.\n"
        assert ql_research.quotecheck(PAGE_URL, "See the LAPS overview for supported platforms",
                                      lambda u: (md, "text/markdown"))[0]

    def test_pages_are_fetched_as_fetch_py_fetches_them(self, monkeypatch):
        import fetch
        asked = []
        monkeypatch.setattr(fetch, "fetch", lambda url: asked.append(url) or pages(url))
        assert ql_research.quotecheck(PAGE_URL, GOOD_QUOTE)[0] and asked == [PAGE_URL]

    def test_quote_max_words_is_the_kb_rule(self):
        import kbcommon
        assert ql_research.QUOTE_MAX_WORDS == kbcommon.QUOTE_WORDS == 25

    @pytest.mark.parametrize("quote,rc,said", [(GOOD_QUOTE, 0, "quotecheck: quote is on the page\n"),
                                               (BAD_QUOTE, 1, "quotecheck: quote is not on the page\n")])
    def test_cli(self, tmp_path, quote, rc, said):
        p = subprocess.run([sys.executable, QL, "quotecheck", PAGE_URL, quote, "--page", str(PAGE)],
                           capture_output=True, text=True, encoding="utf-8", env=querylog_env(tmp_path), timeout=120)
        assert (p.returncode, p.stdout) == (rc, said), p.stderr


class TestResearchConfig:
    @pytest.mark.parametrize("text,want", [
        (None, (False, 0)),  # no file: research is off by default
        ('{"mode": "local"}', (False, 0)),
        ('{"research": true}', (True, ql_base.DEFAULT_RESEARCH_DAILY)),
        ('{"research": true, "research_daily": 1}', (True, 1)),
        ('{"research": true, "research_daily": 0}', (True, 0)),
        ('{"research": "yes"}', (False, 0)),  # fail closed
        ('{"research": true, "research_daily": -1}', (False, 0)),
        ('{"research": true, "research_daily": "many"}', (False, 0)),
        ('{"research": true, "research_daily": true}', (False, 0)),
        ("{not json", (False, 0)),
    ])
    def test_read_research(self, tmp_path, text, want):
        cfg = tmp_path / "config.json"
        if text is not None:
            cfg.write_text(text, encoding="utf-8")
        assert ql_base.read_research(cfg) == want
        assert ql_base.DEFAULT_RESEARCH is False

    def test_the_daily_cap_counts_runs(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text('{"mode": "local", "research": true, "research_daily": 2}', encoding="utf-8")
        assert ql_research.research_budget(tmp_path, cfg, DAY) == 2
        ql_research.count_research(tmp_path, DAY)
        assert ql_research.research_budget(tmp_path, cfg, DAY) == 1
        ql_research.count_research(tmp_path, DAY)
        assert ql_research.research_budget(tmp_path, cfg, DAY) == 0
        ql_research.count_research(tmp_path, DAY)  # never below 0
        assert ql_research.research_budget(tmp_path, cfg, DAY) == 0
        assert ql_research.research_budget(tmp_path, cfg, "2026-09-29") == 2  # a new day
        (tmp_path / "DISABLED").write_text("", encoding="utf-8")
        assert ql_research.research_budget(tmp_path, cfg, "2026-09-29") == 0
        (tmp_path / "DISABLED").unlink()
        cfg.write_text('{"mode": "off", "research": true}', encoding="utf-8")
        assert ql_research.research_budget(tmp_path, cfg, "2026-09-29") == 0

    def test_a_clone_names_its_own_config(self, tmp_path):
        assert ql_research.research_places(tmp_path) == (tmp_path / "_cache" / "querylog",
                                                         tmp_path / "_private" / "querylog.json")


class TestResearch:
    def setup(self, tmp_path, *cands, runs=1, checks=(), extra=()):
        root = kb_root(tmp_path / "root")
        store = gap_store(tmp_path, extra)
        calls, counted = [], []

        def call(prompt):
            calls.append(prompt)
            return reply(*cands)
        research = ql_research.Researcher(runs, call=call, fetcher=pages, counted=lambda: counted.append(1))
        return root, store, KbGate(root, checks=checks), research, calls, counted

    def test_facts_sources_and_a_conflict_are_added(self, tmp_path):
        other = cand(text="Windows LAPS supports Windows Server 2012 R2 after a later update.", quote=BAD_QUOTE)
        legacy = cand(text="Legacy Microsoft LAPS stays available for older operating systems.", quote=LEGACY_QUOTE,
                      conflicts_with=19)
        root, store, gate, research, calls, counted = self.setup(tmp_path, cand(), other, legacy)
        rc, said = run_gap_apply(store, gate, research)  # the gap step and research in one run
        assert rc == 0 and "gaps=1 research=1 facts=1 conflicts=1" in said[0], said
        assert len(calls) == len(counted) == 1 and not research.left()
        assert "How do I configure VMware Horizon instant clone pools?" in calls[0]
        assert "19: - The default password length is 14 characters. [DOC S101]" in calls[0]
        import kbid
        sid = kbid.source_id(PAGE_URL, "S")
        art = (root / "windows" / "laps.md").read_text(encoding="utf-8")
        assert ql_research.edit_problems("laps.md", ARTICLE_MD, art) == []
        lines = art.split("\n")
        assert lines[19] == f"- {cand()['text']} [DOC {sid}]" and lines[20:22] == ["", "## Reference"]
        assert f"sources: [S100, S101, {sid}]" in lines
        src = (root / "_sources.csv").read_text(encoding="utf-8")
        assert src.startswith(SOURCES_CSV) and src[len(SOURCES_CSV):].count("\n") == 1  # one row for one url
        assert src.endswith(f"{sid},{PAGE_URL},Windows LAPS platform support,Example Docs,"
                            f'"CC BY 4.0, stated on the page (test page)",copy,{DAY},,,,\n')
        conflicts = (root / "_conflicts.md").read_text(encoding="utf-8")
        assert conflicts.startswith("# Conflicts\n\n## windows/laps\n\n- **The default password length is 14 characters.**")
        assert f"[DOC {sid} vs S101] (topic: windows/laps)" in conflicts and GAP_ID in conflicts
        rec = by_id(store)[GAP_ID]
        assert (rec["state"], rec["stage"]) == ("applied", "claim")
        assert [(p["to"], p["by"]) for p in rec["promotions"]] == [
            ("candidate-gap", "learn"), ("gap", "apply"), ("candidate-fact", "research"), ("claim", "research")]
        assert rec["observed"] == {"facts": 1, "conflicts": 1, "sources": [sid],
                                   "gate": ["fact 1: quote is not on the page"]}
        gaps = (root / "_gaps.md").read_text(encoding="utf-8")  # the claim closes its entry by the content rules
        (note,) = [ln for ln in gaps.split("\n") if ln.startswith("  - Resolved ")]
        assert f"added 1 fact from {sid} (finding {GAP_ID}) (topic: windows/laps)" in note, note
        assert ql_research.settled(ql_research.ledger_entry(gate, rec)[2])
        assert gate.indexed == 1 and ql_store.store_problems(store) == []
        first = tree(store), root_files(root)
        assert run_gap_apply(store, gate, ql_research.Researcher(1, call=calls.append, fetcher=pages)) == \
            (0, ["apply: nothing to apply"])  # a claim is not researched again
        assert (tree(store), root_files(root)) == first

    def test_a_quote_not_on_its_page_is_rejected(self, tmp_path):
        root, store, gate, research, calls, _ = self.setup(tmp_path, cand(quote=BAD_QUOTE))  # planted
        before = root_files(root)
        run_gap_apply(store, gate)
        gapped = root_files(root)
        assert gapped != before  # the gap entry
        rc, said = run_gap_apply(store, gate, research)
        assert rc == 0 and "research=1 facts=0 conflicts=0" in said[0] and "rejected=1" in said[0], said
        assert root_files(root) == gapped and gate.indexed == 0
        rec = by_id(store)[GAP_ID]
        assert (rec["state"], rec["stage"], rec["observed"]["gate"]) == (
            "rejected", "candidate-fact", ["fact 0: quote is not on the page"])
        assert ql_store.store_problems(store) == []

    def test_research_editing_an_existing_fact_line_is_put_back(self, tmp_path, monkeypatch):
        root, store, gate, research, _, _ = self.setup(tmp_path, cand())
        run_gap_apply(store, gate)
        before = root_files(root)
        add = ql_research.add_fact
        monkeypatch.setattr(ql_research, "add_fact", lambda text, line: add(text, line).replace(
            "is 14 characters", "is 16 characters"))  # planted: the writer also edits an existing fact line
        rc, said = run_gap_apply(store, gate, research)
        assert rc == 0 and "rejected=1" in said[0], said
        assert root_files(root) == before and gate.indexed == 0  # every file put back
        rec = by_id(store)[GAP_ID]
        assert rec["state"] == "rejected" and rec["stage"] == "candidate-fact"
        assert rec["observed"]["gate"] == ["laps.md: removes or edits an existing fact line: - The default password "
                                           "length is 14 characters. [DOC S101]"]

    def test_a_red_check_puts_everything_back(self, tmp_path):
        root, store, gate, research, _, _ = self.setup(tmp_path, cand(), checks=["ERROR windows/laps.md cites S9"])
        run_gap_apply(store, gate)
        before = root_files(root)
        run_gap_apply(store, gate, research)
        assert root_files(root) == before
        assert by_id(store)[GAP_ID]["observed"]["gate"] == ["ERROR windows/laps.md cites S9"]

    def test_at_most_the_daily_runs(self, tmp_path):
        root, store, gate, research, calls, counted = self.setup(tmp_path, cand(), runs=1, extra=("a6",))
        rc, said = run_gap_apply(store, gate, research)
        assert "gaps=2 research=1" in said[0], said
        assert len(calls) == len(counted) == 1
        stages = sorted(r["stage"] for r in by_id(store).values() if r["kind"] == "gap")
        assert stages == ["claim", "gap"]  # the second waits for another day
        rc, said = run_gap_apply(store, gate, ql_research.Researcher(0, call=calls.append, fetcher=pages))
        assert said == ["apply: nothing to apply"] and len(calls) == 1

    def test_no_research_leaves_gap_findings(self, tmp_path):
        root, store, gate, research, calls, _ = self.setup(tmp_path, cand())
        run_gap_apply(store, gate, None)
        assert by_id(store)[GAP_ID]["stage"] == "gap" and calls == []
        assert run_gap_apply(store, gate, None) == (0, ["apply: nothing to apply"])

    def test_a_failed_call_writes_nothing_and_counts(self, tmp_path):
        root, store, gate, _, _, _ = self.setup(tmp_path)
        run_gap_apply(store, gate)
        before = tree(store), root_files(root)
        counted = []

        def down(prompt):
            raise OSError("claude -p exited 1")
        rc, said = run_gap_apply(store, gate, ql_research.Researcher(2, call=down, counted=lambda: counted.append(1)))
        assert said == ["apply: nothing to apply (research runs=1, no reply)"] and counted == [1]
        assert (tree(store), root_files(root)) == before  # tried again on a later run

    @pytest.mark.parametrize("text,why", [
        ("no JSON here", "reply: no JSON object in the reply"),
        ('{"facts": "none"}', "reply: no facts list"),
        ('{"facts": [{"text": "x"}]}', "reply: fact 0 is malformed"),
    ])
    def test_a_reply_that_is_not_the_json_is_rejected(self, tmp_path, text, why):
        root = kb_root(tmp_path / "root")
        store = gap_store(tmp_path)
        run_gap_apply(store, KbGate(root))
        before = root_files(root)
        run_gap_apply(store, KbGate(root), ql_research.Researcher(1, call=lambda p: text, fetcher=pages))
        rec = by_id(store)[GAP_ID]
        assert (rec["state"], rec["stage"], rec["observed"]["gate"]) == ("rejected", "gap", [why])
        assert root_files(root) == before

    @pytest.mark.parametrize("change,why", [
        ({"tag": "DER"}, "tag 'DER' is not one of DOC, COMMUNITY"),
        ({"url": "https://wiki.corp/laps"}, "url is not a public http(s) page"),
        ({"url": "ftp://docs.example.com/x"}, "url is not a public http(s) page"),
        ({"reuse": "free"}, "reuse 'free' is not a reuse class"),
        ({"licence": " "}, "title, publisher or licence is empty"),
        ({"text": "Short."}, "text is not one short sentence"),
        ({"text": "Windows LAPS does not support 2012 R2 at all. [DOC S100]"}, "text carries a tag"),
        ({"text": "The default password length is 14 characters."}, "text is already a fact"),
        ({"text": "Windows LAPS reads its settings from C:\\Users\\" + "anna.nowak\\laps.json on each device."},
         "leak scan flags"),  # a home path, joined at run time so the tracked-file leak scan does not flag it
        ({"conflicts_with": 3}, "conflicts_with 3 names no fact line"),
    ])
    def test_candidate_problems(self, change, why):
        facts = ql_research.fact_lines(ARTICLE_MD)
        assert [n for n, _ in facts] == [18, 19]
        assert ql_research.candidate_problems(cand(), facts) == []
        assert any(why in p for p in ql_research.candidate_problems(cand(**change), facts)), change

    def test_decision_tag_is_never_a_research_tag(self):
        """Research states facts from documentation (DOC or COMMUNITY): a reply that carries the DECISION tag, as
        its `tag` or inside its text, is rejected, though every other tool accepts the kind."""
        import kbfacts
        assert "DECISION" in kbfacts.KINDS and ql_research.RESEARCH_TAGS == ("DOC", "COMMUNITY")
        facts = ql_research.fact_lines(ARTICLE_MD)
        assert ql_research.candidate_problems(cand(), facts) == []
        assert any("tag 'DECISION' is not one of DOC, COMMUNITY" in p
                   for p in ql_research.candidate_problems(cand(tag="DECISION"), facts))
        carried = cand(text="Windows LAPS keeps 14 days of history by decision. [DECISION D-k3f7q2zd]")
        assert any("text carries a tag" in p for p in ql_research.candidate_problems(carried, facts))

    def test_edit_problems(self):
        e = ql_research.edit_problems
        assert e("x/a.md", ARTICLE_MD, ARTICLE_MD.replace("## Reference", "- New. [DOC S1]\n\n## Reference")) == []
        assert e("x/a.md", ARTICLE_MD, ARTICLE_MD.replace("14", "16"))  # planted: an edited fact line
        assert e("x/a.md", ARTICLE_MD, ARTICLE_MD.replace("A test article.", "Other words.")) == []  # no fact line
        assert e("_gaps.md", GAPS_MD, GAPS_MD.replace("Looked somewhere", "Looked"))  # planted: an edited entry
        assert e("_sources.csv", SOURCES_CSV, SOURCES_CSV.replace("windows/laps.md,\n", "a.md;b.md,\n")) == []
        assert e("_sources.csv", SOURCES_CSV, SOURCES_CSV.replace("LAPS policy", "LAPS"))  # planted: a changed row
        assert e("_sources.csv", SOURCES_CSV, SOURCES_CSV.split("S101")[0])  # planted: a removed row
        assert e("x/a.md", None, "anything") == []  # a new file

    def test_source_rows_go_in_id_order(self):
        """A new source row goes where kbgit.py fix, which sorts the rows by id, would put it (planted: appended at
        the end, which fix would move)."""
        import kbgit
        text = SOURCES_CSV + "S-aaaaaaaa,https://a.example.com/,A,P,L,quote,2026-09-01,,,windows/laps.md,\n"
        new = ["S-mmmmmmmm,https://m.example.com/,M,P,L,quote,2026-09-28,,,windows/laps.md,",
               "S150,https://s.example.com/,S,P,L,quote,2026-09-28,,,windows/laps.md,"]
        got = ql_research.insert_rows(text, new)
        assert [ln.split(",")[0] for ln in got.splitlines()] == ["id", "S100", "S101", "S150", "S-aaaaaaaa", "S-mmmmmmmm"]
        assert kbgit.canon_csv(got, True) == got and ql_research.edit_problems("_sources.csv", text, got) == []
        appended = text + "".join(ln + "\n" for ln in new)
        assert kbgit.canon_csv(appended, True) != appended


@pytest.fixture(scope="module")
def researched(tmp_path_factory):
    """A kb copy and a store whose one lookup is a gap under the LAPS article: learn, then apply with research off
    (the gap entry), then with research on at one run a day (the recorded reply and page), then apply again.
    (home, store, outputs, the copy's files before, the copy's files after research)."""
    base = tmp_path_factory.mktemp("research")
    home = Path(copy_kb(str(base / "kb")))
    store = base / "store"
    run = store / "2026-09" / "20260928T130000Z-0000beef.jsonl"
    run.parent.mkdir(parents=True)
    header = {"run": run.stem, "pipeline": 1, "retrieval": 4, "kb_commit": "0" * 40,
              "counts": {"entries": 1, "dropped": 0, "waiting": 0}}
    entry = {"id": E("a4"), "surface": "prompt", "day": "2026-09-27", "tools": ["kb_pack"], "question": LAPS_GAP_Q,
             "verdict": "weak", "articles": [LAPS], "citations": [{"line": f"{LAPS}:18", "verdict": "weak"}],
             "cited": "pack", "judged": "missed"}
    run.write_text("".join(json.dumps(o, separators=(",", ":")) + "\n" for o in (header, entry)), encoding="utf-8",
                   newline="\n")
    art = home / "kb" / "public" / "windows" / "laps.md"
    n, line = ql_research.fact_lines(art.read_text(encoding="utf-8"))[0]
    legacy = cand(text="Legacy Microsoft LAPS stays available for older operating systems.", quote=LEGACY_QUOTE,
                  conflicts_with=n)
    shutil.copy(PAGE, base / "page.html")
    replay = base / "research.json"
    replay.write_text(json.dumps({"replies": [reply(cand(), cand(text="Windows LAPS supports Windows Server 2012 R2 "
                                                                  "after a later update.", quote=BAD_QUOTE), legacy)],
                                  "pages": {PAGE_URL: "page.html"}}), encoding="utf-8")
    data = base / "data"
    cfg = data / "querylog" / "config.json"
    cfg.parent.mkdir(parents=True)
    env = querylog_env(data, home=str(home), base={**os.environ, "KB_INDEX": str(home / "_cache")})
    files = ("kb/public/windows/laps.md", "kb/public/_sources.csv", "kb/public/_conflicts.md", "kb/public/_gaps.md",
             "kb/public/_coverage.csv", "kb/public/_coverage.md")
    snap = lambda: {f: (home / f).read_bytes() for f in files}  # noqa: E731
    before, said = snap(), []
    ql = [sys.executable, str(home / "_tools" / "querylog.py")]
    for config, cmd in (('{"mode": "local"}', ["learn", "--store", str(store)]),
                        ('{"mode": "local"}', ["apply", "--store", str(store), "--replay-research", str(replay)]),
                        ('{"mode": "local", "research": true, "research_daily": 1}',
                         ["apply", "--store", str(store), "--replay-research", str(replay)]),
                        ('{"mode": "local", "research": true, "research_daily": 1}',
                         ["apply", "--store", str(store), "--replay-research", str(replay)])):
        cfg.write_text(config, encoding="utf-8")
        p = subprocess.run([*ql, *cmd], capture_output=True, text=True, encoding="utf-8", env=env, cwd=home,
                           timeout=900)
        assert p.returncode == 0, p.stdout + p.stderr
        said.append(p.stdout.strip())
        if len(said) == 3:
            after = snap()
    return home, store, env, said, before, after, (n, line), data


class TestResearchInKbCopy:
    def test_research_off_writes_the_gap_entry_only(self, researched):
        home, store, env, said, before, after, _, _ = researched
        assert "gaps=1" in said[1] and "research=" not in said[1], said
        text = (home / "kb" / "public" / "_gaps.md").read_text(encoding="utf-8")
        assert f"- **{LAPS_GAP_Q}** " in text and "(topic: windows/laps)" in text

    def test_research_adds_a_fact_a_source_and_a_conflict(self, researched):
        home, store, env, said, before, after, (n, line), _ = researched
        assert "research=1 facts=1 conflicts=1" in said[2], said
        import kbid
        sid = kbid.source_id(PAGE_URL, "S")
        rel = "kb/public/windows/laps.md"
        art = after[rel].decode("utf-8")
        assert f"- {cand()['text']} [DOC {sid}]" in art.split("\n")
        assert ql_research.edit_problems(rel, before[rel].decode("utf-8"), art) == []
        assert ql_research.edit_problems("kb/public/_sources.csv", before["kb/public/_sources.csv"].decode("utf-8"),
                                         after["kb/public/_sources.csv"].decode("utf-8")) == []
        import kbgit  # the new row sits in id order: kbgit.py fix, which sorts the rows by id, changes nothing
        sources = after["kb/public/_sources.csv"].decode("utf-8")
        assert kbgit.canon_csv(sources, True) == sources
        assert ql_research.insert_rows(before["kb/public/_sources.csv"].decode("utf-8"), [
            ln for ln in sources.splitlines() if ln.startswith(sid + ",")]) == sources
        conflicts = after["kb/public/_conflicts.md"].decode("utf-8")
        assert ql_research.edit_problems("kb/public/_conflicts.md", before["kb/public/_conflicts.md"].decode("utf-8"),
                                         conflicts) == []
        (entry,) = [ln for ln in conflicts.split("\n") if GAP_ID in ln]
        assert f"(line {n} of the article)" in entry and entry.endswith("(topic: windows/laps)")
        assert json.loads((Path(researched[7]) / "querylog" / ql_research.RESEARCH_RUNS_NAME).read_text(
            encoding="utf-8"))["runs"] == 1

    def test_check_passes_after_the_research_run(self, researched):
        home, store, env, *_ = researched
        for tool, want in (("check.py", "errors=0"), ("build_index.py", "")):
            argv = [sys.executable, str(home / "_tools" / tool)] + (["--check"] if tool == "build_index.py" else [])
            p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", env=env, cwd=home, timeout=600)
            assert p.returncode == 0 and want in p.stdout, p.stdout[-600:] + p.stderr[-600:]
        assert ql_store.store_problems(store) == []
        rec = by_id(store)[GAP_ID]
        assert (rec["state"], rec["stage"]) == ("applied", "claim")

    def test_a_second_run_changes_nothing(self, researched):
        home, store, env, said, before, after, *_ = researched
        assert said[3] == "apply: nothing to apply", said
        files = {f: (home / f).read_bytes() for f in after}
        assert files == after
