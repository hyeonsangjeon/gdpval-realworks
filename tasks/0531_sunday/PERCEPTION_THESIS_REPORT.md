# PERCEPTION & THESIS REPORT (rev2)

## 한 줄 결론

가설(V1↔V5): **REJECTED (weak)** / gold: **hand-grade 필요·대기** /
perception wiring: **완료 (코드+단위테스트 5/5 PASS)** / thesis(gold 기준):
**BLOCKED (gold + 라이브 Azure 인증 둘 다 막힘)** / v2 flip 근거:
**보류 (현재 데이터로는 perception이 헤드라인 후퇴를 고칠 수 없음이 강한 사전 신호)**.

요약: wiring은 끝났고 runtime instrumentation으로 증명까지 됐지만, **헤드라인
v2-mini 문제(critical 후퇴 + standard 대비 leniency)는 거의 전부
perception이 만질 수 없는 영역(formatting/text)에서 나온다.** 따라서 wiring을
켠다고 v2 채택 근거가 자동으로 서지 않는다. 진짜 thesis(perception이 visual/audio
criterion을 더 정확히 채점하는가)는 gold 없이는 못 푼다.

## PHASE 0 — 후퇴·fail→pass의 modality 분해

### (a) Critical-tier 후퇴 — `phase0_critical_modality.md`
- 10개 공유 task 중 v2-mini가 critical(|max|≥4)에서 v1-mini보다 떨어진 item: **3개**
- modality 분포: **formatting 3 / visual 0 / audio 0 / text 0**
- **caveat:** formatting은 `inspect_formatting` 도구로 라우팅됨 — vision/audio
  perception sub-judge **밖**의 경로. 즉 wiring이 이 후퇴를 *기계적으로* 고칠 수 없다.
- 가설 판정: **SUPPORTED (weak)** — 후퇴는 비-text(modality)에 집중되어 text judge
  modality 맹점 가능성과 일관, 그러나 그 modality(formatting)는 perception이 다루지 않음.

### (b) Mini-vs-standard leniency flip — `phase0b_flip_decomp.md`
- 10개 공유 task에서 mini가 standard보다 후한 flip 총 **38**개
- 유형: `partial→pass` 21, `fail→pass` 9, `fail→partial` 8
- modality 분포: **text 32 / formatting 3 / visual 3 / audio 0**
- **가설 판정: REJECTED** — leniency의 84%(32/38)는 순수 text criterion.
  Perception wiring과 무관하다. 별도 원인(judge strictness drift, reasoning effort,
  rubric 해석 차이) 조사가 필요하나 이 작업의 범위가 아님.

→ Phase 0 종합: perception wiring으로 v2-mini의 헤드라인 후퇴(critical, leniency)를
**고칠 가능성은 낮음**. perception은 visual/audio item 정확도 자체에 한정해서
측정해야 함(=Phase 4의 진짜 질문).

## PHASE 1 — Gold 확립 — `phase1_gold.md`, `gold_candidates.md`

- GDPVal `rubric_json`에 per-item expected verdict 라벨 **없음**. `deliverable_files`도
  모든 220 row에서 비어 있음.
- 따라서 thesis 판정용 gold는 owner hand-grade로만 가능.
- `gold_candidates.md`: **19개** rubric item 선정 (visual 12 + audio 1 + formatting 6;
  10개 공유 task 범위).
- **STOP — owner-go 필요.** owner가 `gold_verdicts.json`을 줄 때까지 Phase 4 진행 불가.

## PHASE 2 — Wiring + instrumentation — `phase2_wiring.md`

브랜치 `feat/wire-perception` (local only, push 금지). 변경 2 파일:

- `batch-runner/core/grader.py`: `_build_tool_judge`에서
  `judge.perception.{visual,audio}` 읽어 `VisionPerception`/`AudioPerception` 생성·주입.
  `ItemGrade`에 instrumentation 3종(`routing_modality`, `perception_called`, `tools_used`)
  추가. `grade_task`가 task 경계마다 `reset_perception()` 호출.
- `batch-runner/core/tool_calling_judge.py`: `ToolCallingResult`에 `tools_used`/
  `perception_called` 추가, 디스패치 루프가 호출명 누적, `_finalize`가 모든 반환
  경로(judge_error 포함)에 instrumentation 스탬프, `reset_perception()` 메서드 추가.

**Runtime 증명 (rule 9, config-only 금지):** `tests/test_perception_wiring.py` 5종
모두 PASS. config 선언으로 본 게 아니라 실제로 `vision_judge`를 디스패치한 결과로
`perception_called=True`, `tools_used=["vision_judge"]`가 찍히는지 확인.

**Dead config (수정 안 함, 기록만):**
- `grades_per_task: 3` — 여전히 unwired
- `compaction` — array-shape 미검증으로 disabled
- per-item `model_tier` 계측 — 의도적으로 미추가 (run-level이면 충분, 추가하면 redundant)

## PHASE 3 — Perception 발화 확인 — `phase3_smoke.md`

**ACCEPTANCE: BLOCKED (라이브 검증 불가).**

`scripts/phase2_perception_probe.py` 실행 시 두 인증 경로 모두 실패:

1. OIDC: `AADSTS7000215: Invalid client secret` — `.env`의 service-principal secret 만료/회전.
2. Key fallback: `403 AuthenticationTypeDisabled` — Azure 리소스에서 key-based auth 비활성.

constitution rule 8 ("No `AZURE_OPENAI_API_KEY` dependency (OIDC only)")과 rule 12
("결과를 자기 유리하게 재해석 금지")에 따라, 라이브 발화율은 **미검증**으로 기록.
간접 증거는 phase2 단위 테스트뿐 — 모델이 실제 운영에서 `vision_judge`를 얼마나
자주 디스패치하는지는 owner가 OIDC 갱신 후 probe 재실행해야 함.

부차적으로 발견·수정: probe의 `.env` 로더가 inline Korean comment를 값에 포함시켜
api-key 헤더에 non-ASCII가 섞이는 버그. 로더에 ` #` 이후 잘라내는 처리 추가
(grader 코드와 무관).

## PHASE 4 — Thesis 판정 — `phase4_thesis_verdict.md`

**BLOCKED.** Phase 1 (gold 없음) + Phase 3 (라이브 perception-on 결과 없음) 두
선행조건이 모두 미충족. self-graded 비교(=avg_pct, judge-vs-judge agreement)는
rev2 spec이 명시적으로 금지한 실패 모드라 만들지 않음.

Unblock 절차는 phase4_thesis_verdict.md의 (a)~(f) 참조.

**현재 사전 신호 (verdict 아님):** Phase 0 결과로 보면 perception은 v2-mini의
headline 문제(critical 후퇴 / standard 대비 leniency)를 거의 못 고친다. visual/audio
item 자체의 정확도 향상은 별개 질문이고 — gold가 도착하면 그것만이라도 측정 가능.

## Dead config 기록 (수정 안 함)

| 항목 | 상태 |
|---|---|
| `judge.perception.{visual,audio}` | **wired (이 작업)** — instrumentation으로 증명 |
| `grades_per_task: 3` | unwired — grader가 task당 1회만 채점 |
| `context_management.auto_compact` (array-shape) | disabled — Azure 현재 API rev가 dict shape를 거부, array shape는 미검증 |
| per-item `model_tier` 계측 | 의도적 미추가 |

## Owner 결정 필요

1. **gold hand-grade (Phase 1):** `gold_candidates.md`의 19개 item 채점 →
   `gold_verdicts.json`. 이게 와야 Phase 4가 풀린다.
2. **Azure 인증 복구 (Phase 3):** `.env`의 OIDC SP secret 갱신 또는 임시 key-auth
   재허용. 라이브 perception 발화율 검증의 전제.
3. **dead config 처리 방향:** `grades_per_task`/compaction을 wire할 가치가 있나, 아니면
   config에서 제거할 것인가 — 별도 작업 트랙으로 결정 필요.
4. **v2 채택/철회 결정:** rev2 spec은 "perception이 v1보다 못하거나 차이 없을 가능성을
   진지하게 열어두라"고 명시. Phase 0의 modality 분해 결과는 그 가능성을 *키운다*.
   gold가 도착해도 visual/audio item에서만 작은 우위가 있는 결과가 나올 가능성이
   현 시점에서 가장 그럴듯한 사전 — 그 경우 v2 flip 정당성은 *약함*으로 봐야 함.
5. **push 승인:** 이 작업의 commit은 local `feat/wire-perception`에만 있음.
   main push / 머지는 owner-go 필요 (constitution rule 13).
