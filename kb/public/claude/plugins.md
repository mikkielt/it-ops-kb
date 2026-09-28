---
topic: claude/plugins
priority: P2
applies_to: "Claude Code 2.1.281 docs (retrieved 2026-09-26)"
retrieved_utc: 2026-09-28
sources: [S-n5myb3fn, S-3peuisvr, S-3xyywfcr, S-4m2kbuls, S-havfntgx, S-toe7z3kj, S-rp4dtt4w, S-gxuoqjzy, S-r3nam2zs, S-pelzabjq, S-i7if5i7z, S-lkcsn2fs, S-cgtbvuug, S-3yod3u7q]
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
- `skills` in the manifest *adds* to the default `skills/` scan; `commands`, `agents`, `outputStyles`, `workflows`, `experimental.themes` and `experimental.monitors` *replace* their default location; `hooks`, `mcpServers` and `lspServers` *merge* into the default file (`hooks/hooks.json`, `.mcp.json`, `.lsp.json`), which loads first. [DOC S-3xyywfcr]
- An unrecognized top-level manifest key is stripped (plugin still loads, `validate` warns); an unknown key inside a `userConfig` option, `channels` entry, `lspServers` config or `monitors` entry is a hard error and the plugin does not load. [DOC S-3xyywfcr]
- `claude plugin validate <path>` reports `Validation passed`, `Validation passed with warnings` (unknown top-level field, non-kebab-case `name`, missing `version`/`description`/`author`), or `Validation failed` (type mismatch, path missing/escapes plugin root, unknown strict-object key); `--strict` turns warnings into failures. [DOC S-3xyywfcr]
- `mcpServers` accepts a `.json` file path, an `.mcpb`/`.dxt` bundle path or URL (extracted/downloaded into `.mcpb-cache/`), or an inline map; `.mcp.json` at the plugin root loads first, then declared shapes in order, and a server name declared later replaces an earlier one. [DOC S-3xyywfcr]
- `lspServers` config fields: `command` and `extensionToLanguage` (required); optional `args`, `transport` (`stdio` default or `socket`, though every server actually runs over stdio), `env`, `initializationOptions`, `settings`, `workspaceFolder`, `startupTimeout`/`shutdownTimeout` (ms), `restartOnCrash` (default `true`), `maxRestarts`, `diagnostics` (default `true`). [DOC S-3xyywfcr]
- `experimental.monitors` (default `monitors/monitors.json`) entries: `name`, `command`, `description` required; `when: "always"` (default, starts at session start/reload) or `"on-skill-invoke:<skill>"`. Monitors run only in interactive sessions, not on Bedrock, Google Cloud Agent Platform, or Microsoft Foundry. [DOC S-3xyywfcr]
- `commands` manifest entries set exactly one of `source` or `content` (both or neither fails validation); optional `description`, `argumentHint`, `model`, `allowedTools`. [DOC S-3xyywfcr]
- `claude plugin init <name> [--with skills|agents|hooks|mcp|lsp|output-style|channel] [--description] [--author] [--author-email] [-f/--force]` scaffolds `~/.claude/skills/<name>/`, requires Claude Code v2.1.157+; it loads next session as `<name>@skills-dir` with no install step. [DOC S-3peuisvr, S-gxuoqjzy]
- `claude plugin validate ./my-plugin` and `claude --plugin-dir ./my-plugin` (repeatable to load several; can point at a `.zip`) are the create/test loop; loading a folder of plugins (no `.claude-plugin/` at the top level) requires v2.1.265+. [DOC S-3peuisvr]
- `--plugin-url <zip-url>` downloads a `.zip` plugin archive at startup for one session (repeat the flag or space-separate URLs for several); `CLAUDE_CODE_PLUGIN_DIRS` (v2.1.280+) lists absolute plugin-dir paths for a session where flags can't be passed; project/local settings can't set that variable. [DOC S-3peuisvr]
- Symlinks in a plugin: within the plugin's own directory, preserved as relative symlinks in the cache; elsewhere in the same marketplace, dereferenced and copied; outside the marketplace, skipped. A local-path or `command`-source (copy mode) install preserves only symlinks resolving inside the plugin's own directory. [DOC S-pelzabjq]
- A rejected component path (points outside the plugin root, a symlink leading outside it, or on macOS/Linux a backslash anywhere in the path) surfaces as `path escapes plugin directory`, and the plugin loads without that component. [DOC S-toe7z3kj]

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
- `claude plugin marketplace add <source>` accepts `owner/repo` (GitHub, `#ref` to pin), a full git clone URL (`#ref`), a local directory or `marketplace.json` path (a relative path must start `./` or `../`, else it is read as GitHub shorthand), or a hosted `marketplace.json` URL; `/plugin market` is a shorthand for `/plugin marketplace` in a session. [DOC S-havfntgx]
- `/plugin install <plugin> --marketplace <source>` (v2.1.275+) adds an unregistered marketplace and installs in one step, with a confirmation prompt unless the marketplace is already added. [DOC S-havfntgx]
- Exit codes for every `claude plugin` subcommand: `0` success, `1` failure; `validate` adds `2` for an unexpected error; `eval` has its own extra codes. [DOC S-gxuoqjzy]
- Plugin id form is `<name>@<origin>`; origin `@<marketplace>` (installed), `@inline` (`--plugin-dir`/`--plugin-url`/`CLAUDE_CODE_PLUGIN_DIRS`/SDK `plugins` option, session-only), `@skills-dir` (`.claude/skills/`), `@synced` (claude.ai account). [DOC S-toe7z3kj]
- Six `enabledPlugins` sources by precedence (low to high): `--add-dir` settings, `user` (`~/.claude/settings.json`), `project` (`.claude/settings.json`), `local` (`.claude/settings.local.json`), `flag` (`--settings`), `managed`; sources merge key by key per plugin id. [DOC S-toe7z3kj]
- Plugin files layout under `~/.claude/plugins/` (or `CLAUDE_CODE_PLUGIN_CACHE_DIR`): `cache/<marketplace>/<plugin>/<version>/` (`${CLAUDE_PLUGIN_ROOT}`), `data/<plugin-id>/` (`${CLAUDE_PLUGIN_DATA}`, persists across updates, deleted on uninstall from last scope unless `--keep-data`), `marketplaces/<name>/`, `synced/`, `.trash/`, `installed_plugins.json`, `known_marketplaces.json`, `flagged-plugins.json`. [DOC S-toe7z3kj]
- In the `${CLAUDE_PLUGIN_DATA}` path `~/.claude/plugins/data/<id>/`, `<id>` is the plugin identifier with every character other than letters, digits, `_` and `-` replaced by `-` (`my-plugin@my-marketplace` becomes `my-plugin-my-marketplace`); the directory is created when first referenced, and on Windows substituted paths use forward slashes. [DOC S-i7if5i7z]
- A plugin loaded with `--plugin-dir` (id `<name>@inline`) therefore keeps its data in `~/.claude/plugins/data/<name>-inline/`, under the plugins root that `CLAUDE_CODE_PLUGIN_CACHE_DIR` can move. [DER S-i7if5i7z, S-toe7z3kj: the id sanitising rule applied to the `@inline` origin and the files layout above]
- `known_marketplaces.json` records each marketplace Claude Code has fetched, with its `source`, `installLocation`, `lastUpdated` and `autoUpdate`, one file per user; `marketplaces/<name>/` holds the clone or download of a marketplace added from GitHub, another Git host or a URL, while a local `file` or `directory` marketplace has no copy there and its `installLocation` is the path given. [DOC S-toe7z3kj]
- `claude plugin marketplace list --json` prints one object per marketplace with string fields `name`, `source` (`github`, `git`, `url`, `directory`, `file` or `claudeai`), `repo` (`owner/repo`, `github` only), `url` (the clone or fetch URL, `git` and `url` only), `path` (`directory` and `file` only), `ref` (when pinned) and `installLocation`. [DOC S-gxuoqjzy]
- A hook or tool running from a plugin copy (`${CLAUDE_PLUGIN_ROOT}` = `cache/<marketplace>/<plugin>/<version>/`) finds the repository it was installed from through its marketplace: the `<marketplace>` entry of `known_marketplaces.json` beside `cache/`, whose `source` names the git url or GitHub repository. It writes its own state only under `${CLAUDE_PLUGIN_DATA}`, since the cache copy changes with every version. [DER S-toe7z3kj, S-gxuoqjzy]
- Version resolution order for a marketplace-sourced plugin (all source types except `command`): 1) manifest `version`, 2) marketplace entry `version`, 3) source-type default (e.g. commit SHA for a relative path in a git-hosted marketplace). Setting `version` pins users to that copy until it changes; omitting it tracks commits. [DOC S-toe7z3kj, S-pelzabjq]
- When the computed version is unchanged, `claude plugin update` prints `<name> is already at the latest version (<version>).` and changes nothing on disk; background auto-update skips the plugin the same way. [DOC S-toe7z3kj]
- Background auto-update runs in an interactive session after the first message, following a random delay of up to ten minutes: it refreshes each marketplace with auto-update on and updates its installed plugins on disk; the running session keeps the loaded versions and shows `Plugin updated: <name> · Run /reload-plugins to apply`. [DOC S-toe7z3kj]
- Whether a marketplace auto-updates: `autoUpdate` on its `extraKnownMarketplaces` entry, else `autoUpdate` in `known_marketplaces.json` (the `/plugin` Marketplaces toggle), else the default (on for Anthropic's official marketplaces such as `claude-plugins-official` but off for `knowledge-work-plugins` and `first-party-plugins`, on for marketplaces added from claude.ai, off for every other marketplace); `DISABLE_UPDATES=1`, `DISABLE_AUTOUPDATER=1` or `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` turn the whole pass off unless `FORCE_AUTOUPDATE_PLUGINS=1`. [DOC S-toe7z3kj]
- Claude Code has no release-channel concept, and one marketplace serves one version of each plugin at a time; for stable and early-access tracks, host two marketplaces with different `name` values whose entries point at different refs of the plugin, and give the refs different versions (or omit `version` so the commit SHA differs), because a ref that moves without a version change leaves users on the cached copy. [DOC S-pelzabjq]
- Holding users on one version: `ref` (branch or tag) and `sha` (commit) on a `github`, `url` or `git-subdir` plugin entry; `#<ref>` on the marketplace add command (e.g. `your-org/your-marketplace#stable`) pins the catalog to that branch or tag; `<plugin>--v<version>` tags serve dependency version ranges. [DOC S-pelzabjq]
- A `git` marketplace source object in `extraKnownMarketplaces` takes `url` and an optional `ref` (the docs' example pins `"ref": "main"`); `marketplace add` reads `user@host:path[.git][#ref]` as a `git` source cloned over SSH and `https://.../repo.git[#ref]` as one cloned over HTTPS. [DOC S-4m2kbuls, S-gxuoqjzy]
- Updating or uninstalling a plugin writes an `.orphaned_at` marker on the old version directory; background cleanup removes it 14 days later. [DOC S-toe7z3kj]
- Node.js dependency install into a copied plugin's cache: `bun.lock`/`bun.lockb` -> `bun install --frozen-lockfile --ignore-scripts`; `npm-shrinkwrap.json`/`package-lock.json` -> `npm ci --ignore-scripts`; first lockfile match wins in that order; Yarn/pnpm lockfiles and a `bunfig.toml` beside a Bun lockfile are skipped; 60-second timeout; lifecycle scripts never run; the install runs only when the plugin root has both `package.json` and a supported lockfile. [DOC S-toe7z3kj]

### Org / managed settings for plugins
- Force-install: managed `extraKnownMarketplaces` (keyed by marketplace `name`, each entry a `source` object plus `autoUpdate`) + managed `enabledPlugins` (`plugin-name@marketplace-name: true`); installs at the start of the user's next session; users can't disable a managed-enabled plugin. Setting a plugin to `false` in managed `enabledPlugins` blocks it at every scope and hides it. [DOC S-rp4dtt4w]
- `strictKnownMarketplaces` (alias `allowedMarketplaces`) allowlists marketplace sources (`github`, `github` owner wildcard `owner/*` v2.1.223+, `git`, `url`, `file`/`directory`, `hostPattern` regex, `pathPattern` regex, `skills-dir`); `[]` blocks every source including the official marketplace. `blockedMarketplaces` denylists sources, checked before the allowlist. Both lists apply before any download and again at session start. [DOC S-rp4dtt4w]
- Other plugin-policy keys: `syncClaudeAiPlugins` (`false` stops claude.ai-synced plugins, v2.1.273+; not managed-only, users can also set it in user or local settings), `disableSideloadFlags` (rejects `--plugin-dir`, `--plugin-url`, `--agents`, SDK `plugins` option, non-SDK `--mcp-config`, and `CLAUDE_CODE_PLUGIN_DIRS` folders), `disableCommandPluginSources` (blocks `command`-source plugins; defaults to the value of `allowManagedHooksOnly` when unset), `strictPluginOnlyCustomization` (`true` or an array of `skills`/`agents`/`hooks`/`mcp` to require plugin/managed/built-in origin only), `pluginSuggestionMarketplaces`, `pluginTrustMessage`, `allowedChannelPlugins`, and env var `CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL=1`. Aliases `strictKnownMarketplaces`/`allowedMarketplaces` and `extraKnownMarketplaces`/`additionalMarketplaces` require v2.1.232+. [DOC S-rp4dtt4w]
- Seed containers/CI: build-time `CLAUDE_CODE_PLUGIN_CACHE_DIR=/opt/claude-seed` to install a marketplace+plugins into a seed directory, then runtime `CLAUDE_CODE_PLUGIN_SEED_DIR=/opt/claude-seed` (`:`/`;`-separated for several) loads them without cloning; seed marketplaces are read-only, `autoUpdate` forced off, and seed entries overwrite a same-name user marketplace entry on each startup; plugins from a seed still need `enabledPlugins` to load. `CLAUDE_CODE_SYNC_PLUGIN_INSTALL=1` makes a `-p`/CI run wait for background plugin installs before its first query. [DOC S-rp4dtt4w]
- A repository's own `.claude/settings.json` can set `extraKnownMarketplaces`/`enabledPlugins` per repo, but `extraKnownMarketplaces` there applies only in a folder the contributor has trusted (workspace trust dialog, or `hasTrustDialogAccepted` in `~/.claude.json` for `-p` runs). [DOC S-rp4dtt4w]

### MCP tool naming and eval
- A plugin-provided MCP tool is named `mcp__plugin_<plugin>_<server>__<tool>`, and its server appears in `/mcp` as `plugin:<plugin>:<server>`. [DOC S-i7if5i7z]
- `claude plugin eval` requires Claude Code v2.1.269+ and (if git is present) git 2.31+; each case's `evals/<case>/prompt.md` (+ optional `case.yaml`, `graders/*.md`) runs 3 times by default in an isolated non-interactive session with only the target plugin loaded, and by default again with no plugin (the no-plugin baseline) to compute `WITH`, `W/OUT`, and `Δ`; `--ablation none` runs only the with-arm. [DOC S-lkcsn2fs]
- `claude plugin eval init` (optionally `--bare <case-name>` for a blank template) interactively proposes cases and graders and trials them; grader `type` is one of `regex`, `tool_used`, `tool_order`, `file_exists` (free, transcript/file based) or `llm`/`baseline` (judge-model calls, cost money); a `tool_used` grader for `tool: Skill` uses `input_match` against the namespaced `plugin:skill` invocation. [DOC S-lkcsn2fs]
- Eval suite directory defaults to `evals/` under the plugin root; override via manifest `"experimental": {"evals": "quality/evals"}` or the `--eval-dir` flag (flag wins if both set); path must be relative, no `..`. [DOC S-lkcsn2fs]
- Grants: a run allows only the read-only tools a case lists in its `allowed_tools` frontmatter, chosen from `Read`, `Glob`, `Grep`, `NotebookRead`, `Skill`, `AskUserQuestion`, `Agent`, `TodoWrite` and the task tools, plus whatever the run grants with `--allow-tools`; `Bash`/`Write`/`Edit`/`WebFetch`/`WebSearch` need an explicit `--allow-tools` grant on the run, and any granted `Bash` runs under the OS-level sandbox. [DOC S-lkcsn2fs]

### Code intelligence (LSP) plugins
- Anthropic's official marketplace has code intelligence plugins, one language server per plugin (among them `pyright-lsp`, `typescript-lsp`, `gopls-lsp`, `rust-analyzer-lsp`, `csharp-lsp`, `jdtls-lsp`, `clangd-lsp`), installed with `/plugin install <name>@claude-plugins-official`; the language server binary is installed separately. [DOC S-cgtbvuug]
- A language with no official plugin is added by declaring its server in `.lsp.json` at a plugin root. [DOC S-cgtbvuug, S-i7if5i7z]
- Claude Code reads a language server's stdout as protocol messages only (logs go to stderr) and accepts message headers up to 64 KiB and message bodies up to 32 MiB. [DOC S-i7if5i7z]
- Claude Code returns an error result for each `LSP` tool call on a file whose language server it cannot start. [DOC S-3yod3u7q]
- What the `LSP` tool gives Claude (diagnostics after edits, definitions, references, symbols, call hierarchies) and where it is inactive: `agents/codebase-mapping.md`. [DER S-cgtbvuug, S-3yod3u7q: pointer to the facts kept there]

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
- SNIPPET: Minimal manifest and marketplace entry; context: Claude Code 2.1.281; checked: syntax [DOC S-3xyywfcr: `name`/`version`/`description`/`author` fields, `author.name` required and `author.email` optional]
```json
{
  "name": "it-ops-helper",
  "version": "1.0.0",
  "description": "Internal helper skills",
  "author": { "name": "IT Ops", "email": "itops@corp.example.com" }
}
```
- SNIPPET: a minimal `.claude-plugin/marketplace.json` catalog with one relative-path plugin entry; context: Claude Code 2.1.281; checked: syntax [DOC S-4m2kbuls: `name`/`owner.name`/`plugins` required fields, relative-path plugin `source`]
```json
{
  "name": "it-ops-marketplace",
  "owner": { "name": "IT Ops" },
  "plugins": [
    { "name": "it-ops-helper", "source": "./plugins/it-ops-helper" }
  ]
}
```
- SNIPPET: Force-install for a fleet (managed settings); context: Claude Code 2.1.281, managed settings (MDM/GPO); checked: syntax [DOC S-rp4dtt4w: `extraKnownMarketplaces` (`source`, `autoUpdate`) and `enabledPlugins` (`plugin-name@marketplace-name: true`) force-install keys]
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
