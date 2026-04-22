# metrics/weather_collector.py
"""
Сбор и анализ погодных данных для города
Влияет на настроение горожан, активность, транспорт
"""

import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging
import asyncio

logger = logging.getLogger(__name__)

@dataclass
class WeatherData:
    """Данные о погоде"""
    timestamp: datetime
    temperature: float  # °C
    feels_like: float   # °C
    humidity: int       # %
    pressure: int       # hPa
    wind_speed: float   # m/s
    wind_direction: str
    clouds: int         # %
    precipitation: float # mm
    condition: str      # 'clear', 'clouds', 'rain', 'snow', 'storm'
    condition_emoji: str
    comfort_index: float  # 0-1 (насколько комфортно)
    
class WeatherCollector:
    """Сборщик погодных данных"""
    
    def __init__(self, city_name: str, lat: float, lon: float, api_key: str = None):
        self.city_name = city_name
        self.lat = lat
        self.lon = lon
        self.api_key = api_key or "your_openweather_api_key"
        self.current_weather = None
        self.forecast = []
        self.history = []
        
    async def fetch_current_weather(self) -> WeatherData:
        """Получение текущей погоды"""
        # OpenWeatherMap API
        url = f"https://api.openweathermap.org/data/2.5/weather"
        params = {
            'lat': self.lat,
            'lon': self.lon,
            'appid': self.api_key,
            'units': 'metric',
            'lang': 'ru'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    data = await resp.json()
                    
                    weather = WeatherData(
                        timestamp=datetime.now(),
                        temperature=data['main']['temp'],
                        feels_like=data['main']['feels_like'],
                        humidity=data['main']['humidity'],
                        pressure=data['main']['pressure'],
                        wind_speed=data['wind']['speed'],
                        wind_direction=self._get_wind_direction(data['wind'].get('deg', 0)),
                        clouds=data['clouds']['all'],
                        precipitation=data.get('rain', {}).get('1h', 0),
                        condition=data['weather'][0]['main'].lower(),
                        condition_emoji=self._get_weather_emoji(data['weather'][0]['main']),
                        comfort_index=self._calculate_comfort_index(data)
                    )
                    
                    self.current_weather = weather
                    return weather
                    
        except Exception as e:
            logger.error(f"Ошибка получения погоды: {e}")
            return self._get_fallback_weather()
    
    async def fetch_forecast(self, days: int = 7) -> List[WeatherData]:
        """Получение прогноза погоды"""
        url = f"https://api.openweathermap.org/data/2.5/forecast"
        params = {
            'lat': self.lat,
            'lon': self.lon,
            'appid': self.api_key,
            'units': 'metric',
            'lang': 'ru',
            'cnt': days * 8  # 3-часовые интервалы
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    data = await resp.json()
                    
                    forecast = []
                    for item in data['list'][:days*4]:  # каждые 3 часа
                        weather = WeatherData(
                            timestamp=datetime.fromtimestamp(item['dt']),
                            temperature=item['main']['temp'],
                            feels_like=item['main']['feels_like'],
                            humidity=item['main']['humidity'],
                            pressure=item['main']['pressure'],
                            wind_speed=item['wind']['speed'],
                            wind_direction=self._get_wind_direction(item['wind'].get('deg', 0)),
                            clouds=item['clouds']['all'],
                            precipitation=item.get('rain', {}).get('3h', 0),
                            condition=item['weather'][0]['main'].lower(),
                            condition_emoji=self._get_weather_emoji(item['weather'][0]['main']),
                            comfort_index=0.5
                        )
                        forecast.append(weather)
                    
                    self.forecast = forecast
                    return forecast
                    
        except Exception as e:
            logger.error(f"Ошибка получения прогноза: {e}")
            return []
    
    def _get_weather_emoji(self, condition: str) -> str:
        """Эмодзи для погоды"""
        emojis = {
            'clear': '☀️',
            'clouds': '☁️',
            'rain': '🌧️',
            'snow': '❄️',
            'thunderstorm': '⛈️',
            'drizzle': '🌦️',
            'mist': '🌫️'
        }
        return emojis.get(condition.lower(), '🌡️')
    
    def _get_wind_direction(self, degrees: float) -> str:
        """Направление ветра"""
        directions = ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ']
        idx = int((degrees + 22.5) / 45) % 8
        return directions[idx]
    
    def _calculate_comfort_index(self, data: Dict) -> float:
        """Расчёт индекса комфортности"""
        temp = data['main']['temp']
        humidity = data['main']['humidity']
        wind = data['wind']['speed']
        
        # Идеальные параметры: 20-22°C, 40-60%, ветер 2-4 м/с
        temp_score = 1 - min(abs(temp - 21) / 20, 1)
        humidity_score = 1 - min(abs(humidity - 50) / 30, 1)
        wind_score = 1 - min(abs(wind - 3) / 8, 1)
        
        return (temp_score * 0.5 + humidity_score * 0.3 + wind_score * 0.2)
    
    def _get_fallback_weather(self) -> WeatherData:
        """Запасные данные при ошибке"""
        return WeatherData(
            timestamp=datetime.now(),
            temperature=0,
            feels_like=0,
            humidity=0,
            pressure=0,
            wind_speed=0,
            wind_direction='',
            clouds=0,
            precipitation=0,
            condition='unknown',
            condition_emoji='🌡️',
            comfort_index=0.5
        )
    
    def get_weather_impact_on_metrics(self) -> Dict[str, float]:
        """Влияние погоды на городские метрики"""
        if not self.current_weather:
            return {'safety': 0, 'happiness': 0, 'economy': 0, 'social': 0}
        
        weather = self.current_weather
        
        # Влияние на безопасность (плохая погода = больше ДТП)
        safety_impact = 0
        if weather.precipitation > 5:
            safety_impact = -0.2
        elif weather.precipitation > 1:
            safety_impact = -0.1
            
        # Влияние на счастье
        happiness_impact = (weather.comfort_index - 0.5) * 0.3
        
        # Влияние на экономику
        economy_impact = 0
        if weather.precipitation > 5:
            economy_impact = -0.1
        if weather.temperature < -15 or weather.temperature > 35:
            economy_impact = -0.15
            
        return {
            'safety': safety_impact,
            'happiness': happiness_impact,
            'economy': economy_impact,
            'social': 0
        }
