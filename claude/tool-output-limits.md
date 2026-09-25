---
topic: claude/tool-output-limits
priority: P1
applies_to: "Claude Code 2.1.281 docs (retrieved 2026-09-23)"
retrieved_utc: 2026-09-23
sources: [S740, S745, S746]
status: complete
---
# MCP tool output size limits and timeouts

## Summary
Warning above 10,000 tokens (fixed); default maximum 25,000 tokens, configurable with `MAX_MCP_OUTPUT_TOKENS`.
Over the limit, a text result is saved to a file under the session's `tool-results` directory and replaced by a path
reference. A tool may raise its own threshold with `_meta["anthropic/maxResultSizeChars"]` up to 500,000 characters.

## Facts
- Warning when MCP tool output exceeds 10,000 tokens; the warning threshold is fixed. [DOC S740]
- Default maximum 25,000 tokens; `MAX_MCP_OUTPUT_TOKENS` changes it (default 25000). [DOC S745]
- `anthropic/maxResultSizeChars` in a tool's `_meta` sets that tool's text threshold (hard ceiling 500,000 characters), independent of `MAX_MCP_OUTPUT_TOKENS`; image content stays subject to the token limit. [DOC S740]
- Over the limit (no images): result saved to a file in the session `tool-results` directory under `~/.claude/projects/` and replaced by a message naming the path. [DOC S740]
- `MCP_TOOL_TIMEOUT` default 100000000 ms (~28 h); stdio servers have no per-request timer. [DOC S745]
- `CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT` default 1800000 ms (30 min) for stdio, 300000 ms for network servers; progress notifications reset it. [DOC S745]
- `MCP_TIMEOUT` (server startup) default 30000 ms. [DOC S745]
- `MCP_SERVER_CONNECTION_BATCH_SIZE` (stdio) default 3. [DOC S745]
- Long calls can auto-move to background (`CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS`); a call waiting on an open elicitation dialog is not backgrounded. [DOC S740]
- `structuredContent` in tool responses is supported since 2.0.21. [DOC S746]

## Reference
| Setting | Default |
|---|---|
| warning threshold | 10,000 tokens (fixed) |
| MAX_MCP_OUTPUT_TOKENS | 25,000 |
| anthropic/maxResultSizeChars ceiling | 500,000 chars |
| MCP_TOOL_TIMEOUT | 100,000,000 ms |
| CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT (stdio) | 1,800,000 ms |
| MCP_TIMEOUT | 30,000 ms |

## Examples
`{"name":"device_list","_meta":{"anthropic/maxResultSizeChars":200000}}`
