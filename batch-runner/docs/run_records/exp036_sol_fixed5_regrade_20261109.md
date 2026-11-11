# exp036 — 선택기 수정 뒤 다섯 과제를 전부 다시 채점한 결과

선택기 수정(#801)이 머지된 뒤 exp036의 다섯 과제를 같은 채점자로 처음부터 다시
채점했습니다. 아래 수치는 커밋된 파일과, 고정 개정판에서 인증 없이 받은
`self_report.json`·결과물 파일에서 다시 계산한 것이고, 이 기록을 만들면서 모델을
부르지 않았습니다.

- 옛 채점(선택기 수정 전): `data/grades/exp036_sol_fixed5__…__src_814d56797e9fc3dc__v2.2.json`
  (sha256 `fcb0359b7bfe5f8e…`, 2026-11-05T15:14:23Z)
- 새 채점(전체 재채점): `data/grades/exp036_sol_fixed5__…__src_6f8811acb9de0b81__v2.2.json`
  (sha256 `6649ba7a6c07d068…`, 2026-11-09T09:08:21Z, `run_status: final`, 5개 중 5개)
- 실행: [42361049576](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/42361049576),
  `main` `567f9b3f`(#801 머지 커밋)에서 돌았습니다. 봇 커밋 셋:
  `f99389d7`(합산 USD 일지), `9f159871`(채점 파일과 원장), `23855644`(자동 분석)
- 기계가 읽는 기록: [`exp036_sol_fixed5_regrade_20261109.json`](exp036_sol_fixed5_regrade_20261109.json)
  (`parity-regrade-record-v1`). 만든 명령:

```
cd batch-runner
python scripts/merge_parity_regrade.py \
  --published ../data/grades/<옛 채점>.json \
  --regrade ../data/grades/<새 채점>.json \
  --self-report <HyeonSang/exp036_sol_fixed5 @8708d920의 self_report.json> \
  --json-out docs/run_records/exp036_sol_fixed5_regrade_20261109.json
```

`self_report.json`은 인증 없이 `8708d9206ce4c9c9ba96f8bfba0745e12e597777` 개정판에서
받았습니다(sha256 `7e9b97c8…3d98`). 재채점이 다섯 과제를 다 덮으므로 이 도구가
"합친 결과"라고 부르는 것은 새 채점 그 자체입니다. JSON의 `mixed_identity_caveat`도
두 채점에서 그렇게 읽어 적습니다: 행 다섯 개가 모두 새 채점에서 왔고, 채점기 지문·렌더러
지문·판정 표본이 하나씩입니다.

## 바뀐 것은 채점기 지문 하나입니다

| | 옛 채점 | 새 채점 |
|---|---|---|
| 판정자 | `gpt-5.6-sol`, effort `max` | 같음 |
| 프롬프트 / 루브릭 | `v2.2` / `11e7900c…` | 같음 |
| 채점 설정 | `exp036_v2_sol_max`, `cfg_1794403983325602` | 같음 |
| 추론 | `HyeonSang/exp036_sol_fixed5` @`8708d920…` | 같음 |
| 렌더러 | LibreOffice 24.2.7.2, PyMuPDF `2.1` | 같음 |
| `grader_source_hash` | `814d56797e9fc3dc…` | **`6f8811acb9de0b81…`** |

새 지문은 `567f9b3f`에서 `step8_grade.compute_grader_source_hash`로 다시 계산해도
`6f8811acb9de0b81…`이 나옵니다. 이 브랜치에서 계산해도 같습니다. 옛 채점을 만든 실행
(42039154052, `fc5a193c`)과 `567f9b3f` 사이에 채점기 소스 묶음(`core/`, `step8_grade.py`,
스키마, requirements, 프롬프트, 내려받기 스크립트, 채점 설정)에서 바뀐 파일은 #801의 두
개뿐입니다: 선택기(`core/deliverable_selector.py`)와 `.eml` 읽기(`core/tools/read_deliverable.py`).

## 점수 — 분모 둘, 범위 둘

| 보기 | 판정 받은 과제 | 판정 받은 과제만 평균 | 다섯 과제 고정 평균 |
|---|--:|--:|--:|
| 옛 채점, `pct` | 2 | 83.665 | 33.466 |
| 옛 채점, `pct_full_denominator` | 2 | 76.855 | 30.742 |
| **새 채점, `pct`** | **4** | **90.83** | **72.664** |
| 새 채점, `pct_full_denominator` | 4 | 90.83 | 72.664 |

- "판정 받은 과제만"은 step 8의 `avg_score_pct` 규칙입니다(오류가 없는 과제의 평균).
  채점 파일 요약에는 두 자리로 반올림되어 옛 83.66 / 76.86, 새 90.83 / 90.83으로
  실려 있습니다.
- "다섯 과제 고정"은 판정을 못 받은 과제를 0점으로 넣은 평균입니다.
- 새 채점에서는 두 분모가 같습니다. 채점에서 빠진 항목(`score_excluded_items`)이
  0개이기 때문입니다. 옛 채점에서는 3baa0009의 시각 항목 9개(배점 11)가 빠져 있었습니다.
- 판정 받은 과제만의 평균은 분모가 2에서 4로 바뀌었으므로 83.665와 90.83을 같은
  양의 변화로 읽으면 안 됩니다. 다섯 과제 고정 평균이 같은 분모끼리의 비교입니다.

### 옛 범위 대신 잰 값입니다

옛 채점만으로는 다섯 과제 고정 평균을 **[33.47, 73.47]** 사이라고밖에 말할 수
없었습니다. 거절된 두 과제가 0점에서 100점 사이 어디든 받을 수 있고(33.466 +
2 × 100 / 5 = 73.466), 나머지 셋은 그대로라고 두었을 때의 범위입니다. 이제
그 자리에 **잰 값 72.664**를 씁니다. 범위의 위쪽 끝에 가깝지만, 범위가 가정한 것과
달리 나머지 셋 중 둘(2ea2e5b5, 3baa0009)의 점수도 바뀌었으므로 "범위 안에 들었다"를
검증된 예측으로 읽지는 마세요.

## 과제별 — 전과 후

| 과제 | 항목 | 전: 상태 / 규칙 | 전 `pct` (전체 분모) | 후: 규칙, 주 대상 | 후 `pct` (전체 분모) |
|---|--:|---|--:|---|--:|
| 02aa1805 | 71 | `selection_error` / `ambiguous_candidates`, 71개 항목 미판정 | 0 | `set_diff_then_separate_primaries`: `Email_to_Manager_Well_Recommendations.eml`, `Illinois_Green_Hydrogen_Well_Screening.xlsx` | **94.13** (94.13) |
| 0112fc9b | 55 | `selection_error` / `format_variant_no_match`, 55개 항목 미판정 | 0 | `set_diff_single+rendition_copies`: `CS_SOAP_Note_2024-03-01.docx` | **98.18** (98.18) |
| 2ea2e5b5 | 60 | 판정 받음, `set_diff_then_primary_support_split` | 98.00 (98.00) | 같은 규칙, 같은 `.pptx` | 98.24 (98.24) |
| 3baa0009 | 49 | 판정 받음, `set_diff_then_separate_primaries`; 시각 항목 9개 제외 | 69.33 (55.71) | `set_diff_then_separate_primaries+requested_image`: `.py`, `.md`, `world_bank_global_growth_2024_2025_2027.jpg` | 72.77 (72.77) |
| 0818571f | 32 | `no_deliverables` / `set_diff_zero_guard` | 0 | 같음, 판정 호출 0 | 0 |

- 02aa1805와 0112fc9b는 옛 채점에서 판정자에게 한 번도 가지 않았습니다(판정 호출 0).
  이번에 각각 판정 호출 227번과 112번을 받았습니다.
- 3baa0009는 요청된 차트 이미지가 이제 주 대상으로 함께 채점됩니다. 빠졌던 시각
  항목 9개가 전부 판정을 받아(지각 호출 9) 배점 분모가 45에서 56이 됐습니다.
- **2ea2e5b5는 입력이 같은 유일한 과제입니다.** 선택도, 파일도, 채점기 판정 경로도
  같고 98.00이 98.24가 됐습니다(+0.24, 판정 호출 160 → 161). 같은 입력을 두 번
  판정한 관측 하나이지, 재채점의 효과가 아닙니다. 이 과제의 지각 호출 20번은 5장짜리
  `.pptx`의 첫 장을 시각 항목마다 한 번씩 본 것이고(`sampled_first_surface`, 5장 중
  1장), 슬라이드 20장을 본 것이 아닙니다.
- 0818571f는 바뀌지 않았습니다. 풀이 단계에서 콘텐츠 필터로 끝나 파일이 없고, 그
  0은 실제 실패로 남깁니다.

## 0점의 원인

| 원인 | 옛 채점 | 새 채점 | 과제 |
|---|--:|--:|---|
| 채점기 거절(`grader_refusal`) | 2 | **0** | 02aa1805, 0112fc9b |
| 콘텐츠 필터(`content_filter`) | 1 | 1 | 0818571f |

원인은 채점 행의 오류를 먼저 보고, 파일이 없으면 `self_report.json`의
`observability.error_category`를 봅니다. 0818571f의 값은 `content_filtered`입니다.
필터를 우회하거나 과제를 바꾸지 않았습니다.

## 비용 — 합산 USD 일지

`sol_batch_grading.py check-journal`과 일지의 `settle` 줄을 직접 더한 값이 같습니다.

| 항목 | 값 |
|---|--:|
| 이번 재채점(`run-42361049576-1.combined_usd.jsonl`) | **$21.88885250** |
| — 02aa1805 | $5.87966950 |
| — 0112fc9b | $4.24441900 |
| — 2ea2e5b5 | $8.41597800 |
| — 3baa0009 | $3.34878600 |
| 호출 | 629건, 전부 `gpt-5.6-sol`, 값이 비거나 미정산인 줄 0 |
| 재채점 시작 시 이미 잡혀 있던 금액 | $51.50751850 |
| — 풀이 | $38.78815600 |
| — 서술 예비 | $2.00000000 |
| — 첫 채점(`run-42039154052-1`, sha256 `3e4bffa2…986ba`) | $10.71936250 |
| **계보 전체 누적(닫는 줄 `committed_usd`)** | **$73.39637100 / 한도 $200** |

38.788156 + 2.00 + 10.7193625 + 21.8888525 = 73.396371로 닫는 줄과 맞습니다. 닫는 줄은
`step8_exit: 0`, 미정산 `pending_usd` 0입니다.

이 금액은 청구서가 아닙니다. 측정된 토큰에 Sol 목록 단가(`long_context_standard_global`)를
곱한 승인 장부이고, 캐시 쓰기는 상한(입력 − 캐시 입력)으로 잡습니다. 채점 파일의
`grading_cost`는 가격표가 `gpt-5.6-sol`을 일부러 가격 없이 두어
(`models_deliberately_not_priced`: 어느 미터가 적용되는지 정할 근거가 없음)
`price_missing`으로 남아 있습니다.

## 단서

- **Sol과 gpt-5.4를 나란히 놓으면 두 모델이 아니라 두 실행 설정을 비교하는 것입니다.**
  exp036은 `install_libreoffice: true`, `model_context_window: 1000000`,
  `reasoning_effort: "max"`로 풀었고(`experiments/exp036_sol_fixed5.yaml`), exp035는
  셋 다 지정하지 않고 `gpt-5.4`로 풀었습니다(`experiments/exp035_codex_foundry_full220.yaml`). 같은 다섯 과제 위의 두 값은 exp035 대조 기록
  [`exp035_parity_regrade_20261109.md`](exp035_parity_regrade_20261109.md)에 있습니다.
- **02aa1805의 94.13에서 깎인 점수는 대부분 빈칸 때문이고, 빠진 정수 계통은 점수에
  들어가지 않았습니다.** 이 과제가 잃은 점수는 86점 중 5.05점입니다(80.95 / 86).
  - `All Wells` 시트의 수식 셀 40개(`K7:N16`)가 계산된 값 없이 저장됐습니다. 채점기는 xlsx를
    `data_only=True`로 읽으므로(`core/tools/read_deliverable.py`) 판정자에게 그 칸은
    빈칸으로 보입니다. 평가 항목 16·17·18·38·55(배점 합 9)가 이 칸에 걸리고, 이번
    채점에서 16(0.5/2), 17(1/2), 18(0/2), 55(0.75/1)이 점수를 잃었고 38(2/2)은 다 받았습니다.
    잃은 5.05점 중 4.75점이 이 네 항목이고, 나머지 0.3점은 14번(Depth 열, 0.7/1)입니다.
    16·17·18번의 판정 근거에는 그 네 칸이 비어 있는 행이 그대로 인용돼 있습니다. 사람이 Excel로 열면
    값이 계산돼 보이므로 이 판정은 그보다 엄격하고, 어느 모델에게나 똑같이 적용됩니다.
  - Sol이 만든 통합 문서 스스로, 요청된 정수 계통 8곳 중 Springerton, Enfield, Crossville,
    Norris City 4곳이 복구본에 없었다고 적어 두었습니다(`All Wells` 시트 A4). 그러나 71개
    평가 항목 중 8곳이 다 들어 있는지 재는 항목은 없습니다. 19번은 첫 시트의 행이 "이
    계통들에만" 속하는지를 보는 항목이라 통과했고(1/1), 기대 후보 우물 7개를 시트와 이메일에서
    찾는 57–70번 14개도 전부 받았습니다. 그래서 빠진 4곳은 94.13에 반영되지 않았습니다.
  통합 문서 확인은 HF에서 받은 `deliverable_files/02aa1805…/Illinois_Green_Hydrogen_Well_Screening.xlsx`
  (@`8708d920`)를 `openpyxl`로 열어 했습니다.
- **보고하는 값은 잰 값입니다.** 옛 [33.47, 73.47] 범위를 더 이상 인용하지 않습니다.
- **렌더러가 같지 않은 비교가 있습니다.** 이 기록의 두 채점은 렌더러가 같습니다
  (PyMuPDF `2.1`). 하지만 exp035 발행 채점은 PyMuPDF `1.28.2`로 렌더링했습니다.
  PyMuPDF는 고정돼 있지 않고(`requirements-renderer.txt: PyMuPDF>=1.21.0`) 채점기 지문도
  그 버전을 덮지 않으므로, Sol과 gpt-5.4의 비교에는 렌더러 차이도 섞여 있습니다.

## 대시보드

- 새 채점은 최상위 `data/grades/`에 있고 `run_status: final`이며 exp036의 다섯 과제를
  전부 덮으므로 카드로 실립니다.
- 옛 채점은 지우지도 옮기지도 않았습니다. `src/lib/officialExperimentScope.js`의
  `SUPERSEDED_GRADE_IDS`에 id를 넣어 기본 화면에서만 내렸습니다. `?debug=1`로 다시 보이고,
  파일과 자기 페이지는 그대로입니다. 두 id는 `__src_<hex>__`만 다릅니다
  (`scripts/__tests__/official-filter.test.mjs`).

## 이 문서가 주장하지 않는 것

- 72.664가 Sol의 실력을 말한다고 주장하지 않습니다. 과제 다섯 개, 판정 한 번씩이고,
  위 설정 차이가 그대로 들어 있습니다.
- 2ea2e5b5의 +0.24 하나로 판정자의 흔들림 크기를 말하지 않습니다. 관측 한 개입니다.
- 위 금액은 Azure 청구서가 아닙니다.
- 02aa1805가 빈칸 문제 없이 몇 점이었을지 추정하지 않습니다.
