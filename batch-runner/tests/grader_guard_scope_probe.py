"""Offline child probe for an immutable grader source or the guarded candidate."""
from __future__ import annotations

import argparse
import copy
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--guarded", action="store_true")
    args = parser.parse_args()

    def offline(event, _args):
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "subprocess.Popen"}:
            raise RuntimeError("external_effect_forbidden_in_grader_fixture")

    sys.addaudithook(offline)
    sys.path.insert(0, str(args.batch))
    import step8_grade as step8
    from core.cost_metering import CostRecorder
    from core.cost_receipts import CostReceiptLedger, STAGE_GRADING
    from core.grader import Grader, ItemGrade
    from core.rubric_loader import RubricItem, TaskRubric
    from tests.test_grader import _config, _Loader

    assert Path(step8.__file__).parent == args.batch
    model = "gpt-5.6-sol"
    tasks = ["02aa1805-c658-4069-8a6a-02dec146063a", "0112fc9b-c3b2-4084-8993-5a4abb1f54f1",
             "2ea2e5b5-257f-42e6-a7dc-93763f28b19d", "3baa0009-5a60-4ae8-ae99-4955cb328ff3",
             "0818571f-5ff7-4d39-9d2c-ced5ae44299e"]
    args.fixture.mkdir(exist_ok=True)
    deliverable = args.fixture / "d.txt"
    deliverable.write_text("fixed synthetic deliverable", encoding="utf-8")
    config = _config(args.fixture)
    config["judge"].update(model=model, deployment=model, reasoning={"effort": "max"})

    class Client:
        max_retries = 0

        def __init__(self):
            self.responses = self
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                model=model, status="completed", output=[],
                output_text='{"verdict":"pass","partial_score":1.0,"evidence":"ok","confidence":0.8,"reasoning":"ok"}',
                usage=SimpleNamespace(input_tokens=10, output_tokens=5,
                                      input_tokens_details=SimpleNamespace(cached_tokens=0)),
            )

    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2000, 1, 1, tzinfo=timezone.utc)

    work = args.fixture / ("guarded" if args.guarded else "sealed")
    work.mkdir()
    money = None
    admission = None
    pricing = None
    if args.guarded:
        import gpt56_pilot_usd_budget as usd
        from tests.test_gpt56_pilot_shared_usd import PRICE_FIXTURE, CONFIG

        pricing = patch.object(usd, "price_document", lambda: copy.deepcopy(PRICE_FIXTURE))
        pricing.start()
        money = usd.PilotUsdLedger(work, capture_sha256="b" * 64, task_ids=tasks, create=True)
        admission = usd.GradingUsdAdmission(money, CONFIG)
    audit = CostReceiptLedger(work / "audit.sqlite3", run_id="synthetic-grader-scope")
    recorder = CostRecorder(audit, **({"usd_admission": admission} if admission is not None else {}))
    client = Client()
    try:
        grader = Grader(config=config, rubric_loader=_Loader(), client=client, cost_recorder=recorder)
        item = RubricItem("r1", "evaluate quality", 10, None)
        task = TaskRubric(task_id=tasks[0], sector="synthetic", occupation="synthetic",
                          prompt="Fixed fixture, not a GDPVal answer.", rubric_items=[item],
                          rubric_pretty="", reference_files=[], gold_deliverable_files=[])
        with patch("time.perf_counter", return_value=100.0), patch.object(step8, "datetime", FixedClock):
            with recorder.attributed(task_id=task.task_id, stage=STAGE_GRADING):
                judged, _, _ = grader._judge(task, item, [deliverable])
            rows = [step8._task_to_dict(Grader._aggregate([judged], task), grading_wall_time_ms=0)]
            for maximum, awarded, verdict in ((10, 0, "fail"), (63, 42, "partial"),
                                               (-2, -2, "pass"), (90, 0, "judge_error")):
                synthetic = ItemGrade(rubric_item_id="r1", criterion="synthetic", max_score=maximum,
                                      awarded_score=awarded, verdict=verdict, decided_by="judge",
                                      required=None, evidence="fixed")
                rows.append(step8._task_to_dict(Grader._aggregate([synthetic], task), grading_wall_time_ms=0))
        assert len(client.calls) == 1 and judged.verdict == "pass"
        if money is not None:
            assert money.snapshot()["pending_requests"] == 0 and money.snapshot()["stop_reason"] is None
        print(json.dumps({"scope": "synthetic_fixture_not_real_five_task_scores", "request": client.calls[0],
                          "judged": asdict(judged), "tasks": rows, "summary": step8._compute_summary(rows)},
                         sort_keys=True, ensure_ascii=False))
        grader.close()
    finally:
        audit.close()
        if money is not None:
            money.close()
        if pricing is not None:
            pricing.stop()


if __name__ == "__main__":
    main()
