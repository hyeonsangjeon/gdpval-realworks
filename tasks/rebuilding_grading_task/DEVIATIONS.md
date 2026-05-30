# PR3 Decision Run — DEVIATIONS

Per Persistence Protocol §3: log infeasibilities and proceed with nearest viable action.

| step | what_failed | why | what_i_did_instead |
|---|---|---|---|
| 0 | scripts/__tests__/test_grading_cost_sweep.py 2 failures (test_render_temp_config_enforces_seed_temp, test_winner_config_has_comment_banner) | Tests reference `winner_config.yaml` files moved to `grading_configs/_archive_v1/` in PR2 task 207 (commit 2aa6688). Pre-existing regression, unrelated to PR3 work. | Logged; not blocking. batch-runner suite (563 pass) is the authoritative gate for grader correctness. Cleanup deferred to the post-PR3 legacy-strip PR. |
