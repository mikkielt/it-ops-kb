---
topic: agents/agent-caching
priority: P1
applies_to: "Anthropic prompt caching (Claude Developer Platform, retrieved 2026-09-25); Claude Code >=2.1.251; OpenAI Responses/Completions API; Azure OpenAI/Foundry Models; MCP spec 2026-07-28"
retrieved_utc: 2026-09-26
sources: [S2130, S2131, S2132, S2133, S2134, S2135, S2136, S2159]
status: complete
---

# Caching in agent systems

## Summary

Anthropic prompt caching stores the KV state for an unchanged prefix, keyed by up to 4 explicit `cache_control` breakpoints, with a 5-minute default TTL (refreshed on each hit) or an optional 1-hour TTL; cache writes cost more than base input, cache reads cost a fraction, and the cache is invalidated by anything that changes the rendered prefix ahead of a breakpoint, most importantly tool definitions, in the fixed order tools → system → messages [DOC S2130]. Claude Code surfaces this as a `Prompt cache (main)` line in `/usage` including named likely causes for a miss, and separately documents that MCP tool-list changes, model switches and `/compact` are among the things that force a rebuild [DOC S2132]. OpenAI and Azure OpenAI apply the same shape (prefix caching on by default, a 1,024-token minimum prefix on GPT-5.6 and later, up to ~90% discount on cache reads) with provider-side differences in TTL model; from GPT-5.6 OpenAI also offers explicit breakpoints and charges 1.25x for cache writes [DOC S2133,S2134]. The MCP spec (2026-07-28) adds server-side result caching for `tools/list`/similar list operations (`ttlMs`, `cacheScope`) and recommends deterministic tool ordering specifically to raise LLM prompt-cache hit rates, extending `mcp/tools.md`'s existing note on `CacheableResult` [DOC S2135,S2136].

## Facts

### Anthropic prompt caching

- Up to 4 explicit cache breakpoints per request are supported via `cache_control` blocks [DOC S2130].
- Two TTLs: 5-minute (default/ephemeral, refreshed on each cache hit) and 1-hour (opt-in, `"ttl": "1h"`) [DOC S2130].
- Minimum cacheable prefix length is model-dependent: as low as 512 tokens for some newer/thinking-oriented models (per the fetched page: "Claude Fable 5.1, Mythos 5.1, Opus 5.5, Opus 5, Fable 5, Mythos 5"), 1,024 tokens for Sonnet 5 / Sonnet 4.6 / Sonnet 4.5 / Opus 4.8, 2,048 tokens for Opus 4.7/Mythos Preview, and 4,096 tokens for Haiku 4.5 and Opus 4.6/4.5 [DOC S2130].
- Cache write pricing: 5-minute writes cost 1.25x the base input token price; 1-hour writes cost 2x [DOC S2130,S2131].
- Cache read (hit and refresh) pricing: 0.1x base input price for all models except Claude Fable 5.1 and Claude Mythos 5.1 (0.025x) and Claude Opus 5.5 (0.05x); the prompt-caching and pricing pages give the same multipliers [DOC S2130, S2131].
- Invalidation hierarchy: caching follows the order **tools → system → messages**; a change to tool definitions invalidates everything (tools, system, messages); toggling web search or citations, or switching `speed`, invalidates system+messages but not tools; a change to `tool_choice` or adding/removing images invalidates only the messages cache; thinking parameters and `output_config.effort` always invalidate messages and, depending on the model, tools and system too [DOC S2130]. This is the concrete "invalidation hierarchy" the assignment asked for.
- Usage fields: responses report `cache_creation_input_tokens` (tokens newly written to cache) and `cache_read_input_tokens` (tokens served from cache); `input_tokens` covers only what follows the last cache breakpoint; total input = read + creation + input [DOC S2130].
- Practical rules: a cache breakpoint must sit on a block identical across requests (never on a changing timestamp or per-request value); the server looks back up to 20 blocks for a prior cache write; a hit requires the full prefix, text and images, to match exactly; a cache can be pre-warmed with a `max_tokens: 0` request that only writes the cache [DOC S2130].

### Claude Code and the cache

- Claude Code (>=2.1.251) shows a `Prompt cache (main)` line in `/usage`: request count, percent of input tokens served from cache, count of misses (with time of last miss and tokens re-cached), a count of "expected rebuilds" (Claude Code's own compaction or tool-result clearing, not counted as ordinary misses), and whether the cache is currently warm against its TTL [DOC S2132].
- A miss is counted when a request reprocessed more than 5% and at least 2,000 tokens of what could have been read from cache; from v2.1.260 the line names a likely cause, e.g. `likely cause: tool definitions changed` [DOC S2132].
- Things that break the cache in a Claude Code session, per the same page: editing/changing tool definitions or MCP servers, toggling settings that sit ahead of the system/messages boundary, switching model mid-session, and — as an *expected* (not counted-as-miss) rebuild — Claude Code's own `/compact` or its clearing of old tool results from context [DOC S2132].
- Cache lifetime in Claude Code depends on the billing surface: one hour on a Claude subscription, dropping to 5 minutes once usage credits are being drawn on (unless the 1-hour TTL is chosen explicitly), and 5 minutes by default on an API key or cloud-provider deployment [DOC S2132].
- MCP tool definitions are deferred by default in current Claude Code (only names + server instructions enter context until a tool is actually used), which also reduces how much of the prompt prefix churns when MCP servers are added or reconfigured [DOC S2132].
- `/clear` resets the cache-stat line along with the rest of the session block; `/compact` itself is a large request because it must read the conversation it is about to summarize [DOC S2132].
- General implication: before building a bespoke cache-hit-rate dashboard, check whether Claude Code's built-in `/usage` line or OTel export already covers it — a team that treats "no new mechanism without an observed failure" as policy would need to name what a bespoke dashboard catches that the built-in ones do not [DER — general cost/complexity discipline for agent tooling].

### OpenAI / Azure OpenAI (comparison)

- OpenAI: caching is on by default for supported models; minimum prefix is 1,024 visible input tokens for GPT-5.6 and later (varies by settings for earlier models); cache reuse requires the *entire* rendered prefix to match exactly (model, tools, schemas, reasoning effort, verbosity all count); caches are not shared across organizations or across regional processing boundaries [DOC S2133].
- OpenAI pricing and breakpoints by generation: GPT-5.6 and later charge 1.25x the uncached input rate for a cache write and 0.1x for a read, and support explicit breakpoints (`prompt_cache_options.mode: explicit`, `prompt_cache_breakpoint` on a content block, up to four cache writes per request) besides the default implicit breakpoint at the latest eligible message; earlier models are implicit-only, with a model-dependent cached-input rate and no cache-write charge [DOC S2133].
- TTL: GPT-5.6+ uses `prompt_cache_options.ttl`, only `30m` supported (also the default); earlier models use `prompt_cache_retention` with `in_memory` (typically 5-10 minutes of inactivity, up to an hour) or `24h` (GPT-5.5 and GPT-5.5 Pro: `24h` only); where both exist the default is `24h` unless the organization has Zero Data Retention, then `in_memory` [DOC S2133].
- Azure OpenAI (Microsoft Foundry Models): same 1,024-token minimum-prefix rule (first 1,024 tokens must be identical); discount applies to Standard deployments' input pricing, with up to 100% discount on Provisioned deployment types; supported on GPT-4o and newer [DOC S2134].

### MCP-side caching and `listChanged`

- The MCP spec (2026-07-28 revision) documents that `tools/list` responses support pagination and a caching utility, returning `ttlMs` and `cacheScope` (`public`/`private`) fields on the result (already noted for `mcp/tools.md`, not repeated there) [DOC S2135] — this is the same `CacheableResult` mechanism `mcp/tools.md` cites.
- Servers that declare the `tools` capability with `listChanged: true` SHOULD send `notifications/tools/list_changed` when the tool set changes; a client that has opened a `subscriptions/listen` stream with `toolsListChanged: true` receives it and is expected to re-fetch `tools/list` [DOC S2135].
- The spec explicitly ties deterministic list ordering to prompt caching: "Servers SHOULD return tools in a deterministic order... Deterministic ordering enables clients to reliably cache the tool list and improves LLM prompt cache hit rates when tools are included in model context" [DOC S2135].
- The tool-set returned by `tools/list` MUST NOT vary per-connection or as a side effect of other requests, but MAY vary by the caller's authorization/granted scopes, since credentials are per-request, not connection state — relevant to an MCP server that varies its tool list by the caller's permission tier [DOC S2135; DER — general implication for tiered-access MCP servers].

## Reference

See `claude/messages-api.md` for the Messages API request/response shape (usage fields, tool-use loop,
stop_reason values) that carries the `cache_creation_input_tokens`/`cache_read_input_tokens` fields this article
covers; not repeated here.

See `agents/hybrid-retrieval.md` for prompt caching applied to Anthropic's Contextual Retrieval technique (the
one-time ~$1.02/million-document-token cost of prepending an LLM-generated context string to each chunk relies on
this article's cache-write/cache-read pricing).

| provider | min cacheable prefix | TTL | write price multiplier | read price multiplier |
|---|---|---|---|---|
| Anthropic (Sonnet 5/4.6/4.5, Opus 4.8) | 1,024 tokens | 5 min (default) or 1 h | 1.25x (5m) / 2x (1h) | 0.1x |
| Anthropic (Haiku 4.5 / Opus 4.6-4.5) | 4,096 tokens | 5 min or 1 h | 1.25x / 2x | 0.1x |
| Anthropic (Fable 5.1, Mythos 5.1) | 512 tokens | 5 min or 1 h | 1.25x / 2x | 0.025x |
| Anthropic (Opus 5.5) | 512 tokens | 5 min or 1 h | 1.25x / 2x | 0.05x |
| Anthropic (Opus 5, Fable 5, Mythos 5) | 512 tokens | 5 min or 1 h | 1.25x / 2x | 0.1x |
| OpenAI GPT-5.6+ | 1,024 visible tokens | 30 min (only option) | n/a (automatic) | ~0.1x |
| OpenAI earlier models | varies | 5-10 min or 24h | n/a (automatic) | ~0.1x |
| Azure OpenAI (GPT-4o+) | 1,024 tokens | provider-managed | n/a (automatic) | discount, up to 100% on Provisioned |

Invalidation hierarchy (Anthropic): `tools` (top) → `system` → `messages` (bottom); changing something at a level invalidates that level and everything below it [DOC S2130].

## Examples

For a stdio MCP server serving example devices (`PL-LT-00123`, `corp.example.com`), the cache-friendly pattern is: a fixed, alphabetically or capability-ordered tool list with no timestamps in tool descriptions, example values (e.g. `jan.kowalski`) kept out of the system prompt (put per-call values in `messages`, not `system`), and reading `/usage`'s `Prompt cache (main)` line or the OTel cache-token metrics (see `claude/otel-monitoring.md`) rather than building a bespoke cache-hit dashboard [DER S2130,S2132,S2135].
