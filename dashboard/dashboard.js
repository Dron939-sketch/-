// ============================================================
// Городской Разум — zero-dep премиум-дашборд
// City selection persisted in localStorage; falls back to URL
// slug (`/kolomna`) and finally to the backend-provided default.
// ============================================================

const REFRESH_MS = 10 * 60 * 1000;
const STORAGE_KEY = "cityMind.selectedCitySlug";

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

// -------------------------------------------------- Rendering helpers

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
    tile.setAttribute("role", "button");
    tile.setAttribute("tabindex", "0");
    tile.setAttribute(
      "aria-label",
      `${v.name}: ${scaled} из 6. Нажмите, чтобы увидеть разбор по источникам.`,
    );
    tile.innerHTML = `
      <div class="icon">${v.icon}</div>
      <div class="score">${scaled}<small> / 6</small></div>
      <div class="name">${v.name}</div>
      <svg class="sparkline empty" data-key="${v.dbKey}" viewBox="0 0 ${SPARKLINE_W} ${SPARKLINE_H}" preserveAspectRatio="none" aria-hidden="true"></svg>
      <div class="trend ${trend.cls}">${trend.label}</div>
    `;
    tile.addEventListener("click", () => openTransparency(v.key));
    tile.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openTransparency(v.key); }
    });
    grid.appendChild(tile);
  });
}

function renderSparklines(history) {
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

// -------------------------------------------------- Meister graph (Cytoscape)

// Group → colour on the graph. Keeps the visual language consistent with
// the TZ mock-up: vectors in gold, context ring cooler, closure red.
const GROUP_COLORS = {
  outcome: "#D4AF37",
  vector:  "#C5A059",
  system:  "#00B4D8",
  context: "#1A3A5C",
  closure: "#E05B5B",
};

let cyInstance = null;
let currentGraph = null;

function _edgeWidth(strength) {
  return Math.max(1.2, Math.min(5, 1 + Number(strength || 0) * 4));
}

function _nodeSize(scaled) {
  const v = Number(scaled || 3.5);
  return 54 + Math.max(0, Math.min(6, v)) * 4;
}

function renderMeisterGraph(graph) {
  currentGraph = graph;
  const host = document.getElementById("meister-graph");
  const meta = document.getElementById("graph-meta");
  if (!host) return;

  if (!graph || graph.disabled || !Array.isArray(graph.nodes) || !graph.nodes.length) {
    host.innerHTML =
      `<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--muted);font-size:0.9rem;padding:24px;text-align:center;">
         Граф недоступен${graph?.reason ? ` (${graph.reason})` : ""}. Соберём после первого snapshot'а метрик.
       </div>`;
    if (meta) meta.textContent = "";
    _resetLegend();
    return;
  }

  if (meta) {
    const loops = graph.loops_count || 0;
    const closure = graph.closure_score != null
      ? `закрытие ${(graph.closure_score * 100).toFixed(0)}%`
      : "";
    meta.textContent = [
      `${graph.nodes.length} узлов`,
      `${graph.edges?.length || 0} связей`,
      loops ? `${loops} петель` : "",
      closure,
    ].filter(Boolean).join(" · ");
  }

  if (typeof window.cytoscape !== "function") {
    host.innerHTML =
      `<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--muted);">
         Cytoscape.js ещё грузится…
       </div>`;
    return;
  }

  const elements = [
    ...graph.nodes.map((n) => ({
      data: {
        id: n.id,
        label: n.short || n.title || n.id,
        title: n.title,
        description: n.description || "",
        group: n.group || "system",
        strength: n.strength,
        scaled: n.scaled,
      },
    })),
    ...(graph.edges || []).map((e, i) => ({
      data: {
        id: `e${i}`,
        source: String(e.source),
        target: String(e.target),
        strength: e.strength,
        label: e.label || "",
      },
    })),
  ];

  if (cyInstance) {
    cyInstance.destroy();
    cyInstance = null;
  }

  host.innerHTML = "";
  cyInstance = window.cytoscape({
    container: host,
    elements,
    wheelSensitivity: 0.15,
    layout: {
      name: "cose",
      animate: true,
      animationDuration: 500,
      fit: true,
      padding: 30,
      nodeRepulsion: 12000,
      idealEdgeLength: 110,
    },
    style: [
      {
        selector: "node",
        style: {
          "background-color": (ele) => GROUP_COLORS[ele.data("group")] || "#C5A059",
          "border-color": "#0A1628",
          "border-width": 2,
          "color": "#0A1628",
          "label": "data(label)",
          "text-valign": "center",
          "text-halign": "center",
          "font-family": "Manrope, sans-serif",
          "font-size": 11,
          "font-weight": 700,
          "width": (ele) => _nodeSize(ele.data("scaled")),
          "height": (ele) => _nodeSize(ele.data("scaled")),
          "text-wrap": "wrap",
          "text-max-width": 70,
          "transition-property": "background-color border-color border-width",
          "transition-duration": "200ms",
        },
      },
      {
        selector: "node:selected",
        style: {
          "border-color": "#D4AF37",
          "border-width": 4,
          "background-color": "#E8D5A3",
        },
      },
      {
        selector: "edge",
        style: {
          "width": (ele) => _edgeWidth(ele.data("strength")),
          "line-color": "rgba(197, 160, 89, 0.45)",
          "target-arrow-color": "rgba(197, 160, 89, 0.8)",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          "opacity": 0.85,
        },
      },
      {
        selector: "edge:selected",
        style: {
          "line-color": "#D4AF37",
          "target-arrow-color": "#D4AF37",
          "opacity": 1,
        },
      },
    ],
  });

  cyInstance.on("tap", "node", (evt) => {
    const node = evt.target;
    _showNodeInLegend({
      id: node.data("id"),
      title: node.data("title"),
      description: node.data("description"),
      group: node.data("group"),
      strength: node.data("strength"),
      scaled: node.data("scaled"),
    });
  });

  cyInstance.on("tap", (evt) => {
    if (evt.target === cyInstance) _resetLegend();
  });

  _populateSimulatorSources(graph);
}

function _populateSimulatorSources(graph) {
  const sel = document.getElementById("sim-source");
  if (!sel) return;
  const prev = sel.value;
  sel.innerHTML = "";
  (graph.nodes || []).forEach((n) => {
    const opt = document.createElement("option");
    opt.value = String(n.id);
    const title = n.short || n.title || `Элемент ${n.id}`;
    opt.textContent = `${n.id}. ${title}`;
    sel.appendChild(opt);
  });
  if (prev && (graph.nodes || []).some((n) => String(n.id) === prev)) {
    sel.value = prev;
  }
  _updateSimPreview();
}

function _showNodeInLegend(node) {
  const box = document.getElementById("graph-legend");
  if (!box) return;
  const groupLabels = {
    outcome: "Итоговый элемент",
    vector:  "Ключевой вектор",
    system:  "Системная причина",
    context: "Контекст",
    closure: "Замыкание",
  };
  box.innerHTML = `
    <div class="legend-title">Элемент №${node.id}</div>
    <div class="legend-body">
      <div class="legend-group">${groupLabels[node.group] || ""}</div>
      <div class="name">${node.title || node.id}</div>
      <div class="badge-score">${(node.scaled ?? 3.5).toFixed(1)}<small> / 6</small></div>
      <p>${node.description || "Описание появится, когда ядро заполнит контекст элемента."}</p>
    </div>
  `;
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "legend-action";
  btn.textContent = "Почему такой показатель?";
  btn.addEventListener("click", () => openRootCause(node.id, node.title));
  box.appendChild(btn);
}

function _resetLegend() {
  const box = document.getElementById("graph-legend");
  if (!box) return;
  box.innerHTML = `
    <div class="legend-title">Выберите элемент</div>
    <div class="legend-hint muted small">Нажмите на узел графа, чтобы увидеть детали.</div>
  `;
}

// -------------------------------------------------- Generic modal helpers

function openModal(id) {
  const m = document.getElementById(id);
  if (!m) return;
  m.classList.add("open");
  m.setAttribute("aria-hidden", "false");
}
function closeModal(id) {
  const m = document.getElementById(id);
  if (!m) return;
  m.classList.remove("open");
  m.setAttribute("aria-hidden", "true");
}
function closeAllModals() {
  document.querySelectorAll(".modal.open").forEach((m) => {
    m.classList.remove("open");
    m.setAttribute("aria-hidden", "true");
  });
}

// -------------------------------------------------- Transparency (vector breakdown)

async function openTransparency(vector) {
  if (!currentCity) return;
  const meta = VECTOR_META.find((v) => v.key === vector);
  document.getElementById("transparency-title").textContent =
    meta ? `${meta.icon} ${meta.name}` : vector;
  document.getElementById("transparency-final").textContent = "…";
  document.getElementById("transparency-formula").textContent = "Считаем разбор…";
  document.getElementById("transparency-components").innerHTML = "";
  document.getElementById("transparency-missing").hidden = true;
  openModal("transparency-modal");

  try {
    const data = await fetchJson(
      `/api/city/${currentCity.slug}/metric/${vector}/breakdown`,
    );
    renderTransparency(data);
  } catch (e) {
    console.warn("transparency unavailable", e);
    document.getElementById("transparency-formula").textContent =
      "Нет данных для разбора — попробуйте позже.";
  }
}

function renderTransparency(data) {
  document.getElementById("transparency-title").textContent =
    data.vector_label || data.vector;
  document.getElementById("transparency-final").textContent =
    `${Number(data.final).toFixed(1)} / 6`;
  document.getElementById("transparency-formula").textContent =
    data.formula || `baseline ${data.baseline} + Σ(weight × source)`;

  const list = document.getElementById("transparency-components");
  list.innerHTML = "";
  (data.components || []).forEach((c) => {
    const row = document.createElement("li");
    const missing = c.raw === 0 && (data.missing_sources || []).includes(c.source);
    row.className = "breakdown-row" + (missing ? " missing" : "");
    const contribution = Number(c.contribution || 0);
    // ±2.5 spans the visible half-bar; clamp to [-1, 1].
    const frac = Math.max(-1, Math.min(1, contribution / 2.5));
    const halfPct = Math.abs(frac) * 50;
    const leftPct = frac >= 0 ? 50 : 50 - halfPct;
    const fillClass = frac < 0 ? "breakdown-bar-fill negative" : "breakdown-bar-fill";
    const sign = contribution >= 0 ? "+" : "";
    row.innerHTML = `
      <div class="breakdown-row-head">
        <span class="label">${c.label || c.source}</span>
        <span class="weight">вес ${(Number(c.weight) * 100).toFixed(0)}%</span>
      </div>
      <div class="breakdown-bar">
        <span class="breakdown-bar-center"></span>
        <span class="${fillClass}" style="left:${leftPct}%;width:${halfPct}%;"></span>
      </div>
      <div class="detail">${sign}${contribution.toFixed(2)} · ${c.detail || ""}</div>
    `;
    list.appendChild(row);
  });

  const missingBox = document.getElementById("transparency-missing");
  const missingLabels = (data.missing_sources || []).map((s) => {
    const found = (data.components || []).find((c) => c.source === s);
    return found?.label || s;
  });
  if (missingLabels.length) {
    missingBox.textContent =
      `Нет свежих данных: ${missingLabels.join(", ")}. Показываем baseline до прибытия сигнала.`;
    missingBox.hidden = false;
  } else {
    missingBox.hidden = true;
  }
}

// -------------------------------------------------- Root-cause trace

async function openRootCause(nodeId, nodeTitle) {
  if (!currentCity) return;
  document.getElementById("root-cause-title").textContent =
    nodeTitle ? `Почему «${nodeTitle}»?` : `Элемент №${nodeId}`;
  document.getElementById("root-cause-subtitle").textContent = "Идём по графу назад…";
  document.getElementById("root-cause-chain").innerHTML = "";
  document.getElementById("root-cause-root").hidden = true;
  openModal("root-cause-modal");

  try {
    const data = await fetchJson(
      `/api/city/${currentCity.slug}/root_cause/${encodeURIComponent(nodeId)}`,
    );
    renderRootCause(data, nodeTitle);
  } catch (e) {
    console.warn("root cause unavailable", e);
    document.getElementById("root-cause-subtitle").textContent =
      "Не удалось построить цепочку причин.";
  }
}

function renderRootCause(data, nodeTitle) {
  const chain = Array.isArray(data.chain) ? data.chain : [];
  const sub = document.getElementById("root-cause-subtitle");
  if (!chain.length) {
    sub.textContent = "Этот элемент не имеет входящих связей — это уже корневая причина.";
  } else {
    sub.textContent = `Цепочка из ${chain.length} ${_hopsWord(chain.length)} · от следствия к корню.`;
  }

  const ol = document.getElementById("root-cause-chain");
  ol.innerHTML = "";
  chain.forEach((hop) => {
    const li = document.createElement("li");
    li.className = "cause-hop";
    const strengthPct = Math.round((Number(hop.strength) || 0) * 100);
    li.innerHTML = `
      <span class="depth-badge">${hop.depth}</span>
      <div class="why">${hop.effect_title} <small class="muted">(следствие)</small></div>
      <div class="because">потому что: <strong>${hop.cause_title}</strong> <span class="strength">${strengthPct}%</span></div>
      <div class="because">${hop.because || ""}</div>
    `;
    ol.appendChild(li);
  });

  const rootBox = document.getElementById("root-cause-root");
  if (data.root && chain.length) {
    rootBox.hidden = false;
    document.getElementById("root-cause-root-body").innerHTML = `
      <div class="name">${data.root.title || data.root.short || data.root.id}</div>
      <div class="desc">${data.root.description || "Дальше граф не ведёт — здесь начинается цепочка."}</div>
    `;
  } else {
    rootBox.hidden = true;
  }
}

function _hopsWord(n) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "шага";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return "шагов";
  return "шагов";
}

// -------------------------------------------------- Butterfly simulator

function _updateSimPreview() {
  const slider = document.getElementById("sim-delta");
  const label = document.getElementById("sim-delta-value");
  if (!slider || !label) return;
  const v = Number(slider.value);
  label.textContent = (v >= 0 ? "+" : "") + v.toFixed(1);

  const out = document.getElementById("sim-output");
  if (!out) return;
  if (!currentGraph || !(currentGraph.nodes || []).length) {
    out.innerHTML = '<div class="sim-hint">Граф ещё не загружен.</div>';
    return;
  }
  const sel = document.getElementById("sim-source");
  const id = sel?.value;
  const node = (currentGraph.nodes || []).find((n) => String(n.id) === String(id));
  if (!node) return;
  const name = node.short || node.title || `Элемент ${node.id}`;
  const sign = v >= 0 ? "+" : "";
  out.innerHTML = `
    <div class="sim-ready">
      <span class="title">${name}</span>
      <span class="effect">${sign}${v.toFixed(1)} на шкале 1–6</span>
      <span class="muted small" style="grid-column:1/-1;">Нажмите «Рассчитать каскад», чтобы увидеть эффект на всех 9 элементах.</span>
    </div>
  `;
}

async function runSimulation() {
  if (!currentCity || !currentGraph) return;
  const sel = document.getElementById("sim-source");
  const slider = document.getElementById("sim-delta");
  const btn = document.getElementById("sim-run");
  const out = document.getElementById("sim-output");
  const source_node_id = sel?.value;
  const delta = Number(slider?.value || 0);
  if (!source_node_id) return;
  if (Math.abs(delta) < 0.05) {
    out.innerHTML = '<div class="sim-error">Сдвиньте ручку хотя бы на 0.1 — иначе симулировать нечего.</div>';
    return;
  }

  btn.disabled = true;
  const prevText = btn.textContent;
  btn.textContent = "Считаю…";
  try {
    const res = await fetch(`/api/city/${currentCity.slug}/simulate`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ source_node_id, delta }),
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const data = await res.json();
    renderSimulationResults(data, source_node_id, delta);
    openModal("simulator-modal");
  } catch (e) {
    console.warn("simulate failed", e);
    out.innerHTML = '<div class="sim-error">Не удалось рассчитать каскад. Попробуйте позже.</div>';
  } finally {
    btn.disabled = false;
    btn.textContent = prevText;
  }
}

function renderSimulationResults(data, sourceId, delta) {
  const nodes = data.nodes || [];
  const sourceNode = (currentGraph?.nodes || []).find((n) => String(n.id) === String(sourceId));
  const sourceName = sourceNode?.short || sourceNode?.title || `Элемент ${sourceId}`;
  const sign = delta >= 0 ? "+" : "";

  document.getElementById("simulator-title").textContent =
    `«${sourceName}» ${sign}${Number(delta).toFixed(1)}`;

  const loops = Number(data.loops_weakened || 0);
  document.getElementById("simulator-subtitle").textContent =
    data.note ||
    (nodes.length
      ? `Каскад достиг ${nodes.length} ${_elementsWord(nodes.length)} графа.`
      : "Изменение гасится графом — каскада нет.");

  const summary = document.getElementById("simulator-summary");
  summary.innerHTML = "";
  const chips = [
    `Источник: ${sourceName}`,
    `Δ ${sign}${Number(delta).toFixed(1)}`,
    `Затронуто: ${nodes.length}`,
  ];
  if (loops > 0) chips.push(`Ослаблено петель: ${loops}`);
  chips.forEach((txt) => {
    const el = document.createElement("span");
    el.className = "chip";
    el.textContent = txt;
    summary.appendChild(el);
  });

  const list = document.getElementById("simulator-results");
  list.innerHTML = "";
  nodes.forEach((n) => {
    const row = document.createElement("li");
    row.className = `sim-result-row ${n.direction || "flat"}`;
    if (String(n.node_id) === String(sourceId)) row.classList.add("source");
    const deltaSign = (n.delta >= 0) ? "+" : "";
    row.innerHTML = `
      <div>
        <div class="title">${n.title}</div>
        <div class="depth">глубина ${n.depth} · Δ ${deltaSign}${Number(n.delta).toFixed(2)}</div>
      </div>
      <div class="prediction">
        <span class="before">${Number(n.before).toFixed(1)}</span>
        <span class="arrow">→</span>
        <span class="after">${Number(n.after).toFixed(1)}</span>
      </div>
      <div class="depth">из 6</div>
    `;
    list.appendChild(row);
  });
}

function _elementsWord(n) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "элемента";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return "элементов";
  return "элементов";
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

  openModal("loop-modal");
}

function closeLoopModal() {
  closeModal("loop-modal");
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

const CRISIS_LEVEL_LABELS = {
  critical: "Критично",
  high:     "Высокий",
  medium:   "Средний",
  watch:    "Мониторинг",
};
const CRISIS_LEVEL_ICON = {
  critical: "!",
  high:     "!",
  medium:   "●",
  watch:    "•",
};

function renderCrisis(data) {
  const strip = document.getElementById("crisis-strip");
  const headline = document.getElementById("crisis-headline");
  const toggle = document.getElementById("crisis-toggle");
  const list = document.getElementById("crisis-alerts");
  if (!strip) return;

  const status = data?.status || "ok";
  const alerts = Array.isArray(data?.alerts) ? data.alerts : [];

  strip.setAttribute("data-status", status);
  headline.textContent = data?.headline || (
    status === "ok" ? "Всё в норме — кризисных сигналов нет"
    : "Есть сигналы — проверьте подробности"
  );

  list.innerHTML = "";
  alerts.forEach((a) => {
    const li = document.createElement("li");
    li.className = "crisis-alert";
    li.setAttribute("data-level", a.level || "watch");
    const pct = Math.round((Number(a.probability) || 0) * 100);
    const horizon = a.horizon ? `· ${a.horizon}` : "";
    li.innerHTML = `
      <span class="level-pill">${CRISIS_LEVEL_ICON[a.level] || "•"}</span>
      <div class="title">
        <span>${a.title || "Сигнал"}</span>
        <span class="horizon">${CRISIS_LEVEL_LABELS[a.level] || a.level || ""} ${horizon}</span>
      </div>
      <div class="description">${a.description || ""}</div>
      <div class="probability">Вероятность: ${pct}%</div>
    `;
    list.appendChild(li);
  });

  if (alerts.length === 0) {
    toggle.hidden = true;
    list.hidden = true;
    toggle.setAttribute("aria-expanded", "false");
    return;
  }
  toggle.hidden = false;
  toggle.textContent = `Подробнее (${alerts.length})`;
  // Auto-expand when attention; collapse when just watch so the strip stays compact.
  const shouldOpen = status === "attention";
  toggle.setAttribute("aria-expanded", String(shouldOpen));
  list.hidden = !shouldOpen;
}

const REPUTATION_SOURCE_LABELS = {
  telegram: "Telegram",
  vk:       "ВКонтакте",
  news_rss: "Новости",
  gosuslugi: "Госуслуги",
  ai_pulse: "🤖 AI-пульс",
};
const REPUTATION_RISK_LABELS = {
  low:    "Низкий",
  medium: "Средний",
  high:   "Высокий",
};

function renderReputation(data) {
  const head = document.getElementById("reputation-risk");
  const riskLabel = document.getElementById("reputation-risk-label");
  const total = document.getElementById("reputation-total");
  const sentEl = document.getElementById("reputation-sentiment");
  const shareEl = document.getElementById("reputation-share");
  const trendEl = document.getElementById("reputation-trend");
  const sourcesEl = document.getElementById("reputation-sources");
  const authorsEl = document.getElementById("reputation-authors");
  const viralEl = document.getElementById("reputation-viral");
  const meta = document.getElementById("reputation-meta");
  if (!head || !authorsEl || !viralEl) return;

  const risk = data?.risk || "low";
  head.setAttribute("data-risk", risk);
  riskLabel.textContent = REPUTATION_RISK_LABELS[risk] || risk;

  total.textContent = Number(data?.total_mentions || 0).toLocaleString("ru-RU");

  if (data?.avg_sentiment != null) {
    const s = Number(data.avg_sentiment);
    sentEl.textContent = (s >= 0 ? "+" : "") + s.toFixed(2);
    sentEl.classList.remove("positive", "negative", "neutral");
    sentEl.classList.add(s > 0.1 ? "positive" : s < -0.1 ? "negative" : "neutral");
  } else {
    sentEl.textContent = "—";
    sentEl.classList.remove("positive", "negative");
    sentEl.classList.add("neutral");
  }

  if (data?.negative_share != null) {
    const pct = Math.round(data.negative_share * 100);
    shareEl.textContent = `${pct}%`;
    trendEl.classList.remove("up", "down", "flat");
    if (data.prior_negative_share != null) {
      const delta = data.negative_share - data.prior_negative_share;
      const deltaPct = Math.round(delta * 100);
      if (deltaPct >= 5) {
        trendEl.className = "rep-trend up";
        trendEl.textContent = `▲ +${deltaPct} п.п. vs 7 дн.`;
      } else if (deltaPct <= -5) {
        trendEl.className = "rep-trend down";
        trendEl.textContent = `▼ ${deltaPct} п.п. vs 7 дн.`;
      } else {
        trendEl.className = "rep-trend flat";
        trendEl.textContent = "≈ без изменений";
      }
    } else {
      trendEl.textContent = "";
    }
  } else {
    shareEl.textContent = "—";
    trendEl.textContent = "";
  }

  sourcesEl.innerHTML = "";
  const bySource = data?.by_source || {};
  Object.entries(bySource)
    .sort((a, b) => b[1] - a[1])
    .forEach(([kind, count]) => {
      const chip = document.createElement("span");
      chip.className = "rep-source-chip" + (kind === "ai_pulse" ? " ai" : "");
      chip.innerHTML = `${REPUTATION_SOURCE_LABELS[kind] || kind}: <strong>${count}</strong>`;
      sourcesEl.appendChild(chip);
    });

  authorsEl.innerHTML = "";
  const authors = Array.isArray(data?.top_negative_authors) ? data.top_negative_authors : [];
  if (!authors.length) {
    authorsEl.innerHTML = `<li class="rep-empty">Негативных авторов за 24 часа не нашлось.</li>`;
  } else {
    authors.forEach((a) => {
      const li = document.createElement("li");
      const sourceLabel = REPUTATION_SOURCE_LABELS[a.source_kind] || a.source_kind || "";
      const avgSent = a.avg_sentiment != null
        ? (a.avg_sentiment >= 0 ? "+" : "") + Number(a.avg_sentiment).toFixed(2)
        : "—";
      li.innerHTML = `
        <div class="author">${a.author}</div>
        <div class="meta">
          ${sourceLabel ? sourceLabel + " · " : ""}${a.mentions} ${_mentionsWord(a.mentions)}
          <span class="pill">${a.negative} негатив${a.negative === 1 ? "" : "ных"}</span>
          · средняя тональность ${avgSent}
        </div>
      `;
      authorsEl.appendChild(li);
    });
  }

  viralEl.innerHTML = "";
  const viral = Array.isArray(data?.viral_negative) ? data.viral_negative : [];
  if (!viral.length) {
    viralEl.innerHTML = `<li class="rep-empty">«Выстрелов» с высокой серьёзностью пока нет.</li>`;
  } else {
    viral.forEach((v) => {
      const li = document.createElement("li");
      const sourceLabel = REPUTATION_SOURCE_LABELS[v.source_kind] || v.source_kind || "";
      const titleHtml = v.url
        ? `<a href="${v.url}" target="_blank" rel="noopener">${v.title}</a>`
        : v.title;
      const badges = [];
      if (v.sentiment != null) {
        const s = Number(v.sentiment);
        badges.push(`<span class="badge neg">тональность ${s >= 0 ? "+" : ""}${s.toFixed(2)}</span>`);
      }
      if (v.severity != null) {
        badges.push(`<span class="badge sev">severity ${Number(v.severity).toFixed(2)}</span>`);
      }
      li.innerHTML = `
        <div class="title">${titleHtml}</div>
        <div class="meta">
          ${sourceLabel ? sourceLabel + " · " : ""}${v.author || "автор неизвестен"}
          ${badges.join(" ")}
        </div>
      `;
      viralEl.appendChild(li);
    });
  }

  if (meta) {
    const ts = data?.generated_at
      ? new Date(data.generated_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })
      : "";
    meta.textContent = ts ? `обновлено ${ts}` : "";
  }
}

function _mentionsWord(n) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "упоминание";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return "упоминания";
  return "упоминаний";
}

function renderInvestment(data) {
  const gradeEl = document.getElementById("investment-grade");
  const indexEl = document.getElementById("investment-index");
  const peerEl = document.getElementById("investment-peer");
  const factorsEl = document.getElementById("investment-factors");
  const strengthsEl = document.getElementById("investment-strengths");
  const weaknessesEl = document.getElementById("investment-weaknesses");
  const meta = document.getElementById("investment-meta");
  if (!gradeEl || !factorsEl) return;

  const grade = data?.grade || "—";
  gradeEl.textContent = grade;
  gradeEl.setAttribute("data-grade", grade);

  indexEl.textContent = data?.overall_index != null
    ? Number(data.overall_index).toFixed(1)
    : "—";

  if (data?.peer_rank && data.peer_rank.position && data.peer_rank.total) {
    peerEl.textContent = `Место ${data.peer_rank.position} из ${data.peer_rank.total} пилотов`;
  } else {
    peerEl.textContent = data?.note || "";
  }

  factorsEl.innerHTML = "";
  (data?.factors || []).forEach((f) => {
    const row = document.createElement("div");
    const pct = Math.round((Number(f.value) || 0) * 100);
    const level = pct < 40 ? "low" : (pct < 65 ? "mid" : "high");
    row.className = `invest-factor ${level}`;
    row.innerHTML = `
      <span class="label">${f.label}</span>
      <span class="bar"><span class="bar-fill" style="width:${pct}%"></span></span>
      <span class="value">${pct}%</span>
    `;
    factorsEl.appendChild(row);
  });

  strengthsEl.innerHTML = "";
  (data?.strengths || []).forEach((s) => {
    const li = document.createElement("li");
    li.textContent = s;
    strengthsEl.appendChild(li);
  });
  if (!strengthsEl.children.length) {
    strengthsEl.innerHTML = `<li class="muted small">Пока ни один фактор не достиг 50%.</li>`;
  }

  weaknessesEl.innerHTML = "";
  (data?.weaknesses || []).forEach((w) => {
    const li = document.createElement("li");
    li.textContent = w;
    weaknessesEl.appendChild(li);
  });
  if (!weaknessesEl.children.length) {
    weaknessesEl.innerHTML = `<li class="muted small">Все факторы выше порога — слабых мест нет.</li>`;
  }

  if (meta) {
    const ts = data?.generated_at
      ? new Date(data.generated_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })
      : "";
    meta.textContent = ts ? `обновлено ${ts}` : "";
  }
}

const FORESIGHT_VECTOR_ICON = {
  safety:  "🛡️", economy: "💰", quality: "😊", social:  "🤝",
};

function renderForesight(data) {
  const scenariosEl = document.getElementById("foresight-scenarios");
  const megaEl = document.getElementById("foresight-megatrends");
  const meta = document.getElementById("foresight-meta");
  if (!scenariosEl || !megaEl) return;

  const horizon = data?.horizon_years || 5;
  const scenarios = Array.isArray(data?.scenarios) ? data.scenarios : [];
  const megatrends = Array.isArray(data?.megatrends) ? data.megatrends : [];

  scenariosEl.innerHTML = "";
  scenarios.forEach((s) => {
    const card = document.createElement("div");
    card.className = `scenario ${s.key}`;
    const prob = Math.round((Number(s.probability) || 0) * 100);
    const compCur = s.composite_current != null ? Number(s.composite_current).toFixed(1) : "—";
    const compY5 = s.composite_year_5 != null ? Number(s.composite_year_5).toFixed(1) : "—";
    const vectorsHtml = (s.vectors || []).map((v) => {
      const now = v.current != null ? Number(v.current).toFixed(1) : "—";
      const then = v.year_5 != null ? Number(v.year_5).toFixed(1) : "—";
      const dir = (v.current != null && v.year_5 != null)
        ? (v.year_5 > v.current + 0.05 ? "up" : v.year_5 < v.current - 0.05 ? "down" : "flat")
        : "flat";
      return `<div class="vec ${dir}">
        <span class="name">${FORESIGHT_VECTOR_ICON[v.key] || ""} ${v.label}</span>
        <span class="now">${now}</span>
        <span class="arrow">→</span>
        <span class="then">${then}</span>
      </div>`;
    }).join("");
    card.innerHTML = `
      <div class="scenario-head">
        <span class="scenario-title">${s.label}</span>
        <span class="scenario-prob">${prob}% вероятность</span>
      </div>
      <div class="scenario-desc">${s.description || ""}</div>
      <div class="scenario-vectors">${vectorsHtml}</div>
      <div class="scenario-composite">Композит: <strong>${compCur} → ${compY5}</strong> · к ${horizon}-му году</div>
    `;
    scenariosEl.appendChild(card);
  });

  megaEl.innerHTML = "";
  megatrends.forEach((m) => {
    const li = document.createElement("li");
    li.setAttribute("data-dir", m.direction || "flat");
    const sign = m.weighted >= 0 ? "+" : "";
    li.innerHTML = `
      <span class="label" title="${m.description || ""}">${m.label}</span>
      <span class="weighted">${sign}${Number(m.weighted).toFixed(2)}</span>
    `;
    megaEl.appendChild(li);
  });

  if (meta) {
    const ts = data?.generated_at
      ? new Date(data.generated_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })
      : "";
    meta.textContent = ts ? `обновлено ${ts}` : "";
  }
}

// -------------------------------------------------- Roadmap

// Mirror of python VECTOR → DB column, used to prefill "текущий" from metrics.
const ROADMAP_DB_COLUMN = { "СБ": "sb", "ТФ": "tf", "УБ": "ub", "ЧВ": "chv" };

function _defaultDeadline() {
  const d = new Date();
  d.setFullYear(d.getFullYear() + 1);
  return d.toISOString().slice(0, 10);
}

function _roadmapPrefillFromMetrics(metrics) {
  const select = document.getElementById("rm-vector");
  const start  = document.getElementById("rm-start");
  const startVal = document.getElementById("rm-start-val");
  const targetEl = document.getElementById("rm-target");
  const targetVal = document.getElementById("rm-target-val");
  const dl = document.getElementById("rm-deadline");
  if (!select || !start || !metrics) return;
  const col = ROADMAP_DB_COLUMN[select.value];
  const cur = Number(metrics[col]);
  if (Number.isFinite(cur)) {
    start.value = cur.toFixed(1);
    if (startVal) startVal.textContent = cur.toFixed(1);
    // Auto-set target ~1.2 above current, clamped to 6.
    const target = Math.min(6, Math.max(cur + 0.1, cur * 1.2));
    targetEl.value = target.toFixed(1);
    if (targetVal) targetVal.textContent = target.toFixed(1);
  }
  if (dl && !dl.value) dl.value = _defaultDeadline();
}

function _fmtRubMln(n) {
  if (n == null) return "—";
  const v = Number(n);
  if (v >= 1_000_000_000) return (v / 1_000_000_000).toFixed(2).replace(/\.?0+$/, "") + " млрд ₽";
  if (v >= 1_000_000)     return (v / 1_000_000).toFixed(1).replace(".0", "") + " млн ₽";
  return v.toLocaleString("ru-RU") + " ₽";
}

function _fmtQuarterPeriod(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const mo = d.toLocaleDateString("ru-RU", { month: "short" });
  return `${mo} ${d.getFullYear()}`;
}

function renderRoadmap(roadmap) {
  const out = document.getElementById("roadmap-output");
  if (!out) return;
  if (!roadmap || typeof roadmap !== "object") {
    out.innerHTML = `<div class="roadmap-error">Не удалось построить дорожную карту.</div>`;
    return;
  }

  const vectorName = roadmap.vector_name || roadmap.vector || "—";
  const scenarioLabels = {
    optimistic: "Оптимистичный",
    baseline: "Базовый",
    pessimistic: "Пессимистичный",
  };
  const scenario = scenarioLabels[roadmap.scenario] || roadmap.scenario || "";
  const dl = roadmap.deadline
    ? new Date(roadmap.deadline).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" })
    : "—";

  const chips = [
    `Вектор: <strong>${vectorName}</strong>`,
    `${Number(roadmap.start_level).toFixed(1)} → <strong>${Number(roadmap.target_level).toFixed(1)}</strong>`,
    `Срок: <strong>${dl}</strong>`,
    `Сценарий: <strong>${scenario}</strong>`,
    `Итого: <strong>${_fmtRubMln(roadmap.total_cost_rub)}</strong>`,
  ];

  const milestones = Array.isArray(roadmap.milestones) ? roadmap.milestones : [];
  const milestonesHtml = milestones.map((m) => {
    const interventionsHtml = (m.interventions || []).map((i) => `<li>${i}</li>`).join("");
    const risksHtml = (m.risks || []).length
      ? `<div class="quarter-risks">⚠ ${(m.risks || []).join(" · ")}</div>`
      : "";
    return `
      <li>
        <span></span>
        <div>
          <div class="quarter-period">${_fmtQuarterPeriod(m.quarter_start)} — ${_fmtQuarterPeriod(m.quarter_end)}</div>
          <div class="quarter-target">Цель к концу квартала: ${Number(m.target_level).toFixed(1)}</div>
          ${interventionsHtml ? `<ul class="quarter-interventions">${interventionsHtml}</ul>` : ""}
          ${risksHtml}
        </div>
        <div class="quarter-cost">${_fmtRubMln(m.estimated_cost_rub)}</div>
      </li>
    `;
  }).join("");

  out.innerHTML = `
    <div class="roadmap-summary">
      ${chips.map((c) => `<span class="chip">${c}</span>`).join("")}
    </div>
    ${milestones.length
      ? `<ol class="roadmap-timeline">${milestonesHtml}</ol>`
      : `<div class="muted small">Карта сгенерирована без квартальных вех.</div>`}
    ${(roadmap.notes || []).length
      ? `<div class="muted small" style="margin-top: 10px;">${(roadmap.notes || []).join(" · ")}</div>`
      : ""}
  `;
}

async function submitRoadmap(event) {
  event.preventDefault();
  if (!currentCity) return;
  const out = document.getElementById("roadmap-output");
  const btn = document.getElementById("rm-run");
  const body = {
    vector: document.getElementById("rm-vector").value,
    start_level: Number(document.getElementById("rm-start").value),
    target_level: Number(document.getElementById("rm-target").value),
    deadline: document.getElementById("rm-deadline").value,
    scenario: document.getElementById("rm-scenario").value,
  };
  if (body.target_level <= body.start_level) {
    out.innerHTML = `<div class="roadmap-error">Цель должна быть выше текущего уровня.</div>`;
    return;
  }
  btn.disabled = true;
  const prev = btn.textContent;
  btn.textContent = "Строю…";
  try {
    const res = await fetch(`/api/city/${currentCity.slug}/roadmap`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const data = await res.json();
    renderRoadmap(data.roadmap || data);
  } catch (e) {
    console.warn("roadmap failed", e);
    out.innerHTML = `<div class="roadmap-error">Не удалось построить карту: ${e.message}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = prev;
  }
}

function renderBenchmark(data) {
  const body = document.getElementById("benchmark-body");
  const meta = document.getElementById("benchmark-meta");
  const summary = document.getElementById("benchmark-summary");
  if (!body) return;

  const cities = Array.isArray(data.cities) ? data.cities : [];
  const stats = Array.isArray(data.vector_stats) ? data.vector_stats : [];
  const statsByKey = {};
  stats.forEach((s) => { statsByKey[s.key] = s; });

  if (!cities.length) {
    body.innerHTML =
      `<tr><td colspan="6" class="muted small" style="padding:16px;text-align:center;">
         Данных для сравнения ещё нет — метрики появятся после первого snapshot'а.
       </td></tr>`;
    if (meta) meta.textContent = "";
    if (summary) summary.innerHTML = "";
    return;
  }

  const total = cities.length;
  body.innerHTML = "";
  cities.forEach((city) => {
    const tr = document.createElement("tr");
    if (currentCity && city.slug === currentCity.slug) tr.classList.add("current");

    const pop = city.population
      ? `${Math.round(city.population / 1000)} тыс.`
      : "";
    const cityCell = document.createElement("td");
    cityCell.className = "col-city";
    cityCell.innerHTML =
      `<span class="benchmark-city">
         <span class="emoji">${city.emoji || "🏙️"}</span>
         <span>
           ${city.name}
           ${pop ? `<span class="pop">${pop}</span>` : ""}
         </span>
       </span>`;
    tr.appendChild(cityCell);

    ["safety", "economy", "quality", "social"].forEach((key) => {
      const cell = document.createElement("td");
      const m = city.metrics?.[key];
      if (!m || m.value == null) {
        cell.innerHTML =
          `<span class="benchmark-cell missing"><span class="value">—</span></span>`;
      } else {
        const isLeader  = statsByKey[key]?.leader_slug  === city.slug;
        const isLaggard = statsByKey[key]?.laggard_slug === city.slug && total > 1;
        const cls = isLeader ? "leader" : (isLaggard ? "laggard" : "");
        cell.innerHTML =
          `<span class="benchmark-cell ${cls}">
             <span class="value">${Number(m.value).toFixed(1)}</span>
             <span class="rank">${m.rank ? "#" + m.rank : "—"}</span>
           </span>`;
      }
      tr.appendChild(cell);
    });

    const compCell = document.createElement("td");
    compCell.className = "col-composite";
    if (city.composite == null) {
      compCell.innerHTML = `<span class="muted">—</span>`;
    } else {
      const isBottom = city.composite_rank === total && total > 1;
      compCell.innerHTML =
        `<span class="benchmark-composite${isBottom ? " laggard" : ""}">
           ${Number(city.composite).toFixed(1)}
           <span class="rank" style="margin-left:6px;">#${city.composite_rank}</span>
         </span>`;
    }
    tr.appendChild(compCell);

    body.appendChild(tr);
  });

  if (meta) {
    const ts = data.generated_at
      ? new Date(data.generated_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })
      : "";
    meta.textContent = ts ? `обновлено ${ts}` : "";
  }

  if (summary) {
    summary.innerHTML = "";
    const leader = cities[0];
    const laggard = cities.filter((c) => c.composite != null).slice(-1)[0];
    if (leader && leader.composite != null) {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.innerHTML = `Лидер: <strong>${leader.emoji || "🏙️"} ${leader.name}</strong> · ${Number(leader.composite).toFixed(1)}`;
      summary.appendChild(chip);
    }
    if (laggard && laggard.slug !== leader?.slug) {
      const chip = document.createElement("span");
      chip.className = "chip laggard";
      chip.innerHTML = `Отстаёт: <strong>${laggard.emoji || "🏙️"} ${laggard.name}</strong> · ${Number(laggard.composite).toFixed(1)}`;
      summary.appendChild(chip);
    }
    const spreads = stats
      .filter((s) => s.spread != null)
      .sort((a, b) => b.spread - a.spread);
    if (spreads[0]) {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.innerHTML = `Макс. разрыв: <strong>${spreads[0].label}</strong> · Δ ${Number(spreads[0].spread).toFixed(1)}`;
      summary.appendChild(chip);
    }
  }
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
    // Snapshot raw vector values so the roadmap form can prefill "текущий".
    window.__LATEST_METRICS__ = metrics.city_metrics
      ? {
          sb:  metrics.city_metrics.safety  != null ? metrics.city_metrics.safety  * 6 : null,
          tf:  metrics.city_metrics.economy != null ? metrics.city_metrics.economy * 6 : null,
          ub:  metrics.city_metrics.quality != null ? metrics.city_metrics.quality * 6 : null,
          chv: metrics.city_metrics.social  != null ? metrics.city_metrics.social  * 6 : null,
        }
      : null;
    _roadmapPrefillFromMetrics(window.__LATEST_METRICS__);
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
  try {
    const graph = await fetchJson(`/api/city/${slug}/model`);
    renderMeisterGraph(graph);
  } catch (e) {
    console.warn("model graph unavailable", e);
    renderMeisterGraph(null);
  }
  try {
    const bench = await fetchJson(`/api/benchmark`);
    renderBenchmark(bench);
  } catch (e) {
    console.warn("benchmark unavailable", e);
  }
  try {
    const crisis = await fetchJson(`/api/city/${slug}/crisis`);
    renderCrisis(crisis);
  } catch (e) {
    console.warn("crisis unavailable", e);
    renderCrisis({ status: "ok", alerts: [] });
  }
  try {
    const reputation = await fetchJson(`/api/city/${slug}/reputation`);
    renderReputation(reputation);
  } catch (e) {
    console.warn("reputation unavailable", e);
  }
  try {
    const investment = await fetchJson(`/api/city/${slug}/investment`);
    renderInvestment(investment);
  } catch (e) {
    console.warn("investment unavailable", e);
  }
  try {
    const foresight = await fetchJson(`/api/city/${slug}/foresight`);
    renderForesight(foresight);
  } catch (e) {
    console.warn("foresight unavailable", e);
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

  document.querySelectorAll(".modal [data-dismiss]").forEach((el) => {
    el.addEventListener("click", (e) => {
      const modal = e.currentTarget.closest(".modal");
      if (modal) closeModal(modal.id);
    });
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeAllModals();
  });

  // Roadmap form wiring: live slider labels + submit + vector-change prefill.
  const rmVec     = document.getElementById("rm-vector");
  const rmStart   = document.getElementById("rm-start");
  const rmStartV  = document.getElementById("rm-start-val");
  const rmTarget  = document.getElementById("rm-target");
  const rmTargetV = document.getElementById("rm-target-val");
  const rmDeadline = document.getElementById("rm-deadline");
  const rmForm = document.getElementById("roadmap-form");
  if (rmStart && rmStartV) rmStart.addEventListener("input", () => { rmStartV.textContent = Number(rmStart.value).toFixed(1); });
  if (rmTarget && rmTargetV) rmTarget.addEventListener("input", () => { rmTargetV.textContent = Number(rmTarget.value).toFixed(1); });
  if (rmVec) rmVec.addEventListener("change", () => _roadmapPrefillFromMetrics(window.__LATEST_METRICS__));
  if (rmDeadline && !rmDeadline.value) rmDeadline.value = _defaultDeadline();
  if (rmForm) rmForm.addEventListener("submit", submitRoadmap);

  const crisisToggle = document.getElementById("crisis-toggle");
  const crisisList   = document.getElementById("crisis-alerts");
  if (crisisToggle && crisisList) {
    crisisToggle.addEventListener("click", () => {
      const open = crisisToggle.getAttribute("aria-expanded") === "true";
      const next = !open;
      crisisToggle.setAttribute("aria-expanded", String(next));
      crisisList.hidden = !next;
    });
  }

  const simSlider = document.getElementById("sim-delta");
  const simSource = document.getElementById("sim-source");
  const simRun    = document.getElementById("sim-run");
  if (simSlider) simSlider.addEventListener("input", _updateSimPreview);
  if (simSource) simSource.addEventListener("change", _updateSimPreview);
  if (simRun)    simRun.addEventListener("click", runSimulation);

  refreshTimer = setInterval(refresh, REFRESH_MS);
}

init();
