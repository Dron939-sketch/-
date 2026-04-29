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
