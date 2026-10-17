---
topic: claude/statusline
priority: P3
applies_to: "Claude Code status line docs page, dateModified 2026-10-14, read 2026-10-17 (Claude Code 2.1.29x era; fields carry their own minimum versions)"
retrieved_utc: 2026-10-17
sources: [S-rkp4qc7b, S743, S745]
status: complete
---

# Claude Code status line: what the command receives and when it runs

## Summary
The `statusLine` setting names a shell command. Claude Code runs it locally with one JSON object on stdin and shows
what it prints on stdout under the prompt; it spends no API tokens. The JSON carries the session id and name, model,
directories, estimated cost and durations, context window use, rate limit use for subscribers, prompt cache
statistics, and git, pull request and worktree context. The command re-runs on session events (a new assistant
message, `/compact`, a permission mode or vim mode change) and, if `refreshInterval` is set, on a timer. A
`subagentStatusLine` setting does the same for the subagent rows in the agent panel.

## Facts
### Configuration and trust
- `statusLine` is an object with `type: "command"` and a `command` (a script path or an inline shell command), plus
  optional `padding` (extra horizontal spacing in characters, default 0), `refreshInterval` (re-run every N seconds,
  minimum 1) and `hideVimModeIndicator` (hides the built-in `-- INSERT --` text when the script renders `vim.mode`
  itself). It goes in user settings or project settings. [DOC S-rkp4qc7b]
- `/statusline <natural language>` has Claude Code write a script under `~/.claude/` and update the settings;
  removing the `statusLine` field, or asking `/statusline` to remove it, disables the line. [DOC S-rkp4qc7b]
- The command runs under the same workspace-trust rule as hooks in settings files: the line stays blank until the
  folder is trusted, and `claude --debug` logs `Status line command skipped: workspace trust not accepted`. [DOC
  S-rkp4qc7b]
- `subagentStatusLine` is subject to the same trust, `disableAllHooks` and `allowManagedHooksOnly` gates as
  `statusLine`; a plugin can ship a default `subagentStatusLine`, but unlike a hook it does not run under
  `allowManagedHooksOnly` even when the plugin is force-enabled in managed `enabledPlugins`. [DOC S-rkp4qc7b]

### When it runs
- The command runs once when a session starts or resumes, then again on a new assistant message, when `/compact`
  finishes, on a permission mode change, when vim mode toggles, when the `command` setting changes, when a
  `refreshInterval` timer elapses, when a rate limit window in the last data reaches its `resets_at`, and when a warm
  prompt cache in the last data reaches its `expires_at`. [DOC S-rkp4qc7b]
- Updates are debounced at 300 ms, except a change to the `command` itself, which runs at once; a new trigger while
  the script still runs cancels the in-flight run. The event triggers go quiet while the main session is idle (for
  example a coordinator waiting on background subagents), so a time-based or externally sourced segment needs
  `refreshInterval`. [DOC S-rkp4qc7b]
- Claude Code displays the output only after the script exits with code 0: a non-zero exit or empty output blanks the
  line, and a slow script delays the update. [DOC S-rkp4qc7b]
- The status line temporarily hides during some interface interactions, including the help menu and permission
  prompts. Outside fullscreen rendering, notifications share its row (system notices on the right); in fullscreen
  rendering they get a row of their own. [DOC S-rkp4qc7b]
- The script cannot read the terminal size with `tput cols`, because its output is captured; Claude Code sets the
  `COLUMNS` and `LINES` environment variables before each run. Output may be several lines, ANSI colors and OSC 8
  links. [DOC S-rkp4qc7b]
- Status line commands run with `CLAUDE_CODE_CHILD_SESSION=1` in their environment, like hook commands and the Bash,
  PowerShell and Monitor tools. [DOC S745]

### Session, cost and context in the input
- The JSON on stdin has `session_id` (unique session identifier), `session_name` (the `--name` or `/rename` value, else
  the AI-generated title; absent when the session has neither, and the default display name does not fill it),
  `prompt_id` (the UUID of the user prompt being processed, matching the `prompt.id` attribute on OpenTelemetry
  events; absent before the first input), `transcript_path` and `version`. [DOC S-rkp4qc7b]
- `session_id` is stable for the life of a session and unique per session, so the docs advise it for a per-session
  cache file name; a process id changes on every run and defeats a cache. [DOC S-rkp4qc7b]
- `cost.total_cost_usd` is the estimated session cost in USD, computed client-side at list price unless a
  `modelPricing` table is in effect, so it may differ from the actual bill; it resets to $0 when `/clear` starts a new
  session (before v2.1.211 the total carried over). [DOC S-rkp4qc7b]
- Other `cost` fields: `total_duration_ms` (wall-clock time the session has run, accumulating across resumes and not
  counting time while it is not running), `total_api_duration_ms` (time waiting for API responses),
  `total_lines_added` and `total_lines_removed`. [DOC S-rkp4qc7b]
- `context_window` holds `context_window_size` (200000 by default, 1000000 for models with extended context),
  `total_input_tokens` and `total_output_tokens` (what the context window holds as of the most recent API response;
  input includes cache reads and writes), `used_percentage`, `remaining_percentage` and `current_usage` (the last
  call's `input_tokens`, `output_tokens`, `cache_creation_input_tokens` and `cache_read_input_tokens`). [DOC
  S-rkp4qc7b]
- `used_percentage` counts input tokens only (`input_tokens + cache_creation_input_tokens + cache_read_input_tokens`)
  and leaves out `output_tokens`; computing it by hand from `current_usage` must use the same formula to match. [DOC
  S-rkp4qc7b]
- `current_usage` is `null` before the first API call and again after `/compact` until the next call; `used_percentage`
  and `remaining_percentage` may be `null` early in a session, so a script reads them with a fallback. [DOC S-rkp4qc7b]
- `exceeds_200k_tokens` is true when input, cache and output tokens of the last response together pass 200k, a fixed
  threshold whatever the window size. [DOC S-rkp4qc7b]
- `/context` can read higher than the status line because it adds an estimate for messages added since the last API
  response; the page names `used_percentage` as the simplest accurate context state. [DOC S-rkp4qc7b]

### Other fields in the input
- `model.id` and `model.display_name`; `fast_mode`; `effort.level` (`low` to `max`, live value, absent when the model
  has no effort parameter); `thinking.enabled`; `output_style.name`; `vim.mode` (only with vim mode on); `agent.name`
  (only with `--agent` or agent settings). [DOC S-rkp4qc7b]
- Directories: `cwd` and `workspace.current_dir` (same value), `workspace.project_dir` (where Claude Code was
  launched), `workspace.added_dirs`, `workspace.git_worktree` (any linked git worktree) and `workspace.repo.host`,
  `owner` and `name` parsed from the `origin` remote; the `worktree.*` object (`name`, `path`, `branch`,
  `original_cwd`, `original_branch`) exists only inside a Claude Code worktree session. [DOC S-rkp4qc7b]
- `pr.number`, `pr.url`, `pr.review_state` and `pr.kind` describe the open pull request of the branch, or for a GitLab
  remote the open merge request (`pr.kind` is `mr`; merge request data needs v2.1.234+); the object is absent when no
  open request is found and removed once it merges or closes. [DOC S-rkp4qc7b]
- `rate_limits.five_hour` and `rate_limits.seven_day` each give `used_percentage` (0 to 100) and `resets_at` (Unix
  epoch seconds); `rate_limits` appears only for claude.ai Pro and Max subscribers or behind a Claude apps gateway
  with a spend limit, only after the first API response, and each window may be absent on its own. [DOC S-rkp4qc7b]
- Behind a Claude apps gateway, `rate_limits.spend_limit` gives `used_percentage` and `resets_at` (v2.1.251+) and,
  optionally, `used_usd`, `limit_usd` and `period` (`daily`, `weekly` or `monthly`; v2.1.284+ on both sides), which
  Claude Code reads from the gateway about every five minutes and which stay absent when
  `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` is set. [DOC S-rkp4qc7b]
- `prompt_cache` (v2.1.251+, main conversation only, absent until its first API response) gives `warm`,
  `caching_observed`, `ttl` (`5m` or `1h`), `expires_at`, `requests`, `misses`, `expected_rebuilds`, `hit_ratio` (0 to
  1), `cache_write_tokens`, `miss_recache_tokens`, `last_miss_at`, `recache_tokens_if_cold` and, from v2.1.260,
  `last_miss_cause` and `miss_causes`. [DOC S-rkp4qc7b]

### Subagent status lines
- `subagentStatusLine` runs one command per refresh tick with all visible subagent rows as one JSON object on stdin:
  the base hook fields, `columns` and a `tasks` array. The command writes one JSON line per row to override,
  `{"id": ..., "content": ...}`; a row without `id` keeps the default rendering and empty `content` hides it. [DOC
  S-rkp4qc7b]
- Each task carries `id`, `type` (`local_agent`), `agentType` (v2.1.293+, the value hooks get as `agent_type`),
  `status` (`running`, `completed`, `failed`, `killed`), `description`, `label`, `startTime` (epoch ms), `tokenCount`,
  `tokenSamples` (up to the last 16 readings) and `cwd`, and optionally `name`, `model`, `effort` and
  `contextWindowSize`. [DOC S-rkp4qc7b]

### How it fits
- For an operator watching many parallel sessions, the status line is the per-session surface that shows cost
  and context use without a model call: a script can print `cost.total_cost_usd`, `context_window.used_percentage`
  and the session id, and a `refreshInterval` keeps it current while the session is idle. The same session id is what
  `CLAUDE_CODE_SESSION_ID` and the hook input `session_id` carry, so a line can be joined to hook logs. [DER
  S-rkp4qc7b, S745, S743: the input fields, the refresh triggers and the session id in hook input]
- The cost figure is an estimate at list price, not a bill, so a budget alert built on it is a guide; the status line
  has no field for a team's total spend except behind a gateway that sets a spend limit. [DER S-rkp4qc7b: the
  `cost.total_cost_usd` description and the `rate_limits.spend_limit` fields]

## Reference
- Docs: `https://code.claude.com/docs/en/statusline` (S-rkp4qc7b). Subagent rows use the base hook fields from
  `https://code.claude.com/docs/en/hooks` (S743).
- Related kb articles:
  - `claude/hooks.md` — hook input fields, `session_id` and the other events; `Notification` input and timing.
  - `claude/settings-and-scopes.md` — where `statusLine` can be set and how managed settings narrow it.
  - `claude/otel-monitoring.md` — fleet-level cost and usage telemetry, as against one session's line.
  - `claude/parallel-sessions.md` — which parallel-work option fits which coordination need.

## Examples
- SNIPPET: a status line that shows the model, context use and estimated cost; context: Claude Code with `jq` installed, user settings; checked: syntax [DER S-rkp4qc7b: field names from the input table, one `jq` expression]
```json
{
  "statusLine": {
    "type": "command",
    "command": "jq -r '\"[\\(.model.display_name)] \\(.context_window.used_percentage // 0)% ctx, $\\(.cost.total_cost_usd // 0)\"'",
    "refreshInterval": 30
  }
}
```
