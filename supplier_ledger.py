"""DONCHI supplier companies, purchase-cost ledger and customer debt timeline."""
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import Request, Depends


def install(app):
    from server import (connection, allrows, onerow, now, uid, audit, money,
                        clean_name, http, get_user, store_from, require_feature,
                        branch_for, adjust_branch)
    schema = """
    CREATE TABLE IF NOT EXISTS supplier_companies(
      id TEXT PRIMARY KEY, store_id TEXT NOT NULL REFERENCES stores(id),
      name TEXT NOT NULL, phone TEXT DEFAULT '', address TEXT DEFAULT '',
      created_at TEXT NOT NULL, UNIQUE(store_id,name));
    CREATE TABLE IF NOT EXISTS supplier_purchases(
      id TEXT PRIMARY KEY, store_id TEXT NOT NULL REFERENCES stores(id),
      company_id TEXT NOT NULL REFERENCES supplier_companies(id),
      bill_id TEXT NOT NULL REFERENCES supplier_bills(id),
      product_id TEXT NOT NULL REFERENCES products(id),
      branch_id TEXT NOT NULL REFERENCES branches(id),
      quantity REAL NOT NULL, unit_cost REAL NOT NULL,
      total REAL NOT NULL, created_at TEXT NOT NULL, created_by TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS supplier_purchases_company ON supplier_purchases(store_id,company_id,created_at);
    """
    with connection() as db:
        db.executescript(schema)
        existing=(db.has_column('customers','customer_type') if hasattr(db,'has_column')
                  else bool(db.execute("SELECT 1 FROM pragma_table_info('customers') WHERE name='customer_type'").fetchone()))
        if not existing:
            db.execute("ALTER TABLE customers ADD COLUMN customer_type TEXT NOT NULL DEFAULT 'person'")

    class CompanyIn(BaseModel):
        name: str
        phone: str = ''
        address: str = ''

    class PurchaseLine(BaseModel):
        product_id: str
        qty: float
        unit_cost: float

    class PurchaseIn(BaseModel):
        company_id: str
        reference: str = ''
        lines: list[PurchaseLine] = Field(min_length=1,max_length=100)
        paid: float = 0
        due_on: Optional[str] = None

    class PayIn(BaseModel):
        amount: float

    def company_snapshot(db,sid):
        companies = allrows(db, 'SELECT * FROM supplier_companies WHERE store_id=? ORDER BY name', (sid,))
        bills = allrows(db, 'SELECT * FROM supplier_bills WHERE store_id=? ORDER BY created_at DESC', (sid,))
        purchases = allrows(db, 'SELECT p.*,pr.name AS product_name FROM supplier_purchases p JOIN products pr ON pr.id=p.product_id WHERE p.store_id=? ORDER BY p.created_at DESC LIMIT 1000', (sid,))
        payments = allrows(db, 'SELECT * FROM supplier_payments WHERE store_id=? ORDER BY created_at DESC LIMIT 1000', (sid,))
        for c in companies:
            own = [b for b in bills if b['supplier']==c['name']]
            c['total'] = round(sum(float(b['amount']) for b in own),2)
            c['paid'] = round(sum(float(b['paid']) for b in own),2)
            c['debt'] = round(c['total']-c['paid'],2)
            c['bills'] = own
            c['purchases'] = [p for p in purchases if p['company_id']==c['id']]
            c['payments'] = [p for p in payments if any(b['id']==p['bill_id'] for b in own)]
        return companies

    @app.get('/api/v6/companies')
    def list_companies(request:Request,user=Depends(get_user)):
        with connection() as db:
            shop=store_from(request,user,db,['owner','manager','warehouse'])
            require_feature(db,shop,'finance')
            return {'companies':company_snapshot(db,shop['id'])}

    @app.post('/api/v6/companies')
    def add_company(payload:CompanyIn,request:Request,user=Depends(get_user)):
        with connection(write=True) as db:
            shop=store_from(request,user,db,['owner','manager'])
            require_feature(db,shop,'finance')
            name=clean_name(payload.name)
            if onerow(db,'SELECT id FROM supplier_companies WHERE store_id=? AND name=?',(shop['id'],name)):
                http(409,'Bu korxona avval qo‘shilgan')
            cid=uid()
            db.execute('INSERT INTO supplier_companies(id,store_id,name,phone,address,created_at) VALUES(?,?,?,?,?,?)',
                (cid,shop['id'],name,payload.phone[:60],payload.address[:250],now()))
            audit(db,shop['id'],user,'SUPPLIER_COMPANY_CREATED',{'id':cid,'name':name})
            return {'ok':True,'id':cid}

    @app.post('/api/v6/purchases')
    def new_purchase(payload:PurchaseIn,request:Request,user=Depends(get_user)):
        with connection(write=True) as db:
            shop=store_from(request,user,db,['owner','manager'])
            require_feature(db,shop,'finance')
            company=onerow(db,'SELECT id,name FROM supplier_companies WHERE store_id=? AND id=?',
                           (shop['id'],payload.company_id))
            if not company:http(404,'Korxona topilmadi')
            branch=branch_for(db,shop['id'],request)
            if len({l.product_id for l in payload.lines})!=len(payload.lines):http(422,'Mahsulot takrorlangan')
            lines=[]; total=0
            for line in payload.lines:
                if line.qty<=0 or line.qty>1e8 or line.qty!=line.qty:http(422,'Miqdor noto‘g‘ri')
                cost=money(line.unit_cost)
                if cost<=0:http(422,'Xarid narxi musbat bo‘lishi kerak')
                product=onerow(db,'SELECT id,name,stock,cost FROM products WHERE id=? AND store_id=? AND active=1',
                               (line.product_id,shop['id']))
                if not product:http(404,'Mahsulot topilmadi')
                total+=round(line.qty*cost,2)
                lines.append((line,product,cost))
            total=round(total,2); paid=money(payload.paid)
            if paid>total+0.01:http(422,'To‘langan pul xarid summasidan ortiq')
            bill_id=uid(); timestamp=now()
            db.execute('INSERT INTO supplier_bills(id,store_id,supplier,reference,amount,paid,due_on,created_at) VALUES(?,?,?,?,?,?,?,?)',
                (bill_id,shop['id'],company['name'],payload.reference[:120],total,paid,payload.due_on,timestamp))
            if paid>0:
                db.execute('INSERT INTO supplier_payments(id,bill_id,store_id,amount,created_at,user_id) VALUES(?,?,?,?,?,?)',
                    (uid(),bill_id,shop['id'],paid,timestamp,user['id']))
            for line,product,cost in lines:
                # Weighted-average acquisition cost; old completed sales remain immutable.
                current=float(product['stock'])
                avg=round((current*float(product['cost'])+line.qty*cost)/(current+line.qty),2)
                db.execute('UPDATE products SET stock=stock+?,cost=? WHERE id=? AND store_id=?',
                    (line.qty,avg,product['id'],shop['id']))
                adjust_branch(db,shop['id'],branch['id'],product['id'],line.qty)
                db.execute('INSERT INTO supplier_purchases VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    (uid(),shop['id'],company['id'],bill_id,product['id'],branch['id'],
                     line.qty,cost,round(line.qty*cost,2),timestamp,user['id']))
                db.execute('INSERT INTO movements(id,store_id,product_id,delta,reason,note,created_at,user_id,branch_id) VALUES(?,?,?,?,?,?,?,?,?)',
                    (uid(),shop['id'],product['id'],line.qty,'korxonadan xarid',
                     company['name']+' / '+payload.reference[:80],timestamp,user['id'],branch['id']))
            audit(db,shop['id'],user,'SUPPLIER_PURCHASE',{'bill_id':bill_id,'company':company['id'],'total':total,'paid':paid})
            return {'ok':True,'bill_id':bill_id,'total':total,'paid':paid,'debt':round(total-paid,2)}

    @app.post('/api/v6/companies/{company_id}/pay')
    def pay_company(company_id:str,payload:PayIn,request:Request,user=Depends(get_user)):
        amount=money(payload.amount)
        if amount<=0:http(422,'To‘lov musbat bo‘lishi kerak')
        with connection(write=True) as db:
            shop=store_from(request,user,db,['owner','manager'])
            require_feature(db,shop,'finance')
            company=onerow(db,'SELECT * FROM supplier_companies WHERE id=? AND store_id=?',(company_id,shop['id']))
            if not company:http(404,'Korxona topilmadi')
            bills=allrows(db,'SELECT id,amount,paid FROM supplier_bills WHERE store_id=? AND supplier=? ORDER BY created_at,id',
                          (shop['id'],company['name']))
            total_due=round(sum(max(0,float(b['amount'])-float(b['paid'])) for b in bills),2)
            if amount>total_due+0.01:http(422,'To‘lov mavjud qarzdan oshmasin')
            remaining=amount
            for b in bills:
                due=round(float(b['amount'])-float(b['paid']),2)
                take=round(min(remaining,due),2)
                if take<=0:continue
                db.execute('UPDATE supplier_bills SET paid=paid+? WHERE id=? AND store_id=?',(take,b['id'],shop['id']))
                db.execute('INSERT INTO supplier_payments(id,bill_id,store_id,amount,created_at,user_id) VALUES(?,?,?,?,?,?)',
                           (uid(),b['id'],shop['id'],take,now(),user['id']))
                remaining=round(remaining-take,2)
                if remaining<=0:break
            audit(db,shop['id'],user,'SUPPLIER_DEBT_PAID',{'company_id':company_id,'amount':amount})
            return {'ok':True,'paid':amount,'remaining_debt':round(total_due-amount,2)}

    @app.get('/api/v6/customers/{customer_id}/ledger')
    def customer_ledger(customer_id:str,request:Request,user=Depends(get_user)):
        with connection() as db:
            shop=store_from(request,user,db,['owner','manager','seller'])
            require_feature(db,shop,'debts')
            customer=onerow(db,'SELECT * FROM customers WHERE id=? AND store_id=?',(customer_id,shop['id']))
            if not customer:http(404,'Mijoz topilmadi')
            sales=allrows(db,'SELECT id,created_at,debt AS amount,subtotal FROM sales WHERE store_id=? AND customer_id=? AND debt>0',(shop['id'],customer_id))
            pays=allrows(db,'SELECT id,created_at,amount,method FROM debt_payments WHERE store_id=? AND customer_id=?',(shop['id'],customer_id))
            returns=allrows(db,'SELECT id,created_at,credit_reduction AS amount FROM sale_returns WHERE store_id=? AND customer_id=? AND credit_reduction>0',(shop['id'],customer_id))
            timeline=[dict(x,kind='debt') for x in sales]+[dict(x,kind='payment') for x in pays]+[dict(x,kind='return') for x in returns]
            timeline.sort(key=lambda x:(x['created_at'],x['id']))
            balance=0
            for e in timeline:
                balance=round(balance+(e['amount'] if e['kind']=='debt' else -e['amount']),2)
                e['balance_after']=balance
            return {'customer':customer,'entries':timeline[::-1],'balance':balance}

    @app.get('/api/v6/today')
    def today_overview(request:Request,user=Depends(get_user)):
        from server import summarize
        with connection() as db:
            shop=store_from(request,user,db,['owner','manager'])
            data=summarize(db,shop)
            companies=company_snapshot(db,shop['id'])
            debts=round(sum(max(0,c['debt']) for c in companies),2)
            return {'today_sales':data['stats']['today'],'today_profit':data['stats']['today_profit'],
                    'customer_debt':data['stats']['debt'],'supplier_debt':debts,
                    'notifications':[{'kind':'daily_profit','text':'Bugungi foyda: '+str(data['stats']['today_profit'])+' so‘m'},
                                     {'kind':'supplier_debt','text':'Korxonalar oldidagi qarz: '+str(debts)+' so‘m'}]}
