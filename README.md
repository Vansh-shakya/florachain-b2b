# 🌿 FloraChain B2B — Wholesale Nursery Supply Platform

FloraChain B2B is a specialized B2B commerce and supply chain management web platform designed for the commercial plant nursery industry. It connects **Commercial Wholesale Suppliers** (growers/distributors) with **Retail Nurseries & Landscapers** (buyers), providing transparent order fulfillment, truck staging, physical delivery inspection, dynamic invoicing, and ledger balance management.

---

## 🌟 Key Features & Domain Workflow

Commercial wholesale plant procurement differs from standard e-commerce due to live perishable inventory, transport damages, and negotiated commercial terms. FloraChain enforces a verified, step-by-step workflow:

1. **Digital Plant Catalog & Inventory:** Real-time catalog categorizing plants (Indoor, Outdoor, Flowering, Tree, Palm, Succulent, etc.) with packaging units, pricing, and active/discontinued status.
2. **Order Staging & Manifesting:** Nurseries place bulk orders; suppliers stage plant batches and assign logistics details (vehicle number, driver name, driver contact).
3. **Dual-Party Physical Delivery Verification:** Upon arrival, nursery inspectors record sound vs. damaged/rejected plant quantities. Orders are locked only after server-side confirmation, preventing billing discrepancies.
4. **Delivered-Sound Invoicing:** Wholesale invoices are automatically generated **strictly** for delivered sound plants (never charging for transport-damaged items).
5. **Flexible Payment & Advance Allocation:** Supports bank transfer, NEFT/RTGS, UPI, and cheque payments. Unallocated advances can be allocated to open invoices with strict counterparty isolation.
6. **Agreed Credit Terms & Late Interest Engine:** Tracks due dates based on negotiated credit periods (e.g., 30 days) and accrues daily late-payment interest for overdue balances.
7. **Transparent Financial Ledger:** Real-time double-entry style accounting statements reflecting gross billing, settled payments, advance credits, accrued interest, and net balance due.
8. **Role-Based Access Control (RBAC):** Distinct interfaces for **Suppliers** (`SUPPLIER`), **Buyer Nurseries** (`NURSERY`), and **Platform Administrators** (`ADMIN`), protected by session-cookie authentication and CSRF defense.

---

## 🛠 Technology Stack

* **Frontend:** Vanilla HTML5, CSS3, ES6 JavaScript
  * Single Page Architecture (SPA) without heavy framework bloat or node build steps
  * Custom responsive design system featuring FloraChain brand green (`#063B00`)
  * Dynamic live-updating dashboards, KPI stat cards, and interactive modal dialogs
* **Backend:** Python 3.10+ & Flask 3.0.3
  * Application Factory pattern (`create_app`) with modular Blueprints
  * Cryptographic session security, CSRF token validation on state-changing requests, and secure cookie flags
  * Service layer isolating business logic (Invoicing, Payments, Interest, Ledger, Auditing)
* **Database & Persistence:**
  * **Default Active Database:** SQLite 3 with Write-Ahead Logging (`PRAGMA journal_mode=WAL`)
  * **Supported Enterprise Engine:** PostgreSQL 15+ (automated adapter and data migration utility included)
* **Testing & Quality Assurance:**
  * Python `unittest` / `pytest` regression suites (226 automated backend tests)
  * Node.js DOM-based headless validation suites (9 UI integration test suites)

---

## 📋 Prerequisites

To run FloraChain B2B locally, ensure you have:
* **Python:** Version 3.10 or higher (`python --version`)
* **pip:** Python package manager
* **Node.js:** Version 18 or higher (optional, required only for running UI assertion test suites: `node --version`)
* **Git:** Version control (`git --version`)

---

## 🚀 Quick Start & Local Setup

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/florachain-b2b.git
cd florachain-b2b/supplier_platform
```

### 2. Set Up Python Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
Copy the example environment template:
```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```
*(The default settings use SQLite at `data/florachain.db` and require no additional database setup.)*

### 5. Launch the Application Server
```bash
# Quick start on Windows
run.bat

# Standard execution on any platform
python run.py
```
The application will start on **`http://127.0.0.1:8000/`** (or the next available port) and automatically open in your default browser.

---

## 🔑 Demo Credentials (Synthetic Demo Personas Only)

> **Security Notice:** The credentials listed below are purely synthetic, non-production test accounts pre-seeded in the local evaluation database. They are intended exclusively for academic grading, local development, and demonstration purposes. Never use real or personal passwords in demonstration environments.

| Role | Email Address | Password | Portal View |
|---|---|---|---|
| **Wholesale Supplier** | `supplier@florachain.com` | `FloraChain2026!` | Supplier Operations, Staging, Dispatch, Billing |
| **Retail Nursery Buyer** | `nursery@greenroots.com` | `FloraChain2026!` | Buyer Orders, Inbound Deliveries, Receipts, Statements |
| **Platform Administrator**| `admin@florachain.com` | `FloraChain2026!` | System-wide Audit Logs, Counterparty Directory |

*Note: In local development mode (`FLORACHAIN_ALLOW_DEMO_ROLE_SWITCH=true`), you can also switch roles quickly using the dropdown in the navigation header.*

---

## 🧪 Running the Automated Test Suites

### Backend Unit & Integration Tests (Python)
Run the full 226-test Python regression suite:
```bash
python -m unittest discover -s tests -p "test_*.py"
```
Or run targeted phase test suites:
```bash
python -m unittest tests/test_phase15_security.py
python -m unittest tests/test_phase16_integration.py
python -m unittest tests/test_phase17_bugfixes.py
```

### Frontend UI & DOM Assertion Suites (Node.js)
Run the 9 modular UI integration test suites:
```bash
node tests/test_phase4.js          # Nursery management & delivery inspection
node tests/test_phase5_ui.js       # Plant catalog UI
node tests/test_phase6_ui.js       # Order creation & detail modals
node tests/test_phase7_ui.js       # Truck loading & logistics manifests
node tests/test_phase8_ui.js       # Wholesale invoice generation UI
node tests/test_phase9_ui.js       # Payment recording & advance allocation UI
node tests/test_phase10_ui.js      # Agreed interest & due date tracking UI
node tests/test_phase11_ui.js      # Commercial account ledger statements
node tests/test_phase12_ui.js      # Nursery buyer portal dashboard
```

---

## 📚 Project Documentation

For deeper architectural, operational, and testing specifications, consult the documents in the [`docs/`](docs/) directory:

* 📐 [**System Architecture (`docs/ARCHITECTURE.md`)**](docs/ARCHITECTURE.md): Multi-tier architecture, API route catalog, calculation engines, and database design.
* 💻 [**Local Setup Guide (`docs/SETUP.md`)**](docs/SETUP.md): Step-by-step setup, troubleshooting, and configuration parameters.
* ☁️ [**Deployment & Demo Guide (`docs/DEPLOYMENT.md`)**](docs/DEPLOYMENT.md): Hosting analysis (Vercel vs. Render vs. PythonAnywhere), SQLite persistence trade-offs, and college demo guide.
* 🔬 [**Testing & Quality Assurance (`docs/TESTING.md`)**](docs/TESTING.md): Test methodology, isolation strategy, test suite catalog, and coverage report.
* 📊 [**Project Implementation Status (`docs/PROJECT_STATUS.md`)**](docs/PROJECT_STATUS.md): Current phase progress, verified security fixes, and roadmap tracking.

---

## 🗺️ 19-Phase Implementation Roadmap

- [x] **Phase 1:** Project Setup, Standards & High-Level Architecture
- [x] **Phase 2:** Frontend Foundation & Responsive Design System
- [x] **Phase 3:** Supplier Dashboard Layout & KPI Framework
- [x] **Phase 4:** Nursery Directory & Physical Delivery Inspection
- [x] **Phase 5:** Plant Management & Catalog Operations
- [x] **Phase 6:** Order Management & Lifecycle Staging
- [x] **Phase 7:** Truck Loading, Manifests & Transport Verification
- [x] **Phase 8:** Delivered-Sound Wholesale Invoicing Engine
- [x] **Phase 9:** Payment Processing, Settlement & Advance Allocations
- [x] **Phase 10:** Due Dates & Agreed Late-Payment Interest Calculation
- [x] **Phase 11:** Commercial Account Ledger & Double-Entry Statements
- [x] **Phase 12:** Nursery Buyer Self-Service Portal
- [x] **Phase 13:** Flask Application Factory, Central Config & Logging
- [x] **Phase 14:** PostgreSQL Dual-Engine Adapter & Safe Data Migration
- [x] **Phase 15:** Authentication Hardening, CSRF Defense & RBAC Audit
- [x] **Phase 16:** Frontend/Backend Integration & Live API Binding
- [x] **Phase 17:** Systematic Verification & Defect Remediation
- [x] **Phase 18:** GitHub Preparation & College Demo Deployment Readiness
- [ ] **Phase 19:** Real-World Validation & Production Demonstration
