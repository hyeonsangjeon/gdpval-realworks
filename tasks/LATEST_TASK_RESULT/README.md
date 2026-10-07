# Latest task result

## Model-free native Task3 retained-bundle preparation

The new fixed-cell caller passed its one offline selector: **21 passed in
40.03s**, exit 0; wrapper **40.587362s**. It authenticated a synthetic native
canonical result, hydrated and verified two synthetic files totaling 408601
bytes, then reached the unchanged frozen-F grading preparer. No private
bundle was fetched, and no native runtime, kernel admission, provider, model
or grader ran. This is preparation code with review/CI pending, not grading
authority or an actual Task3 grade.

Only a new caller and focused test were added before validation:
`gpt54_time_budget_native_grading_intake.py` and
`tests/test_time_budget_native_grading_intake.py` under `batch-runner/`.
The [direct usage contract](../../batch-runner/README.md) describes the
digest-bound request schema and callable. There is no new workflow, scheduler,
intake publication ledger, `inference_sha` input or fabricated
inference-publication association. The existing preparer, reader, native
controller/capture, compiler, registration, core, rubrics and scoring are
unchanged. No consumed cell is relabeled or replayed.

### Independently verified actual Task3, still ungraded

The leader verified native r1 Task3
`2ea2e5b5-257f-42e6-a7dc-93763f28b19d` in
`gpt54_time_budget_v1_codex_r1` / `codex` / repeat 1, completion
`37631184801` / run number 5 / attempt 1. Original R is
`33e24e9c1402ec0b7c92a71222998d1407646a92`, tree
`6e67da4e12169b41a837d92eaf946db15e71010e`. The canonical result is 8518
bytes, SHA256
`4ae3ea3d0dbe6ee540b86e3db17085e3a4d6f73afaf035c7f6f659f99b4601a4`,
fingerprint
`4a62be1df3e21eae52bd7814359887c5f774200948ba67fc15ca62bf2f4b2967`,
at immutable output `d5aeecec1394fb44d4b1da33b1be38a39acdb89a`; claim
`08e485281f25ea06311305e7a4add721a68ba9ea`.

The separate actual readout `37651509527`, artifact `11497400004`, produced
2570 bytes with SHA256
`4dfc3e896b7f57de1c97e1aca2b37feb10031f6b04aa3afe43d1f63c9e189553`.
It independently matched C/R/result/cell/output. Status was success, runner
true, terminal completed, cleanup and host reuse true. It **declared** two
files totaling 408601 bytes; their contents were not fetched or verified.
`items_seen=56` is not a model/request count. Native usage, cost, served
identity and counters remain null, not zero. No quality score is established.
The 297-second execution step is not measured pure model or generation time.

Task4 separately ended with a canonical error and cleanup true at private
output `82ed160109e40dcf74029f2be34a973350374fc6`. Its inner cause remains
unread. It is not used to explain Task3 or treated as a zero score. Native
Task1/Task2 remain consumed uncertain; all five prior V2 cells remain
consumed. No replay, next cell or ABBA advancement occurred or is authorized.

### Scope and independent sources

Accepted base was `f997b5e005bb1c49421e8e32cfa3040fa4266ae9`, tree
`ea1ba7b15863ec5f3b2a21accd9859568a561ee2`, verified by one origin/main
fetch/check. The tested adapter C is
`8faa9c1c3adf9cc6cc8debd6335a72c6bd7e379f`, tree
`f217eda6e2d0dace34c07aa591397ab31c83c9df`. C validates original R's exact
commit/tree and registration; it does not replace R with C or execute old R
code. The preparer blob is identical at base C and actual R:
`24a430137fb47bced1e5a450b5b5568d477a5b2e`, SHA256
`4067abb781faa7bfb18adab54e641fdbeea85eac8174a4210c047cda703b4ffc`.
No shared change or runtime-pin update was needed. The new caller is bound
directly to C's commit/tree; registration seal remains
`3dde5f2f62e8ada29c883e1ef0eb555c969987f710b437af50c513ac9b52d22f`.

Frozen F remains `882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`, template identity
`37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`.
Actual local parquet, references and the full 218405-byte original Step0
must independently reconstruct the captured observation/input seal. A
downloaded marker, claim or declaration cannot supply that authority.
The synthetic proof used its own explicit source/input pins and full Step0
hash; it did not verify the private originals or assert their pins on
synthetic data.

The fixed target remains
`HyeonSang/gdpval-codex-budget-pilot-ci-20260923`. At one trusted immutable
revision, at most four GETs share 60 cumulative seconds: private identity
metadata, the independently expected canonical result, then exactly its two
authenticated declared files. Count 2 and aggregate 408601 bytes are
independent request expectations. Complete native source/control/result
checks precede file reads; every full file digest/size must match before
preparation. No mutable HEAD, redirects, decompression, retries, archives,
claim/request downloads or HF writes are available.

Private no-clobber hydration and grading destinations are disjoint; partial
files and reservations survive failure and cannot be adopted. Credentials
are absent from the preparer and F tree. Only safe binding/count metadata
is returned, with content verification distinguished from the earlier
declaration-only readout. No grading admission/claim or
`execute_first_observation_grading` call occurs.

### One synthetic proof and artifacts

Selector:
`tests/test_time_budget_native_grading_intake.py::test_time_budget_native_retained_grading_intake`.
All 21 parameter names were mechanically checked before collection. The
positive exercised real native capture, source/input/canonical/file
validators and F-derived preparation. Refusals covered result/file digest,
fingerprint, size, path, revision, cell/R/tree, private identity, input seal,
whole Step0, encoding, cumulative deadline, partial/no-clobber state and
credential/private-field leakage. Kernel/control capture metadata was
explicitly synthetic; no successful runtime or preparer verdict was mocked.
No old selector, full suite or live operation was run.

The invocation used Python 3.10.12 with one 300-second TERM bound plus
5-second KILL grace, no `-x`, no retries, Python timing, and the existing
named local fixture Git operations bounded to 30 seconds. The artifact
directory is `/tmp/native-task3-grading-bridge.zWCjyI/`:

- `command.json`, `selection.json`, `source.json`, `cases.json`,
  `outcome.json` and `run-proof.py` retain exact scope and per-case outcomes.
- `pytest.log` SHA256:
  `6b754d8427856b30c2628162a798e8473a5db00b3091abf64eb87cc8e4f458c4`.
- `junit.xml` SHA256:
  `6220be2a26ee0c87ddb2d600ab15a3a2b36eff940e2689c550f760d94a44eebb`.
- `records/` preserves source/structured/final evidence checkpoints and
  fidelity/condition audits. `handoff.json` records the final documentation
  commit/tree and unchanged tested helper/test blobs after publication.

Only CHANGELOG, this record and direct README usage change after the proof.
The [prior record][prior] preserves earlier readout implementation failures,
separate corrections, reviews and live gates; none was rerun or combined
with these 21 cases.

### Remaining gates

The leader approved this bounded implementation decision. The specialist
grading review invocation failed before execution because its configured
model label was unavailable; this is not an endorsement, and no harness
retry was attempted. Fixed-HEAD source review and ordinary CI remain
pending, followed by separately authorized credentialed intake using the
actual retained files and genuine originals. Frozen-F preparation must
succeed on those bytes before any separately directed once-only grade.
This draft grants none of those permissions.

The design remains the same twenty-cell study: GPT-5.4/direct-v1/xhigh,
null context override, zero configured provider retries, concurrency 1,
one external attempt, 1200-second generation/shared 20-second cleanup and
45-minute job ceiling. No money cap or remote-cancellation claim is added.
The experiment-design and English reporting/copyediting guidance kept
actual observations, synthetic validation and unmeasured claims separate.
No CI query/dispatch/retry, Azure, private HF, model, grader, readout,
Project edit, merge or consumed-cell replay was performed.

[prior]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/f997b5e005bb1c49421e8e32cfa3040fa4266ae9/tasks/LATEST_TASK_RESULT/README.md
