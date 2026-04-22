# CityMind — AI-ассистент мэра Коломны

Система интеллектуального управления городским развитием на базе конфайнт-модели.
Пилотный город — **Коломна, Московская область**.

> Ядро системы (конфайнт-модель, анализ петель, библиотека интервенций) уже
> реализовано в корне репозитория. Эта ветка добавляет **MVP** недостающих
> частей по ТЗ v1.0: коллекторы данных, планировщик повестки и roadmap,
> FastAPI + статический дашборд, миграции БД и инфраструктуру.

## Структура

```
.
├── confinement_model.py         # ядро (существует)
├── loop_analyzer.py             # ядро (существует)
├── key_confinement.py           # ядро (существует)
├── intervention_library.py      # ядро (существует)
├── confinement_reporter.py      # ядро (существует)
├── question_context_analyzer.py # ядро (существует)
├── citymind_app.py              # ядро (существует)
├── metrics/                     # модули метрик (существуют + расширяются)
│
├── config/                      # ★ новое: настройки, города, источники
├── collectors/                  # ★ новое: Telegram / VK / News / Обращения
├── agenda/                      # ★ новое: повестка дня, roadmap
├── api/                         # ★ новое: FastAPI + эндпоинты
├── dashboard/                   # ★ новое: статический дашборд мэра
├── migrations/                  # ★ новое: PostgreSQL + TimescaleDB схема
├── tests/                       # ★ новое: unit-тесты
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Быстрый старт

```bash
# 1. Зависимости (Python 3.11+)
pip install -r requirements.txt

# 2. Настройки
cp .env.example .env
# заполните OPENWEATHER_API_KEY / VK_API_TOKEN / TELEGRAM_API_ID / TELEGRAM_API_HASH

# 3. БД + Redis одной командой
docker compose up -d db redis

# 4. Применить схему
psql "postgresql://citymind:citymind@localhost:5432/citymind" -f migrations/init_db.sql

# 5. API + дашборд
uvicorn api.main:app --reload
# → http://localhost:8000         — дашборд
# → http://localhost:8000/docs    — Swagger
```

Если нет внешних ключей — всё равно запустится: коллекторы без ключей
возвращают пустой список, дашборд покажет заглушки.

## Основные эндпоинты

| Метод | URL | Описание |
|-------|-----|----------|
| `GET`  | `/health` | проверка живости |
| `GET`  | `/api/cities` | список городов |
| `GET`  | `/api/city/{name}` | карточка города |
| `GET`  | `/api/city/{name}/news` | собрать ленту (Telegram + VK + Я.Новости) |
| `GET`  | `/api/city/{name}/agenda` | повестка дня (Markdown для Telegram) |
| `POST` | `/api/city/{name}/roadmap` | расчёт roadmap на цель по вектору |

Пример расчёта roadmap:

```bash
curl -X POST http://localhost:8000/api/city/Коломна/roadmap \
  -H "Content-Type: application/json" \
  -d '{
    "vector": "УБ",
    "start_level": 3.0,
    "target_level": 5.0,
    "deadline": "2027-06-30",
    "scenario": "baseline"
  }'
```

## Источники данных Коломны

По ТЗ разделы 4.1–4.2 в реестре зарегистрированы:

- **10 Telegram-каналов** (`@gorodkolomna`, `@kolomna_live`, `@kolomna_chp`, …).
- **5 VK-пабликов** (`typical_kolomna`, `kolomna_today`, …).
- **RSS Яндекс.Новости** по запросу «Коломна».
- **Stub** коллектор обращений через Госуслуги — подключается по ключу.

Список управляется из `config/sources.py`, добавление нового города —
одна запись в `config/cities.py` + соответствующий `CitySources`.

## Тесты

```bash
pytest tests/ -v
```

Интеграционные тесты (реальные API) вынесены за пределы `tests/` —
по умолчанию CI прогоняет только офлайн-часть.

## Текущий статус MVP по ТЗ

- [x] §3.3 скелет: `config/`, `collectors/`, `agenda/`, `api/`, `dashboard/`, `migrations/`.
- [x] §4 реестр источников Коломны (TG/VK/RSS + stub Госуслуг).
- [x] §2.1.3 повестка дня (Markdown для Telegram, §13.1).
- [x] §2.1.4 планировщик roadmap (3 сценария, стоимости, риски).
- [x] §2.1.5 дашборд мэра (виджеты погоды, векторов, доверия, счастья, композитов, повестки).
- [x] §3.1 миграция БД PostgreSQL + TimescaleDB.
- [x] §3.2 стек: FastAPI + aiohttp + Telethon + feedparser + Redis/Celery.
- [x] §9 юнит-тесты `config`, `agenda`, `roadmap`, `collectors`.
- [ ] §2.1.1 реальный парсинг с сохранением в БД (скелет готов, нужен Celery beat).
- [ ] §2.1.2 полный пайплайн аналитики (конфайнт-модель уже есть, надо подключить к коллекторам).
- [ ] §6.2 продуктовые ключи и интеграция с Госуслугами.
- [ ] §5 поэтапное внедрение в городской администрации.
