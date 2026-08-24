"""Static contract for the purpose-built grading image and its build workflow.

The image exists to stop the renderer moving under the judge, so the things
worth testing without Docker are the ones that would let it move anyway: a
version restated instead of derived, a floating base, a floating published
tag, a package source trusted without checking who signed it -- or a grading
job that reaches for something the image does not carry.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import yaml

from scripts import preflight_grading_renderer as preflight


REPO_ROOT = Path(__file__).resolve().parents[2]
BATCH_RUNNER = REPO_ROOT / "batch-runner"
DOCKERFILE_PATH = REPO_ROOT / "batch-runner/sandbox/grading.Dockerfile"
BUILD_WORKFLOW_PATH = REPO_ROOT / ".github/workflows/build-grading-image.yml"
GRADE_WORKFLOW_PATH = REPO_ROOT / ".github/workflows/grade-run.yml"

GRADING_JOBS = ("grade", "grade-dry-run")

# The renderer packages the grade job used to apt-install on every run. They
# moved into the image; this is the list that moved, kept here so the image
# losing one of them is a test failure rather than a rendering difference
# discovered halfway through a paid corpus.
RENDERER_PACKAGES = frozenset({
    "libreoffice-core",
    "libreoffice-calc",
    "libreoffice-impress",
    "libreoffice-writer",
    "fonts-dejavu-core",
    "fonts-liberation2",
    "fontconfig",
})

# Every external binary the grading path may shell out to, and what makes it
# safe. Discovered by walking step8_grade.py's import closure; see
# test_grading_path_shells_out_only_to_known_binaries for how it is enforced.
ALLOWED_SHELL_OUTS = {
    "soffice": "libreoffice-core; asserted by the image build and the preflight",
    "libreoffice": "same package -- _find_soffice tries this name second",
    "ffprobe": (
        "NOT in the image. core/file_reader.py uses it to add a duration and "
        "codec line for .wav/.mp3/.mp4 deliverables and falls back to name "
        "and size without it. Every deliverable recorded in data/grades is "
        ".pdf/.xlsx/.pptx/.docx/.png, so the published corpus never reaches "
        "it -- but the fallback is silent and moves neither "
        "grader_source_hash nor renderer_fingerprint, so it is named here "
        "rather than left to be noticed."
    ),
}

PINNED_ACTION = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
PINNED_IMAGE = re.compile(
    r"^ghcr\.io/hyeonsangjeon/gdpval-grading@sha256:[0-9a-f]{64}$"
)


def _dockerfile() -> str:
    return DOCKERFILE_PATH.read_text(encoding="utf-8")


def _dockerfile_instructions() -> str:
    """The Dockerfile with comments dropped — what actually runs."""
    return "\n".join(
        line
        for line in _dockerfile().splitlines()
        if not line.lstrip().startswith("#")
    )


def _workflow(path: Path) -> dict:
    parsed = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(parsed, dict)
    return parsed


def _apt_packages(shell_text: str) -> set[str]:
    """Collect package names from every ``apt-get install`` in a snippet."""
    joined = " ".join(
        line.strip().rstrip("\\").strip() for line in shell_text.splitlines()
    )
    packages: set[str] = set()
    for segment in re.split(r"(?:&&|\|\||;)", joined):
        tokens = segment.split()
        if "install" not in tokens:
            continue
        if not any(token.endswith("apt-get") for token in tokens):
            continue
        for token in tokens[tokens.index("install") + 1:]:
            if token.startswith("-"):
                continue
            if re.fullmatch(r"[a-z0-9][a-z0-9+.-]*", token):
                packages.add(token)
    return packages


def _run_scripts(job: dict) -> list[tuple[str, str]]:
    return [
        (step.get("name", "<unnamed>"), step["run"])
        for step in job["steps"]
        if "run" in step
    ]



def test_expected_renderer_version_is_derived_from_the_preflight_pin():
    # One source of truth. A second copy is how a renderer upgrade lands in
    # the image while the preflight still asserts the old build, which is a
    # failure that only shows up after a paid run has already been graded.
    match = re.search(
        r'^ARG EXPECTED_LIBREOFFICE_VERSION="(?P<value>[^"]+)"$',
        _dockerfile(),
        re.MULTILINE,
    )
    assert match is not None
    assert match.group("value") == preflight.EXPECTED_LIBREOFFICE_VERSION


def test_image_carries_the_renderer_packages_the_jobs_stopped_installing():
    # The grade job used to apt-install these on every run, which is how a
    # mirror outage cost 63 tasks and five hours on 2026-08-19, and how the
    # renderer could differ between two runs with identical inputs. Dropping
    # one from the image now would reintroduce the second failure quietly:
    # LibreOffice converts a .pptx without libreoffice-impress installed, just
    # not the same way.
    image_packages = _apt_packages(_dockerfile_instructions())

    assert RENDERER_PACKAGES <= image_packages, sorted(
        RENDERER_PACKAGES - image_packages
    )


def test_grading_jobs_run_in_the_published_image_by_digest():
    grade = _workflow(GRADE_WORKFLOW_PATH)
    images = set()

    for name in GRADING_JOBS:
        job = grade["jobs"][name]
        container = job.get("container")
        assert container is not None, f"{name} is not containerised"
        # A tag would let a rebuild change the renderer under a job whose file
        # never changed, which is the whole failure the image exists to close.
        assert PINNED_IMAGE.fullmatch(container["image"]), container["image"]
        # The package is public. A credentials block would hand a registry
        # token to a job with no use for one.
        assert "credentials" not in container, name
        images.add(container["image"])

    # A dry run against a different renderer than the paid run proves nothing
    # about the paid run.
    assert len(images) == 1, sorted(images)


def test_grading_jobs_run_their_steps_under_bash():
    """A container job defaults `run:` to sh, and these steps are bash.

    Found by the free 2026-08-24 rehearsal, which died on the first step with
    ``set: Illegal option -o pipefail``. The dry run fails cheaply; the paid
    job would not have, because Run grading, Commit grade result, Merge shards
    and both analysis steps use ``[[ ]]`` or arrays and all run after the
    corpus has been judged and paid for.

    ``bash -e {0}`` and not the ``shell: bash`` shorthand: the shorthand
    expands to ``bash --noprofile --norc -eo pipefail {0}``, which would add
    pipefail to steps that were graded without it.
    """
    grade = _workflow(GRADE_WORKFLOW_PATH)

    for name in GRADING_JOBS:
        job = grade["jobs"][name]
        assert job.get("defaults", {}).get("run", {}).get("shell") == "bash -e {0}", name

        # And the default has to actually cover the steps that need it: a
        # per-step `shell:` that is not bash would slip past the job default.
        for step in job["steps"]:
            if "run" not in step:
                continue
            shell = step.get("shell")
            assert shell is None or shell.startswith("bash"), (name, step.get("name"))


def test_grading_jobs_declare_the_image_os_setup_python_reads():
    # The runner exports ImageOS for its own image and not for a container, so
    # without this actions/setup-python cannot tell which prebuilt CPython
    # applies. LANG matches what the hosted runner exports, keeping Python's
    # default encoding identical to what the published corpus was graded under.
    grade = _workflow(GRADE_WORKFLOW_PATH)

    for name in GRADING_JOBS:
        env = grade["jobs"][name]["env"]
        assert env.get("ImageOS") == "ubuntu24", name
        assert env.get("LANG") == "C.UTF-8", name


def test_grading_jobs_verify_the_image_before_spending_anything():
    grade = _workflow(GRADE_WORKFLOW_PATH)
    asserted = {}

    for name in GRADING_JOBS:
        steps = grade["jobs"][name]["steps"]
        # First step, so a wrong image costs seconds rather than a checkout, a
        # dependency install and an Azure login.
        assert steps[0]["name"] == "Verify grading container", name
        script = steps[0]["run"]
        assert "/opt/gdpval/renderer-version.txt" in script
        binaries = re.search(r"for binary in ([^;\n]+); do", script)
        assert binaries is not None, name
        asserted[name] = set(binaries.group(1).split())
        assert {"soffice", "fc-match", "git", "curl"} <= asserted[name], name

    # Only the paid job logs in to Azure, so only it needs to prove az exists.
    assert "az" in asserted["grade"]
    assert "az" not in asserted["grade-dry-run"]


def test_no_grading_job_installs_the_renderer_at_runtime():
    # apt in the grade job was both the outage and the drift: these packages
    # carry no version, so whichever LibreOffice the mirror served that day
    # became the judge's eyes. Reintroducing an install here would silently
    # reintroduce both.
    text = GRADE_WORKFLOW_PATH.read_text(encoding="utf-8")
    grade = _workflow(GRADE_WORKFLOW_PATH)

    for name in GRADING_JOBS:
        for step_name, script in _run_scripts(grade["jobs"][name]):
            assert "apt-get" not in script, (name, step_name)
            assert "sudo" not in script, (name, step_name)

    # Belt and braces: the prose above the jobs is allowed to describe the
    # history, but nothing anywhere in the file may run apt.
    assert "apt-get install" not in text


def test_the_dry_run_exercises_the_renderer_it_is_rehearsing():
    # dry_run == true and dry_run == false select different jobs, so the paid
    # job's preflight never runs on a free rehearsal. Without an unconditional
    # copy here, no free run touches the container's renderer at all and the
    # rehearsal certifies nothing about the thing that changed.
    grade = _workflow(GRADE_WORKFLOW_PATH)
    dry_run = grade["jobs"]["grade-dry-run"]

    preflight_step = next(
        step
        for step in dry_run["steps"]
        if step.get("name") == "Preflight grading renderer"
    )
    assert "if" not in preflight_step
    assert "preflight_grading_renderer.py" in preflight_step["run"]

    # On the paid path it stays gated on the config actually needing the
    # renderer -- containerising must not change what the paid run does.
    paid_preflight = next(
        step
        for step in grade["jobs"]["grade"]["steps"]
        if step.get("name") == "Preflight grading renderer"
    )
    assert paid_preflight["if"] == "steps.renderer.outputs.required == 'true'"


def test_no_containerised_job_reaches_for_gh():
    # gh is not in the image, and a `gh` call that only runs on the rc=7
    # handoff would fail after the chunk's budget was already spent. The
    # auto-resume step posts to the REST endpoint gh wraps, with curl.
    grade = _workflow(GRADE_WORKFLOW_PATH)

    for name in GRADING_JOBS:
        for step_name, script in _run_scripts(grade["jobs"][name]):
            # Whole-line comments are dropped first: the auto-resume step
            # explains in prose why it no longer calls gh, and a checker that
            # cannot tell an explanation from an invocation would force that
            # explanation to be deleted to stay green.
            body = "\n".join(
                line
                for line in script.splitlines()
                if not line.lstrip().startswith("#")
            )
            commands = re.findall(r"(?:^|[|&;(]|\$\()\s*(gh)\b", body, re.M)
            assert not commands, (name, step_name)

    retrigger = next(
        step
        for step in grade["jobs"]["grade"]["steps"]
        if step.get("name") == "Auto-retrigger next chunk (time budget hit)"
    )
    assert "actions/workflows/grade-run.yml/dispatches" in retrigger["run"]
    # --fail-with-body, not --fail: a 422 that explains itself is the
    # difference between a fixable dispatch and a stranded paid run.
    assert "--fail-with-body" in retrigger["run"]


def test_grading_path_shells_out_only_to_known_binaries():
    """Walk step8_grade.py's imports and check nothing new needs the host.

    Containerising moved the grading path onto a filesystem chosen on purpose,
    which is worth much more than the runner's -- and also much smaller. A new
    ``subprocess.run(["pdftotext", ...])`` on this path would not fail loudly;
    most of these call sites fall back, so it would change what the judge is
    shown while grader_source_hash and renderer_fingerprint both stay put.
    """
    reachable: set[Path] = set()
    queue = ["step8_grade"]
    seen: set[str] = set()

    def resolve(module: str) -> Path | None:
        relative = module.replace(".", "/")
        for candidate in (
            BATCH_RUNNER / f"{relative}.py",
            BATCH_RUNNER / relative / "__init__.py",
        ):
            if candidate.is_file():
                return candidate
        return None

    def absolute(module: str, node: ast.ImportFrom) -> str | None:
        """Turn a possibly-relative ImportFrom into a dotted module name.

        core/tools/__init__.py reaches read_deliverable with `from
        .read_deliverable import ...`, so a walker that only understood
        absolute imports would stop one file short of the renderer.
        """
        if not node.level:
            return node.module
        package = module if resolve(module).name == "__init__.py" else module.rsplit(".", 1)[0]
        parts = package.split(".")
        if node.level > 1:
            parts = parts[: -(node.level - 1)]
        if not parts:
            return node.module
        return ".".join(parts + ([node.module] if node.module else []))

    while queue:
        module = queue.pop()
        if module in seen:
            continue
        seen.add(module)
        path = resolve(module)
        if path is None:
            continue
        reachable.add(path)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                queue.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                target = absolute(module, node)
                if not target:
                    continue
                queue.append(target)
                # `from core.tools import read_deliverable` names a module,
                # not an attribute, and that module is where soffice is
                # resolved. Following only the package would walk past the
                # single most important file on this path.
                queue.extend(f"{target}.{alias.name}" for alias in node.names)

    assert len(reachable) > 10, "import walk collapsed; the check would be vacuous"

    found: dict[str, Path] = {}
    for path in sorted(reachable):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            names: list[ast.expr] = []
            target = node.func
            if isinstance(target, ast.Attribute) and target.attr == "which":
                names.extend(node.args[:1])
            elif isinstance(target, ast.Attribute) and target.attr in {
                "run",
                "Popen",
                "check_output",
                "check_call",
                "call",
            }:
                if node.args and isinstance(node.args[0], (ast.List, ast.Tuple)):
                    names.extend(node.args[0].elts[:1])
            for name in names:
                if isinstance(name, ast.Constant) and isinstance(name.value, str):
                    found.setdefault(name.value, path)

    # _find_soffice resolves its binary through a loop variable, so the walk
    # above cannot see the name. It is the reason the image exists, so assert
    # it directly rather than widening the scanner for one call site.
    soffice = BATCH_RUNNER / "core/tools/read_deliverable.py"
    assert soffice in reachable
    assert 'for executable in ("soffice", "libreoffice"):' in soffice.read_text(
        encoding="utf-8"
    )

    unexpected = {
        name: str(path.relative_to(REPO_ROOT))
        for name, path in found.items()
        if name not in ALLOWED_SHELL_OUTS
    }
    assert not unexpected, (
        "new external binary on the grading path; confirm the image carries it "
        f"and add it to ALLOWED_SHELL_OUTS: {unexpected}"
    )
    assert "ffprobe" in found, (
        "ffprobe left the grading path -- drop it from ALLOWED_SHELL_OUTS and "
        "from the container note in grade-run.yml"
    )


def test_image_carries_the_actions_runtime_the_grade_job_needs():
    # Without git, actions/checkout falls back to a REST tarball with no .git
    # and the grade job's own checkout verification fails; without az,
    # azure/login cannot complete the OIDC exchange.
    image_packages = _apt_packages(_dockerfile_instructions())

    assert {"git", "curl", "ca-certificates", "azure-cli"} <= image_packages


def test_base_image_is_digest_pinned_to_ubuntu_2404():
    # ubuntu:24.04 is where the 24.2.7.2 renderer comes from; the digest is
    # what stops a rebuild picking up a later one.
    from_lines = [
        line.strip()
        for line in _dockerfile().splitlines()
        if line.startswith("FROM ")
    ]

    assert len(from_lines) == 1
    assert re.fullmatch(r"FROM ubuntu:24\.04@sha256:[0-9a-f]{64}", from_lines[0])


def test_build_asserts_the_renderer_rather_than_reporting_it():
    text = _dockerfile()

    assert 'actual="$(soffice --headless --version)"' in text
    assert 'if [ "$actual" != "$EXPECTED_LIBREOFFICE_VERSION" ]; then' in text
    assert "/opt/gdpval/renderer-version.txt" in text
    assert "grep -qx 'Liberation Sans'" in text


def test_azure_cli_source_is_verified_before_it_is_trusted():
    text = _dockerfile()
    fingerprint = re.search(
        r'^ARG MICROSOFT_GPG_FINGERPRINT="(?P<value>[^"]+)"$', text, re.MULTILINE
    )

    assert fingerprint is not None
    assert re.fullmatch(r"[0-9A-F]{40}", fingerprint.group("value"))
    assert 'if [ "$actual" != "$MICROSOFT_GPG_FINGERPRINT" ]; then' in text
    assert "signed-by=/usr/share/keyrings/microsoft.gpg" in text
    # The documented install path for azure-cli is a redirect piped into a
    # root shell. Nothing that *runs* here may reintroduce it — the prose
    # above the RUN step is allowed to name it, which is why this reads the
    # instructions rather than the file.
    instructions = _dockerfile_instructions()
    assert "aka.ms" not in instructions
    assert not re.search(r"\|\s*(ba)?sh\b", instructions)


def test_build_workflow_verifies_on_pull_request_without_pushing():
    workflow = _workflow(BUILD_WORKFLOW_PATH)
    triggers = workflow["on"]

    assert set(triggers) == {"workflow_dispatch", "pull_request"}
    assert "batch-runner/sandbox/grading.Dockerfile" in triggers["pull_request"]["paths"]
    assert workflow["permissions"] == {"contents": "read"}

    verify = workflow["jobs"]["verify-grading-image"]
    assert verify["permissions"] == {"contents": "read"}
    build = next(
        step for step in verify["steps"] if step.get("name") == "Build grading image"
    )
    assert build["with"]["push"] == "false"
    assert build["with"]["file"] == "batch-runner/sandbox/grading.Dockerfile"


def test_publish_is_gated_and_pinned_by_digest_not_by_tag():
    workflow = _workflow(BUILD_WORKFLOW_PATH)
    publish = workflow["jobs"]["publish-grading-image"]

    assert publish["permissions"] == {"contents": "read", "packages": "write"}
    for guard in (
        "inputs.publish == true",
        "github.ref == 'refs/heads/main'",
    ):
        assert guard in publish["if"]

    build = next(
        step
        for step in publish["steps"]
        if step.get("name") == "Build and push grading image"
    )
    tags = build["with"]["tags"]
    # A moving :latest would let the renderer change under a grade job that
    # never changed, which is the whole failure this image exists to remove.
    assert ":latest" not in tags
    assert "${{ github.sha }}" in tags


def test_publish_is_gated_by_an_environment_that_only_main_can_reach():
    """The approval gate is the environment, so the wiring has to hold.

    This job used to gate on ``github.ref_protected``. main carries no branch
    protection here on purpose -- grade-run.yml pushes grade files straight to
    it from up to nine concurrent shards -- so that condition was never true
    and the job skipped silently on every dispatch. Silently is the problem:
    the run went green having published nothing.

    grading-image-publish replaces it with a required reviewer and a
    deployment branch policy naming main and nothing else, both enforced
    before a runner is handed out. That is a repository setting this file
    cannot read, so what it locks instead is the half that lives in the repo:
    the job still asks for the environment, still refuses any ref but main,
    and is still the only job holding the credential that can write to GHCR.
    """
    workflow = _workflow(BUILD_WORKFLOW_PATH)
    publish = workflow["jobs"]["publish-grading-image"]

    assert publish["environment"] == {"name": "grading-image-publish"}

    # Dropping the environment while keeping the conditions would publish on
    # dispatch with no human in the loop, which is exactly what the owner
    # declined when they declined relaxing the guard outright.
    condition = " ".join(publish["if"].split())
    assert "github.event_name == 'workflow_dispatch'" in condition
    assert "inputs.publish == true" in condition
    assert "github.ref == 'refs/heads/main'" in condition

    # The environment's branch policy enforces main, and so does the job. Both
    # only because a branch policy is edited in a settings page nobody reviews
    # in a diff; the condition is the copy that travels with the code.
    assert "github.ref_protected" not in condition
    verify_checkout = next(
        step for step in publish["steps"] if step.get("name") == "Verify main checkout"
    )
    assert 'test "$GITHUB_REF" = "refs/heads/main"' in verify_checkout["run"]
    assert "GITHUB_REF_PROTECTED" not in verify_checkout["run"]

    # packages: write belongs to the approved job alone. Granting it at the
    # top level, or to the unapproved verify job, would hand the token that
    # can push to a public registry to a run nobody approved.
    assert workflow["permissions"] == {"contents": "read"}
    for name, job in workflow["jobs"].items():
        has_packages = "packages" in (job.get("permissions") or {})
        assert has_packages == (name == "publish-grading-image"), name
        if name != "publish-grading-image":
            assert "environment" not in job, name


def test_every_action_in_the_build_workflow_is_sha_pinned():
    workflow = _workflow(BUILD_WORKFLOW_PATH)
    uses = [
        step["uses"]
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if "uses" in step
    ]

    assert uses
    unpinned = [reference for reference in uses if not PINNED_ACTION.fullmatch(reference)]
    assert not unpinned, unpinned
