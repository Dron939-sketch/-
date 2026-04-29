/* Deputy Agenda manager — standalone screen.
 *
 * Simple imperative JS, no framework. Talks to /api/city/{name}/deputies* and
 * /api/city/{name}/deputy-topics* endpoints documented in api/deputy_routes.py.
 *
 * Design choice: this is a separate screen, NOT embedded in the main dashboard.
 * The main dashboard only shows a "🏛️ Депутаты" link in the topbar (visible
 * to editor/admin) — users opt in by clicking it. Keeps the main dashboard
 * focused on "что мне делать прямо сейчас".
 */

(() => {
  const $ = (id) => document.getElementById(id);

  const state = {
    user: null,
    cityName: localStorage.getItem("cm.city") || "Коломна",
    deputies: [],
    topics: [],
    currentTopic: null,
  };

  // ---- auth ----

  async function fetchMe() {
    try {
      const r = await fetch("/api/auth/me", { credentials: "include" });
      if (!r.ok) return null;
      return await r.json();
    } catch {
      return null;
    }
  }

  function isAllowed(user) {
    return user && (user.role === "admin" || user.role === "editor");
  }

  // ---- API helpers ----

  function api(path, opts = {}) {
    return fetch(`/api/city/${encodeURIComponent(state.cityName)}${path}`, {
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
  }

  async function apiGet(path) {
    const r = await api(path);
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    return r.json();
  }

  async function apiPost(path, body) {
    const r = await api(path, { method: "POST", body: JSON.stringify(body) });
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    return r.json();
  }

  async function apiDelete(path) {
    const r = await api(path, { method: "DELETE" });
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    return r.json();
  }

  // ---- rendering ----

  function renderSummary(dash) {
    const el = $("dep-summary");
    el.innerHTML = "";
    const items = [
      { label: "Депутатов активно", value: dash?.totals?.deputies ?? "—" },
      { label: "Активных тем", value: dash?.totals?.active_topics ?? "—" },
      { label: "Завершено недавно", value: dash?.totals?.completed_topics_recent ?? "—" },
      { label: "Выполнение", value: ((dash?.totals?.completion_rate ?? 0) * 100).toFixed(0) + "%" },
    ];
    for (const it of items) {
      const div = document.createElement("div");
      div.className = "stats-summary-chip";
      div.innerHTML = `<span class="muted small">${it.label}</span><strong>${it.value}</strong>`;
      el.appendChild(div);
    }
    $("dep-meta").textContent = `${state.cityName} · обновлено ${new Date().toLocaleTimeString("ru-RU")}`;
  }

  function renderTopics() {
    const ul = $("topics-list");
    ul.innerHTML = "";
    if (!state.topics.length) {
      ul.innerHTML = '<li class="muted">Активных тем нет. Создайте первую через кнопку "+ Новая тема".</li>';
      return;
    }
    for (const t of state.topics) {
      const li = document.createElement("li");
      const ratio = t.required_posts ? Math.round((t.completed_posts / t.required_posts) * 100) : 0;
      li.innerHTML = `
        <button type="button" class="user-row" data-topic-id="${t.id}" style="width:100%;text-align:left;background:transparent;border:0;padding:0.5rem 0;">
          <strong>${escapeHtml(t.title)}</strong>
          <span class="muted small" style="margin-left:0.5rem;">[${t.priority}] ${t.target_tone}</span>
          <span class="muted small" style="float:right;">${t.completed_posts}/${t.required_posts} (${ratio}%) · ${t.assignees?.length || 0} назн.</span>
        </button>
      `;
      li.querySelector("button").addEventListener("click", () => openTopic(t.id));
      ul.appendChild(li);
    }
  }

  function renderDeputies() {
    const ul = $("deputies-list");
    ul.innerHTML = "";
    if (!state.deputies.length) {
      ul.innerHTML = '<li class="muted">Депутатов пока нет. Добавьте первого через "+ Добавить депутата".</li>';
      return;
    }
    for (const d of state.deputies) {
      const li = document.createElement("li");
      const sectors = (d.sectors || []).join(", ") || "—";
      li.innerHTML = `
        <button type="button" class="user-row dep-card-btn" data-dep-profile="${d.id}" title="Открыть карточку">
          <strong>${escapeHtml(d.name)}</strong>
          <span class="muted small" style="margin-left:0.5rem;">${escapeHtml(d.role)} · ${escapeHtml(d.district || "—")} · ${escapeHtml(d.party || "—")}</span>
          <span class="muted small" style="display:block;">Сектора: ${escapeHtml(sectors)}</span>
        </button>
        <button type="button" class="admin-close-user" data-dep-id="${d.id}" title="Удалить">🗑️</button>
      `;
      li.querySelector("button[data-dep-id]").addEventListener("click", () => deleteDeputy(d.id));
      li.querySelector("button[data-dep-profile]").addEventListener("click", () => openDeputyCard(d.id));
      ul.appendChild(li);
    }
  }

  function renderTopicDetail(topic, posts) {
    $("td-title").textContent = topic.title;
    $("td-meta").textContent = `Приоритет ${topic.priority} · тональность ${topic.target_tone} · срок ${new Date(topic.deadline).toLocaleDateString("ru-RU")} · источник ${topic.source}`;

    const assigneesUl = $("td-assignees");
    assigneesUl.innerHTML = "";
    if (!topic.assignees?.length) {
      assigneesUl.innerHTML = '<li class="muted">Никто не назначен</li>';
    } else {
      for (const aid of topic.assignees) {
        const dep = state.deputies.find((d) => d.id === aid);
        const li = document.createElement("li");
        li.textContent = dep ? `${dep.name} (${dep.role})` : `#${aid}`;
        assigneesUl.appendChild(li);
      }
    }

    const sel = $("td-draft-deputy");
    sel.innerHTML = "";
    for (const aid of topic.assignees || []) {
      const dep = state.deputies.find((d) => d.id === aid);
      if (!dep) continue;
      const opt = document.createElement("option");
      opt.value = String(aid);
      opt.textContent = dep.name;
      sel.appendChild(opt);
    }

    const postsUl = $("td-posts");
    postsUl.innerHTML = "";
    if (!posts.length) {
      postsUl.innerHTML = '<li class="muted">Публикаций ещё нет</li>';
    } else {
      for (const p of posts) {
        const li = document.createElement("li");
        li.innerHTML = `<strong>${escapeHtml(p.deputy_name || "?")}</strong> · ${escapeHtml(p.platform)} · 👁 ${p.views} · ❤️ ${p.likes} · 💬 ${p.comments}`;
        postsUl.appendChild(li);
      }
    }

    $("td-draft").style.display = "none";
    $("topic-detail-card").hidden = false;
    $("topic-detail-card").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function escapeHtml(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // ---- actions ----

  async function loadAll() {
    try {
      const [dash, deputies, topicsResp] = await Promise.all([
        apiGet("/deputy-dashboard"),
        apiGet("/deputies"),
        apiGet("/deputy-topics?status=active"),
      ]);
      state.deputies = deputies.deputies || [];
      state.topics = topicsResp.topics || [];
      renderSummary(dash);
      renderTopics();
      renderDeputies();
      $("updated-at").textContent = new Date().toLocaleTimeString("ru-RU");
    } catch (e) {
      console.error(e);
      alert("Ошибка загрузки: " + e.message);
    }
  }

  async function openTopic(topicId) {
    try {
      const data = await apiGet(`/deputy-topics/${topicId}`);
      state.currentTopic = data.topic;
      renderTopicDetail(data.topic, data.posts || []);
    } catch (e) {
      alert("Не удалось открыть тему: " + e.message);
    }
  }

  // -------------------------------------------- Deputy profile card

  async function openDeputyCard(deputyId) {
    const card = $("dep-card");
    const errorBox = $("dep-card-error");
    errorBox.hidden = true;
    errorBox.textContent = "";
    // Заполняем заглушками пока грузим
    $("dep-card-title").textContent = "Загрузка…";
    $("dep-card-eyebrow").textContent = "";
    $("dep-card-sub").textContent = "";
    $("dep-card-stats").innerHTML = "";
    $("dep-card-topics").innerHTML = "";
    $("dep-card-posts").innerHTML = "";
    $("dep-card-topics-empty").hidden = true;
    $("dep-card-posts-empty").hidden = true;
    card.hidden = false;
    document.body.style.overflow = "hidden";

    try {
      const data = await apiGet(`/deputies/${deputyId}/profile`);
      renderDeputyCard(data);
      // SMM-секция: запоминаем deputy_id для последующих fetch'ей,
      // сразу показываем «Архетип» (детерминированный, мгновенный).
      state.smmDeputyId = deputyId;
      state.smmCache = {};
      activateSmmTab("archetype");
    } catch (e) {
      errorBox.textContent = `Не удалось загрузить карточку: ${e.message}`;
      errorBox.hidden = false;
    }
  }

  function closeDeputyCard() {
    $("dep-card").hidden = true;
    document.body.style.overflow = "";
  }

  function renderDeputyCard(data) {
    const dep = data.deputy || {};
    const stats = data.stats || {};
    const topics = data.active_topics || [];
    const posts = data.recent_posts || [];

    const roleLabel = ({
      speaker: "Спикер Совета",
      sector_lead: "Ведущий по сектору",
      district_rep: "Депутат округа",
      support: "Поддержка",
      neutral: "Нейтральный",
    })[dep.role] || dep.role;

    $("dep-card-eyebrow").textContent = `${roleLabel} · ${dep.district || "—"}`;
    $("dep-card-title").textContent = dep.name || "Депутат";
    const sectors = (dep.sectors || []).join(", ") || "—";
    $("dep-card-sub").textContent = `Партия: ${dep.party || "—"} · Секторы: ${sectors}`;

    // Stats grid
    const statsEl = $("dep-card-stats");
    const completion = stats.completion_pct == null
      ? "—"
      : `${stats.completion_pct.toFixed(0)}%`;
    const fmtN = (v) => (v == null ? "—" : v.toLocaleString("ru-RU"));
    statsEl.innerHTML = `
      <div class="dep-stat"><div class="dep-stat-value">${stats.active_topics_count || 0}</div><div class="dep-stat-label">Активные темы</div></div>
      <div class="dep-stat"><div class="dep-stat-value">${completion}</div><div class="dep-stat-label">План закрыт</div></div>
      <div class="dep-stat"><div class="dep-stat-value">${stats.total_posts || 0}</div><div class="dep-stat-label">Постов всего</div></div>
      <div class="dep-stat"><div class="dep-stat-value">${fmtN(stats.total_views)}</div><div class="dep-stat-label">Просмотры</div></div>
      <div class="dep-stat"><div class="dep-stat-value">${fmtN(stats.total_likes)}</div><div class="dep-stat-label">Лайки</div></div>
      <div class="dep-stat"><div class="dep-stat-value">${fmtN(stats.total_comments)}</div><div class="dep-stat-label">Комментарии</div></div>
    `;

    // Active topics
    const topicsUl = $("dep-card-topics");
    topicsUl.innerHTML = "";
    if (topics.length === 0) {
      $("dep-card-topics-empty").hidden = false;
    } else {
      $("dep-card-topics-empty").hidden = true;
      for (const t of topics) {
        const li = document.createElement("li");
        const req = t.required_posts || 0;
        const done = t.completed_posts || 0;
        const pct = req > 0 ? Math.min(100, Math.round((100 * done) / req)) : 0;
        li.innerHTML = `
          <div class="dep-topic-row">
            <span class="autogen-priority autogen-pri-${escapeHtml(t.priority || "medium")}">${escapeHtml(prioLabel(t.priority))}</span>
            <span class="dep-topic-title">${escapeHtml(t.title)}</span>
          </div>
          <div class="dep-topic-progress">
            <div class="dep-progress-bar"><div class="dep-progress-fill" style="width:${pct}%"></div></div>
            <span class="muted small">${done} / ${req} постов · до ${formatDate(t.deadline)}</span>
          </div>
        `;
        topicsUl.appendChild(li);
      }
    }

    // Recent posts
    const postsUl = $("dep-card-posts");
    postsUl.innerHTML = "";
    if (posts.length === 0) {
      $("dep-card-posts-empty").hidden = false;
    } else {
      $("dep-card-posts-empty").hidden = true;
      for (const p of posts.slice(0, 10)) {
        const li = document.createElement("li");
        const link = p.url ? `<a href="${escapeHtml(p.url)}" target="_blank" rel="noopener">${escapeHtml(p.platform || "пост")}</a>` : escapeHtml(p.platform || "пост");
        li.innerHTML = `
          <div class="dep-post-row">
            <span class="dep-post-platform">${link}</span>
            <span class="muted small">${formatDate(p.published_at)}</span>
          </div>
          <div class="dep-post-topic muted small">${escapeHtml(p.topic_title || "")}</div>
          <div class="dep-post-engagement muted small">
            👁 ${p.views || 0} · ❤ ${p.likes || 0} · 💬 ${p.comments || 0} · 🔁 ${p.reposts || 0}
          </div>
        `;
        postsUl.appendChild(li);
      }
    }
  }

  function prioLabel(p) {
    return ({ critical: "⚡ Критично", high: "❗ Важно", medium: "📋 План", low: "🗒 Отложено" })[p] || p || "—";
  }

  function formatDate(iso) {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleDateString("ru-RU", { day: "2-digit", month: "short", year: "numeric" });
    } catch (_) {
      return iso;
    }
  }

  // -------------------------------------------- SMM-блок (архетип / аудит / контент)

  state.smmDeputyId = null;
  state.smmCache = {};

  function activateSmmTab(name) {
    // Активный таб
    document.querySelectorAll(".dep-smm-tab").forEach((b) => {
      b.dataset.active = (b.dataset.smmTab === name) ? "1" : "0";
    });
    // Видимая панель
    ["archetype", "audit", "post", "plan"].forEach((k) => {
      const pane = $("dep-smm-" + k);
      if (pane) pane.hidden = (k !== name);
    });
    // По первому открытию — лениво загружаем
    if (name !== "post" && !state.smmCache[name]) {
      loadSmmTab(name);
    }
  }

  async function loadSmmTab(name) {
    const id = state.smmDeputyId;
    if (!id) return;
    const pane = $("dep-smm-" + name);
    if (!pane) return;
    pane.innerHTML = '<div class="muted small">Загружаю…</div>';
    try {
      let data;
      if (name === "archetype") {
        data = await apiGet(`/deputies/${id}/archetype`);
        pane.innerHTML = renderArchetype(data);
      } else if (name === "audit") {
        data = await apiGet(`/deputies/${id}/audit`);
        pane.innerHTML = renderAudit(data);
      } else if (name === "plan") {
        data = await apiGet(`/deputies/${id}/content_plan`);
        pane.innerHTML = renderPlan(data);
      }
      state.smmCache[name] = data;
    } catch (e) {
      pane.innerHTML = `<div class="auth-error">Ошибка: ${escapeHtml(e.message)}</div>`;
    }
  }

  function renderArchetype(d) {
    if (!d) return '<div class="muted small">Нет данных.</div>';
    const doList = (d.do || []).map((x) => `<li>${escapeHtml(x)}</li>`).join("");
    const dontList = (d.dont || []).map((x) => `<li>${escapeHtml(x)}</li>`).join("");
    return `
      <div class="dep-smm-arch">
        <div class="dep-smm-arch-name">${escapeHtml(d.name || "")}</div>
        <div class="muted small">${escapeHtml(d.short || "")}</div>
        <div class="dep-smm-arch-voice">${escapeHtml(d.voice || "")}</div>
        <div class="dep-smm-arch-cols">
          <div>
            <div class="dep-smm-h">Делать</div>
            <ul>${doList}</ul>
          </div>
          <div>
            <div class="dep-smm-h">Не делать</div>
            <ul>${dontList}</ul>
          </div>
        </div>
        ${d.sample_post ? `<div class="dep-smm-sample"><div class="dep-smm-h">Образец поста</div>${escapeHtml(d.sample_post)}</div>` : ""}
      </div>
    `;
  }

  function renderAudit(d) {
    if (!d) return '<div class="muted small">Нет данных.</div>';
    if (d.state === "no_vk_handle") {
      return `
        <div class="dep-smm-empty">У депутата не указан VK handle. Привяжите страницу через «Изменение депутата».</div>
        ${(d.recommendations || []).map((r) => `<div class="dep-smm-rec">— ${escapeHtml(r)}</div>`).join("")}
      `;
    }
    if (d.state === "no_posts") {
      return `
        <div class="dep-smm-empty">Стена пуста или закрыта.</div>
        ${(d.recommendations || []).map((r) => `<div class="dep-smm-rec">— ${escapeHtml(r)}</div>`).join("")}
      `;
    }
    const m = d.metrics || {};
    const works = (d.what_works || []).map((q) => `<li>${escapeHtml(q)}</li>`).join("");
    const hurts = (d.what_hurts || []).map((q) => `<li>${escapeHtml(q)}</li>`).join("");
    const recs = (d.recommendations || []).map((r) => `<div class="dep-smm-rec">— ${escapeHtml(r)}</div>`).join("");
    const url = d.vk_url ? `<a href="${escapeHtml(d.vk_url)}" target="_blank" rel="noopener">${escapeHtml(d.vk_handle)}</a>` : "—";
    return `
      <div class="dep-smm-audit">
        <div class="dep-smm-row">VK: ${url}</div>
        <div class="dep-smm-row">Архетип: <strong>${escapeHtml(d.archetype_name || "")}</strong></div>
        <div class="dep-smm-row">Соответствие стилю: <strong>${d.alignment_score == null ? "—" : d.alignment_score + "%"}</strong> (${escapeHtml(d.alignment_label || "")})</div>
        <div class="dep-smm-row">Постов за 60 дней: ${m.posts_count ?? 0}, в неделю: ${m.posts_per_week ?? 0}, ср. длина: ${m.avg_length ?? 0} симв.</div>
        <div class="dep-smm-row">Среднее: ${m.avg_likes ?? 0} лайков · ${m.avg_views ?? 0} просмотров.</div>
        ${works ? `<div class="dep-smm-h">Что в стиле</div><ul>${works}</ul>` : ""}
        ${hurts ? `<div class="dep-smm-h">Что мешает</div><ul>${hurts}</ul>` : ""}
        <div class="dep-smm-h">Рекомендации</div>${recs}
      </div>
    `;
  }

  function renderPlan(d) {
    if (!d || !Array.isArray(d.items) || d.items.length === 0) {
      return '<div class="muted small">План не сформирован.</div>';
    }
    const items = d.items.map((it) => `
      <div class="dep-smm-plan-item">
        <div class="dep-smm-plan-day">${escapeHtml(it.day || "")}</div>
        <div class="dep-smm-plan-topic">${escapeHtml(it.topic || "")}</div>
        ${it.voice ? `<div class="muted small">${escapeHtml(it.voice)}</div>` : ""}
        ${it.draft ? `<div class="dep-smm-plan-draft">${escapeHtml(it.draft)}</div>` : ""}
      </div>
    `).join("");
    return `
      <div class="dep-smm-plan">
        <div class="muted small">Архетип: <strong>${escapeHtml(d.archetype_name || "")}</strong>${d.fallback ? " · шаблон без LLM" : ""}</div>
        <div class="muted small">Неделя: ${escapeHtml(d.week_of || "")}</div>
        ${items}
      </div>
    `;
  }

  async function generateSmmPost() {
    const id = state.smmDeputyId;
    if (!id) return;
    const req = $("dep-smm-post-request").value.trim();
    if (!req) {
      alert("Опишите тему поста.");
      return;
    }
    const out = $("dep-smm-post-result");
    out.innerHTML = '<div class="muted small">Генерирую…</div>';
    try {
      const data = await apiPost(`/deputies/${id}/content_post`, { request: req });
      out.innerHTML = `
        <div class="dep-smm-post-card">
          ${data.title ? `<div class="dep-smm-post-title">${escapeHtml(data.title)}</div>` : ""}
          <div class="dep-smm-post-body">${escapeHtml(data.body || "")}</div>
          ${data.cta ? `<div class="dep-smm-post-cta">${escapeHtml(data.cta)}</div>` : ""}
          <div class="muted small">Архетип: ${escapeHtml(data.archetype_name || "")}${data.fallback ? " · шаблон без LLM" : ""}</div>
        </div>
      `;
    } catch (e) {
      out.innerHTML = `<div class="auth-error">${escapeHtml(e.message)}</div>`;
    }
  }

  // -------------------------------------------- Auto-generation flow

  state.autogenCandidates = [];

  async function openAutogen() {
    const panel = $("autogen-panel");
    const list = $("autogen-list");
    const meta = $("autogen-meta");
    const empty = $("autogen-empty");
    const actions = $("autogen-actions");
    const errorBox = $("autogen-error");
    panel.hidden = false;
    empty.hidden = true;
    actions.hidden = true;
    errorBox.hidden = true;
    list.innerHTML = "";
    meta.textContent = "Сканируем метрики и жалобы…";
    state.autogenCandidates = [];

    try {
      const data = await apiPost("/deputy-topics/auto-generate", {
        dry_run: true,
        hours: 24,
        deadline_days: 5,
      });
      const candidates = data.candidates || [];
      state.autogenCandidates = candidates;
      const sigs = data.found_signals || {};
      meta.textContent =
        `Окно: 24 часа · Жалоб в окне: ${sigs.news_items_in_window ?? 0}` +
        ` · Метрики: ${sigs.metrics_present ? "есть" : "нет"}`;

      if (candidates.length === 0) {
        empty.hidden = false;
        return;
      }
      renderAutogenList(candidates);
      $("autogen-confirm-count").textContent = String(candidates.length);
      actions.hidden = false;
    } catch (e) {
      errorBox.textContent = `Не удалось получить кандидатов: ${e.message}`;
      errorBox.hidden = false;
    }
  }

  function renderAutogenList(candidates) {
    const list = $("autogen-list");
    list.innerHTML = "";
    for (const c of candidates) {
      const li = document.createElement("li");
      li.className = "autogen-item";
      const sectors = (c.target_sectors || []).map(esc).join(", ") || "—";
      const tps = (c.talking_points || []).slice(0, 3)
        .map((t) => `<li>${esc(t)}</li>`).join("");
      li.innerHTML = `
        <div class="autogen-item-head">
          <span class="autogen-priority autogen-pri-${esc(c.priority)}">${esc(priorityLabel(c.priority))}</span>
          <span class="autogen-source">${esc(sourceLabel(c.source))}</span>
        </div>
        <div class="autogen-title">${esc(c.title)}</div>
        <div class="autogen-desc">${esc(c.description || "")}</div>
        <div class="autogen-sectors muted small">Секторы: ${sectors}</div>
        ${tps ? `<ul class="autogen-tps muted small">${tps}</ul>` : ""}
      `;
      list.appendChild(li);
    }
  }

  function priorityLabel(p) {
    return ({ critical: "⚡ Критично", high: "❗ Важно", medium: "📋 План", low: "🗒 Отложено" })[p] || p;
  }

  function sourceLabel(s) {
    if (s === "auto_metrics")    return "Из метрик";
    if (s === "auto_complaints") return "Из жалоб";
    return s || "—";
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function closeAutogen() {
    $("autogen-panel").hidden = true;
    $("autogen-list").innerHTML = "";
    state.autogenCandidates = [];
  }

  async function confirmAutogen() {
    const errorBox = $("autogen-error");
    const confirmBtn = $("autogen-confirm");
    errorBox.hidden = true;
    confirmBtn.disabled = true;
    try {
      const data = await apiPost("/deputy-topics/auto-generate", {
        dry_run: false,
        hours: 24,
        deadline_days: 5,
      });
      const created = data.created || [];
      const dup = data.skipped_duplicate || 0;
      closeAutogen();
      await loadAll();
      const msg = `Создано тем: ${created.length}` + (dup ? ` · пропущено дубликатов: ${dup}` : "");
      // Показываем неблокирующий тост
      flashStatus(msg);
    } catch (e) {
      errorBox.textContent = `Не удалось записать темы: ${e.message}`;
      errorBox.hidden = false;
    } finally {
      confirmBtn.disabled = false;
    }
  }

  function flashStatus(msg) {
    const el = $("dep-meta");
    if (!el) return;
    const prev = el.textContent;
    el.textContent = `✓ ${msg}`;
    setTimeout(() => { el.textContent = prev; }, 4000);
  }

  // -------------------------------------------- Manual topic creation

  async function createTopic(ev) {
    ev.preventDefault();
    const days = parseInt($("t-deadline-days").value, 10) || 3;
    const deadline = new Date(Date.now() + days * 24 * 3600 * 1000).toISOString();
    const talking = $("t-talking").value
      .split(/\n+/)
      .map((s) => s.trim())
      .filter(Boolean);
    const body = {
      title: $("t-title").value.trim(),
      description: $("t-description").value.trim(),
      priority: $("t-priority").value,
      target_tone: $("t-tone").value,
      required_posts: parseInt($("t-required").value, 10) || 5,
      talking_points: talking,
      deadline,
    };
    try {
      await apiPost("/deputy-topics", body);
      $("topic-form").reset();
      $("topic-form-details").open = false;
      await loadAll();
    } catch (e) {
      const err = $("t-error");
      err.textContent = e.message;
      err.hidden = false;
    }
  }

  async function createDeputy(ev) {
    ev.preventDefault();
    const sectors = $("d-sectors").value
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const body = {
      name: $("d-name").value.trim(),
      role: $("d-role").value,
      district: $("d-district").value.trim() || null,
      party: $("d-party").value.trim() || null,
      sectors,
      telegram: $("d-telegram").value.trim() || null,
      vk: $("d-vk").value.trim() || null,
    };
    try {
      await apiPost("/deputies", body);
      $("dep-form").reset();
      $("dep-form-details").open = false;
      await loadAll();
    } catch (e) {
      const err = $("d-error");
      err.textContent = e.message;
      err.hidden = false;
    }
  }

  async function deleteDeputy(id) {
    if (!confirm("Удалить депутата?")) return;
    try {
      await apiDelete(`/deputies/${id}`);
      await loadAll();
    } catch (e) {
      alert("Ошибка удаления: " + e.message);
    }
  }

  async function autoAssign() {
    if (!state.currentTopic) return;
    try {
      await apiPost(`/deputy-topics/${state.currentTopic.id}/assign`, { auto: true, max_assignees: 5 });
      await loadAll();
      await openTopic(state.currentTopic.id);
    } catch (e) {
      alert("Ошибка авто-назначения: " + e.message);
    }
  }

  async function completeTopic() {
    if (!state.currentTopic) return;
    if (!confirm("Закрыть тему?")) return;
    try {
      await apiPost(`/deputy-topics/${state.currentTopic.id}/status`, { status: "completed" });
      $("topic-detail-card").hidden = true;
      await loadAll();
    } catch (e) {
      alert("Ошибка: " + e.message);
    }
  }

  async function generateDraft() {
    if (!state.currentTopic) return;
    const depId = parseInt($("td-draft-deputy").value, 10);
    if (!depId) {
      alert("Сначала назначьте депутатов на тему.");
      return;
    }
    try {
      const r = await apiPost(`/deputy-topics/${state.currentTopic.id}/draft`, { deputy_id: depId });
      const pre = $("td-draft");
      pre.textContent = `[${r.is_draft ? "ЧЕРНОВИК" : "READY"}] · ${r.note}\n\n` +
        `${r.suggested_text}\n\n` +
        `Тональность: ${r.tone}\nПлатформа: ${r.suggested_platform}\n` +
        `Тезисы:\n${r.talking_points.map((p) => "• " + p).join("\n")}\n` +
        `Хэштеги: ${r.hashtags.map((h) => "#" + h).join(" ")}`;
      pre.style.display = "block";
    } catch (e) {
      alert("Ошибка генерации черновика: " + e.message);
    }
  }

  // ---- tabs ----

  function showTopics() {
    $("topics-panel").hidden = false;
    $("deputies-panel").hidden = true;
    $("tab-topics").dataset.active = "1";
    $("tab-deputies").dataset.active = "0";
  }

  function showDeputies() {
    $("topics-panel").hidden = true;
    $("deputies-panel").hidden = false;
    $("tab-topics").dataset.active = "0";
    $("tab-deputies").dataset.active = "1";
  }

  // ---- auth modal ----

  function openLoginModal() {
    $("auth-modal").setAttribute("aria-hidden", "false");
    $("auth-modal").style.display = "flex";
  }

  function closeLoginModal() {
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
      closeLoginModal();
      await init();
    } catch (e) {
      err.textContent = e.message;
      err.hidden = false;
    }
  }

  // ---- init ----

  async function init() {
    state.user = await fetchMe();
    if (!isAllowed(state.user)) {
      $("dep-unauth").hidden = false;
      $("dep-content").hidden = true;
      $("auth-label").textContent = state.user ? state.user.email : "Войти";
      return;
    }
    $("dep-unauth").hidden = true;
    $("dep-content").hidden = false;
    $("auth-label").textContent = state.user.email;
    await loadAll();
  }

  document.addEventListener("DOMContentLoaded", () => {
    $("dep-refresh").addEventListener("click", loadAll);
    $("topic-form").addEventListener("submit", createTopic);
    $("dep-form").addEventListener("submit", createDeputy);
    $("topic-new-btn").addEventListener("click", () => { $("topic-form-details").open = true; });
    $("topic-autogen-btn").addEventListener("click", openAutogen);
    $("autogen-close").addEventListener("click", closeAutogen);
    $("autogen-cancel").addEventListener("click", closeAutogen);
    $("autogen-confirm").addEventListener("click", confirmAutogen);
    // SMM-табы в карточке депутата
    document.querySelectorAll('.dep-smm-tab').forEach((btn) =>
      btn.addEventListener("click", () => activateSmmTab(btn.dataset.smmTab)),
    );
    $("dep-smm-post-go")?.addEventListener("click", generateSmmPost);
    document.querySelectorAll('[data-card-close]').forEach((el) =>
      el.addEventListener("click", closeDeputyCard)
    );
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !$("dep-card").hidden) closeDeputyCard();
    });
    $("dep-new-btn").addEventListener("click", () => { $("dep-form-details").open = true; });
    $("td-close").addEventListener("click", () => { $("topic-detail-card").hidden = true; });
    $("td-auto-assign").addEventListener("click", autoAssign);
    $("td-complete").addEventListener("click", completeTopic);
    $("td-draft-btn").addEventListener("click", generateDraft);
    $("tab-topics").addEventListener("click", showTopics);
    $("tab-deputies").addEventListener("click", showDeputies);
    $("dep-login-btn").addEventListener("click", openLoginModal);
    $("auth-chip").addEventListener("click", openLoginModal);
    $("login-form").addEventListener("submit", doLogin);
    document.querySelectorAll('[data-dismiss]').forEach((el) =>
      el.addEventListener("click", closeLoginModal)
    );
    init();
  });
})();
