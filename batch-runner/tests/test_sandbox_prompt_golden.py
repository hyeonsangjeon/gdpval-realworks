"""Golden byte-identical snapshots of the sandbox prompt assembly.

P0 of the prompt-consolidation refactor (design under tasks/0707_tuesday/). This
test is the *arbiter of zero default drift*: it freezes the exact text produced by

    SandboxRunner._augment_prompt(...)   — section assembly (order/labels/joining)
    SandboxRunner._build_reflection(...) — self-QA repair wording (loop 2)

so that the later phases (P1 externalize reflection strings, P2 spec-driven
section ordering) can refactor the *internals* while proving the emitted prompt is
unchanged. If a later phase legitimately changes the wording, regenerate the
snapshots deliberately:

    REGEN_PROMPT_GOLDEN=1 python -m pytest tests/test_sandbox_prompt_golden.py

Design constraints honored here:
* Model-free & Docker-free — we only call the pure assembly helpers, never the LLM
  or a container (mirrors tests/test_sandbox_runner.py: use_docker="never").
* Deterministic & hermetic — inputs are *canned* (fixed Skill/contract/manifest
  objects and fixed-byte reference files created in a tmp dir), so snapshots are
  stable across machines. Reference file paths are temp dirs but only basenames +
  fixed sizes ever reach the prompt.
* Privacy — asserts none of the real host-root redaction targets leak into the
  assembled text.
"""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.sandbox_runner import SandboxRunner, _REDACT_ROOTS
from core.skills_registry import Skill
from core.deliverable_contract import DeliverableContract
from core.dependency_resolver import DependencyManifest
from core.prompt_loader import render_prompt


GOLDEN_DIR = Path(__file__).parent / "fixtures" / "prompt" / "golden"
REGEN = os.environ.get("REGEN_PROMPT_GOLDEN") == "1"


# ── canned fixture builders ───────────────────────────────────────────────

def _skill(name, title, description, api, exts, kws):
    """A fully-populated Skill as it looks *after* selection (score/matches set)."""
    s = Skill(
        name=name,
        title=title,
        description=description,
        modalities=[name],
        file_extensions=exts,
        keywords=kws,
        requires=[],
        version="1",
        body="",
        api=api,
        path=Path("."),
    )
    s.matched_extensions = list(exts)
    s.matched_keywords = list(kws)
    return s


_SKILLS = {
    "audio": _skill(
        "audio", "Audio Perception", "Listen via FFT/sampling and edit waveforms.",
        "  audio.fft_summary(path) -> dict; audio.loudness_lufs(path) -> float",
        [".wav"], ["mix", "stem"],
    ),
    "video": _skill(
        "video", "Video Perception", "See a clip frame-by-frame and composite.",
        "  video.keyframes(path, max_frames=8) -> list; video.montage(frames, out)",
        [".mp4"], ["composite", "shot"],
    ),
    "document": _skill(
        "document", "Document Toolkit", "Read and author documents.",
        "  document.make_docx(title, lines, out); document.read_any(path) -> str",
        [".docx"], ["report", "memo"],
    ),
    "data": _skill(
        "data", "Data Toolkit", "Load tables and build spreadsheets/charts.",
        "  data.read_table(path) -> df; data.quick_chart(df, out)",
        [".csv", ".xlsx"], ["spreadsheet", "model"],
    ),
}


def _manifest(required, missing=None):
    return DependencyManifest(required=list(required), missing_from_base=list(missing or []))


def _contract(exts, confidence, keywords=None):
    return DeliverableContract(
        expected_extensions=list(exts),
        confidence=confidence,
        required_keywords=list(keywords or []),
    )


# ``refs`` are (filename, fixed_bytes) — written to a tmp dir per test so only the
# basename + fixed size ever surface in the prompt (no host paths).
SCENARIOS = {
    "audio_capstone": dict(
        occupation="Audio Producer",
        task_prompt="Edit the supplied stems, produce a balanced mix, and write an edit report.",
        refs=[("State_of_Affairs_STEM.wav", b"RIFF" + b"\x00" * 508)],
        skills=["audio", "document"],
        manifest=_manifest(["librosa", "python-docx", "soundfile"], missing=["aspose-words"]),
        contract=_contract([".wav", ".docx"], "medium", ["mix"]),
        reflection=None,
    ),
    "video_capstone": dict(
        occupation="Film and Video Editor",
        task_prompt="Composite the actor between the two clips and make them vanish in a teleport effect.",
        refs=[("TWT_A001_03.mp4", b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 500)],
        skills=["video"],
        manifest=_manifest(["opencv-python", "numpy"]),
        contract=_contract([".mp4", ".png"], "medium", ["composite"]),
        reflection=None,
    ),
    "doc_only_no_refs": dict(
        occupation="Management Consultant",
        task_prompt="Write a two-page strategy memo summarizing the market entry options.",
        refs=[],
        skills=["document"],
        manifest=_manifest(["python-docx"]),
        contract=_contract([".docx"], "medium", ["memo"]),
        reflection=None,
    ),
    "accounting_spreadsheet": dict(
        occupation="Accountant",
        task_prompt="Build a quarterly financial model spreadsheet from the ledger and add a summary chart.",
        # CSV *input* (deterministic, stdlib preview) while the deliverable contract
        # expects .xlsx — this is the contract-extension-inference coverage case.
        refs=[("ledger.csv", b"date,account,amount\n2026-01-01,cash,100\n2026-01-02,ar,250\n")],
        skills=["data"],
        manifest=_manifest(["openpyxl", "pandas"]),
        contract=_contract([".xlsx"], "high", ["model"]),
        reflection=None,
    ),
}


def _build_inputs(scenario: dict, base_dir: Path):
    ref_paths = []
    for fname, payload in scenario["refs"]:
        p = base_dir / fname
        p.write_bytes(payload)
        ref_paths.append(str(p))
    skills = [_SKILLS[k] for k in scenario["skills"]]
    return (
        scenario["task_prompt"],
        ref_paths,
        skills,
        scenario["manifest"],
        scenario["contract"],
        scenario["reflection"],
        scenario["occupation"],
    )


@pytest.fixture(scope="module")
def runner():
    # No client calls happen in the assembly helpers; a bare namespace is enough.
    return SandboxRunner(llm_client=SimpleNamespace(), use_docker="never")


def _assert_golden(name: str, actual: str):
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    path = GOLDEN_DIR / name
    if REGEN:
        path.write_text(actual, encoding="utf-8")
        return
    assert path.exists(), (
        f"Missing golden {path.name}. Regenerate with "
        f"REGEN_PROMPT_GOLDEN=1 python -m pytest {Path(__file__).name}"
    )
    expected = path.read_text(encoding="utf-8")
    assert actual == expected, (
        f"Prompt assembly drifted for {name}. If this change is intentional, "
        f"regenerate goldens with REGEN_PROMPT_GOLDEN=1."
    )


def _assert_no_host_roots(text: str):
    for root in _REDACT_ROOTS:
        assert root not in text, f"host root leaked into prompt: {root!r}"


# ── tests ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", list(SCENARIOS))
def test_augment_prompt_golden(name, runner, tmp_path):
    task_prompt, refs, skills, manifest, contract, reflection, occ = _build_inputs(
        SCENARIOS[name], tmp_path
    )
    augmented = runner._augment_prompt(task_prompt, refs, skills, manifest, contract, reflection)
    _assert_no_host_roots(augmented)
    _assert_golden(f"{name}.augmented.txt", augmented)

    # Also lock the template wrapping (render_prompt with no experiment override,
    # which is the exp026 default) so P2 can't drift the final user message either.
    rendered = render_prompt(
        runner.prompt_data, occupation=occ, task_prompt=augmented, experiment_prompt=None
    )
    _assert_no_host_roots(rendered["user_prompt"])
    _assert_golden(f"{name}.rendered_user.txt", rendered["user_prompt"])


def test_augment_prompt_is_deterministic(runner, tmp_path):
    """Same inputs → byte-identical output across calls (no ordering nondeterminism)."""
    task_prompt, refs, skills, manifest, contract, reflection, _ = _build_inputs(
        SCENARIOS["audio_capstone"], tmp_path
    )
    a = runner._augment_prompt(task_prompt, refs, skills, manifest, contract, reflection)
    b = runner._augment_prompt(task_prompt, refs, skills, manifest, contract, reflection)
    assert a == b


def test_augment_prompt_prepends_reflection(runner, tmp_path):
    """When a reflection is supplied it must lead the assembled prompt (repair path)."""
    task_prompt, refs, skills, manifest, contract, _, _ = _build_inputs(
        SCENARIOS["audio_capstone"], tmp_path
    )
    reflection = "[REFLECTION]\nFix the missing .wav deliverable.\n[/REFLECTION]"
    augmented = runner._augment_prompt(task_prompt, refs, skills, manifest, contract, reflection)
    assert augmented.startswith(reflection)
    _assert_golden("audio_capstone.with_reflection.augmented.txt", augmented)


def test_build_reflection_golden(runner):
    """Loop-2 repair reflection wording, with real host-root redaction proven stable.

    The stderr tail embeds the real home dir and a container path; the sanitizer
    must turn the home dir into ``~`` (machine-stable) while leaving the container
    path intact.
    """
    contract = _contract([".xlsx"], "high", ["model"])
    blocking = [
        "missing_expected_type: no .xlsx deliverable was produced",
        "empty_output: execution wrote 0 files",
    ]
    warnings = ["render_qa: first page appears blank"]
    home = os.path.expanduser("~")
    result = {
        "text": "Loaded ledger.csv\nComputed totals\n(no file written)",
        "error": f"Traceback (most recent call last):\n  File \"{home}/run.py\", line 3\n"
                 f"  File \"/workspace/solution.py\", line 9\nValueError: bad column",
    }
    code = "import pandas as pd\ndf = pd.read_csv('ledger.csv')\nprint(df.sum())"
    reflection = runner._build_reflection(contract, blocking, code, result, {"warnings": warnings})

    # Home dir redacted to ~, container path preserved, no raw host roots.
    assert f"{home}/run.py" not in reflection
    assert "~/run.py" in reflection
    assert "/workspace/solution.py" in reflection
    _assert_no_host_roots(reflection)
    _assert_golden("repair_accounting.reflection.txt", reflection)


def test_reflection_wording_is_spec_driven(runner):
    """Editing reflection_strings in the spec must change the emitted wording.

    Proves the P1 externalization is live (not dead config): overriding the open/
    close markers on the loaded spec surfaces them in _build_reflection output.
    """
    r = SandboxRunner(llm_client=SimpleNamespace(), use_docker="never")
    r.prompt_data = dict(r.prompt_data)  # shallow copy — don't mutate shared spec
    r.prompt_data["reflection_strings"] = {
        **(r.prompt_data.get("reflection_strings") or {}),
        "open": "<<REPAIR-OPEN>>",
        "close": "<<REPAIR-CLOSE>>",
    }
    out = r._build_reflection(
        _contract([".xlsx"], "high"), ["missing .xlsx"], "", {"text": "", "error": ""}, {}
    )
    assert out.startswith("<<REPAIR-OPEN>>")
    assert out.rstrip().endswith("<<REPAIR-CLOSE>>")


def test_reflection_falls_back_when_spec_omits_strings():
    """A spec without reflection_strings must still yield the built-in wording."""
    r = SandboxRunner(llm_client=SimpleNamespace(), use_docker="never")
    r.prompt_data = {k: v for k, v in r.prompt_data.items() if k != "reflection_strings"}
    out = r._build_reflection(
        _contract([".xlsx"], "high"), ["missing .xlsx"], "", {"text": "", "error": ""}, {}
    )
    assert out.startswith("[REFLECTION]")
    assert out.rstrip().endswith("[/REFLECTION]")


_PERCEPTION_BLOCK = (
    "[AUDIO ANALYSIS]\n"
    "Tempo ~120 BPM; integrated loudness -14 LUFS; 3 stems detected.\n"
    "[/AUDIO ANALYSIS]"
)


def test_perception_passthrough_equals_prepend(runner, tmp_path):
    """Option A byte-identity: perception as a section == prepending it to the task.

    Proves step2's sandbox pass-through (perception_text) produces exactly the same
    assembled prompt as the legacy prepend-into-task behavior, so enabling the
    perception_analysis section causes zero drift on real perception runs.
    """
    task_prompt, refs, skills, manifest, contract, _, _ = _build_inputs(
        SCENARIOS["audio_capstone"], tmp_path
    )
    sandbox_reflection = "[REFLECTION]\nFix the missing mix.\n[/REFLECTION]"

    old = runner._augment_prompt(  # perception glued to front of task, section off
        _PERCEPTION_BLOCK + "\n\n" + task_prompt, refs, skills, manifest, contract,
        sandbox_reflection, perception_text=None,
    )
    new = runner._augment_prompt(  # perception passed as its own section
        task_prompt, refs, skills, manifest, contract,
        sandbox_reflection, perception_text=_PERCEPTION_BLOCK,
    )
    assert new == old
    assert (_PERCEPTION_BLOCK + "\n\n" + task_prompt) in new  # sits right before task


def test_perception_section_golden(runner, tmp_path):
    """Lock the assembled prompt when perception + a repair reflection are present."""
    task_prompt, refs, skills, manifest, contract, _, _ = _build_inputs(
        SCENARIOS["audio_capstone"], tmp_path
    )
    reflection = "[REFLECTION]\nPrevious attempt produced no .wav. Regenerate.\n[/REFLECTION]"
    augmented = runner._augment_prompt(
        task_prompt, refs, skills, manifest, contract, reflection,
        perception_text=_PERCEPTION_BLOCK,
    )
    _assert_no_host_roots(augmented)
    _assert_golden("audio_capstone.with_perception.augmented.txt", augmented)


def test_perception_omitted_when_absent(runner, tmp_path):
    """No perception_text → perception_analysis section is dropped (default output)."""
    task_prompt, refs, skills, manifest, contract, _, _ = _build_inputs(
        SCENARIOS["audio_capstone"], tmp_path
    )
    with_none = runner._augment_prompt(
        task_prompt, refs, skills, manifest, contract, None, perception_text=None
    )
    assert "[AUDIO ANALYSIS]" not in with_none
