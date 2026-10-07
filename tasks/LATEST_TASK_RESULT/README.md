# Latest task result

## Prospective native static-refusal preservation

The shared execution-failure classifier now preserves an explicit list of
30 static codes from the accepted native callable and its parser. Known
`CodexObservationRefused` codes use the existing `observation_refused`
category. Unknown, malformed, non-string and multiple-argument native errors
retain `validation_refused / execution_refused_or_uncertain`. No exception
text, class name, traceback, local value, prefix or regular-expression match
is published. Imported equality-check messages remain generic.

The legacy V2/controller/registration/deadline vocabulary is kept separate,
so a native-only string cannot give those classes new diagnostic authority.
The existing receipt schema validates the finite union. Its shape and
validator/emitter bodies are unchanged, and the existing uncertainty reader
uses that same validator without a helper or workflow change. This is a
prospective diagnostic correction, not a runtime fix or execution authority.

Accepted base is `9fbdc37fb0ec0e4eb79d32b22f37641235a24186`, tree
`2e72a30ccf0cf7aeea6be5c2e842a023dfd0b4bc`. One origin/main check matched
that base before creating `b/codex-native-refusal-taxonomy-20261007`.
The leader specified this narrow source-grounded change; no new independent
reviewer endorsement is claimed and no reviewer harness was retried.

## Pinned source and one bounded proof

Tested source is `e0ae6d8ccc20e14dc3c7f7686c035873582001e1`, tree
`26a3bbb312731202d8e85bc4651651b6d26af565`. Only these two files changed
before the proof:

- `batch-runner/gpt54_time_budget_v2_ci.py`: blob
  `490f9341aa53f363aa94c2389cffe0c62aca347d`, SHA256
  `17a388bb3c0e40abe4b1eaf5c4ea70f8e46d093cf8faee920d76014ad4a9f6bb`.
- `batch-runner/tests/test_time_budget_native_failure_taxonomy.py`: blob
  `c2219e0694103b7787e404ba2a503eb7228fb435`, SHA256
  `aa8c7793636f978f326fea1235a6424bad9f184439ca88ae251ff5107fbd5658`.

The native callable remains blob `21f592472ad78991d69e6d11af58cf88e1de615e`,
SHA256 `fbc056b86b9e91cfc50a42f6181eac20de0af23748907687e058742a1c7d4d52`.
A static AST comparison matched the handwritten list to its 30 literal
`_require`/parser codes. Production does not generate an allowlist through
introspection. Syntax, parametrized arguments, exact source/tree and file
scope were checked before any test body ran.

The one invocation reported **10 passed in 1.24s**, exit **0**; Python wrapper
elapsed **1.715750s**, zero retries and no collection failure. It used the
existing Python 3.10.12, pytest 9.1.1 and pytest-timeout 2.4.0, with an overall
300s+5s bound, no `-x`, offline settings and 30s read-only Git bounds. The
test bodies require no Git/Bash fixture subprocesses. Exact command, run
from the pinned worktree's `batch-runner` directory:

```text
/ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -p pytest_timeout tests/test_time_budget_native_failure_taxonomy.py::test_time_budget_native_failure_taxonomy -m "not integration" --tb=short -ra --basetemp=/tmp/native-refusal-taxonomy-proof.a5VL6x/pytest-tmp --junitxml=/tmp/native-refusal-taxonomy-proof.a5VL6x/junit.xml
```

The outer invocation was:

```text
timeout --signal=TERM --kill-after=5s 300s /ai-work/venvs/gdpval-realworks-py310/bin/python /tmp/native-refusal-taxonomy-proof.a5VL6x/run-proof.py
```

All ten scenarios passed: representative native guards, unknown native
text, a reason reserved for another class, no arguments, non-string data,
a string subclass, multiple arguments, malformed argument storage, legacy
compatibility and safe uncertainty projection. The guard case exercises
eleven representative static refusals; it does not execute thirty native
guards. Real classifiers and receipt/manifest/projection validators ran
with synthetic data. Named network, process, provider, controller, native,
kernel-construction and exception-formatting sentinels were not reached.
The V2 event retained its exact default bytes. Unknown/extra private fields
were refused by the real readout validator.

There was no native/provider execution, kernel-ownership probe, HF access,
grading or live readout. No earlier selector or full suite was rerun. This
proof is not a real-host readiness check or an explanation of the historical
observation.

Artifacts are in `/tmp/native-refusal-taxonomy-proof.a5VL6x/`:

| Artifact | SHA256 |
| --- | --- |
| `run-proof.py` | `e1a9e34e87e52ab1033ea2583a3912092e83c5561862bfbfc5dbe0271a007b29` |
| `command.json` | `d18ed781613b28ac020dbe4196082d3ef1668a65addaedb1789cf6877ebe12cf` |
| `source.json` | `b8892af4147fc872a3183dcc4a8a7ac9779d3df486f9499ad6a70e8cad36f521` |
| `pytest.log` | `f2742d65aecc107aeb794418769cb2446d97bf411d112cdd6f03b1534f892db5` |
| `junit.xml` | `4a7854db13907f9a16c23d545e4c165dd02d1d50b35a519b83c726092acade8d` |
| `cases.json` | `0dadf9dbc248f9d8801290091eab9312a21ef74be77a04f5073a87c8718ea9db` |
| `outcome.json` | `733748929e6ffc7f226244d51b9f4d83853466a64be239c0f04091b53fa6de06` |

Only CHANGELOG, this LATEST record and the direct README evidence change
after the pinned proof. The final commit/tree, draft PR and artifact hashes
are recorded in `/tmp/native-refusal-taxonomy-proof.a5VL6x/handoff.json`.
That external handoff avoids embedding a commit's own identity in its bytes.

## Historical evidence remains separate

The leader verified historical readout `37585054563`, run number 4, attempt
1, artifact `11466485746`: projection **2027 bytes**, SHA256
`36882db90cc0a348c60f760134a1a5955a09d83ed2083da571795faa339aaee2`, ZIP
SHA256 `b016f8622fab90cab1bf88fc25bf430f5c1af17b4cee9f566eb2aff8804ee7bb`.
It bound controller C `9fbdc37fb0ec0e4eb79d32b22f37641235a24186` to original
R `b0bba8c71369605fd4261c59259e3cc3924de981`, tree
`f9bb914a717d3fc1326ac8e1e925119cfaee307f`; original request **2369 bytes**,
SHA256 `c78a581c482baf495b09efad70899e0067293752f3cc7320f54f2af0079fa062`;
claim `4ca4fd9c86fe1253059fffc66f6e4397c34c3c4e`; output
`d443e8045f58b6f7b4b35ed7f1888182b62296e0`. The fixed cell is
`gpt54_time_budget_v1_codex_r1` / `codex` / repeat 1 /
`02aa1805-c658-4069-8a6a-02dec146063a`.

The downloaded manifest was **observed**, not independently expected:
**1096 bytes**, SHA256
`458db9999f436360072181f5e1907b15c4c9f2c1ed018829137920fd495ade5e`.
Claim and request objects were not reread. Its retained failure was exactly:

```json
{"stage":"observation_callable","category":"validation_refused","reason":"execution_refused_or_uncertain"}
```

No more specific code, raw exception or model call survives that projection.
This patch cannot recover the lost reason or rewrite that receipt. Native
Task1 remains consumed/uncertain; model calls, cost and cleanup are unknown,
not zero. The [prior readout record][prior-readout] retains the original
execution/retention identities and separate 17-case implementation proof.

PR770 `ab0662ec687369bb41a1d62bd43c6b38a4c4f273`, tree
`89e49c81340ab948510fc526dc5253e4d2b4e616`, remains unchanged. Its
[synthetic full-path proof][native-boundary] found no deterministic
production defect; it was not rerun or combined with this proof. PR769
`2a8f6c754a160c50c4a13589132d09c99828b28b` also remains untouched; its
pending emitter change is not integrated here.

## Preserved boundaries and remaining gates

The catalog was read once. Retained source/CI guidance informed the scope;
experiment-design held the existing 20-cell study fixed. experiment-report-en
and im-not-ai-en kept synthetic outcomes, leader-supplied historical facts
and non-proof statements separate. No new design or model-review loop ran.

The registration seal remains
`3dde5f2f62e8ada29c883e1ef0eb555c969987f710b437af50c513ac9b52d22f`.
Frozen F `882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`, source pins, study conditions,
model/prompt, budgets, workflows and execution controls remain unchanged.
No runtime pin update is needed for this controller-only taxonomy change.
The one-attempt/concurrency-1, 1200+20-second and 45-minute limits stand.

Remaining gates are source review and final CI, then an accepted controller
and any separately directed readout or live action with its existing
input/auth/host/claim checks. No such operation is authorized by this patch.
No CI query, dispatch, retry, Project change, merge, private fetch, paid call
or grading occurred. Consumed V2 Tasks1–5 and native Task1 cannot be replayed;
no next cell or ABBA advance is authorized.

[prior-readout]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/4b5088a9f338adee58fe89436836ccc6c9f3363c/tasks/LATEST_TASK_RESULT/README.md
[native-boundary]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/ab0662ec687369bb41a1d62bd43c6b38a4c4f273/tasks/LATEST_TASK_RESULT/README.md
