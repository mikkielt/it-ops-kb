---
topic: agents/foundry-agent-service
priority: P1
applies_to: "Microsoft Foundry Agent Service (GA runtime; Toolbox tool search/Skills, voice-based prompt agents, Work IQ, Agent Optimizer preview), Azure AI Projects SDK, docs current 2026-09-26"
retrieved_utc: 2026-09-26
sources: [S-hkoalitj, S-yutqeaay, S-3axje6py, S-wy457poi, S-5ygcb6vm, S-f5p5qi4d, S-k3l2irzl, S-gessjq23, S-kub3e5bx, S-5tsg2rir, S-23bcmfv4, S-all62inb, S-jgc6ne22, S-6ysoloif]
status: complete
files: [agents/foundry-agent-tools.csv]
---

# Microsoft Foundry Agent Service (in depth)

Extends `agents/own-chatbot-architecture.md` (:20,:61-:80: the three agent types, native MCP support,
publishing protocols, A2A v1.0, enterprise capabilities at a glance -- not repeated here), and does not
repeat `entra/agent-id.md` (Entra Agent ID platform: agent identities, blueprints, Conditional Access, ID
Protection, governance -- Foundry is only the *consumer* of that platform here) or
`agents/microsoft-agent-framework.md` (the framework used to build hosted-agent code). This article
covers the tool catalogue, toolboxes, threads/runs vs. Responses API, BYO-resources setup tiers, RBAC,
quotas/limits, and a runnable MCP-tool example.

## Summary
- Three agent types (prompt, voice-based prompt, hosted) share one **Agent Runtime**; the newest surface
  is the **Responses API** used directly for *ephemeral agents* whose definition lives in application
  code instead of as a persisted Foundry resource. [DOC S-hkoalitj]
- Tools are catalogued individually (MCP, web search, Azure AI Search, code interpreter, file search,
  OpenAPI, A2A, browser automation, Fabric IQ, Work IQ, function calling, Bing grounding, computer use,
  image generation, SharePoint, Fabric data agent, Azure Functions) and a subset can be bundled into a
  **Toolbox**: one MCP-compatible endpoint with centralized auth, governance, and versioning. Full
  per-tool status/auth/limits table: `agents/foundry-agent-tools.csv`. [DOC S-yutqeaay]
- MCP `require_approval` is enforced by the *calling runtime*, never by the toolbox/MCP endpoint itself:
  the endpoint does not block `tools/call` even when a tool is marked `always`. [DOC S-5ygcb6vm, S-3axje6py]
- Three deployment tiers trade managed convenience for data control: **Basic** (Microsoft-managed
  storage), **Standard** (BYO Azure Storage + Azure AI Search + Azure Cosmos DB, all in the customer's
  tenant), **Standard with BYO VNet** (adds full network isolation). [DOC S-5tsg2rir]
- Foundry RBAC roles were renamed in 2026 (old name -> new name, same role IDs): **Azure AI User ->
  Foundry User**, **Azure AI Owner -> Foundry Owner**, **Azure AI Account Owner -> Foundry Account
  Owner**, **Azure AI Project Manager -> Foundry Project Manager**; a fifth role, **Foundry Agent
  Consumer**, is new and is the least-privileged role for principals that only call agent endpoints. [DOC
  S-k3l2irzl]
- Fixed, non-increasable Agent Service limits: 128 tools per agent, 1,000 versions per agent, 100,000
  messages per thread, 10,000 files per agent/thread, 512 MB per file, 300 GB total uploaded files per
  account, 2,000,000 tokens per file for vector-store attachment, 1,500,000 characters per message. [DOC
  S-f5p5qi4d]

## Facts

### Agent types and the Responses API
- **Prompt agents**: instructions + model + tools, authored in the portal or via SDK/REST for CI/CD; no
  code or infrastructure to manage; Foundry auto-scales and snapshots a new version on every change. [DOC
  S-hkoalitj]
- **Voice-based prompt agents**: managed real-time speech via **Voice Live**; two architectures --
  native speech-to-speech (lowest latency) and a cascaded text-model pipeline (speech recognition -> text
  model -> speech synthesis, more control but more latency). In **preview**, including related
  monitoring/evaluation/avatar/WebRTC/telephony capabilities; max voice session duration **60 minutes**;
  stored voice conversations retained **60 days**. [DOC S-hkoalitj, S-f5p5qi4d]
- **Hosted agents**: bring your own code/container (or a .zip that Foundry builds into an image) using
  Agent Framework, LangGraph, the OpenAI Agents SDK, the Anthropic Agent SDK, the GitHub Copilot SDK, or
  custom code; Foundry gives it a managed endpoint, autoscaling per session and request volume, a
  dedicated Entra identity, session-level state persistence, and end-to-end observability. Concurrent
  hosted-agent sessions per subscription+region: **2,000** in Canada Central, East US 2, Japan East,
  North Central US, South Africa North, Southeast Asia, Sweden Central; **1,000** everywhere else hosted
  agents are available; an idle/stopped session keeps its state but doesn't count toward the quota. [DOC
  S-hkoalitj, S-f5p5qi4d]
- **Ephemeral agents via the Responses API**: calling the Responses API directly assembles the agent
  (instructions, tools, model) in the caller's own process per call -- nothing is created/updated/deleted
  as a Foundry resource -- while still getting catalog models, platform tools, project-scoped data, OBO
  auth, and project-level observability/governance through the Foundry project endpoint. [DOC S-hkoalitj]
- Compare-table highlights: only hosted agents get an *automatic, per-agent-dedicated* Entra identity;
  prompt and voice agents get project-level Entra identity; only hosted agents bill for container
  compute in addition to inference + tool usage. [DOC S-hkoalitj]

### Toolboxes
- A toolbox is a Foundry-managed, versioned, curated set of tools exposed behind **one MCP-compatible
  endpoint**; any MCP-compatible runtime can consume it, not only Foundry-hosted agents (Agent Framework,
  LangGraph, GitHub Copilot, etc.). [DOC S-yutqeaay]
- Four pillars: **Build** (define tools/skills once, central auth), **Discover** (tool search, preview),
  **Consume** (single endpoint, cross-protocol/cross-auth), **Govern** (guardrails, observability,
  versioning applied at the toolbox level). [DOC S-yutqeaay]
- **Tool search (preview)**: hides individual tools by default and exposes two meta-tools, `tool_search`
  (describe what's needed, get back relevant tools) and `call_tool` (invoke a discovered tool by name);
  addresses token cost and degraded selection accuracy once a toolbox holds "dozens or even hundreds" of
  tools; supports pinning critical tools and auto-pinning frequently used ones. [DOC S-yutqeaay]
- **Skills (preview)**: package reusable, versioned, **immutable** multi-step workflows that agents
  discover and load automatically via MCP resources at startup; "tools define what an agent can do,
  skills define how it performs a task." [DOC S-yutqeaay]
- Versioning: create and test a new toolbox version, then **promote it to `default_version`**; every
  agent pointed at the toolbox picks up the promoted version automatically with no redeploy. [DOC
  S-yutqeaay, S-3axje6py]
- A toolbox enumerates all its tool sources together at startup; one failing/unavailable MCP server or
  invalid allowed-tool name can block readiness for the whole toolbox -- fix or remove that source,
  create a new version, and promote it. Connecting a hosted agent to the toolbox and troubleshooting a
  `401`/`403` from a tool means checking two separate authorization boundaries: the agent-to-toolbox
  identity, and the downstream auth configured on that tool's project connection. [DOC S-3axje6py,
  S-wy457poi]
- SDK: `project.toolboxes.create_version(name=..., tools=[MCPToolboxTool(server_label=..., server_url=...,
  require_approval=..., project_connection_id=...)])`; a toolbox's consumer endpoint is
  `{PROJECT_ENDPOINT}/toolboxes/{name}/versions/{version}/mcp?api-version=v1` (or the unversioned default
  endpoint). [DOC S-3axje6py]

### MCP tool and require_approval
- Connecting a remote MCP server needs `server_url`, a unique `server_label`, an optional `allowed_tools`
  allow-list (default: every tool the server exposes), an optional `project_connection_id` (stores the
  server's auth), and `require_approval` (default **`always`**; other values: `never`, or a
  `{"never":[...]}` / `{"always":[...]}` per-tool override list). [DOC S-5ygcb6vm]
- The toolbox/MCP endpoint **never blocks `tools/call`** based on `require_approval`; enforcement --
  pausing the call, presenting name+arguments to a human, resuming or rejecting -- is entirely the calling
  agent runtime's responsibility. A system-prompt instruction alone does not enforce approval. [DOC
  S-5ygcb6vm, S-3axje6py]
- When approval is required, the model's attempt to call the tool surfaces as an `mcp_approval_request`
  output item (Responses API) carrying the server label, tool name, and arguments; the caller reviews it
  and replies with an `mcp_approval_response` (`approve: true/false`) referencing that request's id via
  `previous_response_id`. [DOC S-5ygcb6vm]
- Documented best practices for MCP tools: allow-list with `allowed_tools`; treat tool descriptions,
  annotations, and results from remote MCP servers as **untrusted input** (possible indirect prompt
  injection); require approval for high-risk (write/state-changing) operations specifically; re-review
  `allowed_tools`/approval/connection permissions whenever the server's operator or exposed tools change;
  log every approval and tool call for audit. [DOC S-5ygcb6vm]
- Custom MCP servers can be hosted on **Azure Functions** via the Functions MCP webhook endpoint
  `/runtime/webhooks/mcp` and consumed the same way as any other remote MCP server. [DOC S-hkoalitj]
- Authentication for MCP/tool connections: key-based, Microsoft Entra (the agent's or the project's
  managed identity), OAuth identity passthrough (On-Behalf-Of), or unauthenticated where appropriate;
  when the tool sits behind a Toolbox, the Toolbox itself handles credential injection and token refresh
  at runtime (agents authenticate to the Toolbox endpoint with Entra, e.g. `DefaultAzureCredential`, and
  need not hold per-tool credentials). [DOC S-hkoalitj, S-5ygcb6vm]
- Third-party remote MCP servers are outside Microsoft's testing/verification and are governed by the
  caller's own terms with that provider; a Foundry Toolbox, by contrast, is an organization-governed
  resource the customer creates and curates, but the customer remains responsible for tool selection,
  data handling and compliance of what it puts in the toolbox. [DOC S-5ygcb6vm]

### Multi-agent, hosted agents, and A2A
- A2A: Foundry Agent Service supports the generally-available **A2A protocol v1.0** (JSON-RPC) and a
  preview **v0.3**; text modality only, no streaming responses on v1.0. Exposing a Foundry agent as an
  inbound A2A endpoint requires the **Responses protocol** (prompt agents support it by default) and
  publishes an agent card; the calling identity needs the **Foundry Agent Consumer** role or higher on
  the target project. Creating the A2A project connection itself needs **Foundry Project Manager**. [DOC
  S-all62inb]
- Hosted agents get an **automatic, dedicated** Entra identity per agent (vs. prompt/voice agents, whose
  identity is scoped to the project); that identity can authenticate to external MCP servers, including
  ones on Azure Functions, and supports OAuth OBO passthrough when configured. [DOC S-jgc6ne22,
  S-hkoalitj]
- azd (Azure Developer CLI) automates only a slice of hosted-agent identity setup: for development it
  auto-assigns **Foundry User** to the shared project agent identity of unpublished agents; it does not
  configure Container Registry, Application Insights, or custom-resource permissions, and published
  agents (which get their own distinct identity) require manual role assignment. [DOC S-jgc6ne22]
- Microsoft Agent Framework's `FoundryChatClient`/`FoundryToolbox` (package `agent-framework-foundry`) is
  the documented way to attach a Foundry Toolbox's MCP endpoint to a Framework-based hosted agent; see
  `agents/microsoft-agent-framework.md` for the Framework itself. [DOC S-6ysoloif]

### BYO resources / deployment tiers
- **Basic setup**: compatible with the OpenAI Assistants API surface; agent state (files, threads, vector
  stores) lives in Microsoft-managed, logically-separated storage; default when no BYO resources are
  configured. [DOC S-5tsg2rir, S-f5p5qi4d]
- **Standard setup**: same capabilities plus full BYO -- **Azure Storage** (files/uploads), **Azure AI
  Search** (vector stores), **Azure Cosmos DB** (threads/messages/agent metadata) -- all in the
  customer's own tenant/subscription, for compliance and CMK support. [DOC S-kub3e5bx, S-5tsg2rir]
- **Standard with BYO Virtual Network**: adds full network isolation (Private Network Isolation / secured
  outbound); inbound secured communication (private endpoint, disabled public access) can be layered onto
  any tier. [DOC S-5tsg2rir]
- Cosmos DB for a Standard setup needs **>= 3,000 RU/s** total throughput (Provisioned or Serverless);
  the current ("New") Agent Service runtime provisions two containers at 1,000 RU/s each
  (`agent-definitions-v1`, `run-state-v1`); the deprecated Classic runtime used three different containers
  (`thread-message-store`, `system-thread-message-store`, `agent-entity-store`) -- the two runtimes use
  **different** Cosmos containers and are not interchangeable. [DOC S-kub3e5bx]
- Standard setup enforces project-level data isolation by default: two blob containers (files;
  intermediate chunks/embeddings) and three Cosmos containers (user threads, system messages, agent
  config) are auto-provisioned per project. [DOC S-kub3e5bx]
- Capability-settings-managed resource connections are **immutable while in use**: you cannot edit/delete
  them directly or update capability settings on an existing project -- changing which resources a
  project uses means deleting and recreating the project. [DOC S-kub3e5bx]
- There is **no upgrade path** from a hub-based project or from Azure OpenAI Assistants to a Foundry
  project/agent: existing files, conversations, and vector stores do not migrate automatically. [DOC
  S-23bcmfv4]
- Environment prerequisites: creating the account/project needs **Foundry Account Owner** at subscription
  scope; configuring a Standard setup additionally needs `Microsoft.Authorization/roleAssignments/write`
  (the **Role Based Access Control Administrator** built-in role, or subscription **Owner**) to assign
  roles to Cosmos DB, Azure AI Search, and Blob Storage. [DOC S-5tsg2rir]

### RBAC (renamed 2026)
- Role rename (IDs and permissions unchanged): **Azure AI User -> Foundry User**, **Azure AI Owner ->
  Foundry Owner**, **Azure AI Account Owner -> Foundry Account Owner**, **Azure AI Project Manager ->
  Foundry Project Manager**. A new least-privilege role, **Foundry Agent Consumer**, grants only
  "interact with agent endpoints" (no create/manage). [DOC S-k3l2irzl]
- Role definition GUIDs (stable across the rename): Foundry User `53ca6127-db72-4b80-b1b0-d745d6d5456d`;
  Foundry Owner `c883944f-8b7b-4483-af10-35834be79c4a`; Foundry Account Owner
  `e47c6f54-e4a2-4754-9501-8e0985b135e1`; Foundry Project Manager
  `eadc314b-1a2d-4efa-be10-5d325db5065e`; Foundry Agent Consumer
  `eed3b665-ab3a-47b6-8f48-c9382fb1dad6`. Use the GUID, not the name, in code while the rename rolls out.
  [DOC S-k3l2irzl]
- Permission matrix highlights: only **Foundry Project Manager**+ can publish agents; only **Foundry
  Account Owner**/**Foundry Owner** can create Foundry accounts; **Foundry Agent Consumer** can only
  interact with agent endpoints (no data-plane build/develop access); Azure **Owner**/**Contributor** can
  create projects/accounts and manage models but **cannot** interact with agent endpoints or do
  data-plane "build and develop" actions -- those need a Foundry-specific role. [DOC S-k3l2irzl]
- **Scopes**: Foundry resource, Foundry project, and (new) **individual agent**. An agent-scope role
  assignment is currently evaluated **only for agent endpoint access** -- it grants no broader
  control-plane permission -- letting an admin grant `Foundry Agent Consumer` on one agent without
  exposing every agent in the project. The Azure portal only supports assigning Foundry Agent Consumer at
  account scope; project/agent scope requires the Azure CLI. [DOC S-k3l2irzl]
- Recommended enterprise mapping: IT admin = Owner (subscription); managers = Foundry Account Owner
  (resource); team leads = Foundry Project Manager (resource); developers = Foundry User (project) +
  Reader (resource); agent consumers/end users = Foundry Agent Consumer (project or agent scope). [DOC
  S-k3l2irzl]
- Hosted-agent-specific roles referenced separately: **Foundry Agent Consumer** (interact with agent
  endpoints, least privilege) and **Foundry User** (create agents, run inference, interact with agents);
  ARM-plane **Owner**/**Contributor**/**Role Based Access Control Administrator** are needed alongside
  them to create/manage the underlying Azure resources. [DOC S-gessjq23]
- Don't use **Azure AI Developer** for Foundry work: despite the name it scopes to Azure ML
  workspaces/Foundry *hubs*, not Foundry projects or hosted agents. [DOC S-k3l2irzl]

### Quotas and limits (fixed, not increasable except where noted)
- Per-agent/thread: **128** tools registered per agent; **1,000** versions per agent; **10,000** files per
  agent/thread; **512 MB** max single file size; **300 GB** max total uploaded files per account;
  **2,000,000 tokens** max file size for vector-store attachment; **100,000** messages per thread;
  **1,500,000 characters** max `text` content per message. [DOC S-f5p5qi4d]
- These Agent Service limits (files, messages, tools) are **fixed and cannot be increased** -- the
  documented mitigation is application design (rotate threads, keep files small, register only needed
  tools), not a support request. [DOC S-f5p5qi4d]
- What **can** be increased via an Azure support request: model deployment quota, and the concurrent
  hosted-agent-session limit (2,000 in named regions / 1,000 elsewhere). [DOC S-f5p5qi4d]
- Error codes for limit breaches: `file_size_exceeded` (400), `token_limit_exceeded` (400),
  `message_limit_exceeded` (400), `content_size_exceeded` (400), `tool_limit_exceeded` (400),
  `rate_limit_exceeded` (429); model-level 429s can also surface as `session_quota_exceeded` or
  `regional_session_quota_exceeded`. [DOC S-f5p5qi4d]
- Model call rate limits are enforced at the **model deployment** level (Azure OpenAI / Foundry Models
  quotas), not by Agent Service itself. [DOC S-f5p5qi4d]
- Tool availability varies by model and region (e.g. file search is unavailable in Italy North and Brazil
  South for some models); check the tool-support-by-region-and-model table before deploying. [DOC
  S-f5p5qi4d]

## Reference
| Concept | GA / preview | Key constraint | Source |
|---|---|---|---|
| Prompt agent | GA | no code/infra; project-scoped Entra identity | S-hkoalitj |
| Voice-based prompt agent | preview | 60 min/session, 60-day audio retention | S-hkoalitj, S-f5p5qi4d |
| Hosted agent | GA | dedicated per-agent Entra identity; container compute billed | S-hkoalitj |
| Toolbox | GA (tool search, Skills: preview) | 1,000 versions/agent cap applies | S-yutqeaay |
| MCP tool `require_approval` | GA | enforced by caller, not the endpoint | S-5ygcb6vm |
| A2A | v1.0 GA, v0.3 preview | text-only, no streaming | S-all62inb |
| Standard setup (BYO storage/search/Cosmos) | GA | Cosmos >= 3000 RU/s | S-kub3e5bx |

- Related: `agents/own-chatbot-architecture.md` (three agent types overview, A2A/publishing protocols --
  see its own Foundry section for what is not repeated here), `agents/microsoft-agent-framework.md`
  (`FoundryChatClient`/`FoundryToolbox` for hosted agents), `entra/agent-id.md` (the Entra Agent ID
  platform that provisions Foundry's per-project and per-published-agent identities and blueprints),
  `agents/azure-openai-deployments.md` (the underlying model-deployment layer: deployment types, quota/
  rate limits, provisioned throughput, API versions, auth/networking -- not repeated here).

## Examples
- Create a prompt agent with an MCP tool (`require_approval: "always"`) using the Azure AI Projects
  Python SDK, and process the resulting approval request (adapted from the documented sample; placeholder
  endpoint and connection name):
  ```python
  import json
  from azure.identity import DefaultAzureCredential
  from azure.ai.projects import AIProjectClient
  from azure.ai.projects.models import PromptAgentDefinition, MCPTool
  from openai.types.responses.response_input_param import McpApprovalResponse, ResponseInputParam

  PROJECT_ENDPOINT = "https://foundry-PL-SRV-0042.ai.azure.com/api/projects/project-PL-SRV-0042"
  MCP_CONNECTION_NAME = "my-mcp-connection"

  project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())
  openai = project.get_openai_client()

  tool = MCPTool(
      server_label="api-specs",
      server_url="https://mcp.corp.example.com/mcp",
      require_approval="always",
      project_connection_id=MCP_CONNECTION_NAME,
  )

  agent = project.agents.create_version(
      agent_name="MyAgent7",
      definition=PromptAgentDefinition(
          model="gpt-5-mini",
          instructions="Use MCP tools as needed",
          tools=[tool],
      ),
  )

  conversation = openai.conversations.create()
  response = openai.responses.create(
      conversation=conversation.id,
      input="What is my username in my GitHub profile?",
      extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
  )

  # Every pending mcp_approval_request must be reviewed and answered before the run continues.
  input_list: ResponseInputParam = []
  for item in response.output:
      if item.type == "mcp_approval_request" and item.id:
          print(f"Approve {item.server_label} tool call?", getattr(item, "arguments", None))
          input_list.append(
              McpApprovalResponse(type="mcp_approval_response", approve=True, approval_request_id=item.id)
          )

  response = openai.responses.create(
      input=input_list,
      previous_response_id=response.id,
      extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
  )
  project.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
  ```
- Assigning the least-privilege **Foundry Agent Consumer** role at a single agent's scope (Azure CLI),
  so a service principal can call one agent's endpoint without seeing the rest of the project:
  ```bash
  AGENT_SCOPE="/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-PL-SRV-0042/providers/Microsoft.CognitiveServices/accounts/foundry-PL-SRV-0042/projects/project-PL-SRV-0042/agents/MyAgent7"

  az role assignment create \
      --assignee-object-id "<service-principal-object-id>" \
      --assignee-principal-type ServicePrincipal \
      --role "eed3b665-ab3a-47b6-8f48-c9382fb1dad6" \
      --scope "$AGENT_SCOPE"
  ```
