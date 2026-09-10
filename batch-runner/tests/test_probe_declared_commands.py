"""Sweeping one image against what the manifest declares — and not overclaiming it.

The module under test exists because of a gap that was found rather than
assumed. ``sandbox/agentic_v2_capabilities.json`` declares twenty commands with
a ``probe`` argv apiece and no versions; the *measurement* of those probes is a
capability receipt; and the receipt that reads ``verified`` in
``sandbox/v2/README.md`` was taken on a candidate image (``sha256:e47537b8…``)
that was never pushed. The image this repository can fetch is the parent that
candidate was built from. So the evidence and the reachable image are two
different things, and a sweep is what closes the distance for one of them.

Two properties are load-bearing here and both are tested directly:

**A probe with no record is not an absent command.** The driver runs inside the
container; if it dies partway — killed container, no shell — the probes after
that point have no answer. Reporting those as absent would turn a broken sweep
into twenty findings about the image.

**The artifact must not validate as a capability receipt.** It is narrower: no
SBOM, no license classification, no package inventory, no smoke matrix. A test
asserts the validator rejects it, so that a later edit which quietly widened the
shape could not make this artifact answer to a name it has not earned.

Nothing here starts a container. The runner is injected, exactly as the boot is
in the stage D tests, because what needs proving is the framing and the reading
of it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.agentic_v2_substrate import (
    AgenticV2SubstrateManifest,
    validate_capability_receipt,
)
from sandbox.v2.probe_declared_commands import (
    MARK,
    SweepRefused,
    _is_pinned,
    _parse,
    _shell_driver,
    sweep,
)

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]


A_REGISTRY_PIN = (
    "ghcr.io/hyeonsangjeon/gdpval-sandbox@sha256:"
    "ee6ef798631d3c3aeaed28658c640e6f5d021677449852bf2e1f18be5bd24edb"
)
A_LOCAL_IMAGE_ID = "sha256:" + "9" * 64

MANIFEST = BATCH_RUNNER_ROOT / "sandbox" / "agentic_v2_capabilities.json"


class ARunnerThatWasNeverAskedToStartAnything:
    """Stands in for ``docker run`` and records whether it was called."""

    def __init__(self, *, stdout: str = "", returncode: int = 0, stderr: str = ""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr
        self.calls: list[list[str]] = []

    def __call__(self, argv, timeout_seconds):
        self.calls.append(list(argv))
        return self

    # subprocess.CompletedProcess is duck-typed here; these are the three fields
    # the module reads and nothing else.


def _transcript(answers) -> str:
    """Build what the in-container driver would have printed."""
    blocks = []
    for name, status, out, err in answers:
        blocks.append(
            f"{MARK}BEGIN {name}\n"
            f"{MARK}RC {status}\n"
            f"{MARK}OUT\n{out}\n"
            f"{MARK}ERR\n{err}\n"
            f"{MARK}END"
        )
    return "\n".join(blocks) + "\n"


class TestPinningTheThingBeingMeasured:
    def test_a_registry_digest_is_a_pin(self):
        assert _is_pinned(A_REGISTRY_PIN) is True

    def test_a_local_image_id_is_a_pin(self):
        # The case that matters: the candidate carrying the professional-work
        # layer was built and never pushed, so an image ID is the only content
        # address it has.
        assert _is_pinned(A_LOCAL_IMAGE_ID) is True

    @pytest.mark.parametrize(
        "reference",
        [
            "ghcr.io/hyeonsangjeon/gdpval-sandbox:latest",
            "gdpval-agentic-v2-candidate:dev",
            "sha256:abc",
            "",
        ],
    )
    def test_a_tag_or_a_fragment_is_not_a_pin(self, reference):
        assert _is_pinned(reference) is False

    def test_an_unpinned_sweep_starts_nothing(self):
        # Refusing after starting a 7 GB image would be refusing at the most
        # expensive moment available.
        runner = ARunnerThatWasNeverAskedToStartAnything()
        with pytest.raises(SweepRefused) as refused:
            sweep(image="gdpval-agentic-v2-candidate:dev", run=runner)
        assert "not pinned" in str(refused.value)
        assert runner.calls == []


class TestTheDriverTheContainerRuns:
    def test_every_declared_probe_appears_in_it(self):
        driver = _shell_driver(
            [
                {"name": "Rscript", "probe": ["Rscript", "--version"]},
                {"name": "node", "probe": ["node", "--version"]},
            ]
        )
        assert f"{MARK}BEGIN Rscript" in driver
        assert f"{MARK}BEGIN node" in driver
        assert driver.count(f"{MARK}END") == 2

    def test_an_argument_holding_a_space_stays_one_argument(self):
        driver = _shell_driver(
            [{"name": "font", "probe": ["fc-match", "Noto Sans CJK KR"]}]
        )
        assert "'Noto Sans CJK KR'" in driver

    def test_an_argument_holding_a_quote_cannot_break_out_of_the_driver(self):
        # The argv come from a file in this repository, which is a reason to
        # expect them to be ordinary rather than a licence to concatenate.
        driver = _shell_driver(
            [{"name": "odd", "probe": ["sh", "-c", "echo 'x'; rm -rf /"]}]
        )
        assert "\nrm -rf /" not in driver

    def test_each_probe_gets_its_own_exit_status(self):
        driver = _shell_driver([{"name": "a", "probe": ["true"]}])
        assert "status=$?" in driver
        assert f"{MARK}RC " in driver


class TestReadingTheAnswersBack:
    def test_a_probe_that_exited_zero_is_present(self):
        records = _parse(
            _transcript([("bash", 0, "GNU bash, version 5.2.15", "")]),
            [{"name": "bash", "probe": ["bash", "--version"]}],
        )
        assert records[0]["present"] is True
        assert records[0]["returncode"] == 0
        assert records[0]["first_line"] == "GNU bash, version 5.2.15"

    def test_a_probe_that_failed_is_absent_and_says_why(self):
        records = _parse(
            _transcript([("Rscript", 127, "", "sh: Rscript: not found")]),
            [{"name": "Rscript", "probe": ["Rscript", "--version"]}],
        )
        assert records[0]["answered"] is True
        assert records[0]["present"] is False
        assert records[0]["returncode"] == 127
        assert "not found" in records[0]["first_line"]

    def test_a_probe_with_no_record_is_not_reported_as_an_absent_command(self):
        # The sweep died partway. Ten probes never ran, and calling them absent
        # would turn one broken container into ten findings about the image.
        records = _parse(
            _transcript([("bash", 0, "GNU bash", "")]),
            [
                {"name": "bash", "probe": ["bash", "--version"]},
                {"name": "node", "probe": ["node", "--version"]},
            ],
        )
        node = records[1]
        assert node["answered"] is False
        assert node["present"] is False
        assert node["returncode"] is None
        assert "not a statement about the command" in node["grounds"]

    def test_only_the_first_line_is_kept_from_a_talkative_probe(self):
        records = _parse(
            _transcript([("libreoffice", 0, "LibreOffice 7.4.7.2\nand more\n", "")]),
            [{"name": "libreoffice", "probe": ["libreoffice", "--version"]}],
        )
        assert records[0]["first_line"] == "LibreOffice 7.4.7.2"

    def test_the_order_asked_is_the_order_reported(self):
        asked = [{"name": n, "probe": [n]} for n in ("c", "a", "b")]
        records = _parse(
            _transcript([("a", 0, "", ""), ("b", 0, "", ""), ("c", 0, "", "")]), asked
        )
        assert [row["name"] for row in records] == ["c", "a", "b"]


class TestTheArtifactAndWhatItRefusesToBeCalled:
    def _swept(self, **kwargs):
        runner = ARunnerThatWasNeverAskedToStartAnything(**kwargs)
        return sweep(image=A_REGISTRY_PIN, manifest_path=MANIFEST, run=runner), runner

    def test_it_says_what_it_is_not(self):
        result, _ = self._swept()
        assert "a capability receipt" in result["is_not"]
        assert "a signature or provenance verification" in result["is_not"]

    def test_it_does_not_validate_as_a_capability_receipt(self):
        # The strongest anti-overclaim check available: the repository's own
        # validator is asked, and has to say no. If a later edit widened this
        # artifact's shape until it passed, this test is what would notice.
        result, _ = self._swept()
        manifest = AgenticV2SubstrateManifest.load(MANIFEST)
        with pytest.raises(ValueError):
            validate_capability_receipt(result, manifest)

    def test_it_names_the_host_it_was_taken_on(self):
        # A sweep on a 3.10 kernel and a sweep on the Azure host are two
        # measurements even when the image is the same bytes.
        result, _ = self._swept()
        assert result["host"]["machine"]
        assert result["host"]["kernel"]
        assert "cgroup_version" in result["host"]

    def test_it_names_the_declaration_it_was_checked_against(self):
        result, _ = self._swept()
        assert len(result["manifest_sha256"]) == 64
        assert result["declared"]["commands"] == 20
        assert result["declared"]["python_modules"] == 13

    def test_the_container_is_started_with_no_network_and_a_read_only_root(self):
        _, runner = self._swept()
        argv = runner.calls[0]
        assert "--network" in argv and argv[argv.index("--network") + 1] == "none"
        assert "--read-only" in argv
        assert A_REGISTRY_PIN in argv

    def test_the_driver_is_not_copied_into_the_record(self):
        # It is several kilobytes of generated shell and it is reproducible from
        # the manifest. What matters in the record is how the container was
        # started.
        result, _ = self._swept()
        assert result["runtime_argv"][-1] == "<driver>"
        assert not any(MARK in part for part in result["runtime_argv"])

    def test_python_and_python3_are_both_asked_of_every_image(self):
        # The manifest declares platform.python == "3.11" and never says which
        # name reaches it. A command built around the wrong one fails in a way
        # that reads as the model writing a broken command.
        result, _ = self._swept()
        names = [row["name"] for row in result["records"]]
        assert "python" in names and "python3" in names

    def test_absent_commands_are_counted_rather_than_dropped(self):
        transcript = _transcript(
            [("python3", 0, "Python 3.11.15", ""), ("Rscript", 127, "", "not found")]
        )
        result, _ = self._swept(stdout=transcript)
        assert result["probes_declared"] == len(result["records"])
        assert result["present"] >= 1
        assert result["absent"] >= 1
        by_name = {row["name"]: row for row in result["records"]}
        assert by_name["Rscript"]["present"] is False
        assert by_name["python3"]["first_line"] == "Python 3.11.15"


class TestTheMeasurementThatWasActuallyTaken:
    """A regression check on the finding, not on the code.

    These two numbers were measured on 2026-09-10 against the pinned parent and
    a locally built candidate. They are recorded because the *difference*
    between them is the whole professional-work layer, and because a later run
    that quietly produced different numbers should be noticed rather than
    absorbed.
    """

    ARTEFACT = BATCH_RUNNER_ROOT / "sandbox" / "v2" / "declared-command-sweep.json"

    @pytest.mark.skipif(
        not ARTEFACT.is_file(), reason="the recorded sweep has not been committed"
    )
    def test_the_parent_is_missing_exactly_the_professional_work_commands(self):
        recorded = json.loads(self.ARTEFACT.read_text(encoding="utf-8"))
        parent = recorded["parent"]
        absent = {row["name"] for row in parent["records"] if not row["present"]}
        assert absent == {
            "Rscript", "chromium", "cmake", "node", "npm", "python3:ezdxf"
        }

    @pytest.mark.skipif(
        not ARTEFACT.is_file(), reason="the recorded sweep has not been committed"
    )
    def test_the_candidate_answered_every_declared_probe(self):
        recorded = json.loads(self.ARTEFACT.read_text(encoding="utf-8"))
        candidate = recorded["candidate"]
        assert candidate["absent"] == 0
        assert candidate["present"] == candidate["probes_declared"]

    @pytest.mark.skipif(
        not ARTEFACT.is_file(), reason="the recorded sweep has not been committed"
    )
    def test_neither_sweep_is_recorded_as_evidence_it_is_not(self):
        recorded = json.loads(self.ARTEFACT.read_text(encoding="utf-8"))
        assert recorded["capability_receipt_status"] == "not_run"
        assert recorded["signature_status"] == "not_run"
        assert recorded["provenance_status"] == "not_run"
