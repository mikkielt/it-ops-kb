#!/bin/bash
# SessionStart (Claude Code on the web): make a fresh container ready for kb work and orient the new session.
# The kb tools are stdlib-only Python; only the tests need pytest (uv installs pyproject.toml's dev group from
# uv.lock). What a new container lacks is the local git config (commit hooks), the local-scope MCP servers (kb and the
# docs servers), the test environment and the context of earlier sessions.
# Idempotent, non-interactive, a few seconds.
set -uo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi
cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}" || exit 0

say() { printf '%s\n' "$*"; }
self=_self  # the kb's own docs
[ -d kb/_self ] && self=kb/_self

if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
  say "it-ops-kb: python3 3.11+ is missing; the kb tools cannot run."
  exit 0
fi

hooks=$(python3 _tools/kbgit.py install-hooks 2>&1 | tail -1)
servers=$(python3 _tools/kb_mcp.py --register-local 2>&1 | tr '\n' ';' | sed 's/;$//')
check=$(python3 _tools/check.py 2>&1 | tail -1)
if command -v uv >/dev/null 2>&1; then
  deps=$(timeout 90 uv sync --frozen --quiet >/dev/null 2>&1 && echo "ready (uv sync: pytest, pytest-xdist, ruff)" || echo "uv sync failed; tests.py retries it")
else
  deps="uv is not installed: tests.py needs it (or pip install pytest pytest-xdist)"
fi
branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
head=$(git log -1 --format='%h %s' 2>/dev/null)
git fetch -q origin main 2>/dev/null
sync=$(git rev-list --left-right --count FETCH_HEAD...HEAD 2>/dev/null | awk '{print $2" ahead, "$1" behind origin/main"}')

say "it-ops-kb session setup:"
say "- commit hooks: ${hooks}"
say "- MCP servers (local scope; new ones load after a restart): ${servers}"
say "- check.py: ${check}"
say "- test tools: ${deps}"
say "- branch ${branch} at ${head} (${sync:-origin/main not fetched})"
say "- Read ${self}/work-left.md first: it lists the open work. Before any change read ${self}/maintaining.md; ${self}/README.md"
say "  maps the kb's own docs (content rules, tools, git, plugin, design)."
say "- The full gate before a commit takes about 60 s: check.py, build_index.py --check, kbgit.py fix --check, tests.py"
say "  (pytest in parallel, ~20 s, includes rag.py eval), stress_test.py (~35 s), fetch.py --offline; after reworded facts also"
say "  doc2query.py stale; after tool, skill or config changes selfdoc.py stale --since @{upstream} (/kb-self)."
say "  Push with python3 _tools/kbgit.py sync --push."
say "- This environment's network policy may deny learn.microsoft.com, github.com pages and api.github.com; raw GitHub"
say "  files, git over https, code.claude.com and the claude-code-docs MCP server work."
exit 0
