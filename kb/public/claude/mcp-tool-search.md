---
topic: claude/mcp-tool-search
priority: P3
applies_to: "Claude Code and Agent SDK docs as read on 2026-10-20 (Agent SDK tool-search page dateModified 2026-10-14); MCP page re-read 2026-10-21"
retrieved_utc: 2026-10-21
sources: [S1862, S-sug3dznu, S-bisz7fay, S2159, S2132]
status: complete
---
# MCP tool search in Claude Code: what a tools/list costs and how to control it

## Summary
Claude Code defers MCP tool definitions by default (tool search). At session start only the tool names and the server
instructions enter the context; Claude fetches a tool's schema through the `ToolSearch` tool when it decides to use it.
The `ENABLE_TOOL_SEARCH` variable switches the mode (unset, `true`, `auto`, `auto:N`, `false`), a server's `alwaysLoad`
setting or a tool's `_meta["anthropic/alwaysLoad"]` exempts tools from deferral, and descriptions are cut at fixed
character limits. The docs publish no exact token figure for one tool definition (the SDK page says only that 50 tools can use
10-20K tokens); the only published size rule is the `auto` threshold of 10% of the context window.

## Facts
- Tool search keeps MCP context low by deferring tool definitions until Claude needs them; only tool names and server instructions load at session start. [DOC S1862]
- Claude Code sets no fixed per-server tool cap; the practical limit is the context window budget. [DOC S1862]
- The Agent SDK side lists a catalog maximum of 10,000 tools and, by default, up to five most relevant tools returned per search. [DOC S-sug3dznu]
- Loaded tools stay available on later turns until compaction removes the messages where they were discovered; after that Claude searches for them again. [DOC S-sug3dznu]
- Each tool search adds one extra round trip; with fewer than about 10 tools whose definitions fit comfortably in context, loading everything upfront is typically faster. [DOC S-sug3dznu]
- The search matches the query against tool names and descriptions, so a descriptive name such as `search_slack_messages` surfaces for more requests than `query_slack`. [DOC S-sug3dznu]
- Server instructions tell Claude when to search for the server's tools, much as a skill description does; the docs advise stating the task category, when to search and the key capabilities. [DOC S1862]
- Tool search is on by default and applies on Opus 4, Sonnet 4, Haiku 4.5 and later models (on Google Cloud's Agent Platform: Opus 4.5, Sonnet 4.5, Haiku 4.5 and later); on earlier models all MCP tools load upfront and `ENABLE_TOOL_SEARCH=true` does not change that. [DOC S1862]
- When `ANTHROPIC_BASE_URL` points to a gateway, tool search is on by default (from v2.1.304; earlier it was off unless `ENABLE_TOOL_SEARCH` was `true`, `auto` or `auto:N`), so requests carry `defer_loading` fields and `tool_reference` blocks for the gateway to forward; `ENABLE_TOOL_SEARCH=false` loads every tool upfront, and from v2.1.305 Claude Code can retry without tool search after a `400` or `422` whose cause it does not recognize. [DOC S1862]
- Microsoft Foundry deployments hosted on Azure reject tool search server-side; Claude Code detects the rejection and loads MCP tools upfront, and `ENABLE_TOOL_SEARCH` cannot override it. [DOC S1862]
- `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS` keeps tool search off, and `ENABLE_TOOL_SEARCH` cannot override it; from v2.1.227 managed settings can keep tool search on under that variable; a HIPAA-configured session has it off with no override. [DOC S1862]
- `ENABLE_TOOL_SEARCH` values: unset (all MCP tools deferred), `true` (deferred, with the same fallbacks as unset), `auto` (threshold mode: the deferrable tools load upfront while their definitions total under 10% of the context window; from 10% tool search turns on, and the tools can stay deferred even if the total later falls under 10%), `auto:N` (the same with a threshold of N percent, 0-100), `false` (all loaded upfront). [DOC S1862]
- Setting `permissions.deny` to `["ToolSearch"]` disables the `ToolSearch` tool itself. [DOC S1862]
- The Claude Code context-window guide lists MCP tool names among what loads before the first prompt, next to CLAUDE.md, auto memory and skill descriptions; the page as read 2026-10-21 does not mention deferral or the `ENABLE_TOOL_SEARCH` values. [DOC S-bisz7fay]
- In SDK `auto` mode the counted definitions are every MCP tool not marked `alwaysLoad`, from any server, plus built-in tools that load on demand; core built-ins such as Bash, Read and Edit load upfront and do not count. [DOC S-sug3dznu]
- `"alwaysLoad": true` in a server's configuration (any server type) loads all its tools into context whatever `ENABLE_TOOL_SEARCH` says; each upfront tool costs context, so the docs advise it for a small number of tools needed on every turn. [DOC S1862]
- `alwaysLoad: true` also makes startup wait for the server's tools, capped at the 5-second connect timeout; a remote server with a valid cached entry supplies its tools from the cache and does not hold startup. [DOC S1862]
- A server author marks one tool with `_meta["anthropic/alwaysLoad"]: true` in its `tools/list` entry to load it upfront, with no startup wait because of that value; `false` keeps it deferred when the user's configuration sets `alwaysLoad: true` for a `--mcp-config`, SDK or plugin server (v2.1.285+). [DOC S1862]
- A user sets `"alwaysLoad": false` on a server entry to keep all its tools deferred, including tools whose author marked them to load upfront (v2.1.287+). [DOC S1862]
- Server instructions and the description of a tool loaded upfront are cut at 4,096 characters; the description of a tool loaded through tool search is cut at 16,384; search matches only the part within the shorter limit, so key words go first. [DOC S1862]
- A tool loads upfront, and keeps the shorter limit, whenever it is not deferred: tool search off, the tool marked to load upfront, or its server exempt from deferral. [DOC S1862]
- With tool search, a server that finishes connecting mid-turn has its tool names listed on Claude's next request in the same turn; without it, Claude uses the `WaitForMcpServers` tool. [DOC S1862]
- With tool deferral on (the default on supported models) a server connecting or disconnecting mid-conversation does not invalidate the prompt cache, because the tool list of the first request is kept for the whole conversation; with tools loaded upfront, adding or removing a definition does. [DOC S2159]
- The cost guide says that with deferral only tool names and server instructions enter context, points to `/context` to see what consumes space, and notes that CLI tools add no per-tool listing at all. [DOC S2132]
- The only token figure in the four pages is the Agent SDK page's rough one: 50 tools can use 10-20K tokens of the context window (about 200-400 tokens per tool, derived), and tool selection accuracy degrades with more than 30-50 tools loaded at once; no page states the size of one definition or of a given `tools/list` response, and the published size rule is the 10%-of-window `auto` threshold, so a given server's list is measured, not looked up. [DER S1862, S-sug3dznu, S2132, S-bisz7fay: the SDK page's 50-tool figure; the other three pages searched and give none]
- For a server with many read-only tools, the docs imply: descriptive names and keyword-first descriptions (search), server instructions that say when to search (4,096-character cut), and `alwaysLoad` only on the one tool needed at the start of nearly every session. [DER S1862, S-sug3dznu: applying the name, instruction and alwaysLoad rules above]

## Reference
| Setting | Where | Effect |
|---|---|---|
| `ENABLE_TOOL_SEARCH` | environment or settings `env` | unset / `true` / `auto` / `auto:N` / `false` as above |
| `alwaysLoad` | server entry in MCP configuration | `true`: all tools upfront; `false`: all deferred |
| `_meta["anthropic/alwaysLoad"]` | one tool in `tools/list` | `true`: upfront; `false`: deferred under a user's `alwaysLoad: true` |
| `CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH` | environment | one number replaces both cut limits (v2.1.280+) |
| `permissions.deny: ["ToolSearch"]` | settings | disables the search tool |

See `mcp/resources-prompts.md` (server instructions and the cut limits), `claude/permissions-mcp.md` (`readOnlyHint` and `requiresUserInteraction`), `claude/tool-output-limits.md` (result size) and `agents/agent-caching.md` (cache effects).

## Examples
- SNIPPET: one MCP server exempt from deferral while others stay deferred; context: Claude Code `.mcp.json`, placeholder URL; checked: syntax [DER S1862: `alwaysLoad` field on an HTTP server entry]
```json
{
  "mcpServers": {
    "core-tools": {
      "type": "http",
      "url": "https://mcp.corp.example.com/mcp",
      "alwaysLoad": true
    }
  }
}
```
