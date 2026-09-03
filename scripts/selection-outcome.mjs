// Why a graded task ended up where it did.
//
// The grade JSON already reports its headline honestly: avg_score_pct averages
// the tasks the grader actually scored, and tasks the selector refused are
// excluded from it. What the payload does not say out loud is that most of the
// remaining zeros are not the model getting the work wrong. In the exp003
// 220-task run, 24 tasks scored zero and exactly 3 of them were scored zero by
// a judge that had read a deliverable. The other 21 never reached a judge with
// anything to read: six had only the inference stage's failed_to_generate.txt
// placeholder, fourteen produced real files in a format the task did not ask
// for, and one had nothing left after reference files were subtracted out.
//
// Those are four different findings wearing the same red "Zero" badge. This
// module separates them using fields core/deliverable_selector.py already
// writes, so nothing has to be re-graded to tell them apart.
//
// Purely additive by construction: no count the grade JSON publishes is
// recomputed here. A grade file that predates selection_status classifies as
// UNCLASSIFIED and callers gate the whole feature on `covered`, so older
// experiments render exactly as they did before this file existed.

/** @typedef {'scored'|'content_zero'|'inference_failed'|'format_unmet'|'no_deliverable'|'not_selected'|'grading_error'|'score_not_recorded'|'unclassified'} SelectionOutcome */

export const SELECTION_OUTCOME = {
  SCORED: 'scored',
  CONTENT_ZERO: 'content_zero',
  INFERENCE_FAILED: 'inference_failed',
  FORMAT_UNMET: 'format_unmet',
  NO_DELIVERABLE: 'no_deliverable',
  NOT_SELECTED: 'not_selected',
  GRADING_ERROR: 'grading_error',
  // A row carrying no score and no reason for not having one. Every other
  // outcome here answers "why is this not a normal score"; this one answers
  // "we do not know, and the row never said". It is not a zero -- see the
  // comparison in classifyTaskOutcome for why it used to become one.
  SCORE_NOT_RECORDED: 'score_not_recorded',
  UNCLASSIFIED: 'unclassified',
};

// Display order for the zero-reason breakdown: the model's own failures first,
// then the ones the pipeline is responsible for. A reader scanning top-down
// should meet the honest bad news before the excuses.
export const ZERO_OUTCOME_ORDER = [
  SELECTION_OUTCOME.CONTENT_ZERO,
  SELECTION_OUTCOME.FORMAT_UNMET,
  SELECTION_OUTCOME.INFERENCE_FAILED,
  SELECTION_OUTCOME.NO_DELIVERABLE,
  SELECTION_OUTCOME.NOT_SELECTED,
  SELECTION_OUTCOME.UNCLASSIFIED,
];

export const OUTCOME_LABELS = {
  [SELECTION_OUTCOME.SCORED]: 'Scored',
  [SELECTION_OUTCOME.CONTENT_ZERO]: 'Judged zero',
  [SELECTION_OUTCOME.INFERENCE_FAILED]: 'Inference failed',
  [SELECTION_OUTCOME.FORMAT_UNMET]: 'Format not met',
  [SELECTION_OUTCOME.NO_DELIVERABLE]: 'No deliverable',
  [SELECTION_OUTCOME.NOT_SELECTED]: 'Not scored',
  [SELECTION_OUTCOME.GRADING_ERROR]: 'Grading error',
  [SELECTION_OUTCOME.SCORE_NOT_RECORDED]: 'Score not recorded',
  [SELECTION_OUTCOME.UNCLASSIFIED]: 'Unclassified',
};

// Whether the judge ever had a deliverable in front of it. This is the line
// that matters: a zero on the left of it is a verdict, a zero on the right of
// it is a plumbing outcome that happens to be recorded as a score.
const REACHED_JUDGE = new Set([
  SELECTION_OUTCOME.SCORED,
  SELECTION_OUTCOME.CONTENT_ZERO,
]);

// deliverable_selector.py builds this message by concatenation; matching on the
// prefix rather than a loose regex keeps a reworded message from silently
// yielding a half-parsed extension list.
const WRONG_FORMAT_PREFIX =
  'generated files exist but none match requested primary formats:';

const PLACEHOLDER_STEM = 'failed_to_generate';

function basename(path) {
  return String(path).split(/[\\/]/).pop() || '';
}

/** Every file the selector considered, primary targets and support alike. */
export function deliverableFiles(task) {
  const selection = task?.selected_deliverables;
  if (!selection || typeof selection !== 'object') return [];
  const files = [];
  for (const target of selection.primary_targets || []) {
    for (const path of target?.paths || []) {
      if (path) files.push(String(path));
    }
  }
  for (const path of selection.support_artifacts || []) {
    if (path) files.push(String(path));
  }
  return files;
}

// step2 writes failed_to_generate.txt when inference itself never produced a
// file. The selector has no way to know that placeholder is not a deliverable,
// so it reports the task as a format mismatch -- technically true, and
// completely misleading about where the run broke.
function isInferencePlaceholder(files) {
  if (files.length === 0) return false;
  return files.every((file) => basename(file).toLowerCase().startsWith(PLACEHOLDER_STEM));
}

/** Extensions the task demanded, parsed back out of the selector's message. */
export function requiredFormats(selectionError) {
  const message = typeof selectionError === 'string' ? selectionError.trim() : '';
  if (!message.startsWith(WRONG_FORMAT_PREFIX)) return [];
  return message
    .slice(WRONG_FORMAT_PREFIX.length)
    .split(',')
    .map((part) => part.trim().toLowerCase())
    .filter((part) => /^\.[a-z0-9]+$/.test(part));
}

// Formats no text-generating model can produce on its own. Splitting these out
// stops "the model cannot render video" from reading as "the model failed the
// task", which is a different claim and a different fix.
const UNPRODUCIBLE_FORMATS = new Set([
  '.mp4', '.mov', '.avi', '.mkv', '.webm',
  '.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg',
]);

export function formatDemandClass(formats) {
  if (formats.length === 0) return null;
  return formats.every((ext) => UNPRODUCIBLE_FORMATS.has(ext))
    ? 'unproducible_media'
    : 'producible';
}

/**
 * Classify one raw v1 grade task.
 *
 * @param {object} task - a task record straight out of the grade JSON
 * @returns {{outcome: SelectionOutcome, reached_judge: boolean, selection_status: string|null,
 *            required_formats: string[], format_demand: string|null, files: string[],
 *            detail: string}}
 */
export function classifyTaskOutcome(task) {
  const selectionStatus = typeof task?.selection_status === 'string' && task.selection_status
    ? task.selection_status
    : null;
  const selectionError = task?.selection_error ?? null;
  const files = deliverableFiles(task);
  const formats = requiredFormats(selectionError);
  // Finite, not merely typed: the aggregator's row projection gates on
  // Number.isFinite, and if these two disagreed about what counts as a score a
  // row could be labelled "Scored" while the row beside it carried no number.
  const pct = Number.isFinite(task?.pct) ? task.pct : null;
  const hasError = task?.error !== null && task?.error !== undefined && task?.error !== '';

  const base = {
    selection_status: selectionStatus,
    required_formats: formats,
    format_demand: formatDemandClass(formats),
    files,
  };
  const decide = (outcome, detail) => ({
    ...base,
    outcome,
    reached_judge: REACHED_JUDGE.has(outcome),
    detail,
  });

  // Checked before selection_status: a placeholder-only task is reported by the
  // selector as a format mismatch, and that label sends a reader looking for a
  // grading bug instead of an inference failure.
  if (isInferencePlaceholder(files)) {
    return decide(
      SELECTION_OUTCOME.INFERENCE_FAILED,
      'Inference produced no deliverable; only the failed_to_generate placeholder reached grading.',
    );
  }

  if (selectionStatus === 'selection_error') {
    return decide(
      SELECTION_OUTCOME.NOT_SELECTED,
      `The model produced ${files.length} candidate file${files.length === 1 ? '' : 's'}, `
      + 'but the selector could not pick a primary deliverable without guessing, so it '
      + 'declined rather than grade an arbitrary one. Excluded from the average.',
    );
  }

  if (selectionStatus === 'no_generated_candidate') {
    return decide(
      SELECTION_OUTCOME.NO_DELIVERABLE,
      'Nothing remained after the task\'s own reference files were subtracted from the output set.',
    );
  }

  if (selectionStatus === 'wrong_format_primary') {
    const wanted = formats.length ? formats.join(', ') : 'the requested format';
    const detail = formatDemandClass(formats) === 'unproducible_media'
      ? `The task asked for ${wanted}, which a text model cannot render. `
        + `${files.length} supporting file${files.length === 1 ? '' : 's'} were produced instead.`
      : `The task asked for ${wanted} and none of the ${files.length} generated `
        + `file${files.length === 1 ? '' : 's'} matched.`;
    return decide(SELECTION_OUTCOME.FORMAT_UNMET, detail);
  }

  if (hasError) {
    return decide(SELECTION_OUTCOME.GRADING_ERROR, String(task.error));
  }

  // Everything below this line reads `pct` to decide what the row means, so a
  // row that has no `pct` has to be answered before it gets there. Both of the
  // comparisons below are `pct === 0`, and `null === 0` is false, so an absent
  // score used to fall through them and return SCORED -- a claim the row has
  // nothing to support. On grade schema 1.3/1.4 the aggregator's strict
  // validator refuses such a file outright and this is unreachable; on 1.0-1.2,
  // which are checked for the presence of the headline keys and nothing else,
  // this is the only thing between an absent score and the word "Scored".
  //
  // Deliberately not in REACHED_JUDGE: whether a judge ever saw this
  // deliverable is exactly what the missing score fails to say. Deliberately
  // not in ZERO_OUTCOME_ORDER either -- an absent score is not a zero, and
  // listing it as a reason for zeros would reintroduce the confusion by the
  // back door.
  if (pct === null) {
    return decide(
      SELECTION_OUTCOME.SCORE_NOT_RECORDED,
      'This task carries no score. Nothing here says whether it was graded, so it is '
      + 'neither a zero nor a pass -- the record is simply missing.',
    );
  }

  // No selection metadata at all: a grade file written before the selector
  // recorded its reasoning. Guessing here would put invented structure on old
  // experiments, so say plainly that it is unknown.
  if (selectionStatus === null) {
    return pct === 0
      ? decide(SELECTION_OUTCOME.UNCLASSIFIED, 'This grade predates selection reporting; the reason for the zero was not recorded.')
      : decide(SELECTION_OUTCOME.SCORED, '');
  }

  if (pct === 0) {
    return decide(
      SELECTION_OUTCOME.CONTENT_ZERO,
      'A judge read the deliverable and awarded no credit. This is a verdict on the work.',
    );
  }

  return decide(SELECTION_OUTCOME.SCORED, '');
}

/**
 * Roll per-task outcomes up for the summary card.
 *
 * `covered` is the switch the UI gates on: false means this grade carries no
 * selection metadata and the breakdown must not render, so pre-selector
 * experiments keep the exact presentation they have today.
 */
export function summarizeOutcomes(tasks) {
  const list = Array.isArray(tasks) ? tasks : [];
  const outcomes = {};
  for (const key of Object.values(SELECTION_OUTCOME)) outcomes[key] = 0;

  let covered = 0;
  for (const task of list) {
    const { outcome } = classifyTaskOutcome(task);
    outcomes[outcome] += 1;
    if (typeof task?.selection_status === 'string' && task.selection_status) covered += 1;
  }

  const zeroReasons = ZERO_OUTCOME_ORDER
    .filter((outcome) => outcomes[outcome] > 0)
    .map((outcome) => ({
      outcome,
      label: OUTCOME_LABELS[outcome],
      count: outcomes[outcome],
      reached_judge: REACHED_JUDGE.has(outcome),
    }));

  return {
    covered: covered > 0,
    covered_tasks: covered,
    total_tasks: list.length,
    outcomes,
    zero_reasons: zeroReasons,
    // Zeros a judge actually handed down, versus zeros recorded because the
    // deliverable never got in front of one. The gap between these two is the
    // whole reason this module exists.
    judged_zero: outcomes[SELECTION_OUTCOME.CONTENT_ZERO],
    unjudged_zero:
      outcomes[SELECTION_OUTCOME.FORMAT_UNMET]
      + outcomes[SELECTION_OUTCOME.INFERENCE_FAILED]
      + outcomes[SELECTION_OUTCOME.NO_DELIVERABLE],
  };
}
