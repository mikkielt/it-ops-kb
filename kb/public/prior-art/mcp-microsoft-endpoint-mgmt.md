---
topic: prior-art/mcp-microsoft-endpoint-mgmt
priority: P2
applies_to: "a stdio MCP server for engineers, targeting ConfigMgr/Intune/Graph/Entra"
retrieved_utc: 2026-09-28
sources: [S1019, S-gg2bczek, S-vouhh5ur, S-eiluqiui, S2190]
status: complete
---

## Summary
Microsoft publishes one official MCP server catalog, `microsoft/mcp` ("Catalog of official Microsoft
MCP server implementations for AI-powered data access and tool integration," MIT licence). As of this
session's fetch (2026-09-24), its `servers/` directory lists only `Azure.Mcp.Server`,
`Fabric.Mcp.Server` and `Template.Mcp.Server` — no server for ConfigMgr, Intune, Graph device
management, or Entra was present in that catalog. A search of the official MCP Registry (2026-09-28) found no ConfigMgr or
Intune device-management server; Microsoft's read-only Entra MCP Server for Enterprise (preview) is
the nearest official server.

## Facts
- `microsoft/mcp` is described by its own repository metadata as the catalog of official Microsoft
  MCP server implementations; licence MIT; default branch `main`, last push 2026-09-26. [DOC S1019]
- The catalog's top-level `servers/` directory contains exactly three entries at the fetched commit:
  `Azure.Mcp.Server` (Azure resource management), `Fabric.Mcp.Server` (Microsoft Fabric), and
  `Template.Mcp.Server` (a scaffold for adding new official servers). None targets ConfigMgr, Intune,
  Graph device/identity endpoints, or Entra. [DOC S1019]
- The MCP project's list of servers is the MCP Registry (preview): the official metadata repository for publicly accessible MCP servers, with an unauthenticated read-only REST API. Its moderation only removes illegal content, malware, spam and broken servers, so a listing is not an endorsement. [DOC S-gg2bczek, S-vouhh5ur]
- A registry search on 2026-09-28 found no server for ConfigMgr or SCCM and none for "microsoft graph"; "intune" matched only a consulting listing, "defender" only community Advanced Hunting KQL servers, and "endpoint" one community Microsoft 365 server (DynamicEndpoints `m365-core-mcp`, whose GitHub repository no longer resolves). [DER S-eiluqiui: search results of the v0 API]
- Microsoft's own server for directory data is the Microsoft MCP Server for Enterprise (preview): read-only Microsoft Entra queries (users, groups, applications, devices) that turn natural language into Graph calls. [DOC S2190]

## Reference
| project | scope | official? | licence |
|---|---|---|---|
| microsoft/mcp (`Azure.Mcp.Server`) | Azure resource management | yes (Microsoft catalog) | MIT |
| microsoft/mcp (`Fabric.Mcp.Server`) | Microsoft Fabric | yes (Microsoft catalog) | MIT |
| ConfigMgr/Intune/Graph-device/Entra MCP server | — | none found in official catalog | n/a |

## Examples
No fixture data required.
