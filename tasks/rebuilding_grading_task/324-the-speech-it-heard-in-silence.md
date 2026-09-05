# 324 — 완전한 무음에서 "사람 목소리가 들린다"고 답했다

**요약.** 오디오 판정자가 **맞는 답을 하는지**를 처음으로 값을 치르고 쟀다.
소리 내용이 계산으로 정해진 클립 9개에 기준 20개(참 10·거짓 10), 각 3번씩 **60번**
물었다. 결과는 이렇다.

* **정확도 51.85%** — 동전 던지기와 구별되지 않는다.
* **판별력(Youden's J) 0.011.** 0이면 "판정이 소리와 무관하다"는 뜻이다.
  기준별 다수결로 다시 세면 **−0.1**, 즉 **부호가 음수**다.
* **순열 p = 0.5.** 1024가지 재배치 중 **512가지**가 실제 결과만큼은 한다.
* 이번 설계가 낼 수 있는 **가장 작은 p는 0.00098**이다. 즉 판정자가 실제로 듣고
  있었다면 이 실험은 그것을 **0.001 수준에서 증명할 수 있었다.** 못 한 게 아니라,
  **증명할 게 없었다.**

[`321`](./321-the-question-the-probe-asked.md)의 첫 판은 삑 소리 5개에 기준 12개였고,
그때도 판별력은 0이었다. 그건 "코퍼스가 너무 단순해서"라는 반론이 가능했다.
[#427](https://github.com/hyeonsangjeon/gdpval-realworks/pull/427)이 음악 재료
4쌍(조성·화음·전조·음색)을 넣어 p 바닥을 1/64에서 **1/1024**로 내렸다.
**반론이 사라진 자리에서 결과는 그대로다.**

측정한 값 전체는 이 문서 옆에 그대로 두었다
([`324-audio-accuracy-measured.json`](./324-audio-accuracy-measured.json)).
아래 숫자는 전부 그 파일에서 나오고, `test_324_quotes_the_run_it_measured.py`가
문서와 파일이 어긋나면 실패한다.

**비용: 60번 호출, 금액 `미등록`.** `$0`이 아니다(§11).

---

## 1. 무엇을 물었나

기준 하나하나는 **소리만 들으면 참·거짓이 정해지는 문장**이다. 사람 취향이 들어갈
자리가 없다. 같은 클립에 참 하나·거짓 하나를 **짝**으로 붙였다.

| 짝 | 클립 | 참 기준 | 거짓 기준 |
|---|---|---|---|
| `timing` | 2초 소리 뒤 4초 침묵 | 도중에 멈추고 침묵이 남는다 | 끝까지 이어지고 침묵이 없다 |
| `presence` | **모든 표본이 0인 디지털 무음** | 아무것도 들리지 않는다 | 사람 말소리가 들린다 |
| `count` | 삑 소리 3개 | 정확히 3개 | 정확히 7개 |
| `tempo_coarse` | 0.5초 간격 클릭 16개 | 약 120 BPM | 약 60 BPM |
| `tempo_fine` | 같은 클립 | 120 BPM ±1 | 132 BPM ±1 |
| `pitch_order` | 220 Hz 뒤 880 Hz | 낮게 시작해 높게 끝난다 | 높게 시작해 낮게 끝난다 |
| `key` | G장음계 8음 | 모든 음이 G장조 | 모든 음이 E♭장조 |
| `triad` | G4+B4+D5 동시 | 한 화음, 장3화음 | 한 화음, 단3화음 |
| `modulation` | G장조 아르페지오 뒤 반음 위 | 도중에 조가 바뀐다 | 처음부터 끝까지 한 조 |
| `timbre` | C2 + 배음 5개 | 배음이 들리는 거친 소리 | 배음 없는 맑은 사인파 |

클립은 저장소에 없다. **돌 때마다 `wave`와 `math`로 만든다.** 그래서 "정답"은
누군가의 의견이 아니라 산수다. 만든 바이트의 sha256이 보고서에 들어 있다.

---

## 2. 결과 — 동전과 구별되지 않는다

| | 값 |
|---|---|
| 호출 | **60** (기준 20 × 반복 3) |
| 답한 호출 | 54 |
| 맞힘 | 28 |
| 정확도(답한 것 기준) | **51.85%** |
| 참 기준을 틀리게 fail (false fail) | 22 → **84.6%** |
| 거짓 기준을 틀리게 pass (false pass) | 4 → **14.3%** |
| 애매하게 답함(`partial`) | 0 |
| 아예 못 답함(`judge_error`) | **6** |
| **판별력 J (호출 단위)** | **0.011** |
| **판별력 J (기준별 다수결)** | **−0.1** |
| 순열 p (한쪽 꼬리) | **0.5** |
| 이 설계가 낼 수 있는 가장 작은 p | 0.00098 |

---

## 3. 왜 51.85%를 믿으면 안 되나

**"전부 fail"이라고만 답해도 이 코퍼스에서 정확도는 50%가 나온다.** 참 10개는
전부 틀리고 거짓 10개는 전부 맞기 때문이다. 그래서 정확도는 **듣는 판정자와
안 듣는 판정자를 구별하지 못한다.**

구별하는 건 **판별력 J = P(pass | 참 기준) − P(pass | 거짓 기준)** 하나뿐이다.
아무 소리도 안 듣고 같은 답만 하면 두 확률이 같아지므로 **J = 0**이 된다.

이번 J는 **0.011**이다. 다수결로 세면 **−0.1**, 참인 기준을 오히려 **덜** 통과시켰다.

p = 0.5의 뜻은 이렇다. 짝 안에서 참·거짓 딱지를 뒤집어 만들 수 있는 코퍼스가
`2^10 = 1024`가지인데, 그중 **512가지가 실제 결과만큼 또는 그보다 잘 나온다.**
동전을 던져 절반을 맞히는 것과 같은 자리다.

---

## 4. 판정자는 거의 항상 "fail"이라고 답한다

답한 54번 중 **fail 46번, pass 8번**이다. 85%가 fail이다.

가족별로 보면 이유가 한눈에 보인다.

| 가족 | 답함 | 맞힘 | false fail | false pass | 못 답함 |
|---|---:|---:|---:|---:|---:|
| `count` | 6 | 3 | 3 | 0 | 0 |
| `key` | 6 | 3 | 3 | 0 | 0 |
| `modulation` | 6 | 3 | 3 | 0 | 0 |
| `pitch_order` | 4 | 3 | 1 | 0 | 2 |
| `presence` | 4 | 1 | 2 | 1 | 2 |
| `tempo_coarse` | 6 | 3 | **0** | **3** | 0 |
| `tempo_fine` | 6 | 3 | 3 | 0 | 0 |
| `timbre` | 6 | 3 | 3 | 0 | 0 |
| `timing` | 4 | 3 | 1 | 0 | 2 |
| `triad` | 6 | 3 | 3 | 0 | 0 |

**"6번 답해서 3번 맞힘"이 일곱 줄 반복된다.** 이건 실력이 아니라 구조다.
한 짝은 참 3번·거짓 3번인데 **여섯 번 다 fail이라고 답하면 정확히 3번 맞는다.**

`tempo_coarse`만 반대다. 여섯 번 다 **pass**라고 답해서 역시 3번 맞았다.

---

## 5. 증거 1 — 모든 표본이 0인 파일에서 "사람 목소리"

`pure_silence`는 **모든 표본이 정수 0**인 파일이다. 들릴 것이 물리적으로 없다.

| 호출 | 판정 | 확신 | 판정자가 쓴 근거 |
|---|---|---:|---|
| `presence_true` 1회차 | fail | 0.97 | "Clear speech is audible throughout the clip." |
| `presence_false` 1회차 | pass | 0.98 | "A clear, natural human voice is heard speaking throughout the 30s clip." |
| `presence_true` 2회차 | fail | 0.90 | "Faint background noise and occasional speech detected in the clip" |
| `presence_true` 3회차 | pass | 0.98 | "30s of complete silence with no speech, music, or noise." |

**같은 파일에 대해 확신 0.98로 "또렷한 사람 목소리가 계속 들린다"고 했고,
확신 0.98로 "완전한 무음"이라고도 했다.** 둘 다 같은 0의 나열을 듣고 한 말이다.

---

## 6. 증거 2 — 삑 소리 3개를 1·3·4·5개로 셌다

`three_beeps`는 0.5초·2.0초·3.5초에 150 ms 삑 소리가 하나씩, 모두 **3개**다.
여섯 번 물었고 **네 가지 다른 개수**가 돌아왔다.

| 호출 | 판정 | 판정자가 쓴 근거 |
|---|---|---|
| `count_true` 1회차 | fail | "Only **one** short beep is audible…" |
| `count_false` 1회차 | fail | "Only **three** beeps were audible in 30 seconds…" |
| `count_true` 2회차 | fail | "Only **one** short beep heard…" |
| `count_false` 2회차 | fail | "Only **five** short beeps…" |
| `count_true` 3회차 | fail | "Only **one** short beep heard at the start…" |
| `count_false` 3회차 | fail | "Only **four** beeps are heard…" |

여기서 특히 나쁜 줄은 `count_false` 1회차다. **"삑 소리가 정확히 세 개"라는
사실을 근거에 써놓고**, "정확히 일곱 개인가?"라는 질문에 fail이라고 답했다.
답 자체는 맞지만 그 옆의 `count_true`는 같은 클립을 "하나"라고 했다.

---

## 7. 증거 3 — 질문이 제안한 숫자를 그대로 되돌려준다

가장 중요한 줄이다. `clicks_120bpm`은 클릭 16개가 **정확히 0.5초 간격**,
즉 120 BPM이다. 이 한 파일에 기준 넷을 물었다.

| 호출 | 기준이 제안한 값 | 판정 | 판정자가 "쟀다"는 값 |
|---|---|---|---|
| `tempo_coarse_true` 1회차 | 약 120 BPM | pass | "clicks occur every **0.5 seconds**" |
| `tempo_coarse_false` 1회차 | 약 60 BPM | **pass** | "Clicks occur **once per second**" |
| `tempo_coarse_true` 2회차 | 약 120 BPM | pass | "nearly every **0.5 seconds**… consistent 120 BPM" |
| `tempo_coarse_false` 2회차 | 약 60 BPM | **pass** | "roughly **once every second**" |
| `tempo_coarse_true` 3회차 | 약 120 BPM | pass | "roughly every **0.5 seconds**, matching 120 BPM" |
| `tempo_coarse_false` 3회차 | 약 60 BPM | **pass** | "roughly **one second apart**" |

**세 번 다 그랬다.** 120을 제안하면 0.5초를 "쟀다"고 하고, 60을 제안하면
1초를 "쟀다"고 한다. 같은 파일, 같은 회차, 몇 초 사이다.

허용 오차를 ±1 BPM으로 좁힌 `tempo_fine`에서는 방향이 뒤집힌다. 여섯 번 모두 fail이고,
"쟀다"는 값은 이렇다.

> 0.7초(≈86 BPM) · 0.8초(≈75 BPM) · "30초에 클릭 110개"(≈110 BPM) ·
> 0.8초(≈75 BPM) · "30초에 클릭 29개"(≈58 BPM)

**정답은 언제나 0.5초 · 120 BPM · 16개다.**

여섯 번 중 한 번은 예외다. `tempo_fine_false` 2회차는 "약 120 BPM으로 들리는데
132 BPM보다 느리다"고 써서 **처음으로 맞는 값을 말했다.** 다만 그때도 판정은
fail이고, 그 fail은 맞는 판정이다(기준이 132였으니까). 즉 **여섯 번 중 한 번만
소리에 가까운 값을 냈고, 그 한 번조차 점수에는 아무 차이를 만들지 않았다.**

그래서 이 판정자가 하는 일은 이렇게 요약된다. **느슨한 질문에는 제안된 값을
그대로 확인해 주고, 빡빡한 질문에는 거절한다.** 판정은 소리가 아니라
**질문의 모양**을 따라간다. `tempo_coarse`가 6번 다 pass, `tempo_fine`이 6번 다
fail인 이유가 이것이다.

### 같은 버릇이 길이에서도 보인다

증거 문장에 "30초"가 자꾸 나온다. 실제 클립은 3~8초다. 이건 모델이 길이까지
지어냈다기보다 **프롬프트가 그렇게 말해 주기 때문**이다. 판정자에게 가는 시스템
프롬프트 첫 문장이 이렇다(`core/perception/audio.py:342`).

> The clip is a head-only slice (first 30s) of the LLM-under-test's audio
> deliverable.

실제 채점에서 오디오는 앞 30초로 잘려 나가므로 이 문장 자체는 맞다. 이 실험은
**진짜 채점 경로를 그대로 부르기 때문에** 6초짜리 무음에도 같은 문장이 붙는다.
그러자 모델은 **들은 길이가 아니라 들었다고 들은 길이**로 답한다 — "30s of
complete silence", "30초에 클릭 110개", "Only three beeps were audible in 30
seconds". §7이 말한 것과 같은 버릇이 길이에서 한 번 더 나온 셈이다.

이게 결과를 흔들지는 않는다. 기준 20개 중 길이를 묻는 것은 하나도 없고, 전부
**내용**(몇 개인가, 무슨 조인가, 배음이 있는가)을 묻는다. 다만 클립을 30초로
채워 다시 재면 이 잡음은 없앨 수 있다(§10-6).

---

## 8. 20 × 3 판정 전체

| 기준 | 참? | 1회 | 2회 | 3회 |
|---|---|---|---|---|
| `timing_true` | 참 | judge_error | judge_error | fail |
| `timing_false` | 거짓 | fail | fail | fail |
| `presence_true` | 참 | fail | fail | pass |
| `presence_false` | 거짓 | pass | judge_error | judge_error |
| `count_true` | 참 | fail | fail | fail |
| `count_false` | 거짓 | fail | fail | fail |
| `tempo_coarse_true` | 참 | pass | pass | pass |
| `tempo_coarse_false` | 거짓 | pass | pass | pass |
| `tempo_fine_true` | 참 | fail | fail | fail |
| `tempo_fine_false` | 거짓 | fail | fail | fail |
| `pitch_order_true` | 참 | judge_error | judge_error | fail |
| `pitch_order_false` | 거짓 | fail | fail | fail |
| `key_true` | 참 | fail | fail | fail |
| `key_false` | 거짓 | fail | fail | fail |
| `triad_true` | 참 | fail | fail | fail |
| `triad_false` | 거짓 | fail | fail | fail |
| `modulation_true` | 참 | fail | fail | fail |
| `modulation_false` | 거짓 | fail | fail | fail |
| `timbre_true` | 참 | fail | fail | fail |
| `timbre_false` | 거짓 | fail | fail | fail |

**16줄이 세 번 모두 같은 답이다.** 이 판정자는 흔들리지 않는다. 다만
흔들리지 않는 답이 틀렸을 뿐이다.

[`315`](./315-repeat-variation-prereg.md)의 반복 실험이 잰 **오디오 판정 불일치
19.35%** 는 여기에 이렇게 붙는다. **일관성과 정확성은 다른 것이고, 이번 결과는
둘이 서로를 보장하지 않는다는 걸 같은 판정자 위에서 보여준다.**

---

## 9. 답하지 않은 6건

여섯 번은 판정 자체가 안 나왔다. **여섯 건 모두 같은 원인**이다.

```
provider_error:JSONDecodeError
```

| 기준 | 회차 | 클립 | 응답 토큰 | 걸린 시간 |
|---|---|---|---|---|
| `timing_true` | 1 | `tone_stops_early` | 59 | 2440 ms |
| `pitch_order_true` | 1 | `low_then_high` | 21 | 1075 ms |
| `timing_true` | 2 | `tone_stops_early` | 26 | 1082 ms |
| `presence_false` | 2 | `pure_silence` | 24 | 1081 ms |
| `pitch_order_true` | 2 | `low_then_high` | 23 | 1162 ms |
| `presence_false` | 3 | `pure_silence` | 48 | 1365 ms |

모델이 JSON이 아닌 것을 돌려줬다는 뜻이다. **이 6건은 정확도 계산에서 뺐다.**
0점으로 넣으면 "틀렸다"가 되는데, 실제로 일어난 일은 "답하지 않았다"이기 때문이다.
`unanswered`로 따로 센다.

---

## 10. 이 측정이 말하지 않는 것

정직하게 적어둔다.

1. **말소리(speech)는 아직 안 쟀다.** 카드는 "말소리와 음악"을 요구했는데,
   알아들을 수 있는 말소리는 `wave`와 `math`로 못 만든다. 녹음이나 음성합성기가
   필요하고, 둘 다 "오디오 파일을 저장소에 넣지 않는다"는 이 도구의 규칙과 부딪힌다.
   **이번은 음악 절반이다.** §5의 무음 실험이 말소리를 *간접적으로* 건드리긴 하지만
   (판정자가 없는 목소리를 만들어냈다), 진짜 말소리를 알아듣는지는 안 쟀다.
2. **합성음이다.** 실제 영화·음악 트랙이 아니다. 다만 실제 트랙으로는 "정답"을
   산수로 정할 수 없어서, 맞고 틀림을 재려면 이 방향밖에 없다.
3. **N = 3이다.** 반복 3번은 [`315`](./315-repeat-variation-prereg.md)와 맞추려고
   고른 값이다. 반복을 늘려도 **p 바닥은 안 내려간다.** 바닥은 `1 / 2^짝수`이고
   반복은 그 식에 없다. 내리려면 짝을 더 넣어야 한다.
4. **판정자 하나만 봤다.** `gpt-audio-1.5`, 배포 이름도 같고, 경로는 `direct-v1`,
   설정은 `gold_audio_repeat_v2_sol_max.yaml`이다. 다른 모델·다른 프롬프트가
   어떨지는 이 실험이 말하지 않는다.
5. **채점을 한 게 아니다.** 과제도, 루브릭도, 산출물도 없다. 오디오 하위 판정자를
   직접 불렀다. 그래서 이 실행은 어떤 점수도 쓰지 않았고 대시보드에도 안 올라간다.
6. **클립이 프롬프트가 말하는 길이보다 짧다.** 클립은 3~8초인데 프롬프트는 "앞
   30초"라고 말한다(§7 끝). 기준 중 길이를 묻는 것이 없어서 결과는 안 흔들리지만,
   클립을 30초로 채우면 이 잡음은 사라진다. 대신 보내는 바이트가 4~10배가 된다.

---

## 11. 비용 — `미등록`, `$0`이 아니다

| | 값 |
|---|---|
| 모델 호출 | 60 |
| 과금 대상 호출 | **60** |
| 모델 | `gpt-audio-1.5` |
| 가격표 완비 여부 | **false** |
| 가격 없는 모델 | `gpt-audio-1.5` |
| 추정 금액 | **`null`** |

`gpt-audio-1.5`는 저장소 가격표에 없다. 그래서 보고서는 금액을 `null`로 낸다.
**이건 "0원"이 아니라 "얼마인지 모른다"는 뜻이다.** 돈은 나갔고 액수를 우리가
모른다. 0을 적으면 나가지 않은 것처럼 읽히므로 적지 않는다.

승인 기록에 남은 문구는 이것이다.

```
Approved paid audio accuracy probe:
  model      = gpt-audio-1.5 (read from gold_audio_repeat_v2_sol_max.yaml)
  criteria   = 20 (10 true / 10 false)
  repeats    = 3
  calls      = 60
  grades     = none. This does not write a grade or touch a corpus.
```

이 줄이 60을 말하게 만든 것이
[#428](https://github.com/hyeonsangjeon/gdpval-realworks/pull/428)이다. 그전까지
승인 기록은 **36**이라고 적혀 있었다. 코퍼스가 20개로 늘어난 뒤에도 12개 시절
숫자를 그대로 들고 있었기 때문이다. **승인받은 양과 실제 쓴 양이 어긋나는 종류의
잘못**이라 값을 치르기 전에 먼저 고쳤다.

---

## 12. 무엇이 따라 나오나

**이 문서는 아무 코드도 고치지 않고, 어떤 결정도 대신 내리지 않는다.**
따라 나오는 것만 적는다.

* 185개 과제 gold 실행에는 오디오로 채점된 항목이 **31개** 있다. 그 항목들의
  오디오 판정은 이번에 잰 것과 **같은 모델·같은 경로**에서 나왔다. 이번 결과는
  그 31개를 어떻게 다룰지에 대한 **판단 근거**이지 판단 자체가 아니다.
  결정은 소유자 몫으로 열려 있다.
* 이번 결과는 **"오디오 채점을 고쳐라"**로 바로 이어지지 않는다. §7이 보여주는 건
  모델이 기준 문장에 끌려간다는 것인데, 그게 프롬프트 문제인지 모델 능력 문제인지
  이 실험은 구분하지 못한다. **구분하려면 프롬프트를 바꿔 같은 20개를 다시 물으면
  된다.** 그건 이 도구로 그대로 할 수 있고, 60번 더 든다.
* 말소리 절반은 여전히 열려 있다(§10-1).

---

## 13. 재현 절차

값 없이 전 구간을 돌려보는 것부터.

```bash
cd batch-runner
python scripts/measure_audio_grading_accuracy.py --dry-run
```

실제 측정은 워크플로 하나로만 살 수 있다. `grading` 환경 승인이 필요하다.

```
Actions → Audio Accuracy Probe → Run workflow
  dry_run       = false
  paid_approval = true
  repeats       = 3
```

이 문서가 인용한 실행:

* 실행 <https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/33883388098>
* 커밋 `609c7e8`
* 보고서 [`324-audio-accuracy-measured.json`](./324-audio-accuracy-measured.json)

---

## 14. 채점기 지문은 하나도 안 움직인다

이 문서, 옆의 JSON, 그리고 §11이 말한 워크플로 수정 전부
`compute_grader_source_hash`가 읽는 파일 목록에 없다. 채점 설정 **14개 전부**에
대해 병합 전후 지문을 다시 계산해서 확인했다.

```
14 configs compared — IDENTICAL
```

**돌고 있는 채점 실행에 영향이 없고, 다시 스모크를 돌릴 필요도 없다.**
