"""What the capacity read may claim, and what it must refuse to.

Two separate promises are pinned here, and the second matters more than the
first.

The first is that a number in this report came from Azure. The read exists
because exp034's refusals could not be attributed without a denominator, and a
denominator that was inferred rather than read would answer the question with
the assumption it was run to test. The sharpest of these tests is the one that
supplies a ``sku.capacity`` and no rate limits, and insists the tokens-per-minute
figure stays empty: the conversion is real, it is documented, and it is still not
in the payload, so it is not this tool's to make.

The second is that no identifier survives into the report. This runs against a
public repository, so a log naming the account or the resource group cannot be
unpublished. The tests check that from both directions -- that a real identifier
never survives, and that the guard enforcing it does not fire on a report which
never carried one.
"""

import importlib.util
import io
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

BATCH_RUNNER = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BATCH_RUNNER.parent
SCRIPT = BATCH_RUNNER / "scripts" / "azure_deployment_capacity.py"
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "azure-deployment-capacity.yml"

SPEC = importlib.util.spec_from_file_location("azure_deployment_capacity", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
capacity = importlib.util.module_from_spec(SPEC)
sys.modules["azure_deployment_capacity"] = capacity
SPEC.loader.exec_module(capacity)

from core.azure_control_plane import AzureReadFailure  # noqa: E402

# Values shaped like the real ones and belonging to nobody.
ACCOUNT = "contoso-foundry-eastus"
RESOURCE_GROUP = "rg-benchmark-inference"
SUBSCRIPTION = "11111111-2222-3333-4444-555555555555"
DEPLOYMENT = "gpt-5.4"

ENV = {
    "AZURE_AI_ROUTE_PROFILE": "direct-v1",
    "AZURE_OPENAI_V1_ENDPOINT": f"https://{ACCOUNT}.services.ai.azure.com/openai/v1/",
    "AZURE_SUBSCRIPTION_ID": SUBSCRIPTION,
}

MOMENT = datetime(2026, 9, 11, 6, 0, 0, tzinfo=timezone.utc)


def _clock(moment=MOMENT):
    return lambda: moment


def _deployment(
    *,
    name=DEPLOYMENT,
    sku_name="GlobalStandard",
    capacity_units=250,
    rate_limits=(
        {"key": "request", "renewalPeriod": 10, "count": 150},
        {"key": "token", "renewalPeriod": 60, "count": 250_000},
    ),
):
    entry = {
        "name": name,
        "sku": {},
        "properties": {"model": {"name": "gpt-5.4", "version": "2026-01-01"}},
    }
    if sku_name is not None:
        entry["sku"]["name"] = sku_name
    if capacity_units is not None:
        entry["sku"]["capacity"] = capacity_units
    if rate_limits is not None:
        entry["properties"]["rateLimits"] = list(rate_limits)
    return entry


def _runner(deployments=None, *, account_found=True):
    """A stand-in for az that answers both reads from canned payloads."""
    payload = [_deployment()] if deployments is None else deployments

    def run(arguments):
        if arguments[0] == "resource":
            if not account_found:
                return []
            return [{"resourceGroup": RESOURCE_GROUP}]
        assert arguments[:4] == [
            "cognitiveservices",
            "account",
            "deployment",
            "list",
        ]
        return payload

    return run


def _measure(runner=None, *, env=None, deployment=DEPLOYMENT, clock=None):
    return capacity.measure(
        dict(ENV if env is None else env),
        deployment=deployment,
        runner=runner or _runner(),
        clock=clock or _clock(),
    )


def _run(argv, *, runner=None, env=None, clock=None):
    stream = io.StringIO()
    code = capacity.main(
        argv,
        env=dict(ENV if env is None else env),
        runner=runner or _runner(),
        clock=clock or _clock(),
        stream=stream,
    )
    return code, stream.getvalue()


# -------------------------------------------------------------------------
# The denominator itself
# -------------------------------------------------------------------------


def test_a_stated_token_limit_becomes_the_denominator():
    report = _measure()
    assert report["tokens_per_minute"] == 250_000
    assert report["verdict"] == capacity.VERDICT_CAPACITY_RECORDED


def test_a_limit_stated_over_ten_seconds_is_scaled_to_a_minute():
    # 150 requests per 10 seconds is 900 per minute. The period is in the
    # payload, so this is arithmetic rather than a convention.
    report = _measure()
    assert report["requests_per_minute"] == 900


def test_the_sku_capacity_is_recorded_and_never_converted():
    """The point of the whole exercise.

    250 capacity units is a real throughput figure, and the multiplier that
    turns it into tokens per minute is documented. It is documented *elsewhere*,
    it differs per model, and the payload does not carry it -- so converting
    here would put a guess in the field a reader takes for a measurement.
    """
    report = _measure(_runner([_deployment(rate_limits=None)]))
    assert report["sku_capacity"] == 250
    assert report["sku_capacity_unit_stated_by_azure"] is False
    assert report["tokens_per_minute"] is None
    assert report["requests_per_minute"] is None
    assert report["verdict"] == capacity.VERDICT_LIMITS_NOT_STATED
    assert any("not converted" in problem for problem in report["read_failures"])


def test_a_limit_with_no_renewal_period_is_kept_but_not_converted():
    report = _measure(
        _runner([_deployment(rate_limits=[{"key": "token", "count": 250_000}])])
    )
    assert report["tokens_per_minute"] is None
    # Kept, not dropped: a limit nobody knows how to read is still a limit, and
    # dropping it would quietly shrink the evidence a later reader has.
    assert report["rate_limits"] == [
        {
            "key": "token",
            "count": 250_000,
            "renewal_period_seconds": None,
            "per_minute": None,
        }
    ]


def test_a_limit_with_a_zero_period_is_declined_rather_than_divided_by_zero():
    report = _measure(
        _runner(
            [
                _deployment(
                    rate_limits=[
                        {"key": "token", "count": 100, "renewalPeriod": 0}
                    ]
                )
            ]
        )
    )
    assert report["tokens_per_minute"] is None
    assert report["verdict"] == capacity.VERDICT_LIMITS_NOT_STATED


@pytest.mark.parametrize(
    "sku_name, pooled",
    [
        ("GlobalStandard", True),
        ("GlobalBatch", True),
        ("DataZoneStandard", True),
        ("Standard", False),
        ("ProvisionedManaged", False),
    ],
)
def test_a_pooled_sku_is_told_apart_from_a_dedicated_one(sku_name, pooled):
    report = _measure(_runner([_deployment(sku_name=sku_name)]))
    assert report["draws_on_shared_capacity"] is pooled


def test_an_unnamed_sku_is_unknown_rather_than_dedicated():
    """``None``, not ``False``.

    Not knowing whether the capacity is pooled and knowing it is dedicated
    support different readings of a refusal, so they get different values.
    """
    report = _measure(_runner([_deployment(sku_name=None)]))
    assert report["draws_on_shared_capacity"] is None


def test_a_pooled_sku_says_in_prose_that_a_ceiling_only_bounds_the_question():
    _, body = _run(["--deployment", DEPLOYMENT])
    assert "pooled capacity" in body
    assert "bounds the question and does not settle it" in body


def test_a_dedicated_sku_makes_no_such_claim():
    code, body = _run(
        ["--deployment", DEPLOYMENT],
        runner=_runner([_deployment(sku_name="ProvisionedManaged")]),
    )
    assert code == 0
    assert "pooled capacity" not in body


# -------------------------------------------------------------------------
# Answered-and-absent is not the same fact as never-answered
# -------------------------------------------------------------------------


def test_a_deployment_absent_from_an_answered_list_is_a_finding():
    report = _measure(_runner([_deployment(name="gpt-audio-1.5")]))
    assert report["verdict"] == capacity.VERDICT_DEPLOYMENT_ABSENT
    assert report["deployments_seen"] == 1


def test_a_deployment_list_az_never_answered_is_not_that_finding():
    def run(arguments):
        if arguments[0] == "resource":
            return [{"resourceGroup": RESOURCE_GROUP}]
        raise AzureReadFailure("the deployment list", exit_code=1)

    report = _measure(run)
    assert report["verdict"] == capacity.VERDICT_NEVER_COMPLETED
    # Nothing was enumerated, so the count stays absent rather than reading 0.
    assert report["deployments_seen"] is None


def test_an_account_azure_answered_without_is_a_finding_about_this_identity():
    report = _measure(_runner(account_found=False))
    assert report["verdict"] == capacity.VERDICT_CANNOT_READ_ACCOUNT


def test_an_account_lookup_az_never_answered_says_nothing_was_measured():
    def run(arguments):
        raise AzureReadFailure("az resource list", exit_code=2)

    report = _measure(run)
    assert report["verdict"] == capacity.VERDICT_NEVER_COMPLETED
    assert any("never looked up" in problem for problem in report["read_failures"])


def test_the_two_account_failures_do_not_share_a_verdict():
    absent = _measure(_runner(account_found=False))["verdict"]

    def never(arguments):
        raise AzureReadFailure("az resource list", exit_code=2)

    assert absent != _measure(never)["verdict"]


# -------------------------------------------------------------------------
# Which account gets read
# -------------------------------------------------------------------------


def test_the_account_comes_from_the_route_the_run_itself_resolves():
    """Not from a rule retyped here.

    Under project-ci there is no direct endpoint in the environment at all: the
    route derives one from the project's account. Reading the right account in
    that case is only possible by going through the same resolution the run uses,
    so this asserts the derived account is what gets queried.
    """
    env = {
        "AZURE_AI_ROUTE_PROFILE": "project-ci",
        "FOUNDRY_PROJECT_ENDPOINT": (
            f"https://{ACCOUNT}.services.ai.azure.com/api/projects/benchmark-proj"
        ),
        "AZURE_SUBSCRIPTION_ID": SUBSCRIPTION,
    }
    asked = []

    def run(arguments):
        asked.append(list(arguments))
        if arguments[0] == "resource":
            return [{"resourceGroup": RESOURCE_GROUP}]
        return [_deployment()]

    report = _measure(run, env=env)
    assert report["verdict"] == capacity.VERDICT_CAPACITY_RECORDED
    assert report["route_profile"] == "project-ci"
    assert report["account_source"] == "direct-v1"
    assert ACCOUNT in asked[0]


def test_a_deployment_lives_on_an_account_so_the_project_is_never_queried():
    env = {
        "AZURE_AI_ROUTE_PROFILE": "project-ci",
        "FOUNDRY_PROJECT_ENDPOINT": (
            f"https://{ACCOUNT}.services.ai.azure.com/api/projects/benchmark-proj"
        ),
        "AZURE_SUBSCRIPTION_ID": SUBSCRIPTION,
    }
    asked = []

    def run(arguments):
        asked.append(list(arguments))
        if arguments[0] == "resource":
            return [{"resourceGroup": RESOURCE_GROUP}]
        return [_deployment()]

    _measure(run, env=env)
    assert not any("benchmark-proj" in argument for call in asked for argument in call)


def test_a_missing_subscription_is_refused_rather_than_inherited():
    env = {key: value for key, value in ENV.items() if key != "AZURE_SUBSCRIPTION_ID"}
    with pytest.raises(ValueError, match="AZURE_SUBSCRIPTION_ID"):
        _measure(env=env)


def test_a_missing_route_profile_is_refused():
    env = {key: value for key, value in ENV.items() if key != "AZURE_AI_ROUTE_PROFILE"}
    with pytest.raises(ValueError):
        _measure(env=env)


def test_the_deployment_name_is_matched_whatever_case_it_was_typed_in():
    report = _measure(deployment="GPT-5.4")
    assert report["verdict"] == capacity.VERDICT_CAPACITY_RECORDED


def test_a_deployment_name_is_required():
    with pytest.raises(ValueError, match="deployment name"):
        _measure(deployment="   ")


# -------------------------------------------------------------------------
# When the figure was true
# -------------------------------------------------------------------------


def test_the_report_records_when_the_capacity_was_read():
    report = _measure()
    assert report["measured_at"].startswith("2026-09-11T06:00:00")


def test_a_clock_with_no_timezone_is_refused_rather_than_assumed_to_be_utc():
    naive = lambda: datetime(2026, 9, 11, 6, 0, 0)  # noqa: E731
    with pytest.raises(ValueError, match="timezone"):
        _measure(clock=naive)


def test_a_clock_in_another_zone_is_stored_as_utc():
    kst = timezone(timedelta(hours=9))
    report = _measure(clock=lambda: datetime(2026, 9, 11, 15, 0, 0, tzinfo=kst))
    assert report["measured_at"].startswith("2026-09-11T06:00:00")


# -------------------------------------------------------------------------
# What must never be printed
# -------------------------------------------------------------------------


def test_the_account_name_never_reaches_the_report():
    code, body = _run(["--deployment", DEPLOYMENT])
    assert code == 0
    assert ACCOUNT not in body
    assert ACCOUNT.lower() not in body.lower()


def test_the_resource_group_never_reaches_the_report():
    code, body = _run(["--deployment", DEPLOYMENT])
    assert code == 0
    assert RESOURCE_GROUP not in body


def test_the_subscription_id_never_reaches_the_report():
    code, body = _run(["--deployment", DEPLOYMENT])
    assert code == 0
    assert SUBSCRIPTION not in body


def test_the_names_of_the_other_deployments_are_never_printed():
    """A count, not a list.

    How many deployments an account holds is not an identifier. What they are
    called is chosen by whoever made them, and people name things after the
    project they belong to.
    """
    code, body = _run(
        ["--deployment", DEPLOYMENT],
        runner=_runner(
            [_deployment(), _deployment(name="internal-hr-summariser-prod")]
        ),
    )
    assert code == 0
    assert "internal-hr-summariser-prod" not in body
    assert "deployments on the account: 2" in body


def test_an_account_name_that_reached_the_body_is_redacted(monkeypatch):
    """The second layer, checked on its own.

    Nothing writes the account into the report today. This asserts that if
    something did, redaction would still catch it -- which is what makes the
    withholding test below a last resort rather than the only defence.
    """
    report = _measure()
    report["deployment"] = ACCOUNT
    monkeypatch.setattr(capacity, "measure", lambda *a, **k: report)
    code, body = _run(["--deployment", DEPLOYMENT])
    assert code == 0
    assert ACCOUNT not in body
    assert "<accountName>" in body


def test_the_report_is_withheld_when_redaction_is_broken(monkeypatch):
    report = _measure()
    report["deployment"] = ACCOUNT
    monkeypatch.setattr(capacity, "measure", lambda *a, **k: report)
    monkeypatch.setattr(capacity, "redact", lambda text, secrets: text)
    code, body = _run(["--deployment", DEPLOYMENT])
    assert code == 3
    assert body == ""


def test_breaking_redaction_on_a_report_with_nothing_to_leak_still_prints(monkeypatch):
    monkeypatch.setattr(capacity, "redact", lambda text, secrets: text)
    code, body = _run(["--deployment", DEPLOYMENT])
    assert code == 0
    assert "capacity_recorded" in body


# -------------------------------------------------------------------------
# The CLI
# -------------------------------------------------------------------------


def test_the_json_output_carries_the_same_verdict_as_the_prose():
    code, body = _run(["--deployment", DEPLOYMENT, "--json"])
    assert code == 0
    assert json.loads(body)["verdict"] == capacity.VERDICT_CAPACITY_RECORDED


def test_the_json_output_never_carries_the_secret_values_key():
    code, body = _run(["--deployment", DEPLOYMENT, "--json"])
    assert code == 0
    assert "secret_values" not in json.loads(body)


def test_an_unavailable_denominator_is_reported_rather_than_treated_as_an_error():
    code, body = _run(
        ["--deployment", DEPLOYMENT], runner=_runner([_deployment(rate_limits=None)])
    )
    assert code == 0
    assert "unavailable" in body


def test_require_limits_turns_an_unavailable_denominator_into_a_failure():
    code, _ = _run(
        ["--deployment", DEPLOYMENT, "--require-limits"],
        runner=_runner([_deployment(rate_limits=None)]),
    )
    assert code == 1


def test_the_written_file_is_the_redacted_record(tmp_path):
    target = tmp_path / "capacity.json"
    code, _ = _run(["--deployment", DEPLOYMENT, "--output", str(target)])
    assert code == 0
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["tokens_per_minute"] == 250_000
    assert ACCOUNT not in target.read_text(encoding="utf-8")
    assert RESOURCE_GROUP not in target.read_text(encoding="utf-8")


def test_no_file_is_written_when_the_report_would_leak(monkeypatch, tmp_path):
    """A withheld report must not leave the leak behind on disk.

    The file is the copy a run keeps and uploads, so writing it before the leak
    check would publish exactly what refusing to print was protecting.
    """
    report = _measure()
    report["deployment"] = ACCOUNT
    monkeypatch.setattr(capacity, "measure", lambda *a, **k: report)
    monkeypatch.setattr(capacity, "redact", lambda text, secrets: text)
    target = tmp_path / "capacity.json"
    code, _ = _run(["--deployment", DEPLOYMENT, "--output", str(target)])
    assert code == 3
    assert not target.exists()


# -------------------------------------------------------------------------
# It cannot spend anything
# -------------------------------------------------------------------------


MODEL_CALL_PATTERN = re.compile(
    r"responses\.create|chat\.completions|AzureOpenAI|llm_client|code_interpreter"
)


def test_the_script_references_no_model_call_path():
    assert MODEL_CALL_PATTERN.search(SCRIPT.read_text(encoding="utf-8")) is None


def test_every_az_call_it_makes_is_a_read():
    verbs = []

    def run(arguments):
        verbs.append(list(arguments))
        if arguments[0] == "resource":
            return [{"resourceGroup": RESOURCE_GROUP}]
        return [_deployment()]

    _measure(run)
    assert verbs
    for call in verbs:
        assert "list" in call
        assert not {"create", "update", "delete", "set"} & set(call)


def test_the_script_the_workflow_runs_is_committed_and_not_ignored():
    """``batch-runner/scripts/*`` is ignored wholesale in this repository.

    Each script that belongs in git is un-ignored by name, one line at a time,
    so a new one is invisible to ``git add`` until somebody adds that line. A
    script that works locally and was never committed does not fail visibly: the
    job checks out, installs Python, logs into Azure, and only then reports that
    a file is missing -- which reads as an Azure problem.
    """
    inside_git = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
    )
    if inside_git.returncode != 0:
        pytest.skip("not a git checkout, so tracking cannot be checked here")
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(SCRIPT.relative_to(REPOSITORY_ROOT))],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
    )
    assert tracked.returncode == 0, (
        "the capacity script is not tracked by git; add an un-ignore line for it "
        "to .gitignore, or the workflow will run a file that is not there"
    )


# -------------------------------------------------------------------------
# Making an empty answer diagnosable
# -------------------------------------------------------------------------


def test_an_empty_limits_read_says_which_properties_were_there():
    """Two different facts otherwise look identical.

    A deployment that genuinely declares no limits and a payload that declares
    them under a name this tool does not look for both produce an empty report.
    Telling them apart afterwards would mean reading the payload again, in CI,
    because CI is the only place the account is visible -- so the names it did
    carry are recorded the first time.
    """
    code, body = _run(
        ["--deployment", DEPLOYMENT], runner=_runner([_deployment(rate_limits=None)])
    )
    assert code == 0
    assert "model" in body
    assert "the deployment's properties carried" in body


def test_the_property_names_are_not_repeated_when_the_limits_were_read():
    code, body = _run(["--deployment", DEPLOYMENT])
    assert code == 0
    assert "properties carried" not in body


def test_only_names_shaped_like_azure_schema_are_repeated_back():
    """The filter is cheap and the promise it protects is not.

    These are Azure's own property names rather than anything a person chose,
    so nothing here is expected to be withheld. The report's whole claim is
    that no chosen string survives into it, and a claim that holds only while
    an upstream schema stays boring is not the claim being made.
    """
    entry = _deployment(rate_limits=None)
    entry["properties"]["contoso-foundry-eastus"] = "surprise"
    report = _measure(_runner([entry]))
    assert report["properties_seen"] == ["model"]
    assert ACCOUNT not in report["properties_seen"]


# -------------------------------------------------------------------------
# What else was already binding to the module this change moved things out of
# -------------------------------------------------------------------------

DIAGNOSTIC = BATCH_RUNNER / "scripts" / "azure_rbac_diagnostic.py"
SURVEY = BATCH_RUNNER / "scripts" / "azure_boot_host_survey.py"
BOUND_OFF_THE_DIAGNOSTIC = re.compile(r"\brbac\.([A-Za-z_][A-Za-z0-9_]*)")


def _diagnostic_module():
    # Loaded under a name of its own. The boot-host survey loads the same file
    # under its own key, and stamping on that entry would make this check the
    # reason another test file fails.
    name = "azure_rbac_diagnostic_binding_check"
    spec = importlib.util.spec_from_file_location(name, DIAGNOSTIC)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_every_name_the_boot_host_survey_binds_off_the_diagnostic_still_exists():
    """Private by name, public by use.

    The boot-host survey loads the diagnostic by path and reaches into it for
    helpers that were written as local functions with leading underscores. The
    underscore recorded nothing about who depended on them, so moving those
    implementations into ``core.azure_control_plane`` renamed them out from under
    a caller whose own file had not changed -- and its tests, not the
    diagnostic's, were the ones that went red.

    Read out of the survey's source rather than listed here, so a name added
    there later is covered without anybody remembering to come back.
    """
    if not SURVEY.exists():
        pytest.skip("the boot host survey is not in this checkout")
    module = _diagnostic_module()
    used = set(BOUND_OFF_THE_DIAGNOSTIC.findall(SURVEY.read_text(encoding="utf-8")))
    assert used, "nothing was found to bind, so this proves nothing"
    missing = sorted(name for name in used if not hasattr(module, name))
    assert not missing, (
        "the boot host survey binds names the diagnostic no longer has: "
        f"{missing}. Keep them as aliases rather than editing a file this "
        "change does not own."
    )


# -------------------------------------------------------------------------
# The workflow that is the only place this can be asked
# -------------------------------------------------------------------------


def _workflow():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_the_workflow_exists_and_parses():
    assert _workflow()


def test_the_workflow_is_dispatched_by_hand_only():
    # ``on`` parses as the boolean True in YAML 1.1, which is why this is not a
    # plain key lookup.
    triggers = _workflow()[True]
    assert set(triggers) == {"workflow_dispatch"}


def test_the_workflow_asks_for_no_write_permission_on_the_repository():
    assert _workflow()["permissions"] == {"contents": "read", "id-token": "write"}


def test_the_workflow_passes_no_model_credential():
    text = WORKFLOW.read_text(encoding="utf-8")
    for forbidden in ("AZURE_OPENAI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        assert forbidden not in text


def _every_env_mapping(node):
    """Every ``env:`` mapping in the workflow, at the job level or in a step."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "env" and isinstance(value, dict):
                yield value
            yield from _every_env_mapping(value)
    elif isinstance(node, list):
        for item in node:
            yield from _every_env_mapping(item)


def test_the_workflow_does_not_name_the_account_in_a_step_header():
    """Repository variables are not masked the way secrets are.

    Whatever a step lists under ``env:`` is reprinted verbatim in the step
    header, and this repository's logs are public. The account name is inside
    the endpoint secret, which is masked, so the workflow has no reason to ask
    for the variable that spells it out.

    Checked against the parsed mappings rather than the file text, so that the
    comment explaining why these are absent does not read as their presence.
    """
    forbidden = (
        "AZURE_AI_EXPECTED_DIRECT_ACCOUNT",
        "AZURE_AI_EXPECTED_PROJECT_ACCOUNT",
        "AZURE_AI_EXPECTED_PROJECT_NAME",
    )
    mappings = list(_every_env_mapping(_workflow()))
    assert mappings, "the workflow declares no env at all, so this proves nothing"
    for mapping in mappings:
        for key, value in mapping.items():
            for name in forbidden:
                assert name != key
                assert name not in str(value)


def test_the_workflow_keeps_the_grep_that_checks_for_a_model_call():
    """And keeps the same pattern this file checks the source with.

    Pinned as one string rather than a handful of substrings: two copies of a
    guard that drift apart leave both sides passing while the narrower one is
    the only thing actually running in CI.
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    assert MODEL_CALL_PATTERN.pattern in text
    assert "azure_deployment_capacity.py" in text
