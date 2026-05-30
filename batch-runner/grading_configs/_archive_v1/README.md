# `_archive_v1/` — legacy grading configs (PR2 task 207)

These configs target the **v1 text-extract grader path** in
`core.grader.Grader` (with optional `BatchJudge` tier routing). After
the v2 tool-calling rebuild (PR2 tasks 201-208), they are no longer
recommended for new grading runs.

They remain on disk so:

1. existing grade JSONs at `data/grades/*__judge_*__*.json` can be
   reproduced from the same config bytes (4-tuple cache key —
   `rubric_sha` + `config_sha` + `prompt_v` + `judge_model`),
2. the PR1 backfill scripts (`scripts/backfill_sign_aware.py`) can
   reference the original config for unit testing,
3. any operator wanting to A/B compare v1 vs v2 on a specific
   experiment can still pass `--config grading_configs/_archive_v1/<file>`
   to `step8_grade.py`.

Validator (`step8_grade.py::validate_grading_config`) still accepts
schema 1.0, so these files load without modification.

**Do not author new configs here.** Add new configs under
`grading_configs/<name>.yaml` based on `default_v2.yaml`. See the
top-level `grading_configs/README.md` for the migration table.
