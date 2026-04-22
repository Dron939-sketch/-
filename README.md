# Городской Разум

> Прогнозное управление городом на основе алгоритма Мейстера.

Платформа собирает новости, соцсети и обращения граждан, прогоняет их
через AI-обогатитель, считает 4 ключевых вектора (СБ / ТФ / УБ / ЧВ),
формирует ежедневную повестку и roadmap для главы города. MVP развёрнут
на Render: <https://smart-mind.onrender.com>.

## Города в системе

Кластер юго-востока Московской области:

| Город          | Slug          | Население | Прямая ссылка                  |
|----------------|---------------|-----------|---------------------------------|
| Коломна 🏰     | `kolomna`     | 144 589   | `/api/city/kolomna/all_metrics` |
| Луховицы 🥒    | `lukhovitsy`  | 29 300    | `/api/city/lukhovitsy/agenda`   |
| Воскресенск ⚗️ | `voskresensk` | 75 200    | `/api/city/voskresensk/agenda`  |
| Егорьевск ⛪   | `egoryevsk`   | 71 000    | `/api/city/egoryevsk/agenda`    |
| Ступино 🏭     | `stupino`     | 64 100    | `/api/city/stupino/agenda`      |
| Озёры 💧       | `ozyory`      | 24 200    | `/api/city/ozyory/agenda`       |

Коломна — пилот: настроены 10 Telegram-каналов + 5 VK-пабликов + Google News
RSS + stub-коннектор Госуслуг. Остальные пять стартуют только с Google News
RSS — TG/VK добавляются администратором при онбординге (ТЗ §4.4).

Селектор городов — справа от логотипа в шапке дашборда. Выбор сохраняется в
`localStorage`, прямая ссылка `/<slug>` поддерживается.

## Структура

```
.
├── confinement_model.py         # ядро: модель Мейстера
├── loop_analyzer.py             # ядро: анализ петель
├── intervention_library.py      # ядро: библиотека интервенций
├── citymind_app.py              # ядро (legacy)
│
├── config/                      # настройки + 6 городов + источники
├── collectors/                  # Telegram / VK / News / Госуслуги
├── ai/                          # DeepSeek-обогатитель новостей
├── agenda/                      # повестка дня + roadmap
├── api/                         # FastAPI: /api/city/{slug-or-name}/*
├── dashboard/                   # премиум-UI (vanilla JS, Playfair+Manrope)
├── migrations/                  # PostgreSQL + TimescaleDB
└── tests/                       # 24 unit-теста
```

## Быстрый старт

```bash
pip install -r requirements.txt
cp .env.example .env
# заполните DEEPSEEK_API_KEY / OPENWEATHER_API_KEY / VK_API_TOKEN /
# TELEGRAM_API_ID / TELEGRAM_API_HASH

docker compose up -d db redis
psql "postgresql://citymind:citymind@localhost:5432/citymind" -f migrations/init_db.sql
uvicorn api.main:app --reload
# → http://localhost:8000      — премиум-дашборд
# → http://localhost:8000/docs — Swagger
```

Если нет внешних ключей — всё равно запустится: коллекторы без ключей
возвращают пустой список, дашборд показывает плейсхолдеры.

## API

| Метод | URL                                  | Описание                                         |
|-------|---------------------------------------|--------------------------------------------------|
| GET   | `/health`                             | живость + версия                                 |
| GET   | `/api/cities`                         | список городов с brand-полями                    |
| GET   | `/api/city/by-slug/{slug}`            | поиск по slug                                    |
| GET   | `/api/city/{name-or-slug}`            | карточка города                                  |
| GET   | `/api/city/{name-or-slug}/all_metrics`| снимок метрик для дашборда                       |
| GET   | `/api/city/{name-or-slug}/news`       | свежая лента (TG + VK + RSS + Госуслуги)         |
| GET   | `/api/city/{name-or-slug}/agenda`     | повестка дня (с AI-обогащением)                  |
| POST  | `/api/city/{name-or-slug}/roadmap`    | roadmap по выбранному вектору                    |

Пример:

```bash
curl -X POST https://smart-mind.onrender.com/api/city/lukhovitsy/roadmap \
  -H "Content-Type: application/json" \
  -d '{"vector":"УБ","start_level":3.0,"target_level":5.0,
       "deadline":"2027-06-30","scenario":"baseline"}'
```

## Премиум-дизайн (ТЗ ребрендинга)

- Палитра: `#0A1628` глубинная синь · `#0D2135` ночное небо · `#C5A059`
  золотой разум · `#D4AF37` чистое золото · `#E8D5A3` светлое золото.
- Типографика: Playfair Display (логотип, заголовки) + Manrope (всё
  остальное), подключаются с Google Fonts.
- Анимации: плавное появление карточек (`cubic-bezier(.16,1,.3,1)`),
  ховеры с золотым свечением, прогресс-бары с градиентом.
- Селектор городов: dropdown в шапке с emoji, активный город
  подсвечивается, пилот помечен чипом.
- Адаптив: 1440px desktop → 2-col mobile.

## AI-обогащение (DeepSeek)

Эндпоинт `/agenda` пропускает свежие новости через `ai/NewsEnricher`:
sentiment / category / severity / summary. При severity ≥ 0.5 заголовок
повестки заменяется самой важной историей, top_complaints/top_praises
формируются по AI-категории + знаку sentiment.

Стоимость: ~$0.003 на вызов `/agenda` через DeepSeek (`deepseek-chat`).

## Тесты

```bash
pytest tests/ -v
# → 24 passed
```

## Статус по ТЗ

- [x] §3.3 скелет: `config/`, `collectors/`, `ai/`, `agenda/`, `api/`, `dashboard/`, `migrations/`.
- [x] §4 источники Коломны (TG/VK/RSS) + RSS для 5 городов-соседей.
- [x] §2.1.3 повестка дня (Markdown для Telegram, AI-обогащение).
- [x] §2.1.4 планировщик roadmap (3 сценария).
- [x] §2.1.5 премиум-дашборд (палитра + Playfair/Manrope + анимации).
- [x] §3.1 миграции PostgreSQL + TimescaleDB.
- [x] §4 (ребрендинг) мультигород: 6 городов, селектор, slug-роутинг,
      brand-поля (emoji, accent_color), запоминание выбора в localStorage.
- [x] AI-обогащение через DeepSeek (sentiment/category/severity/summary).
- [ ] Celery beat для регулярного парсинга → запись в БД.
- [ ] Подключение existing ядра (ConfinementModel9) к собранным новостям.
- [ ] Полная миграция фронтенда на Next.js + Framer Motion (vanilla MVP
      покрывает требования к визуалу — миграция планируется отдельным PR).
