---
topic: claude/skills-and-subagents
priority: P2
applies_to: "Claude Code docs (code.claude.com), skills/sub-agents/agent-teams, retrieved 2026-09-26"
retrieved_utc: 2026-10-06
sources: [S2158, S2157, S-j22fjuka, S-hvuk3dqt, S-qdxfqzln, S-ezqg74ki, S-bisz7fay]
status: complete
---

# Skills and subagents: frontmatter, locations, and agent teams

## Summary
A skill is a `SKILL.md` file (YAML frontmatter + Markdown body) that Claude loads automatically by `description`
match or that a user invokes with `/name`; a subagent is a `.claude/agents/*.md` file (also frontmatter + Markdown
system prompt) that runs in its own context window and returns a summary to the caller. Both have a strict,
silently-ignored-if-unrecognized frontmatter schema (`claude/skills-and-subagents.csv`), both resolve name clashes
by a fixed location precedence, and both can become teammates in the experimental agent-teams feature, which adds a
shared task list and direct inter-agent messaging on top of ordinary subagent delegation.

## Facts
### Skills
- Skill frontmatter fields use lowercase-hyphenated names except `when_to_use`; a field name that doesn't match the
  table exactly is silently ignored, no error. [DOC S2158]
- `description` + `when_to_use` combined is truncated at 1,536 characters in the skill listing. [DOC S2158]
- `disable-model-invocation: true` also stops the skill from being preloaded into subagents and (as of v2.1.196)
  from running when a scheduled task fires it as its prompt. [DOC S2158]
- `context: fork` runs the skill body in a forked subagent context; `agent` picks which subagent type; `background`
  (default `true`, requires v2.1.218+) controls whether the invoking turn waits for the fork's result. [DOC S2158]
- Boolean skill fields accept `yes/no/on/off/1/0` in any case plus `true/false`; before v2.1.218 only `true/false`
  worked. [DOC S2158]
- Outside Claude Code (claude.ai skill uploads, the Skills API, `package_skill.py`), only six frontmatter fields are
  legal: `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`. Any other field, e.g.
  `argument-hint`, fails packaging/upload with a hard error naming the offending key. [DOC S2158]
- `paths` limits auto-activation to files matching the given globs, using the same syntax as CLAUDE.md
  path-specific rules. [DOC S2158]
- `shell: powershell` requires the PowerShell tool to be enabled; that tool is on by default on Windows without Git
  Bash, on by default with Git Bash for claude.ai/Console accounts, and needs
  `CLAUDE_CODE_USE_POWERSHELL_TOOL=1` on Bedrock, Google Cloud Agent Platform, Microsoft Foundry, macOS, Linux and
  WSL. [DOC S2158]
- Skill locations: Enterprise (`.claude/skills/` in the managed-settings directory), Personal (`~/.claude/skills/`),
  Project (`.claude/skills/`), Nested (`<subdir>/.claude/skills/`), Plugin (`<plugin>/skills/`) and claude.ai
  account sync. When names clash, enterprise beats personal and personal beats project; a project-root skill and a
  nested skill both load; plugin skills load alongside, namespaced as `/plugin-name:skill-name`; a claude.ai-synced
  skill yields its short name to any other skill or command and then runs only under its full name. [DOC S2158]
- A skill and a bundled skill/built-in command sharing a name: the local skill wins but the bundled command's
  *alias* still runs the bundled one (a project `code-review` skill replaces `/code-review`, but `/review` still
  runs the bundled skill). [DOC S2158]
- Reserved skill-folder name: `synced` (any case) — Claude Code uses `~/.claude/skills/synced/` for claude.ai-synced
  skills and skips a same-named skill authored at enterprise/personal/project level. [DOC S2158]
- Reserved namespace: `anthropic-skills` and everything under it (e.g. `anthropic-skills:pdf`) — a skill folder,
  frontmatter `name`, `.claude/commands/` file, or saved workflow using it does not load. [DOC S2158]
- `!`command`` dynamic-context injection lines run before Claude sees the skill content, substituting the command's
  live output (demonstrated with `` !`git diff HEAD` ``); this and other Claude Code-only body features do not
  function in claude.ai chat or via the API. [DOC S2158]
- Claude Code watches skill directories for live edits (add/edit/remove) except in bare mode, picking up changes
  within the running session with no restart; a newly created top-level skills directory needs `/reload-skills`
  because it isn't watched yet. [DOC S2158]

### Subagents
- Subagent frontmatter fields use camelCase (e.g. `maxTurns`, `disallowedTools`) and must match exactly; an
  unrecognized field is silently ignored. Only `name` and `description` are required. [DOC S2157]
- `name` cannot contain `:` (reserved for plugin-scoped ids like `my-plugin:reviewer`); a name containing one fails
  to load and logs an error to the debug log (before v2.1.218 such names were accepted). [DOC S2157]
- If no entry in `tools` resolves to a real tool, the subagent usually fails to launch with a "zero tools" error
  naming the unresolved entries. [DOC S2157]
- `disallowedTools` entries with a specifier such as `Bash(git push *)` still remove the *whole* tool, not just that
  specifier. [DOC S2157]
- `maxTurns`: at the limit Claude Code returns the subagent's output marked partial (partial marking requires
  v2.1.246+) and Claude can resume it. [DOC S2157]
- `skills` preloads full skill content (not just the description) into the subagent's startup context; the subagent
  can still invoke other, unlisted skills via the Skill tool. [DOC S2157]
- `memory: user|project|local` enables persistent cross-session subagent memory at `~/.claude/agent-memory/<name>/`,
  `.claude/agent-memory/<name>/`, or `.claude/agent-memory-local/<name>/` respectively. [DOC S2157]
- `omitClaudeMd: true` skips user/project/local CLAUDE.md at launch (managed policy files still load, except for
  managed subagents); ignored when the agent runs as the main session agent; requires v2.1.271+. [DOC S2157]
- `isolation: worktree` gives the subagent a temporary git worktree branched from the default branch by default (not
  the parent's HEAD; see `worktree.baseRef` below); the worktree auto-cleans up if the subagent made no changes. [DOC S2157]
- `worktree.baseRef` (`"fresh"` default | `"head"`) sets what new worktrees branch from, for `--worktree` and subagent
  worktrees alike: `"fresh"` the repository's default branch on the remote, `"head"` the current local `HEAD`, carrying
  unpushed commits. Inside a worktree `"head"` is that worktree's `HEAD`, not the main checkout's. [DOC S-j22fjuka]
- `worktree.baseRef` takes no branch name; to start from a specific branch, create the worktree with git directly. [DOC S-j22fjuka]
- `worktree.baseRef` was added in v2.1.133 (`fresh` | `head`, covering `--worktree`, `EnterWorktree` and agent-isolation
  worktrees); the same release moved `EnterWorktree`'s base back to `origin/<default>`, where it had been local `HEAD` since 2.1.128. [DOC S-hvuk3dqt]- `experimental.cacheTtl` (`5m` or `1h`) sets prompt-cache TTL for the subagent's own requests; `1h` is ignored while
  the subscription is on usage credits; the field is read only from subagent files; requires v2.1.248+. [DOC S2157]
- For plugin subagents, `hooks`, `mcpServers`, and `permissionMode` are all ignored for security reasons; copy the
  file into `.claude/agents/` or `~/.claude/agents/` to use them, or grant via `permissions.allow` (session-wide).
  [DOC S2157]
- Subagent scope precedence, highest first: Managed settings (1) > `--agents` CLI flag (2, session-only) >
  `.claude/agents/` project (3) > `~/.claude/agents/` personal (4) > plugin `agents/` directory (5, lowest). [DOC
  S2157]
- Project subagents are discovered by walking up from cwd through every `.claude/agents/` to the repo root; when
  nested directories define the same `name`, the definition closest to the working directory wins. Within one
  directory tree (including subfolders), a duplicate `name` loads only one file, by filesystem read order — not
  documented precedence; `/doctor` flags and offers to resolve such duplicates. [DOC S2157]
- Built-in subagents: **Explore** (read-only, model inherits from the main conversation capped at Opus on the Claude
  API; Write/Edit denied), **Plan** (read-only, used in plan mode, same model rule), **general-purpose** (every tool
  available to subagents; model = `CLAUDE_CODE_SUBAGENT_MODEL` if set and nothing else assigns one, else the main
  conversation's model), plus helper agents `claude` (catch-all, no fixed model, also the default background-session
  agent), `statusline-setup` (Sonnet), `claude-code-guide` (Haiku). [DOC S2157]
- A subagent's model comes from the first of these that applies: (1) the `model` parameter Claude passes for that invocation, (2) the definition's `model` frontmatter (`inherit` = the main conversation's model), (3) `CLAUDE_CODE_SUBAGENT_MODEL` set to an alias or model id, (4) the main conversation's model; before v2.1.251 the environment variable came first and overrode the other two, and `inherit` in the variable equals leaving it unset. [DOC S2157]
- The `model` field takes an alias (`sonnet`, `opus`, `haiku`, `fable`), a full model id, or `inherit`. A family alias in the invocation parameter or the frontmatter resolves to the main conversation's exact model when that model belongs to the same family (so a `sonnet` definition in a Sonnet session runs on the session's Sonnet); an alias in `CLAUDE_CODE_SUBAGENT_MODEL` always resolves to the version the alias names. [DOC S2157]
- The `sonnet` alias means the latest Sonnet for the provider (Sonnet 5.5 on the Anthropic API at this reading, Sonnet 4.6 on Claude Platform on AWS, Sonnet 4.5 on Bedrock and Google Cloud's Agent Platform), and aliases move to newer versions as Claude Code releases advance; a full model id pins one version. [DOC S-ezqg74ki]
- `CLAUDE_CODE_SUBAGENT_MODEL` is a default: a definition's `model` or a model Claude passes still wins; adding `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` (v2.1.257+) makes it apply to every subagent, teammate and workflow agent, and set alone it runs them on the main conversation's model. [DOC S2157]
- A per-invocation `model` also holds when the subagent is resumed or sent a follow-up (from v2.1.211; earlier it reverted to the definition's model); subagents inherit the main conversation's extended-thinking setting (from v2.1.198), and `/tasks` names each subagent's model, with its effort when the definition sets one (v2.1.242+). [DOC S2157]
- When an organization's `availableModels` allowlist blocks a subagent's requested model, Claude Code runs it on the newest permitted version of the family for a family alias, and otherwise on the inherited model, with a warning in interactive sessions. [DOC S2157, S-ezqg74ki]
- A definition's `model: sonnet` keeps a subagent on the Sonnet alias only while nothing assigns a model earlier in the order: an orchestrator that passes a `model` for the invocation, or a session that sets `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` with a model, replaces it. [DER S2157: the resolution order above and the FORCE rule]
- A non-fork subagent starts with a fresh, isolated context window: it does not see the parent's conversation history, the skills already invoked or the files already read; Claude writes a delegation message that summarises the task and the subagent works from it. A fork is the exception and inherits the parent conversation. [DOC S2157]
- A non-fork subagent's startup context holds: its own system prompt (its markdown body or `prompt` field, plus appended environment details, not the Claude Code system prompt), the delegation prompt as its task message, every CLAUDE.md level the main conversation loads (including `AGENTS.md` files loaded as project instructions), a repository status snapshot, the full content of skills named in its `skills` field, and (v2.1.206+) a roster of named sibling agents when its tools include `SendMessage`. Explore and Plan skip CLAUDE.md and the status snapshot. [DOC S2157]
- The context-window page says the subagent also has the same MCP servers and skills as the parent (minus a few tools such as plan-mode controls and, by default, `Agent`), and that the main session's auto memory is not included; a custom agent with `memory:` loads its own separate MEMORY.md instead. [DOC S-bisz7fay]
- The docs' guidance on rules: the main conversation still holds the full CLAUDE.md when it reads a subagent's result, so most rules need not reach the subagent, but a rule that must, such as ignoring a directory, is restated in the delegation prompt. `omitClaudeMd: true` suits subagents that take everything from the delegation prompt. [DOC S2157]
- A fork (fork mode is on by default in interactive sessions) sees the same system prompt, tools, model and message history as the main session; a non-fork subagent has a fresh context plus the prompt passed to it, and pays start-up time to gather context, which is the docs' stated reason to prefer a fork when latency matters or phases share context. [DOC S2157]
- Only the subagent's final text comes back to the parent, plus a small metadata trailer with token counts and duration; the walkthrough's example has 6,100 tokens of file reads stay in the subagent and a 420-token result return. [DOC S-bisz7fay]
- `CLAUDE_CODE_DISABLE_EXPLORE_PLAN_AGENTS=1` removes only Explore/Plan (Claude reads/explores directly instead);
  `CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS=1` removes all built-in types in non-interactive mode/Agent SDK sessions.
  [DOC S2157]
- `--agents` CLI JSON: top-level keys are agent names; each value takes `prompt` (system prompt, may be empty) plus
  the frontmatter fields `description, tools, disallowedTools, model, permissionMode, mcpServers, hooks, maxTurns,
  skills, initialPrompt, memory, effort, background, omitClaudeMd, isolation`; `color` and `experimental` are
  accepted-but-ignored. The path-to-JSON-file form (non-interactive only) requires v2.1.281+. [DOC S2157]
- A subagent's file is watched for live edits (few seconds to apply, no restart) except: the first agent file in a
  brand-new `agents` directory (needs restart), agents under `--add-dir` (not watched, needs restart), and sessions
  started with `--disable-slash-commands` (no watching at all). [DOC S2157]

### Agent teams (experimental)
- Disabled by default; enabled only by setting `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` (env or `settings.json`).
  Without it, no team directories are written and Claude never proposes or spawns teammates. [DOC S-qdxfqzln]
- Once enabled, ordinary delegation changes too: any `Agent` tool call that supplies a `name` (not a fork, not one
  passing its own `isolation`) launches as a teammate, so a team can form even when the user only asked for a
  subagent. [DOC S-qdxfqzln]
- Teammates message each other directly and self-coordinate via a shared task list (pending/in-progress/completed,
  with dependencies) using file locking to avoid claim races; agents without the Task tools coordinate via messages
  only. Subagents, by contrast, return a result to the caller (subagents Claude named at spawn can also message
  each other), and the main agent manages all work. [DOC S-qdxfqzln]
- Team storage is session-derived, named `session-<first 8 chars of session id>`: team config at
  `~/.claude/teams/{team-name}/config.json` (removed when the session ends) and task list at
  `~/.claude/tasks/{team-name}/` (persists locally, never uploaded, survives resume; retention follows
  `cleanupPeriodDays`). Each agent's mailbox is `~/.claude/teams/{team-name}/inboxes/{agent-name}.json`. [DOC
  S-qdxfqzln]
- A subagent definition (project/user/managed scope) can be reused as a teammate role: Claude Code applies its
  `tools` (adding `SendMessage` for in-process teammates, plus `TaskCreate/Get/List/Update` in sessions with Task
  tools), its `model` (if the spawn prompt names none), and its body (appended as extra instructions for in-process
  teammates, or used in place of the default prompt for split-pane teammates). The definition's `skills` are NOT
  applied in either display mode (teammates load skills from project/user settings); its `mcpServers` apply only to
  split-pane teammates, while in-process teammates ignore them and load MCP servers from project/user settings.
  [DOC S-qdxfqzln]
- Teammates start in the lead's permission mode except `dontAsk`, which they never inherit; if the lead runs
  `--dangerously-skip-permissions`, all teammates do too. Teammate permission prompts surface in the lead session.
  [DOC S-qdxfqzln]
- A message relayed between agents (via `SendMessage`) is always tagged to the recipient as coming from another
  Claude session, never from the human; a teammate cannot grant permission consent on the user's behalf, and a
  denied action cannot be laundered through another teammate. [DOC S-qdxfqzln]
- Teammate model choice order: (1) the model the spawn prompt names for that teammate, (2) for a
  subagent-definition-based teammate, that definition's `model` (`inherit` = lead's model), (3)
  `CLAUDE_CODE_SUBAGENT_MODEL` if not `inherit`, (4) the lead's current model;
  `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` skips sources 1-2 entirely (requires v2.1.257+). [DOC S-qdxfqzln]
- Teammates inherit the lead's effort level (split-pane teammates only from v2.1.186+). Display modes:
  `in-process` (default), `auto`, `tmux`, `iterm2`, set via `teammateMode` in settings or `--teammate-mode`
  (experimental, undocumented in `--help`). [DOC S-qdxfqzln]
- `TeammateIdle`, `TaskCreated`, `TaskCompleted` hooks let a project enforce quality gates on team activity; exiting
  2 sends feedback and blocks the transition (idle continuation, task creation, or task completion respectively).
  [DOC S-qdxfqzln]

## Reference
See `claude/skills-and-subagents.csv` for the full SKILL.md and agent `.md` frontmatter field table (type/values,
default, effect, source).

Related kb articles:
- `claude/hooks.md` — the hook events referenced above (`SubagentStart`/`SubagentStop`, `Elicitation`, and the
  `hooks` frontmatter field's event/matcher shape).
- `claude/permissions-mcp.md`, `claude/managed-mcp.md` — permission-mode and MCP-server config referenced by
  `permissionMode` and `mcpServers` above.
- `agents/instruction-and-context-limits.md` — cross-product instruction/description length limits; this article's
  1,536-character skill-listing truncation (`description` + `when_to_use`) is the Claude Code data point in that
  survey.
- `agents/agent-cost-governance.md` — per-teammate/per-subagent cost is a separate Claude Code instance's spend;
  see that article for how a team's or subagent fleet's token cost is measured and attributed.
- `claude/plugins.md` — a plugin's `skills/` and `agents/` directories add the plugin-name prefix (`<plugin>:<name>`)
  to the frontmatter this article describes; `claude/plugins.csv` has the manifest's `skills`/`agents`/`commands`
  fields.
- `claude/cross-session-messaging.md` — `SendMessage` and `ListAgents` beyond one session: messaging your other
  Claude Code sessions on this machine, other machines and the cloud, with its inbound controls.

## Examples
- SNIPPET: a `SKILL.md` frontmatter that forks the skill body into a subagent and never auto-invokes from a model match; context: Claude Code, `.claude/skills/<name>/SKILL.md`; checked: no [DOC S2158: `context: fork` and `disable-model-invocation: true` frontmatter fields]
```yaml
# .claude/skills/deploy/SKILL.md (frontmatter delimiters omitted here to keep this fact block parseable)
name: deploy
description: Deploy the application to production
context: fork
disable-model-invocation: true
# --- end frontmatter ---
# Deploy the application:
# 1. Run the test suite
# 2. Build the application
# 3. Push to the deployment target
```

- SNIPPET: a subagent definition restricted to read-only tools with a fixed model; context: Claude Code, `.claude/agents/<name>.md`; checked: no [DOC S2157: subagent frontmatter fields `name`/`description`/`tools`/`model`, camelCase schema]
```markdown
<!-- .claude/agents/code-reviewer.md (frontmatter delimiters omitted here to keep this fact block parseable) -->
name: code-reviewer
description: Reviews code for quality and best practices
tools: Read, Glob, Grep
model: sonnet
# === end frontmatter ===
# You are a code reviewer. When invoked, analyze the code and provide
# specific, actionable feedback on quality, security, and best practices.
```

- SNIPPET: a session-only subagent defined inline on the CLI, restricted to read/grep/glob/bash tools with a fixed model; context: Claude Code, `claude --agents` flag; checked: no [DOC S2157: `--agents` CLI JSON top-level keys are agent names, each taking `description`/`prompt`/`tools`/`model`]
```bash
# CLI-defined subagent for one session, for example PL-LT-00123's local automation
claude --agents '{
  "code-reviewer": {
    "description": "Expert code reviewer. Use proactively after code changes.",
    "prompt": "You are a senior code reviewer.",
    "tools": ["Read", "Grep", "Glob", "Bash"],
    "model": "sonnet"
  }
}'
```
