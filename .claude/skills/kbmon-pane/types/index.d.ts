export type KbmonView = { text: string; columns: number }

declare module 'claude-code' {
  interface PluginState {
    'kbmon-pane': { view: KbmonView | null; fingerprint: string | null }
  }
}
