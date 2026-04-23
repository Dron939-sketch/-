"""Analytics adapters on top of the legacy confinement core."""

from .butterfly import Simulation, NodeDelta, simulate
from .loops import analyze_loops, metrics_to_vectors
from .model import build_graph

__all__ = [
    "analyze_loops",
    "build_graph",
    "metrics_to_vectors",
    "simulate",
    "Simulation",
    "NodeDelta",
]
