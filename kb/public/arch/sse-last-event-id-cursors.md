---
topic: arch/sse-last-event-id-cursors
priority: P3
applies_to: "WHATWG HTML Standard section 9.2 server-sent events (Living Standard, last updated 9 October 2026); FastAPI 0.135.0+ (fastapi.sse); Starlette 1.7.0; nginx ngx_http_proxy_module"
retrieved_utc: 2026-10-11
sources: [S-6r5cdtdk, S-e5yw2g7y, S-ciivqlqu, S-6nbqywql, S-l4qgsnr4]
status: partial
---

# Server-sent events with Last-Event-ID cursors outside MCP

## Summary
Server-sent events (SSE) are a plain-HTTP, one-way event stream in the `text/event-stream` format,
defined by the WHATWG HTML Standard. The `id:` field gives each event a string; when a browser
`EventSource` reconnects it sends the last such string back in a `Last-Event-ID` request header. That
echo is the only resume mechanism the standard defines, so a "cursor" (a monotonically increasing
sequence number the server maps to a query) is a server-side convention built on an opaque string,
not part of the standard. FastAPI 0.135.0 added first-party SSE support. MCP's Streamable HTTP
transport dropped `Last-Event-ID` resumability in 2026-07-28 (see
`mcp/transports-streamable-http.md:26`); this article is about SSE outside MCP.

## Facts
- The HTML Standard is a Living Standard (no numbered versions); its server-sent events section is 9.2
  and the rendered page read for this article states "Last Updated 9 October 2026". [DOC S-6r5cdtdk]
- Stream format: MIME type `text/event-stream`, always UTF-8 (no way to select another encoding), lines
  ended by CRLF, LF or CR. A blank line dispatches the event being built; a line starting with `:` is a
  comment and is ignored; recognised field names are `event`, `data`, `id` and `retry` (compared
  literally, other names ignored). [DOC S-6r5cdtdk]
- Several `data:` lines in one block are joined with LF into one `data` string, and an incomplete
  event at end of stream (no final blank line) is discarded, so every event must end with a blank line.
  [DOC S-6r5cdtdk]
- The `id` field sets the stream's last event ID buffer unless the value contains U+0000 (then it is
  ignored); an `id` with an empty value resets the last event ID to the empty string. The last event
  ID persists across later events that carry no `id`. A block with `id` but no `data` fires no event,
  yet still updates the last event ID string. [DOC S-6r5cdtdk]
- On reconnect the user agent sets the `Last-Event-ID` request header to the last event ID string
  (UTF-8) only when that string is not empty; so a first connection carries no such header. The spec
  describes the value space as essentially any UTF-8 string without U+0000, LF or CR, and links an
  open issue to define it better. [DOC S-6r5cdtdk]
- Reconnection: the user agent waits the event source's reconnection time (initially an
  implementation-defined value "probably in the region of a few seconds"), may add more delay such as
  exponential backoff, then re-fetches. A `retry:` field made only of ASCII digits sets the reconnection
  time in milliseconds. [DOC S-6r5cdtdk]
- Ending the stream: a client reconnects when the connection closes, and "a client can be told to stop
  reconnecting using the HTTP 204 No Content response code"; per the processing model any response whose
  status is not 200, or whose `Content-Type` is not `text/event-stream`, fails the connection with no
  reconnect. HTTP 301 and 307 redirects are followed. [DOC S-6r5cdtdk]
- The `EventSource` constructor takes a URL and one option, `withCredentials`; the only header the
  processing model adds on its own is `Last-Event-ID` on reconnect (user agents may also set `Accept`).
  [DOC S-6r5cdtdk]
- A browser `EventSource` therefore cannot attach a custom header such as `Authorization`, cannot
  choose the HTTP method, and cannot send a request body; authentication has to ride on cookies
  (`withCredentials`) or on the URL, and a non-browser client library is free to send what it wants.
  [DER S-6r5cdtdk: the constructor signature has no headers, method or body parameter and the spec's
  request header list is fixed, so a browser cannot do more than the spec lets it]
- Authoring note: legacy proxies can drop idle connections after a short timeout, so authors can send
  a comment line (starting with `:`) every 15 seconds or so. [DOC S-6r5cdtdk]
- FastAPI (official, added in FastAPI 0.135.0) streams SSE from a path operation that `yield`s with
  `response_class=EventSourceResponse` imported from `fastapi.sse`. Yielding `ServerSentEvent` objects
  sets `data`, `raw_data`, `event`, `id`, `retry` or `comment`; `data` is always JSON-encoded,
  `raw_data` is sent as-is, and the two are mutually exclusive. [DOC S-e5yw2g7y]
- FastAPI's page documents resuming: a browser sends the last received `id` in `Last-Event-ID`, which
  the endpoint can read as a header parameter and use to skip ahead (its example starts at the received
  id plus one). It also states SSE works with any HTTP method, and that FastAPI by default sends a
  keep-alive ping comment every 15 seconds when idle and sets `Cache-Control: no-cache` and
  `X-Accel-Buffering: no`. [DOC S-e5yw2g7y]
- Starlette's `StreamingResponse` takes an async generator or a normal generator/iterator and streams
  the response body; its docs page (1.7.0) shows no SSE-specific helper. [DOC S-ciivqlqu]
- nginx's `proxy_buffering` directive defaults to `on`; buffering can also be switched per response
  by the upstream sending `X-Accel-Buffering` with `yes` or `no`, unless `proxy_ignore_headers`
  disables that capability. [DOC S-6nbqywql]
- MCP's Streamable HTTP transport (revision 2026-07-28) states a server SHOULD ignore a
  `Last-Event-ID` header and SHOULD send `X-Accel-Buffering: no` on SSE streams; those rules are MCP's
  and do not change the general SSE behaviour above. [DOC S-l4qgsnr4]
- A cursor design on top of this: use a server-assigned, monotonically increasing integer (a sequence
  column or log offset) as the event `id`, and on reconnect answer with rows where the sequence is
  greater than the header value, ordered ascending; an absent header means "start from the current
  head" or from a start parameter the client sends in the URL. The header is client-supplied text, so
  parse it as an integer and reject or ignore a value that does not parse. Sending `id:` on every event
  keeps the client's last event ID current; the resumed stream is at-least-once only if the server
  keeps the rows (the standard defines no retention or replay window). [DER S-6r5cdtdk, S-e5yw2g7y: the
  standard treats the id as an opaque string echoed back and the FastAPI example parses it as a number,
  so the mapping to a query is an application convention]
- The page text read does not state a maximum length for the `id` value, nor how long a server must
  retain events for replay; both are the server's choice. [UNK]

## Reference
| Item | Value | Source tag |
|---|---|---|
| MIME type | `text/event-stream`, UTF-8 | DOC |
| Fields | `data`, `event`, `id`, `retry`; `:` comment | DOC |
| Dispatch | blank line | DOC |
| Resume request header | `Last-Event-ID` (omitted when last id empty) | DOC |
| Stop reconnecting | HTTP 204 (or any non-200 / wrong content type) | DOC |
| Keep-alive | comment line about every 15 s | DOC |
| Proxy buffering off | upstream sends `X-Accel-Buffering: no` | DOC |
| FastAPI import | `from fastapi.sse import EventSourceResponse, ServerSentEvent` (0.135.0+) | DOC |

## Examples
Wire format of three events, the second carrying a cursor id; a reconnect after it would send
`Last-Event-ID: 42`.

```
: keep-alive

id: 41
event: job_update
data: {"job": "a", "state": "running"}

id: 42
event: job_update
data: {"job": "a", "state": "done"}

```

- SNIPPET: FastAPI endpoint that resumes after the `Last-Event-ID` cursor from a store; context: FastAPI 0.135.0+, `fetch_after` is a placeholder for the application's query (`WHERE seq > :after ORDER BY seq`); checked: no [DER S-e5yw2g7y: adapted from the FastAPI page's Last-Event-ID example by replacing its list with a store lookup]

```python
from collections.abc import AsyncIterable
from typing import Annotated

from fastapi import FastAPI, Header
from fastapi.sse import EventSourceResponse, ServerSentEvent

app = FastAPI()

async def fetch_after(after: int) -> list[tuple[int, dict]]:
    ...  # rows (seq, payload) with seq > after, ascending

@app.get("/jobs/stream", response_class=EventSourceResponse)
async def stream_jobs(
    last_event_id: Annotated[int | None, Header()] = None,
) -> AsyncIterable[ServerSentEvent]:
    after = last_event_id if last_event_id is not None else 0
    for seq, payload in await fetch_after(after):
        yield ServerSentEvent(data=payload, event="job_update", id=str(seq))
```
