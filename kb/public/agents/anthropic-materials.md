---
topic: agents/anthropic-materials
priority: P2
applies_to: "Anthropic engineering blog, docs and reference repositories, retrieved 2026-09-25"
retrieved_utc: 2026-09-27
sources: [S2137, S2138, S2139, S2140, S2141, S2142, S2143, S2144, S2145, S2146, S2147, S2148, S2149, S2150, S2151, S2152, S2153, S2154, S2156, S2157, S2158, S2159, S-d5e5aem4]
status: complete
---

# Index of Anthropic materials for agent/MCP work

## Summary

The full row-per-item index with dates and one-line reasons is `agents/anthropic-materials.csv`. This file only records how the index was built and its coverage limits. The engineering blog index page (fetched 2026-09-25) listed 25 posts from 2024-09-19 to 2026-04-23; all 25 are rows in the CSV, plus the cookbook and courses repositories and three docs sections, for 30 rows total [DOC S2137]. No copying of prose beyond the title occurred; each CSV row states its own one-line reason in this session's words.

## Facts

- The engineering index groups naturally into the topics the assignment asked for: agents (`building-effective-agents`, `multi-agent-research-system`, `managed-agents`, `harness-design-long-running-apps`, `effective-harnesses-for-long-running-agents`), tools (`writing-tools-for-agents`, `advanced-tool-use`, `desktop-extensions`), context engineering (`effective-context-engineering-for-ai-agents`, `contextual-retrieval`), evals (`demystifying-evals-for-ai-agents`, `eval-awareness-browsecomp`, `AI-resistant-technical-evaluations`, `infrastructure-noise`), code execution with MCP (`code-execution-with-mcp`), Claude Code best practices and safety (`claude-code-best-practices`, `claude-code-sandboxing`, `claude-code-auto-mode`, `april-23-postmortem`, `a-postmortem-of-three-recent-issues`, `how-we-contain-claude`), and skills (`equipping-agents-for-the-real-world-with-agent-skills`) [DOC S2137].
- The cookbook repository (`anthropics/anthropic-cookbook`, now redirecting to `anthropics/claude-cookbooks` under the title Claude Cookbooks; MIT licence) has directories directly useful to tool/MCP/eval work: `claude_agent_sdk/`, `patterns/agents/`, `tool_use/`, `tool_evaluation/`, `misc/prompt_caching.ipynb`, `evals/agentic_search/`, `misc/building_evals.ipynb`, `cost_optimization/`, `skills/`; newer top-level directories include `managed_agents/` and `observability/` [DOC S-d5e5aem4].
- `anthropics/courses` is a separate reference repository of five courses (API fundamentals, an interactive prompt-engineering tutorial, real-world prompting, prompt evaluations, tool use); the owner archived it on 2026-09-15, so it is read-only and no longer updated [DOC S2156].
- Two Claude Code docs sections (`sub-agents`, `skills`) were fetched directly and confirmed live on 2026-09-25; a third (`prompt-caching`) is linked from the costs page fetched for the caching topic [DOC S2157,S2158,S2159].
- Each post's own page, read 2026-09-27, shows the date the CSV gives it: `contextual-retrieval` 2024-09-19, `building-effective-agents` 2024-12-19, `claude-think-tool` 2025-03-20, `multi-agent-research-system` 2025-06-13, `desktop-extensions` 2025-06-26, `writing-tools-for-agents` 2025-09-11, `effective-context-engineering-for-ai-agents` 2025-09-29, `equipping-agents-for-the-real-world-with-agent-skills` 2025-10-16, `claude-code-sandboxing` 2025-10-20, `code-execution-with-mcp` 2025-11-04, `advanced-tool-use` 2025-11-24, `effective-harnesses-for-long-running-agents` 2025-11-26, `demystifying-evals-for-ai-agents` 2026-01-09, `harness-design-long-running-apps` 2026-03-24, `claude-code-auto-mode` 2026-03-25, `managed-agents` 2026-04-08. [DOC S2146, S2138, S2147, S2139, S2148, S2141, S2142, S2143, S2151, S2144, S2149, S2150, S2145, S2153, S2154, S2152]
- The `claude-code-best-practices` post url now redirects (HTTP 308) to the Claude Code docs page "Best practices for Claude Code" (`code.claude.com/docs/en/best-practices`), which shows no publication date; the CSV's 2025-04-18 comes from the engineering index. [DOC S2140, S2137]
- The "how we contain Claude across products" post is flagged as "(Featured)" on the index with no date shown; it is included in the CSV with `date: unknown (featured slot)` [DOC S2137].

## Reference

See `agents/anthropic-materials.csv` for the full table (title, url, kind, date, topics, why it matters).

## Examples

Not applicable — this is a materials index, not a fact set about the fixture estate.
