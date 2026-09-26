---
topic: mcp/python-sdk
priority: P1
applies_to: "MCP Python SDK (PyPI `mcp`) 2.2.0 (tag v2.2.0, 2026-09-07)"
retrieved_utc: 2026-09-26
sources: [S720, S721, S722, S723, S724, S725, S726, S727, S728, S729, S730, S731, S732, S733, S734, S735, S736, S740, S-657bicoa]
status: complete
---
# MCP Python SDK 2.x

## Summary
2.x exists and is the stable line: v2.0.0 (2026-07-28), v2.1.0/2.1.1, v2.0.1, v2.2.0 (2026-09-07, latest); 1.x is
maintained in parallel (v1.30.0). `FastMCP` was renamed `MCPServer` (`from mcp.server import MCPServer`); the old
import raises `ModuleNotFoundError`. 2.x speaks 2026-07-28 and serves legacy clients on the same server.
Elicitation: `Resolve(...)`+`Elicit` is era-portable; `ctx.elicit()` works only on legacy (handshake) connections.

## Facts
- Releases: v2.0.0 2026-07-28, v2.1.0 2026-08-24, v2.1.1 2026-08-25, v2.0.1 2026-08-26, v2.2.0 2026-09-07 (latest), v1.30.0 2026-09-07. [DOC S731]
- Licence MIT; supports Python 3.10-3.14 per the `pyproject.toml` classifiers. [DOC S734, S-657bicoa]
- Semver: minor = features/non-breaking, patch = fixes; breaking changes only in a major; 2.x gets fixes and features, 1.x critical/security fixes only. [DOC S730]
- `mcp` and `mcp-types` release in lockstep; each `mcp` requires the exact matching `mcp-types`. [DOC S730]
- `FastMCP` is now `mcp.server.mcpserver.MCPServer`; importing `mcp.server.fastmcp` raises `ModuleNotFoundError` pointing to the migration guide. [DOC S732]
- `ctx.fastmcp` → `ctx.mcp_server`; `get_context()` removed (declare `ctx: Context`); `FastMCPError` → `MCPServerError`. [DOC S729, S728]
- `mcp.run()` with no argument = stdio transport; transport options go to `run()`, not the constructor. [DOC S724]
- `MCPServer` answers `server/discover` on every transport including stdio. [DOC S722]
- The low-level server's run loop is `serve_dual_era_loop` (answers `initialize` and modern requests). [DOC S735]
- Tool annotations: `@mcp.tool(title=..., annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))`; SDK docs call them hints, not security. [DOC S725]
- Structured output: return annotation = output schema; validated before leaving the server; `structured_output=False` opts out. [DOC S726]
- `ctx.elicit()`/`ctx.elicit_url()` are server-to-client requests available only on legacy connections (2025-11-25 or earlier); on 2026-07-28 connections they raise `NoBackChannelError`. [DOC S720]
- `NoBackChannelError` subclasses `MCPError` (code `-32600`) and reaches the client as a top-level JSON-RPC error, not `isError`. [DOC S728]
- `Resolve(fn)` returning `Elicit(...)` sends a live `elicitation/create` on legacy sessions and returns `InputRequiredResult` on 2026-07-28; tool body gets `AcceptedElicitation`/`DeclinedElicitation`/`CancelledElicitation`. [DOC S720]
- A tool using `Resolve(...)` parameters cannot also return `InputRequiredResult` from its body. [DOC S721]
- Migration guide: for stdio workflows relying on server-initiated requests (push elicitation), pass `mode='legacy'` on the (SDK) client; a 2026-07-28 connection refuses them on every transport. [DOC S728]
- Streamable HTTP legacy leg with `stateless_http=True` or `json_response=True` has no back-channel; `ctx.elicit()` raises `NoBackChannelError` there. [DOC S723]
- Deprecated protocol features (roots, sampling, logging) warn with `MCPDeprecationWarning`. [DOC S727]
- SDK client: `input_required_max_rounds` default 10 bounds the MRTR loop. [DOC S721]
- Hosting in Claude Code: `claude mcp add <name> -- <launch command>` (SDK docs). [DOC S740]
- Whether SDK 2.x's stdio legacy session supports a mid-call `ctx.elicit()` end to end with Claude Code as the host: not stated in one source; derived in answers.md Q14. [DER S728,S740]

## Reference
| API | Legacy session (initialize) | 2026-07-28 session |
|---|---|---|
| `await ctx.elicit(msg, schema=Model)` | live `elicitation/create`, awaits answer mid-call | raises `NoBackChannelError` |
| `Annotated[T, Resolve(fn)]` + `Elicit(...)` | live `elicitation/create` | `InputRequiredResult`, client retries |
| return `InputRequiredResult` | `-32603` "Handler returned an invalid result" | supported |

## Examples
```python
from typing import Annotated
from pydantic import BaseModel
from mcp.server import MCPServer
from mcp.server.mcpserver import Elicit, ElicitationResult, Resolve, AcceptedElicitation

mcp = MCPServer("inventory")

class Confirm(BaseModel):
    ok: bool

async def confirm(device: str) -> Elicit[Confirm]:
    return Elicit(f"Refresh machine policy on {device}?", Confirm)

@mcp.tool()
async def refresh_policy(device: str, c: Annotated[ElicitationResult[Confirm], Resolve(confirm)]) -> str:
    match c:
        case AcceptedElicitation(data=Confirm(ok=True)):
            return f"queued for {device}"
        case _:
            return "not confirmed"
```
(Pattern from S733; device example `PL-LT-00123`.)
