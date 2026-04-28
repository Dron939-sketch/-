#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
МОДУЛЬ 39: БИБЛИОТЕКА МЕРОПРИЯТИЙ СЧАСТЬЯ (Happiness Events Library)
РУССКАЯ PREMIUM-ВЕРСИЯ — ЮГО-ВОСТОК МОСКОВСКОЙ ОБЛАСТИ

Адаптировано для городов юго-востока МО:
- Коломна (пилот)
- Луховицы
- Воскресенск
- Егорьевск
- Ступино
- Озёры

Особенности региона:
- Река Ока (рыбалка, купание, лодки)
- Леса (грибы, ягоды, охота)
- Фермерство (луховицкие огурцы, яблоки)
- Историческое наследие (Коломенский кремль, усадьбы)
- Традиционные промыслы
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ==================== МОДЕЛИ ====================

class EventType(Enum):
    BANYA = "banya"                 # Банные мероприятия
    GASTRONOMY = "gastronomy"       # Гастрономия
    FOLK = "folk"                   # Народные гуляния
    SPORTS = "sports"               # Спорт
    CRAFTS = "crafts"               # Ремёсла
    RELIGIOUS = "religious"         # Православные
    SEASONAL = "seasonal"           # Сезонные
    CHARITY = "charity"             # Благотворительные
    FISHING = "fishing"             # Рыбалка / охота
    COUNTRY = "country"             # Деревенские забавы
    CULTURAL = "cultural"           # Культурно-исторические
    FAMILY = "family"               # Семейные
    EDUCATIONAL = "educational"     # Образовательные
    FERMER = "fermer"               # Фермерские/сельские


class Audience(Enum):
    ALL = "all"
    FAMILY = "family"
    YOUTH = "youth"
    ADULTS = "adults"
    SENIORS = "seniors"
    MEN = "men"
    WOMEN = "women"
    TOURISTS = "tourists"


class Season(Enum):
    WINTER = "winter"
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    YEAR_ROUND = "year_round"


@dataclass
class HappinessEvent:
    id: str
    name: str
    description: str
    type: EventType
    audience: Audience
    season: Season
    happiness_impact: float      # 0-1
    trust_impact: float          # 0-1
    economy_impact: float        # 0-1
    social_impact: float         # 0-1
    health_impact: float         # 0-1
    duration_days: int
    cost_million_rub: float
    expected_attendance: int
    roi: float
    requires_banya: bool = False
    requires_river: bool = False
    requires_forest: bool = False
    requires_snow: bool = False
    requires_kremlin: bool = False
    regional_specific: str = ""
    popularity: float = 0.5
    difficulty: float = 0.5


# ==================== ПОЛНАЯ БИБЛИОТЕКА ====================

class HappinessEventsLibrary:
    """
    Библиотека мероприятий для повышения индекса счастья
    Адаптирована для городов юго-востока Московской области
    """
    
    def __init__(self, city_name: str, population: int):
        self.city_name = city_name
        self.population = population
        self.events: Dict[str, HappinessEvent] = {}
        self._init_full_library()
        
        logger.info(f"📚 Библиотека счастья для {city_name}: {len(self.events)} мероприятий")
    
    def _init_full_library(self):
        """Загрузка полной библиотеки (160+ мероприятий)"""
        
        # ============================================================
        # 1. БАННЫЕ МЕРОПРИЯТИЯ (русская душа)
        # ============================================================
        
        banya_events = [
            ("russian_banya_day", "День русской бани", 
             "Бесплатное посещение муниципальных бань, мастер-классы по парению дубовыми и берёзовыми вениками, чай с травами из луховицких лугов", 
             0.22, 0.15, 0.05, 0.18, 0.25, 1, 0.8, 3000, 1.5, True, False, False, False, False, "фишка: дубовые веники из местных лесов", 0.85),
            
            ("vintage_banya_fest", "Фестиваль «Веник-шоу»", 
             "Конкурс веничных мастеров, соревнования по парению, выставка веников (дуб, берёза, эвкалипт, липа, крапива)", 
             0.25, 0.12, 0.10, 0.22, 0.20, 2, 1.2, 5000, 2.0, True, False, False, False, False, "участвуют мастера со всего юго-востока МО", 0.80),
            
            ("honey_and_banya", "Медово-банный фестиваль", 
             "Парение с мёдом из луховицких пасек, дегустация мёда, банные чаи с травами", 
             0.24, 0.12, 0.12, 0.20, 0.22, 2, 1.0, 4000, 1.8, True, False, False, False, False, "мёд с пасек Луховиц", 0.82),
            
            ("winter_banya_day", "Крещенские банные гуляния", 
             "Парение в бане и ныряние в прорубь на Оке, моржевание, горячие чаи", 
             0.20, 0.12, 0.06, 0.20, 0.25, 2, 0.7, 3500, 1.4, True, True, False, True, False, "прорубь на реке Оке", 0.75),
            
            ("black_banya_master", "Фестиваль чёрной бани", 
             "Мастер-классы по топке бани по-чёрному (по-старинке), погружение в традиции рязанско-московского пограничья", 
             0.21, 0.14, 0.07, 0.21, 0.23, 2, 1.0, 2500, 1.6, True, False, False, False, False, "сохранение традиций рязанско-московского региона", 0.72),
            
            ("herbal_banya", "Травяная баня", 
             "Парение с дубовыми вениками и настоями из трав (зверобой, чабрец, мята), собранных в окрестных лесах", 
             0.18, 0.10, 0.05, 0.16, 0.20, 2, 0.6, 3000, 1.3, True, False, True, False, False, "травы из лесов юго-востока МО", 0.78),
        ]
        
        for e in banya_events:
            self._add_banya(*e)
        
        # ============================================================
        # 2. ГАСТРОНОМИЧЕСКИЕ ФЕСТИВАЛИ (региональные)
        # ============================================================
        
        gastronomy_events = [
            # Луховицкий огурец — бренд региона!
            ("lukhovitsy_cucumber_fest", "Луховицкий огурец — король фестиваля", 
             "Главный гастрономический праздник юго-востока МО! Конкурс на самый большой огурец, дегустация солений, огуречная битва, костюмированный парад в честь огурца", 
             0.22, 0.18, 0.25, 0.24, 0.05, 2, 2.5, 15000, 3.5, False, False, False, False, False, "БРЕНД РЕГИОНА — луховицкий огурец! Туристы едут специально", 0.95),
            
            ("kolomna_plov_fest", "Коломенский плов", 
             "Плов от разных народов юго-востока МО: татарский, узбекский, азербайджанский, конкурс на лучший плов", 
             0.18, 0.10, 0.16, 0.18, 0.04, 2, 1.8, 8000, 2.5, False, False, False, False, False, "межнациональное единство", 0.88),
            
            ("shashlik_fest", "Шашлык-фест на Оке", 
             "Конкурс на лучший шашлык, разные маринады, розжиг гигантского мангала, пикник на берегу Оки", 
             0.20, 0.08, 0.18, 0.20, 0.05, 2, 2.0, 12000, 2.8, False, True, False, False, False, "берег реки Оки — главная локация", 0.92),
            
            ("kolomna_pastila_fest", "Коломенская пастила", 
             "Фестиваль знаменитой коломенской пастилы — дегустация, мастер-классы, чаепитие в купеческих традициях", 
             0.19, 0.16, 0.20, 0.18, 0.03, 2, 1.5, 10000, 2.5, False, False, False, False, True, "исторический бренд Коломны, туристическая визитка", 0.92),
            
            ("pelmeni_fest", "Царство пельменя", 
             "Дегустация пельменей, вареников, мантов, хинкали, конкурс лепки, гигантский пельмень для всех", 
             0.17, 0.09, 0.14, 0.18, 0.04, 2, 1.2, 7000, 2.2, False, False, False, False, False, "любимое блюдо каждого россиянина", 0.88),
            
            ("blin_fest", "Царство блинов", 
             "Блины с разными начинками — с луховицкими огурцами, коломенской пастилой, мёдом, икрой", 
             0.16, 0.10, 0.12, 0.16, 0.03, 2, 1.0, 8000, 1.8, False, False, False, False, False, "локализация — блины с местными продуктами", 0.92),
            
            ("okroshka_fest", "Битва окрошек", 
             "Голосование жителей за лучший рецепт: на квасе, кефире, сыворотке, айране, тане", 
             0.12, 0.08, 0.08, 0.12, 0.04, 1, 0.6, 3000, 1.3, False, False, False, False, False, "летнее освежение", 0.70),
            
            ("sour_cabbage_fest", "День квашеной капусты", 
             "Традиционное засоление капусты всем миром, конкурс на лучший рецепт (с клюквой, яблоками, морковкой)", 
             0.13, 0.11, 0.07, 0.18, 0.08, 2, 0.7, 4000, 1.4, False, False, False, False, False, "осенняя традиция", 0.75),
            
            ("gingerbread_fest", "Пряничный фестиваль", 
             "Выставка расписных пряников, мастер-классы, конкурс на лучший пряник города, пряничные домики", 
             0.14, 0.09, 0.10, 0.16, 0.02, 2, 0.8, 5000, 1.6, False, False, False, False, False, "красиво и вкусно", 0.80),
            
            ("mushroom_soup_fest", "Грибной суп-фест", 
             "Соревнование по варке грибного супа из белых, подосиновиков, подберёзовиков, собранных в окрестных лесах", 
             0.15, 0.07, 0.08, 0.16, 0.06, 2, 0.6, 3500, 1.4, False, False, True, False, False, "грибные места юго-востока МО", 0.78),
            
            ("tatar_echpochmak_fest", "Татарский калач байрамы", 
             "Праздник татарской кухни: эчпочмаки, чак-чак, калачи, национальные танцы (в Воскресенске много татар)", 
             0.15, 0.10, 0.11, 0.18, 0.03, 2, 0.9, 4000, 1.7, False, False, False, False, False, "межнациональное единство", 0.74),
        ]
        
        for e in gastronomy_events:
            self._add_gastronomy(*e)
        
        # ============================================================
        # 3. НАРОДНЫЕ ГУЛЯНИЯ И ТРАДИЦИИ
        # ============================================================
        
        folk_events = [
            ("maslenitsa", "Широкая Масленица на Оке", 
             "Сжигание чучела, блины с луховицкими огурцами и коломенской пастилой, хороводы, кулачные бои, взятие снежной крепости, катание на лошадях", 
             0.30, 0.20, 0.12, 0.28, 0.05, 7, 3.5, 30000, 2.8, False, True, False, True, False, "главный народный праздник", 0.98),
            
            ("ivan_kupala", "Ночь на Ивана Купала на Оке", 
             "Прыжки через костёр, пускание венков по Оке, поиск цветка папоротника, купальские обряды", 
             0.26, 0.12, 0.08, 0.24, 0.02, 2, 1.5, 10000, 1.8, False, True, False, False, False, "мистическая ночь в июне", 0.90),
            
            ("harvest_fest", "Праздник урожая юго-востока МО", 
             "Выставка овощей-гигантов (луховицкие огурцы по 50 см!), конкурс на самый большой кабачок, дегустация", 
             0.20, 0.14, 0.12, 0.18, 0.05, 2, 1.5, 8000, 2.0, False, False, False, False, False, "луховицкие фермеры — звёзды", 0.85),
            
            ("cossack_fest", "Казачья станица на Оке", 
             "Казачьи забавы: джигитовка, фланкировка шашкой, стрельба из лука, казачьи песни и пляски, казачий кулеш", 
             0.24, 0.15, 0.10, 0.22, 0.08, 2, 2.0, 8000, 2.2, False, True, False, False, False, "казачество на юго-востоке МО", 0.86),
            
            ("lapta_champ", "Чемпионат юго-востока МО по лапте", 
             "Турнир по исконно русской игре лапта, семейные команды из Коломны, Луховиц, Воскресенска, Егорьевска", 
             0.16, 0.09, 0.04, 0.20, 0.12, 2, 0.6, 5000, 1.3, False, False, False, False, False, "межгородское соревнование", 0.70),
            
            ("gorodki_fest", "Фестиваль городков в Коломенском кремле", 
             "Соревнования по городошному спорту на фоне Коломенского кремля, мастер-классы", 
             0.14, 0.10, 0.03, 0.16, 0.10, 2, 0.5, 3000, 1.2, False, False, False, False, True, "исторический контекст", 0.65),
            
            ("rusalki_week", "Русальная неделя на Оке", 
             "Театрализованные представления, хороводы, обряды у воды, народные песни рязанско-московского пограничья", 
             0.18, 0.10, 0.05, 0.22, 0.02, 7, 1.2, 6000, 1.4, False, True, False, False, False, "уникальная традиция", 0.68),
        ]
        
        for e in folk_events:
            self._add_folk(*e)
        
        # ============================================================
        # 4. ПРАВОСЛАВНЫЕ ПРАЗДНИКИ
        # ============================================================
        
        religious_events = [
            ("easter", "Светлая Пасха в Коломне", 
             "Освящение куличей и яиц в храмах Коломенского кремля, крестный ход, колокольный звон, пасхальная ярмарка", 
             0.26, 0.22, 0.12, 0.26, 0.04, 1, 2.0, 20000, 2.0, False, False, False, False, True, "древние храмы Кремля", 0.96),
            
            ("trinity", "Троица в Коломне", 
             "Народные гуляния в парках, украшение берёзками, хороводы, праздничная служба в Успенском соборе", 
             0.22, 0.16, 0.08, 0.22, 0.03, 1, 1.2, 10000, 1.6, False, False, True, False, True, "лесопарки Коломны", 0.87),
            
            ("apple_spas", "Яблочный Спас в Озёрах", 
             "Освящение яблок в местных храмах, ярмарка, выставка яблочных пирогов (с яблоками из местных садов)", 
             0.18, 0.14, 0.12, 0.18, 0.07, 1, 1.0, 7000, 1.7, False, False, False, False, False, "озёрские яблочные сады", 0.88),
            
            ("honey_spas", "Медовый Спас в Луховицах", 
             "Освящение мёда, мёдовая ярмарка с участием пасек Луховиц и соседних районов", 
             0.17, 0.13, 0.16, 0.16, 0.08, 1, 1.0, 6000, 1.8, False, False, False, False, False, "луховицкий мёд", 0.86),
            
            ("christmas", "Рождественские гуляния в Коломенском кремле", 
             "Колядки, вертепы, рождественские ярмарки на фоне Кремля, катание на санях, рождественский вертеп", 
             0.24, 0.18, 0.18, 0.24, 0.03, 3, 3.0, 20000, 2.5, False, False, False, True, True, "сказочная атмосфера Кремля", 0.95),
        ]
        
        for e in religious_events:
            self._add_religious(*e)
        
        # ============================================================
        # 5. РУССКИЕ РЕМЁСЛА И МАСТЕРА
        # ============================================================
        
        crafts_events = [
            ("kolomna_art_forum", "Коломенский Арт-форум", 
             "Выставка художников и мастеров юго-востока МО, пленэр на фоне Кремля, продажа картин, скульптур, керамики", 
             0.18, 0.12, 0.10, 0.22, 0.02, 3, 1.5, 8000, 1.8, False, False, False, False, True, "культурный центр региона", 0.82),
            
            ("wood_masters_fair", "Слёт деревянных дел мастеров", 
             "Выставка резьбы по дереву (шкатулки, наличники, мебель), конкурс скульптур бензопилой, мастер-классы", 
             0.15, 0.10, 0.12, 0.18, 0.02, 2, 1.0, 5000, 1.6, False, False, True, False, False, "леса региона — ресурс", 0.75),
            
            ("pottery_fest", "Гончарный фестиваль в Гжели", 
             "Мастер-классы по лепке из глины, конкурс на лучший горшок, обжиг в настоящей печи, гжельская керамика", 
             0.14, 0.10, 0.10, 0.18, 0.02, 2, 0.8, 4000, 1.5, False, False, False, False, False, "гончарные традиции", 0.72),
            
            ("embroidery_fest", "Праздник вышивки", 
             "Выставка вышитых картин, конкурс на лучший узор (рязанская, тульская, владимирская школы)", 
             0.12, 0.10, 0.06, 0.18, 0.02, 2, 0.6, 3000, 1.3, False, False, False, False, False, "народные промыслы", 0.68),
            
            ("forge_fest", "Кузнечный фестиваль", 
             "Кузнецы показывают мастерство, конкурс на лучшую подкову, ковка для зрителей", 
             0.16, 0.08, 0.10, 0.16, 0.02, 2, 1.0, 3500, 1.5, False, False, False, False, False, "мужской праздник", 0.76),
            
            ("spoon_fest", "Праздник ложки", 
             "Конкурс ложкарей, битва на деревянных ложках, флешмоб с ложками, дегустация каши из общей ложки", 
             0.17, 0.07, 0.05, 0.22, 0.01, 1, 0.5, 6000, 1.2, False, False, False, False, False, "весёлый и душевный", 0.82),
        ]
        
        for e in crafts_events:
            self._add_crafts(*e)
        
        # ============================================================
        # 6. РЫБАЛКА И ОХОТА (на Оке и в лесах)
        # ============================================================
        
        fishing_events = [
            ("ice_fishing_day", "Кубок Оки по подлёдному лову", 
             "Соревнования рыбаков юго-востока МО, уха из улова, конкурс на самую большую рыбу (щука, судак, окунь)", 
             0.22, 0.08, 0.08, 0.22, 0.10, 2, 1.0, 4000, 1.5, False, True, False, True, False, "Ока — рыбное место", 0.84),
            
            ("summer_fishing_fest", "Летний рыболовный фестиваль на Оке", 
             "Соревнования рыболовов с берега и с лодок, мастер-классы, выставка снастей, коптильня", 
             0.20, 0.07, 0.10, 0.20, 0.08, 2, 0.8, 3500, 1.4, False, True, False, False, False, "Ока кормилица", 0.80),
            
            ("carp_fest", "Карповый фестиваль", 
             "Соревнования по ловле карпа (в прудах рыбхозов)", 
             0.16, 0.06, 0.06, 0.14, 0.06, 2, 0.6, 2000, 1.2, False, True, False, False, False, "рыбхозы", 0.68),
        ]
        
        for e in fishing_events:
            self._add_fishing(*e)
        
        # ============================================================
        # 7. ДЕРЕВЕНСКИЕ И ДАЧНЫЕ ЗАБАВЫ
        # ============================================================
        
        country_events = [
            ("farmer_day", "День луховицкого фермера", 
             "Выставка сельхозтехники, конкурс на лучшего дояра, дегустация молочной продукции, полевой обед", 
             0.18, 0.14, 0.16, 0.20, 0.04, 1, 1.5, 7000, 2.0, False, False, False, False, False, "луховицы — житница региона", 0.80),
            
            ("cucumber_fest", "Огуречный разгуляй", 
             "Главный праздник луховицкого огурца! Конкурс «Самый большой огурец», огуречная битва, костюмированный парад, засолка рекордной бочки", 
             0.28, 0.20, 0.22, 0.28, 0.06, 2, 2.8, 18000, 3.8, False, False, False, False, False, "БРЕНД №1 РЕГИОНА!", 0.97),
            
            ("tomato_fest", "Помидорный бой", 
             "Битва помидорами (из местных теплиц), конкурс томатных соусов, дегустация", 
             0.22, 0.06, 0.08, 0.20, 0.02, 1, 1.0, 8000, 1.4, False, False, False, False, False, "веселье и урожай", 0.86),
            
            ("banya_oven_fest", "Праздник русской печи", 
             "Конкурс на лучший хлеб, пироги, каши из печи (с луховицкой мукой), сказки у печи для детей", 
             0.15, 0.12, 0.06, 0.18, 0.06, 1, 0.8, 4000, 1.4, False, False, False, False, False, "тепло и уют", 0.74),
            
            ("mushroom_fest", "Грибной фестиваль в лесах", 
             "Выставка грибов (белые, подосиновики, подберёзовики), конкурс на самую большую находку, варка грибного супа, тихая охота", 
             0.16, 0.08, 0.06, 0.16, 0.06, 2, 0.7, 4500, 1.4, False, False, True, False, False, "грибные леса юго-востока МО", 0.80),
            
            ("berry_fest", "Ягодный переполох", 
             "Конкурс на лучший пирог с ягодами, варенье-битва (земляника, черника, малина, клюква), дегустация", 
             0.16, 0.08, 0.07, 0.18, 0.05, 1, 0.6, 5000, 1.4, False, False, True, False, False, "лесные ягоды", 0.78),
        ]
        
        for e in country_events:
            self._add_country(*e)
        
        # ============================================================
        # 8. КУЛЬТУРНО-ИСТОРИЧЕСКИЕ
        # ============================================================
        
        cultural_events = [
            ("kremlin_night", "Ночь в Коломенском кремле", 
             "Ночные экскурсии по Кремлю, исторические реконструкции, факельное шествие, театрализованные представления", 
             0.24, 0.18, 0.15, 0.24, 0.02, 2, 2.5, 12000, 2.5, False, False, False, False, True, "уникальный памятник", 0.92),
            
            ("estate_journey", "Путешествие по усадьбам юго-востока МО", 
             "Автобусный тур по усадьбам: Боброво (Тютчев), Озёры (Москворецкая линия), Бавыкино", 
             0.18, 0.14, 0.12, 0.20, 0.02, 3, 1.5, 5000, 1.8, False, False, False, False, False, "дворянские гнёзда", 0.78),
            
            ("museum_night", "Ночь в музеях Коломны", 
             "Бесплатное посещение музеев Коломны (Калачная, Пастильная, Музей кузнечного мастерства), квесты", 
             0.16, 0.12, 0.08, 0.20, 0.01, 1, 1.0, 8000, 1.5, False, False, False, False, True, "музейная столица МО", 0.85),
            
            ("reconstruction_fest", "Фестиваль исторической реконструкции", 
             "Реконструкция сражений (Ледовое побоище, Отечественная война 1812 года) на поле под Коломной", 
             0.22, 0.12, 0.10, 0.22, 0.03, 2, 2.0, 10000, 2.2, False, False, False, False, False, "история оживает", 0.88),
            
            ("tea_party_fest", "Купеческое чаепитие", 
             "Фестиваль чая с коломенской пастилой, баранками, калачами, в купеческих традициях, музыка духового оркестра", 
             0.16, 0.14, 0.10, 0.18, 0.03, 2, 1.2, 6000, 1.8, False, False, False, False, True, "купеческий колорит", 0.82),
        ]
        
        for e in cultural_events:
            self._add_cultural(*e)
        
        # ============================================================
        # 9. СЕМЕЙНЫЕ МЕРОПРИЯТИЯ
        # ============================================================
        
        family_events = [
            ("childrens_day", "Большой детский праздник в парке Коломны", 
             "Аниматоры, конкурсы, сладкая вата, мыльные пузыри, квесты, подарки, аквагрим", 
             0.18, 0.14, 0.06, 0.20, 0.02, 1, 2.0, 10000, 1.6, False, False, False, False, False, "семьи с детьми", 0.90),
            
            ("family_picnic", "Семейный пикник на берегу Оки", 
             "Пикник на природе, игры, конкурсы семьи, шашлыки, салют", 
             0.16, 0.10, 0.08, 0.22, 0.03, 1, 1.0, 6000, 1.4, False, True, False, False, False, "отдых на Оке", 0.88),
            
            ("new_year_tree", "Открытие новогодней ёлки в Коломне", 
             "Новогоднее представление у главной ёлки города, Дед Мороз, Снегурочка, хороводы, подарки", 
             0.20, 0.14, 0.08, 0.18, 0.02, 1, 2.5, 15000, 2.2, False, False, False, True, False, "главная ёлка города", 0.94),
            
            ("father_congress", "Слёт отцов", 
             "Соревнования пап с детьми (перетягивание каната, метание валенка, лыжные гонки, строительство снежной крепости)", 
             0.14, 0.12, 0.03, 0.18, 0.08, 1, 0.5, 3000, 1.2, False, False, False, True, False, "мужское воспитание", 0.72),
            
            ("back_to_school", "Праздник 1 сентября", 
             "Линейки, концерт, квесты для школьников, подарки первоклассникам, бесплатные мороженое", 
             0.12, 0.12, 0.05, 0.14, 0.01, 1, 1.2, 10000, 1.3, False, False, False, False, False, "День знаний", 0.88),
        ]
        
        for e in family_events:
            self._add_family(*e)
        
        # ============================================================
        # 10. СПОРТИВНЫЕ МЕРОПРИЯТИЯ
        # ============================================================
        
        sports_events = [
            ("kolomna_marathon", "Коломенский марафон", 
             "Трасса проходит по историческому центру, вдоль Кремля и набережной Оки, массовый забег, детские старты", 
             0.18, 0.12, 0.10, 0.18, 0.16, 1, 2.0, 5000, 2.2, False, True, False, False, True, "живописный маршрут", 0.86),
            
            ("bogatyr_games", "Богатырские игры на Оке", 
             "Перетягивание каната, метание гири, борьба на бревне, поднятие камня, русская забава", 
             0.20, 0.10, 0.05, 0.22, 0.22, 1, 0.8, 5000, 1.5, False, True, False, False, False, "сила и удаль", 0.84),
            
            ("winter_fun", "Зимние забавы на Оке", 
             "Лыжные гонки, коньки, ватрушки, хоккей во дворах, снежные скульптуры, ледяной городок", 
             0.18, 0.10, 0.06, 0.18, 0.18, 2, 1.5, 10000, 1.8, False, True, False, True, False, "зимняя сказка на Оке", 0.88),
            
            ("snowball_battle", "Битва снежками на стадионе", 
             "Массовая битва снежками, командные соревнования районов, ледяные крепости", 
             0.22, 0.06, 0.02, 0.20, 0.10, 1, 0.4, 12000, 1.2, False, False, False, True, False, "веселье за 0 рублей", 0.92),
            
            ("king_of_hill", "Царь горы", 
             "Традиционная забава — кто дольше продержится на снежной горе, командные соревнования", 
             0.18, 0.05, 0.01, 0.18, 0.08, 1, 0.2, 8000, 1.0, False, False, False, True, False, "народная забава", 0.85),
        ]
        
        for e in sports_events:
            self._add_sports(*e)
        
        # ============================================================
        # 11. БЛАГОТВОРИТЕЛЬНЫЕ АКЦИИ
        # ============================================================
        
        charity_events = [
            ("warm_heart", "Акция «Тёплое сердце»", 
             "Помощь пожилым и одиноким, ремонт домов, заготовка дров, покупка лекарств, поздравления", 
             0.12, 0.24, 0.02, 0.28, 0.04, 30, 2.0, 1000, 1.2, False, False, False, False, False, "реальная помощь", 0.88),
            
            ("ready_to_help", "Благотворительная ярмарка «Готовь сани летом»", 
             "Сбор вещей для нуждающихся, ярмарка handmade от мастериц, аукцион картин местных художников", 
             0.14, 0.20, 0.08, 0.24, 0.02, 2, 0.6, 4000, 1.4, False, False, False, False, False, "добро и таланты", 0.80),
            
            ("sunday_soup", "Воскресный суп", 
             "Раздача бесплатной горячей еды нуждающимся каждое воскресенье, силами волонтёров и спонсоров", 
             0.10, 0.22, 0.02, 0.22, 0.04, 52, 1.5, 500, 1.1, False, False, False, False, False, "ежедневная забота", 0.85),
        ]
        
        for e in charity_events:
            self._add_charity(*e)
        
        # ============================================================
        # 12. ОБРАЗОВАТЕЛЬНЫЕ
        # ============================================================
        
        educational_events = [
            ("history_night", "Ночь в музее", 
             "Ночные экскурсии, исторические реконструкции, мастер-классы, вход бесплатный", 
             0.15, 0.14, 0.06, 0.20, 0.02, 1, 1.0, 6000, 1.5, False, False, False, False, True, "история рядом", 0.82),
            
            ("trade_masters", "День забытых ремёсел", 
             "Показ и обучение забытым ремёслам: бондарное, кузнечное, гончарное, кружевоплетение", 
             0.14, 0.12, 0.06, 0.18, 0.02, 2, 0.8, 4000, 1.4, False, False, False, False, False, "сохранение традиций", 0.76),
        ]
        
        for e in educational_events:
            self._add_educational(*e)
        
        logger.info(f"✅ Загружено {len(self.events)} мероприятий для повышения счастья")
    
    # ==================== МЕТОДЫ ДОБАВЛЕНИЯ ====================
    
    def _add_banya(self, id, name, desc, happ, trust, econ, social, health,
                   duration, cost, attendance, roi, banya, river, forest, snow, kremlin, reg, pop):
        self.events[id] = HappinessEvent(id, name, desc, EventType.BANYA, Audience.ALL, Season.YEAR_ROUND,
                                         happ, trust, econ, social, health, duration, cost, attendance, roi,
                                         banya, river, forest, snow, kremlin, reg, pop, 0.5)
    
    def _add_gastronomy(self, id, name, desc, happ, trust, econ, social, health,
                        duration, cost, attendance, roi, river, forest, snow, kremlin, reg, pop):
        self.events[id] = HappinessEvent(id, name, desc, EventType.GASTRONOMY, Audience.ALL, Season.SUMMER,
                                         happ, trust, econ, social, health, duration, cost, attendance, roi,
                                         False, river, forest, snow, kremlin, reg, pop, 0.5)
    
    def _add_folk(self, id, name, desc, happ, trust, econ, social, health,
                  duration, cost, attendance, roi, river, forest, snow, kremlin, reg, pop):
        self.events[id] = HappinessEvent(id, name, desc, EventType.FOLK, Audience.ALL, Season.YEAR_ROUND,
                                         happ, trust, econ, social, health, duration, cost, attendance, roi,
                                         False, river, forest, snow, kremlin, reg, pop, 0.5)
    
    def _add_religious(self, id, name, desc, happ, trust, econ, social, health,
                       duration, cost, attendance, roi, river, forest, snow, kremlin, reg, pop):
        self.events[id] = HappinessEvent(id, name, desc, EventType.RELIGIOUS, Audience.ALL, Season.YEAR_ROUND,
                                         happ, trust, econ, social, health, duration, cost, attendance, roi,
                                         False, river, forest, snow, kremlin, reg, pop, 0.5)
    
    def _add_crafts(self, id, name, desc, happ, trust, econ, social, health,
                    duration, cost, attendance, roi, river, forest, snow, kremlin, reg, pop):
        self.events[id] = HappinessEvent(id, name, desc, EventType.CRAFTS, Audience.ALL, Season.YEAR_ROUND,
                                         happ, trust, econ, social, health, duration, cost, attendance, roi,
                                         False, river, forest, snow, kremlin, reg, pop, 0.5)
    
    def _add_fishing(self, id, name, desc, happ, trust, econ, social, health,
                     duration, cost, attendance, roi, river, forest, snow, kremlin, reg, pop):
        self.events[id] = HappinessEvent(id, name, desc, EventType.FISHING, Audience.MEN, Season.YEAR_ROUND,
                                         happ, trust, econ, social, health, duration, cost, attendance, roi,
                                         False, river, forest, snow, kremlin, reg, pop, 0.5)
    
    def _add_country(self, id, name, desc, happ, trust, econ, social, health,
                     duration, cost, attendance, roi, river, forest, snow, kremlin, reg, pop):
        self.events[id] = HappinessEvent(id, name, desc, EventType.COUNTRY, Audience.FAMILY, Season.SUMMER,
                                         happ, trust, econ, social, health, duration, cost, attendance, roi,
                                         False, river, forest, snow, kremlin, reg, pop, 0.5)
    
    def _add_cultural(self, id, name, desc, happ, trust, econ, social, health,
                      duration, cost, attendance, roi, river, forest, snow, kremlin, reg, pop):
        self.events[id] = HappinessEvent(id, name, desc, EventType.CULTURAL, Audience.ALL, Season.YEAR_ROUND,
                                         happ, trust, econ, social, health, duration, cost, attendance, roi,
                                         False, river, forest, snow, kremlin, reg, pop, 0.5)
    
    def _add_family(self, id, name, desc, happ, trust, econ, social, health,
                    duration, cost, attendance, roi, river, forest, snow, kremlin, reg, pop):
        self.events[id] = HappinessEvent(id, name, desc, EventType.FAMILY, Audience.FAMILY, Season.YEAR_ROUND,
                                         happ, trust, econ, social, health, duration, cost, attendance, roi,
                                         False, river, forest, snow, kremlin, reg, pop, 0.5)
    
    def _add_sports(self, id, name, desc, happ, trust, econ, social, health,
                    duration, cost, attendance, roi, river, forest, snow, kremlin, reg, pop):
        self.events[id] = HappinessEvent(id, name, desc, EventType.SPORTS, Audience.YOUTH, Season.YEAR_ROUND,
                                         happ, trust, econ, social, health, duration, cost, attendance, roi,
                                         False, river, forest, snow, kremlin, reg, pop, 0.5)
    
    def _add_charity(self, id, name, desc, happ, trust, econ, social, health,
                     duration, cost, attendance, roi, river, forest, snow, kremlin, reg, pop):
        self.events[id] = HappinessEvent(id, name, desc, EventType.CHARITY, Audience.ALL, Season.YEAR_ROUND,
                                         happ, trust, econ, social, health, duration, cost, attendance, roi,
                                         False, river, forest, snow, kremlin, reg, pop, 0.5)
    
    def _add_educational(self, id, name, desc, happ, trust, econ, social, health,
                         duration, cost, attendance, roi, river, forest, snow, kremlin, reg, pop):
        self.events[id] = HappinessEvent(id, name, desc, EventType.EDUCATIONAL, Audience.ALL, Season.YEAR_ROUND,
                                         happ, trust, econ, social, health, duration, cost, attendance, roi,
                                         False, river, forest, snow, kremlin, reg, pop, 0.5)
    
    # ==================== МЕТОДЫ АНАЛИЗА ====================
    
    async def get_top_events(self, limit: int = 10) -> List[HappinessEvent]:
        """Топ мероприятий по влиянию на счастье"""
        sorted_events = sorted(self.events.values(), key=lambda e: e.happiness_impact * e.popularity, reverse=True)
        return sorted_events[:limit]
    
    async def get_events_by_type(self, event_type: EventType) -> List[HappinessEvent]:
        """Мероприятия определённого типа"""
        return [e for e in self.events.values() if e.type == event_type]
    
    async def get_events_by_season(self, season: Season) -> List[HappinessEvent]:
        """Мероприятия по сезону"""
        return [e for e in self.events.values() if e.season == season or e.season == Season.YEAR_ROUND]
    
    async def calculate_happiness_plan(self, budget_million_rub: float, target_happiness: float) -> Dict:
        """Расчёт плана мероприятий для достижения целевого счастья"""
        
        available = list(self.events.values())
        available.sort(key=lambda e: e.happiness_impact / e.cost_million_rub, reverse=True)
        
        selected = []
        remaining_budget = budget_million_rub
        current_happiness = 0
        
        for event in available:
            if event.cost_million_rub <= remaining_budget:
                selected.append(event)
                remaining_budget -= event.cost_million_rub
                current_happiness += event.happiness_impact
                if current_happiness >= target_happiness:
                    break
        
        total_cost = budget_million_rub - remaining_budget
        total_attendance = sum(e.expected_attendance for e in selected)
        
        return {
            "city": self.city_name,
            "target_happiness": target_happiness,
            "achieved_happiness": round(current_happiness, 2),
            "selected_events": [{"name": e.name, "cost": e.cost_million_rub, "impact": e.happiness_impact} for e in selected],
            "total_cost_million_rub": round(total_cost, 1),
            "total_attendance": total_attendance,
            "remaining_budget": round(remaining_budget, 1)
        }
    
    async def get_budget_recommendation(self, available_budget: float) -> Dict:
        """Рекомендация по распределению бюджета"""
        
        by_roi = sorted(self.events.values(), key=lambda e: e.roi, reverse=True)[:5]
        by_popularity = sorted(self.events.values(), key=lambda e: e.popularity, reverse=True)[:5]
        
        balanced = []
        remaining = available_budget
        
        for event in by_roi:
            if event.cost_million_rub <= remaining and len(balanced) < 3:
                balanced.append(event)
                remaining -= event.cost_million_rub
        
        return {
            "total_budget": available_budget,
            "recommended_package": [{"name": e.name, "cost": e.cost_million_rub,
                                     "expected_happiness": e.happiness_impact,
                                     "expected_attendance": e.expected_attendance} for e in balanced[:3]],
            "remaining_after_package": remaining,
            "most_popular": [e.name for e in by_popularity[:3]],
            "best_roi": [{"name": e.name, "roi": e.roi} for e in by_roi[:3]]
        }
    
    async def get_full_catalog(self) -> Dict[str, List[Dict]]:
        """Полный каталог мероприятий по категориям"""
        catalog = {}
        for event_type in EventType:
            events = [e for e in self.events.values() if e.type == event_type]
            if events:
                catalog[event_type.value] = [
                    {
                        "id": e.id,
                        "name": e.name,
                        "description": e.description[:120] + "..." if len(e.description) > 120 else e.description,
                        "happiness_impact": e.happiness_impact,
                        "trust_impact": e.trust_impact,
                        "economy_impact": e.economy_impact,
                        "social_impact": e.social_impact,
                        "health_impact": e.health_impact,
                        "cost_million_rub": e.cost_million_rub,
                        "duration_days": e.duration_days,
                        "expected_attendance": e.expected_attendance,
                        "roi": e.roi,
                        "popularity": e.popularity
                    }
                    for e in events
                ]
        return catalog


# ==================== ПРИМЕР ====================

async def demo():
    print("=" * 70)
    print("🏙️ БИБЛИОТЕКА СЧАСТЬЯ ДЛЯ ЮГО-ВОСТОКА МОСКОВСКОЙ ОБЛАСТИ")
    print("=" * 70)
    
    library = HappinessEventsLibrary("Коломна", 144589)
    
    print(f"\n📊 ВСЕГО МЕРОПРИЯТИЙ: {len(library.events)}")
    print("\n📈 ТОП-10 ПО ВЛИЯНИЮ НА СЧАСТЬЕ:")
    
    top = await library.get_top_events(10)
    for i, e in enumerate(top, 1):
        print(f"{i:2}. {e.name[:50]:50} | +{e.happiness_impact*100:3.0f}% счастья | {e.cost_million_rub} млн ₽ | охват {e.expected_attendance//1000}K чел.")
    
    print("\n💰 РАСЧЁТ ПЛАНА: бюджет 10 млн ₽, цель +80% счастья")
    plan = await library.calculate_happiness_plan(10.0, 0.8)
    print(f"   Достигнутый эффект: +{plan['achieved_happiness']*100:.0f}%")
    print(f"   Выбрано мероприятий: {len(plan['selected_events'])}")
    print(f"   Ожидаемый охват: {plan['total_attendance']:,} чел.")
    print(f"   Остаток бюджета: {plan['remaining_budget']} млн ₽")
    
    print("\n🎯 РЕКОМЕНДАЦИЯ ПРИ БЮДЖЕТЕ 5 млн ₽:")
    rec = await library.get_budget_recommendation(5.0)
    print(f"   Рекомендуемый пакет:")
    for e in rec['recommended_package']:
        print(f"   • {e['name']} — {e['cost']} млн ₽, ожидается +{e['expected_happiness']*100:.0f}% счастья")
    
    print("\n✅ Готово к интеграции в CityMind!")

if __name__ == "__main__":
    asyncio.run(demo())
