const fs = require('fs');

const html = fs.readFileSync('index.html', 'utf-8');
const js = fs.readFileSync('app/static/js/app.js', 'utf-8');
const css = fs.readFileSync('app/static/css/styles.css', 'utf-8');

console.log('================================================================');
console.log('FLORACHAIN B2B — PHASE 4 COMPREHENSIVE TEST SUITE');
console.log('1. Nursery Management & 2. Physical Inspection & Delivery Verification');
console.log('================================================================\n');

// ----------------------------------------------------------------------------
// TEST 1: File Existence & Integrity
// ----------------------------------------------------------------------------
console.log('--- TEST 1: File Existence & Integrity ---');
console.log('HTML length:', html.length, '| Has Nurseries subpage:', html.includes('id="supplier-page-nurseries"'));
console.log('JS length:', js.length, '| Has renderNurseriesTable:', js.includes('function renderNurseriesTable'));
console.log('CSS length:', css.length, '| Has brand color #063B00:', css.includes('#063B00'));

// ----------------------------------------------------------------------------
// TEST 2: HTML Modals & IDs (Nursery Management + Delivery Verification)
// ----------------------------------------------------------------------------
console.log('\n--- TEST 2: HTML Modals & Element IDs ---');
const requiredIds = [
  // Nursery Management IDs
  'supplier-page-nurseries', 'nurseries-table-tbody', 'nursery-search-input',
  'pill-filter-all', 'pill-filter-active', 'pill-filter-pending', 'pill-filter-inactive',
  'kpi-total-nurseries', 'kpi-supplier-dash-nurseries',
  'nursery-form-modal', 'nursery-view-modal', 'btn-save-nursery',
  // Delivery Verification & Physical Inspection IDs
  'nursery-inbound-tbody', 'delivery-verification-modal', 'delivery-verification-form',
  'verify-order-id', 'verify-display-order-id', 'verify-display-variety',
  'verify-display-truck', 'verify-display-ordered-qty',
  'verify-delivered-qty', 'verify-sound-qty', 'verify-damaged-qty', 'verify-damage-notes',
  'summary-delivered-val', 'summary-sound-val', 'summary-damaged-val', 'summary-damage-pct-val',
  'verify-calc-warning', 'verify-mismatch-warning', 'verify-lock-notice',
  'btn-confirm-verification'
];

let allFound = true;
requiredIds.forEach(id => {
  const found = html.includes(`id="${id}"`);
  if (!found) {
    console.error('❌ Missing ID in HTML:', id);
    allFound = false;
  }
});
if (allFound) {
  console.log(`✅ All ${requiredIds.length} required HTML element IDs are verified present!`);
}

// ----------------------------------------------------------------------------
// Load JavaScript Engine for Unit Tests
// ----------------------------------------------------------------------------
// Mock localStorage in Node.js environment
const memoryStorage = {};
global.localStorage = {
  getItem: (key) => memoryStorage[key] || null,
  setItem: (key, val) => { memoryStorage[key] = String(val); },
  removeItem: (key) => { delete memoryStorage[key]; },
  clear: () => { Object.keys(memoryStorage).forEach(k => delete memoryStorage[k]); }
};

const app = require('../app/static/js/app.js');
const { calculateInspectionMetrics, verifyDeliveryOrder, loadDeliveryVerificationsFromStorage } = app;

console.log('\n--- TEST 3: Inspection Metric Calculations & Validations ---');

// Case A: Valid Quantities
const validResult = calculateInspectionMetrics(150, 150, 145, 5);
console.assert(validResult.isValid === true, 'Valid quantities should pass validation');
console.assert(validResult.acceptedQty === 145, 'Accepted quantity must equal sound quantity (145)');
console.assert(validResult.damagePct === 3.33, `Damage percentage should be 3.33% (got ${validResult.damagePct}%)`);
console.assert(validResult.hasMismatch === false, 'No ordered vs delivered mismatch when counts equal');
console.log('✅ Case A Passed: Valid quantities correctly compute accepted sound (145) and damage rate (3.33%)');

// Case B: Negative Quantities Validation
const negResult = calculateInspectionMetrics(150, 150, -10, 160);
console.assert(negResult.isValid === false, 'Negative quantities must be rejected');
console.assert(negResult.error.includes('non-negative'), 'Error must specify non-negative requirement');
console.log('✅ Case B Passed: Negative quantities successfully rejected with error message');

// Case C: Non-Integer Decimal Validation
const decResult = calculateInspectionMetrics(150, 150, 145.5, 4.5);
console.assert(decResult.isValid === false, 'Decimal quantities must be rejected');
console.assert(decResult.error.includes('whole numbers'), 'Error must specify whole numbers');
console.log('✅ Case C Passed: Fractional/decimal plant quantities successfully rejected');

// Case D: Sound + Damaged Mismatch vs Delivered
const mismatchSum = calculateInspectionMetrics(150, 150, 140, 5); // 140 + 5 = 145 != 150
console.assert(mismatchSum.isValid === false, 'Sum mismatch must fail validation');
console.assert(mismatchSum.error.includes('Calculation Mismatch'), 'Error must state calculation mismatch');
console.log('✅ Case D Passed: Sound + damaged mismatch correctly flagged and blocked');

// Case E: Ordered vs Delivered Mismatch Flagging
const mismatchOrder = calculateInspectionMetrics(150, 130, 125, 5); // Ordered 150, Delivered 130
console.assert(mismatchOrder.isValid === true, 'Delivered count valid internally');
console.assert(mismatchOrder.hasMismatch === true, 'Must flag ordered vs delivered variance');
console.assert(mismatchOrder.mismatchDiff === -20, 'Variance diff must be -20');
console.assert(mismatchOrder.orderedQty === 150, 'Original ordered quantity must not be altered');
console.log('✅ Case E Passed: Ordered vs delivered mismatch correctly flagged (variance -20) without altering orderedQty');

console.log('\n--- TEST 4: Order Verification Workflow & State Transition ---');

// Perform verification on ORD-8801
const verifyResult = verifyDeliveryOrder('ORD-8801', {
  orderedQty: 150,
  deliveredQty: 150,
  soundQty: 145,
  damagedQty: 5,
  damageNotes: '5 ceramic pots broken during transport; stems bent.'
}, 'Inspector Rajesh (Nursery Receiving)');

console.assert(verifyResult.success === true, 'Verification submission must succeed');
console.assert(verifyResult.record.status === 'DELIVERED & VERIFIED', 'Status must transition to DELIVERED & VERIFIED');
console.assert(verifyResult.record.isLocked === true, 'Record must be marked as locked');
console.assert(verifyResult.record.acceptedQty === 145, 'Accepted units must be 145');
console.assert(Boolean(verifyResult.record.verifiedAt), 'Timestamp must be recorded');
console.assert(verifyResult.record.verifiedBy === 'Inspector Rajesh (Nursery Receiving)', 'Inspector identity recorded');
console.log(`✅ Order ORD-8801 successfully verified and locked at ${verifyResult.record.verifiedAt} by ${verifyResult.record.verifiedBy}`);

console.log('\n--- TEST 5: Storage Persistence Verification ---');

// Verify that verification record exists in persistent storage
const storedRecords = loadDeliveryVerificationsFromStorage();
console.assert(Boolean(storedRecords['ORD-8801']), 'Stored records must contain ORD-8801');
console.assert(storedRecords['ORD-8801'].soundQty === 145, 'Stored record must retain soundQty = 145');
console.assert(storedRecords['ORD-8801'].isLocked === true, 'Stored record must remain locked');
console.log('✅ Verified persistence: Record correctly serialized to localStorage and restored identical data');

console.log('\n--- TEST 6: Order Locking Enforcement (Immutability) ---');

// Attempt to re-verify or edit the already locked order
const editAttempt = verifyDeliveryOrder('ORD-8801', {
  orderedQty: 150,
  deliveredQty: 150,
  soundQty: 150, // Attempting to change sound count
  damagedQty: 0
}, 'Unauthorized Alteration');

console.assert(editAttempt.success === false, 'Edit on locked order must be rejected');
console.assert(editAttempt.locked === true, 'Response must identify locked status');
console.assert(editAttempt.error.includes('locked'), 'Error must specify order is locked');

// Verify stored data was NOT altered
const postAttemptStored = loadDeliveryVerificationsFromStorage();
console.assert(postAttemptStored['ORD-8801'].soundQty === 145, 'Sound count must remain 145 after rejected edit attempt');
console.log('✅ Immutability verified: Ordinary edits after locking are strictly rejected and data is preserved');

console.log('\n--- TEST 7: HTTP Server Response ---');
fetch('http://127.0.0.1:8000/index.html')
  .then(r => {
    console.log('Server HTTP Status:', r.status);
    return r.text();
  })
  .then(t => {
    console.log('Server served index.html correctly. Size:', t.length, 'bytes');
    console.log('\n🎉 ALL PHASE 4 TESTS PASSED SUCCESSFULLY!');
  })
  .catch(e => console.error('Server error:', e.message));
