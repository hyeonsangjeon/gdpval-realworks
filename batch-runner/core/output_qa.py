"""Output QA — render generated deliverables and judge their appearance.

This wires :mod:`core.artifact_renderer` into a single report the runner can act
on. By default it is **deterministic and LLM-free**: it records rendered page
counts, image dimensions, blank-page detection, and conversion errors. A blank
*primary* deliverable is treated as blocking (the repair loop can fix it).

An optional model **vision QA** pass (disabled by default,
``execution.sandbox.output_qa.vision.enabled``) samples a few rendered PNGs and
asks the configured vision model for a concise JSON verdict. Its result is
cached by image-set hash + config so repeated runs never re-pay the cost.
"""

from __future__ import annotations

import base64
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

from core.artifact_renderer import render_artifact
from core.artifact_verifier import classify_kind

_PRIMARY_KINDS = {"pdf", "presentation", "document", "spreadsheet", "image"}


@dataclass
class OutputQAReport:
    enabled: bool = True
    render_reports: List[dict] = field(default_factory=list)
    vision_qa: Optional[dict] = None
    ok: bool = True
    blocking_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _is_primary(path: Path, contract) -> bool:
    if contract is not None and contract.expected_extensions:
        return path.suffix.lower() in {e.lower() for e in contract.expected_extensions}
    return classify_kind(path.suffix) in _PRIMARY_KINDS


def _vision_qa(images, task_text, client, model, max_images, cache, cfg):
    """Optional model vision pass over rendered PNGs → JSON verdict (cached)."""
    images = images[:max_images]
    if not images:
        return None

    cache_key = None
    if cache is not None and getattr(cache, "enabled", False):
        try:
            digest = "".join(cache.hash_file(p)[:16] for p in images)
            cache_key = cache.key(cache.hash_bytes(digest.encode()), "vision_qa", cfg)
            hit = cache.get_json(cache_key)
            if hit is not None:
                hit["_cached"] = True
                return hit
        except Exception:
            cache_key = None

    if client is None:
        return None

    instruction = (
        "You are a strict visual QA reviewer for professional deliverables. "
        "Inspect the rendered page image(s) of a generated file. Judge only what "
        "you can see: layout, legibility, blank/empty pages, overflow, broken "
        "charts, obvious formatting defects. Respond with JSON only: "
        '{"visual_ok": true/false, "issues": ["..."], "suggested_repair": "..."}'
    )
    content: List[dict] = [
        {"type": "text", "text": instruction},
        {"type": "text", "text": f"Task context: {task_text[:1200]}"},
    ]
    for p in images:
        try:
            b64 = base64.b64encode(Path(p).read_bytes()).decode("utf-8")
        except Exception:
            continue
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "auto"},
        })
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
            max_completion_tokens=600,
        )
        raw = (response.choices[0].message.content or "").strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        verdict = json.loads(raw) if raw else None
    except Exception as e:
        return {"visual_ok": None, "issues": [f"vision QA call failed: {e}"],
                "suggested_repair": ""}

    if verdict is not None and cache_key is not None:
        try:
            cache.put_json(cache_key, verdict)
        except Exception:
            pass
    return verdict


def run_output_qa(
    artifacts,
    contract=None,
    config: Optional[dict] = None,
    out_dir=None,
    task_text: str = "",
    vision_client=None,
    cache=None,
) -> OutputQAReport:
    """Render artifacts and produce a deterministic (+ optional vision) QA report."""
    config = config or {}
    report = OutputQAReport(enabled=bool(config.get("enabled", True)))
    if not report.enabled:
        return report

    do_render = bool(config.get("render", True))
    max_pages = int(config.get("max_pages_per_artifact", 3))
    blank_threshold = float(config.get("blank_page_threshold", 0.999))
    dpi = int(config.get("dpi", 120))

    arts = [Path(a) for a in artifacts]
    if out_dir is not None:
        out_dir = Path(out_dir)
    elif arts:
        out_dir = arts[0].parent / "_render"
    else:
        out_dir = None

    all_images: List[Path] = []
    if do_render and out_dir is not None:
        render_dir = Path(out_dir)
        render_dir.mkdir(parents=True, exist_ok=True)
        for art in arts:
            if classify_kind(art.suffix) not in _PRIMARY_KINDS:
                continue
            rr = render_artifact(
                art, render_dir, max_pages=max_pages,
                blank_threshold=blank_threshold, dpi=dpi, cache=cache,
            )
            report.render_reports.append(rr.to_dict())
            all_images.extend(Path(i) for i in rr.rendered_images)

            primary = _is_primary(art, contract)
            if rr.errors:
                msg = f"{art.name}: render error — {'; '.join(rr.errors)}"
                if primary:
                    report.blocking_errors.append(msg)
                else:
                    report.warnings.append(msg)
            if primary and not rr.rendered_images:
                report.blocking_errors.append(
                    f"{art.name}: primary deliverable produced no rendered image."
                )
            if rr.blank_pages:
                report.warnings.append(
                    f"{art.name}: {len(rr.blank_pages)} blank page(s) detected "
                    f"at {rr.blank_pages}."
                )
            # Blocking only when a *primary* deliverable is essentially pure white
            # on EVERY rendered page (avoids false-failing sparse-but-valid pages).
            fractions = rr.page_white_fractions
            if (
                primary
                and rr.page_count > 0
                and fractions
                and all(f >= 0.9997 for f in fractions)
            ):
                report.blocking_errors.append(
                    f"{art.name}: primary deliverable appears blank "
                    f"(all {rr.page_count} rendered page(s) are empty)."
                )

    # Optional model vision QA (off by default).
    vcfg = config.get("vision", {}) or {}
    if vcfg.get("enabled") and all_images:
        verdict = _vision_qa(
            all_images, task_text, vision_client,
            model=vcfg.get("deployment") or vcfg.get("model"),
            max_images=int(vcfg.get("max_images", 6)),
            cache=cache,
            cfg={"v": 1, "blank_threshold": blank_threshold},
        )
        report.vision_qa = verdict
        if verdict and verdict.get("visual_ok") is False:
            issues = "; ".join(verdict.get("issues", []) or []) or "unspecified"
            text = f"vision QA flagged issues: {issues}"
            if vcfg.get("blocking"):
                report.blocking_errors.append(text)
            else:
                report.warnings.append(text)

    report.ok = not report.blocking_errors
    return report
