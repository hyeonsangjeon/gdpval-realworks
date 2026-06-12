# CODEX — 채점기 모델 결정: mini vs gpt-5.4 (비용/정확도, 220 미실행)

- **Repo:** `gdpval-realworks`, `main`
- **상황:** gold 20 "Overall style" 2-arm 검증에서 — mini 메타 MAE **1.176**, gpt-5.4 메타 **0.852**(−0.324), 렌더 효과는 ≈0(−0.004). 즉 정확도 게인의 핵심은 *모델*(mini→5.4)이지 렌더가 아니다. owner 관찰: **mini는 채점 자체가 신뢰할 만한 점수를 못 낸다**(평균 1.18/5 오차, under/over 비일관).
- **원래 질문 복귀:** 이 프로젝트는 "채점기를 mini로 갈까 5.4로 갈까"에서 시작했다. 이제 그 결정을 *데이터로* 내릴 시점. 단 220 전체를 5.4로 재채점하는 건 비싸므로, **먼저 비용/정확도/하이브리드 가능성을 분석해 "220을 5.4로 돌릴 가치가 있는지 + 전부 5.4여야 하는지 하이브리드면 되는지"를 결정**한다.
- **범위:** 분석/결정 자료만. **220 전체 5.4 재채점은 이 작업에서 실행하지 마라**(이 분석이 그걸 할지 말지를 정한다). gold 20 기존 결과 + 비용 데이터 재사용. 새 대규모 Azure run 없음.

## ⛔ GIT 행위 절대 금지 / 인증
- `git push`/`merge`/`commit`/`rebase`/`reset`/`revert`/`checkout <file>` 전부 금지. read-only git만. main 건드리지 마라.
- 산출은 파일로 쓰되 커밋 금지(owner 검토).
- 새 Azure 대규모 run 금지. 기존 gold 20 결과(`tasks/0607_sunday/vision_validation/grades.json`)·220 재채점 cost 통계 재사용. secret 조작 금지.

## 분석할 것

### 1. 정확도 — mini vs 5.4 (있는 데이터로)
- gold 20 "Overall style": mini 메타 vs 5.4 메타의 task별/modality별 MAE·bias·|delta| (검증 리포트 재집계).
- **mini가 *어디서* 신뢰 가능하고 어디서 불가한지** 분해:
  - modality별(pdf/docx/xlsx/pptx) mini MAE — mini가 그나마 맞는 modality가 있나, 전부 못 믿나.
  - critical vs non-critical에서 mini 오차 차이(critical에서 더 위험한가).
  - mini의 오차가 *체계적*(항상 후함/짜함)인지 *랜덤*인지 — 체계적이면 보정 가능, 랜덤이면 못 씀.
- **한계 명시:** 이건 gold 20개, "Overall style" 1개 criterion. 다른 criterion(text/visual 등)에서 mini 신뢰도는 이 데이터로 단정 불가 — 그 점 분명히.

### 2. 비용 — mini vs 5.4 (220 규모 추정)
- 220 mini 재채점 실측: 8,904 judge calls, input 130M tok, output 5.5M tok, raw $38.05 / cached $29.24 (기존 cost 통계에서).
- gpt-5.4 단가로 **220 전체 5.4 재채점 비용 추정** (같은 call/token 규모 가정, 5.4 input/output 단가 적용). raw + cached 둘 다.
- mini $29 vs 5.4 $? = **정확도 게인(−0.324 MAE) 대비 비용 증가 배수**.
- gold 20 2-arm 검증의 실제 5.4 호출 비용도 참고치로.

### 3. 하이브리드 가능성 (전부 5.4 vs 선별 5.4)
- **전부 5.4가 필요한가, 아니면 일부만?** 분석:
  - mini가 신뢰 가능한 영역(있다면)은 mini 두고, 불가 영역만 5.4 escalation 하는 게 가능한가.
  - 예: precheck로 끝나는 결정론적 item은 모델 무관 → mini도 5.4도 동일. judge가 필요한 item만 모델이 갈림.
  - "Overall style"·시각 criterion 같은 *판단* item만 5.4, 단순 존재/카운트 item은 mini — 이런 분리가 정확도 유지하며 비용 줄이나.
  - pptx는 5.4+렌더가 추가 게인이었으니, modality+criterion-type별 모델/렌더 라우팅 매트릭스 초안.
- 단순 "전부 5.4"의 비용·정확도 vs "하이브리드"의 비용·정확도 trade-off 표.

### 4. 권고
- 셋 중 권고: (a) 전부 5.4, (b) 하이브리드(mini 기본 + 판단 item 5.4), (c) 데이터 부족 → 추가 측정 필요.
- 220 전체 5.4 재채점을 *할지 말지* 권고 — 할 가치 있으면 다음 작업으로, gold 20으로 충분하면 생략.
- 이 결정이 gold 20 "Overall style"에 국한된 한계, 일반화하려면 무엇이 더 필요한지 명시.

## 출력 — `tasks/0607_sunday/mini_vs_54_decision.md` (커밋 금지)
```
# MINI vs GPT-5.4 — 채점기 모델 결정
## 한 줄 결론
mini 메타 MAE 1.18 vs 5.4 메타 0.85. mini는 [전부/일부] 신뢰 불가. 220 5.4 비용 추정 $[?] (mini $29의 [N]배). 권고: [전부 5.4 / 하이브리드 / 추가측정]. 220 5.4 재채점 [할 가치 있음/생략].
## 1. 정확도 (modality/critical별 mini 신뢰도, 체계적 vs 랜덤, 한계)
## 2. 비용 (220 5.4 추정, mini 대비 배수)
## 3. 하이브리드 (전부 5.4 vs 선별, 라우팅 매트릭스 초안, trade-off)
## 4. 권고 (모델 선택 + 220 5.4 할지 + 일반화 한계)
```

## 제약 재확인
- ⛔ git 상태 변경 전부 금지, read-only, 커밋 금지.
- 220 전체 5.4 재채점 실행 금지(이 분석이 할지 결정). 새 대규모 Azure run 없음.
- gold 20·기존 cost 데이터 재사용. secret 조작 금지.
- gold 20/"Overall style" 한계 명시, 단정 금지.
- 막히면 방향 틀지 말고 보고.
