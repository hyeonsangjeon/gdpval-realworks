"""The workflow that grades a run can be handed a config kept in a directory.

The run-place comparison keeps its three experiment configs in one directory::

    batch-runner/experiments/execution_envelope/exp030_envelope_host_python_process.yaml
    batch-runner/experiments/execution_envelope/exp031_envelope_docker_container.yaml
    batch-runner/experiments/execution_envelope/exp032_envelope_azure_code_interpreter.yaml

``batch-run.yml`` was taught to take that name. ``grade-run.yml`` was not, and
grading is where the comparison's numbers come from -- so all three could be
run and none could be scored. Its check admitted no separator at all, and the
five-task advance check never noticed because an advance check does not grade.

**Refusing the name early was not the only thing in the way.** Two steps past
that check, the name is a *file*: ``resolve_grade_output_path`` builds the
grade filename from it and then refuses anything that is not a single path
component -- and it refuses it after the corpus has been judged and paid for.
Two steps past that, the ``grade`` job uploads two artifacts named after it,
and a GitHub artifact name may not contain a separator either. Loosening only
the first check would have moved the failure downstream of the money.

So the rule is one rule, stated once: the name may reach one directory deep,
and wherever it has to become a single component -- the grade filename, the
shard directory beneath it, the two artifact names -- the separator becomes
``__``. That flattening has to be injective, because ``grade-run.yml`` inherits
a paid approval by matching the flattened stem: two names collapsing onto one
would hand one experiment's approval to another. It is injective only while no
name carries ``__`` of its own, which is why both halves refuse one that does.

These tests hold the two halves together. They type neither the names nor the
rule: the names come from the plan and from the files on disk, the rule is read
back out of the workflow and cross-checked against real bash, and the filename
is built by the real ``resolve_grade_output_path``.

Nothing here calls a model, grades anything, or spends anything.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from step8_grade import (
    EXPERIMENT_PATH_SEPARATOR_SLUG,
    _experiment_path_slug,
    resolve_grade_output_path,
)

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BATCH_RUNNER_ROOT.parent
WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "grade-run.yml"
EXPERIMENTS_ROOT = BATCH_RUNNER_ROOT / "experiments"
PLAN_PATH = EXPERIMENTS_ROOT / "execution_envelope" / "advance_check_plan.yaml"

# The grading config the paid run uses. Its filename template is read rather
# than invented, so the end-to-end check below builds the real filename.
GRADING_CONFIG_PATH = BATCH_RUNNER_ROOT / "grading_configs" / "default_v2_sol_max.yaml"

# Where the workflow's check on the name starts and stops. Reading between
# these is what keeps this file measuring the real rule instead of a copy of it.
CHECK_OPENS_AT = "if (( ${#GRADE_EXPERIMENT_YAML}"
CHECK_CLOSES_AT = 'echo "::error::experiment_yaml must be'

# The refusals the workflow spells out beside the pattern, as written. Each is
# asserted so that dropping one fails here rather than at a dispatch.
GUARDS_WRITTEN_BESIDE_THE_PATTERN = (
    '== *".."*',
    '== *"__"*',
    "== *. ||",
    "== *.lock",
    "== *.yaml",
    "== *.yml",
)

# How the workflow flattens the name where one component is needed.
SLUG_THE_WORKFLOW_COMPUTES = 'echo "experiment_slug=${GRADE_EXPERIMENT_YAML//\\//__}"'

# How the workflow turns an accepted name into a file to look for.
PATH_THE_WORKFLOW_BUILDS = 'EXPERIMENT_PATH="batch-runner/experiments/${GRADE_EXPERIMENT_YAML}.yaml"'

# A config the grader can be given, as against a plan that only describes one.
CONFIG_ROOT_KEY = "experiment"

# The identity fields `resolve_grade_output_path` insists on, none of which
# this file is about. Shaped like a real run's so the filename is a real one.
IDENTITY = {
    "judge_slug": "gpt-5_4",
    "config_hash": "0123456789abcdef",
    "rubric_sha": "a" * 40,
    "rubric_short_sha": "a" * 7,
    "prompt_version": "v2.2",
    "inference_sha": "b" * 40,
    "grader_source_hash": "c" * 64,
}

# Names one directory must not have brought in with it. Taking a separator is
# the whole change, so what a separator must still not buy is the whole risk.
# The first seventeen are the list `batch-run.yml`'s own tests hold it to, so
# the two workflows refuse the same things; the last two are this rule's own.
NAMES_IT_MUST_REFUSE = [
    ("../secrets", "climbs out of the experiments directory"),
    ("execution_envelope/../../secrets", "climbs out further along"),
    ("/etc/passwd", "starts at the root of the disk"),
    ("execution_envelope/deeper/exp030", "asks for a second directory"),
    (".hidden", "starts with a dot"),
    ("execution_envelope/.hidden", "starts a part with a dot"),
    ("-rf", "starts with a dash"),
    ("execution_envelope/-rf", "starts a part with a dash"),
    ("execution_envelope\\exp030", "separates with a backslash"),
    ("/exp030", "starts with the separator"),
    ("execution_envelope/", "stops at the separator"),
    ("", "is nothing at all"),
    ("exp030.", "ends with a dot"),
    ("exp030.lock", "ends with .lock"),
    ("exp 030", "has a space in it"),
    ("exp030;rm", "carries a second command"),
    ("exp030%2Fsecrets", "hides the separator"),
    ("exp030.yaml", "brings the extension the workflow adds"),
    ("execution_envelope__exp030", "collides with a flattened name"),
    ("exp030\n", "carries a newline into $GITHUB_OUTPUT"),
    (" exp030", "is padded with a space the file name would not have"),
]


def _read_the_check_out_of_the_workflow() -> str:
    """The workflow's own words for the rule, from the workflow."""
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    opens = text.find(CHECK_OPENS_AT)
    assert opens != -1, (
        f"{WORKFLOW_PATH.name} no longer contains {CHECK_OPENS_AT!r}, so this "
        "file cannot tell what it now accepts. Point it at the new check "
        "rather than deleting these tests."
    )
    closes = text.find(CHECK_CLOSES_AT, opens)
    assert closes != -1, (
        f"{WORKFLOW_PATH.name} checks the name but no longer refuses it with "
        f"{CHECK_CLOSES_AT!r}."
    )
    return text[opens:closes]


def _pattern_from(check: str) -> re.Pattern[str]:
    """Bash's extended regular expression, compiled by Python.

    The pattern sits unquoted after ``=~`` and runs to the ``]]`` that closes
    its test. Everything in it -- the character classes, the ``{0,99}`` counts,
    the optional group, ``^`` and ``$`` -- means the same thing to Python's
    ``re`` as to bash's POSIX matcher, so nothing is rewritten.
    ``test_bash_reaches_the_same_verdicts_as_the_reading_of_it_here`` checks
    that claim against the shell that really applies it.
    """
    found = re.search(r"=~\s*(?P<body>\S+)\s*\]\]", check)
    assert found, (
        "the check no longer holds a pattern this file can read; it said:\n"
        f"{check}"
    )
    return re.compile(found.group("body"))


def _length_bound_from(check: str) -> int:
    found = re.search(r">\s*(\d+)\s*\)\)", check)
    assert found, f"the check no longer bounds the name's length:\n{check}"
    return int(found.group(1))


@pytest.fixture(scope="module")
def check() -> str:
    return _read_the_check_out_of_the_workflow()


@pytest.fixture(scope="module")
def accepts(check: str):
    pattern = _pattern_from(check)
    longest = _length_bound_from(check)
    for guard in GUARDS_WRITTEN_BESIDE_THE_PATTERN:
        assert guard in check, (
            f"the check no longer refuses names with {guard}, so this file "
            "would stop measuring one of the rules it was written for"
        )

    def accepted(name: str) -> bool:
        return bool(
            1 <= len(name) <= longest
            # `fullmatch`, not `match`: Python's `$` also matches before a
            # trailing newline and bash's does not, and a newline in this name
            # would reach `$GITHUB_OUTPUT` if it ever got past here.
            and pattern.fullmatch(name)
            and ".." not in name
            and "__" not in name
            and not name.endswith((".", ".lock", ".yaml", ".yml"))
        )

    return accepted


@pytest.fixture(scope="module")
def plan() -> dict:
    return yaml.safe_load(PLAN_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def grading_config() -> dict:
    """A config shaped like the paid run's, with its real filename template."""
    real = yaml.safe_load(GRADING_CONFIG_PATH.read_text(encoding="utf-8"))
    return {
        "config_name": real["config_name"],
        "output": {
            "directory": "data/grades",
            "filename_template": real["output"]["filename_template"],
        },
    }


def _dispatch_name(path: Path) -> str:
    """The name the workflow would be given for a config on disk."""
    return path.relative_to(EXPERIMENTS_ROOT).with_suffix("").as_posix()


def _runnable_configs() -> list[Path]:
    return sorted(
        path
        for path in EXPERIMENTS_ROOT.rglob("*.yaml")
        if isinstance(
            (loaded := yaml.safe_load(path.read_text(encoding="utf-8"))), dict
        )
        and CONFIG_ROOT_KEY in loaded
    )


def _plan_names(plan: dict) -> list[str]:
    return [
        Path(written).relative_to("experiments").with_suffix("").as_posix()
        for written in plan["experiment_files"].values()
    ]


# ── What the workflow will now take ───────────────────────────────────────


def test_the_three_run_places_the_plan_names_can_be_graded(plan: dict, accepts) -> None:
    """The names come from the plan, so the plan is what is being checked."""
    named = plan["experiment_files"]
    assert set(named) == {
        "host_python_process",
        "docker_container",
        "azure_code_interpreter",
    }, named

    refused = {}
    for environment, written in named.items():
        name = Path(written).relative_to("experiments").with_suffix("").as_posix()
        assert (EXPERIMENTS_ROOT / f"{name}.yaml").is_file(), written
        if not accepts(name):
            refused[environment] = name

    assert refused == {}, (
        "the plan names these run places' configs, and the grading workflow "
        f"cannot be told to grade them: {refused}"
    )


def test_every_config_in_the_tree_can_be_graded(accepts) -> None:
    """The guard for the next directory somebody groups configs into."""
    configs = _runnable_configs()
    assert len(configs) > 30, "the sweep found almost nothing; check the filter"

    refused = [
        str(path.relative_to(EXPERIMENTS_ROOT))
        for path in configs
        if not accepts(_dispatch_name(path))
    ]
    assert refused == [], (
        "these experiment configs exist but the grading workflow cannot be "
        f"told to grade them: {', '.join(refused)}"
    )


def test_the_workflow_still_looks_for_the_name_under_the_experiments_directory(
    check: str,
) -> None:
    """One directory is safe only because that is all the name is joined onto.

    The pattern bounds how far a name can reach, and this is the other half of
    that: where it reaches from.
    """
    assert PATH_THE_WORKFLOW_BUILDS in WORKFLOW_PATH.read_text(encoding="utf-8")


@pytest.mark.parametrize("name, why", NAMES_IT_MUST_REFUSE)
def test_the_names_it_must_go_on_refusing(accepts, name: str, why: str) -> None:
    """Taking one directory took nothing else with it."""
    assert not accepts(name), f"a name that {why} is accepted: {name!r}"


def test_bash_reaches_the_same_verdicts_as_the_reading_of_it_here(
    check: str, accepts
) -> None:
    """The workflow's rule is bash's to apply, so let bash apply it.

    Everything else here reads that rule through a translation into Python, and
    a translation is a second copy of the thing it describes. The same names go
    through the real check in the real shell, and the two answers must match.

    The names are passed as arguments rather than on standard input, so the
    empty name survives the round trip and is compared like any other. A name
    carrying a newline cannot be compared this way -- it would print as two
    lines -- so those are checked one at a time below.
    """
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("no bash on this machine to compare the reading against")

    def rule(body: str) -> str:
        return "\n".join(
            [
                "set -uo pipefail",
                "accepted() {",
                '  GRADE_EXPERIMENT_YAML="$1"',
                "  " + "\n  ".join(line.strip() for line in check.strip().splitlines()),
                "    return 1",
                "  fi",
                "  return 0",
                "}",
                body,
            ]
        )

    names = [_dispatch_name(path) for path in _runnable_configs()]
    names += [name for name, _ in NAMES_IT_MUST_REFUSE]
    one_line = [name for name in names if "\n" not in name]

    finished = subprocess.run(
        [
            bash,
            "-c",
            rule(
                'for n in "$@"; do\n'
                '  if accepted "$n"; then printf "ACCEPT\\t%s\\n" "$n"\n'
                '  else printf "REJECT\\t%s\\n" "$n"; fi\n'
                "done"
            ),
            "compare-the-rule",
            *one_line,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert finished.returncode == 0, finished.stderr

    answered = finished.stdout.splitlines()
    assert len(answered) == len(one_line), finished.stdout

    disagreed = {}
    for line in answered:
        verdict, _, name = line.partition("\t")
        if (verdict == "ACCEPT") != accepts(name):
            disagreed[name] = f"bash says {verdict.lower()}"
    assert disagreed == {}, (
        "this file reads the workflow's rule differently from the shell that "
        f"applies it: {disagreed}"
    )

    for name in names:
        if "\n" not in name:
            continue
        verdict = subprocess.run(
            [bash, "-c", rule('accepted "$1"'), "compare-the-rule", name],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert (verdict.returncode == 0) == accepts(name), name


# ── That the two halves flatten the name the same way ─────────────────────


def test_the_workflow_and_step_8_flatten_the_separator_the_same_way(
    check: str, plan: dict
) -> None:
    """One rule, two places that have to agree on it.

    The workflow computes the slug for its artifact names and for the stem it
    matches a paid approval against; step 8 computes it for the grade filename.
    A disagreement would not fail anything -- it would upload one name and
    write another, and the approval would stop being inherited.
    """
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert SLUG_THE_WORKFLOW_COMPUTES in text, (
        "the workflow no longer computes the flattened name where this file "
        "can read how"
    )
    assert EXPERIMENT_PATH_SEPARATOR_SLUG == "__"

    for name in _plan_names(plan):
        assert _experiment_path_slug(name) == name.replace(
            "/", EXPERIMENT_PATH_SEPARATOR_SLUG
        )


def test_step_8_refuses_every_name_the_workflow_refuses(accepts) -> None:
    """Step 8 can be run by hand, so it does not lean on the workflow.

    Both halves have to refuse the same names -- including ``__``, which is
    what makes the flattening injective.
    """
    for name, why in NAMES_IT_MUST_REFUSE:
        assert not accepts(name)
        with pytest.raises(ValueError):
            slug = _experiment_path_slug(name)
            pytest.fail(
                f"step 8 accepted a name that {why} and turned it into "
                f"{slug!r}; the workflow refuses it"
            )


def test_step_8_accepts_every_name_the_workflow_accepts(accepts, plan: dict) -> None:
    for name in _plan_names(plan) + [
        _dispatch_name(path) for path in _runnable_configs()
    ]:
        assert accepts(name), name
        assert _experiment_path_slug(name)


def test_no_two_configs_flatten_onto_one_stem(accepts) -> None:
    """Injectivity, over what is actually on disk.

    The paid approval is inherited by matching the flattened stem, so two
    experiments sharing one would let a chunk of one inherit the other's
    approval. Refusing ``__`` inside a name is what prevents it, and this is
    the check that the refusal is enough.
    """
    names = [_dispatch_name(path) for path in _runnable_configs()]
    flattened: dict[str, str] = {}
    for name in names:
        slug = _experiment_path_slug(name)
        assert slug not in flattened, (
            f"{name!r} and {flattened[slug]!r} both flatten to {slug!r}"
        )
        flattened[slug] = name


def test_a_name_carrying_the_separator_slug_is_refused_by_both(accepts) -> None:
    """The one name that would break the flattening, named on purpose.

    ``execution_envelope/exp030`` becomes ``execution_envelope__exp030``. A
    top-level experiment actually called ``execution_envelope__exp030`` would
    land on the same grade file and the same approval stem, so it is refused --
    by the workflow before dispatch, and by step 8 when it is run by hand.
    """
    colliding = "execution_envelope__exp030"
    assert _experiment_path_slug("execution_envelope/exp030") == colliding
    assert not accepts(colliding)
    with pytest.raises(ValueError, match="__"):
        _experiment_path_slug(colliding)


# ── That the flattened name really reaches a file ─────────────────────────


def test_the_grade_filename_for_a_config_in_a_directory_is_one_component(
    grading_config: dict, plan: dict
) -> None:
    """The failure this change exists to prevent, at the place it happened.

    Before, this raised ``formatted grade filename must be a single safe path
    component`` -- two steps after the request was accepted, and after the
    corpus had been judged and paid for.
    """
    for name in _plan_names(plan):
        path = resolve_grade_output_path(
            grading_config, experiment_id=name, **IDENTITY
        )

        assert path.parent == Path("data/grades")
        assert "/" not in path.name
        assert path.name.startswith(name.replace("/", "__") + "__judge_")
        assert path.name.endswith(".json")


def test_the_shard_directory_for_a_config_in_a_directory_is_one_component(
    grading_config: dict, plan: dict
) -> None:
    """Sharding forks the path on the filename's stem.

    A separator surviving into that stem would put one shard's partial a
    directory deeper than the merge looks, and the merge derives the final
    file's name from the stem's parent.
    """
    name = _plan_names(plan)[0]
    path = resolve_grade_output_path(
        grading_config, experiment_id=name, shard_index=3, shard_count=11, **IDENTITY
    )

    assert path.name == "shard-003-of-011.json"
    stem = path.parent
    assert "/" not in stem.name
    assert stem.parent == Path("data/grades/_shards")
    assert stem.name.startswith(name.replace("/", "__") + "__judge_")


def test_the_uploaded_artifacts_are_named_with_the_flattened_name() -> None:
    """A GitHub artifact name may not contain a separator.

    Both uploads happen after the grading is finished and paid for -- the cost
    ledger's upload carries ``continue-on-error``, the grade's does not -- so a
    separator here would lose the run's only off-repository copy of the result.
    """
    text = WORKFLOW_PATH.read_text(encoding="utf-8")

    named = re.findall(r"^\s*name: (?:grade|cost-ledger)-\$\{\{ env\.(\w+)", text, re.M)
    assert len(named) == 2, f"expected two artifact names, found {named}"
    assert set(named) == {"GRADE_EXPERIMENT_SLUG"}, (
        "an artifact is named after the raw experiment name again; a name with "
        "a directory in it would be refused by the upload"
    )


def test_the_slug_is_carried_to_the_job_that_uploads() -> None:
    """The plumbing between the two, since neither half computes it twice."""
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]

    assert (
        jobs["validate-request"]["outputs"]["experiment_slug"]
        == "${{ steps.validate.outputs.experiment_slug }}"
    )
    assert (
        jobs["grade"]["env"]["GRADE_EXPERIMENT_SLUG"]
        == "${{ needs.validate-request.outputs.experiment_slug }}"
    )
    assert "validate-request" in jobs["grade"]["needs"]
