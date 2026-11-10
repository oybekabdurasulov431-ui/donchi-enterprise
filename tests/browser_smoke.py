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
owner_client=TestClient(server.app)
assert owner_client.post("/api/login",json={"username":"owner_smoke","password":OWNER_PASSWORD}).status_code==200
for name,role in [("seller_smoke","seller"),("warehouse_smoke","warehouse"),("manager_smoke","manager")]:
    created=owner_client.post("/api/users",json={
        "username":name,"full_name":role.title()+" Test","role":role,
        "password":OWNER_PASSWORD
    })
    assert created.status_code==200, created.text

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
            # Cookie persists across full reload: no new password prompt.
            page.reload(wait_until="domcontentloaded")
            page.locator('nav.sidebar-nav').wait_for(timeout=12000)
            assert page.locator('#login-form').count()==0, "Login unexpectedly shown on reload"
            assert page.locator('[data-a="install-app"]').count()>=1, "Install CTA absent"
            for section in sections:
                link=page.locator(f'nav.sidebar-nav [data-a="nav"][data-v="{section}"]')
                if link.count()==0:
                    raise AssertionError(f"{username}: section {section} is missing")
                link.click()
                page.locator('h1').wait_for(timeout=6000)
                page.wait_for_timeout(90)
                if errors:
                    raise AssertionError(f"{username}/{section}: browser errors: {errors}")
            if username=="owner_smoke":
                # Reproduce the real production failure: login session persists,
                # but the browser points at a branch deleted after Render restart.
                page.evaluate("""() => localStorage.setItem(
                    'donchi-clean-branch','deleted-demo-branch')""")
                bootstrap_status=[]
                page.on("response",lambda r: bootstrap_status.append(r.status)
                    if "/api/bootstrap" in r.url else None)
                page.reload(wait_until="domcontentloaded")
                page.locator('nav.sidebar-nav [data-v="dashboard"]').wait_for(timeout=12000)
                page.wait_for_timeout(700)
                assert 200 in bootstrap_status, bootstrap_status
                assert page.evaluate("localStorage.getItem('donchi-clean-branch')") != 'deleted-demo-branch'
                assert not errors, errors
                print("PASS: stale stored branch recovered on session reload",flush=True)
            if username=="owner_smoke":
                # A real write through the browser catches broken buttons,
                # forms and API binding errors that menu-only smoke tests miss.
                page.locator('nav.sidebar-nav [data-v="products"]').click()
                page.locator('[data-a="new-product"]').first.click()
                page.locator('#modal-form input[name="name"]').fill("Browser Product")
                page.locator('#modal-form input[name="sku"]').fill("BROWSER-001")
                page.locator('#modal-form input[name="price"]').fill("12000")
                page.locator('#modal-form input[name="cost"]').fill("8000")
                page.locator('#modal-form input[name="stock"]').fill("4")
                with page.expect_response(lambda r:
                        r.url.endswith("/api/products") and r.request.method == "POST",
                        timeout=15000) as result:
                    page.locator('#modal-form button[type="submit"]').click()
                assert result.value.status == 200, "Product form: " + result.value.text()
                page.get_by_text("Browser Product").first.wait_for(timeout=8000)
                if errors: raise AssertionError("Owner browser form errors: "+str(errors))
                print("PASS: browser product form saved",flush=True)
            if username=="admin_smoke":
                # No more long, overlapping fixed settings button.
                page.locator('[data-a="nav"][data-v="platform"]').click()
                page.locator('.donchi-insight-card').first.wait_for(timeout=5000)
                assert page.get_by_text("Render Free").count()==0
                assert page.locator('.donchi-settings-link').count()==1
                api_status=[]
                page.on("response",lambda response: api_status.append([response.status,response.url]) if "/api/" in response.url else None)
                resp=page.goto(url+"/platform/settings.html",wait_until="domcontentloaded")
                page.wait_for_timeout(900)
                print("STANDALONE STATUS",resp.status,"URL",page.url,flush=True)
                print("STANDALONE BODY",page.locator("body").inner_text()[:1200],flush=True)
                print("STANDALONE API",api_status,"ERRORS",errors,flush=True)
                page.locator("#tabs .tab").first.wait_for(timeout=6000)
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
        check_role("/app/","seller_smoke",OWNER_PASSWORD,
            ["pos","shifts","deliveries","debts","customers","updates","sync"])
        check_role("/app/","warehouse_smoke",OWNER_PASSWORD,
            ["products","inventory","lots","branches","updates","sync"])
        check_role("/app/","manager_smoke",OWNER_PASSWORD,
            ["dashboard","pos","shifts","returns","products","inventory","lots",
             "branches","deliveries","debts","customers","crm","finance",
             "insights","updates","analytics","sync"])
        # Mobile viewport + manual PWA guide. No browser install is faked as success.
        mobile=browser.new_page(viewport={"width":390,"height":844},device_scale_factor=2)
        mobile_errors=[]
        mobile.on("pageerror",lambda error:mobile_errors.append(str(error)))
        mobile.goto(url+"/app/",wait_until="domcontentloaded")
        mobile.locator('input[name="username"]').fill("owner_smoke")
        mobile.locator('input[name="password"]').fill(OWNER_PASSWORD)
        mobile.locator('#login-form button[type="submit"]').click()
        mobile.locator('nav.sidebar-nav').wait_for(timeout=12000)
        assert mobile.locator('[data-a="install-app"]').count()>0
        mobile.locator('[data-a="install-app"]').first.click()
        mobile.locator('#donchi-install-guide').wait_for(timeout=4000)
        assert mobile.get_by_text("o‘rnatish",exact=False).count()>0
        mobile.locator('[data-close-install]').click()
        assert mobile.locator('#donchi-install-guide').count()==0
        mobile.locator('.mobile-toggle').click()
        mobile.locator('.sidebar.open').wait_for(timeout=4000)
        mobile.locator('.sidebar.open [data-v="pos"]').click()
        mobile.locator('.donchi-checkout-warning').wait_for(timeout=5000)
        assert "Kassa smenasi yopiq" in mobile.locator('.donchi-checkout-warning').inner_text()
        assert mobile.locator('[data-a="make-sale"]').is_disabled()
        mobile.locator('.donchi-checkout-warning [data-a="open-shift"]').click()
        mobile.locator('#modal-form').wait_for(timeout=5000)
        assert "Boshlang‘ich" in mobile.locator('#modal-form').inner_text()
        assert not mobile_errors, mobile_errors
        mobile.close()
        browser.close()
        print("PASS: Chromium all five roles (Super Admin, Owner, Manager, Seller, Warehouse) opened permitted panels without JavaScript errors.")
finally:
    process.terminate()
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:process.kill()
    TEMP.cleanup()
