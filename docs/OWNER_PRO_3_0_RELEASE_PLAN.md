# DONCHI Owner Pro 3.0 — release gate and implementation plan

Status: **PLANNED / NOT DEPLOYED**. Existing DONCHI 2.0 remains on production.

## Live production findings (2026-11-12)

- Railway project: artistic-possibility; service: donchi-enterprise; environment: production.
- Runtime: Railway deployment is online (1/1 replica).
- Database code: server.py uses SQLite at `DONCHI_DATA_DIR/yempro.sqlite3`; absent `DONCHI_DATA_DIR`, it uses `<repo>/data/yempro.sqlite3`.
- **No Railway volume is mounted**. A successful deployment is not proof that SQLite data is durable. Never run a reset.
- Only named service secrets observed: DONCHI_SUPERADMIN_LOGIN and DONCHI_SUPERADMIN_HASH. Never print or rotate those as part of an upgrade.
- Do not move to PostgreSQL by simply changing an environment variable: server.py currently uses SQLite APIs and requires a tested migration.

## MUST PASS BEFORE PRODUCTION CODE DEPLOY

1. Obtain and verify a complete restorable backup from the live database (including sales, customers, debts, returns, users and audit), stored off-instance. Do not publish backup contents.
2. Provision a persistent data store. If staying on SQLite temporarily, attach an appropriate persistent Railway Volume and point DONCHI_DATA_DIR to its mounted absolute path. A newly attached empty volume does **not** automatically contain old database rows: safely migrate data and confirm row counts and integrity.
3. Verify `PRAGMA quick_check`, row counts and access to backed-up data in a disposable environment; test backup/restore and permissions. Do not echo credentials.
4. Stage migrations, test against a copy of existing data, ensure rollback strategy, and preserve all shop/store_id tenant isolation constraints.
5. Only merge/deploy once data persistence, recovery and auth/session regressions are validated.

## Owner Pro 3.0 requested modules

1. Smart dashboard: accurate revenue, cost of goods, refunds, expenses and profit. Clearly label net profit when costs may be incomplete.
2. Smart warehouse: stock alerts, reorder thresholds, stock valuation based on known acquisition costs.
3. Accounts receivable: partial payments, due dates, nonnegative balances, tenant isolation.
4. Employee center: shifts, cashier performance, permissions and salary reports.
5. Branch command center: consolidated owner-only reports, per-branch stock, permissioned transfers.
6. Cash control: opening/closing cash, cash/card movements, discrepancies and immutable reconciliation.
7. Supplier ledger: purchase orders, purchase costs, invoice history and payable balances.
8. Audit center: append-only actor/time/action/change history; no secret values.
9. Smart alerts: low stock, overdue receivables, returns, unusual discounts; deduplication and owner opt-in.
10. CRM: customer history, optional points/bonuses, traceable cashback liabilities.
11. Reports: reliable Excel/PDF exports; filters, access control and audit trail.
12. AI assistant: later stage, read-only tenant-scoped insights, permission-aware and no uncontrolled actions.

## Existing foundation already in server.py

The current schema contains stores, users, products, customers, sales, sale_items, debt_payments, movements, expenses, audit, cash_shifts, sale_returns, return_items and store_modules. Extend these carefully instead of duplicating them.

## Acceptance criteria (all modules)

- Owner may view only stores/branches the account is authorized for; sellers cannot access owner finance.
- No destructive schema reset, no migration that drops existing columns/data.
- Monetary calculations preserve exact amounts; test refunds, partial payments and stock underflow.
- Responsive desktop/mobile design, dark/light accessible UI, useful empty/error/loading states.
- Offline POS mutations are idempotent and recover from sync conflicts without duplication.
- Regression tests for role access, tenancy, backup recovery, core sales and password/session rotation.
- No sample dashboard figures presented as live financial data.

## Deployment strategy

Implement on feature branches, use draft PRs; do **not** push directly to main while production persistence is unverified. Railway currently auto-deploys main. First release is the persistence/backup safety gate, then owner dashboard and core accounting, then supplier/CRM, then optional AI.
