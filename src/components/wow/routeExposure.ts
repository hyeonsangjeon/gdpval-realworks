/**
 * How much of a published average rests on each sub-judge — and in particular
 * on the one that was measured and found not to work.
 *
 * Kept apart from the card that renders it, and deliberately free of imports,
 * so `scripts/__tests__/route-exposure.test.mjs` can execute the decision
 * itself rather than pattern-match the JSX around it. The same arrangement as
 * `./highMagnitudeReading`, and for the same reason: a rule about when *not* to
 * print a number is only worth having if something checks it.
 */

/**
 * The route whose trustworthiness is in question.
 *
 * The audio sub-judge was run against synthetic clips whose answers were known.
 * It scored 48.6% — a coin — with a discrimination of exactly 0.00 by item
 * majority, a false-negative rate of 83.3% on true claims, higher confidence
 * when it was wrong than when it was right, and 11 of 12 items answered
 * identically across three repeats, so repetition can never surface the error.
 * Nothing about that is visible in a score, which is why the size of the route
 * is published beside it.
 */
export const AUDIO_ROUTE = 'audio'

/**
 * `false` means the run recorded no route at all, and is not the same statement
 * as a route that came back empty. Eleven of the eighteen item-level grades
 * published today are in the first state: they predate routing, so every item
 * carries `routing_modality: null`. Reading those as "no audio" would turn
 * "never asked" into "asked and found none".
 */
export type RouteExposureState = 'not-recorded' | 'measured'

export interface RouteRow {
  route: string
  items: number
  scoredItems: number
  tasks: number
  /** Percentage of the run's scored rubric weight, or null when there is none. */
  scoredMaxShare: number | null
}

export interface RouteComposition {
  recorded?: boolean
  items?: Record<string, number> | null
  scored_items?: Record<string, number> | null
  scored_max_score?: Record<string, number> | null
  tasks?: Record<string, number> | null
  total_items?: number | null
  scored_max_score_total?: number | null
  unrecorded_items?: number | null
  unrecorded_failing_items?: number | null
  /**
   * `mixed` items with an audio child, counted apart from `items.audio`.
   *
   * Both this rule and the producer count a `mixed` item once, under `mixed`.
   * Its children can carry routes of their own, so an audio child is
   * audio-decided weight that the `audio` row does not cover. 0 across every
   * published grade today — stated anyway, so the day it is not 0 the reader
   * is told instead of the shortfall passing silently.
   */
  audio_in_mixed_items?: number | null
  payload_agrees?: boolean | null
}

export interface RouteExposureReading {
  state: RouteExposureState
  /** What goes in the big slot. Never a bare `0%`. */
  value: string
  /** What that number is a share of, or why it is not one. */
  denominator: string
  /** Present when the composition is real but cannot be read at face value. */
  caveat?: string
  /** Every route the run knows about, largest share first. */
  rows: RouteRow[]
}

const finite = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x)
const count = (map: Record<string, number> | null | undefined, key: string): number => {
  const value = map?.[key]
  return finite(value) ? value : 0
}

/** `12.3%`, or `<0.01%` for a share too small to round to two places. */
function sharePct(part: number, whole: number): string {
  return formatRouteShare((part / whole) * 100)
}

/**
 * A percentage, or `—` when there is none to take.
 *
 * `<0.01%` rather than `0.00%` below two decimal places, because a route that
 * decided something printed as a flat zero is the same mistake this card exists
 * to stop — one step smaller.
 */
export function formatRouteShare(share: number | null | undefined): string {
  if (!finite(share)) return '—'
  if (share > 0 && share < 0.01) return '<0.01%'
  return `${share.toFixed(2)}%`
}

/**
 * Turn a route composition into something a reader can act on.
 *
 * Three outcomes, kept apart on purpose:
 *
 *   - the run recorded no route → `not recorded`, and no share is invented;
 *   - the run recorded routes and none went to audio → `none`, a measured zero,
 *     qualified by the unrouted remainder if there is one;
 *   - the run routed items to audio → the share of scored rubric weight that
 *     rests on it.
 *
 * The unrouted remainder is never silently dropped. On the official 220-task
 * grade it is 964 items, every one of them an item the judge failed or errored
 * on, so the routed population it is missing from is missing failures
 * specifically — a share computed over it reads lower than the truth.
 *
 * Neither is the one thing these counts structurally cannot see: a `mixed` item
 * is one item under `mixed`, so an audio child inside it is audio-decided
 * weight the audio row does not cover. 0 across every published grade today,
 * and said out loud the moment it is not.
 */
export function readRouteExposure(
  composition: RouteComposition | null | undefined,
): RouteExposureReading {
  const unrecorded = finite(composition?.unrecorded_items)
    ? (composition?.unrecorded_items as number)
    : 0
  const unrecordedFailing = finite(composition?.unrecorded_failing_items)
    ? (composition?.unrecorded_failing_items as number)
    : 0

  if (!composition || composition.recorded !== true) {
    return {
      state: 'not-recorded',
      value: 'not recorded',
      denominator:
        unrecorded > 0
          ? `None of this run's ${unrecorded} rubric item(s) recorded which ` +
            'sub-judge decided it, so which routes it used cannot be told from ' +
            'the payload. That is not the same as having used none.'
          : 'This run did not record which sub-judge decided each rubric item, ' +
            'so which routes it used cannot be told from the payload. That is ' +
            'not the same as having used none.',
      rows: [],
    }
  }

  const items = composition.items ?? {}
  const scoredItems = composition.scored_items ?? {}
  const scoredMax = composition.scored_max_score ?? {}
  const tasks = composition.tasks ?? {}
  const maxTotal = finite(composition.scored_max_score_total)
    ? (composition.scored_max_score_total as number)
    : Object.values(scoredMax).reduce((sum, x) => sum + (finite(x) ? x : 0), 0)

  const rows: RouteRow[] = Object.keys(items)
    .map((route) => ({
      route,
      items: count(items, route),
      scoredItems: count(scoredItems, route),
      tasks: count(tasks, route),
      scoredMaxShare: maxTotal > 0 ? (count(scoredMax, route) / maxTotal) * 100 : null,
    }))
    .sort((a, b) => (b.scoredMaxShare ?? 0) - (a.scoredMaxShare ?? 0) || b.items - a.items)

  // The remainder is stated whenever it exists, whatever the audio answer turns
  // out to be, because it bounds how much either answer can be trusted.
  let caveat: string | undefined
  if (unrecorded > 0) {
    const total = finite(composition.total_items) ? (composition.total_items as number) : 0
    const ofRun = total > 0 ? ` of this run's ${total}` : ''
    caveat =
      `${unrecorded} item(s)${ofRun} recorded no route, so the shares above ` +
      'are shares of the rest.'
    if (unrecordedFailing >= unrecorded && unrecorded > 0) {
      caveat +=
        ' Every one of them is an item the judge failed or errored on, so what ' +
        'is missing is not a random sample — it is failures.'
    } else if (unrecordedFailing > 0) {
      caveat +=
        ` ${unrecordedFailing} of them are items the judge failed or errored ` +
        'on, so what is missing leans towards failures rather than being a ' +
        'random sample.'
    }
  }

  // A `mixed` item is one item under `mixed`, on both sides of this
  // comparison — but its children carry routes too, so an audio child is
  // audio-decided weight the audio row does not cover. Said whichever way the
  // audio answer comes out, since it moves both of them the same direction.
  const audioInMixed = finite(composition.audio_in_mixed_items)
    ? (composition.audio_in_mixed_items as number)
    : 0
  if (audioInMixed > 0) {
    const sentence =
      `${audioInMixed} item(s) routed \`mixed\` were part-decided by an audio ` +
      'child, which the audio row does not count — so the audio share reads ' +
      'lower here than the work it actually did.'
    caveat = caveat ? `${caveat} ${sentence}` : sentence
  }

  const audioItems = count(items, AUDIO_ROUTE)
  if (audioItems === 0) {
    return {
      state: 'measured',
      // Not a flat "none" when a mixed item was part-decided by an audio
      // child: the audio row is empty, the sub-judge is not.
      value: audioInMixed > 0 ? 'none directly' : 'none',
      denominator:
        unrecorded > 0
          ? 'No rubric item whose route was recorded went to the audio ' +
            'sub-judge. Items that recorded no route are not covered by that.'
          : 'No rubric item in this run went to the audio sub-judge.',
      ...(caveat ? { caveat } : {}),
      rows,
    }
  }

  const audioScored = count(scoredItems, AUDIO_ROUTE)
  const audioTasks = count(tasks, AUDIO_ROUTE)
  const value = maxTotal > 0 ? sharePct(count(scoredMax, AUDIO_ROUTE), maxTotal) : 'no share'
  const denominator =
    maxTotal > 0
      ? `of this run's scored rubric weight was decided by the audio ` +
        `sub-judge — ${audioScored} scored item(s) across ${audioTasks} task(s).`
      : `${audioScored} scored item(s) across ${audioTasks} task(s) went to the ` +
        'audio sub-judge, but this run carries no positive rubric weight to ' +
        'take a share of.'

  return {
    state: 'measured',
    value,
    denominator,
    ...(caveat ? { caveat } : {}),
    rows,
  }
}
