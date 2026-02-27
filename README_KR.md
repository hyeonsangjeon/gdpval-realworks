<p align="center">
  <img src="https://img.shields.io/badge/GDPVal-Real%20Work%20Benchmark-blueviolet?style=for-the-badge" alt="GDPVal RealWorks" />
</p>

<h1 align="center">GDPVal RealWorks</h1>

<p align="center">
  <strong>LLM을 학문적 시험이 아닌, 실제 전문가 업무로 벤치마크하세요.</strong><br/>
  <em>YAML 기반 실험 파이프라인 + 라이브 대시보드로 <a href="https://arxiv.org/abs/2510.04374">GDPVal</a> Gold Subset (220개 태스크)을 평가합니다.</em>
</p>

<p align="center">
  <a href="https://github.com/hyeonsangjeon/gdpval-realworks/actions/workflows/deploy.yml">
    <img src="https://github.com/hyeonsangjeon/gdpval-realworks/actions/workflows/deploy.yml/badge.svg" alt="Deploy" />
  </a>
  <a href="https://github.com/hyeonsangjeon/gdpval-realworks/actions/workflows/batch-run.yml">
    <img src="https://github.com/hyeonsangjeon/gdpval-realworks/actions/workflows/batch-run.yml/badge.svg" alt="Batch Run" />
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License" />
  </a>
</p>

<p align="center">
  <a href="https://hyeonsangjeon.github.io/gdpval-realworks/">🌐 라이브 대시보드</a> · 
  <a href="README.md">🇺🇸 English</a> · 
  <a href="batch-runner/README.md">📖 Batch Runner 문서</a> · 
  <a href="https://arxiv.org/abs/2510.04374">📄 논문</a>
</p>

---

## 문제 인식

대부분의 LLM 벤치마크는 **학술적 추론** — 수학, 코드 퍼즐, 퀴즈를 테스트합니다.  
그런 건 모델이 실제로 **내 업무를 해낼 수 있는지** 알려주지 않습니다.

**GDPVal** (GDP-level Validation)은 다릅니다: 11개 산업, 55개 직종에 걸친 **220개 실무 태스크** — Excel 보고서, 법률 문서, 영업 프레젠테이션 등 사람들이 실제로 돈 받고 하는 일들.

이 레포는 전체 루프를 자동화합니다: **설정 → 실행 → 수집 → 시각화** — YAML 하나로 구동, GitHub Actions에서 실행, 결과는 라이브 대시보드에.

> 🎯 YAML 하나. 버튼 한 번. 실험 전체 라이프사이클.

---

## 동작 원리

<table>
<tr>
<td align="center"><img src="https://mermaid.ink/img/Zmxvd2NoYXJ0IFRECiAgICBBWyJTdGVwIDA6IOu2gO2KuOyKpO2KuOueqTxicj5IRiDroIjtj6wgKyDsiqTrg4Xsg7ciXSAtLT4gQlsiU3RlcCAxOiDtg5zsiqTtgawg7KSA67mEPGJyPu2VhO2EsCArIOuhnOuTnCJd" alt="준비" width="350" /></td>
<td align="center" style="font-size:2em;">→</td>
<td align="center"><img src="https://mermaid.ink/img/Zmxvd2NoYXJ0IFRECiAgICBDWyJTdGVwIDI6IOy2lOuhoDxicj5MTE0gKyBTZWxmLVFBIl0gLS0-IERbIlN0ZXAgMzog7Y-s66e37YyFPGJyPkpTT04gKyBNYXJrZG93biJd" alt="실행" width="350" /></td>
</tr>
<tr>
<td></td>
<td align="center" style="font-size:2em;">↓</td>
<td></td>
</tr>
<tr>
<td align="center"><img src="https://mermaid.ink/img/Zmxvd2NoYXJ0IFRECiAgICBFWyJTdGVwIDQ6IFBhcnF1ZXQ8YnI-7KCc7LacIOuNsOydtO2EsCDrs5HtlakiXSAtLT4gRlsiU3RlcCA1OiDqsoDspp08YnI-66y06rKw7ISxIOqygOyCrCJd" alt="산출물" width="350" /></td>
<td align="center" style="font-size:2em;">→</td>
<td align="center"><img src="https://mermaid.ink/img/Zmxvd2NoYXJ0IFRECiAgICBHWyJTdGVwIDY6IOumrO2PrO2KuDxicj5IVE1MICsgSlNPTiJdIC0tPiBIWyJTdGVwIDc6IOyXheuhnOuTnDxicj5IRiArIFBSIOyDneyEsSJd" alt="리포트 & 업로드" width="350" /></td>
</tr>
</table>


---

## ⚡ 빠른 시작

### 1. Fork & Clone

```bash
git clone https://github.com/hyeonsangjeon/gdpval-realworks.git
cd gdpval-realworks
```

### 2. GitHub 저장소 설정

#### 🔑 Secrets 등록

**Settings → Secrets and variables → Actions → New repository secret** 에서 필요한 시크릿을 추가하세요:

| Secret 이름 | 값 | 필수? |
|---|---|---|
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API 키 | ✅ Azure 사용 시 |
| `AZURE_OPENAI_ENDPOINT` | `https://your-resource.openai.azure.com/` | ✅ Azure 사용 시 |
| `OPENAI_API_KEY` | OpenAI API 키 | OpenAI 사용 시 |
| `ANTHROPIC_API_KEY` | Anthropic API 키 | Anthropic 사용 시 |
| `HF_TOKEN` | HuggingFace write 토큰 ([여기서 발급](https://huggingface.co/settings/tokens)) | ✅ 업로드용 |

> 💡 전부 다 등록할 필요 없습니다 — 실제로 쓸 provider 것만 먼저 넣으면 됩니다.  
> Azure 사용자: `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` + `HF_TOKEN` 이 세 개가 우선입니다.

#### 📄 GitHub Pages

**Settings → Pages → Source** → **"GitHub Actions"** 으로 변경 (기본값 "Deploy from a branch" 말고)

#### 🔓 Workflow 권한

**Settings → Actions → General → Workflow permissions:**

- ✅ **"Read and write permissions"** 선택
- ✅ **"Allow GitHub Actions to create and approve pull requests"** 체크
- 저장

#### 🧹 자동 정리 (권장)

**Settings → General** → ✅ **"Automatically delete head branches"** 체크

> PR 머지 후 실험 브랜치가 자동으로 삭제됩니다. 깔끔!

---

### 3. 첫 번째 실험 실행

1. **Actions** 탭 → **"Run GDPVal Batch Experiment"** 선택
2. **"Run workflow"** 클릭
3. 입력:
   - `experiment_yaml`: `exp998_smoke_baseline_sample` (스모크 테스트, 3개 태스크)
   - `dry_run`: ✅ 체크 (처음엔 업로드 건너뛰기)
4. **Run workflow** 클릭 🚀

```
✅ Step 0: Bootstrap        → HF 레포 준비 완료
✅ Step 1: Prepare tasks    → 3개 태스크 필터링 완료
✅ Step 2: Run inference    → 각 태스크에 LLM 호출 완료
✅ Step 3: Format results   → JSON + Markdown 생성 완료
✅ Step 4: Fill parquet     → 제출용 Parquet 준비 완료
⏭️ Step 5: Validate        → 스킵 (스모크 테스트)
⏭️ Step 6: Upload          → 스킵 (dry run)
```

> 🎉 통과하면 `dry_run` 체크 해제하고 본격 실험을 돌리세요!

---

## 📝 나만의 실험 만들기

`batch-runner/experiments/`에 YAML 파일을 만드세요:

```yaml
experiment:
  id: "exp001_GPT52Chat_baseline"
  name: "GPT-5.2 Chat Baseline (전체 220 태스크)"
  description: "code_interpreter + Self-QA를 사용한 풀 베이스라인 실행."

data:
  source: "HyeonSang/exp001_GPT52Chat_baseline"
  filter:
    sector: null          # null = 전체 섹터
    sample_size: null     # null = 전체 220개

condition_a:
  name: "Baseline"
  model:
    provider: "azure"
    deployment: "gpt-5.2-chat"
    temperature: 0.0
    seed: 42
  prompt:
    system: "You are a helpful assistant that completes professional tasks."
    suffix: "Generate actual files, not descriptions."
  qa:
    enabled: true
    min_score: 6
    max_retries: 3

# condition_b:            ← A/B 비교용 (선택 사항)

execution:
  mode: "code_interpreter"
  max_retries: 5
  resume_max_rounds: 3
```

**Actions → Run workflow**에서 `experiment_yaml: exp001_GPT52Chat_baseline`으로 실행하면 됩니다.

---

## 🧠 실행 모드

| 모드 | 동작 방식 | 적합한 용도 |
|---|---|---|
| **`code_interpreter`** | LLM이 Azure/OpenAI **보안 샌드박스** 안에서 코드를 작성하고 실행. 파일이 클라우드에서 생성됨. | ✅ 프로덕션 — 안전하고 강력 |
| **`subprocess`** | LLM이 코드 생성 → 로컬 격리 임시 디렉토리에서 실행. | OpenAI 외 모델 (Anthropic 등) |
| **`json_renderer`** | LLM이 JSON 스펙 출력 → **고정 렌더러**가 파일 생성. 모든 모델에 동일한 렌더러 사용. | 모델 간 공정한 A/B 비교 |

> 🐳 `subprocess` 모드는 **컨테이너 기반** 실행으로 진화 예정입니다 — 시간이 허락한다면... 그리고 커피가 바닥나지 않는다면.

---

## 🔬 Self-QA: 내장 품질 리플렉션 게이트

모든 태스크 출력물은 작업하고 있는 LLM이 스스로 검수한 후 수락됩니다:
Self-QA는 각 산출물을 루브릭 기반 자기평가로 0~10점 척도에서 점수화합니다. 점수가 설정 임계값(기본 6점) 미만이면 리플렉션 루프로 들어가 재시도합니다.

<img src="https://mermaid.ink/img/Zmxvd2NoYXJ0IExSCiAgICB0YXNrWyLtg5zsiqTtgawiXSAtLT4gZ2VuWyJMTE0g7Lac66ClIOyDneyEsSJdIC0tPiBxYVsiU2VsZi1RQSDqsoDsiJgiXSAtLT4gZ2F0ZXsi7KCQ7IiYID49IDY_In0KICAgIGdhdGUgLS0-fOyYiHwgYWNjZXB0WyLsiJjrnb0iXQogICAgZ2F0ZSAtLT587JWE64uI7JikfCByZXRyeVsi7J6s7Iuc64-EICjstZzrjIAgM-2ajCkiXQo=" alt="Self-QA 흐름" />


검수 항목: 모든 요구사항 충족? 파일이 실제로 생성됐나? 결과물이 전문적인가?

---

## 🏗️ 아키텍처

<img src="https://mermaid.ink/img/Zmxvd2NoYXJ0IFRCCiAgICByb290WyJnZHB2YWwtcmVhbHdvcmtzLyJdCgogICAgd2ZbIi5naXRodWIvd29ya2Zsb3dzLzxici8-YmF0Y2gtcnVuLnltbCwgZGVwbG95LnltbCJdCiAgICBiclsiYmF0Y2gtcnVubmVyLzxici8-c3RlcCDsiqTtgazrpr3tirgsIGNvcmUsIGV4cGVyaW1lbnRzLCBwcm9tcHRzLCB0ZXN0cyJdCiAgICBzcmNbInNyYy88YnIvPnBhZ2VzLCBjb21wb25lbnRzIl0KICAgIGRhdGFbImRhdGEvPGJyLz50ZXN0cywgZ3JhZGVzIl0KICAgIHNjcmlwdHNbInNjcmlwdHMvPGJyLz5hZ2dyZWdhdGUtdGVzdHMubWpzLCBhZ2dyZWdhdGUtZ3JhZGVzLm1qcyJdCgogICAgcm9vdCAtLT4gd2YKICAgIHJvb3QgLS0-IGJyCiAgICByb290IC0tPiBzcmMKICAgIHJvb3QgLS0-IGRhdGEKICAgIHJvb3QgLS0-IHNjcmlwdHMK" alt="프로젝트 구조" />


---

## 🔄 GitHub Actions 워크플로우

### `batch-run.yml` — 실험 실행

| 항목 | 설명 |
|---|---|
| **트리거** | Actions 탭에서 수동 실행 (`workflow_dispatch`) |
| **입력** | 실험 YAML 파일명 + dry_run 옵션 |
| **파이프라인** | Step 0 → Step 6 (부트스트랩 → 업로드) |
| **스마트 스킵** | 스모크 테스트는 검증 스킵; dry_run은 업로드 + PR 스킵 |
| **자동 PR** | 실험 요약이 담긴 Pull Request 자동 생성 |
| **아티팩트** | 전체 workspace 30일간 보관 |
| **타임아웃** | 최대 5시간 |

### `deploy.yml` — 대시보드 배포

| 항목 | 설명 |
|---|---|
| **트리거** | `main` 푸시 시 자동 실행 또는 수동 |
| **빌드** | 테스트/채점 데이터 집계 → React 빌드 → GitHub Pages |
| **범위** | `data/`, `src/`, `scripts/` 변경 시에만 실행 |

---

## 🖥️ 대시보드

> ⏳ **현재 채점 결과를 기다리고 있습니다.** [evals.openai.com](https://evals.openai.com/)에서 채점이 완료되면 대시보드에 반영됩니다 — 시간이 좀 걸립니다.

[hyeonsangjeon.github.io/gdpval-realworks](https://hyeonsangjeon.github.io/gdpval-realworks/)의 React 대시보드에서 확인 가능:

- 📊 **실험 개요** — 모든 실행 기록과 상태, 메타데이터
- 📈 **채점 요약** — 모델별 전체 태스크 점수
- 🔍 **상세 보기** — 개별 태스크 결과 드릴다운
- ⚖️ **비교** — 모델 간 성능 나란히 비교

데이터는 빌드 타임에 `data/`에서 집계 → 정적 JSON → Vite로 서빙됩니다.

---

## 🧪 테스트

```bash
cd batch-runner
pip install -r requirements.txt

# 유닛 테스트만 (API 키 불필요)
pytest

# 통합 테스트 (실제 인증 정보 필요)
pytest -m integration

# 커버리지 포함
pytest --cov=core --cov-report=html
```

### 🖥️ 로컬 실행 (단계별)

```bash
cd batch-runner
export HF_TOKEN="hf_xxx"
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
export AZURE_OPENAI_API_KEY="xxx"

./step0_bootstrap.sh experiments/exp998_smoke_baseline_sample.yaml
./step1_prepare_tasks.sh experiments/exp998_smoke_baseline_sample.yaml
./step2_run_inference.sh condition_a
./step3_format_results.sh
./step4_fill_parquet.sh
./step5_validate.sh
./step6_report.sh
./step7_upload_hf.sh --test
```

> 💡 로컬에서도 실행 가능하지만, 220개 전체 태스크는 **GitHub Actions**를 추천합니다.  
> 배치 워크플로우가 TPM (분당 토큰 수) 쿼터가 허용하는 만큼 병렬 처리합니다 — 클라우드에 맡기고 커피 한 잔 하세요. ☕

---

## 📚 참고 자료

- **GDPVal 논문**: [arXiv:2510.04374](https://arxiv.org/abs/2510.04374)
- **GDPVal 데이터셋**: [openai/gdpval](https://huggingface.co/datasets/openai/gdpval)
- **GDPVal 채점**: [evals.openai.com](https://evals.openai.com/)
- **Azure OpenAI Responses API**: [공식 문서](https://learn.microsoft.com/azure/ai-services/openai/)

---

## 👤 저자

**전현상 (Hyeonsang Jeon)**  
Sr. Solution Engineer · Global Black Belt — AI Apps | Microsoft Asia, Korea  
[![GitHub](https://img.shields.io/badge/GitHub-hyeonsangjeon-181717?logo=github)](https://github.com/hyeonsangjeon)
[![Dashboard](https://img.shields.io/badge/라이브%20대시보드-GDPVal-blueviolet?logo=react)](https://hyeonsangjeon.github.io/gdpval-realworks/)

---

## 📄 라이선스

MIT — 자세한 내용은 [LICENSE](LICENSE) 파일을 참고하세요.
