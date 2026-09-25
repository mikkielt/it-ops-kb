---
topic: mcp/security-best-practices
priority: P1
applies_to: "MCP Security Best Practices, docs 2026-07-28"
retrieved_utc: 2026-09-25
sources: [S716, S710]
status: complete
---
# MCP security best practices (2026-07-28)

## Summary
The page covers: confused deputy, token passthrough, SSRF, state handle hijacking (replaces session hijacking),
local MCP server compromise, OAuth authorization URL validation, stdio in proxy scenarios, mix-up attacks,
localhost redirect URI impersonation, CIMD trust policies, scope minimization. Licence CC-BY-4.0 (docs).

## Facts
- Token passthrough is forbidden: servers MUST NOT accept tokens not explicitly issued for them. [DOC S716]
- State handles: servers MUST NOT treat possession of a handle as authentication; SHOULD use secure random handles and bind them server-side to the verified user (`<user_id>:<handle>`). [DOC S716]
- Local MCP servers: clients offering one-click local server configuration MUST show the exact full command and require explicit approval. [DOC S716]
- Servers intended to run locally SHOULD use the stdio transport to limit access to the MCP client, or restrict HTTP (token, unix sockets/IPC). [DOC S716]
- The stdio transport itself is not inherently vulnerable; the risk is proxy architectures that spawn stdio servers on request. [DOC S716]
- Clients MUST NOT use shell commands (cmd.exe, sh, PowerShell) to open URLs; MUST reject `javascript:`, `data:`, `file:`, `vbscript:` schemes. [DOC S716]
- MCP clients SHOULD require HTTPS for OAuth URLs and SHOULD block private/reserved IP ranges (SSRF), including `169.254.0.0/16`. [DOC S716]
- `requestState` must be treated as attacker-controlled and integrity-protected when it affects authorization or logic. [DOC S710]

## Reference
| Section | Main normative point |
|---|---|
| Confused Deputy | proxy servers MUST obtain per-client consent |
| Token Passthrough | MUST NOT accept tokens not issued to the server |
| SSRF | validate/limit URLs fetched during OAuth discovery |
| State Handle Hijacking | handle is not authentication; bind to user |
| Local MCP Server Compromise | consent showing exact command; prefer stdio |
| OAuth Authorization URL Validation | scheme allowlist; no shell to open URLs |
| stdio in Proxy Scenarios | restrict proxy spawning; log stdio usage |
| Scope Minimization | least-privilege scopes, incremental elevation |

## Examples
A stdio server launched by Claude Code on PL-LT-00123 is reachable only by its parent process; no localhost port is opened. [DER S716: stdio limits access to the MCP client]
