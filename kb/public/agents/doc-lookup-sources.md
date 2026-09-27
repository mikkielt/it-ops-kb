---
topic: agents/doc-lookup-sources
priority: P2
applies_to: "stable (GA) MCP servers and public APIs that return current official documentation for this kb's domains, as of 2026-09-25"
retrieved_utc: 2026-09-27
sources: [S2176, S2177, S2178, S2179, S2180, S2181, S2182, S2183, S2184, S2185, S2186, S2187, S2188, S2189, S2190, S2191, S2192, S2193, S2194, S2195, S2196, S2197, S1809, S-el34o4bb, S-eutmp4xp, S-j7xzzcxj, S-yuwxbqz3, S-b6tooge2, S-ybuoluc4, S-rgy4dvjf, S452, S717, S-fvspfpxd, S-pxvdwitn]
status: partial
---

# Documentation lookup sources for agents: stable MCP servers and APIs

## Summary
Three no-auth remote MCP servers cover most of this kb and are configured for every user in `.mcp.json`:
Microsoft Learn (GA, about 15 domains), Claude Code Docs and the MCP docs site. GitHub's remote MCP server
(GA, needs a token) reaches the source repositories behind many pinned artifacts and is optional. Plain APIs
(GitHub REST, Graph `$metadata`, PyPI JSON, `llms.txt`) cover scripted checks. Preview or beta servers
(GitLab MCP, Microsoft MCP Server for Enterprise) are excluded. Full table: `doc-lookup-sources.csv`.
Refreshing an existing fact still goes through `_tools/fetch.py --diff`; these servers are for finding and
reading the current page.

## Facts
- Microsoft's Learn MCP release notes record general availability on 2025-11-07, removing the preview disclaimers. [DOC S2176]
- `https://learn.microsoft.com/api/mcp` answered `initialize` as "Microsoft Learn MCP Server" 1.0.0 without authentication and lists three tools: `microsoft_docs_search`, `microsoft_docs_fetch` (page as markdown) and `microsoft_code_sample_search`. [DOC S2177]
- `microsoft_docs_search` returns up to 10 content chunks per query, per its tool description. [DOC S2177]
- The npm package `@microsoft/learn-cli` has dist-tag `latest` = 1.0.0 (published 2026-09-10); a separate `preview` dist-tag also exists and is not the stable line. [DOC S2178]
- Anthropic's Claude Code MCP quickstart uses the Claude Code documentation MCP server as its example: a hosted server with full-text search over the docs that needs no authentication. [DOC S2179]
- `https://code.claude.com/docs/mcp` lists `search_claude_code_docs`, `query_docs_filesystem_claude_code_docs` (read-only queries over a virtual docs filesystem) and `submit_feedback`, which sends a report to the docs team. [DOC S2180]
- `https://modelcontextprotocol.io/mcp` lists `search_model_context_protocol`, `query_docs_filesystem_model_context_protocol` and `submit_feedback`. [DOC S2181]
- Mintlify generates an MCP server for each hosted docs site and rate-limits it to 5,000 requests per hour per user IP address. [DOC S2182]
- The Claude Code Docs and MCP docs servers are Mintlify-generated; an agent should not call their `submit_feedback` tool unasked, because it publishes text outside the kb. [DER S2180, S2181, S2182]
- Anthropic lists `llms.txt` as the LLM-optimized documentation index under "Resources for AI ingestion"; `https://platform.claude.com/llms.txt` returned HTTP 200. [DOC S2183, S2184]
- GitHub announced the remote GitHub MCP Server as generally available on 2025-09-04. [DOC S2185]
- GitHub documents the remote MCP server setup for IDE clients, with OAuth or a personal access token. [DOC S2186]
- The remote server's documentation lists per-toolset read-only URLs of the form `https://api.githubcopilot.com/mcp/x/<toolset>/readonly`. [DOC S2187]
- GitHub's REST API allows 60 requests per hour unauthenticated and 5,000 per hour with a personal access token. [DOC S2188]
- GitLab's MCP server page shows status Beta (moved from experiment in GitLab 18.6), so it is excluded here; GitLab docs remain reachable as raw files through the GitLab REST API. [DOC S2189]
- Microsoft MCP Server for Enterprise (Graph/Entra data) is titled "(preview)" on its Learn overview page, so it is excluded. [DOC S2190]
- `https://graph.microsoft.com/v1.0/$metadata` is downloadable without authentication; `/beta` is out of scope as a preview surface. [DOC S2191]
- PyPI's JSON API (`https://pypi.org/pypi/<package>/json`) returns a project's latest-version metadata, its releases and project URLs without authentication; the `releases` key is marked deprecated in favour of the Index API, and `/pypi/<package>/<version>/json` gives one release. [DOC S2192]
- DeepWiki's MCP server is free, remote and needs no authentication, but its wikis are generated automatically from the repositories (Devin indexes them and produces the wikis), so it can only supply leads. [COMMUNITY S2193, S1809]
- Context7 indexes library docs contributed by its community and states that it cannot guarantee their accuracy. [COMMUNITY S2194]
- Context7 (Upstash) serves library docs through a remote MCP server at `https://mcp.context7.com/mcp` with two tools, `resolve-library-id` (library name to a Context7 id such as `/vercel/next.js`) and `query-docs` (docs for that id and a query), or through the `ctx7` CLI; a free API key, sent as `Authorization: Bearer`, is recommended for higher rate limits. [DOC S-eutmp4xp]
- Context7's repository (MIT) holds only the MCP server's source; its API backend, parsing engine and crawling engine are private. [DOC S-eutmp4xp]
- Anyone can add a public GitHub library to Context7 without owning it; Context7 indexes its `.md`, `.mdx`, `.rst`, `.txt` and `.ipynb` files, falls back to generating examples from source code when a public repository has little documentation, and refreshes libraries automatically "based on popularity". Private sources need a Pro or Enterprise plan. [DOC S-j7xzzcxj]
- DeepWiki's MCP server (`https://mcp.deepwiki.com/mcp`, Streamable HTTP; `/sse` is being deprecated) offers `read_wiki_structure`, `read_wiki_contents` and `ask_question` (an AI-generated answer about a GitHub repository) for public repositories only; private repositories need a Devin account and the Devin MCP server with an API key. [DOC S2193]
- Context7 and DeepWiki answer a question from content generated or crawled at query time, with no per-statement evidence level; this kb answers from facts that each carry one tag (`DOC`, `CODE`, `DER`, `COMMUNITY`, `UNK`) and a source row, so an answer drawn from either service enters this kb only as a `COMMUNITY` lead until an official page confirms it. [DER S-eutmp4xp, S-j7xzzcxj, S2193, S1809: Context7 disclaims accuracy of community-contributed docs and generates examples from code; DeepWiki's wikis and `ask_question` answers are Devin-generated]
- Scope differs: Context7 covers libraries whose docs sit in a public GitHub repository and DeepWiki covers GitHub repositories, while most of this kb's domains (ConfigMgr, Intune, Entra ID, GPO) are documented on Microsoft Learn rather than in a library repository, which the Learn MCP server already reaches as a first-party source. [DER S-j7xzzcxj, S2193, S2177]
- Microsoft Learn's terms of use limit copying and reposting of its documents, so Learn text fetched through the MCP server is paraphrased in this kb, not stored verbatim. [DOC S2195]
- The `MicrosoftDocs/memdocs` repository, source of many pinned ConfigMgr/Intune raw files in this kb, is archived (last push 2026-09-02); current ConfigMgr pages are read through Learn. [DOC S2196]
- `api.github.com/repos/microsoft/presidio` redirects (HTTP 301) to the repository now named `data-privacy-stack/presidio`. [DOC S2197]
- The Learn terms of use limit use of documents to informational, non-commercial or personal use and forbid copying or posting them on any network computer, but say certain documentation may carry explicit licence terms that control where they conflict. [DOC S2195]
- MicrosoftDocs repositories carry those explicit terms per repository, and they differ: `memdocs` grants its documentation under CC BY 4.0 and its code under MIT (README and LICENSE files), while `entra-docs` has MIT in both `LICENSE` and `LICENSE-CODE`. [DOC S-yuwxbqz3, S-b6tooge2]
- Learn pages name a private `-pr` repository as their source (`memdocs-pr`, `entra-docs-pr`), so whether a public repository's licence covers a given Learn page is inferred from the public mirror, not stated on the page. [DOC S-ybuoluc4]
- For the licence census, a Learn fact's licence class follows the public mirror's LICENSE at a pinned commit when one exists (CC BY 4.0 or MIT: copy with attribution), else the Learn terms (paraphrase, short quotes). [DER S2195, S-yuwxbqz3, S-b6tooge2: the terms defer to explicit licences]
- GitHub's documentation repository `github/docs` is dual-licensed: CC BY 4.0 for documentation and content in its `assets`, `content` and `data` folders, MIT for code. [DOC S-rgy4dvjf]
- GitLab's repository licence puts `doc/` under CC BY-SA 4.0, a share-alike licence: verbatim copies would have to carry the same licence. [DOC S452]
- The MCP repository licenses new specification contributions under Apache-2.0 (earlier unrelicensed ones stay MIT) and documentation other than the specification under CC BY 4.0. [DOC S717]
- The Claude Code docs pages end "© Anthropic PBC. All rights reserved. Use is subject to applicable Anthropic Terms of Service." [DOC S-fvspfpxd]
- Anthropic's Commercial Terms grant neither party rights to the other's content or intellectual property except as expressly stated. [DOC S-pxvdwitn]
- No open licence was found for Anthropic's docs (code.claude.com, platform.claude.com), so fetched Anthropic text is summarized in this kb, with quotes of 25 words or fewer, not stored verbatim. [DER S-fvspfpxd, S-pxvdwitn]
- A stable docs MCP server or API for Windows security baselines (Security Compliance Toolkit, DISA STIG, CIS) and for Ansible docs was not found. [UNK]

## Reference
- `doc-lookup-sources.csv`: ranked table with endpoint, auth, tools, covered domains and status evidence.
- `.mcp.json` (repository root): the three no-auth servers, shared by every user of this repo.
- `.claude/settings.json`: pre-approves those servers and denies their `submit_feedback` tools.
- `_tools/fetch.py --diff`: re-fetches the recorded sources of a topic and shows what changed.
- `agents/doc-change-detection.md`: version signals, redirects, sitemaps and archives for telling whether a cited page changed.
- Rejected: GitLab MCP server (Beta), Microsoft MCP Server for Enterprise (preview), GitHub MCP Insiders mode (early access), undocumented `platform.claude.com/docs/mcp`.
- `agents/hybrid-retrieval.md`: its Azure AI Search, Anthropic, pgvector and Elasticsearch facts were found and read through the Microsoft Learn MCP server and WebFetch listed here.

## Examples
- SNIPPET: check the shared servers connect, then add a personal read-only GitHub toolset and search Learn
  without MCP; context: Claude Code 2026-09, `.mcp.json` at repo root, `GITHUB_PAT` a personal access token
  in the caller's own environment; checked: no [DOC S2179, S2187, S-el34o4bb: `claude mcp add`
  scope/transport/header syntax, the toolset URL, and the `npx @microsoft/learn-cli search` command]
```bash
# Shared servers are in .mcp.json; check they connect
claude mcp list

# Optional, per user: GitHub read-only repository tools (token from your own environment)
claude mcp add --scope user --transport http github-repos-ro \
  https://api.githubcopilot.com/mcp/x/repos/readonly \
  --header "Authorization: Bearer $GITHUB_PAT"

# Scripted, no MCP: Learn from the command line
npx @microsoft/learn-cli search "DSC v3 resource manifest"
```
