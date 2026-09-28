---
topic: agents/copilot-studio-mcp-client
priority: P2
applies_to: "Microsoft Copilot Studio as an MCP client (standard harness; GitHub Copilot harness preview) reaching a self-hosted MCP server through Power Platform connectors, docs current 2026-09-29"
retrieved_utc: 2026-09-29
sources: [S1964, S2126, S703, S-l4qgsnr4, S-oh3ybprh, S-nt2bmgtl, S-kyrgum3q, S-gcbkqdo3, S-6x6bb2f3, S-wpjbqofq, S-rvnsf5ty, S-rstajp7g, S-m75y4u2y, S-adugdkcv]
status: partial
---

# Copilot Studio as an MCP client: network path and protocol behaviour

## Summary
- Copilot Studio reaches an MCP server through a Power Platform connector (the onboarding wizard's
  MCP connector or a custom connector whose operation carries `x-ms-agentic-protocol: mcp-streamable-1.0`),
  so the call leaves from Power Platform's regional connector egress, not from the user's device. [DOC S1964, S-oh3ybprh]
- A self-hosted server is reached either over the public internet (allow-list the `AzureConnectors`
  and `PowerPlatformPlex` service tags of the environment's geo) or, in a VNet-enabled Managed
  Environment, through a delegated Azure subnet; custom connectors support both, and the on-premises
  data gateway supports custom connectors in Power Automate. [DOC S-oh3ybprh, S-kyrgum3q, S-6x6bb2f3]
- The documented client behaviour stops at the transport (Streamable HTTP only), tools and resources
  (not prompts), and schema quirks; the protocol version it sends, its use of sessions, server
  instructions, tool annotations and result content types are not documented. [DOC S1964, S-rstajp7g, S-rvnsf5ty]

## Facts

### Network path
- Access to MCP servers in Copilot Studio relies on Power Platform connectors for connectivity, so a data policy that regulates Power Platform connectors also regulates the MCP server and its tools. [DOC S1964, S-m75y4u2y]
- A custom connector is a wrapper around a REST API that is either public (visible on the internet) or private (visible only to your network); for private APIs Microsoft offers on-premises data connectivity through an on-premises data gateway. [DOC S-nt2bmgtl]
- If managed or custom connectors are used in Power Platform behind a firewall, the firewall must allow the outbound IP addresses these connectors use in the datacenter region; most connectors use HTTPS port 443, and the source port should be allowed as ANY. [DOC S-oh3ybprh]
- Power Platform requests come from IP addresses or service tags that depend on the region and environment of the app or flow; Microsoft asks to allow-list the regional `PowerPlatformPlex` tag along with the `AzureConnectors` tags, and all service tags of a flow's geo regardless of where the target resource is. [DOC S-oh3ybprh]
- Geo-to-tag examples from the Power Platform table: Europe = `AzureConnectors.NorthEurope`, `AzureConnectors.WestEurope`; United Kingdom = `AzureConnectors.UKNorth`, `UKSouth`, `UKSouth2`, `UKWest`; Germany = `AzureConnectors.GermanyCentral`, `GermanyNorthEast`, `GermanyNorth`, `GermanyWestCentral`. [DOC S-oh3ybprh]
- The preferred source of current connector IP ranges is the Service Tag Discovery API (downloadable JSON files as the alternative), and Microsoft recommends refreshing allow-listed addresses at least every 90 days. [DOC S-oh3ybprh]
- Agent connector traffic forwarded through Global Secure Access needs the Global Secure Access egress IPs allow-listed; built-in connectors such as HTTP may call out from Logic Apps or Power Automate addresses, whose tags must then be allowed too. [DOC S-oh3ybprh]
- VNet support for Power Platform uses Azure subnet delegation for outbound runtime traffic, so connectors can call resources inside the enterprise network (in Azure behind private endpoints, or on-premises brought in with ExpressRoute) without Power Platform IP ranges or service tags. [DOC S-kyrgum3q]
- Custom connectors are in the generally available VNet-supported connector list; VNet support covers Production, Default, Sandbox and Developer environments, not Trial or Dataverse for Teams. [DOC S-kyrgum3q]
- In a VNet-linked environment, custom connectors created before the link must be resaved, and OAuth and token requests do not transit the virtual network: only requests to the API endpoints do. [DOC S-nt2bmgtl]
- Once an environment is subnet-delegated, supported services run requests in the delegated subnet under your network policies; internet-bound calls stay available by default, and Microsoft suggests an Azure NAT gateway on the subnet to control them. [DOC S-kyrgum3q]
- The virtual network must be in the environment's region pair (Europe: westeurope and northeurope; UK: uksouth and ukwest), with delegated subnets in both Azure regions for failover. [DOC S-kyrgum3q]
- Power Platform requires the endpoint to present a TLS certificate with the complete chain from a well-known root CA; a custom root CA cannot be added. [DOC S-kyrgum3q]
- Copilot Studio's VNet page requires a Managed Environment and a tenant or Environment Admin, and names three private-endpoint scenarios (Key Vault over an HTTP node, Application Insights telemetry, VNet-supported connectors such as SQL Server); it does not name MCP. [DOC S-gcbkqdo3]
- Copilot Studio's A2A connections use the custom connector infrastructure, which Microsoft says lets them reach agents on-premises or in a virtual network. [DOC S2126]
- The on-premises data gateway in Power Automate supports "custom connectors that you create" (standard mode only; personal mode is Power BI only). [DOC S-6x6bb2f3]
- Whether an MCP connector (`x-ms-agentic-protocol: mcp-streamable-1.0`) can use the on-premises data gateway or the delegated subnet was not stated on any page read; custom connectors in general can, so it is plausible but unconfirmed. [UNK: no Copilot Studio or connector page read on 2026-09-29 names MCP connectors for either path]

### Connector definition
- The custom-connector path imports an OpenAPI (Swagger 2.0) file whose operation is a `post` with `x-ms-agentic-protocol: mcp-streamable-1.0`; Microsoft's sample uses path `/mcp`, scheme `https`, operationId `InvokeMCP` and a `200` response. [DOC S1964]
- The Azure MCP Server guide exposes a POST method at the root path with the same property, which it calls required for the connector to talk to the API by using the MCP protocol. [DOC S-wpjbqofq]
- That guide secures the connector with OAuth 2.0 (identity provider Azure Active Directory, on-behalf-of login enabled, scope `<server app client id>/.default`), with a client secret or a managed identity plus a federated credential on the client app registration. [DOC S-wpjbqofq]
- The custom connector cannot authenticate users from several tenants: the client app registration should accept only its own tenant, and a cross-tenant server app needs a service principal created in the client's tenant. [DOC S-wpjbqofq]
- Custom connectors that use OAuth 2.0 use a per-connector redirect URI, which must be added to the OAuth app. [DOC S-nt2bmgtl]
- After a custom MCP connector is added to an agent, the agent tries to list the tools from the MCP server and shows them under the connector. [DOC S-wpjbqofq]
- SNIPPET: custom connector definition for a self-hosted MCP server; context: Power Apps custom connector, Import OpenAPI file; checked: no [DER S1964: fields from Microsoft's MCP server schema example, host replaced by a placeholder]
```yaml
swagger: '2.0'
info:
  title: kb MCP server
  description: Streamable MCP server for Copilot Studio
  version: 1.0.0
host: mcp.corp.example.com
basePath: /
schemes:
  - https
paths:
  /mcp:
    post:
      summary: kb MCP server
      x-ms-agentic-protocol: mcp-streamable-1.0
      operationId: InvokeMCP
      responses:
        '200':
          description: Success
```

### Client behaviour
- Copilot Studio supports only the Streamable transport for MCP; it dropped SSE after August 2025, citing the 2025-03-26 transports page for the deprecation. [DOC S1964]
- Of the MCP server features, Copilot Studio supports tools and resources, not prompts; generative orchestration must be on to use MCP. [DOC S-rstajp7g]
- Tools and resources a server publishes are available automatically, with name, description, inputs and outputs from the server, and changes on the server are reflected dynamically. [DOC S-rstajp7g]
- An agent can use an MCP resource only when the server returns it as the output of one of its tools; the settings page lists the tools and a sampling of the resources. [DOC S-m75y4u2y]
- All tools are on by default (**Allow all**); once that toggle is off, tools the server adds later start off. [DOC S-m75y4u2y]
- The wizard's server name and description are what the orchestrator uses to decide whether to call the server at runtime. [DOC S1964]
- Known schema issues: an integer `exclusiveMinimum` throws `System.FormatException`; a type given as an array of types truncates the schema; tools with reference-type inputs are filtered out; enum inputs are read as strings. [DOC S-rvnsf5ty]
- GitHub Copilot harness (preview): the server URL must be an HTTPS endpoint reachable from Copilot Studio; on **Add**, Copilot Studio negotiates the protocol handshake and lists the tools; concurrent MCP server instances per conversation are capped, and each server counts against the agent's tool total. [DOC S-adugdkcv]
- The MCP protocol version Copilot Studio's client sends, whether it keeps `Mcp-Session-Id` sessions, whether it reads server `instructions`, whether it acts on tool annotations (`readOnlyHint`, `destructiveHint`), and which tool-result content types it shows are not stated on any Copilot Studio page read. [UNK: seven Copilot Studio MCP pages and the Azure MCP Server guide read on 2026-09-29]

### How it fits
- A server built for Copilot Studio should accept the handshake revisions (`initialize`, 2025-11-25 and earlier) and not only 2026-07-28: Copilot Studio documents a handshake and cites the 2025-03-26 transport, and a dual-era server picks legacy semantics when a client opens with `initialize`. [DER S1964, S-adugdkcv, S703: handshake and cited revision against the spec's era rule]
- A stateless server that keeps no protocol session works whether or not the client sends `Mcp-Session-Id`, which avoids depending on the undocumented session behaviour. [DER S-l4qgsnr4, S1964: the session id is minted by the server in the handshake revisions and removed in 2026-07-28]
- A loopback-only server is unreachable from Copilot Studio: the call starts in Power Platform's connector service, so the server needs a public HTTPS endpoint allow-listed for the geo's `AzureConnectors` and `PowerPlatformPlex` tags, or a private endpoint reached from a delegated subnet, in both cases with a publicly trusted full-chain TLS certificate. [DER S1964, S-oh3ybprh, S-kyrgum3q: connector egress and TLS rule]
- Authentication belongs at the front of that endpoint (OAuth 2.0 with Entra ID, or an API key header), since tokens for a VNet-linked connector still travel over the public token endpoints. [DER S1964, S-nt2bmgtl: wizard auth options and token requests outside the VNet]

## Reference
- Copilot Studio features, limits, DLP and the MCP wizard: `agents/copilot-studio-inventory.md`.
- MCP transport and sessions: `mcp/transports-streamable-http.md`; revisions and eras: `mcp/spec-overview.md`; tool annotations: `mcp/tools.md`.
- Connector outbound IPs: https://learn.microsoft.com/en-us/connectors/common/outbound-ip-addresses (S-oh3ybprh).

## Examples
- A kb MCP server at `https://mcp.corp.example.com/mcp`, published through a reverse proxy that
  terminates TLS and checks an Entra ID token, allow-lists `AzureConnectors.WestEurope`,
  `AzureConnectors.NorthEurope` and the `PowerPlatformPlex` tag for a Europe environment; the
  custom connector above points at it. Illustration only, not a tested deployment.
