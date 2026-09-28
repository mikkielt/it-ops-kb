"""Portability tests: every hook reaches Python through _tools/kbpy, the launcher finds the interpreter the way each OS
needs, and the hooks read and write UTF-8 whatever the locale (`python3 _tools/tests.py -k portability`).

  TestHookCommands   gate: every command hook in .claude/settings.json and the plugin is `sh "<root>/_tools/kbpy"
                     <script> [word...]` in shell form (words: a subcommand such as `capture`, nothing a shell would
                     read), and every .githooks script calls kbpy, never an interpreter by name (planted: an
                     interpreter by name, exec form, shell syntax after the script, a git hook with python3)
  TestLauncher       _tools/kbpy with stub interpreters: python3 first on POSIX; on Windows (OS=Windows_NT) a python3
                     alias that fails its probe is skipped for python, then py -3; exit 127 when none is found
  TestHookEncoding   kb_hook.py and the change router under a cp1252 locale read a UTF-8 prompt and answer in UTF-8
                     (planted: kb_hook.py without its reconfigure lines loses the prompt)
Needs `sh` for the launcher and shell-form cases (macOS, Linux, Git Bash); they skip without it.
"""
import json, os, re, shutil, subprocess, sys

import pytest

from conftest import querylog_env

TOOLS = os.path.dirname(os.path.abspath(__file__))
KB = os.path.dirname(TOOLS)
SH = shutil.which("sh")
LAUNCH = re.compile(r'sh "\$\{(?P<var>CLAUDE_PROJECT_DIR|CLAUDE_PLUGIN_ROOT)\}/_tools/kbpy" (?P<script>[\w./-]+\.py)(?: (?:--)?[a-z][\w-]*)*$')
needs_sh = pytest.mark.skipif(not SH, reason="no sh on PATH (Windows without Git Bash)")


def load(rel):
    with open(os.path.join(KB, rel), encoding="utf-8") as f:
        return json.load(f)


def command_hooks(cfg):
    """Every command hook of a settings or plugin file: (event, hook dict)."""
    for event, groups in (cfg.get("hooks") or {}).items():
        for group in groups:
            for h in group.get("hooks", []):
                if h.get("type") == "command":
                    yield event, h


def launcher_offenders(cfg, var):
    """Command hooks that do not run a repository script through _tools/kbpy in shell form, with `var` as the root."""
    bad = []
    for event, h in command_hooks(cfg):
        m = LAUNCH.fullmatch(h.get("command", ""))
        if "args" in h or not m or m.group("var") != var or not os.path.isfile(os.path.join(KB, m.group("script"))):
            bad.append(f"{event}: {h.get('command')} {h.get('args', '')}".strip())
    return bad


def githook_offenders(texts):
    """.githooks scripts ({name: text}) that name an interpreter instead of calling _tools/kbpy."""
    return sorted(n for n, t in texts.items()
                  if '_tools/kbpy"' not in t or re.search(r"(?m)^(?!\s*#).*\b(python3?|py -3)\b", t))


class TestHookCommands:
    def test_settings_hooks_go_through_the_launcher(self):
        cfg = load(".claude/settings.json")
        assert sum(1 for _ in command_hooks(cfg)) >= 3
        assert launcher_offenders(cfg, "CLAUDE_PROJECT_DIR") == []

    def test_plugin_hooks_go_through_the_launcher(self):
        cfg = load(".claude-plugin/plugin.json")
        assert sum(1 for _ in command_hooks(cfg)) >= 1
        assert launcher_offenders(cfg, "CLAUDE_PLUGIN_ROOT") == []

    def test_planted_hooks_fail_the_gate(self):
        planted = {"hooks": {"UserPromptSubmit": [{"hooks": [
            {"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR/_tools/kb_hook.py"'},
            {"type": "command", "command": "python3", "args": ["${CLAUDE_PLUGIN_ROOT}/_tools/kb_hook.py"]},
            {"type": "command", "command": 'sh "${CLAUDE_PROJECT_DIR}/_tools/kbpy" _tools/no_such_tool.py'},
            {"type": "command", "command": 'sh "${CLAUDE_PROJECT_DIR}/_tools/kbpy" _tools/querylog.py capture; id'},
            {"type": "command", "command": 'sh "${CLAUDE_PROJECT_DIR}/_tools/kbpy" _tools/querylog.py capture',
             "async": True},
            {"type": "command", "command": 'sh "${CLAUDE_PLUGIN_ROOT}/_tools/kbpy" _tools/kb_hook.py'},
            {"type": "command", "command": 'sh "${CLAUDE_PROJECT_DIR}/_tools/kbpy" _tools/kb_hook.py'}]}]}}
        assert len(launcher_offenders(planted, "CLAUDE_PROJECT_DIR")) == 5

    def test_git_hooks_call_the_launcher(self):
        d = os.path.join(KB, ".githooks")
        texts = {}
        for n in os.listdir(d):
            with open(os.path.join(d, n), encoding="utf-8") as f:
                texts[n] = f.read()
        assert sorted(texts) == ["commit-msg", "pre-push", "prepare-commit-msg"]
        assert githook_offenders(texts) == []
        planted = dict(texts, **{"commit-msg": 'for py in python3 python; do "$py" "$top/_tools/kbgit.py"; done\n'})
        assert githook_offenders(planted) == ["commit-msg"]

    def test_launcher_and_hooks_are_lf_only(self):
        for rel in ["_tools/kbpy"] + [os.path.join(".githooks", n) for n in os.listdir(os.path.join(KB, ".githooks"))]:
            with open(os.path.join(KB, rel), "rb") as f:
                assert b"\r" not in f.read(), f"{rel}: sh cannot run CRLF scripts"

    @needs_sh
    def test_settings_prompt_hook_runs_end_to_end(self, tmp_path):
        """The UserPromptSubmit commands, run as Claude Code runs shell form (`sh -c` with the placeholder set)."""
        env = querylog_env(tmp_path, base=dict(os.environ, CLAUDE_PROJECT_DIR=KB))
        for _, h in command_hooks(load(".claude/settings.json")):
            if "kb_hook.py" in h["command"]:
                cmd = h["command"].replace("${CLAUDE_PROJECT_DIR}", KB)
                p = subprocess.run([SH, "-c", cmd], input=json.dumps({"prompt": "kb: intune win32 app detection rule"}),
                                   capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
                assert p.returncode == 0, p.stderr
                assert json.loads(p.stdout)["decision"] == "block"

    def test_session_start_is_quiet_outside_a_cloud_session(self):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_REMOTE"}
        p = subprocess.run([sys.executable, os.path.join(KB, ".claude", "hooks", "session_start.py")], capture_output=True,
                           text=True, encoding="utf-8", env=env, timeout=60)
        assert (p.returncode, p.stdout, p.stderr) == (0, "", "")


STUB = """#!/bin/sh
if [ "$1" = "-c" ]; then exit {probe}; fi
printf '%s' "{name}"
for a in "$@"; do printf ' [%s]' "$a"; done
echo
"""


@needs_sh
class TestLauncher:
    def run(self, tmp_path, stubs, windows, *args):
        """Run _tools/kbpy with only `stubs` ({name: probe exit code}) on PATH; (returncode, stdout, stderr)."""
        bin_ = tmp_path / "bin"
        bin_.mkdir(exist_ok=True)
        for name, probe in stubs.items():
            (bin_ / name).write_text(STUB.format(name=name, probe=probe), encoding="utf-8", newline="\n")
            (bin_ / name).chmod(0o755)
        env = {"PATH": str(bin_)}
        if windows:
            env["OS"] = "Windows_NT"
        p = subprocess.run([SH, os.path.join(KB, "_tools", "kbpy"), *args], capture_output=True, text=True,
                           encoding="utf-8", env=env, timeout=30)
        return p.returncode, p.stdout.strip(), p.stderr

    def test_posix_prefers_python3(self, tmp_path):
        rc, out, _ = self.run(tmp_path, {"python3": 0, "python": 0}, False, "_tools/x.py", "a b", "--c")
        assert rc == 0
        assert re.fullmatch(r"python3 \[.*[/\\]_tools/\.\./_tools/x\.py\] \[a b\] \[--c\]", out), out

    def test_posix_falls_back_to_python(self, tmp_path):
        rc, out, _ = self.run(tmp_path, {"python": 0}, False, "_tools/x.py")
        assert (rc, out.split()[0]) == (0, "python")

    def test_windows_skips_an_alias_that_fails_its_probe(self, tmp_path):
        rc, out, _ = self.run(tmp_path, {"python3": 9009, "python": 0, "py": 0}, True, "_tools/x.py")
        assert (rc, out.split()[0]) == (0, "python")

    def test_windows_falls_back_to_py_3(self, tmp_path):
        rc, out, _ = self.run(tmp_path, {"python3": 9009, "python": 1, "py": 0}, True, "_tools/x.py", "q")
        assert rc == 0
        assert re.fullmatch(r"py \[-3\] \[.*/_tools/x\.py\] \[q\]", out), out

    def test_no_interpreter_exits_127(self, tmp_path):
        rc, out, err = self.run(tmp_path, {"python3": 9009}, True, "_tools/x.py")
        assert (rc, out) == (127, "")
        assert "no Python 3.11+ found" in err and "_tools/x.py" in err

    def test_no_script_is_a_usage_error(self, tmp_path):
        rc, _, err = self.run(tmp_path, {"python3": 0}, False)
        assert rc == 2 and "usage" in err


PROMPT = "kb: Łódź ☃ zzqxv"  # Ł is C5 81 in UTF-8; 0x81 has no cp1252 character, so a cp1252 read fails


class TestHookEncoding:
    def hook(self, path, prompt, data):
        env = querylog_env(data, base=dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONPATH=TOOLS))
        env.pop("PYTHONUTF8", None)
        p = subprocess.run([sys.executable, "-X", "utf8=0", path], input=json.dumps({"prompt": prompt},
                           ensure_ascii=False).encode("utf-8"), capture_output=True, env=env, timeout=120)
        return p.returncode, p.stdout.decode("utf-8"), p.stderr.decode("utf-8", "replace")

    def test_kb_hook_reads_and_writes_utf8(self, tmp_path):
        rc, out, err = self.hook(os.path.join(TOOLS, "kb_hook.py"), PROMPT, tmp_path)
        assert rc == 0, err
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        assert "Łódź" in ctx or "zzqxv" in ctx

    def test_router_reads_utf8(self, tmp_path):
        rc, out, err = self.hook(os.path.join(KB, ".claude", "hooks", "kb_change_router.py"), "please update the Łódź ☃ article",
                                 tmp_path)
        assert rc == 0, err
        assert "kb-" in json.loads(out)["hookSpecificOutput"]["additionalContext"]

    def test_tools_print_utf8_under_a_cp1252_locale(self):
        """Every tool imports kbcommon, which switches stdout to UTF-8; without it (planted: plain Python) printing a
        character cp1252 lacks fails, as a Windows pipe does."""
        env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONPATH=TOOLS)
        env.pop("PYTHONUTF8", None)
        code = "print('\\u0141\\u00f3d\\u017a \\u2603')"
        ok = subprocess.run([sys.executable, "-X", "utf8=0", "-c", "import kbcommon; " + code], capture_output=True,
                            env=env, timeout=60)
        assert (ok.returncode, ok.stdout.decode("utf-8").strip()) == (0, "Łódź ☃")
        planted = subprocess.run([sys.executable, "-X", "utf8=0", "-c", code], capture_output=True, env=env, timeout=60)
        assert planted.returncode != 0 and b"UnicodeEncodeError" in planted.stderr
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "rag.py"), "show", "public/claude/hooks.md:1", "-n", "3"],
                           capture_output=True, env=env, timeout=120)
        assert p.returncode == 0 and "topic: claude/hooks" in p.stdout.decode("utf-8")

    def test_planted_hook_without_reconfigure_loses_the_prompt(self, tmp_path):
        with open(os.path.join(TOOLS, "kb_hook.py"), encoding="utf-8") as f:
            src = f.read()
        planted = re.sub(r"(?m)^\s*sys\.std(in|out)\.reconfigure\(.*\)\n", "", src)
        assert planted != src
        path = tmp_path / "kb_hook.py"
        path.write_text(planted, encoding="utf-8", newline="\n")
        rc, out, _ = self.hook(str(path), PROMPT, tmp_path / "data")
        assert out == "", "under cp1252 the unconfigured hook cannot read the prompt"
