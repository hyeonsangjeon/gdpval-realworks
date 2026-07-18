"""PID 1 for a disposable agentic task container."""

from __future__ import annotations

import os
import signal
from pathlib import Path


def main() -> None:
    if os.geteuid() == 0:
        raise SystemExit("agentic task container refuses UID 0")
    for relative in (".home", ".cache", ".config", ".tmp"):
        path = Path("/work") / relative
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    while True:
        signal.pause()


if __name__ == "__main__":
    main()