"""The states a publish can actually be in, and what the follow-up check says.

``scripts/verify_published_grades.py`` exists because a grading run pushes its
result with ``GITHUB_TOKEN`` and GitHub starts no workflow for that push. The
check that closes the gap is only worth having if it survives the shapes a real
publish takes: eleven shards racing onto one branch, a commit that was made and
never pushed, a re-run landing beside its predecessor rather than replacing it,
a ledger that grew after the receipt was written.

Two things are real here rather than mocked, and both on purpose.

The repository is real -- every test runs ``git init``, commits, and pushes to a
bare remote. The thing under test is a claim about commits, and a fixture that
mocked git would only assert that the mock behaves the way I assumed git does.

The grade files are real too: the two smoke results published by ``94bb8fa``
and ``602cea4``, the exact pair whose publication started no workflow. They are
copied into the throwaway repository and the copies are what gets corrupted, so
nothing here writes to ``data/grades``. Using them rather than a hand-built
payload means the passing case is a statement about an artifact that shipped,
not about a fixture I tuned until it passed.

Nothing here calls a model, grades anything, or spends anything. The
aggregation is stubbed with a command whose exit code the test chooses -- what
is being checked is that a non-zero exit fails the verification, not that npm
works.
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BATCH_RUNNER_ROOT.parent
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from scripts import verify_published_grades as vpg  # noqa: E402

OK_CMD = f"{sys.executable} -c pass"
FAIL_CMD = f"{sys.executable} -c {shlex.quote('raise SystemExit(3)')}"

#: The two smoke results published on 2026-09-07 by the pair of commits that
#: started no workflow run. Same experiment, two grader fingerprints -- which
#: is also the "legitimate multiple results" case, so the corpus and the
#: scenario are the same two files.
SMOKE_DIR = (
    REPO_ROOT
    / "data"
    / "grades"
    / "_diagnostic"
    / "17e2607b1a293be8802a36f1c1ca8e75b96e3437f99d707bfac13d9a9af247b1"
)
_STEM = (
    "exp026c_cost_receipt_smoke__judge_gpt-5_4__cost_smoke_exp026c_v2_gpt54"
    "__cfg_{cfg}__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf"
    "__inference_0d1d6df224d71aec23a0199ba1e7b272044b500b__src_{src}__v2.2"
)
SMOKE_A = _STEM.format(cfg="c4348e8fa153ce8d", src="7ca55f907056df2d")
SMOKE_B = _STEM.format(cfg="5b77131b1e1fc221", src="f4931215d1ec316b")

pytestmark = pytest.mark.skipif(
    not (SMOKE_DIR / f"{SMOKE_A}.json").is_file(),
    reason="the published smoke corpus these tests verify against is absent",
)


# --------------------------------------------------------------------------
# a repository, and real published grades placed inside it
# --------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True
    )
    assert proc.returncode == 0, f"git {args}: {proc.stderr or proc.stdout}"
    return proc.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository with an ``origin/main`` that is a real remote.

    ``merge-base --is-ancestor`` against a remote-tracking ref is the whole
    publication proof, so the fixture has to have one rather than a local
    branch renamed to look like one.
    """
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(origin)],
        check=True, capture_output=True,
    )
    work = tmp_path / "work"
    subprocess.run(
        ["git", "clone", str(origin), str(work)], check=True, capture_output=True
    )
    _git(work, "config", "user.email", "test@example.invalid")
    _git(work, "config", "user.name", "test")
    (work / "data" / "grades").mkdir(parents=True)
    # The validator reads the schema out of the tree being verified, so the
    # throwaway repository needs the same one the pipeline validates against.
    schemas = work / "batch-runner" / "schemas"
    schemas.mkdir(parents=True)
    shutil.copy2(
        BATCH_RUNNER_ROOT / "schemas" / "grade.schema.json",
        schemas / "grade.schema.json",
    )
    (work / "README.md").write_text("seed\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-m", "seed")
    _git(work, "push", "origin", "main")
    return work


def place(repo: Path, subdir: str, stem: str = SMOKE_A) -> Path:
    """Copy a published grade and its ledger into ``subdir``, names preserved.

    The file names carry the config and fingerprint the run was published
    under, and the grade's ``cost_ledger.path`` points at its sidecar by name,
    so only the directory varies between tests.
    """
    dest = repo / subdir
    dest.mkdir(parents=True, exist_ok=True)
    for suffix in (".json", ".cost_ledger.jsonl"):
        shutil.copy2(SMOKE_DIR / f"{stem}{suffix}", dest / f"{stem}{suffix}")
    return Path(subdir) / f"{stem}.json"


def publish(repo: Path, message: str) -> str:
    """Commit everything staged and push it, the way the workflow does."""
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)
    _git(repo, "push", "origin", "main")
    _git(repo, "fetch", "origin", "main")
    return _git(repo, "rev-parse", "HEAD")


def verdict(repo: Path, commits: list[str], *, cmd: str = OK_CMD) -> dict[str, bool]:
    """Collapse the findings to one verdict per check name.

    Several files can each contribute a ``payload``/``schema``/``ledger``
    finding, and the check passes only if every one of them did.
    """
    findings, _ = vpg.verify(repo, commits, ref="origin/main", aggregate_cmd=cmd)
    out: dict[str, bool] = {}
    for finding in findings:
        out[finding.check] = out.get(finding.check, True) and finding.ok
    return out


def rewrite(repo: Path, rel: Path, mutate) -> None:
    """Edit the *copy* in the throwaway repository. Never the published file."""
    path = repo / rel
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------
# the ordinary publish
# --------------------------------------------------------------------------


def test_a_grade_that_was_actually_published_passes_every_check(repo: Path):
    """The 2026-09-07 smoke, re-verified. This one shipped."""
    place(repo, "data/grades")
    sha = publish(repo, "chore(grades): grade exp026c via cost_smoke_exp026c_v2_gpt54")
    result = verdict(repo, [sha])
    assert all(result.values()), result
    assert set(result) == {"published", "payload", "schema", "ledger", "aggregation"}


def test_the_report_names_the_files_the_commit_published(repo: Path):
    rel = place(repo, "data/grades")
    sha = publish(repo, "chore(grades): grade exp026c")
    _, context = vpg.verify(repo, [sha], ref="origin/main", aggregate_cmd=OK_CMD)
    assert context["published_grade_files"] == [str(rel)]
    assert context["commits"] == [sha]
    assert context["deleted_grade_files"] == []


def test_the_ledger_finding_carries_the_evidence_not_just_a_verdict(repo: Path):
    """84 settled calls and a complete receipt, read off the real ledger. A
    report that said only "ok" would make every failure a log-diving exercise."""
    place(repo, "data/grades")
    sha = publish(repo, "chore(grades): grade exp026c")
    findings, _ = vpg.verify(repo, [sha], ref="origin/main", aggregate_cmd=OK_CMD)
    ledger = next(f for f in findings if f.check == "ledger")
    assert ledger.data["settled_rows"] == 84
    assert ledger.data["receipt_status"] == "complete"
    assert ledger.data["failed"] == []


# --------------------------------------------------------------------------
# 게시 실패 / 취소 -- a commit that was made and never pushed
# --------------------------------------------------------------------------


def test_a_commit_that_never_reached_the_branch_is_not_published(repo: Path):
    """The failure the ancestry proof exists for.

    A SHA the runner holds proves a commit was *made*. If the push failed -- or
    the job was cancelled between commit and push -- that commit describes a
    tree nobody else has, and verifying it would report on a result that was
    never published.
    """
    place(repo, "data/grades")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "chore(grades): grade exp026c")
    sha = _git(repo, "rev-parse", "HEAD")  # committed, never pushed

    findings, _ = vpg.verify(repo, [sha], ref="origin/main", aggregate_cmd=OK_CMD)
    published = next(f for f in findings if f.check == "published")
    assert published.ok is False
    assert published.data["orphaned"] == [sha]


def test_a_ref_that_cannot_be_resolved_fails_rather_than_finding_nothing_wrong(
    repo: Path,
):
    """Fail closed. "I could not check" and "it is fine" must not be one word."""
    place(repo, "data/grades")
    sha = publish(repo, "chore(grades): grade exp026c")
    findings, _ = vpg.verify(
        repo, [sha], ref="origin/no-such-branch", aggregate_cmd=OK_CMD
    )
    published = next(f for f in findings if f.check == "published")
    assert published.ok is False
    assert "cannot resolve" in published.detail


# --------------------------------------------------------------------------
# 동시 게시 -- eleven shards push to one branch on purpose
# --------------------------------------------------------------------------


def test_a_siblings_publish_landing_first_does_not_fail_this_run(repo: Path):
    """Shard B publishes, then shard A rebases onto it and publishes.

    A's verification must cover A's file and be untroubled by B's. Deriving the
    file list from a commit *range* would sweep B's file in, and a defect in
    B's receipt would fail A's job -- a false alarm that trains people to
    ignore the check.
    """
    place(repo, "data/grades", SMOKE_B)
    publish(repo, "chore(grades): grade exp026c [shard 2 of 2]")

    rel_a = place(repo, "data/grades", SMOKE_A)
    sha_a = publish(repo, "chore(grades): grade exp026c [shard 1 of 2]")

    _, context = vpg.verify(repo, [sha_a], ref="origin/main", aggregate_cmd=OK_CMD)
    assert context["published_grade_files"] == [str(rel_a)], (
        "a run verifies what it published, not what its sibling did"
    )


def test_a_broken_sibling_does_not_fail_the_run_that_did_nothing_wrong(repo: Path):
    rel_b = place(repo, "data/grades", SMOKE_B)
    (repo / rel_b).write_text("{ not json", encoding="utf-8")
    publish(repo, "chore(grades): grade exp026c [shard 2 of 2]")

    place(repo, "data/grades", SMOKE_A)
    sha_a = publish(repo, "chore(grades): grade exp026c [shard 1 of 2]")

    assert all(verdict(repo, [sha_a]).values())


# --------------------------------------------------------------------------
# 같은 실험의 정상적인 복수 결과 -- a re-run lands beside its predecessor
# --------------------------------------------------------------------------


def test_two_results_for_one_experiment_are_both_checked_and_neither_stands_in(
    repo: Path,
):
    """These two files *are* that case: one experiment, two grader
    fingerprints, published side by side. Both are verified; a pass on one is
    not evidence about the other."""
    folder = "data/grades/_diagnostic/17e2607b"
    place(repo, folder, SMOKE_A)
    place(repo, folder, SMOKE_B)
    sha = publish(repo, "chore(grades): grade exp026c")

    findings, context = vpg.verify(repo, [sha], ref="origin/main", aggregate_cmd=OK_CMD)
    assert len(context["published_grade_files"]) == 2
    ledgers = [f for f in findings if f.check == "ledger"]
    assert len(ledgers) == 2 and all(f.ok for f in ledgers)
    assert sorted(f.data["settled_rows"] for f in ledgers) == [84, 112]


def test_the_second_of_two_results_failing_is_reported_against_that_file(repo: Path):
    folder = "data/grades/_diagnostic/17e2607b"
    place(repo, folder, SMOKE_A)
    rel_b = place(repo, folder, SMOKE_B)
    rewrite(repo, rel_b, lambda p: p["summary"]["grading_cost"].update(
        {"model_cost_usd": 99.0}
    ))
    sha = publish(repo, "chore(grades): grade exp026c")

    findings, _ = vpg.verify(repo, [sha], ref="origin/main", aggregate_cmd=OK_CMD)
    failed = [f for f in findings if not f.ok]
    assert len(failed) == 1, [f.check for f in failed]
    assert failed[0].check == "ledger"
    assert failed[0].data["file"] == str(rel_b)
    assert "cost_reconciles" in failed[0].data["failed"]


# --------------------------------------------------------------------------
# JSON 누락 · 손상
# --------------------------------------------------------------------------


def test_a_published_grade_that_does_not_parse_is_caught(repo: Path):
    rel = place(repo, "data/grades")
    (repo / rel).write_text('{"schema_version": "1.4", "tasks": [', encoding="utf-8")
    sha = publish(repo, "chore(grades): grade exp026c")
    result = verdict(repo, [sha])
    assert result["payload"] is False
    assert "schema" not in result, "a file that does not parse cannot be validated"


def test_a_grade_with_no_tasks_array_is_caught(repo: Path):
    rel = place(repo, "data/grades")
    rewrite(repo, rel, lambda p: p.pop("tasks"))
    sha = publish(repo, "chore(grades): grade exp026c")
    assert verdict(repo, [sha])["payload"] is False


def test_a_grade_that_parses_but_breaks_the_schema_is_caught(repo: Path):
    """Parsing and validating are two questions. A file can be perfectly good
    JSON and still be missing the block the dashboard reads."""
    rel = place(repo, "data/grades")
    rewrite(repo, rel, lambda p: p.pop("judge"))
    sha = publish(repo, "chore(grades): grade exp026c")
    result = verdict(repo, [sha])
    assert result["payload"] is True
    assert result["schema"] is False


def test_a_grade_the_commit_named_but_the_tree_does_not_have_is_caught(repo: Path):
    """Named by the commit, absent from the tree being verified -- the shape a
    later force-push or a bad checkout produces. It must not read as "no files
    to check, nothing wrong"."""
    rel = place(repo, "data/grades")
    sha = publish(repo, "chore(grades): grade exp026c")
    (repo / rel).unlink()
    assert verdict(repo, [sha])["payload"] is False


def test_a_ledger_line_that_is_not_json_is_reported_not_a_crash(repo: Path):
    """``verify_cost_ledger`` is a command line tool first and raises SystemExit
    on an unparseable ledger line. Uncaught, that ends the job with no report
    and no summary row -- the reader learns that something failed, not what."""
    rel = place(repo, "data/grades")
    ledger = repo / str(rel).replace(".json", ".cost_ledger.jsonl")
    ledger.write_text(
        ledger.read_text(encoding="utf-8") + "{ truncated\n", encoding="utf-8"
    )
    sha = publish(repo, "chore(grades): grade exp026c")

    findings, _ = vpg.verify(repo, [sha], ref="origin/main", aggregate_cmd=OK_CMD)
    ledger_finding = next(f for f in findings if f.check == "ledger")
    assert ledger_finding.ok is False
    assert ledger_finding.data["file"] == str(rel)


def test_a_commit_that_deletes_a_published_grade_is_reported(repo: Path):
    """Grades are appended, never replaced. A deletion is not something this
    pipeline does, so it is surfaced rather than filtered out of the file list
    and thereby made invisible."""
    rel = place(repo, "data/grades")
    publish(repo, "chore(grades): grade exp026c")
    (repo / rel).unlink()
    sha = publish(repo, "chore(grades): remove")

    findings, context = vpg.verify(repo, [sha], ref="origin/main", aggregate_cmd=OK_CMD)
    deletion = next(f for f in findings if f.check == "no_deletions")
    assert deletion.ok is False
    assert context["deleted_grade_files"] == [str(rel)]


# --------------------------------------------------------------------------
# 원장 추가 -- the ledger grew after the receipt was written
# --------------------------------------------------------------------------


def test_a_ledger_appended_to_after_the_receipt_was_written_is_caught(repo: Path):
    """A call recorded after the totals were computed is a bill that no longer
    matches its own itemisation. The digest in the grade file is what notices,
    and this proves the follow-up check actually consults it."""
    rel = place(repo, "data/grades")
    ledger = repo / str(rel).replace(".json", ".cost_ledger.jsonl")
    lines = ledger.read_text(encoding="utf-8").splitlines()
    extra = json.loads(lines[-1])
    extra["call_id"] = "appended-after-publication"
    ledger.write_text(
        "\n".join(lines) + "\n" + json.dumps(extra, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    sha = publish(repo, "chore(grades): grade exp026c")

    findings, _ = vpg.verify(repo, [sha], ref="origin/main", aggregate_cmd=OK_CMD)
    ledger_finding = next(f for f in findings if f.check == "ledger")
    assert ledger_finding.ok is False
    assert ledger_finding.data["failed"] == ["sidecar"], (
        "the digest is what catches an append; the totals are not even reached"
    )


def test_a_ledger_that_is_missing_entirely_is_caught(repo: Path):
    rel = place(repo, "data/grades")
    (repo / str(rel).replace(".json", ".cost_ledger.jsonl")).unlink()
    sha = publish(repo, "chore(grades): grade exp026c")
    assert verdict(repo, [sha])["ledger"] is False


def test_a_grade_published_before_ledgers_existed_is_not_a_failure(repo: Path):
    """Every file published before per-call ledgers has no ``cost_ledger``
    pointer. Reporting that as a reconciliation failure would make the check
    unusable on the corpus it has to run over."""
    rel = place(repo, "data/grades")
    rewrite(repo, rel, lambda p: p.pop("cost_ledger"))
    sha = publish(repo, "chore(grades): grade exp026c")

    findings, _ = vpg.verify(repo, [sha], ref="origin/main", aggregate_cmd=OK_CMD)
    ledger = next(f for f in findings if f.check == "ledger")
    assert ledger.ok is True
    assert ledger.data["declared"] is False


# --------------------------------------------------------------------------
# 집계
# --------------------------------------------------------------------------


def test_an_aggregation_that_refuses_the_tree_fails_the_verification(repo: Path):
    """``aggregate-grades.mjs`` throws on a grade file it cannot read rather
    than emitting a shorter index. A non-zero exit is the dashboard build
    saying it would fail on this commit, and it has to fail here too."""
    place(repo, "data/grades")
    sha = publish(repo, "chore(grades): grade exp026c")
    findings, _ = vpg.verify(repo, [sha], ref="origin/main", aggregate_cmd=FAIL_CMD)
    aggregation = next(f for f in findings if f.check == "aggregation")
    assert aggregation.ok is False
    assert aggregation.data["returncode"] == 3


def test_an_aggregation_that_cannot_be_run_is_a_failure_not_a_skip(repo: Path):
    place(repo, "data/grades")
    sha = publish(repo, "chore(grades): grade exp026c")
    findings, _ = vpg.verify(
        repo, [sha], ref="origin/main", aggregate_cmd="definitely-not-a-command"
    )
    aggregation = next(f for f in findings if f.check == "aggregation")
    assert aggregation.ok is False


def test_a_diagnostic_publish_is_named_out_of_scope_rather_than_counted(repo: Path):
    """The aggregator does a flat ``readdir`` of ``data/grades``. A file in the
    ``_diagnostic`` fork is out of its reach by design -- and today *every*
    ledger-bearing grade in this repository lives there. An aggregation that
    never saw the file is not evidence about the file, so it is named rather
    than quietly folded into a pass."""
    rel = place(repo, "data/grades/_diagnostic/17e2607b")
    sha = publish(repo, "chore(grades): grade exp026c")
    findings, _ = vpg.verify(repo, [sha], ref="origin/main", aggregate_cmd=OK_CMD)
    aggregation = next(f for f in findings if f.check == "aggregation")
    assert aggregation.ok is True
    assert aggregation.data["in_scope"] == []
    assert aggregation.data["out_of_scope"] == [str(rel)]
    assert "outside the aggregator's flat scan" in aggregation.detail


def test_a_flat_publish_is_counted_as_in_scope(repo: Path):
    rel = place(repo, "data/grades")
    sha = publish(repo, "chore(grades): grade exp026c")
    findings, _ = vpg.verify(repo, [sha], ref="origin/main", aggregate_cmd=OK_CMD)
    aggregation = next(f for f in findings if f.check == "aggregation")
    assert aggregation.data["in_scope"] == [str(rel)]
    assert aggregation.data["out_of_scope"] == []


# --------------------------------------------------------------------------
# 중복 실행 방지 · 무변경 게시
# --------------------------------------------------------------------------


def test_verifying_the_same_commit_twice_changes_nothing(repo: Path):
    """The check is a read. Running it again -- on a re-run of the job, or on a
    resumed workflow -- must produce the same verdict and leave the published
    tree exactly as it found it."""
    place(repo, "data/grades")
    sha = publish(repo, "chore(grades): grade exp026c")

    first = verdict(repo, [sha])
    second = verdict(repo, [sha])

    assert first == second
    assert _git(repo, "rev-parse", "HEAD") == sha
    assert _git(repo, "status", "--porcelain") == "", (
        "the verification must not leave the published tree dirty"
    )


def test_a_commit_named_twice_is_verified_once(repo: Path):
    place(repo, "data/grades")
    sha = publish(repo, "chore(grades): grade exp026c")
    _, context = vpg.verify(
        repo, [sha, sha[:12], sha], ref="origin/main", aggregate_cmd=OK_CMD
    )
    assert context["commits"] == [sha]


def test_a_commit_that_published_no_grade_is_reported_as_publishing_none(repo: Path):
    """A no-change publish -- the skip-cache hit -- commits nothing, and the
    workflow records no SHA. The analysis-only commit is the neighbouring case:
    a real commit that touched no grade JSON. Saying so is different from
    claiming a grade was checked."""
    (repo / "data" / "grades" / "run.analysis.md").write_text("x\n", encoding="utf-8")
    sha = publish(repo, "docs(grading): auto-analysis")
    findings, context = vpg.verify(repo, [sha], ref="origin/main", aggregate_cmd=OK_CMD)
    assert context["published_grade_files"] == []
    assert all(f.ok for f in findings)
    assert {f.check for f in findings} == {"published", "aggregation"}


def test_the_verifier_refuses_to_run_with_no_commits_at_all():
    """There is no "verify nothing and pass" path. The caller must name what it
    published, and a workflow that published nothing does not reach this tool."""
    with pytest.raises(SystemExit) as excinfo:
        vpg.main([])
    assert excinfo.value.code == 2


# --------------------------------------------------------------------------
# the command line and the report
# --------------------------------------------------------------------------


def test_the_command_line_exits_nonzero_and_names_what_failed(repo: Path, tmp_path):
    rel = place(repo, "data/grades")
    rewrite(repo, rel, lambda p: p["summary"]["grading_cost"].update(
        {"model_cost_usd": 99.0}
    ))
    sha = publish(repo, "chore(grades): grade exp026c")

    report = tmp_path / "out" / "report.json"
    summary = tmp_path / "summary.md"
    rc = vpg.main(
        [
            "--commits", sha,
            "--repo", str(repo),
            "--ref", "origin/main",
            "--aggregate-cmd", OK_CMD,
            "--report", str(report),
            "--summary", str(summary),
        ]
    )
    assert rc == 1

    written = json.loads(report.read_text(encoding="utf-8"))
    assert written["verdict"] == "fail"
    assert [f["check"] for f in written["findings"] if not f["ok"]] == ["ledger"]

    text = summary.read_text(encoding="utf-8")
    assert "**fail**" in text
    assert sha[:12] in text, "the summary must name the commit that failed"
    assert "`ledger`" in text, "and the check that failed on it"


def test_the_summary_appends_rather_than_replacing_what_is_already_there(
    repo: Path, tmp_path
):
    """``$GITHUB_STEP_SUMMARY`` is a shared file. Opening it for writing would
    erase every earlier step's report."""
    place(repo, "data/grades")
    sha = publish(repo, "chore(grades): grade exp026c")
    summary = tmp_path / "summary.md"
    summary.write_text("## an earlier step said something\n", encoding="utf-8")
    vpg.main(
        ["--commits", sha, "--repo", str(repo), "--ref", "origin/main",
         "--aggregate-cmd", OK_CMD, "--summary", str(summary)]
    )
    assert "an earlier step said something" in summary.read_text(encoding="utf-8")


def test_the_command_line_exits_zero_on_a_publish_that_verifies(repo: Path):
    place(repo, "data/grades")
    sha = publish(repo, "chore(grades): grade exp026c")
    rc = vpg.main(
        ["--commits", sha, "--repo", str(repo), "--ref", "origin/main",
         "--aggregate-cmd", OK_CMD]
    )
    assert rc == 0


def test_a_repository_git_cannot_answer_about_exits_two(tmp_path: Path):
    """Not 0. An unanswerable question is the one state this tool knows nothing
    in, and knowing nothing is not a pass."""
    (tmp_path / "notarepo").mkdir()
    rc = vpg.main(
        ["--commits", "a" * 40, "--repo", str(tmp_path / "notarepo"),
         "--aggregate-cmd", OK_CMD]
    )
    assert rc == 2


def test_a_commit_that_does_not_exist_exits_two(repo: Path):
    rc = vpg.main(
        ["--commits", "0" * 40, "--repo", str(repo), "--ref", "origin/main",
         "--aggregate-cmd", OK_CMD]
    )
    assert rc == 2


# --------------------------------------------------------------------------
# the wiring, read off the workflow file
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def grade_run_workflow() -> dict:
    yaml = pytest.importorskip("yaml")
    path = REPO_ROOT / ".github" / "workflows" / "grade-run.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_the_verification_job_exists_and_follows_the_paid_job(grade_run_workflow):
    job = grade_run_workflow["jobs"]["verify-published"]
    assert job["needs"] == ["grade"]
    assert "always()" in job["if"], (
        "a run that published its grade and then died at a later step is "
        "exactly the one whose commit is unverified; gating on success() "
        "would skip it"
    )
    assert "published_commits != ''" in job["if"]


def test_the_verification_job_is_read_only(grade_run_workflow):
    """It reads the tree and reports. ``contents: write``, ``id-token`` and
    ``actions: write`` belong to the job before it; none of them belong here."""
    job = grade_run_workflow["jobs"]["verify-published"]
    assert job["permissions"] == {"contents": "read"}


def test_no_step_of_the_verification_can_fail_quietly(grade_run_workflow):
    """``continue-on-error`` on the check itself would reproduce the exact
    silence this job was added to end."""
    job = grade_run_workflow["jobs"]["verify-published"]
    for step in job["steps"]:
        if step.get("name") == "Upload the verification report":
            continue  # `if: always()` so the evidence survives a failure
        assert "continue-on-error" not in step, step.get("name")


def test_the_verification_checks_out_the_published_commit_not_a_branch(
    grade_run_workflow,
):
    """Verifying ``main``'s tip would be verifying a superset that contains the
    published commit -- not the same claim, and the pretence this whole path
    exists to prevent."""
    job = grade_run_workflow["jobs"]["verify-published"]
    checkout = next(s for s in job["steps"] if s["name"].startswith("Checkout"))
    assert checkout["with"]["ref"] == "${{ needs.grade.outputs.published_head }}"
    assert checkout["with"]["fetch-depth"] == 0
    assert checkout["with"]["persist-credentials"] is False


def test_the_verification_runs_the_real_aggregation(grade_run_workflow):
    """No ``--aggregate-cmd`` override in the workflow. The flag exists so the
    tests above can choose an exit code; wiring a no-op into CI through it
    would be a check that runs and proves nothing."""
    job = grade_run_workflow["jobs"]["verify-published"]
    step = next(s for s in job["steps"] if s["name"] == "Verify what this run published")
    assert "--aggregate-cmd" not in step["run"]
    assert "verify_published_grades.py" in step["run"]
    assert vpg.DEFAULT_AGGREGATE_CMD == "npm run aggregate"


def test_the_verification_spends_nothing_and_starts_nothing(grade_run_workflow):
    """The cycle this must not create: a publish that triggers a check that
    triggers another paid grading run. Nothing in this job dispatches a
    workflow, and it holds no permission that would let it."""
    job = grade_run_workflow["jobs"]["verify-published"]
    body = "\n".join(step.get("run", "") for step in job["steps"])
    for forbidden in ("gh workflow run", "workflow_dispatch", "step8_grade",
                      "paid_approval", "gh api -X POST", "curl -X POST"):
        assert forbidden not in body, f"{forbidden!r} must not appear in this job"
    assert "actions" not in job["permissions"]


def test_the_paid_job_hands_over_the_commits_it_actually_pushed(grade_run_workflow):
    grade = grade_run_workflow["jobs"]["grade"]
    assert grade["outputs"]["published_commits"] == (
        "${{ steps.published.outputs.commits }}"
    )
    assert grade["outputs"]["published_head"] == "${{ steps.published.outputs.head }}"
    record = next(s for s in grade["steps"] if s.get("id") == "published")
    assert "always()" in record["if"]


def test_every_push_in_the_paid_job_records_what_it_landed(grade_run_workflow):
    """Three steps push: the grade, the shard merge, and the analysis. A push
    that does not record its SHA publishes a commit nothing will check."""
    grade = grade_run_workflow["jobs"]["grade"]
    recording = [
        step for step in grade["steps"]
        if "PUBLISHED_COMMITS_FILE" in step.get("run", "")
        and "rev-parse HEAD >>" in step.get("run", "")
    ]
    assert len(recording) == 3, [s.get("name") for s in recording]


def test_the_script_the_workflow_calls_is_in_the_repository():
    """``batch-runner/scripts/*`` is gitignored with per-file negations, so a
    new script is invisible to ``git add`` unless one was added for it. A
    workflow calling a file the checkout does not have is this whole defect
    reproduced one level up."""
    proc = subprocess.run(
        ["git", "ls-files", "--error-unmatch",
         "batch-runner/scripts/verify_published_grades.py"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        "verify_published_grades.py is not tracked; add a negation for it in "
        ".gitignore or the verify-published job will call a missing file"
    )
