# Источники новостей «Городского Разума»

Каталог зарегистрированных в `config/sources.py` источников
по каждому пилотному городу. Используется как чек-лист для
валидации / расширения — при онбординге новых городов или
при замене «умерших» источников на актуальные.

## Коломна (P0 — высший приоритет)

### Telegram-каналы
| Handle | Название | Категория |
|---|---|---|
| `@gorodkolomna` | Администрация Коломны | official |
| `@kolomna_live` | Коломна LIVE | city |
| `@kolomna_chp` | ЧП Коломна | incidents |
| `@kolomna_overs` | Подслушано Коломна | complaints |
| `@kolomna_dtp` | Коломна ДТП | incidents |
| `@kolomna_news` | Коломна. Новости | news |
| `@kolomna_info` | Коломна-Инфо | news |
| `@kolomna_transport` | Коломна Транспорт | transport |
| `@kolomna_auto` | Коломна Авто | transport |
| `@kolomna_zhkh` | Коломна ЖКХ | utilities |
| `@kolomna_culture` | Культура Коломна | culture |
| `@kolomna_kreml` | Коломенский кремль | culture |
| `@kolomna_sport` | Спорт Коломна | sport |
| `@kolomna_business` | Бизнес Коломна | business |

### VK-группы
| Handle | Название | Категория |
|---|---|---|
| `typical_kolomna` | Типичная Коломна | complaints |
| `kolomna_today` | Коломна Сегодня | news |
| `kolomna_adm` | Администрация Коломны | official |
| `kolomna360` | Коломна 360 | city |
| `kolomna_online` | Коломна Онлайн | news |
| **`auto_kolomna`** | **Автомобилисты Коломны** | **transport** |
| `kolomna_roads` | Дороги Коломны | transport |
| `kolomna_probki` | Коломенские пробки | transport |
| `kolomna_trolley` | Коломенский троллейбус | transport |
| `kolomna_zhkh_vk` | ЖКХ Коломна | utilities |
| `kolomna_blag` | Коломна благоустройство | quality |
| `kolomna_mfc` | МФЦ Коломны | official |
| `kolomna_business_vk` | Коломна Бизнес | business |
| `kolomna_mamas` | Мамы Коломны | social |
| `kolomna_sport_vk` | Коломна Спорт | sport |

### RSS / Новости
- **Google News** — 5 тематических запросов (общий / ДТП / ЖКХ / транспорт / культура)
- **in-kolomna.ru** — главное городское издание (RSS).
- **kolomnagrad.ru** — локальный портал.
- **360tv.ru/kolomna** — раздел областного СМИ.
- **mosregtoday.ru** — официальное областное СМИ с тегом «Коломна».

### Госуслуги / Обращения
- Обращения граждан (stub-коллектор, ждёт API-ключ).
- **ПОС — Платформа обратной связи** (`pos.gosuslugi.ru`) — требует OAuth.

---

## Остальные пилоты (Луховицы / Воскресенск / Егорьевск / Ступино / Озёры)

Стартуют с одного Google News RSS-запроса каждый. При онбординге
необходимо добавить:
- локальные TG-каналы ("Подслушано …", "Типичный …", "ЧП …");
- ключевые VK-паблики администрации и городского сообщества;
- RSS местных порталов.

Приоритеты по умолчанию:
- **P0** — критичные (официальные / ЧП / жалобы).
- **P1** — важные (основные тематические TG-каналы).
- **P2** — фоновые (культура, спорт, ниши).

---

## Как добавить источник

1. Найти handle / URL.
2. Добавить строку в соответствующий блок `config/sources.py`
   (telegram / vk / news_rss / gosuslugi).
3. Проставить категорию из канона (`incidents`, `utilities`,
   `transport`, `culture`, `sport`, `business`, `official`, `news`,
   `complaints`, `other`).
4. Deploy → коллектор подхватит новый источник на ближайшем тике.

## Как проверить, что источник «живой»

- Для RSS: `curl -sI URL | head -3` (ожидаем 200 / `Content-Type: application/xml`).
- Для Telegram: handle должен открываться на `https://t.me/<handle>`.
- Для VK: `vk.com/<handle>` — проверить дату последнего поста.

## Триггер ручного сбора

`POST /api/admin/collect/{city_name}` запускает однократный прогон
коллекторов без ожидания scheduler-тика. Результат — количество
записей, добавленных в БД.
