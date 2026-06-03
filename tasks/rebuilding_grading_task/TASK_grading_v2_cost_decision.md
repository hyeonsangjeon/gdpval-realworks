# TASK — GDPVal Grading v2 Cost-Quality Decision (autonomous run to conclusion)

- **Repo:** `hyeonsangjeon/gdpval-realworks`
- **Recommended executor persona:** `@llm-systems-engineer`
- **Objective (one line):** Drive the v2 (tool-calling judge) cost-quality decision to a **final, data-backed recommendation**, executing all cheap/reversible work autonomously, and stopping only at the single gated production-run checkpoint.
- **Mental model:** The cost problem is an *architecture* problem (Round 3 proved caps aren't the lever). Exhaust the **quality-neutral** levers (prompt caching, server-side compaction, evidence-family batching) and **re-measure standard** *before* deciding whether the model must be downgraded to mini. The model-swap (B-prime) is a fallback gated by re-measurement, not the first move.

---

## HOW TO LAUNCH

Paste the Goal launcher (separate block in chat) into Copilot, or run:

> `@llm-systems-engineer` Execute `TASK_grading_v2_cost_decision.md` to completion. Follow its **Persistence Protocol** exactly. Do not stop, summarize-and-wait, or ask for confirmation until every **Completion Criterion** is checked or a **Hard-Stop Condition** is hit.

---

## PERSISTENCE PROTOCOL  *(this section exists specifically to stop you from halting or pivoting mid-run)*

1. **Run to completion in one continuous session.** Do NOT pause to ask for confirmation, do NOT stop to summarize and wait for input, and do NOT request approval between steps. **Every step in this document is pre-authorized by the owner.**
2. **Checkpoint, do not pause.** After each step, append a status line to `PROGRESS.md` (`step | result | artifacts | next_step`) and **immediately begin the next step**. Writing a checkpoint is not a stopping point.
3. **No mid-run redesign.** Follow the plan as written. If a step is wrong, infeasible, or blocked, **do NOT stop to ask which direction to take** — append an entry to `DEVIATIONS.md` (`step | what_failed | why | what_you_did_instead`) and proceed with the **nearest viable action**. Changing approach silently and continuing is correct; stopping to re-plan is not.
4. **Execute the fork, never ask it.** The decision branch in **Step 4** is *computed* from measured numbers and *executed* by you. Do not present the fork to the user as a question.
5. **A step is "done" only when its artifact exists AND its acceptance check passes.** If the check fails, fix/re-run rather than reporting partial progress.
6. **Bounded retries.** On a blocking error (auth, API, parse), retry up to 3× with reasonable backoff/adjustment, logging each attempt to `PROGRESS.md`. Only then treat it as a Hard-Stop.

### HARD-STOP CONDITIONS — the *only* reasons to stop and return control
- (a) You reach the **gated production run** (the FINAL step). ← expected stop.
- (b) Credential / auth failure you cannot resolve in ≤3 attempts (e.g. Entra ID / `DefaultAzureCredential`, HF token).
- (c) A **destructive or irreversible-cost** action not explicitly authorized in this document (e.g. anything that deletes data, or any run over the **$80** autonomous ceiling that this doc has not pre-cleared as cheap).
- (d) Retries exhausted on a blocking error.

On any Hard-Stop: write a **STOP report** to the top of `PROGRESS.md` stating exactly what is blocking and the one decision/credential you need. Then stop.

---

## COST AUTHORIZATION (so you don't stop to ask about spend)
- **Pre-authorized (run without asking):** all N=10 smokes, the N=20–30 paired stratified smokes, and 3-task probes. These are cheap (~$8–25 each at current per-task rates) and are normal pipeline runs.
- **NOT authorized (gated, human go required):** the **full 220-task production grade**. You prepare the exact command and STOP. Never launch it autonomously.

---

## STEP 0 — Baseline cost truth (is `$168` even real?)
**Action:**
- Pull `usage.prompt_tokens_details.cached_tokens` and total `prompt_tokens` from the existing exp003 N=10 **standard** run artifacts on HF (`self_report.json`). If cached_tokens was not logged, run a **3-task probe** on `default_v2.yaml` (standard, effort=medium) with cached_tokens logging enabled.
- Compute cache **hit ratio** per task and the **effective** (cache-discounted) input cost using the deployment's cached-input price. Recompute the **220-task extrapolation on effective tokens**.
- Confirm whether the original `$168` priced raw input tokens at full rate (likely an overestimate) or effective tokens.

**Artifact:** `baseline_cost_truth.md` — cache hit ratio, raw vs effective per-task cost, corrected 220 extrapolation, and a one-line verdict ("$168 ≈ real" / "$168 overstated → effective ≈ $X").

**Acceptance:** cached_tokens values present for all probe/sample tasks AND effective 220 extrapolation computed.

---

## STEP 1 — Quality-neutral cost levers (the ½–1 day engineering)
Implement on a branch `feat/grading-v2-cost-levers`. These change billing/token-flow, **not** scores.

**1a — Prompt caching (provably output-identical):**
- Restructure judge requests so the **stable prefix is identical and frontmost**: system prompt + tool schemas + rubric scaffold + JSON envelope schema first; task-specific evidence and tool results only at the **end**. Tool definitions must be byte-identical in content **and ordering** across calls.
- Set and log a stable `prompt_cache_key`.
- **Verify on a 3-task probe that `cached_tokens > 0`** (a persistent zero means the prefix is unstable — fix it).

**1b — Server-side compaction (Azure Responses API):**
- First confirm the feature is enabled for this resource/region/model (it is documented on Azure Responses API as of recently, but was absent earlier in 2026 — verify, don't assume).
- Enable via `context_management` + `compact_threshold`. **Tune the threshold high enough that light/medium tasks never trigger compaction (so they stay fully cacheable); only long loops (≈ the 49-call monster `83d10b06`) should compact.**
- Verify on `83d10b06` that input tokens drop materially vs the Round-2 baseline (2.12M).
- Note: `store=true` (default) means the service holds state, but that is **not** auto-compaction — compaction must be explicitly enabled.

**1c — Evidence-family batching (the biggest architecture lever):**
- Refactor the judge so it **reads each deliverable once into a cached evidence bundle**, then scores **multiple rubric items per evidence family** instead of re-reading per item:
  - formatting/style items → one `render_to_image` + one format-analysis turn → multiple item scores.
  - content/accuracy items → one `read_content` evidence bundle → multiple item scores.
- Goal: cut per-task tool-call count (target: heavy-task calls down from ~49 toward ~15–20).

**1d — Strict output envelope (kills Round-3 parse failures):**
- Final scoring turn uses **strict structured output** with **short field names** and **`parallel_tool_calls=false`**. Evidence-gathering turns may use parallel tool calls.
- **Restore `max_output_tokens` to ≥ 2400** so the final JSON envelope never truncates. (Round 3's 1500 truncation was the root parse-failure cause — do not re-introduce it.)

**Artifact:** committed branch + `levers_probe.md` — a 3-task probe showing: caching active (cached_tokens>0), compaction firing only on heavy tasks, reduced call count, **zero parse failures**.

**Acceptance:** all four sub-checks pass on the probe.

---

## STEP 2 — Re-measure STANDARD on N=10
**Action:** Run exp003 **N=10** with `default_v2.yaml` (gpt-5.4 **standard**, effort=medium) on the rebuilt pipeline.
**Capture:** `avg_pct`, `critical_item_pass_rate`, `judge_error_rate`, input/output tokens, **cached_tokens ratio**, per-task cost, and **effective (cache-discounted) 220 extrapolation**.
**Artifact:** `remeasure_standard_n10.md` + the raw `self_report.json`.
**Acceptance:** `judge_error_rate < 2%` AND all metrics captured AND effective 220 extrapolation computed. (If judge_error ≥ 2%, treat as a Step-1 regression: log to DEVIATIONS.md, fix, re-run — do not proceed to the fork on bad data.)

---

## STEP 3 — Paired quality validation (the "+5pp real?" question)
**Action:** On the **same 10 tasks**, compute **per-task paired deltas** `v2 − v1_hybrid` and `v2 − v1_mini` for both `avg_pct` and `critical_item_pass`. (v1 baselines: hybrid 49.25 / 0.421, mini 51.47 / 0.518; v2 default measured 56.66 / 0.4091.)
- Run a **sign test** and **Wilcoxon signed-rank** on the deltas; report **direction consistency** (e.g. "8/10 tasks up") and a **bootstrap CI** on the mean delta.
**Artifact:** `paired_quality_v1_v2.md` — delta table, test statistics, CI, and a verdict: `lift_directionally_significant` / `inconclusive`. Also explicitly flag whether `critical_item_pass` is **non-inferior** to v1 (it was *not* higher in Round 2 — watch this).
**Acceptance:** per-task deltas + test stats + CI + critical_item verdict present.

---

## STEP 4 — DECISION FORK  *(compute and execute — do NOT ask)*
Inputs: `effective_220_cost` (Step 2), `judge_error` (Step 2), `quality_verdict` + `critical_item_noninferior` (Step 3).

```
IF effective_220_cost <= 80 AND judge_error < 2% AND (lift_directionally_significant OR critical_item_noninferior):
    DECISION = "Standard v2 is the default. Proceed to gated production run."   # = the owner's option A, on fixed architecture
    -> go to FINAL

ELIF effective_220_cost <= 80 AND quality_verdict == inconclusive:
    # affordable but quality signal weak: expand validation ONCE (cheap), then re-enter the fork
    run paired stratified N=30 (modality x rubric-size, MUST include >=1 monster task) on STANDARD
    recompute Step 3 stats
    IF now lift_directionally_significant OR critical_item_noninferior: DECISION = "Standard v2 default" -> FINAL
    ELSE: HARD-STOP -> ask owner: standard is affordable but uplift unproven at N=30; confirm whether to (i) ship v2-standard anyway or (ii) keep v1.

ELSE:   # effective_220_cost > 80
    -> go to STEP 5 (B-prime mini smoke)
```
**Artifact:** `DECISION.md` — the computed branch, the exact numbers that drove it, and the recommendation.

---

## STEP 5 — B-prime: mini/medium paired smoke  *(only if Step 4 routed here)*
**Action:** Run a **paired stratified smoke, N=20–30**, stratified by **modality × rubric-size**, **MUST include ≥1 monster task (`83d10b06`)**, on **gpt-5.4-mini, effort=medium** (NOT low — do not weaken the model and reasoning simultaneously on the first test), same rebuilt pipeline.
**Capture vs STANDARD on the same tasks:**
- **score agreement** (correlation + mean absolute diff on avg_pct),
- **critical_item_pass non-inferiority**,
- `judge_error`,
- **actual token/cost and per-task call count** (watch for turn-count blowup — a weak orchestrator can cost *more* via extra retries; this is the real risk, not raw $/token),
- effective 220 extrapolation.

**Verdict rule:**
```
PASS  if  mean|mini-standard| avg_pct <= ~2pp
      AND critical_item_pass non-inferior
      AND judge_error < 2%
      AND no heavy-cluster quality collapse
      AND effective_220_cost <= 80
FAIL  otherwise
```
- **PASS →** DECISION = "mini-default + standard-fallback hybrid" → go to Step 6.
- **FAIL →** DECISION = "mini insufficient" → HARD-STOP and report to owner the *specific* failure (cost / quality / heavy-cluster) plus the two remaining options: accept standard at $X, or pursue mid-term batch/refactor.
- **Do NOT test mini/low in this run.** That is a separate follow-up, only after mini/medium passes.

**Artifact:** update `DECISION.md` with the agreement table, cost, and verdict.

---

## STEP 6 — Hybrid fallback spec  *(only if Step 5 PASS)*
**Action:** Write the **deterministic, rule-based (NOT LLM)** routing rules. Route a task to **standard** if ANY of:
`rubric_items > THRESHOLD`, audio/video criterion present, high expected multimodal hops, prior tool failure, task-level call-count over THRESHOLD, or final-JSON parse error. Otherwise **mini**.
Include the **shadow-audit plan**: on production, run a **10–15% stratified shadow sample** on *both* mini and standard and monitor **drift on `critical_item_pass`** (not just avg_pct).
**Artifact:** `hybrid_routing_spec.md`.

---

## FINAL — Gated production handoff  *(the one expected human checkpoint)*
**Action:** Produce `FINAL_RECOMMENDATION.md` containing:
- baseline cost truth (Step 0),
- before/after cost from the architecture levers (Step 1–2),
- the quality verdict (Step 3),
- the decision branch taken and why (Step 4 / 5),
- the **exact command + config** to launch the full 220-task production grade.

**Then STOP.** Do **not** execute the full 220-task run (gated, irreversible cost). Present `FINAL_RECOMMENDATION.md` and the ready-to-run command, and wait for explicit owner go.

---

## COMPLETION CRITERIA  *(check ALL before considering the Goal complete)*
- [ ] `baseline_cost_truth.md`
- [ ] `levers_probe.md` (caching on, compaction heavy-only, calls reduced, 0 parse failures) + branch committed
- [ ] `remeasure_standard_n10.md` + raw `self_report.json` (judge_error < 2%)
- [ ] `paired_quality_v1_v2.md` (deltas + sign/Wilcoxon + bootstrap CI + critical_item verdict)
- [ ] `DECISION.md` (branch computed + numbers + recommendation)
- [ ] `hybrid_routing_spec.md` *(only if Step 5 PASS)*
- [ ] `FINAL_RECOMMENDATION.md` + exact production command, **stopped at the gate**
- [ ] `PROGRESS.md` (per-step checkpoints) and `DEVIATIONS.md` (any deviations) maintained throughout

The Goal is complete only when `FINAL_RECOMMENDATION.md` exists with a clear branch decision **or** a Hard-Stop report explains exactly what is blocking.
