---
topic: agents/copilot-studio-inventory
priority: P1
applies_to: "Microsoft Copilot Studio (standard harness, GitHub Copilot harness, Copilot chat harness), docs current 2026-09-25"
retrieved_utc: 2026-09-26
sources: [S1960, S1961, S1962, S1963, S1964, S1965, S1966, S1967, S1972, S1973, S1974, S1975, S1977, S1978, S1979, S1980, S1981, S1982, S1983, S1984]
status: complete
files: [agents/copilot-studio-feature-map.csv]
---

# Copilot Studio feature inventory

## Summary
- Copilot Studio ships three "harnesses" (execution engines): **GitHub Copilot harness**
  (reasoning-heavy multi-step), **standard harness** (rule-based topics, most features below), and
  **Copilot chat harness** (extends Microsoft 365 Copilot Chat with tenant knowledge). Harness
  choice changes billing and available features. [DOC S1962]
- Every agent is billed in **Copilot Credits** (renamed from "messages" 2025-09-01), sold as
  pay-as-you-go, a one-year prepurchase plan, or prepaid packs; unused credits don't roll over, and
  exceeding capacity triggers a hard stop after admin-configured notification thresholds. [DOC
  S1960, S1961]
- Feature limits (topics, knowledge sources, tools, connector payloads) are all documented as fixed
  numbers on one Microsoft Learn quotas page, not scattered guesses. [DOC S1960]
- MCP is a first-class tool type: Copilot Studio's onboarding wizard connects to any MCP server over
  Streamable HTTP (SSE dropped after August 2025) with API-key or OAuth 2.0 auth, and access is
  governed by the same Power Platform data-loss-prevention (DLP) policies as any other connector.
  [DOC S1964, S1974]
- Full feature-by-feature detail, with replacement components for an own-code chatbot, is in
  `agents/copilot-studio-feature-map.csv` (31 rows).

## Facts

### Topics, orchestration, instructions
- Topics are authored on a visual canvas or in a **YAML code editor** (`kind: AdaptiveDialog`,
  nodes, conditions, redirects); YAML can be copy-pasted between topics/agents, but Microsoft warns
  that syntax errors can break the conversation and its own support "can't help remediate code
  editor errors." [DOC S1963]
- **Generative orchestration** adds an LLM planning layer that selects the best combination of
  topics/tools/knowledge per turn, can auto-fill topic inputs from conversation context, and
  generates clarifying questions; it caps SharePoint knowledge sources at 25 site URLs/agent when
  active. [DOC S1960, S1962]
- Agent-level **instructions** are capped at 8,000 characters. [DOC S1960]
- Up to 1,000 topics/agent in Dataverse environments (250/agent in Dataverse for Teams before
  upgrade); 200 trigger phrases/topic. [DOC S1960]

### Knowledge sources
- Up to 500 knowledge sources/agent across all types. [DOC S1960]
- SharePoint (fully integrated): modern pages only, DOC/DOCX/PPT/PPTX/PDF file types, 512 MB/file,
  page-level PDF citations only for the "Upload files > SharePoint" path, list queries limited to
  the first 2,048 rows and 15 lists/35,000 rows total (max 120,000 rows across lists). [DOC S1960]
- OneDrive and upload-SharePoint unstructured sources: up to 1,000 files, 50 folders, 10 subfolder
  levels per source, 512 MB/file, 4-6 hour sync latency; documents with *confidential*/*highly
  confidential* sensitivity labels or password protection are silently excluded (show "Ready" but
  never answer). [DOC S1960]
- Dataverse: max 2 sources/agent, 15 tables/source, requires maker READ permission on every table.
  [DOC S1960]
- Salesforce, Confluence, ServiceNow, Zendesk: no documented article-count or size limit; 4-6 hour
  sync. All unstructured sources require per-user, at-runtime authentication — "single credential
  sign-in isn't supported." [DOC S1960]

### Tools, connectors, agent flows
- Up to 100 skills (tools) per agent. [DOC S1960]
- Connector payload capped at 5 MB (450 KB in Government Community Cloud plans). [DOC S1960]
- **Agent flows** are Copilot Studio's native, deterministic ("same input always produces the same
  output") automation format, distinct from generic Power Automate flows; every action executed by
  an agent flow consumes Copilot Studio capacity. A Power Automate cloud flow can be **converted**
  into an agent flow, moving its billing onto Copilot Studio capacity — an irreversible, one-way
  operation. [DOC S1979]

### MCP servers
- Copilot Studio's MCP onboarding wizard supports two connection paths: the wizard itself (API key
  or OAuth 2.0 — dynamic discovery, dynamic without discovery, or fully manual client
  ID/secret/URLs), or a custom Power Apps connector built from an OpenAPI schema describing the MCP
  endpoint. [DOC S1964]
- Only the **Streamable HTTP** transport is supported; SSE for MCP was dropped after August 2025
  because the MCP spec itself deprecated SSE. [DOC S1964]
- Creating a new MCP server for Copilot Studio to consume uses any language's MCP SDK from
  `github.com/modelcontextprotocol`; authentication is again API key or OAuth 2.0, registered with
  an identity provider. [DOC S1965]
- MCP servers are certified through the same Microsoft connector-certification program as other
  third-party connectors before being made available tenant-wide (preview at time of retrieval).
  [DOC S1981]
- Access to any MCP server in Copilot Studio is regulated by **Power Platform data policies**
  exactly like any other Power Platform connector — MCP connectors are one of the connector classes
  (certified, custom, virtual, MCP) that DLP can block. [DOC S1964, S1974]

### Adaptive cards and channels
- Rendering of surveys/multiple-choice options is channel-dependent: a full adaptive card on a
  custom website, text-only in Teams and Facebook, a hero card with up to 6 options in Teams, and
  partial support in Omnichannel for Customer Service. [DOC S1977]
- Publish channels: Custom Website, Demo Website, Microsoft Teams, Microsoft 365 Copilot,
  SharePoint, WhatsApp, Mobile App, Facebook, and Azure Bot Service channels (Cortana, Slack,
  Telegram, Twilio, Line, Kik, GroupMe, Direct Line Speech, Email). Admins can block individual
  channels via **Agent access channels** in the Power Platform admin center or via DLP. [DOC S1977]
- Attachments/uploads from the user are never processed by the agent conversation itself, on any
  channel, even where the channel technically supports attachments. [DOC S1977]

### Authentication and SSO
- Agents default to **Authenticate with Microsoft** — automatic Entra ID SSO for Teams, Power Apps,
  and Microsoft 365 Copilot with no manual setup. **No authentication** allows anyone with the link
  to chat but disables tools that need user credentials. **Authenticate manually** supports other
  channels while keeping authentication. [DOC S1977]
- Full custom-canvas SSO needs **two separate Entra app registrations** (an authentication app and a
  canvas app — reuse of one registration for both is explicitly disallowed), a defined custom scope,
  a token-exchange URL configured in Copilot Studio's Security > Authentication settings, and MSAL
  wiring in the canvas's client-side code. [DOC S1966]
- SSO is **not** supported on Azure Bot Service channels, the Demo Website, Facebook, Mobile App, or
  Power Apps portals; Teams SSO is Entra-ID-only (no third-party IdP). [DOC S1966]

### Variables, state, handoff, analytics
- Variables are topic-scoped by default (with explicit "receive from"/"return to" flags for passing
  values across topic redirects) or promoted to bot-scoped **global variables** (one-way promotion,
  no demotion back to topic-scoped). Environment variables can reference Azure Key Vault secrets;
  the dialog runtime caches a successful secret read for 5 minutes and a failed read for 30 seconds.
  A **Parse value** node converts untyped JSON/event payloads (including channel-specific
  `System.Activity.ChannelData`) into typed Record variables. [DOC S1978]
- **Handoff** to a human agent is implicit (agent can't match intent) or explicit (a **Transfer
  conversation** node); the full conversation history plus named context variables (`va_Scope`,
  `va_LastTopic`, `va_LastPhrases`, `va_AgentMessage`, `va_ConversationId`, `va_BotId`,
  `va_Language`, and user-defined topic variables) are sent to the connected engagement hub (for
  example Dynamics 365 Omnichannel); escalated sessions are tagged in analytics. Omnichannel's ACS
  channel enforces a 28 KB message-size limit on the handoff payload. [DOC S1972]
- **Analytics** ("Monitor" page) separates conversational-session metrics (daily/monthly active
  users, resolved/escalated/abandoned outcomes, per-topic charts, satisfaction score) from
  event-triggered ("autonomous agent") session metrics; data is retained up to 360 days,
  transcripts for 28 days, all timestamps in UTC; active-user metrics require the agent to require
  authentication. [DOC S1973]

### ALM, DLP, quotas, billing
- Every Copilot Studio agent belongs to a **Power Platform solution**; the in-app solution manager
  (GA 2024-12-16) can view/export/import solutions and drive **pipeline deployments** across
  environments without leaving Copilot Studio. [DOC S1967]
- Power Platform **data policies** (DLP) gate connectors — certified, custom, "virtual" (Copilot-
  Studio-specific on/off switches), and MCP — at both design time (blocks saving in the maker
  experience) and runtime (suspends/quarantines running apps, flows, chatbots; disables blocked
  connections). Propagation of a policy change takes "in most cases within an hour," up to 24 hours
  in extreme cases. Copilot Studio virtual connectors are migrating to their own dedicated
  governance rules, separate from classic DLP and from Advanced Connector Policies. [DOC S1974]
- Message-throughput **quotas** scale with prepaid-pack tier: 50 RPM/1,000 RPH at 1-10 packs, up to
  100 RPM/2,000 RPH at 51-150 packs, +1 RPM/+20 RPH per extra 10 packs above 150; trial/developer
  environments are capped at 10 RPM/200 RPH; pay-as-you-go and Microsoft 365 Copilot-licensed usage
  are both fixed at 100 RPM/2,000 RPH. A flat 8,000 RPM quota covers *all* messages to an agent
  (including Bot Framework skill calls). [DOC S1960]
- Since **2025-09-01** the billed unit is **Copilot Credits**, replacing "messages" with no change
  to per-pack quantity or the pay-as-you-go rate. Usage inside Microsoft 365 Copilot (classic/
  generative answers, tenant graph grounding in Teams/SharePoint/Copilot Chat) for
  Microsoft-365-Copilot-licensed users is zero-rated against the Copilot Studio pack/meter. [DOC
  S1961]

### Publishing into Microsoft 365 Copilot
- Copilot Studio distinguishes a **custom agent** (built from scratch, any channel including Teams/
  M365 Copilot) from an **agent for Microsoft 365 Copilot** ("declarative agent" in Microsoft 365
  Copilot terminology — instructions plus knowledge, authored from a dedicated page, not
  auto-deployed when published). [DOC S1975]
- Publishing an agent for Microsoft 365 Copilot provisions a bot resource in the tenant's Entra ID
  environment; availability options are a shareable deep link, sharing to named users/security
  groups, submission to the org catalog, or **download as a .zip** for manual admin upload/review —
  the .zip is the closest thing to a portable export artifact for this agent type. [DOC S1975]

## Reference
- Full row-by-row feature/limit/replacement table: `agents/copilot-studio-feature-map.csv` (31 rows,
  columns: feature, what it does, limits, licence/billing, replacement component in own code, effort
  notes, sources).
- Migration paths (export formats, SDKs, retirement dates) are in
  `agents/own-chatbot-architecture.md`, QG18/QG19 material.
- Declarative-agent manifest schema (capabilities, actions/plugins, MCP-server actions and MCP apps),
  Copilot connectors, custom engine agents, admin agent registry, and Copilot extensibility licensing
  tiers: `agents/m365-copilot-extensibility.md` (this article does not repeat that manifest schema or
  those licensing tiers).

## Examples
- An example scenario: an agent for engineers asking about an example device's compliance state,
  grounded on a Dataverse knowledge source mirroring a subset of a device inventory record, with a
  tool calling a stdio MCP server (if it were exposed over network transport) instead of the
  management API directly — illustrates the MCP-onboarding-wizard path (DOC S1964) against a
  hypothetical MCP server, not a real deployment.
