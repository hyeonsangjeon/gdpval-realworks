# 300 — Gold-Ceiling Test

> PR3 / 1 of 4. SPEC §7-1.

## 목적

`openai/gdpval` rubric에 포함된 gold deliverable을 v2 grader로 채점. **gold가 ceiling을 안 찍으면 grader/입력이 여전히 깨진 것** — 가장 중요한 sanity check.

## 작업

1. `data/gdpval-local`의 reference_files / gold_deliverable_files 위치 확인
2. 새 stub experiment yaml `experiments/exp_gold_baseline.yaml` 작성: gold deliverable 자체를 결과물로 등록
3. v2 grader로 220 task 전체 grade (또는 첫 sample 30)
4. 결과 분석:
   - avg_score_pct 평균 (기대 ≥ 90% — gold이라면 거의 만점)
   - critical_item_pass_rate (기대 ≥ 0.95)
   - judge_error_rate (기대 < 2%)
   - 만점 못 받은 항목들의 evidence — 라이브러리 한계 vs 진짜 미흡 판별

## Acceptance

- gold 평균 pct ≥ 90%
- critical_pass ≥ 0.95
- 미달 시 grader/tool 결함 보고 (PR2로 되돌림 또는 hotfix)
