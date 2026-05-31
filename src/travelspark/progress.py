from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass
class Progress:
    enabled: bool = True

    def say(self, message: str) -> None:
        if self.enabled:
            print(message, file=sys.stderr, flush=True)

    def step(self, label: str, current: int, total: int) -> None:
        if self.enabled:
            print(f"{label} ({current}/{total})", file=sys.stderr, flush=True)
