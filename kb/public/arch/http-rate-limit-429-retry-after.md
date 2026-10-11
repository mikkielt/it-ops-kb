---
topic: arch/http-rate-limit-429-retry-after
priority: P3
applies_to: "RFC 6585 (April 2012); RFC 9110 (June 2022, STD 97); draft-ietf-httpapi-ratelimit-headers-11 (Internet-Draft, 23 May 2026); limits 5.8.0; slowapi v0.1.10 (FastAPI/Starlette)"
retrieved_utc: 2026-10-11
sources: [S-uhsdbxii, S-wct3uoax, S-fdye2dae, S-6xunll63, S-l7o2xn5e, S-bnosg22i, S-455diive, S-5uxkh3j5, S623]
status: partial
---

# Server-side per-caller rate limits answering 429 with Retry-After

## Summary
HTTP's answer to "too many requests" is status 429 (RFC 6585) with an optional `Retry-After` header
(RFC 9110). The standards leave everything else to the server: who a "caller" is, how requests are
counted and where the counters live. A newer IETF draft would add `RateLimit-Policy` and `RateLimit`
header fields but is not yet a standard. For a FastAPI/Starlette service the usual library is
`slowapi` (third party, built on the `limits` library); its defaults key by client IP, keep counters
in process memory and send no `Retry-After` unless header injection is switched on. Vendor behaviours
(429 with and without `Retry-After`) are in `defender/permissions-limits.md:23`,
`graph/throttling.md:28`, `claude/messages-api.md:138` and `agents/agent-error-catalogue.md:22`.

## Facts
- RFC 6585 section 4 (April 2012, Standards Track) defines status 429: the user has sent too many
  requests in a given amount of time ("rate limiting"). The response SHOULD include details of the
  condition and MAY include a `Retry-After` header; its example answers 429 with `Retry-After: 3600`.
  [DOC S-uhsdbxii]
- RFC 6585 states it does not define how the origin server identifies the user or counts requests:
  limits may be per resource, across the whole server or among a set of servers, and the user may be
  identified by authentication credentials or a stateful cookie. It also says a 429 response MUST NOT
  be stored by a cache. [DOC S-uhsdbxii]
- RFC 9110 section 10.2.3 (June 2022, Internet Standard STD 97) defines `Retry-After = HTTP-date /
  delay-seconds`, where `delay-seconds` is a non-negative decimal integer number of seconds; its
  examples are `Retry-After: Fri, 31 Dec 1999 23:59:59 GMT` and `Retry-After: 120`. With a 503 it says
  how long the service is expected to be unavailable; with a 3xx it is the minimum wait before the
  redirected request. [DOC S-wct3uoax]
- Vendors differ on whether a 429 carries `Retry-After`: Defender for Endpoint APIs send it in seconds
  (`defender/permissions-limits.md:23`), whereas a Claude API spend-cap 429 deliberately has none
  (`claude/messages-api.md:138`, `agents/agent-error-catalogue.md:22`); a client must therefore
  handle both cases. [DOC S623, S-5uxkh3j5]
- The `RateLimit-Policy` and `RateLimit` header fields are defined only in an Internet-Draft,
  `draft-ietf-httpapi-ratelimit-headers`, revision 11 dated 23 May 2026 (intended status Standards
  Track, expires 24 November 2026). The draft itself says it is inappropriate to cite Internet-Drafts
  other than as "work in progress"; it is not a standard and can change or be dropped. [DOC S-fdye2dae]
- Draft revision 11 syntax: `RateLimit-Policy` is a list of quota policy items, each a string name
  with `q` (quota, required), `qu` (quota unit, default `requests`), `w` (window in seconds) and `pk`
  (partition key); `RateLimit` items carry `r` (remaining quota, required), `t` (seconds until the
  window resets) and `pk`. Example: `RateLimit-Policy: "burst";q=100;w=60,"daily";q=1000;w=86400`.
  Neither field may appear in a trailer. [DOC S-fdye2dae]
- Draft revision 11 relation to `Retry-After`: when both appear, `Retry-After` MUST take precedence and
  the effective window MAY be ignored; `Retry-After` SHOULD NOT point earlier than the end of the
  effective window. The draft mandates no throttling algorithm and no link between `RateLimit` values
  and the status code, and clients must not treat a positive `r` as a guarantee of service. [DOC
  S-fdye2dae]
- Draft revision 11 on partitioning ("who is the caller"): servers MAY divide quota per user,
  application, HTTP method, resource or a combination, SHOULD document how the partition key is
  generated, SHOULD use only information present in the request, and should avoid sensitive data in
  the key. [DOC S-fdye2dae]
- The `limits` library (docs for 5.8.0, community) offers three strategies: fixed window (one counter
  per resource and limit, cheapest, bursts possible at window edges), moving window (a log of
  timestamps, exact, more memory) and sliding window counter (two weighted counters, added in 4.1). It
  notes that for the sliding window counter the `memcached` and in-memory storages adjust buckets from
  the first hit, which can let an attacker bypass limits in the initial sampling period. [COMMUNITY
  S-6xunll63]
- The Claude API documents its own rate limits as using the token-bucket algorithm (see
  `claude/messages-api.md:136`); the `limits` strategies page read for this article lists no
  token-bucket strategy. [DOC S-5uxkh3j5]
- `slowapi` v0.1.10 describes itself as a rate limiting library for Starlette and FastAPI adapted
  from flask-limiter; it lists redis, memcached and memory backends ("memory as a fallback"), and
  requires the endpoint to take a `request: Request` argument. It is MIT-licensed and not part of
  FastAPI or Starlette. [COMMUNITY S-l7o2xn5e]
- In slowapi v0.1.10 `Limiter` requires a `key_func`, "a callable that returns the domain to rate
  limit by"; the bundled `get_remote_address` returns `request.client.host` (or `127.0.0.1` if none),
  and `get_ipaddr` reads an `X_FORWARDED_FOR` header first, with a docstring pointing to uvicorn's
  `ProxyHeadersMiddleware` as the more robust way to determine the client IP. [CODE S-455diive:
  slowapi/extension.py#Limiter; S-bnosg22i: slowapi/util.py#get_remote_address]
- In slowapi v0.1.10 `_rate_limit_exceeded_handler` returns a JSON body with status 429 and passes it
  to `Limiter._inject_headers`, which writes the `X-RateLimit-*` fields and `Retry-After` only when
  `headers_enabled` is true (constructor default `False`); `Retry-After` is written as seconds, or as an
  HTTP-date when the limiter's `retry_after` option is `"http-date"`. [CODE S-455diive:
  slowapi/extension.py#_rate_limit_exceeded_handler, Limiter._inject_headers]
- In slowapi v0.1.10 the storage defaults to `memory://` when no storage URI or setting is given, and
  `in_memory_fallback_enabled` switches to an in-memory store when the configured storage is down.
  [CODE S-455diive: slowapi/extension.py#Limiter]
- Keying a per-caller limit: because the standards leave identification open, "per caller" means
  whatever the key function returns; keying on the authenticated identity (token subject, API key id)
  gives each caller its own budget, while keying on client IP merges callers behind one NAT or proxy
  and gives a caller with several addresses several budgets. A limiter must run after authentication
  to see the identity. [DER S-uhsdbxii, S-fdye2dae, S-455diive: RFC 6585 leaves identification to the
  server, the draft lists per-user partitions, and slowapi's key is a caller-supplied function]
- Where the counters live: an in-process counter (slowapi's default `memory://`) exists once per
  worker process, so with N worker processes a caller can use up to about N times the configured
  limit, and a restart resets it; a single shared budget needs a store all workers reach (Redis or
  memcached in `limits`, or a table in the application database, where each counted request is a
  write and the increment must be atomic). [DER S-455diive, S-6xunll63: the default store is
  in-process memory and the library lists shared network stores as alternatives; the multiplication
  follows from separate process memory]
- No FastAPI or Starlette documentation page on rate limiting was found by a code search of their docs
  directories for "rate limit", so the framework's own stance is not confirmed. [UNK]

## Reference
| Header | Defined by | Status |
|---|---|---|
| `Retry-After` | RFC 9110 section 10.2.3 | Internet Standard |
| 429 Too Many Requests | RFC 6585 section 4 | Standards Track RFC |
| `RateLimit-Policy`, `RateLimit` | draft-ietf-httpapi-ratelimit-headers-11 | Internet-Draft, not a standard |
| `X-RateLimit-Limit/Remaining/Reset` | slowapi (when `headers_enabled`) | library convention |

## Examples
A throttled response in the shape RFC 6585 shows, with a `Retry-After` in seconds:

```
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
Retry-After: 30

{"error": "rate limit exceeded", "detail": "50 requests per hour per caller"}
```

- SNIPPET: slowapi limiter keyed on an authenticated caller id with `Retry-After` enabled; context: slowapi v0.1.10, FastAPI, `request.state.caller_id` is assumed to be set by earlier authentication middleware; checked: no [DER S-455diive, S-l7o2xn5e: adapted from the slowapi README/docs quick start; the key function and `headers_enabled` follow the v0.1.10 `Limiter` signature]

```python
from fastapi import FastAPI, Request, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

def caller_key(request: Request) -> str:
    return request.state.caller_id  # set by auth middleware, not the client IP

limiter = Limiter(key_func=caller_key, headers_enabled=True)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/items")
@limiter.limit("50/hour")
async def items(request: Request, response: Response):
    return {"items": []}
```
