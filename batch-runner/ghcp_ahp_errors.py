"""One safe refusal type for imported modules and the probe's __main__ entry."""

import re


class Refused(RuntimeError):
    def __init__(self, code):
        super().__init__(code if re.fullmatch(r"[a-z_]{1,80}", str(code)) else "internal_probe_refusal")
