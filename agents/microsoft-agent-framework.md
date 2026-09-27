---
topic: agents/microsoft-agent-framework
priority: P2
applies_to: "Microsoft Agent Framework (Python `agent-framework`, .NET `Microsoft.Agents.AI`, Go public preview); docs and GitHub retrieved 2026-09-26"
retrieved_utc: 2026-09-26
sources: [S-kzoop7qs, S-7ziha7pr, S-esun5f2n, S-lkto4w7b, S-sjqmzszi, S-j2yxzynm, S-cjxn455h, S-mhvboogr, S-do52zses, S1939, S-gs56zhuk, S-4yhrlzez, S-ayrhsrlp, S-nghojxuy, S-iblntf2w, S-fkamc745]
status: partial
---

# Microsoft Agent Framework

## Summary
- **Microsoft Agent Framework** is Microsoft's agent-building framework: the stated direct
  successor to both **Semantic Kernel** and **AutoGen**, created by the same teams, combining
  AutoGen's simple single-/multi-agent abstractions with Semantic Kernel's enterprise features
  (session state, type safety, middleware, telemetry) and adding graph-based **Workflows** for
  explicit multi-agent orchestration. [DOC S-kzoop7qs]
- A general-availability (GA) status for the framework as a whole. [UNK: not in S-kzoop7qs as
  re-read 2026-09-27; the page states only that the Go SDK is in public preview]
- Ships for **Python** (`pip install agent-framework`, package `agent-framework`, MIT licence),
  **.NET** (`Microsoft.Agents.AI`, `Microsoft.Agents.AI.Foundry`), and **Go** (`agent-framework-go`,
  public preview: declarative agents, RAG, CodeAct and functional workflows not yet available).
  [DOC S-kzoop7qs, S1939]
- Core building blocks: agents (`Agent` in Python, `AIAgent` in .NET), a
  **Harness Agent** (opinionated, batteries-included agent for long multi-step tasks: planning/todo
  tracking, context compaction, file access/memory, don't-ask-again tool approval, observability),
  **Workflows** (functional and graph-based), an agent session for state management,
  middleware, context providers for memory, and MCP clients for tool integration. [DOC S-kzoop7qs]
- Model providers documented: **Microsoft Foundry, Anthropic, Azure OpenAI, OpenAI, Ollama**, and
  others via the integrations catalogue. [DOC S-kzoop7qs]
- Not evidence of this article: exact licence terms for the .NET/Go packages beyond MIT (repo-wide);
  only the GitHub repository root licence was confirmed. [UNK]

## Facts

### Packages, licence, release cadence
- The `microsoft/agent-framework` GitHub repository is **MIT**-licensed. [DOC S1939]
- Python: `pip install agent-framework`; the experimental
  `agent-framework-lab` package is no longer installed by `agent-framework` and each Lab module is
  installed explicitly, and DevUI is the separate `agent-framework-devui` package (install with
  `--pre`). [DOC S-kzoop7qs, S-iblntf2w, S-cjxn455h]
- .NET: `dotnet add package Microsoft.Agents.AI.Foundry --prerelease` for the Foundry integration;
  `Microsoft.Agents.AI` is the core namespace package. [DOC S-kzoop7qs, S-sjqmzszi]
- Go: `go get github.com/microsoft/agent-framework-go` — marked **public preview**, with declarative
  agents, RAG, CodeAct, and functional workflows explicitly not yet available. [DOC S-kzoop7qs]
- Release tags observed on GitHub Releases (2026-09-26): Python and .NET ship on parallel,
  roughly weekly cadences with separate `python-<version>` and `dotnet-<version>` tag prefixes —
  most recent seen: `python-1.19.0` (2026-09-18) and `dotnet-1.22.0` (2026-09-18, marked latest); no
  tag was marked pre-release in the 10 most recent of each track. [DOC S-gs56zhuk] — version numbers
  and dates will drift; re-check `_tools/fetch.py --diff` before quoting a specific number.
- `agent-framework` does **not** auto-load `.env` files; call `load_dotenv()` yourself or set
  environment variables directly. [DOC S-kzoop7qs]

### Agents: ChatAgent, custom agents, sessions
- Minimal Python agent: `Agent(client=<ChatClient>, name=..., instructions=...)`, then
  `await agent.run("prompt")` for a non-streaming `AgentResponse`, or `agent.run(..., stream=True)`
  for `AgentResponseUpdate` chunks. [DOC S-kzoop7qs, S-4yhrlzez]
- .NET agents come from a chat client via `.AsAIAgent(model:, instructions:)`, returning an `AIAgent`
  (base abstraction, analogous to Semantic Kernel's `Agent`); the concrete unifying agent type across
  underlying `IChatClient`-based services is `ChatClientAgent` (replacing SK's per-service
  `ChatCompletionAgent`/`OpenAIAssistantAgent`/`AzureAIAgent`). [DOC S-sjqmzszi]
- Custom agents: Python subclasses `BaseAgent` (`pip install agent-framework-core`); .NET implements
  the `AIAgent` contract directly. A custom agent with no underlying chat client has no tools to
  invoke unless it wraps an `IChatClient`/`ChatClient` that already supports tools. [DOC S-4yhrlzez]
- State/threads: `AgentThread` (Python) holds either a service-managed thread (`service_thread_id`)
  or a local `message_store` (`ChatMessageStoreProtocol`), never both; create one via
  `agent.get_new_thread()`, never the constructor directly; thread state round-trips through
  `await thread.serialize()` / `AgentThread.deserialize(state)`. [DOC S-do52zses]
- Sessions replace Semantic Kernel's manually-typed `AgentThread` subclasses: `agent.create_session()`
  creates a new local session, `agent.get_session(service_session_id=...)` resumes a service-managed
  one; pass `session=session` to `agent.run(...)`. Neither `AgentSession` (.NET) nor `AgentThread`
  (Python) exposes a delete API — callers needing hosted-thread deletion (e.g. OpenAI Assistants) must
  track ids and delete via the provider's own SDK. [DOC S-sjqmzszi]
- Tool registration needs no decorator: pass plain functions (with an optional `Description`
  attribute in .NET) directly as `tools=[...]`, unlike Semantic Kernel's mandatory
  `[KernelFunction]`/`KernelPluginFactory`/`Kernel` wiring. [DOC S-sjqmzszi]

### MCP tool integration (Python: MCPStdioTool, MCPStreamableHTTPTool, MCPWebsocketTool)
- Three Python MCP client tool types: **`MCPStdioTool`** (local subprocess servers over stdio),
  **`MCPStreamableHTTPTool`** (HTTP/SSE remote servers), **`MCPWebsocketTool`** (WebSocket servers).
  .NET uses the official MCP C# SDK (`McpClientFactory`, `StdioClientTransport`) with tools converted
  to `AITool`/`AIFunction`; Go has an `mcptool` package with `mcptool.Connect`/`ListTools`, supporting
  HTTP/SSE (`mcp.StreamableClientTransport`) and stdio transports. [DOC S-7ziha7pr]
- On minimal Python installs, MCP support is optional: `pip install mcp --pre` for `MCPStdioTool`,
  `MCPStreamableHTTPTool`, or `Agent.as_mcp_server()`; `pip install mcp[ws] --pre` additionally for
  `MCPWebsocketTool`. [DOC S-7ziha7pr]
- `MCPStreamableHTTPTool(name=..., url=..., headers={...}, description=...)` connects to an HTTP/SSE
  MCP server; pass it (or a list of MCP tool instances) as `tools=` to an `Agent`/`ChatAgent`, and use
  it as an async context manager (`async with mcp_tool: ...`) so the session is opened and closed.
  [DOC S-esun5f2n, S-7ziha7pr]
- The HTTP client `MCPStreamableHTTPTool` builds does **not** persist response cookies by default; a
  server needing cookies for auth/session/load-balancer affinity requires passing a caller-owned,
  pre-configured `httpx.AsyncClient` via `http_client=`. [DOC S-7ziha7pr]
- Authenticated remote MCP endpoints: `static_headers` for fixed credentials, or `header_provider`
  (a callable receiving only the run's `function_invocation_kwargs`, not model-supplied tool
  arguments) for per-run dynamic values; both add headers only to same-origin requests and strip them
  on cross-origin redirects; a `header_provider` value wins over a matching `static_headers` value.
  [DOC S-7ziha7pr]
- `max_host_payload_size_bytes` (default 1 MiB) bounds the retained Host-facing MCP result payload per
  transport (e.g. for AG-UI); oversized payloads are dropped from the Host channel while the
  model-facing parsed value is unaffected. `tool_result_content` (`structured_first` default,
  `content_first`, `content_only`, `structured_only`, `both`) selects which of `content`/
  `structuredContent` the model sees. [DOC S-7ziha7pr]
- Server-initiated **MCP sampling** and `sampling_callback` are **deprecated** as of MCP spec version
  2026-07-28 and are removed no later than 2027-07-28; new integrations should not rely on them — MCP
  servers should call model-provider APIs directly instead. [DOC S-7ziha7pr]
- An agent itself can be exposed as an MCP server: Python `agent.as_mcp_server()` (needs `mcp --pre`
  on minimal installs) plus `mcp.server.stdio.stdio_server()` to serve over stdio; .NET wraps the
  agent with `.AsAIFunction()` into an `McpServerTool` registered on `AddMcpServer().WithStdioServerTransport()`.
  [DOC S-7ziha7pr]
- Microsoft's own guidance: review and log data shared with any third-party remote MCP server, prefer
  servers hosted by trusted providers over proxies, and be aware Microsoft has not tested or verified
  third-party MCP servers used with the framework. [DOC S-7ziha7pr]

### Workflows: graph model, checkpointing, human-in-the-loop
- **Workflow** is a typed, data-flow graph: executors (agents, functions, or sub-workflows) connected
  by typed edges, activated when their inputs are ready, contrasted with AutoGen's `Team`
  (control-flow, broadcast messages) and its experimental `GraphFlow`. [DOC S-lkto4w7b]
- Built-in orchestration patterns: sequential, concurrent, handoff, and group/Magentic collaboration,
  with checkpointing and streaming. [DOC S1939, S-lkto4w7b]
- **Checkpointing**: `WorkflowBuilder(checkpoint_storage=...)` with `FileCheckpointStorage` captures
  executor-local state (`ctx.set_executor_state()`), cross-executor state (`ctx.set_state()`), pending
  inter-executor message queues, and execution position; resume with
  `workflow.run(checkpoint_id=..., checkpoint_storage=..., stream=True)`, and send human responses back
  with `workflow.run(responses=..., stream=True)`. [DOC S-lkto4w7b]
- Older separate `run_stream_from_checkpoint`/`run_from_checkpoint` methods being superseded.
  [UNK: not in S-lkto4w7b as re-read 2026-09-27]
- **Human-in-the-loop (HITL)**: a workflow pauses execution via a typed request/response channel —
  Python `ctx.request_info()` plus an `@response_handler`-decorated method; .NET `RequestPort`
  (`RequestPort.Create<TRequest,TResponse>`) emitting `RequestInfoEvent`; Go uses the same
  `RequestInfoEvent`/response pattern. A checkpoint taken while a request is pending re-emits that
  `RequestInfoEvent` on restore, so a workflow can be paused, persisted, and resumed with the human
  response supplied later. [DOC S-j2yxzynm]
- Agent orchestrations (sequential, concurrent, group chat) get **tool approval** through the same
  request/response mechanism: when an agent calls an approval-required tool, the workflow pauses and
  emits a `RequestInfoEvent` whose payload is a `ToolApprovalRequestContent` (C#, Go) or a `Content`
  with `type == "function_approval_request"` (Python). [DOC S-j2yxzynm]
- The `@tool(approval_mode="always_require")` syntax and use with `SequentialBuilder` without extra
  builder configuration. [DOC S-fkamc745]
- A complete workflow can be converted into a single `Agent`-like object with `.as_agent()`: the
  workflow's start executor must accept message input (true by default for `Agent`/agent-based
  executors); external input requests from `RequestInfoExecutor` surface as function calls to the
  wrapping agent's caller. [DOC S-ayrhsrlp]
- Roadmap items named explicitly as not yet built: a Swarm (handoff-based) pattern and a
  `SelectorGroupChat`-equivalent (LLM-driven speaker selection); distributed workflow execution is
  "planned" (current execution model is single-process composition). [DOC S-lkto4w7b]

### Migration from Semantic Kernel and AutoGen
- Both a dedicated **AutoGen migration guide** and a **Semantic Kernel migration guide** are
  published; Agent Framework is described as the direct successor to both, and both projects continue
  to exist as their own repos (Semantic Kernel, AutoGen) referenced from the migration docs. [DOC
  S-kzoop7qs, S-lkto4w7b, S-sjqmzszi]
- From AutoGen: `AssistantAgent(...)` -> `Agent(...)`; `AssistantAgent` is single-turn unless
  `max_tool_iterations` is raised, while Agent Framework's `Agent` is multi-turn by default and keeps
  calling tools until it can return a final answer; AutoGen's `FunctionTool` wrapper is replaced by
  the `@tool` decorator with automatic schema inference plus hosted tools (code interpreter, web
  search). [DOC S-lkto4w7b]
- From Semantic Kernel (.NET): namespaces move from `Microsoft.SemanticKernel[.Agents]` to
  `Microsoft.Extensions.AI` + `Microsoft.Agents.AI`; `Kernel`-based DI registration is replaced by
  registering `AIAgent` directly; `[KernelFunction]`-decorated plugin methods become plain (optionally
  `[Description]`-annotated) methods; `InvokeAsync`/`InvokeStreamingAsync` become `RunAsync`/
  `RunStreamingAsync`, returning `AgentResponse`/`AgentResponseUpdate` instead of
  `AgentResponseItem<ChatMessageContent>`/`StreamingChatMessageContent`. [DOC S-sjqmzszi]
- From Semantic Kernel (Python): `invoke`/`invoke_stream` become `run(...)`/`run(..., stream=True)`;
  options move from `KernelArguments`/provider-specific settings objects to a single `options` dict of
  provider-specific `TypedDict`s (e.g. `OpenAIChatOptions`); `tools` and `instructions` stay as direct
  keyword arguments, not part of `options`. [DOC S-sjqmzszi]
- Neither migration guide's `AgentThread`/`AgentSession` replacement exposes a thread/session deletion
  API; deleting hosted conversation state (where the provider allows it, e.g. OpenAI Assistants) is
  the caller's own responsibility via the provider SDK. [DOC S-sjqmzszi]

### Observability and DevUI
- Agent Framework integrates with **OpenTelemetry**, emitting traces/logs/metrics per the
  **OpenTelemetry GenAI semantic conventions**; setup options include `configure_otel_providers()`
  reading the standard `OTEL_EXPORTER_OTLP_*` environment variables and zero-code auto-instrumentation
  with the `opentelemetry-instrument` CLI. [DOC S-mhvboogr]
- `create_harness_agent`'s telemetry provider name defaults to `microsoft.agent_framework.harness`
  (override with `otel_provider_name=`); instrumentation is enabled by default and sensitive-data
  capture (raw messages/tool args/results) is disabled by default — enable with `ENABLE_SENSITIVE_DATA`;
  disable instrumentation with `ENABLE_INSTRUMENTATION=false` or `disable_instrumentation()`.
  `create_harness_agent` ships in `agent-framework-core`. [DOC S-mhvboogr]
- **DevUI** (`pip install agent-framework-devui --pre`) is a local web UI + OpenAI-compatible Responses
  API for interactively testing agents/workflows: `devui ./agents --port 8080` (directory discovery)
  or `from agent_framework.devui import serve; serve(entities=[agent], tracing_enabled=True)`
  (in-memory registration); `--tracing`/`tracing_enabled=True` shows OpenTelemetry trace timelines
  (span hierarchy, LLM calls, tool calls) in a debug panel — DevUI displays spans the framework emits,
  it does not create its own. Traces can also be exported to an OTLP collector by setting
  `OTLP_ENDPOINT` (e.g. Jaeger, Zipkin, Azure Monitor, Datadog), independent of DevUI. [DOC
  S-cjxn455h, S-nghojxuy]

## Reference
- `agents/own-chatbot-architecture.md`: names Agent Framework as one of the frameworks Azure AI
  Foundry hosted agents can bring-your-own-container from (alongside LangGraph, OpenAI Agents SDK,
  Anthropic Agent SDK, GitHub Copilot SDK); this article gives the framework's own building blocks
  (agents, MCP tools, workflows, migration paths) in depth. See its "Azure AI Foundry Agent Service"
  section for the Foundry-hosting side of that split.
- `claude/agent-sdk.md`: the Anthropic-side equivalent (Claude Agent SDK) for embedding an
  agent loop, tools, permissions, and MCP servers in your own process — compare its `ClaudeAgentOptions`/
  `disallowed_tools` permission pipeline against this article's MCP tool auth (`header_provider`,
  `static_headers`) and tool-approval (`@tool(approval_mode=...)`) mechanisms.
- `agents/foundry-agent-service.md`: the Foundry-hosting side of the split above — Foundry's own tool
  catalogue and Toolbox, `require_approval` enforcement for the MCP tool, RBAC, and quotas/limits for
  hosted agents built with this framework (`FoundryChatClient`/`FoundryToolbox`).
- `agents/langgraph.md`: LangChain's LangGraph is the closest cross-vendor analogue to this
  framework's typed `Workflow` graph — compare its `StateGraph`/`interrupt()`/`Command(resume=...)`
  human-in-the-loop pattern and checkpointers against this article's `ctx.request_info()`/
  `RequestInfoEvent` and workflow checkpointing.
- `_conflicts.md`: none recorded for this topic; the two migration guides (AutoGen, Semantic Kernel)
  and the overview page were consistent on GA status, package names, and MIT licensing wherever they
  overlapped.

## Examples
- Minimal `ChatAgent` calling a remote MCP server over streamable HTTP (placeholder endpoint; API-key
  auth via `header_provider` so the secret never appears in tool arguments):

- SNIPPET: an `Agent` using an `OpenAIChatClient`, connected to a remote MCP server via
  `MCPStreamableHTTPTool` with `header_provider`-based bearer-token auth and a bounded Host-facing
  payload size; context: Microsoft Agent Framework (Python `agent-framework`), `pip install mcp --pre`;
  checked: no [DOC S-7ziha7pr: `Agent`/`MCPStreamableHTTPTool` construction, `header_provider`,
  `max_host_payload_size_bytes`, `tools=` on `agent.run()`]
```python
import asyncio
import os

from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.openai import OpenAIChatClient

MCP_URL = "https://mcp.corp.example.com/mcp"  # placeholder endpoint


async def main() -> None:
    api_key = os.environ["MCP_API_KEY"]

    async with (
        MCPStreamableHTTPTool(
            name="corp-tools",
            url=MCP_URL,
            description="Internal device-management MCP tools",
            header_provider=lambda _kwargs: {"Authorization": f"Bearer {api_key}"},
            max_host_payload_size_bytes=256 * 1024,
        ) as mcp_server,
        Agent(
            client=OpenAIChatClient(),
            name="DeviceOpsAgent",
            instructions=(
                "You help with device compliance questions using the corp MCP tools. "
                "Never invent a device id; ask for one if it is missing."
            ),
        ) as agent,
    ):
        result = await agent.run(
            "Is PL-LT-00123 currently compliant?",
            tools=mcp_server,
        )
        print(result.text)


if __name__ == "__main__":
    asyncio.run(main())
```

- Marking a destructive tool for mandatory human approval inside a `SequentialBuilder` workflow
  (tenant placeholder `00000000-0000-0000-0000-000000000000`):

- SNIPPET: a function tool marked `@tool(approval_mode="always_require")`, used unmodified in a
  `SequentialBuilder` workflow, which pauses and emits a `request_info` event before the tool runs;
  context: Microsoft Agent Framework workflows (Python); checked: no [DOC S-fkamc745: `@tool(approval_mode=
  "always_require")`, `SequentialBuilder(participants=...).build()`, tool approval works with
  `SequentialBuilder` without extra builder configuration]
```python
from agent_framework import tool
from agent_framework.workflows import SequentialBuilder


@tool(approval_mode="always_require")
def revoke_device_compliance(device_id: str, tenant_id: str) -> str:
    """Revoke compliance for a device (requires human approval)."""
    return f"Compliance revoked for {device_id} in tenant {tenant_id}"


# workflow.run(...) pauses and emits a request_info event before this tool executes;
# the caller must supply the human approval response before the workflow proceeds.
workflow = SequentialBuilder(participants=[compliance_agent]).build()
```
