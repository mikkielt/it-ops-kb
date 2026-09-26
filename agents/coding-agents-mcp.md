---
topic: agents/coding-agents-mcp
priority: P2
applies_to: "GitHub Copilot coding agent (2026-09); VS Code MCP support (2026-09); OpenAI Agents SDK (Python, mcp>=1.19.0,<3); OpenAI Responses API remote MCP tool; Codex CLI config.toml (2026-09)"
retrieved_utc: 2026-09-26
sources: [S-udcaydkb, S-y4l4chtg, S-caxeb7wx, S-shpwh3m7, S-r4egujgz, S-b5ptbcql, S-2q2hcluk]
status: partial
---

# MCP server configuration across coding-agent products

## Summary
Four non-Claude-Code products each configure MCP servers differently. GitHub Copilot coding agent takes a
`mcpServers` JSON block entered into a repository web-UI field (no file in the repo). VS Code uses a
`.vscode/mcp.json` (or portable `.mcp.json`/user-profile `mcp.json`) file with a `servers` object plus an
`inputs` array for secret prompts. The OpenAI Agents SDK (Python) configures MCP servers as constructor
objects in code (`MCPServerStdio`, `MCPServerStreamableHttp`), not a file. The Responses API's hosted `mcp`
tool is a JSON tool definition inside the API request body. Codex CLI uses `[mcp_servers.<name>]` tables in
`config.toml`. Only VS Code and Codex distinguish "trusted"/sandboxed servers that skip per-call confirmation;
Copilot coding agent explicitly runs configured MCP tools **without** asking for approval; the Agents SDK and
Responses API instead expose `require_approval` as an explicit opt-in control per tool or server.

## Facts
### Config file / location and top-level key
- GitHub Copilot coding agent: no repo file — a repository admin pastes JSON into **Settings > Copilot > MCP
  servers > MCP configuration**; the top-level key is `mcpServers`, keyed by server name. [DOC S-udcaydkb]
- VS Code: workspace file `.vscode/mcp.json` (top-level `servers`), or the portable `.mcp.json` at the
  project root (top-level `mcpServers`, the same key Claude Code's own `.mcp.json` uses — see
  `claude/settings-and-scopes.md`); user-profile scope uses a `mcp.json` opened via **MCP: Open User
  Configuration**. [DOC S-caxeb7wx] Configured servers' tools then surface in the Chat view's agent mode
  tool picker, the same place VS Code lists other extension-contributed tools. [DOC S-y4l4chtg]
- OpenAI Agents SDK (Python): no config file — servers are instantiated in code as
  `MCPServerStdio(params={...})` / `MCPServerStreamableHttp(params={...})` / the deprecated
  `MCPServerSse(params={...})` and passed to an `Agent`'s `mcp_servers` list. [DOC S-shpwh3m7]
- OpenAI Responses API: no config file — the MCP server is one entry in the request's `tools` array with
  `"type": "mcp"`. [DOC S-r4egujgz]
- Codex CLI: `~/.codex/config.toml` by default; a project can scope its own servers in `.codex/config.toml`
  for trusted projects. Each server is a `[mcp_servers.<name>]` TOML table. [DOC S-2q2hcluk, S-b5ptbcql]

### Transport support and fields
- Copilot coding agent: `type` is `"local"`, `"stdio"`, `"http"`, or `"sse"`. Local/stdio servers take
  `command`, `args`, `env`; remote (http/sse) servers take `url`, `headers`. Every server entry also carries
  a `tools` array (tool names, or `["*"]` for all). [DOC S-udcaydkb]
- VS Code stdio servers: required `type: "stdio"`, `command`; optional `args`, `cwd`, `env`, `envFile`,
  `dev`, `sandboxEnabled`. HTTP/SSE servers: required `type: "http"|"sse"`, `url`; optional `headers`,
  `oauth`. A `sandbox` top-level object (macOS/Linux only) restricts filesystem/network access. [DOC S-caxeb7wx]
- OpenAI Agents SDK: `MCPServerStdio` params take `command`, `args`; `MCPServerStreamableHttp` (and the
  deprecated `MCPServerSse`) params take `url`, `headers`, `timeout`. Constructor-level options (all three
  classes): `cache_tools_list`, `max_retry_attempts`, `retry_backoff_seconds_base`,
  `client_session_timeout_seconds`, `use_structured_content`, `require_approval`, `failure_error_function`,
  `tool_meta_resolver`. The SDK negotiates MCP protocol version automatically and supports MCP Python SDK
  v1 and v2 (`mcp>=1.19.0,<3`). [DOC S-shpwh3m7]
- OpenAI Responses API `mcp` tool fields: `server_label`, `server_url`, `server_description`, `allowed_tools`
  (array restricting exposed tool names), `authorization` (OAuth token, resubmitted on every request — not
  echoed back in the Response object), `require_approval`, `defer_loading` (delay loading tool defs until
  needed). [DOC S-r4egujgz]
- Codex CLI stdio table fields (from the vendor's own sample): `enabled`, `required`, `command`, `args`,
  `env` (inline map), `env_vars` (names to pass through from the calling shell), `cwd`, `startup_timeout_sec`,
  `tool_timeout_sec`, `enabled_tools`, `disabled_tools`, `scopes`, `oauth_resource`, and a nested
  `[mcp_servers.<name>.tools.<tool>]` table with `output_token_limit`. [DOC S-b5ptbcql]
- Codex CLI streamable-HTTP table fields: `enabled`, `required`, `url`, `bearer_token_env_var`,
  `http_headers` (inline map), `env_http_headers` (map of header name to source env var),
  `http_headers_helper` (an external command that emits headers), `startup_timeout_sec`, `tool_timeout_sec`,
  `enabled_tools`, `disabled_tools`, `scopes`, and a nested `[mcp_servers.<name>.oauth]` table
  (`client_id`, `callback_url`, `callback_port`). [DOC S-b5ptbcql]
- Codex supports two transports overall: stdio (local process) and streamable HTTP (remote, bearer-token or
  OAuth); SSE is not listed as a Codex transport in the vendor sample. [DOC S-2q2hcluk]

### Auth / secrets
- Copilot coding agent: only repository/environment secrets and variables **named with a `COPILOT_MCP_`
  prefix** are exposed to the MCP configuration; substitution syntax is `$VAR_NAME`, `${VAR_NAME}`, or
  `${VAR_NAME:-default_value}`. OAuth-authenticated remote MCP servers are explicitly **not supported**.
  [DOC S-udcaydkb]
- VS Code: secrets go through an `inputs` array (`promptString`, `pickString`, or `command` input types),
  referenced in a server's fields as `${input:<id>}`; a `password: true` input masks the typed value rather
  than hardcoding it in `mcp.json`. HTTP/SSE servers can also carry an `oauth` field. [DOC S-caxeb7wx]
- OpenAI Agents SDK: auth for remote servers is a `headers` dict on `MCPServerStreamableHttp`/`MCPServerSse`
  (e.g. an `Authorization: Bearer ...` header); no separate secrets-store integration is documented. [DOC S-shpwh3m7]
- OpenAI Responses API: the `authorization` field on the `mcp` tool carries an OAuth access token or other
  credential; it is not persisted or visible in the returned Response object, so it must be resent on every
  API call that reuses the tool. [DOC S-r4egujgz]
- Codex CLI: stdio servers get secrets via `env` (inline) or `env_vars` (pass-through from the host shell);
  streamable-HTTP servers use `bearer_token_env_var` (a bearer token read from a named env var),
  `http_headers`/`env_http_headers` for custom headers, `http_headers_helper` (a helper command producing
  headers dynamically), or a full `[mcp_servers.<name>.oauth]` block (`client_id`, `callback_url`,
  `callback_port`) plus the `codex mcp login <server-name>` command to run the OAuth flow. [DOC S-b5ptbcql, S-2q2hcluk]

### Tool allowlist / approval / trust
- Copilot coding agent: the `tools` array is the allowlist (`["*"]` for all); the docs state plainly that
  "Copilot will be able to use the tools provided by the server autonomously, and will not ask for your
  approval before using them" once a server is configured — there is no per-call approval step. For Copilot
  code review specifically, a tool is used only if the server's `tools/list` response sets
  `annotations.readOnlyHint: true`. [DOC S-udcaydkb]
- VS Code: with `sandboxEnabled: true` on a server, "tool confirmations are auto-approved because the server
  runs in a controlled environment"; otherwise VS Code prompts to confirm each tool invocation. The
  `chat.mcp.access` setting governs which servers can be used at all, and **MCP: Reset Trust** clears saved
  trust decisions for non-workspace-sourced servers (workspace-sourced servers instead inherit VS Code's
  Workspace Trust). [DOC S-caxeb7wx]
- OpenAI Agents SDK: `create_static_tool_filter(allowed_tool_names=[...], blocked_tool_names=[...])` is the
  static allow/deny list (allow-list applied first, then blocklist removes from what remains); a dynamic
  filter callback receiving a `ToolFilterContext` (`run_context`, `agent`, `server_name`) can also gate tool
  exposure per call. Approval is `require_approval` on the server: `"always"`/`"never"`/`True`/`False`, a
  per-tool dict (e.g. `{"delete_file": "always", "read_file": "never"}`), or a grouped
  `{"always": {"tool_names": [...]}, "never": {"tool_names": [...]}}` object. For the hosted-tool form
  (`HostedMCPTool`), `require_approval` lives in `tool_config` and an `on_approval_request` callback returns
  `{"approve": True}` / `{"approve": False, "reason": "..."}`. Local servers also accept
  `tool_input_guardrails`/`tool_output_guardrails` functions that can block or rewrite a call before/after
  execution. [DOC S-shpwh3m7]
- OpenAI Responses API: `allowed_tools` is the allowlist; `require_approval` takes `"never"`, `"always"`, or
  an object scoping approval by tool. When approval is required, the API returns an `mcp_approval_request`
  object (`arguments`, `name`, `server_label`, `approval_request_id`) that the caller answers with an
  `mcp_approval_response` (`approve: true|false`, matching `approval_request_id`) before the call proceeds;
  a completed call surfaces as an `mcp_call` object with the arguments sent, output, and any error. [DOC S-r4egujgz]
- Codex CLI: `enabled_tools`/`disabled_tools` per server are the allow/deny list; `required = true` marks a
  server Codex must be able to reach at startup. Codex's own CLI commands are `codex mcp add <server-name>`
  (register a server, optionally with env vars and a command), `codex mcp login <server-name>` (run OAuth),
  and `codex mcp list`. General tool-call approval in Codex is governed by its overall approval-mode setting
  (values described in vendor docs as `auto`/`prompt`/`writes`/`approve`, with per-tool overrides possible) —
  exact key names for that policy were not confirmed against a primary config-reference page in this pass. [UNK]

## Reference
See `agents/mcp-client-config-formats.csv` for a side-by-side table (product, config file/location,
top-level key, transport support, auth options, approval/allowlist controls, status, source) using the same
placeholder MCP server (`https://mcp.corp.example.com/mcp`) configured for every product below.

## Examples
The same placeholder remote MCP server, `https://mcp.corp.example.com/mcp`, configured in each product:

GitHub Copilot coding agent (pasted into the repo's MCP configuration field):
```json
{
  "mcpServers": {
    "corp-tools": {
      "type": "http",
      "url": "https://mcp.corp.example.com/mcp",
      "headers": { "Authorization": "Bearer $COPILOT_MCP_CORP_TOKEN" },
      "tools": ["get_device", "*"]
    }
  }
}
```

VS Code (`.vscode/mcp.json`):
```json
{
  "inputs": [
    { "id": "corp-token", "type": "promptString", "password": true }
  ],
  "servers": {
    "corp-tools": {
      "type": "http",
      "url": "https://mcp.corp.example.com/mcp",
      "headers": { "Authorization": "Bearer ${input:corp-token}" }
    }
  }
}
```

OpenAI Agents SDK (Python):
```python
from agents.mcp import MCPServerStreamableHttp

corp_tools = MCPServerStreamableHttp(
    params={"url": "https://mcp.corp.example.com/mcp", "headers": {"Authorization": "Bearer ..."}},
    cache_tools_list=True,
    require_approval="always",
)
```

OpenAI Responses API (`tools` array entry):
```json
{
  "type": "mcp",
  "server_label": "corp-tools",
  "server_url": "https://mcp.corp.example.com/mcp",
  "allowed_tools": ["get_device"],
  "require_approval": "always"
}
```

Codex CLI (`~/.codex/config.toml`):
```toml
[mcp_servers.corp-tools]
enabled = true
url = "https://mcp.corp.example.com/mcp"
bearer_token_env_var = "CORP_MCP_TOKEN"
startup_timeout_sec = 10.0
tool_timeout_sec = 60.0
enabled_tools = ["get_device"]
```

See also: `claude/settings-and-scopes.md` — Claude Code's own project-root `.mcp.json` (`mcpServers` key),
settings-file scope precedence, and `managed-mcp.json` delivery.
See also: `claude/permissions-mcp.md` — Claude Code's `mcp__<server>__<tool>` permission-rule syntax and
deny/ask/allow evaluation order, the closest Claude Code analogue to the allowlist/approval controls above.
