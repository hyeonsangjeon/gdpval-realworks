# GDPVal Batch Runner

[OpenAI GDPVal](https://huggingface.co/datasets/openai/gdpval) Gold Subset 220개 태스크에 대해 LLM 실험을 실행하고, 결과를 HuggingFace에 업로드하는 Python 파이프라인입니다.

## 여기서 시작하세요

- **게시된 근거 보기:** [라이브 대시보드](https://hyeonsangjeon.github.io/gdpval-realworks/)를 엽니다.
- **가장 작은 실제 실행 확인:**
  [`exp998_smoke_baseline_sample.yaml`](experiments/exp998_smoke_baseline_sample.yaml)을 봅니다.
- **지원되는 클라우드 경로 실행:**
  내 fork의 [Run GDPVal Batch Experiment](../../../actions/workflows/batch-run.yml)에서
  `experiment_yaml=exp998_smoke_baseline_sample`을 사용합니다.
- **결과 위치 확인:** [결과와 아티팩트](../docs/first-experiment_KR.md#7-성공-상태-확인)를 읽습니다.

첫 실행은 [초보자 가이드](../docs/first-experiment_KR.md)를 따르세요. Azure
OIDC, 일회성 Hugging Face 대상, 비용 경계, 3-task smoke test의 정본 경로입니다.

## 아키텍처

<picture>
  <source media="(max-width: 960px)" srcset="../docs/images/readme-system-map-mobile-ko.svg" />
  <img src="../docs/images/readme-system-map-ko.svg" alt="실험 YAML에서 실행, 산출물, 외부 채점, 대시보드 근거로 이어지는 GDPVal RealWorks 파이프라인" />
</picture>

## 빠른 시작

### 권장 경로: GitHub Actions

1. 이 저장소를 fork하고
  [3-task 샘플 config](experiments/exp998_smoke_baseline_sample.yaml)의
  `data.source`만 내 Hugging Face namespace의 새 일회성 dataset으로 바꿉니다.
2. [초보자 가이드](../docs/first-experiment_KR.md#5-repository-secrets-등록)의
  repository secret 5개를 설정합니다.
3. `main`의
  내 fork의 [Batch workflow](../../../actions/workflows/batch-run.yml)를 열고
  `exp998_smoke_baseline_sample`을 입력하며 내부 relay 필드는 기본값으로 둡니다.
4. 아래 경계를 읽은 뒤 첫 smoke에만 `dry_run: true`를 사용합니다.

> `dry_run: true`여도 Step 0, 모델 호출, Self-QA를 실행하고 relay checkpoint를
> 쓸 수 있습니다. Step 5, 최종 Step 7 게시, 결과 PR을 생략할 뿐 무료 또는
> 원격 쓰기 없는 시뮬레이션이 아닙니다.

### 로컬 단계별 디버깅

Python 3.11, Azure CLI 로그인, 실제 모델 예산, 샘플 YAML에 설정한 일회성
Hugging Face 대상이 필요합니다. Step 0은 HF에 쓰고 Step 2는 모델을 호출합니다.

```bash
cd batch-runner
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
az login

export HF_TOKEN="<전용-HF-write-token>"
export AZURE_OPENAI_ENDPOINT="<Azure-OpenAI-resource-endpoint>"
CONFIG="experiments/exp998_smoke_baseline_sample.yaml"

bash step0_bootstrap.sh "$CONFIG"
bash step1_prepare_tasks.sh "$CONFIG"
bash step2_run_inference.sh condition_a
bash step3_format_results.sh
bash step4_fill_parquet.sh

# 3-task smoke는 Step 5를 생략합니다. 모델 호출 없는 미게시 리포트를 만듭니다.
bash step6_report.sh --no-narrative --dry-run
```

설정 확인만을 위해 Step 7을 실행하지 마세요. 3-row smoke 결과를 의도적으로
게시하려면 `bash step7_upload_hf.sh --test`를 사용하며, 업로드 전에 대상의
원격 `data/**`와 `deliverable_files/**`를 삭제합니다.

## 인증과 환경 변수

| 변수명 | 필수 여부 | 설명 |
|--------|----------|------|
| `HF_TOKEN` | 클라우드 게시 | bootstrap, relay 저장, Step 7에 사용하는 전용 Hugging Face write token |
| `AZURE_OPENAI_ENDPOINT` | Azure | `AzureOpenAI(azure_endpoint=...)`용 Azure OpenAI resource endpoint. Foundry project URL이나 `/openai/v1/` base URL은 아님 |
| `AZURE_CLIENT_ID` | GitHub Actions + Azure | OIDC용 Entra application client ID |
| `AZURE_TENANT_ID` | GitHub Actions + Azure | OIDC용 Entra directory tenant ID |
| `AZURE_SUBSCRIPTION_ID` | GitHub Actions + Azure | `azure/login`용 Azure subscription ID |
| `OPENAI_API_KEY` | OpenAI 사용 시 | 네이티브 OpenAI API 키 |
| `ANTHROPIC_API_KEY` | Anthropic 사용 시 | Anthropic API 키 |

지원되는 GitHub Actions 경로는 `AZURE_OPENAI_API_KEY`를 주입하지 않고
`azure/login`과 OIDC를 사용합니다. 로컬 예시는 `az login`과
`DefaultAzureCredential`로 인증합니다. API-key-only direct runner 동작은 이
첫 실행 계약 밖이며 여기서는 보장하지 않습니다.

## 파이프라인 단계별 상세

### Step 0: 부트스트랩 (`step0_bootstrap.sh`)



- 실험 YAML 경로를 받아 `data.source`에서 대상을 읽음:
  `bash step0_bootstrap.sh experiments/exp998_smoke_baseline_sample.yaml`
- 설정한 public HF dataset이 없으면 `openai/gdpval`을 duplicate
- `data/gdpval-local/`에 로컬 스냅샷 다운로드
- `openai/gdpval`의 full revision 하나를 고정함. deliverable을 비우기 전에
  ordered task identity, policy signal, 선언된 모든 reference의 path,
  SHA-256, byte size를 담은 schema-3 `step0_needs_files_manifest.json`을
  target에 보존
- 매 실행마다 target의 exact HEAD를 새 staging에 받고, local snapshot을
  교체하기 전에 canonical model-input projection(prompt, rubric, sector,
  occupation, reference 선언), manifest bytes, 전체 declared reference tree를
  pinned source 계약과 검증
- 검증: 220행, rubric 컬럼 존재, 선언된 reference가 모두 regular file인지 확인
- 기존 대상에 `data/` 경로가 있을 때만 재사용하며, 없으면 dataset repository를
  자동 삭제하지 않고 중단함. 재사용 대상에도 canonical manifest가 있어야 하며
  stripped data에서 이를 재생성하지 않음. 새 일회성 target을 쓰거나 확인한
  partial/legacy repository를 명시적으로 제거해야 함

### Step 1: 태스크 준비 (`step1_prepare_tasks.py`)

실험 YAML 설정 읽기 → 데이터셋 로드 → 필터 적용 (sector, sample_size) → `workspace/step1_tasks_prepared.json`에 태스크 목록 + 조건 설정 저장.

### Step 2: 추론 실행 (`step2_run_inference.py`)

준비된 태스크 읽기 → 태스크별 LLM 호출 →
`workspace/step2_inference_progress_condition_a.json` 같은 조건별 checkpoint와
`workspace/step2_inference_results_condition_a.json` 같은 최종 결과에 저장.
condition A는 호환성을 위해 legacy alias도 기록하며, 다중 라운드 resume은
`error`/`qa_failed` 태스크를 자동 재실행합니다.

### Step 3: 결과 포맷팅 (`step3_format_results.py`)

추론 결과를 `results/<exp_id>/` 아래에 구조화된 JSON + Markdown 리포트로 변환.

### Step 4: Parquet 병합 (`step4_fill_parquet.py`)

`deliverable_text`와 `deliverable_files`를 base parquet에 병합. 원본 컬럼(rubric_json, rubric_pretty 등) 모두 보존.

### Step 5: 유효성 검증 (`step5_validate.py`)

업로드 전 무결성 검사: 220행, 필수 컬럼, deliverable 파일 경로 등.

### Step 6: 리포트 생성 (`step6_report.py`)

`workspace/result.json`의 실험 identity를 검증하고 엄격한 pre-grading report를
`results/<experiment_id>/report/`에 생성합니다.

- **`report_data.json`** — 구조화된 self-report 데이터
- **`report.md`** — 사람이 읽을 수 있는 실행 요약

workspace 소유 결과에서는 `report_data.json`을
`workspace/upload/self_report.json`으로도 복사합니다. HTML은 생성하지 않으며
외부 채점은 별도 pipeline입니다.

기본 narrative 경로는 `gpt-5.4-pro`를 2회 호출한 뒤 실험 모델 fallback을
1회 시도합니다. GitHub workflow는 게시 전에 model-free `--no-narrative`
fallback과 identity 검사를 강제합니다.

### Step 7: HuggingFace 업로드 (`step7_upload_hf.sh`)

원격 `data/**`와 `deliverable_files/**`를 삭제한 뒤 `README.md`,
`data/train-*.parquet`, `deliverable_files/**`, `self_report.json`만
업로드합니다. `reference_files/**`는 duplicate 원본을 유지합니다.
Markdown report는 HF report directory가 아니라 결과 PR로 기록됩니다.

## 실험 YAML 설정

첫 3-task 실행에는 체크인된
[`exp998_smoke_baseline_sample.yaml`](experiments/exp998_smoke_baseline_sample.yaml)을
사용합니다. 실행 전에 `data.source`의 owner만 바꾸고 repository 이름은 YAML
stem과 같게 유지하세요.

```yaml
experiment:
  id: "exp998_smoke_baseline_sample"

data:
  source: "YOUR_HF_USERNAME/exp998_smoke_baseline_sample"
  filter:
    sector: null
    occupation: null
    sample_size: 3

condition_a:
  model:
    provider: "azure"
    deployment: "gpt-5.2-chat"
  qa:
    enabled: true
    max_retries: 3
    min_score: 6

execution:
  mode: "code_interpreter"
  max_retries: 5
  resume_max_rounds: 3
```

실제 샘플 파일에는 전체 prompt와 Self-QA 계약이 있습니다. `condition_b`를
생략하면 단일 조건 실행으로 동작합니다.

## 실행 모드

### `code_interpreter` — Azure OpenAI Responses API (권장)

**Azure OpenAI Responses API의 내장 Code Interpreter**를 활용하는 핵심 실행 모드입니다.

- 모델이 Python 코드를 자율적으로 작성하고 **Azure OpenAI가 관리하는 보안 샌드박스 컨테이너** 내에서 실행
- 파일 생성(Excel, PDF, Word, PowerPoint, 이미지)은 provider-managed sandbox에서 이루어져 host code 실행과 로컬 dependency 위험을 줄입니다. 일반적인 cloud, prompt, data, output review 위험은 남습니다.
- Responses API가 도구 호출(`code_interpreter`)을 실시간 스트리밍하며, 생성된 파일은 Files API로 회수
- 반복적 코드 실행 지원: 모델이 출력을 검사하고, 오류를 수정하고, 재시도 — 단일 API 호출 내에서 모든 것이 완료
- **Azure OpenAI** 및 **OpenAI** 엔드포인트에서 사용 가능

> 이것은 Azure OpenAI를 사용한 프로덕션 실행에 권장되는 모드로, 가장 안전하고 강력한 파일 생성 워크플로우를 제공합니다.

### `subprocess` — 로컬 코드 실행

Responses API를 지원하지 않는 프로바이더(예: Anthropic)용.

- LLM이 Python 코드 생성 → **격리된 임시 디렉토리**에서 화이트리스트 환경 변수만으로 실행
- 로컬에 Python 패키지(openpyxl, reportlab 등) 설치 필요
- 모든 모델 프로바이더에서 사용 가능

### `json_renderer` — 공정한 모델 간 비교

다른 모델 간 통제된 A/B 테스트를 위해 설계.

- LLM이 산출물 구조를 설명하는 **JSON 사양**을 출력
- **고정된 Python 렌더러**(모든 모델에 동일한 코드)가 사양을 파일로 변환
- 코드 생성 능력을 변수에서 제거하여 모델의 태스크 이해력만 비교
- 모든 모델 프로바이더에서 사용 가능

### `sandbox` — 컨테이너 기반 멀티모달 실행

`subprocess`를 Docker 격리, task별 dependency 탐색, Agent Skills, 산출물
검증·render QA·bounded repair loop로 확장한 모드입니다. 컨테이너는 network를
끄고 memory/PID/CPU 제한과 `no-new-privileges`를 적용합니다. 정확한 image,
fallback, cache, manifest 계약은 [sandbox 문서](sandbox/README.md)를
참고하세요.

| 모드 | 지원 프로바이더 | 보안 | 적합한 용도 |
|------|---------------|------|----------|
| `code_interpreter` | Azure OpenAI, OpenAI | 샌드박스 (클라우드) | 프로덕션 실행, 복잡한 파일 생성 |
| `subprocess` | 모든 프로바이더 | 격리된 임시 디렉토리 | 비 OpenAI 모델 |
| `sandbox` | 모든 프로바이더 | network 없는 container + local fallback | 멀티모달·skill 기반 재현 실행 |
| `json_renderer` | 모든 프로바이더 | 코드 실행 없음 | 공정한 모델 간 비교 |

## 멀티 프로바이더 지원

`step2_run_inference.py`가 `condition["model"]["provider"]`를 읽어 클라이언트 선택:

| 프로바이더 | SDK | 환경 변수 |
|-----------|-----|----------|
| `azure` / `azure_openai` | `AzureOpenAI` | `AZURE_OPENAI_ENDPOINT` + `DefaultAzureCredential` (로컬 `az login`, CI OIDC) |
| `openai` | `OpenAI` | `OPENAI_API_KEY` |
| `anthropic` | `AnthropicClient` 래퍼 | `ANTHROPIC_API_KEY` |

모든 프로바이더는 통합된 응답 형식 (`response.choices[0].message.content`)을 반환합니다.

## 프로젝트 구조

```text
batch-runner/
├── step0_bootstrap.sh ... step7_upload_hf.sh
├── core/                         # config, client, executor, validation
├── experiments/                  # versioned YAML 실험 config
├── prompts/                      # prompt template
├── workspace/                    # checkpoint와 upload staging
├── results/<experiment_id>/      # 포맷된 결과와 report/
└── tests/                        # model-free unit/contract test
```


## 데이터 흐름

각 단계는 `workspace/`의 JSON 파일에서 읽으며, 이전 Python 객체가 아닌 파일 기반으로 동작합니다. 각 단계는 독립적으로 재시작 가능합니다.

```text
experiment YAML
  -> workspace/step1_tasks_prepared.json
  -> workspace/step2_inference_{progress,results}_<condition>.json
  -> workspace/result.json + results/<experiment_id>/
  -> workspace/upload/{data,deliverable_files,self_report.json}
  -> 결과 PR(report.md) + Hugging Face allowlist + Actions artifact
```


## 테스트

```bash
# Mock 테스트만 (기본, API 키 불필요)
pytest

# 통합 테스트 (HF_TOKEN 및 실제 데이터 필요)
pytest -m integration

# 전체 테스트
pytest -m ""

# 개별 파일
pytest tests/test_llm_client.py -v

# 커버리지 포함
pytest --cov=core --cov-report=html
```

기본 설정: `-m "not integration"` — 통합 테스트는 기본적으로 건너뜁니다.

## 주의 사항

- **o-series 모델** (`gpt-5.x`, `o3`, `o4`)은 `temperature` 파라미터를 지원하지 않습니다. `temperature=0`을 전달하면 400 에러가 발생합니다.
- **`needs_files` 게이트**: 루브릭에서 파일 산출물을 기대하는 태스크는 파일이 생성되지 않으면 실패하여 재시도가 트리거됩니다.
- **이어하기 동작**: Step 2는 조건별 checkpoint를 분리하고 해당 조건의 `error`/`qa_failed` 태스크만 재실행합니다.
- **HF 업로드**: Step 7은 원격 `data/**`와 `deliverable_files/**`를 삭제한 뒤 위에 적은 명시적 allowlist만 업로드합니다. `reference_files/**`는 보존합니다.
- **`code_interpreter` 모드**는 Azure OpenAI의 Responses API와 내장 Code Interpreter를 활용하는 권장 실행 모드입니다. 보안 샌드박스에서 파일을 생성합니다. Anthropic 등 비 OpenAI 프로바이더는 `subprocess` 또는 `json_renderer`를 사용해야 합니다.

## GitHub Actions

[Run GDPVal Batch Experiment](../../../actions/workflows/batch-run.yml)
(`workflow_dispatch`)를 신뢰된 `main` workflow 정의에서 실행합니다.
preflight는 checkout과 cloud 접근 전에 non-`main` ref 또는 workflow/event SHA
불일치를 거부합니다.

### 워크플로우 파라미터

| 파라미터 | 역할 | 기본값 | 언제 바꾸나 |
|---------|------|--------|-----------|
| `experiment_yaml` | `.yaml`을 뺀 config 파일명 | *(필수)* | 추적 중인 config stem 입력 |
| `experiment_name` | 선택적 표시 이름. 비우면 YAML에서 읽음 | *(비움)* | 보통 비워 둠 |
| `dry_run` | Step 5, 최종 Step 7 게시, 결과 PR 생략. 모델/HF 설정은 실행 | `false` | 비용·쓰기 경계를 읽은 뒤 첫 smoke에서만 사용 |
| `relay_run` | 내부 relay leg 카운터 | `0` | 수동 실행에서는 변경하지 않음 |
| `relay_lineage_id` | relay 전체에 전달되는 안정적 identity | *(비움)* | 내부용. leg 0에서는 비워 둠 |
| `source_sha` | 모든 relay leg가 요구하는 최초 `main` commit | *(비움)* | 내부용. leg 0에서는 비워 둠 |
| `wall_timeout` | `condition_a` Step 2 checkpoint watchdog `0..290`분. `0`은 YAML의 `execution.wall_timeout`에 위임하며 둘 다 `0`일 때만 비활성화 | `290` | relay 디버깅이 아니면 기본값 유지 |
| `sandbox_image_digest` | relay 전체에 전달되는 immutable sandbox image | *(비움)* | 내부용. 필요 시 workflow가 결정 |

### 3-task smoke 입력

```
experiment_yaml:       exp998_smoke_baseline_sample
experiment_name:       <비움>
dry_run:               true
relay_run:             0
relay_lineage_id:      <비움>
source_sha:            <비움>
wall_timeout:          290
sandbox_image_digest:  <비움>
```

### 이어달리기(Relay Run) 동작 원리

긴 실험은 GitHub Actions job 제한에 가까워질 수 있습니다. Step 2는 태스크
사이에서 watchdog을 확인하고, deadline을 확인하면 checkpoint를 저장한 뒤
안정적인 lineage를 다음 relay leg로 전달합니다.

```
Run 1 (직접 트리거):
  → 태스크 실행 → 설정한 wall timeout 도달
  → exact `data.source`에 content-addressed generation 하나를 업로드
  → generation revision과 progress/deliverable SHA-256 + size 전체를 검증한
    뒤에만 `current.json` marker를 전진
  → Run 2 자동 트리거 (relay_run=1)

Run 2 (자동 트리거):
  → marker의 immutable payload revision과 exact file set만 복원
  → Azure login 전에 lineage, complete ordered task set, prepared fingerprint,
    참조 deliverable 전체를 검증
  → 미완료 태스크 이어서 실행 → 완료
  → Step 3~7 정상 진행 → PR 생성
```

이는 보장된 handoff 시간이 아니라 best-effort입니다. 진행 중인 긴 태스크나
앞선 setup이 남은 step/job 시간을 소진할 수 있습니다.

relay 시도 횟수는 실험 config가 제한합니다. workflow는 최초 `main` commit을
`source_sha`로 고정하며, `main`이 바뀌면 relay가 checkout 전에 실패합니다.
checkpoint가 없거나 잘못됐거나 불완전하면 전체 태스크를 조용히 재실행하지
않고 continuation을 실패시킵니다.

Step 0 뒤에는 비변경 HF authorization check로 exact `data.source`의 write
권한을 증명합니다. 이 검사는 task 준비, Azure login, model spend보다 먼저
실행됩니다.
Step 0은 parquet가 선언한 모든 reference path가 unique regular non-symlink
file이며 pinned SHA-256/size와 일치하는지도 inference 전에 검사합니다.
input projection, declared reference set, reference bytes가 달라진 target은
이전 local snapshot을 교체하기 전에 거부합니다.

Checkpoint generation은 source/lineage별 `_checkpoint/` 경로에 있습니다.
성공한 cleanup은 exact-HEAD CAS commit으로 현재 dataset tree에서 그 lineage를
제거합니다. 실패한 upload/cleanup은 orphan generation을 남길 수 있고, path
삭제는 이전 Hugging Face revision이나 저장 이력을 지우지 않습니다. 민감하지
않은 입력·출력만 새 public 일회성 target에 사용하고, 이력 보존이 허용되지
않으면 dataset을 명시적으로 점검하거나 삭제하세요.
`relay_run`, `relay_lineage_id`, `source_sha`, `sandbox_image_digest`를 수동으로
채우지 마세요.

GitHub concurrency를 durable queue로 사용하지 않습니다. 같은 `data.source`를
공유하는 실행을 겹쳐 dispatch하지 마세요. checkpoint와 파괴적 게시는 같은
Hugging Face 대상을 사용합니다.

## 결과와 게시

- Step 2 checkpoint와 최종 inference JSON은 `workspace/`에 있습니다.
- Step 3은 `results/<experiment_id>/`에 포맷된 결과를 씁니다.
- Step 6은 `results/<experiment_id>/report/`에 `report_data.json`과
  `report.md`를 쓰고 HF용 `self_report.json`을 staging합니다.
- non-dry workflow는 Step 7이 HF를 수정하기 전에 `report.md` 하나만 담은
  결과 PR 계약을 검증합니다.
- workflow는 `batch-runner/workspace/`와 `batch-runner/results/`를 30일
  보관합니다. 내려받은 archive root에는 `workspace/`와 `results/`가 있습니다.

외부 rubric grading은 별도 workflow입니다. Self-QA나 Step 6 pre-grading
report가 외부 채점을 의미하지 않습니다.
