"""Regression tests for the 3 silent corruption fixes (TASK_SILENT_CORRUPTION_FIXES).

Each fix is locked by a focused regression test:

Fix 1: _AVAILABLE_FILES dead-write in core/subprocess_runner.py
   The files_header (`_AVAILABLE_FILES = [...]`) prepended to `code` was
   never persisted back to `code_path`, so the subprocess executed the
   original code without the hint. Tests verify the hint actually runs
   inside the subprocess.

Fix 2: Anthropic content[0].text crash + stop_reason ignored in
   core/llm_client.py. AnthropicClient.chat_complete must (a) iterate
   response.content blocks and concat only text-type blocks (no crash on
   thinking/tool_use blocks), and (b) expose response.stop_reason as
   choices[0].finish_reason (with "max_tokens" → "length" mapping) so
   step2:436 truncation guard works for Anthropic.

Fix 3: qa_failed dead invariant in step2_run_inference.py. When Self-QA
   genuinely fails (score < min_score after retries exhausted), the
   returned best_result must carry status="qa_failed" so the 4
   read-sites + RETRIABLE_STATUSES retry plumbing fire. The undetermined
   branch is intentionally left as "success".
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Fix 1 — _AVAILABLE_FILES dead-write in subprocess_runner._execute_safely
# ─────────────────────────────────────────────────────────────────────────────


class TestFix1AvailableFilesPersisted:
    """Verify trusted launcher globals reach untouched generated source."""

    def _make_runner(self):
        from core.subprocess_runner import SubprocessRunner
        return SubprocessRunner(MagicMock())

    def test_available_files_hint_is_executed_by_subprocess(self, tmp_path):
        """With reference files, the subprocess must observe _AVAILABLE_FILES.

        The launcher injects the global without prepending code to solution.py.
        """
        runner = self._make_runner()
        ref_file = tmp_path / "data.csv"
        ref_file.write_text("col1,col2\n1,2\n", encoding="utf-8")

        # Code that depends on the injected _AVAILABLE_FILES variable.
        # Before fix, this would NameError because the variable is never defined
        # in the executed file.
        user_code = "print('FILES:', _AVAILABLE_FILES)"

        result = runner._execute_safely(user_code, reference_files=[str(ref_file)])

        assert result["success"] is True, f"subprocess failed: {result.get('error')}"
        assert "FILES:" in result["text"]
        assert "data.csv" in result["text"]

    def test_no_reference_files_injects_empty_available_files(self, tmp_path):
        runner = self._make_runner()
        user_code = "print('FILES:', _AVAILABLE_FILES)"

        result = runner._execute_safely(user_code, reference_files=None)

        assert result["success"] is True, f"subprocess failed: {result.get('error')}"
        assert "FILES: []" in result["text"]

    def test_future_import_remains_first_with_reference_files(self, tmp_path):
        runner = self._make_runner()
        ref_file = tmp_path / "data.csv"
        ref_file.write_text("x\n1\n", encoding="utf-8")
        user_code = (
            "from __future__ import annotations\n"
            "print('FILES:', _AVAILABLE_FILES)\n"
        )

        result = runner._execute_safely(user_code, reference_files=[str(ref_file)])

        assert result["success"] is True, result.get("error")
        assert "data.csv" in result["text"]
        assert result["preflight"]["ok"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Fix 2 — Anthropic content[0].text crash + stop_reason ignored
# ─────────────────────────────────────────────────────────────────────────────


def _make_text_block(text):
    return SimpleNamespace(type="text", text=text)


def _make_thinking_block(text="internal monologue"):
    # ThinkingBlock objects have no `.text` attribute (well, in some SDK
    # versions they do as `.thinking`, not `.text`). The key invariant we test
    # is that we skip them based on `.type != "text"`.
    return SimpleNamespace(type="thinking", thinking=text)


def _make_tool_use_block(name="search"):
    return SimpleNamespace(type="tool_use", name=name, id="toolu_1", input={})


def _make_anthropic_response(content_blocks, stop_reason="end_turn", model="claude-x"):
    return SimpleNamespace(
        content=content_blocks,
        stop_reason=stop_reason,
        model=model,
        usage=SimpleNamespace(input_tokens=10, output_tokens=20),
    )


@pytest.fixture
def anthropic_client():
    """Build AnthropicClient with the underlying SDK client mocked out."""
    from core.llm_client import AnthropicClient

    # Bypass __init__ to avoid needing the `anthropic` package or API key.
    client = AnthropicClient.__new__(AnthropicClient)
    client.client = MagicMock()
    return client


class TestFix2AnthropicContentExtraction:
    """Iterate content blocks; only text blocks contribute to choices[0].message.content."""

    def test_single_text_block_existing_behavior(self, anthropic_client):
        """Sanity: single text block returns its text (no regression)."""
        anthropic_client.client.messages.create.return_value = _make_anthropic_response(
            [_make_text_block("hello world")]
        )
        resp = anthropic_client.chat_complete(
            model="claude-x",
            messages=[{"role": "user", "content": "hi"}],
        )
        assert resp.choices[0].message.content == "hello world"

    def test_thinking_then_text_does_not_raise(self, anthropic_client):
        """First block thinking, then text → returns the text, no AttributeError.

        Before fix: response.content[0].text crashed because thinking blocks
        don't have a `.text` attribute (or have a different one).
        """
        anthropic_client.client.messages.create.return_value = _make_anthropic_response(
            [_make_thinking_block(), _make_text_block("real answer")]
        )
        resp = anthropic_client.chat_complete(
            model="claude-x",
            messages=[{"role": "user", "content": "hi"}],
        )
        assert resp.choices[0].message.content == "real answer"

    def test_tool_use_then_text_does_not_raise(self, anthropic_client):
        """First block tool_use, then text → returns the text, no AttributeError."""
        anthropic_client.client.messages.create.return_value = _make_anthropic_response(
            [_make_tool_use_block(), _make_text_block("done")]
        )
        resp = anthropic_client.chat_complete(
            model="claude-x",
            messages=[{"role": "user", "content": "hi"}],
        )
        assert resp.choices[0].message.content == "done"

    def test_multiple_text_blocks_concatenated(self, anthropic_client):
        """Multiple text blocks are concatenated."""
        anthropic_client.client.messages.create.return_value = _make_anthropic_response(
            [_make_text_block("part1"), _make_text_block("part2")]
        )
        resp = anthropic_client.chat_complete(
            model="claude-x",
            messages=[{"role": "user", "content": "hi"}],
        )
        assert resp.choices[0].message.content == "part1part2"

    def test_empty_content_returns_empty_string(self, anthropic_client):
        """No content blocks → empty content (no crash)."""
        anthropic_client.client.messages.create.return_value = _make_anthropic_response(
            []
        )
        resp = anthropic_client.chat_complete(
            model="claude-x",
            messages=[{"role": "user", "content": "hi"}],
        )
        assert resp.choices[0].message.content == ""

    def test_only_non_text_blocks_returns_empty_string(self, anthropic_client):
        """If every block is thinking/tool_use → content is "" (no crash)."""
        anthropic_client.client.messages.create.return_value = _make_anthropic_response(
            [_make_thinking_block(), _make_tool_use_block()]
        )
        resp = anthropic_client.chat_complete(
            model="claude-x",
            messages=[{"role": "user", "content": "hi"}],
        )
        assert resp.choices[0].message.content == ""


class TestFix2FinishReasonExposed:
    """stop_reason must be mapped to OpenAI-style finish_reason on choices[0]."""

    def test_max_tokens_maps_to_length(self, anthropic_client):
        """Anthropic 'max_tokens' → OpenAI 'length' so step2 truncation guard fires."""
        anthropic_client.client.messages.create.return_value = _make_anthropic_response(
            [_make_text_block("truncated...")], stop_reason="max_tokens"
        )
        resp = anthropic_client.chat_complete(
            model="claude-x",
            messages=[{"role": "user", "content": "hi"}],
        )
        # step2_run_inference.py:436 — getattr(response.choices[0], "finish_reason", None)
        finish_reason = getattr(resp.choices[0], "finish_reason", None)
        assert finish_reason == "length"

    def test_end_turn_maps_to_stop(self, anthropic_client):
        anthropic_client.client.messages.create.return_value = _make_anthropic_response(
            [_make_text_block("complete")], stop_reason="end_turn"
        )
        resp = anthropic_client.chat_complete(
            model="claude-x",
            messages=[{"role": "user", "content": "hi"}],
        )
        assert getattr(resp.choices[0], "finish_reason", None) == "stop"

    def test_stop_sequence_maps_to_stop(self, anthropic_client):
        anthropic_client.client.messages.create.return_value = _make_anthropic_response(
            [_make_text_block("complete")], stop_reason="stop_sequence"
        )
        resp = anthropic_client.chat_complete(
            model="claude-x",
            messages=[{"role": "user", "content": "hi"}],
        )
        assert getattr(resp.choices[0], "finish_reason", None) == "stop"

    def test_missing_stop_reason_is_none(self, anthropic_client):
        anthropic_client.client.messages.create.return_value = _make_anthropic_response(
            [_make_text_block("complete")], stop_reason=None
        )
        resp = anthropic_client.chat_complete(
            model="claude-x",
            messages=[{"role": "user", "content": "hi"}],
        )
        assert getattr(resp.choices[0], "finish_reason", None) is None


class TestFix2AzureRegression:
    """Verify the Azure/OpenAI completion path is unaffected by the wrapper changes."""

    def test_choice_default_finish_reason_is_none(self):
        """_Choice without explicit finish_reason → None (back-compat)."""
        from core.llm_client import _Choice

        c = _Choice("content")
        assert c.message.content == "content"
        assert c.finish_reason is None

    def test_normalized_response_default_finish_reason_is_none(self):
        from core.llm_client import NormalizedResponse

        r = NormalizedResponse(content="hi")
        assert r.choices[0].message.content == "hi"
        assert r.choices[0].finish_reason is None

    def test_complete_with_azure_response_passes_through(self):
        """complete() returns the raw Azure SDK response (with whatever
        finish_reason that SDK already provides).
        """
        from core.llm_client import complete

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "azure says hi"
        mock_resp.choices[0].finish_reason = "stop"
        mock_client.chat.completions.create.return_value = mock_resp

        response, _ = complete(mock_client, "gpt-x", [{"role": "user", "content": "x"}])
        assert response is mock_resp
        assert response.choices[0].finish_reason == "stop"


# ─────────────────────────────────────────────────────────────────────────────
# Fix 3 — qa_failed dead invariant in step2_run_inference._run_task_with_qa
# ─────────────────────────────────────────────────────────────────────────────


class TestFix3RetrieableStatuses:
    """qa_failed must be in RETRIABLE_STATUSES (already true; sanity lock)."""

    def test_qa_failed_is_retriable(self):
        from step2_run_inference import RETRIABLE_STATUSES

        assert "qa_failed" in RETRIABLE_STATUSES

    def test_get_failed_task_ids_picks_up_qa_failed(self):
        """_get_failed_task_ids includes qa_failed entries → resume retry fires."""
        from step2_run_inference import _get_failed_task_ids

        progress = {
            "results": [
                {"task_id": "t1", "status": "success"},
                {"task_id": "t2", "status": "qa_failed", "error": ""},
                {"task_id": "t3", "status": "error", "error": "boom"},
                {"task_id": "t4", "status": "pending"},
            ]
        }
        failed = _get_failed_task_ids(progress)
        ids = {f["task_id"] for f in failed}
        # qa_failed must be picked up alongside error/pending
        assert "t2" in ids
        assert "t3" in ids
        assert "t4" in ids
        assert "t1" not in ids


def _build_step1_prepared(tmp_path: Path, task_id: str = "t1") -> Path:
    """Write a minimal step1_tasks_prepared.json for run_inference."""
    prepared = {
        "experiment_id": "exp_test",
        "experiment_name": "qa_failed_regression",
        "source": "test",
        "execution": {
            "mode": "subprocess",
            "max_retries": 1,
            "resume_max_rounds": 1,
        },
        "tasks": [
            {
                "task_id": task_id,
                "sector": "test_sector",
                "occupation": "test_occupation",
                "instruction": "Do a thing.",
                "reference_files": [],
            }
        ],
        "condition_a": {
            "name": "test_condition",
            "model": {"provider": "azure", "deployment": "gpt-test"},
            "prompt": {"system": "you are helpful"},
            "qa": {
                "enabled": True,
                "min_score": 6,
                "max_retries": 2,
                "prompt": "Evaluate the output: {deliverable_text}",
                "model": "gpt-qa",
            },
        },
    }
    prepared_path = tmp_path / "step1_tasks_prepared.json"
    prepared_path.write_text(json.dumps(prepared), encoding="utf-8")
    return prepared_path


@pytest.fixture
def patched_run_inference(tmp_path, monkeypatch):
    """Patch WORKSPACE_DIR/DELIVERABLE_DIR + dependencies so run_inference can
    be driven by injected _execute_single_task / _run_self_qa stubs.
    """
    import step2_run_inference as s2

    workspace = tmp_path / "workspace"
    upload = workspace / "upload"
    deliverables = upload / "deliverable_files"
    deliverables.mkdir(parents=True)

    monkeypatch.setattr(s2, "WORKSPACE_DIR", workspace, raising=True)
    monkeypatch.setattr(s2, "UPLOAD_DIR", upload, raising=True)
    monkeypatch.setattr(s2, "DELIVERABLE_DIR", deliverables, raising=True)

    _build_step1_prepared(workspace)

    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.test/")
    monkeypatch.setattr(
        s2, "create_provider_client", MagicMock(return_value=MagicMock())
    )
    monkeypatch.setattr(s2, "TaskExecutor", MagicMock(return_value=MagicMock()))
    # Manifest is optional; FileNotFoundError path is fine.
    monkeypatch.setattr(
        s2.NeedsFilesManifest,
        "load",
        classmethod(lambda cls: (_ for _ in ()).throw(FileNotFoundError())),
    )

    return s2, workspace


def _read_progress(workspace: Path) -> dict:
    progress_path = workspace / "step2_inference_progress.json"
    return json.loads(progress_path.read_text(encoding="utf-8"))


class TestFix3RunTaskWithQA:
    """Drive run_inference end-to-end with mocked _execute_single_task and
    _run_self_qa to verify the qa_failed status is set on genuine fail and
    preserved as success on undetermined / passing.
    """

    def _success_execute(self, *args, **kwargs):
        return {
            "task_id": "t1",
            "status": "success",
            "deliverable_text": "hello",
            "deliverable_files": [],
            "latency_ms": 10,
        }

    def test_genuine_qa_fail_marks_status_qa_failed(
        self, patched_run_inference, monkeypatch
    ):
        """QA fails (score < min_score) → final result.status == "qa_failed"."""
        s2, workspace = patched_run_inference

        monkeypatch.setattr(s2, "_execute_single_task", self._success_execute)
        monkeypatch.setattr(
            s2,
            "_run_self_qa",
            lambda *a, **k: {
                "passed": False,
                "score": 3,
                "issues": ["bad"],
                "suggestion": "fix it",
                "undetermined": False,
                "llm_passed": False,
            },
        )

        s2.run_inference(
            condition_key="condition_a",
            resume=False,
            resume_max_rounds=1,
        )

        progress = _read_progress(workspace)
        results = progress["results"]
        assert len(results) == 1
        assert results[0]["status"] == "qa_failed", (
            f"Expected qa_failed, got {results[0]['status']!r}; "
            f"qa={results[0].get('qa')}"
        )

    def test_qa_passes_keeps_status_success(
        self, patched_run_inference, monkeypatch
    ):
        """QA passes → final result.status remains "success" (no regression)."""
        s2, workspace = patched_run_inference

        monkeypatch.setattr(s2, "_execute_single_task", self._success_execute)
        monkeypatch.setattr(
            s2,
            "_run_self_qa",
            lambda *a, **k: {
                "passed": True,
                "score": 9,
                "issues": [],
                "suggestion": "",
                "undetermined": False,
                "llm_passed": True,
            },
        )

        s2.run_inference(
            condition_key="condition_a",
            resume=False,
            resume_max_rounds=1,
        )

        progress = _read_progress(workspace)
        results = progress["results"]
        assert len(results) == 1
        assert results[0]["status"] == "success"

    def test_qa_undetermined_keeps_status_success(
        self, patched_run_inference, monkeypatch
    ):
        """Undetermined-on-final-attempt → status remains "success" (intentional)."""
        s2, workspace = patched_run_inference

        monkeypatch.setattr(s2, "_execute_single_task", self._success_execute)
        monkeypatch.setattr(
            s2,
            "_run_self_qa",
            lambda *a, **k: {
                "passed": None,
                "score": None,
                "issues": ["parse fail"],
                "suggestion": "",
                "undetermined": True,
            },
        )

        s2.run_inference(
            condition_key="condition_a",
            resume=False,
            resume_max_rounds=1,
        )

        progress = _read_progress(workspace)
        results = progress["results"]
        assert len(results) == 1
        # The undetermined branch must remain status="success" — fix 3 only
        # touches the genuine-fail branch.
        assert results[0]["status"] == "success"
