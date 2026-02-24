"""Result Collector for LLM experiments

Collects and manages experiment results from LLM API calls.

Usage:
    from core.result_collector import ResultCollector

    collector = ResultCollector(
        experiment_id="exp001",
        condition_name="baseline",
        model="gpt-5.2-chat"
    )

    # Add successful result
    response, latency_ms = complete(client, model, messages)
    collector.add(task, prompt_config="baseline", response=response, latency_ms=latency_ms)

    # Add error
    collector.add_error(task, prompt_config="baseline", error="API timeout")

    # Finalize
    result = collector.finalize()
    print(f"Success: {result.success_count}, Errors: {result.error_count}")
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from core.data_loader import GDPValTask


@dataclass
class TaskResult:
    """Result from a single task execution

    Attributes:
        task_id: Task identifier
        prompt_config: Prompt configuration name (e.g., "baseline", "visual_inspection")
        task: Original GDPValTask object (for accessing sector, occupation, etc.)
        content: LLM response content (None if error)
        model: Model name from API response
        usage: Token usage dict (prompt_tokens, completion_tokens, total_tokens)
        latency_ms: Response latency in milliseconds
        timestamp: When the result was recorded
        error: Error message (None if success)
        raw_response: Raw API response for debugging (optional)
        deliverable_text: Meta description of generated deliverables for evaluators
        deliverable_files: List of relative paths to generated files under deliverable_files/
    """
    task_id: str
    prompt_config: str
    task: Optional[Any] = None  # GDPValTask
    content: Optional[str] = None
    model: Optional[str] = None
    usage: Optional[dict] = None
    latency_ms: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None
    raw_response: Optional[dict] = None
    deliverable_text: Optional[str] = None
    deliverable_files: Optional[List[str]] = field(default_factory=list)


@dataclass
class ExperimentResult:
    """Collection of results from an experiment run

    Attributes:
        experiment_id: Unique experiment identifier
        condition_name: Experimental condition (e.g., "baseline", "treatment_a")
        model: Model name
        results: List of task results
        started_at: Experiment start time
        completed_at: Experiment completion time (None until finalized)
    """
    experiment_id: str
    condition_name: str
    model: str
    results: List[TaskResult]
    started_at: datetime
    completed_at: Optional[datetime] = None

    @property
    def success_count(self) -> int:
        """Count of successful task executions"""
        return len([r for r in self.results if r.error is None])

    @property
    def error_count(self) -> int:
        """Count of failed task executions"""
        return len([r for r in self.results if r.error is not None])

    @property
    def total_count(self) -> int:
        """Total number of task results"""
        return len(self.results)

    @property
    def total_tokens(self) -> int:
        """Sum of all tokens used (successful tasks only)"""
        return sum(
            r.usage.get("total_tokens", 0)
            for r in self.results
            if r.usage is not None
        )

    @property
    def avg_latency_ms(self) -> float:
        """Average latency across successful tasks"""
        latencies = [r.latency_ms for r in self.results if r.latency_ms is not None]
        return sum(latencies) / len(latencies) if latencies else 0.0


class ResultCollector:
    """Collects results during an experiment run

    Example:
        collector = ResultCollector("exp001", "baseline", "gpt-5.2-chat")

        for task in tasks:
            try:
                response, latency_ms = complete(client, model, messages)
                collector.add(task, "baseline", response, latency_ms)
            except Exception as e:
                collector.add_error(task, "baseline", str(e))

        result = collector.finalize()
    """

    def __init__(self, experiment_id: str, condition_name: str, model: str):
        """Initialize collector

        Args:
            experiment_id: Unique experiment identifier
            condition_name: Experimental condition name
            model: Model name (deployment name)
        """
        self.experiment = ExperimentResult(
            experiment_id=experiment_id,
            condition_name=condition_name,
            model=model,
            results=[],
            started_at=datetime.utcnow()
        )

    def add(
        self,
        task: Any,
        prompt_config: str,
        response: Any,
        latency_ms: float,
        save_raw: bool = False
    ):
        """Add a successful task result

        Args:
            task: GDPValTask object (must have task_id attribute)
            prompt_config: Prompt configuration name
            response: OpenAI ChatCompletion response object
            latency_ms: Response latency in milliseconds
            save_raw: Whether to save raw response (for debugging)
        """
        self.experiment.results.append(TaskResult(
            task_id=task.task_id,
            prompt_config=prompt_config,
            task=task,
            content=response.choices[0].message.content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            latency_ms=latency_ms,
            raw_response=response.model_dump() if save_raw else None,
            deliverable_text=getattr(task, 'deliverable_text', None) or None,
            deliverable_files=getattr(task, 'deliverable_files', None) or [],
        ))

    def add_error(self, task: Any, prompt_config: str, error: str):
        """Add a failed task result

        Args:
            task: GDPValTask object (must have task_id attribute)
            prompt_config: Prompt configuration name
            error: Error message or exception string
        """
        self.experiment.results.append(TaskResult(
            task_id=task.task_id,
            prompt_config=prompt_config,
            task=task,
            error=error
        ))

    def finalize(self) -> ExperimentResult:
        """Finalize the experiment and return results

        Sets the completion timestamp and returns the ExperimentResult.
        After calling this, you should not add more results.

        Returns:
            ExperimentResult with all collected results
        """
        self.experiment.completed_at = datetime.utcnow()
        return self.experiment
