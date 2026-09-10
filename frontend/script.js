// ===== ResQ AI — plain JavaScript, no build tools, no frameworks =====

// Point this at wherever your FastAPI backend is running.
// (See resq-backend/README.md — default is localhost:8000 in dev.)
const API_BASE = 'http://127.0.0.1:8000';

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
    injury: 'Someone has a deep cut and is bleeding badly, needs medical help.',
    snakebite: 'Someone has been bitten by a snake, urgent medical help needed.',
    cyclone: 'Extreme cyclone winds and storm surge warning in our area.',
    structural_damage: 'Part of the building wall and roof has collapsed.',
    accident: 'A road vehicle collision just occurred with injured passengers.',
  };

  const categoryLabels = {
    flooding: 'House Flooding / Rising Water',
    electrocution: 'Live Wire / Electrocution Hazard',
    injury: 'Trauma / Physical Injury',
    snakebite: 'Snake Bite Emergency',
    cyclone: 'Cyclone / Extreme Storm',
    structural_damage: 'Building / Structural Collapse',
    accident: 'Vehicular Accident / Collision',
    unclassified: 'Emergency Incident',
  };

  // Safe HTML entity escaping to prevent XSS
  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Preset button listeners
  document.querySelectorAll('.preset-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.preset-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      const input = document.getElementById('assessInput');
      if (input) input.value = presetText[btn.getAttribute('data-preset')] || '';
    });
  });

  // Explicit location tracking — NEVER automatically captured
  let userCoords = null;
  const locationToggle = document.getElementById('assessLocationToggle');
  const locationStatus = document.getElementById('assessLocationStatus');

  if (locationToggle) {
    locationToggle.addEventListener('change', () => {
      if (locationToggle.checked) {
        if (!navigator.geolocation) {
          if (locationStatus) locationStatus.textContent = 'GPS not supported in this browser';
          locationToggle.checked = false;
          return;
        }
        if (locationStatus) locationStatus.textContent = 'Requesting GPS…';
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            userCoords = {
              lat: pos.coords.latitude,
              lon: pos.coords.longitude,
            };
            if (locationStatus) locationStatus.textContent = '📍 GPS attached';
          },
          (err) => {
            userCoords = null;
            locationToggle.checked = false;
            if (locationStatus) locationStatus.textContent = 'Permission denied / unavailable';
          },
          { enableHighAccuracy: true, timeout: 8000 }
        );
      } else {
        userCoords = null;
        if (locationStatus) locationStatus.textContent = '';
      }
    });
  }

  // Voice speech-to-text mic button
  const micBtn = document.getElementById('assessMic');
  if (micBtn) {
    micBtn.addEventListener('click', () => {
      micBtn.classList.toggle('recording');
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

  // Modular rendering helpers
  function renderServiceStatus(statusObj) {
    if (!statusObj) return '';
    const notices = [];

    if (statusObj.groq && statusObj.groq !== 'available') {
      notices.push('AI generation unavailable — using verified deterministic safety guidance.');
    }
    if (statusObj.weather && statusObj.weather !== 'available') {
      notices.push('Live weather data is currently unavailable — baseline estimates applied.');
    }
    if (statusObj.maps && statusObj.maps !== 'available' && statusObj.maps !== 'not_requested') {
      notices.push('Nearby hospital lookup service is temporarily degraded.');
    }

    if (notices.length === 0) return '';

    return `
      <div style="background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.25);border-radius:12px;padding:10px 14px;margin-bottom:16px;font-size:12px;color:#fcd34d;">
        ${notices.map((n) => `<div style="display:flex;align-items:center;gap:6px;margin:2px 0;"><span>⚠️</span><span>${escapeHtml(n)}</span></div>`).join('')}
      </div>
    `;
  }

  function renderActionPlan(plan, legacyFallback) {
    const actions = (plan && plan.immediate_actions) || (legacyFallback && legacyFallback.immediate_first_aid) || [];
    const warnings = (plan && plan.safety_warnings) || (legacyFallback && legacyFallback.what_not_to_do) || [];
    const seekHelp = (plan && plan.when_to_seek_help) || [];
    const questions = (plan && plan.questions_to_ask_user) || [];
    const contacts = (plan && plan.emergency_contacts) || (legacyFallback && legacyFallback.call_these_services) || [];

    const renderList = (items, icon) =>
      items
        .map(
          (item) => `
      <li style="margin-bottom:6px;display:flex;align-items:flex-start;gap:8px;">
        <span style="flex-shrink:0;">${icon}</span>
        <span>${escapeHtml(item)}</span>
      </li>
    `
        )
        .join('');

    let html = '';

    if (actions.length > 0) {
      html += `
        <div style="margin-top:16px;">
          <div class="mono-tag" style="color:var(--accent-soft);font-weight:600;">⚡ Immediate Safety Actions</div>
          <ul style="list-style:none;padding:0;margin:8px 0;font-size:14px;line-height:1.6;">${renderList(actions, '✅')}</ul>
        </div>
      `;
    }

    if (warnings.length > 0) {
      html += `
        <div style="margin-top:16px;">
          <div class="mono-tag" style="color:var(--danger-soft);font-weight:600;">🚫 Critical Warnings — What to Avoid</div>
          <ul style="list-style:none;padding:0;margin:8px 0;font-size:14px;line-height:1.6;">${renderList(warnings, '⚠️')}</ul>
        </div>
      `;
    }

    if (contacts.length > 0) {
      html += `
        <div style="margin-top:16px;">
          <div class="mono-tag" style="color:#fbbf24;font-weight:600;">📞 Emergency Helplines (Dial Immediately)</div>
          <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:8px;">
            ${contacts
              .map(
                (c) =>
                  `<span style="background:rgba(251,191,36,0.1);border:1px solid rgba(251,191,36,0.3);padding:6px 12px;border-radius:8px;font-weight:600;font-size:13px;color:#fef08a;">${escapeHtml(c)}</span>`
              )
              .join('')}
          </div>
        </div>
      `;
    }

    if (seekHelp.length > 0) {
      html += `
        <div style="margin-top:16px;">
          <div class="mono-tag" style="color:var(--muted);">🚨 When to Escalate to Emergency Services</div>
          <ul style="list-style:none;padding:0;margin:8px 0;font-size:13px;color:#cbd5e1;line-height:1.5;">${renderList(seekHelp, '🔺')}</ul>
        </div>
      `;
    }

    if (questions.length > 0) {
      html += `
        <div style="margin-top:16px;">
          <div class="mono-tag" style="color:var(--muted);">❓ Situation Assessment Clarifications</div>
          <ul style="list-style:none;padding:0;margin:8px 0;font-size:13px;color:#94a3b8;line-height:1.5;">${renderList(questions, '▫️')}</ul>
        </div>
      `;
    }

    return html;
  }

  function renderWeather(weather) {
    if (!weather) return '';
    const level = (weather.level || 'safe').toLowerCase();
    let badgeClass = 'safe';
    if (level === 'critical') badgeClass = 'critical';
    else if (level === 'warning') badgeClass = 'warning';
    else if (level === 'watch') badgeClass = 'watch';

    const scoreText = typeof weather.score === 'number' ? `Score: ${weather.score}/100` : '';
    const conditionText = weather.condition ? escapeHtml(weather.condition) : '';

    return `
      <div style="background:rgba(255,255,255,0.03);border:1px solid var(--border);border-radius:12px;padding:12px 16px;margin:14px 0;">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;">
          <span class="mono-tag">Weather Hazard Level</span>
          <span class="badge ${badgeClass}">${escapeHtml((weather.level || 'safe').toUpperCase())} ${scoreText ? '· ' + escapeHtml(scoreText) : ''}</span>
        </div>
        ${conditionText ? `<p style="font-size:13px;color:#cbd5e1;margin:6px 0 0;">🌧️ ${conditionText}${weather.temp_c ? ' (' + weather.temp_c + '°C)' : ''}</p>` : ''}
      </div>
    `;
  }

  function renderConfidence(confidence) {
    if (!confidence) return '';
    const level = confidence.confidence_level || 'low';
    const score = typeof confidence.overall_confidence === 'number'
      ? Math.round(confidence.overall_confidence * 100)
      : null;

    let levelBadge = 'safe';
    let levelText = 'High confidence';
    if (level === 'high') {
      levelBadge = 'safe';
      levelText = 'High confidence';
    } else if (level === 'medium') {
      levelBadge = 'watch';
      levelText = 'Moderate confidence';
    } else {
      levelBadge = 'critical';
      levelText = 'Low confidence — some signals uncertain';
    }

    let limitingMsg = '';
    if (confidence.limiting_factor && level !== 'high') {
      const factor = confidence.limiting_factor;
      if (factor === 'weather') {
        limitingMsg = 'Live weather data is currently unavailable, so the assessment has reduced confidence.';
      } else if (factor === 'triage') {
        limitingMsg = 'The incident description is ambiguous, so the assessment has reduced confidence.';
      } else if (factor === 'action_plan') {
        limitingMsg = 'AI-generated guidance is treated conservatively.';
      }
    }

    return `
      <div style="background:rgba(255,255,255,0.03);border:1px solid var(--border);border-radius:12px;padding:12px 16px;margin:14px 0;">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;">
          <span class="mono-tag">Assessment Confidence</span>
          <span class="badge ${levelBadge}">${escapeHtml(levelText)}${score !== null ? ' (' + score + '%)' : ''}</span>
        </div>
        ${limitingMsg ? `<p style="font-size:12px;color:var(--muted);margin:6px 0 0;">ℹ️ ${escapeHtml(limitingMsg)}</p>` : ''}
      </div>
    `;
  }

  function renderHospitals(hospitals, mapsStatus) {
    if (Array.isArray(hospitals) && hospitals.length > 0) {
      const items = hospitals
        .map((h) => {
          const name = escapeHtml(h.name || 'Hospital');
          const addr = h.address ? `<div style="font-size:12px;color:var(--muted);">${escapeHtml(h.address)}</div>` : '';
          const link =
            h.lat && h.lon
              ? `<a href="https://maps.google.com/?q=${encodeURIComponent(h.lat)},${encodeURIComponent(h.lon)}" target="_blank" rel="noopener" style="color:var(--accent-soft);font-size:12px;display:inline-block;margin-top:4px;">📍 Open in Google Maps →</a>`
              : '';
          return `
            <div class="glass-card" style="padding:10px 14px;border-radius:10px;margin-bottom:8px;">
              <div style="font-weight:500;font-size:14px;">➕ ${name}</div>
              ${addr}
              ${link}
            </div>
          `;
        })
        .join('');

      return `
        <div style="margin-top:18px;">
          <div class="mono-tag" style="margin-bottom:8px;">🏥 Verified Nearby Hospitals</div>
          <div>${items}</div>
        </div>
      `;
    }

    if (mapsStatus && mapsStatus !== 'not_requested' && mapsStatus !== 'available') {
      return `
        <div style="margin-top:14px;font-size:12px;color:var(--muted);">
          🏥 Nearby hospital lookup is temporarily unavailable (${escapeHtml(mapsStatus)}).
        </div>
      `;
    }

    return '';
  }

  function renderAssessmentResult(r, situationText) {
    // 1. Triage header & emergency level
    const categoryKey = (r.triage && r.triage.category) || 'unclassified';
    const categoryTitle = categoryLabels[categoryKey] || 'Emergency Assessment';
    const level = r.emergency_level || 'Moderate';
    let levelBadge = 'watch';
    if (level.toLowerCase() === 'critical') levelBadge = 'critical';
    else if (level.toLowerCase() === 'high') levelBadge = 'warning';
    else if (level.toLowerCase() === 'low') levelBadge = 'safe';

    const explanationText = (r.action_plan && r.action_plan.explanation) || r.whats_happening || '';

    // 2. Service degradation banner
    const statusBanner = renderServiceStatus(r.service_status);

    // 3. Action plan sections (Immediate actions, Warnings, Contacts, Escalations)
    const actionPlanHtml = renderActionPlan(r.action_plan, r);

    // 4. Weather hazard display (separate from confidence)
    const weatherHtml = renderWeather(r.weather);

    // 5. Confidence display (separate from risk)
    const confidenceHtml = renderConfidence(r.confidence);

    // 6. Hospital lookup display
    const mapsStatus = r.service_status ? r.service_status.maps : null;
    const hospitalsHtml = renderHospitals(r.hospitals, mapsStatus);

    // 7. Explicit SOS trigger control
    const sosTriggerHtml = `
      <div style="margin-top:24px;padding-top:16px;border-top:1px solid var(--border);">
        <div class="mono-tag" style="color:var(--danger-soft);margin-bottom:6px;">Escalate to Emergency Responders</div>
        <p style="font-size:13px;color:var(--muted);margin:0 0 10px;">If life or safety is threatened, trigger an SOS alert to notify emergency services.</p>
        <button class="btn btn-danger" id="assessSosTriggerBtn" style="width:100%;font-size:14px;padding:12px 18px;">
          🚨 Send One-Tap SOS Alert
        </button>
        <div id="assessSosStatus" style="font-size:13px;margin-top:10px;"></div>
      </div>
    `;

    return `
      ${statusBanner}
      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:12px;">
        <span class="badge ${levelBadge}" style="font-size:13px;padding:6px 14px;">${escapeHtml(level.toUpperCase())} PRIORITY</span>
        <span class="mono-tag">${escapeHtml(categoryTitle)}</span>
      </div>
      <h3 style="font-size:19px;line-height:1.4;margin:8px 0 12px;">${escapeHtml(explanationText)}</h3>
      ${actionPlanHtml}
      ${weatherHtml}
      ${confidenceHtml}
      ${hospitalsHtml}
      ${sosTriggerHtml}
    `;
  }

  // Attach explicit SOS trigger handler to the dynamically rendered button
  function attachSosTriggerListener(situationText) {
    const sosBtn = document.getElementById('assessSosTriggerBtn');
    const statusEl = document.getElementById('assessSosStatus');
    if (!sosBtn) return;

    sosBtn.addEventListener('click', async () => {
      if (userCoords && userCoords.lat && userCoords.lon) {
        // We already have user coordinates from explicit checkbox
        await executeSosCall(userCoords.lat, userCoords.lon, situationText, sosBtn, statusEl);
      } else {
        // Explicitly ask user for geolocation permission for SOS
        if (!navigator.geolocation) {
          if (statusEl) statusEl.innerHTML = '<span style="color:var(--danger-soft);">⚠️ Geolocation is not supported by your browser. Please dial 112 directly.</span>';
          return;
        }
        if (statusEl) statusEl.textContent = 'Acquiring GPS location for SOS…';
        sosBtn.disabled = true;

        navigator.geolocation.getCurrentPosition(
          async (pos) => {
            const lat = pos.coords.latitude;
            const lon = pos.coords.longitude;
            await executeSosCall(lat, lon, situationText, sosBtn, statusEl);
          },
          (err) => {
            sosBtn.disabled = false;
            if (statusEl) {
              statusEl.innerHTML = '<span style="color:var(--danger-soft);">⚠️ Location permission required for SOS dispatch. Please dial 112 directly on phone.</span>';
            }
          },
          { enableHighAccuracy: true, timeout: 10000 }
        );
      }
    });
  }

  async function executeSosCall(lat, lon, situation, btn, statusEl) {
    btn.disabled = true;
    if (statusEl) statusEl.textContent = 'Transmitting emergency SOS record…';

    const result = await apiCall('/api/sos', {
      method: 'POST',
      body: JSON.stringify({
        lat: lat,
        lon: lon,
        situation: situation || 'Emergency reported via assessment',
      }),
    });

    btn.disabled = false;
    if (!statusEl) return;

    if (!result.ok) {
      statusEl.innerHTML = `<span style="color:var(--danger-soft);">⚠️ ${escapeHtml(result.error)}. Call 112 immediately.</span>`;
      return;
    }

    const d = result.data;
    if (d && d.status === 'recorded') {
      if (d.notification_status === 'notification_accepted') {
        statusEl.innerHTML = `<span style="color:#34d399;">✅ Emergency request recorded and notification accepted by responders. Your location: <a href="${escapeHtml(d.maps_link)}" target="_blank" rel="noopener" style="color:var(--accent-soft);">Map</a></span>`;
      } else if (d.notification_status === 'notification_failed') {
        statusEl.innerHTML = `<span style="color:#fbbf24;">⚠️ Emergency request recorded, but push notification delivery could not be confirmed. Call 112 directly.</span>`;
      } else {
        statusEl.innerHTML = `<span style="color:#34d399;">✅ Emergency request recorded. Push notification service unavailable — dial 112 directly.</span>`;
      }
    } else {
      statusEl.innerHTML = `<span style="color:var(--danger-soft);">⚠️ Emergency request could not be persisted. Please contact emergency services (112) directly.</span>`;
    }
  }

  // Submit button listener
  const submitBtn = document.getElementById('assessSubmit');
  if (submitBtn) {
    submitBtn.addEventListener('click', async () => {
      const input = document.getElementById('assessInput');
      const langEl = document.getElementById('assessLang');
      const text = input && input.value.trim();

      if (!text) {
        renderResult(`<div class="mono-tag">Standing by</div>
           <h3 style="font-size:18px;margin-top:8px;">Tell us what's happening</h3>
           <p style="color:var(--muted);font-size:14px;margin-top:8px;">Pick an emergency preset above or describe your situation first.</p>`);
        return;
      }

      // Prevent duplicate submissions and show active loading state
      submitBtn.disabled = true;
      submitBtn.textContent = '⏳ Assessing situation…';

      renderResult(`<div class="mono-tag" style="color:var(--danger-soft);">Analyzing…</div>
         <h3 style="font-size:18px;margin-top:8px;">Assessing your situation…</h3>
         <p style="color:var(--muted);font-size:14px;margin-top:8px;">Classifying hazard, evaluating weather conditions, and generating safety guidance…</p>`);

      try {
        const payload = {
          description: text,
          language: langEl ? langEl.value : 'English',
        };
        // Explicitly include location ONLY if user chose to provide it
        if (userCoords && userCoords.lat && userCoords.lon) {
          payload.lat = userCoords.lat;
          payload.lon = userCoords.lon;
        }

        const result = await apiCall('/api/assessment', {
          method: 'POST',
          body: JSON.stringify(payload),
        });

        if (!result.ok) {
          renderResult(`
            <div class="mono-tag" style="color:var(--danger-soft);">⚠️ Service Notice</div>
            <h3 style="font-size:18px;margin-top:8px;">Could not complete assessment right now</h3>
            <p style="color:var(--muted);font-size:14px;margin-top:8px;">ResQ AI could not reach the assessment service (${escapeHtml(result.error)}). If you are in immediate danger, please use the verified emergency helplines below:</p>
            <div style="margin-top:16px;display:flex;gap:10px;flex-wrap:wrap;">
              <span style="background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);padding:6px 12px;border-radius:8px;font-weight:600;color:var(--danger-soft);">National Emergency: 112</span>
              <span style="background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);padding:6px 12px;border-radius:8px;font-weight:600;color:var(--danger-soft);">Ambulance: 108</span>
              <span style="background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);padding:6px 12px;border-radius:8px;font-weight:600;color:var(--danger-soft);">Disaster Helpline: 1070</span>
            </div>
          `);
          return;
        }

        const r = result.data;
        renderResult(renderAssessmentResult(r, text));
        attachSosTriggerListener(text);
      } catch (err) {
        renderResult(`
          <div class="mono-tag" style="color:var(--danger-soft);">⚠️ Unexpected Error</div>
          <h3 style="font-size:18px;margin-top:8px;">Something went wrong</h3>
          <p style="color:var(--muted);font-size:14px;margin-top:8px;">Please check your connection and call 112 if urgent help is needed.</p>
        `);
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = '🚨 Get Help Now';
      }
    });
  }

  // Export renderers for testing/inspection
  if (typeof window !== 'undefined') {
    window.ResQAssessmentRenderers = {
      escapeHtml,
      renderServiceStatus,
      renderActionPlan,
      renderWeather,
      renderConfidence,
      renderHospitals,
      renderAssessmentResult,
    };
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      escapeHtml,
      renderServiceStatus,
      renderActionPlan,
      renderWeather,
      renderConfidence,
      renderHospitals,
      renderAssessmentResult,
    };
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
        if (!statusEl) return;

        if (!result.ok) {
          // Network or unexpected server error.
          statusEl.textContent = `⚠️ ${result.error}`;
          return;
        }

        const d = result.data;
        // The backend always returns a structured SosResponse.
        // Display the server-composed message which reflects the exact outcome.
        if (d && d.message) {
          statusEl.textContent = d.message;
        } else if (d && d.status === 'recorded') {
          statusEl.textContent = '✅ SOS recorded.';
        } else {
          // Degraded — no durable record; prompt user to call directly.
          statusEl.textContent =
            '⚠️ SOS could not be recorded. Please call 112 immediately.';
        }
      },
      () => {
        btn.disabled = false;
        if (statusEl) statusEl.textContent = 'Could not get your location — check browser permissions.';
      }
    );
  });
})();

