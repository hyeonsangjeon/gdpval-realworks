# GDPVal RealWorks 첫 실행 가이드

먼저 무료로 로컬 대시보드를 열고, 그다음 현재의 3개 태스크 클라우드
스모크 테스트를 실행합니다. GitHub Actions를 처음 써도 따라갈 수 있도록
계정과 권한부터 설명합니다.

## 실행 경로 선택

- **로컬 대시보드:** 약 5분, 무료, 클라우드 계정 불필요
- **3개 태스크 smoke 실험:** 설정 시간 + 모델 실행 시간, GitHub, Azure,
  Hugging Face, 실제 API 사용료 필요

> **중요:** `dry_run: true`는 비용과 원격 쓰기가 없는 시뮬레이션이
> 아닙니다. 모델 호출과 Self-QA를 실행하고, 설정한 Hugging Face 데이터셋을
> 만들거나 재사용하며, 필요하면 relay 체크포인트도 씁니다. Step 5 검증,
> 최종 Step 7 결과 업로드, 결과 PR을 건너뜁니다. 이 3-task smoke는 sample
> size 때문에도 Step 5를 생략합니다.

<p align="center">
   <picture>
      <source media="(max-width: 960px)" srcset="images/readme-first-run-mobile-ko.svg" />
      <img src="images/readme-first-run-ko.svg" alt="무료 로컬 대시보드 경로와 인증 정보가 필요한 3개 태스크 클라우드 실험 경로" />
   </picture>
</p>

## 경로 A: 로컬 대시보드 열기

Git과 Node.js 20 이상이 필요합니다. API 키나 클라우드 계정은 필요 없습니다.

```bash
git clone https://github.com/hyeonsangjeon/gdpval-realworks.git
cd gdpval-realworks
npm ci
npm run dev
```

Vite가 출력한 주소를 브라우저에서 여세요. GitHub Pages용 base path가 있어
로컬 주소도 보통 `/gdpval-realworks/`로 끝납니다.

CI와 같은 데이터·프로덕션 검증을 실행하려면 다음을 사용합니다.

```bash
npm run aggregate
npm run test:aggregate
npm run build
```

완성된 사이트는 `dist/`에 생성됩니다. 이 경로는 저장소 데이터를 읽을 뿐
LLM을 호출하지 않습니다.

## 경로 B: GitHub Actions에서 실제 태스크 3개 실행

**Smoke test**는 설정 오류를 찾기 위해 실제 태스크를 소량만 실행하는
테스트입니다. **Self-QA**는 생성 모델이 자기 결과를 검사하고 재시도하는
과정이며 독립 채점이 아닙니다. **Relay**는 끝나지 않은 태스크를 다음 Actions
job에서 이어갑니다. **OpenID Connect(OIDC)**는 Azure client secret을 저장하지
않고 job에 단기 Azure 권한을 부여합니다.

체크인된 스모크 설정은 Azure 배포 `gpt-5.2-chat`을 사용하고 3개 태스크를
선택하며 Self-QA를 최대 3회 재시도할 수 있습니다. Step 6은 먼저
`gpt-5.4-pro`를 순차적으로 최대 2회 호출합니다. 이 경로에서 오류가 나면
`gpt-5.2-chat` fallback을 1회 시도하며, 오류 전에 완료된 호출도 과금될 수
있습니다. 따라서 시간과 비용은 출력 크기, 재시도, 쿼터, 사용 가능한
deployment, Azure 가격에 따라 달라집니다.

### 1. 계정 준비

다음이 필요합니다.

- GitHub 계정과 이 저장소의 fork
- Azure 구독, Azure OpenAI 리소스, 필수 `gpt-5.2-chat` 배포. 기본 2-call
   report 경로를 사용하려면 선택적으로 `gpt-5.4-pro` 배포도 필요
- Microsoft Entra 앱 등록 권한과 해당 Azure OpenAI 리소스에
  **Cognitive Services OpenAI User** 역할을 부여할 권한
- 쓰기 토큰을 만들 수 있는 Hugging Face 계정

학교나 회사가 Azure tenant를 관리한다면 관리자에게 앱 등록과 역할 부여를
요청하세요. OIDC를 client secret이나 Azure OpenAI API key로 바꾸지 마세요.
배치 워크플로는 federated identity를 기준으로 설계되어 있습니다.

### 2. Fork와 개인 Hugging Face 대상 설정

GitHub에서 저장소를 fork합니다. 내 fork에서
[`batch-runner/experiments/exp998_smoke_baseline_sample.yaml`](../batch-runner/experiments/exp998_smoke_baseline_sample.yaml)을
열고 `data.source`의 소유자만 바꿉니다.

```yaml
data:
  source: "YOUR_HF_USERNAME/exp998_smoke_baseline_sample"
```

데이터셋 저장소 이름은 YAML 파일 stem과 같게 유지하세요. 새로 만든 일회성
테스트 dataset을 사용해야 합니다. Step 0은 새 대상을 기본적으로 **public
dataset**으로 만듭니다. 기존 대상에 `data/`로 시작하는 경로가 하나도 없으면
아무것도 삭제하지 않고 fail-closed합니다. 확인 후 새 일회성 target을 쓰거나
partial repository를 명시적으로 제거하세요. `data/` 경로가 있으면 기존
snapshot을 재사용합니다. 이 snapshot에는 source-derived
`step0_needs_files_manifest.json`도 있어야 합니다. task/policy identity가
없거나 prompt/taxonomy/rubric/reference assignment, reference
path/SHA-256/size까지 어긋나면 중단하며 stripped data에서 manifest를 재생성하지
않습니다. 재사용 target의 submitter text/file/URL/URI column과 physical
deliverable tree도 비어 있어야 합니다. 새 target은 pinned public-source
revision 하나에서 base data와 parquet가 선언한 reference만 받아 만듭니다. 전체
source snapshot, manifest, reference, 비운 submitter state와 고정 payload digest를
target 생성 전에 검증합니다. create와 upload는 각각 한 번만 시도하며 upload
결과가 불명확하면 재시도하거나 삭제하지 않고 점검할 수 있게 보존합니다.
재사용 target은 exact full-SHA HEAD를 fresh staging에 받고 canonical column,
projection, manifest, 전체 reference tree, empty submitter state를 통과한 뒤에만
이전 local snapshot을 교체합니다.

나중에 non-dry Step 7을 실행하면 CAS로 원격 `data/**`, `deliverable_files/**`,
`self_report.json`을 새 결과로 교체합니다. 보존해야 할 dataset을 가리키면 안 됩니다.

수정 내용을 fork의 기본 `main` 브랜치에 커밋하세요. YAML에 토큰, 키,
비밀번호를 넣지 마세요.

### 3. Azure OIDC 1회 설정

워크플로는 [`azure/login`](../.github/workflows/batch-run.yml)과 GitHub의
단기 OIDC 토큰을 사용합니다. 포털에서는 다음 순서로 설정할 수 있습니다.

1. **Microsoft Entra admin center**에서 **App registrations**를 열고 이
   fork용 앱을 만듭니다.
2. **Application (client) ID**와 **Directory (tenant) ID**를 기록합니다.
3. **Certificates & secrets > Federated credentials > Add credential**을
   엽니다.
4. **GitHub Actions deploying Azure resources**를 선택합니다.
5. 내 GitHub owner와 repository를 입력하고 **Branch**, `main`을 선택합니다.
   subject는
   `repo:YOUR_GITHUB_OWNER/gdpval-realworks:ref:refs/heads/main`을 나타내야
   합니다.
6. Azure OpenAI 리소스의 **Access control (IAM)**에서 이 앱의 service
   principal에 **Cognitive Services OpenAI User** 역할을 부여합니다.
7. Azure 구독 ID와 이 저장소의 `AzureOpenAI(azure_endpoint=...)` client가
   사용하는 Azure OpenAI **resource endpoint**를 기록합니다. Foundry에서
   복사한다면 Foundry project URL이나 `/openai/v1/` base URL이 아니라 Azure
   OpenAI resource endpoint를 사용합니다.

Microsoft 공식 절차는
[GitHub Actions에서 OpenID Connect 사용](https://learn.microsoft.com/azure/developer/github/connect-from-azure-openid-connect)을
참고하세요. 이 workflow는 `main` 브랜치 이름을 요구하며 federated
credential도 그 exact branch에 맞춰야 합니다.

### 4. Hugging Face 토큰 만들기

[Hugging Face 토큰 설정](https://huggingface.co/settings/tokens)에서 공개
원본 dataset을 읽고 일회성 대상 dataset을 생성, 수정, 삭제할 수 있는
token을 만듭니다. 계정이 fine-grained 권한을 지원하면 이 작업에만 한정된
전용 token을 사용하세요.

### 5. Repository secrets 등록

GitHub fork의 **Settings > Secrets and variables > Actions > New repository
secret**에서 다음을 추가합니다.

| Secret | 값 |
|---|---|
| `AZURE_CLIENT_ID` | Entra 앱의 client ID |
| `AZURE_TENANT_ID` | Entra directory tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |
| `AZURE_OPENAI_ENDPOINT` | `AzureOpenAI(azure_endpoint=...)`용 Azure OpenAI resource endpoint. Foundry project URL은 아님 |
| `HF_TOKEN` | Hugging Face 전용 write token |

이 경로에는 `AZURE_OPENAI_API_KEY`를 추가하지 마세요. `GITHUB_TOKEN`은
GitHub가 자동으로 제공합니다.

나중에 non-dry run을 하려면 **Settings > Actions > General > Workflow
permissions**에서 **Read and write permissions**와 Actions의 PR 생성을
허용하세요. 조직 정책에 따라 관리자가 설정해야 할 수 있습니다.

### 6. 스모크 워크플로 실행

1. fork의 **Actions** 탭을 열고 요청이 나오면 workflow를 활성화합니다.
2. **Run GDPVal Batch Experiment**를 선택합니다.
3. `main` 브랜치에서 **Run workflow**를 누릅니다.
4. `experiment_yaml`에 `exp998_smoke_baseline_sample`을 입력합니다.
5. `experiment_name`, `relay_lineage_id`, `source_sha`,
   `sandbox_image_digest`는 비워 두고, `relay_run`은 `0`, `wall_timeout`은
   `290`으로 둡니다.
6. 위 비용 경고를 확인한 뒤 `dry_run`을 `true`로 설정하고 실행합니다.

workflow는 checkout이나 cloud 접근 전에 exact `main`이 아닌 dispatch ref를
거부하고 그 commit을 relay 전체에 고정합니다. GitHub concurrency는 durable
queue가 아니므로 같은 `data.source`를 공유하는 실행을 겹치지 마세요.
Relay checkpoint는 그 exact `data.source`를 사용합니다. progress, identity,
fingerprint, 참조 deliverable을 복원·검증할 수 없으면 Azure login 전에
continuation이 실패합니다.
Step 0 뒤에는 비변경 authorization check로 그 exact dataset의 write 권한을
model spend 전에 요구합니다. 각 relay marker는 immutable HF revision 하나와
exact sandbox image digest, SHA-256/size file manifest를 가리킵니다.
Step 0은 pinned source projection을 인증하고 declared reference set만 받으며,
재사용 target의 exact HEAD를 local 설치 전에 검증합니다. Step 2와 각 executor는
모든 reference를 upload/copy 직전에 재검증하고, 누락·변경·copy 실패는 model
또는 generated code 실행 전에 중단합니다.
Cleanup은 현재 tree의 lineage만 제거하며 과거 HF revision은 지우지 않습니다.
실패한 작업은 orphan generation을 남길 수 있으므로 이 public 일회성 target에
민감 자료를 사용하지 마세요.

non-dry Step 7은 원격 output을 삭제하기 전에 canonical parquet shard 하나,
task 소유 output path, canonical repository URL/URI, parquet 선언과 local
deliverable tree의 exact 일치를 요구합니다. 실패 task는 이전 run의 output
metadata를 남길 수 없습니다. Step 4와 Step 7은 model 실행 뒤 각 source row를
manifest v4에 다시 대조합니다. 게시에는 repository, prepared fingerprint,
Step 2 result fingerprint, ordered task ID, result task set이 현재 workspace와
run-specific publication generation까지 일치하는 non-dry local
`self_report.json`이 필요합니다. 새 Step 1은 이전 run의 finalized output을
무효화하고 relay leg는 최초 generation을 유지합니다. Parquet submitter
text/files/URL/URI도 같은 Step 2 결과와 일치해야 합니다. local dry-run report를
만들었다면 Step 7 전에 `bash step6_report.sh --no-narrative`를 다시 실행하세요.
self-report의 task별 summary와 deliverable 파일도 검증된 Step 2 result와 같아야
합니다. Step 0 validated HF HEAD를 CAS parent로 사용하므로 concurrent target 변경은
기존 결과를 덮어쓰지 않고 실패합니다.

스모크 설정은 provider-hosted `code_interpreter`를 사용합니다. 저장소의
Docker sandbox나 agentic preflight를 실행하는 테스트가 아닙니다.

### 7. 성공 상태 확인

예상 경로는 다음과 같습니다.

| 단계 | 스모크에서 예상되는 동작 |
|---|---|
| Inspect mode | cloud credential 없이 입력 파일명, 안전한 YAML 구조, 일반 workflow 허용 mode를 사전 검사 |
| 전체 config 검증 | Hugging Face bootstrap 전에 전체 experiment config를 load하고 validate |
| Step 0 | 새 target을 공개 생성하거나 `data/`와 canonical source-derived manifest가 있는 대상을 재사용. partial/legacy/inconsistent target은 자동 삭제 없이 중단 |
| Step 1 | seed에 따라 태스크 3개 선택 |
| Step 2 | 모델 호출, 산출물 생성, 같은 모델의 Self-QA 실행 |
| Steps 3-4 | JSON/Markdown 결과와 3-row Parquet 생성 |
| Step 5 | `dry_run`이 true이고 sample도 3개이므로 건너뜀 |
| Step 6 | `gpt-5.4-pro` 2-call report와 `gpt-5.2-chat` fallback을 시도. Narrative 실패 시 게시 전에 model-free report를 반드시 생성 |
| Step 7과 결과 PR | `dry_run`이므로 건너뜀 |

credentialed batch job이 마지막 `always()` 단계에 도달하면
`batch-results-<run_id>` Actions artifact 업로드를 시도합니다. inspect-mode의
초기 거부나 job 시작 실패에서는 artifact가 없을 수 있습니다. 업로드에
성공하면 30일 보관됩니다. 완료된 Actions run 아래의 **Artifacts**에서
`batch-results-<run_id>`를 내려받아 압축을 푸세요. archive root에는
`workspace/`와 `results/`가 있습니다.

먼저 다음을 확인하세요.

- `workspace/step2_inference_results.json`: 태스크별 상태
- `workspace/upload/deliverable_files/<task_id>/`: 생성 파일
- `results/exp998_smoke_baseline_sample/`: 포맷된 결과와 리포트
- Actions log: 재시도, 쿼터, 리포트 경고

Self-QA는 산출물을 만든 같은 모델의 재시도 신호입니다. 독립 채점이 아니며
산출물이 전문적으로 정확하다는 증거도 아닙니다.

## 문제 해결

| 증상 | 확인할 것 |
|---|---|
| workflow가 보이지 않음 | Actions가 활성화됐고 YAML이 fork의 `main` 브랜치에 있는지 확인 |
| `AADSTS700213` 또는 federated identity 불일치 | owner, repository, branch, federated subject가 fork와 정확히 같은지 확인 |
| Azure login은 성공하지만 inference가 403 | OpenAI 역할, endpoint, deployment 접근 권한 확인 |
| deployment를 찾지 못함 | 스모크 설정은 `gpt-5.2-chat` 이름을 기대함 |
| Hugging Face 401 또는 403 | token 권한과 `data.source`가 내 namespace인지 확인 |
| HF 대상이 예상과 다르게 동작 | 정확히 `exp998_smoke_baseline_sample` 이름의 새 일회성 public dataset 사용. 필요한 파일이 있는 dataset은 재사용하지 않음 |
| Step 6이 경고인데 job은 계속됨 | PR/HF 게시 전에 model-free fallback report 생성과 identity 검증을 반드시 통과해야 함 |
| 결과 PR이 없음 | `dry_run: true`에서는 정상 |
| Step 5가 생략됨 | 3개 이하 샘플에서는 정상 |
| Relay 복원 실패 | 무작정 재시작하지 말고 exact `data.source` checkpoint와 lineage 확인. 전체 태스크 재실행 대신 continuation이 fail-closed |

## 스모크 다음 단계

기존 실험 YAML을 새 이름으로 복사하고 `sample_size: 3`을 유지한 채 변수를
하나씩 바꾸세요. 샘플을 늘리기 전에 artifact를 검토해야 합니다.
`dry_run`을 해제하면 결과를 게시하고 결과 PR을 만들지만, 3-task 설정이
220-task 전체 실행으로 바뀌는 것은 아닙니다.

전체 실행은 큰 모델 쿼터를 사용할 수 있고 여러 relay job이 필요할 수
있습니다. 외부 채점은 별도 파이프라인입니다. 실행 모드를 바꾸거나 220개로
확대하기 전에 [Batch Runner 문서](../batch-runner/README_KR.md)와
[sandbox 문서](../batch-runner/sandbox/README.md)를 읽으세요.

한 번만 시험했다면 일회성 Hugging Face dataset을 삭제하고, 전용 token을
폐기하며, 5개 repository secret과 fork용 federated credential을 삭제하세요.
추가 실험을 할 계획일 때만 유지합니다.