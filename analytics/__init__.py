"""Analytics adapters on top of the legacy confinement core."""

from .loops import analyze_loops, metrics_to_vectors

__all__ = ["analyze_loops", "metrics_to_vectors"]
