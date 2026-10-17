---
topic: claude/cross-session-messaging
priority: P3
applies_to: "Claude Code v2.1.224+ (macOS, Linux, WSL 2), native Windows per the docs page v2.1.234+; cross-session messaging page and changelog, retrieved 2026-09-30 (Claude Code 2.1.285 current); Remote Control and channels pages read 2026-10-17"
retrieved_utc: 2026-10-17
sources: [S-sdxhnx3i, S746, S-3yod3u7q, S-wzatkg4o, S748, S-d3ythwgb, S2057, S2042, S-fk46gdey, S-4jj4dtg4, S-s67nwj2e, S-yhad7wiu, S-m6qlxza7, S-uw2bn2un]
status: complete
---

# Cross-session messaging: ListAgents and SendMessage between your Claude Code sessions

## Summary
Cross-session messaging lets Claude in one Claude Code session send a plain-text message to another of the same
user's sessions: on the same machine (over a per-session socket or named pipe, never through Anthropic servers), on
another machine through Remote Control, or in a cloud session. Claude finds targets with the `ListAgents` tool
(`/list-agents` for people) and sends with `SendMessage`, on request or on its own initiative. It is on by default
when a session meets the version and platform requirements. The receiving session treats the message as coming from
another Claude session, not from the user, so it cannot approve prompts or change configuration. Inbound delivery is
governed by `crossSessionInbound` (accept, hold, refuse) and a permission-mode default, outbound cross-machine sends
can require approval with `isolatePeerMachines`, and deny rules on `SendMessage` and `ListAgents` turn off sending
and listing.

## Facts
### Availability and versions
- Requires Claude Code v2.1.224 or later on macOS, Linux and Linux inside WSL 2, and v2.1.234 or later on native
  Windows; when a session meets the requirements messaging is on with nothing to enable. [DOC S-sdxhnx3i]
- The changelog added cross-session `SendMessage` with `ListAgents` in v2.1.224 (August 7, 2026) for macOS and Linux,
  and lists "Windows: cross-session messaging is now available" under v2.1.239 (August 21, 2026); the v2.1.234 entry
  has no Windows line. [DOC S746]
- The week 34 digest (releases v2.1.234 to v2.1.239, August 17-21, 2026) announces that sessions on native Windows can
  now message each other with `SendMessage` and `ListAgents`. [DOC S-d3ythwgb]
- For native Windows, plan on v2.1.239 or later: it is the release the changelog and the week 34 digest announce
  Windows support in, and it satisfies the docs page's stated v2.1.234 floor too; v2.1.234 to v2.1.238 on Windows are
  unverified. [DER S-sdxhnx3i, S746, S-d3ythwgb: the stated floor and the release that announced it]
- Same-machine messaging works on every provider (Amazon Bedrock, Claude Platform on AWS, Google Cloud's Agent
  Platform, Microsoft Foundry) and with feature-flag fetching off, but on those providers and with flag fetching off
  it needs v2.1.248 or later. [DOC S-sdxhnx3i]
- Reaching cloud sessions and sessions on other machines needs this session connected to Remote Control, which needs a
  claude.ai sign-in as the active authentication; with an API key or on Bedrock, Claude Platform on AWS, Google
  Cloud's Agent Platform or Microsoft Foundry those sessions cannot be found. [DOC S-sdxhnx3i]
- Starting a conversation with a session on another of your machines requires v2.1.225 or later (before that
  `SendMessage` could only reply after the other session messaged first). [DOC S-sdxhnx3i, S746]
- Check a session with `/list-agents` (alias `/peers`): if the command is not recognized the session does not have the
  feature; if it works but a send did not arrive, something narrower applies (deny rules, the receiver's inbound
  controls, Remote Control not connected, an `offline` target, or an older remote session past the bounded session
  list). [DOC S-sdxhnx3i]
- `/status` shows a `Peer address` row with the session's inbox address (`uds:` prefix), or `unavailable` and the
  reason when no inbox could be set up. [DOC S-sdxhnx3i]

### Tools and targets
- `ListAgents` lists what `SendMessage` can reach: subagents in the session, agent-team teammates, other local Claude
  Code sessions, and, while connected to Remote Control, cloud sessions and Remote Control sessions on other machines;
  it backs `/list-agents` and appears only where cross-session messaging is enabled. Teammate rows and the first line
  with the session's own name require v2.1.239+. [DOC S-3yod3u7q]
- `SendMessage` sends to a teammate, a subagent it resumes by id or name, or another of your sessions; an optional
  `summary` (typically 5-10 words) becomes the one-line preview, else the message's first line; summaries over 200
  characters are truncated. [DOC S-3yod3u7q]
- A local session appears in the listing only when it binds an inbox socket; cloud and other-machine sessions appear
  only while this session is connected to Remote Control, the latter labelled `Remote Control`, and a dropped one
  shows `offline`. [DOC S-sdxhnx3i]
- A message to an `offline` session is accepted and arrives when that machine reconnects. [DOC S-sdxhnx3i]
- A session answers to the name set with `/rename` or `--name`, else a name Claude Code generates; when several live
  sessions share a name, Claude addresses the target by a short identifier from its listing. The user can name a
  target with an `@` mention from the typeahead (v2.1.232+); names with spaces go in double quotes (`@"release
  notes"`). [DOC S-sdxhnx3i]
- While connected to Remote Control, `/list-agents` output withholds local sessions' working directories, names it
  cannot attribute to a person (`(unnamed session)`), and this session's own-name line unless typed at this terminal;
  what Claude itself sees is unchanged. [DOC S-sdxhnx3i]

### Transport
- Same machine: a per-session Unix domain socket on macOS and Linux (including WSL 2) or a named pipe on native
  Windows, never through Anthropic servers. Another machine: through Anthropic servers over that machine's Remote
  Control connection. Cloud: through Anthropic servers straight to the cloud session. [DOC S-sdxhnx3i]
- A session in a container and one on the host cannot reach each other (two in the same container can); a WSL 2
  session and a native Windows session on the same computer cannot either. [DOC S-sdxhnx3i]
- If the sending session is not connected to Remote Control when it sends beyond this machine, the message goes
  through without a reply address, so the receiver cannot answer (one-way). [DOC S-sdxhnx3i]
- The socket path is in `/status` and exported to hooks and Bash as `CLAUDE_CODE_MESSAGING_SOCKET` (before any hook,
  including `SessionStart`), with a per-session token in `CLAUDE_CODE_MESSAGING_TOKEN`; a script opens with
  `{"type":"auth","token":"<token>"}`, optional on macOS/Linux/WSL 2 and required on native Windows. [DOC S-sdxhnx3i]
- On macOS and Linux the socket is restricted to the operating-system user; on native Windows each connection must
  first authenticate with a key only that user can read. An unacceptable socket directory (e.g. owned by another user)
  is refused in favour of a private `/tmp/cc-socks-<uid>`. [DOC S-sdxhnx3i]
- The socket closes a connection that sends no complete line within 30 seconds (changelog: since v2.1.243), so a
  script connects only once its message is ready. [DOC S-sdxhnx3i, S746]
- `claude -p` sessions bind an inbox like interactive ones; bare-mode sessions do not, so they cannot receive and do
  not appear in listings. [DOC S-sdxhnx3i]

### How an incoming message is treated
- A message is text one Claude writes, never the sender's conversation history or files; to move a whole
  conversation, resume the session instead. [DOC S-sdxhnx3i]
- The receiver is told the message came from another session, not the user: it cannot answer a permission prompt,
  Claude is instructed not to change permission settings, `CLAUDE.md` or other configuration because another session
  asked, a `/command` in the text is never executed, and the receiver's own permission prompts still fire. [DOC
  S-sdxhnx3i]
- The sender's Claude is instructed never to ask another session for an action denied or blocked in its own session,
  and to route that work back to the user. [DOC S-sdxhnx3i]
- Delivery: during an active turn the receiver reads it between tool calls (a running tool is never interrupted); an
  idle session starts a new turn. `@` file or MCP resource mentions in the text are not attached. A delivered message
  counts toward usage like a typed prompt. [DOC S-sdxhnx3i]
- The receiver shows a one-line `› Message from @<sender>: <first line>` preview; `Ctrl+O` opens the full text,
  `--verbose` shows it inline; Claude always reads the full message. [DOC S-sdxhnx3i]

### Inbound controls
- `crossSessionInbound`: `accept` delivers, `hold` shows a notice without delivering (released if an `accept` later
  applies), `refuse` drops. Also settable in `/config` as "Messages from your other sessions" (v2.1.232+), which
  writes user settings; the `/config crossSessionInbound=value` shorthand is rejected. [DOC S-sdxhnx3i]
- With no `crossSessionInbound` value, the default is decided by permission-mode class (bypassing vs prompting; auto,
  `acceptEdits` and `dontAsk` count as prompting): a prompting receiver delivers unless the sender says it bypasses;
  a bypassing receiver holds each message for approval unless the sender also bypasses. [DOC S-sdxhnx3i]
- A default hold opens an approval dialog (Approve delivers one message; Deny or dismiss drops it); an unanswered
  dialog closes and drops the message at `dialogExpiry` (default five minutes), except while no terminal is attached
  to a background session. At most 100 held messages are kept, oldest dropped first. [DOC S-sdxhnx3i]
- `dialogExpiry` (user or managed scope, v2.1.224+) takes `"60s"`, `"5m"` (default), `"10m"` or `"never"`;
  `CLAUDE_CODE_USER_DIALOG_TIMEOUT_MS` overrides it for one session. [DOC S-wzatkg4o]
- In a `-p` session a default-held message waits up to `dialogExpiry` and is then dropped and reported expired to a
  reachable sender; an explicit `hold` never expires. To let a `-p` worker accept unattended, pass
  `crossSessionInbound: "accept"` in its `--settings`. [DOC S-sdxhnx3i]
- With no `crossSessionInbound` value, a message verified to come from the session's own child process (a hook or
  Bash command posting to its own socket, by process evidence or the exported token) is delivered. [DOC S-sdxhnx3i]
- An invalid `crossSessionInbound` value warns and holds messages (user settings) or refuses them (managed settings)
  since v2.1.248. [DOC S746]
- `crossSessionInbound` precedence: values rank `accept` < `hold` < `refuse`; a stricter value from
  `.claude/settings.json` or `.claude/settings.local.json` is honored over managed, `--settings` and user values, and a
  project or local value that is not stricter is ignored. [DOC S2057]
- Across several managed sources, `crossSessionInbound` is a lock: the strictest value any source sets applies, and a
  looser value applies only from the highest-ranked source; an invalid managed value is treated as `refuse` with a
  warning. [DOC S2042]
- `isolatePeerMachines: true` from any scope is honored even when a managed source sets `false`. [DOC S2057]

### Restricting and turning off
- `isolatePeerMachines: true` asks the user before any `SendMessage` leaves for a session beyond this machine, even
  in `bypassPermissions` mode; a `true` from any scope applies, so a checked-in project file can turn it on but not
  off. Same-machine messages are never prompted. [DOC S-sdxhnx3i]
- Stop receiving: `crossSessionInbound: "refuse"`; from project or local settings it wins over every other source,
  from user settings unless managed settings or `--settings` set a value. Stop sending and listing: permission deny
  rules on bare `SendMessage` and `ListAgents`. [DOC S-sdxhnx3i]
- Organization-wide off: managed settings with `permissions.deny: ["SendMessage", "ListAgents"]` and
  `crossSessionInbound: "refuse"`; the inbox socket is still bound but drops everything, and denying `SendMessage`
  also removes messaging to subagents and teammates. A refusing session looks unchanged in `/status` and in others'
  listings, so confirm it from the settings files. [DOC S-sdxhnx3i]

### Idle notices and limits
- `SendMessage`'s `notify_when_idle` (v2.1.236+ in both sessions) asks a session on this machine for one notice when
  it next finishes a turn with nothing queued or exits; only the main conversation can subscribe, only to local
  sessions, and the subscription is dropped after 12 hours without a notice. [DOC S-sdxhnx3i]
- Plain text only (team protocol messages stay in the team); a same-machine message over about a million serialized
  characters is refused at the sender; rapid bursts to one session are refused at the sender; the receiver
  rate-limits per sender, drops identical repeats in a short window and queues at most 50 accepted messages, so a loop
  between two sessions stops on its own. [DOC S-sdxhnx3i]

### Coordinating sessions across repositories (Projects)
- Projects are in public beta on Pro and Max plans, rolling out gradually, and not yet available on Team or
  Enterprise plans. [DOC S-fk46gdey]
- A project is one ongoing conversation in which Claude starts a thread per task, usually a cloud session (or a local
  one through Remote Control); every thread starts with the project's instructions. [DOC S-fk46gdey]
- For one goal across many repositories the page names a thread per repository, each with its own pull request,
  and an **Overview** pane that shows which are ready for review. [DOC S-fk46gdey]
- Each cloud thread clones every repository in the project and loads `CLAUDE.md` and skills from all of them; with
  several repositories in an Anthropic-hosted environment, no repository's permission rules, hooks or `env` apply,
  so standing rules go in project instructions and variables in the cloud environment. [DOC S-fk46gdey]
- A thread can add a repository the project lacks to itself partway through a task (that thread only, its
  `CLAUDE.md` and skills missing at start); it needs the Claude GitHub App and push access, and Claude adds
  repositories only from a GitHub owner the project already uses. [DOC S-fk46gdey]
- A project that works on code needs that code on github.com, not on GitHub Enterprise Server, GitLab or Bitbucket,
  with push access from the connected GitHub account and the Claude GitHub App installed on it; a `/web-setup` token
  is not enough for a project's cloud threads. [DOC S-fk46gdey]
- Coordinating agents across repositories therefore takes one of three documented forms: one session reaching other
  checkouts (`--add-dir`, a multi-repository cloud session), separate sessions per repository that message each
  other (this page) or that a Project starts and tracks, or a CI pipeline in one repository that triggers and waits on
  pipelines in others (`gitlab/multi-project-pipelines.md`). A Project's code threads need the repositories on
  github.com, so repositories on GitLab or GitHub Enterprise Server are left with the other forms. [DER S-fk46gdey,
  S-sdxhnx3i: the Projects page and this page's targets; S-4jj4dtg4 in `claude/large-codebases.md`; S-s67nwj2e in
  `gitlab/multi-project-pipelines.md`]

### Answering a session's prompts from another device: Remote Control and channels
- Remote Control connects claude.ai/code or the Claude mobile app to a Claude Code session that keeps running on the
  user's machine, with code execution and filesystem access staying local; the session transcript is stored on
  Anthropic servers while it is connected. It needs a Pro, Max, Team or Enterprise claude.ai login (an Owner enables
  the toggle on Team and Enterprise), and is unavailable with API keys, Bedrock, Google Cloud's Agent Platform,
  Microsoft Foundry, an `ANTHROPIC_BASE_URL` other than `api.anthropic.com`, or a Claude apps gateway sign-in. [DOC
  S-yhad7wiu]
- The conversation and the progress of subagents and dynamic workflows stay in sync across the terminal, the browser
  and the phone, and messages can be sent from any of them. Claude Code keeps permission prompts and `AskUserQuestion`
  questions open until they are answered, and another kind of dialog it forwards to the remote session (its example is
  the model-choice prompt after a safety refusal) closes after five minutes by default with the dialog's no-action
  default, adjustable with `dialogExpiry` (v2.1.224+). The page has no sentence that says in so many words that a
  permission prompt is approved from the phone; see the open gap in `_gaps.md`. [DOC S-yhad7wiu]
- Not every dialog travels: the Fable usage-credits consent prompt is shown only where the session runs, and when
  nobody there answers before it closes the turn ends without sending the request. Commands that only exist in the
  terminal interface (`/plugin`, `/resume`) work only from the local CLI, while `/model`, `/effort`, `/compact`,
  `/clear`, `/context`, `/usage` and a few others work from mobile and web. [DOC S-yhad7wiu]
- Mobile push notifications (Remote Control active, Claude app signed in to the same account) have two toggles in
  `/config`: **Push when Claude decides** (typically a finished long task or a needed decision) and **Push when actions
  required** (permission prompts and questions). There is no per-event configuration, and pushes are skipped while the
  user is typing in the connected terminal; `CLAUDE_CLIENT_PRESENCE_FILE` extends that skip to any time a marker file
  exists. [DOC S-yhad7wiu]
- Trusted Devices (beta, off by default; an Owner turns it on for Team and Enterprise, a Pro or Max user for self) makes
  viewing or steering a Remote Control session require an enrolled device and a sign-in no more than 18 hours old,
  refreshed by Face ID, Touch ID, Windows Hello or a passkey; unenrolled devices cannot view or steer the session, and
  sessions already running when the toggle is turned on are not retroactively protected. [DOC S-yhad7wiu]
- `disableRemoteControl` turns Remote Control off entirely, and organizations with Zero Data Retention or the HIPAA
  configuration cannot enable it. [DOC S-yhad7wiu]
- A channel is an MCP server that Claude Code spawns on the same machine over stdio to push events (chat messages,
  webhooks) into a running session; Telegram, Discord and iMessage plugins ship in the research preview, started with
  `--channels plugin:<name>@<marketplace>`. A server in `.mcp.json` does not push messages unless `--channels` names
  it. Channels need claude.ai or Console API key authentication and are not available on Bedrock, Google Cloud's Agent
  Platform or Microsoft Foundry. [DOC S-uw2bn2un]
- A channel that declares `capabilities.experimental['claude/channel/permission']` receives the session's tool approval
  prompts in parallel with the local terminal dialog, so the user can approve or deny from a phone or chat app: both
  stay live and Claude Code applies whichever answer arrives first and closes the other. [DOC S-m6qlxza7]
- Relay covers tool-use approvals such as `Bash`, `Write` and `Edit`; project trust and MCP server consent dialogs do
  not relay and appear only in the local terminal. Since v2.1.234 Claude Code sends permission requests only to
  servers registered as channels for the session with `--channels` or the development flag, so relay sits behind the
  same session opt-in and organization controls as message delivery. [DOC S-m6qlxza7]
- Relay loop: Claude Code generates a short request id and sends `notifications/claude/channel/permission_request`
  with `request_id`, `tool_name`, `description` and `input_preview`; the channel server formats it for the chat app;
  the remote user replies with yes or no and the id; the server answers with `notifications/claude/channel/permission`
  carrying `request_id` and `behavior` (`allow` or `deny`). Claude Code applies a verdict only if its id matches an open
  request and drops any other silently, and a verdict covers that one call, not future calls. [DOC S-m6qlxza7]
- `request_id` is five lowercase letters from `a` to `z` without `l`; the local dialog does not display it, so the
  channel's outbound handler is the only way for the remote user to learn it. `description` is a summary of what the
  call does, never the command itself (for a Bash call with no model description it is the constant `Run shell
  command`), and `input_preview` carries the arguments (for Bash the command). [DOC S-m6qlxza7]
- Clients on v2.1.211+ sanitize `description` and `input_preview` (direction-override and invisible characters,
  lookalike quotes, runs of whitespace) and relay up to 3,500 code points whole, else the start and end around a
  counted elision marker; clients before it relay `description` raw and cut `input_preview` to 200 UTF-16 units. From
  v2.1.234 credentials with a recognizable provider prefix are masked as `[REDACTED]`, but a secret without a
  recognizable prefix or one spanning whitespace (a private-key block) reaches the server unmasked. [DOC S-m6qlxza7]
- Authority: every approved channel plugin keeps a sender allowlist, and the allowlist also gates permission relay, so
  anyone who can reply through the channel can approve or deny tool use in the session; the page says to allowlist only
  senders trusted with that authority, and the reference says to gate on the sender's id, not the room's. [DOC
  S-uw2bn2un, S-m6qlxza7]
- Organization controls: on Team and Enterprise plans `channelsEnabled` is the master switch (off or unset blocks every
  channel, the development flag included) and `allowedChannelPlugins` replaces the Anthropic-maintained allowlist; Pro
  and Max users without an organization skip these checks. Channels are a research preview, so the flag syntax and
  protocol contract may change, and custom channels need `--dangerously-load-development-channels` to load. [DOC
  S-uw2bn2un]
- Without a relay-capable channel, a session that hits a permission prompt while the user is away pauses until the
  prompt is answered; `--dangerously-skip-permissions` bypasses most prompts but is for trusted environments only. [DOC
  S-uw2bn2un]

### How it fits
- For an operator approving a fleet of sessions from one place, the documented remote answers are narrow: Remote Control
  forwards the prompts of one session at a time to the Claude app or claude.ai/code and pushes a notification for a
  waiting permission prompt (and needs claude.ai sign-in, so not an API-key or gateway estate), and a channel relays tool approvals to a chat app the operator controls. Neither
  relays project trust or MCP consent dialogs, and an approver's authority is exactly whoever the sender allowlist or
  the signed-in account admits. [DER S-yhad7wiu, S-m6qlxza7, S-uw2bn2un: the endpoint and login limits, the relay
  coverage and the allowlist statement]
- For unattended agents in this kb's frame, a bypass-mode session (e.g. a background job with
  `bypassPermissions`) holds every message from a prompting session for approval by default, so an orchestrator that
  must reach a headless worker sets `crossSessionInbound: "accept"` in that worker's `--settings`, and never in user
  settings, where it would apply to every session. [DER S-sdxhnx3i: the permission-mode default and the `-p` worker
  guidance above]
- An organization that must keep agent traffic on the device (e.g. under ZDR, where Remote Control is disabled) still
  gets same-machine messaging, which never passes Anthropic servers, and can add `isolatePeerMachines: true` in
  managed settings to gate anything leaving the machine. [DER S-sdxhnx3i, S748: transport table and `isolatePeerMachines`;
  Remote Control disabled under ZDR per `claude/data-retention.md`]

## Reference
- Docs: `https://code.claude.com/docs/en/cross-session-messaging` (S-sdxhnx3i); tools table rows `ListAgents` and
  `SendMessage` (S-3yod3u7q); settings `crossSessionInbound`, `isolatePeerMachines`, `dialogExpiry` (S-wzatkg4o).
- Related kb articles:
  - `claude/skills-and-subagents.md` — `SendMessage` within a session (subagents) and agent teams; the same
    "message from another Claude session, not the user" rule.
  - `claude/settings-and-scopes.md` — permission modes; cross-session messaging safeguards are never auto-approved.
  - `claude/data-retention.md` — Remote Control is disabled under ZDR, which removes cross-machine and cloud targets.
  - `agents/headless-agent-runtimes.md` — cloud sessions and background runtimes that can be message targets.
  - `agents/peer-state-sync.md` — sharing agent state (not messages) between machines without a server: Syncthing,
    DFS Replication, Automerge and git, and what each does with concurrent changes.
  - `claude/large-codebases.md` — one session across several repositories: `--add-dir`, agent view `@<repo>`
    dispatch, multi-repository cloud sessions and the settings they drop.
  - `gitlab/multi-project-pipelines.md` — coordinating work across GitLab projects in CI: trigger jobs, mirrored
    status, job token allowlists.
  - `claude/parallel-sessions.md` — which parallel-work option (subagents, agent view, agent teams, workflows,
    worktrees) fits which coordination need, and which of them stay on one machine.
- Projects: `https://code.claude.com/docs/en/claude-projects` (S-fk46gdey).
- Remote Control: `https://code.claude.com/docs/en/remote-control` (S-yhad7wiu); channels:
  `https://code.claude.com/docs/en/channels` (S-uw2bn2un) and the contract
  `https://code.claude.com/docs/en/channels-reference` (S-m6qlxza7).
- `claude/hooks.md` — the `Notification` hook (`permission_prompt`, `idle_prompt`) that fires when a session waits;
  `claude/statusline.md` — the per-session cost and context line.

## Examples
- SNIPPET: managed settings that turn cross-session messaging off for an organization; context: Claude Code v2.1.224+, managed settings file; checked: syntax [DOC S-sdxhnx3i: "Turn off cross-session messaging" example]
```json
{
  "permissions": {
    "deny": ["SendMessage", "ListAgents"]
  },
  "crossSessionInbound": "refuse"
}
```

- SNIPPET: require approval before any message leaves this machine; context: Claude Code v2.1.224+, any settings scope (a `true` from any scope applies); checked: syntax [DOC S-sdxhnx3i: `isolatePeerMachines` example]
```json
{
  "isolatePeerMachines": true
}
```
