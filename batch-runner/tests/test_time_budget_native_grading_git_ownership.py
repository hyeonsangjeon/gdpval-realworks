"""One tiny real-Git proof; simulated foreign ownership is not a host claim."""

import hashlib
import json
from pathlib import Path
import subprocess

import pytest
import yaml

import gpt54_disposable_checkout as checkout
import gpt54_time_budget_comparison as registration
import gpt54_time_budget_native_grading_ci as controller
from .test_gpt54_disposable_checkout import _FIXTURE_ENV, _GIT_ENV


ROOT = Path(__file__).resolve().parents[2]
_REAL_RUN = subprocess.run


def test_native_task3_grading_git_ownership(tmp_path, monkeypatch, record_property):
    """Keep real Git/registration checks; substitute only tiny source anchors."""
    workflow = yaml.safe_load((ROOT / controller.WORKFLOW).read_text())
    job = workflow["jobs"][controller.JOB]
    step = next(item for item in job["steps"]
                if item["name"] == "Verify ordinary bootstrap and create separate linked C, original R and frozen F")
    block = step["run"]
    trust = 'export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$GITHUB_WORKSPACE"'
    assert block.splitlines()[0] == ('[[ "$(pwd -P)" == "$GITHUB_WORKSPACE" && '
                                    '-d "$GITHUB_WORKSPACE/.git" && ! -L "$GITHUB_WORKSPACE/.git" ]]')
    assert block.splitlines()[2] == trust
    assert block.count("safe.directory") == 1 and "--global" not in block
    assert step["timeout-minutes"] == 1 and job["timeout-minutes"] == 270
    assert sum(item["timeout-minutes"] for item in job["steps"]) == 269
    assert controller._git is checkout._git and controller._repository is checkout._repository
    assert controller._registered_gitdir is checkout._registered_gitdir
    assert hashlib.sha256((ROOT / "batch-runner/gpt54_disposable_checkout.py").read_bytes()).hexdigest() == (
        "77d6d1957f123b7f32d710be7ffddbd99f6043e00b0313bc7b1cc9802975fa62"
    )

    bootstrap, unrelated = tmp_path / "ordinary-bootstrap", tmp_path / "unrelated-repository"
    temporary, github_env = tmp_path / "runner-temp", tmp_path / "github-env"
    temporary.mkdir(mode=0o700)
    github_env.touch(mode=0o600)
    role = "batch-runner/ownership-source.txt"
    evidence = {"ownership_seam": "GIT_TEST_ASSUME_DIFFERENT_OWNER=1; synthetic, not live UID evidence",
                "source_substitution": "Three tiny fixture commits/trees replace C/R/F anchors only in extracted Bash",
                "bootstrap": str(bootstrap), "unrelated": str(unrelated), "git_calls": [], "guards": {}}
    receipt = tmp_path / "ownership-receipt.json"

    def save():
        receipt.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n")

    def local(command, *, cwd=None, env=_FIXTURE_ENV):
        return _REAL_RUN(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                         capture_output=True, timeout=30, check=False)

    def git(repository, *args):
        assert repository.is_relative_to(tmp_path)
        result = local(["/usr/bin/git", "-C", str(repository), *args])
        assert result.returncode == 0, result.stderr.decode()
        return result.stdout.decode().strip()

    for repository in (bootstrap, unrelated):
        repository.mkdir()
        git(repository, "init", "--quiet", "--initial-branch=fixture-main", "--object-format=sha1", "--template=")
        (repository / "batch-runner/core").mkdir(parents=True)
        (repository / "batch-runner/core/ownership.py").write_text('SYNTHETIC = True\n')
        (repository / role).write_text("synthetic frozen source\n")
        git(repository, "add", "--", ".")
        git(repository, "commit", "--quiet", "-m", "Synthetic frozen source")
    frozen = (git(bootstrap, "rev-parse", "HEAD"), git(bootstrap, "rev-parse", "HEAD^{tree}"))
    anchors = {"frozen_root": frozen}
    for name in ("runtime_root", "controller_root"):
        (bootstrap / role).write_text("synthetic " + name + "\n")
        git(bootstrap, "add", "--", role)
        git(bootstrap, "commit", "--quiet", "-m", "Synthetic " + name)
        anchors[name] = (git(bootstrap, "rev-parse", "HEAD"), git(bootstrap, "rev-parse", "HEAD^{tree}"))
    configs = {path: (path / ".git/config").read_bytes() for path in (bootstrap, unrelated)}
    branches = {path: git(path, "show-ref") for path in (bootstrap, unrelated)}
    environment = {**_FIXTURE_ENV, "GITHUB_WORKSPACE": str(bootstrap), "RUNNER_TEMP": str(temporary),
                   "CONTROLLER_SHA": anchors["controller_root"][0], "CONTROLLER_TREE": anchors["controller_root"][1],
                   "GITHUB_ENV": str(github_env), "GIT_TEST_ASSUME_DIFFERENT_OWNER": "1"}
    before = local(["/usr/bin/git", "-C", str(bootstrap), "rev-parse", "HEAD"], env=environment)
    evidence["original_refusal"] = {"exit": before.returncode, "stderr": before.stderr.decode()}
    save()
    assert before.returncode == 128 and b"detected dubious ownership" in before.stderr

    # No synthetic source SHA is presented as an original R/F or live C anchor.
    for old, new in zip((controller.RETAINED["source"]["sha"], controller.RETAINED["source"]["tree"],
                         registration.ACCEPTED_BASE_SHA, registration.ACCEPTED_BASE_TREE),
                        (*anchors["runtime_root"], *anchors["frozen_root"])):
        assert old in block
        block = block.replace(old, new)
    evidence["synthetic_anchors"] = anchors

    def bash(script=block, env=environment):
        return local(["/bin/bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", script],
                     cwd=bootstrap, env=env)

    for label, env, script in (
        ("physical_path", {**environment, "GITHUB_WORKSPACE": str(unrelated)}, block),
        ("C_head", {**environment, "CONTROLLER_SHA": "0" * 40}, block),
        ("C_tree", {**environment, "CONTROLLER_TREE": "0" * 40}, block),
        ("R_tree", environment, block.replace(anchors["runtime_root"][1], "0" * 40)),
        ("F_tree", environment, block.replace(anchors["frozen_root"][1], "0" * 40)),
    ):
        refused = bash(script, env)
        evidence["guards"][label] = {"exit": refused.returncode, "stderr": refused.stderr.decode()}
        save()
        assert refused.returncode == 1 and list(temporary.iterdir()) == [], (label, refused.stderr)
    created = bash()
    evidence["corrected_workflow"] = {"exit": created.returncode, "stderr": created.stderr.decode()}
    save()
    assert created.returncode == 0, created.stderr.decode()
    roots = {key: temporary / value for key, value in controller.ROOT_NAMES.items()}
    assert github_env.read_text() == "AZURE_CONFIG_DIR=" + str(roots["login_root"]) + "\n"
    assert roots["login_root"].stat().st_mode & 0o777 == 0o700
    assert not roots["state_root"].exists()
    occupied = bash()
    evidence["guards"]["occupied_destination"] = {"exit": occupied.returncode, "stderr": occupied.stderr.decode()}
    save()
    assert occupied.returncode == 1
    unrelated_result = local(["/usr/bin/git", "-C", str(unrelated), "rev-parse", "HEAD"],
        env={**environment, "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "safe.directory",
             "GIT_CONFIG_VALUE_0": str(bootstrap)})
    evidence["unrelated_workflow_scope"] = {"exit": unrelated_result.returncode, "stderr": unrelated_result.stderr.decode()}
    save()
    assert unrelated_result.returncode == 128 and b"detected dubious ownership" in unrelated_result.stderr

    # The imported production helper normally discovers the linked C from its
    # own __file__. Bind that same role to this explicitly synthetic tiny C.
    monkeypatch.setattr(checkout, "TRUSTED_ROOT", roots["controller_root"])
    monkeypatch.setattr(controller, "__file__", str(roots["controller_root"] / controller.HELPER))
    evidence["controller_source_substitution"] = "Imported controller __file__ and shared code-root role name the tiny synthetic linked C"

    def real_source_git(command, **kwargs):
        assert command[:2] == ["/usr/bin/git", "--no-replace-objects"]
        position = command.index("-C")
        repository = Path(command[position + 1])
        assert repository in {bootstrap, unrelated, *(roots[key] for key in anchors)}
        assert kwargs["timeout"] == 60 and kwargs["env"] == _GIT_ENV
        allowances = [item for item in command if item.startswith("safe.directory=")]
        local_bootstrap_read = repository == bootstrap and command[position + 2] == "-c"
        if local_bootstrap_read:
            assert command[position + 2:position + 5] == ["-c", "safe.directory=" + str(bootstrap), "rev-parse"]
        assert allowances == (["safe.directory=" + str(repository)]
                              if local_bootstrap_read or repository == roots["controller_root"] else [])
        # Only the ordinary bootstrap and unrelated refusal probe are foreign
        # in this seam. Newly created linked C/R/F remain owned, as real Git
        # created them; a global seam must not justify trusting all linked roots.
        if repository in {bootstrap, unrelated}:
            kwargs["env"] = {**kwargs["env"], "GIT_TEST_ASSUME_DIFFERENT_OWNER": "1"}
        kwargs["timeout"] = 30
        result = _REAL_RUN(command, **kwargs)
        evidence["git_calls"].append({"repository": str(repository), "args": command[position + 2:],
                                      "trust": allowances, "exit": result.returncode, "stderr": result.stderr.decode()})
        save()
        return result

    monkeypatch.setattr(subprocess, "run", real_source_git)
    with pytest.raises(checkout.DisposableCheckoutRefused, match="local Git rev-parse refused \\(128\\)"):
        checkout._repository(bootstrap)
    evidence["shared_helper_foreign_bootstrap"] = "still refuses without controller-local trust"
    assert controller._checked_bootstrap(bootstrap, *anchors["controller_root"]) == (bootstrap, bootstrap / ".git")
    for sha, tree in (("0" * 40, anchors["controller_root"][1]), (anchors["controller_root"][0], "0" * 40)):
        with pytest.raises(controller.NativeGradingCIRefused, match="bootstrap_identity_mismatch"):
            controller._checked_bootstrap(bootstrap, sha, tree)
    with pytest.raises(controller.NativeGradingCIRefused, match="bootstrap_not_controller_common"):
        controller._checked_bootstrap(unrelated, *anchors["controller_root"])
    evidence["validated_sources"] = {}
    for key, (sha, tree) in anchors.items():
        root = roots[key]
        assert checkout._repository(root) == (root, bootstrap / ".git")
        assert checkout._runtime_revision(root, sha, tree)[0] == bootstrap / ".git"
        assert checkout._git(root, "symbolic-ref", "--quiet", "HEAD", ok=(0, 1)).returncode == 1
        with registration._reviewed_source(root, sha, {role}) as (actual, actual_tree, identities):
            assert actual == root and actual_tree == tree
            assert identities[role] == {"size": (root / role).stat().st_size,
                                       "sha256": hashlib.sha256((root / role).read_bytes()).hexdigest()}
        evidence["validated_sources"][key] = {"path": str(root), "sha": sha, "tree": tree, "detached": True}
        save()
    with pytest.raises(checkout.DisposableCheckoutRefused, match="local Git rev-parse refused \\(128\\)"):
        checkout._repository(unrelated)
    assert evidence["git_calls"][-1]["repository"] == str(unrelated)
    assert "detected dubious ownership" in evidence["git_calls"][-1]["stderr"]
    with pytest.raises(checkout.DisposableCheckoutRefused):
        checkout._runtime_revision(roots["controller_root"], anchors["controller_root"][0], "0" * 40)
    with pytest.raises(checkout.DisposableCheckoutRefused):
        with registration._reviewed_source(roots["controller_root"], anchors["runtime_root"][0], {role}):
            pytest.fail("wrong source commit was accepted")
    _, gitdir = checkout._runtime_revision(roots["controller_root"], *anchors["controller_root"])
    backlink = gitdir / "gitdir"
    original_backlink = backlink.read_bytes()
    try:
        backlink.write_text(str(unrelated / ".git") + "\n")
        with pytest.raises(checkout.DisposableCheckoutRefused, match="detached checkout registration mismatch"):
            controller._checked_bootstrap(bootstrap, *anchors["controller_root"])
        evidence["reciprocal_registration_tamper"] = "refused before granting bootstrap trust"
    finally:
        backlink.write_bytes(original_backlink)
    for repository in (bootstrap, unrelated):
        assert (repository / ".git/config").read_bytes() == configs[repository]
        assert git(repository, "show-ref") == branches[repository]
    assert "GIT_CONFIG" not in github_env.read_text()
    evidence["outcome"] = "real Git refusal; controller-local bootstrap trust; pinned shared helper unchanged; linked C/R/F source checks; unrelated refusal; unchanged config/refs"
    save()
    record_property("ownership_receipt", str(receipt))
    record_property("ownership_receipt_sha256", hashlib.sha256(receipt.read_bytes()).hexdigest())
    record_property("bounded_outcome", evidence["outcome"])
