# 000 — OVERVIEW (Grading Pipeline v2 Rebuild)

> Authoritative SPEC: [`SPEC_GRADING_PIPELINE_V2.md`](./SPEC_GRADING_PIPELINE_V2.md)
> Prior analysis on main: `data/grades/_validation/STRATIFY_v2_*.md`, `SCORE_MATH_AUDIT.md` (commit `a1457a4`)

## 핵심 요약

1. **단일 메인 judge**: production은 `gpt-5.6-sol`
	reasoning_effort=`max`. tier 없음. 최초 PR2 baseline인 `gpt-5.4 medium`은
	`default_v2.yaml` 비교 identity로 보존.
2. **눈/귀 부착**: text 추출 폐기, judge가 `read_deliverable` tool로 파일 직접 조회. production 시각 항목 → `gpt-5.6-sol` reasoning_effort=`max`, 오디오 지각 → `gpt-audio-1.5`.
3. **score-math sign-bug fix**: `verdict='pass'` 부호 시멘틱 정규화, `|max_score|≥4` critical 재정의, `total_max≤0` degenerate 케이스 explicit 처리.
4. **legacy 제거**: `deliverable_extract_max_chars`, tier 분기, `required` OR-가지 잔재 전부.

## PR 분할 (SPEC §6 + 본 작업자 분해)

### PR1 — Score-Math Sign-Bug Fix (선행, 필수)  ✅ **CLOSED** — see [PR1_REPORT.md](./PR1_REPORT.md)

| # | task | 상태 |
|---|---|---|
| 100 | [sign-aware aggregate](./100-sign-aware-aggregate.md) | ✅ `240b860` |
| 101 | [critical redefinition](./101-critical-redefinition.md) | ✅ `ad3b922` |
| 102 | [non-positive total_max handling](./102-handle-nonpositive-total-max.md) | ✅ `b9c46e8` |
| 103 | [backfill existing grades](./103-backfill-existing-grades.md) | ✅ `933c25e` |
| 104 | [regression sweep + report](./104-pr1-regression-sweep.md) | ✅ (this commit) |

**Acceptance**: PR1 끝나면 main 헤드라인 지표(`avg_score_pct`, `critical_item_pass_rate`)가 sign-aware로 신뢰 가능.

### PR2 — Tool-Calling Grader Rebuild (메인, 새 세션 권장)  ✅ **CLOSED** — see [PR2_REPORT.md](./PR2_REPORT.md)

| # | task | 상태 |
|---|---|---|
| 200 | [exp011 env audit](./200-env-audit.md) → [PR2_ENV_AUDIT.md](./PR2_ENV_AUDIT.md) | ✅ (this commit) |
| 201 | [read_deliverable tool 정의/구현](./201-tool-interface.md) | ✅ (this commit) |
| 202 | [judge prompt v2 (tool-aware)](./202-judge-prompt-tool-aware.md) | ✅ (this commit) |
| 203 | [메인 grader rewrite (tool-calling)](./203-grader-main-rewrite.md) | ✅ (this commit) |
| 204 | [modality routing](./204-perception-routing.md) | ✅ (this commit) |
| 205 | [vision perception (gpt-5.4 vision)](./205-vision-judge.md) | ✅ (this commit) |
| 206 | [audio perception (gpt-audio-1.5)](./206-audio-judge.md) | ✅ (this commit) |
| 207 | [legacy removal](./207-legacy-removal.md) | ✅ DONE — config archive + **code strip 완료**. 264행이 PARTIAL 사유로 적은 `_use_batch`/`_tier_judges`/`_summarize_deliverables`/`deliverable_extract_max_chars`와 `core/grader_batch.py`는 모두 제거됨; `Grader`는 tool-calling 설정이 아니면 생성을 거부하고(`core/grader.py:284`), `tests/test_grader.py:875-896`이 그 심볼들의 부재를 검사한다. 인수 grep이 아직 걸리는 것은 (a) 207 자신의 지시 3번이 만든 `_archive_v1/`, (b) 제거 사실을 적은 주석, (c) `core/azure_ai_clients.py:788`의 Azure 배포 허용목록 방어 분기 1건뿐 — 셋 다 legacy 채점 경로가 아니다. (c)는 후속 항목으로 등록. 근거는 [PR3_REPORT.md](./PR3_REPORT.md). |
| 208 | [config schema + validator 업데이트](./208-config-schema-update.md) | ✅ (this commit) |

### PR3 — Validation Gates (새 세션, PR2 후)

| # | task | 상태 |
|---|---|---|
| 300 | [gold-ceiling test](./300-gold-ceiling.md) | ✅ DONE — **작업 완료, 결과는 임계값 미달.** 정답 30과제 실행 완료: 평균 **82.87%** (기준 90%), 필수 항목 통과율 **0.5714** (기준 0.95), 채점기 오류율 **0.14%** (기준 <2%, 통과). 명세대로 미달을 분류한 결과 **grader 결함은 0건**이고, 손실은 도구 결함(약 46점 회복 가능)과 입력 결함(정답이 자기 채점표를 문자 그대로는 못 지킴)이다. 읽기 도구 결함 2건을 고쳐 78.24% → 82.87%로 한 번 재실행했으며, 남은 도구 결함을 모두 고쳐도 상한은 84~85%다. 즉 **정답의 천장은 약 83%**이고 90%는 채점기 수정으로 넘을 수 있는 벽이 아니다. 보고서 [PR3_GOLD_CEILING.md](./PR3_GOLD_CEILING.md). |
| 301 | [exp003 재채점 + formatting 격차 붕괴 + bare-CSV evidence](./301-exp003-revalidation.md) | ✅ DONE — 220 재채점 완료 + 분석 완료. **formatting 격차는 붕괴하지 않고 -25.5pp → -46.0pp로 확대**; v1의 "hybrid over-rejects" 진단이 뒤집힘 (mini가 못 봐서 관대했던 것). bare-CSV 판별은 통과. 보고서는 `tasks/**` privacy 규칙(`5349cbf`) 때문에 [data/grades/_validation/PR3_EXP003_REVALIDATION.md](../../data/grades/_validation/PR3_EXP003_REVALIDATION.md)에 위치. |
| 302 | [cost budget 재추정](./302-cost-budget-recheck.md) | ⚠️ 미해결이지만 **전제가 낡음** — 당시 projection은 N=3 smoke 기준이었고, 그 뒤 220-task 실주행이 이미 끝났다. PR3_SMOKE_FINDINGS.md의 A/B/C는 그 낡은 projection 위에 서 있으므로 그대로 답할 수 없음. 실측 기준으로 다시 세워야 함 (owner gate). |
| 303 | [variance + bootstrap CI + judge_error rate](./303-variance-and-error.md) | ✅ DONE — **세 임계값 모두 통과.** 정답 30과제를 아무것도 바꾸지 않고 3회 채점: 과제별 점수 표준편차 **4.02pp** (기준 ≤5pp), judge 오류율 **0.09%** (4/4,299, 기준 <2%), 평균의 95% 신뢰구간 폭 **7.26pp** (기준 <10pp). 코퍼스 평균은 **82.87 · 83.07 · 83.25%**로 폭 0.37pp — 300의 82.87%는 그날의 운이 아니다. 명세는 exp003 부분집합을 적었으나 실제로 인용되는 숫자가 300의 82.87%이므로 대상을 정답 30과제로 바꿨고, 300의 채택된 실행이 1회차를 겸해 신규 dispatch는 2회였다. 부수 발견: `judge_error` 항목이 `score_excluded`가 되어 **분모(만점)에서도 빠지므로 실행마다 만점이 달라진다** (30과제 중 3과제). 가장 크게 움직인 과제의 7.05pp는 전부 만점 22→24 변화이고 받은 점수는 18.6으로 동일 — 300이 `17111c03`에서 이유를 특정 못한 채 남겨 둔 관찰과 원인이 같다. 소유자 결정 항목으로 등록. 보고서 [PR3_VARIANCE.md](./PR3_VARIANCE.md). |

## 다음 순서 (PR3 이후)

PR3의 남은 항목(300 · 302 · 303)은 전부 유료 dispatch나 비용 결정에 걸려 있다.
그래서 순서를 "무료로 먼저 확정할 수 있는 것 → 유료 중 가장 값어치 있는 것"으로
잡는다. 아래 네 건이 그 순서다.

### C1 — 렌더러 버전 고정 (무료, 선행) ✅ **DONE — `#193`**

**원래 계획은 틀렸다.** 이 항목은 "grade job을 `ghcr.io/hyeonsangjeon/gdpval-sandbox`로
옮긴다"였다. Dockerfile이 아니라 실제 이미지를 받아서 열어보니 성립하지 않는다.

| | sandbox 이미지 | 지금 grade 러너 | 발행된 grade 파일 |
|---|---|---|---|
| LibreOffice | **7.4.7.2** | **24.2.7.2** | **24.2.7.2** (4개 전부) |
| `git` | 없음 | 있음 | — |
| `az` | 없음 | 있음 | — |

즉 그 이미지로 옮기면 (1) 채점기의 눈을 17세대 낡은 렌더러로 **바꿔서 점수를
움직이고** — 이 항목이 막으려던 바로 그 일이다 — (2) `git`이 없어
`actions/checkout`이 `.git` 없는 tarball로 떨어져 shard merge의 commit·push가
깨지고 (3) `az`가 없어 `azure/login` + `DefaultAzureCredential`이 인증하지
못한다. sandbox 이미지에 `az`를 넣는 선택지는 보안상 기각했다 — 그 이미지는 LLM이
쓴 코드를 실행한다.

**목적은 다른 방법으로 달성했다.** 진짜 문제는 컨테이너 유무가 아니라 apt가
`libreoffice-core`/`-calc`/`-impress`/`-writer`를 버전 없이 요청하고, 결과를
출력만 하고 **아무것도 검증하지 않는다**는 것이었다. 그날 미러가 주는 게 곧
judge의 눈이 된다. 301은 formatting 판정이 "본 것"에서 나온다는 걸 확인했으므로
(v2 61.8% vs v1 87.7%) 렌더러 세대가 다른 두 run은 model·prompt·
`grader_source_hash`가 같아도 비교 대상이 아니다.

`#193`은 `scripts/preflight_grading_renderer.py`가 설치된 버전을 발행 corpus의
값(`LibreOffice 24.2.7.2 420(Build:2)`)과 대조하게 했다. shard마다,
`azure/login` **앞에서** 돈다 — drift는 무료 스텝에서 실패한다.

여기에 더 날카로운 구멍 하나가 같이 막혔다. `step9_merge_shards.py:124`는
`renderer_fingerprint`를 contract identity 필드로 요구한다. 즉 shard 9개가 같은
버전을 기록해야 병합된다. 며칠에 걸쳐 resume하는 9-shard run이 중간에 미러 bump를
맞으면 **돈을 다 쓴 뒤에** 병합이 거부된다.

남은 일(무료, P2): `FROM ubuntu:24.04` 기반 전용 grading 이미지. 버전이 구조적으로
일치하고, 미러 의존과 shard당 중복 설치가 사라지고, Ubuntu가 패키지를 올릴 때
사람이 pin을 고칠 필요가 없어진다. board 카드 참조.

### C2 — shard merge 오탐 제거 (무료, 선행) ✅ **DONE — `#194`**

R1 직전 마지막 무료 항목. 발단은 "직전 sol-220 시도에서 shard 3개가 fail로
끝났다"였는데, 실제로 무슨 일이 있었는지 확인해 보니 예상과 반대였다.

- 커밋된 shard 파일 9개 = 25·25·25·25·24·24·24·24·24 = **220**
- 최종 병합 파일 = `run_status: final`, **220 tasks**
- 즉 **그 run은 성공했다.** fail로 뜬 3개가 오히려 정상 shard였다.

원인: 병합 담당을 **파일 개수**로 정했다는 것. shard 하나는 corpus의 일부만
가지므로 파일은 언제나 `run_status: partial`이고, resume 청크가 끝날 때마다
그 시점까지의 slice를 다시 발행한다. 그래서 여러 청크로 도는 run에서는 9개
파일이 **9개 slice가 완성되기 훨씬 전에** 이미 다 존재한다. 청크를 끝낸 shard가
pull → 파일 9개 확인 → 병합 시도 → union이 220에 못 미침 → `exit 1`.

`step9`의 완결성 가드 자체는 옳게 동작했다. 문제는 그 정상적이고 일시적인
상태를 **하드 실패로 보고**했다는 것이다. 진짜 대가는 로그 소음이 아니라,
**정말 멈춘 run과 멀쩡한 run이 화면상 구분되지 않는다**는 점이다. 빨간 줄을 보고
이미 끝난 유료 작업을 재발주할 수 있다.

`#194`는 두 의미를 분리했다. `ShardMergeIncomplete`가 union 크기와 기대치를
들고 나오고, `--defer-if-incomplete`가 그것을 exit **75**(EX_TEMPFAIL —
나중에 다시, 고장 아님)로 바꾼다. 워크플로는 75를 `merged=false`로 받고 물러난다.
나머지는 하나도 느슨해지지 않았다: 플래그 없으면 여전히 exit 1이고, union이
완전한데 병합이 안 되는 경우(identity drift·중복 task)도 여전히 exit 1이다 —
그건 나중에 병합해 줄 사람이 없는 상황이기 때문이다.

### C3 — docx 채점 결과를 스키마가 거부하던 문제 (무료, 선행) ✅ **DONE — `#195`**

C2까지 끝내고 발주한 R1 카나리(shard 0)가 **유료로 3시간 13분을 돌고 11번째
과제에서 죽었다.** 25개 중 10개는 채점을 정상으로 마쳤다. 실패한 곳은 채점이
아니라 **저장**이다.

```
jsonschema.exceptions.ValidationError:
  'docx' is not one of ['pdf', 'xlsx', 'pptx', 'image']
```

`#189`이 `_op_render_to_image`에 .docx 가지를 넣어 `source_kind: "docx"`를
쓰게 만들었는데, 그 값을 받는 `schemas/grade.schema.json`의 enum은 원래
네 개 그대로였다. **눈은 달아 주고, 본 것을 적을 칸은 안 만든 셈이다.**

`#190`이 이 자리를 앞당겼다. 그 fix가 같은 형식 파일 여러 개를 채점 대상으로
되살렸고, 되살아난 5과제 중 3과제가 .docx 묶음이다. 두 fix가 함께 있어야
도달하는 지점이었다.

**무료 리허설로는 잡을 수 없는 결함이었다.** `dry_run=true`는 모델을 부르지
않는다. 모델을 안 부르면 렌더가 없고, 렌더가 없으면 provenance도 없다. 이
코드 경로는 구조적으로 **돈을 쓰기 시작해야만 도달한다.**

같은 커밋이 놓친 두 번째 자리도 함께 고쳤다. `_coverage_metadata`의
surface-count 표에 `docx`가 없어서, 렌더된 문서는 전부 판정 모델에게 "이
문서가 몇 쪽인지 모른다"고 말하고 있었다 — 그 값(`converted_page_count`)은
xlsx와 똑같이 이미 손에 쥐고 있었는데도. 1쪽짜리 메모의 1쪽과 40쪽 보고서의
1쪽은 같은 근거가 아니므로 이건 기록 누락이 아니라 판정 입력의 손실이다.
스키마가 애초에 docx를 거부했으므로 **발행된 어떤 run에도 docx provenance는
없다. 기존 실험 점수는 움직이지 않는다.**

**재발 방지는 fixture가 아니라 파생 검사로 했다.** 손으로 쓴 예시는 누군가
기억해서 적어 둔 모양만 증명한다. 대신 (1) 렌더러가 낼 수 있는 kind 집합을
코드에서 뽑아 스키마 enum이 그것을 포함하는지, (2) 같은 집합이 surface-count
표에 다 들어 있는지, (3) 저장되는 `_RENDERER_METADATA_KEYS`가 전부 스키마에
선언돼 있는지를 검사한다. (3)은 `additionalProperties: false`가 production에서
발동할 수 **없게** 만든다 — 저장 경로가 그 튜플로 필터링되기 때문이다.

카나리는 아무것도 커밋하지 않았다(저장 단계가 통째로 skip). main의
`data/grades/_shards/`에는 발행본 `src_1c967673eb8081a6` shard 9개뿐이다.
**카나리를 다시 돌린다.**

### R1 — 220 task 전체 재채점 (유료, owner gate) ⭐

**유료 중 가장 먼저 할 값어치가 있는 한 건.**

발행된 sol-220 run은 judge error **333 / 10,453 items = 3.19%** 로, 모든 후속
카드가 달고 있는 `< 2%` 게이트를 넘겼다. 원인은 코드에서는 이미 고쳐졌고, 아직
어떤 run에도 반영되지 않았다.

| 원인 | items | 처리 |
|---|---:|---|
| 같은 형식 파일이 여러 개일 때 selector가 선택을 포기 | **243** | `#190` |
| `required_visual_render_target_unavailable` 중 .docx | **65** | `#189` |
| 요청 형식(.xlsx/.pdf/.mp4/.docx)을 모델이 하나도 못 냄 | 12 | harness 결함 아님 — 모델 미제출 |
| `empty_final_text` | 4 | 위와 같음 |
| .docx 아닌 render target 부재 | 8 | 고칠 것 없음 — 아래 참조 (`318`) |
| visual file cap 초과 | 1 (+`#190` 이후 1) | 미해결, 소규모 |

333 중 308이 이미 고쳐졌다. 재실행하면 **~26 / 10,453 = 0.25%** 로 떨어진다 —
기준선을 내려서가 아니라 원인을 없애서 통과한다. 남는 26은 대부분 모델이 채점할
것을 실제로 안 낸 경우다.

**`.docx 아닌 render target 부재` 8건을 실제로 열어봤다** (`318-video-contact-sheet.md`).
이 줄은 "미해결"이라고 적혀 있었지만, 고칠 것이 하나도 없다.

* **6건**은 과제 `7de33b48`인데 채점된 파일 이름이 `failed_to_generate.txt`다.
  모델이 아무것도 못 낸 자리에 하네스가 놓아둔 표시 파일이다. 렌더 대상이
  없는 게 아니라 **결과물이 없다.** 바로 윗줄(모델 미제출)과 같은 종류다.
* **2건**은 `data_flow.txt`와 `MIG_Welding_Catch_Up_Summary.txt`에 대한
  "Overall formatting and style" 항목이다. 순수 텍스트 파일에는 볼 모양이 없다.
  **점수에서 제외한 것이 정답이고**, 여기에 0점을 주면 없는 결함을 지어내는 것이다.
* **영상은 이 8건 안에 하나도 없다.** sol-220은 *모델* 제출물을 채점하고, 모델은
  영상을 낸 적이 없다. 진짜 영상 파일은 **gold 185 corpus에만** 있고 거기서
  4건이 같은 이유로 못 채점됐다 — 그건 진짜 도구 한계였고, `318`이 고쳤다.

게이트와 별개로, **모델이 실제로 제출한 결과물에 0점이 매겨진 rubric item 243개**
(과제 5건)가 복구된다. 그 0점은 지금 발행된 숫자 안에 들어 있다.

**왜 5과제 부분 재채점이 아니라 전체 재실행인가.** 5건만 기존 파일에 덧붙이면 한
run 안에 서로 다른 두 채점 파이프라인이 섞인다. "새로운 기준이 기존 실험에 영향을
주면 안 된다"는 규칙이 막으려는 게 정확히 이 경우다. 전체 재실행에는 그 문제가
없다 — 출력 파일명이 grader source hash를 달고 있고 **그 해시는 이미 바뀌었다**:
발행본 `src_1c967673eb8081a6`, 현재 `src_c8144d680d028d88`
(`compute_grader_source_hash`, `step8_grade.py:136` 이 `batch-runner/core/` 의 모든
`.py`를 해싱하므로 `#189`·`#190` 둘 다 포함된다). 새 run은 새 파일로 떨어지고
**아무것도 덮어쓰지 않는다. 따라서 `force`는 반드시 `false`.**

**선행 조건: 해소됨.** 이 run의 formatting 판정은 LibreOffice 렌더에서 나오는데,
`#193`이 그 버전을 발행 corpus와 동일하게 고정하고 shard 9개가 같은 버전을
기록하도록 보장한다. 직전 시도에서 shard 3개를 fail로 만들었던 병합 오탐은
`#194`가 제거했다(C2) — 그건 R1을 멈추는 결함이 아니라 정상 상태를 실패로
보고하던 것이었다.

**canary는 여전히 한다.** 이유가 바뀌었을 뿐이다. 병합 때문이 아니라, shard 0의
judge-error 비율을 먼저 읽고 나머지 8개를 푸는 게 유료 run에서 싼 보험이기
때문이다. 바로 앞에 무료 `dry_run=true` 리허설도 같이 돌린다.

**그 보험이 첫 시도에서 바로 값을 했다.** 1차 카나리는 C3에 걸려 3시간 13분
만에 죽었다. 9개를 한꺼번에 풀었다면 같은 지점에서 9번 죽었을 것이다.
저장된 결과가 없으므로 재발주는 처음부터 다시 돈다.

**run이 도는 동안 main은 얼려 둔다.** shard 9개는 `grader_source_hash`와
`renderer_fingerprint`가 전부 같아야 병합된다(`step9_merge_shards.py:119`
`CONTRACT_IDENTITY_FIELDS`). 해시는 출력 파일명에도 `src_<16 hex>`로 박히므로
갈라진 shard는 애초에 다른 경로로 떨어져 영영 만나지 못한다. 그리고
`compute_grader_source_hash`는 `step8_grade.py` · `batch-runner/core/` 아래
**모든** `.py`(rglob) · `schemas/grade.schema.json` · `requirements.txt` ·
`scripts/download_inference_from_hf.py` · judge/tool 프롬프트 템플릿 ·
**채점 config YAML 자체**를 해싱한다. 이 중 하나라도 run 도중에 main에 들어가면
그 뒤 dispatch되는 shard는 다른 해시를 갖는다.

이게 위험한 이유는 **언제 걸리는가**에 있다. 해시 불일치는 dispatch 때도,
채점 때도 조용하다. 마지막 병합 단계에서야 거부된다 — 즉 **돈을 다 쓴 뒤에**.
C1이 apt 미러 drift를 막으려던 바로 그 실패 양식이고, 이번엔 미러가 아니라
우리 자신의 머지가 원인이 될 수 있다.

`grade-run.yml`은 해싱 대상이 아니지만 똑같이 건드리면 안 된다. auto-retrigger
resume 청크가 main에서 그 파일을 **다시 읽기** 때문이다. 러너 이미지 교체는
세 번째 이유로 더 위험하다 — LibreOffice 버전이 움직이면
`renderer_fingerprint`가 함께 움직인다.

**안전한 것:** 문서(`tasks/**`, `CHANGELOG.md`, `README*`), 대시보드
(`src/`, 루트 `scripts/`), 그리고 `batch-runner/tests/`. 셋 다 해시 목록 밖이다.
해시를 건드리는 작업은 브랜치에 준비만 해 두고 220-task `final`이 발행될 때까지
머지를 미룬다.

**푸는 것:** `< 2%` 게이트를 처음으로 정당하게 통과 · 303의 3회 중 1회를 겸함
(303의 추가 비용이 2회로 감소) · 300에 corpus 전체 비교 대상 제공.

dispatch 명령·canary 절차·acceptance는 board 카드
*"Re-grade all 220 tasks on the fixed pipeline (paid — owner gate)"* 에 있다.
**owner 승인 없이는 dispatch하지 않는다.**

## 자율 판단 결정 기록 (working memo)

이 작업의 owner agent가 SPEC 모호 영역에서 내린 결정. PR3 끝나면 CHANGELOG에 흡수.

| topic | decision | rationale |
|---|---|---|
| back-fill 정책 | (c) v1 보존 + v2 새 파일 명명 | published 데이터 손상 없이 비교 가능 |
| `total_max≤0` remediation | option 1 (positive-only denominator) | single-line change, 시멘틱 명확, option 2/3 후속 확장 여지 |
| critical 임계값 | `\|max_score\| >= 4` 상수 분리, 주석으로 "저자 signal 부재 컨벤션" 명시 | SPEC §4.4 직접 채택 |
| Grading skills 추출 | PR2 종료 후 grading-engineer agent용으로 추출 | 코드 안정화 후 skill 문서화가 자연 |
| tool 구현 방식 | library tool-calling (SPEC §4.2) 채택 | SPEC 명시 + 현 사용자 인프라(Azure Responses API) 부합 |
| prompt version bump | v1 → v2 archive 보존 | tool-aware 전환 명시 |
| PDF→image 백엔드 | `pdf2image+poppler` 대신 `PyMuPDF` (`fitz`) | 이미 requirements에 있고 wheel-only, GHA system 패키지 불필요 (task 200 audit) |
| 오디오/비디오 probe 백엔드 | `ffmpeg-python`/`moviepy` 대신 `PyAV` (`av`) 우선 | wheel이 ffmpeg 동봉, `grade-run.yml`에 `apt-get install ffmpeg` 추가 불필요 (task 200 audit) |
| `soundfile` 명시 의존 | 201에서 `requirements.txt`에 명시 추가 | 현재는 `librosa`/`pedalboard`의 transitive — 명시화로 fragility 제거 (task 200 audit) |
| v1 prompt 조기 교체 여부 | 교체하지 않고 `grader_judge_v2.md` 별도 신규 생성 + `grader_judge_v1_archive.md` 복사 보존. PR2 끝나고 207에서 v1 삽제 | 203 ToolCallingJudge는 legacy Judge와 공존 예정 — 둘 다 프롬프트 파일 필요 |
| perception routing 테스트 위치 | 기존 `test_grader_routing.py`(tier routing)와 분리해 `test_perception_routing.py` 신규 | concern 분리 — 207에서 legacy tier 테스트 삭제해도 modality routing 테스트는 살아남 |
| perception 클래스 의존성 주입 방향 | `client`을 생성자에 inject (클래스 내부 생성 X) | main judge가 Responses API 클라이언트 소유 + 테스트에서 FakeClient 제공 용이 |
| audio deployment 누락 처리 | `judge()` 호출 시점에 endpoint env 체크, 누락이면 `judge_error=endpoint_missing` graceful return | import-time hard fail 피하고 audio 항목에서만 결속 (main judge는 계속 동작) |
| grade-run.yml default config 교체 타이밍 | 2026-07-26 `default_v2_sol_max.yaml`로 전환 완료 | dry-run 기본, 명시적 paid 승인, protected `grading` environment를 함께 적용. 이전 5.4 config는 비교·재현용으로 보존. |
| 207 legacy 주니케이션 범위 | **조건부 PARTIAL** → **이후 해소됨 (PR3에서 확인)**: v1 sweep/tier configs (`validation_*`, `tiered_*`, `_sweep_template`, `recommended_*`) 명시 아카이브 + README + `_archive_v1/README.md`. **하지만** `core/grader.py`의 `_use_batch`/`_tier_judges`/`_summarize_deliverables`/`deliverable_extract_max_chars` 코드 렌더링 변경 없음. `core/grader_batch.py`도 올. | `default_gpt5pro.yaml`은 현재 default가 아니라 historical comparison identity로 보존. legacy 코드 제거는 별도 cleanup PR에서 기존 historical config 재현성과 함께 처리. **→ 그 cleanup은 실제로 이루어졌다.** 위 넷과 `core/grader_batch.py`는 현재 저장소에 없고 `tests/test_grader.py:875-896`이 부재를 검사한다. 이 행은 당시 결정의 기록으로 남기며, 현재 상태는 207 행을 본다. |

## 작업 흐름 (자동, 사용자 개입 없음)

각 task별:
1. 해당 task md 읽고 변경 범위 확정
2. 코드 변경
3. 영역 테스트 + 회귀
4. 통과 → commit + push
5. task md 상태 ☐ → ✅ 업데이트 (이 OVERVIEW)
6. 다음 task 자동 진행

PR 단위:
1. 마지막 task 완료 시 PR-요약 리포트 1장 (`PR{N}_REPORT.md`)
2. 검증 게이트 자동 실행
3. PASS → 다음 PR (또는 새 세션 핸드오프 메모)

## 비목표 (다시 확인)

- inference / 220 deliverable 재생성 안 함
- pro/hybrid를 default로 채택 안 함
- pairwise-vs-gold(GDPval 표준 win-rate) 모드 구현 안 함 (별도 후속)
- 비디오 *지각* 채점 안 함 (objective probe까지만)
