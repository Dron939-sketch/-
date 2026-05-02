// =============================================================================
// Кабинет кандидата в депутаты — wow-первый экран при role=candidate.
// Hero с countdown, 5 табов: Кампания / Конкуренты / Электорат / Партия / СМИ.
// =============================================================================

(function () {
  "use strict";

  const HERO_ID = "candidate-cabinet-hero";

  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));

  const TABS = [
    { id: "campaign",   icon: "🎯", label: "Кампания",    sub: "этап, чек-лист, миссии" },
    { id: "rivals",     icon: "🥊", label: "Конкуренты",   sub: "досье, сравнение" },
    { id: "voters",     icon: "🗳", label: "Электорат",   sub: "сегменты, обещания" },
    { id: "party",      icon: "🏛", label: "Партия",      sub: "тон, актив, программа" },
    { id: "media",      icon: "📢", label: "СМИ",         sub: "контент-план, бюджет" },
  ];

  function loadActiveTab(party) {
    try {
      const v = localStorage.getItem(`cm.candidate.tab.${party || "default"}`);
      return TABS.some((t) => t.id === v) ? v : "campaign";
    } catch (_) { return "campaign"; }
  }
  function saveActiveTab(party, tabId) {
    try { localStorage.setItem(`cm.candidate.tab.${party || "default"}`, tabId); } catch (_) {}
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  function renderHeader(p, election, stage) {
    const days = election.days_until;
    const daysLabel = days === 1 ? "1 день" : (days % 10 === 1 && days !== 11 ? `${days} день` : `${days} дней`);
    const dateStr = election.date
      ? new Date(election.date).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" })
      : "";
    return `
      <div class="cc-hero" style="--cc-color: ${esc(p.color || '#5EA8FF')}">
        <div class="cc-hero-badge">
          <span class="cc-hero-emoji">${esc(p.emoji || "🇷🇺")}</span>
        </div>
        <div class="cc-hero-text">
          <div class="cc-hero-eyebrow">Кабинет кандидата · ${esc(p.short || "—")}</div>
          <h1 class="cc-hero-greet">${esc(p.name || "Кандидат")}</h1>
          <div class="cc-hero-meta">
            ${esc(stage.icon || "▶")} Этап «${esc(stage.name)}» · ${esc(stage.what || "")}
          </div>
        </div>
        <div class="cc-countdown">
          <div class="cc-countdown-num">${days}</div>
          <div class="cc-countdown-label">${days < 0 ? "выборы прошли" : `${daysLabel} до выборов`}</div>
          <div class="cc-countdown-date">${esc(dateStr)}</div>
        </div>
      </div>
    `;
  }

  function renderTabs(activeId) {
    return `
      <nav class="cc-tabs" role="tablist">
        ${TABS.map((t) => `
          <button type="button" class="cc-tab ${t.id === activeId ? 'is-active' : ''}"
                  role="tab" data-tab="${esc(t.id)}">
            <span class="cc-tab-icon">${esc(t.icon)}</span>
            <span class="cc-tab-text">
              <span class="cc-tab-label">${esc(t.label)}</span>
              <span class="cc-tab-sub">${esc(t.sub)}</span>
            </span>
          </button>
        `).join("")}
      </nav>
    `;
  }

  function renderCampaignTab(data) {
    const checklist = data.checklist || [];
    const missions = data.missions || [];
    return `
      <div class="cc-block">
        <div class="cc-block-title">📋 Чек-лист этапа «${esc(data.stage.name)}»</div>
        <ul class="cc-checklist">
          ${checklist.map((c) => `
            <li class="cc-check cc-check-${esc(c.priority || 'medium')}">
              <span class="cc-check-icon">${c.priority === "high" ? "★" : "○"}</span>
              <span>${esc(c.text)}</span>
            </li>
          `).join("")}
        </ul>
      </div>
      <div class="cc-block">
        <div class="cc-block-title">🎯 Миссии на ближайшее</div>
        <div class="cc-missions">
          ${missions.map((m, i) => `
            <div class="cc-mission">
              <div class="cc-mission-num">${i + 1}</div>
              <div class="cc-mission-body">
                <div class="cc-mission-title">${esc(m.title || "")}</div>
                <div class="cc-mission-why">${esc(m.why || "")}</div>
                ${m.hint ? `<div class="cc-mission-hint">${esc(m.hint)}</div>` : ""}
              </div>
            </div>
          `).join("")}
        </div>
      </div>
    `;
  }

  function renderRivalsTab(data) {
    return `
      <div class="cc-block">
        <div class="cc-block-title">🥊 Конкуренты в гонке</div>
        <p class="cc-empty">Досье на соперников появится в Этапе 5.
        Здесь будут карточки: имя, партия, опыт, ресурсы, тон, история постов,
        сильные/слабые стороны и прогноз кого обходишь.</p>
        <div class="cc-info-grid">
          ${(data.party.rivals || []).map((r) => `
            <div class="cc-info-card">
              <div class="cc-info-emoji">⚔</div>
              <div class="cc-info-title">${esc(r)}</div>
              <div class="cc-info-body">Стандартный конкурент по партийной логике.</div>
            </div>
          `).join("")}
        </div>
      </div>
    `;
  }

  function renderVotersTab(data) {
    const promises = data.party.voter_promises || [];
    const segments = [
      { name: "Пенсионеры",     emoji: "👴",  share: "~25%", concerns: "Лекарства, индексация, ЖКХ, безопасность" },
      { name: "Семьи с детьми",  emoji: "👨‍👩‍👧", share: "~20%", concerns: "Школы, сады, площадки, материнский капитал" },
      { name: "Молодёжь 18-35",  emoji: "🎓",  share: "~25%", concerns: "Работа, ипотека, ИТ, городская среда" },
      { name: "Бюджетники",      emoji: "🩺",  share: "~15%", concerns: "Зарплаты, нагрузка, доступность жилья" },
      { name: "Бизнес / СПД",    emoji: "💼",  share: "~10%", concerns: "Налоги, проверки, доступ к господдержке" },
    ];
    return `
      <div class="cc-block">
        <div class="cc-block-title">🗳 Сегментация округа</div>
        <div class="cc-info-grid">
          ${segments.map((s) => `
            <div class="cc-info-card">
              <div class="cc-info-head">
                <span class="cc-info-emoji">${s.emoji}</span>
                <span class="cc-info-tag">${s.share}</span>
              </div>
              <div class="cc-info-title">${s.name}</div>
              <div class="cc-info-body">${s.concerns}</div>
            </div>
          `).join("")}
        </div>
      </div>
      <div class="cc-block">
        <div class="cc-block-title">📜 Партийные обещания (${esc(data.party.short)})</div>
        <ul class="cc-list">
          ${promises.map((pr) => `<li>${esc(pr)}</li>`).join("")}
        </ul>
      </div>
    `;
  }

  function renderPartyTab(data) {
    const tone = data.party.tone || {};
    return `
      <div class="cc-block cc-party-tone">
        <div class="cc-block-title">🎙 Тон коммуникации «${esc(data.party.short)}»</div>
        <div class="cc-tone-headline">${esc(tone.headline || "")}</div>
        <div class="cc-tone-voice">${esc(tone.voice || "")}</div>
        <div class="cc-tone-twocol">
          <div class="cc-tone-col cc-tone-do">
            <div class="cc-col-title">Делать</div>
            <ul class="cc-list">${(tone.do || []).map((s) => `<li>${esc(s)}</li>`).join("")}</ul>
          </div>
          <div class="cc-tone-col cc-tone-dont">
            <div class="cc-col-title">Не делать</div>
            <ul class="cc-list">${(tone.dont || []).map((s) => `<li>${esc(s)}</li>`).join("")}</ul>
          </div>
        </div>
      </div>
      <div class="cc-block">
        <div class="cc-block-title">📊 Ключевые метрики партийной активности</div>
        <ul class="cc-list">${(data.party.key_metrics || []).map((m) => `<li>${esc(m)}</li>`).join("")}</ul>
      </div>
      <div class="cc-block">
        <div class="cc-block-title">🤝 Союзники</div>
        <ul class="cc-list">${(data.party.allies || []).map((a) => `<li>${esc(a)}</li>`).join("")}</ul>
      </div>
      ${renderSelectionBlock(data.selection || {})}
    `;
  }

  function renderMediaTab(data) {
    return `
      <div class="cc-block">
        <div class="cc-block-title">📢 Контент-план агитации</div>
        <p class="cc-empty">Расширенный контент-план кандидата появится в Этапе 4.
        В отличие от депутатского — 3-5 публикаций в день, А/Б-тест посланий,
        сегментация по аудитории, бюджет на полиграфию + реклама + ROI.</p>
      </div>
      <div class="cc-block">
        <div class="cc-block-title">💰 Избирательный фонд</div>
        <p class="cc-empty">Калькулятор бюджета и контроль за расходованием —
        Этап 4. Лимиты и нарушения по 67-ФЗ.</p>
      </div>
    `;
  }

  function renderSelectionBlock(s) {
    if (!s || !s.kind) return "";
    const isDemo = s.data_kind === "demo";
    const pct = s.progress_pct || 0;
    return `
      <div class="cc-block cc-selection cc-sel-${esc(s.kind)}">
        <div class="cc-block-title">
          ${esc(s.icon || "🗳")} ${esc(s.title || "Отбор")}
          ${isDemo ? `<span class="cc-fallback-tag">демо</span>` : ""}
        </div>
        <p class="cc-empty" style="margin: 0 0 10px;">${esc(s.subtitle || "")}</p>

        <div class="cc-sel-progress">
          <div class="cc-sel-bar">
            <div class="cc-sel-bar-fill" style="width:${pct}%"></div>
          </div>
          <div class="cc-sel-meta">
            <span class="cc-sel-num">${s.current}/${s.target}</span>
            <span class="cc-sel-unit">${esc(s.unit || "")}</span>
            ${s.position ? `<span class="cc-sel-pos">${esc(s.position)}</span>` : ""}
            ${s.deadline_days != null ? `<span class="cc-sel-deadline">⏱ ${s.deadline_days} дн до конца</span>` : ""}
          </div>
        </div>

        ${(s.boost_actions || []).length ? `
          <div class="cc-sel-actions">
            <div class="cc-col-title">Что поднимет показатель</div>
            <ol class="cc-list">
              ${(s.boost_actions || []).map((a) => `<li>${esc(a)}</li>`).join("")}
            </ol>
          </div>` : ""}

        ${(s.links || []).length ? `
          <div class="cc-sel-links">
            ${(s.links || []).map(([label, url]) => `
              <a class="cc-sel-link" href="${esc(url)}" target="_blank" rel="noopener">${esc(label)} ↗</a>
            `).join("")}
          </div>` : ""}

        ${(s.platform) ? `<div class="cc-sel-platform">Платформа: <b>${esc(s.platform)}</b></div>` : ""}
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // Main
  // ---------------------------------------------------------------------------

  async function fetchCabinet(party) {
    try {
      const r = await fetch(`/api/copilot/candidate/cabinet?party=${encodeURIComponent(party || "independent")}`);
      if (!r.ok) return null;
      return await r.json();
    } catch (_) { return null; }
  }

  async function renderCabinet() {
    const hero = document.getElementById(HERO_ID);
    if (!hero) return;
    const role = window.cmRole?.get?.() || null;
    if (role !== "candidate") {
      hero.innerHTML = "";
      return;
    }
    const party = window.cmRole?.party?.() || "independent";
    hero.innerHTML = `<div class="cc-loading">Готовлю кабинет кандидата…</div>`;
    const data = await fetchCabinet(party);
    if (!data) {
      hero.innerHTML = `<div class="cc-empty">Не удалось собрать кабинет. Попробуйте обновить страницу.</div>`;
      return;
    }
    const activeTab = loadActiveTab(party);
    hero.innerHTML = `
      ${renderHeader(data.party || {}, data.election || {}, data.stage || {})}
      ${renderTabs(activeTab)}
      <div class="cc-tab-pane" data-tab="campaign" ${activeTab === "campaign" ? "" : "hidden"}>
        ${renderCampaignTab(data)}
      </div>
      <div class="cc-tab-pane" data-tab="rivals" ${activeTab === "rivals" ? "" : "hidden"}>
        ${renderRivalsTab(data)}
      </div>
      <div class="cc-tab-pane" data-tab="voters" ${activeTab === "voters" ? "" : "hidden"}>
        ${renderVotersTab(data)}
      </div>
      <div class="cc-tab-pane" data-tab="party" ${activeTab === "party" ? "" : "hidden"}>
        ${renderPartyTab(data)}
      </div>
      <div class="cc-tab-pane" data-tab="media" ${activeTab === "media" ? "" : "hidden"}>
        ${renderMediaTab(data)}
      </div>
    `;
    hero.addEventListener("click", onTabClick);
  }

  function onTabClick(ev) {
    const btn = ev.target.closest(".cc-tab");
    if (!btn) return;
    const id = btn.getAttribute("data-tab");
    if (!id) return;
    const party = window.cmRole?.party?.() || null;
    saveActiveTab(party, id);
    document.querySelectorAll(".cc-tab").forEach((b) => {
      b.classList.toggle("is-active", b.getAttribute("data-tab") === id);
    });
    document.querySelectorAll(".cc-tab-pane").forEach((p) => {
      p.hidden = p.getAttribute("data-tab") !== id;
    });
    document.querySelector(".cc-tabs")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function init() {
    renderCabinet();
    document.addEventListener("role:change", () => {
      const hero = document.getElementById(HERO_ID);
      if (!hero) return;
      if (window.cmRole?.get?.() !== "candidate") {
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
