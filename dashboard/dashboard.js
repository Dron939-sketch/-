// ============================================================
// Городской Разум — zero-dep премиум-дашборд
// City selection persisted in localStorage; falls back to URL
// slug (`/kolomna`) and finally to the backend-provided default.
// ============================================================

const REFRESH_MS = 10 * 60 * 1000;
const HEALTH_REFRESH_MS = 60 * 1000;       // ping health every minute
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

// Cheap structural fingerprint so we can skip Cytoscape re-renders when
// node + edge ids match — preserves the user's cose layout on auto-refresh.
function _graphFingerprint(graph) {
  if (!graph || !Array.isArray(graph.nodes)) return "";
  const nodeIds = graph.nodes.map((n) => String(n.id)).sort().join(",");
  const edgeIds = (graph.edges || [])
    .map((e) => `${e.source}>${e.target}`)
    .sort()
    .join(",");
  return `${nodeIds}|${edgeIds}`;
}

// Update node scaled values in place (no layout disruption).
function _updateGraphScaledValues(graph) {
  if (!cyInstance || !graph || !Array.isArray(graph.nodes)) return;
  graph.nodes.forEach((n) => {
    const node = cyInstance.getElementById(String(n.id));
    if (node && node.length) {
      node.data("scaled", n.scaled);
      node.data("strength", n.strength);
    }
  });
}

function renderMeisterGraph(graph) {
  const prevFingerprint = _graphFingerprint(currentGraph);
  const newFingerprint = _graphFingerprint(graph);
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

  // Same topology as last render → only refresh per-node values, keep layout.
  if (cyInstance && prevFingerprint && prevFingerprint === newFingerprint) {
    _updateGraphScaledValues(graph);
    _populateSimulatorSources(graph);
    return;
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
    // wheelSensitivity intentionally NOT set — Cytoscape recommends
    // sticking with default for cross-mouse / cross-OS consistency.
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
  const runBtn = document.getElementById("sim-run");
  if (!slider || !label) return;
  const v = Number(slider.value);
  label.textContent = (v >= 0 ? "+" : "") + v.toFixed(1);

  const out = document.getElementById("sim-output");
  if (!out) return;
  const graphReady = currentGraph && !currentGraph.disabled
    && Array.isArray(currentGraph.nodes) && currentGraph.nodes.length;
  if (!graphReady) {
    out.innerHTML = '<div class="sim-hint">Граф ещё не загружен — симулятор активируется после первого snapshot\'а метрик.</div>';
    if (runBtn) runBtn.disabled = true;
    return;
  }
  if (runBtn) runBtn.disabled = false;
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
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ source_node_id, delta }),
    });
    if (res.status === 401) { openAuthModal("login"); throw new Error("требуется вход"); }
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
  document.getElementById("loop-modal-description").textContent =
    loop.description || "Описание появится, когда будет собрано больше данных по петле.";

  const bp = loop.break_points || {};
  const details = document.getElementById("loop-modal-details");
  details.innerHTML = "";
  const rows = [];
  if (loop.strength != null) rows.push(["Сила петли", `${Math.round(loop.strength * 100)}%`]);
  if (loop.level) {
    const levelLabel = { critical: "Критично", warn: "Внимание", info: "К сведению" }[loop.level] || loop.level;
    rows.push(["Уровень", levelLabel]);
  }
  if (bp.strategic_priority) rows.push(["Приоритет", bp.strategic_priority]);
  if (bp.break_timeline) rows.push(["Горизонт разрыва", bp.break_timeline]);
  if (bp.effort_required) rows.push(["Требуемые усилия", bp.effort_required]);
  if (bp.advice) rows.push(["Совет", bp.advice]);
  if (bp.length != null) rows.push(["Длина цикла", String(bp.length)]);
  if (bp.impact != null) rows.push(["Влияние", `${Math.round(bp.impact * 100)}%`]);
  if (!rows.length) rows.push(["Детали", "появятся после накопления истории"]);

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

const BUDGET_PRIORITY_LABELS = {
  critical: "Критично", high: "Высокий", medium: "Средний", low: "Низкий",
};

function _fmtRub(n) {
  if (n == null) return "—";
  const v = Number(n);
  if (v >= 1_000_000_000) return (v / 1_000_000_000).toFixed(1).replace(".0", "") + " млрд ₽";
  if (v >= 1_000_000)     return (v / 1_000_000).toFixed(1).replace(".0", "") + " млн ₽";
  if (v >= 1_000)         return (v / 1_000).toFixed(0) + " тыс. ₽";
  return v.toFixed(0) + " ₽";
}

function renderBudget(data) {
  const totalEl = document.getElementById("budget-total");
  const perCapitaEl = document.getElementById("budget-per-capita");
  const trackEl = document.getElementById("budget-bar-track");
  const legendEl = document.getElementById("budget-bar-legend");
  const listEl = document.getElementById("budget-list");
  const noteEl = document.getElementById("budget-note");
  const meta = document.getElementById("budget-meta");
  if (!totalEl || !trackEl || !listEl) return;

  totalEl.textContent = _fmtRub(data?.total_budget_rub);
  if (perCapitaEl) {
    if (data?.population && data?.per_capita_rub) {
      perCapitaEl.textContent =
        `${_fmtRub(data.per_capita_rub)} / жителя × ${Number(data.population).toLocaleString("ru-RU")} чел.`;
    } else {
      perCapitaEl.textContent = "";
    }
  }

  // Proportional stacked bar: 4 vector segments + reserve segment.
  const allocations = Array.isArray(data?.allocations) ? data.allocations : [];
  trackEl.innerHTML = "";
  legendEl.innerHTML = "";
  allocations.forEach((a) => {
    const seg = document.createElement("div");
    seg.className = `seg ${a.key}`;
    seg.style.width = `${(a.recommended_share * 100).toFixed(1)}%`;
    seg.title = `${a.label}: ${(a.recommended_share * 100).toFixed(1)}% · ${_fmtRub(a.recommended_rub)}`;
    trackEl.appendChild(seg);

    const legendItem = document.createElement("span");
    legendItem.innerHTML = `<span class="dot ${a.key}"></span>${a.label.split(" (")[0]} ${(a.recommended_share * 100).toFixed(1)}%`;
    legendEl.appendChild(legendItem);
  });
  if (data?.reserve_share) {
    const reserveSeg = document.createElement("div");
    reserveSeg.className = "seg reserve";
    reserveSeg.style.width = `${(data.reserve_share * 100).toFixed(1)}%`;
    reserveSeg.title = `Резерв: ${(data.reserve_share * 100).toFixed(1)}% · ${_fmtRub(data.reserve_rub)}`;
    trackEl.appendChild(reserveSeg);

    const legendItem = document.createElement("span");
    legendItem.innerHTML = `<span class="dot reserve"></span>Резерв ${(data.reserve_share * 100).toFixed(1)}%`;
    legendEl.appendChild(legendItem);
  }

  // Per-vector list ordered by rub desc so critical/underfunded usually top.
  const sorted = [...allocations].sort((a, b) => b.recommended_rub - a.recommended_rub);
  listEl.innerHTML = "";
  sorted.forEach((a) => {
    const li = document.createElement("li");
    li.setAttribute("data-priority", a.priority);
    const icon = a.priority === "critical" ? "!" : a.priority === "high" ? "!" : a.priority === "medium" ? "●" : "•";
    li.innerHTML = `
      <span class="priority-pill">${icon}</span>
      <div>
        <div class="label">${a.label} ${a.has_crisis ? '<span style="color: var(--danger); font-size: 0.78rem; margin-left: 6px;">⚡ кризис</span>' : ''}</div>
        <div class="rationale">${a.rationale}</div>
      </div>
      <div>
        <div class="amount">${_fmtRub(a.recommended_rub)}</div>
        <div class="share">${(a.recommended_share * 100).toFixed(1)}% · ${BUDGET_PRIORITY_LABELS[a.priority] || ""}</div>
      </div>
    `;
    listEl.appendChild(li);
  });

  if (noteEl) {
    noteEl.textContent = data?.note || "";
  }
  if (meta) {
    const ts = data?.generated_at
      ? new Date(data.generated_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })
      : "";
    meta.textContent = ts ? `обновлено ${ts}` : "";
  }
}

// -------------------------------------------------- Happiness events

const EVENT_SEASON_LABELS = {
  winter:     "Зима ❄️",
  spring:     "Весна 🌱",
  summer:     "Лето ☀️",
  autumn:     "Осень 🍂",
  year_round: "Круглый год",
};
const EVENT_AUDIENCE_LABELS = {
  all: "все", family: "семьи", youth: "молодёжь",
  adults: "взрослые", seniors: "пожилые", tourists: "туристы",
};

function renderHappinessEvents(data) {
  const list = document.getElementById("events-list");
  const meta = document.getElementById("events-meta");
  if (!list) return;
  const events = Array.isArray(data?.events) ? data.events : [];
  list.innerHTML = "";

  if (!events.length) {
    const li = document.createElement("li");
    li.className = "task-empty";
    li.textContent = data?.note || "Событий не найдено.";
    list.appendChild(li);
    if (meta) meta.textContent = "";
    return;
  }

  events.forEach((e) => {
    const li = document.createElement("li");
    li.className = "event-card";
    li.setAttribute("data-season", e.season);

    const happinessPct = Math.round((e.happiness_impact || 0) * 100);
    const trustPct = Math.round((e.trust_impact || 0) * 100);
    const costStr = _fmtRubCompact(e.cost_rub);
    const audienceLabel = EVENT_AUDIENCE_LABELS[e.audience] || e.audience;

    li.innerHTML = `
      <div class="event-head">
        <span class="event-name">${e.name}</span>
        <span class="event-season-chip">${EVENT_SEASON_LABELS[e.season] || e.season}</span>
      </div>
      <div class="event-desc">${e.description || ""}</div>
      <div class="event-impact">
        <span>Счастье <strong>+${happinessPct}%</strong></span>
        <span>Доверие <strong>+${trustPct}%</strong></span>
      </div>
      <div class="event-foot">
        <span>Аудитория: ${audienceLabel} · ${e.duration_days} дн.</span>
        <span class="cost">${costStr}</span>
      </div>
    `;
    list.appendChild(li);
  });

  if (meta) {
    const ts = data?.generated_at
      ? new Date(data.generated_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })
      : "";
    const season = data?.season ? EVENT_SEASON_LABELS[data.season] || data.season : "";
    meta.textContent = ts
      ? `${season} · ${events.length} из ${data?.total_library || "?"} событий · обновлено ${ts}`
      : "";
  }
}

// -------------------------------------------------- Eisenhower matrix

const IKE_ORDER = ["do_first", "schedule", "delegate", "eliminate"];

function renderEisenhower(data) {
  const grid = document.getElementById("eisenhower-grid");
  const meta = document.getElementById("eisenhower-meta");
  if (!grid) return;

  const quads = data?.quadrants || {};
  grid.innerHTML = "";

  IKE_ORDER.forEach((key) => {
    const q = quads[key] || { key, label: key, description: "", count: 0, tasks: [] };
    const box = document.createElement("div");
    box.className = "ike-quadrant";
    box.setAttribute("data-key", q.key);

    const tasksHtml = (q.tasks || []).slice(0, 4).map((t) => {
      const safe = (t.title || "").replace(/</g, "&lt;");
      return `
        <li>
          ${safe}
          <div class="owner">${t.suggested_owner || ""} · ${t.deadline_days === 1 ? "24ч" : (t.deadline_days + " дн.")}</div>
        </li>
      `;
    }).join("");
    const overflow = (q.tasks || []).length > 4 ? `<li class="owner">+ ещё ${(q.tasks.length - 4)}</li>` : "";

    box.innerHTML = `
      <div class="ike-head">
        <span class="ike-label">${q.label}</span>
        <span class="ike-count">${q.count}</span>
      </div>
      <div class="ike-desc">${q.description || ""}</div>
      ${q.count === 0
        ? '<div class="ike-empty">Пусто в этом квадранте.</div>'
        : `<ul class="ike-tasks">${tasksHtml}${overflow}</ul>`}
    `;
    grid.appendChild(box);
  });

  if (meta) {
    const ts = data?.generated_at
      ? new Date(data.generated_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })
      : "";
    meta.textContent = ts ? `всего ${data?.total || 0} · обновлено ${ts}` : "";
  }
}

// -------------------------------------------------- Task manager

const TASK_PRIORITY_LABELS = {
  urgent: "Срочно",
  high:   "Высокий",
  medium: "Средний",
  low:    "Низкий",
};
const TASK_SOURCE_LABELS = {
  agenda:  "повестка",
  crisis:  "кризис",
  roadmap: "roadmap",
};

function renderTasks(data) {
  const list = document.getElementById("task-list");
  const meta = document.getElementById("tasks-meta");
  if (!list) return;

  const tasks = Array.isArray(data?.tasks) ? data.tasks : [];
  list.innerHTML = "";

  if (!tasks.length) {
    const li = document.createElement("li");
    li.className = "task-empty";
    li.textContent = data?.note || "Активных поручений нет.";
    list.appendChild(li);
    if (meta) meta.textContent = "";
    return;
  }

  tasks.forEach((t) => {
    const li = document.createElement("li");
    li.className = "task-item";
    li.setAttribute("data-priority", t.priority);
    const source = TASK_SOURCE_LABELS[t.source] || t.source;
    const deadline = t.deadline_days === 1 ? "24ч" : `${t.deadline_days} дн.`;
    li.innerHTML = `
      <span class="task-priority">${TASK_PRIORITY_LABELS[t.priority] || t.priority}</span>
      <div class="task-body">
        <div class="task-title">${(t.title || "").replace(/</g, "&lt;")}</div>
        <div class="task-rationale">${(t.rationale || "").replace(/</g, "&lt;")} · ${source}</div>
      </div>
      <div class="task-meta">
        <span class="owner">${t.suggested_owner || ""}</span>
        <span>срок ${deadline}</span>
      </div>
    `;
    list.appendChild(li);
  });

  if (meta) {
    const ts = data?.generated_at
      ? new Date(data.generated_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })
      : "";
    meta.textContent = ts ? `${tasks.length} поручений · обновлено ${ts}` : "";
  }
}

// -------------------------------------------------- Deep forecast

const DF_VECTOR_LABELS = {
  safety:  "🛡️ Безопасность",
  economy: "💰 Экономика",
  quality: "😊 Качество жизни",
  social:  "🤝 Соцкапитал",
};
const DF_CONFIDENCE_LABELS = {
  high:               "Высокая уверенность",
  medium:             "Средняя уверенность",
  low:                "Низкая уверенность",
};
const DF_METHOD_LABELS = {
  holt:               "Holt (тренд + уровень)",
  trend:              "линейный тренд",
  flat:               "константа",
  insufficient_data:  "нет истории",
};

function renderDeepForecast(data) {
  const grid = document.getElementById("deep-forecast-grid");
  const meta = document.getElementById("deep-forecast-meta");
  if (!grid) return;

  const vectors = Array.isArray(data?.vectors) ? data.vectors : [];
  grid.innerHTML = "";

  if (!vectors.length) {
    grid.innerHTML = `<div class="dec-empty">${data?.note || "Нет данных."}</div>`;
    if (meta) meta.textContent = "";
    return;
  }

  vectors.forEach((v) => {
    const card = document.createElement("div");
    card.className = "df-card";

    const horizonsHtml = ["7", "30", "90"].map((h) => {
      const f = (v.forecasts || {})[h];
      if (!f) return "";
      // Scale bar to the 1..6 axis. Point and band positioned as % of (max-min=5).
      const pointPct  = Math.max(0, Math.min(100, ((f.point - 1) / 5) * 100));
      const lowerPct  = Math.max(0, Math.min(100, ((f.lower - 1) / 5) * 100));
      const upperPct  = Math.max(0, Math.min(100, ((f.upper - 1) / 5) * 100));
      const bandWidth = Math.max(0.5, upperPct - lowerPct);
      return `
        <div class="df-horizon">
          <span class="h-label">${h} дней</span>
          <span class="bar">
            <span class="band" style="left:${lowerPct}%; width:${bandWidth}%;"></span>
            <span class="point-mark" style="left:${pointPct}%;"></span>
          </span>
          <span class="h-point">${Number(f.point).toFixed(1)}</span>
        </div>
      `;
    }).join("");

    const confidenceCls = v.confidence || "low";
    const current = v.current != null
      ? `${Number(v.current).toFixed(1)}<small>из 6</small>`
      : "—";

    card.innerHTML = `
      <div class="df-head">
        <span class="df-label">${DF_VECTOR_LABELS[v.key] || v.key}</span>
        <span class="df-confidence ${confidenceCls}">${DF_CONFIDENCE_LABELS[confidenceCls] || v.confidence}</span>
      </div>
      <div class="df-current">Сейчас: ${current}</div>
      <div class="df-horizons">${horizonsHtml}</div>
      <div class="df-method">Метод: ${DF_METHOD_LABELS[v.method] || v.method} · ${v.samples_used} наблюдений</div>
    `;
    grid.appendChild(card);
  });

  if (meta) {
    const ts = data?.generated_at
      ? new Date(data.generated_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })
      : "";
    meta.textContent = ts ? `обновлено ${ts}` : "";
  }
}

// -------------------------------------------------- Decision simulator

const DEC_FILTERS = [
  { key: null,        label: "Все" },
  { key: "safety",    label: "🛡️ Безопасность" },
  { key: "economy",   label: "💰 Экономика" },
  { key: "quality",   label: "😊 Качество" },
  { key: "social",    label: "🤝 Соцкапитал" },
];
const DEC_SCENARIO_LABELS = {
  optimistic:  "Оптимистичный",
  realistic:   "Реалистичный",
  pessimistic: "Пессимистичный",
};
const DEC_VECTOR_ICON = { safety: "🛡️", economy: "💰", quality: "😊", social: "🤝" };

let _decisionFilter = null;

function _fmtRubCompact(v) {
  const n = Number(v) || 0;
  if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(1).replace(".0", "") + " млрд ₽";
  if (n >= 1_000_000)     return (n / 1_000_000).toFixed(0) + " млн ₽";
  return n.toLocaleString("ru-RU") + " ₽";
}

function _scenarioDeltaRow(s) {
  const entries = [
    ["safety",  s.safety],
    ["economy", s.economy],
    ["quality", s.quality],
    ["social",  s.social],
  ];
  return entries
    .filter(([_v, d]) => Math.abs(Number(d) || 0) >= 0.05)
    .map(([v, d]) => {
      const cls = d > 0.05 ? "up" : d < -0.05 ? "down" : "flat";
      const sign = d >= 0 ? "+" : "";
      return `<span class="delta ${cls}"><span class="vec">${DEC_VECTOR_ICON[v] || v}</span>${sign}${Number(d).toFixed(2)}</span>`;
    }).join("");
}

function renderDecisions(data) {
  const filtersEl = document.getElementById("dec-filters");
  const gridEl = document.getElementById("dec-grid");
  const meta = document.getElementById("decisions-meta");
  if (!gridEl || !filtersEl) return;

  // Build filter chips once.
  if (!filtersEl.children.length) {
    DEC_FILTERS.forEach((f) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "dec-filter" + (f.key === _decisionFilter ? " active" : "");
      b.textContent = f.label;
      b.addEventListener("click", async () => {
        _decisionFilter = f.key;
        // Toggle active class and refresh.
        filtersEl.querySelectorAll(".dec-filter").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        try {
          const url = f.key
            ? `/api/city/${currentCity?.slug}/decisions?vector=${encodeURIComponent(f.key)}`
            : `/api/city/${currentCity?.slug}/decisions`;
          const fresh = await fetchJson(url);
          renderDecisions(fresh);
        } catch (e) {
          console.warn("decisions filter failed", e);
        }
      });
      filtersEl.appendChild(b);
    });
  }

  const decisions = Array.isArray(data?.decisions) ? data.decisions : [];
  gridEl.innerHTML = "";
  if (!decisions.length) {
    gridEl.innerHTML = `<div class="dec-empty">По этому фильтру решений не найдено.</div>`;
    if (meta) meta.textContent = "";
    return;
  }

  decisions.forEach((d) => {
    const card = document.createElement("div");
    card.className = "dec-card";
    card.setAttribute("data-vector", d.primary_vector);

    const scenariosHtml = ["optimistic", "realistic", "pessimistic"].map((key) => {
      const s = (d.scenarios || {})[key];
      if (!s) return "";
      const deltas = _scenarioDeltaRow(s) || `<span class="delta flat">без заметного эффекта</span>`;
      return `
        <div class="dec-scenario ${key}" title="${s.note || ""}">
          <span class="lbl">${DEC_SCENARIO_LABELS[key]}</span>
          <span class="delta-row">${deltas}</span>
        </div>
      `;
    }).join("");

    const risksHtml = (d.risks || []).slice(0, 3)
      .map((r) => `<li>${r}</li>`)
      .join("");

    const tagsHtml = (d.tags || [])
      .map((t) => `<span class="dec-tag">#${t}</span>`)
      .join("");

    card.innerHTML = `
      <div class="dec-name">${d.name}</div>
      <div class="dec-description">${d.description || ""}</div>
      <div class="dec-meta">
        <span><strong>${_fmtRubCompact(d.cost_rub)}</strong> · ${d.duration_months} мес.</span>
      </div>
      <div class="dec-scenarios">${scenariosHtml}</div>
      ${risksHtml ? `<ul class="dec-risks">${risksHtml}</ul>` : ""}
      <div class="dec-tags">${tagsHtml}</div>
    `;
    gridEl.appendChild(card);
  });

  if (meta) {
    const ts = data?.generated_at
      ? new Date(data.generated_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })
      : "";
    meta.textContent = ts
      ? `${decisions.length} вариантов · обновлено ${ts}`
      : "";
  }
}

const MG_CONFIDENCE_LABELS = {
  high:   "Высокая уверенность",
  medium: "Средняя уверенность",
  low:    "Низкая уверенность",
};
const MG_TOPIC_LABELS = {
  transport: "Транспорт", utilities: "ЖКХ", safety: "Безопасность",
  culture: "Культура",   education: "Образование",
  economy: "Экономика",   social: "Социальное",
};

function renderMarketGaps(data) {
  const grid = document.getElementById("market-gaps-grid");
  const meta = document.getElementById("market-gaps-meta");
  if (!grid) return;

  const niches = Array.isArray(data?.niches) ? data.niches : [];
  grid.innerHTML = "";

  if (!niches.length) {
    grid.innerHTML = `<div class="mg-empty">${data?.note || "Пока нет сигнала о дефиците — подождите накопления жалоб."}</div>`;
    if (meta) meta.textContent = "";
    return;
  }

  niches.forEach((n) => {
    const card = document.createElement("div");
    const conf = n.confidence || "low";
    card.className = `mg-card ${conf}-confidence`;
    const fillPct = Math.max(0, Math.min(100, Math.round((Number(n.demand_score) || 0) * 100)));
    const topicLabel = MG_TOPIC_LABELS[n.linked_topic] || n.linked_topic;

    const evidenceHtml = (n.evidence || []).slice(0, 2).map((e) => {
      const t = (e.title || "").replace(/</g, "&lt;");
      return e.url
        ? `<li>· <a href="${e.url}" target="_blank" rel="noopener">${t}</a></li>`
        : `<li>· ${t}</li>`;
    }).join("");

    card.innerHTML = `
      <div class="mg-head">
        <span class="mg-label">${n.label}</span>
        <span class="mg-confidence ${conf}">${MG_CONFIDENCE_LABELS[conf] || conf}</span>
      </div>
      <div class="mg-rationale">${n.rationale || ""}</div>
      <div class="mg-meter"><span class="fill" style="width:${fillPct}%"></span></div>
      ${evidenceHtml ? `<ul class="mg-evidence">${evidenceHtml}</ul>` : ""}
      <span class="mg-topic-tag">Источник: ${topicLabel}</span>
    `;
    grid.appendChild(card);
  });

  if (meta) {
    const ts = data?.generated_at
      ? new Date(data.generated_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })
      : "";
    const total = data?.window_items || 0;
    meta.textContent = ts
      ? `${total} упоминаний за ${data?.window_days || 30} дней · обновлено ${ts}`
      : "";
  }
}

const TOPIC_EMOJIS = {
  transport: "🚌", utilities: "🏠", safety: "🛡️",
  culture:   "🎭", education: "📚", economy:  "💼",
  social:    "🤝", other:     "💬",
};

function renderTopics(data) {
  const grid = document.getElementById("topics-grid");
  const meta = document.getElementById("topics-meta");
  if (!grid) return;

  const topics = Array.isArray(data?.topics) ? data.topics : [];
  grid.innerHTML = "";

  if (!topics.length || data?.total_current === 0) {
    grid.innerHTML = `<div class="topics-empty">${data?.note || "Нет новостей в окне."}</div>`;
    if (meta) meta.textContent = "";
    return;
  }

  topics.forEach((t) => {
    const card = document.createElement("div");
    card.className = "topic-card";

    const trendCls = t.trend || "flat";
    let trendLabel;
    if (t.count_prior === 0 && t.count > 0) {
      trendLabel = "новое";
    } else if (t.trend_ratio != null) {
      const pct = Math.round(t.trend_ratio * 100);
      trendLabel = pct >= 0 ? `▲ +${pct}%` : `▼ ${pct}%`;
    } else {
      trendLabel = "≈ стабильно";
    }

    const sentVal = t.avg_sentiment;
    let sentStr = "—", sentCls = "neutral";
    if (sentVal != null) {
      sentStr = (sentVal >= 0 ? "+" : "") + Number(sentVal).toFixed(2);
      sentCls = sentVal > 0.1 ? "positive" : sentVal < -0.1 ? "negative" : "neutral";
    }

    const titlesHtml = (t.top_titles || []).map((item) => {
      const text = (item.title || "").replace(/</g, "&lt;");
      return item.url
        ? `<li><a href="${item.url}" target="_blank" rel="noopener">${text}</a></li>`
        : `<li>${text}</li>`;
    }).join("");

    card.innerHTML = `
      <div class="topic-card-head">
        <span class="topic-label">
          <span class="emoji">${TOPIC_EMOJIS[t.key] || "💬"}</span>
          <span>${t.label}</span>
        </span>
        <span class="topic-trend ${trendCls}">${trendLabel}</span>
      </div>
      <div class="topic-stats">
        <span><strong>${t.count}</strong> за неделю</span>
        <span class="topic-sent ${sentCls}">тональность ${sentStr}</span>
      </div>
      ${titlesHtml ? `<ul class="topic-titles">${titlesHtml}</ul>` : ""}
    `;
    grid.appendChild(card);
  });

  if (meta) {
    const ts = data?.generated_at
      ? new Date(data.generated_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })
      : "";
    const tot = data?.total_current || 0;
    meta.textContent = ts ? `${tot} новостей · обновлено ${ts}` : "";
  }
}

const KB_VECTOR_LABELS = {
  safety: "Безопасность",
  economy: "Экономика",
  quality: "Качество жизни",
  social: "Социальный капитал",
};
const KB_EVIDENCE_LABELS = {
  proven:     "Проверенная",
  documented: "Подтверждённая",
  practice:   "Практика",
};

function renderCases(data) {
  const signalsEl = document.getElementById("kb-signals");
  const casesEl = document.getElementById("kb-cases");
  const meta = document.getElementById("cases-meta");
  if (!casesEl) return;

  const weak = Array.isArray(data?.weak_vectors) ? data.weak_vectors : [];
  const crisis = Array.isArray(data?.crisis_vectors) ? data.crisis_vectors : [];
  const recs = Array.isArray(data?.recommendations) ? data.recommendations : [];

  // Signals strip explains why these cases were picked.
  if (signalsEl) {
    const tags = [];
    if (weak.length) {
      tags.push(`<span class="muted">Слабые векторы:</span> ` +
        weak.map((v) => `<span class="kb-tag">${KB_VECTOR_LABELS[v] || v}</span>`).join(" "));
    }
    if (crisis.length) {
      tags.push(`<span class="muted">Кризис:</span> ` +
        crisis.map((v) => `<span class="kb-tag crisis">${KB_VECTOR_LABELS[v] || v}</span>`).join(" "));
    }
    if (!weak.length && !crisis.length) {
      tags.push(`<span class="muted">Сигналов нет — показаны практики с самым высоким уровнем подтверждения.</span>`);
    }
    signalsEl.innerHTML = tags.join(" · ");
  }

  casesEl.innerHTML = "";
  if (!recs.length) {
    casesEl.innerHTML = `<div class="kb-empty">Нет подходящих кейсов. Попробуйте позже, когда появятся метрики или сигналы.</div>`;
    if (meta) meta.textContent = "";
    return;
  }

  recs.forEach((r) => {
    const c = r.case || {};
    const matchChips = [];
    (r.matched_vectors || []).forEach((v) => {
      matchChips.push(`<span class="match">${KB_VECTOR_LABELS[v] || v}</span>`);
    });
    (r.matched_tags || []).forEach((t) => {
      matchChips.push(`<span class="match">#${t}</span>`);
    });
    const evidenceLabel = KB_EVIDENCE_LABELS[c.evidence_level] || c.evidence_level;
    const card = document.createElement("div");
    card.className = "kb-case";
    card.innerHTML = `
      <div class="kb-case-head">
        <div class="kb-case-title">${c.title || "Кейс"}</div>
        <span class="kb-evidence" data-level="${c.evidence_level}">${evidenceLabel}</span>
      </div>
      <div class="kb-problem">Проблема: ${c.problem || ""}</div>
      <div class="kb-approach">${c.approach || ""}</div>
      ${matchChips.length ? `<div class="kb-case-foot">${matchChips.join("")}</div>` : ""}
    `;
    casesEl.appendChild(card);
  });

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
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    });
    if (res.status === 401) { openAuthModal("login"); throw new Error("требуется вход"); }
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

// -------------------------------------------------- Admin link toggle

// Admin panel теперь на /admin.html — главный dashboard лишь показывает
// ссылку в топбаре, когда у текущего пользователя роль admin.
function updateAdminLinkVisibility() {
  const link = document.getElementById("admin-link");
  if (link) link.hidden = !(currentUser && currentUser.role === "admin");
  // Депутаты — управление повесткой; доступно editor и admin.
  const deputies = document.getElementById("deputies-link");
  if (deputies) {
    const role = currentUser && currentUser.role;
    deputies.hidden = !(role === "admin" || role === "editor");
  }
}

// -------------------------------------------------- City pulse

function renderCityPulse(data) {
  const numberEl = document.getElementById("pulse-number");
  const valueEl = document.getElementById("pulse-value");
  const labelEl = document.getElementById("pulse-label");
  const factorsEl = document.getElementById("pulse-factors");
  const meta = document.getElementById("pulse-meta");
  if (!numberEl || !factorsEl) return;

  const level = data?.level || "elevated";
  numberEl.setAttribute("data-level", level);
  valueEl.textContent = data?.overall != null ? Math.round(data.overall) : "—";
  labelEl.textContent = data?.label || "—";

  factorsEl.innerHTML = "";
  (data?.factors || []).forEach((f) => {
    const pct = Math.max(0, Math.min(100, Math.round(f.value || 0)));
    const tier = pct < 40 ? "low" : (pct < 65 ? "mid" : "high");
    const row = document.createElement("div");
    row.className = `pulse-factor ${tier}`;
    row.innerHTML = `
      <span class="lbl" title="${f.description || ""}">${f.label}</span>
      <span class="bar"><span class="bar-fill" style="width:${pct}%"></span></span>
      <span class="val">${pct}</span>
    `;
    factorsEl.appendChild(row);
  });

  if (meta) {
    const ts = data?.generated_at
      ? new Date(data.generated_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })
      : "";
    meta.textContent = ts ? `обновлено ${ts}` : "";
  }
}

// -------------------------------------------------- Auth (login / logout)

let currentUser = null;

async function fetchAuthState() {
  try {
    const res = await fetch("/api/auth/me", { credentials: "same-origin" });
    if (!res.ok) return null;
    const data = await res.json();
    return data.authenticated ? data : null;
  } catch (e) {
    return null;
  }
}

function renderAuthChip() {
  const chip = document.getElementById("auth-chip");
  const label = document.getElementById("auth-label");
  if (!chip || !label) return;
  if (currentUser) {
    chip.classList.add("logged-in");
    const display = currentUser.full_name || currentUser.email || "user";
    label.textContent = display.length > 18 ? display.slice(0, 16) + "…" : display;
    chip.title = `${currentUser.email} · роль: ${currentUser.role || "viewer"} · клик — выйти`;
  } else {
    chip.classList.remove("logged-in");
    label.textContent = "Войти";
    chip.title = "Вход / профиль";
  }
}

async function refreshAuth() {
  currentUser = await fetchAuthState();
  renderAuthChip();
  // Показываем ссылку «⚙️ Админка» в топбаре только для admin.
  updateAdminLinkVisibility();
  return currentUser;
}

async function doLogin(email, password) {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `${res.status} ${res.statusText}`);
  }
  currentUser = data;
  renderAuthChip();
  return data;
}

async function doRegister(payload) {
  const res = await fetch("/api/auth/register", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `${res.status} ${res.statusText}`);
  }
  await refreshAuth();
  return data;
}

async function doLogout() {
  try {
    await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
  } catch (e) { /* ignore */ }
  currentUser = null;
  renderAuthChip();
}

function openAuthModal(tab) {
  openModal("auth-modal");
  switchAuthTab(tab || "login");
}

function switchAuthTab(tab) {
  document.querySelectorAll(".auth-tab").forEach((b) => {
    b.classList.toggle("active", b.getAttribute("data-tab") === tab);
  });
  const loginForm = document.getElementById("login-form");
  const regForm = document.getElementById("register-form");
  if (loginForm) loginForm.hidden = tab !== "login";
  if (regForm)   regForm.hidden = tab !== "register";
  document.getElementById("auth-title").textContent =
    tab === "register" ? "Регистрация" : "Вход";
}

function initAuthForms() {
  document.querySelectorAll(".auth-tab").forEach((b) => {
    b.addEventListener("click", () => switchAuthTab(b.getAttribute("data-tab")));
  });

  const loginForm = document.getElementById("login-form");
  const loginError = document.getElementById("login-error");
  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      loginError.hidden = true;
      try {
        await doLogin(
          document.getElementById("login-email").value,
          document.getElementById("login-password").value,
        );
        closeModal("auth-modal");
      } catch (err) {
        loginError.textContent = err.message || "Ошибка входа";
        loginError.hidden = false;
      }
    });
  }

  const regForm = document.getElementById("register-form");
  const regError = document.getElementById("register-error");
  if (regForm) {
    regForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      regError.hidden = true;
      try {
        await doRegister({
          email: document.getElementById("register-email").value,
          password: document.getElementById("register-password").value,
          full_name: document.getElementById("register-name").value || null,
          registration_code: document.getElementById("register-code").value,
          role: "viewer",
        });
        closeModal("auth-modal");
      } catch (err) {
        regError.textContent = err.message || "Ошибка регистрации";
        regError.hidden = false;
      }
    });
  }

  const chip = document.getElementById("auth-chip");
  if (chip) {
    chip.addEventListener("click", () => {
      if (currentUser) {
        // Logged in → confirm logout.
        if (confirm(`Выйти из аккаунта ${currentUser.email}?`)) doLogout();
      } else {
        openAuthModal("login");
      }
    });
  }
}

// Helper for protected actions: checks auth before firing the provided action.
async function requireAuth(action) {
  if (currentUser) return action();
  openAuthModal("login");
}

// -------------------------------------------------- System health indicator

const HEALTH_COMPONENT_LABELS = {
  database:  "База данных",
  redis:     "Redis-кэш",
  deepseek:  "DeepSeek AI",
  scheduler: "Планировщик",
};
const HEALTH_STATUS_LABELS = {
  ok:       "Всё в норме",
  degraded: "Частично деградировано",
  down:     "Есть отказы",
  starting: "Запускается",
  unknown:  "Проверяю…",
};
const HEALTH_SCHEDULER_LOOP_LABELS = {
  collection: "Сбор новостей",
  weather:    "Погода",
  snapshot:   "Снимок метрик",
};

function _fmtAge(seconds) {
  if (seconds == null) return "—";
  const s = Number(seconds);
  if (s < 60) return `${s} сек. назад`;
  if (s < 3600) return `${Math.floor(s / 60)} мин. назад`;
  if (s < 86400) return `${Math.floor(s / 3600)} ч. назад`;
  return `${Math.floor(s / 86400)} дн. назад`;
}

function renderSystemHealth(data) {
  const dotEl = document.getElementById("sh-dot");
  const labelEl = document.getElementById("sh-label");
  const overallEl = document.getElementById("sh-overall");
  const genEl = document.getElementById("sh-generated");
  const listEl = document.getElementById("sh-list");
  if (!dotEl || !listEl) return;

  const status = data?.status || "unknown";
  dotEl.setAttribute("data-status", status);
  labelEl.textContent = HEALTH_STATUS_LABELS[status] || status;
  overallEl.textContent = HEALTH_STATUS_LABELS[status] || status;

  if (data?.generated_at) {
    const t = new Date(data.generated_at);
    genEl.textContent = `проверка в ${t.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`;
  } else {
    genEl.textContent = "";
  }

  const components = data?.components || {};
  listEl.innerHTML = "";
  Object.entries(components).forEach(([key, info]) => {
    const li = document.createElement("li");
    li.setAttribute("data-status", info.status || "unknown");
    const name = HEALTH_COMPONENT_LABELS[key] || key;
    const detail = info.detail || info.status || "";
    li.innerHTML = `
      <span class="dot"></span>
      <span class="sh-name">${name}</span>
      <span class="sh-detail">${info.status || ""}</span>
    `;
    listEl.appendChild(li);

    // Expand scheduler to show per-loop status.
    if (key === "scheduler" && info.loops) {
      const loops = document.createElement("div");
      loops.className = "sh-loops";
      Object.entries(info.loops).forEach(([loopName, loopInfo]) => {
        const line = document.createElement("div");
        line.className = "loop";
        const displayName = HEALTH_SCHEDULER_LOOP_LABELS[loopName] || loopName;
        const ageStr = loopInfo.last_tick
          ? _fmtAge(loopInfo.age_seconds)
          : "ещё не запускался";
        line.innerHTML = `<span>${displayName}</span><span class="${loopInfo.status || ""}">${ageStr}</span>`;
        loops.appendChild(line);
      });
      listEl.appendChild(loops);
    }
  });
}

async function refreshSystemHealth() {
  try {
    const data = await fetchJson("/api/health/system");
    renderSystemHealth(data);
  } catch (e) {
    console.warn("system health unavailable", e);
    renderSystemHealth({ status: "unknown" });
  }
}

// -------------------------------------------------- Narratives

function _narrativesPrefillFromAgenda(agenda) {
  const topicEl = document.getElementById("nr-topic");
  const ctxEl = document.getElementById("nr-context");
  if (!topicEl || !ctxEl) return;
  // Only prefill when the user hasn't typed anything yet.
  if (!topicEl.value && agenda?.headline) topicEl.value = agenda.headline;
  if (!ctxEl.value && agenda?.description) ctxEl.value = agenda.description;
}

async function copyNarrativeText(btn, text) {
  try {
    await navigator.clipboard.writeText(text || "");
    const prev = btn.textContent;
    btn.classList.add("copied");
    btn.textContent = "Скопировано ✓";
    setTimeout(() => {
      btn.classList.remove("copied");
      btn.textContent = prev;
    }, 1600);
  } catch (e) {
    console.warn("clipboard unavailable", e);
    btn.textContent = "Ошибка";
    setTimeout(() => { btn.textContent = "Копировать"; }, 1600);
  }
}

function renderNarratives(data) {
  const out = document.getElementById("narratives-output");
  if (!out) return;
  if (data?.error && !(data.variants || []).some((v) => v.text)) {
    out.innerHTML = `<div class="narratives-error">${data.error}</div>`;
    return;
  }
  const variants = Array.isArray(data?.variants) ? data.variants : [];
  if (!variants.length) {
    out.innerHTML = `<div class="narratives-error">Ответ пустой — попробуйте ещё раз.</div>`;
    return;
  }

  const cardsHtml = variants.map((v) => {
    const hasText = Boolean(v.text);
    const textHtml = hasText
      ? `<div class="nc-text">${v.text.replace(/</g, "&lt;")}</div>`
      : `<div class="nc-text nc-empty">Модель не вернула этот вариант — попробуйте ещё раз.</div>`;
    return `
      <div class="narrative-card ${v.tone}">
        <div class="nc-head">
          <span class="nc-label">${v.label}</span>
          <span class="nc-hint">${v.length_chars || 0} симв.</span>
        </div>
        <div class="nc-hint">${v.description || ""}</div>
        ${textHtml}
        <div class="nc-foot">
          <span>${v.tone}</span>
          <button type="button" class="nc-copy" data-tone="${v.tone}" ${hasText ? "" : "disabled"}>Копировать</button>
        </div>
      </div>
    `;
  }).join("");

  out.innerHTML = `
    ${data.error ? `<div class="narratives-error">${data.error}</div>` : ""}
    <div class="narratives-grid">${cardsHtml}</div>
  `;

  // Attach copy handlers.
  out.querySelectorAll(".nc-copy").forEach((btn) => {
    const tone = btn.getAttribute("data-tone");
    const variant = variants.find((v) => v.tone === tone);
    if (variant?.text) {
      btn.addEventListener("click", () => copyNarrativeText(btn, variant.text));
    }
  });
}

async function submitNarratives(event) {
  event.preventDefault();
  if (!currentCity) return;
  const out = document.getElementById("narratives-output");
  const btn = document.getElementById("nr-run");
  const body = {
    topic: document.getElementById("nr-topic").value.trim(),
    context: document.getElementById("nr-context").value.trim(),
  };
  if (!body.topic) {
    out.innerHTML = `<div class="narratives-error">Заполните тему заявления.</div>`;
    return;
  }
  btn.disabled = true;
  const prev = btn.textContent;
  btn.textContent = "Генерирую…";
  try {
    const res = await fetch(`/api/city/${currentCity.slug}/narratives`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    });
    if (res.status === 401) { openAuthModal("login"); throw new Error("требуется вход"); }
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const data = await res.json();
    renderNarratives(data);
  } catch (e) {
    console.warn("narratives failed", e);
    out.innerHTML = `<div class="narratives-error">Не удалось сгенерировать: ${e.message}</div>`;
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
    const pulse = await fetchJson(`/api/city/${slug}/pulse`);
    renderCityPulse(pulse);
  } catch (e) {
    console.warn("pulse unavailable", e);
  }
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
    _narrativesPrefillFromAgenda(agenda);
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
  try {
    const budget = await fetchJson(`/api/city/${slug}/budget`);
    renderBudget(budget);
  } catch (e) {
    console.warn("budget unavailable", e);
  }
  try {
    const cases = await fetchJson(`/api/city/${slug}/cases`);
    renderCases(cases);
  } catch (e) {
    console.warn("cases unavailable", e);
  }
  try {
    const topics = await fetchJson(`/api/city/${slug}/topics`);
    renderTopics(topics);
  } catch (e) {
    console.warn("topics unavailable", e);
  }
  try {
    const gaps = await fetchJson(`/api/city/${slug}/market_gaps`);
    renderMarketGaps(gaps);
  } catch (e) {
    console.warn("market gaps unavailable", e);
  }
  try {
    const url = _decisionFilter
      ? `/api/city/${slug}/decisions?vector=${encodeURIComponent(_decisionFilter)}`
      : `/api/city/${slug}/decisions`;
    const decisions = await fetchJson(url);
    renderDecisions(decisions);
  } catch (e) {
    console.warn("decisions unavailable", e);
  }
  try {
    const df = await fetchJson(`/api/city/${slug}/deep_forecast`);
    renderDeepForecast(df);
  } catch (e) {
    console.warn("deep forecast unavailable", e);
  }
  try {
    const tasks = await fetchJson(`/api/city/${slug}/tasks`);
    renderTasks(tasks);
  } catch (e) {
    console.warn("tasks unavailable", e);
  }
  try {
    const ike = await fetchJson(`/api/city/${slug}/eisenhower`);
    renderEisenhower(ike);
  } catch (e) {
    console.warn("eisenhower unavailable", e);
  }
  try {
    const events = await fetchJson(`/api/city/${slug}/happiness_events`);
    renderHappinessEvents(events);
  } catch (e) {
    console.warn("happiness events unavailable", e);
  }
  // Покрытие соц-повестки — только для авторизованных. На 401/403 карточка
  // остаётся скрытой и анонимный посетитель её не увидит.
  try {
    const cov = await fetchJson(`/api/city/${slug}/deputy-coverage?hours=24`);
    renderCoverage(cov);
  } catch (e) {
    const card = document.getElementById("deputy-coverage");
    if (card) card.hidden = true;
  }
  setUpdated();
}

function renderCoverage(data) {
  const card = document.getElementById("deputy-coverage");
  if (!card) return;
  const s = data.summary || {};
  const breakdown = data.breakdown || [];
  if ((s.total_top_categories || 0) === 0) {
    // Нет жалоб в окне — карточку не показываем, повестка спокойная.
    card.hidden = true;
    return;
  }
  card.hidden = false;

  const covered = s.covered_count || 0;
  const total = s.total_top_categories || 0;
  const headline = document.getElementById("cov-headline");
  if (headline) {
    headline.textContent =
      total === covered
        ? `Все ${total} категорий жалоб закрыты темами депутатов`
        : `${covered} из ${total} категорий жалоб закрыты · ${total - covered} без темы`;
  }

  const fill = document.getElementById("cov-bar-fill");
  const meta = document.getElementById("cov-progress-meta");
  if (fill) {
    const pct = s.posts_pct == null ? 0 : Math.min(100, s.posts_pct);
    fill.style.width = `${pct}%`;
  }
  if (meta) {
    if (s.posts_pct == null) {
      meta.textContent = "Постов по закрытым темам пока нет.";
    } else {
      meta.textContent = `Постов сделано: ${s.sum_completed_posts} из ${s.sum_required_posts} (${s.posts_pct.toFixed(0)}%)`;
    }
  }

  const ul = document.getElementById("cov-breakdown");
  if (!ul) return;
  ul.innerHTML = "";
  for (const b of breakdown) {
    const li = document.createElement("li");
    li.className = "cov-row " + (b.covered ? "cov-covered" : "cov-uncovered");
    const status = b.covered
      ? `<span class="cov-status cov-yes">✓ В работе</span>`
      : `<span class="cov-status cov-no">⚠ Без темы</span>`;
    const progress = b.covered && b.required_posts > 0
      ? `<span class="muted small">${b.completed_posts}/${b.required_posts} постов</span>`
      : `<span class="muted small">Секторы: ${(b.target_sectors || []).join(", ") || "—"}</span>`;
    li.innerHTML = `
      <div class="cov-row-main">
        <span class="cov-cat">${escCov(b.label)}</span>
        <span class="muted small">· ${b.complaints_count} жалоб</span>
      </div>
      <div class="cov-row-side">${status} ${progress}</div>
    `;
    ul.appendChild(li);
  }
}

function escCov(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
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

  // modal[data-dismiss] + ESC перенесены в wireStaticTopbarButtons().

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

  const nrForm = document.getElementById("narratives-form");
  if (nrForm) nrForm.addEventListener("submit", submitNarratives);

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

  // help-button + sh-button + modal-dismiss перенесены в wireStaticTopbarButtons()
  // и биндятся синхронно до init() — кнопки работают даже на сбое сети.

  initAuthForms();
  refreshAuth();

  refreshSystemHealth();
  setInterval(refreshSystemHealth, HEALTH_REFRESH_MS);

  refreshTimer = setInterval(refresh, REFRESH_MS);
}

// -------------------------------------------------- Сценарии / Действия (модалки)

const INTERVENTION_OPTIONS = [
  { code: "patrol", name: "Патрулирование ДНД", vector: "safety", cost: 2_000_000 },
  { code: "cctv", name: "Видеонаблюдение", vector: "safety", cost: 5_000_000 },
  { code: "lighting", name: "Уличное освещение", vector: "safety", cost: 3_000_000 },
  { code: "youth_programs", name: "Программы для молодёжи", vector: "safety", cost: 1_500_000 },
  { code: "tax_holidays", name: "Налоговые каникулы", vector: "economy", cost: 4_000_000 },
  { code: "biz_forum", name: "Инвестфорум", vector: "economy", cost: 2_500_000 },
  { code: "subsidies", name: "Льготные кредиты", vector: "economy", cost: 6_000_000 },
  { code: "industrial_zone", name: "Промзона", vector: "economy", cost: 15_000_000 },
  { code: "roads", name: "Ремонт дорог", vector: "quality", cost: 8_000_000 },
  { code: "transport", name: "Общественный транспорт", vector: "quality", cost: 5_000_000 },
  { code: "parks", name: "Парки и скверы", vector: "quality", cost: 3_500_000 },
  { code: "clinics", name: "Поликлиники", vector: "quality", cost: 7_000_000 },
  { code: "ngo_grants", name: "Гранты НКО", vector: "social", cost: 1_500_000 },
  { code: "festivals", name: "Фестивали", vector: "social", cost: 2_000_000 },
  { code: "volunteering", name: "Волонтёрство", vector: "social", cost: 1_000_000 },
  { code: "school_councils", name: "Школьные советы", vector: "social", cost: 800_000 },
];

const PRIORITY_LABELS = {
  critical: { label: "⚡ Критично", cls: "cm-pri-critical" },
  high:     { label: "❗ Важно",   cls: "cm-pri-high" },
  medium:   { label: "📋 План",   cls: "cm-pri-medium" },
  low:      { label: "🗒 Отложено", cls: "cm-pri-low" },
};

function fmtMln(rub) { return `${(rub / 1_000_000).toFixed(1)} млн ₽`; }

function openCmModal(id) {
  const m = document.getElementById(id);
  if (!m) return;
  m.hidden = false;
  document.body.style.overflow = "hidden";
}

function closeCmModal(id) {
  const m = document.getElementById(id);
  if (!m) return;
  m.hidden = true;
  document.body.style.overflow = "";
  const results = m.querySelector(".cm-results-block");
  if (results) {
    results.hidden = true;
    results.innerHTML = "";
  }
}

function addInterventionRow() {
  const container = document.getElementById("interventions-list");
  if (!container) return;
  const row = document.createElement("div");
  row.className = "intervention-row";
  const opts = ['<option value="">Выберите вмешательство</option>'];
  INTERVENTION_OPTIONS.forEach((o) => {
    opts.push(`<option value="${o.code}" data-cost="${o.cost}">${o.name} (~${fmtMln(o.cost)})</option>`);
  });
  row.innerHTML = `
    <select class="intervention-code">${opts.join("")}</select>
    <input type="number" class="intervention-budget" placeholder="Бюджет, ₽" min="0" step="100000" />
    <input type="number" class="intervention-month" placeholder="Мес." min="0" max="36" value="0" />
    <button type="button" class="btn-remove" aria-label="Удалить строку">✕</button>
  `;
  const select = row.querySelector(".intervention-code");
  const budgetInput = row.querySelector(".intervention-budget");
  select.addEventListener("change", () => {
    const opt = select.selectedOptions[0];
    if (opt && opt.dataset.cost) budgetInput.value = opt.dataset.cost;
  });
  row.querySelector(".btn-remove").addEventListener("click", () => row.remove());
  container.appendChild(row);
}

async function runScenario() {
  const resultsDiv = document.getElementById("scenario-results");
  if (!currentCity) return;

  const name = document.getElementById("scenario-name").value.trim() || "Сценарий";
  const horizon = parseInt(document.getElementById("scenario-horizon").value, 10) || 12;
  const interventions = [];
  document.querySelectorAll("#interventions-list .intervention-row").forEach((row) => {
    const code = row.querySelector(".intervention-code").value;
    const budget = parseInt(row.querySelector(".intervention-budget").value, 10) || 0;
    const month = parseInt(row.querySelector(".intervention-month").value, 10) || 0;
    if (code && budget > 0) interventions.push({ code, budget_rub: budget, start_month: month });
  });

  if (interventions.length === 0) {
    resultsDiv.hidden = false;
    resultsDiv.innerHTML = `<p style="color: var(--danger)">Добавьте хотя бы одно вмешательство с положительным бюджетом.</p>`;
    return;
  }

  resultsDiv.hidden = false;
  resultsDiv.innerHTML = `<p class="muted">Запуск симуляции…</p>`;

  try {
    const res = await fetch(`/api/city/${currentCity.slug}/scenario`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario_name: name, horizon_months: horizon, interventions }),
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const data = await res.json();
    renderScenarioResults(data.scenario);
  } catch (e) {
    resultsDiv.innerHTML = `<p style="color: var(--danger)">Не удалось получить прогноз: ${e.message}</p>`;
  }
}

function renderScenarioResults(scenario) {
  const resultsDiv = document.getElementById("scenario-results");
  const deltas = Object.entries(scenario.delta_vectors || {})
    .map(([k, v]) => `${k}: ${v > 0 ? "+" : ""}${(v * 100).toFixed(1)}%`)
    .join(" · ");
  const timeline = (scenario.timeline || [])
    .filter((_, i, a) => i % 3 === 0 || i === a.length - 1)
    .map((t) => {
      const v = Object.entries(t.vectors || {})
        .map(([k, val]) => `${k}: ${(val * 100).toFixed(0)}%`)
        .join(", ");
      return `Месяц ${t.month}: ${v}`;
    })
    .join("\n");
  const conf = { high: "Высокая ✓", medium: "Средняя", low: "Низкая" }[scenario.confidence] || "—";
  const notes = (scenario.notes || []).join("; ");
  resultsDiv.innerHTML = `
    <h3>${scenario.scenario_name || "Сценарий"}</h3>
    <p><strong>Общий бюджет:</strong> ${fmtMln(scenario.total_cost_rub || 0)}</p>
    <p><strong>Уверенность прогноза:</strong> ${conf}</p>
    <p><strong>Изменения векторов:</strong> ${deltas || "—"}</p>
    ${timeline ? `<h4>Динамика по месяцам</h4><pre>${timeline}</pre>` : ""}
    ${notes ? `<p><strong>Заметки:</strong> ${notes}</p>` : ""}
  `;
}

async function generateActions() {
  const resultsDiv = document.getElementById("actions-results");
  if (!currentCity) return;

  const problems = document.getElementById("problems-text").value
    .split("\n").map((s) => s.trim()).filter((s) => s.length > 0);
  const include = document.getElementById("include-metrics").checked;

  if (problems.length === 0) {
    resultsDiv.hidden = false;
    resultsDiv.innerHTML = `<p style="color: var(--danger)">Введите хотя бы одну проблему.</p>`;
    return;
  }

  resultsDiv.hidden = false;
  resultsDiv.innerHTML = `<p class="muted">Генерация плана действий…</p>`;

  try {
    const res = await fetch(`/api/city/${currentCity.slug}/actions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ problems, include_metric_alerts: include }),
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const data = await res.json();
    renderActionPlan(data.plan);
  } catch (e) {
    resultsDiv.innerHTML = `<p style="color: var(--danger)">Не удалось сгенерировать план: ${e.message}</p>`;
  }
}

function escapeHtml(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function renderActionPlan(plan) {
  const resultsDiv = document.getElementById("actions-results");
  const actions = (plan.actions || []).map((a) => {
    const pri = PRIORITY_LABELS[a.priority] || PRIORITY_LABELS.medium;
    const responsible = a.responsible?.role || a.responsible || "—";
    return `
      <div class="cm-action-card">
        <div class="cm-action-head">
          <span class="cm-action-title">${escapeHtml(a.title)}</span>
          <span class="cm-priority-chip ${pri.cls}">${pri.label}</span>
        </div>
        <div class="cm-action-meta">${escapeHtml(a.description || "")}</div>
        <div class="cm-action-meta"><strong>Ответственный:</strong> ${escapeHtml(responsible)}</div>
        <div class="cm-action-meta"><strong>Срок:</strong> ${a.deadline_days ?? "—"} дн.</div>
        ${a.expected_outcome ? `<div class="cm-action-meta"><strong>Результат:</strong> ${escapeHtml(a.expected_outcome)}</div>` : ""}
      </div>`;
  }).join("");
  resultsDiv.innerHTML = `
    <h3>План для ${escapeHtml(plan.city || currentCity.name)}</h3>
    ${plan.summary ? `<p><strong>Резюме:</strong> ${escapeHtml(plan.summary)}</p>` : ""}
    ${plan.total_estimated_cost_rub > 0 ? `<p><strong>Оценка стоимости:</strong> ${fmtMln(plan.total_estimated_cost_rub)}</p>` : ""}
    ${actions || `<p class="muted">Нет действий, удовлетворяющих условиям.</p>`}
  `;
}

// Топбар-кнопки, которым НЕ нужен currentCity — биндим синхронно при
// загрузке страницы, чтобы они работали даже если init() упадёт на
// fetch'е /api/cities или /all_metrics.
function wireStaticTopbarButtons() {
  const helpBtn = document.getElementById("help-button");
  if (helpBtn && !helpBtn.dataset.wired) {
    helpBtn.dataset.wired = "1";
    helpBtn.addEventListener("click", () => openModal("help-modal"));
  }
  // System-health: тоже не зависит от города, биндим заранее.
  const shBtn = document.getElementById("sh-button");
  const shPanel = document.getElementById("sh-panel");
  if (shBtn && shPanel && !shBtn.dataset.wired) {
    shBtn.dataset.wired = "1";
    shBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const open = !shPanel.hidden;
      shPanel.hidden = open;
      shBtn.setAttribute("aria-expanded", String(!open));
    });
    document.addEventListener("click", (e) => {
      if (shPanel.hidden) return;
      if (shPanel.contains(e.target) || shBtn.contains(e.target)) return;
      shPanel.hidden = true;
      shBtn.setAttribute("aria-expanded", "false");
    });
  }
  // Закрытие любой modal[data-dismiss] — ESC + клик-по-крестику + бэкдропу.
  document.querySelectorAll(".modal [data-dismiss]").forEach((el) => {
    if (el.dataset.wired) return;
    el.dataset.wired = "1";
    el.addEventListener("click", (e) => {
      const modal = e.currentTarget.closest(".modal");
      if (modal) closeModal(modal.id);
    });
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeAllModals();
  });
}

function wireScenarioActionButtons() {
  const scenarioBtn = document.getElementById("btn-scenario");
  const actionsBtn = document.getElementById("btn-actions");
  if (scenarioBtn) {
    scenarioBtn.addEventListener("click", () => {
      openCmModal("modal-scenario");
      const list = document.getElementById("interventions-list");
      if (list && list.children.length === 0) addInterventionRow();
    });
  }
  if (actionsBtn) {
    actionsBtn.addEventListener("click", () => openCmModal("modal-actions"));
  }
  // delegate close clicks (backdrop + ✕ + cancel buttons)
  document.querySelectorAll('[data-close]').forEach((el) => {
    el.addEventListener("click", () => closeCmModal(el.getAttribute("data-close")));
  });
  // wire the form action buttons once
  const addBtn = document.getElementById("btn-add-intervention");
  if (addBtn) addBtn.addEventListener("click", addInterventionRow);
  const runBtn = document.getElementById("btn-run-scenario");
  if (runBtn) runBtn.addEventListener("click", runScenario);
  const genBtn = document.getElementById("btn-generate-actions");
  if (genBtn) genBtn.addEventListener("click", generateActions);
  // ESC closes whichever cm-modal is open
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    document.querySelectorAll(".cm-modal:not([hidden])").forEach((m) => closeCmModal(m.id));
  });
}

// -------------------------------------------------- Голосовой помощник «Душа города»

const SoulAssistant = (() => {
  let mediaRecorder = null;
  let recordChunks = [];
  let recording = false;

  const $ = (id) => document.getElementById(id);
  const escSoul = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));

  function open() {
    const p = $("soul-panel");
    if (!p) return;
    p.hidden = false;
    setTimeout(() => $("soul-text")?.focus(), 50);
    if ($("soul-log").children.length === 0) {
      addBubble("soul", "Здравствуй, друг. Я — Коломна. Расскажи, что тебя ко мне привело?");
    }
  }
  function close() {
    if ($("soul-panel")) $("soul-panel").hidden = true;
    if (recording) cancelRecord();
  }

  function addBubble(who, text) {
    const log = $("soul-log");
    if (!log) return null;
    const div = document.createElement("div");
    div.className = `soul-bubble soul-${who}`;
    div.innerHTML = escSoul(text);
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  function setHint(msg) {
    const h = $("soul-hint");
    if (h) h.textContent = msg;
  }

  async function ask({ text, audioBlob, audioFormat }) {
    const slug = (window.currentCity?.slug) || (typeof currentCity !== "undefined" ? currentCity?.slug : null) || "kolomna";
    const cityPath = encodeURIComponent(slug);
    let res;
    try {
      if (audioBlob) {
        const fd = new FormData();
        fd.append("audio", audioBlob, `q.${audioFormat}`);
        fd.append("audio_format", audioFormat);
        fd.append("speak", "true");
        res = await fetch(`/api/city/${cityPath}/voice/ask-audio`, { method: "POST", body: fd });
      } else {
        res = await fetch(`/api/city/${cityPath}/voice/ask`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: text, speak: true }),
        });
      }
    } catch (e) {
      addBubble("soul", "Связь дрогнула. Попробуйте ещё раз через минуту.");
      return;
    }
    if (!res.ok) {
      addBubble("soul", `Не получилось: ${res.status}`);
      return;
    }
    const data = await res.json();
    if (data.transcript && audioBlob) addBubble("user", data.transcript);
    if (data.stt_failed) {
      addBubble("soul", "Я не расслышала. Скажите ещё раз громче, пожалуйста.");
    } else if (data.reply_text) {
      addBubble("soul", data.reply_text);
    }
    if (data.reply_audio_base64 && data.audio_mime) {
      playB64Audio(data.reply_audio_base64, data.audio_mime);
    }
  }

  function playB64Audio(b64, mime) {
    const player = $("soul-player");
    if (!player) return;
    player.src = `data:${mime};base64,${b64}`;
    player.play().catch(() => {});
  }

  async function sendText() {
    const input = $("soul-text");
    if (!input) return;
    const t = input.value.trim();
    if (!t) return;
    addBubble("user", t);
    input.value = "";
    setHint("Город размышляет…");
    await ask({ text: t });
    setHint("Можно ещё. Или нажмите 🎙 для голоса.");
  }

  function pickAudioFormat() {
    if (typeof MediaRecorder === "undefined") return null;
    const candidates = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/mp4",
      "audio/ogg;codecs=opus",
    ];
    for (const t of candidates) {
      if (MediaRecorder.isTypeSupported(t)) return t;
    }
    return "";
  }

  async function startRecord() {
    if (recording) return stopRecord();
    if (!navigator.mediaDevices?.getUserMedia) {
      addBubble("soul", "Браузер не поддерживает запись с микрофона.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = pickAudioFormat();
      mediaRecorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      recordChunks = [];
      mediaRecorder.ondataavailable = (e) => { if (e.data?.size > 0) recordChunks.push(e.data); };
      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        if (!recordChunks.length) {
          setHint("Запись пуста. Попробуйте ещё.");
          return;
        }
        const type = mediaRecorder.mimeType || "audio/webm";
        const blob = new Blob(recordChunks, { type });
        const fmt = type.includes("mp4") ? "mp4" : type.includes("ogg") ? "ogg" : "webm";
        setHint("Город слушает…");
        await ask({ audioBlob: blob, audioFormat: fmt });
        setHint("Можно ещё. Или напишите.");
      };
      mediaRecorder.start();
      recording = true;
      const mic = $("soul-mic");
      if (mic) { mic.classList.add("soul-mic-active"); mic.textContent = "■"; }
      setHint("Говорите… Нажмите ■ когда закончите.");
    } catch (e) {
      addBubble("soul", "Доступ к микрофону отклонён. Можно набрать вопрос текстом.");
    }
  }

  function stopRecord() {
    if (!recording || !mediaRecorder) return;
    recording = false;
    const mic = $("soul-mic");
    if (mic) { mic.classList.remove("soul-mic-active"); mic.textContent = "🎙"; }
    try { mediaRecorder.stop(); } catch (_) {}
  }

  function cancelRecord() {
    if (!recording || !mediaRecorder) return;
    recording = false;
    const mic = $("soul-mic");
    if (mic) { mic.classList.remove("soul-mic-active"); mic.textContent = "🎙"; }
    try { mediaRecorder.stream?.getTracks?.().forEach((t) => t.stop()); } catch (_) {}
    recordChunks = [];
  }

  function wire() {
    $("soul-fab")?.addEventListener("click", open);
    $("soul-close")?.addEventListener("click", close);
    $("soul-send")?.addEventListener("click", sendText);
    $("soul-mic")?.addEventListener("click", startRecord);
    $("soul-text")?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); sendText(); }
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !$("soul-panel")?.hidden) close();
    });
  }

  return { wire };
})();

wireStaticTopbarButtons();
wireScenarioActionButtons();
// Soul-виджет вытеснил Ко-пилот (см. /copilot.js + /copilot.css);
// сама IIFE SoulAssistant остаётся как dead code, можно удалить
// отдельным cleanup-PR без риска регресса.

init();
