"""Analytics adapters on top of the legacy confinement core."""

from .benchmark import BenchmarkResult, CityMetric, CityRow, VectorStat, benchmark
from .butterfly import Simulation, NodeDelta, simulate
from .crisis import Alert, CrisisReport, detect_crises
from .decisions import Decision, DecisionScenario, filter_for as filter_decisions, list_decisions, get_decision
from .deep_forecast import DeepForecastReport, VectorForecast, forecast as deep_forecast
from .foresight import ForesightReport, MegatrendRow, Scenario, VectorProjection, forecast as foresight_forecast
from .investment import Factor, InvestmentProfile, compute as investment_compute
from .knowledge import Case, Recommendation, library_size, recommend as recommend_cases
from .loops import analyze_loops, metrics_to_vectors
from .market_gaps import GapReport, Niche, analyze as analyze_market_gaps
from .model import build_graph
from .reputation import AuthorStat, ReputationReport, ViralPost, analyze as reputation_analyze
from .resources import ResourcePlan, VectorAllocation, plan as resource_plan
from .root_cause import CauseHop, RootCauseTrace, trace as trace_root_cause
from .tasks import Task, TaskList, derive as derive_tasks
from .topics import TopicReport, TopicRow, analyze as topics_analyze, classify_item
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
    "list_decisions",
    "filter_decisions",
    "get_decision",
    "Decision",
    "DecisionScenario",
    "deep_forecast",
    "DeepForecastReport",
    "VectorForecast",
    "foresight_forecast",
    "ForesightReport",
    "MegatrendRow",
    "Scenario",
    "VectorProjection",
    "investment_compute",
    "Factor",
    "InvestmentProfile",
    "recommend_cases",
    "Case",
    "Recommendation",
    "library_size",
    "analyze_market_gaps",
    "GapReport",
    "Niche",
    "metrics_to_vectors",
    "reputation_analyze",
    "AuthorStat",
    "ReputationReport",
    "ViralPost",
    "resource_plan",
    "ResourcePlan",
    "VectorAllocation",
    "simulate",
    "Simulation",
    "NodeDelta",
    "trace_root_cause",
    "RootCauseTrace",
    "CauseHop",
    "derive_tasks",
    "Task",
    "TaskList",
    "topics_analyze",
    "TopicReport",
    "TopicRow",
    "classify_item",
    "breakdown",
    "Breakdown",
    "Component",
]
