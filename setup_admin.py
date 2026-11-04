"""First-run setup for the DONCHI platform owner (nothing stored in source code)."""
from __future__ import annotations
import getpass
import sys

# Import initializes tables but deliberately does not create demo accounts.
from server import connection, onerow, uid, now, pwdhash

USERNAME = 'oybek.py'

def main():
    with connection() as db:
        number = onerow(db, 'SELECT COUNT(*) AS c FROM users')['c']
        admin = onerow(db, "SELECT id FROM users WHERE role='superadmin' LIMIT 1")
    if admin:
        print('Super Admin allaqachon mavjud. Mavjud parolni bu skript o\u02bbzgartirmaydi.')
        return 0
    if number:
        print('Bazadagi eski foydalanuvchilar saqlangan. Toza boshlash uchun RESET_DONCHI.bat ni ishlating.')
        return 2
    print('\nDONCHI: birinchi Super Admin hisobini yaratish')
    print('Login: ' + USERNAME)
    print('Parolni faqat shu kompyuterda kiriting. GitHub ga yuborilmaydi.')
    try:
        password = getpass.getpass('Yangi parol: ')
        confirm = getpass.getpass('Parolni takrorlang: ')
    except (EOFError, KeyboardInterrupt):
        print('\nParol kiritish bekor qilindi.')
        return 2
    if not password or password != confirm:
        print('Parollar mos emas yoki bo\u02bbsh.')
        return 2
    if password == '12345' or len(password) < 10:
        print('DIQQAT: Bu parol juda zaif. Faqat lokal sinov uchun ishlating; internetga chiqarmang.')
        try:
            answer=input('Shu parol bilan faqat lokal demo yaratilsinmi? (ha/yoq): ').strip().lower()
        except (EOFError, KeyboardInterrupt):
            return 2
        if answer != 'ha': return 2
    with connection(write=True) as db:
        if onerow(db,'SELECT id FROM users LIMIT 1'):
            print('Baza oldin yaratilibdi; ikki marta hisob ochilmadi.')
            return 2
        db.execute('INSERT INTO users(id,username,full_name,password_hash,role,store_id,active,created_at) VALUES(?,?,?,?,?,?,?,?)',
                   (uid(),USERNAME,'DONCHI platforma egasi',pwdhash(password),'superadmin',None,1,now()))
    print('Super Admin yaratildi. Do\u02bbkonlar: 0. Endi serverni ishga tushiring.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
