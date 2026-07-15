"""Work-auth provider registry. `get_provider(scheme)` returns the provider the
profile selected. Scheme names are validated against engine.profile.SCHEMES so the
two never drift."""

from __future__ import annotations

from typing import Any

from engine.profile import SCHEMES
from work_auth.base import WorkAuthProvider
from work_auth.none_provider import NoneProvider
from work_auth.eu_blue_card import EuBlueCardProvider


def get_provider(scheme: str, **kwargs: Any) -> WorkAuthProvider:
    """Instantiate the provider for `scheme`. Raises ValueError for an unknown or
    unsupported scheme. nl-ind-hsm is registered in this same map (Task 5)."""
    if scheme not in SCHEMES:
        raise ValueError(f"unknown work_auth scheme {scheme!r}; allowed: {sorted(SCHEMES)}")
    if scheme == "none":
        return NoneProvider()
    if scheme == "eu-blue-card":
        return EuBlueCardProvider()
    if scheme == "nl-ind-hsm":
        # Imported lazily so Task 4 stands alone before Task 5 lands the module.
        from work_auth.nl_ind_hsm import NlIndHsmProvider
        return NlIndHsmProvider(**kwargs)
    raise ValueError(f"scheme {scheme!r} has no registered provider")
