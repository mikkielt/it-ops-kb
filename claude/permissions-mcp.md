---
topic: claude/permissions-mcp
priority: P1
applies_to: "Claude Code 2.1.281 docs (retrieved 2026-09-23)"
retrieved_utc: 2026-09-25
sources: [S742, S740, S743, S746]
status: complete
---
# Permission rules for MCP tools

## Summary
MCP tools are named `mcp__<server>__<tool>`. Rules: `mcp__server` or `mcp__server__*` (all tools of a server),
`mcp__server__tool` (one tool). Evaluation is deny → ask → allow; a deny at any scope cannot be overridden.
Parameter-level matching for MCP tools is only possible via `--disallowedTools` deny rules (settings files skip
`mcp__` rules with parentheses). A server can force a prompt on every call with `_meta["anthropic/requiresUserInteraction"]`.

## Facts
- `mcp__puppeteer` and `mcp__puppeteer__*` match all tools of server `puppeteer`; `mcp__puppeteer__puppeteer_navigate` matches one tool. [DOC S742]
- The server name is the name as configured in Claude Code. [DOC S742]
- Rules are evaluated deny, then ask, then allow; the first match wins; specificity does not change the order. [DOC S742]
- If a tool is denied at any level no other level can allow it; managed deny cannot be overridden by `--allowedTools`. [DOC S742]
- Deny/ask rules accept tool-name globs (`"mcp__*"` = every MCP tool); allow globs are accepted only after a literal `mcp__<server>__` prefix (e.g. `mcp__github__get_*`); `"mcp__*"` as allow is skipped with a warning. [DOC S742]
- A bare-name deny removes the tool from Claude's context entirely. [DOC S742]
- Settings files skip any `mcp__` rule with parentheses; MCP parameter matching requires a deny rule via `--disallowedTools`. [DOC S742]
- `allowManagedPermissionRulesOnly` makes managed settings the only source of permission rules. [DOC S742]
- `_meta["anthropic/requiresUserInteraction"]: true` (the JSON boolean only) on a tool in `tools/list` forces its permission prompt on every call, even in acceptEdits/auto/bypassPermissions, with no "don't ask again"; matching allow rules do not skip it; `dontAsk` mode denies it; with `--permission-prompt-tool` an `allow` result is converted to a deny, while the Agent SDK `canUseTool` callback can approve it. Requires v2.1.199+. [DOC S740]
- Plugin-bundled server tools are named `mcp__plugin_<plugin>_<server>__<tool>`. [DOC S743]
- Claude Code displays tool annotations and titles in the `/mcp` view (since 1.0.44). [DOC S746]
- Whether Claude Code uses `readOnlyHint`/`destructiveHint` in permission decisions: not documented in permissions or MCP pages. [UNK]

## Reference
| Rule | Matches |
|---|---|
| `mcp__inventory` | all tools of server `inventory` |
| `mcp__inventory__*` | all tools of server `inventory` |
| `mcp__inventory__device_get` | one tool |
| `mcp__*` (deny/ask only) | all MCP tools |

## Examples
```json
{ "permissions": { "allow": ["mcp__inventory__device_get"], "ask": ["mcp__inventory__client_refresh_policy"], "deny": ["mcp__dsc__*"] } }
```
