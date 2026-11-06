"""Chromium UI smoke tests using a disposable database and real FastAPI server."""
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
TEMP=tempfile.TemporaryDirectory(prefix="donchi-browser-test-")
os.environ["DONCHI_DATA_DIR"]=TEMP.name
sys.path.insert(0,str(ROOT))
import server

OWNER_PASSWORD="OwnerOnlyIntegrationTest2026!"
ADMIN_PASSWORD="AdminOnlyIntegrationTest2026!"

with server.connection(write=True) as db:
    db.execute(
        "INSERT INTO users(id,username,full_name,password_hash,role,store_id,active,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (server.uid(),"admin_smoke","Test Admin",server.pwdhash(ADMIN_PASSWORD),"superadmin",None,1,server.now())
    )
from fastapi.testclient import TestClient
tc=TestClient(server.app)
assert tc.post("/api/login",json={"username":"admin_smoke","password":ADMIN_PASSWORD}).status_code==200
res=tc.post("/api/stores",json={"name":"Browser Test Store","username":"owner_smoke",
    "owner_name":"Owner Test","password":OWNER_PASSWORD,"plan":"Business"})
assert res.status_code==200, res.text

sock=socket.socket();sock.bind(("127.0.0.1",0));port=sock.getsockname()[1];sock.close()
url=f"http://127.0.0.1:{port}"
process=subprocess.Popen([sys.executable,"-m","uvicorn","server:app","--host","127.0.0.1","--port",str(port)],
    cwd=ROOT,env=os.environ.copy(),stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
try:
    for _ in range(80):
        try:
            if httpx.get(url+"/api/health",timeout=1).status_code==200: break
        except Exception: pass
        time.sleep(.2)
    else: raise RuntimeError("Server did not start")
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=["--no-sandbox"])
        def check_role(path,username,password,sections):
            page=browser.new_page()
            errors=[]
            page.on("pageerror",lambda error:errors.append(str(error)))
            page.goto(url+path,wait_until="domcontentloaded")
            page.locator('input[name="username"]').fill(username)
            page.locator('input[name="password"]').fill(password)
            page.locator('form#login-form button[type="submit"]').click()
            page.locator('nav.sidebar-nav').wait_for(timeout=12000)
            for section in sections:
                link=page.locator(f'nav.sidebar-nav [data-a="nav"][data-v="{section}"]')
                if link.count()==0:
                    raise AssertionError(f"{username}: section {section} is missing")
                link.click()
                page.locator('h1').wait_for(timeout=6000)
                page.wait_for_timeout(90)
                if errors:
                    raise AssertionError(f"{username}/{section}: browser errors: {errors}")
            if username=="admin_smoke":
                page.goto(url+"/platform/settings.html",wait_until="domcontentloaded")
                page.locator("#tabs .tab").first.wait_for(timeout=12000)
                for label in ["Profil","Xavfsizlik","Platforma","Tariflar","Bildirishnomalar","Audit","Zaxira nusxa","Monitoring"]:
                    page.get_by_role("button",name=label,exact=True).click()
                    page.locator(".card").first.wait_for(timeout=5000)
                if errors: raise AssertionError("standalone settings: "+str(errors))
            page.close()
        check_role("/platform/","admin_smoke",ADMIN_PASSWORD,
            ["platform","releases-admin","inquiries","platform-settings"])
        check_role("/app/","owner_smoke",OWNER_PASSWORD,
            ["dashboard","pos","shifts","returns","products","inventory",
             "lots","branches","deliveries","debts","customers","crm","finance",
             "insights","telegram","updates","security","analytics","team","settings","sync"])
        browser.close()
        print("PASS: Chromium Super Admin and Owner UI pages opened without JS errors.")
finally:
    process.terminate()
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:process.kill()
    TEMP.cleanup()
