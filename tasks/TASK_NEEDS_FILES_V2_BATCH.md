# TASK_NEEDS_FILES_V2_BATCH — Dual-Signal Manifest (batch-runner)

> Backward-compatible 확장. default policy `deliverable_only` 유지 → 기존 실험 결과·비교 가능성 보존.
> 새 정책은 YAML/env override로만 활성화.

---

## Goal

`step0_needs_files_manifest.json` 을 **단일 신호(`deliverable_files` 길이)** 에서 **이중 신호(deliverable + prompt 휴리스틱)** 로 확장한다.

핵심 불변식:
- **default `needs_files` 키의 값은 현재(=185) 그대로**. 정책 전환은 명시적 opt-in.
- `core/needs_files.NeedsFilesManifest` 의 기존 API 100% 하위 호환.
- 끝난 실험 self_report.json 은 손대지 않는다 (별도 backfill TASK 분리).

---

## Worker Assignment

- **Primary**: `coder`
- **Required reviewer**: `first-reviewer` (APPROVE 필수)
- **Recommended secondary review**: `extreme-reasoner` — 평가 신뢰성 영향 가능 영역. convention 의 강제 트리거 명시 영역은 아니지만, manifest 변경이 `step5_validate` dummy 생성 → success rate 정의에 닿으므로 1회 거쳐주는 게 안전.
- **Optional final**: `codex exec` 2차 리뷰 (manifest 스키마 변경부에 한정)
- **git-committer**: first-reviewer APPROVE 직후만

CLI:

```bash
copilot --yolo --max-autopilot-continues 25 \
  --deny-tool='shell(rm -rf)' \
  --deny-tool='shell(git push --force)' \
  --deny-tool='shell(git reset --hard)' \
  --deny-tool='shell(sudo)' \
  --agent coder \
  -p "tasks/TASK_NEEDS_FILES_V2_BATCH.md 를 읽고 구현해. 끝나면 first-reviewer 호출."
```

---

## Scope

**대상 (수정/신규)**:
- 신규: `batch-runner/core/prompt_classifier.py`
- 신규: `batch-runner/tests/test_prompt_classifier.py`
- 신규: `batch-runner/tests/test_resolve_needs_files.py`
- 수정: `batch-runner/core/repo_bootstrapper.py` (특히 line 335 부근 `_generate_manifest_from_dir`)
- 수정: `batch-runner/core/needs_files.py` (getter 추가, 기존 API 보존)
- 수정: `batch-runner/core/config.py` (정책 상수 + env override)

**손대지 않을 곳 (read-only)**:
- `step1_prepare_tasks.py`, `step2_run_inference.py`, `step5_validate.py` — manifest 소비자. `NeedsFilesManifest.needs_files(task_id)` API 가 안 깨지면 무수정.
- `fill_parquet.py`, `step3_compile_report.py` — 채점 출력 측. 다음 phase.
- `src/`, `dashboard/`, `scripts/aggregate-*.mjs` — UI는 별도 TASK_NEEDS_FILES_V2_UI 에서 처리.
- `data/`, `tasks/*REPORT.md` — read-only.

---

## Design

### 1. Prompt Classifier (`core/prompt_classifier.py`)

`tasks/HF_PROMPT_ANALYSIS_REPORT.md` Appendix A 의 룰을 그대로 코드화. 입력은 `prompt: str`, 출력은:

```python
@dataclass
class PromptClassification:
    requires_file: bool
    explicit_exts: List[str]      # prompt 에 직접 박힌 확장자
    inferred_exts: List[str]      # 명사 휴리스틱
    confidence: str               # "explicit" | "inferred" | "ambiguous" | "text_only"

def classify_prompt(prompt: str) -> PromptClassification:
    ...
```

규칙 (HF report Appendix A 인용):
- **explicit_exts**: 정규식으로 `.docx, .xlsx, .pptx, .pdf, .csv, .png, .jpg, .wav, .mp3, .mp4, .zip, .html, .md, .txt, .json, .ipynb, .dwg` 매칭.
- **inferred_exts**: producer verb 와 deliverable noun 의 인접 매칭으로 추정.
  - report→`.docx`, spreadsheet/workbook→`.xlsx`, slide deck/presentation→`.pptx`,
  - chart/image/diagram→`.png`, audio→`.wav`, video→`.mp4`, csv→`.csv`,
  - pdf→`.pdf`, notebook→`.ipynb`, archive→`.zip`, cad drawing→`.dwg`.
- **confidence**:
  - explicit_exts 있으면 `"explicit"`
  - inferred_exts 만 있으면 `"inferred"`
  - producer verb 만 있고 noun 없거나 noun 만 있고 verb 없음 → `"ambiguous"`
  - 둘 다 없음 → `"text_only"`
- `requires_file = confidence in {"explicit", "inferred", "ambiguous"}`

**테스트 (`test_prompt_classifier.py`)**:
- 단위: confidence 4 클래스 각각 fixture prompt 3개씩 (총 12 케이스)
- 통합: 220 prompt 전체에 대해 explicit_ext / inferred_ext / ambiguous / text_only 분포 카운트 → `HF_PROMPT_ANALYSIS_REPORT.md` 의 ±5건 이내 일치 확인 (정확 일치는 강제하지 않음 — 휴리스틱은 비결정적 표현이 있음)

### 2. Policy Resolver (`needs_files.py` 또는 `repo_bootstrapper.py` 내부)

```python
def resolve_needs_files(
    has_deliverable: bool,
    prompt_classification: PromptClassification,
    policy: str,
) -> bool:
    if policy == "deliverable_only":
        return has_deliverable
    if policy == "explicit_boost":
        return has_deliverable or bool(prompt_classification.explicit_exts)
    if policy == "union":
        return has_deliverable or prompt_classification.requires_file
    if policy == "intersection":
        return has_deliverable and prompt_classification.requires_file
    raise ValueError(f"unknown policy: {policy}")
```

**테스트 (`test_resolve_needs_files.py`)**: 4 policy × 4 입력 조합(t/f × t/f) = 16 케이스 truth table.

### 3. Config 상수 (`core/config.py`)

```python
NEEDS_FILES_POLICY = os.environ.get("NEEDS_FILES_POLICY", "deliverable_only")
NEEDS_FILES_POLICIES_KNOWN = ("deliverable_only", "explicit_boost", "union", "intersection")
```

YAML override 도 가능하게: experiments YAML 에 `needs_files_policy: explicit_boost` 박으면 `step1` 이 env 로 주입하거나 매니페스트 재생성 직전에 override. **default 는 절대 변경 금지** (현재 동작 보존).

### 4. Manifest schema v2 (확장 — 기존 키 모두 유지)

`_generate_manifest_from_dir` (`repo_bootstrapper.py:289-358`) 수정. 각 task 엔트리:

```json
{
  "needs_files": true,
  "original_file_count": 1,
  "original_files": ["..."],
  "has_deliverable_files": true,
  "prompt_classification": {
    "requires_file": true,
    "explicit_exts": [".wav"],
    "inferred_exts": [],
    "confidence": "explicit"
  },
  "policy_results": {
    "deliverable_only": true,
    "explicit_boost": true,
    "union": true,
    "intersection": true
  }
}
```

`_summary` 도 확장:

```json
{
  "_total_tasks": 220,
  "_summary": {
    "needs_files": 185,
    "text_only": 35,
    "active_policy": "deliverable_only",
    "policy_counts": {
      "deliverable_only": 185,
      "explicit_boost": <NN>,
      "union": <NN>,
      "intersection": <NN>
    },
    "confidence_distribution": {
      "explicit": <NN>,
      "inferred": <NN>,
      "ambiguous": <NN>,
      "text_only": <NN>
    }
  }
}
```

### 5. NeedsFilesManifest API 확장 (`core/needs_files.py`)

**유지 (변경 금지)**: `.needs_files(task_id) -> bool`, `.original_file_count(task_id)`, `.original_files(task_id)`, `.summary`.

**신규 getter**:
- `.has_deliverable_files(task_id) -> bool`
- `.prompt_classification(task_id) -> dict`
- `.policy_result(task_id, policy: str) -> bool`
- `.summary.policy_counts` (속성)

기존 manifest 파일(v1 schema)을 읽을 때 신규 키가 없으면 **defensive default** 반환 (예: `prompt_classification` 미존재 → `None`). 즉 옛 manifest 로 작업 중인 환경도 깨지지 않음.

---

## Acceptance Criteria

- [ ] `core/prompt_classifier.py` 신규 — `classify_prompt()` 와 `PromptClassification` 데이터클래스
- [ ] 단위 테스트 통과: `pytest batch-runner/tests/test_prompt_classifier.py -v`
- [ ] 단위 테스트 통과: `pytest batch-runner/tests/test_resolve_needs_files.py -v`
- [ ] `repo_bootstrapper._generate_manifest_from_dir` 수정 — manifest v2 schema 출력 확인
- [ ] **default policy=`deliverable_only` 일 때 `needs_files` 카운트 = 185** (기존과 동일) ← Most-important regression check
- [ ] `NeedsFilesManifest` 기존 API 동작 변화 없음 (`step1`/`step2`/`step5` 무수정으로 동작)
- [ ] `core/config.py` 에 `NEEDS_FILES_POLICY` env 변수 지원
- [ ] manifest 의 `_summary.policy_counts` 4종 모두 채워짐
- [ ] manifest v1 (옛 schema) 도 `NeedsFilesManifest` 가 읽을 수 있음 (방어적 기본값)
- [ ] `git status` — 위 6개 파일 외 변경 없음
- [ ] secrets 미노출

---

## Out of Scope

- UI 측 하드코딩 `220` 동적화 → `TASK_NEEDS_FILES_V2_UI.md`
- 끝난 실험 self_report.json 백필 → `TASK_NEEDS_FILES_V2_BACKFILL.md`
- step3 report_data.json 에 신규 필드 surface → 백필 TASK 와 함께
- default policy 전환 결정 (deliverable_only → explicit_boost) → 별도 정책 결정 회의 후

---

## Failure Policy

- 220 task fixture 로 통합 테스트 시 HF 캐시 누락 → quota/auth 확인 후 1회 재시도. 그래도 실패면 unit test 만으로 PR 가능 (integration mark 분리).
- 휴리스틱 카운트가 HF_PROMPT_ANALYSIS_REPORT 결과와 ±5건 초과 차이 → fail 처리, 휴리스틱 룰 재점검.
- first-reviewer REJECT → 1회 재시도. 2회 실패 시 사용자 보고.

---

## Handoff

작업 완료 후:
1. `git diff --stat` 출력으로 변경 파일 6개 확인.
2. `pytest batch-runner/tests/test_prompt_classifier.py batch-runner/tests/test_resolve_needs_files.py -v` 통과 로그.
3. fresh manifest 생성 후 `_summary` 섹션 dump.
4. first-reviewer 호출 → APPROVE 시 git-committer 호출 가능.
5. UI 패치(`TASK_NEEDS_FILES_V2_UI`) 와 병렬 진행 가능 — 서로 독립.
