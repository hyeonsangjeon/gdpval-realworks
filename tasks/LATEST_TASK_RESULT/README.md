# Latest task result

## PROJECT5-TASK5-R1-BUDGET-OBSERVATION-20261003-2215

The one authorized combined r1 selector passed at implementation HEAD
`bca9af2f4e97a82a72d55e9742bfd1f0a6ee3a1a`: 1 passed in 10.51s, with 576 mode
cases, test/log-capture exits 0, no timeout and zero recorded network/model/
writer/child/paid effects. The 10.51s is pytest's duration; outer elapsed time
is unavailable. Only the two completion records change after this proof;
tested executable, test, report and JSON bytes remain unchanged.

This unit adds only `TASK5_FRESH_R1` and `TASK5_KEEP_R1` to the existing budget
path, making exactly four canonical Task5 bindings eligible. It records the
leader's actual KEEP/r2 RESULT-only budget receipt separately in the
[report](../codex_budget_pilot/RETENTION_DIAGNOSTIC_REPORT.md) and
[JSON](../codex_budget_pilot/retention_diagnostic_readout.json). Both r2 budget
observations are consumed. Both r1 budgets remain unobserved. No live read or
new experiment ran here.

Work started in the new clean branch/worktree
`codex-retention-task5-r1-budget-observation-20261003-2215`, from delivered main
`55393ba822c66a7c4ec2b2e40c9c8869eb2d7c1a`. The one duplicate-open-PR inspection
returned none. The preserved checkout, all earlier worktrees and
`wip/local-main-preserved-20260719` were untouched. The leader supplied accepted
PR732 HEAD `b3bb851e3e527e3be97f3a282df47367e84bdfdc`, review
[5400850876](https://github.com/hyeonsangjeon/gdpval-realworks/pull/732#pullrequestreview-5400850876)
and all ten checks. Its complete source review and distinct 7.26s/5.29s proofs
are prior acceptance evidence, not validation of this new HEAD, and were not rerun.

### Closed extension and direct pre-edit decision

The leader's 2026-10-03 22:15 KST APPROVE-WITH-CONDITIONS decision applies only
to this bounded r1 observation extension. It is a direct Project5 leader decision, not a
returned agent verdict. No unavailable memo transport was retried. Final
immutable-source review, same-HEAD CI, delivery and separate live-read
authorization remain required.

The existing `observe_budget` input and `--observe-budget` reader flag accept
only canonical `TASK5_FRESH_R1`, `TASK5_KEEP_R1`, `TASK5_KEEP_R2` and
`TASK5_FRESH_R2`. Task4, unknown and copied profiles stay refused. For full task
ID `0818571f-5ff7-4d39-9d2c-ced5ae44299e`, the new r1 profiles bind the complete
unchanged control tuples in JSON cells[4] and cells[5], not discovered branch tips.

| New profile | Fixed producer/run/job/request | Failed inference terminal / output |
| --- | --- | --- |
| fresh/r1, ordinal 4 / repetition 1 | `e5e338aa22c247133936fa075c2def7bffb95173` / `37032230813` / `110933285330` / `9a53e9c0ae7b50400f2b27d514207e489b237cc5b5195ff8e36fcc4ea920370b` | `94628d12162da2e00cace216fdda5ce41f57e47f` / `70a69c818be5c7d751a0481808dbba86aa983b19` |
| keep/r1, ordinal 5 / repetition 1 | `a8353cd41f01f7d94129421512a57a62b9bd6997` / `37066171719` / `111036410671` / `22e0bc6f06e4c9c2ac2d3fa4bfe6a7c567ef24e9111bf319b704409d731997de` | `33278d9c26e8c8e8cfe68649e482e01f684d7705` / `5e56a906c4bd7a3510087ffc2efe392637e22be9` |

Both retain workflow `370228282` / attempt 1. The unchanged inert compiler
derives sealed configurations
`d67cbfeb3a26716d445b36a4466d5dc55559652381db71056aaf44a50a43e2eb` for fresh/r1 and
`4c75e2f0d8eb5a197fc44c2dc71b1abc166334c350791224ab5e3abc1a017cc3` for keep/r1.
Their private namespaces are `retention-task5-fresh-r1-budget` and
`retention-task5-keep-r1-budget`; each has its own corresponding
`retention-task5-*-r1-budget-observation.json` marker, with no wildcard selector.
The historical KEEP/r1 supplied-grader binding stays null. Existing r2 constants
and registered configurations remain exact.

Before RESULT retrieval, the shared verifier checks exact terminal/claim/manifest
controls, object identities, authority and immutable history. It then permits
only the declared RESULT at the fixed output commit and validates size/hash,
fingerprint, task, source and configuration before the unchanged
`codex_budget_pilot_grade_readout._budget_snapshot` projection. No ledger or
deliverable body is fetched. Unknown/copied profiles, discovery, wrong controls
and ambiguous or reused destinations remain refused.

The r2 budget constants and behavior, ordinary controls-only observation and
success intake remain intact. The eight execution bindings, producer/controller/
publication code, three jobs, permissions, secret scopes, concurrency/cancellation
and experiment settings are unchanged. Budget mode still excludes every other
mode and both paid jobs, including spurious nonempty request outputs. The
180-second read command and four-minute step bound remain. Current hash checks
precede lazy imports and credentials; GitHub/OIDC/runtime tokens are stripped,
destinations stay private and only the safe receipt is published.

All coupled expectations were updated together, including the six sites fixed
in PR732, both existing budget selectors and the shared pure workflow helpers.
The helpers contain independently authored four-cell expectations, not values
derived from the YAML being tested. No assertion was deleted or skipped.

### New actual KEEP/r2 observation supplied by the leader

Consumed budget observer `37125749122`, read job `111210580807`, succeeded at
`2026-10-03T13:21:06.8522139Z`; approval/execution were skipped. Observation
SHA256 is `eca874ea9123475d5632c08c90dc072942a296d3badb1f8923c44db48bb3b043`.
The verified RESULT is 7619 bytes, SHA256
`d17695351a36522df6b66a1e0fe0860e90410af92c11ec157672a0750ea282ff`, with result
fingerprint `657c19e44d255e6a2849a4f88bb60dab5e5a5710a846cc992abaa3b4e85d2077`,
recorded prepared fingerprint
`14e9357577a916bbeb974853dbe776534082ec16f608b03b20a16e21d0d5c829` and registered
configuration `1bda6431161ff4d27e751b3475979f861eb875beb7d16a608c7649830f051286`.
It uses the unchanged projector
`96d0dd63f5d67aa9f54e95615b4467357aa65ea5223418be47e120cc3ad5e815`.

```json
{"total_seconds":10800,"started_unix":1790987596.6290615,"expires_unix":1790998396.6290615,"remaining_seconds":0.0,"wait_seconds":8742.75936126709,"attempts_admitted":38,"native_resumes":37,"missing":{}}
```

This point is stored only in `cells[6].current_budget_observation`. Its source
outcome remains failed / exit 1 / cleanup true / grade null, with 38 recorded
model calls / known partial USD 0.847605. The zero-clamped remaining value is
not exact uncapped elapsed time or a failure-cause diagnosis. Wait measures
retry backoff only; admissions and confirmed resumes are native counters, not
model or HTTP calls. Only RESULT was verified, not ledger/deliverables or
overall payload; grading readiness and independent provider/input/CAS
authentication remain false. All earlier terminal-only evidence and missingness
stay exact. The report's r2 comparison is descriptive, not a causal ranking.

The immutable producer tuple remains source
`bdb7c21111a4c86136b6158f4969a39a9950acb3` / run `37081963299` / attempt 1 /
execution `111085094584` / request
`1b042b77fcc80b8c1a1c21fdd73feeefbcb80ce7f505b7c842aba496419386ac`, terminal
`3be1c0b892a199fdfccf3d5c4379d40c782119e5`, claim
`e7db56481f7cb2d908a9362ad1091022237afd21` and output
`3984e404ba59e0b7f356ca5d0426b57d4477ea50`. Its exact hashes, sizes, object-set,
authority and failed keep/r1 predecessor remain in JSON cells[6] unchanged.

### Actual fresh/r2 observation supplied by the leader

The leader supplied consumed budget observer `37119043633`, read job
`111191419176`, successful receipt `2026-10-03T11:17:04.8848163Z`;
approval/execution were skipped. Observation SHA256 is
`02892ab81228f52767087c2196be84bbeb2f7c399fdd600f773b4f4b74fbce36` and the
projector SHA256 is `96d0dd63f5d67aa9f54e95615b4467357aa65ea5223418be47e120cc3ad5e815`.
No raw payload was supplied, and the worker did not query or replay the read.

The verified RESULT has SHA256
`f68a695c50e26caa4f37984e190216c1bb5eb0553dd4c5c778edc3be521efdd1`, 6069 bytes;
result fingerprint `abbf03cb06df0c2b544992fdbfdb1c42346364d38e00d11ceedee00f37f59077`;
recorded prepared fingerprint
`ec31c8bf37bda72326fce9b99df8c4751f9713ceb2885002b9f2dbc789cfe8ce`; registered
configuration `3dd0af0802619dd60cc9eda5c492f6b75cd641463dca84a68ad5ad362e56074a`.

| Stored field | Actual recorded value |
| --- | ---: |
| `total_seconds` | 10800 |
| `started_unix` | 1791009579.9246106 |
| `expires_unix` | 1791020379.9246106 |
| `remaining_seconds` | 10724.012340545654 |
| `wait_seconds` | 0.0 |
| `attempts_admitted` | 1 |
| `native_resumes` | 0 |

The snapshot's `missing` object is empty. Time fields are seconds; started and
expires are stored Unix timestamps. Remaining time is zero-clamped, not uncapped
elapsed time. Wait is retry backoff only, and resumes are confirmed native
bindings. Admissions/resumes are not model or HTTP calls. Nonzero remaining time
does not identify the final failure cause or prove an absence of provider errors.

`cells[7].current_budget_observation` holds this later RESULT-only observation.
The historical terminal-only `read`, `terminal_details`, their missing reasons
and original closeout fields remain exact. RESULT-body verification alone is
true; overall payload, ledger/deliverable bodies and grading readiness stay false.
Detailed failure/recovery exposure remains unavailable /
`not_recorded_in_terminal_controls`. Publication-derived proof does not
independently authenticate provider activity, original inputs or actual CAS.
Observer `writer_acknowledgment=not_established` is distinct from producer acknowledgment.

The six historical failed-terminal observations declared 1 result, 1 ledger,
0 deliverables and 3 objects including the manifest; they did not verify payload
bodies. Absence of all partial work remains not established. The later r2
RESULT-only budget observations create no successful intake or grade.

The final producer remains `dfa812a2b7ad10b1aa3c7e873b4fabef9b195bd6`, workflow
`370228282`, run `37101934436` / attempt 1 / execution `111147701025`, request
`797141f8291078b82cf0d7a31c20fdadb5105bd0ad45d58f1225b8a39658c05a`, failed /
exit 1 / cleanup true / terminal publication acknowledged / grade null at
`2026-10-03T06:40:58.8935285Z`. Terminal
`4fdd9c2e3da1dbd7ef30d335d5fe378a4cddc84c`, claim
`c8abf52115d6fb9670da496043da4300d7315fd4`, output
`ddf15bff98aede8c714c5c3611ff30ee3e09afd9` and all their hashes remain unchanged.
The earlier terminal-only observer `37108712457` / read `111162238261` at
`f7439da4f3443ea67dc02ddea0cb3a1806622e0d`, receipt
`2026-10-03T08:11:30.6738396Z`, did not verify RESULT bodies. The original
17:05 KST brief lacked a numeric exit code; the 17:36 KST supplement supplied
integer 1 from that observer. Neither historical statement is backfilled.

Preparation `111143024723`, approval job `111143427544` and owner approval
`6824090693`, posted/read back once, remain supplied operational evidence.
Grader hash `9f656008909dbaf1e299cf42fecfabce11ced81a01d9aeff335a13d8e55d2cca`
and original bundle `757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`
are supplied provenance, not independent input/provider authentication.
The older keep/r1 reader's null supplied-grader field stays null; later actual
preparation hash `75f38c05e5c348e481e54f4c0b2000772c2414d7bae7519b1f2a38d92e1e0dc5`
does not rewrite it. KEEP/r2's supplied grader hash
`81bfae73b21f260ffd4985d701631f53c4ee7cb67e4d1a7ff39a7563598bbc6f` also remains exact.

### Single combined r1 proof

The new worktree was clean at tested HEAD
`bca9af2f4e97a82a72d55e9742bfd1f0a6ee3a1a`, tree
`044164c7d2406de3fb2600d5335bbff75dc45aeb`. No prerequisite or collection probe,
old proof, broad suite, CI query or live operation was run. The exact token-free
invocation was:

```text
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=/ai-work/copilot/worktrees/codex-retention-task5-r1-budget-observation-20261003-2215/batch-runner bash /tmp/retention-task5-r1-budget-20261003-2215.9Ke27u/run-proof.sh
```

The retained launcher ran only this command from `batch-runner`:

```text
timeout --signal=KILL 180s /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -q -s tests/test_codex_retention_task5_r1_budget.py::test_task5_r1_budgets_are_fixed_private_and_model_free --tb=short
```

It collected exactly one test and passed in 10.51s, with test/log-capture exits 0
and no timeout. Python 3.10.12 / pytest 9.1.1 were reported by this invocation.
The selector reached both exact r1 bindings and sealed configurations; changed/
missing current pins before import/session; fixed controls/history before
RESULT; source/cell/run/job/request/configuration/hash/fingerprint refusals;
missing/null/recorded-zero semantics; private markers/readback, no-clobber,
lost-ack/no-replay; unchanged r2 and controls-only paths; and all 576 mode cases
with spurious-request paid isolation. Network/model/writer/child/paid effects
were zero. Collection-time helper imports and exclusive fixture ownership were
preserved, with no duplicate source creation. Real validators stayed active;
only synthetic body identities were substituted in the test transport. This
proof does not establish an actual r1 budget observation.

Removing only the new KEEP current-observation field reproduced the delivered
JSON's Python compact sorted canonical hash
`bb8749e42de933000f126299616bdc2235c63bf420f6a4ebf5a7c16512924965`. The existing
fresh receipt, all other JSON fields and original pilot report bytes were
unchanged; the pilot report SHA256 remains
`88a37d8cfdae6c3c05a79db78827bfe2d59fdcd944067e4f6fcd7f387dddae0e`.
This local evidence check is not independent authentication of a private receipt.

| Current proof/artifact | SHA256 |
| --- | --- |
| `proof.log` | `33544c4e25e1ca9ab7acd5b9178e66588cd5aeeed97c60b4c197d3906e37cf58` |
| `run-proof.sh` | `ac06edcfe2573014b1d6b15addc4fb99538f01a57ec6dfdd3135073c29d19257` |
| `status.txt` | `efcc32872ebd2ff7620b538ec980fab2614614b8fec099cef21b6db2e4cdf2e7` |
| Invocation record | `84e5c426551c576778da91a8f86dea30033961e6208f09ecba42f7767a775ac8` |
| Combined r1 selector source | `da289ab121454753df3d558095ba084781ecf5d89bc9790c5208503d29537d74` |
| Report with the bounded r2 comparison | `21990ef4a53b474b74f4479f628ca18855d80b8e5cbb34e40ead3f1c4df9d2d6` |
| JSON with both separate r2 observations | `e8b79d25813bde83fc3b9b5615b73151016a702a75fb94b92d4b356cf73b497d` |

### Preserved PR732 proofs

The accepted [PR732 task record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/b3bb851e3e527e3be97f3a282df47367e84bdfdc/tasks/LATEST_TASK_RESULT/README.md)
retains both exact commands and their reached boundaries. Its new-feature
selector at `417db02a9433efe312202a4da6535979eeb7deda` passed 1 test in 7.26s
with 576 cases. Its separate six-file compatibility correction at
`1e775e4338046632a4f66f387eb4fccad4b0f699` passed 1 test in 5.29s with 576 cases.
Both had test/log-capture exits 0, no timeout and zero recorded live effects;
durations are pytest's, not outer elapsed time. Neither was rerun or relabeled.
The missed two-profile expectations at `a67911109c3a768b74f068520f2a72338e04001c`
were static mismatch evidence, not an observed CI failure. That earlier
correction had 30 insertions / 18 deletions across six tests and no runtime/data
changes; the other five tests were not executed by its one-selector proof.

| Historical PR732 evidence | SHA256 |
| --- | --- |
| 7.26s log | `c5065d19a0a3d042ed98d13cb268a243b3cef582168adcb012b368e93f200254` |
| 7.26s launcher / selector source | `214f3e09f54b75450edd63db3e418c023523db7be5241effba8bda891f3ae23a` / `77efa6bd9d3e04b7f80f74c0b0f86fd33ed59eed6349d706a5913b11a508f513` |
| 5.29s log | `3b71391b4887693392963a829ac3bae160f594890a08edc6d136ca66b58e0783` |
| 5.29s launcher / selector source | `a0c120f423e421bc5fa73c5190c9a76c9bfc4b90f54eebf1212b5265fffcf691` / `aad3e06627db7a2669ee8baa1a90818e8bf51ecc00f4fd132479ba61e9812dac` |
| Both status files | `efcc32872ebd2ff7620b538ec980fab2614614b8fec099cef21b6db2e4cdf2e7` |
| Historical report / JSON | `412feb95c965ce6477d2fec3cb30bf7672c5b5b2f06bd96ed3de6770d396f7f1` / `394d96519362164bc5edd5994600fffe349b1273a491761200c1ee266cdcfd4b` |
| Pre-observation canonical JSON | `aaea03354686ada4e716b4eb0eb24b9c1ab964d8e4e4e4210e5b960519dfdd89` |

### Current pins and immutable evidence

Only the shared reader hash changes in the observer's separate
`CURRENT_DEPENDENCIES`. Both workflow shared-reader preflight and CLI pin pairs
use it. All other current dependency values, including the budget
projector, remain exact; historical producer/`RESULT`/`PARENT`/`READER` evidence
is not repinned.

| Current executable | SHA256 |
| --- | --- |
| Shared result/terminal/budget reader | `dd23824360e03f415feb5c7d247024ac7d67300c4ed7f2120e0eb2c9d6e47eb9` |
| Grade observer, current-reader pin only | `6c7793b0b0913103970d9bb6c85caa11cbeea0319efd2c5e2d2d9c7fbc3a32fe` |
| Existing workflow, four closed Task5 budget cases | `a7faab701e41f793a3050d02defee1698627cdd878329dc79052184dc1597849` |
| Unchanged budget-projector module | `96d0dd63f5d67aa9f54e95615b4467357aa65ea5223418be47e120cc3ad5e815` |
| Unchanged KEEP/r2 producer adapter | `7ac1e8d8014e7fff765c65a80774d808a8b34d2cc2d88af8ef9ba8580ad820af` |
| Unchanged fresh/r2 producer adapter | `6f1b78b8956e58b147802921e69d3009fd9ad774fced22037dbd112ecddcd4bd` |

Historical grading digests remain
`25d2591a2b53d3055a7efb46b55ce86bab811a702e6598b7119f0625784b6ca0` and
`1ced90e270d80055cc3482bea4a5489f045f1b9dcb0ed2622ebd8de80285a56d`; intake remains
`4d33c1160fe27af76fa37cf1360d85e7cdeb92992ccfaf748ee65bb6c80c84a4`.

### Prior outcomes, accounting and proof limits

Eight registered cells remain two successes and six failures with null grades.
Task4 KEEP succeeded in 2/2 and FRESH in 0/2; Task5 both treatments succeeded in
0/2. These are descriptive results only. In registered order, the inference
call/known-USD pairs remain 10/0.409894, 39/0.303358, 39/0.29944, 6/0.22195,
18/2.576093, 13/0.413364, 38/0.847605 and 1/0.13489. Prior Decimal totals remain
164 calls / USD 5.206594, comprising Task4 94 / USD 1.234642 and Task5 70 /
USD 3.971952, all known partial inference rather than invoices. Estimated/runtime
costs and HTTP counts remain null; `call_reachability_unknown` and applicable
`usage_absent` reasons are unchanged. Cached/reasoning counters are subsets.
The final receipt retains input 66249, cached 37632, output 3596 and reasoning
2675 tokens; one recorded generation component does not rule out unrecorded
provider errors or native retries. Null generation cost or recorded zero usage
does not prove free work or zero actual usage.

Task4 grades remain 30.6/45 = 68.0% included / 54.64% full and 30.35/45 =
67.44% included / 54.20% full, each with 9 exclusions / maximum 11 from full
maximum 56. Their separate 93/91 grade calls retain `price_missing`, null
known/model/estimated/runtime costs and HTTP counts, and invoice false.
No global grade average, cost-efficiency ranking or regrade was added. The
original 30-cell pilot stays closed at 24 epoch04 outcomes (18 graded / 6
model-free UNGRADED) plus 6 frozen epoch03 failures, not 30 identical-source successes.

PR731's [immutable task record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/c84c406b8c41a6998fc6311b675b8b8708f1f026/tasks/LATEST_TASK_RESULT/README.md)
retains the prior exact commands, source pins and saved logs. Its first actual
selector passed 1 test in 9.50s with 576 cases, test/capture exits 0 and no
timeout at `db48f5ec661ad20bbf422ab4bc00a4bd564b715c`, with implementation bytes
unchanged from `64bcb21c8d6ad04b6999dfb214576397d89bfb7d`; log SHA256
`2cee50d40a6fdbdb28566c27f344f94e17cedfab7f0be4030d3898de25198528`.
Its separate launcher-127 failure occurred because `/usr/bin/time` was absent,
before timeout, pytest, collection, fixtures or assertions; capture exit 0,
no pytest duration, log SHA256
`4406ff374092e54cb7d6383d83fea174581b0770e6b4a35ecfb03a369cc7ecd5`.
Neither is this new proof, and neither was repeated.

Accepted report HEAD `47978bdcd8b6026f9bd35ff24e94e8771a672544`, review
[5399909431](https://github.com/hyeonsangjeon/gdpval-realworks/pull/730#pullrequestreview-5399909431)
and all nine applicable checks remain prior evidence. The 0.289s report check
at base `f7439da4f3443ea67dc02ddea0cb3a1806622e0d` with working-tree artifacts
retains log `896e281a5b6b7e9e29736cc066e21bf98e97047ec81cc05d113ca54aab2f7080`.
The 0.001517s exit-code addendum check against
`c5ea85c83a0cf26eb2cc74f6c8bb15929346e972` retains log
`6c88bb666a2e1036d56fa708beb42c03f215b1a753f02e9e2705a8041a049af1`.
Both had check/capture exits 0 and no timeout. Original snapshot hashes remain
historical; the corrected prior JSON hash was
`42839c92b3aac1c36a3bd3b3afa0930f1bd1f882d711cf12bb78bf4fbc832f5c`, not the
current artifact hash above. Accepted PR729 HEAD
`70c80baa5c150d1734bb77de7fac1ebaac17b303`, review 5399481664 and all ten checks
retain the 17.09s proof at `245fbd54abbfb6a9d7420c3e73ec27ce643fd0e5`, log
`9655c23bb2b7ce0f304a8e92bc92f580ebccdfd113cdbb608f9c20bc86fecd50`.
No accepted proof or review was repeated or relabeled as validation of new bytes.

The [immutable pre-report record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/f7439da4f3443ea67dc02ddea0cb3a1806622e0d/tasks/LATEST_TASK_RESULT/README.md)
preserves all earlier commands, selector scopes, corrections and failure boundaries.

| Historical proof | Preserved failure and log SHA256 |
| --- | --- |
| `2068c92d4841e5f7be7aa9e9fc027c9dcc0205d5` | 1 failed / 2 passed in 51.26s, exit 1, no timeout; fresh-state fixture sequencing refused. `15c8dbf5bf0534c2630dc3a9c9a6a7821b1412c5fcced67a83d23a686cb98495` |
| `e29f26b8e3ae91907fb7ba759da0feeee20d7046` | 1 failed in 26.67s, exit 1, no timeout; execute-return stopped at `retention_terminal_unresolved:hf_operation_failed`. `51a95d83582a52fb70275391af6c2338c04230b2de1deb226e69f4685f5f6b53` |
| `77118007ffe9d676e740e98d36bb8e6847fc3a8d` | 1 failed in 29.18s, exit 1, no timeout; original `ValueError` at `batch-runner/core/inference_manifest.py:110` from the then-hardcoded Task4 discriminator. Three synthetic commits returned, writer acknowledgment stayed zero. `f9a9d047ead8725b9d83b15b687c374725a7ffd4df4fd6e98a51a7734cefb7c2` |
| `f4a2c2fdd87e7b69ee99fec52bc0e33fcb19e2d9` | 2 passed / 1 failed in 17.71s, exit 1, no timeout; late helper import reached the active Popen refusal fixture before routing assertions. `74c75d9273fb30cb54c51f71dc3ec236756797c917e112d01fb9a35c9bc86dcc` |
| `703d9bbf94f59045c4a04d58bf16ddda82d905a0` | 1 failed / 1 passed in 7.64s, exit 1, no timeout; duplicate exclusive source creation raised `FileExistsError` before lifecycle entry. The 288-mode selector passed at that HEAD. `3365b47a58477e67d93537a12776a2c6d32546b28066221881d26348f0c6fbf5` |

The first two failed memo streams retain failure-record SHA256
`5f78b7d705e339ed48fa6f643e657e5060e6304a957a5222cd1b3d6321b59456`.
The third, after the one-line obsolete agent model-field removal, retains
`5e5e1e2d35dc797b08d6bd2d0445e887d2abfb23205af7cb2065aaf59962f66d` and
`stream disconnected before completion: response.failed event received`.
None returned an approving memo. The obsolete route rejection does not identify
their internal failure cause. Later direct leader decisions are scope-specific
transport substitutions, not returned agent verdicts. Those failures stay failures.

### Skills and remaining work

The complete catalog was inspected once for this unit. `experiment-design`
preserved only the measurement boundary; `experiment-report-en` then protected
`im-not-ai-en` apply to the supplied numerical evidence and completion passages.
No new experiment-design axis, memo request, UI or repository audit was added.
The registered settings remain exact: GPT-5.4 / direct-v1 / xhigh,
SDK/CLI 0.147.0, mechanical B/no C, one concurrent inference, 10800 cumulative
seconds from first admission including waits/recovery/downtime without reset,
and 1800-second native-turn wait, not an all-in attempt ceiling. KEEP/FRESH
remain guarded within-cell treatments with no fixed admission or automatic
monetary cap. No design, provider, runtime or budget axis changed.

Source/structural/candidate checkpoints, a factual-change ledger,
literal/date/link/hedge reconciliation and reverse-condition review preserve
the distinction between actual supplied evidence and synthetic proof, original
terminal-only missingness and later RESULT-only measurement. The protected
copyedit makes no factual changes. This bounded same-session editorial review
is not independent source approval. No UI/animation skill, repository audit,
agent-policy change or memo request was used.

Final independent review of the new immutable HEAD, applicable same-HEAD CI and
delivery remain leader-owned and still precede either separately authorized r1
model-free read. Both r1 budgets remain unobserved, both r2 observations are
consumed, and no live-read authority is granted. Only finite
execution and available accounting are closed, not the whole Project5 card.
Realized budget/wait/admission/resume and attribution gaps remain. Post-selection,
two repetitions, fixed order/service variation, source-wrapper evolution,
unavailable recovery detail and uncalibrated judging prevent causal retention
or model-performance claims. Missing prices, exclusion causes/item overlap and
intermediate-input comparisons remain gaps. The GHCP Sol VM card stays blocked
without a KVM/image handoff; no recheck or substitute runtime was attempted.
Neither the original pilot nor the eight-cell inference sequence is reopened.

Git author/committer remain `hyeonsangjeon <wingnut0310@gmail.com>` without
attribution trailers. No Project edit, merge, Azure/HF/live-outcome query,
model/grade call, dispatch/replay, install, permission/budget change or old-proof
rerun occurred. These records stop at pre-merge facts.
