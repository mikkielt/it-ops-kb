---
topic: claude/mcp-install-scopes
priority: P3
applies_to: "Claude Code MCP installation scopes (local, project, user), the project .mcp.json file and the claude mcp add, add-json, get and list commands, as the Claude Code docs read on 2026-10-23 (the docs describe Claude Code 2.1.2xx; versions are named where the page names them)"
retrieved_utc: 2026-10-23
sources: [S1862, S2179, S-puvxt3jl, S-pmhgjvef, S-7caoetch, S-hvuk3dqt]
status: partial
---

# Claude Code MCP installation scopes: local scope per project directory, project .mcp.json, and a file that does not parse

## Summary
Claude Code stores an MCP server at one of three scopes. `local` (the default) and `user` live in `~/.claude.json`, the first under the entry of one project directory, the second at the top level; `project` is a `.mcp.json` file in the project root that is meant to be committed. When a name appears in more than one scope the highest one wins whole: local, then project, then user, then plugins, then claude.ai connectors. The docs key a local-scope entry to "the project" the command ran in and show the key as the directory the command was run from; they do not say how a session started in a directory above the repository, or in a subdirectory, maps to a key, nor whether a `.mcp.json` above the start directory is found. A `.mcp.json` Claude Code cannot use is not loaded: before Claude Code 2.1.144 `claude mcp list` then reported no servers at all, and since then it shows the configuration errors.

## Facts
### The three scopes
- `claude mcp add` writes to one of three scopes in two files: `local` (the default) in `~/.claude.json` "under the entry for this project", visible only to the person and only in that project; `project` in `.mcp.json` in the project root, for everyone who clones it; `user` in `~/.claude.json` under the top-level `mcpServers` key, in all the person's projects. On Windows `~/.claude.json` is `%USERPROFILE%\.claude.json`, and `CLAUDE_CONFIG_DIR`, when set, makes Claude Code read `.claude.json` from inside that directory. [DOC S2179]
- A local-scoped server "loads only in the project where you added it"; the command writes it into the entry for the current project, and the page's example run from `/path/to/your/project` produces `{"projects": {"/path/to/your/project": {"mcpServers": {...}}}}`. MCP "local scope" is not the `.claude/settings.local.json` of general settings. [DOC S1862]
- When Claude Code changes the session's directory with `/cd`, it disconnects the previous directory's project and local-scope MCP servers (and the servers of plugins no longer enabled). [DOC S-pmhgjvef]
- `claude mcp add`, `add-json` and `remove` for the `user` or `local` scope exit with `MCP server "<name>" was not saved to <path>/.claude.json` when the change is not in the file after the write (the file read-only or sandbox-protected), the path followed by `(local scope for <project directory>)` for a local-scope server; before Claude Code 2.1.283 they reported success anyway. [DOC S-7caoetch]
- `claude mcp get <name>` shows which scope holds a server's definition. [DOC S2179]
- When the same name is defined in more than one place, Claude Code connects once, using the whole entry from the highest-precedence source (fields are not merged): local, project, user, plugin-provided servers, claude.ai connectors; the three scopes match by name, plugins and connectors by endpoint. Defining a name in several scopes with different endpoints raises a warning in `claude mcp list` and `/mcp`. [DOC S1862]
- Claude Code gives a stdio server the environment variable `CLAUDE_PROJECT_DIR` (the stable project root) and answers the server's `roots/list` with the session's launch directory plus any added working directories. [DOC S1862]
- A server declared in a project `.mcp.json` or at local scope runs its `headersHelper` command from the project directory the server is declared in, and only after the trust dialog for that directory is accepted. [DOC S1862]

### The project file
- Project scope is a `.mcp.json` "at your project's root directory" with servers under the `mcpServers` key; `claude mcp add --scope project` creates or updates it. Interactive sessions ask for approval before using its servers, `claude mcp reset-project-choices` clears the choices, and `claude -p`, Agent SDK and some cloud sessions load them without asking. [DOC S1862]
- `claude mcp list` and `claude mcp get` read project-server approvals only from settings files outside the repository until the workspace is trusted; a server not yet approved shows `Pending approval`. A server a `disabledMcpjsonServers` entry rejects shows `Rejected` in `claude mcp get`. [DOC S1862]
- `.mcp.json` supports `${VAR}` and `${VAR:-default}` in `command`, `args`, `env`, `url` and `headers`; an unset variable with no default does not stop the file loading: the server loads with the `${VAR}` text and a warning appears in `claude mcp list`. [DOC S1862]
- The docs' troubleshooting table lists why a `.mcp.json` never loads: the file is under `.claude/`, or its servers sit under a top-level `servers` key (VS Code's `mcp.json` shape) instead of `mcpServers`; an `mcpServers` block in `settings.json` is not read at all. Relative paths in `command` or `args` resolve against the directory Claude Code was launched from, not the location of `.mcp.json`. [DOC S-puvxt3jl]
- A JSON entry with a `url` and no `type` is a configuration error, because an entry with no `type` is read as stdio; Claude Code skips that server and reports `MCP server "<name>" has a "url" but no "type"; add "type": "http" (or "sse" / "ws") to this entry`. A `"type": "sdk"` entry is skipped with a warning too. [DOC S1862]
- Claude Code 2.1.144's changelog lists the fix for `claude mcp list` "silently reporting no servers when `.mcp.json` can't be parsed (e.g. using VS Code's `servers` key instead of `mcpServers`)": it now shows configuration errors. Another entry fixes an empty `.mcp.json` being reported as invalid. [DOC S-hvuk3dqt]
- So a `.mcp.json` that cannot be parsed (invalid JSON, or the wrong top-level key) loads none of its servers, and on Claude Code 2.1.144 or later the reason is in `claude mcp list`; the docs read do not say what an interactive session shows at start for a file that does not parse. [DER S-hvuk3dqt, S-puvxt3jl: the changelog fix and the table row; the interactive start message was not found in the pages read]

### Not stated in the docs read
- Which key a local-scope entry takes when a session starts in a directory other than the one the `add` command ran in (a subdirectory of the repository, or a workspace directory above it), and whether it takes the git root: the page says "the current project" and shows the directory the command was run from. A registration for a workspace directory is therefore made by running the command from that directory, and `claude mcp get <name>` there shows whether it resolved. [UNK]
- Whether a `.mcp.json` in a parent of the start directory is read, or only the one in the start directory or repository root: the pages read say "project root" and "repository root" and describe no search upward for this file (the sandbox page lists `.mcp.json` among the protected files "in your working directory and the directories above it", which concerns writes, not loading). [UNK]
- Whether the `claude mcp add` command run outside a trusted folder, or from a directory without a git repository, writes the same local key; the docs read name no such case. [UNK]

## Reference
| Scope | Where it is stored | Who sees it | Source |
|---|---|---|---|
| local (default) | `~/.claude.json`, `projects.<directory>.mcpServers` | the person, one project | S1862, S2179 |
| project | `.mcp.json` in the project root, key `mcpServers` | everyone who clones it, after approval | S1862 |
| user | `~/.claude.json`, top-level `mcpServers` | the person, every project | S1862, S2179 |

See also `claude/settings-and-scopes.md` (settings files and their precedence, `--setting-sources`), `claude/managed-mcp.md` (the managed file with the same format), `claude/ci-and-headless.md` (what a `-p` run loads) and `claude/hooks.md` (the `CLAUDECODE` and `CLAUDE_CODE_CHILD_SESSION` variables, including an IDE's integrated terminal).

## Examples
- SNIPPET: register one stdio server at local scope for the directory the command runs in, then check which scope holds it; context: Claude Code 2.1.2xx CLI, placeholder server name and script path; checked: no [DER S1862, S2179: `claude mcp add-json` takes a name and a JSON object, `--scope` picks the scope, `claude mcp get` shows the scope]
```bash
cd /path/to/workspace
claude mcp add-json example-kb '{"type":"stdio","command":"python3","args":["/path/to/clone/_tools/kb_mcp.py"]}' --scope local
claude mcp get example-kb
```
