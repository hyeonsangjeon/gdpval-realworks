"""Rubric-based grading engine.

Routes rubric items to deterministic prechecks where possible, otherwise to an
Azure OpenAI Responses API judge. Evidence is mandatory for judge verdicts.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

import openpyxl
from PyPDF2 import PdfReader
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from core.file_reader import read_reference_file
from core.rubric_loader import RubricItem, TaskRubric

logger = logging.getLogger(__name__)

Verdict = Literal["pass", "partial", "fail", "judge_error"]
DecidedBy = Literal["precheck", "judge"]

PRECHECK_PATTERNS: list[tuple[str, str]] = [
    (
        r"\b(file|workbook|document|pdf|deliverable).*(named|basename|filename|extension|exists?|is a|is an|single|exactly one)\b",
        "file_exists_or_name",
    ),
    (
        r"\b(\.xlsx|\.xls|\.xlsm|\.pdf|\.docx?|\.pptx?|\.txt|\.csv|\.json|\.wav|\.mp3|\.mp4|\.png|\.jpg)\b",
        "file_extension",
    ),
    (r"\bworksheet\b.*(named|exactly|contains|present)", "worksheet_name"),
    (
        r"\b(at least|exactly|no more than|fewer than)\s+\d+\b.*(rows?|columns?|pages?|sheets?|sections?|items?|files?)\b",
        "count_check",
    ),
    (r"\bpage(s)?\b.*\b(at least|exactly)\s+\d+\b", "page_count"),
    (r"\bword(s)?\b.*\b(at least|exactly|approximately)\s+\d+\b", "word_count"),
]


@dataclass
class ItemGrade:
    rubric_item_id: str
    criterion: str
    max_score: int
    awarded_score: float
    verdict: Verdict
    decided_by: DecidedBy
    required: Optional[bool]
    evidence: str
    judge_confidence: Optional[float] = None
    judge_latency_ms: Optional[float] = None
    precheck_pattern_id: Optional[str] = None
    judge_raw_response: Optional[str] = None


@dataclass
class TaskGrade:
    task_id: str
    sector: str
    occupation: str
    items: list[ItemGrade]
    total_awarded: float
    total_max: int
    pct: float
    critical_fail: bool
    gold_referenced: bool
    judge_call_count: int
    precheck_count: int
    judge_total_latency_ms: float
    judge_input_tokens: int
    judge_output_tokens: int
    error: Optional[str] = None


class Grader:
    def __init__(self, config: dict, rubric_loader):
        self.config = config
        self.rubric_loader = rubric_loader

        provider = self.config.get("judge", {}).get("provider", "azure_openai")
        if provider != "azure_openai":
            raise NotImplementedError(f"Unsupported judge provider: {provider}")

        endpoint_env = self.config["judge"]["endpoint_env"]
        endpoint = os.getenv(endpoint_env)
        if not endpoint:
            raise ValueError(f"Missing Azure endpoint env var: {endpoint_env}")

        credential = DefaultAzureCredential()
        token_provider = get_bearer_token_provider(
            credential, "https://cognitiveservices.azure.com/.default"
        )

        timeout = int(self.config.get("judge", {}).get("timeout_sec", 600))
        api_version = self.config.get("judge", {}).get(
            "api_version", "2025-04-01-preview"
        )
        self.model = self.config["judge"]["model"]
        self.client = AzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=token_provider,
            api_version=api_version,
            timeout=timeout,
        )

        self.prompt_template = self._read_prompt_template(self.config["prompt"]["template"])
        self.prompt_version = self._extract_prompt_version(self.prompt_template)
        self._min_delay_seconds = (
            float(self.config.get("tpm_guard", {}).get("min_delay_ms_between_calls", 0))
            / 1000.0
        )
        self._last_judge_call_at: float | None = None

    @staticmethod
    def _classify(item: RubricItem) -> tuple[str, Optional[str]]:
        for pattern, pid in PRECHECK_PATTERNS:
            if re.search(pattern, item.criterion, re.I):
                return "precheck", pid
        return "judge", None

    def grade_task(self, task: TaskRubric, deliverable_dir: str) -> TaskGrade:
        deliverable_path = Path(deliverable_dir)
        files = self._list_files(deliverable_path)

        no_deliverables = not deliverable_path.exists() or not files
        items: list[ItemGrade] = []
        judge_call_count = 0
        precheck_count = 0
        judge_total_latency_ms = 0.0
        judge_input_tokens = 0
        judge_output_tokens = 0

        for item in task.rubric_items:
            mode, pattern_id = self._classify(item)
            if no_deliverables:
                if mode == "judge":
                    ig = self._absent_judge_item(item)
                    judge_call_count += 1
                else:
                    ig = self._fail_precheck_item(item, pattern_id, "deliverable absent")
                    precheck_count += 1
                items.append(ig)
                continue

            if mode == "precheck":
                precheck_count += 1
                pre = self._run_precheck(pattern_id, item, files)
                if pre is None:
                    ig, in_tok, out_tok = self._judge(task, item, files)
                    judge_call_count += 1
                    judge_total_latency_ms += ig.judge_latency_ms or 0.0
                    judge_input_tokens += in_tok
                    judge_output_tokens += out_tok
                else:
                    verdict, evidence = pre
                    ig = self._to_item_grade_from_precheck(
                        item, pattern_id, verdict, evidence
                    )
            else:
                ig, in_tok, out_tok = self._judge(task, item, files)
                judge_call_count += 1
                judge_total_latency_ms += ig.judge_latency_ms or 0.0
                judge_input_tokens += in_tok
                judge_output_tokens += out_tok
            items.append(ig)

        grade = self._aggregate(items, task)
        grade.judge_call_count = judge_call_count
        grade.precheck_count = precheck_count
        grade.judge_total_latency_ms = round(judge_total_latency_ms, 2)
        grade.judge_input_tokens = judge_input_tokens
        grade.judge_output_tokens = judge_output_tokens
        if no_deliverables:
            grade.error = "no_deliverables"
        return grade

    def _list_files(self, deliverable_dir: Path) -> list[Path]:
        if not deliverable_dir.exists() or not deliverable_dir.is_dir():
            return []
        return sorted([p for p in deliverable_dir.rglob("*") if p.is_file()])

    def _run_precheck(
        self,
        pattern_id: Optional[str],
        item: RubricItem,
        files: list[Path],
    ) -> Optional[tuple[Verdict, str]]:
        if not pattern_id:
            return None

        handlers = {
            "file_exists_or_name": self._precheck_file_exists_or_name,
            "file_extension": self._precheck_file_extension,
            "worksheet_name": self._precheck_worksheet_name,
            "count_check": self._precheck_count_check,
            "page_count": self._precheck_page_count,
            "word_count": self._precheck_word_count,
        }
        handler = handlers.get(pattern_id)
        if not handler:
            return None

        try:
            return handler(item, files)
        except Exception as exc:
            logger.warning(
                "Precheck failed for %s (%s): %s", item.rubric_item_id, pattern_id, exc
            )
            return None

    def _precheck_file_exists_or_name(
        self,
        item: RubricItem,
        files: list[Path],
    ) -> Optional[tuple[Verdict, str]]:
        criterion = item.criterion
        named_match = re.search(
            r"(?:basename|named|filename)\s*(?:is|=)?\s*['\"]([^'\"]+)['\"]",
            criterion,
            re.I,
        )
        if named_match:
            expected = named_match.group(1).strip().lower()
            for f in files:
                if f.stem.lower() == expected or f.name.lower() == expected:
                    return "pass", f"Filename observed: '{f.name}'"
            return "fail", f"Expected basename '{expected}' not found"

        if files:
            return "pass", f"Deliverable files present ({len(files)})"
        return "fail", "No deliverable files found"

    def _precheck_file_extension(
        self,
        item: RubricItem,
        files: list[Path],
    ) -> Optional[tuple[Verdict, str]]:
        exts = set(
            re.findall(
                r"\.(xlsx|xls|xlsm|pdf|docx?|pptx?|txt|csv|json|wav|mp3|mp4|png|jpg)",
                item.criterion,
                re.I,
            )
        )
        if not exts:
            return None
        expected_exts = {f".{x.lower()}" for x in exts}
        observed = {f.suffix.lower() for f in files}
        if observed.intersection(expected_exts):
            ext = sorted(observed.intersection(expected_exts))[0]
            return "pass", f"Observed required extension: '{ext}'"
        return "fail", f"Required extension not found: {sorted(expected_exts)}"

    def _precheck_worksheet_name(
        self,
        item: RubricItem,
        files: list[Path],
    ) -> Optional[tuple[Verdict, str]]:
        m = re.search(
            r"worksheet\s+(?:named|name)\s*['\"]([^'\"]+)['\"]",
            item.criterion,
            re.I,
        )
        if not m:
            return None
        target = m.group(1).strip().lower()
        xlsx_files = [f for f in files if f.suffix.lower() in {".xlsx", ".xlsm"}]
        if not xlsx_files:
            return "fail", "No Excel workbook found"

        for xf in xlsx_files:
            wb = openpyxl.load_workbook(str(xf), data_only=True)
            names = {n.lower() for n in wb.sheetnames}
            if target in names:
                return "pass", f"Worksheet '{m.group(1)}' present in {xf.name}"
        return "fail", f"Worksheet '{m.group(1)}' not found"

    def _precheck_count_check(
        self,
        item: RubricItem,
        files: list[Path],
    ) -> Optional[tuple[Verdict, str]]:
        m = re.search(
            r"(exactly|at least|no more than|fewer than)\s+(\d+)\s+files?",
            item.criterion,
            re.I,
        )
        if not m:
            return None
        mode = m.group(1).lower()
        expected = int(m.group(2))
        observed = len(files)
        ok = (
            (mode == "exactly" and observed == expected)
            or (mode == "at least" and observed >= expected)
            or (mode == "no more than" and observed <= expected)
            or (mode == "fewer than" and observed < expected)
        )
        if ok:
            return "pass", f"File count {observed} satisfies '{mode} {expected}'"
        return "fail", f"File count {observed} violates '{mode} {expected}'"

    def _precheck_page_count(
        self,
        item: RubricItem,
        files: list[Path],
    ) -> Optional[tuple[Verdict, str]]:
        m = re.search(r"page(?:s)?\b.*\b(at least|exactly)\s+(\d+)", item.criterion, re.I)
        if not m:
            return None
        mode = m.group(1).lower()
        expected = int(m.group(2))

        pdfs = [f for f in files if f.suffix.lower() == ".pdf"]
        if not pdfs:
            return None

        observed = len(PdfReader(str(pdfs[0])).pages)
        ok = (mode == "exactly" and observed == expected) or (
            mode == "at least" and observed >= expected
        )
        if ok:
            return "pass", f"PDF page count {observed} satisfies '{mode} {expected}'"
        return "fail", f"PDF page count {observed} violates '{mode} {expected}'"

    def _precheck_word_count(
        self,
        item: RubricItem,
        files: list[Path],
    ) -> Optional[tuple[Verdict, str]]:
        m = re.search(
            r"word(?:s)?\b.*\b(at least|exactly|approximately)\s+(\d+)",
            item.criterion,
            re.I,
        )
        if not m:
            return None
        mode = m.group(1).lower()
        expected = int(m.group(2))

        txt_candidates = [f for f in files if f.suffix.lower() in {".txt", ".docx"}]
        if not txt_candidates:
            return None

        text = read_reference_file(str(txt_candidates[0]))
        words = len(re.findall(r"\S+", text))
        if mode == "at least":
            ok = words >= expected
        elif mode == "exactly":
            ok = words == expected
        else:
            ok = abs(words - expected) <= max(10, int(expected * 0.1))

        if ok:
            return "pass", f"Word count {words} satisfies '{mode} {expected}'"
        return "fail", f"Word count {words} violates '{mode} {expected}'"

    def _judge(
        self, task: TaskRubric, item: RubricItem, files: list[Path]
    ) -> tuple[ItemGrade, int, int]:
        if not files:
            return self._absent_judge_item(item), 0, 0

        summary = self._summarize_deliverables(files)
        prompt = self._build_prompt(task, item, summary)

        retries = int(self.config.get("grader", {}).get("judge_max_retries", 1))
        for attempt in range(retries + 1):
            try:
                raw, latency_ms, input_tok, output_tok = self._call_judge(prompt)
            except Exception as exc:
                logger.warning(
                    "Judge call failed for %s after retries: %s",
                    item.rubric_item_id,
                    exc,
                )
                return (
                    ItemGrade(
                        rubric_item_id=item.rubric_item_id,
                        criterion=item.criterion,
                        max_score=item.score,
                        awarded_score=0.0,
                        verdict="judge_error",
                        decided_by="judge",
                        required=item.required,
                        evidence="judge_api_call_failed",
                        judge_confidence=None,
                        judge_latency_ms=0.0,
                        precheck_pattern_id=None,
                        judge_raw_response=str(exc) if self._save_raw() else None,
                    ),
                    0,
                    0,
                )
            parsed = self._safe_parse_judge_json(raw)
            if parsed is None:
                if attempt < retries:
                    prompt += (
                        "\n\nYour last response failed to parse as JSON. "
                        "Return only valid JSON."
                    )
                    continue
                return (
                    ItemGrade(
                        rubric_item_id=item.rubric_item_id,
                        criterion=item.criterion,
                        max_score=item.score,
                        awarded_score=0.0,
                        verdict="judge_error",
                        decided_by="judge",
                        required=item.required,
                        evidence="judge_json_parse_failed",
                        judge_confidence=None,
                        judge_latency_ms=latency_ms,
                        judge_raw_response=raw if self._save_raw() else None,
                    ),
                    input_tok,
                    output_tok,
                )

            verdict = str(parsed.get("verdict", "fail")).lower()
            if verdict not in {"pass", "partial", "fail"}:
                verdict = "fail"

            partial = float(parsed.get("partial_score", 0.0) or 0.0)
            partial = max(0.0, min(1.0, partial))
            if verdict == "pass":
                partial = 1.0
            elif verdict == "fail":
                partial = 0.0
            elif partial <= 0.0 or partial >= 1.0:
                verdict = "fail"
                partial = 0.0

            evidence = str(parsed.get("evidence") or "").strip()
            evidence_max = int(self.config.get("grader", {}).get("evidence_max_chars", 200))
            if len(evidence) > evidence_max:
                evidence = evidence[:evidence_max]
            if self.config.get("grader", {}).get("fail_on_missing_evidence", True) and not evidence:
                verdict = "fail"
                partial = 0.0
                evidence = "missing evidence"

            awarded = float(item.score) * partial
            confidence_f = None
            confidence = parsed.get("confidence")
            if confidence is not None:
                try:
                    confidence_f = max(0.0, min(1.0, float(confidence)))
                except (TypeError, ValueError):
                    confidence_f = None

            return (
                ItemGrade(
                    rubric_item_id=item.rubric_item_id,
                    criterion=item.criterion,
                    max_score=item.score,
                    awarded_score=awarded,
                    verdict=verdict,
                    decided_by="judge",
                    required=item.required,
                    evidence=evidence,
                    judge_confidence=confidence_f,
                    judge_latency_ms=latency_ms,
                    precheck_pattern_id=None,
                    judge_raw_response=raw if self._save_raw() else None,
                ),
                input_tok,
                output_tok,
            )

        raise RuntimeError("unreachable")

    def _call_judge(self, prompt: str) -> tuple[str, float, int, int]:
        gen = self.config.get("judge", {}).get("generation", {})
        reasoning = self.config.get("judge", {}).get("reasoning", {})
        per_item_max = int(self.config.get("grader", {}).get("per_item_max_output_tokens", 800))
        max_output = int(min(per_item_max, int(gen.get("max_output_tokens", 4096))))

        retry_cfg = self.config.get("tpm_guard", {}).get("retry_on_429", {})
        max_retries = int(retry_cfg.get("max_retries", 3)) if retry_cfg.get("enabled", True) else 0
        backoff = float(retry_cfg.get("initial_backoff_sec", 2))
        factor = float(retry_cfg.get("exponential_factor", 2.0))

        for attempt in range(max_retries + 1):
            self._apply_tpm_delay()
            start = time.time()
            try:
                response = self.client.responses.create(
                    model=self.model,
                    input=prompt,
                    temperature=float(gen.get("temperature", 0)),
                    max_output_tokens=max_output,
                    seed=int(gen.get("seed", 42)),
                    reasoning={"effort": reasoning.get("effort", "high")},
                )
                latency_ms = (time.time() - start) * 1000
                text = getattr(response, "output_text", "") or ""
                usage = getattr(response, "usage", None)
                input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
                output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
                return text, latency_ms, input_tokens, output_tokens
            except Exception as exc:
                status = getattr(exc, "status_code", None)
                if status in (429, 500, 502, 503, 504) and attempt < max_retries:
                    time.sleep(backoff)
                    backoff *= factor
                    continue
                raise

        raise RuntimeError("unreachable")

    def _apply_tpm_delay(self) -> None:
        if self._min_delay_seconds <= 0:
            return
        now = time.time()
        if self._last_judge_call_at is not None:
            elapsed = now - self._last_judge_call_at
            remaining = self._min_delay_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)
                now = time.time()
        self._last_judge_call_at = now

    def _summarize_deliverables(self, files: list[Path]) -> list[dict]:
        max_chars = int(self.config.get("grader", {}).get("deliverable_extract_max_chars", 4000))
        out: list[dict] = []
        for path in files:
            text = read_reference_file(str(path))
            if len(text) > max_chars:
                text = text[:max_chars] + "..."
            out.append(
                {
                    "filename": path.name,
                    "size_bytes": path.stat().st_size,
                    "mime_type": path.suffix.lower().lstrip(".") or "unknown",
                    "content": text,
                }
            )
        return out

    def _build_prompt(
        self,
        task: TaskRubric,
        item: RubricItem,
        deliverable_summaries: list[dict],
    ) -> str:
        task_prompt_max = int(self.config.get("grader", {}).get("task_prompt_truncate_chars", 500))
        prompt = self.prompt_template
        prompt = prompt.replace("{{sector}}", task.sector)
        prompt = prompt.replace("{{occupation}}", task.occupation)
        prompt = prompt.replace(
            "{{task_prompt_truncated_500}}", self._truncate(task.prompt, task_prompt_max)
        )
        prompt = prompt.replace("{{rubric_item_id}}", item.rubric_item_id)
        prompt = prompt.replace("{{max_score}}", str(item.score))
        prompt = prompt.replace("{{required}}", self._json_scalar(item.required))
        prompt = prompt.replace("{{criterion}}", item.criterion)

        block = ""
        for d in deliverable_summaries:
            block += (
                f"### File: {d['filename']} ({d['size_bytes']} bytes, {d['mime_type']})\n"
                f"```\n{d['content']}\n```\n"
            )

        prompt = re.sub(
            r"\{\{#each deliverable_files\}\}[\s\S]*?\{\{/each\}\}",
            block.strip(),
            prompt,
            flags=re.MULTILINE,
        )
        return prompt

    def _to_item_grade_from_precheck(
        self,
        item: RubricItem,
        pattern_id: Optional[str],
        verdict: Verdict,
        evidence: str,
    ) -> ItemGrade:
        evidence = self._truncate(
            evidence.strip(), int(self.config.get("grader", {}).get("evidence_max_chars", 200))
        )
        if verdict == "pass":
            awarded = float(item.score)
        elif verdict == "partial":
            awarded = float(item.score) * 0.5
        else:
            awarded = 0.0
        return ItemGrade(
            rubric_item_id=item.rubric_item_id,
            criterion=item.criterion,
            max_score=item.score,
            awarded_score=awarded,
            verdict=verdict,
            decided_by="precheck",
            required=item.required,
            evidence=evidence,
            precheck_pattern_id=pattern_id,
        )

    @staticmethod
    def _aggregate(items: list[ItemGrade], task: TaskRubric) -> TaskGrade:
        total_awarded = sum(it.awarded_score for it in items)
        total_max = task.max_score
        pct = (total_awarded / total_max * 100.0) if total_max else 0.0
        critical_fail = any(bool(it.required) and it.verdict in ("fail", "judge_error") for it in items)
        return TaskGrade(
            task_id=task.task_id,
            sector=task.sector,
            occupation=task.occupation,
            items=items,
            total_awarded=round(total_awarded, 4),
            total_max=total_max,
            pct=round(pct, 2),
            critical_fail=critical_fail,
            gold_referenced=bool(task.gold_deliverable_files),
            judge_call_count=0,
            precheck_count=0,
            judge_total_latency_ms=0.0,
            judge_input_tokens=0,
            judge_output_tokens=0,
        )

    def _absent_judge_item(self, item: RubricItem) -> ItemGrade:
        return ItemGrade(
            rubric_item_id=item.rubric_item_id,
            criterion=item.criterion,
            max_score=item.score,
            awarded_score=0.0,
            verdict="fail",
            decided_by="judge",
            required=item.required,
            evidence="deliverable absent",
            judge_confidence=1.0,
            judge_latency_ms=0.0,
        )

    def _fail_precheck_item(
        self,
        item: RubricItem,
        pattern_id: Optional[str],
        evidence: str,
    ) -> ItemGrade:
        return ItemGrade(
            rubric_item_id=item.rubric_item_id,
            criterion=item.criterion,
            max_score=item.score,
            awarded_score=0.0,
            verdict="fail",
            decided_by="precheck",
            required=item.required,
            evidence=evidence,
            precheck_pattern_id=pattern_id,
        )

    @staticmethod
    def _safe_parse_judge_json(raw_text: str) -> Optional[dict]:
        text = raw_text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _read_prompt_template(path: str) -> str:
        return Path(path).read_text(encoding="utf-8")

    @staticmethod
    def _extract_prompt_version(prompt_text: str) -> str:
        m = re.search(r"prompt_version:\s*([A-Za-z0-9_.-]+)", prompt_text)
        return m.group(1) if m else "v1"

    @staticmethod
    def _truncate(value: str, max_chars: int) -> str:
        if len(value) <= max_chars:
            return value
        return value[:max_chars] + "..."

    @staticmethod
    def _json_scalar(value: object) -> str:
        return json.dumps(value)

    def _save_raw(self) -> bool:
        return bool(self.config.get("grader", {}).get("save_raw_responses", False))
