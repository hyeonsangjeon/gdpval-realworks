# 마지막 구간이 끝난 뒤 — 결과를 대시보드까지 올리는 절차

이 문서는 **채점 이야기가 아니다.** 채점을 어떻게 할지는
[`grading_design.md`](grading_design.md)에 따로 적어 두었다. 여기는 그보다
앞이다. exp035의 마지막 구간이 끝나면 워크플로가 자동으로 PR을 하나 연다.
**업로드가 실패한 상태라면 그 PR의 Pages 검사가 빨갛게 뜬다.** 왜 그런지와,
그때 무엇을 해야 하는지를 적는다.

측정한 날은 2026-09-12이고, 그때 34685779030(relay_run 4)이 아직 돌고
있었다. 모델 호출은 0이다.

## 마지막 구간이 자동으로 하는 일

`batch-run.yml`의 「Create Pull Request with results」(1265행)가 PR을 연다.
문이 셋이고 exp035 계보 B는 셋 다 통과한다 — `dry_run`이 false이고,
마지막 구간이라 `needs_relay`가 `'false'`이고, step 2a가 성공이면 열린다.

그 PR에 들어가는 파일은 **하나뿐이다.**

```yaml
add-paths: batch-runner/results/${{ env.EXPERIMENT_ID }}/report/report.md
```

1296행이다. `report.md` 한 장이고, 같은 폴더의 `report_data.json`은 들어가지
않는다. `.gitignore` 259행이 그 이름을 막고 있기 때문이다.

```
batch-runner/results/*/report/report_data.json
```

바로 위 258행에 막는 이유가 적혀 있다 — "report_data.json은 HF Dataset에서
관리 (self_report.json)". 그동안은 맞는 말이었다.

## 대시보드가 그 폴더를 어떻게 읽는가

`scripts/aggregate-reports.mjs`는 실험 목록을 **폴더 이름을 훑어서** 만든다
(`readdir(RESULTS_DIR)`, 329행). 그래서 `report.md` 한 장만 병합돼도
`exp035_codex_foundry_full220` 폴더가 생기고, 그 순간 그 실험은 대시보드가
읽어야 하는 대상이 된다.

읽는 순서는 둘이다.

1. `batch-runner/results/<폴더>/report/report_data.json` — 있으면 그걸 쓴다.
2. 없으면 허브에서 받는다(102행).

```
https://huggingface.co/datasets/HyeonSang/<폴더>/resolve/main/self_report.json
```

주소의 `<폴더>`가 결과 폴더 이름 그대로다. exp035의 실험 YAML은
`data.source`가 `HyeonSang/exp035_codex_foundry_full220`이니 **이름은 맞다.**
문제는 이름이 아니다.

## 그 주소를 실제로 눌러 봤다

먼저 다섯 개를 그대로 받아 봤다. 인증 없는 공개 읽기다.

| 실험 | 실행 방식 | self_report.json |
|---|---|---|
| `exp003_GPT52Chat_baseline_runner_exec` | runner_exec | **200** |
| `exp027_GPT54_default_subprocess_bridge50` | subprocess | **200** |
| `exp033_codex_foundry_fixed5` | codex_foundry | **404** |
| `exp034_codex_foundry_trial30` | codex_foundry | **404** |
| `exp035_codex_foundry_full220` | codex_foundry | **404** |

**`codex_foundry` 방식으로 돌린 실험이 허브에 올라간 적이 한 번도 없다.**
exp035의 실험 YAML도 같은 말을 한다(244행 부근) — 이 세 단계 묶음이
"한 번도 거치지 않은 업로드 경로"라고 그 안에 적혀 있다.

지금 저장소의 결과 폴더 27개 중 26개는 허브에서 받아 오고 있고, 그래서
빌드가 초록이다. 나머지 하나가 exp034인데, 그것만 `report_data.json`을
저장소에 넣어 뒀다. 허브가 404라서 그렇게 한 것이다(#529, #532).

exp033도 404인데 아무것도 깨지지 않는 이유는 간단하다 — **결과 폴더가
아예 없다.** 대시보드는 폴더를 훑어서 목록을 만드니, 폴더가 없으면 그
실험을 찾지도 않는다. 그래서 지금 저장소에 있는 `codex_foundry` 실험 폴더는
exp034 하나뿐이고, 그 하나는 이미 사본을 넣어 막아 둔 상태다. exp035가
들어오면 **막히지 않은 두 번째**가 된다.

| 결과 폴더 27개 | `publish_to_hf` | 저장소에 payload |
|---|---|---|
| 24개 | 적지 않음 | 없음 (허브에서 받음) |
| 2개 | 실험 YAML 없음 | 없음 (허브에서 받음) |
| **exp034** | **false** | **있음** |

가운데 줄의 둘은 `exp030_envelope_host_python_process`와
`exp031_envelope_docker_container`다. 실험 YAML이 없으니 `publish_to_hf`를
볼 자리도 없는데, 둘 다 허브에서 **200**으로 받아진다. 같은 자리에서
`exp026c_cost_receipt_smoke`도 200이다. 즉 이 표의 "허브에서 받음"은
빌드가 초록이라는 데서 미루어 짐작한 것이 아니라 눌러 본 값이다.

exp035도 `publish_to_hf: false`다(실험 YAML 662행). 다만 그 값은 스위치가
아니라 **기록**이다 — YAML 252행이 직접 그렇게 적어 두었다. `codex_foundry`
방식에서는 아무도 그 키를 읽어서 업로드를 결정하지 않는다.

## 이미 있는 검사 둘은 왜 이걸 못 막나

이 문제의 절반씩을 막는 테스트가 이미 둘 있다.

- `scripts/__tests__/a-run-that-never-reached-the-hub-is-not-a-run-that-never-happened.test.mjs`
- `scripts/__tests__/a-report-that-only-exists-here-is-not-a-report-without-a-page.test.mjs`

둘 다 잘 쓰여 있고, 둘 다 같은 값 하나를 보고 판단한다 —
`meta.publication_plan`. 그런데 그 값을 정하는 코드가 이렇다
(`step6_report.py` 631~632행).

```python
"publication_plan": (
    "dry_run_no_step7" if dry_run else "step7_upload_requested"
),
```

**`dry_run` 하나로만 갈린다.** 이름 그대로 `requested`, 즉 "올리라고
시켰다"는 기록이지 "올라갔다"는 기록이 아니다. exp035는 `dry_run`이
false이니 무조건 `step7_upload_requested`가 찍히고, 두 테스트는 exp035를
**이미 발행된 쪽**으로 분류한다. 그래서 payload를 저장소에 넣으라고
요구하지 않는다.

다만 이 둘이 통과한다고 해서 아무도 못 막는다는 뜻은 아니다. 막는 것은
따로 있고, 그게 다음 절이다.

## 실제로 막는 것은 Pages 검사다

`deploy.yml`은 `pull_request`에서도 돈다(28행). 그 path 목록에
`batch-runner/results/**`가 들어 있고(34행), 자동 PR이 건드리는 자리가
바로 거기다. 그리고 `npm run build`(148행)에는 main 조건이 없다 —
main으로 제한되는 것은 아티팩트 업로드 단계(196행)와 `deploy` 잡(206행)
뿐이다. 즉 **PR 단계에서 aggregate가 실제로 돈다.**

읽기만 해서 얻은 결론이 아니라, 자동 PR이 만들 상태를 그대로 만들어
돌려 봤다. 결과 폴더에 `report.md` 한 장만 놓고 `aggregate-reports.mjs`를
실행한 것이다.

```
Error: 1 of 28 report(s) could not be loaded:
  exp035_codex_foundry_full220: no local report_data.json, and HuggingFace answered HTTP 404
Publishing the rest would drop them from the leaderboard, the trend view and
the sector matrix without saying so. If HuggingFace rate-limited this build,
re-run it; otherwise fix or remove the directory.
```

종료 코드 1이다. 그러니 **모르고 병합해서 나중에 배포가 깨지는 상황이
아니다.** PR에 빨간 검사로 먼저 뜬다. 좋은 쪽이다.

## 다시 돌려도 안 없어진다

여기가 진짜 함정이다. 위 오류 문구는 **"재시도해 보라"고 먼저 권한다** —
"If HuggingFace rate-limited this build, re-run it". 그리고 이 저장소에는
Pages 검사가 HuggingFace 요청 제한 때문에 빨개지는 **알려진 간헐 실패가
실제로 있다.** 그때의 올바른 대응이 재시도다.

404는 그쪽이 아니다. `aggregate-reports.mjs`가 다시 시도하는 상태는
408·425·429·500·502·503·504뿐이고(78행) 404는 그 안에 없다. 한 번 받고
바로 실패로 기록한 뒤 440행에서 던진다. **몇 번을 다시 돌려도 같은 자리에서
같은 값이 나온다.**

그래서 빨간 검사를 봤을 때 **먼저 숫자를 확인한다.** 429면 재시도가 맞고,
404면 재시도는 시간만 쓴다.

문구가 권하는 다른 하나는 더 위험하다 — "fix or remove the directory".
여기서 폴더를 지우면 220문제를 끝까지 돌린 실험이 대시보드에서 사라진다.
**지울 것이 아니라 채울 것이다.**

## 두 갈래다

step 7은 `continue-on-error`가 없다(1341행). 그러니 업로드가 실패하면
**그 실행 자체가 빨갛게 끝난다.** 두 갈래로 갈린다.

| step 7 | 허브 | 자동 PR의 Pages 검사 | 할 일 |
|---|---|---|---|
| 성공 | 200 | 초록 | 그대로 병합 |
| 실패 | 404 | **빨강** | 아래의 두 가지를 넣고 병합 |

**PR은 step 7보다 먼저 열린다**(1265행 대 1341행). 그래서 업로드가
실패해도 PR 자체는 정상적으로 열려 있고, 바뀌는 것은 그 PR에 붙는 검사
색깔뿐이다. 실행이 빨간 것과 PR이 빨간 것은 서로 다른 자리이고, 이 경우
**둘 다** 빨갛다.

**이건 step 7이 실패한다는 예측이 아니다.** 이 방식으로는 아직 한 번도
해 본 적이 없다는 사실과, 실패했을 때 무엇이 어떻게 보이는지를 적은 것이다.

## 병합 전에 할 일

마지막 구간이 끝나고 PR이 열리면, 검사가 다 붙기를 기다릴 것 없이 이것부터
한다. 1초면 끝나고, 빨간 검사가 뜨기 전에 이미 답을 알 수 있다.

```bash
curl -s -o /dev/null -w '%{http_code}\n' -L \
  https://huggingface.co/datasets/HyeonSang/exp035_codex_foundry_full220/resolve/main/self_report.json
```

- **200이면** 그대로 병합한다. 저장소에 사본을 또 넣지 않는다. 허브에 있는
  것을 페이지가 직접 받아 가고, 사본을 두면 둘이 조용히 어긋난다. 이 비대칭은
  위의 두 번째 테스트가 그 이유까지 적어 두었다.
- **404면** 병합 전에 두 가지를 같이 넣는다.

404일 때 넣을 것은 exp034가 이미 한 그대로다.

1. `.gitignore`에 예외 한 줄. 지금 267행에 exp034 것이 이렇게 들어 있다.

   ```
   !batch-runner/results/exp034_codex_foundry_trial30/report/report_data.json
   ```

2. 실행 아티팩트에서 꺼낸 `report_data.json`을 그 자리에 놓는다. 필요하면
   `derived_cost.json`도 같이 놓는다(이건 막혀 있지 않아 예외가 필요 없다).

그러면 `aggregate-reports.mjs`가 그 폴더를 `served_locally`로 표시하고,
상세 페이지도 허브 대신 빌드가 내보낸 사본을 읽는다. 허브를 한 번도 건드리지
않는다.

**이 복구에는 모델 호출이 0이다.** 결과는 전부 실행 아티팩트 안에 있고,
exp035 실험 YAML도 같은 말을 적어 두었다 — 세 단계 전부 아티팩트에서 공짜로
다시 돌릴 수 있어서, 실패해도 잃는 것은 그 실행의 `conclusion`이지 결과가
아니다. 다만 아티팩트는 30일 뒤에 사라지므로(`retention-days: 30`), 404인
경우에는 **그 안에 꺼내 두어야 한다.**

## 여기서 하지 않는 것

- **실행 중에 워크플로를 고치지 않는다.** 위 내용은 읽기와, 이 저장소 안에서
  `aggregate-reports.mjs`를 한 번 돌려 본 것으로 얻었다. 워크플로 파일은
  건드리지 않았다 — `batch-run.yml`을 구간이 도는 중에 병합하면 다음 구간이
  죽는다.
- **테스트를 새로 만들지 않는다.** "허브에 올라갔는가"는 망으로 물어야
  답이 나오는데, 위의 두 테스트는 둘 다 "여기서는 망을 건드리지 않는다"를
  명시한다. 그리고 망으로 묻는 검사는 **이미 있다** — PR에서 도는 Pages
  `validate` 잡이 그것이다. 거기에 더해 `codex_foundry`면 무조건 사본을
  넣으라고 쓰는 검사는 step 7이 성공한 날 **틀린 요구**가 된다 — 사본을
  두지 말라는 쪽이 그 테스트가 이유까지 들어 설명해 둔 원칙이다.
- **성공률을 건드리지 않는다.** 이 문서는 결과를 어디에 두느냐의 이야기이지
  결과가 무엇이냐의 이야기가 아니다. 220문제 중 무엇이 풀렸는지는
  `round_state.json`이, 채점은 `grading_design.md`가 따로 맡는다.
