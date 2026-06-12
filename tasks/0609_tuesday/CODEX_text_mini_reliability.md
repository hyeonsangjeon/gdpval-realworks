/Users/hsjeon/git/gdpval-realworks/tasks/0609_tuesday/CODEX_text_mini_reliability.md# CODEX — [벤치마크 분석] text criterion에서 mini vs 5.4 신뢰도

- **Repo:** `gdpval-realworks`, `main`
- **성격:** 이건 *production 모델 결정용이 아니다*(그건 전부 5.4로 이미 기움 — 예산 여유로 비용 제약 없음). 순수 **벤치마크 분석**: "mini의 신뢰 불가가 formatting(Overall style)에 국한인가, 아니면 text criterion(숫자/존재/값)에서도 그런가?"를 *알기 위해서*. 즉 mini가 *어디까지* 못 믿을 만한지의 지도를 그린다.
- **이미 아는 것:** gold 20 "Overall style"(formatting)에서 mini MAE 1.18, 오차 RANDOM, pdf/xlsx 신뢰 불가. **모르는 것:** text-routed criterion(전체 item의 ~76%)에서 mini 신뢰도. text는 객관적(사실 확인)이라 formatting과 다를 수 있음.
- **범위:** text criterion 소규모 mini vs 5.4 비교만. **220 전체 재채점 금지**(이건 분석이지 baseline 생성 아님). 기존 220 mini grade JSON 재사용 + text item 소규모 5.4 재채점(<$1 예상).

## ⛔ GIT / 인증
- `git push`/`merge`/`commit`/`rebase`/`reset`/`revert`/`checkout <file>` 전부 금지. read-only git만. main 건드리지 마라. 산출은 파일로 쓰되 커밋 금지.
- 소규모 text 비교만(20~40 item). 새 대규모 Azure run 금지. 로컬 `az login` + stale env unset(`.env` 불변), secret 조작 금지. 막히면 멈춰 보고.

## 분석

### 1. text item 표본 추출 (기존 220 mini JSON)
- `data/grades/exp003_...rubric_v2_tools_mini.json`에서 **routing_modality="text" + decided_by="judge"** item 중 20~40개 추출.
- 다양성 확보: 여러 task/modality/sector에 걸쳐, 가능하면 *객관적 유형* 위주 — 숫자 일치("X = 230,754"), 필드 존재("contains City and Country"), 값 확인("confidence level 90%") 같이 *정답이 파일에 명확히 있는* 것. (주관적 text는 판별이 어려우니 객관 위주.)
- 추출한 item 목록(task_id, criterion 요약, mini awarded/verdict)을 표로.

### 2. 같은 item을 5.4로 재채점 (소규모)
- 동일 프롬프트/툴로 그 text item만 gpt-5.4 채점(렌더 없음 — text는 렌더 무관). <$1 예상.
- mini와 동일 입력(같은 deliverable, 같은 criterion).

### 3. mini vs 5.4 비교 (owner gold 없이)
- **verdict 일치율:** pass/fail/partial이 몇 % 일치하나.
- **score 차이:** |mini_awarded - 5.4_awarded|의 평균/최대/분포.
- **불일치 item 판별:** 갈린 item을 *내용까지* 열어 어느 쪽이 맞는지 판단(text는 객관적이라 가능: "1040에 정말 그 값이 있나"는 파일 보면 정답이 있음). mini가 틀린 건지 5.4가 틀린 건지, 또는 criterion이 모호한 건지.
- **mini 오차 패턴:** text에서도 RANDOM인가(formatting처럼) 아니면 체계적인가, 아니면 거의 안 틀리나.

### 4. 해석 (벤치마크 관점)
- text에서 mini가 5.4와 거의 일치 → "mini의 신뢰 불가는 *판단형*(formatting/visual)에 국한, *사실 확인형*(text)에선 mini도 쓸 만" → mini 약점의 경계가 명확해짐.
- text에서도 많이 갈림 → "mini는 text에서도 못 믿음" → mini 약점이 광범위, 전부 5.4의 추가 근거.
- 어느 유형의 text(숫자/존재/값)에서 mini가 특히 약한지 있으면 기록.
- **한계 명시:** 20~40 item 소표본, text 일부 유형만. 신호이지 단정 아님. 이건 분석이며 production 결정(전부 5.4)을 바꾸려는 게 아님.

## 출력 — `tasks/0607_sunday/text_mini_reliability.md` (커밋 금지)
```
# [분석] text criterion mini vs 5.4 신뢰도
## 한 줄 결론
text item [N]개 mini vs 5.4: verdict 일치율 [?]%, score diff 평균 [?]. mini는 text에서 [거의 일치=판단형에만 약함 / 갈림=광범위 약함]. 오차 패턴 [random/체계적/거의없음]. (분석 목적 — production은 전부 5.4 유지.)
## 1. text item 표본 (추출 기준 + 목록 표)
## 2. 5.4 재채점 (소규모, 비용)
## 3. mini vs 5.4 비교 (verdict 일치율 / score diff / 불일치 item 판별 / 오차 패턴)
## 4. 해석 (mini 약점 경계 — 판단형 국한인가 광범위인가, text 유형별, 한계)
```

## 제약 재확인
- ⛔ git 상태 변경 전부 금지, read-only, 커밋 금지.
- 220 전체 재채점 금지(이건 분석). text 비교 소규모(<$1)만. 새 대규모 run 없음.
- 기존 220 mini JSON 재사용. secret 조작 금지. 인증 막히면 보고.
- 소표본 한계 명시, 단정 금지. production 결정(전부 5.4) 안 바꿈.
- 막히면 방향 틀지 말고 보고.
