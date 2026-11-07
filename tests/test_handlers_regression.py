"""Integration checks: Super Admin + store owner + POS, debt, stock, settings.

Runs against a throwaway SQLite database; no production accounts or data.
"""
import os
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

TMP = tempfile.TemporaryDirectory(prefix="donchi-handlers-")
os.environ["DONCHI_DATA_DIR"] = TMP.name
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import server
from fastapi.testclient import TestClient

ADMIN_PASSWORD = "TestOnlySuperAdmin_2026@"
OWNER_PASSWORD = "TestOnlyShopOwner_2026@"


class HandlersRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with server.connection(write=True) as db:
            db.execute(
                "INSERT INTO users(id,username,full_name,password_hash,role,store_id,active,created_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (server.uid(), "tester", "Test Administrator", server.pwdhash(ADMIN_PASSWORD),
                 "superadmin", None, 1, server.now()),
            )
        cls.admin = TestClient(server.app)
        r = cls.admin.post("/api/login", json={"username": "tester", "password": ADMIN_PASSWORD})
        assert r.status_code == 200, r.text

    def ok(self, response, code=200):
        self.assertEqual(response.status_code, code, response.text[:1500])
        if code == 200 and "application/json" in response.headers.get("content-type", ""):
            self.assertTrue(response.json().get("ok", True))
            return response.json()
        return {}

    def test_01_public_and_admin_handlers(self):
        self.ok(self.admin.get("/api/health"))
        self.ok(self.admin.get("/api/bootstrap"))
        r = self.ok(self.admin.get("/api/platform-admin/settings"))
        self.assertEqual(r["profile"]["username"], "tester")
        self.assertGreaterEqual(len(r["plans"]), 4)
        self.assertIn("monitor", r)
        unauth = TestClient(server.app)
        self.ok(unauth.get("/api/platform-admin/settings"), 401)
        self.ok(unauth.post("/api/products",json={}), 401)

    def test_02_store_owner_crud_sales_and_debt(self):
        store = self.ok(self.admin.post("/api/stores", json={
            "name": "Demo Shop", "username": "owner_regression",
            "owner_name": "Store Owner", "password": OWNER_PASSWORD,
            "plan": "Business",
        }))["store_id"]
        self.ok(self.admin.post(f"/api/stores/{store}/plan",json={"plan":"Premium"}))
        self.ok(self.admin.post(f"/api/stores/{store}/modules",json={"module":"debts","enabled":True}))
        owner=TestClient(server.app)
        self.ok(owner.post("/api/login",json={"username":"owner_regression","password":OWNER_PASSWORD}))
        boot=self.ok(owner.get("/api/bootstrap"))["data"]
        self.assertEqual(boot["store"]["id"],store)
        self.ok(owner.put("/api/settings",json={"name":"Demo Shop Updated","phone":"998900000000"}))
        self.ok(owner.post("/api/users",json={"username":"seller_regression","full_name":"Seller","role":"seller","password":"OnlyTest_Seller_2026!"}))
        product=self.ok(owner.post("/api/products",json={"name":"Feed","sku":"FEED-001","unit":"qop","price":90000,"cost":60000,"stock":10,"min_stock":1}))["id"]
        customer=self.ok(owner.post("/api/customers",json={"name":"Client One","phone":"998900000001"}))["id"]
        original_branch=self.ok(owner.get("/api/bootstrap"))["data"]["branches"][0]["id"]
        second_branch=self.ok(owner.post("/api/v5/branches",json={"name":"Second Branch","address":"Demo street"}))["id"]
        self.ok(owner.post("/api/v5/branches/transfer",json={
            "from_branch":original_branch,"to_branch":second_branch,"product_id":product,"qty":2
        }))
        self.ok(owner.post("/api/v5/lots",json={"product_id":product,"branch_id":original_branch,
            "lot_code":"LOT-001","qty":3,"unit_cost":60000}))
        delivery=self.ok(owner.post("/api/v5/deliveries",json={"customer_id":customer,"destination":"Test street","fee":5000}))["id"]
        self.ok(owner.post(f"/api/v5/deliveries/{delivery}/status",json={"status":"assigned"}))
        bill=self.ok(owner.post("/api/v5/bills",json={"supplier":"Test Supplier","amount":50000}))["id"]
        self.ok(owner.post(f"/api/v5/bills/{bill}/pay",json={"amount":10000}))
        self.ok(owner.put(f"/api/v5/customers/{customer}/crm",json={
            "tag":"VIP","notes":"Automation test","credit_limit":200000,"loyalty_points":10
        }))
        self.ok(owner.post("/api/shifts/open",json={"opening_cash":1000}))
        sale=self.ok(owner.post("/api/sales",json={
            "client_id":str(uuid.uuid4()),"customer_id":customer,
            "lines":[{"product_id":product,"qty":2}],"cash_paid":100000,"card_paid":0
        }))
        self.assertIn("id",sale)
        self.ok(owner.post("/api/debts/pay",json={"client_id":str(uuid.uuid4()),"customer_id":customer,"amount":50000,"method":"cash"}))
        self.ok(owner.post("/api/inventory/adjust",json={"product_id":product,"delta":2,"reason":"Kirim"}))
        self.ok(owner.get("/api/bootstrap"))
        self.ok(owner.post("/api/expenses",json={"category":"Rent","amount":3000,"note":"test"}))
        self.ok(owner.post("/api/shifts/close",json={"counted_cash":0}))
        self.ok(owner.get("/api/export"))
        self.ok(owner.get("/api/platform-admin/settings"),403)

    def test_03_platform_admin_security_and_plans(self):
        r=self.ok(self.admin.put("/api/platform-admin/plans/Business",json={
            "price":99000,"days":30,"max_users":6,"max_branches":2
        }))
        r=self.ok(self.admin.put("/api/platform-admin/brand",json={
            "brand_name":"DONCHI","tagline":"Store automation","support_phone":"",
            "support_email":"","logo":""
        }))
        r=self.ok(self.admin.put("/api/platform-admin/notifications",json={
            "telegram_enabled":False,"telegram_chat_id":"",
            "notify_new_store":True,"notify_service_errors":True
        }))
        r=self.ok(self.admin.get("/api/platform-admin/settings"))
        self.assertTrue(r["audit"])
        r=self.admin.get("/api/platform-admin/backup")
        self.assertEqual(r.status_code,200,r.text[:1000])
        self.assertGreater(len(r.content),1000)
        self.ok(self.admin.post("/api/platform-admin/sessions/revoke-others"))
        self.ok(self.admin.get("/api/bootstrap"))

    def test_04_validation_permissions_and_static_routes(self):
        self.ok(self.admin.get("/api/health"))
        self.ok(self.admin.get("/platform/"))
        self.ok(self.admin.get("/platform/settings.html"))
        self.ok(self.admin.get("/platform-admin.js"))
        self.ok(self.admin.get("/app.js"))
        self.ok(self.admin.post("/api/stores",json={"name":"","username":"bad","owner_name":"x","password":"short"}),422)

    def test_05_tenant_isolation_and_financial_integrity(self):
        # Two independent customers must never see or change one another's data.
        shops = []
        owners = []
        for suffix in ("alpha", "beta"):
            shop_id = self.ok(self.admin.post("/api/stores", json={
                "name": f"Isolated {suffix}", "username": f"owner_{suffix}",
                "owner_name": f"Owner {suffix}", "password": OWNER_PASSWORD, "plan": "Business"
            }))["store_id"]
            shop_client = TestClient(server.app)
            self.ok(shop_client.post("/api/login", json={
                "username": f"owner_{suffix}", "password": OWNER_PASSWORD
            }))
            shops.append(shop_id)
            owners.append(shop_client)

        alpha, beta = owners
        self.ok(alpha.get("/api/bootstrap", headers={"X-Store-ID": shops[1]}), 403)
        self.ok(beta.get("/api/bootstrap", headers={"X-Store-ID": shops[0]}), 403)
        self.ok(alpha.post("/api/products", json={
            "name": "Cross-tenant", "sku": "A-FAIL", "unit": "dona",
            "price": 10, "stock": 1
        }, headers={"X-Store-ID": shops[1]}), 403)
        self.ok(alpha.get("/api/platform-admin/settings"), 403)

        pid = self.ok(alpha.post("/api/products", json={
            "name": "Single item", "sku": "A-ONE", "unit": "dona",
            "price": 100, "cost": 50, "stock": 1
        }))["id"]
        self.ok(alpha.post("/api/shifts/open", json={"opening_cash": 0}))
        client_id = str(uuid.uuid4())
        sale = {
            "client_id": client_id, "lines": [{"product_id": pid, "qty": 2}],
            "cash_paid": 200, "card_paid": 0
        }
        self.ok(alpha.post("/api/sales", json=sale), 409)  # cannot oversell
        sale["lines"][0]["qty"] = 1
        sale["cash_paid"] = 100
        first = self.ok(alpha.post("/api/sales", json=sale))
        second = self.ok(alpha.post("/api/sales", json=sale))
        self.assertEqual(first["id"], second["id"])
        self.assertTrue(second.get("duplicate"))
        self.ok(alpha.post("/api/sales", json={**sale, "client_id": str(uuid.uuid4())}), 409)
        self.ok(alpha.post("/api/inventory/adjust", json={
            "product_id": pid, "delta": -1, "reason": "Tekshiruv"
        }), 409)
        alpha_data = self.ok(alpha.get("/api/bootstrap"))["data"]
        beta_data = self.ok(beta.get("/api/bootstrap"))["data"]
        self.assertEqual(next(x for x in alpha_data["products"] if x["id"] == pid)["stock"], 0)
        self.assertFalse(any(x["id"] == pid for x in beta_data.get("products", [])))

        # A forged cross-origin mutation must be rejected when using browser cookies.
        self.ok(alpha.post("/api/expenses", json={
            "category": "Test", "amount": 1
        }, headers={"Origin": "https://attacker.invalid"}), 403)

    def test_06_validation_and_permissions(self):
        self.ok(self.admin.post("/api/stores", json={
            "name": "Wrong plan", "username": "wrong_plan",
            "owner_name": "Test", "password": OWNER_PASSWORD, "plan": "FakePlan"
        }), 422)
        self.ok(self.admin.post("/api/products", json={
            "name": "Forbidden", "sku": "FORBIDDEN", "unit": "qop",
            "price": 1, "stock": 1
        }), 403)
        no_session = TestClient(server.app)
        self.ok(no_session.get("/api/bootstrap"), 401)
        self.ok(no_session.get("/api/platform-admin/backup"), 401)

    def test_07_2fa_revokes_old_sessions_and_bearer_tokens(self):
        # The first browser remains authenticated after enabling 2FA, but
        # other browsers and old bearer tokens must be invalidated.
        from platform_admin import _otp
        second = TestClient(server.app)
        old_login = self.ok(second.post("/api/login", json={
            "username": "tester", "password": ADMIN_PASSWORD
        }))
        old_bearer = old_login["token"]
        self.ok(second.get("/api/bootstrap"))
        secret = self.ok(self.admin.post("/api/platform-admin/2fa/start"))["secret"]
        code = _otp(secret, int(time.time() // 30))
        self.ok(self.admin.post("/api/platform-admin/2fa/confirm", json={"code": code}))
        self.ok(self.admin.get("/api/platform-admin/settings"))
        self.ok(second.get("/api/bootstrap"), 401)
        unauth = TestClient(server.app)
        self.ok(unauth.get("/api/bootstrap", headers={
            "Authorization": "Bearer " + old_bearer
        }), 401)
        self.ok(unauth.post("/api/login", json={
            "username": "tester", "password": ADMIN_PASSWORD
        }), 401)
        # A fresh TOTP login should succeed. The code must not be replayed,
        # so test the current auth session instead of consuming it at login.
        disable_code = _otp(secret, int(time.time() // 30))
        self.ok(self.admin.post("/api/platform-admin/2fa/disable", json={
            "code": disable_code, "current_password": ADMIN_PASSWORD
        }))
        self.ok(self.admin.get("/api/bootstrap"))
        self.ok(unauth.post("/api/login", json={
            "username": "tester", "password": ADMIN_PASSWORD
        }))

    def test_08_atomic_modules_and_non_finite_amounts(self):
        # Batch update must reject invalid values without saving a partial result.
        shop = self.ok(self.admin.post("/api/stores", json={
            "name": "Atomic Test Store", "username": "owner_atomic",
            "owner_name": "Atomic Owner", "password": OWNER_PASSWORD, "plan": "Business"
        }))["store_id"]
        modules = {
            "debts": False, "returns": True, "analytics": True, "delivery": False,
            "finance": True, "crm": False, "branches": True, "telegram": False,
            "insights": True
        }
        good = self.ok(self.admin.put(f"/api/stores/{shop}/modules", json={"modules": modules}))
        self.assertEqual(good["modules"], modules)
        self.ok(self.admin.put(f"/api/stores/{shop}/modules", json={
            "modules": {**modules, "debts": True, "crm": "invalid"}
        }), 422)
        self.ok(self.admin.put(f"/api/stores/{shop}/modules", json={
            "modules": {"debts": True}
        }), 422)
        with server.connection() as db:
            flags = server.features_for(db, shop)
        self.assertEqual(flags, modules)

        owner = TestClient(server.app)
        self.ok(owner.post("/api/login", json={
            "username": "owner_atomic", "password": OWNER_PASSWORD
        }))
        self.ok(owner.post("/api/products", json={
            "name": "Valid Product", "sku": "ATOM-1", "unit": "dona",
            "price": 10, "stock": 0
        }))
        for invalid in ("Infinity", "-Infinity", "NaN"):
            # Send malformed JSON numeric tokens directly: httpx rightly refuses
            # non-finite floats when encoding its json= argument.
            response = owner.post("/api/expenses",
                content='{"category":"Invalid","amount":'+invalid+'}',
                headers={"Content-Type":"application/json"})
            self.assertEqual(response.status_code, 422, response.text[:800])
            response = owner.post("/api/products",
                content='{"name":"Bad Product","sku":"BAD-NUM","unit":"dona","price":'+invalid+',"stock":1}',
                headers={"Content-Type":"application/json"})
            self.assertEqual(response.status_code, 422, response.text[:800])


if __name__=="__main__":
    unittest.main(verbosity=2)
