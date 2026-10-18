---
topic: claude/mods
priority: P3
applies_to: "Claude Code mods (function hooks in a plugin), docs pages dateModified 2026-10-08 to 2026-10-17, read 2026-10-18; mods on by default from Claude Code 2.1.287 (Desktop 2.1.286)"
retrieved_utc: 2026-10-18
sources: [S-oawin5n2, S-y5j64svc, S-sao3dfcq, S-mvuodgli, S-kppz7qns, S-ho47nrnt, S-4vxgduip, S-toe7z3kj, S-3peuisvr, S-hvuk3dqt]
status: partial
---

# Claude Code mods: a plugin of function hooks that draws a pane or a band

## Summary
A mod is a plugin whose JavaScript or TypeScript code registers event handlers ("hooks") that run inside Claude Code,
unlike a settings hook, which runs a shell command, HTTP request or prompt. A mod can draw a pane beside the transcript
or a band above the prompt, add a `/command`, change a tool call or a prompt, and reach files, processes and the network
through the mods API (`$`). Drawing works in the terminal, the Desktop app and the VS Code extension; in `claude -p` and
the Agent SDK the hooks run and nothing is drawn. Mods are on by default from Claude Code 2.1.287. The pages do not
document that a mod can append a row to the conversation that the model reads and the person does not see; the documented
route for text only the model reads is a `prompt.submit` hook's `context` (see the Facts below and `_gaps.md`).

## Facts
### What a mod is and where it runs
- A mod is a plugin that changes how Claude Code looks and behaves: event handlers written in JavaScript or TypeScript
  that Claude Code calls when an event happens (a tool call, a submitted prompt, a part of the interface being drawn).
  The pages call both kinds "hooks": a mod's handler is a function that runs inside Claude Code, the settings-file kind
  is a "settings hook". [DOC S-oawin5n2]
- A small mod has three files: `.claude-plugin/plugin.json` (the plugin manifest, no extra required fields),
  `hooks/hooks.json` (points to the code file) and `hooks/register.js` (the hooks module, which exports `register(on)`
  and tells Claude Code which events to run its functions on). A hook receives `($, e, next)`: the mods API, the event,
  and the rest of the chain. [DOC S-oawin5n2, S-mvuodgli]
- Mods are on by default; the terminal needs Claude Code 2.1.287 or later and the Desktop app 2.1.286 or later. The
  changelog entry of 2.1.287 (October 1, 2026) reads "Added Claude Mods: plugins may now modify deeper behavior". The
  environment variable `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS`, set "during early access", is ignored at any value from
  2.1.287. [DOC S-oawin5n2, S-ho47nrnt, S-hvuk3dqt]
- Where a mod's hooks run and where its drawing appears: `claude` in a terminal runs and draws; the Desktop Code tab runs
  and draws (not in a WSL session, where plugins are unavailable); the VS Code chat panel runs and draws from extension
  version 2.1.299 in a session that fetches feature flags; `claude -p` and the Agent SDK run the hooks and draw
  nothing; a cloud session runs the hooks of a plugin that reaches it and draws nothing; Remote Control draws in the
  terminal on the person's machine. [DOC S-oawin5n2]
- A mod runs with the user's permissions and is not sandboxed: it can read and write files the user can, start
  programs, make network requests, read environment variables and settings, see every prompt and tool call and change
  them. A process a mod starts runs outside the Bash sandbox. A mod cannot change what the permission prompt shows.
  [DOC S-oawin5n2]
- `claude plugin validate <dir>` prints a `hooks:` line (the events the mod handles) and a `calls:` line (the mods API
  methods its code calls) without running it, and Claude Code refuses to load a mod that uses the mods API in a way the
  command cannot read. [DOC S-ho47nrnt]
- Turning mods off: disable the plugin in `/plugin` (one mod), start with `--safe-mode` (every installed mod for one
  session), or set `"disableAllHooks": true` in `~/.claude/settings.json` (every installed mod, every session, and the
  settings hooks and a custom status line too). `/plugin` shows a dim line such as "1 mod active" with the names.
  [DOC S-oawin5n2]

### How a project or a user loads one
- A folder under `~/.claude/skills/` or the project's `.claude/skills/` that holds a `.claude-plugin/plugin.json` loads
  as a plugin in every session with no flag and no install step; its id is `<name>@skills-dir`. `claude plugin init`
  scaffolds one under `~/.claude/skills/`; a plugin for everyone in one repository is the same layout made by hand at
  `<project>/.claude/skills/<name>/`. [DOC S-3peuisvr, S-toe7z3kj]
- A project-scope plugin in `.claude/skills/` loads only after the workspace trust dialog is accepted for that folder
  ("Trusting a parent folder or running with `-p` isn't enough"). Claude Code reads the `.claude/skills/` of the
  session's primary working directory only and does not search parent directories for plugins, so a session started in a
  subdirectory does not load a plugin kept at the repository root. [DOC S-toe7z3kj]
- For a project-scope plugin the page lists three restrictions on components that run code: MCP servers go through the
  per-server approval of a project `.mcp.json`, MCP servers declared as a bundle or from a file outside the plugin
  directory are skipped, and background monitors do not load. The list does not name hooks or a hooks module, and no
  mods page read says whether a project-scope mod's hooks module loads before or after trust. [DOC S-toe7z3kj]
- `--plugin-dir <directory>` loads a plugin directory for one session and reloads its hooks module when the file is
  saved; `CLAUDE_CODE_PLUGIN_DIRS` loads directories for apps that take no flag (`:` separated, `;` on Windows).
  [DOC S-mvuodgli]

### Pane and band
- A pane is a sidebar beside the transcript in a wide fullscreen terminal, or a framed region above the prompt
  otherwise; several open panes each get a tab. The band is a strip directly above the prompt input, always there and
  shared by every mod; a hook's returned tree replaces what mods after it draw there, and `await next(e)` placed among
  the children of a `Box` keeps theirs. Both are empty until a mod fills them. [DOC S-y5j64svc]
- A `ui.render` hook runs for every render site unless filtered: `on('ui.render', { component: 'Pane' }, ...)` runs for
  panes and checks `e.requestId`, which is the `id` the pane was opened with; `{ component: 'AbovePrompt' }` draws in
  the band. `e.surface` says which app draws. [DOC S-y5j64svc, S-mvuodgli]
- Width and height to draw to: a `Pane` and the band draw to `e.props.bodyColumns`; a pane beside the transcript
  (`placement: 'dock'`) has `e.props.scroll.bodyRows` rows; a pane above the prompt (`placement: 'inline'`) grows with
  its tree up to a limit, and a taller tree scrolls as a whole. `e.viewport` (`columns`, `rows`, `isFullscreen`) is absent
  until the app has measured its window, and its `rows` is the whole window's height. [DOC S-mvuodgli]
- Claude Code runs a `ui.render` hook again when the site's props change or the terminal width changes; it does not run
  it on a timer and cannot see a module variable change, so a mod calls `$.ui.invalidate('ui.render')` after its data
  changes. Redraws are throttled to 10 a second, or 30 in the terminal for the visible pane, the expanded band and the
  hint line under the prompt; calls that come sooner are coalesced. [DOC S-y5j64svc, S-mvuodgli]
- `$.ui.open({ id, title, focus, closeOnEscape, holdToasts, rows, columns })` opens a pane and `$.ui.close({ id })`
  closes it; `focus`, `closeOnEscape` and `holdToasts` accept only `true` (`false` throws), `rows` is the height asked for
  above the prompt (default a third of the space), `columns` the width asked for beside the transcript, and the VS Code
  extension ignores both. A command that opens a pane while Claude is working must be registered with
  `immediate: true`. [DOC S-y5j64svc]
- A pane a mod opens by itself (from a timer or a `turn.start` hook) appears only in a terminal at least 144 columns
  wide, or 110 after the user has opened that pane once; a pane opened by something the user did (a command, a button)
  appears at any width. `$.ui.open` resolves to `{ isPlaced: true }`, or `{ isPlaced: false, reason }` while the pane waits
  for the user to open it or for a wider terminal. [DOC S-y5j64svc, S-mvuodgli]
- In the VS Code extension a panel 800 pixels or wider docks panes beside the conversation (`placement: 'dock'`,
  `e.viewport.isFullscreen` true); a narrower panel draws them above the prompt box (`placement: 'inline'`) with 12 rows
  before scrolling. [DOC S-y5j64svc]

### Timers, processes and showing something without a turn
- `$.clock.every(ms, fn)` and `$.clock.after(ms, fn)` replace `setInterval` and `setTimeout` (the hooks module has no
  timer globals or Node.js APIs) and return a timer with `cancel()`. Work that outlives one event starts them from a
  `session.start` hook; the timer's callback runs outside any event, between turns, starts no turn, and when it throws
  the error goes to the debug log and the timer runs again at the next interval. Timers stop when the module reloads.
  [DOC S-sao3dfcq, S-y5j64svc]
- `session.start` fires once for each loaded mod before the first prompt and again after a reload of that mod, not after
  `/clear`, `/resume` or `/branch`. A hook's own execution time for one event is limited to 10 seconds, not counting time
  inside `next` or a mods API call other than `$.clock.sleep`. [DOC S-mvuodgli]
- `$.process.run(['cmd', 'arg'])` takes an argument list and uses no shell; it resolves to `{ exitCode, stdout, stderr }`
  whatever the exit code and rejects if the program cannot start or is still running at the timeout, which is 30 seconds
  by default and 10 minutes at most. `$.process.spawn` streams a long-running command's output. [DOC S-sao3dfcq, S-mvuodgli]
- Showing something without starting a turn: `$.ui.status(text)` is one line under the prompt that stays until changed,
  starting with a warning mark and the mod's name; `$.ui.toast(text)` is a toast with the mod's name, shown 4 seconds
  unless `{ timeoutMs }` is passed; `$.ui.log(text)` is a dim line in the transcript that Claude does not read. [DOC S-sao3dfcq, S-mvuodgli]

### What the model reads
- A `prompt.submit` hook sees each prompt before the turn starts: `next({ ...e, text })` rewrites it (the transcript and
  history show the new text), `next({ ...e, context: [...(e.context ?? []), extra] })` "adds text only Claude reads, after
  the prompt" (the message looks the same in the transcript), and `{ drop: reason }` stops it. [DOC S-4vxgduip]
- `$.prompt.submit({ text })` starts a turn from a background job: Claude reads the text after a sentence that names the
  mod as the sender, and `asUser: true` sends it as the user's own words. The call waits until the session is idle and
  resolves when the new turn starts. [DOC S-sao3dfcq]
- `$.session.send({ to, text })` sends a plain-text message to another session, a subagent or a teammate; nothing
  appears in the sending session and the receiver's Claude reads the text. `$.session.messages()` returns the newest
  4,096 entries of the transcript as `{ role, text, toolUses }`. [DOC S-sao3dfcq, S-mvuodgli]
- A `session.append` hook runs once for each row the conversation keeps (a prompt, a response block, a tool result, a
  notice) before it is stored and can rewrite the row's text blocks or a `tool_result` block's `content`; the namespace
  table lists an `append` method on `$.session`, and the test kit's `mock.session(on).appended()` lists the rows a mod
  added with `$.session.append` (Claude Code 2.1.293 or later). [DOC S-mvuodgli, S-kppz7qns]
- No page read states the `role` of a row added with `$.session.append`, whether the model reads it, or whether the
  person sees it in the transcript; looked in the mods overview, interface, api, events, reference, test and admin
  pages, 2026-10-18. [UNK: the published pages name the method and the test mock only]
- `session.start` receives `surface` and `isInteractive` in the test kit's call
  `$.session.start({ surface: 'terminal', isInteractive: true, cwd: '/work' })`, and `$.session` lists `surfaces`; the
  prose of the pages read does not say what `isInteractive` is for `claude -p` or the SDK, though the where-mods-run
  table says a mod draws in neither. [DOC S-kppz7qns, S-oawin5n2]

## Reference
- Mods overview: https://code.claude.com/docs/en/plugins/mods/overview
- Draw in the interface: https://code.claude.com/docs/en/plugins/mods/interface
- Use the mods API: https://code.claude.com/docs/en/plugins/mods/api
- React to events: https://code.claude.com/docs/en/plugins/mods/events
- Mods reference (limits, render sites): https://code.claude.com/docs/en/plugins/mods/reference
- Test a mod: https://code.claude.com/docs/en/plugins/mods/test
- Manage mods for your organization: https://code.claude.com/docs/en/plugins/mods/admin
- Related articles: [plugins.md](plugins.md), [hooks.md](hooks.md), [statusline.md](statusline.md),
  [terminal-split-pane.md](terminal-split-pane.md).

## Examples
- SNIPPET: a hooks module that opens a pane at session start and redraws it once a second; context: Claude Code 2.1.287
  or later in an interactive terminal, `hooks/hooks.json` pointing at this file; checked: no [DER S-y5j64svc, S-sao3dfcq]
  (assembled from the page's `$.ui.open`, `ui.render` filter and `$.clock.every` examples)

```javascript
export function register(on) {
  on('session.start', async ($, e, next) => {
    await $.ui.open({ id: 'monitor', title: 'Monitor' })
    $.clock.every(1000, () => $.ui.invalidate('ui.render'))
    return next(e)
  })
  on('ui.render', { component: 'Pane' }, async ($, e, next) => {
    if (e.requestId !== 'monitor') return next(e)
    const { Box, Text } = $.ui.resolve(e)
    return Box({ children: [Text({ children: ['width: ' + e.props.bodyColumns] })] })
  })
}
```
