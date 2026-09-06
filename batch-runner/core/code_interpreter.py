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

Requires: Azure OpenAI with the Responses API. Which API version that is
gets decided by whoever builds the client this runner is handed — this
module takes no version of its own, so there is one place to look rather
than two that can drift apart. The comparison pins the version it expects
in its plan, and core.execution_envelope_preflight holds that pinned string
against the client-code constants before a run starts.

See https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/code-interpreter?view=foundry-classic&tabs=python

"""

import inspect
import re
from pathlib import Path
from typing import Optional

from core.azure_ai_clients import AzureAIWorkload, validate_client_capabilities
from core.config import DEFAULT_TOKENS
from core.prompt_loader import load_prompt, render_prompt
from core.execution_envelope_observed import (
    API_FAMILY_RESPONSES,
    RecordsItsFirstRequest,
)
from core.execution_environment_readiness import ENVIRONMENT_AZURE_CODE_INTERPRETER
from core.shared_first_request import SHARED_PROMPT_NAME, build_shared_task_text
from core.file_preview import build_file_structure_info
from core.reference_integrity import open_verified_reference


#: What a provider's own error code may be made of before it is allowed
#: into a redacted message: letters, digits and underscore, nothing else.
#: Real codes look like ``PermissionDenied``, ``AuthorizationFailed``,
#: ``DeploymentNotFound`` or ``insufficient_quota``. An endpoint, an account
#: name, a deployment name, a file path or a sentence of prose all need a
#: dot, a dash, a slash, a colon or a space, so none of them can get through
#: this. That is the whole reason the allow-list is a shape and not a
#: blocklist of things to strip out.
_PROVIDER_CODE_SHAPE = re.compile(r"\A[A-Za-z0-9_]{1,64}\Z")

#: Where a refusal's own code is looked for, in the order it is preferred.
#: The first pair is what the OpenAI SDK lifts out of a JSON body onto the
#: exception itself. The second pair is read back out of the body, because
#: Azure nests its code one level down under ``error`` and the SDK leaves the
#: attributes ``None`` in that case. Looking in the body as well is what makes
#: this useful against a real Azure refusal rather than only a synthetic one.
_PROVIDER_CODE_ATTRIBUTES = ("code", "type")
_PROVIDER_CODE_BODY_KEYS = ("code", "type")


def _provider_code_of(value: object) -> Optional[str]:
    """Return ``value`` when it is code-shaped, and otherwise nothing."""
    if isinstance(value, str) and _PROVIDER_CODE_SHAPE.match(value):
        return value
    return None


def _provider_error_classification(exc: BaseException) -> str:
    """Say what a provider refusal was, without saying who refused it.

    Exactly two things are ever taken from the exception:

    * the HTTP status, and only when it is a whole number a status can be;
    * the provider's own error code, and only when it is code-shaped by
      ``_PROVIDER_CODE_SHAPE``.

    The message, the request, the response headers and the body itself are
    never carried into the result. So a redacted message gains the one thing
    an operator needs to act — *what* was refused — and still cannot name an
    endpoint, an account, a project or a deployment.

    Every read is guarded, because these are attributes on somebody else's
    exception and a property is free to raise. A classification that cannot
    be worked out is simply absent; it never replaces the class name.
    """
    parts: list[str] = []

    try:
        status = getattr(exc, "status_code", None)
    except Exception:
        status = None
    if isinstance(status, int) and 100 <= status <= 599:
        parts.append(f"http {status}")

    code = None
    for attribute in _PROVIDER_CODE_ATTRIBUTES:
        try:
            code = _provider_code_of(getattr(exc, attribute, None))
        except Exception:
            code = None
        if code is not None:
            break
    if code is None:
        try:
            body = getattr(exc, "body", None)
        except Exception:
            body = None
        nested = body.get("error") if isinstance(body, dict) else None
        for holder in (body, nested):
            if not isinstance(holder, dict):
                continue
            for key in _PROVIDER_CODE_BODY_KEYS:
                code = _provider_code_of(holder.get(key))
                if code is not None:
                    break
            if code is not None:
                break
    if code is not None:
        parts.append(f"code {code}")

    return ", ".join(parts)


def _redacted_provider_error_message(exc: BaseException) -> str:
    """The one sentence a redacted provider failure is allowed to say."""
    classification = _provider_error_classification(exc)
    error_type = type(exc).__name__
    if classification:
        return (
            f"Code Interpreter provider error "
            f"({error_type}, {classification})"
        )
    return f"Code Interpreter provider error ({error_type})"


def _raise_redacted_provider_error(message: str):
    raise RuntimeError(message) from None


class _CodeInterpreterProviderCallProxy:
    """Delegate nested SDK calls while replacing provider exceptions."""

    def __init__(self, target) -> None:
        self._target = target

    def _get_raw_attribute(self, name: str):
        try:
            value = getattr(self._target, name)
        except Exception as exc:
            message = _redacted_provider_error_message(exc)
        else:
            return value
        _raise_redacted_provider_error(message)

    def __getattr__(self, name: str):
        return _CodeInterpreterProviderCallProxy(
            self._get_raw_attribute(name)
        )

    def __call__(self, *args, **kwargs):
        try:
            result = self._target(*args, **kwargs)
        except Exception as exc:
            message = _redacted_provider_error_message(exc)
        else:
            return result
        _raise_redacted_provider_error(message)


def _close_sync_resources(resources: tuple[tuple[str, object | None], ...]) -> None:
    first_error: BaseException | None = None
    seen: set[int] = set()
    for role, resource in resources:
        if resource is None or id(resource) in seen:
            continue
        seen.add(id(resource))
        close = getattr(resource, "close", None)
        if not callable(close):
            continue
        try:
            if inspect.iscoroutinefunction(close):
                raise RuntimeError(
                    f"sync Code Interpreter lifecycle does not support async {role} close"
                )
            result = close()
            if inspect.isawaitable(result):
                if inspect.iscoroutine(result):
                    result.close()
                raise RuntimeError(
                    f"sync Code Interpreter lifecycle does not support async {role} close"
                )
        except BaseException as exc:
            if first_error is None:
                first_error = exc
    if first_error is not None:
        raise first_error


class CodeInterpreterRunner(RecordsItsFirstRequest):
    """Synchronous Code Interpreter runner; instances are not thread-safe."""

    #: This run place is the one that does not send chat completions, which is
    #: itself a declared uncontrolled difference rather than something the
    #: shared first request removes.
    OBSERVED_API_FAMILY = API_FAMILY_RESPONSES
    OBSERVED_RUN_PLACE = ENVIRONMENT_AZURE_CODE_INTERPRETER

    #: Whether this run place opens a new request for each turn the model
    #: takes. ``False`` here: ``run`` issues exactly one ``responses.create``
    #: per attempt, with the code interpreter attached to that same call, so
    #: however many times the service returns to the model with a tool result,
    #: it happens inside the one request and under the one
    #: ``max_output_tokens`` sent with it.
    #:
    #: Read by core/execution_envelope_preflight.py, which holds the cost
    #: sum's ``output_tokens_capped_per_attempt`` against it. That figure
    #: decides whether an attempt is billed for one answer or for one per
    #: turn, so claiming a single cap where the caller really sends a fresh
    #: one each turn divides the bill by the number of turns.
    SENDS_A_FRESH_REQUEST_PER_TURN = False

    #: Which prompt sections this run place fills from the reference files.
    #: Only the structure summary: ``run`` calls ``build_file_structure_info``
    #: at line 208 and prepends it, and nothing else here puts file content
    #: into the prompt. The files themselves go up as container attachments
    #: (``_upload_reference_files`` → ``container_cfg["file_ids"]``, lines
    #: 220-226); the model reads them by running code, so their bytes arrive
    #: as tool results inside the request rather than as prompt text, and are
    #: already priced by ``max_tool_result_tokens_per_turn`` and the
    #: carried-forward input assumption.
    #:
    #: Read by core/execution_envelope_preflight.py, which asks
    #: core/file_preview.py what these sections can add per file and holds the
    #: answer against the cost sum's ``REFERENCE_FILE_CHARACTER_CAP``. Dropping
    #: a section from this tuple lowers what the plan is required to cover, so
    #: it must be dropped from the code first.
    REFERENCE_FILE_PROMPT_SECTIONS = ("file_structure",)

    #: Which prompt sections this run place puts in its **first** request past
    #: the rendered prompt and the reference files. None: this runner builds
    #: its request from ``render_prompt`` and the structure summary alone, and
    #: has no ``_augment_prompt``. Empty is a *claim*, not an omission — the
    #: preflight refuses a run place that declares nothing, because nothing
    #: looking is not the same as the claim holding.
    FIRST_REQUEST_EXTRA_SECTIONS: tuple[str, ...] = ()

    DEFAULT_PROMPT = "code_interpreter_occupation_codegen"

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        prompt_name: Optional[str] = None,
        max_completion_tokens: Optional[int] = None,
        *,
        client=None,
        redact_provider_errors: bool = False,
        shared_first_request: bool = False,
    ):
        self._closed = False
        self._uploaded_file_ids: set = set()
        self.redact_provider_errors = redact_provider_errors
        self.shared_first_request = bool(shared_first_request)
        if self.shared_first_request and (prompt_name or None) != SHARED_PROMPT_NAME:
            raise ValueError(
                "shared_first_request needs prompt_name="
                f"{SHARED_PROMPT_NAME!r}; got {prompt_name!r}. Sharing the "
                "sections while each run place keeps its own wording leaves "
                "the difference this setting exists to remove"
            )
        if endpoint is not None:
            raise ValueError(
                "endpoint overrides are forbidden; use a typed project route"
            )
        if api_key is not None:
            raise ValueError("static Azure AI API keys are forbidden")
        if client is None:
            raise ValueError(
                "typed Azure AI Code Interpreter client is required"
            )
        validate_client_capabilities(
            client,
            AzureAIWorkload.CODE_INTERPRETER,
        )
        self.client = (
            _CodeInterpreterProviderCallProxy(client)
            if self.redact_provider_errors
            else client
        )
        # Kept alongside the loaded data, as the other two runners do, so a
        # finished run can record *which file* this run place read rather than
        # only what the file said. The comparison's claim is that three run
        # places loaded one file; a name is what makes that claim checkable
        # from a run record.
        self.prompt_name = prompt_name or self.DEFAULT_PROMPT
        self.prompt_data = load_prompt(self.prompt_name)
        self.max_completion_tokens = (
            max_completion_tokens
            if max_completion_tokens is not None
            else DEFAULT_TOKENS["code_generation"]
        )

    # ── public ─────────────────────────────────────────────────────────

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._delete_uploaded_reference_files()

    def __enter__(self) -> "CodeInterpreterRunner":
        if self._closed:
            raise RuntimeError("Code Interpreter runner is closed")
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()

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
        if self._closed:
            return {
                "success": False,
                "text": "",
                "files": [],
                "error": "Code Interpreter runner is closed",
            }
        try:
            # Reset uploaded file tracking
            self._uploaded_file_ids = set()

            # Reference 파일 구조 자동 주입 (컬럼명 하드코딩 에러 방지)
            if self.shared_first_request:
                # One definition, three run places. The reference files are
                # still on the host at this point — they are uploaded a few
                # lines below — so the structure summary and the previews the
                # other two places build can be built here from the same files.
                task_prompt = build_shared_task_text(
                    task_prompt=task_prompt,
                    reference_files=reference_files or [],
                )
            else:
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
                max_output_tokens=self.max_completion_tokens,
                include=["code_interpreter_call.outputs"],
            )

            # 5. Extract text
            text_response = getattr(response, "output_text", "") or ""

            # 6. Collect output files (outputs parsing + container scan fallback)
            output_files = self._collect_output(response, verbose=verbose)

            result = {
                "success": True,
                "text": text_response,
                "files": output_files,
            }
            self._record_first_request(
                client=self.client,
                requested_model=model,
                system_message=rendered["system_message"],
                user_prompt=rendered["user_prompt"],
                response=response,
                reference_files=reference_files,
            )
            return self._with_observation(result)

        except Exception as exc:
            error = str(exc)
            return {
                "success": False,
                "text": "",
                "files": [],
                "error": error,
            }
        finally:
            self._delete_uploaded_reference_files()

    # ── private ────────────────────────────────────────────────────────

    def _upload_reference_files(self, reference_files: Optional[list]) -> list:
        """Upload local files and return list of file IDs."""
        if not reference_files:
            return []

        file_ids = []
        for path in reference_files:
            with open_verified_reference(path) as (reference_file, _verified):
                uploaded = self.client.files.create(
                    file=(Path(path).name, reference_file),
                    purpose="assistants",
                )
            file_ids.append(uploaded.id)
            self._uploaded_file_ids.add(uploaded.id)
        return file_ids

    def _delete_uploaded_reference_files(self) -> None:
        """Best-effort removal of provider-side input files after one task."""
        for file_id in sorted(self._uploaded_file_ids):
            try:
                self.client.files.delete(file_id)
            except Exception as exc:
                if self.redact_provider_errors:
                    print(
                        f"      ⚠️  Input file cleanup failed ({file_id}) "
                        f"({type(exc).__name__})"
                    )
                else:
                    print(f"      ⚠️  Input file cleanup failed ({file_id}): {exc}")
        self._uploaded_file_ids.clear()

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
            except Exception as exc:
                if self.redact_provider_errors:
                    print(
                        f"      ⚠️  Container download failed ({file_id}), "
                        f"trying files API ({type(exc).__name__})"
                    )
                else:
                    print(
                        f"      ⚠️  Container download failed ({file_id}), "
                        f"trying files API: {exc}"
                    )

        # Strategy 2: Files API fallback
        try:
            content_resp = self.client.files.content(file_id)
            return content_resp.read() if hasattr(content_resp, "read") else content_resp
        except Exception as exc:
            if self.redact_provider_errors:
                print(
                    f"      ⚠️  Files API download also failed ({file_id}) "
                    f"({type(exc).__name__})"
                )
            else:
                print(f"      ⚠️  Files API download also failed ({file_id}): {exc}")

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
                print("      [DEBUG] response.output is empty or missing")
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
                print("      [DEBUG] No files from strategies 1/2. Trying container scan.")
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

                except Exception as exc:
                    if self.redact_provider_errors:
                        print(
                            f"      \u26a0\ufe0f  Container scan failed ({container_id}) "
                            f"({type(exc).__name__})"
                        )
                    else:
                        print(
                            f"      \u26a0\ufe0f  Container scan failed "
                            f"({container_id}): {exc}"
                        )

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
