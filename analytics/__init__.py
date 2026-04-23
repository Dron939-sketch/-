"""Analytics adapters on top of the legacy confinement core."""

from .butterfly import Simulation, NodeDelta, simulate
from .loops import analyze_loops, metrics_to_vectors
from .model import build_graph
from .root_cause import CauseHop, RootCauseTrace, trace as trace_root_cause
from .transparency import Breakdown, Component, breakdown

__all__ = [
    "analyze_loops",
    "build_graph",
    "metrics_to_vectors",
    "simulate",
    "Simulation",
    "NodeDelta",
    "trace_root_cause",
    "RootCauseTrace",
    "CauseHop",
    "breakdown",
    "Breakdown",
    "Component",
]
