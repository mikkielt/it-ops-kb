---
topic: reuse/mcp-microsoft-endpoint-mgmt
priority: P2
applies_to: "a stdio MCP server for engineers, targeting ConfigMgr/Intune/Graph/Entra"
retrieved_utc: 2026-09-26
sources: [S1019]
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
- No community MCP server for ConfigMgr/Intune/Graph/Entra device management meeting an
  established/actively-maintained bar was located within the fetch budget; this is recorded as a gap,
  not a confirmed negative for the whole ecosystem. [UNK]

## Reference
| project | scope | official? | licence | reuse verdict |
|---|---|---|---|---|
| microsoft/mcp (`Azure.Mcp.Server`, `Fabric.Mcp.Server`) | Azure / Fabric | yes | MIT | no (wrong domain) |
| ConfigMgr/Intune/Graph-device/Entra MCP server | -- | none found | n/a | no (does not exist) |

## Examples
No fixture data required (mechanism-only facts).
