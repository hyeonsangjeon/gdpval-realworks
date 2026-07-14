# Repository Completion Requirements

For every repository task that changes code, documentation, data, configuration,
CI/CD, or remote project state (including PR merges, deployments, and workflow
runs), complete all of the following before reporting the task as done:

1. Update `tasks/LATEST_TASK_RESULT/README.md` so it describes the latest task's
   current result. Replace stale status rather than accumulating an unbounded
   history. Include the task scope, concrete outcome, verification evidence,
   and any remaining work.
2. Add or update the corresponding `CHANGELOG.md` entry under `[Unreleased]`
   using the repository's Keep a Changelog categories. Preserve unrelated
   entries and user changes.
3. Perform these documentation updates after validation and before the final
   response. Do not declare completion while either record is stale.
