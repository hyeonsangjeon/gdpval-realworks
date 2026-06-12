# CODEX — exp003 전체 220 재채점 [judge=gpt-5.4, 순차 OIDC relay] = 최종 baseline

- **Repo:** `gdpval-realworks`, `main` (selector+audit+evidence fix+gold 머지 완료)
- **결정 확정:** 채점기 모델 = **gpt-5.4 (full)**. 근거: mini는 판단형(formatting/visual) criterion에서 신뢰 불가(MAE 1.18, RANDOM), 5.4가 −28% 개선. 예산 여유(PayGo, 월 한도 대비 사용 적음)로 전부 5.4 채택(하이브리드 대신 단순성). 이번 재채점이 **대시보드/벤치마크의 최종 공식 baseline**이 된다.
- **목적:** 깨끗한 selector+audit 파이프라인 위에서 **judge를 mini→gpt-5.4로** 바꿔 220 전체를 한 번 재채점. 기존 mini baseline(`data/grades/...judge_gpt-5_4-mini__rubric_v2_tools_mini.json`)을 대체하는 게 아니라 *병렬 산출*(5.4 버전 별도 파일)로 두고 비교.
- **범위:** 220 재채점 1회(judge=5.4) + gold 20 재비교 분석. **pptx 렌더는 이번 범위 밖**(5.4-only baseline 먼저 → 이후 pptx 선별 렌더를 얹어 "5.4 vs 5.4+렌더" 비교). 모델/코드 변경 없음(judge config만 5.4로).

## ⛔ GIT 행위 절대 금지 (강제 — 이전 자율머지 위반 재발 방지)
- `git push`/`merge`/`commit`/`rebase`/`reset`/`revert`/`checkout <file>`/`tag`/`branch -f` **전부 금지.** read-only git만(`status`/`log`/`diff` 조회만). **main에 어떤 것도 push/머지 금지.**
- 분석 산출은 파일로 쓰되 **커밋하지 마라**(owner 검토). 어떤 이유로도(편의/막힘/최적화) git 상태 바꾸지 마라. 위반 시 중단 보고.
- 단, **재채점 grade JSON은 OIDC 워크플로의 정상 산출 경로**로 생성/푸시되는 게 정상(mini 때 chunk별 commit처럼) — 이건 파이프라인 동작이지 agent의 임의 git 조작이 아님. 워크플로 *밖에서* agent가 수동 commit/merge 하는 것만 금지.

## 인증 — OIDC (로컬 아님)
- 220은 GitHub Actions **OIDC 파이프라인**에서. 로컬 `az login`은 긴 run에서 세션 만료 위험. OIDC는 워크플로마다 federated token이라 안정적.
- **SP secret reset/조작 금지** — OIDC federated credential이지 secret 회전 아님. 로컬 `.env` stale SP env 문제는 OIDC엔 무관.

## 동시성 정책 — 순차 (PayGo TPM 보호)
- 리소스는 **PayGo(Standard)**. 병목은 TPM/RPM. **병렬 dispatch 하지 마라** — TPM 천장 초과 시 429 폭탄 + 재시도 오버헤드로 오히려 느려지고, relay checkpoint 경합/snapshot validation 버그 위험.
- **mini 때와 동일한 순차 relay 구조 사용**(검증됨): 4-chunk 순차, wall-timeout 시 checkpoint를 HF `_checkpoint/`에 저장 → 다음 relay window 자동 트리거(`relay_max_runs`까지). 한 번에 한 window.
- 5.4는 reasoning 토큰으로 output이 mini보다 클 수 있어 **window당 처리량이 mini보다 적을 수 있음** → relay window가 더 많이 필요할 수 있음(정상, 그냥 순차로 흘려보냄). 시간 급하지 않으므로 throttle 시 재시도하며 순차 진행.
- 429가 나면 백오프 재시도(순차 유지). 동시성 올려서 우회하지 마라.

## 재채점 실행
- exp003 전체 220 task, v2 tool-calling 경로, **judge config만 mini→gpt-5.4**. selector+audit 코드는 main 그대로(스모크/220-mini에서 검증됨, 변경 없음).
- **config 네이밍:** 기존 mini config(`default_v2_mini.yaml` 및 출력 `...judge_gpt-5_4-mini__rubric_v2_tools_mini.json`)를 *미러링*해 5.4 버전 생성 — judge model/deployment를 `gpt-5.4`로, 출력 파일명도 기존 관례 따라 5.4 식별자로(예: `...judge_gpt-5_4__rubric_v2_tools.json`). repo의 기존 네이밍 관례를 따르되 mini와 *구분*되는 별도 파일.
- **mini baseline 파일을 덮어쓰지 마라** — 5.4는 별도 파일. 둘 다 보존해 비교.
- audit 필드가 5.4 재채점에도 220 전체 0 누락으로 기록되는지(mini 때처럼).
- snapshot validation 버그 주의: HF repo에 이미 220 row 있으면 fresh-run 로직 오적용 → relay-resume 시 emptiness check 완화 또는 별도 5.4 snapshot 경로.

## 재채점 후 검증 + gold 비교
1. **전체 요약:** graded/error task 수, selection_status 분포(mini와 동일해야 — selector는 모델 무관), avg_score_pct, critical_pass.
2. **5.4 vs mini 전체 비교:** 같은 220에서 judge만 다를 때 점수 분포 차이(5.4가 전반적으로 더 엄격한지 — text 분석에서 5.4 과보수 경향 관찰됨). wrong_format/selection_status는 동일해야(모델 무관).
3. **gold 20 재비교 (핵심):** 5.4 재채점의 "Overall style" vs owner gold — **220 전체 파이프라인 5.4가 gold 20 검증의 MAE 0.85를 전체에서도 유지/근접하는지.** modality별(pdf/xlsx/pptx/docx) MAE.
4. **5.4 과보수 경향 확인:** text 분석에서 5.4가 "증거 안 보이면 fail/partial"로 과보수했음. 220 전체에서 이 경향이 어떻게 나타나는지(text criterion 점수가 mini보다 체계적으로 낮은지) — 이게 향후 프롬프트 튜닝 포인트.
5. **비용 실측:** 5.4 judge calls, input/output 토큰, 실제 비용(raw/cached). mini $29 대비 실제 배수(추정 5배가 맞았는지, reasoning 토큰으로 더 늘었는지).

## 권한/제약
- ⛔ git 상태 변경 전부 금지(워크플로 정상 산출 제외). read-only git. 분석은 쓰되 커밋 금지.
- 220 재채점 **1회**(judge=5.4). 같은 걸 두 번 돌리지 마라(비용). relay 재개는 1회 run의 연장.
- **순차 relay만. 병렬 dispatch 금지**(PayGo TPM 429 방지). 429는 백오프 재시도, 동시성 우회 금지.
- judge config만 5.4. selector/점수/verdict 로직 불변. mini baseline 파일 보존(덮어쓰기 금지).
- pptx 렌더 이번 범위 밖.
- 막히면(인증/snapshot/relay/429) 방향 틀지 말고 무엇이 막혔는지 보고. git/secret 우회 금지.
- 비용 인지: 220 전체 5.4(추정 ~$146, reasoning으로 더 늘 수 있음). 예산 여유 확인됨.

## 출력 — `tasks/0607_sunday/full_regrade_220_gpt54.md` (커밋 금지)
```
# FULL REGRADE 220 — judge=gpt-5.4 (final baseline)
## 한 줄 결론
220 재채점 완료(judge=5.4, 순차 OIDC relay). selection 분포 [mini와 동일?], avg_pct [?], gold 20 "Overall style" MAE [0.85 유지?], 5.4 과보수 경향 [text 점수 mini 대비?], 실측 비용 $[?](mini $29의 [N]배). mini baseline 보존, 별도 파일. git 수동조작 없음.
## 전체 요약 (graded/error, selection 분포, avg_pct, critical_pass)
## 5.4 vs mini 전체 비교 (점수 분포 차이, selection 동일성 확인)
## gold 20 재비교 (Overall style MAE, modality별 — 0.85 전체 재현되나)
## 5.4 과보수 경향 (text criterion 점수 mini 대비 체계적 차이 — 튜닝 포인트)
## 비용 실측 (calls/토큰/비용, mini 대비 배수)
## audit 필드 (220 전체 0 누락 확인)
## 다음: pptx 선별 렌더를 5.4 baseline 위에 (5.4 vs 5.4+렌더) → 블로그 작성
```

## 제약 재확인
- ⛔ git push/merge/commit 등 전부 금지(워크플로 정상 산출 제외), read-only, 커밋 금지.
- 순차 relay만, 병렬 금지(PayGo 429 방지), judge=5.4, 재채점 1회.
- mini baseline 보존(별도 파일), selector/점수 로직 불변, pptx 렌더 범위 밖.
- gold 20 MAE가 전체에서 재현되는지 + 5.4 과보수 경향 확인이 핵심.
- 막히면 보고(우회 금지).
