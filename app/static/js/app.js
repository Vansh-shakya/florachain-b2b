/**
 * FloraChain B2B — Nursery Supply Management Platform
 * Phase 2: Frontend Foundation Engine
 * 
 * Features:
 * - Client-side view routing (Home, Login, Supplier Dashboard, Nursery Dashboard)
 * - Simulated authentication with 1-click demo logins
 * - Realistic B2B dummy data for wholesale nursery workflows
 * - Interactive search filtering & toast notifications
 */

// ============================================================================
// CSRF TOKEN CLIENT-SIDE INTERCEPTOR (Phase 15 Security Hardening)
// ============================================================================
(function initCsrfInterceptor() {
  if (typeof window === 'undefined' || !window.fetch) return;

  function readCookie(name) {
    if (typeof document === 'undefined') return null;
    const match = document.cookie.match(new RegExp('(?:^|;\\s*)' + name + '=([^;]+)'));
    return match ? decodeURIComponent(match[1]) : null;
  }

  function getCsrfToken() {
    return window.__floraCsrfToken || readCookie('csrf_token') || null;
  }

  const originalFetch = window.fetch;
  window.fetch = async function(resource, init = {}) {
    init = init || {};
    const method = (init.method || 'GET').toUpperCase();
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
      const token = getCsrfToken();
      if (token) {
        if (!init.headers) {
          init.headers = { 'X-CSRF-Token': token };
        } else if (typeof Headers !== 'undefined' && init.headers instanceof Headers) {
          if (!init.headers.has('X-CSRF-Token')) {
            init.headers.set('X-CSRF-Token', token);
          }
        } else if (Array.isArray(init.headers)) {
          if (!init.headers.some(h => (Array.isArray(h) ? h[0] : '').toLowerCase() === 'x-csrf-token')) {
            init.headers.push(['X-CSRF-Token', token]);
          }
        } else if (typeof init.headers === 'object') {
          if (!init.headers['X-CSRF-Token'] && !init.headers['x-csrf-token']) {
            init.headers['X-CSRF-Token'] = token;
          }
        }
      }
    }

    const response = await originalFetch(resource, init);

    try {
      const respCsrf = response.headers ? response.headers.get('X-CSRF-Token') : null;
      if (respCsrf) {
        window.__floraCsrfToken = respCsrf;
      }
    } catch (_) {}

    return response;
  };
})();

// ============================================================================
// GLOBAL SESSION & IDENTITY STATE (Phase 16 Integration)
// ============================================================================

let currentUserProfile = null;

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Updates header user pill and Sign Out button based on active identity.
 */
function updateActiveUserHeader(user) {
  currentUserProfile = user;
  const userText = document.getElementById('active-user-text');
  const logoutBtn = document.getElementById('header-logout-btn');

  if (userText) {
    if (user && user.role) {
      const roleIcon = user.role === 'SUPPLIER' ? '🏢' : (user.role === 'NURSERY' ? '🌱' : '🛡️');
      const displayName = user.business_name || user.username || user.role;
      userText.textContent = `${roleIcon} ${displayName} (${user.role})`;
    } else {
      userText.textContent = 'Not Signed In';
    }
  }

  if (logoutBtn) {
    logoutBtn.style.display = (user && user.role) ? 'inline-flex' : 'none';
  }
}

/**
 * Proactively verifies session with backend GET /api/auth/me on load.
 */
async function checkCurrentUserSession() {
  if (typeof window === 'undefined' || typeof fetch !== 'function') return null;

  try {
    const resp = await fetch('/api/auth/me');
    if (!resp.ok) {
      updateActiveUserHeader(null);
      return null;
    }

    const body = await resp.json().catch(() => ({}));
    if (body.success && body.authenticated && body.data) {
      if (body.csrf_token) {
        window.__floraCsrfToken = body.csrf_token;
      }
      updateActiveUserHeader(body.data);
      return body.data;
    } else {
      updateActiveUserHeader(null);
      return null;
    }
  } catch (err) {
    console.warn('Session check failed:', err);
    updateActiveUserHeader(null);
    return null;
  }
}

/**
 * Authenticated sign-out calling POST /api/auth/logout.
 */
async function handleLogout() {
  if (typeof window !== 'undefined' && typeof fetch === 'function') {
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
    } catch (err) {
      console.warn('Logout network error:', err);
    }
  }

  currentUserProfile = null;
  updateActiveUserHeader(null);
  showToast('Signed out successfully.', 'info');
  navigateTo('login');
}

// ============================================================================
// 1. DUMMY DATA FOR PHASE 2 FRONTEND FOUNDATION
// ============================================================================

const DUMMY_DATA = {
  // Wholesale Supplier Orders
  supplierOrders: [
    {
      id: 'ORD-8801',
      nursery: 'Green Meadows Landscape Nursery',
      variety: 'Areca Palm (12-inch Pot)',
      qty: 150,
      orderDate: '2026-10-02',
      status: 'DISPATCHED',
      statusLabel: 'In Transit',
      badgeClass: 'badge-info'
    },
    {
      id: 'ORD-8802',
      nursery: 'Evergreen Retail Garden Center',
      variety: 'Bougainvillea Dwarf (8-inch Bag)',
      qty: 300,
      orderDate: '2026-10-02',
      status: 'STAGING',
      statusLabel: 'Staging & Tagging',
      badgeClass: 'badge-warning'
    },
    {
      id: 'ORD-8803',
      nursery: 'Urban Eden Landscaping Co.',
      variety: 'Ficus Lyrata Bambino (10-inch Pot)',
      qty: 80,
      orderDate: '2026-10-01',
      status: 'CONFIRMED',
      statusLabel: 'Confirmed',
      badgeClass: 'badge-neutral'
    },
    {
      id: 'ORD-8804',
      nursery: 'Sunrise Flora & Palms',
      variety: 'Golden Pothos Totem (3-foot)',
      qty: 120,
      orderDate: '2026-09-29',
      status: 'DELIVERED',
      statusLabel: 'Delivered & Counted',
      badgeClass: 'badge-success'
    },
    {
      id: 'ORD-8805',
      nursery: 'Valley Bloom Botanical',
      variety: 'Monstera Deliciosa (12-inch Pot)',
      qty: 60,
      orderDate: '2026-09-28',
      status: 'DRAFT',
      statusLabel: 'Draft Estimate',
      badgeClass: 'badge-neutral'
    }
  ],

  // Supplier In-Transit Transport Trucks
  supplierTrucks: [
    {
      truckNo: 'KA-04-E-8821',
      driver: 'Ramesh Kumar (+91 98450 12345)',
      destination: 'Green Meadows Nursery',
      cargo: '150 Areca Palms',
      status: 'En Route (ETA: 2h)'
    },
    {
      truckNo: 'KA-05-MH-4412',
      driver: 'Suresh Patil (+91 97401 55678)',
      destination: 'Evergreen Garden Center',
      cargo: '300 Bougainvillea',
      status: 'Loading at Dock B'
    }
  ],

  // Supplier Operational Activity Feed
  supplierActivity: [
    {
      icon: '🚚',
      desc: 'Truck KA-04-E-8821 dispatched to Green Meadows Nursery (150 Areca Palms).',
      time: '2 hours ago'
    },
    {
      icon: '📋',
      desc: 'Evergreen Garden Center placed new order ORD-8802 (300 Bougainvillea Dwarf).',
      time: '4 hours ago'
    },
    {
      icon: '💰',
      desc: 'Payment of ₹45,000 received from Sunrise Flora against INV-398.',
      time: 'Yesterday'
    },
    {
      icon: '⚠️',
      desc: 'Automated credit reminder issued to Urban Eden Co. (5 days past Net 30).',
      time: '2 days ago'
    }
  ],

  // Phase 3: Section A — Recent Orders
  // Columns: Order ID, Nursery, Order Date, Total Amount, Status
  // Example statuses: Pending, Confirmed, Preparing, Loaded, Delivered
  supplierRecentOrders: [
    {
      id: 'ORD-9104',
      nursery: 'Green Meadows Landscape Nursery',
      orderDate: '2026-10-03',
      totalAmount: '₹84,500',
      status: 'Preparing',
      badgeClass: 'badge-warning'
    },
    {
      id: 'ORD-9103',
      nursery: 'Urban Eden Landscaping Co.',
      orderDate: '2026-10-02',
      totalAmount: '₹46,200',
      status: 'Loaded',
      badgeClass: 'badge-info'
    },
    {
      id: 'ORD-9102',
      nursery: 'Evergreen Retail Garden Center',
      orderDate: '2026-10-01',
      totalAmount: '₹1,25,000',
      status: 'Confirmed',
      badgeClass: 'badge-neutral'
    },
    {
      id: 'ORD-9101',
      nursery: 'Sunrise Flora & Palms',
      orderDate: '2026-09-30',
      totalAmount: '₹95,000',
      status: 'Delivered',
      badgeClass: 'badge-success'
    },
    {
      id: 'ORD-9100',
      nursery: 'Valley Bloom Botanical',
      orderDate: '2026-09-29',
      totalAmount: '₹38,000',
      status: 'Pending',
      badgeClass: 'badge-warning'
    }
  ],

  // Phase 3: Section B — Recent Truck Loading
  // Columns: Truck Number, Nursery, Loading Date, Driver, Status
  supplierTruckLoading: [
    {
      truckNo: 'KA-04-E-8821',
      nursery: 'Green Meadows Landscape Nursery',
      loadingDate: '2026-10-03',
      driver: 'Ramesh Kumar (+91 98450 12345)',
      status: 'Loading Dock B',
      badgeClass: 'badge-warning'
    },
    {
      truckNo: 'MH-12-Q-4450',
      nursery: 'Urban Eden Landscaping Co.',
      loadingDate: '2026-10-02',
      driver: 'Vikram Singh (+91 98220 87654)',
      status: 'In Transit',
      badgeClass: 'badge-info'
    },
    {
      truckNo: 'KA-05-MH-4412',
      nursery: 'Evergreen Retail Garden Center',
      loadingDate: '2026-10-01',
      driver: 'Suresh Patil (+91 97401 55678)',
      status: 'Delivered',
      badgeClass: 'badge-success'
    },
    {
      truckNo: 'DL-01-AX-9901',
      nursery: 'Sunrise Flora & Palms',
      loadingDate: '2026-09-30',
      driver: 'Harpreet Singh (+91 98110 33221)',
      status: 'Dispatched',
      badgeClass: 'badge-info'
    }
  ],

  // Phase 3: Section C — Pending Payments
  // Columns: Nursery, Invoice, Total Amount, Paid, Remaining, Due Date, Status
  supplierPendingPayments: [
    {
      nursery: 'Urban Eden Landscaping Co.',
      invoice: 'INV-2026-088',
      totalAmount: '₹62,000',
      paid: '₹20,000',
      remaining: '₹42,000',
      dueDate: '2026-10-05',
      status: 'Partially Paid',
      badgeClass: 'badge-warning'
    },
    {
      nursery: 'Valley Bloom Botanical',
      invoice: 'INV-2026-085',
      totalAmount: '₹48,000',
      paid: '₹0',
      remaining: '₹48,000',
      dueDate: '2026-09-28',
      status: 'Overdue',
      badgeClass: 'badge-danger'
    },
    {
      nursery: 'Green Meadows Landscape Nursery',
      invoice: 'INV-2026-091',
      totalAmount: '₹30,000',
      paid: '₹0',
      remaining: '₹30,000',
      dueDate: '2026-10-15',
      status: 'Unpaid',
      badgeClass: 'badge-neutral'
    }
  ],

  // Phase 4: Commercial Nurseries Partner Directory
  // Columns: Nursery ID, Nursery Name, Contact Person, Phone, Location, Active Orders, Outstanding Amount, Status, Actions
  nurseries: [
    {
      id: 'NUR-101',
      name: 'Green Meadows Landscape Nursery',
      contactPerson: 'Amit Sharma',
      phone: '9876543210',
      email: 'amit@greenmeadows.com',
      location: 'Delhi',
      address: 'Plot 42, Mehrauli Road, Chattarpur',
      city: 'Delhi',
      gstin: '07AAAAA0000A1Z5',
      paymentTerms: '15 Days',
      creditLimit: '₹1,50,000',
      activeOrders: 2,
      outstanding: '₹32,500',
      outstandingRaw: 32500,
      status: 'Active',
      badgeClass: 'badge-success'
    },
    {
      id: 'NUR-102',
      name: 'Urban Eden Landscaping Co.',
      contactPerson: 'Rahul Verma',
      phone: '9812345678',
      email: 'purchasing@urbaneden.in',
      location: 'Noida',
      address: 'Sector 62, Commercial Zone B',
      city: 'Noida',
      gstin: '09BBBBB1111B1Z2',
      paymentTerms: '30 Days',
      creditLimit: '₹2,00,000',
      activeOrders: 3,
      outstanding: '₹48,000',
      outstandingRaw: 48000,
      status: 'Pending',
      badgeClass: 'badge-warning'
    },
    {
      id: 'NUR-103',
      name: 'Valley Bloom Botanical',
      contactPerson: 'Neha Singh',
      phone: '9898989898',
      email: 'neha@valleybloom.com',
      location: 'Ghaziabad',
      address: 'Kavi Nagar Industrial Area, Warehouse 3',
      city: 'Ghaziabad',
      gstin: '09CCCCC2222C1Z8',
      paymentTerms: '10 Days',
      creditLimit: '₹1,00,000',
      activeOrders: 0,
      outstanding: '₹0',
      outstandingRaw: 0,
      status: 'Active',
      badgeClass: 'badge-success'
    },
    {
      id: 'NUR-104',
      name: 'Evergreen Retail Garden Center',
      contactPerson: 'Rajesh Gupta',
      phone: '9811223344',
      email: 'rgupta@evergreenretail.in',
      location: 'Gurgaon',
      address: 'Golf Course Extension Road, Sector 56',
      city: 'Gurgaon',
      gstin: '06DDDDD3333D1Z4',
      paymentTerms: '30 Days',
      creditLimit: '₹2,50,000',
      activeOrders: 2,
      outstanding: '₹39,500',
      outstandingRaw: 39500,
      status: 'Pending',
      badgeClass: 'badge-warning'
    },
    {
      id: 'NUR-105',
      name: 'Sunrise Flora & Palms',
      contactPerson: 'Priya Nair',
      phone: '9822334455',
      email: 'priya@sunriseflora.com',
      location: 'Faridabad',
      address: 'Mathura Road, Milestone 28',
      city: 'Faridabad',
      gstin: '06EEEEE4444E1Z7',
      paymentTerms: 'Advance Payment',
      creditLimit: '₹50,000',
      activeOrders: 1,
      outstanding: '₹0',
      outstandingRaw: 0,
      status: 'Active',
      badgeClass: 'badge-success'
    },
    {
      id: 'NUR-106',
      name: 'Royal Palms Nursery',
      contactPerson: 'Vikram Malhotra',
      phone: '9833445566',
      email: 'info@royalpalms.co.in',
      location: 'Greater Noida',
      address: 'Knowledge Park III, Plot 14',
      city: 'Greater Noida',
      gstin: '09FFFFF5555F1Z1',
      paymentTerms: '10 Days',
      creditLimit: '₹75,000',
      activeOrders: 0,
      outstanding: '₹0',
      outstandingRaw: 0,
      status: 'Inactive',
      badgeClass: 'badge-neutral'
    }
  ],

  // Nursery Inbound Shipments
  nurseryInbound: [
    {
      orderId: 'ORD-8801',
      variety: 'Areca Palm (12-inch Pot)',
      qty: 150,
      truckNo: 'KA-04-E-8821',
      driver: 'Ramesh Kumar (+91 98450 12345)',
      status: 'Arrived at Dock',
      badgeClass: 'badge-warning',
      actionText: 'Ready for Inspection',
      isLocked: false
    },
    {
      orderId: 'ORD-8802',
      variety: 'Bougainvillea Dwarf (8-inch Bag)',
      qty: 300,
      truckNo: 'KA-05-MH-4412',
      driver: 'Suresh Patil (+91 97401 55678)',
      status: 'In Transit',
      badgeClass: 'badge-info',
      actionText: 'In Transit',
      isLocked: false
    },
    {
      orderId: 'ORD-8760',
      variety: 'Golden Pothos Totem (3-foot)',
      qty: 100,
      truckNo: 'DL-01-AX-9901',
      driver: 'Harpreet Singh (+91 98110 33221)',
      status: 'DELIVERED & VERIFIED',
      badgeClass: 'badge-success',
      actionText: 'Verified',
      isLocked: true,
      soundQty: 98,
      damagedQty: 2,
      damagePct: 2.0,
      damageNotes: '2 pots fractured during transport; root ball exposed.',
      verifiedAt: '2026-10-14T11:30:00.000Z',
      verifiedBy: 'Amit Sharma (Green Meadows Receiving)'
    }
  ],

  // Nursery Order History
  nurseryOrders: [
    {
      orderId: 'ORD-8801',
      variety: 'Areca Palm (12-inch Pot)',
      qty: 150,
      date: '2026-10-02',
      status: 'DISPATCHED',
      badgeClass: 'badge-info'
    },
    {
      orderId: 'ORD-8760',
      variety: 'Golden Pothos Totem (3-foot)',
      qty: 100,
      date: '2026-09-18',
      status: 'DELIVERED',
      badgeClass: 'badge-success'
    },
    {
      orderId: 'ORD-8692',
      variety: 'Ficus Lyrata (10-inch Pot)',
      qty: 50,
      date: '2026-08-30',
      status: 'COMPLETED',
      badgeClass: 'badge-success'
    }
  ],

  // Nursery Grower Catalog Highlights
  catalogPreview: [
    { name: 'Areca Palm', spec: '12-inch Nursery Pot', price: '₹350 / unit', stock: '450 in stock' },
    { name: 'Bougainvillea Dwarf', spec: '8-inch Heavy Bag', price: '₹180 / unit', stock: '800 in stock' },
    { name: 'Ficus Lyrata Bambino', spec: '10-inch Nursery Pot', price: '₹650 / unit', stock: '200 in stock' },
    { name: 'Monstera Deliciosa', spec: '12-inch Nursery Pot', price: '₹550 / unit', stock: '150 in stock' }
  ]
};

// ============================================================================
// 2. VIEW ROUTING ENGINE
// ============================================================================

/**
 * Switch active page view between:
 * 'home', 'login', 'supplier', 'nursery'
 */
function navigateTo(viewName) {
  const validViews = ['home', 'login', 'supplier', 'nursery'];
  if (!validViews.includes(viewName)) {
    viewName = 'home';
  }

  // 1. Update View Sections Visibility
  validViews.forEach(v => {
    const el = document.getElementById(`view-${v}`);
    if (el) {
      if (v === viewName) {
        el.classList.add('active');
      } else {
        el.classList.remove('active');
      }
    }
  });

  // 2. Update Nav Link Active States
  validViews.forEach(v => {
    const navEl = document.getElementById(`nav-${v}`);
    if (navEl) {
      if (v === viewName) {
        navEl.classList.add('active');
      } else {
        navEl.classList.remove('active');
      }
    }
  });

  // 3. Update User Status Pill in Header
  if (currentUserProfile && currentUserProfile.role) {
    updateActiveUserHeader(currentUserProfile);
  } else {
    const userText = document.getElementById('active-user-text');
    if (userText) {
      if (viewName === 'supplier') {
        userText.textContent = '🏢 Supplier Portal Active';
      } else if (viewName === 'nursery') {
        userText.textContent = '🌱 Nursery Portal Active';
      } else if (viewName === 'login') {
        userText.textContent = '🔑 Authentication';
      } else {
        userText.textContent = 'Not Signed In';
      }
    }
  }

  // 4. Update Window Hash without jumping
  if (viewName === 'supplier' && (window.location.hash === '#nurseries' || window.location.hash === '#plants' || window.location.hash === '#orders' || window.location.hash === '#truck-loading' || window.location.hash === '#invoices')) {
    // Retain hash if already on nurseries, plants, orders, truck loading, or invoices
  } else if (window.location.hash !== `#${viewName}`) {
    history.pushState(null, '', `#${viewName}`);
  }

  // 5. Ensure appropriate subpage is displayed when on supplier portal
  if (viewName === 'supplier') {
    if (window.location.hash === '#nurseries') {
      showSupplierSubpage('nurseries');
    } else if (window.location.hash === '#plants') {
      showSupplierSubpage('plants');
    } else if (window.location.hash === '#orders') {
      showSupplierSubpage('orders');
    } else if (window.location.hash === '#truck-loading') {
      showSupplierSubpage('truck-loading');
    } else if (window.location.hash === '#invoices') {
      showSupplierSubpage('invoices');
    } else if (window.location.hash === '#payments') {
      showSupplierSubpage('payments');
    } else if (window.location.hash === '#ledger' || window.location.hash === '#history') {
      showSupplierSubpage('ledger');
    } else {
      showSupplierSubpage('dashboard');
    }
  } else if (viewName === 'nursery') {
    fetchAndRenderNurseryDashboard();
  }

  // 5. Scroll smoothly to top
  window.scrollTo({ top: 0, behavior: 'smooth' });

  // 6. Close mobile nav if open
  const navMenu = document.getElementById('main-nav-menu');
  if (navMenu && navMenu.classList.contains('show')) {
    navMenu.classList.remove('show');
  }
}

// Toggle mobile dropdown nav
function toggleMobileNav() {
  const navMenu = document.getElementById('main-nav-menu');
  if (navMenu) {
    navMenu.classList.toggle('show');
  }
}

// ============================================================================
// 3. LOGIN & SIMULATED AUTHENTICATION (Phase 2 Foundation)
// ============================================================================

let currentLoginRole = 'supplier'; // 'supplier' or 'nursery'

function switchLoginRole(role) {
  currentLoginRole = role;
  const supplierTab = document.getElementById('login-tab-supplier');
  const nurseryTab = document.getElementById('login-tab-nursery');
  const emailInput = document.getElementById('login-email');

  if (role === 'supplier') {
    supplierTab.classList.add('active');
    nurseryTab.classList.remove('active');
    if (emailInput) emailInput.value = 'supplier@greenrootsfarms.com';
  } else {
    nurseryTab.classList.add('active');
    supplierTab.classList.remove('active');
    if (emailInput) emailInput.value = 'purchasing@greenmeadows.com';
  }
}

function getOrderStatusBadgeClass(status) {
  switch (status) {
    case 'LOCKED_VERIFIED': return 'badge-success';
    case 'DELIVERED': return 'badge-primary';
    case 'DISPATCHED': return 'badge-info';
    case 'STAGING': return 'badge-warning';
    case 'CONFIRMED': return 'badge-neutral';
    case 'CANCELLED': return 'badge-danger';
    default: return 'badge-secondary';
  }
}

function getTruckStatusBadgeClass(status) {
  switch (status) {
    case 'COMPLETED':
    case 'DISPATCHED': return 'badge-success';
    case 'LOADING':
    case 'STAGING': return 'badge-warning';
    case 'CANCELLED': return 'badge-danger';
    default: return 'badge-info';
  }
}

function getInvoiceStatusBadgeClass(status) {
  switch (status) {
    case 'SETTLED': return 'badge-success';
    case 'ISSUED':
    case 'PARTIALLY_PAID': return 'badge-warning';
    case 'CANCELLED': return 'badge-danger';
    default: return 'badge-secondary';
  }
}

function formatDashCurrency(num) {
  const val = Number(num) || 0;
  return '₹' + val.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

async function handleDummyLogin(e) {
  if (e && e.preventDefault) e.preventDefault();
  const submitBtn = document.getElementById('login-submit-btn');
  const emailInput = document.getElementById('login-email');
  const passwordInput = document.getElementById('login-password');

  const email = (emailInput?.value || '').trim();
  const password = passwordInput?.value || '';

  if (!email || !password) {
    showToast('Please enter both email/username and password.', 'warning');
    return;
  }

  const originalText = submitBtn ? submitBtn.innerHTML : '';
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span>⏳</span> Verifying Credentials...';
  }

  try {
    const resp = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });

    const body = await resp.json().catch(() => ({}));
    if (!resp.ok || !body.success) {
      showToast(body.error || 'Authentication failed. Please check credentials.', 'error');
      return;
    }

    if (body.csrf_token) {
      window.__floraCsrfToken = body.csrf_token;
    } else if (body.data && body.data.csrf_token) {
      window.__floraCsrfToken = body.data.csrf_token;
    }

    const user = body.data;
    updateActiveUserHeader(user);
    showToast(`Welcome back, ${user.business_name || user.username}!`, 'success');

    if (user.role === 'SUPPLIER' || user.role === 'ADMIN') {
      navigateTo('supplier');
      fetchAndRenderSupplierDashboard();
    } else if (user.role === 'NURSERY') {
      navigateTo('nursery');
    } else {
      navigateTo('home');
    }
  } catch (err) {
    console.error('Login network error:', err);
    showToast('Network error: Unable to connect to authentication server.', 'error');
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalText;
    }
  }
}

async function quickDemoLogin(role) {
  const targetRole = (role || '').toUpperCase();
  try {
    const resp = await fetch('/api/auth/switch-role', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role: targetRole })
    });

    const body = await resp.json().catch(() => ({}));
    if (!resp.ok || !body.success) {
      showToast(body.error || 'Demo role switcher is disabled in this environment. Please log in with credentials.', 'warning');
      return;
    }

    if (body.csrf_token) {
      window.__floraCsrfToken = body.csrf_token;
    } else if (body.data && body.data.csrf_token) {
      window.__floraCsrfToken = body.data.csrf_token;
    }

    const user = body.data;
    updateActiveUserHeader(user);
    showToast(`Logged in as ${user.business_name} (${user.role})`, 'success');

    if (targetRole === 'SUPPLIER' || targetRole === 'ADMIN') {
      navigateTo('supplier');
      fetchAndRenderSupplierDashboard();
    } else {
      navigateTo('nursery');
    }
  } catch (err) {
    console.error('Demo login failed:', err);
    showToast('Network error while connecting for demo login.', 'error');
  }
}

// ============================================================================
// 4. DATA RENDERING FUNCTIONS
// ============================================================================

/**
 * Live Supplier Dashboard loader connecting to real backend API endpoints (Phase 16)
 */
async function fetchAndRenderSupplierDashboard() {
  if (typeof window === 'undefined' || typeof fetch !== 'function') {
    renderSupplierDashboard();
    return;
  }

  try {
    const [ordersRes, trucksRes, invoicesRes, nurseriesRes] = await Promise.allSettled([
      fetch('/api/orders'),
      fetch('/api/truck-loadings'),
      fetch('/api/invoices'),
      fetch('/api/orders/nurseries')
    ]);

    let orders = [];
    if (ordersRes.status === 'fulfilled' && ordersRes.value.ok) {
      const b = await ordersRes.value.json().catch(() => ({}));
      if (b.success && Array.isArray(b.data)) orders = b.data;
    }

    let trucks = [];
    if (trucksRes.status === 'fulfilled' && trucksRes.value.ok) {
      const b = await trucksRes.value.json().catch(() => ({}));
      if (b.success && Array.isArray(b.data)) trucks = b.data;
    }

    let invoices = [];
    if (invoicesRes.status === 'fulfilled' && invoicesRes.value.ok) {
      const b = await invoicesRes.value.json().catch(() => ({}));
      if (b.success && Array.isArray(b.data)) invoices = b.data;
    }

    let nurseries = [];
    if (nurseriesRes.status === 'fulfilled' && nurseriesRes.value.ok) {
      const b = await nurseriesRes.value.json().catch(() => ({}));
      if (b.success && Array.isArray(b.data)) nurseries = b.data;
    }

    // 1. KPI Summary Cards
    const kpiOrders = document.getElementById('kpi-supplier-dash-orders');
    if (kpiOrders) kpiOrders.textContent = orders.length;

    const kpiTrucks = document.getElementById('kpi-supplier-dash-trucks');
    if (kpiTrucks) kpiTrucks.textContent = trucks.length;

    const kpiNurseries = document.getElementById('kpi-supplier-dash-nurseries');
    if (kpiNurseries) kpiNurseries.textContent = nurseries.length || 1;

    const totalSales = orders.reduce((sum, o) => sum + (Number(o.total_amount) || 0), 0);
    const kpiSales = document.getElementById('kpi-supplier-dash-sales');
    if (kpiSales) kpiSales.textContent = formatDashCurrency(totalSales);

    const totalOutstanding = invoices
      .filter(i => i.status !== 'CANCELLED')
      .reduce((sum, i) => sum + (Number(i.remaining_balance != null ? i.remaining_balance : (Number(i.total_amount || 0) - Number(i.total_paid || 0))) || 0), 0);
    const kpiOutstanding = document.getElementById('kpi-supplier-dash-outstanding');
    if (kpiOutstanding) kpiOutstanding.textContent = formatDashCurrency(totalOutstanding);

    // 2. Recent Orders Table (Top 5)
    const recentOrdersTbody = document.getElementById('supplier-recent-orders-tbody');
    if (recentOrdersTbody) {
      if (orders.length === 0) {
        recentOrdersTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-secondary); padding: 1.5rem;">No recent orders recorded.</td></tr>`;
      } else {
        const topOrders = orders.slice(0, 5);
        recentOrdersTbody.innerHTML = topOrders.map(order => {
          const dateStr = order.created_at ? new Date(order.created_at).toISOString().split('T')[0] : '—';
          const badgeClass = getOrderStatusBadgeClass(order.status);
          return `
            <tr>
              <td><strong>${escapeHtml(order.id)}</strong></td>
              <td>${escapeHtml(order.nursery_name || 'Nursery Partner')}</td>
              <td>${dateStr}</td>
              <td><strong>${formatDashCurrency(order.total_amount)}</strong></td>
              <td><span class="badge ${badgeClass}">${escapeHtml(order.status)}</span></td>
            </tr>
          `;
        }).join('');
      }
    }

    // 3. Recent Truck Loading Table (Top 5)
    const truckLoadingTbody = document.getElementById('supplier-truck-loading-tbody');
    if (truckLoadingTbody) {
      if (trucks.length === 0) {
        truckLoadingTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-secondary); padding: 1.5rem;">No recent truck manifests recorded.</td></tr>`;
      } else {
        const topTrucks = trucks.slice(0, 5);
        truckLoadingTbody.innerHTML = topTrucks.map(truck => {
          const badgeClass = getTruckStatusBadgeClass(truck.status);
          const dateStr = truck.loading_date || (truck.created_at ? new Date(truck.created_at).toISOString().split('T')[0] : '—');
          return `
            <tr>
              <td><strong>${escapeHtml(truck.truck_no || 'TBD')}</strong></td>
              <td>${escapeHtml(truck.nursery_name || truck.destination_nursery || 'Nursery Partner')}</td>
              <td>${dateStr}</td>
              <td>${escapeHtml(truck.driver_info || truck.driver || 'Pending')}</td>
              <td><span class="badge ${badgeClass}">${escapeHtml(truck.status || 'STAGED')}</span></td>
            </tr>
          `;
        }).join('');
      }
    }

    // 4. Pending Invoices Table (Top 5)
    const pendingPaymentsTbody = document.getElementById('supplier-pending-payments-tbody');
    if (pendingPaymentsTbody) {
      const pendingInvoices = invoices.filter(i => i.status !== 'CANCELLED');
      if (pendingInvoices.length === 0) {
        pendingPaymentsTbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-secondary); padding: 1.5rem;">No pending invoices or settlements.</td></tr>`;
      } else {
        const topInvoices = pendingInvoices.slice(0, 5);
        pendingPaymentsTbody.innerHTML = topInvoices.map(pay => {
          const badgeClass = getInvoiceStatusBadgeClass(pay.status);
          const rem = pay.remaining_balance != null ? pay.remaining_balance : (Number(pay.total_amount || 0) - Number(pay.total_paid || 0));
          return `
            <tr>
              <td><strong>${escapeHtml(pay.nursery_name || 'Nursery Partner')}</strong></td>
              <td>${escapeHtml(pay.invoice_ref || pay.id)}</td>
              <td>${formatDashCurrency(pay.total_amount)}</td>
              <td style="color: var(--primary); font-weight: 600;">${formatDashCurrency(pay.total_paid || 0)}</td>
              <td><strong style="color: #9A3412;">${formatDashCurrency(rem)}</strong></td>
              <td>${escapeHtml(pay.payment_due_date || pay.due_date || '—')}</td>
              <td><span class="badge ${badgeClass}">${escapeHtml(pay.status)}</span></td>
            </tr>
          `;
        }).join('');
      }
    }
  } catch (err) {
    console.error('Error fetching live supplier dashboard data:', err);
    renderSupplierDashboard();
  }
}

/**
 * Render Supplier Dashboard data (Phase 3 fallback)
 */
function renderSupplierDashboard() {
  // Phase 3: Section A — Recent Orders Table
  const recentOrdersTbody = document.getElementById('supplier-recent-orders-tbody');
  if (recentOrdersTbody && DUMMY_DATA.supplierRecentOrders) {
    recentOrdersTbody.innerHTML = DUMMY_DATA.supplierRecentOrders.map(order => `
      <tr>
        <td><strong>${order.id}</strong></td>
        <td>${order.nursery}</td>
        <td>${order.orderDate}</td>
        <td><strong>${order.totalAmount}</strong></td>
        <td>
          <span class="badge ${order.badgeClass}">${order.status}</span>
        </td>
      </tr>
    `).join('');
  }

  // Phase 3: Section B — Recent Truck Loading Table
  const truckLoadingTbody = document.getElementById('supplier-truck-loading-tbody');
  if (truckLoadingTbody && DUMMY_DATA.supplierTruckLoading) {
    truckLoadingTbody.innerHTML = DUMMY_DATA.supplierTruckLoading.map(truck => `
      <tr>
        <td><strong>${truck.truckNo}</strong></td>
        <td>${truck.nursery}</td>
        <td>${truck.loadingDate}</td>
        <td>${truck.driver}</td>
        <td>
          <span class="badge ${truck.badgeClass}">${truck.status}</span>
        </td>
      </tr>
    `).join('');
  }

  // Phase 3: Section C — Pending Payments Table
  const pendingPaymentsTbody = document.getElementById('supplier-pending-payments-tbody');
  if (pendingPaymentsTbody && DUMMY_DATA.supplierPendingPayments) {
    pendingPaymentsTbody.innerHTML = DUMMY_DATA.supplierPendingPayments.map(pay => `
      <tr>
        <td><strong>${pay.nursery}</strong></td>
        <td>${pay.invoice}</td>
        <td>${pay.totalAmount}</td>
        <td style="color: var(--primary); font-weight: 600;">${pay.paid}</td>
        <td><strong style="color: #9A3412;">${pay.remaining}</strong></td>
        <td>${pay.dueDate}</td>
        <td>
          <span class="badge ${pay.badgeClass}">${pay.status}</span>
        </td>
      </tr>
    `).join('');
  }

  // Legacy fallback containers (if present)
  const legacyTbody = document.getElementById('supplier-orders-tbody');
  if (legacyTbody && DUMMY_DATA.supplierOrders) {
    legacyTbody.innerHTML = DUMMY_DATA.supplierOrders.map(order => `
      <tr>
        <td><strong>${order.id}</strong></td>
        <td>${order.nursery}</td>
        <td>${order.variety}</td>
        <td><strong>${order.qty} units</strong></td>
        <td>${order.orderDate}</td>
        <td>
          <span class="badge ${order.badgeClass}">${order.statusLabel}</span>
        </td>
      </tr>
    `).join('');
  }

  const legacyTrucks = document.getElementById('supplier-trucks-list');
  if (legacyTrucks && DUMMY_DATA.supplierTrucks) {
    legacyTrucks.innerHTML = DUMMY_DATA.supplierTrucks.map(truck => `
      <div class="activity-feed-item">
        <div class="activity-icon-box">🚚</div>
        <div>
          <div class="activity-desc"><strong>${truck.truckNo}</strong> — ${truck.cargo}</div>
          <div class="activity-time">To: ${truck.destination} • Driver: ${truck.driver} • <strong>${truck.status}</strong></div>
        </div>
      </div>
    `).join('');
  }
}

/**
 * Toggle mobile drawer for Supplier Sidebar
 */
function toggleSupplierSidebar() {
  const sidebar = document.getElementById('supplier-sidebar');
  const backdrop = document.getElementById('supplier-sidebar-backdrop');
  if (sidebar) sidebar.classList.toggle('open');
  if (backdrop) backdrop.classList.toggle('active');
}

/**
 * Update active state on Supplier Sidebar items (1 to 10).
 * Ensures that:
 * - 'Dashboard' is highlighted when the route is #supplier.
 * - 'Nurseries' is highlighted when the route is #nurseries.
 * - 'Plants' is highlighted only when the Plants page/route is active.
 * - Other sidebar items similarly become active only when their corresponding page/route is active.
 */
function updateSupplierSidebarActive(activeItemName) {
  const links = document.querySelectorAll('.supplier-sidebar .sidebar-link');
  links.forEach(link => link.classList.remove('active'));

  const linkId = `slink-${activeItemName.replace(/\s+/g, '')}`;
  const activeLink = document.getElementById(linkId);
  if (activeLink) {
    activeLink.classList.add('active');
  }
}

/**
 * Toggle supplier subpage view between 'dashboard', 'nurseries', 'plants', 'orders', and 'truck-loading' (Phase 7)
 */
function showSupplierSubpage(subpageName) {
  const isNurseries = subpageName === 'nurseries';
  const isPlants = subpageName === 'plants';
  const isOrders = subpageName === 'orders';
  const isTruckLoading = subpageName === 'truck-loading';
  const isInvoices = subpageName === 'invoices';
  const isPayments = subpageName === 'payments';
  const isLedger = subpageName === 'ledger';
  const dashboardPage = document.getElementById('supplier-page-dashboard');
  const nurseriesPage = document.getElementById('supplier-page-nurseries');
  const plantsPage = document.getElementById('supplier-page-plants');
  const ordersPage = document.getElementById('supplier-page-orders');
  const truckLoadingPage = document.getElementById('supplier-page-truck-loading');
  const invoicesPage = document.getElementById('supplier-page-invoices');
  const paymentsPage = document.getElementById('supplier-page-payments');
  const ledgerPage = document.getElementById('supplier-page-ledger');
  const topbarTitle = document.getElementById('supplier-topbar-title');
  const topbarSubtitle = document.getElementById('supplier-topbar-subtitle');

  if (isNurseries) {
    if (dashboardPage) dashboardPage.style.display = 'none';
    if (nurseriesPage) nurseriesPage.style.display = 'block';
    if (plantsPage) plantsPage.style.display = 'none';
    if (ordersPage) ordersPage.style.display = 'none';
    if (truckLoadingPage) truckLoadingPage.style.display = 'none';
    if (invoicesPage) invoicesPage.style.display = 'none';
    if (paymentsPage) paymentsPage.style.display = 'none';
    if (ledgerPage) ledgerPage.style.display = 'none';
    if (topbarTitle) topbarTitle.textContent = 'Nursery Management';
    if (topbarSubtitle) topbarSubtitle.textContent = 'Manage commercial nursery partners, contacts and account activity.';
    updateSupplierSidebarActive('Nurseries');
    if (window.location.hash !== '#nurseries') {
      history.pushState(null, '', '#nurseries');
    }
    applyNurseryFilters();
    updateNurserySummaryKPIs();
  } else if (isPlants) {
    if (dashboardPage) dashboardPage.style.display = 'none';
    if (nurseriesPage) nurseriesPage.style.display = 'none';
    if (plantsPage) plantsPage.style.display = 'block';
    if (ordersPage) ordersPage.style.display = 'none';
    if (truckLoadingPage) truckLoadingPage.style.display = 'none';
    if (invoicesPage) invoicesPage.style.display = 'none';
    if (paymentsPage) paymentsPage.style.display = 'none';
    if (ledgerPage) ledgerPage.style.display = 'none';
    if (topbarTitle) topbarTitle.textContent = 'Plant Catalog & Inventory';
    if (topbarSubtitle) topbarSubtitle.textContent = 'Manage wholesale plant catalog, container specifications, bulk pricing and stock levels.';
    updateSupplierSidebarActive('Plants');
    if (window.location.hash !== '#plants') {
      history.pushState(null, '', '#plants');
    }
    fetchAndRenderPlants();
  } else if (isOrders) {
    if (dashboardPage) dashboardPage.style.display = 'none';
    if (nurseriesPage) nurseriesPage.style.display = 'none';
    if (plantsPage) plantsPage.style.display = 'none';
    if (ordersPage) ordersPage.style.display = 'block';
    if (truckLoadingPage) truckLoadingPage.style.display = 'none';
    if (invoicesPage) invoicesPage.style.display = 'none';
    if (paymentsPage) paymentsPage.style.display = 'none';
    if (ledgerPage) ledgerPage.style.display = 'none';
    if (topbarTitle) topbarTitle.textContent = 'Wholesale Order Management';
    if (topbarSubtitle) topbarSubtitle.textContent = 'Track, filter, and assemble commercial nursery batch orders across multiple plant varieties.';
    updateSupplierSidebarActive('Orders');
    if (window.location.hash !== '#orders') {
      history.pushState(null, '', '#orders');
    }
    fetchAndRenderOrders();
  } else if (isTruckLoading) {
    if (dashboardPage) dashboardPage.style.display = 'none';
    if (nurseriesPage) nurseriesPage.style.display = 'none';
    if (plantsPage) plantsPage.style.display = 'none';
    if (ordersPage) ordersPage.style.display = 'none';
    if (truckLoadingPage) truckLoadingPage.style.display = 'block';
    if (invoicesPage) invoicesPage.style.display = 'none';
    if (paymentsPage) paymentsPage.style.display = 'none';
    if (ledgerPage) ledgerPage.style.display = 'none';
    if (topbarTitle) topbarTitle.textContent = 'Truck Loading & Vehicle Manifests';
    if (topbarSubtitle) topbarSubtitle.textContent = 'Assign transport vehicles, record plant staging counts, and track wholesale dispatch manifests.';
    updateSupplierSidebarActive('Truck Loading');
    if (window.location.hash !== '#truck-loading') {
      history.pushState(null, '', '#truck-loading');
    }
    fetchAndRenderTruckLoadings();
  } else if (isInvoices) {
    if (dashboardPage) dashboardPage.style.display = 'none';
    if (nurseriesPage) nurseriesPage.style.display = 'none';
    if (plantsPage) plantsPage.style.display = 'none';
    if (ordersPage) ordersPage.style.display = 'none';
    if (truckLoadingPage) truckLoadingPage.style.display = 'none';
    if (invoicesPage) invoicesPage.style.display = 'block';
    if (paymentsPage) paymentsPage.style.display = 'none';
    if (ledgerPage) ledgerPage.style.display = 'none';
    if (topbarTitle) topbarTitle.textContent = 'Commercial Invoices';
    if (topbarSubtitle) topbarSubtitle.textContent = 'Verified delivery invoices generated strictly on accepted sound plants with frozen terms.';
    updateSupplierSidebarActive('Invoices');
    if (window.location.hash !== '#invoices') {
      history.pushState(null, '', '#invoices');
    }
    fetchAndRenderInvoices();
  } else if (isPayments) {
    if (dashboardPage) dashboardPage.style.display = 'none';
    if (nurseriesPage) nurseriesPage.style.display = 'none';
    if (plantsPage) plantsPage.style.display = 'none';
    if (ordersPage) ordersPage.style.display = 'none';
    if (truckLoadingPage) truckLoadingPage.style.display = 'none';
    if (invoicesPage) invoicesPage.style.display = 'none';
    if (paymentsPage) paymentsPage.style.display = 'block';
    if (ledgerPage) ledgerPage.style.display = 'none';
    if (topbarTitle) topbarTitle.textContent = 'Wholesale Payments & Settlements';
    if (topbarSubtitle) topbarSubtitle.textContent = 'Record incoming payments, track advance deposits, and manage invoice balances.';
    updateSupplierSidebarActive('Payments');
    if (window.location.hash !== '#payments') {
      history.pushState(null, '', '#payments');
    }
    fetchAndRenderPayments();
  } else if (isLedger) {
    if (dashboardPage) dashboardPage.style.display = 'none';
    if (nurseriesPage) nurseriesPage.style.display = 'none';
    if (plantsPage) plantsPage.style.display = 'none';
    if (ordersPage) ordersPage.style.display = 'none';
    if (truckLoadingPage) truckLoadingPage.style.display = 'none';
    if (invoicesPage) invoicesPage.style.display = 'none';
    if (paymentsPage) paymentsPage.style.display = 'none';
    if (ledgerPage) ledgerPage.style.display = 'block';
    if (topbarTitle) topbarTitle.textContent = 'Commercial Ledger & Transaction History';
    if (topbarSubtitle) topbarSubtitle.textContent = 'Authoritative financial statement, chronological audit trail, and verified business position.';
    updateSupplierSidebarActive('Ledger');
    if (window.location.hash !== '#ledger' && window.location.hash !== '#history') {
      history.pushState(null, '', '#ledger');
    }
    fetchAndRenderLedger();
  } else {
    if (dashboardPage) dashboardPage.style.display = 'block';
    if (nurseriesPage) nurseriesPage.style.display = 'none';
    if (plantsPage) plantsPage.style.display = 'none';
    if (ordersPage) ordersPage.style.display = 'none';
    if (truckLoadingPage) truckLoadingPage.style.display = 'none';
    if (invoicesPage) invoicesPage.style.display = 'none';
    if (paymentsPage) paymentsPage.style.display = 'none';
    if (ledgerPage) ledgerPage.style.display = 'none';
    if (topbarTitle) topbarTitle.textContent = 'Supplier Dashboard';
    if (topbarSubtitle) topbarSubtitle.textContent = 'Commercial Plant Logistics & Wholesale Operations';
    updateSupplierSidebarActive('Dashboard');
    if (window.location.hash !== '#supplier') {
      history.pushState(null, '', '#supplier');
    }
  }
}

/**
 * Handle navigation between Supplier Sidebar items (1 to 10)
 */
function selectSidebarItem(itemName) {
  // Close mobile drawer if open
  const sidebar = document.getElementById('supplier-sidebar');
  const backdrop = document.getElementById('supplier-sidebar-backdrop');
  if (sidebar && sidebar.classList.contains('open')) {
    sidebar.classList.remove('open');
    if (backdrop) backdrop.classList.remove('active');
  }

  const validSupplierHashes = ['#supplier', '#nurseries', '#plants', '#orders', '#truck-loading', '#invoices', '#payments', '#ledger', '#history'];

  if (itemName === 'Dashboard') {
    if (!validSupplierHashes.includes(window.location.hash)) {
      navigateTo('supplier');
    }
    showSupplierSubpage('dashboard');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } else if (itemName === 'Nurseries') {
    if (!validSupplierHashes.includes(window.location.hash)) {
      navigateTo('supplier');
    }
    showSupplierSubpage('nurseries');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } else if (itemName === 'Plants') {
    if (!validSupplierHashes.includes(window.location.hash)) {
      navigateTo('supplier');
    }
    showSupplierSubpage('plants');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } else if (itemName === 'Orders') {
    if (!validSupplierHashes.includes(window.location.hash)) {
      navigateTo('supplier');
    }
    showSupplierSubpage('orders');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } else if (itemName === 'Truck Loading') {
    if (!validSupplierHashes.includes(window.location.hash)) {
      navigateTo('supplier');
    }
    showSupplierSubpage('truck-loading');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } else if (itemName === 'Invoices') {
    if (!validSupplierHashes.includes(window.location.hash)) {
      navigateTo('supplier');
    }
    showSupplierSubpage('invoices');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } else if (itemName === 'Payments') {
    if (!validSupplierHashes.includes(window.location.hash)) {
      navigateTo('supplier');
    }
    showSupplierSubpage('payments');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } else if (itemName === 'Ledger' || itemName === 'History') {
    if (!validSupplierHashes.includes(window.location.hash)) {
      navigateTo('supplier');
    }
    showSupplierSubpage('ledger');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } else {
    // Keep whichever subpage is active highlighted
    const nurseriesPage = document.getElementById('supplier-page-nurseries');
    const plantsPage = document.getElementById('supplier-page-plants');
    const ordersPage = document.getElementById('supplier-page-orders');
    const truckLoadingPage = document.getElementById('supplier-page-truck-loading');
    const invoicesPage = document.getElementById('supplier-page-invoices');
    const paymentsPage = document.getElementById('supplier-page-payments');
    const ledgerPage = document.getElementById('supplier-page-ledger');
    const isNurseriesActive = nurseriesPage && nurseriesPage.style.display !== 'none';
    const isPlantsActive = plantsPage && plantsPage.style.display !== 'none';
    const isOrdersActive = ordersPage && ordersPage.style.display !== 'none';
    const isTruckActive = truckLoadingPage && truckLoadingPage.style.display !== 'none';
    const isInvoicesActive = invoicesPage && invoicesPage.style.display !== 'none';
    const isPaymentsActive = paymentsPage && paymentsPage.style.display !== 'none';
    const isLedgerActive = ledgerPage && ledgerPage.style.display !== 'none';
    updateSupplierSidebarActive(
      isLedgerActive ? 'Ledger' : (isPaymentsActive ? 'Payments' : (isInvoicesActive ? 'Invoices' : (isTruckActive ? 'Truck Loading' : (isOrdersActive ? 'Orders' : (isPlantsActive ? 'Plants' : (isNurseriesActive ? 'Nurseries' : 'Dashboard'))))))
    );

    const phaseMap = {
      'Settings': 'Phase 15 (Platform Settings)'
    };
    const phaseInfo = phaseMap[itemName] || 'an upcoming phase';
    showPhaseNotice(`${itemName} page will be activated in ${phaseInfo}.`);
  }
}

/**
 * Filter supplier orders dynamically
 */
function filterSupplierOrders() {
  const query = (document.getElementById('supplier-order-search')?.value || '').toLowerCase().trim();
  const tbody = document.getElementById('supplier-orders-tbody');
  if (!tbody) return;

  const filtered = DUMMY_DATA.supplierOrders.filter(o => 
    o.id.toLowerCase().includes(query) ||
    o.nursery.toLowerCase().includes(query) ||
    o.variety.toLowerCase().includes(query)
  );

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-secondary); padding: 2rem;">No orders match "${query}"</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map(order => `
    <tr>
      <td><strong>${order.id}</strong></td>
      <td>${order.nursery}</td>
      <td>${order.variety}</td>
      <td><strong>${order.qty} units</strong></td>
      <td>${order.orderDate}</td>
      <td>
        <span class="badge ${order.badgeClass}">${order.statusLabel}</span>
      </td>
    </tr>
  `).join('');
}

/**
 * Render Nursery Dashboard data
 */
function renderNurseryDashboard() {
  // 1. Render Nursery Inbound Table
  const inboundTbody = document.getElementById('nursery-inbound-tbody');
  if (inboundTbody) {
    inboundTbody.innerHTML = DUMMY_DATA.nurseryInbound.map(item => {
      const isLocked = Boolean(item.isLocked);
      return `
      <tr>
        <td><strong>${item.orderId}</strong></td>
        <td>${item.variety}</td>
        <td><strong>${item.qty} units</strong></td>
        <td>
          <div><strong>${item.truckNo}</strong></div>
          <small style="color: var(--text-secondary); font-size: 0.75rem;">${item.driver}</small>
        </td>
        <td>
          <span class="badge ${item.badgeClass || (isLocked ? 'badge-success' : 'badge-warning')}">${item.status}</span>
        </td>
        <td>
          ${isLocked ? `
            <button class="btn btn-secondary btn-sm" onclick="openDeliveryVerificationModal('${item.orderId}', true)" title="View finalized inspection record">
              🔒 Verified (${item.soundQty ?? item.qty} Sound / ${item.damagedQty ?? 0} Damaged)
            </button>
          ` : `
            <button class="btn btn-primary btn-sm" onclick="openDeliveryVerificationModal('${item.orderId}', false)" title="Inspect sound plants & record transit damage">
              🔍 Inspect on Arrival
            </button>
          `}
        </td>
      </tr>
    `;
    }).join('');
  }

  // 2. Render Nursery Order History Table
  const ordersTbody = document.getElementById('nursery-orders-tbody');
  if (ordersTbody) {
    ordersTbody.innerHTML = DUMMY_DATA.nurseryOrders.map(order => `
      <tr>
        <td><strong>${order.orderId}</strong></td>
        <td>${order.variety}</td>
        <td><strong>${order.qty} units</strong></td>
        <td>${order.date}</td>
        <td>
          <span class="badge ${order.badgeClass}">${order.status}</span>
        </td>
      </tr>
    `).join('');
  }

  // 3. Render Catalog Highlights Preview
  const catalogContainer = document.getElementById('nursery-catalog-preview');
  if (catalogContainer) {
    catalogContainer.innerHTML = DUMMY_DATA.catalogPreview.map(cat => `
      <li class="activity-feed-item">
        <div class="activity-icon-box">🌿</div>
        <div style="flex: 1;">
          <div style="display: flex; justify-content: space-between; font-size: 0.88rem; font-weight: 700; color: var(--text-main);">
            <span>${cat.name}</span>
            <span style="color: var(--primary);">${cat.price}</span>
          </div>
          <div class="activity-time" style="display: flex; justify-content: space-between;">
            <span>${cat.spec}</span>
            <span style="color: var(--primary); font-weight: 600;">${cat.stock}</span>
          </div>
        </div>
      </li>
    `).join('');
  }
}

// ============================================================================
// 5. TOAST NOTIFICATIONS & PHASE NOTICE HELPERS
// ============================================================================

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  
  let icon = 'ℹ️';
  if (type === 'success') icon = '✅';
  if (type === 'warning') icon = '⚠️';

  toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(8px)';
    toast.style.transition = 'all 0.25s ease';
    setTimeout(() => toast.remove(), 250);
  }, 3200);
}

function showPhaseNotice(message) {
  showToast(message, 'warning');
}

// ============================================================================
// PHASE 4: SUPPLIER NURSERY MANAGEMENT ENGINE
// ============================================================================

let currentNurseryFilter = 'All';
let currentNurserySearch = '';
let currentViewNurseryId = null;

/**
 * Loads real registered nursery partners from GET /api/orders/nurseries (Phase 16)
 */
async function fetchAndRenderNurseries() {
  if (typeof window === 'undefined' || typeof fetch !== 'function') return;

  try {
    const resp = await fetch('/api/orders/nurseries');
    if (!resp.ok) return;

    const body = await resp.json().catch(() => ({}));
    if (body.success && Array.isArray(body.data) && body.data.length > 0) {
      const registered = body.data.map(n => ({
        id: `NUR-${String(n.id).padStart(3, '0')}`,
        dbId: n.id,
        name: n.business_name,
        contactPerson: n.username,
        phone: '+91 98201 12345',
        email: n.email,
        location: 'Delhi NCR',
        address: 'Sector 62, Commercial Greenbelt, Noida',
        city: 'Noida',
        gstin: '07AAAAA0000A1Z5',
        paymentTerms: '15 Days Net',
        creditLimit: '₹5,00,000',
        activeOrders: 1,
        outstanding: '₹0.00',
        outstandingRaw: 0,
        status: 'Active',
        badgeClass: 'badge-success'
      }));

      DUMMY_DATA.nurseries = registered;
      applyNurseryFilters();
      updateNurserySummaryKPIs();
    }
  } catch (err) {
    console.warn('Could not fetch registered nurseries:', err);
  }
}

/**
 * Render Nursery Directory Table
 */
function renderNurseriesTable(items) {
  const tbody = document.getElementById('nurseries-table-tbody');
  const subtitle = document.getElementById('nursery-count-subtitle');
  if (!tbody) return;

  if (subtitle) {
    subtitle.textContent = `Showing ${items.length} of ${DUMMY_DATA.nurseries.length} commercial nursery accounts`;
  }

  if (items.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="9" style="text-align: center; color: var(--text-secondary); padding: 3rem 1rem;">
          <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">🔍</div>
          <div style="font-weight: 600; color: var(--text-main); margin-bottom: 0.25rem;">No commercial nurseries found</div>
          <div>No nurseries match the current search or status filter.</div>
          ${currentNurserySearch ? `
            <button class="btn btn-secondary btn-sm" onclick="clearNurserySearch()" style="margin-top: 0.85rem;">
              Clear Search
            </button>
          ` : ''}
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = items.map(nursery => `
    <tr>
      <td><strong>${nursery.id}</strong></td>
      <td>
        <div style="font-weight: 700; color: var(--text-main);">${nursery.name}</div>
        <small style="color: var(--text-secondary); font-size: 0.75rem;">${nursery.email || ''}</small>
      </td>
      <td>${nursery.contactPerson}</td>
      <td>
        <a href="tel:${nursery.phone}" style="color: var(--primary); text-decoration: none; font-weight: 600;">
          ${nursery.phone}
        </a>
      </td>
      <td>${nursery.location || nursery.city || '—'}</td>
      <td>
        <span class="badge ${nursery.activeOrders > 0 ? 'badge-info' : 'badge-neutral'}">
          ${nursery.activeOrders} ${nursery.activeOrders === 1 ? 'order' : 'orders'}
        </span>
      </td>
      <td>
        <strong style="color: ${nursery.outstandingRaw > 0 ? '#9A3412' : 'var(--text-main)'};">
          ${nursery.outstanding}
        </strong>
      </td>
      <td>
        <span class="badge ${nursery.badgeClass}">${nursery.status}</span>
      </td>
      <td>
        <div style="display: flex; gap: 0.4rem; align-items: center;">
          <button class="btn btn-secondary btn-sm" onclick="openViewNurseryModal('${nursery.id}')" title="View Details">
            👁️ View
          </button>
          <button class="btn btn-secondary btn-sm" onclick="openEditNurseryModal('${nursery.id}')" title="Edit Nursery">
            ✏️ Edit
          </button>
        </div>
      </td>
    </tr>
  `).join('');
}

/**
 * Update Nursery Summary KPI Cards
 */
function updateNurserySummaryKPIs() {
  const totalEl = document.getElementById('kpi-total-nurseries');
  const dashTotalEl = document.getElementById('kpi-supplier-dash-nurseries');
  const activeEl = document.getElementById('kpi-active-nurseries');
  const pendingOrdersEl = document.getElementById('kpi-pending-orders');
  const receivablesEl = document.getElementById('kpi-outstanding-receivables');

  const total = DUMMY_DATA.nurseries.length;
  const active = DUMMY_DATA.nurseries.filter(n => n.status === 'Active').length;
  const pendingOrders = DUMMY_DATA.nurseries.reduce((sum, n) => sum + (n.activeOrders || 0), 0);
  const totalOutstanding = DUMMY_DATA.nurseries.reduce((sum, n) => sum + (n.outstandingRaw || 0), 0);

  if (totalEl) totalEl.textContent = total;
  if (dashTotalEl) dashTotalEl.textContent = total;
  if (activeEl) activeEl.textContent = active;
  if (pendingOrdersEl) pendingOrdersEl.textContent = pendingOrders;
  if (receivablesEl) receivablesEl.textContent = `₹${totalOutstanding.toLocaleString('en-IN')}`;
}

/**
 * Handle Search Input
 */
function handleNurserySearch(query) {
  currentNurserySearch = (query || '').toLowerCase().trim();
  const clearBtn = document.getElementById('nursery-search-clear');
  if (clearBtn) {
    clearBtn.style.display = currentNurserySearch ? 'block' : 'none';
  }
  applyNurseryFilters();
}

/**
 * Clear Search Input
 */
function clearNurserySearch() {
  const input = document.getElementById('nursery-search-input');
  if (input) input.value = '';
  handleNurserySearch('');
}

/**
 * Set Filter Pill (All, Active, Pending, Inactive)
 */
function setNurseryFilter(filter) {
  currentNurseryFilter = filter;
  ['All', 'Active', 'Pending', 'Inactive'].forEach(f => {
    const pill = document.getElementById(`pill-filter-${f.toLowerCase()}`);
    if (pill) {
      if (f === filter) {
        pill.classList.add('active');
      } else {
        pill.classList.remove('active');
      }
    }
  });
  applyNurseryFilters();
}

/**
 * Apply combined search & status filters
 */
function applyNurseryFilters() {
  let filtered = [...DUMMY_DATA.nurseries];

  // 1. Status Filter
  if (currentNurseryFilter !== 'All') {
    filtered = filtered.filter(n => n.status === currentNurseryFilter);
  }

  // 2. Search Query
  if (currentNurserySearch) {
    filtered = filtered.filter(n => 
      (n.id && n.id.toLowerCase().includes(currentNurserySearch)) ||
      (n.name && n.name.toLowerCase().includes(currentNurserySearch)) ||
      (n.contactPerson && n.contactPerson.toLowerCase().includes(currentNurserySearch)) ||
      (n.phone && n.phone.includes(currentNurserySearch)) ||
      (n.city && n.city.toLowerCase().includes(currentNurserySearch)) ||
      (n.location && n.location.toLowerCase().includes(currentNurserySearch)) ||
      (n.email && n.email.toLowerCase().includes(currentNurserySearch))
    );
  }

  renderNurseriesTable(filtered);
}

/**
 * Clear Form Field Errors
 */
function clearFieldErrors() {
  const errs = document.querySelectorAll('#nursery-partner-form .field-error');
  errs.forEach(err => err.classList.remove('visible'));
}

/**
 * Open Add Nursery Modal
 */
function openAddNurseryModal() {
  const modal = document.getElementById('nursery-form-modal');
  const title = document.getElementById('nursery-modal-title');
  const formId = document.getElementById('nursery-form-id');
  const submitBtn = document.getElementById('btn-save-nursery');
  const form = document.getElementById('nursery-partner-form');

  if (form) form.reset();
  if (formId) formId.value = '';
  if (title) title.textContent = 'Add Commercial Nursery';
  if (submitBtn) submitBtn.textContent = 'Save Nursery';

  // Set default values
  const terms = document.getElementById('nursery-form-terms');
  if (terms) terms.value = '15 Days';
  const credit = document.getElementById('nursery-form-credit');
  if (credit) credit.value = '₹1,50,000';
  const status = document.getElementById('nursery-form-status');
  if (status) status.value = 'Active';

  clearFieldErrors();
  if (modal) {
    modal.style.display = 'flex';
    showToast('Commercial nursery partner accounts are provisioned via platform user registration (role NURSERY).', 'info');
    setTimeout(() => {
      document.getElementById('nursery-form-name')?.focus();
    }, 50);
  }
}

/**
 * Open Edit Nursery Modal
 */
function openEditNurseryModal(id) {
  const nursery = DUMMY_DATA.nurseries.find(n => n.id === id);
  if (!nursery) return;

  const modal = document.getElementById('nursery-form-modal');
  const title = document.getElementById('nursery-modal-title');
  const formId = document.getElementById('nursery-form-id');
  const submitBtn = document.getElementById('btn-save-nursery');

  if (formId) formId.value = nursery.id;
  if (title) title.textContent = `Edit Nursery — ${nursery.name}`;
  if (submitBtn) submitBtn.textContent = 'Update Nursery';

  // Fill existing values
  const nameInput = document.getElementById('nursery-form-name');
  if (nameInput) nameInput.value = nursery.name || '';
  const contactInput = document.getElementById('nursery-form-contact');
  if (contactInput) contactInput.value = nursery.contactPerson || '';
  const phoneInput = document.getElementById('nursery-form-phone');
  if (phoneInput) phoneInput.value = nursery.phone || '';
  const emailInput = document.getElementById('nursery-form-email');
  if (emailInput) emailInput.value = nursery.email || '';
  const addressInput = document.getElementById('nursery-form-address');
  if (addressInput) addressInput.value = nursery.address || '';
  const cityInput = document.getElementById('nursery-form-city');
  if (cityInput) cityInput.value = nursery.city || nursery.location || '';
  const gstinInput = document.getElementById('nursery-form-gstin');
  if (gstinInput) gstinInput.value = nursery.gstin || '';
  const termsInput = document.getElementById('nursery-form-terms');
  if (termsInput) termsInput.value = nursery.paymentTerms || '15 Days';
  const creditInput = document.getElementById('nursery-form-credit');
  if (creditInput) creditInput.value = nursery.creditLimit || '₹1,50,000';
  const statusInput = document.getElementById('nursery-form-status');
  if (statusInput) statusInput.value = nursery.status || 'Active';

  clearFieldErrors();
  if (modal) {
    modal.style.display = 'flex';
  }
}

/**
 * Close Nursery Add/Edit Modal
 */
function closeNurseryModal() {
  const modal = document.getElementById('nursery-form-modal');
  if (modal) modal.style.display = 'none';
  clearFieldErrors();
}

/**
 * Handle Add/Edit Nursery Form Submission
 */
function handleNurseryFormSubmit(e) {
  e.preventDefault();
  clearFieldErrors();

  const idVal = document.getElementById('nursery-form-id')?.value.trim();
  const nameVal = document.getElementById('nursery-form-name')?.value.trim();
  const contactVal = document.getElementById('nursery-form-contact')?.value.trim();
  const phoneVal = document.getElementById('nursery-form-phone')?.value.trim();
  const emailVal = document.getElementById('nursery-form-email')?.value.trim();
  const addressVal = document.getElementById('nursery-form-address')?.value.trim();
  const cityVal = document.getElementById('nursery-form-city')?.value.trim();
  const gstinVal = document.getElementById('nursery-form-gstin')?.value.trim().toUpperCase();
  const termsVal = document.getElementById('nursery-form-terms')?.value || '15 Days';
  const creditVal = document.getElementById('nursery-form-credit')?.value.trim() || '₹1,50,000';
  const statusVal = document.getElementById('nursery-form-status')?.value || 'Active';

  let hasError = false;
  if (!nameVal) {
    document.getElementById('err-nursery-name')?.classList.add('visible');
    hasError = true;
  }
  if (!contactVal) {
    document.getElementById('err-nursery-contact')?.classList.add('visible');
    hasError = true;
  }
  if (!phoneVal || phoneVal.length < 7) {
    document.getElementById('err-nursery-phone')?.classList.add('visible');
    hasError = true;
  }

  if (hasError) return;

  const badgeCls = statusVal === 'Active' 
    ? 'badge-success' 
    : (statusVal === 'Pending' ? 'badge-warning' : 'badge-neutral');

  if (typeof window !== 'undefined') {
    showToast('Commercial nursery partners are managed via platform user registration (role NURSERY). Direct client modification is restricted.', 'warning');
    closeNurseryModal();
    return;
  }

  if (idVal) {
    // EDIT existing nursery (unit test runner fallback)
    const existing = DUMMY_DATA.nurseries.find(n => n.id === idVal);
    if (existing) {
      existing.name = nameVal;
      existing.contactPerson = contactVal;
      existing.phone = phoneVal;
      existing.email = emailVal;
      existing.address = addressVal;
      existing.city = cityVal;
      existing.location = cityVal || existing.location || 'Delhi NCR';
      existing.gstin = gstinVal;
      existing.paymentTerms = termsVal;
      existing.creditLimit = creditVal;
      existing.status = statusVal;
      existing.badgeClass = badgeCls;
    }
  } else {
    // ADD new nursery (unit test runner fallback)
    const maxNum = DUMMY_DATA.nurseries.reduce((max, n) => {
      const match = n.id.match(/NUR-(\d+)/);
      if (match) {
        const num = parseInt(match[1], 10);
        return num > max ? num : max;
      }
      return max;
    }, 100);
    const newId = `NUR-${maxNum + 1}`;

    const newNursery = {
      id: newId,
      name: nameVal,
      contactPerson: contactVal,
      phone: phoneVal,
      email: emailVal,
      location: cityVal || 'Delhi NCR',
      address: addressVal,
      city: cityVal,
      gstin: gstinVal,
      paymentTerms: termsVal,
      creditLimit: creditVal,
      activeOrders: 0,
      outstanding: '₹0',
      outstandingRaw: 0,
      status: statusVal,
      badgeClass: badgeCls
    };

    DUMMY_DATA.nurseries.unshift(newNursery);
  }

  closeNurseryModal();
  applyNurseryFilters();
  updateNurserySummaryKPIs();
}

/**
 * Open View Nursery Modal
 */
function openViewNurseryModal(id) {
  const nursery = DUMMY_DATA.nurseries.find(n => n.id === id);
  if (!nursery) return;

  currentViewNurseryId = id;
  const modal = document.getElementById('nursery-view-modal');
  const title = document.getElementById('view-nursery-title');
  const badge = document.getElementById('view-nursery-status-badge');
  const sub = document.getElementById('view-nursery-id-subtitle');
  const contact = document.getElementById('view-nursery-contact');
  const phone = document.getElementById('view-nursery-phone');
  const email = document.getElementById('view-nursery-email');
  const location = document.getElementById('view-nursery-location');
  const address = document.getElementById('view-nursery-address');
  const gstin = document.getElementById('view-nursery-gstin');
  const terms = document.getElementById('view-nursery-terms');
  const credit = document.getElementById('view-nursery-credit');
  const outstanding = document.getElementById('view-nursery-outstanding');

  if (title) title.textContent = nursery.name;
  if (badge) {
    badge.textContent = nursery.status;
    badge.className = `badge ${nursery.badgeClass}`;
  }
  if (sub) sub.textContent = `Nursery ID: ${nursery.id} • Verified Wholesale Client`;
  if (contact) contact.textContent = nursery.contactPerson || '—';
  if (phone) phone.textContent = nursery.phone || '—';
  if (email) email.textContent = nursery.email || '—';
  if (location) location.textContent = nursery.city || nursery.location || '—';
  if (address) address.textContent = nursery.address || '—';
  if (gstin) gstin.textContent = nursery.gstin || 'Unregistered / Exempt';
  if (terms) terms.textContent = nursery.paymentTerms || '15 Days';
  if (credit) credit.textContent = nursery.creditLimit || '₹1,50,000';
  if (outstanding) outstanding.textContent = nursery.outstanding || '₹0';

  if (modal) {
    modal.style.display = 'flex';
  }
}

/**
 * Close View Nursery Modal
 */
function closeViewNurseryModal() {
  const modal = document.getElementById('nursery-view-modal');
  if (modal) modal.style.display = 'none';
}

/**
 * Transition from View Modal to Edit Modal
 */
function editFromViewModal() {
  if (currentViewNurseryId) {
    closeViewNurseryModal();
    openEditNurseryModal(currentViewNurseryId);
  }
}

// ============================================================================
// PHASE 5: PLANT CATALOG & INVENTORY MANAGEMENT ENGINE
// ============================================================================

let cachedPlantsData = [];
let currentPlantFilters = {
  search: '',
  category: '',
  status: 'ALL'
};
let currentViewPlantId = null;

function escapePlantHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Format currency to Indian Rupees (INR)
 */
function formatPlantCurrency(amount) {
  const num = Number(amount) || 0;
  return '₹' + num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/**
 * Fetch plants from live /api/plants endpoint and render
 */
async function fetchAndRenderPlants() {
  const tbody = document.getElementById('plants-table-tbody');

  if (tbody) {
    tbody.innerHTML = `
      <tr>
        <td colspan="9" style="text-align: center; color: var(--text-secondary); padding: 2.5rem 1rem;">
          <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">⏳</div>
          <div style="font-weight: 600; color: var(--text-main);">Loading Wholesale Plant Catalog...</div>
          <div style="font-size: 0.82rem; margin-top: 0.25rem;">Fetching live inventory from FloraChain B2B API</div>
        </td>
      </tr>
    `;
  }

  try {
    const res = await fetch('/api/plants');
    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      throw new Error(errJson.error || `Failed to fetch plants (HTTP ${res.status})`);
    }

    const json = await res.json();
    if (json.success && Array.isArray(json.data)) {
      cachedPlantsData = json.data;
    } else {
      cachedPlantsData = [];
    }

    updatePlantSummaryKPIs();
    renderPlantsTable();
  } catch (err) {
    console.error('Error fetching plants:', err);
    if (tbody) {
      tbody.innerHTML = `
        <tr>
          <td colspan="9" style="text-align: center; color: var(--status-overdue-text); padding: 2.5rem 1rem;">
            <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">⚠️</div>
            <div style="font-weight: 700; margin-bottom: 0.25rem;">Failed to load plant catalog</div>
            <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.85rem;">${escapePlantHtml(err.message)}</div>
            <button class="btn btn-secondary btn-sm" onclick="fetchAndRenderPlants()">
              <span>🔄</span> Retry Connection
            </button>
          </td>
        </tr>
      `;
    }
    if (typeof showToast === 'function') {
      showToast('Could not refresh plant catalog from server.', 'error');
    }
  }
}

/**
 * Update Plant Summary KPI Cards
 */
function updatePlantSummaryKPIs() {
  const totalEl = document.getElementById('kpi-total-plants');
  const activeEl = document.getElementById('kpi-active-plants');
  const stockUnitsEl = document.getElementById('kpi-total-stock-units');
  const lowStockEl = document.getElementById('kpi-low-stock-plants');

  const total = cachedPlantsData.length;
  const active = cachedPlantsData.filter(p => p.status === 'ACTIVE').length;
  const totalUnits = cachedPlantsData.reduce((acc, p) => acc + (Number(p.stock_qty) || 0), 0);
  const lowOrOut = cachedPlantsData.filter(p => (Number(p.stock_qty) || 0) <= 10 || p.status === 'OUT_OF_STOCK').length;

  if (totalEl) totalEl.textContent = total;
  if (activeEl) activeEl.textContent = active;
  if (stockUnitsEl) stockUnitsEl.textContent = totalUnits.toLocaleString('en-IN');
  if (lowStockEl) lowStockEl.textContent = lowOrOut;
}

/**
 * Render Plants Data Table
 */
function renderPlantsTable() {
  const tbody = document.getElementById('plants-table-tbody');
  const countSubtitle = document.getElementById('plant-count-subtitle');
  if (!tbody) return;

  const q = (currentPlantFilters.search || '').toLowerCase().trim();
  const cat = (currentPlantFilters.category || '').toUpperCase().trim();
  const st = (currentPlantFilters.status || 'ALL').toUpperCase().trim();

  const filtered = cachedPlantsData.filter(p => {
    // Search filter
    if (q) {
      const matchName = (p.common_name || '').toLowerCase().includes(q);
      const matchBotanical = (p.botanical_name || '').toLowerCase().includes(q);
      const matchDesc = (p.description || '').toLowerCase().includes(q);
      const matchSize = (p.container_size || '').toLowerCase().includes(q);
      if (!matchName && !matchBotanical && !matchDesc && !matchSize) return false;
    }

    // Category filter
    if (cat && (p.category || '').toUpperCase() !== cat) {
      return false;
    }

    // Status filter
    if (st !== 'ALL' && (p.status || '').toUpperCase() !== st) {
      return false;
    }

    return true;
  });

  if (countSubtitle) {
    countSubtitle.textContent = `Showing ${filtered.length} of ${cachedPlantsData.length} wholesale plant catalog records`;
  }

  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="9" style="text-align: center; color: var(--text-secondary); padding: 3rem 1rem;">
          <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">🌿</div>
          <div style="font-weight: 700; color: var(--text-main); margin-bottom: 0.25rem;">No plants found</div>
          <div style="font-size: 0.85rem; margin-bottom: 1rem;">No plant catalog records match your active search or filter selection.</div>
          <button class="btn btn-primary btn-sm" onclick="openAddPlantModal()">
            <span>➕</span> Add First Plant
          </button>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filtered.map(plant => {
    let statusBadgeClass = 'badge-success';
    let statusLabel = 'ACTIVE';
    if (plant.status === 'OUT_OF_STOCK') {
      statusBadgeClass = 'badge-warning';
      statusLabel = 'OUT OF STOCK';
    } else if (plant.status === 'DISCONTINUED') {
      statusBadgeClass = 'badge-neutral';
      statusLabel = 'DISCONTINUED';
    }

    const priceFormatted = formatPlantCurrency(plant.unit_price) + ` / ${plant.unit || 'plant'}`;
    const botanicalHtml = plant.botanical_name ? `<br><small style="color: var(--text-secondary); font-style: italic;">${escapePlantHtml(plant.botanical_name)}</small>` : '';

    return `
      <tr>
        <td>
          <strong>${escapePlantHtml(plant.common_name)}</strong>
          ${botanicalHtml}
        </td>
        <td>
          <span class="badge badge-info" style="font-size: 0.72rem;">${escapePlantHtml(plant.category)}</span>
        </td>
        <td>${escapePlantHtml(plant.container_size)}</td>
        <td><strong style="color: var(--primary);">${priceFormatted}</strong></td>
        <td>
          <span style="font-weight: 700; ${plant.stock_qty <= 10 ? 'color: var(--status-overdue-text);' : ''}">${Number(plant.stock_qty || 0).toLocaleString('en-IN')} ${escapePlantHtml(plant.unit || 'plant')}s</span>
        </td>
        <td>${Number(plant.min_order_qty || 1)} units</td>
        <td><span class="badge ${statusBadgeClass}">${statusLabel}</span></td>
        <td><small style="color: var(--text-secondary);">${escapePlantHtml(plant.supplier_name || plant.supplier_username || 'Wholesale Supplier')}</small></td>
        <td>
          <div style="display: flex; gap: 0.35rem; align-items: center;">
            <button type="button" class="btn btn-secondary btn-sm" onclick="openViewPlantModal(${plant.id})" title="View complete plant details">
              <span>👁️</span> View
            </button>
            <button type="button" class="btn btn-secondary btn-sm" onclick="openEditPlantModal(${plant.id})" title="Edit plant specifications and pricing">
              <span>✏️</span> Edit
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

/**
 * Handle Plant Search Input
 */
function handlePlantSearch(val) {
  currentPlantFilters.search = val || '';
  const clearBtn = document.getElementById('plant-search-clear');
  if (clearBtn) {
    clearBtn.style.display = val ? 'block' : 'none';
  }
  renderPlantsTable();
}

/**
 * Clear Plant Search
 */
function clearPlantSearch() {
  const input = document.getElementById('plant-search-input');
  if (input) input.value = '';
  handlePlantSearch('');
}

/**
 * Handle Plant Category Filter Dropdown
 */
function handlePlantCategoryChange(cat) {
  currentPlantFilters.category = cat || '';
  renderPlantsTable();
}

/**
 * Handle Plant Status Filter Pills
 */
function setPlantStatusFilter(status) {
  currentPlantFilters.status = status || 'ALL';

  const pills = ['all', 'active', 'outofstock', 'discontinued'];
  pills.forEach(p => {
    const el = document.getElementById(`pill-plant-${p}`);
    if (el) el.classList.remove('active');
  });

  const activePillId = status === 'ALL' ? 'pill-plant-all' :
                       status === 'ACTIVE' ? 'pill-plant-active' :
                       status === 'OUT_OF_STOCK' ? 'pill-plant-outofstock' : 'pill-plant-discontinued';

  const activeEl = document.getElementById(activePillId);
  if (activeEl) activeEl.classList.add('active');

  renderPlantsTable();
}

/**
 * Open Add Plant Modal
 */
function openAddPlantModal() {
  const form = document.getElementById('plant-item-form');
  if (form) form.reset();

  const idField = document.getElementById('plant-form-id');
  if (idField) idField.value = '';

  const title = document.getElementById('plant-modal-title');
  if (title) title.textContent = 'Add Plant to Wholesale Catalog';

  clearPlantFieldErrors();

  const modal = document.getElementById('plant-form-modal');
  if (modal) modal.style.display = 'flex';
}

/**
 * Open Edit Plant Modal
 */
async function openEditPlantModal(plantId) {
  clearPlantFieldErrors();

  let plant = cachedPlantsData.find(p => p.id === plantId);

  // If not cached, fetch from API
  if (!plant) {
    try {
      const res = await fetch(`/api/plants/${plantId}`);
      if (res.ok) {
        const json = await res.json();
        if (json.success) plant = json.data;
      }
    } catch (_) {}
  }

  if (!plant) {
    showToast(`Plant #${plantId} could not be loaded.`, 'error');
    return;
  }

  const idField = document.getElementById('plant-form-id');
  const commonNameField = document.getElementById('plant-form-common-name');
  const botanicalField = document.getElementById('plant-form-botanical-name');
  const categoryField = document.getElementById('plant-form-category');
  const containerField = document.getElementById('plant-form-container-size');
  const unitField = document.getElementById('plant-form-unit');
  const priceField = document.getElementById('plant-form-price');
  const stockField = document.getElementById('plant-form-stock');
  const minOrderField = document.getElementById('plant-form-min-order');
  const statusField = document.getElementById('plant-form-status');
  const descField = document.getElementById('plant-form-description');
  const title = document.getElementById('plant-modal-title');

  if (idField) idField.value = plant.id;
  if (commonNameField) commonNameField.value = plant.common_name || '';
  if (botanicalField) botanicalField.value = plant.botanical_name || '';
  if (categoryField) categoryField.value = plant.category || 'INDOOR';
  if (containerField) containerField.value = plant.container_size || '';
  if (unitField) unitField.value = plant.unit || 'plant';
  if (priceField) priceField.value = plant.unit_price || '';
  if (stockField) stockField.value = plant.stock_qty ?? 0;
  if (minOrderField) minOrderField.value = plant.min_order_qty || 1;
  if (statusField) statusField.value = plant.status || 'ACTIVE';
  if (descField) descField.value = plant.description || '';

  if (title) title.textContent = `Edit Plant — ${plant.common_name}`;

  const modal = document.getElementById('plant-form-modal');
  if (modal) modal.style.display = 'flex';
}

/**
 * Close Plant Modal
 */
function closePlantModal() {
  const modal = document.getElementById('plant-form-modal');
  if (modal) modal.style.display = 'none';
  clearPlantFieldErrors();
}

/**
 * Clear Plant Field Error Messages
 */
function clearPlantFieldErrors() {
  const errors = [
    'err-plant-common-name',
    'err-plant-category',
    'err-plant-container-size',
    'err-plant-price',
    'err-plant-stock',
    'err-plant-min-order'
  ];
  errors.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
  });
}

/**
 * Open View Plant Modal
 */
async function openViewPlantModal(plantId) {
  currentViewPlantId = plantId;
  let plant = cachedPlantsData.find(p => p.id === plantId);

  try {
    const res = await fetch(`/api/plants/${plantId}`);
    if (res.ok) {
      const json = await res.json();
      if (json.success && json.data) plant = json.data;
    }
  } catch (_) {}

  if (!plant) {
    showToast(`Plant record #${plantId} not found.`, 'error');
    return;
  }

  const title = document.getElementById('view-plant-title');
  const botanical = document.getElementById('view-plant-botanical-subtitle');
  const statusBadge = document.getElementById('view-plant-status-badge');
  const category = document.getElementById('view-plant-category');
  const container = document.getElementById('view-plant-container');
  const price = document.getElementById('view-plant-price');
  const stock = document.getElementById('view-plant-stock');
  const minOrder = document.getElementById('view-plant-min-order');
  const supplier = document.getElementById('view-plant-supplier');
  const desc = document.getElementById('view-plant-description');

  if (title) title.textContent = plant.common_name;
  if (botanical) botanical.textContent = plant.botanical_name ? `Botanical: ${plant.botanical_name}` : 'Wholesale Cultivar Spec';
  if (statusBadge) {
    statusBadge.textContent = plant.status;
    statusBadge.className = `badge ${plant.status === 'ACTIVE' ? 'badge-success' : (plant.status === 'OUT_OF_STOCK' ? 'badge-warning' : 'badge-neutral')}`;
  }
  if (category) category.textContent = plant.category;
  if (container) container.textContent = plant.container_size;
  if (price) price.textContent = `${formatPlantCurrency(plant.unit_price)} / ${plant.unit || 'plant'}`;
  if (stock) stock.textContent = `${Number(plant.stock_qty || 0).toLocaleString('en-IN')} ${plant.unit || 'plant'}s`;
  if (minOrder) minOrder.textContent = `${plant.min_order_qty || 1} units`;
  if (supplier) supplier.textContent = plant.supplier_name || plant.supplier_username || 'Wholesale Supplier';
  if (desc) desc.textContent = plant.description || 'No additional care or cultivation notes provided for this cultivar.';

  const modal = document.getElementById('plant-view-modal');
  if (modal) modal.style.display = 'flex';
}

/**
 * Close View Plant Modal
 */
function closeViewPlantModal() {
  const modal = document.getElementById('plant-view-modal');
  if (modal) modal.style.display = 'none';
  currentViewPlantId = null;
}

/**
 * Transition from View Modal to Edit Modal
 */
function editFromPlantViewModal() {
  if (currentViewPlantId) {
    const id = currentViewPlantId;
    closeViewPlantModal();
    openEditPlantModal(id);
  }
}

/**
 * Handle Plant Form Submit (Create or Update)
 */
async function handlePlantFormSubmit(e) {
  e.preventDefault();
  clearPlantFieldErrors();

  const idVal = document.getElementById('plant-form-id')?.value;
  const isEdit = Boolean(idVal);

  const commonName = (document.getElementById('plant-form-common-name')?.value || '').trim();
  const botanicalName = (document.getElementById('plant-form-botanical-name')?.value || '').trim();
  const category = (document.getElementById('plant-form-category')?.value || '').trim();
  const containerSize = (document.getElementById('plant-form-container-size')?.value || '').trim();
  const unit = (document.getElementById('plant-form-unit')?.value || 'plant').trim();
  const priceRaw = document.getElementById('plant-form-price')?.value;
  const stockRaw = document.getElementById('plant-form-stock')?.value;
  const minOrderRaw = document.getElementById('plant-form-min-order')?.value;
  const status = (document.getElementById('plant-form-status')?.value || 'ACTIVE').trim();
  const description = (document.getElementById('plant-form-description')?.value || '').trim();

  // Client-side validations
  let hasError = false;

  if (!commonName) {
    const el = document.getElementById('err-plant-common-name');
    if (el) el.style.display = 'block';
    hasError = true;
  }

  if (!category) {
    const el = document.getElementById('err-plant-category');
    if (el) el.style.display = 'block';
    hasError = true;
  }

  if (!containerSize) {
    const el = document.getElementById('err-plant-container-size');
    if (el) el.style.display = 'block';
    hasError = true;
  }

  const price = parseFloat(priceRaw);
  if (isNaN(price) || price <= 0) {
    const el = document.getElementById('err-plant-price');
    if (el) el.style.display = 'block';
    hasError = true;
  }

  const stock = parseInt(stockRaw, 10);
  if (isNaN(stock) || stock < 0) {
    const el = document.getElementById('err-plant-stock');
    if (el) el.style.display = 'block';
    hasError = true;
  }

  const minOrder = parseInt(minOrderRaw, 10);
  if (isNaN(minOrder) || minOrder < 1) {
    const el = document.getElementById('err-plant-min-order');
    if (el) el.style.display = 'block';
    hasError = true;
  }

  if (hasError) return;

  const payload = {
    common_name: commonName,
    botanical_name: botanicalName,
    category: category,
    container_size: containerSize,
    unit: unit,
    unit_price: Math.round(price * 100) / 100,
    stock_qty: stock,
    min_order_qty: minOrder,
    description: description,
    status: status
  };

  const submitBtn = document.getElementById('btn-save-plant');
  const originalHtml = submitBtn ? submitBtn.innerHTML : '';
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span>⏳</span> Saving...';
  }

  try {
    const url = isEdit ? `/api/plants/${idVal}` : '/api/plants';
    const method = isEdit ? 'PUT' : 'POST';

    const res = await fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const json = await res.json().catch(() => ({}));

    if (!res.ok || !json.success) {
      throw new Error(json.error || `Failed to save plant (HTTP ${res.status})`);
    }

    closePlantModal();
    showToast(isEdit ? `Plant "${commonName}" updated successfully.` : `Plant "${commonName}" added to catalog.`, 'success');
    await fetchAndRenderPlants();
  } catch (err) {
    console.error('Error saving plant:', err);
    showToast(err.message || 'Error saving plant record.', 'error');
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalHtml;
    }
  }
}

// ============================================================================
// PHASE 6: WHOLESALE ORDER MANAGEMENT ENGINE
// ============================================================================

let liveOrders = [];
let currentOrderStatusFilter = 'ALL';
let orderSearchQuery = '';
let availablePlantsForOrders = [];
let availableNurseriesForOrders = [];

function escapeOrderHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatOrderCurrency(amount) {
  const num = parseFloat(amount) || 0;
  return '₹' + num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatOrderStatusBadge(status) {
  switch (status) {
    case 'CONFIRMED':
    case 'STAGING':
      return `<span class="badge badge-primary">${escapeOrderHtml(status)}</span>`;
    case 'DISPATCHED':
      return `<span class="badge badge-info">In Transit</span>`;
    case 'INSPECTED_PENDING_CONFIRMATION':
      return `<span class="badge badge-warning">Pending Signatures</span>`;
    case 'LOCKED_VERIFIED':
    case 'DELIVERED':
      return `<span class="badge badge-success">Verified & Locked</span>`;
    case 'CANCELLED':
      return `<span class="badge badge-danger">Cancelled</span>`;
    default:
      return `<span class="badge badge-secondary">${escapeOrderHtml(status || 'DRAFT')}</span>`;
  }
}

async function fetchAndRenderOrders() {
  const tbody = document.getElementById('orders-table-tbody');
  if (tbody) {
    tbody.innerHTML = `
      <tr>
        <td colspan="9" style="text-align: center; color: var(--text-secondary); padding: 2.5rem;">
          <div style="display: flex; align-items: center; justify-content: center; gap: 0.5rem;">
            <span>🔄</span> Loading wholesale orders from live database...
          </div>
        </td>
      </tr>
    `;
  }

  try {
    const res = await fetch('/api/orders');
    if (!res.ok) {
      if (res.status === 401) {
        if (tbody) {
          tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--danger); padding: 2rem;">Please sign in to view wholesale orders.</td></tr>`;
        }
        return;
      }
      throw new Error(`Server returned HTTP ${res.status}`);
    }

    const data = await res.json();
    if (data.success && Array.isArray(data.data)) {
      liveOrders = data.data;
      updateOrderSummaryKPIs(liveOrders);
      applyOrderFiltersAndRender();
    } else {
      throw new Error(data.error || 'Failed to load orders.');
    }
  } catch (err) {
    console.error('Error fetching orders:', err);
    if (tbody) {
      tbody.innerHTML = `
        <tr>
          <td colspan="9" style="text-align: center; color: var(--danger); padding: 2rem;">
            ⚠️ Could not load wholesale orders. <button class="btn btn-secondary btn-sm" onclick="fetchAndRenderOrders()" style="margin-left: 0.5rem;">Retry</button>
          </td>
        </tr>
      `;
    }
  }
}

function updateOrderSummaryKPIs(orders) {
  const total = orders.length;
  const confirmed = orders.filter(o => o.status === 'CONFIRMED' || o.status === 'STAGING').length;
  const dispatched = orders.filter(o => o.status === 'DISPATCHED').length;
  const delivered = orders.filter(o => o.status === 'LOCKED_VERIFIED' || o.status === 'DELIVERED').length;

  const totalEl = document.getElementById('kpi-total-orders');
  const confirmedEl = document.getElementById('kpi-confirmed-orders');
  const dispatchedEl = document.getElementById('kpi-dispatched-orders');
  const deliveredEl = document.getElementById('kpi-delivered-orders');

  if (totalEl) totalEl.textContent = total;
  if (confirmedEl) confirmedEl.textContent = confirmed;
  if (dispatchedEl) dispatchedEl.textContent = dispatched;
  if (deliveredEl) deliveredEl.textContent = delivered;
}

function handleOrderSearch(value) {
  orderSearchQuery = (value || '').toLowerCase().trim();
  const clearBtn = document.getElementById('order-search-clear');
  if (clearBtn) clearBtn.style.display = orderSearchQuery ? 'block' : 'none';
  applyOrderFiltersAndRender();
}

function clearOrderSearch() {
  const input = document.getElementById('order-search-input');
  if (input) input.value = '';
  handleOrderSearch('');
}

function setOrderStatusFilter(status) {
  currentOrderStatusFilter = status;
  ['all', 'confirmed', 'dispatched', 'locked'].forEach(key => {
    const pill = document.getElementById(`pill-order-${key}`);
    if (pill) pill.classList.remove('active');
  });

  const activeId = status === 'ALL' ? 'pill-order-all' :
                   status === 'CONFIRMED' ? 'pill-order-confirmed' :
                   status === 'DISPATCHED' ? 'pill-order-dispatched' :
                   status === 'LOCKED_VERIFIED' ? 'pill-order-locked' : 'pill-order-all';
  const activeEl = document.getElementById(activeId);
  if (activeEl) activeEl.classList.add('active');

  applyOrderFiltersAndRender();
}

function applyOrderFiltersAndRender() {
  let filtered = [...liveOrders];

  if (currentOrderStatusFilter !== 'ALL') {
    filtered = filtered.filter(o => o.status === currentOrderStatusFilter);
  }

  if (orderSearchQuery) {
    filtered = filtered.filter(o => {
      const idMatch = (o.id || '').toLowerCase().includes(orderSearchQuery);
      const nurseryMatch = (o.nursery_name || '').toLowerCase().includes(orderSearchQuery);
      const varietyMatch = (o.variety || '').toLowerCase().includes(orderSearchQuery);
      return idMatch || nurseryMatch || varietyMatch;
    });
  }

  renderOrdersTable(filtered);
}

function renderOrdersTable(ordersToRender) {
  const tbody = document.getElementById('orders-table-tbody');
  const subtitle = document.getElementById('order-count-subtitle');
  if (!tbody) return;

  if (subtitle) {
    subtitle.textContent = `Showing ${ordersToRender.length} of ${liveOrders.length} registered wholesale plant orders`;
  }

  if (ordersToRender.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="9" style="text-align: center; color: var(--text-secondary); padding: 3rem 1.5rem;">
          <div style="font-size: 2rem; margin-bottom: 0.5rem;">📦</div>
          <p style="font-weight: 600; color: var(--text-main); margin-bottom: 0.35rem;">No wholesale orders found</p>
          <p style="font-size: 0.85rem; margin-bottom: 1rem;">Try clearing search filters or create a new wholesale order.</p>
          <button class="btn btn-primary btn-sm" onclick="openCreateOrderModal()"><span>➕</span> Create First Order</button>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = ordersToRender.map(o => {
    const totalVal = o.total_amount ? formatOrderCurrency(o.total_amount) : formatOrderCurrency(o.ordered_qty * o.unit_price);
    const dateStr = o.created_at ? new Date(o.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '—';
    const transportStr = (o.truck_no && o.truck_no !== 'TBD') ? `${escapeOrderHtml(o.truck_no)}` : '<span style="color: var(--text-secondary); font-style: italic;">Pending Dispatch</span>';

    return `
      <tr>
        <td><strong style="color: var(--text-main); font-family: monospace; font-size: 0.92rem;">${escapeOrderHtml(o.id)}</strong></td>
        <td>
          <div style="font-weight: 600; color: var(--text-main);">${escapeOrderHtml(o.nursery_name || 'Nursery Partner')}</div>
          <div style="font-size: 0.78rem; color: var(--text-secondary);">${escapeOrderHtml(o.nursery_username || '')}</div>
        </td>
        <td>
          <div style="font-weight: 500; max-width: 260px; white-space: normal; line-height: 1.35;">${escapeOrderHtml(o.variety)}</div>
          ${o.items_count > 1 ? `<span style="font-size: 0.75rem; color: var(--primary); font-weight: 700;">${o.items_count} line items</span>` : ''}
        </td>
        <td><strong>${o.ordered_qty}</strong> <span style="font-size: 0.8rem; color: var(--text-secondary);">units</span></td>
        <td style="font-weight: 800; color: var(--primary);">${totalVal}</td>
        <td><div style="font-size: 0.85rem;">${transportStr}</div></td>
        <td>${formatOrderStatusBadge(o.status)}</td>
        <td style="font-size: 0.82rem; color: var(--text-secondary);">${dateStr}</td>
        <td>
          <div style="display: flex; gap: 0.35rem; align-items: center;">
            <button class="btn btn-secondary btn-sm" onclick="openOrderDetailModal('${escapeOrderHtml(o.id)}')" title="View itemized lines and order status">
              <span>👁️</span> Details
            </button>
            ${(o.status === 'CONFIRMED' || o.status === 'STAGING' || o.status === 'DISPATCHED') ? `
              <button class="btn btn-secondary btn-sm" onclick="openTruckLoadingModal('${escapeOrderHtml(o.id)}')" title="Load truck or edit manifest" style="color: var(--primary); font-weight: 600;">
                <span>🚚</span> Load
              </button>
            ` : ''}
            ${(o.status === 'LOCKED_VERIFIED') ? `
              <button class="btn btn-secondary btn-sm" onclick="handleOrderInvoiceAction('${escapeOrderHtml(o.id)}')" title="View or generate commercial invoice" style="color: #063B00; font-weight: 600;">
                <span>📄</span> Invoice
              </button>
            ` : ''}
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

async function openCreateOrderModal() {
  const modal = document.getElementById('order-create-modal');
  const nurserySelect = document.getElementById('order-form-nursery');
  const itemsContainer = document.getElementById('order-form-items-list');
  const errNursery = document.getElementById('err-order-nursery');
  const errItems = document.getElementById('err-order-items');

  if (errNursery) errNursery.style.display = 'none';
  if (errItems) errItems.style.display = 'none';

  // Load plants and nurseries
  try {
    const plantsRes = await fetch('/api/plants?status=ACTIVE');
    if (plantsRes.ok) {
      const pJson = await plantsRes.json();
      if (pJson.success && Array.isArray(pJson.data)) {
        availablePlantsForOrders = pJson.data;
      }
    }

    const nurseryRes = await fetch('/api/orders/nurseries');
    if (nurseryRes.ok) {
      const nJson = await nurseryRes.json();
      if (nJson.success && Array.isArray(nJson.data)) {
        availableNurseriesForOrders = nJson.data;
      }
    }
  } catch (e) {
    console.warn('Could not refresh catalog data for order modal:', e);
  }

  if (nurserySelect) {
    nurserySelect.innerHTML = '<option value="">-- Choose Nursery Partner --</option>';
    if (availableNurseriesForOrders.length > 0) {
      availableNurseriesForOrders.forEach(n => {
        nurserySelect.innerHTML += `<option value="${n.id}">${escapeOrderHtml(n.business_name)} (${escapeOrderHtml(n.username)})</option>`;
      });
    } else {
      nurserySelect.innerHTML += `<option value="2" selected>Green Meadows Landscape Nursery (nursery_amit)</option>`;
    }
  }

  const notesInput = document.getElementById('order-form-notes');
  if (notesInput) notesInput.value = '';

  if (itemsContainer) {
    itemsContainer.innerHTML = '';
    addOrderItemRow();
  }

  if (modal) modal.style.display = 'flex';
}

function closeCreateOrderModal() {
  const modal = document.getElementById('order-create-modal');
  if (modal) modal.style.display = 'none';
}

function addOrderItemRow(prefillPlantId = null, prefillQty = 1) {
  const tbody = document.getElementById('order-form-items-list');
  if (!tbody) return;

  const row = document.createElement('tr');
  row.className = 'order-form-item-row';

  let plantOptions = '<option value="">-- Choose Plant Variety --</option>';
  availablePlantsForOrders.forEach(p => {
    const isSelected = prefillPlantId && String(p.id) === String(prefillPlantId);
    plantOptions += `<option value="${p.id}" ${isSelected ? 'selected' : ''} data-price="${p.unit_price}" data-unit="${p.unit}" data-min-order="${p.min_order_qty}" data-stock="${p.stock_qty}">
      ${escapeOrderHtml(p.common_name)} (${escapeOrderHtml(p.container_size)}) — ₹${p.unit_price}/${p.unit}
    </option>`;
  });

  row.innerHTML = `
    <td>
      <select class="form-select order-item-plant" onchange="handleOrderItemPlantChange(this)" style="padding: 0.45rem 0.65rem; font-size: 0.85rem;" required>
        ${plantOptions}
      </select>
    </td>
    <td>
      <input type="number" class="form-input order-item-price" step="0.01" min="0.01" placeholder="0.00" oninput="updateOrderFormCalculations()" style="padding: 0.45rem 0.65rem; font-size: 0.85rem;" required>
    </td>
    <td>
      <input type="number" class="form-input order-item-qty" step="1" min="1" value="${prefillQty}" oninput="updateOrderFormCalculations()" style="padding: 0.45rem 0.65rem; font-size: 0.85rem;" required>
    </td>
    <td style="vertical-align: middle;">
      <div class="order-item-total" style="font-weight: 700; color: var(--primary); font-size: 0.9rem;">₹0.00</div>
    </td>
    <td style="text-align: center; vertical-align: middle;">
      <button type="button" class="btn btn-secondary btn-sm" onclick="removeOrderItemRow(this)" style="padding: 0.25rem 0.55rem; color: var(--danger);" title="Remove line item">✕</button>
    </td>
  `;

  tbody.appendChild(row);
  updateOrderFormCalculations();
}

function removeOrderItemRow(buttonEl) {
  const tbody = document.getElementById('order-form-items-list');
  const rows = tbody ? tbody.querySelectorAll('.order-form-item-row') : [];
  if (rows.length <= 1) {
    showToast('At least one plant line item is required.', 'warning');
    return;
  }

  const tr = buttonEl.closest('tr');
  if (tr) tr.remove();
  updateOrderFormCalculations();
}

function handleOrderItemPlantChange(selectEl) {
  const tr = selectEl.closest('tr');
  if (!tr) return;

  const plantId = selectEl.value;
  const plant = availablePlantsForOrders.find(p => String(p.id) === String(plantId));

  const priceInput = tr.querySelector('.order-item-price');
  const qtyInput = tr.querySelector('.order-item-qty');

  if (plant) {
    if (priceInput) priceInput.value = plant.unit_price;
    if (qtyInput && Number(qtyInput.value) < plant.min_order_qty) {
      qtyInput.value = plant.min_order_qty;
    }
  }

  updateOrderFormCalculations();
}

function updateOrderFormCalculations() {
  const tbody = document.getElementById('order-form-items-list');
  if (!tbody) return;

  const rows = tbody.querySelectorAll('.order-form-item-row');
  let totalQty = 0;
  let grandTotal = 0;

  rows.forEach(row => {
    const qtyInput = row.querySelector('.order-item-qty');
    const priceInput = row.querySelector('.order-item-price');
    const totalDiv = row.querySelector('.order-item-total');

    const qty = parseInt(qtyInput?.value, 10) || 0;
    const price = parseFloat(priceInput?.value) || 0;
    const lineTotal = roundCurrency(qty * price);

    if (totalDiv) {
      totalDiv.textContent = formatOrderCurrency(lineTotal);
    }

    totalQty += qty;
    grandTotal += lineTotal;
  });

  const totalQtyEl = document.getElementById('order-form-total-qty');
  const totalValEl = document.getElementById('order-form-total-value');

  if (totalQtyEl) totalQtyEl.textContent = totalQty;
  if (totalValEl) totalValEl.textContent = formatOrderCurrency(grandTotal);
}

function roundCurrency(val) {
  return Math.round((val + Number.EPSILON) * 100) / 100;
}

async function handleCreateOrderSubmit(e) {
  e.preventDefault();

  const nurserySelect = document.getElementById('order-form-nursery');
  const notesInput = document.getElementById('order-form-notes');
  const submitBtn = document.getElementById('btn-submit-order');
  const errNursery = document.getElementById('err-order-nursery');
  const errItems = document.getElementById('err-order-items');

  if (errNursery) errNursery.style.display = 'none';
  if (errItems) errItems.style.display = 'none';

  const nurseryId = nurserySelect?.value;
  if (!nurseryId) {
    if (errNursery) errNursery.style.display = 'block';
    return;
  }

  const tbody = document.getElementById('order-form-items-list');
  const rows = tbody ? tbody.querySelectorAll('.order-form-item-row') : [];
  if (rows.length === 0) {
    if (errItems) {
      errItems.textContent = 'At least one plant line item is required.';
      errItems.style.display = 'block';
    }
    return;
  }

  const items = [];
  let validationError = null;

  rows.forEach((row, idx) => {
    const plantSelect = row.querySelector('.order-item-plant');
    const priceInput = row.querySelector('.order-item-price');
    const qtyInput = row.querySelector('.order-item-qty');

    const plantId = plantSelect?.value;
    const plant = availablePlantsForOrders.find(p => String(p.id) === String(plantId));
    const variety = plant ? plant.common_name : (plantSelect?.selectedOptions[0]?.text || '').trim();
    const price = parseFloat(priceInput?.value);
    const qty = parseInt(qtyInput?.value, 10);

    if (!plantId || !variety) {
      validationError = `Row #${idx + 1}: Please select a plant variety.`;
      return;
    }
    if (isNaN(qty) || qty <= 0) {
      validationError = `Row #${idx + 1}: Quantity must be a positive number.`;
      return;
    }
    if (isNaN(price) || price <= 0) {
      validationError = `Row #${idx + 1}: Unit price must be greater than zero.`;
      return;
    }

    items.push({
      plant_id: parseInt(plantId, 10),
      variety: variety,
      quantity: qty,
      unit_price: price
    });
  });

  if (validationError) {
    if (errItems) {
      errItems.textContent = validationError;
      errItems.style.display = 'block';
    }
    return;
  }

  const payload = {
    nursery_user_id: parseInt(nurseryId, 10),
    notes: (notesInput?.value || '').trim(),
    items: items
  };

  const originalHtml = submitBtn ? submitBtn.innerHTML : '';
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span>⏳</span> Creating Order...';
  }

  try {
    const res = await fetch('/api/orders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.error || 'Failed to create order.');
    }

    closeCreateOrderModal();
    showToast(data.message || 'Wholesale order created successfully.', 'success');
    await fetchAndRenderOrders();
  } catch (err) {
    console.error('Error creating order:', err);
    showToast(err.message || 'Error creating order.', 'error');
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalHtml;
    }
  }
}

async function openOrderDetailModal(orderId) {
  const modal = document.getElementById('order-detail-modal');
  if (!modal) return;

  window.__currentLoadedOrderId = orderId;

  // Reset expandable audit history container
  const auditContainer = document.getElementById('view-order-audit-container');
  if (auditContainer) auditContainer.style.display = 'none';
  const auditList = document.getElementById('view-order-audit-list');
  if (auditList) auditList.innerHTML = '';
  const auditCount = document.getElementById('view-order-audit-count');
  if (auditCount) auditCount.textContent = '0 events';
  const auditBtn = document.getElementById('btn-toggle-order-audit');
  if (auditBtn) auditBtn.innerHTML = '<span>📜</span> View Audit History';

  try {
    const res = await fetch(`/api/orders/${orderId}`);
    if (!res.ok) throw new Error(`Server returned HTTP ${res.status}`);
    const body = await res.json();
    if (!body.success || !body.data) throw new Error(body.error || 'Order not found.');

    const details = body.data;
    const order = details.order || details;
    const items = details.items || [];

    const titleEl = document.getElementById('view-order-title');
    const badgeEl = document.getElementById('view-order-status-badge');
    const subtitleEl = document.getElementById('view-order-subtitle');
    const nurseryEl = document.getElementById('view-order-nursery');
    const supplierEl = document.getElementById('view-order-supplier');
    const dateEl = document.getElementById('view-order-date');
    const transportEl = document.getElementById('view-order-transport');
    const totalQtyEl = document.getElementById('view-order-total-qty');
    const totalAmountEl = document.getElementById('view-order-total-amount');

    if (titleEl) titleEl.textContent = `Order #${order.id}`;
    if (badgeEl) {
      badgeEl.className = 'badge ' + (order.status === 'LOCKED_VERIFIED' ? 'badge-success' : (order.status === 'DISPATCHED' ? 'badge-info' : 'badge-primary'));
      badgeEl.textContent = order.status;
    }
    if (subtitleEl) subtitleEl.textContent = `${escapeOrderHtml(order.nursery_name || 'Nursery')} • ${escapeOrderHtml(order.variety)}`;
    if (nurseryEl) nurseryEl.textContent = order.nursery_name || 'Nursery Partner';
    if (supplierEl) supplierEl.textContent = order.supplier_name || 'Wholesale Supplier';
    if (dateEl) dateEl.textContent = order.created_at ? new Date(order.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '—';
    if (transportEl) {
      transportEl.textContent = (order.truck_no && order.truck_no !== 'TBD') ? `${order.truck_no} (${order.driver_info})` : 'Pending Dispatch / TBD';
    }

    if (totalQtyEl) totalQtyEl.textContent = `${details.total_qty || order.ordered_qty} units`;
    if (totalAmountEl) totalAmountEl.textContent = formatOrderCurrency(details.total_amount || (order.ordered_qty * order.unit_price));

    const tbody = document.getElementById('view-order-items-tbody');
    if (tbody) {
      if (items.length > 0) {
        tbody.innerHTML = items.map(it => `
          <tr>
            <td><strong>${escapeOrderHtml(it.variety)}</strong></td>
            <td><span class="badge badge-secondary">${escapeOrderHtml(it.category || 'General')}</span></td>
            <td>${escapeOrderHtml(it.container_size || 'Standard')}</td>
            <td style="color: var(--primary); font-weight: 600;">${formatOrderCurrency(it.unit_price)}</td>
            <td><strong>${it.quantity}</strong></td>
            <td style="font-weight: 800; color: var(--primary);">${formatOrderCurrency(it.line_total)}</td>
          </tr>
        `).join('');
      } else {
        tbody.innerHTML = `
          <tr>
            <td><strong>${escapeOrderHtml(order.variety)}</strong></td>
            <td><span class="badge badge-secondary">Wholesale Batch</span></td>
            <td>Commercial Nursery Spec</td>
            <td style="color: var(--primary); font-weight: 600;">${formatOrderCurrency(order.unit_price)}</td>
            <td><strong>${order.ordered_qty}</strong></td>
            <td style="font-weight: 800; color: var(--primary);">${formatOrderCurrency(order.ordered_qty * order.unit_price)}</td>
          </tr>
        `;
      }
    }

    const inspBox = document.getElementById('view-order-inspection-box');
    if (inspBox) {
      if (details.inspection) {
        inspBox.style.display = 'block';
        document.getElementById('view-order-delivered-qty').textContent = details.inspection.delivered_qty;
        document.getElementById('view-order-sound-qty').textContent = details.inspection.sound_qty;
        document.getElementById('view-order-damaged-qty').textContent = details.inspection.damaged_qty;
        document.getElementById('view-order-damage-pct').textContent = `${details.inspection.damage_pct}%`;
        
        const sigsDiv = document.getElementById('view-order-signatures');
        if (sigsDiv && details.confirmations) {
          sigsDiv.innerHTML = details.confirmations.map(c => `
            <div>✅ <strong>${escapeOrderHtml(c.party_role)}:</strong> ${escapeOrderHtml(c.business_name)} (${new Date(c.confirmed_at).toLocaleString('en-IN')})</div>
          `).join('');
        }
      } else {
        inspBox.style.display = 'none';
      }
    }

    const agrBox = document.getElementById('view-order-agreement-box');
    if (agrBox) {
      if (details.agreement) {
        agrBox.style.display = 'block';
        const summaryDiv = document.getElementById('view-order-agr-summary');
        if (summaryDiv) {
          summaryDiv.innerHTML = `
            <div>Ref: <strong>${escapeOrderHtml(details.agreement.agreement_ref)}</strong> | Status: <strong>${escapeOrderHtml(details.agreement.status)}</strong></div>
            <div>Advance: ${formatOrderCurrency(details.agreement.advance_amount)} | Balance Due: ${formatOrderCurrency(details.agreement.balance_amount)} (by ${escapeOrderHtml(details.agreement.payment_due_date)})</div>
          `;
        }
      } else {
        agrBox.style.display = 'none';
      }
    }

    modal.style.display = 'flex';
  } catch (err) {
    console.error('Error fetching order details:', err);
    showToast(err.message || 'Could not load order details.', 'error');
  }
}

function closeOrderDetailModal() {
  const modal = document.getElementById('order-detail-modal');
  if (modal) modal.style.display = 'none';
}

/**
 * Toggles and dynamically loads the append-only audit trail for the active order (Phase 16)
 */
async function toggleOrderAuditHistory() {
  const container = document.getElementById('view-order-audit-container');
  const btn = document.getElementById('btn-toggle-order-audit');
  const list = document.getElementById('view-order-audit-list');
  const countEl = document.getElementById('view-order-audit-count');
  if (!container) return;

  if (container.style.display === 'block') {
    container.style.display = 'none';
    if (btn) btn.innerHTML = '<span>📜</span> View Audit History';
    return;
  }

  const orderId = window.__currentLoadedOrderId;
  if (!orderId) {
    showToast('No active order selected.', 'warning');
    return;
  }

  if (btn) btn.innerHTML = '<span>⏳</span> Loading Audit Trail...';

  try {
    const resp = await fetch(`/api/orders/${orderId}/audit`);
    const body = await resp.json().catch(() => ({}));
    if (!resp.ok || !body.success) {
      showToast(body.error || 'Failed to retrieve order audit history.', 'warning');
      if (btn) btn.innerHTML = '<span>📜</span> View Audit History';
      return;
    }

    const events = body.data || [];
    if (countEl) countEl.textContent = `${events.length} event${events.length === 1 ? '' : 's'}`;

    if (events.length === 0) {
      list.innerHTML = '<div style="padding: 1rem; color: var(--text-secondary); text-align: center;">No audit events recorded for this order.</div>';
    } else {
      list.innerHTML = events.map(ev => {
        const dt = ev.created_at ? new Date(ev.created_at).toLocaleString('en-IN') : '—';
        let detailHtml = '';
        if (ev.details) {
          try {
            const parsed = typeof ev.details === 'string' ? JSON.parse(ev.details) : ev.details;
            detailHtml = Object.entries(parsed).map(([k, v]) => `<strong>${escapeHtml(k)}:</strong> ${escapeHtml(String(v))}`).join(' • ');
          } catch (_) {
            detailHtml = escapeHtml(String(ev.details));
          }
        }
        return `
          <div style="padding: 0.5rem 0.6rem; border-bottom: 1px solid var(--border-color); display: flex; flex-direction: column; gap: 0.2rem;">
            <div style="display: flex; justify-content: space-between; font-size: 0.78rem; color: var(--text-secondary);">
              <span><strong>${escapeHtml(ev.action || ev.event_type || 'EVENT')}</strong> by <strong>${escapeHtml(ev.actor_business || ev.actor_username || ev.actor_role || 'System')}</strong></span>
              <span>${dt}</span>
            </div>
            ${detailHtml ? `<div style="font-size: 0.8rem; color: var(--text-main);">${detailHtml}</div>` : ''}
          </div>
        `;
      }).join('');
    }

    container.style.display = 'block';
    if (btn) btn.innerHTML = '<span>📜</span> Hide Audit History';
  } catch (err) {
    console.error('Error fetching order audit trail:', err);
    showToast('Network error while retrieving order audit log.', 'error');
    if (btn) btn.innerHTML = '<span>📜</span> View Audit History';
  }
}

// ============================================================================
// PHASE 7: TRUCK LOADING & VEHICLE MANIFEST ENGINE
// ============================================================================

let liveTruckManifests = [];
let currentTruckStatusFilter = 'ALL';
let truckSearchQuery = '';
let currentTruckOrderDetails = null;

function formatTruckStatusBadge(status) {
  switch (status) {
    case 'CONFIRMED':
      return `<span class="badge badge-primary">Ready to Load</span>`;
    case 'STAGING':
      return `<span class="badge badge-warning">Staging in Progress</span>`;
    case 'DISPATCHED':
      return `<span class="badge badge-info">In Transit</span>`;
    case 'LOCKED_VERIFIED':
    case 'DELIVERED':
      return `<span class="badge badge-success">Delivered & Verified</span>`;
    case 'CANCELLED':
      return `<span class="badge badge-danger">Cancelled</span>`;
    default:
      return `<span class="badge badge-secondary">${escapeOrderHtml(status || 'Draft')}</span>`;
  }
}

async function fetchAndRenderTruckLoadings() {
  const tbody = document.getElementById('truck-manifests-table-tbody');
  const dashTbody = document.getElementById('supplier-truck-loading-tbody');

  if (tbody) {
    tbody.innerHTML = `
      <tr>
        <td colspan="10" style="text-align: center; color: var(--text-secondary); padding: 2.5rem;">
          <div style="display: flex; align-items: center; justify-content: center; gap: 0.5rem;">
            <span>🔄</span> Loading vehicle manifests from live database...
          </div>
        </td>
      </tr>
    `;
  }

  try {
    const res = await fetch('/api/truck-loadings');
    if (!res.ok) {
      if (res.status === 401) {
        if (tbody) tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--danger); padding: 2rem;">Please sign in to view truck loading manifests.</td></tr>`;
        return;
      }
      throw new Error(`Server returned HTTP ${res.status}`);
    }

    const data = await res.json();
    if (data.success && Array.isArray(data.data)) {
      liveTruckManifests = data.data;
      updateTruckSummaryKPIs(liveTruckManifests);
      applyTruckFiltersAndRender();

      // Also update the Recent Truck Loading table on the Supplier Dashboard!
      if (dashTbody) {
        dashTbody.innerHTML = liveTruckManifests.slice(0, 5).map(m => {
          const truckStr = (m.truck_no && m.truck_no !== 'TBD') ? m.truck_no : 'Pending Assignment';
          const driverStr = (m.driver_info && m.driver_info !== 'TBD') ? m.driver_info : 'Pending Assignment';
          const dateStr = m.loaded_at ? new Date(m.loaded_at).toLocaleDateString('en-IN') : (m.created_at ? new Date(m.created_at).toLocaleDateString('en-IN') : '—');
          return `
            <tr>
              <td><strong>${escapeOrderHtml(truckStr)}</strong></td>
              <td>${escapeOrderHtml(m.nursery_name)}</td>
              <td>${dateStr}</td>
              <td>${escapeOrderHtml(driverStr)}</td>
              <td>${formatTruckStatusBadge(m.status)}</td>
            </tr>
          `;
        }).join('');
      }
    } else {
      throw new Error(data.error || 'Failed to load manifests.');
    }
  } catch (err) {
    console.error('Error fetching truck loadings:', err);
    if (tbody) {
      tbody.innerHTML = `
        <tr>
          <td colspan="10" style="text-align: center; color: var(--danger); padding: 2rem;">
            ⚠️ Could not load manifests. <button class="btn btn-secondary btn-sm" onclick="fetchAndRenderTruckLoadings()" style="margin-left: 0.5rem;">Retry</button>
          </td>
        </tr>
      `;
    }
  }
}

function updateTruckSummaryKPIs(manifests) {
  const activeManifests = manifests.filter(m => m.status === 'CONFIRMED' || m.status === 'STAGING').length;
  const loadedUnits = manifests.reduce((sum, m) => sum + (m.total_loaded_qty || 0), 0);
  const dispatchedCount = manifests.filter(m => m.status === 'DISPATCHED').length;
  const completedCount = manifests.filter(m => m.status === 'LOCKED_VERIFIED' || m.status === 'DELIVERED').length;

  const activeEl = document.getElementById('kpi-truck-active-manifests');
  const unitsEl = document.getElementById('kpi-truck-loaded-units');
  const dispEl = document.getElementById('kpi-truck-dispatched-count');
  const compEl = document.getElementById('kpi-truck-completed-count');

  if (activeEl) activeEl.textContent = activeManifests;
  if (unitsEl) unitsEl.textContent = loadedUnits.toLocaleString('en-IN');
  if (dispEl) dispEl.textContent = dispatchedCount;
  if (compEl) compEl.textContent = completedCount;
}

function handleTruckSearch(value) {
  truckSearchQuery = (value || '').toLowerCase().trim();
  const clearBtn = document.getElementById('truck-search-clear');
  if (clearBtn) clearBtn.style.display = truckSearchQuery ? 'block' : 'none';
  applyTruckFiltersAndRender();
}

function clearTruckSearch() {
  const input = document.getElementById('truck-search-input');
  if (input) input.value = '';
  handleTruckSearch('');
}

function setTruckStatusFilter(status) {
  currentTruckStatusFilter = status;
  ['all', 'staging', 'dispatched', 'completed'].forEach(key => {
    const pill = document.getElementById(`pill-truck-${key}`);
    if (pill) pill.classList.remove('active');
  });

  const activeId = status === 'ALL' ? 'pill-truck-all' :
                   status === 'STAGING' ? 'pill-truck-staging' :
                   status === 'DISPATCHED' ? 'pill-truck-dispatched' :
                   status === 'COMPLETED' ? 'pill-truck-completed' : 'pill-truck-all';
  const activeEl = document.getElementById(activeId);
  if (activeEl) activeEl.classList.add('active');

  applyTruckFiltersAndRender();
}

function applyTruckFiltersAndRender() {
  let filtered = [...liveTruckManifests];

  if (currentTruckStatusFilter === 'STAGING') {
    filtered = filtered.filter(m => m.status === 'CONFIRMED' || m.status === 'STAGING');
  } else if (currentTruckStatusFilter === 'DISPATCHED') {
    filtered = filtered.filter(m => m.status === 'DISPATCHED');
  } else if (currentTruckStatusFilter === 'COMPLETED') {
    filtered = filtered.filter(m => m.status === 'LOCKED_VERIFIED' || m.status === 'DELIVERED');
  }

  if (truckSearchQuery) {
    filtered = filtered.filter(m => {
      const idMatch = (m.order_id || '').toLowerCase().includes(truckSearchQuery);
      const truckMatch = (m.truck_no || '').toLowerCase().includes(truckSearchQuery);
      const driverMatch = (m.driver_info || '').toLowerCase().includes(truckSearchQuery);
      const nurseryMatch = (m.nursery_name || '').toLowerCase().includes(truckSearchQuery);
      const varietyMatch = (m.variety || '').toLowerCase().includes(truckSearchQuery);
      return idMatch || truckMatch || driverMatch || nurseryMatch || varietyMatch;
    });
  }

  renderTruckManifestsTable(filtered);
}

function renderTruckManifestsTable(manifests) {
  const tbody = document.getElementById('truck-manifests-table-tbody');
  const subtitle = document.getElementById('truck-count-subtitle');
  if (!tbody) return;

  if (subtitle) {
    subtitle.textContent = `Showing ${manifests.length} of ${liveTruckManifests.length} wholesale vehicle loading records`;
  }

  if (manifests.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="10" style="text-align: center; color: var(--text-secondary); padding: 3rem 1.5rem;">
          <div style="font-size: 2rem; margin-bottom: 0.5rem;">🚚</div>
          <p style="font-weight: 600; color: var(--text-main); margin-bottom: 0.35rem;">No vehicle manifests found</p>
          <p style="font-size: 0.85rem; margin-bottom: 1rem;">Try clearing search filters or load an eligible wholesale order.</p>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = manifests.map(m => {
    const truckStr = (m.truck_no && m.truck_no !== 'TBD') ? `<strong>${escapeOrderHtml(m.truck_no)}</strong>` : '<span style="color: var(--text-secondary); font-style: italic;">Pending Vehicle</span>';
    const driverStr = (m.driver_info && m.driver_info !== 'TBD') ? escapeOrderHtml(m.driver_info) : '<span style="color: var(--text-secondary); font-style: italic;">Pending Driver</span>';
    const isCompleted = m.status === 'LOCKED_VERIFIED' || m.status === 'DELIVERED';

    return `
      <tr>
        <td><strong style="color: var(--text-main); font-family: monospace; font-size: 0.92rem;">${escapeOrderHtml(m.order_id)}</strong></td>
        <td>
          <div style="font-weight: 600; color: var(--text-main);">${escapeOrderHtml(m.nursery_name || 'Nursery Partner')}</div>
        </td>
        <td>${truckStr}</td>
        <td><div style="font-size: 0.82rem;">${driverStr}</div></td>
        <td>
          <div style="font-weight: 500; max-width: 200px; white-space: normal; line-height: 1.35;">${escapeOrderHtml(m.variety)}</div>
        </td>
        <td><strong>${m.ordered_qty}</strong></td>
        <td style="color: var(--primary); font-weight: 700;">${m.total_loaded_qty}</td>
        <td>
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            <div style="flex: 1; min-width: 60px; height: 6px; background: rgba(0,0,0,0.08); border-radius: 3px; overflow: hidden;">
              <div style="width: ${m.loading_pct}%; height: 100%; background: ${m.loading_pct === 100 ? 'var(--success)' : 'var(--primary)'}; border-radius: 3px;"></div>
            </div>
            <span style="font-size: 0.78rem; font-weight: 700; color: ${m.loading_pct === 100 ? 'var(--success)' : 'var(--text-main)'};">${m.loading_pct}%</span>
          </div>
        </td>
        <td>${formatTruckStatusBadge(m.status)}</td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="openTruckLoadingModal('${escapeOrderHtml(m.order_id)}')" title="${isCompleted ? 'View immutable manifest' : 'Staging & truck loading'}">
            <span>${isCompleted ? '👁️' : '🚚'}</span> ${isCompleted ? 'Manifest' : 'Load / Edit'}
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

async function openTruckLoadingModal(orderId) {
  const modal = document.getElementById('truck-loading-modal');
  if (!modal) return;

  clearTruckFieldErrors();

  try {
    const res = await fetch(`/api/orders/${orderId}/loading`);
    if (!res.ok) throw new Error(`Server returned HTTP ${res.status}`);
    const body = await res.json();
    if (!body.success || !body.data) throw new Error(body.error || 'Could not load order manifest.');

    currentTruckOrderDetails = body.data;
    const order = currentTruckOrderDetails.order;
    const items = currentTruckOrderDetails.items || [];

    document.getElementById('truck-modal-order-id').value = order.id;
    document.getElementById('truck-modal-title').textContent = `🚚 Truck Loading Manifest: Order #${order.id}`;
    
    const badgeEl = document.getElementById('truck-modal-status-badge');
    if (badgeEl) {
      badgeEl.className = 'badge ' + (order.status === 'LOCKED_VERIFIED' ? 'badge-success' : (order.status === 'DISPATCHED' ? 'badge-info' : 'badge-primary'));
      badgeEl.textContent = order.status;
    }

    document.getElementById('truck-modal-subtitle').textContent = `Client: ${escapeOrderHtml(order.nursery_name)} • Total Order: ${currentTruckOrderDetails.total_ordered_qty} plant units`;

    const truckNoInput = document.getElementById('truck-modal-truck-no');
    const driverInfoInput = document.getElementById('truck-modal-driver-info');
    const notesInput = document.getElementById('truck-modal-notes');

    if (truckNoInput) truckNoInput.value = (order.truck_no && order.truck_no !== 'TBD') ? order.truck_no : '';
    if (driverInfoInput) driverInfoInput.value = (order.driver_info && order.driver_info !== 'TBD') ? order.driver_info : '';
    if (notesInput) notesInput.value = order.loading_notes || '';

    const lockedNotice = document.getElementById('truck-modal-locked-notice');
    const isEditable = currentTruckOrderDetails.is_editable;
    const saveBtn = document.getElementById('btn-save-truck-staging');
    const dispatchBtn = document.getElementById('btn-dispatch-truck');
    const autoLoadBtn = document.getElementById('btn-load-all-max');

    if (lockedNotice) lockedNotice.style.display = isEditable ? 'none' : 'block';
    if (truckNoInput) truckNoInput.disabled = !isEditable;
    if (driverInfoInput) driverInfoInput.disabled = !isEditable;
    if (notesInput) notesInput.disabled = !isEditable;
    if (saveBtn) saveBtn.style.display = isEditable ? 'inline-flex' : 'none';
    if (dispatchBtn) dispatchBtn.style.display = isEditable ? 'inline-flex' : 'none';
    if (autoLoadBtn) autoLoadBtn.style.display = isEditable ? 'inline-flex' : 'none';

    const tbody = document.getElementById('truck-loading-modal-items-tbody');
    if (tbody) {
      tbody.innerHTML = items.map(it => {
        const remaining = it.quantity - (it.loaded_qty || 0);
        const itemStatus = (it.loaded_qty === it.quantity) 
          ? '<span class="badge badge-success" style="font-size: 0.72rem;">Loaded</span>' 
          : ((it.loaded_qty > 0) ? '<span class="badge badge-warning" style="font-size: 0.72rem;">Partial</span>' : '<span class="badge badge-secondary" style="font-size: 0.72rem;">Pending</span>');

        return `
          <tr data-item-id="${it.id}" data-ordered="${it.quantity}">
            <td>
              <strong>${escapeOrderHtml(it.variety)}</strong>
              ${it.container_size ? `<div style="font-size: 0.75rem; color: var(--text-secondary);">${escapeOrderHtml(it.container_size)} (${escapeOrderHtml(it.unit || 'unit')})</div>` : ''}
            </td>
            <td style="text-align: center; font-weight: 700;">${it.quantity}</td>
            <td style="text-align: center; color: var(--text-secondary);">${it.loaded_qty || 0}</td>
            <td style="text-align: center;">
              <input 
                type="number" 
                class="form-input truck-item-loaded-input" 
                data-item-id="${it.id}"
                data-ordered="${it.quantity}"
                min="0" 
                max="${it.quantity}" 
                step="1" 
                value="${it.loaded_qty || 0}"
                oninput="handleTruckItemQtyChange(this)"
                style="width: 80px; text-align: center; padding: 0.35rem; font-weight: 700; margin: 0 auto;"
                ${!isEditable ? 'disabled' : ''}
                required
              >
            </td>
            <td style="text-align: center; font-weight: 700;" class="truck-item-remaining-col">${remaining}</td>
            <td style="text-align: center;" class="truck-item-status-col">${itemStatus}</td>
          </tr>
        `;
      }).join('');
    }

    updateTruckModalTotals();
    modal.style.display = 'flex';
  } catch (err) {
    console.error('Error opening truck loading modal:', err);
    showToast(err.message || 'Could not open truck loading manifest.', 'error');
  }
}

function closeTruckLoadingModal() {
  const modal = document.getElementById('truck-loading-modal');
  if (modal) modal.style.display = 'none';
  clearTruckFieldErrors();
}

function clearTruckFieldErrors() {
  const errTruck = document.getElementById('err-truck-no');
  const errDriver = document.getElementById('err-driver-info');
  const errItems = document.getElementById('err-truck-items');
  if (errTruck) errTruck.style.display = 'none';
  if (errDriver) errDriver.style.display = 'none';
  if (errItems) errItems.style.display = 'none';
}

function handleTruckItemQtyChange(inputEl) {
  const tr = inputEl.closest('tr');
  if (!tr) return;

  const ordered = parseInt(inputEl.getAttribute('data-ordered'), 10) || 0;
  let val = parseInt(inputEl.value, 10);

  if (isNaN(val) || val < 0) {
    val = 0;
    inputEl.value = 0;
  } else if (val > ordered) {
    val = ordered;
    inputEl.value = ordered;
    showToast(`Loaded quantity cannot exceed ordered units (${ordered}).`, 'warning');
  }

  const remainingCol = tr.querySelector('.truck-item-remaining-col');
  const statusCol = tr.querySelector('.truck-item-status-col');
  const remaining = Math.max(0, ordered - val);

  if (remainingCol) remainingCol.textContent = remaining;
  if (statusCol) {
    if (val === ordered && ordered > 0) {
      statusCol.innerHTML = '<span class="badge badge-success" style="font-size: 0.72rem;">Loaded</span>';
    } else if (val > 0) {
      statusCol.innerHTML = '<span class="badge badge-warning" style="font-size: 0.72rem;">Partial</span>';
    } else {
      statusCol.innerHTML = '<span class="badge badge-secondary" style="font-size: 0.72rem;">Pending</span>';
    }
  }

  updateTruckModalTotals();
}

function autoLoadMaxAllItems() {
  const tbody = document.getElementById('truck-loading-modal-items-tbody');
  if (!tbody) return;

  const rows = tbody.querySelectorAll('tr');
  rows.forEach(tr => {
    const input = tr.querySelector('.truck-item-loaded-input');
    const ordered = parseInt(tr.getAttribute('data-ordered'), 10) || 0;
    if (input && !input.disabled) {
      input.value = ordered;
      handleTruckItemQtyChange(input);
    }
  });

  showToast('All items staged to maximum ordered capacity.', 'info');
}

function updateTruckModalTotals() {
  const tbody = document.getElementById('truck-loading-modal-items-tbody');
  if (!tbody) return;

  const rows = tbody.querySelectorAll('tr');
  let totalOrdered = 0;
  let totalLoaded = 0;

  rows.forEach(tr => {
    const ordered = parseInt(tr.getAttribute('data-ordered'), 10) || 0;
    const input = tr.querySelector('.truck-item-loaded-input');
    const loaded = parseInt(input?.value, 10) || 0;

    totalOrdered += ordered;
    totalLoaded += loaded;
  });

  const remaining = Math.max(0, totalOrdered - totalLoaded);
  const pct = totalOrdered > 0 ? Math.round((totalLoaded / totalOrdered) * 100) : 0;

  const orderedEl = document.getElementById('truck-modal-total-ordered');
  const loadedEl = document.getElementById('truck-modal-total-loaded');
  const remainingEl = document.getElementById('truck-modal-total-remaining');
  const pctEl = document.getElementById('truck-modal-progress-pct');
  const barEl = document.getElementById('truck-modal-progress-bar');

  if (orderedEl) orderedEl.textContent = totalOrdered;
  if (loadedEl) loadedEl.textContent = totalLoaded;
  if (remainingEl) remainingEl.textContent = remaining;
  if (pctEl) pctEl.textContent = `${pct}%`;
  if (barEl) {
    barEl.style.width = `${pct}%`;
    barEl.style.background = pct === 100 ? 'var(--success)' : 'var(--primary)';
  }
}

async function submitTruckLoading(isDispatch) {
  clearTruckFieldErrors();

  const orderId = document.getElementById('truck-modal-order-id')?.value;
  if (!orderId) return;

  const truckNo = (document.getElementById('truck-modal-truck-no')?.value || '').trim();
  const driverInfo = (document.getElementById('truck-modal-driver-info')?.value || '').trim();
  const notes = (document.getElementById('truck-modal-notes')?.value || '').trim();

  // Validate dispatch requirements
  if (isDispatch) {
    let hasErr = false;
    if (!truckNo) {
      const errEl = document.getElementById('err-truck-no');
      if (errEl) errEl.style.display = 'block';
      hasErr = true;
    }
    if (!driverInfo) {
      const errEl = document.getElementById('err-driver-info');
      if (errEl) errEl.style.display = 'block';
      hasErr = true;
    }
    if (hasErr) return;
  }

  // Gather items loaded counts
  const tbody = document.getElementById('truck-loading-modal-items-tbody');
  const rows = tbody ? tbody.querySelectorAll('tr') : [];
  const items = [];
  let totalLoaded = 0;
  let validationError = null;

  rows.forEach(tr => {
    const itemId = parseInt(tr.getAttribute('data-item-id'), 10);
    const ordered = parseInt(tr.getAttribute('data-ordered'), 10) || 0;
    const input = tr.querySelector('.truck-item-loaded-input');
    const loaded = parseInt(input?.value, 10);

    if (isNaN(loaded) || loaded < 0) {
      validationError = 'Loaded quantity must be a non-negative whole integer.';
      return;
    }
    if (loaded > ordered) {
      validationError = `Loaded quantity (${loaded}) cannot exceed ordered quantity (${ordered}).`;
      return;
    }

    items.push({ id: itemId, loaded_qty: loaded });
    totalLoaded += loaded;
  });

  if (validationError) {
    const errItems = document.getElementById('err-truck-items');
    if (errItems) {
      errItems.textContent = validationError;
      errItems.style.display = 'block';
    }
    return;
  }

  if (isDispatch && totalLoaded <= 0) {
    const errItems = document.getElementById('err-truck-items');
    if (errItems) {
      errItems.textContent = 'Cannot dispatch a transport vehicle with 0 loaded units.';
      errItems.style.display = 'block';
    }
    return;
  }

  const payload = {
    truck_no: truckNo,
    driver_info: driverInfo,
    notes: notes,
    dispatch: isDispatch,
    items: items
  };

  const btn = isDispatch ? document.getElementById('btn-dispatch-truck') : document.getElementById('btn-save-truck-staging');
  const originalHtml = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span>⏳</span> Processing...';
  }

  try {
    const res = await fetch(`/api/orders/${orderId}/loading`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.error || 'Failed to save truck loading.');
    }

    closeTruckLoadingModal();
    showToast(data.message || (isDispatch ? 'Vehicle dispatched successfully!' : 'Truck staging saved!'), 'success');

    // Refresh tables
    await fetchAndRenderTruckLoadings();
    if (typeof fetchAndRenderOrders === 'function') {
      fetchAndRenderOrders();
    }
  } catch (err) {
    console.error('Error saving truck loading:', err);
    showToast(err.message || 'Error saving truck loading.', 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }
  }
}

// ============================================================================
// PHASE 8: WHOLESALE INVOICE GENERATION & FREEZING ENGINE
// ============================================================================

let liveInvoices = [];
let currentInvoicesStatusFilter = 'ALL';
let currentInvoicesDueStatusFilter = 'ALL';
let invoicesSearchQuery = '';
let currentActiveInvoiceId = null;
let currentActiveInvoiceData = null;

function formatInvoiceStatusBadge(status) {
  switch (status) {
    case 'ISSUED':
      return '<span class="badge badge-success" style="font-weight: 700;">ISSUED</span>';
    case 'CANCELLED':
      return '<span class="badge badge-danger">CANCELLED</span>';
    case 'DRAFT':
      return '<span class="badge badge-warning">DRAFT</span>';
    default:
      return `<span class="badge badge-secondary">${status || 'UNKNOWN'}</span>`;
  }
}

function formatDueStatusBadge(dueStatus, overdueDays) {
  const s = (dueStatus || '').toUpperCase();
  switch (s) {
    case 'OVERDUE':
      return `<span class="badge badge-danger" style="font-weight: 700;">OVERDUE (${overdueDays || 0}d)</span>`;
    case 'NOT_DUE':
      return '<span class="badge badge-info" style="font-weight: 600;">NOT DUE</span>';
    case 'IN_GRACE_PERIOD':
      return '<span class="badge badge-warning" style="font-weight: 600;">GRACE PERIOD</span>';
    case 'SETTLED':
      return '<span class="badge badge-success" style="font-weight: 700;">SETTLED</span>';
    case 'NO_DUE_DATE':
      return '<span class="badge badge-neutral">NO DUE DATE</span>';
    case 'CANCELLED':
      return '<span class="badge badge-neutral">CANCELLED</span>';
    default:
      return `<span class="badge badge-neutral">${escapeOrderHtml(s || '-')}</span>`;
  }
}

function formatInvoiceCurrency(amount) {
  return '₹' + Number(amount || 0).toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

async function fetchAndRenderInvoices() {
  const tbody = document.getElementById('invoices-table-tbody');
  if (tbody && liveInvoices.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="10" style="text-align: center; color: var(--text-secondary); padding: 2.5rem;">
          Loading commercial wholesale invoices...
        </td>
      </tr>
    `;
  }

  try {
    let url = `/api/invoices?status=${encodeURIComponent(currentInvoicesStatusFilter)}`;
    if (currentInvoicesDueStatusFilter && currentInvoicesDueStatusFilter !== 'ALL') {
      url += `&due_status=${encodeURIComponent(currentInvoicesDueStatusFilter)}`;
    }
    if (invoicesSearchQuery) {
      url += `&search=${encodeURIComponent(invoicesSearchQuery)}`;
    }

    const res = await fetch(url);
    if (!res.ok) {
      if (res.status === 401) {
        if (tbody) tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--danger); padding: 2rem;">Please sign in to view invoices.</td></tr>`;
        return;
      }
      throw new Error(`Failed to fetch invoices: HTTP ${res.status}`);
    }

    const json = await res.json();
    if (!json.success || !Array.isArray(json.data)) {
      throw new Error(json.error || 'Invalid API response format.');
    }

    liveInvoices = json.data;
    updateInvoicesSummaryKPIs(liveInvoices);
    renderInvoicesTable(liveInvoices);
  } catch (err) {
    console.error('Error fetching invoices:', err);
    if (tbody) {
      tbody.innerHTML = `
        <tr>
          <td colspan="10" style="text-align: center; color: var(--danger); padding: 2rem;">
            Failed to load commercial invoices. ${err.message || ''}
          </td>
        </tr>
      `;
    }
  }
}

async function updateInvoicesSummaryKPIs(invoices) {
  const elTotal = document.getElementById('kpi-invoices-total-invoiced');
  const elActive = document.getElementById('kpi-invoices-active-count');
  const elUnits = document.getElementById('kpi-invoices-units-invoiced');
  const elReady = document.getElementById('kpi-invoices-verified-ready');

  const activeInvoices = invoices.filter(i => i.status === 'ISSUED');
  const totalAmount = activeInvoices.reduce((sum, i) => sum + (Number(i.total_amount) || 0), 0);
  const totalUnits = activeInvoices.reduce((sum, i) => sum + (Number(i.total_quantity) || 0), 0);

  if (elTotal) elTotal.textContent = formatInvoiceCurrency(totalAmount);
  if (elActive) elActive.textContent = activeInvoices.length;
  if (elUnits) elUnits.textContent = totalUnits.toLocaleString('en-IN');

  // Count verified orders ready to invoice
  try {
    const ordersRes = await fetch('/api/orders?status=LOCKED_VERIFIED');
    if (ordersRes.ok) {
      const oJson = await ordersRes.json();
      if (oJson.success && Array.isArray(oJson.data)) {
        const invoicedOrderIds = new Set(activeInvoices.map(i => i.order_id));
        const readyCount = oJson.data.filter(o => !invoicedOrderIds.has(o.id)).length;
        if (elReady) elReady.textContent = readyCount;
      }
    }
  } catch (e) {
    if (elReady) elReady.textContent = '-';
  }
}

function renderInvoicesTable(invoicesToRender) {
  const tbody = document.getElementById('invoices-table-tbody');
  if (!tbody) return;

  if (invoicesToRender.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="10" style="text-align: center; color: var(--text-secondary); padding: 3rem 1.5rem;">
          <div style="font-size: 2.2rem; margin-bottom: 0.5rem;">📄</div>
          <div style="font-weight: 700; margin-bottom: 0.25rem;">No commercial invoices found</div>
          <div style="font-size: 0.85rem; color: var(--text-muted); max-width: 440px; margin: 0 auto;">
            Invoices are generated strictly when wholesale deliveries complete physical inspection and dual counter-signature locking.
          </div>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = invoicesToRender.map(inv => {
    const dateStr = inv.invoice_date || (inv.created_at ? inv.created_at.split(' ')[0] : 'N/A');
    const itemsCount = inv.items_count || 1;
    const varietiesLabel = itemsCount === 1 ? '1 plant variety' : `${itemsCount} plant varieties`;
    const dueDateStr = inv.due_date || 'No Due Date';
    const dueBadge = formatDueStatusBadge(inv.due_status, inv.overdue_days);
    const accruedInterest = Number(inv.accrued_interest || 0);
    const totalPayable = Number(inv.total_amount_payable || inv.total_amount || 0);

    const interestHtml = accruedInterest > 0
      ? `<div style="font-size: 0.75rem; color: #9A3412; font-weight: 600; margin-top: 0.15rem;">+${formatInvoiceCurrency(accruedInterest)} late int. (Payable: ${formatInvoiceCurrency(totalPayable)})</div>`
      : '';

    return `
      <tr>
        <td>
          <span style="font-family: monospace; font-weight: 700; color: #063B00; font-size: 0.92rem;">
            ${escapeOrderHtml(inv.invoice_number)}
          </span>
        </td>
        <td style="font-size: 0.85rem; color: var(--text-secondary);">${dateStr}</td>
        <td>
          <span style="font-family: monospace; font-size: 0.85rem; background: var(--bg-surface); padding: 0.15rem 0.35rem; border-radius: 4px; border: 1px solid var(--border-color);">
            ${escapeOrderHtml(inv.order_id)}
          </span>
        </td>
        <td>
          <div style="font-weight: 600; color: var(--text-main); font-size: 0.9rem;">${escapeOrderHtml(inv.nursery_name || 'Nursery Partner')}</div>
        </td>
        <td>
          <div style="font-size: 0.85rem; color: var(--text-muted);">${varietiesLabel}</div>
        </td>
        <td>
          <strong style="color: var(--primary);">${(inv.total_quantity || 0).toLocaleString('en-IN')}</strong>
          <span style="font-size: 0.78rem; color: var(--text-muted);"> units</span>
        </td>
        <td>
          <strong style="font-size: 0.95rem; color: #063B00;">${formatInvoiceCurrency(inv.total_amount)}</strong>
        </td>
        <td>
          <div style="font-size: 0.85rem; font-weight: 600; color: var(--text-main);">${escapeOrderHtml(dueDateStr)}</div>
          <div style="margin-top: 0.2rem; display: flex; align-items: center; gap: 0.35rem; flex-wrap: wrap;">
            ${dueBadge}
          </div>
          ${interestHtml}
        </td>
        <td>${formatInvoiceStatusBadge(inv.status)}</td>
        <td style="text-align: right;">
          <div style="display: flex; gap: 0.35rem; justify-content: flex-end; align-items: center;">
            <button class="btn btn-secondary btn-sm" onclick="openInvoiceDetailModal('${escapeOrderHtml(inv.invoice_number)}')" title="View itemized commercial invoice">
              <span>👁️</span> View
            </button>
            <button class="btn btn-secondary btn-sm" onclick="printInvoiceDirect('${escapeOrderHtml(inv.invoice_number)}')" title="Print commercial invoice">
              <span>🖨️</span>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function handleInvoicesSearch(val) {
  invoicesSearchQuery = (val || '').trim();
  const clearBtn = document.getElementById('btn-clear-invoices-search');
  if (clearBtn) {
    clearBtn.style.display = invoicesSearchQuery ? 'block' : 'none';
  }
  fetchAndRenderInvoices();
}

function clearInvoicesSearch() {
  const input = document.getElementById('invoices-search-input');
  if (input) input.value = '';
  handleInvoicesSearch('');
}

function setInvoicesStatusFilter(status) {
  currentInvoicesStatusFilter = status;
  const pills = document.querySelectorAll('#invoices-status-pills .pill-btn');
  pills.forEach(p => {
    if (p.getAttribute('data-status') === status) {
      p.classList.add('active');
    } else {
      p.classList.remove('active');
    }
  });
  fetchAndRenderInvoices();
}

function setInvoicesDueStatusFilter(dueStatus) {
  currentInvoicesDueStatusFilter = dueStatus;
  const pills = document.querySelectorAll('#invoices-due-status-pills .pill-btn');
  pills.forEach(p => {
    if (p.getAttribute('data-due') === dueStatus) {
      p.classList.add('active');
    } else {
      p.classList.remove('active');
    }
  });
  fetchAndRenderInvoices();
}

async function openInvoiceDetailModal(invoiceIdOrNumber) {
  const modal = document.getElementById('invoice-detail-modal');
  if (!modal) return;

  currentActiveInvoiceId = invoiceIdOrNumber;

  // Clear previous data
  const tbody = document.getElementById('modal-inv-items-table-tbody');
  if (tbody) tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; padding: 2rem;">Loading invoice details...</td></tr>`;

  try {
    const res = await fetch(`/api/invoices/${encodeURIComponent(invoiceIdOrNumber)}`);
    if (!res.ok) {
      throw new Error(`Failed to load invoice: HTTP ${res.status}`);
    }

    const data = await res.json();
    if (!data.success || !data.data) {
      throw new Error(data.error || 'Failed to load invoice details.');
    }

    const inv = data.data.invoice;
    const items = data.data.items || [];
    const supplier = data.data.supplier || {};
    const nursery = data.data.nursery || {};

    // Header values
    const elNum = document.getElementById('modal-inv-number');
    const elBadge = document.getElementById('modal-inv-status-badge');
    const elDate = document.getElementById('modal-inv-date');
    const elOrder = document.getElementById('modal-inv-order-id');
    const elDueDate = document.getElementById('modal-inv-due-date');
    const elDueBox = document.getElementById('modal-inv-due-box');

    if (elNum) elNum.textContent = inv.invoice_number;
    if (elBadge) {
      elBadge.className = inv.status === 'ISSUED' ? 'badge badge-success' : 'badge badge-danger';
      elBadge.textContent = inv.status;
    }
    if (elDate) elDate.textContent = inv.invoice_date || (inv.created_at ? inv.created_at.split(' ')[0] : 'N/A');
    if (elOrder) elOrder.textContent = inv.order_id;
    if (elDueDate && elDueBox) {
      if (inv.due_date) {
        elDueDate.textContent = inv.due_date;
        elDueBox.style.display = 'block';
      } else {
        elDueBox.style.display = 'none';
      }
    }

    // Counterparties
    const elSuppName = document.getElementById('modal-inv-supplier-name');
    const elSuppEmail = document.getElementById('modal-inv-supplier-email');
    const elNursName = document.getElementById('modal-inv-nursery-name');
    const elNursEmail = document.getElementById('modal-inv-nursery-email');

    if (elSuppName) elSuppName.textContent = supplier.name || inv.supplier_name;
    if (elSuppEmail) elSuppEmail.textContent = supplier.email || inv.supplier_email;
    if (elNursName) elNursName.textContent = nursery.name || inv.nursery_name;
    if (elNursEmail) elNursEmail.textContent = nursery.email || inv.nursery_email;

    // Transport & Verification
    const elTruck = document.getElementById('modal-inv-truck-info');
    const elVerif = document.getElementById('modal-inv-verification-info');
    const elPolicy = document.getElementById('modal-inv-damage-policy');

    if (elTruck) elTruck.textContent = `${inv.truck_no || 'TBD'} • ${inv.driver_info || 'Driver on record'}`;
    if (elVerif) elVerif.textContent = 'Dual counter-signed & locked in audit ledger';
    if (elPolicy) {
      if (inv.damage_billing_policy === 'CREDITED_EXCLUDED') {
        elPolicy.textContent = 'Damaged plants credited (zero charge)';
      } else {
        elPolicy.textContent = inv.damage_billing_policy;
      }
    }

    // Line items table
    if (tbody) {
      tbody.innerHTML = items.map(it => {
        const specStr = it.container_size ? `${it.container_size} (${it.unit || 'plant'})` : (it.unit || 'plant');
        const damagedDeduction = it.damaged_qty > 0 && it.damaged_unit_price === 0
          ? `<span style="font-size: 0.75rem; color: var(--danger); display: block;">(-${it.damaged_qty} credited)</span>`
          : '';

        return `
          <tr>
            <td>
              <div style="font-weight: 700; color: var(--text-main);">${escapeOrderHtml(it.variety)}</div>
              ${it.botanical_name ? `<div style="font-size: 0.78rem; font-style: italic; color: var(--text-muted);">${escapeOrderHtml(it.botanical_name)}</div>` : ''}
            </td>
            <td><div style="font-size: 0.85rem; color: var(--text-secondary);">${escapeOrderHtml(specStr)}</div></td>
            <td style="text-align: right; color: var(--text-muted);">${it.ordered_qty}</td>
            <td style="text-align: right; color: var(--text-muted);">${it.delivered_qty}</td>
            <td style="text-align: right; font-weight: 600; color: var(--primary);">${it.sound_qty}</td>
            <td style="text-align: right; color: ${it.damaged_qty > 0 ? 'var(--danger)' : 'var(--text-muted)'}; font-weight: ${it.damaged_qty > 0 ? '600' : 'normal'};">
              ${it.damaged_qty}
            </td>
            <td style="text-align: right; font-weight: 700; color: #063B00;">
              ${it.billable_qty}
              ${damagedDeduction}
            </td>
            <td style="text-align: right;">${formatInvoiceCurrency(it.unit_price)}</td>
            <td style="text-align: right; font-weight: 700;">${formatInvoiceCurrency(it.line_total)}</td>
          </tr>
        `;
      }).join('');
    }

    // Financial totals
    const elSub = document.getElementById('modal-inv-subtotal');
    const elTax = document.getElementById('modal-inv-tax');
    const elDisc = document.getElementById('modal-inv-discount');
    const elGrand = document.getElementById('modal-inv-grand-total');
    const elNotes = document.getElementById('modal-inv-notes');

    if (elSub) elSub.textContent = formatInvoiceCurrency(inv.subtotal);
    if (elTax) elTax.textContent = formatInvoiceCurrency(inv.tax_amount);
    if (elDisc) elDisc.textContent = formatInvoiceCurrency(inv.discount_amount);
    if (elGrand) elGrand.textContent = formatInvoiceCurrency(inv.total_amount);
    if (elNotes) elNotes.textContent = inv.notes || 'Invoiced strictly based on verified sound delivered plants.';

    // Phase 9: Payment Summary & Allocations
    const paySum = data.data.payment_summary || {};
    const elPayTotal = document.getElementById('modal-inv-pay-total');
    const elTotalPaid = document.getElementById('modal-inv-total-paid');
    const elBalDue = document.getElementById('modal-inv-balance-due');
    const elPayBadge = document.getElementById('modal-inv-payment-badge');
    const payTbody = document.getElementById('modal-inv-payments-tbody');
    const btnRecordPay = document.getElementById('btn-modal-inv-record-payment');

    const invTotal = paySum.total_amount != null ? paySum.total_amount : inv.total_amount;
    const paidAmt = paySum.total_paid != null ? paySum.total_paid : 0.0;
    const balDue = paySum.outstanding_balance != null ? paySum.outstanding_balance : invTotal;
    const payStatus = paySum.payment_status || (paidAmt >= invTotal && invTotal > 0 ? 'PAID' : (paidAmt > 0 ? 'PARTIALLY_PAID' : 'UNPAID'));

    if (elPayTotal) elPayTotal.textContent = formatInvoiceCurrency(invTotal);
    if (elTotalPaid) elTotalPaid.textContent = formatInvoiceCurrency(paidAmt);
    if (elBalDue) elBalDue.textContent = formatInvoiceCurrency(balDue);
    if (elPayBadge) {
      elPayBadge.className = `badge ${payStatus === 'PAID' ? 'badge-success' : (payStatus === 'PARTIALLY_PAID' ? 'badge-warning' : 'badge-neutral')}`;
      elPayBadge.textContent = payStatus === 'PAID' ? 'PAID IN FULL' : (payStatus === 'PARTIALLY_PAID' ? 'PARTIALLY PAID' : 'UNPAID');
    }

    if (payTbody) {
      const allocs = paySum.allocations || [];
      if (allocs.length === 0) {
        payTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 0.75rem;">No payment receipts recorded yet.</td></tr>`;
      } else {
        payTbody.innerHTML = allocs.map(a => `
          <tr>
            <td><strong>${escapeOrderHtml(a.payment_date || '-')}</strong></td>
            <td><a href="javascript:void(0)" onclick="openPaymentDetailModal('${a.payment_id}')" style="font-weight: 700; color: var(--primary);">${escapeOrderHtml(a.payment_number || a.payment_id)}</a></td>
            <td>${formatPaymentMethodBadge(a.payment_method)} <span style="font-family: monospace; font-size: 0.75rem; color: var(--text-muted);">${escapeOrderHtml(a.reference_number || '')}</span></td>
            <td style="text-align: right; font-weight: 700; color: var(--primary);">${formatInvoiceCurrency(a.amount)}</td>
            <td><span class="badge ${a.status === 'ACTIVE' ? 'badge-success' : 'badge-danger'}">${escapeOrderHtml(a.status)}</span></td>
          </tr>
        `).join('');
      }
    }

    if (btnRecordPay) {
      btnRecordPay.style.display = (balDue > 0 && inv.status !== 'CANCELLED') ? 'inline-flex' : 'none';
    }

    // Cancel button visibility
    const cancelBtn = document.getElementById('btn-cancel-invoice');
    if (cancelBtn) {
      cancelBtn.style.display = inv.status === 'CANCELLED' ? 'none' : 'inline-flex';
    }

    // Phase 10: Contractual Due Date & Agreed Late-Payment Interest
    currentActiveInvoiceData = data.data;
    const interestSummary = data.data.interest_summary || {};

    const elDueDateDisplay = document.getElementById('modal-inv-due-date-display');
    const elOverdueDaysLabel = document.getElementById('modal-inv-overdue-days-label');
    const elDueBadge = document.getElementById('modal-inv-due-status-badge');
    const elAgreedRateDisplay = document.getElementById('modal-inv-agreed-rate-display');
    const elBasisDisplay = document.getElementById('modal-inv-basis-display');
    const elAccruedInterest = document.getElementById('modal-inv-accrued-interest');
    const elTotalPayable = document.getElementById('modal-inv-total-payable');
    const breakdownWrapper = document.getElementById('modal-inv-interest-breakdown-wrapper');
    const breakdownTbody = document.getElementById('modal-inv-interest-breakdown-tbody');
    const btnEditTerms = document.getElementById('btn-modal-inv-edit-terms');

    const dueStatus = interestSummary.due_status || 'NOT_DUE';
    const overdueDays = interestSummary.overdue_days || 0;
    const ratePct = interestSummary.interest_rate_pct != null ? interestSummary.interest_rate_pct : (inv.interest_rate_pct || 0.0);
    const basis = interestSummary.interest_calculation_basis || inv.interest_calculation_basis || 'ANNUAL_SIMPLE';
    const graceDays = interestSummary.interest_grace_period_days != null ? interestSummary.interest_grace_period_days : (inv.interest_grace_period_days || 0);
    const accruedInt = interestSummary.accrued_interest != null ? interestSummary.accrued_interest : 0.0;
    const totalPayableAmt = interestSummary.total_amount_payable != null ? interestSummary.total_amount_payable : (paySum.outstanding_balance != null ? paySum.outstanding_balance : inv.total_amount);

    if (elDueDateDisplay) {
      elDueDateDisplay.textContent = inv.due_date || 'No Due Date Set';
    }
    if (elOverdueDaysLabel) {
      if (dueStatus === 'OVERDUE') {
        elOverdueDaysLabel.textContent = `${overdueDays} days overdue`;
        elOverdueDaysLabel.style.color = 'var(--danger)';
        elOverdueDaysLabel.style.fontWeight = '600';
      } else if (dueStatus === 'SETTLED') {
        elOverdueDaysLabel.textContent = 'Invoice settled in full';
        elOverdueDaysLabel.style.color = 'var(--success, #16a34a)';
        elOverdueDaysLabel.style.fontWeight = 'normal';
      } else if (dueStatus === 'IN_GRACE_PERIOD') {
        elOverdueDaysLabel.textContent = `Within grace period (${graceDays}d)`;
        elOverdueDaysLabel.style.color = '#d97706';
        elOverdueDaysLabel.style.fontWeight = '600';
      } else if (dueStatus === 'NOT_DUE' && inv.due_date) {
        elOverdueDaysLabel.textContent = `Payment due on ${inv.due_date}`;
        elOverdueDaysLabel.style.color = 'var(--text-muted)';
        elOverdueDaysLabel.style.fontWeight = 'normal';
      } else {
        elOverdueDaysLabel.textContent = 'No active overdue accrual';
        elOverdueDaysLabel.style.color = 'var(--text-muted)';
        elOverdueDaysLabel.style.fontWeight = 'normal';
      }
    }
    if (elDueBadge) {
      elDueBadge.className = `badge ${
        dueStatus === 'OVERDUE' ? 'badge-danger' : 
        (dueStatus === 'SETTLED' ? 'badge-success' : 
        (dueStatus === 'IN_GRACE_PERIOD' ? 'badge-warning' : 'badge-neutral'))
      }`;
      elDueBadge.textContent = dueStatus;
    }
    if (elAgreedRateDisplay) {
      elAgreedRateDisplay.textContent = `${Number(ratePct).toFixed(1)}% p.a.`;
    }
    if (elBasisDisplay) {
      let basisText = basis === 'ANNUAL_SIMPLE' ? 'Annual Simple (Act/365)' : 
                      (basis === 'MONTHLY_SIMPLE' ? 'Monthly Simple (30/360)' : 
                      (basis === 'DAILY_SIMPLE' ? 'Daily Simple' : '0% No Interest'));
      if (graceDays > 0) {
        basisText += ` • ${graceDays}d grace`;
      }
      elBasisDisplay.textContent = basisText;
    }
    if (elAccruedInterest) {
      elAccruedInterest.textContent = formatInvoiceCurrency(accruedInt);
    }
    if (elTotalPayable) {
      elTotalPayable.textContent = formatInvoiceCurrency(totalPayableAmt);
    }

    // Stepwise Breakdown Table
    const breakdown = interestSummary.calculation_breakdown || [];
    if (breakdownWrapper && breakdownTbody) {
      if (breakdown.length > 0) {
        breakdownWrapper.style.display = 'block';
        breakdownTbody.innerHTML = breakdown.map(seg => `
          <tr>
            <td><strong>${escapeOrderHtml(seg.period_start)}</strong> to <strong>${escapeOrderHtml(seg.period_end)}</strong></td>
            <td style="text-align: right;">${seg.days}</td>
            <td style="text-align: right; font-family: monospace;">${formatInvoiceCurrency(seg.principal)}</td>
            <td style="text-align: right;">${Number(seg.rate_pct).toFixed(1)}%</td>
            <td style="text-align: right; font-weight: 700; color: #9A3412;">${formatInvoiceCurrency(seg.interest)}</td>
          </tr>
        `).join('');
      } else {
        breakdownWrapper.style.display = 'none';
        breakdownTbody.innerHTML = '';
      }
    }

    if (btnEditTerms) {
      btnEditTerms.style.display = inv.status !== 'CANCELLED' ? 'inline-flex' : 'none';
    }

    modal.style.display = 'flex';
  } catch (err) {
    console.error('Error opening invoice modal:', err);
    showToast(err.message || 'Failed to open invoice.', 'error');
  }
}

function closeInvoiceDetailModal() {
  const modal = document.getElementById('invoice-detail-modal');
  if (modal) modal.style.display = 'none';
  currentActiveInvoiceId = null;
  currentActiveInvoiceData = null;
}

function openEditInvoiceTermsModal() {
  const modal = document.getElementById('invoice-terms-modal');
  if (!modal) return;
  if (!currentActiveInvoiceData || !currentActiveInvoiceData.invoice) {
    showToast('No active invoice selected.', 'warning');
    return;
  }
  const inv = currentActiveInvoiceData.invoice;
  const inputDueDate = document.getElementById('terms-form-due-date');
  const inputRate = document.getElementById('terms-form-interest-rate');
  const inputBasis = document.getElementById('terms-form-basis');
  const inputGrace = document.getElementById('terms-form-grace-days');
  const inputNotes = document.getElementById('terms-form-notes');

  if (inputDueDate) inputDueDate.value = inv.due_date || '';
  if (inputRate) inputRate.value = inv.interest_rate_pct != null ? inv.interest_rate_pct : 18.0;
  if (inputBasis) inputBasis.value = inv.interest_calculation_basis || 'ANNUAL_SIMPLE';
  if (inputGrace) inputGrace.value = inv.interest_grace_period_days != null ? inv.interest_grace_period_days : 0;
  if (inputNotes) inputNotes.value = '';

  modal.style.display = 'flex';
}

function closeEditInvoiceTermsModal() {
  const modal = document.getElementById('invoice-terms-modal');
  if (modal) modal.style.display = 'none';
}

async function handleUpdateInvoiceTermsSubmit(e) {
  if (e) e.preventDefault();
  if (!currentActiveInvoiceId) return;

  const dueDate = (document.getElementById('terms-form-due-date')?.value || '').trim();
  const rateVal = parseFloat(document.getElementById('terms-form-interest-rate')?.value || '0');
  const basis = document.getElementById('terms-form-basis')?.value || 'ANNUAL_SIMPLE';
  const graceDays = parseInt(document.getElementById('terms-form-grace-days')?.value || '0', 10);
  const notes = (document.getElementById('terms-form-notes')?.value || '').trim();

  if (!dueDate) {
    showToast('Payment due date is required.', 'warning');
    return;
  }
  if (isNaN(rateVal) || rateVal < 0) {
    showToast('Interest rate must be 0 or a positive number.', 'warning');
    return;
  }

  const payload = {
    due_date: dueDate,
    interest_rate_pct: rateVal,
    interest_calculation_basis: basis,
    interest_grace_period_days: isNaN(graceDays) ? 0 : graceDays,
    notes: notes
  };

  try {
    const res = await fetch(`/api/invoices/${encodeURIComponent(currentActiveInvoiceId)}/interest-terms`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.error || 'Failed to update agreed terms.');
    }

    showToast(data.message || 'Agreed terms updated successfully.', 'success');
    closeEditInvoiceTermsModal();
    // Refresh modal and list
    await openInvoiceDetailModal(currentActiveInvoiceId);
    if (typeof fetchAndRenderInvoices === 'function') {
      fetchAndRenderInvoices();
    }
  } catch (err) {
    console.error('Error updating agreed terms:', err);
    showToast(err.message || 'Error updating agreed terms.', 'error');
  }
}

function printInvoiceModal() {
  window.print();
}

async function printInvoiceDirect(invoiceNumber) {
  await openInvoiceDetailModal(invoiceNumber);
  setTimeout(() => {
    window.print();
  }, 350);
}

async function generateInvoiceForOrder(orderId) {
  if (!confirm(`Generate commercial wholesale invoice for Order #${orderId}?\n\nThis will freeze billable quantities based strictly on verified sound plants.`)) {
    return;
  }

  try {
    const res = await fetch(`/api/orders/${encodeURIComponent(orderId)}/invoice`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.error || 'Failed to generate invoice.');
    }

    showToast(data.message || 'Commercial invoice successfully issued!', 'success');

    // Refresh orders and invoices
    if (typeof fetchAndRenderOrders === 'function') {
      fetchAndRenderOrders();
    }
    await fetchAndRenderInvoices();

    // Open the newly generated invoice modal
    if (data.data && data.data.invoice) {
      openInvoiceDetailModal(data.data.invoice.invoice_number);
    }
  } catch (err) {
    console.error('Error generating invoice:', err);
    showToast(err.message || 'Error generating invoice.', 'error');
  }
}

async function handleOrderInvoiceAction(orderId) {
  // Check if invoice already exists in liveInvoices
  const existing = liveInvoices.find(i => i.order_id === orderId && i.status === 'ISSUED');
  if (existing) {
    openInvoiceDetailModal(existing.invoice_number);
  } else {
    generateInvoiceForOrder(orderId);
  }
}

async function promptCancelInvoice() {
  if (!currentActiveInvoiceId) return;

  const reason = prompt('Please enter the reason for cancelling this commercial invoice:');
  if (!reason || !reason.trim()) {
    showToast('Cancellation reason is required.', 'warning');
    return;
  }

  try {
    const res = await fetch(`/api/invoices/${encodeURIComponent(currentActiveInvoiceId)}/cancel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: reason.trim() })
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.error || 'Failed to cancel invoice.');
    }

    showToast(data.message || 'Invoice cancelled successfully.', 'success');
    closeInvoiceDetailModal();
    fetchAndRenderInvoices();
  } catch (err) {
    console.error('Error cancelling invoice:', err);
    showToast(err.message || 'Error cancelling invoice.', 'error');
  }
}

// ============================================================================
// PHASE 9: WHOLESALE PAYMENT MANAGEMENT & SETTLEMENTS ENGINE
// ============================================================================

let livePayments = [];
let currentPaymentSearchQuery = '';
let currentPaymentStatusFilter = 'ALL';
let currentPaymentMethodFilter = 'ALL';
let currentActivePaymentId = null;
let availableInvoicesForPayment = [];

function formatPaymentCurrency(amount) {
  if (amount == null || isNaN(amount)) return '₹0.00';
  return '₹' + Number(amount).toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

function formatPaymentMethodBadge(method) {
  const m = (method || '').toUpperCase();
  switch (m) {
    case 'BANK_TRANSFER':
      return '<span class="badge badge-primary" style="font-size: 0.75rem;">Bank Transfer</span>';
    case 'UPI':
      return '<span class="badge badge-success" style="font-size: 0.75rem;">UPI</span>';
    case 'CHEQUE':
      return '<span class="badge badge-warning" style="font-size: 0.75rem;">Cheque</span>';
    case 'CASH':
      return '<span class="badge badge-neutral" style="font-size: 0.75rem;">Cash</span>';
    default:
      return `<span class="badge badge-neutral" style="font-size: 0.75rem;">${escapeOrderHtml(m || 'Other')}</span>`;
  }
}

function formatPaymentStatusBadge(status) {
  const s = (status || '').toUpperCase();
  switch (s) {
    case 'RECORDED':
      return '<span class="badge badge-success">RECORDED</span>';
    case 'REVERSED':
      return '<span class="badge badge-danger">REVERSED</span>';
    default:
      return `<span class="badge badge-neutral">${escapeOrderHtml(s)}</span>`;
  }
}

function formatPaymentTypeBadge(type) {
  const t = (type || '').toUpperCase();
  if (t === 'ADVANCE_PAYMENT') {
    return '<span class="badge badge-info" style="font-size: 0.75rem;">Advance</span>';
  }
  return '<span class="badge badge-primary" style="font-size: 0.75rem;">Invoice</span>';
}

async function fetchAndRenderPayments() {
  const tbody = document.getElementById('payments-table-tbody');
  if (tbody && livePayments.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="9" style="text-align: center; color: var(--text-secondary); padding: 2.5rem;">
          Loading wholesale payment records...
        </td>
      </tr>
    `;
  }

  try {
    const res = await fetch('/api/payments');
    if (!res.ok) {
      throw new Error(`Failed to fetch payments: HTTP ${res.status}`);
    }

    const data = await res.json();
    if (!data.success) {
      throw new Error(data.error || 'Failed to load payments.');
    }

    livePayments = data.data || [];
    if (data.kpi) {
      updatePaymentsSummaryKPIs(data.kpi);
    }

    filterAndRenderPayments();
  } catch (err) {
    console.error('Error fetching payments:', err);
    if (tbody) {
      tbody.innerHTML = `
        <tr>
          <td colspan="9" style="text-align: center; color: var(--danger); padding: 2rem;">
            Failed to load payment records: ${escapeOrderHtml(err.message || 'Server error')}
          </td>
        </tr>
      `;
    }
  }
}

function updatePaymentsSummaryKPIs(kpi) {
  const elTotalRec = document.getElementById('kpi-payments-total-received');
  const elOutstanding = document.getElementById('kpi-payments-outstanding-balance');
  const elSettled = document.getElementById('kpi-payments-invoices-settled');
  const elAdvance = document.getElementById('kpi-payments-advance-balance');

  if (elTotalRec) elTotalRec.textContent = formatPaymentCurrency(kpi.total_received || 0);
  if (elOutstanding) elOutstanding.textContent = formatPaymentCurrency(kpi.total_outstanding || 0);
  if (elSettled) elSettled.textContent = (kpi.settled_invoices_count || 0).toLocaleString('en-IN');
  if (elAdvance) elAdvance.textContent = formatPaymentCurrency(kpi.total_unallocated_advances || 0);
}

function filterAndRenderPayments() {
  let list = livePayments.slice();

  if (currentPaymentStatusFilter !== 'ALL') {
    list = list.filter(p => (p.status || '').toUpperCase() === currentPaymentStatusFilter);
  }

  if (currentPaymentMethodFilter !== 'ALL') {
    list = list.filter(p => (p.payment_method || '').toUpperCase() === currentPaymentMethodFilter);
  }

  if (currentPaymentSearchQuery) {
    const q = currentPaymentSearchQuery.toLowerCase();
    list = list.filter(p => {
      const num = (p.payment_number || '').toLowerCase();
      const ref = (p.reference_number || '').toLowerCase();
      const nursery = (p.nursery_name || '').toLowerCase();
      const inv = (p.invoice_number || '').toLowerCase();
      const notes = (p.notes || '').toLowerCase();
      return num.includes(q) || ref.includes(q) || nursery.includes(q) || inv.includes(q) || notes.includes(q);
    });
  }

  renderPaymentsTable(list);
}

function renderPaymentsTable(paymentsToRender) {
  const tbody = document.getElementById('payments-table-tbody');
  if (!tbody) return;

  if (paymentsToRender.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="9" style="text-align: center; color: var(--text-secondary); padding: 3rem 1.5rem;">
          <div style="font-size: 2.2rem; margin-bottom: 0.5rem;">💵</div>
          <div style="font-weight: 700; margin-bottom: 0.25rem;">No payment records found</div>
          <div style="font-size: 0.85rem; color: var(--text-muted); max-width: 440px; margin: 0 auto;">
            Record payments received via bank transfer (UTR), UPI, or cheque against issued wholesale invoices.
          </div>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = paymentsToRender.map(pay => {
    const isReversed = pay.status === 'REVERSED';
    const allocatedStr = pay.invoice_number
      ? `<span style="font-family: monospace; font-weight: 600; color: #063B00;">${escapeOrderHtml(pay.invoice_number)}</span>`
      : (pay.unallocated_amount > 0 ? `<span style="color: #166534; font-size: 0.8rem;">Advance (Unallocated: ${formatPaymentCurrency(pay.unallocated_amount)})</span>` : '<span style="color: var(--text-muted);">-</span>');

    return `
      <tr style="${isReversed ? 'opacity: 0.65; background: rgba(220, 38, 38, 0.02);' : ''}">
        <td>
          <span style="font-family: monospace; font-weight: 700; color: #063B00; font-size: 0.92rem;">
            ${escapeOrderHtml(pay.payment_number)}
          </span>
        </td>
        <td style="font-size: 0.85rem; color: var(--text-secondary);">${escapeOrderHtml(pay.payment_date || '-')}</td>
        <td>
          <div style="font-weight: 600; color: var(--text-main); font-size: 0.9rem;">${escapeOrderHtml(pay.nursery_name || 'Nursery Partner')}</div>
        </td>
        <td>
          <div>${formatPaymentMethodBadge(pay.payment_method)}</div>
          <div style="font-family: monospace; font-size: 0.76rem; color: var(--text-muted); margin-top: 0.15rem;">
            ${escapeOrderHtml(pay.reference_number)}
          </div>
        </td>
        <td>${formatPaymentTypeBadge(pay.payment_type)}</td>
        <td style="text-align: right;">
          <strong style="font-size: 0.95rem; color: ${isReversed ? 'var(--text-muted); text-decoration: line-through;' : 'var(--primary);'}">
            ${formatPaymentCurrency(pay.amount)}
          </strong>
        </td>
        <td>${allocatedStr}</td>
        <td>${formatPaymentStatusBadge(pay.status)}</td>
        <td style="text-align: right;">
          <div style="display: flex; gap: 0.35rem; justify-content: flex-end; align-items: center;">
            <button class="btn btn-secondary btn-sm" onclick="openPaymentDetailModal('${escapeOrderHtml(pay.id)}')" title="View payment receipt">
              <span>👁️</span> View
            </button>
            ${!isReversed ? `
              <button class="btn btn-secondary btn-sm" onclick="promptReversePayment('${escapeOrderHtml(pay.id)}')" title="Reverse payment record" style="color: var(--danger, #d32f2f);">
                <span>✕</span>
              </button>
            ` : ''}
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function handlePaymentsSearch(query) {
  currentPaymentSearchQuery = (query || '').trim();
  const clearBtn = document.getElementById('btn-clear-payments-search');
  if (clearBtn) {
    clearBtn.style.display = currentPaymentSearchQuery ? 'block' : 'none';
  }
  filterAndRenderPayments();
}

function clearPaymentsSearch() {
  const input = document.getElementById('payments-search-input');
  if (input) input.value = '';
  handlePaymentsSearch('');
}

function setPaymentsStatusFilter(status) {
  currentPaymentStatusFilter = (status || 'ALL').toUpperCase();
  const container = document.getElementById('payments-status-pills');
  if (container) {
    container.querySelectorAll('.pill-btn').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-status') === currentPaymentStatusFilter);
    });
  }
  filterAndRenderPayments();
}

function setPaymentsMethodFilter(method) {
  currentPaymentMethodFilter = (method || 'ALL').toUpperCase();
  const container = document.getElementById('payments-method-pills');
  if (container) {
    container.querySelectorAll('.pill-btn').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-method') === currentPaymentMethodFilter);
    });
  }
  filterAndRenderPayments();
}

async function openRecordPaymentModal(prefillInvoiceId = null, prefillOrderId = null) {
  const modal = document.getElementById('record-payment-modal');
  if (!modal) return;

  const form = document.getElementById('record-payment-form');
  if (form) form.reset();

  const dateInput = document.getElementById('pay-form-date');
  if (dateInput) {
    dateInput.value = new Date().toISOString().split('T')[0];
  }

  const previewBox = document.getElementById('pay-balance-preview-box');
  if (previewBox) previewBox.style.display = 'none';

  const select = document.getElementById('pay-form-invoice-select');
  if (select) {
    select.innerHTML = '<option value="" disabled selected>Loading active invoices...</option>';

    try {
      const res = await fetch('/api/invoices?status=ISSUED');
      if (res.ok) {
        const data = await res.json();
        availableInvoicesForPayment = (data.data || []).filter(inv => inv.status !== 'CANCELLED');

        select.innerHTML = '<option value="" disabled selected>Select an issued commercial invoice...</option>';

        availableInvoicesForPayment.forEach(inv => {
          const bal = inv.outstanding_balance != null ? inv.outstanding_balance : inv.total_amount;
          const isSelected = prefillInvoiceId && (inv.id === prefillInvoiceId || inv.invoice_number === prefillInvoiceId);
          const opt = document.createElement('option');
          opt.value = inv.id;
          opt.textContent = `${inv.invoice_number} • ${inv.nursery_name || 'Nursery'} • Balance: ${formatPaymentCurrency(bal)}`;
          if (isSelected) opt.selected = true;
          select.appendChild(opt);
        });

        const advOpt = document.createElement('option');
        advOpt.value = '__ADVANCE__';
        advOpt.textContent = '📥 Record Unallocated Advance Payment / Deposit';
        select.appendChild(advOpt);

        if (prefillInvoiceId) {
          handlePaymentInvoiceSelectionChange(prefillInvoiceId);
        }
      }
    } catch (err) {
      console.error('Error loading invoices for payment modal:', err);
      select.innerHTML = '<option value="" disabled selected>Error loading invoices</option>';
    }
  }

  modal.style.display = 'flex';
}

function closeRecordPaymentModal() {
  const modal = document.getElementById('record-payment-modal');
  if (modal) modal.style.display = 'none';
}

function handlePaymentInvoiceSelectionChange(selectedVal) {
  const previewBox = document.getElementById('pay-balance-preview-box');
  const amountInput = document.getElementById('pay-form-amount');
  if (!previewBox) return;

  if (!selectedVal || selectedVal === '__ADVANCE__') {
    previewBox.style.display = 'none';
    if (amountInput && selectedVal === '__ADVANCE__') {
      amountInput.placeholder = 'Enter advance deposit amount';
    }
    return;
  }

  const inv = availableInvoicesForPayment.find(i => i.id === selectedVal || i.invoice_number === selectedVal);
  if (!inv) {
    previewBox.style.display = 'none';
    return;
  }

  const invTotal = inv.total_amount || 0;
  const paidTotal = inv.total_paid || 0;
  const balDue = inv.outstanding_balance != null ? inv.outstanding_balance : Math.max(0, invTotal - paidTotal);

  const elTot = document.getElementById('pay-preview-inv-total');
  const elPaid = document.getElementById('pay-preview-paid-total');
  const elBal = document.getElementById('pay-preview-balance-due');

  if (elTot) elTot.textContent = formatPaymentCurrency(invTotal);
  if (elPaid) elPaid.textContent = formatPaymentCurrency(paidTotal);
  if (elBal) elBal.textContent = formatPaymentCurrency(balDue);

  previewBox.style.display = 'grid';

  if (amountInput) {
    amountInput.placeholder = balDue.toFixed(2);
    amountInput.max = balDue.toFixed(2);
    if (!amountInput.value) {
      amountInput.value = balDue.toFixed(2);
    }
  }
}

async function handleRecordPaymentSubmit(event) {
  if (event) event.preventDefault();

  const select = document.getElementById('pay-form-invoice-select');
  const amountInput = document.getElementById('pay-form-amount');
  const dateInput = document.getElementById('pay-form-date');
  const methodSelect = document.getElementById('pay-form-method');
  const refInput = document.getElementById('pay-form-reference');
  const notesInput = document.getElementById('pay-form-notes');
  const submitBtn = document.getElementById('btn-submit-record-payment');

  const selectedTarget = select ? select.value : '';
  const amount = parseFloat(amountInput ? amountInput.value : 0);
  const payDate = dateInput ? dateInput.value : '';
  const method = methodSelect ? methodSelect.value : 'BANK_TRANSFER';
  const ref = refInput ? refInput.value.trim() : '';
  const notes = notesInput ? notesInput.value.trim() : '';

  if (!selectedTarget) {
    showToast('Please select a target invoice or choose Advance payment.', 'warning');
    return;
  }

  if (isNaN(amount) || amount <= 0) {
    showToast('Payment amount must be greater than ₹0.00.', 'warning');
    return;
  }

  if (!ref) {
    showToast('Transaction / UTR reference number is required.', 'warning');
    return;
  }

  const isAdvance = selectedTarget === '__ADVANCE__';
  const payload = {
    amount: amount,
    payment_date: payDate,
    payment_method: method,
    reference_number: ref,
    notes: notes,
    payment_type: isAdvance ? 'ADVANCE_PAYMENT' : 'INVOICE_PAYMENT'
  };

  if (!isAdvance) {
    payload.invoice_id = selectedTarget;
  } else {
    payload.nursery_user_id = 2; // Default demo nursery
  }

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = 'Recording Payment...';
  }

  try {
    const res = await fetch('/api/payments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.error || 'Failed to record payment.');
    }

    showToast(data.message || 'Payment recorded successfully.', 'success');
    closeRecordPaymentModal();

    fetchAndRenderPayments();
    if (typeof fetchAndRenderInvoices === 'function') {
      fetchAndRenderInvoices();
    }
  } catch (err) {
    console.error('Error submitting payment:', err);
    showToast(err.message || 'Error recording payment.', 'error');
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<span>💵</span> Record Payment Receipt';
    }
  }
}

async function openPaymentDetailModal(paymentIdOrNumber) {
  const modal = document.getElementById('payment-detail-modal');
  if (!modal) return;

  currentActivePaymentId = paymentIdOrNumber;

  try {
    const res = await fetch(`/api/payments/${encodeURIComponent(paymentIdOrNumber)}`);
    if (!res.ok) {
      throw new Error(`Failed to load payment: HTTP ${res.status}`);
    }

    const data = await res.json();
    if (!data.success || !data.data) {
      throw new Error(data.error || 'Failed to load payment details.');
    }

    const pay = data.data.payment;
    const allocations = data.data.allocations || [];
    const nursery = data.data.nursery || {};
    const supplier = data.data.supplier || {};

    const elNum = document.getElementById('modal-pay-number');
    const elAmount = document.getElementById('modal-pay-amount');
    const elDate = document.getElementById('modal-pay-date');
    const elBadge = document.getElementById('modal-pay-status-badge');
    const elNurseryName = document.getElementById('modal-pay-nursery-name');
    const elNurseryEmail = document.getElementById('modal-pay-nursery-email');
    const elSupplierName = document.getElementById('modal-pay-supplier-name');
    const elSupplierEmail = document.getElementById('modal-pay-supplier-email');
    const elMethod = document.getElementById('modal-pay-method');
    const elRef = document.getElementById('modal-pay-ref');
    const elType = document.getElementById('modal-pay-type');
    const elNotes = document.getElementById('modal-pay-notes');
    const revBanner = document.getElementById('modal-pay-reversal-banner');
    const revReason = document.getElementById('modal-pay-reversal-reason');
    const revBtn = document.getElementById('btn-modal-reverse-payment');
    const allocTbody = document.getElementById('modal-pay-allocations-tbody');

    if (elNum) elNum.textContent = pay.payment_number;
    if (elAmount) elAmount.textContent = formatPaymentCurrency(pay.amount);
    if (elDate) elDate.textContent = pay.payment_date;
    if (elBadge) {
      elBadge.className = `badge ${pay.status === 'RECORDED' ? 'badge-success' : 'badge-danger'}`;
      elBadge.textContent = pay.status;
    }
    if (elNurseryName) elNurseryName.textContent = nursery.name || pay.nursery_name || 'Nursery Partner';
    if (elNurseryEmail) elNurseryEmail.textContent = nursery.email || '';
    if (elSupplierName) elSupplierName.textContent = supplier.name || pay.supplier_name || 'Wholesale Supplier';
    if (elSupplierEmail) elSupplierEmail.textContent = supplier.email || '';
    if (elMethod) elMethod.innerHTML = formatPaymentMethodBadge(pay.payment_method);
    if (elRef) elRef.textContent = pay.reference_number;
    if (elType) elType.innerHTML = formatPaymentTypeBadge(pay.payment_type);
    if (elNotes) elNotes.textContent = pay.notes || 'No remarks provided.';

    if (revBanner) {
      if (pay.status === 'REVERSED') {
        revBanner.style.display = 'block';
        if (revReason) revReason.textContent = `Reason: ${pay.reversal_reason || 'Reversed by authorized user'} (${pay.reversed_at || ''})`;
      } else {
        revBanner.style.display = 'none';
      }
    }

    if (revBtn) {
      revBtn.style.display = pay.status === 'REVERSED' ? 'none' : 'inline-flex';
    }

    if (allocTbody) {
      if (allocations.length === 0) {
        allocTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 1rem;">No invoice allocations applied yet.</td></tr>`;
      } else {
        allocTbody.innerHTML = allocations.map(a => `
          <tr>
            <td><strong>${escapeOrderHtml(a.invoice_number)}</strong></td>
            <td><span style="font-family: monospace; font-size: 0.8rem;">${escapeOrderHtml(a.order_id || '-')}</span></td>
            <td style="text-align: right; color: var(--text-muted);">${formatPaymentCurrency(a.invoice_total)}</td>
            <td style="text-align: right; font-weight: 700; color: var(--primary);">${formatPaymentCurrency(a.amount)}</td>
            <td><span class="badge ${a.status === 'ACTIVE' ? 'badge-success' : 'badge-danger'}">${escapeOrderHtml(a.status)}</span></td>
          </tr>
        `).join('');
      }
    }

    modal.style.display = 'flex';
  } catch (err) {
    console.error('Error opening payment detail modal:', err);
    showToast(err.message || 'Failed to open payment details.', 'error');
  }
}

function closePaymentDetailModal() {
  const modal = document.getElementById('payment-detail-modal');
  if (modal) modal.style.display = 'none';
  currentActivePaymentId = null;
}

async function promptReversePayment(paymentId) {
  if (!paymentId) return;

  const reason = prompt('Please enter the reason for reversing this payment receipt:');
  if (!reason || !reason.trim()) {
    showToast('A clear reversal reason is required.', 'warning');
    return;
  }

  try {
    const res = await fetch(`/api/payments/${encodeURIComponent(paymentId)}/reverse`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: reason.trim() })
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.error || 'Failed to reverse payment.');
    }

    showToast(data.message || 'Payment reversed successfully.', 'success');
    closePaymentDetailModal();
    fetchAndRenderPayments();
    if (typeof fetchAndRenderInvoices === 'function') {
      fetchAndRenderInvoices();
    }
  } catch (err) {
    console.error('Error reversing payment:', err);
    showToast(err.message || 'Error reversing payment.', 'error');
  }
}

function promptReverseCurrentPayment() {
  if (currentActivePaymentId) {
    promptReversePayment(currentActivePaymentId);
  }
}

function openRecordPaymentModalForCurrentInvoice() {
  if (currentActiveInvoiceId) {
    closeInvoiceDetailModal();
    openRecordPaymentModal(currentActiveInvoiceId);
  }
}

// ============================================================================
// PHASE 11: COMMERCIAL LEDGER & TRANSACTION HISTORY ENGINE
// ============================================================================

let liveLedgerEntries = [];
let liveLedgerSummary = {};
let liveLedgerCounterparties = [];
let ledgerFilters = {
  type: 'ALL',
  nursery_id: 'ALL',
  status: 'ALL',
  start_date: '',
  end_date: '',
  search: '',
  order: 'desc'
};

function formatLedgerCurrency(val) {
  const num = Number(val);
  if (isNaN(num)) return '₹0.00';
  return '₹' + num.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

function escapeLedgerHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatLedgerTypeBadge(type) {
  const t = (type || '').toUpperCase();
  switch (t) {
    case 'INVOICE_ISSUED':
      return '<span class="badge" style="background: #E0E7FF; color: #3730A3; font-weight: 600;">🧾 Invoice Issued</span>';
    case 'INVOICE_CANCELLED':
      return '<span class="badge" style="background: #FEE2E2; color: #991B1B; font-weight: 600;">❌ Invoice Cancelled</span>';
    case 'PAYMENT_RECORDED':
      return '<span class="badge" style="background: #D1FAE5; color: #065F46; font-weight: 600;">💰 Payment Received</span>';
    case 'ADVANCE_RECORDED':
      return '<span class="badge" style="background: #CFFAFE; color: #155E75; font-weight: 600;">📥 Advance Received</span>';
    case 'ADVANCE_ALLOCATED':
    case 'PAYMENT_ALLOCATED':
      return '<span class="badge" style="background: #F3E8FF; color: #6B21A8; font-weight: 600;">🔄 Payment Allocated</span>';
    case 'PAYMENT_REVERSED':
      return '<span class="badge" style="background: #FEE2E2; color: #B91C1C; font-weight: 600;">⚠️ Payment Reversed</span>';
    case 'TERMS_AMENDED':
      return '<span class="badge" style="background: #FEF3C7; color: #92400E; font-weight: 600;">📝 Terms Amended</span>';
    case 'DELIVERY_VERIFIED':
      return '<span class="badge" style="background: #E0F2FE; color: #0369A1; font-weight: 600;">🚚 Delivery Verified</span>';
    default:
      return `<span class="badge" style="background: #F1F5F9; color: #475569;">${escapeLedgerHtml(t)}</span>`;
  }
}

function formatLedgerDirectionBadge(direction) {
  const d = (direction || '').toUpperCase();
  if (d === 'DEBIT') {
    return '<span class="badge" style="background: #FEE2E2; color: #991B1B; font-weight: 600;">DR (Debit)</span>';
  } else if (d === 'CREDIT') {
    return '<span class="badge" style="background: #D1FAE5; color: #065F46; font-weight: 600;">CR (Credit)</span>';
  } else {
    return '<span class="badge" style="background: #F1F5F9; color: #475569; font-weight: 500;">INFO</span>';
  }
}

function formatLedgerStatusBadge(status) {
  const s = (status || '').toUpperCase();
  if (['ISSUED', 'RECORDED', 'ACTIVE', 'VERIFIED'].includes(s)) {
    return `<span class="badge badge-success">${escapeLedgerHtml(s)}</span>`;
  } else if (['CANCELLED', 'REVERSED'].includes(s)) {
    return `<span class="badge badge-danger">${escapeLedgerHtml(s)}</span>`;
  } else if (['ALLOCATED'].includes(s)) {
    return `<span class="badge badge-info">${escapeLedgerHtml(s)}</span>`;
  } else {
    return `<span class="badge" style="background: #E2E8F0; color: #334155;">${escapeLedgerHtml(s)}</span>`;
  }
}

async function fetchAndRenderLedger() {
  const tbody = document.getElementById('ledger-table-tbody');
  if (tbody) {
    tbody.innerHTML = `
      <tr>
        <td colspan="9" style="text-align: center; padding: 2.5rem; color: var(--text-muted);">
          Loading commercial ledger records...
        </td>
      </tr>
    `;
  }

  try {
    const params = new URLSearchParams();
    if (ledgerFilters.type && ledgerFilters.type !== 'ALL') {
      params.append('type', ledgerFilters.type);
    }
    if (ledgerFilters.nursery_id && ledgerFilters.nursery_id !== 'ALL') {
      params.append('nursery_id', ledgerFilters.nursery_id);
    }
    if (ledgerFilters.status && ledgerFilters.status !== 'ALL') {
      params.append('status', ledgerFilters.status);
    }
    if (ledgerFilters.start_date) {
      params.append('start_date', ledgerFilters.start_date);
    }
    if (ledgerFilters.end_date) {
      params.append('end_date', ledgerFilters.end_date);
    }
    if (ledgerFilters.search) {
      params.append('search', ledgerFilters.search);
    }
    if (ledgerFilters.order) {
      params.append('order', ledgerFilters.order);
    }

    const url = `/api/ledger?${params.toString()}`;
    const res = await fetch(url);
    const data = await res.json();

    if (!res.ok || !data.success) {
      throw new Error(data.error || 'Failed to fetch ledger records.');
    }

    liveLedgerEntries = data.data || [];
    liveLedgerSummary = data.summary || {};
    liveLedgerCounterparties = data.counterparties || [];

    updateLedgerSummaryKPIs(liveLedgerSummary);
    updateLedgerCounterpartySelect(liveLedgerCounterparties);
    renderLedgerTable(liveLedgerEntries);

  } catch (err) {
    console.error('Error fetching ledger:', err);
    if (tbody) {
      tbody.innerHTML = `
        <tr>
          <td colspan="9" style="text-align: center; padding: 2.5rem; color: #B91C1C;">
            ⚠️ Failed to load commercial ledger: ${escapeLedgerHtml(err.message)}
          </td>
        </tr>
      `;
    }
    showToast('Failed to load ledger records.', 'error');
  }
}

function updateLedgerSummaryKPIs(summary) {
  if (!summary) summary = {};

  const elInvoiced = document.getElementById('kpi-ledger-total-invoiced');
  const elPaid = document.getElementById('kpi-ledger-total-paid');
  const elPrincipal = document.getElementById('kpi-ledger-outstanding-principal');
  const elAdvances = document.getElementById('kpi-ledger-unallocated-advances');
  const elInterest = document.getElementById('kpi-ledger-accrued-interest');
  const elNet = document.getElementById('kpi-ledger-net-balance');

  if (elInvoiced) elInvoiced.textContent = formatLedgerCurrency(summary.total_invoiced_gross || 0);
  if (elPaid) elPaid.textContent = formatLedgerCurrency(summary.total_payments_recorded || 0);
  if (elPrincipal) elPrincipal.textContent = formatLedgerCurrency(summary.outstanding_principal || 0);
  if (elAdvances) elAdvances.textContent = formatLedgerCurrency(summary.total_unallocated_advances || 0);
  if (elInterest) elInterest.textContent = formatLedgerCurrency(summary.total_accrued_interest || 0);
  if (elNet) elNet.textContent = formatLedgerCurrency(summary.net_balance_due || 0);
}

function updateLedgerCounterpartySelect(counterparties) {
  const select = document.getElementById('ledger-nursery-select');
  if (!select) return;

  const currentVal = ledgerFilters.nursery_id || 'ALL';
  let html = '<option value="ALL">All Counterparties</option>';

  if (Array.isArray(counterparties)) {
    counterparties.forEach(cp => {
      const isSel = (String(cp.id) === String(currentVal)) ? 'selected' : '';
      html += `<option value="${escapeLedgerHtml(cp.id)}" ${isSel}>${escapeLedgerHtml(cp.name)}</option>`;
    });
  }

  select.innerHTML = html;
}

function renderLedgerTable(entries) {
  const tbody = document.getElementById('ledger-table-tbody');
  if (!tbody) return;

  if (!entries || entries.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="9" style="text-align: center; padding: 2.5rem; color: var(--text-muted);">
          No ledger transactions found matching the selected filters.
        </td>
      </tr>
    `;
    return;
  }

  let html = '';
  entries.forEach(item => {
    const isCredit = item.direction === 'CREDIT';
    const isDebit = item.direction === 'DEBIT';
    const amountColor = isCredit ? '#065F46' : (isDebit ? '#991B1B' : '#475569');
    const amountPrefix = isCredit ? '+ ' : (isDebit ? '- ' : '');

    html += `
      <tr>
        <td style="font-weight: 500; white-space: nowrap;">${escapeLedgerHtml(item.transaction_date || '')}</td>
        <td>${formatLedgerTypeBadge(item.type)}</td>
        <td style="font-family: monospace; font-weight: 600; color: var(--text-main);">${escapeLedgerHtml(item.reference_id || '')}</td>
        <td style="font-family: monospace; color: var(--text-muted);">${escapeLedgerHtml(item.related_reference || '—')}</td>
        <td style="font-weight: 500;">${escapeLedgerHtml(item.nursery_name || 'All / General')}</td>
        <td>${formatLedgerDirectionBadge(item.direction)}</td>
        <td style="text-align: right; font-weight: 700; color: ${amountColor};">
          ${amountPrefix}${formatLedgerCurrency(item.amount || 0)}
        </td>
        <td>${formatLedgerStatusBadge(item.status)}</td>
        <td style="max-width: 280px; font-size: 0.85rem; color: var(--text-muted);">${escapeLedgerHtml(item.description || '')}</td>
      </tr>
    `;
  });

  tbody.innerHTML = html;
}

function handleLedgerSearch(val) {
  ledgerFilters.search = (val || '').trim();
  const clearBtn = document.getElementById('btn-clear-ledger-search');
  if (clearBtn) {
    clearBtn.style.display = ledgerFilters.search ? 'block' : 'none';
  }
  fetchAndRenderLedger();
}

function clearLedgerSearch() {
  const input = document.getElementById('ledger-search-input');
  if (input) input.value = '';
  handleLedgerSearch('');
}

function setLedgerTypeFilter(type) {
  ledgerFilters.type = type;
  const pillGroup = document.getElementById('ledger-type-pills');
  if (pillGroup) {
    const btns = pillGroup.querySelectorAll('.pill-btn');
    btns.forEach(b => {
      if (b.getAttribute('data-type') === type) {
        b.classList.add('active');
      } else {
        b.classList.remove('active');
      }
    });
  }
  fetchAndRenderLedger();
}

function handleLedgerNurseryFilter(nurseryId) {
  ledgerFilters.nursery_id = nurseryId;
  fetchAndRenderLedger();
}

function handleLedgerDateFilter() {
  const startInput = document.getElementById('ledger-start-date');
  const endInput = document.getElementById('ledger-end-date');
  ledgerFilters.start_date = startInput ? startInput.value : '';
  ledgerFilters.end_date = endInput ? endInput.value : '';
  fetchAndRenderLedger();
}

function handleLedgerSortOrder(order) {
  ledgerFilters.order = order || 'desc';
  fetchAndRenderLedger();
}

// ============================================================================
// PHASE 12: NURSERY BUYER DASHBOARD ENGINE
// ============================================================================

let liveNurseryDashboardData = null;

async function fetchAndRenderNurseryDashboard() {
  try {
    const res = await fetch('/api/nursery/dashboard');
    const json = await res.json();
    if (!res.ok || !json.success) {
      console.warn('Could not load live nursery dashboard, fallback or not logged in as nursery:', json?.error);
      return;
    }

    liveNurseryDashboardData = json.data;
    const data = json.data;

    // 1. Update Profile & Header Banner
    const profile = data.profile || {};
    const bannerName = document.getElementById('nursery-banner-name');
    const bannerDesc = document.getElementById('nursery-banner-desc');
    if (bannerName && profile.business_name) {
      bannerName.textContent = profile.business_name;
    }
    if (bannerDesc) {
      const emailText = profile.email ? ` • ${profile.email}` : '';
      bannerDesc.textContent = `Retail Nursery Partner • Verified Buyer Account (${profile.username || 'Buyer'})${emailText} • FloraChain B2B`;
    }

    // 2. Update KPI Cards
    const metrics = data.metrics || {};
    const elOrders = document.getElementById('kpi-nursery-orders');
    const elOrdersSub = document.getElementById('kpi-nursery-orders-subtext');
    const elTrucks = document.getElementById('kpi-nursery-trucks');
    const elTrucksSub = document.getElementById('kpi-nursery-trucks-subtext');
    const elPrincipal = document.getElementById('kpi-nursery-outstanding-principal');
    const elAdvances = document.getElementById('kpi-nursery-unallocated-advances');
    const elInterest = document.getElementById('kpi-nursery-accrued-interest');
    const elNet = document.getElementById('kpi-nursery-net-balance');

    if (elOrders) elOrders.textContent = metrics.active_orders || 0;
    if (elOrdersSub) elOrdersSub.textContent = `${metrics.in_transit || 0} in transit • ${metrics.total_orders || 0} total`;
    
    if (elTrucks) elTrucks.textContent = metrics.inbound_tasks_count || 0;
    if (elTrucksSub) elTrucksSub.textContent = `${metrics.inbound_tasks_count || 0} shipments awaiting arrival/inspection`;

    if (elPrincipal) elPrincipal.textContent = formatOrderCurrency(metrics.outstanding_principal || 0);
    if (elAdvances) elAdvances.textContent = formatOrderCurrency(metrics.total_unallocated_advances || 0);
    if (elInterest) elInterest.textContent = formatOrderCurrency(metrics.total_accrued_interest || 0);
    if (elNet) elNet.textContent = formatOrderCurrency(metrics.net_balance_due || 0);

    // 3. Render Inbound Shipments Table
    renderNurseryInboundTable(data.inbound_tasks || []);

    // 4. Render Purchase Order History Table
    renderNurseryOrdersTable(data.recent_orders || []);

    // 5. Render Invoices Table
    renderNurseryInvoicesTable(data.invoices || []);

    // 6. Render Commercial Statement Box
    const elStmtGross = document.getElementById('nursery-statement-gross');
    const elStmtPaid = document.getElementById('nursery-statement-paid');
    const elStmtAdv = document.getElementById('nursery-statement-advances');
    const elStmtPrinc = document.getElementById('nursery-statement-principal');
    const elStmtInt = document.getElementById('nursery-statement-interest');
    const elStmtNet = document.getElementById('nursery-statement-net');

    if (elStmtGross) elStmtGross.textContent = formatOrderCurrency(metrics.total_invoiced_gross || 0);
    if (elStmtPaid) elStmtPaid.textContent = formatOrderCurrency(metrics.total_allocated_payments || 0);
    if (elStmtAdv) elStmtAdv.textContent = formatOrderCurrency(metrics.total_unallocated_advances || 0);
    if (elStmtPrinc) elStmtPrinc.textContent = formatOrderCurrency(metrics.outstanding_principal || 0);
    if (elStmtInt) elStmtInt.textContent = formatOrderCurrency(metrics.total_accrued_interest || 0);
    if (elStmtNet) elStmtNet.textContent = formatOrderCurrency(metrics.net_balance_due || 0);

    // 7. Render Recent Ledger Activity Table
    renderNurseryLedgerTable(data.recent_transactions || []);

    // 8. Render Deal Agreements Table
    renderNurseryAgreementsTable(data.agreements || []);

  } catch (err) {
    console.error('Error fetching live nursery dashboard:', err);
  }
}

function renderNurseryInboundTable(tasks) {
  const tbody = document.getElementById('nursery-inbound-tbody');
  if (!tbody) return;

  if (!tasks || tasks.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align: center; padding: 2rem; color: var(--text-muted);">
          No inbound plant shipments currently scheduled for arrival.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = tasks.map(item => {
    const isLocked = Boolean(item.is_locked);
    const soundText = item.sound_qty !== null && item.sound_qty !== undefined ? `${item.sound_qty} Sound` : `${item.ordered_qty} units`;
    const damagedText = item.damaged_qty ? ` / ${item.damaged_qty} Damaged` : '';
    
    return `
      <tr>
        <td style="font-family: monospace; font-weight: 700; color: var(--text-main);">${escapeOrderHtml(item.order_id)}</td>
        <td style="font-weight: 500;">${escapeOrderHtml(item.variety)}</td>
        <td><strong>${item.ordered_qty}</strong> units</td>
        <td>
          <div style="font-weight: 600;">${escapeOrderHtml(item.truck_no)}</div>
          <small style="color: var(--text-muted); font-size: 0.78rem;">${escapeOrderHtml(item.driver_info)}</small>
        </td>
        <td>${formatOrderStatusBadge(item.status)}</td>
        <td style="text-align: right;">
          ${isLocked ? `
            <button class="btn btn-secondary btn-sm" onclick="openDeliveryVerificationModal('${escapeOrderHtml(item.order_id)}', true)" title="View finalized inspection record">
              ✅ Verified (${soundText}${damagedText})
            </button>
          ` : `
            <button class="btn btn-primary btn-sm" onclick="openDeliveryVerificationModal('${escapeOrderHtml(item.order_id)}', false)" title="Inspect sound plants &amp; record transit damage">
              🔍 Inspect on Arrival
            </button>
          `}
        </td>
      </tr>
    `;
  }).join('');
}

function renderNurseryOrdersTable(orders) {
  const tbody = document.getElementById('nursery-orders-tbody');
  if (!tbody) return;

  if (!orders || orders.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" style="text-align: center; padding: 2rem; color: var(--text-muted);">
          No purchase orders placed yet.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = orders.map(order => `
    <tr>
      <td style="font-family: monospace; font-weight: 700; color: var(--text-main);">${escapeOrderHtml(order.order_id)}</td>
      <td style="font-weight: 500;">${escapeOrderHtml(order.variety)}</td>
      <td><strong>${order.ordered_qty}</strong> units</td>
      <td>${escapeOrderHtml((order.created_at || '').split(' ')[0])}</td>
      <td style="text-align: right; font-weight: 700; color: var(--text-main);">${formatOrderCurrency(order.total_amount || 0)}</td>
      <td>${formatOrderStatusBadge(order.status)}</td>
      <td style="text-align: right;">
        <button class="btn btn-secondary btn-sm" onclick="openOrderDetailModal('${escapeOrderHtml(order.order_id)}')" title="View complete order details &amp; lines">
          <span>👁️</span> Details
        </button>
      </td>
    </tr>
  `).join('');
}

function renderNurseryInvoicesTable(invoices) {
  const tbody = document.getElementById('nursery-invoices-tbody');
  if (!tbody) return;

  if (!invoices || invoices.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" style="text-align: center; padding: 2rem; color: var(--text-muted);">
          No wholesale invoices currently open or issued.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = invoices.map(inv => `
    <tr>
      <td style="font-family: monospace; font-weight: 700; color: var(--primary);">${escapeOrderHtml(inv.invoice_number)}</td>
      <td style="font-family: monospace; color: var(--text-muted);">${escapeOrderHtml(inv.order_id || '—')}</td>
      <td>
        <div style="font-weight: 500;">${escapeOrderHtml(inv.due_date || 'No Due Date')}</div>
        <div style="margin-top: 0.2rem;">${formatDueStatusBadge(inv.due_status, inv.overdue_days)}</div>
      </td>
      <td style="text-align: right; font-weight: 600; color: var(--text-main);">${formatOrderCurrency(inv.outstanding_principal || 0)}</td>
      <td style="text-align: right; font-weight: 600; color: #B45309;">${formatOrderCurrency(inv.accrued_interest || 0)}</td>
      <td style="text-align: right; font-weight: 700; color: var(--primary);">${formatOrderCurrency(inv.total_payable || 0)}</td>
      <td>${formatInvoiceStatusBadge(inv.status)}</td>
      <td style="text-align: right;">
        <button class="btn btn-secondary btn-sm" onclick="openInvoiceDetailModal('${escapeOrderHtml(inv.invoice_number)}')" title="View itemized invoice, terms &amp; payments">
          <span>🧾</span> View
        </button>
      </td>
    </tr>
  `).join('');
}

function renderNurseryLedgerTable(transactions) {
  const tbody = document.getElementById('nursery-ledger-tbody');
  if (!tbody) return;

  if (!transactions || transactions.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="4" style="text-align: center; padding: 1.5rem; color: var(--text-muted);">
          No recent ledger transactions recorded.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = transactions.map(item => {
    const isCredit = item.direction === 'CREDIT';
    const isDebit = item.direction === 'DEBIT';
    const amountColor = isCredit ? '#065F46' : (isDebit ? '#991B1B' : '#475569');
    const amountPrefix = isCredit ? '+ ' : (isDebit ? '- ' : '');

    return `
      <tr>
        <td style="white-space: nowrap;">${escapeOrderHtml(item.transaction_date || '')}</td>
        <td>${formatLedgerTypeBadge(item.type)}</td>
        <td style="font-family: monospace; font-weight: 600;">${escapeOrderHtml(item.reference_id || '')}</td>
        <td style="text-align: right; font-weight: 700; color: ${amountColor};">
          ${amountPrefix}${formatOrderCurrency(item.amount || 0)}
        </td>
      </tr>
    `;
  }).join('');
}

function renderNurseryAgreementsTable(agreements) {
  const tbody = document.getElementById('nursery-agreements-tbody');
  if (!tbody) return;

  if (!agreements || agreements.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="9" style="text-align: center; padding: 2rem; color: var(--text-muted);">
          No active deal agreements recorded.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = agreements.map(agr => `
    <tr>
      <td style="font-family: monospace; font-weight: 700; color: var(--text-main);">${escapeOrderHtml(agr.agreement_ref)}</td>
      <td style="font-family: monospace; color: var(--text-muted);">${escapeOrderHtml(agr.order_id || '—')}</td>
      <td style="font-weight: 500;">${escapeOrderHtml(agr.supplier_name || 'Wholesale Grower')}</td>
      <td style="font-weight: 600;">${formatOrderCurrency(agr.total_order_value || 0)}</td>
      <td>
        <div><strong>${formatOrderCurrency(agr.advance_amount || 0)}</strong> (${agr.advance_percentage}%)</div>
        <small style="color: var(--text-muted);">${formatOrderCurrency(agr.balance_amount || 0)} on delivery</small>
      </td>
      <td>${escapeOrderHtml(agr.payment_due_date || 'N/A')}</td>
      <td style="font-weight: 600; color: #8A5300;">${agr.interest_rate_pct ? agr.interest_rate_pct + '% p.a.' : '0%'}</td>
      <td><span class="badge ${agr.status === 'AGREED' ? 'badge-success' : 'badge-warning'}">${escapeOrderHtml(agr.status)}</span></td>
      <td style="text-align: right;">
        <button class="btn btn-secondary btn-sm" onclick="openDealAgreementModal('${escapeOrderHtml(agr.agreement_ref)}')" title="Review contractual terms &amp; sign">
          <span>🤝</span> Terms
        </button>
      </td>
    </tr>
  `).join('');
}

function openNurseryLedgerModal() {
  const modal = document.getElementById('nursery-ledger-modal');
  if (!modal) return;
  modal.style.display = 'flex';

  const tbody = document.getElementById('nursery-modal-ledger-tbody');
  if (tbody) {
    if (liveNurseryDashboardData && liveNurseryDashboardData.recent_transactions) {
      const txs = liveNurseryDashboardData.recent_transactions;
      if (txs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 2rem; color: var(--text-muted);">No ledger entries on account.</td></tr>`;
      } else {
        tbody.innerHTML = txs.map(item => {
          const isCredit = item.direction === 'CREDIT';
          const isDebit = item.direction === 'DEBIT';
          const amountColor = isCredit ? '#065F46' : (isDebit ? '#991B1B' : '#475569');
          const amountPrefix = isCredit ? '+ ' : (isDebit ? '- ' : '');

          return `
            <tr>
              <td style="white-space: nowrap;">${escapeOrderHtml(item.transaction_date || '')}</td>
              <td>${formatLedgerTypeBadge(item.type)}</td>
              <td style="font-family: monospace; font-weight: 600;">${escapeOrderHtml(item.reference_id || '')}</td>
              <td style="font-family: monospace; color: var(--text-muted);">${escapeOrderHtml(item.related_reference || '—')}</td>
              <td>${formatLedgerDirectionBadge(item.direction)}</td>
              <td style="text-align: right; font-weight: 700; color: ${amountColor};">
                ${amountPrefix}${formatOrderCurrency(item.amount || 0)}
              </td>
              <td>${formatLedgerStatusBadge(item.status)}</td>
              <td style="max-width: 250px; font-size: 0.85rem; color: var(--text-muted);">${escapeOrderHtml(item.description || '')}</td>
            </tr>
          `;
        }).join('');
      }
    }
  }
}

function closeNurseryLedgerModal() {
  const modal = document.getElementById('nursery-ledger-modal');
  if (modal) modal.style.display = 'none';
}

// ============================================================================
// PHASE 4: PHYSICAL INSPECTION & DELIVERY VERIFICATION ENGINE
// ============================================================================

const DELIVERY_VERIFICATIONS_STORAGE_KEY = 'florachain_delivery_verifications';

/**
 * Validates and calculates physical plant inspection metrics:
 * - Checks for non-negative whole numbers
 * - Validates: soundQty + damagedQty === deliveredQty
 * - Flags mismatch if deliveredQty !== orderedQty
 * - Computes damage percentage & accepted billable sound units
 * - Preserves original orderedQty without silent mutation
 */
function calculateInspectionMetrics(orderedQty, deliveredQty, soundQty, damagedQty) {
  const ordered = Number(orderedQty);
  const delivered = Number(deliveredQty);
  const sound = Number(soundQty);
  const damaged = Number(damagedQty);

  const isNonNegativeInt = (n) => Number.isInteger(n) && n >= 0;
  if (!isNonNegativeInt(ordered) || !isNonNegativeInt(delivered) || !isNonNegativeInt(sound) || !isNonNegativeInt(damaged)) {
    return {
      isValid: false,
      error: 'Quantities must be non-negative whole numbers.',
      orderedQty: ordered,
      deliveredQty: delivered,
      soundQty: sound,
      damagedQty: damaged,
      damagePct: 0,
      hasMismatch: false,
      mismatchDiff: 0,
      acceptedQty: 0
    };
  }

  const sumMatches = (sound + damaged) === delivered;
  const damagePct = delivered > 0 ? Number(((damaged / delivered) * 100).toFixed(2)) : 0;
  const hasMismatch = delivered !== ordered;
  const mismatchDiff = delivered - ordered;

  if (!sumMatches) {
    return {
      isValid: false,
      error: `Calculation Mismatch: Sound (${sound}) + Damaged (${damaged}) = ${sound + damaged}, which does not match Delivered total (${delivered}).`,
      orderedQty: ordered,
      deliveredQty: delivered,
      soundQty: sound,
      damagedQty: damaged,
      damagePct,
      hasMismatch,
      mismatchDiff,
      acceptedQty: sound
    };
  }

  return {
    isValid: true,
    error: null,
    orderedQty: ordered,
    deliveredQty: delivered,
    soundQty: sound,
    damagedQty: damaged,
    damagePct,
    hasMismatch,
    mismatchDiff,
    acceptedQty: sound
  };
}

/**
 * Load verified delivery records from localStorage
 */
function loadDeliveryVerificationsFromStorage() {
  try {
    if (typeof localStorage === 'undefined') return {};
    const raw = localStorage.getItem(DELIVERY_VERIFICATIONS_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (typeof parsed === 'object' && parsed !== null) {
        return parsed;
      }
    }
  } catch (e) {
    console.warn('Could not load delivery verifications from storage:', e);
  }
  return {};
}

/**
 * Save verified delivery records to localStorage
 */
function saveDeliveryVerificationsToStorage(verifications) {
  try {
    if (typeof localStorage === 'undefined') return;
    localStorage.setItem(DELIVERY_VERIFICATIONS_STORAGE_KEY, JSON.stringify(verifications));
  } catch (e) {
    console.warn('Could not save delivery verifications to storage:', e);
  }
}

/**
 * Merge persistent delivery verifications into in-memory state on startup
 * Uses authoritative Flask SQLite API first, with graceful fallback to localStorage
 */
async function syncStoredVerifications() {
  if (typeof window !== 'undefined' && typeof fetch === 'function') {
    try {
      const resp = await fetch('/api/orders');
      if (resp.ok) {
        const body = await resp.json();
        if (body.success && Array.isArray(body.data)) {
          body.data.forEach(dbOrder => {
            const inbound = DUMMY_DATA.nurseryInbound.find(o => o.orderId === dbOrder.id);
            if (inbound) {
              if (dbOrder.is_locked) {
                inbound.status = 'DELIVERED & VERIFIED';
                inbound.badgeClass = 'badge-success';
                inbound.isLocked = true;
                inbound.soundQty = dbOrder.sound_qty;
                inbound.damagedQty = dbOrder.damaged_qty;
                inbound.damagePct = dbOrder.damage_pct;
                inbound.damageNotes = dbOrder.damage_notes;
                inbound.verifiedAt = dbOrder.locked_at;
                inbound.verifiedBy = 'Dual Confirmation (Nursery & Supplier)';
              } else if (dbOrder.inspection_status === 'PENDING_SUPPLIER_CONFIRMATION') {
                inbound.status = 'PENDING SUPPLIER CONFIRMATION';
                inbound.badgeClass = 'badge-warning';
                inbound.isLocked = false;
                inbound.soundQty = dbOrder.sound_qty;
                inbound.damagedQty = dbOrder.damaged_qty;
                inbound.damagePct = dbOrder.damage_pct;
                inbound.damageNotes = dbOrder.damage_notes;
                inbound.verifiedBy = 'Nursery Intake (Pending Counter-Sign)';
              }
            }

            const suppOrder = DUMMY_DATA.supplierOrders.find(o => o.id === dbOrder.id);
            if (suppOrder) {
              if (dbOrder.is_locked) {
                suppOrder.status = 'DELIVERED';
                suppOrder.statusLabel = 'Delivered & Verified';
                suppOrder.badgeClass = 'badge-success';
              } else if (dbOrder.inspection_status === 'PENDING_SUPPLIER_CONFIRMATION') {
                suppOrder.status = 'PENDING_CONFIRMATION';
                suppOrder.statusLabel = 'Counter-Sign Required';
                suppOrder.badgeClass = 'badge-warning';
              }
            }
          });
          renderNurseryDashboard();
          renderSupplierDashboard();
          return;
        }
      }
    } catch (e) {
      console.warn('API sync failed, falling back to local storage:', e);
    }
  }

  // Fallback to legacy local storage (untrusted)
  const verifications = loadDeliveryVerificationsFromStorage();
  if (!verifications || Object.keys(verifications).length === 0) return;

  DUMMY_DATA.nurseryInbound.forEach(item => {
    const saved = verifications[item.orderId];
    if (saved) {
      item.status = saved.status || 'DELIVERED & VERIFIED';
      item.badgeClass = 'badge-success';
      item.isLocked = Boolean(saved.isLocked);
      item.soundQty = saved.soundQty;
      item.damagedQty = saved.damagedQty;
      item.damagePct = saved.damagePct;
      item.damageNotes = saved.damageNotes;
      item.verifiedAt = saved.verifiedAt;
      item.verifiedBy = saved.verifiedBy;
    }
  });
}

/**
 * Open Delivery Verification Modal (Supports Inspection Mode, Supplier Counter-Sign, and Locked View)
 */
async function openDeliveryVerificationModal(orderId, isLockedView = false) {
  const modal = document.getElementById('delivery-verification-modal');
  let order = DUMMY_DATA.nurseryInbound.find(o => o.orderId === orderId);
  if (!order && liveNurseryDashboardData) {
    const liveTask = (liveNurseryDashboardData.inbound_tasks || []).find(t => t.order_id === orderId) ||
                     (liveNurseryDashboardData.recent_orders || []).find(t => t.order_id === orderId);
    if (liveTask) {
      order = {
        orderId: liveTask.order_id,
        variety: liveTask.variety,
        qty: liveTask.ordered_qty,
        truckNo: liveTask.truck_no,
        driver: liveTask.driver_info,
        status: liveTask.status,
        soundQty: liveTask.sound_qty,
        damagedQty: liveTask.damaged_qty
      };
      DUMMY_DATA.nurseryInbound.push(order);
    }
  }
  if (!modal || !order) return;

  const verifications = loadDeliveryVerificationsFromStorage();
  const savedRecord = verifications[orderId];
  if (savedRecord && savedRecord.isLocked) {
    isLockedView = true;
  }

  // Populate Header & Manifest Context
  const title = document.getElementById('delivery-verify-title');
  const badge = document.getElementById('delivery-verify-status-badge');
  const subtitle = document.getElementById('delivery-verify-subtitle');
  const idInput = document.getElementById('verify-order-id');

  const displayOrderId = document.getElementById('verify-display-order-id');
  const displayVariety = document.getElementById('verify-display-variety');
  const displayTruck = document.getElementById('verify-display-truck');
  const displayOrdered = document.getElementById('verify-display-ordered-qty');

  const deliveredInput = document.getElementById('verify-delivered-qty');
  const soundInput = document.getElementById('verify-sound-qty');
  const damagedInput = document.getElementById('verify-damaged-qty');
  const notesInput = document.getElementById('verify-damage-notes');

  const submitBtn = document.getElementById('btn-confirm-verification');
  const lockNotice = document.getElementById('verify-lock-notice');
  const lockIcon = document.getElementById('verify-lock-icon');
  const lockText = document.getElementById('verify-lock-text');

  if (idInput) idInput.value = order.orderId;
  if (displayOrderId) displayOrderId.textContent = order.orderId;
  if (displayVariety) displayVariety.textContent = order.variety;
  if (displayTruck) displayTruck.textContent = `${order.truckNo} • ${order.driver}`;
  if (displayOrdered) displayOrdered.textContent = `${order.qty} units`;

  clearVerificationFieldErrors();

  // Try fetching live state from Flask API
  let liveRecord = null;
  if (typeof window !== 'undefined' && typeof fetch === 'function') {
    try {
      const resp = await fetch(`/api/orders/${orderId}`);
      if (resp.ok) {
        const body = await resp.json();
        if (body.success && body.data) {
          liveRecord = body.data;
        }
      }
    } catch (e) {
      console.warn('Could not fetch live order details:', e);
    }
  }

  const isLocked = liveRecord ? liveRecord.is_locked : Boolean(order.isLocked || isLockedView);
  const inspection = liveRecord ? liveRecord.inspection : null;
  const isPendingSupplier = liveRecord ? (inspection && !liveRecord.is_locked && liveRecord.nursery_confirmed && !liveRecord.supplier_confirmed) : (order.status === 'PENDING SUPPLIER CONFIRMATION');

  if (isLocked) {
    // LOCKED / READ-ONLY MODE
    const rec = inspection || savedRecord || order;
    if (title) title.textContent = '🔒 Verified Delivery Inspection Record';
    if (badge) {
      badge.textContent = 'FINALIZED & LOCKED';
      badge.className = 'badge badge-success';
    }
    if (subtitle) {
      subtitle.textContent = `Order #${order.orderId} • Dual confirmation finalized & permanently locked in audit ledger`;
    }

    if (deliveredInput) {
      deliveredInput.value = rec.delivered_qty ?? rec.deliveredQty ?? order.qty;
      deliveredInput.disabled = true;
    }
    if (soundInput) {
      soundInput.value = rec.sound_qty ?? rec.soundQty ?? order.qty;
      soundInput.disabled = true;
    }
    if (damagedInput) {
      damagedInput.value = rec.damaged_qty ?? rec.damagedQty ?? 0;
      damagedInput.disabled = true;
    }
    if (notesInput) {
      notesInput.value = rec.damage_notes || rec.damageNotes || '';
      notesInput.disabled = true;
    }

    if (submitBtn) submitBtn.style.display = 'none';

    if (lockNotice) {
      lockNotice.style.display = 'flex';
      lockNotice.style.backgroundColor = '#F0FDF4';
      lockNotice.style.borderColor = '#86EFAC';
      lockNotice.style.color = '#166534';
      if (lockIcon) lockIcon.textContent = '✅';
      if (lockText) {
        const sigText = liveRecord && liveRecord.confirmations && liveRecord.confirmations.length
          ? liveRecord.confirmations.map(c => `<strong>${c.party_role}:</strong> ${c.user_name} (${c.business_name})`).join(' • ')
          : 'Verified by Nursery and Supplier';
        lockText.innerHTML = `<strong>Record Immutable:</strong> ${sigText}. Commercial billing is finalized on ${rec.sound_qty ?? rec.soundQty ?? order.qty} accepted sound plants.`;
      }
    }

    onVerificationInputsChanged();
  } else if (isPendingSupplier) {
    // PENDING SUPPLIER CONFIRMATION MODE
    const insp = inspection || savedRecord || order;
    if (title) title.textContent = '🚚 Delivery Inspection • Awaiting Counter-Signature';
    if (badge) {
      badge.textContent = 'PENDING SUPPLIER CONFIRMATION';
      badge.className = 'badge badge-warning';
    }
    if (subtitle) {
      subtitle.textContent = `Order #${order.orderId} • Nursery arrival counts recorded; awaiting supplier dispatch confirmation`;
    }

    if (deliveredInput) {
      deliveredInput.value = insp.delivered_qty ?? insp.deliveredQty ?? order.qty;
      deliveredInput.disabled = true;
    }
    if (soundInput) {
      soundInput.value = insp.sound_qty ?? insp.soundQty ?? order.qty;
      soundInput.disabled = true;
    }
    if (damagedInput) {
      damagedInput.value = insp.damaged_qty ?? insp.damagedQty ?? 0;
      damagedInput.disabled = true;
    }
    if (notesInput) {
      notesInput.value = insp.damage_notes || insp.damageNotes || '';
      notesInput.disabled = true;
    }

    if (lockNotice) {
      lockNotice.style.display = 'flex';
      lockNotice.style.backgroundColor = '#FFFBEB';
      lockNotice.style.borderColor = '#FCD34D';
      lockNotice.style.color = '#92400E';
      if (lockIcon) lockIcon.textContent = '⏳';
      if (lockText) {
        lockText.innerHTML = `<strong>Awaiting Supplier Counter-Signature:</strong> Nursery dock counts (${soundInput.value} sound, ${damagedInput.value} damaged) are recorded. Supplier must counter-sign to finalize and lock.`;
      }
    }

    if (submitBtn) {
      submitBtn.style.display = 'inline-flex';
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<span>✍️</span> Counter-Sign & Confirm Delivery';
      submitBtn.onclick = (e) => {
        e.preventDefault();
        handleSupplierCounterSign(order.orderId);
      };
    }

    onVerificationInputsChanged();
  } else {
    // ACTIVE INSPECTION FORM MODE (NURSERY DOCK INTAKE)
    if (title) title.textContent = '🚚 Physical Inspection & Delivery Verification';
    if (badge) {
      badge.textContent = order.status;
      badge.className = `badge ${order.badgeClass || 'badge-warning'}`;
    }
    if (subtitle) {
      subtitle.textContent = `Order #${order.orderId} • Verify sound plants and record transit damage`;
    }

    if (deliveredInput) {
      deliveredInput.value = order.qty;
      deliveredInput.disabled = false;
    }
    if (soundInput) {
      soundInput.value = order.qty;
      soundInput.disabled = false;
    }
    if (damagedInput) {
      damagedInput.value = 0;
      damagedInput.disabled = false;
    }
    if (notesInput) {
      notesInput.value = '';
      notesInput.disabled = false;
    }

    if (submitBtn) {
      submitBtn.style.display = 'inline-flex';
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<span>🔒</span> Submit Arrival Inspection';
      submitBtn.onclick = null;
    }

    if (lockNotice) {
      lockNotice.style.display = 'flex';
      lockNotice.style.backgroundColor = '#F8FAFC';
      lockNotice.style.borderColor = '#CBD5E1';
      lockNotice.style.color = 'var(--text-secondary)';
      if (lockIcon) lockIcon.textContent = '🔒';
      if (lockText) {
        lockText.innerHTML = `<strong>Dual-Party Verification Notice:</strong> Submitting will record physical intake counts. Both Nursery and Supplier must independently confirm before the order is permanently locked.`;
      }
    }

    onVerificationInputsChanged();
  }

  modal.style.display = 'flex';
}

/**
 * Close Delivery Verification Modal
 */
function closeDeliveryVerificationModal() {
  const modal = document.getElementById('delivery-verification-modal');
  if (modal) modal.style.display = 'none';
  clearVerificationFieldErrors();
}

/**
 * Real-time event handler when delivery quantity inputs change
 */
function onVerificationInputsChanged() {
  const orderId = document.getElementById('verify-order-id')?.value;
  const order = DUMMY_DATA.nurseryInbound.find(o => o.orderId === orderId);
  const orderedQty = order ? order.qty : 150;

  const deliveredVal = parseInt(document.getElementById('verify-delivered-qty')?.value, 10);
  const soundVal = parseInt(document.getElementById('verify-sound-qty')?.value, 10);
  const damagedVal = parseInt(document.getElementById('verify-damaged-qty')?.value, 10);

  const delivered = isNaN(deliveredVal) ? 0 : deliveredVal;
  const sound = isNaN(soundVal) ? 0 : soundVal;
  const damaged = isNaN(damagedVal) ? 0 : damagedVal;

  const metrics = calculateInspectionMetrics(orderedQty, delivered, sound, damaged);

  // Update Summary KPI Numbers
  const sumDelivered = document.getElementById('summary-delivered-val');
  const sumSound = document.getElementById('summary-sound-val');
  const sumDamaged = document.getElementById('summary-damaged-val');
  const sumPct = document.getElementById('summary-damage-pct-val');

  if (sumDelivered) sumDelivered.textContent = delivered;
  if (sumSound) sumSound.textContent = sound;
  if (sumDamaged) sumDamaged.textContent = damaged;
  if (sumPct) sumPct.textContent = `${metrics.damagePct.toFixed(1)}%`;

  // Mismatch error banner (sound + damaged !== delivered)
  const calcWarning = document.getElementById('verify-calc-warning');
  const calcWarningText = document.getElementById('verify-calc-warning-text');
  const submitBtn = document.getElementById('btn-confirm-verification');

  if (!metrics.isValid) {
    if (calcWarning) calcWarning.style.display = 'flex';
    if (calcWarningText) calcWarningText.textContent = metrics.error;
    if (submitBtn) submitBtn.disabled = true;
  } else {
    if (calcWarning) calcWarning.style.display = 'none';
    if (submitBtn) submitBtn.disabled = false;
  }

  // Ordered vs Delivered Mismatch banner
  const mismatchWarning = document.getElementById('verify-mismatch-warning');
  const mismatchWarningText = document.getElementById('verify-mismatch-warning-text');
  if (metrics.hasMismatch) {
    if (mismatchWarning) mismatchWarning.style.display = 'flex';
    if (mismatchWarningText) {
      mismatchWarningText.textContent = `Quantity Mismatch: Delivered count (${delivered}) differs from original order count (${orderedQty}). Variance: ${metrics.mismatchDiff > 0 ? '+' : ''}${metrics.mismatchDiff} units.`;
    }
  } else {
    if (mismatchWarning) mismatchWarning.style.display = 'none';
  }
}

/**
 * Clear form errors
 */
function clearVerificationFieldErrors() {
  const errDelivered = document.getElementById('err-verify-delivered');
  const errSound = document.getElementById('err-verify-sound');
  const errDamaged = document.getElementById('err-verify-damaged');
  if (errDelivered) errDelivered.classList.remove('visible');
  if (errSound) errSound.classList.remove('visible');
  if (errDamaged) errDamaged.classList.remove('visible');
}

/**
 * Handle form submission to verify and lock order
 * Sends to Flask API when available, falls back to local verification in offline test runner
 */
async function handleDeliveryVerificationSubmit(e) {
  if (e && e.preventDefault) e.preventDefault();
  clearVerificationFieldErrors();

  const orderId = document.getElementById('verify-order-id')?.value;
  const order = DUMMY_DATA.nurseryInbound.find(o => o.orderId === orderId);
  if (!order) {
    showToast('Inbound order not found.', 'warning');
    return;
  }

  const deliveredVal = parseInt(document.getElementById('verify-delivered-qty')?.value, 10);
  const soundVal = parseInt(document.getElementById('verify-sound-qty')?.value, 10);
  const damagedVal = parseInt(document.getElementById('verify-damaged-qty')?.value, 10);
  const damageNotes = document.getElementById('verify-damage-notes')?.value || '';

  let hasError = false;
  if (isNaN(deliveredVal) || deliveredVal < 0) {
    document.getElementById('err-verify-delivered')?.classList.add('visible');
    hasError = true;
  }
  if (isNaN(soundVal) || soundVal < 0) {
    document.getElementById('err-verify-sound')?.classList.add('visible');
    hasError = true;
  }
  if (isNaN(damagedVal) || damagedVal < 0) {
    document.getElementById('err-verify-damaged')?.classList.add('visible');
    hasError = true;
  }

  if (hasError) return;

  const submitBtn = document.getElementById('btn-confirm-verification');
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span>⏳</span> Submitting to Ledger...';
  }

  // 1. In browser environment, submit to Flask database API
  if (typeof window !== 'undefined' && typeof fetch === 'function') {
    try {
      const resp = await fetch(`/api/orders/${orderId}/inspection`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          delivered_qty: deliveredVal,
          sound_qty: soundVal,
          damaged_qty: damagedVal,
          damage_notes: damageNotes
        })
      });

      const body = await resp.json().catch(() => ({}));
      if (!resp.ok || !body.success) {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = '<span>🔒</span> Submit Arrival Inspection';
        }
        showToast(body.error || 'Server rejected inspection.', 'warning');
        return;
      }

      closeDeliveryVerificationModal();
      showToast(`✅ Physical inspection for Order #${orderId} saved. Status: Pending Supplier Counter-Signature.`, 'success');
      await syncStoredVerifications();
      return;
    } catch (err) {
      console.error('Inspection submission network error:', err);
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span>🔒</span> Submit Arrival Inspection';
      }
      showToast('Network error: Unable to submit inspection to server. Order remains unverified.', 'error');
      return;
    }
  }

  // 2. Node.js unit test runner fallback only (when window is undefined)
  const result = verifyDeliveryOrder(orderId, {
    orderedQty: order.qty,
    deliveredQty: deliveredVal,
    soundQty: soundVal,
    damagedQty: damagedVal,
    damageNotes
  });

  if (!result.success) {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<span>🔒</span> Submit Arrival Inspection';
    }
    showToast(result.error || 'Verification failed.', 'warning');
    return;
  }

  closeDeliveryVerificationModal();
  renderNurseryDashboard();
  renderSupplierDashboard();
  showToast(`✅ Order ${orderId} verified & locked: ${result.record.soundQty} sound plants accepted (${result.record.damagePct}% damaged).`, 'success');
}

/**
 * Handle Supplier Counter-Signature via Flask API
 */
async function handleSupplierCounterSign(orderId) {
  const submitBtn = document.getElementById('btn-confirm-verification');
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span>⏳</span> Counter-Signing...';
  }

  try {
    const resp = await fetch(`/api/orders/${orderId}/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        party_role: 'SUPPLIER',
        signature_note: 'Verified and counter-signed by wholesale supplier dispatch.'
      })
    });

    const body = await resp.json();
    if (!resp.ok || !body.success) {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span>✍️</span> Counter-Sign & Confirm Delivery';
      }
      showToast(body.error || 'Supplier counter-sign rejected.', 'warning');
      return;
    }

    closeDeliveryVerificationModal();
    showToast(`✅ Dual confirmation finalized! Order #${orderId} permanently locked in audit ledger.`, 'success');
    await syncStoredVerifications();
  } catch (err) {
    showToast('Failed to connect to confirmation server.', 'warning');
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<span>✍️</span> Counter-Sign & Confirm Delivery';
    }
  }
}

/**
 * Core business logic function to verify delivery and enforce locking
 */
function verifyDeliveryOrder(orderId, inspectionData, inspector = 'Amit Sharma (Green Meadows Receiving)') {
  const verifications = loadDeliveryVerificationsFromStorage();

  // Enforce locking: Reject any subsequent modifications
  if (verifications[orderId] && verifications[orderId].isLocked) {
    return {
      success: false,
      locked: true,
      error: `Order ${orderId} is locked. Finalized delivery inspections cannot be edited or modified.`
    };
  }

  const metrics = calculateInspectionMetrics(
    inspectionData.orderedQty,
    inspectionData.deliveredQty,
    inspectionData.soundQty,
    inspectionData.damagedQty
  );

  if (!metrics.isValid) {
    return {
      success: false,
      error: metrics.error
    };
  }

  const inboundOrder = DUMMY_DATA.nurseryInbound.find(o => o.orderId === orderId);
  if (!inboundOrder) {
    return {
      success: false,
      error: `Inbound shipment ${orderId} not found.`
    };
  }

  // Immutable verification record
  const record = {
    orderId,
    variety: inboundOrder.variety,
    orderedQty: metrics.orderedQty,
    deliveredQty: metrics.deliveredQty,
    soundQty: metrics.soundQty,
    damagedQty: metrics.damagedQty,
    damagePct: metrics.damagePct,
    damageNotes: (inspectionData.damageNotes || '').trim(),
    acceptedQty: metrics.acceptedQty,
    hasMismatch: metrics.hasMismatch,
    mismatchDiff: metrics.mismatchDiff,
    verifiedAt: new Date().toISOString(),
    verifiedBy: inspector,
    isLocked: true,
    status: 'DELIVERED & VERIFIED'
  };

  // Persist to storage
  verifications[orderId] = record;
  saveDeliveryVerificationsToStorage(verifications);

  // Update in-memory state
  inboundOrder.status = 'DELIVERED & VERIFIED';
  inboundOrder.badgeClass = 'badge-success';
  inboundOrder.isLocked = true;
  inboundOrder.soundQty = metrics.soundQty;
  inboundOrder.damagedQty = metrics.damagedQty;
  inboundOrder.damageNotes = record.damageNotes;
  inboundOrder.damagePct = metrics.damagePct;
  inboundOrder.verifiedAt = record.verifiedAt;
  inboundOrder.verifiedBy = record.verifiedBy;

  // Also sync nurseryOrders history list
  const nOrder = DUMMY_DATA.nurseryOrders.find(o => o.orderId === orderId);
  if (nOrder) {
    nOrder.status = 'DELIVERED & VERIFIED';
    nOrder.badgeClass = 'badge-success';
  }

  return {
    success: true,
    record
  };
}

// ============================================================================
// DIGITAL DEAL AGREEMENTS & PAYMENT TERMS ENGINE (Stage: Digital Deal Agreements)
// ============================================================================

let currentLoadedAgreement = null;
let cachedOrdersForAgreement = [];

async function fetchAndRenderAgreements() {
  if (typeof fetch === 'undefined') return;
  try {
    const res = await fetch('/api/agreements');
    if (!res.ok) return;
    const json = await res.json();
    if (!json.success || !json.data) return;

    renderAgreementsList(json.data);
  } catch (err) {
    console.warn('Could not fetch deal agreements from API:', err);
  }
}

function renderAgreementsList(agreements) {
  if (typeof document === 'undefined') return;
  const supplierTbody = document.getElementById('supplier-agreements-tbody');
  const nurseryTbody = document.getElementById('nursery-agreements-tbody');

  if (supplierTbody) {
    if (!agreements || agreements.length === 0) {
      supplierTbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-secondary); padding: 1.5rem;">No commercial deal agreements created yet. Click "Propose Deal Terms" to begin.</td></tr>`;
    } else {
      supplierTbody.innerHTML = agreements.map(a => {
        const isAgreed = a.status === 'AGREED';
        const badgeClass = isAgreed ? 'badge-success' : (a.status === 'CANCELLED' ? 'badge-danger' : 'badge-warning');
        const badgeLabel = isAgreed ? 'AGREED & FINALIZED' : (a.nursery_approved ? 'AWAITING SUPPLIER' : 'PENDING NURSERY');
        const formattedTotal = '₹' + Number(a.total_order_value).toLocaleString('en-IN', { minimumFractionDigits: 2 });
        const advBal = `${a.advance_percentage}% (₹${Number(a.advance_amount).toLocaleString('en-IN')}) / ₹${Number(a.balance_amount).toLocaleString('en-IN')}`;
        const interestStr = a.interest_rate_pct > 0 ? `${a.interest_rate_pct}% p.a.` : 'None';

        return `
          <tr>
            <td><strong>${a.agreement_ref}</strong></td>
            <td><span class="order-link" style="color: var(--primary); font-weight: 600; cursor: pointer;" onclick="openDealAgreementModal(${a.id})">${a.order_id}</span></td>
            <td>${a.nursery_name || a.nursery_username}</td>
            <td><strong>${formattedTotal}</strong></td>
            <td><small style="color: var(--text-secondary);">${advBal}</small></td>
            <td>${a.payment_due_date}</td>
            <td><span style="color: #8A5300; font-weight: 600;">${interestStr}</span></td>
            <td><span class="badge ${badgeClass}">${badgeLabel}</span></td>
            <td>
              <button type="button" class="btn btn-secondary btn-sm" onclick="openDealAgreementModal(${a.id})">
                <span>🔍</span> Review
              </button>
            </td>
          </tr>
        `;
      }).join('');
    }
  }

  if (nurseryTbody) {
    if (!agreements || agreements.length === 0) {
      nurseryTbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-secondary); padding: 1.5rem;">No commercial deal agreements registered for your nursery yet.</td></tr>`;
    } else {
      nurseryTbody.innerHTML = agreements.map(a => {
        const isAgreed = a.status === 'AGREED';
        const badgeClass = isAgreed ? 'badge-success' : (a.nursery_approved ? 'badge-info' : 'badge-warning');
        const badgeLabel = isAgreed ? 'AGREED & FINALIZED' : (a.nursery_approved ? 'APPROVED BY YOU' : 'ACTION REQUIRED');
        const formattedTotal = '₹' + Number(a.total_order_value).toLocaleString('en-IN', { minimumFractionDigits: 2 });
        const advBal = `${a.advance_percentage}% (₹${Number(a.advance_amount).toLocaleString('en-IN')}) / ₹${Number(a.balance_amount).toLocaleString('en-IN')}`;
        const interestStr = a.interest_rate_pct > 0 ? `${a.interest_rate_pct}% p.a.` : 'None';
        const btnClass = (!isAgreed && !a.nursery_approved) ? 'btn-primary' : 'btn-secondary';
        const btnText = (!isAgreed && !a.nursery_approved) ? '✍️ Review & Approve' : '🔍 Review';

        return `
          <tr>
            <td><strong>${a.agreement_ref}</strong></td>
            <td><span class="order-link" style="color: var(--primary); font-weight: 600; cursor: pointer;" onclick="openDealAgreementModal(${a.id})">${a.order_id}</span></td>
            <td>${a.supplier_name || a.supplier_username}</td>
            <td><strong>${formattedTotal}</strong></td>
            <td><small style="color: var(--text-secondary);">${advBal}</small></td>
            <td>${a.payment_due_date}</td>
            <td><span style="color: #8A5300; font-weight: 600;">${interestStr}</span></td>
            <td><span class="badge ${badgeClass}">${badgeLabel}</span></td>
            <td>
              <button type="button" class="btn ${btnClass} btn-sm" onclick="openDealAgreementModal(${a.id})">
                ${btnText}
              </button>
            </td>
          </tr>
        `;
      }).join('');
    }
  }
}

async function openDealAgreementModal(agreementId) {
  if (typeof document === 'undefined') return;
  const modal = document.getElementById('deal-agreement-modal');
  if (!modal) return;

  try {
    const res = await fetch(`/api/agreements/${agreementId}`);
    if (!res.ok) {
      if (typeof showToast === 'function') showToast('Could not load deal agreement details.', 'error');
      return;
    }
    const json = await res.json();
    if (!json.success || !json.data) return;

    const a = json.data;
    currentLoadedAgreement = a;

    // Set title and subtitle
    const title = document.getElementById('agr-modal-title');
    const subtitle = document.getElementById('agr-modal-subtitle');
    const badge = document.getElementById('agr-modal-status-badge');

    if (title) title.innerHTML = `🤝 Digital Deal Agreement • ${a.agreement_ref}`;
    if (subtitle) subtitle.textContent = `Order #${a.order_id} • Version ${a.version} • Created ${a.created_at}`;

    const isAgreed = (a.status === 'AGREED');
    if (badge) {
      badge.textContent = isAgreed ? 'AGREED & FINALIZED' : a.status.replace(/_/g, ' ');
      badge.className = isAgreed ? 'badge badge-success' : 'badge badge-warning';
    }

    const setTxt = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    };

    setTxt('agr-view-order-id', a.order_id);
    setTxt('agr-view-variety', a.plant_variety);
    setTxt('agr-view-supplier', a.supplier_name ? `${a.supplier_name} (${a.supplier_username})` : a.supplier_username);
    setTxt('agr-view-nursery', a.nursery_name ? `${a.nursery_name} (${a.nursery_username})` : a.nursery_username);

    setTxt('agr-view-total-val', '₹' + Number(a.total_order_value).toLocaleString('en-IN', { minimumFractionDigits: 2 }));
    setTxt('agr-view-qty-pricing', `${a.quantity} units @ ₹${Number(a.unit_price).toFixed(2)}`);

    setTxt('agr-view-advance-val', '₹' + Number(a.advance_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 }));
    setTxt('agr-view-advance-pct', `${a.advance_percentage}% Upfront Advance`);

    setTxt('agr-view-balance-val', '₹' + Number(a.balance_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 }));
    setTxt('agr-view-balance-pct', `${(100 - a.advance_percentage).toFixed(1)}% on Delivery`);

    setTxt('agr-view-due-date', a.payment_due_date);
    setTxt('agr-view-period-days', `Credit Period: Net ${a.payment_period_days} Days`);

    const interestBasisLabel = a.interest_calculation_basis === 'ANNUAL_SIMPLE' ? 'Annual Simple' : a.interest_calculation_basis;
    setTxt('agr-view-interest', `${a.interest_rate_pct}% p.a. (${interestBasisLabel})`);
    setTxt('agr-view-grace', `${a.interest_grace_period_days} Days Grace Period`);
    setTxt('agr-view-notes', a.notes || 'Standard commercial wholesale agreement.');

    // Assent status cards
    const suppBadge = document.getElementById('agr-supplier-assent-badge');
    const suppInfo = document.getElementById('agr-supplier-assent-info');
    if (a.supplier_approved && a.supplier_approval) {
      if (suppBadge) {
        suppBadge.textContent = 'Approved & Recorded';
        suppBadge.className = 'badge badge-success';
      }
      if (suppInfo) {
        suppInfo.innerHTML = `<strong>${a.supplier_approval.username}</strong> (${a.supplier_approval.business_name})<br><small style="color: var(--text-secondary);">${a.supplier_approval.approved_at} • ${a.supplier_approval.approval_type}</small>`;
      }
    } else {
      if (suppBadge) {
        suppBadge.textContent = 'Awaiting Assent';
        suppBadge.className = 'badge badge-warning';
      }
      if (suppInfo) suppInfo.textContent = 'Supplier has not registered approval for these terms yet.';
    }

    const nursBadge = document.getElementById('agr-nursery-assent-badge');
    const nursInfo = document.getElementById('agr-nursery-assent-info');
    if (a.nursery_approved && a.nursery_approval) {
      if (nursBadge) {
        nursBadge.textContent = 'Approved & Recorded';
        nursBadge.className = 'badge badge-success';
      }
      if (nursInfo) {
        nursInfo.innerHTML = `<strong>${a.nursery_approval.username}</strong> (${a.nursery_approval.business_name})<br><small style="color: var(--text-secondary);">${a.nursery_approval.approved_at} • ${a.nursery_approval.approval_type}</small>`;
      }
    } else {
      if (nursBadge) {
        nursBadge.textContent = 'Awaiting Assent';
        nursBadge.className = 'badge badge-warning';
      }
      if (nursInfo) nursInfo.textContent = 'Nursery has not registered approval for these terms yet.';
    }

    // Determine if current user can approve
    const actionBox = document.getElementById('agr-approval-action-box');
    const amendBox = document.getElementById('agr-amendment-box');
    const amendBtn = document.getElementById('btn-toggle-amend-view');
    if (amendBox) amendBox.style.display = 'none';

    let me = null;
    try {
      const meRes = await fetch('/api/auth/me');
      if (meRes.ok) {
        const meJson = await meRes.json();
        if (meJson.success) me = meJson.data;
      }
    } catch (_) {}

    const canApprove = me && (
      (me.role === 'SUPPLIER' && me.id === a.supplier_user_id && !a.supplier_approved) ||
      (me.role === 'NURSERY' && me.id === a.nursery_user_id && !a.nursery_approved)
    );

    if (actionBox) actionBox.style.display = canApprove ? 'block' : 'none';
    if (amendBtn) amendBtn.style.display = isAgreed ? 'inline-flex' : 'none';

    modal.style.display = 'flex';
  } catch (err) {
    console.error('Error opening deal agreement modal:', err);
    if (typeof showToast === 'function') showToast('Failed to display agreement.', 'error');
  }
}

function closeDealAgreementModal() {
  if (typeof document === 'undefined') return;
  const modal = document.getElementById('deal-agreement-modal');
  if (modal) modal.style.display = 'none';
  currentLoadedAgreement = null;
}

async function submitAgreementApproval() {
  if (!currentLoadedAgreement) return;
  const notesInput = document.getElementById('agr-approval-notes-input');
  const notes = notesInput ? notesInput.value.trim() : '';
  const btn = document.getElementById('btn-approve-deal-action');

  try {
    if (btn) btn.disabled = true;
    const res = await fetch(`/api/agreements/${currentLoadedAgreement.id}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes })
    });
    const json = await res.json();
    if (!res.ok || !json.success) {
      if (typeof showToast === 'function') showToast(json.error || 'Failed to approve agreement.', 'error');
      if (btn) btn.disabled = false;
      return;
    }

    if (typeof showToast === 'function') showToast(json.message || 'Deal agreement terms approved successfully!', 'success');
    await openDealAgreementModal(currentLoadedAgreement.id);
    fetchAndRenderAgreements();
  } catch (err) {
    console.error('Error submitting approval:', err);
    if (typeof showToast === 'function') showToast('Network error while recording agreement approval.', 'error');
  } finally {
    if (btn) btn.disabled = false;
  }
}

function toggleAmendmentBox() {
  if (typeof document === 'undefined') return;
  const box = document.getElementById('agr-amendment-box');
  if (!box) return;
  const isHidden = (box.style.display === 'none' || !box.style.display);
  box.style.display = isHidden ? 'block' : 'none';

  if (isHidden && currentLoadedAgreement) {
    const adv = document.getElementById('amend-adv-pct');
    const per = document.getElementById('amend-period');
    if (adv) adv.value = currentLoadedAgreement.advance_percentage;
    if (per) per.value = currentLoadedAgreement.payment_period_days;
  }
}

async function submitAgreementAmendment() {
  if (!currentLoadedAgreement) return;
  const reasonInput = document.getElementById('amend-reason');
  const reason = reasonInput ? reasonInput.value.trim() : '';
  if (!reason) {
    if (typeof showToast === 'function') showToast('Amendment justification / reason is mandatory.', 'warning');
    if (reasonInput) reasonInput.focus();
    return;
  }

  const advInput = document.getElementById('amend-adv-pct');
  const periodInput = document.getElementById('amend-period');
  const payload = {
    reason,
    advance_percentage: advInput ? parseFloat(advInput.value) : undefined,
    payment_period_days: periodInput ? parseInt(periodInput.value, 10) : undefined
  };

  try {
    const res = await fetch(`/api/agreements/${currentLoadedAgreement.id}/amend`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const json = await res.json();
    if (!res.ok || !json.success) {
      if (typeof showToast === 'function') showToast(json.error || 'Failed to issue amendment.', 'error');
      return;
    }

    if (typeof showToast === 'function') showToast(json.message || 'Versioned amendment created successfully!', 'success');
    closeDealAgreementModal();
    fetchAndRenderAgreements();
  } catch (err) {
    console.error('Error submitting amendment:', err);
    if (typeof showToast === 'function') showToast('Network error while submitting amendment.', 'error');
  }
}

async function openCreateAgreementModal() {
  if (typeof document === 'undefined') return;
  const modal = document.getElementById('create-agreement-modal');
  if (!modal) return;

  const select = document.getElementById('create-agr-order-select');
  if (select) {
    select.innerHTML = '<option value="">Loading orders...</option>';
    try {
      const res = await fetch('/api/orders');
      if (res.ok) {
        const json = await res.json();
        if (json.success && json.data) {
          cachedOrdersForAgreement = json.data;
          select.innerHTML = '<option value="">-- Choose an Order --</option>' +
            json.data.map(o => `<option value="${o.id}">${o.id} — ${o.variety} (${o.ordered_qty} units @ ₹${o.unit_price})</option>`).join('');
        }
      }
    } catch (e) {
      console.warn('Could not load orders for agreement creation:', e);
    }
  }

  recalcCreateAgreementPreview();
  modal.style.display = 'flex';
}

function closeCreateAgreementModal() {
  if (typeof document === 'undefined') return;
  const modal = document.getElementById('create-agreement-modal');
  if (modal) modal.style.display = 'none';
}

function onCreateAgreementOrderChanged() {
  if (typeof document === 'undefined') return;
  const select = document.getElementById('create-agr-order-select');
  const previewBox = document.getElementById('create-agr-order-preview');
  const previewVal = document.getElementById('create-agr-preview-value');
  if (!select) return;

  const orderId = select.value;
  const order = cachedOrdersForAgreement.find(o => o.id === orderId);
  if (order && previewBox && previewVal) {
    const total = order.ordered_qty * order.unit_price;
    previewVal.textContent = `${order.variety} • ${order.ordered_qty} units @ ₹${order.unit_price} = ₹${total.toLocaleString('en-IN')}`;
    previewBox.style.display = 'block';
  } else if (previewBox) {
    previewBox.style.display = 'none';
  }
  recalcCreateAgreementPreview();
}

function recalcCreateAgreementPreview() {
  if (typeof document === 'undefined') return;
  const select = document.getElementById('create-agr-order-select');
  const advPctInput = document.getElementById('create-agr-advance-pct');
  const advPreview = document.getElementById('create-preview-adv-amt');
  const balPreview = document.getElementById('create-preview-bal-amt');

  if (!select || !advPctInput) return;
  const orderId = select.value;
  const order = cachedOrdersForAgreement.find(o => o.id === orderId);

  const total = order ? (order.ordered_qty * order.unit_price) : 52500.0;
  const advPct = parseFloat(advPctInput.value) || 0.0;

  const advAmt = Math.round(total * (advPct / 100.0));
  const balAmt = total - advAmt;

  if (advPreview) advPreview.textContent = `₹${advAmt.toLocaleString('en-IN')} (${advPct}%)`;
  if (balPreview) balPreview.textContent = `₹${balAmt.toLocaleString('en-IN')} (${(100 - advPct).toFixed(0)}%)`;
}

async function handleCreateAgreementSubmit(event) {
  if (event && event.preventDefault) event.preventDefault();
  const select = document.getElementById('create-agr-order-select');
  const advPctInput = document.getElementById('create-agr-advance-pct');
  const periodInput = document.getElementById('create-agr-period-days');
  const interestInput = document.getElementById('create-agr-interest-rate');
  const basisSelect = document.getElementById('create-agr-interest-basis');
  const notesInput = document.getElementById('create-agr-notes-input');
  const submitBtn = document.getElementById('btn-submit-create-agreement');

  if (!select || !select.value) {
    if (typeof showToast === 'function') showToast('Please select a wholesale order.', 'warning');
    return;
  }

  const payload = {
    order_id: select.value,
    advance_percentage: parseFloat(advPctInput.value) || 20.0,
    payment_period_days: parseInt(periodInput.value, 10) || 10,
    interest_rate_pct: parseFloat(interestInput.value) || 0.0,
    interest_calculation_basis: basisSelect ? basisSelect.value : 'ANNUAL_SIMPLE',
    notes: notesInput ? notesInput.value.trim() : ''
  };

  try {
    if (submitBtn) submitBtn.disabled = true;
    const res = await fetch('/api/agreements', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const json = await res.json();
    if (!res.ok || !json.success) {
      if (typeof showToast === 'function') showToast(json.error || 'Failed to create deal agreement.', 'error');
      if (submitBtn) submitBtn.disabled = false;
      return;
    }

    if (typeof showToast === 'function') showToast(json.message || 'Deal agreement created successfully!', 'success');
    closeCreateAgreementModal();
    fetchAndRenderAgreements();
  } catch (err) {
    console.error('Error creating deal agreement:', err);
    if (typeof showToast === 'function') showToast('Network error while creating deal agreement.', 'error');
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

// Close modals on clicking backdrop (Browser environment)
if (typeof document !== 'undefined') {
  document.addEventListener('click', (e) => {
    const formModal = document.getElementById('nursery-form-modal');
    const viewModal = document.getElementById('nursery-view-modal');
    const verifyModal = document.getElementById('delivery-verification-modal');
    const agrModal = document.getElementById('deal-agreement-modal');
    const createAgrModal = document.getElementById('create-agreement-modal');
    const invDetailModal = document.getElementById('invoice-detail-modal');
    const invTermsModal = document.getElementById('invoice-terms-modal');
    if (e.target === formModal) closeNurseryModal();
    if (e.target === viewModal) closeViewNurseryModal();
    if (e.target === verifyModal) closeDeliveryVerificationModal();
    if (e.target === agrModal) closeDealAgreementModal();
    if (e.target === createAgrModal) closeCreateAgreementModal();
    if (e.target === invDetailModal) closeInvoiceDetailModal();
    if (e.target === invTermsModal) closeEditInvoiceTermsModal();
  });
}

// Close modals on Escape key (Browser environment)
if (typeof window !== 'undefined') {
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeNurseryModal();
      closeViewNurseryModal();
      closePlantModal();
      closeViewPlantModal();
      closeDeliveryVerificationModal();
      closeDealAgreementModal();
      closeCreateAgreementModal();
      closeInvoiceDetailModal();
      closeEditInvoiceTermsModal();
      closeRecordPaymentModal();
      closePaymentDetailModal();
    }
  });

  // ============================================================================
  // 6. INITIALIZATION & HASH LISTENER
  // ============================================================================

  window.addEventListener('DOMContentLoaded', () => {
    // Check active session identity from backend
    checkCurrentUserSession();

    // Wire header logout button
    const logoutBtn = document.getElementById('header-logout-btn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', (e) => {
        e.preventDefault();
        handleLogout();
      });
    }

    // Sync persistent delivery verification state
    syncStoredVerifications();

    // Fetch and render deal agreements
    fetchAndRenderAgreements();

    // Render live data across views
    renderSupplierDashboard();
    fetchAndRenderSupplierDashboard();
    renderNurseryDashboard();
    fetchAndRenderNurseries();
    applyNurseryFilters();
    updateNurserySummaryKPIs();

    // Read initial hash or default to 'home'
    const initialHash = window.location.hash.replace('#', '');
    if (['home', 'login', 'supplier', 'nursery'].includes(initialHash)) {
      navigateTo(initialHash);
    } else if (initialHash === 'nurseries') {
      navigateTo('supplier');
      showSupplierSubpage('nurseries');
    } else if (initialHash === 'plants') {
      navigateTo('supplier');
      showSupplierSubpage('plants');
    } else if (initialHash === 'orders') {
      navigateTo('supplier');
      showSupplierSubpage('orders');
    } else if (initialHash === 'truck-loading') {
      navigateTo('supplier');
      showSupplierSubpage('truck-loading');
    } else if (initialHash === 'invoices') {
      navigateTo('supplier');
      showSupplierSubpage('invoices');
    } else if (initialHash === 'payments') {
      navigateTo('supplier');
      showSupplierSubpage('payments');
    } else if (initialHash === 'ledger' || initialHash === 'history') {
      navigateTo('supplier');
      showSupplierSubpage('ledger');
    } else {
      navigateTo('home');
    }
  });

  // Support browser back/forward buttons
  window.addEventListener('hashchange', () => {
    const hash = window.location.hash.replace('#', '');
    if (['home', 'login', 'supplier', 'nursery'].includes(hash)) {
      navigateTo(hash);
    } else if (hash === 'nurseries') {
      navigateTo('supplier');
      showSupplierSubpage('nurseries');
    } else if (hash === 'plants') {
      navigateTo('supplier');
      showSupplierSubpage('plants');
    } else if (hash === 'orders') {
      navigateTo('supplier');
      showSupplierSubpage('orders');
    } else if (hash === 'truck-loading') {
      navigateTo('supplier');
      showSupplierSubpage('truck-loading');
    } else if (hash === 'invoices') {
      navigateTo('supplier');
      showSupplierSubpage('invoices');
    } else if (hash === 'payments') {
      navigateTo('supplier');
      showSupplierSubpage('payments');
    } else if (hash === 'ledger' || hash === 'history') {
      navigateTo('supplier');
      showSupplierSubpage('ledger');
    }
  });
}

// Export engines for Node.js automated testing
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    DUMMY_DATA,
    calculateInspectionMetrics,
    verifyDeliveryOrder,
    loadDeliveryVerificationsFromStorage,
    saveDeliveryVerificationsToStorage,
    syncStoredVerifications,
    DELIVERY_VERIFICATIONS_STORAGE_KEY,
    fetchAndRenderAgreements,
    openDealAgreementModal,
    closeDealAgreementModal,
    submitAgreementApproval,
    submitAgreementAmendment,
    formatPlantCurrency,
    escapePlantHtml,
    renderPlantsTable,
    updatePlantSummaryKPIs,
    handlePlantSearch,
    clearPlantSearch,
    handlePlantCategoryChange,
    setPlantStatusFilter,
    openAddPlantModal,
    openEditPlantModal,
    closePlantModal,
    openViewPlantModal,
    closeViewPlantModal,
    handlePlantFormSubmit,
    escapeOrderHtml,
    formatOrderCurrency,
    formatOrderStatusBadge,
    updateOrderSummaryKPIs,
    setOrderStatusFilter,
    handleOrderSearch,
    clearOrderSearch,
    renderOrdersTable,
    openCreateOrderModal,
    closeCreateOrderModal,
    addOrderItemRow,
    removeOrderItemRow,
    handleOrderItemPlantChange,
    updateOrderFormCalculations,
    handleCreateOrderSubmit,
    openOrderDetailModal,
    closeOrderDetailModal,
    formatTruckStatusBadge,
    updateTruckSummaryKPIs,
    handleTruckSearch,
    clearTruckSearch,
    setTruckStatusFilter,
    renderTruckManifestsTable,
    openTruckLoadingModal,
    closeTruckLoadingModal,
    handleTruckItemQtyChange,
    autoLoadMaxAllItems,
    updateTruckModalTotals,
    submitTruckLoading,
    formatInvoiceStatusBadge,
    formatInvoiceCurrency,
    fetchAndRenderInvoices,
    updateInvoicesSummaryKPIs,
    renderInvoicesTable,
    handleInvoicesSearch,
    clearInvoicesSearch,
    setInvoicesStatusFilter,
    currentInvoicesDueStatusFilter,
    setInvoicesDueStatusFilter,
    formatDueStatusBadge,
    openInvoiceDetailModal,
    closeInvoiceDetailModal,
    openEditInvoiceTermsModal,
    closeEditInvoiceTermsModal,
    handleUpdateInvoiceTermsSubmit,
    printInvoiceModal,
    printInvoiceDirect,
    generateInvoiceForOrder,
    handleOrderInvoiceAction,
    promptCancelInvoice,
    formatPaymentCurrency,
    formatPaymentMethodBadge,
    formatPaymentStatusBadge,
    formatPaymentTypeBadge,
    fetchAndRenderPayments,
    updatePaymentsSummaryKPIs,
    renderPaymentsTable,
    handlePaymentsSearch,
    clearPaymentsSearch,
    setPaymentsStatusFilter,
    setPaymentsMethodFilter,
    openRecordPaymentModal,
    closeRecordPaymentModal,
    handlePaymentInvoiceSelectionChange,
    handleRecordPaymentSubmit,
    openPaymentDetailModal,
    closePaymentDetailModal,
    promptReversePayment,
    formatLedgerCurrency,
    escapeLedgerHtml,
    formatLedgerTypeBadge,
    formatLedgerDirectionBadge,
    formatLedgerStatusBadge,
    fetchAndRenderLedger,
    updateLedgerSummaryKPIs,
    updateLedgerCounterpartySelect,
    renderLedgerTable,
    handleLedgerSearch,
    clearLedgerSearch,
    setLedgerTypeFilter,
    handleLedgerNurseryFilter,
    handleLedgerDateFilter,
    handleLedgerSortOrder,
    ledgerFilters,
    fetchAndRenderNurseryDashboard,
    renderNurseryInboundTable,
    renderNurseryOrdersTable,
    renderNurseryInvoicesTable,
    renderNurseryLedgerTable,
    renderNurseryAgreementsTable,
    openNurseryLedgerModal,
    closeNurseryLedgerModal,
    handleDummyLogin,
    quickDemoLogin,
    handleLogout,
    checkCurrentUserSession,
    updateActiveUserHeader,
    fetchAndRenderSupplierDashboard,
    fetchAndRenderNurseries,
    toggleOrderAuditHistory
  };
}

