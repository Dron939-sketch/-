// =============================================================================
// Личный кабинет депутата — wow-первый экран при role=deputy.
// Подгружает /api/copilot/deputy/cabinet и рендерит большой hero
// с приветствием, рейтингом, архетипом, рекомендациями и контент-планом.
// =============================================================================

(function () {
  "use strict";

  const HERO_ID = "deputy-cabinet-hero";

  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));

  // ---------------------------------------------------------------------------
  // Render helpers
  // ---------------------------------------------------------------------------

  function archetypeEmoji(code) {
    return ({
      caregiver: "🌳",  ruler: "👑",      sage: "📚",      hero: "🛡",
      explorer: "🧭",   creator: "🎨",    everyman: "🤝", lover: "💗",
      jester: "🎭",     innocent: "🌅",   magician: "✨",  outlaw: "⚔",
    })[code] || "🌟";
  }

  function ratingStars(stars) {
    const full = "★".repeat(Math.max(0, Math.min(5, Math.round(stars))));
    const empty = "☆".repeat(5 - full.length);
    return full + empty;
  }

  function alignmentLabel(score) {
    if (score == null) return "—";
    if (score >= 70) return "В голосе";
    if (score >= 40) return "Частично совпадает";
    if (score >= 15) return "Размытый стиль";
    return "Стиль не виден";
  }

  // ---------------------------------------------------------------------------
  // Sub-blocks
  // ---------------------------------------------------------------------------

  function renderHeader(d, a, rating) {
    const greeting = d.first_name ? `Здравствуйте, ${esc(d.first_name)}!` : "Добро пожаловать!";
    return `
      <div class="dc-hero">
        <div class="dc-hero-text">
          <div class="dc-hero-eyebrow">Личный кабинет депутата</div>
          <h1 class="dc-hero-greet">${greeting}</h1>
          <div class="dc-hero-meta">
            ${esc(d.name || "")} · ${esc(d.district || "")}
            ${d.vk_url ? `· <a href="${esc(d.vk_url)}" target="_blank" rel="noopener">VK ↗</a>` : ""}
          </div>
          <div class="dc-actions">
            <button type="button" class="dc-action-btn dc-action-primary" id="dc-create-content">
              <span class="dc-action-emoji">🎬</span>
              <span class="dc-action-text">
                <span class="dc-action-title">Создать контент</span>
                <span class="dc-action-sub">пост в твоём стиле за 30 секунд</span>
              </span>
            </button>
            <button type="button" class="dc-action-btn dc-action-secondary" id="dc-create-event">
              <span class="dc-action-emoji">📣</span>
              <span class="dc-action-text">
                <span class="dc-action-title">Создать медиаповод</span>
                <span class="dc-action-sub">пошаговый сценарий PR-события</span>
              </span>
            </button>
          </div>
          <p class="dc-hero-sub">
            Я проанализировал вашу страницу глазами горожан и архетип бренда.
            Вот что увидел и как поднять рейтинг.
          </p>
        </div>
        <div class="dc-archetype-badge">
          <div class="dc-arch-emoji">${archetypeEmoji(a.code)}</div>
          <div class="dc-arch-name">«${esc(a.name)}»</div>
          <div class="dc-arch-short">${esc(a.short || "")}</div>
        </div>
      </div>
    `;
  }

  function renderRatings(rating, audit) {
    const m = (audit && audit.metrics) || {};
    const align = audit ? audit.alignment_score : null;
    const stars = (rating && rating.value) || 0;
    return `
      <div class="dc-stats">
        <div class="dc-stat dc-stat-rating">
          <div class="dc-stat-value">${stars.toFixed(1)}</div>
          <div class="dc-stat-stars">${ratingStars(stars)}</div>
          <div class="dc-stat-label">Рейтинг бренда</div>
        </div>
        <div class="dc-stat">
          <div class="dc-stat-value">${align == null ? "—" : Math.round(align)}<span class="dc-stat-unit">%</span></div>
          <div class="dc-stat-label">${esc(alignmentLabel(align))}</div>
          <div class="dc-stat-hint">соответствие архетипу</div>
        </div>
        <div class="dc-stat">
          <div class="dc-stat-value">${m.posts_per_week ?? 0}<span class="dc-stat-unit">/нед</span></div>
          <div class="dc-stat-label">Регулярность</div>
          <div class="dc-stat-hint">всего ${m.posts_count ?? 0} постов</div>
        </div>
        <div class="dc-stat">
          <div class="dc-stat-value">${Math.round(m.avg_likes ?? 0)}</div>
          <div class="dc-stat-label">Лайков в среднем</div>
          <div class="dc-stat-hint">~${m.avg_length ?? 0} символов</div>
        </div>
      </div>
    `;
  }

  function renderCitizensView(audit, archetype) {
    if (!audit) return "";
    const works = (audit.what_works || []).slice(0, 3);
    const hurts = (audit.what_hurts || []).slice(0, 3);
    const dos   = (archetype.do || []).slice(0, 3);
    const donts = (archetype.dont || []).slice(0, 2);

    if (audit.state === "no_posts") {
      return `
        <div class="dc-block">
          <div class="dc-block-title">👀 Глазами горожан</div>
          <div class="dc-empty">
            Стена пустая или закрытая. Откройте её и опубликуйте первый
            пост — я смогу показать, что именно работает на вашу репутацию.
          </div>
        </div>
      `;
    }
    return `
      <div class="dc-block">
        <div class="dc-block-title">👀 Глазами горожан</div>
        <div class="dc-two-col">
          <div class="dc-col dc-col-good">
            <div class="dc-col-title">Это работает на вашу репутацию</div>
            ${works.length ? `<ul class="dc-quotes">
              ${works.map((q) => `<li>«${esc(q)}…»</li>`).join("")}
            </ul>` : `<div class="dc-empty-sub">Пока нет постов в голосе архетипа.</div>`}
            <div class="dc-col-tip">Чего ждут от «${esc(archetype.name)}»:</div>
            <ul class="dc-list">
              ${dos.map((s) => `<li>${esc(s)}</li>`).join("")}
            </ul>
          </div>
          <div class="dc-col dc-col-bad">
            <div class="dc-col-title">Это размывает голос</div>
            ${hurts.length ? `<ul class="dc-quotes">
              ${hurts.map((q) => `<li>«${esc(q)}…»</li>`).join("")}
            </ul>` : `<div class="dc-empty-sub">Размытых сообщений почти нет — хорошо.</div>`}
            <div class="dc-col-tip">Что лучше не делать:</div>
            <ul class="dc-list">
              ${donts.map((s) => `<li>${esc(s)}</li>`).join("")}
            </ul>
          </div>
        </div>
      </div>
    `;
  }

  function renderRecommendations(audit) {
    const recs = (audit && audit.recommendations) || [];
    if (recs.length === 0) return "";
    return `
      <div class="dc-block">
        <div class="dc-block-title">🎯 Что поднимет рейтинг</div>
        <ol class="dc-recs">
          ${recs.map((r) => `<li>${esc(r)}</li>`).join("")}
        </ol>
      </div>
    `;
  }

  function renderPlan(plan, archetype) {
    const items = (plan && plan.items) || [];
    if (items.length === 0) return "";
    return `
      <div class="dc-block">
        <div class="dc-block-title">
          📅 Контент-план в голосе «${esc(archetype.name)}»
          ${plan.fallback ? `<span class="dc-fallback-tag">шаблон</span>` : ""}
        </div>
        <div class="dc-plan-grid">
          ${items.map((it) => `
            <div class="dc-plan-card">
              <div class="dc-plan-day">${esc(it.day || "")}</div>
              <div class="dc-plan-topic">${esc(it.topic || "")}</div>
              ${it.draft ? `<div class="dc-plan-draft">${esc(it.draft)}</div>` : ""}
              ${it.draft ? `<button type="button" class="dc-copy" data-text="${esc(it.draft)}">Скопировать</button>` : ""}
            </div>
          `).join("")}
        </div>
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // Main
  // ---------------------------------------------------------------------------

  async function fetchCabinet(externalId) {
    try {
      const r = await fetch(`/api/copilot/deputy/cabinet?external_id=${encodeURIComponent(externalId)}`);
      if (!r.ok) return null;
      return await r.json();
    } catch (_) { return null; }
  }

  function renderError(hero, msg) {
    hero.innerHTML = `<div class="dc-empty">${esc(msg)}</div>`;
  }

  async function renderCabinet() {
    const hero = document.getElementById(HERO_ID);
    if (!hero) return;
    const role = window.cmRole?.get?.() || null;
    const eid  = window.cmRole?.deputyId?.() || null;
    if (role !== "deputy") return;
    if (!eid) {
      renderError(hero, "Не выбран депутат — откройте picker и выберите ещё раз.");
      return;
    }
    hero.innerHTML = `<div class="dc-loading">Анализирую страницу и собираю кабинет…</div>`;
    const data = await fetchCabinet(eid);
    if (!data) {
      renderError(hero, "Не удалось собрать кабинет. Попробуйте обновить страницу.");
      return;
    }
    hero.innerHTML = `
      ${renderHeader(data.deputy || {}, data.archetype || {}, data.rating || {})}
      ${renderRatings(data.rating || {}, data.audit || null)}
      ${renderCitizensView(data.audit || {}, data.archetype || {})}
      ${renderRecommendations(data.audit || {})}
      ${renderPlan(data.plan || {}, data.archetype || {})}
    `;
    hero.addEventListener("click", onCopyClick);
    document.getElementById("dc-create-content")?.addEventListener("click",
      () => openContentWizard(data.deputy?.external_id, data.archetype?.name));
    document.getElementById("dc-create-event")?.addEventListener("click",
      () => openEventWizard(data.deputy?.external_id, data.archetype?.name));
  }

  // ---------------------------------------------------------------------------
  // Wizards: создать контент / создать медиаповод
  // ---------------------------------------------------------------------------

  const POST_TYPES = [
    { code: "story",    emoji: "📖", label: "История помощи",            hint: "пост-история о конкретном случае" },
    { code: "thanks",   emoji: "🙏", label: "Благодарность жителям",     hint: "признание + апелляция к команде" },
    { code: "appeal",   emoji: "📢", label: "Обращение в администрацию", hint: "корректный публичный запрос" },
    { code: "report",   emoji: "✅", label: "Отчёт о решении",            hint: "было — стало, цифры и сроки" },
    { code: "news",     emoji: "📰", label: "Срочная новость",           hint: "оперативный пост по горячему" },
    { code: "congrats", emoji: "🎉", label: "Поздравление",               hint: "к дате / итогам / городу" },
  ];

  const EVENT_SOURCES = [
    { code: "complaint",   emoji: "🚧", label: "Нерешённая жалоба",  hint: "сделать дело + красиво показать" },
    { code: "result",      emoji: "🏁", label: "Уже сделанная работа", hint: "капитализировать результат" },
    { code: "anniversary", emoji: "🎂", label: "Годовщина / дата",   hint: "повод от календаря" },
    { code: "joint",       emoji: "🤝", label: "Совместная акция",   hint: "партнёр + общая выгода" },
  ];

  const EVENT_FORMATS = [
    { code: "meeting",    emoji: "👥", label: "Встреча с жителями",      hint: "60 минут вживую" },
    { code: "walkaround", emoji: "🚶", label: "Обход территории",        hint: "5-7 точек по жалобам" },
    { code: "live",       emoji: "📺", label: "Прямой эфир в VK",        hint: "30 минут Q&A" },
    { code: "action",     emoji: "🎬", label: "Совместная акция",       hint: "с партнёром / открытие" },
  ];

  function openContentWizard(deputyId, archetypeName) {
    if (!deputyId) return;
    const wrap = mountModal("dc-modal-content");
    let step = 1;
    let postType = null;
    let topic = "";
    let length = "standard";

    function render() {
      const card = wrap.querySelector(".dc-modal-card");
      if (step === 1) {
        card.innerHTML = `
          <div class="dc-mod-eyebrow">🎬 Создать контент · шаг 1 из 3</div>
          <h3 class="dc-mod-title">Какой пост?</h3>
          <div class="dc-mod-grid">
            ${POST_TYPES.map((t) => `
              <button type="button" class="dc-mod-option" data-code="${t.code}">
                <span class="dc-mod-emoji">${t.emoji}</span>
                <span class="dc-mod-label">${t.label}</span>
                <span class="dc-mod-hint">${t.hint}</span>
              </button>`).join("")}
          </div>
          <button type="button" class="dc-mod-close" data-close>✕</button>
        `;
        card.querySelectorAll(".dc-mod-option").forEach((b) => {
          b.addEventListener("click", () => {
            postType = b.getAttribute("data-code");
            step = 2; render();
          });
        });
      } else if (step === 2) {
        card.innerHTML = `
          <div class="dc-mod-eyebrow">🎬 Создать контент · шаг 2 из 3</div>
          <h3 class="dc-mod-title">О чём пост?</h3>
          <p class="dc-mod-sub">Опиши тему в свободной форме или оставь пусто — я предложу по контексту округа.</p>
          <textarea class="dc-mod-input" id="dc-topic-in" rows="3"
            placeholder="Например: ямы на ул. Ленина 12, жители просили полгода…"></textarea>
          <div class="dc-mod-radios">
            <label><input type="radio" name="len" value="short"> Короткий (~300 знаков)</label>
            <label><input type="radio" name="len" value="standard" checked> Стандарт (~700 знаков)</label>
            <label><input type="radio" name="len" value="long"> Лонгрид (~1500 знаков)</label>
          </div>
          <div class="dc-mod-foot">
            <button type="button" class="dc-mod-btn ghost" id="dc-back">← Назад</button>
            <button type="button" class="dc-mod-btn primary" id="dc-go">Сгенерировать</button>
          </div>
          <button type="button" class="dc-mod-close" data-close>✕</button>
        `;
        card.querySelector("#dc-back").addEventListener("click", () => { step = 1; render(); });
        card.querySelector("#dc-go").addEventListener("click", () => {
          topic = card.querySelector("#dc-topic-in").value || "";
          length = (card.querySelector('input[name="len"]:checked')?.value) || "standard";
          step = 3; render();
        });
      } else {
        card.innerHTML = `
          <div class="dc-mod-eyebrow">🎬 Создать контент · шаг 3 из 3</div>
          <h3 class="dc-mod-title">Готовлю пост в голосе «${esc(archetypeName || "—")}»…</h3>
          <div class="dc-mod-loading">Формулирую формат, добавляю фото-задание и хэштеги…</div>
          <button type="button" class="dc-mod-close" data-close>✕</button>
        `;
        runContentGen();
      }
      card.querySelector("[data-close]")?.addEventListener("click", () => unmountModal(wrap));
    }

    async function runContentGen() {
      try {
        const res = await fetch("/api/copilot/content/generate", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            deputy_id: deputyId, post_type: postType, topic, length,
          }),
        });
        if (!res.ok) {
          renderContentError(wrap, `Не удалось сгенерировать (${res.status}).`);
          return;
        }
        const data = await res.json();
        renderContentResult(wrap, data);
      } catch (_) {
        renderContentError(wrap, "Сеть недоступна.");
      }
    }
    render();
  }

  function renderContentError(wrap, msg) {
    const card = wrap.querySelector(".dc-modal-card");
    card.innerHTML = `
      <div class="dc-mod-eyebrow">🎬 Создать контент</div>
      <h3 class="dc-mod-title">Не получилось</h3>
      <p class="dc-mod-sub">${esc(msg)}</p>
      <button type="button" class="dc-mod-btn primary" data-close>Закрыть</button>
    `;
    card.querySelector("[data-close]")?.addEventListener("click", () => unmountModal(wrap));
  }

  function renderContentResult(wrap, data) {
    const card = wrap.querySelector(".dc-modal-card");
    card.classList.add("dc-modal-wide");
    card.innerHTML = `
      <div class="dc-mod-eyebrow">🎬 Готово ${data.fallback ? "· шаблон" : ""}</div>
      <h3 class="dc-mod-title">${esc(data.title || "Пост")}</h3>
      ${data.title_variants?.length ? `
        <div class="dc-mod-block">
          <div class="dc-mod-blk-title">Варианты заголовка</div>
          <ul class="dc-mod-list">${data.title_variants.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>
        </div>` : ""}
      <div class="dc-mod-block">
        <div class="dc-mod-blk-title">Текст поста</div>
        <pre class="dc-mod-text" id="dc-result-text">${esc(data.full_text || "")}</pre>
      </div>
      <div class="dc-mod-block">
        <div class="dc-mod-blk-title">📷 Фото-задание</div>
        <div class="dc-mod-note">${esc(data.photo_brief || "")}</div>
        <div class="dc-mod-blk-title" style="margin-top:8px">#️⃣ Хэштеги</div>
        <div class="dc-mod-note">${esc(data.hashtags || "")}</div>
      </div>
      <div class="dc-mod-foot">
        <button type="button" class="dc-mod-btn ghost" id="dc-copy">Скопировать</button>
        <a class="dc-mod-btn primary" href="${esc(data.vk_compose_url || "https://vk.com/feed")}"
           target="_blank" rel="noopener">Открыть в VK ↗</a>
        <button type="button" class="dc-mod-btn ghost" data-close>Закрыть</button>
      </div>
    `;
    card.querySelector("#dc-copy")?.addEventListener("click", () => {
      const t = data.full_text || "";
      navigator.clipboard?.writeText?.(t);
      const b = card.querySelector("#dc-copy");
      if (b) { b.textContent = "Скопировано"; setTimeout(() => b.textContent = "Скопировать", 1600); }
    });
    card.querySelector("[data-close]")?.addEventListener("click", () => unmountModal(wrap));
  }

  // --- Event wizard ---
  function openEventWizard(deputyId, archetypeName) {
    if (!deputyId) return;
    const wrap = mountModal("dc-modal-event");
    let step = 1;
    let source = null;
    let format = null;
    let topic = "";

    function render() {
      const card = wrap.querySelector(".dc-modal-card");
      if (step === 1) {
        card.innerHTML = `
          <div class="dc-mod-eyebrow">📣 Создать медиаповод · шаг 1 из 3</div>
          <h3 class="dc-mod-title">Из чего повод?</h3>
          <div class="dc-mod-grid">
            ${EVENT_SOURCES.map((t) => `
              <button type="button" class="dc-mod-option" data-code="${t.code}">
                <span class="dc-mod-emoji">${t.emoji}</span>
                <span class="dc-mod-label">${t.label}</span>
                <span class="dc-mod-hint">${t.hint}</span>
              </button>`).join("")}
          </div>
          <button type="button" class="dc-mod-close" data-close>✕</button>
        `;
        card.querySelectorAll(".dc-mod-option").forEach((b) => {
          b.addEventListener("click", () => { source = b.getAttribute("data-code"); step = 2; render(); });
        });
      } else if (step === 2) {
        card.innerHTML = `
          <div class="dc-mod-eyebrow">📣 Создать медиаповод · шаг 2 из 3</div>
          <h3 class="dc-mod-title">Формат события?</h3>
          <div class="dc-mod-grid">
            ${EVENT_FORMATS.map((t) => `
              <button type="button" class="dc-mod-option" data-code="${t.code}">
                <span class="dc-mod-emoji">${t.emoji}</span>
                <span class="dc-mod-label">${t.label}</span>
                <span class="dc-mod-hint">${t.hint}</span>
              </button>`).join("")}
          </div>
          <textarea class="dc-mod-input" id="dc-evt-topic" rows="2"
            placeholder="Тема события (опционально): двор у дома 12, отопительный сезон…"></textarea>
          <div class="dc-mod-foot">
            <button type="button" class="dc-mod-btn ghost" id="dc-back">← Назад</button>
          </div>
          <button type="button" class="dc-mod-close" data-close>✕</button>
        `;
        card.querySelectorAll(".dc-mod-option").forEach((b) => {
          b.addEventListener("click", () => {
            format = b.getAttribute("data-code");
            topic = card.querySelector("#dc-evt-topic").value || "";
            step = 3; render();
          });
        });
        card.querySelector("#dc-back").addEventListener("click", () => { step = 1; render(); });
      } else {
        card.innerHTML = `
          <div class="dc-mod-eyebrow">📣 Создать медиаповод · шаг 3 из 3</div>
          <h3 class="dc-mod-title">Собираю сценарий…</h3>
          <div class="dc-mod-loading">Шаги, медиа-чеклист, готовые черновики постов…</div>
          <button type="button" class="dc-mod-close" data-close>✕</button>
        `;
        runEventGen();
      }
      card.querySelector("[data-close]")?.addEventListener("click", () => unmountModal(wrap));
    }

    async function runEventGen() {
      try {
        const res = await fetch("/api/copilot/event/scenario", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ deputy_id: deputyId, source, format, topic }),
        });
        if (!res.ok) {
          renderContentError(wrap, `Не удалось собрать сценарий (${res.status}).`);
          return;
        }
        const data = await res.json();
        renderEventResult(wrap, data);
      } catch (_) {
        renderContentError(wrap, "Сеть недоступна.");
      }
    }
    render();
  }

  function renderEventResult(wrap, data) {
    const card = wrap.querySelector(".dc-modal-card");
    card.classList.add("dc-modal-wide");
    card.innerHTML = `
      <div class="dc-mod-eyebrow">📣 Сценарий медиаповода</div>
      <h3 class="dc-mod-title">${esc(data.format_label || "Событие")} — ${esc(data.topic || "")}</h3>
      <p class="dc-mod-sub">Источник: ${esc(data.source_label || "")} · голос «${esc(data.archetype || "")}»</p>

      <div class="dc-mod-block">
        <div class="dc-mod-blk-title">Шаги</div>
        <ol class="dc-mod-list dc-mod-steps">
          ${(data.steps || []).map((s) => `<li>${esc(s)}</li>`).join("")}
        </ol>
      </div>
      <div class="dc-mod-twocol">
        <div class="dc-mod-block">
          <div class="dc-mod-blk-title">📷 Медиа-чеклист</div>
          <ul class="dc-mod-list">
            ${(data.media_checklist || []).map((s) => `<li>${esc(s)}</li>`).join("")}
          </ul>
        </div>
        <div class="dc-mod-block">
          <div class="dc-mod-blk-title">📞 Кому позвонить</div>
          <ul class="dc-mod-list">
            ${(data.callto || []).map((s) => `<li>${esc(s)}</li>`).join("")}
          </ul>
        </div>
      </div>
      <div class="dc-mod-block">
        <div class="dc-mod-blk-title">Готовые посты</div>
        <div class="dc-mod-drafts">
          ${["teaser", "report", "summary"].map((k) => `
            <div class="dc-mod-draft">
              <div class="dc-mod-draft-tag">${k === "teaser" ? "Тизер" : k === "report" ? "Репортаж" : "Итог"}</div>
              <pre class="dc-mod-text">${esc((data.drafts || {})[k] || "")}</pre>
              <button type="button" class="dc-mod-btn ghost dc-evt-copy"
                data-text="${esc((data.drafts || {})[k] || "")}">Скопировать</button>
            </div>
          `).join("")}
        </div>
      </div>
      <div class="dc-mod-foot">
        <button type="button" class="dc-mod-btn primary" data-close>Готово</button>
      </div>
    `;
    card.querySelectorAll(".dc-evt-copy").forEach((b) => {
      b.addEventListener("click", () => {
        navigator.clipboard?.writeText?.(b.dataset.text || "");
        b.textContent = "Скопировано";
        setTimeout(() => b.textContent = "Скопировать", 1600);
      });
    });
    card.querySelector("[data-close]")?.addEventListener("click", () => unmountModal(wrap));
  }

  // --- Modal helpers ---
  function mountModal(id) {
    const old = document.getElementById(id);
    if (old) old.remove();
    const wrap = document.createElement("div");
    wrap.id = id;
    wrap.className = "dc-modal";
    wrap.innerHTML = `
      <div class="dc-modal-bg" data-bg></div>
      <div class="dc-modal-card"></div>
    `;
    wrap.querySelector("[data-bg]").addEventListener("click", () => unmountModal(wrap));
    document.body.appendChild(wrap);
    return wrap;
  }
  function unmountModal(wrap) {
    if (wrap?.parentNode) wrap.parentNode.removeChild(wrap);
  }

  function onCopyClick(ev) {
    const btn = ev.target.closest(".dc-copy");
    if (!btn) return;
    const text = btn.dataset.text || "";
    if (!text || !navigator.clipboard?.writeText) return;
    navigator.clipboard.writeText(text).then(
      () => { btn.textContent = "Скопировано"; },
      () => { btn.textContent = "Не получилось"; },
    );
    setTimeout(() => { btn.textContent = "Скопировать"; }, 1800);
  }

  function init() {
    renderCabinet();
    document.addEventListener("role:change", () => {
      // При смене роли — перерисовать (или скрыть, если не deputy)
      const hero = document.getElementById(HERO_ID);
      if (!hero) return;
      if (window.cmRole?.get?.() !== "deputy") {
        hero.innerHTML = "";
        return;
      }
      renderCabinet();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
