---
topic: agents/coding-agent-codebase-context
priority: P3
applies_to: "Aider v0.86.2; GitHub Copilot repository indexing (github/docs @87a7556); VS Code Copilot workspace context (vscode-docs @0fc6a01); Cursor docs (retrieved 2026-09-28); OpenAI Codex AGENTS.md (docs retrieved 2026-09-28, code rust-v0.158.0); Gemini CLI v0.61.0; Anthropic context-engineering article (2025-09-29)"
retrieved_utc: 2026-09-29
sources: [S1855, S-yq3633pk, S-pht5euzf, S-q4hcjmq7, S-g6eifvzw, S-oqjcjt4q, S-5yij7tgr, S-v2sqknkh, S-4owuypm5, S-iuskapuz, S-zsi4cru4, S-c5olve2h, S-jomschqn, S-c4vaxr7q, S-mer4fr7g, S-bci74yyr, S-fema44tc, S-clksl3oh, S-e7vrnq3a, S-mxqyhxx7]
status: complete
---

# How coding agents learn a codebase without loading all of it

## Summary
Coding assistants do not put a repository into the prompt. They combine three things: instruction files loaded up
front and scoped by directory or glob (CLAUDE.md, AGENTS.md, GEMINI.md, Cursor rules, Copilot instructions);
retrieval at the moment of need (grep, glob, file search, language-server lookups, and in some products a semantic
index, local or remote); and a compact overview such as Aider's ranked repository map. Anthropic calls the second
approach "just in time": the agent keeps file paths and queries, not file contents. What each product indexes,
where the index lives and how instruction files are discovered and capped differs; the facts below give the
official statements per product. Claude Code's own settings for this are in `claude/large-codebases.md`.

## Facts
### Just-in-time context
- Anthropic's context-engineering article describes "just in time" agents that keep lightweight identifiers (file paths, stored queries, links) and load data with tools at runtime, allowing progressive disclosure through exploration. [DOC S1855]
- The same article describes Claude Code as hybrid: CLAUDE.md files go into context up front, while glob and grep let it find and read files just in time, avoiding stale indexes and complex syntax trees. [DOC S1855]

### Repository map (Aider)
- Aider sends a repository map with each request: the repository's files with the key symbols defined in each; the model asks for the specific files it needs, and Aider offers to add them to the chat. [DOC S-yq3633pk]
- Aider picks what fits in the map with a graph ranking over a graph of files (nodes) and their dependencies (edges), keeping the identifiers most often referenced elsewhere. [DOC S-yq3633pk]
- `--map-tokens` is documented as defaulting to 1k tokens (0 disables the map); `--map-multiplier-no-files` (default 2) enlarges it when no files are in the chat; `--map-refresh` is `auto` (default), `always`, `files` or `manual`. [DOC S-yq3633pk, S-pht5euzf]
- Aider builds the map from tree-sitter and needs the language grammar's `tags.scm` for a language to be mapped. [DOC S-q4hcjmq7]
- At v0.86.2 the ranking is NetworkX PageRank personalised toward the files and identifiers mentioned in the chat. [CODE S-g6eifvzw: aider/repomap.py#RepoMap.get_ranked_tags]
- At v0.86.2 the default map budget is the model's input window divided by 8, clamped to 1024 to 4096 tokens; with no files in the chat the budget is multiplied, up to the context window minus padding. [CODE S-oqjcjt4q: aider/models.py#Model.get_repo_map_tokens; CODE S-g6eifvzw: aider/repomap.py#RepoMap.get_repo_map]

### Semantic indexes (GitHub Copilot, VS Code, Cursor)
- GitHub Copilot keeps a semantic code search index per repository, built automatically when a chat has repository context; the first index of a large repository can take up to 60 seconds, there is no limit on how many repositories are indexed, and indexed repositories are not used for model training. [DOC S-5yij7tgr]
- Copilot's cloud agent uses semantic code search besides exact-match tools like grep, with no configuration. [DOC S-5yij7tgr]
- Indexing a repository not hosted on GitHub (GitLab, local) from VS Code uploads the data to GitHub; the feature is policy-controlled and off by default. Content exclusion filters the index. [DOC S-5yij7tgr]
- VS Code's Copilot agents pick among search tools: semantic search (`#codebase`, needs a workspace index), text search, grep (no index needed), file search by glob, usages (definitions, references, implementations), directory listing and file reads; small workspaces may be read whole. [DOC S-v2sqknkh]
- In VS Code every search match becomes conversation context even if the file is never opened, so `.gitignore` and `files.exclude` (search and index) and `search.exclude` (search only) matter. [DOC S-v2sqknkh]
- A VS Code workspace index may be partly local and partly remote; remote indexing works for GitHub.com and GitHub Enterprise Cloud, not GitHub Enterprise Server, and binary files are not indexed. [DOC S-v2sqknkh]
- Cursor's current Search docs describe Instant Grep, whose index is built and queried on the local machine: Cursor uploads no paths or code to build it and stores no embeddings of the codebase for search. An Explore subagent searches in its own context and returns a summary. [DOC S-4owuypm5]
- `.cursorignore` (gitignore syntax) hides files from Cursor's agent, Tab, inline edit and @-mentions, but the agent's terminal and MCP tools can still reach them. [DOC S-zsi4cru4]

### Instruction files and their discovery
- Cursor project rules are `.mdc` files in `.cursor/rules` whose frontmatter (`alwaysApply`, `description`, `globs`) makes them always apply, attach when a matching file is in context, or be chosen by the agent from the description; Cursor advises rules under 500 lines that reference files rather than copy them. [DOC S-iuskapuz]
- Cursor also reads nested AGENTS.md files, combining them with parent directories' and letting the more specific win. [DOC S-iuskapuz]
- OpenAI Codex reads one global file in `~/.codex` (`AGENTS.override.md`, else `AGENTS.md`), then walks from the project root (typically the Git root) down to the working directory taking at most one file per directory, and concatenates them root-down so closer files override earlier guidance. [DOC S-c5olve2h]
- Codex stops adding instruction files once their combined size reaches `project_doc_max_bytes`, 32 KiB by default, and builds the chain once per run. [DOC S-c5olve2h]
- The default is `32 * 1024` in the code at rust-v0.158.0. [CODE S-jomschqn: codex-rs/config/src/config_toml.rs#DEFAULT_PROJECT_DOC_MAX_BYTES]
- Gemini CLI loads a global `~/.gemini/GEMINI.md`, workspace files, and just-in-time files found when a tool touches a directory (scanning it and its ancestors up to a trusted root), concatenating everything into every prompt. [DOC S-c4vaxr7q]
- Gemini CLI's `context.fileName` accepts a list (e.g. `["AGENTS.md", "GEMINI.md"]`); memory discovery searches at most `context.discoveryMaxDirs` (default 200) directories and stops going up at `context.memoryBoundaryMarkers` (default `.git`). [DOC S-c4vaxr7q, S-mer4fr7g]
- At v0.61.0 the source of `memoryDiscovery.ts` walks upward from each trusted root to the directory containing a boundary marker (`.git` by default), or to the trusted root when none is found, and `loadJitSubdirectoryMemory` loads context files for a path a tool touched from the deepest trusted root containing it, skipping paths outside every trusted root; the file has no downward directory scan. [CODE S-bci74yyr: packages/core/src/utils/memoryDiscovery.ts#getEnvironmentMemoryPaths, loadJitSubdirectoryMemory]
- At v0.61.0 (commit `bb523741c7429a44d03e964bc124c7c92df59d5f`) the `context.discoveryMaxDirs` setting (default 200) is passed from the CLI settings into the core config, which stores it and exposes it through `getDiscoveryMaxDirs()`; a search of the `packages` tree finds no caller of that getter outside tests. The only breadth-first file search with a directory limit, `bfsFileSearch`, has no caller outside its tests either, and the one caller of its synchronous form, the path corrector for a tool's mistyped file path, passes its own fixed `maxDirs: 50`. So at this version the 200-directory limit has no consumer in the source, and no GEMINI.md scan below the working directory is limited by it. This is the implementation at one commit, not a documented promise. [CODE S-mxqyhxx7: packages/cli/src/config/config.ts#discoveryMaxDirs; S-fema44tc: packages/core/src/config/config.ts#getDiscoveryMaxDirs; S-clksl3oh: packages/core/src/utils/bfsFileSearch.ts#bfsFileSearch, bfsFileSearchSync; S-e7vrnq3a: packages/core/src/utils/pathCorrector.ts#correctPath]
- The Gemini CLI configuration page at v0.61.0 still describes a scan of subdirectories below the working directory limited to 200 directories, while the GEMINI.md page describes just-in-time loading on tool access; the source read supports the just-in-time reading, and the subdirectory-scan sentence has no implementation behind it at that commit (the setting's value is stored and never read). [DER S-mer4fr7g, S-c4vaxr7q, S-bci74yyr, S-fema44tc, S-clksl3oh: the two docs pages against the source]

### How it fits
- None of these coding agents (Claude Code, GitHub Copilot, Cursor, Codex, Gemini CLI, Aider) loads the whole repository: the durable context is small scoped instruction files plus a map of names (files, symbols, imports), and code is fetched on demand by path, symbol, grep or index query. A kb that answers questions about the products a codebase uses fits the same pattern as an on-demand tool (an MCP server or skill) rather than loaded text. [DER S1855, S-yq3633pk, S-v2sqknkh, S-c5olve2h: just-in-time retrieval, ranked maps and capped instruction files]
- Instruction-file caps and scopes differ (Codex 32 KiB combined, Cursor's 500-line advice, Gemini's 200-directory discovery, Claude Code's per-directory loading), so one AGENTS.md read by several tools stays short and points to deeper files instead of holding them. [DER S-c5olve2h, S-iuskapuz, S-mer4fr7g: the three stated limits]
- Semantic indexes differ in where code goes: GitHub Copilot's index is remote (non-GitHub repositories are uploaded), VS Code mixes local and remote, Cursor's Instant Grep index is local; a repository whose code must not leave the machine needs that checked per product. [DER S-5yij7tgr, S-v2sqknkh, S-4owuypm5: each page's statement of index location]

## Reference
- Anthropic, effective context engineering: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Aider repository map: https://aider.chat/docs/repomap.html
- GitHub Copilot repository indexing: https://docs.github.com/en/copilot/concepts/context/repository-indexing
- VS Code workspace context: https://code.visualstudio.com/docs/agents/reference/workspace-context
- Cursor search, rules, ignore file: https://cursor.com/docs/agent/tools/search, https://cursor.com/docs/rules, https://cursor.com/docs/reference/ignore-file
- Codex AGENTS.md: https://developers.openai.com/codex/guides/agents-md
- Gemini CLI GEMINI.md: https://github.com/google-gemini/gemini-cli/blob/v0.61.0/docs/cli/gemini-md.md
- Related: `claude/large-codebases.md` (Claude Code's settings for this); `agents/codebase-mapping.md` (deterministic maps from the language's own tools, LSP, ctags, Tree-sitter); `agents/docs-maintenance-agents.md` (AGENTS.md standard, Copilot instruction files); `agents/instruction-and-context-limits.md`.

## Examples
- SNIPPET: let Gemini CLI read the same AGENTS.md as other agents; context: Gemini CLI v0.61.0, `.gemini/settings.json`; checked: syntax [DOC S-c4vaxr7q, S-mer4fr7g: `context.fileName` accepts an array]
```json
{
  "context": {
    "fileName": ["AGENTS.md", "GEMINI.md"]
  }
}
```
