"""PR2 task 207's acceptance grep, and what is honestly left of it.

207 was accepted against one command::

    grep -r "tier_pro\\|tier_standard\\|tier_mini\\|deliverable_extract_max_chars" \\
         batch-runner/core/ batch-runner/grading_configs/   -> 0 matches

It never returned zero, and PR3 wrote down why: three kinds of hit, none of
them a grading path. Prose is where a carve-out goes to stop being checked, so
this file turns each kind into its own assertion, and the ones that are meant
to be empty are checked as empty rather than described as small.

* ``core/`` is now zero. That is what this task changed -- the last live hit
  was the Azure deployment allowlist enumerating the three tier names, and it
  no longer enumerates them.
* ``grading_configs/*.yaml`` still matches, in comments and in a ``description``
  block that record the removal. Neither can route a judge. What would is a
  key, so the rule here is that no line may *assign* one of these names, and
  the parsed configs are checked for the keys separately, at any depth.
  ``default_v2.yaml`` is hashed by ``compute_grader_source_hash``, so editing
  its prose to satisfy a grep would move the preserved PR2 baseline identity;
  the test is written to the real rule instead.
* ``grading_configs/_archive_v1/`` still matches everywhere, because 207's own
  instruction 3 created it. Those files are not reachable: ``grade-run.yml``
  refuses a ``grading_config`` containing a path separator.

The last test is the one with teeth outside the grep. Removing an enumeration
narrows an allowlist quietly; the boundary is only stronger if the config that
used to widen it is now refused, at the entry point a real run goes through.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE = REPO_ROOT / "batch-runner" / "core"
CONFIGS = REPO_ROOT / "batch-runner" / "grading_configs"
ARCHIVE = CONFIGS / "_archive_v1"
GRADE_RUN = REPO_ROOT / ".github" / "workflows" / "grade-run.yml"

#: The four names 207's acceptance command searches for.
LEGACY_NAMES = (
    "tier_pro",
    "tier_standard",
    "tier_mini",
    "deliverable_extract_max_chars",
)

#: Config keys that would actually route or truncate something, as opposed to
#: naming one in a comment. Checked at any depth, so a tier block nested under
#: a future wrapper key is caught too.
LEGACY_KEYS = frozenset(LEGACY_NAMES) | {"judge_routing", "batch_size"}


#: A line that *assigns* one of the legacy names -- ``tier_pro:``, or a list
#: entry ``- tier_pro:``. Prose and comments naming one do not match.
_ASSIGNS_LEGACY = re.compile(
    r"^\s*-?\s*(?:" + "|".join(LEGACY_NAMES) + r")\s*:",
)


def _hits(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return [
        (number, line)
        for number, line in enumerate(text.splitlines(), start=1)
        if any(name in line for name in LEGACY_NAMES)
    ]


def _keys_at_any_depth(node: object) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str):
                found.add(key)
            found |= _keys_at_any_depth(value)
    elif isinstance(node, list):
        for item in node:
            found |= _keys_at_any_depth(item)
    return found


def test_the_grading_core_names_no_legacy_tier():
    """``batch-runner/core/`` -- the half of 207's grep that must be zero."""
    offenders = {
        str(path.relative_to(REPO_ROOT)): _hits(path)
        for path in sorted(CORE.rglob("*.py"))
        if _hits(path)
    }
    assert not offenders, (
        "207's acceptance grep matches live grading code again: "
        f"{ {name: [n for n, _ in lines] for name, lines in offenders.items()} }"
    )


def test_shipped_configs_name_a_tier_only_where_it_cannot_route():
    shipped = [p for p in sorted(CONFIGS.glob("*.yaml")) if ARCHIVE not in p.parents]
    assert shipped, "no shipped grading configs found; the glob moved"
    live = {
        f"{path.name}:{number}": line.strip()
        for path in shipped
        for number, line in _hits(path)
        if _ASSIGNS_LEGACY.match(line)
    }
    assert not live, f"a shipped config assigns a legacy key: {live}"


@pytest.mark.parametrize(
    "path",
    [p for p in sorted(CONFIGS.glob("*.yaml"))],
    ids=lambda p: p.name,
)
def test_no_shipped_config_carries_a_legacy_key_at_any_depth(path: Path):
    parsed = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    carried = sorted(_keys_at_any_depth(parsed) & LEGACY_KEYS)
    assert not carried, f"{path.name} carries legacy config keys: {carried}"


def test_the_archive_that_still_matches_cannot_be_dispatched():
    """The archive is allowed to match because nothing can run it.

    That is only true while the workflow's name check forbids a separator, so
    the check is read out of the workflow rather than trusted.
    """
    assert list(ARCHIVE.glob("*.yaml")), "the v1 archive is empty; this claim moved"

    workflow = GRADE_RUN.read_text(encoding="utf-8")
    found = re.search(r"\^\[A-Za-z0-9\]\[A-Za-z0-9\._-\]\*\\\.ya\?ml\$", workflow)
    assert found, "grade-run.yml no longer pins a grading_config basename pattern"

    pattern = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.ya?ml$")
    for path in sorted(ARCHIVE.glob("*.yaml")):
        relative = path.relative_to(CONFIGS).as_posix()
        assert not pattern.match(relative), f"{relative} is dispatchable"
    assert pattern.match("default_v2_sol_max.yaml"), "the pattern rejects a live config"


def test_the_acceptance_grep_reports_only_the_documented_carve_outs():
    """Run 207's command and require every survivor to be one of them.

    ``git grep`` rather than the file walk above, so the command in the task
    and the command in the test are the same one. A survivor is explained only
    if it is in the archive 207 itself created, or is a line that names a
    legacy knob without assigning it.
    """
    completed = subprocess.run(
        [
            "git",
            "grep",
            "-n",
            "-E",
            "|".join(LEGACY_NAMES),
            "--",
            "core/",
            "grading_configs/",
        ],
        cwd=REPO_ROOT / "batch-runner",
        capture_output=True,
        text=True,
    )
    assert completed.returncode in (0, 1), completed.stderr
    unexplained = []
    for line in completed.stdout.splitlines():
        path, _, rest = line.partition(":")
        _, _, text = rest.partition(":")
        if path.startswith("grading_configs/_archive_v1/"):
            continue
        if path.startswith("grading_configs/") and not _ASSIGNS_LEGACY.match(text):
            continue
        unexplained.append(line)
    assert not unexplained, (
        "207's grep matches something that is neither the archive it created "
        f"nor a line that only names the removal: {unexplained}"
    )


def test_validate_grading_config_refuses_a_config_that_still_routes_by_tier():
    """The entry point, not the helper.

    ``Grader`` only refuses a config for *lacking*
    ``judge.tools.read_deliverable``. A config carrying both that and
    ``judge_routing`` therefore used to validate, credential its tier
    deployments, and grade every item on the main judge anyway. Deleting the
    enumeration on its own would have left that config valid and merely
    stopped crediting deployments -- quieter, not safer.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT / "batch-runner"))
    import step8_grade  # noqa: E402

    config = yaml.safe_load(
        (CONFIGS / "default_v2_sol_max.yaml").read_text(encoding="utf-8")
    )
    step8_grade.validate_grading_config(config)  # unchanged: still valid

    config["judge_routing"] = {"tier_pro": {"model": "p", "deployment": "p"}}
    with pytest.raises(ValueError, match="judge_routing is not a grading path"):
        step8_grade.validate_grading_config(config)
