---
topic: claude/managed-mcp
priority: P1
applies_to: "Claude Code 2.1.281 docs (retrieved 2026-09-23)"
retrieved_utc: 2026-09-25
sources: [S741, S746]
status: complete
---
# managed-mcp.json, allowlists and denylists

## Summary
`managed-mcp.json` at a system path gives exclusive control: only its servers (plus `managedMcpServers` and
in-process app servers) load. `allowedMcpServers`/`deniedMcpServers` filter servers by `serverUrl`, `serverCommand`
(exact argv) or `serverName` (not a security control). Denylist always wins and merges from all scopes; make the
allowlist authoritative with `allowManagedMcpServersOnly: true` in a managed source.

## Facts
- Paths: macOS `/Library/Application Support/ClaudeCode/managed-mcp.json`; Linux/WSL `/etc/claude-code/managed-mcp.json`; Windows `C:\Program Files\ClaudeCode\managed-mcp.json`. [DOC S741]
- Same format as a project `.mcp.json` (`mcpServers` map; stdio entries with `type`, `command`, `args`, `env`). [DOC S741]
- It cannot be delivered via server-managed settings; deploy with MDM/GPO/Intune or any admin-privileged process. [DOC S741]
- Any user on the machine can read the file; do not put credentials in `env`; use `${VAR}` expansion, OAuth/per-user headers, or `headersHelper`. [DOC S741]
- With the file present, users cannot add or use other servers (including plugin and `--mcp-config` servers); `claude mcp add` fails with "enterprise MCP configuration is active and has exclusive control over MCP servers". [DOC S741]
- On a workstation, `--mcp-config` with a readable managed file exits: "You cannot dynamically configure MCP servers when an enterprise MCP config is present". [DOC S741]
- `{"mcpServers": {}}` disables MCP (except in-process app servers and `managedMcpServers`). [DOC S741]
- Since v2.1.271 an unreadable/unparsable managed-mcp.json keeps exclusive control (no user/project/plugin servers) and warns. [DOC S746]
- `deniedMcpServers` applies to managed-mcp.json servers too and users' own denylists merge in. [DOC S741]
- Since v2.1.259, `allowedMcpServers` does not apply to managed-mcp.json servers unless their definition uses `${VAR}` expansion. [DOC S741]
- Evaluation order: merge lists → denylist (nothing overrides a match) → allowlist (if set anywhere). [DOC S741]
- Stdio servers are allowed when they match a `serverCommand` entry; a `serverName` match counts only when the allowlist has no `serverCommand` entries. [DOC S741]
- `serverCommand` matches exactly: every argument, in order. [DOC S741]
- `serverCommand`/`serverUrl` values undergo `${VAR}` expansion before matching; policy entries expand from a pinned environment (startup env plus managed `env`). Requires v2.1.219+. [DOC S741]
- `serverName` is a user-assigned label and is not a security control. [DOC S741]
- `allowedMcpServers` unset = all allowed; `[]` = none (apart from the organization's own). [DOC S741]
- Without `allowManagedMcpServersOnly`, allowlists merge from every scope including user settings; with it (managed source only), only the managed allowlist counts. [DOC S741]
- A single invalid entry is dropped with a `claude doctor` warning (since v2.1.154). [DOC S746]
- Blocked servers disappear from `/mcp` and `claude mcp list` without a policy notice. [DOC S741]

## Reference
| Key | Where | Effect |
|---|---|---|
| managed-mcp.json | system path | fixed server set, exclusive |
| managedMcpServers | managed settings only | provided remote servers alongside user's |
| allowedMcpServers | any scope (enforce via managed) | allowlist |
| deniedMcpServers | any scope | denylist, always wins |
| allowManagedMcpServersOnly | managed only | lock allowlist to managed |
| allowAllClaudeAiMcps | managed only | claude.ai connectors alongside managed-mcp.json |

Related: `claude/plugins.md` — a plugin's `.mcp.json`/`mcpServers` servers are named `mcp__plugin_<plugin>_<server>__<tool>`
and are subject to the same `allowedMcpServers`/`deniedMcpServers` and `managed-mcp.json` exclusivity rules above.
`claude/settings-and-scopes.md` — how `allowManagedMcpServersOnly`, `allowedMcpServers`/`deniedMcpServers`, and
`allowAllClaudeAiMcps` fit into managed-settings precedence and the cross-source keys read from every admin source.

## Examples
```json
{
  "mcpServers": {
    "inventory": { "type": "stdio", "command": "C:\\Program Files\\inventory\\inventory.exe", "args": ["mcp"] }
  }
}
```
Matching allowlist entry form: `{ "serverCommand": ["C:\\Program Files\\inventory\\inventory.exe", "mcp"] }`.
