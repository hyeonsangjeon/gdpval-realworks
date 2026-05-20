# 000 — 컨셉 합의문 + 아키텍처

## 1. 배경

- OpenAI가 `evals.openai.com` 호스팅 채점을 종료
  ([공지](https://evals.openai.com/gdpval/grading))
- GDPval v2 dataset에 `rubric_json`, `rubric_pretty`, `deliverable_files`
  (gold), `reference_files`가 공개됨
- 우리 코드의 `core/evals_submitter.py`는 placeholder였고 production 호출
  경로 없음 (010 명세 참조)
- Dashboard는 “Grading In Progress” placeholder로 외부 채점을 기다리는
  UX. 채점 데이터(`data/grades/`)가 비어있는 상태

## 2. 컨셉 합의

### 2.1. 채점 단위 — partial 0~1 per rubric item (Q1)
- rubric item마다 0~1 (또는 0 ~ max_score)로 부분 점수 부여
- holistic 단일 점수가 아닌 rubric item level data가 분석/시각화의 기반

### 2.2. Gold deliverable — rubric만 본다 (Q2)
- 0/220 tasks have gold. 사용 불가
- rubric이 self-contained하게 설계되어 있어 가능

### 2.3. 정규화 — % + 절대값 병기 (Q3)
- task별 `pct = sum(awarded) / sum(max) * 100`
- 절대값(`awarded`, `max`)도 항상 기록
- Dashboard UI에 i 풍선으로 의미 설명

### 2.4. Required 정책 — 가중 합산만 (Q4)
- 현재 220 / 220 모두 `required=null`
- `critical_fail` 플래그 컬럼은 schema에 유지하되 현재는 항상 false
- 미래 dataset에 `required=true`가 등장하면 자동 발화

### 2.5. Multi-file — pre-check + LLM judge (Q5)
- rubric item을 다음 분류기로 라우팅:
  - **precheckable** (정규표현 패턴 매칭): 코드로 직접 검증
  - **judgement**: LLM judge가 evidence quote와 함께 verdict
- 분류기는 1차에서 규칙 기반(`PRECHECK_PATTERNS`), 누락 발견 시 룰 추가

### 2.6. Evidence quote 의무화 (Q8)
- LLM judge verdict는 반드시 evidence quote (≤ 200자) 포함
- 누락 시 verdict=fail (defensive default)
- judge JSON 파싱 실패는 1회 재시도, 그 후 verdict=judge_error

### 2.7. Reproducibility
- temperature=0, seed=42, rubric_version(HF commit SHA), prompt 버전을
  grade JSON에 박제
- 4-tuple cache key: `(exp_id, judge_model, rubric_sha, prompt_v)`
- 파일명: `data/grades/<exp_id>__<judge>__<rubric_short_sha>__<prompt_v>.json`

### 2.8. Judge 모델 (J1)
- 1차: `gpt-5.4-pro` (Azure OpenAI Responses API)
- narrative_analyzer.py가 이미 사용 중인 deployment 재활용
- self-preference bias 인지하고 진행. Phase B에서 cross-family 보정
  (Claude/Gemini)으로 calibration factor 산출

## 3. 아키텍처

```
[Inference Pipeline]    batch-run.yml   (기존, 무변경)
   step1~step7 → HF Hub PR → step2_inference_results.json
                                   │
                                   ▼ (수동 trigger, P1=a)
[Grading Pipeline]      grade-run.yml   (신규, 분리)
   step8_grade.py
       │
       ├── core/rubric_loader.py    (openai/gdpval HF rubric+gold cache)
       ├── core/grader.py           (precheck + LLM judge, evidence)
       ├── prompts/grader_judge.md  (rubric-aware prompt)
       └── grading_configs/*.yaml   (judge model + reasoning + tpm guard)
                                   │
                                   ▼
                          data/grades/<exp_id>__<judge>__<sha>__<v>.json
                                   │
                                   ├──→ scripts/aggregate-grades.mjs
                                   │      → public/generated/grades-*.json
                                   │      → Dashboard WOW 카드/차트
                                   │
                                   ▼
[Narrative Summary]     step6_report.py (확장, PR#2)
   NarrativeAnalyzer.analyze(grade=...)  ← grade를 추가 input으로
       gpt-5.4-pro (Responses API, 기존 2-call)
                                   │
                                   ▼
                          workspace/report/* → Dashboard narrative
```

## 4. PR 분할 (확정)

### PR #1 — Phase A core (이 명세 패키지의 001~007 + 010, 011)
- 신규: `core/rubric_loader.py`, `core/grader.py`,
  `prompts/grader_judge.md`, `step8_grade.py`,
  `grading_configs/default_gpt5pro.yaml`, `.github/workflows/grade-run.yml`,
  `.github/agents/grading-engineer.md`
- 삭제: `core/evals_submitter.py`, `tests/test_evals_submitter.py`
- 산출: `data/grades/<exp_id>__...json` (smoke 검증으로 생성 확인)
- **무변경**: dashboard, narrative_analyzer, batch-run.yml

### PR #2 — Phase A wow (008, 009)
- NarrativeAnalyzer.analyze()에 `grade` 파라미터 추가, prompt 가드 조건부화
- scripts/aggregate-grades.mjs 확장 (WOW 메트릭 계산)
- Dashboard 컴포넌트 (W1~W7 카드/차트), 카피 수정

### PR #3 — Phase B (추후, 별도 spec)
- cross-family judge (Claude/Gemini) 22~33 stratified sample
- Cohen’s κ, calibration factor
- workflow_run 자동 chain
- multi-judge variance (W7, W10)

## 5. 운영 정책

### 5.1. 트리거 (P1)
- 기존 exp001~025: **수동 (`workflow_dispatch`)**
- 신규 실험: 1차 수동, 안정화 후 `workflow_run` 자동 chain (Phase B)

### 5.2. 재실행 (P2)
- 동일 4-tuple `(exp, judge, rubric_sha, prompt_v)` 존재 → skip
- `--force` 플래그로 덮어쓰기

### 5.3. 동시성 (P3)
- 1차: 순차 (`max_concurrent: 1`)
- 이유: `gpt-5.4-pro` TPM 한도
- Phase B에서 asyncio + semaphore 도입 검토

## 6. WOW 메트릭 (009 참조)

OpenAI 더미는 task-level binary × 3 graders만 노출 (avg ∈ {0, 0.33, 0.67,
1.0} 4단계). 우리는 item-level partial로 데이터가 10배 풍부. 이를 활용한
시각화:

- **W1** Rubric Item Coverage (task당 통과 항목 비율)
- **W2** Critical Item Pass Rate (가중치 ≥ 3점 항목 통과율)
- **W3** Precheck vs Judge Breakdown
- **W4** Sector × Rubric Category Heatmap
- **W5** Score Density Histogram (item-level)
- **W6** Rubric Severity Curve (가중치 정렬 통과율)
- **W7** Failure Mode Cluster (Phase A 후반부 또는 Phase B)

OpenAI 호환 메트릭 (비교 가능성):
- Average Score % + CI
- Perfect (100%) / Partial / Zero count
- Inconsistent (Phase B multi-judge에서만 의미)

## 7. 비용 견적

220 tasks × 평균 30 items × 절반(~15)이 judge 대상:
- ~3300 judge 호출
- 호출당 ~3000 input + 800 output tokens
- `gpt-5.4-pro` 가격 기준: ~$50~80 / 실험 1회 채점
- precheck 항목은 무료 (decision time < 100ms)

## 8. 보안 / 라이선스 / 가드

- HF에서 rubric/gold 다운로드 시 캐시는 `data/gdpval-local/` 재사용
  (이미 step0_bootstrap이 사용 중인 위치)
- rubric은 openai/gdpval dataset license 준수 — 결과 파일에 `rubric_source`
  필드로 출처 명시 (N3 참조)
- judge prompt에 PII 가드: deliverable에 사람 이름/이메일 등이 있어도
  evidence quote에 노출하지 않도록 prompt에 명시 (003 참조)

## 9. 의사결정 박제 (변경 금지)

이 컨셉 합의문은 PR #1 머지 전까지 “frozen”이다. 변경이 필요하면 별도
amendment 문서를 발행하고 명시적 사용자 승인 후 본 파일을 갱신한다.
