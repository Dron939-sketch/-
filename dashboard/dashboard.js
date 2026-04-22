// ============================================================
// Городской Разум — zero-dep премиум-дашборд
// City selection persisted in localStorage; falls back to URL
// slug (`/kolomna`) and finally to the backend-provided default.
// ============================================================

const REFRESH_MS = 10 * 60 * 1000;
const STORAGE_KEY = "cityMind.selectedCitySlug";

// Dashboard keys (safety/economy/quality/social) → DB keys (sb/tf/ub/chv)
// for the sparkline history endpoint.
const VECTOR_META = [
  { key: "safety",  dbKey: "sb",  name: "Безопасность",   icon: "🛡️" },
  { key: "economy", dbKey: "tf",  name: "Экономика",       icon: "💰" },
  { key: "quality", dbKey: "ub",  name: "Качество жизни",  icon: "😊" },
  { key: "social",  dbKey: "chv", name: "Соцкапитал",     icon: "🤝" },
];

const SPARKLINE_W = 160;
const SPARKLINE_H = 30;

async function fetchJson(url) {
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// -------------------------------------------------- City bootstrap

function pickInitialSlug(cities) {
  const urlSlug = window.location.pathname.replace(/^\/+/, "").toLowerCase();
  if (urlSlug && cities.some((c) => c.slug === urlSlug)) return urlSlug;
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored && cities.some((c) => c.slug === stored)) return stored;
  const pilot = cities.find((c) => c.is_pilot);
  if (pilot) return pilot.slug;
  return cities[0]?.slug;
}

function renderCityMenu(cities, currentSlug, onPick) {
  const menu = document.getElementById("city-menu");
  menu.innerHTML = "";
  cities.forEach((c) => {
    const li = document.createElement("li");
    li.setAttribute("role", "option");
    if (c.slug === currentSlug) li.classList.add("active");
    li.innerHTML = `<span class="city-emoji">${c.emoji || "🏙️"}</span>` +
      `<span>${c.name}</span>` +
      (c.is_pilot ? `<span class="pilot-chip">Пилот</span>` : "");
    li.addEventListener("click", () => onPick(c));
    menu.appendChild(li);
  });
}

function applyCity(city) {
  document.getElementById("city-name").textContent = city.name;
  document.getElementById("city-emoji").textContent = city.emoji || "🏙️";
  localStorage.setItem(STORAGE_KEY, city.slug);
  document.getElementById("footer-tag").textContent =
    `${city.region || ""} · алгоритм Мейстера`.trim();
  if (city.accent_color) {
    document.documentElement.style.setProperty("--gold", city.accent_color);
  }
}

// -------------------------------------------------- Rendering

function fmtPct(v) { return v == null ? "—" : `${Math.round(v * 100)}%`; }
function fmtTrend(v) {
  if (v == null) return { label: "—", cls: "flat" };
  const pct = Math.round(v * 100);
  if (pct > 0) return { label: `▲ +${pct}% за неделю`, cls: "up" };
  if (pct < 0) return { label: `▼ ${pct}% за неделю`,   cls: "down" };
  return { label: "без изменений", cls: "flat" };
}

function renderGreeting(city) {
  const now = new Date();
  const weekday = now.toLocaleDateString("ru-RU", { weekday: "long" });
  const full = now.toLocaleDateString("ru-RU", {
    day: "numeric", month: "long", year: "numeric",
  });
  document.getElementById("today-date").textContent = `${weekday}, ${full}`;
  const hour = now.getHours();
  const greeting = hour < 5 ? "Доброй ночи"
    : hour < 12 ? "Доброе утро"
    : hour < 18 ? "Добрый день"
    : "Добрый вечер";
  document.getElementById("greeting-title").textContent = greeting;
  document.getElementById("greeting-sub").textContent =
    `Сводка по городу ${city.name} на сегодня`;
  document.title = `Городской Разум — ${city.name}`;
}

function renderWeather(w) {
  if (!w) return;
  document.getElementById("weather-emoji").textContent = w.condition_emoji || "☁️";
  document.getElementById("weather-temp").textContent =
    w.temperature != null ? `${Math.round(w.temperature)}°C` : "—";
  document.getElementById("weather-feels").textContent =
    w.feels_like != null ? `${Math.round(w.feels_like)}°C` : "—";
  document.getElementById("weather-humidity").textContent =
    w.humidity != null ? `${w.humidity}%` : "—";
  document.getElementById("weather-wind").textContent =
    w.wind_speed != null ? `${w.wind_speed} м/с` : "—";
  document.getElementById("weather-cond").textContent = w.condition || "";
}

function renderVectors(metrics, trends) {
  const grid = document.getElementById("vectors-grid");
  grid.innerHTML = "";
  VECTOR_META.forEach((v) => {
    const val = metrics?.[v.key];
    const trend = fmtTrend(trends?.[v.key]);
    const scaled = val != null ? (val * 6).toFixed(1) : "—";
    const tile = document.createElement("div");
    tile.className = "vector-tile";
    tile.innerHTML = `
      <div class="icon">${v.icon}</div>
      <div class="score">${scaled}<small> / 6</small></div>
      <div class="name">${v.name}</div>
      <svg class="sparkline empty" data-key="${v.dbKey}" viewBox="0 0 ${SPARKLINE_W} ${SPARKLINE_H}" preserveAspectRatio="none" aria-hidden="true"></svg>
      <div class="trend ${trend.cls}">${trend.label}</div>
    `;
    grid.appendChild(tile);
  });
}

function renderSparklines(history) {
  // history: {sb:[[ts, v], ...], tf:[...], ub:[...], chv:[...]}
  VECTOR_META.forEach((v) => {
    const svg = document.querySelector(`.sparkline[data-key="${v.dbKey}"]`);
    if (!svg) return;
    const series = (history && history[v.dbKey]) || [];
    if (series.length < 2) {
      svg.classList.add("empty");
      svg.innerHTML = "";
      return;
    }
    const values = series.map((p) => p[1]);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const pad = 3;
    const points = series.map((p, i) => {
      const x = (i / (series.length - 1)) * SPARKLINE_W;
      const y = SPARKLINE_H - pad - ((p[1] - min) / range) * (SPARKLINE_H - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    const fillPoints = `0,${SPARKLINE_H} ${points.join(" ")} ${SPARKLINE_W},${SPARKLINE_H}`;
    svg.classList.remove("empty");
    svg.innerHTML = `
      <defs>
        <linearGradient id="sparklineGradient-${v.dbKey}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--gold)" stop-opacity="0.45"/>
          <stop offset="100%" stop-color="var(--gold)" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <polygon class="sparkline-fill" points="${fillPoints}" fill="url(#sparklineGradient-${v.dbKey})"/>
      <polyline points="${points.join(" ")}"/>
    `;
  });
}

// -------------------------------------------------- Loops & modal

let currentLoops = [];

function renderLoops(loops) {
  currentLoops = Array.isArray(loops) ? loops : [];
  const el = document.getElementById("loops-list");
  el.innerHTML = "";
  currentLoops.forEach((l, idx) => {
    const li = document.createElement("li");
    li.setAttribute("role", "button");
    li.setAttribute("tabindex", "0");
    li.dataset.index = String(idx);
    li.innerHTML =
      `<span class="dot ${l.level || "info"}"></span>` +
      `<span>${l.name || "Петля"}</span>` +
      `<span class="caret">→</span>`;
    li.addEventListener("click", () => openLoopModal(idx));
    li.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openLoopModal(idx); }
    });
    el.appendChild(li);
  });
}

function openLoopModal(idx) {
  const loop = currentLoops[idx];
  if (!loop) return;
  document.getElementById("loop-modal-title").textContent = loop.name || "Петля";
  document.getElementById("loop-modal-description").textContent = loop.description || "";

  const bp = loop.break_points || {};
  const details = document.getElementById("loop-modal-details");
  details.innerHTML = "";
  const rows = [];
  if (loop.strength != null) rows.push(["Сила петли", `${Math.round(loop.strength * 100)}%`]);
  if (bp.strategic_priority) rows.push(["Приоритет", bp.strategic_priority]);
  if (bp.break_timeline) rows.push(["Горизонт разрыва", bp.break_timeline]);
  if (bp.effort_required) rows.push(["Требуемые усилия", bp.effort_required]);
  if (bp.advice) rows.push(["Совет", bp.advice]);
  if (bp.length != null) rows.push(["Длина цикла", String(bp.length)]);
  if (bp.impact != null) rows.push(["Влияние", `${Math.round(bp.impact * 100)}%`]);

  rows.forEach(([label, value]) => {
    const row = document.createElement("div");
    row.className = "detail-row";
    row.innerHTML = `<span class="label">${label}</span><span class="value">${value}</span>`;
    details.appendChild(row);
  });

  const resourcesBox = document.getElementById("loop-modal-resources");
  const resourcesList = document.getElementById("loop-modal-resources-list");
  resourcesList.innerHTML = "";
  if (Array.isArray(bp.recommended_resources) && bp.recommended_resources.length) {
    bp.recommended_resources.forEach((r) => {
      const li = document.createElement("li");
      li.textContent = r;
      resourcesList.appendChild(li);
    });
    resourcesBox.hidden = false;
  } else {
    resourcesBox.hidden = true;
  }

  const modal = document.getElementById("loop-modal");
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
}

function closeLoopModal() {
  const modal = document.getElementById("loop-modal");
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
}

// -------------------------------------------------- Misc

function renderTrustHappy(data) {
  const trustPct = data.trust?.index != null ? data.trust.index : null;
  const happyPct = data.happiness?.overall != null ? data.happiness.overall : null;
  if (trustPct != null) {
    document.getElementById("trust-fill").style.width = `${Math.round(trustPct * 100)}%`;
    document.getElementById("trust-percent").textContent = fmtPct(trustPct);
  }
  if (happyPct != null) {
    document.getElementById("happiness-fill").style.width = `${Math.round(happyPct * 100)}%`;
    document.getElementById("happiness-percent").textContent = fmtPct(happyPct);
  }

  const complaints = document.getElementById("top-complaints");
  complaints.innerHTML = "";
  (data.trust?.top_complaints || []).slice(0, 5).forEach((t) => {
    const li = document.createElement("li");
    li.textContent = t;
    complaints.appendChild(li);
  });
  const praises = document.getElementById("top-praises");
  praises.innerHTML = "";
  (data.trust?.top_praises || []).slice(0, 5).forEach((t) => {
    const li = document.createElement("li");
    li.textContent = t;
    praises.appendChild(li);
  });
}

function renderForecast(data) {
  document.getElementById("forecast-summary").textContent =
    data.forecast_3m?.summary || "Прогноз появится после сбора данных.";
  document.getElementById("forecast-rec").textContent =
    data.forecast_3m?.recommendation || "";
}

function renderAgenda(agenda) {
  document.getElementById("agenda-headline").textContent = agenda.headline || "—";
  document.getElementById("agenda-description").textContent = agenda.description || "";
  const list = document.getElementById("agenda-actions");
  list.innerHTML = "";
  (agenda.actions || []).forEach((a) => {
    const li = document.createElement("li");
    li.textContent = a;
    list.appendChild(li);
  });
}

function setUpdated() {
  document.getElementById("updated-at").textContent =
    "Обновлено: " + new Date().toLocaleTimeString("ru-RU", {
      hour: "2-digit", minute: "2-digit",
    });
}

// -------------------------------------------------- Refresh loop

let currentCity = null;
let refreshTimer = null;

async function refresh() {
  if (!currentCity) return;
  const slug = currentCity.slug;
  try {
    const metrics = await fetchJson(`/api/city/${slug}/all_metrics`);
    renderWeather(metrics.weather);
    renderVectors(metrics.city_metrics, metrics.trends);
    renderLoops(metrics.loops);
    renderTrustHappy(metrics);
    renderForecast(metrics);
  } catch (e) {
    console.warn("metrics unavailable", e);
  }
  try {
    const history = await fetchJson(`/api/city/${slug}/history?days=30`);
    renderSparklines(history.series || {});
  } catch (e) {
    console.warn("history unavailable", e);
  }
  try {
    const agenda = await fetchJson(`/api/city/${slug}/agenda`);
    renderAgenda(agenda);
  } catch (e) {
    console.warn("agenda unavailable", e);
  }
  setUpdated();
}

async function switchCity(city) {
  currentCity = city;
  applyCity(city);
  renderGreeting(city);
  const cities = window.__CITIES__ || [];
  renderCityMenu(cities, city.slug, switchCity);
  document.getElementById("city-menu").hidden = true;
  document.getElementById("city-button").setAttribute("aria-expanded", "false");
  await refresh();
}

async function init() {
  let cities = [];
  try {
    cities = await fetchJson("/api/cities");
  } catch (e) {
    console.error("cities unavailable", e);
    return;
  }
  window.__CITIES__ = cities;

  const slug = pickInitialSlug(cities);
  const city = cities.find((c) => c.slug === slug) || cities[0];
  await switchCity(city);

  // Toggle the dropdown on button click.
  const btn = document.getElementById("city-button");
  const menu = document.getElementById("city-menu");
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const open = !menu.hidden;
    menu.hidden = open;
    btn.setAttribute("aria-expanded", String(!open));
  });
  document.addEventListener("click", () => {
    menu.hidden = true;
    btn.setAttribute("aria-expanded", "false");
  });

  // Modal dismissal — backdrop click, close button, Esc.
  document.querySelectorAll("#loop-modal [data-dismiss]").forEach((el) => {
    el.addEventListener("click", closeLoopModal);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeLoopModal();
  });

  refreshTimer = setInterval(refresh, REFRESH_MS);
}

init();
