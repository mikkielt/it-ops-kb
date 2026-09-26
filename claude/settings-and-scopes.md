---
topic: claude/settings-and-scopes
priority: P2
applies_to: "Claude Code docs (retrieved 2026-09-26)"
retrieved_utc: 2026-09-26
sources: [S2057, S-wzatkg4o, S2042, S-22qwtmf7, S-zcuxapgb, S1863, S-rfpmkpck, S-vilbjgtf, S-lreom5ko, S-inpjf36q, S-a2zimsvk]
status: complete
files: [claude/settings-keys.csv, claude/env-vars.csv]
---

# Settings files, scopes and precedence

## Summary
Claude Code reads settings from four JSON files (user, shared project, project local, plus managed) with fixed
precedence: managed > CLI `--settings` > project local > shared project > user. Managed settings are delivered
server-side from the claude.ai console or on-device via `managed-settings.json`, MDM/plist, or Windows registry
(`HKLM\SOFTWARE\Policies\ClaudeCode`); a handful of keys are managed-only. Permission modes (`default`/`acceptEdits`/
`plan`/`auto`/`dontAsk`/`bypassPermissions`) layer on top of permission rules. CLAUDE.md/AGENTS.md give Claude
persistent instructions (guidance, not enforcement); the `.claude` directory holds settings, hooks, skills, agents,
and rules. Environment variables control provider routing, proxy/CA/mTLS, telemetry, and auth, with their own
precedence against settings-file `env` values.

## Facts
### Settings files and precedence
- Four settings files plus managed sources, in override order highest first: managed settings (`managed-settings.json`, MDM, or claude.ai console) > `claude --settings` (CLI) > project local `.claude/settings.local.json` > shared project `.claude/settings.json` > user `~/.claude/settings.json`. [DOC S2057]
- Managed settings apply above every other level; nothing set by a user, project, local file, or `--settings` overrides them, apart from a short list of security-sensitive exceptions. [DOC S2057]
- `.claude/settings.local.json` is written by Claude Code itself when a user picks "Yes, and don't ask again" on a Bash permission prompt, saved as an `allow` rule; it is added to the global git excludes file (`core.excludesFile`, else `$XDG_CONFIG_HOME/git/ignore` or `~/.config/git/ignore`) the first time Claude Code writes it in an unignoring repo. [DOC S2057]
- In a git repository, Claude Code keeps `.claude/settings.local.json` at the repository root (main checkout root in a worktree), not the starting subdirectory, since v2.1.211; paths in the file still anchor at the session's primary working directory when they start with `/`. [DOC S2057]
- Local-file `allow` rules apply without the workspace-trust step required for the committed `.claude/settings.json`, as long as the local file stays untracked by git. [DOC S2057]
- Array settings (e.g. `permissions.allow`, `hooks`) combine across all applicable scopes; scalar settings (e.g. `model`) use the most specific value that sets them. [DOC S2057]
- `~/.claude.json` is a fifth file Claude Code writes for itself: sign-in session, MCP server configs, per-project trust state, and the small set of global config keys `/config` writes. Not for manual editing. [DOC S2057][DOC S-rfpmkpck]
- On Windows, `~/.claude` means `%USERPROFILE%\.claude`; `CLAUDE_CONFIG_DIR` relocates it. [DOC S2057]
- `/status` shows the `Setting sources` line naming which managed source is active for the current machine. [DOC S2057]

### Managed settings delivery
- File-based managed settings paths: macOS `/Library/Application Support/ClaudeCode/managed-settings.json`; Linux/WSL `/etc/claude-code/managed-settings.json`; Windows `C:\Program Files\ClaudeCode\managed-settings.json` (the legacy `C:\ProgramData\ClaudeCode\managed-settings.json` path is not read). [DOC S2042]
- An optional `managed-settings.d/` directory next to `managed-settings.json` lets teams split policy into multiple files; Claude Code merges `managed-settings.json` first, then every `*.json` in the directory alphabetically (use numeric prefixes like `10-telemetry.json` to control order); hidden and non-`.json` files are ignored. [DOC S2042]
- macOS delivery: the `com.anthropic.claudecode` managed-preferences domain (configuration profile), same top-level keys as the JSON file, nested settings as dictionaries, lists as plist arrays. [DOC S2042]
- Windows delivery: a `REG_SZ`/`REG_EXPAND_SZ` value named `Settings` under `HKLM\SOFTWARE\Policies\ClaudeCode`; a user-writable HKCU variant of the same key/value exists under `HKCU\SOFTWARE\Policies\ClaudeCode` and applies only when no higher admin source supplies a given policy key. [DOC S2042]
- MDM/OS-level policy is checked for changes every 30 minutes; a file-based `managed-settings.json` is reloaded when the file changes; server-managed settings are fetched at startup and polled hourly. [DOC S2042]
- Precedence order when more than one managed source is present, highest first: (1) server-managed/remote settings — only fetched when the session authenticates directly to Anthropic's API with an eligible credential or via a gateway `/login`; (2) MDM/OS-level policy; (3) `managed-settings.json` + `managed-settings.d/*.json` merged; (4) HKCU registry (Windows/WSL, and only when no admin source above sets the key). [DOC S2042]
- `managedSourcesBehavior` (managed-only, read from the highest-ranked source carrying it or a policy key) controls combination: `"first-wins"` (default) uses only the first source with a policy key; `"merge"` (requires v2.1.242+) combines every admin source, lists union, locks take the strictest value, restriction allowlists take the highest-ranked source's list whole. [DOC S2042]
- Cross-source keys (read from every admin source regardless of `managedSourcesBehavior`) include: `sandbox.network.allowManagedDomainsOnly`, `sandbox.filesystem.allowManagedReadPathsOnly`, `allowAllClaudeAiMcps`, `allowManagedMcpServersOnly`, `deniedMcpServers`, `disableClaudeAiConnectors`, `sandbox.bwrapPath`/`sandbox.socatPath`/`sandbox.ripgrep`, `sandbox.filesystem.disabled`, `sandbox.network.strictAllowlist`, `useAutoModeDuringPlan`, `syncClaudeAiSkills`, `syncClaudeAiPlugins`, `enableArtifact`, `maxEffortLevel` (lowest cap wins), commit-trailer opt-outs, `forceRemoteSettingsRefresh`, and per-variable `env` (v2.1.223+). [DOC S2042]
- `forceRemoteSettingsRefresh: true` blocks session startup until server-managed settings are freshly fetched and exits the client if the fetch fails; it can also be set via MDM/file-based managed settings to enforce fail-closed behavior before any server payload arrives. [DOC S-22qwtmf7]
- The cached server-managed `env` block withholds several categories until a fetch confirms the payload for the session: proxy/TLS config (`HTTPS_PROXY`, `NODE_EXTRA_CA_CERTS`, `CLAUDE_CODE_CLIENT_CERT`/`CLAUDE_CODE_CLIENT_KEY`), provider routing (`ANTHROPIC_BASE_URL`, `CLAUDE_CODE_USE_BEDROCK`/`CLAUDE_CODE_USE_VERTEX`, provider endpoint URLs), auth credentials (`ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`), `CLAUDE_CONFIG_DIR`, and (v2.1.223+) WIF and profile/config-dir selector variables plus OS directory variables (`HOME`, `XDG_CONFIG_HOME`, `APPDATA`, `USERPROFILE`); an endpoint-managed (MDM/file) value for the same variable still fills in and reaches the settings fetch itself. [DOC S-22qwtmf7]
- Certain settings require an interactive security-approval dialog before Claude Code applies them from a managed source: shell-command settings (`apiKeyHelper`, `statusLine`, `otelHeadersHelper`), sandbox binary settings (`sandbox.bwrapPath`, `sandbox.socatPath`, `sandbox.ripgrep`), sandbox network/isolation settings weakening isolation, custom `env` variables that set credentials/routing/base URLs, and any hook definition; a managed `claudeMd` value does NOT require approval (instruction text, not an executed command). [DOC S-22qwtmf7]
- Approval is remembered per organization (claude.ai login) or per gateway (Claude apps gateway), keyed to the credential used, and re-prompts when the approval-requiring settings change or after `/logout`. [DOC S-22qwtmf7]
- Server-managed settings require a Claude for Teams or Enterprise plan, the Owner or Primary Owner role to edit, and network access to `api.anthropic.com`; configured at Admin Settings > Claude Code > Managed settings in the claude.ai console. [DOC S-22qwtmf7]
- Server-managed settings cannot deliver a `managed-mcp.json` (deliver `allowedMcpServers`/`deniedMcpServers` or, on v2.1.259+, `managedMcpServers` for http/sse servers instead), nor OS-level-only keys like `policyHelper` and `wslInheritsWindowsSettings`. [DOC S-22qwtmf7]
- `claude doctor`'s `Managed settings (remote)` line (v2.1.248+) reports one of: settings loaded, no server-managed settings configured, fetch failed (with cause and whether a cached policy applies), or fetch skipped (with reason). [DOC S-22qwtmf7]

### Permission modes
- Six modes: `default` (Manual: reads only), `acceptEdits` (reads + file edits + common filesystem Bash commands like `mkdir`/`touch`/`rm`/`mv`/`cp`/`sed`, and PowerShell `Set-Content`/`Add-Content`/`Clear-Content`/`Remove-Item` when that tool is enabled), `plan` (reads, plus classifier-approved commands when auto mode is available), `auto` (everything, background safety checks via a second-model classifier), `dontAsk` (reads + pre-approved tools only; anything else is denied, not prompted), `bypassPermissions` (everything, isolated containers/VMs only). [DOC S-zcuxapgb]
- The CLI accepts `manual` as an alias for `default` (v2.1.200+); the mode is labeled "Manual" everywhere. [DOC S-zcuxapgb]
- With v2.1.283+, `auto` is the built-in starting mode for interactive terminal and VS Code sessions; on earlier versions it's the built-in start only on Pro/Max/Team plans in sessions that fetch feature flags. `claude -p` and Agent SDK sessions always start in `default`. [DOC S-zcuxapgb]
- Starting mode precedence: `--permission-mode` flag (or `--dangerously-skip-permissions`) > `permissions.defaultMode` in a settings file > built-in default. Setting `"auto"` or `"bypassPermissions"` in `.claude/settings.json` or `.claude/settings.local.json` does not take effect for the starting mode (falls back further); the other mode values apply from any settings file. [DOC S-zcuxapgb]
- Writes to protected paths, and `rm`/`rmdir` on critical paths, are never auto-approved except in `bypassPermissions` mode (and plan-mode sessions with bypass available); deny rules and ask rules block/require approval in every mode including `bypassPermissions`. [DOC S-zcuxapgb]
- No mode auto-approves: explicit ask-rule matches, organization connector tools set to `ask`, tools requiring user interaction (`AskUserQuestion`, MCP tools marked `requiresUserInteraction`), critical-path `rm`/`rmdir`, cross-session messaging safeguards, and (with `permissions.blockReadsOutsideWorkingDirectories` on, v2.1.257+) reads outside working directories. [DOC S-zcuxapgb]
- `claude --permission-mode dontAsk --allowedTools "Bash(npm test)" "Read"` is the documented pattern for locked-down CI; cloud sessions ignore `dontAsk` from settings files. [DOC S-zcuxapgb]
- `claude -p "<prompt>" --dangerously-skip-permissions` fully unattended requires a container/VM/sandbox runtime and, on Linux/macOS, a non-root user; cloud sessions ignore this mode from settings files. [DOC S-zcuxapgb]
- `Shift+Tab` cycles CLI permission modes: `default → acceptEdits → plan → default`, with `bypassPermissions` and `auto` slotting in after `plan` when enabled/available. [DOC S-zcuxapgb]

### CLAUDE.md, AGENTS.md and memory
- CLAUDE.md scopes, in load order broadest to most specific: managed policy file (`/Library/Application Support/ClaudeCode/CLAUDE.md`, `/etc/claude-code/CLAUDE.md`, `C:\Program Files\ClaudeCode\CLAUDE.md`) → user `~/.claude/CLAUDE.md` → project `./CLAUDE.md` or `./.claude/CLAUDE.md` → local `./CLAUDE.local.md`. [DOC S1863]
- All discovered CLAUDE.md/CLAUDE.local.md files are concatenated into context (not merged/overridden); ordered root-to-working-directory, with each directory's `CLAUDE.local.md` appended after its `CLAUDE.md`. Subdirectory files load on demand when Claude reads files there. [DOC S1863]
- `@path` imports (relative or absolute, max depth 4) expand into context at launch; an import outside the working directory in a project-level file is "external" and needs a one-time approval dialog (user-scope files like `~/.claude/CLAUDE.md` are trusted without it, except in Cowork desktop sessions). [DOC S1863]
- Target under 200 lines per CLAUDE.md file; use path-scoped `.claude/rules/*.md` (YAML frontmatter `paths:` glob list, budget 1,000 expanded patterns / 4 MiB) to load instructions only for matching files. [DOC S1863]
- Managed `claudeMd` key can embed CLAUDE.md content directly in `managed-settings.json`/server-managed settings instead of a separate file; honored only from managed/policy settings, loads before user and project CLAUDE.md, and cannot be excluded by `claudeMdExcludes`. [DOC S1863]
- `claudeMdExcludes` (any settings layer, arrays merge across layers) skips ancestor CLAUDE.md/rules files by absolute-path glob in large monorepos; cannot exclude the managed policy file. [DOC S1863]
- AGENTS.md is read only when the working directory and its ancestors have no `CLAUDE.md`/`CLAUDE.local.md`; requires Claude Code v2.1.277+ to read directly, otherwise import it from a CLAUDE.md with `@AGENTS.md`. [DOC S1863]
- Settings vs. CLAUDE.md split for enforcement: block tools/paths → `permissions.deny`; sandbox isolation → `sandbox.enabled`; env/provider routing → `env`; login/org restriction → `forceLoginMethod`/`forceLoginOrgUUID`; behavioral/style guidance → CLAUDE.md (guidance only, not enforced). [DOC S1863]

### The .claude directory
- Project root: `CLAUDE.md`, `.mcp.json` (team-shared MCP servers), `.worktreeinclude` (gitignore-syntax list of untracked files to copy into new git worktrees). [DOC S-rfpmkpck]
- `.claude/settings.json` (committed) and `.claude/settings.local.json` (gitignored) hold `permissions`, `hooks`, `statusLine`, `model`, `env`, `outputStyle`. [DOC S-rfpmkpck]
- `.claude/rules/` — topic-scoped instructions, optionally `paths:`-gated; `.claude/skills/<name>/SKILL.md` — invocable `/name` prompts with bundled files; `.claude/commands/<name>.md` — legacy single-file `/name` prompts (skills preferred for new work; a same-named skill wins over a command); `.claude/output-styles/` — project-shared output styles; `.claude/agents/<name>.md` — subagents with their own context window, `tools:` frontmatter restricts access; `.claude/workflows/*.js` — dynamic workflow scripts, each becomes a `/<name>` command, saved via `/workflows`; `.claude/agent-memory/<agent>/MEMORY.md` — per-subagent persistent memory (only for subagents with `memory:` frontmatter; `memory: local` → `.claude/agent-memory-local/`, `memory: user` → `~/.claude/agent-memory/`). [DOC S-rfpmkpck]
- User home: `~/.claude.json` (app state: OAuth session, per-project trust, personal MCP servers, `/config` UI toggles); `~/.claude/CLAUDE.md`; `~/.claude/settings.json`; `~/.claude/keybindings.json`; `~/.claude/rules/` (applies to every project, loaded before project rules). [DOC S-rfpmkpck]

## Reference
See `claude/settings-keys.csv` for the settings.json key table (key, type, scope incl. managed-only, default, effect)
and `claude/env-vars.csv` for the enterprise-relevant environment variables (provider selection, proxy/CA/mTLS,
telemetry/traffic, auth, limits).

| Precedence tier (highest first) | Source |
|---|---|
| 1 | Managed settings (server-managed, MDM/OS policy, `managed-settings.json`+`.d/`, HKCU) |
| 2 | `claude --settings <file>` (CLI) |
| 3 | `.claude/settings.local.json` (project local) |
| 4 | `.claude/settings.json` (shared project) |
| 5 | `~/.claude/settings.json` (user) |

Related: `claude/managed-mcp.md` — `managed-mcp.json`, `allowedMcpServers`/`deniedMcpServers`, `allowManagedMcpServersOnly`
(this article's Facts summarize only how those keys fit into the managed-settings precedence and cross-source rules;
see that article for MCP server matching and evaluation order). `claude/permissions-mcp.md` — permission rule
evaluation order, globs, `allowManagedPermissionRulesOnly` (this article covers the surrounding settings-file and
precedence system those rules live in). `claude/hooks.md` — hook event types and payloads (this article covers
`allowManagedHooksOnly`/`disableAllHooks` and the security-approval dialog for managed hook delivery).

Back-links added to `claude/managed-mcp.md` and `claude/permissions-mcp.md` Reference sections.
`claude/enterprise-admin.md` — console-level org administration (SSO, SCIM, roles, domain capture, Compliance API,
usage analytics) at the claude.ai admin-console layer, a separate control plane from this article's file/MDM-based
managed-settings delivery.
`claude/agent-sdk.md` — `ClaudeAgentOptions.setting_sources`/`Options.settingSources` controls which of these
filesystem settings sources (user/project/local) an embedded Agent SDK session loads; endpoint-managed policy and
server-managed settings load regardless of that option, same as for the CLI.

## Examples
Minimal organization `managed-settings.json` enforcing a deny list and locking permission rules to managed settings:
```json
{
  "permissions": {
    "deny": ["Read(./.env)", "Read(./secrets/**)"],
    "disableBypassPermissionsMode": "disable"
  },
  "allowManagedPermissionRulesOnly": true
}
```

Team `.claude/settings.json` sharing permissions and a default model, committed to git:
```json
{
  "permissions": { "allow": ["Bash(npm test *)", "Bash(npm run *)"] },
  "model": "claude-sonnet-5",
  "env": { "BASH_DEFAULT_TIMEOUT_MS": "300000" }
}
```

Personal override in `.claude/settings.local.json` (gitignored) for one project, e.g. tenant `00000000-0000-0000-0000-000000000000`:
```json
{
  "model": "claude-opus-5-5",
  "permissions": { "allow": ["Bash(docker *)"] }
}
```

Route through Amazon Bedrock with a corporate proxy and custom CA, set in `~/.claude/settings.json`:
```json
{
  "env": {
    "CLAUDE_CODE_USE_BEDROCK": "1",
    "HTTPS_PROXY": "https://proxy.corp.example.com:8080",
    "NODE_EXTRA_CA_CERTS": "/etc/ssl/certs/corp-ca.pem"
  }
}
```

Lock a workstation to Manual mode and CI to a strict allowlist:
```bash
# Interactive workstation default (in ~/.claude/settings.json): {"permissions":{"defaultMode":"default"}}
claude -p "run the test suite" --permission-mode dontAsk --allowedTools "Bash(npm test)" "Read"
```
