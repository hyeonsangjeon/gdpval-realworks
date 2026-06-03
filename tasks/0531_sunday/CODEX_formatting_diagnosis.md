# CODEX — formatting judge 후퇴 진단 (read-only, 배치 없음)

- **Repo:** `gdpval-realworks` (local, `main`)
- **왜 이게 우선:** critical item의 **32.5%(157/483)가 formatting**이다(modality_distribution.md). visual+audio(6%)의 5배 이상. 그리고 v2-mini의 critical 후퇴 3건이 *전부* formatting에서 났다(phase0_critical_modality.md). perception은 이걸 못 건드린다(formatting은 `inspect_formatting` 경로, perception sub-judge 밖). 즉 **benchmark 신뢰도의 실제 급소는 formatting 채점이고, 그게 왜 약한지는 한 번도 조사된 적 없다.**
- **목적:** formatting criterion 채점이 (1) v2-mini에서 왜 후퇴했는지, (2) 일반적으로 얼마나 신뢰할 만한지를 *기존 데이터+코드로* 진단. 결론을 내리는 게 아니라 **원인 가설을 evidence로 좁히는** 작업.

## 성공 기준
- "formatting 후퇴/약점의 원인 가설"을 코드·데이터 증거로 ranked list로 제시(추정 아님).
- self-graded avg 비교로 끝내지 말 것. formatting *판정의 정합성*(evidence가 실제 파일 속성과 맞는지)을 봐라.
- 결론 예단 금지. "formatting judge는 멀쩡한데 rubric이 모호한 것"일 가능성도 열어둬라.

## 권한/제약
- **read-only.** 코드·config·grade JSON 수정 금지. Azure run·full-220 run 금지(인증 불필요).
- 숫자는 raw에서 재계산. main push/머지 금지.

## PHASE A — formatting 후퇴 3건 해부 (v2-mini vs v1-mini)
phase0가 지목한 formatting critical 후퇴 3 item을 raw grade JSON에서 열어:
- 각 item의 criterion 텍스트, deliverable 종류(docx/xlsx/pptx/pdf 등), v1-mini와 v2-mini의 **verdict + score + evidence quote**를 나란히.
- 왜 갈렸나를 분류: (i) 같은 증거 다른 해석, (ii) v2-mini가 `inspect_formatting`으로 다른/부족한 증거를 봄, (iii) 한쪽이 증거 없이 판정, (iv) rubric 기준이 모호해 둘 다 정당.
- **산출 일부:** item별 비교표 + 후퇴 메커니즘 분류.

## PHASE B — formatting 채점 경로 코드 점검
- `grader_routing.py`에서 formatting으로 분류되는 키워드/조건 확인 — formatting 라우팅이 과대/과소 포착하는가(text인데 formatting으로, 또는 그 반대).
- `tool_calling_judge.py`의 `inspect_formatting` op이 **실제로 무엇을 반환**하는지 확인: 폰트/색/병합셀/스타일 등 어떤 속성을 judge에게 주는가, 아니면 빈약한 요약만 주는가. 반환이 빈약하면 그게 후퇴 원인일 수 있다.
- formatting criterion에 precheck(deterministic)이 적용되는 게 있나? `PRECHECK_PATTERNS` 확인.
- **산출 일부:** formatting 라우팅 정확도 + `inspect_formatting` 반환 내용의 충실도 평가(파일:라인).

## PHASE C — formatting 채점 신뢰도 (전체 157 critical 범위)
- 기존 full-220 grade JSON에서 **critical formatting 157 item**의 분포를 보라: pass/partial/fail 비율, evidence quote가 *실제로 formatting 속성을 인용*하는 비율 vs 일반적 텍스트만 인용하는 비율.
- evidence가 formatting 속성(폰트/표/스타일 등)을 인용 못 하는 item이 많으면 → formatting 채점이 구조적으로 약하다는 신호(text judge가 형식을 "본다고 하면서" 실제론 내용만 보는 것).
- **산출 일부:** formatting 채점 신뢰도 지표 + 약한 item 사례.

## 출력 — `tasks/0531_sunday/formatting_diagnosis.md` 하나
```
# FORMATTING JUDGE DIAGNOSIS
## 한 줄 결론
formatting 후퇴 주원인: [가설] / formatting 채점 전반 신뢰도: [높음/중간/낮음] / 다음 권고: [...]
## PHASE A — 후퇴 3건 해부 (비교표 + 메커니즘)
## PHASE B — 코드 경로 (라우팅 정확도 + inspect_formatting 충실도, 파일:라인)
## PHASE C — 157 critical formatting 신뢰도 (evidence validity)
## 원인 가설 (ranked, 각각 증거)
## owner 결정 필요 / 다음 트랙
```

## 제약 재확인
- read-only, Azure run 없음, push 없음.
- self-graded avg로 끝내지 말 것 — evidence validity가 핵심.
- 예단 금지(rubric 모호성 가능성 포함).
- `inspect_formatting` 반환·라우팅은 코드로 *증명*, 추정 금지.
