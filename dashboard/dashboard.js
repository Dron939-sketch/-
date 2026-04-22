// Minimal dashboard fetcher. Polls /api/city/<name>/all_metrics and /agenda
// once on load and every 10 minutes. No framework dependencies — keeps the
// bundle size zero and matches the spec requirement for hourly refresh.

const CITY = document.getElementById("city-name").textContent.trim();
const REFRESH_MS = 10 * 60 * 1000;

async function fetchJson(url) {
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el && value !== undefined && value !== null) el.textContent = value;
}

function formatPct(v) {
  return (v * 100).toFixed(0) + "%";
}

function compositeColor(value) {
  if (value === null || value === undefined) return "";
  if (value >= 0.66) return "good";
  if (value >= 0.4) return "warn";
  return "bad";
}

function renderMetrics(data) {
  const w = data.weather || {};
  if (w.temperature != null) {
    setText("weather-temp", `${Math.round(w.temperature)}°C`);
    setText("weather-cond", `${w.condition || ""} ${w.condition_emoji || ""}`.trim());
  }

  const vectors = data.city_metrics || {};
  document.querySelectorAll(".vectors .value").forEach((el) => {
    const key = el.getAttribute("data-key");
    if (vectors[key] != null) el.textContent = formatPct(vectors[key]);
  });

  const trust = data.trust || {};
  if (trust.index != null) setText("trust-index", trust.index.toFixed(2));
  const ol = document.getElementById("top-complaints");
  ol.innerHTML = "";
  (trust.top_complaints || []).slice(0, 5).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    ol.appendChild(li);
  });

  if (data.happiness && data.happiness.overall != null) {
    setText("happiness-index", data.happiness.overall.toFixed(2));
  }

  const grid = document.getElementById("composite-grid");
  grid.innerHTML = "";
  const composite = data.composite_indices || {};
  const labels = {
    quality_of_life: "Качество жизни",
    economic_development: "Экономика",
    social_cohesion: "Соцкапитал",
    environmental: "Экология",
    infrastructure: "Инфраструктура",
    mayoral_performance: "Работа администрации",
    city_attractiveness: "Привлекательность",
    future_outlook: "Перспективы",
  };
  Object.entries(labels).forEach(([key, label]) => {
    const v = composite[key];
    const div = document.createElement("div");
    div.className = `composite-item ${compositeColor(v)}`;
    div.innerHTML = `<div class="label">${label}</div><div class="v">${
      v == null ? "—" : formatPct(v)
    }</div>`;
    grid.appendChild(div);
  });
}

function renderAgenda(agenda) {
  setText("agenda-headline", agenda.headline);
  setText("agenda-description", agenda.description);
  const list = document.getElementById("agenda-actions");
  list.innerHTML = "";
  (agenda.actions || []).forEach((a) => {
    const li = document.createElement("li");
    li.textContent = a;
    list.appendChild(li);
  });
}

async function refresh() {
  try {
    const metrics = await fetchJson(`/api/city/${encodeURIComponent(CITY)}/all_metrics`);
    renderMetrics(metrics);
  } catch (e) {
    console.warn("metrics unavailable", e);
  }
  try {
    const agenda = await fetchJson(`/api/city/${encodeURIComponent(CITY)}/agenda`);
    renderAgenda(agenda);
  } catch (e) {
    console.warn("agenda unavailable", e);
  }
  document.getElementById("updated-at").textContent =
    "Обновлено: " + new Date().toLocaleString("ru-RU");
}

refresh();
setInterval(refresh, REFRESH_MS);
