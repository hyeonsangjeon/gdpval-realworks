# TASK_GRADE_SOURCE_LINKAGE_BACKEND — Embed inference source linkage in grade JSON

## TL;DR
`step8_grade.py`가 grade JSON \uc791\uc131 \uc2dc `source_inference_experiment_id` \ud544\ub4dc\ub97c \ud3ec\ud568\ud558\ub3c4\ub85d \ud55c\ub2e4.
\uc774\ub85c\uc368 grade \u2194 inference run \uc5f0\uacb0\uc774 \ud30c\uc77c \uc790\uccb4 \ub0b4\uc5d0 \uba85\uc2dc\uc801\uc73c\ub85c \uae30\ub85d\ub418\uc5b4, \ub300\uc2dc\ubcf4\ub4dc calibration \ub9e4\uce6d\uc774 \uac15\uac74\ud574\uc9c4\ub2e4.

## Why
Phase 1\uc758 calibration \uae30\ub2a5(`TASK_GRADE_DETAIL_SELF_QA_CALIBRATION.md`)\uc740 `grade.experiment_id == report.experiment_id`\ub85c \ub9e4\uce6d\ud558\ub294\ub370,
\uc774\ub984\uc774 \uc870\uae08\uc774\ub77c\ub3c4 \ub2e4\ub974\uba74 (\uc608: exp998 grade \u2194 exp999 inference) \ub9e4\uce6d \uc2e4\ud328 \u2192 unmatched\ub85c \ud45c\uc2dc.
\uc785\ub825\ub3d8\ub418\ub294 \uc18c\uc2a4 ID\ub97c grade JSON\uc5d0 \uc9c1\uc811 \uae30\ub85d\ud558\uba74 \uc774 \ubaa8\ud638\uc131\uc774 \uc81c\uac70\ub41c\ub2e4.

## Scope

**\uc218\uc815**:
- `batch-runner/step8_grade.py` \u2014 grade JSON \uc791\uc131 \uc2dc `source_inference_experiment_id`, `source_inference_run_dir` \ud544\ub4dc \ucd94\uac00
- `batch-runner/schemas/grade.schema.json` (\uc788\ub2e4\uba74) \u2014 \uc2e0\uaddc \ud544\ub4dc \ucd94\uac00
- `scripts/aggregate-grades.mjs` \u2014 \uadf8 \ud544\ub4dc\ub97c \uc6b0\uc120\uc801\uc73c\ub85c \uc0ac\uc6a9, \uc5c6\uc73c\uba74 `experiment_id`\ub85c fallback
- `data/grades/exp998_smoke_baseline_sample__*.json` \u2014 1\ud68c\uc131 backfill\ub85c `source_inference_experiment_id: "exp999_smoke_baseline_sample"` \ucd94\uac00
- `batch-runner/tests/test_step8_grade.py` \u2014 \uc2e0\uaddc \ud544\ub4dc \uac80\uc99d \ud14c\uc2a4\ud2b8 \ucd94\uac00

**\uba85\uc138\uad6c\uc870**:

```json
{
  "schema_version": "1.0",
  "experiment_id": "exp998_smoke_baseline_sample",
  "experiment_yaml_name": "exp998_smoke_baseline_sample",
  "source_inference_experiment_id": "exp999_smoke_baseline_sample",  // \u2190 NEW
  "source_inference_run_dir": "batch-runner/results/exp999_smoke_baseline_sample",  // \u2190 NEW (optional, debugging)
  "inference_model": "gpt-5.2-chat",
  ...
}
```

### Step8 \ubcc0\uacbd \ud3ec\uc778\ud2b8
- \uc774\ubbf8 step8_grade.py\ub294 inference run \ub514\ub809\ud1a0\ub9ac\ub97c \uc77d\uc5b4 \ucc44\uc810\ud568. \uadf8 \ub514\ub809\ud1a0\ub9ac\uc758 `experiment_id`\ub97c JSON\uc5d0 \uadf8\ub300\ub85c \uae30\ub85d.

### Aggregate-grades \ubcc0\uacbd \ud3ec\uc778\ud2b8
\uc6b0\uc120\uc21c\uc704:
1. `grade.source_inference_experiment_id` (Phase 2 \uc2e0\uaddc \ud544\ub4dc) \u2192 \uc0ac\uc6a9
2. `grade.experiment_id` (Phase 1 fallback) \u2192 \uc0ac\uc6a9
3. \uc544\ubb34\uac83\ub3c4 \ub9e4\uce6d \uc548 \ub428 \u2192 unmatched

## Verification

1. `step8_grade.py` \uc2e4\ud589 \uc2dc \uc0dd\uc131\ub418\ub294 grade JSON\uc5d0 \uc2e0\uaddc \ud544\ub4dc \uc874\uc7ac
2. \uae30\uc874 grade \ud30c\uc77c (Phase 1) \uc77d\uae30 \uacc4\uc18d \uc791\ub3d9 (backward compat)
3. exp998 grade backfill \ud6c4 \ub300\uc2dc\ubcf4\ub4dc\uc5d0\uc11c calibration \ud45c\uc2dc\ub428 (3/3 matched)
4. \ud14c\uc2a4\ud2b8: `python -m pytest batch-runner/tests/test_step8_grade.py -v`

## Out of Scope
- grade \uc7ac\ucc44\uc810 (Phase 1 grade\ub294 backfill\ub9cc \uc801\uc6a9, \uc810\uc218 \ubcc0\uacbd \uc5c6\uc74c)
- \uc5ec\ub7ec inference run\uc744 \ud558\ub098\uc758 grade\ub85c \ubcd1\ud569\ud558\ub294 \uba40\ud2f0-\uc18c\uc2a4 \uc2dc\ub098\ub9ac\uc624

## Dependencies
- Phase 1 (`TASK_GRADE_DETAIL_SELF_QA_CALIBRATION.md`)\uac00 \uba38\uc9c0\ub41c \ud6c4 \uc2dc\uc791
