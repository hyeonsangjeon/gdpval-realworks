"""Deterministic, serial ABBA admission; no dispatch, credentials or model client.

The registered runs are blocks of five tasks, not an ABBA block per task.
The existing private cell CAS writes the schedule claim/capture atomically
with admission/output. A lost claim or missing capture never grants a retry.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path

from core.agentic_v2_preregistration import seal
from core.time_budget_observation_deadline import TASK_IDS
import gpt54_time_budget_comparison as registration

HELPER = "batch-runner/gpt54_time_budget_schedule.py"
VERSION = "gpt54-time-budget-serial-abba-v1"
MAX_OBSERVATIONS = 20
CONCURRENCY_GROUP = "gpt54-time-budget-first-v2-observation"
CLAIM_NAME = "schedule-admission.json"
CAPTURE_NAME = "schedule-capture.json"
WORKFLOWS = {
    "sandbox_v2": ".github/workflows/gpt54-time-budget-first-v2.yml",
    "codex": ".github/workflows/gpt54-time-budget-first-codex.yml",
}
REASONS = frozenset({
    "schedule_contract_mismatch", "observation_not_registered", "observation_limit_exceeded",
    "observation_already_captured", "observation_already_claimed", "observation_out_of_order",
    "previous_capture_unverified", "previous_observation_uncertain", "schedule_history_invalid",
    "schedule_source_changed", "schedule_record_mismatch",
})


class ScheduleRefused(ValueError):
    """Fixed nonsecret reason only; never provider/transport exception text."""


def _require(value: bool, reason: str) -> None:
    if not value:
        raise ScheduleRefused(reason)


@dataclass(frozen=True)
class ScheduledObservation:
    sequence: int  # 1..20, one Actions job per entry.
    abba_position: int  # 1..4, matches registration abba_index + 1.
    study_id: str
    run_id: str
    condition: str
    repeat: int
    task_id: str

    @property
    def cell(self) -> dict:
        return {key: getattr(self, key) for key in ("study_id", "run_id", "condition", "repeat", "task_id")}

    @property
    def observation_id(self) -> str:
        # Source/image updates cannot mint a second ID for a consumed cell.
        return seal({"format": VERSION, **asdict(self)})

    @property
    def prefix(self) -> str:
        return "time-budget/" + self.study_id + "/" + self.run_id + "/" + self.task_id

    def binding(self, schedule: tuple[ScheduledObservation, ...]) -> dict:
        return {"format": VERSION, "observation_id": self.observation_id,
                "sequence": self.sequence, "abba_position": self.abba_position,
                "schedule_sha256": seal([asdict(item) for item in schedule]), "cell": self.cell}


def build_schedule(plan: dict) -> tuple[ScheduledObservation, ...]:
    """Expand the fixed registration only. This is intent, not launch authority."""
    try:
        registration._expect("schedule_contract_mismatch", plan["scope"], registration._policy()["scope"])
        _require(plan["study_id"] == registration.STUDY_ID
                 and tuple(item["task_id"] for item in plan["shared"]["dataset"]["tasks"]) == TASK_IDS,
                 "schedule_contract_mismatch")
        expected = [{"run_id": f"gpt54_time_budget_v1_{suffix}_r{repeat}", "condition": condition,
                     "repeat": repeat, "task_count": 5}
                    for condition, suffix, repeat in registration.RUN_ORDER]
        registration._expect("schedule_contract_mismatch", plan["runs"], expected)
        result = tuple(ScheduledObservation(
            (position - 1) * 5 + index, position, registration.STUDY_ID,
            run["run_id"], run["condition"], run["repeat"], task)
            for position, run in enumerate(plan["runs"], 1)
            for index, task in enumerate(TASK_IDS, 1))
        _require(len(result) == MAX_OBSERVATIONS == len({item.observation_id for item in result}),
                 "schedule_contract_mismatch")
        return result
    except (KeyError, TypeError, registration.TimeBudgetRegistrationRefused):
        raise ScheduleRefused("schedule_contract_mismatch") from None


def select(schedule: tuple[ScheduledObservation, ...], cell: dict) -> ScheduledObservation:
    selected = [item for item in schedule if registration._canonical_json(item.cell)
                == registration._canonical_json(cell)]
    _require(len(selected) == 1, "observation_not_registered")
    return selected[0]


def next_observation(schedule: tuple[ScheduledObservation, ...], *, captured_ids: list[str],
                     claimed_ids: list[str], requested_id: str | None = None) -> ScheduledObservation:
    """No holes, duplicates, retries, score selection or 21st observation."""
    order = [item.observation_id for item in schedule]
    _require(len(order) == MAX_OBSERVATIONS and len(set(order)) == len(order), "schedule_contract_mismatch")
    _require(len(captured_ids) <= MAX_OBSERVATIONS and len(claimed_ids) <= MAX_OBSERVATIONS,
             "observation_limit_exceeded")
    _require(len(set(captured_ids)) == len(captured_ids) and len(set(claimed_ids)) == len(claimed_ids)
             and set(captured_ids) <= set(claimed_ids) <= set(order), "schedule_history_invalid")
    if requested_id is not None:
        _require(requested_id in order, "observation_not_registered")
        _require(requested_id not in captured_ids, "observation_already_captured")
        _require(requested_id not in claimed_ids, "observation_already_claimed")
    _require(len(captured_ids) < MAX_OBSERVATIONS, "observation_limit_exceeded")
    _require(captured_ids == order[:len(captured_ids)], "observation_out_of_order")
    _require(claimed_ids == captured_ids, "previous_observation_uncertain")
    selected = schedule[len(captured_ids)]
    _require(requested_id is None or requested_id == selected.observation_id, "observation_out_of_order")
    return selected


def job_descriptors(plan: dict) -> dict:
    schedule = build_schedule(plan)
    return {"format": VERSION, "launch_allowed": False, "execution_enabled": False,
            "max_observations": MAX_OBSERVATIONS, "inference_concurrency": 1,
            "jobs": [{**item.binding(schedule), "workflow": WORKFLOWS[item.condition],
                      "job": "observation", "runner": "ubuntu-24.04", "concurrency_group": CONCURRENCY_GROUP,
                      "requires_capture": None if item.sequence == 1 else schedule[item.sequence - 2].observation_id}
                     for item in schedule]}


def claim_record(context: dict, claim: dict) -> dict:
    schedule = build_schedule(context["plan"])
    selected = select(schedule, context["cell"])
    from codex_budget_pilot_retention import _encoded, _object

    return {"format": VERSION, "binding": selected.binding(schedule),
            "source": context["request"]["source"], "registration_sha256": seal(context["plan"]),
            "claim": _object(selected.prefix + "/admission.json", _encoded(claim)),
            "state": "permanently_claimed_not_captured"}


def capture_record(context: dict, admission: dict, manifest: dict, payload: dict | None) -> dict:
    from codex_budget_pilot_retention import _encoded, _object

    value = claim_record(context, admission["claim"])
    control = None if payload is None else payload["time_budget_observation"]
    confirmed = (control is not None and control["cleanup_complete"] is True
                 and control["host_reusable"] is True and manifest["execution_receipt"]["outcome"] == "returned")
    return {**value, "state": "captured" if confirmed else "uncertain_stop",
            "claim_commit": admission["returned_commit"],
            "output": _object(select(build_schedule(context["plan"]), context["cell"]).prefix
                              + "/output-manifest.json", _encoded(manifest))}


def require_next_remote(context: dict, api, token, deadline, *, repository: str, parent: str,
                        cache: Path) -> None:
    """Read metadata only at the exact CAS parent; never adopt historical bodies.

    The caller commits this cell once with parent_commit=parent. Both harnesses
    share that parent and the Actions concurrency group. A competing claimant
    either sees the occupied prefix or loses the CAS before model admission.
    """
    from huggingface_hub import RepoFolder
    import codex_budget_pilot_output as storage
    from codex_budget_pilot_retention import _control, _objects

    schedule = build_schedule(context["plan"])
    selected = select(schedule, context["cell"])
    storage._remaining(deadline)
    found = api.get_paths_info(repo_id=repository, repo_type="dataset", revision=parent,
                               paths=[item.prefix for item in schedule], token=token)
    _require(type(found) is list and len(found) <= MAX_OBSERVATIONS
             and all(isinstance(item, RepoFolder) for item in found), "schedule_history_invalid")
    occupied = [item.path for item in found]
    _require(len(set(occupied)) == len(occupied)
             and set(occupied) <= {item.prefix for item in schedule}, "schedule_history_invalid")
    if selected.prefix in occupied:
        captured = api.get_paths_info(repo_id=repository, repo_type="dataset", revision=parent,
                                     paths=[selected.prefix + "/output-manifest.json"], token=token)
        raise ScheduleRefused("observation_already_captured" if captured else "observation_already_claimed")
    _require(set(occupied) == {item.prefix for item in schedule[:selected.sequence - 1]},
             "observation_out_of_order")
    captured_ids = []
    for prior in schedule[:selected.sequence - 1]:
        try:
            record, _ = _control(api, repository, parent, prior.prefix + "/" + CAPTURE_NAME,
                                 cache, token, deadline)
        except (OSError, ValueError):
            raise ScheduleRefused("previous_capture_unverified") from None
        _require(set(record) == {"format", "binding", "source", "registration_sha256", "claim", "state",
                                  "claim_commit", "output"}
                 and record["format"] == VERSION
                 and registration._canonical_json(record["binding"])
                     == registration._canonical_json(prior.binding(schedule)),
                 "schedule_record_mismatch")
        _require(record["source"] == context["request"]["source"]
                 and record["registration_sha256"] == seal(context["plan"]), "schedule_source_changed")
        _require(record["state"] == "captured", "previous_observation_uncertain")
        _require(storage._hash(record["claim_commit"], 40), "schedule_record_mismatch")
        for key, suffix in (("claim", "admission.json"), ("output", "output-manifest.json")):
            obj = record[key]
            _require(type(obj) is dict and set(obj) == {"path", "size", "sha256", "git_blob_sha1"}
                     and obj["path"] == prior.prefix + "/" + suffix
                     and storage._hash(obj["sha256"]) and storage._hash(obj["git_blob_sha1"], 40)
                     and type(obj["size"]) is int and 0 < obj["size"] <= storage.MAX_MANIFEST_BYTES,
                     "schedule_record_mismatch")
        _objects(api, repository, parent, [record["claim"]], token, deadline, written_at=record["claim_commit"])
        _objects(api, repository, parent, [record["output"]], token, deadline)
        captured_ids.append(prior.observation_id)
    next_observation(schedule, captured_ids=captured_ids, claimed_ids=list(captured_ids),
                     requested_id=selected.observation_id)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=registration.PLAN)
    args = parser.parse_args(argv)
    try:
        print(registration._canonical_json(job_descriptors(registration.load_registration(args.manifest))))
        return 0  # Only model-free descriptors; never permission to launch.
    except (ScheduleRefused, registration.TimeBudgetRegistrationRefused) as error:
        print(json.dumps({"launch_allowed": False, "reason": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
