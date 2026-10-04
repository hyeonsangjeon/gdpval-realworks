# Offline Codex run analysis

`scripts/analyze_codex_run.py` has two separate local input modes. Neither
downloads artifacts, invokes a model or grades a task. Choose one input; the
compact mode does not supply data to Step2 collection or accounting.

From `batch-runner`:

```bash
# Existing unpacked Step2 artifact mode
python scripts/analyze_codex_run.py /path/to/unpacked-artifact

# Explicit compact-outcomes mode
python scripts/analyze_codex_run.py --outcomes-json docs/run_records/exp035_run34685779030_partial/outcomes.json
```

The Step2 path, output, default help and errors retain their existing behavior
when `--outcomes-json` is absent. The new option is documented here without
changing that default help. Compact-specific help is available with
`--outcomes-json PATH --help`. A compact path and a Step2 artifact path are
mutually exclusive; supplying the compact option more than once is an error.

## Compact input and output

The input is one UTF-8 JSON list. Each row requires a unique canonical UUID
`task_id`, recorded `status` of `success` or `error`, and matching `outcome` of
`ok` or `failed`. An empty list is allowed and produces counts, not a percentage.

`reason` may be absent, null, empty, or a lowercase ASCII category identifier
of at most64 characters. This is label validation, not another failure
taxonomy. `message` may be absent, null or a string. `attempted` may be absent,
null or a boolean. Missing fields remain missing; the report distinguishes
`NOT_RECORDED` from explicit null and false. Non-object rows, duplicate JSON
keys/task IDs, non-finite JSON numbers, invalid types, inconsistent outcomes
and mixed Step2 fields (`observability`, `error`, `http_status_code`) fail with
a CLI error. Input errors do not expose file contents or private paths.

The compact report identifies its source by SHA256 and byte count, preserves
row order, and prints the row and unique-task denominators plus recorded
task IDs/status/outcome/reason/attempted fields. It does not print messages,
provider endpoints, credentials, task bodies or free-form notes. Extra compact
accounting fields stay in the untouched source; they are not converted into
ledger rows, calls, attempt totals, costs or grades. `failure_class` and its
note do not remove failures or establish that no model work occurred.

Only present `status`, `reason` and `message` fields map to the existing
`_derived_output_limit_diagnostic`. This mapping does not claim that compact
rows originally contained Step2 `observability.error_category` or `error`.
The existing full matcher decides whether to add its fixed category
`output_limit_exceeded`, provenance`offline_local_result_error_explicit_reason`
and null`missing_reason`. It does not replace recorded fields or change
runtime classification or recovery eligibility. Known recorded reasons retain
precedence; an ordinary substring, missing/redacted text, context/input limit
or conflicting wrapper is insufficient.

Rows without an addition remain diagnosis-unavailable with the report reason
`not_established_by_recorded_status_reason_message`. That includes rows whose
recorded status/reason is ineligible, not just rows with missing text. It does
not prove that an output limit never occurred or identify another cause.

## Retained exp035 point

The one bounded selector at implementation
`cab506a72d6d25d1b73246ae8d66e4eaad86fb97` ran the compact mode once on
`docs/run_records/exp035_run34685779030_partial/outcomes.json`, SHA256
`9e98e98d3dbd0a9030c95642388ccb53b210a5e8f4cbc685b13391e67b4a8d6b`.
It preserved all220 rows/220 unique tasks:

| Retained evidence | Count |
| --- | --- |
| Recorded `success` / `ok` | 150/220 rows |
| Recorded `error` / `failed` | 70/220 rows |
| Additional full-match output-limit diagnostic | 3/220 rows, indices151/152/198 |
| No added output-limit diagnosis | 217/220 rows, not217 failed tasks |

All3 supplied substring candidates qualified under the existing full matcher;
that result was observed, not assumed by the selector. The separate fixture
proof covered55 authored cases with8 expected additions,35 invalid input
sources and4 CLI exclusions. Those fixture counts are not extra retained
outcomes. The single pytest item passed in1.76s; that is test duration, not
model latency or a measured improvement.

This is retrospective local exp035 evidence, not new provider observation,
independent failure-cause attribution, judging or an invoice. It does not
change or combine the original30-cell budget pilot or separate8-cell retention
study. Their outcomes, grades, costs and consumed observations stay unchanged.
The [current completion record](../../tasks/LATEST_TASK_RESULT/README.md)
retains exact commands, tested tree and log identities; prior source acceptance
does not replace review and CI of the new HEAD.
