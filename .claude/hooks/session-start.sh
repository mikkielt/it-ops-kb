#!/bin/bash
# SessionStart (Claude Code on the web): make a fresh container ready for kb work and orient the new session.
# The kb tools are stdlib-only Python, so there is nothing to install; what a new container lacks is the local git
# config (commit hooks) and the context of earlier sessions. Idempotent, non-interactive, a few seconds.
set -uo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi
cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}" || exit 0

say() { printf '%s\n' "$*"; }

if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
  say "it-ops-kb: python3 3.9+ is missing; the kb tools cannot run."
  exit 0
fi

hooks=$(python3 _tools/kbgit.py install-hooks 2>&1 | tail -1)
check=$(python3 _tools/check.py 2>&1 | tail -1)
branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
head=$(git log -1 --format='%h %s' 2>/dev/null)
git fetch -q origin main 2>/dev/null
sync=$(git rev-list --left-right --count FETCH_HEAD...HEAD 2>/dev/null | awk '{print $2" ahead, "$1" behind origin/main"}')

say "it-ops-kb session setup:"
say "- commit hooks: ${hooks}"
say "- check.py: ${check}"
say "- branch ${branch} at ${head} (${sync:-origin/main not fetched})"
say "- Read work-left.md first: it lists the open work (census 2026-09-25: blocked and unconfirmed sources, resume with"
say "  /kb-census 2026-09-25 --resume; census tag not created; plugin install from gitlab.com; known debt)."
say "- The full gate before a commit takes about 70 s: check.py, build_index.py --check, kbgit.py fix --check, tests.py"
say "  (~30 s), stress_test.py (~35 s), fetch.py --offline. Push with python3 _tools/kbgit.py sync --push."
say "- This environment's network policy may deny learn.microsoft.com, github.com pages and api.github.com; raw GitHub"
say "  files, git over https, code.claude.com and the claude-code-docs MCP server work."
exit 0
