# TASK_NEEDS_FILES_V2_GUARDRAILS — Policy Snapshot Guardrails

> 후속 작업. BATCH PR(`feature/needs-files-v2-batch` `05befc8`)의 extreme-reasoner APPROVE-WITH-CONDITIONS 5개 조건 전부 해소.

## Goal
비-default 정책 전환 시점에 발생할 수 있는 silent regression 차단:
1. manifest active_policy 스냅샷 ↔ 런타임 NEEDS_FILES_POLICY 불일치 raise/warn
2. v1 manifest에서 비-default policy_result 거짓 동치 금지
3. step5_validate에서 비-default 정책 사용 시 WARNING + JSON caveat
4. manifest 생성 시 confidence_distribution 로그 (telemetry)
5. needs_files.py docstring에 정책 스냅샷 시맨틱 명시

핵심 불변식:
- default policy=deliverable_only 환경에서 동작 변화 0 (raise/warn 발생 0)
- BATCH PR의 모든 기존 동작 유지

## Scope
**수정**:
- `batch-runner/core/needs_files.py` — 조건 1, 2, 5
- `batch-runner/core/repo_bootstrapper.py` — 조건 4 (로그 breadcrumb)
- `batch-runner/step5_validate.py` — 조건 3 (WARNING + JSON caveat)

**신규 테스트**:
- `batch-runner/tests/test_policy_guardrails.py` — 조건 1·2·3 단위 테스트
  - manifest active_policy != env 시 raise (strict mode)
  - default 환경에선 raise 안 함
  - v1 manifest + 비-default policy_result → raise/None
  - step5_validate WARNING + JSON caveat 출력 검증 (subprocess)

**손대지 않을 곳**:
- `core/prompt_classifier.py`, `core/config.py` (BATCH에서 완성됨)
- `step0`/`step1`/`step2`/`step3`/`fill_parquet` 등 (manifest 소비자, API 유지)
- `src/`, `dashboard/`, `scripts/`, `tasks/*REPORT.md`, README

## Design

### 조건 1 — active_policy 불일치 감지
`NeedsFilesManifest._load` 또는 `__init__` 끝에:
```python
manifest_policy = self.summary.active_policy  # 신규 키, v2만
runtime_policy = os.environ.get("NEEDS_FILES_POLICY", "deliverable_only")
strict = os.environ.get("NEEDS_FILES_STRICT", "0") == "1"
if manifest_policy is not None and manifest_policy != runtime_policy:
    msg = (f"Manifest active_policy='{manifest_policy}' != runtime NEEDS_FILES_POLICY='{runtime_policy}'. "
           "Manifest is a snapshot; regenerate or unset NEEDS_FILES_POLICY.")
    if strict:
        raise ValueError(msg)
    else:
        warnings.warn(msg, RuntimeWarning)
```
v1 manifest는 `manifest_policy is None` → skip (default 시뮬레이션).

### 조건 2 — v1 fallback policy_result
`.policy_result(task_id, policy)`에서:
```python
entry = self._tasks.get(task_id, {})
policy_results = entry.get("policy_results")
if policy_results is None:
    if policy == "deliverable_only":
        return entry.get("needs_files", False)
    raise ValueError(f"policy_result('{policy}') unavailable on v1 manifest; regenerate.")
return policy_results.get(policy, False)
```

### 조건 3 — step5_validate WARNING
manifest 로드 직후:
```python
active_policy = manifest.summary.active_policy or "deliverable_only"
if active_policy != "deliverable_only":
    print(f"[WARN] step5_validate: manifest active_policy='{active_policy}'. "
          f"success_rate definition differs from baseline 'deliverable_only'.", file=sys.stderr)
report["policy_caveat"] = active_policy if active_policy != "deliverable_only" else None
```

### 조건 4 — confidence_distribution 로그
`_generate_manifest_from_dir` 끝, manifest 저장 직후:
```python
logger.info(f"[manifest] confidence={summary['confidence_distribution']}")
```
(또는 print/stderr — 일관성 있는 방식)

### 조건 5 — docstring
`core/needs_files.py` module docstring 또는 `NeedsFilesManifest` 클래스 docstring에 추가:
```
The manifest's `_summary.active_policy` field is a snapshot taken at manifest generation time.
Runtime changes to NEEDS_FILES_POLICY do NOT automatically re-evaluate the manifest. If you change
the policy, regenerate the manifest (re-run step0). Setting NEEDS_FILES_STRICT=1 makes a snapshot
vs runtime mismatch raise instead of warn.
```

## Acceptance Criteria
- [ ] 5개 조건 코드 반영
- [ ] 신규 테스트 파일 `test_policy_guardrails.py` — 단위 테스트 통과
- [ ] BATCH PR의 기존 테스트(`test_prompt_classifier.py`, `test_resolve_needs_files.py`) 회귀 없음
- [ ] default 환경에서 raise/warn 발생 0 (regression invariant)
- [ ] 변경 파일이 명세된 3개(수정) + 1개(신규 테스트) + spec = 5개
- [ ] step1/step2/fill_parquet/step3 무수정
- [ ] secrets 노출 0

## Failure Policy
- 기존 테스트 회귀 → REJECT, 가드레일 로직 재검토
- first-reviewer REJECT 1회 재시도

## Out of Scope
- default 정책 전환 결정 (별도 회의)
- 끝난 실험 backfill (TASK_NEEDS_FILES_V2_BACKFILL)
- UI docs 통일 (별도)
