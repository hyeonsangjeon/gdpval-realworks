# PHASE 0 — critical-item modality (v2-mini vs v1-mini)

Shared tasks: 10
Critical = abs(max_score) >= 4

REGRESSED critical items (v1-mini RIGHT, v2-mini WRONG): 3
  modality breakdown: {'formatting': 3}
  perception (visual+audio+formatting): 3 | text: 0

RECOVERED critical items (v2-mini RIGHT, v1-mini WRONG): 1
  modality breakdown: {'formatting': 1}

## Regressed items detail

| task | modality | v2 verdict | v1 verdict | max | criterion |
|---|---|---|---|---|---|
| 27e8912c | formatting | partial | pass | 5 | Overall formatting and style of the deliverable |
| 7b08cd4d | formatting | partial | pass | 5 | Overall formatting and style of the deliverable |
| 83d10b06 | formatting | partial | pass | 5 | Overall formatting and style of the deliverable |

## Recovered items detail

| task | modality | v2 verdict | v1 verdict | max | criterion |
|---|---|---|---|---|---|
| ee09d943 | formatting | pass | partial | 5 | Overall formatting and style of the deliverable |

## Hypothesis verdict

SUPPORTED: 3/3 (100%) regressed critical items are visual/audio/formatting. The V1 critical regression is plausibly a symptom of unwired perception.

## CRITICAL CAVEAT (mechanical, must read before PHASE 3)

All 3 regressed critical items classify as **formatting** modality, which the
v2 router (`grader_routing.classify_criterion`) maps to `preferred_op=inspect_formatting`.
**`formatting` does NOT invoke a perception sub-judge.** Only `visual`
(-> `render_to_image` + `vision_judge`) and `audio` (-> `probe_audio` + `audio_judge`)
escalate to the vision/audio sub-judges wired in PHASE 1.

Consequence: wiring the vision/audio perception sub-judges will **not**
mechanically touch these 3 formatting regressions. They are a judge-strictness
difference (v2 says `partial`, v1 says `pass` on "Overall formatting and style"),
gradeable from `inspect_formatting` output the text judge already had access to.

So the PHASE 0 hypothesis is **SUPPORTED only in the weak sense**: the regression
is concentrated in non-text (modality-classified) criteria, NOT in raw content/text
criteria. But the specific failing modality (formatting) is not the one perception
wiring addresses. Expected effect of perception wiring on THIS 10-task critical_pass
regression: ~zero. PHASE 3 must test perception's accuracy on the **visual/audio**
criteria that exist in the set (PR3 inventory: 12 visual + 1 audio), none of which
were critical regressions.
