# Token usage: exact counts from session transcripts

What a kb lookup costs in tokens, read from what Claude Code already recorded and never estimated: `_tools/kbusage.py` reads a session transcript, and the query log keeps the counts of every lookup in a usage sidecar beside its run file (`kb/_self/querylog.md`, Surfaces and Store). Standard library only, with no model and no network, so the same transcript always gives the same record.

## How tokens are measured

- **The counts are the API's own.** For every API request Claude Code writes the response's `usage` into the session transcript (`~/.claude/projects/<project>/<session>.jsonl`): `input_tokens` (uncached), `cache_creation_input_tokens` (with its one-hour part in `cache_creation.ephemeral_1h_input_tokens`), `cache_read_input_tokens` and `output_tokens`. These are the numbers billing uses (`claude/agent-sdk.md`, `agents/agent-caching.md`); the reader copies them and adds them up.
- **One count per request.** A request's response is written as one record per content block, all with the same `requestId` and `usage`; the reader counts each `requestId` once, with the most output any of its records reports. Records with the model `<synthetic>` (no API call) are left out.
- **A prompt's requests.** Every user record carries the `promptId` of the prompt it belongs to (the prompt itself and each tool result); an assistant record belongs to the prompt of the user record before it. The reader reads the main transcript from its end, in blocks, back to the last user record of another prompt, so reading one prompt of a long session reads only its end.
- **Subagents.** A subagent writes its own transcript, `<session>/subagents/agent-<id>.jsonl`, whose first record carries the `promptId` of the prompt that started it, and `agent-<id>.meta.json` names its `agentType`. Its requests count under `sub`, by agent group; the main transcript's own sidechain records are left out, so nothing counts twice. A background subagent still running when the session ends is counted as far as it got.
- **Per tool call.** The API reports no tokens per tool call. A step is one request whose `tool_use` blocks the next user record answered: the reader keeps each result's tool group, whether it succeeded (`is_error`) and its length in characters, and `grow`, how much the next request's whole input (uncached + cache write + cache read) exceeds this request's. `grow` is the context the step added: the tool results, plus the request's own reply and the framing Claude Code adds; it is exact as a difference, not a count of the results alone, and it is left out when the context shrank (a compaction) or no request followed.
- **`start`** is the whole input of the prompt's first request: the context the prompt began with (system prompt, tools, instructions, earlier turns).
- **Checked against the session's own totals.** A transcript's `cost-state` record holds the session's totals per model (`modelUsage`); on a Claude Code 2.1.283 session the sum of every prompt's `main` and `sub` counts equalled them for input, cache write, cache read and output.
- **The format is observed, not documented.** Claude Code documents no transcript schema (the kb has no fact on it); the reader relies on the fields above, skips a line that is not JSON, and gives no record when it finds no request of the prompt. `READER_VERSION` changes when what the reader returns changes.

## What a record holds, and what never leaves the transcript

| kept | never kept |
|---|---|
| model ids (`claude-...`, anything else as `other`) | prompts, replies, thinking, system text |
| per model: `requests`, `in`, `cw`, `cw1h`, `cr`, `out` | tool inputs (commands, urls, questions) and tool results |
| agent groups: `general-purpose`, `Explore`, `Plan`, `kb-lookup`, `kb-reviewer`, else `other` | agent names and descriptions, other agent types |
| tool groups: a kb tool's name (`kb_pack`, ...), `docs:<server>` for the three documentation servers, a built-in tool's name, `mcp:other` for any other MCP tool, else `other` | other MCP servers' and tools' names |
| per step: tool group, `ok`, `chars`, `grow` | file paths, the transcript path, `requestId`, uuids, session, user and organisation ids, `cwd`, git branch |

- **The transcript is read where it is, never copied.** A hook gets `transcript_path` in its input; the query log reads each kb prompt's records in memory and writes one `usage` spool row of the record. The path is written to no file: the `SessionEnd` launcher passes it to the distill it starts as a command-line argument.
- **At most `STEPS_MAX` steps** per record; `cut` counts the steps left out.

## `kbusage.py`

- `python3 _tools/kbusage.py TRANSCRIPT [--prompt PROMPT_ID]` prints one JSON line per prompt of a transcript (or the one named), numbered in order instead of by its id: the record the sidecar keeps, or `"usage": null`.
- `python3 _tools/kbusage.py tree PATH [--format json] [--top N]` reads a transcript with its `subagents/*.jsonl`, or a project directory of transcripts, and prints the calls and characters of tool results by tool, Bash command head, file path and agent group; a call repeated across resumed transcripts counts once. Its check exits 1 when a group's rows do not add up to the totals or the characters exceed `TOKEN_SPAN_MAX` (16) per token of fresh input, and 2 for a missing path or no transcripts. The distill does not use it.
- `kbusage.prompt_usage(transcript_path, prompt_id)` is what the query log's distill calls: the record, or None.
- Tested in `_tools/test_kbusage.py` on the fixture transcript `_tools/fixtures/kbusage/session.jsonl` and its `session/subagents/`.

## In the query log

- **After the prompt, not at its `Stop`.** When the `Stop` hook runs, the transcript does not hold the answer's own request yet: on Claude Code 2.1.283 a record read at `Stop` missed each prompt's last request, while the same transcript read after the session equalled the run's reported usage exactly. So a prompt's usage is read at the next event of its session that comes after it (`ql_capture.add_usage`: one `usage` row for each prompt of the session's spool file that used the kb, a `kb_hook` or `mcp` row or a prompt with a `kb_intent`, and has none of this reader yet):
  - **the next prompt:** the async `UserPromptSubmit` capture writes the rows of the session's earlier kb prompts, never of the prompt it records;
  - **the session's end:** `SessionEnd` marks the session closed and starts `querylog.py distill --session <id> --transcript <path>`, which waits for the distill lock (`USAGE_LOCK_WAIT_S`), writes the rows of the prompts still without one (the last prompt), then distills (`kb/_self/querylog.md`, Surfaces and Distill).
- **`SessionEnd` does not always run in `claude -p`.** On Claude Code 2.1.283 some headless runs ran their `SessionEnd` hooks and others, with the same flags and tools, ran none, not even a plain command hook that appends its input to a file. A session that ends without it closes by idle time (`SESSION_IDLE_CLOSED_S`), and its last prompt gets a usage row only if a later prompt of the session (`claude -p --resume`) comes first.
- **What gets no usage:** a prompt the `kb:` hook answered without the model (no request), the last prompt of a session that ended without `SessionEnd`, and a `kb_ask.py` run (its `claude -p` runs with hooks off). The sidecar header's `missing` counts the written entries without usage.
- **Distill:** the written entries with a `usage` row of this `READER_VERSION` become the lines of `kb/_querylog/usage/<yyyy-mm>/<run-id>.jsonl`, beside the run file of the same run, committed and pushed with it (Store, Delivery).
- **Digest:** per week, the lookups with usage, input tokens per lookup (median and p90), output (median), the share of input read from the cache and spent in subagents, and the steps made only of kb tools with their median `grow` and result characters (Reporting).
