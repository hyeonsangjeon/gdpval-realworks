# CODEX — 닫기: v2-mini flip 폐기 기록 (공짜, 1파일)

- **Repo:** `gdpval-realworks` (local, `main`)
- **목적:** `tasks/rebuilding_grading_task/FINAL_RECOMMENDATION.md`가 아직 "default_v2_mini 권장"으로 남아있다. flip은 데이터로 폐기됐으므로, 옛 문서 보고 누가(또는 agent가) flip을 재시도하지 않게 SUPERSEDED 표식을 단다.

## 작업
`FINAL_RECOMMENDATION.md` **맨 위에** 아래 배너를 추가해라(기존 본문은 audit trail로 *삭제하지 말고* 그대로 둔다):

```
> ⛔ SUPERSEDED (2025-06-01) — 이 문서의 "default_v2_mini를 production default로" 권고는 폐기됨.
> 근거: (1) v2-mini는 현재 default(v1-mini) 대비 critical_pass에서 9~15pp 후퇴(같은 10-task, 같은 집계). 
> (2) 후퇴 3건은 전부 formatting(perception 밖), standard 대비 leniency 38건 중 32건은 text — 둘 다 perception wiring으로 안 고쳐짐(phase0). 
> (3) perception이 만질 수 있는 visual+audio는 전체 critical의 6%(29/483), 7개 task에 한정(modality_distribution.md). benchmark-wide flip 정당화 불가.
> 결정: v2-mini default flip 폐기. v1(default_gpt5pro) 유지. perception wiring 브랜치는 flip과 분리된 기술 PR로만 평가.
> 상세: tasks/0531_sunday/ (PERCEPTION_THESIS_REPORT.md, modality_distribution.md).
```

## 제약
- 본문 기존 내용 삭제·수정 금지(배너만 추가). 
- 다른 파일 건드리지 마라. main push/머지 금지 — local commit만, owner 리뷰.
- 날짜는 실제 오늘 날짜로.
