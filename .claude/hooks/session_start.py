#!/usr/bin/env python3
"""SessionStart (Claude Code on the web): make a fresh container ready for kb work and orient the new session.

The kb tools are stdlib-only Python; only the tests need pytest (uv installs pyproject.toml's dev group from uv.lock).
What a new container lacks is the local git config (commit hooks), the local-scope MCP servers (kb and the docs
servers), the test environment and the context of earlier sessions. Idempotent, non-interactive, a few seconds.
Outside a cloud session (CLAUDE_CODE_REMOTE is not "true") it does nothing. Run through `_tools/kbpy`, like every
hook, so it finds the interpreter on every OS; `--test` runs it as if in a cloud session.
"""
import os, shutil, subprocess, sys

HOME = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SELF = "kb/_self"  # the kb's own docs


def run(args, timeout=120):
    """(returncode, stdout+stderr) of a command run in the clone; (None, message) when it cannot start or times out."""
    try:
        p = subprocess.run(args, cwd=HOME, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, str(e)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def last_line(text):
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def report():
    if sys.version_info < (3, 11):
        return ["it-ops-kb: python3 3.11+ is missing; the kb tools cannot run."]
    py = [sys.executable]
    hooks = last_line(run(py + ["_tools/kbgit.py", "install-hooks"])[1])
    servers = ";".join(ln for ln in run(py + ["_tools/kb_mcp.py", "--register-local"])[1].splitlines() if ln)
    check = last_line(run(py + ["_tools/check.py"])[1])
    if shutil.which("uv"):
        rc, _ = run(["uv", "sync", "--frozen", "--quiet"], timeout=90)
        deps = "ready (uv sync: pytest, pytest-xdist, ruff)" if rc == 0 else "uv sync failed; tests.py retries it"
    else:
        deps = "uv is not installed: tests.py needs it (or pip install pytest pytest-xdist)"
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])[1].strip()
    head = run(["git", "log", "-1", "--format=%h %s"])[1].strip()
    run(["git", "fetch", "-q", "origin", "main"])
    rc, counts = run(["git", "rev-list", "--left-right", "--count", "FETCH_HEAD...HEAD"])
    parts = counts.split()
    sync = f"{parts[1]} ahead, {parts[0]} behind origin/main" if rc == 0 and len(parts) == 2 else "origin/main not fetched"
    return [
        "it-ops-kb session setup:",
        f"- commit hooks: {hooks}",
        f"- MCP servers (local scope; new ones load after a restart): {servers}",
        f"- check.py: {check}",
        f"- test tools: {deps}",
        f"- branch {branch} at {head} ({sync})",
        f"- The open work is the backlog ({SELF}/backlog.md; the horizon hook printed its state). Before any change read {SELF}/maintaining.md; {SELF}/README.md",
        "  maps the kb's own docs (content rules, tools, git, plugin, design).",
        "- The full gate before a commit takes about 60 s: check.py, build_index.py --check, kbgit.py fix --check, tests.py",
        "  (pytest in parallel, ~20 s, includes rag.py eval), stress_test.py (~35 s), fetch.py --offline; after reworded facts also",
        "  doc2query.py stale; after tool, skill or config changes selfdoc.py stale --since @{upstream} (/kb-self).",
        "  Push with python3 _tools/kbgit.py sync --push.",
        "- This environment's network policy may deny learn.microsoft.com, github.com pages and api.github.com; raw GitHub",
        "  files, git over https, code.claude.com and the claude-code-docs MCP server work.",
    ]


def main(argv):
    if os.environ.get("CLAUDE_CODE_REMOTE") != "true" and "--test" not in argv:
        return 0
    out = "".join(line + "\n" for line in report())
    sys.stdout.buffer.write(out.encode("utf-8"))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
