"""Read committed, canonical single-shard evidence; never authorize new spend.

The workflow's actor/context checks and protected ``grading`` environment stay
in place. As on the multi-shard path, an exact bot commit author is the lineage
proof, not an assertion that a particular human clicked approval. The normal
combined-USD preflight and per-request admission still run after inheritance.
Only canonical, unsharded runs are handled here; diagnostics/repeats fall back
to the existing environment gate rather than inheriting another output's scope.
"""

from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import quote


class InheritanceRefused(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise InheritanceRefused(reason)


class CommittedFiles:
    """All evidence, including authorship, is read at the dispatch's main SHA."""

    def __init__(self, repository, revision):
        self.repository = repository
        self.revision = revision

    def api(self, route, *, raw=False):
        accept = "application/vnd.github.raw+json" if raw else "application/vnd.github+json"
        return subprocess.run(
            ["gh", "api", "--method", "GET", "--header", f"Accept: {accept}",
             f"repos/{self.repository}/{route}"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        ).stdout

    def entries(self, path):
        rows = json.loads(self.api(f"contents/{quote(path, safe='/')}?ref={self.revision}"))
        require(type(rows) is list and len(rows) < 1000, "directory absent or truncated")
        require(all(type(row) is dict for row in rows), "invalid directory entry")
        return rows

    def raw(self, path):
        return self.api(f"contents/{quote(path, safe='/')}?ref={self.revision}", raw=True)

    def author(self, path, expected):
        rows = json.loads(self.api(
            f"commits?path={quote(path, safe='/')}&sha={self.revision}&per_page=1"))
        require(type(rows) is list and len(rows) == 1, "missing committed author")
        require(rows[0]["commit"]["author"]["email"] == expected, "committed author mismatch")


def money(value):
    require(type(value) is str, "USD amount not reported")
    result = Decimal(value)
    require(result.is_finite() and result >= 0, "invalid USD amount")
    return result


def verify_journal(raw, *, experiment, config_name, inference, run_id, attempt):
    require(raw.endswith(b"\n"), "torn USD journal")
    rows = [json.loads(line) for line in raw.splitlines()]
    require(len(rows) >= 2 and all(type(row) is dict and type(row.get("seq")) is int
            and row["seq"] == index for index, row in enumerate(rows)), "invalid USD journal sequence")
    opened, closed = rows[0], rows[-1]
    require(opened.get("event") == "open" and opened.get("schema") == "sol-batch-grading-journal-v1",
            "USD journal owner not reported")
    for key, expected in (("experiment_id", experiment), ("config_name", config_name),
                          ("inference_revision", inference), ("github_run_id", run_id),
                          ("github_run_attempt", attempt)):
        require(opened.get(key) == expected, f"USD journal {key} mismatch")
    require(closed.get("event") == "close" and type(closed.get("step8_exit")) is int
            and closed["step8_exit"] == 7, "USD journal is not a resumable chunk")
    pending, concluded, spent = {}, set(), Decimal(0)
    for row in rows[1:-1]:
        ticket = row.get("ticket")
        require(type(ticket) is str and bool(ticket), "USD journal ticket missing")
        if row.get("event") == "reserve":
            require(ticket not in pending and ticket not in concluded, "USD journal ticket reused")
            pending[ticket] = money(row.get("reserve_usd"))
        else:
            require(row.get("event") in {"settle", "abandon"} and ticket in pending,
                    "USD journal conclusion mismatch")
            spent += money(row.get("spent_usd"))
            del pending[ticket]
            concluded.add(ticket)
    require(not pending and money(closed.get("pending_usd")) == 0, "USD journal still pending")
    require(money(closed.get("spent_usd")) == spent, "USD journal spend mismatch")
    floor = money(opened.get("committed_floor_usd"))
    require(floor == sum((money(opened.get(key)) for key in (
        "solve_usd", "narrative_allowance_usd", "prior_grading_usd")), Decimal(0)),
        "USD committed floor mismatch")
    committed = money(closed.get("committed_usd"))
    require(committed == floor + spent and committed < money(opened.get("ceiling_usd")),
            "USD ceiling reached or totals disagree")
    return opened


def verify_journal_history(files, journal, opened, author):
    """A later/changed journal must not hide spend behind an older partial."""
    directory = journal.rsplit("/", 1)[0]
    previous = opened.get("prior_journals")
    require(type(previous) is list, "prior USD journals not reported")
    expected, total = {journal}, Decimal(0)
    for row in previous:
        require(type(row) is dict, "invalid prior USD journal")
        path = row.get("path")
        require(type(path) is str and path.startswith(directory + "/")
                and re.fullmatch(r"run-[1-9][0-9]{0,19}-[1-9][0-9]{0,5}\.combined_usd\.jsonl",
                                 path[len(directory) + 1:]) and path not in expected,
                "prior USD journal path mismatch")
        files.author(path, author)
        require(hashlib.sha256(files.raw(path)).hexdigest() == row.get("sha256"),
                "prior USD journal bytes changed")
        total += money(row.get("spent_usd"))
        expected.add(path)
    actual = set()
    for row in files.entries(directory):
        name = row.get("name")
        if type(name) is str and name.startswith("run-") and name.endswith(".combined_usd.jsonl"):
            require(row.get("type") == "file" and "/" not in name, "invalid USD journal entry")
            actual.add(f"{directory}/{name}")
    require(actual == expected and total == money(opened.get("prior_grading_usd")),
            "committed USD journal set or prior spend changed")


def resolve(files, env, config_name, config_bytes):
    for key, expected in (("GRADE_SHARD_COUNT", "1"), ("GRADE_SHARD_INDEX", "0"),
                          ("GRADE_RUN_ORDINAL", "1"), ("GRADE_TASKS_LIMIT", "0"),
                          ("GRADE_TASKS", ""), ("GRADE_FORCE", "false"),
                          ("GRADE_DRY_RUN", "false"), ("GRADE_PAID_APPROVAL", "true"),
                          ("GRADE_RESUME", "true"), ("GITHUB_ACTOR", "github-actions[bot]"),
                          ("GITHUB_TRIGGERING_ACTOR", "github-actions[bot]")):
        require(env.get(key) == expected, f"{key} does not describe the approved continuation")
    require(re.fullmatch(r"(?:[1-9]|10)", env.get("GRADE_RESUME_CHUNK", "")), "invalid resume chunk")
    experiment, slug = env["GRADE_EXPERIMENT_YAML"], env["GRADE_EXPERIMENT_SLUG"]
    inference, author = env["GRADE_INFERENCE_REVISION"], env["GRADE_BOT_EMAIL"]
    require(slug == experiment.replace("/", "__") and re.fullmatch(r"[0-9a-f]{40}", inference),
            "experiment or inference identity missing")
    config_hash = hashlib.sha256(config_bytes).hexdigest()[:16]
    rows = files.entries("data/grades")
    candidates = [row["name"] for row in rows if row.get("type") == "file"
                  and type(row.get("name")) is str and "/" not in row["name"]
                  and row["name"].startswith(f"{slug}__") and row["name"].endswith(".json")
                  and f"__{config_name}__cfg_{config_hash}__" in row["name"]
                  and f"__inference_{inference}__" in row["name"]]
    require(len(candidates) == 1, "missing or ambiguous committed single-shard partial")
    path = f"data/grades/{candidates[0]}"
    files.author(path, author)
    partial = json.loads(files.raw(path))
    require(partial.get("run_status") == "partial" and type(partial.get("tasks")) is list,
            "committed grade is not partial")
    require(partial.get("experiment_yaml_name") == experiment and partial.get("experiment_id") == experiment
            and partial.get("source_inference_revision") == inference, "partial experiment/inference mismatch")
    require(partial["judge"].get("config_name") == config_name
            and partial["judge"].get("config_hash") == config_hash, "partial grading config mismatch")
    source = partial.get("grader_source_hash")
    require(type(source) is str and re.fullmatch(r"[0-9a-f]{64}", source)
            and f"__src_{source[:16]}__" in path, "partial source binding missing")
    evidence = partial["runner_evidence"]
    body = {key: evidence[key] for key in ("schema_version", "stage", "observation")}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"),
                                       allow_nan=False).encode()).hexdigest()
    require(evidence.get("sha256") == digest and body["schema_version"] == "native-runner-evidence-v1"
            and body["stage"] == "grading", "grading environment receipt mismatch")
    observed = body["observation"]
    for key, expected in (("github_actions", "true"), ("runner_environment", "github-hosted"),
                          ("os_id", "ubuntu"), ("os_version_id", "24.04"), ("image_os", "ubuntu24"),
                          ("platform_system", "Linux"), ("github_hosted", True),
                          ("eligible_for_execution", True)):
        require(type(observed.get(key)) is type(expected) and observed[key] == expected,
                f"grading environment {key} mismatch")
    run_id, attempt = observed.get("run_id"), observed.get("run_attempt")
    require(type(run_id) is str and re.fullmatch(r"[1-9][0-9]{0,19}", run_id)
            and type(attempt) is str and re.fullmatch(r"[1-9][0-9]{0,5}", attempt), "prior run missing")
    journal = f"data/grades/_combined_usd/{slug}/run-{run_id}-{attempt}.combined_usd.jsonl"
    files.author(journal, author)
    opened = verify_journal(files.raw(journal), experiment=experiment, config_name=config_name,
                            inference=inference, run_id=run_id, attempt=attempt)
    verify_journal_history(files, journal, opened, author)
    # A chunk can finish no whole task but still advance its first task. That
    # continuation needs the committed checkpoint, never the USD journal alone.
    progress = []
    if any(row.get("name") == "_progress" and row.get("type") == "dir" for row in rows):
        prefix = candidates[0][:-5] + "__"
        for row in files.entries("data/grades/_progress"):
            name = row.get("name")
            if type(name) is not str or not name.startswith(prefix):
                continue
            require(row.get("type") == "file" and "/" not in name and name.endswith(".json"),
                    "invalid progress entry")
            checkpoint_path = f"data/grades/_progress/{name}"
            files.author(checkpoint_path, author)
            checkpoint = json.loads(files.raw(checkpoint_path))
            require(checkpoint.get("format") == "task-progress-v1"
                    and checkpoint.get("grader_source_hash") == source
                    and type(checkpoint.get("completed_items")) is list and checkpoint["completed_items"],
                    "progress identity or completed items missing")
            task_id = checkpoint.get("task_id")
            require(type(task_id) is str and re.fullmatch(r"[A-Za-z0-9_-]+", task_id)
                    and name == f"{prefix}{task_id}.json", "progress task binding mismatch")
            progress.append(checkpoint)
    require(partial["tasks"] or progress, "partial has neither completed tasks nor committed progress")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-name", required=True)
    parser.add_argument("--config-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        env = os.environ
        revision = env["GITHUB_SHA"]
        require(re.fullmatch(r"[0-9a-f]{40}", revision), "dispatch SHA missing")
        print(resolve(CommittedFiles(env["GITHUB_REPOSITORY"], revision), env,
                      args.config_name, args.config_file.read_bytes()))
    except Exception as error:
        # A GitHub read error, malformed artifact or mismatch always keeps the
        # protected environment gate. Never print provider bodies or tokens.
        detail = str(error) if isinstance(error, InheritanceRefused) else type(error).__name__
        print(f"[inherit] single-shard evidence refused: {detail}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
