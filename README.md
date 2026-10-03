# Nursery Supply Management Platform

A specialized B2B web application designed for the commercial plant nursery industry, connecting **Suppliers** (growers/wholesalers) with **Nurseries** (retailers/landscapers).

---

## 🌿 Core Business Workflow

1. **Order Placement:** Nursery browses catalog and places an order for plant batches.
2. **Order Staging:** Supplier prepares, tags, and stages the plants.
3. **Truck Dispatch:** Supplier loads the transport vehicle and logs truck & driver details.
4. **Delivery & Inspection:** Nursery receives the truck, physically counts the plants, and records verified sound count vs damaged/rejected count.
5. **Invoice Generation:** An invoice is automatically generated strictly based on verified delivered plants.
6. **Payment & Balance Tracking:** Advance payments and settlements are recorded, keeping a real-time balance due.
7. **Due Date & Late Interest:** Due dates are tracked, and agreed late-payment interest is calculated for overdue invoices.
8. **Transaction Ledger:** Complete double-entry style financial history and account statements are maintained.

---

## 🛠 Technology Stack

* **Frontend:** HTML5, CSS3, JavaScript (Vanilla, no framework)
* **Backend:** Python Flask
* **Database:** PostgreSQL
* **Version Control:** Git & GitHub

---

## 📁 Project Structure

```text
supplier_platform/
├── .gitignore
├── README.md
├── requirements.txt
├── app/
│   ├── models/         # Database models
│   ├── routes/         # API routes & page endpoints
│   ├── services/       # Calculation engines (invoices, ledger, interest)
│   ├── static/         # CSS, JS, and image assets
│   └── templates/      # HTML views
└── tests/              # Automated unit and integration tests
```

---

## 🚀 Development Phases

- [x] **Phase 0:** Technical planning & system architecture
- [ ] **Phase 1:** Project setup & wireframe mockups (Frontend HTML/CSS prototypes)
- [ ] **Phase 2:** Database schema design & user authentication
- [ ] **Phase 3:** Plant catalog & order placement flow
- [ ] **Phase 4:** Dispatch & delivery verification system
- [ ] **Phase 5:** Invoicing, payments, late-interest calculation & ledger
- [ ] **Phase 6:** Automated testing & deployment
