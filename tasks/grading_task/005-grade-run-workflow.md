# 005 — `.github/workflows/grade-run.yml`

## 목적

`step8_grade.py`를 GitHub Actions에서 실행하는 워크플로. inference 워크플로
(`batch-run.yml`)와 완전 분리.

## 위치

`.github/workflows/grade-run.yml`

## 트리거 (P1 확정)

- 1차: `workflow_dispatch` 만 (수동)
- Phase B: `workflow_run` (batch-run 완료 시 자동 chain) 추가

## 입력 파라미터 (workflow_dispatch)

```yaml
on:
  workflow_dispatch:
    inputs:
      experiment_yaml:
        description: 'Experiment YAML name (without .yaml)'
        required: true
        type: string
      grading_config:
        description: 'Grading config file under batch-runner/grading_configs/'
        required: true
        type: string
        default: 'default_gpt5pro.yaml'
      force:
        description: 'Overwrite existing grade file (skip cache)'
        required: false
        type: boolean
        default: false
      tasks_limit:
        description: 'Limit to first N tasks (smoke). 0 = all'
        required: false
        type: number
        default: 0
      dry_run:
        description: 'Classify only, no LLM calls'
        required: false
        type: boolean
        default: false
```

## 잡 정의

```yaml
permissions:
  contents: write       # grade JSON commit + push
  id-token: write       # Azure OIDC
  pull-requests: write  # (Phase B) optional PR for grade result

jobs:
  grade:
    runs-on: ubuntu-latest
    timeout-minutes: 480   # 8h ceiling. 220 tasks × ~30s × buffer
    
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          cd batch-runner
          pip install -r requirements.txt
      
      - name: Azure Login (OIDC)
        uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
      
      - name: Download inference results from HF
        env:
          HF_TOKEN: ${{ secrets.HF_TOKEN }}
        run: |
          # Resolve repo_id from experiment YAML, then download
          cd batch-runner
          python scripts/download_inference_from_hf.py \
            --experiment "${{ inputs.experiment_yaml }}" \
            --output workspace/step2_inference_results.json
      
      - name: Run grading
        env:
          AZURE_OPENAI_ENDPOINT: ${{ secrets.AZURE_OPENAI_ENDPOINT }}
        run: |
          cd batch-runner
          ARGS=(
            "${{ inputs.experiment_yaml }}"
            --config "grading_configs/${{ inputs.grading_config }}"
            --source local
          )
          [[ "${{ inputs.force }}" == "true" ]] && ARGS+=(--force)
          [[ "${{ inputs.dry_run }}" == "true" ]] && ARGS+=(--dry-run)
          [[ "${{ inputs.tasks_limit }}" != "0" ]] && ARGS+=(--limit "${{ inputs.tasks_limit }}")
          
          python step8_grade.py "${ARGS[@]}"
      
      - name: Commit grade result
        if: inputs.dry_run == false
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add data/grades/
          if git diff --staged --quiet; then
            echo "No grade file changes (likely skip-cache hit)"
            exit 0
          fi
          git commit -m "chore(grades): grade ${{ inputs.experiment_yaml }} via ${{ inputs.grading_config }}"
          git push
      
      - name: Upload grade artifact
        if: always() && inputs.dry_run == false
        uses: actions/upload-artifact@v4
        with:
          name: grade-${{ inputs.experiment_yaml }}
          path: data/grades/${{ inputs.experiment_yaml }}__*.json
          retention-days: 30
```

## Concurrency

```yaml
concurrency:
  group: grade-${{ inputs.experiment_yaml }}-${{ inputs.grading_config }}
  cancel-in-progress: false
```

→ 같은 (exp, config) 조합 동시 실행 방지. 다른 exp는 병렬 OK.

## Secrets 요구

| Secret | 용도 |
|---|---|
| `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` | OIDC (이미 batch-run에서 사용) |
| `AZURE_OPENAI_ENDPOINT` | Responses API endpoint |
| `HF_TOKEN` | 우리 submission repo에서 inference 결과 다운로드 |

`AZURE_OPENAI_API_KEY`는 **요구하지 않음** — PR #40 / commit `39f70fc`에서
삭제했고, openai SDK가 ENV에서 API KEY를 감지하면 OIDC를 무시하는 회귀
방지가 목적.

## download_inference_from_hf.py (sidecar)

`batch-runner/scripts/download_inference_from_hf.py` — 작은 헬퍼:
- experiment YAML 읽어 `repo_owner`/`repo_id` 확정
- HF Hub에서 `step2_inference_results.json` + `upload/deliverable_files/`
  다운로드
- 로컬 `workspace/` 미러링

Phase A 1차에서 만든다. ~50 라인 수준.

## Phase B 변경 (이 명세에는 미포함, 참고)

- `workflow_run` 트리거 추가:
  ```yaml
  on:
    workflow_run:
      workflows: ["Run GDPVal Batch Experiment"]
      types: [completed]
      branches: [main]
  ```
- 단, TPM 우려로 1차에는 자동 chain 비활성

## 테스트

- 로컬: `act` 또는 GH Actions UI에서 `workflow_dispatch` 수동 트리거
- smoke: `experiment_yaml=exp998_smoke_baseline_sample`, `tasks_limit=3`,
  `dry_run=true` → 분류 결과만 확인
- 통합 smoke: 위 설정에서 `dry_run=false` → 3 task 실 채점 → grade JSON
  commit 확인

## 의존성

- 004 (step8_grade.py)
- 006 (grading_configs/default_gpt5pro.yaml)
- 010 (evals_submitter 삭제 — 동일 PR에 포함)

## 비고

- inference 워크플로(`batch-run.yml`)의 6h step timeout 이슈(PR #41)와는
  무관 — grading은 별도 잡이고, 220 tasks 순차 채점이 6h 넘으면 단순히
  job-level 8h timeout으로 보호
- HF에 grade JSON을 추가로 push할지는 Phase B에서 결정. 1차에서는 git
  commit만 (dashboard가 git에서 읽음)
