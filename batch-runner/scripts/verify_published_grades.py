#!/usr/bin/env python3
"""Check the commit a grading run actually pushed, at that commit.

A grading run ends by committing its grade file to ``main`` and pushing. The
push is made with ``GITHUB_TOKEN``, and GitHub does not start a workflow for a
``push`` event that token produced -- documented behaviour, so recursion is
impossible by construction. The consequence is that the result of a paid run
lands on ``main`` and **no check runs on it**. Not a check that failed: no run
row at all.

That is not hypothetical. ``94bb8fa`` and ``602cea4`` published a re-graded
smoke on 2026-09-07. The last Backend Tests run on ``main`` before them was
``89e242d``, green, two hours earlier -- green about a tree that no longer
existed. The next was ``972f52a``, the merge that already contained the fix.
For the two hours in between, ``main`` was red, the badge said green, and the
five failures surfaced only when a *different* pull request (#447) rebuilt from
a ``main`` that had quietly changed underneath it. A human PR carried the
failure of somebody else's publish.

This is the follow-up check. It reads the commits the run pushed, proves they
are on the branch they claim to be on, and re-verifies what they published --
result, schema, ledger, aggregation -- with no model call and no credential.

Four questions, in the order a defect would show up in:

  * Is the commit actually published? A SHA the runner holds locally is not
    evidence; it has to be an ancestor of the branch that was pushed to.
  * Does the grade file at that commit still parse, and does it satisfy the
    schema the pipeline validates against?
  * Does its cost receipt reconcile against its own ledger? (Delegated whole to
    ``verify_cost_ledger.py``; this file re-implements none of it.)
  * Does the dashboard aggregation still run clean over the tree that now
    contains it?

Run it against a checkout of the exact commit:

    python batch-runner/scripts/verify_published_grades.py \\
        --commits 94bb8fa 602cea4 --json

The exit code is 0 only when every check passed. There is deliberately no flag
that skips a check or downgrades one to a warning: a check that cannot be
performed is a failure, because "could not tell" and "fine" were the same
silence this exists to end.

What it does NOT do: judge the grading, re-grade anything, call a model, or
touch the published commit. A run may score badly and publish a flawless
receipt. Nothing here rewrites, reverts or deletes what was published -- the
failing artifact is the evidence, and it is left exactly where it landed.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
BATCH_RUNNER_ROOT = SCRIPTS_DIR.parent
REPO_ROOT = BATCH_RUNNER_ROOT.parent

if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

# The aggregation the dashboard build actually runs. Deliberately the whole
# npm target rather than aggregate-grades.mjs alone: that script reads
# reports-index.json, which an earlier script in the chain produces, and
# running it by itself silently degrades every qa_score to null. Checking a
# weaker aggregation than the one that ships would be checking the wrong thing.
DEFAULT_AGGREGATE_CMD = "npm run aggregate"

#: Where the dashboard aggregator looks. It is a flat ``readdir`` of
#: ``data/grades`` filtered to ``.json``, so a grade published into a
#: subdirectory -- a cohort folder, or the ``_diagnostic`` fork a re-run at a
#: moved fingerprint lands in -- is out of its reach by design. Such a file is
#: reported as out-of-scope with the reason named, not counted as aggregated.
AGGREGATED_DIR = Path("data/grades")


class Finding:
    """One check's verdict, with the evidence that produced it.

    Same shape as ``verify_cost_ledger.Finding`` on purpose: the two reports
    are read side by side and by the same summary renderer.
    """

    def __init__(self, check: str, ok: bool, detail: str, data: Any = None) -> None:
        self.check = check
        self.ok = ok
        self.detail = detail
        self.data = data

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"check": self.check, "ok": self.ok, "detail": self.detail}
        if self.data is not None:
            out["data"] = self.data
        return out


class GitError(RuntimeError):
    """git could not answer. Never softened into "nothing to check"."""


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed ({proc.returncode}): "
            f"{(proc.stderr or proc.stdout).strip()}"
        )
    return proc.stdout


def resolve_commits(repo: Path, commits: list[str]) -> list[str]:
    """Expand caller-supplied revisions to full SHAs, order preserved.

    Abbreviated SHAs are accepted because that is what a human pastes from a
    log; ``rev-parse`` is what decides, so an ambiguous or absent one raises
    rather than being dropped from the list.
    """
    resolved: list[str] = []
    for rev in commits:
        full = _git(repo, "rev-parse", "--verify", f"{rev}^{{commit}}").strip()
        if full not in resolved:
            resolved.append(full)
    return resolved


def check_published(repo: Path, commits: list[str], ref: str) -> Finding:
    """Every named commit must be an ancestor of the ref it was pushed to.

    This is the check that stops the whole report from being a story about a
    commit that never left the runner. A local SHA proves the run *made* a
    commit; only ancestry proves anybody else can see it.

    It also fails when the ref itself is unknown, rather than treating an
    unresolvable ref as "no contradiction found".
    """
    try:
        head = _git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").strip()
    except GitError as exc:
        return Finding(
            "published",
            False,
            f"cannot resolve {ref}, so publication cannot be established: {exc}",
            {"ref": ref},
        )

    orphaned = []
    for sha in commits:
        proc = subprocess.run(
            ["git", "-C", str(repo), "merge-base", "--is-ancestor", sha, head],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            orphaned.append(sha)

    if orphaned:
        return Finding(
            "published",
            False,
            f"{len(orphaned)} commit(s) are not on {ref}: {', '.join(orphaned)}. "
            "A commit that is not on the branch was not published, and "
            "verifying it would describe a tree nobody else has.",
            {"ref": ref, "ref_head": head, "orphaned": orphaned},
        )
    return Finding(
        "published",
        True,
        f"all {len(commits)} commit(s) are ancestors of {ref} ({head[:12]})",
        {"ref": ref, "ref_head": head, "commits": commits},
    )


def grade_files_in(repo: Path, commits: list[str]) -> tuple[list[Path], list[str]]:
    """The grade JSONs those commits touched, and the ones they deleted.

    Scoped to the named commits rather than a diff between two points: a
    rebase can interleave another shard's commits into the same range, and
    failing this run because a sibling published something is a false alarm
    that trains people to ignore the check.

    A deletion is returned separately instead of being filtered out. Removing a
    published grade is not a thing this pipeline does, so if one appears it is
    reported rather than skipped past.
    """
    touched: list[Path] = []
    deleted: list[str] = []
    for sha in commits:
        out = _git(
            repo,
            "show",
            "--no-renames",
            "--name-status",
            "--format=",
            sha,
            "--",
            "data/grades",
        )
        for line in out.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            status, path = parts[0], parts[-1]
            if not path.endswith(".json"):
                continue
            if status.startswith("D"):
                deleted.append(path)
                continue
            candidate = Path(path)
            if candidate not in touched:
                touched.append(candidate)
    return touched, deleted


def check_payload(repo: Path, rel: Path) -> tuple[Finding, dict | None]:
    """The file is on disk at this commit, and it is JSON with tasks in it."""
    path = repo / rel
    if not path.is_file():
        return (
            Finding(
                "payload",
                False,
                f"{rel} is named by a published commit but is not in the tree at "
                "the commit being verified",
                {"file": str(rel)},
            ),
            None,
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return (
            Finding(
                "payload",
                False,
                f"{rel} does not parse: {exc}",
                {"file": str(rel)},
            ),
            None,
        )
    if not isinstance(payload, dict):
        return (
            Finding("payload", False, f"{rel} is not a JSON object", {"file": str(rel)}),
            None,
        )
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        return (
            Finding(
                "payload",
                False,
                f"{rel} has no tasks array; a grade file without one grades nothing",
                {"file": str(rel)},
            ),
            None,
        )
    return (
        Finding(
            "payload",
            True,
            f"{rel} parses, {len(tasks)} task(s), run_status="
            f"{payload.get('run_status')!r}",
            {
                "file": str(rel),
                "tasks": len(tasks),
                "run_status": payload.get("run_status"),
                "schema_version": payload.get("schema_version"),
            },
        ),
        payload,
    )


def check_schema(repo: Path, rel: Path, payload: dict) -> Finding:
    """The same validator the pipeline runs before it persists a grade.

    Re-run here because the pipeline validates the file it is about to write,
    and this validates the file that actually landed. Between the two sit a
    rebase, a push and whatever else reached the branch.
    """
    schema_path = repo / "batch-runner" / "schemas" / "grade.schema.json"
    if not schema_path.is_file():
        return Finding(
            "schema",
            False,
            f"grade schema is missing at {schema_path.relative_to(repo)}, so the "
            "payload cannot be validated",
            {"file": str(rel)},
        )
    try:
        from core.grade_payload import validate_grade_payload
    except Exception as exc:  # pragma: no cover - import environment failure
        return Finding(
            "schema",
            False,
            f"cannot import the grade validator: {exc}",
            {"file": str(rel)},
        )
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validate_grade_payload(payload, schema)
    except Exception as exc:
        return Finding(
            "schema",
            False,
            f"{rel} does not satisfy grade.schema.json: "
            f"{type(exc).__name__}: {exc}",
            {"file": str(rel)},
        )
    return Finding(
        "schema",
        True,
        f"{rel} validates against grade.schema.json "
        f"(schema_version={payload.get('schema_version')!r})",
        {"file": str(rel)},
    )


def check_ledger(repo: Path, rel: Path, payload: dict) -> Finding:
    """Delegated whole to verify_cost_ledger.

    None of its twelve checks are re-implemented or re-interpreted here. A
    grade with no ``cost_ledger`` pointer is reported as having none -- true of
    every file published before ledgers existed -- and a grade that points at
    one has to reconcile.
    """
    if not isinstance(payload.get("cost_ledger"), dict):
        return Finding(
            "ledger",
            True,
            f"{rel} declares no cost_ledger; nothing to reconcile against",
            {"file": str(rel), "declared": False},
        )
    try:
        from scripts.verify_cost_ledger import verify as verify_ledger
    except Exception as exc:  # pragma: no cover - import environment failure
        return Finding(
            "ledger", False, f"cannot import the ledger verifier: {exc}", {"file": str(rel)}
        )
    try:
        findings, context = verify_ledger(repo / rel)
    except (Exception, SystemExit) as exc:
        # SystemExit is in there on purpose. verify_cost_ledger is a command
        # line tool first, and it raises SystemExit on a ledger line that is
        # not JSON. Left uncaught that unwinds the whole run: the job fails,
        # which is right, but with no report artifact and no summary row -- so
        # the reader is told nothing about which file broke. Reported instead.
        return Finding(
            "ledger",
            False,
            f"the ledger verifier raised on {rel}: {type(exc).__name__}: {exc}",
            {"file": str(rel)},
        )
    failed = [f.check for f in findings if not f.ok]
    data = {
        "file": str(rel),
        "declared": True,
        "checks": len(findings),
        "failed": failed,
        "settled_rows": context.get("settled_rows"),
        "receipt_status": context.get("receipt_status"),
        "estimated_cost_usd": context.get("receipt_estimated_cost_usd"),
        "findings": [f.as_dict() for f in findings if not f.ok],
    }
    if failed:
        return Finding(
            "ledger",
            False,
            f"{rel} does not reconcile against its ledger: {', '.join(failed)}",
            data,
        )
    return Finding(
        "ledger",
        True,
        f"{rel} reconciles {len(findings)}/{len(findings)}: "
        f"{context.get('settled_rows')} settled call(s), receipt "
        f"{context.get('receipt_status')}",
        data,
    )


def check_aggregation(repo: Path, published: list[Path], command: str) -> Finding:
    """The dashboard build, over the tree that now contains the new grade.

    A grade file the aggregator refuses does not produce a shorter index; it
    throws, which is what makes this worth running. What it cannot do is reach
    a subdirectory, so a ``_diagnostic`` publish is named as out-of-scope here
    rather than being counted as aggregated -- an aggregation that never saw
    the file is not evidence about the file.
    """
    in_scope = [p for p in published if p.parent == AGGREGATED_DIR]
    out_of_scope = [str(p) for p in published if p.parent != AGGREGATED_DIR]
    try:
        proc = subprocess.run(
            shlex.split(command),
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=900,
        )
    except FileNotFoundError as exc:
        return Finding(
            "aggregation",
            False,
            f"cannot run the aggregation ({command}): {exc}",
            {"command": command},
        )
    except subprocess.TimeoutExpired:
        return Finding(
            "aggregation",
            False,
            f"the aggregation ({command}) did not finish within 900s",
            {"command": command},
        )
    tail = (proc.stdout + proc.stderr).strip().splitlines()[-25:]
    data = {
        "command": command,
        "returncode": proc.returncode,
        "in_scope": [str(p) for p in in_scope],
        "out_of_scope": out_of_scope,
        "output_tail": tail,
    }
    if proc.returncode != 0:
        return Finding(
            "aggregation",
            False,
            f"the aggregation refused the published tree (exit {proc.returncode}); "
            "the dashboard build would fail on this commit",
            data,
        )
    detail = f"aggregation clean over {len(in_scope)} in-scope grade file(s)"
    if out_of_scope:
        detail += (
            f"; {len(out_of_scope)} published below {AGGREGATED_DIR}/ rather "
            "than directly in it, and so outside the aggregator's flat scan by "
            "design -- not aggregated, and not claimed to be: "
            + ", ".join(out_of_scope)
        )
    return Finding("aggregation", True, detail, data)


def verify(
    repo: Path,
    commits: list[str],
    *,
    ref: str = "origin/main",
    aggregate_cmd: str = DEFAULT_AGGREGATE_CMD,
) -> tuple[list[Finding], dict[str, Any]]:
    """Every check, in the order a defect would surface in."""
    findings: list[Finding] = []
    resolved = resolve_commits(repo, commits)
    context: dict[str, Any] = {
        "repo": str(repo),
        "commits": resolved,
        "ref": ref,
        "head": _git(repo, "rev-parse", "HEAD").strip(),
    }

    findings.append(check_published(repo, resolved, ref))

    published, deleted = grade_files_in(repo, resolved)
    context["published_grade_files"] = [str(p) for p in published]
    context["deleted_grade_files"] = deleted

    if deleted:
        findings.append(
            Finding(
                "no_deletions",
                False,
                f"{len(deleted)} published grade file(s) were removed by these "
                f"commits: {', '.join(deleted)}. Grades are appended, never "
                "replaced -- a re-run lands beside its predecessor.",
                {"deleted": deleted},
            )
        )

    for rel in published:
        payload_finding, payload = check_payload(repo, rel)
        findings.append(payload_finding)
        if payload is None:
            continue
        findings.append(check_schema(repo, rel, payload))
        findings.append(check_ledger(repo, rel, payload))

    findings.append(check_aggregation(repo, published, aggregate_cmd))
    return findings, context


def render_summary(findings: list[Finding], context: dict[str, Any]) -> str:
    """The markdown that goes in the job summary.

    It names the commit and the check, because "the verification failed" sends
    the reader back to the log to find out which of eleven things broke on
    which of two commits.
    """
    failed = [f for f in findings if not f.ok]
    verdict = "pass" if not failed else "fail"
    lines = [
        f"## Published-commit verification: **{verdict}**",
        "",
        f"* branch: `{context.get('ref')}`",
        f"* commits verified: "
        + ", ".join(f"`{sha[:12]}`" for sha in context.get("commits", [])),
        f"* grade files published: "
        + (
            ", ".join(f"`{p}`" for p in context.get("published_grade_files") or [])
            or "_none_"
        ),
        "",
        "| check | verdict | detail |",
        "| --- | --- | --- |",
    ]
    for finding in findings:
        mark = "pass" if finding.ok else "**FAIL**"
        detail = finding.detail.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| `{finding.check}` | {mark} | {detail} |")
    if failed:
        lines += [
            "",
            f"{len(failed)} check(s) failed on a commit that is **already on "
            f"`{context.get('ref')}`**. Nothing here reverts or rewrites it: the "
            "published artifact is the evidence. Fix forward.",
        ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--commits",
        nargs="+",
        required=True,
        help="the commit(s) the grading run pushed, in order",
    )
    parser.add_argument("--repo", type=Path, default=REPO_ROOT, help="repository root")
    parser.add_argument(
        "--ref",
        default="origin/main",
        help="the branch the commits must be on for them to count as published",
    )
    parser.add_argument(
        "--aggregate-cmd",
        default=DEFAULT_AGGREGATE_CMD,
        help="the aggregation to run; defaults to the dashboard's own target",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--summary",
        type=Path,
        help="write the markdown summary here as well as to stdout",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="write the full JSON report here, for upload as an artifact",
    )
    args = parser.parse_args(argv)

    repo = args.repo.resolve()
    try:
        findings, context = verify(
            repo,
            args.commits,
            ref=args.ref,
            aggregate_cmd=args.aggregate_cmd,
        )
    except GitError as exc:
        # Fail closed. An unanswerable git question is the one state in which
        # this tool knows nothing, and knowing nothing is not a pass.
        print(f"cannot verify: {exc}", file=sys.stderr)
        return 2

    failed = [f for f in findings if not f.ok]
    report = {
        "verdict": "pass" if not failed else "fail",
        "context": context,
        "findings": [f.as_dict() for f in findings],
    }

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    summary = render_summary(findings, context)
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as handle:
            handle.write(summary)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"repo   : {context['repo']}")
        print(f"ref    : {context['ref']}")
        print(f"commits: {', '.join(sha[:12] for sha in context['commits'])}")
        print(f"grades : {', '.join(context['published_grade_files']) or '(none)'}")
        print()
        for finding in findings:
            mark = "PASS" if finding.ok else "FAIL"
            print(f"[{mark}] {finding.check}: {finding.detail}")
        print()
        print("VERDICT: pass" if not failed else f"VERDICT: fail ({len(failed)} checks)")

    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
