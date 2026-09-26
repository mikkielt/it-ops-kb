---
topic: claude/elicitation
priority: P1
applies_to: "Claude Code 2.1.281 docs (retrieved 2026-09-23)"
retrieved_utc: 2026-09-26
sources: [S740, S743, S745, S746, S710]
status: complete
---
# MCP elicitation in Claude Code

## Summary
Claude Code supports MCP elicitation since 2.1.76 (2026-03-14): form mode shows an interactive dialog; URL mode
opens the browser. No configuration is needed. `Elicitation`/`ElicitationResult` hooks can auto-answer or override.
Claude Code keeps stdio servers on the earlier (handshake) protocol by default, so a stdio server's elicitation arrives
as a legacy `elicitation/create` request unless `MCP_PROTOCOL_NEGOTIATION=auto` is set.

## Facts
- "Added MCP elicitation support": servers can request structured input mid-task via a dialog (form fields or browser URL) — 2.1.76, 2026-03-14. [DOC S746]
- Elicitation dialogs appear automatically when a server requests them; no user configuration is required. [DOC S740]
- Form mode: dialog with server-defined fields; URL mode: Claude Code opens a browser URL, the user completes the flow and confirms in the CLI. [DOC S740]
- URL mode passes the URL as an argument to the system URL handler, with a length cap (~8,000 characters unescaped, ~4,000 if heavily percent-escaped); over the cap the user can only decline. [DOC S740]
- A call waiting on an open elicitation dialog is not moved to the background. [DOC S740]
- To auto-respond without a dialog, use the `Elicitation` hook. [DOC S740]
- Client runtimes: v1 (MCP TypeScript SDK 1.x) and v2 (TypeScript SDK 2.0, adds 2026-07-28); v2 is used on 2.1.232+ in sessions that fetch feature flags, and by default on 2.1.274+ in others. [DOC S740]
- On v2, Claude Code probes HTTP servers for 2026-07-28 by default; it probes stdio servers only when `MCP_PROTOCOL_NEGOTIATION=auto`; otherwise it connects as v1 does (earlier protocol). [DOC S740]
- `MCP_PROTOCOL_NEGOTIATION`: `auto` probes HTTP, connector and stdio servers; `legacy` skips the probe for all; requires 2.1.221+. [DOC S745]
- `MCP_SDK_GENERATION` pins runtime `v1` or `v2` (2.1.218+). [DOC S745]
- 2.1.281 (2026-09-23) "Added MCP URL-mode elicitation on 2026-07-28 protocol connections". [DOC S746]
- 2.1.238 fixed stdio MCP servers receiving a `server/discover` request before `initialize`. [DOC S746]
- 2.1.117 fixed `elicitation/create` requests auto-cancelling in print/SDK mode when the server finishes connecting mid-turn. [DOC S746]
- Form-mode elicitation delivered as MRTR (`InputRequiredResult`) on 2026-07-28 connections: no explicit statement found in docs or changelog. [UNK]
- Behaviour of elicitation in non-interactive `-p` mode without a hook: not documented beyond the 2.1.117 fix. [UNK]

## Reference
| Server transport | Default protocol in Claude Code (v2 runtime) | Elicitation delivery |
|---|---|---|
| stdio | earlier handshake protocol (no probe) | legacy `elicitation/create` request mid-call |
| stdio + `MCP_PROTOCOL_NEGOTIATION=auto` | 2026-07-28 if server answers `server/discover` | MRTR `InputRequiredResult` |
| HTTP | probes 2026-07-28 | MRTR (URL mode added 2.1.281) |
(Delivery column derived from S740/S745 plus spec S710.)

## Examples
Elicitation hook output that declines every request from server `inventory`:
`{"hookSpecificOutput":{"hookEventName":"Elicitation","action":"decline"}}` with matcher `inventory`.
