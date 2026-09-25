---
topic: claude/hooks
priority: P1
applies_to: "Claude Code 2.1.281 docs (retrieved 2026-09-23)"
retrieved_utc: 2026-09-25
sources: [S743, S746]
status: complete
---
# Hooks relevant to MCP tools

## Summary
MCP tools appear in `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PermissionRequest`, `PermissionDenied`
under their `mcp__<server>__<tool>` names. PreToolUse returns `hookSpecificOutput.permissionDecision`
(allow/deny/ask/defer) and may replace input with `updatedInput`. PostToolUse may replace output with
`hookSpecificOutput.updatedToolOutput` (all tools since 2.1.121) or legacy `updatedMCPToolOutput` (MCP only).
`Elicitation` and `ElicitationResult` hooks intercept MCP elicitation.

## Facts
- Matcher `mcp__memory__.*` matches all tools of a server; a bare `mcp__memory` is an exact string and matches no tool. [DOC S743]
- PreToolUse input for MCP tools carries `mcp_server` {`name`, `source`} (v2.1.274+); base trust on `source`, not name. [DOC S743]
- PreToolUse fields: `permissionDecision` (`allow`/`deny`/`ask`/`defer`), `permissionDecisionReason`, `updatedInput`, `additionalContext`. [DOC S743]
- `updatedInput` replaces the entire input object; permission rules are evaluated against the hook-returned input. [DOC S743]
- Multiple PreToolUse decisions: precedence deny > defer > ask > allow; deny and ask rules are still evaluated whatever the hook returns. [DOC S743]
- Exit code 2 from PreToolUse = deny; stderr becomes the reason shown to Claude. [DOC S743]
- Top-level `decision`/`reason` are deprecated for PreToolUse (`approve`/`block` map to allow/deny). [DOC S743]
- A hook cannot skip approval of a tool marked `anthropic/requiresUserInteraction` (v2.1.199+). [DOC S743]
- PostToolUse fields: `decision: "block"` + `reason` (adds text; Claude still sees original), `additionalContext`, `classifierContext`, `updatedToolOutput`, `updatedMCPToolOutput` (MCP only; prefer `updatedToolOutput`). [DOC S743]
- `updatedToolOutput` for all tools was added in 2.1.121 (previously MCP-only). [DOC S746]
- `updatedToolOutput` only changes what Claude sees; the tool already ran; OpenTelemetry tool spans and analytics capture the original output before the hook. [DOC S743]
- MCP tool output replacement is passed through without schema validation. [DOC S743]
- Hook types: `command`, `http`, `mcp_tool`, `prompt`, `agent`; PreToolUse/PostToolUse support all five. [DOC S743]
- `Elicitation` hook: matcher = MCP server name; input has `mcp_server_name`, `message`, optional `mode`, `url`, `elicitation_id`, `requested_schema`; output `hookSpecificOutput.action` (accept/decline/cancel) and `content`; exit 2 denies. [DOC S743]
- `ElicitationResult` hook: runs after the user responds; can override `action`/`content`; exit 2 changes action to `decline`. [DOC S743]
- Elicitation and ElicitationResult hooks were added in 2.1.76 (2026-03-14). [DOC S746]

## Reference
| Event | MCP relevance | Replace data |
|---|---|---|
| PreToolUse | gate/rewrite call | `updatedInput` |
| PermissionRequest | answer permission dialog | decision object |
| PostToolUse | inspect/replace result | `updatedToolOutput` / `updatedMCPToolOutput` |
| PostToolUseFailure | error handling | - |
| Elicitation | auto-answer elicitation | `action`, `content` |
| ElicitationResult | override user answer | `action`, `content` |

## Examples
```json
{ "hooks": { "PostToolUse": [ { "matcher": "mcp__inventory__.*", "hooks": [ { "type": "command", "command": "inventory hook redact" } ] } ] } }
```
