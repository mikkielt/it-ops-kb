---
topic: agents/doc-lookup-sources
priority: P2
applies_to: "stable (GA) MCP servers and public APIs that return current official documentation for this kb's domains, as of 2026-09-25"
retrieved_utc: 2026-09-29
sources: [S2176, S2177, S2178, S2179, S2180, S2181, S2182, S2183, S2184, S2185, S2186, S2187, S2188, S2189, S2190, S2191, S2192, S2193, S2194, S2195, S2196, S2197, S1809, S-el34o4bb, S-eutmp4xp, S-j7xzzcxj, S-yuwxbqz3, S-b6tooge2, S-ybuoluc4, S-rgy4dvjf, S452, S717, S-fvspfpxd, S-pxvdwitn, S-gupervu4, S-ke227men, S-fqi6xbbc, S-autbwi4y, S-eluaxz73, S-ekcs6zhr, S-3yod3u7q, S-ehhvgjky, S742, S1824]
status: complete
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
- Context7 refresh cadence: when a library is requested and its docs are older than a popularity-based threshold, a background refresh starts: top 100 libraries after 1 day, top 1,000 after 15 days, top 5,000 after 30 days, all others after 45 days (website libraries slightly longer). [DOC S-gupervu4]
- Context7 limits: the API guide publishes no request-rate numbers ("low rate limits" without an API key) and answers an exceeded limit with `429` plus `Retry-After` and `RateLimit-*` headers [DOC S-ke227men]; the Free plan is blocked after 1,000 API calls a month (with 20 bonus calls a day while blocked), and Pro includes 2,000 calls per seat, then $5 per 1,000 [DOC S-fqi6xbbc].
- Context7 results carry source URLs: the documentation-context API returns fields described as "URL to source location" and "URL to source page", and its text output has `Source: <url>` lines. [DOC S-autbwi4y]
- DeepWiki's MCP server (`https://mcp.deepwiki.com/mcp`, Streamable HTTP; `/sse` is being deprecated) offers `read_wiki_structure`, `read_wiki_contents` and `ask_question` (an AI-generated answer about a GitHub repository) for public repositories only; private repositories need a Devin account and the Devin MCP server with an API key. [DOC S2193]
- Context7 and DeepWiki answer a question from content generated or crawled at query time, with no per-statement evidence level; this kb answers from facts that each carry one tag (`DOC`, `CODE`, `DER`, `COMMUNITY`, `UNK`) and a source row, so an answer drawn from either service enters this kb only as a `COMMUNITY` lead until an official page confirms it. [DER S-eutmp4xp, S-j7xzzcxj, S2193, S1809: Context7 disclaims accuracy of community-contributed docs and generates examples from code; DeepWiki's wikis and `ask_question` answers are Devin-generated]
- Scope differs: Context7 covers libraries whose docs sit in a public GitHub repository and DeepWiki covers GitHub repositories, while most of this kb's domains (ConfigMgr, Intune, Entra ID, GPO) are documented on Microsoft Learn rather than in a library repository, which the Learn MCP server already reaches as a first-party source. [DER S-j7xzzcxj, S2193, S2177]
- Microsoft Learn's terms of use limit copying and reposting of its documents, so Learn text fetched through the MCP server is paraphrased in this kb, not stored verbatim. [DOC S2195]
- The `MicrosoftDocs/memdocs` repository, source of many pinned ConfigMgr/Intune raw files in this kb, is archived (last push 2026-09-02); current ConfigMgr pages are read through Learn. [DOC S2196]
- `api.github.com/repos/microsoft/presidio` redirects (HTTP 301) to the repository now named `data-privacy-stack/presidio`. [DOC S2197]
- The Learn terms of use limit use of documents to informational, non-commercial or personal use and forbid copying or posting them on any network computer, but say certain documentation may carry explicit licence terms that control where they conflict. [DOC S2195]
- MicrosoftDocs repositories carry those explicit terms per repository, and they differ: `memdocs` grants its documentation under CC BY 4.0 and its code under MIT (README and LICENSE files), while `entra-docs` has MIT in both `LICENSE` and `LICENSE-CODE`. [DOC S-yuwxbqz3, S-b6tooge2]
- Learn pages name a private `-pr` repository as their source (`memdocs-pr`, `entra-docs-pr`), so whether a public repository's licence covers a given Learn page is inferred from the public mirror, not stated on the page. [DOC S-ybuoluc4]
- For the licence census, a Learn page's reuse class follows its public mirror's LICENSE when the mirror is live (CC BY 4.0 or MIT: copy with attribution), else the Learn terms (paraphrase, short quotes); an archived mirror such as `memdocs` no longer receives the page's updates, so its licence covers only the archived text and the live page falls under the Learn terms. [DER S2195, S-yuwxbqz3, S-b6tooge2, S2196: the terms defer to explicit licences; memdocs is archived]
- GitHub's documentation repository `github/docs` is dual-licensed: CC BY 4.0 for documentation and content in its `assets`, `content` and `data` folders, MIT for code. [DOC S-rgy4dvjf]
- GitLab's repository licence puts `doc/` under CC BY-SA 4.0, a share-alike licence: verbatim copies would have to carry the same licence. [DOC S452]
- The MCP repository licenses new specification contributions under Apache-2.0 (earlier unrelicensed ones stay MIT) and documentation other than the specification under CC BY 4.0. [DOC S717]
- The Claude Code docs pages end "© Anthropic PBC. All rights reserved. Use is subject to applicable Anthropic Terms of Service." [DOC S-fvspfpxd]
- Anthropic's Commercial Terms grant neither party rights to the other's content or intellectual property except as expressly stated. [DOC S-pxvdwitn]
- No open licence was found for Anthropic's docs (code.claude.com, platform.claude.com), so fetched Anthropic text is summarized in this kb, with quotes of 25 words or fewer, not stored verbatim. [DER S-fvspfpxd, S-pxvdwitn]
- Microsoft publishes security baselines through the Microsoft Download Center as the Security Compliance Toolkit zip (GPO backups, reports, spreadsheets, scripts), not through an API. [DOC S-eluaxz73] Red Hat's Ansible development tools MCP server is a Technology Preview aimed at playbook development, not a documentation lookup service. [DOC S-ekcs6zhr] No stable (GA) docs MCP server or API for Windows security baselines (SCT, DISA STIG, CIS) or for Ansible docs was found on 2026-09-27. [DER S-eluaxz73, S-ekcs6zhr: distribution channels read; absence of a GA docs server]

### Live search tools a routed lookup can call (checked 2026-09-29)
- Mintlify's generated MCP server has three tools: search (snippets with titles and links), query-docs-filesystem (shell-style reads of the site's virtual filesystem, including reads of several pages in one call) and submit-feedback; search takes optional `version` and `language` filters, and the skill.md files are exposed as MCP resources. [DOC S2182]
- Microsoft Learn's `microsoft_docs_search` returns up to 10 chunks of at most 500 tokens each with title, url and excerpt, `microsoft_code_sample_search` up to 20 samples (optional `language` filter), and `microsoft_docs_fetch` a whole page as Markdown, so a search adds at most about 5,000 tokens of tool result. [DOC S2177] [DER S2177: 10 x 500 tokens]
- Claude Code's `WebSearch` tool runs a query on Anthropic's web search backend and returns titles and urls only; it does not fetch the pages, so reading one takes a `WebFetch` call. One call may issue up to eight backend searches. [DOC S-3yod3u7q]
- A Claude Code session may make at most 200 `WebSearch` calls, counted across subagents (v2.1.212 or later, `CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION` raises it); permission rules for `WebSearch` take no specifier, and the tool is available on the Claude API but not on Amazon Bedrock. [DOC S-3yod3u7q]
- `WebFetch` asks for a url and a prompt and runs the prompt over the page with a small fast model, so it is lossy; it truncates large pages, caches a response 15 minutes, fails a page not downloaded within five minutes (v2.1.268 adds `CLAUDE_CODE_WEBFETCH_DEADLINE_MS`) and refuses hostnames without a dot. [DOC S-3yod3u7q]
- In Manual and `acceptEdits` permission modes `WebFetch` prompts before a fetch except for a built-in set of preapproved documentation domains and domains a rule allows; the page does not list that set, and an explicit `WebFetch(domain:...)` rule overrides it. [DOC S-3yod3u7q] [UNK: whether Microsoft Learn or the Claude and MCP docs hosts are in the preapproved set]
- `WebSearch` and `WebFetch` both need approval in a permission-prompting mode, and `-p` has no terminal to answer, so a headless researcher lists them in `--allowedTools` (which allows them without prompting and does not restrict which tools exist) or runs under a mode that skips the prompt. [DER S-3yod3u7q, S742, S1824: the prompt table and the `-p` no-TTY rule]

### What the three docs endpoints answer over plain HTTP (unauthenticated probe, 2026-09-29)
- A POST of `initialize` (protocol version `2025-11-25`, `Accept: application/json, text/event-stream`) to `https://learn.microsoft.com/api/mcp` was answered with protocol version `2025-06-18`, as `Content-Type: text/event-stream` holding one `event: message` block, and with an `mcp-session-id` header. A `tools/list` POST sent without that header was also answered `200`, so the server did not require the session id. [DER S2177: the request and the response headers seen; the version answer follows the negotiation rule in mcp/transports-streamable-http.md]
- The same probe against `https://code.claude.com/docs/mcp` and `https://modelcontextprotocol.io/mcp` was answered with protocol version `2025-11-25`, as `text/event-stream` with one `event: message` block, and with no session-id header; `tools/list` to the Claude Code endpoint answered `200` without a prior `initialize`. `curl` with its default user agent was accepted by both. Re-run on 2026-10-02 with `curl` 8.7.1 on macOS, the `initialize` response of both endpoints again carried protocol version `2025-11-25` and a `serverInfo` of name `Claude Code Docs` or `Model Context Protocol` with version `1.0.0`; the date of the run is what dates a live endpoint's answer. [DER S2180, S2181: the request and the response seen]
- All three responses carry `Cache-Control` values that forbid storing them (`no-cache, no-store` for Learn; `no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0` for the Claude Code endpoint; `no-cache, no-transform` for the MCP endpoint), so the responses give a client no lifetime to reuse for a search POST: a local cache keys on the server and the request body and picks its own lifetime. [DER S2177, S2180, S2181: the header values seen]

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
