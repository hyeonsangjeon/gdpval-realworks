# CODEX — gold 20 렌더+vision 검증 (메타데이터로는 부족한 Overall Style을 렌더로 메우나)

- **Repo:** `gdpval-realworks`, `main` (selector+audit+gold 머지 완료)
- **상황:** 220 clean 재채점에서 "Overall formatting and style"의 v2(메타데이터-only) vs owner gold가 **MAE 1.21/5**, 개별 오차 큼(`99ac6944` -2.5, `bbe0a93b` -3.0, `85d95ce5` +2.5, `403b9234` -1.75). under/over가 상쇄돼 평균만 중립. modality MAE: PDF 1.70 > XLSX 1.20 > PPTX 1.00, docx는 +1.0 체계적 후함. visual item 337개 중 232개 + audio 58개 전부가 `perception_called=false`로 채점됨.
- **목적:** "Overall style"을 **렌더된 이미지 + 메타데이터**로 채점하면 owner gold에 *가까워지는가*를 gold 20개로 싸게 검증. 가까워지면(MAE 감소 + 회귀 없음) 220 전체 렌더 투자 정당화. 아니면 접근 재고.
- **범위:** gold 20개 검증만. 220 전체 재채점·파이프라인 통합·GHCR 빌드는 범위 밖(이 검증 통과 후 별도). **audio는 이 작업 대상 아님**(audio deliverable이 7개 모두 wrong_format으로 미생성 — 채점할 audio가 없음. audio perception은 audio 생성 트랙이 푼 뒤 별도).

## ⛔ GIT 행위 절대 금지 (강제 — 이전 자율머지 위반 재발 방지)
- `git push`/`merge`/`commit`/`rebase`/`reset`/`revert`/`checkout <file>`/`tag`/`branch -f` **전부 금지.**
- git은 read-only(`status`/`log`/`diff` 조회만). **main에 어떤 것도 push/머지 금지.**
- 산출(렌더 png, 검증 md)은 파일로 쓰되 **커밋하지 마라**(owner 검토 후). 어떤 이유로도 git 상태 바꾸지 마라. 위반 시 중단 보고.

## 인증 — 로컬 (gold 20개라 로컬로 충분)
- owner 로컬 `az login` 세션 사용. 채점 전 stale SP env unset + 토큰 테스트(이전 스모크와 동일):
  ```bash
  cd batch-runner; set -a; source .env; set +a
  unset AZURE_CLIENT_ID AZURE_CLIENT_SECRET AZURE_TENANT_ID
  # AzureCliCredential / DefaultAzureCredential token_ok 확인 후 진행
  ```
- `.env` 파일 수정 금지(현재 셸 env만 unset). SP secret reset/조작 금지.
- 인증 막히면 멈춰 보고(git/secret 우회 금지).

## 렌더 (probe에서 검증된 경로)
- 각 gold deliverable을 이미지로: PDF/이미지는 PyMuPDF 직접, XLSX/DOCX/PPTX는 `soffice --headless --convert-to pdf` → PyMuPDF PNG.
- 로컬 macOS에 LibreOffice 있으면 사용(probe에서 확인됨). 폰트 누락으로 □(tofu) 나면 — 그게 *소스 파일 결함*인지 *폰트 문제*인지 구분(probe처럼). 폰트 문제면 설치, 소스 결함이면 그대로(실제 결함이니 vision이 봐야 함).
- 렌더 범위: XLSX는 데이터/표/차트 보이는 시트, DOCX 첫 페이지+표 페이지, PPTX 슬라이드들, PDF 전 페이지(짧으면).
- 렌더 png는 `tasks/0607_sunday/vision_validation/png/`에 저장(커밋 금지).

## vision 채점 (입력 = 렌더 png + 기존 메타데이터, 둘 다)
- gold 20개의 "Overall formatting and style" criterion을, **렌더 png + 기존 formatting 메타데이터를 함께** judge(vision 가능 모델)에게 주고 채점.
- 즉 현재 메타데이터-only 대비 *이미지를 추가*했을 때 점수가 owner gold에 가까워지는지 측정.
- split_children 4개(`27e8912c`/`a74ead3b`/`bbe0a93b`/`6dcae3f5`)는 각 child를 렌더+채점 후 `blocking_min_else_mean` 집계(기존 정책 유지).
- vision judge가 *렌더를 실제로 근거로* 삼는지(evidence에 시각적 관찰이 있는지) 확인 — 파일명/텍스트만으로 답하면 안 됨.

## 측정 (핵심 — 점수 상승 아니라 gold와의 거리)
**"점수가 올랐나"가 아니라 "owner gold와의 거리(|v2 - owner|)가 줄었나"로 판정.** 양방향(under/over) 다.

1. **격차 큰 항목 개선:** `99ac6944`(-2.5)/`bbe0a93b`(-3.0)/`85d95ce5`(+2.5)/`403b9234`(-1.75)/`9a0d8d36`(-1.5)/`7bbfcfe9`(-2.0) 등이 렌더 후 owner에 *가까워지나*(|delta| 감소).
2. **회귀 없음(positive control):** 이미 owner와 가까운 항목 — `f9a1c16c`(0.0)/`6dcae3f5`(-0.25)/`a74ead3b`(-0.25)/`43dc9778`(-0.5) — 이 렌더 후에도 *유지*되나(|delta| 증가 안 함). 렌더가 멀쩡한 걸 망가뜨리면 안 됨.
3. **전체 MAE:** 메타데이터-only 1.21 → 렌더+메타데이터 [?]. 이게 220 전체 렌더 투자의 값어치 판정.
4. **modality별 MAE 변화:** PDF 1.70 / XLSX 1.20 / PPTX 1.00 / docx(+1.0 후함)가 각각 어떻게 바뀌나 — 렌더가 *어느 modality*에 가장 효과 있는지(220 우선순위 정함).

## 판정
- MAE 줄고 + 회귀 없으면 → "렌더+vision이 Overall style 정확도를 올린다, 220 전체 적용 정당화. 우선순위 modality = [MAE 가장 준 것]."
- MAE 안 줄거나 회귀 있으면 → 어느 항목이 왜 안 됐는지 보고. 렌더 품질 문제인지(폰트/범위) vision 판단 문제인지 구분. **임의로 더 손대지 말고 멈춰 보고.**

## 권한/제약
- gold 20개만. 220 전체·통합·GHCR 빌드 없음.
- ⛔ git 상태 변경 전부 금지. 산출은 쓰되 커밋 금지.
- 인증: 로컬 stale env unset(`.env` 불변), secret 조작 금지.
- audio 대상 아님(채점할 audio 없음).
- 측정 = gold와의 거리(MAE), 점수 상승 아님. 회귀 확인 필수.
- 막히면 방향 틀지 말고 보고(git/secret 우회 금지).
- 비용 인지: vision 호출(gold 20개 Overall style + split children분).

## 출력 — `tasks/0607_sunday/vision_validation.md` (커밋 금지)
```
# VISION RENDER VALIDATION — gold 20 Overall Style
## 한 줄 결론
렌더+메타데이터 vs 메타데이터-only: 전체 MAE 1.21 -> [?]. 격차 큰 [N]개 개선, positive control [회귀 0/있음], modality별 [PDF/XLSX/PPTX/docx MAE 변화]. 판정: 220 전체 렌더 [정당화/재고]. git 상태 변경 없음.
## 렌더 (20개 png 생성, tofu 구분, 실패 항목)
## vision 채점 (렌더+메타데이터, split 4개 child 집계, evidence가 시각 근거인지)
## 측정 표 (task별 owner / 메타only v2 / 렌더+vision / |delta| 변화)
## 회귀 확인 (가까운 항목 유지?)
## modality별 MAE 변화 (어디에 렌더가 가장 효과 — 220 우선순위)
## 판정 + 다음 (정당화 시: GHCR 빌드 -> 220 렌더 통합 -> mini vs 5.4)
```

## 제약 재확인
- gold 20개만, 220/통합/GHCR 없음.
- ⛔ git push/merge/commit 등 전부 금지, read-only git, 커밋 금지.
- 측정 = MAE(gold와 거리), 회귀 확인 필수, 점수 상승 아님.
- audio 제외. 로컬 인증(secret 조작 금지).
- 막히면 보고(우회 금지).
