/**
 * FloraChain B2B — Phase 12 Nursery Dashboard UI Test Suite
 * Tests DOM structure, buyer KPI summary cards, inbound shipments table,
 * purchase orders table, wholesale invoices & due dates table, commercial statement box,
 * recent ledger activity table, full ledger modal, and exported JS functions.
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
console.log('FLORACHAIN B2B — PHASE 12 NURSERY BUYER DASHBOARD UI TESTS');
console.log('====================================================================\n');

// ----------------------------------------------------------------------------
// TEST GROUP 1: Nursery Portal View Container & Header Banner
// ----------------------------------------------------------------------------
console.log('--- TEST GROUP 1: Nursery Portal Container & Header Banner ---');

assert(
  html.includes('id="view-nursery"'),
  'index.html contains #view-nursery view container',
  'Missing #view-nursery'
);

assert(
  html.includes('id="nursery-banner-name"'),
  'Contains #nursery-banner-name for dynamic buyer business name',
  'Missing #nursery-banner-name'
);

assert(
  html.includes('id="nursery-banner-desc"'),
  'Contains #nursery-banner-desc for dynamic buyer profile details',
  'Missing #nursery-banner-desc'
);

assert(
  html.includes('onclick="fetchAndRenderNurseryDashboard()"'),
  'Header has refresh button calling fetchAndRenderNurseryDashboard()',
  'Missing refresh button with fetchAndRenderNurseryDashboard()'
);

// ----------------------------------------------------------------------------
// TEST GROUP 2: KPI Summary Cards (6-Card Buyer Operations & Finance)
// ----------------------------------------------------------------------------
console.log('\n--- TEST GROUP 2: Nursery KPI Summary Cards ---');

assert(
  html.includes('id="kpi-nursery-orders"'),
  'Contains #kpi-nursery-orders for Active Purchase Orders',
  'Missing #kpi-nursery-orders'
);

assert(
  html.includes('id="kpi-nursery-trucks"'),
  'Contains #kpi-nursery-trucks for Inbound Deliveries / Staged Trucks',
  'Missing #kpi-nursery-trucks'
);

assert(
  html.includes('id="kpi-nursery-outstanding-principal"'),
  'Contains #kpi-nursery-outstanding-principal for Outstanding Invoiced Principal',
  'Missing #kpi-nursery-outstanding-principal'
);

assert(
  html.includes('id="kpi-nursery-unallocated-advances"'),
  'Contains #kpi-nursery-unallocated-advances for Unallocated Advance Credits',
  'Missing #kpi-nursery-unallocated-advances'
);

assert(
  html.includes('id="kpi-nursery-accrued-interest"'),
  'Contains #kpi-nursery-accrued-interest for Accrued Late-Payment Interest',
  'Missing #kpi-nursery-accrued-interest'
);

assert(
  html.includes('id="kpi-nursery-net-balance"'),
  'Contains #kpi-nursery-net-balance for Net Commercial Balance Due',
  'Missing #kpi-nursery-net-balance'
);

// ----------------------------------------------------------------------------
// TEST GROUP 3: Inbound Shipments & Dock Inspection Table
// ----------------------------------------------------------------------------
console.log('\n--- TEST GROUP 3: Inbound Shipments Table ---');

assert(
  html.includes('id="nursery-inbound-table"'),
  'Contains #nursery-inbound-table for scheduled vehicle arrivals',
  'Missing #nursery-inbound-table'
);

assert(
  html.includes('id="nursery-inbound-tbody"'),
  'Contains #nursery-inbound-tbody for dynamic arrival rows',
  'Missing #nursery-inbound-tbody'
);

// ----------------------------------------------------------------------------
// TEST GROUP 4: Purchase Orders History Table
// ----------------------------------------------------------------------------
console.log('\n--- TEST GROUP 4: Purchase Orders Table ---');

assert(
  html.includes('id="nursery-orders-table"'),
  'Contains #nursery-orders-table for plant purchase orders',
  'Missing #nursery-orders-table'
);

assert(
  html.includes('id="nursery-orders-tbody"'),
  'Contains #nursery-orders-tbody for dynamic order rows',
  'Missing #nursery-orders-tbody'
);

// ----------------------------------------------------------------------------
// TEST GROUP 5: Wholesale Invoices & Due Dates Table
// ----------------------------------------------------------------------------
console.log('\n--- TEST GROUP 5: Wholesale Invoices Table ---');

assert(
  html.includes('id="nursery-invoices-table"'),
  'Contains #nursery-invoices-table for wholesale invoices',
  'Missing #nursery-invoices-table'
);

assert(
  html.includes('id="nursery-invoices-tbody"'),
  'Contains #nursery-invoices-tbody for dynamic invoice rows',
  'Missing #nursery-invoices-tbody'
);

// ----------------------------------------------------------------------------
// TEST GROUP 6: Commercial Account Statement Box & Fields
// ----------------------------------------------------------------------------
console.log('\n--- TEST GROUP 6: Commercial Account Statement Box ---');

assert(
  html.includes('id="nursery-statement-gross"'),
  'Contains #nursery-statement-gross for gross invoiced purchases',
  'Missing #nursery-statement-gross'
);

assert(
  html.includes('id="nursery-statement-paid"'),
  'Contains #nursery-statement-paid for allocated payments settled',
  'Missing #nursery-statement-paid'
);

assert(
  html.includes('id="nursery-statement-advances"'),
  'Contains #nursery-statement-advances for unallocated advance deposits',
  'Missing #nursery-statement-advances'
);

assert(
  html.includes('id="nursery-statement-principal"'),
  'Contains #nursery-statement-principal for outstanding principal',
  'Missing #nursery-statement-principal'
);

assert(
  html.includes('id="nursery-statement-interest"'),
  'Contains #nursery-statement-interest for contractual late interest',
  'Missing #nursery-statement-interest'
);

assert(
  html.includes('id="nursery-statement-net"'),
  'Contains #nursery-statement-net for net balance payable',
  'Missing #nursery-statement-net'
);

// ----------------------------------------------------------------------------
// TEST GROUP 7: Recent Ledger Activity & Full Statement Modal
// ----------------------------------------------------------------------------
console.log('\n--- TEST GROUP 7: Ledger Activity & Statement Modal ---');

assert(
  html.includes('id="nursery-ledger-table"'),
  'Contains #nursery-ledger-table for recent transactions snippet',
  'Missing #nursery-ledger-table'
);

assert(
  html.includes('id="nursery-ledger-tbody"'),
  'Contains #nursery-ledger-tbody for recent transactions rows',
  'Missing #nursery-ledger-tbody'
);

assert(
  html.includes('id="nursery-ledger-modal"'),
  'Contains #nursery-ledger-modal for complete statement view',
  'Missing #nursery-ledger-modal'
);

assert(
  html.includes('id="nursery-modal-ledger-tbody"'),
  'Contains #nursery-modal-ledger-tbody for modal statement rows',
  'Missing #nursery-modal-ledger-tbody'
);

assert(
  html.includes('onclick="openNurseryLedgerModal()"'),
  'Contains action button calling openNurseryLedgerModal()',
  'Missing openNurseryLedgerModal button'
);

assert(
  html.includes('onclick="closeNurseryLedgerModal()"'),
  'Contains close button calling closeNurseryLedgerModal()',
  'Missing closeNurseryLedgerModal button'
);

// ----------------------------------------------------------------------------
// TEST GROUP 8: Agreed Deal Terms Table
// ----------------------------------------------------------------------------
console.log('\n--- TEST GROUP 8: Agreed Deal Terms Table ---');

assert(
  html.includes('id="nursery-agreements-table"'),
  'Contains #nursery-agreements-table for agreed deal contracts',
  'Missing #nursery-agreements-table'
);

assert(
  html.includes('id="nursery-agreements-tbody"'),
  'Contains #nursery-agreements-tbody for dynamic agreement rows',
  'Missing #nursery-agreements-tbody'
);

// ----------------------------------------------------------------------------
// TEST GROUP 9: JavaScript Exported Functions & Engine Integrity
// ----------------------------------------------------------------------------
console.log('\n--- TEST GROUP 9: JavaScript Phase 12 Functions ---');

assert(
  typeof app.fetchAndRenderNurseryDashboard === 'function',
  'fetchAndRenderNurseryDashboard is exported as a function',
  'fetchAndRenderNurseryDashboard missing from exports'
);

assert(
  typeof app.renderNurseryInboundTable === 'function',
  'renderNurseryInboundTable is exported as a function',
  'renderNurseryInboundTable missing from exports'
);

assert(
  typeof app.renderNurseryOrdersTable === 'function',
  'renderNurseryOrdersTable is exported as a function',
  'renderNurseryOrdersTable missing from exports'
);

assert(
  typeof app.renderNurseryInvoicesTable === 'function',
  'renderNurseryInvoicesTable is exported as a function',
  'renderNurseryInvoicesTable missing from exports'
);

assert(
  typeof app.renderNurseryLedgerTable === 'function',
  'renderNurseryLedgerTable is exported as a function',
  'renderNurseryLedgerTable missing from exports'
);

assert(
  typeof app.renderNurseryAgreementsTable === 'function',
  'renderNurseryAgreementsTable is exported as a function',
  'renderNurseryAgreementsTable missing from exports'
);

assert(
  typeof app.openNurseryLedgerModal === 'function',
  'openNurseryLedgerModal is exported as a function',
  'openNurseryLedgerModal missing from exports'
);

assert(
  typeof app.closeNurseryLedgerModal === 'function',
  'closeNurseryLedgerModal is exported as a function',
  'closeNurseryLedgerModal missing from exports'
);

// ----------------------------------------------------------------------------
// TEST GROUP 10: Table Rendering Behavior (Mock DOM Test)
// ----------------------------------------------------------------------------
console.log('\n--- TEST GROUP 10: Table Empty & Populated Rendering Logic ---');

// Mock a lightweight document environment for rendering tests
const mockElements = {};
function createMockElement(id) {
  return {
    id,
    innerHTML: '',
    textContent: '',
    style: {}
  };
}

const elementIds = [
  'nursery-inbound-tbody',
  'nursery-orders-tbody',
  'nursery-invoices-tbody',
  'nursery-ledger-tbody',
  'nursery-agreements-tbody',
  'nursery-modal-ledger-tbody',
  'nursery-ledger-modal',
  'nursery-banner-name',
  'nursery-banner-desc',
  'kpi-nursery-orders',
  'kpi-nursery-orders-subtext',
  'kpi-nursery-trucks',
  'kpi-nursery-trucks-subtext',
  'kpi-nursery-outstanding-principal',
  'kpi-nursery-unallocated-advances',
  'kpi-nursery-accrued-interest',
  'kpi-nursery-net-balance',
  'nursery-statement-gross',
  'nursery-statement-paid',
  'nursery-statement-advances',
  'nursery-statement-principal',
  'nursery-statement-interest',
  'nursery-statement-net'
];

elementIds.forEach(id => {
  mockElements[id] = createMockElement(id);
});

global.document = {
  getElementById: (id) => mockElements[id] || null
};

// 1. Test empty state rendering
app.renderNurseryInboundTable([]);
assert(
  mockElements['nursery-inbound-tbody'].innerHTML.includes('No inbound plant shipments'),
  'renderNurseryInboundTable handles empty array with clear message',
  'Empty state failed'
);

app.renderNurseryOrdersTable([]);
assert(
  mockElements['nursery-orders-tbody'].innerHTML.includes('No purchase orders placed yet'),
  'renderNurseryOrdersTable handles empty array with clear message',
  'Empty state failed'
);

app.renderNurseryInvoicesTable([]);
assert(
  mockElements['nursery-invoices-tbody'].innerHTML.includes('No wholesale invoices'),
  'renderNurseryInvoicesTable handles empty array with clear message',
  'Empty state failed'
);

app.renderNurseryLedgerTable([]);
assert(
  mockElements['nursery-ledger-tbody'].innerHTML.includes('No recent ledger transactions'),
  'renderNurseryLedgerTable handles empty array with clear message',
  'Empty state failed'
);

app.renderNurseryAgreementsTable([]);
assert(
  mockElements['nursery-agreements-tbody'].innerHTML.includes('No active deal agreements'),
  'renderNurseryAgreementsTable handles empty array with clear message',
  'Empty state failed'
);

// 2. Test populated state rendering
const sampleOrders = [{
  order_id: 'ORD-TEST-99',
  variety: 'Ficus Benjamina (5-Gallon)',
  ordered_qty: 150,
  created_at: '2026-11-03 09:00:00',
  total_amount: 37500.0,
  status: 'DISPATCHED'
}];

app.renderNurseryOrdersTable(sampleOrders);
assert(
  mockElements['nursery-orders-tbody'].innerHTML.includes('ORD-TEST-99') &&
  mockElements['nursery-orders-tbody'].innerHTML.includes('Ficus Benjamina') &&
  mockElements['nursery-orders-tbody'].innerHTML.includes('openOrderDetailModal'),
  'renderNurseryOrdersTable renders order rows with link to openOrderDetailModal',
  'Order row rendering failed'
);

const sampleInvoices = [{
  invoice_number: 'INV-2026-99',
  order_id: 'ORD-TEST-99',
  due_date: '2026-11-13',
  due_status: 'NOT_DUE',
  overdue_days: 0,
  outstanding_principal: 30000.0,
  accrued_interest: 0.0,
  total_payable: 30000.0,
  status: 'ISSUED'
}];

app.renderNurseryInvoicesTable(sampleInvoices);
assert(
  mockElements['nursery-invoices-tbody'].innerHTML.includes('INV-2026-99') &&
  mockElements['nursery-invoices-tbody'].innerHTML.includes('openInvoiceDetailModal'),
  'renderNurseryInvoicesTable renders invoice rows with link to openInvoiceDetailModal',
  'Invoice row rendering failed'
);

const sampleTransactions = [{
  transaction_date: '2026-11-03',
  type: 'INVOICE',
  reference_id: 'INV-2026-99',
  direction: 'DEBIT',
  amount: 37500.0
}];

app.renderNurseryLedgerTable(sampleTransactions);
assert(
  mockElements['nursery-ledger-tbody'].innerHTML.includes('INV-2026-99') &&
  mockElements['nursery-ledger-tbody'].innerHTML.includes('- '),
  'renderNurseryLedgerTable renders debit direction with minus sign',
  'Ledger row rendering failed'
);

// 3. Test modal open/close
app.openNurseryLedgerModal();
assert(
  mockElements['nursery-ledger-modal'].style.display === 'flex',
  'openNurseryLedgerModal displays the modal as flex',
  'Modal open failed'
);

app.closeNurseryLedgerModal();
assert(
  mockElements['nursery-ledger-modal'].style.display === 'none',
  'closeNurseryLedgerModal hides the modal as none',
  'Modal close failed'
);

// ----------------------------------------------------------------------------
// Summary
// ----------------------------------------------------------------------------
console.log('\n====================================================================');
console.log(`TEST RESULTS: ${passed} passed, ${failed} failed`);
console.log('====================================================================\n');

if (failed > 0) {
  process.exit(1);
} else {
  process.exit(0);
}

