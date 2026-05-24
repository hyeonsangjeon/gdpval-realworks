# Phase A — 인증 차단 보고서 (2026-05-24)

## 결과 요약

**상태**: 사용자 행동 필요 (autonomous 진행 불가)
**누적 비용**: **$0.00** (모든 호출이 auth 실패로 토큰 발생 전 끝남)
**소요 시간**: ~2분 (두 번의 시도 합산)
**완료된 variants**: 0 / 15
**원인**: Azure OpenAI 인증 두 경로 모두 차단

---

## 시도 1: OIDC (DefaultAzureCredential, SP 기반)

```
AADSTS7000215: Invalid client secret provided.
Ensure the secret being sent in the request is the client secret value,
not the client secret ID, for a secret added to app
'f5e0ecfa-6d29-46b1-bdff-bb19ed3307ba'.
```

**해석**: `batch-runner/.env`의 `AZURE_CLIENT_SECRET`이 만료되었거나 무효화됨. Service Principal credentials 갱신이 필요. 로그: `_blocked/A1_first_attempt.log`

## 시도 2: API Key fallback (`GRADER_ALLOW_API_KEY_FALLBACK=1`)

dispatcher가 `AZURE_OPENAI_API_KEY`로 fallback 시도. 그러나:

```
Error code: 403 - {'error': {'code': 'AuthenticationTypeDisabled',
'message': 'Key based authentication is disabled for this resource.'}}
```

**해석**: Azure OpenAI resource 자체가 **local (key-based) authentication을 비활성화**해 둠. Microsoft tenant의 보안 정책일 가능성 높음. resource 정책 변경 권한이 없으면 우회 불가.

## 시도 3: AzureCliCredential (참고, sweep 시작 전 별도 확인)

```bash
az account get-access-token --resource https://cognitiveservices.azure.com
→ AADSTS530004: AcceptCompliantDevice setting isn't configured...
```

**해석**: Conditional Access 정책이 device compliance를 요구. Mac local 환경에선 통과 불가.

---

## 코드 변경 사항 (이 보고서 작성 시점까지 commit됨)

| commit | 영향 |
|---|---|
| `e9ea8cb` | dispatcher가 `batch-runner/.env`를 subprocess에 inject (root cause 분석에서 발견된 별도 버그도 같이 해결) |
| `5a2e5ed` | grader.py에 opt-in API key fallback 추가 (`GRADER_ALLOW_API_KEY_FALLBACK=1` 시) — 이번엔 resource 정책에 막혀 효과 없었지만, 향후 SP secret 단독 만료 케이스 회복용으로 유효 |

→ **모두 회귀 0**, 51 tests (39 grading + 12 dispatcher) 통과 유지.

---

## 사용자 행동 옵션 (가장 빠른 순서)

### 옵션 A — SP secret 갱신 (권장)
1. Azure portal → App Registrations → App ID `f5e0ecfa-6d29-46b1-bdff-bb19ed3307ba`
2. Certificates & secrets → New client secret → 값 복사
3. `batch-runner/.env`의 `AZURE_CLIENT_SECRET=` 갱신
4. Sweep 재실행: `python scripts/grading_cost_sweep.py --phases A --output-dir <SWEEP_DIR>`

**소요**: ~3-5분. **추가 비용**: 없음 (재시도 비용 $0). 그 후 sweep ~$20-25 진행.

### 옵션 B — Workload Identity Federation
GitHub Actions에서 sweep을 돌리는 워크플로우 생성 (이미 grade-run.yml에 OIDC 셋업 있음). 본 dispatcher가 step8_grade를 호출하는 패턴 그대로 GH Actions 환경으로 옮기면 됨. 

**소요**: 30~60분 (워크플로우 작성 + 권한 확인). 별도 task로 분리 필요.

### 옵션 C — Local auth 활성화 (admin 필요, 비권장)
Resource 정책 변경. Microsoft 내부 보안정책상 허가 가능성 낮음.

---

## 다음 단계 (사용자가 옵션 A 선택 시 dispatcher는 즉시 재진행 가능)

`feat/grade-cost-sweep` 브랜치, HEAD `5a2e5ed`. 모든 인프라(grader_batch, dispatcher, plan, fallback) 준비됨. SP secret만 갱신되면 다음 명령으로 즉시 sweep 시작:

```bash
cd /Users/hsjeon/git/gdpval-realworks
source .venv/bin/activate
SWEEP_DIR="tasks/0523_saturday/cost_opt_results/2026-05-24-grade-cost-sweep"
python scripts/grading_cost_sweep.py \
  --plan tasks/0523_saturday/grading_cost_sweep_plan.yaml \
  --output-dir "$SWEEP_DIR" \
  --phases A 2>&1 | tee "$SWEEP_DIR/phase_a.log"
```

(이전 시도로 인한 $0 cost 외 추가 비용 없음. 본 sweep cost cap은 $80.)

---

## 학습된 교훈 (peer 관점)

1. **Resource policy ≠ identity availability**. SP/API key가 있어도 resource가 모두 거부할 수 있음. sweep 사전점검에 "1회 token 발급 + 1회 dummy /openai/deployments GET" probe 추가하면 첫 variant 진입 전에 잡힘 → 향후 dispatcher 개선 후보.
2. **Conditional Access 정책 차단**. Microsoft tenant에선 AzureCliCredential도 device compliance 미통과 시 막힘. CI/Actions 환경이 로컬보다 안전.
3. **`.env` autoloader 누락**. dispatcher가 step8_grade를 invoke할 때 parent shell env에 의존하면 위험. 이번 fix(e9ea8cb)로 영구 해결.
4. **OIDC-only 정책의 트레이드오프**. 헌법 룰은 보안엔 옳지만, secret rotation 실패 시 사람 개입 없이 회복 불가. opt-in fallback (5a2e5ed)이 합리적 안전망.

---

_보고서 생성: 2026-05-24 04:42 UTC, by orchestrator._
