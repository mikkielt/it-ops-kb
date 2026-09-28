---
topic: reuse/mcp-microsoft-endpoint-mgmt
priority: P2
applies_to: "a stdio MCP server for engineers, targeting ConfigMgr/Intune/Graph/Entra"
retrieved_utc: 2026-09-28
sources: [S1019, S-eiluqiui, S-vouhh5ur]
status: complete
---

## Summary
`no` reuse: Microsoft's own official MCP server catalog (`microsoft/mcp`, MIT) lists no server for
ConfigMgr, Intune, Graph device management, or Entra as of this session's fetch. A custom MCP tool
surface for these APIs stays fully custom; there is nothing to import or port from this domain.

## Facts
- `microsoft/mcp`'s `servers/` directory contains exactly three entries at the fetched commit:
  `Azure.Mcp.Server`, `Fabric.Mcp.Server`, `Template.Mcp.Server` (a scaffold for new official servers).
  None targets ConfigMgr, Intune, Graph device/identity endpoints, or Entra. [DOC S1019]
- A search of the official MCP Registry (2026-09-28) found no ConfigMgr, SCCM or Intune device-management server, and the registry's permissive moderation means a listing would not vouch for one anyway. [DER S-eiluqiui, S-vouhh5ur: v0 API search results and the moderation policy]

## Reference
| project | scope | official? | licence | reuse verdict |
|---|---|---|---|---|
| microsoft/mcp (`Azure.Mcp.Server`, `Fabric.Mcp.Server`) | Azure / Fabric | yes | MIT | no (wrong domain) |
| ConfigMgr/Intune/Graph-device/Entra MCP server | -- | none found | n/a | no (does not exist) |

## Examples
No fixture data required (mechanism-only facts).
