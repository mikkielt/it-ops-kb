---
topic: prior-art/mcp-microsoft-endpoint-mgmt
priority: P2
applies_to: "a stdio MCP server for engineers, targeting ConfigMgr/Intune/Graph/Entra"
retrieved_utc: 2026-09-26
sources: [S1019]
status: partial
---

## Summary
Microsoft publishes one official MCP server catalog, `microsoft/mcp` ("Catalog of official Microsoft
MCP server implementations for AI-powered data access and tool integration," MIT licence). As of this
session's fetch (2026-09-24), its `servers/` directory lists only `Azure.Mcp.Server`,
`Fabric.Mcp.Server` and `Template.Mcp.Server` — no server for ConfigMgr, Intune, Graph device
management, or Entra was present in that catalog. No community MCP server specifically for
ConfigMgr/Intune/Graph/Entra device management was independently verified this session.

## Facts
- `microsoft/mcp` is described by its own repository metadata as the catalog of official Microsoft
  MCP server implementations; licence MIT; default branch `main`, last push 2026-09-26. [DOC S1019]
- The catalog's top-level `servers/` directory contains exactly three entries at the fetched commit:
  `Azure.Mcp.Server` (Azure resource management), `Fabric.Mcp.Server` (Microsoft Fabric), and
  `Template.Mcp.Server` (a scaffold for adding new official servers). None targets ConfigMgr, Intune,
  Graph device/identity endpoints, or Entra. [DOC S1019]
- The `modelcontextprotocol/modelcontextprotocol` and `modelcontextprotocol/python-sdk` repositories
  (already cloned locally for other kb agents, per BRIEF.md) define the MCP protocol and Python SDK
  themselves but do not list or endorse specific server implementations for Microsoft endpoint
  management. [UNK: no source row reads those two repositories; S1019 is microsoft/mcp]
- No community MCP server for ConfigMgr/Intune/Graph/Entra device management meeting the brief's bar
  (established, actively maintained) was located within this session's fetch budget; absence is
  recorded as a gap, not as a confirmed negative for the whole ecosystem. [UNK]

## Reference
| project | scope | official? | licence |
|---|---|---|---|
| microsoft/mcp (`Azure.Mcp.Server`) | Azure resource management | yes (Microsoft catalog) | MIT |
| microsoft/mcp (`Fabric.Mcp.Server`) | Microsoft Fabric | yes (Microsoft catalog) | MIT |
| ConfigMgr/Intune/Graph-device/Entra MCP server | — | none found in official catalog | n/a |

## Examples
No fixture data required.
