"""GDPVal Sandbox Skills — Agent-Skill toolkits mounted inside the sandbox.

Each sub-package (``audio``, ``video``, ``document``, ``image``, ``data``) ships
a ``SKILL.md`` (Agent-Skill metadata + usage manual) and a ``toolkit.py`` with
runnable helper functions. The whole ``skills`` package is copied into the
sandbox working directory and added to ``PYTHONPATH`` so LLM-generated
``solution.py`` can simply::

    from skills import audio, video, document, image, data

    info = video.video_info("clip.mp4")
    frames = video.keyframes("clip.mp4", max_frames=8)
    peaks = audio.fft_summary("track.wav")

All heavy third-party imports inside the toolkits are *lazy* — importing the
``skills`` package never fails even when librosa / opencv / pymupdf are absent.
Calling a function that needs a missing library raises a clear
``SkillDependencyError`` naming the pip package to install.
"""

from __future__ import annotations


class SkillDependencyError(ImportError):
    """Raised when a skill helper needs a library that is not installed.

    The message always names the pip package(s) to install so the dependency
    resolver / sandbox image can be fixed.
    """


def _require(module: str, pip_name: str | None = None):
    """Lazy-import ``module`` or raise a clear :class:`SkillDependencyError`."""
    import importlib

    try:
        return importlib.import_module(module)
    except ImportError as exc:  # pragma: no cover - exercised via toolkits
        pkg = pip_name or module
        raise SkillDependencyError(
            f"Skill needs '{module}' — install with: pip install {pkg}"
        ) from exc


__all__ = ["SkillDependencyError", "_require"]
