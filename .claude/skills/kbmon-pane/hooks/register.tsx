import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, Timer } from 'claude-code'

import type { KbmonView } from '../types'

const PANE = 'kbmon'
const REFRESH_MS = 60_000
const SETTLE_MS = 1_000
// A shared snapshot is served up to this old (the refresh period less a slack for timer jitter), so a pane's own next
// timer run finds it due, while another session's pane that falls due meanwhile reuses it.
const SHARED_MAX_AGE_S = (REFRESH_MS - 5_000) / 1000
const FIRST_MS = 1_500
const RUN_MS = 120_000
const DEFAULT_COLUMNS = 80
const NEEDS = 'needs you: '
const LAUNCHERS = [['python3'], ['python'], ['py', '-3']]

const view = atom({ plugin: 'kbmon-pane', key: 'view' } as const, null)
const fingerprint = atom({ plugin: 'kbmon-pane', key: 'fingerprint' } as const, null)

let launcher = 0
let columns = DEFAULT_COLUMNS
let inFlight = false
let isStale = false
let lastAlerts: string | null = null
let lastRow: string | null = null
let lastNeeds: Set<string> | null = null
let settle: Timer | undefined

// The text of the alert rows above kbmon's header, without the time each is "since": it changes when the alert set
// does, so the receipt (a second kbmon run) is asked for only then.
function alertsOf(text: string): string {
  return (text.startsWith('kbmon · ') ? '' : text.split('\nkbmon · ')[0])
    .split('\n')
    .filter(line => line.startsWith('!! '))
    .map(line => line.replace(/ — since .*$/, ''))
    .join('\n')
}

// One kbmon.py run, with Python found as python3, python or py -3; the stdout, or the reason it gave none.
async function kbmon($: EngineInterface, flags: string[], width: number): Promise<string> {
  let reason = 'no Python found (python3, python, py -3)'
  for (let step = 0; step < LAUNCHERS.length; step += 1) {
    const which = (launcher + step) % LAUNCHERS.length
    const argv = [...LAUNCHERS[which], '_tools/kbmon.py', ...flags]
    try {
      const ran = await $.process.run(argv, { env: { COLUMNS: String(width) }, timeoutMs: RUN_MS })
      // kbmon exits 1 while an alert is on; a missing or stub Python gives no output.
      if (ran.exitCode <= 1 && ran.stdout.trim() !== '') {
        launcher = which

        return ran.stdout
      }
      reason = ran.stderr.trim().split('\n').slice(-1)[0] || `${argv[0]} exited ${ran.exitCode}`
    } catch (error) {
      reason = String(error)
    }
  }
  throw new Error(reason)
}

// The row of the text that starts with kbmon's needs-you line, or null.
function needsRowOf(text: string): string | null {
  return text.split('\n').find(line => line.startsWith(NEEDS)) ?? null
}

// The entries of a needs-you line: split at `; `, without the age mon_needs.line appends to a run, overlap or orphan
// entry, without the figure of a disk entry (`disk 9.4% free`) or of a delivery or fast-forward cause, and without the
// `not read: PANELS` suffix, so only an entry that appears, goes or changes its kind differs.
// `complete` is false for a line with the suffix: the panel it names says nothing about what waits.
const AGE = String.raw`\d+[dhms](?:\d+[hms])?`
const NOT_READ = 'not read: '
const CAUSE = /^(query-log delivery refused: |checkout cannot fast-forward to origin\/main: )(.*)$/

function entriesOf(line: string): { entries: Set<string>; complete: boolean } {
  const parts = (line.startsWith(NEEDS) ? line.slice(NEEDS.length) : line).split('; ')
  const complete = !parts[parts.length - 1].startsWith(NOT_READ)
  const entries = new Set<string>()
  for (const part of parts) {
    if (part === 'nothing' || part.startsWith(NOT_READ)) {
      continue
    }
    entries.add(
      part
        .replace(new RegExp(`^(orphan pid \\S+) \\(${AGE}(?:, in (.*))?\\)$`), (_, pid: string, where?: string) =>
          where === undefined ? pid : `${pid} in ${where}`,
        )
        .replace(new RegExp(`^(overlap .* undecided) for ${AGE}$`), '$1')
        .replace(new RegExp(`^(\\S+ (?:blocked(?: on gates? .*)?|run failed.*|landing refused.*)), ${AGE}$`), '$1')
        .replace(/^disk [\d.]+% free$/, 'disk free')
        .replace(CAUSE, (_, head: string, why: string) => `${head}${why.replace(/\d+(?:\.\d+)?/g, '#')}`),
    )
  }

  return { entries, complete }
}

// Tells the person when an entry of the needs-you line appears, goes or changes its kind. The first complete reading is
// the baseline, and a line with the not-read suffix before it tells nothing. A line with a not-read suffix tells only the entries new to the baseline and never lowers it, so a panel
// that timed out and the entries returning are no news; a complete line replaces the baseline, and `nothing` is not
// told. The pane's row is cut at its width, so the whole line comes from `--status all`, asked for when the row changed
// or was cut; a cut row with no whole line from it is left unread. The call is not awaited, so a slow Notification hook holds no refresh. A call that rejects or answers
// `isSent: false` is no error: the pane and the receipt go on, and the next change is tried again.
async function notifyNeeds($: EngineInterface, text: string, width: number): Promise<void> {
  const row = needsRowOf(text)
  if (row === null || (row === lastRow && lastNeeds !== null && !row.endsWith('\u2026'))) {
    return
  }
  let line = row
  try {
    const first = (await kbmon($, ['--status', 'all'], width)).split('\n')[0]
    if (first.startsWith(NEEDS)) {
      line = first
    } else if (row.endsWith('…')) {
      // No whole line for a cut row: its last part is a cut entry, not an entry, so the row stays unread.
      return
    }
  } catch {
    // The row stays unread, so the next refresh asks again.
    return
  }
  const before = lastNeeds
  const { entries, complete } = entriesOf(line)
  lastRow = row
  if (before === null) {
    // A first line with the suffix says nothing of what waited before: the baseline waits for a complete line.
    lastNeeds = complete ? entries : null
    return
  }
  const isNew = [...entries].some(entry => !before.has(entry))
  const isGone = [...before].some(entry => !entries.has(entry))
  lastNeeds = complete ? entries : new Set([...before, ...entries])
  if (entries.size === 0 || !(isNew || (complete && isGone))) {
    return
  }
  // Not awaited: the user's Notification hooks run first and can take long, and the refresh holds `inFlight` until it ends.
  void (async () => {
    try {
      await $.ui.notify(line)
    } catch {
      // Another mod's hook denied it or the terminal write failed.
    }
  })()
}

async function refresh($: EngineInterface): Promise<void> {
  // The last run is still going: never start another; the width it ran at is checked when it ends.
  if (inFlight) {
    isStale = true

    return
  }
  inFlight = true
  isStale = false
  const width = columns
  try {
    const text = await kbmon($, ['--once', '--shared', '--max-age', String(SHARED_MAX_AGE_S)], width)
    await update($, view, () => ({ text, columns: width }) as KbmonView)
    await notifyNeeds($, text, width)
    const alerts = alertsOf(text)
    if (alerts === lastAlerts) {
      return
    }
    lastAlerts = alerts

    const receipt = JSON.parse(await kbmon($, ['--receipt'], width)) as { line: string; fingerprint: string }
    const before = await read($, fingerprint)
    if (before === receipt.fingerprint) {
      return
    }
    await update($, fingerprint, () => receipt.fingerprint)
    await $.session.append({ message: { type: 'user', content: [{ type: 'text', text: receipt.line }] } })
    if (before !== null) {
      $.ui.toast(receipt.line)
    }
  } catch (error) {
    await update($, view, () => ({ text: `kbmon: ${String(error)}`, columns: width }) as KbmonView)
  } finally {
    inFlight = false
    if (isStale && columns !== width) {
      void refresh($)
    }
  }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    // A -p run or the SDK has no person at the prompt: the mod does nothing there.
    if (!e.isInteractive) {
      return next(e)
    }
    await $.command.register({ name: 'kbmon', description: 'Open the kbmon pane' })
    void $.ui.open({ id: PANE, title: 'kbmon' })
    // The first run waits for the pane's first drawing to say its width.
    $.clock.after(FIRST_MS, () => void refresh($))
    $.clock.every(REFRESH_MS, () => void refresh($))

    return next(e)
  })

  on('command.run', { command: 'kbmon' }, async $ => {
    await $.ui.open({ id: PANE, title: 'kbmon' })
    void refresh($)

    return { text: 'kbmon pane opened.' }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    columns = e.props.bodyColumns
    const shown = await read($, view)
    // A resize clips the old layout at once; kbmon lays it out again at the new width once the resize settles.
    if (shown !== null && shown.columns !== columns) {
      settle?.cancel()
      settle = $.clock.after(SETTLE_MS, () => void refresh($))
    }
    const lines = shown === null ? ['kbmon: reading the first snapshot...'] : shown.text.split('\n')

    return (
      <Box flexDirection="column">
        {lines.map(line => (
          <Text wrap="truncate-end">{line === '' ? ' ' : line}</Text>
        ))}
      </Box>
    )
  })
}
