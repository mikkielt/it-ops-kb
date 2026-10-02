"""The change router hook (.claude/hooks/kb_change_router.py): a request to change the kb is routed to its skill
(`python3 _tools/tests.py -k router`).

Routing by the prompt's words; questions, kb: prompts, slash commands and prompts whose words name no change skill pass
unchanged; a skill set is named once per session; every routed skill exists and is model-invocable; the hook is registered in .claude/settings.json and never shipped in the plugin; stdin/stdout JSON.
"""
import glob, importlib.util, json, os, re, subprocess, sys

import pytest

from conftest import KB

HOOK = os.path.join(KB, ".claude", "hooks", "kb_change_router.py")
_spec = importlib.util.spec_from_file_location("kb_change_router", HOOK)
router = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(router)


def likely(prompt):
    a = router.answer(prompt)
    return None if a is None else a["hookSpecificOutput"]["additionalContext"].split("Likely: ", 1)[1].split(". Any change", 1)[0]


@pytest.mark.parametrize("prompt, skill", [
    ("update the Kerberos facts, S1216 changed", "kb-refresh"),
    ("refresh auth/kerberos", "kb-refresh"),
    ("please update the Intune scope tags article", "kb-refresh"),
    ("add a new topic on Intune scope tags", "kb-add-topic"),
    ("create a new root for our MDM team's knowledge", "kb-add-root"),
    ("source ~/src/deploy and put it here", "kb-ingest"),
    ("ingest this repository into our team root", "kb-ingest"),
    ("import our team's repo into a new root", "kb-ingest"),
    ("research how uv handles lockfiles and extend the kb", "kb-research"),
    ("research the gaps from the query log", "kb-research"),
    ("research the query log's gaps", "kb-research"),
    ("work the query log queue", "kb-research"),
    ("run a census of all sources", "kb-census"),
    ("commit and push this", "kb-git-sync"),
    ("fix the rag.py search bug", "kb-self"),
    ("plan an epic for the census rewrite", "kb-backlog"),
    ("file a bug: pack returns good for an empty article", "kb-backlog"),
    ("start the sprint", "kb-sprint"),
    ("work on ST-pbonxqx4", "kb-item"),
    ("pick up the next task", "kb-item"),
    ("change the kb-verify skill to also run ruff", "kb-self"),
])
def test_change_requests_are_routed(prompt, skill):
    assert f"/{skill} (" in (likely(prompt) or ""), likely(prompt)


@pytest.mark.parametrize("prompt", [
    "What is the default LAPS password length?",
    "how do I fix error 0x80070005 in Intune?",
    "kb: update ring policy for Windows",
    "kb+: add a device to a group",
    "/kb-refresh auth/kerberos",
    "explain the verdict rules",
    "Another Claude session sent a message:\n<agent-message>Added a new topic, census of sources S-wmmyfoun</agent-message>",
    "[SYSTEM NOTIFICATION - NOT USER INPUT]\n<task-notification>add topics finished</task-notification>",
    "<task-notification>update the skills</task-notification>",
    "",
])
def test_questions_and_commands_pass_unchanged(prompt):
    assert router.answer(prompt) is None


def test_every_routed_skill_exists_and_is_model_invocable():
    for skill, _, rx in router.ROUTES:
        re.compile(rx)
        p = os.path.join(KB, ".claude", "skills", skill, "SKILL.md")
        assert os.path.exists(p), f"routed skill {skill} does not exist"
        fm = open(p, encoding="utf-8").read().split("\n---", 1)[0]
        assert "disable-model-invocation: true" not in fm, f"{skill}: the router names it, so Claude must be able to invoke it"


def test_every_change_skill_is_routed():
    plugin = json.load(open(os.path.join(KB, ".claude-plugin", "plugin.json"), encoding="utf-8"))["skills"]
    shipped = {os.path.basename(s.rstrip("/")) for s in plugin}
    change = {os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(KB, ".claude", "skills", "*", "SKILL.md"))} - shipped
    assert change == {s for s, _, _ in router.ROUTES}, "each clone-only skill needs a route (and each route a skill)"


def test_registered_in_the_clone_only():
    settings = open(os.path.join(KB, ".claude", "settings.json"), encoding="utf-8").read()
    assert ".claude/hooks/kb_change_router.py" in settings
    assert "kb_change_router" not in open(os.path.join(KB, ".claude-plugin", "plugin.json"), encoding="utf-8").read(), \
        "a host project cannot change the kb: the router never ships in the plugin"


def test_hook_protocol():
    run = lambda data: subprocess.run([sys.executable, HOOK], input=data, capture_output=True, text=True, encoding="utf-8", timeout=30)  # noqa: E731
    p = run(json.dumps({"prompt": "add a new topic on Intune scope tags"}))
    out = json.loads(p.stdout)
    assert p.returncode == 0 and out["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "/kb-add-topic" in out["hookSpecificOutput"]["additionalContext"]
    for data in (json.dumps({"prompt": "What is LAPS?"}), "not json"):
        p = run(data)
        assert (p.returncode, p.stdout) == (0, ""), p.stderr


@pytest.mark.parametrize("event", [
    {"prompt": 5, "session_id": "x"},
    {"prompt": ["add a new topic"], "session_id": "x"},
    {"prompt": None, "session_id": "x"},
    {"prompt": {"text": "add a new topic"}, "session_id": "x"},
    {"prompt": 1.5},
    {"prompt": True},
    {"session_id": ["x"]},
    {"prompt": "add a new topic on Intune scope tags", "session_id": {"a": 1}},
    [],
    ["add a new topic"],
    5,
    None,
    "add a new topic",
])
def test_malformed_event_is_silent_and_exits_zero(event):
    """A non-string prompt, a missing or non-dict field, or a non-object event never breaks the hook: no output, exit 0,
    no traceback (a prompt must never be blocked by the router)."""
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(event), capture_output=True, text=True,
                       encoding="utf-8", timeout=30)
    if isinstance(event, dict) and isinstance(event.get("prompt"), str):
        assert p.returncode == 0 and "Traceback" not in p.stderr, p.stderr  # routed: bad session id keeps no marker
    else:
        assert (p.returncode, p.stdout) == (0, ""), p.stderr
    assert "Traceback" not in p.stderr, p.stderr


@pytest.mark.parametrize("prompt", [5, 1.5, True, ["add a new topic"], None, {"a": 1}])
def test_non_string_prompt_routes_nowhere(prompt, tmp_path):
    assert router.routes(prompt) == [] and router.answer(prompt) is None
    assert router.emit({"prompt": prompt, "session_id": "s1"}, str(tmp_path)) is None
    assert not os.listdir(tmp_path)


def test_deeply_nested_event_is_silent_and_exits_zero():
    """A JSON nesting deeper than the parser's limit (a RecursionError on interpreters that raise it) is not our input."""
    p = subprocess.run([sys.executable, HOOK], input="[" * 100000, capture_output=True, text=True, encoding="utf-8",
                       timeout=60)
    assert (p.returncode, p.stdout) == (0, ""), p.stderr[-300:]


def test_routes_to_sections_not_the_whole_maintaining_doc():
    """A change is sent to the "Conduct for changes" section, never to kb/_self/maintaining.md as a whole file."""
    text = router.answer("add a new topic on Intune scope tags")["hookSpecificOutput"]["additionalContext"]
    assert "maintaining.md" not in text, text
    assert 'python3 _tools/selfdoc.py section maintaining "Conduct for changes"' in text, text


def test_session_start_names_conduct_section_not_whole_maintaining_doc():
    """The cloud SessionStart text sends a change to the "Conduct for changes" section, not all of maintaining.md."""
    out = subprocess.run([sys.executable, os.path.join(KB, ".claude", "hooks", "session_start.py"), "--test"],
                         capture_output=True, text=True, encoding="utf-8", cwd=KB).stdout
    assert "read kb/_self/maintaining.md" not in out, out
    assert 'python3 _tools/selfdoc.py section maintaining "Conduct for changes"' in out, out


def test_named_sections_exist():
    """The sections the router and AGENTS.md name resolve with selfdoc.py (a renamed heading breaks them)."""
    sys.path.insert(0, os.path.join(KB, "_tools"))
    import selfdoc
    agents = open(os.path.join(KB, "AGENTS.md"), encoding="utf-8").read()
    assert "`kb/_self/maintaining.md`" not in agents, "AGENTS.md sends a change to the whole of maintaining.md"
    for heading in (re.search(r'"([^"]+)"', router.CONDUCT).group(1), "Skills that change the kb"):
        cmd = f'python3 _tools/selfdoc.py section maintaining "{heading}"'
        assert selfdoc.section("maintaining", heading)[0], f"no section {heading!r} in kb/_self/maintaining.md"
        assert cmd.strip("`") in agents or heading in agents, f"AGENTS.md does not name the section {heading!r}"


@pytest.mark.parametrize("prompt", ["please improve things", "update it", "change that please"])
def test_change_router_once_silent_without_a_match(prompt, tmp_path):
    """A change verb whose words name no change skill adds nothing: no generic "pick a skill" line."""
    assert router.routes(prompt) == [] and router.answer(prompt) is None
    assert router.emit({"prompt": prompt, "session_id": "s1"}, str(tmp_path)) is None
    assert not os.listdir(tmp_path), "a prompt that routes nowhere leaves no marker"


def test_change_router_once_per_session(tmp_path):
    """A skill set is named once per session: the follow-up "commit it" adds no repeat context, another set or another
    session is named again, and a session id unsafe as a file name (or none) keeps no marker."""
    m = str(tmp_path)
    first = router.emit({"prompt": "commit and push this", "session_id": "s1"}, m)
    assert "/kb-git-sync (" in first["hookSpecificOutput"]["additionalContext"]
    assert router.emit({"prompt": "commit it", "session_id": "s1"}, m) is None
    assert router.emit({"prompt": "commit it", "session_id": "s2"}, m) == first
    assert router.emit({"prompt": "refresh auth/kerberos", "session_id": "s1"}, m) is not None
    assert router.emit({"prompt": "refresh auth/kerberos and commit it", "session_id": "s1"}, m) is not None
    assert router.emit({"prompt": "commit it", "session_id": "../x"}, m) is not None
    assert router.emit({"prompt": "commit it"}, m) is not None
    assert sorted(os.listdir(m)) == ["s1.txt", "s2.txt"]


def test_change_router_once_marker_errors_never_block(tmp_path):
    """A marker directory that cannot be created (a file stands in its place) still gives the answer."""
    blocked = tmp_path / "file"
    blocked.write_text("x", encoding="utf-8")
    for _ in range(2):
        assert router.emit({"prompt": "commit it", "session_id": "s1"}, str(blocked / "markers")) is not None


def test_change_router_once_hook_protocol():
    """Through stdin: a session's second "commit it" prints nothing; the marker lives under _cache/change_router/."""
    sid = f"test-once-{os.getpid()}"
    marker = os.path.join(router.MARKERS, sid + ".txt")
    assert router.MARKERS == os.path.join(KB, "_cache", "change_router")
    run = lambda: subprocess.run([sys.executable, HOOK], input=json.dumps({"prompt": "commit it", "session_id": sid}),  # noqa: E731
                                 capture_output=True, text=True, encoding="utf-8", timeout=30)
    try:
        first, second = run(), run()
        assert first.returncode == 0 and "/kb-git-sync" in json.loads(first.stdout)["hookSpecificOutput"]["additionalContext"]
        assert (second.returncode, second.stdout) == (0, ""), second.stderr
        assert os.path.isfile(marker)
    finally:
        if os.path.exists(marker):
            os.remove(marker)


def test_reset_removes_only_that_sessions_marker(tmp_path):
    """After a compaction or clear the routing line is gone from the conversation: the reset drops that session's marker,
    so the same request is routed again, and another session's marker stays."""
    m = str(tmp_path)
    first = router.emit({"prompt": "commit and push this", "session_id": "s1"}, m)
    router.emit({"prompt": "commit and push this", "session_id": "s2"}, m)
    assert router.emit({"prompt": "commit it", "session_id": "s1"}, m) is None  # the defect: silent after compaction
    router.reset({"session_id": "s1", "source": "compact"}, m)
    assert os.listdir(m) == ["s2.txt"]
    assert router.emit({"prompt": "commit it", "session_id": "s1"}, m) == first
    assert router.emit({"prompt": "commit it", "session_id": "s2"}, m) is None


@pytest.mark.parametrize("event", [{"session_id": "nope"}, {"session_id": "../s1"}, {"session_id": ["s1"]},
                                   {"session_id": None}, {}, [], None, "s1", 5])
def test_reset_of_an_unknown_or_unsafe_session_is_a_no_op(event, tmp_path):
    """No marker, no directory, an unsafe or malformed session id: nothing is removed, nothing raised."""
    (tmp_path / "s1.txt").write_text("kb-git-sync\n", encoding="utf-8")
    router.reset(event, str(tmp_path))
    assert os.listdir(tmp_path) == ["s1.txt"]
    router.reset({"session_id": "s1"}, str(tmp_path / "missing"))  # a missing cache directory
    router.reset({"session_id": "s1"}, str(tmp_path / "s1.txt" / "below"))  # a directory that is a file


def test_reset_hook_protocol_is_silent_and_removes_the_marker():
    """Through stdin, as the SessionStart hook runs it: no stdout (it would become context), exit 0, the session's marker
    gone; a missing marker, an unsafe id and input that is not JSON are silent exit 0 too."""
    sid = f"test-reset-{os.getpid()}"
    marker = os.path.join(router.MARKERS, sid + ".txt")
    run = lambda data: subprocess.run([sys.executable, HOOK, "--reset"], input=data, capture_output=True, text=True,  # noqa: E731
                                      encoding="utf-8", timeout=30)
    try:
        os.makedirs(router.MARKERS, exist_ok=True)
        with open(marker, "w", encoding="utf-8", newline="\n") as f:
            f.write("kb-git-sync\n")
        for data in (json.dumps({"session_id": sid, "source": "compact"}), json.dumps({"session_id": sid}), "not json",
                     json.dumps({"session_id": "../x"}), "[" * 100000):
            p = run(data)
            assert (p.returncode, p.stdout) == (0, ""), p.stderr[-300:]
            assert "Traceback" not in p.stderr, p.stderr
            if data == json.dumps({"session_id": sid, "source": "compact"}):
                assert not os.path.exists(marker)
    finally:
        if os.path.exists(marker):
            os.remove(marker)


def test_reset_is_registered_for_compact_and_clear():
    """settings.json runs the reset on SessionStart sources compact and clear, and not on startup, which a new session's
    own marker never needs."""
    hooks = json.load(open(os.path.join(KB, ".claude", "settings.json"), encoding="utf-8"))["hooks"]["SessionStart"]
    found = [g.get("matcher") for g in hooks for h in g["hooks"] if "kb_change_router.py --reset" in h["command"]]
    assert found == ["compact|clear"], found
