// =============================================================================
// Джарвис — голосовой ассистент города. Voice-only, без текстового ввода.
// FAB-орб пульсирует в углу. Через 10 секунд после первой загрузки страницы
// один раз за сессию здоровается голосом.
// =============================================================================

(function () {
  "use strict";

  const STORAGE_HISTORY = "jarvis.history";
  const STORAGE_VOICE_OFF = "jarvis.voiceOff";
  const STORAGE_IDENTITY = "jarvis.identity";
  const STORAGE_LAST_ALERT_ID = "jarvis.lastAlertId";
  const SESSION_GREETED = "jarvis.greeted";
  const GREETING_DELAY_MS = 10_000;
  const ALERTS_POLL_MS = 90_000;
  const MAX_HISTORY = 16;

  // Anonymous identity — persistent UUID, генерится один раз. Никаких PII.
  function getIdentity() {
    try {
      let id = localStorage.getItem(STORAGE_IDENTITY);
      if (id && id.length >= 16) return id;
      // Простой UUID-генератор без зависимостей
      const a = new Uint8Array(16);
      (window.crypto || window.msCrypto).getRandomValues(a);
      id = Array.from(a, (b) => b.toString(16).padStart(2, "0")).join("");
      localStorage.setItem(STORAGE_IDENTITY, id);
      return id;
    } catch (_) {
      return "";  // приватный режим — память отключена, ассистент работает
    }
  }

  const el = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));

  // ---------------------------------------------------------------------------
  // Markup
  // ---------------------------------------------------------------------------

  function injectMarkup() {
    if (el("jv-fab")) return;
    const wrap = document.createElement("div");
    wrap.innerHTML = `
      <button type="button" class="jv-fab" id="jv-fab" title="Поговорить с Джарвисом" aria-label="Активировать Джарвиса">
        <span class="jv-orb" aria-hidden="true">
          <span class="jv-orb-core"></span>
          <span class="jv-orb-ring"></span>
        </span>
        <span class="jv-fab-label">Джарвис</span>
      </button>

      <aside class="jv-panel" id="jv-panel" hidden role="dialog" aria-label="Джарвис">
        <header class="jv-head">
          <div>
            <div class="jv-eyebrow">Джарвис</div>
            <h2 class="jv-title" id="jv-title">Слушаю.</h2>
          </div>
          <div class="jv-head-controls">
            <button type="button" class="jv-icon-btn" id="jv-voice-toggle" title="Звук" aria-label="Звук">🔊</button>
            <button type="button" class="jv-icon-btn" id="jv-clear" title="Очистить" aria-label="Очистить">⟳</button>
            <button type="button" class="jv-close" id="jv-close" aria-label="Закрыть">×</button>
          </div>
        </header>

        <div class="jv-log" id="jv-log" aria-live="polite"></div>

        <div class="jv-mic-wrap">
          <button type="button" class="jv-mic" id="jv-mic" aria-label="Говорить">
            <span class="jv-mic-icon">🎙</span>
          </button>
          <div class="jv-hint" id="jv-hint">Нажмите и говорите.</div>
        </div>

        <!-- Уведомления через Max -->
        <details class="jv-notify" id="jv-notify">
          <summary>📨 Уведомления</summary>
          <div class="jv-notify-body" id="jv-notify-body">
            <div class="jv-notify-status" id="jv-notify-status">Загружаю…</div>
          </div>
        </details>

        <!-- SMM-аудит личной VK-страницы -->
        <details class="jv-notify jv-smm" id="jv-smm">
          <summary>📊 Мой SMM-аудит</summary>
          <div class="jv-notify-body" id="jv-smm-body">
            <div class="jv-notify-status">Загружаю…</div>
          </div>
        </details>
      </aside>

      <!-- Невидимый toast c приветствием при первом заходе -->
      <div class="jv-toast" id="jv-toast" hidden role="status" aria-live="polite">
        <span class="jv-toast-orb"></span>
        <span class="jv-toast-text" id="jv-toast-text">Я рядом.</span>
        <button type="button" class="jv-toast-close" id="jv-toast-close" aria-label="Скрыть">×</button>
      </div>
    `;
    document.body.appendChild(wrap);
  }

  // ---------------------------------------------------------------------------
  // Storage helpers
  // ---------------------------------------------------------------------------

  function loadHistory() {
    try {
      const raw = localStorage.getItem(STORAGE_HISTORY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed.slice(-MAX_HISTORY) : [];
    } catch (_) { return []; }
  }
  function saveHistory(arr) {
    try { localStorage.setItem(STORAGE_HISTORY, JSON.stringify(arr.slice(-MAX_HISTORY))); }
    catch (_) {}
  }
  function clearHistory() {
    try { localStorage.removeItem(STORAGE_HISTORY); } catch (_) {}
  }
  function voiceEnabled() {
    return localStorage.getItem(STORAGE_VOICE_OFF) !== "1";
  }
  function setVoiceEnabled(on) {
    if (on) localStorage.removeItem(STORAGE_VOICE_OFF);
    else localStorage.setItem(STORAGE_VOICE_OFF, "1");
  }
  function alreadyGreeted() {
    try { return sessionStorage.getItem(SESSION_GREETED) === "1"; }
    catch (_) { return false; }
  }
  function markGreeted() {
    try { sessionStorage.setItem(SESSION_GREETED, "1"); } catch (_) {}
  }

  // ---------------------------------------------------------------------------
  // City / TTS
  // ---------------------------------------------------------------------------

  function currentCityName() {
    if (window.currentCity?.name) return window.currentCity.name;
    if (typeof currentCity !== "undefined" && currentCity?.name) return currentCity.name;
    const slug = window.location.pathname.replace(/^\/+/, "").split("/")[0];
    if (slug && /^[a-z\-]+$/.test(slug)) return slug;
    return "Коломна";
  }

  function pickRussianVoice() {
    const synth = window.speechSynthesis;
    if (!synth) return null;
    const voices = synth.getVoices() || [];
    const sorted = voices.sort((a, b) => {
      const score = (v) => (
        (v.lang === "ru-RU" ? 100 : v.lang.startsWith("ru") ? 50 : 0) +
        (/Google|Yandex|Microsoft/i.test(v.name) ? 10 : 0)
      );
      return score(b) - score(a);
    });
    return sorted[0] || null;
  }

  let audioPlayer = null;
  function getAudioPlayer() {
    if (!audioPlayer) {
      audioPlayer = new Audio();
      audioPlayer.preload = "none";
    }
    return audioPlayer;
  }
  function playB64(b64, mime) {
    const p = getAudioPlayer();
    try { p.pause(); } catch (_) {}
    p.src = `data:${mime || "audio/mpeg"};base64,${b64}`;
    p.play().catch(() => {});
  }
  function speakBrowser(text) {
    const synth = window.speechSynthesis;
    if (!synth) return;
    try {
      synth.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = "ru-RU"; u.rate = 1.0; u.pitch = 1.0;
      const v = pickRussianVoice();
      if (v) u.voice = v;
      synth.speak(u);
    } catch (_) {}
  }
  function speak(text, fishPayload) {
    if (!voiceEnabled()) return;
    if (fishPayload && fishPayload.audio) {
      playB64(fishPayload.audio, fishPayload.audio_mime);
      return;
    }
    speakBrowser(text);
  }
  function stopSpeaking() {
    if (window.speechSynthesis) {
      try { window.speechSynthesis.cancel(); } catch (_) {}
    }
    if (audioPlayer) { try { audioPlayer.pause(); } catch (_) {} }
  }

  // ---------------------------------------------------------------------------
  // Bubble + status rendering
  // ---------------------------------------------------------------------------

  function addBubble(role, text, opts) {
    const log = el("jv-log");
    if (!log) return null;
    const div = document.createElement("div");
    div.className = `jv-bubble jv-${role}`;
    div.innerHTML = esc(text);
    if (opts && opts.action) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "jv-action-btn";
      btn.textContent = actionLabel(opts.action);
      btn.addEventListener("click", () => handleAction(opts.action));
      div.appendChild(btn);
    }
    if (role === "assistant") {
      const replay = document.createElement("button");
      replay.type = "button";
      replay.className = "jv-replay-btn";
      replay.title = "Озвучить ещё раз";
      replay.textContent = "▶";
      const fishPayload = (opts && opts.audio)
        ? { audio: opts.audio, audio_mime: opts.audio_mime } : null;
      replay.addEventListener("click", () => speak(text, fishPayload));
      div.appendChild(replay);
    }
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  function setStatus(msg) {
    const t = el("jv-title");
    if (t) t.textContent = msg;
    const h = el("jv-hint");
    if (h) h.textContent = msg;
  }

  function setOrbState(state) {
    // state: idle | listening | thinking | speaking
    const fab = el("jv-fab");
    const panel = el("jv-panel");
    [fab, panel].forEach((root) => {
      if (!root) return;
      root.dataset.state = state;
    });
  }

  function actionLabel(action) {
    return ({
      open_scenario:     "🎯 Сценарии",
      open_actions:      "✓ Действия",
      open_topic:        "🗂 Тема",
      open_admin:        "⚙️ Админка",
      open_deputies:     "🏛 Депутаты",
      show_chart:        "📊 График",
      run_pulse:         "💓 Пульс",
      run_forecast:      "🔮 Прогноз",
      run_crisis:        "🚨 Кризис",
      run_loops:         "🧠 Петли",
      run_benchmark:     "📊 Сравнить",
      run_topics:        "🗂 Темы",
      run_deputy_topics: "📝 Темы депутатам",
    })[action] || "Запустить";
  }

  async function handleAction(action) {
    if (action.startsWith("open_") || action === "show_chart") {
      switch (action) {
        case "open_scenario": document.getElementById("btn-scenario")?.click(); break;
        case "open_actions":  document.getElementById("btn-actions")?.click(); break;
        case "open_admin":    window.location.href = "/admin.html"; break;
        case "open_deputies":
        case "open_topic":    window.location.href = "/deputies.html"; break;
        case "show_chart":
          document.querySelector(".forecast, .deep-forecast, .history")?.scrollIntoView({
            behavior: "smooth", block: "start",
          });
      }
      return;
    }
    if (action.startsWith("run_")) {
      setOrbState("thinking");
      setStatus("Считаю…");
      try {
        const res = await fetch("/api/copilot/execute", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action, city: currentCityName(), speak: voiceEnabled() }),
        });
        if (!res.ok) {
          addBubble("assistant", `Расчёт не удался (${res.status}).`);
          setOrbState("idle"); setStatus("Готов.");
          return;
        }
        const data = await res.json();
        const reply = data.text || "Готово.";
        addBubble("assistant", reply, {
          action: null, audio: data.audio || null, audio_mime: data.audio_mime || null,
        });
        const updated = loadHistory();
        updated.push({ role: "assistant", text: reply });
        saveHistory(updated);
        if (voiceEnabled()) {
          setOrbState("speaking");
          speak(reply, { audio: data.audio, audio_mime: data.audio_mime });
        }
        setStatus("Готов.");
        setTimeout(() => setOrbState("idle"), 5000);
      } catch (_) {
        addBubble("assistant", "Связь дрогнула.");
        setOrbState("idle"); setStatus("Сеть недоступна.");
      }
    }
  }

  // ---------------------------------------------------------------------------
  // STT — SpeechRecognition
  // ---------------------------------------------------------------------------

  let recognition = null;
  let recognising = false;

  function setupRecognition() {
    const Klass = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Klass) return null;
    const r = new Klass();
    r.lang = "ru-RU"; r.interimResults = true; r.continuous = false;
    r.maxAlternatives = 1;
    return r;
  }

  function startRecognition() {
    if (recognising) { stopRecognition(); return; }
    if (!recognition) recognition = setupRecognition();
    if (!recognition) {
      setStatus("Голосовой ввод не поддерживается этим браузером.");
      return;
    }
    stopSpeaking();
    let finalText = "";
    recognition.onresult = (ev) => {
      let interim = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const r = ev.results[i];
        if (r.isFinal) finalText += r[0].transcript;
        else interim += r[0].transcript;
      }
      const txt = (finalText + interim).trim();
      if (txt) setStatus(txt);
    };
    recognition.onerror = (e) => {
      setStatus(e.error === "not-allowed"
        ? "Доступ к микрофону отклонён."
        : `Сбой распознавания: ${e.error}`);
      finishRec();
    };
    recognition.onend = () => {
      finishRec();
      const txt = finalText.trim();
      if (txt) {
        addBubble("user", txt);
        sendToCopilot(txt);
      } else {
        setStatus("Не уловил, скажите ещё раз.");
      }
    };
    try {
      recognition.start();
      recognising = true;
      setOrbState("listening");
      setStatus("Слушаю…");
    } catch (_) {
      setStatus("Не удалось запустить запись.");
    }

    function finishRec() {
      recognising = false;
      setOrbState("idle");
    }
  }

  function stopRecognition() {
    if (!recognising || !recognition) return;
    try { recognition.stop(); } catch (_) {}
  }

  // ---------------------------------------------------------------------------
  // POST /api/copilot/chat
  // ---------------------------------------------------------------------------

  async function sendToCopilot(text) {
    setOrbState("thinking");
    setStatus("Думаю…");
    const history = loadHistory();
    history.push({ role: "user", text });
    saveHistory(history);
    try {
      const res = await fetch("/api/copilot/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text, city: currentCityName(),
          history: history.slice(-8, -1), speak: voiceEnabled(),
          identity: getIdentity(),
        }),
      });
      if (!res.ok) {
        addBubble("assistant", `Ошибка ${res.status}.`);
        setOrbState("idle"); setStatus("Сбой сети.");
        return;
      }
      const data = await res.json();
      const reply = data.text || "…";
      addBubble("assistant", reply, {
        action: data.action || null,
        audio: data.audio || null, audio_mime: data.audio_mime || null,
      });
      const upd = loadHistory();
      upd.push({ role: "assistant", text: reply });
      saveHistory(upd);
      if (voiceEnabled()) {
        setOrbState("speaking");
        speak(reply, { audio: data.audio, audio_mime: data.audio_mime });
      }
      setStatus("Слушаю.");
      setTimeout(() => setOrbState("idle"), 5000);
    } catch (_) {
      addBubble("assistant", "Связь дрогнула.");
      setOrbState("idle"); setStatus("Сеть недоступна.");
    }
  }

  // ---------------------------------------------------------------------------
  // Проактивность — polling /alerts каждые 90s
  // ---------------------------------------------------------------------------

  function getLastAlertId() {
    try { return parseInt(localStorage.getItem(STORAGE_LAST_ALERT_ID) || "0", 10) || 0; }
    catch (_) { return 0; }
  }
  function setLastAlertId(id) {
    try { localStorage.setItem(STORAGE_LAST_ALERT_ID, String(id || 0)); } catch (_) {}
  }

  async function pollAlerts() {
    try {
      const since = getLastAlertId();
      const url = `/api/copilot/alerts?city=${encodeURIComponent(currentCityName())}&since_id=${since}&limit=5`;
      const res = await fetch(url);
      if (!res.ok) return;
      const data = await res.json();
      const alerts = data.alerts || [];
      if (alerts.length === 0) return;
      // Показываем только самый «громкий» — критический раньше warning'а.
      const sorted = alerts.slice().sort((a, b) => {
        const w = (lvl) => ({ critical: 3, warning: 2, info: 1 })[lvl] || 0;
        return w(b.level) - w(a.level);
      });
      const top = sorted[0];
      if (top) announceAlert(top);
      setLastAlertId(data.max_id || alerts[alerts.length - 1].id);
    } catch (_) {
      // тихо игнорируем — следующий тик попробует ещё раз
    }
  }

  function announceAlert(alert) {
    const text = alert.title + (alert.summary ? ". " + alert.summary : "");
    showToast(`⚠ ${text}`);
    if (voiceEnabled()) {
      // Префикс «Я заметил…» — голос Джарвиса как смотрящего.
      const said = `Я заметил: ${alert.title.toLowerCase()}.`
        + (alert.summary ? " " + alert.summary : "");
      speak(said);
    }
  }

  // ---------------------------------------------------------------------------
  // Уведомления через Max
  // ---------------------------------------------------------------------------

  const PREF_LABELS = {
    critical:    "Критичные алерты по городу",
    daily_brief: "Утренняя сводка дня",
    topics:      "Новые темы для депутатов",
  };

  async function loadMaxStatus() {
    const id = getIdentity();
    if (!id) return null;
    try {
      const r = await fetch(`/api/max/status?identity=${encodeURIComponent(id)}`);
      if (!r.ok) return null;
      return await r.json();
    } catch (_) {
      return null;
    }
  }

  function renderMaxStatus(s) {
    const body = el("jv-notify-body");
    if (!body) return;
    if (!s || !s.configured) {
      body.innerHTML = `<div class="jv-notify-status muted">Канал Max не настроен на сервере.</div>`;
      return;
    }
    if (!s.linked) {
      const link = s.deeplink;
      body.innerHTML = `
        <div class="jv-notify-status">Привяжите Max — и я буду писать о критичных событиях.</div>
        ${link ? `<a class="jv-notify-link" href="${link}" target="_blank" rel="noopener">Открыть бота в Max</a>` : ""}
        <button type="button" class="jv-notify-recheck" id="jv-notify-recheck">Я нажал «Старт»</button>
      `;
      el("jv-notify-recheck")?.addEventListener("click", refreshMaxSection);
      return;
    }
    const prefs = s.prefs || {};
    const checks = Object.keys(PREF_LABELS).map((k) => `
      <label class="jv-notify-check">
        <input type="checkbox" data-pref="${k}" ${prefs[k] ? "checked" : ""} />
        <span>${esc(PREF_LABELS[k])}</span>
      </label>
    `).join("");
    body.innerHTML = `
      <div class="jv-notify-status">Привязано${s.user_name ? `: ${esc(s.user_name)}` : ""}.</div>
      <div class="jv-notify-prefs">${checks}</div>
      <button type="button" class="jv-notify-unlink" id="jv-notify-unlink">Отвязать</button>
    `;
    body.querySelectorAll('input[data-pref]').forEach((inp) => {
      inp.addEventListener("change", onPrefChange);
    });
    el("jv-notify-unlink")?.addEventListener("click", onUnlink);
  }

  async function onPrefChange(ev) {
    const id = getIdentity();
    if (!id) return;
    const inp = ev.currentTarget;
    const prefs = {};
    document.querySelectorAll('#jv-notify-body input[data-pref]').forEach((c) => {
      prefs[c.dataset.pref] = !!c.checked;
    });
    try {
      await fetch("/api/max/prefs", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identity: id, prefs }),
      });
    } catch (_) {
      // Откатываем чекбокс при ошибке
      inp.checked = !inp.checked;
    }
  }

  async function onUnlink() {
    const id = getIdentity();
    if (!id) return;
    try {
      await fetch("/api/max/unlink", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identity: id }),
      });
    } catch (_) {}
    refreshMaxSection();
  }

  async function refreshMaxSection() {
    const status = await loadMaxStatus();
    renderMaxStatus(status);
  }

  // ---------------------------------------------------------------------------
  // SMM-аудит — личная VK-страница пользователя
  // ---------------------------------------------------------------------------

  let smmArchetypesCache = null;
  let smmLastAudit = null;

  async function loadSmmStatus() {
    const id = getIdentity();
    if (!id) return null;
    try {
      const r = await fetch(`/api/copilot/vk/status?identity=${encodeURIComponent(id)}`);
      if (!r.ok) return null;
      return await r.json();
    } catch (_) { return null; }
  }

  async function loadArchetypes() {
    if (smmArchetypesCache) return smmArchetypesCache;
    try {
      const r = await fetch("/api/copilot/vk/archetypes");
      if (!r.ok) return [];
      const data = await r.json();
      smmArchetypesCache = data.archetypes || [];
      return smmArchetypesCache;
    } catch (_) { return []; }
  }

  function renderSmmUnlinked(archetypes) {
    const opts = ['<option value="">— подбери автоматически —</option>']
      .concat(archetypes.map((a) =>
        `<option value="${esc(a.code)}">${esc(a.name)} — ${esc(a.short)}</option>`
      )).join("");
    return `
      <div class="jv-notify-status">Привяжи свою VK-страницу — оценю стиль и подскажу, что улучшить.</div>
      <input type="text" class="jv-smm-input" id="jv-smm-handle"
             placeholder="vk.com/ivanov или ivanov" autocomplete="off" />
      <select class="jv-smm-select" id="jv-smm-archetype">${opts}</select>
      <button type="button" class="jv-smm-btn primary" id="jv-smm-link">Привязать</button>
    `;
  }

  function renderSmmLinked(s) {
    const last = s.last_audit_at
      ? new Date(s.last_audit_at).toLocaleDateString("ru-RU",
          { day: "numeric", month: "short" })
      : null;
    return `
      <div class="jv-notify-status">
        Привязано: <a class="jv-smm-link" href="${esc(s.vk_url)}"
          target="_blank" rel="noopener">${esc(s.vk_handle)}</a>
        ${last ? `<span class="muted"> · аудит ${esc(last)}</span>` : ""}
      </div>
      <button type="button" class="jv-smm-btn primary" id="jv-smm-audit">Запустить аудит</button>
      <button type="button" class="jv-notify-unlink" id="jv-smm-unlink">Отвязать</button>
      <div class="jv-smm-result" id="jv-smm-result"></div>
    `;
  }

  function renderSmmAudit(out) {
    if (!out) return "";
    if (out.state === "no_posts") {
      return `
        <div class="jv-smm-section">
          <div class="jv-smm-status">Стена пустая или закрытая.</div>
          <ul class="jv-smm-recs">
            ${(out.recommendations || []).map((r) => `<li>${esc(r)}</li>`).join("")}
          </ul>
        </div>
      `;
    }
    const m = out.metrics || {};
    const score = out.alignment_score;
    const label = out.alignment_label || "—";
    const arch = out.archetype_name || "—";
    return `
      <div class="jv-smm-section">
        <div class="jv-smm-score">
          <span class="jv-smm-score-num">${score == null ? "—" : score}</span>
          <span class="jv-smm-score-lbl">${esc(label)}</span>
          <span class="jv-smm-score-arch">голос «${esc(arch)}»</span>
        </div>
        <div class="jv-smm-metrics">
          <span>📝 ${m.posts_count ?? 0} постов</span>
          <span>📅 ${m.posts_per_week ?? 0}/нед</span>
          <span>📏 ~${m.avg_length ?? 0} симв</span>
          <span>👍 ${m.avg_likes ?? 0}</span>
        </div>
        <div class="jv-smm-recs-title">Что улучшить</div>
        <ul class="jv-smm-recs">
          ${(out.recommendations || []).map((r) => `<li>${esc(r)}</li>`).join("")}
        </ul>
        ${(out.what_works && out.what_works.length) ? `
          <div class="jv-smm-recs-title">В голосе</div>
          <ul class="jv-smm-quotes">
            ${out.what_works.map((q) => `<li>«${esc(q)}…»</li>`).join("")}
          </ul>` : ""}
        ${(out.what_hurts && out.what_hurts.length) ? `
          <div class="jv-smm-recs-title">Размывает голос</div>
          <ul class="jv-smm-quotes">
            ${out.what_hurts.map((q) => `<li>«${esc(q)}…»</li>`).join("")}
          </ul>` : ""}
      </div>
    `;
  }

  async function refreshSmmSection() {
    const body = el("jv-smm-body");
    if (!body) return;
    body.innerHTML = `<div class="jv-notify-status">Загружаю…</div>`;
    const [status, archetypes] = await Promise.all([
      loadSmmStatus(), loadArchetypes(),
    ]);
    if (!status || !status.linked) {
      body.innerHTML = renderSmmUnlinked(archetypes);
      el("jv-smm-link")?.addEventListener("click", onSmmLink);
      return;
    }
    body.innerHTML = renderSmmLinked(status);
    el("jv-smm-audit")?.addEventListener("click", onSmmAudit);
    el("jv-smm-unlink")?.addEventListener("click", onSmmUnlink);
    // Если уже делали аудит в этой сессии — показываем результат сразу
    if (smmLastAudit) {
      const r = el("jv-smm-result");
      if (r) r.innerHTML = renderSmmAudit(smmLastAudit);
    }
  }

  async function onSmmLink() {
    const id = getIdentity();
    if (!id) return;
    const inp = el("jv-smm-handle");
    const sel = el("jv-smm-archetype");
    const handle = (inp?.value || "").trim();
    if (!handle) {
      setStatus("Введи VK-ссылку или screen_name.");
      return;
    }
    const btn = el("jv-smm-link");
    if (btn) { btn.disabled = true; btn.textContent = "Привязываю…"; }
    try {
      const res = await fetch("/api/copilot/vk/link", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          identity: id, vk_handle: handle,
          archetype: sel?.value || null,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        setStatus(detail.detail || "Не получилось привязать.");
        if (btn) { btn.disabled = false; btn.textContent = "Привязать"; }
        return;
      }
      smmLastAudit = null;
      refreshSmmSection();
    } catch (_) {
      setStatus("Сеть недоступна.");
      if (btn) { btn.disabled = false; btn.textContent = "Привязать"; }
    }
  }

  async function onSmmUnlink() {
    const id = getIdentity();
    if (!id) return;
    try {
      await fetch("/api/copilot/vk/unlink", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identity: id }),
      });
    } catch (_) {}
    smmLastAudit = null;
    refreshSmmSection();
  }

  async function onSmmAudit() {
    const id = getIdentity();
    if (!id) return;
    const btn = el("jv-smm-audit");
    const result = el("jv-smm-result");
    if (btn) { btn.disabled = true; btn.textContent = "Анализирую…"; }
    if (result) result.innerHTML = `<div class="jv-notify-status">Читаю стену, считаю метрики…</div>`;
    try {
      const res = await fetch("/api/copilot/vk/audit", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identity: id }),
      });
      if (!res.ok) {
        if (result) result.innerHTML = `<div class="jv-notify-status">Аудит не удался (${res.status}).</div>`;
        return;
      }
      const data = await res.json();
      smmLastAudit = data;
      if (result) result.innerHTML = renderSmmAudit(data);
    } catch (_) {
      if (result) result.innerHTML = `<div class="jv-notify-status">Сеть недоступна.</div>`;
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Перезапустить аудит"; }
    }
  }

  // ---------------------------------------------------------------------------
  // Greeting (через 10 секунд после первой загрузки за сессию)
  // ---------------------------------------------------------------------------

  async function greet() {
    if (alreadyGreeted()) return;
    markGreeted();   // помечаем сразу, чтобы не зациклить при ошибке
    let payload = null;
    try {
      const res = await fetch("/api/copilot/greeting");
      if (res.ok) payload = await res.json();
    } catch (_) {}
    const text = (payload && payload.text)
      || "Я Джарвис, ваш помощник по городу. Я рядом, в фоне.";
    showToast(text);
    if (voiceEnabled()) speak(text, payload);
  }

  function showToast(text) {
    const t = el("jv-toast");
    const tt = el("jv-toast-text");
    if (!t || !tt) return;
    tt.textContent = text;
    t.hidden = false;
    setTimeout(() => { t.hidden = true; }, 12_000);
  }

  // ---------------------------------------------------------------------------
  // Open / close / wire
  // ---------------------------------------------------------------------------

  function openPanel() {
    const p = el("jv-panel");
    if (!p) return;
    p.hidden = false;
    if (el("jv-log").children.length === 0) {
      const h = loadHistory();
      if (h.length === 0) {
        addBubble("assistant",
          "Я рядом. Нажмите микрофон и спросите — про метрики, прогноз, депутатов, что угодно.");
      } else {
        h.forEach((turn) => addBubble(turn.role, turn.text));
      }
    }
    refreshVoiceToggle();
    setStatus("Готов слушать.");
    setOrbState("idle");
    // Подгрузка состояния Max-подписки — асинхронно, не блокирует UI
    refreshMaxSection();
    refreshSmmSection();
  }

  function closePanel() {
    const p = el("jv-panel");
    if (p) p.hidden = true;
    stopRecognition();
    stopSpeaking();
    setOrbState("idle");
  }

  function refreshVoiceToggle() {
    const btn = el("jv-voice-toggle");
    if (!btn) return;
    btn.textContent = voiceEnabled() ? "🔊" : "🔇";
    btn.title = voiceEnabled() ? "Выключить звук" : "Включить звук";
  }

  function wire() {
    el("jv-fab")?.addEventListener("click", openPanel);
    el("jv-close")?.addEventListener("click", closePanel);
    el("jv-mic")?.addEventListener("click", startRecognition);
    el("jv-voice-toggle")?.addEventListener("click", () => {
      setVoiceEnabled(!voiceEnabled());
      refreshVoiceToggle();
      if (!voiceEnabled()) stopSpeaking();
    });
    el("jv-clear")?.addEventListener("click", async () => {
      clearHistory();
      // Сервер тоже забывает про этого собеседника — fire-and-forget
      const id = getIdentity();
      if (id) {
        try {
          await fetch("/api/copilot/forget", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ identity: id }),
          });
        } catch (_) {}
      }
      const log = el("jv-log");
      if (log) log.innerHTML = "";
      addBubble("assistant", "Память очищена. Я готов.");
    });
    el("jv-toast-close")?.addEventListener("click", () => {
      const t = el("jv-toast"); if (t) t.hidden = true;
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !el("jv-panel")?.hidden) closePanel();
    });
    // У некоторых браузеров getVoices() пустой пока не сработал voiceschanged
    if (window.speechSynthesis) {
      window.speechSynthesis.onvoiceschanged = () => {};
    }
    // Без SpeechRecognition нет смысла открывать панель — но FAB всё
    // равно покажем, чтобы пользователь увидел Джарвиса.
    const Klass = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Klass) {
      const m = el("jv-mic"); const h = el("jv-hint");
      if (m) m.disabled = true;
      if (h) h.textContent = "Голосовой ввод не поддерживается. Откройте Chrome / Edge / Yandex Browser.";
    }
  }

  function init() {
    injectMarkup();
    wire();
    // Авто-приветствие через 10 секунд после первой загрузки за сессию.
    if (!alreadyGreeted()) {
      setTimeout(() => { greet(); }, GREETING_DELAY_MS);
    }
    // Проактивность: первый poll через 30s после загрузки (даём загрузиться
    // дашборду), потом каждые 90s.
    setTimeout(() => {
      pollAlerts();
      setInterval(pollAlerts, ALERTS_POLL_MS);
    }, 30_000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
