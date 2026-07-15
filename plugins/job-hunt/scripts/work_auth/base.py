"""Work-authorisation provider interface.

A provider annotates companies with a work-auth status and gates individual
listings. `profile.work_auth.scheme` selects the provider. Providers are pure and
offline: they read only local/cached data, never the network during use. The one
provider with a live data source (nl-ind-hsm) puts that behind an injectable
refresh path, so all annotation is offline-testable.
"""

from __future__ import annotations

from typing import Any

# Canonical status vocabulary (providers may use a subset):
#   "confirmed"  authoritatively eligible (e.g. on a recognised register)
#   "possible"   likely but not certain
#   "not_found"  not on the register / no evidence
#   "flag"       provider cannot verify; surface for manual review
#   "n/a"        no work-auth filter applies
STATUSES = ("confirmed", "possible", "not_found", "flag", "n/a")

# Gate outcomes.
KEEP, FLAG, DROP = "keep", "flag", "drop"


class WorkAuthProvider:
    """Base interface. Subclasses set `scheme` and implement annotate()/gate()."""

    scheme: str = "base"

    def annotate(self, companies: list[str]) -> dict[str, dict[str, Any]]:
        """Return {company: {"status": <STATUS>, ...}} for each input company."""
        raise NotImplementedError

    def gate(self, listing: dict[str, Any]) -> str:
        """Return KEEP / FLAG / DROP for one listing. Reads the status the caller
        attached at listing["work_auth"]["status"]."""
        raise NotImplementedError

    @staticmethod
    def _status_of(listing: dict[str, Any]) -> str:
        return (listing.get("work_auth") or {}).get("status", "n/a")
