---
topic: agents/agent-memory-services
priority: P3
applies_to: "Claude API memory tool (memory_20250818); Claude Managed Agents memory stores (Beta, header agent-memory-2026-07-22); Memory in Microsoft Foundry Agent Service and the Memory Store API (preview, Learn 2026-10); Cloudflare Agents SDK state and Durable Objects (docs 2026-06 to 2026-10)"
retrieved_utc: 2026-10-15
sources: [S-n5jx3ykg, S749, S-ovnqfusm, S-gybzd4tj, S-qwkcddyd, S-akyurl2s, S-4wv4j3r2, S-3bnq55fu, S-x5vpwiqv, S-2oqpgch6]
status: complete
---

# Managed memory services for agents (Claude memory tool, Foundry agent memory, Cloudflare Agents state)

## Summary
Four services keep what an agent learns beyond one context window, and they differ first in who holds the storage. The Claude API memory tool is client-side: Claude asks for file operations under `/memories` and the caller's own handler carries them out against storage the caller controls. Claude Managed Agents memory stores (Beta) are held by Anthropic: a workspace-scoped store is mounted into the session's sandbox as a directory, and every write makes an immutable version. Memory in Microsoft Foundry Agent Service (preview) is a managed long-term memory: the service extracts user profile, chat summary and procedural memories from conversations with a chat model and an embedding model, partitions them by `scope`, and serves them through a memory search tool or the Memory Store API. Cloudflare Agents keep state in the SQLite database of the Durable Object each agent instance is: one named instance handles every request and client for that agent, its storage is strongly consistent, and `setState` persists a change and broadcasts it to every connected client.

## Facts

### Claude API memory tool (client-side storage)
- The memory tool lets Claude create, read, update and delete files in a directory of memory files that persist between conversations, so knowledge builds up without staying in the context window. [DOC S-n5jx3ykg]
- The tool runs client-side: Claude only requests the file operations, and the caller's application executes them against storage it controls and returns each result in a `tool_result` block. [DOC S-n5jx3ykg]
- `/memories` is a path prefix that the caller's handler maps onto real storage, such as a per-user directory or keys in a database; the page says memory lives entirely in the caller's application. [DOC S-n5jx3ykg]
- A later conversation continues from the same memory when it sends the same `tools` entry and the handler serves the same store. [DOC S-n5jx3ykg]
- The tool is declared by the tools entry `{"type": "memory_20250818", "name": "memory"}`, with no input schema, and works on all Claude 4 and later models. [DOC S-n5jx3ykg]
- The memory tool needs no beta header, although the SDK helpers and tool runner for it sit in each SDK's beta namespace. [DOC S-n5jx3ykg]
- The SDK helpers are `BetaAbstractMemoryTool` (Python and C#), `betaMemoryTool` (TypeScript) and `BetaMemoryToolHandler` (Java); Python and TypeScript also ship a local-filesystem implementation, `BetaLocalFilesystemMemoryTool`. [DOC S-n5jx3ykg]
- The handler implements six commands: `view` (a directory listing two levels deep, or a file with line numbers and an optional `view_range`), `create`, `str_replace`, `insert`, `delete` and `rename`. [DOC S-n5jx3ykg]
- `create` on an existing file returns an error in the reference behaviour, but Claude's tool description says create "creates or overwrites", so overwriting is also a valid handler choice. [DOC S-n5jx3ykg]
- `rename` onto an existing destination returns an error instead of overwriting, and the handler should reject a `delete` or `rename` of the `/memories` root itself. [DOC S-n5jx3ykg]
- With the tool present, the API adds a memory protocol to the system prompt telling Claude to view its memory directory before anything else and to assume its context window can be reset at any moment. [DOC S-n5jx3ykg]
- The page puts the safeguards on the caller: strip sensitive data before writing, cap file sizes, expire files not accessed for a long time, and reject paths outside `/memories` (canonicalize, refuse `../` and URL-encoded traversal). [DOC S-n5jx3ykg]
- The memory tool is ZDR-eligible and HIPAA-eligible; the eligibility table describes it as client-side memory storage where the customer controls data retention. [DOC S749]

### Claude Managed Agents memory stores (Beta, Anthropic-held)
- Managed Agents memory is Beta: memory store calls take the beta header `agent-memory-2026-07-22`, not combined with `managed-agents-2026-04-01` (sending both returns 400); session endpoints, including attaching a store, keep `managed-agents-2026-04-01`. [DOC S-ovnqfusm]
- A memory store is a workspace-scoped collection of text documents; attached to a session, it is mounted as a directory in the session's sandbox, and the agent reads and writes it with its ordinary file tools. [DOC S-ovnqfusm]
- Each store mounts under `/mnt/memory/` as a slug of its display name; a note describing each mount is added to the system prompt automatically. [DOC S-ovnqfusm]
- Stores are attached only when a session is created, at most 8 per session, with access `read_write` (the default) or `read_only`, enforced at the filesystem level. [DOC S-ovnqfusm]
- Every change to a memory creates an immutable version attributed to the session; versions belong to the store, survive the memory's deletion, and are kept 30 days after they are written, except recent versions of a live memory, which are always kept. [DOC S-ovnqfusm]
- A memory update can carry a `content_sha256` precondition: it applies only when the stored content hash still matches the one read, so a concurrent write is not overwritten. [DOC S-ovnqfusm]
- A store holds at most 10,000 memories; once full, new memories fail both through the API and through the agent's file writes, while existing memories stay readable and editable. [DOC S-ovnqfusm]
- Archiving a store makes it read-only and keeps it from new sessions, with no unarchive; deleting a store removes its memories and versions. [DOC S-ovnqfusm]
- On a self-hosted sandbox a worker syncs the store to local disk and back (at most once per 15-second sync interval by default) and Anthropic's copy of the store stays the source of truth. [DOC S-gybzd4tj]
- Because each self-hosted worker syncs on an interval, a write in one session reaches another running session only after both have synced; cloud sandboxes see each other's changes almost immediately. [DOC S-gybzd4tj]
- Managed Agents (`/v1/agents`, `/v1/sessions`, `/v1/environments`) are not eligible for ZDR or HIPAA: sessions are stateful and their transcripts persist until deleted. [DOC S749]

### Memory in Microsoft Foundry Agent Service (preview)
- Memory in Foundry Agent Service and the Memory Store API are in preview, under the Supplemental Terms of Use for Microsoft Azure Previews; the page says pricing and billing can change during the preview. [DOC S-qwkcddyd]
- It is a managed long-term memory: memories are stored as items in a managed memory store, extracted from conversations, consolidated with LLMs (duplicates merged, conflicting facts resolved) and retrieved by search. [DOC S-qwkcddyd]
- Three memory types are extracted, all enabled by default: user profile memory, chat summary memory and procedural memory. [DOC S-qwkcddyd]
- An agent uses memory either through the memory search tool attached to a prompt agent or through the low-level memory store APIs, which also give item-level create, read, update, list and delete. [DOC S-qwkcddyd]
- A memory store names the chat model and embedding model deployments that process its content; memory needs compatible Azure OpenAI chat and embedding deployments, and billing is for the use of those models. [DOC S-qwkcddyd]
- `scope` partitions a store: each scope keeps an isolated collection of memory items, and memory APIs called directly need `scope` set explicitly in every request. [DOC S-akyurl2s]
- With the memory search tool (type `memory_search_preview` in the agent definition), `scope` set to `{{$userId}}` resolves per call to the `x-memory-user-id` request header, or, without it, to the caller's Microsoft Entra tenant id and object id. [DOC S-akyurl2s]
- After each agent response the service calls `update_memories`, but writes to long-term memory are debounced by `update_delay`, a period of inactivity after which the scheduled update completes; calling the update API with `update_delay` 0 processes it at once. [DOC S-akyurl2s]
- An explicit user request to remember or forget is applied immediately by the memory search tool, but does not override the store's TTL. [DOC S-akyurl2s]
- `default_ttl_seconds` sets a store's retention (0 means no expiration) and applies to memories from every path; in the latest preview such defaults are set only when the store is created. [DOC S-akyurl2s]
- Limits: 100 scopes per store, 10,000 memories per scope, 1,000 search and 1,000 update requests per minute; virtual network integration is not supported for memory stores. [DOC S-qwkcddyd]
- The page names prompt injection and memory corruption as the risks of LLM-extracted memory and suggests Azure AI Content Safety prompt injection detection and adversarial testing. [DOC S-qwkcddyd]
- For role-based access the how-to assigns the Foundry User role (formerly Azure AI User) to the project's managed identity, and falls back to key-based authentication where roles are not feasible. [DOC S-akyurl2s]

### Cloudflare Agents state on Durable Objects
- The Agents SDK's `Agent` class is a Durable Object (it extends `Server` from `partyserver`, which extends `DurableObject`), so each agent instance is a globally addressable, single-threaded compute instance with its own storage. [DOC S-3bnq55fu]
- Each Durable Object has a globally unique name, so requests from anywhere reach that one object, and clients that must work together can coordinate through it. [DOC S-x5vpwiqv]
- A Durable Object's storage is transactional and strongly consistent, persists across requests and is private to that object; the SQLite backend gives both a key-value and an SQL API. [DOC S-x5vpwiqv]
- Durable Objects are single-threaded and cooperatively multi-tasked; in-memory state is lost when an idle object hibernates, so data needed later must be written to storage. [DOC S-x5vpwiqv]
- Input gates block new events (incoming requests, fetch responses) while the object's synchronous code runs, and its storage operations keep other requests from interleaving; output gates hold outgoing responses until pending storage writes complete, so a client never sees an unpersisted write confirmed. [DOC S-2oqpgch6]
- Awaiting non-storage I/O such as `fetch()` or an R2 write opens the input gate, so other requests can interleave; `transaction()` is the documented choice for an atomic read-modify-write, and `blockConcurrencyWhile()` is reserved for initialization and migrations. [DOC S-2oqpgch6]
- Agent state lives in an SQL database embedded in each agent instance; the page lists it as persistent across restarts and hibernation, read-your-own-writes consistent and safe for concurrent updates. [DOC S-4wv4j3r2]
- `setState()` saves the new state to SQLite, broadcasts it to every connected WebSocket client and then calls `onStateChanged()` (best-effort); clients can push state too, through `useAgent` or `AgentClient`. [DOC S-4wv4j3r2]
- `validateStateChange()` runs synchronously before persistence and broadcast, and throwing from it rejects the update, whether a client or the server proposed it. [DOC S-4wv4j3r2]
- State is stored as JSON and broadcast whole on every change, so the page advises keeping it small and putting history and large collections in the agent's SQL database (`this.sql`). [DOC S-4wv4j3r2]
- Workflow steps change an agent's state with `step.updateAgentState`, `step.mergeAgentState` and `step.resetAgentState`, durable operations that persist across workflow retries. [DOC S-4wv4j3r2]

### Who holds the storage, and how it fits this kb
- Who holds the memory: the Claude memory tool keeps it wherever the caller's handler writes (an on-premises file share or database is possible); Managed Agents memory stores and Foundry memory stores are held by the vendor; a Cloudflare agent's state sits in its Durable Object on Cloudflare's network. [DER S-n5jx3ykg, S-ovnqfusm, S-qwkcddyd, S-x5vpwiqv: client-side handler; Anthropic copy is source of truth; managed memory store; storage attached to the object]
- For an estate that must keep agent memory inside its own boundary, the memory tool is the only one of the four whose storage the operator chooses; it is also the only one marked ZDR-eligible, while Managed Agents is not. [DER S-n5jx3ykg, S749: client-side storage; ZDR table rows]
- None of the four filters secrets for the operator: the memory tool page leaves validation to the handler, and Foundry offers `user_profile_details` to steer extraction; secrets therefore stay out of memory only by a handler check or an extraction instruction the operator writes. [DER S-n5jx3ykg, S-akyurl2s: caller-side validation; user_profile_details exclusion]
- Several agents writing one memory: Managed Agents gives optimistic concurrency (`content_sha256`), Cloudflare serializes through the one Durable Object per name, while the memory tool and Foundry pages name no conditional write for memory content, so the memory tool's handler has to bring its own (as in `agents/shared-state-concurrency.md`). [DER S-ovnqfusm, S-2oqpgch6, S-n5jx3ykg, S-akyurl2s: precondition; single-threaded object with gates; no precondition on either page]
- Foundry memory cannot sit behind a virtual network and is preview, so it is not the recommended path for an estate that requires private networking for production data. [DER S-qwkcddyd: VNet integration not supported; preview terms]

## Reference

| Service | Status | Storage held by | How the agent reads it | Isolation | Concurrent writers |
| --- | --- | --- | --- | --- | --- |
| Claude memory tool | no beta header (SDK helpers in beta namespace) | the caller (handler) | `memory` tool commands under `/memories` | whatever the handler maps | the handler's storage decides |
| Claude Managed Agents memory stores | Beta | Anthropic | file tools on `/mnt/memory/<store>/` | per store, `read_only` or `read_write` per session | `content_sha256` precondition |
| Foundry Agent Service memory | preview | Microsoft (managed memory store) | `memory_search_preview` tool or Memory Store API | `scope` per user or group | not stated |
| Cloudflare Agents state | not stated on the pages read | the agent's Durable Object | `this.state`, `this.sql` | one object per name, storage private to it | single-threaded object, input and output gates |

- Related: `agents/shared-state-concurrency.md` (conditional writes, leases, locks), `agents/langgraph.md` (checkpointers and long-term stores), `agents/foundry-agent-service.md` (the Foundry Agent Service itself, RBAC roles), `claude/messages-api.md` (Messages API, Files API), `claude/data-retention.md` (ZDR scope), `claude/skills-and-subagents.md` (Claude Code subagent memory directories).
- Claude memory tool: https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool; Foundry memory: https://learn.microsoft.com/azure/foundry/agents/concepts/what-is-memory; Cloudflare state: https://developers.cloudflare.com/agents/runtime/lifecycle/state/

## Examples
- SNIPPET: a Messages API request body that enables the memory tool; context: Claude 4 or later model, the caller's handler answers each `tool_use` for `memory`; checked: syntax [DER S-n5jx3ykg: tools entry and example request from the memory tool page]

```json
{
  "model": "claude-opus-5-5",
  "max_tokens": 2048,
  "tools": [{"type": "memory_20250818", "name": "memory"}],
  "messages": [{"role": "user", "content": "Continue the patch report for PL-LT-00123."}]
}
```

- SNIPPET: path check a memory tool handler runs before any file operation; context: Python 3.9 or later, `root` is the directory the handler maps `/memories` onto; checked: syntax [DER S-n5jx3ykg: validate the `/memories` prefix, resolve to canonical form, stay inside the memory directory]

```python
from pathlib import Path


def resolve_memory_path(root: Path, requested: str) -> Path:
    if requested != "/memories" and not requested.startswith("/memories/"):
        raise ValueError(f"path outside /memories: {requested}")
    relative = requested[len("/memories"):].lstrip("/")
    target = (root / relative).resolve()
    target.relative_to(root.resolve())  # raises ValueError when it escapes the root
    return target
```
