"""Model-free tests for the opt-in typed Azure AI Step 2 wiring."""

import copy
import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import core.code_interpreter as code_interpreter
import core.video_analyzer as video_analyzer
import step2_run_inference as step2
from core.azure_ai_clients import (
    DIRECT_TOKEN_SCOPE,
    AzureAIWorkload,
    ClassifiedEndpoint,
    EndpointKind,
    RouteProfile,
    RouteSelection,
)
from core.cost_metering import (
    ROUTE_IDENTITY_ATTRIBUTE,
    RouteCallIdentity,
    api_version_of,
    deployment_of,
    route_identity_of,
)
from core.executor import TaskExecutor as CoreTaskExecutor
from core.result_fingerprint import (
    inference_result_fingerprint,
    validate_inference_result_fingerprint,
)


_SENSITIVE_QA_DETAIL = (
    "https://private-account.invalid/openai/v1/ "
    "account=private deployment=leaked-only"
)


def _route(
    workload="inference",
    fingerprint="a" * 64,
    *,
    endpoint_kind="direct-v1",
    profile="direct-v1",
):
    return {
        "endpoint_kind": endpoint_kind,
        "profile": profile,
        "runtime_fingerprint": fingerprint,
        "workload": workload,
    }


def _planned_fingerprint(workload, deployment):
    return hashlib.sha256(
        f"{AzureAIWorkload(workload).value}:{deployment.strip()}".encode()
    ).hexdigest()


def _unmetered(client):
    """Look through the cost-metering wrapper at the client it stands for.

    Step 2 hands out every provider client already wrapped, so that each call
    records what it cost. The wrapper forwards everything and changes nothing
    about *which* client is *which* — which is what the assertions below are
    for. So they check the wrapper is present, then look through it, and the
    routing claim they always made is unchanged.
    """
    assert getattr(client, "_is_cost_metered", False), (
        "Step 2 must hand out metered clients"
    )
    return client.inner


def _checkpoint_success(task_id="task-1"):
    return {
        "task_id": task_id,
        "status": "success",
        "content": "done",
        "deliverable_text": "done",
        "deliverable_files": [],
        "model": "main-model",
        "usage": None,
        "observability": {},
        "latency_ms": 1.0,
        "timestamp": "2026-07-23T00:00:00+00:00",
    }


def _runtime_route(
    workload=AzureAIWorkload.INFERENCE,
    *,
    endpoint_kind=EndpointKind.DIRECT_V1,
    profile=RouteProfile.DIRECT_V1,
):
    return RouteSelection(
        profile=RouteProfile(profile),
        workload=AzureAIWorkload(workload),
        endpoint=ClassifiedEndpoint(
            kind=EndpointKind(endpoint_kind),
            url="https://runtime.invalid/",
            account="runtime",
        ),
        token_scope=DIRECT_TOKEN_SCOPE,
    )


class _Manifest:
    def require_schema(self, version):
        assert version == 4

    def __contains__(self, task_id):
        return task_id == "task-1"

    def reference_records(self, task_id, reference_files):
        return []

    def needs_files(self, task_id):
        return False

    def source_projection_sha256(self, task_id):
        return "source-projection"

    def __str__(self):
        return "test-manifest"


class _Resource:
    def __init__(self, name, events, close_error=None):
        self.name = name
        self.events = events
        self.close_error = close_error
        self.close_calls = 0

    def close(self):
        self.close_calls += 1
        self.events.append(f"close:{self.name}")
        if self.close_error is not None:
            raise self.close_error


class _Managed(_Resource):
    def __init__(
        self,
        name,
        events,
        fingerprint=None,
        route=None,
    ):
        super().__init__(name, events)
        self.runtime_fingerprint = fingerprint or hashlib.sha256(
            name.encode("utf-8")
        ).hexdigest()
        self.route = route or _runtime_route()


class _Executor(_Resource):
    def __init__(self, events, kwargs):
        super().__init__("executor", events)
        self.kwargs = kwargs
        self.execute_calls = []

    def execute(self, **kwargs):
        self.execute_calls.append(kwargs)
        return {
            "success": True,
            "text": "done",
            "deliverable_text": "done",
            "files": [],
        }


class _Factory(_Resource):
    def __init__(self, events, settings):
        super().__init__("factory", events)
        self.settings = settings


def _write_prepared(
    workspace: Path,
    *,
    provider="azure",
    mode="subprocess",
    preprocessors=None,
    hardened=False,
    qa_enabled=False,
    qa_model=None,
    main_deployment="main-model",
):
    sandbox = {"hardened_substrate": True} if hardened else {}
    prepared = {
        "experiment_id": "exp-test",
        "experiment_name": "Typed wiring",
        "source": "owner/repository",
        "publication_generation": "exp-test:local:test",
        "execution": {
            "mode": mode,
            "max_retries": 0,
            "resume_max_rounds": 0,
            "sandbox": sandbox,
        },
        "condition_a": {
            "name": "Baseline",
            "model": {"provider": provider, "deployment": main_deployment},
            "prompt": {"system": "system"},
            "preprocessors": preprocessors or [],
            "qa": {
                "enabled": qa_enabled,
                "prompt": "Inspect {instruction}" if qa_enabled else "",
                **({"model": qa_model} if qa_model is not None else {}),
            },
        },
        "condition_b": None,
        "tasks": [{
            "task_id": "task-1",
            "instruction": "Create the result",
            "sector": "sector",
            "occupation": "occupation",
            "reference_files": [],
            "reference_file_records": [],
            "needs_files": False,
            "source_projection_sha256": "source-projection",
        }],
    }
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "step1_tasks_prepared.json").write_text(
        json.dumps(prepared),
        encoding="utf-8",
    )


def _patch_run(monkeypatch, tmp_path, **prepared_kwargs):
    workspace = tmp_path / "workspace"
    upload = tmp_path / "upload"
    _write_prepared(workspace, **prepared_kwargs)
    monkeypatch.setattr(step2, "WORKSPACE_DIR", workspace)
    monkeypatch.setattr(step2, "UPLOAD_DIR", upload)
    monkeypatch.setattr(step2.NeedsFilesManifest, "load", lambda: _Manifest())
    monkeypatch.setattr(step2, "validate_prepared_fingerprint", lambda data: "p" * 64)
    monkeypatch.setattr(
        step2,
        "validate_publication_generation",
        lambda value: value,
    )
    monkeypatch.setattr(
        step2,
        "resolve_verified_reference_paths",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        step2,
        "bind_deliverable_file_records",
        lambda results, root: results,
    )
    return workspace


def _enable_typed(monkeypatch, events, routes=None, profile="direct-v1"):
    settings = object()
    monkeypatch.setenv("AZURE_AI_ROUTE_PROFILE", profile)

    class _Settings:
        @classmethod
        def from_env(cls):
            events.append("preflight:settings")
            return settings

    def _workloads(condition, execution_mode):
        events.append("preflight:workloads")
        model = condition["model"]
        azure_main = model["provider"] in {"azure", "azure_openai"}
        workloads = []
        if azure_main:
            main_deployment = model["deployment"].strip()
            workloads.append((AzureAIWorkload.INFERENCE, main_deployment))
            qa = condition.get("qa", {})
            if qa.get("enabled") is True:
                qa_deployment = qa.get("model") or main_deployment
                workloads.append((
                    AzureAIWorkload.INFERENCE,
                    qa_deployment.strip(),
                ))
        for preprocessor in condition.get("preprocessors", []):
            model = preprocessor.get("model", {})
            if model.get("provider", "azure") in {"azure", "azure_openai"}:
                workloads.append((
                    AzureAIWorkload.INFERENCE,
                    model.get("deployment", "probe-model"),
                ))
        if execution_mode == "code_interpreter":
            workloads.append((AzureAIWorkload.CODE_INTERPRETER, main_deployment))
        return workloads

    def _preflight(workloads, *, settings):
        events.append("preflight:routes")
        if routes is not None:
            return copy.deepcopy(routes)
        output = []
        seen = set()
        for workload, deployment in workloads:
            identity = (workload.value, deployment)
            if identity in seen:
                continue
            seen.add(identity)
            endpoint_kind = (
                "project"
                if workload is AzureAIWorkload.CODE_INTERPRETER
                else "direct-v1"
            )
            output.append(_route(
                workload.value,
                _planned_fingerprint(workload, deployment),
                endpoint_kind=endpoint_kind,
                profile=profile,
            ))
        return output

    monkeypatch.setattr(step2, "AzureAIRouteSettings", _Settings)
    monkeypatch.setattr(step2, "inference_route_workloads", _workloads)
    monkeypatch.setattr(step2, "preflight_routes", _preflight)
    return settings


def _install_runtime_fakes(monkeypatch, events, managed_overrides=None):
    created = {"managed": [], "executors": [], "factories": []}
    managed_overrides = managed_overrides or []

    def _factory(*, settings):
        events.append("create:factory")
        factory = _Factory(events, settings)
        created["factories"].append(factory)
        return factory

    def _typed(workload, deployment, *, factory):
        events.append(f"create:{workload.value}:{deployment}")
        override = (
            managed_overrides[len(created["managed"])]
            if len(created["managed"]) < len(managed_overrides)
            else {}
        )
        profile = RouteProfile(os.environ["AZURE_AI_ROUTE_PROFILE"])
        endpoint_kind = (
            EndpointKind.PROJECT
            if workload is AzureAIWorkload.CODE_INTERPRETER
            else EndpointKind.DIRECT_V1
        )
        managed = _Managed(
            f"{workload.value}:{deployment}",
            events,
            fingerprint=override.get(
                "fingerprint",
                _planned_fingerprint(workload, deployment),
            ),
            route=override.get(
                "route",
                _runtime_route(
                    workload,
                    endpoint_kind=endpoint_kind,
                    profile=profile,
                ),
            ),
        )
        managed.factory = factory
        created["managed"].append(managed)
        return managed

    def _executor(**kwargs):
        events.append("create:executor")
        executor = _Executor(events, kwargs)
        created["executors"].append(executor)
        return executor

    monkeypatch.setattr(step2, "AzureAIClientFactory", _factory)
    monkeypatch.setattr(step2, "create_typed_azure_client", _typed)
    monkeypatch.setattr(step2, "TaskExecutor", _executor)
    return created


def _run(resume=False, mode=None, wall_timeout=None):
    return step2.run_inference(
        execution_mode=mode,
        max_retries=0,
        resume=resume,
        resume_max_rounds=0,
        wall_timeout=wall_timeout,
    )


def _run_that_produced_nothing(**kwargs):
    """Run Step 2 over a task that leaves no deliverable, and take the exit.

    A run where not one task wrote deliverable text or a deliverable file now
    stops at Step 2 with code 1, rather than handing Step 4 a parquet it
    cannot fill. The guard is the last thing the run does, so every artifact
    these tests then read has already been written.
    """
    with pytest.raises(SystemExit) as exit_info:
        _run(**kwargs)
    assert exit_info.value.code == 1


def _write_valid_typed_checkpoint(path):
    routes = [_route(
        fingerprint=_planned_fingerprint("inference", "main-model")
    )]
    step2._save_progress(
        "exp-test",
        "Baseline",
        "subprocess",
        1,
        [_checkpoint_success()],
        "2026-07-23T00:00:00+00:00",
        path,
        run_id="exp-test:local:1",
        condition_identity="condition_a",
        ordered_task_ids=["task-1"],
        prepared_fingerprint="p" * 64,
        azure_ai_routes=routes,
    )


def test_redacted_main_client_delegates_nested_calls_and_drops_raw_exception():
    sensitive = (
        "https://private-account.invalid/openai/v1/ "
        "account=private deployment=leaked-only"
    )
    response = object()

    class _Completions:
        def create(self, *, fail):
            if fail:
                raise RuntimeError(sensitive)
            return response

    raw = SimpleNamespace(
        chat=SimpleNamespace(completions=_Completions()),
        route="verified-route",
        runtime_fingerprint="f" * 64,
    )
    client = step2._RedactedAzureAIClient(raw)

    assert client.chat.completions.create(fail=False) is response
    assert client.route == "verified-route"
    assert client.runtime_fingerprint == "f" * 64
    with pytest.raises(RuntimeError) as caught:
        client.chat.completions.create(fail=True)

    assert str(caught.value) == "Typed Azure AI provider error (RuntimeError)"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert sensitive not in repr(caught.value)


def test_redacted_main_client_hands_its_route_declaration_over_whole():
    declaration = RouteCallIdentity(
        model_argument_names_deployment=True, api_version="v1"
    )
    raw = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: None)),
        route="verified-route",
        runtime_fingerprint="f" * 64,
    )
    setattr(raw, ROUTE_IDENTITY_ATTRIBUTE, declaration)

    client = step2._RedactedAzureAIClient(raw)

    # This boundary re-wraps every attribute it hands out, so that a provider
    # exception raised deeper in cannot escape with an endpoint inside it.
    # Re-wrapping this one would give the cost meter a proxy where it expects a
    # declaration, and inference on the v1 route would go back to recording no
    # deployment and no API version — the very state the boundary is standing
    # in front of. What passes through is a routing rule and the name of an API
    # contract: no endpoint, no account, no credential.
    assert route_identity_of(client) is declaration
    assert deployment_of(client, "gold-judge") == "gold-judge"
    assert api_version_of(client) == "v1"
    # Everything else still goes through the boundary.
    assert isinstance(client.chat, step2._RedactedAzureAICallProxy)


def test_redacted_main_client_without_a_declaration_answers_unknown_not_error():
    # The undeclared case has to stay quiet rather than raise: the boundary
    # turns every missing attribute into a RuntimeError, and metering only
    # watches a call — it never gets a vote on whether the call happens.
    client = step2._RedactedAzureAIClient(SimpleNamespace(chat=SimpleNamespace()))

    assert route_identity_of(client) is None
    assert deployment_of(client, "gold-judge") is None
    assert api_version_of(client) is None


def test_redacted_main_client_drops_nested_attribute_exception():
    sensitive = "account=private deployment=leaked-only"

    class _Chat:
        @property
        def completions(self):
            raise RuntimeError(sensitive)

    client = step2._RedactedAzureAIClient(SimpleNamespace(chat=_Chat()))

    with pytest.raises(RuntimeError) as caught:
        _ = client.chat.completions

    assert str(caught.value) == "Typed Azure AI provider error (RuntimeError)"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert sensitive not in repr(caught.value)


def test_profile_absent_keeps_legacy_client_and_output_shape(monkeypatch, tmp_path):
    workspace = _patch_run(monkeypatch, tmp_path)
    monkeypatch.delenv("AZURE_AI_ROUTE_PROFILE", raising=False)
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://legacy.invalid/")
    raw_client = object()
    provider_calls = []
    events = []
    monkeypatch.setattr(
        step2,
        "create_provider_client",
        lambda provider, **kwargs: provider_calls.append((provider, kwargs)) or raw_client,
    )
    created = _install_runtime_fakes(monkeypatch, events)
    monkeypatch.setattr(
        step2,
        "AzureAIClientFactory",
        lambda **kwargs: pytest.fail("typed factory must not be created"),
    )

    _run()

    output = json.loads(
        (workspace / "step2_inference_results_condition_a.json").read_text()
    )
    assert provider_calls == [(
        "azure",
        {"endpoint": "https://legacy.invalid/"},
    )]
    assert _unmetered(created["executors"][0].kwargs["llm_client"]) is raw_client
    assert "redact_provider_errors" not in created["executors"][0].kwargs
    assert "azure_ai_routes" not in output
    assert "azure_ai_routes" not in json.loads(
        (workspace / "step2_inference_progress_condition_a.json").read_text()
    )
    assert events[-1] == "close:executor"


def test_typed_preflight_precedes_factory_and_client(monkeypatch, tmp_path):
    _patch_run(monkeypatch, tmp_path)
    events = []
    _enable_typed(monkeypatch, events)
    _install_runtime_fakes(monkeypatch, events)
    monkeypatch.setattr(
        step2,
        "create_provider_client",
        lambda *args, **kwargs: pytest.fail("legacy client must not be created"),
    )

    _run()

    assert events[:5] == [
        "preflight:workloads",
        "preflight:settings",
        "preflight:routes",
        "create:factory",
        "create:inference:main-model",
    ]


@pytest.mark.parametrize(
    "boundary",
    ["settings", "endpoint"],
)
def test_typed_invalid_route_configuration_rejects_before_runtime(
    boundary, monkeypatch, tmp_path, capsys
):
    _patch_run(monkeypatch, tmp_path)
    monkeypatch.setenv("AZURE_AI_ROUTE_PROFILE", "direct-v1")
    events = []

    def _workloads(condition, execution_mode):
        events.append("planner")
        return [(AzureAIWorkload.INFERENCE, "main-model")]

    class _Settings:
        @classmethod
        def from_env(cls):
            events.append("settings")
            if boundary == "settings":
                raise ValueError("sensitive route settings")
            return object()

    def _preflight(workloads, *, settings):
        events.append("preflight")
        raise ValueError("sensitive endpoint configuration")

    monkeypatch.setattr(step2, "inference_route_workloads", _workloads)
    monkeypatch.setattr(step2, "AzureAIRouteSettings", _Settings)
    monkeypatch.setattr(step2, "preflight_routes", _preflight)
    for symbol in (
        "AzureAIClientFactory",
        "create_provider_client",
        "create_typed_azure_client",
        "TaskExecutor",
    ):
        monkeypatch.setattr(
            step2,
            symbol,
            lambda *args, _symbol=symbol, **kwargs: pytest.fail(
                f"{_symbol} must not be called"
            ),
        )

    with pytest.raises(SystemExit) as caught:
        _run()

    assert caught.value.code == 1
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert capsys.readouterr().out == (
        "❌ typed Azure AI route preflight failed (ValueError)\n"
    )
    assert events == (
        ["planner", "settings"]
        if boundary == "settings"
        else ["planner", "settings", "preflight"]
    )


def test_typed_agentic_invalid_experiment_rejects_before_planning(
    monkeypatch, tmp_path, capsys
):
    mode = "agentic_sandbox"
    _patch_run(monkeypatch, tmp_path, mode=mode)
    events = []
    _enable_typed(monkeypatch, events)
    _install_runtime_fakes(monkeypatch, events)

    with pytest.raises(SystemExit):
        _run(mode=mode)

    output = capsys.readouterr().out
    assert "failed to reload hardened execution config" in output
    assert "experiment ID must be exp028 or exp030" in output
    assert events == []

def test_typed_resume_false_starts_fresh_with_stale_checkpoints(
    monkeypatch, tmp_path
):
    workspace = _patch_run(monkeypatch, tmp_path)
    for name in (
        "step2_inference_progress_condition_a.json",
        "step2_inference_progress.json",
    ):
        (workspace / name).write_text("stale", encoding="utf-8")
    events = []
    _enable_typed(monkeypatch, events)
    _install_runtime_fakes(monkeypatch, events)

    _run(resume=False)

    output = json.loads(
        (workspace / "step2_inference_results_condition_a.json").read_text()
    )
    assert output["azure_ai_routes"]


def test_unsupported_provider_rejects_before_planning_or_runtime(
    monkeypatch, tmp_path, capsys
):
    _patch_run(monkeypatch, tmp_path, provider="unsupported-provider")
    monkeypatch.setenv("AZURE_AI_ROUTE_PROFILE", "direct-v1")

    class _ForbiddenSettings:
        @classmethod
        def from_env(cls):
            pytest.fail("settings must not be read")

    monkeypatch.setattr(step2, "AzureAIRouteSettings", _ForbiddenSettings)
    for symbol in (
        "inference_route_workloads",
        "AzureAIClientFactory",
        "create_provider_client",
        "create_typed_azure_client",
        "TaskExecutor",
    ):
        monkeypatch.setattr(
            step2,
            symbol,
            lambda *args, _symbol=symbol, **kwargs: pytest.fail(
                f"{_symbol} must not be called"
            ),
        )

    with pytest.raises(SystemExit):
        _run()

    assert capsys.readouterr().out == (
        "❌ Unsupported provider: 'unsupported-provider'. Use: "
        "azure, azure_openai, openai, anthropic\n"
    )


def test_requested_profile_with_native_only_workload_uses_no_typed_resources(
    monkeypatch, tmp_path
):
    workspace = _patch_run(monkeypatch, tmp_path, provider="openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    events = []
    _enable_typed(monkeypatch, events)
    created = _install_runtime_fakes(monkeypatch, events)
    native = object()
    provider_calls = []
    monkeypatch.setattr(
        step2,
        "create_provider_client",
        lambda provider, **kwargs: provider_calls.append(provider) or native,
    )

    _run()

    output = json.loads(
        (workspace / "step2_inference_results_condition_a.json").read_text()
    )
    progress = json.loads(
        (workspace / "step2_inference_progress_condition_a.json").read_text()
    )
    assert provider_calls == ["openai"]
    assert created["managed"] == []
    assert created["factories"] == []
    assert _unmetered(created["executors"][0].kwargs["llm_client"]) is native
    assert events == [
        "preflight:workloads",
        "create:executor",
        "close:executor",
    ]
    assert "azure_ai_routes" not in output
    assert "azure_ai_routes" not in progress


@pytest.mark.parametrize("mode", ["subprocess", "code_interpreter"])
def test_typed_clients_share_factory_and_reach_exact_executor_slots(
    mode, monkeypatch, tmp_path
):
    _patch_run(monkeypatch, tmp_path, mode=mode)
    events = []
    settings = _enable_typed(
        monkeypatch,
        events,
        profile="project-ci" if mode == "code_interpreter" else "direct-v1",
    )
    created = _install_runtime_fakes(monkeypatch, events)
    monkeypatch.setattr(
        step2,
        "create_provider_client",
        lambda *args, **kwargs: pytest.fail("legacy client must not be created"),
    )

    _run(mode=mode)

    executor = created["executors"][0]
    main = created["managed"][0]
    assert created["factories"][0].settings is settings
    main_proxy = _unmetered(executor.kwargs["llm_client"])
    assert isinstance(main_proxy, step2._RedactedAzureAIClient)
    assert main_proxy._target is main
    assert all(
        managed.factory is created["factories"][0]
        for managed in created["managed"]
    )
    if mode == "code_interpreter":
        assert executor.kwargs["redact_provider_errors"] is True
        ci_client = created["managed"][1]
        assert _unmetered(executor.kwargs["code_interpreter_client"]) is ci_client
        assert [event for event in events if event.startswith("close:")] == [
            "close:executor",
            "close:code-interpreter:main-model",
            "close:inference:main-model",
            "close:factory",
        ]
    else:
        assert "redact_provider_errors" not in executor.kwargs
        assert executor.kwargs["code_interpreter_client"] is None
        assert [event for event in events if event.startswith("close:")] == [
            "close:executor",
            "close:inference:main-model",
            "close:factory",
        ]


@pytest.mark.parametrize("profile", [None, "direct-v1", "legacy-rollback"])
def test_code_interpreter_requires_project_profile_before_clients(
    profile, monkeypatch, tmp_path, capsys
):
    _patch_run(monkeypatch, tmp_path, mode="code_interpreter")
    if profile is None:
        monkeypatch.delenv("AZURE_AI_ROUTE_PROFILE", raising=False)
    else:
        monkeypatch.setenv("AZURE_AI_ROUTE_PROFILE", profile)
    factory = MagicMock()
    provider_client = MagicMock()
    typed_client = MagicMock()
    executor = MagicMock()
    monkeypatch.setattr(step2, "AzureAIClientFactory", factory)
    monkeypatch.setattr(step2, "create_provider_client", provider_client)
    monkeypatch.setattr(step2, "create_typed_azure_client", typed_client)
    monkeypatch.setattr(step2, "TaskExecutor", executor)

    with pytest.raises(SystemExit):
        _run(mode="code_interpreter")

    assert "requires the project-ci route profile" in capsys.readouterr().out
    factory.assert_not_called()
    provider_client.assert_not_called()
    typed_client.assert_not_called()
    executor.assert_not_called()


def test_planned_runtime_fingerprint_mismatch_fails_before_use_and_cleans_up(
    monkeypatch, tmp_path, capsys
):
    _patch_run(monkeypatch, tmp_path)
    events = []
    _enable_typed(monkeypatch, events)
    created = _install_runtime_fakes(
        monkeypatch,
        events,
        managed_overrides=[{"fingerprint": "f" * 64}],
    )

    with pytest.raises(SystemExit):
        _run()

    assert "❌ typed Azure AI inference client init failed (ValueError)" in (
        capsys.readouterr().out
    )
    assert "create:executor" not in events
    assert created["managed"][0].close_calls == 1
    assert created["factories"][0].close_calls == 1
    assert [event for event in events if event.startswith("close:")] == [
        "close:inference:main-model",
        "close:factory",
    ]


@pytest.mark.parametrize(
    "runtime_route",
    [
        _runtime_route(
            endpoint_kind=EndpointKind.LEGACY_DATED,
            profile=RouteProfile.LEGACY_ROLLBACK,
        ),
        _runtime_route(profile=RouteProfile.PROJECT_CI),
        _runtime_route(workload=AzureAIWorkload.NARRATIVE),
    ],
    ids=["route", "profile", "workload"],
)
def test_runtime_route_profile_or_workload_mismatch_fails_before_use_and_cleans_up(
    runtime_route, monkeypatch, tmp_path
):
    _patch_run(monkeypatch, tmp_path)
    events = []
    _enable_typed(monkeypatch, events)
    created = _install_runtime_fakes(
        monkeypatch,
        events,
        managed_overrides=[{"route": runtime_route}],
    )

    with pytest.raises(SystemExit):
        _run()

    assert "create:executor" not in events
    assert created["managed"][0].close_calls == 1
    assert created["factories"][0].close_calls == 1


def test_typed_self_qa_uses_distinct_verified_wrapper_and_closes_in_order(
    monkeypatch, tmp_path
):
    _patch_run(monkeypatch, tmp_path, qa_enabled=True)
    events = []
    _enable_typed(monkeypatch, events, profile="project-ci")
    created = _install_runtime_fakes(monkeypatch, events)
    qa_clients = []

    def _self_qa(*args, **kwargs):
        qa_clients.append(args[4])
        return {
            "passed": True,
            "score": 10,
            "issues": [],
            "suggestion": "",
            "undetermined": False,
        }

    monkeypatch.setattr(step2, "_run_self_qa", _self_qa)

    _run()

    main_client, qa_client = created["managed"]
    assert qa_client is not main_client
    main_proxy = _unmetered(created["executors"][0].kwargs["llm_client"])
    assert isinstance(main_proxy, step2._RedactedAzureAIClient)
    assert main_proxy._target is main_client
    assert [_unmetered(seen) for seen in qa_clients] == [qa_client]
    assert main_client.runtime_fingerprint == qa_client.runtime_fingerprint
    assert [event for event in events if event.startswith("close:")] == [
        "close:executor",
        "close:inference:main-model",
        "close:inference:main-model",
        "close:factory",
    ]


def test_executor_init_failure_exits_and_closes_typed_resources(
    monkeypatch, tmp_path, capsys
):
    _patch_run(monkeypatch, tmp_path)
    events = []
    _enable_typed(monkeypatch, events, profile="project-ci")
    created = _install_runtime_fakes(monkeypatch, events)
    sensitive_detail = "private-executor-detail"
    monkeypatch.setattr(
        step2,
        "TaskExecutor",
        lambda **kwargs: (_ for _ in ()).throw(
            RuntimeError(sensitive_detail)
        ),
    )

    with pytest.raises(SystemExit):
        _run()

    output = capsys.readouterr().out
    assert "❌ typed Azure AI executor init failed (RuntimeError)" in output
    assert sensitive_detail not in output
    assert created["managed"][0].close_calls == 1
    assert created["factories"][0].close_calls == 1
    assert [event for event in events if event.startswith("close:")] == [
        "close:inference:main-model",
        "close:factory",
    ]


@pytest.mark.parametrize(
    ("phase", "mode", "qa_enabled", "expected"),
    [
        (
            "factory",
            "subprocess",
            False,
            "❌ typed Azure AI client factory init failed (RuntimeError)",
        ),
        (
            "main",
            "subprocess",
            False,
            "❌ typed Azure AI inference client init failed (RuntimeError)",
        ),
        (
            "qa",
            "subprocess",
            True,
            "❌ typed Azure AI Self-QA client init failed (RuntimeError)",
        ),
        (
            "code-interpreter",
            "code_interpreter",
            False,
            "❌ typed Azure AI Code Interpreter client init failed (RuntimeError)",
        ),
        (
            "executor",
            "subprocess",
            False,
            "❌ typed Azure AI executor init failed (RuntimeError)",
        ),
    ],
)
def test_typed_init_errors_hide_sensitive_endpoint_and_identity_text(
    phase, mode, qa_enabled, expected, monkeypatch, tmp_path, capsys
):
    _patch_run(
        monkeypatch,
        tmp_path,
        mode=mode,
        qa_enabled=qa_enabled,
    )
    events = []
    _enable_typed(
        monkeypatch,
        events,
        profile="project-ci" if mode == "code_interpreter" else "direct-v1",
    )
    _install_runtime_fakes(monkeypatch, events)
    sensitive_endpoint = "https://private-account.invalid/openai/v1/"
    sensitive_identity = "private-identity-value"
    sensitive_detail = f"{sensitive_endpoint} {sensitive_identity}"

    def _raise_sensitive(*args, **kwargs):
        raise RuntimeError(sensitive_detail)

    if phase == "factory":
        monkeypatch.setattr(step2, "AzureAIClientFactory", _raise_sensitive)
    elif phase == "main":
        monkeypatch.setattr(step2, "create_typed_azure_client", _raise_sensitive)
    elif phase in {"qa", "code-interpreter"}:
        original_create = step2.create_typed_azure_client
        calls = 0

        def _fail_second_client(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError(sensitive_detail)
            return original_create(*args, **kwargs)

        monkeypatch.setattr(
            step2,
            "create_typed_azure_client",
            _fail_second_client,
        )
    else:
        monkeypatch.setattr(step2, "TaskExecutor", _raise_sensitive)

    with pytest.raises(SystemExit) as caught:
        _run(mode=mode)

    assert caught.value.code == 1
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    output = capsys.readouterr().out
    assert expected in output
    assert sensitive_detail not in output
    assert sensitive_endpoint not in output
    assert sensitive_identity not in output


def test_legacy_executor_init_error_preserves_full_detail(
    monkeypatch, tmp_path, capsys
):
    _patch_run(monkeypatch, tmp_path)
    monkeypatch.delenv("AZURE_AI_ROUTE_PROFILE", raising=False)
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://legacy.invalid/")
    monkeypatch.setattr(
        step2,
        "create_provider_client",
        lambda *args, **kwargs: object(),
    )
    detail = "legacy executor initialization detail"
    monkeypatch.setattr(
        step2,
        "TaskExecutor",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError(detail)),
    )

    with pytest.raises(SystemExit):
        _run()

    assert (
        f"❌ Executor init failed for mode 'subprocess': {detail}"
        in capsys.readouterr().out
    )


def test_native_main_with_azure_preprocessor_executor_init_error_preserves_detail(
    monkeypatch, tmp_path, capsys
):
    _patch_run(
        monkeypatch,
        tmp_path,
        provider="openai",
        preprocessors=[{
            "type": "audio_analyzer",
            "model": {"provider": "azure", "deployment": "probe-model"},
        }],
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    events = []
    _enable_typed(monkeypatch, events)
    created = _install_runtime_fakes(monkeypatch, events)
    native_client = object()
    provider_calls = []
    monkeypatch.setattr(
        step2,
        "create_provider_client",
        lambda provider, **kwargs: provider_calls.append(provider) or native_client,
    )
    detail = "native executor initialization detail"

    def _fail_executor(**kwargs):
        events.append("create:executor")
        assert _unmetered(kwargs["llm_client"]) is native_client
        raise RuntimeError(detail)

    monkeypatch.setattr(step2, "TaskExecutor", _fail_executor)
    monkeypatch.setattr(
        step2,
        "complete",
        lambda *args, **kwargs: pytest.fail("model API must not be called"),
    )
    monkeypatch.setattr(
        step2,
        "analyze_audio_files",
        lambda **kwargs: pytest.fail("preprocessor API must not be called"),
    )

    with pytest.raises(SystemExit) as caught:
        _run()

    stdout = capsys.readouterr().out
    assert caught.value.code == 1
    assert f"❌ Executor init failed for mode 'subprocess': {detail}" in stdout
    assert "typed Azure AI executor init failed" not in stdout
    assert provider_calls == ["openai"]
    assert created["managed"] == []
    assert created["factories"][0].close_calls == 1
    assert [event for event in events if event.startswith("close:")] == [
        "close:factory",
    ]


@pytest.mark.parametrize("body_error", [RuntimeError("body"), SystemExit(7)])
def test_runtime_resources_close_on_error_and_system_exit(body_error):
    events = []
    resources = step2._Step2RuntimeResources()
    executor = _Resource("executor", events)
    first = _Resource("first", events)
    second = _Resource("second", events)
    factory = _Resource("factory", events)

    with pytest.raises(type(body_error)) as caught:
        with resources:
            resources.own_executor(executor)
            resources.own_client(first)
            resources.own_client(second)
            resources.own_factory(factory)
            raise body_error

    assert caught.value is body_error
    if isinstance(body_error, SystemExit):
        assert caught.value.code == 7
    resources.close()
    assert events == [
        "close:executor",
        "close:second",
        "close:first",
        "close:factory",
    ]


def test_cleanup_first_error_is_primary_and_all_distinct_resources_attempted():
    events = []
    executor_error = RuntimeError("executor cleanup")
    body_error = ValueError("body")
    resources = step2._Step2RuntimeResources()
    executor = _Resource("executor", events, executor_error)
    shared = _Resource("shared", events, OSError("shared cleanup"))
    factory = _Resource("factory", events, LookupError("factory cleanup"))

    with pytest.raises(RuntimeError, match="executor cleanup") as caught:
        with resources:
            resources.own_executor(executor)
            resources.own_client(shared)
            resources.own_client(shared)
            resources.own_factory(factory)
            raise body_error

    assert caught.value is executor_error
    assert caught.value.__cause__ is body_error
    assert events == ["close:executor", "close:shared", "close:factory"]


@pytest.mark.parametrize(
    ("failing_role", "expected_message"),
    [
        (
            "managed client",
            "typed Azure AI managed client cleanup failed (OSError)",
        ),
        (
            "factory",
            "typed Azure AI factory cleanup failed (LookupError)",
        ),
    ],
)
def test_typed_cleanup_errors_are_class_only_and_all_resources_are_attempted(
    failing_role, expected_message, capsys
):
    events = []
    sensitive_parts = (
        "https://private-account.invalid/openai/v1/",
        "account=private",
        "deployment=leaked-only",
    )
    sensitive = " ".join(sensitive_parts)
    raw_error = (
        OSError(sensitive)
        if failing_role == "managed client"
        else LookupError(sensitive)
    )
    resources = step2._Step2RuntimeResources()
    executor = _Resource("executor", events)
    first = _Resource("first", events)
    second = _Resource(
        "second",
        events,
        raw_error if failing_role == "managed client" else None,
    )
    factory = _Resource(
        "factory",
        events,
        raw_error if failing_role == "factory" else None,
    )
    resources.own_executor(executor)
    resources.own_client(first)
    resources.own_client(second)
    resources.own_factory(factory)

    with pytest.raises(RuntimeError) as caught:
        resources.close()

    resources.close()
    captured = capsys.readouterr()
    assert str(caught.value) == expected_message
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert raw_error.__traceback__ is not None
    traceback = caught.value.__traceback__
    while traceback is not None:
        assert traceback.tb_frame.f_locals.get("self") not in {
            second,
            factory,
        }
        traceback = traceback.tb_next
    for sensitive_part in sensitive_parts:
        assert sensitive_part not in str(caught.value)
        assert sensitive_part not in repr(caught.value)
        assert sensitive_part not in captured.out + captured.err
    assert events == [
        "close:executor",
        "close:second",
        "close:first",
        "close:factory",
    ]


def test_sanitized_typed_cleanup_is_primary_with_body_as_explicit_cause(
    capsys,
):
    events = []
    sensitive_parts = (
        "https://private-account.invalid/openai/v1/",
        "account=private",
        "deployment=leaked-only",
    )
    raw_error = OSError(" ".join(sensitive_parts))
    body_error = ValueError("local body detail")
    resources = step2._Step2RuntimeResources()

    with pytest.raises(RuntimeError) as caught:
        with resources:
            resources.own_executor(_Resource("executor", events))
            resources.own_client(
                _Resource("managed", events, raw_error)
            )
            resources.own_factory(_Resource("factory", events))
            raise body_error

    resources.close()
    captured = capsys.readouterr()
    assert str(caught.value) == (
        "typed Azure AI managed client cleanup failed (OSError)"
    )
    assert caught.value.__cause__ is body_error
    assert caught.value.__context__ is body_error
    assert caught.value is not raw_error
    assert caught.value.__cause__ is not raw_error
    assert caught.value.__context__ is not raw_error
    for sensitive_part in sensitive_parts:
        assert sensitive_part not in str(caught.value)
        assert sensitive_part not in repr(caught.value)
        assert sensitive_part not in str(caught.value.__cause__)
        assert sensitive_part not in str(caught.value.__context__)
        assert sensitive_part not in captured.out + captured.err
    assert events == [
        "close:executor",
        "close:managed",
        "close:factory",
    ]


@pytest.mark.parametrize("pp_type", ["audio_analyzer", "video_analyzer"])
@pytest.mark.parametrize("analyzer_error", [False, True])
def test_typed_preprocessor_closes_wrapper_and_records_fingerprint(
    pp_type, analyzer_error, monkeypatch
):
    events = []
    managed = _Managed("preprocessor", events, "b" * 64)
    factory = object()
    path = "/private/a.wav" if pp_type == "audio_analyzer" else "/private/a.mp4"
    filter_name = (
        "filter_audio_files"
        if pp_type == "audio_analyzer"
        else "filter_video_files"
    )
    analyzer_name = (
        "analyze_audio_files"
        if pp_type == "audio_analyzer"
        else "analyze_video_files"
    )
    monkeypatch.setattr(step2, filter_name, lambda files: [path])
    monkeypatch.setattr(
        step2,
        "create_typed_azure_client",
        lambda workload, deployment, *, factory: managed,
    )

    def _analyze(**kwargs):
        if analyzer_error:
            raise RuntimeError("private analyzer detail")
        return "analysis"

    monkeypatch.setattr(step2, analyzer_name, _analyze)
    observations = []
    output = step2._run_preprocessors(
        {
            "preprocessors": [{
                "type": pp_type,
                "model": {"provider": "azure", "deployment": "probe"},
            }],
        },
        [path],
        "task",
        observations,
        azure_ai_factory=factory,
        azure_ai_route_plan=step2._build_azure_ai_route_plan(
            [(AzureAIWorkload.INFERENCE, "probe")],
            [_route(fingerprint="b" * 64)],
        ),
    )

    assert output == ("" if analyzer_error else "analysis")
    assert managed.close_calls == 1
    assert observations[0]["runtime_fingerprint"] == "b" * 64
    assert "endpoint" not in observations[0]


@pytest.mark.parametrize("pp_type", ["audio_analyzer", "video_analyzer"])
def test_typed_preprocessor_route_mismatch_skips_analyzer_and_closes_wrapper(
    pp_type, monkeypatch
):
    events = []
    managed = _Managed("preprocessor", events, "b" * 64)
    path = "/private/a.wav" if pp_type == "audio_analyzer" else "/private/a.mp4"
    filter_name = (
        "filter_audio_files"
        if pp_type == "audio_analyzer"
        else "filter_video_files"
    )
    analyzer_name = (
        "analyze_audio_files"
        if pp_type == "audio_analyzer"
        else "analyze_video_files"
    )
    analyzer_calls = []
    monkeypatch.setattr(step2, filter_name, lambda files: [path])
    monkeypatch.setattr(
        step2,
        "create_typed_azure_client",
        lambda workload, deployment, *, factory: managed,
    )
    monkeypatch.setattr(
        step2,
        analyzer_name,
        lambda **kwargs: analyzer_calls.append(kwargs) or "analysis",
    )
    observations = []

    output = step2._run_preprocessors(
        {
            "preprocessors": [{
                "type": pp_type,
                "model": {"provider": "azure", "deployment": "probe"},
            }],
        },
        [path],
        "task",
        observations,
        azure_ai_factory=object(),
        azure_ai_route_plan=step2._build_azure_ai_route_plan(
            [(AzureAIWorkload.INFERENCE, "probe")],
            [_route(fingerprint="a" * 64)],
        ),
    )

    assert output == ""
    assert analyzer_calls == []
    assert managed.close_calls == 1
    assert observations[0]["status"] == "error"
    assert "runtime_fingerprint" not in observations[0]


def test_native_preprocessor_stays_on_legacy_factory(monkeypatch):
    legacy = object()
    calls = []
    monkeypatch.setattr(step2, "filter_video_files", lambda files: ["/private/a.mp4"])
    monkeypatch.setattr(
        step2,
        "create_provider_client",
        lambda provider: calls.append(provider) or legacy,
    )
    monkeypatch.setattr(
        step2,
        "create_typed_azure_client",
        lambda *args, **kwargs: pytest.fail("native preprocessor must stay legacy"),
    )
    monkeypatch.setattr(step2, "analyze_video_files", lambda **kwargs: "analysis")
    observations = []

    output = step2._run_preprocessors(
        {
            "preprocessors": [{
                "type": "video_analyzer",
                "model": {"provider": "openai", "deployment": "probe"},
            }],
        },
        ["/private/a.mp4"],
        "task",
        observations,
        azure_ai_factory=object(),
    )

    assert output == "analysis"
    assert calls == ["openai"]
    assert "runtime_fingerprint" not in observations[0]


def test_native_main_with_azure_preprocessor_uses_both_paths(
    monkeypatch, tmp_path
):
    preprocessors = [{
        "type": "audio_analyzer",
        "model": {
            "provider": "azure_openai",
            "deployment": "  probe-model  ",
        },
    }]
    workspace = _patch_run(
        monkeypatch,
        tmp_path,
        provider="openai",
        main_deployment="  native-main  ",
        preprocessors=preprocessors,
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    events = []
    _enable_typed(monkeypatch, events)
    created = _install_runtime_fakes(monkeypatch, events)
    native = object()
    provider_calls = []
    monkeypatch.setattr(
        step2,
        "create_provider_client",
        lambda provider, **kwargs: provider_calls.append(provider) or native,
    )
    monkeypatch.setattr(step2, "filter_audio_files", lambda files: ["/private/a.wav"])
    monkeypatch.setattr(step2, "analyze_audio_files", lambda **kwargs: "analysis")

    _run()

    assert provider_calls == ["openai"]
    assert _unmetered(created["executors"][0].kwargs["llm_client"]) is native
    assert created["executors"][0].execute_calls[0]["model"] == "  native-main  "
    assert [client.name for client in created["managed"]] == [
        "inference:probe-model"
    ]
    assert created["managed"][0].close_calls == 1
    output = json.loads(
        (workspace / "step2_inference_results_condition_a.json").read_text()
    )
    assert output["model"] == "  native-main  "


def test_native_main_with_azure_preprocessor_preserves_local_failure_detail(
    monkeypatch, tmp_path
):
    preprocessors = [{
        "type": "audio_analyzer",
        "model": {"provider": "azure", "deployment": "probe-model"},
    }]
    workspace = _patch_run(
        monkeypatch,
        tmp_path,
        provider="openai",
        main_deployment="native-main",
        preprocessors=preprocessors,
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    events = []
    _enable_typed(monkeypatch, events)
    created = _install_runtime_fakes(monkeypatch, events)
    native = object()
    monkeypatch.setattr(
        step2,
        "create_provider_client",
        lambda provider, **kwargs: native,
    )
    monkeypatch.setattr(
        step2,
        "filter_audio_files",
        lambda files: ["/private/audio.wav"],
    )
    monkeypatch.setattr(step2, "analyze_audio_files", lambda **kwargs: "analysis")
    detail = "Code execution failed (exit code 23): local subprocess stderr"

    def _fail_locally(self, **kwargs):
        return {
            "success": False,
            "error": detail,
            "text": "local partial output",
            "deliverable_text": "local draft",
            "files": [],
        }

    monkeypatch.setattr(_Executor, "execute", _fail_locally)

    _run()

    progress = json.loads(
        (workspace / "step2_inference_progress_condition_a.json").read_text()
    )
    final = json.loads(
        (workspace / "step2_inference_results_condition_a.json").read_text()
    )
    assert _unmetered(created["executors"][0].kwargs["llm_client"]) is native
    assert "redact_provider_errors" not in created["executors"][0].kwargs
    expected = "task_execution_error:TaskExecutionError"
    assert progress["results"][0]["error"] == expected
    assert final["results"][0]["error"] == expected


def test_route_plan_preserves_exact_deduped_workload_order():
    workloads = [
        (AzureAIWorkload.INFERENCE, " main "),
        (AzureAIWorkload.INFERENCE, "main"),
        (AzureAIWorkload.CODE_INTERPRETER, " main "),
    ]
    routes = [
        _route(
            fingerprint="a" * 64,
            profile="project-ci",
        ),
        _route(
            workload="code-interpreter",
            fingerprint="b" * 64,
            endpoint_kind="project",
            profile="project-ci",
        ),
    ]

    plan = step2._build_azure_ai_route_plan(workloads, routes)

    assert [(workload.value, deployment) for workload, deployment, _ in plan] == [
        ("inference", "main"),
        ("code-interpreter", "main"),
    ]
    assert [record for _, _, record in plan] == routes


@pytest.mark.parametrize(
    ("profile", "endpoint_kind"),
    [("direct-v1", "direct-v1"), ("legacy-rollback", "legacy-dated")],
)
def test_validate_route_records_rejects_non_project_code_interpreter(
    profile, endpoint_kind
):
    route = _route(
        workload="code-interpreter",
        profile=profile,
        endpoint_kind=endpoint_kind,
    )

    with pytest.raises(ValueError, match="workload are incompatible"):
        step2._validate_azure_ai_routes([route], typed_enabled=True)


def test_canonical_planned_deployment_requires_one_exact_planned_identity():
    route = _route()
    plan = [(AzureAIWorkload.INFERENCE, "canonical", route)]

    assert step2._canonical_planned_deployment(
        AzureAIWorkload.INFERENCE,
        "  canonical  ",
        plan,
    ) == "canonical"
    with pytest.raises(ValueError, match="absent or ambiguous"):
        step2._canonical_planned_deployment(
            AzureAIWorkload.INFERENCE,
            "missing",
            plan,
        )
    with pytest.raises(ValueError, match="absent or ambiguous"):
        step2._canonical_planned_deployment(
            AzureAIWorkload.INFERENCE,
            "canonical",
            [*plan, *plan],
        )


def test_typed_whitespace_deployments_use_exact_canonical_runtime_strings(
    monkeypatch, tmp_path
):
    preprocessors = [
        {
            "type": "audio_analyzer",
            "model": {
                "provider": "azure",
                "deployment": "  audio-model  ",
            },
        },
        {
            "type": "video_analyzer",
            "model": {
                "provider": "azure_openai",
                "deployment": "  video-model  ",
            },
        },
    ]
    workspace = _patch_run(
        monkeypatch,
        tmp_path,
        main_deployment="  main-model  ",
        qa_enabled=True,
        qa_model="  qa-model  ",
        preprocessors=preprocessors,
    )
    events = []
    _enable_typed(monkeypatch, events)
    created = _install_runtime_fakes(monkeypatch, events)
    verify_calls = []
    original_verify = step2._verify_managed_azure_ai_client

    def _verify(client, workload, deployment, route_plan):
        verify_calls.append((AzureAIWorkload(workload).value, deployment))
        return original_verify(client, workload, deployment, route_plan)

    monkeypatch.setattr(step2, "_verify_managed_azure_ai_client", _verify)
    monkeypatch.setattr(
        step2,
        "filter_audio_files",
        lambda paths: ["/private/audio.wav"],
    )
    monkeypatch.setattr(
        step2,
        "filter_video_files",
        lambda paths: ["/private/video.mp4"],
    )
    analyzer_calls = []
    monkeypatch.setattr(
        step2,
        "analyze_audio_files",
        lambda **kwargs: analyzer_calls.append((
            "audio",
            kwargs["model_deployment"],
            kwargs["redact_provider_errors"],
        )) or "audio analysis",
    )
    monkeypatch.setattr(
        step2,
        "analyze_video_files",
        lambda **kwargs: analyzer_calls.append((
            "video",
            kwargs["model_deployment"],
            kwargs["redact_provider_errors"],
        )) or "video analysis",
    )
    qa_calls = []

    def _complete(client, model, messages, **kwargs):
        qa_calls.append((_unmetered(client), model, kwargs))
        return (
            SimpleNamespace(
                choices=[SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content=json.dumps({
                        "passed": True,
                        "score": 10,
                        "issues": [],
                        "suggestion": "",
                    })),
                )],
            ),
            1.0,
        )

    monkeypatch.setattr(step2, "complete", _complete)

    _run()

    output = json.loads(
        (workspace / "step2_inference_results_condition_a.json").read_text()
    )
    prepared = json.loads(
        (workspace / "step1_tasks_prepared.json").read_text()
    )
    assert prepared["condition_a"]["model"]["deployment"] == "  main-model  "
    assert prepared["condition_a"]["qa"]["model"] == "  qa-model  "
    # Model fields remain schema-compatibility metadata. Only azure_ai_routes
    # carries typed route provenance, and those records omit deployments.
    assert output["model"] == "main-model"
    assert output["results"][0]["model"] == "main-model"
    assert [
        observation["model"]
        for observation in output["results"][0]["observability"]["preprocessors"]
    ] == ["audio-model", "video-model"]
    assert all(set(route) == step2._AZURE_AI_ROUTE_KEYS for route in output[
        "azure_ai_routes"
    ])
    assert [route["runtime_fingerprint"] for route in output["azure_ai_routes"]] == [
        _planned_fingerprint("inference", "main-model"),
        _planned_fingerprint("inference", "qa-model"),
        _planned_fingerprint("inference", "audio-model"),
        _planned_fingerprint("inference", "video-model"),
    ]
    assert [managed.name for managed in created["managed"]] == [
        "inference:main-model",
        "inference:qa-model",
        "inference:audio-model",
        "inference:video-model",
    ]
    assert verify_calls == [
        ("inference", "main-model"),
        ("inference", "qa-model"),
        ("inference", "audio-model"),
        ("inference", "video-model"),
    ]
    assert created["executors"][0].execute_calls[0]["model"] == "main-model"
    assert analyzer_calls == [
        ("audio", "audio-model", True),
        ("video", "video-model", True),
    ]
    assert qa_calls == [(
        created["managed"][1],
        "qa-model",
        {"temperature": 0, "max_completion_tokens": 4096},
    )]
    assert "redact_provider_errors" not in created["executors"][0].kwargs


def test_typed_qa_provider_error_is_absent_from_stdout_progress_and_final(
    monkeypatch, tmp_path, capsys
):
    workspace = _patch_run(
        monkeypatch,
        tmp_path,
        qa_enabled=True,
        qa_model="qa-model",
    )
    events = []
    _enable_typed(monkeypatch, events)
    _install_runtime_fakes(monkeypatch, events)
    sensitive = (
        "https://private-account.invalid/openai/v1/ "
        "account=private deployment=leaked-only"
    )
    monkeypatch.setattr(
        step2,
        "complete",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError(sensitive)),
    )

    _run()

    stdout = capsys.readouterr().out
    progress = (
        workspace / "step2_inference_progress_condition_a.json"
    ).read_text()
    final = (
        workspace / "step2_inference_results_condition_a.json"
    ).read_text()
    assert sensitive not in stdout + progress + final
    assert "QA API call failed (RuntimeError)" in stdout
    assert "QA API error (RuntimeError)" in progress
    assert "QA API error (RuntimeError)" in final


def test_typed_malformed_qa_response_is_redacted_without_raw_response(
    monkeypatch, tmp_path, capsys
):
    workspace = _patch_run(
        monkeypatch,
        tmp_path,
        qa_enabled=True,
        qa_model="qa-model",
    )
    events = []
    _enable_typed(monkeypatch, events)
    _install_runtime_fakes(monkeypatch, events)
    sensitive = (
        "https://private-account.invalid/openai/v1/ "
        "account=private deployment=leaked-only"
    )
    monkeypatch.setattr(
        step2,
        "complete",
        lambda *args, **kwargs: (
            SimpleNamespace(choices=[SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content=sensitive),
            )]),
            1.0,
        ),
    )

    _run()

    stdout = capsys.readouterr().out
    progress_text = (
        workspace / "step2_inference_progress_condition_a.json"
    ).read_text()
    final_text = (
        workspace / "step2_inference_results_condition_a.json"
    ).read_text()
    assert sensitive not in stdout + progress_text + final_text
    assert "QA JSON parse failed (JSONDecodeError)" in stdout
    for document in (json.loads(progress_text), json.loads(final_text)):
        qa = document["results"][0]["qa"]
        assert qa["issues"] == ["QA JSON parse failed (JSONDecodeError)"]
        assert "raw_response" not in qa


def test_typed_qa_rejects_legacy_regex_fallback_payload(monkeypatch, capsys):
    payload = (
        '"passed": true, "score": 8, '
        f'"issues": ["{_SENSITIVE_QA_DETAIL}"]'
    )
    monkeypatch.setattr(
        step2,
        "complete",
        lambda *args, **kwargs: (
            SimpleNamespace(choices=[SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content=payload),
            )]),
            1.0,
        ),
    )

    result = step2._run_self_qa(
        {"instruction": "task"},
        {
            "model": {"deployment": "qa-model"},
            "qa": {"enabled": True, "prompt": "Inspect {instruction}"},
        },
        "deliverable",
        [],
        object(),
        redact_provider_errors=True,
    )

    stdout = capsys.readouterr().out
    assert _SENSITIVE_QA_DETAIL not in stdout
    assert _SENSITIVE_QA_DETAIL not in json.dumps(result)
    assert stdout == "  ⚠️  QA JSON parse failed (JSONDecodeError)\n"
    assert result == {
        "passed": None,
        "score": None,
        "issues": ["QA JSON parse failed (JSONDecodeError)"],
        "suggestion": "",
        "undetermined": True,
    }


def test_typed_qa_rejects_duplicate_json_members(monkeypatch, capsys):
    payload = (
        '{"passed":false,"score":1,"score":10,'
        f'"issues":["{_SENSITIVE_QA_DETAIL}"],"suggestion":""}}'
    )
    monkeypatch.setattr(
        step2,
        "complete",
        lambda *args, **kwargs: (
            SimpleNamespace(choices=[SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content=payload),
            )]),
            1.0,
        ),
    )

    result = step2._run_self_qa(
        {"instruction": "task"},
        {
            "model": {"deployment": "qa-model"},
            "qa": {"enabled": True, "prompt": "Inspect {instruction}"},
        },
        "deliverable",
        [],
        object(),
        redact_provider_errors=True,
    )

    stdout = capsys.readouterr().out
    assert _SENSITIVE_QA_DETAIL not in stdout
    assert _SENSITIVE_QA_DETAIL not in json.dumps(result)
    assert stdout == "  ⚠️  QA JSON parse failed (ValueError)\n"
    assert result == {
        "passed": None,
        "score": None,
        "issues": ["QA JSON parse failed (ValueError)"],
        "suggestion": "",
        "undetermined": True,
    }


@pytest.mark.parametrize(
    "payload",
    [
        [_SENSITIVE_QA_DETAIL],
        {
            "score": 8,
            "issues": [_SENSITIVE_QA_DETAIL],
            "suggestion": _SENSITIVE_QA_DETAIL,
        },
        {
            "passed": True,
            "score": 8,
            "issues": [_SENSITIVE_QA_DETAIL],
            "suggestion": _SENSITIVE_QA_DETAIL,
            "extra": _SENSITIVE_QA_DETAIL,
        },
        {
            "passed": 1,
            "score": 8,
            "issues": [_SENSITIVE_QA_DETAIL],
            "suggestion": _SENSITIVE_QA_DETAIL,
        },
        {
            "passed": True,
            "score": True,
            "issues": [_SENSITIVE_QA_DETAIL],
            "suggestion": _SENSITIVE_QA_DETAIL,
        },
        {
            "passed": True,
            "score": 8.5,
            "issues": [_SENSITIVE_QA_DETAIL],
            "suggestion": _SENSITIVE_QA_DETAIL,
        },
        {
            "passed": True,
            "score": 0,
            "issues": [_SENSITIVE_QA_DETAIL],
            "suggestion": _SENSITIVE_QA_DETAIL,
        },
        {
            "passed": True,
            "score": 11,
            "issues": [_SENSITIVE_QA_DETAIL],
            "suggestion": _SENSITIVE_QA_DETAIL,
        },
        {
            "passed": True,
            "score": 8,
            "issues": _SENSITIVE_QA_DETAIL,
            "suggestion": _SENSITIVE_QA_DETAIL,
        },
        {
            "passed": True,
            "score": 8,
            "issues": [_SENSITIVE_QA_DETAIL, "two", "three", "four"],
            "suggestion": _SENSITIVE_QA_DETAIL,
        },
        {
            "passed": True,
            "score": 8,
            "issues": [_SENSITIVE_QA_DETAIL, {"detail": _SENSITIVE_QA_DETAIL}],
            "suggestion": _SENSITIVE_QA_DETAIL,
        },
        {
            "passed": True,
            "score": 8,
            "issues": [_SENSITIVE_QA_DETAIL],
            "suggestion": [_SENSITIVE_QA_DETAIL],
        },
    ],
    ids=[
        "not-dict",
        "missing-key",
        "extra-key",
        "passed-not-bool",
        "score-bool",
        "score-not-int",
        "score-low",
        "score-high",
        "issues-not-list",
        "too-many-issues",
        "issue-not-string",
        "suggestion-not-string",
    ],
)
def test_typed_valid_json_with_invalid_qa_schema_is_safely_rejected(
    payload, monkeypatch, capsys
):
    monkeypatch.setattr(
        step2,
        "complete",
        lambda *args, **kwargs: (
            SimpleNamespace(choices=[SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content=json.dumps(payload)),
            )]),
            1.0,
        ),
    )

    result = step2._run_self_qa(
        {"instruction": "task"},
        {
            "model": {"deployment": "qa-model"},
            "qa": {"enabled": True, "prompt": "Inspect {instruction}"},
        },
        "deliverable",
        [],
        object(),
        redact_provider_errors=True,
    )

    stdout = capsys.readouterr().out
    assert _SENSITIVE_QA_DETAIL not in stdout
    assert _SENSITIVE_QA_DETAIL not in json.dumps(result)
    assert stdout == "  ⚠️  QA JSON parse failed (ValueError)\n"
    assert result == {
        "passed": None,
        "score": None,
        "issues": ["QA JSON parse failed (ValueError)"],
        "suggestion": "",
        "undetermined": True,
    }


def test_typed_valid_qa_schema_preserves_normal_values(monkeypatch, capsys):
    payload = {
        "passed": False,
        "score": 7,
        "issues": ["The title needs a date."],
        "suggestion": "Add the reporting date.",
    }
    monkeypatch.setattr(
        step2,
        "complete",
        lambda *args, **kwargs: (
            SimpleNamespace(choices=[SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content=json.dumps(payload)),
            )]),
            1.0,
        ),
    )

    result = step2._run_self_qa(
        {"instruction": "task"},
        {
            "model": {"deployment": "qa-model"},
            "qa": {
                "enabled": True,
                "prompt": "Inspect {instruction}",
                "min_score": 8,
            },
        },
        "deliverable",
        [],
        object(),
        redact_provider_errors=True,
    )

    assert capsys.readouterr().out == ""
    assert result == {
        "passed": False,
        "score": 7,
        "llm_passed": False,
        "issues": ["The title needs a date."],
        "suggestion": "Add the reporting date.",
        "undetermined": False,
    }


def test_legacy_structurally_loose_qa_json_keeps_existing_defaults(
    monkeypatch, capsys
):
    monkeypatch.setattr(
        step2,
        "complete",
        lambda *args, **kwargs: (
            SimpleNamespace(choices=[SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content='{"score": 7}'),
            )]),
            1.0,
        ),
    )

    result = step2._run_self_qa(
        {"instruction": "task"},
        {
            "model": {"deployment": "legacy-model"},
            "qa": {
                "enabled": True,
                "prompt": "Inspect {instruction}",
                "min_score": 8,
            },
        },
        "deliverable",
        [],
        object(),
    )

    assert capsys.readouterr().out == ""
    assert result == {
        "passed": False,
        "score": 7,
        "llm_passed": True,
        "issues": [],
        "suggestion": "",
        "undetermined": False,
    }


def test_legacy_malformed_qa_response_preserves_detailed_diagnostics(
    monkeypatch, capsys
):
    malformed = "legacy malformed response with deployment=legacy-detail"
    monkeypatch.setattr(
        step2,
        "complete",
        lambda *args, **kwargs: (
            SimpleNamespace(choices=[SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content=malformed),
            )]),
            1.0,
        ),
    )

    result = step2._run_self_qa(
        {"instruction": "task"},
        {
            "model": {"deployment": "legacy-model"},
            "qa": {"enabled": True, "prompt": "Inspect {instruction}"},
        },
        "deliverable",
        [],
        object(),
    )

    stdout = capsys.readouterr().out
    assert malformed in stdout
    assert malformed in result["issues"][0]
    assert result["raw_response"] == malformed


def test_typed_main_provider_error_is_redacted_by_client_proxy(
    monkeypatch, tmp_path, capsys
):
    workspace = _patch_run(monkeypatch, tmp_path, mode="json_renderer")
    events = []
    _enable_typed(monkeypatch, events)
    _install_runtime_fakes(monkeypatch, events)
    sensitive = (
        "https://private-account.invalid/openai/v1/ "
        "account=private deployment=leaked-only"
    )
    original_create = step2.create_typed_azure_client

    class _FailingCompletions:
        def create(self, **kwargs):
            raise RuntimeError(sensitive)

    def _typed_client(workload, deployment, *, factory):
        managed = original_create(workload, deployment, factory=factory)
        if workload is AzureAIWorkload.INFERENCE:
            managed.chat = SimpleNamespace(
                completions=_FailingCompletions()
            )
        return managed

    monkeypatch.setattr(step2, "create_typed_azure_client", _typed_client)
    monkeypatch.setattr(step2, "TaskExecutor", CoreTaskExecutor)

    _run_that_produced_nothing(mode="json_renderer")

    stdout = capsys.readouterr().out
    progress_text = (
        workspace / "step2_inference_progress_condition_a.json"
    ).read_text()
    final_text = (
        workspace / "step2_inference_results_condition_a.json"
    ).read_text()
    expected = "task_execution_error:RuntimeError"
    assert sensitive not in stdout + progress_text + final_text
    assert json.loads(progress_text)["results"][0]["error"] == expected
    assert json.loads(final_text)["results"][0]["error"] == expected


def test_typed_main_local_failure_preserves_result_fields_and_observability(
    monkeypatch, tmp_path
):
    workspace = _patch_run(monkeypatch, tmp_path)
    events = []
    _enable_typed(monkeypatch, events)
    _install_runtime_fakes(monkeypatch, events)
    detail = "Code execution failed (exit code 17): local parser detail"

    def _fail(self, **kwargs):
        return {
            "success": False,
            "error": detail,
            "text": "local partial output",
            "deliverable_text": "local draft",
            "files": [],
            "sandbox_manifest": {
                "schema_version": "test-v1",
                "sandbox_backend": "local_fallback",
                "attempts": [{
                    "status": "error",
                    "stdout": "local stdout",
                    "response": "local response",
                }],
                "final_status": "error",
            },
        }

    monkeypatch.setattr(_Executor, "execute", _fail)

    _run()

    progress = json.loads((
        workspace / "step2_inference_progress_condition_a.json"
    ).read_text())
    final = json.loads((
        workspace / "step2_inference_results_condition_a.json"
    ).read_text())
    for document in (progress, final):
        result = document["results"][0]
        assert result["error"] == "task_execution_error:TaskExecutionError"
        assert result["content"] == "local partial output"
        assert result["deliverable_text"] == "local draft"
        assert result["observability"]["sandbox"]["backend"] == "local_fallback"
        assert result["observability"]["sandbox"]["attempts"][0][
            "stdout"
        ] == "local stdout"
    assert result["deliverable_files"] == []


def test_typed_code_interpreter_response_error_uses_canonical_model_and_redacts(
    monkeypatch, tmp_path, capsys
):
    workspace = _patch_run(
        monkeypatch,
        tmp_path,
        mode="code_interpreter",
        main_deployment="  main-model  ",
    )
    events = []
    _enable_typed(monkeypatch, events, profile="project-ci")
    created = _install_runtime_fakes(monkeypatch, events)
    sensitive = (
        "https://private-account.invalid/openai/v1/ "
        "account=private deployment=leaked-only"
    )
    response_models = []
    original_create = step2.create_typed_azure_client

    def _typed_client(workload, deployment, *, factory):
        client = original_create(workload, deployment, factory=factory)
        if workload is AzureAIWorkload.CODE_INTERPRETER:
            def _response_create(**kwargs):
                response_models.append(kwargs["model"])
                raise RuntimeError(sensitive)

            client.responses = SimpleNamespace(create=_response_create)
            client.files = SimpleNamespace(
                create=lambda **kwargs: None,
                delete=lambda file_id: None,
                content=lambda file_id: b"",
            )
            client.containers = SimpleNamespace(
                create=lambda **kwargs: None,
                files=SimpleNamespace(
                    list=lambda container_id: SimpleNamespace(data=[]),
                    content=SimpleNamespace(
                        retrieve=lambda **kwargs: b"",
                    ),
                ),
            )
        return client

    monkeypatch.setattr(step2, "create_typed_azure_client", _typed_client)
    monkeypatch.setattr(step2, "TaskExecutor", CoreTaskExecutor)

    _run_that_produced_nothing(mode="code_interpreter")

    stdout = capsys.readouterr().out
    progress = (
        workspace / "step2_inference_progress_condition_a.json"
    ).read_text()
    final = (
        workspace / "step2_inference_results_condition_a.json"
    ).read_text()
    assert response_models == ["main-model"]
    assert sensitive not in stdout + progress + final
    assert "Code Interpreter provider error (RuntimeError)" in stdout
    assert json.loads(progress)["results"][0]["error"] == (
        "task_execution_error:RuntimeError"
    )
    assert created["managed"][1].close_calls == 1


def test_typed_code_interpreter_auxiliary_api_errors_never_escape_run_outputs(
    monkeypatch, tmp_path, capsys
):
    workspace = _patch_run(
        monkeypatch,
        tmp_path,
        mode="code_interpreter",
        main_deployment="  main-model  ",
    )
    reference_path = tmp_path / "reference.txt"
    reference_path.write_text("reference", encoding="utf-8")
    prepared_path = workspace / "step1_tasks_prepared.json"
    prepared = json.loads(prepared_path.read_text())
    prepared["tasks"][0]["reference_files"] = ["reference.txt"]
    prepared_path.write_text(json.dumps(prepared), encoding="utf-8")
    monkeypatch.setattr(
        step2,
        "resolve_verified_reference_paths",
        lambda *args, **kwargs: [str(reference_path)],
    )

    class _ReferenceStage:
        def __enter__(self):
            return [str(reference_path)]

        def __exit__(self, exc_type, exc, traceback):
            return None

    monkeypatch.setattr(
        step2,
        "stage_verified_references",
        lambda paths: _ReferenceStage(),
    )

    @contextmanager
    def _open_reference(path):
        with open(path, "rb") as stream:
            yield stream, None

    monkeypatch.setattr(
        code_interpreter,
        "open_verified_reference",
        _open_reference,
    )
    events = []
    _enable_typed(monkeypatch, events, profile="project-ci")
    _install_runtime_fakes(monkeypatch, events)
    sensitive = (
        "https://private-account.invalid/openai/v1/ "
        "account=private deployment=leaked-only"
    )
    response_models = []
    original_create = step2.create_typed_azure_client

    def _typed_client(workload, deployment, *, factory):
        client = original_create(workload, deployment, factory=factory)
        if workload is AzureAIWorkload.CODE_INTERPRETER:
            output = SimpleNamespace(
                type="image",
                file_id="output-file",
                filename="output.png",
            )

            def _response_create(**kwargs):
                response_models.append(kwargs["model"])
                return SimpleNamespace(
                    output=[SimpleNamespace(
                        type="code_interpreter_call",
                        container_id="container-1",
                        outputs=[output],
                    )],
                    output_text="done",
                    container_id=None,
                )

            def _raise_sensitive(*args, **kwargs):
                raise RuntimeError(sensitive)

            client.responses = SimpleNamespace(create=_response_create)
            client.files = SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(id="input-file"),
                delete=_raise_sensitive,
                content=_raise_sensitive,
            )
            client.containers = SimpleNamespace(
                create=lambda **kwargs: None,
                files=SimpleNamespace(
                    list=_raise_sensitive,
                    content=SimpleNamespace(retrieve=_raise_sensitive),
                ),
            )
        return client

    monkeypatch.setattr(step2, "create_typed_azure_client", _typed_client)
    monkeypatch.setattr(step2, "TaskExecutor", CoreTaskExecutor)

    _run(mode="code_interpreter")

    stdout = capsys.readouterr().out
    progress = (
        workspace / "step2_inference_progress_condition_a.json"
    ).read_text()
    final = (
        workspace / "step2_inference_results_condition_a.json"
    ).read_text()
    assert response_models == ["main-model"]
    assert sensitive not in stdout + progress + final
    assert "Container download failed (output-file)" in stdout
    assert "Files API download also failed (output-file) (RuntimeError)" in stdout
    assert "Container scan failed (container-1) (RuntimeError)" in stdout
    assert "Input file cleanup failed (input-file) (RuntimeError)" in stdout
    assert json.loads(progress)["results"][0]["status"] == "success"


def test_typed_audio_video_api_errors_are_absent_from_persisted_outputs(
    monkeypatch, tmp_path, capsys
):
    audio_path = tmp_path / "private.wav"
    video_path = tmp_path / "private.mp4"
    audio_path.write_bytes(b"audio")
    video_path.write_bytes(b"video")
    preprocessors = [
        {
            "type": "audio_analyzer",
            "model": {"provider": "azure", "deployment": "audio-model"},
        },
        {
            "type": "video_analyzer",
            "model": {"provider": "azure", "deployment": "video-model"},
        },
    ]
    workspace = _patch_run(
        monkeypatch,
        tmp_path,
        preprocessors=preprocessors,
    )
    events = []
    _enable_typed(monkeypatch, events)
    _install_runtime_fakes(monkeypatch, events)
    sensitive = (
        "https://private-account.invalid/openai/v1/ "
        "account=private deployment=leaked-only"
    )

    class _FailingCompletions:
        def create(self, **kwargs):
            raise RuntimeError(sensitive)

    original_create = step2.create_typed_azure_client

    def _typed_client(workload, deployment, *, factory):
        client = original_create(workload, deployment, factory=factory)
        if deployment in {"audio-model", "video-model"}:
            client.chat = SimpleNamespace(
                completions=_FailingCompletions()
            )
        return client

    monkeypatch.setattr(step2, "create_typed_azure_client", _typed_client)
    monkeypatch.setattr(
        step2,
        "filter_audio_files",
        lambda paths: [str(audio_path)],
    )
    monkeypatch.setattr(
        step2,
        "filter_video_files",
        lambda paths: [str(video_path)],
    )
    monkeypatch.setattr(video_analyzer, "_select_backend", lambda: "cv2")
    monkeypatch.setattr(
        video_analyzer,
        "extract_keyframes",
        lambda *args, **kwargs: (
            {
                "fps": 1.0,
                "frame_count": 1,
                "duration_sec": 1.0,
                "resolution": "1x1",
            },
            [(0.0, b"jpeg")],
        ),
    )

    _run()

    stdout = capsys.readouterr().out
    progress = (
        workspace / "step2_inference_progress_condition_a.json"
    ).read_text()
    final = (
        workspace / "step2_inference_results_condition_a.json"
    ).read_text()
    assert sensitive not in stdout + progress + final
    assert "Audio preprocessor API error (non-fatal) (RuntimeError)" in stdout
    assert "Video preprocessor API error (non-fatal) (RuntimeError)" in stdout


def test_legacy_audio_api_error_default_preserves_provider_detail(
    tmp_path, capsys
):
    audio_path = tmp_path / "legacy.wav"
    audio_path.write_bytes(b"audio")
    sensitive = "legacy provider API detail"

    class _FailingCompletions:
        def create(self, **kwargs):
            raise RuntimeError(sensitive)

    output = step2.analyze_audio_files(
        client=SimpleNamespace(
            chat=SimpleNamespace(completions=_FailingCompletions())
        ),
        model_deployment="legacy-model",
        system_prompt="system",
        audio_paths=[str(audio_path)],
    )

    assert output == ""
    assert sensitive in capsys.readouterr().out


@pytest.mark.parametrize(
    "routes",
    [
        [],
        [_route(), _route(workload="code-interpreter")],
        [_route(workload="code-interpreter")],
    ],
    ids=["short", "long", "wrong-order-workload"],
)
def test_route_plan_rejects_length_order_or_workload_disagreement(routes):
    with pytest.raises(ValueError):
        step2._build_azure_ai_route_plan(
            [(AzureAIWorkload.INFERENCE, "main")],
            routes,
        )


@pytest.mark.parametrize(
    "routes",
    [
        None,
        [],
        [_route() | {"endpoint": "https://private.invalid"}],
        [_route() | {"deployment": "private-model"}],
        [_route(fingerprint="A" * 64)],
        [_route(workload="unknown")],
        [{
            "endpoint_kind": "invalid",
            "profile": "direct-v1",
            "runtime_fingerprint": "a" * 64,
            "workload": "inference",
        }],
        [_route(), _route()],
    ],
)
def test_route_record_validation_rejects_malformed_raw_or_duplicate(routes):
    with pytest.raises(ValueError):
        step2._validate_azure_ai_routes(routes, typed_enabled=True)


@pytest.mark.parametrize(
    "route",
    [
        _route(endpoint_kind="project"),
        _route(endpoint_kind="legacy-dated"),
        _route(profile="legacy-rollback"),
        _route(profile="legacy-rollback", endpoint_kind="project"),
        _route(profile="project-ci", endpoint_kind="project"),
        _route(
            workload="code-interpreter",
            profile="project-ci",
            endpoint_kind="direct-v1",
        ),
        _route(
            workload="narrative",
            profile="project-ci",
            endpoint_kind="project",
        ),
    ],
)
def test_route_record_validation_rejects_impossible_profile_kind_matrix(route):
    with pytest.raises(ValueError, match="incompatible"):
        step2._validate_azure_ai_routes([route], typed_enabled=True)


def test_route_record_validation_allows_same_workload_with_distinct_fingerprints():
    routes = [_route(fingerprint="a" * 64), _route(fingerprint="b" * 64)]

    assert step2._validate_azure_ai_routes(routes, typed_enabled=True) == routes


def test_progress_routes_roundtrip_and_reject_mismatch_or_downgrade(tmp_path):
    path = tmp_path / "progress.json"
    routes = [_route()]
    identity = {
        "run_id": "run",
        "condition_identity": "condition_a",
        "ordered_task_ids": ["task-1"],
        "prepared_fingerprint": "p" * 64,
    }
    step2._save_progress(
        "exp-test",
        "Baseline",
        "subprocess",
        1,
        [_checkpoint_success()],
        "2026-07-23T00:00:00+00:00",
        path,
        azure_ai_routes=routes,
        **identity,
    )

    loaded = step2._load_and_validate_progress(
        path,
        experiment_id="exp-test",
        condition_name="Baseline",
        execution_mode="subprocess",
        azure_ai_routes=routes,
        **identity,
    )
    assert loaded["azure_ai_routes"] == routes

    with pytest.raises(ValueError, match="route mismatch"):
        step2._load_and_validate_progress(
            path,
            experiment_id="exp-test",
            condition_name="Baseline",
            execution_mode="subprocess",
            azure_ai_routes=[_route(fingerprint="b" * 64)],
            **identity,
        )
    with pytest.raises(ValueError, match="legacy progress"):
        step2._load_and_validate_progress(
            path,
            experiment_id="exp-test",
            condition_name="Baseline",
            execution_mode="subprocess",
            **identity,
        )

    path.write_text(json.dumps({
        key: value
        for key, value in loaded.items()
        if key != "azure_ai_routes"
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="missing Azure AI routes"):
        step2._load_and_validate_progress(
            path,
            experiment_id="exp-test",
            condition_name="Baseline",
            execution_mode="subprocess",
            azure_ai_routes=routes,
            **identity,
        )


def test_final_output_binds_routes_before_result_fingerprint(monkeypatch, tmp_path):
    workspace = _patch_run(monkeypatch, tmp_path)
    events = []
    _enable_typed(monkeypatch, events, routes=[_route(
        fingerprint=_planned_fingerprint("inference", "main-model")
    )])
    _install_runtime_fakes(monkeypatch, events)

    _run()

    output = json.loads(
        (workspace / "step2_inference_results_condition_a.json").read_text()
    )
    validate_inference_result_fingerprint(output)
    original = output["result_fingerprint"]
    changed = copy.deepcopy(output)
    changed["azure_ai_routes"][0]["runtime_fingerprint"] = "b" * 64
    changed["result_fingerprint"] = inference_result_fingerprint(changed)
    validate_inference_result_fingerprint(changed)
    assert changed["result_fingerprint"] != original