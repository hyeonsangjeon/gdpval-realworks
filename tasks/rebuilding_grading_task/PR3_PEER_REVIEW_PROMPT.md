# Peer Review Request — GDPVal Grading v2 Cost-Quality Decision

> 다른 모델(GPT Pro / Claude Opus 4.8)에게 한 줄 평가 요청용 프롬프트.
> 상황을 한 번에 이해할 수 있도록 self-contained로 작성됨.
> 답변에 형식 자유. 권장 결정 + 그 이유 + 우리가 놓친 게 있는지를 듣고 싶음.

---

## TASK (모델에게 줄 질문)

다음 상황을 읽고 **A/B/C/D/E 중 어느 옵션을 권장하는지 + 그 이유**를 한 문단으로 답해줘. 또한 **우리가 놓치고 있는 lever / 해석 / 위험**이 있다면 짚어줘. 길이 제한 없음.

---

## CONTEXT

### 프로젝트

- **GDPVal RealWorks**: 220개 real-world expert task에 대한 LLM benchmark + grading pipeline
- v1 grading: 채점기에게 deliverable 파일을 **plain text로 추출**한 다음 1500자로 잘라서 prompt에 박아줌. format/style 평가는 구조적으로 불가능 (text로 변환하는 순간 폰트/색/병합셀/차트 다 사라짐).
- 분석 결과 v1의 "Overall formatting and style" criterion 격차가 결국 **text 변환 artifact**임이 정량 확인됨 (formatting bucket이 hybrid-stricter pair의 60.3% 차지).

### v2 rebuild (PR1+PR2 완료)

- v1의 text-extract 경로 폐기
- **Tool-calling judge** (Azure OpenAI Responses API의 function calling): 채점기가 직접 `read_deliverable(op, path, scope)` tool로 파일을 열어봄. 6 ops: `inspect_structure / read_content / inspect_formatting / render_to_image / probe_audio / probe_video`.
- modality routing (visual/audio/formatting/text)에 따라 vision/audio sub-judge로 escalation
- sign-aware score math (PR1에서 fix)
- 단일 judge tier: **gpt-5.4 standard, reasoning_effort=medium**. SPEC §4.1 명시: "mini는 multi-step tool orchestration에 약함" 우려 때문에 standard 선택.

### 측정 데이터 (오늘 한 라운드씩)

**Round 1 — exp998 smoke (sample n=3)**
- avg_pct 84.62 / judge_error 1.19% / 220 외삽 $52
- task가 가벼워서 표본 작음. 다음 라운드 진행 근거.

**Round 2 — exp003 N=10 (`default_v2.yaml`)**
- avg_pct **56.66** (v1 hybrid 49.25 / v1 mini 51.47 대비 **+5-7pp**)
- critical_item_pass_rate 0.4091 (v1 hybrid 0.421와 유사)
- judge_error_rate **0.72%** (SPEC §7.4 ceiling 2% 안전)
- input/output tokens 4.95M / 293k (94% input-heavy)
- 220-task linear extrapolation **$168** (사전 자율 ceiling $80 초과)
- 무거운 task 1개 (`83d10b06`, rubric 36 items, 49 judge calls): input **2.12M tokens** 사용

**Round 3 — exp003 N=10 (`default_v2_tight.yaml`)**
- caps tighten 시도: `per_item_call_cap` 8→4, `max_iterations` 10→6, `max_output_tokens` 2400→1500
- 기대: $80-99/run
- 실제: **$193/run (+15%), judge_error 3.38% (ceiling 위반)**
- 원인:
  1. `max_output_tokens` 1500이 최종 JSON envelope 잘라서 parse 실패 → judge_error 폭증
  2. `per_item_call_cap` 4가 모델에게 `cap_exceeded` 응답 받게 했는데, 그 응답 자체가 input batch에 누적되어 모델이 재시도하면서 token이 더 늘어남
  3. `max_iterations` 6은 거의 영향 없음
- 결론: **input token cost는 (rubric_items_per_task × tokens_per_call)에 비례**. caps는 lever가 아님.

### 자율 게이트 평가 (round 3)

- 220 extrap ≤ $80 → ❌ ($193)
- avg_pct ≥ 51 → ✓
- judge_error < 2% → ❌
- → 2/3 fail, 자율 PROCEED revoked, STOP+ALERT.

### Quality 비교 (10-task sample)

|  | v1 hybrid | v1 mini | v2 default | v2 tight |
|---|--:|--:|--:|--:|
| avg_pct | 49.25 | 51.47 | **56.66** | 54.77 |
| critical_pass | 0.421 | 0.518 | 0.4091 | 0.4091 |
| judge_error | low | low | 0.72% | 3.38% |
| per-task cost | ~$0.10 (sweep) | ~$0.08 (sweep) | $0.77 | $0.88 |

### Architectural 가설 검증 결과

- **v2 tool-calling이 v1 text-extract보다 +5pp 정확함 — 측정으로 확정.**
- evidence가 fabrication 없이 read_deliverable 응답을 직접 인용함 (예: `'"kind": "docx"'`)
- 단, **standard 모델의 $/token 단가가 비용 dominant**. mini가 ~10× 저렴.

---

## OPTIONS

| | 액션 | est. full cost (220 tasks) | quality 추정 |
|---|---|--:|---|
| **A** | `default_v2`로 복귀하고 $168을 그대로 받아들임. exp003 full 1회 실행. | $168 | best (측정 avg 56.66) |
| **B** | v2 tool-calling 그대로 두고 **judge.model을 gpt-5.4 → gpt-5.4-mini, effort=low**로 변경. 같은 exp003 N=10 smoke로 검증 후 통과시 full. | $25-40 추정 | -3-5pp 추정 (avg 51-53), tool-use 신뢰도 미검증 |
| **C** | 미온적 tighten: `per_item_call_cap`=6, `max_output_tokens`=2400 복원, 나머지는 default_v2. | $130-150 추정 | ≈ default_v2 |
| **D** | $168 받아들이고 full 1회 — head-to-head v1 vs v2 데이터만 확보. cost 결정은 후속으로. | $168 | best |
| **E** | PR3 abort, v2-as-default 계획 폐기, v1 (default_gpt5pro.yaml) 유지. | $0 | v1 baseline (avg 49-51) |

---

## CURRENT RECOMMENDATION (검수받고 싶은 것)

내 추천은 **B**:
- v2의 +5pp quality lift를 검증으로 살림
- 진짜 cost lever ($/token)를 공격
- SPEC §4.1의 "mini tool-use 우려"는 standard에서 judge_error 0.72% 측정했으니 mini가 2-3배여도 천장 안일 가능성
- ~$3, ~60min smoke 1번으로 결정 가능

**불확실한 점**:
1. mini의 tool-orchestration 신뢰도가 실제로 얼마인지 모름 (SPEC 우려가 보수적인지 정확한지)
2. mini로 갈 때 quality drop이 -3-5pp일지 -10pp일지 모름
3. cost lever가 정말 모델 단가뿐인지, 아니면 prompt simplification / rubric batching 같은 architectural 옵션을 빠뜨렸는지

---

## 알고 싶은 것

1. A/B/C/D/E 중 **어느 게 합리적인 선택**? 이유?
2. **우리가 빠뜨린 cost lever**가 있나? (예: prompt compression, rubric batching, modality skipping aggressive화, 다른 모델 — gpt-5-nano? gpt-4.1?, sub-judge 비활성화 등)
3. B로 갈 경우 **mini의 tool-use 신뢰도를 검증할 추가 안전장치**? (예: judge_error retry, mini 실패 시 standard fallback 같은 hybrid 라우팅)
4. v2의 +5pp가 v1보다 정말 의미 있는 lift인지, 아니면 측정 noise 가능성? (N=10 sample이라 confidence 약함)
5. 다른 reasonable 접근: 예를 들어 **standard로 채점하되 sample N개만 (예: 50/220)** 하는 것? (cost cap이 첫째 목적이면)

답변 형식 자유. 한 옵션 강하게 권장해도 좋고, 새 옵션 제시해도 좋음.
