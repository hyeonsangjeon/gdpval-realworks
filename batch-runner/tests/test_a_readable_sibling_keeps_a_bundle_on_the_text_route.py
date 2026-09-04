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

This file records what it is worth. Across all 99 committed grade payloads,
12 payloads carry a mixed renderable/non-renderable bundle under a TEXT or
FORMATTING criterion, and they belong to just three tasks:

    46fc494e   .pdf + .py            70 items x 4 payloads   (gold-185)
    58ac1cc5   .docx .pdf + .txt     39 items x 6 payloads   (220-task runs)
    bf68f2ad   .xlsx + .txt          34-35 items x 6 payloads

722 items in all. In every one of them the renderable member yields text, so
clause (a) closes the gate before clause (c) is ever consulted. Clause (c)
blocked **nothing**. The hole has no causal effect on any published grade in
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

#: What ``read_deliverable`` stamps on text it pulled out of a binary format.
EXTRACTION_MARKER = re.compile(r'"kind"\s*:\s*"(xlsx|docx|pptx|pdf)"')
PDF_PAGE_MARKER = "[Page "


def _mixed_bundle_items() -> list[tuple[Path, str, dict]]:
    """Every published item that put a mixed bundle in front of a text judge.

    Walks the committed payloads rather than a hard-coded list so that a new
    grade landing in ``data/grades`` is picked up, not silently skipped.
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


def test_only_three_tasks_ever_put_a_mixed_bundle_on_the_text_route(mixed_bundles):
    """The canary. A fourth task here means the zero in ``323`` is stale.

    This is deliberately strict: the whole finding is a measurement over a
    known corpus, so the corpus changing invalidates it. Adding a grade that
    trips this is not a bug in the grade -- it is a request to re-measure.
    """
    by_task: dict[str, set[Path]] = {}
    counts: dict[str, int] = {}
    for path, task_id, _item in mixed_bundles:
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
    assert len({p for p, _t, _i in mixed_bundles}) == 12
    assert len(mixed_bundles) == 722


def test_each_bundle_has_the_shape_that_makes_the_gate_refuse_it(mixed_bundles):
    """Renderable and non-renderable in one selection -- clause (c)'s trigger."""
    shapes: dict[str, set[str]] = {}
    for _path, task_id, item in mixed_bundles:
        suffixes = {Path(p).suffix.lower() for p in item["selected_paths"]}
        shapes.setdefault(task_id[:8], set()).update(suffixes)

    for prefix, (renderable, non_renderable, _p, _i) in EXPECTED_CORPUS.items():
        assert shapes[prefix] == renderable | non_renderable
        assert renderable <= GRADER_VISUAL_RENDER_EXTENSIONS
        assert not (non_renderable & GRADER_VISUAL_RENDER_EXTENSIONS)


def test_the_renderable_member_yielded_text_so_clause_a_shut_the_gate(mixed_bundles):
    """The causal claim: the gate never reached clause (c) on these bundles.

    ``read_deliverable`` stamps the source format on text it extracted from a
    binary file, so a ``"kind": "xlsx"`` in a judge's evidence is that judge
    holding text pulled out of the ``.xlsx``. With text in hand,
    ``selected_paths_have_text`` is True and escalation is denied at clause (a)
    -- the ``.txt`` sibling never gets a say.
    """
    for prefix in (XLSX_AND_TXT, DOCX_PDF_AND_TXT):
        evidence = [
            item.get("evidence") or ""
            for _p, task_id, item in mixed_bundles
            if task_id.startswith(prefix)
        ]
        extracted = [
            text
            for text in evidence
            if EXTRACTION_MARKER.search(text) or PDF_PAGE_MARKER in text
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
