"""Ground-truth backend router.

The project supports two explicit backends:

- ``official``: the authors' Zenodo record 14171745, via
  :mod:`official_ground_truth_adapter`. This is the preferred backend for a
  replication study once the Zenodo files have been installed and the adapter
  has been mapped to the authors' entry point.
- ``reconstruction``: our earlier transparent geometric reconstruction. It is
  retained only as a fallback / sensitivity baseline and is never silently
  presented as the authors' implementation.
"""
from __future__ import annotations

from typing import Iterable

from ground_truth_reconstruction import GTConfig
from ground_truth_reconstruction import analyze_ground_truth as _analyze_reconstruction


class GroundTruthBackendError(RuntimeError):
    """Raised when a requested ground-truth backend cannot be used."""


def analyze_ground_truth(
    vehicles: Iterable,
    cfg: GTConfig | None = None,
    backend: str = "reconstruction",
) -> dict:
    """Run one of the supported ground-truth backends.

    Parameters
    ----------
    vehicles:
        Iterable of validated ``Vehicle`` objects.
    cfg:
        Configuration for the *reconstruction* backend. Ignored for the
        official backend because the authors' code should keep its own logic.
    backend:
        ``"official"`` or ``"reconstruction"``.
    """
    backend = backend.strip().lower().replace("-", "_")

    if backend in {"reconstruction", "reconstructed", "baseline"}:
        result = _analyze_reconstruction(vehicles, cfg or GTConfig())
        result["ground_truth_backend"] = "reconstruction"
        return result

    if backend in {"official", "zenodo", "authors", "author"}:
        from official_ground_truth_adapter import analyze_official_ground_truth

        result = analyze_official_ground_truth(list(vehicles))
        result["ground_truth_backend"] = "official_zenodo_14171745"
        return result

    raise GroundTruthBackendError(
        f"Unknown ground-truth backend: {backend!r}. "
        "Use 'official' or 'reconstruction'."
    )


__all__ = ["GTConfig", "GroundTruthBackendError", "analyze_ground_truth"]
