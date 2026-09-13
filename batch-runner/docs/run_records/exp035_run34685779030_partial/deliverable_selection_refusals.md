# 파일을 못 고른 8문제 — **왜** 못 고르는지 갈랐습니다

이 폴더의 `report.md`는 exp035에서 채점기가 최종 파일을 못 고른 8문제를
표로 적어 두었습니다. 그 표는 **무슨 일이 있었는지**까지이고, **왜**는 비어
있습니다. 이 문서가 그 자리를 채웁니다.

모델을 한 번도 부르지 않았고 채점을 다시 돌리지 않았습니다. 근거는 같은
폴더의 `deliverable_manifest.json`(파일 목록)과 고정된 rubric 스냅샷
`11e7900cdcac61bc4daf59e65feb238acda98fbf`, 그리고 오늘 저장소의
`core/deliverable_selector.py`입니다. 든 비용은 **$0**입니다.

**이건 세 번째 이야기입니다.** `failure_causes.md`는 파일을 아예 못 낸
70개(모델·환경 쪽)를 다루고, `baseline_selector_drift.md`는 비교 기준본이
옛 채점기에서 나왔다는 **시대차**를 다룹니다. 이 문서가 다루는 8개는
**파일을 냈는데 오늘 채점기가 그중 하나를 고르지 못한** 경우입니다.

---

## 어디서 멈추는가

채점기는 낸 파일을 판정자에게 넘기기 전에 "이 중 무엇이 최종 산출물인가"를
정합니다. 그 과정에 `format_variant`라는 갈래가 있습니다 — **같은 이름에
확장자만 다른 파일이 여럿이면** 같은 것을 여러 형식으로 낸 것으로 보고, 과제가
요구한 형식 하나를 고릅니다(`core/deliverable_selector.py:480`).

고를 수 없으면 그 자리에서 멈춥니다.

```python
primary_paths = _choose_format_variant(generated, required_exts, deliverable_summary)
if not primary_paths:
    return _selection_error(
        task_id, task_class, generated, reference_echo,
        "no requested format among format variants",
        "format_variant_no_match",
    )
```
`core/deliverable_selector.py:228-237`

멈추면 그 과제는 판정자에게 가지 않습니다. rubric 항목이 몇 개든 전부
채점되지 않습니다.

---

## 8개는 서로 다른 두 가지입니다

| 갈래 | n | rubric 항목 | 무슨 일 |
|---|---|---|---|
| **B** | **6** | **312** | 선택기가 "어떤 형식을 내라"는 요구를 **하나도 못 읽음** |
| **C** | **2** | **122** | 요구 형식을 읽었는데 **맞는 파일이 여럿**이라 하나로 못 좁힘 |
| 합 | 8 | 434 | |

### C 2개 — 맞는 파일이 여럿

| 과제 | 읽은 요구 | 낸 파일 | 그중 요구 형식 |
|---|---|---|---|
| `0e386e32` | `.zip` | 37개 | **2개** |
| `9a8c8e28` | `.pdf` | 7개 | **3개** |

`9a8c8e28`은 체크리스트·안내서·퀴즈 **세 가지**를 각각 PDF와 HTML로 냈습니다.
산출물이 애초에 셋인 과제라 "하나만 골라라"라는 틀이 맞지 않는 쪽입니다.
`0e386e32`은 37개 파일 중 `.zip`이 둘이고 PDF는 없습니다.

---

## B 6개 — **모델은 요구한 형식을 실제로 냈습니다**

이 갈래가 이 문서의 핵심입니다. 선택기가 요구 형식을 못 읽었는데,
**여섯 과제 모두 과제가 이름을 댄 형식의 파일을 실제로 냈습니다.**

| 과제 | 과제가 말한 형식 | 낸 파일 | 그중 그 형식 | 예 |
|---|---|---|---|---|
| `15d37511` | 스프레드시트 | 4개 | **1개** | `..._Revenue_Gross_Margin_P...` |
| `15ddd28d` | Word `.docx` | 2개 | **1개** | `Modlev_Tail_Lamp_Negotiation_Strategy.docx` |
| `1aecc095` | Word `.doc`/`.docx` | 4개 | **3개** | `MA Telehealth Workflow Email.docx` |
| `7de33b48` | zip 묶음 | 7개 | **1개** | `screen-reader-status-message.zip` |
| `aad21e4c` | Word | 4개 | **1개** | `NoxaPulse_Share_Subscription_Agreement.docx` |
| `cebf301e` | Word | 3개 | **1개** | `customer-portal-design.docx` |

**관측.** 모델이 형식을 안 지킨 것이 아니라, 채점기가 그 요구를 읽어내지
못했습니다.

---

## 왜 못 읽었는가 — 자리까지 나옵니다

요구 형식을 뽑는 곳은 `_required_primary_extensions`
(`core/deliverable_selector.py:453`)입니다. 이 함수는 지시문과 rubric 항목을
**전부 한 줄로 이어붙인 뒤**, 아래 모양으로만 찾습니다.

> **방아쇠 낱말** (`single` · `exactly one` · `final` · `primary` · `deliverable`)
> 이 나오고 **그 뒤에** 확장자가 나올 것

확장자는 앞에 공백이 있어야 인정됩니다(`_STANDALONE`,
`core/deliverable_selector.py:450`). 파일 이름에 붙은 확장자를 형식 요구로
오해하지 않으려고 PR #261이 넣은 조건입니다.

이 두 조건이 여섯 과제에서 각각 이렇게 빗나갑니다.

| 과제 | 본문 길이 | 확장자 글자 | 공백 앞에 있는 것 | 가장 이른 방아쇠 | 못 읽은 이유 |
|---|---|---|---|---|---|
| `1aecc095` | 7,166자 | `.docx` 2회 | 2회 (1263, 1338) | `exactly one` 1433 | **둘 다 방아쇠보다 앞** |
| `7de33b48` | 7,530자 | `.zip` 1회 | 1회 (3480) | `deliverable` 7519 | **방아쇠보다 앞** |
| `aad21e4c` | 12,613자 | `.docx` 1회 | 1회 (2572) | `deliverable` 12602 | **방아쇠보다 앞** |
| `15ddd28d` | 9,429자 | `.docx` 1회 | **0회** | `deliverable` 3875 | `(.docx)` — 괄호가 붙음 |
| `cebf301e` | 6,954자 | `.docx` 1회 | 1회 (4368) | **없음** | 방아쇠 낱말이 본문에 없음 |
| `15d37511` | 8,318자 | `.xlsx` **0회** | 0회 | `primary` 878 | 확장자를 안 쓰고 말로만 |

확장자 없이도 걸리는 대체 문구(`single word file`, `single workbook` 등)는
여섯 과제 어디에도 없었습니다.

본문에 실제로 적혀 있는 말은 이렇습니다.

- `aad21e4c` (2572자 자리) — *submission includes a word document file with a
  .docx extension*
- `cebf301e` (4368자 자리) — *provides the design document as a .docx
  microsoft word*
- `1aecc095` (1263자 자리) — *the file "telehealth workflow" is delivered in
  word format (.doc or .docx)*

**세 문장 모두 형식을 분명히 말합니다.** 걸리지 않은 것은 낱말의 **순서**와
**괄호** 때문입니다.

### 관측 / 가능한 설명 / 한계

- **관측** — 여섯 과제 중 다섯은 확장자 글자가 본문에 있고, 그중 넷은 공백
  조건까지 통과합니다. 걸리지 않은 것은 방아쇠와의 순서 또는 괄호 때문입니다.
  하나(`15d37511`)만 확장자 글자 자체가 없습니다.
- **가능한 설명** — 이 추출기는 한 줄로 접힌 긴 본문에서 앞뒤 순서를 가정하는데,
  지시문과 rubric을 이어붙이면 그 가정이 자주 깨집니다. rubric이 형식을
  말하고 방아쇠 낱말은 지시문 끝에만 있는 배치가 실제로 나옵니다.
- **한계** — **추출기를 고쳤을 때 이 여섯 개가 어떻게 되는지는 돌려보지
  않았습니다.** `1aecc095`는 `.docx`가 3개라 형식을 읽어냈더라도 다시 좁히지
  못했을 수 있습니다. 고친 코드로 재생한 결과가 없으므로 그 이상은 말하지
  않습니다.

---

## 이 가드는 한쪽에만 발동합니다

같은 220문제를, 오늘 코드로, 양쪽 회차에 돌렸습니다.

| | exp003 (비교 기준) | exp035 (Codex) |
|---|---|---|
| 파일을 낸 과제 | 219개 | 150개 |
| `format_variant_no_match` | **0개** | **8개** |
| 가드가 발동할 수 있는 상태인 과제 | 2개 (**0.9%**) | 29개 (**19.3%**) |
| 과제당 파일 수 중앙값 | 1개 | 3개 |
| 파일 2개 이상 낸 과제 | 79개 (36.1%) | 137개 (91.3%) |
| 한 과제 최대 파일 수 | 19개 | 37개 |

"발동할 수 있는 상태"는 `_looks_like_format_variant`
(`core/deliverable_selector.py:634`)가 참이 되는 경우 — 이미지가 아닌 파일
둘 이상이 **같은 이름에 다른 확장자**를 가진 경우입니다.

- **관측** — 이 갈래에 들어가는 비율이 exp003은 0.9%, exp035는 19.3%입니다.
  들어간 뒤 실패하는 것은 exp003 0/2, exp035 8/29입니다.
- **가능한 설명** — exp035의 하네스는 `.docx` 옆에 `.md`를, PDF 옆에 HTML을
  같이 내는 습관이 있습니다. 이 가드는 **같은 이름으로 여러 형식을 낸 쪽에만**
  걸릴 수 있는 구조입니다.
- **한계** — 과제 목록은 220개로 양쪽이 같으므로 과제 구성 차이는 아닙니다.
  다만 "하네스 습관 때문"이라고 갈라 재지는 않았습니다. 분모도 다릅니다
  (219 대 150).

**방향이 `baseline_selector_drift.md`와 반대입니다.** 선택기 시대차는
exp035 쪽에 **유리하게** 기울어 있었습니다(exp003의 비교값 `57.30`이 하한,
구간 `[57.30, 60.94]`). 이 가드는 exp035 쪽에 **불리하게** 기울어 있습니다.
최종 보고서는 두 축을 함께 적어야 합니다. 한쪽만 적으면 기울기가 한 방향으로만
보입니다.

---

## 뜻하지 않는 것

- **이 8개가 점수를 잘 받았으리라는 뜻이 아닙니다.** 판정자에게 가지 않았으니
  점수를 모릅니다. 갔더라도 낮았을 수 있습니다.
- **선택기를 고치지 않았습니다.** `core/`는 채점 조각이 도는 동안 해시가
  동결돼 있고, 회차 중간에 채점 규칙을 바꾸면 그 회차의 결과가 두 규칙에
  걸칩니다.
- **파일을 손으로 고르지 않았습니다.** 추론 결과도 건드리지 않았습니다.
  점수가 잘 나올 파일을 임의로 지정하는 것은 이 기록이 하지 않는 일입니다.
- **모델 실패가 아닙니다.** `failure_causes.md`가 다루는 70개와 겹치지
  않습니다. 이 8개는 전부 파일을 냈습니다.
- **시대차도 아닙니다.** 8개 전부 오늘 코드의 동작이고, PR #261 앞뒤에서
  달라지지 않습니다.

---

## 숫자를 어떻게 확인했나

- 파일 목록은 이 폴더의 `deliverable_manifest.json`(150과제)에서 읽었습니다.
- 과제 지시문과 rubric은 고정 스냅샷
  `11e7900cdcac61bc4daf59e65feb238acda98fbf`에서 읽었습니다. 채점 설정이
  고정한 것과 같은 개정입니다.
- 선택 결과는 채점기가 부르는 것과 같은 `select_deliverables`를 그대로 불러
  얻었습니다. 별도 구현을 쓰지 않았습니다.
- exp003 쪽 파일 목록은 커밋된 기준본 채점 결과
  `data/grades/*regrade_exp003_v2_sol_max*__src_595c7254caf8fbd7__v2.2.json`의
  `selected_deliverables`에서 복원했습니다. 복원한 결과를 오늘 코드로 돌리면
  `ok` 206 · `wrong_format_primary` 13 · 파일 없음 1 = **220**이 나오고,
  이는 `baseline_selector_drift.md`가 따로 기록한 오늘 시대 값과 같습니다.
  두 값이 서로 다른 경로에서 나왔으므로 이 일치가 대조입니다.
- rubric 항목 수 312 + 122 = **434**는 `report.md`의 8문제 표 합계와 같습니다.

읽은 것: `core/deliverable_selector.py`,
`docs/run_records/exp035_run34685779030_partial/deliverable_manifest.json`,
`report.md`, `baseline_selector_drift.md`,
`data/grades/*regrade_exp003_v2_sol_max*__src_595c7254caf8fbd7__v2.2.json`.
