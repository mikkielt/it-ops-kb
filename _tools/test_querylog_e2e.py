"""Query log end to end (kb/_self/querylog.md; `python3 _tools/tests.py -k e2e`).

Each scenario drives a clone of a kb copy whose `origin` is a local bare repository through the whole pipeline:
capture (the query log hook commands of the clone's .claude/settings.json, fed the recorded events of
_tools/fixtures/querylog/e2e.json on stdin: capture, kb_hook.py, and the SessionEnd launcher), distill with the
recorded Haiku replies of that file, then the push of mode `auto` (querylog.Pusher: the worktree's own
`querylog.py learn` and `apply`, then its `kbgit.py sync --push`). After each scenario the tests check the store on the
remote, the findings, the eval file, the ledgers, the spool and the gate (the store gates and check-trailers).

  TestAnswered      a kb: lookup the hook answered with `good`: one entry, no finding, only the run file pushed; the
                    hook's answer is kb_hook.answer's
  TestFixes         a miss fixed by an alias, one fixed by an expansion and one with no article that answers it (a
                    _gaps.md entry under its topic), in one push; a second run on unchanged inputs changes nothing;
                    red CI on that push gives a revert and `apply-failed`, and nothing is applied again
  TestFixedSince    a miss that passes on HEAD by the time learn runs: `fixed-since`, no change to the kb
  TestFetches       web, docs-server and curl fetches beside a kb lookup keep host and path only; a fetch in a prompt
                    that never used the kb writes no row
  TestToolRows      kb_ask.py, fetch.py and census.py rows join the prompt whose window holds them
  TestRedaction     identifiers in a prompt are redacted before Haiku and in the run file; an entry Haiku flags as
                    still identifying is dropped and only counted
  TestCaps          more entries than the Haiku caps allow: the rest wait in the spool, and later runs take them
  TestTwoClones     two clones distilling against one remote, the second pushing after the first moved main:
                    separate run files, no entry id twice, no conflict
  TestConflict      a conflict with origin/main: the querylog/<run-id> branch with the merge-request push options,
                    main unchanged, the findings pending and held on the next run
  TestCiNotRed      unfinished CI holds the push; `manual` and `skipped` are not red
  TestResearch      research on within its daily cap (a quote-checked fact and a _conflicts.md entry), over its cap,
                    and off
  test_modes        modes `off`, `local`, `auto` and the default (no file), the DISABLED marker, an unreadable config
  TestSessions      an open session is not distilled; one closed by SessionEnd and one idle for a day are
  TestPushFailure   a refused push keeps the spool; the next push delivers, and the spool goes after it

The SessionEnd hook runs while the test holds the distill lock, so the launcher marks the session closed and starts
no distill of its own: distill runs in this process with the recorded Haiku and with `glab` and `gh` as stubs. The
worktree's research answers from a recorded reply and page. Nothing reaches the network or the real `claude`, and
nothing is written to this clone's own spool. Every scenario is marked `git` (tests.py runs them; KB_TESTS_FAST=1,
kbgit.py sync's gate, leaves them out).
"""
import datetime, json, os, re, shlex, shutil, subprocess, sys, time, uuid
from pathlib import Path

import pytest

import querylog
from conftest import GIT, Repo, copy_kb, git_env
from test_querylog import (ALIAS_Q, BAD_QUOTE, FIXTURES, LAPS, LAPS_GAP_Q, LEGACY_QUOTE, PAGE, PAGE_URL, PARAPHRASE_Q,
                           PUSH_OPTIONS_HOOK, REJECT_HOOK, SH, c, cand, jsonl, pipeline, prompt, reply, serve, signed_out,
                           stop, tool)

pytestmark = [pytest.mark.skipif(not GIT, reason="git is not installed"), pytest.mark.git]

LOOKUPS = json.loads((FIXTURES / "e2e.json").read_text(encoding="utf-8"))["lookups"]
PIPELINE_HOOKS = ("_tools/querylog.py capture", "_tools/kb_hook.py", "_tools/querylog.py launch")
EVAL, ALIASES, EXPANSIONS = ("kb/public/_retrieval/lookup_eval.csv", "_tools/aliases.csv",
                             "kb/public/_retrieval/doc2query/expansions.csv")
GAPS, CONFLICTS, SOURCES, ARTICLE = ("kb/public/_gaps.md", "kb/public/_conflicts.md", "kb/public/_sources.csv",
                                     "kb/public/windows/laps.md")
KB_FILES = (EVAL, ALIASES, EXPANSIONS, GAPS, CONFLICTS, SOURCES, ARTICLE)
RUN_TOOL = {  # a request made inside fetch.py or census.py, as the script makes it (the row names the script)
    "fetch.py": "import sys; sys.argv[0] = 'fetch.py'; import fetch; fetch.DELAY = 0; fetch.fetch(sys.argv[1])",
    "census.py": "import sys; sys.argv[0] = 'census.py'; import census; census.fetch(sys.argv[1])"}
RAW = ["anna.nowak", "acme-corp", "10." + "1.20.33", "PL-LAPTOP-7731", "Nowakowski", "secret", "token=abc", "tabs=",
       "#enable", "view=x", "city=", "weather", "BODY", "session_id", "prompt_id", '"prompt":', '"answer":']


def env():
    """A git scenario's environment (conftest.git_env) with no plugin, project or cloud variables, so every tool runs
    as it does in a clone; kbgit.py sync gates without tests.py (KB_SYNC_NO_TESTS=1); localhost needs no proxy."""
    e = git_env(KB_SYNC_NO_TESTS="1", NO_PROXY="*", no_proxy="*")
    for k in ("CLAUDE_PLUGIN_ROOT", "CLAUDE_PLUGIN_DATA", "CLAUDE_PROJECT_DIR", "CLAUDE_CODE_REMOTE", "KB_INDEX"):
        e.pop(k, None)
    return e


@pytest.fixture(scope="session")
def seed(tmp_path_factory):
    """A bare repository of a kb copy with no committed store, and its commit: every scenario's origin starts there.
    Under pytest-xdist the first worker builds it in the run's shared temporary directory and the others wait for it."""
    base = tmp_path_factory.getbasetemp()
    tmp = (base.parent if os.environ.get("PYTEST_XDIST_WORKER") else base) / "e2e-seed"
    done = tmp / "seed.json"
    try:
        tmp.mkdir()
    except FileExistsError:
        deadline = time.monotonic() + 900
        while not done.exists():
            assert time.monotonic() < deadline, f"no seed at {tmp}"
            time.sleep(0.2)
        got = json.loads(done.read_text(encoding="utf-8"))
        assert "error" not in got, got
        return Path(got["bare"]), got["base"]
    got = {"error": "not built"}
    try:
        repo = Repo(copy_kb(str(tmp / "seed"), skip=("_fetch_state.csv", "_querylog")), env())
        repo.git("init", "-q", "-b", "main")
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "base")
        Repo(tmp, env()).git("clone", "-q", "--bare", repo.path, str(tmp / "seed.git"))
        got = {"bare": str(tmp / "seed.git"), "base": repo.rev("HEAD")}
    finally:
        querylog.write_text(done, json.dumps(got))
    return Path(got["bare"]), got["base"]


class Haiku:
    """The recorded Haiku replies of e2e.json: each entry of a batch is answered with the reply of the one lookup
    whose `match` (default: its prompt) is in the entry's rule-redacted prompt. Keeps every batch it was sent."""

    def __init__(self):
        self.batches = []

    def __call__(self, text):
        items = json.loads(text[text.index("\n\n[") + 2:])
        self.batches.append(items)
        out = []
        for it in items:
            hits = [lk["haiku"] for lk in LOOKUPS.values() if "haiku" in lk and lk.get("match", lk["prompt"]) in it["prompt"]]
            assert len(hits) == 1, f"no single recorded reply for {it['prompt']!r}"
            out.append({"i": it["i"], **hits[0]})
        return json.dumps(out)

    def sent(self):
        return json.dumps(self.batches, ensure_ascii=False)


class World:
    """One scenario: `origin` (a bare repository cloned from the seed, or `remote`), the person's clone of it, and
    the clone's query log directory. Runs the hooks, distill and the push; reads back what the remote holds."""

    def __init__(self, tmp, seed, name="a", remote=None):
        self.tmp, self.env = Path(tmp), env()
        bare, self.base = seed
        top = Repo(self.tmp, self.env)
        if remote is None:
            remote = Repo(self.tmp / f"{name}.git", self.env)
            top.git("clone", "-q", "--bare", str(bare), remote.path)
        self.remote = remote
        self.clone = Repo(self.tmp / name, self.env)
        top.git("clone", "-q", remote.path, self.clone.path)
        self.home = Path(self.clone.path)
        self.q = self.home / "_cache" / "querylog"
        self.cfg = self.home / "_private" / "querylog.json"
        self.settings = json.loads((self.home / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.haiku = Haiku()
        self.ci = signed_out
        self.calls = []  # glab and gh argument lists
        self.replay = None  # the recorded research reply file the worktree's apply answers from
        self.server = None  # the local HTTP server's url for fetch.py and census.py

    # --- the person's side: config, hooks, tools --------------------------------------------------------------------

    def config(self, text):
        self.cfg.parent.mkdir(parents=True, exist_ok=True)
        self.cfg.write_text(text if isinstance(text, str) else json.dumps(text), encoding="utf-8", newline="\n")

    def argv(self, command):
        """A hook command as Claude Code runs it: through sh (Git Bash on Windows), else its script with this Python."""
        if SH:
            return [SH, "-c", command]
        words = shlex.split(command)  # sh "${CLAUDE_PROJECT_DIR}/_tools/kbpy" <script> [args]
        return [sys.executable, str(self.home / words[2]), *words[3:]]

    def hook(self, event):
        """Every query log hook the clone's settings run on `event`, the event on stdin: [(command, stdout)]."""
        name, out = event["hook_event_name"], []
        for m in self.settings["hooks"].get(name, []):
            if name.startswith("PostTool") and not re.fullmatch(m.get("matcher", ".*"), event["tool_name"]):
                continue
            for h in m["hooks"]:
                if not h["command"].endswith(PIPELINE_HOOKS):
                    continue
                p = subprocess.run(self.argv(h["command"]), input=json.dumps(event, ensure_ascii=False).encode("utf-8"),
                                   capture_output=True, cwd=self.home, timeout=300,
                                   env={**self.env, "CLAUDE_PROJECT_DIR": str(self.home).replace("\\", "/")})
                assert p.returncode == 0, (h["command"], p.stderr)
                out.append((h["command"], p.stdout.decode("utf-8")))
        return out

    def run_tool(self, call):
        if call["run"] == "kb_ask.py":
            argv, cwd = [sys.executable, str(self.home / "_tools" / "kb_ask.py"), *call["args"]], self.home
        else:
            argv, cwd = [sys.executable, "-c", RUN_TOOL[call["run"]], self.server + call["path"]], self.home / "_tools"
        p = subprocess.run(argv, cwd=cwd, env=self.env, capture_output=True, timeout=300)
        assert p.returncode == 0, p.stderr

    def lookup(self, name, sid):
        """The recorded lookup `name` in session `sid`: its prompt, each call (PostToolUse, PostToolUseFailure, or a
        tool the session runs), then Stop. The kb: hook's stdout, or ''."""
        lk, pid = LOOKUPS[name], f"{name}-{uuid.uuid4().hex[:8]}"
        said = self.hook(prompt(c(lk["prompt"]), pid, sid))
        for call in lk.get("calls", []):
            if "run" in call:
                self.run_tool(call)
            elif "error" in call:
                self.hook(tool(call["tool"], call["input"], pid=pid, ok=False, error=call["error"], sid=sid))
            else:
                self.hook(tool(call["tool"], call["input"], call["response"], pid=pid, sid=sid))
        if "answer" in lk:
            self.hook(stop(lk["answer"], pid, sid))
        return next((o for cmd, o in said if cmd.endswith("kb_hook.py")), "")

    def end(self, sid):
        """The SessionEnd hook, run while this process holds the distill lock: the launcher marks the session closed
        and starts nothing."""
        lock = querylog.acquire(self.q)
        assert lock is not None
        try:
            self.hook({"hook_event_name": "SessionEnd", "session_id": sid, "reason": "prompt_input_exit"})
        finally:
            querylog.release(lock)

    # --- the pipeline ---------------------------------------------------------------------------------------------

    def run(self, argv, cwd=None):
        if argv[0] in ("glab", "gh"):
            self.calls.append(list(argv))
            return self.ci(argv)
        return querylog.run_cmd(argv, cwd=cwd, env=self.env)

    def pusher(self, out, now, step=None):
        """The push of `apply --push` for this clone: its worktree's learn and apply (research from the clone's config,
        answered from `replay`), then kbgit.py sync --push. `step(pusher, wt, store, hold, out)` wraps learn and
        apply."""
        research = ["--clone", str(self.home)] + (["--replay-research", str(self.replay)] if self.replay else [])
        p = querylog.Pusher(self.home, self.q, self.run, None, out, now, research=research, cloud=False)
        if step:
            p.apply_step = lambda wt, store, hold, o: step(p, wt, store, hold, o)
        return p

    def distill(self, now=None, step=None):
        """One distill (the mode of the clone's config), with the push of mode `auto`: (exit code, output lines)."""
        said, now = [], now or datetime.datetime.now(datetime.timezone.utc)
        rc = querylog.distill(qdir=self.q, cfg=self.cfg, haiku=self.haiku, now_dt=now, kb_commit=self.clone.rev("HEAD"),
                              out=said.append, deliver=lambda q, out: self.pusher(out, now, step)())
        return rc, said

    # --- what there is to check ---------------------------------------------------------------------------------------

    def main(self):
        return self.remote.rev("main")

    def show(self, rel, rev="main"):
        p = self.remote.run_git("show", f"{rev}:{rel}")
        return p.stdout if p.returncode == 0 else None

    def added(self, rel, rev="main"):
        """The lines of `rel` at `rev` that the seed does not have."""
        base = set((self.show(rel, self.base) or "").splitlines())
        return [ln for ln in (self.show(rel, rev) or "").splitlines() if ln not in base]

    def store(self, rev="main"):
        """The remote's kb/_querylog at `rev`, written out under the scenario's directory."""
        d = self.tmp / f"store-{uuid.uuid4().hex[:8]}"
        names = self.remote.git("ls-tree", "-r", "--name-only", rev, "--", querylog.STORE_REL).split()
        for n in names:
            (d / n).parent.mkdir(parents=True, exist_ok=True)
            (d / n).write_text(self.show(n, rev), encoding="utf-8", newline="\n")
        return d / querylog.STORE_REL

    def spool(self):
        sp = self.q / "spool"
        return sorted(p.name for p in sp.iterdir()) if sp.is_dir() else []

    def local_runs(self):
        return querylog.run_files(self.q / "store")

    def state(self, rev="main"):
        """What the remote holds at `rev` and what the clone keeps: run files, entries, findings, the kb files'
        added lines, the spool, and the gate (the store gates and the leak scan, check-trailers, the person's checkout
        untouched)."""
        store = self.store(rev)
        runs = querylog.run_files(store)
        rels = [p.relative_to(store).as_posix() for p in runs + querylog.findings_files(store)]
        self.clone.git("fetch", "-q", "origin")
        trailers = self.clone.kbgit("check-trailers", f"{self.base}..origin/main")
        return {
            "runs": [p.stem for p in runs],
            "headers": [jsonl(p)[0] for p in runs],
            "entries": [e for p in runs for e in jsonl(p)[1:]],
            "findings": querylog.finding_states(store),
            "text": "".join(p.read_text(encoding="utf-8") for p in sorted(store.rglob("*.jsonl"))),
            **{rel: self.added(rel, rev) for rel in KB_FILES},
            "spool": self.spool(),
            "gate": querylog.store_problems(store) + querylog.leak_problems(store, rels) +
                    ([] if trailers.returncode == 0 else [trailers.stdout.strip()]) +
                    [f"person's checkout: {s}" for s in [self.clone.git("status", "--porcelain").strip()] if s] +
                    ([] if self.clone.rev("HEAD") == self.base else ["person's checkout moved"]),
        }

    def commits(self, since=None):
        """[(subject, KB-Auto values)] of the remote's main after `since` (default: the seed), oldest first."""
        revs = self.remote.git("rev-list", "--reverse", f"{since or self.base}..main").split()
        return [(self.remote.git("log", "-1", "--format=%s", r).strip(),
                 self.remote.git("log", "-1", "--format=%(trailers:key=KB-Auto,valueonly)", r).strip()) for r in revs]


def kinds(findings):
    return sorted((r["kind"], r["state"], r.get("stage", "")) for r in findings.values())


def question(entries, name):
    return next(e for e in entries if e.get("question") == LOOKUPS[name]["asked"])


def bullets(lines):
    return [ln for ln in lines if ln.startswith("- ")]


def says(lines, text):
    return any(text in s for s in lines)


def sid():
    return str(uuid.uuid4())


# ---------------------------------------------------------------- one lookup answered by the kb: hook

class TestAnswered:
    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory, seed):
        w = cls.w = World(tmp_path_factory.mktemp("e2e-answered"), seed)
        s = sid()
        cls.answer = w.lookup("win32", s)
        w.end(s)
        cls.rc, cls.said = w.distill()
        cls.st = w.state()

    def test_an_entry_no_finding_and_only_the_run_file(self):
        import kb_hook
        st, w = self.st, self.w
        assert self.rc == 0 and says(self.said, "entries=1 dropped=0 waiting=0"), self.said
        assert json.loads(self.answer) == kb_hook.answer(c(LOOKUPS["win32"]["prompt"]))  # the hook's answer is unchanged
        (e,) = st["entries"]
        assert (e["surface"], e["intent"], e["tools"], e["verdict"], e["judged"]) == \
            ("prompt", "lookup", ["kb_hook"], "good", "answered")
        assert "public/intune/win32-apps.md" in e["articles"] and e["question"] == LOOKUPS["win32"]["asked"]
        assert st["findings"] == {} and w.commits() == [("chore(kb): query log store, 1 run file(s)", "querylog")]
        assert all(st[rel] == [] for rel in KB_FILES)
        assert st["spool"] == [] and st["gate"] == [], st["gate"]


# ---------------------------------------------------------------- misses: an alias, an expansion, a gap entry

class TestFixes:
    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory, seed):
        w = cls.w = World(tmp_path_factory.mktemp("e2e-fixes"), seed)
        s = sid()
        for name in ("alias", "expansion", "gap"):
            w.lookup(name, s)
        w.end(s)
        cls.first = w.distill()
        cls.main1, cls.st1, cls.commits1 = w.main(), w.state(), w.commits()
        cls.local1 = {p: p.read_bytes() for p in (w.q / "store").rglob("*") if p.is_file()}
        cls.again = w.distill()
        cls.main2 = w.main()
        cls.local2 = {p: p.read_bytes() for p in (w.q / "store").rglob("*") if p.is_file()}
        w.ci = pipeline("failed")
        cls.red = w.distill()
        cls.main3, cls.st3 = w.main(), w.state()
        cls.after = w.distill()
        cls.main4, cls.st4 = w.main(), w.state()

    def test_an_alias_an_expansion_and_a_gap_entry(self):
        import kbid
        (rc, said), st = self.first, self.st1
        assert rc == 0 and says(said, "entries=3 dropped=0 waiting=0"), said
        assert [v for _, v in self.commits1] == ["querylog", "alias, eval, expansion, gap, querylog"], self.commits1
        assert sorted(st[EVAL]) == sorted([f"{kbid.eval_id(q)},{q},windows/laps.md,good," for q in (PARAPHRASE_Q, ALIAS_Q)])
        assert st[ALIASES] == ["zqxlapsor,laps"] and len(st[EXPANSIONS]) == 1 and PARAPHRASE_Q in st[EXPANSIONS][0]
        (gap,) = bullets(st[GAPS])
        assert gap.startswith(f"- **{LAPS_GAP_Q}** ") and gap.endswith("(topic: windows/laps)"), gap
        text = self.w.show(GAPS, self.main1)
        section = text[text.rindex("\n## windows/laps\n"):]
        assert gap in section.split("\n## ", 2)[1]  # at the end of its topic's section
        assert kinds(st["findings"]) == [("alias", "applied", "miss"), ("eval", "applied", "miss"),
                                         ("eval", "applied", "miss"), ("expansion", "applied", "miss"),
                                         ("gap", "applied", "gap")]
        g = next(r for r in st["findings"].values() if r["kind"] == "gap")
        assert g["article"] == LAPS and g["id"] in gap
        assert [p["to"] for p in g["promotions"]] == ["candidate-gap", "gap"]
        assert all(st[rel] == [] for rel in (CONFLICTS, SOURCES, ARTICLE))
        assert st["spool"] == [] and st["gate"] == [], st["gate"]

    def test_a_second_run_changes_nothing(self):
        rc, said = self.again
        assert rc == 0 and said[0] == "distill: nothing to write (waiting=0)", said
        assert says(said, "apply --push: nothing to push") and self.main2 == self.main1, said
        assert self.local2 == self.local1  # the local store: no run or findings file
        assert self.w.haiku.batches and len(self.w.haiku.batches) == 1  # Haiku's output is never regenerated

    def test_red_ci_gives_a_revert_apply_failed_and_no_retry(self):
        (rc, said), st, w = self.red, self.st3, self.w
        assert rc == 0 and says(said, f"CI of the last automatic commit {self.main1[:9]} is red"), said
        subjects = [s for s, _ in w.commits(self.main1)]
        assert subjects and subjects[0] == f"revert: query log commit {self.main1[:9]}", subjects
        for rel in (EVAL, ALIASES, EXPANSIONS, GAPS):
            assert st[rel] == [], rel  # the fixes are gone from main
        assert set(self.st1["runs"]) == set(st["runs"])  # the store's files stay
        failed = sorted(r["kind"] for r in st["findings"].values() if r["state"] == querylog.APPLY_FAILED)
        assert failed == ["alias", "eval", "eval", "expansion", "gap"], failed
        assert st["gate"] == [], st["gate"]
        rc, said = self.after  # the next run: CI on a revert is not checked, and nothing is applied again
        assert rc == 0 and says(said, "apply --push: nothing to push") and self.main4 == self.main3, said
        assert self.st4[EVAL] == [] and self.st4[GAPS] == [] and self.st4["gate"] == []


# ---------------------------------------------------------------- a miss the kb answers on HEAD

class TestFixedSince:
    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory, seed):
        w = cls.w = World(tmp_path_factory.mktemp("e2e-fixed"), seed)
        s = sid()
        w.lookup("fixed_since", s)
        w.end(s)
        cls.rc, cls.said = w.distill()
        cls.st = w.state()

    def test_fixed_since_and_no_change(self):
        st, w = self.st, self.w
        assert self.rc == 0, self.said
        (e,) = st["entries"]
        assert (e["verdict"], e["judged"], e["best"]) == ("weak", "partly", LAPS)
        assert kinds(st["findings"]) == [("eval", "fixed-since", "miss")]
        assert [v for _, v in w.commits()] == ["querylog", "querylog"]  # the run file, then learn's findings
        assert all(st[rel] == [] for rel in KB_FILES)
        assert st["spool"] == [] and st["gate"] == [], st["gate"]


# ---------------------------------------------------------------- fetches beside a lookup, and without one

class TestFetches:
    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory, seed):
        w = cls.w = World(tmp_path_factory.mktemp("e2e-fetches"), seed)
        s = sid()
        w.lookup("fetches", s)
        w.lookup("plain_fetch", s)
        cls.rows = [json.loads(ln) for ln in (w.q / "spool" / f"{s}.jsonl").read_text(encoding="utf-8").splitlines()]
        w.end(s)
        cls.rc, cls.said = w.distill()
        cls.st = w.state()

    def test_host_and_path_only_and_no_row_without_the_kb(self):
        st = self.st
        assert [r["surface"] for r in self.rows] == ["prompt", "mcp", "fetch", "fetch", "fetch", "fetch", "stop", "prompt"]
        assert self.rc == 0 and says(self.said, "entries=1 dropped=0 waiting=0"), self.said
        (e,) = st["entries"]
        assert sorted((f["tool"], f.get("fetcher"), f["host"], f["path"], f["outcome"]) for f in e["fetches"]) == [
            ("Bash", "curl", "learn.microsoft.com", "/en-us/windows-server/identity/laps/laps-management-policy-settings",
             "unknown"),
            ("WebFetch", None, "learn.microsoft.com", "/en-us/windows-server/identity/laps/gone", "http-404"),
            ("WebFetch", None, "learn.microsoft.com", "/en-us/windows-server/identity/laps/laps-scenarios-azure-active-"
                                                      "directory", "unknown"),
            ("mcp__microsoft-learn__microsoft_docs_fetch", None, "learn.microsoft.com",
             "/en-us/windows-server/identity/laps/laps-overview", "unknown")]
        for raw in RAW:
            assert raw not in st["text"], raw
        # the kb's own question and the kb lines it returned; nothing of the prompt as typed or of the reply
        assert (e["question"], e["cited"]) == (LOOKUPS["fetches"]["asked"], "pack") and "summary" not in e
        assert e["citations"] == [{"line": "public/windows/laps.md:18", "verdict": "good"}]
        for word in ("How do I", "turn on", "Entra admin center", "recovery"):
            assert word not in st["text"], word
        assert {r["kind"] for r in st["findings"].values()} <= {"source"}  # report-only, never applied
        assert all(st[rel] == [] for rel in KB_FILES)
        assert st["spool"] == [] and st["gate"] == [], st["gate"]


# ---------------------------------------------------------------- tools that write their own rows

class TestToolRows:
    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory, seed):
        w = cls.w = World(tmp_path_factory.mktemp("e2e-tools"), seed)
        s = sid()
        with serve() as url:
            w.server = url
            w.lookup("tools", s)
        cls.tools = sorted(p.name for p in (w.q / "spool").glob("tools-*.jsonl"))
        w.end(s)
        cls.rc, cls.said = w.distill()
        cls.st = w.state()

    def test_kb_ask_fetch_and_census_rows_join_their_prompt(self):
        st, w = self.st, self.w
        assert self.rc == 0 and says(self.said, "entries=1 dropped=0 waiting=0"), self.said
        (e,) = st["entries"]  # one entry: the prompt with the three tools' rows, none of their own
        assert (e["surface"], e["tools"], e["route"], e.get("intent")) == \
            ("prompt", ["kb_ask", "fetch.py", "census.py"], "plan", None)
        assert e["question"] == LOOKUPS["tools"]["asked"] and "route kb_ask takes" not in st["text"]  # kb_ask's own
        assert e["citations"] and all(querylog.CITATION.fullmatch(x["line"]) for x in e["citations"])
        assert sorted((f["tool"], f["outcome"], f["n"], f.get("chars")) for f in e["fetches"]) == [
            ("census.py", "http-404", 1, None), ("fetch.py", "http-200", 1, 5)]
        assert not any("host" in f for f in e["fetches"])  # 127.0.0.1 is no public host
        assert len(self.tools) == 1 and st["spool"] in ([], self.tools)  # today's tools file goes after its day
        consumed = json.loads((w.q / querylog.CONSUMED_NAME).read_text(encoding="utf-8")) if st["spool"] else {}
        assert all(len(ids) == 3 for ids in consumed.values())
        assert st["gate"] == [], st["gate"]


# ---------------------------------------------------------------- redaction

class TestRedaction:
    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory, seed):
        w = cls.w = World(tmp_path_factory.mktemp("e2e-redact"), seed)
        s = sid()
        w.lookup("identifier", s)
        w.lookup("identifying", s)
        w.end(s)
        cls.rc, cls.said = w.distill()
        cls.st = w.state()

    def test_an_identifier_is_redacted_and_an_identifying_entry_dropped(self):
        st, w = self.st, self.w
        assert self.rc == 0 and says(self.said, "entries=1 dropped=1 waiting=0"), self.said
        (h,) = st["headers"]
        assert h["counts"] == {"entries": 1, "dropped": 1, "waiting": 0}
        (e,) = st["entries"]
        assert e["question"] == LOOKUPS["identifier"]["asked"]
        assert "Nowakowski" not in st["text"] and "Autopilot" not in st["text"]  # only its count is kept
        sent = w.haiku.sent()
        for raw in ("anna.nowak", "acme-corp", "10." + "1.20.33", "PL-LAPTOP-7731"):
            assert raw not in sent and raw not in st["text"], raw
        assert "PL-LT-00123" in sent and "jan.kowalski@corp.example.com" in sent
        assert st["spool"] == [] and st["gate"] == [], st["gate"]


# ---------------------------------------------------------------- the Haiku caps

class TestCaps:
    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory, seed):
        w = cls.w = World(tmp_path_factory.mktemp("e2e-caps"), seed)
        s = sid()
        for name in ("win32", "laps_length", "do_port"):
            w.lookup(name, s)
        w.end(s)
        now = datetime.datetime.now(datetime.timezone.utc)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(querylog, "HAIKU_BATCH_ENTRIES", 2)
            mp.setattr(querylog, "HAIKU_BATCHES_PER_RUN", 1)
            mp.setattr(querylog, "HAIKU_DAILY_CALLS", 1)
            cls.first = w.distill(now)
            cls.spool1, cls.st1 = w.spool(), w.state()
            cls.second = w.distill(now + datetime.timedelta(minutes=1))
            cls.calls2 = len(w.haiku.batches)
            cls.third = w.distill(now + datetime.timedelta(days=1))
        cls.st3 = w.state()

    def test_the_rest_wait_and_the_next_runs_take_them(self):
        w = self.w
        rc, said = self.first
        assert rc == 0 and says(said, "entries=2 dropped=0 waiting=1"), said
        assert len(self.st1["entries"]) == 2 and self.spool1, self.spool1  # the waiting lookup's rows stay
        rc, said = self.second
        assert rc == 0 and said[0] == "distill: nothing to write (waiting=1)" and self.calls2 == 1, said  # daily cap
        rc, said = self.third
        assert rc == 0 and says(said, "entries=1 dropped=0 waiting=0") and len(w.haiku.batches) == 2, said
        st = self.st3
        assert len(st["runs"]) == 2 and len(st["entries"]) == 3
        assert sorted(e["question"] for e in st["entries"]) == sorted(
            LOOKUPS[n]["asked"] for n in ("win32", "laps_length", "do_port"))
        assert st["spool"] == [] and st["gate"] == [], st["gate"]


# ---------------------------------------------------------------- two clones, one remote

class TestTwoClones:
    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory, seed):
        tmp = tmp_path_factory.mktemp("e2e-two")
        a = cls.a = World(tmp, seed, "a")
        b = cls.b = World(tmp, seed, "b", remote=a.remote)
        sa, sb = sid(), sid()
        a.lookup("win32", sa)
        a.end(sa)
        b.lookup("fixed_since", sb)
        b.end(sb)
        cls.a_run = []

        def meanwhile(p, wt, store, hold, out):
            rc = p.learn_and_apply(wt, store, hold, out)
            cls.a_run.append(a.distill())  # the other clone distills and pushes while this one is between its commits
            return rc
        cls.b_run = b.distill(step=meanwhile)
        cls.st = b.state()
        cls.a_spool = a.spool()
        cls.branches = a.remote.git("for-each-ref", "--format=%(refname)", "refs/heads").split()

    def test_separate_run_files_no_duplicate_id_no_conflict(self):
        ((rc_a, said_a),), (rc_b, said_b) = self.a_run, self.b_run
        assert rc_a == 0 and says(said_a, "apply --push: pushed "), said_a
        assert rc_b == 0 and says(said_b, "apply --push: pushed ") and not says(said_b, "conflict"), said_b
        st = self.st
        assert len(st["runs"]) == 2 and len({e["id"] for e in st["entries"]}) == 2
        assert querylog.duplicate_ids(self.b.store()) == []
        assert self.branches == ["refs/heads/main"]
        assert kinds(st["findings"]) == [("eval", "fixed-since", "miss")]
        assert st["spool"] == [] and self.a_spool == [] and st["gate"] == [], st["gate"]


# ---------------------------------------------------------------- a conflict with origin/main

class TestConflict:
    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory, seed):
        tmp = tmp_path_factory.mktemp("e2e-conflict")
        w = cls.w = World(tmp, seed)
        w.remote.git("config", "receive.advertisePushOptions", "true")
        hook = Path(w.remote.path) / "hooks" / "pre-receive"
        hook.write_text(PUSH_OPTIONS_HOOK, encoding="utf-8", newline="\n")
        hook.chmod(0o755)
        planter = Repo(tmp / "planter", w.env)
        Repo(tmp, w.env).git("clone", "-q", w.remote.path, planter.path)
        s = sid()
        w.lookup("gap", s)
        w.end(s)

        def plant(p, wt, store, hold, out):
            """learn and apply, then another clone pushes a different file at the path of apply's findings file."""
            before = set(Path(store).rglob("*.jsonl"))
            rc = p.learn_and_apply(wt, store, hold, out)
            new = max(set(Path(store).rglob("*.jsonl")) - before, key=lambda f: f.stem)
            cls.planted_rel = new.relative_to(wt).as_posix()
            header = {"run": new.stem, "pipeline": querylog.PIPELINE_VERSION, "retrieval": querylog.retrieval_version(),
                      "kb_commit": "0" * 40, "counts": {"findings": 0}}
            planter.write(cls.planted_rel, json.dumps(header, separators=(",", ":")) + "\n")
            planter.git("add", "-A")
            planter.git("commit", "-q", "-m", "chore(kb): planted findings file")
            planter.git("push", "-q", "origin", "HEAD:main")
            cls.planted = planter.rev("HEAD")
            return rc
        cls.first = w.distill(step=plant)
        cls.main1, cls.spool1 = w.main(), w.spool()
        cls.refs1 = w.remote.git("for-each-ref", "--format=%(refname)", "refs/heads").split()
        cls.opts = (Path(w.remote.path) / "push-options.txt").read_text(encoding="utf-8").splitlines()
        cls.again = w.distill()
        cls.st = w.state()
        cls.refs2 = w.remote.git("for-each-ref", "--format=%(refname)", "refs/heads").split()

    def test_a_branch_with_the_mr_options_findings_pending_and_held(self):
        w = self.w
        rc, said = self.first
        assert rc == 0, said
        (line,) = [s for s in said if "conflict: pushed" in s]
        branch = line.split("pushed ", 1)[1].split(" ", 1)[0]
        assert branch == querylog.CONFLICT_BRANCH_PREFIX + Path(self.planted_rel).stem
        assert self.main1 == self.planted  # nothing of the run reached main
        assert self.opts == list(querylog.MR_OPTIONS)
        assert w.show(GAPS, branch) != w.show(GAPS) and self.spool1  # the gap entry waits on the branch; rows stay
        rc, said = self.again
        assert rc == 0 and says(said, "finding(s) wait on a querylog/ branch and are left alone"), said
        st = self.st
        assert self.refs2 == self.refs1 and len(self.refs1) == 2  # main and the one branch, no second branch
        assert len(st["runs"]) == 1 and st[GAPS] == []  # the run file reached main; the gap entry is held
        (g,) = [r for r in st["findings"].values() if r["kind"] == "gap"]
        assert (g["state"], g["stage"]) == ("open", "candidate-gap")
        assert st["spool"] == [] and st["gate"] == [], st["gate"]


# ---------------------------------------------------------------- CI that is not red

class TestCiNotRed:
    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory, seed):
        w = cls.w = World(tmp_path_factory.mktemp("e2e-ci"), seed)
        cls.said = {}
        for name, status in (("win32", None), ("laps_length", "running"), (None, "manual"), ("do_port", "skipped")):
            if name:
                s = sid()
                w.lookup(name, s)
                w.end(s)
            w.ci = pipeline(status) if status else signed_out
            cls.said[status] = (w.distill(), w.main(), w.spool())
        cls.st = w.state()

    def test_unfinished_ci_holds_the_push_and_manual_or_skipped_do_not(self):
        (_, first, _) = self.said[None]
        (rc, said), main, spool = self.said["running"]
        assert rc == 0 and main == first and spool, said
        assert says(said, "is not finished (glab on gitlab.com: running); nothing pushed this run"), said
        for status in ("manual", "skipped"):
            (rc, said), main, spool = self.said[status]
            assert rc == 0 and main != first and spool == [] and says(said, "apply --push: pushed "), (status, said)
            assert not says(said, "is red") and not says(said, "not finished"), said
        st = self.st
        assert len(st["runs"]) == 3 and st["gate"] == [], st["gate"]
        assert all(c[:2] in (["glab", "auth"], ["glab", "api"]) for c in self.w.calls)


# ---------------------------------------------------------------- opt-in research

class TestResearch:
    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory, seed):
        tmp = Path(tmp_path_factory.mktemp("e2e-research"))
        w = cls.w = World(tmp, seed)
        n, _ = querylog.fact_lines((w.home / ARTICLE).read_text(encoding="utf-8"))[0]
        legacy = cand(text="Legacy Microsoft LAPS stays available for older operating systems.", quote=LEGACY_QUOTE,
                      conflicts_with=n)
        shutil.copy(PAGE, tmp / "page.html")
        w.replay = tmp / "research.json"
        w.replay.write_text(json.dumps({"replies": [reply(cand(), cand(text="Windows LAPS supports Windows Server 2012 "
                                                                        "R2 after a later update.", quote=BAD_QUOTE),
                                                          legacy)],
                                        "pages": {PAGE_URL: "page.html"}}), encoding="utf-8")
        cls.line = n
        cls.runs, cls.states, cls.commits = [], [], []
        for name, config in (("gap", {"mode": "auto", "research": True, "research_daily": 1}),
                             ("gap_gmsa", {"mode": "auto", "research": True, "research_daily": 1}),
                             ("gap_win32", {"mode": "auto"})):
            w.config(config)
            s = sid()
            w.lookup(name, s)
            w.end(s)
            before = w.main()
            cls.runs.append((w.distill(), querylog.read_json(w.q / querylog.RESEARCH_RUNS_NAME, {})))
            cls.states.append(w.state())
            cls.commits.append(w.commits(before))

    def gap_of(self, st, name):
        return next(r for r in st["findings"].values() if r["kind"] == "gap" and r["entry"] == question(
            st["entries"], name)["id"])

    def test_research_within_its_daily_cap(self):
        import kbid
        ((rc, said), counted), st = self.runs[0], self.states[0]
        assert rc == 0 and counted.get("runs") == 1, said
        sid_ = kbid.source_id(PAGE_URL, "S")
        assert bullets(st[ARTICLE]) == [f"- {cand()['text']} [DOC {sid_}]"], st[ARTICLE]
        assert [r.split(",")[0] for r in st[SOURCES]] == [sid_]
        (conflict,) = bullets(st[CONFLICTS])
        g = self.gap_of(st, "gap")
        assert g["id"] in conflict and f"(line {self.line} of the article)" in conflict and "not settled" in conflict
        assert (g["state"], g["stage"]) == ("applied", "claim")
        assert [p["to"] for p in g["promotions"]] == ["candidate-gap", "gap", "candidate-fact", "claim"]
        assert len(bullets(st[GAPS])) == 1 and "2012 R2 after a later update" not in self.w.show(ARTICLE)  # no quote
        assert [v for _, v in self.commits[0]] == ["querylog", "gap, querylog, research"], self.commits[0]
        assert st["gate"] == [], st["gate"]

    def test_research_over_its_cap(self):
        ((rc, said), counted), st, before = self.runs[1], self.states[1], self.states[0]
        assert rc == 0 and counted.get("runs") == 1, said  # no run started
        g = self.gap_of(st, "gap_gmsa")
        assert (g["state"], g["stage"]) == ("applied", "gap") and g["article"] == "public/windows/gmsa.md"
        gaps = bullets(st[GAPS])
        assert len(gaps) == 2 and gaps[1].endswith("(topic: windows/gmsa)"), gaps
        assert [v for _, v in self.commits[1]] == ["querylog", "gap, querylog"], self.commits[1]
        assert (st[ARTICLE], st[SOURCES], st[CONFLICTS]) == (before[ARTICLE], before[SOURCES], before[CONFLICTS])
        assert st["gate"] == [], st["gate"]

    def test_research_off(self):
        ((rc, said), counted), st, before = self.runs[2], self.states[2], self.states[1]
        assert rc == 0 and counted.get("runs") == 1, said
        g = self.gap_of(st, "gap_win32")
        assert (g["state"], g["stage"]) == ("applied", "gap")
        assert bullets(st[GAPS])[-1].endswith("(topic: intune/win32-apps)")
        assert (st[ARTICLE], st[SOURCES], st[CONFLICTS]) == (before[ARTICLE], before[SOURCES], before[CONFLICTS])
        assert self.gap_of(st, "gap_gmsa")["stage"] == "gap"  # left at gap: research is off
        assert st["spool"] == [] and st["gate"] == [], st["gate"]


# ---------------------------------------------------------------- modes, the DISABLED marker, a broken config

@pytest.mark.parametrize("mode", ["off", "local", "auto", "default", "disabled", "unreadable"])
def test_modes(tmp_path, seed, mode):
    import kb_hook
    w = World(tmp_path, seed)
    if mode in ("off", "local", "auto"):
        w.config({"mode": mode})
    elif mode == "disabled":
        w.config({"mode": "auto"})
        w.q.mkdir(parents=True)
        (w.q / querylog.DISABLED_NAME).write_text("push refused for want of rights\n", encoding="utf-8")
    elif mode == "unreadable":
        w.config("{not json")
    s = sid()
    answer = w.lookup("win32", s)
    assert json.loads(answer) == kb_hook.answer(c(LOOKUPS["win32"]["prompt"]))  # the kb: hook answers in every mode
    wrote = w.spool()
    w.end(s)
    rc, said = w.distill()
    st = w.state()
    assert rc == 0 and st["gate"] == [], (said, st["gate"])
    if mode in ("off", "disabled", "unreadable"):
        assert wrote == [] and said == ["distill: logging is off"] and w.local_runs() == []
        assert w.main() == w.base and not (w.q / querylog.WORKTREE_NAME).exists()
    elif mode == "local":
        assert wrote == [f"{s}.jsonl"] and says(said, "entries=1 dropped=0 waiting=0") and len(w.local_runs()) == 1
        assert w.spool() == [] and w.main() == w.base and not (w.q / querylog.WORKTREE_NAME).exists()
    else:
        assert says(said, "apply --push: pushed ") and len(st["runs"]) == 1 and st["spool"] == [], said


# ---------------------------------------------------------------- sessions open, ended and idle

class TestSessions:
    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory, seed):
        w = cls.w = World(tmp_path_factory.mktemp("e2e-sessions"), seed)
        cls.open_, cls.ended, cls.idle = sid(), sid(), sid()
        w.lookup("win32", cls.open_)
        w.lookup("laps_length", cls.ended)
        w.lookup("do_port", cls.idle)
        w.end(cls.ended)
        cls.markers = sorted(p.name for p in (w.q / "spool").glob("*.end"))
        old = datetime.datetime.now().timestamp() - querylog.SESSION_IDLE_CLOSED_S - 60
        os.utime(w.q / "spool" / f"{cls.idle}.jsonl", (old, old))
        cls.open_before = (w.q / "spool" / f"{cls.open_}.jsonl").read_bytes()
        cls.rc, cls.said = w.distill()
        cls.st = w.state()

    def test_an_open_session_waits_an_ended_and_an_idle_one_are_distilled(self):
        st, w = self.st, self.w
        assert self.markers == [f"{self.ended}.end"]
        assert self.rc == 0 and says(self.said, "entries=2 dropped=0 waiting=0"), self.said
        assert sorted(e["question"] for e in st["entries"]) == sorted(
            LOOKUPS[n]["asked"] for n in ("laps_length", "do_port"))
        assert st["spool"] == [f"{self.open_}.jsonl"]
        assert (w.q / "spool" / f"{self.open_}.jsonl").read_bytes() == self.open_before
        assert st["gate"] == [], st["gate"]


# ---------------------------------------------------------------- a refused push, then a delivered one

class TestPushFailure:
    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory, seed):
        w = cls.w = World(tmp_path_factory.mktemp("e2e-refused"), seed)
        hook = Path(w.remote.path) / "hooks" / "pre-receive"
        hook.write_text(REJECT_HOOK, encoding="utf-8", newline="\n")
        hook.chmod(0o755)
        s = sid()
        w.lookup("win32", s)
        w.end(s)
        cls.before = w.spool()
        cls.refused = w.distill()
        cls.main1, cls.spool1 = w.main(), w.spool()
        hook.unlink()
        cls.delivered = w.distill()
        cls.st = w.state()

    def test_a_failed_push_keeps_the_spool_and_a_successful_one_deletes_it_after(self):
        rc, said = self.refused
        assert rc == 1 and says(said, "kbgit.py sync exit 1: nothing pushed to main"), said
        assert self.main1 == self.w.base and self.spool1 == self.before and self.before, self.spool1
        assert not says(said, "deleted the spool rows")
        rc, said = self.delivered
        assert rc == 0 and said[0] == "distill: nothing to write (waiting=0)", said  # nothing distilled twice
        pushed = next(i for i, s in enumerate(said) if s.startswith("apply --push: pushed "))
        gone = next(i for i, s in enumerate(said) if s.startswith("apply --push: deleted the spool rows of 1 entries"))
        assert pushed < gone, said
        st = self.st
        assert len(st["runs"]) == 1 and st["spool"] == [] and st["gate"] == [], st["gate"]
