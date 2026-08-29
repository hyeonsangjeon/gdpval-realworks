"""A source file, a config file and a notebook are things a judge can read.

Two modules had to agree before that was true, and neither did.

``read_deliverable._kind_of`` decided what a file is from its extension alone,
and its map names no source or config format. A ``.py``, a ``.yaml``, an
``.overpassql`` were all ``unknown``, which routes ``read_content`` to "this
file holds no text" -- a sentence that is false about every one of them.

``deliverable_selector.DOCUMENT_EXTENSIONS`` decides what counts as a
document-like candidate, and left the same formats out. ``_classify_task``
needs two document-like files before it will call a multi-file task
``uniform_primaries``; each of the three affected gold tasks has exactly one
once its source file is discounted, so all three fell through to ``ambiguous``
and the whole task was declined.

Measured on the 185 gold-bearing tasks of the pinned revision, before this
change:

* ``46fc494e`` (Mechanical Engineers) -- ``HeatConduction.py`` -- 0 of 81
  rubric items, 117 points
* ``854f3814`` (Software Developers) -- ``abq okc query.overpassql`` -- 0 of
  23 items, 33 points
* ``2c249e0f`` (Software Developers) -- ``robot_data_upload_api_v2.yaml`` --
  0 of 50 items, 74 points
* ``c7d83f01`` (Financial and Investment Analysts) --
  ``AmericanOptionPricing.ipynb`` -- no selection error at all, all 43 items
  judged, every read returning ``char_count=0``. The worst of the four,
  because nothing reported it.

Nothing here calls a model, marks anything, or spends anything.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.deliverable_selector import (  # noqa: E402
    DOCUMENT_EXTENSIONS,
    select_deliverables,
)
from core.tools import has_extractable_text  # noqa: E402
from core.tools.read_deliverable import (  # noqa: E402
    MAX_CONTENT_CHARS,
    TEXT_SNIFF_BYTES,
    _kind_of,
    _reads_as_text,
    read_deliverable,
)


@pytest.fixture()
def base_dir(tmp_path: Path) -> Path:
    root = tmp_path / "deliverables"
    root.mkdir()
    return root


# ── The file is opened, not guessed at from its name ──────────────────────

# Every one of these ships as a gold deliverable on the pinned revision except
# the last two, which the corpus names in prose. Sizes are the real ones.
SOURCE_FILES_THE_CORPUS_SHIPS = [
    pytest.param("HeatConduction.py", b"import numpy as np\n", id="py-46fc494e"),
    pytest.param(
        "abq okc query.overpassql",
        b'[out:json][timeout:180];\nway["ref"="US:I 40"];\n',
        id="overpassql-854f3814",
    ),
    pytest.param(
        "robot_data_upload_api_v2.yaml",
        b"openapi: 3.0.3\ninfo:\n  title: Robot Data Upload API\n",
        id="yaml-2c249e0f",
    ),
    pytest.param("config.yml", b"retries: 3\n", id="yml-named-beside-yaml"),
    pytest.param("manifest.json", b'{"ok": true}\n', id="json"),
]


@pytest.mark.parametrize("name,content", SOURCE_FILES_THE_CORPUS_SHIPS)
def test_a_source_or_config_file_is_read_as_text(
    base_dir: Path, name: str, content: bytes
) -> None:
    written = base_dir / name
    written.write_bytes(content)

    assert _kind_of(written) in ("txt", "notebook")
    result = read_deliverable(op="read_content", path=name, base_dir=str(base_dir))
    assert result["ok"], result
    assert result["data"]["text"].strip() == content.decode().strip()
    assert result["data"]["char_count"] > 0


def test_a_file_whose_bytes_are_not_text_stays_unknown(base_dir: Path) -> None:
    """The sniff answers no as readily as yes, or it is not an answer."""
    drawing = base_dir / "assembly.dwg"
    drawing.write_bytes(b"AC1032\x00\x00\x00\x00" + b"\xff" * 200)

    assert _kind_of(drawing) == "unknown"
    data = read_deliverable(
        op="read_content", path="assembly.dwg", base_dir=str(base_dir)
    )["data"]
    assert data["char_count"] == 0
    assert "holds no text" in data["note"]


def test_a_mapped_extension_is_never_reinterpreted_by_its_bytes(
    base_dir: Path,
) -> None:
    """The name wins where the map has an entry, and the map is not a guess.

    A workbook that happens to start with printable bytes is still a workbook,
    and letting content override the map could only invent ways to misread a
    format that was named correctly.
    """
    fake_workbook = base_dir / "figures.xlsx"
    fake_workbook.write_bytes(b"this is not really a workbook")
    fake_image = base_dir / "chart.png"
    fake_image.write_bytes(b"nor is this a png")

    assert _kind_of(fake_workbook) == "xlsx"
    assert _kind_of(fake_image) == "image"


def test_an_empty_file_of_an_unmapped_extension_is_an_empty_text_file(
    base_dir: Path,
) -> None:
    """No bytes means no byte that is not text.

    A zero-byte deliverable is a real defect, and it reads better as an empty
    file the judge is told is empty than as a file nothing here understands.
    """
    empty = base_dir / "pipeline.py"
    empty.write_bytes(b"")

    assert _kind_of(empty) == "txt"
    data = read_deliverable(
        op="read_content", path="pipeline.py", base_dir=str(base_dir)
    )["data"]
    assert data["char_count"] == 0
    assert data["has_text_layer"] is False
    assert "no extractable text" in data["note"]


def test_a_character_split_by_the_cap_is_not_evidence_of_binary(
    base_dir: Path,
) -> None:
    """Where the read stopped is a fact about the read, not about the file."""
    filler = b"a" * (TEXT_SNIFF_BYTES - 1)
    straddling = base_dir / "notes.overpassql"
    straddling.write_bytes(filler + "€".encode() + b"more text after")

    assert _reads_as_text(straddling) is True
    assert _kind_of(straddling) == "txt"


def test_a_broken_byte_inside_the_window_is_evidence_of_binary(
    base_dir: Path,
) -> None:
    """The tolerance is one character at the boundary, not a blanket pardon."""
    broken = base_dir / "notes.overpassql"
    broken.write_bytes(b"query text " + b"\xff\xfe" + b"a" * 4096)

    assert _reads_as_text(broken) is False
    assert _kind_of(broken) == "unknown"


def test_a_file_that_cannot_be_opened_is_not_called_text(base_dir: Path) -> None:
    """Unreadable is not binary, but nothing downstream can read it either."""
    assert _reads_as_text(base_dir / "was_never_written.py") is False


# ── A notebook is read as a notebook, not as its own JSON ──────────────────


def _notebook(cells: list[dict], **metadata: object) -> str:
    return json.dumps(
        {
            "cells": cells,
            "metadata": {"language_info": {"name": "python"}, **metadata},
            "nbformat": 4,
            "nbformat_minor": 5,
        }
    )


def test_a_notebook_is_flattened_to_its_cells(base_dir: Path) -> None:
    """The raw file is JSON, so the sniff alone would hand over the JSON.

    That reads badly in a measurable way. The corpus notebook,
    ``AmericanOptionPricing.ipynb``, is 2,285,938 characters of which 39,478 --
    1.7 per cent -- are source; the rest is base64 image payload. A raw read
    is cut at MAX_CONTENT_CHARS, so 91 per cent of the file never reaches the
    judge and most of what does is base64. Flattened, the whole notebook is
    48,933 characters and nothing is cut.
    """
    notebook = base_dir / "analysis.ipynb"
    notebook.write_text(
        _notebook(
            [
                {"cell_type": "markdown", "source": ["# Pricing\n"], "metadata": {}},
                {
                    "cell_type": "code",
                    "source": ["print(binomial(100))\n"],
                    "metadata": {},
                    "outputs": [
                        {
                            "output_type": "stream",
                            "name": "stdout",
                            "text": ["10.4501\n"],
                        }
                    ],
                },
            ]
        )
    )

    assert _kind_of(notebook) == "notebook"
    data = read_deliverable(
        op="read_content", path="analysis.ipynb", base_dir=str(base_dir)
    )["data"]
    assert data["kind"] == "notebook"
    assert "# Pricing" in data["text"]
    assert "print(binomial(100))" in data["text"]
    assert "10.4501" in data["text"]
    # The JSON scaffolding the judge would otherwise have paid its window for.
    assert "nbformat_minor" not in data["text"]
    assert has_extractable_text(notebook) is True


def test_a_figure_in_a_notebook_is_named_rather_than_dumped(
    base_dir: Path,
) -> None:
    """A rubric asks whether the notebook plots something.

    The answer is that a figure exists, which is the one thing base64 bytes
    could not tell a text read.
    """
    notebook = base_dir / "analysis.ipynb"
    payload = "iVBORw0KGgo" * 5_000
    notebook.write_text(
        _notebook(
            [
                {
                    "cell_type": "code",
                    "source": ["plt.plot(prices)\n"],
                    "metadata": {},
                    "outputs": [
                        {
                            "output_type": "display_data",
                            "data": {"image/png": payload},
                            "metadata": {},
                        }
                    ],
                }
            ]
        )
    )

    text = read_deliverable(
        op="read_content", path="analysis.ipynb", base_dir=str(base_dir)
    )["data"]["text"]
    assert "image/png output, not text" in text
    assert payload[:64] not in text


def test_a_notebook_that_does_not_parse_is_still_read_as_text(
    base_dir: Path,
) -> None:
    """A broken notebook is a text file, and saying so beats raising."""
    notebook = base_dir / "half_written.ipynb"
    notebook.write_text('{"cells": [{"cell_type": "code",')

    data = read_deliverable(
        op="read_content", path="half_written.ipynb", base_dir=str(base_dir)
    )["data"]
    assert data["char_count"] > 0
    assert '"cells"' in data["text"]


def test_notebook_structure_reports_what_a_notebook_has(base_dir: Path) -> None:
    notebook = base_dir / "analysis.ipynb"
    notebook.write_text(
        _notebook(
            [
                {"cell_type": "markdown", "source": ["# Title\n"], "metadata": {}},
                {
                    "cell_type": "code",
                    "source": ["x = 1\n"],
                    "metadata": {},
                    "outputs": [
                        {"output_type": "stream", "name": "stdout", "text": ["1\n"]}
                    ],
                },
            ]
        )
    )

    data = read_deliverable(
        op="inspect_structure", path="analysis.ipynb", base_dir=str(base_dir)
    )["data"]
    assert data["kind"] == "notebook"
    assert data["cell_count"] == 2
    assert data["cell_types"] == {"code": 1, "markdown": 1}
    assert data["output_count"] == 1
    assert data["language"] == "python"


def test_a_notebook_larger_than_the_window_still_says_it_was_truncated(
    base_dir: Path,
) -> None:
    notebook = base_dir / "huge.ipynb"
    cell = {"cell_type": "code", "source": ["x = 1  # padding\n" * 400], "metadata": {}}
    notebook.write_text(_notebook([dict(cell) for _ in range(60)]))

    data = read_deliverable(
        op="read_content", path="huge.ipynb", base_dir=str(base_dir)
    )["data"]
    assert data["truncated"] is True
    assert data["char_count"] == MAX_CONTENT_CHARS


# ── The other ops keep their footing on the new kinds ──────────────────────


def test_the_listening_and_watching_probes_name_the_kind_they_were_given(
    base_dir: Path,
) -> None:
    script = base_dir / "solver.py"
    script.write_bytes(b"print(1)\n")

    for op, note in (("probe_audio", "not an audio file"),
                     ("probe_video", "not a video file")):
        data = read_deliverable(op=op, path="solver.py", base_dir=str(base_dir))["data"]
        assert data["kind"] == "txt"
        assert data["note"] == note


def test_rendering_a_script_is_refused_by_name(base_dir: Path) -> None:
    """Refusal is fine here; a silent misread would not be."""
    script = base_dir / "solver.py"
    script.write_bytes(b"print(1)\n")

    result = read_deliverable(
        op="render_to_image", path="solver.py", base_dir=str(base_dir)
    )
    assert result["ok"] is False
    assert "txt" in result["error"]


# ── The selector can now choose one of these as the deliverable ────────────

# task id, the files it ships, and the file that used to be discounted.
GOLD_TASKS_THAT_WERE_DECLINED = [
    pytest.param(
        "46fc494e",
        [
            "HeatConduction.py",
            "Material analysis Report.pdf",
            "isotherms_20min.png",
            "profiles_by_time.png",
            "time_traces.png",
        ],
        "HeatConduction.py",
        "Provides a node temperature profile vs node index at t ≈ 0.5 minutes "
        "(time stamp within ±0.1 min of 0.5 min).",
        id="46fc494e-a-python-solver-and-a-report",
    ),
    pytest.param(
        "854f3814",
        ["abq okc query instructions.md", "abq okc query.overpassql"],
        "abq okc query.overpassql",
        "Includes the full OverpassQL query as a single, contiguous snippet, "
        "either in its own file or embedded within another file.",
        id="854f3814-a-query-and-its-instructions",
    ),
    pytest.param(
        "2c249e0f",
        ["data_flow_updated_v2.txt", "robot_data_upload_api_v2.yaml"],
        "robot_data_upload_api_v2.yaml",
        "A YAML file with extension .yaml or .yml exists in the deliverable "
        "root and serves as the OpenAPI specification",
        id="2c249e0f-a-spec-and-a-data-flow",
    ),
]


@pytest.mark.parametrize(
    "task,files,discounted,criterion", GOLD_TASKS_THAT_WERE_DECLINED
)
def test_the_expert_answer_is_no_longer_declined_as_ambiguous(
    task: str, files: list[str], discounted: str, criterion: str
) -> None:
    """A gold answer is what the task wanted. It cannot be unrecognisable."""
    selection = select_deliverables(
        task_id=task,
        deliverable_files=[f"deliverable_files/{task}/{name}" for name in files],
        instruction="Produce the deliverable described below.",
        rubric_items=[{"criterion": criterion, "score": 2}],
    )

    assert selection.selection_status == "ok", selection.selection_error
    chosen = {
        path.rsplit("/", 1)[-1]
        for target in selection.primary_targets
        for path in target.paths
    }
    assert discounted in chosen


def test_the_yml_spelling_is_here_because_a_rubric_names_it() -> None:
    """2c249e0f writes both spellings in one line, so the pair is one format."""
    assert {".yaml", ".yml"} <= DOCUMENT_EXTENSIONS


def test_junk_a_run_leaves_behind_is_still_not_a_deliverable() -> None:
    """Why this is a named list rather than "anything unrecognised".

    ``grader._list_files`` walks the whole deliverable tree and appends every
    file it finds, with no junk filter. A rule that promoted any unmapped
    extension would make a stray editor or interpreter artefact a candidate
    primary on a model run, which is a worse failure than the one being fixed
    -- it would be graded, and silently.
    """
    for junk in (".ds_store", ".log", ".pyc", ".swp", ".tmp", ".bak"):
        assert junk not in DOCUMENT_EXTENSIONS
