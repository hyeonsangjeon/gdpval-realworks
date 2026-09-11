/**
 * A report that only exists here is not a report without a page.
 *
 * `a-run-that-never-reached-the-hub-is-not-a-run-that-never-happened.test.mjs`
 * establishes the first half: a run dispatched `dry_run: true` skips step 7,
 * so no `HyeonSang/<experiment_id>` dataset is ever created, and the committed
 * `batch-runner/results/<dir>/report/report_data.json` is the only copy of its
 * results. That file is now required to be committed.
 *
 * This is the second half, and it was missing. Being committed got the run into
 * the leaderboard and the sector matrix, because both read
 * `reports-index.json` — but the index deliberately drops `task_results`, and
 * the one page that shows per-task outcomes fetched them straight from
 * HuggingFace:
 *
 *     `${HF_BASE}/${entry.meta.experiment_id}/resolve/main/self_report.json`
 *
 * For exp034 that URL answers **404**. `useReport` set an error, and
 * `ExperimentDetail.tsx` renders an error panel and returns on `error ||
 * !report`. So the run appeared in every aggregate view and its own page — the
 * only place its 30 task outcomes could be read — was a red box. The results
 * were in the repository the whole time; nothing served them.
 *
 * `aggregate-reports.mjs` now writes the full payload to
 * `public/generated/reports/<short_id>.json` for exactly those reports it read
 * locally, marks the index entry `served_locally`, and `useReport` routes on
 * that flag. This file holds every end of that to the same declaration the
 * other file keys on — `publication_plan` — so the next dry run is covered the
 * day its report lands.
 *
 * Why a flag and not "try local, fall back to the hub": a static host serving
 * an SPA answers a missing file with **200 and `text/html`**, not 404. Measured
 * against `vite preview`, which is what the browser tests run:
 *
 *     /generated/reports/exp034.json => 200  application/json  {"meta":{...
 *     /generated/reports/exp027.json => 200  text/html         <!doctype html>
 *
 * So a probe cannot distinguish "no local copy" from "here is index.html", and
 * every published report would have died on the JSON parse instead.
 *
 * Why not copy every report locally: a report that ran step 7 is already served
 * from the URL the page asks for. A second copy in this build would diverge
 * from it silently the moment either changed, and nobody would know which one
 * they were reading. The asymmetry is deliberate and is asserted below.
 *
 * Nothing here reaches the network.
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';

const ROOT = new URL('../..', import.meta.url).pathname;
const GENERATED = join(ROOT, 'public', 'generated');
const REPORTS_INDEX = join(GENERATED, 'reports-index.json');
const PAYLOAD_DIR = join(GENERATED, 'reports');
const HOOK = join(ROOT, 'src', 'hooks', 'useReports.ts');

/** What step 6 writes into `meta` when the dispatch skipped step 7. */
const NEVER_PUBLISHED = 'dry_run_no_step7';

/** And what it writes when the upload was asked for. */
const PUBLISHED = 'step7_upload_requested';

async function indexReports() {
  const index = JSON.parse(await readFile(REPORTS_INDEX, 'utf8'));
  assert.ok(Array.isArray(index.reports), 'reports-index.json carries no reports array');
  return index.reports;
}

const neverPublished = (reports) =>
  reports.filter((r) => r.meta?.publication_plan === NEVER_PUBLISHED);

async function payload(shortId) {
  return JSON.parse(await readFile(join(PAYLOAD_DIR, `${shortId}.json`), 'utf8'));
}

test('a report with no copy on the hub is served from this build', async () => {
  const reports = neverPublished(await indexReports());

  for (const report of reports) {
    let served;
    try {
      served = await payload(report.short_id);
    } catch (err) {
      assert.fail(
        `${report.short_id} declares ${NEVER_PUBLISHED}, so the hub answers 404 for it ` +
          `and its detail page has nothing to fetch — but ` +
          `public/generated/reports/${report.short_id}.json was not written: ${err.message}`,
      );
    }

    assert.equal(
      served.meta?.experiment_id,
      report.meta.experiment_id,
      `the payload served for ${report.short_id} belongs to a different experiment`,
    );

    assert.equal(
      report.served_locally,
      true,
      `${report.short_id} has a payload written but its index entry does not say so, ` +
        `so the page will still ask the hub and still get a 404`,
    );
  }
});

test('the served payload carries the task rows the index leaves out', async () => {
  // This is the entire reason the file exists. An index entry without
  // `task_results` renders the summary header and an empty table; the payload
  // is what the page is actually for.
  const reports = neverPublished(await indexReports());

  for (const report of reports) {
    const served = await payload(report.short_id);

    assert.ok(
      Array.isArray(served.task_results),
      `${report.short_id} is served without task_results, which is the one thing ` +
        `the index does not already carry`,
    );
    assert.equal(
      served.task_results.length,
      report.summary.total_tasks,
      `${report.short_id} serves a different number of task rows than its run attempted`,
    );
  }
});

test('the index itself still drops the task rows', async () => {
  // Teeth for the test above. If the index ever started carrying
  // `task_results`, the payload would be redundant and the assertion would
  // pass for the wrong reason — and the index, fetched on every page load,
  // would have quietly grown by the size of every run's per-task detail.
  const reports = await indexReports();

  for (const report of reports) {
    assert.equal(
      report.task_results,
      undefined,
      `${report.short_id} carries task_results in the index; it is meant to be lightweight`,
    );
  }
});

test('a report that published is not copied here as well', async () => {
  // The asymmetry. Two copies of one run, one in this build and one on the
  // hub, diverge without anything reporting it.
  const reports = await indexReports();
  const uploaded = reports.filter((r) => r.meta?.publication_plan === PUBLISHED);

  assert.ok(uploaded.length >= 1, `no report declares ${PUBLISHED}`);

  for (const report of uploaded) {
    assert.notEqual(
      report.served_locally,
      true,
      `${report.short_id} is on the hub and is also marked as served from this build`,
    );
    await assert.rejects(
      payload(report.short_id),
      /ENOENT/,
      `${report.short_id} is on the hub and is also served from this build; ` +
        `the two copies can disagree and nothing would say which is right`,
    );
  }
});

test('the corpus still holds a run that never published', async () => {
  // Without this, every check above passes over an empty list.
  const reports = await indexReports();

  assert.ok(
    neverPublished(reports).length >= 1,
    `no report declares ${NEVER_PUBLISHED}; the checks above are now vacuous`,
  );
});

test('the page routes on the flag rather than probing for the file', async () => {
  // Writing the file is half the fix. A payload nothing reads is worse than
  // no payload: the build reports success and the page is still a 404.
  //
  // Asserted against the source rather than through a browser because what is
  // being guarded is which URL gets built, and the wrong answer only shows up
  // as a fetch that was never made.
  const source = await readFile(HOOK, 'utf8');

  assert.match(
    source,
    /entry\.served_locally/,
    'useReport no longer routes on served_locally; a run with no hub copy is back ' +
      'to an error panel, or a published one is reading index.html as JSON',
  );
  assert.match(
    source,
    /generated\/reports\/\$\{shortId\}\.json/,
    'useReport no longer requests the locally served payload',
  );
  assert.match(
    source,
    /\$\{HF_BASE\}\/\$\{entry\.meta\.experiment_id\}\/resolve\/main\/self_report\.json/,
    'useReport no longer reads published reports from the hub',
  );
});
