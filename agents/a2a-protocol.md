---
topic: agents/a2a-protocol
priority: P2
applies_to: "A2A protocol spec v1.0.0 / v1.0.1; A2A Python SDK (a2a-sdk)"
retrieved_utc: 2026-09-25
sources: [S2120, S2121, S2122, S2123, S2124, S2125, S2126, S2127, S2128, S2129]
status: partial
files: [agents/a2a/a2a-proto-digest.md, agents/a2a/a2a.proto]
---

# Agent2Agent (A2A) protocol

## Summary

Agent2Agent (A2A) is an open protocol, launched by Google in April 2025 and donated to the Linux Foundation in June 2025 for vendor-neutral governance, for opaque agent-to-agent task delegation (an agent invokes another agent without seeing its internals) [DOC S2123,S2128]. The current released spec is v1.0.0, with a v1.0.1 extension mechanism; the proto file is the normative definition, pinned in `agents/a2a/` (see the digest) [DOC S2120]. Microsoft (Copilot Studio) and Google (ADK) support it natively as of 2026; no official Anthropic product is confirmed to speak A2A, though Anthropic has co-presented MCP+A2A patterns with Google Cloud [DOC S2126; DOC S2129; UNK]. Topic 8 (`agents/agent-dispatch-and-shared-services.md`) covers whether to dispatch to another agent; this file covers only the A2A mechanism.

## Facts

- **Version and status.** The protocol advanced from v0.3.0 (2025-07) to v1.0.0 (dated by the spec site to a period the fetched page associates with a 2026-08-27 "A2A joins the Agentic AI Foundation" post), which the source characterizes as the production-ready milestone, adding signed Agent Cards for cryptographic verification; v1.0.1 (2026-05 per WebSearch) added an extension mechanism for new data, requirements, RPC methods and state machines [DOC S2120; UNK: from a search summary only; the exact 1.0.0 date and the "Agentic AI Foundation" rename need direct confirmation, see gaps].
- **Governance.** A2A was launched by Google in April 2025 and transferred to the Linux Foundation on 2025-06-23, announced at Open Source Summit North America, as the "Agent2Agent Protocol Project" for vendor-neutral stewardship [DOC S2123]. Founding/supporting organizations named in the announcement: Google, AWS, Cisco (Outshift), Salesforce, SAP, Microsoft, ServiceNow, with "more than 100" companies supporting overall [DOC S2123]. A later Linux Foundation post reports the project surpassing 150 supporting organizations and production use inside its first year [DOC S2124].
- **Normative definition.** The authoritative definition is `specification/a2a.proto` (Protocol Buffers); generated JSON artifacts are non-normative build outputs regenerated from the proto [DOC S2120]. Pinned copy: `agents/a2a/a2a.proto`, commit `43e0c874d3baba68ed84b98678d7f2268438e69f`, sha256 `945df6e34001b2bfd0fd62d9484b63094dfad9d78705e41e2873441c419ae2d1` [DOC S2121,S2122].
- **Agent Card and discovery.** The Agent Card is a JSON metadata document a server publishes (conventionally at `/.well-known/agent.json`) describing identity, provider, declared capabilities (streaming, push notifications, extended cards), skills, service endpoints, security schemes and extensions [DOC S2120; DOC S2126]. Microsoft Copilot Studio's A2A connector fetches the card automatically from the agent's endpoint to populate name/description [DOC S2126].
- **Task states.** The spec defines a task lifecycle enum: `TASK_STATE_SUBMITTED`, `TASK_STATE_WORKING`, `TASK_STATE_INPUT_REQUIRED` (interrupted, awaiting input), `TASK_STATE_AUTH_REQUIRED` (interrupted, awaiting auth), and terminal states `TASK_STATE_COMPLETED`, `TASK_STATE_FAILED`, `TASK_STATE_CANCELED`, `TASK_STATE_REJECTED` [DOC S2120].
- **Transports.** Three functionally equivalent bindings: JSON-RPC 2.0, gRPC, and HTTP+JSON/REST [DOC S2120].
- **Streaming and push.** Server-Sent Events carry `SendStreamingMessage`/`SubscribeToTask` for persistent connections; push notifications use HTTP POST webhooks to client-registered endpoints for async updates; clients without a persistent connection can poll via `GetTask` [DOC S2120].
- **Authentication.** Declared security schemes cover API key, HTTP Basic/Bearer, OAuth 2.0 (authorization code, client credentials, device code), OpenID Connect, and mutual TLS [DOC S2120]. Copilot Studio's A2A connector setup form offers exactly three: None, API key (header or query parameter), and OAuth 2.0 (client id/secret, authorization/token/refresh URLs) [DOC S2126].
- **Relation to MCP.** The spec carries an "Appendix B. Relationship to MCP" (content not captured in full) [DOC S2120]. Independent characterization: A2A and MCP are peer, not competing, protocols — A2A governs opaque agent-to-agent collaboration where each agent keeps its own reasoning, while MCP standardizes how a single agent accesses external tools and data [UNK: search summary only, no single vendor page cited]. Microsoft's own docs draw the same line operationally: use A2A to delegate to another agent that has its own reasoning, use MCP servers for tools/resources, and use the Microsoft 365 Agents SDK's Activity Protocol for agents built with that SDK [DOC S2126].
- **SDKs.** The official first-party SDK is Python (`a2a-sdk` on PyPI, Apache-2.0, requires Python >= 3.10, implements both client and server roles) [DOC S2125]. The GitHub org also lists (per one fetched summary, not independently verified per-language) Go, JavaScript, Java, .NET and Rust SDKs [DOC S2121].
- **Vendor support.** Microsoft Copilot Studio has a GA "A2A agent" connection type (standard harness) that lets a Copilot Studio agent delegate tasks to an external A2A agent via its endpoint URL and agent card, using the custom-connector infrastructure (so on-prem/VNet A2A agents are reachable) [DOC S2126]; ms.date on that page is 2026-08-26. Microsoft's Cloud blog from 2025-05-07 announced multi-agent app support for A2A pre-dating the Copilot Studio GA feature [DOC S2127]. Google's ADK (Agent Development Kit) supports both MCP (as a tool source) and A2A (as an exposure/consumption protocol) natively, per WebSearch summary of Google's Cloud Next 2026 and ADK v1.0 announcements [UNK: search summary only, page not fetched].
- **Anthropic.** No official Anthropic product page confirming native A2A protocol support was found; Anthropic has published a webinar with Google Cloud on "Deploying multi-agent systems using MCP and A2A with Claude on Vertex AI," which demonstrates Claude models participating in an A2A-orchestrated system via Vertex AI tooling, not a first-party Claude/Claude Code/Agent SDK A2A implementation [DOC S2129]. Community wrapper projects exist that expose the Claude Code CLI or Claude Agent SDK as an A2A server, which is evidence there is no built-in support to wrap [UNK: search summary only, page not fetched]. Tag: **UNK** for "does any Anthropic product speak A2A natively."

## Reference

| item | value | source |
|---|---|---|
| spec version | 1.0.0 (extension mechanism in 1.0.1) | S2120 |
| licence | Apache-2.0 | S2121 |
| governance | Linux Foundation (Agent2Agent Protocol Project) | S2123 |
| normative artifact | `specification/a2a.proto` | S2120 |
| pinned commit | 43e0c874d3baba68ed84b98678d7f2268438e69f | S2121,S2122 |
| task states | SUBMITTED, WORKING, INPUT_REQUIRED, AUTH_REQUIRED, COMPLETED, FAILED, CANCELED, REJECTED | S2120 |
| transports | JSON-RPC 2.0, gRPC, HTTP+JSON/REST | S2120 |
| auth schemes | API key, HTTP Basic/Bearer, OAuth 2.0, OIDC, mTLS | S2120 |
| Python SDK | `a2a-sdk`, Apache-2.0, Python >= 3.10 | S2125 |
| Copilot Studio support | GA A2A agent connection, ms.date 2026-08-26 | S2126 |
| Anthropic native support | not found (UNK) | — |

## Examples

A hypothetical connected-agent scenario, using example names only: a stdio MCP server stays the tool boundary for device data on `PL-LT-00123` / `corp.example.com`; A2A, if ever adopted, would sit above that as an agent-to-agent layer. For a system whose policy is "no always-on service," A2A stays out of scope until that policy is deliberately revisited [DER — general implication for stdio-only MCP deployments].
