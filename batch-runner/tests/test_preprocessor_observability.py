"""Behavior-neutral observability tests for inference preprocessors."""

import hashlib
from types import SimpleNamespace

import step2_run_inference as step2


def _condition(pp_type: str) -> dict:
    return {
        "preprocessors": [{
            "type": pp_type,
            "trigger": f"has_{pp_type.split('_')[0]}_files",
            "model": {"provider": "azure", "deployment": "probe-model"},
            "include_task_instruction": True,
        }]
    }


def test_audio_skip_records_reason(monkeypatch):
    monkeypatch.setattr(step2, "filter_audio_files", lambda files: [])
    observations = []

    output = step2._run_preprocessors(
        _condition("audio_analyzer"), [], "task", observations
    )

    assert output == ""
    assert observations == [{
        "type": "audio_analyzer",
        "trigger": "has_audio_files",
        "status": "skipped_no_matching_files",
        "matched_file_count": 0,
        "matched_extensions": [],
    }]


def test_audio_success_records_hash_without_body(monkeypatch):
    analysis = "private analysis body"
    monkeypatch.setattr(
        step2, "filter_audio_files", lambda files: ["/private/input.wav"]
    )
    monkeypatch.setattr(step2, "create_provider_client", lambda provider: object())
    monkeypatch.setattr(step2, "analyze_audio_files", lambda **kwargs: analysis)
    observations = []

    output = step2._run_preprocessors(
        _condition("audio_analyzer"), ["/private/input.wav"], "task", observations
    )

    assert output == analysis
    assert observations[0]["status"] == "success"
    assert observations[0]["matched_file_count"] == 1
    assert observations[0]["matched_extensions"] == [".wav"]
    assert observations[0]["analysis_chars"] == len(analysis)
    assert observations[0]["analysis_sha256"] == hashlib.sha256(
        analysis.encode("utf-8")
    ).hexdigest()
    assert analysis not in str(observations)
    assert "/private" not in str(observations)


def test_video_error_records_type_without_message(monkeypatch, capsys):
    monkeypatch.setattr(
        step2, "filter_video_files", lambda files: ["/secret/input.mp4"]
    )
    monkeypatch.setattr(step2, "create_provider_client", lambda provider: object())

    def _fail(**kwargs):
        raise RuntimeError("sensitive upstream detail")

    monkeypatch.setattr(step2, "analyze_video_files", _fail)
    observations = []

    output = step2._run_preprocessors(
        _condition("video_analyzer"), ["/secret/input.mp4"], "task", observations
    )

    assert output == ""
    assert observations[0]["status"] == "error"
    assert observations[0]["error_type"] == "RuntimeError"
    assert observations[0]["matched_file_count"] == 1
    assert observations[0]["matched_extensions"] == [".mp4"]
    assert "sensitive upstream detail" not in str(observations)
    assert "/secret" not in str(observations)
    captured = capsys.readouterr()
    assert "RuntimeError" in captured.out
    assert "sensitive upstream detail" not in captured.out


def test_compact_observability_keeps_only_provenance():
    secret_filename = "private-client-name-secret.xlsx"
    result = {
        "sandbox_manifest": {
            "schema_version": "1.0",
            "sandbox_backend": "docker",
            "sandbox_image": "image@sha256:abc",
            "run_context": {"run_id": "123"},
            "selected_skills_detail": [{"name": "audio", "score": 10}],
            "attempts": [{
                "attempt": 0,
                "status": "ok",
                "prompt_sha256": "a" * 64,
                "generated_artifacts": [secret_filename],
            }],
            "best_attempt": 0,
            "final_status": "ok",
            "verification_report": {"heavy": "omitted"},
        }
    }

    observed = step2._build_execution_observability(result, [])

    assert observed["sandbox"]["backend"] == "docker"
    assert observed["sandbox"]["best_attempt"] == 0
    assert "verification_report" not in observed["sandbox"]
    assert observed["sandbox"]["attempts"][0]["generated_artifact_count"] == 1
    assert secret_filename not in str(observed)


def test_execute_single_task_preserves_compact_observability(monkeypatch):
    manifest = {
        "schema_version": "1.0",
        "sandbox_backend": "docker",
        "sandbox_image": "image@sha256:abc",
        "run_context": {"run_id": "123"},
        "selected_skills_detail": [{"name": "document", "score": 10}],
        "attempts": [{"attempt": 0, "prompt_sha256": "a" * 64}],
        "best_attempt": 0,
        "final_status": "ok",
    }

    class _Executor:
        def execute(self, **kwargs):
            return {
                "success": True,
                "text": "done",
                "deliverable_text": "done",
                "files": [],
                "sandbox_manifest": manifest,
            }

    monkeypatch.setattr(step2, "_save_files", lambda files, task_id: [])
    task = {
        "task_id": "task-1",
        "instruction": "Create a document",
        "occupation": "Analyst",
        "reference_files": [],
        "needs_files": False,
    }
    condition = {
        "prompt": {"system": "test", "prefix": None, "body": None, "suffix": None},
        "preprocessors": [],
    }

    result = step2._execute_single_task(
        task,
        condition,
        _Executor(),
        "sandbox",
        SimpleNamespace(),
        "gpt-5.4",
    )

    assert result["status"] == "success"
    assert result["observability"]["preprocessors"] == []
    assert result["observability"]["sandbox"]["image"] == "image@sha256:abc"
    assert result["observability"]["sandbox"]["attempts"][0]["prompt_sha256"] == "a" * 64


def test_step6_task_result_preserves_compact_observability():
    import step6_report

    observation = {
        "preprocessors": [{"type": "audio_analyzer", "status": "success"}],
        "sandbox": {"best_attempt": 0, "final_status": "ok"},
    }
    task_results, _ = step6_report._build_task_results({
        "results": [{
            "task_id": "task-1",
            "status": "success",
            "observability": observation,
        }]
    })

    assert task_results[0]["observability"] == observation


def test_compact_observability_drops_unknown_attempt_text():
    secret = "raw secret task or filename"
    observed = step2._build_execution_observability({
        "sandbox_manifest": {
            "attempts": [{
                "attempt": 0,
                "generated_artifacts": [secret],
                "unexpected_raw_field": secret,
            }]
        }
    }, [])

    assert secret not in str(observed)
    assert observed["sandbox"]["attempts"][0]["generated_artifact_count"] == 1


def test_sensitive_attempt_text_never_reaches_step6_task_result():
    import step6_report

    secret = "private-client-secret-filename.xlsx"
    observed = step2._build_execution_observability({
        "sandbox_manifest": {
            "attempts": [{
                "attempt": 0,
                "generated_artifacts": [secret],
                "unexpected_raw_field": secret,
            }],
            "final_status": "ok",
        }
    }, [])
    task_results, _ = step6_report._build_task_results({
        "results": [{
            "task_id": "task-1",
            "status": "success",
            "observability": observed,
        }]
    })

    assert secret not in str(task_results)
    attempt = task_results[0]["observability"]["sandbox"]["attempts"][0]
    assert attempt["generated_artifact_count"] == 1