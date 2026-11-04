"""Clean DB regression: no automatic store/customer/user; first-run account creation only."""
from pathlib import Path
import tempfile,os,sys
from fastapi.testclient import TestClient
with tempfile.TemporaryDirectory(prefix='donchi-clean-test-') as tmp:
    os.environ['DONCHI_DATA_DIR']=tmp
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    import server
    with server.connection() as db:
        for table in ('users','stores','products','customers','sales','debt_payments','releases','demo_inquiries'):
            assert server.onerow(db,f'SELECT COUNT(*) c FROM {table}')['c']==0,table
    from unittest.mock import patch
    import setup_admin
    with patch('getpass.getpass',side_effect=['TemporaryLocalTest234!','TemporaryLocalTest234!']):
        assert setup_admin.main()==0
    with server.connection() as db:
        row=server.onerow(db,'SELECT * FROM users LIMIT 1')
        assert row['username']=='oybek.py' and row['role']=='superadmin'
        assert server.checkpwd('TemporaryLocalTest234!',row['password_hash'])
        assert server.onerow(db,'SELECT COUNT(*) c FROM stores')['c']==0
    client=TestClient(server.app)
    r=client.post('/api/login',json={'username':'oybek.py','password':'TemporaryLocalTest234!'})
    assert r.status_code==200,r.text
    admin=client.get('/api/bootstrap')
    assert admin.status_code==200,admin.text
    assert admin.json()['data']['platform']==[]
    assert client.post('/api/login',json={'username':'superadmin','password':'Demo2026!'}).status_code==401
    assert server.onerow(server.sql_conn(),'SELECT COUNT(*) c FROM stores')['c']==0
print('PASS DONCHI Clean Start: zero stores, custom owner, salted hash, login and empty platform')
