#!/usr/bin/env python3
"""Recompute ``summary.wow`` for grade JSONs written before it was emitted.

This script has run once already. #188 introduced it and applied it, and the
four analytic fields it was written for -- ``by_sector``,
``by_rubric_category``, ``score_density_histogram`` and
``rubric_severity_curve`` -- are populated on this tree everywhere they
legitimately can be. Running it again today writes none of them.

What it now recovers is ``item_counts``, the denominators the ``wow`` rates
were divided by. Each rate is a fraction whose denominator is discarded, and
the fallback for an empty one is ``0.0`` -- indistinguishable from "every item
failed", and the worst score on the scale. ``step8_grade`` began emitting the
counts beside the rates after #188, but only for runs graded afterwards;
nothing re-grades a published file, so on the corpus committed here **not one
payload carries them**. Twenty files publish ``precheck_pass_rate: 0.0`` and
every one of them prechecked nothing.

So this pass adds ``item_counts`` and nothing else: once per file for the
run as a whole, and once per sector row beside the rates that row already
publishes -- twenty-two and sixty-two of them, eighty-four new keys, no other
key added or changed anywhere in the twenty-two files. That is not by intent
but by construction: every analytic field is recomputed and offered on every
run, and the three guards below are what refuse the ones that would move a
published number.

The per-sector copy matters as much as the run-level one. ``SectorHeatmap.tsx``
draws a cell per sector from those rates, so a sector that prechecked nothing
renders the same 0% as a sector that prechecked forty items and failed all
forty.

The clearest case is the one this cannot fix. The 185-task gold ceiling judged
8,816 items, ran 0 prechecks, and published a 0% structural pass rate -- and its
exact bytes are quoted as a reproduction receipt in ``PR3_FULL_GOLD_CORPUS.md``,
so it is refused here along with five others. That gap is printed on every run
rather than left to be noticed; moving those seals is a separate change, because
editing five evidence documents is not the same kind of act as adding a
denominator, and a reviewer should not have to sort one from the other in a
single diff.

Nothing needs re-grading. Each field is a pure function of the ``tasks`` array
already in the file, and ``step8_grade._compute_summary`` is that function.
This script calls it on the file's own tasks and copies the recomputed ``wow``
block back in.

Two of the analytic fields stay empty where they are empty, and that is
correct:

``by_rubric_category``
    GDPVal rubric items have an id, a criterion string and a weight, and
    nothing that groups them into categories. ``step8_grade`` leaves this
    empty on purpose rather than inventing a taxonomy and presenting it as
    measurement. ``SectorHeatmap.tsx`` already falls back to the per-sector
    rates.

``rubric_severity_curve`` on pre-sign-aware files
    The curve counts ``model_did_right``, which grades written before PR1
    task 100 do not carry. Without it every point reads 0.0 and the chart
    asserts a total failure that never happened. A scalar rate can absorb a
    missing field; a curve cannot, because its shape is the claim.

The safety property this script enforces: **no published number changes.**

That is not automatic, and the first cut of this script got it wrong. Six of
the thirty-three grade payloads on disk were graded under semantics the current
summariser no longer reproduces. Recomputing their whole ``wow`` block moves
published rates:

* the four pre-sign-aware ``__v1.json`` files carry no ``model_did_right``,
  so ``critical_item_pass_rate`` recomputes to ``0.0`` against a published
  ``0.42`` / ``0.52`` / ``1.0`` -- a total-failure claim that never happened;
* the two ``rubric_v2_tools`` files drift by roughly a point
  (``0.501 -> 0.485``, ``0.4232 -> 0.4338``).

So the rule is per-file, not global: **a file's semantics-dependent
breakdowns are written only when the current summariser reproduces that
file's five published scalar rates exactly.** Agreement is the evidence that
the same code understands the same file. Where it disagrees, only
``score_density_histogram`` is written -- it is a bucket count over the
per-task ``pct`` values already published in the file, so it carries no
semantic assumption at all. ``item_counts`` is gated with the breakdowns, and
for a sharper reason: a recomputed denominator under a published numerator it
does not belong to states a fraction nobody ever computed.

Three guards enforce the property, on the parsed documents rather than on
text, so key order and formatting can neither mask a real change nor invent a
false one: nothing outside ``summary.wow`` moves, none of the five scalar
rates moves, and no per-sector rate one level down moves either -- ``by_sector``
is rewritten wholesale and each row carries the same rates, which
``SectorHeatmap.tsx`` renders. Keys already present in ``wow`` that
``_compute_summary`` does not produce (``_v2sm_*``, written by
``backfill_sign_aware.py``) are preserved.

The walk is recursive under ``data/grades``, minus ``_shards/``: a shard is an
intermediate that ``step9`` merges into the payload beside it. Files whose bytes
some other document has already vouched for are refused outright, and which
files those are is asked of the repository rather than listed here -- six of the
thirty-seven, including the gold ceiling above. See ``documents_asserting``.

Dry-run by default. Pass ``--apply`` to write.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "batch-runner"))

from step8_grade import _compute_summary  # noqa: E402

# Legacy demo data, not a real grading run. 103-backfill-existing-grades.md
# excludes it by name, and it carries no `wow` block at all to bring forward.
EXCLUDED = {"dummy_gpt5_baseline.json"}

ANALYTIC_FIELDS = (
    "by_sector",
    "by_rubric_category",
    "score_density_histogram",
    "rubric_severity_curve",
)

#: The denominators each ``wow`` rate was divided by.
#:
#: Every rate in ``wow`` is a fraction whose denominator is discarded, and the
#: fallback for an empty one is ``0.0`` -- the same value as "every item
#: failed". ``step8_grade`` began publishing the counts alongside the rates so
#: the two can be told apart, but only for runs graded afterwards. Nothing
#: re-grades a published file, so on the corpus committed here the counts are
#: absent everywhere and the distinction is unrecoverable: twenty payloads
#: report ``precheck_pass_rate: 0.0`` and every one of them prechecked nothing.
#:
#: They are recoverable without re-grading, because the counters are a pure
#: function of the ``tasks`` array already in the file -- the same basis as the
#: four fields above, and gated the same way.
COUNT_FIELDS = ("item_counts",)

#: Published rates. These must be byte-identical before and after, always.
SCALAR_RATES = (
    "rubric_item_coverage_avg",
    "critical_item_pass_rate",
    "precheck_pass_rate",
    "judge_pass_rate",
    "judge_error_rate",
)

#: A bucket count over the per-task ``pct`` values already published in the
#: file. No sign-awareness, no item semantics, nothing that a change in
#: grading criteria could move. Safe to write even where the summariser and
#: the file disagree about everything else.
SEMANTICS_FREE_FIELDS = ("score_density_histogram",)


def _is_empty(value: object) -> bool:
    return value is None or (
        isinstance(value, (list, dict, str)) and len(value) == 0
    )


def _display(path: Path) -> str:
    """Repo-relative where possible. Bare names collide once the walk is
    recursive -- there are eleven ``shard-000-of-011.json`` on disk."""
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return path.name


#: Any run of 12+ hex digits: the cohort directory (64), `rubric_`/`inference_`
#: (40 each), `cfg_`/`src_` (16 each). Bounded by non-hex on both sides so a
#: digest is shortened whole rather than clipped mid-run.
_HEX_RUN = re.compile(r"(?<![0-9a-f])[0-9a-f]{12,}(?![0-9a-f])")


def _short(display: str) -> str:
    """A printable form of a path that is up to 339 characters long.

    Shortened by abbreviating its digests, not by truncating it. Truncation
    was the first attempt and it reintroduced exactly the collision
    ``_display`` exists to prevent: the last seventy characters of these names
    are ``...__src_<16hex>__v2.2.json``, and six files on disk share a tail
    with another -- the merged payload of a cohort, and its ``_repeats/run-002``
    and ``run-003`` re-runs, are identical there and differ only in a directory
    the tail never reaches. Three lines of output, three different item counts,
    no way to tell which was which.

    Abbreviating instead cuts the longest path to 208 characters and keeps all
    thirty-seven distinct. The digests are the redundant part anyway -- the same
    ``rubric_11e7900c...`` appears on every line.
    """
    return _HEX_RUN.sub(lambda m: m.group()[:8] + "…", display)


def _filled(wow: dict) -> int:
    return sum(1 for f in ANALYTIC_FIELDS if not _is_empty(wow.get(f)))


#: How much of a digest counts as an assertion about a file's bytes.
#:
#: Documents here abbreviate. ``PR3_REPEAT_VARIATION.md`` records each run it
#: compared as ``sha256`` followed by sixteen characters -- the way a person
#: writes a hash they expect someone to eyeball. Searching for the full
#: sixty-four finds three of the six sealed payloads on this tree and misses
#: those three completely, so the prefix is what gets searched.
#:
#: Sixteen is sixty-four bits. Measured, not assumed: it flags exactly the same
#: six files as twelve does, so the extra reach is not buying false positives.
#: A false positive would be the safe direction anyway -- it refuses a write.
#:
#: No digest is quoted anywhere in this file, deliberately. The first draft
#: pasted a real one here as an example and sealed the run it belonged to,
#: which is the mechanism working: a comment that states a digest is a document
#: that states a digest. Describe the shape instead.
DIGEST_PREFIX = 16


def documents_asserting(path: Path, tree: Path = REPO_ROOT) -> list[str]:
    """Tracked files in ``tree`` that state this file's current digest.

    A document that records a file's sha256 is vouching for those exact bytes.
    Rewriting the file does not make that document stale -- it makes it
    **false**, asserting a hash the bytes no longer have. So anything vouched
    for is refused, and the refusal names the documents so the next person can
    read what they claim before deciding to move them.

    This used to read one list: the shard digests in
    ``stage3_partial_inventory.json``. That was wrong in the way a hand-kept
    list is always wrong -- it was complete for the document it came from and
    silently incomplete for the tree. It knew eleven files, all of them under
    ``_shards/`` and therefore already out of the walk, and knew nothing about
    the six that were actually in scope: the anchor payload sealed in
    ``CHANGELOG.md``, the 185-task gold ceiling sealed in
    ``PR3_FULL_GOLD_CORPUS.md``, and three repeat runs sealed in
    ``PR3_REPEAT_VARIATION.md``. The first ``--apply`` rewrote two of them and
    four tests went red saying so. Asking the repository is the version of this
    that cannot fall behind the repository.

    Tracked files only. An untracked document asserting a digest is somebody's
    working note, not a committed claim, and treating it as one would make the
    refusal depend on what happens to be lying around.

    Fail closed. If the question cannot be asked there is no way to know what is
    sealed, and refusing every write is the answer that cannot destroy evidence.
    """
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:DIGEST_PREFIX]
    try:
        found = subprocess.run(
            ["git", "-C", str(tree), "grep", "--full-name", "-l", "-F", digest],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise SystemExit(
            f"cannot ask {tree} what it vouches for: {exc}. Refusing to write, "
            "because a file this script cannot confirm is unsealed may be "
            "evidence another document asserts a hash for."
        ) from exc

    # 0 found, 1 found nothing. Anything else is git failing to answer, which
    # is not the same as answering "no".
    if found.returncode not in (0, 1):
        raise SystemExit(
            f"`git grep` failed in {tree} (exit {found.returncode}): "
            f"{found.stderr.strip()}. Refusing to write for the same reason."
        )

    try:
        itself = str(path.resolve().relative_to(tree.resolve()))
    except ValueError:
        itself = ""
    # A file cannot state its own digest -- that would take a preimage search --
    # so this only ever drops a path git found for some other reason. It is here
    # because a self-seal could never be cleared by editing the file, and that
    # deadlock is worth one cheap set subtraction to rule out.
    return sorted(set(found.stdout.split()) - {itself})


def collect_grade_files(grades_dir: Path) -> list[Path]:
    """Published grade payloads under ``grades_dir``.

    Recursive, where this used to be a flat ``glob("*.json")``. The flat form
    reached eighteen of the thirty-seven, and the nineteen it missed are not
    leftovers: ten of the twenty-two files this writes sit under ``_diagnostic/``
    and a flat walk reaches none of them.

    Reachable is not the same as writable, and the 185-task gold ceiling is the
    file that shows the difference. It is the corpus's clearest instance of the
    defect -- 8,816 items judged, none prechecked, a 0% structural pass rate
    published -- it lives under ``_diagnostic/``, and it is still not fixed here.
    Not because the walk cannot see it, which it now can, but because
    ``PR3_FULL_GOLD_CORPUS.md`` quotes its bytes. Those are two different
    reasons and the earlier draft of this docstring ran them together, which
    made a scope decision look like a prohibition.

    ``_shards/`` stays out. A shard is an intermediate that ``step9`` merges
    into the payload beside it; the merged file is the published unit, and
    rewriting both would restate the same run twice. Every shard is also sealed
    in ``stage3_partial_inventory.json``, so ``documents_asserting`` would
    refuse them anyway -- this exclusion is a scope decision that could be
    revisited, that refusal is not.
    """
    return [
        path
        for path in grades_dir.rglob("*.json")
        if path.name not in EXCLUDED and "_shards" not in path.parts
    ]


def backfill_one(
    path: Path, apply: bool, tree: Path = REPO_ROOT
) -> dict:
    """Return a report for one file; write it only when ``apply`` is set."""
    vouchers = documents_asserting(path, tree)
    if vouchers:
        return {
            "path": _display(path),
            "status": "sealed",
            "reason": "digest asserted by " + ", ".join(vouchers),
        }

    original_text = path.read_text()
    doc = json.loads(original_text)

    tasks = doc.get("tasks")
    summary = doc.get("summary")
    if not isinstance(tasks, list) or not isinstance(summary, dict):
        return {"path": _display(path), "status": "skipped", "reason": "no tasks/summary"}
    old_wow = summary.get("wow")
    if not isinstance(old_wow, dict):
        return {"path": _display(path), "status": "skipped", "reason": "no summary.wow"}

    before_filled = _filled(old_wow)

    # Recompute from the file's own tasks. `unpriced_models` only affects the
    # `cost` block, which this script never reads.
    recomputed = _compute_summary(copy.deepcopy(tasks))["wow"]

    # Does the current summariser still reproduce this file's published rates?
    # That agreement is the whole licence for writing its derived breakdowns:
    # by_sector and rubric_severity_curve are built from the same counters as
    # these scalars, so if the scalars disagree the breakdowns are describing
    # a grading semantics this file was never graded under.
    #
    # `item_counts` is gated the same way and for a sharper reason: it is
    # the set of denominators those scalars were divided by. Attaching a
    # recomputed denominator to a published numerator it does not belong to
    # would state a fraction nobody ever computed -- worse than leaving it
    # absent, because absent at least reads as unknown.
    diverged = [k for k in SCALAR_RATES if old_wow.get(k) != recomputed.get(k)]
    writable = SEMANTICS_FREE_FIELDS if diverged else ANALYTIC_FIELDS + COUNT_FIELDS

    new_wow = dict(old_wow)  # keep _v2sm_* and anything else non-standard
    for field in writable:
        new_wow[field] = recomputed[field]

    if new_wow == old_wow:
        return {
            "path": _display(path),
            "status": "unchanged",
            "before_filled": before_filled,
            "after_filled": before_filled,
            "diverged": diverged,
        }

    candidate = copy.deepcopy(doc)
    candidate["summary"]["wow"] = new_wow

    # Guard 1: nothing outside summary.wow moved. Compared on the parsed
    # documents with `wow` excised from both, so key order and formatting can
    # neither mask a real change nor invent a false one.
    a, b = copy.deepcopy(doc), copy.deepcopy(candidate)
    a["summary"].pop("wow", None)
    b["summary"].pop("wow", None)
    if a != b:
        return {
            "path": _display(path),
            "status": "ABORTED",
            "reason": "a field outside summary.wow would change",
        }

    # Guard 2: no published rate inside wow moved. The first cut of this
    # script lacked exactly this check and would have republished four files'
    # critical_item_pass_rate as 0.0.
    moved = [k for k in SCALAR_RATES if old_wow.get(k) != new_wow.get(k)]
    if moved:
        return {
            "path": _display(path),
            "status": "ABORTED",
            "reason": f"published rate would change: {moved}",
        }

    # Guard 3: no published rate one level down moved either. `by_sector` is
    # rewritten wholesale, and each row carries the same five-ish rates as the
    # top-level block -- SectorHeatmap.tsx renders them. Guard 2 says nothing
    # about those, so the docstring's "no published number changes" was being
    # enforced one level shallower than it was stated. Measured across the
    # agreeing files on disk: zero rows move, and the only difference is the
    # `item_counts` this change adds. That is what makes the guard cheap to
    # add rather than a thing to argue about.
    #
    # Iterating the *published* row is what makes adding `item_counts` legal
    # without an exception for it: a key the file never had is never compared,
    # while a key it did have -- including a count from a newer grader -- has
    # to survive unchanged like any other published number.
    sector_moved = []
    for sector, old_row in (old_wow.get("by_sector") or {}).items():
        new_row = (new_wow.get("by_sector") or {}).get(sector) or {}
        sector_moved += [
            f"{sector}.{field}"
            for field, value in old_row.items()
            if new_row.get(field) != value
        ]
    if sector_moved:
        return {
            "path": _display(path),
            "status": "ABORTED",
            "reason": f"published per-sector value would change: {sector_moved}",
        }

    changed = sorted(
        f for f in ANALYTIC_FIELDS if old_wow.get(f) != new_wow.get(f)
    )
    still_empty = sorted(f for f in ANALYTIC_FIELDS if _is_empty(new_wow.get(f)))

    if apply:
        # Match the trailing-newline convention of the file as found.
        text = json.dumps(candidate, indent=2, ensure_ascii=False)
        if original_text.endswith("\n"):
            text += "\n"
        path.write_text(text)

    return {
        "path": _display(path),
        "status": "written" if apply else "would-write",
        "before_filled": before_filled,
        "after_filled": _filled(new_wow),
        "changed": changed,
        "still_empty": still_empty,
        "diverged": diverged,
        "counts": new_wow.get("item_counts") if "item_counts" in writable else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "grades_dir",
        nargs="?",
        type=Path,
        default=REPO_ROOT / "data" / "grades",
    )
    ap.add_argument("--apply", action="store_true", help="write files (default: dry run)")
    ap.add_argument(
        "--tree",
        type=Path,
        default=REPO_ROOT,
        help="git repository to ask which digests are already vouched for",
    )
    args = ap.parse_args()

    files = sorted(collect_grade_files(args.grades_dir))
    if not files:
        print(f"no grade JSONs under {args.grades_dir}", file=sys.stderr)
        return 1

    reports = [backfill_one(p, args.apply, args.tree) for p in files]
    aborted = [r for r in reports if r["status"] == "ABORTED"]
    touched = [r for r in reports if r["status"] in ("written", "would-write")]
    sealed = [r for r in reports if r["status"] == "sealed"]

    for r in reports:
        if r["status"] in ("skipped", "unchanged", "sealed"):
            print(f"  {r['status']:<12} {_short(r['path'])}"
                  f"{'  (' + r['reason'] + ')' if r.get('reason') else ''}")
            continue
        if r["status"] == "ABORTED":
            print(f"  ABORTED      {_short(r['path'])}  {r['reason']}")
            continue
        print(f"  {r['status']:<12} {_short(r['path'])}")
        print(f"      analytic fields filled: {r['before_filled']}/4 -> {r['after_filled']}/4")
        print(f"      changed: {r['changed']}")
        if r.get("counts"):
            counts = r["counts"]
            unmeasured = sorted(k for k, v in counts.items() if v == 0)
            print(f"      item_counts: {counts}"
                  + (f"  <- nothing measured for {unmeasured}" if unmeasured else ""))
        if r.get("diverged"):
            print(f"      SEMANTICS DIVERGED on {r['diverged']} -- "
                  f"restricted to {list(SEMANTICS_FREE_FIELDS)}")
        if r["still_empty"]:
            print(f"      still empty: {r['still_empty']}")

    print()
    diverged = [r for r in reports if r.get("diverged")]
    print(f"{len(files)} files considered, {len(EXCLUDED)} excluded by name")
    print(f"{len(touched)} {'written' if args.apply else 'would be written'}, "
          f"{len(aborted)} aborted")
    print(f"{len(diverged)} files where the current summariser no longer reproduces "
          f"the published rates (semantics-free fields only)")
    # Named, not just counted. These are the files the change does not reach,
    # and one of them is the 185-task gold ceiling -- the clearest instance of
    # the defect in the corpus. A count alone would let that read as routine.
    print(f"{len(sealed)} files left alone because another document asserts "
          f"their digest:")
    for r in sealed:
        print(f"    {_short(r['path'])}")
        print(f"        {r['reason']}")
    if not args.apply and touched:
        print("\ndry run -- re-run with --apply to write")
    return 1 if aborted else 0


if __name__ == "__main__":
    sys.exit(main())
