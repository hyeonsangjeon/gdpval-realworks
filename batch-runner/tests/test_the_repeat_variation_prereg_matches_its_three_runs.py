"""The repeat-variation preregistration has to agree with the runs it pins.

`315-repeat-variation-prereg.md` fixes, before the analysis is written, how the
grader's own run-to-run wobble will be measured. A preregistration is only worth
something if it is bound to data: otherwise the numbers it quotes drift, the
identity table it promises to fail closed on quietly stops matching the files,
and by the time the report lands nobody can tell whether the method was chosen
before or after the answer.

So this file reads the document and checks it against the three 30-task grading
runs it names -- all three tracked in the repository, no model calls, no network.

* Section 4's pinned table. Every row is parsed out of the markdown and compared
  to all three run files. This is the same table the analysis will fail closed
  on, so a row that has silently stopped matching is caught here rather than at
  report time. The row count is checked against the prose that counts it, and
  the payload-schema row is checked twice: once against the files (`1.3`) and
  once against the live `SCHEMA_VERSION`, which the document says has since
  moved to `1.4`. If someone bumps the constant again the document has to say so.

* The same-file-twice guard. Three distinct content hashes, three distinct
  `graded_at`, one identical filename. Comparing a run with itself yields a
  standard deviation of zero, and zero passes every gate ever written.

* Section 3's rates and section 5's denominator table. 450 score-outcome
  differences and 204 verdict differences over 4,299 item pairs, the 246 that
  keep the verdict but move the score, the 23 two-step `pass`/`fail` moves, the
  three tasks whose `total_max` moved, and the identity between `judge_error`
  and `score_excluded`. These are recomputed from the files, not read.

* Sections 9 and 11's censuses, including that this cohort holds zero `audio`
  items -- the structural reason the 38% audio flip cannot leak into the
  interval this analysis reports.

What this file deliberately does *not* do is re-run the 10,000-resample
bootstrap behind section 6. That takes twenty-odd seconds and belongs to the
analysis script, which will regenerate its own block and byte-compare it. Here
only the arithmetic tying the two interval widths together is checked, so a
transcription slip in a width or in the 1.48x ratio is still caught.
"""

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

import pytest

from step8_grade import SCHEMA_VERSION


REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = REPO_ROOT / "tasks/rebuilding_grading_task/315-repeat-variation-prereg.md"

#: The three runs share one filename; only the directory differs. Located by
#: shape so that a re-graded sibling landing in the same digest directory under
#: a different grader fingerprint cannot be picked up by accident.
RUN_GLOB = (
    "exp_gold_baseline__judge_gpt-5_6-sol__gold_ceiling_30_v2_sol_max__"
    "cfg_d1bfc8217c9981d2__*__src_c33d9d55703fbf5d__v2.2.json"
)

VERDICTS = ("pass", "partial", "fail", "judge_error")

#: Distance in verdict space, so that a two-step move can be told from an
#: adjacent one. `judge_error` is off this axis: it is a grading failure, not a
#: harsher or gentler reading, so pairs involving it are counted separately.
VERDICT_RANK = {"fail": 0, "partial": 1, "pass": 2}


# --------------------------------------------------------------------------
# document parsing
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def doc() -> str:
    assert DOC_PATH.exists(), f"preregistration missing: {DOC_PATH}"
    return DOC_PATH.read_text(encoding="utf-8")


def _section(doc: str, number: int) -> str:
    """Return one numbered section, so prose searches cannot cross into another.

    Tokens like ``text`` or ``pass`` appear in several sections; an unscoped
    search would let a census in section 9 be satisfied by a sentence in
    section 3.
    """
    match = re.search(
        rf"^## {number}\. .*?(?=^## \d+\. |\Z)", doc, re.M | re.S
    )
    assert match, f"section {number} not found in the preregistration"
    return match.group(0)


def _rows(section: str) -> list[list[str]]:
    """Return the markdown table rows of a section as stripped cell lists."""
    out = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|") or set(line) <= set("|- "):
            continue
        out.append([cell.strip() for cell in line.strip("|").split("|")])
    return out


def _identity_rows(doc: str) -> dict[str, str]:
    """Section 4's pinned table, label -> value cell."""
    rows = _rows(_section(doc, 4))
    table = {r[0]: r[1] for r in rows if len(r) == 2 and r[0] and r[0] != "값"}
    assert table, "section 4 has no pinned identity table"
    return table


def _codes(cell: str) -> list[str]:
    """Backticked tokens in a table cell, with any elision marker removed."""
    return [tok.strip("…") for tok in re.findall(r"`([^`]+)`", cell)]


# --------------------------------------------------------------------------
# run files
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def run_paths(doc: str) -> list[Path]:
    digest = re.search(r"data/grades/_diagnostic/([0-9a-f]{8})", doc)
    assert digest, "section 4 does not name the grade directory"
    roots = sorted(
        (REPO_ROOT / "data/grades/_diagnostic").glob(f"{digest.group(1)}*")
    )
    assert len(roots) == 1, f"expected one directory for {digest.group(1)}, got {roots}"
    root = roots[0]

    paths = sorted(root.glob(RUN_GLOB))
    assert len(paths) == 1, f"expected one run-1 file in {root}, got {paths}"
    for repeat in ("run-002", "run-003"):
        found = sorted((root / "_repeats" / repeat).glob(RUN_GLOB))
        assert len(found) == 1, f"expected one file in {repeat}, got {found}"
        paths += found
    return paths


@pytest.fixture(scope="module")
def runs(run_paths: list[Path]) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in run_paths]


@pytest.fixture(scope="module")
def item_maps(runs: list[dict]) -> list[dict]:
    """One (task_id, rubric_item_id) -> item mapping per run."""
    maps = []
    for run in runs:
        by_key = {}
        for task in run["tasks"]:
            for item in task["items"]:
                key = (task["task_id"], item["rubric_item_id"])
                assert key not in by_key, f"duplicate rubric item {key}"
                by_key[key] = item
        maps.append(by_key)
    return maps


@pytest.fixture(scope="module")
def pairs() -> list[tuple[int, int]]:
    return [(0, 1), (0, 2), (1, 2)]


# --------------------------------------------------------------------------
# section 4 -- the table the analysis fails closed on
# --------------------------------------------------------------------------


def test_the_pinned_identity_table_matches_every_run(doc, runs):
    table = _identity_rows(doc)

    def cell(fragment: str) -> str:
        hits = [v for k, v in table.items() if fragment in k]
        assert len(hits) == 1, f"section 4 row for {fragment!r}: {hits}"
        return hits[0]

    for index, run in enumerate(runs, start=1):
        where = f"run {index}"

        assert run["expected_ordered_task_ids_sha256"].startswith(
            _codes(cell("과제 목록 지문"))[0]
        ), where
        assert str(run["expected_task_count"]) == "30" == re.sub(
            r"\D", "", cell("과제 수")
        ), where
        assert run["grader_source_hash"].startswith(
            _codes(cell("채점기 소스 지문"))[0]
        ), where

        config_name, config_hash = _codes(cell("채점 설정"))
        assert config_name == f"{run['judge']['config_name']}.yaml", where
        assert config_hash == f"cfg_{run['judge']['config_hash']}", where

        model, deployment = _codes(cell("모델·배포"))
        assert model == run["judge"]["model"], where
        assert deployment == run["judge"]["deployment"], where

        assert _codes(cell("API 버전"))[0] == run["judge"]["api_version"], where

        effort, temperature, seed = _codes(cell("reasoning effort"))
        assert effort == run["judge"]["reasoning_effort"], where
        assert float(temperature) == float(run["judge"]["temperature"]), where
        assert int(seed) == int(run["judge"]["seed"]), where

        assert cell("판정 프롬프트") == run["prompt"]["version"], where
        assert run["rubric"]["revision"].startswith(_codes(cell("루브릭"))[0]), where
        assert run["source_inference_revision"].startswith(
            _codes(cell("정답본 revision"))[0]
        ), where

        renderer = cell("렌더러 지문")
        fingerprint = run["renderer_fingerprint"]
        assert fingerprint["libreoffice_version"] in renderer, where
        assert fingerprint["pymupdf_version"] in renderer, where

        assert _codes(cell("payload 스키마"))[0] == run["schema_version"], where


def test_the_prose_counts_the_rows_it_actually_pinned(doc):
    """Adding a row without touching the sentence that counts them is a slip."""
    section = _section(doc, 4)
    stated = re.search(r"다음 (\d+)가지 중 하나라도 다르면", section)
    assert stated, "section 4 does not say how many dimensions it pins"
    assert len(_identity_rows(doc)) == int(stated.group(1))

    listed = re.search(r"§4의 (\d+)개 지문", _section(doc, 12))
    assert listed, "section 12 does not refer back to the pinned count"
    assert int(listed.group(1)) == int(stated.group(1))


def test_the_schema_row_is_pinned_to_the_files_not_to_the_code(doc, runs):
    """The document pins `1.3` on purpose; it must say so when the code moves."""
    section = _section(doc, 4)
    claimed_current = re.search(r"`SCHEMA_VERSION`은 \*\*`([\d.]+)`로 올라갔다", section)
    assert claimed_current, "section 4 does not name the current SCHEMA_VERSION"
    assert claimed_current.group(1) == SCHEMA_VERSION, (
        "step8_grade.SCHEMA_VERSION is now "
        f"{SCHEMA_VERSION!r}; update section 4 of the preregistration, which "
        f"still says {claimed_current.group(1)!r}"
    )
    assert {run["schema_version"] for run in runs} == {"1.3"}, (
        "the pinned files no longer carry schema 1.3"
    )


def test_the_three_runs_are_not_the_same_file_three_times(doc, run_paths, runs):
    """Self-comparison yields zero variance, and zero clears every gate."""
    assert len({p.name for p in run_paths}) == 1, "the three runs must share a filename"

    digests = {hashlib.sha256(p.read_bytes()).hexdigest() for p in run_paths}
    assert len(digests) == 3, "two of the three run files are byte-identical"

    stamps = [run["graded_at"] for run in runs]
    assert len(set(stamps)) == 3, f"graded_at collision: {stamps}"

    section = _section(doc, 4)
    for stamp in stamps:
        tail = stamp.split("T")[1]
        assert stamp in section or tail in section, (
            f"section 4 does not record graded_at {stamp}"
        )


def test_every_run_grades_the_same_items(item_maps):
    keys = [set(m) for m in item_maps]
    assert keys[0] == keys[1] == keys[2]
    assert len(keys[0]) == 1433


def test_every_run_finished_all_thirty_tasks(runs):
    for index, run in enumerate(runs, start=1):
        assert run["run_status"] == "final", f"run {index}"
        assert run["summary"]["graded_tasks"] == 30, f"run {index}"
        assert run["summary"]["error_tasks"] == 0, f"run {index}"


# --------------------------------------------------------------------------
# section 5 -- the moving denominator
# --------------------------------------------------------------------------


def test_judge_error_and_score_excluded_are_the_same_events(item_maps):
    errors, excluded = set(), set()
    for index, mapping in enumerate(item_maps):
        for key, item in mapping.items():
            if item["verdict"] == "judge_error":
                errors.add((index, key))
            if item["score_excluded"]:
                excluded.add((index, key))
    assert errors == excluded, "score exclusion has a second cause"
    assert len(errors) == 4
    assert len({key for _, key in errors}) == 3


def test_the_denominator_table_matches_the_runs(doc, runs):
    rows = [r for r in _rows(_section(doc, 5)) if len(r) == 4 and re.fullmatch(r"`[0-9a-f]{8}`", r[0])]
    assert len(rows) == 3, "section 5 does not list three tasks with moving totals"

    totals = {}
    for run in runs:
        for task in run["tasks"]:
            totals.setdefault(task["task_id"][:8], []).append(task["total_max"])

    moved = {short for short, values in totals.items() if len(set(values)) > 1}
    assert moved == {r[0].strip("`") for r in rows}, (
        "section 5 lists the wrong set of tasks whose max score moved"
    )
    for row in rows:
        stated = [int(re.sub(r"\D", "", cell)) for cell in row[1:]]
        assert stated == totals[row[0].strip("`")], f"task {row[0]}"


def test_the_excluded_item_count_matches_the_prose(doc, item_maps):
    excluded = {
        key
        for mapping in item_maps
        for key, item in mapping.items()
        if item["score_excluded"]
    }
    section = _section(doc, 5)
    stated = re.search(r"빠지는 항목은 ([\d,]+)개 중 (\d+)개", section)
    assert stated, "section 5 does not state how many items drop out"
    assert int(stated.group(1).replace(",", "")) == len(item_maps[0])
    assert int(stated.group(2)) == len(excluded) == 3


# --------------------------------------------------------------------------
# section 3 -- the two rates, and why they differ
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def disagreement(item_maps, pairs) -> dict:
    verdict_per_pair, score_per_pair = [], []
    both = same_verdict_moved_score = two_step = 0
    for left, right in pairs:
        v = s = 0
        for key, item in item_maps[left].items():
            other = item_maps[right][key]
            verdict_differs = item["verdict"] != other["verdict"]
            score_differs = (item["awarded_score"], item["score_excluded"]) != (
                other["awarded_score"],
                other["score_excluded"],
            )
            v += verdict_differs
            s += score_differs
            both += verdict_differs and score_differs
            same_verdict_moved_score += score_differs and not verdict_differs
            ranks = (
                VERDICT_RANK.get(item["verdict"]),
                VERDICT_RANK.get(other["verdict"]),
            )
            if None not in ranks and abs(ranks[0] - ranks[1]) == 2:
                two_step += 1
        verdict_per_pair.append(v)
        score_per_pair.append(s)
    total = len(item_maps[0]) * len(pairs)
    return {
        "total": total,
        "verdict_per_pair": verdict_per_pair,
        "score_per_pair": score_per_pair,
        "verdict": sum(verdict_per_pair),
        "score": sum(score_per_pair),
        "same_verdict_moved_score": same_verdict_moved_score,
        "two_step": two_step,
    }


def test_the_two_disagreement_rates_reproduce(doc, disagreement):
    section = _section(doc, 3)
    rows = {
        r[0]: r[1:]
        for r in _rows(section)
        if len(r) == 3 and ("점수 결과" in r[0] or "판정" in r[0])
    }
    assert len(rows) == 2, "section 3 does not tabulate both rates"

    def stated(fragment):
        key = next(k for k in rows if fragment in k)
        count, per_pair = rows[key]
        n = int(re.search(r"([\d,]+)", count).group(1).replace(",", ""))
        pct = float(re.search(r"\(([\d.]+)%\)", count).group(1))
        split = [int(x) for x in re.findall(r"\d+", per_pair)]
        return n, pct, split

    total = disagreement["total"]
    assert total == 4299

    n, pct, split = stated("점수 결과")
    assert n == disagreement["score"] == 450
    assert split == disagreement["score_per_pair"] == [153, 144, 153]
    assert pct == round(100 * n / total, 2)

    n, pct, split = stated("판정")
    assert n == disagreement["verdict"] == 204
    assert split == disagreement["verdict_per_pair"] == [66, 65, 73]
    assert pct == round(100 * n / total, 2)


def test_the_verdict_rate_is_a_subset_of_the_score_rate(doc, disagreement):
    """The 246 the document names are what makes the two numbers reconcilable."""
    section = _section(doc, 3)
    stated = re.search(r"그런 경우가 (\d+)개다", section)
    assert stated, "section 3 does not count the same-verdict score moves"
    assert int(stated.group(1)) == disagreement["same_verdict_moved_score"] == 246
    assert (
        disagreement["score"] - disagreement["same_verdict_moved_score"]
        <= disagreement["verdict"]
    )

    two_step = re.search(r"그중 (\d+)개는 `pass`↔`fail`", section)
    assert two_step, "section 3 does not count the two-step moves"
    assert int(two_step.group(1)) == disagreement["two_step"] == 23


def test_the_corpus_means_move_only_as_far_as_stated(doc, runs):
    published = [run["summary"]["openai_compat"]["avg_score_pct"] for run in runs]
    section = _section(doc, 3)
    stated = re.search(
        r"말뭉치 평균은 ([\d.]+) → ([\d.]+) → ([\d.]+)로 ([\d.]+)pp", section
    )
    assert stated, "section 3 does not state the corpus means"
    assert [float(stated.group(i)) for i in (1, 2, 3)] == published
    assert float(stated.group(4)) == round(max(published) - min(published), 2)


def test_the_per_task_gaps_are_in_the_stated_band(doc, runs, pairs):
    per_run = [{t["task_id"]: t["pct"] for t in run["tasks"]} for run in runs]
    means, largest = [], 0.0
    for left, right in pairs:
        gaps = [
            abs(per_run[left][task] - per_run[right][task]) for task in per_run[0]
        ]
        means.append(sum(gaps) / len(gaps))
        largest = max(largest, max(gaps))

    stated = re.search(
        r"절대값 평균 ([\d.]+)~([\d.]+)pp, 최대 ([\d.]+)pp", _section(doc, 3)
    )
    assert stated, "section 3 does not state the per-task gap band"
    low, high, cap = (float(stated.group(i)) for i in (1, 2, 3))
    assert low <= min(means) and max(means) <= high, means
    assert math.isclose(cap, largest, abs_tol=0.005), largest


# --------------------------------------------------------------------------
# sections 9 and 11 -- what is present, and what is structurally absent
# --------------------------------------------------------------------------


def test_the_verdict_census_matches_and_the_vocabulary_is_closed(doc, item_maps):
    census = Counter(
        item["verdict"] for mapping in item_maps for item in mapping.values()
    )
    assert set(census) <= set(VERDICTS), f"unexpected verdict: {set(census) - set(VERDICTS)}"

    section = _section(doc, 9)
    for verdict in VERDICTS:
        stated = re.search(rf"`{verdict}` ([\d,]+)", section)
        assert stated, f"section 9 does not count `{verdict}`"
        assert int(stated.group(1).replace(",", "")) == census[verdict], verdict
    assert sum(census.values()) == 4299


def test_the_selection_and_decision_censuses_are_unanimous(doc, item_maps):
    section = _section(doc, 9)
    for field, expected in (("selection_status", "ok"), ("decided_by", "judge")):
        values = Counter(
            item[field] for mapping in item_maps for item in mapping.values()
        )
        assert values == {expected: 4299}, f"{field}: {values}"
        assert re.search(rf"`{field}`.*`{expected}` ([\d,]+) / ([\d,]+)", section), (
            f"section 9 does not report {field}"
        )


def test_the_tool_call_proxy_distribution_matches(doc, item_maps):
    census = Counter(
        (item.get("tools_used") or []).count("read_deliverable")
        for mapping in item_maps
        for item in mapping.values()
    )
    section = _section(doc, 9)
    stated = dict(
        (int(calls), int(count.replace(",", "")))
        for calls, count in re.findall(r"(\d+)회 ([\d,]+)", section)
    )
    assert stated == dict(census), f"section 9 proxy census drifted: {dict(census)}"
    assert census[0] == 92, "the zero-call tail is the point of the proxy"


def test_this_cohort_holds_no_audio_items(doc, runs):
    census = Counter(
        item["routing_modality"] for task in runs[0]["tasks"] for item in task["items"]
    )
    assert census["audio"] == 0
    section = _section(doc, 11)
    for modality, count in census.items():
        stated = re.search(rf"`{modality}` ([\d,]+)", section)
        assert stated, f"section 11 does not count `{modality}`"
        assert int(stated.group(1).replace(",", "")) == count, modality
    assert "`audio`는 0건이다" in section


# --------------------------------------------------------------------------
# sections 6 and 8 -- the numbers the analysis will be held to
# --------------------------------------------------------------------------


def test_the_design_effect_arithmetic_closes(doc):
    """The bootstrap itself belongs to the analysis; its arithmetic lives here."""
    section = _section(doc, 6)
    widths = {}
    for row in _rows(section):
        if len(row) != 3 or "bootstrap" not in row[0]:
            continue
        interval = [float(x) for x in re.findall(r"[\d.]+", row[1])]
        width = float(re.search(r"([\d.]+)pp", row[2]).group(1))
        assert math.isclose(interval[1] - interval[0], width, abs_tol=0.001), row
        widths["cluster" if "cluster" in row[0] else "naive"] = width
    assert set(widths) == {"naive", "cluster"}, "section 6 lost one of its two rows"

    stated = re.search(r"단순 방법은 구간을 ([\d.]+)배 좁게", section)
    assert stated, "section 6 does not state the design effect"
    assert math.isclose(
        float(stated.group(1)),
        round(widths["cluster"] / widths["naive"], 2),
        abs_tol=0.005,
    )
    assert widths["cluster"] > widths["naive"], "clustering must widen the interval"

    for value in (re.search(r"seed `(\d+)`", section), re.search(r"B `([\d,]+)`", section)):
        assert value, "section 6 quotes an interval without naming how it was drawn"
    fixed = _section(doc, 8)
    assert re.search(r"seed `(\d+)`", section).group(1) in fixed
    assert re.search(r"B `([\d,]+)`", section).group(1) in fixed


def test_the_target_precision_is_justified_by_the_gap_it_must_resolve(doc, runs):
    section = _section(doc, 8)
    target = re.search(r"\*\*반폭 ≤ ([\d.]+)pp\*\*", section)
    gap = re.search(r"차이가 \*\*([\d.]+)pp\*\*", section)
    assert target and gap, "section 8 does not fix a target or justify it"

    threshold = re.search(r"([\d.]+)%가 90%", section)
    assert threshold, "section 8 does not name the score it is comparing to 90%"
    observed = float(threshold.group(1))
    assert observed == runs[0]["summary"]["openai_compat"]["avg_score_pct"]
    assert math.isclose(float(gap.group(1)), round(90 - observed, 2), abs_tol=0.005)
    assert float(target.group(1)) < float(gap.group(1))


def test_the_document_never_prices_the_unpriced_model_at_zero(doc):
    """`$0` is only ever allowed as the thing being refused, never as a figure.

    Checked against the words that immediately follow the token, not against
    the whole line: a line can say the price table lacks the model *and* then
    write the amount as zero, and a line-level search would call that fine.
    """
    occurrences = list(re.finditer(r"\$0", doc))
    assert occurrences, "the no-$0 rule has vanished from the document"
    for found in occurrences:
        tail = doc[found.end() : found.end() + 24]
        assert re.match(r"[`\s]*(이|으로|로)?\s*(아니|만들지|적지|쓰지)", tail), (
            f"a bare $0 survives: ...{doc[found.start() - 40 : found.end() + 24]}..."
        )
