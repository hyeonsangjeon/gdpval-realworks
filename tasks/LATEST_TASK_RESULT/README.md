# First-cell private storage metadata route — 2026-10-06

The fixed read-only Actions route and its helper are implemented, but local
validation failed. The sole selector reported **17 failed, 8 passed and
1 teardown error in 5.31s**, exit 1. A narrow linked-source correction followed
without another invocation. Corrected-source review and CI remain required;
there is no positive private-target or prefix observation from this task.

## Scope and review basis

The independent branch starts from accepted main
`b4e15f02c1db8674ffeff83f133c710627c696e8`, tree
`5de4c1ce82dcfeddf0178a52c6c3bf0e40bae54f`. PR757 and its old worktree were
left untouched; no PR757 source was stacked or copied into this branch.

The leader performed the actual read-only pre-edit CI/secret-charter review,
separately from implementation, and issued **APPROVE-WITH-CONDITIONS** for
implementation and one synthetic proof. The supervisor retains
`project5-storage-metadata-decision-1715.md`; its operative conditions were
supplied in the task. This is not a successful spawned-agent review. The
unavailable model harness was not retried, and no agent, model, billing or
account setting changed.

Only these implementation surfaces were added:

- `.github/workflows/gpt54-time-budget-storage-metadata.yml`
- `batch-runner/gpt54_time_budget_storage_metadata.py`
- `batch-runner/tests/test_time_budget_storage_metadata.py`

The workflow binds `hyeonsangjeon`, the fixed repository, main, exact reviewed
workflow/checkout commit and tree, and attempt 1 before the credentialed step.
Checkout credentials are nonpersistent. Setup is credential-free; only the
single metadata step receives `HF_TOKEN`. Effective permission is
`contents: read`, with no `id-token: write` or Azure login. The metadata job has
a 10-minute ceiling including setup; its HF operations share a 60-second
deadline and a two-request limit, without retry or redirects.

The helper reuses the existing bounded HF transport and exact private-target
validator. It requests only privacy/head fields at main, then metadata for
the exact prefix at that returned immutable commit. The SDK's paths-info POST
is read-only metadata, not an HF write. No sibling listing, claim/result body,
original input, repository creation, branch setup, upload, model or grader
operation is selected. Access errors, malformed metadata and timeout cannot
become an absent-prefix result.

The only public artifact is `time-budget-storage-metadata.json`, containing
`format`, `source`, `ci`, `timestamp_utc`, `target_identity_sha256`,
`verified_private`, `parent_commit`, `prefix` and `prefix_outcome`.
`verified_private` is true only after the exact private-target check, otherwise
null. Prefix outcomes are `absent`, `present` or `refused`; a verified first
response may be retained when the second operation refuses. Raw exceptions,
tokens, headers and private objects are excluded by the publication schema.
This is only a candidate parent for a later request, not input verification,
host support, paid permission or observation admission.

## One bounded proof

Tested HEAD: `7984413c3829c157eef50a8499c9a3549e869dbf`

Tested tree: `ff76c9b2d4eedbf01740248ae6d7732e4f84e46e`

The retained command checked that exact clean HEAD/tree before and after the
invocation. It used Python 3.10.12, synthetic temporary Git identities and
synthetic HTTP responses, with socket/write sentinels and telemetry disabled.
No live HF metadata or private asset was accessed.

From `batch-runner`:

```bash
timeout --signal=TERM --kill-after=5s 300s \
  env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTEST_ADDOPTS= \
  HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 \
  GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_NO_LAZY_FETCH=1 \
  /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest \
  -o addopts= -o junit_family=xunit1 -p no:cacheprovider -m 'not integration' \
  -vv --tb=short --color=no \
  --basetemp=/tmp/pr758-storage-metadata-proof.SFIDHpPp/pytest-tmp \
  --junitxml=/tmp/pr758-storage-metadata-proof.SFIDHpPp/junit.xml \
  tests/test_time_budget_storage_metadata.py
```

The reported outcome was **17 failed, 8 passed, 1 error in 5.31s**, exit 1.
There was no `-x`, skipped/deselected case or bound expiry. All 25 selected
cases finished; `[blob]` passed its call phase but failed teardown. That is not
an additional passing case or a successful invocation.

The exact node prefix below is `tests/test_time_budget_storage_metadata.py::`:

| Function | Exact parameter IDs | Outcome |
| --- | --- | --- |
| `test_time_budget_storage_metadata_roundtrip` | `absent`, `present` | Both failed at credential-free `validate-source` |
| `test_time_budget_storage_metadata_source_refusal` | `actor`, `ref`, `source`, `tree`, `attempt` | Passing call phases |
| `test_time_budget_storage_metadata_source_refusal` | `blob` | Passing call phase, teardown error |
| `test_time_budget_storage_metadata_target_refusal` | `missing_credential`, `nonprivate`, `wrong_target`, `bad_parent` | All failed |
| `test_time_budget_storage_metadata_transport_refusal` | `head_401`, `head_403`, `head_404`, `prefix_404`, `prefix_timeout`, `prefix_redirect` | All failed |
| `test_time_budget_storage_metadata_malformed_prefix` | `not_list`, `wrong_path`, `duplicate` | All failed |
| `test_time_budget_storage_metadata_cumulative_bound` | No parameter | Failed; transport call count was zero |
| `test_time_budget_storage_metadata_final_source_reread` | No parameter | Failed; transport call count was zero |
| `test_time_budget_storage_metadata_envelope_allowlist` | No parameter | Passed |
| `test_time_budget_storage_metadata_workflow_contract` | No parameter | Passed |

Artifacts are retained at `/tmp/pr758-storage-metadata-proof.SFIDHpPp`:

| Artifact | SHA256 |
| --- | --- |
| `run-proof.sh`, exact unredacted invocation and pin checks | `fbd4c94d113132c6acc32f82237e5d27d2081bbfd561e6db0e1c202c9490a088` |
| `pytest.log` | `a22910af6f139bd9f05605a9b36012921d503f6d289c68d7f35ab3acd02621b0` |
| `junit.xml` | `9dbb8a2fe8fb5a402ba503cf53438c9743f8a19cbfde69b406b60e63f1b9ad87` |

## First failure and unrerun correction

The first observed failure was `roundtrip[absent]`: `validate-source` returned
2 before the first metadata request. Read-only inspection of its retained
fixture showed an ordinary detached repository with a `.git` directory.
The reused `_registered_gitdir` validator requires a linked worktree under
the common repository's `worktrees` directory, including reciprocal Git
registration files. The fixture and the original workflow setup did not meet
that contract. The downstream absence of an envelope was not a private-target
or access-error result. The tree/blob negative cases do not prove their
intended guards when the source layout already refuses.

The teardown sentinel recorded one generic forbidden effect, without a
call-site label. Its exact source is not claimed. The original fixture also
forbade every `time.sleep`, including ordinary bounded Git subprocess waiting.
The correction confines that prohibition to the online HF session while
retaining socket and HF-write sentinels. No successful source, privacy or
digest validator is mocked or weakened.

Unrerun correction HEAD: `26b1b4c161e33d956c2f3b4b3a392e95afa3a843`

Unrerun correction tree: `17c7dc2eaaa7404913f947ca48bf4c3f00c524db`

That correction creates a genuine detached linked metadata source during
credential-free workflow setup, binds it to the actual Actions checkout's
common repository and exact commit/tree, and uses the same layout in the
synthetic fixture. The existing source validator remains unchanged. Neither
the corrected route nor its downstream metadata behavior was rerun locally.

The exact post-proof scope is the new workflow, helper and test correction
plus CHANGELOG, this LATEST record and the README's direct usage section.
After the correction commit, only those three documentation files change.
No core, old workflow, registration, frozen F/profile/hash, input or inference
route was edited. The fixed 20-observation study, GPT-5.4/direct-v1/xhigh,
1200-second generation/shared 20-second cleanup, one attempt, concurrency 1
and 45-minute observation-job ceiling remain unchanged.

## Remaining gates and earlier evidence

Final source review and corrected-HEAD ordinary CI must establish the unproved
paths before acceptance. No CI query, dispatch, retry or poll was performed.
After delivery, the leader must select the accepted-main SHA/tree and authorize
the separate read-only metadata dispatch shown in the README. No real private
flag, parent commit or prefix state is established here; the earlier NAS packet
still has zero HF operations and unknown values. The leader reported that the
Actions secret list contains `HF_TOKEN`; its value was not read or moved to NAS.

Any later observation still needs its own exact source/input/host/request
identities and independent live direction. Existing parent CAS, nonrenewable
claims, kernel ownership admission and grading gates remain mandatory.

The [accepted-basis record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/b4e15f02c1db8674ffeff83f133c710627c696e8/tasks/LATEST_TASK_RESULT/README.md)
preserves the earlier grading, observation and host evidence through immutable
links. PR757's [1 passed in 15.88s correction](https://github.com/hyeonsangjeon/gdpval-realworks/blob/32b5fadcb4346fc576b1e5e631b164c596f68bf4/tasks/LATEST_TASK_RESULT/README.md)
remains separate from its [10 passed / 1 failed continuation](https://github.com/hyeonsangjeon/gdpval-realworks/blob/561219c661e8a5f05cd20c1637aac792d782a887/tasks/LATEST_TASK_RESULT/README.md)
and [original failed invocation](https://github.com/hyeonsangjeon/gdpval-realworks/blob/0fe559377bbbd20eab790dd7a5c48e4509911c90/tasks/LATEST_TASK_RESULT/README.md).
None is blended with this failed metadata selector or treated as live authority.
