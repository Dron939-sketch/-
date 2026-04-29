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

  function renderHeader(d, a, rating, profile, bio) {
    const greeting = d.first_name ? `Здравствуйте, ${esc(d.first_name)}!` : "Добро пожаловать!";
    const photo = profile && profile.photo
      ? `<img class="dc-hero-photo" src="${esc(profile.photo)}" alt="${esc(d.name || '')}" />`
      : `<div class="dc-hero-photo dc-hero-photo-stub">${esc((d.first_name || "Д")[0])}</div>`;
    return `
      <div class="dc-hero">
        ${photo}
        <div class="dc-hero-text">
          <div class="dc-hero-eyebrow">Личный кабинет</div>
          <h1 class="dc-hero-greet">${greeting}</h1>
          <div class="dc-hero-meta">
            ${esc(d.name || "")} · ${esc(d.district || "")} ·
            <span class="dc-hero-arch">${archetypeEmoji(a.code)} «${esc(a.name)}»</span>
            ${d.vk_url ? ` · <a href="${esc(d.vk_url)}" target="_blank" rel="noopener">VK ↗</a>` : ""}
          </div>
          <details class="dc-hero-details">
            <summary>Подробнее о профиле</summary>
            ${bio && bio.summary ? `<p class="dc-hero-sub">${esc(bio.summary)}</p>` : ""}
            ${bio && bio.facts ? `
              <div class="dc-hero-facts">
                ${bio.facts.map((f) =>
                  `<span class="dc-hero-fact">${esc(f.icon || "")} ${esc(f.label || "")}</span>`
                ).join("")}
              </div>` : ""}
          </details>
        </div>
        <div class="dc-actions">
          <button type="button" class="dc-action-btn dc-action-primary" id="dc-create-content"
                  title="Готовый пост в твоём стиле за 30 секунд">
            <span class="dc-action-emoji">🎬</span>
            <span class="dc-action-title">Контент</span>
          </button>
          <button type="button" class="dc-action-btn dc-action-secondary" id="dc-create-event"
                  title="Пошаговый сценарий PR-события">
            <span class="dc-action-emoji">📣</span>
            <span class="dc-action-title">Медиаповод</span>
          </button>
          <button type="button" class="dc-action-btn dc-action-audit" id="dc-run-audit"
                  title="Пересчитать аудит VK с нуля">
            <span class="dc-action-emoji">🔄</span>
            <span class="dc-action-title">Аудит VK</span>
          </button>
        </div>
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // Табы — 5 разделов кабинета
  // ---------------------------------------------------------------------------

  const TABS = [
    { id: "today",   icon: "🏠", label: "Сегодня",   sub: "брифинг, миссии, действия" },
    { id: "metrics", icon: "📊", label: "Метрики",   sub: "рейтинг, мейстер, план" },
    { id: "context", icon: "🌐", label: "Контекст",  sub: "город, тренды, комменты" },
    { id: "image",   icon: "🎭", label: "Образ",     sub: "персона, голос, аналитика" },
    { id: "ties",    icon: "👥", label: "Связи",     sub: "коалиция, упоминания" },
  ];

  function loadActiveTab(deputyId) {
    try {
      const v = localStorage.getItem(`cm.deputy.tab.${deputyId || "default"}`);
      return TABS.some((t) => t.id === v) ? v : "today";
    } catch (_) { return "today"; }
  }
  function saveActiveTab(deputyId, tabId) {
    try { localStorage.setItem(`cm.deputy.tab.${deputyId || "default"}`, tabId); } catch (_) {}
  }

  function renderTabs(activeId) {
    return `
      <nav class="dc-tabs" role="tablist">
        ${TABS.map((t) => `
          <button type="button" class="dc-tab ${t.id === activeId ? 'is-active' : ''}"
                  role="tab" aria-selected="${t.id === activeId}"
                  data-tab="${esc(t.id)}">
            <span class="dc-tab-icon">${esc(t.icon)}</span>
            <span class="dc-tab-text">
              <span class="dc-tab-label">${esc(t.label)}</span>
              <span class="dc-tab-sub">${esc(t.sub)}</span>
            </span>
          </button>
        `).join("")}
      </nav>
    `;
  }

  function onTabClick(ev) {
    const btn = ev.target.closest(".dc-tab");
    if (!btn) return;
    const id = btn.getAttribute("data-tab");
    if (!id) return;
    const eid = window.cmRole?.deputyId?.() || null;
    saveActiveTab(eid, id);
    document.querySelectorAll(".dc-tab").forEach((b) => {
      const isActive = b.getAttribute("data-tab") === id;
      b.classList.toggle("is-active", isActive);
      b.setAttribute("aria-selected", String(isActive));
    });
    document.querySelectorAll(".dc-tab-pane").forEach((p) => {
      p.hidden = p.getAttribute("data-tab") !== id;
    });
    // Скролл наверх к табам
    document.querySelector(".dc-tabs")?.scrollIntoView({ behavior: "smooth", block: "start" });
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
    const dos   = (archetype.do || []).slice(0, 3);
    const donts = (archetype.dont || []).slice(0, 2);
    if (audit.state === "no_posts") {
      return `
        <details class="dc-block dc-collapsible">
          <summary class="dc-block-title">👀 Голос архетипа</summary>
          <div class="dc-empty">
            Стена пустая или закрытая. Откройте её и опубликуйте первый пост.
          </div>
        </details>
      `;
    }
    return `
      <details class="dc-block dc-collapsible">
        <summary class="dc-block-title">👀 Голос «${esc(archetype.name)}» — что делать и чего избегать</summary>
        <div class="dc-two-col">
          <div class="dc-col dc-col-good">
            <div class="dc-col-title">Чего ждут</div>
            <ul class="dc-list">
              ${dos.map((s) => `<li>${esc(s)}</li>`).join("")}
            </ul>
          </div>
          <div class="dc-col dc-col-bad">
            <div class="dc-col-title">Чего лучше не делать</div>
            <ul class="dc-list">
              ${donts.map((s) => `<li>${esc(s)}</li>`).join("")}
            </ul>
          </div>
        </div>
      </details>
    `;
  }

  function renderRecommendations(audit) {
    const recs = (audit && audit.recommendations) || [];
    if (recs.length === 0) return "";
    return `
      <div class="dc-block dc-recs-block">
        <div class="dc-block-title">🎯 Рекомендации по улучшению образа</div>
        <p class="dc-empty-sub">После аудита: что подтянуть в стиле, регулярности, тоне.</p>
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
  // Цели на квартал — пользователь выбирает 1-3 направления, под них
  // подсвечиваются миссии и идеи. Хранится в localStorage по deputyId.
  // ---------------------------------------------------------------------------

  const GOALS = [
    { code: "followers",   icon: "📈", label: "Увеличить подписчиков",
      hint: "+50% за квартал" },
    { code: "rating",      icon: "⭐", label: "Поднять рейтинг бренда",
      hint: "до 4.5 из 5 ⭐" },
    { code: "reach",       icon: "🚀", label: "Расширить охват",
      hint: "+30% к среднему" },
    { code: "complaints",  icon: "💬", label: "Закрыть жалобы",
      hint: "≥80% ответов в срок" },
    { code: "coalition",   icon: "🤝", label: "Расширить коалицию",
      hint: "3 совместных проекта" },
    { code: "voice",       icon: "🎭", label: "Усилить голос архетипа",
      hint: "соответствие 70%+" },
  ];

  function _goalsKey(deputyId) {
    return `cm.deputy.goals.${deputyId || "default"}`;
  }
  function loadGoals(deputyId) {
    try {
      const raw = localStorage.getItem(_goalsKey(deputyId));
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (_) { return []; }
  }
  function saveGoals(deputyId, goals) {
    try { localStorage.setItem(_goalsKey(deputyId), JSON.stringify(goals)); } catch (_) {}
  }

  function renderGoals(deputyId) {
    const active = new Set(loadGoals(deputyId));
    return `
      <div class="dc-goals" data-deputy-id="${esc(deputyId || "")}">
        <div class="dc-goals-head">
          <div>
            <div class="dc-goals-eyebrow">🎯 Цели на квартал</div>
            <div class="dc-goals-greet">Выбери до 3 направлений — под них настрою миссии и идеи</div>
          </div>
          <span class="dc-goals-count" id="dc-goals-count">${active.size}/3</span>
        </div>
        <div class="dc-goals-grid">
          ${GOALS.map((g) => `
            <button type="button" class="dc-goal-chip ${active.has(g.code) ? 'is-active' : ''}"
                    data-goal="${esc(g.code)}">
              <span class="dc-goal-icon">${esc(g.icon)}</span>
              <span class="dc-goal-text">
                <span class="dc-goal-label">${esc(g.label)}</span>
                <span class="dc-goal-hint">${esc(g.hint)}</span>
              </span>
              <span class="dc-goal-check">${active.has(g.code) ? "✓" : ""}</span>
            </button>
          `).join("")}
        </div>
      </div>
    `;
  }

  function onGoalClick(ev) {
    const chip = ev.target.closest(".dc-goal-chip");
    if (!chip) return;
    const block = chip.closest(".dc-goals");
    const deputyId = block?.dataset.deputyId;
    const code = chip.getAttribute("data-goal");
    const active = new Set(loadGoals(deputyId));
    if (active.has(code)) {
      active.delete(code);
    } else if (active.size < 3) {
      active.add(code);
    } else {
      // Уже 3 — мигаем счётчиком как warning
      const cnt = document.getElementById("dc-goals-count");
      if (cnt) {
        cnt.classList.add("is-max");
        setTimeout(() => cnt.classList.remove("is-max"), 800);
      }
      return;
    }
    saveGoals(deputyId, [...active]);
    chip.classList.toggle("is-active");
    const check = chip.querySelector(".dc-goal-check");
    if (check) check.textContent = active.has(code) ? "✓" : "";
    const cnt = document.getElementById("dc-goals-count");
    if (cnt) cnt.textContent = `${active.size}/3`;
  }

  // ---------------------------------------------------------------------------
  // Утренний брифинг — что важно сегодня + голос Джарвиса
  // ---------------------------------------------------------------------------

  function renderBriefing(b, deputyId) {
    if (!b || !(b.items || []).length) return "";
    return `
      <div class="dc-briefing" data-deputy-id="${esc(deputyId || "")}">
        <div class="dc-brief-head">
          <div>
            <div class="dc-brief-eyebrow">☕ Сегодня для тебя</div>
            <div class="dc-brief-greet">${esc(b.greeting || "")}</div>
          </div>
          <button type="button" class="dc-brief-voice" id="dc-brief-voice"
                  title="Послушать брифинг голосом">
            <span class="dc-brief-voice-icon">🎙</span>
            <span class="dc-brief-voice-lbl">Послушать (~2 мин)</span>
          </button>
        </div>
        <div class="dc-brief-grid">
          ${b.items.map((it) => `
            <div class="dc-brief-card dc-brief-${esc(it.kind || 'item')}">
              <div class="dc-brief-card-icon">${esc(it.icon || "▶")}</div>
              <div class="dc-brief-card-tag">${esc(it.tag || "")}</div>
              <div class="dc-brief-card-title">${esc(it.title || "")}</div>
              <div class="dc-brief-card-body">${esc(it.body || "")}</div>
              ${it.action ? `
                <button type="button" class="dc-brief-card-go"
                        data-wizard="${esc(it.wizard || '')}"
                        data-text="${esc(it.draft || it.body || '')}">
                  ${esc(it.action)} →
                </button>
              ` : ""}
            </div>
          `).join("")}
        </div>
        <audio class="dc-brief-audio" id="dc-brief-audio" preload="none"></audio>
      </div>
    `;
  }

  let briefingPlayer = null;
  async function onBriefingVoiceClick(ev) {
    const btn = ev.target.closest("#dc-brief-voice");
    if (!btn) return;
    const block = btn.closest(".dc-briefing");
    const deputyId = block?.dataset.deputyId;
    if (!deputyId) return;
    const audio = document.getElementById("dc-brief-audio");
    btn.disabled = true;
    const lbl = btn.querySelector(".dc-brief-voice-lbl");
    if (lbl) lbl.textContent = "Готовлю…";
    try {
      const r = await fetch(`/api/copilot/deputy/briefing/voice?external_id=${encodeURIComponent(deputyId)}`);
      if (!r.ok) {
        if (lbl) lbl.textContent = "Не получилось";
        btn.disabled = false;
        return;
      }
      const data = await r.json();
      if (data.audio && audio) {
        audio.src = `data:${data.audio_mime || "audio/mpeg"};base64,${data.audio}`;
        audio.play().catch(() => {});
        if (lbl) lbl.textContent = "Идёт воспроизведение…";
        audio.onended = () => {
          if (lbl) lbl.textContent = "Послушать ещё раз";
          btn.disabled = false;
        };
      } else if (data.text && window.speechSynthesis) {
        // Fallback: speechSynthesis browser
        try {
          window.speechSynthesis.cancel();
          const u = new SpeechSynthesisUtterance(data.text);
          u.lang = "ru-RU"; u.rate = 1.0;
          u.onend = () => {
            if (lbl) lbl.textContent = "Послушать ещё раз";
            btn.disabled = false;
          };
          window.speechSynthesis.speak(u);
          if (lbl) lbl.textContent = "Идёт воспроизведение…";
        } catch (_) {
          if (lbl) lbl.textContent = "Голос недоступен";
          btn.disabled = false;
        }
      } else {
        if (lbl) lbl.textContent = "Голос недоступен";
        btn.disabled = false;
      }
    } catch (_) {
      if (lbl) lbl.textContent = "Сеть недоступна";
      btn.disabled = false;
    }
  }

  function onBriefingCardClick(ev) {
    const btn = ev.target.closest(".dc-brief-card-go");
    if (!btn) return;
    const wizard = btn.getAttribute("data-wizard");
    if (wizard === "content") {
      document.getElementById("dc-create-content")?.click();
      return;
    }
    if (wizard === "event") {
      document.getElementById("dc-create-event")?.click();
      return;
    }
    // Без wizard — копируем body / draft в clipboard если есть
    const text = btn.dataset.text || "";
    if (text && navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text);
      btn.textContent = "Скопировано →";
      setTimeout(() => {
        const card = btn.closest(".dc-brief-card");
        const tag = card?.dataset.action || "→";
        btn.textContent = tag;
      }, 1600);
    }
  }

  // ---------------------------------------------------------------------------
  // Образ депутата — расширенный портрет
  // ---------------------------------------------------------------------------

  function renderPersona(p, affinity, voice) {
    if (!p || !p.headline) return "";
    const top3 = (affinity || []).slice(0, 3);
    const main = top3[0];
    return `
      <div class="dc-persona">
        <div class="dc-persona-eyebrow">Образ глазами горожан</div>
        <div class="dc-persona-headline">${esc(p.headline)}</div>
        <div class="dc-persona-traits">
          ${(p.traits || []).map((t) => `<span class="dc-persona-tag">${esc(t)}</span>`).join("")}
        </div>
        ${main ? `
          <div class="dc-affinity-main">
            <div class="dc-affinity-eyebrow">Образ, к которому очень близка</div>
            <div class="dc-affinity-headline">
              ${archetypeEmoji(main.code)} «${esc(main.name)}» —
              <span class="dc-affinity-pct">${main.affinity}%</span>
            </div>
            <div class="dc-affinity-short">${esc(main.short || "")}</div>
          </div>` : ""}
        ${top3.length > 1 ? `
          <div class="dc-affinity-rest">
            <div class="dc-persona-lbl">Также читается как</div>
            <div class="dc-affinity-bars">
              ${top3.slice(1).map((a) => `
                <div class="dc-affinity-row">
                  <div class="dc-affinity-name">${archetypeEmoji(a.code)} ${esc(a.name)}</div>
                  <div class="dc-affinity-bar">
                    <div class="dc-affinity-bar-fill" style="width:${a.affinity}%"></div>
                  </div>
                  <div class="dc-affinity-val">${a.affinity}%</div>
                </div>
              `).join("")}
            </div>
          </div>` : ""}
        <div class="dc-persona-twocol">
          <div class="dc-persona-col">
            <div class="dc-persona-lbl">Как читается</div>
            <div class="dc-persona-text">${esc(p.reads_as || "")}</div>
          </div>
          <div class="dc-persona-col dc-persona-warn">
            <div class="dc-persona-lbl">Зона риска</div>
            <div class="dc-persona-text">${esc(p.danger || "")}</div>
          </div>
        </div>
        ${voice && voice.state === "ok" ? `
          <div class="dc-voice">
            <div class="dc-persona-lbl">🎙 Голос-портрет — что я услышал в твоих постах</div>
            <div class="dc-voice-headline">${esc(voice.headline || "")}</div>
            <div class="dc-voice-body">
              ${(voice.top_words || []).length ? `
                <div class="dc-voice-words">
                  ${voice.top_words.slice(0, 6).map((w) =>
                    `<span class="dc-voice-word">${esc(w.word)} <small>×${w.count}</small></span>`
                  ).join("")}
                </div>` : ""}
              <div class="dc-voice-stats">
                <span>📏 ср. предложение ~${voice.avg_sentence || 0} симв</span>
                ${voice.shares ? `
                  <span>💬 эмодзи в ${voice.shares.emoji}% постов</span>
                  <span>❗ восклицания ${voice.shares.excl}%</span>
                  <span>❓ вопросы ${voice.shares.question}%</span>
                ` : ""}
                <span>🌡 тон <b>${esc(voice.tone || "")}</b> (${voice.tone_score}%)</span>
              </div>
            </div>
          </div>` : ""}
        ${(p.style_hints || []).length ? `
          <div class="dc-persona-hints">
            ${p.style_hints.map((h) => `<div class="dc-persona-hint">· ${esc(h)}</div>`).join("")}
          </div>` : ""}
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // Карта внимания — что обсуждают сейчас по её секторам
  // ---------------------------------------------------------------------------

  function renderTrendsNow(t) {
    if (!t || !(t.trends || []).length) {
      if (t && t.state === "no_data") {
        return `
          <div class="dc-block dc-trends-empty">
            <div class="dc-block-title">🌐 Карта внимания</div>
            <div class="dc-empty-sub">Пока нет данных. Подключи VK API token или БД новостей —
            здесь появятся горячие темы по твоим секторам.</div>
          </div>`;
      }
      return "";
    }
    const sourceTag = t.source === "vk"
      ? `<span class="dc-trends-source">live VK</span>`
      : `<span class="dc-trends-source dc-trends-fallback">из новостей</span>`;
    return `
      <details class="dc-block dc-collapsible dc-trends-block">
        <summary class="dc-block-title">
          🌐 Карта внимания — что обсуждают сейчас
          ${sourceTag}
        </summary>
        <p class="dc-empty-sub">Топ горячих тем за 48ч в твоих секторах. Тот, кто заходит в тему первым — собирает охват.</p>
        <div class="dc-trends-list">
          ${t.trends.map((tr, i) => `
            <div class="dc-trend-card">
              <div class="dc-trend-num">${i + 1}</div>
              <div class="dc-trend-body">
                <div class="dc-trend-kw">${esc(tr.keyword || "")}</div>
                <div class="dc-trend-stats">
                  📝 ${tr.posts || 0} постов
                  ${tr.engagement ? `· 👍 ${tr.engagement} реакций` : ""}
                </div>
              </div>
            </div>
          `).join("")}
        </div>
      </details>
    `;
  }

  // ---------------------------------------------------------------------------
  // Городской контекст: ключевые показатели + новости по секторам
  // ---------------------------------------------------------------------------

  function renderCityBrief(b) {
    if (!b || (!(b.kpi || []).length && !(b.news_for_me || []).length)) return "";
    const counts = b.news_counts || {};
    return `
      <div class="dc-block dc-city-block">
        <div class="dc-block-title">
          🏙 Город сегодня
          ${counts.total ? `<span class="dc-city-meta">·  за 24ч: ${counts.total} сюжетов</span>` : ""}
        </div>
        ${(b.kpi || []).length ? `
          <div class="dc-city-kpi">
            ${b.kpi.map((v) => `
              <div class="dc-kpi-tile ${v.important ? 'dc-kpi-mine' : ''}"
                   title="${esc(v.name)} · ${v.value}/${v.max}">
                <div class="dc-kpi-code">${esc(v.code)}</div>
                <div class="dc-kpi-val">${v.value}<span class="dc-kpi-max">/${v.max}</span></div>
                <div class="dc-kpi-name">${esc(v.name)}</div>
                ${v.important ? `<div class="dc-kpi-mine-tag">мой сектор</div>` : ""}
              </div>
            `).join("")}
          </div>` : ""}
        ${(b.news_for_me || []).length ? `
          <div class="dc-city-news">
            <div class="dc-persona-lbl">📰 Заслуживает твоего внимания</div>
            <ul class="dc-news-list">
              ${b.news_for_me.map((n) => `
                <li>
                  <span class="dc-news-text">${esc(n.text || "")}</span>
                  ${(n.sectors || []).length ? `
                    <span class="dc-news-tags">
                      ${n.sectors.map((s) => `<span class="dc-news-tag">${esc(s)}</span>`).join("")}
                    </span>` : ""}
                </li>
              `).join("")}
            </ul>
          </div>` : ""}
        ${b.state === "no_db" ? `
          <div class="dc-empty-sub">Подключи БД с метриками и новостями — здесь появится живая сводка.</div>
        ` : ""}
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // Алгоритм Мейстера для депутата — 4 вектора + прогноз 4 недели
  // ---------------------------------------------------------------------------

  function renderMeister(m) {
    if (!m || !m.current) return "";
    const cur = m.current;
    return `
      <div class="dc-block dc-meister-block">
        <div class="dc-block-title">
          🧮 Алгоритм Мейстера · личный
          <span class="dc-meister-comp">${m.composite_now}/6 → ${m.composite_4w}/6
            <span class="dc-meister-delta ${m.delta >= 0 ? 'up' : 'down'}">
              ${m.delta >= 0 ? "+" : ""}${m.delta}
            </span>
          </span>
        </div>
        <div class="dc-meister-axes">
          ${cur.map((v) => `
            <div class="dc-meister-axis" title="${esc(v.what || '')}">
              <div class="dc-meister-emoji" style="background:${esc(v.color)}33; border-color:${esc(v.color)}">${esc(v.emoji || v.code)}</div>
              <div class="dc-meister-name-row">
                <div class="dc-meister-name">${esc(v.name)}</div>
                <div class="dc-meister-what">${esc(v.what || "")}</div>
              </div>
              <div class="dc-meister-bar">
                <div class="dc-meister-bar-fill"
                     style="width:${(v.value / 6 * 100).toFixed(1)}%; background:${esc(v.color)}"></div>
              </div>
              <div class="dc-meister-value">${v.value}/6 <span class="muted">(${v.raw}${esc(v.unit || '')})</span></div>
            </div>
          `).join("")}
        </div>
        ${m.summary ? `<div class="dc-meister-summary">${esc(m.summary)}</div>` : ""}
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // Где комментировать — горячие посты для роста подписчиков и охвата
  // ---------------------------------------------------------------------------

  function renderCommentTargets(t) {
    if (!t || !(t.targets || []).length) {
      if (t && t.state === "no_data") {
        return `
          <details class="dc-block dc-collapsible dc-comments-empty">
            <summary class="dc-block-title">💬 Где комментировать для роста</summary>
            <div class="dc-empty-sub">Подключи VK API token — здесь появятся посты горожан с высоким охватом и низкой конкуренцией в комментариях.</div>
          </details>`;
      }
      return "";
    }
    return `
      <div class="dc-block dc-comments-block">
        <div class="dc-block-title">
          💬 Где комментировать — рост подписчиков
          <span class="dc-trends-source">live VK</span>
        </div>
        <p class="dc-empty-sub">
          Посты с высоким охватом и небольшим количеством комментариев — твой комментарий будет на виду. Открой пост, скопируй готовый ответ.
        </p>
        <div class="dc-comments-list">
          ${t.targets.map((c, i) => `
            <div class="dc-comment-card">
              <div class="dc-comment-head">
                <div class="dc-comment-stats">
                  👍 ${c.likes} · 👁 ${c.views} · 💬 ${c.comments}
                  <span class="dc-comment-opp">opp ${c.opportunity}</span>
                </div>
                ${c.url ? `<a href="${esc(c.url)}" target="_blank" rel="noopener"
                  class="dc-comment-go">Открыть пост ↗</a>` : ""}
              </div>
              <div class="dc-comment-text">${esc(c.text || "")}</div>
              <div class="dc-comment-suggested">
                <div class="dc-comment-suggested-tag">Шаблон в твоём голосе</div>
                <pre class="dc-mod-text">${esc(c.comment || "")}</pre>
                <button type="button" class="dc-mod-btn ghost dc-comment-copy"
                        data-text="${esc(c.comment || "")}">Скопировать</button>
              </div>
            </div>
          `).join("")}
        </div>
      </div>
    `;
  }

  function onCommentCopyClick(ev) {
    const btn = ev.target.closest(".dc-comment-copy");
    if (!btn) return;
    const text = btn.dataset.text || "";
    if (text && navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text);
      btn.textContent = "Скопировано";
      setTimeout(() => btn.textContent = "Скопировать", 1600);
    }
  }

  // ---------------------------------------------------------------------------
  // Кнопка «Аудит страницы VK» — форсированный пересчёт через ?refresh=1
  // ---------------------------------------------------------------------------

  async function onRunAuditClick(ev) {
    const btn = ev.target.closest("#dc-run-audit");
    if (!btn) return;
    const eid = window.cmRole?.deputyId?.() || null;
    if (!eid) return;
    const lbl = btn.querySelector(".dc-action-title");
    const sub = btn.querySelector(".dc-action-sub");
    const orig_lbl = lbl?.textContent || "";
    const orig_sub = sub?.textContent || "";
    btn.disabled = true;
    if (lbl) lbl.textContent = "Анализирую…";
    if (sub) sub.textContent = "VK-страница, тексты, тон";
    try {
      const hero = document.getElementById(HERO_ID);
      if (hero) hero.classList.add("dc-auditing");
      // refresh=1 форсирует пересчёт на бэке
      const r = await fetch(`/api/copilot/deputy/cabinet?external_id=${encodeURIComponent(eid)}&refresh=1`);
      if (!r.ok) {
        if (lbl) lbl.textContent = "Не получилось";
        btn.disabled = false;
        return;
      }
      const data = await r.json();
      if (hero) {
        hero.innerHTML = "";
        hero.classList.remove("dc-auditing");
      }
      // Перерендериваем
      await renderCabinet();
      // Прокручиваем к рекомендациям после аудита
      document.querySelector(".dc-recs")?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (_) {
      if (lbl) lbl.textContent = "Сеть недоступна";
      btn.disabled = false;
    }
  }

  // ---------------------------------------------------------------------------
  // Виджет «Действия по проблеме» — карточки ситуаций + on-demand план
  // ---------------------------------------------------------------------------

  function renderActionsWidget(situations, deputyId) {
    if (!situations || situations.length === 0) return "";
    return `
      <div class="dc-block dc-actions-block" data-deputy-id="${esc(deputyId || "")}">
        <div class="dc-block-title">🧭 Действия — что делать в типовой ситуации</div>
        <p class="dc-empty-sub">
          Это для тебя лично, не для замов. Выбери ситуацию — получишь пошаговый план + контакты + жанры постов.
        </p>
        <div class="dc-act-grid">
          ${situations.map((s) => `
            <button type="button" class="dc-act-card" data-sit="${esc(s.code)}">
              <div class="dc-act-emoji">${esc(s.emoji || "")}</div>
              <div class="dc-act-label">${esc(s.label || "")}</div>
              <div class="dc-act-hint">${esc(s.hint || "")}</div>
            </button>
          `).join("")}
        </div>
        <div class="dc-act-result" id="dc-act-result"></div>
      </div>
    `;
  }

  async function onActionClick(ev) {
    const card = ev.target.closest(".dc-act-card");
    if (!card) return;
    const block = card.closest(".dc-actions-block");
    const deputyId = block?.dataset.deputyId;
    const situation = card.getAttribute("data-sit");
    const result = document.getElementById("dc-act-result");
    if (!deputyId || !situation || !result) return;
    result.innerHTML = `<div class="dc-mod-loading">Собираю план…</div>`;
    try {
      const res = await fetch("/api/copilot/deputy/action-plan", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ deputy_id: deputyId, situation }),
      });
      if (!res.ok) {
        result.innerHTML = `<div class="dc-empty-sub">Не получилось (${res.status}).</div>`;
        return;
      }
      const data = await res.json();
      result.innerHTML = `
        <div class="dc-act-plan">
          <div class="dc-act-plan-head">
            <span class="dc-act-emoji">${esc(data.emoji || "")}</span>
            <span class="dc-act-plan-label">${esc(data.label || "")}</span>
          </div>
          <ol class="dc-act-steps">
            ${(data.steps || []).map((s) => `
              <li>
                <div class="dc-act-when">${esc(s.when || "")}</div>
                <div class="dc-act-do">${esc(s.do || "")}</div>
              </li>
            `).join("")}
          </ol>
          <div class="dc-act-twocol">
            ${data.media ? `
              <div class="dc-act-block">
                <div class="dc-act-blk-title">📷 Что снять</div>
                <div>${esc(data.media)}</div>
              </div>` : ""}
            ${(data.contacts && data.contacts.length) ? `
              <div class="dc-act-block">
                <div class="dc-act-blk-title">📞 С кем связаться</div>
                <ul class="dc-mod-list">
                  ${data.contacts.map((c) => `<li>${esc(c)}</li>`).join("")}
                </ul>
              </div>` : ""}
          </div>
        </div>
      `;
    } catch (_) {
      result.innerHTML = `<div class="dc-empty-sub">Сеть недоступна.</div>`;
    }
  }

  // ---------------------------------------------------------------------------
  // Виджет «Сценарии» — what-if симулятор
  // ---------------------------------------------------------------------------

  function renderScenarioWidget(meta, initial) {
    const params = (meta && meta.params) || {};
    if (Object.keys(params).length === 0) return "";
    const sliderRow = (key) => {
      const p = params[key];
      const val = (initial && initial[key] != null) ? initial[key] : p.default;
      return `
        <div class="dc-scn-row">
          <label class="dc-scn-label">
            <span>${esc(p.label)}</span>
            <span class="dc-scn-val" id="dc-scn-val-${key}">${val}${esc(p.unit || "")}</span>
          </label>
          <input type="range" min="${p.min}" max="${p.max}" step="${p.step}"
                 value="${val}" class="dc-scn-slider" data-key="${esc(key)}"
                 data-unit="${esc(p.unit || "")}" />
        </div>
      `;
    };
    return `
      <details class="dc-block dc-collapsible dc-scn-block">
        <summary class="dc-block-title">📊 Сценарии — что если…</summary>
        <p class="dc-empty-sub">Крути ползунки — увидишь, как изменится твой рейтинг и 4 вектора.</p>
        <div class="dc-scn-controls">
          ${Object.keys(params).map(sliderRow).join("")}
        </div>
        <div class="dc-scn-output" id="dc-scn-output">
          <div class="dc-scn-rating">
            <span class="dc-scn-rating-num" id="dc-scn-rating">—</span>
            <span class="dc-scn-rating-lbl">прогнозный рейтинг (0-5)</span>
          </div>
          <div class="dc-scn-vectors" id="dc-scn-vectors"></div>
        </div>
      </details>
    `;
  }

  let scenarioDebounce = null;
  function onScenarioInput(ev) {
    const sl = ev.target.closest(".dc-scn-slider");
    if (!sl) return;
    const key = sl.getAttribute("data-key");
    const unit = sl.getAttribute("data-unit") || "";
    const lbl = document.getElementById(`dc-scn-val-${key}`);
    if (lbl) lbl.textContent = sl.value + unit;
    // Debounce — крутят быстро, дёргаем после паузы
    if (scenarioDebounce) clearTimeout(scenarioDebounce);
    scenarioDebounce = setTimeout(runScenario, 180);
  }

  async function runScenario() {
    const block = document.querySelector(".dc-scn-block");
    if (!block) return;
    const sliders = block.querySelectorAll(".dc-scn-slider");
    const payload = {};
    sliders.forEach((s) => { payload[s.getAttribute("data-key")] = parseFloat(s.value); });
    try {
      const res = await fetch("/api/copilot/deputy/scenario", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) return;
      const data = await res.json();
      const ratingEl = document.getElementById("dc-scn-rating");
      if (ratingEl) ratingEl.textContent = data.rating;
      const vectorsEl = document.getElementById("dc-scn-vectors");
      if (vectorsEl) {
        vectorsEl.innerHTML = (data.vectors || []).map((v) => `
          <div class="dc-scn-vec">
            <div class="dc-scn-vec-code">${esc(v.code)}</div>
            <div class="dc-scn-vec-name">${esc(v.name)}</div>
            <div class="dc-scn-vec-val">${v.value}/6</div>
          </div>
        `).join("");
      }
    } catch (_) {}
  }

  // ---------------------------------------------------------------------------
  // Идеи и пиар — top-3 на эту неделю
  // ---------------------------------------------------------------------------

  function renderPrIdeas(ideas) {
    if (!ideas || ideas.length === 0) return "";
    return `
      <div class="dc-block">
        <div class="dc-block-title">💡 Идеи и пиар на неделе</div>
        <div class="dc-ideas-grid">
          ${ideas.map((it) => `
            <div class="dc-idea-card">
              <div class="dc-idea-head">
                <span class="dc-idea-icon">${esc(it.icon || "")}</span>
                <span class="dc-idea-when">${esc(it.when || "")}</span>
              </div>
              <div class="dc-idea-title">${esc(it.title || "")}</div>
              <div class="dc-idea-action">${esc(it.action || "")}</div>
              <button type="button" class="dc-idea-go" data-wizard="${esc(it.wizard || 'content')}">
                Запустить →
              </button>
            </div>
          `).join("")}
        </div>
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // Личные задачи — упрощённый Эйзенхауэр для депутата
  // ---------------------------------------------------------------------------

  const QUADRANT_LABEL = {
    do_now:   { label: "Сегодня", color: "urgent" },
    schedule: { label: "Запланировать", color: "important" },
    delegate: { label: "Регулярно", color: "routine" },
  };

  function renderPersonalTasks(tasks) {
    if (!tasks || tasks.length === 0) return "";
    return `
      <div class="dc-block">
        <div class="dc-block-title">🗂 Мои задачи на неделю</div>
        <div class="dc-tasks">
          ${tasks.map((t) => {
            const q = QUADRANT_LABEL[t.quadrant] || QUADRANT_LABEL.schedule;
            return `
              <div class="dc-task dc-task-${esc(q.color)}">
                <div class="dc-task-q">${esc(q.label)}</div>
                <div class="dc-task-body">
                  <div class="dc-task-title">${esc(t.title || "")}</div>
                  ${t.subtitle ? `<div class="dc-task-sub">${esc(t.subtitle)}</div>` : ""}
                </div>
              </div>
            `;
          }).join("")}
        </div>
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // Чего ждут избиратели — derived из секторов
  // ---------------------------------------------------------------------------

  function renderExpectations(items) {
    if (!items || items.length === 0) return "";
    return `
      <details class="dc-block dc-collapsible">
        <summary class="dc-block-title">🎯 Чего ждут от меня избиратели</summary>
        <div class="dc-chip-grid">
          ${items.map((it) => `
            <button type="button" class="dc-chip dc-chip-${esc(it.priority || 'medium')}"
                    title="${esc(it.why || '')}"
                    data-text="${esc(it.title || '')}: ${esc(it.why || '')}">
              <span class="dc-chip-icon">${it.priority === "high" ? "★" : "○"}</span>
              <span class="dc-chip-text">
                <span class="dc-chip-label">${esc(it.title || "")}</span>
                <span class="dc-chip-meta">${esc(it.sector || "")}</span>
              </span>
            </button>
          `).join("")}
        </div>
      </details>
    `;
  }

  // ---------------------------------------------------------------------------
  // Упоминания обо мне — VK-search proxy (на старте demo)
  // ---------------------------------------------------------------------------

  function renderMentions(m) {
    if (!m || !m.items || m.items.length === 0) return "";
    const icon = (k) => k === "positive" ? "💚" : k === "critical" ? "⚠" : "·";
    return `
      <details class="dc-block dc-collapsible">
        <summary class="dc-block-title">
          🔔 Упоминания обо мне
          ${m.data_kind === "demo" ? `<span class="dc-fallback-tag">пример</span>` : ""}
        </summary>
        ${m.summary ? `<p class="dc-empty-sub">${esc(m.summary)}</p>` : ""}
        <div class="dc-chip-grid">
          ${m.items.map((it) => `
            <button type="button" class="dc-chip dc-chip-${esc(it.weight || 'neutral')}"
                    title="«${esc(it.text || '')}»"
                    data-text="${esc(it.source || '')} · ${esc(it.context || '')}">
              <span class="dc-chip-icon">${icon(it.kind)}</span>
              <span class="dc-chip-text">
                <span class="dc-chip-label">${esc(it.source || "")} · ${esc(it.context || "")}</span>
                <span class="dc-chip-meta">«${esc((it.text || '').slice(0, 60))}…»</span>
              </span>
            </button>
          `).join("")}
        </div>
        ${m.hint ? `<div class="dc-empty-sub" style="margin-top:8px">${esc(m.hint)}</div>` : ""}
      </details>
    `;
  }

  // ---------------------------------------------------------------------------
  // Коалиция — соседи по округу + руководство Совета
  // ---------------------------------------------------------------------------

  function renderCoalition(c) {
    if (!c || !c.items || c.items.length === 0) return "";
    return `
      <details class="dc-block dc-collapsible">
        <summary class="dc-block-title">🤝 Коалиция</summary>
        <div class="dc-chip-grid">
          ${c.items.map((it) => `
            <button type="button" class="dc-chip dc-chip-${esc(it.scope || 'neighbour')}"
                    data-text="${esc(it.name || '')} — сильна в ${esc(it.strength || '')}">
              <span class="dc-chip-icon">${it.scope === 'leadership' ? '👑' : '🤝'}</span>
              <span class="dc-chip-text">
                <span class="dc-chip-label">${esc(it.name || "")}</span>
                <span class="dc-chip-meta">${esc(it.role || "")} · ${esc(it.strength || "")}</span>
              </span>
            </button>
          `).join("")}
        </div>
        ${c.hint ? `<div class="dc-empty-sub" style="margin-top:8px">${esc(c.hint)}</div>` : ""}
      </details>
    `;
  }

  // ---------------------------------------------------------------------------
  // Миссии недели — gamification: рейтинг → action-list
  // ---------------------------------------------------------------------------

  function renderMissions(missions) {
    if (!missions || missions.length === 0) return "";
    return `
      <div class="dc-block dc-missions-block">
        <div class="dc-block-title">🎯 Миссии недели</div>
        <div class="dc-missions">
          ${missions.map((m, i) => `
            <div class="dc-mission" data-code="${esc(m.code || '')}">
              <div class="dc-mission-num">${i + 1}</div>
              <div class="dc-mission-body">
                <div class="dc-mission-title">${esc(m.title || "")}</div>
                <div class="dc-mission-why">${esc(m.why || "")}</div>
                ${m.hint ? `<div class="dc-mission-hint">${esc(m.hint)}</div>` : ""}
              </div>
              <div class="dc-mission-effort dc-effort-${esc(m.effort || 'M')}">${esc(m.effort || 'M')}</div>
            </div>
          `).join("")}
        </div>
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // Шаблоны ответов на жалобы — карточки + on-demand генерация
  // ---------------------------------------------------------------------------

  function renderReplyTemplates(categories, deputyId) {
    if (!categories || categories.length === 0) return "";
    return `
      <details class="dc-block dc-collapsible dc-replies-block" data-deputy-id="${esc(deputyId || "")}">
        <summary class="dc-block-title">💬 Готовые ответы на жалобы</summary>
        <p class="dc-empty-sub">Кликни — Джарвис соберёт ответ в твоём голосе. Можно копировать сразу.</p>
        <div class="dc-replies-grid">
          ${categories.map((c) => `
            <button type="button" class="dc-reply-card" data-cat="${esc(c.code)}">
              <div class="dc-reply-emoji">${esc(c.emoji || "")}</div>
              <div class="dc-reply-label">${esc(c.label || "")}</div>
              <div class="dc-reply-example">${esc(c.example || "")}</div>
            </button>
          `).join("")}
        </div>
        <div class="dc-reply-result" id="dc-reply-result"></div>
      </details>
    `;
  }

  async function onReplyClick(ev) {
    const card = ev.target.closest(".dc-reply-card");
    if (!card) return;
    const block = card.closest(".dc-replies-block");
    const deputyId = block?.dataset.deputyId;
    const category = card.getAttribute("data-cat");
    const result = document.getElementById("dc-reply-result");
    if (!deputyId || !category || !result) return;
    result.innerHTML = `<div class="dc-mod-loading">Собираю ответ в твоём голосе…</div>`;
    try {
      const res = await fetch("/api/copilot/reply/render", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ deputy_id: deputyId, category }),
      });
      if (!res.ok) {
        result.innerHTML = `<div class="dc-empty-sub">Не получилось (${res.status}).</div>`;
        return;
      }
      const data = await res.json();
      result.innerHTML = `
        <div class="dc-reply-output">
          <div class="dc-reply-tag">Ответ в голосе «${esc(data.archetype || "—")}»</div>
          <pre class="dc-mod-text">${esc(data.text || "")}</pre>
          <button type="button" class="dc-mod-btn primary" id="dc-reply-copy">Скопировать</button>
        </div>
      `;
      const copyBtn = document.getElementById("dc-reply-copy");
      copyBtn?.addEventListener("click", () => {
        navigator.clipboard?.writeText?.(data.text || "");
        copyBtn.textContent = "Скопировано";
        setTimeout(() => copyBtn.textContent = "Скопировать", 1600);
      });
    } catch (_) {
      result.innerHTML = `<div class="dc-empty-sub">Сеть недоступна.</div>`;
    }
  }

  // ---------------------------------------------------------------------------
  // Округ сегодня — приоритеты по секторам (на старте — demo-карточки)
  // ---------------------------------------------------------------------------

  function renderDistrictToday(dt) {
    const items = (dt && dt.items) || [];
    if (items.length === 0) return "";
    const isDemo = dt.data_kind === "demo";
    return `
      <details class="dc-block dc-collapsible">
        <summary class="dc-block-title">
          🏘 Округ сегодня
          ${isDemo ? `<span class="dc-fallback-tag">пример</span>` : ""}
        </summary>
        <div class="dc-chip-grid">
          ${items.map((it) => `
            <button type="button" class="dc-chip"
                    title="${esc(it.text || '')}"
                    data-text="${esc(it.sector || '')}: ${esc(it.text || '')}">
              <span class="dc-chip-icon">📍</span>
              <span class="dc-chip-text">
                <span class="dc-chip-label">${esc(it.sector || "")}</span>
                <span class="dc-chip-meta">${esc((it.text || '').slice(0, 70))}…</span>
              </span>
            </button>
          `).join("")}
        </div>
        ${isDemo && dt.hint ? `<div class="dc-empty-sub" style="margin-top:8px">${esc(dt.hint)}</div>` : ""}
      </details>
    `;
  }

  // ---------------------------------------------------------------------------
  // Heatmap времени публикаций
  // ---------------------------------------------------------------------------

  function renderTimingHeatmap(timing) {
    const h = timing && timing.heatmap;
    if (!h || h.state !== "ok") return "";
    const days  = h.days  || [];
    const bands = h.bands || [];
    // matrix — 28 ячеек 7×4. Найдём max avg_likes для нормализации цвета.
    const matrix = h.matrix || [];
    const maxAvg = matrix.reduce((m, c) => Math.max(m, c.avg_likes || 0), 0) || 1;
    const cellAt = (dow, band) => matrix.find((c) => c.dow === dow && c.band === band);

    const headerRow = `<th></th>` + days.map((d) => `<th>${esc(d)}</th>`).join("");
    const rows = bands.map((band) => {
      const cells = days.map((_, dow) => {
        const c = cellAt(dow, band);
        const intensity = c ? Math.min(1, (c.avg_likes || 0) / maxAvg) : 0;
        const alpha = 0.08 + intensity * 0.55;
        const labelTitle = c
          ? `${days[dow]}, ${band}: ${c.count} постов, в среднем ${c.avg_likes} лайков`
          : `${days[dow]}, ${band}: нет данных`;
        return `<td title="${esc(labelTitle)}"
                  style="background:rgba(94,168,255,${alpha.toFixed(2)})">
                  ${c && c.count > 0 ? `<span class="dc-hm-likes">${c.avg_likes}</span>` : ""}
                </td>`;
      }).join("");
      return `<tr><th>${esc(band)}</th>${cells}</tr>`;
    }).join("");

    return `
      <details class="dc-block dc-collapsible">
        <summary class="dc-block-title">📊 Когда лучше публиковать</summary>
        <table class="dc-heatmap">
          <thead><tr>${headerRow}</tr></thead>
          <tbody>${rows}</tbody>
        </table>
        ${timing.tip ? `<div class="dc-heatmap-tip">${esc(timing.tip)}</div>` : ""}
      </details>
    `;
  }

  // ---------------------------------------------------------------------------
  // Поводы недели — календарь дат + сезонные идеи
  // ---------------------------------------------------------------------------

  function renderCalendar(events) {
    if (!events || events.length === 0) return "";
    const visible = events.slice(0, 5);
    return `
      <details class="dc-block dc-collapsible">
        <summary class="dc-block-title">🗓 Поводы недели</summary>
        <div class="dc-cal-list">
          ${visible.map((e) => {
            const when = e.days_until == null
              ? "сезонный"
              : e.days_until === 0 ? "сегодня"
              : e.days_until === 1 ? "завтра"
              : `через ${e.days_until} дн`;
            const dt = e.date_iso
              ? new Date(e.date_iso).toLocaleDateString("ru-RU",
                  { day: "numeric", month: "short" })
              : "";
            return `
              <div class="dc-cal-card">
                <div class="dc-cal-when">${esc(when)}${dt ? ` · ${esc(dt)}` : ""}</div>
                <div class="dc-cal-title">${esc(e.title || "")}</div>
                <div class="dc-cal-hint">${esc(e.hint || "")}</div>
              </div>
            `;
          }).join("")}
        </div>
      </details>
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
    const activeTab = loadActiveTab(eid);
    hero.innerHTML = `
      ${renderHeader(data.deputy || {}, data.archetype || {}, data.rating || {},
                     data.profile || null, data.bio || null)}
      ${renderTabs(activeTab)}
      <div class="dc-tab-pane" data-tab="today" ${activeTab === "today" ? "" : "hidden"}>
        ${renderGoals(eid)}
        ${renderBriefing(data.briefing || {}, eid)}
        ${renderMissions(data.missions || [])}
        ${renderPrIdeas(data.pr_ideas || [])}
        ${renderActionsWidget(data.action_situations || [], eid)}
        ${renderPersonalTasks(data.personal_tasks || [])}
      </div>
      <div class="dc-tab-pane" data-tab="metrics" ${activeTab === "metrics" ? "" : "hidden"}>
        ${renderRatings(data.rating || {}, data.audit || null)}
        ${renderMeister(data.meister || {})}
        ${renderRecommendations(data.audit || {})}
        ${renderPlan(data.plan || {}, data.archetype || {})}
        ${renderScenarioWidget(data.scenario_meta || {}, data.scenario_initial || {})}
      </div>
      <div class="dc-tab-pane" data-tab="context" ${activeTab === "context" ? "" : "hidden"}>
        ${renderCityBrief(data.city_brief || {})}
        ${renderTrendsNow(data.trends_now || {})}
        ${renderCommentTargets(data.comment_targets || {})}
        ${renderDistrictToday(data.district_today || {})}
        ${renderCalendar(data.calendar || [])}
      </div>
      <div class="dc-tab-pane" data-tab="image" ${activeTab === "image" ? "" : "hidden"}>
        ${renderPersona(data.persona || {}, data.affinity || [], data.voice_portrait || {})}
        ${renderCitizensView(data.audit || {}, data.archetype || {})}
        ${renderTimingHeatmap(data.timing || {})}
      </div>
      <div class="dc-tab-pane" data-tab="ties" ${activeTab === "ties" ? "" : "hidden"}>
        ${renderCoalition(data.coalition || {})}
        ${renderExpectations(data.expectations || [])}
        ${renderMentions(data.mentions || {})}
        ${renderReplyTemplates(data.reply_categories || [], eid)}
      </div>
    `;
    hero.addEventListener("click", onCopyClick);
    hero.addEventListener("click", onReplyClick);
    hero.addEventListener("click", onIdeaClick);
    hero.addEventListener("click", onActionClick);
    hero.addEventListener("click", onBriefingVoiceClick);
    hero.addEventListener("click", onBriefingCardClick);
    hero.addEventListener("click", onGoalClick);
    hero.addEventListener("click", onCommentCopyClick);
    hero.addEventListener("click", onRunAuditClick);
    hero.addEventListener("click", onTabClick);
    hero.addEventListener("input", onScenarioInput);
    runScenario();
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

  function onIdeaClick(ev) {
    const btn = ev.target.closest(".dc-idea-go");
    if (!btn) return;
    const card = btn.closest(".dc-idea-card");
    const wizard = btn.getAttribute("data-wizard") || "content";
    // Берём deputyId / archetypeName с триггера действий в hero
    const contentBtn = document.getElementById("dc-create-content");
    const eventBtn = document.getElementById("dc-create-event");
    const deputyId = window.cmRole?.deputyId?.() || null;
    if (!deputyId) return;
    if (wizard === "event") {
      eventBtn?.click();
    } else {
      contentBtn?.click();
    }
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
