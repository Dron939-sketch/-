// ============================================================
// Городской Разум — zero-dep премиум-дашборд
// City selection persisted in localStorage; falls back to URL
// slug (`/kolomna`) and finally to the backend-provided default.
// ============================================================

const REFRESH_MS = 10 * 60 * 1000;
const STORAGE_KEY = "cityMind.selectedCitySlug";

const VECTOR_META = [
  { key: "safety",  name: "Безопасность",   icon: "🛡️" },
  { key: "economy", name: "Экономика",       icon: "💰" },
  { key: "quality", name: "Качество жизни",  icon: "😊" },
  { key: "social",  name: "Соцкапитал",     icon: "🤝" },
];

async function fetchJson(url) {
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// -------------------------------------------------- City bootstrap

function pickInitialSlug(cities) {
  // 1. explicit URL path (/kolomna, /stupino, ...)
  const urlSlug = window.location.pathname.replace(/^\/+/, "").toLowerCase();
  if (urlSlug && cities.some((c) => c.slug === urlSlug)) return urlSlug;

  // 2. localStorage
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored && cities.some((c) => c.slug === stored)) return stored;

  // 3. pilot city
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
      <div class="trend ${trend.cls}">${trend.label}</div>
    `;
    grid.appendChild(tile);
  });
}

function renderLoops(loops) {
  const el = document.getElementById("loops-list");
  el.innerHTML = "";
  (loops || []).forEach((l) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="dot ${l.level || "info"}"></span> ${l.name}`;
    el.appendChild(li);
  });
}

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
  // Re-render the menu so the active marker moves with the selection.
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

  refreshTimer = setInterval(refresh, REFRESH_MS);
}

init();
