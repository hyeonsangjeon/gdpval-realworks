"""Evals.openai.com Submission

Submits experiment results to evals.openai.com for official grading.

Usage:
    from core.evals_submitter import EvalsSubmitter

    submitter = EvalsSubmitter(email="your@email.com")
    result = submitter.submit(
        dataset_url="https://huggingface.co/datasets/gdpval-realwork/exp001-baseline",
        model_name="gpt-4",
        experiment_id="exp001",
        condition_name="baseline"
    )
    print(f"Submission ID: {result['submission_id']}")
"""

import os
import json
import requests
from typing import Optional, Dict, Any
from datetime import datetime


class EvalsSubmitter:
    """Submit results to evals.openai.com

    Note: This is a placeholder implementation. The actual evals.openai.com
    submission process may involve:
    1. Web form submission
    2. Email notification
    3. API endpoint (if available)

    For now, this creates a submission record locally and provides
    instructions for manual submission.
    """

    # Placeholder - actual endpoint may be different
    EVALS_ENDPOINT = "https://evals.openai.com/api/submit"

    def __init__(self, email: Optional[str] = None):
        """Initialize evals submitter

        Args:
            email: Email address for receiving results (defaults to EMAIL env var)

        Raises:
            ValueError: If email is not provided
        """
        self.email = email or os.getenv("EMAIL")
        if not self.email:
            raise ValueError(
                "Email is required for evals submission. "
                "Set EMAIL environment variable or pass email parameter."
            )

    def submit(
        self,
        dataset_url: str,
        model_name: str,
        experiment_id: str,
        condition_name: str,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit experiment to evals.openai.com

        Args:
            dataset_url: HuggingFace dataset URL
            model_name: Model name (e.g., "gpt-4", "gpt-5.2-chat")
            experiment_id: Experiment ID (e.g., "exp001")
            condition_name: Condition name (e.g., "baseline")
            api_key: Optional OpenAI API key (defaults to OPENAI_API_KEY env var)

        Returns:
            Dictionary with submission result:
            {
                "status": "submitted" | "pending_manual" | "error",
                "submission_id": str,
                "message": str,
                "submitted_at": str,
                "email": str,
                "dataset_url": str,
                "model_name": str
            }

        Example:
            >>> submitter = EvalsSubmitter(email="user@example.com")
            >>> result = submitter.submit(
            ...     dataset_url="https://huggingface.co/datasets/gdpval-realwork/exp001-baseline",
            ...     model_name="gpt-4",
            ...     experiment_id="exp001",
            ...     condition_name="baseline"
            ... )
            >>> print(result["status"])
            pending_manual
        """
        print(f"\n📧 Preparing evals.openai.com submission...")
        print(f"   Email: {self.email}")
        print(f"   Dataset: {dataset_url}")
        print(f"   Model: {model_name}")

        # Generate submission ID
        submission_id = f"{experiment_id}_{condition_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        # Prepare submission data
        submission_data = {
            "dataset_url": dataset_url,
            "model_name": model_name,
            "email": self.email,
            "experiment_id": experiment_id,
            "condition_name": condition_name,
            "submitted_at": datetime.utcnow().isoformat(),
        }

        # Try API submission (if endpoint is available)
        api_result = self._try_api_submission(submission_data, api_key)
        if api_result.get("success"):
            return {
                "status": "submitted",
                "submission_id": submission_id,
                "message": "Successfully submitted to evals.openai.com API",
                "submitted_at": submission_data["submitted_at"],
                "email": self.email,
                "dataset_url": dataset_url,
                "model_name": model_name,
            }

        # Fallback: Manual submission instructions
        print(f"\n📋 Manual submission required:")
        print(f"   1. Visit: https://evals.openai.com")
        print(f"   2. Submit the following:")
        print(f"      - Dataset URL: {dataset_url}")
        print(f"      - Model: {model_name}")
        print(f"      - Email: {self.email}")
        print(f"   3. You will receive results via email")

        # Save submission record locally
        self._save_submission_record(submission_id, submission_data)

        return {
            "status": "pending_manual",
            "submission_id": submission_id,
            "message": "Manual submission required. See console output for instructions.",
            "submitted_at": submission_data["submitted_at"],
            "email": self.email,
            "dataset_url": dataset_url,
            "model_name": model_name,
        }

    def _try_api_submission(
        self, submission_data: Dict[str, Any], api_key: Optional[str]
    ) -> Dict[str, Any]:
        """Try to submit via API (if available)

        Args:
            submission_data: Submission data dictionary
            api_key: Optional OpenAI API key

        Returns:
            Dictionary with success status and response
        """
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {"success": False, "message": "No API key available"}

        try:
            # Note: This is a placeholder. Actual API endpoint may be different
            # or may not exist. Check OpenAI Evals documentation for details.
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            response = requests.post(
                self.EVALS_ENDPOINT,
                json=submission_data,
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                return {"success": True, "response": response.json()}
            else:
                return {
                    "success": False,
                    "message": f"API returned {response.status_code}",
                }

        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"API request failed: {e}"}

    def _save_submission_record(
        self, submission_id: str, submission_data: Dict[str, Any]
    ) -> None:
        """Save submission record to local file

        Args:
            submission_id: Unique submission ID
            submission_data: Submission data dictionary
        """
        # Create submissions directory
        submissions_dir = os.path.expanduser("~/.gdpval/submissions")
        os.makedirs(submissions_dir, exist_ok=True)

        # Save submission record
        record_path = os.path.join(submissions_dir, f"{submission_id}.json")
        with open(record_path, "w", encoding="utf-8") as f:
            json.dump(submission_data, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Submission record saved: {record_path}")

    def get_submission_status(self, submission_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a previous submission

        Args:
            submission_id: Submission ID to check

        Returns:
            Submission data dictionary if found, None otherwise
        """
        submissions_dir = os.path.expanduser("~/.gdpval/submissions")
        record_path = os.path.join(submissions_dir, f"{submission_id}.json")

        if not os.path.exists(record_path):
            return None

        with open(record_path, "r", encoding="utf-8") as f:
            return json.load(f)
