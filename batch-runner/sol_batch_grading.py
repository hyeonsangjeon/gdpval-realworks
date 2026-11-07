#!/usr/bin/env python3
"""Owner-approved USD admissions for paid Sol Max grades, one per approved pair.

grade-run.yml runs ``preflight`` for every generic grade, before any Azure
login, and runs ``run`` in place of ``python step8_grade.py`` only when that
preflight answered ``enabled=true``. It applies only to the pairs in
:data:`APPROVALS`: one experiment graded with one config, under one ceiling.
Any other grade gets ``enabled=false`` and runs step 8 as before. The config
half of a pair never grades another experiment, so a copied config cannot
carry an approval elsewhere. Where an approval is ``exclusive_experiment``
(the Sol batch), the experiment half is never graded by another config either,
so the batch cannot be graded by a config its ceiling was not sized for.

:data:`EXP036_SOL_BATCH`: the owner's USD 200 (approved 2026-11-05) covers the
solve run and its grade together. ``preflight`` seeds the grade's admission
with what is already committed:

* the solve spend that ``sol_batch_controls`` booked onto each published task
  row (self_report.json ``observability.budget_metrics``), cross-checked
  against a lower bound priced from the published cost_ledger.jsonl;
* a fixed allowance for the step 6 narrative, which runs outside both ledgers;
* every grading journal already committed for this experiment.

:data:`EXP035_PARITY` (approved 2026-11-06): regrading only the exp035 tasks
whose deliverable selection the reviewed selector changed, under the approved
grading-only ceiling (:data:`EXP035_PARITY_CEILING_USD`). Its seed is every
committed journal of that approval; there is no solve spend, because exp035's
inference is not part of it.

An entry whose ``approved`` is ``None`` registers a pair without admitting it:
the pair is refused once its two YAML files are read, before anything
published or committed is ("registered but not approved for spending"); its
config grades no other experiment, an exclusive entry's experiment is graded
by no other config (a non-exclusive entry's experiment with another config
stays inert, like any grade no approval names), and no journal can claim it.
:func:`approval_problems` holds every entry to the registry's rules.

An approval defines the scope it pays for: the whole published run (the Sol
batch) or the config's pinned task list (a grading-only approval). ``run``
refuses step 8's ``--tasks`` and ``--limit``, which would grade a subset of it
under the same ceiling.

``run`` then lets step 8 grade under a per-request admission that refuses any
request whose reservation would carry that total past the ceiling. A refusal
surfaces in step 8 as ``GradingUsdStopped``: the finished tasks are saved as a
partial and step 8 exits 4, which never requests another paid chunk.

Run control only. Nothing here changes what step 8 or core score, which tasks
are in scope, or any byte of a sealed file.

The one runtime patch. step8_grade.py and core/** are byte-sealed by #794.
step8 hands ``usd_admission`` to ``open_cost_recorder`` only for the paused
pilot (step8_grade.py:2536-2638, via gpt56_pilot_usd_budget.is_pilot_grading
and open_grading_admission at :686-718), and parse_args (:567-656) takes no
other admission input. :func:`install_admission` therefore rebinds exactly one
name, the module global ``step8_grade.open_cost_recorder`` (imported at :36,
called once at :2941-2946), to a closure that passes
``core.cost_metering.open_cost_recorder`` (:1009-1063) this module's
admission. CostRecorder already applies that reviewed interface: check_client
at :691-692, and grading_request, unattributed, reserve, finish and abandon at
:888-976. No file changes, so grader_source_hash and the seal do not move. An
identity check refuses if a future reseal moves that name.

Top-level imports are the standard library and yaml only. Everything else is
imported after :func:`applies` has found this grade's approval, so the
``enabled=false`` path that every other paid grade now passes cannot fail on
an import.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, NoReturn, Sequence

import yaml

SOLVE_SEED_SOL_BATCH = "sol_batch_controls"
SOLVE_SEED_NONE = "none"


@dataclass(frozen=True)
class Approval:
    """One owner-approved (experiment, grading config) pair and its USD ceiling.

    With ``approved`` None the pair is registered but admits nothing yet: it is
    refused once the experiment YAML and the config are read, before anything
    published or committed is. Its config grades nothing else, and when
    ``exclusive_experiment`` is set its experiment is graded by nothing else.
    """

    #: ``experiment.id`` in experiments/<id>.yaml; the YAML must be named after it.
    experiment_id: str
    #: ``config_name`` of the one grading config this approval admits.
    config_name: str
    #: The combined ceiling; None exactly when ``approved`` is None.
    ceiling_usd: Decimal | None
    #: SOLVE_SEED_SOL_BATCH: the ceiling also covers the solve run, seeded from
    #: what sol_batch_controls booked. SOLVE_SEED_NONE: grading spend only.
    solve_seed: str
    #: True: no other config may grade this experiment (the Sol batch).
    exclusive_experiment: bool
    #: Pinned inference commit, or None when the dispatch names it.
    inference_revision: str | None
    #: step 8's ordered-task-ids SHA-256 of the config's pinned scope, or None
    #: when the config pins none and the grade covers the whole published run.
    task_ids_sha256: str | None
    #: The owner's dated approval, or None: registered, not approved.
    approved: str | None


EXP036_SOL_BATCH = Approval(
    experiment_id="exp036_sol_fixed5",
    config_name="exp036_v2_sol_max",
    ceiling_usd=Decimal("200"),
    solve_seed=SOLVE_SEED_SOL_BATCH,
    exclusive_experiment=True,
    inference_revision=None,
    task_ids_sha256=None,
    approved="2026-11-05 owner: USD 200 for the exp036 solve run and its grade together",
)
#: The parity regrade's automatic stop: the owner's USD 200 of 2026-11-06,
#: 12:20 KST ("한도 높여. 중간에 멈출 확률 제로로": raise the ceiling, make
#: the chance of stopping midway zero). Priced at the Sol list meter from
#: exp035's own token counts, the eight tasks' 424 items are expected to cost
#: about USD 62 (p99 112); one draw in a million passed 200. This is the one
#: place the figure lives, and test_sol_batch_grading_approvals pins it.
EXP035_PARITY_CEILING_USD = Decimal("200")
EXP035_PARITY = Approval(
    experiment_id="exp035_codex_foundry_full220",
    config_name="e35par",
    ceiling_usd=EXP035_PARITY_CEILING_USD,
    solve_seed=SOLVE_SEED_NONE,
    exclusive_experiment=False,
    inference_revision="dc36d6837a8f0899f8bfa4d32aae9a9f6805f3b0",
    task_ids_sha256="b2ed72124660d52d20ffb3af870fa308a3ebdf3b2bbe4aed9dc495f240ac4851",
    approved=("2026-11-06 owner (\"셋다 예\", 01:55 KST): regrade the exp035 tasks whose"
              " deliverable selection the reviewed selector changed, for parity; stop automatically"
              " at USD 200 (\"한도 높여. 중간에 멈출 확률 제로로\", 12:20 KST)"),
)
#: Every admission this module can open. One approval per experiment and per
#: config, because an experiment's journals share one directory.
#:
#: There is no retired state. An entry cannot simply be removed or set back to
#: unapproved once it has a committed journal: that journal would then have no
#: owner and every later preflight of its experiment would refuse. Nor can an
#: experiment take a second entry: the registry would be malformed, and that
#: refuses every approved grade. So after the parity regrade exp035 cannot be
#: graded under another ceiling (for example a single-hash regrade for the Sol
#: 220 comparison) until a PR gives the registry a retired state that keeps
#: journal ownership but admits nothing.
APPROVALS: tuple[Approval, ...] = (EXP036_SOL_BATCH, EXP035_PARITY)
#: The Sol batch; equal to ``sol_batch_controls.EXPERIMENT_ID`` (a test holds
#: the two together).
GRADED_EXPERIMENT_ID = EXP036_SOL_BATCH.experiment_id
#: The one grading config allowed to grade it.
GRADING_CONFIG_NAME = EXP036_SOL_BATCH.config_name
#: Experiment id plus config name. For this judge and prompt version the
#: longest file step 8 creates is 219 + that many bytes (the grade stem plus
#: CHECKPOINT_TMP_EXTRA), so 36 keeps it within NAME_MAX. check_name_budget
#: computes the real name before any login; approval_problems holds the
#: registry to it.
NAME_BUDGET_CHARACTERS = 36
#: exp035's Sol Max config. The judge, rubric, grader, tpm_guard, prompt and
#: output blocks were copied from it, and the reservation sizes below assume
#: that judge; a drifted block would grade under a ceiling sized for another.
TEMPLATE = "grading_configs/exp035_codex_foundry_full220_v2_sol_max.yaml"
TEMPLATE_SHA256 = "89820de9d9c4e2e3edc1420d3c05fd12c7bb4c3475fd47ad92ed56566a897025"
TEMPLATE_BLOCKS = ("schema_version", "judge", "rubric", "grader", "tpm_guard", "prompt", "output")
#: One journal per grading process, committed by grade-run.yml. The suffix is
#: .jsonl on purpose: verify_published_grades.grade_files_in (:213) and
#: scripts/aggregate-grades.mjs (:1465) read only *.json, so a journal is never
#: taken for a grade.
JOURNAL_DIR = Path("data/grades/_combined_usd")
JOURNAL_SCHEMA = "sol-batch-grading-journal-v1"
JOURNAL_NAME = re.compile(r"run-[1-9][0-9]{0,19}-[1-9][0-9]{0,5}\.combined_usd\.jsonl")
#: What core/task_checkpoint.py:199-212 adds to a grade stem for a task's
#: progress file while it is written: ``__<36-character task id>.json.tmp``.
#: It is the longest name step 8 creates from the stem, so it sets the budget.
CHECKPOINT_TMP_EXTRA = len("__") + 36 + len(".json.tmp")
NAME_MAX = 255
REFUSED_EXIT = 4
#: The same strings as gpt56_pilot_usd_budget's CEILING, UNVERIFIED and
#: UNKNOWN, so step 8's refusal record reads the same for either admission.
CEILING = "usd_ceiling_exceeded"
UNVERIFIED = "usd_ledger_unverified"
UNKNOWN = "usd_usage_unverified"

_FULL_SHA = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_RUN_ID = re.compile(r"[1-9][0-9]{0,19}")
_RUN_ATTEMPT = re.compile(r"[1-9][0-9]{0,5}")
_MONEY_TEXT = re.compile(r"(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,8})?")
_MONEY_PLACES = Decimal("0.00000001")
_TOKENS_PER_MILLION = Decimal(1_000_000)
_FETCH_ATTEMPTS = 3
_FETCH_BACKOFF_SECONDS = 5
_JOURNAL_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND | os.O_NOFOLLOW


class CombinedUsdRefused(Exception):
    """This grade may not start, or may not continue, under the combined ceiling.

    ``code`` is one of :data:`CEILING`, :data:`UNVERIFIED` or :data:`UNKNOWN`;
    ``detail`` says which check refused, without any credential or endpoint.
    """

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _refuse(detail: str, code: str = UNVERIFIED) -> NoReturn:
    raise CombinedUsdRefused(code, detail)


def _money(amount: Decimal | int | str) -> str:
    """USD at the cost ledger's eight places, rounded up, as text."""
    return format(Decimal(amount).quantize(_MONEY_PLACES, rounding=ROUND_CEILING), "f")


def _ceil8(amount: Decimal) -> Decimal:
    return amount.quantize(_MONEY_PLACES, rounding=ROUND_CEILING)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_yaml(path: Path, label: str) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        _refuse(f"{label} could not be read ({type(exc).__name__})")


def _experiment_path(experiment_yaml_name: str) -> Path:
    # cwd-relative, as step8_grade.load_experiment_yaml (:1364) opens it.
    return Path("experiments", f"{experiment_yaml_name}.yaml")


# -- applicability ------------------------------------------------------------


def approval_problems(approvals: Sequence[Approval] | None = None) -> list[str]:
    """What breaks the registry's rules; empty when every entry keeps them.

    One approval per experiment and per config (an experiment's journals share
    one directory); experiment id plus config name within the name budget; a
    ceiling exactly when there is an approval; a Sol batch entry exclusive to
    its experiment, taking its scope from sol_batch_controls; a grading-only
    entry pinned to one inference revision and one task scope.
    """
    entries = APPROVALS if approvals is None else tuple(approvals)
    problems: list[str] = []
    experiments: set[str] = set()
    configs: set[str] = set()
    for approval in entries:
        if type(approval) is not Approval:
            problems.append(f"{approval!r} is not an Approval")
            continue
        name = f"{approval.experiment_id}/{approval.config_name}"
        if (not isinstance(approval.experiment_id, str) or not approval.experiment_id
                or not isinstance(approval.config_name, str) or not approval.config_name):
            problems.append(f"{name}: names no experiment or no config")
            continue
        if approval.experiment_id in experiments:
            problems.append(f"{name}: a second approval for the experiment")
        if approval.config_name in configs:
            problems.append(f"{name}: a second approval for the config")
        experiments.add(approval.experiment_id)
        configs.add(approval.config_name)
        if len(approval.experiment_id) + len(approval.config_name) > NAME_BUDGET_CHARACTERS:
            problems.append(f"{name}: experiment id plus config name is past "
                            f"{NAME_BUDGET_CHARACTERS} characters")
        if approval.approved is None:
            if approval.ceiling_usd is not None:
                problems.append(f"{name}: a ceiling without an approval")
        else:
            if not isinstance(approval.approved, str) or not approval.approved.strip():
                problems.append(f"{name}: the approval is not stated")
            if (type(approval.ceiling_usd) is not Decimal or not approval.ceiling_usd.is_finite()
                    or approval.ceiling_usd <= 0):
                problems.append(f"{name}: an approval without a positive ceiling")
        if approval.solve_seed == SOLVE_SEED_SOL_BATCH:
            if (approval.exclusive_experiment is not True or approval.inference_revision is not None
                    or approval.task_ids_sha256 is not None):
                problems.append(f"{name}: a Sol batch approval is exclusive and takes its scope "
                                "from sol_batch_controls")
        elif approval.solve_seed == SOLVE_SEED_NONE:
            if (not isinstance(approval.inference_revision, str)
                    or not _FULL_SHA.fullmatch(approval.inference_revision)
                    or not isinstance(approval.task_ids_sha256, str)
                    or not _SHA256.fullmatch(approval.task_ids_sha256)):
                problems.append(f"{name}: a grading-only approval pins its inference revision "
                                "and task scope")
        else:
            problems.append(f"{name}: an unknown solve seed")
    return problems


def approval_for(experiment_yaml_name: str, config_path: str | Path) -> Approval | None:
    """The approval this grade runs under, or ``None`` when no approval names it.

    Both files are read the way step 8 reads them. A file that cannot be read
    refuses rather than answering ``None``: step 8 would fail on it too, and
    refusing here keeps an unreadable approved file from slipping past as "not
    approved". A config named by an approval that is handed another
    experiment refuses, and so does an exclusive approval's experiment handed
    another config.
    """
    if not isinstance(experiment_yaml_name, str) or not experiment_yaml_name:
        _refuse("experiment name must be a non-empty string")
    experiment = _load_yaml(_experiment_path(experiment_yaml_name), "experiment YAML")
    config = _load_yaml(Path(config_path), "grading config")
    meta = experiment.get("experiment") if isinstance(experiment, dict) else None
    declared = meta.get("id") if isinstance(meta, dict) else None
    named = config.get("config_name") if isinstance(config, dict) else None
    by_config = [approval for approval in APPROVALS if approval.config_name == named]
    by_experiment = [approval for approval in APPROVALS
                     if approval.exclusive_experiment and approval.experiment_id == declared]
    if not by_config and not by_experiment:
        return None
    problems = approval_problems()
    if problems:
        _refuse(f"the approval registry is malformed: {problems[0]}")
    for approval in (*by_config, *by_experiment):
        if approval.experiment_id == declared and approval.config_name == named:
            # Before anything published or committed is read.
            if approval.approved is None:
                _refuse(f"{approval.experiment_id} is registered but not approved for spending")
            return approval
    pair = (by_config or by_experiment)[0]
    _refuse(f"{pair.experiment_id} and the {pair.config_name} config only grade each other")


def applies(experiment_yaml_name: str, config_path: str | Path) -> bool:
    """Whether an approval in :data:`APPROVALS` holds this grade's USD admission."""
    return approval_for(experiment_yaml_name, config_path) is not None


# -- the committed floor ------------------------------------------------------


@dataclass(frozen=True)
class Seed:
    """What is already committed against the ceiling before this grade starts."""

    experiment_id: str
    config_name: str
    inference_revision: str
    solve_usd: Decimal
    published_ledger_floor_usd: Decimal
    published_ledger_status: str
    narrative_allowance_usd: Decimal
    prior_grading_usd: Decimal
    prior_journals: tuple[Mapping[str, str], ...]
    ceiling_usd: Decimal

    def committed_floor(self) -> Decimal:
        return self.solve_usd + self.narrative_allowance_usd + self.prior_grading_usd

    def as_record(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "config_name": self.config_name,
            "inference_revision": self.inference_revision,
            "solve_usd": _money(self.solve_usd),
            "published_ledger_floor_usd": _money(self.published_ledger_floor_usd),
            "published_ledger_status": self.published_ledger_status,
            "narrative_allowance_usd": _money(self.narrative_allowance_usd),
            "prior_grading_usd": _money(self.prior_grading_usd),
            "prior_journals": [dict(journal) for journal in self.prior_journals],
            "committed_floor_usd": _money(self.committed_floor()),
            "ceiling_usd": _money(self.ceiling_usd),
        }


def check_name_budget(
    step8: Any,
    config: Mapping[str, Any],
    config_path: str | Path,
    experiment_yaml_name: str,
    inference_revision: str,
) -> Path:
    """Refuse a pair whose grade stem leaves step 8 a file it cannot create.

    Resolved with step 8's own functions, so the stem is the one the paid run
    will write. A name past NAME_MAX fails only after approval, OIDC login and
    the HF download (the cost ledger cannot open, or a task's progress cannot
    be saved), so it is refused here instead.
    """
    try:
        revision = config["rubric"]["revision"]
        out = step8.resolve_grade_output_path(
            config,
            experiment_id=experiment_yaml_name,
            judge_slug=step8._judge_slug(config["judge"]["model"]),
            config_hash=step8.hash_config(str(config_path)),
            rubric_sha=revision,
            rubric_short_sha=revision[:7],
            prompt_version=config["prompt"]["version"],
            inference_sha=inference_revision,
            grader_source_hash=step8.compute_grader_source_hash(Path(config_path), config),
        )
    except (KeyError, TypeError, OSError, ValueError) as exc:
        _refuse(f"the grade file name could not be resolved ({type(exc).__name__})")
    longest = len(out.stem.encode("utf-8")) + CHECKPOINT_TMP_EXTRA
    if longest > NAME_MAX:
        _refuse(
            f"a task progress file would be {longest} bytes, past the {NAME_MAX}-byte "
            "file name limit; shorten the experiment or config name"
        )
    return out


def preflight(
    experiment_yaml_name: str,
    config_path: str | Path,
    inference_revision: str,
    shard_count: int,
) -> Seed | None:
    """The committed floor for an approved grade, or ``None`` for any other grade.

    Model-free: it reads the two YAML files, the template, the committed
    grading journals and, for the Sol batch, the published self_report.json
    and cost_ledger.jsonl (anonymously). It refuses before any OIDC login when
    the pair, the config, the scope, the file name or the remaining budget is
    inadmissible.
    """
    approval = approval_for(experiment_yaml_name, config_path)
    if approval is None:
        return None
    import step8_grade as step8

    # Every journal of one approval lands in one directory named after the
    # experiment YAML; an alias YAML declaring the same id would open a second
    # directory and hide the first one's spend from this sum.
    if experiment_yaml_name != approval.experiment_id:
        _refuse("an approved experiment is graded under its own YAML name only")
    # One process owns the admission. N shards would each see the whole
    # remaining budget.
    if type(shard_count) is not int or shard_count != 1:
        _refuse("an approved grade is graded by one unsharded process")
    if not isinstance(inference_revision, str) or not _FULL_SHA.fullmatch(inference_revision):
        _refuse("the inference revision must be a full 40-character lowercase HF commit")
    if approval.inference_revision is not None and inference_revision != approval.inference_revision:
        _refuse("the dispatch names another inference revision than the approval")

    experiment = _load_yaml(_experiment_path(experiment_yaml_name), "experiment YAML")
    config = _load_yaml(Path(config_path), "grading config")
    try:
        template_bytes = Path(TEMPLATE).read_bytes()
    except OSError as exc:
        _refuse(f"the template config could not be read ({type(exc).__name__})")
    if hashlib.sha256(template_bytes).hexdigest() != TEMPLATE_SHA256:
        _refuse("the template config changed")
    template = yaml.safe_load(template_bytes)
    for block in TEMPLATE_BLOCKS:
        if block not in config or block not in template or config[block] != template[block]:
            _refuse(f"grading config block {block!r} differs from the template")
    rerun = config.get("rerun_identity")
    if approval.task_ids_sha256 is None:
        if rerun is not None:
            if (not isinstance(rerun, dict) or rerun.get("experiment_id") != approval.experiment_id
                    or rerun.get("inference_revision") != inference_revision):
                _refuse("the config's rerun_identity names another experiment or revision")
    else:
        # The ceiling was sized for one pinned scope; a config that pins any
        # other list, or none, is not the grade that was approved.
        if (not isinstance(rerun, dict) or rerun.get("experiment_id") != approval.experiment_id
                or rerun.get("inference_revision") != inference_revision):
            _refuse("the config's rerun_identity names another experiment or revision")
        task_ids = rerun.get("task_ids")
        if (not isinstance(task_ids, list) or not task_ids
                or any(not isinstance(task_id, str) for task_id in task_ids)
                or rerun.get("expected_task_count") != len(task_ids)
                or step8._ordered_task_ids_sha256(task_ids) != approval.task_ids_sha256):
            _refuse("the config's pinned task scope is not the approved scope")

    check_name_budget(step8, config, config_path, experiment_yaml_name, inference_revision)

    # Everything local before anything is fetched.
    try:
        slug = step8._experiment_path_slug(experiment_yaml_name)
    except ValueError:
        _refuse("the experiment name is not a single grade-file component")
    prior, journals = prior_grading(step8._repo_root(), slug, approval)
    solve_usd, floor, status, narrative = _solve_seed(approval, experiment, inference_revision)
    seed = Seed(
        experiment_id=approval.experiment_id,
        config_name=approval.config_name,
        inference_revision=inference_revision,
        solve_usd=solve_usd,
        published_ledger_floor_usd=floor,
        published_ledger_status=status,
        narrative_allowance_usd=narrative,
        prior_grading_usd=prior,
        prior_journals=tuple(journals),
        ceiling_usd=approval.ceiling_usd,
    )
    if seed.committed_floor() >= seed.ceiling_usd:
        _refuse(
            f"committed {_money(seed.committed_floor())} of {_money(seed.ceiling_usd)} "
            "before grading starts",
            CEILING,
        )
    return seed


def _solve_seed(
    approval: Approval, experiment: Any, inference_revision: str,
) -> tuple[Decimal, Decimal, str, Decimal]:
    """``(solve_usd, ledger_floor_usd, ledger_status, narrative_usd)`` already under the ceiling.

    A grading-only approval holds no solve spend. The Sol batch holds what
    sol_batch_controls booked onto the published task rows (cross-checked by
    :func:`published_solve`) plus the step 6 narrative allowance, and its two
    sides must name the same experiment and the same ceiling.
    """
    if approval.solve_seed == SOLVE_SEED_NONE:
        return Decimal(0), Decimal(0), "not_applicable", Decimal(0)
    if approval.solve_seed != SOLVE_SEED_SOL_BATCH:
        _refuse("the approval names no known solve seed")
    import sol_batch_controls as controls

    if controls.EXPERIMENT_ID != approval.experiment_id:
        _refuse("sol_batch_controls grades a different experiment")
    if controls.CEILING_USD != approval.ceiling_usd:
        _refuse("the solve and grade sides name different ceilings")
    try:
        repo_id = experiment["data"]["source"]
    except (KeyError, TypeError):
        _refuse("the experiment YAML names no data.source")
    solve_usd, floor, status = published_solve(repo_id, inference_revision)
    return solve_usd, floor, status, controls.NARRATIVE_ALLOWANCE_USD


# -- the published solve spend ------------------------------------------------


def _fetch(repo_id: str, filename: str, revision: str) -> Path | None:
    """One file of the published dataset at ``revision``, or ``None`` if it is not there.

    Anonymous (``token=False``): the batch's dataset is public, and this runs
    before any credential step. The not-found errors are the ones
    scripts/download_inference_from_hf.py:33-38 imports. LocalEntryNotFoundError
    subclasses EntryNotFoundError in huggingface_hub 1.24.0 but means the Hub
    could not be reached, so it is retried like any other failure.
    """
    from huggingface_hub import hf_hub_download
    from huggingface_hub.errors import (
        EntryNotFoundError,
        LocalEntryNotFoundError,
        RemoteEntryNotFoundError,
    )

    failure: BaseException | None = None
    for attempt in range(1, _FETCH_ATTEMPTS + 1):
        try:
            return Path(hf_hub_download(
                repo_id=repo_id,
                repo_type="dataset",
                filename=filename,
                revision=revision,
                token=False,
            ))
        except (EntryNotFoundError, RemoteEntryNotFoundError) as exc:
            if not isinstance(exc, LocalEntryNotFoundError):
                return None
            failure = exc
        except Exception as exc:  # noqa: BLE001 - retried, then refused by type
            failure = exc
        if attempt < _FETCH_ATTEMPTS:
            time.sleep(_FETCH_BACKOFF_SECONDS * attempt)
    _refuse(f"{filename} could not be fetched ({type(failure).__name__})")


def _call_fetch(
    fetch: Callable[[str, str, str], Path | None], repo_id: str, filename: str, revision: str,
) -> Path | None:
    try:
        return fetch(repo_id, filename, revision)
    except CombinedUsdRefused:
        raise
    except Exception as exc:  # noqa: BLE001 - any fetch failure leaves the seed unknown
        _refuse(f"{filename} could not be fetched ({type(exc).__name__})")


def published_solve(
    repo_id: str,
    revision: str,
    *,
    fetch: Callable[[str, str, str], Path | None] = _fetch,
) -> tuple[Decimal, Decimal, str]:
    """``(solve_usd, ledger_floor_usd, ledger_status)`` from the dataset at ``revision``.

    The solve spend is what sol_batch_controls booked per task and step 2
    published as ``observability.budget_metrics.conservative_cost_usd``; it
    survives relay legs, where each leg's per-turn ledger does not. The
    published cost_ledger.jsonl holds only the last leg's rows, so its settled
    rows priced at the same list meter are a lower bound: booked spend below
    it, not counting ``PRIOR_LINEAGE_SPEND_USD``, means a booking was lost,
    and refuses. A row that reached Codex without a booking refuses unless
    ``LOST_BOOKING_USD`` names it for ``revision``.
    """
    import sol_batch_controls as controls
    from core.repository_identity import validate_hf_dataset_repo_id

    try:
        validate_hf_dataset_repo_id(repo_id)
    except ValueError:
        _refuse("data.source is not a valid HF dataset id")

    report_path = _call_fetch(fetch, repo_id, "self_report.json", revision)
    if report_path is None:
        _refuse("self_report.json is not published at this revision")
    try:
        report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        _refuse(f"self_report.json could not be read ({type(exc).__name__})")
    meta = report.get("meta") if isinstance(report, dict) else None
    if not isinstance(meta, dict) or meta.get("experiment_id") != GRADED_EXPERIMENT_ID:
        _refuse("self_report.json belongs to another experiment")
    rows = report.get("task_results")
    if not isinstance(rows, list):
        _refuse("self_report.json has no task_results list")
    try:
        solve = controls.solve_spend_usd(rows, revision)
    except controls.SolBatchControlsRefused as exc:
        _refuse(str(exc))
    # Only this lineage's own bookings can cover its own ledger. What earlier
    # lineages spent must not hide a booking lost from this one.
    booked = solve - controls.PRIOR_LINEAGE_SPEND_USD

    ledger_path = _call_fetch(fetch, repo_id, "cost_ledger.jsonl", revision)
    if ledger_path is None:
        floor, status = Decimal(0), "absent"
    else:
        try:
            rates = controls.load_sol_list_rates()
        except controls.SolBatchControlsRefused as exc:
            _refuse(str(exc))
        floor = Decimal(0)
        try:
            lines = Path(ledger_path).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            _refuse(f"cost_ledger.jsonl could not be read ({type(exc).__name__})")
        for line in lines:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                _refuse("cost_ledger.jsonl has a line that is not JSON")
            if not isinstance(row, dict):
                _refuse("cost_ledger.jsonl has a line that is not an object")
            if row.get("record_type") != "call" or row.get("state") != "settled":
                continue
            price = controls.list_price_usd(
                input_tokens=row.get("input_tokens"),
                cached_input_tokens=row.get("cached_input_tokens"),
                output_tokens=row.get("output_tokens"),
                reasoning_tokens=row.get("reasoning_tokens"),
                rates=rates,
            )
            if price is not None:
                floor += price
        status = "present"
    if booked < floor:
        _refuse(
            f"published booked solve spend {_money(booked)} (without prior lineages) is below "
            f"the published ledger's settled floor {_money(floor)}"
        )
    return solve, floor, status


# -- committed grading journals -----------------------------------------------


def _journal_amount(value: Any, field: str) -> Decimal:
    if not isinstance(value, str) or not _MONEY_TEXT.fullmatch(value):
        _refuse(f"journal {field} is not a USD amount")
    return Decimal(value)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _refuse("journal line repeats a key")
        result[key] = value
    return result


def _reject_constant(name: str) -> NoReturn:
    _refuse(f"journal line carries {name}")


def _journal_owner(record: Mapping[str, Any]) -> Approval | None:
    """The approved admission that wrote a journal, from its open line."""
    for approval in APPROVALS:
        if approval.approved is None:
            continue
        if (record.get("experiment_id") == approval.experiment_id
                and record.get("config_name") == approval.config_name):
            return approval
    return None


def _read_journal(path: Path, approval: Approval | None = None) -> tuple[Decimal, str]:
    """``(spent_usd, sha256)`` of one committed journal; anything malformed refuses.

    The open line names the approval that wrote it. With ``approval`` given,
    a journal written under any other approval refuses too.
    """
    if not JOURNAL_NAME.fullmatch(path.name):
        _refuse(f"{path.name} is not a combined USD journal name")
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            _refuse(f"{path.name} is not a regular file")
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as handle:
            raw = handle.read()
    except OSError as exc:
        _refuse(f"{path.name} could not be read ({type(exc).__name__})")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        _refuse(f"{path.name} is not UTF-8")
    # Every line is written whole and fsynced, so a missing final newline is
    # a torn write, not a short journal.
    if not text.endswith("\n"):
        _refuse(f"{path.name} does not end with a complete line")
    lines = text[:-1].split("\n")
    spent = Decimal(0)
    open_tickets: dict[str, Decimal] = {}
    concluded: set[str] = set()
    closed_spent: Decimal | None = None
    for index, line in enumerate(lines):
        try:
            record = json.loads(
                line, object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_constant,
            )
        except ValueError:
            _refuse(f"{path.name} line {index} is not JSON")
        if not isinstance(record, dict) or type(record.get("seq")) is not int or record["seq"] != index:
            _refuse(f"{path.name} line {index} is out of sequence")
        if closed_spent is not None:
            _refuse(f"{path.name} continues after its close line")
        event = record.get("event")
        if index == 0:
            owner = _journal_owner(record)
            if event != "open" or record.get("schema") != JOURNAL_SCHEMA or owner is None:
                _refuse(f"{path.name} is not the journal of an approved admission")
            if approval is not None and owner is not approval:
                _refuse(f"{path.name} is not a {approval.experiment_id} / {approval.config_name} journal")
            continue
        ticket = record.get("ticket")
        if event == "reserve":
            if not isinstance(ticket, str) or not ticket or ticket in open_tickets or ticket in concluded:
                _refuse(f"{path.name} line {index} reuses or lacks a ticket")
            open_tickets[ticket] = _journal_amount(record.get("reserve_usd"), "reserve_usd")
        elif event in ("settle", "abandon"):
            if not isinstance(ticket, str) or ticket not in open_tickets:
                _refuse(f"{path.name} line {index} concludes a ticket that is not open")
            spent += _journal_amount(record.get("spent_usd"), "spent_usd")
            del open_tickets[ticket]
            concluded.add(ticket)
        elif event == "stop":
            if not isinstance(record.get("reason"), str):
                _refuse(f"{path.name} line {index} is a stop without a reason")
        elif event == "close":
            closed_spent = _journal_amount(record.get("spent_usd"), "spent_usd")
        else:
            _refuse(f"{path.name} line {index} has an unknown event")
    if closed_spent is not None:
        # The close line carries the in-memory total. A conclusion whose own
        # line failed to write is still in it, so the larger figure is kept.
        spent = max(spent, closed_spent)
    # A reservation that never concluded is spent: the request may have been
    # served and billed after the process died.
    return spent + sum(open_tickets.values(), Decimal(0)), hashlib.sha256(raw).hexdigest()


def journal_spend(path: Path | str) -> Decimal:
    """USD one committed journal spent: settled, abandoned, and never-concluded reserves."""
    return _read_journal(Path(path))[0]


def prior_grading(
    repo_root: Path | str, slug: str, approval: Approval = EXP036_SOL_BATCH,
) -> tuple[Decimal, list[dict[str, str]]]:
    """Every committed journal for this experiment, each counted once.

    Journals are per process and never overlap. step 8's own cost ledgers are
    never summed here: a resumed chunk re-imports the earlier chunk's rows, so
    adding them would count those rows twice. A journal in the directory that
    another approval wrote refuses: it is spend this sum cannot place.
    """
    root = Path(repo_root)
    directory = root / JOURNAL_DIR / slug
    for part in (root / JOURNAL_DIR, directory):
        if part.is_symlink() or (part.exists() and not part.is_dir()):
            _refuse(f"{part.name} is not a plain directory")
    total = Decimal(0)
    journals: list[dict[str, str]] = []
    if not directory.exists():
        return total, journals
    for path in sorted(directory.glob("run-*.combined_usd.jsonl")):
        spent, digest = _read_journal(path, approval)
        total += spent
        journals.append({
            "path": path.relative_to(root).as_posix(),
            "sha256": digest,
            "spent_usd": _money(spent),
        })
    return total, journals


# -- the per-request admission ------------------------------------------------


class CombinedGradingAdmission:
    """The ``usd_admission`` core's CostRecorder applies to every metered grading request.

    Each request reserves an upper bound before it is sent and settles at the
    reported usage afterwards. A request whose reservation would carry the
    committed total past the ceiling is refused before it is sent. Every
    reservation and conclusion is one fsynced journal line, so the spend of a
    process that dies is still on disk for the next preflight.
    """

    def __init__(self, seed: Seed, journal_path: Path | str):
        import gpt56_pilot_usd_budget as usd
        import sol_batch_controls as controls

        path = Path(journal_path)
        if not JOURNAL_NAME.fullmatch(path.name):
            _refuse(f"{path.name} is not a combined USD journal name")
        self._usd = usd
        self._controls = controls
        self._lock = threading.RLock()
        self.seed = seed
        self.journal_path = path
        try:
            self.rates_sol = controls.load_sol_list_rates()
        except controls.SolBatchControlsRefused as exc:
            _refuse(str(exc))
        self.spent = Decimal(0)
        self.pending: dict[str, Decimal] = {}
        self.stops: list[str] = []
        self._tickets = 0
        self._seq = 0
        self._journal_failed = False
        try:
            self._fd: int | None = os.open(path, _JOURNAL_FLAGS, 0o644)
        except OSError as exc:
            _refuse(f"the journal could not be created ({type(exc).__name__})")
        try:
            self._append(
                "open",
                schema=JOURNAL_SCHEMA,
                **seed.as_record(),
                github_run_id=os.environ.get("GITHUB_RUN_ID"),
                github_run_attempt=os.environ.get("GITHUB_RUN_ATTEMPT"),
                opened_at=_now(),
            )
        except (OSError, TypeError, ValueError) as exc:
            os.close(self._fd)
            self._fd = None
            _refuse(f"the journal could not be written ({type(exc).__name__})")

    # -- journal ------------------------------------------------------------

    def _append(self, event: str, **fields: Any) -> None:
        with self._lock:
            if self._fd is None:
                raise OSError("journal is closed")
            line = json.dumps({"event": event, "seq": self._seq, **fields}, sort_keys=True, allow_nan=False)
            data = memoryview((line + "\n").encode("utf-8"))
            try:
                while data:
                    data = data[os.write(self._fd, data):]
            except OSError:
                # A torn line makes the journal unreadable to the next
                # preflight, which refuses; this process stops admitting.
                self._journal_failed = True
                raise
            # The whole line is written, so its seq is spent even if the fsync
            # below fails; the next line must never repeat it.
            self._seq += 1
            try:
                os.fsync(self._fd)
            except OSError:
                self._journal_failed = True
                raise

    def _record(self, event: str, **fields: Any) -> None:
        """Journal a conclusion or stop without raising into the caller."""
        try:
            self._append(event, **fields)
        except Exception as exc:  # noqa: BLE001 - never displaces the provider's own outcome
            self._journal_failed = True
            print(f"[combined-usd] journal write failed ({type(exc).__name__})", file=sys.stderr)

    def _stop(self, reason: str, **fields: Any) -> None:
        with self._lock:
            if reason not in self.stops:
                self.stops.append(reason)
            self._record("stop", reason=reason, **fields)

    # -- state --------------------------------------------------------------

    def committed(self) -> Decimal:
        with self._lock:
            return self.seed.committed_floor() + self.spent + sum(self.pending.values(), Decimal(0))

    def _is_audio(self, model: Any) -> bool:
        # The pilot's own rule (gpt56_pilot_usd_budget._list_rates): any
        # gpt-audio* model has no Azure meter and takes the audio stand-in.
        return type(model) is str and model.startswith("gpt-audio")

    def _reserve_usd(self, model: Any, inputs: int, outputs: int) -> Decimal:
        if self._is_audio(model):
            rates = self._usd.AUDIO_STAND_IN_USD_PER_MILLION
            per_input = rates["input"] + rates["cache_write"]
            per_output = rates["output"]
        else:
            per_input = self.rates_sol.input + self.rates_sol.cache_write
            per_output = self.rates_sol.output
        return _ceil8((Decimal(inputs) * per_input + Decimal(outputs) * per_output) / _TOKENS_PER_MILLION)

    def _settled_usd(self, model: Any, response: Any) -> tuple[Decimal | None, dict[str, Any]]:
        from core.cost_metering import extract_usage

        usage = extract_usage(response)
        tokens = {
            "input_tokens": usage.input_tokens,
            "cached_input_tokens": usage.cached_input_tokens,
            "output_tokens": usage.output_tokens,
            "reasoning_tokens": usage.reasoning_tokens,
        }
        if self._is_audio(model):
            inputs, outputs = usage.input_tokens, usage.output_tokens
            if (type(inputs) is not int or type(outputs) is not int or inputs < 0 or outputs < 0):
                return None, tokens
            rates = self._usd.AUDIO_STAND_IN_USD_PER_MILLION
            amount = (Decimal(inputs) * rates["input"] + Decimal(outputs) * rates["output"]) / _TOKENS_PER_MILLION
            return _ceil8(amount), tokens
        return self._controls.list_price_usd(
            input_tokens=usage.input_tokens,
            cached_input_tokens=usage.cached_input_tokens,
            output_tokens=usage.output_tokens,
            reasoning_tokens=usage.reasoning_tokens,
            rates=self.rates_sol,
        ), tokens

    # -- the CostRecorder interface (core/cost_metering.py:691-692, :888-976) --

    def check_client(self, client: Any) -> None:
        # SDK retries are allowed, as the pilot decided on 2026-10-30
        # (gpt56_pilot_usd_budget.py:631-634); the reservation covers one.
        return None

    @contextmanager
    def grading_request(self) -> Iterator[None]:
        """Turn a refusal into the BaseException step 8 stops on.

        ``GradingUsdStopped`` passes the grader's ``except Exception``
        fallbacks, so a money stop never becomes a judge error or a smaller
        denominator. step 8 catches it at :3465-3474, saves the partial and
        returns 4.
        """
        try:
            yield
        except self._usd.PilotUsdRefused as refused:
            raise self._usd.GradingUsdStopped(refused.code) from None

    def reserve(self, *, task_id: str, provider: str, kwargs: Any) -> dict[str, Any]:
        usd = self._usd
        with self._lock:
            if self.stops:
                raise usd.PilotUsdRefused(self.stops[0], "grading")
            if self._journal_failed or self._fd is None:
                self._stop(UNVERIFIED, task_id=task_id, detail="journal unavailable")
                raise usd.PilotUsdRefused(usd.UNVERIFIED, "grading")
            try:
                model = kwargs.get("model") if type(kwargs) is dict else None
                # The #795-reviewed bound (:551-556): exact visible text, else
                # 8000 tokens per image, base64/100+1000 per audio clip, and
                # 32768 output tokens when the request names no limit.
                inputs, outputs = usd._request_allowance(kwargs)
                amount = self._reserve_usd(model, inputs, outputs)
                committed = self.committed()
            except Exception as exc:  # noqa: BLE001 - an unsized request is not sent
                self._stop(UNVERIFIED, task_id=task_id, detail=f"reservation not sized ({type(exc).__name__})")
                raise usd.PilotUsdRefused(usd.UNVERIFIED, "grading") from None
            if committed + amount > self.seed.ceiling_usd:
                self._stop(
                    CEILING,
                    task_id=task_id,
                    requested_reserve_usd=_money(amount),
                    committed_usd=_money(committed),
                )
                raise usd.PilotUsdRefused(usd.CEILING, "grading")
            self._tickets += 1
            ticket = f"g{self._tickets}"
            try:
                self._append(
                    "reserve",
                    ticket=ticket,
                    task_id=task_id,
                    provider=provider,
                    model=model if type(model) is str else None,
                    reserve_usd=_money(amount),
                    committed_usd=_money(committed + amount),
                )
            except Exception:  # noqa: BLE001 - an unjournaled request is not sent
                self._stop(UNVERIFIED, task_id=task_id, detail="journal write failed")
                raise usd.PilotUsdRefused(usd.UNVERIFIED, "grading") from None
            self.pending[ticket] = amount
            return {"ticket": ticket, "model": model, "reserve_usd": amount}

    def finish(self, ticket: Any, response: Any) -> None:
        """Settle at reported usage, or keep the whole reservation; never raises."""
        try:
            with self._lock:
                key = ticket.get("ticket") if isinstance(ticket, dict) else None
                reserved = self.pending.pop(key, None)
                if reserved is None:
                    return
                try:
                    amount, tokens = self._settled_usd(ticket.get("model"), response)
                except Exception:  # noqa: BLE001 - unreadable usage keeps the reservation
                    amount, tokens = None, {}
                if amount is None:
                    self.spent += reserved
                    self._record("abandon", ticket=key, reason="usage_unreported", spent_usd=_money(reserved))
                    return
                # A settlement above its reservation is booked as observed; it
                # is not a stop. The next reservation sees the larger total.
                self.spent += amount
                self._record("settle", ticket=key, spent_usd=_money(amount), reserve_usd=_money(reserved), **tokens)
        except Exception:  # noqa: BLE001 - see docstring
            self._journal_failed = True

    def abandon(self, ticket: Any) -> None:
        """Book the outstanding reservation of a request that failed; idempotent."""
        try:
            with self._lock:
                key = ticket.get("ticket") if isinstance(ticket, dict) else None
                reserved = self.pending.pop(key, None)
                if reserved is None:
                    return
                self.spent += reserved
                self._record("abandon", ticket=key, reason="request_failed", spent_usd=_money(reserved))
        except Exception:  # noqa: BLE001 - never displaces the provider's own error
            self._journal_failed = True

    def unattributed(self) -> NoReturn:
        # Pilot parity. Every grader call runs inside attributed() at
        # core/grader.py:574, so a call outside one is not a grading call.
        self._stop(UNKNOWN, detail="request outside any task's scope")
        raise self._usd.PilotUsdRefused(self._usd.UNKNOWN, "grading")

    def close(self, step8_exit: int | None) -> None:
        """Write the close line and release the journal; never raises."""
        with self._lock:
            if self._fd is None:
                return
            try:
                self._append(
                    "close",
                    step8_exit=step8_exit,
                    spent_usd=_money(self.spent),
                    pending_usd=_money(sum(self.pending.values(), Decimal(0))),
                    committed_usd=_money(self.committed()),
                    closed_at=_now(),
                )
            except Exception as exc:  # noqa: BLE001 - step 8's exit code must survive
                print(f"[combined-usd] journal close failed ({type(exc).__name__})", file=sys.stderr)
            finally:
                try:
                    os.close(self._fd)
                except OSError:
                    pass
                self._fd = None


# -- wiring into step 8 -------------------------------------------------------


def _runner_receipt() -> Any:
    try:
        from core import runner_environment

        return runner_environment.receipt("grading")
    except Exception:  # noqa: BLE001 - a refusal is printed with or without it
        return None


def _refusal_record(code: str, detail: str) -> dict[str, Any]:
    return {
        "status": "refused",
        "source": "grading",
        "reason": code,
        "detail": detail,
        "actual_billing_hard_limit_verified": False,
        "runner_evidence": _runner_receipt(),
    }


def _refuse_exit(admission: CombinedGradingAdmission, reason: str, detail: str) -> NoReturn:
    """Stop step 8 where its cost ledger is opened, before any judge exists.

    Printed in the shape of step 8's refuse_pilot_money (:2544-2549), plus the
    detail. step 8 has registered nothing by then that needs this ledger.
    """
    print(json.dumps(_refusal_record(reason, detail), sort_keys=True), file=sys.stderr)
    admission._stop(reason, detail=detail)
    raise SystemExit(REFUSED_EXIT)


def install_admission(step8: Any, admission: CombinedGradingAdmission) -> Callable[..., Any]:
    """Rebind ``step8.open_cost_recorder`` so step 8's one ledger carries ``admission``.

    Returns the binding it replaced, so a caller can put it back.
    """
    import core.cost_metering as cm

    if step8.open_cost_recorder is not cm.open_cost_recorder:
        _refuse("step8 cost-recorder binding drifted")
    original = step8.open_cost_recorder

    def open_cost_recorder_with_combined_usd(path: Any, **kwargs: Any) -> tuple[Any, str | None]:
        if kwargs.get("usd_admission") is not None:
            _refuse_exit(admission, UNVERIFIED, "a pilot admission was already chosen")
        kwargs.pop("usd_admission", None)
        recorder, note = original(path, usd_admission=admission, **kwargs)
        # Without a recorder step 8 grades unmetered (it fails open for every
        # run but the pilot), and nothing would hold the ceiling.
        if recorder is None:
            _refuse_exit(admission, UNVERIFIED, note or "cost ledger could not be opened")
        return recorder, note

    step8.open_cost_recorder = open_cost_recorder_with_combined_usd
    return original


def _exit_status(code: Any) -> int:
    """The process status ``SystemExit(code)`` would produce."""
    if code is None:
        return 0
    if isinstance(code, int) and not isinstance(code, bool):
        return code
    print(code, file=sys.stderr)
    return 1


def run(step8_argv: Sequence[str], inference_revision: str) -> int:
    """Run step 8 under its approval's USD admission; returns its exit code.

    Refused from step 8's arguments alone, before any file is read: a dry
    run, the paused pilot's workspace, a source other than local, more than
    one shard, and any ``--tasks`` or non-zero ``--limit`` (the approval, not
    the dispatch, defines the scope).
    """
    import step8_grade as step8

    saved_argv = sys.argv
    sys.argv = ["step8_grade.py", *step8_argv]
    try:
        args = step8.parse_args()
    finally:
        sys.argv = saved_argv
    try:
        if args.dry_run:
            _refuse("a dry run makes no paid call; run step8_grade.py directly")
        if args.pilot_usd_workspace:
            _refuse("the paused pilot keeps its own admission")
        if args.source != "local":
            _refuse("only --source local is graded")
        if args.shard_count != 1:
            _refuse("an approved grade is graded by one unsharded process")
        # The approval defines the scope its ceiling was sized for: the whole
        # published run, or the config's pinned task list. --tasks or --limit
        # would grade a subset (a _diagnostic/ grade) and spend under that
        # ceiling all the same. grade-run.yml passes tasks and tasks_limit
        # here only, so this is where they are refused; nothing is read and no
        # journal is opened first.
        if args.tasks or args.limit:
            _refuse("an approved grade covers its approval's whole scope; --tasks and --limit "
                    "would grade a subset under its ceiling")
        seed = preflight(args.experiment_yaml_name, args.config, inference_revision, args.shard_count)
        if seed is None:
            _refuse("no approved USD admission holds this grade; run step8_grade.py directly")
        run_id = os.environ.get("GITHUB_RUN_ID", "")
        run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
        if not _RUN_ID.fullmatch(run_id) or not _RUN_ATTEMPT.fullmatch(run_attempt):
            _refuse("GITHUB_RUN_ID and GITHUB_RUN_ATTEMPT name the journal and must be set")
        # A re-run of a failed job can follow an attempt whose journal never
        # reached main; its preflight would not see that spend and could
        # spend it again. sol_batch_controls refuses solve re-runs the same way.
        if run_attempt != "1":
            _refuse("a GitHub re-run would forget spend from an unpublished journal; dispatch a fresh run")
        try:
            inference = json.loads(
                (Path("workspace") / "step2_inference_results.json").read_text(encoding="utf-8")
            )
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            _refuse(f"the downloaded inference could not be read ({type(exc).__name__})")
        # The seed was priced at the dispatched revision; grading another
        # commit of the same dataset under it would spend against the wrong
        # solve run.
        if not isinstance(inference, dict) or inference.get("source_revision") != inference_revision:
            _refuse("the downloaded inference is not the dispatched revision")
        journal = (
            step8._repo_root() / JOURNAL_DIR / step8._experiment_path_slug(args.experiment_yaml_name)
            / f"run-{run_id}-{run_attempt}.combined_usd.jsonl"
        )
        try:
            journal.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            _refuse(f"the journal directory could not be created ({type(exc).__name__})")
        admission = CombinedGradingAdmission(seed, journal)
    except CombinedUsdRefused as refused:
        print(json.dumps(_refusal_record(refused.code, refused.detail), sort_keys=True), file=sys.stderr)
        return REFUSED_EXIT

    print(
        f"[combined-usd] committed {_money(seed.committed_floor())} of {_money(seed.ceiling_usd)} "
        f"before grading (solve {_money(seed.solve_usd)}, narrative "
        f"{_money(seed.narrative_allowance_usd)}, earlier grading {_money(seed.prior_grading_usd)}); "
        f"journal {journal.name}",
        flush=True,
    )
    rc: int | None = None
    original: Callable[..., Any] | None = None
    try:
        try:
            original = install_admission(step8, admission)
        except CombinedUsdRefused as refused:
            print(json.dumps(_refusal_record(refused.code, refused.detail), sort_keys=True), file=sys.stderr)
            admission._stop(refused.code, detail=refused.detail)
            rc = REFUSED_EXIT
            return rc
        sys.argv = ["step8_grade.py", *step8_argv]
        try:
            rc = step8.main()
        except SystemExit as exited:
            rc = _exit_status(exited.code)
        return rc
    finally:
        sys.argv = saved_argv
        if original is not None:
            step8.open_cost_recorder = original
        admission.close(rc)
        if CEILING in admission.stops:
            print("::error::combined solve+grade USD ceiling reached", flush=True)
        elif admission.stops:
            print(f"::error::combined solve+grade USD admission stopped: {admission.stops[0]}", flush=True)


# -- command line -------------------------------------------------------------


def _write_github_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sol_batch_grading.py",
        description="Owner-approved USD admissions for paid Sol Max grades (sol_batch_grading.APPROVALS).",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("preflight", help="Model-free admission check; writes enabled=true|false.")
    check.add_argument("--experiment", required=True)
    check.add_argument("--config", required=True)
    check.add_argument("--inference-revision", required=True)
    check.add_argument("--shard-count", required=True, type=int)
    grade = commands.add_parser("run", help="Run step 8 under the admission: run --inference-revision SHA -- <step8 args>.")
    grade.add_argument("--inference-revision", required=True)
    journal = commands.add_parser("check-journal", help="Print what one journal spent.")
    journal.add_argument("--journal", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = _parser()
    step8_argv: list[str] = []
    if arguments[:1] == ["run"]:
        # Split by hand: everything after "--" belongs to step 8, flags and all.
        if "--" not in arguments:
            parser.error("run needs '--' before the step 8 arguments")
        split = arguments.index("--")
        arguments, step8_argv = arguments[:split], arguments[split + 1:]
        if not step8_argv:
            parser.error("run needs the step 8 arguments after '--'")
    options = parser.parse_args(arguments)
    try:
        if options.command == "preflight":
            enabled = applies(options.experiment, options.config)
            _write_github_output("enabled", "true" if enabled else "false")
            if not enabled:
                print(json.dumps({"enabled": False}, sort_keys=True))
                return 0
            seed = preflight(options.experiment, options.config, options.inference_revision, options.shard_count)
            if seed is None:
                _refuse("applicability changed between two reads")
            print(
                f"[combined-usd] committed {_money(seed.committed_floor())} of "
                f"{_money(seed.ceiling_usd)} before grading; grading may reserve up to "
                f"{_money(seed.ceiling_usd - seed.committed_floor())}",
                file=sys.stderr,
            )
            print(json.dumps(seed.as_record(), sort_keys=True))
            return 0
        if options.command == "run":
            return run(step8_argv, options.inference_revision)
        spent = journal_spend(options.journal)
        print(json.dumps({"spent_usd": _money(spent)}, sort_keys=True))
        return 0
    except CombinedUsdRefused as refused:
        print(json.dumps(_refusal_record(refused.code, refused.detail), sort_keys=True), file=sys.stderr)
        return REFUSED_EXIT


if __name__ == "__main__":
    sys.exit(main())
