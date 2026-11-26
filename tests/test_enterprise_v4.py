"""Isolated regression tests for Enterprise 4.0.
Does not connect to production or Railway; creates a temporary SQLite DB.
"""
import os, sqlite3, tempfile, unittest
from contextlib import contextmanager
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.testclient import TestClient

import enterprise_v4

class EnterpriseV4Test(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, 'isolated.sqlite')
        db=sqlite3.connect(self.path)
        db.executescript("""
          CREATE TABLE stores(id TEXT,name TEXT,plan TEXT,status TEXT,created_at TEXT,phone TEXT,address TEXT);
          CREATE TABLE users(id TEXT,store_id TEXT,username TEXT,full_name TEXT,role TEXT,active INTEGER,created_at TEXT);
          CREATE TABLE branches(id TEXT,store_id TEXT,name TEXT);
          CREATE TABLE sales(id TEXT,store_id TEXT,subtotal REAL,debt REAL);
          CREATE TABLE sale_returns(id TEXT,store_id TEXT,total REAL,credit_reduction REAL);
          CREATE TABLE debt_payments(id TEXT,store_id TEXT,amount REAL);
          CREATE TABLE products(id TEXT,store_id TEXT,stock REAL,cost REAL,min_stock REAL,active INTEGER);
          INSERT INTO stores VALUES ('a','Do‘kon A','Business','active','2026-01-01','','');
          INSERT INTO stores VALUES ('b','Do‘kon B','Start','active','2026-01-02','','');
          INSERT INTO users VALUES ('ua','a','owner-a','A egasi','owner',1,'2026-01-01');
          INSERT INTO users VALUES ('ub','b','owner-b','B egasi','owner',1,'2026-01-01');
          INSERT INTO branches VALUES ('ba','a','Asosiy');
          INSERT INTO branches VALUES ('bb','b','Asosiy');
          INSERT INTO sales VALUES ('sa','a',1000,300);
          INSERT INTO sales VALUES ('sb','b',9000,700);
          INSERT INTO debt_payments VALUES ('pa','a',100);
          INSERT INTO products VALUES ('pr-a','a',1,100,2,1);
          INSERT INTO products VALUES ('pr-b','b',4,300,2,1);
        """)
        db.commit();db.close()
        @contextmanager
        def connection():
            c=sqlite3.connect(self.path)
            c.row_factory=sqlite3.Row
            try:yield c
            finally:c.close()
        def rows(db,sql,params=()):return [dict(x) for x in db.execute(sql,params)]
        def row(db,sql,params=()):
            x=db.execute(sql,params).fetchone()
            return dict(x) if x else None
        def role(user,roles):
            if user['role'] not in roles:raise HTTPException(403,'Forbidden')
        def http(status,message):raise HTTPException(status,message)
        def get_user(request:Request):
            name=request.headers.get('X-Test-User','owner-a')
            return {'role':'superadmin','store_id':None} if name=='admin' else {'role':'owner','store_id':'b' if name=='owner-b' else 'a'}
        app=FastAPI()
        enterprise_v4.install(app,get_user,connection,rows,row,role,http,lambda:'2026-11-26')
        self.client=TestClient(app)
    def tearDown(self):self.temp.cleanup()
    def test_superadmin_required(self):
        for path in ('overview','billing','protection','alerts','stores/a'):
            r=self.client.get('/api/v4/platform/'+path,headers={'X-Test-User':'owner-a'})
            self.assertEqual(r.status_code,403,path)
    def test_admin_overview(self):
        r=self.client.get('/api/v4/platform/overview',headers={'X-Test-User':'admin'})
        self.assertEqual(r.status_code,200,r.text)
        d=r.json()
        self.assertEqual(d['totals']['stores'],2)
        self.assertEqual(d['totals']['revenue'],10000)
        self.assertEqual(d['totals']['debt'],900)
    def test_owner_isolation(self):
        r=self.client.get('/api/v4/owner/dashboard',headers={'X-Test-User':'owner-a'})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['store']['id'],'a')
        self.assertEqual(r.json()['sales_total'],1000)
        r=self.client.get('/api/v4/owner/dashboard',headers={'X-Test-User':'owner-b'})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['store']['id'],'b')
        self.assertEqual(r.json()['sales_total'],9000)
    def test_admin_cannot_view_owner_endpoint(self):
        self.assertEqual(self.client.get('/api/v4/owner/dashboard',headers={'X-Test-User':'admin'}).status_code,403)
    def test_360_no_password_hashes(self):
        r=self.client.get('/api/v4/platform/stores/a',headers={'X-Test-User':'admin'})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(len(r.json()['users']),1)
        self.assertNotIn('password_hash',str(r.json()))
if __name__=='__main__':unittest.main()
