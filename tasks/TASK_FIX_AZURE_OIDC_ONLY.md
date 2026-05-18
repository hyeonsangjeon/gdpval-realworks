# TASK_FIX_AZURE_OIDC_ONLY — Azure 인증 OIDC 전용 강제

## 배경
exp025 dry_run에서 220/220 inference 실패 (403 AuthenticationTypeDisabled).

## 진단 (Claude Desktop 분석 정정)

**Claude Desktop 분석은 부분 오류:**
- spec 주장: "create_client() except의 API key fallback이 key 인증 시도"
- **실제**: fallback **미도달**. OIDC try 블록 정상 성공:
  ```
  🔐 Auth: DefaultAzureCredential (Entra ID token)  ← 정상 출력됨
  [1/220] ✗ 403 - AuthenticationTypeDisabled        ← 그래도 403
  ```

**진짜 원인 (검증 완료):**
`openai` SDK의 `AzureOpenAI` 클래스가 환경변수 `AZURE_OPENAI_API_KEY`를 **자동 감지**해
`api-key` 헤더로 전송. 우리가 명시한 `azure_ad_token_provider`를 silently 덮어씀.
Azure 리소스 `disableLocalAuth=true`라 키 거부 → 403.

검증 근거: `batch-runner/core/llm_client.py:172-184` 의 OIDC `try` 블록이
`return AzureOpenAI(azure_ad_token_provider=token_provider, ...)` 로 정상 반환하며
`🔐 Auth: DefaultAzureCredential` 로그가 실제 출력됨. except fallback(187-194)은
도달조차 안 됨. 그럼에도 403 발생 → SDK가 env 의 키를 자동 픽업해 헤더에 실은 것.

## 수정 사항

### Fix A — `.github/workflows/batch-run.yml` (정확히 3곳)
다음 3개 step 의 env 블록에서 `AZURE_OPENAI_API_KEY: ${{ secrets.AZURE_OPENAI_API_KEY }}` 줄 제거:
1. **Step 2a** (line 256, `'Step 2a: Run inference (condition_a)'`)
2. **Step 2b** (line 373, `'Step 2b: Run inference (condition_b)'`)
3. **Step 6** (line 417, `'Step 6: Generate experiment report'` — Desktop spec 누락분, step6도
   `step6_report.sh` → `create_client()` 호출, continue-on-error: true)

유지: `AZURE_OPENAI_ENDPOINT`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` (다른 provider 용).
(Step 6 env 는 원래 `AZURE_OPENAI_ENDPOINT` + `AZURE_OPENAI_API_KEY` 둘뿐 →
ENDPOINT 만 남김)

주석 추가 (각 제거 위치 또는 대표 위치):
`# Removed AZURE_OPENAI_API_KEY — openai SDK auto-detects env key and overrides azure_ad_token_provider. OIDC only via DefaultAzureCredential / azure/login@v2.`

### Fix B — `batch-runner/core/llm_client.py` `create_client()`
except 블록(현 185-200)의 API key fallback `if api_key: return AzureOpenAI(api_key=...)`
분기를 제거하고, 항상 명시적 raise 로 변경 (fail-loud):

```python
except Exception as e:
    print(f"   ⚠️  DefaultAzureCredential failed: {e}")
    print(f"   ⚠️  API Key fallback disabled (Azure disableLocalAuth=true)")
    print(f"   ⚠️  Local: run 'az login' then retry")
    print(f"   ⚠️  CI: verify azure/login@v2 OIDC step succeeded")
    raise ValueError(
        f"Azure authentication failed.\n"
        f"  - DefaultAzureCredential failed: {e}\n"
        f"  - API key fallback disabled (disableLocalAuth=true).\n"
        f"  Fix: 'az login' locally, or check OIDC config in GitHub Actions."
    )
```

(이 버그의 직접 fix 아님 — fail-loud 하드닝. 미래 다른 인증 실패를 silent 로 만들지 않음.
docstring 의 "API Key fallback" 표현도 현실에 맞게 정정 권장.)

## Acceptance
- workflow YAML 3곳에서 AZURE_OPENAI_API_KEY 제거 (grep 결과 0건)
- llm_client.py except 블록이 raise (api_key 분기 제거)
- 다른 provider(anthropic, openai-native) 무영향
- V2 + silent-corruption 회귀 0 (140+ passed 유지)
- workflow YAML 정합성 OK (yaml.safe_load 통과)
- secrets 0 (env 줄 제거하는 거지 노출 X)

## Failure Policy
- 기존 테스트 회귀 → REJECT
- first-reviewer/extreme-reasoner REJECT → 1회 재시도
- 분류기 차단 → 즉시 중단 + 보고

## Out of Scope
- Azure App Registration / OIDC 설정 변경
- 다른 provider 로직
- 다른 workflow 파일
- 대시보드 / UI
