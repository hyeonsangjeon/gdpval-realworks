"""Client requests survive the existing Codex config path without a live call."""

import ast
import sys
from pathlib import Path
from types import CodeType, ModuleType, SimpleNamespace

import pytest

from core import codex_runner
from core.codex_runtime_config import (
    DEFAULT_PROVIDER_ID,
    CodexProviderConfigurationError,
    CodexProviderSettings,
    requested_model_config_overrides,
)
from core.executor import TaskExecutor
from core.experiment_config import ExperimentConfig
from step1_prepare_tasks import _public_codex_config


ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://fixture.openai.azure.com/openai/v1/"
MODEL = "gpt-5.4"
# Literal pre-change output with only auth argv fixed for this offline test.
DEFAULT_OVERRIDE_BYTES = (
    b'model_providers.gdpval-foundry.name="gdpval-foundry"\n'
    b'model_providers.gdpval-foundry.base_url="https://fixture.openai.azure.com/openai/v1"\n'
    b'model_providers.gdpval-foundry.wire_api="responses"\n'
    b'model_providers.gdpval-foundry.auth.command="/fixture/python"\n'
    b'model_providers.gdpval-foundry.auth.args=["/fixture/token.py"]\n'
    b'model_providers.gdpval-foundry.auth.timeout_ms=30000\n'
    b'model_providers.gdpval-foundry.auth.refresh_interval_ms=1800000\n'
    b'model_providers.gdpval-foundry.request_max_retries=0\n'
    b'model_providers.gdpval-foundry.stream_max_retries=0'
)
QUERY_OVERRIDE_BYTES = (
    b'\n'
    b'model_providers.gdpval-foundry.query_params.alpha="one"\n'
    b'model_providers.gdpval-foundry.query_params.zeta="two"'
)


@pytest.fixture(scope="module")
def step2_codex_constructor() -> CodeType:
    """Evaluate only the real constructor expression, never the step-2 driver."""
    path = ROOT / "step2_run_inference.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "codex_settings"
            for target in node.targets
        )
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "CodexProviderSettings"
    ]
    assert len(calls) == 1
    return compile(ast.Expression(body=calls[0]), str(path), "eval")


@pytest.mark.parametrize(
    "controls,expected,error_field",
    [
        pytest.param({}, (), None, id="default-bytes"),
        pytest.param(
            {"reasoning_effort": None, "model_context_window": None},
            (), None, id="explicit-null-no-op",
        ),
        *[
            pytest.param(
                {"reasoning_effort": effort},
                (f'model_reasoning_effort="{effort}"',),
                None, id=f"effort-{effort}",
            )
            for effort in ("none", "minimal", "low", "medium", "high", "xhigh", "max")
        ],
        pytest.param(
            {"reasoning_effort": "max", "model_context_window": 1000000},
            ('model_reasoning_effort="max"', "model_context_window=1000000"),
            None, id="max-long-request",
        ),
        pytest.param(
            {"model_context_window": 1}, ("model_context_window=1",),
            None, id="context-only",
        ),
        pytest.param(
            {"model_context_window": (1 << 63) - 1},
            ("model_context_window=9223372036854775807",),
            None, id="context-int64-boundary",
        ),
        *[
            pytest.param(
                {"reasoning_effort": value}, (), "reasoning_effort",
                id=f"invalid-effort-{label}",
            )
            for label, value in (
                ("empty", ""), ("case", "Max"), ("space", " xhigh "),
                ("unknown", "ultra"), ("number", 1), ("bool", True),
                ("list", ["max"]),
            )
        ],
        *[
            pytest.param(
                {"model_context_window": value}, (), "model_context_window",
                id=f"invalid-context-{label}",
            )
            for label, value in (
                ("bool", True), ("zero", 0), ("negative", -1),
                ("whole-float", 1000000.0), ("fraction", 1.5),
                ("string", "1000000"), ("infinity", float("inf")),
                ("negative-infinity", float("-inf")), ("nan", float("nan")),
                ("overflow", 1 << 63), ("list", [1000000]),
            )
        ],
    ],
)
def test_codex_requested_model_controls(
    controls: dict[str, object],
    expected: tuple[str, ...],
    error_field: str | None,
    step2_codex_constructor: CodeType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Default bytes stay fixed; explicit/invalid requests survive every hop."""
    monkeypatch.setattr(
        CodexProviderSettings, "auth_command",
        lambda self: ["/fixture/python", "/fixture/token.py"],
    )
    query = {"zeta": "two", "alpha": "one"}
    block = {
        "endpoint_from_route": True, "model": MODEL,
        "query_params": query, **controls,
    }
    public = _public_codex_config({"endpoint": ENDPOINT, **block})
    assert "endpoint" not in public
    for key in ("reasoning_effort", "model_context_window"):
        assert (key in public) is (key in controls)
        if key in controls:
            assert public[key] is controls[key]

    config = ExperimentConfig.from_yaml(
        str(ROOT / "experiments/exp033_codex_foundry_fixed5.yaml")
    )
    for address in ({"endpoint": ENDPOINT}, {"endpoint_from_route": True}):
        config.execution.codex = {"model": MODEL, **address, **controls}
        errors = config.validate()
        if error_field:
            assert any(error_field in error for error in errors), errors
        else:
            assert errors == []

    def step2_settings() -> CodexProviderSettings:
        # Endpoint resolution is a local fixture. All other arguments are the
        # production constructor expression, so a cast or dropped key fails.
        return eval(step2_codex_constructor, {
            "CodexProviderSettings": CodexProviderSettings,
            "resolve_endpoint_setting": lambda *_: ENDPOINT,
            "codex_config": public, "os": SimpleNamespace(environ={}),
            "model": MODEL, "DEFAULT_PROVIDER_ID": DEFAULT_PROVIDER_ID,
        })

    real_runner = codex_runner.CodexAgentRunner
    constructed = []

    def fake_runner(provider: CodexProviderSettings, **_kwargs: object) -> SimpleNamespace:
        constructed.append(provider)
        return SimpleNamespace(provider=provider)

    monkeypatch.setattr(codex_runner, "CodexAgentRunner", fake_runner)

    def direct_executor() -> TaskExecutor:
        return TaskExecutor(
            mode="codex_foundry",
            codex_options={"endpoint": ENDPOINT, **public},
        )

    if error_field:
        for build in (
            lambda: requested_model_config_overrides(**controls),
            lambda: CodexProviderSettings(endpoint=ENDPOINT, model=MODEL, **controls),
            step2_settings, direct_executor,
        ):
            with pytest.raises(CodexProviderConfigurationError, match=error_field):
                build()
        assert constructed == []
        return

    assert requested_model_config_overrides(**controls) == expected
    settings = CodexProviderSettings(
        endpoint=ENDPOINT, model=MODEL, query_params=query, **controls
    )
    suffix = b"\n" + "\n".join(expected).encode("utf-8") if expected else b""
    plain = CodexProviderSettings(endpoint=ENDPOINT, model=MODEL, **controls)
    assert "\n".join(plain.config_overrides()).encode("utf-8") == (
        DEFAULT_OVERRIDE_BYTES + suffix
    )
    expected_bytes = DEFAULT_OVERRIDE_BYTES + QUERY_OVERRIDE_BYTES + suffix
    for actual in (settings, step2_settings(), direct_executor().runner.provider):
        assert actual.reasoning_effort == controls.get("reasoning_effort")
        assert actual.model_context_window == controls.get("model_context_window")
        assert "\n".join(actual.config_overrides()).encode("utf-8") == expected_bytes
    assert len(constructed) == 1

    class FakeCodex:
        def __init__(self, sdk_config: SimpleNamespace) -> None:
            self.config = sdk_config
            self.threads = []

        def thread_start(self, **kwargs: object) -> str:
            self.threads.append(kwargs)
            return "fixture-thread"

    # No real SDK import, process, auth, or turn. The existing open/start path
    # must carry the config tuple onto the same client that opens the thread.
    sdk = ModuleType("openai_codex")
    sdk.Codex = FakeCodex
    sdk.Sandbox = SimpleNamespace(workspace_write="workspace-write")
    sdk.ApprovalMode = SimpleNamespace(deny_all="deny-all")
    sdk_client = ModuleType("openai_codex.client")
    sdk_client.CodexConfig = SimpleNamespace
    monkeypatch.setitem(sys.modules, "openai_codex", sdk)
    monkeypatch.setitem(sys.modules, "openai_codex.client", sdk_client)
    runner = real_runner(settings, verify_runtime=False, preflight_auth=False)
    monkeypatch.setattr(runner, "_build_environment", lambda _: {})
    workspace = SimpleNamespace(workspace=tmp_path / "workspace")
    client = runner.open_runtime(workspace)
    assert client.config.config_overrides == settings.config_overrides()
    assert runner.start_thread(
        client, workspace, developer_instructions="fixture instructions"
    ) == "fixture-thread"
    assert client.threads == [{
        "model": MODEL, "model_provider": DEFAULT_PROVIDER_ID,
        "cwd": str(workspace.workspace), "sandbox": "workspace-write",
        "approval_mode": "deny-all", "developer_instructions": "fixture instructions",
    }]
