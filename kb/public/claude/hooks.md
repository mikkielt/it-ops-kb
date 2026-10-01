---
topic: claude/hooks
priority: P1
applies_to: "Claude Code 2.1.281 docs (retrieved 2026-09-23; UserPromptSubmit, common input, async and Stop sections re-read 2026-09-27; SessionEnd and Windows command hooks read 2026-09-28; tool event input, Stop input and disableAllHooks read 2026-09-28; SessionStart, systemMessage and output caps read 2026-09-28; subagent input fields read 2026-09-28; subagent agent_type values and failure input re-read 2026-10-01)"
retrieved_utc: 2026-10-01
sources: [S743, S745, S746, S1800, S2157, S-h5sble4p, S-sjuwcuhk, S-3yod3u7q, S-av5665nf, S-uzkb4duq, S-npnkw4t2]
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
- Common input fields `agent_id` and `agent_type` identify a subagent: `agent_id` is present only when the hook fires inside a subagent call, which tells subagent calls from main-thread calls; `agent_type` is the agent name (e.g. `Explore`), present when the hook fires inside a subagent or the session uses `--agent`, and a subagent's type takes precedence over the session's `--agent` value. [DOC S743]
- Hooks from settings files, managed policy settings and plugins also run inside subagents: a subagent's tool calls fire the same configured `PreToolUse` and `PostToolUse` hooks as the main conversation, with `agent_id` and `agent_type` in their input. [DOC S743]
- `SubagentStart` hooks receive `agent_id` and `agent_type` (the name the matcher filters on) beyond the common input fields; `SessionStart` receives `agent_type` only when Claude Code was started with `claude --agent <name>`. [DOC S743]
- The `agent_type` value of a subagent is the built-in agent's name (`general-purpose`, `Explore`, `Plan`) or, for a custom subagent, the `name` field of its frontmatter, not its filename; for a subagent shipped by a plugin it is the plugin-scoped id such as `my-plugin:reviewer`, not the bare name. The colon puts that name on the matcher's regular-expression path, so an exact `SubagentStart` or `SubagentStop` matcher is anchored: `^my-plugin:reviewer$`. [DOC S743]
- In the Agent SDK's callback hooks, `agent_id` and `agent_type` are set when the hook fires inside a subagent: on the base hook input for every event in TypeScript; in Python, optional on `PreToolUse`, `PostToolUse`, `PostToolUseFailure` and `PermissionRequest` and required on `SubagentStart` and `SubagentStop`. [DOC S-av5665nf]
- `transcript_path` is written asynchronously and may not yet hold the current turn's latest messages when a hook fires; `Stop` and `SubagentStop` hooks receive `last_assistant_message` (Claude's final response text) for that purpose. [DOC S743]
- `CLAUDE_CODE_SESSION_ID` is set automatically to the current session id in Bash and PowerShell tool subprocesses, hook command subprocesses and stdio MCP server subprocesses; for Bash, PowerShell and hooks it matches the hook input `session_id` and is updated on `/clear`, while an MCP server keeps the id it was spawned with (with `--continue` or `--resume` without an id it may get the initial startup id). [DOC S745]
- A Bash command sees the session id through `CLAUDE_CODE_SESSION_ID`, but the docs list no environment variable for a subagent's id: `agent_id` and `agent_type` are hook input fields, so attributing a subagent's tool call to the subagent goes through `PreToolUse`/`PostToolUse` hook input, not the shell. [DER S743, S745: `agent_id` appears only in hook input, no such variable in the environment-variable list]
- `CLAUDE_CODE_CHILD_SESSION=1` is set in subprocesses Claude Code spawns through the Bash, PowerShell and Monitor tools, hook commands and status line commands (not stdio MCP servers), so a nested `claude` run from a script can tell it was launched by another session; `CLAUDE_CODE_BRIDGE_SESSION_ID` (v2.1.199+) holds the Remote Control session id in `session_` form only while that connection is active. [DOC S745]
- `SubagentStart` fires when Claude spawns a subagent with the Agent tool, when it resumes a subagent, and each time an in-process agent-team teammate handles a new message, so one subagent can produce several `SubagentStart` events for the same `agent_id`; its example input has `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `agent_id` (like `agent-abc123`) and `agent_type`, no `permission_mode`. [DOC S743]
- `SubagentStop` input adds `stop_hook_active`, `agent_id`, `agent_type`, `agent_transcript_path` and `last_assistant_message`, and the `background_tasks` and `session_crons` arrays scoped to the parent session; `transcript_path` stays the main session's transcript while `agent_transcript_path` is the subagent's own file in a nested `subagents/` folder (example `.../<session-id>/subagents/agent-<agent-id>.jsonl`). [DOC S743]
- `SubagentStop` also fires when one of Claude Code's own internal agents finishes (prompt suggestions, `/btw` side questions); for those `agent_type` is the agent the session itself runs as (`--agent` or the `agent` setting) or an empty string, and a matcher naming agent types does not match the empty string, while an omitted, `""` or `"*"` matcher does. [DOC S743]
- Subagent transcripts are files `~/.claude/projects/{project}/{sessionId}/subagents/agent-{agentId}.jsonl`; they persist independently of the main conversation (unaffected by its compaction, kept for the session) and are deleted after `cleanupPeriodDays` (30 days by default); a compaction in one is logged as a `type: "system"`, `subtype: "compact_boundary"` entry with `compactMetadata.trigger` and `compactMetadata.preTokens`. [DOC S2157]
- Main transcripts are JSONL files `~/.claude/projects/<project>/<session-id>.jsonl` (`<project>` is the working directory path with non-alphanumeric characters replaced by `-`, truncated to 200 characters plus a hash when longer); each line is a message, tool use or metadata entry, and the entry format is internal to Claude Code and changes between versions, so a script that parses it can break on any release (the docs point to `/export` and the script interfaces instead). [DOC S-uzkb4duq]
- `PostToolBatch` hooks receive `tool_calls`, an array with one object per tool call of the batch, each holding `tool_name`, `tool_input`, `tool_use_id` and `tool_response`; `tool_response` is the same serialized `tool_result` content the model receives (for `Read` the line-numbered text), unlike `PostToolUse`, which passes the tool's structured output object, and can be large. [DOC S743]
- The sessions page lists the interfaces that give a script structured session data: `claude -p` with `--output-format json` or `stream-json` (result, session id, usage, cost), `claude -p --resume <session-id>`, the `transcript_path` field that hooks and status line commands receive, and the Agent SDK; it prefers them over parsing transcript files, whose entry format it calls internal. [DOC S-uzkb4duq]
- `CLAUDE_ENV_FILE` is available only to `SessionStart`, `Setup`, `CwdChanged` and `FileChanged` hooks: exports appended to it persist into later Bash commands; other hook types have no such variable. [DOC S743]
- `UserPromptSubmit` output: `decision: "block"` prevents the prompt from being processed and erases it from context; `reason` is shown to the user and not added to context; `suppressOriginalPrompt: true` omits the prompt text from that block message; `sessionTitle` sets the session title. Exit code 2 blocks the same way, showing stderr to the user. [DOC S743]
- Without a block, plain-text stdout on exit 0 or `hookSpecificOutput.additionalContext` is added to Claude's context as a system reminder starting with the hook's name; neither produces a visible transcript entry. [DOC S743]
- `UserPromptSubmit` `command`, `http` and `mcp_tool` hooks default to a 30-second timeout (600 s on most other events); on timeout the output, including `additionalContext`, is discarded and the prompt reaches Claude without it, while an Agent SDK callback hook that times out blocks the prompt instead. [DOC S743]
- `"async": true` (command hooks only) runs a hook in the background; async hooks cannot block or control Claude, so `decision`, `permissionDecision` and `continue` have no effect, and their output is delivered on the next conversation turn. [DOC S743]
- A hook that answers a prompt itself (block, answer in `reason`) spends no model tokens on that prompt: the prompt is erased from context and `reason` never enters it. This kb's `kb:` hook works this way. [DER S743: `decision`/`reason` semantics above; the kb hook is `_tools/kb_hook.py`]
- A query log can be built from hooks alone: `UserPromptSubmit` gives the question with `session_id` and `prompt_id`, and `Stop` gives `last_assistant_message` for the same session. A logging hook that must not delay the prompt fits `async: true`, but a hook that blocks or adds context cannot be async. [DER S743: input fields, `async` and decision rules above]
- `SessionEnd` hooks (input field `reason`: `clear`, `resume`, `logout`, `prompt_input_exit`, `other`) have no decision control and cannot block termination; Claude Code discards their JSON output fields such as `systemMessage`. [DOC S743]
- `SessionEnd` hooks share a 1.5-second budget on exit, `/clear` and interactive `/resume`. A per-hook `timeout` raises the budget to the highest such value in settings files, up to 60 seconds, but timeouts on plugin-provided hooks do not raise it; `CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS` sets the budget explicitly and, since v2.1.268, also the timeout of each hook without its own. [DOC S743]
- On a `claude -p` run stopped by SIGTERM, only `SessionEnd` hooks still run before exit (`claude/ci-and-headless.md`). [DOC S1800]
- A `SessionEnd` hook that must do more than about a second of work (a batch job, a network push) fits only as a launcher that starts a detached process and returns; from a plugin it cannot win more time with `timeout`, and an environment variable is a per-user setting, not something a repository can ship. [DER S743: the 1.5-second shared budget, the plugin exception and the variable above]

### SessionStart, and what reaches the user
- `SessionStart` runs when Claude Code starts or resumes a session (matchers `startup`, `resume`, `clear`, `compact`, `fork`); it runs on every session, so its hooks should stay fast, and only `command` and `mcp_tool` hooks are supported. [DOC S743]
- At an interactive start, a `--continue` or `--resume` launch or `/clear`, `SessionStart` hooks run in the background: the user can type at once, but Claude's first response waits for the hooks to finish. [DOC S743]
- `SessionStart` plain-text stdout is added to Claude's context, and `hookSpecificOutput.additionalContext` is added before the first prompt. [DOC S743]
- The universal JSON output field `systemMessage` is a warning message shown to the user; some events discard it or deliver it elsewhere (`SessionEnd` discards it). [DOC S743]
- After an async hook's process exits, its `additionalContext` and `systemMessage` are delivered to Claude on the next conversation turn and, unlike a synchronous hook's `systemMessage`, neither is shown to the user. [DOC S743]
- A hook's `additionalContext`, `systemMessage` and plain stdout are each capped at 10,000 characters; longer output is saved to a file and replaced by its path and a preview of the first 2,000 characters. [DOC S743]
- A command hook's `timeout` defaults to 600 seconds on `SessionStart` (the default for most events), and a hook canceled at its timeout has its output discarded. [DOC S743]
- A message a hook must show the person, not Claude, comes from a synchronous `SessionStart` command hook that prints a JSON object with `systemMessage` only: an async hook's `systemMessage` and any plain stdout reach Claude instead. Such a hook stays short and sets its own `timeout`, since Claude's first response waits for it. [DER S743: `systemMessage`, async delivery, SessionStart stdout and waiting above]

### Tool event input
- `PreToolUse` hooks receive `tool_name`, `tool_input` and `tool_use_id` beyond the common input fields; `PostToolUse` fires only after a tool executed successfully and its input holds `tool_input` (the arguments sent) and `tool_response` (the result returned), whose schema depends on the tool, plus an optional `duration_ms`. [DOC S743]
- `PostToolUseFailure` hooks receive the same `tool_name` and `tool_input` as `PostToolUse`, with a top-level `error` string (its format varies by tool; generally the text Claude receives) and optional `is_interrupt` and `duration_ms`; it does not fire for calls rejected by validation or a permission denial. [DOC S743]
- `PostToolUse` fires only after a tool executed successfully; `PostToolUseFailure` fires when a tool that started executing fails (it threw, or an MCP tool returned an error result). For Bash and PowerShell a command that ran and exited non-zero fires `PostToolUseFailure`, not `PostToolUse`: the docs' example is a failed `npm test` whose `error` is `"Exit code 1\nError: ..."`, so the first line `Exit code N` carries the exit status and the rest is stdout and stderr interleaved. [DOC S743]
- A `PostToolUseFailure` `error` can also be a bare message with no exit-code line (the shell process could not start) or carry lines Claude Code inserts, such as `Command timed out after 2m 0s`; long strings are middle-truncated around `... [N characters truncated] ...`. The docs advise keying on `tool_name`, `is_interrupt` and the `Exit code N` first line and treating the rest as display text; cancelling a running tool does not fire the hook, and `duration_ms` excludes permission prompts and `PreToolUse` hooks. [DOC S743]
- `tool_input` by tool: Bash and PowerShell `command`, `description`, `timeout`, `run_in_background`; WebFetch `url` and `prompt`; WebSearch `query` and optional `allowed_domains`, `blocked_domains`. [DOC S743]
- On Windows where the PowerShell tool is enabled, Claude routes shell commands through it, and without Git Bash the Bash tool is not registered at all, so a hook that inspects shell commands matches `Bash|PowerShell`. [DOC S743]
- WebFetch converts an HTML page to Markdown and runs its prompt on it with a small, fast model, so Claude usually receives that model's answer, not the page; large pages are truncated first, and a redirect to a different host returns a text result naming the original URL and the target instead of following it. [DOC S-3yod3u7q]
- `Stop` hooks receive `stop_hook_active`, `last_assistant_message`, `background_tasks` and `session_crons` beyond the common input fields. [DOC S743]
- `--settings '{"disableAllHooks": true}'` turns hooks off for one run and takes precedence over project and local settings; `disableAllHooks` outside managed settings cannot disable managed hooks. [DOC S743]
- A logging hook on `PostToolUse` and `Stop` joins its rows to the prompt by `prompt_id`, a common input field, and a fetch's outcome needs `PostToolUseFailure` as well, since `PostToolUse` sees only successful calls. [DER S743: common input fields, PostToolUse and PostToolUseFailure input above]

### Reading a Bash command in a hook script
- `shlex.split(s)` splits a string with shell-like quoting in POSIX mode by default and leaves comments in place (`comments=False`); passing `None` raises an exception since Python 3.12 instead of reading stdin. [DOC S-npnkw4t2]
- `shlex.shlex(text, posix=True, punctuation_chars=True)` returns each run of the characters `();<>|&` as its own token, so `a && b; c` yields `a`, `&&`, `b`, `;`, `c`; without `punctuation_chars` a word such as `b;` stays one token. [DOC S-npnkw4t2]
- The `shlex` page calls its parsing short of a full shell parser and says the tokens returned may be invalid for shells, so the caller does its own checks; `punctuation_chars` also lets `~-./*?=` stay inside words, which keeps a path such as `kb/public/claude/hooks.md` one token. [DOC S-npnkw4t2]
- The `shlex` page names no exception for an unclosed quote (run locally, `shlex.split("cat 'a")` raises `ValueError`), so a hook that parses `tool_input.command` catches `ValueError` and prints nothing instead of failing; a `PreToolUse` hook that exits 0 with no output adds nothing. [UNK]
- A `PreToolUse` hook that only adds context for `cat`, `sed`, `head`, `tail` or `grep` on a path can split the command with `punctuation_chars=True` into segments at `|`, `;`, `&&` and `||`, take the first token of each segment as the command name and test its later tokens against the path pattern; it does not need to resolve `$(...)` or variables, since a miss only loses a hint. [DER S-npnkw4t2, S743: tokens per segment; `additionalContext` reaches Claude without blocking]

### Command hooks on Windows
- A command hook runs in exec form when `args` is set: `command` is resolved as an executable on `PATH` and spawned with `args` as the argument vector, with no shell and no tokenization on any platform. [DOC S743]
- Without `args` a command hook runs in shell form: the `command` string goes to `sh -c` on macOS and Linux, to Git Bash on Windows, or to PowerShell when Git Bash is not installed. [DOC S743]
- The command hook field `shell` accepts `"bash"` or `"powershell"`; it defaults to `"bash"`, or to `"powershell"` on Windows without Git Bash, and is ignored when `args` is set. [DOC S743]
- On Windows, exec form needs `command` to resolve to a real executable such as a `.exe`; `.cmd` and `.bat` shims cannot be spawned without a shell, so run them in shell form. [DOC S743]
- Both forms substitute the path placeholders and export `CLAUDE_PROJECT_DIR`, `CLAUDE_PLUGIN_ROOT` and `CLAUDE_PLUGIN_DATA` to the hook process; in shell form each placeholder should be wrapped in double quotes. [DOC S743]
- In a PowerShell shell-form hook, `${CLAUDE_PROJECT_DIR}` (rewritten to `${env:NAME}` since v2.1.198) or `$env:CLAUDE_PROJECT_DIR` works; the bare `$CLAUDE_PROJECT_DIR` resolves to `$null` there. [DOC S743]
- On macOS and Linux, command hooks run in their own session without a controlling terminal; Windows has no `/dev/tty`. [DOC S743]
- Git for Windows is optional for native Windows Claude Code; with it, Claude Code uses Git Bash for the Bash tool (`CLAUDE_CODE_GIT_BASH_PATH` names `bash.exe` when it is not found), and without it shell commands go through the PowerShell tool. [DOC S-h5sble4p]
- A hook command that must run on every OS cannot rely on one interpreter name in exec form: on Windows the name must be a real `.exe` on `PATH`, and `python3` is only a compatibility alias there (`python/stdlib-windows-portability.md`). Shell form reaches a POSIX shell on macOS, Linux and Windows with Git Bash, where a small launcher can try `python3`, `python` and `py -3` in turn; without Git Bash the command reaches PowerShell instead. [DER S743, S-h5sble4p, S-sjuwcuhk: shell-form shells and the exec-form `.exe` rule above; the `python3` alias in the Python docs]

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

Related: `claude/powershell-tool.md` — the PowerShell tool, its `PowerShell(...)` permission rules and skill `shell: powershell`. `claude/plugins.md` — a plugin's `hooks/hooks.json` and manifest `hooks` key use this same event/matcher
shape and are merged together at load. `claude/settings-and-scopes.md` — `allowManagedHooksOnly`, `disableAllHooks`,
`allowedHttpHookUrls`, and the security-approval dialog required for a server-managed or MDM-delivered hook.
`claude/agent-sdk.md` — the Agent SDK runs this same hook engine (`options.hooks` callbacks plus settings-file
shell-command hooks) inside an embedded session; see its permission-callback (`can_use_tool`/`canUseTool`) example.

## Examples
- SNIPPET: a PostToolUse hook that runs a redaction command for every tool of one MCP server; context: Claude Code 2.1.281, settings.json `hooks` key; checked: syntax [DOC S743: matcher form `mcp__<server>__.*` matches all tools of a server, `hooks.PostToolUse[].hooks[].type: "command"`]
```json
{ "hooks": { "PostToolUse": [ { "matcher": "mcp__inventory__.*", "hooks": [ { "type": "command", "command": "inventory hook redact" } ] } ] } }
```
