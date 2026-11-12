"""Owner Pro 3.0 smoke tests, isolated from production data."""
import os
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from datetime import timezone
from fastapi import FastAPI, HTTPException
from starlette.requests import Request
from owner_pro import install


class OwnerProTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=os.path.join(self.tmp.name,"test.db")
        db=sqlite3.connect(self.path)
        db.executescript("""
            CREATE TABLE products(id TEXT, store_id TEXT, sku TEXT,name TEXT,category TEXT,unit TEXT,stock REAL,min_stock REAL,cost REAL,price REAL,active INTEGER);
            CREATE TABLE sales(id TEXT,store_id TEXT,subtotal REAL,cash_paid REAL,card_paid REAL,debt REAL,customer_id TEXT,created_at TEXT);
            CREATE TABLE sale_items(sale_id TEXT,qty REAL,cost REAL);
            CREATE TABLE sale_returns(id TEXT,store_id TEXT,total REAL,customer_id TEXT,credit_reduction REAL,created_at TEXT);
            CREATE TABLE return_items(return_id TEXT,qty REAL,cost REAL);
            CREATE TABLE expenses(store_id TEXT,amount REAL);
            CREATE TABLE debt_payments(store_id TEXT,customer_id TEXT,amount REAL);
            CREATE TABLE customers(id TEXT,store_id TEXT,name TEXT,phone TEXT);
            CREATE TABLE cash_shifts(id TEXT,store_id TEXT,cashier_id TEXT,opening_cash REAL,closing_cash REAL,expected_cash REAL,variance REAL,status TEXT,opened_at TEXT,closed_at TEXT);
            CREATE TABLE users(id TEXT,full_name TEXT);
            CREATE TABLE audit(store_id TEXT,username TEXT,action TEXT,created_at TEXT);
        """)
        db.executemany("INSERT INTO customers VALUES(?,?,?,?)",[("c1","s1","A",""),("c2","s2","B","")])
        db.executemany("INSERT INTO sales VALUES(?,?,?,?,?,?,?,?)",[
            ("a","s1",100,80,0,20,"c1","2026-11-12T00:00:00+00:00"),
            ("b","s2",999999,0,0,999999,"c2","2026-11-12T00:00:00+00:00")])
        db.executemany("INSERT INTO sale_items VALUES(?,?,?)",[("a",1,40),("b",1,2)])
        db.executemany("INSERT INTO products VALUES(?,?,?,?,?,?,?,?,?,?,?)",[
            ("p1","s1","A","Stock A","", "dona",1,3,4,10,1),
            ("p2","s2","B","Stock B","", "dona",0,3,4,10,1)])
        db.commit();db.close()

        @contextmanager
        def connection():
            d=sqlite3.connect(self.path);d.row_factory=sqlite3.Row
            try:yield d
            finally:d.close()
        def onerow(db,query,params=()):
            row=db.execute(query,params).fetchone()
            return dict(row) if row else None
        def allrows(db,query,params=()):
            return [dict(r) for r in db.execute(query,params).fetchall()]
        def role(user,allowed):
            if user["role"] not in allowed:raise HTTPException(403)
        def store_from(request,user,db,allowed=None):
            if user["role"] not in (allowed or ["owner"]):raise HTTPException(403)
            target=request.headers.get("X-Store-ID",user["store_id"])
            if target!=user["store_id"]:raise HTTPException(403)
            return {"id":target,"name":"Test store"}
        def require_feature(db,store,module):pass
        def fake_user():return {"role":"owner","store_id":"s1"}
        app=FastAPI()
        install(app,get_user=fake_user,connection=connection,store_from=store_from,
                onerow=onerow,allrows=allrows,role=role,
                require_feature=require_feature,local_tz=timezone.utc)
        self.routes={r.path:r.endpoint for r in app.routes}

    def tearDown(self):
        self.tmp.cleanup()

    def request(self, headers=()):
        return Request({"type":"http","method":"GET","path":"/","headers":list(headers)})

    def test_owner_isolation(self):
        user={"role":"owner","store_id":"s1"}
        overview=self.routes["/api/owner-pro/overview"](self.request(),user=user)
        self.assertEqual(overview["kpis"]["net_revenue_all_time"],100)
        self.assertEqual(overview["kpis"]["receivables"],20)
        low=self.routes["/api/owner-pro/inventory"](self.request(),user=user)
        self.assertEqual([r["name"] for r in low["low_stock"]],["Stock A"])

    def test_manager_denied(self):
        with self.assertRaises(HTTPException) as e:
            self.routes["/api/owner-pro/overview"](self.request(),user={"role":"manager","store_id":"s1"})
        self.assertEqual(e.exception.status_code,403)

    def test_other_tenant_header_denied(self):
        with self.assertRaises(HTTPException) as e:
            self.routes["/api/owner-pro/overview"](
                self.request([(b"x-store-id",b"s2")]),
                user={"role":"owner","store_id":"s1"})
        self.assertEqual(e.exception.status_code,403)


if __name__=="__main__":
    unittest.main()
