# PHASE 3 — perception firing (smoke)

## Probe design

`scripts/phase2_perception_probe.py` (named `phase2_*` for historical
reasons; semantically this is Phase 3 in the rev2 plan).

- Build a v2-mini Grader from `grading_configs/default_v2_mini.yaml`
  (which carries the `judge.perception.{visual,audio}` block).
- Synthesize a tiny PNG deliverable in a temp dir.
- Construct a `TaskRubric` with one VISUAL criterion and one TEXT
  criterion (control).
- Call `grader.grade_task(...)` end-to-end against real Azure.
- Acceptance gate per rev2 spec: `perception_called > 0` on VISUAL item
  AND `judge_error rate < 2%`.

The script does **not** re-grade exp003 because the modality
deliverable binaries that the existing perception-off v2-mini grades
ran on are not staged locally (only the exp997 2-task smoke is), and
inference is non-deterministic so they cannot be faithfully
reconstructed. Probing wired perception against a synthetic deliverable
is the cheapest honest test of the firing path; comparison against
existing perception-off grades happens in Phase 4 (gated on owner gold).

## Live result

**ACCEPTANCE: BLOCKED (cannot test live).** Two consecutive runs against
real Azure both came back with auth failures *before* the model could
reach any tool dispatch:

```
   ⚠️  Grader OIDC failed (ClientAuthenticationError); falling back to AZURE_OPENAI_API_KEY
ToolCallingJudge upstream call failed: PermissionDeniedError: 403
  {'error': {'code': 'AuthenticationTypeDisabled',
             'message': 'Key based authentication is disabled for this resource.'}}
```

Specifically:

1. **OIDC** (`EnvironmentCredential` from the .env service-principal) is
   rejected: `AADSTS7000215: Invalid client secret`. The SP secret in
   the local `.env` has expired or been rotated.
2. **API-key fallback** (the Grader's own bypass for local debugging)
   gets HTTP 403 `AuthenticationTypeDisabled` from the resource: key
   auth is disabled on the Azure OpenAI resource.

Both auth surfaces are owner-controlled and outside this task's
ownership scope (per constitution rule 8: "No AZURE_OPENAI_API_KEY
dependency (OIDC only)"). I refuse to "search for a reading that lets
me proceed" (rule 12) — the live firing rate is **unverified**.

What the probe *did* prove during this session: the wiring is loaded
correctly. The probe printed:

```
tool_judge active:        True
vision_perception wired:  True
audio_perception wired:   True
judge model: gpt-5.4-mini | vision model: gpt-5.4
```

i.e. `_build_tool_judge` constructed both perception sub-judges from
the YAML, attached the Grader's Azure client, and would have made tools
available to the model — but the upstream HTTP 403 stopped every
request at the Responses API call, before any tool could be dispatched.

## Side fix in the probe (not a wiring fix)

The previous probe attempts also failed with
`UnicodeEncodeError: 'ascii' codec ... position 102-105` in the api-key
header. Root cause: `batch-runner/.env` line 2 has an inline Korean
comment trailing the value; the probe's naive `.env` loader treated the
whole tail as part of `AZURE_OPENAI_API_KEY`. Fixed by stripping
` #...` from values in `scripts/phase2_perception_probe.py`. **Not a
grader bug** and not in the wiring path — only affected the local
probe.

## Indirect runtime proof

Pure unit-test wiring proofs (Phase 2 doc, all 5 tests PASS) cover:

- VisionPerception/AudioPerception are instantiated from config.
- The model dispatching `vision_judge` on a VISUAL item flips
  `perception_called=True` and adds `"vision_judge"` to `tools_used`.
- A TEXT item leaves `perception_called=False`.

These prove the *wired path* end-to-end at the unit-test boundary; they
do **not** prove the live model dispatches `vision_judge` for any given
real criterion (the model's tool-choice behavior is what we wanted the
live probe to measure). That measurement remains unfilled.

## What's needed to satisfy the live acceptance gate

Owner action — one of:

- Refresh the OIDC service-principal client secret in
  `batch-runner/.env` so OIDC succeeds, then re-run
  `python scripts/phase2_perception_probe.py`; OR
- Re-enable key-based auth on the Azure OpenAI resource (temporarily,
  for local debugging); OR
- Run the probe from within the existing `.github/workflows/grade-run.yml`
  pipeline (workload-identity OIDC works there) — but this would
  require a workflow job and is out of scope for a local probe.

## Recorded for Phase 4

Even when the live probe runs, the rev2 spec's Phase 3 acceptance
("modality item perception call > 0 AND judge_error < 2%") only
verifies that the path *fires*. It does **not** establish that
perception is *more accurate*. That is the Phase 4 question and is
independently gated on owner gold (Phase 1).
