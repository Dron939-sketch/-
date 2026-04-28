// ============================================================
// Admin dashboard — отдельная страница /admin.html
// Показывает usage analytics + drill-down по пользователям.
// Требует role=admin. При отсутствии прав показывает login-экран.
// ============================================================

let currentUser = null;
let currentRange = 7;

async function fetchJson(url) {
  const res = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

function fmtTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("ru-RU", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  });
}
function fmtDateShort(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
}
function escapeHtml(s) { return (s || "").replace(/</g, "&lt;"); }

// -------------------------------------------------- Auth

async function fetchAuthState() {
  try {
    const data = await fetchJson("/api/auth/me");
    return data.authenticated ? data : null;
  } catch (e) { return null; }
}

function renderAuthChip() {
  const chip = document.getElementById("auth-chip");
  const label = document.getElementById("auth-label");
  if (!chip) return;
  if (currentUser) {
    const name = currentUser.full_name || currentUser.email || "user";
    label.textContent = name.length > 20 ? name.slice(0, 18) + "…" : name;
    chip.classList.add("logged-in");
  } else {
    label.textContent = "Войти";
    chip.classList.remove("logged-in");
  }
}

async function doLogin(email, password) {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `${res.status} ${res.statusText}`);
  currentUser = data;
  return data;
}

async function doLogout() {
  try { await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" }); }
  catch (e) { /* ignore */ }
  currentUser = null;
  location.reload();
}

function openAuthModal() {
  const m = document.getElementById("auth-modal");
  m.classList.add("open");
  m.setAttribute("aria-hidden", "false");
}
function closeAuthModal() {
  const m = document.getElementById("auth-modal");
  m.classList.remove("open");
  m.setAttribute("aria-hidden", "true");
}

// -------------------------------------------------- Render

function renderSummary(s) {
  const el = document.getElementById("admin-summary");
  if (!el) return;
  el.innerHTML = "";
  const chips = [
    `Всего событий: <strong>${(s.total_events || 0).toLocaleString("ru-RU")}</strong>`,
    `Авторизованных: <strong>${s.authenticated_events || 0}</strong>`,
    `Анонимных: <strong>${s.anonymous_events || 0}</strong>`,
    `Уникальных пользователей: <strong>${s.distinct_users || 0}</strong>`,
    `Сессий: <strong>${s.distinct_sessions || 0}</strong>`,
  ];
  if (s.avg_response_ms != null) chips.push(`Сред. отклик: <strong>${s.avg_response_ms} мс</strong>`);
  if (s.errors_5xx) chips.push(`<span style="color: var(--danger);">5xx: ${s.errors_5xx}</span>`);
  if (s.errors_4xx) chips.push(`<span style="color: var(--warn);">4xx: ${s.errors_4xx}</span>`);
  chips.forEach((html) => {
    const c = document.createElement("span");
    c.className = "chip";
    c.innerHTML = html;
    el.appendChild(c);
  });
  const meta = document.getElementById("admin-summary-meta");
  if (meta) meta.textContent = `окно ${s.window_days} дн.`;
}

function renderDaily(rows) {
  const chart = document.getElementById("admin-daily");
  if (!chart) return;
  chart.innerHTML = "";
  if (!rows || !rows.length) {
    chart.innerHTML = '<div class="stats-empty">Нет данных.</div>';
    return;
  }
  const maxHits = Math.max(1, ...rows.map((r) => r.hits));
  rows.forEach((r) => {
    const bar = document.createElement("div");
    bar.className = "bar";
    bar.style.height = `${Math.max(2, (r.hits / maxHits) * 120)}px`;
    bar.title = `${fmtDateShort(r.day)} — ${r.hits} hits · ${r.users} польз. · ${r.sessions} сес.`;
    const lbl = document.createElement("span");
    lbl.className = "dlabel";
    lbl.textContent = fmtDateShort(r.day);
    bar.appendChild(lbl);
    chart.appendChild(bar);
  });
}

function renderUsers(users) {
  const list = document.getElementById("admin-users");
  if (!list) return;
  list.innerHTML = "";
  if (!users.length) {
    list.innerHTML = '<li class="stats-empty">Авторизованных событий ещё не было.</li>';
    return;
  }
  users.forEach((u) => {
    const li = document.createElement("li");
    const display = escapeHtml(u.full_name || u.email || `user#${u.user_id}`);
    const last = u.last_seen ? fmtDateShort(u.last_seen) : "";
    li.innerHTML = `
      <div>
        <div class="name">${display}</div>
        <div class="sub">${u.role || "viewer"} · последний визит: ${last}</div>
      </div>
      <div class="events">${u.events}</div>
    `;
    li.addEventListener("click", () => openUserDetail(u));
    list.appendChild(li);
  });
}

function renderEndpoints(endpoints) {
  const list = document.getElementById("admin-endpoints");
  if (!list) return;
  list.innerHTML = "";
  if (!endpoints.length) {
    list.innerHTML = '<li class="stats-empty">Обращений к API ещё не было.</li>';
    return;
  }
  endpoints.forEach((e) => {
    const li = document.createElement("li");
    const errSeg = [];
    if (e.errors_5xx) errSeg.push(`<span style="color: var(--danger);">5xx: ${e.errors_5xx}</span>`);
    if (e.errors_4xx) errSeg.push(`<span style="color: var(--warn);">4xx: ${e.errors_4xx}</span>`);
    li.innerHTML = `
      <div>
        <div class="path">${escapeHtml(e.path)}</div>
        <div class="sub">${e.distinct_users || 0} польз. · сред. ${e.avg_ms || 0} мс${errSeg.length ? " · " + errSeg.join(" · ") : ""}</div>
      </div>
      <div class="hits">${e.hits}</div>
    `;
    list.appendChild(li);
  });
}

async function openUserDetail(user) {
  const section = document.getElementById("admin-user-detail");
  const emailEl = document.getElementById("admin-user-email");
  const timeline = document.getElementById("admin-user-timeline");
  if (!section) return;
  section.hidden = false;
  emailEl.textContent = user.email || `#${user.user_id}`;
  timeline.innerHTML = '<li class="stats-empty">Загружаю…</li>';
  try {
    const data = await fetchJson(`/api/admin/stats/user/${user.user_id}?limit=100`);
    const events = data.events || [];
    if (!events.length) {
      timeline.innerHTML = '<li class="stats-empty">Нет активности в этом окне.</li>';
      return;
    }
    timeline.innerHTML = "";
    events.forEach((e) => {
      const li = document.createElement("li");
      const statusCls = e.status >= 500 ? "err" : e.status >= 400 ? "err" : e.status >= 300 ? "redir" : "ok";
      li.innerHTML = `
        <span class="ts">${fmtTime(e.created_at)}</span>
        <span class="method">${e.method}</span>
        <span class="path">${escapeHtml(e.path)}</span>
        <span class="status ${statusCls}">${e.status}${e.response_time_ms != null ? ` · ${e.response_time_ms}мс` : ""}</span>
      `;
      timeline.appendChild(li);
    });
    section.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    timeline.innerHTML = `<li class="stats-empty">Ошибка: ${err.message}</li>`;
  }
}

// -------------------------------------------------- Data fetch

async function loadAll() {
  try {
    const [sum, users, endpoints, daily] = await Promise.all([
      fetchJson(`/api/admin/stats/summary?days=${currentRange}`),
      fetchJson(`/api/admin/stats/users?days=${currentRange}&limit=20`),
      fetchJson(`/api/admin/stats/endpoints?days=${currentRange}&limit=20`),
      fetchJson(`/api/admin/stats/daily?days=${currentRange}`),
    ]);
    renderSummary(sum);
    renderUsers(users.users || []);
    renderEndpoints(endpoints.endpoints || []);
    renderDaily(daily.days || []);
    const upd = document.getElementById("updated-at");
    if (upd) upd.textContent = "Обновлено: " + new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  } catch (e) {
    console.error("admin load failed", e);
    if (e.message && e.message.startsWith("401")) {
      showAuthGate();
    } else if (e.message && e.message.startsWith("403")) {
      showAuthGate("У вас нет роли admin. Попросите администратора.");
    }
  }
}

function showAuthGate(msg) {
  document.getElementById("admin-unauth").hidden = false;
  document.getElementById("admin-content").hidden = true;
  if (msg) {
    document.querySelector("#admin-unauth p").textContent = msg;
  }
}

function showContent() {
  document.getElementById("admin-unauth").hidden = true;
  document.getElementById("admin-content").hidden = false;
}

// -------------------------------------------------- Init

async function init() {
  currentUser = await fetchAuthState();
  renderAuthChip();

  if (!currentUser || currentUser.role !== "admin") {
    showAuthGate();
  } else {
    showContent();
    await loadAll();
  }

  // Wire controls.
  const rangeSel = document.getElementById("range-select");
  const refreshBtn = document.getElementById("admin-refresh");
  if (rangeSel) rangeSel.addEventListener("change", () => {
    currentRange = Number(rangeSel.value) || 7;
    loadAll();
  });
  if (refreshBtn) refreshBtn.addEventListener("click", loadAll);

  // Auth chip — logout when logged in, login modal otherwise.
  const chip = document.getElementById("auth-chip");
  if (chip) chip.addEventListener("click", () => {
    if (currentUser) {
      if (confirm(`Выйти из аккаунта ${currentUser.email}?`)) doLogout();
    } else {
      openAuthModal();
    }
  });

  // Login button on unauth gate.
  const gateBtn = document.getElementById("admin-login-btn");
  if (gateBtn) gateBtn.addEventListener("click", openAuthModal);

  // Login form.
  const loginForm = document.getElementById("login-form");
  const loginError = document.getElementById("login-error");
  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      loginError.hidden = true;
      try {
        const user = await doLogin(
          document.getElementById("login-email").value,
          document.getElementById("login-password").value,
        );
        closeAuthModal();
        if (user.role === "admin") {
          showContent();
          renderAuthChip();
          await loadAll();
        } else {
          showAuthGate(`Вы вошли как ${user.role}. Нужна роль admin.`);
          renderAuthChip();
        }
      } catch (err) {
        loginError.textContent = err.message || "Ошибка входа";
        loginError.hidden = false;
      }
    });
  }

  // Modal dismiss handlers.
  document.querySelectorAll(".modal [data-dismiss]").forEach((el) => {
    el.addEventListener("click", closeAuthModal);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeAuthModal();
  });

  // Per-user drill-down close.
  const closeUserBtn = document.getElementById("admin-close-user");
  if (closeUserBtn) closeUserBtn.addEventListener("click", () => {
    document.getElementById("admin-user-detail").hidden = true;
  });

  // VK groups discovery form.
  const vkForm = document.getElementById("vk-discover-form");
  if (vkForm) vkForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = document.getElementById("vk-discover-q").value.trim();
    if (!q) return;
    await runVkDiscover(q);
  });
}

async function runVkDiscover(query) {
  const out = document.getElementById("vk-discover-results");
  out.innerHTML = '<div class="muted small" style="padding:12px;">Ищу…</div>';
  try {
    const data = await fetchJson(`/api/admin/vk_discover?q=${encodeURIComponent(query)}&limit=50`);
    renderVkGroups(data);
  } catch (err) {
    out.innerHTML = `<div class="auth-error">Ошибка: ${escapeHtml(err.message)}</div>`;
  }
}

function renderVkGroups(data) {
  const out = document.getElementById("vk-discover-results");
  out.innerHTML = "";
  const groups = data.groups || [];
  if (!groups.length) {
    out.innerHTML = '<div class="muted small" style="padding:12px;">Группы не найдены. Попробуйте другой запрос.</div>';
    return;
  }
  groups.forEach((g) => {
    const row = document.createElement("div");
    row.className = "vk-group-row" + (g.is_closed ? " closed" : "");
    const members = (g.members_count || 0).toLocaleString("ru-RU");
    const desc = g.description ? escapeHtml(g.description) : "";
    row.innerHTML = `
      <div>
        <span class="vk-name"><a href="${escapeHtml(g.url)}" target="_blank" rel="noopener">${escapeHtml(g.name)}</a></span>
        <span class="vk-handle">@${escapeHtml(g.screen_name)} · ${g.type}${g.is_closed ? ' · 🔒' : ''}</span>
        ${desc ? `<div class="vk-desc">${desc}</div>` : ''}
      </div>
      <div class="vk-members">${members}</div>
      <button type="button" class="vk-copy-btn" data-line="${escapeHtml(g.config_line || '')}">Копировать</button>
    `;
    out.appendChild(row);
  });
  out.querySelectorAll(".vk-copy-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const line = btn.getAttribute("data-line") || "";
      try {
        await navigator.clipboard.writeText(line);
        const prev = btn.textContent;
        btn.classList.add("copied");
        btn.textContent = "✓ Скопировано";
        setTimeout(() => { btn.classList.remove("copied"); btn.textContent = prev; }, 1600);
      } catch (e) {
        btn.textContent = "Ошибка";
      }
    });
  });
}

init();
