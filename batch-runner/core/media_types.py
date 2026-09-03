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
#: Video containers the visual prepass renders as a contact sheet: evenly
#: spaced, timestamped stills tiled into one image. Named separately from the
#: rest of the visual set because the render is a *sample* rather than a
#: reproduction -- a page render shows the page, whereas twelve frames of a
#: two-minute clip show twelve moments and say so -- but folded into
#: ``GRADER_VISUAL_RENDER_EXTENSIONS`` below, because routing has one
#: question to ask and it is "can the judge be shown this".
#:
#: Kept equal to ``_EXT_KIND``'s ``video`` entries by
#: ``test_video_render_extensions_match_the_kind_map``: the renderer
#: dispatches on kind, so a suffix here that the kind map calls something
#: else would plan a render the renderer then refuses.
GRADER_VIDEO_RENDER_EXTENSIONS = frozenset({
    ".mp4",
    ".mov",
    ".webm",
    ".mkv",
    ".avi",
})

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
}) | GRADER_VIDEO_RENDER_EXTENSIONS

#: Source files: code, stylesheets and markup that describe an appearance
#: rather than having one. Read as a set of *program text*, not of "things
#: that happen to be readable" -- ``.csv``, ``.txt``, ``.md`` and ``.json``
#: are deliberately absent, because a spreadsheet export or a memo is data a
#: reader looks at, and this set exists to name work whose only honest
#: reading is its source.
#:
#: The distinction earns its keep in one place, the visual demotion in
#: ``grader_routing``. A React component's rendered appearance is not a
#: property of the submission at all; it exists only once something builds
#: and runs the code. So "the rendered DOM includes an element with
#: role=status" is answered by reading the JSX, and that is not a substitute
#: for looking -- it is the only place the answer is written down.
GRADER_SOURCE_CODE_EXTENSIONS = frozenset({
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".css",
    ".go",
    ".h",
    ".hpp",
    ".htm",
    ".html",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".m",
    ".mjs",
    ".php",
    ".pl",
    ".py",
    ".r",
    ".rb",
    ".rs",
    ".scss",
    ".sh",
    ".sql",
    ".svelte",
    ".swift",
    ".ts",
    ".tsx",
    ".vue",
})
