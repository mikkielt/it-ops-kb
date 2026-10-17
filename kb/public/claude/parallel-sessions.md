---
topic: claude/parallel-sessions
priority: P3
applies_to: "Claude Code docs: run agents in parallel, agent view (research preview), worktrees, dynamic workflows, agent teams (experimental), subagents; retrieved 2026-10-16"
retrieved_utc: 2026-10-17
sources: [S-76oyiuez, S-qulnsg4e, S-aishnkok, S-j22fjuka, S-qdxfqzln, S-wzatkg4o, S-hvuk3dqt, S2157, S-sdxhnx3i, S-2ip5zngf, S-eumxht6x]
status: partial
---

# Parallel work in Claude Code: which option fits which coordination need

## Summary
Claude Code documents five ways to work on several tasks at once (subagents, agent view, agent teams, dynamic
workflows, projects) and three supporting tools (worktrees, cross-session messaging, `/batch`). They differ in who
coordinates (Claude in one conversation, you, a lead agent, a script), where intermediate results live, whether the
workers can talk to each other, whether they edit isolated copies of the files, and whether they run on one machine
or beyond it. Agent view puts each background session's edits in its own git worktree before it writes
(`worktree.bgIsolation` turns that off); agent teams do not isolate teammates, so their files are partitioned by
hand; a dynamic workflow holds the plan in a script instead of in Claude's context. Only cross-session messaging
(over Remote Control) and projects reach other machines or the cloud; agent view, agent teams, worktrees and
workflows run on the machine that started them. Each kind has its own way to be watched and stopped (agent view,
`/tasks`, the agent panel, `/workflows`) and its own record of what a stop leaves behind: a transcript for every
kind, a worktree only where one was made.

## Facts
### The options and what each is for
- The parallel-work page names five approaches (subagents, agent view, agent teams, dynamic workflows, projects) and says they differ in how involved you stay and in whether the work runs on your machine or in the cloud. [DOC S-76oyiuez]
- Subagents are delegated workers inside one session that do a side task in their own context and return a summary; the page's use case is a side task that would flood the main conversation with search results, logs or file contents. [DOC S-76oyiuez]
- Agent view (`claude agents`, research preview) is one screen to dispatch and monitor background sessions; the page's use case is several independent tasks you hand off, checking status at a glance and stepping in only when one needs you. [DOC S-76oyiuez]
- Agent teams are multiple coordinated sessions with a shared task list and inter-agent messaging, managed by a lead; they are experimental and disabled by default, and fit work Claude should split, assign and keep in sync. [DOC S-76oyiuez]
- Projects are one ongoing conversation at claude.ai/code or in the desktop app in which Claude starts parallel threads in the cloud or, when asked, on your computer through Remote Control; the page names them public beta on Pro and Max and for work that spans days or weeks and should keep running when your machine is off. [DOC S-76oyiuez]
- Dynamic workflows are a script that runs many subagents and cross-checks their results; the page's use cases are a job that outgrows a handful of subagents or needs findings verified against each other: a codebase-wide audit, a 500-file migration, cross-checked research, a plan drafted from several angles. [DOC S-76oyiuez]
- Worktrees, cross-session messaging and `/batch` are listed as supporting tools, not ways to run agents; `/batch` is a skill that splits one large change into 5 to 30 worktree-isolated subagents, a packaged use of subagents and worktrees. [DOC S-76oyiuez]
- A background Bash command spawns no agent; a forked subagent (`/subtask`) is a subagent that inherits the whole conversation, and `/fork` copies the session into a new background session; a routine runs a session on a schedule in the cloud, not in parallel on your machine. [DOC S-76oyiuez]
- In every approach the workers are Claude sessions; a different tool is exposed to Claude as an MCP server. Running several sessions or subagents at once multiplies token usage. [DOC S-76oyiuez]

### Choosing by coordination need
- Who coordinates: Claude inside one conversation (subagents), you handing off tasks and checking back (agent view), Claude as lead planning, assigning and supervising workers (agent teams), or a script that holds the plan instead of Claude's turn-by-turn judgment (dynamic workflows). [DOC S-76oyiuez]
- Whether workers talk to each other: cross-session messaging passes findings between sessions you run yourself, agent-view sessions included; subagents report only to the conversation that spawned them; agent-view sessions report results only to you; teammates message each other directly and share a task list when they have the Task tools. [DOC S-76oyiuez]
- Whether tasks touch the same files: isolate with worktrees, which subagents and sessions you run yourself can each use; agent teams do not put teammates in worktrees, so the work is partitioned so each teammate owns different files. [DOC S-76oyiuez]
- The agent-teams page warns that two teammates editing the same file leads to overwrites and advises splitting the work by file set. [DOC S-qdxfqzln]
- To check on running work: `claude agents` for background sessions, the @-mention typeahead and `/tasks` for subagents and other background items of the current session, `/workflows` for dynamic workflows; `/agents` is a separate command that points to subagent file locations. [DOC S-76oyiuez]

### What each one shares or isolates
- Each subagent starts with a fresh, isolated context window that does not see the conversation history, the skills already invoked or the files already read; a fork is the exception, inheriting the whole conversation. [DOC S2157]
- An agent teammate has its own context window and loads the same project context as a regular session (CLAUDE.md, MCP servers, skills) plus the lead's spawn prompt, but not the lead's conversation history. [DOC S-qdxfqzln]
- Teammates share a task list (for agents with the Task tools) and message each other by name; the task list directory persists locally, is never uploaded, and the team config directory is removed when the session ends. [DOC S-qdxfqzln]
- Agent-team limits: one team per session (a team cannot be shared across sessions), no nested teams, a fixed lead, and no restoring of in-process teammates by `/resume` or `/rewind`. [DOC S-qdxfqzln]
- A worktree gives a session its own files and branch but shares the repository's `.git` directory, project-scope plugins, and permission approvals (a "don't ask again" rule from a worktree session is saved to the main checkout's `.claude/settings.local.json`, since v2.1.211). [DOC S-j22fjuka]
- A worktree session also reads the main checkout's untracked project skills, agents and commands when its own checkout has no such directory (skills need v2.1.277+). [DOC S-j22fjuka]
- A subagent run with `isolation: worktree` gets a temporary worktree that is removed when it finishes without changes; it takes its starting instructions from the main conversation and does not load the `CLAUDE.md` or `.claude/rules/` at the worktree's root when the worktree is in the default location. [DOC S-j22fjuka]
- The workflows page compares four options by who holds the plan: subagents (a worker Claude spawns; Claude decides turn by turn; results in Claude's context), skills (instructions Claude follows; results in Claude's context), agent teams (a lead supervising peers; results in a shared task list) and workflows (a script the runtime executes; results in script variables). [DOC S-qulnsg4e]
- The same table gives the scale as a few delegated tasks per turn for subagents and skills, a handful of long-running peers for teams and dozens to hundreds of agents per run for workflows, and the interruption behaviour as a restarted turn for subagents and skills, teammates that keep running for teams and a run resumable in the same session for workflows. [DOC S-qulnsg4e]

### Agent view and worktree isolation
- A session dispatched from agent view or started with `claude --bg` starts in the working directory and, before it edits files, is moved into an isolated git worktree under `.claude/worktrees/`, so parallel sessions can read the same checkout but each writes to its own. [DOC S-aishnkok]
- Once the session is in its worktree, Claude Code enforces worktree isolation for the session and for the subagents it spawns; a subagent inherits the session's working directory, so its edits land in that worktree, and `isolation: worktree` (frontmatter or at spawn) gives it a separate one. [DOC S-aishnkok]
- Claude skips the worktree when the session was moved to the background from an open session with `←` or `/background`, when the session is already inside a linked git worktree (Claude's or one made with `git worktree add`), when the edited file is inside a linked worktree, when the directory is not a git repository and no `WorktreeCreate` hook is set, or when the write is outside the working directory. [DOC S-aishnkok]
- `worktree.bgIsolation` takes `"worktree"` (the default: Claude Code blocks `Edit` and `Write` in the main checkout until the session calls `EnterWorktree`) or `"none"` (background jobs edit the working copy directly); the page sets `"none"` for a repository where worktrees are impractical, and a session moved to the background with `←` or `/background` edits in place whatever the key says. [DOC S-wzatkg4o]
- The changelog lists `worktree.bgIsolation: "none"` as added in v2.1.143. [DOC S-hvuk3dqt]
- With `"none"`, with a failed worktree move, or in a session started inside an existing worktree, a session editing a checkout it did not isolate itself still asks before committing or switching branches. [DOC S-aishnkok]
- Outside a git repository sessions write to the working directory and are not isolated from each other, so the page advises against dispatching parallel sessions that edit the same files; another version control system is covered by a `WorktreeCreate` hook. [DOC S-aishnkok]
- Inside a git repository, a session that Claude moves into a worktree cannot use `Edit`, `Write` or `NotebookEdit` on the shared checkout until the move happens. [DOC S-aishnkok]
- Claude Code checks four things while a session is isolated: edits that target the main checkout, a command whose working directory resolves to it, git redirected into it (`git -C`, `--git-dir`, `GIT_DIR`, `cd`), and a command whose text does not show that its git stays inside the worktree; none of them tracks what a shell command writes, so `cp` or a redirect into the main checkout is not refused by them. [DOC S-j22fjuka]
- For a background session's changes in a worktree it entered, Claude is told to commit without asking, push the branch when a remote exists and open a draft pull request when the task calls for it, and never to push to `main` or `master`, force-push or merge; the user's own git instructions take precedence. [DOC S-aishnkok]
- Deleting a session in agent view removes the worktree Claude created for it unless a kept case applies, so changes are committed first; a periodic sweep removes subagent and background-session worktrees older than `cleanupPeriodDays` except those that still hold work, and a `git worktree lock` protects a worktree while its agent runs. [DOC S-j22fjuka]

### Seeing and stopping running parallel work
- In agent view, `Ctrl+X` on a selected session stops it and a second `Ctrl+X` within two seconds deletes it; on a group header it deletes every session in the group after confirmation, and a stop that fails (for example because the background service does not respond) does not block the delete. [DOC S-aishnkok]
- A reply to a session from agent view's peek panel that is exactly `/stop` stops the session at once instead of being delivered, whether the session is working or waiting on you; for a shell job the reply goes to the command's terminal as typed input. [DOC S-aishnkok]
- Detaching never stops a background session: `←`, `Ctrl+Z`, `/exit` and a double `Ctrl+C` or `Ctrl+D` all leave it running, and `/stop` ends a session from inside it. [DOC S-aishnkok]
- From a shell, `claude agents` lists background sessions, `claude logs <id|name>` prints a session's recent output, `claude attach <id|name>` opens it, `claude stop <id>` stops it (`claude kill` is accepted), and `claude respawn <id>` restarts a running or stopped session. [DOC S-aishnkok]
- `claude agents --json` is the page's supported way to read session state from a script: each background session has a `state` of `working`, `blocked`, `done`, `failed` or `stopped`, and a live process has a `status` of `busy`, `waiting` or `idle` plus a `waitingFor` such as `permission prompt` or `input needed`; the files under `~/.claude/jobs/<id>/` are not a stable interface. [DOC S-aishnkok]
- Agent view shows `Stopped` for a session you stopped with `Ctrl+X` or `claude stop`, whose process was ended from outside Claude Code, or that ended while the background service was off; a session whose process exits unexpectedly is restarted by the supervisor, but ending one you backgrounded yourself with `←` or `/background` (for example with `kill`) marks it stopped instead. [DOC S-aishnkok]
- `claude daemon stop --any` stops the supervisor and the background sessions it hosts, and `--keep-workers` leaves the sessions running for the next supervisor; on macOS and Linux a session's process waits about a minute for a new supervisor and stops if none comes, which is why the page says to run `claude agents` within that minute after a stall. [DOC S-aishnkok]
- When attaching, peeking or `claude logs` reports that the background service did not respond, the page treats the supervisor as stalled and gives `claude daemon stop --any --keep-workers` followed by `claude agents` as the recovery; on Windows a supervisor that ignores the stop request needs `taskkill /PID <pid>`. [DOC S-aishnkok]
- Deleting a session stops the background shell commands, workflows and background subagents it carried over; `CLAUDE_CODE_DISABLE_BG_EXIT_HANDOFF=1` makes them stop with the session's process instead of carrying over. [DOC S-aishnkok]
- For subagents of the current session, `/tasks` lists them and `x` on a row stops one; a subagent Claude stops with the `TaskStop` tool, which also accepts a teammate or a named background agent by ID or name, can be resumed by a message, while one you stopped with `x` does not auto-resume. [DOC S2157, S-2ip5zngf]
- `Ctrl+X Ctrl+K`, pressed twice within three seconds, stops every running background subagent in the session and turns off artifact auto-replies for the rest of it; it works while a background subagent's permission prompt is open. [DOC S-eumxht6x]
- A background subagent's permission prompt appears in the main session naming the subagent, and `Esc` denies that one tool call without stopping the subagent; `Ctrl+B` moves a running task to the background. [DOC S2157]
- For an in-process agent-team teammate, the arrow keys select a teammate in the agent panel, `Enter` opens its session, `x` stops it, and `Esc` while viewing its transcript interrupts its current turn; the graceful route is to ask the lead to shut the teammate down, which sends a request the teammate can approve or reject. [DOC S-qdxfqzln]
- Teammates finish their current request or tool call before shutting down, so the page lists slow shutdown as a limitation; a teammate row that vanished after sitting idle has been hidden, not stopped, and a message to the teammate by name brings the row back. [DOC S-qdxfqzln]
- For a dynamic workflow, `/workflows` lists runs and `x` on a list entry stops a running one; in the progress view `p` pauses or resumes the run, `x` stops the selected agent or, with focus on the run, the whole workflow, and `r` restarts the selected running agent. [DOC S-qulnsg4e]
- A stopped workflow stays in the task panel while any of its agents' processes still run, and stopping it again signals those processes again; the `Large workflow` warning (more than 25 agents or a projected 1.5 million tokens) is advisory and points to `/workflows`, where the run can be stopped. [DOC S-qulnsg4e]

### What is kept when parallel work is stopped
- A deleted background session leaves the list but its transcript stays on the machine and opens with `claude --resume`; on v2.1.212 or later a bare `/resume` in agent view's dispatch input lists past sessions, deleted ones included, and resumes the chosen one as a background session. [DOC S-aishnkok]
- A finished or waiting background session that stays unattached for about an hour has its process stopped by the supervisor; the conversation stays on disk and resumes when you attach or reply, and `Ctrl+T` pins a session to keep its process running. [DOC S-aishnkok]
- Agent view deletes a session's worktree including uncommitted changes, `claude rm` keeps it when it holds uncommitted changes, and neither removes a worktree another running session uses or has locked; a worktree with commits Claude Code cannot confirm are saved elsewhere is kept until the delete is repeated, and `claude rm <id> --discard-unpushed` discards the commits and the branch. [DOC S-aishnkok]
- A worktree you made yourself and started the session in is left in place whichever way the session is deleted. [DOC S-aishnkok]
- When a session is backgrounded, running background shell commands, background subagents and dynamic workflows carry over to its new process, a subagent still running in a workflow restarts from the beginning, and running monitors stop. [DOC S-aishnkok]
- Subagent transcripts are files `agent-<agentId>.jsonl` under the session's `subagents/` folder in `~/.claude/projects/`; they are untouched by the main conversation's compaction, last for the session and are deleted after `cleanupPeriodDays` (30 days by default). [DOC S2157]
- A background subagent that fails or that you stop keeps its row in the subagent panel for 30 seconds, and `x` clears it sooner; while the row is there, typing into the subagent's transcript resumes it yourself, after which a message from Claude can auto-resume it again. [DOC S2157]
- A background subagent that ends on an API error is marked failed and the message Claude receives names the error and includes the subagent's last output, so partial work is not lost; a foreground subagent cut off after producing text returns that partial output with a note that it did not finish. [DOC S2157]
- A subagent worktree with no changes is removed when the subagent finishes, one with changes stays until the periodic sweep can remove it without losing work, and Claude Code holds a `git worktree lock` on a worktree while its agent runs. [DOC S-j22fjuka]
- The sweep releases a lock Claude Code set for a session whose process has exited, so a killed background session does not keep its worktree locked (before v2.1.210 the lock stayed until `git worktree unlock`); `-p` runs are not cleaned up at exit. [DOC S-j22fjuka]
- When the session ends, the team config directory of an agent team is removed but the task list under `~/.claude/tasks/{team-name}/` stays until the `cleanupPeriodDays` sweep; `/resume` and `/rewind` do not restore in-process teammates, and a message to a stopped in-process teammate in the same session brings it back with its saved conversation. [DOC S-qdxfqzln]
- A workflow run that is stopped keeps the results of completed agents: on relaunch a completed agent returns its saved result, an agent that was running when the whole run stopped starts over without counting as failed, and an agent stopped on its own with `x` counts as failed, so it and every agent that started after it run again. [DOC S-qulnsg4e]
- Relaunching a stopped workflow is refused until the agents of the stopped run have exited, so a second copy cannot run beside them; a stalled agent's restart starts without the earlier attempt's transcript, files the attempt changed stay changed and its tokens stay in the run total. [DOC S-qulnsg4e]
- Choosing `Exit and stop tasks` when leaving a session stops a running workflow, but its saved results stay under the session's directory in `~/.claude/projects/` for a session resumed with `claude --resume`; in a session started fresh Claude has no earlier run to relaunch. [DOC S-qulnsg4e]
- The docs name no worktree or file-level rollback for the files a stopped agent-team teammate or a stopped workflow agent had already changed: agent teams do not isolate teammates in worktrees, and the workflows page says only that files a stalled attempt changed stay changed. [DER S-qdxfqzln, S-qulnsg4e: the isolation rows and the stall paragraph; the agent-teams and workflows pages read on 2026-10-17 state neither]

### How it fits: which stop for which kind of work
- No single command stops every kind of parallel work: a background session stops with `Ctrl+X`, `/stop` or `claude stop <id>`, a subagent with `x` in `/tasks` or `Ctrl+X Ctrl+K` for all of them, a teammate with `x` in the agent panel or a shutdown request through the lead, a workflow with `x` in `/workflows`, and the supervisor with `claude daemon stop --any`. [DER S-aishnkok, S2157, S-eumxht6x, S-qdxfqzln, S-qulnsg4e: the per-kind stop rows above]
- A stop keeps the conversation or transcript in every kind and the files only where an isolation exists: a background session's changes sit in its worktree until a delete removes them, so commit or push first; a teammate's edits are in the shared checkout and stay there. [DER S-aishnkok, S-qdxfqzln, S-j22fjuka: delete rules and the teams isolation row]

### Which options reach other machines or the cloud
- Agent view runs sessions on your machine under a per-user supervisor process that outlives the terminal; sessions survive sleep but stop when the machine shuts down, and the page sends anyone who wants Claude to start and track cloud sessions to projects. [DOC S-aishnkok]
- Agent teams keep their team and task data in local directories under a name derived from the session ID, run teammates in the lead's terminal (in-process) or in tmux or iTerm2 panes, and allow one team per session. [DOC S-qdxfqzln]
- Worktrees are separate checkouts of one repository that share its `.git` directory (and are made with `claude --worktree` or `git worktree add`). [DOC S-j22fjuka]
- Projects start threads in the cloud or on your computer through Remote Control, and the parallel-work page names cross-session messaging as the way sessions on this machine, on another machine or in the cloud pass findings between themselves. [DOC S-76oyiuez]
- Cross-session messaging reaches subagents, teammates and local sessions, and, only while connected to Remote Control (a claude.ai sign-in), cloud sessions and sessions on other machines; same-machine messages use a local socket and never pass Anthropic servers. [DOC S-sdxhnx3i]
- Workflows are available on all paid plans, with Anthropic API access and on Amazon Bedrock, Google Cloud's Agent Platform and Microsoft Foundry; a run can be resumed in the same session, replays in a backgrounded session, and in a cloud session its results are saved with the conversation so a relaunch after the VM is reclaimed returns completed agents. [DOC S-qulnsg4e]

### Dynamic workflows against subagents and skills
- A dynamic workflow is a JavaScript script that orchestrates many subagents; Claude writes it for the described task and a runtime executes it in the background while the session stays responsive. [DOC S-qulnsg4e]
- A workflow holds the loop, the branching and the intermediate results in script variables, so Claude's context holds only the final answer; with subagents, skills and agent teams Claude decides turn by turn and every result enters a context window. [DOC S-qulnsg4e]
- Because the plan is code, a workflow can apply a repeatable quality pattern: independent agents adversarially review each other's findings before they are reported, or a plan is drafted from several angles and weighed. [DOC S-qulnsg4e]
- The docs say to use a dynamic workflow, not a subagent or a skill, when a task needs more agents than one conversation can coordinate or the orchestration should be codified as a script you can read and rerun; what a workflow holds that a subagent or skill does not is the plan, the loop and the intermediate results. [DOC S-qulnsg4e]
- Each run writes its script to a file under the session's directory in `~/.claude/projects/`; a run can be saved as a command in `.claude/workflows/` (shared) or `~/.claude/workflows/` (personal) or shipped in a plugin's `workflows/` directory. [DOC S-qulnsg4e]
- The runtime has no mid-run user input (sign-off between stages means one workflow per stage), no direct filesystem or shell access from the script itself (agents do that), and no module loading. [DOC S-qulnsg4e]
- The runtime runs up to 16 agents at once by default, accepts up to 4,096 items in one `parallel()` or `pipeline()` call and stops at 1,000 agents per run. [DOC S-qulnsg4e]
- A run that schedules more than 25 agents, or projects more than 1.5 million tokens, shows a `Large workflow` warning; agents in a run can read each other's prompt cache when they share the same prefix. [DOC S-qulnsg4e]
- The keyword `ultracode` or a direct request such as "use a workflow" in a prompt you type opts one task in; `/effort ultracode` makes Claude plan workflows for every substantive task and costs more tokens each time; `-p`, a scheduled prompt or a relayed webhook payload does not start one through the keyword. [DOC S-qulnsg4e]
- In `claude -p` and the Agent SDK no launch prompt is shown, so the `Workflow` tool call goes through ordinary permission evaluation and needs an allow rule (`Workflow` or `Workflow(<name>)`), auto or bypass mode, a `PreToolUse` hook that allows it, or a host approval. [DOC S-qulnsg4e]
- The subagents a workflow spawns use the session's permission rules and sandboxing, and `/deep-research` is the one bundled workflow. [DOC S-qulnsg4e]
- The page's example for a migration asks for each file to be transformed in its own isolated copy, but it does not say here how that copy is made, so a workflow's file isolation is not confirmed by the page. [UNK]

### How it fits
- For a need in this kb's frame, the options sort as follows: a noisy side task inside one task is a subagent; many independent tasks handed off and checked later are agent view sessions, each in its own worktree; workers that must exchange findings while they run are an agent team (one machine, files partitioned by hand) or cross-session messaging between sessions you run; a job over hundreds of items with verification is a workflow; work that must continue with the machine off is a project thread, a cloud session or a routine. [DER S-76oyiuez, S-qulnsg4e, S-aishnkok, S-qdxfqzln: the use-case rows and limits above]
- Beyond cross-session messaging (`claude/cross-session-messaging.md:38`, `:51`: Remote Control and a claude.ai sign-in reach other machines and cloud sessions), the only option that reaches sessions on several machines or cloud sessions is projects; agent view, agent teams, worktrees and workflows stay on one machine, the one that started them, so a design that needs a shared plan across machines must use one of those two or a shared record outside Claude Code. [DER S-76oyiuez, S-sdxhnx3i, S-aishnkok: the docs describe no cross-machine form of the other options]
- A workflow cannot pause for a person mid-run, so a tiered-approval step belongs between two workflows rather than inside one. [DER S-qulnsg4e: the no-mid-run-input row]

## Reference
- Run agents in parallel: https://code.claude.com/docs/en/agents (S-76oyiuez)
- Agent view: https://code.claude.com/docs/en/agent-view (S-aishnkok); worktrees: https://code.claude.com/docs/en/worktrees (S-j22fjuka)
- Dynamic workflows: https://code.claude.com/docs/en/workflows (S-qulnsg4e); agent teams: https://code.claude.com/docs/en/agent-teams (S-qdxfqzln)
- Setting `worktree.bgIsolation`: https://code.claude.com/docs/en/settings-reference (S-wzatkg4o)
- Related: `claude/cross-session-messaging.md` (the messaging tools, Remote Control reach and Projects); `claude/skills-and-subagents.md` (subagent frontmatter, `isolation`, agent teams); `claude/large-codebases.md` (agent view across several repositories); `agents/coordination-messages.md` (what messages hold and what coordination costs).

## Examples
- SNIPPET: let agent-view background sessions edit the working copy directly in a repository where worktrees are impractical; context: Claude Code v2.1.143+, project `.claude/settings.json`; checked: syntax [DOC S-wzatkg4o: `worktree.bgIsolation` example]
```json
{
  "worktree": {
    "bgIsolation": "none"
  }
}
```
