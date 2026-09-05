"""The 324 findings document has to quote the run it measured.

A paid measurement gets written up once and read for a long time afterwards,
and every number in the write-up is a number somebody typed. The report itself
is committed beside the document, so nothing here has to be taken on trust:
this file re-derives each figure from ``324-audio-accuracy-measured.json`` and
requires the document to state it.

The three exhibits are the part that would rot most quietly. A paraphrase of
what the model said is an interpretation; the document quotes it verbatim, and
every quoted fragment is checked back against the evidence field it came from.
A quote that drifts one word from the JSON fails here.

The last two checks are about honesty rather than accuracy. ``gpt-audio-1.5``
has no published price, so the run's cost is unknown -- and a document that
wrote ``$0`` for an unknown amount would be readable, tidy and false. And the
report has to carry ``measured: true``: a dry run scores 100% off a stub, and
publishing that shape as a result is the single worst thing this document
could do.
"""

import json
import re
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]

DOC_PATH = (
    REPO_ROOT
    / "tasks/rebuilding_grading_task/324-the-speech-it-heard-in-silence.md"
)
REPORT_PATH = (
    REPO_ROOT / "tasks/rebuilding_grading_task/324-audio-accuracy-measured.json"
)
WORKFLOW_PATH = REPO_ROOT / ".github/workflows/audio-accuracy-probe.yml"
AUDIO_MODULE_PATH = REPO_ROOT / "batch-runner/core/perception/audio.py"

# The document is Korean and uses U+2212 for a negative number, because that is
# what a reader sees. The JSON uses ASCII. Compare in one alphabet.
MINUS = "−"

# A row of a markdown table, split on the pipes with the outer ones dropped.
TABLE_ROW = re.compile(r"^\|(.+)\|\s*$")


def _cells(line: str) -> list[str]:
    match = TABLE_ROW.match(line)
    if match is None:
        return []
    return [cell.strip() for cell in match.group(1).split("|")]


def _plain(text: str) -> str:
    """Markdown bold and the ellipsis are presentation, not content."""
    return text.replace("**", "").replace("`", "")


@pytest.fixture(scope="module")
def doc() -> str:
    assert DOC_PATH.is_file(), f"{DOC_PATH.relative_to(REPO_ROOT)} is missing"
    return DOC_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def report() -> dict:
    assert REPORT_PATH.is_file(), (
        f"{REPORT_PATH.relative_to(REPO_ROOT)} is missing, so nothing the "
        f"document says can be checked"
    )
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def test_both_files_survive_a_fresh_clone():
    """``tasks/rebuilding_grading_task/`` is ignored with a per-file allowlist.

    Probed without ``--verbose``: with it, git reports the last matching
    pattern including negations and exits 0 either way, so only the exit code
    distinguishes "ignored" from "un-ignored by a later rule". 1 means no
    pattern ignores this path.
    """
    for path in (DOC_PATH, REPORT_PATH):
        relative = path.relative_to(REPO_ROOT)
        finished = subprocess.run(
            ["git", "check-ignore", str(relative)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert finished.returncode == 1, (
            f"{relative} is gitignored, so the document would reference a "
            f"file that is not in the repository"
        )


def test_the_report_is_a_measured_run_not_a_dry_one(report):
    """A dry run answers from the segment list and scores 100%."""
    assert report["measured"] is True
    assert report["pins"]["audio_deployment"] == "gpt-audio-1.5"
    assert report["pins"]["repeats"] == 3
    assert report["pins"]["claims"] == 20
    assert report["pins"]["true_claims"] == report["pins"]["false_claims"] == 10


def _allowed_numbers(report: dict) -> tuple[set[str], set[str]]:
    """Every percentage and every decimal the report can justify.

    Built by deriving rather than listing, so a figure that is in the document
    and not in here is a figure nobody can point at a source for.
    """
    acc = report["accuracy"]
    overall = acc["overall"]
    perm = acc["permutation"]
    j = acc["discrimination_j"]

    fails = sum(1 for call in report["calls"] if call["verdict"] == "fail")

    percentages = {
        f"{overall['accuracy'] * 100:.2f}",
        f"{acc['on_true_claims']['false_fail_rate'] * 100:.1f}",
        f"{acc['on_false_claims']['false_pass_rate'] * 100:.1f}",
        # What a judge that answers the same word every time scores on a
        # corpus with as many true claims as false ones.
        str(round(report["pins"]["true_claims"] / report["pins"]["claims"] * 100)),
        str(round(fails / overall["answered"] * 100)),
    }
    # The repeat-run figures the report itself carries, so the document can
    # cite them without a second source.
    percentages |= set(re.findall(r"(\d+(?:\.\d+)?)%", report["what_this_measures"]))

    decimals = set(percentages)
    decimals |= {
        f"{j['per_call']:.3f}",
        str(abs(j["per_claim_majority"])),
        str(perm["p_one_sided"]),
        f"{perm['smallest_attainable_p']:.5f}",
    }
    # The thresholds this design can reach, which is what makes the floor
    # worth printing at all.
    decimals |= {
        str(threshold)
        for threshold in (0.05, 0.01, 0.001)
        if perm["smallest_attainable_p"] < threshold
    }
    for call in report["calls"]:
        decimals |= {str(call["confidence"]), f"{call['confidence']:.2f}"}
        decimals |= set(re.findall(r"(?<![\w.])(\d+\.\d+)(?!\d)", call["evidence"]))
    for clip in report["clips"]:
        decimals.add(str(clip["duration_s"]))
        for segment in clip["segments"]:
            decimals |= {str(segment["start_s"]), str(segment["end_s"])}
    decimals |= set(
        re.findall(r"(?<![\w.])(\d+\.\d+)(?!\d)", report["pins"]["audio_model"])
    )
    return percentages, decimals


def test_every_number_in_the_document_comes_from_the_report(doc, report):
    """Not "the document mentions the right figure" -- "every figure in the
    document is a right one".

    A containment check passes while a second copy of the same number rots
    three sections away, which is the failure this whole probe was corrected
    for once already. So the check runs the other way: pull every percentage
    and every decimal out of the prose and require each to be derivable.
    """
    percentages, decimals = _allowed_numbers(report)

    found_percentages = set(re.findall(r"(\d+(?:\.\d+)?)%", doc))
    stray = found_percentages - percentages
    assert not stray, (
        f"the document states {sorted(stray)}% and the report does not "
        f"support it; supported: {sorted(percentages)}"
    )

    found_decimals = set(re.findall(r"(?<![\w.])(\d+\.\d+)(?!\d)", doc))
    stray = found_decimals - decimals
    assert not stray, (
        f"the document states the decimal(s) {sorted(stray)} and the report "
        f"does not support them"
    )

    # And the figures that matter most are required to be present, not merely
    # permitted.
    for required in (
        f"{report['accuracy']['overall']['accuracy'] * 100:.2f}%",
        f"{report['accuracy']['discrimination_j']['per_call']:.3f}",
        str(report["accuracy"]["permutation"]["p_one_sided"]),
        f"{report['accuracy']['permutation']['smallest_attainable_p']:.5f}",
    ):
        assert required in doc, f"the document does not state {required}"


def test_the_results_table_carries_the_measured_values(doc, report):
    """The two-column tables, read as label-to-value and checked by label.

    ``0.5`` is the permutation p and it is also the click interval eleven
    times over, so "the document contains 0.5" proves nothing about the p.
    Reading the row by its own label does.
    """
    acc = report["accuracy"]
    overall = acc["overall"]
    perm = acc["permutation"]

    rows: dict[str, str] = {}
    for line in doc.splitlines():
        cells = _cells(line)
        if len(cells) == 2:
            rows.setdefault(_plain(cells[0]), _plain(cells[1]))

    expected = {
        "답한 호출": str(overall["answered"]),
        "맞힘": str(overall["correct"]),
        "판별력 J (호출 단위)": f"{acc['discrimination_j']['per_call']:.3f}",
        "판별력 J (기준별 다수결)": f"{MINUS}{abs(acc['discrimination_j']['per_claim_majority'])}",
        "순열 p (한쪽 꼬리)": str(perm["p_one_sided"]),
        "이 설계가 낼 수 있는 가장 작은 p": f"{perm['smallest_attainable_p']:.5f}",
        "애매하게 답함(partial)": str(overall["hedged"]),
        "아예 못 답함(judge_error)": str(overall["unanswered"]),
        "과금 대상 호출": str(report["cost"]["billable_calls"]),
        "가격 없는 모델": report["cost"]["unpriced_models"][0],
        "모델": report["pins"]["audio_model"],
    }

    for label, value in expected.items():
        assert label in rows, f"the results tables have no {label!r} row"
        assert rows[label] == value, (
            f"{label}: the document says {rows[label]!r}, the report says "
            f"{value!r}"
        )

    # Every "p = x" in the prose is the same p.
    for stated in re.findall(r"\bp\s*=\s*(\d+(?:\.\d+)?)", doc):
        assert stated == str(perm["p_one_sided"]), (
            f"the document writes p = {stated}, the report measured "
            f"p = {perm['p_one_sided']}"
        )


def test_the_negative_discrimination_keeps_its_sign_everywhere(doc, report):
    """A minus sign is one character and it reverses the finding.

    The document prints the per-claim majority J three times. Every one of
    them has to carry the sign -- not just the first, which is all a
    containment check would prove.
    """
    majority = report["accuracy"]["discrimination_j"]["per_claim_majority"]
    assert majority < 0

    magnitude = re.escape(str(abs(majority)))
    signed = re.findall(rf"{MINUS}{magnitude}(?!\d)", doc)
    unsigned = re.findall(rf"(?<![\w.{MINUS}\-]){magnitude}(?!\d)", doc)

    assert len(signed) >= 3, (
        f"the document states the per-claim majority J {len(signed)} times "
        f"with its sign; it is quoted in the summary, the results table and "
        f"the section that explains it"
    )
    assert not unsigned, (
        f"the document states {str(abs(majority))!r} without a minus sign "
        f"{len(unsigned)} time(s), which reverses what was measured"
    )


def test_the_headline_counts_are_the_measured_ones(doc, report):
    """The whole-number figures, re-derived rather than re-read."""
    acc = report["accuracy"]
    overall = acc["overall"]
    perm = acc["permutation"]

    required = {
        "calls": str(overall["calls"]),
        "answered": str(overall["answered"]),
        "correct": str(overall["correct"]),
        "false fail count": str(overall["false_fail"]),
        "false pass count": str(overall["false_pass"]),
        "unanswered": str(overall["unanswered"]),
        "pairs": str(perm["pairs"]),
        "assignments": str(perm["assignments"]),
        "at least observed": str(perm["at_least_observed"]),
        "claims": str(report["pins"]["claims"]),
        "clips": str(report["pins"]["clips"]),
        "repeats": str(report["pins"]["repeats"]),
    }

    for label, value in required.items():
        assert value in doc, f"the document does not state the {label} ({value})"


def test_every_relabelling_count_is_one_of_the_two_measured_ones(doc, report):
    """The permutation counts are stated twice, so containment is not enough.

    ``at_least_observed`` appears in the summary and again in the section that
    explains it. A check that only asks whether the document contains ``512``
    still passes when one of the two copies is wrong -- which is the same
    second-copy rot the whole-number check above cannot see. Read the counter
    instead: every number the document counts relabellings with has to be one
    of the two the report measured, and both have to be there.
    """
    perm = report["accuracy"]["permutation"]
    measured = {str(perm["assignments"]), str(perm["at_least_observed"])}

    # ``가지`` is the counter this document uses for "ways of relabelling".
    # The digits can be followed by the markdown that closes a bold span or a
    # code span before the counter: "1024가지", "**512가지**", "`2^10 = 1024`가지".
    counted = set(re.findall(r"(\d+)[`*]*가지", doc))

    stray = counted - measured
    assert not stray, (
        f"the document counts {sorted(stray)} relabelling(s); the report "
        f"enumerated {perm['assignments']} assignments of which "
        f"{perm['at_least_observed']} did at least as well as observed"
    )
    assert counted == measured, (
        f"the document states the relabelling counts {sorted(counted)}; both "
        f"{sorted(measured)} have to appear"
    )


def test_the_family_table_is_the_measured_one(doc, report):
    """Parsed out of the document and compared row by row.

    The table is the document's argument -- "six answered, three correct"
    repeated down the page is what shows a judge answering the same word every
    time -- so a hand-edited cell here would break the reasoning, not just a
    number.
    """
    families = report["accuracy"]["by_family"]
    seen: dict[str, tuple[int, ...]] = {}

    for line in doc.splitlines():
        cells = _cells(line)
        if len(cells) != 6:
            continue
        name = _plain(cells[0])
        if name not in families:
            continue
        try:
            seen[name] = tuple(int(_plain(cell)) for cell in cells[1:])
        except ValueError:  # the header row, or a prose table
            continue

    assert set(seen) == set(families), (
        f"the family table lists {sorted(seen)}, the report has "
        f"{sorted(families)}"
    )

    for name, row in families.items():
        expected = (
            row["answered"],
            row["correct"],
            row["false_fail"],
            row["false_pass"],
            row["unanswered"],
        )
        assert seen[name] == expected, f"{name}: document {seen[name]} != {expected}"


def test_the_verdict_grid_is_the_measured_one(doc, report):
    """All sixty verdicts, in the order the document prints them."""
    grid: dict[str, dict[int, str]] = {}
    holds: dict[str, bool] = {}
    for call in report["calls"]:
        grid.setdefault(call["claim_id"], {})[call["repeat"]] = call["verdict"]
        holds[call["claim_id"]] = call["holds"]

    seen: dict[str, tuple[str, ...]] = {}
    for line in doc.splitlines():
        cells = _cells(line)
        # Five columns, and the second one is the truth marker -- which is
        # what separates this table from the unanswered-calls table, whose
        # second column is a repeat number.
        if len(cells) != 5 or cells[1] not in ("참", "거짓"):
            continue
        claim_id = _plain(cells[0])
        if claim_id not in grid:
            continue
        seen[claim_id] = tuple(_plain(cell) for cell in cells[1:])

    assert set(seen) == set(grid), (
        f"the verdict grid is missing {sorted(set(grid) - set(seen))}"
    )

    for claim_id, row in seen.items():
        truth, *verdicts = row
        assert truth == ("참" if holds[claim_id] else "거짓"), (
            f"{claim_id} is marked {truth!r} but the report says "
            f"holds={holds[claim_id]}"
        )
        expected = [grid[claim_id][repeat] for repeat in sorted(grid[claim_id])]
        assert list(verdicts) == expected, (
            f"{claim_id}: document {verdicts} != {expected}"
        )


def test_every_quoted_verdict_is_verbatim(doc, report):
    """The exhibits are quotations, and a quotation has to be exact.

    Fragments joined by an ellipsis are checked one at a time, because that is
    what the ellipsis means. Korean spans are the document's own prose and are
    not looked for in an English report.
    """
    evidence = [call["evidence"] for call in report["calls"] if call["evidence"]]
    hangul = re.compile(r"[가-힣]")
    quoted = re.findall(r'"([^"\n]{12,})"', doc)

    assert len(quoted) >= 15, (
        f"only {len(quoted)} quotations found; the three exhibits carry "
        f"sixteen between them"
    )

    checked = 0
    for quotation in quoted:
        if hangul.search(quotation):
            continue
        for fragment in _plain(quotation).split("…"):
            fragment = fragment.strip().rstrip(".")
            if not fragment:
                continue
            assert any(fragment in item for item in evidence), (
                f"the document quotes {fragment!r}, which no call's evidence "
                f"contains"
            )
            checked += 1

    assert checked >= 15, f"only {checked} fragments were checkable"


def test_the_silence_exhibit_is_what_the_judge_said(report):
    """The document's centrepiece, asserted against the report directly.

    Every sample in this clip is zero. If a future run of this probe stopped
    producing a confident "a human voice is heard", the document's title would
    be describing something that no longer happened, and it should fail here
    rather than stay on the shelf.
    """
    presence = {
        (call["claim_id"], call["repeat"]): call
        for call in report["calls"]
        if call["family"] == "presence"
    }

    heard_a_voice = presence[("presence_false", 1)]
    assert heard_a_voice["verdict"] == "pass"
    assert heard_a_voice["confidence"] >= 0.95
    assert "human voice" in heard_a_voice["evidence"]

    heard_silence = presence[("presence_true", 3)]
    assert heard_silence["confidence"] >= 0.95
    assert "complete silence" in heard_silence["evidence"]

    # Same file, same run, opposite descriptions, both stated confidently.
    assert heard_a_voice["clip_id"] == heard_silence["clip_id"] == "pure_silence"


def test_the_tempo_exhibit_is_what_the_judge_said(report):
    """The mechanism the document names: the verdict follows the question.

    Under the coarse criteria the judge confirmed whichever tempo it was
    offered; under the +/-1 BPM criteria it refused every time. Both halves are
    required, because either alone has an innocent reading.
    """
    coarse = [c for c in report["calls"] if c["family"] == "tempo_coarse"]
    fine = [c for c in report["calls"] if c["family"] == "tempo_fine"]

    assert len(coarse) == len(fine) == 6
    assert {c["verdict"] for c in coarse} == {"pass"}
    assert {c["verdict"] for c in fine} == {"fail"}

    # The true clicks are 0.5 s apart. Offered 60 BPM, the judge reported one
    # second; offered 120, it reported half a second.
    offered_sixty = [c for c in coarse if c["claim_id"].endswith("_false")]
    assert len(offered_sixty) == 3
    for call in offered_sixty:
        lowered = call["evidence"].lower()
        assert "second" in lowered
        assert "0.5" not in lowered

    assert all("0.5" in c["evidence"] for c in coarse if c["claim_id"].endswith("_true"))

    # Every interval the document quotes from the fine criteria, and none of
    # them is the true one.
    quoted_intervals = ["0.7s", "86 BPM", "0.8 seconds", "75 bpm", "110 clicks",
                        "29 clicks in 30s", "58 BPM"]
    joined = " ".join(c["evidence"] for c in fine)
    for fragment in quoted_intervals:
        assert fragment in joined, fragment


def test_the_document_records_the_one_time_it_was_right(doc, report):
    """The exception the document declines to leave out.

    One fine-criteria call did report 120 BPM. Its verdict is still ``fail``
    and that fail is still correct, so it changes no number -- which is
    exactly why it would be easy to drop, and why the document says it.
    """
    exception = [
        call
        for call in report["calls"]
        if call["family"] == "tempo_fine" and "around 120 BPM" in call["evidence"]
    ]

    assert len(exception) == 1
    assert exception[0]["claim_id"] == "tempo_fine_false"
    assert exception[0]["verdict"] == "fail"
    assert exception[0]["outcome"] == "correct"
    assert "132" in doc


def test_the_unanswered_calls_are_named_with_their_cause(doc, report):
    """Six calls returned no verdict, and they are excluded rather than
    scored zero. A reader has to be able to see which six and why."""
    unanswered = [c for c in report["calls"] if c["verdict"] == "judge_error"]

    assert len(unanswered) == report["accuracy"]["overall"]["unanswered"]
    assert {c["judge_error"] for c in unanswered} == {
        "provider_error:JSONDecodeError"
    }
    assert "provider_error:JSONDecodeError" in doc

    for call in unanswered:
        assert f"`{call['claim_id']}`" in doc
        assert f"`{call['clip_id']}`" in doc
        assert str(call["output_tokens"]) in doc
        assert str(round(call["latency_ms"])) in doc


def test_the_cost_is_recorded_as_unknown_and_never_as_zero(doc, report):
    """An unpriced model costs an unknown amount, not nothing.

    A zero figure is not banned outright, because the document's job is partly
    to say that this run was *not* free. What is banned is writing one without
    the denial: every ``$0`` and every 0원 has to be followed by 아니- ("is
    not"), so a later edit that trims the qualifier and leaves the figure
    fails here.
    """
    cost = report["cost"]

    assert cost["pricing_complete"] is False
    assert cost["unpriced_models"] == ["gpt-audio-1.5"]
    assert cost["estimated_cost_usd"] is None
    assert cost["billable_calls"] == report["accuracy"]["overall"]["calls"]

    assert "미등록" in doc
    assert str(cost["billable_calls"]) in doc

    denied = 0
    for pattern in (r"\$0(?![.\d])", r"0원"):
        for match in re.finditer(pattern, doc):
            window = doc[match.end():match.end() + 24]
            assert "아니" in window, (
                f"the document writes {match.group()!r} at offset "
                f"{match.start()} without saying it is not the cost"
            )
            denied += 1

    assert denied >= 2, "the document never says this run was not free"

    for forbidden in ("0 USD", "비용 없음", "무료"):
        assert forbidden not in doc, (
            f"the document writes {forbidden!r} for a run whose price is "
            f"unknown"
        )


def test_the_approval_record_the_document_quotes_is_the_real_one(doc, report):
    """The document reproduces the gate's log line, so it has to match it.

    This is the line that says what was authorised. It went stale once
    already -- it said twelve criteria after the corpus became twenty -- and
    a copy of it in a document is one more place for that to happen.
    """
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    claims = report["pins"]["claims"]
    repeats = report["pins"]["repeats"]

    criteria_line = (
        f"criteria   = {claims} "
        f"({report['pins']['true_claims']} true / "
        f"{report['pins']['false_claims']} false)"
    )
    assert criteria_line in workflow
    assert criteria_line in doc

    assert f"$(({claims} * PROBE_REPEATS))" in workflow
    assert f"calls      = {claims * repeats}" in doc
    assert claims * repeats == report["accuracy"]["overall"]["calls"]


def test_the_prompt_line_the_document_blames_is_still_there(doc):
    """The document explains the recurring "30s" in the evidence by quoting
    the system prompt. If that wording changes, the explanation is wrong."""
    source = AUDIO_MODULE_PATH.read_text(encoding="utf-8")

    assert 'f"a head-only slice (first {int(trim_seconds)}s) of"' in source
    assert "head-only slice (first 30s)" in doc


def test_the_document_says_what_it_did_not_measure(doc):
    """The card asked for speech and music; this is the music half.

    A findings document that quietly dropped the half it could not do would
    read as complete. The limit is stated in the document, and it is stated
    here so that removing it fails.
    """
    assert "말소리" in doc
    assert "음악 절반" in doc
    assert "gold_audio_repeat_v2_sol_max.yaml" in doc


def test_the_document_points_at_the_run_it_came_from(doc, report):
    """A reader has to be able to open the run and the artifact."""
    assert "actions/runs/33883388098" in doc
    assert REPORT_PATH.name in doc
    assert report["what_this_measures"].startswith(
        "Whether the audio sub-judge's verdict is correct"
    )
