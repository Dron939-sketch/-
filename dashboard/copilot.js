// =============================================================================
// Голосовой Ко-пилот — универсальный виджет (главная / админка / депутаты).
// Использует браузерный SpeechRecognition (где доступен) для STT и
// speechSynthesis для TTS. На сервер ходит только за контекстным ответом —
// /api/copilot/chat. Никаких внешних зависимостей, IIFE.
// =============================================================================

(function () {
  "use strict";

  const STORAGE_HISTORY = "cityCopilot.history";
  const STORAGE_VOICE_OFF = "cityCopilot.voiceOff";
  const MAX_HISTORY = 16;

  const el = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));

  // ---------------------------------------------------------------------------
  // Markup — вставляется в DOM один раз при load.
  // ---------------------------------------------------------------------------

  function injectMarkup() {
    if (el("cp-fab")) return;
    const wrap = document.createElement("div");
    wrap.innerHTML = `
      <button type="button" class="cp-fab" id="cp-fab" title="Голосовой Ко-пилот" aria-label="Открыть Ко-пилота">
        <span class="cp-fab-icon" aria-hidden="true">🤖</span>
      </button>
      <aside class="cp-panel" id="cp-panel" hidden role="dialog" aria-label="Голосовой Ко-пилот">
        <header class="cp-head">
          <div>
            <div class="cp-eyebrow">Голосовой Ко-пилот</div>
            <h2 class="cp-title">Аналитический ассистент</h2>
          </div>
          <div class="cp-head-controls">
            <button type="button" class="cp-icon-btn" id="cp-voice-toggle" title="Включить/выключить озвучку" aria-label="Озвучка">🔊</button>
            <button type="button" class="cp-icon-btn" id="cp-clear" title="Очистить историю" aria-label="Очистить">🗑</button>
            <button type="button" class="cp-close" id="cp-close" aria-label="Закрыть">&times;</button>
          </div>
        </header>
        <div class="cp-log" id="cp-log" aria-live="polite"></div>
        <div class="cp-typing" id="cp-typing" hidden>
          <span></span><span></span><span></span>
        </div>
        <div class="cp-input-row">
          <input type="text" id="cp-text" placeholder="Спросите Ко-пилота…" autocomplete="off" />
          <button type="button" class="cp-send" id="cp-send" title="Отправить">→</button>
          <button type="button" class="cp-mic" id="cp-mic" title="Голосовой ввод" aria-label="Микрофон">🎙</button>
        </div>
        <div class="muted small cp-hint" id="cp-hint">🎙 голос или Enter для текста.</div>
      </aside>
    `;
    document.body.appendChild(wrap);
  }

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  function loadHistory() {
    try {
      const raw = localStorage.getItem(STORAGE_HISTORY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
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

  function pickRussianVoice() {
    const synth = window.speechSynthesis;
    if (!synth) return null;
    const voices = synth.getVoices() || [];
    // Предпочитаем Google русский / Yandex / Microsoft Irina / любой ru-RU
    const sorted = voices.sort((a, b) => {
      const score = (v) => (
        (v.lang === "ru-RU" ? 100 : v.lang.startsWith("ru") ? 50 : 0) +
        (/Google|Yandex|Microsoft/i.test(v.name) ? 10 : 0)
      );
      return score(b) - score(a);
    });
    return sorted[0] || null;
  }

  // ---------------------------------------------------------------------------
  // Determine current city slug from URL or window.currentCity
  // ---------------------------------------------------------------------------

  function currentCityName() {
    if (window.currentCity?.name) return window.currentCity.name;
    if (typeof currentCity !== "undefined" && currentCity?.name) return currentCity.name;
    // URL slug fallback (if dashboard.js не успел инициализироваться)
    const slug = window.location.pathname.replace(/^\/+/, "").split("/")[0];
    if (slug && /^[a-z\-]+$/.test(slug)) return slug;
    return "Коломна";
  }

  // ---------------------------------------------------------------------------
  // UI rendering
  // ---------------------------------------------------------------------------

  function addBubble(role, text, opts) {
    const log = el("cp-log");
    if (!log) return null;
    const div = document.createElement("div");
    div.className = `cp-bubble cp-${role}`;
    div.innerHTML = esc(text);
    if (opts && opts.action) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "cp-action-btn";
      btn.textContent = actionLabel(opts.action);
      btn.addEventListener("click", () => handleAction(opts.action));
      div.appendChild(btn);
    }
    if (opts && Array.isArray(opts.sources) && opts.sources.length > 0) {
      const ul = document.createElement("ul");
      ul.className = "cp-sources";
      opts.sources.slice(0, 5).forEach((s) => {
        const li = document.createElement("li");
        li.textContent = s;
        ul.appendChild(li);
      });
      div.appendChild(ul);
    }
    if (role === "assistant") {
      const replay = document.createElement("button");
      replay.type = "button";
      replay.className = "cp-replay-btn";
      replay.title = "Озвучить ещё раз";
      replay.textContent = "▶";
      // Сохраняем MP3 на bubble чтобы replay использовал тот же Fish-аудио
      // вместо повторного запроса синтеза.
      const fishPayload = (opts && opts.audio)
        ? { audio: opts.audio, audio_mime: opts.audio_mime }
        : null;
      replay.addEventListener("click", () => speak(text, fishPayload));
      div.appendChild(replay);
    }
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  function showTyping(on) {
    const t = el("cp-typing");
    if (!t) return;
    t.hidden = !on;
    if (on) {
      const log = el("cp-log");
      if (log) log.scrollTop = log.scrollHeight;
    }
  }

  function setHint(msg) {
    const h = el("cp-hint");
    if (h) h.textContent = msg;
  }

  function actionLabel(action) {
    return ({
      open_scenario:     "🎯 Открыть сценарии",
      open_actions:      "✓ Открыть генератор действий",
      open_topic:        "🗂 Открыть тему",
      open_admin:        "⚙️ Открыть админку",
      open_deputies:     "🏛 Открыть депутатов",
      show_chart:        "📊 Показать график",
      run_pulse:         "💓 Посчитать пульс",
      run_forecast:      "🔮 Прогноз на 30 дней",
      run_crisis:        "🚨 Кризис-радар",
      run_loops:         "🧠 Петли Мейстера",
      run_benchmark:     "📊 Сравнить с другими",
      run_topics:        "🗂 Топ тематик",
      run_deputy_topics: "📝 Темы депутатам",
    })[action] || "Выполнить";
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
          break;
      }
      return;
    }
    if (action.startsWith("run_")) {
      // Прямое выполнение через /api/copilot/execute — ответ как обычный bubble.
      showTyping(true);
      setHint("Считаю…");
      try {
        const res = await fetch("/api/copilot/execute", {
          method:  "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action, city: currentCityName(), speak: voiceEnabled() }),
        });
        showTyping(false);
        if (!res.ok) {
          addBubble("assistant", `Расчёт не удался (${res.status}).`);
          setHint("Ошибка.");
          return;
        }
        const data = await res.json();
        const reply = data.text || "Готово.";
        addBubble("assistant", reply, {
          action: null, sources: data.sources || [],
          audio: data.audio || null, audio_mime: data.audio_mime || null,
        });
        const updated = loadHistory();
        updated.push({ role: "assistant", text: reply });
        saveHistory(updated);
        if (voiceEnabled()) speak(reply, { audio: data.audio, audio_mime: data.audio_mime });
        setHint("Готово.");
      } catch (e) {
        showTyping(false);
        addBubble("assistant", "Связь дрогнула при расчёте.");
        setHint("Сеть недоступна.");
      }
    }
  }

  // ---------------------------------------------------------------------------
  // TTS — Fish Audio (MP3) с fallback на browser speechSynthesis
  // ---------------------------------------------------------------------------

  let audioPlayer = null;
  function getAudioPlayer() {
    if (!audioPlayer) {
      audioPlayer = new Audio();
      audioPlayer.preload = "none";
    }
    return audioPlayer;
  }

  function playAudioFromBase64(b64, mime) {
    const player = getAudioPlayer();
    try { player.pause(); } catch (_) {}
    player.src = `data:${mime || "audio/mpeg"};base64,${b64}`;
    player.play().catch(() => {
      // Автоплей заблокирован — это редко, но бывает на iOS до взаимодействия.
      // В этом случае просто ничего не делаем, пользователь нажмёт ▶.
    });
  }

  function speakBrowser(text) {
    const synth = window.speechSynthesis;
    if (!synth) return;
    try {
      synth.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = "ru-RU";
      u.rate = 1.0;
      u.pitch = 1.0;
      const v = pickRussianVoice();
      if (v) u.voice = v;
      synth.speak(u);
    } catch (_) {}
  }

  // speak(text, fishPayload?) — если бэкенд вернул MP3, играем его;
  // иначе — браузерный синтезатор. Используется и при autoplay ответа,
  // и при клике ▶ (replay) — без MP3-payload играем заново через synth.
  function speak(text, fishPayload) {
    if (!voiceEnabled()) return;
    if (fishPayload && fishPayload.audio) {
      playAudioFromBase64(fishPayload.audio, fishPayload.audio_mime);
      return;
    }
    speakBrowser(text);
  }

  function stopSpeaking() {
    if (window.speechSynthesis) {
      try { window.speechSynthesis.cancel(); } catch (_) {}
    }
    if (audioPlayer) {
      try { audioPlayer.pause(); } catch (_) {}
    }
  }

  // ---------------------------------------------------------------------------
  // STT — SpeechRecognition (где доступен)
  // ---------------------------------------------------------------------------

  let recognition = null;
  let recognising = false;

  function setupRecognition() {
    const Klass = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Klass) return null;
    const r = new Klass();
    r.lang = "ru-RU";
    r.interimResults = true;
    r.continuous = false;
    r.maxAlternatives = 1;
    return r;
  }

  function startRecognition() {
    if (recognising) return stopRecognition();
    if (!recognition) recognition = setupRecognition();
    if (!recognition) {
      setHint("Голосовой ввод не поддерживается в этом браузере.");
      return;
    }
    stopSpeaking();
    const input = el("cp-text");
    const mic = el("cp-mic");
    let finalText = "";
    recognition.onresult = (ev) => {
      let interim = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const res = ev.results[i];
        if (res.isFinal) finalText += res[0].transcript;
        else interim += res[0].transcript;
      }
      if (input) input.value = (finalText + interim).trim();
    };
    recognition.onerror = (e) => {
      setHint(e.error === "not-allowed"
        ? "Доступ к микрофону отклонён."
        : `Ошибка распознавания: ${e.error}`);
      stopRecognition();
    };
    recognition.onend = () => {
      recognising = false;
      if (mic) { mic.classList.remove("cp-mic-active"); mic.textContent = "🎙"; }
      if (finalText.trim()) {
        // Auto-send 500ms после конца речи (как в ТЗ)
        setTimeout(sendText, 500);
      } else {
        setHint("Я не уловила. Попробуйте ещё.");
      }
    };
    try {
      recognition.start();
      recognising = true;
      if (mic) { mic.classList.add("cp-mic-active"); mic.textContent = "■"; }
      setHint("Слушаю… говорите.");
    } catch (e) {
      setHint("Не удалось запустить запись.");
    }
  }

  function stopRecognition() {
    if (!recognising || !recognition) return;
    try { recognition.stop(); } catch (_) {}
  }

  // ---------------------------------------------------------------------------
  // Send to backend
  // ---------------------------------------------------------------------------

  async function sendText() {
    const input = el("cp-text");
    const text = (input?.value || "").trim();
    if (!text) return;
    addBubble("user", text);
    if (input) input.value = "";

    const history = loadHistory();
    history.push({ role: "user", text });
    saveHistory(history);

    showTyping(true);
    setHint("Ко-пилот думает…");

    try {
      const res = await fetch("/api/copilot/chat", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          city: currentCityName(),
          history: history.slice(-8, -1),  // последние 8 минус только что добавленный
        }),
      });
      showTyping(false);
      if (!res.ok) {
        addBubble("assistant", `Сервер ответил ${res.status}. Попробуйте позже.`);
        setHint("Ошибка сети.");
        return;
      }
      const data = await res.json();
      const reply = data.text || "Ответ не получен.";
      addBubble("assistant", reply, {
        action: data.action || null,
        sources: data.sources || [],
        audio: data.audio || null,
        audio_mime: data.audio_mime || null,
      });
      const updated = loadHistory();
      updated.push({ role: "assistant", text: reply });
      saveHistory(updated);
      const engine = data.tts_engine === "fish" ? "🔊 Fish Audio…" : "🔊 Озвучиваю…";
      setHint(voiceEnabled() ? engine : "Готово.");
      if (voiceEnabled()) speak(reply, { audio: data.audio, audio_mime: data.audio_mime });
      else stopSpeaking();
    } catch (e) {
      showTyping(false);
      addBubble("assistant", "Связь дрогнула. Попробуйте через минуту.");
      setHint("Сеть недоступна.");
    }
  }

  // ---------------------------------------------------------------------------
  // Open / close / wire
  // ---------------------------------------------------------------------------

  function openPanel() {
    const p = el("cp-panel");
    if (!p) return;
    p.hidden = false;
    setTimeout(() => el("cp-text")?.focus(), 50);
    if (el("cp-log").children.length === 0) {
      // Восстановим историю из localStorage
      const h = loadHistory();
      if (h.length === 0) {
        addBubble("assistant",
          "Здравствуйте. Я голосовой Ко-пилот мэра. Спросите про город — метрики, жалобы, прогноз. Можно голосом.",
        );
      } else {
        h.forEach((turn) => addBubble(turn.role, turn.text));
      }
    }
    refreshVoiceToggle();
  }

  function closePanel() {
    const p = el("cp-panel");
    if (p) p.hidden = true;
    stopRecognition();
    stopSpeaking();
  }

  function refreshVoiceToggle() {
    const btn = el("cp-voice-toggle");
    if (!btn) return;
    btn.textContent = voiceEnabled() ? "🔊" : "🔇";
    btn.title = voiceEnabled() ? "Выключить озвучку" : "Включить озвучку";
  }

  function wire() {
    el("cp-fab")?.addEventListener("click", openPanel);
    el("cp-close")?.addEventListener("click", closePanel);
    el("cp-send")?.addEventListener("click", sendText);
    el("cp-mic")?.addEventListener("click", startRecognition);
    el("cp-text")?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); sendText(); }
    });
    el("cp-voice-toggle")?.addEventListener("click", () => {
      setVoiceEnabled(!voiceEnabled());
      refreshVoiceToggle();
      if (!voiceEnabled()) stopSpeaking();
    });
    el("cp-clear")?.addEventListener("click", () => {
      clearHistory();
      const log = el("cp-log");
      if (log) log.innerHTML = "";
      addBubble("assistant", "История очищена. Я готов слушать.");
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !el("cp-panel")?.hidden) closePanel();
    });

    // На некоторых браузерах getVoices() пуст до speechSynthesis.onvoiceschanged
    if (window.speechSynthesis) {
      window.speechSynthesis.onvoiceschanged = () => {};
    }

    // Спрятать 🎙 если SpeechRecognition не поддержан и нет fallback
    const Klass = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Klass) {
      const m = el("cp-mic");
      if (m) m.style.display = "none";
    }
  }

  function init() {
    injectMarkup();
    wire();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
