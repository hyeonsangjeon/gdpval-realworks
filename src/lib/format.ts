// Small formatting helpers shared by the dashboard's diagnostic UI.

/** Format a 0–1 ratio (or already-pct number) as "NN.N%". */
export function fmtPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  const num = v <= 1 ? v * 100 : v
  return `${num.toFixed(1)}%`
}

/** Format seconds as "Ns" under 60s, "N.Nm" above. */
export function fmtLatency(sec: number | null | undefined): string {
  if (sec == null || Number.isNaN(sec) || sec <= 0) return '—'
  if (sec < 60) return `${sec.toFixed(0)}s`
  return `${(sec / 60).toFixed(1)}m`
}
