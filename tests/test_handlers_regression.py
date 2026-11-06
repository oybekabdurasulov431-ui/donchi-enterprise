"""Integration checks: Super Admin + store owner + POS, debt, stock, settings.

Runs against a throwaway SQLite database; no production accounts or data.
"""
import os
import sys
import tempfile
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


if __name__=="__main__":
    unittest.main(verbosity=2)
