# 거절은 닿지 않은 호출이 아니다 — 341 구현 기록

## 0. 메타

| | |
|---|---|
| 담당 | 세션 A |
| 날짜 | 2026-09-08 |
| 브랜치 | `fix/refusal-is-not-an-unreached-call` |
| 넘겨받은 진단 | B, `tasks/rebuilding_grading_task/341-what-a-refused-call-costs.md` (미게시) |
| 상위 명세 | `TASK_PER_TASK_COST_RECEIPTS.md` (같은 폴더) |
| 모델 호출 | **한 번도 없음.** 아래 숫자는 전부 로컬 가짜 클라이언트에서 나왔다 |

이 문서는 A가 쓴다. B의 미게시 문서는 인용만 하고 수정하지 않았다. B가 소유한
`core/perception/audio.py`, `tests/test_a_broken_audio_reply_still_costs_what_it_cost.py`,
`tasks/rebuilding_grading_task/**`, `CHANGELOG.md`는 **읽기만 했다.**

---

## 1. 한 줄 요약

**돈이 틀린 게 아니라 이유가 틀렸다.** 사업자가 `400`으로 거절한 호출을 원장이
"요청이 도달했는지 모름"으로 기록하고 있었다. 도달했는지는 그 호출에서 **유일하게
확실한 것**이다 — 상태 코드가 왔다는 게 도달했다는 증거다. 금액은 원래도 비워
두고 있었으므로 그대로 두고, 사실과 다른 그 한 줄만 고쳤다.

---

## 2. 원인 — 직접 확인한 것

`core/cost_metering.py`의 `MeteredClient._around`가 이랬다.

```python
object.__setattr__(self, "last_call_id", call_id)
response = call(**kwargs)          # ← try/except 가 없다
recorder.ledger.settle(call_id, usage=..., resolved_model=...)
```

`call(**kwargs)`가 예외를 던지면 `settle`에 도달하지 못한다. 요청 **전에** 써 둔
행이 `reserved`인 채로 남고, `build_receipt`는 그 행을
`call_reachability_unknown`으로 읽는다. 이건 설계된 안전장치다 — 예외 하나에
비용 기록이 통째로 사라지는 것보다 낫다. 다만 그 안전장치가 **모든** 실패에
같은 문장을 붙이는 게 문제였다.

B가 지적한 자리는 정확했다. B §2의 인용을 그대로 옮긴다.

> `core/cost_receipts.py:1353`의 `abandon`은 자기 조건을 이렇게 못 박는다.
> "Record that the call **never left** — so it never cost anything.
> Only correct where the failure is known to **precede the request**."
> `400`은 나갔다. 그러니 지금 문서대로라면 `abandon`도 쓸 수 없다.
> **빈 칸은 여기다 — "닿았고, 답장 받았고, 확실히 안 물렸다"를 뜻하는 상태가 없다.**

`core/perception/audio.py:246`은 이미 여덟 개 상태를 "과금 안 된 거절"로 알고
그에 맞게 행동한다(작업의 시도 횟수를 되돌려준다). 원장만 그 사실을 못 듣고 있었다.

### 2.1 돈을 잃는 문제는 아니다

`reserved` 행은 금액을 **주장하지 않는다.** `$0`이라고 쓰는 것보다 훨씬 안전한
쪽이다. 잘못된 건 사람이 읽고 **행동하는** 라벨이다. `call_reachability_unknown`은
"물렸는지 가서 확인하라"는 신호인데, 속도 제한에 50번 튕기면 확실히 공짜인 50개의
확인 요청이 만들어지고, 진짜로 모르는 것(5xx, 타임아웃)이 그 더미에 묻힌다.

B §3의 판단과 같다. 아직 실제로 발생하지는 않았다 — 337 실행 로그에 429·5xx·
타임아웃이 없었다.

---

## 3. B의 제안 중 채택하지 않은 부분과 그 이유

B §5.2는 `abandon`의 조건을 넓혀 `ledger.abandon(call_id, note=f"provider_{status}")`로
쓰자고 제안했다. **이건 쓰면 안 된다.**

`build_receipt`는 `abandoned` 행을 **통째로 건너뛴다**(`build_receipt` 안의
`if state == STATE_ABANDONED: continue`). 그러므로 `400`이 `abandoned`가 되면:

- 그 작업의 `model_calls`가 **1 줄어든다** — 사업자 쪽에 기록이 남아 있는 호출을
  두고 "호출이 없었다"고 말하게 된다
- 그 작업의 유일한 호출이었다면 영수증이 **`complete` + `$0`**이 된다

두 번째가 결정적이다. 이번 지시가 명시적으로 금지한 것이다:

> HTTP 400이라는 이유만으로 비용 0/complete를 만들면 안 됩니다.

그리고 상위 명세 P1과도 정면으로 충돌한다 — 진짜 `$0`은 "모델을 한 번도 부르지
않은 규칙 기반 경로" 하나뿐이다. **모델이 안 돌았다는 것은 계정에 아무것도 안
물렸다는 사업자의 진술이 아니다.**

B도 이 지점을 열어 두었다(B §7): "`abandoned` 재사용이냐 새 상태 `refused`냐 …
**둘 중 하나를 이 문서가 고르지 않는다**." A가 골랐다: **새 상태.**

---

## 4. 채택한 설계 — 세 번째 상태

`STATE_REFUSED = "refused"` + `REASON_CALL_REFUSED_UNPRICED = "call_refused_unpriced"`.

거절된 행은:

| | |
|---|---|
| 호출로 **센다** | 요청이 실제로 나갔으니까 (`model_calls += 1`) |
| 금액을 **주장하지 않는다** | 사업자가 사용량을 보고하지 않았으니까 |
| 영수증을 **`partial`로 유지한다** | 안 물렸다는 근거가 없으니까 |

**도달했다는 사실**(이제 확정)과 **과금 여부**(여전히 불명)를 갈라놓는 게 요점이다.
`reserved`는 둘 다 모른다고 말하고, `abandoned`는 둘 다 안다고 말한다. 거절은 그
중간이고, 그 중간을 표현할 자리가 없었던 것이다.

### 4.1 다섯 가지 끝맺음

지시가 요구한 구분을 그대로 옮긴 매핑이다.

| 상황 | 상태 | 이유 | note |
|---|---|---|---|
| 확인 가능한 HTTP 거절 (8개 상태) | `refused` | `call_refused_unpriced` | `provider_refused_{status}` |
| 보내기 전 실패 | `abandoned` | (없음, 영수증에서 제외) | 호출자가 준다 |
| 전송 여부 불명 | `reserved` | `call_reachability_unknown` | `provider_error_<클래스명>` |
| 응답은 있지만 usage 없음 | `settled` | `usage_absent` | — |
| 타임아웃 | `reserved` | `call_reachability_unknown` | `provider_timeout` |

여덟 개 상태는 `400, 401, 403, 404, 413, 415, 422, 429`이며 `audio.py`의
`_UNBILLED_STATUS`와 같은 집합이다. 두 벌을 두지 않기 위해 테스트가 둘의 동일성을
검사한다(B §5.3의 취지와 같되, B의 파일은 고치지 않고 A쪽에서 검사만 한다).

**5xx는 일부러 건드리지 않았다.** 게이트웨이가 모델에 닿기 전에 끊은 것인지,
모델이 돌고 나서 전달에 실패한 것인지 이 층에서는 알 수 없다. 그대로 `reserved`이며
`provider_status_500` 같은 note만 새로 붙는다. B의 경계 조건과 같다: "`[broke]`(5xx)는
그대로 통과해야 하고, 통과하지 않으면 제안이 너무 넓게 잡은 것이다."

### 4.2 note에 사업자 문구를 넣지 않는다

note는 실패의 **모양**으로만 만든다 — 상태 숫자, 고정된 낱말, 예외 클래스 이름을
영숫자만 남겨 64자로 자른 것. `str(error)`는 절대 쓰지 않는다. 사업자 오류 메시지는
요청 URL을 그대로 인용하는 일이 흔하고 헤더를 인용할 수도 있는데, 원장은 디스크에
커밋되고 샤드 사이로 오간다. 진단 문자열 하나 얻자고 원장을 비밀이 흘러드는
자리로 만들 수는 없다.

측정으로 확인했다(§6의 `test_a_note_never_carries_the_providers_own_words`):
URL과 키 모양 문자열을 담은 메시지로 `400`·타임아웃·일반 예외를 각각 일으킨 뒤
기록된 행 전체를 JSON으로 덤프해 둘 중 어느 것도 남지 않는 것을 확인한다.

### 4.3 마이그레이션이 필요 없다

`cost_calls.state`는 `TEXT NOT NULL`이고 CHECK 제약이 없다. 새 값은 지금까지
나타난 적 없는 문자열일 뿐이다. 341 이전에 쓰인 원장 파일은 전부
`reserved`/`settled`/`abandoned`만 담고 있고, 각각 예전과 같은 뜻으로 읽힌다.
이것도 테스트로 고정했다.

---

## 5. 바꾼 파일

| 파일 | 무엇을 | 채점기 지문에 들어가나 |
|---|---|---|
| `core/cost_metering.py` | `try/except` 추가, `classify_call_failure`, `_record_failed_call` | **예** |
| `core/cost_receipts.py` | `STATE_REFUSED`, `REASON_CALL_REFUSED_UNPRICED`, `refuse()`, `leave_unresolved()`, 병합·모순 가드 | **예** |
| `schemas/grade.schema.json` | `costMissingReason` enum에 값 1개 추가 | **예** |
| `scripts/verify_cost_ledger.py` | `reserved`만 미정산으로 보고하도록 좁힘 | 아니오 |
| `tests/test_a_refusal_is_not_an_unreached_call.py` | 신규 (69개) | 아니오 |
| `TASK_PER_TASK_COST_RECEIPTS.md` | §3.4 행 1개, §5.3 정정 주석, §6.2 `refuse` 추가 | 아니오 |

`_record_failed_call`은 원장 쓰기가 실패해도 **사업자의 원래 예외를 가리지 않는다.**
기록에 실패하면 예약이 그대로 남는데, 그게 어차피 보수적인 해석이다.

`verify_cost_ledger.py`를 같이 고친 이유: 기존 코드가 `state != settled`를 전부
"보냈는데 답장 기록이 없다"로 보고했다. 그대로 두면 거절 행마다 가짜 경보가
뜨고 **진짜 미정산 행이 그 안에 묻힌다** — 원장 한 층 위에서 똑같은 실수를 하는
셈이고, `call_refused_unpriced`가 막으려는 게 바로 그거다.

---

## 6. 검증 — 실제로 돌린 것

### 6.1 새 테스트가 고치기 **전에는 실패하는가**

양쪽으로 초록이면 아무것도 증명하지 못하므로, `try/except`만 원래대로 되돌려
같은 파일을 돌렸다.

| | |
|---|---|
| 고친 뒤 | **69 passed** |
| `try/except`를 되돌린 뒤 | **21 failed, 48 passed** |

실패한 21개에 여덟 개 상태 전부가 들어 있다. (되돌린 파일은 즉시 복원했고
`git diff --stat`으로 확인했다.)

### 6.2 회귀

| 묶음 | 결과 |
|---|---|
| cost·receipt·audio·perception·meter 관련 37개 파일 | **1,377 passed / 2 skipped** (변경 전과 동일) |
| 위 + 신규 파일 | **1,446 passed / 2 skipped** |
| 백엔드 전체 (신규 파일 제외, 소스 변경 적용) | **8,834 passed / 15 skipped / 45 deselected / 0 failed** |
| 게시된 채점 기록 95개를 **새 스키마로** 검증 | **95 pass / 0 fail** |

### 6.3 B의 "1,671개 중 1개"를 직접 확인했다

지시대로 B의 수치를 그대로 믿지 않고 재어 봤다.

**결론: 실질적으로 맞다.** B의 미게시 테스트 파일(14개)을 A 트리에 임시로 복사해
돌린 결과 **정확히 1개**가 실패하고, 그게 B가 지목한 바로 그 줄이다.

```
FAILED test_a_refused_request_is_recorded_as_unknown_not_as_free[refused]
  assert rows[0]["state"] == "reserved"
  AssertionError: assert 'refused' == 'reserved'
```

같은 테스트의 `[broke]`(5xx) 갈래는 **통과했다** — B가 제시한 경계 조건이 실제로
지켜졌다는 뜻이다. (복사본은 즉시 삭제했고 `git status`로 확인했다.)

**다만 분모 1,671은 그대로 재현되지 않는다.** B가 정확한 명령을 적어 두지 않았고,
A의 37개 파일 선택은 1,379개, `-k "cost or receipt or audio or perception or meter"`는
1,662개(B의 미게시 파일을 더하면 1,676개)를 모은다. 분모는 선택 방식에 따라
달라지는 값이고, 의미 있는 숫자는 §6.2의 전체 스위트 쪽이다. **분자 1은 맞다.**

---

## 7. 하류 영향 — 기록해 둔다

### 7.1 채점기 지문이 움직인다

`core/**`와 `schemas/grade.schema.json`이 지문 입력이므로 이 변경은 지문을 바꾼다.
저장소 자신의 검사기로 확인했다.

| | |
|---|---|
| 변경 전 (`origin/main` `0167131`) | `50f6f8bbc7d50b3d8ea8d733f91b673890c2aff4449dbbf8f8688d78b3132f15` |
| 변경 후 | `ee1ca0b0948840f01786ad8f9340476600073c82843c1abcaf8302580391ec31` |

`check_grader_hash_freeze.py`는 **PASS**다 — 지금 진행 중인 유료 채점 실행이
없다(비완료 `grade-run` 0건). 다만 검사기가 스스로 남기는 경고가 그대로 적용된다:

> This diff does move the grader source hash. … it means the next paid run has to
> be preceded by a fresh smoke at the new fingerprint.

**다음 유료 채점 실행 전에 `ee1ca0b0…`에서 새 스모크가 필요하다.** 그리고 샤드가
떠 있는 동안에는 이 변경을 병합하면 안 된다.

`scripts/`는 지문 입력이 아니므로 `verify_cost_ledger.py` 수정은 지문에 영향이 없다.

### 7.2 B의 미게시 테스트 한 줄

B의 `test_a_broken_audio_reply_still_costs_what_it_cost.py`가 `[refused]` 갈래에서
`state == "reserved"`를 못 박아 두었다. 이 변경이 `"refused"`로 바꾼다. B의 문서도
같은 결론을 적어 두었다("**그 한 줄은 고쳐야 하는 게 맞다** — 그게 이 변경의
내용이니까"). **A는 B의 파일을 고치지 않았다.** B가 게시할 때 그 한 줄을 함께
고쳐야 하며, 두 변경이 어느 순서로 들어가든 한쪽은 상대를 기다린다.

또한 B의 §5 제안 diff는 `state == "abandoned"`를 기대하는데, A는 `"refused"`를
쓴다. 이유는 §3이다.

### 7.3 명세 문서의 한 문장이 틀렸다

`TASK_PER_TASK_COST_RECEIPTS.md` §5.3이 이렇게 적어 두었다.

> 아홉 번째 값을 더하면 이미 게시된 채점 산출물이 스키마 검증에 걸린다.

**측정해 보니 아니다.** `enum`에 값을 더하는 것은 **넓히는** 변경이고, 게시본은
옛 8개만 담고 있으므로 전부 통과한다. 게시된 채점 기록 95개 전부가 새 스키마에
통과했고, 실제로 쓰인 값은 `price_missing`과 `call_reachability_unknown` 둘뿐이었다.
깨지는 것은 값을 **빼거나 이름을 바꿀 때**다.

원문은 지우지 않고 날짜 붙은 정정 주석을 아래에 덧붙였다. 그 절이 다룬 소리 가격
상황에 새 값이 필요 없었다는 판단 자체는 그대로 옳다.

### 7.4 새로 막은 구멍

`MISSING_REASONS`(파이썬)와 `grade.schema.json`의 닫힌 enum이 **어긋나도 아무것도
빨개지지 않았다.** 유료 실행이 끝나는 시점에 채점 기록이 검증에 걸려서야 드러날
종류의 구멍이다. 두 목록의 동일성을 검사하는 테스트를 넣었다.

### 7.5 스키마 버전은 올리지 않았다

`schema_version` enum은 `["1.0" … "1.4"]` 그대로다. 값을 더하는 변경은 옛 기록의
유효성을 바꾸지 않으므로 새 버전을 요구하지 않는다. 다만 이 판단은
`1.4`를 선언한 기록이 이제 두 가지 스키마(값 8개짜리와 9개짜리) 중 어느 쪽으로도
검증된다는 뜻이기도 하다. 값을 **빼는** 변경이 나오면 그때는 버전을 올려야 한다.

---

## 8. 이 문서가 하지 않은 것 / 승인 없이는 못 하는 것

| | |
|---|---|
| 모델 호출 | 한 번도 안 했다 |
| B 소유 파일 수정 | 안 했다. `audio.py`·B의 테스트·`tasks/rebuilding_grading_task/**`·`CHANGELOG.md` 전부 읽기만 |
| 가격표 수정 | 안 했다. 추정 요율도 넣지 않았다 |
| 실행된 사전등록·과거 산출물 덮어쓰기 | 안 했다. §5.3은 원문을 두고 주석만 덧붙였다 |
| 5xx·타임아웃·SDK 내부 재시도 | 안 고쳤다. B §7의 한계가 그대로 남는다 |
| `429`를 여덟 개에 계속 둘 것인가 | 이 변경은 `audio.py`의 판단을 그대로 따른다. 재시도 판단과 과금 판단이 같은 목록을 봐야 하는지는 별개 질문이고 여기서 정하지 않았다 |
| **push · PR 생성 · 병합 · main 변경** | **안 했다. 별도 승인이 필요하다** |
| **새 지문에서의 스모크 실행** | **유료 경로다. 별도 승인이 필요하다** |

---

## 9. 이어받는 사람에게

로컬 브랜치 `fix/refusal-is-not-an-unreached-call`에 커밋까지 되어 있고 push는
안 했다. 열려 있는 PR은 #457 하나뿐이며 그 위에 쌓지 않았다.

병합 전에 확인할 것 두 가지:

1. **유료 채점 샤드가 떠 있지 않은지** — 떠 있으면 병합하면 안 된다.
   `check_grader_hash_freeze.py`가 그 판단을 대신해 준다
2. **B의 `[refused]` 한 줄** — 두 변경 중 늦게 들어가는 쪽이 상대를 기다린다
