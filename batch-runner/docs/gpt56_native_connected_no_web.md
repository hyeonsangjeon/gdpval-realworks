# Native CONNECTED diagnostic: web-search-free request proof

## Observed failure

Actions run [40960964194](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/40960964194)
used main `98e677c2f40699b5c964d6428a05e2da4b2f59be`, Codex SDK/CLI
0.147.0, GitHub-hosted Ubuntu 24.04 image 20261026.354.1. Authentication,
thread creation and turn creation succeeded. The HTTP observer checked one
request, rejected it as `native_token_request_unverified`, and forwarded zero
requests upstream. Usage was null and every served-configuration field was
`not_reported`. Workflow success is not a CONNECTED verdict or a five-task run.
The separate cleanup failure made the top-level verdict `unclassified_failure`.
The $7.20 reference reservation is not a measured charge; reconciliation with
the combined USD 200 pilot ledger is still required before pilot progression.

## Bounded intervention

The default pinned request inventory includes remote `web_search`. The strict
token precheck accepts only locally visible text and function/custom tool
definitions. This is a demonstrated incompatibility, not proof that it was
the only cause of the live refusal: that run did not retain the request body.

[Official Codex configuration](https://developers.openai.com/codex/config-reference/)
documents `web_search = "disabled"` as removing that tool. Codex 0.147.0's
schema includes the same value. The runner now sets it only for the existing
Sol response-observed CONNECTED diagnostic. Conflicting explicit overrides
are refused. Default runtime and five-task pilot configuration are unchanged.
No input/output/request/time/USD ceiling, response-evidence requirement or
server-hard-limit claim changes. The parser still rejects remote tools,
opaque context, missing usage and unsupported output-limit contracts.

## Model-free check before another paid attempt

`tests/test_sol_native_loopback.py` requires explicit opt-in and actual hosted
runner admission. The pinned real SDK/CLI uses a fake auth command and a
loopback scripted Responses provider through the production HTTP observer.
Only auth source and the far end of HTTP are replaced; the request precheck,
response capture, deadline, cleanup and native startup run normally. The test
requires one admitted request, Sol/Max request fields, an inserted
`max_output_tokens=10000`, locally inspectable tools/text, a completed scripted
reply and durable synthetic response evidence. Missing settings do not pass.

`gpt56-native-runner-check.yml` runs this after its actual Ubuntu 24.04 sandbox
proof, with an empty inherited environment plus allowlisted runner metadata.
It has no secrets, Azure login or paid input. Its artifact is explicitly
`synthetic_model_free`: it cannot prove provider capability, served settings,
model quality, actual billing or five-task completion. NAS does not run it.

The source-only successor preserves every predecessor file, the frozen grader
seal and all non-source plan fields. GHCP's separate model-free workflow also
fetches full Git history so historical fixture commits are present on dispatch.
