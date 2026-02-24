"""Tests for Main Orchestrator

Usage:
    pytest tests/test_main.py -v
"""

import os
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from types import SimpleNamespace

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import run_experiment, main
from core.data_loader import GDPValTask


@pytest.fixture
def mock_tasks():
    """Create mock GDPVal tasks"""
    return [
        GDPValTask(
            task_id=f"task_{i:03d}",
            occupation="Engineer",
            sector="Finance and Insurance",
            prompt=f"Task {i} prompt",
            reference_files=[],
            reference_file_urls=[],
            reference_file_hf_uris=[],
            deliverable_text="",
            deliverable_files=[]
        )
        for i in range(5)
    ]


@pytest.fixture
def mock_response():
    """Create mock OpenAI response"""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = "Mock response content"
    response.model = "gpt-5.2-chat"
    response.usage = SimpleNamespace(
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150
    )
    return response


@pytest.fixture
def mock_env():
    """Mock environment variables"""
    return {
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_API_KEY": "test-key"
    }


class TestRunExperiment:
    """Test suite for run_experiment() function"""

    def test_run_experiment_basic(self, mock_tasks, mock_response, mock_env):
        """Test basic experiment run"""
        with patch.dict(os.environ, mock_env):
            with patch("main.GDPValDataLoader") as mock_loader_cls:
                with patch("main.create_client") as mock_client_fn:
                    with patch("main.complete") as mock_complete_fn:
                        with patch("main.TaskExecutor") as mock_executor_cls:
                            # Setup mocks
                            mock_loader = Mock()
                            mock_loader.load.return_value = mock_tasks
                            mock_loader_cls.return_value = mock_loader

                            mock_client = Mock()
                            mock_client_fn.return_value = mock_client

                            mock_complete_fn.return_value = (mock_response, 123.45)

                            # Mock executor to return success
                            mock_exec = Mock()
                            mock_exec.execute.return_value = {
                                "success": True,
                                "text": "Mock response content",
                                "files": [],
                                "error": None,
                            }
                            mock_executor_cls.return_value = mock_exec

                            # Run experiment
                            result = run_experiment(
                                experiment_id="test_exp001",
                                condition="baseline",
                                model="gpt-5.2-chat"
                            )

                            # Verify result structure
                            assert isinstance(result, dict)
                            assert result["experiment_id"] == "test_exp001"
                            assert result["condition_name"] == "baseline"
                            assert result["model"] == "gpt-5.2-chat"
                            assert "summary" in result
                            assert result["summary"]["total_tasks"] == 5
                            assert result["summary"]["success_count"] == 5
                            assert result["summary"]["error_count"] == 0

    def test_run_experiment_with_sector_filter(self, mock_tasks, mock_response, mock_env):
        """Test experiment with sector filter"""
        with patch.dict(os.environ, mock_env):
            with patch("main.GDPValDataLoader") as mock_loader_cls:
                with patch("main.create_client") as mock_client_fn:
                    with patch("main.complete") as mock_complete_fn:
                        # Setup mocks
                        mock_loader = Mock()
                        mock_loader.load.return_value = mock_tasks
                        mock_loader_cls.return_value = mock_loader

                        mock_client_fn.return_value = Mock()
                        mock_complete_fn.return_value = (mock_response, 100.0)

                        # Run with sector filter
                        result = run_experiment(
                            experiment_id="test_exp002",
                            condition="baseline",
                            model="gpt-5.2-chat",
                            sector="Finance and Insurance"
                        )

                        # All tasks match the sector
                        assert result["summary"]["total_tasks"] == 5

    def test_run_experiment_with_sample(self, mock_tasks, mock_response, mock_env):
        """Test experiment with sample size"""
        with patch.dict(os.environ, mock_env):
            with patch("main.GDPValDataLoader") as mock_loader_cls:
                with patch("main.create_client") as mock_client_fn:
                    with patch("main.complete") as mock_complete_fn:
                        # Setup mocks
                        mock_loader = Mock()
                        mock_loader.load.return_value = mock_tasks
                        mock_loader_cls.return_value = mock_loader

                        mock_client_fn.return_value = Mock()
                        mock_complete_fn.return_value = (mock_response, 100.0)

                        # Run with sample
                        result = run_experiment(
                            experiment_id="test_exp003",
                            condition="baseline",
                            model="gpt-5.2-chat",
                            sample_size=3
                        )

                        # Should sample 3 tasks
                        assert result["summary"]["total_tasks"] == 3

    def test_run_experiment_with_output_file(self, mock_tasks, mock_response, mock_env, tmp_path):
        """Test experiment with output file"""
        output_file = tmp_path / "results" / "test.json"

        with patch.dict(os.environ, mock_env):
            with patch("main.GDPValDataLoader") as mock_loader_cls:
                with patch("main.create_client") as mock_client_fn:
                    with patch("main.complete") as mock_complete_fn:
                        # Setup mocks
                        mock_loader = Mock()
                        mock_loader.load.return_value = mock_tasks
                        mock_loader_cls.return_value = mock_loader

                        mock_client_fn.return_value = Mock()
                        mock_complete_fn.return_value = (mock_response, 100.0)

                        # Run with output
                        run_experiment(
                            experiment_id="test_exp004",
                            condition="baseline",
                            model="gpt-5.2-chat",
                            output_path=str(output_file)
                        )

                        # Check files created
                        assert output_file.exists()
                        assert output_file.with_suffix(".md").exists()

    def test_run_experiment_handles_errors(self, mock_tasks, mock_env):
        """Test that experiment handles API errors gracefully"""
        with patch.dict(os.environ, mock_env):
            with patch("main.GDPValDataLoader") as mock_loader_cls:
                with patch("main.create_client") as mock_client_fn:
                    with patch("main.complete") as mock_complete_fn:
                        # Setup mocks
                        mock_loader = Mock()
                        mock_loader.load.return_value = mock_tasks
                        mock_loader_cls.return_value = mock_loader

                        mock_client_fn.return_value = Mock()

                        # Simulate API error
                        mock_complete_fn.side_effect = Exception("API timeout")

                        # Run experiment
                        result = run_experiment(
                            experiment_id="test_exp005",
                            condition="baseline",
                            model="gpt-5.2-chat"
                        )

                        # Should capture errors
                        assert result["summary"]["total_tasks"] == 5
                        assert result["summary"]["success_count"] == 0
                        assert result["summary"]["error_count"] == 5

    def test_run_experiment_missing_credentials(self, mock_tasks):
        """Test that experiment fails with missing credentials"""
        with patch.dict(os.environ, {}, clear=True):
            with patch("main.GDPValDataLoader") as mock_loader_cls:
                mock_loader = Mock()
                mock_loader.load.return_value = mock_tasks
                mock_loader_cls.return_value = mock_loader

                with pytest.raises(ValueError) as exc_info:
                    run_experiment(
                        experiment_id="test_exp006",
                        condition="baseline",
                        model="gpt-5.2-chat"
                    )

                assert "Missing Azure credentials" in str(exc_info.value)

    def test_run_experiment_invalid_condition(self, mock_tasks, mock_env):
        """Test that experiment fails with invalid prompt condition"""
        with patch.dict(os.environ, mock_env):
            with patch("main.GDPValDataLoader") as mock_loader_cls:
                mock_loader = Mock()
                mock_loader.load.return_value = mock_tasks
                mock_loader_cls.return_value = mock_loader

                with pytest.raises(ValueError) as exc_info:
                    run_experiment(
                        experiment_id="test_exp007",
                        condition="invalid_preset",
                        model="gpt-5.2-chat"
                    )

                assert "Unknown preset" in str(exc_info.value)


class TestMainCLI:
    """Test suite for main() CLI function"""

    def test_main_help(self):
        """Test --help flag"""
        test_args = ["main.py", "--help"]

        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_main_missing_required_args(self):
        """Test that CLI fails without required arguments"""
        test_args = ["main.py"]

        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code != 0

    def test_main_success(self, mock_tasks, mock_response, mock_env):
        """Test successful CLI execution"""
        test_args = [
            "main.py",
            "--experiment", "cli_exp001",
            "--condition", "baseline",
            "--model", "gpt-5.2-chat",
            "--sample", "3"
        ]

        with patch.object(sys, "argv", test_args):
            with patch.dict(os.environ, mock_env):
                with patch("main.GDPValDataLoader") as mock_loader_cls:
                    with patch("main.create_client") as mock_client_fn:
                        with patch("main.complete") as mock_complete_fn:
                            # Setup mocks
                            mock_loader = Mock()
                            mock_loader.load.return_value = mock_tasks
                            mock_loader_cls.return_value = mock_loader

                            mock_client_fn.return_value = Mock()
                            mock_complete_fn.return_value = (mock_response, 100.0)

                            # Run CLI
                            exit_code = main()

                            assert exit_code == 0

    def test_main_with_output(self, mock_tasks, mock_response, mock_env, tmp_path):
        """Test CLI with output file"""
        output_file = tmp_path / "cli_result.json"
        test_args = [
            "main.py",
            "--experiment", "cli_exp002",
            "--condition", "baseline",
            "--model", "gpt-5.2-chat",
            "--sample", "2",
            "--output", str(output_file)
        ]

        with patch.object(sys, "argv", test_args):
            with patch.dict(os.environ, mock_env):
                with patch("main.GDPValDataLoader") as mock_loader_cls:
                    with patch("main.create_client") as mock_client_fn:
                        with patch("main.complete") as mock_complete_fn:
                            # Setup mocks
                            mock_loader = Mock()
                            mock_loader.load.return_value = mock_tasks
                            mock_loader_cls.return_value = mock_loader

                            mock_client_fn.return_value = Mock()
                            mock_complete_fn.return_value = (mock_response, 100.0)

                            # Run CLI
                            exit_code = main()

                            assert exit_code == 0
                            assert output_file.exists()

    def test_main_keyboard_interrupt(self, mock_tasks, mock_env):
        """Test CLI handles keyboard interrupt"""
        test_args = [
            "main.py",
            "--experiment", "cli_exp003",
            "--condition", "baseline",
            "--model", "gpt-5.2-chat"
        ]

        with patch.object(sys, "argv", test_args):
            with patch.dict(os.environ, mock_env):
                with patch("main.GDPValDataLoader") as mock_loader_cls:
                    with patch("main.create_client") as mock_client_fn:
                        with patch("main.TaskExecutor") as mock_executor_cls:
                            # Setup mocks
                            mock_loader = Mock()
                            mock_loader.load.return_value = mock_tasks
                            mock_loader_cls.return_value = mock_loader

                            mock_client_fn.return_value = Mock()
                            mock_exec = Mock()
                            mock_exec.execute.side_effect = KeyboardInterrupt()
                            mock_executor_cls.return_value = mock_exec

                            # Run CLI
                            exit_code = main()

                            assert exit_code == 130  # Standard exit code for SIGINT

    def test_main_error_handling(self, mock_env):
        """Test CLI error handling"""
        test_args = [
            "main.py",
            "--experiment", "cli_exp004",
            "--condition", "baseline",
            "--model", "gpt-5.2-chat"
        ]

        with patch.object(sys, "argv", test_args):
            with patch.dict(os.environ, mock_env):
                with patch("main.GDPValDataLoader") as mock_loader_cls:
                    # Simulate error
                    mock_loader_cls.side_effect = Exception("Dataset load failed")

                    # Run CLI
                    exit_code = main()

                    assert exit_code == 1


class TestMainWithConfig:
    """Test suite for main() with YAML config"""

    def test_main_with_config(self, mock_tasks, mock_response, mock_env, tmp_path):
        """Test CLI with YAML config file"""
        import yaml

        config_data = {
            "experiment": {
                "id": "test_exp",
                "name": "Test",
                "description": "Test",
                "author": "Test",
                "created_at": "2025-02-09",
            },
            "control": {"fixed": ["model"], "changed": ["prompt"]},
            "data": {
                "source": "openai/gdpval",
                "filter": {"sector": None, "occupation": None, "sample_size": 3},
            },
            "condition_a": {
                "name": "Baseline",
                "model": {
                    "provider": "azure",
                    "deployment": "gpt-5.2-chat",
                    "temperature": 0.0,
                    "seed": 42,
                },
                "prompt": {"system": "You are helpful.", "prefix": None, "suffix": None},
            },
            "condition_b": {
                "name": "Treatment",
                "model": {
                    "provider": "azure",
                    "deployment": "gpt-5.2-chat",
                    "temperature": 0.0,
                    "seed": 42,
                },
                "prompt": {"system": "You are helpful.", "prefix": None, "suffix": "Work carefully."},
            },
            "output": {"publish_to_hf": False, "submit_to_evals": False, "save_path": None},
        }

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        test_args = ["main.py", "--config", str(config_file)]

        with patch.object(sys, "argv", test_args):
            with patch.dict(os.environ, mock_env):
                with patch("main.GDPValDataLoader") as mock_loader_cls:
                    with patch("main.create_client") as mock_client_fn:
                        with patch("main.complete") as mock_complete_fn:
                            mock_loader = Mock()
                            mock_loader.load.return_value = mock_tasks
                            mock_loader_cls.return_value = mock_loader

                            mock_client_fn.return_value = Mock()
                            mock_complete_fn.return_value = (mock_response, 100.0)

                            exit_code = main()
                            assert exit_code == 0

    def test_main_with_config_test_mode(self, mock_tasks, mock_response, mock_env, tmp_path):
        """Test CLI with --test flag"""
        import yaml

        config_data = {
            "experiment": {"id": "test", "name": "Test", "description": "", "author": "", "created_at": "2025-02-09"},
            "control": {"fixed": [], "changed": []},
            "data": {"source": "openai/gdpval", "filter": {"sector": None, "sample_size": None}},
            "condition_a": {
                "name": "A",
                "model": {"provider": "azure", "deployment": "gpt-5.2-chat", "temperature": 0.0},
                "prompt": {"system": "Test"},
            },
            "condition_b": {
                "name": "B",
                "model": {"provider": "azure", "deployment": "gpt-5.2-chat", "temperature": 0.0},
                "prompt": {"system": "Test"},
            },
            "output": {"publish_to_hf": False, "submit_to_evals": False},
        }

        config_file = tmp_path / "test.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        test_args = ["main.py", "--config", str(config_file), "--test"]

        with patch.object(sys, "argv", test_args):
            with patch.dict(os.environ, mock_env):
                with patch("main.GDPValDataLoader") as mock_loader_cls:
                    with patch("main.create_client"):
                        with patch("main.complete") as mock_complete_fn:
                            mock_loader = Mock()
                            mock_loader.load.return_value = mock_tasks[:3]
                            mock_loader_cls.return_value = mock_loader
                            mock_complete_fn.return_value = (mock_response, 100.0)

                            exit_code = main()
                            assert exit_code == 0


class TestMainIntegration:
    """Integration-style tests without full API calls"""

    def test_full_workflow_mock(self, mock_tasks, mock_response, mock_env, tmp_path):
        """Test full workflow with all components mocked"""
        output_file = tmp_path / "workflow_result.json"

        with patch.dict(os.environ, mock_env):
            with patch("main.GDPValDataLoader") as mock_loader_cls:
                with patch("main.create_client") as mock_client_fn:
                    with patch("main.complete") as mock_complete_fn:
                        with patch("main.TaskExecutor") as mock_executor_cls:
                            # Setup mocks
                            mock_loader = Mock()
                            mock_loader.load.return_value = mock_tasks
                            mock_loader_cls.return_value = mock_loader

                            mock_client_fn.return_value = Mock()
                            mock_complete_fn.return_value = (mock_response, 123.45)

                            # Mock executor to return success
                            mock_exec = Mock()
                            mock_exec.execute.return_value = {
                                "success": True,
                                "text": "Mock response content",
                                "files": [],
                                "error": None,
                            }
                            mock_executor_cls.return_value = mock_exec

                            # Run full experiment
                            result = run_experiment(
                                experiment_id="workflow_exp001",
                                condition="baseline",
                                model="gpt-5.2-chat",
                                sector="Finance and Insurance",
                                sample_size=3,
                                output_path=str(output_file),
                                save_markdown=True
                            )

                            # Verify result
                            assert result["experiment_id"] == "workflow_exp001"
                            assert result["summary"]["total_tasks"] == 3
                            assert result["summary"]["success_count"] == 3

                            # Verify files
                            assert output_file.exists()
                            assert output_file.with_suffix(".md").exists()

                            # Verify JSON content
                            with open(output_file) as f:
                                saved_data = json.load(f)
                            assert saved_data["experiment_id"] == "workflow_exp001"


class TestIncrementalSaveAndResume:
    """Test suite for incremental save, resume, and retry features"""

    def test_load_existing_results_no_file(self):
        """No existing file returns empty"""
        from main import _load_existing_results
        results, started_at = _load_existing_results("/nonexistent/path.json")
        assert results == []
        assert started_at is None

    def test_load_existing_results_valid_file(self, tmp_path):
        """Load results from existing JSON"""
        from main import _load_existing_results
        data = {
            "experiment_id": "exp001",
            "started_at": "2026-01-01T00:00:00",
            "results": [
                {"task_id": "t1", "status": "success", "content": "ok"},
                {"task_id": "t2", "status": "error", "error": "fail"},
            ],
        }
        path = tmp_path / "exp001.json"
        path.write_text(json.dumps(data))
        results, started_at = _load_existing_results(str(path))
        assert len(results) == 2
        assert started_at == "2026-01-01T00:00:00"

    def test_save_incremental_json_atomic(self, tmp_path):
        """Incremental save creates valid JSON"""
        from main import _save_incremental_json
        results = [
            {"task_id": "t1", "status": "success", "latency_ms": 100.0,
             "usage": {"total_tokens": 50}},
            {"task_id": "t2", "status": "error", "error": "api error",
             "latency_ms": 200.0, "usage": None},
        ]
        path = str(tmp_path / "out.json")
        _save_incremental_json("exp001", "baseline", "gpt-4", results,
                               "2026-01-01T00:00:00", path)

        with open(path) as f:
            data = json.load(f)
        assert data["experiment_id"] == "exp001"
        assert data["summary"]["success_count"] == 1
        assert data["summary"]["error_count"] == 1
        assert data["completed_at"] is None  # Not finalized yet
        assert len(data["results"]) == 2

    def test_save_incremental_no_tmp_left(self, tmp_path):
        """Atomic write should not leave .tmp file"""
        from main import _save_incremental_json
        path = str(tmp_path / "out.json")
        _save_incremental_json("exp001", "baseline", "gpt-4", [],
                               "2026-01-01T00:00:00", path)
        assert not (tmp_path / "out.json.tmp").exists()
        assert (tmp_path / "out.json").exists()

    def test_execute_single_task_with_error_context(self, mock_tasks):
        """Error context is appended to prompt for retry"""
        from main import _execute_single_task

        captured_prompts = []
        task = mock_tasks[0]

        def mock_build(t):
            return {"system": "sys", "user": "original prompt"}

        mock_builder = Mock()
        mock_builder.build = mock_build

        mock_executor = Mock()
        mock_executor.execute = Mock(return_value={
            "success": True,
            "text": "Generated output",
            "deliverable_text": "desc",
            "files": [],
        })

        result = _execute_single_task(
            task, mock_builder, mock_executor, "subprocess", None, "gpt-4",
            "exp001", "baseline", error_context="ImportError: no module named X",
        )

        # Verify error context was injected into the prompt
        call_args = mock_executor.execute.call_args
        prompt_sent = call_args.kwargs.get("task_prompt") or call_args[1].get("task_prompt")
        if prompt_sent is None:
            prompt_sent = call_args[0][0] if call_args[0] else ""
        assert "[RETRY - PREVIOUS ATTEMPT FAILED]" in prompt_sent
        assert "ImportError: no module named X" in prompt_sent
        assert result["status"] == "success"

    def test_run_batch_inference_resume(self, mock_tasks, tmp_path):
        """Resume skips already-completed tasks"""
        from main import _run_batch_inference

        # Pre-populate 2 successful results
        existing = {
            "experiment_id": "exp001",
            "started_at": "2026-01-01T00:00:00",
            "results": [
                {"task_id": "task_000", "status": "success", "prompt_config": "baseline",
                 "content": "ok", "deliverable_text": "d", "deliverable_files": [],
                 "model": "gpt-4", "usage": {"total_tokens": 10}, "latency_ms": 100,
                 "timestamp": "2026-01-01T00:00:00"},
                {"task_id": "task_001", "status": "success", "prompt_config": "baseline",
                 "content": "ok", "deliverable_text": "d", "deliverable_files": [],
                 "model": "gpt-4", "usage": {"total_tokens": 10}, "latency_ms": 100,
                 "timestamp": "2026-01-01T00:00:00"},
            ],
        }
        out_path = str(tmp_path / "exp001.json")
        with open(out_path, "w") as f:
            json.dump(existing, f)

        mock_builder = Mock()
        mock_builder.build = Mock(return_value={"system": "sys", "user": "prompt"})

        mock_executor_cls = Mock()
        mock_result = {"success": True, "text": "ok", "deliverable_text": "d", "files": []}

        with patch("main.TaskExecutor") as mock_exec_cls, \
             patch("main.NeedsFilesManifest.load", side_effect=FileNotFoundError):
            mock_exec = Mock()
            mock_exec.execute = Mock(return_value=mock_result)
            mock_exec_cls.return_value = mock_exec

            collector = _run_batch_inference(
                mock_tasks, mock_builder, None, "gpt-4",
                "exp001", "baseline", execution_mode="subprocess",
                output_path=out_path,
            )

        result = collector.finalize()
        # All 5 tasks should be in results (2 resumed + 3 new)
        assert result.total_count == 5
        assert result.success_count == 5
        # Only 3 tasks should have been executed (2 were skipped)
        assert mock_exec.execute.call_count == 3

    def test_run_batch_inference_retry(self, tmp_path):
        """Retry loop retries failed tasks with error context"""
        from main import _run_batch_inference

        tasks = [
            GDPValTask(
                task_id="task_retry",
                occupation="Engineer",
                sector="Tech",
                prompt="test",
                reference_files=[],
                reference_file_urls=[],
                reference_file_hf_uris=[],
                deliverable_text="",
                deliverable_files=[],
            )
        ]

        mock_builder = Mock()
        mock_builder.build = Mock(return_value={"system": "sys", "user": "prompt"})

        # First call fails, second call (retry) succeeds
        call_count = [0]
        def mock_execute(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"success": False, "error": "Pillow textsize removed"}
            return {"success": True, "text": "fixed", "deliverable_text": "d", "files": []}

        with patch("main.TaskExecutor") as mock_exec_cls, \
             patch("main.NeedsFilesManifest.load", side_effect=FileNotFoundError):
            mock_exec = Mock()
            mock_exec.execute = Mock(side_effect=mock_execute)
            mock_exec_cls.return_value = mock_exec

            collector = _run_batch_inference(
                tasks, mock_builder, None, "gpt-4",
                "task_retry_exp", "baseline", execution_mode="subprocess",
                output_path=str(tmp_path / "retry.json"),
                max_retries=3,
            )

        result = collector.finalize()
        assert result.total_count == 1
        assert result.success_count == 1

        # Verify the retry prompt included error context
        retry_call = mock_exec.execute.call_args_list[1]
        retry_prompt = retry_call.kwargs.get("task_prompt", "")
        assert "Pillow textsize removed" in retry_prompt
        assert "[RETRY - PREVIOUS ATTEMPT FAILED]" in retry_prompt

        # Check incremental JSON was saved
        with open(tmp_path / "retry.json") as f:
            saved = json.load(f)
        assert saved["summary"]["success_count"] == 1
        assert saved["results"][0]["retry_count"] == 1
