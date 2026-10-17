---
topic: agents/agent-troubleshooting-method
priority: P3
applies_to: "a troubleshooting method for agentic work: Google's Site Reliability Engineering book (2017), chapters 12 (Effective Troubleshooting) and 15 (Postmortem Culture); DORA's 2024 Accelerate State of DevOps report and 2025 State of AI-assisted Software Development report; Claude Code best practices, troubleshooting and configuration debugging pages (retrieved 2026-10-15)"
retrieved_utc: 2026-10-17
sources: [S-bykh7vnm, S-u2rergzb, S-2k5yy4cc, S-acskf4b2, S-xyroxc3f, S-hs7ypnlx, S-o3v6ozch, S-odq4ke5n, S-aqddt7m6, S-aishnkok, S-qulnsg4e, S-qdxfqzln, S2157, S1921]
status: complete
---

# A troubleshooting methodology for agentic work: SRE troubleshooting, blameless postmortems and DORA on AI-assisted delivery

## Summary
Google's Site Reliability Engineering (SRE) book treats troubleshooting as the hypothetico-deductive method run as a loop: a problem report (expected, actual, how to reproduce), triage that stops the bleeding first, examining metrics, logs and exposed state, diagnosing by simplifying, asking what and where, and looking at what changed last, then testing hypotheses one at a time with notes, and a cure that ends in a postmortem. Its postmortems are blameless: they look for contributing causes in systems and processes, not culprits, and every one is reviewed and shared. DORA's research finds that AI adoption raises individual productivity, but in 2024 it went with lower delivery throughput and stability, and in 2025 with higher throughput and still lower stability: AI amplifies a team's existing strengths and weaknesses, so automated tests, version control and small batches are the safety nets. For a coding agent, Claude Code's own guidance supplies the matching moves: correct early, rewind, clear the context after two failed corrections, and isolate configuration with `/context`, `--safe-mode` and `--debug`.

## Facts
### Troubleshooting (SRE book, chapter 12)
- Google's Site Reliability Engineering (SRE) book frames troubleshooting as the hypothetico-deductive method: from observations of a system and a theory of how it works, iteratively hypothesize causes of the failure and test them. [DOC S-bykh7vnm]
- The chapter's model runs from a problem report through triage, examine, diagnose, and test and treat, to a cure; the book holds that troubleshooting is learnable and teachable, and that it works best with both a generic method and solid knowledge of the system. [DOC S-bykh7vnm]
- A problem report should state the expected behaviour, the actual behaviour and, if possible, how to reproduce it; Google opens a bug for every issue, which leaves a searchable log of investigation and remediation. [DOC S-bykh7vnm]
- Triage sizes the response to the impact and first makes the system work as well as it can (divert traffic, drop load, disable subsystems): stopping the bleeding comes before root-causing, while evidence such as logs is preserved. [DOC S-bykh7vnm]
- Examine uses three tools: time-series metrics, logs and request tracing, and endpoints that expose a server's current state (recent requests, error and latency histograms). The book warns that false correlations in graphs can lead down wrong paths. [DOC S-bykh7vnm]
- Diagnose, generic practices: simplify and reduce by checking the data flowing between components, working from one end of the stack to the other or, in large systems, by bisection, which halves the system and repeats on the faulty half. [DOC S-bykh7vnm]
- Diagnose also asks "what", "where" and "why" of a malfunctioning system, which is often still doing something, just not the wanted thing, and starts from what touched it last: recent changes are a productive place to begin. [DOC S-bykh7vnm]
- Test and treat: an ideal test has mutually exclusive alternatives, so it rules one group of hypotheses in and another out; tests run in decreasing order of likelihood, weighing the risk each test poses to the system. [DOC S-bykh7vnm]
- Experiments can mislead through confounding factors, active tests can have side effects that change later results (verbose logging can worsen a latency problem), and some tests are only suggestive, not definitive. [DOC S-bykh7vnm]
- Take clear notes of the ideas, the tests run and the results seen; in long cases they keep a responder from repeating steps. [DOC S-bykh7vnm]
- Negative results (an experiment where the expected effect is absent) should not be ignored or discounted: they are conclusive, and the book asks for them to be published. [DOC S-bykh7vnm]
- Cure: proving a cause by reproducing it at will is often not possible in production, so responders often find only probable causal factors; several factors may cause a failure only jointly, and systems are path-dependent. [DOC S-bykh7vnm]
- Once the causal factors are found, the responders write up what went wrong, how they tracked it down, how they fixed it and how to prevent a recurrence: a postmortem. [DOC S-bykh7vnm]
- The chapter's common pitfalls: looking at irrelevant symptoms or misreading metrics, not knowing how to change the system safely to test a hypothesis, improbable theories or latching on to causes of past problems, and hunting spurious correlations. [DOC S-bykh7vnm]

### Blameless postmortems (SRE book, chapter 15)
- A postmortem is a written record of an incident: its impact, the actions taken to mitigate or resolve it, the root causes and the follow-up actions that prevent a recurrence. [DOC S-u2rergzb]
- Its goals are that the incident is documented, all contributing root causes are understood, and effective preventive actions reduce the likelihood or impact of a recurrence. [DOC S-u2rergzb]
- Common triggers: user-visible downtime or degradation beyond a threshold, data loss of any kind, on-call intervention (rollback, rerouting traffic), a resolution time above a threshold, and a monitoring failure; criteria are set before an incident, and any stakeholder may ask for a postmortem. [DOC S-u2rergzb]
- A blameless postmortem identifies the contributing causes without indicting any individual or team for bad or inappropriate behaviour, and assumes everyone acted with good intentions on the information they had. [DOC S-u2rergzb]
- Blame does harm: where finger pointing prevails, people hide issues for fear of punishment, and an atmosphere of blame lets incidents be swept under the rug. Postmortems look for why someone had incomplete or incorrect information and fix systems and processes, not people. [DOC S-u2rergzb]
- A blameless postmortem still calls out where and how services can be improved; the book contrasts a finger-pointing complaint with the same proposal written as a constructive action item. [DOC S-u2rergzb]
- Review: the first draft goes to senior engineers, who check that key incident data was collected, the impact assessment is complete, the root cause is deep enough, the action plan and bug priorities fit, and the outcome was shared. "An unreviewed postmortem might as well never have existed." [DOC S-u2rergzb]
- Reviewed postmortems are shared as widely as useful and added to a team or organisation repository of past incidents; Google aggregates them with tools to find common themes across products. [DOC S-u2rergzb]
- The culture is kept up by visible rewards and practices such as a postmortem of the month, postmortem reading clubs and the Wheel of Misfortune, which re-enacts a past postmortem with engineers in the roles. [DOC S-u2rergzb]

### DORA on AI-assisted software development
- DORA's 2024 report: more than 75 percent of respondents rely on AI for at least one daily professional responsibility, most often writing code, summarising information and explaining code. [DOC S-2k5yy4cc]
- In the 2024 data, a 25% increase in AI adoption went with gains of 7.5% in documentation quality, 3.4% in code quality and 3.1% in code review speed (estimates). [DOC S-2k5yy4cc]
- In the 2024 data, as AI adoption increased, delivery throughput fell by an estimated 1.5% and delivery stability by an estimated 7.2%; DORA reads this as a sign that a better development process does not improve delivery without basics such as small batches and robust testing. [DOC S-2k5yy4cc]
- In 2024, 39% of respondents reported little to no trust in AI-generated code. [DOC S-2k5yy4cc]
- DORA's 2024 report page: AI adoption significantly increases individual productivity, flow and job satisfaction, but harms software delivery stability and throughput, so small batch sizes and robust testing remain crucial. [DOC S-xyroxc3f]
- The 2025 DORA report (State of AI-assisted Software Development, announced 2025-09-23) draws on survey responses from nearly 5,000 technology professionals and over 100 hours of qualitative data; its central finding is that AI amplifies what a team already has, strengths and weaknesses alike. [DOC S-acskf4b2]
- In 2025, unlike 2024, AI adoption had a positive relationship with software delivery throughput and product performance, and still a negative relationship with software delivery stability. [DOC S-acskf4b2]
- DORA's 2025 reading: without robust control systems (strong automated testing, mature version control, fast feedback loops) a higher change volume leads to instability; loosely coupled teams with fast feedback gain, tightly coupled ones with slow processes see little or no benefit. [DOC S-acskf4b2]
- In 2025, 90% of respondents used AI at work, more than 80% believed it raised their productivity, and 30% reported little or no trust in AI-generated code. [DOC S-acskf4b2]
- The 2025 research identified seven capabilities that magnify AI's positive impact (the DORA AI Capabilities Model); DORA advises treating AI adoption as an organisational transformation. [DOC S-acskf4b2]
- DORA's capability catalogue tags seven capabilities as AI ones: AI-accessible internal data, clear and communicated AI stance, healthy data ecosystems, platform engineering, user-centric focus, version control, and working in small batches. [DOC S-hs7ypnlx]
- DORA's catalogue calls version control a critical safety net as AI speeds up the velocity of change, and small batches the counter to AI-driven instability through shorter lead times and faster feedback. [DOC S-hs7ypnlx]

### Debugging a coding agent (Claude Code)
- Claude Code best practices: correct Claude as soon as it goes off track. `Esc` stops it mid-action with context kept; `Esc` twice or `/rewind` restores earlier conversation and code; `/clear` resets context between unrelated tasks. [DOC S-o3v6ozch]
- After more than two corrections on the same issue in one session, the context is cluttered with failed approaches: `/clear` and start fresh with a more specific prompt that carries what was learned. [DOC S-o3v6ozch]
- The page's common failure patterns, each with its fix: the kitchen-sink session (`/clear` between tasks), correcting over and over (clear after two failed corrections), the over-specified CLAUDE.md (prune, or turn a rule into a hook), the trust-then-verify gap (always provide verification), and infinite exploration (scope it, or use subagents). [DOC S-o3v6ozch]
- Checkpoints let an agent try something risky: if it does not work, rewind and try a different approach. [DOC S-o3v6ozch]
- Claude Code troubleshooting: `/doctor` runs an automated check of the installation, settings, extensions and context usage and offers fixes; `claude doctor` runs from the shell when `claude` does not start, and `/mcp` shows MCP server status. [DOC S-odq4ke5n]
- `/context` shows what occupies the context window (system prompt, tools, MCP tools, subagents, memory files, skills, messages); if a file loaded but an instruction is still not followed, the issue is likely how it is written. [DOC S-aqddt7m6]
- `claude --safe-mode` turns off CLAUDE.md, skills, plugins, hooks, MCP servers, custom commands and agents, output styles and keybindings (managed hooks and settings policy still apply); a problem that disappears there lies in one of the items turned off. [DOC S-aqddt7m6]
- `claude --debug` writes a debug log that records each hook event, the matchers checked and the hook's exit code and output; `claude --debug=mcp` puts an MCP server's stderr in the log at `~/.claude/debug/<session-id>.txt`. [DOC S-aqddt7m6]

### Troubleshooting a multi-agent run (Claude Code and Anthropic's Research system)
- In agent view a session is `blocked` only when it waits on you (a question, a permission or sandbox decision, an error only you can clear such as an expired login), `working` while a turn or a self-driven step such as a `/loop` iteration or a CI wait runs, and `done` when the last turn finished; `waitingFor` names the open prompt. A session in `working` for long is therefore not waiting on you. [DOC S-aishnkok]
- To see what a parallel agent is doing before stopping it: `claude logs <id|name>` prints a background session's recent output, `/workflows` shows an agent's prompt, recent tool calls (with their state) and result, a teammate's transcript opens from the agent panel, and a subagent's transcript opens from `/tasks`. [DOC S-aishnkok, S-qulnsg4e, S-qdxfqzln, S2157]
- A workflow agent whose output stops arriving restarts by itself from the same prompt (shown as `(retry 1)`, at most five restarts) and then fails the `agent()` call; the stall window is lengthened per agent with `stallMs` or for all agents with `CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS`. [DOC S-qulnsg4e]
- Anthropic's Research post found that users reporting "not finding obvious information" could not be diagnosed until it added full production tracing, which showed whether agents used bad queries, chose poor sources or hit tool failures. [DOC S1921]
- A stuck or looping parallel agent maps onto the SRE loop as: report (which agent, its state and last output), triage (stop that agent, not the whole run, and keep its transcript), examine (its transcript and tool calls, the brief it was given), diagnose (a vague brief explains duplicated work, a missing stop condition or cap explains runaway spawning, a failed tool or an unanswered permission prompt explains a hang) and treat (fix the brief or the cap, then resume the same agent or start a replacement). [DER S-bykh7vnm, S-aishnkok, S-qulnsg4e, S-qdxfqzln, S1921: the SRE steps applied to the states, transcripts and failure causes the vendor pages name]
- Duplicated work between parallel agents is diagnosed from the briefs, not from the agents: Anthropic traced it to short instructions without a division of labour, and the fix it gives is a brief with an objective, output format, tool guidance and task boundaries; for teammates editing one file the Claude Code fix is a file partition. [DER S1921, S-qdxfqzln: both pages name the cause and fix; the common diagnosis is derived]

### How it fits a coding agent's failures
- The SRE loop maps onto a failed agent task: the report is the failing check's output (expected, actual, the command that reproduces it); triage is stopping or rewinding the agent before root-causing, keeping the transcript as evidence; examine is `/context`, the debug log and the transcript; diagnose starts from what changed last (the last edit, a new CLAUDE.md rule, plugin or hook) and bisects the configuration with `--safe-mode`. [DER S-bykh7vnm, S-o3v6ozch, S-aqddt7m6: SRE steps and pitfalls; Claude Code's stop, rewind, `/context`, safe mode and debug log]
- Test and treat for an agent is one change per attempt in a fresh session, with notes of what was tried: Claude Code's "two failed corrections, then `/clear`" rule is the agent-side form of the SRE book's notes and negative results, a failed approach carried into a new prompt as a result rather than left in the context. [DER S-bykh7vnm, S-o3v6ozch]
- A blameless postmortem of an agent failure looks for the contributing causes in the system around the agent (the prompt, the context it had, its tools, a missing check) and fixes those, for example with a hook or a done check, rather than re-prompting the same session; this follows the SRE book's "fix systems and processes" and Claude Code's advice to turn a repeated rule into a hook and to always provide verification. [DER S-u2rergzb, S-o3v6ozch]
- DORA's findings put the stabilisers outside the agent: AI-generated change volume raises instability unless automated tests, version control and small batches hold, which is the same pass-or-fail check and small, separately verified items that `agents/agent-planning-and-done.md` asks of agent work. [DER S-acskf4b2, S-hs7ypnlx, S-o3v6ozch]

## Reference
| SRE step | What it asks | For a coding agent | Source |
|---|---|---|---|
| Problem report | expected, actual, how to reproduce | the failing check's command and output | S-bykh7vnm |
| Triage | stop the bleeding, keep evidence | `Esc`, `/rewind`; keep the transcript | S-bykh7vnm, S-o3v6ozch |
| Examine | metrics, logs, exposed state | `/context`, `claude --debug`, `/doctor`, `/mcp` | S-bykh7vnm, S-aqddt7m6, S-odq4ke5n |
| Diagnose | simplify, what/where/why, what touched it last, bisection | the last edit or config change; `--safe-mode`, clean config | S-bykh7vnm, S-aqddt7m6 |
| Test and treat | mutually exclusive tests, likeliest first, notes | one change per attempt; `/clear` after two failed corrections | S-bykh7vnm, S-o3v6ozch |
| Cure | probable cause, then a postmortem | a blameless postmortem; fix the harness (hook, check) | S-bykh7vnm, S-u2rergzb |

See also `agents/agent-planning-and-done.md` (definition of done, pass-or-fail checks, the declared-done-early failure), `agents/agent-evaluation.md` (eval sets from real failures), `agents/test-suite-size-and-agent-overengineering.md` (the SRE book on testing), `claude/hooks.md` (hooks and their debug output).

## Examples
- SNIPPET: a problem report for a failed agent task, in the SRE book's expected, actual and reproduce form; context: any coding agent with a pass-or-fail check; checked: no [DER S-bykh7vnm: the three parts of an effective problem report]
```text
Expected: python3 _tools/check.py prints errors=0 after the edit to kb/public/agents/example.md
Actual:   errors=1, "sources: header lists S-00000000, which the body does not cite"
Reproduce: python3 _tools/check.py
Last change: the agent removed the only fact citing S-00000000
```
