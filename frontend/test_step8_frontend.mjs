/**
 * Step 8 — Frontend renderer unit tests
 * Run: node --test frontend/test_step8_frontend.mjs
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);

// Minimal browser globals
global.window = undefined;
global.document = {
  getElementById: () => null,
  querySelectorAll: () => ({ forEach: () => {} }),
};
try { global.navigator = { geolocation: null }; } catch(e) { Object.defineProperty(global, "navigator", { value: { geolocation: null }, writable: true, configurable: true }); }
global.firebase = undefined;
global.firebaseConfig = undefined;
global.FCM_VAPID_KEY = undefined;

const scriptPath = path.join(__dirname, 'script.js');
const renderers = require(scriptPath);

const { escapeHtml, renderServiceStatus, renderActionPlan, renderWeather, renderConfidence, renderHospitals, renderAssessmentResult } = renderers;

// escapeHtml
test('escapeHtml null returns empty', () => { assert.equal(escapeHtml(null), ''); });
test('escapeHtml undefined returns empty', () => { assert.equal(escapeHtml(undefined), ''); });
test('escapeHtml plain string unchanged', () => { assert.equal(escapeHtml('hello'), 'hello'); });
test('escapeHtml ampersand', () => { assert.equal(escapeHtml('a & b'), 'a &amp; b'); });
test('escapeHtml less-than', () => { assert.ok(escapeHtml('<script>').includes('&lt;')); });
test('escapeHtml XSS payload escaped', () => { const r = escapeHtml('<img onerror=alert(1)>'); assert.ok(!r.includes('<img')); });
test('escapeHtml number coerced', () => { assert.equal(escapeHtml(42), '42'); });

// renderServiceStatus
test('renderServiceStatus null returns empty', () => { assert.equal(renderServiceStatus(null), ''); });
test('renderServiceStatus all available returns empty', () => { assert.equal(renderServiceStatus({ groq:'available', weather:'available', maps:'available' }).trim(), ''); });
test('renderServiceStatus groq unavailable shows banner', () => { assert.ok(renderServiceStatus({ groq:'unavailable', weather:'available', maps:'not_requested' }).includes('AI generation unavailable')); });
test('renderServiceStatus weather degraded shows banner', () => { assert.ok(renderServiceStatus({ groq:'available', weather:'degraded', maps:'not_requested' }).includes('Live weather data')); });
test('renderServiceStatus maps degraded shows banner', () => { assert.ok(renderServiceStatus({ groq:'available', weather:'available', maps:'degraded' }).includes('hospital lookup')); });
test('renderServiceStatus maps not_requested no warning', () => { assert.equal(renderServiceStatus({ groq:'available', weather:'available', maps:'not_requested' }).trim(), ''); });

// renderActionPlan
test('renderActionPlan null,null empty', () => { assert.equal(renderActionPlan(null, null).trim(), ''); });
test('renderActionPlan immediate_actions rendered', () => { const h = renderActionPlan({ immediate_actions:['Call 112'], safety_warnings:[], emergency_contacts:[], when_to_seek_help:[], questions_to_ask_user:[] }, null); assert.ok(h.includes('Call 112')); });
test('renderActionPlan legacy fallback', () => { const h = renderActionPlan(null, { immediate_first_aid:['Apply pressure'], what_not_to_do:['No movement'], call_these_services:['108'] }); assert.ok(h.includes('Apply pressure')); });
test('renderActionPlan XSS escaped', () => { const h = renderActionPlan({ immediate_actions:['<script>'], safety_warnings:[], emergency_contacts:[], when_to_seek_help:[], questions_to_ask_user:[] }, null); assert.ok(!h.includes('<script>')); });

// renderWeather
test('renderWeather null empty', () => { assert.equal(renderWeather(null), ''); });
test('renderWeather safe badge', () => { assert.ok(renderWeather({ level:'safe', score:10 }).includes('badge safe')); });
test('renderWeather critical badge', () => { assert.ok(renderWeather({ level:'critical', score:90 }).includes('badge critical')); });
test('renderWeather score shown', () => { assert.ok(renderWeather({ level:'safe', score:15 }).includes('15/100')); });

// renderConfidence
test('renderConfidence null empty', () => { assert.equal(renderConfidence(null), ''); });
test('renderConfidence high safe badge', () => { assert.ok(renderConfidence({ confidence_level:'high', overall_confidence:0.87 }).includes('badge safe')); });
test('renderConfidence low critical badge', () => { assert.ok(renderConfidence({ confidence_level:'low', overall_confidence:0.3 }).includes('badge critical')); });
test('renderConfidence weather factor shown when low', () => { assert.ok(renderConfidence({ confidence_level:'low', overall_confidence:0.4, limiting_factor:'weather' }).includes('unavailable')); });
test('renderConfidence factor NOT shown when high', () => { assert.ok(!renderConfidence({ confidence_level:'high', overall_confidence:0.9, limiting_factor:'weather' }).includes('unavailable')); });

// renderHospitals
test('renderHospitals null empty', () => { assert.equal(renderHospitals(null, null), ''); });
test('renderHospitals empty array empty', () => { assert.equal(renderHospitals([], null), ''); });
test('renderHospitals lat/lon shows map link', () => { const h = renderHospitals([{ name:'City Hosp', lat:17.38, lon:78.46 }], 'available'); assert.ok(h.includes('maps.google.com')); });
test('renderHospitals degraded notice', () => { assert.ok(renderHospitals([], 'degraded').includes('temporarily unavailable')); });
test('renderHospitals not_requested empty', () => { assert.equal(renderHospitals([], 'not_requested').trim(), ''); });
test('renderHospitals XSS in name escaped', () => { const h = renderHospitals([{ name:'<script>xss</script>' }], 'available'); assert.ok(!h.includes('<script>')); });

// renderAssessmentResult integration
const MOCK_FULL = {
  emergency_level: 'High', triage: { category:'flooding' },
  weather: { level:'warning', score:60 },
  confidence: { confidence_level:'medium', overall_confidence:0.65 },
  action_plan: { immediate_actions:['Move up'], safety_warnings:['No wading'], emergency_contacts:['112'], when_to_seek_help:[], questions_to_ask_user:[], explanation:'Flooding' },
  hospitals: [{ name:'Test Hosp', lat:17.38, lon:78.46 }],
  service_status: { groq:'available', weather:'available', maps:'available' },
  whats_happening: '',
};

test('renderAssessmentResult does not throw', () => {
  assert.doesNotThrow(() => renderAssessmentResult(MOCK_FULL, 'flooding'));
});
test('renderAssessmentResult shows priority badge', () => {
  assert.ok(renderAssessmentResult(MOCK_FULL, 'flooding').includes('HIGH PRIORITY'));
});
test('renderAssessmentResult shows immediate action', () => {
  assert.ok(renderAssessmentResult(MOCK_FULL, 'flooding').includes('Move up'));
});
test('renderAssessmentResult includes SOS button', () => {
  assert.ok(renderAssessmentResult(MOCK_FULL, 'flooding').includes('assessSosTriggerBtn'));
});
test('renderAssessmentResult SOS not auto-disabled', () => {
  assert.ok(!renderAssessmentResult(MOCK_FULL, 'flooding').includes('disabled'));
});
test('renderAssessmentResult legacy fallback renders', () => {
  const leg = { emergency_level:'Moderate', triage:{category:'injury'}, immediate_first_aid:['Apply pressure'], what_not_to_do:['No removal'], call_these_services:['108'], whats_happening:'Bleeding', service_status:{}, hospitals:[], confidence:null, weather:null, action_plan:null };
  assert.ok(renderAssessmentResult(leg, 'test').includes('Apply pressure'));
});
test('renderAssessmentResult degradation banner when groq unavailable', () => {
  const deg = { ...MOCK_FULL, service_status:{ groq:'unavailable', weather:'available', maps:'not_requested' } };
  assert.ok(renderAssessmentResult(deg, 'test').includes('AI generation unavailable'));
});
test('renderAssessmentResult XSS in whats_happening escaped', () => {
  const xss = { ...MOCK_FULL, action_plan:null, whats_happening:'<script>alert(1)</script>' };
  assert.ok(!renderAssessmentResult(xss, 'test').includes('<script>alert'));
});

