"""Query log tests, report (kb/_self/querylog.md, Digest and Status; `python3 _tools/tests.py -k TestDigest`, and
the other classes below).

  TestDigest        two copies of one fixture store give byte-identical `digest` output, equal to the expected text;
                    the default week is the newest entry's; findings states stop at the week's Sunday; an empty or
                    missing store and a bad week; distill sums a fetch's result characters
  TestDigestHook    the first SessionStart of an ISO week shows last week's digest once as a systemMessage; mode off,
                    the DISABLED marker and an empty week show nothing; planted: over DIGEST_BUDGET_S shows nothing
                    and is not tried again that week; the hook command prints at most one JSON line and exits 0
  TestStatus        open source findings ranked by result characters, open querylog/ merge requests (glab and gh
                    stubs: GitLab MR API, gh pr list) and KB-Auto reverts; not signed in, a failed call and no origin
                    are skipped with a note; the revert trailer read from a real git log (marker git)
Every run writes under a temporary plugin data directory (conftest.querylog_env), never the clone's own spool, and no
test calls the real `claude`: Haiku is the recorded reply file or a stub. The helpers the classes share are in
ql_testkit.py.
"""
import datetime, json, os, subprocess, sys, time, uuid

import pytest

import ql_distill, ql_report, ql_store
from conftest import querylog_env, Repo
from ql_testkit import learn_store, QL, session_start


# ---------------------------------------------------------------- digest and status (Query log item 9)

W39_RUN = "20260927T100000Z-0000cafe"  # a second run file, in ISO week 2026-W39
W39_FINDINGS = "20260927T230000Z-0000d1ce"  # findings written in 2026-W39
W40_FINDINGS = "20260929T080000Z-0000d2ce"  # findings written in 2026-W40: after the week's end


def f_rec(kind, entry=None, state="open", **kw):
    rec = {"id": ql_store.finding_id(kind, entry if entry else kw.get("signal", ""), kw.get("host", "")),
           "kind": kind, "state": state}
    if entry:
        rec["id"] = ql_store.finding_id(kind, entry)
        rec.update(stage=kw.pop("stage", "miss"), entry=entry)
    rec.update(kw)
    return rec


def write_store_file(path, header, objs):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(o, separators=(",", ":")) + "\n" for o in [header, *objs]), encoding="utf-8",
                    newline="\n")


def digest_store(dst):
    """The fixture store plus a run file and findings files around ISO week 2026-W39: two misses fixed (one since,
    one by apply), a gap still open, two open source findings, and a later record that the week's end must not see."""
    store = learn_store(dst.parent, dst.name)
    a = "55555555-0000-4000-8000-0000000000"
    extra = {"id": "66666666-0000-4000-8000-0000000000a1", "surface": "kb_ask", "day": "2026-09-27", "tools": ["kb_ask"],
             "route": "good", "question": "Which port does WinRM over HTTPS use?", "verdict": "good"}
    write_store_file(store / "2026-09" / f"{W39_RUN}.jsonl",
                     {"run": W39_RUN, "pipeline": 2, "retrieval": 4, "kb_commit": "0" * 40,
                      "counts": {"entries": 1, "dropped": 2, "waiting": 0}}, [extra])
    lap = "public/windows/laps.md"
    w39 = [f_rec("eval", a + "a1", "fixed-since", expect=lap),
           f_rec("eval", a + "a3", "applied", expect="public/intune/win32-apps.md"),
           f_rec("expansion", a + "a3", "applied", article="public/intune/win32-apps.md"),
           f_rec("gap", a + "a4", stage="candidate-gap",
                 promotions=[{"from": "miss", "to": "candidate-gap", "by": "learn"}]),
           f_rec("eval", a + "a2", expect=lap),
           f_rec("alias", a + "a2", article=lap, terms=["zqxlapsor"]),
           f_rec("source", signal="stage", host="learn.microsoft.com", level=0, needs=1, triggers=["failures"]),
           f_rec("source", signal="stage", host="arxiv.org", level=0, needs=1, triggers=["failures"])]
    w40 = [f_rec("alias", a + "a2", "applied", article=lap, terms=["zqxlapsor"]),
           f_rec("eval", a + "a2", "applied", expect=lap)]
    for run, recs in ((W39_FINDINGS, w39), (W40_FINDINGS, w40)):
        write_store_file(store / "findings" / "2026-09" / f"{run}.jsonl",
                         {"run": run, "pipeline": 2, "retrieval": 4, "kb_commit": "0" * 40,
                          "counts": {"findings": len(recs)}}, recs)
    return store


DIGEST_W39 = """query log digest 2026-W39 (2026-09-21 to 2026-09-27)
lookups: 16 (prompt 5, kb_ask 1, tool_fetch 10)
verdicts: good 3, weak 1, none 2, no verdict 10
judged: answered 1, partly 1, missed 3, not judged 11
misses: 4, fixed: 2 (by the kb since 1, by apply 1, by research 0)
fetches: 13, failed 12, result characters 1079632
usage: 0 of 16 lookups
runs: 1, entries dropped by redaction 2
finding records written: 8
findings by kind and state at the week's end:
  eval: open 1, fixed-since 1, applied 1
  alias: open 1
  expansion: applied 1
  gap: open 1
  source: open 2"""


class TestDigest:
    def test_two_copies_of_one_store_give_identical_output(self, tmp_path):
        outs = []
        for name in ("one", "two"):
            store = digest_store(tmp_path / name / "store")
            assert ql_store.store_problems(store) == []
            p = subprocess.run([sys.executable, QL, "digest", "--store", str(store), "--week", "2026-W39"],
                               capture_output=True, timeout=120, cwd=str(tmp_path / name))
            assert p.returncode == 0, p.stderr
            outs.append(p.stdout)
        assert outs[0] == outs[1]
        assert outs[0].decode("utf-8").replace("\r\n", "\n") == DIGEST_W39 + "\n"

    def test_the_default_week_is_the_newest_entrys(self, tmp_path):
        store = digest_store(tmp_path / "store")
        week, lines_, found = ql_report.digest(store)
        assert (week, "\n".join(lines_), found) == ("2026-W39", DIGEST_W39, True)
        assert ql_report.digest(store) == ql_report.digest(store)  # nothing but the store goes in

    def test_the_weeks_end_bounds_the_findings(self, tmp_path):
        store = digest_store(tmp_path / "store")
        week, lines_, found = ql_report.digest(store, "2026-W40")
        text = "\n".join(lines_)
        assert found and "lookups: 0\n" in text and "finding records written: 2" in text
        assert "  eval: fixed-since 1, applied 2" in text and "  alias: applied 1" in text
        assert "runs: 1," in text  # the fixture's run file, written 2026-09-28

    def test_an_empty_or_missing_store_and_a_bad_week(self, tmp_path):
        assert ql_report.digest(tmp_path / "none") == (None, ["query log digest: the store holds no run file"], False)
        store = digest_store(tmp_path / "store")
        assert ql_report.digest(store, "2026-W30")[2] is False
        with pytest.raises(ValueError):
            ql_report.digest(store, "2026-09-27")
        p = subprocess.run([sys.executable, QL, "digest", "--store", str(store), "--week", "last"], capture_output=True,
                           timeout=120)
        assert p.returncode == 2 and b"not an ISO week" in p.stderr

    def test_digest_superseded_gap_is_not_fixed(self, tmp_path):
        """A gap candidate learn superseded (fixed-since) by an eval finding that apply recorded no-fix is no fix:
        the eval finding stands for the miss, and it is not fixed."""
        store = digest_store(tmp_path / "store")
        a4 = "55555555-0000-4000-8000-0000000000a4"
        recs = [f_rec("gap", a4, "fixed-since", stage="candidate-gap",
                      promotions=[{"from": "miss", "to": "candidate-gap", "by": "learn"}]),
                f_rec("eval", a4, "no-fix", stage="candidate-gap", expect="public/windows/laps.md",
                      promotions=[{"from": "miss", "to": "candidate-gap", "by": "apply"}])]
        run = "20260927T233000Z-0000d3ce"
        write_store_file(store / "findings" / "2026-09" / f"{run}.jsonl",
                         {"run": run, "pipeline": 2, "retrieval": 4, "kb_commit": "0" * 40,
                          "counts": {"findings": len(recs)}}, recs)
        text = "\n".join(ql_report.digest(store, "2026-W39")[1])
        assert "  gap: fixed-since 1" in text and "  eval: open 1, fixed-since 1, applied 1, no-fix 1" in text
        assert "misses: 4, fixed: 2 (by the kb since 1, by apply 1, by research 0)" in text

    def test_distill_sums_result_characters_per_fetch(self):
        import redact
        rows = [{"id": "77777777-0000-4000-8000-000000000001", "ts": "2026-09-27T08:00:00.000Z", "surface": "prompt",
                 "prompt": "kb: laps", "kb_intent": "lookup"}]
        for i, c in enumerate((10, 5, None)):
            rows.append({"id": str(uuid.uuid4()), "ts": f"2026-09-27T08:00:0{i + 1}.000Z", "surface": "fetch",
                         "tool": "WebFetch", "host": "learn.microsoft.com", "path": "/en-us/a", "outcome": "unknown",
                         **({"chars": c} if c is not None else {})})
        entry, _, _ = ql_distill.entry_of(rows, redact.known())
        assert entry["fetches"] == [{"tool": "WebFetch", "host": "learn.microsoft.com", "path": "/en-us/a",
                                     "outcome": "unknown", "n": 3, "chars": 15}]


class TestDigestHook:
    MONDAY = datetime.datetime(2026, 9, 28, 7, 0, tzinfo=datetime.timezone.utc)  # 2026-W40: shows 2026-W39

    @pytest.fixture
    def qdir(self, tmp_path, monkeypatch):
        q = tmp_path / "querylog"
        monkeypatch.setattr(ql_report, "places", lambda: (q, q / "config.json"))
        return q

    def test_the_first_session_of_a_week_shows_last_weeks_digest_once(self, tmp_path, qdir):
        store = digest_store(tmp_path / "store")
        line = ql_report.digest_hook(self.MONDAY, store)
        assert json.loads(line) == {"systemMessage": DIGEST_W39}
        assert (qdir / ql_report.DIGEST_MARKER).read_text(encoding="utf-8") == "2026-W40\n"
        assert ql_report.digest_hook(self.MONDAY + datetime.timedelta(days=6, hours=16), store) is None  # Sunday
        nxt = ql_report.digest_hook(self.MONDAY + datetime.timedelta(days=7), store)  # 2026-W41 shows 2026-W40
        assert json.loads(nxt)["systemMessage"].startswith("query log digest 2026-W40 ")

    def test_off_disabled_empty_and_over_budget_show_nothing(self, tmp_path, qdir, monkeypatch):
        store = digest_store(tmp_path / "store")
        qdir.mkdir(parents=True)
        (qdir / "config.json").write_text('{"mode": "off"}', encoding="utf-8")
        assert ql_report.digest_hook(self.MONDAY, store) is None and not (qdir / ql_report.DIGEST_MARKER).exists()
        (qdir / "config.json").unlink()
        (qdir / "DISABLED").touch()
        assert ql_report.digest_hook(self.MONDAY, store) is None and not (qdir / ql_report.DIGEST_MARKER).exists()
        (qdir / "DISABLED").unlink()
        late = datetime.datetime(2026, 12, 1, tzinfo=datetime.timezone.utc)
        assert ql_report.digest_hook(late, store) is None  # an empty week
        assert (qdir / ql_report.DIGEST_MARKER).exists()
        (qdir / ql_report.DIGEST_MARKER).unlink()
        monkeypatch.setattr(ql_report, "DIGEST_BUDGET_S", -1)  # planted: reading the store took too long
        assert ql_report.digest_hook(self.MONDAY, store) is None
        assert (qdir / ql_report.DIGEST_MARKER).read_text(encoding="utf-8") == "2026-W40\n"  # not tried again

    def test_the_hook_command_prints_at_most_one_json_line_and_exits_0(self, tmp_path):
        t0 = time.monotonic()
        p = subprocess.run([sys.executable, QL, "digest", "--hook"], input=json.dumps(session_start()).encode("utf-8"),
                           capture_output=True, env=querylog_env(tmp_path), timeout=60)
        assert p.returncode == 0 and time.monotonic() - t0 < ql_report.DIGEST_HOOK_TIMEOUT_S, p.stderr
        out = p.stdout.decode("utf-8").strip()
        assert out == "" or list(json.loads(out)) == ["systemMessage"]
        assert (tmp_path / "querylog" / ql_report.DIGEST_MARKER).exists()
        p = subprocess.run([sys.executable, QL, "digest", "--hook"], input=b"not json", capture_output=True,
                           env=querylog_env(tmp_path), timeout=60)
        assert (p.returncode, p.stdout) == (0, b"")  # shown once this week already


class StubRun:
    """git, glab and gh answers for status: origin's url, signed in or not, the open merge requests, the log."""

    def __init__(self, url="git@gitlab.corp.example.com:grp/kb.git", signed=True, mrs=None, log="", api_ok=True):
        self.url, self.signed, self.mrs, self.log, self.api_ok, self.calls = url, signed, mrs or [], log, api_ok, []

    def __call__(self, argv, cwd=None):
        self.calls.append(argv)
        if argv[1:3] == ["remote", "get-url"]:
            return (0, self.url + "\n", "") if self.url else (2, "", "error: No such remote 'origin'")
        if argv[1:2] == ["log"]:
            return 0, self.log, ""
        if argv[1:3] == ["auth", "status"]:
            return (0, "", "") if self.signed else (1, "", "You are not logged into any hosts")
        return (0, json.dumps(self.mrs), "") if self.api_ok else (1, "", "HTTP 401")


def status_lines(store, run):
    said = []
    assert ql_report.status(store, home=str(store.parent), run=run, out=said.append) == 0
    return said


class TestStatus:
    LOG = ("1111111\x1fchore(kb): query log apply 20260927T230000Z-0000d1ce\x1feval, expansion, querylog\x1e\n"
           "2222222\x1frevert: query log commit 3333333aa\x1frevert\x1e\n"
           "4444444\x1fdocs(kb): a person's commit\x1f\x1e\n")

    def test_the_three_lists_on_gitlab(self, tmp_path):
        store = digest_store(tmp_path / "store")
        mrs = [{"iid": 12, "source_branch": "querylog/20260927T230000Z-0000d1ce", "title": "chore(kb): query log apply",
                "web_url": "https://gitlab.corp.example.com/grp/kb/-/merge_requests/12"},
               {"iid": 13, "source_branch": "feature/x", "title": "a person's MR", "web_url": "u"}]
        run = StubRun(mrs=mrs, log=self.LOG)
        said = status_lines(store, run)
        assert said == [
            "open source findings, most result characters first: 2",
            f"  1018432 chars  learn.microsoft.com  stage: level 0, needs 1 (failures)  "
            f"{ql_store.finding_id('source', 'stage', 'learn.microsoft.com')}",
            f"  0 chars  arxiv.org  stage: level 0, needs 1 (failures)  "
            f"{ql_store.finding_id('source', 'stage', 'arxiv.org')}",
            "open conflict merge requests (glab on gitlab.corp.example.com): 1",
            "  !12 querylog/20260927T230000Z-0000d1ce  chore(kb): query log apply  "
            "https://gitlab.corp.example.com/grp/kb/-/merge_requests/12",
            "reverted automatic commits: 1",
            "  2222222 revert: query log commit 3333333aa"]
        assert ["glab", "api", "--hostname", "gitlab.corp.example.com",
                "projects/grp%2Fkb/merge_requests?state=opened&target_branch=main&per_page=100"] in run.calls

    def test_github_lists_pull_requests(self, tmp_path):
        store = digest_store(tmp_path / "store")
        prs = [{"number": 4, "headRefName": "querylog/20260927T230000Z-0000d1ce", "title": "t", "url": "https://x/4"}]
        run = StubRun(url="https://github.com/o/r.git", mrs=prs)
        said = status_lines(store, run)
        assert "open conflict merge requests (gh on github.com): 1" in said
        assert "  #4 querylog/20260927T230000Z-0000d1ce  t  https://x/4" in said
        assert ["gh", "pr", "list", "-R", "github.com/o/r", "--base", "main", "--state", "open",
                "--json", "number,title,headRefName,url", "-L", "100"] in run.calls

    @pytest.mark.parametrize("run,note", [
        (StubRun(signed=False), "not checked: glab is not signed in to gitlab.corp.example.com (You are not logged"),
        (StubRun(api_ok=False), "not checked: glab api failed (HTTP 401)"),
        (StubRun(url=None), "not checked: no remote origin"),
    ])
    def test_merge_requests_are_skipped_with_a_note(self, tmp_path, run, note):
        said = status_lines(digest_store(tmp_path / "store"), run)
        assert any(line.startswith("open conflict merge requests: " + note) for line in said), said
        if not run.signed or not run.url:
            assert not [c for c in run.calls if c[:2] in (["glab", "api"], ["gh", "pr"])]  # no API call

    @pytest.mark.git
    def test_reverted_commits_come_from_the_trailer(self, tmp_path):
        """In a real repository: the KB-Auto trailers of git log, one revert among them."""
        repo = Repo(tmp_path / "clone")
        os.makedirs(repo.path)
        repo.git("init", "-q")
        for text, msg in (("a\n", "chore(kb): query log apply x\n\nKB-Auto: eval"),
                          ("b\n", "revert: query log commit abc\n\nKB-Auto: revert"),
                          ("c\n", "docs: a body that names KB-Auto: revert\n\nno trailer here.\n\nOther: x")):
            repo.write("a.txt", text)
            repo.git("add", "a.txt")
            repo.git("commit", "-q", "-m", msg)

        def run(argv, cwd=None):
            p = subprocess.run(argv, cwd=cwd, env=repo.env, capture_output=True, text=True, encoding="utf-8")
            return p.returncode, p.stdout, p.stderr
        got = ql_report.reverted_commits(repo.path, run)
        assert [s for _, s in got] == ["revert: query log commit abc"]
