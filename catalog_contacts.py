"""Tenant-isolated categories, editable customer/company records and supplier returns."""
from pydantic import BaseModel
from fastapi import Request, Depends


def install(app):
    from server import (connection, allrows, onerow, now, uid, audit, clean_name,
                        money, http, get_user, store_from, branch_for, adjust_branch)

    with connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS product_categories(
          id TEXT PRIMARY KEY, store_id TEXT NOT NULL REFERENCES stores(id),
          name TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL, UNIQUE(store_id,name));
        CREATE TABLE IF NOT EXISTS company_purchase_returns(
          id TEXT PRIMARY KEY,store_id TEXT NOT NULL REFERENCES stores(id),
          purchase_line_id TEXT NOT NULL REFERENCES company_purchase_lines(id),
          company_id TEXT NOT NULL REFERENCES supplier_companies(id),
          bill_id TEXT NOT NULL REFERENCES supplier_bills(id),
          product_id TEXT NOT NULL REFERENCES products(id),
          branch_id TEXT NOT NULL REFERENCES branches(id),
          quantity REAL NOT NULL,amount REAL NOT NULL,created_at TEXT NOT NULL,
          user_id TEXT NOT NULL REFERENCES users(id));
        CREATE INDEX IF NOT EXISTS company_returns_store
          ON company_purchase_returns(store_id,created_at);
        """)
        existing=(db.has_column('customers','active') if hasattr(db,'has_column')
                  else bool(db.execute("SELECT 1 FROM pragma_table_info('customers') WHERE name='active'").fetchone()))
        if not existing:db.execute("ALTER TABLE customers ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
        existing=(db.has_column('supplier_companies','active') if hasattr(db,'has_column')
                  else bool(db.execute("SELECT 1 FROM pragma_table_info('supplier_companies') WHERE name='active'").fetchone()))
        if not existing:db.execute("ALTER TABLE supplier_companies ADD COLUMN active INTEGER NOT NULL DEFAULT 1")

    class NameIn(BaseModel):
        name:str

    class CustomerEdit(BaseModel):
        name:str
        phone:str=''
        address:str=''
        customer_type:str='person'

    class CompanyEdit(BaseModel):
        name:str
        phone:str=''
        address:str=''

    class ReturnIn(BaseModel):
        qty:float

    @app.get('/api/v8/categories')
    def categories(request:Request,user=Depends(get_user)):
        with connection() as db:
            shop=store_from(request,user,db,['owner','manager','warehouse'])
            rows=allrows(db,'SELECT * FROM product_categories WHERE store_id=? AND active=1 ORDER BY name',(shop['id'],))
            existing={r['name'] for r in rows}
            products=allrows(db,"SELECT DISTINCT category FROM products WHERE store_id=? AND active=1 AND category<>''",(shop['id'],))
            for p in products:
                if p['category'] not in existing:rows.append({'id':None,'name':p['category'],'store_id':shop['id'],'active':1})
            return {'items':sorted(rows,key=lambda x:x['name'].lower())}

    @app.post('/api/v8/categories')
    def create_category(payload:NameIn,request:Request,user=Depends(get_user)):
        with connection(write=True) as db:
            shop=store_from(request,user,db,['owner','manager'])
            name=clean_name(payload.name,70)
            row=onerow(db,'SELECT id,active FROM product_categories WHERE store_id=? AND name=?',(shop['id'],name))
            if row:
                if row['active']:http(409,'Kategoriya avval mavjud')
                db.execute('UPDATE product_categories SET active=1 WHERE id=?',(row['id'],))
                cid=row['id']
            else:
                cid=uid()
                db.execute('INSERT INTO product_categories(id,store_id,name,active,created_at) VALUES(?,?,?,?,?)',(cid,shop['id'],name,1,now()))
            audit(db,shop['id'],user,'CATEGORY_CREATED',{'id':cid,'name':name})
            return {'ok':True,'id':cid}

    @app.put('/api/v8/categories/{category_id}')
    def edit_category(category_id:str,payload:NameIn,request:Request,user=Depends(get_user)):
        with connection(write=True) as db:
            shop=store_from(request,user,db,['owner','manager'])
            row=onerow(db,'SELECT * FROM product_categories WHERE id=? AND store_id=? AND active=1',(category_id,shop['id']))
            if not row:http(404,'Kategoriya topilmadi')
            name=clean_name(payload.name,70)
            if onerow(db,'SELECT id FROM product_categories WHERE store_id=? AND name=? AND id<>?',(shop['id'],name,category_id)):http(409,'Kategoriya nomi band')
            db.execute('UPDATE products SET category=? WHERE store_id=? AND category=?',(name,shop['id'],row['name']))
            db.execute('UPDATE product_categories SET name=? WHERE id=?',(name,category_id))
            audit(db,shop['id'],user,'CATEGORY_RENAMED',{'from':row['name'],'to':name})
            return {'ok':True}

    @app.delete('/api/v8/categories/{category_id}')
    def delete_category(category_id:str,request:Request,user=Depends(get_user)):
        with connection(write=True) as db:
            shop=store_from(request,user,db,['owner','manager'])
            row=onerow(db,'SELECT * FROM product_categories WHERE id=? AND store_id=? AND active=1',(category_id,shop['id']))
            if not row:http(404,'Kategoriya topilmadi')
            used=onerow(db,'SELECT COUNT(*) AS n FROM products WHERE store_id=? AND active=1 AND category=?',(shop['id'],row['name']))['n']
            if used:http(409,'Avval ushbu kategoriyadagi mahsulotlarni boshqa kategoriyaga o‘tkazing')
            db.execute('UPDATE product_categories SET active=0 WHERE id=?',(category_id,))
            audit(db,shop['id'],user,'CATEGORY_ARCHIVED',{'id':category_id})
            return {'ok':True}

    @app.put('/api/v8/customers/{customer_id}')
    def update_customer(customer_id:str,payload:CustomerEdit,request:Request,user=Depends(get_user)):
        if payload.customer_type not in ('person','shop'):http(422,'Mijoz turi noto‘g‘ri')
        with connection(write=True) as db:
            shop=store_from(request,user,db,['owner','manager'])
            row=onerow(db,'SELECT id FROM customers WHERE id=? AND store_id=? AND active=1',(customer_id,shop['id']))
            if not row:http(404,'Mijoz topilmadi')
            db.execute('UPDATE customers SET name=?,phone=?,address=?,customer_type=? WHERE id=? AND store_id=?',
                       (clean_name(payload.name),payload.phone[:60],payload.address[:180],payload.customer_type,customer_id,shop['id']))
            audit(db,shop['id'],user,'CUSTOMER_EDITED',{'id':customer_id})
            return {'ok':True}

    @app.delete('/api/v8/customers/{customer_id}')
    def archive_customer(customer_id:str,request:Request,user=Depends(get_user)):
        with connection(write=True) as db:
            shop=store_from(request,user,db,['owner','manager'])
            row=onerow(db,'SELECT id FROM customers WHERE id=? AND store_id=? AND active=1',(customer_id,shop['id']))
            if not row:http(404,'Mijoz topilmadi')
            total=onerow(db,'SELECT COALESCE(SUM(debt),0) AS d FROM sales WHERE store_id=? AND customer_id=?',(shop['id'],customer_id))['d']
            paid=onerow(db,'SELECT COALESCE(SUM(amount),0) AS p FROM debt_payments WHERE store_id=? AND customer_id=?',(shop['id'],customer_id))['p']
            returned=onerow(db,'SELECT COALESCE(SUM(credit_reduction),0) AS r FROM sale_returns WHERE store_id=? AND customer_id=?',(shop['id'],customer_id))['r']
            if float(total)-float(paid)-float(returned)>0.01:http(409,'Avval mijozning qarzini yoping')
            db.execute('UPDATE customers SET active=0 WHERE id=? AND store_id=?',(customer_id,shop['id']))
            audit(db,shop['id'],user,'CUSTOMER_ARCHIVED',{'id':customer_id})
            return {'ok':True}

    @app.put('/api/v8/companies/{company_id}')
    def update_company(company_id:str,payload:CompanyEdit,request:Request,user=Depends(get_user)):
        with connection(write=True) as db:
            shop=store_from(request,user,db,['owner','manager'])
            row=onerow(db,'SELECT * FROM supplier_companies WHERE id=? AND store_id=? AND active=1',(company_id,shop['id']))
            if not row:http(404,'Korxona topilmadi')
            name=clean_name(payload.name)
            if onerow(db,'SELECT id FROM supplier_companies WHERE store_id=? AND name=? AND id<>?',(shop['id'],name,company_id)):http(409,'Bu nom band')
            db.execute('UPDATE supplier_bills SET supplier=? WHERE store_id=? AND supplier=?',(name,shop['id'],row['name']))
            db.execute('UPDATE supplier_companies SET name=?,phone=?,address=? WHERE id=? AND store_id=?',
                       (name,payload.phone[:60],payload.address[:250],company_id,shop['id']))
            audit(db,shop['id'],user,'SUPPLIER_COMPANY_EDITED',{'id':company_id})
            return {'ok':True}

    @app.delete('/api/v8/companies/{company_id}')
    def archive_company(company_id:str,request:Request,user=Depends(get_user)):
        with connection(write=True) as db:
            shop=store_from(request,user,db,['owner','manager'])
            row=onerow(db,'SELECT * FROM supplier_companies WHERE id=? AND store_id=? AND active=1',(company_id,shop['id']))
            if not row:http(404,'Korxona topilmadi')
            bills=allrows(db,'SELECT amount,paid FROM supplier_bills WHERE store_id=? AND supplier=?',(shop['id'],row['name']))
            if sum(float(b['amount'])-float(b['paid']) for b in bills)>0.01:http(409,'Avval korxona qarzini yoping')
            db.execute('UPDATE supplier_companies SET active=0 WHERE id=? AND store_id=?',(company_id,shop['id']))
            audit(db,shop['id'],user,'SUPPLIER_COMPANY_ARCHIVED',{'id':company_id})
            return {'ok':True}

    @app.post('/api/v8/company-purchases/{line_id}/return')
    def return_to_supplier(line_id:str,payload:ReturnIn,request:Request,user=Depends(get_user)):
        with connection(write=True) as db:
            shop=store_from(request,user,db,['owner','manager'])
            line=onerow(db,'SELECT * FROM company_purchase_lines WHERE id=? AND store_id=?',(line_id,shop['id']))
            if not line:http(404,'Xarid qatori topilmadi')
            qty=money(payload.qty)
            if qty<=0:http(422,'Qaytariladigan miqdor musbat bo‘lsin')
            returned=onerow(db,'SELECT COALESCE(SUM(quantity),0) AS q FROM company_purchase_returns WHERE store_id=? AND purchase_line_id=?',(shop['id'],line_id))['q']
            if qty>float(line['quantity'])-float(returned)+0.000001:http(422,'Olingan miqdordan ortiq qaytarib bo‘lmaydi')
            bill=onerow(db,'SELECT * FROM supplier_bills WHERE id=? AND store_id=?',(line['bill_id'],shop['id']))
            amount=round(qty*float(line['unit_cost']),2)
            if not bill or amount>float(bill['amount'])-float(bill['paid'])+.001:http(409,'Bu nakladnoydagi to‘langan summadan ortiq qaytarish uchun avval to‘lovni qaytarish hisobini rasmiylashtiring')
            product=onerow(db,'SELECT stock,name FROM products WHERE id=? AND store_id=?',(line['product_id'],shop['id']))
            stock=onerow(db,'SELECT qty FROM branch_stock WHERE store_id=? AND branch_id=? AND product_id=?',(shop['id'],line['branch_id'],line['product_id']))
            if not product or float(product['stock'])+0.000001<qty or not stock or float(stock['qty'])+0.000001<qty:http(409,'Filialda qaytarish uchun mahsulot qoldig‘i yetarli emas')
            db.execute('UPDATE products SET stock=stock-? WHERE id=? AND store_id=?',(qty,line['product_id'],shop['id']))
            adjust_branch(db,shop['id'],line['branch_id'],line['product_id'],-qty)
            db.execute('UPDATE supplier_bills SET amount=amount-? WHERE id=? AND store_id=?',(amount,line['bill_id'],shop['id']))
            rid=uid()
            db.execute('INSERT INTO company_purchase_returns(id,store_id,purchase_line_id,company_id,bill_id,product_id,branch_id,quantity,amount,created_at,user_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       (rid,shop['id'],line_id,line['company_id'],line['bill_id'],line['product_id'],line['branch_id'],qty,amount,now(),user['id']))
            db.execute('INSERT INTO movements(id,store_id,product_id,delta,reason,note,created_at,user_id,branch_id) VALUES(?,?,?,?,?,?,?,?,?)',
                       (uid(),shop['id'],line['product_id'],-qty,'korxonaga qaytarish',bill['reference'] or '',now(),user['id'],line['branch_id']))
            audit(db,shop['id'],user,'SUPPLIER_RETURN',{'id':rid,'line_id':line_id,'qty':qty,'amount':amount})
            return {'ok':True,'returned_id':rid,'amount':amount,'remaining_bill':round(float(bill['amount'])-amount-float(bill['paid']),2)}
