---
topic: mcp/tasks-extension
priority: P1
applies_to: "MCP Tasks extension io.modelcontextprotocol/tasks for 2026-07-28"
retrieved_utc: 2026-09-28
sources: [S713, S714, S715, S718, S701, S740, S746]
status: complete
---
# Tasks extension (`io.modelcontextprotocol/tasks`)

## Summary
In 2026-07-28 tasks moved out of core into an official extension. A server may answer `tools/call` with a
`CreateTaskResult` (`resultType: "task"`); the client polls `tasks/get`, answers mid-flight input via `tasks/update`,
and may `tasks/cancel`. `tasks/result` (blocking) and `tasks/list` were removed. Extensions are opt-in on both sides.

## Facts
- Tasks moved to extension `io.modelcontextprotocol/tasks`; blocking `tasks/result` replaced by polling `tasks/get`; new `tasks/update`; `tasks/list` removed; servers may return task handles without per-request opt-in. [DOC S701]
- Only `tools/call` currently supports task-augmented execution. [DOC S718]
- Server MUST NOT return `CreateTaskResult` to a client that did not include the extension capability on that request; otherwise `-32021` if it cannot serve without a task. [DOC S718]
- Statuses: `working`, `input_required`, `completed`, `failed`, `cancelled`; the last three are terminal. [DOC S713]
- `Task` carries `taskId`, status, `ttlMs` (number or null), optional `pollIntervalMs`; the server MUST durably create the task before returning `CreateTaskResult`. [DOC S718]
- Clients SHOULD respect `pollIntervalMs`; servers MAY rate-limit faster polling. [DOC S718]
- `input_required` tasks expose `inputRequests` (MRTR shape) in `tasks/get`; client answers with `tasks/update`; server acks with empty result (eventually consistent). [DOC S718]
- `notifications/cancelled` MUST NOT be used for tasks; use `tasks/cancel`; cancellation is cooperative. [DOC S718]
- Optional `notifications/tasks` via `subscriptions/listen`; polling is the default. [DOC S713]
- Extensions are disabled by default and need explicit opt-in; SDKs may choose whether to implement them. [DOC S714]
- The community-maintained extension matrix lists no Tasks column and no Claude Code row. [DOC S715]
- Claude Code's MCP page lists the client capabilities it declares on 2026-07-28 connections (elicitation form and URL) and names no Tasks extension; the changelog has no Tasks entry either. [DER S740, S746: pages searched 2026-09-28]

## Reference
| Method | Direction | Purpose |
|---|---|---|
| tools/call → CreateTaskResult | C→S | start, receive handle |
| tasks/get | C→S | poll status/result/inputRequests |
| tasks/update | C→S | deliver inputResponses |
| tasks/cancel | C→S | request cancellation |

## Examples
A `logs.collect` call for PL-LT-00123 could return `{"resultType":"task","task":{"taskId":"...","status":"working","ttlMs":3600000,"pollIntervalMs":5000}}` (shape per S718 examples).
