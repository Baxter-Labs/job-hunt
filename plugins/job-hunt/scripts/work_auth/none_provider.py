"""`none` scheme: domestic / no sponsorship needed. No filter."""

from __future__ import annotations

from typing import Any

from work_auth.base import KEEP, WorkAuthProvider


class NoneProvider(WorkAuthProvider):
    scheme = "none"

    def annotate(self, companies: list[str]) -> dict[str, dict[str, Any]]:
        return {c: {"status": "n/a"} for c in dict.fromkeys(companies)}

    def gate(self, listing: dict[str, Any]) -> str:
        return KEEP
