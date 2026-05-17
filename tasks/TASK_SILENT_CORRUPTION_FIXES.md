# TASK_SILENT_CORRUPTION_FIXES — 3건 silent corruption fix bundle

BRILLIANT_OPPORTUNITIES.md ⭐⭐⭐⭐⭐ Top 2 + 3 + 4. 셋 다 HF 배포 데이터·평가 결과에 직접 영향, 에러 안 남, 로그 안 찍힘. 한 PR로 묶어서 차단.

> **경로 정정 노트**: 원 지시문은 Fix 2를 `core/providers/anthropic.py`, Fix 3을 `core/qa.py`로 추정했으나 그 파일들은 존재하지 않는다. BRILLIANT_OPPORTUNITIES.md가 명시한 실제 위치(아래 file:line)가 권위 있는 출처이며 이를 따른다. extreme-reasoner 의무 리뷰는 지시대로 그대로 유지(QA 동작 변경 검토 목적).

## 핵심 불변식
- 기존 정상 동작에 회귀 0 (default 환경에서 결과 변화 0건이거나, 변하면 그게 곧 fix 효과)
- 각 fix는 명확한 regression test로 lock
- secrets 노출 0

## Fix 1 — `_AVAILABLE_FILES` Dead-Write
**BRILLIANT 위치**: `batch-runner/core/subprocess_runner.py` — write@`code_path.write_text(code, ...)` → header prepend(`files_header = ... ; code = files_header + code`) → exec(`subprocess.run([python_executable, str(code_path)], ...)`).

**현 코드 (검증 완료, `_execute` / `with tempfile.TemporaryDirectory()` 블록 내)**:
1. `code_path = Path(tmpdir) / "solution.py"` → `code_path.write_text(code, encoding="utf-8")` — 원본 code를 디스크에 기록
2. reference 파일 복사 → `copied_files` 수집
3. `if copied_files:` → `files_header` (`import os` / `_AVAILABLE_FILES = [...]` / `# Available files:`) 를 **로컬 변수** `code`에 prepend. `else:` → `"# No reference files available\n\n" + code`
4. `subprocess.run([python_executable, str(code_path)], ...)` — **디스크의 원본 파일**(힌트 없음)을 실행

→ `_AVAILABLE_FILES` 힌트가 실행 코드에 절대 들어가지 않음 (dead-write).

**Fix**: prepend(if/else) 직후 `code_path.write_text(code, encoding="utf-8")` 1회 추가하여 변형된 `code`를 실행 파일에 반영. (또는 동등하게 header 계산을 첫 write 이전으로 이동.) 최소 변경 — 한 줄 추가.

**Test**: `subprocess_runner`를 reference 파일이 있는 상태로 호출 → 실행된 solution.py(또는 subprocess가 본 소스)에 `_AVAILABLE_FILES`가 정의돼 있고 그 리스트가 실제 복사된 파일명 목록과 일치하는지 검증. 권장: 생성 코드가 `print(_AVAILABLE_FILES)` 하도록 하여 stdout로 확인하거나, write 후 `code_path` 내용을 단언. reference 파일 없을 때 회귀 없음(기존 동작) 확인.

## Fix 2 — Anthropic `content[0].text` 크래시 + `stop_reason` 미참조
**BRILLIANT 위치**: `batch-runner/core/llm_client.py:99` — `content = response.content[0].text if response.content else ""` (`AnthropicClient.chat_complete`).

**현 코드 구조**:
- `NormalizedResponse(content, model, usage)` 는 OpenAI 호환 wrapper: `choices=[_Choice(content)]`, `_Choice.message.content`. **`finish_reason` 속성 없음**.
- step2_run_inference.py:436 가 `finish_reason = getattr(response.choices[0], "finish_reason", None)` 후 `if finish_reason == "length":` 로 절단 경고. Anthropic 경로는 `_Choice`에 `finish_reason`이 없어 항상 `None` → 절단 영구 미감지.

**문제**: extended thinking / tool_use 켜지면 `response.content[0]` 가 `ThinkingBlock`/`ToolUseBlock` → `.text` 없음 → `AttributeError` 로 태스크/배치 실패. `stop_reason` 도 버려져 `max_tokens` 절단이 "성공"으로 기록.

**Fix**:
- `response.content` 블록 리스트를 순회, `getattr(block, "type", None) == "text"` 인 블록들의 `.text` 만 결합(빈 경우 `""`). thinking/tool_use 블록은 skip.
- Anthropic `response.stop_reason` 을 OpenAI 호환 `finish_reason` 으로 매핑하여 `_Choice`/`NormalizedResponse` 에 보존. 매핑: Anthropic `"max_tokens"` → `"length"` (step2:437 `== "length"` 분기 fire), 그 외(`"end_turn"`/`"stop_sequence"`/`"tool_use"`)는 그대로 전달하거나 합리적 호환값. `_Choice`/`NormalizedResponse` 시그니처에 `finish_reason` 인자 추가(기본값으로 기존 호출부 회귀 0).

**Test**:
- 첫 블록이 thinking, 이후 text 블록 mock → text 정상 추출, no AttributeError
- 첫 블록이 tool_use, 이후 text → text 정상 추출
- 첫 블록이 text (기존 케이스) → 기존 동작 동일
- `stop_reason == "max_tokens"` mock → `response.choices[0].finish_reason == "length"` 확인 (step2 절단 감지 호환)
- Azure 경로(`_Choice` 기존 사용처) 회귀 0 확인

## Fix 3 — `qa_failed` Dead Invariant
**BRILLIANT 위치**: `batch-runner/step2_run_inference.py:55`(`RETRIABLE_STATUSES = {"error","qa_failed","pending"}`), `:1208`(`_print_status` `elif result["status"] == "qa_failed"`), `:1410`/`:1426`(summary count). **set 지점 0건.**

**현 코드 (`_run_task_with_qa` 내, while 루프)**:
- QA 점수 `< min_score` 이고 `qa_attempts >= qa_max_retries` 일 때 `"saving as success"` 출력 후 `break` → best_result 가 `status="success"` 그대로 반환.
- (별개) undetermined 경로는 의도적으로 `best_qa["passed"]=True`, `"saving as success (undetermined)"` — 이는 의도된 동작이므로 **건드리지 않음** (genuine fail 만 대상).

**Fix**: QA 최종 미달(retry 소진 후에도 `best_score < min_score`, 즉 진짜 QA fail)일 때 반환되는 best_result 의 `status` 를 `"qa_failed"` 로 설정. undetermined 케이스는 제외. → 기존 4개 read site(RETRIABLE / _print_status / summary x2)와 resume `_get_failed_task_ids` retry 인프라가 정상 작동.

**중요 (동작 변경 — extreme-reasoner 검토 필수)**: 지금까지 QA fail 이 silently `success` 통과했는데 이제 `qa_failed` → resume 시 retry 대상. run 시간 + 토큰 비용 증가, 그러나 README "re-runs error/qa_failed automatically" 약속 충족 + 데이터 품질 개선. pre/post-fix run 간 채점 비교가능성(comparability)에 영향 — extreme-reasoner 가 trade-off 판정.

**Test**:
- Self-QA 가 최종 fail (score < min_score, retry 소진) → 반환 result `status == "qa_failed"` 확인
- 정상 통과 task → `status == "success"` 유지
- undetermined 최종 → 기존대로 `"success"` 유지 (회귀 0)
- `"qa_failed"` 가 `RETRIABLE_STATUSES` 에 의해 retry 대상으로 분기되는지 (state/mock 검증)

## Scope
**수정 대상**:
- Fix 1: `batch-runner/core/subprocess_runner.py`
- Fix 2: `batch-runner/core/llm_client.py`
- Fix 3: `batch-runner/step2_run_inference.py`

**신규 테스트**:
- `batch-runner/tests/test_silent_corruption_fixes.py` — 3개 fix 각각의 regression test

**손대지 않을 곳**:
- `core/needs_files.py`, `core/prompt_classifier.py`, `core/repo_bootstrapper.py` (V2 영역, 회귀 0 유지)
- step1~7 (step2_run_inference.py 의 위 3 fix 지점 외), `src/`, `scripts/`, `data/`, `tasks/` (이 spec 파일 외)
- 기존 테스트 파일(test_llm_client.py / test_subprocess_runner.py 등)은 회귀 확인용으로만 실행, 수정 금지

## Acceptance
- 3개 fix 모두 적용 + 각각 regression test 통과
- 기존 테스트 회귀 0 (V2: test_prompt_classifier, test_resolve_needs_files, test_policy_guardrails, test_step6_v2_fields) + test_llm_client / test_subprocess_runner 회귀 0
- `git status`: 명시된 4개 파일(코드 3 + 테스트 1) + 이 spec 파일 외 변경 없음
- secrets 0
- extreme-reasoner DECISION: APPROVE 또는 APPROVE-WITH-CONDITIONS (REJECT 시 멈춰서 사용자 컨펌)

## Failure Policy
- 기존 테스트 회귀 → REJECT, fix 재검토
- first-reviewer REJECT 1회 재시도
- extreme-reasoner REJECT → 사용자 컨펌 필수

## Out of Scope
- Top 1 (main.py 부재) — 반나절 작업, 별도
- Top 5 (relay 골든테스트) — 1일+ 작업, 별도
- ⭐⭐⭐⭐ 이하 후보들
