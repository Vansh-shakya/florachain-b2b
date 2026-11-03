# 🛠️ FloraChain B2B — Local Developer & Evaluator Setup Guide

This guide provides step-by-step instructions for installing, configuring, running, and testing FloraChain B2B on your local development machine.

---

## 1. System Requirements & Prerequisites

Before setting up FloraChain B2B, ensure the following software is installed on your workstation:

* **Python 3.10 or higher**
  * Check version: `python --version` (or `python3 --version`)
  * Ensure `pip` is included and updated: `python -m pip install --upgrade pip`
* **Node.js 18 or higher (Optional)**
  * Needed only if you wish to run the frontend DOM assertion test suites.
  * Check version: `node --version`
* **Git**
  * Check version: `git --version`
* **Web Browser**
  * Google Chrome, Microsoft Edge, Mozilla Firefox, or Apple Safari.

---

## 2. Step-by-Step Installation

### Step 1: Clone the Repository
```bash
git clone https://github.com/your-username/florachain-b2b.git
cd florachain-b2b/supplier_platform
```

### Step 2: Create a Python Virtual Environment
A virtual environment ensures that the project's dependencies remain isolated from other Python packages on your system.

* **On Windows (PowerShell / Command Prompt):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\activate
  ```
* **On Linux / macOS:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

*(When activated, your terminal prompt will display `(venv)`.)*

### Step 3: Install Required Python Packages
```bash
pip install -r requirements.txt
```

Verify the installation of core frameworks:
```bash
python -c "import flask, werkzeug; print('Flask:', flask.__version__, '| Werkzeug:', werkzeug.__version__)"
```

### Step 4: Configure Local Environment Variables
Create your local `.env` configuration file from the provided template:

* **On Windows:**
  ```powershell
  copy .env.example .env
  ```
* **On Linux / macOS:**
  ```bash
  cp .env.example .env
  ```

The default `.env` is already configured for zero-setup local development:
* Database: Uses embedded SQLite at `data/florachain.db` (no database server required).
* Environment: `FLASK_ENV=development`.
* Demo Switcher: `FLORACHAIN_ALLOW_DEMO_ROLE_SWITCH=true` (allows quick role switching in the navigation header).

---

## 3. Running the Application

### Option A: Quick-Start Script (Windows)
```cmd
run.bat
```

### Option B: Python Runner (Cross-Platform)
```bash
python run.py
```

The server will automatically:
1. Detect an open port starting at `8000` (e.g., `8000`, `8001`).
2. Verify or initialize the database schema in `data/florachain.db`.
3. Open your default web browser to `http://127.0.0.1:8000/`.
4. Output startup telemetry in your terminal:
   ```text
   ====================================================================
   🌿 FloraChain B2B — Nursery Supply Platform
      Stage 2: Authentication, Session RBAC & Security Guardrails
   ====================================================================
   🚀 Server running at:       http://127.0.0.1:8000/
   📁 Serving frontend from:   .../supplier_platform
   🗄️ Database initialized at: data/florachain.db (WAL mode)
   🌐 Health endpoint:         http://127.0.0.1:8000/api/health
   🔑 Auth endpoint:           http://127.0.0.1:8000/api/auth/login
   🎛️ Demo Role Switcher:      Enabled (local development runner)
   🔒 Production Default:      Disabled (strict credentials required)
   ⏹️  To stop the server, press Ctrl + C in this terminal window.
   ====================================================================
   ```

To stop the server, press `Ctrl + C` in the terminal.

---

## 4. Evaluator Login & Demonstration Accounts (Synthetic Personas Only)

> **Security Notice:** The accounts and credentials listed below are purely synthetic, non-production test personas pre-seeded in the local evaluation database. They are intended exclusively for academic grading, local development, and demonstration purposes. Never use real or personal passwords in demonstration environments.

FloraChain B2B comes pre-seeded with sample data representing typical commercial transactions. Use these credentials to evaluate different role perspectives:

| Role | Username / Email | Password | Primary Capabilities |
|---|---|---|---|
| **Wholesale Supplier** | `supplier@florachain.com` | `FloraChain2026!` | Manage catalog, stage orders, dispatch trucks, issue invoices, review ledger |
| **Retail Nursery Buyer** | `nursery@greenroots.com` | `FloraChain2026!` | Review inbound trucks, inspect deliveries, review invoices, check account statements |
| **Platform Administrator**| `admin@florachain.com` | `FloraChain2026!` | Audit history inspection, user management, delivery correction arbitration |

*Tip: When logged in, you can switch perspectives using the role dropdown in the navigation header.*

---

## 5. Running the Test Suites

### Backend Unit & Integration Tests (Python)
Run all 226 tests in the regression suite:
```bash
python -m unittest discover -s tests -p "test_*.py"
```

Expected output:
```text
Ran 226 tests in ~96s
OK (skipped=1)
```

Run specific test modules:
* Authentication & Security: `python -m unittest tests/test_phase15_security.py`
* Frontend/Backend Integration: `python -m unittest tests/test_phase16_integration.py`
* Bugfix Regression Suite: `python -m unittest tests/test_phase17_bugfixes.py`

### Frontend UI & DOM Tests (Node.js)
Run the 9 automated frontend assertion suites:
```bash
node tests/test_phase4.js
node tests/test_phase5_ui.js
node tests/test_phase6_ui.js
node tests/test_phase7_ui.js
node tests/test_phase8_ui.js
node tests/test_phase9_ui.js
node tests/test_phase10_ui.js
node tests/test_phase11_ui.js
node tests/test_phase12_ui.js
```

---

## 6. Troubleshooting & Common Questions

### Port 8000 is Already in Use
`run.py` includes automatic port probing (`find_available_port`). If port 8000 is occupied by another process, it will automatically bind to `8001`, `8002`, etc., and announce the URL in the terminal.

### Windows UTF-8 Terminal Encoding
If your Windows PowerShell or Command Prompt displays garbled characters for emoji or rupee symbols (`₹`), `run.py` automatically configures `sys.stdout.reconfigure(encoding='utf-8')`. You can also run:
```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

### Resetting to Fresh Demonstration Data
If you modify data during testing and wish to restore the baseline demo records:
1. Stop the server (`Ctrl + C`).
2. Delete the temporary database file:
   ```bash
   # Windows
   del data\florachain.db
   # Linux / macOS
   rm data/florachain.db
   ```
3. Restart the server (`python run.py`). The database schema and baseline demo records will be re-created automatically.

