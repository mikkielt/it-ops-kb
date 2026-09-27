---
topic: claude/hooks
priority: P1
applies_to: "Claude Code 2.1.281 docs (retrieved 2026-09-23; UserPromptSubmit, common input, async and Stop sections re-read 2026-09-27)"
retrieved_utc: 2026-09-27
sources: [S743, S746]
status: complete
---
# Hooks relevant to MCP tools

## Summary
MCP tools appear in `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PermissionRequest`, `PermissionDenied`
under their `mcp__<server>__<tool>` names. PreToolUse returns `hookSpecificOutput.permissionDecision`
(allow/deny/ask/defer) and may replace input with `updatedInput`. PostToolUse may replace output with
`hookSpecificOutput.updatedToolOutput` (all tools since 2.1.121) or legacy `updatedMCPToolOutput` (MCP only).
`Elicitation` and `ElicitationResult` hooks intercept MCP elicitation. `UserPromptSubmit` runs before Claude
processes a prompt: it can add context, or block the prompt, erase it from context and show the user a `reason`
instead, so a hook can answer a prompt without a model call.

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

### UserPromptSubmit, common input and logging
- Every hook receives common input fields including `session_id`, `transcript_path`, `cwd` and `permission_mode`; `UserPromptSubmit` adds `prompt`, the submitted text, with collapsed `[Pasted text #N]` content expanded in place. [DOC S743]
- Common input field `prompt_id` (v2.1.196+) is a UUID for the prompt being processed and matches the `prompt.id` attribute on OpenTelemetry events, so hook output can be joined with telemetry for one prompt; it is absent until the first user input. [DOC S743]
- `transcript_path` is written asynchronously and may not yet hold the current turn's latest messages when a hook fires; `Stop` and `SubagentStop` hooks receive `last_assistant_message` (Claude's final response text) for that purpose. [DOC S743]
- `UserPromptSubmit` output: `decision: "block"` prevents the prompt from being processed and erases it from context; `reason` is shown to the user and not added to context; `suppressOriginalPrompt: true` omits the prompt text from that block message; `sessionTitle` sets the session title. Exit code 2 blocks the same way, showing stderr to the user. [DOC S743]
- Without a block, plain-text stdout on exit 0 or `hookSpecificOutput.additionalContext` is added to Claude's context as a system reminder starting with the hook's name; neither produces a visible transcript entry. [DOC S743]
- `UserPromptSubmit` `command`, `http` and `mcp_tool` hooks default to a 30-second timeout (600 s on most other events); on timeout the output, including `additionalContext`, is discarded and the prompt reaches Claude without it, while an Agent SDK callback hook that times out blocks the prompt instead. [DOC S743]
- `"async": true` (command hooks only) runs a hook in the background; async hooks cannot block or control Claude, so `decision`, `permissionDecision` and `continue` have no effect, and their output is delivered on the next conversation turn. [DOC S743]
- A hook that answers a prompt itself (block, answer in `reason`) spends no model tokens on that prompt: the prompt is erased from context and `reason` never enters it. This kb's `kb:` hook works this way. [DER S743: `decision`/`reason` semantics above; the kb hook is `_tools/kb_hook.py`]
- A query log can be built from hooks alone: `UserPromptSubmit` gives the question with `session_id` and `prompt_id`, and `Stop` gives `last_assistant_message` for the same session. A logging hook that must not delay the prompt fits `async: true`, but a hook that blocks or adds context cannot be async. [DER S743: input fields, `async` and decision rules above]

## Reference
| Event | MCP relevance | Replace data |
|---|---|---|
| PreToolUse | gate/rewrite call | `updatedInput` |
| PermissionRequest | answer permission dialog | decision object |
| PostToolUse | inspect/replace result | `updatedToolOutput` / `updatedMCPToolOutput` |
| PostToolUseFailure | error handling | - |
| Elicitation | auto-answer elicitation | `action`, `content` |
| ElicitationResult | override user answer | `action`, `content` |
| UserPromptSubmit | answer or gate a prompt before the model | `decision: "block"` + `reason`, `additionalContext` |

Related: `claude/plugins.md` — a plugin's `hooks/hooks.json` and manifest `hooks` key use this same event/matcher
shape and are merged together at load. `claude/settings-and-scopes.md` — `allowManagedHooksOnly`, `disableAllHooks`,
`allowedHttpHookUrls`, and the security-approval dialog required for a server-managed or MDM-delivered hook.
`claude/agent-sdk.md` — the Agent SDK runs this same hook engine (`options.hooks` callbacks plus settings-file
shell-command hooks) inside an embedded session; see its permission-callback (`can_use_tool`/`canUseTool`) example.

## Examples
- SNIPPET: a PostToolUse hook that runs a redaction command for every tool of one MCP server; context: Claude Code 2.1.281, settings.json `hooks` key; checked: syntax [DOC S743: matcher form `mcp__<server>__.*` matches all tools of a server, `hooks.PostToolUse[].hooks[].type: "command"`]
```json
{ "hooks": { "PostToolUse": [ { "matcher": "mcp__inventory__.*", "hooks": [ { "type": "command", "command": "inventory hook redact" } ] } ] } }
```
