# ☁️ FloraChain B2B — Deployment & Demo Evaluation Guide

**Target Audience:** Academic evaluators, students, and engineers preparing to deploy FloraChain B2B for demonstration to college professors and review panels.  
**Scope:** Hosting platform feasibility, serverless vs. PaaS trade-offs, database persistence analysis, environment configuration, and production security hardening.

---

## 1. Executive Summary & College Demo Hosting Recommendation

The primary objective is to showcase FloraChain B2B to college teachers via a accessible public URL with zero hosting cost, zero architectural risk, and reliable data persistence.

### Comparison Matrix of Free Hosting Options

| Hosting Platform | Deployment Type | SQLite Persistence Support | External DB Required? | Cold-Start Latency | Recommendation Level |
|---|---|---|---|---|---|
| **PythonAnywhere** | WSGI / Linux PaaS | ✅ **Yes (Persistent Disk)** | ❌ No | None (Always active) | ⭐⭐⭐⭐⭐ **Highest Recommendation for College Demo** |
| **Render.com** | Container / Web Service | ⚠️ **Ephemeral Disk** (Resets on restart) | 💡 **Yes (Free Neon / Supabase PostgreSQL)** | 30–50 sec cold start on free tier | ⭐⭐⭐⭐ **Excellent with Free PostgreSQL** |
| **Vercel** | Serverless Lambdas | ❌ **No (Strictly Read-Only + `/tmp` wipes)** | ⚠️ **Mandatory External Database** | 1–3 sec cold start | ⭐⭐⭐ **Viable only with External Cloud DB** |
| **Railway / Fly.io** | Containers | ⚠️ Trial/Card required | ❌ No | Minimal | ⭐⭐ **Requires credit card on file** |

### Evaluator Recommendation:
1. **Option 1 (Simplest & Most Reliable — Zero Code Changes):** Deploy on **PythonAnywhere** (Free Beginner Account).
   * **Why:** PythonAnywhere provides a persistent POSIX filesystem. The default embedded SQLite database (`data/florachain.db`) works out of the box with zero modifications, zero credit card requirements, and permanent persistence across visits.
2. **Option 2 (Modern Cloud PaaS with PostgreSQL):** Deploy on **Render.com** connected to a free **Neon.tech or Supabase** serverless PostgreSQL instance.
   * **Why:** FloraChain B2B already includes a dual-engine PostgreSQL adapter (`app/models/database.py`) and schema (`app/models/schema_postgres.sql`) built in Phase 14. Setting the single environment variable `DATABASE_URL=postgresql://...` activates PostgreSQL seamlessly without altering code.

---

## 2. In-Depth Vercel Feasibility Analysis

Vercel is a popular hosting platform for frontend and Jamstack applications. However, deploying a stateful Python Flask application on Vercel presents architectural constraints that must be understood:

### A. The Ephemeral Filesystem Problem (SQLite Limitation)
* **How Vercel Works:** Vercel packages Python backends as stateless Serverless Functions (AWS Lambda). The root filesystem is **strictly read-only**, except for the temporary `/tmp` directory (limited to 512 MB).
* **Impact on SQLite:** If FloraChain is configured to write its SQLite database to `/tmp/florachain.db`:
  1. **Cold Starts:** Every time a new lambda container spins up, `/tmp` is completely fresh and empty.
  2. **Concurrency Inconsistency:** Two simultaneous requests from different professors may hit different lambda instances, each seeing a separate `/tmp` SQLite file with divergent data.
  3. **Data Loss:** When the lambda instance goes idle and terminates (after a few minutes), all orders, delivery verifications, invoices, and payment records created during the demo are lost.
* **Conclusion:** **SQLite cannot be used for multi-user persistent state on Vercel.**

### B. What is Required to Run FloraChain on Vercel?
To host FloraChain on Vercel without data loss, the application **must** be connected to an external persistent PostgreSQL database:
1. **Database:** Provision a free managed PostgreSQL instance on [Neon.tech](https://neon.tech/) or [Supabase.com](https://supabase.com/).
2. **Environment Variable:** Set `DATABASE_URL=postgresql://user:password@ep-host.neon.tech/florachain?sslmode=require` in the Vercel Project Dashboard.
3. **WSGI Handler:** Create a lightweight `api/index.py` entry point:
   ```python
   from app import create_app
   app = create_app()
   ```
4. **Vercel Configuration (`vercel.json`):**
   ```json
   {
     "rewrites": [{ "source": "/(.*)", "destination": "/api/index.py" }]
   }
   ```
*(Note: Per project safety guidelines, we have not altered the local repository to force Vercel deployment; the above instructions allow seamless deployment if external PostgreSQL is provisioned.)*

---

## 3. Step-by-Step Deployment Guides

### Guide A: PythonAnywhere (Recommended Free Demo Deployment)

1. **Create Account:** Sign up for a free Beginner account at [pythonanywhere.com](https://www.pythonanywhere.com/).
2. **Open Bash Console:** From the Dashboard, navigate to **Consoles** -> **Bash**.
3. **Clone Repository:**
   ```bash
   git clone https://github.com/your-username/florachain-b2b.git
   cd florachain-b2b/supplier_platform
   ```
4. **Create Virtualenv & Install Dependencies:**
   ```bash
   mkvirtualenv --python=python3.10 florachain-venv
   pip install -r requirements.txt
   ```
5. **Configure Web Tab:**
   * Go to the **Web** tab in the PythonAnywhere dashboard.
   * Click **Add a new web app**, choose **Manual configuration**, and select **Python 3.10**.
   * Under **Virtualenv**, enter: `/home/yourusername/.virtualenvs/florachain-venv`.
   * Under **Code**, set source directory to: `/home/yourusername/florachain-b2b/supplier_platform`.
6. **Edit WSGI Configuration File:**
   Click the link to the WSGI configuration file and update its contents:
   ```python
   import sys
   import os

   path = '/home/yourusername/florachain-b2b/supplier_platform'
   if path not in sys.path:
       sys.path.append(path)

   # Set environment variables for production
   os.environ['FLASK_ENV'] = 'production'
   os.environ['SECRET_KEY'] = 'your-secure-random-secret-key-for-college-demo'
   os.environ['FLORACHAIN_ALLOW_DEMO_ROLE_SWITCH'] = 'true' # Optional: enables role switcher for teachers

   from app import create_app
   application = create_app()
   ```
7. **Reload Web App:** Click the green **Reload** button. Your app is live at `https://yourusername.pythonanywhere.com/`!

---

### Guide B: Render.com (Containerized Web Service with Cloud PostgreSQL)

1. **Create Free PostgreSQL on Neon.tech:**
   * Go to [Neon.tech](https://neon.tech/) and create a free serverless PostgreSQL project.
   * Copy the connection string: `postgresql://user:password@ep-name.region.neon.tech/neondb?sslmode=require`.
2. **Apply FloraChain Schema:**
   * Connect using psql or Neon SQL Editor and run the contents of [`app/models/schema_postgres.sql`](../app/models/schema_postgres.sql).
3. **Deploy Web Service on Render:**
   * Sign up at [render.com](https://render.com/) and click **New Web Service**.
   * Connect your GitHub repository.
   * **Root Directory:** `supplier_platform`
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `gunicorn "app:create_app()"`
   * **Environment Variables:**
     * `FLASK_ENV`: `production`
     * `SECRET_KEY`: `your-random-generated-production-secret-key`
     * `DATABASE_URL`: `postgresql://user:password@ep-name.region.neon.tech/neondb?sslmode=require`
     * `FLORACHAIN_ALLOW_DEMO_ROLE_SWITCH`: `false` (or `true` if teachers need quick role switching)
4. **Deploy:** Click **Create Web Service**. Render builds the service and provides a public HTTPS URL.

---

## 4. Production Security Hardening & Environment Variables

When deploying for public demonstration, the following security measures must be configured:

| Variable Name | Production Setting | Purpose |
|---|---|---|
| `FLASK_ENV` | `production` | Disables debug stack traces on 500 errors, activates secure cookies. |
| `SECRET_KEY` | High-entropy string (min 32 bytes) | Signs session cookies and CSRF tokens. Must remain secret. |
| `SESSION_COOKIE_SECURE` | `True` (auto-enabled in prod) | Restricts cookies to HTTPS transmissions only. |
| `SESSION_COOKIE_HTTPONLY` | `True` (enforced) | Blocks JavaScript access to session cookies (`document.cookie`). |
| `SESSION_COOKIE_SAMESITE` | `Lax` (enforced) | Mitigates cross-site request forgery attacks. |
| `CSRF_ENABLED` | `True` (enforced) | Validates anti-CSRF token on all POST/PUT/PATCH/DELETE requests. |
| `FLORACHAIN_ALLOW_DEMO_ROLE_SWITCH` | `false` (recommended) | Disables `/api/auth/switch-role` endpoint so only valid credentials authenticate. |

### Generating a Secure Secret Key
Generate a cryptographically strong secret key using Python:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 5. Demonstration Data Privacy & Safety

To protect private data and maintain academic integrity:
1. **Never Commit Live Databases:**
   * `supplier_platform/data/florachain.db` is strictly excluded in `.gitignore`.
   * Real customer names, actual bank account numbers, and genuine financial data must never be added to public demo instances.
2. **Pre-Seeded Demonstration Personas:**
   * Use the sanitized baseline records included with the platform:
     * Supplier: `Flora Wholesale Nursery Ltd.` (`supplier@florachain.com`)
     * Buyer Nursery: `Green Roots Retail Nursery` (`nursery@greenroots.com`)
     * System Administrator: `FloraChain Admin` (`admin@florachain.com`)
     * Common Password: `FloraChain2026!`
3. **Database Reset Strategy:**
   * If evaluators create messy test orders, you can reset the SQLite database in seconds by deleting `data/florachain.db` and restarting the application to regenerate fresh baseline records.

---

## 6. Rollback Considerations

* **Local Rollback:** If a Flask process fails, the legacy static server can be started instantly via `python run_legacy.py`.
* **Database Rollback:** The dual-engine architecture maintains SQLite and PostgreSQL schema parity. If testing PostgreSQL and an issue occurs, simply unsetting `DATABASE_URL` reverts the system immediately back to local SQLite without data corruption.

