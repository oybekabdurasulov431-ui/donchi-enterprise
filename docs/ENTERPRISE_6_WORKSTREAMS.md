# DONCHI Enterprise — 6-workstream delivery record
Date: 2026-11-08

## Status
This pull request is an **incremental reliability release**, NOT a finished
PostgreSQL migration, payment integration, high-availability system, or promise
of zero defects. Keep the app on demo data until durable storage is deployed.

## 1. Durable data and backups
- Current backend: SQLite at `DONCHI_DATA_DIR/yempro.sqlite3`.
- Current Render service: Free Docker, no persistent disk and no managed
  Postgres database attached. A fresh container may have an empty database.
- Implemented now: authenticated Super Admin SQLite download verified by
  `PRAGMA quick_check(1)`; database diagnostics expose storage warnings.
- Not implemented: automated off-site backups, tested restore, persistent
  PostgreSQL database and automatic schema migrations.
- Production path:
  1. Provision an approved persistent managed database and arrange funding,
     retention, encryption and billing controls with the account owner.
  2. Port SQL and schema (SQLite `?` placeholders, `PRAGMA`, conflict syntax,
     transactions and time types) and run tenant-isolation regression tests.
  3. Export a consistent SQLite snapshot, validate its integrity, load it into
     a staging DB, compare table row counts and key business totals.
  4. Test a fully reversed rollback and a separate end-to-end restore.
  5. Switch the application using versioned migrations and monitored rollout.
  6. Enable scheduled off-site encrypted backups with tested retention policy.
- **Do not** pretend switching `DATABASE_URL` alone migrates this codebase.

## 2. Super Admin
- Existing features: stores, plans, modules, notifications configuration,
  security, audit, backup, monitor.
- Implemented now: display database integrity, backup and persistence warnings
  without claiming automatic backup is active.
- Remaining: payment provider integration, audited billing lifecycle and
  organization-wide alerting with delivery proof.

## 3. POS and inventory
- Existing regression suite covers sales idempotency, insufficient stock,
  tenant boundaries, shift handling, returns and debt handlers.
- Implemented now: capture an immutable price/name snapshot for receipts.
  A later product edit cannot silently change the displayed receipt total.
- Remaining: full device printer and barcode compatibility verification and
  stress testing with concurrent checkouts.

## 4. Offline / online
- Existing IndexedDB outbox uses stable client IDs.
- Implemented now: a failed conflict pauses replay, displays an error, and
  requires explicit user action before retry; no silent repeated writes.
- Remaining: cross-device reconciliation and audit trails across conflict
  resolution, plus browser storage/retention failure testing.

## 5. Monitoring and tests
- Existing CI: backend compilation, JavaScript syntax, API regression and
  Chromium navigation smoke across Super Admin, Owner, Manager, Seller and
  Warehouse roles.
- Implemented now: backup integrity assertions, database health visibility,
  and a real browser product-creation test.
- Remaining: error reporting/alert destinations, SLOs, load tests,
  scheduled backups and disaster recovery drills.

## 6. UI / UX
- Implemented now: mobile overflow/long-number responsiveness and clearer
  Super Admin storage status; do not hide data-loss warnings.
- Remaining: accessibility audit, screen-reader/keyboard passes,
  task-based usability studies, and receipt printer validation.

## Release gate
- [ ] GitHub Actions test suite passes
- [ ] Deploy stays healthy after a cold restart
- [ ] Super Admin can view monitoring and download verified backup
- [ ] Owner can add product, customer and sell successfully
- [ ] Offline rejected queue operations require human review
- [ ] Data migration and restore are completed before real customers

All tests use disposable demo databases. A green build is evidence of test
coverage, not a guarantee of no production bugs.
