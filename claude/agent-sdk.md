---
topic: claude/agent-sdk
priority: P2
applies_to: "Claude Agent SDK (Python claude-agent-sdk, TypeScript @anthropic-ai/claude-agent-sdk); code.claude.com docs retrieved 2026-09-26"
retrieved_utc: 2026-09-26
sources: [S-22nastju, S-fksbud2r, S-fmj24q2u, S-rjw74jiz, S-pbd7pui3, S-isqfh6pr, S-gztpah4d, S-llf2m5cf, S-5be7mkzk, S-av5665nf]
status: complete
files: [claude/agent-sdk-options.csv]
---

# Agent SDK: building agents on the Claude Code engine

## Summary
The Agent SDK (Python `claude-agent-sdk`, TypeScript `@anthropic-ai/claude-agent-sdk`, renamed from the
Claude Code SDK at v0.1.0) embeds the Claude Code binary as a library: same agent loop, tools, permissions,
hooks, sessions, skills, and plugins as the CLI, driven from your own process. Python offers `query()`
(new session per call) and `ClaudeSDKClient` (persistent, interruptible session); TypeScript's `query()`
plays both roles and adds `startup()`/`prewarm()` to pay subprocess-spawn cost early. Tool permission is a
six-step pipeline (hooks -> deny rules -> ask rules -> permission mode -> allow rules -> `canUseTool`
callback); in-process MCP servers let Python/TypeScript functions become Claude tools with no subprocess.
Cost fields (`total_cost_usd`, `ResultMessage.usage`/`modelUsage`) are client-side estimates from a bundled
price table, not billing data. The SDK spawns one CLI subprocess per session, owning a shell, working
directory, and local session transcripts.

## Facts

### query() vs ClaudeSDKClient / core functions
- Python `query()` creates a new session per call by default, returns `AsyncIterator[Message]`, supports streaming input and hooks and custom tools, but not interrupts; use `continue_conversation=True` or `resume` for continuity. [DOC S-fksbud2r]
- Python `ClaudeSDKClient` reuses the same session across multiple exchanges, supports `interrupt()`, `set_permission_mode()`, `set_model()`, `rewind_files()`, `get_mcp_status()`, `reconnect_mcp_server()`, `toggle_mcp_server()`, `stop_task()`, and works as an async context manager. [DOC S-fksbud2r]
- TypeScript `query()` returns a `Query` object extending `AsyncGenerator<SDKMessage, void>` with extra methods (e.g. `setPermissionMode`); it plays the role of both Python functions. [DOC S-fmj24q2u]
- TypeScript `startup({options, initializeTimeoutMs})` (default timeout 60000 ms) pre-warms the CLI subprocess and returns a `WarmQuery` whose `.query(prompt)` then resolves immediately. [DOC S-fmj24q2u]
- TypeScript `prewarm()` (alpha, SDK v0.3.282+) starts an unbound spare process before a session's working directory is known; `claim()` binds it later. A spare holds roughly 230-260 MB of memory while waiting; `prewarm()` throws if `options` sets `resume`, `continue`, or `forkSession`. [DOC S-fmj24q2u]
- Import from either the package root or the `/core` entry (TS SDK v0.3.282+, needs TypeScript 5.0+) in one process, not both — they are separate bundles and loading both duplicates the SDK's classes and state. `/core` omits `prewarm()`, `InMemorySessionStore`, and the session list/read/fork/import/summarize helpers. [DOC S-fmj24q2u]
- `ClaudeAgentOptions`/`ClaudeCodeOptions` was renamed `ClaudeAgentOptions` in the Python SDK at Agent SDK v0.1.0, matching the package rename `claude-code-sdk` -> `claude-agent-sdk` (`claude_code_sdk` -> `claude_agent_sdk` import path) and TS `@anthropic-ai/claude-code` -> `@anthropic-ai/claude-agent-sdk`. [DOC S-llf2m5cf]
- Since v0.1.0 the SDK no longer defaults to Claude Code's own system prompt (a minimal prompt is used instead); pass `system_prompt={"type":"preset","preset":"claude_code"}` (or `systemPrompt: {type:"preset", preset:"claude_code"}`) to restore it. [DOC S-llf2m5cf]

### ClaudeAgentOptions / Options fields
- Full Python `ClaudeAgentOptions` field table (name, type, default, effect) is in `claude/agent-sdk-options.csv`, with the TypeScript `Options` equivalent name in the same row where documented. [DOC S-fksbud2r]
- `allowed_tools` does not restrict Claude to only the listed tools — unlisted tools remain available and fall through to `permission_mode`/`canUseTool`; use `disallowed_tools` to actually remove a tool. [DOC S-fksbud2r,S-rjw74jiz]
- `disallowed_tools=["Bash"]` removes the tool definition from the request entirely (Claude cannot attempt it); `disallowed_tools=["Bash(rm *)"]` leaves `Bash` available and denies matching calls in every permission mode including `bypassPermissions`, for the command as written. `disallowed_tools=["*"]` removes every tool; `"mcp__*"` removes every MCP tool. [DOC S-rjw74jiz]
- Allow-rule tool-name globs are accepted only after a literal `mcp__<server>__` prefix (e.g. `mcp__puppeteer__*`); an unanchored `allowed_tools=["*"]` or `["mcp__*"]` is ignored with a startup warning and approves nothing. [DOC S-rjw74jiz]
- `setting_sources`/`settingSources` defaults to loading all filesystem sources (user/project/local); pass `[]` to disable all three. If `skills` is set and `setting_sources` is left unset, only user and project sources load — set `setting_sources` explicitly to keep local settings too. Endpoint-managed policy and server-managed settings load regardless of this option. [DOC S-fksbud2r]
- `skills` set to a list of exact names, or the literal string `"all"`; malformed or wildcard-form names raise `ValueError` before the CLI process starts (Python SDK 0.2.129+); setting `skills` auto-adds the `Skill` tool to `allowed_tools`. [DOC S-fksbud2r]
- `max_budget_usd`/`maxBudgetUsd` stops the query once the client-side cost estimate reaches the USD value; it counts only that call's own spend (a resumed session's restored total doesn't count), and a `/clear` restarts the budget. [DOC S-fksbud2r,S-isqfh6pr]
- Session mutation helpers exist standalone and independent of a live query: `list_sessions()`/`listSessions()`, `get_session_messages()`/`getSessionMessages()`, `get_session_info()`/`getSessionInfo()`, `rename_session()`/`renameSession()`, `tag_session()`/`tagSession()` — all synchronous in Python, Promise-returning in TypeScript. [DOC S-fksbud2r,S-fmj24q2u]
- TypeScript `resolveSettings()` (alpha) resolves effective settings for a directory using the CLI's own merge engine without spawning the CLI; it reads MDM sources (macOS plist, Windows HKLM/HKCU) but does not execute an admin-configured `policyHelper` subprocess, and does not fetch server-managed settings unless passed via `options.serverManagedSettings`. [DOC S-fmj24q2u]

### In-process (SDK) MCP servers and custom tools
- `tool(name, description, input_schema, annotations=None)` (Python decorator) or `tool(name, description, inputSchema, handler, extras?)` (TypeScript, Zod schema) define a type-safe MCP tool; `input_schema` accepts a simple `{"text": str}` mapping or full JSON Schema in Python, a Zod raw shape in TypeScript. [DOC S-fksbud2r,S-fmj24q2u]
- `create_sdk_mcp_server(name, version="1.0.0", tools=None)` (Python) / `createSdkMcpServer({name, version?, instructions?, tools?, alwaysLoad?, timeout?})` (TypeScript) creates an in-process MCP server that runs inside the SDK application's own process (no subprocess, no network hop); the returned config is passed to `ClaudeAgentOptions.mcp_servers`/`options.mcpServers`. [DOC S-fksbud2r,S-fmj24q2u]
- `ToolAnnotations` extends `mcp.types.ToolAnnotations` with `maxResultSizeChars` (int, up to 500,000; a Claude Code-specific setting sent in the tool's `_meta` as `anthropic/maxResultSizeChars`, not a standard MCP hint), plus `readOnlyHint` (default False), `destructiveHint` (default True), `idempotentHint` (default False), `openWorldHint` (default True). Python snake_case annotation fields require Python Agent SDK 0.2.140+. [DOC S-fksbud2r]
- TypeScript `createSdkMcpServer({..., timeout})`: overrides `MCP_TOOL_TIMEOUT` for that server's tool calls; must be a whole number >= 1000 ms; requires TypeScript Agent SDK v0.3.248+. `alwaysLoad: true` (server- or tool-level) keeps a tool's full schema in the initial prompt instead of deferring it behind tool search. [DOC S-fmj24q2u]
- An MCP quickstart connects an external HTTP MCP server (e.g. `https://code.claude.com/docs/mcp`) via `mcp_servers`/`mcpServers` plus `allowed_tools=["mcp__claude-code-docs__*"]`/`allowedTools`. [DOC S-5be7mkzk]

### Permission model: modes, rules, canUseTool
- Six-step evaluation order for every tool request: (1) hooks -> (2) deny rules (`disallowed_tools`/settings.json) -> (3) ask rules (settings.json) -> (4) active permission mode -> (5) allow rules (`allowed_tools`/settings.json) -> (6) `canUseTool` callback. A hook `allow` does not skip steps 2-3; deny rules block even in `bypassPermissions`. [DOC S-rjw74jiz]
- Permission modes: `default` (no mode auto-approvals), `dontAsk` (deny instead of prompting; `canUseTool` never called), `acceptEdits` (auto-approve file edits and filesystem ops `mkdir`/`touch`/`rm`/`rmdir`/`mv`/`cp`/`sed` inside the working directory/`additionalDirectories`), `bypassPermissions` (approve everything reaching this step except critical-path `rm`/`rmdir`; refuses to start as root/sudo outside a recognized sandbox on Linux/macOS), `plan` (file edits never auto-approved, sent to `canUseTool`; on Claude Code v2.1.212+ file-modifying shell commands like `touch`/`rm` also route to `canUseTool`), `auto` (a model classifier approves/denies prompts). [DOC S-rjw74jiz]
- `canUseTool`/`can_use_tool` is invoked only when the six-step flow falls through to a prompt; it is never called for calls auto-approved by `allowed_tools`, allow rules, or the active permission mode. In `dontAsk` mode the callback step is skipped entirely. [DOC S-fksbud2r,S-pbd7pui3]
- Callback signature: Python `async def can_use_tool(tool_name: str, input_data: dict, context: ToolPermissionContext) -> PermissionResultAllow | PermissionResultDeny`; TypeScript `async (toolName, input, {signal, suggestions}) => {behavior:"allow", updatedInput} | {behavior:"deny", message}`. [DOC S-pbd7pui3]
- `PermissionResultAllow(updated_input=...)` / `{behavior:"allow", updatedInput}` lets the tool run with a possibly-modified input; before Claude Code v2.1.207 an allow result omitting `updatedInput` was rejected with a validation error. `PermissionResultDeny(message=...)` / `{behavior:"deny", message}` blocks the call and shows Claude the reason. [DOC S-pbd7pui3]
- The callback's third argument carries `suggestions`, ready-made `PermissionUpdate` entries; echoing one with `destination: "localSettings"` back as `updated_permissions`/`updatedPermissions` persists an allow rule to `.claude/settings.local.json` so future matching calls skip the prompt (Python requires claude-agent-sdk 0.1.80+). [DOC S-pbd7pui3]
- Subagent inheritance: a subagent runs in the parent session's permission mode unless its `AgentDefinition` sets `permissionMode` and the parent is in `default`/`dontAsk`/`plan`; Claude Code never applies a `bypassPermissions` value to a subagent unless the parent session itself runs in `bypassPermissions` (requires Claude Code v2.1.267+ for that exception). [DOC S-rjw74jiz]
- `AskUserQuestion` also triggers `canUseTool` (clarifying questions, common in `plan` mode); its input has a `questions` array of `{question, header (<=12 chars), options[2-4] with label/description, multiSelect}`; the response is `{questions, answers: {question_text: label_or_labels}, response?}`. [DOC S-pbd7pui3]

### Message types and cost tracking
- Python `ResultMessage` (dataclass) fields include `subtype`, `duration_ms`, `duration_api_ms`, `total_cost_usd: float | None`, `usage: dict[str, Any] | None`, `result: str | None`, `structured_output`, `terminal_reason` (e.g. `completed`, `max_turns`, `api_error`, `aborted_streaming`, `aborted_tools`), and `origin`. [DOC S-fksbud2r]
- `total_cost_usd`/`costUSD` are client-side estimates from a price table bundled at build time (or a `modelPricing` managed-settings table); they are not authoritative billing data and can drift on pricing changes, an unrecognized model, or unmodeled billing rules. Use the Usage and Cost API or Console for real billing. [DOC S-isqfh6pr]
- `usage` on the result message covers only the top-level main agent loop and excludes subagent token spend; `total_cost_usd` and `model_usage`/`modelUsage` include subagent requests. Prefer `model_usage`/`modelUsage` for whole-tree accounting. [DOC S-isqfh6pr]
- In streaming input mode, one `query()` call emits one `ResultMessage` per turn; `total_cost_usd` and `model_usage` are cumulative for the call so far (reset only by `/clear`, `/reset`, or `/new`) — read the latest result rather than summing across results. [DOC S-isqfh6pr]
- A crashed session emits a final `error_during_execution` result whose cost fields may be zeroed; recover totals from the previous turn's result, or by summing assistant-message `usage` (main loop input/cache tokens only; output tokens and subagent spend aren't recoverable that way). [DOC S-isqfh6pr]
- Per-step assistant-message `output_tokens` is a placeholder captured at `message_start`, before generation finished; read the real output count from the result message's `usage`, or per-model from `model_usage`/`modelUsage`. [DOC S-isqfh6pr]
- Prompt caching is automatic; cache writes default to a 5-minute TTL when authenticating via API key, Bedrock, Vertex, Foundry, or Claude Platform on AWS. Set `ENABLE_PROMPT_CACHING_1H` (env var, can be passed via `options.env`) for a 1-hour TTL on both the main conversation and other requests, or use `CLAUDE_CODE_PROMPT_CACHE_TTL` / `CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL` (`5m`|`1h`) to set each bucket independently (these take precedence over `ENABLE_PROMPT_CACHING_1H`). [DOC S-isqfh6pr]

### Hosting and process model
- The SDK spawns and supervises a `claude` CLI subprocess per session over stdio; the subprocess owns the shell, working directory, and JSONL session transcripts on local disk. N concurrent sessions means N subprocesses; give each a distinct `cwd` for filesystem isolation. [DOC S-gztpah4d]
- None of a subprocess's local-disk state (session transcripts under `~/.claude/projects/` or `CLAUDE_CONFIG_DIR`, `CLAUDE.md`, working-directory artifacts) survives a container restart, scale-down, or node move; persist transcripts via a `SessionStore` adapter and use a mounted volume or object-store sync for the rest. [DOC S-gztpah4d]
- Four session lifecycle patterns for containerized hosting: ephemeral (one container per task, destroyed on completion; e.g. bug fix, invoice extraction), and others covered in the hosting cookbook (Docker, Modal, Kubernetes manifests). [DOC S-gztpah4d]
- If a package manager skips the platform-specific optional dependency (bundled native `claude` binary, e.g. `@anthropic-ai/claude-agent-sdk-darwin-arm64`), the SDK throws `Native CLI binary for <platform>-<arch> not found`; set `pathToClaudeCodeExecutable` to a separately installed `claude` binary as a workaround. [DOC S-fmj24q2u]
- Compiling to a single executable (`bun build --compile`) breaks the bundled-binary lookup (`require.resolve` fails inside `$bunfs`); embed the platform binary as a file asset and extract it at startup with `extractFromBunfs()` (SDK v0.3.144+), passing the extracted path to `pathToClaudeCodeExecutable`. [DOC S-fmj24q2u]

### Sessions, hooks (cross-reference)
- Hooks fire via `options.hooks` callbacks plus shell-command hooks from settings files (when the matching `setting_sources`/`settingSources` entry is enabled — the default for `query()`); a `matcher` pattern (e.g. `"Write|Edit"`) filters which hooks run per event; hooks unmatched run for every event of that type. [DOC S-av5665nf]
- See `claude/hooks.md` for the MCP-tool-specific hook mechanics (`PreToolUse`/`PostToolUse` on `mcp__<server>__<tool>` names, `updatedInput`/`updatedToolOutput`) — those apply the same way inside Agent SDK sessions since the SDK runs the same hook engine as the CLI. [DER S-av5665nf: hooks.mdx describes the same event/matcher/callback model documented for the CLI in claude/hooks.md, applied to SDK-embedded sessions]

### Authentication
- Anthropic does not allow third-party Agent SDK products to offer claude.ai login or its rate limits; use the API key authentication methods instead. [DOC S-22nastju]
- Authentication reuses the same CLI provider environment variables documented in `claude/env-vars.csv`: `ANTHROPIC_API_KEY` (X-Api-Key), `CLAUDE_CODE_USE_BEDROCK`/`CLAUDE_CODE_USE_VERTEX`/`CLAUDE_CODE_USE_FOUNDRY`/`CLAUDE_CODE_USE_ANTHROPIC_AWS` to route to Bedrock/Vertex/Foundry/Claude Platform on AWS, and `CLAUDE_CODE_OAUTH_TOKEN` for a long-lived subscription token. [DER claude/env-vars.csv: same env-var mechanism the CLI uses, applied to an Agent SDK-spawned subprocess]
- Passing provider env vars through `ClaudeAgentOptions.env`/`options.env` (e.g. `{"CLAUDE_CODE_USE_BEDROCK": "1", "ENABLE_PROMPT_CACHING_1H": "1"}`) merges them on top of the inherited process environment for that session. [DOC S-fksbud2r,S-isqfh6pr]

## Examples

### In-process SDK MCP tool (Python)
```python
import asyncio
from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    create_sdk_mcp_server,
    query,
    tool,
)


@tool("lookup_asset_owner", "Look up the assigned owner for an asset tag", {"asset_tag": str})
async def lookup_asset_owner(args: dict) -> dict:
    # placeholder lookup against an internal inventory system
    owners = {"PL-LT-00123": "jan.kowalski"}
    owner = owners.get(args["asset_tag"], "unknown")
    return {"content": [{"type": "text", "text": f"Owner: {owner}"}]}


inventory_server = create_sdk_mcp_server(
    name="inventory",
    version="1.0.0",
    tools=[lookup_asset_owner],
)


async def main():
    options = ClaudeAgentOptions(
        mcp_servers={"inventory": inventory_server},
        allowed_tools=["mcp__inventory__lookup_asset_owner"],
    )
    async for message in query(
        prompt="Who owns asset PL-LT-00123?",
        options=options,
    ):
        if isinstance(message, ResultMessage) and message.subtype == "success":
            print(message.result)


asyncio.run(main())
```

### Permission callback (Python) gating a headless run
```python
import asyncio
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from claude_agent_sdk.types import PermissionResultAllow, PermissionResultDeny


async def can_use_tool(tool_name: str, input_data: dict, context) -> (
    PermissionResultAllow | PermissionResultDeny
):
    # Auto-approve read-only lookups; deny anything else without prompting
    # (used for a scheduled agent against corp.example.com with nobody to ask)
    if tool_name in ("Read", "Grep", "Glob"):
        return PermissionResultAllow(updated_input=input_data)
    return PermissionResultDeny(message="Unattended run: only read-only tools are approved")


async def main():
    options = ClaudeAgentOptions(
        cwd="/work/session-a",
        allowed_tools=["Read", "Grep", "Glob"],
        can_use_tool=can_use_tool,
        max_budget_usd=2.0,
    )
    async for message in query(
        prompt="Summarize configuration drift under corp.example.com/inventory",
        options=options,
    ):
        if isinstance(message, ResultMessage):
            print(message.subtype, message.total_cost_usd)


asyncio.run(main())
```

## Reference
| Aspect | Python | TypeScript |
|---|---|---|
| Package | `claude-agent-sdk` (was `claude-code-sdk`) | `@anthropic-ai/claude-agent-sdk` (was `@anthropic-ai/claude-code`) |
| One-off call | `query()` | `query()` |
| Persistent session | `ClaudeSDKClient` | `query()`'s returned `Query` object |
| Options type | `ClaudeAgentOptions` (was `ClaudeCodeOptions`) | `Options` |
| Options field table | see `claude/agent-sdk-options.csv` | see `claude/agent-sdk-options.csv` |
| Define a custom tool | `@tool(name, description, input_schema)` | `tool(name, description, inputSchema, handler)` |
| In-process MCP server | `create_sdk_mcp_server()` | `createSdkMcpServer()` |
| Cost/usage on completion | `ResultMessage.total_cost_usd` / `.usage` / `.model_usage` | `SDKResultMessage.total_cost_usd` / `.usage` / `.modelUsage` |

See also: `claude/settings-and-scopes.md` (settings file precedence and `setting_sources` interaction, CLAUDE.md, managed settings that apply to SDK sessions the same as the CLI), `claude/hooks.md` (MCP-tool hook event fields, `PreToolUse`/`PostToolUse` mechanics shared with the SDK's hook engine), `agents/headless-agent-runtimes.md` (`claude -p` as the cross-language equivalent of the SDK for languages other than Python/TypeScript, and unattended-run permission/cost controls such as `--permission-prompts none` and `--max-budget-usd` that mirror `permission_mode`/`max_budget_usd` here), `claude/env-vars.csv` (full provider auth and proxy/CA environment variable list), `claude/agent-cost-governance.md` (organization-wide `modelPricing` and subagent cost governance).

## Open UNKs
- None recorded for this article; all facts above trace to a re-read Anthropic docs page cited inline.
