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

/**
 * Format a Self-QA score as "N/10", or an em dash when there is no score.
 *
 * null here means the figure was never measured — every task errored, so
 * nothing was scored — not that it was measured and came out at zero. The two
 * read identically once "0/10" is on the page, and only one of them is a
 * statement about the model. A score that really is zero still prints as zero;
 * the dash is only ever for the absence of one.
 *
 * `digits` is left off by default so callers that never rounded keep printing
 * the number they always printed. Only pass it where the call site already had
 * a `.toFixed()`.
 */
export function fmtScore(v: number | null | undefined, digits?: number): string {
  if (v == null || Number.isNaN(v)) return '—'
  return `${digits == null ? v : v.toFixed(digits)}/10`
}
