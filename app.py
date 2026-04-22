# app.py (дополнение к существующему)

# Добавить импорты
from metrics.weather_collector import WeatherCollector
from metrics.trust_analyzer import TrustAnalyzer
from metrics.happiness_analyzer import HappinessAnalyzer
from metrics.composite_index import CompositeIndexCalculator

# Добавить в класс CityContext
@dataclass
class CityContext:
    city_name: str
    lat: float
    lon: float
    model: ConfinementModel9
    weather_collector: WeatherCollector
    trust_analyzer: TrustAnalyzer
    happiness_analyzer: HappinessAnalyzer
    composite_calculator: CompositeIndexCalculator
    metrics_history: List = field(default_factory=list)

# Новый эндпоинт для всех метрик
@app.get("/api/city/all_metrics")
async def get_all_metrics(city_name: str):
    """Получение всех метрик для дашборда"""
    if city_name not in city_contexts:
        return {"error": "City not initialized"}
    
    context = city_contexts[city_name]
    
    # Сбор всех метрик параллельно
    weather = await context.weather_collector.fetch_current_weather()
    trust = await context.trust_analyzer.analyze_social_media()
    
    # Получаем текущие метрики города
    city_metrics = context.analyzer.current_metrics
    
    # Счастье
    happiness = await context.happiness_analyzer.calculate_happiness(
        city_metrics, trust, weather
    )
    
    # Композитные индексы
    composites = context.composite_calculator.calculate_all_indices(
        city_metrics, trust, happiness, weather
    )
    
    # Влияние погоды
    weather_impact = context.weather_collector.get_weather_impact_on_metrics()
    
    return {
        "city": city_name,
        "timestamp": datetime.now().isoformat(),
        "weather": {
            "temperature": weather.temperature,
            "feels_like": weather.feels_like,
            "condition": weather.condition,
            "condition_emoji": weather.condition_emoji,
            "humidity": weather.humidity,
            "wind_speed": weather.wind_speed,
            "comfort_index": weather.comfort_index,
            "impact_on_metrics": weather_impact
        },
        "trust": {
            "index": trust.trust_index,
            "positive_mentions": trust.positive_mentions,
            "negative_mentions": trust.negative_mentions,
            "top_complaints": trust.top_complaints,
            "top_praises": trust.top_praises,
            "trend": trust.sentiment_trend
        },
        "happiness": {
            "overall": happiness.overall_happiness,
            "life_satisfaction": happiness.life_satisfaction,
            "emotional_state": happiness.emotional_state,
            "social_connection": happiness.social_connection,
            "top_factors": happiness.top_factors,
            "breakdown": happiness.sub_indices
        },
        "composite_indices": {
            "quality_of_life": composites.quality_of_life_index,
            "economic_development": composites.economic_development_index,
            "social_cohesion": composites.social_cohesion_index,
            "environmental": composites.environmental_index,
            "infrastructure": composites.infrastructure_index,
            "mayoral_performance": composites.mayoral_performance_index,
            "city_attractiveness": composites.city_attractiveness_index,
            "future_outlook": composites.future_outlook_index,
            "overall_color": composites.overall_color
        },
        "city_metrics": {
            "safety": city_metrics.get('СБ', 3.0) / 6.0,
            "economy": city_metrics.get('ТФ', 3.0) / 6.0,
            "quality": city_metrics.get('УБ', 3.0) / 6.0,
            "social": city_metrics.get('ЧВ', 3.0) / 6.0
        }
    }
