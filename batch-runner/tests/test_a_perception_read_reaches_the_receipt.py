"""What the grader looked at and what it listened to reach the receipt.

The receipt's atomic row is one model identity at one stage, and the marking
side spends three identities on a single task: the judge, the model that reads
the pictures, and the model that listens to the audio. ``core/grader.py`` keeps
them apart with three wrappers over one connection — the judge's client, a
second pinned to ``STAGE_PERCEPTION``, and a third pinned to the retry kind —
and hands the perception wrapper to both readers, which name their own
deployment on every request.

Every part of that is tested except the part that connects it. The ledger is
known to keep two models under one stage on two lines
(``test_a_run_summary_row_is_one_model_not_one_label``), and the grader is
known to build the two readers at all (``test_perception_wiring``), but nothing
drove a real ``Grader``'s readers into a real ledger, so nothing was checking
that the grader hands them a metered client in the first place. On ``main``
before this file, ``_perception_client`` had no test referring to it anywhere.

That gap is not theoretical, and the cost of it is not a wrong number — it is
no number. Measured, by mutating the wiring and running every test that
mentions perception or cost, 2647 of them:

``self._perception_client = client`` — drop the wrapper, keep everything else.
Both reads still happen, both still return verdicts, both are still real money,
and the receipt for the task reads ``status=not_run, model_calls=0,
known_cost_usd=0``. Spend reported as nothing at all. **2647 passed.**

``self._perception_client = self.client`` — reuse the judge's wrapper instead
of the perception one. Both reads are billed to ``stage='grading'``, so "what
did reading the deliverable cost" is inside the judge's line with no way to
separate it out. That is the merged-perception line this project has already
had once. **Also uncaught.**

So the two tests below drive the readers the grader really built, through the
ledger, and check the four things a reader of the receipt depends on: that the
spend arrived, that it arrived under ``perception`` and not under the judge,
that the two readers are two rows and not one, and that a price known for one
of them is not quietly spread over the other. No provider is contacted; the
connection is a double and every amount comes from the fixture table.
"""

from __future__ import annotations

import base64
import json
import struct
import wave
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from core.cost_metering import CostRecorder
from core.cost_receipts import (
    BUCKET_GRADING,
    STAGE_GRADING,
    STAGE_PERCEPTION,
    STATUS_COMPLETE,
    STATUS_PARTIAL,
    CostReceiptLedger,
    load_receipt_price_table,
)
from core.grader import Grader


#: The settings a real marking run loads. The deployments are read out of it
#: rather than written down here, so renaming one moves the test with it
#: instead of leaving the receipt unpriced underneath a green suite.
CONFIG_PATH = Path("grading_configs/default_v2.yaml")

#: Two rates, far enough apart that no amount below can be confused for the
#: other: the listening model is dearer per token *and* asked for fewer of
#: them, so a merged or swapped line shows up as the wrong number, not as a
#: number that happens to still add up.
VISION_RATE = {"input": "10", "output": "20"}    # 300k + 100k = $5.00
AUDIO_RATE = {"input": "40", "output": "80"}     # 100k +  50k = $8.00

VISION_USAGE = (300_000, 100_000)
AUDIO_USAGE = (100_000, 50_000)

VISION_USD = Decimal("5.00")
AUDIO_USD = Decimal("8.00")

#: A one-pixel PNG. The vision reader checks the payload is really base64
#: before it spends a call, so this has to decode.
PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
    "z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

VERDICT = json.dumps({
    "verdict": "pass",
    "partial_score": 1.0,
    "evidence": "the deliverable shows it",
    "confidence": 0.9,
    "reasoning": "read directly",
})


def _rate(rate: dict) -> dict:
    return {
        "input_usd_per_million": rate["input"],
        "cached_input_usd_per_million": rate["input"],
        "output_usd_per_million": rate["output"],
        "reasoning_billed_as": "output",
        "source": "fixture",
        "last_reviewed": "2026-09-02",
        "currency": "USD",
        "unit": "per 1,000,000 tokens",
    }


def price_table(**by_deployment: dict) -> dict:
    """A table naming only the deployments passed in.

    Leaving one out is how the "unpriced" half of the contract is set up: a
    model the table does not name has to come back ``price_missing`` on its
    own line, without touching the line beside it.
    """
    return {
        "cost_receipt_schema_version": "cost-receipt-price-table-v1",
        "providers": {
            f"azure:{name}": _rate(rate) for name, rate in by_deployment.items()
        },
        "runtime": {},
    }


class _Responses:
    """The surface the vision reader uses, in the shape it parses."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        inp, out = VISION_USAGE
        return SimpleNamespace(
            output=[SimpleNamespace(
                type="message",
                content=[SimpleNamespace(type="output_text", text=VERDICT)],
            )],
            output_text=VERDICT,
            usage=SimpleNamespace(
                input_tokens=inp,
                output_tokens=out,
                input_tokens_details=SimpleNamespace(cached_tokens=0),
            ),
        )


class _Completions:
    """The surface the audio reader uses.

    Spelled in the Chat Completions shape and not the Responses one, for the
    same reason ``test_a_failed_audio_call_does_not_cost_the_task_its_turn``
    spells it that way: a double that answers both shapes would let a return
    to the endpoint that cannot accept audio keep passing here.
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        inp, out = AUDIO_USAGE
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content=VERDICT, audio=None))],
            usage=SimpleNamespace(
                prompt_tokens=inp,
                completion_tokens=out,
                prompt_tokens_details=SimpleNamespace(cached_tokens=0),
            ),
        )


class _Client:
    """One connection offering both surfaces, the way the real one does."""

    def __init__(self) -> None:
        self.responses = _Responses()
        self.chat = SimpleNamespace(completions=_Completions())


@pytest.fixture
def document() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def deployments(document) -> tuple[str, str]:
    """``(vision, audio)`` as the committed settings name them."""
    perception = document["judge"]["perception"]
    vis = perception["visual"]
    aud = perception["audio"]
    return (
        vis.get("deployment") or vis["model"],
        aud.get("deployment") or aud["model"],
    )


@pytest.fixture
def wav_file(tmp_path) -> Path:
    """A second of tone, because the reader opens the file for real."""
    path = tmp_path / "clip.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(
            b"".join(struct.pack("<h", (i % 50) * 300) for i in range(8000))
        )
    return path


def _ledger(tmp_path, table: dict) -> CostReceiptLedger:
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps(table), encoding="utf-8")
    return CostReceiptLedger(
        tmp_path / "cost.sqlite3",
        run_id="run-1",
        price_table=load_receipt_price_table(prices),
    )


def _read_both(judge, wav_file: Path) -> None:
    """One look and one listen, the way a task with both would take them."""
    assert judge.vision_perception is not None, (
        "the committed settings built no vision reader"
    )
    assert judge.audio_perception is not None, (
        "the committed settings built no audio reader"
    )
    judge.vision_perception.judge(
        criterion="the chart carries a title", image_b64=PNG_B64
    )
    judge.audio_perception.judge(
        criterion="the narration is audible", audio_path=str(wav_file)
    )


def _by_model(receipt) -> dict:
    """``requested_model -> (stage, status, calls, amount, missing)``."""
    return {
        component.requested_model: (
            component.stage,
            component.status,
            component.model_calls,
            component.known_cost_usd,
            tuple(component.missing_reasons),
        )
        for component in receipt.components
    }


def test_a_look_and_a_listen_are_two_priced_lines_under_perception(
    tmp_path, document, deployments, wav_file
):
    """The spend arrives, under its own stage, once per model.

    Four separate claims, and each of them is one of the mutations in the
    module docstring: the calls are on the receipt at all, they are filed
    under ``perception`` rather than inside the judge's line, the two readers
    are two rows, and each row carries its own model's money.
    """
    vision_deployment, audio_deployment = deployments
    table = price_table(**{
        vision_deployment: VISION_RATE,
        audio_deployment: AUDIO_RATE,
    })
    client = _Client()

    with _ledger(tmp_path, table) as ledger:
        recorder = CostRecorder(ledger)
        grader = Grader(
            document, rubric_loader=None, client=client, cost_recorder=recorder
        )
        judge = grader._tool_judge
        assert judge is not None, "the committed settings built no judge"

        # The stage in scope is the judge's, which is the point: a perception
        # read taken mid-marking has to leave that scope on its own wrapper.
        with recorder.attributed(task_id="task-a", stage=STAGE_GRADING):
            _read_both(judge, wav_file)

        receipt = recorder.receipt_for("task-a", BUCKET_GRADING)

    # Both reads really went out, each naming its own deployment.
    assert [c.get("model") for c in client.responses.calls] == [vision_deployment]
    assert [c.get("model") for c in client.chat.completions.calls] == [
        audio_deployment
    ]

    # ...and both arrived. Dropping the metered wrapper leaves the two calls
    # above untouched and makes this receipt read not_run / 0 / $0.
    assert receipt.status == STATUS_COMPLETE
    assert receipt.model_calls == 2
    assert receipt.known_cost_usd == VISION_USD + AUDIO_USD

    assert _by_model(receipt) == {
        vision_deployment: (
            STAGE_PERCEPTION, STATUS_COMPLETE, 1, VISION_USD, ()
        ),
        audio_deployment: (
            STAGE_PERCEPTION, STATUS_COMPLETE, 1, AUDIO_USD, ()
        ),
    }


def test_an_unpriced_reader_does_not_take_the_other_one_down_with_it(
    tmp_path, document, deployments, wav_file
):
    """One model missing from the table leaves one line missing a price.

    The directive this file serves says the two readers' prices *and their
    reasons for having none* stay apart. So with only the vision model priced:
    the vision line keeps its real amount, the audio line says ``price_missing``
    and claims no money, and the receipt as a whole goes ``partial`` rather
    than reporting the total it can see as though it were the total.

    The failure this rules out is the tempting one — a receipt that answers
    "$5.00, complete" because $5.00 is all it could price.
    """
    vision_deployment, audio_deployment = deployments
    client = _Client()

    with _ledger(tmp_path, price_table(**{vision_deployment: VISION_RATE})) as ledger:
        recorder = CostRecorder(ledger)
        grader = Grader(
            document, rubric_loader=None, client=client, cost_recorder=recorder
        )
        with recorder.attributed(task_id="task-a", stage=STAGE_GRADING):
            _read_both(grader._tool_judge, wav_file)
        receipt = recorder.receipt_for("task-a", BUCKET_GRADING)

    assert receipt.status == STATUS_PARTIAL
    assert receipt.model_calls == 2
    # The money it does know is the money it saw, not a share of a bigger one.
    assert receipt.known_cost_usd == VISION_USD

    assert _by_model(receipt) == {
        vision_deployment: (
            STAGE_PERCEPTION, STATUS_COMPLETE, 1, VISION_USD, ()
        ),
        audio_deployment: (
            STAGE_PERCEPTION, STATUS_PARTIAL, 1, Decimal("0"), ("price_missing",)
        ),
    }


def test_a_task_that_only_looked_files_no_line_for_listening(
    tmp_path, document, deployments, wav_file
):
    """Negative control: a row per model that ran, not per model configured.

    A ``$0.0000`` audio line on every task that never played anything would be
    the same untruth as a missing one, pointing the other way — a reader would
    learn that listening is free, from tasks that never listened.
    """
    vision_deployment, audio_deployment = deployments
    table = price_table(**{
        vision_deployment: VISION_RATE,
        audio_deployment: AUDIO_RATE,
    })
    client = _Client()

    with _ledger(tmp_path, table) as ledger:
        recorder = CostRecorder(ledger)
        grader = Grader(
            document, rubric_loader=None, client=client, cost_recorder=recorder
        )
        with recorder.attributed(task_id="task-a", stage=STAGE_GRADING):
            grader._tool_judge.vision_perception.judge(
                criterion="the chart carries a title", image_b64=PNG_B64
            )
        receipt = recorder.receipt_for("task-a", BUCKET_GRADING)

    assert client.chat.completions.calls == []
    assert list(_by_model(receipt)) == [vision_deployment]
    assert receipt.known_cost_usd == VISION_USD


def test_reading_still_works_with_no_ledger_to_write_to(
    tmp_path, document, wav_file
):
    """Negative control: metering stays opt-in.

    A run without a recorder hands the readers the bare connection. They have
    to go on reading — otherwise turning metering off would stop the grader
    seeing the deliverable, and the absent ledger would be reported as an
    absent bill rather than a smaller one.
    """
    client = _Client()
    grader = Grader(document, rubric_loader=None, client=client)

    _read_both(grader._tool_judge, wav_file)

    assert len(client.responses.calls) == 1
    assert len(client.chat.completions.calls) == 1
