"""The change router hook (.claude/hooks/kb_change_router.py): a request to change the kb is routed to its skill
(`python3 _tools/tests.py -k router`).

Routing by the prompt's words; questions, kb: prompts and slash commands pass unchanged; every routed skill exists and
is model-invocable; the hook is registered in .claude/settings.json and never shipped in the plugin; stdin/stdout JSON.
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
    ("add a new topic on Intune scope tags", "kb-add-topic"),
    ("research how uv handles lockfiles and extend the kb", "kb-research"),
    ("run a census of all sources", "kb-census"),
    ("commit and push this", "kb-git-sync"),
    ("fix the rag.py search bug", "kb-self"),
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
    run = lambda data: subprocess.run([sys.executable, HOOK], input=data, capture_output=True, text=True, timeout=30)  # noqa: E731
    p = run(json.dumps({"prompt": "add a new topic on Intune scope tags"}))
    out = json.loads(p.stdout)
    assert p.returncode == 0 and out["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "/kb-add-topic" in out["hookSpecificOutput"]["additionalContext"]
    for data in (json.dumps({"prompt": "What is LAPS?"}), "not json"):
        p = run(data)
        assert (p.returncode, p.stdout) == (0, ""), p.stderr
