# Task: Azure DefaultAzureCredential 인증 전환

**Task ID**: 00002  
**Created**: 2026-03-25  
**Priority**: Critical (Blocker)  
**Status**: Planning  
**Owner**: hyeonsangjeon  
**Depends on**: None (blocks all exp013-024 runs)

---

## 🎯 Problem

MS 내부 보안 정책이 `disableLocalAuth=true`를 강제하며, 어떤 방법으로도 되돌릴 수 없음:
- `az rest --method PATCH` → 즉시 `true`로 롤백
- `Set-AzCognitiveServicesAccount -DisableLocalAuth $false` → 즉시 롤백
- `SecurityControl=Ignore` 태그 → 효과 없음
- API Key 조회 자체 차단 (`az cognitiveservices account keys list` → BadRequest)

**결과**: API Key 기반 인증이 영구 차단됨. 모든 exp013-024 실험이 403 에러로 실패.

**검증 완료**: `DefaultAzureCredential` (Entra ID 토큰) 인증은 정상 작동 확인.
```python
# 로컬에서 az login 후 성공 확인 (2026-03-24)
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
client = AzureOpenAI(azure_endpoint=..., azure_ad_token_provider=token_provider, ...)
# → gpt-5.4 호출 성공, "Hello!" 응답 확인
```

---

## 🛠️ Solution: DefaultAzureCredential Fallback

### 인증 우선순위

1. **DefaultAzureCredential** (Entra ID 토큰) — 우선 시도
   - 로컬: `az login` 토큰 자동 사용
   - GitHub Actions: OIDC Federated Credential (Phase 2)
   - Azure VM/Container: Managed Identity
2. **API Key** (fallback) — `AZURE_OPENAI_API_KEY` 있으면 사용
   - Key 인증 가능한 외부 환경 호환성 유지

---

## 📝 수정 범위

### File 1: `batch-runner/core/llm_client.py`

**create_client()** 수정:

```python
def create_client(
    endpoint: str | None = None,
    api_key: str | None = None,
    api_version: str | None = None,
) -> AzureOpenAI:
    endpoint = endpoint or os.getenv("AZURE_OPENAI_ENDPOINT", DEFAULT_ENDPOINT)
    api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
    api_version = api_version or DEFAULT_API_VERSION

    # Priority 1: DefaultAzureCredential (Entra ID token)
    try:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        credential = DefaultAzureCredential()
        token_provider = get_bearer_token_provider(
            credential, "https://cognitiveservices.azure.com/.default"
        )
        print("   🔐 Auth: DefaultAzureCredential (Entra ID token)")
        return AzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=token_provider,
            api_version=api_version,
            timeout=480,
        )
    except Exception as e:
        # Priority 2: API Key fallback
        if api_key:
            print(f"   🔑 Auth: API Key (DefaultAzureCredential failed: {e})")
            return AzureOpenAI(
                azure_endpoint=endpoint,
                api_key=api_key,
                api_version=api_version,
                timeout=480,
            )
        raise ValueError(
            f"No Azure credentials available.\n"
            f"  - DefaultAzureCredential failed: {e}\n"
            f"  - AZURE_OPENAI_API_KEY not set.\n"
            f"  Run 'az login' or set AZURE_OPENAI_API_KEY."
        )
```

**create_provider_client()** — azure 분기도 동일한 패턴으로 수정.

### File 2: `batch-runner/requirements.txt`

```
azure-identity>=1.15.0
```

### File 3: `batch-runner/step2_run_inference.py`

클라이언트 생성 로그에 인증 방식 표시 — `create_client()` 내부에서 print하므로 추가 수정 불필요. 단, step2의 클라이언트 생성 부분에서 `AZURE_OPENAI_API_KEY` 체크 로직이 있으면 제거 또는 완화:

```python
# BEFORE: API Key 필수 체크
if not endpoint or not api_key:
    print("❌ Missing Azure credentials...")
    sys.exit(1)

# AFTER: endpoint만 체크 (인증은 create_client 내부에서 처리)
if not endpoint:
    print("❌ Missing AZURE_OPENAI_ENDPOINT")
    sys.exit(1)
client = create_provider_client("azure", endpoint=endpoint)
```

---

## 🏗️ Phase 2: GitHub Actions OIDC 인증 (같이 진행)

### 완료된 것 (2026-03-25 01:30)
- ✅ Azure AD App Registration: `gdpval-realworks-github-actions` (appId: `f5e0ecfa-6d29-46b1-bdff-bb19ed3307ba`)
- ✅ Service Principal 생성
- ✅ Cognitive Services OpenAI User 역할 할당
- ✅ Federated Credential 추가 (subject: `repo:hyeonsangjeon/gdpval-realworks:ref:refs/heads/main`)
- ✅ GitHub Secrets 등록: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`

### 남은 수정

**File 4: `.github/workflows/batch-run.yml`**

workflow permissions에 `id-token: write` 추가:
```yaml
permissions:
  contents: write
  pull-requests: write
  actions: write
  id-token: write    # ← OIDC 토큰 발급에 필요
```

Step 2a 바로 앞에 Azure Login step 추가:
```yaml
    - name: 'Azure Login (OIDC)'
      uses: azure/login@v2
      with:
        client-id: ${{ secrets.AZURE_CLIENT_ID }}
        tenant-id: ${{ secrets.AZURE_TENANT_ID }}
        subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
```

---

## ✅ Implementation Checklist

### Phase 1: 코드 수정
- [ ] `llm_client.py` 수정 (DefaultAzureCredential 우선 + API Key fallback)
- [ ] `requirements.txt`에 `azure-identity` 추가
- [ ] `step2_run_inference.py`에서 API Key 필수 체크 완화

### Phase 2: GitHub Actions OIDC
- [x] Azure AD App Registration: `gdpval-realworks-github-actions`
- [x] Service Principal 생성
- [x] Cognitive Services OpenAI User 역할 할당
- [x] Federated Credential 추가 (main branch)
- [ ] Federated Credential 추가 (workflow_dispatch용 — 아래 참고)
- [x] GitHub Secrets: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`
- [ ] workflow에 `azure/login@v2` 추가
- [ ] workflow permissions에 `id-token: write` 추가

### Phase 3: workflow_dispatch Federated Credential

Federated Credential의 `subject`가 `ref:refs/heads/main`인데, `workflow_dispatch`로 트리거하면 subject가 다를 수 있음. 필요하면 추가:

```bash
az ad app federated-credential create \
  --id f5e0ecfa-6d29-46b1-bdff-bb19ed3307ba \
  --parameters '{
    "name": "gdpval-github-actions-dispatch",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:hyeonsangjeon/gdpval-realworks:environment:production",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

또는 workflow에 `environment: production`을 설정하고 GitHub에서 해당 environment를 만들어야 함. 만약 main branch에서 workflow_dispatch를 트리거하면 기존 credential로 충분할 수 있음 — 먼저 테스트 후 필요하면 추가.

### Phase 4: Node.js 24 업데이트
- [ ] `.github/workflows/batch-run.yml`에서 deprecated actions 업데이트:
  - `actions/checkout@v4` → `actions/checkout@v5` (또는 최신)
  - `actions/setup-python@v5` → 최신 Node24 호환 버전 확인
  - `actions/upload-artifact@v4` → `actions/upload-artifact@v5`
  - `peter-evans/create-pull-request@v6` → `peter-evans/create-pull-request@v7`
- [ ] 최신 버전이 없는 경우 env에 추가:
  ```yaml
  env:
    PYTHON_VERSION: '3.11'
    FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: 'true'
  ```
- [ ] `.github/workflows/deploy.yml`도 동일하게 업데이트

### Phase 5: 파일명 Sanitize (GitHub Actions artifact 에러 수정)

LLM이 생성한 deliverable 파일명에 NTFS 금지 문자(콜론 `:`, 따옴표 `"` 등)가 포함되면 `actions/upload-artifact`가 실패함.
예: `Undercover Operations Guide: Employee Evaluation.pdf`

**File 5: `batch-runner/core/subprocess_runner.py`**

`_execute_safely()` 안 파일 수집 부분에서 파일명 sanitize:

```python
# 기존
output_files.append({
    "filename": file_path.name,
    "content": file_path.read_bytes()
})

# 수정 — NTFS 금지 문자 치환
import re
sanitized_name = re.sub(r'[:"<>|*?\r\n]', '_', file_path.name)
output_files.append({
    "filename": sanitized_name,
    "content": file_path.read_bytes()
})
```

---

## 🔗 Related

| Item | Description |
|------|-------------|
| TASK 00001 | GPT-5.4 Reasoning Ablation Study (blocked by this) |
| exp013 | 192/220 실패 (403 AuthenticationTypeDisabled) |
| exp021 | artifact 업로드만 실패, inference는 성공 (인증 창에서 돌아감) |
| `llm_client.py` | 인증 로직 변경 대상 |
| `step2_run_inference.py` | API Key 필수 체크 완화 대상 |

---

## 📝 Copilot Prompt

```
## Task: DefaultAzureCredential 전환 + workflow OIDC + Node.js 24 업데이트

⚠️ 커밋/푸시 하지 마.

TASK 문서: /Users/hsjeon/git/gdpval-realworks/docs/task_00002_azure_credential_migration_2026-03-25.md

### 1. batch-runner/core/llm_client.py
- create_client()와 create_provider_client()의 azure 분기: DefaultAzureCredential 우선 → API Key fallback
- 인증 방식 로그 출력 (🔐 / 🔑)

### 2. batch-runner/requirements.txt
- azure-identity>=1.15.0 추가

### 3. batch-runner/step2_run_inference.py
- azure provider 분기에서 api_key 필수 체크 제거, endpoint만 필수

### 3b. batch-runner/core/code_interpreter.py (⚠️ High priority — Codex review)
- __init__에서 AzureOpenAI(api_key=...) 직접 생성하고 있음 (라인 37-40)
- llm_client.py와 동일한 패턴으로 DefaultAzureCredential 우선 → API Key fallback 적용
- 수정 전:
  ```python
  self.client = AzureOpenAI(
      api_key=api_key or os.getenv("AZURE_OPENAI_API_KEY"),
      azure_endpoint=endpoint or os.getenv("AZURE_OPENAI_ENDPOINT"),
      api_version=api_version,
  )
  ```
- 수정 후: DefaultAzureCredential 우선 시도, 실패시 api_key fallback (llm_client.py의 create_client()와 동일한 로직)

### 3c. batch-runner/core/executor.py
- CodeInterpreterRunner 생성 부분 (라인 56)에서 api_key를 전달하고 있음
- DefaultAzureCredential 전환 후에도 호환되는지 확인

### 4. .github/workflows/batch-run.yml

4a. permissions에 추가:
  id-token: write

4b. Step 2a 앞에 Azure Login step 추가:
  - name: 'Azure Login (OIDC)'
    uses: azure/login@v2
    with:
      client-id: ${{ secrets.AZURE_CLIENT_ID }}
      tenant-id: ${{ secrets.AZURE_TENANT_ID }}
      subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

4c. Node.js 20 deprecated actions 업데이트:
  - actions/checkout@v4 → actions/checkout@v5 (없으면 v4 유지 + FORCE_JAVASCRIPT_ACTIONS_TO_NODE24)
  - actions/setup-python@v5 → 최신 Node24 호환 버전 확인
  - actions/upload-artifact@v4 → actions/upload-artifact@v5
  - peter-evans/create-pull-request@v6 → peter-evans/create-pull-request@v7
  최신 버전 없으면 env에 FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true 추가.

### 5. .github/workflows/deploy.yml
- 동일하게 Node.js 20 deprecated actions 업데이트

### 6. batch-runner/core/subprocess_runner.py
- _execute_safely()의 파일 수집 부분에서 파일명 sanitize 추가
- NTFS 금지 문자 (: " < > | * ? \r \n)를 언더스코어(_)로 치환
- LLM이 생성한 파일명에 콜론 등이 포함되면 actions/upload-artifact가 실패하는 문제 수정

### 점검
- [ ] id-token: write 권한 있는지
- [ ] azure/login@v2가 Step 2a 전에 위치하는지
- [ ] DefaultAzureCredential이 우선 사용되는지
- [ ] Node.js 24 경고 사라지는지
- [ ] 기존 Anthropic/OpenAI 경로에 영향 없는지
- [ ] step2에서 api_key 없어도 에러 안 나는지
- [ ] subprocess_runner.py에서 파일명 sanitize가 적용되는지 (콜론 등 치환)
- [ ] code_interpreter.py에서 DefaultAzureCredential이 적용되는지 확인
- [ ] executor.py의 CodeInterpreterRunner 생성이 호환되는지 확인

⚠️ 커밋/푸시 하지 마. 수정 파일 목록과 요약 보여줘.
```

---

## 🚀 로컬 실행 가이드 (수정 후)

```bash
cd ~/git/gdpval-realworks/batch-runner

# API Key unset (DefaultAzureCredential 강제)
unset AZURE_OPENAI_API_KEY
export AZURE_OPENAI_ENDPOINT="https://dlstmvprtus-wingnut0310-ai.openai.azure.com/"

# Step 0-1 (이미 HF에 데이터 있으면 스킵 가능)
bash step0_bootstrap.sh experiments/exp013_GPT54_reasoning_high.yaml
bash step1_prepare_tasks.sh experiments/exp013_GPT54_reasoning_high.yaml

# Step 2 실행 (az login 토큰으로 인증)
bash step2_run_inference.sh condition_a

# Step 3-7
bash step3_format_results.sh
bash step4_fill_parquet.sh
bash step5_validate.sh
bash step6_report.sh
bash step7_upload_hf.sh --test
```