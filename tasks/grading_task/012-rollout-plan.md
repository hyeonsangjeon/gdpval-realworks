# 012 — Rollout Plan (Phase A → Phase B)

## PR 분할 (확정)

### PR #1 — Phase A core (이 패키지 001~007, 010, 011)
- 신규 파일:
  - `batch-runner/core/rubric_loader.py` (001)
  - `batch-runner/core/grader.py` (002)
  - `batch-runner/prompts/grader_judge.md` (003)
  - `batch-runner/step8_grade.py` (004)
  - `.github/workflows/grade-run.yml` (005)
  - `batch-runner/grading_configs/default_gpt5pro.yaml` (006)
  - `batch-runner/schemas/grade.schema.json` (007)
  - `.github/agents/grading-engineer.md` (011)
  - `batch-runner/scripts/download_inference_from_hf.py` (005 sidecar)
  - 테스트 파일들 (각 spec의 "테스트" 섹션 참조)
- 삭제:
  - `batch-runner/core/evals_submitter.py` (010)
  - `batch-runner/tests/test_evals_submitter.py` (010)
- 수정:
  - `.github/agents/llm-systems-engineer.md` (010 — 한 줄 제거)
  - `CHANGELOG.md` (Removed + Added 섹션)
- **무변경**:
  - `core/narrative_analyzer.py`, `step6_report.py`
  - dashboard (src/, scripts/aggregate-grades.mjs는 dummy 그대로 표시)
  - `batch-run.yml` (inference 파이프라인)

### PR #2 — Phase A wow (이 패키지 008, 009)
- 수정:
  - `core/narrative_analyzer.py` (008 — `grade` 파라미터)
  - `step6_report.py` (008 — grade 로더)
  - `scripts/aggregate-grades.mjs` (009 — v1.0 schema 파싱)
  - `src/hooks/useGrades.ts`, `src/types/*.ts` (009 — 타입)
  - `src/pages/GradeDetail.tsx` (009 — WOW 카드/차트)
  - `src/components/GradesSummary.tsx` (009 — 카드 + 카피)
  - `src/data/tooltipTexts.ts` (009 — i 풍선)
- 신규:
  - `src/components/wow/*.tsx` (W1~W6 컴포넌트)
- 회귀 테스트:
  - dummy_gpt5_baseline.json이 여전히 legacy 모드로 표시되는지

### PR #3 — Phase B (별도 spec 필요)
- Cross-family judge (Claude/Gemini) 22~33 stratified sample
- Cohen's κ + calibration factor 계산 스크립트
- W7 (Failure Mode Cluster) LLM clustering batch
- `workflow_run` 자동 chain
- Multi-judge variance (W10)

## 검증 시퀀스 (S2 = a 먼저, OK면 b)

### Stage 1 — smoke (`exp998_smoke_baseline_sample`, 3 tasks)
```bash
# Dry-run으로 분류기 확인
python step8_grade.py exp998_smoke_baseline_sample \
  --config grading_configs/default_gpt5pro.yaml \
  --dry-run --limit 3
# expected output: classification stats (precheck N개, judge M개)

# 실 채점 (소량)
python step8_grade.py exp998_smoke_baseline_sample \
  --config grading_configs/default_gpt5pro.yaml \
  --limit 3

# 결과 검증
jq '.summary' data/grades/exp998_smoke_baseline_sample__*.json
# expected:
#   - schema_version="1.0"
#   - tasks 3개
#   - 각 task에 items[] 채워짐
#   - 각 item에 evidence 존재
#   - pct 0~100 범위
```

**합격 기준 (Stage 1)**:
- [ ] grade JSON 파일 생성 (007 schema validate 통과)
- [ ] 모든 verdict에 evidence quote 존재
- [ ] precheck_count + judge_call_count = 총 rubric items 수
- [ ] judge_error 0건 (3 tasks 기준)
- [ ] CI 워크플로 `grade-run.yml` 수동 트리거 성공

### Stage 2 — 실 채점 (`exp025_GPT54_high_postfix`, 220 tasks)
```bash
# GitHub Actions UI에서:
# workflow_dispatch trigger:
#   experiment_yaml: exp025_GPT54_high_postfix
#   grading_config: default_gpt5pro.yaml
#   force: false
#   tasks_limit: 0
#   dry_run: false
```

**합격 기준 (Stage 2)**:
- [ ] 220 tasks 모두 채점 (또는 judge_error 1% 미만)
- [ ] 총 비용 < $100 (예산 가드)
- [ ] 워크플로 8h timeout 이내 완료
- [ ] grade JSON git commit 성공
- [ ] (PR #2 머지 후) dashboard에서 WOW 카드 정상 표시

## 운영 절차 (PR #1 머지 후)

### 신규 실험 channel
```
1. inference: batch-run.yml workflow_dispatch (수동)
2. 결과 확인: HF submission repo, data/tests/<exp>.yaml
3. grading: grade-run.yml workflow_dispatch (수동, P1=a)
4. dashboard 자동 빌드: GitHub Pages
```

### 기존 실험 백필 (exp001~024 + exp025 후)
- 1개씩 수동 trigger
- TPM 우려로 동시 1잡만 (concurrency group이 이미 분리되어 다른 exp는
  병렬 OK이지만, 같은 judge_model을 쓰는 한 Azure deployment TPM이 공유
  되므로 실질적으로 1잡)

## 비용 견적 재확인

| 항목 | 1회 비용 (220 tasks) |
|---|---|
| Judge 호출 ~3300개 (precheck 50% 가정) | ~$50~80 (gpt-5.4-pro) |
| HF 데이터 다운로드 | $0 (캐시 hit) |
| GitHub Actions 분 | ~8h × runner cost (linux-large) |
| **총** | **~$60~90 / 실험** |

기존 실험 25개 백필 → 약 **$1500~2250**. 예산 사전 승인 필요.

## 모니터링 / 알림

PR #1엔 미포함. Phase B에서 추가:
- judge_error_rate > 5% → Slack/Discord 알림
- 비용 알림: 일일 누적 grading 비용 > $200 → 알림
- TPM throttling 빈발 시 자동 backoff 강화

## 롤백 절차

### 코드 롤백 (PR #1)
- `git revert <merge_commit>` — `core/evals_submitter.py` 복구 포함

### 데이터 롤백
- 잘못 생성된 grade JSON 파일은 `git rm` + `git commit` (PR #2의
  dashboard가 자동으로 다시 "pending" 상태 표시)

### 부분 롤백 (judge model 교체)
- `grading_configs/default_gpt5pro.yaml` 수정 (model + deployment 2줄)
- 새 grade 파일이 새 4-tuple로 생성 → 기존 grade는 보존
- dashboard는 가장 최근 (mtime 기준) 파일 우선 표시

## 의사결정 박제

- 본 rollout plan은 PR #1 머지 전까지 "frozen"
- 변경 필요 시 amendment 문서 발행 + 사용자 명시적 승인

## 의존성

- 모든 다른 spec (000~011)
- 사용자 GH Actions 권한 (workflow_dispatch)
- Azure OIDC + AZURE_OPENAI_ENDPOINT secret 정상

## 다음 actionable

1. ✅ 본 명세 패키지 14개 파일 박제 (이 작업 완료 시)
2. ⏭ PR #1 작업 — coder agent 또는 grading-engineer agent에 위임
3. ⏭ Stage 1 smoke 검증
4. ⏭ Stage 2 실 채점
5. ⏭ PR #2 (narrative + WOW dashboard)
6. ⏭ Phase B 별도 spec 작성
