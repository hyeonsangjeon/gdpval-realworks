"""HuggingFace Dataset Uploader

Uploads experiment results to HuggingFace for evals.openai.com submission.

Usage:
    from core.hf_uploader import HuggingFaceUploader

    uploader = HuggingFaceUploader(token=os.getenv("HF_TOKEN"))
    hf_url = uploader.upload_condition(
        experiment_id="exp001",
        condition_name="baseline",
        result=experiment_result,
        output_dir="results/exp001_a"
    )
    print(f"Uploaded to: {hf_url}")
"""

import os
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

try:
    from huggingface_hub import HfApi, create_repo
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False

from core.result_collector import ExperimentResult


class HuggingFaceUploader:
    """Upload experiment results to HuggingFace datasets

    Follows evals.openai.com requirements:
    - deliverable_text column with LLM response
    - deliverable_files column with file paths
    - deliverable_files/ directory with actual files
    """

    ORG = "gdpval-realwork"

    def __init__(self, token: Optional[str] = None):
        """Initialize HuggingFace uploader

        Args:
            token: HuggingFace API token (defaults to HF_TOKEN env var)

        Raises:
            ImportError: If huggingface_hub is not installed
            ValueError: If token is not provided
        """
        if not HF_AVAILABLE:
            raise ImportError(
                "huggingface_hub is not installed. "
                "Install it with: pip install huggingface_hub"
            )

        self.token = token or os.getenv("HF_TOKEN")
        if not self.token:
            raise ValueError(
                "HuggingFace token is required. "
                "Set HF_TOKEN environment variable or pass token parameter."
            )

        self.api = HfApi()

    def upload_condition(
        self,
        experiment_id: str,
        condition_name: str,
        result: ExperimentResult,
        output_dir: str,
    ) -> str:
        """Upload a single condition's results to HuggingFace

        Args:
            experiment_id: Experiment ID (e.g., "exp001")
            condition_name: Condition name (e.g., "baseline")
            result: ExperimentResult object
            output_dir: Local output directory with results

        Returns:
            HuggingFace dataset URL

        Example:
            >>> uploader = HuggingFaceUploader(token="hf_xxx")
            >>> url = uploader.upload_condition(
            ...     experiment_id="exp001",
            ...     condition_name="baseline",
            ...     result=result,
            ...     output_dir="results/exp001_a"
            ... )
            >>> print(url)
            https://huggingface.co/datasets/gdpval-realwork/exp001-baseline
        """
        # Normalize condition name (lowercase, replace spaces with hyphens)
        normalized_condition = condition_name.lower().replace(" ", "-").replace("_", "-")
        repo_id = f"{self.ORG}/{experiment_id}-{normalized_condition}"

        print(f"\n🤗 Uploading to HuggingFace: {repo_id}")

        # 1. Create repository
        print(f"   Creating repository...")
        try:
            create_repo(
                repo_id,
                repo_type="dataset",
                token=self.token,
                exist_ok=True,
                private=False,
            )
            print(f"   ✓ Repository created/verified")
        except Exception as e:
            raise RuntimeError(f"Failed to create repository: {e}")

        # 2. Prepare data in evals format
        print(f"   Preparing data in evals.openai.com format...")
        data_dir = Path(output_dir) / "hf_upload"
        data_dir.mkdir(parents=True, exist_ok=True)

        self._prepare_evals_format(result, data_dir)
        print(f"   ✓ Data prepared in {data_dir}")

        # 3. Upload data folder
        print(f"   Uploading data...")
        try:
            self.api.upload_folder(
                folder_path=str(data_dir),
                repo_id=repo_id,
                repo_type="dataset",
                token=self.token,
            )
            print(f"   ✓ Data uploaded")
        except Exception as e:
            raise RuntimeError(f"Failed to upload data: {e}")

        # 4. Generate and upload README
        print(f"   Generating dataset card...")
        readme = self._generate_dataset_card(
            experiment_id=experiment_id,
            condition_name=condition_name,
            result=result,
        )

        try:
            self.api.upload_file(
                path_or_fileobj=readme.encode("utf-8"),
                path_in_repo="README.md",
                repo_id=repo_id,
                repo_type="dataset",
                token=self.token,
            )
            print(f"   ✓ README uploaded")
        except Exception as e:
            raise RuntimeError(f"Failed to upload README: {e}")

        hf_url = f"https://huggingface.co/datasets/{repo_id}"
        print(f"   ✅ Upload complete: {hf_url}\n")

        return hf_url

    def _prepare_evals_format(self, result: ExperimentResult, output_dir: Path) -> None:
        """Prepare data in evals.openai.com format

        Creates:
        - data/train.jsonl with deliverable_text and deliverable_files columns
        - deliverable_files/ directory with LLM-generated files

        Args:
            result: ExperimentResult object
            output_dir: Output directory for prepared data
        """
        data_dir = output_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        deliverable_files_dir = output_dir / "deliverable_files"
        deliverable_files_dir.mkdir(parents=True, exist_ok=True)

        # Convert results to JSONL format
        jsonl_path = data_dir / "train.jsonl"

        with open(jsonl_path, "w", encoding="utf-8") as f:
            for task_result in result.results:
                # Get original task data
                task = task_result.task if task_result.task else {}

                # Base data from original task
                record = {
                    "task_id": task_result.task_id,
                    "sector": getattr(task, "sector", ""),
                    "occupation": getattr(task, "occupation", ""),
                    "task": getattr(task, "task", ""),
                    # Add deliverable fields required by evals.openai.com
                    "deliverable_text": task_result.content if task_result.content else "",
                    "deliverable_files": f"deliverable_files/{task_result.task_id}/",
                }

                # Write JSONL line
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

                # Create deliverable_files directory for this task
                task_files_dir = deliverable_files_dir / task_result.task_id
                task_files_dir.mkdir(parents=True, exist_ok=True)

                # Save response as text file
                if task_result.content:
                    response_file = task_files_dir / "response.txt"
                    response_file.write_text(task_result.content, encoding="utf-8")

    def _generate_dataset_card(
        self,
        experiment_id: str,
        condition_name: str,
        result: ExperimentResult,
    ) -> str:
        """Generate README.md dataset card

        Args:
            experiment_id: Experiment ID
            condition_name: Condition name
            result: ExperimentResult object

        Returns:
            README.md content as string
        """
        # Calculate statistics
        success_rate = (result.success_count / result.total_count * 100) if result.total_count > 0 else 0
        duration_seconds = (result.completed_at - result.started_at).total_seconds()

        return f"""---
license: mit
task_categories:
  - text-generation
  - question-answering
tags:
  - gdpval
  - llm-evaluation
  - benchmark
  - real-work
size_categories:
  - n<1K
---

# GDPVal Experiment: {experiment_id} - {condition_name}

This dataset contains results from a GDPVal experiment evaluating LLM performance on real expert work tasks.

## Experiment Details

- **Experiment ID**: {experiment_id}
- **Condition**: {condition_name}
- **Model**: {result.model}
- **Total Tasks**: {result.total_count}
- **Success Rate**: {success_rate:.1f}%
- **Total Tokens**: {result.total_tokens:,}
- **Avg Latency**: {result.avg_latency_ms:.2f}ms
- **Duration**: {duration_seconds:.1f}s
- **Completed**: {result.completed_at.strftime("%Y-%m-%d %H:%M:%S")} UTC

## Dataset Format

This dataset follows the evals.openai.com format with the following columns:

- `task_id`: Unique task identifier
- `sector`: Economic sector (e.g., "Finance and Insurance")
- `occupation`: Job occupation
- `task`: Task description
- `deliverable_text`: LLM response text
- `deliverable_files`: Path to deliverable files directory

## Links

- 📊 [GDPVal RealWork Dashboard](https://YOUR_USERNAME.github.io/gdpval-realwork)
- 📄 [GDPVal Paper](https://arxiv.org/abs/2510.04374)
- 🤗 [Original GDPVal Dataset](https://huggingface.co/datasets/openai/gdpval)

## Usage

```python
from datasets import load_dataset

dataset = load_dataset("gdpval-realwork/{experiment_id}-{condition_name.lower().replace(' ', '-')}")
```

## Citation

```bibtex
@misc{{gdpval2025,
  title={{Benchmark LLMs on Expert Work, Not Academic Tests}},
  author={{OpenAI}},
  year={{2025}},
  url={{https://arxiv.org/abs/2510.04374}}
}}

@misc{{gdpval-realwork,
  author={{Hyeonsang Jeon}},
  title={{GDPVal RealWork Experiments}},
  year={{2026}},
  publisher={{HuggingFace}},
  url={{https://huggingface.co/datasets/gdpval-realwork/{experiment_id}-{condition_name.lower().replace(' ', '-')}}}
}}
```

## License

MIT License
"""
