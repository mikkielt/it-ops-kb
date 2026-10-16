---
topic: claude/large-codebases
priority: P3
applies_to: "Claude Code docs: large codebases, how Claude Code works, best practices (retrieved 2026-09-28); several repositories: agent view, Desktop, settings, cloud environments (retrieved 2026-10-15)"
retrieved_utc: 2026-10-15
sources: [S-4jj4dtg4, S-eubvc22d, S-o3v6ozch, S-aishnkok, S-3qhgxjky, S2057, S-gu5aqnrl]
status: complete
---

# Working in a large codebase with Claude Code without loading all of it

## Summary
Claude Code does not load a repository into context up front: it loads instruction files for where it starts,
reads more as it works, and compacts when context fills. Anthropic's large-codebase guide scopes that work to the
part of the tree a task touches: per-directory `CLAUDE.md` files that load on demand, `claudeMdExcludes`, `Read`
deny rules for generated and vendored code, a code intelligence plugin instead of scanning files, sparse
worktrees, per-directory skills, and an existing code search or RAG index exposed as an MCP tool. The same ideas
hold for any coding agent (`agents/codebase-mapping.md`).

## Facts
- The context window holds the conversation, file contents, command outputs, CLAUDE.md, auto memory, loaded skills and system instructions; when it nears the limit Claude Code clears older tool outputs first, then summarizes the conversation, so rules that must persist belong in CLAUDE.md. [DOC S-eubvc22d]
- A "Compact Instructions" section in CLAUDE.md, or `/compact` with a focus, controls what compaction keeps; `/context` shows what uses space. [DOC S-eubvc22d]
- MCP tool definitions are deferred by default and loaded through tool search, so until a tool is used only tool names and server instructions take context. [DOC S-eubvc22d]
- Claude Code loads every CLAUDE.md from the working directory and its parents at launch and each subdirectory's CLAUDE.md on demand when it reads files there. [DOC S-4jj4dtg4]
- Started from the repository root, Claude can read every file and loads only the root CLAUDE.md at launch; started from a subdirectory, it can read that subtree only (until more is granted) and loads that directory's and every ancestor's CLAUDE.md. [DOC S-4jj4dtg4]
- Project `.claude/settings.json` is not inherited from parent directories the way CLAUDE.md files are. [DOC S-4jj4dtg4]
- A per-directory CLAUDE.md lives with its code and loads when started there or when Claude reads a file there; a path-scoped rule in `.claude/rules/` lives centrally and loads when Claude works with a file matching its `paths:` glob. [DOC S-4jj4dtg4]
- Claude's content searches respect `.gitignore`; for checked-in generated or vendored paths the guide uses `Read` deny rules in `permissions.deny` (e.g. `Read(./**/vendor/**/*)`). [DOC S-4jj4dtg4]
- `Read` deny rules cover the built-in file tools and the Bash file commands Claude Code recognizes when a denied path is an argument; a Bash `grep -r` or `find` over a directory with denied files still prints them, and subprocesses that open files themselves are not covered. [DOC S-4jj4dtg4]
- A code intelligence plugin lets Claude find definitions and callers through the language server instead of reading and grepping files; it pairs with `claudeMdExcludes` and `Read` deny rules, which keep irrelevant content out. [DOC S-4jj4dtg4]
- `worktree.sparsePaths` makes a worktree check out only the listed directories plus root-level files (git sparse-checkout); every worktree in a session, subagent worktrees included, shares the list. [DOC S-4jj4dtg4]
- A directory added with `--add-dir` or `/add-dir` loads its skills, and its CLAUDE.md and rules only with `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1`; one added through the `additionalDirectories` setting gives file access only, no CLAUDE.md, rules or skills. [DOC S-4jj4dtg4]
- A skill loads on demand when relevant: Claude chooses from every discovered skill's name and description and only the chosen skill's content enters context; a skill's `paths` frontmatter loads it only for matching files. [DOC S-4jj4dtg4]
- Started from the repository root, skills from every subdirectory Claude touches accumulate; with many skills some lose their descriptions, so the guide advises short descriptions that lead with words a request would contain. [DOC S-4jj4dtg4]
- To move conventions out of always-loaded CLAUDE.md the guide lists skills, plugins and MCP servers: an organization that already runs a code search or RAG index over the repository exposes it as an MCP tool so Claude queries it instead of reading files. [DOC S-4jj4dtg4]
- A `SessionStart` hook's stdout is added to Claude's context before the first prompt; the guide uses one to map the launch directory to the plugin its owners maintain. [DOC S-4jj4dtg4]
- Anthropic's best practices treat context as the fundamental constraint and delegate codebase research to subagents, which read files in their own context windows and report summaries. [DOC S-o3v6ozch]

### Several repositories in one session
- The same mechanism that grants a sibling package grants a separately checked-out repository: `permissions.additionalDirectories` (relative paths resolve against the directory Claude starts from) or `--add-dir` at launch; either lets Claude read and edit files there. [DOC S-4jj4dtg4]
- The guide commits `additionalDirectories` to `.claude/settings.json` for sibling directories everyone needs, and uses `.claude/settings.local.json` or `--add-dir` for a personal or one-off selection. [DOC S-4jj4dtg4]
- Agent view (`claude agents`) opened in a parent directory dispatches a new session into a child repository named with `@<repo>` in the prompt; the `@` list holds git repositories one level below the launch directory, the repository's own worktrees inside its tree, and directories that already have a session. [DOC S-aishnkok]
- Agent view passes every configuration flag, `--add-dir` included, through to the sessions it dispatches; `--add-dir` is repeated once per directory and placed after `agents`, since before it `claude agents --json` fails with `unknown option`. [DOC S-aishnkok]
- Cloud sessions support several repositories: in the Desktop app, after choosing a cloud environment, the **+** button beside the repository adds more, each with its own branch selector, for tasks such as updating a shared library and its consumers. [DOC S-3qhgxjky]
- In an Anthropic-hosted environment a cloud session with several repositories starts above the clones and reads only `enabledPlugins` and `extraKnownMarketplaces` from each repository's `.claude/settings.json`: no permission rules, hooks or `env`. [DOC S2057]
- So a `SessionStart` hook in a repository's settings does not run in such a session; the cloud environments page installs dependencies there with the environment's setup script instead. [DOC S-gu5aqnrl]
- Plan a multi-repository cloud session around what it drops: permission rules and hooks that guard one repository locally do not reach it, so the guard has to live in the cloud environment (setup script, network policy) or the session should take one repository. [DER S2057, S-gu5aqnrl: settings read in multi-repository sessions; hooks not run there]

## Reference
- Large codebases: https://code.claude.com/docs/en/large-codebases
- How Claude Code works (context window): https://code.claude.com/docs/en/how-claude-code-works
- Best practices: https://code.claude.com/docs/en/best-practices
- Several repositories: agent view https://code.claude.com/docs/en/agent-view, Desktop cloud sessions https://code.claude.com/docs/en/desktop, settings in cloud sessions https://code.claude.com/docs/en/settings, cloud environments https://code.claude.com/docs/en/cloud-environments; coordinating sessions across repositories: `claude/cross-session-messaging.md`; GitLab pipelines across projects: `gitlab/multi-project-pipelines.md`.
- Related: `claude/settings-and-scopes.md` (CLAUDE.md scopes, imports, `claudeMdExcludes`, rules); `claude/skills-and-subagents.md`; `claude/parallel-sessions.md` (agent view worktree isolation, `worktree.bgIsolation`, and the other parallel-work options); `claude/plugins.md` (code intelligence plugins); `agents/codebase-mapping.md` (tool-native mapping); `agents/coding-agent-codebase-context.md` (how other coding agents do the same: repo maps, indexes, AGENTS.md discovery); `agents/docs-maintenance-agents.md` (AGENTS.md and Copilot instruction files).

## Examples
- SNIPPET: keep generated and vendored code out of Claude's reads; context: Claude Code, project `.claude/settings.json` at the directory sessions start from; checked: syntax [DOC S-4jj4dtg4]
```json
{
  "permissions": {
    "deny": [
      "Read(./**/dist/**/*)",
      "Read(./**/build/**/*)",
      "Read(./**/*.generated.*)",
      "Read(./**/vendor/**/*)"
    ]
  }
}
```
