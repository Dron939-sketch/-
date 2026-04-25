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
        <div class="user-row">
          <strong>${escapeHtml(d.name)}</strong>
          <span class="muted small" style="margin-left:0.5rem;">${escapeHtml(d.role)} · ${escapeHtml(d.district || "—")} · ${escapeHtml(d.party || "—")}</span>
          <span class="muted small" style="display:block;">Сектора: ${escapeHtml(sectors)}</span>
        </div>
        <button type="button" class="admin-close-user" data-dep-id="${d.id}" title="Удалить">🗑️</button>
      `;
      li.querySelector("button[data-dep-id]").addEventListener("click", () => deleteDeputy(d.id));
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
