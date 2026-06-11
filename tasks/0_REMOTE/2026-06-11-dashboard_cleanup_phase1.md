# OPUS (Copilot remote) — 대시보드 1차 정리: 데모/스모크 백도어 + exp003 매핑 보고

> **기록용 작업 명세** (owner 지시 원문). 작성 2026-06-11. 진행/결과는 `tasks/0607_sunday/dashboard_cleanup_phase1.md`에 별도 기록.

- **Repo:** `gdpval-realworks`, 대시보드는 GitHub Pages (`hyeonsangjeon.github.io/gdpval-realworks`), React+TS 프론트엔드.
- **상황:** 대시보드 Grading Analysis 탭에 카드가 뒤섞여 있다 — 실제 실험(exp003)과 *레거시 데모*(`GPT-5 Baseline (Sample)` DEMO)·*스모크*(`exp998_smoke_baseline_sample`, 3-task 테스트)가 한 화면에. 상단 "BEST SUCCESS RATE 99.5%"는 스모크의 부풀린 수치가 잡힌 것으로 보임(실제 exp003는 ~50-59%대).
- **이번 작업 = 1차(보수적):** 명백한 비실험 카드(데모/스모크)만 *기본 화면에서 숨기고* 쿼리파라미터로 복원 가능하게 한다. **exp003 카드는 이번엔 건드리지 말고**, 대신 "각 exp003 카드가 어느 grade JSON/실험에서 오는지" *매핑을 조사·보고*만 한다(2차 정리의 근거 확보). exp003 정리는 그 매핑을 owner가 보고 2차에서.
- **왜 보수적인가:** exp003가 여러 judge(gpt-5.4 / gpt-5.4-mini / gpt-5.4-pro)로 중복돼 있고 Graded 수도 제각각(219/220, 10/10 등)이라, *어느 게 clean 220 official이고 어느 게 옛날/부분/스모크인지* 아직 불명확. 모르는 상태로 적극 숨기면 진짜 official을 가릴 위험. 데모/스모크만 안전하게 치우고, 판별 데이터를 먼저 확보한다.

## ⛔ GIT 행위 절대 금지
- `git push`/`merge`/`commit`/`rebase`/`reset`/`revert`/`checkout <file>`/`tag`/`branch -f` **전부 금지.** read-only git만(`status`/`log`/`diff` 조회).
- 코드 변경(필터 로직)은 **로컬 작업트리에만** 남기고 **커밋/푸시 금지.** owner가 검토 후 직접 커밋. 산출(변경 diff, 매핑 보고)은 파일로 쓰되 커밋 금지.
- 어떤 이유로도 git 상태를 바꾸지 마라. 위반 시 중단 보고.

## PART 0 — 데이터 소스 직접 확인 (가정 금지)
- 대시보드가 grade 데이터를 *어디서* 읽는지 **코드에서 직접 확인**하라. (이전엔 HuggingFace로 알려졌으나 *바뀌었을 수 있으니 가정하지 말 것.*)
- 확인할 것: 데이터 fetch 경로(HF dataset? repo 내 JSON? API?), 빌드 타임 vs 런타임 로딩, 어느 파일/엔드포인트가 카드 리스트를 만드는지.
- 결과를 보고에 명시(소스 위치 + 로딩 방식). 이게 틀리면 이후 필터가 엉뚱한 데 적용되므로 *먼저 확정*.

## PART 1 — 숨길 대상 식별 (데모/스모크만)
코드/데이터에서 다음을 *식별 규칙*으로 잡아라(하드코딩된 카드명 나열이 아니라 패턴/플래그로):
- **데모:** `GPT-5 Baseline (Sample)` 또는 `DEMO` 플래그가 붙은 항목(레거시 데모 데이터). 식별 필드(예: `is_demo`, `source: legacy`, 이름 패턴)를 코드/데이터에서 찾아 규칙화.
- **스모크:** experiment id가 `exp998_smoke*`(또는 `*_smoke_*`) 패턴인 항목. 3-task 규모 테스트.
- **exp003는 제외** — 이번 숨김 대상 아님(2차에서). 식별 규칙이 exp003를 *건드리지 않는지* 확인.

## PART 2 — 백도어 토글 구현 (기본 숨김 + 복원)
- 기본 화면(쿼리파라미터 없음): 데모/스모크 카드 **숨김**. official 실험(exp003 등)만 표시.
- **`?debug=1`** (쿼리파라미터)이 있으면: 숨긴 데모/스모크도 *다시 표시*(전부 보임).
- 구현 주의:
  - **삭제가 아니라 표시 필터.** grade JSON/데이터는 그대로 두고 *렌더링만* 거른다(비가역 위험 0).
  - `?debug=1`은 공개 URL 누구나 칠 수 있는 *표시 토글*이지 접근 제어가 아님 — 데모/스모크는 민감정보 아니므로 이걸로 충분. (민감 데이터 가리는 용도 아님.)
  - 토글 상태를 URL에서 읽는 표준 방식(React Router / URLSearchParams 등 repo 관례 따라).
  - localStorage/sessionStorage 쓰지 마라(불필요). URL 파라미터만.

## PART 3 — 상단 지표 정상화 (BEST SUCCESS RATE 등)
- "BEST SUCCESS RATE 99.5%" 등 상단 요약 카드(BEST SELF-QA / BEST SUCCESS RATE / EXPERIMENTS / TASKS EVALUATED)가 **숨긴 데모/스모크를 제외한 official 실험만 반영**하도록.
  - 예: BEST SUCCESS RATE가 스모크(3-task, 99.5%)가 아니라 exp003 실제 최고치(~59%대)를 보이게.
  - EXPERIMENTS 카운트(현재 21)도 official만 셀지 전체를 셀지 — *기본 화면 기준 official만*, `?debug=1`이면 전체. (일관성: 토글 상태에 따라 상단 지표도 같이 바뀌게.)
- 단 이 지표 계산 로직이 어디 있는지 코드에서 찾아 *최소 수정*. 과도하게 리팩터하지 마라.

## PART 4 — exp003 매핑 보고 (2차 정리 근거 — 핵심)
**숨기지 말고 조사만.** 각 exp003 카드가 *어느 grade JSON 파일/어느 실험 run*에서 오는지 매핑:
- 화면의 exp003 카드들(JUDGE gpt-5.4 / gpt-5.4-mini / gpt-5.4-pro, 각기 다른 % 와 Graded 수)이 각각 *어느 데이터 소스*(파일명/HF path)에 대응하는지.
- 각각의 **task 수(완전성)**: 220인가 부분(10/10 등)인가. 어느 게 clean 220 official인가(우리가 방금 만든 `..._judge_gpt-5_4__rubric_v2_tools.json` = clean 5.4 220, `..._judge_gpt-5_4-mini__rubric_v2_tools_mini.json` = clean mini).
- **`gpt-5.4-pro` 카드(77%대)가 무엇인지** — 스모크인지, 옛날 실험인지, 별도 judge인지. 데이터로 밝혀라.
- 중복/옛날/부분 카드 후보 목록(2차에서 숨길 후보) — *제안만*, 이번엔 실행 안 함.
- 이 매핑이 2차 정리("official만 남기고 옛날/부분 exp003 숨김 + official 배지")의 입력이 된다.

## 검증
- `?debug=1` 없을 때: 데모/스모크 안 보임, exp003 다 보임, 상단 지표 official 반영.
- `?debug=1` 있을 때: 전부 보임(데모/스모크 복원).
- exp003 카드가 1차에서 *하나도 안 사라졌는지* 확인(이번엔 exp003 불가침).
- 로컬에서 토글 양쪽 동작 확인(스크린샷 또는 동작 설명).

## 출력 — `tasks/0607_sunday/dashboard_cleanup_phase1.md` (커밋 금지)
```
# DASHBOARD CLEANUP PHASE 1 — 데모/스모크 백도어 + exp003 매핑
## 한 줄 결론
## PART 0 데이터 소스 (코드에서 확인한 fetch 경로/로딩 방식)
## PART 1-2 데모/스모크 식별 규칙 + 토글 구현 (변경 파일/라인, 삭제 아닌 필터)
## PART 3 상단 지표 정상화 (어느 로직, 최소 수정)
## PART 4 exp003 매핑 (카드↔파일, task 수, pro 정체, 2차 숨김 후보 — 제안만)
## 검증 (토글 양쪽, exp003 불가침 확인)
## 다음 (owner 커밋 후): 2차 = exp003 official만 남기고 옛날/부분 숨김 + official 배지
```

## 제약 재확인
- ⛔ git push/merge/commit 등 전부 금지. read-only. 코드 변경은 로컬만, 커밋 금지.
- 데이터 소스 *직접 확인*(HF 가정 금지) — 이게 PART 0, 먼저.
- 데모/스모크만 숨김(표시 필터, 삭제 아님). **exp003 불가침**(2차에서).
- 토글 = URL 파라미터, localStorage 금지. 접근제어 아닌 표시 토글.
- 상단 지표 최소 수정. exp003 매핑은 *조사·제안만*, 실행 금지.
- 막히면 방향 틀지 말고 무엇이 막혔는지 보고.
