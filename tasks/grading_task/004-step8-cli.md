# 004 — `step8_grade.py` CLI

## 목적

단일 실험에 대해 grading 파이프라인을 실행하는 엔트리포인트.
- 실험 결과 (`step2_inference_results.json` 또는 HF submission repo) 로드
- 220 태스크 순회, Grader 호출
- 4-tuple cache key 검사 (skip/force)
- 결과를 `data/grades/<exp_id>__<judge>__<rubric_sha>__<prompt_v>.json`로 저장

## 위치

`batch-runner/step8_grade.py`

## CLI 시그니처

```bash
python step8_grade.py <experiment_yaml_name> \
  --config grading_configs/<config_name>.yaml \
  [--force] \
  [--dry-run] \
  [--tasks <task_id1,task_id2,...>] \
  [--limit N] \
  [--source local|hf]
```

### 인자

| 인자 | 필수 | 기본 | 설명 |
|---|---|---|---|
| `<experiment_yaml_name>` | ✓ | — | 확장자 제외, 예: `exp025_GPT54_high_postfix` |
| `--config` | ✓ | — | grading config 경로 |
| `--force` | | False | 동일 4-tuple grade 파일 있어도 덮어쓰기 |
| `--dry-run` | | False | 채점 안 함. 분류 결과(precheck/judge 수)만 출력 |
| `--tasks` | | (전체) | 일부 task만 채점 (디버그용, 콤마 구분) |
| `--limit` | | (전체) | 처음 N개만 (smoke용) |
| `--source` | | `local` | `local`: workspace/step2_inference_results.json, `hf`: submission repo에서 download |

## 동작 흐름

```python
def main():
    args = parse_args()
    
    # 1. Load grading config
    config = yaml.safe_load(open(args.config))
    config["__config_hash"] = hash_yaml_content(args.config)  # cache key용
    
    # 2. Load experiment YAML (for repo_id, condition info)
    exp_yaml = load_experiment_yaml(args.experiment_yaml_name)
    
    # 3. Resolve inference results
    if args.source == "local":
        inf_results = load_local_inference_results(args.experiment_yaml_name)
    else:
        inf_results = download_hf_submission(exp_yaml)
    
    # 4. Init RubricLoader, fetch rubric_sha
    loader = RubricLoader(
        repo_id=config["rubric"]["repo_id"],
        revision=config["rubric"]["revision"],
        cache_dir=config["rubric"]["cache_dir"],
    )
    rubric_sha = loader.rubric_short_sha  # 7 chars
    
    # 5. Compute output path with 4-tuple cache key
    judge_slug = config["judge"]["model"].replace(".", "_")
    prompt_v = config["prompt"]["version"]
    out_path = Path("data/grades") / (
        f"{args.experiment_yaml_name}__{judge_slug}"
        f"__{rubric_sha}__{prompt_v}.json"
    )
    
    # 6. Skip check (P2=a)
    if out_path.exists() and not args.force:
        print(f"SKIP — exists: {out_path}. Use --force to overwrite.")
        sys.exit(0)
    
    # 7. Filter tasks
    tasks = filter_tasks(inf_results, args.tasks, args.limit)
    
    # 8. Init Grader
    grader = Grader(config=config, rubric_loader=loader)
    
    # 9. Dry-run → print classification stats only
    if args.dry_run:
        print_dry_run_stats(tasks, grader)
        sys.exit(0)
    
    # 10. Sequential grading loop (P3=a)
    grade_results = []
    for i, inf_task in enumerate(tasks):
        task = loader.load(inf_task["task_id"])
        deliverable_dir = resolve_deliverable_dir(inf_task)
        tg = grader.grade_task(task, deliverable_dir)
        grade_results.append(tg)
        print(f"[{i+1}/{len(tasks)}] {task.task_id[:8]} → {tg.pct:.1f}% "
              f"({tg.total_awarded:.1f}/{tg.total_max})")
        
        # TPM guard delay
        time.sleep(config["tpm_guard"]["min_delay_ms_between_calls"] / 1000)
        
        # Incremental save (every 10 tasks)
        if (i + 1) % 10 == 0:
            save_partial(out_path, grade_results, config, rubric_sha)
    
    # 11. Final save (full JSON per 007 schema)
    save_final(out_path, grade_results, config, rubric_sha)
    
    # 12. Summary print
    print_summary(grade_results)
```

## Exit codes

| Code | 의미 |
|---|---|
| 0 | 성공 (또는 skip) |
| 1 | 일반 에러 |
| 2 | inference results not found |
| 3 | rubric loader 초기화 실패 (HF 네트워크) |
| 4 | judge API 인증 실패 (Azure OIDC) |

## Logging

- stdout: 진행 상황 (task당 1줄)
- stderr: warning / error
- `workspace/grading/<exp_id>__<...>__log.txt`: 상세 로그 (Phase A
  후반부에 추가)

## Resume (Phase A 후반부 / Phase B)

- 1차 PR에서는 incremental save만 (10 task마다 partial 저장)
- 중단 시 partial JSON에서 이미 채점된 task_id를 skip하는 `--resume` 플래그는
  Phase B에서 추가 (TPM 우려로 우선순위 낮음)

## 테스트 (`tests/test_step8_grade.py`)

- `test_skip_when_grade_exists`
- `test_force_overwrites`
- `test_dry_run_no_llm_calls`
- `test_limit_n_tasks`
- `test_tasks_filter`
- `test_exit_2_when_no_inference_results`
- 통합 smoke (mock Grader): 3 task → JSON 생성 → 007 schema validate

## 의존성

- 001 (RubricLoader), 002 (Grader), 006 (config)
- 007 schema 준수
- `core/experiment_config.py` (기존, experiment YAML 파싱 재활용)

## 비고

- step1~7과 동일한 위치(`batch-runner/`)에 둠. 워크플로 `grade-run.yml`이
  이 파일을 호출.
- `--source hf`는 Phase B에서 실제 구현. 1차에선 stub만 (또는 NotImplemented)
