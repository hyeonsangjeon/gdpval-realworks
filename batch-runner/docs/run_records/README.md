# 실행 기록 (run records)

여기 있는 폴더는 **대시보드에 실리는 실험이 아닙니다.** 끝까지 가지 못한 실행을
있는 그대로 남겨둔 기록입니다.

## `batch-runner/results/`가 아니라 여기인 이유

두 가지입니다. 둘 다 실제로 빌드를 깨뜨린 뒤에 알게 된 것입니다.

**1. `results/` 아래는 전부 "발행되는 실험"이라는 뜻입니다.**

`scripts/aggregate-reports.mjs`는 `batch-runner/results/`의 모든 하위 폴더를
훑어서 `report/report_data.json`을 요구합니다. 없으면 로컬에 이어
HuggingFace에서 받아오려 하고, 그것도 실패하면 **빌드를 세웁니다**:

```
Error: 1 of 28 report(s) could not be loaded:
  exp035_..._partial: no local report_data.json, and HuggingFace answered HTTP 401
```

일부러 그렇게 만들어져 있습니다 — 리포트 하나가 조용히 빠진 채로 발행되면
리더보드·추세·섹터 행렬에서 아무 말 없이 사라지기 때문입니다.

끊긴 실행에 `report_data.json`을 만들어 넣으면 통과는 하지만, 그러면 이
부분 실행이 **리더보드에 점수처럼 올라갑니다.** 45문제 중 30개 성공은 성적이
아니라 중단 지점입니다. 그걸 성적표에 올리면 측정이 아니게 됩니다.

**2. short_id가 충돌합니다.**

`extractShortId()`는 폴더 이름 앞의 `exp\d+`를 잘라냅니다. 그래서
`exp035_codex_foundry_full220_run34571840967_partial`과, 나중에 완주한 실행이
쓸 `exp035_codex_foundry_full220`이 **둘 다 `exp035`**가 됩니다.
`findShortIdCollisions()`가 이걸 잡아 빌드를 세웁니다 — 안 그러면 한쪽 숫자가
다른 쪽 이름으로 렌더링되기 때문입니다.

즉 이름을 어떻게 바꿔도 `results/` 안에서는 완주한 exp035와 공존할 수 없습니다.

## 그래서 규칙

- 완주해서 **발행할** 실험 → `batch-runner/results/<exp_id>/report/`
- 끊기거나 버려진 실행의 **보존 기록** → 여기 `run_records/<exp_id>_run<실행번호>_partial/`

폴더 이름에 실행 번호를 박습니다. 같은 실험을 여러 번 돌리다 끊긴 기록이
서로 덮어쓰지 않게 하기 위해서입니다.

## 여기 있는 기록

| 폴더 | 실행 | 무슨 일이 |
|------|------|----------|
| `exp035_run34571840967_partial/` | [34571840967](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/34571840967) | 220문제 중 45개에서 중단. 인계 구간 결함(#535에서 수정) |
