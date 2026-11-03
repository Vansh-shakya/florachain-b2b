/**
 * FloraChain B2B — Phase 5 Plant Management UI Test Suite
 * Tests frontend HTML elements, modals, currency formatting, escaping, and validation.
 */

const fs = require('fs');
const path = require('path');

const baseDir = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(baseDir, 'index.html'), 'utf-8');
const js = fs.readFileSync(path.join(baseDir, 'app/static/js/app.js'), 'utf-8');
const css = fs.readFileSync(path.join(baseDir, 'app/static/css/styles.css'), 'utf-8');

console.log('================================================================');
console.log('FLORACHAIN B2B — PHASE 5 PLANT MANAGEMENT UI TEST SUITE');
console.log('================================================================\n');

let passCount = 0;
let failCount = 0;

function assertTest(label, condition, detail = '') {
  if (condition) {
    passCount++;
    console.log(`  [PASS] ${label}`);
  } else {
    failCount++;
    console.error(`  [FAIL] ${label} - ${detail}`);
  }
}

// ----------------------------------------------------------------------------
// TEST 1: File Existence & Subpage Integrity
// ----------------------------------------------------------------------------
console.log('--- TEST 1: File Existence & Subpage Markup ---');
assertTest('index.html contains #supplier-page-plants subpage', html.includes('id="supplier-page-plants"'));
assertTest('index.html contains #plants-table-tbody table body', html.includes('id="plants-table-tbody"'));
assertTest('index.html contains Plants sidebar link slink-Plants', html.includes('id="slink-Plants"'));
assertTest('app.js defines fetchAndRenderPlants function', js.includes('async function fetchAndRenderPlants'));
assertTest('app.js defines renderPlantsTable function', js.includes('function renderPlantsTable'));
assertTest('app.js defines handlePlantFormSubmit function', js.includes('async function handlePlantFormSubmit'));

// ----------------------------------------------------------------------------
// TEST 2: HTML Modals & Required Element IDs
// ----------------------------------------------------------------------------
console.log('\n--- TEST 2: Plant Management Element IDs & Modals ---');
const requiredPlantIds = [
  // Subpage & KPI IDs
  'supplier-page-plants',
  'kpi-total-plants',
  'kpi-active-plants',
  'kpi-total-stock-units',
  'kpi-low-stock-plants',
  'plant-count-subtitle',

  // Search & Filter IDs
  'plant-search-input',
  'plant-search-clear',
  'plant-filter-category',
  'pill-plant-all',
  'pill-plant-active',
  'pill-plant-outofstock',
  'pill-plant-discontinued',

  // Table Body
  'plants-table-tbody',

  // Add/Edit Modal & Form IDs
  'plant-form-modal',
  'plant-item-form',
  'plant-modal-title',
  'plant-form-id',
  'plant-form-common-name',
  'plant-form-botanical-name',
  'plant-form-category',
  'plant-form-container-size',
  'plant-form-unit',
  'plant-form-price',
  'plant-form-stock',
  'plant-form-min-order',
  'plant-form-status',
  'plant-form-description',
  'btn-save-plant',

  // Validation Error Element IDs
  'err-plant-common-name',
  'err-plant-category',
  'err-plant-container-size',
  'err-plant-price',
  'err-plant-stock',
  'err-plant-min-order',

  // View Plant Modal IDs
  'plant-view-modal',
  'view-plant-title',
  'view-plant-botanical-subtitle',
  'view-plant-status-badge',
  'view-plant-category',
  'view-plant-container',
  'view-plant-price',
  'view-plant-stock',
  'view-plant-min-order',
  'view-plant-supplier',
  'view-plant-description',
  'view-plant-edit-btn'
];

let allIdsFound = true;
requiredPlantIds.forEach(id => {
  const present = html.includes(`id="${id}"`);
  if (!present) {
    allIdsFound = false;
    assertTest(`HTML element #${id} present`, false, 'Missing from index.html');
  }
});
if (allIdsFound) {
  assertTest(`All ${requiredPlantIds.length} Plant Management HTML element IDs present`, true);
}

// ----------------------------------------------------------------------------
// TEST 3: JavaScript Engine Functions & Helpers
// ----------------------------------------------------------------------------
console.log('\n--- TEST 3: Currency & Escaping Engine Functions ---');

// Mock localStorage for app.js export
global.localStorage = {
  getItem: () => null,
  setItem: () => {},
  removeItem: () => {},
  clear: () => {}
};

const app = require(path.join(baseDir, 'app/static/js/app.js'));
const { formatPlantCurrency, escapePlantHtml } = app;

// 3a. Currency formatting
assertTest('Currency format 350 -> ₹350.00', formatPlantCurrency(350).includes('350.00'));
assertTest('Currency format 125000 -> ₹1,25,000.00', formatPlantCurrency(125000).includes('1,25,000.00'));
assertTest('Currency format 0 -> ₹0.00', formatPlantCurrency(0).includes('0.00'));
assertTest('Currency format null/undefined -> ₹0.00', formatPlantCurrency(null).includes('0.00'));

// 3b. HTML Escaping
assertTest('Escape HTML & -> &amp;', escapePlantHtml('A & B') === 'A &amp; B');
assertTest('Escape HTML <script> -> &lt;script&gt;', escapePlantHtml('<script>') === '&lt;script&gt;');
assertTest('Escape HTML double quotes', escapePlantHtml('12" pot') === '12&quot; pot');
assertTest('Escape HTML single quotes', escapePlantHtml("Ficus 'Bambino'") === 'Ficus &#39;Bambino&#39;');

// ----------------------------------------------------------------------------
// TEST 4: Category Dropdown Options Alignment
// ----------------------------------------------------------------------------
console.log('\n--- TEST 4: Category Dropdown Options Alignment ---');
const expectedCategories = [
  'INDOOR', 'OUTDOOR', 'FLOWERING', 'ORNAMENTAL',
  'TREE', 'PALM', 'SUCCULENT', 'CLIMBER',
  'SEASONAL', 'MEDICINAL', 'FRUIT', 'OTHER'
];
expectedCategories.forEach(cat => {
  assertTest(`Filter category option ${cat} in HTML`, html.includes(`value="${cat}"`));
});

// ----------------------------------------------------------------------------
// TEST 5: Packaging Units Alignment
// ----------------------------------------------------------------------------
console.log('\n--- TEST 5: Unit Dropdown Options Alignment ---');
const expectedUnits = ['plant', 'pot', 'bag', 'tray', 'bundle'];
expectedUnits.forEach(unit => {
  assertTest(`Packaging unit option ${unit} in HTML`, html.includes(`value="${unit}"`));
});

// ----------------------------------------------------------------------------
// TEST 6: Hash Routing & Sidebar Integration
// ----------------------------------------------------------------------------
console.log('\n--- TEST 6: Navigation & Subpage Routing ---');
assertTest('app.js handles #plants subpage display', js.includes("isPlants = subpageName === 'plants'"));
assertTest('app.js handles initial hash #plants', js.includes("initialHash === 'plants'"));
assertTest('app.js handles hashchange to #plants', js.includes("hash === 'plants'"));
assertTest('selectSidebarItem handles Plants item', js.includes("itemName === 'Plants'"));

// ----------------------------------------------------------------------------
// SUMMARY
// ----------------------------------------------------------------------------
console.log('\n================================================================');
const total = passCount + failCount;
console.log(`RESULTS: ${passCount}/${total} passed, ${failCount} failed`);
if (failCount === 0) {
  console.log('ALL PHASE 5 UI TESTS PASSED SUCCESSFULLY!');
} else {
  console.error(`${failCount} test(s) failed.`);
}
console.log('================================================================');

process.exit(failCount === 0 ? 0 : 1);

