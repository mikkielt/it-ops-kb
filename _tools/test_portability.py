"""Portability tests: every hook reaches Python through _tools/kbpy, the launcher finds the interpreter the way each OS
needs, and the hooks read and write UTF-8 whatever the locale (`python3 _tools/tests.py -k portability`).

  TestHookCommands   gate: every command hook in .claude/settings.json and the plugin is `sh "<root>/_tools/kbpy"
                     <script> [word...]` in shell form (words: a subcommand such as `capture`, nothing a shell would
                     read), the launcher's own `--notice`, or the PowerShell launcher (PS_LAUNCH) with `shell:
                     powershell`, and every .githooks script calls kbpy, never an interpreter by name (planted: an
                     interpreter by name, exec form, shell syntax after the script, a git hook with python3, the
                     PowerShell launcher without its shell field); both files start their SessionStart hooks with a
                     synchronous `--notice`. The raw-read PreToolUse hook fires once per Bash call through sh and once
                     per PowerShell call through PowerShell, so a Windows host without Git Bash (no sh) gets it too
                     (planted: one `Bash|PowerShell` sh entry, and that entry beside a PowerShell one, which fires twice)
  TestLauncher       _tools/kbpy with stub interpreters: python3 first on POSIX; on Windows (OS=Windows_NT) a python3
                     alias that fails its probe is skipped for python, then py -3; exit 127 when none is found;
                     `--notice` prints one JSON systemMessage only when none is found, and exits 0
  TestPowerShellLauncher  the PowerShell hook command, run as Claude Code runs `shell: powershell` (pwsh, else
                     powershell, with -Command), with stub interpreters: the same order as kbpy, a failing probe skipped,
                     exit 127 when none is found; end to end with the real interpreter it answers a raw read
  TestHookEncoding   kb_hook.py and the change router under a cp1252 locale read a UTF-8 prompt and answer in UTF-8
                     (planted: kb_hook.py without its reconfigure lines loses the prompt)
Needs `sh` for the launcher and shell-form cases (macOS, Linux, Git Bash) and PowerShell (pwsh or Windows PowerShell)
for the PowerShell launcher cases; each skips without its shell.
"""
import json, os, re, shutil, subprocess, sys

import pytest

from conftest import querylog_env

TOOLS = os.path.dirname(os.path.abspath(__file__))
KB = os.path.dirname(TOOLS)
SH = shutil.which("sh")
LAUNCH = re.compile(r'sh "\$\{(?P<var>CLAUDE_PROJECT_DIR|CLAUDE_PLUGIN_ROOT)\}/_tools/kbpy" (?P<script>[\w./-]+\.py)(?: (?:--)?[a-z][\w-]*)*$')
NOTICE = re.compile(r'sh "\$\{(?P<var>CLAUDE_PROJECT_DIR|CLAUDE_PLUGIN_ROOT)\}/_tools/kbpy" --notice')
needs_sh = pytest.mark.skipif(not SH, reason="no sh on PATH (Windows without Git Bash)")
# The PowerShell twin of kbpy, inline in the hook so it needs no .ps1 (no execution policy): the same interpreters in
# the same order, each probed for 3.11+, then the script with the hook's stdin; exit 127 when none is found.
PS_HEAD = ("$p = 'import sys; sys.exit(sys.version_info < (3, 11))'; foreach ($c in 'python3', 'python', 'py -3') "
           "{ $e, $a = -split $c; try { & $e $a -c $p *>$null } catch { continue }; if ($LASTEXITCODE -eq 0) { & $e $a ")
PS_TAIL = "; exit $LASTEXITCODE } }; exit 127"
PS_LAUNCH = re.compile(re.escape(PS_HEAD) + r'"\$env:(?P<var>CLAUDE_PROJECT_DIR|CLAUDE_PLUGIN_ROOT)/(?P<script>[\w./-]+\.py)"'
                       + re.escape(PS_TAIL))
# Claude Code's order for `shell: powershell`: pwsh, else Windows PowerShell (kb/public/claude/powershell-tool.md)
PS = shutil.which("pwsh") or shutil.which("powershell")
needs_ps = pytest.mark.skipif(not PS, reason="no PowerShell on PATH (pwsh is opt-in on macOS and Linux)")


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
        powershell = h.get("shell") == "powershell"
        m = (PS_LAUNCH if powershell else LAUNCH).fullmatch(h.get("command", ""))
        n = None if powershell else NOTICE.fullmatch(h.get("command", ""))
        if n and "args" not in h and "shell" not in h and n.group("var") == var:
            continue
        if "args" in h or ("shell" in h and not powershell) or not m or m.group("var") != var \
                or not os.path.isfile(os.path.join(KB, m.group("script"))):
            bad.append(f"{event}: {h.get('command')} {h.get('args', '')}".strip())
    return bad


def raw_read_offenders(cfg):
    """The raw-read hint (kb_hook.py on PreToolUse) must fire exactly once per Bash call, through sh, and once per
    PowerShell call, through `shell: powershell`: the Bash tool exists only with Git Bash, and without Git Bash a
    shell-form hook reaches PowerShell, where `sh` is missing (kb/public/claude/hooks.md). Matchers are read as
    Claude Code reads a tool matcher: an exact name or a `|` list."""
    bad = []
    for tool, want in (("Bash", None), ("PowerShell", "powershell")):
        hits = [h for group in cfg.get("hooks", {}).get("PreToolUse", [])
                if tool in (group.get("matcher") or "*").split("|") or group.get("matcher") in (None, "", "*")
                for h in group.get("hooks", []) if "kb_hook.py" in h.get("command", "")]
        if len(hits) != 1 or hits[0].get("shell") != want:
            bad.append(f"{tool}: {len(hits)} kb_hook.py hooks, shells {[h.get('shell') for h in hits]}")
    return bad


def githook_offenders(texts):
    """.githooks scripts ({name: text}) that name an interpreter instead of calling _tools/kbpy."""
    return sorted(n for n, t in texts.items()
                  if '_tools/kbpy"' not in t or re.search(r"(?m)^(?!\s*#).*\b(python3?|py -3)\b", t))


class TestHookCommands:
    @pytest.mark.parametrize("rel", [".claude/settings.json", ".claude-plugin/plugin.json"])
    def test_session_starts_with_the_python_notice(self, rel):
        """Without Python every other hook exits 127 in silence: the first SessionStart hook is kbpy --notice,
        synchronous (an async hook's systemMessage reaches Claude, not the person) with a short timeout."""
        first = load(rel)["hooks"]["SessionStart"][0]["hooks"][0]
        assert NOTICE.fullmatch(first["command"]) and not first.get("async") and 0 < first.get("timeout", 0) <= 10, first

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
            {"type": "command", "command": 'sh "${CLAUDE_PROJECT_DIR}/_tools/kbpy" _tools/kb_hook.py'},
            {"type": "command", "command": PS_HEAD + '"$env:CLAUDE_PROJECT_DIR/_tools/kb_hook.py"' + PS_TAIL},
            {"type": "command", "shell": "powershell",
             "command": 'sh "${CLAUDE_PROJECT_DIR}/_tools/kbpy" _tools/kb_hook.py'},
            {"type": "command", "shell": "powershell",
             "command": PS_HEAD + '"$env:CLAUDE_PROJECT_DIR/_tools/kb_hook.py"' + PS_TAIL}]}]}}
        assert len(launcher_offenders(planted, "CLAUDE_PROJECT_DIR")) == 7

    def test_raw_read_hook_fires_once_per_shell_tool(self):
        assert raw_read_offenders(load(".claude/settings.json")) == []
        sh_hook = {"type": "command", "command": 'sh "${CLAUDE_PROJECT_DIR}/_tools/kbpy" _tools/kb_hook.py'}
        ps_hook = {"type": "command", "shell": "powershell",
                   "command": PS_HEAD + '"$env:CLAUDE_PROJECT_DIR/_tools/kb_hook.py"' + PS_TAIL}
        both_sh = {"hooks": {"PreToolUse": [{"matcher": "Bash|PowerShell", "hooks": [sh_hook]}]}}
        assert raw_read_offenders(both_sh) == ["PowerShell: 1 kb_hook.py hooks, shells [None]"]
        twice = {"hooks": {"PreToolUse": [{"matcher": "Bash|PowerShell", "hooks": [sh_hook]},
                                          {"matcher": "PowerShell", "hooks": [ps_hook]}]}}
        assert raw_read_offenders(twice) == ["PowerShell: 2 kb_hook.py hooks, shells [None, 'powershell']"]

    def test_powershell_launcher_tries_what_kbpy_tries(self):
        with open(os.path.join(TOOLS, "kbpy"), encoding="utf-8") as f:
            kbpy = f.read()
        assert 'for py in python3 python "py -3"; do' in kbpy and "'python3', 'python', 'py -3'" in PS_HEAD
        assert "sys.version_info < (3, 11)" in kbpy

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
            if "kb_hook.py" in h["command"] and h.get("shell") != "powershell":
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
if [ "$1" = "-c" ] || [ "$2" = "-c" ]; then exit {probe}; fi
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

    def test_notice_is_silent_with_python(self, tmp_path):
        for windows in (False, True):
            assert self.run(tmp_path, {"python3": 0}, windows, "--notice")[:2] == (0, "")

    def test_notice_tells_the_person_without_python(self, tmp_path):
        rc, out, _ = self.run(tmp_path, {"python3": 9009}, True, "--notice")
        msg = json.loads(out)["systemMessage"]
        # the installer by kbpy's own directory (a plugin copy is not the project), JSON-escaped on a Windows path
        assert rc == 0 and "no Python 3.11+ found" in msg and os.path.join(KB, "_tools") + "/install-python.ps1" in msg, out
        assert "kb-setup" not in msg, "the plugin has no /kb-setup"
        (tmp_path / "posix").mkdir()
        rc, out, _ = self.run(tmp_path / "posix", {}, False, "--notice")
        assert rc == 0 and "install-python.ps1" not in json.loads(out)["systemMessage"], out

    def test_no_script_is_a_usage_error(self, tmp_path):
        rc, _, err = self.run(tmp_path, {"python3": 0}, False)
        assert rc == 2 and "usage" in err


STUB_CMD = """@echo off
if "%~1"=="-c" exit /b {probe}
if "%~2"=="-c" exit /b {probe}
echo {name} %*
"""


def ps_hook_command():
    """The command of the PowerShell raw-read hook in .claude/settings.json."""
    for group in load(".claude/settings.json")["hooks"]["PreToolUse"]:
        for h in group["hooks"]:
            if h.get("shell") == "powershell" and "kb_hook.py" in h["command"]:
                return h["command"]
    raise AssertionError("no PowerShell kb_hook.py hook")


@needs_ps
class TestPowerShellLauncher:
    def run(self, cmd, env, stdin=""):
        """Run `cmd` as Claude Code runs a `shell: powershell` hook; (returncode, stdout, stderr)."""
        p = subprocess.run([PS, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                           input=stdin.encode("utf-8"), capture_output=True, env=env, timeout=120)
        return p.returncode, p.stdout.decode("utf-8").strip(), p.stderr.decode("utf-8", "replace")

    def stubbed(self, tmp_path, stubs):
        """Only `stubs` ({name: probe exit code}) on PATH, plus what PowerShell itself needs to start."""
        bin_ = tmp_path / "bin"
        bin_.mkdir()
        for name, probe in stubs.items():
            if os.name == "nt":
                (bin_ / f"{name}.cmd").write_text(STUB_CMD.format(name=name, probe=probe), encoding="utf-8",
                                                  newline="\r\n")
            else:
                (bin_ / name).write_text(STUB.format(name=name, probe=probe), encoding="utf-8", newline="\n")
                (bin_ / name).chmod(0o755)
        keep = ("SYSTEMROOT", "COMSPEC", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE", "PSMODULEPATH", "PATHEXT")
        env = {k: v for k, v in os.environ.items() if k.upper() in keep}
        env.update(PATH=str(bin_), CLAUDE_PROJECT_DIR=KB)
        return env

    def test_skips_an_alias_that_fails_its_probe(self, tmp_path):
        rc, out, err = self.run(ps_hook_command(), self.stubbed(tmp_path, {"python3": 9009, "python": 0, "py": 0}))
        assert rc == 0, err
        assert self.argv(out) == f"python {KB}/_tools/kb_hook.py".replace("\\", "/"), out

    def test_falls_back_to_py_3(self, tmp_path):
        """`py -3` reaches py as two words (planted: splatting the string '-3' with `@a` passes `-` and `3`)."""
        env = self.stubbed(tmp_path, {"python3": 9009, "python": 1, "py": 0})
        rc, out, err = self.run(ps_hook_command(), env)
        assert rc == 0, err
        assert self.argv(out) == f"py -3 {KB}/_tools/kb_hook.py".replace("\\", "/"), out
        planted = ps_hook_command().replace("& $e $a ", "& $e @a ")
        assert planted != ps_hook_command()
        assert not self.argv(self.run(planted, env)[1]).startswith("py -3 ")

    @staticmethod
    def argv(out):
        """A stub's echo of its arguments, the same from the .cmd stub (quotes kept) and the sh stub ([arg])."""
        return re.sub(r'["\[\]]', "", out).replace("\\", "/")

    def test_no_interpreter_exits_127(self, tmp_path):
        rc, out, _ = self.run(ps_hook_command(), self.stubbed(tmp_path, {"python3": 9009}))
        assert (rc, out) == (127, "")

    def test_answers_a_raw_read_end_to_end(self, tmp_path):
        """The real interpreter reads the hook's JSON from stdin (PowerShell hands a native command its own stdin) and
        its UTF-8 answer comes back unchanged."""
        env = querylog_env(tmp_path, base=dict(os.environ, CLAUDE_PROJECT_DIR=KB))
        event = {"hook_event_name": "PreToolUse", "tool_name": "PowerShell",
                 "tool_input": {"command": "Get-Content kb/public/claude/hooks.md # Łódź"}}
        rc, out, err = self.run(ps_hook_command(), env, json.dumps(event, ensure_ascii=False))
        assert rc == 0, err
        assert "rag.py" in json.loads(out)["hookSpecificOutput"]["additionalContext"]
        event["tool_input"]["command"] = "Get-ChildItem kb"
        assert self.run(ps_hook_command(), env, json.dumps(event))[:2] == (0, "")


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
