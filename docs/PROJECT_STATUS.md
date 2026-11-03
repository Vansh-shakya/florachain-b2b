# 📊 FloraChain B2B — Project Status & Roadmap Tracking

**Document Date:** November 3, 2026  
**Current Phase:** Phase 18 Complete — Documentation & Deployment Preparation  
**Next Phase:** Phase 19 — Real-World Validation & Production Demonstration  
**Active Production Database:** SQLite 3 (`supplier_platform/data/florachain.db`, 14 tables, 43 records intact)  
**Enterprise Test Database:** PostgreSQL 18.6 (`florachain_test`, 14 tables, 43 records verified)  

---

## 1. Roadmap Phase Overview

| Phase | Milestone Name | Status | Verified Deliverables |
|---|---|---|---|
| **Phase 1** | Project Setup & Architecture | ✅ Completed | System blueprint, 3-tier structure, and data flow specifications. |
| **Phase 2** | Frontend Foundation & Theme | ✅ Completed | Vanilla CSS design system, FloraChain brand green (`#063B00`), responsive layout. |
| **Phase 3** | Supplier Dashboard Layout | ✅ Completed | Supplier overview view, KPI cards, and subpage navigation framework. |
| **Phase 4** | Nursery Directory & Delivery Inspection | ✅ Completed | Nursery management modal and dual-party delivery verification logic. |
| **Phase 5** | Plant Management & Catalog Operations | ✅ Completed | Plant table, add/edit/discontinue workflows, category and unit dropdowns. |
| **Phase 6** | Order Management & Lifecycle Staging | ✅ Completed | Order creation modal, multi-item table, line-item pricing, order staging. |
| **Phase 7** | Truck Loading & Logistics Manifests | ✅ Completed | Vehicle and driver logging, loading manifest verification, staging transition. |
| **Phase 8** | Delivered-Sound Wholesale Invoicing | ✅ Completed | Automatic invoice calculation strictly based on accepted sound delivery count. |
| **Phase 9** | Payment Processing & Advance Allocation | ✅ Completed | Recording payments (Bank Transfer, UPI, Cheque), settling invoices, advance credits. |
| **Phase 10** | Due Dates & Agreed Late Interest | ✅ Completed | Negotiated credit periods, daily compounding late-payment interest engine. |
| **Phase 11** | Commercial Account Ledger | ✅ Completed | Double-entry style financial history, account statements, debit/credit audit trail. |
| **Phase 12** | Nursery Buyer Self-Service Portal | ✅ Completed | Buyer dashboard, inbound shipments, purchase orders, statements, ledger modal. |
| **Phase 13** | Flask Application Factory Setup | ✅ Completed | Hardened Flask factory (`create_app`), Blueprint routing, centralized logging. |
| **Phase 14** | PostgreSQL Dual-Engine Adapter | ✅ Completed | Universal adapter for SQLite and PostgreSQL, schema parity, live data migration. |
| **Phase 15** | Authentication & RBAC Hardening | ✅ Completed | Session fixation rotation, CSRF defense, object-level order access controls. |
| **Phase 16** | Frontend/Backend Integration | ✅ Completed | Replaced all simulated client mock data with live REST API backend endpoints. |
| **Phase 17** | Testing & Defect Remediation | ✅ Completed | Comprehensive testing across 12 core workflows, 3 surgical bugfixes applied. |
| **Phase 18** | GitHub & Deployment Preparation | ✅ Completed | Production documentation, `.gitignore` hardening, hosting feasibility analysis. |
| **Phase 19** | Real-World Validation & Launch | ⏳ Pending | Live teacher demonstration, feedback capture, final acceptance. |

---

## 2. Current System Architecture & State

### Database State
* **Default Database Engine:** SQLite 3 in Write-Ahead Logging mode (`PRAGMA journal_mode=WAL`).
* **Relational Schema:** 14 relational tables strictly enforcing foreign keys, unique constraints, and check constraints:
  - `users` (3 baseline accounts: Supplier, Nursery Buyer, Admin)
  - `plants` (6 baseline botanical stock records)
  - `orders` (3 baseline commercial orders)
  - `order_items` (3 order line-item records)
  - `delivery_inspections` (3 inspection logs)
  - `inspection_confirmations` (4 dual-party confirmation signoffs)
  - `inspection_corrections` (0 records; ready for dispute handling)
  - `invoices` (1 baseline invoice generated from sound plants)
  - `invoice_items` (1 invoice line item)
  - `payments` (1 baseline settled payment)
  - `payment_allocations` (1 payment-to-invoice allocation)
  - `deal_agreements` (2 negotiated commercial agreements)
  - `agreement_approvals` (3 agreement approvals)
  - `audit_events` (12 immutable audit log entries)
* **Total Preserved Baseline Records:** Exactly 43 rows across both SQLite and the mirrored PostgreSQL test database.

### Security Posture
* **Authentication:** Password hashing with Werkzeug `scrypt`, server-side session cookies with `HttpOnly`, `SameSite=Lax`, and `Secure` (in production).
* **Cross-Site Request Forgery (CSRF):** CSRF tokens generated per session and validated on all state-changing HTTP methods (`POST`, `PUT`, `PATCH`, `DELETE`).
* **Object-Level Authorization:** Orders and audit logs enforce strict counterparty tenancy (users can only access orders where they are the assigned buyer or seller).
* **Demo Role Switcher:** The demo switcher endpoint (`/api/auth/switch-role`) is strictly restricted to local development environments (`FLORACHAIN_ALLOW_DEMO_ROLE_SWITCH=true`) and returns `403 Forbidden` in production mode.

---

## 3. Verified Quality Assurance & Test Results

* **Python Backend Regression Suite:**
  - `226 tests executed, 226 PASSED, 0 FAILED, 1 SKIPPED` (Live PostgreSQL socket test cleanly skipped when PostgreSQL server is offline).
  - Average execution time: ~96 seconds.
* **Node.js Frontend UI Test Suites:**
  - 9 modular test files (`test_phase4.js` through `test_phase12_ui.js`).
  - Total DOM assertions: 300+ DOM checks and validation workflows.
  - Result: **0 failures across all 9 test suites**.
* **Database Isolation:** All integration and unit tests run against temporary in-memory or throwaway file databases; production databases (`data/florachain.db` and PostgreSQL `florachain_test`) remain 100% untouched.

---

## 4. Known Limitations & Environmental Constraints

1. **Headless Browser Frameworks:**
   - Playwright, Puppeteer, and Selenium drivers are not installed in the local execution environment.
   - *Mitigation:* Comprehensive UI validation is performed via Node.js DOM-based test harnesses, client-server API contract tests, and manual browser verification.
2. **SQLite Ephemeral Filesystem Limitation on Serverless:**
   - Serverless platforms like Vercel or AWS Lambda mount a temporary read-only filesystem with an ephemeral `/tmp` directory that resets on cold starts.
   - *Mitigation:* As analyzed in [`docs/DEPLOYMENT.md`](DEPLOYMENT.md), standard persistent PaaS hosting (PythonAnywhere, Render, Railway) or pairing with a free cloud PostgreSQL database (Neon/Supabase) is required for persistent multi-user data storage.

---

## 5. Next Steps for Phase 19

1. Conduct end-to-end evaluation using realistic nursery ordering scenarios.
2. Gather feedback from college professors and peers on domain modeling, accounting accuracy, and user experience.
3. Review performance telemetry and finalize project presentation materials.

