---
topic: agents/agent-planning-and-done
priority: P3
applies_to: "planning multi-session agent work and deciding when a task is done: Scrum Guide 2020, Anthropic long-running harness guidance (2025-11-26), Claude Code best practices and /goal (retrieved 2026-09-28), Kanban Guide v2025.5 (retrieved 2026-10-08)"
retrieved_utc: 2026-10-08
sources: [S-2wwcyoa4, S2150, S-o3v6ozch, S-vp5onm7b, S1896, S-v2ztgtdn, S-cbzadytw]
status: complete
---

# Planning agent work and its definition of done

## Summary
Scrum's Definition of Done is one shared quality bar that every item must meet before it counts as delivered; work below it goes back to the backlog. Anthropic's guidance for long-running agents turns that into files an agent reads each session: a JSON feature list whose entries start failing and flip to passing only after end-to-end tests, a progress file, git history, and an init script. Claude Code's best practices add the other half: give the agent a check that returns pass or fail, separate exploring and planning from coding, and let something other than the working agent decide it is done (a `/goal` evaluator, a Stop hook, or a fresh reviewer subagent).

## Facts
- The Definition of Done is a formal description of the state of the Increment when it meets the product's quality measures; the moment a Product Backlog item meets it, an Increment is born. [DOC S-2wwcyoa4]
- An item that does not meet the Definition of Done cannot be released or even presented at the Sprint Review; it returns to the Product Backlog. Work cannot be part of an Increment unless it meets the Definition of Done. [DOC S-2wwcyoa4]
- An organisation's Definition of Done is the minimum for all its Scrum Teams; without one, the team creates one for the product; several teams on one product share and comply with the same one. [DOC S-2wwcyoa4]
- Each Scrum artifact carries a commitment against which progress is measured: the Product Goal for the Product Backlog, the Sprint Goal for the Sprint Backlog and the Definition of Done for the Increment. [DOC S-2wwcyoa4]
- In Sprint Planning, Developers plan the work to create an Increment that meets the Definition of Done, often by decomposing backlog items into work items of one day or less; the Retrospective inspects the Definition of Done among other things. [DOC S-2wwcyoa4]
- The Product Backlog is an emergent, ordered list of what is needed to improve the product and the single source of work for the Scrum Team; items the team can make Done within one Sprint are ready for selection at Sprint Planning. [DOC S-2wwcyoa4]
- Product Backlog refinement breaks items down into smaller, more precise items and adds details such as a description, order and size; the Developers who will do the work size it. [DOC S-2wwcyoa4]
- The Sprint Backlog holds the Sprint Goal (why), the selected Product Backlog items (what) and an actionable plan for the Increment (how), and is updated through the Sprint as more is learned. [DOC S-2wwcyoa4]
- The Sprint Goal is the single objective for the Sprint; if the work turns out different than expected, the scope of the Sprint Backlog is renegotiated without changing the Sprint Goal. [DOC S-2wwcyoa4]
- Sprints are fixed-length events of one month or less, and a new Sprint starts immediately after the previous one ends. [DOC S-2wwcyoa4]
- The 2020 Scrum Guide names no epics, user stories, tasks or subtasks and no velocity or story points: a backlog item's type and hierarchy are outside the guide. Those levels come from tools and frameworks, for example GitLab's epic, issue and task hierarchy (`gitlab/work-items-planning.md`). [DER S-2wwcyoa4, S-v2ztgtdn: none of the terms occurs in the guide's text, read 2026-09-28; GitLab's child item hierarchy]
- A goal-bounded Sprint (one that ends when its goal is met rather than at a fixed date) departs from the Scrum Guide's fixed length; what it keeps is the Sprint Goal as the single commitment, with the Definition of Done as the quality bar. [DER S-2wwcyoa4: fixed length versus the Sprint Goal commitment]
- The 2020 Scrum Guide has no term "spike" and no rule that research or unknowns are ordered before the work that depends on them: it says the Scrum Team is responsible for all product-related activities including "experimentation, research and development", and treats Product Backlog order as an emergent matter for the Product Owner. A research task ahead of dependent work is a team convention, not a Scrum rule. [DER S-2wwcyoa4: no occurrence of "spike" in the guide's text, and the quoted activities list, read 2026-09-29]
- The 2020 Scrum Guide does not use the term "acceptance criteria": it defines one Definition of Done shared by all items, and item-specific conditions are outside the guide. [DER S-2wwcyoa4: no occurrence of "acceptance" in the guide's text, read 2026-09-28]
- The Product Goal is the Scrum Team's long-term objective, kept in the Product Backlog; the team must fulfill (or abandon) one objective before taking on the next, and the rest of the Product Backlog emerges to define what will fulfill it. [DOC S-2wwcyoa4]
- Done in Scrum is an outcome, not an activity: to provide value the Increment must be usable, each Increment is additive to all prior ones and thoroughly verified, and the Sprint Review inspects the outcome of the Sprint. [DOC S-2wwcyoa4]
- The Product Owner is accountable for Product Backlog management, which includes ordering its items and keeping it transparent, visible and understood. [DOC S-2wwcyoa4]
- The 2020 Scrum Guide has no "Definition of Ready" and no work-in-progress limit: its only readiness rule is that items the team can make Done within one Sprint are ready for selection, and it bounds work per Sprint through the Sprint Goal and the Sprint's fixed length rather than through a count. [DER S-2wwcyoa4: no occurrence of "Definition of Ready", "WIP" or "work in progress" in the guide's text, read 2026-10-08]
- The Kanban Guide (v2025.5) requires a Definition of Workflow (DoW) with at least: what the work items are, when an item counts as started and finished, the states between them (items between started and finished are work in progress, WIP), how WIP is controlled, explicit policies for flow through each state, and a service level expectation. [DOC S-cbzadytw]
- Kanban system members must explicitly control the number of work items between started and finished; controlling WIP should create a pull system, so new work is selected only on a clear signal of capacity (for example WIP dropping below the control), and not beyond the WIP control. Exceptions must be explicit in the DoW. [DOC S-cbzadytw]
- The service level expectation is a forecast of how long an item takes from started to finished, in two parts, a period and a probability (the guide's example: "85% of work items will be finished in eight days or less"), based on historical cycle time; active management keeps items from ageing unnecessarily against it. [DOC S-cbzadytw]
- The Kanban Guide's four mandatory flow metrics are WIP (items started but not finished), Throughput (items finished per unit of time, an exact count), Work Item Age (time since an item started) and Cycle Time (time from start to finish). [DOC S-cbzadytw]
- Neither guide caps the size of the backlog itself: Kanban's WIP control counts only items between started and finished, and Scrum's Product Backlog is emergent and ordered. A backlog that grows because every review finding becomes an item is therefore bounded by what may start (a WIP control or Sprint Goal), by an explicit entry policy for when an item may start (Kanban's started point and policies; Scrum's "ready for selection"), by a done that is an outcome (a usable, verified Increment), and by ordering, which leaves low-value items unstarted. [DER S-cbzadytw, S-2wwcyoa4: WIP counts started to finished; the Product Backlog is emergent and ordered by the Product Owner; Increment must be usable]
- Anthropic saw two failure modes when an agent ran across many context windows from a high-level prompt: it tried to one-shot the whole app and ran out of context mid-feature, and a later session saw progress and declared the job done. [DOC S2150]
- The fix was an initializer session that writes an `init.sh`, a `claude-progress.txt` log and an initial git commit, then coding sessions that each make incremental progress and leave structured updates; both used the same system prompt, tools and harness, only a different first prompt. [DOC S2150]
- The initializer expands the prompt into a JSON feature list (over 200 entries for the example app), each with `category`, `description`, `steps` and `passes: false`; coding agents may only change `passes`. JSON was chosen because the model is less likely to overwrite it inappropriately than Markdown. [DOC S2150]
- Coding agents work on one feature at a time, commit with descriptive messages and write a progress summary, leaving a clean state: code fit to merge to a main branch, with no major bugs and no unrelated mess for the next session. [DOC S2150]
- Without explicit prompting the agent marked features complete after unit tests or `curl` calls although the feature did not work end to end; prompting it to test as a human user would, with browser automation, fixed most of this. [DOC S2150]
- Each coding session starts by getting its bearings: `pwd`, the git log and progress file, the feature list (pick the highest-priority unfinished feature), then `init.sh` and a basic end-to-end test before any new work, so a broken state is found before it is built upon. [DOC S2150]
- Claude Code best practices: Claude stops when work looks done, so give it a check that returns pass or fail (tests, a build exit code, a linter, a fixture diff, a screenshot comparison) and let it iterate until the check passes; "if you can't verify it, don't ship it". [DOC S-o3v6ozch]
- The same page lists four ways to gate the stop: ask in the prompt; a `/goal` condition re-checked after every turn; a Stop hook that runs the check as a script and blocks the turn from ending; or a verification subagent or workflow so the working agent is not the one grading itself. [DOC S-o3v6ozch]
- Recommended workflow: explore (plan mode), plan, implement while verifying against the plan, commit. Planning pays when the approach is uncertain, several files change or the code is unfamiliar; if the diff fits in one sentence, skip the plan. [DOC S-o3v6ozch]
- Before counting unattended work as done, a subagent in a fresh context reviews the diff against the plan and reports gaps; since a reviewer asked for gaps usually finds some, it should flag only gaps that affect correctness or the stated requirements. [DOC S-o3v6ozch]
- `/goal <condition>` is a session-scoped prompt-based Stop hook: after each turn a small fast model (Haiku by default on the Claude API) returns met, not met or impossible, with a reason; met or impossible clears the goal. It is unavailable when `disableAllHooks` is true. [DOC S-vp5onm7b]
- The `/goal` evaluator does not run commands or read files: it judges only what Claude surfaced in the conversation. A durable condition has one measurable end state, a stated check (for example "`npm test` exits 0") and the constraints that must not change; it can be up to 4,000 characters, and a turn or time clause bounds it. [DOC S-vp5onm7b]
- If Claude keeps answering the `/goal` evaluator without tool use for several turns, Claude Code stops the loop and returns control with the goal still set. [DOC S-vp5onm7b]
- A definition of done for one agent subtask can be written as three parts: the end state, the command whose output proves it (so a transcript-only judge such as `/goal` can see it), and what must not change; the project's shared gate (for this kb, `kb/_self/maintaining.md`'s gate) is the Scrum-style minimum every subtask meets as well. [DER S-2wwcyoa4, S-vp5onm7b, S-o3v6ozch: shared Definition of Done as the minimum; `/goal`'s end state, check and constraints]
- A task list an agent keeps across sessions is safest as structured data it may only flip from failing to passing after an end-to-end check, with the failing state as the default; a status in prose invites the "declared done early" failure. [DER S2150, S-o3v6ozch]
- Anthropic's eval guidance to start with 20 to 50 tasks drawn from real failures (`agents/agent-evaluation.md`) applies to a done check as well: a planted failure per gate shows the gate can fail. [DER S1896: start small from real failures; applied to gate tests]

## Reference
| Failure | Setup (initializer) | Every session (coding agent) | Source |
|---|---|---|---|
| declares the project done too early | JSON feature list, all failing | read it; pick one feature | S2150 |
| leaves bugs or undocumented progress | git repo and progress notes | read notes and git log, run a basic test; end with a commit and a progress update | S2150 |
| marks features done without testing | feature list | mark passing only after careful end-to-end testing | S2150 |
| spends time working out how to run the app | `init.sh` | start by running `init.sh` | S2150 |

| DoD part | Question it answers | Example |
|---|---|---|
| End state | what exists when done | `querylog.py learn` writes a findings file |
| Check | which command proves it | `python3 _tools/tests.py` passes, including the planted-failure test |
| Constraints | what must not change | `kb_hook.py` latency; no file outside the listed ones |

See also `gitlab/work-items-planning.md` (GitLab's epic, issue and task hierarchy, blocking links, iterations, priority and severity labels), `agents/agent-evaluation.md` (graders, eval sets), `claude/hooks.md` (Stop hooks), `agents/headless-agent-runtimes.md` (unattended runs), `agents/anthropic-materials.md` (the post index).

## Examples
- SNIPPET: a `/goal` condition with an end state, a check and a constraint; context: Claude Code with `/goal` (hooks not disabled); checked: no [DER S-vp5onm7b: the three parts of an effective condition and the turn clause]
```text
/goal python3 _tools/tests.py exits 0 and python3 _tools/check.py prints errors=0, with no file changed outside _tools/querylog.py and _tools/test_querylog.py, or stop after 30 turns
```
