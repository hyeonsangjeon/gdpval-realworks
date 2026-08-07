# Repository Completion Requirements

For every repository task that changes code, documentation, data, configuration,
CI/CD, or remote project state (including PR merges, deployments, and workflow
runs), complete all of the following before reporting the task as done:

1. Update `tasks/LATEST_TASK_RESULT/README.md` so it describes the latest task's
   current result. Replace stale task status rather than accumulating an
   unbounded history. Include the task scope, concrete outcome, verification
   evidence, the reviewed head SHA when a review gate applies, and any
   remaining work.
2. Add or update the corresponding `CHANGELOG.md` entry under `[Unreleased]`
   using the repository's Keep a Changelog categories. Preserve unrelated
   entries and user changes. Apply the same evidence boundary described below
   to the changelog entry.
3. Stop both completion records at pre-merge facts. Do not record the carrying
   PR's own merge SHA, merge time, or `OPEN` / `MERGED` state in either record.
   Git history already holds those facts, and a record describing its own merge
   cannot be written before that merge, so requiring it forces an unnecessary
   follow-up PR.
4. If an earlier entry genuinely needs a status correction, fold it into the
   next substantive work PR. Do not open a documentation-only PR solely to
   record that an earlier PR merged.
5. Perform these documentation updates after validation and before the final
   response. Do not declare completion while the task scope, outcome,
   verification evidence, reviewed head SHA when applicable, or remaining work
   is stale. This clarifies the evidence boundary; it does not relax the
   completion requirements.
