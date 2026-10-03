"""_tools/autopilot.py without a paid run: `runner start` against a fake claude that prints a recorded-shape stream
(with and without a compact_boundary) in a throwaway clone with a local origin, and `runner-status` over the commits
a run left in its worktree. The tests named autopilot_runner_* are the item's checks."""
import json, os, re, sys, time
from pathlib import Path

import pytest

import autopilot, bl_base
from conftest import Repo, git_env

SP = "SP-abcdefgh"
STORY, T1, T2, T3, OUTSIDE = "ST-aaaaaaaa", "TK-bbbbbbbb", "TK-cccccccc", "TK-dddddddd", "TK-zzzzzzzz"

FAKE = '''import json, os, sys, time
seen = {"argv": sys.argv[1:], "cwd": os.getcwd(), "headless": os.environ.get("KB_HEADLESS_RUNNER")}
open(os.environ["FAKE_SEEN"], "w", encoding="utf-8").write(json.dumps(seen))
out = sys.stdout.buffer
for ln in open(os.environ["FAKE_STREAM"], "rb").read().splitlines(keepends=True):
    out.write(ln)
    out.flush()
    if os.environ.get("FAKE_PAUSE"):
        time.sleep(float(os.environ.pop("FAKE_PAUSE")))
    if os.environ.get("FAKE_HANG_AFTER") and os.environ["FAKE_HANG_AFTER"].encode() in ln:
        if os.environ.get("FAKE_IGNORE_TERM"):
            import signal
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
        time.sleep(60)
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
'''


def ev(**kw):
    return json.dumps(kw, ensure_ascii=False) + "\n"


def result(text, **kw):
    return ev(type="result", subtype="success", is_error=False, result=text, session_id="s1", num_turns=7,
              total_cost_usd=0.42, **kw)


def stream(*, boundary=False, final="Landed two items.\nsprint-runner: landed-limit", tail=True):
    """A recorded-shape stream: init, an assistant turn with a tool call, its result, optionally a compact_boundary
    and the final result."""
    s = ev(type="system", subtype="init", session_id="s1", cwd="/w", tools=["Bash", "Agent"], model="m")
    s += ev(type="assistant", message={"role": "assistant", "content": [
        {"type": "text", "text": "Starting zażółć"}, {"type": "tool_use", "id": "t1", "name": "Bash",
                                                        "input": {"command": "python3 _tools/backlog.py horizon"}}]})
    s += ev(type="user", message={"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]})
    if boundary:
        s += ev(type="system", subtype="compact_boundary", session_id="s1",
                compact_metadata={"trigger": "auto", "pre_tokens": 168000})
    if tail:
        s += ev(type="assistant", message={"role": "assistant", "content": [{"type": "text", "text": "after"}]})
        s += result(final) if final is not None else ""
    return s


class World:
    """A clone with a local origin holding a sprint, a story and tasks, the fake claude and its environment."""

    def __init__(self, tmp_path, monkeypatch):
        self.tmp, self.mp = tmp_path, monkeypatch
        monkeypatch.setenv("KB_HOST_LOCK_DIR", str(tmp_path / "hostlocks"))  # the runners' records, one host per test
        env = git_env()
        self.origin = Repo(tmp_path / "origin.git", env)
        (tmp_path / "origin.git").mkdir()
        self.origin.git("init", "--bare", "-b", "main")
        self.root = Path(tmp_path / "clone")
        self.root.mkdir()
        self.repo = Repo(self.root, env)
        self.repo.git("init", "-b", "main")
        self.repo.git("remote", "add", "origin", str(tmp_path / "origin.git"))
        self.repo.write(".claude/settings.json", "{}\n")
        self.repo.write(".claude-plugin/plugin.json", '{"name": "main"}\n')
        self.repo.write(".claude-plugin/docs/.claude-plugin/plugin.json", '{"name": "docs"}\n')
        self.repo.write(".claude-plugin/not-a-plugin/readme.txt", "x\n")
        self.item(SP, kind="sprint", status="active")
        self.item(STORY, kind="story", status="todo", sprint=SP)
        for t in (T1, T2, T3):
            self.item(t, kind="task", status="doing", parent=STORY)
        self.item(OUTSIDE, kind="task", status="doing", parent="ST-yyyyyyyy")
        self.commit("seed")
        self.repo.git("push", "origin", "main")
        self.fake = tmp_path / "fake_claude.py"
        self.fake.write_text(FAKE, encoding="utf-8", newline="\n")
        for k, v in git_env().items():
            monkeypatch.setenv(k, v)
        monkeypatch.setenv("FAKE_SEEN", str(tmp_path / "seen.json"))
        monkeypatch.setenv("FAKE_STREAM", str(tmp_path / "stream.jsonl"))
        for k in ("FAKE_HANG_AFTER", "FAKE_IGNORE_TERM", "FAKE_EXIT", "FAKE_PAUSE"):
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setattr(autopilot, "CLAUDE", [sys.executable, str(self.fake)])

    def item(self, iid, **kw):
        self.repo.write(f"kb/_self/backlog/{iid}.json", json.dumps({"id": iid, "title": "t " + iid, **kw}, indent=2) + "\n")

    def commit(self, msg):
        self.repo.git("add", "-A")
        self.repo.git("commit", "-q", "--allow-empty", "-m", msg)

    def stream(self, text, **env):
        (self.tmp / "stream.jsonl").write_bytes(text.encode("utf-8"))
        for k, v in env.items():
            self.mp.setenv("FAKE_" + k.upper(), str(v))

    def start(self, landed=None):
        return autopilot.runner_start(SP, landed, self.root)

    def status(self):
        return json.loads((autopilot.cache_dir(self.root, SP) / "status.json").read_text(encoding="utf-8"))

    def seen(self):
        return json.loads((self.tmp / "seen.json").read_text(encoding="utf-8"))

    def wt(self):
        return autopilot.worktree_path(self.root, SP)

    def streams(self):
        return sorted(autopilot.cache_dir(self.root, SP).glob("*.jsonl"))

    def origin_main(self):
        return self.repo.rev("origin/main")


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


# ---------------------------------------------------------------- the command the runner starts

@pytest.mark.parametrize("landed", [None, 1, 3, 12])
def test_autopilot_runner_start_passes_settings_and_plugins_explicitly_and_no_permission_flag(world, landed):
    world.stream(stream())
    assert world.start(landed) == 0
    seen, wt = world.seen(), world.wt()
    argv = seen["argv"]
    want = f"/kb-sprint run {SP} --headless" + (f" --landed {landed}" if landed else "")
    assert argv[0] == "-p" and argv[1] == want == autopilot.PROMPT.format(
        sprint=SP, landed=autopilot.LANDED_FLAG.format(k=landed) if landed else "")
    assert argv[argv.index("--output-format") + 1] == "stream-json" and "--verbose" in argv
    assert argv[argv.index("--settings") + 1] == str(wt / ".claude" / "settings.json")
    plugins = [argv[i + 1] for i, a in enumerate(argv) if a == "--plugin-dir"]
    assert plugins == [str(wt), str(wt / ".claude-plugin" / "docs")]  # the project, then each plugin under .claude-plugin
    assert not permission_flags(argv)
    assert Path(seen["cwd"]).resolve() == wt.resolve()
    assert seen["headless"] == "1"  # the run's publish --hook pushes nothing


def runner_denies(argv):
    """The deny rules the run's --disallowedTools carries (the arguments after it up to the next flag)."""
    if "--disallowedTools" not in argv:
        return []
    rest = argv[argv.index("--disallowedTools") + 1:]
    return [a for a in rest[:next((i for i, a in enumerate(rest) if a.startswith("--")), len(rest))]]


def test_autopilot_runner_denies_the_run_an_answer_recorded_as_the_operators(world):
    """The second layer: the text rule for the common order; the guard is the tool's own (test_backlog_headless_operator.py)."""
    world.stream(stream())
    world.start()
    denies = runner_denies(world.seen()["argv"])
    for shell in ("Bash", "PowerShell"):
        for by in ("--by operator", "--by=operator"):
            assert f"{shell}(python3 _tools/backlog.py answer * {by}*)" in denies
    # the project's settings, which the operator-present manager session reads, deny it nowhere
    settings = json.loads((Path(__file__).resolve().parent.parent / ".claude" / "settings.json").read_text("utf-8"))
    assert not [r for r in settings["permissions"].get("deny", []) if "--by" in r]


def test_autopilot_runner_denies_a_planted_run_without_them_fails_the_check(world, monkeypatch):
    world.stream(stream())
    monkeypatch.setattr(autopilot, "RUNNER_DENY", ())
    world.start()
    assert not runner_denies(world.seen()["argv"])  # what the test above refuses


def test_autopilot_runner_publish_hook_does_nothing_in_a_headless_run(monkeypatch, capsys):
    import kbpublic
    monkeypatch.setattr(kbpublic, "publish_remote", lambda cwd: "public")
    called = []
    monkeypatch.setattr(kbpublic, "cmd_publish", lambda a, cwd: called.append(cwd))
    a = type("A", (), {"remote": None})()
    monkeypatch.setenv(kbpublic.HEADLESS_ENV, "1")
    assert kbpublic.cmd_publish_hook(a, ".") == 0 and called == []
    monkeypatch.delenv(kbpublic.HEADLESS_ENV)
    assert kbpublic.cmd_publish_hook(a, ".") == 0 and called == ["."]  # the planted contrast: an interactive session


def permission_flags(argv):
    return [a for a in argv if "permission" in a or "dangerously" in a]


def test_autopilot_runner_start_a_planted_permission_flag_fails_the_check(world, monkeypatch):
    world.stream(stream())
    real = autopilot.claude_argv
    monkeypatch.setattr(autopilot, "claude_argv", lambda *a, **k: real(*a, **k) + ["--permission-mode", "bypassPermissions"])
    world.start()
    assert permission_flags(world.seen()["argv"])  # what the test above refuses


def test_autopilot_runner_plugin_dirs_are_the_manifests_only(tmp_path):
    (tmp_path / ".claude-plugin" / "a" / ".claude-plugin").mkdir(parents=True)
    (tmp_path / ".claude-plugin" / "a" / ".claude-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".claude-plugin" / "b").mkdir()
    assert autopilot.plugin_dirs(tmp_path) == [str(tmp_path / ".claude-plugin" / "a")]  # no manifest at the top: not a plugin
    (tmp_path / ".claude-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
    assert autopilot.plugin_dirs(tmp_path) == [str(tmp_path), str(tmp_path / ".claude-plugin" / "a")]


# ---------------------------------------------------------------- the stream and the exit cause

@pytest.mark.parametrize("cause", ["landed-limit", "sprint-done", "blocked"])
def test_autopilot_runner_keeps_the_stream_and_records_the_cause_of_the_final_result(world, cause):
    text = stream(final=f"Done for now.\nsprint-runner: {cause}")
    world.stream(text)
    assert world.start() == 0
    kept = world.streams()
    assert len(kept) == 1 and re.fullmatch(r"\d{8}T\d{6}Z\.jsonl", kept[0].name)
    assert kept[0].read_bytes() == text.encode("utf-8")  # every line, byte for byte
    st = world.status()
    assert st["cause"] == cause and st["exit_code"] == 0 and st["stream"] == kept[0].name
    assert st["start_ref"] == world.origin_main() and st["sprint"] == SP and st["landed_limit"] is None


def test_autopilot_runner_stream_lines_are_written_as_they_arrive(world, tmp_path):
    """The first line is in the file while the child still runs (it pauses after it), not when it exits."""
    world.stream(stream(), pause=1.5)
    times = []

    class Keep:
        def write(self, line):
            times.append(time.monotonic())

        def flush(self):
            pass

    with open(tmp_path / "err", "w", encoding="utf-8") as err:
        autopilot.supervise(autopilot.CLAUDE, tmp_path, Keep(), err)
    assert len(times) == 5 and times[1] - times[0] >= 1.0 and times[-1] - times[1] < 1.0


@pytest.mark.parametrize("hang_after, ignore_term", [("compact_boundary", False),
                                                       pytest.param("compact_boundary", True, marks=pytest.mark.skipif(
                                                           os.name != "posix", reason="a child ignoring SIGTERM is POSIX"))])
def test_autopilot_runner_ends_the_child_at_the_first_compact_boundary(world, hang_after, ignore_term):
    text = stream(boundary=True)
    world.stream(text, hang_after=hang_after, **({"ignore_term": 1} if ignore_term else {}))
    world.mp.setattr(autopilot, "GRACE_S", 0.5)
    t = time.monotonic()
    code = world.start(landed=5)
    assert time.monotonic() - t < 30  # the child sleeps 60 s after the boundary: it was ended, not awaited
    kept = world.streams()[0].read_text(encoding="utf-8")
    assert '"compact_boundary"' in kept and "after" not in kept and '"type": "result"' not in kept
    st = world.status()
    assert code == 0 and st["cause"] == "compaction" and st["landed_limit"] == 5 and st["exit_code"] != 0


def test_autopilot_runner_a_boundary_named_in_text_does_not_end_the_run(world):
    s = ev(type="system", subtype="init", session_id="s1")
    s += ev(type="assistant", message={"content": [{"type": "text", "text": '{"type": "system", "subtype": "compact_boundary"}'}]})
    s += ev(type="system", subtype="status", status="compacting")  # a system event that is no boundary
    s += "not json at all, with compact_boundary in it\n"
    s += result("fine\nsprint-runner: sprint-done")
    world.stream(s)
    assert world.start() == 0
    assert world.status()["cause"] == "sprint-done" and world.streams()[0].read_bytes() == s.encode("utf-8")


def test_autopilot_runner_the_first_boundary_wins_over_a_result_before_it(world):
    s = stream() + ev(type="system", subtype="compact_boundary", session_id="s1")
    world.stream(s)
    world.start()
    assert world.status()["cause"] == "compaction"


@pytest.mark.parametrize("text, exit_code, why", [
    (stream(final="all fine"), 0, "names no cause"),  # a result with no sprint-runner line
    (stream(final="sprint-runner: sprint-done", ), 3, "sprint-done"),  # a non-zero exit is an error whatever it says
    (stream(final=None), 0, "no result event"),
    (stream(final="sprint-runner: made-up"), 0, "names no cause"),
    (stream(final="note: sprint-runner: sprint-done and more"), 0, "names no cause"),  # the marker is a whole line
])
def test_autopilot_runner_an_error_when_the_result_and_exit_code_name_no_cause(world, text, exit_code, why):
    world.stream(text, exit=exit_code)
    assert world.start() == 1
    st = world.status()
    assert st["cause"] == "error" and st["exit_code"] == exit_code
    if exit_code == 0:
        assert why in st["detail"]


def test_autopilot_runner_an_error_result_is_an_error_with_its_text(world):
    world.stream(stream(tail=False) + ev(type="result", subtype="error_max_turns", is_error=True, result="Max turns reached\nsprint-runner: sprint-done"),
                 exit=1)
    assert world.start() == 1
    assert world.status()["cause"] == "error" and "Max turns" in world.status()["detail"]


def test_autopilot_runner_a_claude_that_cannot_start_is_an_error_with_a_status(world, monkeypatch):
    monkeypatch.setattr(autopilot, "CLAUDE", [str(world.tmp / "no-such-claude")])
    assert world.start() == 1
    st = world.status()
    assert st["cause"] == "error" and "cannot start" in st["detail"] and st["ended"]


def test_autopilot_runner_status_is_running_until_the_child_ends(world, monkeypatch):
    seen = {}

    def peek(argv, cwd, keep, stderr):
        seen.update(world.status())
        return {"compaction": False, "result": None, "exit_code": 0}

    monkeypatch.setattr(autopilot, "supervise", peek)
    world.start()
    assert seen["cause"] == "running" and seen["start_ref"] == world.origin_main() and seen["ended"] is None


def test_autopilot_runner_two_runs_in_one_second_keep_two_streams(world, monkeypatch):
    monkeypatch.setattr(autopilot, "now", lambda: __import__("datetime").datetime(2026, 10, 2, 8, 30, 15,
                                                                                  tzinfo=__import__("datetime").timezone.utc))
    world.stream(stream())
    world.start()
    world.start()
    assert [p.name for p in world.streams()] == ["20261002T083015Z-2.jsonl", "20261002T083015Z.jsonl"]
    assert world.status()["stream"] == "20261002T083015Z-2.jsonl"


# ---------------------------------------------------------------- the worktree

def test_autopilot_runner_worktree_is_made_at_origin_main_and_fast_forwarded_when_clean(world):
    world.stream(stream())
    first = world.origin_main()
    world.start()
    wt = Repo(world.wt(), git_env())
    assert wt.rev("HEAD") == first and wt.git("branch", "--show-current").strip() == "orch/" + SP
    world.repo.write("kb/x.md", "x\n")
    world.commit("on main")
    world.repo.git("push", "origin", "main")
    second = world.repo.rev("HEAD")
    world.start()  # reused, fast-forwarded to the new origin/main
    assert wt.rev("HEAD") == second and world.status()["start_ref"] == second


def test_autopilot_runner_worktree_ahead_of_origin_main_is_kept(world):
    world.stream(stream())
    world.start()
    wt = Repo(world.wt(), git_env())
    wt.git("commit", "-q", "--allow-empty", "-m", "claim")
    ahead = wt.rev("HEAD")
    world.start()
    assert wt.rev("HEAD") == ahead and world.status()["start_ref"] == ahead


def test_autopilot_runner_dirty_worktree_is_refused_naming_its_files(world, capsys, monkeypatch):
    world.stream(stream())
    world.start()
    before = world.status()
    seen = world.tmp / "seen.json"
    seen.unlink()
    (world.wt() / "kb" / "_self" / "backlog" / f"{T1}.json").write_text("{}\n", encoding="utf-8")  # modified
    (world.wt() / "stray.txt").write_text("x\n", encoding="utf-8")  # untracked
    monkeypatch.setattr(autopilot, "ROOT", world.root)
    assert autopilot.main(["runner", "start", SP]) == 2
    err = capsys.readouterr().err
    assert f"{T1}.json" in err and "stray.txt" in err and "uncommitted" in err
    assert not seen.exists() and world.status() == before  # no claude run, no status written


def test_autopilot_runner_diverged_worktree_is_refused(world, capsys, monkeypatch):
    world.stream(stream())
    world.start()
    Repo(world.wt(), git_env()).git("commit", "-q", "--allow-empty", "-m", "local")
    world.repo.write("kb/y.md", "y\n")
    world.commit("remote")
    world.repo.git("push", "origin", "main")
    monkeypatch.setattr(autopilot, "ROOT", world.root)
    assert autopilot.main(["runner", "start", SP]) == 2
    assert "by hand" in capsys.readouterr().err


def test_autopilot_runner_without_the_settings_file_is_refused(world, capsys, monkeypatch):
    world.repo.git("rm", "-q", ".claude/settings.json")
    world.commit("no settings")
    world.repo.git("push", "origin", "main")
    monkeypatch.setattr(autopilot, "ROOT", world.root)
    assert autopilot.main(["runner", "start", SP]) == 2
    assert "settings.json" in capsys.readouterr().err


@pytest.mark.parametrize("args", [["SP-short"], ["../x"], ["TK-abcdefgh"], ["SP-ABCDEFGH"], [""], [SP, "--landed", "0"],
                                  [SP, "--landed", "x"]])
def test_autopilot_runner_a_bad_argument_is_a_usage_error(args):
    with pytest.raises(SystemExit) as e:
        autopilot.main(["runner", "start", *args])
    assert e.value.code == 2


# ---------------------------------------------------------------- runner-status

def assert_short(text):
    assert len(text) < autopilot.STATUS_MAX, f"{len(text)} characters"


def done(world, iid):
    wt = Repo(world.wt(), git_env())
    wt.git("commit", "-q", "--allow-empty", "-m", f'chore(backlog): done {iid} "t"\n\nKB-Work: {iid}')


def test_autopilot_runner_status_reports_landed_items_gates_bugs_and_the_cause(world, capsys, monkeypatch):
    world.stream(stream(final="x\nsprint-runner: landed-limit"))
    world.start(landed=2)
    wt = Repo(world.wt(), git_env())
    done(world, T1)
    done(world, T2)
    done(world, OUTSIDE)  # not an item of the sprint
    wt.git("commit", "-q", "--allow-empty", "-m", f"feat: work on {T3}\n\nKB-Work: {T3}")  # no done commit
    wt.write("kb/_self/backlog/" + T3 + ".json", json.dumps({"id": T3, "kind": "task", "title": "t", "status": "doing",
             "parent": STORY, "gates": [{"id": "name", "kind": "provisional", "question": "q", "answer": "recommend",
                                          "by": "agent"}, {"id": "ask", "kind": "blocking", "question": "q"}]}, indent=2) + "\n")
    wt.write("kb/_self/backlog/BG-eeeeeeee.json", json.dumps({"id": "BG-eeeeeeee", "kind": "bug", "title": "b",
                                                              "status": "todo"}) + "\n")
    wt.write("kb/_self/backlog/ST-ffffffff.json", json.dumps({"id": "ST-ffffffff", "kind": "story", "title": "s"}) + "\n")
    wt.git("add", "-A")
    wt.git("commit", "-q", "-m", "gates and a bug")
    monkeypatch.setattr(autopilot, "ROOT", world.root)
    assert autopilot.main(["runner-status", SP]) == 0
    out = capsys.readouterr().out
    assert_short(out)
    assert f"{SP} exit cause landed-limit" in out
    assert f"landed 2: {T1}, {T2}" in out and OUTSIDE not in out and T3 not in out.split("gates")[0]
    assert f"gates 2: {T3}/name=recommend, {T3}/ask=open" in out
    assert "bugs 1: BG-eeeeeeee" in out and "ST-ffffffff" not in out
    assert world.status()["start_ref"][:10] in out


def test_autopilot_runner_status_without_a_run_exits_1(world, capsys, monkeypatch):
    monkeypatch.setattr(autopilot, "ROOT", world.root)
    assert autopilot.main(["runner-status", SP]) == 1
    assert "no run recorded" in capsys.readouterr().out


def test_autopilot_runner_status_of_a_run_in_progress_says_running(world, monkeypatch):
    monkeypatch.setattr(autopilot, "supervise", lambda *a: {"compaction": False, "result": None, "exit_code": 0})
    world.start()
    st = world.status()
    st.update(cause="running", ended=None)
    (autopilot.cache_dir(world.root, SP) / "status.json").write_text(json.dumps(st), encoding="utf-8")
    assert "exit cause running" in autopilot.status_text(SP, world.root)


@pytest.mark.parametrize("n", [0, 1, 7, 18, 19, 60, 140])
def test_autopilot_runner_status_stays_under_the_limit_whatever_the_run_did(world, n):
    """n landed items, n open gates and n bugs, with a long detail: the report is cut by section, never past the cap."""
    world.stream(stream(final="x" * 400), exit=1)
    world.start()
    wt = Repo(world.wt(), git_env())
    ids = [f"TK-{chr(97 + i // 26 % 26)}{chr(97 + i % 26)}{'q' * 6}" for i in range(n)]
    for iid in ids:
        wt.write(f"kb/_self/backlog/{iid}.json", json.dumps({"id": iid, "kind": "task", "title": "t", "status": "doing",
                 "parent": STORY, "gates": [{"id": "g", "kind": "blocking", "question": "q"}]}) + "\n")
    for i in range(n):
        wt.write(f"kb/_self/backlog/BG-{chr(97 + i // 26 % 26)}{chr(97 + i % 26)}{'w' * 6}.json",
                 json.dumps({"id": f"BG-{chr(97 + i // 26 % 26)}{chr(97 + i % 26)}{'w' * 6}", "kind": "bug", "title": "b"}) + "\n")
    wt.git("add", "-A")
    wt.git("commit", "-q", "--allow-empty", "-m", "items")
    for iid in ids:
        done(world, iid)
    text = autopilot.status_text(SP, world.root)
    assert_short(text)
    assert f"landed {n}" in text and f"gates {n}" in text and f"bugs {n}" in text
    assert text.splitlines()[0].startswith(f"{SP} exit cause error")  # the 400-character error text is cut


@pytest.mark.parametrize("n", range(0, 70))
@pytest.mark.parametrize("width", [4, 11, 23])
def test_autopilot_runner_fit_never_passes_its_budget_and_counts_every_item(n, width):
    items = [("x" * width + str(i))[:width + 1] for i in range(n)]
    for budget in (60, 160, 240):
        line = autopilot.fit("things", items, budget)
        assert line.startswith(f"things {n}") and (len(line) <= budget or n == 0 or len(line) <= len(f"things {n}: +{n} more"))
        shown = line.split(": ", 1)[1] if ": " in line else ""
        assert len(set(re.findall(r"x+\d+", shown))) <= n


def test_autopilot_runner_status_that_prints_the_raw_stream_fails_the_length_test(world):
    world.stream(stream(final="y" * 3000))
    world.start()
    raw = world.streams()[0].read_text(encoding="utf-8")

    def planted(sprint, root):  # a runner-status that dumps the stream instead of reporting it
        return raw

    assert_short(autopilot.status_text(SP, world.root))
    with pytest.raises(AssertionError):
        assert_short(planted(SP, world.root))
    assert len(raw) > autopilot.STATUS_MAX


def test_autopilot_runner_status_reads_its_run_from_the_status_file_not_the_stream(world, monkeypatch):
    world.stream(stream(final="x\nsprint-runner: blocked"))
    world.start()
    world.streams()[0].write_text("", encoding="utf-8")  # the stream is gone: the report still has its cause
    assert "exit cause blocked" in autopilot.status_text(SP, world.root)
    monkeypatch.setattr(bl_base, "git", lambda *a, **k: (_ for _ in ()).throw(bl_base.Refused("boom")))
    assert "git: boom" in autopilot.status_text(SP, world.root)  # an unreadable repository degrades, never raises


# ---------------------------------------------------------------- the skill's headless path

SKILL = Path(__file__).resolve().parent.parent / ".claude" / "skills" / "kb-sprint" / "SKILL.md"
NEVER_ASK = re.compile(r"never call AskUserQuestion", re.I)


def skill_sections(text):
    """(level, heading, body) per Markdown heading, outside code fences."""
    out, fence = [], False
    for line in text.splitlines():
        if line.startswith("```"):
            fence = not fence
        m = None if fence else re.match(r"^(#+) (.*)$", line)
        if m:
            out.append([len(m.group(1)), m.group(2), []])
        elif out:
            out[-1][2].append(line)
    return [(lv, h, "\n".join(b)) for lv, h, b in out]


def headless_problems(skill_text, prompt):
    """What is wrong with the skill's headless path against the prompt the runner sends: the prompt's subcommand and
    its flag must name a section the skill holds (the flag's section under the subcommand's), and that section may
    name AskUserQuestion only to forbid it."""
    words = prompt.split()
    sub = words[1:2] and words[1]
    flags = [w for w in words if w.startswith("--")]
    if prompt.split()[0] != "/kb-sprint" or not sub or not flags:
        return [f"the prompt {prompt!r} is not '/kb-sprint SUB --FLAG ...'"]
    sections, found = skill_sections(skill_text), None
    for i, (lv, heading, _) in enumerate(sections):
        if lv == 2 and heading.split()[0] == sub:
            for lv2, h2, body in sections[i + 1:]:
                if lv2 <= 2:
                    break
                if flags[0] in h2:
                    found = (h2, body)
    if not found:
        return [f"no section under '## {sub}' names {flags[0]}"]
    heading, body = found
    problems = [f"the section {heading!r} does not name {need!r}" for need in (
        "--landed", "gate add", "--provisional", "horizon", "next", *(autopilot.CAUSE_MARKER.format(cause=c)
                                                                      for c in autopilot.CAUSES_FROM_RESULT))
        if need not in body]
    if "AskUserQuestion" in NEVER_ASK.sub("", body):
        problems.append(f"the section {heading!r} names an AskUserQuestion call")
    return problems


def test_autopilot_runner_skill_headless(world):
    world.stream(stream())
    assert world.start(5) == 0
    prompt = world.seen()["argv"][1]  # what runner start sent
    assert "--headless" in prompt and "--landed 5" in prompt
    text = SKILL.read_text(encoding="utf-8")
    assert headless_problems(text, prompt) == []
    for sprint, landed in ((SP, ""), (SP, autopilot.LANDED_FLAG.format(k=1)), ("SP-zzzzzzzz", autopilot.LANDED_FLAG.format(k=40))):
        assert headless_problems(text, autopilot.PROMPT.format(sprint=sprint, landed=landed)) == []


@pytest.mark.parametrize("how", ["no section", "ask", "ask elsewhere in the section", "renamed flag", "no cause"])
def test_autopilot_runner_skill_headless_a_planted_failure_fails_the_check(how):
    prompt = autopilot.PROMPT.format(sprint=SP, landed=autopilot.LANDED_FLAG.format(k=2))
    text = SKILL.read_text(encoding="utf-8")
    assert headless_problems(text, prompt) == []
    if how == "no section":
        planted = text.replace("### Headless (--headless)", "### Unattended")
    elif how == "ask":
        planted = text.replace("Never call AskUserQuestion", "Call AskUserQuestion")
    elif how == "ask elsewhere in the section":
        planted = text.replace("## review SP\n", "Use AskUserQuestion to confirm a gate.\n\n## review SP\n", 1)
    elif how == "renamed flag":
        planted = text.replace("### Headless (--headless)", "### Headless (--unattended)")
    else:
        planted = text.replace("sprint-runner: blocked", "sprint-runner: stuck")
    assert planted != text
    assert headless_problems(planted, prompt)


# ---------------------------------------------------------------- status: the manager's state in one capped command

def plant(root, iid, **kw):
    d = Path(root) / "kb" / "_self" / "backlog"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{iid}.json").write_text(json.dumps({"id": iid, "title": "t " + iid, **kw}), encoding="utf-8")


def sealed(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(tmp_path / "hostlocks"))
    (tmp_path / "hostlocks").mkdir()
    return tmp_path / "clone"


def run_status(root, hook=False):
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = autopilot.status(hook, root)
    return code, buf.getvalue()


def test_autopilot_status_prints_runner_sprint_gate_decision_and_tick(tmp_path, monkeypatch):
    root = sealed(tmp_path, monkeypatch)
    plant(root, SP, kind="sprint", status="active")
    plant(root, STORY, kind="story", status="todo", sprint=SP)
    plant(root, T1, kind="task", status="done", parent=STORY)
    plant(root, T2, kind="task", status="todo", parent=STORY)
    plant(root, T3, kind="task", status="todo", parent=STORY,
          gates=[{"id": "g1", "kind": "blocking", "question": "q", "options": ["a", "b"]}])
    (root / "kb" / "_self").mkdir(parents=True, exist_ok=True)
    (root / "kb" / "_self" / "_decisions.csv").write_text(
        "id,text,by,status\nD-aaaaaaaa,x,autopilot,active\nD-bbbbbbbb,y,operator,active\nD-cccccccc,z,autopilot,superseded\n",
        encoding="utf-8")
    bl_base.runner_record_path(os.getpid()).write_text(
        json.dumps({"pid": os.getpid(), "sprint": SP, "clone": str(root), "started": "2026-01-01T00:00:00Z"}), encoding="utf-8")
    plant(root, "SP-zzzzzzzz", kind="sprint", status="done")  # status lists only a sprint that still has its item file
    ended = autopilot.cache_dir(root, "SP-zzzzzzzz")
    ended.mkdir(parents=True)
    (ended / "status.json").write_text(json.dumps({"cause": "blocked"}), encoding="utf-8")
    state = root / "_cache" / "autopilot" / "state.json"
    state.write_text(json.dumps({"tick": 7, "actions": ["answered gate", {"action": "started sprint"}]}), encoding="utf-8")
    code, out = run_status(root)
    assert code == 0
    assert f"runners 2: {SP} pid {os.getpid()} alive" in out and "SP-zzzzzzzz ended blocked" in out
    assert f"sprints 1: {SP} 1/4 done" in out and "next TK-" in out
    assert f"gates 1: {T3}/g1" in out
    assert "unratified 1: D-aaaaaaaa" in out
    assert "tick 7 actions 2: answered gate, started sprint" in out


def test_autopilot_status_ticks_file_is_read_when_state_is_missing(tmp_path, monkeypatch):
    root = sealed(tmp_path, monkeypatch)
    d = root / "_cache" / "autopilot"
    d.mkdir(parents=True)
    (d / "ticks.jsonl").write_text('{"tick": 1, "actions": ["old"]}\n{"tick": 2, "actions": ["new"]}\nnot json\n', encoding="utf-8")
    assert "tick 2 actions 1: new" in run_status(root)[1]


def test_autopilot_status_caps_a_long_list(tmp_path, monkeypatch):
    root = sealed(tmp_path, monkeypatch)
    for n in range(40):
        plant(root, f"TK-{n:08d}", kind="task", status="todo",
              gates=[{"id": "g", "kind": "blocking", "question": "q", "options": ["a", "b"]}])
    d = root / "_cache" / "autopilot"
    d.mkdir(parents=True)
    (d / "state.json").write_text(json.dumps({"tick": 1, "actions": [f"act{n}" for n in range(30)]}), encoding="utf-8")
    out = run_status(root)[1]
    assert "gates 40: TK-00000000/g, TK-00000001/g, TK-00000002/g +37 more" in out
    assert "actions 30: act0, act1, act2 +27 more" in out
    assert "act3" not in out and "TK-00000003" not in out
    hook = run_status(root, hook=True)[1]
    assert "TK-00000002" not in hook and "+38 more" in hook


def test_autopilot_status_hook_is_under_1000_characters_and_exits_0_with_no_state(tmp_path, monkeypatch):
    root = sealed(tmp_path, monkeypatch)
    code, out = run_status(root, hook=True)
    assert code == 0 and 0 < len(out) < autopilot.HOOK_MAX
    monkeypatch.setattr(autopilot, "ROOT", root / "missing")
    assert autopilot.main(["status", "--hook"]) == 0
    assert not (root / "_cache").exists() and not (root / "missing").exists()


def test_autopilot_status_hook_truncates_with_dots_and_never_fails(tmp_path, monkeypatch):
    root = sealed(tmp_path, monkeypatch)
    d = root / "_cache" / "autopilot"
    d.mkdir(parents=True)
    (d / "state.json").write_text(json.dumps({"tick": 1, "actions": ["x" * 500, "y" * 500, "z"]}), encoding="utf-8")
    monkeypatch.setattr(autopilot, "one_line", lambda t, n=0: str(t))
    code, out = run_status(root, hook=True)
    assert code == 0 and len(out.rstrip("\n")) < autopilot.HOOK_MAX and out.rstrip("\n").endswith("...")
    monkeypatch.setattr(autopilot, "status_report", lambda *a: 1 / 0)
    assert run_status(root, hook=True) == (0, "autopilot status unavailable\n")


@pytest.mark.parametrize("body", ["{not json", "[1, 2]", '{"tick": 3, "actions": 5}', '{"actions": [null, 4, {"x": 1}]}'])
def test_autopilot_status_a_corrupt_state_file_is_not_an_error(tmp_path, monkeypatch, body):
    root = sealed(tmp_path, monkeypatch)
    d = root / "_cache" / "autopilot"
    d.mkdir(parents=True)
    (d / "state.json").write_text(body, encoding="utf-8")
    code, out = run_status(root)
    assert code == 0 and "unavailable" not in out


# ---------------------------------------------------------------- the compaction hooks

def plant_main_lock(lock_dir, pid, clone, step="kbgit.py sync --push"):
    lock_dir.mkdir(parents=True, exist_ok=True)
    (lock_dir / "kb-main.lock").write_text(f"pid={pid}\nclone={clone}\nstarted=2026-10-02T12:00:00Z\nstep={step}\n",
                                           encoding="utf-8")


def gone_pid():
    """The pid of a process that has ended."""
    import subprocess
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


@pytest.fixture
def hook_env(tmp_path, monkeypatch):
    locks, clone = tmp_path / "hostlocks", tmp_path / "clone"
    clone.mkdir()
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(locks))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(clone))
    return locks, clone


def run_precompact(capsys, payload='{"trigger": "auto"}'):
    import io
    code = autopilot.precompact(stdin=io.StringIO(payload))
    return code, capsys.readouterr().err


def test_autopilot_status_precompact_blocks_while_this_clones_land_or_sync_holds_the_main_lock(hook_env, capsys):
    locks, clone = hook_env
    plant_main_lock(locks, os.getpid(), clone, "backlog.py land: fetch and rebase")
    code, err = run_precompact(capsys)
    assert code == 2
    assert "backlog.py land: fetch and rebase" in err and str(os.getpid()) in err and "(auto)" in err


@pytest.mark.parametrize("plant", ["none", "gone", "other clone", "torn"])
def test_autopilot_status_precompact_lets_compaction_run_without_a_live_holder_of_this_clone(hook_env, capsys,
                                                                                            tmp_path, plant):
    locks, clone = hook_env
    if plant == "gone":
        plant_main_lock(locks, gone_pid(), clone)
    elif plant == "other clone":
        (tmp_path / "other").mkdir()
        plant_main_lock(locks, os.getpid(), tmp_path / "other")
    elif plant == "torn":
        locks.mkdir()
        (locks / "kb-main.lock").write_text("pid=", encoding="utf-8")
    assert run_precompact(capsys) == (0, "")


@pytest.mark.parametrize("payload", ["", "not json", "[1]"])
def test_autopilot_status_precompact_reads_any_stdin_and_still_judges_the_lock(hook_env, capsys, payload):
    locks, clone = hook_env
    assert run_precompact(capsys, payload)[0] == 0
    plant_main_lock(locks, os.getpid(), clone)
    assert run_precompact(capsys, payload)[0] == 2


def test_autopilot_status_precompact_an_error_never_blocks(hook_env, capsys, monkeypatch):
    locks, clone = hook_env
    plant_main_lock(locks, os.getpid(), clone)
    monkeypatch.setattr(autopilot, "main_lock_holder", lambda clone: 1 / 0)
    assert run_precompact(capsys) == (0, "")


SETTINGS = Path(__file__).resolve().parent.parent / ".claude" / "settings.json"
STATUS_HOOK = "_tools/autopilot.py status --hook"
PRECOMPACT_HOOK = "_tools/autopilot.py precompact"


def compaction_hook_problems(settings):
    """What the compaction hooks lack: status --hook on SessionStart under a matcher holding `compact`, precompact on
    PreCompact for every trigger (no matcher), each with a timeout."""
    hooks = settings.get("hooks", {})
    out = []
    starts = [h for g in hooks.get("SessionStart", []) if "compact" in (g.get("matcher") or "").split("|")
              for h in g.get("hooks", []) if STATUS_HOOK in h.get("command", "")]
    if not starts:
        out.append("no SessionStart compact hook runs status --hook")
    pre = [(g, h) for g in hooks.get("PreCompact", []) for h in g.get("hooks", [])
           if PRECOMPACT_HOOK in h.get("command", "")]
    if not pre:
        out.append("no PreCompact hook runs precompact")
    elif any(g.get("matcher") not in (None, "", "*") for g, _ in pre):
        out.append("the PreCompact hook is limited to one trigger")
    if any(not h.get("timeout") for h in starts + [h for _, h in pre]):
        out.append("a compaction hook has no timeout")
    return out


def test_autopilot_status_compaction_hooks_are_in_settings():
    assert compaction_hook_problems(json.loads(SETTINGS.read_text(encoding="utf-8"))) == []


@pytest.mark.parametrize("plant, want", [
    (lambda s: s["hooks"].pop("PreCompact"), "no PreCompact hook runs precompact"),
    (lambda s: s["hooks"]["PreCompact"][0].update(matcher="manual"), "the PreCompact hook is limited to one trigger"),
    (lambda s: [g.update(matcher="startup") for g in s["hooks"]["SessionStart"] if g.get("matcher") == "compact"],
     "no SessionStart compact hook runs status --hook"),
    (lambda s: s["hooks"]["PreCompact"][0]["hooks"][0].pop("timeout"), "a compaction hook has no timeout"),
])
def test_autopilot_status_compaction_hooks_a_planted_change_fails(plant, want):
    s = json.loads(SETTINGS.read_text(encoding="utf-8"))
    plant(s)
    assert want in compaction_hook_problems(s)
