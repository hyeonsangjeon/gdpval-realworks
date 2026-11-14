"""Every stage of the Sol 220 is graded with the libraries exp037 was graded with.

requirements.txt and requirements-renderer.txt only give lower bounds, so the
grade job used to install whatever was newest that day: exp035 rendered PDFs
with PyMuPDF 1.28.2, exp036 and exp037 with 2.1, and exp037's two chunks even
differed in trimesh. The grade job and its free dry run now install under
grading_constraints/exp037_grade_environment.txt, the versions exp037's final
chunk installed. That file sits outside the grader source hash on purpose, so
exp039 and exp040 keep exp037's grader identity, and inside GRADING_INPUT_PATHS,
so changing it mid-lineage still refuses a chunk. Model-free and offline.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
import yaml

import step8_grade

REPO_ROOT = Path(__file__).resolve().parents[2]
BATCH_ROOT = REPO_ROOT / "batch-runner"
WORKFLOW = REPO_ROOT / ".github/workflows/grade-run.yml"
CONSTRAINTS = "grading_constraints/exp037_grade_environment.txt"
EXP037_GRADE = sorted((REPO_ROOT / "data/grades").glob(
    "exp037_sol_first25__judge_gpt-5_6-sol__exp037_v2_sol_max__*__v2.2.json"))

#: What exp037's grade job reported installing for the libraries the judge's
#: read_deliverable tools and the renderer use to see a deliverable.
EXP037_RENDERERS = {"PyMuPDF": "2.1", "openpyxl": "3.1.5", "python-pptx": "1.0.2",
                    "python-docx": "1.2.0", "Pillow": "13.0.0"}


def _pins() -> dict[str, str]:
    pins = {}
    for line in (BATCH_ROOT / CONSTRAINTS).read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([0-9][A-Za-z0-9.+!_-]*)", line)
        assert match, f"not an exact pin: {line!r}"
        assert match[1].lower() not in {name.lower() for name in pins}, f"pinned twice: {match[1]}"
        pins[match[1]] = match[2]
    return pins


def _install_step(job: str) -> str:
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"][job]["steps"]
    (step,) = [s for s in steps if s.get("name") == "Install dependencies"]
    return step["run"]


@pytest.mark.parametrize("job", ["grade-dry-run", "grade"])
def test_the_paid_grade_and_its_dry_run_install_under_the_constraints(job):
    run = _install_step(job)
    assert f"pip install -r requirements.txt -c {CONSTRAINTS}" in run


def test_the_constraints_hold_exp037s_renderer_versions():
    pins = _pins()
    for name, version in EXP037_RENDERERS.items():
        assert pins.get(name) == version, name
    # Every package requirements-renderer.txt declares is pinned, so none of
    # them can move under a later stage.
    declared = [re.split(r"[<>=!~ ]", line, maxsplit=1)[0]
                for line in (BATCH_ROOT / "requirements-renderer.txt").read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#")]
    assert declared and {name.lower() for name in declared} <= {name.lower() for name in pins}


def test_the_constraints_are_outside_the_grader_identity():
    assert len(EXP037_GRADE) == 1, EXP037_GRADE
    grade = json.loads(EXP037_GRADE[0].read_text(encoding="utf-8"))
    config_path = BATCH_ROOT / "grading_configs/exp037_v2_sol_max.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    cwd = os.getcwd()
    try:
        os.chdir(BATCH_ROOT)
        this_tree = step8_grade.compute_grader_source_hash(
            "grading_configs/exp037_v2_sol_max.yaml", config, batch_root=BATCH_ROOT)
    finally:
        os.chdir(cwd)
    # The grader exp037 was graded with is still this tree's grader: the
    # constraints file changed what installs, not the grader's identity.
    assert this_tree == grade["grader_source_hash"]
    closure = step8_grade._requirements_closure(BATCH_ROOT, BATCH_ROOT / "requirements.txt")
    assert BATCH_ROOT / CONSTRAINTS not in {Path(p) for p in closure}


def test_a_change_to_the_constraints_between_dispatch_and_checkout_refuses_the_chunk():
    text = WORKFLOW.read_text(encoding="utf-8")
    blocks = [block.split(")", 1)[0] for block in text.split("GRADING_INPUT_PATHS=(")[1:]]
    assert len(blocks) == 2
    for block in blocks:
        assert "batch-runner/grading_constraints" in block.split()
