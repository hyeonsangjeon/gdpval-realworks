# CODEX — grading "눈·귀" 아키텍처 설계 (A: 추출환경 + B: skill·동적 rubric)

> **선행:** `tasks/0601_monday/rubric_criterion_profile.md`(Step 1)가 있어야 한다. 그 self-contained 비율과 "눈·귀 명세"가 이 설계의 입력이다. 없으면 Step 1 먼저.
> **이 작업은 설계(design)다 — 대규모 구현·실행이 아니다.** 산출은 설계 문서 + (가벼우면) 추출 함수 prototype까지. 컨테이너 빌드/full run/머지는 owner-go 후 별도.

- **Repo:** `gdpval-realworks` (local, `main`)
- **목표 아키텍처(네 의견 정리):** 채점기에게 *모든 시각·청각·형식 정보를 추출해 주는* 환경 + 그 정보로 rubric을 판정하는 절차를 skill로 최적화. **후보 LLM은 이 skill/추출을 안 씀**(채점기 전용) — leakage 없음. rubric은 HF에서 동적으로 붙여 변경 대응.

## 핵심 설계 원칙 (먼저 못박기)
1. **A(눈·귀)와 B(rubric)를 분리한다.**
   - **A = task-agnostic 추출 환경:** ffmpeg/soundfile/pedalboard(audio), LibreOffice(렌더), openpyxl 확장(formatting) 등으로 *어느 task든* 같은 방식으로 modality 증거를 뽑는다. 문제 번호 무관.
   - **B = task-specific rubric 주입:** 각 task의 criterion을 채점기 컨텍스트에 붙인다. **단 정적 skill에 굽지 말고 런타임에 HF `rubric_json`에서 fetch.**
2. **skill에 task별 rubric *내용*을 정적으로 굽지 마라.** HF rubric이 바뀌면 skill이 stale해져 *틀린 기준으로 조용히 채점*한다(우리가 계속 막은 drift 함정). skill엔 *변하지 않는 것*(modality별 검증 레시피 + rubric 로더)만, *변하는 것*(task rubric)은 동적.
3. **rubric이 single source of truth.** 정답을 deliverable_files에서 찾지 마라(100점 미보장, wav null). 판정 기준은 rubric criterion 자체다.
4. **self-contained 우선.** Step 1에서 self-contained로 분류된 criterion부터 설계한다(추출만으로 채점 가능). reference-requiring은 별도 미결 트랙.

## 권한/제약
- **설계 위주. read-only가 기본**, 단 *가벼운 추출 함수 prototype*(예: wav 클리핑 측정 1개, xlsx number_format 추출 1개)은 만들어 동작 확인 OK(소규모, Azure 불필요).
- 금지: 컨테이너 실제 빌드/푸시, full-220 run, cost-cap 수정, main 머지/push. 무거운 구현은 설계 승인 후.
- 기존 자산 재사용: `feat/wire-perception`의 wiring·instrumentation(`perception_called`/`tools_used`), `read_deliverable.py`의 기존 추출, UK BEIS inspect_evals Docker 구성(ffmpeg/libsndfile/soundfile/pedalboard) 참조.

## PART A — 추출 환경 설계 (눈·귀)
Step 1의 "눈·귀 명세"를 받아, modality별로:
- **audio:** self-contained audio criterion을 커버하는 측정 목록(클리핑/LUFS/peak/길이/샘플레이트/포맷/필요시 스펙트럼) + 각 측정이 *어떤 criterion*을 판정하는지 매핑 + 라이브러리(ffmpeg/soundfile/pedalboard). 기존 multi-agent audio 경로(gpt-audio-1.5)와 어떻게 합치/대체되는지.
- **visual:** 렌더링 필요 범위(xlsx/docx/pptx → LibreOffice로 이미지화?) + 어떤 시각 속성 + vision sub-judge 연결.
- **formatting:** `inspect_formatting`이 *현재 빠뜨린* 속성(number format, conditional formatting, alignment, row height, freeze panes, print/page setup, 렌더 모습 — formatting_diagnosis.md 참조)을 어디까지 추가할지 + 각 속성이 어떤 criterion을 커버하는지.
- **컨테이너 명세:** 위를 다 담는 이미지에 무엇이 들어가나(base, ffmpeg, libsndfile, soundfile, pedalboard, LibreOffice, fonts 등). GHCR 경유(메모리의 TASK30 Docker 마이그레이션과 연결). **명세만 — 빌드는 나중.**
- **self-contained vs reference 경계:** 추출이 *판정까지* 하는 criterion(절대 기준)과, 추출은 하되 *비교 대상이 필요한* criterion을 구분해 후자는 미결로.

## PART B — skill + 동적 rubric 로더 설계
- **skill 구조:** modality별 "검증 레시피" — "audio criterion이면 [A의 측정]을 보고 이렇게 pass/partial/fail, formatting이면 [A의 속성]을 보고 이렇게…". *task별 정답이 아니라 modality별 판정 절차.*
- **동적 rubric 주입:** 채점 시 task의 `rubric_json`을 HF에서 fetch해 컨텍스트에 붙이는 메커니즘. HF rubric 버전/해시를 기록해 *어떤 rubric으로 채점했는지* 감사 가능하게. rubric 바뀌면 자동 반영, skill 재작성 불필요.
- **holistic 경계:** "Overall formatting and style" 같은 holistic criterion은 단일 정답이 아니라 *acceptable 경계 + 차원*으로 판정(formatting_diagnosis의 교훈 — 정당한 다른 형식을 fail시키지 않게).
- **경량 모델 적합성:** A+B가 채점기에 풍부한 증거+절차를 주면 *경량 모델로 충분*해지는지 — 이걸 나중에 어떻게 측정할지(원래 mini vs 5.4 질문이 여기서 닫힘) 측정 계획만 명시.

## PART C — instrumentation & 검증 계획
- per-item으로 기록할 것: `tools_used`, `path_used`(어느 deliverable 파일을 봤나 — formatting_diagnosis의 path ambiguity 대응), `op_used`, `modality`, `rubric_version`, perception 호출 여부.
- 이 아키텍처가 채점을 *실제로 개선*했는지는 self-graded avg로 못 본다(반복된 함정). 검증엔 gold가 필요 — *어떤 criterion에 gold가 꼭 필요하고*(holistic·reference-requiring) *어떤 건 추출로 자체 검증되는지*(self-contained 절대 기준) 구분한 검증 계획. gold 필요분은 Step 1에서 나온 우선 항목으로.

## 출력 — `tasks/0601_monday/grading_eyes_ears_design.md` 하나
(폴더 없으면 생성. 이 작업의 모든 산출물·prototype·중간 점검 파일은 `tasks/0601_monday/` 아래에 둔다. 기존 컨텍스트 *읽기* 경로는 안 바뀜.)
```
# GRADING EYES & EARS — DESIGN
## 한 줄 결론
self-contained 비율 [X%] 기반, 추출환경(A)+skill(B)로 [범위]. 구현 무게: [가벼움/중간/무거움(LibreOffice 렌더 등)]. 경량 모델 적합성 검증은 [계획].
## PART A — 추출 환경 (modality별 측정/속성 → criterion 매핑, 컨테이너 명세)
## PART B — skill 구조 + 동적 rubric 로더 (정적 굽기 금지, HF fetch)
## PART C — instrumentation + gold 필요 범위 검증 계획
## 구현 단계 제안 (가벼운 것부터, 무거운 건 owner-go)
## 미결: reference-requiring criterion 처리
```

## 제약 재확인
- 설계 우선. 무거운 구현·컨테이너 빌드·full run·머지는 owner-go 후.
- skill에 task rubric 정적 굽기 금지 — 동적 fetch.
- 정답 출처 = rubric, deliverable_files 아님.
- 경량/중량 모델 결정은 A+B 깐 *뒤* 측정 — 지금 예단 금지.
