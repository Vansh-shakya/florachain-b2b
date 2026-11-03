/**
 * FloraChain B2B — Phase 10 Payment Due Date & Agreed Late-Payment Interest UI Test Suite
 * Tests DOM elements, due status filters, detail modal elements, stepwise breakdown table,
 * agreed terms modal form, badge formatters, and exported JS functions.
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
console.log('FLORACHAIN B2B — PHASE 10 DUE DATE & LATE-PAYMENT INTEREST UI TEST SUITE');
console.log('====================================================================\n');

// ----------------------------------------------------------------------------
// TEST GROUP 1: Invoices Due Status Filter Pills & Table Headers
// ----------------------------------------------------------------------------
console.log('--- TEST GROUP 1: Invoices Subpage Due Status Pills & Table Header ---');

assert(
  html.includes('id="invoices-due-status-pills"'),
  'index.html contains #invoices-due-status-pills filter group',
  'Missing #invoices-due-status-pills'
);

assert(
  html.includes('data-due="ALL"') &&
  html.includes('data-due="OVERDUE"') &&
  html.includes('data-due="NOT_DUE"') &&
  html.includes('data-due="SETTLED"'),
  'Due status filter pills include ALL, OVERDUE, NOT_DUE, SETTLED',
  'Missing one or more data-due attribute values'
);

assert(
  html.includes('<th>Due Date & Late Interest</th>') || html.includes('<th>Due Date &amp; Late Interest</th>'),
  'Invoices table header includes Due Date & Late Interest column',
  'Missing <th>Due Date & Late Interest</th>'
);

// ----------------------------------------------------------------------------
// TEST GROUP 2: Invoice Detail Modal Phase 10 Elements
// ----------------------------------------------------------------------------
console.log('\n--- TEST GROUP 2: Invoice Detail Modal Phase 10 Elements ---');

assert(
  html.includes('id="modal-inv-due-date-display"'),
  'Modal contains #modal-inv-due-date-display element',
  'Missing modal-inv-due-date-display'
);

assert(
  html.includes('id="modal-inv-overdue-days-label"'),
  'Modal contains #modal-inv-overdue-days-label element',
  'Missing modal-inv-overdue-days-label'
);

assert(
  html.includes('id="modal-inv-due-status-badge"'),
  'Modal contains #modal-inv-due-status-badge badge element',
  'Missing modal-inv-due-status-badge'
);

assert(
  html.includes('id="btn-modal-inv-edit-terms"'),
  'Modal contains #btn-modal-inv-edit-terms button',
  'Missing btn-modal-inv-edit-terms'
);

assert(
  html.includes('id="modal-inv-agreed-rate-display"'),
  'Modal contains #modal-inv-agreed-rate-display element',
  'Missing modal-inv-agreed-rate-display'
);

assert(
  html.includes('id="modal-inv-basis-display"'),
  'Modal contains #modal-inv-basis-display element',
  'Missing modal-inv-basis-display'
);

assert(
  html.includes('id="modal-inv-accrued-interest"'),
  'Modal contains #modal-inv-accrued-interest element',
  'Missing modal-inv-accrued-interest'
);

assert(
  html.includes('id="modal-inv-total-payable"'),
  'Modal contains #modal-inv-total-payable element',
  'Missing modal-inv-total-payable'
);

assert(
  html.includes('id="modal-inv-interest-breakdown-wrapper"'),
  'Modal contains #modal-inv-interest-breakdown-wrapper section',
  'Missing modal-inv-interest-breakdown-wrapper'
);

assert(
  html.includes('id="modal-inv-interest-breakdown-tbody"'),
  'Modal contains #modal-inv-interest-breakdown-tbody calculation table',
  'Missing modal-inv-interest-breakdown-tbody'
);

// ----------------------------------------------------------------------------
// TEST GROUP 3: Invoice Terms Modal & Form Controls
// ----------------------------------------------------------------------------
console.log('\n--- TEST GROUP 3: Invoice Terms Modal & Form Controls ---');

assert(
  html.includes('id="invoice-terms-modal"'),
  'index.html contains #invoice-terms-modal backdrop',
  'Missing #invoice-terms-modal'
);

assert(
  html.includes('id="invoice-terms-form"'),
  'Terms modal contains #invoice-terms-form form',
  'Missing #invoice-terms-form'
);

assert(
  html.includes('id="terms-form-due-date"'),
  'Terms form contains #terms-form-due-date input',
  'Missing #terms-form-due-date'
);

assert(
  html.includes('id="terms-form-interest-rate"'),
  'Terms form contains #terms-form-interest-rate input',
  'Missing #terms-form-interest-rate'
);

assert(
  html.includes('id="terms-form-basis"'),
  'Terms form contains #terms-form-basis select',
  'Missing #terms-form-basis'
);

assert(
  html.includes('value="ANNUAL_SIMPLE"') &&
  html.includes('value="MONTHLY_SIMPLE"') &&
  html.includes('value="DAILY_SIMPLE"') &&
  html.includes('value="NONE"'),
  'Calculation basis dropdown supports ANNUAL_SIMPLE, MONTHLY_SIMPLE, DAILY_SIMPLE, NONE',
  'Missing basis option values'
);

assert(
  html.includes('id="terms-form-grace-days"'),
  'Terms form contains #terms-form-grace-days input',
  'Missing #terms-form-grace-days'
);

assert(
  html.includes('id="terms-form-notes"'),
  'Terms form contains #terms-form-notes textarea',
  'Missing #terms-form-notes'
);

assert(
  html.includes('id="btn-submit-inv-terms"'),
  'Terms form contains #btn-submit-inv-terms submit button',
  'Missing #btn-submit-inv-terms'
);

// ----------------------------------------------------------------------------
// TEST GROUP 4: JS Engine Functions & Exports
// ----------------------------------------------------------------------------
console.log('\n--- TEST GROUP 4: JS Engine Functions & Exports ---');

assert(
  typeof app.formatDueStatusBadge === 'function',
  'app.js exports formatDueStatusBadge()',
  'formatDueStatusBadge is not exported'
);

assert(
  typeof app.setInvoicesDueStatusFilter === 'function',
  'app.js exports setInvoicesDueStatusFilter()',
  'setInvoicesDueStatusFilter is not exported'
);

assert(
  typeof app.openEditInvoiceTermsModal === 'function',
  'app.js exports openEditInvoiceTermsModal()',
  'openEditInvoiceTermsModal is not exported'
);

assert(
  typeof app.closeEditInvoiceTermsModal === 'function',
  'app.js exports closeEditInvoiceTermsModal()',
  'closeEditInvoiceTermsModal is not exported'
);

assert(
  typeof app.handleUpdateInvoiceTermsSubmit === 'function',
  'app.js exports handleUpdateInvoiceTermsSubmit()',
  'handleUpdateInvoiceTermsSubmit is not exported'
);

// ----------------------------------------------------------------------------
// TEST GROUP 5: Functional Formatting Verification
// ----------------------------------------------------------------------------
console.log('\n--- TEST GROUP 5: Functional Formatting Verification ---');

const badgeOverdue = app.formatDueStatusBadge('OVERDUE', 8);
assert(
  badgeOverdue.includes('badge-danger') && badgeOverdue.includes('OVERDUE') && badgeOverdue.includes('8d'),
  'formatDueStatusBadge("OVERDUE", 8) formats correctly with badge-danger and 8d',
  `Unexpected markup: ${badgeOverdue}`
);

const badgeNotDue = app.formatDueStatusBadge('NOT_DUE', 0);
assert(
  badgeNotDue.includes('badge-info') && badgeNotDue.includes('NOT DUE'),
  'formatDueStatusBadge("NOT_DUE") formats correctly with badge-info',
  `Unexpected markup: ${badgeNotDue}`
);

const badgeGrace = app.formatDueStatusBadge('IN_GRACE_PERIOD', 0);
assert(
  badgeGrace.includes('badge-warning') && badgeGrace.includes('GRACE PERIOD'),
  'formatDueStatusBadge("IN_GRACE_PERIOD") formats correctly with badge-warning',
  `Unexpected markup: ${badgeGrace}`
);

const badgeSettled = app.formatDueStatusBadge('SETTLED', 0);
assert(
  badgeSettled.includes('badge-success') && badgeSettled.includes('SETTLED'),
  'formatDueStatusBadge("SETTLED") formats correctly with badge-success',
  `Unexpected markup: ${badgeSettled}`
);

const currFormatted = app.formatInvoiceCurrency(120.96);
assert(
  currFormatted === '₹120.96',
  'formatInvoiceCurrency(120.96) formats correctly as ₹120.96',
  `Expected ₹120.96, got ${currFormatted}`
);

console.log('\n====================================================================');
console.log(`PHASE 10 UI TEST SUMMARY: ${passed} Passed, ${failed} Failed`);
console.log('====================================================================\n');

if (failed > 0) {
  process.exit(1);
} else {
  process.exit(0);
}

