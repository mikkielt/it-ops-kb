---
topic: claude/messages-api
priority: P1
applies_to: "Claude API (platform.claude.com/docs), Messages API, Message Batches API, Files API, Token Counting API, MCP connector (mcp-client-2025-11-20 beta), retrieved 2026-09-26"
retrieved_utc: 2026-09-26
sources: [S-osulh6sh, S-eu3n3hyf, S-5uxkh3j5, S-3pftmimx, S-wbsmegvl, S-b4bqwu2v, S-jrsntqfg, S-qpqoaaqj, S-qso6o6wu, S1847]
status: complete
files: [claude/models.csv, claude/api-limits.csv]
---

# Claude Messages API

## Summary
The Messages API (`POST https://api.anthropic.com/v1/messages`, header `anthropic-version: 2023-06-01`) takes
`model`, `max_tokens`, `messages`, and optionally `system` and `tools`/`tool_choice`; tool use runs as a loop of
`tool_use` content blocks from Claude answered by `tool_result` blocks the caller sends back, ending in one of the
documented `stop_reason` values [DOC S-osulh6sh, S-qso6o6wu]. Three adjacent endpoints extend this: token counting
(`/v1/messages/count_tokens`, no `max_tokens` needed) [DOC S-jrsntqfg], the Message Batches API for up to 100,000
requests or 256 MB per batch at 50% of standard price [DOC S-3pftmimx], and the Files API for uploading data once
and referencing it by `file_id` [DOC S-wbsmegvl, S-b4bqwu2v]. Current model IDs, context windows and max output are
in `claude/models.csv`; rate limits, batch/file/token limits are in `claude/api-limits.csv`. This topic does not
repeat prompt caching (`agents/agent-caching.md`) or the HTTP/tool-pairing error catalogue
(`agents/agent-error-catalogue.md`) it extends.

## Facts

### Request shape
- Endpoint: `POST https://api.anthropic.com/v1/messages`; required header `anthropic-version: 2023-06-01`;
  authentication header `x-api-key: <key>` [DOC S-osulh6sh].
- Required body fields: `model` (string, a pinned model ID), `max_tokens` (integer, minimum 0), `messages` (array of
  `{role, content}`, alternating `user`/`assistant` turns; consecutive same-role turns are combined) [DOC
  S-osulh6sh, S-jrsntqfg].
- Optional `system`: string or array of text blocks, the system prompt [DOC S-osulh6sh].
- Optional `tools`: array of tool definitions (`name`, `description`, `input_schema`); optional `tool_choice` with
  `type` one of `"auto"`, `"any"`, `"tool"` (requires `name`), `"none"`; `auto`/`any`/`tool` each accept an optional
  `disable_parallel_tool_use: boolean` [DOC S-osulh6sh].
- If the final message in `messages` has role `assistant`, the response continues that content directly (a
  prefill), letting a caller constrain part of the output [DOC S-jrsntqfg].
- Content block types seen in requests/responses: `text`, `tool_use`, `tool_result`, `thinking`, `document`,
  `image`, `container_upload` (the last three reference Files API `file_id` values) [DOC S-osulh6sh, S-b4bqwu2v].

### Tool-use loop
- Claude emits one or more `tool_use` blocks (each with `id`, `name`, `input`) and a `stop_reason` of `tool_use`
  when it wants a tool call answered; the caller executes the tool and sends back a `user` message containing one
  `tool_result` block per `tool_use.id`, each with `tool_use_id` and `content` (text or content blocks), and an
  optional `is_error: true` when the tool call failed [DOC S-osulh6sh].
- `stop_reason` values: `end_turn`, `stop_sequence`, `max_tokens`, `tool_use` (the original four) [DOC S-osulh6sh],
  plus `pause_turn` (server-tool sampling loop hit its iteration cap, 10 per request by default, e.g. during web
  search — resend the response as-is to let Claude continue; a response only awaiting a client-side `tool_use` is
  never `pause_turn`), `refusal` (a safety classifier declined; returned as a normal HTTP 200 with `stop_details`
  naming the policy category; documented handling is to retry on a fallback model rather than resend to the same
  model), and `model_context_window_exceeded` (generation filled the context window and the response is truncated;
  distinct from the request-time `413 request_too_large`) — full detail and error taxonomy already in
  `agents/agent-error-catalogue.md`, not repeated here [DOC S-qso6o6wu, S1847].
- `tool_choice.type: "tool"` forces exactly the named tool; a `strict: true` tool (structured-output-style
  constrained sampling) is documented separately and already covered, with its PHI caveat, in
  `agents/agent-error-catalogue.md` [DER: cross-reference, no new source].

### Response usage fields
- `usage.input_tokens`: tokens after the last prompt-cache breakpoint (not total input) [DOC S-osulh6sh].
- `usage.output_tokens`: tokens generated [DOC S-osulh6sh].
- `usage.cache_creation_input_tokens` / `usage.cache_read_input_tokens`: optional, present when prompt caching is
  used; total input tokens = `cache_read_input_tokens + cache_creation_input_tokens + input_tokens` — full caching
  mechanics are in `agents/agent-caching.md`, not repeated here [DOC S-osulh6sh; cross-ref agents/agent-caching.md].

### MCP connector (Messages API, no separate MCP client)
- Beta feature, beta header `mcp-client-2025-11-20` (the prior `mcp-client-2025-04-04` is deprecated); connects
  directly to remote MCP servers from a Messages API request without running an MCP client [DOC S-qpqoaaqj].
- Request shape: an `mcp_servers` array of `{"type": "url", "url": "<remote MCP server url>", "name": "<label>",
  "authorization_token": "<OAuth bearer token>"}`, paired with a `tools` array entry `{"type": "mcp_toolset",
  "mcp_server_name": "<name>"}` to enable that server's tools (allowlist/denylist and per-tool config are
  supported on the toolset entry) [DOC S-qpqoaaqj].
- Multiple MCP servers can be attached in one request; OAuth Bearer tokens are the supported authentication
  mechanism; not available on Amazon Bedrock or Google Cloud as of the fetched page [DOC S-qpqoaaqj].
- Claude only calls an MCP tool when the request maps to that tool's described capability (explicit or implicit),
  never for general knowledge questions about the connected service [DOC S-qpqoaaqj].

### Token Counting API
- `POST /v1/messages/count_tokens`: same `messages` (and optional `system`, `tools`) shape as `/v1/messages` but no
  `max_tokens`; counts tokens including tools, images and documents without creating a Message. Response:
  `{"input_tokens": <n>}` [DOC S-jrsntqfg].
- Optional headers `anthropic-user-profile-id` (requires the `user-profiles` beta) and `anthropic-workspace-id`
  are shared with the Messages endpoint [DOC S-jrsntqfg].

### Message Batches API
- A batch is limited to 100,000 requests or 256 MB, whichever is reached first; each batched request needs
  `max_tokens >= 1` (`max_tokens: 0` cache pre-warming is not supported inside a batch) [DOC S-3pftmimx].
- Processing: most batches finish within 1 hour; results become accessible once all messages complete or after 24
  hours, whichever is first; a batch that has not finished within 24 hours expires; results remain downloadable for
  29 days after creation (the batch metadata itself stays viewable after that, without results) [DOC S-3pftmimx].
- Discount: 50% off standard Messages pricing; prompt-caching discounts stack with the batch discount, but cache
  hits inside a batch are best-effort (30-98% observed hit rates, since batch requests run asynchronously and
  concurrently) [DOC S-3pftmimx].
- `processing_status` values: `in_progress` -> `ended` (or `canceling` -> `ended` after a cancel request; canceled
  batches may contain partial results for requests already processed) [DOC S-3pftmimx].
- Endpoints: create (`POST /v1/messages/batches`), retrieve, list, cancel (`POST
  /v1/messages/batches/{id}/cancel`) — poll `processing_status` on the retrieval endpoint until `ended` [DOC
  S-3pftmimx].
- `output-300k-2026-03-24` beta header raises the batch `max_tokens` cap to 300,000 (standard cap 128k) on Claude
  Opus 5.5, Opus 5, Opus 4.8, Opus 4.7, Opus 4.6, Sonnet 5, and Sonnet 4.6 [DOC S-3pftmimx, S-eu3n3hyf].
- Batch requests still count toward the shared Message Batches API rate limits (RPM to all Batches endpoints, plus
  a cap on batch requests in the processing queue) — see `claude/api-limits.csv` [DOC S-5uxkh3j5].

### Files API
- `POST /v1/files` (multipart form, field `file`; optional `expires_in_seconds` 3,600-7,776,000) returns
  `FileMetadata` (`id`, `filename`, `mime_type`, `size_bytes`, `downloadable`, `expires_at`); `GET /v1/files`
  (paginated, `limit` 1-1,000, default 20, or up to 100 `ids[]` in one call, mutually exclusive with `page`/`limit`);
  `GET /v1/files/{id}`; `GET /v1/files/{id}/content` (download; `downloadable` defaults to false);
  `DELETE /v1/files/{id}` [DOC S-wbsmegvl].
- `downloadable` is false for files you upload: only files created by skills or the code execution tool can be
  downloaded. [DOC S-b4bqwu2v]
- Limits: 500 MB max file size, 1 TB total storage per organization, up to 100 workspaces per organization
  (contact account team for more); filename 1-255 characters, forbidden characters `< > : " | ? * \ /` and Unicode
  0-31 [DOC S-b4bqwu2v].
- Files are workspace-scoped, not per-user/session: any API key with access to the workspace can read any file in
  it; the docs warn never to accept a `file_id` from an untrusted/end-user source, and to use one workspace per
  tenant in a multi-tenant app [DOC S-b4bqwu2v].
- Referencing a file in a Messages request uses a `document` block (`{"type":"document","source":{"type":"file",
  "file_id":"..."}}`, PDF or `text/plain`), an `image` block, or a `container_upload` block (code execution tool
  input) [DOC S-b4bqwu2v].
- Files API operations (upload/list/retrieve/delete/download) are free; file content used in a Messages request is
  billed as input tokens [DOC S-b4bqwu2v].
- As of the fetched page the Files API needs no beta header (`files-api-2025-04-14` is optional/legacy and still
  accepted for backward compatibility) [DOC S-b4bqwu2v].

### Rate limits and error behavior
- Two limit types: **spend limits** (monthly cost cap per tier: Start $500, Build $1,000, Scale $200,000; Custom
  tier has none) and **rate limits** (RPM / ITPM / OTPM per model class, token-bucket algorithm) [DOC S-5uxkh3j5].
- Reaching the tier spend cap returns HTTP 429 `rate_limit_error` with `error.details.error_code:
  "enforced_spend_limit_reached"` and **no** `retry-after` header — retries (including SDK auto-retry) fail until
  the next calendar month or a tier increase; a self-set spend limit instead returns HTTP 400
  `invalid_request_error` [DOC S-5uxkh3j5].
- Only uncached input tokens count toward ITPM for most models: `cache_read_input_tokens` is excluded (except
  Claude Haiku 3.5, which counts it); `OTPM` is metered on actual output tokens produced, not the `max_tokens`
  request value [DOC S-5uxkh3j5].
- Response headers: `retry-after` (seconds; absent on the spend-cap 429) and the `anthropic-ratelimit-{requests,
  tokens,input-tokens,output-tokens}-{limit,remaining,reset}` family (reset times in RFC 3339); Priority Tier adds
  `anthropic-priority-{input,output}-tokens-*` [DOC S-5uxkh3j5].
- Full RPM/ITPM/OTPM figures by tier and model class, Message Batches API limits, and Files API's ~500 requests/min
  cap are in `claude/api-limits.csv` [DOC S-5uxkh3j5, S-b4bqwu2v].
- HTTP error taxonomy (`400`-`529`) and the 32 MB Messages/Token-Counting request-size ceiling, 256 MB Batch, 500 MB
  Files ceilings are already documented in `agents/agent-error-catalogue.md`; not repeated here [DOC S1847;
  cross-ref agents/agent-error-catalogue.md].

## Reference
See `claude/models.csv` (model id, context window, max output, notes, source) and `claude/api-limits.csv`
(RPM/ITPM/OTPM per tier and model class, Message Batches API limits, Files API rate limit).

Cross-links: prompt caching mechanics and the `cache_control`/TTL/invalidation model are in
`agents/agent-caching.md` (not repeated here); the HTTP error taxonomy, `tool_use`/`tool_result` pairing failures,
strict-schema restrictions and MCP tool-count/size guidance are in `agents/agent-error-catalogue.md` (not repeated
here). Both articles' References now point back to this one for Messages API request/response shape and the
Batches/Files/rate-limit numbers.

## Examples
Python tool-use loop with one tool (a device lookup), and a `count_tokens` call, using placeholders only
(`PL-LT-00123`):

```python
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY

tools = [{
    "name": "get_device_status",
    "description": "Look up an endpoint's compliance status by device id.",
    "input_schema": {
        "type": "object",
        "properties": {"device_id": {"type": "string", "description": "e.g. PL-LT-00123"}},
        "required": ["device_id"],
    },
}]

messages = [{"role": "user", "content": "Is PL-LT-00123 compliant?"}]

response = client.messages.create(
    model="claude-sonnet-5",
    max_tokens=1024,
    tools=tools,
    tool_choice={"type": "auto"},
    messages=messages,
)

if response.stop_reason == "tool_use":
    tool_use = next(b for b in response.content if b.type == "tool_use")
    # tool_use.input == {"device_id": "PL-LT-00123"}
    result_text = "compliant"  # replace with a real lookup against your inventory
    messages.append({"role": "assistant", "content": response.content})
    messages.append({
        "role": "user",
        "content": [{
            "type": "tool_result",
            "tool_use_id": tool_use.id,
            "content": result_text,
            "is_error": False,
        }],
    })
    final = client.messages.create(
        model="claude-sonnet-5", max_tokens=1024, tools=tools, messages=messages,
    )
    print(final.content[0].text)

# Token Counting API: check size before sending
count = client.messages.count_tokens(
    model="claude-sonnet-5",
    tools=tools,
    messages=[{"role": "user", "content": "Is PL-LT-00123 compliant?"}],
)
print(count.input_tokens)
```
</content>
