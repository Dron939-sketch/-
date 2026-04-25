/* Home screen — minimal, focused.
 *
 * Loads:
 *   GET /api/cities                     — for the city selector menu
 *   GET /api/auth/me                    — to toggle Депутаты/Админка links
 *   GET /api/city/{name}/voice          — pulse + crisis + AI phrase
 *   GET /api/city/{name}/tasks          — top 3 tasks for "today" card
 *   GET /api/city/{name}/all_metrics    — для chips (репутация, счастье, погода)
 *
 * Design: zero framework, single file. The full dashboard.js lives on
 * /full-dashboard.html and is NOT loaded here — keeps the home screen
 * fast and uncluttered.
 */

(() => {
  const $ = (id) => document.getElementById(id);

  const state = {
    cityName: localStorage.getItem("cm.city") || "Коломна",
    user: null,
  };

  // ---------- helpers ----------

  function escapeHtml(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  async function fetchJson(url) {
    try {
      const r = await fetch(url, { credentials: "include" });
      if (!r.ok) return null;
      return await r.json();
    } catch {
      return null;
    }
  }

  function pulseLevel(value) {
    if (value == null) return "elevated";
    if (value >= 70) return "good";
    if (value >= 50) return "elevated";
    if (value >= 30) return "warn";
    return "critical";
  }

  function pulseLabel(value) {
    if (value == null) return "Загрузка…";
    if (value >= 70) return "Хорошее состояние";
    if (value >= 50) return "Стабильно";
    if (value >= 30) return "Пониженный фон";
    return "Требует внимания";
  }

  function greetingByHour() {
    const h = new Date().getHours();
    if (h < 5) return "Доброй ночи";
    if (h < 12) return "Доброе утро";
    if (h < 18) return "Добрый день";
    return "Добрый вечер";
  }

  function todayLabel() {
    const fmt = new Intl.DateTimeFormat("ru-RU", {
      weekday: "long", day: "numeric", month: "long",
    });
    return fmt.format(new Date());
  }

  // ---------- hero ----------

  async function loadHero() {
    const data = await fetchJson(`/api/city/${encodeURIComponent(state.cityName)}/voice`);
    const pulse = data?.pulse;
    const phrase = data?.phrase || "Сводка пока не сформирована.";
    const crisis = data?.crisis_status;

    const level = (() => {
      if (crisis === "attention") return "critical";
      if (crisis === "watch") return "warn";
      return pulseLevel(pulse);
    })();

    const hero = $("hero");
    hero.dataset.level = level === "warn" ? "elevated" : level;

    $("hero-pulse-value").textContent = pulse != null ? Math.round(pulse) : "—";
    $("hero-pulse-label").textContent = pulseLabel(pulse);
    $("hero-voice").textContent = phrase;

    // CTA: if attention/watch → primary action goes to crisis details.
    const ctaRow = $("hero-cta-row");
    const primary = $("hero-cta-primary");
    const secondary = $("hero-cta-secondary");
    if (crisis === "attention" || crisis === "watch") {
      primary.textContent = crisis === "attention"
        ? "🚨 Открыть кризис"
        : "👁 Проверить сигналы";
      primary.href = "/full-dashboard.html#crisis-strip";
      secondary.textContent = "📝 Что сделать сегодня";
      secondary.href = "/full-dashboard.html#task-manager";
      secondary.hidden = false;
      ctaRow.hidden = false;
    } else {
      primary.textContent = "📝 Повестка дня";
      primary.href = "/full-dashboard.html#agenda";
      secondary.hidden = true;
      ctaRow.hidden = false;
    }
  }

  // ---------- ops chips ----------

  async function loadOpsChips() {
    const snap = await fetchJson(`/api/city/${encodeURIComponent(state.cityName)}/all_metrics`);
    if (!snap) return;

    // crisis chip — uses /crisis directly (status = ok|watch|attention)
    const crisis = await fetchJson(`/api/city/${encodeURIComponent(state.cityName)}/crisis`);
    const chipCrisis = $("chip-crisis");
    const status = crisis?.status || "ok";
    chipCrisis.dataset.level = status;
    $("chip-crisis-value").textContent = {
      ok: "Спокойно", watch: "Под наблюдением", attention: "Требует внимания",
    }[status] || "—";
    const alerts = crisis?.alerts || [];
    $("chip-crisis-sub").textContent = alerts.length
      ? `${alerts.length} активных сигналов`
      : "Нет активных сигналов";

    // reputation chip — positive/negative mentions ratio
    const trust = snap.trust || {};
    const pos = trust.positive_mentions || 0;
    const neg = trust.negative_mentions || 0;
    const total = pos + neg;
    const ratio = total ? Math.round((pos / total) * 100) : 50;
    $("chip-rep-value").textContent = `${ratio}% позитива`;
    $("chip-rep-sub").textContent = total
      ? `${pos} ↑ · ${neg} ↓`
      : "Нет упоминаний за 24ч";

    // happiness chip
    const happy = snap.happiness || {};
    const happyVal = happy.overall != null ? Math.round(happy.overall * 100) : null;
    const trustVal = trust.index != null ? Math.round(trust.index * 100) : null;
    $("chip-happy-value").textContent = happyVal != null ? `${happyVal}%` : "—";
    $("chip-happy-sub").textContent = trustVal != null ? `Доверие ${trustVal}%` : "—";

    // weather chip
    const wx = snap.weather || {};
    if (wx.condition_emoji) $("chip-wx-emoji").textContent = wx.condition_emoji;
    $("chip-wx-value").textContent = wx.temperature != null ? `${Math.round(wx.temperature)}°` : "—";
    $("chip-wx-sub").textContent = wx.condition || "—";
  }

  // ---------- today: top 3 tasks ----------

  async function loadToday() {
    const data = await fetchJson(`/api/city/${encodeURIComponent(state.cityName)}/tasks`);
    const list = $("today-list");
    list.innerHTML = "";
    const tasks = (data?.tasks || []).slice(0, 3);
    if (!tasks.length) {
      const li = document.createElement("li");
      li.className = "today-empty";
      li.textContent = "Срочных задач нет — сегодня можно заняться стратегией.";
      list.appendChild(li);
      return;
    }
    for (const t of tasks) {
      const li = document.createElement("li");
      const owner = t.suggested_owner ? ` · ${escapeHtml(t.suggested_owner)}` : "";
      const horizon = t.horizon ? ` · ${escapeHtml(t.horizon)}` : "";
      li.innerHTML = `
        <div class="today-task-body">
          <span class="today-task-title">${escapeHtml(t.title)}</span>
          <span class="today-task-priority" data-p="${escapeHtml(t.priority || 'medium')}">${escapeHtml(t.priority || 'medium')}</span>
          <div class="today-task-meta">${escapeHtml(t.source || "")}${owner}${horizon}</div>
        </div>
      `;
      list.appendChild(li);
    }
  }

  // ---------- city selector ----------

  async function loadCities() {
    const cities = await fetchJson("/api/cities");
    const menu = $("city-menu");
    if (!cities || !Array.isArray(cities)) return;
    menu.innerHTML = "";
    for (const c of cities) {
      const li = document.createElement("li");
      li.setAttribute("role", "option");
      li.innerHTML = `<span class="city-emoji">${escapeHtml(c.emoji || "🏙️")}</span> ${escapeHtml(c.name)}`;
      li.addEventListener("click", () => switchCity(c.name, c.emoji));
      menu.appendChild(li);
    }
    // Reflect current city
    const current = cities.find((c) => c.name === state.cityName) || cities[0];
    if (current) {
      $("city-name").textContent = current.name;
      $("city-emoji").textContent = current.emoji || "🏙️";
      state.cityName = current.name;
      localStorage.setItem("cm.city", current.name);
    }
  }

  function switchCity(name, emoji) {
    state.cityName = name;
    localStorage.setItem("cm.city", name);
    $("city-name").textContent = name;
    if (emoji) $("city-emoji").textContent = emoji;
    $("city-menu").hidden = true;
    $("city-button").setAttribute("aria-expanded", "false");
    refreshAll();
  }

  // ---------- auth ----------

  async function loadAuth() {
    state.user = await fetchJson("/api/auth/me");
    const role = state.user?.role;
    const isAuthed = !!state.user;
    $("auth-label").textContent = isAuthed ? state.user.email : "Войти";

    const isStaff = role === "admin" || role === "editor";
    const deputiesLink = $("deputies-link");
    if (deputiesLink) deputiesLink.hidden = !isStaff;
    const tileDeputies = $("tile-deputies");
    if (tileDeputies) tileDeputies.hidden = !isStaff;

    const adminLink = $("admin-link");
    if (adminLink) adminLink.hidden = role !== "admin";
  }

  // ---------- login modal ----------

  function openLogin() {
    $("auth-modal").setAttribute("aria-hidden", "false");
    $("auth-modal").style.display = "flex";
  }
  function closeLogin() {
    $("auth-modal").setAttribute("aria-hidden", "true");
    $("auth-modal").style.display = "none";
  }
  async function doLogin(ev) {
    ev.preventDefault();
    const err = $("login-error");
    err.hidden = true;
    try {
      const r = await fetch("/api/auth/login", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: $("login-email").value,
          password: $("login-password").value,
        }),
      });
      if (!r.ok) {
        err.textContent = (await r.json()).detail || "Ошибка входа";
        err.hidden = false;
        return;
      }
      closeLogin();
      await loadAuth();
    } catch (e) {
      err.textContent = e.message;
      err.hidden = false;
    }
  }

  // ---------- init ----------

  async function refreshAll() {
    $("hero-greeting").textContent = greetingByHour() + (state.user?.full_name ? `, ${state.user.full_name.split(" ")[0]}` : "");
    $("hero-date").textContent = todayLabel();
    await Promise.all([loadHero(), loadOpsChips(), loadToday()]);
  }

  document.addEventListener("DOMContentLoaded", async () => {
    // City selector toggle
    $("city-button").addEventListener("click", () => {
      const menu = $("city-menu");
      const btn = $("city-button");
      const open = menu.hidden;
      menu.hidden = !open;
      btn.setAttribute("aria-expanded", String(open));
    });
    document.addEventListener("click", (e) => {
      if (!e.target.closest(".city-selector")) {
        $("city-menu").hidden = true;
        $("city-button").setAttribute("aria-expanded", "false");
      }
    });

    // Auth
    $("auth-chip").addEventListener("click", openLogin);
    $("login-form").addEventListener("submit", doLogin);
    document.querySelectorAll('[data-dismiss]').forEach((el) =>
      el.addEventListener("click", closeLogin)
    );

    await loadCities();
    await loadAuth();
    await refreshAll();

    // Refresh hero every 60s — keep the voice fresh.
    setInterval(loadHero, 60000);
  });
})();
