"""
Code Interpreter Runner for OpenAI/Azure OpenAI models.

Uses Azure OpenAI Responses API + Code Interpreter tool to safely generate files
in a sandboxed environment.

File handling:
  - Reference files: uploaded to auto-created container via container.file_ids
  - Output files: retrieved via three strategies:
      1) Parse code_interpreter_call.outputs for image-type outputs
      2) Check message content blocks for output_file references
      3) Fallback: scan container via containers.files.list/content API

Requires: Azure OpenAI with Responses API (api_version >= 2025-03-01-preview)

See https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/code-interpreter?view=foundry-classic&tabs=python

"""

import os
import re
from pathlib import Path
from typing import Optional

from openai import AzureOpenAI

from core.prompt_loader import load_prompt, render_prompt
from core.file_preview import build_file_structure_info


class CodeInterpreterRunner:
    """Azure OpenAI Responses API + Code Interpreter for file generation"""

    DEFAULT_PROMPT = "code_interpreter_occupation_codegen"

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        api_version: str = "2025-03-01-preview",
        prompt_name: Optional[str] = None,
    ):
        self.client = AzureOpenAI(
            api_key=api_key or os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_API_KEY"),
            azure_endpoint=endpoint or os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version=api_version,
        )
        # Load prompt template
        self.prompt_data = load_prompt(prompt_name or self.DEFAULT_PROMPT)
        # Track uploaded file IDs to distinguish input vs output
        self._uploaded_file_ids: set = set()

    # ── public ─────────────────────────────────────────────────────────

    def run(
        self,
        task_prompt: str,
        model: str,
        reference_files: Optional[list] = None,
        occupation: str = "professional",
        experiment_prompt: Optional[dict] = None,
        verbose: bool = False,
    ) -> dict:
        """
        Execute task using Code Interpreter.

        Args:
            task_prompt: The task instruction
            model: Model deployment name (e.g., "gpt-5.2-chat")
            reference_files: Optional list of local file paths to upload
            occupation: Professional role from task data
            experiment_prompt: Optional prompt overrides from experiment YAML
                Keys: system (str), prefix (str|None), body (str|None), suffix (str|None)
            verbose: Print detailed debug info about API response structure

        Returns:
            dict with keys: success, text, files, (error)
        """
        try:
            # Reset uploaded file tracking
            self._uploaded_file_ids = set()

            # Reference 파일 구조 자동 주입 (컬럼명 하드코딩 에러 방지)
            file_structure_info = build_file_structure_info(reference_files or [])
            if file_structure_info:
                task_prompt = file_structure_info + "\n\n" + task_prompt

            # 1. Render prompt from YAML template
            rendered = render_prompt(
                self.prompt_data,
                occupation=occupation,
                task_prompt=task_prompt,
                experiment_prompt=experiment_prompt,
            )

            # 2. Upload reference files → get file_ids for container
            file_ids = self._upload_reference_files(reference_files)

            # 3. Build container config
            container_cfg: dict = {"type": "auto"}
            if file_ids:
                container_cfg["file_ids"] = file_ids

            # 4. Call Responses API
            response = self.client.responses.create(
                model=model,
                instructions=rendered["system_message"],
                input=rendered["user_prompt"],
                tools=[{
                    "type": "code_interpreter",
                    "container": container_cfg,
                }],
                include=["code_interpreter_call.outputs"],
            )

            # 5. Extract text
            text_response = getattr(response, "output_text", "") or ""

            # 6. Collect output files (outputs parsing + container scan fallback)
            output_files = self._collect_output(response, verbose=verbose)

            return {
                "success": True,
                "text": text_response,
                "files": output_files,
            }

        except Exception as e:
            return {
                "success": False,
                "text": "",
                "files": [],
                "error": str(e),
            }

    # ── private ────────────────────────────────────────────────────────

    def _upload_reference_files(self, reference_files: Optional[list]) -> list:
        """Upload local files and return list of file IDs."""
        if not reference_files:
            return []

        file_ids = []
        for path in reference_files:
            try:
                with open(path, "rb") as f:
                    uploaded = self.client.files.create(file=f, purpose="assistants")
                    file_ids.append(uploaded.id)
                    self._uploaded_file_ids.add(uploaded.id)
            except Exception as e:
                print(f"      ⚠️  Upload failed ({path}): {e}")
        return file_ids

    def _download_file(self, file_id: str, container_id: str = None) -> Optional[bytes]:
        """Download file content with container API → files API fallback."""
        # Strategy 1: Container files API (preferred)
        if container_id:
            try:
                content_resp = self.client.containers.files.content.retrieve(
                    file_id=file_id,
                    container_id=container_id,
                )
                return content_resp.read() if hasattr(content_resp, "read") else content_resp
            except Exception as e:
                print(f"      ⚠️  Container download failed ({file_id}), trying files API: {e}")

        # Strategy 2: Files API fallback
        try:
            content_resp = self.client.files.content(file_id)
            return content_resp.read() if hasattr(content_resp, "read") else content_resp
        except Exception as e:
            print(f"      ⚠️  Files API download also failed ({file_id}): {e}")

        return None

    def _collect_output(self, response, verbose: bool = False) -> list:
        """
        Collect generated files from Code Interpreter response.

        Strategy 1: Parse code_interpreter_call outputs for image-type outputs
        Strategy 2: Check message content blocks for output_file references
        Strategy 3: Scan container via containers.files.list (fallback)
        """
        output_files = []
        if not hasattr(response, "output") or not response.output:
            if verbose:
                print(f"      [DEBUG] response.output is empty or missing")
            return output_files

        seen_file_ids: set = set()
        seen_containers: set = set()
        text_parts: list = []

        # ── Verbose: dump full response structure ──────────────────────────
        if verbose:
            print(f"      [DEBUG] response.output count: {len(response.output)}")
            # Also check response-level container_id
            resp_cid = getattr(response, "container_id", "MISSING")
            print(f"      [DEBUG] response.container_id: {resp_cid}")
            for i, item in enumerate(response.output):
                itype = getattr(item, "type", "MISSING")
                cid = getattr(item, "container_id", "MISSING")
                attrs = [a for a in dir(item) if not a.startswith("_") and not callable(getattr(item, a, None))]
                print(f"      [DEBUG] output[{i}]: type={itype}, container_id={cid}")
                print(f"      [DEBUG] output[{i}]: attrs={attrs}")
                outputs = getattr(item, "outputs", None)
                if outputs:
                    for j, out in enumerate(outputs):
                        otype = getattr(out, "type", "MISSING")
                        oattrs = [a for a in dir(out) if not a.startswith("_") and not callable(getattr(out, a, None))]
                        print(f"      [DEBUG]   outputs[{j}]: type={otype}, attrs={oattrs}")

        # ── Collect response-level container_id if present ────────────────
        resp_container_id = getattr(response, "container_id", None)
        if resp_container_id:
            seen_containers.add(resp_container_id)

        for item in response.output:
            item_type = getattr(item, "type", None)

            # ── Strategy 2: Message content blocks (output_file / text) ──
            if item_type == "message":
                for content_block in getattr(item, "content", []):
                    block_type = getattr(content_block, "type", None)
                    if block_type == "text":
                        text_parts.append(getattr(content_block, "text", ""))
                    elif block_type == "output_file":
                        fid = getattr(content_block, "file_id", None)
                        if fid and fid not in seen_file_ids and fid not in self._uploaded_file_ids:
                            seen_file_ids.add(fid)
                            fname = getattr(content_block, "filename", None) or f"output_{fid}"
                            print(f"      \U0001f4ce File in message: {fname}")
                            content = self._download_file(fid)
                            if content:
                                output_files.append({"filename": fname, "content": content})
                continue

            if item_type != "code_interpreter_call":
                continue

            container_id = getattr(item, "container_id", None)
            if container_id:
                seen_containers.add(container_id)

            # ── Strategy 1: Parse outputs field for image-type outputs ──
            # NOTE: Responses API outputs only contains "logs" (stdout) and "image" types.
            # "files" type does not exist — files must be retrieved via container scan (Strategy 3).
            outputs = getattr(item, "outputs", None) or []
            for output_item in outputs:
                if getattr(output_item, "type", None) == "image":
                    fid = getattr(output_item, "file_id", None)
                    if fid and fid not in seen_file_ids and fid not in self._uploaded_file_ids:
                        seen_file_ids.add(fid)
                        fname = getattr(output_item, "filename", None) or f"image_{fid}.png"
                        content = self._download_file(fid, container_id)
                        if content:
                            output_files.append({"filename": fname, "content": content})

        # ── Strategy 3: Container scan fallback (always try if no files collected) ──
        if not output_files:
            if verbose:
                print(f"      [DEBUG] No files from strategies 1/2. Trying container scan.")
                print(f"      [DEBUG] seen_containers: {seen_containers}")
            for container_id in seen_containers:
                try:
                    files_page = self.client.containers.files.list(container_id)
                    for cf in files_page.data:
                        cf_id = getattr(cf, "id", None)
                        # Skip input/reference files
                        if getattr(cf, "source", "") == "user":
                            continue
                        if cf_id in seen_file_ids or cf_id in self._uploaded_file_ids:
                            continue
                        seen_file_ids.add(cf_id)

                        fname = Path(cf.path).name if cf.path else f"output_{cf_id}"
                        print(f"      \U0001f5c2\ufe0f  Container scan found: {fname}")
                        content = self._download_file(cf_id, container_id)
                        if content:
                            output_files.append({"filename": fname, "content": content})

                except Exception as e:
                    print(f"      \u26a0\ufe0f  Container scan failed ({container_id}): {e}")

        # ── Warn: sandbox paths in text but no files collected ──
        if not output_files:
            full_text = getattr(response, "output_text", "") or " ".join(text_parts)
            if "sandbox:" in full_text or "/mnt/data/" in full_text:
                sandbox_paths = re.findall(r'sandbox:/mnt/data/([^\s\)\"\']+)', full_text)
                print(
                    "      \u26a0\ufe0f  No files collected but sandbox paths found in text. "
                    "The model saved files in sandbox without returning them as outputs."
                )
                if sandbox_paths:
                    print(f"      \u26a0\ufe0f  Files created in sandbox: {sandbox_paths}")
                if not seen_containers:
                    print(
                        "      \u26a0\ufe0f  container_id is None — try re-running with --verbose "
                        "to inspect response structure, or check API include params."
                    )

        return output_files
