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
| `exp035_run34603033098_partial/` | [34603033098](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/34603033098) | 220문제 중 58개에서 중단. `RELAY_RUN_INPUT: 0`으로 출발해 위 실행을 이어받지 않고 **처음부터 다시** 돌았고, 그 45개를 다시 풀었습니다 |
| `exp035_run34631861765_partial/` | [34631861765](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/34631861765) | 220문제 중 102개에서 중단. **이어받기가 처음으로 실제 동작**해 위 실행의 58개를 하나도 잃지 않고 물려받아 59–102번을 진행. 두 계보 중 긴 쪽을 골라 중복 0 |

계보가 둘입니다. 34571840967이 계보 A, 나머지 둘이 계보 B이고, **계보 A가 손댄
45문제는 계보 B가 손댄 102문제에 전부 포함됩니다.** 그래서 기록이 셋이라고
진도가 45+58+44인 것이 아니라, 이 회차가 손댄 문제는 **102개(220문제의
46.4%)** 입니다. 비용은 반대로 겹치지 않습니다 — 두 번 풀었으면 두 번
나갔습니다.

## 기록을 만드는 방법

손으로 적지 않습니다. `batch-runner/scripts/build_partial_run_record.py`가
아티팩트에서 `outcomes.json`과 `deliverable_manifest.json`을 만듭니다:

```
python scripts/build_partial_run_record.py <아티팩트 폴더> \
    --run-id <실행번호> \
    --output-dir docs/run_records/<이름> \
    --log <ANSI 제거한 job 로그> \
    [--log <다른 구간의 로그>]... \
    [--ledger <앞 구간의 원장>]...
```

`--log`를 빼도 기록은 만들어지지만, 실패한 문제마다 제공자가 실제로 무슨 말을
했는지가 `message_source: "not_available"`로 비어서 나옵니다. 체크포인트에는
실패 종류와 무관하게 `task_execution_error:TaskExecutionError`가 똑같이 적혀
있어서, 원인 문구는 **로그에만** 남습니다. 비는 자리는 비워 두고 추측으로
채우지 않습니다.

**이어받은 구간에서는 `--log`와 `--ledger`를 구간 수만큼 넣어야 합니다.**
한 구간은 자기가 부른 문제만 로그에 적고, 자기가 부른 문제만 원장에 적습니다.
그래서 물려받은 문제는 — 실제로는 앞 구간이 돈을 내고 제공자가 문구까지
보낸 문제인데 — 이 구간의 로그와 원장에서만 보면 **아무도 부른 적 없는 문제와
똑같이 보입니다.** 빠뜨리면 두 가지가 어긋납니다:

| 빠뜨린 것 | 그러면 |
|---|---|
| 앞 구간의 `--log` | 그 실패들이 문구 없이 남고 `message_source: "not_available"`이 붙습니다 |
| 앞 구간의 `--ledger` | 그 문제들이 `absent_from_supplied_ledgers`로 남고 스크립트가 `NOT PRICED` 경고를 찍습니다 |

두 자리 모두 **`$0.00`이나 빈 문구로 조용히 채우지 않습니다** — 모르는 것을
모른다고 적는 것이 이 플래그들의 존재 이유입니다. 고정 시험은
`tests/test_a_failure_with_no_sentence_says_so_on_its_own_row.py`와
`tests/test_a_resumed_leg_may_not_price_inherited_work_as_free.py`입니다.

`report.md`는 사람이 씁니다.

## 여러 기록의 비용을 합칠 때

`derive_run_cost.derive()`에 **원장을 한꺼번에** 넘기면 됩니다. 구간마다 따로
계산해 손으로 더할 필요가 없습니다.

```python
from derive_run_cost import derive
derive([legA_ledger, legB3_ledger, legB4_ledger])
# -> 호출 258, 금액 $56.1650, 문제 102
```

이게 이 회차의 **중복 없는 집계**입니다. 문제는 합쳐지고(45+58+44가 아니라
102), 금액은 더해집니다 — 겹친 문제는 두 번 낸 돈이 한 줄에 합산됩니다. 두
성질이 다른 이유는 간단합니다: **커버리지는 두 번 세면 안 되고, 지출은 두 번
나갔기 때문입니다.**

원장들의 가격표 지문이 서로 다르면 `derive()`는 합치지 않고
`DerivationRefused`를 냅니다. 단가가 바뀐 뒤의 실행과 그 전의 실행을 한 숫자로
만들지 않기 위해서입니다. 실행이 기록한 지문이 지금 저장소에 있는 가격표와
다를 때도 같은 이유로 거절합니다 — 실행이 본 적 없는 단가로 그 실행의 금액을
매기면 다른 요금제의 숫자가 나오기 때문입니다. 그래서 **실행이 도는 중에는
단가표를 고치면 안 됩니다.** 고치면 그 실행의 비용은 영구히 계산 불가가 됩니다.
