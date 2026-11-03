/**
 * FloraChain B2B — Phase 9 Wholesale Payment Management UI Test Suite
 * Tests DOM structure, subpage elements, record/detail modals, invoice integration, and exported JS engine functions.
 */

const fs = require('fs');
const path = require('path');

const htmlPath = path.join(__dirname, '..', 'index.html');
const jsPath = path.join(__dirname, '..', 'app', 'static', 'js', 'app.js');

const html = fs.readFileSync(htmlPath, 'utf-8');
const app = require(jsPath);

let passed = 0;
let failed = 0;

function assert(condition, testName, errMsg) {
  if (condition) {
    console.log(`  [PASS] ${testName}`);
    passed++;
  } else {
    console.error(`  [FAIL] ${testName}: ${errMsg || 'Assertion failed'}`);
    failed++;
  }
}

console.log('====================================================================');
console.log('FLORACHAIN B2B — PHASE 9 PAYMENT MANAGEMENT UI TEST SUITE');
console.log('====================================================================\n');

// ----------------------------------------------------------------------------
// TEST GROUP 1: Sidebar & Subpage Container
// ----------------------------------------------------------------------------
console.log('--- TEST GROUP 1: Sidebar & Subpage DOM Elements ---');
assert(
  html.includes('id="slink-Payments"'),
  'index.html contains sidebar link for Payments (#slink-Payments)',
  'Missing id="slink-Payments"'
);

assert(
  html.includes('id="supplier-page-payments"'),
  'index.html contains #supplier-page-payments subpage container',
  'Missing id="supplier-page-payments"'
);

assert(
  html.includes('id="kpi-payments-total-received"') &&
  html.includes('id="kpi-payments-outstanding-balance"') &&
  html.includes('id="kpi-payments-invoices-settled"') &&
  html.includes('id="kpi-payments-advance-balance"'),
  'index.html contains 4 KPI summary cards for Payments',
  'Missing one or more payment KPI card IDs'
);

assert(
  html.includes('id="payments-search-input"') &&
  html.includes('id="payments-status-pills"') &&
  html.includes('id="payments-method-pills"'),
  'index.html contains Payments search and method/status filter toolbar elements',
  'Missing search input or filter pill groups'
);

assert(
  html.includes('id="payments-table-tbody"'),
  'index.html contains Payments table with tbody id="payments-table-tbody"',
  'Missing id="payments-table-tbody"'
);

// ----------------------------------------------------------------------------
// TEST GROUP 2: Record Payment Receipt Modal
// ----------------------------------------------------------------------------
console.log('\n--- TEST GROUP 2: Record Payment Modal DOM Elements ---');
assert(
  html.includes('id="record-payment-modal"'),
  'index.html contains #record-payment-modal backdrop',
  'Missing id="record-payment-modal"'
);

assert(
  html.includes('id="pay-form-invoice-select"'),
  'Record Payment modal contains target invoice/advance selector dropdown',
  'Missing id="pay-form-invoice-select"'
);

assert(
  html.includes('id="pay-balance-preview-box"') &&
  html.includes('id="pay-preview-inv-total"') &&
  html.includes('id="pay-preview-paid-total"') &&
  html.includes('id="pay-preview-balance-due"'),
  'Record Payment modal contains live financial balance preview box',
  'Missing balance preview fields'
);

assert(
  html.includes('id="pay-form-amount"') &&
  html.includes('id="pay-form-date"') &&
  html.includes('id="pay-form-method"') &&
  html.includes('id="pay-form-reference"'),
  'Record Payment modal contains amount, date, method, and reference inputs',
  'Missing payment form inputs'
);

assert(
  html.includes('id="btn-submit-record-payment"'),
  'Record Payment modal contains submit button id="btn-submit-record-payment"',
  'Missing id="btn-submit-record-payment"'
);

// ----------------------------------------------------------------------------
// TEST GROUP 3: Payment Detail & Receipt Modal
// ----------------------------------------------------------------------------
console.log('\n--- TEST GROUP 3: Payment Detail Modal DOM Elements ---');
assert(
  html.includes('id="payment-detail-modal"'),
  'index.html contains #payment-detail-modal backdrop',
  'Missing id="payment-detail-modal"'
);

assert(
  html.includes('id="modal-pay-number"') &&
  html.includes('id="modal-pay-amount"') &&
  html.includes('id="modal-pay-date"') &&
  html.includes('id="modal-pay-status-badge"'),
  'Payment Detail modal contains receipt number, amount, date, and status badge',
  'Missing payment receipt header elements'
);

assert(
  html.includes('id="modal-pay-nursery-name"') &&
  html.includes('id="modal-pay-supplier-name"'),
  'Payment Detail modal contains counterparty buyer and supplier boxes',
  'Missing counterparty name boxes'
);

assert(
  html.includes('id="modal-pay-reversal-banner"') &&
  html.includes('id="btn-modal-reverse-payment"'),
  'Payment Detail modal contains reversal audit banner and action button',
  'Missing reversal banner or button'
);

assert(
  html.includes('id="modal-pay-allocations-tbody"'),
  'Payment Detail modal contains invoice allocations table tbody id="modal-pay-allocations-tbody"',
  'Missing id="modal-pay-allocations-tbody"'
);

// ----------------------------------------------------------------------------
// TEST GROUP 4: Invoice Integration (Payment Summary in Invoice Modal)
// ----------------------------------------------------------------------------
console.log('\n--- TEST GROUP 4: Invoice Detail Modal Payment Integration ---');
assert(
  html.includes('id="modal-inv-pay-total"') &&
  html.includes('id="modal-inv-total-paid"') &&
  html.includes('id="modal-inv-balance-due"') &&
  html.includes('id="modal-inv-payment-badge"'),
  'Invoice Detail modal integrates Payment & Settlement Summary fields',
  'Missing payment summary fields in invoice modal'
);

assert(
  html.includes('id="modal-inv-payments-tbody"'),
  'Invoice Detail modal contains recorded payment receipts table tbody',
  'Missing id="modal-inv-payments-tbody"'
);

assert(
  html.includes('id="btn-modal-inv-record-payment"'),
  'Invoice Detail modal contains Record Payment action button',
  'Missing id="btn-modal-inv-record-payment"'
);

// ----------------------------------------------------------------------------
// TEST GROUP 5: JavaScript Engine & Helper Functions
// ----------------------------------------------------------------------------
console.log('\n--- TEST GROUP 5: JavaScript Engine & Helper Functions ---');
assert(
  typeof app.formatPaymentStatusBadge === 'function' &&
  app.formatPaymentStatusBadge('RECORDED').includes('RECORDED') &&
  app.formatPaymentStatusBadge('REVERSED').includes('REVERSED'),
  'formatPaymentStatusBadge generates appropriate badges for statuses',
  'formatPaymentStatusBadge failed'
);

assert(
  typeof app.formatPaymentMethodBadge === 'function' &&
  app.formatPaymentMethodBadge('BANK_TRANSFER').includes('Bank Transfer') &&
  app.formatPaymentMethodBadge('UPI').includes('UPI'),
  'formatPaymentMethodBadge generates formatted method badges',
  'formatPaymentMethodBadge failed'
);

assert(
  typeof app.formatPaymentCurrency === 'function' &&
  app.formatPaymentCurrency(41160).includes('41,160.00'),
  'formatPaymentCurrency correctly formats Indian Rupee amounts',
  'formatPaymentCurrency failed'
);

assert(
  typeof app.fetchAndRenderPayments === 'function' &&
  typeof app.openRecordPaymentModal === 'function' &&
  typeof app.closeRecordPaymentModal === 'function' &&
  typeof app.openPaymentDetailModal === 'function' &&
  typeof app.closePaymentDetailModal === 'function' &&
  typeof app.promptReversePayment === 'function',
  'Phase 9 payment management functions are exported in app.js',
  'Missing exported Phase 9 functions in app.js'
);

console.log('\n====================================================================');
console.log(`RESULTS: ${passed}/${passed + failed} passed, ${failed} failed`);
if (failed === 0) {
  console.log('ALL PHASE 9 FRONTEND UI TESTS PASSED SUCCESSFULLY!');
} else {
  console.error('SOME PHASE 9 TESTS FAILED.');
  process.exit(1);
}

