"""How a report says that something was never measured.

A run summary averages what it has. When it has nothing -- every task errored,
so no task was scored; nothing recorded a latency, so nothing was timed -- the
average does not come out at zero, it does not exist. Writing zero for it
publishes the worst value on the scale as though it had been observed:
``0.0/10`` reads as a model that failed every rubric item, and ``0ms`` reads as
a run that finished instantly.

``step3_format_results.py`` has always drawn this distinction, storing ``None``
for an empty bucket and rendering a dash. This module is that same answer in
one place, for the report writer and for the prompt the narrating model is
handed -- a figure that reaches the narrator comes back as prose, and prose
about a run that scored zero is harder to withdraw than a table cell.

A measurement that really is zero still prints as zero. The dash is only ever
for the absence of one.
"""

from __future__ import annotations

from typing import Optional, Union

#: What every surface prints where a measurement is absent. The same dash
#: ``step3_format_results.py`` writes, so a reader who has seen one report has
#: already seen this one.
NOT_MEASURED = "-"


def render_measured(
    value: Optional[Union[int, float]], suffix: str = "", spec: str = ""
) -> str:
    """Render ``value`` with its unit, or the dash that says there is no value.

    ``spec`` is an ordinary format spec, so a thousands separator is ``","``
    and one decimal place is ``".1f"``. Formatting lives in here rather than at
    the call sites because the two mistakes are not equally loud: a caller that
    forgets ``None`` is possible crashes on ``f"{None:,}"`` and gets fixed,
    while a caller that reaches for ``or 0`` instead prints a plausible number
    forever. Only the second one is the defect this module exists to stop.
    """
    if value is None:
        return NOT_MEASURED
    return f"{value:{spec}}{suffix}"
