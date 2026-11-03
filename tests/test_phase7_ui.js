/**
 * FloraChain B2B — Phase 7: Truck Loading UI & Integration Test Suite
 * Tests DOM structure, modal elements, KPI cards, tables, formatting, and calculation helpers.
 */

const fs = require('fs');
const path = require('path');
const assert = require('assert');

console.log('====================================================================');
console.log('FLORACHAIN B2B — PHASE 7 TRUCK LOADING UI TEST SUITE');
console.log('====================================================================\n');

let passedTests = 0;
let totalTests = 0;

function test(name, fn) {
  totalTests++;
  try {
    fn();
    console.log(`  [PASS] ${name}`);
    passedTests++;
  } catch (err) {
    console.error(`  [FAIL] ${name}: ${err.message}`);
  }
}

// 1. Read index.html
const indexPath = path.join(__dirname, '..', 'index.html');
const indexHtml = fs.readFileSync(indexPath, 'utf-8');

// 2. Load app.js modules
const appJsPath = path.join(__dirname, '..', 'app', 'static', 'js', 'app.js');
const app = require(appJsPath);

console.log('--- TEST GROUP 1: Sidebar & Subpage DOM Elements ---');

test('index.html contains sidebar link for Truck Loading (#slink-TruckLoading)', () => {
  assert(indexHtml.includes('id="slink-TruckLoading"'), 'Missing id="slink-TruckLoading"');
  assert(indexHtml.includes("selectSidebarItem('Truck Loading')"), 'Missing onclick="selectSidebarItem(\'Truck Loading\')"');
});

test('index.html contains #supplier-page-truck-loading subpage container', () => {
  assert(indexHtml.includes('id="supplier-page-truck-loading"'), 'Missing id="supplier-page-truck-loading"');
});

test('index.html contains 4 KPI summary cards for Truck Loading', () => {
  assert(indexHtml.includes('id="kpi-truck-active-manifests"'), 'Missing id="kpi-truck-active-manifests"');
  assert(indexHtml.includes('id="kpi-truck-loaded-units"'), 'Missing id="kpi-truck-loaded-units"');
  assert(indexHtml.includes('id="kpi-truck-dispatched-count"'), 'Missing id="kpi-truck-dispatched-count"');
  assert(indexHtml.includes('id="kpi-truck-completed-count"'), 'Missing id="kpi-truck-completed-count"');
});

test('index.html contains Truck Loading search and filter toolbar elements', () => {
  assert(indexHtml.includes('id="truck-search-input"'), 'Missing id="truck-search-input"');
  assert(indexHtml.includes('id="truck-search-clear"'), 'Missing id="truck-search-clear"');
  assert(indexHtml.includes('id="pill-truck-all"'), 'Missing id="pill-truck-all"');
  assert(indexHtml.includes('id="pill-truck-staging"'), 'Missing id="pill-truck-staging"');
  assert(indexHtml.includes('id="pill-truck-dispatched"'), 'Missing id="pill-truck-dispatched"');
  assert(indexHtml.includes('id="pill-truck-completed"'), 'Missing id="pill-truck-completed"');
});

test('index.html contains Truck Manifests table with tbody id="truck-manifests-table-tbody"', () => {
  assert(indexHtml.includes('id="truck-manifests-table-tbody"'), 'Missing id="truck-manifests-table-tbody"');
  assert(indexHtml.includes('id="truck-count-subtitle"'), 'Missing id="truck-count-subtitle"');
});

console.log('\n--- TEST GROUP 2: Truck Loading Modal DOM Elements ---');

test('index.html contains #truck-loading-modal and form', () => {
  assert(indexHtml.includes('id="truck-loading-modal"'), 'Missing id="truck-loading-modal"');
  assert(indexHtml.includes('id="truck-loading-form"'), 'Missing id="truck-loading-form"');
});

test('Truck Loading modal contains vehicle registration and driver inputs', () => {
  assert(indexHtml.includes('id="truck-modal-truck-no"'), 'Missing id="truck-modal-truck-no"');
  assert(indexHtml.includes('id="truck-modal-driver-info"'), 'Missing id="truck-modal-driver-info"');
  assert(indexHtml.includes('id="truck-modal-notes"'), 'Missing id="truck-modal-notes"');
});

test('Truck Loading modal contains itemized varieties table and auto-load button', () => {
  assert(indexHtml.includes('id="truck-loading-modal-items-tbody"'), 'Missing id="truck-loading-modal-items-tbody"');
  assert(indexHtml.includes('id="btn-load-all-max"'), 'Missing id="btn-load-all-max"');
  assert(indexHtml.includes('onclick="autoLoadMaxAllItems()"'), 'Missing autoLoadMaxAllItems trigger');
});

test('Truck Loading modal contains progress bar and summary fields', () => {
  assert(indexHtml.includes('id="truck-modal-progress-bar"'), 'Missing id="truck-modal-progress-bar"');
  assert(indexHtml.includes('id="truck-modal-progress-pct"'), 'Missing id="truck-modal-progress-pct"');
  assert(indexHtml.includes('id="truck-modal-total-ordered"'), 'Missing id="truck-modal-total-ordered"');
  assert(indexHtml.includes('id="truck-modal-total-loaded"'), 'Missing id="truck-modal-total-loaded"');
  assert(indexHtml.includes('id="truck-modal-total-remaining"'), 'Missing id="truck-modal-total-remaining"');
});

test('Truck Loading modal contains staging save and dispatch action buttons', () => {
  assert(indexHtml.includes('id="btn-save-truck-staging"'), 'Missing id="btn-save-truck-staging"');
  assert(indexHtml.includes('id="btn-dispatch-truck"'), 'Missing id="btn-dispatch-truck"');
  assert(indexHtml.includes('submitTruckLoading(false)'), 'Missing submitTruckLoading(false)');
  assert(indexHtml.includes('submitTruckLoading(true)'), 'Missing submitTruckLoading(true)');
});

console.log('\n--- TEST GROUP 3: JavaScript Engine & Helper Functions ---');

test('formatTruckStatusBadge generates appropriate badges for statuses', () => {
  assert(app.formatTruckStatusBadge('CONFIRMED').includes('badge-primary'));
  assert(app.formatTruckStatusBadge('STAGING').includes('badge-warning'));
  assert(app.formatTruckStatusBadge('DISPATCHED').includes('badge-info'));
  assert(app.formatTruckStatusBadge('LOCKED_VERIFIED').includes('badge-success'));
  assert(app.formatTruckStatusBadge('CANCELLED').includes('badge-danger'));
});

test('Phase 7 functions are exported in app.js', () => {
  assert.strictEqual(typeof app.openTruckLoadingModal, 'function');
  assert.strictEqual(typeof app.closeTruckLoadingModal, 'function');
  assert.strictEqual(typeof app.handleTruckItemQtyChange, 'function');
  assert.strictEqual(typeof app.autoLoadMaxAllItems, 'function');
  assert.strictEqual(typeof app.updateTruckModalTotals, 'function');
  assert.strictEqual(typeof app.submitTruckLoading, 'function');
  assert.strictEqual(typeof app.setTruckStatusFilter, 'function');
  assert.strictEqual(typeof app.handleTruckSearch, 'function');
});

console.log('\n====================================================================');
console.log(`RESULTS: ${passedTests}/${totalTests} passed, ${totalTests - passedTests} failed`);
if (passedTests === totalTests) {
  console.log('ALL PHASE 7 FRONTEND UI TESTS PASSED SUCCESSFULLY!');
  process.exit(0);
} else {
  console.error('SOME TESTS FAILED');
  process.exit(1);
}

