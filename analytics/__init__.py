"""Analytics adapters on top of the legacy confinement core."""

from .benchmark import BenchmarkResult, CityMetric, CityRow, VectorStat, benchmark
from .butterfly import Simulation, NodeDelta, simulate
from .crisis import Alert, CrisisReport, detect_crises
from .foresight import ForesightReport, MegatrendRow, Scenario, VectorProjection, forecast as foresight_forecast
from .investment import Factor, InvestmentProfile, compute as investment_compute
from .loops import analyze_loops, metrics_to_vectors
from .model import build_graph
from .reputation import AuthorStat, ReputationReport, ViralPost, analyze as reputation_analyze
from .root_cause import CauseHop, RootCauseTrace, trace as trace_root_cause
from .transparency import Breakdown, Component, breakdown

__all__ = [
    "analyze_loops",
    "benchmark",
    "BenchmarkResult",
    "CityMetric",
    "CityRow",
    "VectorStat",
    "build_graph",
    "detect_crises",
    "Alert",
    "CrisisReport",
    "foresight_forecast",
    "ForesightReport",
    "MegatrendRow",
    "Scenario",
    "VectorProjection",
    "investment_compute",
    "Factor",
    "InvestmentProfile",
    "metrics_to_vectors",
    "reputation_analyze",
    "AuthorStat",
    "ReputationReport",
    "ViralPost",
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
