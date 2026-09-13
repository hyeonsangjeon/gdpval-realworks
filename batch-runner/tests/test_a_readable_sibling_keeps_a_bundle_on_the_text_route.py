"""The readable-sibling hole, measured over every grade this repo has published.

``322`` §9 left a limit standing and pinned it with a synthetic test:

    If a readable file is selected alongside an unreadable one, the door does
    not open. A ``.txt`` next to a video keeps that bundle on the text route.

The door is ``resolve_runtime_routing``'s escalation gate. A criterion with no
visual keyword reaches the vision path only if all three hold:

    (a) the text probe says a selected file yields no text,
    (b) the criterion is TEXT or FORMATTING,
    (c) *every* selected suffix is renderable.

Clause (a) already tolerates a partly-readable bundle -- that is what
``some_selected_path_lacks_text`` was added for. Clause (c) does not: one
``.py`` or ``.txt`` sibling fails ``issubset`` and the bundle stays on the text
route no matter what the probe found. That is the hole.

This file records what it is worth. When ``323`` measured it, 12 payloads
carried a mixed renderable/non-renderable bundle under a TEXT or FORMATTING
criterion, and they belonged to just three tasks:

    46fc494e   .pdf + .py            70 items x 4 payloads   (gold-185)
    58ac1cc5   .docx .pdf + .txt     39 items x 6 payloads   (220-task runs)
    bf68f2ad   .xlsx + .txt          34-35 items x 6 payloads

722 items in all. In every one of them the renderable member yields text, so
clause (a) closes the gate before clause (c) is ever consulted. Clause (c)
blocked **nothing**.

exp035 then landed and multiplied that corpus by five: 10 more payloads, 48
more tasks, 3,324 more items, 4,046 in all. This file separates the two,
because they support the finding to different depths.

The **outcome** is pinned across all of it and is directly observed. Every one
of the 4,046 items records ``perception_called: false``: no mixed bundle has
ever escalated, in any published grade, under either era. That is read off the
payload rather than inferred.

The **mechanism** is pinned only where the payload can carry it. ``323``'s
"clause (a) shut the gate, so clause (c) blocked nothing" is a claim about
*which* clause closed it, and it needs extraction evidence to stand. exp035
supplies that for 28 of its 48 tasks and 84 of its 3,324 items; for the other
20 tasks the payload cannot say whether (a) or (c) refused the bundle. So
``323``'s zero is **stale rather than falsified** -- it was measured over a
three-task corpus that is no longer what is committed -- and the 20 tasks are
named below rather than folded into a number.

Either way the hole has no observed causal effect on any published grade in
this repository, which is why ``322`` was right to pin it rather than change
the gate: loosening clause (c) buys zero measured benefit and spends it against
the per-task image budget, which is where escalation has already gone wrong
once. PR #303 fixed an escalation that rendered the *whole* bundle rather than
the unreadable member; on task ``43dc9778`` that needed 134 images against a
budget of 72, and all 67 of the task's items were excluded -- 87.36% to 0.00%
(``311`` §9).

Two things this file deliberately does not assert.

The gold-185 escalation scan -- 8,184 text/formatting items with selected
paths, 48 permitting escalation, 48 firing, 0 blocked by clause (c) -- probes
files under ``data/gdpval-local/``, which is gitignored. It is not reproducible
in CI and is recorded in ``323`` instead, with the command that produced it.

For ``46fc494e`` the payload cannot show this. All 280 of its items carry
evidence, and not one carries an extraction marker -- the strings are Python
source fragments and prose, neither of which proves the ``.pdf`` was read. That
the ``.pdf`` yields text was established by probing the file directly, which CI
cannot do. What the payload *does* prove is narrower and, for the gate, more
interesting: the same mixed bundle reached the vision path anyway, by the
keyword route. Only the escalation gate refuses it.

Nothing here calls a model or a network. It reads committed JSON.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from core.media_types import GRADER_VISUAL_RENDER_EXTENSIONS

REPO_ROOT = Path(__file__).resolve().parents[2]
GRADES = REPO_ROOT / "data/grades"

GOLD_PDF_AND_PY = "46fc494e"
DOCX_PDF_AND_TXT = "58ac1cc5"
XLSX_AND_TXT = "bf68f2ad"

#: task prefix -> (renderable suffixes, non-renderable suffixes, payloads, items)
EXPECTED_CORPUS = {
    GOLD_PDF_AND_PY: ({".pdf"}, {".py"}, 4, 280),
    DOCX_PDF_AND_TXT: ({".docx", ".pdf"}, {".txt"}, 6, 234),
    XLSX_AND_TXT: ({".xlsx"}, {".txt"}, 6, 208),
}

#: The run whose payloads arrived after ``323`` took its measurement. Kept as a
#: path fragment because that is the only place a grade file records which run
#: produced it; the merged grade and its nine shards all carry it.
EXP035_RUN = "exp035_codex_foundry_full220"

#: exp035's extent, pinned so it cannot grow quietly either. ``bf68f2ad`` is
#: the one task present in both eras, which is why the task totals here and in
#: ``EXPECTED_CORPUS`` add to 50 rather than 51.
EXP035_TASKS = 48
EXP035_PAYLOADS = 10
EXP035_ITEMS = 3324

#: Where exp035's mechanism evidence runs out. 84 of its items carry an
#: extraction marker, spread over 28 tasks; the 20 below carry none at all, so
#: for them the payload cannot distinguish clause (a) from clause (c).
EXP035_ITEMS_WITH_EXTRACTION = 84
EXP035_TASKS_WITHOUT_EXTRACTION = {
    "1b9ec237", "1e5a1d7f", "401a07f1", "4de6a529", "575f8679",
    "6974adea", "69a8ef86", "6dcae3f5", "83d10b06", "87da214f",
    "a0ef404e", "a74ead3b", "a99d85fc", "d025a41c", "d7cfae6f",
    "dfb4e0cd", "ed2bc14c", "f9f82549", "fd6129bd", "ffed32d8",
}

#: What ``read_deliverable`` stamps on text it pulled out of a binary format.
EXTRACTION_MARKER = re.compile(r'"kind"\s*:\s*"(xlsx|docx|pptx|pdf)"')
PDF_PAGE_MARKER = "[Page "


def _from_exp035(path: Path) -> bool:
    return EXP035_RUN in str(path)


def _has_extraction_evidence(item: dict) -> bool:
    text = item.get("evidence") or ""
    return bool(EXTRACTION_MARKER.search(text)) or PDF_PAGE_MARKER in text


def _mixed_bundle_items() -> list[tuple[Path, str, dict]]:
    """Every published item that put a mixed bundle in front of a text judge.

    Walks the committed payloads rather than a hard-coded list so that a new
    grade landing in ``data/grades`` is picked up, not silently skipped. The
    era split happens in the fixtures below, on the returned paths -- this walk
    stays corpus-wide so that nothing is filtered out before it is counted.
    """
    found: list[tuple[Path, str, dict]] = []
    for path in sorted(GRADES.rglob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        for task in payload.get("tasks") or []:
            items = task.get("items")
            if not isinstance(items, list):
                continue  # run-summary stubs carry no items
            for item in items:
                if (item.get("routing_modality") or "").lower() not in (
                    "text",
                    "formatting",
                ):
                    continue
                suffixes = {
                    Path(p).suffix.lower() for p in (item.get("selected_paths") or [])
                }
                renderable = suffixes & GRADER_VISUAL_RENDER_EXTENSIONS
                if renderable and not suffixes.issubset(GRADER_VISUAL_RENDER_EXTENSIONS):
                    found.append((path, task.get("task_id") or "", item))
    return found


@pytest.fixture(scope="module")
def mixed_bundles() -> list[tuple[Path, str, dict]]:
    found = _mixed_bundle_items()
    assert found, (
        "no published item selects a mixed renderable/non-renderable bundle. "
        "Either data/grades was pruned or selection changed; 323's measured "
        "zero rests on this corpus existing."
    )
    return found


@pytest.fixture(scope="module")
def historical_bundles(mixed_bundles) -> list[tuple[Path, str, dict]]:
    """The corpus ``323`` actually measured, with exp035 held out.

    Not a narrowing of what is checked: the held-out half is checked by
    ``test_exp035_multiplied_the_corpus_by_five_and_none_of_it_escalated``,
    and the outcome assertion below runs over both halves together.
    """
    return [row for row in mixed_bundles if not _from_exp035(row[0])]


@pytest.fixture(scope="module")
def exp035_bundles(mixed_bundles) -> list[tuple[Path, str, dict]]:
    return [row for row in mixed_bundles if _from_exp035(row[0])]


def test_the_three_tasks_323_measured_are_unchanged(historical_bundles):
    """The canary, still strict, now scoped to the corpus it was measured over.

    ``323``'s finding is a measurement, so the corpus changing invalidates it.
    A grade tripping this is not a bug in the grade -- it is a request to
    re-measure. exp035 *was* that request, and it is answered by pinning its
    extent separately rather than by widening these numbers to swallow it,
    because the two eras support the finding to different depths.
    """
    by_task: dict[str, set[Path]] = {}
    counts: dict[str, int] = {}
    for path, task_id, _item in historical_bundles:
        prefix = task_id[:8]
        by_task.setdefault(prefix, set()).add(path)
        counts[prefix] = counts.get(prefix, 0) + 1

    assert set(by_task) == set(EXPECTED_CORPUS), (
        f"mixed-bundle tasks are now {sorted(by_task)}, expected "
        f"{sorted(EXPECTED_CORPUS)}. Re-run the escalation scan in 323 §3 "
        f"before trusting its 'blocked: 0' figure."
    )
    for prefix, (_r, _n, payloads, items) in EXPECTED_CORPUS.items():
        assert (len(by_task[prefix]), counts[prefix]) == (payloads, items), (
            f"{prefix} now appears as {counts[prefix]} items across "
            f"{len(by_task[prefix])} payloads, not {items} across {payloads}"
        )
    assert len({p for p, _t, _i in historical_bundles}) == 12
    assert len(historical_bundles) == 722


def test_exp035_multiplied_the_corpus_by_five_and_none_of_it_escalated(
    mixed_bundles, exp035_bundles
):
    """The outcome, read off the payload rather than inferred from a clause.

    ``perception_called`` is the item's own record of whether the judge was
    handed a rendered image. It is ``False`` on every mixed bundle ever
    published -- all 4,046 of them, both eras -- so the hole has still cost
    nothing, and that holds for the 20 tasks whose mechanism is undetermined
    just as much as for the ones that carry extraction evidence.

    This is the assertion that makes holding exp035 out of the numbers above
    safe. It runs over the whole corpus, not either half.
    """
    by_task = {task_id[:8] for _p, task_id, _i in exp035_bundles}
    payloads = {path for path, _t, _i in exp035_bundles}
    assert (len(by_task), len(payloads), len(exp035_bundles)) == (
        EXP035_TASKS,
        EXP035_PAYLOADS,
        EXP035_ITEMS,
    ), (
        f"exp035 now contributes {len(exp035_bundles)} items across "
        f"{len(payloads)} payloads and {len(by_task)} tasks, not "
        f"{EXP035_ITEMS}/{EXP035_PAYLOADS}/{EXP035_TASKS}"
    )
    assert len(mixed_bundles) == 722 + EXP035_ITEMS

    escalated = [
        (path, task_id)
        for path, task_id, item in mixed_bundles
        if item.get("perception_called") is not False
    ]
    assert not escalated, (
        f"{len(escalated)} mixed bundles escalated to the vision path, e.g. "
        f"{escalated[:3]}. 322 pinned this hole on the grounds that it costs "
        f"nothing; that is no longer true and the gate needs re-deciding."
    )


def test_the_twenty_undetermined_tasks_are_named_rather_than_counted(exp035_bundles):
    """Where the mechanism evidence stops, listed so it cannot drift silently.

    84 of exp035's 3,324 items carry an extraction marker. The 28 tasks holding
    them inherit ``323``'s clause-(a) reading; the 20 that carry none do not,
    and no claim is made about which clause refused their bundles. Naming them
    rather than reporting "20" means a task moving between the two groups shows
    up as a diff instead of a silently equal count.
    """
    with_evidence: dict[str, int] = {}
    seen: set[str] = set()
    for _path, task_id, item in exp035_bundles:
        prefix = task_id[:8]
        seen.add(prefix)
        with_evidence.setdefault(prefix, 0)
        if _has_extraction_evidence(item):
            with_evidence[prefix] += 1

    silent = {prefix for prefix, count in with_evidence.items() if count == 0}
    assert silent == EXP035_TASKS_WITHOUT_EXTRACTION, (
        f"the undetermined set moved: now {sorted(silent)}. A task gaining "
        f"evidence is good news and a task losing it is not, but either way "
        f"323's clause-(a) reading covers a different set than it says."
    )
    assert sum(with_evidence.values()) == EXP035_ITEMS_WITH_EXTRACTION
    assert len(seen) - len(silent) == 28


def test_each_bundle_has_the_shape_that_makes_the_gate_refuse_it(historical_bundles):
    """Renderable and non-renderable in one selection -- clause (c)'s trigger."""
    shapes: dict[str, set[str]] = {}
    for _path, task_id, item in historical_bundles:
        suffixes = {Path(p).suffix.lower() for p in item["selected_paths"]}
        shapes.setdefault(task_id[:8], set()).update(suffixes)

    for prefix, (renderable, non_renderable, _p, _i) in EXPECTED_CORPUS.items():
        assert shapes[prefix] == renderable | non_renderable
        assert renderable <= GRADER_VISUAL_RENDER_EXTENSIONS
        assert not (non_renderable & GRADER_VISUAL_RENDER_EXTENSIONS)


def test_the_renderable_member_yielded_text_so_clause_a_shut_the_gate(
    historical_bundles,
):
    """The causal claim: the gate never reached clause (c) on these bundles.

    ``read_deliverable`` stamps the source format on text it extracted from a
    binary file, so a ``"kind": "xlsx"`` in a judge's evidence is that judge
    holding text pulled out of the ``.xlsx``. With text in hand,
    ``selected_paths_have_text`` is True and escalation is denied at clause (a)
    -- the ``.txt`` sibling never gets a say.
    """
    for prefix in (XLSX_AND_TXT, DOCX_PDF_AND_TXT):
        extracted = [
            item
            for _p, task_id, item in historical_bundles
            if task_id.startswith(prefix) and _has_extraction_evidence(item)
        ]
        assert extracted, (
            f"{prefix}: no recorded evidence shows text extracted from a "
            f"renderable member, so the claim that clause (a) shut the gate is "
            f"no longer supported by the payload"
        )


def test_the_keyword_route_renders_the_bundle_the_escalation_gate_refuses():
    """The asymmetry, and the reason the fix is not "loosen clause (c)".

    ``46fc494e`` ships ``.pdf`` + ``.py``. Its keyword-routed visual criteria
    rendered the ``.pdf`` and ignored the ``.py`` without complaint. So the
    bundle is renderable in practice; what refuses it is clause (c)'s demand
    that *every* suffix be renderable, which the keyword route never makes.
    """
    provenance: list[dict] = []
    for path in sorted(GRADES.rglob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        for task in payload.get("tasks") or []:
            if not (task.get("task_id") or "").startswith(GOLD_PDF_AND_PY):
                continue
            items = task.get("items")
            if not isinstance(items, list):
                continue
            selected = {
                Path(p).suffix.lower()
                for item in items
                for p in (item.get("selected_paths") or [])
            }
            if selected != {".pdf", ".py"}:
                continue  # other runs of this task shipped other files
            for item in items:
                provenance.extend(item.get("visual_provenance") or [])

    assert provenance, (
        "the .pdf/.py run of 46fc494e no longer records any render; the "
        "asymmetry between the keyword route and the escalation gate cannot "
        "be shown from the payload any more"
    )
    rendered = {entry["path"] for entry in provenance}
    assert rendered == {"Material analysis Report.pdf"}, (
        f"rendered {sorted(rendered)}; the point is that the .py sibling is "
        f"skipped rather than blocking the render"
    )
    assert all(
        entry["renderer_metadata"]["source_kind"] == "pdf" for entry in provenance
    )
