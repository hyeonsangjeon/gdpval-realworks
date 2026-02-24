"""Result Formatter for experiment results

Formats experiment results into JSON and Markdown for reporting and storage.

Usage:
    from core.result_formatter import ResultFormatter

    formatter = ResultFormatter()

    # To JSON
    json_str = formatter.to_json(experiment_result)
    with open("results.json", "w") as f:
        f.write(json_str)

    # To dict (for further processing)
    data = formatter.to_dict(experiment_result)

    # To Markdown
    md_str = formatter.to_markdown(experiment_result)
    with open("results.md", "w") as f:
        f.write(md_str)
"""

import json
from typing import Dict, Any
from datetime import datetime


class ResultFormatter:
    """Formats experiment results into various output formats

    Example:
        formatter = ResultFormatter()
        json_output = formatter.to_json(experiment_result)
        markdown_output = formatter.to_markdown(experiment_result)
    """

    def to_json(self, result, indent: int = 2) -> str:
        """Convert ExperimentResult to JSON string

        Args:
            result: ExperimentResult object
            indent: JSON indentation (default: 2)

        Returns:
            JSON string with formatted results
        """
        return json.dumps(self.to_dict(result), indent=indent, default=str)

    def to_dict(self, result) -> Dict[str, Any]:
        """Convert ExperimentResult to dictionary

        Args:
            result: ExperimentResult object

        Returns:
            Dictionary containing all experiment data including:
            - experiment_id, condition_name, model
            - summary (total_tasks, success_count, error_count, total_tokens, avg_latency_ms)
            - started_at, completed_at timestamps
            - detailed results for each task
        """
        return {
            "experiment_id": result.experiment_id,
            "condition_name": result.condition_name,
            "model": result.model,
            "summary": {
                "total_tasks": result.total_count,
                "success_count": result.success_count,
                "error_count": result.error_count,
                "total_tokens": result.total_tokens,
                "avg_latency_ms": round(result.avg_latency_ms, 2),
                "success_rate": round(result.success_count / result.total_count * 100, 2) if result.total_count > 0 else 0.0,
            },
            "started_at": result.started_at.isoformat(),
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            "duration_seconds": self._calculate_duration(result.started_at, result.completed_at),
            "results": [self._format_task_result(r) for r in result.results]
        }

    def to_markdown(self, result) -> str:
        """Convert ExperimentResult to Markdown report

        Args:
            result: ExperimentResult object

        Returns:
            Markdown-formatted report string
        """
        lines = []

        # Header
        lines.append(f"# Experiment Report: {result.experiment_id}")
        lines.append("")
        lines.append(f"**Condition**: {result.condition_name}")
        lines.append(f"**Model**: {result.model}")
        lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Total Tasks**: {result.total_count}")
        lines.append(f"- **Success**: {result.success_count} ({result.success_count / result.total_count * 100:.1f}%)" if result.total_count > 0 else "- **Success**: 0 (0.0%)")
        lines.append(f"- **Errors**: {result.error_count}")
        lines.append(f"- **Total Tokens**: {result.total_tokens:,}")
        lines.append(f"- **Avg Latency**: {result.avg_latency_ms:.2f}ms")
        lines.append("")

        # Timeline
        lines.append("## Timeline")
        lines.append("")
        lines.append(f"- **Started**: {result.started_at.isoformat()}")
        if result.completed_at:
            lines.append(f"- **Completed**: {result.completed_at.isoformat()}")
            duration = self._calculate_duration(result.started_at, result.completed_at)
            if duration:
                lines.append(f"- **Duration**: {duration:.1f}s")
        lines.append("")

        # Success results
        success_results = [r for r in result.results if r.error is None]
        if success_results:
            lines.append("## Successful Results")
            lines.append("")
            lines.append(f"Total: {len(success_results)} tasks")
            lines.append("")
            for r in success_results[:5]:  # Show first 5
                lines.append(f"### {r.task_id}")
                lines.append(f"- **Prompt Config**: {r.prompt_config}")
                lines.append(f"- **Model**: {r.model}")
                if r.usage:
                    lines.append(f"- **Tokens**: {r.usage.get('total_tokens', 0)}")
                lines.append(f"- **Latency**: {r.latency_ms:.2f}ms" if r.latency_ms else "- **Latency**: N/A")
                lines.append(f"- **Content**: {r.content[:100]}..." if r.content and len(r.content) > 100 else f"- **Content**: {r.content}")
                lines.append("")
            if len(success_results) > 5:
                lines.append(f"*... and {len(success_results) - 5} more successful results*")
                lines.append("")

        # Error results
        error_results = [r for r in result.results if r.error is not None]
        if error_results:
            lines.append("## Errors")
            lines.append("")
            lines.append(f"Total: {len(error_results)} errors")
            lines.append("")
            for r in error_results:
                lines.append(f"### {r.task_id}")
                lines.append(f"- **Prompt Config**: {r.prompt_config}")
                lines.append(f"- **Error**: {r.error}")
                lines.append(f"- **Timestamp**: {r.timestamp.isoformat()}")
                lines.append("")

        return "\n".join(lines)

    def save_json(self, result, filepath: str):
        """Save ExperimentResult as JSON file

        Args:
            result: ExperimentResult object
            filepath: Path to save JSON file
        """
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.to_json(result))

    def save_markdown(self, result, filepath: str):
        """Save ExperimentResult as Markdown file

        Args:
            result: ExperimentResult object
            filepath: Path to save Markdown file
        """
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.to_markdown(result))

    def _format_task_result(self, task_result) -> Dict[str, Any]:
        """Format a single TaskResult for output

        Args:
            task_result: TaskResult object

        Returns:
            Dictionary with task result data
        """
        formatted = {
            "task_id": task_result.task_id,
            "prompt_config": task_result.prompt_config,
            "timestamp": task_result.timestamp.isoformat(),
        }

        # Success case
        if task_result.error is None:
            formatted.update({
                "status": "success",
                "content": task_result.content,
                "deliverable_text": task_result.deliverable_text,
                "deliverable_files": task_result.deliverable_files or [],
                "model": task_result.model,
                "usage": task_result.usage,
                "latency_ms": round(task_result.latency_ms, 2) if task_result.latency_ms else None,
            })
        # Error case
        else:
            formatted.update({
                "status": "error",
                "error": task_result.error,
                "content": None,
                "deliverable_text": None,
                "deliverable_files": [],
                "model": None,
                "usage": None,
                "latency_ms": None,
            })

        return formatted

    def _calculate_duration(self, started_at: datetime, completed_at: datetime = None) -> float:
        """Calculate duration in seconds

        Args:
            started_at: Start timestamp
            completed_at: End timestamp (optional)

        Returns:
            Duration in seconds, or None if completed_at is None
        """
        if completed_at is None:
            return None
        return (completed_at - started_at).total_seconds()
