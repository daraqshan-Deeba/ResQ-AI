// ===== ResQ AI — plain JavaScript, no build tools, no frameworks =====

// Point this at wherever your FastAPI backend is running.
// (See resq-backend/README.md — default is localhost:8000 in dev.)
const API_BASE = 'http://localhost:8000';

// ---------- Landing page: mobile menu toggle ----------
const navToggle = document.getElementById('navToggle');
const mobileMenu = document.getElementById('mobileMenu');
if (navToggle && mobileMenu) {
  navToggle.addEventListener('click', () => {
    mobileMenu.classList.toggle('open');
  });
}

// ---------- Landing page: ambient rain ----------
const rainMount = document.getElementById('rain');
if (rainMount) {
  const DROP_COUNT = 60;
  let dropsHtml = '';
  for (let i = 0; i < DROP_COUNT; i++) {
    const left = Math.random() * 100;
    const duration = 0.7 + Math.random() * 1.1;
    const delay = Math.random() * 3;
    const height = 40 + Math.random() * 60;
    dropsHtml += `<span class="drop" style="left:${left}%;height:${height}px;animation-duration:${duration}s;animation-delay:${delay}s;"></span>`;
  }
  rainMount.innerHTML = dropsHtml;
}

// ---------- Small fetch helper: never throws to the UI, always returns {ok, data|error} ----------
async function apiCall(path, options = {}) {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
    if (!res.ok) {
      const detail = await res.text().catch(() => '');
      return { ok: false, error: `${res.status} ${res.statusText}${detail ? ' — ' + detail : ''}` };
    }
    return { ok: true, data: await res.json() };
  } catch (err) {
    // Most common cause during dev: backend isn't running, or CORS_ORIGINS
    // in .env doesn't include this page's origin.
    return { ok: false, error: 'Could not reach the backend — is it running at ' + API_BASE + '?' };
  }
}

// ---------- Dashboard: page switching ----------
const pageTitles = {
  overview: 'Emergency Overview',
  assessment: 'Emergency Assessment',
  assistant: 'AI Assistant',
  hospitals: 'Nearby Hospitals',
  shelters: 'Nearby Shelters',
  reports: 'Community Reports',
  sos: 'Send SOS',
  profile: 'Profile',
  settings: 'Settings',
};

// Pages that should lazy-load live data the first time they're shown.
const pageLoaders = {
  overview: loadOverviewData,
  hospitals: loadHospitals,
  shelters: loadShelters,
  reports: loadReports,
};
const loadedPages = new Set();

function showPage(pageName) {
  document.querySelectorAll('.page').forEach((el) => (el.style.display = 'none'));
  const target = document.getElementById('page-' + pageName);
  if (target) target.style.display = 'block';

  document.querySelectorAll('.nav-item').forEach((el) => el.classList.remove('active'));
  document.querySelectorAll('.nav-item[data-page="' + pageName + '"]').forEach((el) => el.classList.add('active'));

  const titleEl = document.getElementById('topbarTitle');
  if (titleEl && pageTitles[pageName]) titleEl.textContent = pageTitles[pageName];

  if (pageLoaders[pageName] && !loadedPages.has(pageName)) {
    loadedPages.add(pageName);
    pageLoaders[pageName]();
  }

  window.scrollTo(0, 0);
}

// Any element with data-page="..." switches the dashboard view (sidebar links,
// quick action cards, the floating SOS button, etc.)
document.querySelectorAll('[data-page]').forEach((el) => {
  el.addEventListener('click', (e) => {
    e.preventDefault();
    showPage(el.getAttribute('data-page'));
  });
});

// Land on the right dashboard page depending on where the user came from
// (e.g. index.html links to dashboard.html?page=assessment or ?page=overview)
(function initDashboardFromUrl() {
  const sidebar = document.querySelector('.dash-body');
  if (!sidebar) return; // not on the dashboard page
  const params = new URLSearchParams(window.location.search);
  const requested = params.get('page');
  showPage(requested && pageTitles[requested] ? requested : 'overview');
})();

// ---------- Overview page: live weather + risk score (Sentinel) ----------
async function loadOverviewData() {
  const result = await apiCall('/api/weather/risk');
  const weatherResult = await apiCall('/api/weather');

  if (!result.ok || !weatherResult.ok) {
    console.warn('Overview data unavailable:', result.error || weatherResult.error);
    return; // leave the static placeholder numbers in place
  }

  const risk = result.data;
  const weather = weatherResult.data;

  const scoreEl = document.getElementById('riskScoreValue');
  const circleEl = document.getElementById('riskGaugeCircle');
  const rainfallPctEl = document.getElementById('rainfallPct');
  const rainfallBarEl = document.getElementById('rainfallBar');
  const drainagePctEl = document.getElementById('drainagePct');
  const drainageBarEl = document.getElementById('drainageBar');
  const statusLevelEl = document.getElementById('statusLevelText');
  const topbarBadge = document.getElementById('topbarStatusBadge');
  const weatherConditionEl = document.getElementById('weatherCondition');
  const weatherTempEl = document.getElementById('weatherTemp');

  if (scoreEl) scoreEl.textContent = risk.score;
  if (circleEl) {
    const circumference = 251; // matches the SVG's stroke-dasharray
    circleEl.style.strokeDashoffset = String(circumference * (1 - risk.score / 100));
  }
  if (rainfallPctEl) rainfallPctEl.textContent = `${risk.rainfall_intensity_pct}%`;
  if (rainfallBarEl) rainfallBarEl.style.width = `${risk.rainfall_intensity_pct}%`;
  if (drainagePctEl) drainagePctEl.textContent = `${risk.drainage_capacity_pct}%`;
  if (drainageBarEl) drainageBarEl.style.width = `${risk.drainage_capacity_pct}%`;

  const levelLabel = risk.level.toUpperCase();
  if (statusLevelEl) statusLevelEl.textContent = levelLabel;
  if (topbarBadge) {
    topbarBadge.textContent = levelLabel;
    topbarBadge.className = 'badge ' + risk.level; // reuses .badge.watch/.critical/.warning/.safe
  }
  if (weatherConditionEl) weatherConditionEl.textContent = weather.condition;
  if (weatherTempEl) weatherTempEl.textContent = `${Math.round(weather.temp_c)}°C`;
}

// ---------- Mock-until-connected AI chat widget (Responder) ----------
const initialMessages = [
  { role: 'assistant', text: "Hi, I'm the ResQ AI assistant. Tell me your location and what's happening, and I'll help you find the safest next step." },
];

function buildChatWidget(mountId) {
  const mount = document.getElementById(mountId);
  if (!mount) return;

  let messages = [...initialMessages];
  let sending = false;

  mount.innerHTML = `
    <div class="chat-box">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;">
        <span class="feature-icon" style="margin-bottom:0;width:32px;height:32px;">🤖</span>
        <div>
          <div style="font-size:14px;font-weight:500;">Responder</div>
          <div class="mono-tag" style="text-transform:none;">AI Assistant</div>
        </div>
      </div>
      <div class="chat-messages" id="${mountId}-messages"></div>
      <div class="chat-input-row">
        <input type="text" id="${mountId}-input" placeholder="Describe your situation…" />
        <button class="chat-send" id="${mountId}-send">➤</button>
      </div>
    </div>
  `;

  const messagesEl = document.getElementById(mountId + '-messages');
  const inputEl = document.getElementById(mountId + '-input');
  const sendEl = document.getElementById(mountId + '-send');

  function render() {
    messagesEl.innerHTML = messages
      .map(
        (m) => `
        <div class="chat-msg ${m.role}">
          <span class="chat-avatar" style="background:${m.role === 'user' ? 'rgba(255,255,255,.1)' : 'rgba(37,99,235,.15)'};">${m.role === 'user' ? '🙂' : '🤖'}</span>
          <div class="chat-bubble">${m.text}</div>
        </div>`
      )
      .join('');
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  async function send() {
    const text = inputEl.value.trim();
    if (!text || sending) return;

    const historyForApi = messages.map((m) => ({ role: m.role, text: m.text }));
    messages.push({ role: 'user', text });
    inputEl.value = '';
    sending = true;
    messages.push({ role: 'assistant', text: '…' });
    render();

    const result = await apiCall('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ history: historyForApi, message: text }),
    });

    messages.pop(); // remove the "…" placeholder
    messages.push({
      role: 'assistant',
      text: result.ok ? result.data.reply : `⚠️ ${result.error}`,
    });
    sending = false;
    render();
  }

  sendEl.addEventListener('click', send);
  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') send();
  });

  render();
}

buildChatWidget('chatWidgetMount');
buildChatWidget('chatWidgetMount2');

// ---------- Assessment page: presets, mic, real submit (Responder) ----------
(function initAssessmentPage() {
  const presetText = {
    flooding: 'My house is flooding and water is rising fast.',
    electrocution: 'There are live wires down near standing water.',
    injury: 'Someone slipped and is injured, they need help.',
    snakebite: 'Someone has been bitten by a snake.',
  };

  document.querySelectorAll('.preset-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.preset-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      const input = document.getElementById('assessInput');
      if (input) input.value = presetText[btn.getAttribute('data-preset')] || '';
    });
  });

  const micBtn = document.getElementById('assessMic');
  if (micBtn) {
    micBtn.addEventListener('click', () => {
      micBtn.classList.toggle('recording');
      // Uses the browser's free built-in Web Speech API when available.
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) return;
      const recognition = new SpeechRecognition();
      recognition.lang = 'en-IN';
      recognition.onresult = (e) => {
        const input = document.getElementById('assessInput');
        if (input) input.value = e.results[0][0].transcript;
      };
      recognition.onend = () => micBtn.classList.remove('recording');
      recognition.start();
    });
  }

  function renderResult(html) {
    const result = document.getElementById('assessResult');
    if (result) result.innerHTML = html;
  }

  const submitBtn = document.getElementById('assessSubmit');
  if (submitBtn) {
    submitBtn.addEventListener('click', async () => {
      const input = document.getElementById('assessInput');
      const langEl = document.getElementById('assessLang');
      const text = input && input.value.trim();

      if (!text) {
        renderResult(`<div class="mono-tag">Standing by</div>
           <h3 style="font-size:18px;margin-top:8px;">Tell us what's happening</h3>
           <p style="color:var(--muted);font-size:14px;margin-top:8px;">Pick a preset or type a description first.</p>`);
        return;
      }

      renderResult(`<div class="mono-tag" style="color:var(--danger-soft);">Analyzing…</div>
         <h3 style="font-size:18px;margin-top:8px;">Contacting Responder</h3>
         <p style="color:var(--muted);font-size:14px;margin-top:8px;">Checking live conditions and nearby help…</p>`);

      const result = await apiCall('/api/assessment', {
        method: 'POST',
        body: JSON.stringify({
          description: text,
          language: langEl ? langEl.value : 'English',
        }),
      });

      if (!result.ok) {
        renderResult(`<div class="mono-tag" style="color:var(--danger-soft);">⚠️ Couldn't reach Responder</div>
           <p style="color:var(--muted);font-size:14px;margin-top:8px;">${result.error}</p>`);
        return;
      }

      const r = result.data;
      const list = (items) => items.map((i) => `<li style="margin-bottom:4px;">${i}</li>`).join('');
      const nearby = r.nearby_help
        .map((n) => (n.url ? `<li><a href="${n.url}" target="_blank" rel="noopener" style="color:var(--accent-soft);">${n.name}</a></li>` : `<li>${n.name}</li>`))
        .join('');

      renderResult(`
        <div class="badge critical" style="margin-bottom:12px;">${r.emergency_level}</div>
        <h3 style="font-size:18px;">${r.whats_happening}</h3>
        <div class="mono-tag" style="margin-top:16px;">Immediate first aid</div>
        <ul style="font-size:14px;margin:8px 0;padding-left:20px;">${list(r.immediate_first_aid)}</ul>
        <div class="mono-tag">What not to do</div>
        <ul style="font-size:14px;margin:8px 0;padding-left:20px;">${list(r.what_not_to_do)}</ul>
        <div class="mono-tag">Call these services</div>
        <p style="font-size:14px;margin:8px 0;">${r.call_these_services.join(' · ')}</p>
        <div class="mono-tag">Things to carry</div>
        <ul style="font-size:14px;margin:8px 0;padding-left:20px;">${list(r.things_to_carry)}</ul>
        <div class="mono-tag">Nearby help</div>
        <ul style="font-size:14px;margin:8px 0;padding-left:20px;">${nearby}</ul>
      `);
    });
  }
})();

// ---------- Hospitals page (Wayfinder) ----------
async function loadHospitals() {
  const statusEl = document.getElementById('hospitalsStatus');
  const listEl = document.getElementById('hospitalsList');
  const result = await apiCall('/api/hospitals');
  if (!result.ok) {
    if (statusEl) statusEl.textContent = `Showing sample data — ${result.error}`;
    return;
  }
  if (listEl) {
    listEl.innerHTML = result.data
      .map(
        (h) => `
        <div class="glass-card list-item">
          <span class="feature-icon" style="background:rgba(239,68,68,.15);color:var(--danger-soft);">➕</span>
          <h3 style="font-size:16px;margin-top:12px;">${h.name}</h3>
          <div class="mono-tag" style="margin-top:8px;">📍 ${h.address || ''}</div>
        </div>`
      )
      .join('');
  }
  if (statusEl) statusEl.textContent = 'Live from Google Places.';
}

// ---------- Shelters page (Wayfinder / your DB) ----------
async function loadShelters() {
  const statusEl = document.getElementById('sheltersStatus');
  const listEl = document.getElementById('sheltersList');
  const result = await apiCall('/api/shelters');
  if (!result.ok) {
    if (statusEl) statusEl.textContent = `Showing sample data — ${result.error}`;
    return;
  }
  if (listEl) {
    listEl.innerHTML = result.data
      .map((s) => {
        const pct = s.capacity ? Math.round((s.occupied / s.capacity) * 100) : 0;
        return `
        <div class="glass-card list-item">
          <span class="feature-icon" style="background:rgba(6,182,212,.15);color:var(--accent-soft);">🏘️</span>
          <h3 style="font-size:16px;margin-top:12px;">${s.name}</h3>
          <div style="font-size:14px;margin-top:10px;">${s.occupied} / ${s.capacity} occupied</div>
          <div class="risk-factor-bar" style="margin-top:8px;"><div class="risk-factor-fill" style="width:${pct}%;background:linear-gradient(90deg,var(--accent),var(--primary));"></div></div>
        </div>`;
      })
      .join('');
  }
  if (statusEl) statusEl.textContent = 'Manually maintained — see README for how to update this.';
}

// ---------- Community reports page ----------
function timeAgo(isoString) {
  const diffMs = Date.now() - new Date(isoString).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min ago`;
  return `${Math.round(mins / 60)} hr ago`;
}

async function loadReports() {
  const statusEl = document.getElementById('reportsStatus');
  const listEl = document.getElementById('reportsList');
  const result = await apiCall('/api/reports');
  if (!result.ok) {
    if (statusEl) statusEl.textContent = `Showing sample data — ${result.error}`;
    return;
  }
  if (listEl) {
    listEl.innerHTML = result.data
      .map(
        (r) => `
        <div class="glass-card list-item" style="display:flex;gap:16px;margin-bottom:16px;">
          <span class="feature-icon" style="margin-bottom:0;">👥</span>
          <div>
            <div style="display:flex;gap:8px;align-items:center;">
              <b>${r.area}</b>${r.verified ? '<span style="color:var(--accent-soft);font-size:12px;">✅ Verified</span>' : ''}
            </div>
            <p style="font-size:14px;margin:4px 0;">${r.message}</p>
            <span class="mono-tag">${timeAgo(r.created_at)}</span>
          </div>
        </div>`
      )
      .join('');
  }
  if (statusEl) statusEl.textContent = 'Live from the database.';
}

(function initReportForm() {
  const submitBtn = document.getElementById('reportSubmit');
  if (!submitBtn) return;
  submitBtn.addEventListener('click', async () => {
    const areaEl = document.getElementById('reportArea');
    const messageEl = document.getElementById('reportMessage');
    const area = areaEl && areaEl.value.trim();
    const message = messageEl && messageEl.value.trim();
    if (!area || !message) return;

    submitBtn.disabled = true;
    const result = await apiCall('/api/reports', {
      method: 'POST',
      body: JSON.stringify({ area, message }),
    });
    submitBtn.disabled = false;

    if (result.ok) {
      areaEl.value = '';
      messageEl.value = '';
      loadedPages.delete('reports'); // force a refresh
      loadReports();
    } else {
      alert(`Couldn't submit report: ${result.error}`);
    }
  });
})();

// ---------- Firebase Cloud Messaging: push alerts (Settings page) ----------
(function initPushAlerts() {
  const btn = document.getElementById('enableAlertsBtn');
  if (!btn) return;

  btn.addEventListener('click', async () => {
    const statusEl = document.getElementById('alertsStatus');
    const setStatus = (text) => { if (statusEl) statusEl.textContent = text; };

    if (typeof firebase === 'undefined' || !firebaseConfig || firebaseConfig.apiKey === 'YOUR_API_KEY') {
      setStatus('⚠️ Fill in firebase-config.js with your project\'s values first (see README).');
      return;
    }
    if (!('serviceWorker' in navigator) || !('Notification' in window)) {
      setStatus('Push notifications aren\'t supported in this browser.');
      return;
    }

    btn.disabled = true;
    try {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        setStatus('Notifications were not allowed — check your browser\'s site settings.');
        return;
      }

      if (!firebase.apps.length) firebase.initializeApp(firebaseConfig);
      const registration = await navigator.serviceWorker.register('firebase-messaging-sw.js');
      const messaging = firebase.messaging();
      const token = await messaging.getToken({
        vapidKey: FCM_VAPID_KEY,
        serviceWorkerRegistration: registration,
      });

      const result = await apiCall('/api/device-token', {
        method: 'POST',
        body: JSON.stringify({ token }),
      });

      setStatus(result.ok ? '✅ Push alerts enabled on this device.' : `⚠️ ${result.error}`);

      // Foreground messages (tab focused) show up here rather than as a
      // system notification — background ones are handled in the service worker.
      messaging.onMessage((payload) => {
        const title = (payload.notification && payload.notification.title) || 'ResQ AI Alert';
        const body = (payload.notification && payload.notification.body) || '';
        setStatus(`🔔 ${title}: ${body}`);
      });
    } catch (err) {
      setStatus(`⚠️ Could not enable push alerts: ${err.message}`);
    } finally {
      btn.disabled = false;
    }
  });
})();

// ---------- SOS page ----------
(function initSosPage() {
  const btn = document.getElementById('sosConfirmBtn');
  if (!btn) return;
  btn.addEventListener('click', () => {
    const statusEl = document.getElementById('sosStatus');
    if (!navigator.geolocation) {
      if (statusEl) statusEl.textContent = 'Location isn\'t available in this browser.';
      return;
    }
    btn.disabled = true;
    if (statusEl) statusEl.textContent = 'Getting your location…';

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const { latitude, longitude } = position.coords;
        if (statusEl) statusEl.textContent = 'Sending SOS…';
        const result = await apiCall('/api/sos', {
          method: 'POST',
          body: JSON.stringify({ lat: latitude, lon: longitude }),
        });
        btn.disabled = false;
        if (statusEl) {
          statusEl.textContent = result.ok
            ? '✅ SOS sent with your live location.'
            : `⚠️ ${result.error}`;
        }
      },
      () => {
        btn.disabled = false;
        if (statusEl) statusEl.textContent = 'Could not get your location — check browser permissions.';
      }
    );
  });
})();
