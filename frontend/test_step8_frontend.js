/**
 * Step 8 — Frontend renderer unit tests (Node.js, no npm required)
 * Run: node frontend/test_step8_frontend.js
 */

'use strict';

// ---- Comprehensive DOM stub so script.js IIFE code does not crash ----
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

// Load script.js — module.exports block will fire in Node CJS context
const renderers = require('./script.js');
const { escapeHtml, renderServiceStatus, renderActionPlan, renderWeather, renderConfidence, renderHospitals, renderAssessmentResult } = renderers;

// ---- Tiny test runner ----
let passed = 0, failed = 0;
function t(name, fn) {
  try { fn(); passed++; console.log('  ✅ ' + name); }
  catch(e) { failed++; console.log('  ❌ ' + name + '\n     ' + e.message); }
}

console.log('\n=== Step 8 Frontend Renderer Tests ===\n');

// escapeHtml
console.log('--- escapeHtml ---');
t('null → empty', () => { if(escapeHtml(null) !== '') throw new Error('expected empty'); });
t('undefined → empty', () => { if(escapeHtml(undefined) !== '') throw new Error('expected empty'); });
t('plain string unchanged', () => { if(escapeHtml('hello') !== 'hello') throw new Error('changed'); });
t('& escaped', () => { if(!escapeHtml('a & b').includes('&amp;')) throw new Error('not escaped'); });
t('< escaped', () => { if(!escapeHtml('<x>').includes('&lt;')) throw new Error('not escaped'); });
t('" escaped', () => { if(!escapeHtml('"hi"').includes('&quot;')) throw new Error('not escaped'); });
t("' escaped", () => { if(!escapeHtml("it's").includes('&#039;')) throw new Error('not escaped'); });
t('XSS payload escaped', () => { const r=escapeHtml('<img onerror=alert(1)>'); if(r.includes('<img')) throw new Error('XSS not escaped'); });
t('number coerced', () => { if(escapeHtml(42) !== '42') throw new Error('not 42'); });

// renderServiceStatus
console.log('\n--- renderServiceStatus ---');
t('null → empty', () => { if(renderServiceStatus(null).trim() !== '') throw new Error(); });
t('all available → empty', () => { if(renderServiceStatus({groq:'available',weather:'available',maps:'available'}).trim() !== '') throw new Error('expected empty'); });
t('groq unavailable → banner', () => { if(!renderServiceStatus({groq:'unavailable',weather:'available',maps:'not_requested'}).includes('AI generation unavailable')) throw new Error(); });
t('weather degraded → banner', () => { if(!renderServiceStatus({groq:'available',weather:'degraded',maps:'not_requested'}).includes('Live weather data')) throw new Error(); });
t('maps degraded → banner', () => { if(!renderServiceStatus({groq:'available',weather:'available',maps:'degraded'}).includes('hospital lookup')) throw new Error(); });
t('maps not_requested → no maps warning', () => { if(renderServiceStatus({groq:'available',weather:'available',maps:'not_requested'}).trim() !== '') throw new Error(); });
t('multi-issue → multi ⚠️', () => { const count=(renderServiceStatus({groq:'unavailable',weather:'degraded',maps:'degraded'}).match(/⚠️/g)||[]).length; if(count<3) throw new Error('expected 3+ icons, got '+count); });

// renderActionPlan
console.log('\n--- renderActionPlan ---');
t('null,null → empty', () => { if(renderActionPlan(null,null).trim() !== '') throw new Error(); });
t('immediate_actions rendered', () => { const h=renderActionPlan({immediate_actions:['Call 112'],safety_warnings:[],emergency_contacts:[],when_to_seek_help:[],questions_to_ask_user:[]},null); if(!h.includes('Call 112')) throw new Error(); });
t('safety_warnings rendered', () => { const h=renderActionPlan({immediate_actions:[],safety_warnings:['No wading'],emergency_contacts:[],when_to_seek_help:[],questions_to_ask_user:[]},null); if(!h.includes('No wading')) throw new Error(); });
t('emergency_contacts rendered', () => { const h=renderActionPlan({immediate_actions:[],safety_warnings:[],emergency_contacts:['112'],when_to_seek_help:[],questions_to_ask_user:[]},null); if(!h.includes('112')) throw new Error(); });
t('when_to_seek_help rendered', () => { const h=renderActionPlan({immediate_actions:[],safety_warnings:[],emergency_contacts:[],when_to_seek_help:['Chest pain'],questions_to_ask_user:[]},null); if(!h.includes('Chest pain')) throw new Error(); });
t('legacy fallback when plan null', () => { const h=renderActionPlan(null,{immediate_first_aid:['Apply pressure'],what_not_to_do:['No movement'],call_these_services:['108']}); if(!h.includes('Apply pressure')) throw new Error(); });
t('legacy what_not_to_do', () => { const h=renderActionPlan(null,{immediate_first_aid:[],what_not_to_do:['No removal'],call_these_services:[]}); if(!h.includes('No removal')) throw new Error(); });
t('XSS in action escaped', () => { const h=renderActionPlan({immediate_actions:['<script>alert(1)</script>'],safety_warnings:[],emergency_contacts:[],when_to_seek_help:[],questions_to_ask_user:[]},null); if(h.includes('<script>')) throw new Error('XSS not escaped'); });

// renderWeather
console.log('\n--- renderWeather ---');
t('null → empty', () => { if(renderWeather(null) !== '') throw new Error(); });
t('safe badge', () => { if(!renderWeather({level:'safe',score:10}).includes('badge safe')) throw new Error(); });
t('critical badge', () => { if(!renderWeather({level:'critical',score:90}).includes('badge critical')) throw new Error(); });
t('warning badge', () => { if(!renderWeather({level:'warning',score:60}).includes('badge warning')) throw new Error(); });
t('score shown', () => { if(!renderWeather({level:'safe',score:15}).includes('15/100')) throw new Error(); });
t('temperature shown', () => { if(!renderWeather({level:'safe',condition:'Cloudy',temp_c:28}).includes('28°C')) throw new Error(); });
t('XSS in condition escaped', () => { const h=renderWeather({level:'critical',condition:'"><svg onload=1>'}); if(h.includes('<svg')) throw new Error('XSS not escaped'); });

// renderConfidence
console.log('\n--- renderConfidence ---');
t('null → empty', () => { if(renderConfidence(null) !== '') throw new Error(); });
t('high → safe badge', () => { if(!renderConfidence({confidence_level:'high',overall_confidence:0.87}).includes('badge safe')) throw new Error(); });
t('medium → watch badge', () => { if(!renderConfidence({confidence_level:'medium',overall_confidence:0.65}).includes('badge watch')) throw new Error(); });
t('low → critical badge', () => { if(!renderConfidence({confidence_level:'low',overall_confidence:0.3}).includes('badge critical')) throw new Error(); });
t('percentage shown', () => { if(!renderConfidence({confidence_level:'high',overall_confidence:0.87}).includes('87%')) throw new Error(); });
t('weather factor shown when low', () => { if(!renderConfidence({confidence_level:'low',overall_confidence:0.4,limiting_factor:'weather'}).includes('unavailable')) throw new Error(); });
t('triage factor shown when medium', () => { if(!renderConfidence({confidence_level:'medium',overall_confidence:0.55,limiting_factor:'triage'}).includes('ambiguous')) throw new Error(); });
t('factor NOT shown when high', () => { const h=renderConfidence({confidence_level:'high',overall_confidence:0.9,limiting_factor:'weather'}); if(h.includes('unavailable')) throw new Error('should not show factor when high'); });

// renderHospitals
console.log('\n--- renderHospitals ---');
t('null → empty', () => { if(renderHospitals(null, null) !== '') throw new Error(); });
t('empty array → empty', () => { if(renderHospitals([], null) !== '') throw new Error(); });
t('hospital with lat/lon shows map link', () => { const h=renderHospitals([{name:'City Hosp',lat:17.38,lon:78.46}],'available'); if(!h.includes('maps.google.com')) throw new Error(); });
t('hospital without lat/lon no map link', () => { const h=renderHospitals([{name:'Rural Clinic',address:'Road'}],'available'); if(h.includes('maps.google.com')) throw new Error('should not have map link'); });
t('degraded mapsStatus shows notice', () => { if(!renderHospitals([],'degraded').includes('temporarily unavailable')) throw new Error(); });
t('not_requested → empty', () => { if(renderHospitals([],'not_requested').trim() !== '') throw new Error(); });
t('XSS in hospital name escaped', () => { const h=renderHospitals([{name:'<script>xss</script>'}],'available'); if(h.includes('<script>')) throw new Error(); });
t('javascript: URI not injected into href', () => { const h=renderHospitals([{name:'Test',lat:'javascript:alert(1)',lon:0}],'available'); if(h.includes('href="javascript:')) throw new Error('javascript: URI must not appear'); });

// renderAssessmentResult
console.log('\n--- renderAssessmentResult ---');
const MOCK = {
  emergency_level:'High', triage:{category:'flooding'},
  weather:{level:'warning',score:60,condition:'Heavy rain'},
  confidence:{confidence_level:'medium',overall_confidence:0.65},
  action_plan:{immediate_actions:['Move to higher ground'],safety_warnings:['No wading'],emergency_contacts:['112'],when_to_seek_help:['Water at chest'],questions_to_ask_user:[],explanation:'Flooding emergency'},
  hospitals:[{name:'Test Hospital',lat:17.38,lon:78.46}],
  service_status:{groq:'available',weather:'available',maps:'available'},
  whats_happening:'',
};

t('does not throw', () => { renderAssessmentResult(MOCK,'flooding'); });
t('shows HIGH PRIORITY badge', () => { if(!renderAssessmentResult(MOCK,'flooding').includes('HIGH PRIORITY')) throw new Error(); });
t('shows immediate action', () => { if(!renderAssessmentResult(MOCK,'flooding').includes('Move to higher ground')) throw new Error(); });
t('shows safety warning', () => { if(!renderAssessmentResult(MOCK,'flooding').includes('No wading')) throw new Error(); });
t('shows emergency contact', () => { if(!renderAssessmentResult(MOCK,'flooding').includes('112')) throw new Error(); });
t('includes SOS button', () => { if(!renderAssessmentResult(MOCK,'flooding').includes('assessSosTriggerBtn')) throw new Error(); });
t('SOS button text present', () => { if(!renderAssessmentResult(MOCK,'flooding').includes('Send One-Tap SOS Alert')) throw new Error(); });
t('SOS button not auto-disabled', () => { if(renderAssessmentResult(MOCK,'flooding').includes('disabled')) throw new Error('button should not be disabled'); });
t('hospital shown', () => { if(!renderAssessmentResult(MOCK,'flooding').includes('Test Hospital')) throw new Error(); });
t('weather hazard shown', () => { const h=renderAssessmentResult(MOCK,'flooding'); if(!h.includes('Weather Hazard Level')) throw new Error(); });
t('confidence shown', () => { const h=renderAssessmentResult(MOCK,'flooding'); if(!h.includes('Assessment Confidence')) throw new Error(); });
t('legacy fallback renders', () => { const leg={emergency_level:'Moderate',triage:{category:'injury'},immediate_first_aid:['Apply pressure'],what_not_to_do:['No removal'],call_these_services:['108'],whats_happening:'Bleeding',service_status:{},hospitals:[],confidence:null,weather:null,action_plan:null}; const h=renderAssessmentResult(leg,'test'); if(!h.includes('Apply pressure')) throw new Error(); });
t('degradation banner shows when groq unavailable', () => { const deg={...MOCK,service_status:{groq:'unavailable',weather:'available',maps:'not_requested'}}; if(!renderAssessmentResult(deg,'test').includes('AI generation unavailable')) throw new Error(); });
t('XSS in whats_happening escaped', () => { const xss={...MOCK,action_plan:null,whats_happening:'<script>alert(1)</script>'}; if(renderAssessmentResult(xss,'test').includes('<script>alert')) throw new Error(); });

// Summary
console.log('\n==============================');
console.log(`TOTAL: ${passed+failed}  ✅ PASSED: ${passed}  ❌ FAILED: ${failed}`);
if (failed > 0) { process.exit(1); }
else { console.log('\n✅  All Step 8 frontend renderer tests passed.\n'); }
