"""Shared media type sets for grader selection, routing, and tools."""

from __future__ import annotations


GRADER_AUDIO_EXTENSIONS = frozenset({
    ".wav",
    ".mp3",
    ".flac",
    ".ogg",
    ".m4a",
    ".aac",
})

#: Extensions the visual prepass can actually turn into an image for the
#: judge to look at. Kept here rather than in ``tool_calling_judge`` so the
#: pure-functional routing module can consult it without importing the
#: grading stack.
#:
#: ``tool_calling_judge._VISUAL_RENDER_SCOPES`` remains the runtime authority
#: -- it carries the per-suffix render scope, which is not derivable from a
#: bare set -- and its keys are held equal to this set by
#: ``test_visual_render_extensions_match_the_renderer``. The duplication is
#: deliberate and guarded: the failure it prevents is a suffix being added to
#: one and not the other, which would route a renderable file to text (or
#: promise a render that cannot happen) with no error anywhere.
GRADER_VISUAL_RENDER_EXTENSIONS = frozenset({
    ".pdf",
    ".xlsx",
    ".xlsm",
    ".pptx",
    ".docx",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".webp",
})
