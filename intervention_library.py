#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
МОДУЛЬ 5: БИБЛИОТЕКА ИНТЕРВЕНЦИЙ ДЛЯ ГОРОДОВ (intervention_library.py)
Содержит интервенции для разрыва петель и работы с городскими системами
Адаптировано для городского планирования и управления
"""

import random
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class CityInterventionLibrary:
    """
    Библиотека интервенций для разрыва городских петель
    
    Используется для:
    - Подбора интервенций по типу городской петли
    - Персонализации под профиль города
    - Ежедневных практик для администрации
    - Недельных программ развития
    """
    
    def __init__(self):
        """Инициализация библиотеки"""
        self.interventions = self._build_library()
        self.projects = self._build_projects()
        self.quotes = self._build_quotes()
        self.practices = self._build_practices()
        self.metrics = self._build_metrics()
        
        logger.info("CityInterventionLibrary инициализирована")
    
    def _build_library(self) -> Dict[str, Any]:
        """
        Строит библиотеку интервенций по типам городских петель
        """
        return {
            # Для петли безопасность-экономика
            'safety_economy_cycle': {
                'name': 'Петля безопасности и экономики',
                'description': 'Проблемы безопасности отпугивают бизнес → экономический спад → рост преступности',
                'break_points': [2, 3, 1],
                'interventions': {
                    2: {
                        'name': 'Программа "Безопасный город"',
                        'description': 'Системное повышение безопасности через технологии и сообщества',
                        'project': 'Установка систем видеонаблюдения, увеличение патрулей, программа "Соседский дозор"',
                        'duration': '6-12 месяцев',
                        'difficulty': 'Средняя',
                        'budget': 'Средний',
                        'expected': 'Снижение преступности на 20-30%, рост доверия жителей',
                        'city_level': 'Тактический'
                    },
                    3: {
                        'name': 'Экономическая поддержка МСП',
                        'description': 'Помощь малому бизнесу для создания рабочих мест',
                        'project': 'Создание фонда поддержки, налоговые льготы, гранты для предпринимателей',
                        'duration': '12-24 месяца',
                        'difficulty': 'Высокая',
                        'budget': 'Высокий',
                        'expected': 'Создание 500+ рабочих мест, рост налоговых поступлений',
                        'city_level': 'Стратегический'
                    },
                    1: {
                        'name': 'Комплексное решение проблем',
                        'description': 'Системный подход к решению главных городских проблем',
                        'project': 'Создание ситуационного центра, стратегическая сессия с жителями',
                        'duration': '3-6 месяцев',
                        'difficulty': 'Средняя',
                        'budget': 'Средний',
                        'expected': 'Дорожная карта развития города',
                        'city_level': 'Стратегический'
                    }
                }
            },
            
            # Для петли качества жизни
            'quality_of_life_cycle': {
                'name': 'Петля качества жизни',
                'description': 'Экономические проблемы снижают качество жизни → отток населения → ухудшение экономики',
                'break_points': [4, 3, 5],
                'interventions': {
                    4: {
                        'name': 'Благоустройство общественных пространств',
                        'description': 'Быстрые победы для повышения комфорта жизни',
                        'project': 'Реновация парка, создание сквера, установка скамеек и освещения',
                        'duration': '3-6 месяцев',
                        'difficulty': 'Легкая',
                        'budget': 'Низкий-Средний',
                        'expected': 'Повышение удовлетворенности жителей, рост городской гордости',
                        'city_level': 'Тактический'
                    },
                    3: {
                        'name': 'Программа "Мой район"',
                        'description': 'Развитие локальной экономики и инфраструктуры',
                        'project': 'Создание локальных центров притяжения, поддержка районного бизнеса',
                        'duration': '12-18 месяцев',
                        'difficulty': 'Средняя',
                        'budget': 'Средний',
                        'expected': 'Оживление районов, снижение маятниковой миграции',
                        'city_level': 'Локальный'
                    },
                    5: {
                        'name': 'Кампания "Люблю свой город"',
                        'description': 'Формирование позитивной городской идентичности',
                        'project': 'Медиа-кампания с историями успеха, городские фестивали',
                        'duration': '6-9 месяцев',
                        'difficulty': 'Средняя',
                        'budget': 'Средний',
                        'expected': 'Рост городской гордости, снижение негативных нарративов',
                        'city_level': 'Коммуникационный'
                    }
                }
            },
            
            # Для полного порочного круга
            'full_vicious_cycle': {
                'name': 'Полный порочный круг города',
                'description': 'Все проблемы города замыкаются: страхи → экономика → качество жизни → негативные мифы',
                'break_points': [9, 5, 1],
                'interventions': {
                    9: {
                        'name': 'Разрушение городского мифа',
                        'description': 'Создание нового нарратива через реальные изменения',
                        'project': 'Разработка и внедрение нового бренда города, серия быстрых побед',
                        'duration': '12-24 месяца',
                        'difficulty': 'Очень высокая',
                        'budget': 'Высокий',
                        'expected': 'Смена восприятия города, приток инвестиций и туристов',
                        'city_level': 'Трансформационный'
                    },
                    5: {
                        'name': 'Трансформация городских нарративов',
                        'description': 'Системная работа с убеждениями жителей',
                        'project': 'Открытые форумы, стратегические сессии, работа с лидерами мнений',
                        'duration': '9-12 месяцев',
                        'difficulty': 'Высокая',
                        'budget': 'Средний',
                        'expected': 'Смена доминирующих городских нарративов',
                        'city_level': 'Коммуникационный'
                    },
                    1: {
                        'name': 'Прорывное решение главной проблемы',
                        'description': 'Фокус на ключевой проблеме города',
                        'project': 'Создание проектного офиса, привлечение экспертов, краудсорсинг решений',
                        'duration': '6-12 месяцев',
                        'difficulty': 'Высокая',
                        'budget': 'Высокий',
                        'expected': 'Прорыв в решении системной проблемы',
                        'city_level': 'Стратегический'
                    }
                }
            },
            
            # Для институциональной петли
            'institutional_cycle': {
                'name': 'Институциональная петля',
                'description': 'Негативные нарративы → неэффективные институты → деградация среды → укрепление нарративов',
                'break_points': [7, 6, 5],
                'interventions': {
                    7: {
                        'name': 'Реформа городского управления',
                        'description': 'Повышение эффективности и прозрачности институтов',
                        'project': 'Внедрение открытых данных, цифровизация услуг, обратная связь с жителями',
                        'duration': '12-18 месяцев',
                        'difficulty': 'Высокая',
                        'budget': 'Высокий',
                        'expected': 'Рост доверия к власти, повышение эффективности',
                        'city_level': 'Системный'
                    },
                    6: {
                        'name': 'Программа "Инициативное бюджетирование"',
                        'description': 'Вовлечение жителей в распределение бюджетных средств',
                        'project': 'Конкурс проектов благоустройства, обучение ТОСов',
                        'duration': '6-9 месяцев',
                        'difficulty': 'Средняя',
                        'budget': 'Средний',
                        'expected': 'Активные сообщества, реализованные проекты жителей',
                        'city_level': 'Локальный'
                    },
                    5: {
                        'name': 'Открытый диалог с жителями',
                        'description': 'Прозрачная коммуникация власти и граждан',
                        'project': 'Серия встреч в районах, онлайн-платформа для обращений',
                        'duration': '3-6 месяцев',
                        'difficulty': 'Легкая',
                        'budget': 'Низкий',
                        'expected': 'Восстановление доверия, сбор обратной связи',
                        'city_level': 'Коммуникационный'
                    }
                }
            },
            
            # Для петли социальной изоляции
            'social_isolation': {
                'name': 'Петля социальной изоляции',
                'description': 'Низкое качество жизни → миф о разобщенности → слабые институты → ухудшение жизни',
                'break_points': [4, 5, 7],
                'interventions': {
                    4: {
                        'name': 'Создание общественных центров',
                        'description': 'Места притяжения для сообществ',
                        'project': 'Открытие коворкингов, клубов по интересам, соседских центров',
                        'duration': '6-12 месяцев',
                        'difficulty': 'Средняя',
                        'budget': 'Средний',
                        'expected': 'Рост социальной активности, новые сообщества',
                        'city_level': 'Локальный'
                    },
                    5: {
                        'name': 'Кампания "Добрососедство"',
                        'description': 'Формирование культуры взаимопомощи',
                        'project': 'Дворовые праздники, конкурс "Лучший дом", чаты соседей',
                        'duration': '3-6 месяцев',
                        'difficulty': 'Легкая',
                        'budget': 'Низкий',
                        'expected': 'Укрепление соседских связей, снижение изоляции',
                        'city_level': 'Тактический'
                    },
                    7: {
                        'name': 'Поддержка НКО и волонтерства',
                        'description': 'Институциональная поддержка гражданских инициатив',
                        'project': 'Гранты для НКО, волонтерский центр, обучение активистов',
                        'duration': '12-18 месяцев',
                        'difficulty': 'Средняя',
                        'budget': 'Средний',
                        'expected': 'Рост гражданской активности, решенные социальные проблемы',
                        'city_level': 'Системный'
                    }
                }
            },
            
            # Универсальные интервенции для города
            'universal': {
                'name': 'Универсальные городские интервенции',
                'description': 'Подходят для любых городских проблем',
                'break_points': [1, 2, 3, 4, 5, 6, 7, 8, 9],
                'interventions': {
                    1: {
                        'name': 'Стратегическая сессия',
                        'description': 'Сбор всех стейкхолдеров для поиска решений',
                        'project': 'Организация форума с жителями, бизнесом, экспертами',
                        'duration': '1-2 месяца',
                        'difficulty': 'Средняя',
                        'budget': 'Средний',
                        'expected': 'Общее видение и план действий',
                        'city_level': 'Стратегический'
                    },
                    2: {
                        'name': 'Аудит безопасности',
                        'description': 'Анализ и улучшение городской безопасности',
                        'project': 'Инвентаризация проблемных мест, установка освещения и камер',
                        'duration': '3-6 месяцев',
                        'difficulty': 'Средняя',
                        'budget': 'Средний',
                        'expected': 'Повышение уровня безопасности',
                        'city_level': 'Тактический'
                    },
                    3: {
                        'name': 'Инвестиционная стратегия',
                        'description': 'Привлечение инвестиций в город',
                        'project': 'Создание инвестиционного портала, презентации для инвесторов',
                        'duration': '6-12 месяцев',
                        'difficulty': 'Высокая',
                        'budget': 'Низкий',
                        'expected': 'Рост инвестиций, новые проекты',
                        'city_level': 'Стратегический'
                    },
                    4: {
                        'name': 'Программа комфортной среды',
                        'description': 'Повышение качества городской среды',
                        'project': 'Благоустройство дворов, парков, набережных',
                        'duration': '12-24 месяца',
                        'difficulty': 'Средняя',
                        'budget': 'Высокий',
                        'expected': 'Комфортная среда для жизни',
                        'city_level': 'Тактический'
                    },
                    5: {
                        'name': 'Медиа-кампания',
                        'description': 'Формирование позитивного образа города',
                        'project': 'Создание контента о городе, работа с блогерами, городские события',
                        'duration': '6-9 месяцев',
                        'difficulty': 'Средняя',
                        'budget': 'Средний',
                        'expected': 'Изменение восприятия города',
                        'city_level': 'Коммуникационный'
                    },
                    6: {
                        'name': 'Развитие ТОС',
                        'description': 'Поддержка территориального общественного самоуправления',
                        'project': 'Обучение активистов, грантовая поддержка',
                        'duration': '12-18 месяцев',
                        'difficulty': 'Средняя',
                        'budget': 'Низкий',
                        'expected': 'Активные сообщества, решенные локальные проблемы',
                        'city_level': 'Локальный'
                    },
                    7: {
                        'name': 'Цифровая трансформация',
                        'description': 'Внедрение цифровых сервисов для жителей',
                        'project': 'Мобильное приложение, портал услуг, открытые данные',
                        'duration': '12-24 месяца',
                        'difficulty': 'Высокая',
                        'budget': 'Высокий',
                        'expected': 'Прозрачность и удобство',
                        'city_level': 'Системный'
                    },
                    8: {
                        'name': 'Межмуниципальное сотрудничество',
                        'description': 'Кооперация с соседними городами',
                        'project': 'Создание ассоциации, совместные проекты',
                        'duration': '12-36 месяцев',
                        'difficulty': 'Средняя',
                        'budget': 'Низкий',
                        'expected': 'Синергия, совместные решения',
                        'city_level': 'Стратегический'
                    },
                    9: {
                        'name': 'Ребрендинг города',
                        'description': 'Формирование новой городской идентичности',
                        'project': 'Разработка бренда, стратегия продвижения',
                        'duration': '12-24 месяца',
                        'difficulty': 'Высокая',
                        'budget': 'Средний',
                        'expected': 'Новый образ города',
                        'city_level': 'Трансформационный'
                    }
                }
            }
        }
    
    def _build_projects(self) -> Dict[str, List[Dict]]:
        """
        Строит библиотеку готовых проектов для города
        """
        return {
            'quick_wins': [
                {
                    'name': 'Светлый город',
                    'description': 'Установка LED-освещения в темных местах',
                    'duration': '2-3 месяца',
                    'budget': 'Низкий',
                    'impact': 'Высокий',
                    'timeline': 'Быстрый'
                },
                {
                    'name': 'Чистый двор',
                    'description': 'Субботники и озеленение дворов',
                    'duration': '1 месяц',
                    'budget': 'Низкий',
                    'impact': 'Средний',
                    'timeline': 'Мгновенный'
                },
                {
                    'name': 'Городские клумбы',
                    'description': 'Озеленение общественных пространств',
                    'duration': '1-2 месяца',
                    'budget': 'Низкий',
                    'impact': 'Средний',
                    'timeline': 'Быстрый'
                }
            ],
            'medium_term': [
                {
                    'name': 'Велоинфраструктура',
                    'description': 'Создание сети велодорожек',
                    'duration': '6-12 месяцев',
                    'budget': 'Средний',
                    'impact': 'Высокий',
                    'timeline': 'Средний'
                },
                {
                    'name': 'Парк технологий',
                    'description': 'Создание IT-кластера',
                    'duration': '12-18 месяцев',
                    'budget': 'Высокий',
                    'impact': 'Очень высокий',
                    'timeline': 'Средний'
                },
                {
                    'name': 'Умные остановки',
                    'description': 'Модернизация остановок с Wi-Fi и зарядками',
                    'duration': '6-9 месяцев',
                    'budget': 'Средний',
                    'impact': 'Высокий',
                    'timeline': 'Средний'
                }
            ],
            'long_term': [
                {
                    'name': 'Город-сад',
                    'description': 'Комплексное озеленение и экология',
                    'duration': '3-5 лет',
                    'budget': 'Очень высокий',
                    'impact': 'Трансформационный',
                    'timeline': 'Долгий'
                },
                {
                    'name': 'Умный город',
                    'description': 'Цифровая экосистема города',
                    'duration': '3-5 лет',
                    'budget': 'Очень высокий',
                    'impact': 'Трансформационный',
                    'timeline': 'Долгий'
                },
                {
                    'name': 'Транспортная революция',
                    'description': 'Обновление транспорта и инфраструктуры',
                    'duration': '3-7 лет',
                    'budget': 'Очень высокий',
                    'impact': 'Трансформационный',
                    'timeline': 'Долгий'
                }
            ]
        }
    
    def _build_quotes(self) -> Dict[str, List[str]]:
        """
        Строит библиотеку мотивирующих цитат для городского развития
        """
        return {
            'urban_development': [
                'Города — это возможность изменить мир. Начни с малого.',
                'Лучший способ предсказать будущее города — создать его.',
                'Каждый великий город когда-то начинался с одной идеи.',
                'Устойчивое развитие — это не тренд, а необходимость.',
                'Город — это люди. Меняя людей, меняешь город.'
            ],
            'community': [
                'Вместе мы можем больше. Город — это командная работа.',
                'Сильный город — это сильные сообщества.',
                'Каждый житель — соавтор городской среды.',
                'Доверие — главная валюта города.',
                'Соседи — это твоя первая система поддержки.'
            ],
            'leadership': [
                'Хорошие лидеры создают видение, великие — действуют.',
                'Управлять городом — значит слушать и действовать.',
                'Прозрачность рождает доверие. Доверие рождает развитие.',
                'Не жди идеального момента — начни с того, что есть.',
                'Маленькие победы создают большой импульс.'
            ],
            'innovation': [
                'Инновации — это не технологии, это новые способы решать старые проблемы.',
                'Самый рискованный шаг — не сделать никакого шага.',
                'Будущее уже здесь, оно просто неравномерно распределено.',
                'Лучший способ предсказать будущее — изобрести его.',
                'Города, которые не меняются, умирают.'
            ]
        }
    
    def _build_practices(self) -> Dict[int, Dict[str, str]]:
        """
        Строит библиотеку еженедельных практик для городской администрации
        """
        return {
            1: {
                'title': 'Анализ главной проблемы',
                'practice': 'Соберите команду для глубокого анализа главной городской проблемы. Используйте технику "5 почему".',
                'duration': '2 часа',
                'type': 'analysis'
            },
            2: {
                'title': 'Безопасность: аудит территории',
                'practice': 'Проведите пеший аудит проблемных мест с жителями. Определите топ-10 точек для быстрых решений.',
                'duration': '1 день',
                'type': 'field_work'
            },
            3: {
                'title': 'Экономика: встреча с бизнесом',
                'practice': 'Организуйте встречу с предпринимателями. Узнайте их главные барьеры и возможности.',
                'duration': '3 часа',
                'type': 'engagement'
            },
            4: {
                'title': 'Качество жизни: опрос жителей',
                'practice': 'Запустите короткий опрос о качестве жизни. Проанализируйте топ-3 жалобы и топ-3 пожелания.',
                'duration': '1 неделя',
                'type': 'research'
            },
            5: {
                'title': 'Нарративы: мониторинг СМИ',
                'practice': 'Проведите анализ городских медиа. Какие темы доминируют? Какие позитивные кейсы можно усилить?',
                'duration': '1 день',
                'type': 'analysis'
            },
            6: {
                'title': 'Локальная среда: обход районов',
                'practice': 'Посетите 3 разных района, поговорите с жителями. Что их радует? Что расстраивает?',
                'duration': '1 день',
                'type': 'field_work'
            },
            7: {
                'title': 'Институты: регламенты',
                'practice': 'Проанализируйте 3 ключевых процесса в администрации. Как их можно упростить?',
                'duration': '2 дня',
                'type': 'analysis'
            },
            8: {
                'title': 'Региональный контекст: бенчмаркинг',
                'practice': 'Изучите опыт 2-3 успешных городов. Что можно адаптировать?',
                'duration': '2 дня',
                'type': 'research'
            },
            9: {
                'title': 'Мифы: фактчекинг',
                'practice': 'Составьте список городских мифов и найдите факты, которые их опровергают.',
                'duration': '1 день',
                'type': 'analysis'
            }
        }
    
    def _build_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Строит библиотеку метрик для отслеживания прогресса
        """
        return {
            'safety': {
                'name': 'Безопасность',
                'indicators': [
                    'Уровень преступности (снижение на %)',
                    'Количество ДТП (снижение на %)',
                    'Освещенность улиц (% охвата)',
                    'Доверие к полиции (опрос)'
                ],
                'targets': {
                    'short_term': 'снижение на 10%',
                    'medium_term': 'снижение на 25%',
                    'long_term': 'снижение на 50%'
                }
            },
            'economy': {
                'name': 'Экономика',
                'indicators': [
                    'Бюджет города (рост на %)',
                    'Количество МСП (рост на %)',
                    'Уровень безработицы (снижение на %)',
                    'Инвестиции (рост на %)'
                ],
                'targets': {
                    'short_term': 'рост на 5%',
                    'medium_term': 'рост на 15%',
                    'long_term': 'рост на 30%'
                }
            },
            'quality_of_life': {
                'name': 'Качество жизни',
                'indicators': [
                    'Удовлетворенность жителей (опрос)',
                    'Благоустроенные пространства (количество)',
                    'Экологическая ситуация (индекс)',
                    'Доступность услуг (время/охват)'
                ],
                'targets': {
                    'short_term': '+10% к удовлетворенности',
                    'medium_term': '+20% к удовлетворенности',
                    'long_term': '+40% к удовлетворенности'
                }
            },
            'social_capital': {
                'name': 'Социальный капитал',
                'indicators': [
                    'Активные ТОСы (рост на %)',
                    'Волонтеры (количество)',
                    'НКО (количество проектов)',
                    'Городские события (посещаемость)'
                ],
                'targets': {
                    'short_term': '+20% к активности',
                    'medium_term': '+50% к активности',
                    'long_term': '+100% к активности'
                }
            }
        }
    
    def get_for_loop(self, loop_type: str, element_id: int = None) -> Optional[Dict[str, Any]]:
        """
        Возвращает интервенцию для городской петли и конкретного элемента
        
        Args:
            loop_type: тип петли
            element_id: ID элемента (1-9)
            
        Returns:
            интервенция или None
        """
        loop_data = self.interventions.get(loop_type)
        if not loop_data:
            # Пробуем универсальную
            loop_data = self.interventions.get('universal')
            logger.warning(f"Тип петли {loop_type} не найден, использую universal")
        
        if not loop_data:
            return None
        
        if element_id is not None and element_id in loop_data.get('interventions', {}):
            return loop_data['interventions'][element_id]
        
        # Если элемент не указан, берем первый рекомендуемый
        if loop_data.get('break_points'):
            first_point = loop_data['break_points'][0]
            return loop_data['interventions'].get(first_point)
        
        return None
    
    def get_personalized(self, loop_type: str, city_profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Возвращает персонализированную интервенцию с учетом профиля города
        
        Args:
            loop_type: тип петли
            city_profile: профиль города (векторы и уровни)
            
        Returns:
            персонализированная интервенция
        """
        base = self.get_for_loop(loop_type)
        if not base:
            return None
        
        # Копируем, чтобы не менять оригинал
        intervention = base.copy()
        
        # Добавляем персонализацию на основе слабого вектора
        weak_vector = self._get_weakest_vector(city_profile)
        
        vector_advice = {
            'СБ': 'Приоритет — безопасность и стабильность. Начните с быстрых побед в этой сфере.',
            'ТФ': 'Ключевая проблема — экономика. Сфокусируйтесь на привлечении инвестиций.',
            'УБ': 'Главный вызов — качество жизни. Начните с благоустройства ключевых пространств.',
            'ЧВ': 'Социальный капитал требует внимания. Инвестируйте в сообщества и коммуникацию.'
        }
        
        intervention['personalized_intro'] = vector_advice.get(weak_vector, 
            'Учитывая профиль города, предлагаем следующий план действий.')
        
        # Добавляем быстрый проект
        quick_win = random.choice(self.projects.get('quick_wins', []))
        intervention['quick_win'] = quick_win
        
        # Добавляем метрики для отслеживания
        if weak_vector:
            metric = self.metrics.get(weak_vector.lower(), self.metrics['safety'])
            intervention['metrics_to_track'] = metric
        
        # Добавляем цитату
        intervention['quote'] = self.get_random_quote()
        
        return intervention
    
    def _get_weakest_vector(self, city_profile: Dict[str, Any]) -> Optional[str]:
        """Определяет самый слабый вектор города"""
        if not city_profile:
            return None
        
        scores = {k: v for k, v in city_profile.items() if k in ['СБ', 'ТФ', 'УБ', 'ЧВ']}
        if not scores:
            return None
        
        return min(scores, key=scores.get)
    
    def get_daily_practice(self, element_id: int) -> Dict[str, str]:
        """
        Возвращает еженедельную практику для элемента
        
        Args:
            element_id: ID элемента (1-9)
            
        Returns:
            практика с названием, описанием и длительностью
        """
        practice = self.practices.get(element_id, {
            'title': 'Анализ городской ситуации',
            'practice': 'Проведите анализ текущей ситуации в городе по всем ключевым направлениям.',
            'duration': '1 день',
            'type': 'analysis'
        })
        return practice
    
    def get_random_quote(self, category: str = None) -> str:
        """
        Возвращает случайную цитату
        
        Args:
            category: категория (urban_development, community, leadership, innovation)
            
        Returns:
            цитата
        """
        if category and category in self.quotes:
            return random.choice(self.quotes[category])
        
        # Все категории
        all_quotes = []
        for quotes in self.quotes.values():
            all_quotes.extend(quotes)
        return random.choice(all_quotes)
    
    def get_program_for_quarter(self, key_element_id: int, timeline: str = 'quick') -> List[Dict[str, str]]:
        """
        Возвращает программу на квартал для работы с ключевым элементом
        
        Args:
            key_element_id: ID ключевого элемента (1-9)
            timeline: 'quick' (быстрые победы), 'medium' (среднесрочные), 'long' (долгосрочные)
            
        Returns:
            список заданий по месяцам
        """
        programs = {
            'quick': [
                ('Месяц 1', 'Диагностика', 'Провести аудит ситуации, собрать данные, опросить жителей'),
                ('Месяц 2', 'Быстрые победы', 'Реализовать 3-5 быстрых проектов с высокой видимостью'),
                ('Месяц 3', 'Оценка', 'Измерить результаты, скорректировать планы, коммуницировать успехи')
            ],
            'medium': [
                ('Месяц 1-2', 'Планирование', 'Разработать детальный план, сформировать команду, найти ресурсы'),
                ('Месяц 3-5', 'Реализация', 'Запустить ключевые проекты, вовлечь стейкхолдеров'),
                ('Месяц 6', 'Оценка и корректировка', 'Промежуточные итоги, корректировка курса')
            ],
            'long': [
                ('Квартал 1', 'Стратегия', 'Разработка долгосрочной стратегии, поиск партнеров'),
                ('Квартал 2-3', 'Пилоты', 'Запуск пилотных проектов, сбор обратной связи'),
                ('Квартал 4', 'Масштабирование', 'Тиражирование успешных практик, системные изменения')
            ]
        }
        
        program = programs.get(timeline, programs['quick'])
        
        days = []
        for period, theme, task in program:
            days.append({
                'period': period,
                'theme': theme,
                'task': task,
                'quote': self.get_random_quote()
            })
        
        return days
    
    def get_project_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Ищет проект по названию
        
        Args:
            name: название проекта
            
        Returns:
            проект или None
        """
        for category in self.projects.values():
            for project in category:
                if project.get('name') == name:
                    return project
        return None
    
    def get_all_interventions(self) -> List[Dict[str, Any]]:
        """
        Возвращает список всех интервенций
        
        Returns:
            список всех интервенций
        """
        all_interventions = []
        for loop_type, loop_data in self.interventions.items():
            for element_id, intervention in loop_data.get('interventions', {}).items():
                intervention_copy = intervention.copy()
                intervention_copy['loop_type'] = loop_type
                intervention_copy['element_id'] = element_id
                all_interventions.append(intervention_copy)
        return all_interventions
    
    def get_metrics_dashboard(self) -> Dict[str, Any]:
        """
        Возвращает дашборд метрик для отслеживания прогресса города
        
        Returns:
            словарь с метриками и целевыми показателями
        """
        dashboard = {
            'categories': [],
            'total_indicators': 0,
            'recommended_frequency': 'ежемесячно'
        }
        
        for key, metric in self.metrics.items():
            dashboard['categories'].append({
                'name': metric['name'],
                'indicators': metric['indicators'],
                'short_term_target': metric['targets']['short_term'],
                'medium_term_target': metric['targets']['medium_term'],
                'long_term_target': metric['targets']['long_term']
            })
            dashboard['total_indicators'] += len(metric['indicators'])
        
        return dashboard
    
    def get_comparison_matrix(self) -> Dict[str, List[str]]:
        """
        Возвращает матрицу сравнения интервенций по сложности и эффективности
        
        Returns:
            матрица сравнения
        """
        return {
            'low_cost_high_impact': [
                'Установка освещения в проблемных местах',
                'Субботники с жителями',
                'Медиа-кампания в соцсетях',
                'Встречи с жителями во дворах'
            ],
            'medium_cost_high_impact': [
                'Создание общественных пространств',
                'Программа поддержки МСП',
                'Цифровизация услуг',
                'Инициативное бюджетирование'
            ],
            'high_cost_transformational': [
                'Строительство набережной',
                'Создание технопарка',
                'Транспортная реформа',
                'Реновация центра города'
            ]
        }


# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def get_intervention_library() -> CityInterventionLibrary:
    """
    Возвращает экземпляр библиотеки интервенций (синглтон)
    """
    return CityInterventionLibrary()


def format_intervention_for_mayor(intervention: Dict) -> str:
    """
    Форматирует интервенцию для главы города
    
    Args:
        intervention: словарь с интервенцией
        
    Returns:
        отформатированный текст
    """
    if not intervention:
        return "Интервенция не найдена"
    
    text = f"""
📋 **ПРОЕКТ: {intervention.get('name', 'Не указан')}**

**Описание:**
{intervention.get('description', 'Нет описания')}

**Ключевой проект:**
{intervention.get('project', 'Не указан')}

**Сроки:** {intervention.get('duration', 'Не указаны')}
**Сложность:** {intervention.get('difficulty', 'Не указана')}
**Бюджет:** {intervention.get('budget', 'Не указан')}
**Уровень:** {intervention.get('city_level', 'Не указан')}

**Ожидаемый результат:**
{intervention.get('expected', 'Не указан')}
"""
    
    if 'quick_win' in intervention:
        text += f"\n**🚀 Быстрая победа:**\n{intervention['quick_win']['name']} — {intervention['quick_win']['description']}"
    
    if 'quote' in intervention:
        text += f"\n\n💬 *\"{intervention['quote']}\"*"
    
    return text


# ============================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ
# ============================================

if __name__ == "__main__":
    print("🧪 Тестирование CityInterventionLibrary...")
    
    lib = CityInterventionLibrary()
    
    # Тест 1: Получить интервенцию для петли
    print("\n📋 Интервенция для петли safety_economy_cycle (элемент 2):")
    intervention = lib.get_for_loop('safety_economy_cycle', 2)
    if intervention:
        print(f"  Название: {intervention['name']}")
        print(f"  Проект: {intervention['project'][:80]}...")
        print(f"  Сроки: {intervention['duration']}")
    
    # Тест 2: Персонализированная интервенция
    print("\n📋 Персонализированная интервенция:")
    city_profile = {'СБ': 2.3, 'ТФ': 2.8, 'УБ': 3.2, 'ЧВ': 2.5}
    personalized = lib.get_personalized('full_vicious_cycle', city_profile)
    if personalized:
        print(f"  Название: {personalized['name']}")
        print(f"  Персонализация: {personalized.get('personalized_intro', 'Нет')}")
        print(f"  Быстрая победа: {personalized.get('quick_win', {}).get('name', 'Нет')}")
    
    # Тест 3: Еженедельная практика
    print("\n📋 Еженедельная практика для элемента 5:")
    practice = lib.get_daily_practice(5)
    print(f"  {practice['title']}: {practice['practice'][:60]}...")
    
    # Тест 4: Квартальная программа
    print("\n📋 Квартальная программа (быстрые победы):")
    program = lib.get_program_for_quarter(3, 'quick')
    for period in program:
        print(f"  {period['period']}: {period['theme']} — {period['task'][:40]}...")
    
    # Тест 5: Случайная цитата
    print("\n📋 Случайная цитата:")
    print(f"  {lib.get_random_quote('urban_development')}")
    
    # Тест 6: Дашборд метрик
    print("\n📊 Дашборд метрик:")
    dashboard = lib.get_metrics_dashboard()
    print(f"  Всего категорий: {len(dashboard['categories'])}")
    print(f"  Всего индикаторов: {dashboard['total_indicators']}")
    print(f"  Рекомендуемая частота: {dashboard['recommended_frequency']}")
    
    # Тест 7: Матрица сравнения
    print("\n🎯 Матрица сравнения (low cost, high impact):")
    matrix = lib.get_comparison_matrix()
    for project in matrix['low_cost_high_impact'][:3]:
        print(f"  • {project}")
    
    print("\n✅ Тест завершен")
