import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, Timer } from 'claude-code'

import type { KbmonView } from '../types'

const PANE = 'kbmon'
const REFRESH_MS = 60_000
const SETTLE_MS = 1_000
const FIRST_MS = 1_500
const RUN_MS = 120_000
const DEFAULT_COLUMNS = 80
const LAUNCHERS = [['python3'], ['python'], ['py', '-3']]

const view = atom({ plugin: 'kbmon-pane', key: 'view' } as const, null)
const fingerprint = atom({ plugin: 'kbmon-pane', key: 'fingerprint' } as const, null)

let launcher = 0
let columns = DEFAULT_COLUMNS
let inFlight = false
let isStale = false
let lastAlerts: string | null = null
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
async function kbmon($: EngineInterface, flag: string, width: number): Promise<string> {
  let reason = 'no Python found (python3, python, py -3)'
  for (let step = 0; step < LAUNCHERS.length; step += 1) {
    const which = (launcher + step) % LAUNCHERS.length
    const argv = [...LAUNCHERS[which], '_tools/kbmon.py', flag]
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
    const text = await kbmon($, '--once', width)
    await update($, view, () => ({ text, columns: width }) as KbmonView)
    const alerts = alertsOf(text)
    if (alerts === lastAlerts) {
      return
    }
    lastAlerts = alerts

    const receipt = JSON.parse(await kbmon($, '--receipt', width)) as { line: string; fingerprint: string }
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
