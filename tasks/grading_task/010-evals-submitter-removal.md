# 010 — `core/evals_submitter.py` 삭제 (C1 = a 확정)

## 결정

**삭제** (a). _deprecated로 이동(b) 옵션 폐기.

## 근거

1. **Placeholder URL** — `EVALS_ENDPOINT = "https://evals.openai.com/api/submit"`
   는 한 번도 200 응답을 받은 적 없음. 주석에 "actual endpoint may be
   different or may not exist" 명시.
2. **Production 호출처 0건** — grep 결과 import는 자기 자신 + 테스트뿐.
   step7_upload_hf.sh, batch-run.yml 어디서도 호출 안 됨.
3. **OpenAI 호스팅 종료** — 미래에 API가 재개되더라도 spec을 알 수
   없으므로 그때 새로 작성하는 게 깔끔.
4. **Dead code 보존 비용** — 누군가 미래에 잘못 쓰는 위험 + 라이브러리
   업그레이드 시 불필요한 fix 부담.

## 삭제 대상

| 경로 | 액션 |
|---|---|
| `batch-runner/core/evals_submitter.py` | `git rm` |
| `batch-runner/tests/test_evals_submitter.py` | `git rm` |
| `.github/agents/llm-systems-engineer.md` | "OpenAI Evals integration" 한 줄 제거 |

## 검증

```bash
# 삭제 후 import 잔재 확인 (없어야 정상)
grep -r "evals_submitter\|EvalsSubmitter" \
  --include="*.py" --include="*.sh" --include="*.yml" --include="*.md"
# expected: 0 matches (또는 deprecation comment 1줄만)

# pytest 통과 확인
cd batch-runner && pytest -q
```

## CHANGELOG 엔트리 (PR #1 작성 시 추가)

`### Removed` 섹션 신설 또는 기존 `[Unreleased]`에 추가:

```markdown
### Removed

- **`core/evals_submitter.py` (dead code).** This module was a
  placeholder for evals.openai.com hosted grading submission. The API
  endpoint was a guess (`"https://evals.openai.com/api/submit"`) — never
  validated as working — and the module had zero production callsites.
  OpenAI has since [ended hosted grading](https://evals.openai.com/gdpval/grading)
  and open-sourced their rubrics on
  [openai/gdpval](https://huggingface.co/datasets/openai/gdpval) for
  community self-evaluation. We are building a separate self-grading
  pipeline (`step8_grade.py` + `grade-run.yml`, see PR #N) so this dead
  module is removed rather than retained. The associated test file is
  also removed. (PR #N)
```

## 의존성

- 없음 (다른 명세에 input 아님). PR #1에 단독 항목으로 포함.

## 비고

- `.github/agents/llm-systems-engineer.md`의 architecture 다이어그램에서
  해당 라인을 제거할 때 다른 모듈 설명은 건드리지 않음 (최소 변경).
- 011 (grading-engineer.md) 추가 시 같은 agent 인덱스에 신규 라인 추가
  하는 게 자연스러움.
