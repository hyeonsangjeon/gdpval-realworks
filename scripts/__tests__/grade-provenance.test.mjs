// Unit tests for src/lib/gradeProvenance.js and its wiring into the dashboard.
//
// The audit gap this closes: step8 publishes a `final` grade whose source
// inference run predates `inference_provenance.json`, and the aggregator
// carries `source_azure_ai_provenance_status` onto the projection — but until
// this module existed nothing in `src/` read that field, so the grade rendered
// exactly like one whose routes were verified.
//
// Run:
//   node --test scripts/__tests__/grade-provenance.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { isPublishableGrade, processGradesFile } from '../aggregate-grades.mjs';
import {
  hasUnverifiedRouteProvenance,
  LEGACY_MISSING_PROVENANCE,
  UNVERIFIED_PROVENANCE_DESCRIPTION,
  UNVERIFIED_PROVENANCE_LABEL,
} from '../../src/lib/gradeProvenance.js';

/** A minimal publishable v1 grade payload, as step8 writes it. */
function gradePayload(overrides = {}) {
  return {
    schema_version: '1.0',
    run_status: 'final',
    experiment_id: 'exp-legacy',
    inference_model: 'gpt-5.2-chat',
    judge: { model: 'gpt-5.6-sol' },
    summary: {
      total_tasks: 1,
      graded_tasks: 1,
      error_tasks: 0,
      // Schema 1.3 rejects a payload that omits any of these six, and every
      // published 1.0-1.2 file carries them; this fixture is about provenance
      // badging, so it just needs a headline that could exist.
      openai_compat: {
        avg_score_pct: 50,
        ci_pct: 4.2,
        perfect_count: 0,
        partial_count: 1,
        zero_count: 0,
        inconsistent_count: 0,
      },
      wow: {},
    },
    tasks: [{ task_id: 't1', pct: 50, error: null }],
    ...overrides,
  };
}

test('only a missing route sidecar is badged', () => {
  assert.equal(hasUnverifiedRouteProvenance(LEGACY_MISSING_PROVENANCE), true);
  assert.equal(LEGACY_MISSING_PROVENANCE, 'legacy-missing');
});

test('proven, local, and absent provenance render nothing', () => {
  // The first three are the remaining `grade.schema.json` enum members; `null`
  // is what every grade written before the field existed carries, and
  // `undefined` is what a caller reading an older projection object gets.
  for (const status of [
    'runtime-verified',
    'verified-sidecar',
    'local-runtime',
    null,
    undefined,
  ]) {
    assert.equal(hasUnverifiedRouteProvenance(status), false);
  }
});

test('badge copy is non-empty and names the gap it warns about', () => {
  assert.match(UNVERIFIED_PROVENANCE_LABEL, /\S/);
  assert.match(UNVERIFIED_PROVENANCE_DESCRIPTION, /provenance/i);
});

test('a published legacy-provenance grade reaches the badge through the aggregator', () => {
  const projected = processGradesFile(
    'legacy.json',
    gradePayload({ source_azure_ai_provenance_status: 'legacy-missing' }),
  );

  // Publishable and badged are independent: the run graded its complete corpus,
  // so it is not demoted to diagnostic — it is labelled instead.
  assert.equal(isPublishableGrade(projected), true);
  assert.equal(
    hasUnverifiedRouteProvenance(projected.source_azure_ai_provenance_status),
    true,
  );
});

test('a sidecar-backed grade reaches the dashboard unbadged', () => {
  const projected = processGradesFile('sidecar.json', gradePayload());

  assert.equal(isPublishableGrade(projected), true);
  assert.equal(
    hasUnverifiedRouteProvenance(projected.source_azure_ai_provenance_status),
    false,
  );
});

test('every grade render site reads the shared predicate, not a bare literal', async () => {
  // Three components surface `legacy_dummy` today; each must surface this too,
  // and none may re-spell the status string, or a future rename to the enum
  // would silently stop badging one of them.
  const sites = [
    'src/pages/GradeDetail.tsx',
    'src/components/GradesSummary.tsx',
    'src/components/dashboard/GradingAnalysisView.tsx',
  ];

  for (const site of sites) {
    const source = await readFile(new URL(`../../${site}`, import.meta.url), 'utf8');
    assert.match(
      source,
      /source_azure_ai_provenance_status/,
      `${site} does not read the provenance status`,
    );
    assert.doesNotMatch(
      source,
      /['"]legacy-missing['"]/,
      `${site} hardcodes the status literal instead of using gradeProvenance`,
    );
  }
});
