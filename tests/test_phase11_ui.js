/**
 * FloraChain B2B — Phase 11 Commercial Ledger & Transaction History UI Test Suite
 * Tests DOM structure, KPI summary cards, filter toolbar, transaction table,
 * badge formatting, direction styling, and exported JS functions.
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
console.log('FLORACHAIN B2B — PHASE 11 COMMERCIAL LEDGER & TRANSACTION HISTORY UI TESTS');
console.log('====================================================================\n');

// ----------------------------------------------------------------------------
// TEST GROUP 1: Sidebar Navigation Items
// ----------------------------------------------------------------------------
console.log('--- TEST GROUP 1: Sidebar Navigation Items ---');

assert(
  html.includes('id="slink-Ledger"'),
  'index.html contains #slink-Ledger sidebar link',
  'Missing #slink-Ledger'
);

assert(
  html.includes('id="slink-History"'),
  'index.html contains #slink-History sidebar link',
  'Missing #slink-History'
);

// ----------------------------------------------------------------------------
// TEST GROUP 2: Ledger Subpage Container & Page Header
// ----------------------------------------------------------------------------
console.log('\n--- TEST GROUP 2: Ledger Subpage Container & Header ---');

assert(
  html.includes('id="supplier-page-ledger"'),
  'index.html contains #supplier-page-ledger container',
  'Missing #supplier-page-ledger'
);

assert(
  html.includes('Commercial Ledger & Transaction History') || html.includes('Commercial Ledger &amp; Transaction History'),
  'Ledger page header contains correct title text',
  'Missing subpage title'
);

assert(
  html.includes('onclick="fetchAndRenderLedger()"'),
  'Ledger header has refresh button calling fetchAndRenderLedger()',
  'Missing refresh button with fetchAndRenderLedger()'
);

// ----------------------------------------------------------------------------
// TEST GROUP 3: KPI Summary Cards (6-Card Financial Metrics)
// ----------------------------------------------------------------------------
console.log('\n--- TEST GROUP 3: KPI Summary Cards ---');

assert(
  html.includes('id="kpi-ledger-total-invoiced"'),
  'Contains #kpi-ledger-total-invoiced for Total Invoiced Gross',
  'Missing #kpi-ledger-total-invoiced'
);

assert(
  html.includes('id="kpi-ledger-total-paid"'),
  'Contains #kpi-ledger-total-paid for Total Payments Received',
  'Missing #kpi-ledger-total-paid'
);

assert(
  html.includes('id="kpi-ledger-outstanding-principal"'),
  'Contains #kpi-ledger-outstanding-principal for Outstanding Principal',
  'Missing #kpi-ledger-outstanding-principal'
);

assert(
  html.includes('id="kpi-ledger-unallocated-advances"'),
  'Contains #kpi-ledger-unallocated-advances for Unallocated Advances',
  'Missing #kpi-ledger-unallocated-advances'
);

assert(
  html.includes('id="kpi-ledger-accrued-interest"'),
  'Contains #kpi-ledger-accrued-interest for Accrued Late-Payment Interest',
  'Missing #kpi-ledger-accrued-interest'
);

assert(
  html.includes('id="kpi-ledger-net-balance"'),
  'Contains #kpi-ledger-net-balance for Net Balance Due',
  'Missing #kpi-ledger-net-balance'
);

// ----------------------------------------------------------------------------
// TEST GROUP 4: Search & Filter Toolbar
// ----------------------------------------------------------------------------
console.log('\n--- TEST GROUP 4: Search & Filter Toolbar ---');

assert(
  html.includes('id="ledger-search-input"'),
  'Contains #ledger-search-input for text searching',
  'Missing #ledger-search-input'
);

assert(
  html.includes('id="btn-clear-ledger-search"'),
  'Contains #btn-clear-ledger-search button',
  'Missing #btn-clear-ledger-search'
);

assert(
  html.includes('id="ledger-nursery-select"'),
  'Contains #ledger-nursery-select counterparty dropdown',
  'Missing #ledger-nursery-select'
);

assert(
  html.includes('id="ledger-type-pills"'),
  'Contains #ledger-type-pills filter pill container',
  'Missing #ledger-type-pills'
);

assert(
  html.includes('data-type="ALL"') &&
  html.includes('data-type="INVOICE"') &&
  html.includes('data-type="PAYMENT"') &&
  html.includes('data-type="ADVANCE"') &&
  html.includes('data-type="REVERSAL"') &&
  html.includes('data-type="TERMS"') &&
  html.includes('data-type="DELIVERY"'),
  'Type filter pills include ALL, INVOICE, PAYMENT, ADVANCE, REVERSAL, TERMS, DELIVERY',
  'Missing one or more data-type attribute values'
);

assert(
  html.includes('id="ledger-start-date"') && html.includes('id="ledger-end-date"'),
  'Contains #ledger-start-date and #ledger-end-date date range inputs',
  'Missing date range inputs'
);

assert(
  html.includes('id="ledger-sort-order"'),
  'Contains #ledger-sort-order sort selector',
  'Missing #ledger-sort-order'
);

// ----------------------------------------------------------------------------
// TEST GROUP 5: Ledger Table Structure
// ----------------------------------------------------------------------------
console.log('\n--- TEST GROUP 5: Ledger Table Structure ---');

assert(
  html.includes('id="ledger-table"'),
  'Contains #ledger-table element',
  'Missing #ledger-table'
);

assert(
  html.includes('id="ledger-table-tbody"'),
  'Contains #ledger-table-tbody element',
  'Missing #ledger-table-tbody'
);

assert(
  html.includes('<th>Date</th>') &&
  html.includes('<th>Type</th>') &&
  html.includes('<th>Ref #</th>') &&
  html.includes('<th>Related Ref</th>') &&
  html.includes('<th>Counterparty</th>') &&
  html.includes('<th>Flow</th>') &&
  html.includes('Amount (₹)') &&
  html.includes('<th>Status</th>') &&
  html.includes('<th>Narration / Context</th>'),
  'Ledger table has all 9 authoritative column headers',
  'Missing one or more ledger table columns'
);

// ----------------------------------------------------------------------------
// TEST GROUP 6: JavaScript Engine Functions & Formatters
// ----------------------------------------------------------------------------
console.log('\n--- TEST GROUP 6: JavaScript Engine Functions & Formatters ---');

assert(
  typeof app.formatLedgerCurrency === 'function',
  'app.formatLedgerCurrency is exported as function',
  'formatLedgerCurrency not exported'
);

assert(
  app.formatLedgerCurrency(12345.67) === '₹12,345.67',
  'formatLedgerCurrency formats currency with commas and ₹ symbol',
  `Unexpected format: ${app.formatLedgerCurrency(12345.67)}`
);

assert(
  typeof app.formatLedgerTypeBadge === 'function',
  'app.formatLedgerTypeBadge is exported as function',
  'formatLedgerTypeBadge not exported'
);

const invBadge = app.formatLedgerTypeBadge('INVOICE_ISSUED');
assert(
  invBadge.includes('Invoice Issued') && invBadge.includes('badge'),
  'formatLedgerTypeBadge renders Invoice Issued badge',
  `Unexpected badge: ${invBadge}`
);

const payBadge = app.formatLedgerTypeBadge('PAYMENT_RECORDED');
assert(
  payBadge.includes('Payment Received') && payBadge.includes('badge'),
  'formatLedgerTypeBadge renders Payment Received badge',
  `Unexpected badge: ${payBadge}`
);

const revBadge = app.formatLedgerTypeBadge('PAYMENT_REVERSED');
assert(
  revBadge.includes('Payment Reversed') && revBadge.includes('badge'),
  'formatLedgerTypeBadge renders Payment Reversed badge',
  `Unexpected badge: ${revBadge}`
);

assert(
  typeof app.formatLedgerDirectionBadge === 'function',
  'app.formatLedgerDirectionBadge is exported as function',
  'formatLedgerDirectionBadge not exported'
);

const debitBadge = app.formatLedgerDirectionBadge('DEBIT');
assert(
  debitBadge.includes('DR (Debit)'),
  'formatLedgerDirectionBadge renders DR (Debit) badge',
  `Unexpected direction badge: ${debitBadge}`
);

const creditBadge = app.formatLedgerDirectionBadge('CREDIT');
assert(
  creditBadge.includes('CR (Credit)'),
  'formatLedgerDirectionBadge renders CR (Credit) badge',
  `Unexpected direction badge: ${creditBadge}`
);

assert(
  typeof app.formatLedgerStatusBadge === 'function',
  'app.formatLedgerStatusBadge is exported as function',
  'formatLedgerStatusBadge not exported'
);

assert(
  typeof app.escapeLedgerHtml === 'function',
  'app.escapeLedgerHtml is exported as function',
  'escapeLedgerHtml not exported'
);

assert(
  app.escapeLedgerHtml('<script>alert("xss")</script>') === '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;',
  'escapeLedgerHtml sanitizes malicious characters',
  'XSS sanitization failed'
);

assert(
  typeof app.fetchAndRenderLedger === 'function',
  'app.fetchAndRenderLedger is exported as function',
  'fetchAndRenderLedger not exported'
);

assert(
  typeof app.updateLedgerSummaryKPIs === 'function',
  'app.updateLedgerSummaryKPIs is exported as function',
  'updateLedgerSummaryKPIs not exported'
);

assert(
  typeof app.renderLedgerTable === 'function',
  'app.renderLedgerTable is exported as function',
  'renderLedgerTable not exported'
);

assert(
  typeof app.handleLedgerSearch === 'function',
  'app.handleLedgerSearch is exported as function',
  'handleLedgerSearch not exported'
);

assert(
  typeof app.clearLedgerSearch === 'function',
  'app.clearLedgerSearch is exported as function',
  'clearLedgerSearch not exported'
);

assert(
  typeof app.setLedgerTypeFilter === 'function',
  'app.setLedgerTypeFilter is exported as function',
  'setLedgerTypeFilter not exported'
);

assert(
  typeof app.handleLedgerNurseryFilter === 'function',
  'app.handleLedgerNurseryFilter is exported as function',
  'handleLedgerNurseryFilter not exported'
);

assert(
  typeof app.handleLedgerDateFilter === 'function',
  'app.handleLedgerDateFilter is exported as function',
  'handleLedgerDateFilter not exported'
);

assert(
  typeof app.handleLedgerSortOrder === 'function',
  'app.handleLedgerSortOrder is exported as function',
  'handleLedgerSortOrder not exported'
);

assert(
  typeof app.ledgerFilters === 'object' && app.ledgerFilters.type === 'ALL',
  'app.ledgerFilters state object initialized with ALL type filter',
  'ledgerFilters not initialized correctly'
);

// ----------------------------------------------------------------------------
// SUMMARY
// ----------------------------------------------------------------------------
console.log('\n====================================================================');
console.log(`TEST SUMMARY: ${passed} PASSED, ${failed} FAILED`);
console.log('====================================================================');

if (failed > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
