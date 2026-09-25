# Plan: further token optimization (decided 2026-09-25, not started)

Decided: implement everything below. It builds on `token-usage-report.md` (measurements, and changes A-G already done) and on web and Claude Code docs research from 2026-09-25 (sources at the end).

Principle: deterministic tools answer; the agent picks a tool, checks the verdict and writes the reply.

The numbers that matter are measured in a **host project that uses the kb as a plugin**, not only in this repo. The reference scenario is a developer whose TypeScript MCP server talks to MECM and AD. They install `it-ops-kb` as a plugin, look up facts while coding, and later run a review skill (T13).

Read `MAINTAINING.md` before changing anything. Every task ends with the full gate:
- `check.py`, `build_index.py --check`, `kbgit.py fix --check`;
- `tests.py`, and `stress_test.py` if `_tools/` changed;
- `fetch.py --offline`;
- `rag.py eval` at 100%.

## What the implementer must know first

- **Where guidance reaches.**
  - In a clone of this repo, `CLAUDE.md` imports `AGENTS.md`.
  - In a host project that uses the plugin, `AGENTS.md` and `MAINTAINING.md` never load; only the host's own `CLAUDE.md` does.
  - The plugin reaches a host session only through: the `kb` server's instructions (always loaded), skill and agent names and descriptions (always loaded), and skill and agent bodies (loaded when used).
  - Any rule a host must follow goes there.
- **No `rag.py` in a host.** The plugin copy lives under `~/.claude/plugins/cache/...`, so `python3 _tools/rag.py` does not resolve from the host's directory. In a host, the kb MCP tools are the only lookup interface. Nothing reached from the plugin may depend on a `rag.py` path.
- **Plugin MCP tools are deferred** (tool search). The first kb call in a session costs an extra round trip to load the tool schema. See T3.
- **Subagents inherit the `AGENTS.md` their parent loaded at session start.** After changing `AGENTS.md`, start a new session before measuring. The 2026-09-25 re-measurement shows the effect (subagents -13%, fresh sessions -74%).
- **Fixed context.** A clone session starts at about 41.2k tokens, almost all of it Claude Code's own system prompt and tool definitions. The only large lever left is a lean custom agent (T1).
- **Plugin agent limits.** Plugin agents honour `name`, `description`, `model`, `effort`, `maxTurns`, `tools`, `disallowedTools`, `skills`, `memory`, `background`, `omitClaudeMd`, `isolation`, `color` and `experimental.cacheTtl`. They ignore `permissionMode`, `hooks`, `mcpServers` and `initialPrompt`.
- **Bare mode.** `claude -p --bare` skips installed plugins. Scripts must pass `--plugin-dir <path>` or `--mcp-config` explicitly, and bare mode needs an API key.

## Tasks, in order

### T1. Lean kb-lookup subagent

Create **.claude/agents/kb-lookup.md** (new file). Frontmatter:
- `name: kb-lookup`
- `description`: "Multi-part research in the it-ops-kb documentation (facts, not live device or directory data). For a single fact call kb_pack directly instead of this agent."
- `tools`: only the kb MCP tools: `mcp__plugin_it-ops-kb_kb__kb_pack`, `…kb_facts`, `…kb_audit`, `…kb_source`, `…kb_show`, `…kb_status`. No Bash: in a host, Bash would run in the host's repo, and `rag.py` is not there.
- `model: haiku`, `effort: low`, `maxTurns: 6`, `omitClaudeMd: true`, `skills: [kb-lookup]` (preloads the procedure).
- Body (the system prompt): the lookup procedure from `/kb-lookup` in a few lines, and "answer in at most N lines, cite path:line and url".

Ship it from the plugin with `"agents": ["./.claude/agents/kb-lookup.md"]` in `.claude-plugin/plugin.json`. The path list keeps the kb's `agents/` article directory out of the plugin. Update `test_no_default_agents_scan` and the README runbook to match.

To decide while implementing: in a clone the `kb` MCP server is not configured (only the plugin declares it), so the agent's MCP tool names would not resolve there. Recommended: run clone sessions with the plugin loaded from the working tree (`claude --plugin-dir .`, or a local marketplace add and install), so the same tool names exist in both places. Verify this, and check that no tool is loaded twice.

Acceptance: record the agent's startup context in a fresh session (the transcript's first request). The hypothesis is under 10k tokens, against 50k for the general-purpose agent. Record the real number in `token-usage-report.md`.

`experimental.cacheTtl`: leave unset. Set `1h` only if measurement shows the agent is spawned repeatedly with gaps over 5 minutes, because 1-hour cache writes cost more.

### T2. Put the guidance where the plugin reaches

- `kb_mcp.py` `INSTRUCTIONS`: add "Single facts: call kb_pack yourself. Use the kb-lookup agent only for multi-part research. Never start a general-purpose agent for a kb lookup."
- Start every kb tool description with "Documentation facts from it-ops-kb (not live device or directory data)". A host's own MECM/AD MCP server returns live data. Without the prefix, names like `kb_audit` invite the wrong tool choice.
- Check every text the plugin ships (server instructions, tool descriptions, the `/kb-lookup` skill, the agent) for `rag.py` references. Keep them only where marked "in a clone".

### T3. `kb_pack` always loaded

Add `"_meta": {"anthropic/alwaysLoad": true}` to the `kb_pack` entry only, in `TOOL_LIST` in `kb_mcp.py`. The other kb tools stay deferred.

Acceptance: in a host session, the first kb lookup happens without a ToolSearch call. Always-on cost: about 150 tokens.

### T4. Batch pack

`kb_pack` accepts `questions` (a list of 1-6) as well as `question`.
- It returns one result: a section per question with its own `coverage:` verdict, and one shared sources footer.
- `rag.py pack` accepts `-q` more than once.
- `/kb-lookup` and the agent: a multi-part question is one batch call.

Acceptance: the T4 scenario (Kerberos CLI to AdminService and SQL) takes 3 turns or fewer in a fresh session. It took 6 on 2026-09-25.

### T5. `response_format` on kb tools

`concise` or `detailed`, as Anthropic's tool-design guidance recommends:
- **concise**: fact lines with `path:line` and tag, no url footer, no article flags.
- **detailed**: the current output.

Defaults:
- `kb_pack`: `detailed`, because answers need urls, and making the agent resolve them costs a turn.
- `kb_facts`, `kb_audit`, `kb_search`: `concise`.
- The review (T13) asks for `detailed`.

Acceptance: `rag.py eval` unchanged; `kb_facts` output on `agents` at least 30% smaller.

### T6. Keep editing skills out of every session (clone only)

Set `disable-model-invocation: true` on `/kb-setup`, `/kb-research`, `/kb-refresh`, `/kb-add-topic`, `/kb-census`, `/kb-verify` and `/kb-git-sync`. Their descriptions (about 3 KB) then leave the skill listing; people still run them by name.

This does not affect hosts: the plugin ships only `/kb-lookup`.

Acceptance: `/context` in a clone shows the smaller skill listing, and `test_skills_well_formed` still passes.

### T7. Split the plugin: kb and docs

The marketplace gets two plugins:
- `it-ops-kb`: the `kb` server, `/kb-lookup`, the kb-lookup agent, the `kb:` hook.
- `it-ops-kb-docs`: the three documentation servers (`microsoft-learn`, `claude-code-docs`, `mcp-docs`) and the PreToolUse hook that blocks `submit_feedback`.

Why: in a host, the docs servers add their names and instructions to every session. A MECM/AD developer usually wants `microsoft-learn` but not the other two, and may already have it configured (which duplicates it).

To verify first: whether a root `.mcp.json` still loads into the kb plugin when `plugin.json` declares `mcpServers`. The current test says the root `.mcp.json` loads into the plugin. If it does, the docs plugin needs its own directory as its marketplace `source`. Pick a directory name that `test_no_default_agents_scan` does not forbid.

Update:
- `marketplace.json`, both manifests and `test_kb_mcp.py` (`PluginManifest`);
- the README runbook ("Use from another project");
- `claude plugin validate` must pass for both plugins.

### T8. Low effort only on the lookup agent

`effort: low` goes in the agent (T1), never in the `/kb-lookup` skill. Skill frontmatter effort overrides the host's session effort while the skill runs, which would lower the quality of a coding session's synthesis.

### T9. One line from the hook when the kb does not cover a question

In `_tools/kb_hook.py`, for `coverage: none`, set `additionalContext` to one line instead of the pack: "it-ops-kb has no coverage for: <missing words>; say so and add nothing from memory".

Keep the early exit: a prompt without `kb:` must return before loading `kbfacts`. The hook runs on every host prompt (about 50 ms).

Test: extend `Lookup.test_kb_hook`.

### T10. Product-alias table

Add **_tools/aliases.csv** with columns `term,canonical` and one row per alias. Seed rows:
- `sccm`, `memcm`, `mecm`, `configmgr`, `configuration manager` -> configmgr
- `azure ad`, `aad`, `entra id`, `entra` -> entra
- `endpoint manager`, `mem`, `intune` -> intune
- `group policy`, `gpo` -> gpo
- `administration service`, `adminservice` -> adminservice
- `windows laps`, `laps` -> laps
- `defender for endpoint`, `mde` -> defender
- `dsc v3`, `dsc` -> dsc
- `active directory`, `ad ds`, `ad` -> ad

In `kbfacts.pack`:
- expand query terms to their canonical form and every alias before scoring;
- expansions must not count as extra key words in the coverage verdict (the lesson of the "Wi-Fi" bug);
- `check.py` or a test checks the CSV shape.

Acceptance: new eval rows phrased with aliases (e.g. "SCCM AdminService Kerberos", "Azure AD PIM groups writeback") pass; all existing rows still pass.

### T11. Retrieval weighting (stdlib only; no embeddings, no model reranking)

Anthropic's contextual retrieval prepends document context to each chunk. The deterministic part here:
- index each article's Summary text into its fact units at a lower weight;
- give the title double weight.

Accept only if `rag.py eval` stays at 100% and the mean pack size does not grow.

### T12. `kb_topics_for`: code signals to topics (deterministic, supports T13)

Add `rag.py topics-for PATH... | --keywords ...` and the MCP tool `kb_topics_for`.
- Input: file paths or text from a host repository.
- Output: ranked kb topics with the signals that matched.
- Signals: a curated `signals` list per topic, e.g.
  - `msal`, `PublicClientApplication` -> `auth/msal-public-client`
  - `AdminService`, `/AdminService/wmi/` -> `mecm/adminservice`
  - `ldap3`, `ldaps` -> `auth/ldap-smb-signing`
  - Graph permission scope names -> `graph/permissions`
  - `CMPivot` -> `mecm/cmpivot`
  - `Negotiate`, `SPN`, `kinit` -> `auth/kerberos`
- The signals live in the topics' front matter or in a CSV under `_tools/`; decide which, and keep `build_index.py` in step.
- In a host, the tool reads the paths the agent passes, not the host repository directly.

### T13. `/kb-review-workspace` (plugin, read-only)

Reviews a host workspace (e.g. the TypeScript MCP server for MECM/AD) against the kb.

Skill (new directory `.claude/skills/kb-review-workspace/`):
- `disable-model-invocation: true` (no always-on cost; the user starts it);
- it runs in the agent below, so reading the host's code stays out of the main session;
- output is a report in chat only; no file written in the host.

New plugin agent, `kb-reviewer` (new file **.claude/agents/kb-reviewer.md**). It has the opposite settings to the lookup agent:
- `tools`: `Read`, `Grep`, `Glob` plus the kb MCP tools;
- `model: sonnet`, `effort: medium`;
- `omitClaudeMd` **not** set: the host's `CLAUDE.md` describes its architecture;
- `maxTurns` about 25;
- flow: `kb_topics_for` on the host's files, then `kb_facts` / `kb_pack` with `response_format: detailed` per topic, then findings with `path:line` in the host plus the kb citation.

Invariants to update:
- `test_only_the_read_only_skill` allows exactly the two plugin skills;
- no `Write`, `Edit` or git in any plugin `allowed-tools`;
- `plugin.json` lists both agent files.

Add the skill to the `AGENTS.md` skills list (the test requires it).

### T14. Measure in a host project

Build a throwaway host directory outside the repo:
- `git init`;
- a short `CLAUDE.md` describing "a TypeScript MCP server for MECM and AD";
- 3-5 `.ts` files that call the AdminService with Negotiate, use MSAL, query LDAP and request Graph scopes.

Load the plugin with `--plugin-dir <this repo>` and record:
- `claude plugin details it-ops-kb` (the always-on cost);
- `/context` in an interactive session (MCP tools, agents, skills lines);
- the six questions from `token-usage-report.md`, each with `claude -p "<question>" --model sonnet --output-format json`: turns, input tokens, output tokens, time;
- one `/kb-review-workspace` run: turns, tokens, and whether the findings cite both the host line and the kb.

Compare the same questions in this repo. Put the results in `token-usage-report.md` under a new section.

Method notes from the 2026-09-25 runs:
- Allow the Skill tool, or the old procedure wastes a turn on a denied call.
- Compare token counts, not dollars: cost depends on which run in a batch pays the cache write.
- Start each batch from a fresh session.

## Watch, do not adopt yet

- API `search_result` content blocks give native citations from tool results. They are not part of MCP, and one report says the Agent SDK drops them from MCP tool results (issue linked below). Revisit when MCP or Claude Code supports them.
- `--bare` is to become the default for `claude -p`. After that, scripts that expect the plugin must pass `--plugin-dir`.

## Sources (read 2026-09-25)

- Claude Code docs:
  - subagents, frontmatter reference: https://code.claude.com/docs/en/sub-agents
  - plugin agent fields: https://code.claude.com/docs/en/plugins/components
  - manifest path fields: https://code.claude.com/docs/en/plugins/manifest-reference
  - features overview (what loads when): https://code.claude.com/docs/en/features-overview
  - MCP tool search and `alwaysLoad`: https://code.claude.com/docs/en/mcp
  - costs: https://code.claude.com/docs/en/costs
  - prompt caching: https://code.claude.com/docs/en/prompt-caching
  - headless and bare mode: https://code.claude.com/docs/en/headless
  - system prompt flags: https://code.claude.com/docs/en/cli-reference
  - plugin cost measurement: https://code.claude.com/docs/en/plugins/measure
  - agent loop (effort, tool scoping): https://code.claude.com/docs/en/agent-sdk/agent-loop
- Anthropic engineering:
  - writing tools for agents (`response_format`, truncation defaults): https://www.anthropic.com/engineering/writing-tools-for-agents
  - effective context engineering: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
  - code execution with MCP (150k to 2k tokens): https://www.anthropic.com/engineering/code-execution-with-mcp
  - contextual retrieval: https://www.anthropic.com/engineering/contextual-retrieval
- Claude Platform:
  - search results: https://platform.claude.com/docs/en/build-with-claude/search-results
  - Agent SDK issue on dropped `search_result` blocks: https://github.com/anthropics/claude-agent-sdk-python/issues/574
