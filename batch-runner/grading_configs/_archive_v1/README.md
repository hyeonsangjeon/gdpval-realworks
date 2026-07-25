# `_archive_v1/` — legacy grading configs (PR2 task 207)

These configs target the **v1 text-extract grader path** in
`core.grader.Grader` (with optional `BatchJudge` tier routing). After
the v2 tool-calling rebuild (PR2 tasks 201-208), they are no longer
recommended for new grading runs.

They remain on disk as provenance so:

1. existing grade JSONs at `data/grades/*__judge_*__*.json` retain their
   original config bytes and cache identity,
2. the PR1 backfill scripts (`scripts/backfill_sign_aware.py`) can
   reference the original config for unit testing,
3. an operator can inspect the historical v1/v2 A/B configuration without
   silently translating its endpoint contract.

These archived files are **not runnable inputs** to the current typed-route
validator because they retain the historical `judge.endpoint_env` field. To
rerun one, use its historical commit/environment, or copy it to a new top-level
config, remove `endpoint_env`, add an explicit matching `deployment`, and treat
the result as a new run identity. Never resume an old partial across that
migration boundary.

**Do not author new configs here.** Add new configs under
`grading_configs/<name>.yaml` based on `default_v2_sol_max.yaml`. See the
top-level `grading_configs/README.md` for the migration table.
