// =============================================================================
// Role picker — demo-режим без логинов. При первом заходе пользователь
// выбирает роль (мэр / зам мэра / депутат / кандидат), выбор пишется в
// localStorage. Каждая <section> с data-roles="..." скрывается, если
// текущая роль не в списке. Чип в topbar показывает текущую роль и
// открывает picker по клику.
// =============================================================================

(function () {
  "use strict";

  const STORAGE_KEY = "cm.role";
  const STORAGE_DEPUTY = "cm.deputyId";
  const STORAGE_PARTY  = "cm.candidate.party";
  const VALID_ROLES = ["mayor", "vice", "deputy", "candidate"];

  const ROLES = {
    mayor:     { emoji: "🏛", label: "Мэр",                 desc: "Полный обзор города, все инструменты управления." },
    vice:      { emoji: "⚙️", label: "Зам мэра",             desc: "Свой сектор: метрики, темы, депутаты." },
    deputy:    { emoji: "📋", label: "Депутат",             desc: "Округ, личный SMM-аудит, контент-план." },
    candidate: { emoji: "🇷🇺", label: "Кандидат в депутаты", desc: "Кампания, праймериз, конкуренты, штаб." },
  };

  // Партии для второго шага «кандидат». 5 партий + самовыдвиженец.
  const PARTIES = [
    { code: "er",          emoji: "🐻", short: "ЕР",      label: "Единая Россия",       desc: "Праймериз через er.ru, партийная вертикаль, акцент на стабильности." },
    { code: "new_people",  emoji: "✨", short: "НЛ",      label: "Новые люди",           desc: "Открытые онлайн-праймериз, ставка на новые лица и предпринимателей." },
    { code: "ldpr",        emoji: "🦅", short: "ЛДПР",    label: "ЛДПР",                 desc: "Кадровый отбор через партаппарат, эмоциональная риторика." },
    { code: "sr",          emoji: "⚖", short: "СР",      label: "Справедливая Россия",  desc: "Социальная справедливость, объединение со «За Правду»." },
    { code: "kprf",        emoji: "☭", short: "КПРФ",    label: "Коммунисты",           desc: "Региональная сеть, идеологическая преемственность." },
    { code: "independent", emoji: "🗽", short: "Самовыдв.", label: "Самовыдвиженец",     desc: "Без партии — нужно собрать подписи избирателей округа." },
  ];

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------

  function getRole() {
    try {
      const v = localStorage.getItem(STORAGE_KEY);
      return VALID_ROLES.includes(v) ? v : null;
    } catch (_) { return null; }
  }
  function setRole(role) {
    try { localStorage.setItem(STORAGE_KEY, role); } catch (_) {}
  }
  function getDeputyId() {
    try { return localStorage.getItem(STORAGE_DEPUTY) || null; } catch (_) { return null; }
  }
  function setDeputyId(id) {
    try {
      if (id) localStorage.setItem(STORAGE_DEPUTY, id);
      else    localStorage.removeItem(STORAGE_DEPUTY);
    } catch (_) {}
  }
  function getParty() {
    try {
      const v = localStorage.getItem(STORAGE_PARTY);
      return PARTIES.some((p) => p.code === v) ? v : null;
    } catch (_) { return null; }
  }
  function setParty(code) {
    try {
      if (code) localStorage.setItem(STORAGE_PARTY, code);
      else      localStorage.removeItem(STORAGE_PARTY);
    } catch (_) {}
  }

  let deputiesCache = null;
  async function loadDeputies() {
    if (deputiesCache) return deputiesCache;
    try {
      const r = await fetch("/api/copilot/deputies/list");
      if (!r.ok) return [];
      const data = await r.json();
      deputiesCache = data.deputies || [];
      return deputiesCache;
    } catch (_) { return []; }
  }

  // ---------------------------------------------------------------------------
  // Section visibility — data-roles на каждом элементе. Если атрибут не
  // задан — секция видна всем. "mayor,vice" — только этим двум ролям.
  // ---------------------------------------------------------------------------

  function applyRoleVisibility(role) {
    document.querySelectorAll("[data-roles]").forEach((el) => {
      const allowed = (el.getAttribute("data-roles") || "")
        .split(",").map((s) => s.trim()).filter(Boolean);
      if (allowed.length === 0) return;
      // hidden=true прячет элемент, не схлопывая layout — для inline ссылок
      // в topbar это важно.
      el.hidden = !allowed.includes(role);
    });
    document.body.dataset.role = role;
  }

  // ---------------------------------------------------------------------------
  // Topbar chip
  // ---------------------------------------------------------------------------

  async function renderChip(role) {
    const chip = document.getElementById("role-chip");
    if (!chip) return;
    const meta = ROLES[role] || ROLES.candidate;
    let label = meta.label;
    let emoji = meta.emoji;
    if (role === "deputy") {
      const eid = getDeputyId();
      if (eid) {
        const list = await loadDeputies();
        const d = list.find((x) => x.external_id === eid);
        if (d) {
          // Только фамилия в чипе — короче
          label = d.name.split(" ")[0];
        }
      }
    }
    if (role === "candidate") {
      const code = getParty();
      const p = PARTIES.find((pp) => pp.code === code);
      if (p) {
        emoji = p.emoji;
        label = "Кандидат · " + p.short;
      }
    }
    chip.innerHTML = `
      <span class="rc-chip-emoji">${emoji}</span>
      <span class="rc-chip-label">${label}</span>
      <span class="rc-chip-arrow">▾</span>
    `;
    chip.title = `Сменить роль (текущая: ${meta.label}${label !== meta.label ? " — " + label : ""})`;
  }

  // ---------------------------------------------------------------------------
  // Modal picker
  // ---------------------------------------------------------------------------

  function openPicker() {
    if (document.getElementById("rc-modal")) return;
    const wrap = document.createElement("div");
    wrap.id = "rc-modal";
    wrap.className = "rc-modal";
    wrap.innerHTML = `
      <div class="rc-backdrop" data-rc-close></div>
      <div class="rc-card" role="dialog" aria-label="Выбор роли">
        <div class="rc-eyebrow">Демо-режим · Городской Разум</div>
        <h2 class="rc-title">С какой ролью зайти?</h2>
        <p class="rc-sub">Без логина и пароля. Можно сменить в любой момент по чипу в шапке.</p>
        <div class="rc-grid">
          ${VALID_ROLES.map((r) => `
            <button type="button" class="rc-option" data-role="${r}">
              <span class="rc-option-emoji">${ROLES[r].emoji}</span>
              <span class="rc-option-label">${ROLES[r].label}</span>
              <span class="rc-option-desc">${ROLES[r].desc}</span>
            </button>
          `).join("")}
        </div>
      </div>
    `;
    document.body.appendChild(wrap);
    wrap.querySelectorAll(".rc-option").forEach((b) => {
      b.addEventListener("click", async () => {
        const role = b.getAttribute("data-role");
        if (!VALID_ROLES.includes(role)) return;
        if (role === "deputy") {
          await renderDeputyStep(wrap);
          return;
        }
        if (role === "candidate") {
          renderCandidateStep(wrap);
          return;
        }
        // Для не-депутата сбрасываем привязку к конкретному депутату
        setDeputyId(null);
        setParty(null);
        setRole(role);
        applyRoleVisibility(role);
        renderChip(role);
        closePicker();
        document.dispatchEvent(new CustomEvent("role:change", { detail: { role } }));
      });
    });
    wrap.querySelectorAll("[data-rc-close]").forEach((el) => {
      el.addEventListener("click", () => {
        // Закрыть можно только если роль уже выбрана.
        if (getRole()) closePicker();
      });
    });
    document.addEventListener("keydown", onEsc);
  }

  async function renderDeputyStep(wrap) {
    const card = wrap.querySelector(".rc-card");
    if (!card) return;
    card.innerHTML = `
      <div class="rc-eyebrow">Демо-режим · Городской Разум</div>
      <h2 class="rc-title">Кто из депутатов?</h2>
      <p class="rc-sub">
        Загружаю список…
      </p>
    `;
    const deputies = await loadDeputies();
    const withVK    = deputies.filter((d) => d.has_vk);
    const withoutVK = deputies.filter((d) => !d.has_vk);

    const dItem = (d, disabled) => `
      <button type="button" class="rc-deputy ${disabled ? "rc-deputy-soon" : ""}"
              data-eid="${d.external_id}" ${disabled ? "disabled" : ""}>
        <span class="rc-deputy-name">${d.name}</span>
        <span class="rc-deputy-meta">
          ${d.district || ""}${d.note ? ` · ${d.note}` : ""}
          ${d.has_vk ? `<span class="rc-deputy-badge">📊 VK подключён</span>` : `<span class="rc-deputy-badge muted">скоро</span>`}
        </span>
      </button>
    `;

    card.innerHTML = `
      <div class="rc-eyebrow">Демо-режим · Шаг 2 из 2</div>
      <h2 class="rc-title">Кто из депутатов?</h2>
      <p class="rc-sub">
        Выберите депутата — для него я подготовлю личный кабинет: аудит VK,
        архетип, рекомендации и контент-план.
      </p>
      <div class="rc-deputies">
        ${withVK.length ? `
          <div class="rc-deputies-group">
            <div class="rc-deputies-title">Активная демо-страница</div>
            ${withVK.map((d) => dItem(d, false)).join("")}
          </div>` : ""}
        ${withoutVK.length ? `
          <div class="rc-deputies-group">
            <div class="rc-deputies-title">Остальной состав</div>
            ${withoutVK.map((d) => dItem(d, true)).join("")}
          </div>` : ""}
      </div>
      <button type="button" class="rc-back" id="rc-back">← Назад к выбору роли</button>
    `;

    card.querySelectorAll(".rc-deputy:not([disabled])").forEach((b) => {
      b.addEventListener("click", () => {
        const eid = b.getAttribute("data-eid");
        if (!eid) return;
        setRole("deputy");
        setDeputyId(eid);
        applyRoleVisibility("deputy");
        renderChip("deputy");
        closePicker();
        document.dispatchEvent(new CustomEvent("role:change", {
          detail: { role: "deputy", deputyId: eid },
        }));
      });
    });
    card.querySelector("#rc-back")?.addEventListener("click", () => {
      closePicker();
      openPicker();
    });
  }

  function renderCandidateStep(wrap) {
    const card = wrap.querySelector(".rc-card");
    if (!card) return;
    card.innerHTML = `
      <div class="rc-eyebrow">Демо-режим · Шаг 2 из 2</div>
      <h2 class="rc-title">От какой партии?</h2>
      <p class="rc-sub">
        Выбор партии настраивает кабинет: тон коммуникации, праймериз,
        партийную вертикаль, конкурентный анализ соратников и оппонентов.
      </p>
      <div class="rc-parties">
        ${PARTIES.map((p) => `
          <button type="button" class="rc-party rc-party-${p.code}" data-code="${p.code}">
            <span class="rc-party-emoji">${p.emoji}</span>
            <span class="rc-party-text">
              <span class="rc-party-label">${p.label}</span>
              <span class="rc-party-desc">${p.desc}</span>
            </span>
          </button>
        `).join("")}
      </div>
      <button type="button" class="rc-back" id="rc-back">← Назад к выбору роли</button>
    `;

    card.querySelectorAll(".rc-party").forEach((b) => {
      b.addEventListener("click", () => {
        const code = b.getAttribute("data-code");
        if (!code) return;
        setRole("candidate");
        setParty(code);
        setDeputyId(null);
        applyRoleVisibility("candidate");
        renderChip("candidate");
        closePicker();
        document.dispatchEvent(new CustomEvent("role:change", {
          detail: { role: "candidate", party: code },
        }));
      });
    });
    card.querySelector("#rc-back")?.addEventListener("click", () => {
      closePicker();
      openPicker();
    });
  }

  function closePicker() {
    const m = document.getElementById("rc-modal");
    if (m) m.remove();
    document.removeEventListener("keydown", onEsc);
  }

  function onEsc(e) {
    if (e.key === "Escape" && getRole()) closePicker();
  }

  // ---------------------------------------------------------------------------
  // Public API + init
  // ---------------------------------------------------------------------------

  window.cmRole = {
    get:        getRole,
    deputyId:   getDeputyId,
    party:      getParty,
    set:        (r) => { if (VALID_ROLES.includes(r)) setRole(r); applyRoleVisibility(r); renderChip(r); },
    open:       openPicker,
    apply:      (r) => applyRoleVisibility(r || getRole() || "candidate"),
  };

  function init() {
    const role = getRole();
    if (role) {
      applyRoleVisibility(role);
      renderChip(role);
    } else {
      // По умолчанию — кандидат (наш main demo target), чтобы layout не дёргался;
      // модалка закрепит реальный выбор
      applyRoleVisibility("candidate");
      renderChip("candidate");
      openPicker();
    }
    const chip = document.getElementById("role-chip");
    if (chip) chip.addEventListener("click", openPicker);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
