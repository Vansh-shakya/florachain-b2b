/**
 * FloraChain B2B — Phase 8 Commercial Invoicing UI Test Suite
 * Tests DOM structure, subpage elements, modal components, and exported JS engine functions.
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
console.log('FLORACHAIN B2B — PHASE 8 COMMERCIAL INVOICING UI TEST SUITE');
console.log('====================================================================\n');

// ----------------------------------------------------------------------------
// TEST GROUP 1: Sidebar & Subpage Container
// ----------------------------------------------------------------------------
console.log('--- TEST GROUP 1: Sidebar & Subpage DOM Elements ---');
assert(
  html.includes('id="slink-Invoices"'),
  'index.html contains sidebar link for Invoices (#slink-Invoices)',
  'Missing id="slink-Invoices"'
);

assert(
  html.includes('id="supplier-page-invoices"'),
  'index.html contains #supplier-page-invoices subpage container',
  'Missing id="supplier-page-invoices"'
);

assert(
  html.includes('id="kpi-invoices-total-invoiced"') &&
  html.includes('id="kpi-invoices-active-count"') &&
  html.includes('id="kpi-invoices-units-invoiced"') &&
  html.includes('id="kpi-invoices-verified-ready"'),
  'index.html contains 4 KPI summary cards for Invoices',
  'Missing one or more invoice KPI card element IDs'
);

assert(
  html.includes('id="invoices-search-input"') &&
  html.includes('id="invoices-status-pills"'),
  'index.html contains Invoices search and filter toolbar elements',
  'Missing search input or status filter pills'
);

assert(
  html.includes('id="invoices-table-tbody"'),
  'index.html contains Invoices table with tbody id="invoices-table-tbody"',
  'Missing id="invoices-table-tbody"'
);

// ----------------------------------------------------------------------------
// TEST GROUP 2: Commercial Invoice Detail Modal
// ----------------------------------------------------------------------------
console.log('\n--- TEST GROUP 2: Commercial Invoice Detail Modal DOM Elements ---');
assert(
  html.includes('id="invoice-detail-modal"'),
  'index.html contains #invoice-detail-modal backdrop',
  'Missing id="invoice-detail-modal"'
);

assert(
  html.includes('id="modal-inv-number"') &&
  html.includes('id="modal-inv-date"') &&
  html.includes('id="modal-inv-order-id"') &&
  html.includes('id="modal-inv-status-badge"'),
  'Invoice modal contains invoice number, date, order ref, and status badge',
  'Missing invoice header metadata elements'
);

assert(
  html.includes('id="modal-inv-supplier-name"') &&
  html.includes('id="modal-inv-supplier-email"') &&
  html.includes('id="modal-inv-nursery-name"') &&
  html.includes('id="modal-inv-nursery-email"'),
  'Invoice modal contains counterparty supplier and nursery partner boxes',
  'Missing supplier or nursery profile elements'
);

assert(
  html.includes('id="modal-inv-truck-info"') &&
  html.includes('id="modal-inv-verification-info"') &&
  html.includes('id="modal-inv-damage-policy"'),
  'Invoice modal contains delivery verification and damage billing policy badge',
  'Missing verification or damage policy element'
);

assert(
  html.includes('id="modal-inv-items-table-tbody"'),
  'Invoice modal contains itemized lines table tbody id="modal-inv-items-table-tbody"',
  'Missing id="modal-inv-items-table-tbody"'
);

assert(
  html.includes('id="modal-inv-subtotal"') &&
  html.includes('id="modal-inv-tax"') &&
  html.includes('id="modal-inv-discount"') &&
  html.includes('id="modal-inv-grand-total"'),
  'Invoice modal contains subtotal, tax, discount, and grand total fields',
  'Missing one or more invoice financial summary elements'
);

assert(
  html.includes('printInvoiceModal()') &&
  html.includes('id="btn-cancel-invoice"'),
  'Invoice modal contains Print Invoice button and Cancel Invoice button',
  'Missing print or cancel action buttons'
);

// ----------------------------------------------------------------------------
// TEST GROUP 3: JavaScript Engine & Helper Functions
// ----------------------------------------------------------------------------
console.log('\n--- TEST GROUP 3: JavaScript Engine & Helper Functions ---');
assert(
  typeof app.formatInvoiceStatusBadge === 'function' &&
  app.formatInvoiceStatusBadge('ISSUED').includes('ISSUED') &&
  app.formatInvoiceStatusBadge('CANCELLED').includes('CANCELLED'),
  'formatInvoiceStatusBadge generates appropriate badges for statuses',
  'formatInvoiceStatusBadge function missing or defective'
);

assert(
  typeof app.formatInvoiceCurrency === 'function' &&
  app.formatInvoiceCurrency(41160.0).includes('41,160.00'),
  'formatInvoiceCurrency correctly formats Indian Rupee amounts',
  'formatInvoiceCurrency missing or incorrect'
);

assert(
  typeof app.fetchAndRenderInvoices === 'function' &&
  typeof app.updateInvoicesSummaryKPIs === 'function' &&
  typeof app.renderInvoicesTable === 'function' &&
  typeof app.openInvoiceDetailModal === 'function' &&
  typeof app.closeInvoiceDetailModal === 'function' &&
  typeof app.printInvoiceModal === 'function' &&
  typeof app.generateInvoiceForOrder === 'function',
  'Phase 8 invoicing functions are exported in app.js',
  'One or more Phase 8 functions not exported'
);

console.log('\n====================================================================');
console.log(`RESULTS: ${passed}/${passed + failed} passed, ${failed} failed`);
if (failed === 0) {
  console.log('ALL PHASE 8 FRONTEND UI TESTS PASSED SUCCESSFULLY!');
  process.exit(0);
} else {
  console.error('SOME PHASE 8 UI TESTS FAILED');
  process.exit(1);
}

