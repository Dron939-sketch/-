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
    { id: "legal",      icon: "⚖", label: "Юридика и штаб", sub: "67-ФЗ, документы, фонд, команда" },
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

  function renderHeader(p, election, stage, cityBrief) {
    const days = election.days_until;
    const daysLabel = days === 1 ? "1 день" : (days % 10 === 1 && days !== 11 ? `${days} день` : `${days} дней`);
    const dateStr = election.date
      ? new Date(election.date).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" })
      : "";
    const kpi = (cityBrief && cityBrief.kpi) || [];
    return `
      <div class="cc-hero" style="--cc-color: ${esc(p.color || '#5EA8FF')}">
        <div class="cc-hero-row">
          <div class="cc-hero-badge">
            <span class="cc-hero-emoji">${esc(p.emoji || "🇷🇺")}</span>
          </div>
          <div class="cc-hero-text">
            <div class="cc-hero-eyebrow">
              Кабинет кандидата · ${esc(p.short || "—")}
              ${renderDemoIndicator()}
            </div>
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

        <div class="cc-hero-actions">
          <button type="button" class="cc-action-btn cc-action-primary" id="cc-create-content">
            <span class="cc-action-emoji">🎬</span>
            <span class="cc-action-title">Контент</span>
          </button>
          <button type="button" class="cc-action-btn cc-action-secondary" id="cc-create-event">
            <span class="cc-action-emoji">📣</span>
            <span class="cc-action-title">Медиаповод</span>
          </button>
          <button type="button" class="cc-action-btn cc-action-audit" id="cc-run-audit">
            <span class="cc-action-emoji">🎭</span>
            <span class="cc-action-title">Аудит VK + стратегия</span>
          </button>
        </div>

        ${kpi.length ? `
          <div class="cc-city-kpi-strip">
            <div class="cc-kpi-eyebrow">🏙 Город сейчас (Мейстер 0-6)</div>
            <div class="cc-kpi-row">
              ${kpi.map((v) => `
                <div class="cc-kpi-tile" title="${esc(v.name)}">
                  <div class="cc-kpi-code">${esc(v.code)}</div>
                  <div class="cc-kpi-val">${v.value}<span class="cc-kpi-max">/${v.max}</span></div>
                  <div class="cc-kpi-name">${esc(v.name)}</div>
                </div>
              `).join("")}
            </div>
          </div>` : ""}
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

  const THREAT_LABEL = {
    5: { text: "Опасный",      color: "#FF9F4A" },
    4: { text: "Сильный",       color: "#FFD89B" },
    3: { text: "Средний",       color: "#5EA8FF" },
    2: { text: "Низкий",        color: "rgba(184, 212, 255, 0.6)" },
    1: { text: "Слабый",        color: "rgba(184, 212, 255, 0.4)" },
  };

  const STATUS_LABEL = {
    registered:     { text: "✓ зарегистрирован", color: "#B0F0C0" },
    primaries:      { text: "🗳 в праймериз",      color: "#FFD89B" },
    not_registered: { text: "⏳ не зарегистрирован", color: "rgba(184, 212, 255, 0.5)" },
  };

  function renderRivalsTab(data) {
    const r = data.rivals || {};
    const items = r.items || [];
    if (items.length === 0) {
      return `
        <div class="cc-block">
          <div class="cc-block-title">🥊 Конкуренты в гонке</div>
          <div class="cc-empty">Конкурентов пока не выявлено.</div>
        </div>`;
    }
    const agg = r.aggregate || {};
    return `
      <div class="cc-block">
        <div class="cc-block-title">
          🥊 Конкуренты в гонке — ${items.length}
          ${r.data_kind === "demo" ? `<span class="cc-fallback-tag">типажи</span>` : ""}
        </div>
        ${r.hint ? `<p class="cc-empty" style="margin: 0 0 8px;">${esc(r.hint)}</p>` : ""}

        <div class="cc-rivals-summary">
          <div class="cc-rival-stat">
            <div class="cc-rival-stat-num">${agg.count || 0}</div>
            <div class="cc-rival-stat-lbl">всего</div>
          </div>
          <div class="cc-rival-stat">
            <div class="cc-rival-stat-num">${agg.avg_reach || 0}</div>
            <div class="cc-rival-stat-lbl">ср. охват</div>
          </div>
          <div class="cc-rival-stat">
            <div class="cc-rival-stat-num">${agg.max_reach || 0}</div>
            <div class="cc-rival-stat-lbl">макс охват</div>
          </div>
          <div class="cc-rival-stat">
            <div class="cc-rival-stat-num">${agg.avg_freq || 0}</div>
            <div class="cc-rival-stat-lbl">ср. частота</div>
          </div>
        </div>
      </div>

      ${items.map((it) => {
        const threat = THREAT_LABEL[it.threat] || THREAT_LABEL[1];
        const status = STATUS_LABEL[it.status] || STATUS_LABEL.not_registered;
        return `
          <div class="cc-block cc-rival-card" style="border-left-color: ${esc(it.party_color)}">
            <div class="cc-rival-head">
              <div class="cc-rival-id">
                <div class="cc-rival-name">${esc(it.name)}</div>
                <div class="cc-rival-meta">
                  <span class="cc-rival-party" style="background: ${esc(it.party_color)}33; border-color: ${esc(it.party_color)}">
                    ${esc(it.party_short)}
                  </span>
                  <span class="cc-rival-exp">${it.experience_years} лет опыта</span>
                  <span class="cc-rival-status" style="color: ${esc(status.color)}">${esc(status.text)}</span>
                  ${it.is_same_party ? `<span class="cc-rival-same">в моей партии</span>` : ""}
                </div>
              </div>
              <div class="cc-rival-threat" style="background: ${esc(threat.color)}33; border-color: ${esc(threat.color)}; color: ${esc(threat.color)}">
                ⚔ ${esc(threat.text)}
              </div>
            </div>

            <div class="cc-rival-bars">
              <div class="cc-rival-bar-row">
                <div class="cc-rival-bar-lbl">Охват</div>
                <div class="cc-rival-bar"><div class="cc-rival-bar-fill" style="width:${it.reach}%; background: ${esc(it.party_color)}"></div></div>
                <div class="cc-rival-bar-val">${it.reach}/100</div>
              </div>
              <div class="cc-rival-bar-row">
                <div class="cc-rival-bar-lbl">Частота</div>
                <div class="cc-rival-bar"><div class="cc-rival-bar-fill" style="width:${it.frequency}%; background: ${esc(it.party_color)}"></div></div>
                <div class="cc-rival-bar-val">${it.frequency}/100</div>
              </div>
            </div>

            <div class="cc-rival-tone">🎙 Тон: <b>${esc(it.tone)}</b></div>

            <div class="cc-rival-twocol">
              <div class="cc-rival-col cc-rival-strong">
                <div class="cc-col-title">Сильные стороны</div>
                <div>${esc(it.strengths)}</div>
              </div>
              <div class="cc-rival-col cc-rival-weak">
                <div class="cc-col-title">Слабые стороны</div>
                <div>${esc(it.weaknesses)}</div>
              </div>
            </div>
          </div>
        `;
      }).join("")}
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
    const portals = data.bio_portals || {};
    return `
      ${renderBioPortalsBlock(portals)}
      <div class="cc-block">
        <div class="cc-block-title">📢 Контент-план агитации</div>
        <p class="cc-empty">Расширенный контент-план кандидата — на следующей итерации.
        В отличие от депутатского — 3-5 публикаций в день, А/Б-тест посланий,
        сегментация по аудитории, бюджет на полиграфию + реклама + ROI.</p>
      </div>
    `;
  }

  function renderBioPortalsBlock(portals) {
    if (!portals || !portals.total) return "";
    const tierLabel = (t) => t === "must" ? "обязательно"
                          : t === "recommended" ? "рекомендуется"
                          : "усиление";
    const tierColor = (t) => t === "must" ? "#FF9F4A"
                          : t === "recommended" ? "#5EA8FF"
                          : "rgba(184, 212, 255, 0.5)";
    const renderPortal = (p) => `
      <div class="cc-portal" style="border-left-color: ${esc(tierColor(p.tier))}">
        <div class="cc-portal-head">
          <span class="cc-portal-icon">${esc(p.icon)}</span>
          <a class="cc-portal-link" href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.title)} ↗</a>
          <span class="cc-portal-tier" style="background: ${esc(tierColor(p.tier))}33; color: ${esc(tierColor(p.tier))}">
            ${esc(tierLabel(p.tier))}
          </span>
          ${p.free ? `<span class="cc-portal-free">бесплатно</span>` : ""}
        </div>
        <div class="cc-portal-what">${esc(p.what || "")}</div>
        <div class="cc-portal-why">💡 ${esc(p.why || "")}</div>
        <details class="cc-portal-howto">
          <summary>Как разместиться</summary>
          <ol>${(p.how_to || []).map((s) => `<li>${esc(s)}</li>`).join("")}</ol>
        </details>
        <div class="cc-portal-audience">🎯 ${esc(p.audience || "")}</div>
      </div>
    `;
    return `
      <div class="cc-block">
        <div class="cc-block-title">🌐 Биография вне VK — что должно гуглиться</div>
        <p class="cc-empty">Когда избиратель гуглит твоё имя, важно занять первую страницу выдачи.
        Партнёрские био-порталы индексируются быстро и закрывают эту нишу.</p>

        ${(portals.must || []).length ? `
          <div class="cc-portal-group">
            <div class="cc-portal-group-title">⭐ Обязательно</div>
            ${(portals.must || []).map(renderPortal).join("")}
          </div>` : ""}

        ${(portals.recommended || []).length ? `
          <div class="cc-portal-group">
            <div class="cc-portal-group-title">👍 Рекомендуется</div>
            ${(portals.recommended || []).map(renderPortal).join("")}
          </div>` : ""}

        ${(portals.advanced || []).length ? `
          <div class="cc-portal-group">
            <div class="cc-portal-group-title">🚀 Усиление (на этапе агитации)</div>
            ${(portals.advanced || []).map(renderPortal).join("")}
          </div>` : ""}

        ${(portals.checklist || []).length ? `
          <div class="cc-portal-checklist">
            <div class="cc-block-title" style="font-size: 0.96rem">✓ Чек-лист</div>
            <ul class="cc-list">${(portals.checklist || []).map((c) => `<li>${esc(c)}</li>`).join("")}</ul>
          </div>` : ""}
      </div>
    `;
  }

  function renderLegalTab(data) {
    const legal = data.legal || {};
    const docs = legal.documents || [];
    const prohibitions = legal.prohibitions || [];
    const fund = legal.fund || {};
    const team = legal.team || {};
    const fmt = (n) => n.toLocaleString("ru-RU") + " ₽";
    return `
      <div class="cc-block">
        <div class="cc-block-title">📋 Документы для регистрации</div>
        <p class="cc-empty" style="margin: 0 0 8px;">67-ФЗ «Об основных гарантиях избирательных прав». Полный пакет — за 35-45 дней до подачи.</p>
        <ul class="cc-checklist">
          ${docs.map((d) => `
            <li class="cc-check ${d.required ? 'cc-check-high' : ''}">
              <span class="cc-check-icon">${d.required ? "★" : "○"}</span>
              <div>
                <div style="font-weight: 700">${esc(d.name)}</div>
                <div style="font-size: 0.78rem; color: rgba(184, 212, 255, 0.65)">${esc(d.where || "")}</div>
              </div>
            </li>
          `).join("")}
        </ul>
      </div>

      <div class="cc-block">
        <div class="cc-block-title">🚫 Запреты по 67-ФЗ</div>
        <div class="cc-info-grid">
          ${prohibitions.map((p) => `
            <div class="cc-info-card">
              <div class="cc-info-head">
                <span class="cc-info-emoji">${esc(p.icon)}</span>
                <span class="cc-info-title" style="font-size: 0.92rem">${esc(p.title)}</span>
              </div>
              <div class="cc-info-body">${esc(p.what)}</div>
            </div>
          `).join("")}
        </div>
      </div>

      <div class="cc-block">
        <div class="cc-block-title">
          💰 Избирательный фонд — ${esc(fund.label || "")}
          <span class="cc-fallback-tag">справочно</span>
        </div>
        <div class="cc-info-grid">
          <div class="cc-info-card">
            <div class="cc-info-emoji">📊</div>
            <div class="cc-info-title">Лимит фонда</div>
            <div class="cc-info-body" style="font-size: 1.1rem; font-weight: 700; color: var(--cc-color, #5EA8FF)">
              ${fund.max_fund ? fmt(fund.max_fund) : "—"}
            </div>
          </div>
          <div class="cc-info-card">
            <div class="cc-info-emoji">💼</div>
            <div class="cc-info-title">Из собственных средств</div>
            <div class="cc-info-body" style="font-size: 1.1rem; font-weight: 700">
              ${fund.max_self ? fmt(fund.max_self) : "—"}
            </div>
          </div>
        </div>
        ${fund.note ? `<div class="cc-empty" style="margin-top: 8px">${esc(fund.note)}</div>` : ""}
      </div>

      <div class="cc-block">
        <div class="cc-block-title">
          👥 Штаб — минимум для регистрации
          <span class="cc-team-cost">от ${fmt(team.min_payroll || 0)}/мес</span>
        </div>
        <div class="cc-info-grid">
          ${(team.essentials || []).map((r) => `
            <div class="cc-info-card cc-team-essential">
              <div class="cc-info-head">
                <span class="cc-info-emoji">${esc(r.icon)}</span>
                <span class="cc-info-tag">обязательно</span>
              </div>
              <div class="cc-info-title">${esc(r.title)}</div>
              <div class="cc-info-body">${esc(r.what)}</div>
              ${r.rate_per_month_rub > 0 ? `<div class="cc-team-rate">${fmt(r.rate_per_month_rub)}/мес</div>` : ""}
            </div>
          `).join("")}
        </div>
      </div>

      <div class="cc-block">
        <div class="cc-block-title">
          ✨ Расширенный штаб — для активной кампании
          <span class="cc-team-cost">+${fmt((team.full_payroll || 0) - (team.min_payroll || 0))}/мес</span>
        </div>
        <div class="cc-info-grid">
          ${(team.optionals || []).map((r) => `
            <div class="cc-info-card">
              <div class="cc-info-head">
                <span class="cc-info-emoji">${esc(r.icon)}</span>
                <span class="cc-info-tag">опционально</span>
              </div>
              <div class="cc-info-title">${esc(r.title)}</div>
              <div class="cc-info-body">${esc(r.what)}</div>
              ${r.rate_per_month_rub > 0 ? `<div class="cc-team-rate">${fmt(r.rate_per_month_rub)}/мес</div>` : ""}
            </div>
          `).join("")}
        </div>
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
  // Demo paywall: 10 минут бесплатно в день, потом подписка 2990₽/мес.
  // Счётчик в localStorage, обнуляется по локальной полуночи.
  // ---------------------------------------------------------------------------

  const DEMO_LIMIT_SECONDS = 600;             // 10 минут
  const SUBSCRIPTION_PRICE = "2 990 ₽/мес";

  function _today() { return new Date().toISOString().slice(0, 10); }
  function loadDemoUsage() {
    try {
      const raw = localStorage.getItem("cm.candidate.demo");
      if (!raw) return { date: _today(), seconds: 0 };
      const parsed = JSON.parse(raw);
      if (parsed.date !== _today()) return { date: _today(), seconds: 0 };
      return { date: parsed.date, seconds: Number(parsed.seconds) || 0 };
    } catch (_) { return { date: _today(), seconds: 0 }; }
  }
  function saveDemoUsage(usage) {
    try { localStorage.setItem("cm.candidate.demo", JSON.stringify(usage)); } catch (_) {}
  }

  let demoTimerHandle = null;

  function startDemoTimer() {
    stopDemoTimer();
    demoTimerHandle = setInterval(() => {
      // Если роль больше не «кандидат» — выключаемся
      if (window.cmRole?.get?.() !== "candidate") {
        stopDemoTimer();
        return;
      }
      const u = loadDemoUsage();
      // Дата уже сменилась — обнуляем
      if (u.date !== _today()) {
        u.date = _today(); u.seconds = 0;
      }
      u.seconds += 1;
      saveDemoUsage(u);

      const left = DEMO_LIMIT_SECONDS - u.seconds;
      updateDemoIndicator(u.seconds);

      if (left <= 0) {
        stopDemoTimer();
        showPaywall();
      }
    }, 1000);
  }
  function stopDemoTimer() {
    if (demoTimerHandle) {
      clearInterval(demoTimerHandle);
      demoTimerHandle = null;
    }
  }

  function updateDemoIndicator(seconds) {
    const el = document.getElementById("cc-demo-indicator");
    if (!el) return;
    const left = Math.max(0, DEMO_LIMIT_SECONDS - seconds);
    const m = Math.floor(left / 60);
    const s = left % 60;
    el.textContent = `⏱ ${m}:${s.toString().padStart(2, "0")} бесплатно`;
    el.classList.toggle("cc-demo-warn", left < 120);
  }

  function renderDemoIndicator() {
    const usage = loadDemoUsage();
    const left = Math.max(0, DEMO_LIMIT_SECONDS - usage.seconds);
    const m = Math.floor(left / 60);
    const s = left % 60;
    const cls = left < 120 ? "cc-demo-warn" : "";
    return `<div class="cc-demo-indicator ${cls}" id="cc-demo-indicator">⏱ ${m}:${s.toString().padStart(2, "0")} бесплатно</div>`;
  }

  function showPaywall() {
    if (document.getElementById("cc-paywall")) return;
    // Считаем сколько часов до полуночи
    const now = new Date();
    const tomorrow = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
    const diffMs = tomorrow - now;
    const hh = Math.floor(diffMs / 3_600_000);
    const mm = Math.floor((diffMs % 3_600_000) / 60_000);
    const wrap = document.createElement("div");
    wrap.id = "cc-paywall";
    wrap.className = "cc-paywall";
    wrap.innerHTML = `
      <div class="cc-paywall-card">
        <div class="cc-paywall-eyebrow">⏱ 10 минут демо закончились</div>
        <h2 class="cc-paywall-title">Подключите подписку — продолжайте без ограничений</h2>
        <p class="cc-paywall-sub">
          Полный доступ к кабинету кандидата: контент-визард в архетипе партии,
          сценарии медиаповодов, чек-листы 67-ФЗ, штаб, конкуренты, праймериз
          и весь функционал без ограничений.
        </p>
        <div class="cc-paywall-price">${esc(SUBSCRIPTION_PRICE)}</div>

        <div class="cc-paywall-form" id="cc-paywall-form">
          <input type="text" class="cc-audit-input" id="cc-paywall-contact"
                 placeholder="Телефон, email или Telegram — куда позвонить" autocomplete="off">
          <div class="cc-paywall-actions">
            <button type="button" class="cc-paywall-btn primary" id="cc-paywall-buy">
              🚀 Купить подписку
            </button>
            <button type="button" class="cc-paywall-btn ghost" id="cc-paywall-close-btn">
              Завтра вернусь
            </button>
          </div>
        </div>

        <div class="cc-paywall-success" id="cc-paywall-success" hidden>
          <div class="cc-paywall-ok-icon">✓</div>
          <div class="cc-paywall-ok-text">
            <b>Заявка отправлена.</b>
            <div>Я свяжусь с вами в ближайшее время.</div>
          </div>
        </div>

        <div class="cc-paywall-hint">
          Счётчик 10 мин обнулится через <b>${hh}ч ${mm}м</b> — в полночь по местному времени.
        </div>
      </div>
    `;
    document.body.appendChild(wrap);
    wrap.querySelector("#cc-paywall-close-btn")?.addEventListener("click", () => wrap.remove());
    wrap.querySelector("#cc-paywall-buy")?.addEventListener("click", submitPaymentIntent);
  }

  async function submitPaymentIntent() {
    const wrap = document.getElementById("cc-paywall");
    if (!wrap) return;
    const btn = document.getElementById("cc-paywall-buy");
    const contact = (document.getElementById("cc-paywall-contact")?.value || "").trim();
    const role = window.cmRole?.get?.() || null;
    const party = window.cmRole?.party?.() || null;
    if (btn) { btn.disabled = true; btn.textContent = "Отправляю…"; }
    try {
      const r = await fetch("/api/copilot/payment/intent", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role, party, contact }),
      });
      if (r.ok) {
        document.getElementById("cc-paywall-form")?.setAttribute("hidden", "");
        const ok = document.getElementById("cc-paywall-success");
        if (ok) ok.hidden = false;
      } else {
        if (btn) { btn.disabled = false; btn.textContent = "Попробовать ещё раз"; }
      }
    } catch (_) {
      if (btn) { btn.disabled = false; btn.textContent = "Сеть недоступна — попробовать ещё"; }
    }
  }

  function checkDemoLimitOnLoad() {
    const u = loadDemoUsage();
    if (u.seconds >= DEMO_LIMIT_SECONDS) {
      showPaywall();
      return false;  // сигнал что лимит закончился
    }
    return true;
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
      ${renderHeader(data.party || {}, data.election || {}, data.stage || {}, data.city_brief || {})}
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
      <div class="cc-tab-pane" data-tab="legal" ${activeTab === "legal" ? "" : "hidden"}>
        ${renderLegalTab(data)}
      </div>
    `;
    hero.addEventListener("click", onTabClick);
    document.getElementById("cc-run-audit")?.addEventListener("click", openAuditModal);
    // Запускаем демо-таймер. Если уже исчерпан — показываем paywall сразу.
    if (!checkDemoLimitOnLoad()) return;
    startDemoTimer();
  }

  // ---------------------------------------------------------------------------
  // VK Audit модалка — вход handle, результат с рекомендациями
  // ---------------------------------------------------------------------------

  function openAuditModal() {
    const old = document.getElementById("cc-audit-modal");
    if (old) old.remove();
    const wrap = document.createElement("div");
    wrap.id = "cc-audit-modal";
    wrap.className = "cc-audit-modal";
    wrap.innerHTML = `
      <div class="cc-audit-bg" data-close></div>
      <div class="cc-audit-card">
        <button type="button" class="cc-audit-close" data-close>✕</button>
        <div class="cc-audit-eyebrow">🎭 Аудит VK-страницы кандидата</div>
        <h3 class="cc-audit-title">Введите ссылку на свой VK</h3>
        <p class="cc-audit-sub">
          Я проанализирую посты, тон, частоту и архетип. Дам рекомендации
          по образу, бренду, целевому архетипу и победной стратегии.
        </p>
        <input type="text" class="cc-audit-input" id="cc-audit-input"
               placeholder="vk.com/ivanov или ivanov" autocomplete="off">
        <button type="button" class="cc-paywall-btn primary" id="cc-audit-go" style="margin-top: 12px">
          🚀 Запустить аудит
        </button>
        <div class="cc-audit-result" id="cc-audit-result"></div>
      </div>
    `;
    document.body.appendChild(wrap);
    wrap.querySelectorAll("[data-close]").forEach((el) =>
      el.addEventListener("click", () => wrap.remove()),
    );
    wrap.querySelector("#cc-audit-go")?.addEventListener("click", runAudit);
  }

  async function runAudit() {
    const input = document.getElementById("cc-audit-input");
    const result = document.getElementById("cc-audit-result");
    const handle = (input?.value || "").trim();
    if (!handle) {
      if (result) result.innerHTML = `<div class="cc-empty">Введите VK handle или ссылку.</div>`;
      return;
    }
    const party = window.cmRole?.party?.() || "independent";
    if (result) result.innerHTML = `<div class="cc-empty">⏳ Анализирую страницу… это занимает 5-10 секунд.</div>`;
    try {
      const r = await fetch("/api/copilot/candidate/audit", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ handle, party }),
      });
      if (!r.ok) {
        const detail = await r.json().catch(() => ({}));
        if (result) result.innerHTML = `<div class="cc-empty">Не получилось: ${esc(detail.detail || r.status)}</div>`;
        return;
      }
      const data = await r.json();
      if (result) result.innerHTML = renderAuditResult(data);
    } catch (e) {
      if (result) result.innerHTML = `<div class="cc-empty">Сеть недоступна.</div>`;
    }
  }

  function renderAuditResult(d) {
    const recs = d.recommendations || {};
    const a = d.audit || {};
    const m = a.metrics || {};
    const align = a.alignment_score;
    const profile = d.profile || {};
    const aff = d.affinity || [];
    const voice = d.voice_portrait || {};
    return `
      <div class="cc-audit-output">
        ${profile.photo ? `<img class="cc-audit-photo" src="${esc(profile.photo)}" alt="" />` : ""}
        <div class="cc-audit-stats">
          <div><b>${align != null ? Math.round(align) : "—"}%</b> соответствие архетипу</div>
          <div><b>${m.posts_per_week ?? 0}</b> постов в неделю</div>
          <div><b>${Math.round(m.avg_likes ?? 0)}</b> лайков в среднем</div>
          ${profile.followers ? `<div><b>${profile.followers}</b> подписчиков</div>` : ""}
        </div>

        ${aff.length ? `
          <div class="cc-audit-section">
            <div class="cc-block-title">🎭 Top архетипы (близость постов)</div>
            <div class="cc-audit-aff">
              ${aff.slice(0, 3).map((x, i) => `
                <div class="cc-audit-aff-row">
                  <span class="cc-audit-aff-rank">${i + 1}</span>
                  <span class="cc-audit-aff-name">${esc(x.name)}</span>
                  <span class="cc-audit-aff-pct">${x.affinity}%</span>
                </div>
              `).join("")}
            </div>
          </div>` : ""}

        ${voice.state === "ok" ? `
          <div class="cc-audit-section">
            <div class="cc-block-title">🎙 Голос-портрет</div>
            <div class="cc-empty">${esc(voice.headline || "")}</div>
          </div>` : ""}

        <div class="cc-audit-section">
          <div class="cc-block-title">👁 Образ глазами избирателя</div>
          <ul class="cc-list">${(recs.image || []).map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
        </div>

        <div class="cc-audit-section">
          <div class="cc-block-title">🏷 Бренд — что укрепить</div>
          <ul class="cc-list">${(recs.brand || []).map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
        </div>

        <div class="cc-audit-section">
          <div class="cc-block-title">🎭 Целевой архетип под партию</div>
          <ul class="cc-list">${(recs.archetype || []).map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
        </div>

        <div class="cc-audit-section cc-audit-strategy">
          <div class="cc-block-title">🏆 Победная стратегия — 30 дней</div>
          <div class="cc-info-grid">
            ${(recs.strategy || []).map((s) => `
              <div class="cc-info-card">
                <div class="cc-info-emoji">${esc(s.icon)}</div>
                <div class="cc-info-title">${esc(s.what)}</div>
                <div class="cc-info-body">${esc(s.why)}</div>
              </div>
            `).join("")}
          </div>
        </div>
      </div>
    `;
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
        stopDemoTimer();
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
