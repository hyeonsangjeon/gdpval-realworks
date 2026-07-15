# SPEC: GDPVal Grading Pipeline v2 — Tool-Calling Judge Rebuild

## 0. 메타

- **Status**: Draft → 작업 오푸스 핸드오프용
- **Owner**: hyeonsangjeon
- **Repo**: `hyeonsangjeon/gdpval-realworks`
- **영향 범위**: `batch-runner/core/grader.py`, `core/rubric_loader.py`, grading 호출 경로 전체, `data/grades/*`
- **데이터 소스**: `openai/gdpval` (commit `11e7900`, v2 — rubrics + gold deliverables + reference files)
- **선행 분석 산출물 (이미 main에 커밋됨, `a1457a4`)**:
  - `data/grades/_validation/STRATIFY_v2_exp003_critical_gap.md`
  - `data/grades/_validation/SCORE_MATH_AUDIT.md`
  - `scripts/stratify_critical_gap_v2.py`

이 SPEC은 grading subsystem을 처음부터 다시 짜기 위한 것이다. inference / 220 deliverable 생성 경로는 **건드리지 않는다** (기존 산출물 신뢰).

---

## 1. 배경 — 왜 다시 만드나

### 1.1 근본 진단: format-blindness

현재 grader는 채점기에게 실제 deliverable 파일(`.xlsx`/`.docx`/`.pptx`/`.wav`/`.mp4`)을 주지 않고, 파일을 먼저 plain text로 추출한 뒤 `deliverable_extract_max_chars=1500`으로 잘라서 그 텍스트만 준다. 이 변환에서 글꼴·색·테두리·열너비·병합셀·차트·레이아웃 등 "포맷"에 해당하는 모든 정보가 소실된다. 그래서 루브릭이 "Overall formatting and style"를 채점하라고 해도, 채점기가 받은 입력에는 포맷 정보가 **구조적으로 0**이다.

### 1.2 환경 비대칭

deliverable을 *생성*하는 모델은 라이브러리 접근이 있는 풍부한 파이썬 환경(exp011 BEIS parity, ~80 패키지)에서 진짜 포맷된 파일을 만든다. 그런데 *채점*하는 쪽은 그 결과를 raw text로 납작하게 눌러서 받는다. 만든 쪽이 공들인 포맷을 채점하는 쪽이 못 보는 비대칭. **원칙: 채점기 환경은 최소한 생성기 환경과 parity(또는 superset)여야 한다.**

### 1.3 정량 근거 (Scenario B 확정)

`STRATIFY_v2`에서 hybrid vs mini critical_pass −10pp 격차를 criterion별로 분해한 결과:

| bucket | hybrid-stricter 비중 |
|---|--:|
| formatting | 60.3% |
| penalty | 21.8% |
| content | 17.9% |

격차의 대부분이 단일 criterion `"Overall formatting and style of the deliverable"`에 집중(formatting hybrid-stricter 케이스 47개 중 45개). content 항목에서는 두 채점기가 ~4pp 안에서 일치. → **비싼 채점기가 "더 잡은" 것이 아니라, 텍스트로는 구분 불가능한 입력을 더 비관적으로 찍은 아티팩트.**

### 1.4 부수 발견 (score-math 결함)

`SCORE_MATH_AUDIT`에서:

- `required` field가 10,453 item 전부 `null` → 기존 "critical = required OR weight≥4"는 사실상 **weight≥4 단독**으로만 작동.
- `TaskRubric.max_score`가 양수+음수 item을 산술 합산 → **4개 task에서 `total_max ≤ 0`**, pct가 수학적으로 무의미한데 `[0,100]` clamp가 가림.
- negative penalty item에서 `verdict='pass'` 시멘틱이 반대(`pass`=위반 발생, `fail`=위반 없음)인데 정규화 없이 합산.
- 결과적으로 `critical_item_pass_rate` 헤드라인(0.421 vs 0.518)이 "criterion 충족"과 "위반 저지름"을 혼동.
- negative penalty item 94개가 critical 집합에서 누락되어 있었음.

### 1.5 핵심 교훈

**정확도는 더 큰 채점 모델이 아니라, 채점기에게 파일을 볼 눈을 달아주는 데서 나온다.** 따라서 v2는 모델을 키우는 게 아니라 입력 방식을 바꾸는 작업이다.

---

## 2. 목표 / 비목표

### 목표
1. 채점기가 raw text가 아니라 **실제 deliverable 파일을 tool로 직접 조회**해서 채점한다.
2. modality별(표/문서/시각/오디오/비디오)로 올바른 perception 경로를 라우팅한다.
3. score-math 부호 결함을 고쳐 헤드라인 지표(`avg_score_pct`, `critical_item_pass_rate`)를 신뢰 가능하게 만든다.
4. critical 정의를 부호 무관 magnitude 기반으로 재정의해 negative penalty item을 포함한다.
5. 단일 메인 judge로 단순하게 유지(tier 재도입 금지).

### 비목표
- inference / deliverable 재생성 (안 한다).
- pro/hybrid를 default로 채택 (안 한다 — §4.6 참조).
- pairwise-vs-gold(GDPval 표준 win-rate) 채점 모드 구현 — 별도 후속, 이번 범위 아님(rubric 모드만).

---

## 3. 아키텍처 개요

```
[task rubric (openai/gdpval)] ─┐
                               ├─→ [MAIN JUDGE: gpt-5.4 medium]
[deliverable file path] ───────┘        │
                                         │ tool calls (필요 시)
                                         ▼
                        ┌────────── perception tools ──────────┐
                        │ read_deliverable(op, path, ...)       │
                        │   ├ 구조/서식  → openpyxl/python-docx/pptx │
                        │   ├ 시각        → render→image + vision   │
                        │   ├ 오디오 객관 → soundfile/ffmpeg         │
                        │   ├ 오디오 지각 → gpt-audio-1.5            │
                        │   └ 비디오      → ffmpeg                   │
                        └───────────────────────────────────────┘
                                         │
                                         ▼
                          [per-item verdict + evidence]
                                         │
                          [sign-aware scoring + critical agg]
                                         ▼
                                  [grade JSON]
```

**핵심 전환**: 사전 text 추출(`deliverable_extract_max_chars`) 폐기 → 메인 judge가 필요할 때 tool로 파일을 직접 읽음.

---

## 4. 컴포넌트 스펙

### 4.1 메인 rubric judge

- **모델**: `gpt-5.4`, `reasoning_effort=medium`. 단일. tier 없음.
- **근거**: content 항목에서 mini=standard=pro 동급(정확도 차이 無). standard를 쓰는 이유는 정확도가 아니라 **tool-use / agentic 신뢰도** — judge가 멀티스텝 tool 루프를 돌려야 하므로 mini의 tool 오케스트레이션 약점을 피하기 위함. mini→standard 비용 차는 mini→pro의 9×와 달리 modest.
- **호출 API**: Azure OpenAI Responses API (`client.responses.create()`), function/tool calling 활성화. timeout은 per-request로 설정(client 생성 시점 X — NarrativeAnalyzer 교훈과 동일).
- **프롬프트 계약**: "여기 루브릭이 있다. `read_deliverable` tool로 실제 deliverable 파일을 직접 열어 구조·서식·내용을 확인한 뒤, 각 루브릭 항목을 네가 *관찰한 사실*에 근거해 채점하라. 각 항목에 verdict + evidence(관찰 근거)를 남겨라." (기존 `prompts/grader_judge.md`를 tool-aware 버전으로 개정.)
- temperature=0, seed 고정 유지.

### 4.2 Tool 인터페이스 — `read_deliverable`

기존 exp011 subprocess 환경을 **재사용**한다(새 샌드박스 금지). 사전 확인: Dockerfile/requirements에서 `ffmpeg`, `libsndfile`/`soundfile`, `pedalboard`, `openpyxl`, `python-docx`, `python-pptx`, `pdfplumber` 가용 여부 검증.

judge에 노출할 tool 연산(operation) 제안:

- `inspect_structure(path)` — 파일 타입 자동 판별 후 구조 요약(시트 목록/행렬 크기, 문서 섹션/스타일, 슬라이드 수 등).
- `read_content(path, scope)` — 전체 또는 지정 범위 내용 읽기 (**1500자 truncation 폐기** — on-demand full read).
- `inspect_formatting(path)` — 서식 메타데이터: `cell.fill/font/border`, 병합셀, 열너비, 합계 행 서식, 문서 스타일, 차트 존재 여부 등.
- `render_to_image(path, page/sheet)` — 시각 판단용 페이지 이미지 반환(vision 경로로 연결).
- `probe_audio(path)` — sample rate, channels, duration, peak/LUFS, clipping, silence 비율.
- `probe_video(path)` — codec, duration, resolution, fps, 트랙 구성.

모든 연산은 read-only. 파일 경로는 grading harness가 신뢰 경로로 주입(judge가 임의 경로 접근 못 하게).

### 4.3 Perception 라우팅 (modality별 2계층)

각 modality는 "객관(라이브러리/tool)" 층 + "지각(modality 전용 모델)" 층으로 나뉜다. 객관 층이 대부분의 "유효한 deliverable이냐"를 싸게 잡고, 전용 모델은 진짜 지각적 품질 항목에만 얹는다.

| modality | 객관 (tool) | 지각 (모델) |
|---|---|---|
| 표/스프레드시트 | openpyxl (값·서식·차트) | — (대부분 라이브러리로 충분) |
| 문서 | python-docx (스타일·구조) | — |
| 슬라이드 | python-pptx (레이아웃) | — |
| 시각 (차트 모양·polish) | render_to_image | **gpt-5.4 vision** |
| 오디오 | soundfile/ffmpeg (probe) | **gpt-audio-1.5** (믹싱/음질 등) |
| 비디오 | ffmpeg (probe) | (이번 범위: 객관까지. 지각은 후속) |

라우팅은 **항목(criterion)이 요구하는 modality 기준**으로. 모든 호출을 agentic full-loop로 돌리지 말 것 — perception(특히 vision/audio 모델) 경로는 그게 필요한 항목 부분집합에만 라우팅해 비용을 bound.

### 4.4 Critical 정의 + 부호 정규화

- `required` field는 전부 null이므로 사용 불가 → critical 신호 없음. 따라서 **프로젝트 컨벤션으로 명시**: `critical = |max_score| >= 4` (양수 must-have + 음수 must-not 둘 다 포함, 94개 penalty item 포함).
- 임계값 4는 heuristic이므로 코드 상단에 상수로 분리하고 주석으로 "저자 criticality signal 부재로 인한 프로젝트 컨벤션"임을 명시.
- **부호 정규화**: 채점 verdict를 통합 플래그 `model_did_right`로 정규화한 뒤 critical/gap 계산.
  - 양수 item: `did_right = (verdict == pass)`
  - 음수 item: `did_right = (verdict == fail)` ← 위반 안 함이 good
  - `critical_item_pass_rate`는 `model_did_right` 기준으로 집계 (현재처럼 raw verdict 합산 금지).

### 4.5 점수 계산 (sign-aware)

- `total_max` 계산 시 양수/음수 산술 합으로 인한 `total_max ≤ 0` degenerate 케이스를 **clamp로 가리지 말 것.** 명시적으로 감지해서 별도 처리/플래그(예: positive-only denominator 사용 또는 task 제외 + 사유 기록).
- pct 정규화는 부호 시멘틱을 반영하도록 재정의. negative penalty는 "획득 점수"가 아니라 "회피 대상"이므로 정규화 공식에 그대로 음수 max를 분모에 넣지 말 것.
- `SCORE_MATH_AUDIT.md`의 3가지 remediation 옵션 중 택1하여 구현하고 결정 근거를 PR에 기록.

### 4.6 pro/hybrid 정책

- **default 아님.** 9× 비용에 비해 content 정확도 이득 없음, formatting 이득은 아티팩트.
- 유일하게 남은 live question = **penalty bucket(21.8%)**: sign-bug fix 후 hybrid가 진짜로 위반(negative item)을 더 잡는지 재확인. 만약 그렇다면 → "pro를 default로"가 아니라 **penalty/negative item 한정 narrow audit**로만. (full 220 default 아님, 아주 싼 슬라이스.)

---

## 5. 제거할 legacy

- `deliverable_extract_max_chars` 및 사전 text-추출 채점 경로 전체.
- `critical = required OR weight≥4` 로직 (required 분기 死).
- raw verdict 기반 `critical_item_pass_rate` 집계.
- `total_max` clamp로 degenerate 케이스 은폐하는 부분.
- tier 라우팅 잔재(pro/std/mini tier 분기) — 단일 judge로 대체.

---

## 6. PR 분할 / 작업 순서

> **순서 고정.** 1번은 모든 실험 헤드라인을 오염시키는 correctness 버그라 최우선. 2번은 큰 아키텍처 작업. 1과 2를 같은 PR에 묶지 말 것.

**PR1 — score-math sign-bug fix (최우선, 작고 빠름)**
- §4.4 부호 정규화 + §4.5 점수 계산 + critical 재정의(`|max_score|≥4`).
- 기존 grade JSON 백필(또는 재계산) 경로.
- 단위 테스트: 음수 item 정규화, `total_max≤0` 4개 task, critical 집합 크기 변화(397→483 검증).

**PR2 — tool-calling grader rebuild (메인 작업)**
- §4.1 메인 judge(gpt-5.4 medium) + Responses API tool calling.
- §4.2 `read_deliverable` tool, exp011 env 재사용.
- §4.3 modality 라우팅(vision = gpt-5.4 vision, audio = gpt-audio-1.5).
- `prompts/grader_judge.md` tool-aware 개정.
- §5 legacy 제거.

**PR3 — validation (검증)**
- §7 게이트 실행 및 리포트.

---

## 7. 검증 게이트 / Acceptance criteria

1. **gold-ceiling**: `openai/gdpval`의 gold deliverable을 v2 grader로 채점 → 평균 pct가 ceiling(~90%대), critical 항목 대부분 pass. (gold가 ceiling을 안 찍으면 grader/입력이 여전히 깨진 것.)
2. **formatting 격차 붕괴**: exp003 재채점 시 `"Overall formatting and style"` criterion이 더 이상 구조적으로 억눌리지 않음 — 잘 만든 deliverable은 점수 회복, 진짜 미흡한 것만 감점.
3. **bare-CSV 모호성 해소**: 파일을 openpyxl로 여는 것만으로 "진짜 포맷된 xlsx vs bare CSV"가 evidence에 명시적으로 구분되어 기록됨.
4. **judge_error_rate**: tool 경로에서 < 2% (tool-use 신뢰도). 초과 시 모델 올리기 전에 `reasoning_effort` 먼저 상향(low→medium→high).
5. **variance 통제**: task당 3회 채점 + bootstrap 95% CI 보고 유지.
6. PR1 헤드라인 지표가 sign-aware로 재계산되어 published(HF) 수치와 일치.

---

## 8. Config 델타 (제안 YAML)

```yaml
judge:
  model: gpt-5.4
  reasoning_effort: medium        # mini→standard: tool-use 신뢰도. pro 아님
  api: responses                  # Azure OpenAI Responses API, per-request timeout
  temperature: 0
  seed: 42
  grades_per_task: 3              # bootstrap CI 유지
  # deliverable_extract_max_chars: REMOVED  ← 폐기

  tools:
    read_deliverable:
      env: exp011_subprocess      # 새 샌드박스 금지, 기존 env 재사용
      ops: [inspect_structure, read_content, inspect_formatting,
            render_to_image, probe_audio, probe_video]
      read_only: true

  perception:
    visual:  { model: gpt-5.4, vision: true }   # 차트·레이아웃 등 시각 항목만
    audio:   { model: gpt-audio-1.5 }           # 지각적 음질만
    # 구조/객관은 모델 아님 — tool(op) 직접 사용

  critical:
    rule: abs_max_score_threshold
    threshold: 4                  # |max_score| >= 4 (음수 penalty 포함)
    # required field: 전부 null이라 사용 불가 (프로젝트 컨벤션으로 명시)
    sign_aware: true              # model_did_right 정규화 후 집계

  scoring:
    sign_aware_pct: true
    handle_nonpositive_total_max: explicit   # clamp 은폐 금지
```

---

## 9. 리스크 / Open questions

- **tool-use 비결정성**: tool 출력 때문에 temp=0이어도 run간 편차 발생 가능 → 3회+bootstrap, error_rate 모니터로 대응.
- **새 비용**: vision/audio 경로로 per-task 비용이 옛날 $18보다 오름. perception 라우팅으로 bound하되 **새 파이프라인 비용 재추정 필요**(아직 미산정). 운영 한도는 저장소 외부 설정으로 검증.
- **env 가용성 확정**: ffmpeg/soundfile/openpyxl 등 실제 Dockerfile/requirements에서 검증 후 진행(내 기억 아닌 repo가 authoritative).
- **threshold=4 적정성**: 저자 signal 부재 하의 임의 경계. gold-ceiling 검증과 함께 민감도 점검 여지.
- **vision 모델 충분성**: gpt-5.4 vision이 시각 항목을 충분히 판단하는지 — 부족하면 해당 항목만 상향(전체 모델 교체 아님).

---

## 10. Out of scope

- inference / 220 deliverable 재생성.
- pairwise-vs-gold (GDPval 표준 win-rate) 채점 모드 — 별도 SPEC.
- 비디오 *지각* 품질 채점 — 이번엔 객관(probe)까지만.
- pro/hybrid default 채택.
- Docker 전체 컨테이너 마이그레이션(TASK30/GHCR) — 독립 작업.
