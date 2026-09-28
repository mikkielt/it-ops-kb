# Token usage: exact counts from session transcripts

What a kb lookup costs in tokens, read from what Claude Code already recorded and never estimated: `_tools/kbusage.py` reads a session transcript, and the query log keeps the counts of every lookup in a usage sidecar beside its run file (`kb/_self/querylog.md`, Surfaces and Store). Standard library only, with no model and no network, so the same transcript always gives the same record.

## How tokens are measured

- **The counts are the API's own.** For every API request Claude Code writes the response's `usage` into the session transcript (`~/.claude/projects/<project>/<session>.jsonl`): `input_tokens` (uncached), `cache_creation_input_tokens` (with its one-hour part in `cache_creation.ephemeral_1h_input_tokens`), `cache_read_input_tokens` and `output_tokens`. These are the numbers billing uses (`claude/agent-sdk.md`, `agents/agent-caching.md`); the reader copies them and adds them up.
- **One count per request.** A request's response is written as one record per content block, all with the same `requestId` and `usage`; the reader counts each `requestId` once, with the most output any of its records reports. Records with the model `<synthetic>` (no API call) are left out.
- **A prompt's requests.** Every user record carries the `promptId` of the prompt it belongs to (the prompt itself and each tool result); an assistant record belongs to the prompt of the user record before it. The reader reads the main transcript from its end, in blocks, back to the last user record of another prompt, so a Stop hook reads one prompt, not the whole session.
- **Subagents.** A subagent writes its own transcript, `<session>/subagents/agent-<id>.jsonl`, whose first record carries the `promptId` of the prompt that started it, and `agent-<id>.meta.json` names its `agentType`. Its requests count under `sub`, by agent group; the main transcript's own sidechain records are left out, so nothing counts twice. A background subagent still running when the prompt's `Stop` fires is counted as far as it got.
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

- **The transcript is read where it is, never copied.** The query log's async `Stop` capture gets `transcript_path` in its hook input, reads the prompt's records in memory and writes one `usage` spool row of the record; the path is not stored, and distill never opens a transcript.
- **At most `STEPS_MAX` steps** per record; `cut` counts the steps left out.

## `kbusage.py`

- `python3 _tools/kbusage.py TRANSCRIPT [--prompt PROMPT_ID]` prints one JSON line per prompt of a transcript (or the one named), numbered in order instead of by its id: the record the sidecar keeps, or `"usage": null`.
- `kbusage.prompt_usage(transcript_path, prompt_id)` is what capture calls: the record, or None.
- Tested in `_tools/test_kbusage.py` on the fixture transcript `_tools/fixtures/kbusage/session.jsonl` and its `session/subagents/`.

## In the query log

- **Capture:** a prompt that used the kb gets a `usage` row beside its `stop` row (`kb/_self/querylog.md`, Surfaces); a prompt the `kb:` hook answered without the model makes no request and gets none.
- **Distill:** the written entries with a `usage` row of this `READER_VERSION` become the lines of `kb/_querylog/usage/<yyyy-mm>/<run-id>.jsonl`, beside the run file of the same run, committed and pushed with it (Store, Delivery).
- **Digest:** per week, the lookups with usage, input tokens per lookup (median and p90), output (median), the share of input read from the cache and spent in subagents, and the steps made only of kb tools with their median `grow` and result characters (Reporting).
