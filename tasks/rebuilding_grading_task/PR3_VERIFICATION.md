# PR3_VERIFICATION

> READ-ONLY 진단. 코드 + 기존 `data/grades/*.json` 만으로 재계산. 어떤 grade run/네트워크/수정/commit 없음.
> 모든 숫자는 파일에서 직접 재계산했고 방법을 명시함. 저장 위치: `tasks/rebuilding_grading_task/PR3_VERIFICATION.md`
> (repo에 `outputs/` 디렉터리가 없어 PR3 산출물 형제 위치에 저장).

## 한 줄 결론

FINAL_RECOMMENDATION은 **부분 정합**. v2 개별 숫자(0.500/0.433/57.20/59.48/$55)는 raw에서 재현되지만,
**헤드라인 표가 현재 default(v1-mini)와의 비교에서 집계 방식과 scope를 섞어 실제 critical-pass 후퇴(−9~−15pp)를 −8.3pp로 축소**하고,
**v2 채택의 1순위 명분(perception sub-judge 아키텍처)이 코드에 wiring되지 않아 측정된 적이 없다.**
go 전 차단 항목: **3개** (V1 critical 후퇴 / V5 아키텍처 미측정 / V1·V7 헤드라인 숫자 정합).

## 검증 결과

| 항목 | 판정 | 핵심 증거 | 결론 영향 |
|---|---|---|---|
| V1 critical_pass 모순 | **FAIL** | 0.500 = item-pooled(11/22), 0.433 = task-macro — 둘 다 v2-mini 동일 10태스크의 값, 집계만 다름. 같은 10태스크·같은 방식 v2-mini vs v1-mini = pooled 0.500 vs **0.591**(−9.1pp), macro 0.433 vs **0.583**(−15.0pp). 헤드라인은 v2-mini-pooled(0.500)를 v1-mini-macro(0.583)에 붙이고 "(220-mean)"으로 오기 | **flip-blocker.** 현재 default 대비 가장 결정적 지표가 후퇴하는데 헤드라인이 이를 가림 |
| V2 batching skip | **PASS**(주장 사실) / $80 도달 **UNVERIFIABLE** | judge는 rubric item마다 re-read 확정([tool_calling_judge.py:181](batch-runner/core/tool_calling_judge.py:181), 매 item `messages` 새로 시작 :197, `read_deliverable` per-item :300; [grader.py:1149](batch-runner/core/grader.py:1149) per-item loop). monster `83d10b06` = 38 item / 36 call / **2,945,554 input tok = standard 전체 입력의 47%**; 상위 6태스크=89%; 입력이 raw 비용의 85% | $173은 batching 미적용 수치 확정. batching이 최대 비용 lever인 것 맞음. $80까지 내려올지는 **미측정** — 낙관적 추정으로도 ~$95–120, $80은 미입증 |
| V3 compaction | **PASS**(스키마 문제로 확정) + caveat | 코드가 명시: dict → Azure HTTP 400 "expected an array of objects"; array shape `[{"type":"auto_compact","threshold":N}]`는 opt-in으로 존재([tool_calling_judge.py:229-239](batch-runner/core/tool_calling_judge.py:229)), default `compact_threshold=None`(:169) | **기능 미지원 아님 = 호출 스키마 오류.** 단 array fix는 live 검증 안 됨, 그리고 `_build_tool_calling_judge`가 config→compact_threshold를 안 넘김(grader.py:1128) → 현재 production에서 켤 수도 없음. 비용 최적화라 헤드라인 영향 작음 |
| V4 mini inflate | **UNVERIFIABLE**(N=10, gold 없음; lean: 입증된 lift 아님) | +2.28(59.48 vs 57.20)은 **3태스크 집중**(a328feea +12.08, c44e9b62 +4.88, f84ea6ac +4.40; 나머지 7개 ±2.7, 1개 −2.48). spread는 mini sd=28.36 ≥ standard 26.62 → **압축 없음**. evidence는 mini 100% non-empty + 실제 read_deliverable 인용("Confidence level,90%" 등) | +2.28을 quality 향상으로 단정 불가(CI 하한 +0.19는 a328feea 1개에 의존). 단 mini judge_pass_rate 0.449 > 0.391, coverage 0.476 > 0.421 = **약한 leniency 신호** → shadow audit 정당 |
| V5 architecture 측정 | **FAIL**(asserted, not demonstrated) | perception sub-judge가 **wiring 안 됨**: [grader.py:1128](batch-runner/core/grader.py:1128)의 `_build_tool_calling_judge`가 `vision_perception`/`audio_perception` 인자 없이 생성 → 항상 None → `vision_judge`/`audio_judge` tool 노출 안 됨([tool_calling_judge.py:421-423](batch-runner/core/tool_calling_judge.py:421)). [step8_grade.py:130](batch-runner/step8_grade.py:130)은 perception block을 **검증만** 함. 10태스크에 visual 12 + audio 1 + formatting 22 criterion(critical 중 visual 5 + formatting 6) 존재하나 전부 text judge가 채점 | **v2 1순위 명분 붕괴.** "perception sub-judge로 format/audio/visual을 제대로 채점"은 측정된 적 없음. modality-criterion별 v1 vs v2 비교도 어디에도 없음(분석은 task-pct 뿐) |
| V6 비용 외삽 | **PASS**(산수) + 취약 | monster `83d10b06` N=10에 **포함**. $55 = $2.475×22 확정. 단 비용 tail **상위 3태스크 = 76%**(43dc9778 27.3% / 83d10b06 26.2% / c44e9b62 22.5%) → 선형 ×22가 high-item 밀도에 매우 민감, 변동폭 ~$40–85+, $80 초과 가능 | owner-go gate가 "220에서 variance 더 큼"으로 이미 차단 → 적절. 단 baseline 오류(아래) |
| V7 정합성/완료 | **PARTIAL** | 헤드라인↔본문↔raw 불일치 다수(아래 표). 완료상태: PROGRESS는 FINAL+owner-go gate로 깔끔히 끝남, 미완 "16/23" todo 없음(tight smoke 실행됨). 단 DEVIATIONS가 **두 개의 silent gap 미기록**: (1) perception 미배선, (2) `grades_per_task:3`·compaction-from-config 미구현 | 결론 자체는 "BLOCKED ON OWNER GO" 맞음. 그러나 owner가 보는 헤드라인 숫자가 정합하지 않아 informed go/no-go 불가 |

## 숫자 불일치 표 (헤드라인 vs 본문 vs raw 재계산)

같은 10 shared task: `17111c03 27e8912c 43dc9778 7b08cd4d 7d7fc9a7 83d10b06 a328feea c44e9b62 ee09d943 f84ea6ac`.
critical = `abs(max_score)>=4`. pooled = Σpass/Σcrit(step8 `summary.wow`). macro = per-task 평균(paired script).

| metric | FINAL 헤드라인 | FINAL 본문 | raw 재계산 | 어느 게 맞나 |
|---|---|---|---|---|
| v2-mini critical | **0.500** | 0.433 (line 51, Risks) | pooled **0.5000** (11/22) / macro **0.4333** | 둘 다 맞음(같은 run, 다른 집계). 헤드라인=pooled, 본문=macro — 한 문서가 한 run을 두 방식으로 적어 모순처럼 보임 |
| v1-mini critical(헤드라인) | **0.583 "(220-mean)"** | 0.583 (line 51) | 10태스크 macro **0.5833** / pooled **0.5909** | 0.583은 **10태스크 macro**. "(220-mean)" = **오기** |
| v1-mini critical(진짜 220-mean) | (표시 안 함) | — | **0.5177**(legacy) / **0.5963**(v2sm) | 둘 다 헤드라인에 없음. 0.583과 불일치 |
| v2-mini vs v1-mini critical(같은 10·같은 방식) | 0.500 vs 0.583 → −8.3pp | "worse than v1-mini, 15pp gap" (PROGRESS) | pooled −9.1pp / macro **−15.0pp** | 본문/PROGRESS의 −15pp가 정직. 헤드라인 −8.3pp는 방식 혼합 산물 |
| v1-mini avg_pct | **51.47 "(220-mean)"** | "+1.84 inconclusive, CI crosses 0" (line 49) | 같은 10태스크 **57.91** / 220-mean 51.47 | 51.47은 220-mean. v2-mini 10태스크(59.48)와 나란히 둠 = **본문이 인정한 sample bias 재발** |
| v2-mini vs v1-mini avg(같은 10) | 암시 +8 (59.48 vs 51.47) | +1.84 (inconclusive) | **+1.57** (59.48 vs 57.91) | 본문이 대략 맞음. 헤드라인은 편향 |
| v1-hybrid critical | — | "non-inferior to v1-hybrid (**0.433**)" (line 51) | macro **0.3417** | 본문 오류 — 0.433은 v2-standard 값(paired_mini 문서가 컬럼을 relabel한 흔적). v1-hybrid는 0.342 |
| v2-mini vs v2-standard critical | 0.500 = 0.500 | "0.500 (equal)" | 둘 다 pooled 0.500 / macro 0.433 | 사실이나 **비교 대상이 틀림** — 비교해야 할 건 v2-standard가 아니라 현재 default(v1-mini) |
| cost v1-mini | **~$18** | ~$18 | full-220 측정 **$8.67** / 같은10×22 **$13.7** | $18 **재현 불가**. 실측 ~$8.67. 진짜 배수 ~4–5× (3× 아님) |
| cost v2-mini | $55 | $55 | effective **$54.5** | 맞음 |
| judge_error_rate | mini 1.21% / std 0.24% / tight 3.38% | 동일 | wow 0.0121 / 0.0024 / 0.0338 | 맞음 |

## go 전에 해소해야 할 blocker (우선순위 순)

1. **critical_item_pass 후퇴(현재 default 대비) — 가장 결정적.** 같은 10태스크·같은 집계 기준 v2-mini는 v1-mini(=현재 default `default_gpt5pro.yaml`, gpt-5.4-mini)보다 critical-pass가 **pooled −9.1pp / macro −15.0pp** 낮다. v1-mini가 `27e8912c·7b08cd4d·83d10b06`에서 critical 통과하는데 v2-mini는 실패(역으로 v2-mini는 `ee09d943` 1개만 회복). 이건 측정 착시가 아니라 실제 후퇴다. → 더 넓은 task에서 재측정하거나, 후퇴를 명시적으로 수용하거나(근거 필요), hybrid router로 완화 확정 후에 flip. 헤드라인 0.500 단독으로 go 결정 금지.

2. **perception 아키텍처 미배선(미측정).** FINAL "Why v2 mini" #1·#3과 README가 내세우는 vision/audio sub-judge는 grader가 인스턴스화하지 않아 **모든 측정 run에서 비활성**이었다. visual/audio criterion도 text judge가 채점했다. → v2를 "아키텍처가 제품"으로 정당화하려면 (a) perception을 실제 wiring하고 modality-criterion 단위로 v1 대비 개선을 **측정**하거나, (b) 그 측정 전까지 perception을 채택 명분에서 빼라.

3. **헤드라인 숫자 정합성 복구(informed go의 전제).** 헤드라인 표를 같은 집계·같은 scope로 통일: v1-mini critical "(220-mean)" 오기 수정(실제 0.583은 10태스크 macro), v1-mini avg 51.47(220) vs v2-mini 59.48(10) 나란히 두는 sample bias 제거, v2-mini critical을 pooled/macro 중 하나로 일관 표기. 본문(line 49·51)은 비교적 정직하나 line 51의 "v1-hybrid (0.433)"는 0.342로 정정.

(비-blocker, 후속 정리) — standard $173은 1c batching 미적용치라 최적화 시 과대; v1-mini $18 baseline은 실측 $8.67로 정정 필요; `grades_per_task:3`·config-driven compaction은 미구현(dead config) 정리; PR2 task 207 legacy strip 잔존(FINAL이 이미 인지).

## 추가로 발견한 것 (위 항목 밖)

- **`grades_per_task: 3`이 구현 안 됨.** 코어/스텝 코드에 `grades_per_task` 참조 0건이고 calls/judge_item = **1.00**(=태스크당 1회 채점). 즉 "bootstrap CI per SPEC §7.5"의 per-task 분산은 측정된 적 없다. summary의 `ci_pct`는 태스크 간 분산일 뿐 3회 재채점이 아니다. perception·compaction과 함께 **"선언했으나 미배선된 config"** 패턴.
- **paired 문서 컬럼 relabel 함정.** `paired_mini_vs_standard.md`는 `paired_quality_v1_v2.py`를 그대로 재사용해 헤더가 "v2/v1h/v1m"인데 실제로는 v2=mini, v1h=**v2-standard**, v1m=v1-mini다. 이 때문에 "v1 hybrid mean crit 0.433"가 사실 v2-standard 값으로 FINAL 본문에 잘못 전이됐다(line 51).
- **paired script의 v1 vs v2 비대칭 집계.** `_crit_pass_rate`는 `model_did_right` 있으면 그걸, 없으면 `(verdict=='pass')==(max>=0)` fallback을 쓴다. v1 legacy JSON엔 `model_did_right`가 없어 fallback, v2엔 있어 sign-aware — 같은 표 안에서 두 정의가 섞인다(본 검증은 grader 규칙으로 **균일 재구성**해도 결론 동일함을 확인: v2-mini 0.500/0.433 vs v1-mini 0.591/0.583).
- **`default_v2_tight`는 caps만 죄어 품질 동반 하락**(avg 54.77, critical pooled 0.409, judge_error 3.38%). DECISION의 "cost-lever는 caps가 아니라 model"이라는 통찰은 데이터와 일치 — 단 그 통찰이 standard의 1c batching 미적용 비용을 면죄하지는 않는다.
- **monster item 수 표기 흔들림.** 문서들이 `83d10b06`을 "36 items"로 적지만 raw는 **38 items / 36 calls**(36은 call 수). `7d7fc9a7`도 "49-call"=49 calls지만 56 items. 결정 영향 없음.
- **현재 production default 확인.** [grade-run.yml:14](.github/workflows/grade-run.yml) `default: "default_gpt5pro.yaml"` = schema 1.0 text-extract, model **gpt-5.4-mini**. 즉 FINAL의 "v1 mini (current default)" 라벨은 정확하고, 따라서 V1의 후퇴는 "제안 default가 현재 default 대비 critical 후퇴"가 맞다.

---
### 부록 A — 같은 10태스크 재계산(증거)

| run | pooled (Σpass/Σcrit) | macro (per-task 평균) | critN | passN | avg_pct(10) |
|---|--:|--:|--:|--:|--:|
| v2_mini (default_v2_mini) | **0.5000** | **0.4333** | 22 | 11 | 59.48 |
| v2_standard (default_v2) | 0.5000 | 0.4333 | 22 | 11 | 57.20 |
| v2_tight (default_v2_tight) | 0.4091 | 0.3250 | 22 | 9 | 54.77 |
| **v1_mini (현재 default)** | **0.5909** | **0.5833** | 22 | 13 | 57.91 |
| v1_hybrid | 0.5000 | 0.3417 | 22 | 11 | 54.49 |

per-task critical(passN/critN): v1-mini가 `27e8912c`(1/2 vs 0/2)·`7b08cd4d`(1/1 vs 0/1)·`83d10b06`(1/1 vs 0/1)에서 우위, v2-mini는 `ee09d943`(1/1 vs 0/1)만 우위. 순차 결과 v1-mini 13 vs v2-mini 11 critical-pass.

### 부록 B — 비용 재계산(증거)

| | raw 10 | effective 10 (cache%) | ×22 effective |
|---|--:|--:|--:|
| v2_standard | $9.088 | $7.861 (31.6%) | **$173** |
| v2_mini | $3.105 | $2.475 (45.2%) | **$54.5** |
| v1_mini (같은10, mini가, no cache) | $0.623 | ≈$0.623 | ≈$13.7 |
| v1_mini (full-220 실측) | $8.67 | — | (측정치) |

mini 비용 tail: 상위 3태스크(43dc9778·83d10b06·c44e9b62) = 76%. standard 입력 tail: monster 1개 = 47%, 상위 6 = 89%.
