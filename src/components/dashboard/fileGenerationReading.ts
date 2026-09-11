/**
 * How to read a file-generation rate without inventing a measurement.
 *
 * `step5_validate` counts the tasks a run owed a file for, and the dashboard
 * divides by that count. When the count is zero there is nothing to divide by,
 * and the old form on both surfaces —
 *
 *   needs_files_total > 0 ? ((succeeded / needs_files_total) * 100) : 0
 *
 * — answered that with `0`, which is also the value a run earns by failing
 * every file it was asked for. Four full 220-task runs published a 0% file
 * generation rate that way (`exp013`, `exp014`, `exp025`, `exp026`); none of
 * them generated a file badly, because none of them was asked for one.
 *
 * A third state sits underneath both: `step6_report` writes `null` into every
 * field of `file_generation` when `validate_stats.json` could not be read, so a
 * payload can carry no record of a rate at all. That is not a zero denominator
 * either — it is not knowing what the denominator was.
 *
 * Deliberately free of imports, so
 * `scripts/__tests__/file-generation-denominator.test.mjs` can execute this
 * decision rather than pattern-match the JSX around it. `readWowRate` in
 * `../wow/rateReading` is the same rule for the `summary.wow` pass rates.
 */

/** What the published file-generation figure is actually standing on. */
export type FileGenerationStanding =
  /** A denominator was recorded and it is non-zero. The rate means what it says. */
  | 'measured'
  /** A denominator was recorded and it is zero. No task owed a file. */
  | 'none-required'
  /** No denominator was recorded, so it is not known which of the two above this is. */
  | 'not-recorded'
  /** The run published no `file_generation` block at all. */
  | 'absent'

export interface FileGenerationReading {
  standing: FileGenerationStanding
  /** What goes in the value slot. A percentage only when one was measured. */
  value: string
  /** The bar length as a 0–1 fraction, or `null` when there is nothing to draw. */
  fraction: number | null
  /** Whether this figure may be compared against another run's. */
  comparable: boolean
  /** Why the figure is not a rate, when it is not. */
  caveat?: string
}

/** The producer's field names, in one place so a rename cannot go unnoticed. */
export interface FileGenerationLike {
  needs_files_total?: number | null
  files_succeeded?: number | null
  files_failed?: number | null
  files_absent?: number | null
  /** Read but not divided by: a count, rendered through `readFileGenerationCount`. */
  dummy_files_created?: number | null
}

/** Which of the two outcomes the rate is being taken over. */
export type FileGenerationOutcome = 'succeeded' | 'failed'

const OUTCOME_FIELD: Record<FileGenerationOutcome, keyof FileGenerationLike> = {
  succeeded: 'files_succeeded',
  failed: 'files_failed',
}

const isNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value)

/**
 * Read one file-generation rate against the denominator it was divided by.
 *
 * A genuine zero still reads as `0.0%`: with a denominator to divide by, that
 * is a measurement, and this rule must not hide the run that really did fail
 * every file it owed.
 */
export function readFileGenerationRate(
  fg: FileGenerationLike | null | undefined,
  outcome: FileGenerationOutcome,
): FileGenerationReading {
  if (!fg) {
    return {
      standing: 'absent',
      value: 'not recorded',
      fraction: null,
      comparable: false,
      caveat: 'This run published no file generation record.',
    }
  }

  const total = fg.needs_files_total
  if (!isNumber(total)) {
    return {
      standing: 'not-recorded',
      value: 'not recorded',
      fraction: null,
      comparable: false,
      caveat:
        'This run recorded no count of the tasks that required a file, so ' +
        'there is no denominator to read a rate against.',
    }
  }

  if (total === 0) {
    // Not `0%`, and not a zero-length bar either: a bar drawn at zero is read
    // off the chart as the worst possible result, which is the one thing this
    // run did not measure.
    return {
      standing: 'none-required',
      value: 'n/a',
      fraction: null,
      comparable: false,
      caveat:
        'No task in this run required a file, so file generation was not ' +
        `measured. This is not a 0% ${outcome === 'failed' ? 'failure' : 'generation'} rate.`,
    }
  }

  const counted = fg[OUTCOME_FIELD[outcome]]
  if (!isNumber(counted)) {
    return {
      standing: 'not-recorded',
      value: 'not recorded',
      fraction: null,
      comparable: false,
      caveat:
        `This run required a file for ${total} task${total === 1 ? '' : 's'} ` +
        'but recorded no outcome for them.',
    }
  }

  const fraction = counted / total
  return {
    standing: 'measured',
    value: `${(fraction * 100).toFixed(1)}%`,
    fraction,
    comparable: true,
    caveat: undefined,
  }
}

/** A count that may itself be absent, rendered without turning that into a zero.
 *
 * The same payload that carries no denominator carries no counts, and
 * `{fg.files_failed}` on a `null` renders as an empty cell that reads as one
 * more zero beside the others.
 */
export function readFileGenerationCount(value: number | null | undefined): string {
  return isNumber(value) ? String(value) : 'not recorded'
}

/**
 * Which of the two roll-ups a run carries, and which one is being read.
 *
 * A run whose step 5 was skipped publishes an all-`null` `file_generation`. The
 * count is still recoverable from its artifact — `recover_file_rollup.py` runs
 * step 5's own `validate()` against it offline — and lands beside the null as
 * `file_generation_recovered` rather than inside it, so the run goes on saying
 * what it recorded.
 *
 * Which means a reader who takes `file_generation` alone sees `not recorded`
 * for a run whose number is sitting in the same payload. This picks between
 * them, and says which one it picked; it never merges fields across the two,
 * because half a measurement and half a reconstruction is neither.
 */
export interface ResolvedFileGeneration {
  /** The block to read counts and rates from, or nothing to read. */
  fg: FileGenerationLike | null | undefined
  /** True when the run recorded no denominator and this was rebuilt after it. */
  recovered: boolean
  /** The run the reconstruction was made from, when it is one. */
  sourceRunId?: string
  /** Which of step 5's four gates skipped the count, when it is one. */
  skippedBy?: string
}

/** The two fields, named once so a rename cannot go unnoticed. */
export interface ReportWithFileGeneration {
  file_generation?: FileGenerationLike | null
  file_generation_recovered?:
    | (FileGenerationLike & {
        provenance?: { source_run_id?: string; step5_skipped_by?: string }
      })
    | null
}

export function resolveFileGeneration(
  report: ReportWithFileGeneration | null | undefined,
): ResolvedFileGeneration {
  const measured = report?.file_generation
  // A measurement taken during the run always wins, even against a recovery
  // that disagrees with it. Preferring the reconstruction would make the
  // recovery tool able to overwrite a real count by being run twice.
  if (isNumber(measured?.needs_files_total)) {
    return { fg: measured, recovered: false }
  }

  const recovered = report?.file_generation_recovered
  if (isNumber(recovered?.needs_files_total)) {
    return {
      fg: recovered,
      recovered: true,
      sourceRunId: recovered?.provenance?.source_run_id,
      skippedBy: recovered?.provenance?.step5_skipped_by,
    }
  }

  // Neither: hand back whichever block exists so the reading below can tell
  // `absent` from `not-recorded`, which are different things to a reader.
  return { fg: measured ?? recovered ?? undefined, recovered: false }
}

/** One line saying a figure was rebuilt after the run, for rendering beside it. */
export function recoveredNote(resolved: ResolvedFileGeneration): string | undefined {
  if (!resolved.recovered) return undefined
  const from = resolved.sourceRunId ? ` from run ${resolved.sourceRunId}` : ''
  const why = resolved.skippedBy ? ` (step 5 was skipped: ${resolved.skippedBy})` : ''
  return `Reconstructed after the run${from}${why}. The run itself recorded no count.`
}
