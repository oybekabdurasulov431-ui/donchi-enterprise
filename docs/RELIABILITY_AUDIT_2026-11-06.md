# DONCHI Enterprise — Reliability and Security Audit (2026-11-06)

## Scope and evidence

GitHub Actions workflow **DONCHI Handler Regression** was run on the isolated reliability branch using Python 3.13, FastAPI TestClient, Node.js 22 syntax checks, and headless Chromium. All tests use a disposable SQLite database and temporary test accounts; they never modify Render's live tenant database.

Last verified run: https://github.com/oybekabdurasulov431-ui/donchi-enterprise/actions/runs/42237250209 — **success**.

### Tested end-to-end API behavior

- Authentication and session access: Super Admin login, owner login, unauthorized requests rejected, role permission boundary
- Super Admin: bootstrap, profile/settings read, plans, branding, notifications, audit history and full SQLite backup
- Store owner: tenant CRUD, user management, product, customer, store settings, exports
- POS: open and close cash shift, sale, debt payment, stock adjustment, expense
- Advanced handlers: branch creation, inter-branch transfer, stock lot receipt, delivery status, supplier invoice/payment, customer CRM
- Safety: cross-tenant header isolation, duplicate sale idempotency, insufficient stock handling, negative stock rejection, forbidden cross-origin mutations, invalid plans
- Security: activating and disabling TOTP 2FA invalidates old sessions and old bearer tokens without terminating the current browser
- UI: Chromium opens Super Admin and Owner navigation pages and all 8 standalone Super Admin settings tabs; no uncaught page JavaScript exceptions in those routes
- Code: backend Python compilation and frontend JavaScript syntax

### Fixes prepared on reliability branch

1. Improved readiness: `/api/health` checks database availability and returns HTTP 503 when inaccessible instead of reporting healthy.
2. Session security: enabling or disabling 2FA rotates the session version, revokes other device sessions and invalidates legacy bearer tokens.
3. Expanded automated tests for multi-tenant, financial consistency, CSRF and session security.

### Outstanding production blockers (must not be reported as fully solved)

1. **Render Free ephemeral SQLite** — app logs have shown "Initial administrator configured" after restarts. Existing accounts, passwords, sessions, sales and backup files can disappear. Use persistent database/storage with tested migration and restore before onboarding real shops; do not deploy blindly.
2. **Live login failures** — Render logs include POST /api/login 401. Without the user's private login details, cannot determine whether user credentials, a reset DB, TOTP, browser cache or a locked account explains each instance. Check from real user session securely; do not send passwords to chat.
3. **Not a comprehensive certification** — UI smoke verifies navigation and JS exception-free rendering, but not every action, device/browser, offline sync conflict, accessibility, network failure, high concurrency or recovery.
4. **Incomplete product features** — automatic billing/plan enforcement, Telegram event-trigger notifications, periodic off-site backups, safe one-click restore and durable data storage have not been implemented.
5. **Persistent service secrets** — signing keys created on an ephemeral drive reset and invalidate sessions. Migrate to environment-held rotating keys or persistent secret management while preserving secure rotation.
6. **Backup handling** — current SQLite backup download includes sensitive account and customer data. Define retention, encryption, access control and restore testing before production.
7. **UI cache** — service worker caching must be re-verified across deployment upgrades, offline/online transitions and hard refreshes.

## Release gate

- [x] CI API handler and Chromium UI regression suite green on test branch
- [x] Security regression for TOTP session rotation green
- [ ] Real user acceptance test of production login and Super Admin actions
- [ ] DB migration to persistent storage and tested backup/restore
- [ ] Full offline/online reconciliation, multi-user concurrency and load testing
- [ ] Live/production rollback plan, metrics and secure error monitoring
- [ ] Release to Render after data safety checks

**Conclusion:** Core demo handlers pass automated checks. DONCHI is not certified error-free or production-ready until the remaining blockers are addressed.
