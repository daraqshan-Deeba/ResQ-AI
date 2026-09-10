/**
 * Step 9 — Frontend End-to-End & Invariant Validation Tests
 * Run: node frontend/test_step9_frontend.js
 */

'use strict';

const makeEl = () => ({
  style: {}, textContent: '', innerHTML: '', classList: { toggle:()=>{}, add:()=>{}, remove:()=>{} },
  addEventListener: () => {}, scrollTop: 0, scrollHeight: 0,
  disabled: false, checked: false, value: '', getAttribute: () => null,
  querySelectorAll: () => ({ forEach: () => {} }),
});

global.document = {
  getElementById: () => makeEl(),
  querySelector: () => null,
  querySelectorAll: () => ({ forEach: () => {} }),
};
Object.defineProperty(global, 'window', { value: {
  location: { search: '' },
  ResQAssessmentRenderers: null,
  SpeechRecognition: undefined,
  webkitSpeechRecognition: undefined,
}, writable: true, configurable: true });
Object.defineProperty(global, 'navigator', { value: { geolocation: null }, writable: true, configurable: true });
global.firebase = undefined;
global.firebaseConfig = undefined;
global.FCM_VAPID_KEY = undefined;
global.fetch = async () => {};
global.URLSearchParams = class { constructor() {} get() { return null; } };

const renderers = require('./script.js');
const {
  escapeHtml,
  renderServiceStatus,
  renderActionPlan,
  renderWeather,
  renderConfidence,
  renderHospitals,
  renderAssessmentResult,
} = renderers;

let passed = 0, failed = 0;
function t(name, fn) {
  try { fn(); passed++; console.log('  ✅ ' + name); }
  catch(e) { failed++; console.log('  ❌ ' + name + '\n     ' + e.message); }
}

console.log('\n=== Step 9 Frontend Invariant & End-to-End Tests ===\n');

// 1. Scenario L: Multi-service degradation presentation
console.log('--- Scenario L: Multi-service degradation presentation ---');
t('groq + weather + maps degraded shows all 3 human-readable notices', () => {
  const html = renderServiceStatus({ groq: 'unavailable', weather: 'unavailable', maps: 'unavailable' });
  if (!html.includes('AI generation unavailable')) throw new Error('Missing groq notice');
  if (!html.includes('Live weather data is currently unavailable')) throw new Error('Missing weather notice');
  if (!html.includes('Nearby hospital lookup service is temporarily degraded')) throw new Error('Missing maps notice');
  if (html.includes('stack') || html.includes('Traceback') || html.includes('Error:')) throw new Error('Internal details leaked');
});

t('no secret keys or credential placeholders ever appear in rendered status', () => {
  const html = renderServiceStatus({ groq: 'unavailable', weather: 'unavailable', maps: 'unavailable' });
  if (html.includes('api_key') || html.includes('API_KEY') || html.includes('secret') || html.includes('bearer')) {
    throw new Error('Credential leak in UI');
  }
});

// 2. Scenario M: XSS sanitization across all renderer inputs
console.log('\n--- Scenario M: Full XSS Attack Vector Sanitization ---');
const XSS_PAYLOADS = [
  '<script>alert("pwned")</script>',
  '<img src=x onerror=alert(1)>',
  '<svg onload=alert(2)>',
  '"><iframe src="javascript:alert(3)">',
  '\'><script>alert(4)</script>',
];

XSS_PAYLOADS.forEach((payload, idx) => {
  t(`XSS payload #${idx+1} escaped in action plan items`, () => {
    const html = renderActionPlan({
      immediate_actions: [payload],
      safety_warnings: [payload],
      emergency_contacts: [payload],
      when_to_seek_help: [payload],
      questions_to_ask_user: [payload],
    }, null);
    if (html.includes('<script>') || html.includes('<img src=x') || html.includes('<svg onload') || html.includes('<iframe')) {
      throw new Error(`Raw payload rendered: ${payload}`);
    }
  });

  t(`XSS payload #${idx+1} escaped in hospital attributes`, () => {
    const html = renderHospitals([{ name: payload, address: payload, lat: 17.0, lon: 78.0 }], 'available');
    if (html.includes('<script') || html.includes('<img') || html.includes('<svg') || html.includes('<iframe')) {
      throw new Error(`Unescaped hospital XSS: ${payload}`);
    }
  });

  t(`XSS payload #${idx+1} escaped in weather condition`, () => {
    const html = renderWeather({ level: 'critical', score: 95, condition: payload });
    if (html.includes('<script') || html.includes('<img') || html.includes('<svg') || html.includes('<iframe')) {
      throw new Error(`Unescaped weather XSS: ${payload}`);
    }
  });
});

// 3. Scenario K: Complete End-to-End Orchestrator Result Rendering
console.log('\n--- Scenario K: Complete AssessmentResult UI Rendering ---');
const E2E_MOCK = {
  emergency_level: 'Critical',
  triage: { category: 'electrocution', confidence: 0.95, tier: 1 },
  weather: { level: 'critical', score: 92, condition: 'Severe Thunderstorm', temp_c: 24.5 },
  confidence: { confidence_level: 'low', overall_confidence: 0.35, limiting_factor: 'action_plan' },
  action_plan: {
    immediate_actions: ['Keep at least 10 meters distance', 'Do not touch standing water'],
    safety_warnings: ['Never approach downed power lines', 'Do not touch victim with bare hands'],
    emergency_contacts: ['112', '108'],
    when_to_seek_help: ['Victim is unresponsive or has electrical burns'],
    questions_to_ask_user: [],
    explanation: 'High-voltage electrocution hazard combined with active storm.',
  },
  hospitals: [
    { name: 'Osmania General Hospital', address: 'Afzal Gunj', lat: 17.375, lon: 78.474 },
  ],
  service_status: { groq: 'available', weather: 'available', maps: 'available' },
  whats_happening: 'Live wire in water',
};

t('renders complete assessment without runtime exceptions', () => {
  const html = renderAssessmentResult(E2E_MOCK, 'Downed wire in flooded street');
  if (!html) throw new Error('Result was empty');
});

t('weather hazard and confidence remain visually and semantically distinct', () => {
  const html = renderAssessmentResult(E2E_MOCK, 'Downed wire in flooded street');
  if (!html.includes('Weather Hazard Level') || !html.includes('CRITICAL')) {
    throw new Error('Weather hazard missing or not labeled Critical');
  }
  if (!html.includes('Assessment Confidence') || !html.includes('Low confidence')) {
    throw new Error('Confidence missing or not labeled Low');
  }
});

t('includes explicit SOS trigger button that requires user confirmation', () => {
  const html = renderAssessmentResult(E2E_MOCK, 'Downed wire in flooded street');
  if (!html.includes('id="assessSosTriggerBtn"')) {
    throw new Error('Missing explicit SOS trigger button in rendered assessment');
  }
});

// Summary
console.log('\n==============================');
console.log(`TOTAL: ${passed+failed}  ✅ PASSED: ${passed}  ❌ FAILED: ${failed}`);
if (failed > 0) { process.exit(1); }
else { console.log('\n✅  All Step 9 frontend invariant tests passed.\n'); }

