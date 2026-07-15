"""`eu-blue-card` scheme: flag-only. There is no single authoritative EU Blue Card
employer register, so this provider cannot confirm eligibility. It flags every
role for manual salary/skill-threshold review and never drops."""

from __future__ import annotations

from typing import Any

from work_auth.base import FLAG, WorkAuthProvider

_NOTE = ("EU Blue Card eligibility not verifiable from a register; "
         "confirm the salary/skill threshold for the country manually.")


class EuBlueCardProvider(WorkAuthProvider):
    scheme = "eu-blue-card"

    def annotate(self, companies: list[str]) -> dict[str, dict[str, Any]]:
        return {c: {"status": "flag", "note": _NOTE} for c in dict.fromkeys(companies)}

    def gate(self, listing: dict[str, Any]) -> str:
        return FLAG
