# OPUS — PART 0: 대시보드 git 안착(자가 해결) + PART 1~3: 채점기 정확도 개선 패키지

> **기록용 작업 명세** (owner 지시 원문). 작성 2026-06-12. 진행/결과는 `tasks/0612_friday/accuracy_package.md`.

- **Repo:** `gdpval-realworks`
- **이번 작업 = 두 덩어리.** PART 0은 대시보드 phase 1+2를 origin/main에 *스스로 진단해서* 안착(한정적 git 권한). PART 1~3은 5.4 baseline의 두 정확도 잔여 이슈(과보수, pptx 렌더 게인)를 닫는 패키지.
- **배경:** judge=gpt-5.4 220 clean baseline 확정(`data/grades/exp003_..._judge_gpt-5_4__rubric_v2_tools.json`, 220/215, avg 53.3). gold-20 "Overall style" full-pipeline MAE **1.261**(2-arm 0.852 — 격차는 파이프라인 효과). 5.4 체계적 under-score(bias −0.64), pdf/xlsx `fail→0` 5건 — 과보수(0609 bbe0a93b/ee09d943). 렌더는 2-arm에서 **pptx만 일관 개선(ΔMAE −0.062)**, xlsx 악화(+0.100)라 xlsx 보류.

## PART 0 — 대시보드 phase 1+2 origin 안착 (git 자가 진단·해결)
- 상황: origin/main=`f0c58f3`로 보임(phase1 `bd82a77` 미반영?), HEAD=`e2f4c5b`(정체 불명), phase2 미커밋.
- **git 권한(이 PART 한정):** `fetch`/`status`/`log`/`diff` + phase1·2 대시보드 변경 commit/push(origin main). 여전히 금지: merge/rebase/reset/revert/force-push/tag/branch, 대시보드 외 커밋, PART1~3 커밋.
- 절차: fetch→origin 최신 확인→e2f4c5b 정체 확인→phase2 작업트리 존재 확인(없으면 보고서대로 재적용)→대시보드 파일만 surgical commit→push→라이브 검증(기본 exp003 2+배지/데모·스모크 없음/Best 99.5%·Exp21, `?debug=1` 13 복원).

## PART 1 — 5.4 과보수 진단 + judge 프롬프트 튜닝 (analyzer-first)
- 1a 진단(읽기): full 1.261 vs 2-arm 0.852 격차 원인 항목 분해(`fail→0` 5건 evidence 분류: 과보수/관찰부족/기타), 0609 2건 동일 축 확인. *진단 없이 프롬프트 고치지 마라.*
- 1b 튜닝: `prompts/grader_judge_v2.md`에 최소·외과적 가이드("관찰된 범위로 판단, 전체 스캔 못 함을 fail 사유로 X", "holistic 0점은 관찰된 명백 결함 시만").
- 1c A/B(gold-20 소규모): 현 vs 튜닝 프롬프트, 같은 gpt-5.4. 측정=owner gold MAE/bias(상승 아님), 회귀(과관대 스윙) 확인. <$5, az login + stale SP unset(.env 불변).

## PART 2 — pptx 선별 렌더 통합 (검증된 게인만)
- pptx만(xlsx 보류, pdf/docx 제외). 판단형 criterion에 렌더 PNG(soffice→PyMuPDF) 첨부. 설치(apt-get vs GHCR) 비교·제안, 단순한 쪽 구현.
- **opt-in 필수**(YAML 플래그), 기본 동작 불변·기존 baseline 영향 0.
- 검증(gold pptx 4: a74ead3b/ec591973/9a0d8d36/403b9234): [5.4 메타] vs [5.4+렌더] MAE — −0.062 재현? tofu 주의.

## PART 3 — 통합 검증 + 220 권고 (실행 금지)
- gold-20 [튜닝+pptx] vs baseline: 1.261→? 권고(개선폭/비용/리스크), 220 GO는 owner. config/절차 준비(opt-in, 출력 파일명 별도 보존).

## 제약
- git PART0만. PART1~3 코드/프롬프트/보고서 로컬 미커밋. 220 재채점 실행 금지(권고만). 검증 gold 소규모.
- 기존 baseline(5.4/mini) 불변. 렌더/프롬프트 opt-in. 진단 먼저. 측정=owner gold 거리. secret/.env 불변. 막히면 보고.

## 출력 — `tasks/0612_friday/accuracy_package.md` (PART0 결과 포함, 나머지 미커밋)
