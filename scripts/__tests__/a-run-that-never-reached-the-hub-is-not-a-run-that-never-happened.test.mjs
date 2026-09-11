/**
 * A run that never reached the hub is not a run that never happened.
 *
 * `aggregate-reports.mjs` finds experiments by listing the committed
 * directories under `batch-runner/results/`, and reads each one's
 * `report_data.json` locally or, failing that, from
 * `huggingface.co/datasets/HyeonSang/<dir>/resolve/main/self_report.json`.
 * `.gitignore` keeps the local copy out of the repository on the stated ground
 * that "report_data.json은 HF Dataset에서 관리" — which was true of every run
 * that came before, because every one of them ran step 7.
 *
 * A run dispatched `dry_run: true` does not. Step 2 makes the paid calls, step
 * 6 writes the full report, and step 7 — the upload — is skipped, so no
 * `HyeonSang/<dir>` dataset is ever created and the fetch above answers 404.
 * With nothing committed and nothing on the hub there is no directory to list
 * either, so the build does not fail: it reports one fewer experiment and goes
 * green. exp034 finished on 2026-09-10 with 22 of 30 tasks succeeding and
 * appeared nowhere.
 *
 * The only other copy is the run artifact, and that expires — `batch-run.yml`
 * sets `retention-days: 30`.
 *
 * So for these runs the committed file is the record, and this file holds the
 * repository to that. It keys on the declaration the report makes about
 * itself rather than on a list of experiment ids, so the next dry run is
 * covered the day its report lands.
 *
 * Nothing here reaches the network.
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';

const ROOT = new URL('../..', import.meta.url).pathname;
const REPORTS_INDEX = join(ROOT, 'public', 'generated', 'reports-index.json');
const RESULTS_DIR = join(ROOT, 'batch-runner', 'results');

/** What step 6 writes into `meta` when the dispatch skipped step 7. */
const NEVER_PUBLISHED = 'dry_run_no_step7';

/** And what it writes when the upload was asked for. */
const PUBLISHED = 'step7_upload_requested';

async function publishedReports() {
  const index = JSON.parse(await readFile(REPORTS_INDEX, 'utf8'));
  assert.ok(Array.isArray(index.reports), 'reports-index.json carries no reports array');
  return index.reports;
}

const neverPublished = (reports) =>
  reports.filter((r) => r.meta?.publication_plan === NEVER_PUBLISHED);

test('a report that says it never published has its data committed', async () => {
  const reports = await publishedReports();

  for (const report of neverPublished(reports)) {
    const dirName = report.meta.experiment_id;
    const path = join(RESULTS_DIR, dirName, 'report', 'report_data.json');

    let committed;
    try {
      committed = JSON.parse(await readFile(path, 'utf8'));
    } catch (err) {
      assert.fail(
        `${report.short_id} declares ${NEVER_PUBLISHED}, so no HuggingFace dataset ` +
          `exists for it and ${path} is the only copy — but it could not be read: ` +
          `${err.message}`,
      );
    }

    assert.equal(
      committed.meta?.experiment_id,
      dirName,
      'the committed report belongs to a different experiment than its directory',
    );
  }
});

test('the corpus still holds a run that never published', async () => {
  // Teeth. If no report declares itself unpublished, the test above passes
  // over an empty list and proves nothing — which is the state the repository
  // was already in when exp034 was missing entirely.
  const reports = await publishedReports();

  assert.ok(
    neverPublished(reports).length >= 1,
    'no report declares ' + NEVER_PUBLISHED + '; the check above is now vacuous',
  );
});

test('a run that asked for the upload is not required to commit anything', async () => {
  // The asymmetry is the whole point, and stating it here keeps the rule above
  // from being widened into "every report must be committed". A run that ran
  // step 7 has a copy on the hub, and `.gitignore` is right to keep the local
  // one out.
  const reports = await publishedReports();
  const uploaded = reports.filter((r) => r.meta?.publication_plan === PUBLISHED);

  assert.ok(uploaded.length >= 1, 'no report declares ' + PUBLISHED);
  for (const report of uploaded) {
    assert.notEqual(report.meta.publication_plan, NEVER_PUBLISHED);
  }
});

test('exp034 carries the numbers its run produced', async () => {
  // The record. These are read from the run's own report, not recomputed: 30
  // tasks attempted, 22 finishing with a deliverable. The eight that did not
  // are benchmark outcomes and stay that way.
  const reports = await publishedReports();
  const exp034 = reports.find((r) => r.short_id === 'exp034');

  assert.ok(exp034, 'exp034 is not in the index');
  assert.equal(exp034.meta.execution_mode, 'codex_foundry');
  assert.equal(exp034.summary.total_tasks, 30);
  assert.equal(exp034.summary.success_count, 22);
  assert.equal(exp034.summary.error_count, 8);
});

test('a null file roll-up is a gap in the counting, not a run without files', async () => {
  // `file_generation` comes back all nulls here, which
  // file-generation-denominator.test.mjs reads as `not-recorded` — correctly,
  // because nothing was counted. What it must not be read as is 0%.
  //
  // The cause is mechanical and belongs with the rest of this file: step 6
  // fills the roll-up from workspace/validate_stats.json (step6_report.py:1679)
  // and step 5 is what writes that file, so a dispatch that skips step 5 for
  // the same reason it skips step 7 has nothing to read. It is recoverable
  // afterwards for nothing — the artifact workspace still holds
  // step0_needs_files_manifest.json and step2_inference_results.json — but it
  // is not recovered here, and a null is the honest record until it is.
  // A null roll-up is not exclusively a dry run's doing: exp026c published and
  // has one too, for a cause not looked into.
  //
  // Two fields on a task row look alike and are not. `has_deliverable_files`
  // is copied from the manifest (step6_report.py:573) and describes the task
  // in the GDPVal dataset — whether the reference task ships deliverable files
  // at all. It says nothing about this run, and six rows here carry it `true`
  // while the task errored and produced nothing. The outcome is `files_count`
  // and `deliverable_files`, and those are what this checks.
  const committed = JSON.parse(
    await readFile(
      join(RESULTS_DIR, 'exp034_codex_foundry_trial30', 'report', 'report_data.json'),
      'utf8',
    ),
  );

  assert.equal(committed.file_generation.needs_files_total, null, 'the roll-up is no longer null');

  const produced = committed.task_results.filter((t) => t.files_count > 0);
  assert.equal(
    produced.length,
    committed.summary.success_count,
    'the rows that produced files and the rows that succeeded are different sets',
  );
  for (const row of produced) {
    assert.equal(
      row.deliverable_files.length,
      row.files_count,
      `${row.task_id} counts a different number of files than it lists`,
    );
  }
});

test('the report states a solving cost and never a grading cost', async () => {
  // Two different questions are asked about the same run — what it cost to
  // produce the answers, and what it cost to grade them — and they are
  // recorded in different places on purpose: this block, and `grading_cost`
  // inside the files under `data/grades/`. A single summed figure would be
  // readable as either and correct as neither.
  const reports = await publishedReports();

  for (const report of neverPublished(reports)) {
    assert.deepEqual(
      Object.keys(report.cost_summary ?? {}),
      ['problem_solving_cost'],
      `${report.short_id} carries a cost key other than the solving cost`,
    );
  }
});

test('an unpriced run publishes no dollar figure rather than a zero', async () => {
  // This deployment is absent from `experiments/execution_envelope/
  // model_price_table.json`, so the receipt comes back `partial`. What must
  // not happen is the absence being rounded into a number: a $0.00 beside
  // nine million real tokens reads as a free run.
  //
  // The raw report does carry `known_cost_usd: 0` here, and that is not a bug
  // to fix in the file — step 6 fills every money field on every status, and
  // `measuredAmount` in cost-receipt.mjs drops a zero under any status but
  // `complete` precisely so it never reaches a reader as $0.0000. What is
  // checked below is the part the read layer cannot rescue.
  const reports = await publishedReports();

  for (const report of neverPublished(reports)) {
    const cost = report.cost_summary.problem_solving_cost;
    if (cost.status === 'complete') continue;

    assert.equal(
      cost.cost_per_successful_deliverable_usd,
      null,
      `${report.short_id} prints a per-deliverable price it cannot support`,
    );
    assert.ok(
      Array.isArray(cost.missing_reasons) && cost.missing_reasons.length > 0,
      `${report.short_id} is ${cost.status} without saying what is missing`,
    );
  }
});
