/**
 * FloraChain B2B — Phase 6: Order Management UI & Integration Test Suite
 * Tests DOM structure, modal elements, KPI cards, tables, formatting, and calculation helpers.
 */

const fs = require('fs');
const path = require('path');
const assert = require('assert');

console.log('====================================================================');
console.log('FLORACHAIN B2B — PHASE 6 ORDER MANAGEMENT UI TEST SUITE');
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

test('index.html contains sidebar link for Orders (#slink-Orders)', () => {
  assert(indexHtml.includes('id="slink-Orders"'), 'Missing id="slink-Orders"');
  assert(indexHtml.includes("selectSidebarItem('Orders')"), 'Missing onclick="selectSidebarItem(\'Orders\')"');
});

test('index.html contains #supplier-page-orders subpage container', () => {
  assert(indexHtml.includes('id="supplier-page-orders"'), 'Missing id="supplier-page-orders"');
  assert(indexHtml.includes('class="supplier-subpage"'), 'Missing class="supplier-subpage"');
});

test('index.html contains 4 KPI summary cards for Orders', () => {
  assert(indexHtml.includes('id="kpi-total-orders"'), 'Missing id="kpi-total-orders"');
  assert(indexHtml.includes('id="kpi-confirmed-orders"'), 'Missing id="kpi-confirmed-orders"');
  assert(indexHtml.includes('id="kpi-dispatched-orders"'), 'Missing id="kpi-dispatched-orders"');
  assert(indexHtml.includes('id="kpi-delivered-orders"'), 'Missing id="kpi-delivered-orders"');
});

test('index.html contains Orders search and filter toolbar elements', () => {
  assert(indexHtml.includes('id="order-search-input"'), 'Missing id="order-search-input"');
  assert(indexHtml.includes('id="order-search-clear"'), 'Missing id="order-search-clear"');
  assert(indexHtml.includes('id="pill-order-all"'), 'Missing id="pill-order-all"');
  assert(indexHtml.includes('id="pill-order-confirmed"'), 'Missing id="pill-order-confirmed"');
  assert(indexHtml.includes('id="pill-order-dispatched"'), 'Missing id="pill-order-dispatched"');
  assert(indexHtml.includes('id="pill-order-locked"'), 'Missing id="pill-order-locked"');
});

test('index.html contains Orders table with tbody id="orders-table-tbody"', () => {
  assert(indexHtml.includes('id="orders-table-tbody"'), 'Missing id="orders-table-tbody"');
  assert(indexHtml.includes('id="order-count-subtitle"'), 'Missing id="order-count-subtitle"');
});

console.log('\n--- TEST GROUP 2: Create Order Modal DOM Elements ---');

test('index.html contains #order-create-modal', () => {
  assert(indexHtml.includes('id="order-create-modal"'), 'Missing id="order-create-modal"');
  assert(indexHtml.includes('id="order-create-form"'), 'Missing id="order-create-form"');
});

test('Create Order modal contains nursery selector and multi-item table container', () => {
  assert(indexHtml.includes('id="order-form-nursery"'), 'Missing id="order-form-nursery"');
  assert(indexHtml.includes('id="order-form-items-list"'), 'Missing id="order-form-items-list"');
  assert(indexHtml.includes('onclick="addOrderItemRow()"'), 'Missing addOrderItemRow trigger');
});

test('Create Order modal contains total calculation summary fields', () => {
  assert(indexHtml.includes('id="order-form-total-qty"'), 'Missing id="order-form-total-qty"');
  assert(indexHtml.includes('id="order-form-total-value"'), 'Missing id="order-form-total-value"');
  assert(indexHtml.includes('id="btn-submit-order"'), 'Missing id="btn-submit-order"');
});

console.log('\n--- TEST GROUP 3: Order Details View Modal DOM Elements ---');

test('index.html contains #order-detail-modal and itemized lines table', () => {
  assert(indexHtml.includes('id="order-detail-modal"'), 'Missing id="order-detail-modal"');
  assert(indexHtml.includes('id="view-order-title"'), 'Missing id="view-order-title"');
  assert(indexHtml.includes('id="view-order-status-badge"'), 'Missing id="view-order-status-badge"');
  assert(indexHtml.includes('id="view-order-items-tbody"'), 'Missing id="view-order-items-tbody"');
  assert(indexHtml.includes('id="view-order-total-qty"'), 'Missing id="view-order-total-qty"');
  assert(indexHtml.includes('id="view-order-total-amount"'), 'Missing id="view-order-total-amount"');
});

test('Order Details modal integrates physical inspection and deal agreement boxes', () => {
  assert(indexHtml.includes('id="view-order-inspection-box"'), 'Missing id="view-order-inspection-box"');
  assert(indexHtml.includes('id="view-order-agreement-box"'), 'Missing id="view-order-agreement-box"');
});

console.log('\n--- TEST GROUP 4: JavaScript Helper & Formatting Functions ---');

test('formatOrderCurrency properly formats Indian currency amounts', () => {
  assert.strictEqual(app.formatOrderCurrency(350), '₹350.00');
  assert.strictEqual(app.formatOrderCurrency(52500), '₹52,500.00');
  assert.strictEqual(app.formatOrderCurrency(0), '₹0.00');
  assert.strictEqual(app.formatOrderCurrency('12500.5'), '₹12,500.50');
});

test('escapeOrderHtml prevents HTML injection', () => {
  assert.strictEqual(app.escapeOrderHtml('<script>alert("xss")</script>'), '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;');
  assert.strictEqual(app.escapeOrderHtml('Standard & Clean'), 'Standard &amp; Clean');
});

test('formatOrderStatusBadge generates appropriate badges for statuses', () => {
  assert(app.formatOrderStatusBadge('CONFIRMED').includes('badge-primary'));
  assert(app.formatOrderStatusBadge('DISPATCHED').includes('badge-info'));
  assert(app.formatOrderStatusBadge('LOCKED_VERIFIED').includes('badge-success'));
  assert(app.formatOrderStatusBadge('CANCELLED').includes('badge-danger'));
});

console.log('\n====================================================================');
console.log(`RESULTS: ${passedTests}/${totalTests} passed, ${totalTests - passedTests} failed`);
if (passedTests === totalTests) {
  console.log('ALL PHASE 6 FRONTEND UI TESTS PASSED SUCCESSFULLY!');
  process.exit(0);
} else {
  console.error('SOME TESTS FAILED');
  process.exit(1);
}

