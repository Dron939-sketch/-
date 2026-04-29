// =============================================================================
// Role picker — demo-режим без логинов. При первом заходе пользователь
// выбирает роль (мэр / зам мэра / депутат / гость), выбор пишется в
// localStorage. Каждая <section> с data-roles="..." скрывается, если
// текущая роль не в списке. Чип в topbar показывает текущую роль и
// открывает picker по клику.
// =============================================================================

(function () {
  "use strict";

  const STORAGE_KEY = "cm.role";
  const VALID_ROLES = ["mayor", "vice", "deputy", "guest"];

  const ROLES = {
    mayor:  { emoji: "🏛", label: "Мэр",       desc: "Полный обзор города, все инструменты управления." },
    vice:   { emoji: "⚙️", label: "Зам мэра",   desc: "Свой сектор: метрики, темы, депутаты." },
    deputy: { emoji: "📋", label: "Депутат",    desc: "Округ, личный SMM-аудит, контент-план." },
    guest:  { emoji: "👤", label: "Гость",     desc: "Город как житель: погода, пульс, Джарвис." },
  };

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

  function renderChip(role) {
    const chip = document.getElementById("role-chip");
    if (!chip) return;
    const meta = ROLES[role] || ROLES.guest;
    chip.innerHTML = `
      <span class="rc-chip-emoji">${meta.emoji}</span>
      <span class="rc-chip-label">${meta.label}</span>
      <span class="rc-chip-arrow">▾</span>
    `;
    chip.title = `Сменить роль (текущая: ${meta.label})`;
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
      b.addEventListener("click", () => {
        const role = b.getAttribute("data-role");
        if (!VALID_ROLES.includes(role)) return;
        setRole(role);
        applyRoleVisibility(role);
        renderChip(role);
        closePicker();
        // Триггерим событие, чтобы виджеты могли пере-инициализироваться
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
    get:    getRole,
    set:    (r) => { if (VALID_ROLES.includes(r)) setRole(r); applyRoleVisibility(r); renderChip(r); },
    open:   openPicker,
    apply:  (r) => applyRoleVisibility(r || getRole() || "guest"),
  };

  function init() {
    const role = getRole();
    if (role) {
      applyRoleVisibility(role);
      renderChip(role);
    } else {
      // По умолчанию — гость, чтобы layout не дёргался; модалка закрепит выбор
      applyRoleVisibility("guest");
      renderChip("guest");
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
