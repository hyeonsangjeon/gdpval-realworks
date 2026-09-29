"""One externally approved retention cell on the existing serial CAS branch.

Default use is offline planning. Preparation is not admission. A live invocation
must reverify a same-run, owner-authored GitHub environment review of the exact
request, the actual execution job/runner, source, inputs, route and Azure session.
Only then can it attempt one CAS write and one owned child. No retry, setup,
scheduler, grading, old-campaign reinterpretation or cross-runner restore exists.
"""

from __future__ import annotations

import argparse
import base64
import binascii
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.request
import urllib.parse

import yaml
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

import codex_budget_pilot as owned
import codex_budget_pilot_ci as legacy_ci
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained
import codex_ci_input_intake as intake
import codex_retention_diagnostic as registration
import codex_retention_first_cell as controller
import codex_retention_historical as historical
import codex_retention_prepare_packet as preparation
from core.cost_projection import project_cost_receipt
from core.hf_publication import _PublicationFile, _publication_additions
from core.inference_manifest import canonical_deliverable_path
from ghcp_vm_input_bundle import _publication_parents, _write_no_clobber
from gpt54_v2_grading_input import _object
from scripts import azure_oidc_identity_preflight as azure_identity

ROOT = preparation.ROOT
WORKFLOW = ".github/workflows/codex-retention-first-cell.yml"
REPOSITORY = legacy_ci.REPOSITORY
OWNER = "hyeonsangjeon"
ENVIRONMENT = "grading"
PREPARE_JOB = "retention-prepare"
APPROVE_JOB = "retention-approve"
EXECUTE_JOB = "retention-execute"
BRANCH = retained.BRANCH
PREFIX = "retention-diagnostics/" + registration.CAMPAIGN + "/" + controller.FIRST_CELL_ID
CLAIM = PREFIX + "/admission.json"
TERMINAL = PREFIX + "/terminal.json"
OUTPUT = PREFIX + "/outputs"
PACKET_ROLE = "batch-runner/workspace/retention-ci-first"
REQUEST_FORMAT = "retention-first-cell-execution-request-v1"
CLAIM_FORMAT = "retention-first-cell-claim-v1"
TERMINAL_FORMAT = "retention-first-cell-terminal-v1"
APPROVAL_PREFIX = "approve-retention-first-cell sha256:"
API = "https://api.github.com/repos/" + REPOSITORY + "/actions/runs/"
OIDC_ISSUER = "https://token.actions.githubusercontent.com"
OIDC_JWKS = OIDC_ISSUER + "/.well-known/jwks"
OIDC_MAX_BYTES = 64 * 1024
OIDC_MAX_AGE_SECONDS = 600
OIDC_SKEW_SECONDS = 30
UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
SOURCE_PATHS = (
    "batch-runner/codex_retention_ci.py", "batch-runner/codex_retention_historical.py", WORKFLOW,
    "batch-runner/codex_budget_pilot_ci.py", "batch-runner/codex_budget_pilot_retention.py",
    "batch-runner/codex_budget_pilot_output.py", "batch-runner/codex_ci_input_intake.py",
    "batch-runner/codex_ci_input_bundle.py", "batch-runner/gpt54_disposable_checkout.py",
    "batch-runner/scripts/azure_oidc_identity_preflight.py",
)
SCOPE = {
    "cell_id": controller.FIRST_CELL_ID, "ordinal": 0, "cell_count": 1,
    "registered_denominator": 8, "active_inference_ceiling": 1,
    "cumulative_seconds": 10800, "native_turn_wait_seconds": 1800,
    "native_turn_wait_is_all_in_attempt_ceiling": False,
    "max_admissions": None, "restart_clock": False, "mechanical_recovery": "B",
    "retention_bundle": "keep", "c_feedback": False, "grading_launched": False,
    "automatic_rerun": False, "monetary_automatic_cap": None, "invoice_complete": False,
}


class RetentionCIRefused(ValueError):
    """Safe structural diagnostics; never a provider body or private path."""


def require(condition, reason):
    if not condition:
        raise RetentionCIRefused(reason)


def same(reason, actual, expected):
    require(owned._canonical_json(actual) == owned._canonical_json(expected), reason)


def source_identity():
    files = {name: owned._identity(preparation._read(ROOT / name, "adapter_source")) for name in SOURCE_PATHS}
    return {"files": files, "sha256": owned._digest(files), "reviewed": False}


def require_source(sha: str) -> dict:
    require(output._hash(sha, 40), "exact_reviewed_source_required")
    owned._repository(ROOT)
    owned._safe_checkout_configuration(ROOT)
    require(owned._git(ROOT, "rev-parse", "HEAD").stdout == (sha + "\n").encode()
            and not owned._git(ROOT, "status", "--porcelain", "--untracked-files=normal").stdout,
            "clean_exact_retention_source_required")
    tree = owned._git(ROOT, "rev-parse", "HEAD^{tree}").stdout.decode().strip()
    require(output._hash(tree, 40), "source_tree_required")
    # Direct-workflow JWTs have no numeric job-ID claim. Only this reviewed
    # execution job may mint a same-run token; an API job name alone is not
    # proof that the current process possesses that job's issuance authority.
    workflow = yaml.safe_load(preparation._read(ROOT / WORKFLOW, "workflow_source"))
    jobs = workflow["jobs"]
    require(workflow["permissions"] == {"contents": "read"}
            and set(jobs) == {PREPARE_JOB, APPROVE_JOB, EXECUTE_JOB}
            and "permissions" not in jobs[PREPARE_JOB] and jobs[APPROVE_JOB]["permissions"] == {}
            and jobs[EXECUTE_JOB]["permissions"] == {"contents": "read", "actions": "read", "id-token": "write"}
            and "environment" not in jobs[EXECUTE_JOB]
            and all(job["runs-on"] == "ubuntu-22.04" and "uses" not in job for job in jobs.values()),
            "exclusive_execution_job_oidc_scope_required")
    return {"head": sha, "tree": tree, "adapter": source_identity()}


@dataclass(frozen=True)
class ExecutionGrantRequest:
    """A locator for provider verification, NOT a grant or an approval flag."""

    reviewed_source_sha: str
    request_sha256: str
    historical_root: Path


def canonical_request(request: controller.Request, *, reviewed_source_sha: str,
                      run_id: str, historical_root: Path) -> tuple[dict, dict]:
    require(type(run_id) is str and re.fullmatch(r"[1-9][0-9]{0,19}", run_id) is not None,
            "exact_github_run_required")
    source = require_source(reviewed_source_sha)
    stage = controller.verify_staged_runtime(request)
    # Observe the historical producer with its real compiler and the same real
    # originals. No copied digest is substituted for this compilation/reading.
    observation = historical.observe(historical_root, request.sources)
    expected_identity = azure_identity.expected_identity(os.environ)
    require(request.packet == ROOT / PACKET_ROLE, "fixed_materialized_packet_role_required")
    document = {
        "format": REQUEST_FORMAT, "scope": SCOPE,
        "source": source, "plan_sha256": stage["plan_sha256"],
        "packet_sha256": stage["packet_sha256"], "stage_sha256": owned._digest(stage),
        "config_sha256": stage["config_sha256"], "input_roles_sha256": stage["input_roles_sha256"],
        "selected_task": stage["selected_task"], "grading": stage["grading"],
        "compiler_source": stage["compiler_source"], "preparer_source": stage["preparer_source"],
        "controller_source": stage["controller_source"],
        "historical_observer_sha256": owned._digest(observation),
        "historical_observer_source": historical.SOURCE, "historical_producer_source": historical.PRODUCER,
        "provider": {"repository": REPOSITORY, "workflow": WORKFLOW, "run_id": run_id,
                     "attempt": 1, "event": "workflow_dispatch", "ref": "refs/heads/main",
                     "approval_environment": ENVIRONMENT, "execution_job": EXECUTE_JOB},
        "host": {"runner_label": "ubuntu-22.04", "python": "3.10.12", "sdk": "0.147.0",
                 "cli": "0.147.0", "identity": "provider_authenticated_same_run_execution_job",
                 "origin_witness": "github_rs256_job_oidc_request_job_and_local_boot_audience",
                 "trust_boundary": "github_job_scoped_issuance_credential_not_hardware_attestation",
                 "cross_runner_restore": False, "job_minutes": 240},
        "deployment": registration.compile_plan()["common"]["model"],
        "azure_identity_sha256": owned._digest(expected_identity),
        "serial_domain": {"repository_name_sha256": retained.TARGET_SHA256, "branch": BRANCH,
                          "prefix": PREFIX, "predecessor_cell": historical.FINAL_CELL},
        "preparation_is_admission": False,
    }
    return document, observation


class LocalTransport(owned.LocalTransport):
    """Only transport is injectable; all verdicts remain in production code."""

    def authority_opener(self):
        return urllib.request.build_opener(urllib.request.ProxyHandler({}), intake._NoRedirect())

    def _authority_json(self, url, *, token, deadline, limit=OIDC_MAX_BYTES):
        with intake._response(self.authority_opener(), url, token=token, accept="application/json",
                deadline=deadline, stage=intake.GitHubStage.RELEASE_METADATA) as response:
            require(response.geturl() == url and response.status == 200,
                    "github_authority_origin_or_status_refused")
            require(intake._header(response, "Link") is None, "github_authority_pagination_refused")
            data = intake._body(response, limit=limit, types={"application/json"}, deadline=deadline)
        try:
            return json.loads(data, object_pairs_hook=_object)
        except (ValueError, TypeError, UnicodeError):
            raise RetentionCIRefused("github_authority_json_refused") from None

    def github(self, run_id: str) -> tuple[dict, dict, list]:
        token = os.environ.get("GITHUB_TOKEN", "")
        require(token and len(token) <= 4096 and all(33 <= ord(char) <= 126 for char in token),
                "explicit_github_read_token_required")
        deadline = time.monotonic() + intake.TRANSFER_TIMEOUT_SECONDS
        records = []
        for suffix in ("", "/attempts/1/jobs?per_page=100", "/approvals"):
            url = API + run_id + suffix
            records.append(self._authority_json(url, token=token, deadline=deadline,
                                               limit=intake.MAX_METADATA_BYTES))
        return tuple(records)

    def github_job_token(self, audience: str) -> tuple[dict, dict]:
        """Issue only after authenticated approval; no caller-supplied JWT path."""
        token = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")
        require(token and len(token) <= 16384 and all(33 <= ord(char) <= 126 for char in token),
                "github_job_issuance_credential_required")
        locator = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")
        try:
            address = urllib.parse.urlsplit(locator)
            query = urllib.parse.parse_qsl(address.query, keep_blank_values=True, strict_parsing=True)
            require(len(locator) <= 4096 and address.scheme == "https"
                    and address.netloc == address.hostname and not address.fragment
                    and re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+actions\.githubusercontent\.com",
                                     address.netloc) is not None
                    and address.hostname != "token.actions.githubusercontent.com"
                    and re.fullmatch("/" + UUID + "/_apis/distributedtask/hubs/build/plans/" + UUID
                                     + "/jobs/" + UUID + "/idtoken", address.path) is not None
                    and query == [("api-version", "2.0")], "github_job_issuance_locator_refused")
        except ValueError:
            raise RetentionCIRefused("github_job_issuance_locator_refused") from None
        url = urllib.parse.urlunsplit(address._replace(query=urllib.parse.urlencode(
            [*query, ("audience", audience)])))
        deadline = time.monotonic() + intake.TRANSFER_TIMEOUT_SECONDS
        issued = self._authority_json(url, token=token, deadline=deadline)
        keys = self._authority_json(OIDC_JWKS, token=None, deadline=deadline)
        return issued, keys

    def azure(self, arguments: list[str]) -> str:
        return azure_identity._run_az(arguments)

    def process(self, command: list[str], **options):
        # Keep the existing command/owned-supervisor machinery. In addition to
        # its HF/GitHub stripping, do not pass GitHub OIDC request credentials
        # into a model or tool process. The host Azure CLI session is unchanged.
        options["env"] = {key: value for key, value in options["env"].items()
                          if key not in {"ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_URL"}}
        return self.owned_process(command, **options)

    def owned_process(self, command: list[str], **options):
        return super().process(command, **options)


def _base64url(value):
    require(type(value) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,24000}", value) is not None,
            "github_oidc_encoding_refused")
    try:
        data = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, binascii.Error):
        raise RetentionCIRefused("github_oidc_encoding_refused") from None
    require(base64.urlsafe_b64encode(data).decode().rstrip("=") == value, "github_oidc_encoding_refused")
    return data


def verify_job_origin(document, run, job, boot, transport):
    """Verify GitHub's signed scope, not a local checksum or caller verdict.

    The owner approves the same-run hosted job policy; GitHub's job-scoped
    issuance credential supplies its origin witness. This cannot defend against
    theft of that issuance credential and is not hardware attestation.
    """
    host = {"job": job["id"], "runner": job["runner_id"], "boot": boot}
    audience = "urn:gdpval:retention-first-cell:" + owned._digest(document) + ":" + owned._digest(host)
    issued, jwks = transport.github_job_token(audience)
    require(type(issued) is dict and set(issued) == {"value"} and type(issued["value"]) is str
            and len(issued["value"]) <= 24000, "github_job_token_response_refused")
    parts = issued["value"].split(".")
    require(len(parts) == 3, "github_job_token_format_refused")
    try:
        header, claims = (json.loads(_base64url(value), object_pairs_hook=_object) for value in parts[:2])
    except (ValueError, TypeError, UnicodeError):
        raise RetentionCIRefused("github_job_token_json_refused") from None
    require(type(header) is dict and {"typ", "alg", "kid"} <= set(header)
            and set(header) <= {"typ", "alg", "kid", "x5t", "x5t#S256"}
            and header["typ"] == "JWT" and header["alg"] == "RS256"
            and type(header["kid"]) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,256}", header["kid"]) is not None,
            "github_oidc_header_refused")
    require(type(jwks) is dict and set(jwks) == {"keys"} and type(jwks["keys"]) is list
            and 1 <= len(jwks["keys"]) <= 16, "github_oidc_keyset_refused")
    key_ids = [key.get("kid") for key in jwks["keys"] if type(key) is dict]
    require(len(key_ids) == len(jwks["keys"]) and all(type(kid) is str for kid in key_ids)
            and len(set(key_ids)) == len(key_ids) and header["kid"] in key_ids, "github_oidc_key_id_refused")
    key = jwks["keys"][key_ids.index(header["kid"])]
    require(key.get("kty") == "RSA" and key.get("alg", "RS256") == "RS256" and key.get("use") == "sig"
            and not {"jku", "x5u", "d", "p", "q", "dp", "dq", "qi"} & key.keys(), "github_oidc_key_refused")
    modulus, exponent = (int.from_bytes(_base64url(key.get(field)), "big") for field in ("n", "e"))
    require(2048 <= modulus.bit_length() <= 4096 and exponent == 65537, "github_oidc_key_refused")
    try:
        rsa.RSAPublicNumbers(exponent, modulus).public_key().verify(
            _base64url(parts[2]), (parts[0] + "." + parts[1]).encode("ascii"), padding.PKCS1v15(), hashes.SHA256())
    except (InvalidSignature, ValueError):
        raise RetentionCIRefused("github_oidc_signature_refused") from None
    repository = run["repository"]
    expected = {"iss": OIDC_ISSUER, "aud": audience, "sub": "repo:" + REPOSITORY + ":ref:refs/heads/main",
        "repository": REPOSITORY, "repository_id": str(repository["id"]), "repository_owner": OWNER,
        "repository_owner_id": str(repository["owner"]["id"]), "actor": OWNER,
        "actor_id": str(run["actor"]["id"]), "ref": "refs/heads/main", "ref_type": "branch",
        "sha": document["source"]["head"], "workflow_ref": REPOSITORY + "/" + WORKFLOW + "@refs/heads/main",
        "workflow_sha": document["source"]["head"], "run_id": str(run["id"]), "run_attempt": "1",
        "event_name": "workflow_dispatch", "runner_environment": "github-hosted"}
    require(type(claims) is dict and all(claims.get(key) == value for key, value in expected.items())
            and "environment" not in claims, "github_oidc_scope_mismatch")
    now = time.time()
    require(all(type(claims.get(field)) is int for field in ("iat", "nbf", "exp"))
            and now - OIDC_MAX_AGE_SECONDS <= claims["iat"] <= now + OIDC_SKEW_SECONDS
            and 0 <= claims["nbf"] <= now + OIDC_SKEW_SECONDS and claims["nbf"] < claims["exp"]
            and now < claims["exp"] <= claims["iat"] + OIDC_MAX_AGE_SECONDS,
            "github_oidc_time_refused")
    # Fresh issuances may change jti/iat/exp/kid. Bind only verified, stable
    # semantics; no token, credential or token digest enters a CAS record.
    return {"issuer": OIDC_ISSUER, "scope_sha256": owned._digest(expected),
            "host_instance_sha256": owned._digest(host)}


def verify_approval(document: dict, transport: LocalTransport) -> dict:
    source, provider = document["source"]["head"], document["provider"]
    expected = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": REPOSITORY,
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": source, "RETENTION_WORKFLOW_SHA": source,
        "GITHUB_RUN_ID": provider["run_id"], "GITHUB_JOB": EXECUTE_JOB,
        "GITHUB_WORKFLOW_REF": REPOSITORY + "/" + WORKFLOW + "@refs/heads/main",
        "RUNNER_OS": "Linux", "ImageOS": "ubuntu22"}
    require(all(os.environ.get(key) == value for key, value in expected.items()),
            "retention_ci_source_run_or_host_mismatch")
    run, jobs, reviews = transport.github(provider["run_id"])
    require(type(run) is dict and type(run.get("id")) is int and str(run["id"]) == provider["run_id"]
            and run.get("url") == API + provider["run_id"] and run.get("head_sha") == source
            and run.get("path") == WORKFLOW and run.get("event") == "workflow_dispatch"
            and run.get("head_branch") == "main" and type(run.get("run_attempt")) is int
            and run["run_attempt"] == 1 and run.get("status") == "in_progress"
            and run.get("repository", {}).get("full_name") == REPOSITORY
            and all(run.get(key, {}).get("login") == OWNER for key in ("actor", "triggering_actor")),
            "authenticated_retention_run_mismatch")
    repository = run["repository"]
    require(type(repository.get("id")) is int and repository["id"] > 0
            and repository.get("owner", {}).get("login") == OWNER
            and type(repository["owner"].get("id")) is int and repository["owner"]["id"] > 0
            and all(type(run[key].get("id")) is int and run[key]["id"] == repository["owner"]["id"]
                    for key in ("actor", "triggering_actor")), "authenticated_repository_owner_mismatch")
    require(type(jobs) is dict and type(jobs.get("jobs")) is list and type(jobs.get("total_count")) is int
            and jobs["total_count"] == len(jobs["jobs"]) == 3, "authenticated_job_set_mismatch")
    by_name = {job.get("name"): job for job in jobs["jobs"] if type(job) is dict}
    require(set(by_name) == {PREPARE_JOB, APPROVE_JOB, EXECUTE_JOB}, "authenticated_job_set_mismatch")
    for name, job in by_name.items():
        require(type(job.get("id")) is int and job["id"] > 0
                and job.get("run_id") == run["id"] and job.get("head_sha") == source
                and job.get("run_attempt") == 1
                and job.get("status") == ("in_progress" if name == EXECUTE_JOB else "completed")
                and job.get("conclusion") == (None if name == EXECUTE_JOB else "success"),
                "authenticated_job_state_mismatch")
    job = by_name[EXECUTE_JOB]
    require(type(job.get("runner_id")) is int and job["runner_id"] > 0
            and job.get("runner_name") == os.environ.get("RUNNER_NAME") and bool(job.get("runner_name"))
            and job.get("labels") == ["ubuntu-22.04"], "authenticated_execution_runner_mismatch")
    require(type(reviews) is list and len(reviews) == 1 and type(reviews[0]) is dict,
            "unambiguous_owner_environment_review_required")
    review = reviews[0]
    environments = review.get("environments")
    require(review.get("state") == "approved" and review.get("user", {}).get("login") == OWNER
            and review["user"].get("id") == repository["owner"]["id"]
            and review.get("comment") == APPROVAL_PREFIX + owned._digest(document)
            and type(environments) is list and len(environments) == 1
            and environments[0].get("name") == ENVIRONMENT
            and type(environments[0].get("id")) is int and environments[0]["id"] > 0,
            "owner_environment_request_approval_mismatch")
    boot = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
    require(re.fullmatch(r"[0-9a-f-]{36}", boot) is not None, "live_host_instance_required")
    origin = verify_job_origin(document, run, job, boot, transport)
    return {"request_sha256": owned._digest(document), "provider_run_id": provider["run_id"],
            "provider_job_id": job["id"], "runner_id": job["runner_id"],
            "host_instance_sha256": origin["host_instance_sha256"], "job_origin": origin,
            "review_sha256": owned._digest(review), "reviewer": OWNER, "environment": ENVIRONMENT}


def require_runtime(document: dict, request: controller.Request, transport: LocalTransport):
    from core.codex_runtime_config import require_pinned_runtime
    from core.azure_ai_clients import AzureAIRouteSettings
    import step2_run_inference as step2

    require(sys.version_info[:3] == (3, 10, 12), "retention_python_version_mismatch")
    require_pinned_runtime()  # Version queries only, not a constructor or turn.
    step2._require_runnable_execution_mode("codex_foundry")
    step2._require_host_may_carry_a_benchmark_run("codex_foundry")
    settings = AzureAIRouteSettings.from_env()
    model = document["deployment"]
    require(settings.profile.value == model["route_profile"] and settings.direct_v1 is not None
            and settings.direct_v1.account == model["account"], "retention_registered_route_required")
    cell = controller._context(request)["cell"]
    routes = step2.preflight_routes(step2.inference_route_workloads(cell["config"]["condition_a"],
                                                                    "codex_foundry"), settings=settings)
    identity = azure_identity.verify_session_identity(os.environ, run_az=transport.azure)
    same("retention_azure_identity_mismatch", owned._digest(identity), document["azure_identity_sha256"])
    return routes


def _cache(host: Path, name: str) -> Path:
    path = host / name
    path.mkdir(mode=0o700, exist_ok=False)
    return path


def _absent(api, repo, parent, paths, token):
    from huggingface_hub import RepoFolder

    require(api.get_paths_info(repo_id=repo, repo_type="dataset", revision=parent,
                              paths=paths, token=token) == [], "retention_namespace_already_used")
    ancestors = ["retention-diagnostics", "retention-diagnostics/" + registration.CAMPAIGN]
    found = api.get_paths_info(repo_id=repo, repo_type="dataset", revision=parent,
                              paths=ancestors, token=token)
    require(type(found) is list and len(found) <= len(ancestors)
            and all(isinstance(item, RepoFolder) and item.path in ancestors for item in found),
            "retention_namespace_ancestor_refused")


def _snapshot(host, request, document, state):
    """Real result/ledger/deliverable checks; only allowlisted bytes can leave."""
    context = controller._context(request)
    cell = controller._adapted_cell(context["cell"])
    plan = context["plan"]
    owned._validate_state(plan, cell, state)
    owned._require_quiet_owner(host, plan)
    owner = owned._load(host / "owned-child.json")
    require(owner["phase"] == "reaped" and owner["cell_id"] == request.cell_id
            and owner["stage"] == "infer" and state["status"] in owned.TERMINAL
            and state["child_invocations"] == 1, "confirmed_selected_child_cleanup_required")
    checked = deepcopy(state)
    owned._finish(host, cell, checked, state["exit_code"])
    for key in ("result", "receipt", "accounting", "artifacts"):
        same("terminal_result_or_accounting_changed", checked[key], state[key])
    require(state["status"] == checked["status"] or state["reason"] == "child_timeout_partial_accounting",
            "terminal_status_changed")
    files = {}
    if state["result"] is not None:
        data = output._bytes(host / cell["roles"]["result"], limit=output.MAX_RECORD_BYTES, expected=state["result"])
        value = owned._json_object(data)
        output._safe_record(value)
        require(set(value) <= output.RESULT_FIELDS, "unsafe_result_fields")
        row, = value["results"]
        require(set(row) <= output.ROW_FIELDS and not row.get("failure_evidence")
                and row.get("usage") is None and not row.get("reflection_history")
                and row.get("reflection_attempts", 0) == 0, "unsafe_result_fields")
        output._receipt_fields(row.get("problem_solving_cost"))
        if "source" in value:
            same("result_source_mismatch", value["source"], context["plan"]["inputs"]["repo_id"])
        if "summary" in value:
            require(type(value["summary"]) is dict and set(value["summary"]) <= {
                "total", "success", "error", "qa_failed", "problem_solving_cost"}, "unsafe_result_summary")
            output._receipt_fields(value["summary"].get("problem_solving_cost"))
        if "azure_ai_routes" in value:
            same("unsafe_result_routes", output.canonicalize_azure_ai_routes(value["azure_ai_routes"]),
                 value["azure_ai_routes"])
        if value.get("cost_ledger") is not None:
            require(set(value["cost_ledger"]) == {"path", "sha256"}, "unsafe_ledger_reference")
        if "observability" in row:
            from step2_run_inference import _build_execution_observability
            observed = row["observability"]
            require(type(observed) is dict and observed.get("preprocessors", []) == [], "unsafe_result_observability")
            same("unsafe_result_observability", observed, _build_execution_observability({
                "error_category": observed.get("error_category"), "execution_metrics": observed.get("execution_metrics"),
                "codex_diagnostics": observed.get("codex"), "task_deadline": observed.get("task_deadline"),
                "budget_metrics": observed.get("budget_metrics"), "substrate_manifest": observed.get("substrate"),
            }, []))
        require(not row.get("error") or row["error"] == output.public_task_error_text(row["error"]),
                "unsafe_result_error")
        files["step2_inference_results.json"] = data
        for item in state["artifacts"]["deliverable_files"]:
            name = canonical_deliverable_path(cell["task_id"], item["path"])
            require(name == item["path"] and name not in files and not {part.lower() for part in Path(name).parts}
                    & {"codex_home", "auth.json", "credentials.json", "transcript.jsonl", "native-transcript.jsonl"}
                    and Path(name).suffix.lower() not in {".sqlite", ".sqlite3"}, "private_state_file_refused")
            files[name] = output._bytes(ROOT / "batch-runner/workspace/upload" / name,
                                       limit=output.MAX_FILE_BYTES, expected=item)
        ledger = state["artifacts"]["ledger"]
        if ledger is not None:
            data = output._bytes(host / cell["roles"]["ledger"], limit=output.MAX_RECORD_BYTES, expected=ledger)
            output._ledger(data, cell)
            files[Path(owned.LEDGER).name] = data
    else:
        require(state["status"] in {"failed", "stopped"}, "missing_result_not_success")
    require(len(files) <= output.MAX_FILES + 2 and sum(map(len, files.values())) <= output.MAX_TOTAL_BYTES,
            "retention_output_bounds_exceeded")
    receipt = project_cost_receipt(state["receipt"])
    summary = {"format": "retention-first-cell-output-v1", "request_sha256": owned._digest(document),
        "source_sha": document["source"]["head"], "cell_id": request.cell_id,
        "status": state["status"], "exit_code": state["exit_code"], "cleanup_confirmed": True,
        "accounting": state["accounting"], "receipt": receipt, "grade": None,
        "grading_launched": False, "invoice_complete": False,
        "missing": ([] if state["result"] is not None else ["bound_inference_result", "validated_deliverables"])
            + ([] if state["artifacts"].get("ledger") is not None else ["bound_ledger_export"])
            + ([] if receipt is not None and receipt["usage"] is not None else ["usage"]),
        "files": [{"path": name, **owned._identity(data)} for name, data in sorted(files.items())]}
    return summary, files


def verify_terminal(api, repo, head, document, cache, token, deadline):
    """Read an immutable terminal after an ambiguous response; never replay.

    This is an observer, not admission or a claim adopter. A later cell is not
    implemented here. Observation cannot release an unconfirmed live child.
    """
    terminal, _ = retained._control(api, repo, head, TERMINAL, cache, token, deadline, written_at=head)
    require(set(terminal) == {"format", "request_sha256", "authority", "scope", "claim_commit", "claim_identity",
            "output_commit", "output_objects", "completion", "publication_acknowledged"}
            and terminal["format"] == TERMINAL_FORMAT and terminal["publication_acknowledged"] is True
            and terminal["request_sha256"] == owned._digest(document)
            and terminal["scope"] == "existing_inference_branch_one_use_remote_cas"
            and all(output._hash(terminal[key], 40) for key in ("claim_commit", "output_commit"))
            and len({head, terminal["claim_commit"], terminal["output_commit"]}) == 3,
            "retention_terminal_contract_mismatch")
    claim, claim_bytes = retained._control(api, repo, terminal["claim_commit"], CLAIM, cache, token, deadline,
        expected=terminal["claim_identity"], written_at=terminal["claim_commit"])
    require(set(claim) == {"format", "request_sha256", "authority", "scope", "expected_parent",
                         "predecessor", "model_result", "grade"}
            and claim["format"] == CLAIM_FORMAT and claim["model_result"] is False and claim["grade"] is None,
            "retention_claim_contract_mismatch")
    for key in ("request_sha256", "authority", "scope"):
        same("retention_terminal_claim_mismatch", terminal[key], claim[key])
    predecessor = claim["predecessor"]
    require(type(predecessor) is dict and set(predecessor) == {
        "cell_id", "terminal_commit", "terminal_sha256", "output_commit", "manifest_sha256"}
        and predecessor["cell_id"] == historical.FINAL_CELL
        and predecessor["terminal_commit"] == claim["expected_parent"]
        and all(output._hash(predecessor[key], 40 if key.endswith("commit") else 64)
                for key in ("terminal_commit", "terminal_sha256", "output_commit", "manifest_sha256")),
        "retention_predecessor_binding_mismatch")
    summary, summary_bytes = retained._control(api, repo, terminal["output_commit"], OUTPUT + "/" + output.MANIFEST,
                                               cache, token, deadline, written_at=terminal["output_commit"])
    same("retention_terminal_output_mismatch", summary, terminal["completion"])
    require(set(summary) == {"format", "request_sha256", "source_sha", "cell_id", "status", "exit_code",
        "cleanup_confirmed", "accounting", "receipt", "grade", "grading_launched", "invoice_complete", "missing", "files"}
        and summary["format"] == "retention-first-cell-output-v1"
        and summary["request_sha256"] == owned._digest(document) and summary["source_sha"] == document["source"]["head"]
        and summary["cell_id"] == controller.FIRST_CELL_ID and summary["status"] in owned.TERMINAL
        and summary["cleanup_confirmed"] is True and summary["grade"] is None
        and summary["grading_launched"] is False and summary["invoice_complete"] is False
        and (summary["exit_code"] is None or type(summary["exit_code"]) is int), "retention_completion_mismatch")
    receipt = project_cost_receipt(summary["receipt"])
    same("retention_accounting_mismatch", summary["receipt"], receipt)
    require(summary["accounting"] == ("missing" if receipt is None else receipt["status"]), "retention_accounting_mismatch")
    files = summary["files"]
    require(type(files) is list and len(files) <= output.MAX_FILES + 2, "retention_output_bounds_exceeded")
    for record in files:
        require(type(record) is dict and set(record) == {"path", "size", "sha256"}
                and type(record["size"]) is int and 0 <= record["size"] <= output.MAX_FILE_BYTES
                and output._hash(record["sha256"]), "retention_output_identity_refused")
        name = record["path"]
        require(name in {"step2_inference_results.json", Path(owned.LEDGER).name}
                or canonical_deliverable_path(registration.TASK4, name) == name, "retention_output_role_refused")
    names = [record["path"] for record in files]
    require(names == sorted(set(names)) and sum(item["size"] for item in files) <= output.MAX_TOTAL_BYTES,
            "retention_output_bounds_exceeded")
    missing = ([] if "step2_inference_results.json" in names else ["bound_inference_result", "validated_deliverables"])
    if missing:
        require(summary["status"] in {"failed", "stopped"} and files == [], "missing_result_not_success")
    missing += ([] if Path(owned.LEDGER).name in names else ["bound_ledger_export"])
    missing += ([] if receipt is not None and receipt["usage"] is not None else ["usage"])
    same("retention_missing_accounting_mismatch", summary["missing"], missing)
    expected = {OUTPUT + "/" + record["path"]: {key: record[key] for key in ("size", "sha256")} for record in files}
    expected[OUTPUT + "/" + output.MANIFEST] = owned._identity(summary_bytes)
    objects = terminal["output_objects"]
    require(type(objects) is list and len(objects) == len(expected), "retention_output_objects_mismatch")
    for record in objects:
        require(type(record) is dict and set(record) == {"path", "size", "sha256", "git_blob_sha1"}
                and record["path"] in expected and output._hash(record["git_blob_sha1"], 40)
                and {key: record[key] for key in ("size", "sha256")} == expected[record["path"]],
                "retention_output_objects_mismatch")
    for revision in (terminal["output_commit"], head):
        retained._objects(api, repo, revision, objects, token, deadline, written_at=terminal["output_commit"])
    retained._objects(api, repo, head, [retained._object(CLAIM, claim_bytes)], token, deadline,
                      written_at=terminal["claim_commit"])
    return {"request_sha256": owned._digest(document), "terminal_commit": head, "completion": summary,
            "observation_only": True, "replay_authorized": False}


class _Admission:
    """Private one-use continuation of a verified external grant, not a token API."""

    def __init__(self, request, document, observation, authority, transport, api):
        self.request, self.document, self.observation = request, document, observation
        self.authority, self.transport, self.api = authority, transport, api
        self.receipt = None

    @property
    def binding(self):
        return {"request_sha256": owned._digest(self.document), "authority": self.authority,
                "scope": "existing_inference_branch_one_use_remote_cas"}

    def admit(self, host: Path):
        same("external_grant_changed_before_claim", verify_approval(self.document, self.transport), self.authority)
        retained._write(host / "remote-admission-reserved.json", {"outcome": "unresolved", **self.binding})
        cache = _cache(host, "claim-verification")
        result = {"outcome": "unresolved", "stage": "predecessor", "reason": None,
                  "returned_commit": None, "claim": None}
        try:
            with retained._session(self.api) as (api, token, deadline):
                repo = retained._target()
                parent = output._metadata(api, repo, BRANCH, token, deadline)["sha"]
                old_plan = self.observation["plan"]
                final = retained._terminal(api, repo, parent, old_plan, old_plan["cells"][-1],
                    self.observation["inputs"], cache, token, deadline)
                same("recorded_final_old_run_mismatch", final["claim"]["binding"]["github_run"],
                     {"id": historical.FINAL_RUN, "job": "cell", "attempt": 1})
                # _terminal verified the original compiler/config/input hashes,
                # completion, manifest, object history and cleanup at THIS CAS
                # parent. No guessed historical terminal SHA or receipt is used.
                _absent(api, repo, parent, [PREFIX], token)
                claim = {"format": CLAIM_FORMAT, **self.binding, "expected_parent": parent,
                         "predecessor": final["observation"], "model_result": False, "grade": None}
                result.update(stage="claim", claim=claim)
                result["returned_commit"] = retained._commit(api, repo, parent, CLAIM, claim, cache, token, deadline)
                result.update(outcome="acknowledged", stage="claim_verified")
        except (Exception, KeyboardInterrupt) as error:
            result["reason"] = str(error) if isinstance(error, RetentionCIRefused) else output._error_context(error)[0]
        retained._write(host / "remote-admission-receipt.json", result)
        require(result["outcome"] == "acknowledged", "retention_claim_unresolved:" + str(result["reason"]))
        self.receipt = result

    def require_admission(self, host):
        require(self.receipt is not None, "verified_remote_retention_admission_required")
        same("remote_retention_receipt_changed", retained._read(host / "remote-admission-receipt.json"), self.receipt)
        same("remote_retention_reservation_changed", retained._read(host / "remote-admission-reserved.json"),
             {"outcome": "unresolved", **self.binding})
        same("retention_input_or_stage_changed_after_claim", owned._digest(controller.verify_staged_runtime(self.request)),
             self.document["stage_sha256"])
        same("retention_authority_changed_after_claim", verify_approval(self.document, self.transport), self.authority)

    def finish(self, host, state):
        summary, files = _snapshot(host, self.request, self.document, state)
        retained._write(host / "remote-terminal-reserved.json", {"outcome": "unresolved", **self.binding})
        cache = _cache(host, "terminal-verification")
        result = {"outcome": "unresolved", "stage": "output", "reason": None,
                  "output_commit": None, "terminal_commit": None, "completion": summary}
        try:
            with retained._session(self.api) as (api, token, deadline):
                repo, parent = retained._target(), self.receipt["returned_commit"]
                require(output._metadata(api, repo, BRANCH, token, deadline)["sha"] == parent,
                        "retention_output_parent_changed")
                _absent(api, repo, parent, [OUTPUT, TERMINAL], token)
                claim, _ = retained._control(api, repo, parent, CLAIM, cache, token, deadline, written_at=parent)
                same("retention_claim_changed", claim, self.receipt["claim"])
                payloads = {**files, output.MANIFEST: retained._encoded(summary)}
                staged = tuple(_PublicationFile(OUTPUT + "/" + name, io.BytesIO(data), len(data),
                                               hashlib.sha256(data).hexdigest()) for name, data in payloads.items())
                objects = [retained._object(OUTPUT + "/" + name, data) for name, data in sorted(payloads.items())]
                try:
                    operations = _publication_additions(staged)
                    response = api.create_commit(repo_id=repo, repo_type="dataset", revision=BRANCH, token=token,
                        parent_commit=parent, operations=operations, commit_message="Retain one diagnostic cell output",
                        num_threads=1, run_as_future=False, create_pr=False)
                    revision = getattr(response, "oid", None)
                    require(output._hash(revision, 40) and revision != parent
                            and not any(getattr(item, "_should_ignore", False) for item in operations),
                            "retention_output_acknowledgment_missing")
                finally:
                    for item in staged:
                        item.stream.close()
                result["output_commit"] = revision
                retained._objects(api, repo, revision, objects, token, deadline, written_at=revision)
                require(output._metadata(api, repo, BRANCH, token, deadline)["sha"] == revision,
                        "retention_terminal_parent_changed")
                terminal = {"format": TERMINAL_FORMAT, **self.binding, "claim_commit": parent,
                    "claim_identity": owned._identity(retained._encoded(claim)), "output_commit": revision,
                    "output_objects": objects, "completion": summary, "publication_acknowledged": True}
                result["stage"] = "terminal"
                result["terminal_commit"] = retained._commit(api, repo, revision, TERMINAL, terminal, cache, token, deadline)
                retained._objects(api, repo, result["terminal_commit"], objects, token, deadline, written_at=revision)
                retained._objects(api, repo, result["terminal_commit"],
                    [retained._object(CLAIM, retained._encoded(claim))], token, deadline, written_at=parent)
                observed = verify_terminal(api, repo, result["terminal_commit"], self.document,
                    _cache(host, "terminal-readback"), token, deadline)
                same("retention_terminal_readback_changed", observed["completion"], summary)
                result.update(outcome="acknowledged", stage="terminal_verified")
        except (Exception, KeyboardInterrupt) as error:
            result["reason"] = str(error) if isinstance(error, RetentionCIRefused) else output._error_context(error)[0]
        retained._write(host / "remote-terminal-receipt.json", result)
        require(result["outcome"] == "acknowledged", "retention_terminal_unresolved:" + str(result["reason"]))
        return result


def execute(request: controller.Request, *, host_state: Path, grant: ExecutionGrantRequest | None,
            _test_transport=None, _test_api=None):
    # No construction, reservation or clock can precede these real checks.
    controller._context(request)
    require(type(grant) is ExecutionGrantRequest, "retention_execution_grant_required")
    require(output._hash(grant.request_sha256), "exact_retention_request_digest_required")
    document, observation = canonical_request(request, reviewed_source_sha=grant.reviewed_source_sha,
        run_id=os.environ.get("GITHUB_RUN_ID", ""), historical_root=grant.historical_root)
    same("approved_retention_request_changed", owned._digest(document), grant.request_sha256)
    transport = LocalTransport() if _test_transport is None else _test_transport
    require(isinstance(transport, LocalTransport) and type(transport).child is owned.LocalTransport.child,
            "retention_owned_child_transport_required")
    authority = verify_approval(document, transport)
    require_runtime(document, request, transport)
    admission = _Admission(request, document, observation, authority, transport, _test_api)
    state = controller._run_post_authority_cell(request, host_state=host_state, _admission=admission)
    with retained._lock(Path(host_state)):
        terminal = admission.finish(Path(host_state), state)
    return {"cell_id": request.cell_id, "status": state["status"], "request_sha256": grant.request_sha256,
            "cleanup_confirmed": True, "remote_terminal": terminal["outcome"],
            "grade": None, "grading_launched": False, "invoice_complete": False}


def _cli_request(args):
    original = preparation._path(args.original_root)
    return controller.Request(controller.FIRST_CELL_ID, preparation.PreparedInputs(
        preparation._path(args.historical_root), original / "original.parquet",
        original / "reference-only", original / "step0-manifest.json"), ROOT / PACKET_ROLE, ROOT,
        preparation.source_identity()["sha256"], controller.source_identity()["sha256"])


def main(argv=None):
    parser = output._Parser(description=__doc__)
    parser.add_argument("--reviewed-source-sha", required=True)
    parser.add_argument("--cell", default=controller.FIRST_CELL_ID)
    parser.add_argument("--historical-root", type=Path)
    parser.add_argument("--original-root", type=Path)
    parser.add_argument("--request-sha256")
    parser.add_argument("--request-out", type=Path)
    parser.add_argument("--host-state", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--verify-approval", action="store_true")
    mode.add_argument("--execute", action="store_true")
    try:
        args = parser.parse_args(argv)
        require(args.cell == controller.FIRST_CELL_ID, "only_registered_ordinal_zero_supported")
        source = require_source(args.reviewed_source_sha)
        registration.compile_plan()
        if not (args.prepare or args.verify_approval or args.execute):
            print(owned._canonical_json({"mode": "plan_only", "source": source, "scope": SCOPE,
                "commands": [], "launch_authorized": False, "transfer_attempted": False}))
            return 0
        require(args.historical_root is not None and args.original_root is not None, "explicit_prepared_originals_required")
        request = _cli_request(args)
        if args.prepare:
            preparation.prepare_packet(cell_id=request.cell_id, sources=request.sources, output=request.packet,
                                       expected_preparer_sha256=request.expected_preparer_sha256)
            controller.stage_runtime(request)
            document, _ = canonical_request(request, reviewed_source_sha=args.reviewed_source_sha,
                run_id=os.environ.get("GITHUB_RUN_ID", ""), historical_root=args.historical_root)
            require(args.request_out is not None, "explicit_request_record_required")
            destination = preparation._path(args.request_out)
            with _publication_parents(destination.parent) as (_, _, directory_fd):
                _write_no_clobber(destination, retained._encoded(document), parent_fd=directory_fd(destination.parent))
            print(owned._canonical_json({"mode": "prepared_not_admitted", "request_sha256": owned._digest(document),
                "launch_authorized": False, "source_sha": args.reviewed_source_sha, "scope": SCOPE,
                "materialized_grader_source_sha256": document["grading"]["materialized_grader_source_sha256"]}))
        elif args.verify_approval:
            document, _ = canonical_request(request, reviewed_source_sha=args.reviewed_source_sha,
                run_id=os.environ.get("GITHUB_RUN_ID", ""), historical_root=args.historical_root)
            same("approved_retention_request_changed", owned._digest(document), args.request_sha256)
            verify_approval(document, LocalTransport())
            print(owned._canonical_json({"approval_verified": True, "admission_attempted": False,
                                        "request_sha256": args.request_sha256}))
        else:
            require(args.host_state is not None, "explicit_host_state_required")
            result = controller.execute_first_cell(request, host_state=args.host_state, grant=ExecutionGrantRequest(
                args.reviewed_source_sha, args.request_sha256, args.historical_root))
            print(owned._canonical_json(result))
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        reason = str(error) if isinstance(error, (RetentionCIRefused, controller.RetentionControllerRefused,
            preparation.RetentionPreparationRefused, registration.RetentionRegistrationRefused,
            historical.HistoricalSourceRefused)) else "retention_ci_verification_refused:" + type(error).__name__
        print(owned._canonical_json({"reason": reason, "launch_authorized": False, "grading_launched": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
