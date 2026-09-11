"""The six absent commands, held to being the image rather than the environment.

D3's sweep found thirty-four declared commands present in a booted guest and six
absent. `scripts/explain_guest_command_absences.py` shows the six are exactly
what the professional-work candidate adds on top of the parent, which makes them
a setup error rather than a deficient sandbox.

That claim has a short shelf life if nobody holds it. Add a package to
`debian-extra.lock` and the correspondence stops being exact; rebuild the guest
from the candidate and the absences should disappear entirely. Either way the
committed artefact would keep asserting a tidy six-for-six that is no longer
true, and the next reader would plan a 220-task run around it.

So these tests re-derive the correspondence from the committed files on every
run, and fail when the story and the files diverge. They read files only --
nothing here boots, pulls, calls a model, or spends.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BATCH_RUNNER_ROOT.parent
SCRIPT = BATCH_RUNNER_ROOT / "scripts" / "explain_guest_command_absences.py"
ARTEFACT = REPOSITORY_ROOT / "tasks" / "0822_saturday" / (
    "guest_command_absences_explained.json"
)

SPEC = importlib.util.spec_from_file_location("explain_guest_command_absences", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
sys.modules["explain_guest_command_absences"] = module
SPEC.loader.exec_module(module)


@pytest.fixture(scope="module")
def report() -> dict:
    return module.explain()


@pytest.fixture(scope="module")
def script_source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def imported_modules(script_source) -> set:
    tree = ast.parse(script_source)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


class TestTheCorrespondenceIsExact:
    """Six for six, with nothing left over on either side."""

    def test_every_absence_is_accounted_for(self, report):
        correspondence = report["the_correspondence"]
        assert correspondence["accounts_for_every_absence"] is True, (
            "the six-for-six correspondence has broken. If a lock file gained a "
            "package, classify it in COMMAND_PROVIDED_BY or PROVIDES_NO_COMMAND. "
            "If the guest was rebuilt from the candidate, the absences should be "
            "gone and this whole explanation is obsolete rather than wrong."
        )

    def test_no_absence_is_left_unexplained(self, report):
        # The direction that would mean a real environment gap: a command
        # missing that the candidate does not add.
        assert report["the_correspondence"]["absent_and_not_explained"] == []

    def test_no_candidate_command_was_found_present(self, report):
        # The other direction, and the one that would quietly falsify the story:
        # if a candidate-added command were present, the guest was not purely
        # the parent and the tidy explanation would be a coincidence.
        assert report["the_correspondence"]["expected_absent_but_found_present"] == []

    def test_every_locked_package_is_classified(self, report):
        # An unclassified package is neither counted nor declared command-free,
        # so it would silently shrink the set the claim is checked against.
        assert report["what_the_candidate_adds_on_top"]["unclassified"] == []

    def test_the_six_are_the_six(self, report):
        assert report["the_correspondence"]["absent_in_the_guest"] == [
            "Rscript", "chromium", "cmake", "node", "npm", "python3:ezdxf"
        ]


class TestItIsHonestAboutWhichImageWasMeasured:
    def test_the_guest_was_the_parent(self, report):
        image = report["the_image_that_was_measured"]
        assert image["is_the_parent"] is True
        assert image["is_the_professional_work_candidate"] is False

    def test_the_sweep_and_the_boot_measured_the_same_image(self, report):
        # Layer by layer. If these ever differ, the sweep's absences say nothing
        # about the guest C2 booted, and the two artefacts cannot be read
        # together at all.
        assert report["the_image_that_was_measured"][
            "the_sweep_and_the_boot_are_the_same_image"
        ] is True

    def test_the_pinned_digest_is_the_one_parent_lock_names(self, report):
        parent = json.loads(
            (BATCH_RUNNER_ROOT / "sandbox" / "v2" / "parent.lock.json").read_text(
                encoding="utf-8"
            )
        )
        assert report["the_image_that_was_measured"]["pinned_digest"] == (
            parent["manifest_digest"]
        )

    def test_it_does_not_claim_the_candidate_is_reachable(self, report):
        # An earlier draft of this script said no digest for the candidate was
        # recorded anywhere. That was wrong three times over: sandbox/v2/README.md
        # records an image ID and an OCI manifest, and the container sweep ran a
        # third. What is true is narrower -- none of them can be pulled.
        where = report["where_the_candidate_actually_is"]
        assert where["is_pullable_from_here"] is False
        assert where["recorded_digests"]["image_id"] is not None
        assert where["recorded_digests"]["oci_manifest"] is not None
        assert where["the_digest_the_container_sweep_ran"].startswith("sha256:")
        disclaimed = " ".join(report["what_this_is_not"])
        assert "not a claim that the candidate is reachable" in disclaimed
        assert "never pushed" in disclaimed

    def test_the_recorded_digests_are_read_from_the_readme(self, report):
        readme = (
            BATCH_RUNNER_ROOT / "sandbox" / "v2" / "README.md"
        ).read_text(encoding="utf-8")
        for digest in report["where_the_candidate_actually_is"][
            "recorded_digests"
        ].values():
            assert digest in readme

    def test_it_does_not_claim_the_candidate_would_boot(self, report):
        # The A/B that shows the layer supplies the six was taken under docker.
        # Nothing has booted the candidate as a microVM guest.
        disclaimed = " ".join(report["what_this_is_not"])
        assert "not a claim that the candidate would boot as a microVM guest" in (
            disclaimed
        )


class TestTheLayerWasMeasuredAndNotJustInferred:
    """The stronger evidence: the same forty probes, run against both images."""

    def test_the_candidate_answered_every_probe(self, report):
        measured = report["the_layer_was_measured_not_inferred"]
        assert measured["candidate_present"] == 40
        assert measured["candidate_absent"] == 0
        assert measured["candidate_absent_commands"] == []

    def test_the_parent_missed_exactly_six(self, report):
        measured = report["the_layer_was_measured_not_inferred"]
        assert measured["parent_present"] == 34
        assert measured["parent_absent"] == 6

    def test_the_ab_was_taken_on_the_image_that_later_booted(self, report):
        # Without this the A/B would be about some other parent build and could
        # not be laid alongside the guest sweep at all.
        assert report["the_layer_was_measured_not_inferred"][
            "the_container_parent_is_the_booted_image"
        ] is True

    def test_docker_and_firecracker_name_the_same_six(self, report):
        measured = report["the_layer_was_measured_not_inferred"]
        assert measured["two_runtimes_name_the_same_six"] is True
        assert measured["parent_absent_commands"] == report["the_correspondence"][
            "absent_in_the_guest"
        ]

    def test_the_two_runtimes_really_were_different(self, report):
        # The claim is worth something only because the kernels differ; if both
        # sides were the same machine this would be one measurement counted twice.
        settles = report["the_layer_was_measured_not_inferred"]["what_that_settles"]
        assert "3.10.102" in settles
        assert "6.1.141" in settles


class TestTheVerdictIsNotOverstated:
    def test_it_does_not_promise_those_tasks_will_pass(self, report):
        # The six are explained, not fixed. A reader who takes "not an
        # environment defect" as "so those tasks are fine" would mis-plan the
        # 220-task run in the opposite direction.
        assert "those tasks will still fail" in report["therefore"]

    def test_it_refuses_the_model_failure_reading_too(self, report):
        assert "not a model failure" in report["therefore"]


class TestTheCommittedArtefactMatchesTheDerivation:
    def test_the_artefact_is_committed(self):
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(ARTEFACT.relative_to(
                REPOSITORY_ROOT
            ))],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
        )
        assert tracked.returncode == 0, (
            "the artefact is ignored by the blanket rule and needs a negation"
        )

    def test_it_has_not_drifted_from_what_the_files_say(self, report):
        # The artefact is a transcription of the derivation. If somebody edits
        # it by hand, or edits a lock and forgets to regenerate it, this is what
        # says so.
        assert json.loads(ARTEFACT.read_text(encoding="utf-8")) == report


class TestItOnlyReads:
    """Checked against the parsed module, not against its prose.

    An earlier version of this grepped the source for words like "docker". That
    broke the moment the docstring started naming the runtimes it compares --
    which is the sort of false alarm that gets a test deleted rather than fixed.
    The imports are the thing that decides what a script can reach.
    """

    ALLOWED = {"__future__", "json", "re", "sys", "pathlib"}

    def test_it_imports_nothing_that_can_reach_out(self, imported_modules):
        assert imported_modules <= self.ALLOWED, (
            f"unexpected imports: {sorted(imported_modules - self.ALLOWED)}"
        )

    def test_it_calls_nothing_that_writes(self, script_source):
        # It prints; the caller redirects. A script that wrote the artefact
        # itself could rewrite it to agree with itself, and the drift test
        # above would then be checking the derivation against a copy of itself.
        tree = ast.parse(script_source)
        called = {
            node.func.attr if isinstance(node.func, ast.Attribute)
            else getattr(node.func, "id", "")
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        }
        assert called.isdisjoint({"write_text", "write_bytes", "open", "mkdir",
                                  "unlink", "system", "run", "Popen"})

    def test_every_path_it_touches_is_inside_this_repository(self):
        # Checked on the loaded module rather than the source text, because a
        # leading slash in a string is not a path -- an f-string fragment like
        # "/40 present" tripped the textual version of this.
        paths = [
            value for value in vars(module).values() if isinstance(value, Path)
        ]
        assert paths, "the module declares no paths, so this checks nothing"
        for path in paths:
            assert REPOSITORY_ROOT in path.resolve().parents or (
                path.resolve() == REPOSITORY_ROOT
            ), f"path outside the repository: {path}"
