---
topic: claude/plugins
priority: P2
applies_to: "Claude Code 2.1.281 docs (retrieved 2026-09-26)"
retrieved_utc: 2026-09-26
sources: [S-n5myb3fn, S-3peuisvr, S-3xyywfcr, S-4m2kbuls, S-havfntgx, S-toe7z3kj, S-rp4dtt4w, S-gxuoqjzy, S-r3nam2zs, S-pelzabjq, S-i7if5i7z, S-lkcsn2fs]
status: complete
files: [claude/plugins.csv]
---
# Plugins: layout, manifest, marketplaces, install, evals

## Summary
A plugin is a directory of components (skills, agents, hooks, MCP/LSP servers, ...) that Claude Code installs and
loads as one unit, most often fetched from a marketplace [DOC S-n5myb3fn], plus an optional manifest at
`.claude-plugin/plugin.json`; only `plugin.json` goes inside `.claude-plugin/`, every other component directory sits
at the plugin root. A marketplace is a `.claude-plugin/marketplace.json` catalog naming plugins and their fetch
`source`; users add a marketplace once, then `claude plugin install <name>@<marketplace>`. Plugin MCP tools are
named `mcp__plugin_<plugin>_<server>__<tool>`. `claude plugin validate` checks a manifest/marketplace before
install; `claude plugin eval` runs prompt+grader test cases with and without the plugin loaded to score what it
contributes. See `claude/skills-and-subagents.md` for skill/agent frontmatter, `claude/managed-mcp.md` for MCP
allow/deny controls, and `claude/hooks.md` for hook event/field semantics that a plugin's `hooks/hooks.json` uses.

## Facts

### Plugin layout and manifest
- Only `.claude-plugin/plugin.json` goes inside `.claude-plugin/`; `skills/`, `commands/`, `agents/`, `hooks/hooks.json`, `.mcp.json`, `.lsp.json`, `bin/`, `settings.json` all sit at the plugin root, not inside `.claude-plugin/`. [DOC S-3peuisvr, S-3xyywfcr]
- The manifest is optional: without it, Claude Code loads components from the standard layout and names the plugin from the marketplace entry or, for `--plugin-dir`, from the directory name. [DOC S-3xyywfcr]
- `plugin.json` fields: `name` (required, kebab-case, no spaces/`@`/`:`/path separators; namespaces every component, e.g. agent `reviewer` in `deploy-tools` is `deploy-tools:reviewer`), `displayName`, `version` (not semver-checked; pins the plugin until changed), `description`, `author` (`name` required, `email`/`url` optional), `homepage` (must parse as a URL), `repository`, `license` (SPDX id), `keywords`, `metadata` (free-form, ignored by Claude Code, requires v2.1.222+), `defaultEnabled` (default `true`), `dependencies`, `settings` (only `agent` and `subagentStatusLine` take effect), `userConfig`, `channels`, `skills`/`commands`/`agents`/`hooks`/`mcpServers`/`lspServers`/`outputStyles`/`workflows`, `experimental` (`themes`, `monitors`, `evals`). [DOC S-3xyywfcr]
- `skills` in the manifest *adds* to the default `skills/` scan; `commands`, `agents`, `hooks`(merges with `hooks/hooks.json`), `mcpServers`(merges with `.mcp.json`) and `outputStyles`/`workflows`/`experimental.themes` *replace* their default directory scan. [DOC S-3xyywfcr, S-3peuisvr]
- An unrecognized top-level manifest key is stripped (plugin still loads, `validate` warns); an unknown key inside a `userConfig` option, `channels` entry, `lspServers` config or `monitors` entry is a hard error and the plugin does not load. [DOC S-3xyywfcr]
- `claude plugin validate <path>` reports `Validation passed`, `Validation passed with warnings` (unknown top-level field, non-kebab-case `name`, missing `version`/`description`/`author`), or `Validation failed` (type mismatch, path missing/escapes plugin root, unknown strict-object key); `--strict` turns warnings into failures. [DOC S-3xyywfcr]
- `mcpServers` accepts a `.json` file path, an `.mcpb`/`.dxt` bundle path or URL (extracted/downloaded into `.mcpb-cache/`), or an inline map; `.mcp.json` at the plugin root loads first, then declared shapes in order, and a server name declared later replaces an earlier one. [DOC S-3xyywfcr]
- `lspServers` config fields: `command` and `extensionToLanguage` (required); optional `args`, `transport` (`stdio` default or `socket`, though every server actually runs over stdio), `env`, `initializationOptions`, `settings`, `workspaceFolder`, `startupTimeout`/`shutdownTimeout` (ms), `restartOnCrash` (default `true`), `maxRestarts`, `diagnostics` (default `true`). [DOC S-3xyywfcr]
- `experimental.monitors` (default `monitors/monitors.json`) entries: `name`, `command`, `description` required; `when: "always"` (default, starts at session start/reload) or `"on-skill-invoke:<skill>"`. Monitors run only in interactive sessions, not on Bedrock, Google Cloud Agent Platform, or Microsoft Foundry. [DOC S-3xyywfcr]
- `commands` manifest entries set exactly one of `source` or `content` (both or neither fails validation); optional `description`, `argumentHint`, `model`, `allowedTools`. [DOC S-3xyywfcr]
- `claude plugin init <name> [--with skills|agents|hooks|mcp|lsp|output-style|channel] [--description] [--author] [--author-email] [-f/--force]` scaffolds `~/.claude/skills/<name>/`, requires Claude Code v2.1.157+; it loads next session as `<name>@skills-dir` with no install step. [DOC S-3peuisvr, S-gxuoqjzy]
- `claude plugin validate ./my-plugin` and `claude --plugin-dir ./my-plugin` (repeatable to load several; can point at a `.zip`) are the create/test loop; loading a folder of plugins (no `.claude-plugin/` at the top level) requires v2.1.265+. [DOC S-3peuisvr]
- `--plugin-url <https-zip-url>` fetches a plugin archive at startup for one session; `CLAUDE_CODE_PLUGIN_DIRS` (v2.1.280+) lists absolute plugin-dir paths for a session where flags can't be passed; project/local settings can't set that variable. [DOC S-3peuisvr]
- Symlinks in a plugin: within the plugin's own directory, preserved as relative symlinks in the cache; elsewhere in the same marketplace, dereferenced and copied; outside the marketplace, skipped. A local-path or `command`-source (copy mode) install preserves only symlinks resolving inside the plugin's own directory. [DOC S-pelzabjq]
- A rejected component path (points outside the plugin root, a symlink leading outside it, or on macOS/Linux any backslash after `./`) surfaces as `path escapes plugin directory`, and the plugin loads without that component. [DOC S-toe7z3kj]

### Marketplace.json fields and reserved names
- `marketplace.json` lives at `.claude-plugin/marketplace.json`; the marketplace root is the directory containing `.claude-plugin/`, and every relative plugin `source` resolves from that root, not from inside `.claude-plugin/`. [DOC S-4m2kbuls, S-r3nam2zs]
- Top-level fields: `name` (required, no spaces/control/bidi chars, no `/`/`\`/`..`/`.`), `owner` (required, `name` required inside), `plugins` (required array; each entry validated independently so one bad entry doesn't fail the marketplace), `$schema`, `description`, `version`, `metadata.description`/`metadata.version`, `metadata.pluginRoot` (bare-name resolution base, v2.1.239+), `forceRemoveDeletedPlugins` (bool), `allowCrossMarketplaceDependenciesOn` (array), `renames` (former name -> current name or `null`, v2.1.193+). [DOC S-4m2kbuls]
- Reserved marketplace names (usable only from a `github`/`git` source under `github.com/anthropics/`): official (`claude-code-marketplace`, `claude-code-plugins`, `claude-plugins-official`, `anthropic-marketplace`, `anthropic-plugins`, `agent-skills`, `anthropic-agent-skills`, `life-sciences`, `knowledge-work-plugins`, `claude-for-legal`, `claude-for-financial-services`, `financial-services-plugins`, `first-party-plugins`, `claude-tag-plugins`); community (`claude-community`, `claude-plugins-community`, `healthcare`); directory names (`anthropic-plugin-directory`, `claude-plugin-directory`); `npm`/`pip`/`uv`/`cargo`/`github`/`gh` in any casing (v2.1.275+); names starting with `claudeai-`. [DOC S-4m2kbuls]
- Names Claude Code reserves for non-marketplace origins: `inline` (`--plugin-dir`/`--plugin-url`), `builtin`, `skills-dir` (`.claude/skills/` auto-load), `synced` (claude.ai account); also `claude-plugin-test`. [DOC S-4m2kbuls]
- Plugin entry fields: `name`, `source` (required); `description`, `version` (plugin.json's own `version` wins if both set, `validate` warns of the mismatch), `category`, `tags`, `strict` (default `true`), `relevance`, `dependencies`, `defaultEnabled` (default `true`, entry wins over plugin.json), `displayName`, `metadata` (v2.1.222+), `headers`, `headersHelper` (needs `"strict": false`, v2.1.238+). [DOC S-4m2kbuls]
- Strict mode: with `plugin.json` present and `strict: true` (default), Claude Code appends the entry's component fields (`commands`,`agents`,`skills`,`hooks`,`outputStyles`,`themes`) to the manifest, except `hooks` matchers which replace per event; with `strict: false` and any entry component field set, the plugin fails to load with a conflicting-manifests error. [DOC S-4m2kbuls]
- Plugin source types: relative path (string starting `./`, or bare name under `metadata.pluginRoot`; `"."` = marketplace root); `github` (`repo` "owner/repo", `ref`, `sha`); `url` (full git URL, `ref`, `sha`); `git-subdir` (`url`, `path`, `ref`, `sha`; sparse partial clone); `npm` (`package`, `version`, `registry`; install scripts never run); `archive` (`url` https only, `sha256`, v2.1.224+); `command` (`command`, `timeout` 1-600s default 60, `mode`: `copy` default or `link`, v2.1.229+). [DOC S-4m2kbuls]
- A relative-path source resolves only when Claude Code has the marketplace's files (`github`, `git`, `file`, `directory` sources); a bare `url` marketplace source fetches only `marketplace.json`, so relative-path entries there can't resolve — give them an object source (`github`/`git-subdir`) instead. [DOC S-4m2kbuls]

### Install, scopes, CLI
- Install scopes: user (`enabledPlugins` in `~/.claude/settings.json`, every project on the machine), project (`.claude/settings.json`, committed; each collaborator still runs `claude plugin install ... --scope project` once), local (`.claude/settings.local.json`, this repo only for you). Precedence: local > project > user. [DOC S-havfntgx, S-toe7z3kj]
- `claude plugin install <plugin> [-s/--scope user|project|local] [--config key=value] [-y/--yes] [--accept-command <sha256>] [--json]`; default scope `user`; `-y` ignored when Claude runs the command itself via the Bash tool. [DOC S-gxuoqjzy]
- `claude plugin uninstall <plugin> [-s/--scope] [--keep-data] [--prune] [-y] [--json]`; `claude plugin enable|disable <plugin> [-s/--scope] [--json]` (scope auto-detected local→project→user when omitted); `claude plugin update <plugin> [-s/--scope user|project|local|managed] [-y] [--accept-command] [--json]`; `claude plugin list [--json] [--available]`; `claude plugin details <name>`; `claude plugin prune [-s/--scope] [--dry-run] [-y]` (`autoremove` alias) removes orphaned auto-installed dependencies only. [DOC S-gxuoqjzy]
- `claude plugin marketplace add <source>` accepts `owner/repo` (GitHub, `#ref` to pin), a full git clone URL (`#ref`), a local path (must start `./` or `../`, else read as GitHub shorthand), or a hosted `marketplace.json` URL; `/plugin market` is a shorthand for `/plugin marketplace` in a session. [DOC S-havfntgx]
- `/plugin install <plugin> --marketplace <source>` (v2.1.275+) adds an unregistered marketplace and installs in one step, with a confirmation prompt unless the marketplace is already added. [DOC S-havfntgx]
- Exit codes for every `claude plugin` subcommand: `0` success, `1` failure; `validate` adds `2` for an unexpected error; `eval` has its own extra codes. [DOC S-gxuoqjzy]
- Plugin id form is `<name>@<origin>`; origin `@<marketplace>` (installed), `@inline` (`--plugin-dir`/`--plugin-url`/`CLAUDE_CODE_PLUGIN_DIRS`/SDK `plugins` option, session-only), `@skills-dir` (`.claude/skills/`), `@synced` (claude.ai account). [DOC S-toe7z3kj]
- Six `enabledPlugins` sources by precedence (low to high): `--add-dir` settings, `user` (`~/.claude/settings.json`), `project` (`.claude/settings.json`), `local` (`.claude/settings.local.json`), `flag` (`--settings`), `managed`; sources merge key by key per plugin id. [DOC S-toe7z3kj]
- Plugin files layout under `~/.claude/plugins/` (or `CLAUDE_CODE_PLUGIN_CACHE_DIR`): `cache/<marketplace>/<plugin>/<version>/` (`${CLAUDE_PLUGIN_ROOT}`), `data/<plugin-id>/` (`${CLAUDE_PLUGIN_DATA}`, persists across updates, deleted on uninstall from last scope unless `--keep-data`), `marketplaces/<name>/`, `synced/`, `.trash/`, `installed_plugins.json`, `known_marketplaces.json`, `flagged-plugins.json`. [DOC S-toe7z3kj]
- Version resolution order for a marketplace-sourced plugin (all source types except `command`): 1) manifest `version`, 2) marketplace entry `version`, 3) source-type default (e.g. commit SHA for a relative path in a git-hosted marketplace). Setting `version` pins users to that copy until it changes; omitting it tracks commits. [DOC S-toe7z3kj, S-pelzabjq per work-left.md]
- Updating or uninstalling a plugin writes an `.orphaned_at` marker on the old version directory; background cleanup removes it 14 days later. [DOC S-toe7z3kj]
- Node.js dependency install into a copied plugin's cache: `bun.lock`/`bun.lockb` -> `bun install --frozen-lockfile --ignore-scripts`; `npm-shrinkwrap.json`/`package-lock.json` -> `npm ci --ignore-scripts`; first lockfile match wins in that order; Yarn/pnpm lockfiles and a `bunfig.toml` beside a Bun lockfile are skipped; 60-second timeout; lifecycle scripts never run; not configurable off. [DOC S-toe7z3kj]

### Org / managed settings for plugins
- Force-install: managed `extraKnownMarketplaces` (keyed by marketplace `name`, each entry a `source` object plus `autoUpdate`) + managed `enabledPlugins` (`plugin-name@marketplace-name: true`); installs at the start of the user's next session; users can't disable a managed-enabled plugin. Setting a plugin to `false` in managed `enabledPlugins` blocks it at every scope and hides it. [DOC S-rp4dtt4w]
- `strictKnownMarketplaces` (alias `allowedMarketplaces`) allowlists marketplace sources (`github`, `github` owner wildcard `owner/*` v2.1.223+, `git`, `url`, `file`/`directory`, `hostPattern` regex, `pathPattern` regex, `skills-dir`); `[]` blocks every source including the official marketplace. `blockedMarketplaces` denylists sources, checked before the allowlist. Both lists apply before any download and again at session start. [DOC S-rp4dtt4w]
- Other managed plugin-policy keys: `syncClaudeAiPlugins` (`false` stops claude.ai-synced plugins, v2.1.273+), `disableSideloadFlags` (rejects `--plugin-dir`, `--plugin-url`, `--agents`, SDK `plugins` option, non-SDK `--mcp-config`, and `CLAUDE_CODE_PLUGIN_DIRS` folders), `disableCommandPluginSources` (blocks `command`-source plugins; defaults to the value of `allowManagedHooksOnly` when unset), `strictPluginOnlyCustomization` (`true` or an array of `skills`/`agents`/`hooks`/`mcp` to require plugin/managed/built-in origin only), `pluginSuggestionMarketplaces`, `pluginTrustMessage`, `allowedChannelPlugins`, and env var `CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL=1`. Aliases `strictKnownMarketplaces`/`allowedMarketplaces` and `extraKnownMarketplaces`/`additionalMarketplaces` require v2.1.232+. [DOC S-rp4dtt4w]
- Seed containers/CI: build-time `CLAUDE_CODE_PLUGIN_CACHE_DIR=/opt/claude-seed` to install a marketplace+plugins into a seed directory, then runtime `CLAUDE_CODE_PLUGIN_SEED_DIR=/opt/claude-seed` (`:`/`;`-separated for several) loads them without cloning; seed marketplaces are read-only, `autoUpdate` forced off, and seed entries overwrite a same-name user marketplace entry on each startup; plugins from a seed still need `enabledPlugins` to load. `CLAUDE_CODE_SYNC_PLUGIN_INSTALL=1` makes a `-p`/CI run wait for background plugin installs before its first query. [DOC S-rp4dtt4w]
- A repository's own `.claude/settings.json` can set `extraKnownMarketplaces`/`enabledPlugins` per repo, but `extraKnownMarketplaces` there applies only in a folder the contributor has trusted (workspace trust dialog, or `hasTrustDialogAccepted` in `~/.claude.json` for `-p` runs). [DOC S-rp4dtt4w]

### MCP tool naming and eval
- A plugin-provided MCP tool is named `mcp__plugin_<plugin>_<server>__<tool>`, and it appears in `/mcp` as `plugin:<plugin>:<server>`. [DOC S-i7if5i7z, S-toe7z3kj]
- `claude plugin eval` requires Claude Code v2.1.269+ and (if git is present) git 2.31+; each case's `evals/<case>/prompt.md` (+ optional `case.yaml`, `graders/*.md`) runs 3 times by default in an isolated non-interactive session with only the target plugin loaded, and by default again with no plugin (the no-plugin baseline) to compute `WITH`, `W/OUT`, and `Δ`; `--ablation none` runs only the with-arm. [DOC S-lkcsn2fs]
- `claude plugin eval init` (optionally `--bare <case-name>` for a blank template) interactively proposes cases and graders and trials them; grader `type` is one of `regex`, `tool_used`, `tool_order`, `file_exists` (free, transcript/file based) or `llm`/`baseline` (judge-model calls, cost money); a `tool_used` grader for `tool: Skill` uses `input_match` against the namespaced `plugin:skill` invocation. [DOC S-lkcsn2fs]
- Eval suite directory defaults to `evals/` under the plugin root; override via manifest `"experimental": {"evals": "quality/evals"}` or the `--eval-dir` flag (flag wins if both set); path must be relative, no `..`. [DOC S-lkcsn2fs]
- Grants: runs default to read-only tools (`Read`, `Glob`, `Grep`, `NotebookRead`, `Skill`, `AskUserQuestion`, `Agent`, `TodoWrite`, task tools) plus `allowed_tools` in a case's frontmatter; `Bash`/`Write`/`Edit`/`WebFetch`/`WebSearch` need an explicit `--allow-tools` grant on the run, and any granted `Bash` runs under the OS-level sandbox. [DOC S-lkcsn2fs]

## Reference
| Key / thing | Where | Note |
|---|---|---|
| `.claude-plugin/plugin.json` | plugin root | manifest; `name` only required field |
| `hooks/hooks.json` | plugin root | merges with manifest `hooks`; see `claude/hooks.md` for event/field semantics |
| `.mcp.json` | plugin root | merges with manifest `mcpServers`; see `claude/managed-mcp.md` for allow/deny controls that also gate plugin MCP servers |
| `skills/`, `agents/` | plugin root | see `claude/skills-and-subagents.md` for `SKILL.md`/agent `.md` frontmatter, namespacing as `<plugin>:<name>` |
| `.claude-plugin/marketplace.json` | marketplace root | catalog; `name`, `owner`, `plugins` required |
| `${CLAUDE_PLUGIN_ROOT}` | env var | version-specific cache dir; changes every version, don't persist data there |
| `${CLAUDE_PLUGIN_DATA}` | env var | persistent per-plugin dir, survives updates |
| `extraKnownMarketplaces` / `enabledPlugins` | managed or `.claude/settings.json` | force-register marketplace / force-enable-or-block plugins |
| `strictKnownMarketplaces` / `blockedMarketplaces` | managed only | allowlist / denylist of marketplace sources |

## Examples
Minimal manifest and marketplace entry:
```json
{
  "name": "it-ops-helper",
  "version": "1.0.0",
  "description": "Internal helper skills",
  "author": { "name": "IT Ops", "email": "itops@corp.example.com" }
}
```
```json
{
  "name": "it-ops-marketplace",
  "owner": { "name": "IT Ops" },
  "plugins": [
    { "name": "it-ops-helper", "source": "./plugins/it-ops-helper" }
  ]
}
```
Force-install for a fleet (managed settings):
```json
{
  "extraKnownMarketplaces": {
    "it-ops-marketplace": {
      "source": { "source": "github", "repo": "corp-example/it-ops-marketplace" },
      "autoUpdate": true
    }
  },
  "enabledPlugins": { "it-ops-helper@it-ops-marketplace": true }
}
```
Plugin MCP tool name a hook or permission rule would match: `mcp__plugin_it-ops-helper_inventory__lookup_asset` for asset `PL-LT-00123`.
