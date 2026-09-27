---
topic: agents/a2a-protocol
priority: P2
applies_to: "A2A protocol spec v1.0.0 / v1.0.1; A2A Python SDK (a2a-sdk)"
retrieved_utc: 2026-09-27
sources: [S2120, S2121, S2122, S2123, S2124, S2125, S2126, S2127, S2128, S2129, S-xasyjfgi, S-2jevtssc, S-t24szuu4, S-byrq57yo, S-fpw4ly2l]
status: complete
files: [agents/a2a/a2a-proto-digest.md, agents/a2a/a2a.proto]
---

# Agent2Agent (A2A) protocol

## Summary

Agent2Agent (A2A) is an open protocol, launched by Google in April 2025 and donated to the Linux Foundation in June 2025 for vendor-neutral governance, for opaque agent-to-agent task delegation (an agent invokes another agent without seeing its internals) [DOC S2123,S2128]. Since 2026-08-27 it is a Growth Stage project of the Linux Foundation-directed Agentic AI Foundation (AAIF), beside MCP [DOC S-2jevtssc]. The latest release is v1.0.1 (bug fixes on v1.0.0 of 2026-03-12); the proto file is the normative definition, pinned in `agents/a2a/` (see the digest) [DOC S2120, S-xasyjfgi]. Microsoft (Copilot Studio) supports it, and Google ADK supports it as an Experimental feature; no Anthropic product page states native A2A support, though Anthropic has co-presented MCP+A2A patterns with Google Cloud [DOC S2126, S-fpw4ly2l, S2129]. Topic 8 (`agents/agent-dispatch-and-shared-services.md`) covers whether to dispatch to another agent; this file covers only the A2A mechanism.

## Facts

- **Version and status.** Releases on the a2aproject/A2A repository: v0.3.0 on 2025-07-30, v1.0.0 on 2026-03-12 (a release with breaking spec changes), and v1.0.1 published 2026-05-28 (changelog dated 2026-05-26), whose notes list only bug fixes, e.g. preferring `application/a2a+json` in the HTTP binding [DOC S-xasyjfgi]. The spec page still names 1.0.0 as the latest released specification version and defines signed Agent Cards (section 8.4) [DOC S2120]. An earlier note that v1.0.1 added an extension mechanism came from a search summary and is not what the release notes say; extension rules live in the spec's governance section [DER S-xasyjfgi, S2120: release notes list bug fixes only].
- **Agentic AI Foundation.** On 2026-08-27 A2A was accepted as a Growth Stage project of the Agentic AI Foundation (AAIF), which operates under the Linux Foundation, alongside MCP, goose and AGENTS.md; this is a later governance step after the 2025 Linux Foundation "Agent2Agent Protocol Project", not a rename of it [DOC S-2jevtssc].
- **Governance.** A2A was launched by Google in April 2025 and transferred to the Linux Foundation on 2025-06-23, announced at Open Source Summit North America, as the "Agent2Agent Protocol Project" for vendor-neutral stewardship [DOC S2123]. Founding/supporting organizations named in the announcement: Google, AWS, Cisco (Outshift), Salesforce, SAP, Microsoft, ServiceNow, with "more than 100" companies supporting overall [DOC S2123]. A later Linux Foundation post reports the project surpassing 150 supporting organizations and production use inside its first year [DOC S2124].
- **Normative definition.** The authoritative definition is `specification/a2a.proto` (Protocol Buffers); generated JSON artifacts are non-normative build outputs regenerated from the proto [DOC S2120]. Pinned copy: `agents/a2a/a2a.proto`, commit `43e0c874d3baba68ed84b98678d7f2268438e69f`, sha256 `945df6e34001b2bfd0fd62d9484b63094dfad9d78705e41e2873441c419ae2d1` [DOC S2121,S2122].
- **Agent Card and discovery.** The Agent Card is a JSON metadata document a server publishes (well-known URI `/.well-known/agent-card.json`, registered in the spec's IANA section) describing identity, provider, declared capabilities (streaming, push notifications, extended cards), skills, service endpoints, security schemes and extensions [DOC S2120]. Microsoft Copilot Studio's A2A connector pulls the name/description automatically from a valid agent card at the standard `.well-known` URL; its troubleshooting note gives that location as the endpoint plus `/.well-known/agent.json`, not `agent-card.json` [DOC S2126].
- **Task states.** The spec defines a task lifecycle enum: `TASK_STATE_SUBMITTED`, `TASK_STATE_WORKING`, `TASK_STATE_INPUT_REQUIRED` (interrupted, awaiting input), `TASK_STATE_AUTH_REQUIRED` (interrupted, awaiting auth), and terminal states `TASK_STATE_COMPLETED`, `TASK_STATE_FAILED`, `TASK_STATE_CANCELED`, `TASK_STATE_REJECTED` [DOC S2120].
- **Transports.** Three functionally equivalent bindings: JSON-RPC 2.0, gRPC, and HTTP+JSON/REST [DOC S2120].
- **Streaming and push.** Server-Sent Events carry `SendStreamingMessage`/`SubscribeToTask` for persistent connections; push notifications use HTTP POST webhooks to client-registered endpoints for async updates; clients without a persistent connection can poll via `GetTask` [DOC S2120].
- **Authentication.** Declared security schemes cover API key, HTTP Basic/Bearer, OAuth 2.0 (authorization code, client credentials, device code), OpenID Connect, and mutual TLS [DOC S2120]. Copilot Studio's A2A connector setup form offers exactly three: None, API key (header or query parameter), and OAuth 2.0 (client id/secret, authorization/token/refresh URLs) [DOC S2126].
- **Relation to MCP.** The spec's Appendix B calls A2A and MCP complementary: MCP connects an agent to tools and data, A2A lets peer agents collaborate and delegate tasks, and an A2A server agent may itself use MCP internally [DOC S2120]. The AAIF announcement puts it as MCP being the vertical integration layer and A2A the horizontal agent-to-agent protocol [DOC S-2jevtssc]. Microsoft's own docs draw the same line operationally: use A2A to delegate to another agent that has its own reasoning, use MCP servers for tools/resources, and use the Microsoft 365 Agents SDK's Activity Protocol for agents built with that SDK [DOC S2126].
- **SDKs.** The official first-party SDK is Python (`a2a-sdk` on PyPI, Apache-2.0, requires Python >= 3.10, implements both client and server roles) [DOC S2125]. The a2aproject GitHub organisation also holds SDK repositories `a2a-js`, `a2a-java`, `a2a-go`, `a2a-dotnet` and `a2a-rs`, plus tooling repositories such as `a2a-tck` (compatibility kit), `a2a-inspector` and `a2a-cli` [DOC S-t24szuu4].
- **JSON Schema.** `a2a.json` is a non-normative JSON Schema bundle generated from the proto at build time and deliberately not committed to the repository; the site publishes it at `https://a2a-protocol.org/latest/spec/a2a.json` [DOC S-byrq57yo].
- **Vendor support.** Microsoft Copilot Studio has an "A2A agent" connection type (standard harness; the page carries no preview label) that lets a Copilot Studio agent delegate tasks to an external A2A agent via its endpoint URL and agent card, using the custom-connector infrastructure (so on-prem/VNet A2A agents are reachable) [DOC S2126]; ms.date on that page is 2026-08-26. Microsoft's Cloud blog from 2025-05-07 announced multi-agent app support for A2A pre-dating the Copilot Studio feature [DOC S2127]. Google's ADK (Agent Development Kit) documents A2A for both exposing and consuming agents in Python, Go and Java, badged Experimental [DOC S-fpw4ly2l]. The AAIF announcement also names Google Cloud, AWS Bedrock AgentCore Runtime and Azure AI Foundry as having native A2A support [DOC S-2jevtssc].
- **Anthropic.** No official Anthropic product page confirming native A2A protocol support was found; Anthropic has published a webinar with Google Cloud on "Deploying multi-agent systems using MCP and A2A with Claude on Vertex AI," which demonstrates Claude models participating in an A2A-orchestrated system via Vertex AI tooling, not a first-party Claude/Claude Code/Agent SDK A2A implementation [DOC S2129]. The Claude Code docs, the Claude platform docs index (`llms.txt`) and the AAIF adopter list do not mention A2A for any Anthropic product (searched 2026-09-27), so no Anthropic product is documented as speaking A2A natively [DER S2129, S-2jevtssc: absence across the official docs searched; see _gaps.md].

## Reference

| item | value | source |
|---|---|---|
| spec version | 1.0.0 (2026-03-12); release 1.0.1 (bug fixes, 2026-05-28) | S2120, S-xasyjfgi |
| licence | Apache-2.0 | S2121 |
| governance | Linux Foundation (Agent2Agent Protocol Project); AAIF Growth Stage project since 2026-08-27 | S2123, S-2jevtssc |
| normative artifact | `specification/a2a.proto` | S2120 |
| pinned commit | 43e0c874d3baba68ed84b98678d7f2268438e69f | S2121,S2122 |
| task states | SUBMITTED, WORKING, INPUT_REQUIRED, AUTH_REQUIRED, COMPLETED, FAILED, CANCELED, REJECTED | S2120 |
| transports | JSON-RPC 2.0, gRPC, HTTP+JSON/REST | S2120 |
| auth schemes | API key, HTTP Basic/Bearer, OAuth 2.0, OIDC, mTLS | S2120 |
| Python SDK | `a2a-sdk`, Apache-2.0, Python >= 3.10 | S2125 |
| Copilot Studio support | A2A agent connection (no preview label), ms.date 2026-08-26 | S2126 |
| Anthropic native support | not documented (searched 2026-09-27) | S2129 |

## Examples

A hypothetical connected-agent scenario, using example names only: a stdio MCP server stays the tool boundary for device data on `PL-LT-00123` / `corp.example.com`; A2A, if ever adopted, would sit above that as an agent-to-agent layer. For a system whose policy is "no always-on service," A2A stays out of scope until that policy is deliberately revisited [DER — general implication for stdio-only MCP deployments].
