# MINI vs GPT-5.4 — 채점기 모델 결정

> 분석/결정 자료. **git 상태 변경 없음**(커밋/머지/푸시 없음). **새 대규모 Azure run 없음** — gold 20 기존 결과 + 220 mini 실측 비용 재사용.
> 데이터: `tasks/0607_sunday/vision_validation/grades.json`(gold 20, Arm A=5.4 메타 / `baseline_meta_mini`=mini 메타), 220 mini 실측(`tasks/0601_monday/full_regrade_220.md`), 단가(`scripts/analyze_grade_run.py`).

## 한 줄 결론

mini 메타 MAE **1.18** vs 5.4 메타 **0.85**(−0.324, −28%). **mini는 pdf·xlsx에서 신뢰 불가(MAE 1.4~1.5)이고 오차가 RANDOM(stdev 1.44, over 8/under 6)이라 사후 보정도 불가** — 단 docx만 체계적 후함(+0.69). 220 5.4 비용 추정 **$146/run(cached-eff), mini $29의 5.0배**(+$117/run). 결정론적 precheck는 **4.5%뿐**이라 "mini+precheck" 절감은 무의미. **권고: 판단(judgment) criterion만 5.4로 escalation 하는 하이브리드**(전부 5.4도, 전부 mini도 아님). **220 전체 5.4 재채점은 현 데이터로는 보류** — 단, "Overall style" 1개 criterion·gold 20 한계가 크므로 **text/value criterion에서 mini 신뢰도 측정(소규모)을 1건 추가**한 뒤 최종 확정.

---

## 1. 정확도 — mini vs 5.4 (gold 20 "Overall style")

### 전체
| | MAE | bias | n |
|---|---:|---:|---:|
| mini 메타-only | **1.176** | −0.06 | 17 |
| gpt-5.4 메타-only | **0.852** | +0.08 | 20 |

5.4가 owner gold에 **−0.324(−28%)** 더 가깝다. bias는 둘 다 ≈0(중립)이라 평균이 아니라 **개별 오차 산포**가 문제.

### modality별 — mini가 어디서 신뢰 가능/불가한가
| modality | n | mini MAE | mini bias | 5.4 MAE | 5.4 bias | mini 신뢰? |
|---|---:|---:|---:|---:|---:|---|
| pdf | 6 | **1.417** | −0.08 | 0.736 | +0.07 | **불가** |
| xlsx | 5 | **1.500** | −0.70 | 1.250 | −0.35 | **불가** |
| docx | 5 | 0.812 | **+0.69** | 0.850 | +0.75 | 부분(후함) |
| pptx | 4 | **0.375** | +0.12 | 0.531 | −0.22 | ok |

- **pdf·xlsx: mini 신뢰 불가**(MAE 1.4~1.5). 5.4는 pdf를 절반(0.74)으로 줄임. xlsx는 5.4도 1.25로 높음(둘 다 어려운 modality — 별도 이슈).
- **docx: mini가 체계적으로 +0.69 후함**(5개 중 3개가 정확히 +1.0 over). 5.4도 +0.75 후함이라 **이건 모델 문제라기보다 criterion/rubric 해석 문제** — 보정 가능 영역.
- **pptx: mini가 의외로 ok(0.375), 5.4보다 낮음**. 단 n=4 소표본 노이즈 가능. (렌더 검증에서 pptx는 5.4+렌더가 추가 게인이었음 → §3 라우팅 참고.)

### critical vs non-critical
- 220 재채점 기준 critical item(|max_score|≥4) = 3.9%, 그중 **95.3%가 judge 결정**(precheck로 안 끝남). "Overall style"(max 5)은 전부 critical. 즉 **critical item은 거의 다 모델 판단에 의존** → mini의 random 오차가 critical 점수에 직접 전파.
- gold 20은 전부 critical "Overall style"이라 critical/non-critical 내부 비교는 이 데이터로 불가(한계).

### 체계적 vs 랜덤 — 보정 가능성
- mini 오차 분포: **over(+) 8개 / under(−) 6개 / ~0 3개**, mean **−0.06**, stdev **1.44**.
- 부호가 양방향으로 흩어지고 평균이 0에 가까움 → **RANDOM**. under 최대 −3.0(`bbe0a93b`), over 최대 +2.5(`85d95ce5`). **상수 오프셋 보정 불가**(어디서 후하고 어디서 짠지 예측 안 됨).
- **유일한 예외: docx는 체계적 +0.69 후함** → docx만은 보정/프롬프트 조정 여지.
- 결론: **mini의 부정확은 "일관된 편향"이 아니라 "신뢰성 부재"** — owner가 말한 "mini는 점수 자체를 못 낸다"가 데이터로 확인됨.

### ⚠️ 한계 (단정 금지)
- **gold 20개, "Overall formatting and style" 단일 criterion**(routing=formatting)에 국한.
- text/value/존재-카운트 criterion에서 mini 신뢰도는 **이 데이터로 알 수 없음**. mini가 "숫자 일치/필드 존재" 같은 단순 item은 5.4와 동등할 수 있음(§3) — 측정 안 됨.
- modality n=4~6 소표본. pptx ok/docx 후함은 표본 노이즈일 수 있음.

## 2. 비용 — 220 5.4 추정 (mini 실측 기반)

**220 mini 실측**(`full_regrade_220.md`): 8,904 judge calls, input **130.09M** tok, output **5.52M** tok.
**단가**(`analyze_grade_run.py`, 권위 소스): gpt-5.4 **$1.25/$5.00** per M(in/out), mini **$0.25/$1.00**. cached input 50% 할인.

| | mini (실측) | gpt-5.4 (추정, 동일 call/token) | 배수 |
|---|---:|---:|---:|
| input 비용 | $32.52 | $162.62 | 5.0× |
| output 비용 | $5.52 | $27.62 | 5.0× |
| **RAW 합계** | **$38.05** ✓ | **$190.23** | **5.0×** |
| **cached-effective**(~54% input cached) | **$29.24** | **$146.20** | **5.0×** |

- mini RAW를 단가로 역산하면 정확히 **$38.05** — CODEX 실측과 일치(모델 검증됨).
- gpt-5.4는 input/output 단가가 mini의 **정확히 5배** → 비용도 5.0배. 토큰 규모가 같다고 가정(같은 프롬프트/툴 루프).
- **절대 증가: cached-effective +$117/run, RAW +$152/run**.
- **정확도 게인(−0.324 MAE) 대비 비용: $117 추가로 MAE 28% 감소** = run당 $117에 채점 신뢰성 확보.
- 참고: gold 20 2-arm 검증의 실제 5.4 호출은 ~50 calls(매우 작음) — gold 규모 검증은 5.4로도 저렴(<$1 수준). **비용 문제는 오직 220 전체 규모에서만 발생.**

> 주의: 5.4는 reasoning 토큰이 output에 포함돼 **output 토큰이 mini보다 더 늘 수 있음**(동일 가정은 보수적 하한). 실제 220 5.4는 $146보다 높을 가능성.

## 3. 하이브리드 가능성 — 전부 5.4 vs 선별 5.4

### 결정론적(precheck) item은 모델 무관 — 하지만 비중이 작다
220 재채점 5,455 item 중:
| 결정 방식 | 개수 | 비중 | 모델 영향 |
|---|---:|---:|---|
| precheck (결정론적) | 244 | **4.5%** | **없음**(mini=5.4 동일) |
| judge (모델 판단) | 5,211 | **95.5%** | **있음** |

→ **"mini 기본 + precheck만 신뢰" 전략은 4.5%만 절약** = 무의미. 95.5%가 judge라 모델 선택이 거의 모든 점수를 좌우.

### criterion-type 라우팅 — judgment item만 5.4
judge item을 routing modality로 분해:
| routing | judge item | 비중 | mini 신뢰도(gold 20 근거) |
|---|---:|---:|---|
| text | 4,122 | 76% | **미측정**(존재/값/카운트 — mini OK일 수 있음) |
| formatting | 228 | 4.2% | **불가**(Overall-style = 이 버킷, mini MAE 1.18) |
| visual | 159 | 2.9% | 미측정(렌더+5.4가 게인이었음) |
| audio | 45 | 0.8% | 대상 외(deliverable 미생성) |
| None(텍스트성) | 657 | 12% | 미측정 |

- **판단(judgment) 버킷 = formatting+visual+audio = 432 item = 7.9%**. mini가 확인된 약점(Overall-style)이 정확히 여기.
- **나머지 ~88%(text+None)는 "사실 확인형"** — mini 신뢰도 미측정이나, 단순 존재/값/카운트는 mini도 5.4와 동등할 개연성.

### trade-off 표 (라우팅 가정 — text는 mini 신뢰 *가정*, 미검증)
| 전략 | 5.4 비중(item) | 220 비용(eff) | 정확도(Overall-style) | 비고 |
|---|---:|---:|---|---|
| 전부 mini | 0% | **$29** | MAE 1.18 (신뢰 불가) | 현재 |
| 전부 5.4 | 100% | **$146** | MAE 0.85 | 5.0× 비용 |
| 하이브리드(판단 7.9%만 5.4) | ~8% | **≈$38~50**¹ | 판단 item↑, text는 mini 유지 | text mini 신뢰 *가정 필요* |

¹ 하이브리드 비용은 토큰 비중이 item 비중과 다를 수 있어(판단 item이 렌더/긴 컨텍스트로 토큰 무거움) 정밀 추정엔 토큰 단위 측정 필요. item 비중 기준 대략치.

- **하이브리드의 매력**: 비용을 mini 근처($38~50)로 유지하면서 mini의 확인된 약점(formatting/visual 판단)만 5.4로 교정.
- **하이브리드의 위험**: text(76%)에서 mini가 신뢰 가능하다는 **가정이 미검증**. 만약 text criterion에서도 mini가 random하면 하이브리드는 무너지고 전부 5.4가 필요.

## 4. 권고

### 모델 선택: **(b) 하이브리드** (조건부) — 단 1건 추가 측정 후 확정
1. **전부 mini는 탈락**: pdf/xlsx 신뢰 불가 + 오차 RANDOM(보정 불가). owner 관찰("mini는 점수를 못 낸다")이 데이터로 확인.
2. **전부 5.4는 과투자 가능성**: $146/run(5×). 단순 사실 확인 item(88%)까지 5.4로 돌릴 근거는 아직 없음.
3. **하이브리드(판단 criterion만 5.4) 우선 권고**: formatting/visual 7.9% item을 5.4로, 나머지는 mini. 비용 ≈$38~50으로 mini 근처 유지하며 확인된 약점 교정.

### 220 전체 5.4 재채점: **현 시점 보류**
- gold 20 "Overall style"만으로 220 전부 5.4($146×N runs)를 정당화하기엔 근거 부족.
- **먼저 할 일(저비용, 다음 작업):** text/value criterion에 대한 **mini vs 5.4 소규모 측정**(gold 또는 owner-라벨 20~30 item, text-routed criterion). 결과에 따라:
  - text에서도 mini random → **전부 5.4**로 전환(220 5.4 정당화).
  - text에서 mini OK → **하이브리드 확정**(판단 item만 5.4, 220 하이브리드 재채점).

### 일반화 한계 (명시)
- 본 결정의 정확도 근거는 **gold 20개·"Overall formatting and style" 단일 criterion·n=4~6 modality 소표본**.
- **검증된 것:** Overall-style(formatting 판단)에서 mini는 pdf/xlsx 신뢰 불가, 오차 random, 5.4가 −28% 개선.
- **검증 안 된 것:** text/value/존재 criterion의 mini 신뢰도(전체 item의 ~88%), critical vs non-critical 내부 차이, modality별 결론의 표본 안정성.
- 하이브리드를 "전부 5.4 없이" 확정하려면 **text-criterion mini 신뢰도 1건 측정이 필수 선행**.

### 다음 작업 순서(권고)
1. **text-criterion mini vs 5.4 소규모 측정**(저비용, gold/owner 라벨 재사용) → 하이브리드 vs 전부 5.4 갈림 확정.
2. 하이브리드 확정 시: **criterion-type 라우터**(formatting/visual→5.4, text/존재→mini) 구현 + 220 하이브리드 재채점 비용 토큰 단위 재추정.
3. (직교) xlsx는 mini·5.4 모두 MAE 높음 — 모델과 별개로 **rubric/렌더 범위** 이슈로 별도 트랙.

---

### 부록 — 산출물(미커밋) / 근거
- 정확도: `tasks/0607_sunday/vision_validation/grades.json` (gold 20, Arm A=5.4 메타, `baseline_meta_mini`=mini 메타).
- 비용 실측: `tasks/0601_monday/full_regrade_220.md`(8,904 calls / 130.09M in / 5.52M out / RAW $38.05 / cached $29.24).
- 단가: `scripts/analyze_grade_run.py` `PRICING_USD_PER_M_TOKENS`(gpt-5.4 $1.25/$5.00, mini $0.25/$1.00, cached 50%).
- 라우팅/precheck 분포: 220 재채점 `data/grades/exp003_...rubric_v2_tools_mini.json`(5,455 item, precheck 4.5% / judge 95.5%).

### 부록 — 제약 준수
git 상태 변경 없음(read-only). 새 대규모 Azure run 없음(기존 데이터 재사용). secret 미조작. 본 보고서·분석은 미커밋. gold 20/"Overall style" 한계 명시, 단정 회피.
