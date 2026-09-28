---
topic: agents/m365-copilot-extensibility
priority: P1
applies_to: "Microsoft 365 Copilot extensibility: declarative agents, custom engine agents, API/MCP plugins, Copilot connectors; docs current 2026-09-26"
retrieved_utc: 2026-09-28
sources: [S1840, S-gum2njhe, S-46ndqgay, S-3r3y76di, S-nztel442, S-4rvc364j, S-atzopgi7, S-j46dza7u, S-ipjygran, S-dfgcii3c, S-u2bv3zsu, S-7gjdhgh5, S-qgctvfuf, S-rymoydzk, S-nmxo2lu7, S-3wxcangs, S-5kn2m73o, S-aag4xzbw, S-xasz2mbx, S-bjnw7imn, S-rqk5odum, S-xgl6s552, S-x5qiebqy, S-lgyskerc, S-w32jevfq, S-7f2wrltf]
status: complete
files: [agents/declarative-agent-manifest.csv]
---

# Microsoft 365 Copilot extensibility

## Summary
- Two ways to build an agent for Microsoft 365 Copilot: a **declarative agent** (instructions +
  knowledge + actions layered on Copilot's own orchestrator, models, and Microsoft 365 compliance/
  RAI posture; no separate hosting) or a **custom engine agent** (bring your own orchestrator,
  models, and hosting, typically Azure; needed for proactive/autonomous behavior, group
  collaboration, agent-to-agent delegation, or running outside Microsoft 365). [DOC S-j46dza7u]
- Declarative agents are described by a **JSON manifest** with its own schema-version lineage
  (v1.0-v1.8 at retrieval; v1.8 is current). Field limits (`instructions` 8,000 characters, `name`
  100, `description` 1,000) are covered in `agents/instruction-and-context-limits.md`/`.csv`; this
  article covers the capability/action surface and the extensibility ecosystem around the manifest.
  Full field-by-field table: `agents/declarative-agent-manifest.csv`. [DOC S1840, S-gum2njhe]
- Declarative-agent **actions** are plugins: either **API plugins** (an OpenAPI description plus a
  plugin manifest, schema v2.4 current) or an **MCP server** wrapped as a plugin (dynamic tool
  discovery by default, or a pinned/curated tool list) — both configured the same way in Agents
  Toolkit's "Add an Action" flow. [DOC S-ipjygran, S-u2bv3zsu]
- **Copilot connectors** bring external line-of-business data into Microsoft 365 Copilot: synced
  connectors ingest and index content into Microsoft Graph, federated connectors fetch it in real time
  through MCP without indexing. More than 100 connectors are listed in the gallery; custom synced
  ones are built with Agents Toolkit, the connector SDK or the Copilot connector APIs. [DOC S-xasz2mbx]
- Admin governance runs through the Microsoft 365 admin center's **agent inventory/registry**
  (Agents > All Agents), which lists every agent tenant-wide by publisher type and channel and
  exposes a preview Graph API (`copilotPackages`) for bulk inventory/reporting. [DOC S-bjnw7imn]
- Licensing: a Microsoft 365 Copilot add-on license removes all extensibility usage charges;
  without it, Copilot Chat users can still run instruction-only/public-grounded declarative agents
  free, but shared-tenant-data usage (Copilot connectors, SharePoint knowledge) is metered in
  Copilot Credits via Copilot Studio pay-as-you-go billing. [DOC S-nmxo2lu7]

## Facts

### Declarative agents vs. custom engine agents
- A declarative agent's characteristics: hosted entirely by Copilot (no extra hosting), buildable
  with low-code Microsoft 365 Copilot Agent Builder or pro-code Visual Studio/Visual Studio
  Code + Microsoft 365 Agents Toolkit, and runs only inside Microsoft 365 Copilot and Microsoft 365
  apps (Teams, Word, Excel, Outlook). It cannot initiate proactive actions — every interaction is
  user-initiated. [DOC S-j46dza7u]
- A custom engine agent needs its own hosting (typically Azure, at extra cost), can use any
  orchestration framework (Semantic Kernel, LangChain, etc.) and any model, supports proactive/
  autonomous workflows and agent-to-agent collaboration, and can run outside Microsoft 365 (e.g.
  external apps) in addition to Teams/Copilot/Word/Excel/Edge. It must independently meet its own
  compliance, security, and Responsible AI requirements — it does not inherit Microsoft 365's.
  [DOC S-j46dza7u]
- Cost comparison: a declarative agent needs a Microsoft 365 Copilot add-on license (or Copilot Chat
  access via an eligible Microsoft 365 license) and has no extra usage charge for licensed users; a
  custom engine agent needs no Microsoft 365 Copilot license at all but pays for its own hosting
  (Azure App Service, Azure Bot Service for multi-channel publishing) and, for unlicensed users
  touching shared tenant data, Copilot Credits usage-based billing. [DOC S-nmxo2lu7]
- Declarative agents grounded on web search, with limited capabilities, can be built without a
  Microsoft 365 Copilot license. Per the capability table, Copilot Chat users without usage-based
  billing still get custom actions, custom instructions, code interpreter, image generator, MCP Apps
  and web search; grounding on organizational data (Copilot connectors, SharePoint, embedded files,
  Dataverse) needs pay-as-you-go billing in the tenant or a Microsoft 365 Copilot license, and Email,
  People, Teams messages and Teams meetings knowledge need the license. [DOC S-3wxcangs, S-rymoydzk]
### Declarative agent manifest schema
- The manifest is a JSON document; Microsoft 365 app manifest packages (`app package`) reference it.
  Each schema version publishes its own JSON Schema file
  (`https://developer.microsoft.com/json-schemas/copilot/declarative-agent/v<version>/schema.json`).
  [DOC S-gum2njhe]
- Version history relevant to capabilities (full field table in
  `agents/declarative-agent-manifest.csv`): v1.2 added the web search `sites` property and the graphic
  art and code interpreter capabilities over v1.0; v1.3 added the Dataverse, Microsoft Teams messages, Email, and People capabilities;
  v1.4 added `behavior_overrides` and `disclaimer`, SharePoint-IDs `part_type`/`part_id`, Copilot
  connector content-scoping properties on the Connection object, and the scenario-models capability;
  v1.5 added the meetings (search) capability; v1.7 added `editorial_answers`,
  `default_response_mode`, and conversation-starter `depends_on`; v1.8 (current) added the
  `EmailActions` (triage, supervised send, delete, inbox rules, auto-reply, folder management) and
  `MeetingActions` (scheduling, time-finding polls, time insights) write-capable capabilities. [DOC
  S-46ndqgay, S-3r3y76di, S-nztel442, S-4rvc364j, S-atzopgi7, S-gum2njhe]
- `capabilities` cannot contain more than one object of the same derived capability type per agent
  (e.g. only one Dataverse capability object). [DOC S1840]
- `actions` is an array of `{id, file}` objects, each `file` being a path to the plugin manifest for
  that action; schema 1.8 also accepts an inlined plugin manifest in place of a reference and allows 1-10
  action objects. [DOC S1840, S-gum2njhe]

### Actions: API plugins and MCP-server plugins
- Plugin manifest schema is versioned separately from the declarative-agent manifest; v2.4 is
  current (v2.3 added Office Add-in `LocalPlugin` runtime support and the local-endpoint spec
  object). An API plugin's runtime object is `type: OpenApi` with an OpenAPI spec fetched from a
  `url` or embedded as `api_description`; each `function` binds to an OpenAPI `operationId` and
  declares `security_info.data_handling` values (`GetPublicData`, `GetPrivateData`, `DataTransform`,
  `DataExport`, `ResourceStateUpdate`) used to determine the relative risk of invoking the function; a
  separate `confirmation` object describes the dialog shown before a call. [DOC S-7gjdhgh5]
- Runtime authentication `auth.type` is `None`, `OAuthPluginVault`, or `ApiKeyPluginVault` (the latter
  two carry a `reference_id` so no secret is stored in the manifest itself); schema 2.4 keeps these
  values and adds the `RemoteMCPServer` runtime type for MCP plugins. [DOC S-u2bv3zsu]
- Separately from the plugin-manifest `auth` object, Microsoft 365 Copilot documents five supported
  authentication schemes for MCP and API plugins: Microsoft Entra SSO (both plugin types), OAuth 2.0
  authorization code flow (both), dynamic client registration/DCR (MCP plugins only), API key (API
  plugins only, not MCP), and no authentication/anonymous (both). Registering an MCP server as an
  **agent connector** (the `agentConnectors` node of the Microsoft 365 app manifest) is a distinct
  surface from a plugin, with its own, different set of supported authorization types. [DOC
  S-qgctvfuf]
- Building an MCP-server-based action in Microsoft 365 Agents Toolkit: create a Declarative Agent
  project, choose "Add an Action" > "Start with an MCP Server", supply the server URL, pick an
  authentication type (OAuth static registration, OAuth dynamic registration/DCR, Entra SSO, or
  None), then Provision (sideload) from the Toolkit's Lifecycle pane; the generated `ai-plugin.json`
  defaults to **dynamic tool discovery** (tools resolved at runtime, none added manually) unless a
  fixed/pinned tool list is configured. The redirect/callback URL for OAuth is fixed:
  `https://teams.microsoft.com/api/platform/v1.0/oAuthRedirect`. [DOC S-ipjygran]
- **MCP apps** let an MCP-server plugin's tools return interactive UI widgets rendered
  inline or full-screen inside Microsoft 365 Copilot chat, via either the MCP Apps extension
  (`modelcontextprotocol.github.io/ext-apps`) or the OpenAI Apps SDK; at least one pinned tool must
  return a widget if dynamic discovery is disabled. Requires Microsoft 365 Agents Toolkit >= 6.12.0.
  [DOC S-dfgcii3c]
- A third-party MCP server made generally available to a tenant (beyond a developer's own sideload)
  must go through the **Microsoft connector certification program**: it is packaged and submitted as
  a Power Platform custom connector like any other certified connector, subject to Marketplace
  policy and technical review. [DOC S-aag4xzbw]
- Admins can monitor approved MCP server invocations tenant-wide through **Microsoft Defender
  advanced hunting** on `CloudAppEvents` where `ActionType == "ExecuteToolByGateway"`, which surfaces
  agent name, MCP server name, and other invocation metadata. [DOC S-5kn2m73o]

### Custom engine agents and toolkits
- Custom engine agents can be built with Copilot Studio (low-code) or pro-code tooling (Visual
  Studio, Visual Studio Code + Microsoft 365 Agents Toolkit) in .NET, Python, or JavaScript, using
  frameworks such as Semantic Kernel or LangChain; a Microsoft 365 Copilot license is not required to
  build one with Teams SDK — cost instead depends on the Azure services consumed. [DOC S-j46dza7u,
  S-3wxcangs]
- Sideloading any custom app (declarative agent or custom engine agent project built via Agents
  Toolkit) requires a tenant admin to enable **Upload custom apps** in Teams admin center > Teams
  apps > Setup policies > Global (Org-wide default); sideloaded apps, including agents, are then
  managed per-user from Teams > Apps > Manage your apps. [DOC S-rymoydzk]

### Copilot connectors
- Synced Copilot connectors ingest external items, defined with the `externalItem` schema, into
  Microsoft Graph, where they are semantically indexed (title and content); deployed connectors are
  tenant-wide unless external item security is restricted. Building one needs an AI administrator to
  register an app and grant admin consent for Microsoft Graph permissions. [DOC S-xasz2mbx]
- **Synced** connectors: content synced into Graph, Entra ID app registration, indexed search.
  **Federated** connectors (MCP-based): no data movement, query-time fetch from the MCP server, auth by
  MCP-supported methods, and no semantic indexing. [DOC S-xasz2mbx]
- Building a custom synced connector: three routes — Microsoft 365 Agents Toolkit, the connector SDK,
  or the Copilot connector APIs. More than 100 connectors (Azure services, Box, Confluence, Google
  services, MediaWiki, Salesforce, ServiceNow and more) are listed in the Copilot connectors gallery.
  [DOC S-xasz2mbx]
- Microsoft 365 Copilot connectors were formerly called Microsoft Graph connectors; custom connectors use the Copilot connectors REST API (connections, schema, items, external groups), and items ingested this way consume the tenant's item quota. [DOC S-xgl6s552]
- The connector agent behind SDK-built connectors runs full and incremental crawls on admin-defined intervals, detects deleted and changed items (by hash), and stamps ACLs from Entra ID or the source for security trimming. [DOC S-x5qiebqy]
- In the admin center Sync tab, incremental crawls don't pick up permission updates, so full crawls must run periodically; the repeat interval is 15 minutes to 12 hours. [DOC S-lgyskerc]

### Admin controls and governance
- The Microsoft 365 admin center's **agent registry** (Agents > All Agents > Registry) lists every
  agent available to the tenant in four publisher-type buckets: Microsoft agents, external
  partner-built agents, agents published by the org (LOB), and agents shared by their creator; it
  also reports **Total agents**, **Agents without owners**, and **Unmanaged agents** (created/managed
  outside Agent 365, without its risk protection and observability) tenant-wide counts. [DOC
  S-bjnw7imn]
- Viewing risk signals in the registry needs an E7 or Agent 365 licence on the tenant; pinning agents
  needs the AI Administrator role. [DOC S-bjnw7imn]
- AI Reader, Global Reader, Security Administrator/Reader, Reports Reader and User Experience Success Manager can view insights and the agent registry but can't install, modify or approve agents; only AI Administrator and Global Administrator have tenant-wide governance. [DOC S-w32jevfq]
- A preview Microsoft Graph API surface (`copilotPackages` — list and get-details operations) lets
  admins pull the tenant's full agent inventory and per-agent metadata programmatically, gated on the
  AI Admin role, for bulk management/compliance reporting instead of the admin-center UI. [DOC
  S-bjnw7imn]
- Uploading a custom agent (.zip) in the registry: under **Publish** choose the users or groups who can
  install it and under **Deploy** (optional) those who get it preinstalled, then apply a security
  policy template. Admins can pin up to three deployed agents into the Agents list in Microsoft
  Copilot, for all users or specific users or groups. [DOC S-bjnw7imn]
- An agent's details pane has tabs Details, Users (users who get it preinstalled and users who can install it), Data & Tools (read-only capabilities, knowledge sources and tools, plus Agent ID details), Security, Permissions, Certification and Activity, with Agent instances, Connected Agents and Computer use shown when they apply. [DOC S-7f2wrltf]

### Licensing
- Three licensing tiers for extensibility: **Microsoft 365 Copilot** (paid add-on; frequent users;
  no extra charge for any extensibility feature usage), **Microsoft 365 Copilot Chat** (included for
  eligible Microsoft 365 users; free for instruction-only or public-grounded agents, but
  usage-based Copilot Credits billing via Copilot Studio metering for shared-tenant-data grounding
  such as SharePoint or Copilot connectors), and **no Copilot license** (Copilot itself inaccessible;
  extensibility features unavailable). [DOC S-nmxo2lu7]
- Building declarative agents needs no extra license beyond Microsoft 365 Copilot itself — once you
  hold that license, Copilot connectors and plugins are included; building on web-search-only
  grounding needs no license at all. Grounding an agent in organizational data through Copilot Studio
  needs either a Copilot Studio license or pay-as-you-go consumption metering enabled in the tenant.
  [DOC S-3wxcangs]
- The Microsoft 365 Copilot APIs (a separate, newer API surface for building on top of Copilot) are
  free to call for users who already hold a Microsoft 365 Copilot license; there is currently no
  supported access path for unlicensed users. [DOC S-nmxo2lu7]

## Reference
- Manifest field limits (name/description/instructions/disclaimer character caps) and their schema
  version: `agents/instruction-and-context-limits.md:36`, `agents/instruction-and-context-limits.csv`
  (this article's Facts do not repeat those numbers; see `agents/declarative-agent-manifest.csv` for
  the full field table referencing the same limits).
- Copilot Studio's own agent-building surface, feature limits, MCP onboarding wizard, DLP governance,
  and publishing-into-Microsoft-365-Copilot flow: `agents/copilot-studio-inventory.md` (back-linked
  from there in its Reference section).
- Agent identity, Conditional Access, and identity-governance for agents (including Agent 365
  registry convergence and the AI Reader/AI Administrator roles used for the inventory above):
  `entra/agent-id.md`.
- Foundry Agent Service, M365 Agents SDK, and custom-chatbot architecture patterns for custom engine
  agents: `agents/own-chatbot-architecture.md`.
- Prompt-injection mitigations relevant to any agent surfaced in Microsoft 365 Copilot:
  `agents/prompt-injection-design-patterns.md`.

## Examples

### Minimal declarative agent manifest (schema 1.8) with an MCP-server action
Placeholders only; the MCP server URL is a placeholder, not a real deployment.

- SNIPPET: a minimal declarative agent manifest with a web-search capability and one action
  referencing an external plugin manifest file; context: declarative agent schema v1.8; checked: no
  [DOC S-gum2njhe: `version`, `capabilities` array with a `WebSearch` object, `actions` array with
  `{id, file}`]
```json
{
  "version": "v1.8",
  "name": "IT Helpdesk Agent",
  "description": "Answers questions about corp IT tickets using an internal MCP server.",
  "instructions": "You help employees check the status of IT tickets. Use the ticket-lookup tool. Do not invent ticket numbers or statuses.",
  "capabilities": [
    { "name": "WebSearch" }
  ],
  "actions": [
    {
      "id": "ticketMcpPlugin",
      "file": "ai-plugin.json"
    }
  ]
}
```

The referenced `ai-plugin.json` (plugin manifest schema 2.4) wraps the MCP server as a `RemoteMCPServer`
runtime with dynamic tool discovery, authenticated through an Entra SSO auth config (which the manifest
references as an `OAuthPluginVault` runtime-auth entry, not a literal `EntraSso` type):

- SNIPPET: a plugin manifest wrapping an MCP server as a `RemoteMCPServer` runtime, authenticated via an
  Entra SSO auth config referenced as `OAuthPluginVault`; context: plugin manifest schema v2.4, an
  Entra SSO auth config already created (Agents Toolkit, the declarative-agent-developer skill, or the
  Teams developer portal); checked: no [DOC S-u2bv3zsu: runtime `type: RemoteMCPServer`, MCP server
  spec object's `url`; DOC S-rqk5odum: Entra SSO auth config resolves to `auth.type: OAuthPluginVault`
  with a `reference_id`]
```json
{
  "schema_version": "v2.4",
  "name_for_human": "IT Ticket Tools",
  "description_for_human": "Look up and summarize corp IT tickets.",
  "runtimes": [
    {
      "type": "RemoteMCPServer",
      "spec": {
        "url": "https://mcp.corp.example.com/mcp"
      },
      "auth": {
        "type": "OAuthPluginVault",
        "reference_id": "00000000-0000-0000-0000-000000000000"
      }
    }
  ]
}
```

Sideload path: Microsoft 365 Agents Toolkit > Create a New Agent/App > Declarative Agent > Add an
Action > Start with an MCP Server > enter `https://mcp.corp.example.com/mcp` > choose Entra SSO >
Provision from the Lifecycle pane, then test at `https://m365.cloud.microsoft/chat`. [DOC S-ipjygran]
