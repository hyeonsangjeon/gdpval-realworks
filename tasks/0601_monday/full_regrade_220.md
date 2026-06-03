# FULL REGRADE 220 — selector+audit (clean measurement)

## 한 줄 결론
BLOCKED on gold only. selector+audit+evidence fix는 `main`/`origin/main`에 머지 및 push 완료됐다. 하지만 owner hand-grade `overall_style_v1` gold JSON이 아직 repo에 없어서, gold 21건 비교를 포함한 220 clean measurement는 시작하지 않았다.

## Code/Merge 상태

현재 selector branch와 main은 같은 커밋을 가리킨다.

```text
main = f57467e55756d127736241960a5a341236f13a5e
origin/main = f57467e55756d127736241960a5a341236f13a5e
feat/deliverable-selector = f57467e55756d127736241960a5a341236f13a5e
origin/feat/deliverable-selector = f57467e55756d127736241960a5a341236f13a5e
```

Included evidence fix commit:

```text
f57467e fix(grader): preserve split child evidence in audit
```

This includes:
- selector implementation
- grader integration
- audit schema/fields
- split child evidence fix
- smoke reports

## Gold JSON 상태

다음 경로/패턴으로 확인했지만 owner gold JSON은 없다.

```text
docs/human-in-the-loop/overall-style-gold.json: missing
docs/** / tasks/** *gold*.json: no owner gold export found
owner_score numeric: not found
gold_version=overall_style_v1: not found outside HITL sheet templates
```

현재 발견되는 JSON은 smoke output뿐이다.

```text
tasks/0601_monday/smoke_regrade_outputs/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__selector_smoke_gold20.json
```

이 파일은 machine grade output이지 owner gold가 아니다.

## 실행하지 않은 것

- 220 재채점: not run
- OIDC workflow dispatch: not run
- relay/checkpoint run: not run
- secret reset/manipulation: none
- local Azure 220 run: none

## 필요한 owner action

Owner hand-grade export JSON을 아래 경로에 추가:

```text
docs/human-in-the-loop/overall-style-gold.json
```

Expected:
- `gold_version = overall_style_v1`
- `owner_score` populated
- item count: 21 if that is the owner-final HITL set
- task/file identifiers sufficient to join against regrade output

## 다음

Gold JSON이 들어오면 다시 실행:
- OIDC relay 220 재채점
- selection_status 분포
- reference echo 교정 수
- wrong_format_primary 목록
- audit field 220 전체 기록 확인
- gold 21건 v2 vs owner_score 격차 분석
- 렌더+vision 범위 결정
