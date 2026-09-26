---
topic: claude/ci-and-headless
priority: P2
applies_to: "Claude Code v2.1.x (code.claude.com docs, retrieved 2026-09-26)"
retrieved_utc: 2026-09-26
sources: [S1800, S1801, S1802, S-32ilsmsf, S-l6l42j6e, S-pilcrlei, S1824]
status: partial
---

# `claude -p` CLI details, GitHub Actions/GitLab CI parameters, sandboxing and gateways for CI

## Summary
This article covers the CLI mechanics and CI-integration parameters for running Claude Code unattended: the
`-p`/`--print` flag's interaction with other flags, bare mode, structured-output and streaming flags, exit/signal
behaviour, the `anthropics/claude-code-action` GitHub Action's OIDC/cloud-provider setup, GitLab CI/CD's job
shape and variables, the Bash sandbox's filesystem/network isolation for a CI runner, and LLM gateways as a
CI credential layer. It complements `agents/headless-agent-runtimes.md`, which covers the cross-runtime
comparison (routines, Copilot coding agent, GitLab Duo Agent Platform, `gh-aw`) and does not repeat that
article's `claude -p` exit-code/`--output-format` summary or its runtime-comparison table.

## Facts
- `-p` rejects `--bg` outright, and rejects `--cloud` with a task description, both with an error naming the conflict; `--cloud` with a session ID or claude.ai/code URL plus `-p` instead queues a message into that existing cloud session and exits. [DOC S1800]
- Without `--bare`, a `-p` session loads the same context an interactive session would (hooks in the project's `.claude/settings.json`, `.mcp.json` servers, CLAUDE.md, plugins), even in a folder never trusted before: `-p` shows no workspace-trust dialog and no per-server approval prompt. [DOC S1800]
- `--add-dir` under `--bare` is a partial exception: skills in that directory's `.claude/skills/` still load, but its `.claude/commands/` and `.claude/agents/` are still skipped. [DOC S1800]
- In `--bare` mode Claude has access to Bash, file-read and file-edit tools only; extra context must be passed explicitly with `--append-system-prompt`/`--append-system-prompt-file`, `--settings`, `--mcp-config`, `--agents`, or `--plugin-dir`/`--plugin-url`. [DOC S1800]
- A background Bash task (e.g. a dev server) started during `claude -p` is terminated about five seconds after Claude returns its final result and stdin closes; a background subagent or workflow instead keeps `claude -p` open until it finishes, its result folded into the final output. [DOC S1800]
- The wait for a background subagent/workflow ends after 10 minutes of continuous idle waiting by default (`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` to change it, `0` to disable); a Monitor watch started during `-p` is waited on until it times out (five minutes by default) or that 10-minute cap ends the wait, whichever is first. [DOC S1800]
- SIGTERM on a `claude -p` run exits with code 143, leaves the in-progress turn unrecorded, terminates the process tree of any running Bash command, then runs `SessionEnd` hooks only (no new tool call, model request, or other hook) before exiting; SIGINT (or the Agent SDK's `interrupt()`) ends the turn cleanly instead. [DOC S1800]
- A permission prompt still pending when SIGTERM arrives is left unanswered; if the Agent SDK closes the session instead, it ends Claude Code's input first and Claude Code cancels the prompt once input ends. [DOC S1800]
- `CLAUDE_CODE_RESUME_INTERRUPTED_TURN=1` makes a resumed session continue the interrupted turn instead of starting fresh on the next prompt. [DOC S1800]
- If the working directory of a `claude -p`/Agent SDK session is deleted mid-session, the session keeps running; the next turn emits a `stream-json` warning message and shell commands fail until the directory exists again. [DOC S1800]
- Piped stdin to `-p` is capped at 10 MB; exceeding it exits with a clear error and non-zero status — write larger input to a file and reference its path in the prompt instead. [DOC S1800]
- `--output-format json` with `--continue`/`--resume` reports the whole conversation's cumulative cost, earlier runs' spend included, not just the new call's. [DOC S1800]
- `--json-schema` (with `--output-format json`) validates structured output against a JSON Schema, delivered in `structured_output`; an invalid schema exits with `Error: --json-schema is not a valid JSON Schema`; the `format` keyword (e.g. `"format":"email"`) is accepted as an annotation only, never enforced. Before v2.1.205, an invalid schema was silently ignored and any schema containing `format` was rejected as invalid. [DOC S1800]
- `--output-format stream-json` with `--verbose --include-partial-messages` streams token-level events; the last line is a `result` message with final text, cost and session metadata; a slow consumer makes Claude Code wait for queued output to drain before exit, capped at 30 seconds (2 seconds before v2.1.214). [DOC S1800]
- Subagent messages in the stream carry `parent_tool_use_id`; by default only `tool_use`/`tool_result` blocks are forwarded, and `--forward-subagent-text` (or `CLAUDE_CODE_FORWARD_SUBAGENT_TEXT`, v2.1.211+) adds the subagent's own text/thinking blocks, including nested subagents and forked skills at every depth (v2.1.219+/v2.1.275+ for some nesting cases). [DOC S1800]
- `system/api_retry` events fire on a retryable API failure; on v2.1.246+, a `401`/`403` rejecting an `apiKeyHelper` credential is retried quietly for the first two attempts before the event starts appearing from the third attempt on. [DOC S1800]
- The `system/init` event's optional `mcp_servers`/`mcp_server_errors` fields (v2.1.219+) let a CI job detect an MCP server that failed config validation (`unknown_type`, `url_missing_type`, `invalid_config`, `reserved_name`) without a fragile stderr scrape; `plugins`/`plugin_errors` do the same for plugin load failures, including a `--plugin-dir` path/archive failure (`path` field requires v2.1.283+). [DOC S1800]
- `--max-turns` (print mode only) exits with an error once the limit is hit, with no limit by default; under `--input-format stream-json`, a message still queued when the limit ends a turn stays queued and starts a fresh turn with its own limit. [DOC S1824]
- `--max-budget-usd` (print mode only, v2.1.217+ for enforcement) is a hard dollar cap; subagent spend counts toward it; hitting the cap fails any further subagent spawn with `Budget limit reached` and stops running background subagents; a resumed conversation's restored prior-run totals don't count toward a new cap. [DOC S1824]
- `--permission-prompts none` (v2.1.259+) denies (rather than blocks on) any prompt nobody can answer in print mode, distinct from `--permission-prompt-tool <name>`, which names an MCP tool to answer prompts and cannot approve a tool marked as requiring user interaction (converted to deny, v2.1.199+); Claude Code waits for that tool's server up to the `MCP_TIMEOUT` startup timeout (30s default). [DOC S1824]
- `--mcp-config <file-or-json>` (space-separated, multiple allowed) makes `-p` wait for still-pending servers before the first turn, up to the `MCP_TIMEOUT` startup timeout (30s default); a server with a cached tool list skips the wait and connects on first use (v2.1.221+). [DOC S1824]
- The Claude Code GitHub Action detects mode from the workflow: no `prompt` input → interactive mode, waiting for the `@claude` trigger phrase (configurable via `trigger_phrase`) in a comment, review, or issue title/body; a `prompt` input → automation mode, running on any GitHub event including `schedule:`, subject only to the actor checks. [DOC S1801]
- Before starting, the Action checks write access (skipped for actor-less events like `schedule`) and that the actor is human, not a bot, unless listed in `allowed_bots`; a scheduled run is attributed to whichever user last edited the workflow's cron line, so a bot-owned cron line needs that bot listed in `allowed_bots`. [DOC S1801]
- Automation-mode results default to the workflow run log; posting to the PR/issue needs the prompt to direct it and a tool that can post, e.g. the review example's `--comment` plus `mcp__github_inline_comment__create_inline_comment` in `claude_args`' `--allowedTools`. [DOC S1801]
- Workload identity federation for the GitHub Action needs `anthropic_federation_rule_id` (`fdrl_...`) and `anthropic_organization_id`, plus optionally `anthropic_service_account_id` (`svac_...`) and `anthropic_workspace_id` (`wrkspc_...`); the workflow must grant `id-token: write` even when a custom `github_token` is passed. [DOC S1801]
- Action authentication inputs: `anthropic_api_key` (Claude API key), `claude_code_oauth_token` (from `claude setup-token`, Pro/Max/Team/Enterprise), or the federation inputs above; a shared org-wide secret should use an API key rather than an OAuth token, since the token is tied to the individual who ran `setup-token`. [DOC S1801]
- Cloud-provider inputs on the Action: `use_bedrock: "true"`, `use_vertex: "true"`, `use_foundry: "true"`; all three authenticate via the workflow's GitHub OIDC token exchanged for cloud credentials, so no static cloud secret is stored. [DOC S-32ilsmsf,S1801]
- For Amazon Bedrock, the GitHub OIDC identity provider uses issuer `https://token.actions.githubusercontent.com` and audience `sts.amazonaws.com`; the trusted IAM role's policy should scope the trust condition to `repo:your-org/your-repo:*` and needs `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream`, `bedrock:ListInferenceProfiles`, `bedrock:GetInferenceProfile`, plus two `aws-marketplace` subscription actions. [DOC S-32ilsmsf]
- For Google Cloud's Agent Platform, the Workload Identity Pool's GitHub OIDC provider trusts issuer `https://token.actions.githubusercontent.com`, restricted by an attribute condition to the repository; the impersonated service account needs only `roles/aiplatform.user` (Vertex AI User). [DOC S-32ilsmsf]
- For Microsoft Foundry, a Microsoft Entra application (or user-assigned managed identity) gets a federated identity credential trusting the repository's GitHub-issued tokens and the `Azure AI User` role on the Foundry resource; secrets to add are `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`. [DOC S-32ilsmsf]
- Cloud-provider secrets by provider: `AWS_ROLE_TO_ASSUME` (Bedrock); `GCP_WORKLOAD_IDENTITY_PROVIDER` + `GCP_SERVICE_ACCOUNT` (Agent Platform); `AZURE_CLIENT_ID` + `AZURE_TENANT_ID` + `AZURE_SUBSCRIPTION_ID` (Foundry); a custom GitHub App also needs `APP_ID` + `APP_PRIVATE_KEY`. [DOC S-32ilsmsf]
- On public repositories, a comment with the trigger phrase from any user starts the cloud-provider workflow before the Action's write-access check runs, since the credential/token-exchange steps run first — this consumes Actions minutes and leaves audit-log entries even for a rejected user, unless a separate write-access-check step is added ahead of the credential steps. [DOC S-32ilsmsf]
- Claude Code GitLab CI/CD is GitLab-maintained and beta; the minimal job installs the CLI via `curl -fsSL https://claude.ai/install.sh | bash` (placed in `~/.local/bin`, not on `PATH` by default) inside a `node:24-alpine3.21` image, gated by `rules:` on `$CI_PIPELINE_SOURCE` (`web`, `merge_request_event`). [DOC S1802]
- The quick-setup job's `script:` invokes `claude -p "${AI_FLOW_INPUT:-...}" --permission-mode acceptEdits --allowedTools "Bash Read Edit Write mcp__gitlab" --debug`, reading `AI_FLOW_INPUT`/`AI_FLOW_CONTEXT`/`AI_FLOW_EVENT` for context from web/API-triggered pipelines. [DOC S1802]
- Manual/production GitLab setup adds project credentials for GitLab API operations: the default `CI_JOB_TOKEN`, or a Project Access Token with `api` scope stored as `GITLAB_ACCESS_TOKEN` (masked). [DOC S1802]
- GitLab's Bedrock job example exchanges a GitLab-minted OIDC token (`id_tokens: GITLAB_OIDC_TOKEN`, `aud` set to the GitLab instance URL) for AWS credentials via `aws sts assume-role-with-web-identity`, exporting `AWS_ROLE_TO_ASSUME`/`AWS_REGION` and setting `CLAUDE_CODE_USE_BEDROCK: "1"`. [DOC S1802]
- GitLab's Agent Platform (Vertex) job example writes the GitLab OIDC token to a file and builds an `external_account` credential JSON (`credential_source.file`) for Application Default Credentials, exporting `GOOGLE_APPLICATION_CREDENTIALS` and setting `CLAUDE_CODE_USE_VERTEX: "1"` plus `ANTHROPIC_VERTEX_PROJECT_ID`. [DOC S1802]
- GitLab CI cost/perf controls named by the vendor: `--max-turns`, the job-level `timeout:` keyword (e.g. `timeout: 30m`), and limiting concurrency; the docs note exact CLI flags can vary by `@anthropic-ai/claude-code` version and suggest running `claude --help` in the job to check. [DOC S1802]
- The Bash sandbox (macOS Seatbelt; Linux/WSL2 via `bubblewrap` + `socat`, native Windows unsupported — run under WSL2) enforces the same filesystem/network isolation whether in **auto-allow** mode (sandboxed commands run without prompting) or **regular permissions** mode (all Bash commands still prompt even when sandboxed). [DOC S-l6l42j6e]
- By default sandboxed commands can write to the working directory, a per-user temp directory, and any `--add-dir`/`/add-dir`/`permissions.additionalDirectories` paths; `sandbox.filesystem.allowWrite`/`denyWrite`/`allowRead`/`denyRead` extend this, enforced at the OS level for the command and its child processes. [DOC S-l6l42j6e]
- `sandbox.filesystem.disabled: true` turns off filesystem isolation while keeping network isolation (domain allowlisting still applies); it can be set only from user settings, managed settings, or `--settings` — never from a checked-out project's `.claude/settings.json`/`.claude/settings.local.json` — so a CI checkout cannot itself widen this. [DOC S-l6l42j6e]
- `sandbox.failIfUnavailable: true` turns a missing sandbox dependency or unsupported platform into a hard failure instead of the default silent unsandboxed fallback — the documented way to make sandboxing a CI security gate rather than a best-effort default. [DOC S-l6l42j6e]
- `sandbox.credentials.files`/`envVars` entries with `"mode":"deny"` block reads of listed credential files (e.g. `~/.aws/credentials`, `~/.ssh`) and unset listed environment variables (e.g. `GITHUB_TOKEN`, `NPM_TOKEN`) for every sandboxed command; `"mode":"mask"` (v2.1.199+ for env vars) instead substitutes a per-session sentinel value that the sandbox proxy swaps for the real credential only on outbound requests to allowed hosts, keeping tools like `gh`/`npm` working. [DOC S-l6l42j6e]
- `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` strips credentials from every subprocess regardless of sandboxing (`sandbox.credentials` alone affects only sandboxed Bash commands), and forces every command, including shell-mode `!` commands, to run sandboxed. [DOC S-l6l42j6e]
- An LLM gateway lets an organization centralize provider credentials (server-side only), usage/cost tracking per developer, audit logging, and provider switching without touching developer/CI machines, at the cost of the gateway itself becoming infrastructure that must track new Claude Code releases or break the features they add. [DOC S-pilcrlei]
- Setting only `ANTHROPIC_BASE_URL` (no gateway credential) still routes requests through the gateway but does not replace a saved claude.ai subscription login — that login's usage limits and billing still apply; a full swap needs a gateway credential variable or `apiKeyHelper`, after which subscription usage limits no longer apply and billing is per-token to whoever owns the forwarded credential. [DOC S-pilcrlei]
- A gateway that forwards Claude API traffic on to Anthropic must forward the OAuth capability in the `anthropic-beta` header for a subscription-backed session to keep working through it. [DOC S-pilcrlei]
- Anthropic does not endorse, maintain, or audit third-party gateway products and does not support routing Claude Code to non-Claude models through any gateway. [DOC S-pilcrlei]

## Reference

| CI surface | Auth mechanism | Minimum job shape | Cost/limit knobs |
|---|---|---|---|
| GitHub Action (`anthropics/claude-code-action@v1`) | `ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN` / OIDC federation (`anthropic_federation_rule_id`+`anthropic_organization_id`) or `use_bedrock`/`use_vertex`/`use_foundry` OIDC | `prompt` (automation) or trigger-phrase wait (interactive), `claude_args` for CLI flags | `--max-turns` in `claude_args`, workflow `timeout`, GitHub concurrency controls [DOC S1801] |
| GitLab CI/CD job | masked `ANTHROPIC_API_KEY` var, or `id_tokens:`-minted `GITLAB_OIDC_TOKEN` exchanged for Bedrock/Vertex creds | `curl .../install.sh \| bash`, then `claude -p "$AI_FLOW_INPUT" --permission-mode acceptEdits --allowedTools ...` | `--max-turns`, job `timeout:`, concurrency limits [DOC S1802] |
| Local/any-host `claude -p` | `ANTHROPIC_API_KEY` (bare) or provider creds; a gateway credential/`apiKeyHelper` replaces subscription login | `claude -p "<prompt>" --output-format ... --allowedTools ...` | `--max-turns`, `--max-budget-usd`, `--permission-prompts none` [DOC S1800,S1824] |

See `agents/headless-agent-runtimes.md` for how this compares to routines, GitHub Copilot coding agent, GitLab Duo
Agent Platform and `gh-aw`, and for the `claude -p` exit-code/`--output-format` baseline and cost-figure caveats
this article does not repeat (lines 22, 58, 66 of that article).

## Examples

GitLab CI job running `claude -p` on an MR event with a masked API key (fixture project `corp.example.com/PL-SRV-0042`):

```yaml
stages:
  - ai

claude:
  stage: ai
  image: node:24-alpine3.21
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
  before_script:
    - apk add --no-cache git curl bash
    - curl -fsSL https://claude.ai/install.sh | bash
    - export PATH="$HOME/.local/bin:$PATH"
  script:
    - >
      claude -p "${AI_FLOW_INPUT:-'Review this MR and implement the requested changes'}"
      --permission-mode acceptEdits
      --allowedTools "Bash Read Edit Write mcp__gitlab"
      --max-turns 15
      --debug
  variables:
    GIT_STRATEGY: fetch
```

`ANTHROPIC_API_KEY` is added as a masked (and, per `gitlab/variables.md`, optionally protected) CI/CD variable under
**Settings > CI/CD > Variables**, not committed to `.gitlab-ci.yml`. See `gitlab/variables.md` for masked/protected/hidden
variable semantics and `gitlab/pipelines-rules.md` for `rules:`/`$CI_PIPELINE_SOURCE` matching used above.

GitHub Actions workflow running `anthropics/claude-code-action@v1` on a schedule, capped with `--max-turns` and scoped
permissions, against fixture repo `corp.example.com/PL-LT-00123`:

```yaml
name: Daily Report
on:
  schedule:
    - cron: "0 9 * * *"
jobs:
  report:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      issues: read
      id-token: write
    steps:
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          prompt: "Generate a summary of yesterday's commits and open issues"
          claude_args: |
            --model claude-opus-5-5
            --max-turns 10
            --allowedTools "mcp__github__list_commits,mcp__github__list_issues"
```

See also: `agents/headless-agent-runtimes.md` (cross-runtime comparison, `claude -p` exit codes, cost caveats),
`claude/agent-sdk.md` (running `claude -p` as a subprocess vs. the Python/TypeScript SDK), `claude/env-vars.csv`
(`ANTHROPIC_BASE_URL`, `CLAUDE_CODE_USE_BEDROCK`/`_VERTEX`, `MCP_TIMEOUT`), `claude/settings-and-scopes.md`
(`sandbox.*` settings scopes and precedence), `gitlab/variables.md` (masked/protected/hidden CI/CD variables used
above), `gitlab/pipelines-rules.md` (`rules:`, `$CI_PIPELINE_SOURCE`, scheduled-pipeline ownership).
