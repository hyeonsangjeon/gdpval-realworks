"""Four criteria about pictures, judged by a harness with no way to look.

The 185-task gold ceiling carries nine ``required_visual_render_target_
unavailable`` items. Five are on ``7de33b48`` and are about React source, and
the source-code demotion in ``grader_routing`` already routes those to text.
The other four are video, on ``e222075d`` and ``75401f7c``::

    Both graphic cards use white text on a solid black background ...
    The first non-logo content shot begins within 7.0 seconds of the start.
    The image is not stretched or squashed; aspect ratio is preserved ...
    The image fills the 1920x1080 frame without unintended letterboxing ...

Every one is answerable from frames. None was answered. ``_VISUAL_RENDER_
SCOPES`` had no video suffix, so ``validate_planned_visual_names`` returned no
planned names, and ``preflight_visual`` set ``judge_error`` and returned --
before the model was called even once. The judge was not wrong about these
items; it was never asked. ``probe_video`` was sitting in the tool table the
whole time, holding the stored width and height that two of the four turn on.

The asymmetry is the odd part: ``video_analyzer`` has sampled keyframes since
the solving side needed them, and ``av`` has been a pinned requirement
throughout. The grader could listen to a video's audio track and could not see
a single frame of it.

The loss repeats. Across every published payload ``.mp4`` appears in 624
selected paths on those two tasks, and 81 items are ``judge_error``. Each one
is also ``score_excluded``, which lifts the headline average rather than
lowering it -- so the corpus reports these as slightly *better* than if the
frames had been looked at and the criteria genuinely failed.

What the fix may not do is answer confidently from too little. A single
first-frame render would answer "does the first content shot begin within 7
seconds" from one instant, and be believed. So the render is a contact sheet:
twelve evenly spaced stills, each captioned with its timestamp, tiled into one
image -- one render and one vision call, so the per-item and per-task visual
budgets count a video exactly like every other deliverable.

Three properties are load-bearing.

**A tile is where its caption says it is.** The strongest test here encodes a
reel whose colour changes every second and then reads the pixel out of each
tile. If seeking drifted, or the labels were assigned in the wrong order, the
colours would not line up. A sheet of twelve real frames with wrong timestamps
is worse than no sheet at all, because a temporal criterion would be answered
from it.

**Nothing is padded.** Two of the four criteria are about aspect ratio and
letterboxing. A montage that boxed frames into fixed cells would paint bars
into the evidence and the vision sub-judge would report them, so tiles are
scaled uniformly and the stored geometry travels in the metadata as the
authority.

**The coverage claim stays true.** Twelve of 3,600 frames is not
``sampled_first_surface``, and it is not one surface. Reporting it as either
would repeat the defect ``309`` and ``111`` were about: a number published in
a shape that cannot express what it actually measured.

Real videos, encoded with PyAV. Nothing here calls a model or a network.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

import pytest

av = pytest.importorskip("av")
np = pytest.importorskip("numpy")
PIL_Image = pytest.importorskip("PIL.Image")

from core.media_types import (  # noqa: E402
    GRADER_VIDEO_RENDER_EXTENSIONS,
    GRADER_VISUAL_RENDER_EXTENSIONS,
)
from core.perception.vision import contact_sheet_note  # noqa: E402
from core.tool_calling_judge import (  # noqa: E402
    _RENDERER_METADATA_KEYS,
    _TOTAL_SURFACE_KEYS,
    _VISUAL_RENDER_SCOPES,
    ToolCallingJudge,
)
from core.tools.read_deliverable import (  # noqa: E402
    _EXT_KIND,
    _video_sample_times,
    read_deliverable,
)

#: One solid colour per second of the reel, so a frame's colour states the
#: second it was taken from and a tile can be checked against its caption.
SECOND_COLOURS = [
    (220, 20, 20), (20, 200, 20), (20, 20, 220), (230, 230, 20),
    (200, 20, 200), (20, 220, 220), (240, 240, 240), (90, 90, 90),
    (250, 140, 0), (120, 0, 200),
]
FPS = 10


def _encode_reel(
    path: Path,
    *,
    seconds: int = 10,
    width: int = 320,
    height: int = 180,
    codec: str = "mpeg4",
) -> Path:
    """A reel whose colour changes once a second."""
    container = av.open(str(path), mode="w")
    try:
        stream = container.add_stream(codec, rate=FPS)
        stream.width, stream.height = width, height
        stream.pix_fmt = "yuv420p"
        for index in range(seconds * FPS):
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            frame[:, :] = SECOND_COLOURS[(index // FPS) % len(SECOND_COLOURS)]
            for packet in stream.encode(
                av.VideoFrame.from_ndarray(frame, format="rgb24")
            ):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    finally:
        container.close()
    return path


@pytest.fixture(scope="module")
def reel(tmp_path_factory) -> Path:
    return _encode_reel(tmp_path_factory.mktemp("video") / "deliverable.mp4")


def _render(path: Path) -> dict:
    envelope = read_deliverable(
        "render_to_image", path.name, base_dir=str(path.parent)
    )
    assert envelope["ok"], envelope
    return envelope["data"]


def _sheet(data: dict):
    return PIL_Image.open(io.BytesIO(base64.b64decode(data["base64"])))


# ── the item is reached at all ────────────────────────────────────────


def test_a_video_is_now_a_planned_visual_target():
    """The gate that failed all four items closed.

    ``planned_supported_visual_names`` returning empty is what
    ``preflight_visual`` turns into ``required_visual_render_target_
    unavailable``, so this is the exact assertion the four items failed.
    """
    planned, error = ToolCallingJudge.validate_planned_visual_names(
        ["reel.mp4"], 10
    )
    assert error is None
    assert planned == ["reel.mp4"]


def test_every_video_suffix_the_kind_map_knows_can_be_rendered():
    """The renderer dispatches on kind, so the two sets must agree.

    A suffix planned here but called something else by ``_EXT_KIND`` would
    reach ``_op_render_to_image`` and raise ``UnsupportedScope`` -- a
    guaranteed judge_error one layer further down than the one being fixed.
    """
    from_kind_map = {
        suffix for suffix, kind in _EXT_KIND.items() if kind == "video"
    }
    assert from_kind_map == set(GRADER_VIDEO_RENDER_EXTENSIONS)
    assert GRADER_VIDEO_RENDER_EXTENSIONS <= GRADER_VISUAL_RENDER_EXTENSIONS
    assert set(_VISUAL_RENDER_SCOPES) == set(GRADER_VISUAL_RENDER_EXTENSIONS)
    for suffix in GRADER_VIDEO_RENDER_EXTENSIONS:
        assert set(_VISUAL_RENDER_SCOPES[suffix]) == {"frames"}


# ── a tile is where its caption says it is ────────────────────────────


def test_each_tile_holds_the_frame_its_timestamp_names(reel):
    """The load-bearing one: twelve real frames, each in the right place.

    The reel changes colour every second, so the colour at the centre of a
    tile states which second it came from. Reading it back catches a seek
    that drifts, a label attached to the wrong tile, and a grid laid out in
    a different order than the timestamps were recorded in -- none of which
    a "twelve images came out" assertion would notice.
    """
    data = _render(reel)
    sheet = _sheet(data)
    columns, rows = (int(part) for part in data["contact_sheet_grid"].split("x"))
    tile_width = sheet.width // columns
    cell_height = sheet.height // rows
    caption_height = cell_height - round(180 * tile_width / 320)

    timestamps = data["sampled_timestamps_s"]
    assert len(timestamps) == data["sampled_frame_count"] == 12

    for index, timestamp in enumerate(timestamps):
        x = (index % columns) * tile_width + tile_width // 2
        y = (index // columns) * cell_height + (cell_height - caption_height) // 2
        pixel = sheet.getpixel((x, y))[:3]
        expected = SECOND_COLOURS[min(int(timestamp), len(SECOND_COLOURS) - 1)]
        assert all(abs(a - b) < 40 for a, b in zip(pixel, expected)), (
            f"tile {index} captioned t={timestamp:.2f}s holds {pixel}, "
            f"but the reel is {expected} at that moment"
        )


def test_the_caption_drawn_on_a_tile_is_that_tile_s_timestamp(reel):
    """The model reads the pixels, not ``sampled_timestamps_s``.

    Checking tiles against the metadata list proves the sheet and the
    metadata agree, and stops exactly there: draw the captions in reverse
    and every other assertion in this file still passes, while the vision
    sub-judge is told the last frame is the first one. So each caption strip
    is re-rendered locally for all twelve candidate timestamps and the tile's
    own must be the closest match. Comparing best-of-twelve rather than
    demanding an exact patch keeps this robust to a font substitution or a
    moved offset -- every candidate shifts with it -- while a swapped,
    reversed or off-by-one label moves the winner.
    """
    from PIL import Image, ImageDraw

    from core.tools.read_deliverable import _video_label_font

    data = _render(reel)
    sheet = _sheet(data)
    columns, rows = (int(part) for part in data["contact_sheet_grid"].split("x"))
    tile_width = sheet.width // columns
    cell_height = sheet.height // rows
    tile_height = round(
        data["source_height"] * tile_width / data["source_width"]
    )
    strip_height = cell_height - tile_height
    font = _video_label_font(tile_width)
    timestamps = data["sampled_timestamps_s"]

    def _reference(timestamp: float):
        patch = Image.new("RGB", (tile_width, strip_height), (32, 32, 32))
        ImageDraw.Draw(patch).text(
            (4, 1), f"t={timestamp:.2f}s", fill=(255, 255, 255), font=font
        )
        return np.asarray(patch, dtype=np.int16)

    references = [_reference(timestamp) for timestamp in timestamps]

    for index, timestamp in enumerate(timestamps):
        x = (index % columns) * tile_width
        y = (index // columns) * cell_height + tile_height
        strip = np.asarray(
            sheet.crop((x, y, x + tile_width, y + strip_height)).convert("RGB"),
            dtype=np.int16,
        )
        distances = [int(np.abs(strip - ref).sum()) for ref in references]
        best = min(range(len(distances)), key=distances.__getitem__)
        assert best == index, (
            f"tile {index} should be captioned t={timestamp:.2f}s, but its "
            f"caption strip matches t={timestamps[best]:.2f}s more closely"
        )


def test_the_sheet_carries_distinct_moments_not_one_frame_twelve_times(reel):
    """A seek that silently fails would tile the same frame twelve times.

    That sheet would look plausible and would answer a temporal criterion
    with whatever the first frame happened to show.
    """
    data = _render(reel)
    sheet = _sheet(data)
    columns, rows = (int(part) for part in data["contact_sheet_grid"].split("x"))
    tile_width, cell_height = sheet.width // columns, sheet.height // rows
    seen = {
        sheet.getpixel((
            (i % columns) * tile_width + tile_width // 2,
            (i // columns) * cell_height + 20,
        ))[:3]
        for i in range(len(data["sampled_timestamps_s"]))
    }
    assert len(seen) >= 8, f"only {len(seen)} distinct tile colours: {seen}"


def test_the_timestamps_are_ordered_and_inside_the_clip(reel):
    data = _render(reel)
    timestamps = data["sampled_timestamps_s"]
    assert timestamps == sorted(timestamps)
    assert timestamps[0] == 0.0
    assert max(timestamps) < data["source_duration_s"]


def test_the_last_instant_is_not_sampled():
    """Seeking to exactly the duration lands past the last decodable frame.

    It costs a tile and returns nothing, so the sampler stops short of it.
    """
    times = _video_sample_times(10.0, 12)
    assert len(times) == 12
    assert times[0] == 0.0
    assert max(times) < 10.0


def test_a_still_clip_of_unknown_length_still_yields_one_sample():
    """Zero duration is not zero frames; it is a length nobody recorded."""
    assert _video_sample_times(0.0, 12) == [0.0]


# ── nothing is padded ─────────────────────────────────────────────────


def test_tiles_are_uniformly_scaled_so_no_bar_is_invented(reel):
    """Two of the four criteria are about letterboxing and aspect ratio.

    If the montage padded a 16:9 frame into a squarer cell, the vision
    sub-judge would report bars that are not in the deliverable, and the
    criterion would fail on an artefact of the grading harness.
    """
    data = _render(reel)
    sheet = _sheet(data)
    columns, rows = (int(part) for part in data["contact_sheet_grid"].split("x"))
    tile_width = sheet.width // columns
    cell_height = sheet.height // rows
    source_ratio = data["source_width"] / data["source_height"]
    # The cell is the tile plus a caption strip; the tile itself must keep
    # the source ratio to within a rounding pixel.
    caption_height = cell_height - round(tile_width / source_ratio)
    assert 0 < caption_height < cell_height / 3
    assert abs((tile_width / (cell_height - caption_height)) - source_ratio) < 0.02


def test_the_stored_geometry_travels_with_the_sheet(reel):
    """Aspect ratio is answered from the numbers, not from a scaled tile.

    The tiles are downscaled, so "is the image stretched" cannot be read off
    the sheet at all -- it is a property of the stored dimensions. Those only
    reach the judge if the evidence chain is allowed to carry them, and
    ``_RENDERER_METADATA_KEYS`` is the allow-list that decides.
    """
    data = _render(reel)
    assert (data["source_width"], data["source_height"]) == (320, 180)
    assert data["source_fps"] == float(FPS)
    for key in ("source_width", "source_height", "source_duration_s",
                "source_fps", "source_frame_count", "sampled_frame_count",
                "sampled_timestamps_s", "contact_sheet_grid"):
        assert key in _RENDERER_METADATA_KEYS, key
        assert key in data, key


# ── the coverage claim stays true ─────────────────────────────────────


def test_coverage_reports_the_frames_it_sampled_not_one_first_surface(reel):
    """Twelve of 100 frames, said in a shape that can express twelve.

    ``sampled_first_surface`` with a count of 1 is what every other render
    reports and it is wrong twice over here: the sheet is not one surface,
    and it is not the first one.
    """
    class _Item:
        criterion = "The first non-logo content shot begins within 7.0 seconds."

    data = _render(reel)
    coverage = ToolCallingJudge._coverage_metadata(_Item(), data)
    assert coverage["coverage_mode"] == "sampled_frame_grid"
    assert coverage["sampled_surface_count"] == 12
    assert coverage["total_surface_count"] == 100
    assert _TOTAL_SURFACE_KEYS["video"] == "source_frame_count"


def test_a_pdf_still_reports_the_first_surface(reel):
    """The new branch is video-only; every other kind is untouched."""
    class _Item:
        criterion = "The chart has a title."

    coverage = ToolCallingJudge._coverage_metadata(
        _Item(), {"source_kind": "pdf", "source_page_count": 9}
    )
    assert coverage["coverage_mode"] == "sampled_first_surface"
    assert coverage["sampled_surface_count"] == 1
    assert coverage["total_surface_count"] == 9


def test_the_provenance_a_judged_video_writes_passes_the_grade_schema(reel):
    """Every field of a real render, through the real schema, in one go.

    The schema's two derivation guards compare declared properties against
    ``_RENDERER_METADATA_KEYS`` and ``_EXT_KIND``, and between them they miss
    two of the four objects this render fills: ``scope`` gained ``frames``
    and ``coverage_mode`` gained a second value, and neither guard looks at
    either. Both were rejected by ``additionalProperties: false`` and a
    ``const`` with nothing in CI to say so -- a run that grades a video would
    have paid for the judging and then failed validation on the way to disk.

    So this builds provenance the way ``preflight_visual`` does, from an
    actual sheet rather than a remembered shape, and validates it.
    """
    import json

    from jsonschema import validate

    from tests.test_grade_schema import _minimal_payload, _valid_visual_provenance

    class _Item:
        criterion = "The image fills the 1920x1080 frame without letterboxing."

    data = _render(reel)
    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "schemas" / "grade.schema.json")
        .read_text()
    )
    provenance = {
        "path": reel.name,
        "source_sha256": "b" * 64,
        "scope": data["scope"],
        "renderer_metadata": {
            key: data[key] for key in _RENDERER_METADATA_KEYS if key in data
        },
        "coverage_metadata": ToolCallingJudge._coverage_metadata(_Item(), data),
        # Borrowed whole: the vision envelope is not what this render
        # changed, and re-deriving it here would only test my memory of it.
        "vision": _valid_visual_provenance()["vision"],
    }
    payload = _minimal_payload()
    payload["tasks"][0]["items"][0]["visual_provenance"] = [provenance]
    validate(instance=payload, schema=schema)

    # The two fields the derivation guards cannot see.
    assert provenance["scope"] == {"frames": 12}
    assert provenance["coverage_metadata"]["coverage_mode"] == "sampled_frame_grid"


def test_the_frame_count_is_read_before_the_container_closes(reel):
    """PyAV attributes are backed by the open container.

    Read after ``close()`` they return whatever is left at that address --
    which is how this first reported 14,704,472,685 frames for a
    twelve-second clip, and would have published a coverage ratio of twelve
    in fourteen billion.
    """
    data = _render(reel)
    assert data["source_frame_count"] == 100
    assert data["source_frame_count"] == pytest.approx(
        data["source_duration_s"] * data["source_fps"], rel=0.05
    )


def test_a_container_that_stores_no_frame_count_derives_one(tmp_path):
    """Matroska and WebM routinely report 0 frames.

    0 is not a count and would divide the coverage ratio by nothing, so it
    is derived from duration x rate instead.
    """
    reel = _encode_reel(tmp_path / "clip.mkv", seconds=4)
    with av.open(str(reel)) as container:
        assert container.streams.video[0].frames == 0, (
            "fixture no longer exercises the derivation branch"
        )
    data = _render(reel)
    assert data["source_frame_count"] == pytest.approx(4 * FPS, abs=2)


# ── the vision sub-judge is told what it is looking at ────────────────


def test_the_sub_judge_is_told_the_image_is_a_contact_sheet(reel):
    """Otherwise it is a busy page with a grid the model must guess at.

    The note also has to say the gaps were never seen, so "no sampled frame
    before 7s showed it" does not get reported as "it did not happen".
    """
    note = contact_sheet_note(_render(reel))
    assert "contact sheet" in note
    assert "12 stills" in note
    assert "4x3" in note
    assert "320x180" in note
    assert "timestamp" in note
    assert "between two sampled timestamps" in note


def test_a_page_render_gets_no_note(reel):
    assert contact_sheet_note({"source_kind": "pdf", "page": 1}) == ""
    assert contact_sheet_note({}) == ""


def test_an_incomplete_render_gets_no_note_rather_than_a_wrong_one():
    """A note naming a grid the sheet does not have is worse than silence."""
    assert contact_sheet_note(
        {"source_kind": "video", "sampled_frame_count": 12}
    ) == ""


# ── fail closed ───────────────────────────────────────────────────────


def test_a_file_with_no_video_stream_fails_rather_than_rendering_blank(
    tmp_path,
):
    """An audio-only container must not produce an empty sheet to judge.

    The suffix says video, so routing plans a render; the container has
    nothing to draw. A blank or black sheet here would be graded, and
    "the graphic cards use white text on black" would come back as a
    confident fail against a deliverable nobody looked at.
    """
    path = tmp_path / "audio_only.mp4"
    container = av.open(str(path), mode="w")
    try:
        stream = container.add_stream("aac", rate=44100)
        frame = av.AudioFrame.from_ndarray(
            np.zeros((1, 1024), dtype="int16"), format="s16", layout="mono"
        )
        frame.sample_rate = 44100
        for packet in stream.encode(frame):
            container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)
    finally:
        container.close()
    assert path.is_file() and path.stat().st_size > 0

    envelope = read_deliverable(
        "render_to_image", path.name, base_dir=str(tmp_path)
    )
    assert not envelope.get("ok")
    assert "video" in str(envelope.get("error", "")).lower()


def test_an_unknown_scope_key_is_refused(reel):
    envelope = read_deliverable(
        "render_to_image", reel.name, base_dir=str(reel.parent),
        scope={"page": 1},
    )
    assert not envelope.get("ok")
    assert "page" in str(envelope.get("error", ""))


def test_a_zero_frame_request_is_refused(reel):
    envelope = read_deliverable(
        "render_to_image", reel.name, base_dir=str(reel.parent),
        scope={"frames": 0},
    )
    assert not envelope.get("ok")


def test_the_sheet_stays_under_the_shared_byte_cap(reel):
    from core.tools.read_deliverable import MAX_IMAGE_BYTES

    data = _render(reel)
    assert data["byte_size"] <= MAX_IMAGE_BYTES
    assert len(base64.b64decode(data["base64"])) == data["byte_size"]


def test_one_video_costs_one_render_and_one_vision_call(reel):
    """The budget counts calls, not frames.

    A sheet spending a call per frame would price one deliverable like
    twelve, and ``file_cap_per_item`` would fail whole items closed on a
    single video.
    """
    planned, error = ToolCallingJudge.validate_planned_visual_names(
        [reel.name], 1
    )
    assert error is None
    assert len(planned) == 1
