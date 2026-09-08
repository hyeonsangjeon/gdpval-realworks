# 341 — 거절당한 호출은 얼마인가

**상태: 제안이 받아들여졌다.** 아래 §1~§8은 제안하던 당시 그대로 두고,
실제로 무엇이 들어갔는지는 **§9**에 적는다. §7의 "안 정한 것" 중 하나가
정해졌으니, 그 결과를 §7 위에 덮어쓰지 않고 뒤에 붙이는 게 맞다.

**한 문장으로:** 제공자가 `400`으로 **거절한** 요청을, 영수증은 *"API에 닿았는지
모르겠다"*고 적는다. 닿았다. 답장이 왔고, 그 답장이 거절이었다. 금액은 맞고
**이유가 틀렸다.**

이 문서는 **고치지 않는다.** 고칠 자리가 공용 계측 코드(`core/cost_metering.py`)라
이 갈래의 소유가 아니다. 대신 **실패하는 테스트**와 **제안 diff**를 두고, 그
제안이 기존 테스트를 얼마나 건드리는지까지 재서 남긴다.

---

## 1. 무엇을 봤나

`core/perception/audio.py:246`이 여덟 개의 상태 코드를 **"과금되지 않았다"**로
분류한다.

```python
_UNBILLED_STATUS = frozenset({400, 401, 403, 404, 413, 415, 422, 429})
```

바로 위 주석이 왜인지 적어 놨다 — 모델이 돌기 **전에** 거절당했으므로 안 물렸고,
그래서 이 여덟 개만 호출 칸을 돌려준다는 것이다. 어댑터는 이 사실을 **알고
행동한다.**

**그런데 원장은 그 사실을 전달받지 못한다.**

`core/cost_metering.py:754`의 `MeteredClient._around`는 이렇게 생겼다.

```python
recorder.ledger.reserve(..., request_sha256=request_digest_of(kwargs))
object.__setattr__(self, "last_call_id", call_id)
response = call(**kwargs)          # <- try/except 가 없다
recorder.ledger.settle(call_id, usage=..., resolved_model=...)
```

`call(**kwargs)`가 예외를 던지면 `settle`까지 못 간다. 예약 행이 `reserved`인
채로 남고, 영수증은 `call_reachability_unknown`을 단다.

---

## 2. 왜 그게 틀린 말인가

명세가 그 이유를 정의해 놨다. `TASK_PER_TASK_COST_RECEIPTS.md` §6.2:

> 정산되지 않은 예약 행은 사라지지 않고 `call_reachability_unknown`으로 남아 그
> 작업 영수증을 `partial`로 만든다. 이것이 **"API 도달 여부 불명확"**의 처리다.

`400`은 **상태 코드**다. 상태 코드는 **답장**이다. 요청이 제공자에게 닿았기
때문에 받은 것이고, 그 답장이 *"모델을 돌리기 전에 거절했다"*는 내용이다.

**여기서 불명확하지 않은 유일한 것이 바로 도달 여부다.**

| | `500`·타임아웃·끊긴 연결 | `400`·`429` 같은 여덟 개 |
|---|---|---|
| 닿았나 | **모른다** | **닿았다** (답장이 왔다) |
| 물렸나 | **모른다** | **안 물렸다** (모델이 안 돌았다) |
| 지금 영수증 | `call_reachability_unknown` | `call_reachability_unknown` |
| 맞나 | ✅ 정확하다 | ❌ **둘 다 아는데 모른다고 적는다** |

### `abandon`도 지금 그대로는 답이 아니다

`core/cost_receipts.py:1353`의 `abandon`은 자기 조건을 이렇게 못 박는다.

> Record that the call **never left** — so it never cost anything.
> Only correct where the failure is known to **precede the request**.

`400`은 나갔다. 그러니 지금 문서대로라면 `abandon`도 쓸 수 없다.

**빈 칸은 여기다 — "닿았고, 답장 받았고, 확실히 안 물렸다"를 뜻하는 상태가
없다.**

---

## 3. 이게 돈을 잃는 문제인가 — **아니다**

먼저 분명히 해 둔다. **지금 동작이 위험한 쪽으로 틀린 게 아니다.**

`reserved`로 남으면 영수증은 금액을 **주장하지 않는다**. 모르는 것을 `$0`이라고
적는 것보다 훨씬 안전하다. `_UNBILLED_STATUS`의 주석도 같은 비대칭을 말한다 —
*"호출을 더 세면 문항 하나를 잃고, 덜 세면 원장이 영영 모르는 돈이 생긴다."*

**틀린 것은 금액이 아니라 이유표다.** 그리고 그게 왜 문제냐면:

`call_reachability_unknown`은 사람이 **"물렸을 수도 있는데 확인이 안 된다"**로
읽으라고 만든 신호다. 조사를 시작하라는 뜻이다. 그런데 요금 한도(`429`)에 50번
막힌 실행은 **50개의 거짓 신호**를 만든다. 전부 공짜인 게 확실한 반송인데
전부 "확인 필요"로 찍힌다. 그러면 그 옆에 섞인 **진짜 모르는 것**(5xx·타임아웃)이
안 보인다.

> **아직 안 일어난 일이다.** `339` §9가 적었듯 `337` 실행 로그에는 `429`·5xx·
> 타임아웃 흔적이 없었다. 여기서 말하는 건 *"이렇게 되면 이렇게 된다"*이지
> *"이렇게 됐다"*가 아니다.

---

## 4. 실패하는 테스트

아래 그대로 오늘 돌리면 **여덟 개가 다 실패한다.**

```python
@pytest.mark.parametrize("status", [400, 401, 403, 404, 413, 415, 422, 429])
def test_a_provider_refusal_is_not_recorded_as_a_call_that_might_have_run(
    tmp_path, wav_file, status
):
    """A status is an answer, so reachability is not what is unknown here."""
    ...
    client = _Client(_Refused(status))
    with CostReceiptLedger(..., price_table=load_receipt_price_table(prices)) as ledger:
        recorder = CostRecorder(ledger)
        grader = Grader(document, rubric_loader=None, client=client,
                        cost_recorder=recorder)
        with recorder.attributed(task_id="task-a", stage=STAGE_GRADING):
            grader._tool_judge.audio_perception.judge(
                criterion="the narration is audible", audio_path=str(wav_file))
        receipt = recorder.receipt_for("task-a", BUCKET_GRADING)
        rows = ledger.calls_for("task-a")

    assert len(client.calls) == 1, "the request did go out"
    assert rows[0]["state"] == "abandoned", (
        f"a {status} left the row {rows[0]['state']!r}: the provider answered, "
        "so this is not an unreached call"
    )
    assert REASON_CALL_REACHABILITY_UNKNOWN not in receipt.missing_reasons
    assert receipt.known_cost_usd == Decimal("0")
```

오늘의 출력:

```
E   AssertionError: a 429 left the row 'reserved': the provider answered,
E   so this is not an unreached call
E   assert 'reserved' == 'abandoned'
...
8 failed in 1.68s
```

전체 파일은 이 문서 옆에 두지 **않았다.** 통과할 수 없는 테스트를 검사 묶음에
넣으면 CI가 빨개지고, 그걸 `skip`이나 `xfail`로 덮으면 이 문서가 없는 것과
같아진다. **고칠 사람이 붙여 넣을 수 있게 여기 본문에 둔다.**

---

## 5. 제안 diff

세 파일이고, 가운데 것이 본체다.

### 5.1 `core/cost_metering.py` — 목록의 집을 옮기고, 예외를 받는다

```diff
+#: Provider rejections that are answers rather than silences: the request
+#: reached the API and came back refused before any model ran. The audio
+#: adapter already treats these as unbilled when it decides whether to give a
+#: call slot back; the ledger needs the same list for a different decision --
+#: telling a refusal apart from a call whose fate is genuinely unknown. One
+#: list, because two copies would drift and the drift would be invisible.
+UNBILLED_STATUSES = frozenset({400, 401, 403, 404, 413, 415, 422, 429})
+
+
+def _refusal_status(error: BaseException) -> int | None:
+    """The status a provider refusal carries, or ``None`` if it carries none.
+
+    A silence -- a timeout, a dropped socket, a 5xx -- has no place here and
+    must keep leaving its reservation standing, because it may well have been
+    served and billed out of sight.
+    """
+    status = getattr(error, "status_code", None)
+    if status is None:
+        status = getattr(getattr(error, "response", None), "status_code", None)
+    try:
+        status = int(status)
+    except (TypeError, ValueError):
+        return None
+    return status if status in UNBILLED_STATUSES else None
+
+
 class MeteredClient:
     ...
     def _around(self, call: Any, kwargs: dict[str, Any]) -> Any:
         ...
         object.__setattr__(self, "last_call_id", call_id)
-        response = call(**kwargs)
+        try:
+            response = call(**kwargs)
+        except BaseException as error:
+            status = _refusal_status(error)
+            if status is not None:
+                # The provider answered, and the answer was a refusal issued
+                # before any model ran. Not an unreached call, and not a
+                # billed one. Anything without such a status falls through
+                # with its reservation intact, which is the whole point of
+                # reserving first.
+                recorder.ledger.abandon(call_id, note=f"provider_{status}")
+            raise
         recorder.ledger.settle(
             call_id,
             usage=extract_usage(response),
             resolved_model=resolved_model_of(response, requested),
         )
         return response
```

### 5.2 `core/cost_receipts.py` — `abandon`의 조건문을 넓힌다

지금 문서는 *"나가지 않았을 때만"*이라 `400`을 배제한다. 실제로 이 함수가
보장하는 것은 **"확실히 아무것도 안 물렸다"**이고, 그건 더 넓다.

```diff
     def abandon(self, call_id: str, *, note: str | None = None) -> None:
-        """Record that the call never left — so it never cost anything.
+        """Record that the call cost nothing, and that this is known.
 
-        Only correct where the failure is known to precede the request: a
-        prompt that could not be assembled, a client that could not be built.
-        A timeout is *not* this; a timeout leaves the reservation standing,
-        because the request may well have been served and billed.
+        Two kinds of call qualify. One never left: a prompt that could not be
+        assembled, a client that could not be built. The other left and came
+        back refused with a status in :data:`UNBILLED_STATUSES`, before any
+        model ran -- a refusal is an answer, and this one says nothing was
+        spent.
+
+        A timeout is neither, and a 5xx is neither. They leave the
+        reservation standing, because the request may well have been served
+        and billed out of sight.
         """
```

### 5.3 `core/perception/audio.py` — 목록을 두 벌 두지 않는다

```diff
+from core.cost_metering import UNBILLED_STATUSES
+
-#: Provider rejections that happened before the model ran, and so were not
-#: billed. ...
-_UNBILLED_STATUS = frozenset({400, 401, 403, 404, 413, 415, 422, 429})
+#: Provider rejections that happened before the model ran, and so were not
+#: billed. Only these give a call slot back; ... The list itself lives in
+#: ``core.cost_metering`` because the ledger makes the same judgement about
+#: the same eight statuses, and two copies would drift apart silently.
+_UNBILLED_STATUS = UNBILLED_STATUSES
```

> 5.3은 이 갈래가 소유한 파일이지만 **혼자서는 아무 의미가 없다.** 5.1이 없으면
> 그냥 상수를 옮기기만 한 것이다. 그래서 이번에 안 넣었다.

---

## 6. 이 제안이 기존 테스트를 얼마나 건드리나 — **쟀다**

제안을 monkeypatch로 얹고(공용 파일은 **안 고쳤다**) 돌렸다.

| | |
|---|---|
| §4의 새 테스트 8개 | **8 passed** |
| `cost`·`receipt`·`audio`·`perception`·`metering` 관련 기존 묶음 | **1,666 passed / 4 skipped / 1 failed** |

**실패한 1개가 어느 것이냐가 요점이다.**

```
FAILED tests/test_a_broken_audio_reply_still_costs_what_it_cost.py::
       test_a_refused_request_is_recorded_as_unknown_not_as_free[refused]
```

이건 `340`이 **오늘의 `400` 동작을 못 박아 둔 그 테스트**다. 제안이 바꾸려는
바로 그 한 줄이고, 같은 테스트의 `[broke]`(=`500`) 갈래는 **통과한다.** 즉
제안은 5xx·타임아웃을 안 건드리고 여덟 개 상태만 건드린다는 게 실제로
확인됐다.

**1,671개 중 딱 1개.** 그리고 그 1개는 이 변경을 설명하려고 쓴 것이다.

---

## 7. 안 정한 것 / 정할 사람이 정해야 하는 것

| 질문 | 왜 여기서 안 정하나 |
|---|---|
| `abandoned` 재사용이냐 새 상태 `refused`냐 | `abandoned` 행은 `build_receipt`에서 **통째로 건너뛴다**(`cost_receipts.py:1724`). 그래서 `400`이 `abandoned`가 되면 그 작업의 **`model_calls`가 1 줄어든다.** *"모델이 안 돌았으니 모델 호출이 아니다"*는 말이 되고, *"API는 쳤으니 세야 한다"*도 말이 된다. **둘 중 하나를 이 문서가 고르지 않는다** — 새 상태를 만들면 스키마·마이그레이션·모든 읽는 쪽이 따라온다 |
| `429`를 여덟 개에 계속 둘 것인가 | 어댑터는 `429`를 *"기다렸다 다시"*로 취급한다(`_DETERMINISTIC_STATUS`에는 없다). 과금 판단과 재시도 판단이 같은 목록을 봐야 하는지는 별개 질문이다 |
| SDK 내부 재시도 | `339` §9가 남긴 것과 같은 한계다. SDK가 안에서 3번 치고 마지막 것만 예외로 올려보내면 이 층은 1번으로 본다. 이 제안은 그걸 **안 고친다** |

---

## 8. 이 문서가 하지 않은 것

| | |
|---|---|
| `core/cost_metering.py` 수정 | 공용 코드다. 읽기만 했다 |
| `core/cost_receipts.py` 수정 | 위와 같다 |
| 가격표 수정 | 위와 같다 |
| 명세(`TASK_PER_TASK_COST_RECEIPTS.md`) 본문 수정 | 위와 같다. §6.2는 **인용만** 했다 |
| 실패하는 테스트를 검사 묶음에 넣기 | CI를 빨갛게 두거나 `xfail`로 덮는 것 둘 다 안 한다. 본문 §4에 둔다 |
| 모델 호출 | 한 번도 안 했다. 위 숫자는 전부 가짜 응답으로 나온 것이다 |

---

**이어받는 사람에게:** §5를 그대로 붙이고 §4를 `batch-runner/tests/`에 넣으면
8개가 통과하고 `340`의 `[refused]` 한 줄이 실패한다. **그 한 줄은 고쳐야 하는
게 맞다** — 그게 이 변경의 내용이니까. 대신 `[broke]`(5xx)는 그대로 통과해야
하고, 통과하지 않으면 제안이 너무 넓게 잡은 것이다.

---

## 9. 실제로 무엇이 들어갔나 (나중에 적음)

**공용 코드는 A가 고쳤다.** 이 문서의 제안대로다. 이 갈래는 §8에 적은 대로
`core/`를 한 줄도 안 고쳤고, 지금도 안 고쳤다.

**§7의 첫 줄이 정해졌다: `abandoned` 재사용이 아니라 새 상태 `refused`.**
그 이유가 §7에 적힌 그대로다 — `abandoned` 행은 영수증에서 통째로 건너뛰니까,
거절을 거기 넣으면 그 과제의 `model_calls`가 1 줄어든다. 그러면 **전부 거절당한
실행의 영수증이 `$0`짜리 완결**이 된다. "안 썼다"고 말하는 것이고, 맞는 답은
"불렀는데 얼마인지는 주장하지 않는다"다. 그래서 `refused` 행은 **호출로 세고,
금액을 안 달고, 영수증을 `partial`에 둔다.**

**끝나는 방식마다 어디로 가는지가 같이 정해졌다.** 이 문서가 다룬 건 첫
줄이고, 나머지는 첫 줄을 갈라내면서 같이 이름이 붙은 것들이다.

| 이렇게 끝나면 | 상태 | 사유 |
|---|---|---|
| 확정 HTTP 거절 (400 등) | **`refused`** | `call_refused_unpriced` |
| 보내기 전에 실패 | `abandoned` | 영수증에서 빠짐 |
| 갔는지 모름 (5xx·타임아웃) | `reserved` | `call_reachability_unknown` |
| 답은 왔는데 usage 없음 | `settled` | `usage_absent` |

**이 갈래가 한 일은 두 가지뿐이다.**

* §4가 못 박아 둔 `[refused]` 기대값을 `reserved` → `refused`로 옮겼다.
  `[broke]`(5xx)는 §8의 마지막 문단이 요구한 대로 **그대로 `reserved`**이고,
  그래서 두 갈래를 상태와 사유 **양쪽 이름으로** 따로 못 박았다. 둘 다
  받아들이게 적으면 구분이 사라진 날에도 통과한다.
* `342`의 검사기가 새 상태를 읽게 했다. 조건 7이 "답이 온 것"과 "요청이 튕긴
  것"을 나눠 세게 바뀐 게 그것이다 — [`343`](./343-audio-metering-rehearsal.md)
  §3.5.

**이 문서의 숫자는 안 고쳤다.** §6의 `1,666 / 4 / 1`은 제안을 monkeypatch로
얹고 잰 그때의 값이다. 지금 다시 재면 다른 값이 나오지만, 그건 그때 잰 게
틀렸다는 뜻이 아니라 **다른 걸 잰다**는 뜻이다.

**§7의 나머지 두 줄은 아직 열려 있다** — `429`를 여덟 개에 계속 둘 것인가,
SDK 내부 재시도를 이 층이 볼 수 있는가. 둘 다 이 변경이 안 건드렸다.
