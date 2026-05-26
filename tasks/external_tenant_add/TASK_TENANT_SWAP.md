# TASK_TENANT_SWAP — Dual-tenant Azure budget failover (spec only)

> 작성: 2026-05-26
> 상태: **spec only — 구현 보류** (먼저 grading 검증/cost 측정 후 필요성 재평가)

## 배경

내부 Microsoft 테넌트 외에 **external tenant**가 별도 $2,500/월 예산으로 사용 가능. 단일 grade-run이 단일 tenant 한도 도달 직전에 다른 tenant로 자동 swap하면 가용 capacity가 사실상 2배 (월 12회 → 24회 풀런).

조건:
- 자동: pre-run budget check → 한도 넘을 예상이면 external로 swap
- 수동 override: `tenant=internal|external|auto` workflow input
- 감사 가능: budget_state.json은 git에 commit (per-run audit trail)

## 디자인 (확정)

### 1. State store
`data/budget_state.json` — 두 tenant의 MTD 사용량 기록.
```json
{
  "schema_version": "1.0",
  "month": "YYYY-MM",
  "tenants": {
    "internal": {
      "monthly_cap_usd": 2500,
      "spent_usd": 0.0,
      "runs": []
    },
    "external": {
      "monthly_cap_usd": 2500,
      "spent_usd": 0.0,
      "runs": []
    }
  }
}
```
- 매월 1일 reset (month 필드 비교 후 새 객체로)
- per-run entry: `{id, cost, at, config, experiment}`

### 2. GH Secrets 명명 규칙
| 변수 | 내부 | 외부 |
|---|---|---|
| Client ID | `AZURE_CLIENT_ID` | `AZURE_CLIENT_ID_EXTERNAL` |
| Client Secret | `AZURE_CLIENT_SECRET` | `AZURE_CLIENT_SECRET_EXTERNAL` |
| Tenant ID | `AZURE_TENANT_ID` | `AZURE_TENANT_ID_EXTERNAL` |
| Subscription | `AZURE_SUBSCRIPTION_ID` | `AZURE_SUBSCRIPTION_ID_EXTERNAL` |
| Endpoint | `AZURE_OPENAI_ENDPOINT` | `AZURE_OPENAI_ENDPOINT_EXTERNAL` |

### 3. Picker
`scripts/select_tenant.py`:
- input: `--estimated-cost`, `--state-file`, `--buffer-usd 50`
- output: stdout에 `internal` / `external` / `block`
- 로직:
  1. month mismatch → state reset
  2. internal.spent + estimated + buffer < internal.cap → return internal
  3. else external.spent + estimated + buffer < external.cap → return external
  4. else → return block (exit 2)

### 4. Recorder
`scripts/record_run_cost.py`:
- input: `--tenant`, `--grade-json`
- 동작: grade JSON의 `cost.estimated_cost_usd` (또는 직접 계산) → state file에 append + spent_usd 합산

### 5. Workflow 통합 (`grade-run.yml`, `grade-cost-sweep.yml` 둘 다)
```yaml
inputs:
  tenant: { type: choice, options: [auto, internal, external], default: auto }

jobs:
  grade:
    steps:
      - name: Select tenant (auto)
        id: tenant
        run: |
          if [[ "${{ inputs.tenant }}" == "auto" ]]; then
            T=$(python scripts/select_tenant.py --estimated-cost 200 --state-file data/budget_state.json)
          else
            T="${{ inputs.tenant }}"
          fi
          echo "selected=$T" >> $GITHUB_OUTPUT
          if [[ "$T" == "block" ]]; then
            echo "::error::Both tenants exhausted. Bump cap or wait for monthly reset."
            exit 2
          fi
      - name: Azure Login
        uses: azure/login@v2
        with:
          client-id: ${{ steps.tenant.outputs.selected == 'external' && secrets.AZURE_CLIENT_ID_EXTERNAL || secrets.AZURE_CLIENT_ID }}
          tenant-id:  ${{ steps.tenant.outputs.selected == 'external' && secrets.AZURE_TENANT_ID_EXTERNAL  || secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ steps.tenant.outputs.selected == 'external' && secrets.AZURE_SUBSCRIPTION_ID_EXTERNAL || secrets.AZURE_SUBSCRIPTION_ID }}
      - name: Run grading
        env:
          AZURE_OPENAI_ENDPOINT: ${{ steps.tenant.outputs.selected == 'external' && secrets.AZURE_OPENAI_ENDPOINT_EXTERNAL || secrets.AZURE_OPENAI_ENDPOINT }}
      - name: Record actual cost
        if: always() && inputs.dry_run == false
        run: |
          python scripts/record_run_cost.py \
            --tenant "${{ steps.tenant.outputs.selected }}" \
            --grade-json "data/grades/${{ inputs.experiment_yaml }}__*.json"
          git add data/budget_state.json
          git commit -m "chore(budget): \$X on ${{ steps.tenant.outputs.selected }} tenant" || true
          git push
```

## Acceptance

- `select_tenant.py` unit tests: 4 cases (internal OK / internal full external OK / both full → block / month reset)
- `record_run_cost.py` unit tests: 3 cases (first run, append, month reset)
- 첫 swap 시나리오 dry run: internal에 90% spent 상태 만들고 trigger → external 자동 선택 확인
- 두 tenant 모두 RUN 1회 성공 — OIDC + endpoint 작동 검증

## 선결 조건 (사용자 작업)

1. **External Azure tenant 결정** — 어떤 subscription/AAD App 사용?
2. **External AAD App federated identity 등록** — `repo:hyeonsangjeon/gdpval-realworks:ref:refs/heads/main` subject
3. **External Azure OpenAI resource** + deployments (gpt-5.4-pro, gpt-5.4, gpt-5.4-mini) 존재 확인
4. **External GH secrets 5개** 등록 (위 명명 규칙)
5. **External tenant 월예산 합의** — $2,500 가정 (필요시 spec 갱신)

## 구현 우선순위

**보류**. 먼저 grading config 검증 (0526_tuesday tasks)을 완료한 후, 실제 단일 tenant 한도가 부족한지 데이터로 확인. 풀런 1~2회로 실비용 측정해서 월 capacity 확정한 후 결정.

## Out of scope

- Azure billing API 실시간 조회 (24h delay 있어 의미 작음, dispatcher 추정으로 충분)
- Slack/email 알림 (별도 task)
- Per-experiment cost cap (per-run cap만 적용)
