# CODEX — perception wiring 마무리 (기술 PR, flip과 분리)

- **Repo:** `gdpval-realworks` (local, branch `feat/wire-perception`)
- **전제:** v2-mini default flip은 폐기됨(modality 6%, 후퇴는 perception 밖). **이 작업은 flip과 무관한 기술 PR이다** — "dead config(perception)를 실제 wiring으로 바꾸고, 그게 런타임에 작동함을 증명하고, 머지 가능 상태로 만든다." flip을 되살리려는 게 아니다. 106/220 task가 visual/audio item을 가지므로 perception을 켜두는 것 자체는 그 item 채점 품질에 의미가 있다.
- **목적:** Codex 검수가 짚은 **audio endpoint 버그**를 고치고, Azure 인증을 복구해 **live perception 발화를 한 번 증명**한 뒤, owner 리뷰용으로 PR을 정리.

## 성공 기준
- audio 경로가 vision과 **따로** 검증됨(둘을 한 테스트로 뭉뚱그리지 말 것).
- live probe에서 `perception_called`/`tools_used` instrumentation이 *실제 Azure 호출 기준으로* 찍힘 — 단위테스트 아님.
- 안 되면 "안 됨"으로 정직하게. 미검증을 검증인 척 금지(rule 12).

## 권한/제약
- 사전 승인: live perception probe(소규모, 인증 복구 후), 단위테스트.
- 금지: full-220 run, cost-cap 수정, **main push/머지**(owner-go 필요, rule 13). 작업은 `feat/wire-perception` local commit만.
- dead config(grades_per_task/compaction)는 이 PR 범위 아님 — 건드리지 마라.

## STEP 1 — audio endpoint 버그 fix (Codex 발견)
- `AudioPerception`이 availability check엔 `AZURE_AUDIO_ENDPOINT`를 쓰는데 실제 client는 top-level `AZURE_OPENAI_ENDPOINT`로 만든다 — availability와 실제 호출 endpoint가 갈릴 수 있다.
- 코드를 읽어 확인하고, **audio client가 audio deployment의 올바른 endpoint를 쓰도록** 정합화해라. audio가 같은 리소스/다른 endpoint 양쪽 케이스를 코드가 어떻게 다루는지 명시.
- 너 메모리/문서상 audio는 `gpt-audio-1.5` 계열 — 그 deployment가 `dlstmvprtus-wingnut0310-ai` 리소스에 있는지, 별도 endpoint인지 config로 확인.
- vision 경로도 같은 endpoint-mismatch 패턴이 없는지 같이 점검.

## STEP 2 — Azure 인증 복구 (전제조건)
- 현재 막힘: OIDC `AADSTS7000215 Invalid client secret`(SP secret 만료/회전 필요) + key fallback `403 AuthenticationTypeDisabled`(Conditional Access로 local auth 영구 비활성).
- **SP secret 회전은 owner 작업이다** — Azure AD App `gdpval-realworks-github-actions`(appId `f5e0ecfa-6d29-46b1-bdff-bb19ed3307ba`)에 새 client secret 발급 → `.env`/GitHub Secret 갱신. agent는 *무엇을 갱신해야 하는지*만 명확히 안내하고, secret 값 자체는 다루지 마라.
- key-based auth는 쓰지 마라(rule 8, OIDC only). 복구는 OIDC 경로로.
- **이 STEP이 막히면 STEP 3을 못 한다 → owner-go로 표시하고 STEP 1 결과까지만 보고.**

## STEP 3 — live 발화 증명 (인증 복구 후)
- visual criterion + audio criterion을 *각각* 포함한 소규모 set으로 perception probe 실행(기존 `scripts/phase2_perception_probe.py` 또는 N≈10 re-smoke).
- 확인: visual item에서 `vision_judge_called=true` + `tools_used`에 `render_to_image`/`vision_judge`; **audio item에서 `audio_judge_called=true` + audio가 올바른 endpoint로 갔는지**(STEP 1 fix 검증). 호출 0건이면 wiring/endpoint 미완 → 고쳐라.
- judge_error, 추가 토큰/비용 기록.

## STEP 4 — PR 정리
- 변경 요약(파일:라인), 단위테스트 + live probe 결과, 알려진 한계(인증 막혔으면 그 사실)를 PR description으로.
- **"이 PR은 perception을 wiring하는 기술 정리이며 v2-mini flip 근거가 아니다"를 명시.**

## 출력 — `tasks/0531_sunday/perception_merge_ready.md`
```
# PERCEPTION WIRING — MERGE READINESS
## 한 줄 결론
audio endpoint fix: [완료/필요] / 인증 복구: [됨/owner 대기] / live 발화: [vision ✓/✗, audio ✓/✗] / 머지 가능: [예/owner-go 대기]
## STEP 1 — audio(+vision) endpoint 정합화 (파일:라인)
## STEP 2 — 인증 상태 / owner가 할 것
## STEP 3 — live 발화 증명 (vision/audio 따로)
## STEP 4 — PR 요약 + 한계
```

## 제약 재확인
- flip 되살리기 아님 — 기술 PR. 
- audio/vision 따로 검증. 미검증을 검증인 척 금지.
- SP secret 값은 안 다룸 — owner 안내만. main push/머지 금지.
