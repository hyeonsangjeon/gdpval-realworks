# 네이티브 Sol 응답 증빙 캡처

다음 연결 스모크와 파일럿에서 응답 본문·헤더를 마스킹해 보관하고,
그 파일의 SHA256과 응답 필드를 receipt에 남기는 경로를 추가했다.
필수 필드나 안전한 원문 저장이 없으면 CLI에 응답을 전달하지 않는다.
이는 **수집 준비**이며 Sol·Max·1M의 실제 적용 증명은 아니다.
기존 10개 실행 막힘은 해제하지 않았다. 실제 모델 호출은 이번 작업 범위 밖이다.

## 구현 범위와 저장 계약

`gpt56_native_response_capture.py`의 `NativeResponseArtifacts`를 기존
`gpt56_pilot_wire_receipt.py`의 시도별 loopback 기록기에 연결했다.
`core/codex_runner.py::open_runtime`은 연결 진단에도 같은 기록기와 초기화
감시를 사용한다. 파일럿 경로의 기존 세션·소스·계정 검사는 유지한다.

| 구분 | 기록 위치·의미 |
| --- | --- |
| 원문 파일 | 응답 상태·헤더 목록·`body_utf8`를 담은 JSON. HTTP entity 본문이며 TLS 패킷이나 chunk framing 원본은 아니다. |
| SHA256 | 비밀값을 마스킹한 **저장 파일 바이트**의 해시. 마스킹 전 원문 해시나 공급자 서명은 아니다. |
| 파일럿 receipt | `transport.provider_observation.response_evidence` 및 Step 2의 같은 진단 필드. 원문·헤더는 receipt에 넣지 않는다. |
| 연결 진단 receipt | 새 Sol 진단 `/4`의 `observed.provider_response_evidence`. `--out`의 부모 아래 `codex-foundry-connection-responses/`에 저장한다. |
| 공개 전 검사 | 기존 workflow의 leak-check 안에서 해시·일반 파일·마스킹·누락/추가 파일을 확인한 뒤에만 별도 응답 파일을 artifact에 포함한다. |

파일은 덮어쓰지 않으며 디렉터리 0700·파일 0600을 사용한다. 헤더의
인증·쿠키·토큰 필드, 이미 전달받은 인증값, JSON 비밀 필드, JWT·Bearer·
일반 토큰 패턴과 URL을 마스킹한다. JSON escape와 TCP 조각 경계도 검사한다.
마스킹 전 임시 파일은 쓰지 않는다. 이는 지정된 비밀값·패턴의 마스킹이지
모든 개인정보를 익명화한다는 보장은 아니다. 새 자격증명을 찾거나 읽지 않는다.

캡처 메모리는 응답당 4 MiB로 제한한다. 이는 관측 도구의 바이트 한도이며
300,000 입력 토큰·10,000 출력 토큰 상한이나 공급자 토크나이저가 아니다.
불완전·인코딩 미지원·용량 초과 응답은 통과시키지 않는다. 저장 지연으로
마감시각을 넘기면 프로세스 정리를 먼저 진행하며 늦은 저장을 성공 증빙으로
되살리지 않는다. 저장 자체가 불가능하면 원문/해시가 있다고 주장하지 않는다.

## 응답 필드와 실패 판정

| 고정 필드 | 실제로 읽는 곳 | 누락 시 |
| --- | --- | --- |
| `served_model` | 최종 provider response 객체의 `model` | `not_reported`, `served_model_unverified` |
| `served_model_version` | 같은 객체의 명시적인 `model_version` | `not_reported`; 모델 이름의 날짜나 소유자 inventory에서 추정하지 않는다. |
| `reasoning_effort` | 같은 객체의 `reasoning.effort` | `not_reported`, `reasoning_effort_unverified` |
| `context_tokens` | `context_window` / `model_context_window` / `context_window_tokens` / `tokenLimit` / `modelContextWindow`의 유효한 정수 | `not_reported`(기록만, 중단 아님 — 2026-10-30 소유자 결정). 서로 다른 값이 둘 이상이면 `context_window_mismatch` |

위 context 경로는 **앞으로 받을 응답의 검사 계약**이다. 실제 Foundry가
이 필드를 내보낸다는 근거가 아니다. 잘못된 타입과 서로 다른 context
값도 통과시키지 않는다. 원문은 별도 파일에서 검토할 수 있다.
요청 설정, SDK thread 설정, rollout, app-server의 258400 표시에서
응답 필드를 채우지 않는다. `observed`는 응답에 값이 있었다는 뜻이며
실제 모델 내부 동작·Max 효과·1M 처리 능력의 독립 증명으로 승격하지 않는다.

2026-10-30 소유자 결정(벤치마크 카드 3번): Responses 응답 객체에는 context
window가 없다. 그래서 값이 없거나 읽을 수 없으면 `not_reported`로 남기고
중단하지 않는다. 응답이 1,000,000이 아닌 값을 보고하면 여전히 중단한다.

모델은 요청 배포 `gpt-5.6-sol`과 정확히 같아야 한다. Fast·날짜 별칭도
조용히 같은 것으로 취급하지 않는다. effort는 `max`, context는 1,000,000을
요구한다. 불일치, 필수 필드 누락, 저장 실패, 호출 간 필드 변화는 고정 사유로
중단한다. 이미 공급자가 실행한 첫 요청의 비용을 취소한다는 뜻은 아니다.
CLI의 도구/텍스트 효과와 후속 요청을 막는 장치다. 실패 receipt는 남기되
그 뒤의 파일럿 과제·재시도·완료 승인은 차단한다.

## 기존 증빙과 상한 보존

원본 run 39407062120 / artifact 12257312458의 `/3` 결과는 바꾸지 않았다.
그 결과의 `connected`, SDK 보고 입력 9444토큰 / 출력 5토큰, `served_model=null`, app-server
258400은 그대로 역사적 기록이다. 원문 응답·served version·Max/1M의 새
증빙으로 재해석하지 않는다. 이번에는 모델·스모크·5문제·채점을 실행하지 않았다.

새 `..._source_20261027_response_capture.yaml`은 10-27 connection 등록의
소스 전용 후속본이다. 기존 등록은 그대로이며 비소스 plan 값도 같다.
58개 source pin 중 runner·wire·preflight만 갱신한다. 새 캡처 모듈의 실제
import 경로, 진단 스크립트, artifact workflow도 검토한 Git blob과 함께
시작/최종 검사에 묶는다. 소스 거부 조건은 완화하지 않는다.

풀이+채점 합계 USD 200, 요청 수 32/128/640, 시도당 1,800초, 기존 토큰
사전검사와 SQLite 장부는 유지한다. `token_hard_limit_enforced=false`도
그대로다. 가격표·기존 caps·봉인된 채점기 hash는 바꾸지 않는다.

## 막힘 10개: 이전 handoff의 ③ 이후 분류 포함

① 승인된 계정·배포·호스트 결속은 이전 작업에서 닫힌 상태를 유지한다.
아래 번호는 기존 11개 요구사항의 번호다. ②·③만 수집 준비 상태가 달라졌고,
실제 증빙은 아직 없다. 나머지는 기존 조건을 유지한다.

| # | 기존 막힘 | 이번 작업 뒤 상태·남은 조건 |
| --- | --- | --- |
| ② | `foundry_served_model_version_unverified` | 다음 호출에서 원문과 model/version 필드 수집 가능. 실제 응답·버전 증빙 필요. |
| ③ | `max_and_long_1m_capability_unverified` | 다음 호출에서 응답 effort/context 수집 가능. 공급자가 보고하지 않으면 차단; 실제 적용·능력은 미검증. |
| ④ | `native_call_and_token_limits_unresolved` | 유지. 기존 클라이언트 제한 외에 서버 하드 토큰·usage 계약은 공급자 증빙 필요. |
| ⑤ | `prepared_input_bytes_unverified` | 유지. 승인된 입력과 상위 증빙 묶음이 준비되면 무료 로컬 결속 가능. |
| ⑥ | `live_inference_identity_and_wire_unverified` | 유지. 실제 파일럿 세션의 증빙 필요; 가짜 응답과 옛 연결 진단으로 대체 불가. |
| ⑦ | `pilot_dispatch_and_grading_identity_not_wired` | 유지. frozen grader source 불일치에 대한 소유자 검토 필요. 자동 재봉인 없음. |
| ⑧ | `foundry_usage_and_tariff_mapping_unverified` | 유지. 적용 tier·cache-write·청구량 연결은 공급자/소유자 증빙 필요. |
| ⑨ | `native_sandbox_and_result_bundle_host_unverified` | 유지. 실제 소유 세션의 workspace·결과 보관 증빙 필요. |
| ⑩ | `actual_pilot_deployment_not_prepared` | 유지. 상위 묶음 뒤 무료 로컬 config/deployment 준비 가능. Azure 배포 생성 허가는 아님. |
| ⑪ | `prepared_request_capture_unverified` | 유지. 입력/config/deployment 묶음 뒤 무료 prepared-request 캡처 가능. 이번 응답 캡처와 별개다. |

금액 결정은 USD 200으로 끝났다. 남은 소유자 항목은 채점기 소스 변경 검토와
병합 후 실행 소스·환경 승인이다. 실제 응답/능력/호스트 증빙은 별도 승인된
실행이 필요하다. 이번 작업은 유료 재개·push·PR·dispatch·병합 권한을 추가하지 않는다.

## 검증 기록

검증 HEAD는 `7b2cd13d6ae23a7f65f4f481636976da436a1e42`다.
한 명령에서 **618 통과 / 실패 0 / 오류 0 / 건너뜀 0**, exit 0을 확인했다.
pytest 표시 시간은 **700.09초**, JUnit은 **700.079초**, 외부 타이머는
**700.676초**다. 명령은 `bash /tmp/p5-native-response.tz5Zd7/run-related.sh final-validated`.
스크립트에 대상·`env -i`·오프라인 변수·1,800초+정리 5초 한도가 기록되어 있다.
이 합산은 기존 관련 379개 선택, 연결 진단/워크플로 188개, 새 응답 테스트
47개, 새 세션 차단 테스트 4개를 **같은 실행에서** 확인한 결과다.

가짜 JSON/SSE와 가짜 SDK/Python 자식 프로세스만 사용했다. 실제 모델 성능,
공급자 응답 형식, 청구 금액, 전체 프로젝트/실환경 통합을 검증한 결과가 아니다.
이전 379개 증빙과 이번의 예비 실행들을 위 합산에 더하지 않는다.
수정 전 617개 통과 뒤 별도 저장 지연 검사에서 실패를 재현했으며,
잠금 대기를 제거한 뒤 47개 응답 테스트와 최종 618개를 각각 다시 확인했다.
예비 단계의 환경 누락·추가 artifact 경로·변경된 함수 인자·현재 grader hash
기대값 문제는 검증 환경/기대값을 명시적으로 고쳤다. assertion을 완화하지 않았다.
실행 코드는 저장 지연이 SDK 종료를 막는 실제 결함을 추가로 고쳤다.

새 소스 등록의 파일 SHA256은
`768adaed42d65233986447810dd5a8646306b3e44f42bf7feb2037042b9c1446`이다.
해당 HEAD의 plan-only 프리플라이트는 **exit 2 / 3.151초**,
`source_verified → inspect_plan`, configuration valid, launch false였다.
막힘은 **해제 0 / 유지 10 / 신규 0**이며 수집 준비 표시는 ②·③에만 붙었다.
문서만 추가한 최종 HEAD에서도 같은 120초+정리 5초 명령으로 재확인한다.

현재 grader 전체 source hash는
`f64b9c394f04766ed3bb544a7e9cb963b7bf5d0885ace1f19bf5bc3563fc4bd5`다.
그 계산은 모든 `core/*.py`를 포함하므로 runner 변경도 반영된다.
봉인된 `47effd1db4c1de5ff7cf0473a034ece7748312e682597fb06ee480678e000fcf`
와의 불일치 거부는 유지하며 자동 재봉인하지 않았다.

증거는 `/tmp/p5-native-response.tz5Zd7/`의 `final-validated.log`,
`final-validated.junit.xml`, `final-validated.timing.txt`, `validated-preflight.json`,
`run-related.sh`, `HANDOFF.md`에 있다. 결과 보고에는 수집 준비와 실제 관측을
구분하는 사실/조건 대조를 적용했다. 원본 진단과 이전 handoff는 수정하지 않았다.

## 변경 파일 15개

- `batch-runner/gpt56_native_response_capture.py`
- `batch-runner/gpt56_pilot_wire_receipt.py`
- `batch-runner/core/codex_runner.py`
- `batch-runner/scripts/diagnose_codex_foundry_connection.py`
- `batch-runner/gpt56_sol_codex_pilot_preflight.py`
- `.github/workflows/codex-foundry-connection-diagnostic.yml`
- `batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot_source_20261027_response_capture.yaml`
- `batch-runner/tests/test_gpt56_native_response_capture.py`
- `batch-runner/tests/test_gpt56_pilot_wire_receipt.py`
- `batch-runner/tests/test_gpt56_pilot_provider_observation.py`
- `batch-runner/tests/test_codex_foundry_connection_probe.py`
- `batch-runner/tests/test_sol_source_registration.py`
- `batch-runner/docs/gpt56_native_response_capture.md`
- `tasks/LATEST_TASK_RESULT/README.md`
- `CHANGELOG.md`
