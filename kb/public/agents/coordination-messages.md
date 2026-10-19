---
topic: agents/coordination-messages
priority: P2
applies_to: "Anthropic engineering posts on context engineering, multi-agent research and tool writing; Claude Code subagents, agent teams and costs docs (2026-10); A2A spec 1.0.0 for message parts (see agents/a2a-protocol.md)"
retrieved_utc: 2026-10-19
sources: [S1855, S1921, S1935, S-wf2dmtu6, S-qdxfqzln, S2132, S2157]
status: complete
---

# What a message between agents holds, how parallel agents avoid duplicate work, and what coordination costs

## Summary

Vendor guidance converges on one shape for a message between agents: the receiver starts with only what the message
(or spawn prompt) holds, so a brief carries the objective, output format, tool and source guidance and task
boundaries, and a reply carries a condensed summary plus references to stored output, not the raw work. Duplicate
research is prevented in Anthropic's own system by the lead's decomposition of the task, because its subagents
cannot coordinate; Claude Code's agent teams add a shared task list with claim locking and ask for work split by
file or by lens. Coordination is paid for in tokens at every recipient: each teammate or subagent has its own
context window, loads its own startup context, and its brief and returned summary land in a window. Typed
(structured) results between agents are covered for A2A in `agents/a2a-protocol.md` and for MCP tools in
`agents/subagents-vs-deterministic-tools.md`.

## Facts

### What a message to or from an agent should hold
- In Anthropic's context-engineering guidance a sub-agent may explore with tens of thousands of tokens but "returns only a condensed, distilled summary of its work (often 1,000-2,000 tokens)"; the detailed search context stays in the sub-agent and the lead synthesizes. [DOC S1855]
- The same guidance calls tool result clearing, dropping the raw result of a tool call made deep in the history, "one of the safest lightest touch forms of compaction", and advises tuning a compaction prompt first for recall, then for precision by cutting superfluous content. [DOC S1855]
- Anthropic's tool-writing guidance says a tool should return only high-signal information, and that resolving opaque identifiers such as UUIDs to meaningful names or a 0-indexed scheme "significantly improves Claude’s precision in retrieval tasks by reducing hallucinations". [DOC S1935]
- The same post suggests a `response_format` enum, "allowing your agent to control whether tools return “concise” or “detailed” responses", so a caller asks for identifiers only when a later call needs them. [DOC S1935]
- A Claude Code subagent starts with a fresh conversation: it does not see the parent's turns, only its final response returns, and the parent's context grows by that summary, not by the subtask transcript, so the delegation prompt is the only task context the subagent gets. [DOC S-wf2dmtu6]
- An agent-team teammate loads the project's CLAUDE.md, MCP servers and skills and receives the lead's spawn prompt; the lead's conversation history does not carry over, so the spawn prompt holds the task-specific details. [DOC S-qdxfqzln]
- When a teammate stops, it notifies the lead automatically and the notification includes the teammate's final answer, so the lead need not poll. [DOC S-qdxfqzln]
- Anthropic's Research system says subagents work as compression: each explores in its own context window and condenses "the most important tokens for the lead research agent". [DOC S1921]
- A message one agent sends another should hold, to keep the receiver's context small: the goal in a sentence, the boundary (what is out of scope and who covers it), the output format, pointers to inputs as paths, ids or urls rather than pasted content, and a return of a short summary plus pointers to anything stored. This follows from a receiver that sees only the message, a window that every token depletes, and the references-not-copies pattern. [DER S1921, S1855, S-wf2dmtu6: the receiver starts empty, so inputs travel as pointers and results return condensed]

### How parallel agents avoid duplicating each other's research
- In Anthropic's Research system the lead decomposes the query and each subagent needs an objective, an output format, guidance on tools and sources and clear task boundaries; vague one-line tasks made agents perform "the exact same searches as other agents" (the example is in `agents/subagents-vs-deterministic-tools.md`). [DOC S1921]
- Anthropic's post says that system executes subagents synchronously and that "the lead agent can’t steer subagents, subagents can’t coordinate", while asynchronous execution would add parallelism but also coordination, state-consistency and error-propagation problems. [DOC S1921]
- Because those subagents cannot see each other's work, avoiding duplicates there rests on how the lead divides the task before dispatch and not on any exchange between them. [DER S1921: the post names no cross-subagent deduplication mechanism, and says subagents cannot coordinate]
- Claude Code's subagent docs advise parallel subagents for independent investigations: each explores its own area and Claude synthesizes, which "works best when the research paths don't depend on each other". [DOC S2157]
- In an agent team the lead creates tasks in a shared list; a task is pending, in progress or completed, and a pending task with unresolved dependencies cannot be claimed until they are completed. Work is assigned by the lead or self-claimed by a teammate that takes the next unassigned, unblocked task. [DOC S-qdxfqzln]
- The agent-teams docs give two ways to keep teammates apart: a code-review prompt "assigns each teammate a distinct lens so they don't overlap", and for edits "each teammate owns a different set of files", since two teammates editing one file overwrite each other. [DOC S-qdxfqzln]
- The docs warn that more teammates means more communication, task coordination and chance of conflicts, with diminishing returns, and suggest starting with 3-5 teammates; they suggest new users begin with tasks with clear boundaries that do not write code, such as reviewing a PR or researching a library. [DOC S-qdxfqzln]
- No official source read here describes a shared record of searches already made (a ledger agents consult before searching) as a way to avoid duplicate research; the documented mechanisms are the lead's division of labour, the task list and file or lens ownership (searched 2026-10-16: the Anthropic multi-agent, context-engineering and tool-writing posts, and the Claude Code subagents and agent-teams pages; see `_gaps.md`). [DER S1921, S2157, S-qdxfqzln: absence across the pages searched]

- The agent-teams page says task claiming "uses file locking to prevent race conditions when multiple teammates try to claim the same task simultaneously", so two teammates cannot both take one task from the shared list. [DOC S-qdxfqzln]
- The same page lists as a limitation that "teammates sometimes fail to mark tasks as completed, which blocks dependent tasks", and tells the user to check whether the work is done and update the status by hand or nudge the teammate. [DOC S-qdxfqzln]
- The agent-teams page read 2026-10-19 names a lock on the claim but no expiry, lease or heartbeat for it (the words "expire" and "lease" are absent), so a claim whose holder stops is cleared by a person or the lead, not by a timeout; whether a stopped teammate's claimed task returns to pending is the open question in `_gaps.md`. [DER S-qdxfqzln: absence across the page text, with the stuck-task limitation above]
- Anthropic's Research system graded each output with one LLM judge against a rubric of five criteria: factual accuracy, citation accuracy, completeness, source quality and tool efficiency ("did it use the right tools a reasonable number of times?"). [DOC S1921]
- None of those five criteria counts work repeated between subagents, and the post gives the duplication it saw as one example from its simulations (one subagent on the 2021 automotive chip crisis, two others on 2025 supply chains), with no rate. The nearest published measure is tool-call count, which the post lists beside token use and model choice among the factors behind BrowseComp performance. [DER S1921: the rubric criteria and the example read 2026-10-19; no duplicate-work metric on the page]

### What coordination costs in tokens
- Claude Code's cost page says each teammate has its own context window and "token usage scales with the number of active teammates and how long each one runs"; the agent-teams page adds that token costs scale linearly with team size. [DOC S2132, S-qdxfqzln]
- The cost page's levers for teams: use Sonnet for teammates, keep teams small, keep spawn prompts focused because "everything in the spawn prompt adds to their context from the start", and shut teammates down when done since "each active teammate continues consuming tokens until it exits or the session ends". [DOC S2132]
- An in-process teammate's requests fall outside the main conversation's cache TTL bucket, so its prompt cache holds for five minutes by default; the `subagentPromptCacheTtl` setting set to `1h` keeps it for an hour, and the API bills 1-hour cache writes at a higher rate. [DOC S-qdxfqzln]
- Subagent results return to the main conversation, and the docs warn that "Running many subagents that each return detailed results can consume significant context, and each subagent spends tokens of its own while it runs". [DOC S2157]
- A subagent's own requests count toward the same usage limits as the main conversation, so offloading verbose output saves the main window, not the account's spend; choosing a smaller model for the subagent is the documented way to spend less. [DOC S2157, S2132]
- Subagent descriptions are in the parent's context, and when the combined descriptions of non-built-in subagents "exceed 15,000 tokens" Claude Code warns at startup; the docs move detail into each subagent's system prompt, which loads only when it runs. [DOC S2157]
- Each recipient therefore costs a fixed startup context (CLAUDE.md, MCP servers, skills, system prompt) plus the brief, plus its own work, plus the returned summary in the caller's window; a team of N pays the first three N times and a subagent fleet pays the last once per return. [DER S2132, S2157, S-qdxfqzln, S-wf2dmtu6: startup context and brief are charged to each new window; only the summary enters the caller's]

## Reference

| item | value | source |
|---|---|---|
| sub-agent return size named by Anthropic | "often 1,000-2,000 tokens" after tens of thousands explored | S1855 |
| teammate startup context | CLAUDE.md, MCP servers, skills, spawn prompt; no lead history | S-qdxfqzln |
| subagent startup context | own system prompt, project context; no parent turns | S-wf2dmtu6 |
| in-process teammate cache TTL | 5 minutes default; `subagentPromptCacheTtl` `1h` | S-qdxfqzln |
| subagent descriptions warning | combined over 15,000 tokens | S2157 |
| suggested team size | 3-5 teammates | S-qdxfqzln |
| brief contents, references instead of copied output | `agents/subagents-vs-deterministic-tools.md` (QG13) | see that article |
| attention budget | `agents/instruction-and-context-limits.md` | see that article |
| token multipliers of agents and multi-agent systems | `agents/subagents-vs-deterministic-tools.md` | see that article |
| agent-team cost multiplier and cost measurement | `agents/agent-cost-governance.md` | see that article |
| typed results over A2A | `agents/a2a-protocol.md` | see that article |
| typed results over MCP | `mcp/tools.md`, `agents/subagents-vs-deterministic-tools.md` | see those articles |
| messaging between sessions | `claude/cross-session-messaging.md` | see that article |

## Examples

A lead asks three subagents to check a fleet's patch state, each over its own slice of devices (the first slice
starting at `PL-LT-00123`), with the output format and the boundary stated in each brief. Each subagent writes its
findings to a file in a shared directory and returns a two-line summary and the file path; the lead reads the files
only for the slices that report a failure. The slices keep the subagents from repeating each other's checks, and the
lead's window holds three short summaries, not three transcripts [DER S1921, S2157: division of labour in the brief,
references returned].
