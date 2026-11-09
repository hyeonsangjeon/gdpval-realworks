# exp035 — 선택이 바뀐 8개 과제만 다시 채점한 대조 결과

선택기 수정(#801) 뒤 exp035(gpt-5.4) 220개 과제 중 **판정자에게 보이는 것이 달라진
8개 과제(평가 항목 424개)**만 같은 Sol Max 채점자로 다시 채점했습니다. 결과는 진단
폴더에 있고, **발행된 exp035 채점은 그대로 둡니다.** 이 문서는 두 채점을 합쳐 본
"대조용 보기"를 실행 기록으로 따로 남기는 것입니다. 수치는 전부 커밋된 파일에서 다시
계산했고, 이 기록을 만들면서 모델을 부르지 않았습니다.

- 발행 채점: `data/grades/exp035_codex_foundry_full220__…__src_fd0db9d9d78d6d54__v2.2.json`
  (sha256 `a7cd9b348028dfd0…`, 2026-09-12T20:34:50Z, `run_status: final`, 220개)
- 대조 재채점: `data/grades/_diagnostic/b2ed7212…4851/exp035_codex_foundry_full220__judge_gpt-5_6-sol__e35par__cfg_947381242d273196__…__src_02cbcf3824bd89a2__v2.2.json`
  (sha256 `87d42eb58724e2cd…`, 2026-11-09T09:54:39Z, `run_status: diagnostic`, 8개 중 8개)
- 실행: [42560225887](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/42560225887),
  `main` `567f9b3f`(#801 머지 커밋)에서 돌았습니다. 봇 커밋 셋:
  `d870c18c`(합산 USD 일지), `7dd25183`(채점 파일과 원장), `8d9c4c24`(자동 분석)
- 범위: [`exp035_parity_selection_20261106.json`](exp035_parity_selection_20261106.json)의
  `ordered_task_ids` 8개, sha256 `b2ed72124660d52d…4851`. 그 기록의 `grade_sha256`은 위
  발행 채점의 바이트와 같고, `selector_sha256`(`07222c6b…574d`)은 지금
  `core/deliverable_selector.py`의 sha256과 같습니다.
- 기계가 읽는 기록: [`exp035_parity_regrade_20261109.json`](exp035_parity_regrade_20261109.json)
  (`parity-regrade-record-v1`). 만든 명령:

```
cd batch-runner
python scripts/merge_parity_regrade.py \
  --published ../data/grades/<발행 채점>.json \
  --regrade ../data/grades/_diagnostic/b2ed7212…4851/<e35par 채점>.json \
  --selection-diff docs/run_records/exp035_parity_selection_20261106.json \
  --self-report <HyeonSang/exp035_codex_foundry_full220 @dc36d683의 self_report.json> \
  --compare ../data/grades/<exp036 새 채점>.json \
  --json-out docs/run_records/exp035_parity_regrade_20261109.json
```

`self_report.json`은 인증 없이 `dc36d6837a8f0899f8bfa4d32aae9a9f6805f3b0` 개정판에서
받았습니다(220행, sha256 `5642abc1…0996`). 도구는 실험·추론 개정판·판정자·프롬프트·
루브릭이 같은지, 재채점이 자기 범위를 다 채웠는지, 범위가 선택 비교 기록과 같은지를
확인한 뒤에만 기록을 씁니다. 이번에 거절 없이 통과했습니다.

## 점수 — 분모 둘, 범위 둘

| 보기 | 판정 받은 과제 | 판정 받은 과제만 평균 | 220 고정 평균 | 전체 분모(판정만 / 220) |
|---|--:|--:|--:|--:|
| 발행 채점 | 142 | 81.0654 | 52.3240 | 80.7363 / 52.1116 |
| **대조용 합친 보기** | **148** | **81.0504** | **54.5248** | 80.8237 / 54.3723 |
| 차이 | +6 | −0.0150 | **+2.2008** | +0.0874 / +2.2607 |

- "판정 받은 과제만"은 step 8의 `avg_score_pct` 규칙(오류 없는 과제의 평균)이고,
  "220 고정"은 판정을 못 받은 과제를 0점으로 넣은 평균입니다
  ([`exp035_grading_coverage_220.md`](exp035_grading_coverage_220.md)의 규칙).
- 220 고정 평균이 2.20 오른 것은 새로 판정을 받은 6개(합 468.55점)와 3baa0009(+2.98),
  b1a79ce1(+12.64)을 220으로 나눈 값입니다(484.17 / 220 = 2.2008).
- 판정 받은 과제만의 평균은 거의 그대로입니다(−0.015). 분모가 142에서 148로
  바뀌었으므로 이 값의 변화를 품질 변화로 읽지 마세요.
- 재채점한 8개만의 평균은 77.5775입니다(채점 파일 요약 77.58). 8개 모두 채점에서 빠진
  항목이 0개입니다.

**이 합친 보기는 발행 점수가 아닙니다.** 행 212개는 발행 채점(`src_fd0db9d9d78d6d54`)에서,
행 8개는 재채점(`src_02cbcf3824bd89a2`)에서 왔습니다. 두 채점은 채점기 지문, 렌더러
(PyMuPDF `1.28.2` 대 `2.1`), 판정 표본이 다릅니다. 발행 채점을 만든 `93707428`과
재채점을 만든 `567f9b3f` 사이에 채점기 지문이 덮는 파일(`core/`의 `.py`, `step8_grade.py`,
스키마, requirements 두 개, 프롬프트 두 개, 내려받기 스크립트) 중 39개가 바뀌었고(그중 24개는
이름이 `agentic_v2_`나 `codex_`로 시작하는 풀이 쪽 모듈입니다), 채점 설정 파일도
다릅니다(발행 템플릿 대 `e35par.yaml`). 이 기록은 판정자에게 보이는 선택이 바뀐 과제만
골라 다시 매긴 것이고, 나머지 212개 행이 오늘 채점기로도 같은 점수일 것이라고 주장하지
않습니다. JSON의 `mixed_identity_caveat`이 같은 말을 합니다.

## 과제별 — 전과 후

| 과제 | 항목 | 전: 상태 / 규칙 | 전 `pct` (전체 분모) | 후: 규칙, 주 대상 | 후 `pct` | `critical_fail` |
|---|--:|---|--:|---|--:|---|
| 15d37511 | 56 | `selection_error` / `format_variant_no_match` | 0 | `set_diff_then_separate_primaries+rendition_copies`: `.xlsx`, `build_glongro_projection.py` | 65.76 | 예 |
| 15ddd28d | 46 | `selection_error` / `format_variant_no_match` | 0 | `set_diff_then_format_variant`: `.docx` | 76.96 | 아니오 |
| 1aecc095 | 52 | `selection_error` / `format_variant_no_match` | 0 | `set_diff_then_uniform_primaries+rendition_copies`: `.docx` 3개 | 77.64 | 예 |
| 3baa0009 | 49 | 판정 받음, `set_diff_then_separate_primaries`; 시각 항목 9개 제외 | 67.11 (53.93) | `set_diff_then_separate_primaries+requested_image`: `.py`, `.md`, `world_bank_global_growth_chart.jpg` | 70.09 | 아니오 |
| 9a8c8e28 | 67 | `selection_error` / `format_variant_no_match` | 0 | `set_diff_then_separate_primaries+rendition_copies`: `.pdf` 3개 | 58.70 | 예 |
| aad21e4c | 84 | `selection_error` / `format_variant_no_match` | 0 | `set_diff_then_separate_primaries+rendition_copies`: `.docx`, `.py`, `.txt` | 89.49 | 예 |
| b1a79ce1 | 35 | 판정 받음, `set_diff_then_primary_support_split`: `.py`만 | 69.34 (69.34) | `set_diff_then_primary_support_split+requested_image`: `generate_moodboard.py`, `music_video_moodboard.png` | 81.98 | 아니오 |
| cebf301e | 35 | `selection_error` / `format_variant_no_match` | 0 | `set_diff_then_separate_primaries+rendition_copies`: `.docx`, `.py` | 100.00 | 아니오 |

- 재채점 후의 `pct`와 `pct_full_denominator`는 8개 모두 같습니다(빠진 항목 0).
- 3baa0009는 요청된 차트 이미지가 주 대상으로 함께 채점되어 빠졌던 시각 항목 9개가 판정을
  받았습니다(지각 호출 9). b1a79ce1은 무드보드 PNG가 주 대상이 되어 지각 호출 28번을
  받았습니다. 전에는 그림 그리는 스크립트만 보고 판정했습니다.
- 8개 중 4개(15d37511, 1aecc095, 9a8c8e28, aad21e4c)에 `critical_fail`이 있습니다. 점수가
  생겼다는 것이 그 결과물을 쓸 수 있다는 뜻은 아닙니다.
- 재채점하지 않은 거절 2개(0e386e32, 7de33b48)는 선택 비교에서 전과 똑같이 거절되어
  범위에 들어가지 않았습니다. 코드 묶음 과제이고, 선택기가 일부러 거절하는 경우입니다.

## 0점의 원인

| 원인 | 발행 채점 | 합친 보기 | 내역 |
|---|--:|--:|---|
| 인프라(`infrastructure`) | 55 | 55 | `rate_limited` 41, `transport_error` 14 |
| 콘텐츠 필터(`content_filter`) | 9 | 9 | `content_filtered` |
| 원인 미분류(`unclassified_failure`) | 6 | 6 | `turn_failed` |
| 채점기 거절(`grader_refusal`) | 8 | **2** | 0e386e32, 7de33b48만 남음 |
| 합계 | 78 | 72 | |

풀이 쪽 원인은 `self_report.json`의 `observability.error_category`에서 읽었습니다.
`turn_failed`는 러너가 원인을 적지 못한 실패여서 모델 쪽으로도 인프라 쪽으로도 세지
않습니다. 예전 표기(`other_model_side`)를 쓰는 문서가 있으면 같은 6개입니다.

## 같은 다섯 과제 위의 Sol과 gpt-5.4

`--compare`로 exp036 새 채점(`src_6f8811acb9de0b81`)의 다섯 과제 위에 둘을 나란히
놓았습니다. gpt-5.4 쪽은 위의 합친 보기에서 그 다섯 행을 가져온 것입니다.

| 보기 | 판정 받은 과제 | 판정만 평균 | 5 고정 평균 | 전체 분모(판정만 / 5) |
|---|--:|--:|--:|--:|
| gpt-5.4, 합친 보기 | 3 | 88.02 | **52.812** | 87.54 / 52.524 |
| Sol(exp036 새 채점) | 4 | 90.83 | **72.664** | 90.83 / 72.664 |
| 참고: gpt-5.4, 발행 채점 | 3 | 87.0267 | 52.216 | 82.1533 / 49.292 |
| 참고: Sol, exp036 옛 채점 | 2 | 83.665 | 33.466 | 76.855 / 30.742 |

| 과제 | gpt-5.4 (합친 보기) | Sol |
|---|--:|--:|
| 02aa1805 | 0 — 콘텐츠 필터, 파일 없음 | 94.13 |
| 0112fc9b | 95.15 (전체 분모 93.71) | 98.18 |
| 2ea2e5b5 | 98.82 | 98.24 |
| 3baa0009 | 70.09 (재채점된 행) | 72.77 |
| 0818571f | 0 — 콘텐츠 필터, 파일 없음 | 0 — 콘텐츠 필터, 파일 없음 |

JSON의 `compare` 블록은 0점을 원인이 아니라 채점 행의 오류 그대로(`no_deliverables`)
적습니다. 위 표의 "콘텐츠 필터"는 두 실험의 `self_report.json`에서 직접 확인한 것입니다
(exp035는 02aa1805와 0818571f 둘 다, exp036은 0818571f가 `content_filtered`).

## 비용 — 합산 USD 일지

`sol_batch_grading.py check-journal`과 일지의 `settle` 줄을 직접 더한 값이 같습니다.

| 항목 | 값 |
|---|--:|
| 이 재채점(`run-42560225887-1.combined_usd.jsonl`) | **$57.50499500** |
| — 15d37511 | $5.20127600 |
| — 15ddd28d | $4.41110650 |
| — 1aecc095 | $4.52320100 |
| — 3baa0009 | $3.11861400 |
| — 9a8c8e28 | $9.80049150 |
| — aad21e4c | $21.83060650 |
| — b1a79ce1 | $5.55316550 |
| — cebf301e | $3.06653400 |
| 호출 | 1,017건, 전부 `gpt-5.6-sol`, 값이 비거나 미정산인 줄 0 |
| 시작 시 이미 잡혀 있던 금액 | $0 (풀이·서술 없음, 이 승인의 첫 일지) |
| 누적(닫는 줄 `committed_usd`) | **$57.50499500 / 한도 $200** |

한도는 `sol_batch_grading.EXP035_PARITY_CEILING_USD`(USD 200)이고, 같은 자리의 주석이
예상을 약 USD 62(p99 112)로 적어 두었습니다. 닫는 줄은 `step8_exit: 0`, 미정산 0입니다.
이 금액은 청구서가 아닙니다. 측정된 토큰에 Sol 목록 단가를 곱한 승인 장부이고, 캐시
쓰기는 상한으로 잡습니다. exp036의 $200 한도와는 따로 셉니다.

## 단서

- **Sol과 gpt-5.4의 비교는 두 모델이 아니라 두 실행 설정의 비교입니다.** exp036은
  `install_libreoffice: true`, `model_context_window: 1000000`, `reasoning_effort: "max"`로
  풀었고, exp035는 셋 다 지정하지 않았습니다. 과제도 다섯 개뿐이고 0818571f는 둘 다
  필터로 끝났습니다.
- **02aa1805의 Sol 점수에는 Sol 통합 문서의 한계와 채점기 읽기 방식이 같이 들어 있습니다.**
  요청된 정수 계통 8곳 중 4곳이 복구되지 않았다고 문서 스스로 적었고, 수식 셀 40개
  (`K7:N16`)가 계산된 값 없이 저장돼 판정자에게 빈칸으로 보였습니다(`data_only=True`).
  자세한 내용은 [`exp036_sol_fixed5_regrade_20261109.md`](exp036_sol_fixed5_regrade_20261109.md)에
  있습니다. gpt-5.4는 이 과제에서 파일을 내지 못했습니다.
- **잰 값이 옛 범위를 대신합니다.** exp036 옛 채점만으로는 Sol의 5 고정 평균을 [33.47, 73.47]
  범위로만 말할 수 있었고, 이제 72.664를 씁니다.
- **렌더러가 다릅니다.** 발행 exp035 채점은 PyMuPDF `1.28.2`, 재채점과 exp036은 `2.1`로
  렌더링했습니다. PyMuPDF는 고정돼 있지 않고(`requirements-renderer.txt: PyMuPDF>=1.21.0`)
  채점기 지문도 그 버전을 덮지 않습니다. 그래서 합친 보기 안에도, Sol과 gpt-5.4 사이에도
  렌더러 차이가 섞여 있습니다.
- **금 기준 채점은 다시 매기지 않았습니다.** `gold_ceiling_185`
  (`_diagnostic/cef3a5b9…/…src_79c2f5035c4aa826…`)의 3baa0009 행은 이미지 승격 전 선택
  (`set_diff_then_primary_support_split`, 75.27)으로 매긴 것입니다.

## 대시보드

재채점 파일은 `_diagnostic/` 아래에 있고 `run_status: diagnostic`이라 집계기
(`scripts/aggregate-grades.mjs`)가 읽지 않습니다. 집계기는 최상위 `data/grades/*.json`만
읽습니다. **exp035 카드는 바뀌지 않습니다.**

## 이 문서가 주장하지 않는 것

- 54.5248은 exp035의 발행 점수가 아닙니다. 발행 점수는 여전히 52.32(220 고정)와
  81.07(판정만)입니다.
- 나머지 212개 행이 오늘 채점기로도 같은 점수라고 주장하지 않습니다.
- 52.812와 72.664의 차이가 모델 차이라고 주장하지 않습니다.
- 위 금액은 Azure 청구서가 아닙니다.
