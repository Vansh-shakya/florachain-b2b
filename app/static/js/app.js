/**
 * Nursery Supply Management Platform — Interactive Prototype Engine
 * Handles role-switching, full order lifecycle states, truck dispatch,
 * goods physical inspection/verification, dynamic invoicing, payments,
 * late-payment interest calculator, and double-entry ledger.
 */

// Initial Seed Data for the Interactive Demo
const DEFAULT_STATE = {
  activeRole: 'supplier', // 'supplier' or 'nursery'
  plants: [
    { id: 'PLANT-101', name: 'Areca Palm', variety: 'Chrysalidocarpus', size: '12-inch Pot', price: 350, stock: 450 },
    { id: 'PLANT-102', name: 'Ficus Lyrata (Fiddle Leaf)', variety: 'Bambino', size: '10-inch Pot', price: 650, stock: 200 },
    { id: 'PLANT-103', name: 'Bougainvillea Dwarf', variety: 'Barbara Karst', size: '8-inch Bag', price: 180, stock: 800 },
    { id: 'PLANT-104', name: 'Monstera Deliciosa', variety: 'Swiss Cheese', size: '12-inch Pot', price: 550, stock: 150 },
    { id: 'PLANT-105', name: 'Golden Pothos Totem', variety: 'Epipremnum', size: '3-foot Totem', price: 420, stock: 320 }
  ],
  orders: [
    {
      id: 'ORD-901',
      nurseryName: 'Green Meadows Landscape Nursery',
      plantId: 'PLANT-101',
      plantName: 'Areca Palm',
      orderedQty: 100,
      loadedQty: 100,
      verifiedQty: 95,
      damagedQty: 5,
      damageNotes: '5 pots fractured during transport; root ball exposed.',
      unitPrice: 350,
      status: 'VERIFIED', // PLACED, PREPARED, DISPATCHED, ARRIVED, VERIFIED, INVOICED, PAID
      dispatch: {
        truckNo: 'KA-04-E-8821',
        driverName: 'Ramesh Kumar',
        driverPhone: '+91 98450 12345',
        time: 'Today, 08:30 AM'
      },
      invoiceId: 'INV-401'
    },
    {
      id: 'ORD-902',
      nurseryName: 'Evergreen Retail Garden Center',
      plantId: 'PLANT-103',
      plantName: 'Bougainvillea Dwarf',
      orderedQty: 250,
      loadedQty: 250,
      verifiedQty: null,
      damagedQty: null,
      damageNotes: '',
      unitPrice: 180,
      status: 'DISPATCHED',
      dispatch: {
        truckNo: 'KA-05-MH-4412',
        driverName: 'Suresh Patil',
        driverPhone: '+91 97401 55678',
        time: 'Today, 10:15 AM'
      },
      invoiceId: null
    }
  ],
  invoices: [
    {
      id: 'INV-401',
      orderId: 'ORD-901',
      nurseryName: 'Green Meadows Landscape Nursery',
      verifiedUnits: 95,
      unitPrice: 350,
      subtotal: 33250, // 95 * 350
      taxAmount: 1662.50, // 5% GST
      totalAmount: 34912.50,
      dueDate: getFutureDate(15),
      advancePaid: 15000,
      balanceDue: 19912.50,
      annualInterestRate: 18.0, // 18% p.a.
      status: 'PARTIALLY_PAID' // UNPAID, PARTIALLY_PAID, PAID, OVERDUE
    }
  ],
  ledger: [
    {
      date: '2026-09-28',
      type: 'INVOICE',
      reference: 'INV-401',
      description: 'Invoice generated for 95 verified Areca Palms (ORD-901)',
      debit: 34912.50,
      credit: 0,
      balance: 34912.50
    },
    {
      date: '2026-09-29',
      type: 'PAYMENT',
      reference: 'PAY-882',
      description: 'Advance payment received via Bank IMPS (Ref #IMPS9921)',
      debit: 0,
      credit: 15000.00,
      balance: 19912.50
    }
  ]
};

// State persistence in LocalStorage
function loadState() {
  const saved = localStorage.getItem('nursery_platform_state');
  if (saved) {
    try {
      return JSON.parse(saved);
    } catch (e) {
      console.warn('Failed parsing saved state, resetting to defaults.', e);
    }
  }
  return JSON.parse(JSON.stringify(DEFAULT_STATE));
}

let AppState = loadState();

function saveState() {
  localStorage.setItem('nursery_platform_state', JSON.stringify(AppState));
  renderAll();
}

function resetDemoData() {
  if (confirm('Reset prototype data to default sample nursery and supplier state?')) {
    AppState = JSON.parse(JSON.stringify(DEFAULT_STATE));
    saveState();
    showToast('Prototype data reset to initial state', 'info');
  }
}

// Date helper
function getFutureDate(daysAhead) {
  const d = new Date();
  d.setDate(d.getDate() + daysAhead);
  return d.toISOString().split('T')[0];
}

// Toast notification helper
function showToast(message, type = 'success') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${type === 'success' ? '✓' : type === 'warning' ? '⚠' : 'ℹ'}</span> <span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(100%)';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// Switch between Supplier and Nursery Portals
function switchRole(role) {
  AppState.activeRole = role;
  saveState();
}

// Order Stage Transition Helpers
function prepareOrder(orderId) {
  const order = AppState.orders.find(o => o.id === orderId);
  if (order && order.status === 'PLACED') {
    order.status = 'PREPARED';
    saveState();
    showToast(`Order #${order.id} marked as Staged & Prepared for loading!`, 'success');
  }
}

// Truck Dispatch Modal Open
let activeDispatchOrderId = null;
function openDispatchModal(orderId) {
  activeDispatchOrderId = orderId;
  const modal = document.getElementById('dispatch-modal');
  const order = AppState.orders.find(o => o.id === orderId);
  if (modal && order) {
    document.getElementById('modal-dispatch-order-id').innerText = order.id;
    document.getElementById('modal-dispatch-plant').innerText = `${order.orderedQty}x ${order.plantName}`;
    modal.showModal();
  }
}

function submitDispatch(e) {
  e.preventDefault();
  if (!activeDispatchOrderId) return;
  const order = AppState.orders.find(o => o.id === activeDispatchOrderId);
  if (order) {
    const truckNo = document.getElementById('input-truck-no').value.trim();
    const driverName = document.getElementById('input-driver-name').value.trim();
    const driverPhone = document.getElementById('input-driver-phone').value.trim();

    order.status = 'DISPATCHED';
    order.loadedQty = order.orderedQty;
    order.dispatch = {
      truckNo: truckNo || 'KA-04-E-1000',
      driverName: driverName || 'Field Driver',
      driverPhone: driverPhone || '+91 98000 00000',
      time: 'Just now'
    };
    saveState();
    document.getElementById('dispatch-modal').close();
    showToast(`Truck dispatched for Order #${order.id}! Status is now In-Transit.`, 'success');
  }
}

// Simulate Truck Arrival at Nursery Dock
function markTruckArrived(orderId) {
  const order = AppState.orders.find(o => o.id === orderId);
  if (order && order.status === 'DISPATCHED') {
    order.status = 'ARRIVED';
    saveState();
    showToast(`Truck arrived at Nursery Dock for Order #${order.id}! Ready for verification.`, 'info');
  }
}

// Delivery Verification Modal (Physical Inspection of Plants)
let activeVerifyOrderId = null;
function openVerificationModal(orderId) {
  activeVerifyOrderId = orderId;
  const modal = document.getElementById('verify-modal');
  const order = AppState.orders.find(o => o.id === orderId);
  if (modal && order) {
    document.getElementById('modal-verify-order-id').innerText = order.id;
    document.getElementById('modal-verify-plant-name').innerText = order.plantName;
    document.getElementById('modal-verify-loaded-qty').innerText = order.loadedQty;

    // Reset fields
    document.getElementById('input-sound-qty').value = order.loadedQty;
    document.getElementById('input-damaged-qty').value = 0;
    document.getElementById('input-damage-notes').value = '';
    updateVerificationSummary(order.loadedQty, 0);

    modal.showModal();
  }
}

function onVerificationInputsChange() {
  const soundQty = parseInt(document.getElementById('input-sound-qty').value, 10) || 0;
  const damagedQty = parseInt(document.getElementById('input-damaged-qty').value, 10) || 0;
  updateVerificationSummary(soundQty, damagedQty);
}

function updateVerificationSummary(sound, damaged) {
  const total = sound + damaged;
  document.getElementById('summary-sound').innerText = sound;
  document.getElementById('summary-damaged').innerText = damaged;
  document.getElementById('summary-total-counted').innerText = total;

  const warningElem = document.getElementById('verify-count-warning');
  const loaded = parseInt(document.getElementById('modal-verify-loaded-qty').innerText, 10);
  if (total !== loaded) {
    warningElem.style.display = 'block';
    warningElem.innerText = `Note: Total counted (${total}) differs from truck manifest count (${loaded}).`;
  } else {
    warningElem.style.display = 'none';
  }
}

function submitVerification(e) {
  e.preventDefault();
  if (!activeVerifyOrderId) return;
  const order = AppState.orders.find(o => o.id === activeVerifyOrderId);
  if (order) {
    const soundQty = parseInt(document.getElementById('input-sound-qty').value, 10) || 0;
    const damagedQty = parseInt(document.getElementById('input-damaged-qty').value, 10) || 0;
    const notes = document.getElementById('input-damage-notes').value.trim();

    order.verifiedQty = soundQty;
    order.damagedQty = damagedQty;
    order.damageNotes = notes;
    order.status = 'VERIFIED';

    saveState();
    document.getElementById('verify-modal').close();
    showToast(`Delivery verified: ${soundQty} sound plants accepted, ${damagedQty} damaged.`, 'success');
  }
}

// Supplier Generates Invoice based Strictly on Verified Quantities
function generateInvoice(orderId) {
  const order = AppState.orders.find(o => o.id === orderId);
  if (!order || order.status !== 'VERIFIED') {
    alert('Invoice can only be issued after the nursery completes delivery verification.');
    return;
  }

  const invoiceNo = `INV-${Math.floor(100 + Math.random() * 900)}`;
  const verifiedUnits = order.verifiedQty;
  const subtotal = verifiedUnits * order.unitPrice;
  const taxAmount = +(subtotal * 0.05).toFixed(2); // 5% GST
  const totalAmount = +(subtotal + taxAmount).toFixed(2);

  const newInvoice = {
    id: invoiceNo,
    orderId: order.id,
    nurseryName: order.nurseryName,
    verifiedUnits: verifiedUnits,
    unitPrice: order.unitPrice,
    subtotal: subtotal,
    taxAmount: taxAmount,
    totalAmount: totalAmount,
    dueDate: getFutureDate(15),
    advancePaid: 0,
    balanceDue: totalAmount,
    annualInterestRate: 18.0,
    status: 'UNPAID'
  };

  order.status = 'INVOICED';
  order.invoiceId = invoiceNo;
  AppState.invoices.push(newInvoice);

  // Add Debit entry to B2B Ledger
  const prevBalance = AppState.ledger.length > 0 ? AppState.ledger[AppState.ledger.length - 1].balance : 0;
  const newBalance = +(prevBalance + totalAmount).toFixed(2);

  AppState.ledger.push({
    date: new Date().toISOString().split('T')[0],
    type: 'INVOICE',
    reference: invoiceNo,
    description: `Invoice for ${verifiedUnits} verified units of ${order.plantName} (${order.id})`,
    debit: totalAmount,
    credit: 0,
    balance: newBalance
  });

  saveState();
  showToast(`Invoice #${invoiceNo} issued for ₹${totalAmount.toLocaleString()}! Ledger updated.`, 'success');
}

// Payment Recording Modal
let activePaymentInvoiceId = null;
function openPaymentModal(invoiceId) {
  activePaymentInvoiceId = invoiceId;
  const modal = document.getElementById('payment-modal');
  const invoice = AppState.invoices.find(i => i.id === invoiceId);
  if (modal && invoice) {
    document.getElementById('modal-payment-inv-id').innerText = invoice.id;
    document.getElementById('modal-payment-total').innerText = `₹${invoice.totalAmount.toLocaleString()}`;
    document.getElementById('modal-payment-balance').innerText = `₹${invoice.balanceDue.toLocaleString()}`;
    document.getElementById('input-payment-amount').value = invoice.balanceDue;
    modal.showModal();
  }
}

function submitPayment(e) {
  e.preventDefault();
  if (!activePaymentInvoiceId) return;
  const invoice = AppState.invoices.find(i => i.id === activePaymentInvoiceId);
  if (invoice) {
    const payAmount = parseFloat(document.getElementById('input-payment-amount').value) || 0;
    const method = document.getElementById('input-payment-method').value;
    const ref = document.getElementById('input-payment-ref').value.trim() || 'CASH/TXN';

    if (payAmount <= 0) {
      alert('Payment amount must be greater than zero.');
      return;
    }
    if (payAmount > invoice.balanceDue) {
      alert(`Amount exceeds current balance due of ₹${invoice.balanceDue.toLocaleString()}`);
      return;
    }

    invoice.advancePaid = +(invoice.advancePaid + payAmount).toFixed(2);
    invoice.balanceDue = +(invoice.totalAmount - invoice.advancePaid).toFixed(2);

    if (invoice.balanceDue === 0) {
      invoice.status = 'PAID';
      const order = AppState.orders.find(o => o.id === invoice.orderId);
      if (order) order.status = 'PAID';
    } else {
      invoice.status = 'PARTIALLY_PAID';
    }

    // Ledger Credit entry
    const prevBalance = AppState.ledger.length > 0 ? AppState.ledger[AppState.ledger.length - 1].balance : 0;
    const newBalance = +(prevBalance - payAmount).toFixed(2);

    AppState.ledger.push({
      date: new Date().toISOString().split('T')[0],
      type: 'PAYMENT',
      reference: `REC-${Math.floor(100 + Math.random() * 900)}`,
      description: `Payment received via ${method} (Ref: ${ref}) against ${invoice.id}`,
      debit: 0,
      credit: payAmount,
      balance: newBalance
    });

    saveState();
    document.getElementById('payment-modal').close();
    showToast(`Payment of ₹${payAmount.toLocaleString()} recorded! Balance updated.`, 'success');
  }
}

// Nursery Places New Order
function submitNewOrder(e) {
  e.preventDefault();
  const plantSelect = document.getElementById('new-order-plant');
  const plantId = plantSelect.value;
  const plant = AppState.plants.find(p => p.id === plantId);
  const qty = parseInt(document.getElementById('new-order-qty').value, 10) || 0;

  if (qty <= 0) {
    alert('Please enter a valid quantity of plants.');
    return;
  }

  const orderId = `ORD-${Math.floor(900 + Math.random() * 99)}`;
  const newOrder = {
    id: orderId,
    nurseryName: 'Green Meadows Landscape Nursery',
    plantId: plant.id,
    plantName: plant.name,
    orderedQty: qty,
    loadedQty: null,
    verifiedQty: null,
    damagedQty: null,
    damageNotes: '',
    unitPrice: plant.price,
    status: 'PLACED',
    dispatch: null,
    invoiceId: null
  };

  AppState.orders.unshift(newOrder);
  saveState();
  document.getElementById('new-order-form').reset();
  showToast(`Order #${orderId} for ${qty}x ${plant.name} submitted to supplier!`, 'success');
}

// Interactive Overdue Interest Calculation Simulator
function calculateSimulatedInterest() {
  const daysOverdue = parseInt(document.getElementById('calc-days-overdue').value, 10) || 0;
  const annualRate = parseFloat(document.getElementById('calc-interest-rate').value) || 18.0;

  // Calculate against active unpaid balance of sample invoice
  const sampleInvoice = AppState.invoices[0];
  const balance = sampleInvoice ? sampleInvoice.balanceDue : 0;

  // Formula: Interest = Balance * (Annual Rate / 365) * Days
  const dailyRate = annualRate / 100 / 365;
  const calculatedInterest = +(balance * dailyRate * daysOverdue).toFixed(2);
  const totalPayableWithInterest = +(balance + calculatedInterest).toFixed(2);

  document.getElementById('calc-principal').innerText = `₹${balance.toLocaleString()}`;
  document.getElementById('calc-interest-amt').innerText = `₹${calculatedInterest.toLocaleString()}`;
  document.getElementById('calc-total-due').innerText = `₹${totalPayableWithInterest.toLocaleString()}`;
  document.getElementById('calc-days-display').innerText = `${daysOverdue} Days Overdue`;
}

// ==========================================================================
// Rendering Engine (DOM Updaters)
// ==========================================================================

function renderAll() {
  renderRoleSwitcher();
  renderStats();
  renderCatalog();
  renderOrdersTable();
  renderInvoicesTable();
  renderLedgerTable();
  calculateSimulatedInterest();
}

function renderRoleSwitcher() {
  const supplierBtn = document.getElementById('role-btn-supplier');
  const nurseryBtn = document.getElementById('role-btn-nursery');
  const supplierSection = document.getElementById('section-supplier');
  const nurserySection = document.getElementById('section-nursery');

  if (AppState.activeRole === 'supplier') {
    supplierBtn.classList.add('active');
    nurseryBtn.classList.remove('active');
    supplierSection.classList.add('active');
    nurserySection.classList.remove('active');
  } else {
    nurseryBtn.classList.add('active');
    supplierBtn.classList.remove('active');
    nurserySection.classList.add('active');
    supplierSection.classList.remove('active');
  }
}

function renderStats() {
  const totalOrders = AppState.orders.length;
  const inTransitCount = AppState.orders.filter(o => o.status === 'DISPATCHED' || o.status === 'ARRIVED').length;
  const verifiedCount = AppState.orders.filter(o => o.status === 'VERIFIED' || o.status === 'INVOICED' || o.status === 'PAID').length;
  const totalReceivables = AppState.invoices.reduce((sum, inv) => sum + inv.balanceDue, 0);

  document.getElementById('stat-total-orders').innerText = totalOrders;
  document.getElementById('stat-in-transit').innerText = inTransitCount;
  document.getElementById('stat-verified').innerText = verifiedCount;
  document.getElementById('stat-receivables').innerText = `₹${totalReceivables.toLocaleString()}`;
}

function renderCatalog() {
  const grid = document.getElementById('plant-catalog-grid');
  const select = document.getElementById('new-order-plant');
  if (!grid || !select) return;

  grid.innerHTML = '';
  select.innerHTML = '';

  AppState.plants.forEach(plant => {
    // Add to order select dropdown
    const option = document.createElement('option');
    option.value = plant.id;
    option.text = `${plant.name} (${plant.size}) — ₹${plant.price}/unit`;
    select.appendChild(option);

    // Card in catalog view
    const card = document.createElement('div');
    card.className = 'plant-card';
    card.innerHTML = `
      <div>
        <span class="plant-badge">${plant.variety}</span>
        <div class="plant-name">${plant.name}</div>
        <div class="plant-spec">Size: ${plant.size}</div>
      </div>
      <div class="plant-footer">
        <div>
          <div class="plant-price">₹${plant.price}</div>
          <div class="plant-stock">Available: ${plant.stock} units</div>
        </div>
        <button class="btn btn-secondary btn-sm" onclick="quickSelectPlant('${plant.id}')">Order</button>
      </div>
    `;
    grid.appendChild(card);
  });
}

function quickSelectPlant(plantId) {
  switchRole('nursery');
  const select = document.getElementById('new-order-plant');
  if (select) {
    select.value = plantId;
    document.getElementById('new-order-qty').focus();
  }
}

function getBadgeHtml(status) {
  const map = {
    'PLACED': { text: 'Order Placed', class: 'badge-placed' },
    'PREPARED': { text: 'Plants Prepared', class: 'badge-prepared' },
    'DISPATCHED': { text: 'In Transit 🚚', class: 'badge-dispatched' },
    'ARRIVED': { text: 'At Nursery Dock', class: 'badge-arrived' },
    'VERIFIED': { text: 'Quantity Verified ✓', class: 'badge-verified' },
    'INVOICED': { text: 'Invoice Issued', class: 'badge-invoiced' },
    'PAID': { text: 'Paid & Settled', class: 'badge-paid' },
    'OVERDUE': { text: 'Overdue (Interest)', class: 'badge-overdue' }
  };
  const b = map[status] || { text: status, class: 'badge-placed' };
  return `<span class="badge ${b.class}">${b.text}</span>`;
}

function renderOrdersTable() {
  // Supplier view order queue
  const supplierTbody = document.getElementById('supplier-orders-tbody');
  if (supplierTbody) {
    supplierTbody.innerHTML = AppState.orders.map(order => {
      let actionBtns = '';
      if (order.status === 'PLACED') {
        actionBtns = `<button class="btn btn-warning btn-sm" onclick="prepareOrder('${order.id}')">Prepare Batch</button>`;
      } else if (order.status === 'PREPARED') {
        actionBtns = `<button class="btn btn-primary btn-sm" onclick="openDispatchModal('${order.id}')">Load & Dispatch 🚚</button>`;
      } else if (order.status === 'DISPATCHED') {
        actionBtns = `<span style="font-size:0.8rem; color:var(--slate-500)">Driver: ${order.dispatch.driverName}</span>`;
      } else if (order.status === 'ARRIVED') {
        actionBtns = `<span style="font-size:0.8rem; color:var(--purple-600)">Awaiting Nursery Count</span>`;
      } else if (order.status === 'VERIFIED') {
        actionBtns = `<button class="btn btn-success btn-sm" onclick="generateInvoice('${order.id}')">Generate Invoice</button>`;
      } else if (order.status === 'INVOICED' || order.status === 'PAID') {
        actionBtns = `<span style="font-size:0.8rem; color:var(--emerald-600)">Invoiced (${order.invoiceId})</span>`;
      }

      return `
        <tr>
          <td><strong>#${order.id}</strong></td>
          <td>${order.nurseryName}</td>
          <td>${order.plantName}</td>
          <td><strong>${order.orderedQty}</strong></td>
          <td>${order.verifiedQty !== null ? `<span style="color:var(--emerald-600); font-weight:700;">${order.verifiedQty} sound</span> (${order.damagedQty} damaged)` : '-'}</td>
          <td>${getBadgeHtml(order.status)}</td>
          <td>${actionBtns}</td>
        </tr>
      `;
    }).join('');
  }

  // Nursery view tracking table
  const nurseryTbody = document.getElementById('nursery-orders-tbody');
  if (nurseryTbody) {
    nurseryTbody.innerHTML = AppState.orders.map(order => {
      let actionBtns = '';
      if (order.status === 'DISPATCHED') {
        actionBtns = `<button class="btn btn-secondary btn-sm" onclick="markTruckArrived('${order.id}')">Simulate Truck Arrival</button>`;
      } else if (order.status === 'ARRIVED') {
        actionBtns = `<button class="btn btn-primary btn-sm" onclick="openVerificationModal('${order.id}')">Inspect & Verify Plants</button>`;
      } else if (order.status === 'VERIFIED') {
        actionBtns = `<span style="font-size:0.8rem; color:var(--emerald-600)">Verified (${order.verifiedQty} sound)</span>`;
      } else if (order.status === 'INVOICED') {
        actionBtns = `<span style="font-size:0.8rem; color:var(--blue-600)">Invoice Received</span>`;
      } else {
        actionBtns = `<span style="font-size:0.8rem; color:var(--slate-400)">In Preparation</span>`;
      }

      return `
        <tr>
          <td><strong>#${order.id}</strong></td>
          <td>${order.plantName}</td>
          <td>${order.orderedQty} units</td>
          <td>${order.dispatch ? `Truck: ${order.dispatch.truckNo}<br><small>${order.dispatch.driverName} (${order.dispatch.driverPhone})</small>` : 'Not yet dispatched'}</td>
          <td>${getBadgeHtml(order.status)}</td>
          <td>${actionBtns}</td>
        </tr>
      `;
    }).join('');
  }
}

function renderInvoicesTable() {
  const tbody = document.getElementById('invoices-tbody');
  if (!tbody) return;

  tbody.innerHTML = AppState.invoices.map(inv => {
    return `
      <tr>
        <td><strong>#${inv.id}</strong></td>
        <td>${inv.nurseryName}</td>
        <td>${inv.verifiedUnits} units</td>
        <td>₹${inv.totalAmount.toLocaleString()}</td>
        <td><strong style="color: ${inv.balanceDue > 0 ? 'var(--rose-600)' : 'var(--emerald-600)'}">₹${inv.balanceDue.toLocaleString()}</strong></td>
        <td>${inv.dueDate}</td>
        <td>${getBadgeHtml(inv.status)}</td>
        <td>
          ${inv.balanceDue > 0 ? `<button class="btn btn-secondary btn-sm" onclick="openPaymentModal('${inv.id}')">Record Payment</button>` : '<span style="color:var(--emerald-600); font-weight:600">Settled</span>'}
        </td>
      </tr>
    `;
  }).join('');
}

function renderLedgerTable() {
  const tbody = document.getElementById('ledger-tbody');
  if (!tbody) return;

  tbody.innerHTML = AppState.ledger.map(entry => {
    return `
      <tr>
        <td>${entry.date}</td>
        <td><span class="badge ${entry.type === 'INVOICE' ? 'badge-placed' : 'badge-verified'}">${entry.type}</span></td>
        <td><strong>${entry.reference}</strong></td>
        <td>${entry.description}</td>
        <td style="color: ${entry.debit > 0 ? 'var(--slate-800)' : 'var(--slate-400)'}">${entry.debit > 0 ? `₹${entry.debit.toLocaleString()}` : '-'}</td>
        <td style="color: ${entry.credit > 0 ? 'var(--emerald-600)' : 'var(--slate-400)'}; font-weight:600;">${entry.credit > 0 ? `₹${entry.credit.toLocaleString()}` : '-'}</td>
        <td><strong>₹${entry.balance.toLocaleString()}</strong></td>
      </tr>
    `;
  }).join('');
}

// Global initialization
document.addEventListener('DOMContentLoaded', () => {
  renderAll();

  // Bind forms
  const newOrderForm = document.getElementById('new-order-form');
  if (newOrderForm) newOrderForm.addEventListener('submit', submitNewOrder);

  const dispatchForm = document.getElementById('dispatch-form');
  if (dispatchForm) dispatchForm.addEventListener('submit', submitDispatch);

  const verifyForm = document.getElementById('verify-form');
  if (verifyForm) verifyForm.addEventListener('submit', submitVerification);

  const paymentForm = document.getElementById('payment-form');
  if (paymentForm) paymentForm.addEventListener('submit', submitPayment);

  // Bind calculation inputs
  const daysSlider = document.getElementById('calc-days-overdue');
  if (daysSlider) daysSlider.addEventListener('input', calculateSimulatedInterest);

  const rateInput = document.getElementById('calc-interest-rate');
  if (rateInput) rateInput.addEventListener('input', calculateSimulatedInterest);
});
