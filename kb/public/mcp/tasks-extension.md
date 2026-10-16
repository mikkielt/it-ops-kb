---
topic: mcp/tasks-extension
priority: P1
applies_to: "MCP Tasks extension io.modelcontextprotocol/tasks for 2026-07-28"
retrieved_utc: 2026-10-16
sources: [S713, S714, S715, S718, S701, S740, S746]
status: partial
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
- A task is the stateless protocol's explicit identifier for long-running work: the client uses `task.taskId` for all later `tasks/get`, `tasks/update` and `tasks/cancel` calls, and SHOULD persist task ids to durable storage so polling can resume after a crash or restart. [DOC S718]
- Over Streamable HTTP the client MUST set the `Mcp-Name` header to `params.taskId` on `tasks/get`, `tasks/update` and `tasks/cancel`, so intermediaries can route to "the server instance holding its state, which is typically required for correctness". [DOC S718]
- A client opts into pushed status with a `subscriptions/listen` request whose `notifications` filter carries `taskIds`; the acknowledgement lists the ids the server agreed to; each `notifications/tasks` notification carries the full task, as `tasks/get` would return it at that moment, and the client MAY keep polling too. [DOC S718]
- A client that asks for task notifications without declaring the extension gets `-32021`; `notifications/progress` and `notifications/message` MUST NOT be sent on the `subscriptions/listen` stream for a task. [DOC S718]
- Security section: a server MAY use task ids as bearer tokens for stored state and MUST generate them with enough entropy that a third party cannot guess them, and it MUST authenticate and authorize every task-related request; with no `tasks/list`, one caller's tasks cannot leak to another. [DOC S718]
- The spec text does not say whether a task created by one principal may be read or updated by another (a subagent, a second client) when the server's authorization allows it; it names only "permission to access a task". [UNK S718: security section read 2026-10-16]
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
