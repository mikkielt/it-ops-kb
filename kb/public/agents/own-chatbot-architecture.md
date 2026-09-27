---
topic: agents/own-chatbot-architecture
priority: P1
applies_to: "Microsoft 365 Agents SDK (GA), Bot Framework SDK (retiring), Azure AI Foundry Agent Service, docs current 2026-09-25"
retrieved_utc: 2026-09-27
sources: [S1961, S1964, S1965, S1966, S1967, S1968, S1969, S1970, S1971, S1972, S1974, S1975, S1976, S1977, S1985]
status: complete
---

# Migrating off Copilot Studio: own-chatbot architecture

## Summary
- The **Microsoft 365 Agents SDK** (C#, JavaScript, Python) is a framework for conversational agents
  that is deliberately *only* a channel-abstraction and turn/state-management layer — it is
  explicitly **not** an AI model, an orchestration engine, or a no-code builder. [DOC S1971]
- The **Bot Framework SDK** it replaces is retiring: final long-term support ends 2025-12-31, after
  which it gets no updates/features and no Azure-portal service tickets, though already-built bots
  keep running; Microsoft states the Agents SDK as the migration target. [DOC S1976]
- A separate, heavier path is **Azure AI Foundry Agent Service** (Microsoft Foundry): a managed
  platform offering prompt agents (config-only), voice-based prompt agents, and hosted agents
  (bring-your-own container, any framework), with native MCP tool support, Entra agent identities,
  and A2A protocol support (v1.0 GA). [DOC S1970]
- No fetched source confirms Teams AI library's current relationship to the Agents SDK; that gap is
  recorded in `_parts/agents-copilot/gaps.md`.

## Facts

### Microsoft 365 Agents SDK
- Solves three stated problems: (1) multi-channel messaging — one channel-abstraction layer
  translates a common `Activity` format to/from Teams, M365 Copilot, a website, Slack, Facebook
  Messenger, etc., so channel logic doesn't have to be rewritten per surface; (2) AI-provider
  lock-in — the SDK is AI-agnostic, providing message/state scaffolding with no assumption about
  which model or orchestration library generates responses; (3) conversation state — a built-in
  "turn" concept (one unit of conversational work) with state/storage management, so state
  persistence doesn't have to be hand-rolled. [DOC S1971]
- Supported languages per the official overview: C# (.NET 8.0), JavaScript (Node.js 18+), Python
  (3.9-3.11). The Python repo's own README instead says the packages target Python 3.10 or
  greater, recommends 3.11+, and lists support for 3.10-3.14 — a minor discrepancy between the two Microsoft-authored pages on the exact Python
  floor. [DOC S1971, S1969] — flagged also in `_parts/agents-copilot/conflicts.md` scope note.
- The Python package (`microsoft/Agents-for-python`, MIT licence) additionally ships: aiohttp/
  FastAPI hosting, Azure Blob and CosmosDB storage, MSAL-based and Entra-ID-sidecar authentication,
  Waterfall dialogs/prompts for multi-turn flows, Activity-protocol types/validators, third-party
  connectors (Facebook Messenger, Slack, Twilio), and a **Copilot Studio Client** for direct engine
  interaction with agents built in Copilot Studio (i.e. it can call *into* an existing Copilot
  Studio agent, not just replace one). [DOC S1969]
- Samples for .NET, JavaScript, and Python live in `github.com/microsoft/Agents`, which the README calls
  a jumping-off point: most client-library source lives in the per-language repos (`Agents-for-net`,
  `Agents-for-js`, `Agents-for-python`); language-specific reference docs are published per-language under
  `learn.microsoft.com` (`.NET`, `JavaScript`, `Python` API references). [DOC S1968, S1985]

### Bot Framework SDK retirement
- The GitHub README for `microsoft/botframework-sdk` states: final long-term support ends
  **2025-12-31**; after that date the project receives no updates or maintenance, no product/feature
  updates, and Azure-portal service tickets are no longer serviced — but bots already built with the
  SDK "will continue to function." The README planned archiving no later than the end of December 2025;
  GitHub shows the repository archived (read-only) on 2026-01-05. [DOC S1976]
- Microsoft's stated migration path from an existing Bot Framework SDK bot is to "update your bot to
  the Agents SDK." [DER from S1976, S1971 — no fetched page gives a step-by-step migration guide
  within this pass's budget]

### Azure AI Foundry Agent Service (Microsoft Foundry)
- Three agent types, trading code control for managed convenience: **prompt agents** (instructions +
  model + tools, no code/infra to manage — authored via portal or SDK/REST for CI/CD), **voice-based
  prompt agents** (managed real-time speech via Voice Live), and **hosted agents** (bring your own
  container built with Microsoft's **Agent Framework**, LangGraph, the OpenAI Agents SDK, the
  Anthropic Agent SDK, the GitHub Copilot SDK, or custom code — Foundry runs it with a managed
  endpoint, autoscaling, and a dedicated Entra identity). [DOC S1970]
- Foundry documents native **MCP support**: remote MCP servers (for example an Azure DevOps MCP
  Server) can be added as agent tools, and custom MCP servers can be hosted on Azure Functions via a
  `/runtime/webhooks/mcp` endpoint; authentication options for MCP/tool connections are key-based,
  Microsoft Entra (agent or project managed identity), OAuth on-behalf-of (OBO) passthrough, or
  unauthenticated. Foundry groups tools into a **toolbox** exposed behind one managed MCP-compatible
  endpoint with centralized auth/governance/versioning. [DOC S1970]
- Publishing supports the OpenResponses and Activity protocols for Microsoft 365 (Teams/Copilot),
  an Invocations protocol for custom app integration, and the **A2A protocol** for agent-to-agent
  communication — A2A v1.0 is GA, v0.3 remains in preview. [DOC S1970]
- Content safety (prompt-injection/XPIA mitigation), private VNet isolation (with hosted agents
  supporting bring-your-own VNet, each session in a VM-isolated sandbox), and RBAC are documented as
  built-in enterprise capabilities of the Foundry platform itself — not of the Agents SDK. [DOC
  S1970]

### What replaces what (row detail also in copilot-studio-feature-map.csv)
- **Channel adapter** → Agents SDK's Activity-normalizing channel abstraction. [DOC S1971]
- **Dialogue/turn state** → Agents SDK's turn concept plus its storage backends (Blob/CosmosDB in
  the Python package); Waterfall dialogs for multi-turn logic. [DOC S1971, S1969]
- **Orchestration by an LLM with tools** → explicitly not supplied by the Agents SDK; must be
  supplied by the developer or delegated to Foundry Agent Service / Agent Framework / Semantic
  Kernel, which the Python SDK's own description says it integrates components from. [DOC S1971,
  S1969]
- **MCP as the tool layer** → Foundry Agent Service documents this natively (toolboxes, remote MCP
  servers, Entra/OBO auth); the Agents SDK's own README does not advertise a first-class MCP client/
  server, only a Copilot-Studio-engine client. [DOC S1970, S1969]
- **Handoff to a human** → not a built-in Agents SDK feature; comparable to Copilot Studio's
  Transfer-conversation-node/Omnichannel integration (S1972), would need custom code against an
  external engagement-hub API. [DER from S1972, S1971]
- **Content safety** → not addressed in the Agents SDK docs fetched; documented only as a Foundry
  Agent Service platform feature. [DOC S1970]
- **ALM** → the Agents SDK is plain source code, so git + CI is its natural ALM path, unlike Copilot
  Studio's Power-Platform-solution/pipeline model (S1967) — for a team whose change record is a merge
  request with no self-approval and one CI script per trigger, plain source code under git is a strictly
  better fit than a solution-based ALM model. [DER S1967: solution-based ALM vs source code]

- **Billing** → Copilot Studio bills standard-harness agents in Copilot Credits (since 2025-09-01), with usage by Microsoft 365 Copilot-licensed users inside Microsoft 365 Copilot zero-rated. [DOC S1961]
- **Custom MCP server** → Copilot Studio's own guidance builds one with an MCP SDK from `github.com/modelcontextprotocol`, with optional API-key or OAuth 2.0 authentication. [DOC S1965]
- **Governance** → Copilot Studio puts MCP connectors under Power Platform data policies like any other connector. [DOC S1974]
- **SSO on a custom canvas** → Copilot Studio already needs two separate Entra app registrations, a custom scope, a token-exchange URL and MSAL code in the canvas. [DOC S1966]
- **Channels and surfaces** → Copilot Studio publishes to Teams, Microsoft 365 Copilot, websites, SharePoint and Azure Bot Service channels, can be blocked per channel by admins, and accepts no user attachments on any channel; an agent for Microsoft 365 Copilot is a declarative agent that is not auto-deployed and can be downloaded as a .zip for the Teams or org catalog. [DOC S1977, S1975]

### Serving both a CLI agent and a Teams front from one MCP server (design tension)
- Copilot Studio's MCP onboarding wizard (S1964) and Foundry Agent Service's remote-MCP support
  (S1970) both connect to *any* MCP server that speaks Streamable HTTP with API-key/OAuth 2.0 (or
  Entra/OBO, for Foundry) authentication. In principle the same MCP tool definitions written for a
  stdio CLI agent could be exposed a second time to a Teams-facing agent this way, **without**
  changing the tool implementations — only the transport (stdio vs. network) and auth layer would
  differ. [DER S1964, S1970: both accept any Streamable HTTP MCP server]
- **Tension with a "no always-on service" rule**: a stdio-only MCP server, launched as a subprocess of
  the engineer's own agent session, with "no always-on service, no public endpoint and no gateway,"
  cannot be reached from Copilot Studio or Foundry (a cloud-hosted caller) without exactly the
  always-on, network-facing component such a rule forbids. This is a general fact about what opening a
  remote-MCP path would need to supply, not a recommendation to open it. [DER from S1964, S1970]
- **Tension with a "container-ready, not containerized" rule**: Foundry hosted agents run as containers
  with a managed endpoint (S1970); a design that stays container-ready but not containerized, with no
  image, chart, or broker built, would cross that boundary the moment its tool set lands on Foundry
  hosted agents, or on an Azure-hosted Agents SDK bot (the conventional Bot-Framework-era deployment
  target). [DER from S1970]

## Reference
- Feature-by-feature replacement mapping: `agents/copilot-studio-feature-map.csv`.
- Quota/billing/DLP/ALM facts underlying the "leaving Copilot Studio" cost comparison:
  `agents/copilot-studio-inventory.md`.
- Full QG17-QG20 answers with citations: `_parts/agents-copilot/answers.md`.
- `entra/agent-id.md`: depth on the Entra agent identities and blueprints Foundry Agent Service (per
  project and per published agent) and Copilot Studio (per agent, shared tenant blueprint) create
  automatically for the products this article covers.
- `agents/microsoft-agent-framework.md`: depth on the **Agent Framework** named above as one of the
  bring-your-own-container options for Foundry hosted agents — its `ChatAgent`/`Agent` abstraction,
  MCP tool client types (`MCPStdioTool`, `MCPStreamableHTTPTool`, `MCPWebsocketTool`), graph-based
  Workflows with checkpointing/human-in-the-loop, and migration paths from Semantic Kernel and
  AutoGen.
- `agents/foundry-agent-service.md`: depth on Foundry Agent Service itself — the full tool/toolbox
  catalogue (MCP `require_approval` enforcement, tool search, Skills), Basic/Standard/BYO-VNet setup
  tiers, the 2026 RBAC role rename, and fixed quotas/limits.

## Examples
- A hypothetical Teams front for a device-management CLI: an engineer's Teams message ("check
  `PL-LT-00123` compliance") would need (a) an Entra-registered bot identity (crossing the
  "no always-on service" boundary), (b) an Agents SDK Teams channel adapter normalizing the Teams
  `Activity`, and (c) the same tool-calling logic the CLI already has, reached either directly or via
  a network-exposed MCP endpoint (crossing the same boundary as (a)). No such deployment exists; this
  illustrates the architecture gap only, using an example hostname per the texts regime.
