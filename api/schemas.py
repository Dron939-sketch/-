"""Pydantic schemas for the public API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CityBrief(BaseModel):
    slug: Optional[str] = None
    name: str
    region: str
    emoji: Optional[str] = None
    accent_color: Optional[str] = None
    population: int
    coordinates: Dict[str, float]
    districts: List[str]
    key_problems: List[str]
    is_pilot: bool = False


class WeatherBlock(BaseModel):
    temperature: Optional[float] = None
    feels_like: Optional[float] = None
    condition: Optional[str] = None
    condition_emoji: Optional[str] = None
    humidity: Optional[int] = None
    wind_speed: Optional[float] = None
    comfort_index: Optional[float] = None


class TrustBlock(BaseModel):
    index: Optional[float] = Field(None, ge=0, le=1)
    positive_mentions: int = 0
    negative_mentions: int = 0
    top_complaints: List[str] = []
    top_praises: List[str] = []
    trend: Optional[str] = None


class HappinessBlock(BaseModel):
    overall: Optional[float] = Field(None, ge=0, le=1)
    life_satisfaction: Optional[float] = None
    emotional_state: Optional[float] = None
    social_connection: Optional[float] = None
    top_factors: List[str] = []


class CompositeBlock(BaseModel):
    quality_of_life: Optional[float] = None
    economic_development: Optional[float] = None
    social_cohesion: Optional[float] = None
    environmental: Optional[float] = None
    infrastructure: Optional[float] = None
    mayoral_performance: Optional[float] = None
    city_attractiveness: Optional[float] = None
    future_outlook: Optional[float] = None
    overall_color: Optional[str] = None


class VectorBlock(BaseModel):
    safety: float = Field(ge=0, le=1)
    economy: float = Field(ge=0, le=1)
    quality: float = Field(ge=0, le=1)
    social: float = Field(ge=0, le=1)


class CityMetricsResponse(BaseModel):
    city: str
    timestamp: datetime
    weather: WeatherBlock
    trust: TrustBlock
    happiness: HappinessBlock
    composite_indices: CompositeBlock
    city_metrics: VectorBlock


class NewsItem(BaseModel):
    id: str
    source_kind: str
    source_handle: str
    title: str
    content: str
    url: Optional[str] = None
    published_at: datetime
    category: Optional[str] = None


class NewsResponse(BaseModel):
    city: str
    collected: int
    items: List[NewsItem]


class AgendaResponse(BaseModel):
    city: str
    date: datetime
    headline: str
    description: str
    actions: List[str]
    top_complaints: List[str]
    top_praises: List[str]
    vectors: Dict[str, float]
    weather_line: str
    happiness: Optional[float] = None
    trust: Optional[float] = None
    markdown: str


class RoadmapRequest(BaseModel):
    vector: str = Field(..., description="СБ / ТФ / УБ / ЧВ")
    start_level: float = Field(..., ge=1.0, le=6.0)
    target_level: float = Field(..., ge=1.0, le=6.0)
    deadline: date
    scenario: str = Field("baseline", pattern="^(optimistic|baseline|pessimistic)$")


class RoadmapResponse(BaseModel):
    city: str
    roadmap: Dict[str, Any]


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    default_city: str
