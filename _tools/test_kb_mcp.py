"""The `kb` MCP server and the Claude Code plugin that ships it (`python3 _tools/tests.py -k mcp`).

TestKbServer    _tools/kb_mcp.py as a subprocess over stdio: the legacy handshake (initialize, then
                notifications/initialized), tools/list (every description marked as documentation facts, only kb_pack
                always loaded, response_format on the list tools), kb_search (hits with path:line and source urls;
                the not-found note), kb_show, kb_source, kb_status, the 2026-07-28 server/discover and its version
                check, resultType on every result, JSON-RPC errors (parse error, unknown method or tool), stdout
                carrying only JSON-RPC, exit on EOF; kb_pack (coverage verdict, fact lines, url footer; a batch of
                questions with a verdict each and one footer), kb_audit, kb_facts (concise at least 30% smaller than
                detailed), kb_source with cited, kb_topics_for.
TestPluginManifest  .claude-plugin/marketplace.json and the two plugins: it-ops-kb (from the root: the kb server, the
                read-only kb-lookup, kb-review-workspace and kb-gap skills, the kb-lookup and kb-reviewer agents listed by path
                so the kb's agents/ articles never load, the kb: hook) and it-ops-kb-docs (the three documentation
                servers and a PreToolUse hook blocking submit_feedback: one command, run in each of sh, bash, dash,
                pwsh and Windows PowerShell present (not WSL's bash launcher), exits 2 with its reason on stderr;
                planted: the old `>&2` command, a parser error in PowerShell); no root .mcp.json (it would load into
                it-ops-kb); no pinned version (users track commits); rag.py named only as the clone form; the GitLab
                SSH remote. With the `claude` CLI installed, `claude plugin validate` passes for both. The clone-only
                kb-worker agent (test_kb_worker_agent*): the sonnet alias, effort high, not in plugin.json, and it runs
                `kbgit.py fix --check` and, for a change to any Python file ruff covers (_tools/, .claude/**/*.py), the ruff and
                tools_map tests before a commit (test_kb_worker_rule_4_worker_ruff_for_any_python). Its
                dispatch (test_kb_worker_dispatch*): /kb-sprint run starts tasks and subtasks on it with no model
                override, S1 and S2 bugs and breakdowns on the session model; the review, /kb-census and the
                runbook agree. Its fallback (test_kb_worker_fallback*): when the Agent tool does not list kb-worker,
                the skill and the runbook start the task on general-purpose with model sonnet, pointed at its file.
                Its load (test_kb_worker_load*): a worker runs its item's checks and the fast tests, never
                stress_test.py or a second full run; the orchestrator runs stress_test.py once per landing that
                changed _tools/; each brief names the in-flight sibling items and the files they change.
test_worker_provisional_gate*  kb-worker records a choice its item's goal leaves open as a provisional gate (gate add
                --kind provisional, answer --provisional) committed with the work, never report prose only; /kb-sprint
                run lands an item only after its gates are answered or provisional, read on its branch before
                `backlog.py land`, and its review confirms them; the runbook agrees. Planted: each rule taken out.
test_sprint_worker_starts_from_orchestrator_tip*  .claude/settings.json sets worktree.baseRef to "head", so an
                isolation worktree branches from the orchestrator's HEAD; /kb-sprint run commits and pushes the claims
                and dispatches only after that claim sync; kb-worker checks its base against origin/main and rebases
                only if behind, with no checkout by hand; the runbook agrees. Planted: each rule taken out.
test_code_mr_merge_retry*  after `land` sends a code/<id> merge request, /kb-sprint run step 4 and /kb-item step 7 read
                it (glab mr view) and retry an auto-merge that failed (state opened with a merge_error) once with a
                plain glab mr merge, naming the error; the runbook agrees. Planted: each rule taken out.
test_sprint_brief_known_failures*  /kb-sprint run's brief names each test the orchestrator knows fails on the host, with
                the bug filed for it (id and title) and its cause, so a worker files no duplicate and guesses no cause;
                the runbook agrees. Planted: each rule taken out.
test_sprint_second_clone_worktree*  a sprint in a second clone is orchestrated from a fresh session in that clone, else
                each worker gets a worktree and work/<id> branch of it made by hand after the claim sync, the agent run
                without isolation and briefed with the path; the runbook agrees. Planted: each rule taken out.
test_kb_topics_for_imports_arg_*  the imports argument of kb_topics_for and rag.py topics-for --imports reach imports mode
                (a comment's name finds nothing, a declared package does); only the boolean true switches it; under --roots it
                goes with text; a planted ignored argument is caught.
test_decision_lookup_mcp_*  kb_pack, kb_show and kb_audit with a root's decisions (`include_invalidated` on kb_pack and
                kb_show): the labels, the coverage an active decision gives, the decisions of the lines kb_show prints, the
                possible contradictions in kb_audit; planted: no decision file, and a string where the boolean true goes.
test_lookup_shows_log_lines_mcp  kb_pack, kb_show and kb_audit print a root's active LOG rows (observed signal, with the dates
                they cover) beside the facts of the matched article, none for a proposed, an invalidated or an unrelated
                row, and the pack's coverage line is the one it has with no row; planted: no `_logs.csv`.
test_embed_roots_*  `--roots NAME[,NAME]` (a host embedding the server): only the named roots in every tool and
                kb_status, every root without it, and an unknown or missing name refused at the start on stderr.
test_status_*   how far a clone or an installed plugin is behind the kb it follows, from local refs: the update
                command (checking out the newest census tag for a clone detached at one), and under --roots the
                kb copy line and kb_status keep the staleness but name no local path and no command.
test_kb_mcp_pack_ignores_freshness_banner  the tests that assert pack text start the server with quiet_upstream
                (KB_NO_UPSTREAM=1), so they pass in a clone or worktree behind its upstream: in a planted behind
                clone the pack opens with its verdict that way and with the kb copy line without it.
test_live_docs_cache_*  docs_search and docs_fetch against an in-process HTTP stub (no network): the client's
                handshake (session id and protocol version echoed, JSON and SSE replies); the same server and query
                within 7 days makes no second HTTP call, an 8-day-old entry makes one; a query, a server or a tool
                that differs is its own entry; an error is never cached; only the unlimited stdio server lists the tools;
                _cache/ is git-ignored; planted failures (a broken cache, an ignored expiry) are caught.
test_embed_contract_*  kb_mcp.py as a host server's stdio child: the names and input schemas of kb_pack, kb_search and
                kb_show and the instructions' sha256 match _tools/fixtures/kb_mcp_contract.json unless kb_mcp.VERSION
                moved; one call of each answers in shape; a planted schema change is caught. After a VERSION bump:
                `uv run --frozen python _tools/test_kb_mcp.py --write-contract`.
test_skill_section_git_doc*  no .claude/skills/*/SKILL.md passes the doc to `selfdoc.py section` as a bare `git`, which a
                worktree session's isolation check reads as a second git call and refuses; skills pass `git.md`, which
                selfdoc.py takes as the bare name. Planted: a code-block and an inline command with bare `git`.
"""
import hashlib, json, os, re, shlex, shutil, subprocess, sys, tempfile
from pathlib import Path

import pytest

from conftest import KB, P, Q, TOOLS, git_env, timeout_s

import kb_mcp  # noqa: E402  (conftest puts _tools on sys.path)

SERVER = os.path.join(TOOLS, "kb_mcp.py")
REMOTE = "git@gitlab.com:mikkielt/it-ops-kb.git"
DOCS_PLUGIN = ".claude-plugin/it-ops-kb-docs"
# Every shell a shell-form command hook can reach (kb/public/claude/hooks.md): sh -c on macOS and Linux, Git Bash on
# Windows, PowerShell (pwsh, else Windows PowerShell, with -Command) on Windows without Git Bash; each one present runs.


def wsl_dirs(env=None):
    """Where Windows puts WSL's bash launcher: the Windows directory (System32\\bash.exe) and the app execution
    aliases (%LOCALAPPDATA%\\Microsoft\\WindowsApps\\bash.exe); none off Windows."""
    env = os.environ if env is None else env
    windir = env.get("SystemRoot") or env.get("WINDIR")
    local = env.get("LOCALAPPDATA")
    return [d for d in (windir, local and os.path.join(local, "Microsoft", "WindowsApps")) if d]


def is_wsl_launcher(path, dirs=None):
    """Whether a POSIX shell found on PATH is WSL's launcher (a bash or sh under wsl_dirs): Claude Code never runs
    hooks with it, and with no Linux distribution installed it prints a UTF-16 notice and exits 1."""
    p = os.path.normcase(os.path.abspath(path))
    for d in wsl_dirs() if dirs is None else dirs:
        w = os.path.normcase(os.path.abspath(d))
        try:
            if os.path.commonpath([p, w]) == w:
                return True
        except ValueError:  # another drive
            pass
    return False


def _starts(path):
    """Whether `sh -c 'exit 0'` exits 0 in this shell (a launcher with nothing to launch does not)."""
    try:
        return subprocess.run([path, "-c", "exit 0"], capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def hook_shells(which=shutil.which, starts=_starts):
    """[(name, argv before the command)] of the hook shells present: sh, bash and dash but WSL's launcher (and, on
    Windows, any that fails `-c 'exit 0'`), then pwsh and Windows PowerShell."""
    def real(p):
        return not is_wsl_launcher(p) and (os.name != "nt" or starts(p))
    return ([(n, [p, "-c"]) for n in ("sh", "bash", "dash") if (p := which(n)) and real(p)]
            + [(n, [p, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command"])
               for n in ("pwsh", "powershell") if (p := which(n))])


HOOK_SHELLS = hook_shells()


def block_offenders(cmd):
    """The shells present in which the submit_feedback hook command `cmd` does not block: exit 2 blocks a PreToolUse
    call with stderr as the reason, while any other exit (a PowerShell parser error exits 1) lets the call through."""
    bad = []
    for name, argv in HOOK_SHELLS:
        p = subprocess.run(argv + [cmd], input=b'{"tool_name": "x"}', capture_output=True, timeout=60)
        err = p.stderr.decode("utf-8", "replace").strip()
        if p.returncode != 2 or p.stdout.strip() or "submit_feedback posts text to the docs vendor" not in err:
            bad.append(f"{name}: exit {p.returncode}, stdout {p.stdout.strip()[:80]!r}, stderr {err[:120]!r}")
    return bad


def quiet_upstream(env=None):
    """`env` (default os.environ) with KB_NO_UPSTREAM=1. A clone or worktree behind the branch it follows (a CI
    checkout, a sprint worktree while main moves on) opens every kb_pack with a `kb copy: N commits behind` line
    above `coverage:`; every test that asserts pack text starts the server with this, so the line is left out."""
    return {**(os.environ if env is None else env), "KB_NO_UPSTREAM": "1"}


def follow_upstream(env):
    """`env` without KB_NO_UPSTREAM, for the tests that plant a behind clone and assert the kb copy line."""
    return {k: v for k, v in env.items() if k != "KB_NO_UPSTREAM"}


def load(rel):
    with open(os.path.join(KB, rel), encoding="utf-8") as f:
        return json.load(f)


KB_WORKER = ".claude/agents/kb-worker.md"


def kb_worker_problems(text, plugin_agents):
    """What is wrong with the kb-worker agent file `text` and the plugin's agent list: [] when nothing."""
    head = text.split("\n---", 1)[0]
    fm = dict(re.findall(r"(?m)^(\w+):[ \t]*(.*?)[ \t]*$", head))
    problems = []
    if fm.get("name") != "kb-worker":
        problems.append(f"name is {fm.get('name')!r}, not kb-worker")
    if fm.get("model") != "sonnet":
        problems.append(f"model is {fm.get('model')!r}: the sonnet alias follows the newest Sonnet; "
                        "a full id pins one and inherit takes the session's")
    if fm.get("effort") != "high":
        problems.append(f"effort is {fm.get('effort')!r}, not high")
    if any(Path(a).name == Path(KB_WORKER).name for a in plugin_agents):
        problems.append("kb-worker is listed in plugin.json: it is a clone-only agent")
    return problems


KB_SPRINT = ".claude/skills/kb-sprint/SKILL.md"
KB_CENSUS = ".claude/skills/kb-census/SKILL.md"
RUNBOOK = "kb/_self/backlog.md"


def md_section(text, heading):
    """The body under the Markdown heading line `heading` up to the next heading of the same or a higher level."""
    level = len(heading) - len(heading.lstrip("#"))
    m = re.search(rf"(?m)^{re.escape(heading)}[ \t]*$", text)
    if not m:
        return ""
    end = re.search(rf"(?m)^#{{1,{level}}} ", text[m.end():])
    return text[m.end():m.end() + end.start()] if end else text[m.end():]


def kb_worker_dispatch_problems(sprint, census, runbook):
    """What is wrong with how /kb-sprint (`sprint`), /kb-census (`census`) and the runbook (`runbook`) dispatch
    subagents to kb-worker: [] when nothing."""
    problems = []
    run = md_section(sprint, "## run [SP]")
    step3 = re.search(r"(?ms)^3\. Start one subagent.*?(?=^\d+\. )", run)
    step3 = step3.group(0) if step3 else ""
    if not re.search(r"(?m)^\s*- a task or subtask: `subagent_type: \"kb-worker\"`", step3):
        problems.append("/kb-sprint run step 3 does not start a task or subtask with subagent_type kb-worker")
    if not re.search(r"Never pass the Agent tool's `model`", step3):
        problems.append("/kb-sprint run step 3 does not forbid passing a model")
    session = [l for l in step3.splitlines() if "session model" in l]
    if not any("`S1` or `S2` bug" in l and "no tasks yet" in l and "kb-worker" not in l for l in session):
        problems.append("/kb-sprint run step 3 does not send S1 and S2 bugs and a story or bug with no tasks "
                        "to the session model")
    if "kb-worker" in md_section(sprint, "## review SP"):
        problems.append("/kb-sprint review names kb-worker: the review keeps the session model")
    if "kb-worker" in census:
        problems.append("/kb-census names kb-worker: census subagents keep the session model")
    work = md_section(runbook, "## Working on items")
    bullet = next((l for l in work.splitlines() if "`kb-worker`" in l), "")
    for phrase in ("task or subtask", "no `model`", "`S1` or `S2` bug", "no tasks yet", "session model",
                   "sprint review", "`/kb-census`"):
        if phrase not in bullet:
            problems.append(f"the runbook's Working on items does not say {phrase!r} with kb-worker")
    return problems


def kb_worker_fallback_problems(sprint, runbook):
    """What is wrong with the fallback /kb-sprint run step 3 (`sprint`) and the runbook (`runbook`) give for a
    session whose Agent tool does not list kb-worker: [] when nothing."""
    problems = []
    step3 = re.search(r"(?ms)^3\. Start one subagent.*?(?=^\d+\. )", md_section(sprint, "## run [SP]"))
    work = md_section(runbook, "## Working on items")
    for where, text in (("/kb-sprint run step 3", step3.group(0) if step3 else ""),
                        ("the runbook's Working on items", work)):
        line = next((l for l in text.splitlines() if "does not list `kb-worker`" in l), "")
        if not line:
            problems.append(f"{where} has no fallback for an Agent tool that does not list kb-worker")
            continue
        for phrase in ("session start", "general-purpose", "sonnet", "`.claude/agents/kb-worker.md`"):
            if phrase not in line:
                problems.append(f"{where}'s kb-worker fallback does not say {phrase!r}")
        if not re.search(r"`model: \"?sonnet\"?`", line):
            problems.append(f"{where}'s kb-worker fallback does not pass `model: sonnet`")
        if "exception" not in line and "the one `model`" not in line:
            problems.append(f"{where}'s kb-worker fallback does not mark itself the exception to passing no model")
    return problems


FAST_TESTS = "python3 _tools/tests.py --changed origin/main"


def kb_worker_ruff_problems(worker):
    """What is wrong with kb-worker's rule 4 (`worker`) on running the gate's ruff check for a changed Python file:
    [] when nothing."""
    rule = re.search(r"(?ms)^4\. \*\*The sync gate's own checks.*?(?=^\d+\. )", worker)
    sentence = next((s for s in re.split(r"(?<=\.) ", rule.group(0)) if "tests.py -k" in s), "") if rule else ""
    problems = []
    if not rule:
        problems.append("kb-worker has no rule 4 on the sync gate's own checks")
    if 'tests.py -k "ruff or tools_map"' not in sentence:
        problems.append("kb-worker's rule 4 does not run the ruff and tools_map tests")
    if "any Python file" not in sentence or "`.claude/**/*.py`" not in sentence or "`_tools/`" not in sentence:
        problems.append("kb-worker's rule 4 does not run them for any Python file the gate's ruff covers (`.claude/**/*.py`, `_tools/`)")
    return problems


def kb_worker_load_problems(worker, sprint, runbook):
    """What is wrong with the test load kb-worker (`worker`), /kb-sprint run (`sprint`) and the runbook (`runbook`)
    put on a host that runs up to four workers at once: [] when nothing."""
    problems = []
    bar = re.search(r"(?ms)^3\. \*\*Done bar\.\*\*.*?(?=^\d+\. )", worker)
    bar = bar.group(0) if bar else ""
    if FAST_TESTS not in bar:
        problems.append(f"kb-worker's done bar does not run the fast tests, `{FAST_TESTS}`")
    for sentence in re.split(r"(?<=\.) ", bar):
        full = re.search(r"`python3 _tools/tests\.py`", sentence)
        mine = "never" not in sentence.lower() and "orchestrator" not in sentence.lower()
        if (full or "stress_test.py" in sentence) and mine:
            problems.append(f"kb-worker's done bar runs the full tests or the stress suite: {sentence.strip()!r}")
    if not re.search(r"Never run `python3 _tools/stress_test\.py`", bar):
        problems.append("kb-worker's done bar does not forbid stress_test.py")
    if "never a second" not in bar:
        problems.append("kb-worker's done bar does not forbid a second run")
    if "sibling items in flight" not in bar:
        problems.append("kb-worker's done bar does not keep off the in-flight siblings' files")
    run = md_section(sprint, "## run [SP]")
    step3 = re.search(r"(?ms)^3\. Start one subagent.*?(?=^\d+\. )", run)
    brief = [l for l in (step3.group(0) if step3 else "").splitlines() if l.lstrip().startswith("- ")]
    if not any("in-flight sibling items" in l and "id and title" in l and "files" in l for l in brief):
        problems.append("/kb-sprint run's brief does not name the in-flight sibling items (id and title) and their files")
    if not any(FAST_TESTS in l and "never `python3 _tools/stress_test.py`" in l for l in brief):
        problems.append("/kb-sprint run's brief does not give the fast tests and forbid stress_test.py")
    step4 = re.search(r"(?ms)^4\. When a subagent returns.*?(?=^\d+\. )", run)
    land = [l for l in (step4.group(0) if step4 else "").splitlines() if "stress_test.py" in l]
    if not any("`python3 _tools/stress_test.py` once" in l and "changed `_tools/`" in l for l in land):
        problems.append("/kb-sprint run's landing does not run stress_test.py once for a change to _tools/")
    work = md_section(runbook, "## Working on items")
    line = next((l for l in work.splitlines() if FAST_TESTS in l), "")
    for phrase in ("never `stress_test.py`", "sibling", "files", "once per landing", "`_tools/`"):
        if phrase not in line:
            problems.append(f"the runbook's Working on items does not say {phrase!r} with the fast tests")
    return problems


GATE_ADD = "gate add ID --kind provisional"
GATE_ANSWER = "answer ID GATE --provisional"
LANDED_BY_GATES = "answered or provisional"


def worker_provisional_gate_problems(worker, sprint, runbook):
    """What is wrong with how kb-worker (`worker`), /kb-sprint (`sprint`) and the runbook (`runbook`) turn a choice an
    item's goal leaves open into a provisional gate, land the item only after its gates are answered or provisional,
    and have the review confirm them: [] when nothing."""
    problems = []
    rule = re.search(r"(?ms)^6\. \*\*Choices.*?(?=^\d+\. )", worker)
    rule = rule.group(0) if rule else ""
    for phrase, what in ((GATE_ADD, "record a provisional gate"), (GATE_ANSWER, "answer it --provisional"),
                         ("with the work", "commit it with the work"), ("prose", "rule out report prose"),
                         (LANDED_BY_GATES, "say the item lands only once its gates are answered or provisional"),
                         ("confirm", "say the review confirms the answers")):
        if phrase not in rule:
            problems.append(f"kb-worker's rule 6 does not {what} ({phrase!r})")
    run = md_section(sprint, "## run [SP]")
    step3 = re.search(r"(?ms)^3\. Start one subagent.*?(?=^\d+\. )", run)
    brief = [l for l in (step3.group(0) if step3 else "").splitlines() if l.lstrip().startswith("- ")]
    if not any("provisional gate" in l and "`--provisional`" in l and "with the work" in l and "prose" in l
               for l in brief):
        problems.append("/kb-sprint run's brief does not ask for a provisional gate, answered and committed with the "
                        "work, instead of report prose")
    step4 = re.search(r"(?ms)^4\. When a subagent returns.*?(?=^\d+\. )", run)
    step4 = step4.group(0) if step4 else ""
    gates = re.search(rf"(?m)^\s*1\. Land an item only after its gates are {LANDED_BY_GATES}\..*$", step4)
    land = step4.find("backlog.py land ID")
    if not gates or land < 0 or gates.start() > land:
        problems.append("/kb-sprint run step 4 does not land an item only after its gates are answered or "
                        "provisional, before `backlog.py land`")
    elif "git show work/<id>:kb/_self/backlog/<id>.json" not in gates.group(0) or "review" not in gates.group(0):
        problems.append("/kb-sprint run step 4.1 does not read the gates on the branch and hand them to the review")
    review = md_section(sprint, "## review SP")
    first = next((l for l in review.splitlines() if l.startswith("1. ")), "")
    if "provisional answer" not in first or "run step 4.1" not in first:
        problems.append("/kb-sprint review step 1 does not confirm the provisional answers of run step 4.1")
    work = md_section(runbook, "## Working on items")
    if not any(LANDED_BY_GATES in l and "`.claude/agents/kb-worker.md`" in l and "provisional gate" in l
               for l in work.splitlines()):
        problems.append("the runbook's Working on items does not land an item only after its gates are answered "
                        "or provisional")
    gates_doc = md_section(runbook, "## Dependencies, gates and triggers")
    if not any("goal leaves open" in l and GATE_ADD in l and f"`{GATE_ANSWER}`" in l
               and "with the work" in l for l in gates_doc.splitlines()):
        problems.append("the runbook's gates section does not make a choice the goal leaves open a provisional gate")
    return problems


def worker_provisional_gate_texts():
    texts = []
    for rel in (KB_WORKER, KB_SPRINT, RUNBOOK):
        with open(os.path.join(KB, rel), encoding="utf-8") as f:
            texts.append(f.read())
    return texts


def test_worker_provisional_gate():
    """A worker records a choice its goal leaves open as a provisional gate, answered and committed with the work, not
    report prose; /kb-sprint run lands an item only after its gates are answered or provisional; the review confirms
    them (SP-ufr3qnff)."""
    assert worker_provisional_gate_problems(*worker_provisional_gate_texts()) == []


@pytest.mark.parametrize("i, old, new", [
    (0, "--kind provisional --question", "--question"),
    (0, "answer ID GATE --provisional", "answer ID GATE"),
    (0, "Commit the item file with the work", "Commit the item file later"),
    (0, "never leave a choice in your report's prose only", "name each choice in your report"),
    (0, "only once each of its gates is answered or provisional", "as it is"),
    (1, "never prose in the report only", "or describe it in the report"),
    (1, "1. Land an item only after its gates are answered or provisional.", "1. Land the item."),
    (1, "(run step 4.1) among them", "among them"),
    (2, "lands it only after each gate is answered or provisional", "lands it"),
    (2, "commits with the work, never only a line in its report", "may name it in its report"),
])
def test_worker_provisional_gate_planted_failures(i, old, new):
    """Each rule fails on a planted copy of the agent, the skill or the runbook without it."""
    texts = worker_provisional_gate_texts()
    planted = texts[i].replace(old, new, 1)
    assert planted != texts[i], f"plant does not apply: {old!r}"
    texts[i] = planted
    assert worker_provisional_gate_problems(*texts), f"not caught: {old!r} -> {new!r}"


SETTINGS = ".claude/settings.json"
BASE_REF = "`worktree.baseRef`"


def sprint_worker_base_problems(settings, worker, sprint, runbook):
    """What is wrong with where a /kb-sprint worker's worktree starts: the project settings (`settings`, JSON text)
    branch isolation worktrees from the orchestrator's HEAD; /kb-sprint run (`sprint`) dispatches only after the claim
    sync; kb-worker (`worker`) checks its base against origin/main and rebases only if behind, with no checkout by
    hand; the runbook (`runbook`) agrees. [] when nothing."""
    problems = []
    try:
        base = (json.loads(settings).get("worktree") or {}).get("baseRef")
    except (ValueError, AttributeError):
        base = None
    if base != "head":
        problems.append(f"{SETTINGS} sets worktree.baseRef to {base!r}, not \"head\"")
    run = md_section(sprint, "## run [SP]")
    step2 = re.search(r"(?ms)^2\. From the ready list.*?(?=^\d+\. )", run)
    step2 = step2.group(0) if step2 else ""
    if "--commit" not in step2 or "kbgit.py sync --push" not in step2 or "claim sync" not in step2:
        problems.append("/kb-sprint run step 2 does not commit the claims and push them (the claim sync)")
    step3 = re.search(r"(?ms)^3\. Start one subagent.*?(?=^\d+\. )", run)
    line = next((l for l in (step3.group(0) if step3 else "").splitlines() if BASE_REF in l), "")
    for phrase in ('`"head"`', "`HEAD`", "pushed claim commits", "dispatch only after the claim sync",
                   "by hand", "rebases only if behind"):
        if phrase not in line:
            problems.append(f"/kb-sprint run step 3 does not say {phrase!r} with {BASE_REF}")
    rule = re.search(r"(?ms)^2\. \*\*Branch and commits\.\*\*.*?(?=^\d+\. )", worker)
    rule = rule.group(0) if rule else ""
    for phrase in (BASE_REF, '`"head"`', "orchestrator's branch tip", "no checkout by hand",
                   "git merge-base --is-ancestor origin/main HEAD", "git rebase origin/main", "only if behind"):
        if phrase not in rule:
            problems.append(f"kb-worker's rule 2 does not say {phrase!r}")
    work = md_section(runbook, "## Working on items")
    bullet = next((l for l in work.splitlines() if BASE_REF in l), "")
    for phrase in ('`"head"`', "orchestrator's branch tip", "pushed claim commits", "only after its claim sync",
                   "rebases only if behind", "no checkout by hand"):
        if phrase not in bullet:
            problems.append(f"the runbook's Working on items does not say {phrase!r} with {BASE_REF}")
    return problems


def sprint_worker_base_texts():
    texts = []
    for rel in (SETTINGS, KB_WORKER, KB_SPRINT, RUNBOOK):
        with open(os.path.join(KB, rel), encoding="utf-8") as f:
            texts.append(f.read())
    return texts


def test_sprint_worker_starts_from_orchestrator_tip():
    """A /kb-sprint worker's worktree branches from the orchestrator's HEAD (worktree.baseRef "head"), claim commits
    included, so its work lands without a cherry-pick (SP-4fbfzobr, where every worker began on a stale base)."""
    assert sprint_worker_base_problems(*sprint_worker_base_texts()) == []


@pytest.mark.parametrize("i, old, new", [
    (0, '"baseRef": "head"', '"baseRef": "fresh"'),
    (0, '"worktree": {\n    "baseRef": "head"\n  },\n', ""),
    (1, "no checkout by hand", "check out `origin/main`"),
    (1, "rebase (`git rebase origin/main`) only if behind", "always rebase (`git rebase origin/main`)"),
    (1, "`git merge-base --is-ancestor origin/main HEAD`", "`git status`"),
    (2, "then push the claims once, the claim sync: `python3 _tools/kbgit.py sync --push`", ""),
    (2, "so dispatch only after the claim sync of step 2", "so dispatch at once"),
    (2, "`worktree.baseRef` to `\"head\"`", "`worktree.baseRef` to `\"fresh\"`"),
    (2, "The brief names no base to check out by hand", "The brief names the base to check out"),
    (3, "only after its claim sync", "at once"),
    (3, "rebases only if behind, with no checkout by hand", "checks out the orchestrator's branch"),
])
def test_sprint_worker_starts_from_orchestrator_tip_planted_failures(i, old, new):
    """Each rule fails on a planted copy of the settings, the agent, the skill or the runbook without it."""
    texts = sprint_worker_base_texts()
    planted = texts[i].replace(old, new, 1)
    assert planted != texts[i], f"plant does not apply: {old!r}"
    texts[i] = planted
    assert sprint_worker_base_problems(*texts), f"not caught: {old!r} -> {new!r}"


KB_ITEM = ".claude/skills/kb-item/SKILL.md"
MR_VIEW = "`glab mr view code/<id> -F json -R <project url>`"
MR_MERGE = "`python3 _tools/backlog.py merge <id>`"


def code_mr_merge_retry_problems(sprint, item, runbook):
    """What is wrong with how /kb-sprint run step 4 (`sprint`), /kb-item step 7 (`item`) and the runbook (`runbook`)
    follow a `code/<id>` merge request after `land` sent it: read its state, and when its auto-merge failed (`opened`
    with a `merge_error`) retry once with a plain merge and name the error. [] when nothing."""
    run = md_section(sprint, "## run [SP]")
    step4 = re.search(r"(?ms)^4\. When a subagent returns.*?(?=^\d+\. )", run)
    step7 = re.search(r"(?ms)^7\. \*\*Prove and land\*\*.*?(?=^\d+\. )", item)
    work = md_section(runbook, "## Working on items")
    problems = []
    for where, text in (("/kb-sprint run step 4", step4.group(0) if step4 else ""),
                        ("/kb-item step 7", step7.group(0) if step7 else ""),
                        ("the runbook's Working on items", work)):
        line = next((l for l in text.splitlines() if MR_VIEW in l), "")
        if not line:
            problems.append(f"{where} does not read the code/<id> request's state with {MR_VIEW}")
            continue
        for phrase in ("`opened` with a `merge_error`", MR_MERGE, "name", "the error", "third time"):
            if phrase not in line:
                problems.append(f"{where} does not say {phrase!r} with the request's state")
        if not re.search(r"retr(y|ies) once", line):
            problems.append(f"{where} does not retry a failed auto-merge once")
        if line.find(MR_VIEW) > line.find(MR_MERGE):
            problems.append(f"{where} merges before it reads the request's state")
    return problems


def code_mr_merge_retry_texts():
    texts = []
    for rel in (KB_SPRINT, KB_ITEM, RUNBOOK):
        with open(os.path.join(KB, rel), encoding="utf-8") as f:
            texts.append(f.read())
    return texts


def test_code_mr_merge_retry():
    """After `land` sends a code/<id> merge request, the session reads its state and retries a failed auto-merge once
    with a plain `glab mr merge`, naming the error (SP-rhgeod5g, a pre-receive hook error on auto-merge)."""
    assert code_mr_merge_retry_problems(*code_mr_merge_retry_texts()) == []


@pytest.mark.parametrize("i, old, new", [
    (0, "read the request: `glab mr view code/<id> -F json -R <project url>`", "wait for the request"),
    (0, "`state` `opened` with a `merge_error`", "a request still open"),
    (0, "retry once with", "retry with"),
    (0, "and name the error in your report", "and go on"),
    (1, "`python3 _tools/backlog.py merge <id>`", "`glab mr merge code/<id>`"),
    (1, "never tried a third time", "tried again"),
    (2, "reads the request itself, `glab mr view code/<id> -F json -R <project url>`", "waits"),
    (2, "retries once", "retries"),
])
def test_code_mr_merge_retry_planted_failures(i, old, new):
    """Each rule fails on a planted copy of the sprint skill, the item skill or the runbook without it."""
    texts = code_mr_merge_retry_texts()
    planted = texts[i].replace(old, new, 1)
    assert planted != texts[i], f"plant does not apply: {old!r}"
    texts[i] = planted
    assert code_mr_merge_retry_problems(*texts), f"not caught: {old!r} -> {new!r}"


KNOWN_FAILURES = "known failing tests"


def sprint_brief_known_failures_problems(sprint, runbook):
    """What is wrong with how /kb-sprint run's brief (`sprint`) and the runbook (`runbook`) name the tests the
    orchestrator already knows fail on the host: each with its bug and cause, so a worker files no duplicate and
    guesses no cause. [] when nothing."""
    problems = []
    step3 = re.search(r"(?ms)^3\. Start one subagent.*?(?=^\d+\. )", md_section(sprint, "## run [SP]"))
    brief = [l for l in (step3.group(0) if step3 else "").splitlines() if l.lstrip().startswith("- ")]
    work = md_section(runbook, "## Working on items")
    for where, lines in (("/kb-sprint run's brief", brief), ("the runbook's Working on items", work.splitlines())):
        line = next((l for l in lines if KNOWN_FAILURES in l), "")
        if not line:
            problems.append(f"{where} does not name the {KNOWN_FAILURES}")
            continue
        for phrase in ("fails on the host", "the bug filed for it", "id and title", "its cause", "files it again",
                       "guesses a cause", "worker's to file"):
            if phrase not in line:
                problems.append(f"{where} does not say {phrase!r} with the {KNOWN_FAILURES}")
    return problems


def sprint_brief_known_failures_texts():
    texts = []
    for rel in (KB_SPRINT, RUNBOOK):
        with open(os.path.join(KB, rel), encoding="utf-8") as f:
            texts.append(f.read())
    return texts


def test_sprint_brief_known_failures():
    """/kb-sprint run's brief names each test the orchestrator knows fails on the host, with its bug and cause
    (SP-rhgeod5g, where two workers each filed a duplicate bug with a wrong cause)."""
    assert sprint_brief_known_failures_problems(*sprint_brief_known_failures_texts()) == []


@pytest.mark.parametrize("i, old, new", [
    (0, "   - the known failing tests: ", "   - the failing tests: "),
    (0, "with the bug filed for it (id and title) and its cause", "if any"),
    (0, "so the worker neither files it again nor guesses a cause", "for the record"),
    (0, "a failure the brief does not name is the worker's to file", "the worker skips any failure"),
    (1, "and the known failing tests: ", "and the failing tests: "),
    (1, "with the bug filed for it (id and title) and its cause", "if any"),
    (1, "so a worker neither files it again nor guesses a cause", "for the record"),
])
def test_sprint_brief_known_failures_planted_failures(i, old, new):
    """Each rule fails on a planted copy of the sprint skill or the runbook without it."""
    texts = sprint_brief_known_failures_texts()
    planted = texts[i].replace(old, new, 1)
    assert planted != texts[i], f"plant does not apply: {old!r}"
    texts[i] = planted
    assert sprint_brief_known_failures_problems(*texts), f"not caught: {old!r} -> {new!r}"


SECOND_CLONE = "A sprint in a second clone"
WORKTREE_ADD = "`git -C <clone> worktree add <clone>/.claude/worktrees/<id> -b work/<id> origin/main`"


def sprint_second_clone_worktree_problems(sprint, runbook):
    """What is wrong with how /kb-sprint run step 3 (`sprint`) and the runbook (`runbook`) give each worker its own
    worktree and work/<id> branch of a second clone, where the Agent tool's isolation would branch from the session's
    clone: [] when nothing."""
    problems = []
    step3 = re.search(r"(?ms)^3\. Start one subagent.*?(?=^\d+\. )", md_section(sprint, "## run [SP]"))
    work = md_section(runbook, "## Working on items")
    for where, text in (("/kb-sprint run step 3", step3.group(0) if step3 else ""),
                        ("the runbook's Working on items", work)):
        line = next((l for l in text.splitlines() if SECOND_CLONE in l), "")
        if not line:
            problems.append(f"{where} does not say how to run workers from a second clone")
            continue
        for phrase in ("fresh Claude session", "no working directory of its own", "wrong clone", "after the claim sync",
                       "`git -C <clone> fetch origin`", WORKTREE_ADD, "without `isolation`", "names that path in the brief",
                       "absolute path"):
            if phrase not in line:
                problems.append(f"{where} does not say {phrase!r} for a sprint in a second clone")
        if 0 <= line.find(WORKTREE_ADD) < line.find("fresh Claude session"):
            problems.append(f"{where} puts the hand-made worktree before the fresh session in the clone")
    return problems


def sprint_second_clone_worktree_texts():
    texts = []
    for rel in (KB_SPRINT, RUNBOOK):
        with open(os.path.join(KB, rel), encoding="utf-8") as f:
            texts.append(f.read())
    return texts


def test_sprint_second_clone_worktree():
    """A sprint run in a second clone starts its workers in that clone: a fresh session there, else a worktree and
    work/<id> branch made by hand with the agent run without isolation (SP-xourq2gj)."""
    assert sprint_second_clone_worktree_problems(*sprint_second_clone_worktree_texts()) == []


@pytest.mark.parametrize("i, old, new", [
    (0, "   A sprint in a second clone (", "   A sprint elsewhere ("),
    (0, "Start a fresh Claude session in that clone and orchestrate from there. ", ""),
    (0, "-b work/<id> origin/main`; it starts", "`; it starts"),
    (0, "starts the subagent without `isolation`", "starts the subagent with `isolation`"),
    (0, "by absolute path into it", "in it"),
    (1, "is orchestrated from a fresh Claude session started in that clone", "is orchestrated as any other"),
    (1, "after the claim sync, `git -C", "at once, `git -C"),
    (1, "and names that path in the brief", "and briefs it"),
])
def test_sprint_second_clone_worktree_planted_failures(i, old, new):
    """Each rule fails on a planted copy of the sprint skill or the runbook without it."""
    texts = sprint_second_clone_worktree_texts()
    planted = texts[i].replace(old, new, 1)
    assert planted != texts[i], f"plant does not apply: {old!r}"
    texts[i] = planted
    assert sprint_second_clone_worktree_problems(*texts), f"not caught: {old!r} -> {new!r}"


class TestKbServer:
    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def server(cls):
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "kb_search", "arguments": {"query": "kerberos constrained delegation", "k": 3,
                                                           "response_format": "detailed"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
             "params": {"name": "kb_search", "arguments": {"query": "zanzibarquux flibbertigibbet"}}},
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
             "params": {"name": "kb_show", "arguments": {"path": "README.md:1", "n": 3}}},
            {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "kb_source", "arguments": {"ids": ["S100", "S99999"]}}},
            {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "kb_status", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"name": "kb_show", "arguments": {"path": "../etc/passwd"}}},
            {"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "no_such_tool", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 10, "method": "no/such/method"},
            {"jsonrpc": "2.0", "id": 11, "method": "server/discover",
             "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"}}},
            {"jsonrpc": "2.0", "id": 12, "method": "tools/list",
             "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "1999-01-01"}}},
            {"jsonrpc": "2.0", "id": 13, "method": "tools/call",
             "params": {"name": "kb_pack", "arguments": {"question": "Does deleting an Entra device delete its BitLocker keys?"}}},
            {"jsonrpc": "2.0", "id": 14, "method": "tools/call",
             "params": {"name": "kb_audit", "arguments": {"prefix": "ad", "status": "complete"}}},
            {"jsonrpc": "2.0", "id": 15, "method": "tools/call",
             "params": {"name": "kb_facts", "arguments": {"prefix": "ad/computer-attributes", "tags": ["UNK"]}}},
            {"jsonrpc": "2.0", "id": 16, "method": "tools/call",
             "params": {"name": "kb_source", "arguments": {"ids": ["S100"], "cited": True}}},
            {"jsonrpc": "2.0", "id": 17, "method": "tools/call",
             "params": {"name": "kb_pack", "arguments": {"questions": [
                 "Does deleting an Entra device delete its BitLocker keys?", "When is NTLMv1 disabled by default?"]}}},
            {"jsonrpc": "2.0", "id": 18, "method": "tools/call",
             "params": {"name": "kb_facts", "arguments": {"prefix": "agents"}}},
            {"jsonrpc": "2.0", "id": 19, "method": "tools/call",
             "params": {"name": "kb_facts", "arguments": {"prefix": "agents", "response_format": "detailed"}}},
            {"jsonrpc": "2.0", "id": 20, "method": "tools/call",
             "params": {"name": "kb_topics_for", "arguments": {"text": "new PublicClientApplication(c); fetch('/AdminService/wmi/SMS_R_System')"}}},
            {"jsonrpc": "2.0", "id": 21, "method": "tools/call",
             "params": {"name": "kb_pack", "arguments": {"question": "x", "response_format": "verbose"}}},
            {"jsonrpc": "2.0", "id": 22, "method": "tools/call",
             "params": {"name": "kb_topics_for", "arguments": {"paths": [TOOLS + "/kb_mcp.py", "no/such/dir"]}}},
            {"jsonrpc": "2.0", "id": 23, "method": "tools/call",
             "params": {"name": "kb_pack", "arguments": {"question": "Does deleting an Entra device delete its BitLocker keys?",
                                                         "root": "public"}}},
            {"jsonrpc": "2.0", "id": 24, "method": "tools/call",
             "params": {"name": "kb_pack", "arguments": {"question": "bitlocker keys", "root": "no-such-root"}}},
            {"jsonrpc": "2.0", "id": 25, "method": "tools/call",
             "params": {"name": "kb_show", "arguments": {"path": Q("auth/kerberos.md") + ":1", "n": 1}}},
        ]
        stdin = "".join(json.dumps(m) + "\n" for m in msgs) + "this is not json\n"
        cls.proc = subprocess.run([sys.executable, SERVER], input=stdin, capture_output=True, text=True, encoding="utf-8", timeout=60,
                                  cwd=os.sep, env=quiet_upstream())
        cls.lines = [ln for ln in cls.proc.stdout.splitlines() if ln.strip()]
        cls.replies = [json.loads(ln) for ln in cls.lines]
        cls.by_id = {r.get("id"): r for r in cls.replies}

    def text(self, msg_id):
        r = self.by_id[msg_id]["result"]
        return r["isError"], r["content"][0]["text"]

    def test_exits_on_eof_and_stdout_is_only_jsonrpc(self):
        assert self.proc.returncode == 0, self.proc.stderr
        assert len(self.lines) == 26, "one reply per request, none for the notification"  # 25 requests + parse error
        for r in self.replies:
            assert r["jsonrpc"] == "2.0"

    def test_initialize(self):
        r = self.by_id[1]["result"]
        assert r["protocolVersion"] == "2025-06-18"
        assert "tools" in r["capabilities"]
        assert r["serverInfo"]["name"] == "kb"
        assert "UNK" in r["instructions"]

    def test_tools_list(self):
        tools = {t["name"]: t for t in self.by_id[2]["result"]["tools"]}
        assert sorted(tools) == ["docs_fetch", "docs_search", "kb_audit", "kb_facts", "kb_pack", "kb_search", "kb_show",
                                 "kb_source", "kb_status", "kb_topics_for"]
        for t in tools.values():
            assert t["inputSchema"]["type"] == "object"
            assert t["annotations"]["readOnlyHint"]
            if t["name"].startswith("docs_"):  # the live-docs tools say they are neither kb facts nor live device data
                assert t["description"].startswith("Live documentation from a remote docs server (not kb facts, not live "
                                                   "device or directory data)"), t["name"]
                continue
            assert t["description"].startswith("Documentation facts from it-ops-kb (not live device or directory data)"), \
                            f"{t['name']}: a host's live MECM/AD tools must not be confused with the kb"
        assert tools["kb_search"]["inputSchema"]["required"] == ["query"]
        always = [n for n, t in tools.items() if t.get("_meta", {}).get("anthropic/alwaysLoad")]
        assert always == ["kb_pack"], "only kb_pack skips tool search; the rest stay deferred"
        for n in ("kb_pack", "kb_facts", "kb_audit", "kb_search"):
            assert tools[n]["inputSchema"]["properties"]["response_format"]["enum"] == ["concise", "detailed"]
            assert tools[n]["inputSchema"]["properties"]["root"]["type"] == "string", f"{n} takes a root filter"
        assert tools["kb_pack"]["inputSchema"]["properties"]["response_format"]["default"] == "detailed"
        assert tools["kb_facts"]["inputSchema"]["properties"]["response_format"]["default"] == "concise"

    def test_kb_search_cites_paths_and_urls(self):
        err, text = self.text(3)
        assert not err
        assert re.search(r"(?m)^\[\d+(\.\d+)?\] [\w./-]+\.(md|csv):\d+  § ", text)
        assert re.search(r"(?m)^  -> S[-\w]+  https://", text)

    def test_kb_pack_audit_facts_cited(self):
        err, text = self.text(13)
        assert not err
        assert text.startswith("coverage: good"), text[:200]
        assert re.search(rf"(?m)^- {re.escape(Q('entra/bitlocker-key-deletion.md'))}:\d+ ", text), "paths print qualified"
        assert re.search(r"(?m)^  -> S[-\w]+  https://", text)
        err, text = self.text(14)
        assert not err
        assert f"| {Q('ad/computer-attributes.md')} | complete |" in text
        err, text = self.text(15)
        assert not err
        assert re.search(r"facts=\d+", text)
        err, text = self.text(16)
        assert not err
        assert re.search(r"cited at [\w/.-]+:\d+", text)

    def test_kb_pack_batch(self):
        err, text = self.text(17)
        assert not err
        assert len(re.findall(r"(?m)^# Q\d: ", text)) == 2
        assert len(re.findall(r"(?m)^coverage: ", text)) == 2, "a verdict per question"
        assert text.count("\nsources:") == 1, "one shared footer"
        err, text = self.text(21)
        assert err
        assert "response_format" in text

    def test_concise_facts_are_smaller(self):
        (e1, concise), (e2, detailed) = self.text(18), self.text(19)
        assert not (e1 or e2)
        assert re.search(r"facts=\d+", concise).group(0) == re.search(r"facts=\d+", detailed).group(0)
        assert len(concise) <= 0.7 * len(detailed), "concise must be at least 30% smaller"

    def test_kb_topics_for(self):
        err, text = self.text(20)
        assert not err
        assert re.search(rf"(?m)^- {Q('mecm/adminservice')}  .*AdminService", text), "topics print qualified"
        assert re.search(rf"(?m)^- {Q('auth/msal-public-client')}  PublicClientApplication \(1, text:1\)", text)
        err, text = self.text(22)
        assert not err
        assert "skipped: no/such/dir: no such file or directory" in text

    def test_kb_search_says_when_the_kb_lacks_it(self):
        err, text = self.text(4)
        assert not err
        assert "note: not found anywhere" in text
        assert "no match" in text

    def test_kb_show_and_its_bounds(self):
        err, text = self.text(5)
        assert not err
        assert "# README.md lines 1-3 of" in text
        assert "it-ops-kb" in text
        err, text = self.text(8)
        assert err
        assert "not a path inside the kb" in text
        err, text = self.text(25)
        assert not err
        assert text.startswith(f"# {Q('auth/kerberos.md')} lines 1-1 of"), text[:80]

    def test_root_filter(self):
        err, text = self.text(23)
        assert not err
        assert text == self.text(13)[1], "the public root alone gives the same pack when it is the only root"
        err, text = self.text(24)
        assert err
        assert "no root 'no-such-root'" in text and "roots: public" in text

    def test_kb_source(self):
        err, text = self.text(6)
        assert not err
        assert re.search(r"S100  .+\n  url: https?://", text)
        assert "S99999  UNKNOWN id" in text

    def test_kb_status(self):
        err, text = self.text(7)
        assert not err
        for key in ("kb_dir:", "commit:", "census_log:", "sources:", "newest_retrieved_utc:", "topics:", "roots: public (prefix S"):
            assert key in text

    def test_errors(self):
        assert self.by_id[9]["error"]["code"] == -32602
        assert self.by_id[10]["error"]["code"] == -32601
        assert self.by_id[None]["error"]["code"] == -32700
        e = self.by_id[12]["error"]
        assert (e["code"], e["data"]["requested"]) == (-32022, "1999-01-01")
        assert "2026-07-28" in e["data"]["supported"]

    def test_server_discover(self):
        r = self.by_id[11]["result"]
        assert "2026-07-28" in r["supportedVersions"]
        assert "tools" in r["capabilities"]
        assert r["cacheScope"] == "public"
        assert r["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "kb"

    def test_every_result_has_result_type(self):
        """2026-07-28 requires resultType on every result: Claude Code drops a tools/list without it (no kb tools)."""
        for r in self.replies:
            if "result" in r:
                assert r["result"].get("resultType") == "complete", r.get("id")


class TestPluginManifest:
    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def manifests(cls):
        cls.mkt = load(".claude-plugin/marketplace.json")
        cls.plugin = load(".claude-plugin/plugin.json")
        cls.docs = load(DOCS_PLUGIN + "/.claude-plugin/plugin.json")
        cls.servers = load(DOCS_PLUGIN + "/.mcp.json")["mcpServers"]

    def test_two_plugins_kb_and_docs(self):
        entries = {e["name"]: e for e in self.mkt["plugins"]}
        assert sorted(entries) == ["it-ops-kb", "it-ops-kb-docs"]
        assert entries["it-ops-kb"]["source"] == "."
        assert entries["it-ops-kb-docs"]["source"] == "./" + DOCS_PLUGIN
        assert self.plugin["name"] == "it-ops-kb", "entry name must equal the manifest name"
        assert self.docs["name"] == "it-ops-kb-docs"
        for obj in (self.mkt, *entries.values(), self.plugin, self.docs):
            assert "version" not in obj, "a pinned version would keep users on one copy; the commit sha tracks updates"
        assert self.plugin["repository"] == REMOTE
        assert self.docs["repository"] == REMOTE

    def test_no_docs_servers_in_the_kb_plugin(self):
        """A plugin sourced from the root loads a root .mcp.json whatever plugin.json says, so the docs servers live
        only in the docs plugin; a host that already has microsoft-learn installs only it-ops-kb."""
        assert not os.path.exists(os.path.join(KB, ".mcp.json")), "a root .mcp.json would load into it-ops-kb"
        assert sorted(self.plugin["mcpServers"]) == ["kb"]
        assert sorted(self.servers) == ["claude-code-docs", "mcp-docs", "microsoft-learn"]
        assert "mcpServers" not in self.docs

    def test_only_read_only_skills(self):
        assert self.plugin["skills"] == ["./.claude/skills/kb-lookup", "./.claude/skills/kb-review-workspace",
                                         "./.claude/skills/kb-gap"]
        assert not os.path.isdir(os.path.join(KB, "skills")), "a root skills/ directory would be loaded too"
        for rel in self.plugin["skills"] + self.plugin["agents"]:
            path = os.path.join(KB, rel, "SKILL.md") if not rel.endswith(".md") else os.path.join(KB, rel)
            with open(path, encoding="utf-8") as f:
                fm = f.read().split("\n---", 1)[0]
            for w in ("Write", "Edit", "NotebookEdit", "Bash", "git"):
                assert not re.search(rf"(?m)^(allowed-tools|tools):.*\b{w}\b", fm), f"{rel} may not use {w}"
        with open(os.path.join(KB, ".claude/skills/kb-lookup/SKILL.md"), encoding="utf-8") as f:
            lookup = f.read()
        assert "disable-model-invocation" not in lookup.split("\n---", 1)[0]
        assert f"mcp__plugin_{self.plugin['name']}_kb__kb_pack" in lookup
        with open(os.path.join(KB, ".claude/skills/kb-review-workspace/SKILL.md"), encoding="utf-8") as f:
            fm = f.read().split("\n---", 1)[0]
        for line in ("disable-model-invocation: true", "context: fork", "agent: it-ops-kb:kb-reviewer"):
            assert line in fm
        # the gap report is drafted for the user to paste: kb tools only, nothing written, sent or posted
        with open(os.path.join(KB, ".claude/skills/kb-gap/SKILL.md"), encoding="utf-8") as f:
            fm, body = f.read().split("\n---", 1)
        assert "disable-model-invocation: true" in fm
        tools = re.search(r"(?m)^allowed-tools:(.*)$", fm).group(1).split()
        assert tools and all(re.fullmatch(r"mcp__(plugin_it-ops-kb_kb|kb)__kb_\w+", t) for t in tools), tools
        assert "submit_feedback" in re.search(r"(?m)^disallowed-tools:(.*)$", fm).group(1)
        assert "corp.example.com" in body, "the draft replaces organisation data with the kb's placeholders"

    def test_agents(self):
        """The lookup agent is lean (kb tools only, small model, no CLAUDE.md); the reviewer reads code."""
        assert self.plugin["agents"] == ["./.claude/agents/kb-lookup.md", "./.claude/agents/kb-reviewer.md"]
        assert os.path.isdir(os.path.join(KB, P("agents"))), "the kb's agents/ articles: never a default scan"

        def fm(rel):
            with open(os.path.join(KB, rel), encoding="utf-8") as f:
                head = f.read().split("\n---", 1)[0]
            return dict(re.findall(r"(?m)^(\w+):[ \t]*(.*)$", head)), head
        lookup, raw = fm(".claude/agents/kb-lookup.md")
        assert (lookup["name"], lookup["model"], lookup["effort"], lookup["omitClaudeMd"]) == ("kb-lookup", "haiku", "low", "true")
        assert int(lookup["maxTurns"]) <= 6
        tools = [t.strip() for t in lookup["tools"].split(",")]
        assert all(re.fullmatch(r"mcp__(plugin_it-ops-kb_kb|kb)__kb_\w+", t) for t in tools), tools
        assert "- kb-lookup" in raw, "the lookup procedure is preloaded"
        reviewer, _ = fm(".claude/agents/kb-reviewer.md")
        assert (reviewer["name"], reviewer["model"]) == ("kb-reviewer", "sonnet")
        assert "omitClaudeMd" not in reviewer, "the host's CLAUDE.md describes the code under review"
        assert {"Read", "Grep", "Glob", "mcp__plugin_it-ops-kb_kb__kb_topics_for"} <= {t.strip() for t in reviewer["tools"].split(",")}
        with open(os.path.join(KB, ".claude/skills/kb-lookup/SKILL.md"), encoding="utf-8") as f:
            assert not re.search(r"(?m)^effort:", f.read().split("\n---", 1)[0]), "effort in a skill overrides the host session's"
        for d in ("commands", "output-styles", "workflows", "themes", "monitors", "hooks", "bin"):
            assert not os.path.exists(os.path.join(KB, d)), f"{d}/ at the root would load as a plugin component"

    def test_kb_worker_agent(self):
        """kb-worker, the sprint item worker, runs on the sonnet alias (the newest Sonnet) at high effort and stays
        out of the plugin: a clone-only agent."""
        with open(os.path.join(KB, KB_WORKER), encoding="utf-8") as f:
            text = f.read()
        assert kb_worker_problems(text, self.plugin["agents"]) == []
        body = text.split("\n---", 1)[1]
        for phrase in ("touches", "work/<id>", "KB-Work", "Never push", "new bug", "gate"):
            assert phrase in body, f"the worker brief names {phrase!r}"
        # The sync gate's own checks run in the worktree before each commit, not first at the orchestrator's gate.
        for phrase in ("kbgit.py fix --check", 'tests.py -k "ruff or tools_map"'):
            assert phrase in body, f"the worker brief runs {phrase!r} before a commit"

    def test_kb_worker_rule_4_worker_ruff_for_any_python(self):
        """Rule 4 has a worker run the ruff and tools_map tests for any Python file the sync gate's ruff check covers,
        `.claude/**/*.py` as well as `_tools/`, not only when its touches include `_tools/`."""
        with open(os.path.join(KB, KB_WORKER), encoding="utf-8") as f:
            text = f.read()
        assert kb_worker_ruff_problems(text) == []
        for old, new in (("`.claude/**/*.py`", "`_tools/`"), ("any Python file", "`_tools/`"),
                         ('tests.py -k "ruff or tools_map"', "tests.py")):
            planted = text.replace(old, new)
            assert planted != text, f"plant does not apply: {old!r}"
            assert kb_worker_ruff_problems(planted), f"not caught: {old!r} -> {new!r}"

    def test_kb_worker_agent_planted_failures(self):
        """Each rule fails on a planted copy: a pinned id, inherit, no model, another effort, a plugin listing."""
        with open(os.path.join(KB, KB_WORKER), encoding="utf-8") as f:
            text = f.read()
        agents = self.plugin["agents"]
        for old, new in (("model: sonnet", "model: claude-sonnet-5"), ("model: sonnet", "model: inherit"),
                         ("model: sonnet\n", ""), ("effort: high", "effort: medium"), ("name: kb-worker", "name: worker")):
            planted = text.replace(old, new, 1)
            assert planted != text, old
            assert kb_worker_problems(planted, agents), f"not caught: {old!r} -> {new!r}"
        assert kb_worker_problems(text, agents + ["./" + KB_WORKER]), "not caught: kb-worker listed in plugin.json"

    @staticmethod
    def dispatch_texts():
        texts = []
        for rel in (KB_SPRINT, KB_CENSUS, RUNBOOK):
            with open(os.path.join(KB, rel), encoding="utf-8") as f:
                texts.append(f.read())
        return texts

    def test_kb_worker_dispatch(self):
        """/kb-sprint run starts each task or subtask on kb-worker with no model override; S1 and S2 bugs and a
        story or bug with no tasks go to the session model; the review, /kb-census and the runbook agree."""
        assert kb_worker_dispatch_problems(*self.dispatch_texts()) == []

    def test_kb_worker_dispatch_planted_failures(self):
        """Each rule fails on a planted copy of the skill, the census skill or the runbook."""
        sprint, census, runbook = self.dispatch_texts()
        plants = [
            (0, '- a task or subtask: `subagent_type: "kb-worker"`', '- a task or subtask: `subagent_type: "general-purpose"`'),
            (0, "Never pass the Agent tool's `model`", "Pass the Agent tool's `model: sonnet`"),
            (0, "an `S1` or `S2` bug and its tasks", "an `S1` bug and its tasks"),
            (0, "a story or bug with no tasks yet (its breakdown): a subagent on the session model",
             "a story or bug with no tasks yet (its breakdown): `kb-worker`"),
            (0, 'reviewer subagent on the session model (`subagent_type: "general-purpose"`',
             'reviewer subagent on `kb-worker` (`subagent_type: "kb-worker"`'),
            (1, "## Phase", "Start phase 2 readers on `kb-worker`.\n\n## Phase"),
            (2, "started with no `model`", "started with a `model`"),
            (2, "The sprint review and every `/kb-census` subagent never use `kb-worker`.", ""),
        ]
        for i, old, new in plants:
            texts = [sprint, census, runbook]
            texts[i] = texts[i].replace(old, new, 1)
            assert texts[i] != [sprint, census, runbook][i], f"plant does not apply: {old!r}"
            assert kb_worker_dispatch_problems(*texts), f"not caught: {old!r} -> {new!r}"

    def test_kb_worker_fallback(self):
        """Agent files load at session start: when the Agent tool does not list kb-worker, /kb-sprint run and the
        runbook start the task on general-purpose with model sonnet, briefed with .claude/agents/kb-worker.md."""
        sprint, _, runbook = self.dispatch_texts()
        assert kb_worker_fallback_problems(sprint, runbook) == []

    def test_kb_worker_fallback_planted_failures(self):
        """Each rule fails on a planted copy of the skill or the runbook."""
        sprint, _, runbook = self.dispatch_texts()
        plants = [
            (0, "does not list `kb-worker`", "lists no workers"),
            (0, '`model: "sonnet"`', "the session model"),
            (0, "points the worker at `.claude/agents/kb-worker.md`", "briefs the worker"),
            (0, "The one exception, a fallback", "A fallback"),
            (1, "does not list `kb-worker`", "lists no workers"),
            (1, "`general-purpose` with `model: sonnet`", "`general-purpose`"),
            (1, "points the worker at `.claude/agents/kb-worker.md`", "briefs the worker"),
            (1, "at session start", "late"),
        ]
        for i, old, new in plants:
            texts = [sprint, runbook]
            texts[i] = texts[i].replace(old, new, 1)
            assert texts[i] != [sprint, runbook][i], f"plant does not apply: {old!r}"
            assert kb_worker_fallback_problems(*texts), f"not caught: {old!r} -> {new!r}"

    @staticmethod
    def load_texts():
        texts = []
        for rel in (KB_WORKER, KB_SPRINT, RUNBOOK):
            with open(os.path.join(KB, rel), encoding="utf-8") as f:
                texts.append(f.read())
        return texts

    def test_kb_worker_load(self):
        """Up to four workers share the host: each runs its item's checks and the fast tests (no stress_test.py, no
        second full run), the orchestrator runs stress_test.py once per landing that changed _tools/, and each brief
        names the in-flight sibling items and the files they change."""
        assert kb_worker_load_problems(*self.load_texts()) == []

    def test_kb_worker_load_planted_failures(self):
        """Each rule fails on a planted copy of the agent, the skill or the runbook."""
        worker, sprint, runbook = self.load_texts()
        plants = [
            (0, "then the fast tests, `python3 _tools/tests.py --changed origin/main`", "then `python3 _tools/tests.py`"),
            (0, "Never run `python3 _tools/stress_test.py` or the full", "Also run `python3 _tools/stress_test.py` and the full"),
            (0, "and never a second run", "and a second run"),
            (0, "Your brief names the sibling items in flight", "Your brief names the items in flight"),
            (1, "the in-flight sibling items (id and title)", "the items"),
            (1, "; never `python3 _tools/stress_test.py` or the full `tests.py`", ", then `python3 _tools/stress_test.py`"),
            (1, "`python3 _tools/stress_test.py` once, when the landing changed `_tools/`", "the full tests"),
            (2, "never `stress_test.py` or the full `tests.py`", "then `stress_test.py`"),
            (2, "The orchestrator runs `python3 _tools/stress_test.py` once per landing", "The orchestrator runs it"),
        ]
        for i, old, new in plants:
            texts = [worker, sprint, runbook]
            texts[i] = texts[i].replace(old, new, 1)
            assert texts[i] != [worker, sprint, runbook][i], f"plant does not apply: {old!r}"
            assert kb_worker_load_problems(*texts), f"not caught: {old!r} -> {new!r}"

    def test_shipped_texts_mark_rag_py_as_clone_only(self):
        """A host has no _tools/rag.py on its path: the server's texts and the agents never name it, and the skills
        name it only as the clone form of a kb tool (in brackets, after saying so)."""
        sys.path.insert(0, TOOLS)
        import kb_mcp
        for text in [kb_mcp.INSTRUCTIONS] + [t["description"] for t in kb_mcp.TOOL_LIST + kb_mcp.LIVE_TOOL_LIST]:
            assert "rag.py" not in text
        for rel in (".claude/agents/kb-lookup.md", ".claude/agents/kb-reviewer.md", ".claude/skills/kb-review-workspace/SKILL.md",
                    ".claude/skills/kb-gap/SKILL.md"):
            with open(os.path.join(KB, rel), encoding="utf-8") as f:
                assert "rag.py" not in f.read(), rel
        with open(os.path.join(KB, ".claude/skills/kb-lookup/SKILL.md"), encoding="utf-8") as f:
            body = f.read().split("\n---", 1)[1]
        first = body.index("rag.py")
        assert "in a clone" in body[:first].lower(), "the skill says rag.py is the clone form before using it"
        for line in body.splitlines():
            for m in re.finditer(r"rag\.py", line):
                assert line.count("(", 0, m.start()) > line.count(")", 0, m.start()) or "in a clone" in line.lower(), \
                                f"rag.py outside brackets: {line}"

    def test_kb_server_from_the_plugin_root(self):
        kb = self.plugin["mcpServers"]["kb"]
        assert kb["command"] == "python3"
        assert kb["args"] == ["${CLAUDE_PLUGIN_ROOT}/_tools/kb_mcp.py"]

    def test_submit_feedback_blocked_on_every_docs_server(self):
        hooks = self.docs["hooks"]["PreToolUse"]
        assert len(hooks) == 1
        rx = re.compile(hooks[0]["matcher"])
        for s in self.servers:
            assert rx.fullmatch(f"mcp__plugin_{self.docs['name']}_{s}__submit_feedback"), s
        assert not rx.fullmatch(f"mcp__plugin_{self.docs['name']}_microsoft-learn__microsoft_docs_search")
        h = hooks[0]["hooks"][0]
        # shell form with no interpreter to find (the docs plugin has no _tools/kbpy) and no `shell` field, so the
        # host's default shell runs it: sh, Git Bash, or PowerShell on Windows without Git Bash
        assert h["type"] == "command" and "args" not in h and "shell" not in h and "python" not in h["command"]
        if not HOOK_SHELLS:
            pytest.skip("no sh and no PowerShell on PATH")
        assert block_offenders(h["command"]) == []
        # planted: the old command, whose `>&2` is a parser error in PowerShell (exit 1, a non-blocking hook error)
        old = "echo 'blocked by the it-ops-kb-docs plugin: submit_feedback posts text to the docs vendor' >&2; exit 2"
        ps = [n for n, _ in HOOK_SHELLS if n in ("pwsh", "powershell")]
        assert [b.split(":")[0] for b in block_offenders(old)] == ps
        assert "PreToolUse" not in self.plugin["hooks"], "the kb plugin has no docs servers to guard"

    def test_hook_shells_leave_out_the_wsl_launcher(self, tmp_path, monkeypatch):
        # System32\bash.exe and the WindowsApps alias start WSL, which exits 1 with no distribution installed: no hook
        # runs in either
        windir, local = tmp_path / "Windows", tmp_path / "AppData" / "Local"
        monkeypatch.setenv("SystemRoot", str(windir))
        monkeypatch.setenv("LOCALAPPDATA", str(local))
        git_sh = str(tmp_path / "Git" / "usr" / "bin" / "sh.exe")
        ps = str(windir / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe")
        for bash in (windir / "System32" / "bash.exe", local / "Microsoft" / "WindowsApps" / "bash.exe"):
            found = {"sh": git_sh, "bash": str(bash), "powershell": ps}
            got = hook_shells(found.get, starts=lambda p: True)
            assert [(n, a[0]) for n, a in got] == [("sh", git_sh), ("powershell", ps)], bash
        assert not is_wsl_launcher(str(tmp_path / "Windows-not" / "bash.exe"))
        # on Windows a shell elsewhere that cannot run `exit 0` is left out too
        found = {"bash": str(tmp_path / "other" / "bash.exe")}
        assert [n for n, _ in hook_shells(found.get, starts=lambda p: False)] == ([] if os.name == "nt" else ["bash"])
        assert not any(is_wsl_launcher(a[0]) for n, a in HOOK_SHELLS if n in ("sh", "bash", "dash"))

    def test_kb_prompt_hook_from_the_plugin_root(self):
        hooks = self.plugin["hooks"]["UserPromptSubmit"]
        assert len(hooks) == 1
        h = hooks[0]["hooks"][0]
        assert (h["type"], h["command"]) == ("command", 'sh "${CLAUDE_PLUGIN_ROOT}/_tools/kbpy" _tools/kb_hook.py')
        assert "args" not in h, "exec form needs a real .exe on Windows: the launcher runs in shell form"

    @pytest.mark.skipif(not shutil.which("claude"), reason="the claude CLI is not installed")
    def test_claude_plugin_validate(self):
        for target in (KB, os.path.join(KB, DOCS_PLUGIN)):
            p = subprocess.run(["claude", "plugin", "validate", target], capture_output=True, text=True, encoding="utf-8", timeout=120)
            assert p.returncode == 0, p.stdout + p.stderr
            assert "Validation passed" in p.stdout + p.stderr
            warnings = [ln for ln in (p.stdout + p.stderr).splitlines() if ln.strip().startswith(">") or ln.strip().startswith("\u276f")]
            assert all("No version specified" in w for w in warnings), "\n".join(warnings)


@pytest.fixture
def short_tmp():
    """A temporary directory with a short path: a plugin copy under pytest's tmp_path (which holds the user name
    and the test name) passes 260 characters on Windows without long paths, and copytree fails."""
    d = tempfile.mkdtemp(prefix="kbs")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


def test_status_of_a_plugin_copy_from_a_directory_marketplace(short_tmp):
    """A plugin installed from a local directory marketplace has no clone under plugins/marketplaces/: kb_status
    reports its version (the commit) as the commit instead of calling the copy unknown."""
    from conftest import copy_kb
    sha = "929d59973c2b"
    home = copy_kb(str(short_tmp / "plugins" / "cache" / "it-ops-kb" / "it-ops-kb" / sha))
    env = {k: v for k, v in os.environ.items() if k not in ("KB_ROOTS", "KB_INDEX", "CLAUDE_PLUGIN_DATA")}
    p = subprocess.run([sys.executable, os.path.join(home, "_tools", "kb_mcp.py"), "--status"], capture_output=True,
                       text=True, encoding="utf-8", timeout=120, env=env, cwd=str(short_tmp))
    assert p.returncode == 0, p.stdout + p.stderr
    assert f"installed_as: plugin it-ops-kb@it-ops-kb, version {sha}" in p.stdout, p.stdout
    assert f"commit: {sha}\n" in p.stdout, p.stdout


def _status(home, cwd):
    env = {k: v for k, v in git_env().items() if k not in ("KB_ROOTS", "KB_INDEX", "CLAUDE_PLUGIN_DATA")}
    p = subprocess.run([sys.executable, os.path.join(home, "_tools", "kb_mcp.py"), "--status"], capture_output=True,
                       text=True, encoding="utf-8", timeout=timeout_s(120), env=env, cwd=str(cwd))
    assert p.returncode == 0, p.stdout + p.stderr
    return p.stdout


def _ahead(repo, n):
    """Commit n empty commits on top of HEAD without moving it; return the new tip."""
    tip, tree = repo.rev("HEAD"), repo.rev("HEAD^{tree}")
    for i in range(n):
        tip = repo.git("commit-tree", tree, "-p", tip, "-m", f"upstream {i}").strip()
    return tip


@pytest.mark.git
def test_status_says_how_far_a_clone_is_behind_its_remote(tmp_path):
    """A clone whose origin/main holds newer commits (as of its last fetch) says how many and how to update, from
    local refs only; one level with its remote says 0."""
    from conftest import Repo, copy_kb
    repo = Repo(copy_kb(str(tmp_path / "kb")))
    repo.git("init", "-q", "-b", "main")
    repo.git("add", "README.md")
    repo.git("commit", "-q", "-m", "kb")
    repo.git("update-ref", "refs/remotes/origin/main", repo.rev("HEAD"))
    out = _status(repo.path, tmp_path)
    assert "upstream: origin/main" in out and "behind_upstream: 0 commits\n" in out and "update:" not in out, out
    repo.git("update-ref", "refs/remotes/origin/main", _ahead(repo, 3))
    out = _status(repo.path, tmp_path)
    assert "behind_upstream: 3 commits\n" in out, out
    assert f"update: git -C {repo.path} pull --ff-only" in out, out
    code = "import kb_mcp; print(kb_mcp.kb_pack({'question': 'default Windows LAPS password length'}))"
    p = subprocess.run([sys.executable, "-c", code], cwd=os.path.join(repo.path, "_tools"), capture_output=True, text=True, encoding="utf-8",
                       timeout=300, env=follow_upstream(git_env(KB_INDEX=str(tmp_path / "index"))))
    assert p.stdout.startswith("kb copy: 3 commits behind origin/main"), p.stdout[:300] + p.stderr[-500:]
    assert f"to update: git -C {repo.path} pull --ff-only.\n\ncoverage: good" in p.stdout, p.stdout[:300]


@pytest.mark.git
def test_status_follows_the_integration_remote_not_origin(tmp_path):
    """A clone with no upstream branch whose integration remote is `integ` (kb.integrationRemote) measures its
    distance against integ/main, even when an origin/main level with HEAD exists; with no remote branch of the
    integration remote it reports none, and integ/HEAD is preferred over integ/main."""
    from conftest import Repo, copy_kb
    repo = Repo(copy_kb(str(tmp_path / "kb")))
    repo.git("init", "-q", "-b", "main")
    repo.git("add", "README.md")
    repo.git("commit", "-q", "-m", "kb")
    repo.git("config", "kb.integrationRemote", "integ")
    repo.git("update-ref", "refs/remotes/origin/main", repo.rev("HEAD"))  # a decoy, level with HEAD
    assert "upstream:" not in _status(repo.path, tmp_path)
    repo.git("update-ref", "refs/remotes/integ/main", _ahead(repo, 3))
    out = _status(repo.path, tmp_path)
    assert "upstream: integ/main" in out and "behind_upstream: 3 commits\n" in out and "origin" not in out, out
    repo.git("update-ref", "refs/remotes/integ/other", _ahead(repo, 1))
    repo.git("symbolic-ref", "refs/remotes/integ/HEAD", "refs/remotes/integ/other")
    out = _status(repo.path, tmp_path)
    assert "upstream: integ/HEAD" in out and "behind_upstream: 1 commits\n" in out, out


def _behind_clone(tmp_path, n=3):
    """A kb copy committed as a clone whose origin/main is n commits ahead of its HEAD (as of its last fetch)."""
    from conftest import Repo, copy_kb
    repo = Repo(copy_kb(str(tmp_path / "kb")))
    repo.git("init", "-q", "-b", "main")
    repo.git("add", "README.md")
    repo.git("commit", "-q", "-m", "kb")
    repo.git("update-ref", "refs/remotes/origin/main", _ahead(repo, n))
    return repo


def _pack_and_status(repo, tmp_path, roots=None):
    """(kb_pack text, kb_status text) from the clone's kb_mcp, limited to `roots` (as --roots does) when given."""
    code = ("import kb_mcp, kbcommon\n"
            f"if {roots!r}: kbcommon.serve_only({roots!r})\n"
            "print(kb_mcp.kb_pack({'question': 'default Windows LAPS password length'}))\n"
            "print('=====')\n"
            "print(kb_mcp.kb_status({}))")
    p = subprocess.run([sys.executable, "-c", code], cwd=os.path.join(repo.path, "_tools"), capture_output=True,
                       text=True, encoding="utf-8", timeout=300, env=follow_upstream(git_env(KB_INDEX="0")))
    assert p.returncode == 0, p.stderr[-1000:]
    pack, _, status = p.stdout.partition("=====\n")
    return pack, status


@pytest.mark.git
def test_kb_mcp_pack_ignores_freshness_banner(tmp_path):
    """Planted failure: a clone 3 commits behind its origin/main (a worktree while main moves on). Its server started
    as the pack tests start it (quiet_upstream) opens kb_pack with `coverage:`, one verdict per question; started
    without it, the same packs open with the kb copy line that the pack tests' assertions would trip on."""
    repo = _behind_clone(tmp_path)
    calls = [{"question": "What is the default Windows LAPS password length?"},
             {"questions": ["Does deleting an Entra device delete its BitLocker keys?",
                            "When is NTLMv1 disabled by default?"]}]
    msgs = [{"jsonrpc": "2.0", "id": 0, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}}]
    msgs += [{"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": "kb_pack", "arguments": a}}
             for i, a in enumerate(calls, start=1)]

    def packs(env):
        p = subprocess.run([sys.executable, os.path.join(repo.path, "_tools", "kb_mcp.py")],
                           input="".join(json.dumps(m) + "\n" for m in msgs), capture_output=True, text=True,
                           encoding="utf-8", timeout=300, env=env, cwd=os.sep)
        assert p.returncode == 0, p.stderr[-1000:]
        by_id = {r.get("id"): r for r in map(json.loads, p.stdout.splitlines())}
        return [by_id[i]["result"]["content"][0]["text"] for i in range(1, len(calls) + 1)]

    env = git_env(KB_INDEX="0")
    for text in packs(follow_upstream(env)):
        assert text.startswith("kb copy: 3 commits behind origin/main"), text[:300]
    single, batch = packs(quiet_upstream(env))
    assert single.startswith("coverage: ") and "kb copy:" not in single, single[:300]
    assert batch.startswith("# Q1: ") and "kb copy:" not in batch, batch[:300]
    assert len(re.findall(r"(?m)^coverage: ", batch)) == 2, batch[:600]


@pytest.mark.git
def test_status_names_no_local_path_when_limited_by_roots(tmp_path):
    """Planted failure both ways: one clone behind its remote. Unlimited (the plugin, the team's own clone) the
    kb copy line and kb_status name the clone's path and the pull command; limited by --roots (a server for clients
    outside the team) they keep the staleness and name neither."""
    repo = _behind_clone(tmp_path)
    pack, status = _pack_and_status(repo, tmp_path)
    assert pack.startswith("kb copy: 3 commits behind origin/main"), pack[:300]
    assert f"to update: git -C {repo.path} pull --ff-only." in pack, pack[:300]
    assert f"update: git -C {repo.path} pull --ff-only" in status and "kb_dir: " in status, status
    pack, status = _pack_and_status(repo, tmp_path, roots=["public"])
    assert pack.startswith("kb copy: 3 commits behind the kb it follows; newer facts may exist. Tell the user.\n"), \
        pack[:300]
    assert "behind_upstream: 3 commits\n" in status and "roots: public (prefix S" in status, status
    for text in (pack, status):
        assert repo.path not in text and os.path.realpath(repo.path) not in text, text[:600]
        assert "git -C" not in text and "update:" not in text and "kb_dir:" not in text, text[:600]


@pytest.mark.git
def test_status_tells_a_clone_at_a_census_tag_to_check_out_the_newest(tmp_path):
    """A clone detached at a census tag (a host pinned to a confirmed kb) cannot pull: it is told to check out the
    newest census tag it has, or to fetch tags when it is at the newest; on a branch it is told to pull."""
    repo = _behind_clone(tmp_path)
    repo.git("tag", "census-2026-01-01")
    repo.git("checkout", "-q", "--detach", "census-2026-01-01")
    out = _status(repo.path, tmp_path)
    assert f"update: git -C {repo.path} fetch --tags, then check out the newest census-* tag (" in out, out
    repo.git("tag", "census-2026-02-01", "refs/remotes/origin/main~1")
    out = _status(repo.path, tmp_path)
    assert f"update: git -C {repo.path} checkout census-2026-02-01 (" in out and "pull" not in out, out
    repo.git("checkout", "-q", "main")
    assert f"update: git -C {repo.path} pull --ff-only (" in _status(repo.path, tmp_path)


@pytest.mark.git
def test_status_says_how_far_an_installed_plugin_is_behind_its_marketplace(short_tmp):
    """An installed plugin copy (no .git) is compared with the marketplace clone Claude Code keeps beside the cache:
    commits there after the copy's version mean the copy is older than the kb it follows."""
    from conftest import Repo, copy_kb
    plugins = short_tmp / "plugins"
    mkt = Repo(plugins / "marketplaces" / "it-ops-kb")
    os.makedirs(mkt.path)
    mkt.git("init", "-q", "-b", "main")
    mkt.git("commit", "-q", "--allow-empty", "-m", "version")
    sha = mkt.rev("HEAD")[:12]
    mkt.git("reset", "-q", "--hard", _ahead(mkt, 2))
    home = copy_kb(str(plugins / "cache" / "it-ops-kb" / "it-ops-kb" / sha))
    out = _status(home, short_tmp)
    assert f"commit: {sha}\n" in out and "behind_upstream: 2 commits\n" in out, out
    assert "update: /plugin marketplace update, then /reload-plugins" in out, out


def test_domain_is_matched_without_case_and_an_unknown_one_is_refused():
    """A model passed domain "Intune" and got `coverage: none` for a question the kb covers: a domain is matched
    against the kb's paths without regard to case, and one no path is under is an error listing the domains."""
    code = ("import json, kb_mcp\n"
            "out = {'pack': kb_mcp.kb_pack({'question': 'Can the Mark device noncompliant action be removed?', "
            "'domain': 'Intune'})}\n"
            "out['search'] = kb_mcp.kb_search({'query': 'noncompliance actions', 'domain': '/Public/Intune/'})\n"
            "for d in ('no-such-domain', 'Public/NoSuch'):\n"
            "    try:\n"
            "        kb_mcp.kb_pack({'question': 'x', 'domain': d}); out[d] = 'accepted'\n"
            "    except kb_mcp.ToolError as e:\n"
            "        out[d] = str(e)\n"
            "print(json.dumps(out))")
    env = quiet_upstream({k: v for k, v in os.environ.items() if k not in ("KB_ROOTS", "CLAUDE_PLUGIN_DATA")})
    p = subprocess.run([sys.executable, "-c", code], cwd=TOOLS, capture_output=True, text=True, encoding="utf-8", env=env, timeout=180)
    out = json.loads(p.stdout.strip().splitlines()[-1])
    assert out["pack"].startswith("coverage: good") and "public/intune/" in out["pack"], out["pack"][:300]
    assert "public/intune/" in out["search"], out["search"][:300]
    for d in ("no-such-domain", "Public/NoSuch"):
        assert out[d].startswith(f"no domain {d!r}") and "intune" in out[d], out[d]
    p = subprocess.run([sys.executable, os.path.join(TOOLS, "rag.py"), "pack", "noncompliance actions", "-d", "nosuch"],
                       capture_output=True, text=True, encoding="utf-8", env=env, timeout=180)
    assert p.returncode == 1 and "no domain 'nosuch'" in p.stderr and "coverage:" not in p.stdout, p.stdout + p.stderr


def _embedded(roots_dir, *args, calls=()):
    """kb_mcp.py started as a host embeds it: KB_ROOTS names a team's root directory, `args` the flags (--roots);
    `calls` are (tool, arguments) sent after the handshake. Returns the process and {id: (isError, text)}."""
    env = quiet_upstream({k: v for k, v in os.environ.items() if k not in ("KB_ROOTS", "KB_INDEX", "CLAUDE_PLUGIN_DATA")})
    env.update({"KB_ROOTS": roots_dir, "KB_INDEX": "0"})
    msgs = [{"jsonrpc": "2.0", "id": 0, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "host", "version": "0"}}}]
    msgs += [{"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": n, "arguments": a}}
             for i, (n, a) in enumerate(calls, start=1)]
    p = subprocess.run([sys.executable, SERVER, *args], input="".join(json.dumps(m) + "\n" for m in msgs),
                       capture_output=True, text=True, encoding="utf-8", timeout=timeout_s(180), env=env, cwd=os.sep)
    out = {}
    for ln in p.stdout.splitlines():
        r = json.loads(ln)
        if r.get("id") and "result" in r:
            out[r["id"]] = (r["result"]["isError"], r["result"]["content"][0]["text"])
    return p, out


def test_embed_roots_serves_only_the_named_root(tmp_path):
    """--roots fixture: every tool and kb_status see the team's root alone; the public root is not served."""
    from test_kb_root import QUESTION, SID, URL, make_root
    root = str(tmp_path / "team-kb")
    make_root(root)
    p, out = _embedded(root, "--roots", "fixture", calls=[
        ("kb_pack", {"question": QUESTION}),
        ("kb_pack", {"question": "What is the default Windows LAPS password length?"}),
        ("kb_search", {"query": "kerberos constrained delegation"}),
        ("kb_facts", {"prefix": "print"}),
        ("kb_audit", {"prefix": "intune"}),
        ("kb_show", {"path": Q("auth/kerberos.md") + ":1", "n": 1}),
        ("kb_source", {"ids": ["S100", SID]}),
        ("kb_status", {}),
        ("kb_pack", {"question": QUESTION, "root": "public"}),
        ("kb_topics_for", {"text": "new PublicClientApplication(c); the spooler service"}),
    ])
    assert p.returncode == 0, p.stderr
    assert "coverage: good" in out[1][1], out[1][1][:300]  # a word one unit holds counts (kbfacts.informative_words)
    assert "fixture/print/queues.md:" in out[1][1] and "public/" not in out[1][1], out[1]
    assert "coverage: none" in out[2][1] and "public/" not in out[2][1], out[2][1][:300]
    assert "public/" not in out[3][1], out[3][1][:300]
    assert "fixture/print/queues.md" in out[4][1] and "public/" not in out[4][1], out[4][1][:300]
    assert out[5][0] and "no article matches" in out[5][1], out[5]
    assert out[6][0] and "not a path inside the kb" in out[6][1], out[6]
    assert "S100  UNKNOWN id" in out[7][1] and f"{SID}  Print queue retention\n  url: {URL}" in out[7][1], out[7][1]
    status = out[8][1]
    assert "roots: fixture (prefix FXT, internal, " in status and "public (prefix" not in status, status
    assert "census_log: none" in status and "sources: 1 (0 superseded)" in status, status
    assert out[9][0] and "no root 'public'; roots: fixture" in out[9][1], out[9]
    assert "fixture/print/queues" in out[10][1] and "public/" not in out[10][1], out[10][1]


def test_decision_lookup_mcp_pack_show_and_audit(tmp_path):
    """kb_pack prints the decisions beside the facts (decided, proposed; `include_invalidated: true` adds the invalidated
    with why; only the boolean true does), an active decision that answers lifts the coverage, kb_show lists the
    decisions of the lines it shows, and kb_audit the active decisions that share a context. The two tools' schemas
    carry the argument."""
    from test_kb_lookup import (DECISION_CONTEXT, DECISION_PATTERN_QUESTION, DECISION_QUESTION, DECISION_TEXT,
                                decision_lookup_root, decision_lookup_rows)
    from test_kb_root import ARTICLE, SID, decision, did
    cited = f"- The nightly purge runs at 02:00 on the spooler. [DOC {SID}; DECISION {did(5)}]\n"
    rows = decision_lookup_rows() + [
        decision(5, text="Retention is the team's choice.", context="item:TK-abcd2345"),
        decision(6, text="Print owner is named by the team.", context=DECISION_CONTEXT)]
    root = decision_lookup_root(tmp_path, rows, cited)
    first = next(n for n, ln in enumerate((ARTICLE + cited).splitlines(), start=1) if "nightly purge runs" in ln)
    p, out = _embedded(root, "--roots", "fixture", calls=[
        ("kb_pack", {"question": DECISION_QUESTION}),
        ("kb_pack", {"question": DECISION_PATTERN_QUESTION}),
        ("kb_pack", {"question": DECISION_PATTERN_QUESTION, "include_invalidated": True}),
        ("kb_pack", {"question": DECISION_PATTERN_QUESTION, "include_invalidated": "yes"}),
        ("kb_show", {"path": f"fixture/print/queues.md:{first}", "n": 1}),
        ("kb_show", {"path": "fixture/print/queues.md:16", "n": 1, "include_invalidated": True}),
        ("kb_audit", {"prefix": "fixture"}),
        ("kb_pack", {"questions": [DECISION_QUESTION, DECISION_PATTERN_QUESTION], "include_invalidated": True}),
    ])
    assert p.returncode == 0, p.stderr
    answered, proposed, with_invalid, string_flag, shown, plain_show, audit, batch = (out[i][1] for i in range(1, 9))
    assert answered.startswith("coverage: good (an active decision answers it") and (
        f"decided by operator on 2026-10-01: {DECISION_TEXT} [DECISION {did(0)}]") in answered, answered
    assert f"proposed (not confirmed): Print queue names move to the pattern PQ-site-floor-room. [DECISION {did(1)}]" in proposed, proposed
    assert "invalidated because" not in proposed and did(2) not in proposed and did(3) not in proposed, proposed
    assert f"invalidated because article:print/queues is gone: Finished print jobs stay for 30 days. [DECISION {did(2)}]" in with_invalid, with_invalid
    assert did(3) not in with_invalid, "a superseded decision is never shown"
    assert "invalidated because" not in string_flag, "only the boolean true adds the invalidated decisions"
    assert "\ndecisions:\n" in shown and f"- fixture/_decisions.csv:6 decided by operator on 2026-10-01: Retention is the team's choice. [DECISION {did(5)}]" in shown, shown
    assert f"[DECISION {did(0)}]" in shown and "invalidated because" not in shown, "the article's decisions come with its lines: " + shown
    assert "\ndecisions:\n" in plain_show and did(5) not in plain_show.split("decisions:")[1], plain_show  # not cited on line 16
    assert f"invalidated because article:print/queues is gone: Finished print jobs stay for 30 days. [DECISION {did(2)}]" in plain_show \
        and did(3) not in plain_show, plain_show
    assert "possible contradiction: 2 active decisions share article:fixture/print/queues" in audit and did(0) in audit and did(6) in audit, audit
    assert did(1) not in audit.split("possible contradiction")[1], audit
    assert "# Q1:" in batch and "invalidated because" in batch, batch
    tools = {t["name"]: t for t in kb_mcp.TOOL_LIST}
    for name in ("kb_pack", "kb_show"):
        prop = tools[name]["inputSchema"]["properties"]["include_invalidated"]
        assert prop["type"] == "boolean" and prop["default"] is False, (name, prop)
    assert "include_invalidated" not in tools["kb_audit"]["inputSchema"]["properties"]
    # planted: with no decision file the same calls print no decision section and no contradiction
    from test_kb_lookup import decision_lookup_set
    decision_lookup_set(root, None)
    p, out = _embedded(root, "--roots", "fixture", calls=[("kb_pack", {"question": DECISION_QUESTION}),
                                                          ("kb_audit", {"prefix": "fixture"})])
    assert "## decisions" not in out[1][1] and out[1][1].startswith("coverage: none"), out[1][1]
    assert "possible contradiction" not in out[2][1], out[2][1]


def test_lookup_shows_log_lines_mcp(tmp_path):
    """kb_pack, kb_show and kb_audit print the active LOG rows of the matched article under `observed signal (LOG, not a
    fact):` with the dates they cover; a proposed, an invalidated and an unrelated row never print, and the pack's coverage
    line and facts are those of the same call with no `_logs.csv`."""
    from test_kb_lookup import (LOG_BLOCK, LOG_QUESTION, decision_lookup_root, log_lookup_ids, log_lookup_rows, log_lookup_set,
                                log_lookup_split)
    root = decision_lookup_root(tmp_path)
    calls = [("kb_pack", {"question": LOG_QUESTION}), ("kb_show", {"path": "fixture/print/queues.md:1", "n": 40}),
             ("kb_audit", {"prefix": "fixture"}), ("kb_pack", {"questions": [LOG_QUESTION, "What is the queue name pattern?"]})]
    p, bare = _embedded(root, "--roots", "fixture", calls=calls)
    assert p.returncode == 0 and not any(LOG_BLOCK in bare[i][1] for i in bare), (p.stderr, bare)
    log_lookup_set(root, log_lookup_rows())
    p, out = _embedded(root, "--roots", "fixture", calls=calls)
    assert p.returncode == 0, p.stderr
    for i in (1, 2, 3):
        rest, block = log_lookup_split(out[i][1])
        assert len(block) == 2 and f"[LOG {log_lookup_ids(0)}]" in block[0] and f"[LOG {log_lookup_ids(1)}]" in block[1], out[i][1]
        assert "observed 2026-09-21 to 2026-09-30:" in block[0], block
        assert all(log_lookup_ids(n) not in out[i][1] for n in (2, 3, 4, 5)), out[i][1]
        assert rest == bare[i][1], (i, "only the block is added")
    assert out[1][1].splitlines()[0] == bare[1][1].splitlines()[0] and out[1][1].startswith("coverage: good"), out[1][1]
    batch = out[4][1]  # a part of a multi-part pack carries its own block, and the parts' verdict lines are the plain ones
    assert batch.count(LOG_BLOCK) == 2 and [ln for ln in batch.splitlines() if ln.startswith("coverage:")] \
        == [ln for ln in bare[4][1].splitlines() if ln.startswith("coverage:")], batch


MSAL_TOPIC = "public/auth/msal-public-client"


def imports_arg_code(tmp_path):
    """A directory with one file that declares msal and one whose comment only mentions PublicClientApplication."""
    (tmp_path / "app.py").write_text("import msal\n", encoding="utf-8", newline="\n")
    (tmp_path / "note.py").write_text("# PublicClientApplication is mentioned here, never imported\nprint(1)\n",
                                      encoding="utf-8", newline="\n")
    return str(tmp_path)


def imports_arg_problems(default, by_imports):
    """What the imports argument must change between the default answer and the one with imports: [] when it does."""
    problems = []
    if "by their imports" in default or "PublicClientApplication" not in default:
        problems.append("the default answer is not the lexical one")
    if "by their imports (1 found)" not in by_imports:
        problems.append("the answer with imports is not in imports mode")
    if f"- {MSAL_TOPIC}  imports: msal (" not in by_imports:
        problems.append("the declared package msal did not find its topic")
    if "PublicClientApplication" in by_imports:
        problems.append("a name in a comment matched under imports")
    return problems


def test_decision_tag_is_a_kb_facts_filter(monkeypatch):
    """kb_facts's tag enum lists every kind kbfacts parses, DECISION included, and a `tags: [DECISION]` call keeps
    only the facts that cite a decision (planted: a DOC filter leaves that fact out)."""
    import kbfacts
    enum = next(t for t in kb_mcp.TOOL_LIST if t["name"] == "kb_facts")["inputSchema"]["properties"]["tags"]["items"]["enum"]
    assert "DECISION" in enum and enum == list(kbfacts.EVIDENCE_KINDS) and "LOG" not in enum
    article = ("- Finished jobs are kept 14 days. [DECISION D-k3f7q2zd]\n"
               "- The spooler purges nightly. [DOC S100]\n- Unconfirmed. [UNK]\n")
    monkeypatch.setattr(kbfacts, "units", lambda _scope: kbfacts.md_units("public/print/queues.md", article))
    got = kb_mcp.kb_facts({"prefix": "print", "tags": ["DECISION"], "response_format": "detailed"})
    assert "Finished jobs are kept 14 days" in got and "spooler purges" not in got and "Unconfirmed" not in got, got
    only_doc = kb_mcp.kb_facts({"prefix": "print", "tags": ["DOC"], "response_format": "detailed"})
    assert "Finished jobs are kept" not in only_doc and "spooler purges" in only_doc, only_doc


def test_kb_topics_for_imports_arg_reaches_imports_mode(tmp_path):
    schema = next(t for t in kb_mcp.TOOL_LIST if t["name"] == "kb_topics_for")["inputSchema"]
    assert schema["properties"]["imports"]["type"] == "boolean" and "imports" not in schema.get("required", [])
    code = imports_arg_code(tmp_path)
    default = kb_mcp.kb_topics_for({"paths": [code]})
    by_imports = kb_mcp.kb_topics_for({"paths": [code], "imports": True})
    assert not imports_arg_problems(default, by_imports), imports_arg_problems(default, by_imports)
    assert kb_mcp.kb_topics_for({"paths": [code], "imports": False}) == default, "false is the default mode"
    assert kb_mcp.kb_topics_for({"paths": [code], "imports": "true"}) == default, "only the boolean true switches"
    text = kb_mcp.kb_topics_for({"text": "import msal\n", "imports": True})
    assert f"- {MSAL_TOPIC}  imports: msal (text:1; msal)" in text, text


def test_kb_topics_for_imports_arg_planted_failure(tmp_path):
    """The checker fails when the argument is ignored, and when imports mode would read comments."""
    code = imports_arg_code(tmp_path)
    default = kb_mcp.kb_topics_for({"paths": [code]})
    assert imports_arg_problems(default, default), "an ignored argument must be caught"
    assert imports_arg_problems(default, default.replace("- ", "by their imports (1 found)\n- ")), "comment matches must be caught"


def test_kb_topics_for_imports_arg_rag_flag(tmp_path):
    code = imports_arg_code(tmp_path)
    run = lambda *a: subprocess.run([sys.executable, os.path.join(TOOLS, "rag.py"), "topics-for", code, *a], capture_output=True,
                                    text=True, encoding="utf-8", timeout=120, env=quiet_upstream()).stdout
    assert not imports_arg_problems(run(), run("--imports")), run("--imports")
    helped = subprocess.run([sys.executable, os.path.join(TOOLS, "rag.py"), "topics-for", "-h"], capture_output=True,
                            text=True, encoding="utf-8", timeout=120).stdout
    assert "--imports" in helped


def test_kb_topics_for_imports_arg_under_roots_takes_text(tmp_path):
    from test_kb_root import make_root
    root = str(tmp_path / "team-kb")
    make_root(root)
    p, out = _embedded(root, "--roots", "fixture,public", calls=[
        ("kb_topics_for", {"text": "import msal\n", "imports": True}),
        ("kb_topics_for", {"paths": [str(tmp_path)], "imports": True})])
    assert p.returncode == 0, p.stderr
    assert not out[1][0] and f"- {MSAL_TOPIC}  imports: msal (text:1; msal)" in out[1][1], out[1]
    assert out[2][0] and "paths is off" in out[2][1], out[2]


def test_embed_roots_names_several_roots_and_status_follows(tmp_path):
    """--roots public,fixture serves both; --roots public leaves the team's root out of the pack and kb_status."""
    from test_kb_root import QUESTION, make_root
    root = str(tmp_path / "team-kb")
    make_root(root)
    p, out = _embedded(root, "--roots=fixture,public", calls=[("kb_status", {})])
    assert p.returncode == 0, p.stderr
    assert "roots: public (prefix S, public, " in out[1][1] and "; fixture (prefix FXT, " in out[1][1], out[1][1]
    p, out = _embedded(root, "--roots", "public", calls=[("kb_pack", {"question": QUESTION}), ("kb_status", {})])
    assert p.returncode == 0, p.stderr
    assert "fixture/" not in out[1][1], out[1][1][:300]
    assert "roots: public (prefix S, public, " in out[2][1] and "fixture" not in out[2][1], out[2][1]
    assert "census_log: public/_census/" in out[2][1], out[2][1]


def test_embed_roots_default_serves_every_root(tmp_path):
    """Without --roots the server serves every root, as the plugin starts it."""
    from test_kb_root import QUESTION, make_root
    root = str(tmp_path / "team-kb")
    make_root(root)
    p, out = _embedded(root, calls=[("kb_status", {}), ("kb_pack", {"question": QUESTION})])
    assert p.returncode == 0, p.stderr
    assert "roots: public (prefix S, public, " in out[1][1] and "; fixture (prefix FXT, " in out[1][1], out[1][1]
    assert "fixture/print/queues.md:" in out[2][1], out[2][1][:300]


@pytest.mark.parametrize("args, message", [
    (["--roots", "fixture,no-such-root"], "no root 'no-such-root'; roots: public, fixture"),
    (["--roots=nosuch", "--status"], "no root 'nosuch'; roots: public, fixture"),
    (["--roots"], "--roots needs one or more root names"),
    (["--roots", " , "], "--roots needs one or more root names"),
])
def test_embed_roots_refuses_an_unknown_name(tmp_path, args, message):
    """Planted failure: a --roots name that is no root stops the start before the server answers anything, with
    the error on stderr (naming the roots there are) and nothing on stdout."""
    from test_kb_root import make_root
    root = str(tmp_path / "team-kb")
    make_root(root)
    p, out = _embedded(root, *args, calls=[("kb_status", {})])
    assert p.returncode == 2, (p.returncode, p.stdout, p.stderr)
    assert p.stdout == "" and not out, p.stdout
    assert message in p.stderr and "Traceback" not in p.stderr, p.stderr


CONTRACT = Path(TOOLS) / "fixtures" / "kb_mcp_contract.json"
EMBEDDED = ("kb_pack", "kb_search", "kb_show")  # the tools a host server re-exposes
REGENERATE = "uv run --frozen python _tools/test_kb_mcp.py --write-contract"
CONTRACT_CALLS = {"kb_pack": {"question": "What is the default Windows LAPS password length?"},
                  "kb_search": {"query": "kerberos constrained delegation", "k": 2},
                  "kb_show": {"path": "README.md:1", "n": 2}}


def live_contract():
    """kb_mcp.py spawned as a host server spawns it (a stdio child): initialize, tools/list and one tools/call of
    each embedded tool. Returns the contract as the fixture pins it (VERSION, a sha256 of the instructions, the
    embedded tools' names and input schemas) and {tool: result} of the calls."""
    env = quiet_upstream({k: v for k, v in os.environ.items() if k not in ("KB_ROOTS", "CLAUDE_PLUGIN_DATA")})
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "host", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}]
    msgs += [{"jsonrpc": "2.0", "id": 10 + i, "method": "tools/call", "params": {"name": n, "arguments": CONTRACT_CALLS[n]}}
             for i, n in enumerate(EMBEDDED)]
    p = subprocess.run([sys.executable, SERVER], input="".join(json.dumps(m) + "\n" for m in msgs), capture_output=True,
                       text=True, encoding="utf-8", timeout=300, env=env, cwd=os.sep)
    assert p.returncode == 0, p.stderr
    by_id = {r.get("id"): r for r in map(json.loads, p.stdout.splitlines())}
    init, tools = by_id[1]["result"], {t["name"]: t for t in by_id[2]["result"]["tools"]}
    contract = {"version": init["serverInfo"]["version"],
                "instructions_sha256": hashlib.sha256(init["instructions"].encode("utf-8")).hexdigest(),
                "tools": {n: {"name": n, "inputSchema": tools[n]["inputSchema"]} for n in EMBEDDED if n in tools}}
    return contract, {n: by_id[10 + i].get("result") for i, n in enumerate(EMBEDDED)}


def contract_mismatch(pinned, live):
    """None when the live contract may stand: it equals the pinned one, or VERSION moved (a bump with the fixture
    regenerated is the sanctioned way to change what a host re-exposes). Else what differs, and how to fix it."""
    if pinned == live or pinned.get("version") != live.get("version"):
        return None
    parts = [k for k in ("version", "instructions_sha256") if pinned.get(k) != live.get(k)]
    have, want = live.get("tools") or {}, pinned.get("tools") or {}
    parts += [f"tools.{n}" for n in sorted(set(have) | set(want)) if have.get(n) != want.get(n)]
    return (f"the tools a host server re-exposes changed at the same kb_mcp.VERSION {live.get('version')}: "
            f"{', '.join(parts)} differ from {CONTRACT.name}. A host embedding kb_mcp.py relies on them: bump "
            f"kb_mcp.VERSION and regenerate the fixture with `{REGENERATE}`, or undo the change.")


def write_contract():
    """Regenerate _tools/fixtures/kb_mcp_contract.json from the live server (run by hand after a VERSION bump)."""
    contract, _ = live_contract()
    CONTRACT.write_text(json.dumps(contract, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8",
                        newline="\n")
    print(f"wrote {CONTRACT} (kb_mcp {contract['version']})")


@pytest.fixture(scope="module")
def embed_live():
    return live_contract()


def test_embed_contract_matches_the_fixture(embed_live):
    """The names and input schemas of kb_pack, kb_search and kb_show and the instructions' digest are what the
    fixture pins, unless kb_mcp.VERSION moved."""
    pinned = json.loads(CONTRACT.read_text(encoding="utf-8"))
    live, _ = embed_live
    assert set(pinned) == {"version", "instructions_sha256", "tools"} and sorted(pinned["tools"]) == sorted(EMBEDDED), \
        f"{CONTRACT.name} pins {sorted(pinned)}; regenerate it with `{REGENERATE}`"
    assert contract_mismatch(pinned, live) is None, contract_mismatch(pinned, live)


def test_embed_contract_calls_answer_in_shape(embed_live):
    """One tools/call of each embedded tool answers with a text block and isError false; kb_pack's text has a
    coverage line. The text itself follows the kb's content and is not pinned."""
    _, calls = embed_live
    for name in EMBEDDED:
        r = calls[name]
        assert r is not None, f"{name}: no result"
        assert r["isError"] is False, (name, r)
        assert r["content"] and r["content"][0]["type"] == "text" and r["content"][0]["text"].strip(), (name, r)
    text = calls["kb_pack"]["content"][0]["text"]
    assert re.search(r"(?m)^coverage: (good|weak|none)\b", text), text[:300]


@pytest.mark.parametrize("change, part", [
    (lambda c: c["tools"]["kb_search"]["inputSchema"]["properties"]["k"].update(maximum=50), "tools.kb_search"),
    (lambda c: c["tools"]["kb_pack"]["inputSchema"].update(required=["question"]), "tools.kb_pack"),
    (lambda c: c["tools"].pop("kb_show"), "tools.kb_show"),
    (lambda c: c.update(instructions_sha256="0" * 64), "instructions_sha256"),
], ids=["schema", "required", "tool-gone", "instructions"])
def test_embed_contract_planted_failure(change, part):
    """Planted failure: a copy of the fixture with one schema or the digest changed is a mismatch at the same
    VERSION, naming the part and how to regenerate; the same change with VERSION moved is accepted."""
    pinned = json.loads(CONTRACT.read_text(encoding="utf-8"))
    live = json.loads(json.dumps(pinned))
    change(live)
    message = contract_mismatch(pinned, live)
    assert message and part in message and REGENERATE in message and "kb_mcp.VERSION" in message, message
    assert contract_mismatch(pinned, {**live, "version": pinned["version"] + ".1"}) is None
    assert contract_mismatch(pinned, json.loads(json.dumps(pinned))) is None


# ---------------------------------------------------------------- live docs (a local HTTP stub, never the network)

DAY = 86400


class DocsStub:
    """A Streamable HTTP MCP server on 127.0.0.1: /sse answers as text/event-stream, /json as application/json. It
    hands out an Mcp-Session-Id at initialize and answers a later request without that id and the negotiated
    MCP-Protocol-Version with 400, so a client that skips them fails. `calls` lists every tools/call as
    (path, tool, arguments); `mode` "error" answers them with isError, "http500" with a 500."""

    def __init__(self):
        import http.server, threading
        self.calls, self.posts, self.mode = [], [], "ok"
        stub = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def send(self, status, body=b"", ctype="application/json", extra=()):
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                for k, v in extra:
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                msg = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                stub.posts.append((self.path, msg.get("method"), dict(self.headers)))
                if "text/event-stream" not in self.headers.get("Accept", "") or "application/json" not in self.headers.get("Accept", ""):
                    return self.send(406)
                if msg.get("method") != "initialize" and (self.headers.get("Mcp-Session-Id") != "sess-1"
                                                          or self.headers.get("MCP-Protocol-Version") != "2025-11-25"):
                    return self.send(400)
                if "id" not in msg:
                    return self.send(202)
                if msg["method"] == "initialize":
                    res, extra = {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}},
                                  "serverInfo": {"name": "stub", "version": "0"}}, [("Mcp-Session-Id", "sess-1")]
                elif msg["method"] == "tools/call":
                    p = msg["params"]
                    stub.calls.append((self.path, p["name"], p["arguments"]))
                    if stub.mode == "http500":
                        return self.send(500)
                    res, extra = {"content": [{"type": "text", "text": f"result {len(stub.calls)} for {json.dumps(p['arguments'], sort_keys=True)}"}],
                                  "isError": stub.mode == "error"}, []
                    if stub.mode == "error":
                        res["content"][0]["text"] = "the docs server failed"
                else:
                    return self.send(200, json.dumps({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "no"}}).encode())
                body = json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": res})
                if self.path == "/sse":  # a notification first, then the reply, split over two data lines' worth of events
                    note = json.dumps({"jsonrpc": "2.0", "method": "notifications/message", "params": {}})
                    self.send(200, f"event: message\ndata: {note}\n\nevent: message\ndata: {body}\n\n".encode(), "text/event-stream", extra)
                else:
                    self.send(200, body.encode(), "application/json", extra)

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def live_docs(tmp_path, monkeypatch):
    """(kb_mcp, stub): kb_mcp's docs urls point at the stub, its cache at tmp_path."""
    sys.path.insert(0, TOOLS)
    import kb_mcp
    stub = DocsStub()
    mcp = tmp_path / "docs.mcp.json"
    base = f"http://127.0.0.1:{stub.port}"
    mcp.write_text(json.dumps({"mcpServers": {"microsoft-learn": {"type": "http", "url": base + "/sse"},
                                              "claude-code-docs": {"type": "http", "url": base + "/json"},
                                              "mcp-docs": {"type": "http", "url": base + "/sse"}}}), encoding="utf-8")
    monkeypatch.setattr(kb_mcp, "DOCS_MCP", str(mcp))
    monkeypatch.setenv("KB_DOCS_CACHE", str(tmp_path / "cache"))
    yield kb_mcp, stub
    stub.close()


def cache_files(tmp_path):
    return sorted((tmp_path / "cache").glob("*.json")) if (tmp_path / "cache").is_dir() else []


def age_entries(tmp_path, days):
    """Rewrite every stored entry as fetched `days` ago."""
    import time
    for f in cache_files(tmp_path):
        entry = json.loads(f.read_text(encoding="utf-8"))
        entry["fetched"] = time.time() - days * DAY
        f.write_text(json.dumps(entry), encoding="utf-8")


def repeat_costs(kb_mcp, stub, tmp_path, days_between):
    """HTTP tools/calls made by one docs_search, then the same one again after the entry aged `days_between` days:
    (calls after the first, calls after the second, the two answers)."""
    args = {"server": "microsoft-learn", "query": "windows laps password length"}
    first = kb_mcp.docs_search(args)
    after_first = len(stub.calls)
    age_entries(tmp_path, days_between)
    second = kb_mcp.docs_search(args)
    return after_first, len(stub.calls), (first, second)


def test_live_docs_cache_repeat_within_7_days_makes_no_http_call(live_docs, tmp_path):
    kb_mcp, stub = live_docs
    first, total, (a, b) = repeat_costs(kb_mcp, stub, tmp_path, days_between=6)
    assert (first, total) == (1, 1), "a repeat 6 days later is served from disk"
    assert "from the cache" not in a and "(from the cache, fetched " in b
    assert a.split("\n\n", 1)[1] == b.split("\n\n", 1)[1], "the cached text is the fetched text"
    assert a.startswith("live docs, not in the kb: microsoft-learn microsoft_docs_search")


def test_live_docs_cache_8_day_old_entry_is_fetched_again(live_docs, tmp_path):
    kb_mcp, stub = live_docs
    first, total, (a, b) = repeat_costs(kb_mcp, stub, tmp_path, days_between=8)
    assert (first, total) == (1, 2), "an entry older than 7 days is fetched again"
    assert "from the cache" not in b and a.split("\n\n", 1)[1] != b.split("\n\n", 1)[1]
    entry = json.loads(cache_files(tmp_path)[0].read_text(encoding="utf-8"))
    assert entry["text"] == b.split("\n\n", 1)[1] and entry["server"] == "microsoft-learn", "the entry was replaced"
    assert kb_mcp.DOCS_TTL_S == 7 * DAY


@pytest.mark.parametrize("plant", ["broken-cache", "ignored-expiry"])
def test_live_docs_cache_planted_failure(live_docs, tmp_path, monkeypatch, plant):
    """Planted failures: a cache that never hits makes the repeat a second HTTP call, and a cache that ignores the
    age serves an 8-day-old entry; the two tests above would fail on each."""
    kb_mcp, stub = live_docs
    if plant == "broken-cache":
        monkeypatch.setattr(kb_mcp, "docs_cache_read", lambda key, now: None)
        first, total, _ = repeat_costs(kb_mcp, stub, tmp_path, days_between=0)
        assert (first, total) == (1, 2), "the repeat within 7 days would not be served from disk"
    else:
        monkeypatch.setattr(kb_mcp, "DOCS_TTL_S", 10 ** 9)
        first, total, _ = repeat_costs(kb_mcp, stub, tmp_path, days_between=8)
        assert (first, total) == (1, 1), "the 8-day-old entry would still be served"


def test_live_docs_cache_key_is_server_tool_and_arguments(live_docs, tmp_path):
    kb_mcp, stub = live_docs
    kb_mcp.docs_search({"server": "mcp-docs", "query": "elicitation"})
    kb_mcp.docs_search({"server": "mcp-docs", "query": "  elicitation "})  # the same query, trimmed
    assert len(stub.calls) == 1
    kb_mcp.docs_search({"server": "mcp-docs", "query": "sampling"})  # another query
    kb_mcp.docs_search({"server": "claude-code-docs", "query": "elicitation"})  # another server
    kb_mcp.docs_fetch({"server": "mcp-docs", "target": "elicitation"})  # another tool, same text
    assert len(stub.calls) == 4 and len({f.name for f in cache_files(tmp_path)}) == 4
    for f in cache_files(tmp_path):
        assert f.stem == kb_mcp.docs_cache_key(*[json.loads(f.read_text(encoding="utf-8"))[k] for k in ("server", "tool", "arguments")])
    assert kb_mcp.docs_cache_key("a", "t", {"query": "x", "n": 1}) == kb_mcp.docs_cache_key("a", "t", {"n": 1, "query": "x"})


def test_live_docs_cache_never_stores_an_error(live_docs, tmp_path):
    kb_mcp, stub = live_docs
    args = {"server": "claude-code-docs", "query": "hooks"}
    for mode, message in (("error", "docs server failed"), ("http500", "HTTP 500")):
        stub.mode = mode
        with pytest.raises(kb_mcp.ToolError, match=message):
            kb_mcp.docs_search(args)
        assert cache_files(tmp_path) == [], mode
    stub.mode = "ok"
    before = len(stub.calls)
    assert "from the cache" not in kb_mcp.docs_search(args), "after the failures the next call goes to the server"
    assert len(stub.calls) == before + 1 and len(cache_files(tmp_path)) == 1


def test_live_docs_cache_ignores_an_unreadable_entry(live_docs, tmp_path):
    kb_mcp, stub = live_docs
    kb_mcp.docs_search({"server": "mcp-docs", "query": "roots"})
    cache_files(tmp_path)[0].write_text("{not json", encoding="utf-8")
    assert "from the cache" not in kb_mcp.docs_search({"server": "mcp-docs", "query": "roots"})
    assert len(stub.calls) == 2


def test_live_docs_cache_client_speaks_streamable_http(live_docs):
    """initialize, then notifications/initialized, then tools/call, with the session id and negotiated version on the
    later requests (the stub answers 400 otherwise), over an SSE and a JSON reply; each server's own tool and
    argument name."""
    kb_mcp, stub = live_docs
    kb_mcp.docs_search({"server": "microsoft-learn", "query": "q"})  # /sse
    kb_mcp.docs_fetch({"server": "claude-code-docs", "target": "head -20 /hooks.mdx"})  # /json
    kb_mcp.docs_fetch({"server": "microsoft-learn", "target": "https://learn.microsoft.com/example"})
    kb_mcp.docs_search({"server": "mcp-docs", "query": "q"})
    assert [m for p, m, _ in stub.posts[:3]] == ["initialize", "notifications/initialized", "tools/call"]
    assert stub.posts[0][2]["Accept"] == "application/json, text/event-stream"
    assert stub.calls == [("/sse", "microsoft_docs_search", {"query": "q"}),
                          ("/json", "query_docs_filesystem_claude_code_docs", {"command": "head -20 /hooks.mdx"}),
                          ("/sse", "microsoft_docs_fetch", {"url": "https://learn.microsoft.com/example"}),
                          ("/sse", "search_model_context_protocol", {"query": "q"})]


def test_live_docs_cache_sse_events_are_parsed():
    sys.path.insert(0, TOOLS)
    import kb_mcp
    body = 'event: message\ndata: {"id": 1,\ndata:  "result": {}}\n\n: comment\ndata:{"id": 2}\n\ndata: not json\n\n'
    assert kb_mcp.sse_messages(body) == [{"id": 1, "result": {}}, {"id": 2}]


def test_live_docs_cache_sse_splits_only_at_cr_and_lf():
    """An SSE line ends only at CR LF, CR or LF: a reply whose text holds U+2028, U+2029, U+0085 (or another
    str.splitlines separator) unescaped is one data line and parses whole."""
    sys.path.insert(0, TOOLS)
    import kb_mcp
    text = "a\u2028b\u2029c\u0085d\x0be\x0cf\x1cg\x1dh\x1ei"
    reply = {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": text}]}}
    data = json.dumps(reply, ensure_ascii=False)
    assert kb_mcp.sse_messages("event: message\ndata: " + data + "\n\n") == [reply]
    assert kb_mcp.sse_messages("event: message\r\ndata: " + data + "\r\n\r\n") == [reply]
    assert kb_mcp.sse_messages("event: message\rdata: " + data + "\r\rdata: {\"id\": 2}") == [reply, {"id": 2}]


def test_live_docs_cache_rejects_bad_arguments(live_docs):
    kb_mcp, stub = live_docs
    for fn, args in ((kb_mcp.docs_search, {"server": "elsewhere", "query": "x"}), (kb_mcp.docs_search, {"server": "mcp-docs"}),
                     (kb_mcp.docs_fetch, {"server": "mcp-docs", "target": " "})):
        with pytest.raises(kb_mcp.ToolError):
            fn(args)
    assert stub.posts == [], "nothing is sent for a bad call"


def test_live_docs_cache_tools_are_listed_by_the_stdio_server_only(monkeypatch):
    """handle() serves the live-docs tools only after main() turned them on, so kb_http.py (which calls handle() alone)
    never offers them; KB_LIVE_DOCS=0 turns them off for the stdio server."""
    monkeypatch.delenv("KB_LIVE_DOCS", raising=False)
    sys.path.insert(0, TOOLS)
    import kb_mcp
    listing = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "docs_search", "arguments": {}}}
    names = lambda: {t["name"] for t in kb_mcp.handle(listing)["result"]["tools"]}  # noqa: E731
    assert names() == set(kb_mcp.HANDLERS) and kb_mcp.handle(call)["error"]["code"] == -32602
    monkeypatch.setattr(kb_mcp, "LIVE_ON", [True])
    assert names() == set(kb_mcp.HANDLERS) | {"docs_search", "docs_fetch"}
    assert kb_mcp.handle(call)["result"]["isError"] is True, "listed: an empty query is a tool error, not an unknown tool"
    monkeypatch.setenv("KB_LIVE_DOCS", "0")
    assert names() == set(kb_mcp.HANDLERS)


def test_live_docs_cache_tools_are_off_under_roots():
    """A server limited to named roots (a host's child, serving clients outside the team) lists no live-docs tool and
    refuses a call to one; the unlimited server lists them (TestKbServer.test_tools_list)."""
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "docs_search", "arguments": {"server": "mcp-docs", "query": "x"}}}]
    p = subprocess.run([sys.executable, SERVER, "--roots", "public"], input="".join(json.dumps(m) + "\n" for m in msgs),
                       capture_output=True, text=True, encoding="utf-8", timeout=120, env=quiet_upstream(), cwd=os.sep)
    assert p.returncode == 0, p.stderr
    by_id = {r["id"]: r for r in map(json.loads, p.stdout.splitlines())}
    assert not {"docs_search", "docs_fetch"} & {t["name"] for t in by_id[1]["result"]["tools"]}
    assert by_id[2]["error"]["code"] == -32602


def test_live_docs_cache_lives_under_the_ignored_cache_directory(monkeypatch):
    sys.path.insert(0, TOOLS)
    import kb_mcp
    monkeypatch.delenv("KB_DOCS_CACHE", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
    folder = Path(kb_mcp.docs_cache_dir())
    assert folder == Path(kb_mcp.kbcommon.HOME) / "_cache" / "live-docs"
    p = subprocess.run(["git", "check-ignore", "-q", "_cache/live-docs/0000.json"], cwd=KB, capture_output=True)
    assert p.returncode == 0, ".gitignore must cover _cache/ (the cache is never committed)"
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", "/plugin-data")
    assert Path(kb_mcp.docs_cache_dir()) == Path("/plugin-data") / "live-docs"


SELFDOC_SECTION = re.compile(r"python3 _tools/selfdoc\.py section ([^`\n]*)")


def skill_section_git_doc_problems(skills):
    """What names a doc as a bare `git` argument in a `selfdoc.py section` command of the SKILL.md texts `skills`
    ({path: text}): [] when nothing. Claude Code's worktree isolation reads a second `git` word in one Bash command
    as a second git call and refuses the command, so a skill passes the doc as `git.md`."""
    problems = []
    for rel, text in sorted(skills.items()):
        for n, line in enumerate(text.splitlines(), 1):
            for m in SELFDOC_SECTION.finditer(line):
                try:
                    args = shlex.split(m.group(1))
                except ValueError:
                    problems.append(f"{rel}:{n}: unparsable selfdoc.py section arguments: {m.group(1)!r}")
                    continue
                docs = args[0::2]  # DOC HEADING pairs
                if "git" in docs:
                    problems.append(f"{rel}:{n}: selfdoc.py section names the doc as bare `git`; pass `git.md`")
    return problems


def skill_texts():
    return {p.relative_to(KB).as_posix(): p.read_text(encoding="utf-8")
            for p in sorted(Path(KB, ".claude", "skills").glob("*/SKILL.md"))}


def test_skill_section_git_doc():
    skills = skill_texts()
    assert skills, "no SKILL.md found under .claude/skills"
    assert skill_section_git_doc_problems(skills) == []


def test_skill_section_git_doc_planted_failure():
    planted = {".claude/skills/x/SKILL.md": "```\npython3 _tools/selfdoc.py section maintaining "
                                            "\"Conduct for changes\" git \"Workflow\"\n```\n",
               ".claude/skills/y/SKILL.md": "Run `python3 _tools/selfdoc.py section git \"Workflow\"` first.\n"}
    problems = skill_section_git_doc_problems(planted)
    assert len(problems) == 2 and all("bare `git`" in p for p in problems), problems
    fixed = {k: v.replace(' git "', ' git.md "') for k, v in planted.items()}
    assert skill_section_git_doc_problems(fixed) == []
    # a heading that reads "git" is not a doc name
    assert skill_section_git_doc_problems({"z": 'python3 _tools/selfdoc.py section backlog "git"'}) == []


def test_skill_section_git_doc_name_with_md_is_accepted_by_selfdoc():
    """selfdoc.py section takes a doc name with `.md` as it takes the bare one (maintaining.md here; git.md the same)."""
    p = subprocess.run([sys.executable, os.path.join(TOOLS, "selfdoc.py"), "section", "maintaining.md",
                        "Conduct for changes"], cwd=KB, capture_output=True, text=True, encoding="utf-8",
                       timeout=timeout_s(60))
    assert p.returncode == 0 and "## Conduct for changes" in p.stdout, p.stdout + p.stderr


if __name__ == "__main__":
    if sys.argv[1:] != ["--write-contract"]:
        sys.exit(f"usage: {REGENERATE}")
    write_contract()
