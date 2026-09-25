#!/usr/bin/env python3
"""PreToolUse hook of the it-ops-kb-docs plugin: exit 2 blocks the docs servers' submit_feedback, stderr says why.
A plugin cannot ship permission rules (its settings only take agent and subagentStatusLine), so a hook does it."""
import sys

sys.stdin.read()
print("blocked by the it-ops-kb-docs plugin: submit_feedback posts text to the docs vendor, outside the kb; never call it",
      file=sys.stderr)
sys.exit(2)
