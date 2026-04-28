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

const INTERVENTION_OPTIONS = [
  { code: "patrol", name: "Патрулирование ДНД", vector: "safety", cost: 2000000 },
  { code: "cctv", name: "Видеонаблюдение", vector: "safety", cost: 5000000 },
  { code: "lighting", name: "Уличное освещение", vector: "safety", cost: 3000000 },
  { code: "youth_programs", name: "Программы для молодёжи", vector: "safety", cost: 1500000 },
  
  { code: "tax_holidays", name: "Налоговые каникулы", vector: "economy", cost: 4000000 },
  { code: "biz_forum", name: "Инвестфорум", vector: "economy", cost: 2500000 },
  { code: "subsidies", name: "Льготные кредиты", vector: "economy", cost: 6000000 },
  { code: "industrial_zone", name: "Промзона", vector: "economy", cost: 15000000 },
  
  { code: "roads", name: "Ремонт дорог", vector: "quality", cost: 8000000 },
  { code: "transport", name: "Общественный транспорт", vector: "quality", cost: 5000000 },
  { code: "parks", name: "Парки и скверы", vector: "quality", cost: 3500000 },
  { code: "clinics", name: "Поликлиники", vector: "quality", cost: 7000000 },
  
  { code: "ngo_grants", name: "Гранты НКО", vector: "social", cost: 1500000 },
  { code: "festivals", name: "Фестивали", vector: "social", cost: 2000000 },
  { code: "volunteering", name: "Волонтёрство", vector: "social", cost: 1000000 },
  { code: "school_councils", name: "Школьные советы", vector: "social", cost: 800000 },
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

  // Modal buttons
  document.getElementById("btn-scenario").addEventListener("click", () => {
    openModal("modal-scenario");
    if (document.getElementById("interventions-list").children.length === 0) {
      addInterventionRow();
    }
  });
  
  document.getElementById("btn-actions").addEventListener("click", () => {
    openModal("modal-actions");
  });

  refreshTimer = setInterval(refresh, REFRESH_MS);
}

// -------------------------------------------------- Modals & New Features

function openModal(id) {
  document.getElementById(id).hidden = false;
}

function closeModal(id) {
  document.getElementById(id).hidden = true;
  // Clear results
  const results = document.getElementById(id.replace("modal-", "") + "-results");
  if (results) {
    results.hidden = true;
    results.innerHTML = "";
  }
}

function addInterventionRow() {
  const container = document.getElementById("interventions-list");
  const row = document.createElement("div");
  row.className = "intervention-row";
  
  let optionsHtml = '<option value="">Выберите вмешательство</option>';
  INTERVENTION_OPTIONS.forEach(opt => {
    optionsHtml += `<option value="${opt.code}" data-cost="${opt.cost}">${opt.name} (~${(opt.cost/1000000).toFixed(1)} млн ₽)</option>`;
  });
  
  row.innerHTML = `
    <select class="intervention-code" onchange="updateBudgetSuggestion(this)">${optionsHtml}</select>
    <input type="number" class="intervention-budget" placeholder="Бюджет (₽)" min="0" step="100000" />
    <input type="number" class="intervention-month" placeholder="Месяц" min="0" max="36" value="0" />
    <button type="button" class="btn-remove" onclick="this.parentElement.remove()">✕</button>
  `;
  
  container.appendChild(row);
}

function updateBudgetSuggestion(select) {
  const option = select.selectedOptions[0];
  const budgetInput = select.parentElement.querySelector(".intervention-budget");
  if (option && option.dataset.cost) {
    budgetInput.value = option.dataset.cost;
  }
}

async function runScenario() {
  const name = document.getElementById("scenario-name").value || "Сценарий";
  const horizon = parseInt(document.getElementById("scenario-horizon").value) || 12;
  
  const interventions = [];
  document.querySelectorAll(".intervention-row").forEach(row => {
    const code = row.querySelector(".intervention-code").value;
    const budget = parseInt(row.querySelector(".intervention-budget").value) || 0;
    const month = parseInt(row.querySelector(".intervention-month").value) || 0;
    
    if (code && budget > 0) {
      interventions.push({ code, budget_rub: budget, start_month: month });
    }
  });
  
  if (interventions.length === 0) {
    alert("Добавьте хотя бы одно вмешательство");
    return;
  }
  
  const resultsDiv = document.getElementById("scenario-results");
  resultsDiv.innerHTML = "<p>Запуск симуляции...</p>";
  resultsDiv.hidden = false;
  
  try {
    const slug = currentCity.slug;
    const response = await fetch(`/api/city/${slug}/scenario`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scenario_name: name,
        horizon_months: horizon,
        interventions,
      }),
    });
    
    if (!response.ok) throw new Error(await response.text());
    
    const data = await response.json();
    displayScenarioResults(data.scenario);
  } catch (e) {
    resultsDiv.innerHTML = `<p style="color: var(--danger)">Ошибка: ${e.message}</p>`;
  }
}

function displayScenarioResults(scenario) {
  const resultsDiv = document.getElementById("scenario-results");
  
  const deltaText = Object.entries(scenario.delta_vectors)
    .map(([k, v]) => `${k}: ${v > 0 ? '+' : ''}${(v*100).toFixed(1)}%`)
    .join(", ");
  
  const timelineSummary = scenario.timeline
    .filter((_, i) => i % 3 === 0 || i === scenario.timeline.length - 1)
    .map(t => `Месяц ${t.month}: ${Object.entries(t.vectors).map(([k,v]) => `${k}: ${(v*100).toFixed(0)}%`).join(", ")}`)
    .join("\n");
  
  resultsDiv.innerHTML = `
    <h3>Результаты: ${scenario.scenario_name}</h3>
    <p><strong>Общий бюджет:</strong> ${(scenario.total_cost_rub / 1000000).toFixed(1)} млн ₽</p>
    <p><strong>Уверенность:</strong> ${scenario.confidence === 'high' ? 'Высокая ✓' : scenario.confidence === 'medium' ? 'Средняя' : 'Низкая'}</p>
    <p><strong>Изменения:</strong> ${deltaText}</p>
    <h4>Динамика по месяцам:</h4>
    <pre>${timelineSummary}</pre>
    ${scenario.notes.length > 0 ? `<p><strong>Заметки:</strong> ${scenario.notes.join("; ")}</p>` : ""}
  `;
}

async function generateActions() {
  const problemsText = document.getElementById("problems-text").value;
  const includeMetrics = document.getElementById("include-metrics").checked;
  
  const problems = problemsText.split("\n").map(s => s.trim()).filter(s => s.length > 0);
  
  if (problems.length === 0) {
    alert("Введите хотя бы одну проблему");
    return;
  }
  
  const resultsDiv = document.getElementById("actions-results");
  resultsDiv.innerHTML = "<p>Генерация плана действий...</p>";
  resultsDiv.hidden = false;
  
  try {
    const slug = currentCity.slug;
    const response = await fetch(`/api/city/${slug}/actions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        problems,
        include_metric_alerts: includeMetrics,
      }),
    });
    
    if (!response.ok) throw new Error(await response.text());
    
    const data = await response.json();
    displayActionPlan(data.plan);
  } catch (e) {
    resultsDiv.innerHTML = `<p style="color: var(--danger)">Ошибка: ${e.message}</p>`;
  }
}

function displayActionPlan(plan) {
  const resultsDiv = document.getElementById("actions-results");
  
  const actionsHtml = plan.actions.map(a => `
    <div style="padding: 12px; margin: 8px 0; background: rgba(197,160,89,0.05); border-left: 3px solid var(--gold); border-radius: 6px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
        <strong style="color: var(--gold-light)">${a.title}</strong>
        <span style="font-size:0.8rem; padding: 2px 8px; border-radius: 4px; background: ${a.priority === 'critical' ? 'rgba(224,91,91,0.2)' : a.priority === 'high' ? 'rgba(232,168,95,0.2)' : 'rgba(139,155,180,0.2)'}">
          ${a.priority === 'critical' ? '⚡ Критично' : a.priority === 'high' ? '❗ Важно' : '📋 План'}
        </span>
      </div>
      <p style="margin: 4px 0; font-size: 0.9rem; color: var(--muted);">${a.description}</p>
      <p style="margin: 4px 0; font-size: 0.85rem;"><strong>Ответственный:</strong> ${a.responsible.role}</p>
      <p style="margin: 4px 0; font-size: 0.85rem;"><strong>Срок:</strong> ${a.deadline_days} дн.</p>
      <p style="margin: 4px 0; font-size: 0.85rem;"><strong>Результат:</strong> ${a.expected_outcome}</p>
    </div>
  `).join("");
  
  resultsDiv.innerHTML = `
    <h3>План действий для ${plan.city}</h3>
    <p><strong>Резюме:</strong> ${plan.summary}</p>
    ${plan.total_estimated_cost_rub > 0 ? `<p><strong>Оценка стоимости:</strong> ${(plan.total_estimated_cost_rub / 1000000).toFixed(1)} млн ₽</p>` : ""}
    <hr style="border: none; border-top: 1px solid rgba(197,160,89,0.15); margin: 16px 0;" />
    ${actionsHtml}
  `;
}

init();
