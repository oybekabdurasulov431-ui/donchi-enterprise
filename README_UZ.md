# DONCHI Clean Start 1.1

GitHub va yangi mijozlar uchun **demo ma\u02bblumotlari mavjud bo\u02bblmagan** DONCHI Enterprise loyihasi.

## Natija
- Demo do\u02bbkonlar: **0**.
- Mahsulotlar, savdolar, mijozlar, qarzlar, xodimlar, xabarlar: **0**.
- Super Admin login: `oybek.py`.
- Super Admin paroli **kodda yo\u02bbq**; birinchi ishga tushirganda konsolda so\u02bbraladi va DB\u02bbga salted PBKDF2 xesh bilan saqlanadi.
- Agar mahalliy sinov uchun `12345` ni tanlasangiz, dastur zaif parol haqida ogohlantiradi. **Internetga chiqarishdan oldin albatta kuchli parolga almashtiring.**

## Birinchi ishga tushirish
Windows\u02bbda ZIP\u02bbni Extract All qiling; papkada PowerShell oching:

```powershell
.\START_WINDOWS.bat
```

Python 3.10+, FastAPI, Uvicorn kerak. Birinchi start paketlarni o\u02bbrnatadi, so\u02bbng Super Admin parolini ikki marta so\u02bbraydi. Siz kiritgan parolni GitHub\u02bbga yuboradigan kodda saqlamaydi. Login yaratildi degan xabar chiqqach, server ishga tushadi.

- Super Admin: http://127.0.0.1:8787/platform/
- Do\u02bbkon admini: http://127.0.0.1:8787/app/ (do\u02bbkon yaratmaguningizcha alohida login yo\u02bbq)
- Sayt: http://127.0.0.1:8787/site/

## Eski ma\u02bblumotlarni tozalash
- Eski serverni `Ctrl+C` bilan **to\u02bbxtating**.
- Yangi ZIP alohida papkaga chiqarilsa, avvalgi dasturdagi ma\u02bblumotlarga tegmaydi: yangi baza **bo\u02bbsh** bo\u02bbladi.
- Agar shu papkada eski `data/` mavjud bo\u02bblsa, `RESET_DONCHI.bat` orqali **aniq rozilik** bilan tozalang.
- Script eski `data/`ni `backups/`ga ko\u02bbchiradi (GitHubga yuklanmaydi), yangi bazani yaratadi va `oybek.py` uchun yangi parol so\u02bbraydi. Eski foydalanuvchilar sessiyasi o\u02bbchadi.
- Oldingi Chrome/Edge qurilmalaridagi offline savdo navbati va kesh saqlanishi mumkin. Browser Settings → Site data dan `127.0.0.1:8787` uchun ma\u02bblumotlarni ham tozalang. **Sinxronlanmagan savdolarni qayta tiklab bo\u02bblmasligi mumkin!**
- `backups/`dagi oldingi nusxani qayta tiklash yoki butunlay o\u02bbchirishni faqat qasddan bajaring.

## GitHub
Repo\u02bbni Private yarating. `.gitignore` avtomatik `data/`, `backups/`, `.env`, SQLite va kalitlarni chiqarib tashlaydi. `git status` bilan tekshiring. Birinchi Super Admin parolini repozitoriyga hech qachon joylamang.

## Sinov
```powershell
python -m pip install -r requirements-dev.txt
python tests/test_clean_start.py
```

## Cheklov
Bu **lokal MVP**, production uchun tayyor emas: HTTPS, PostgreSQL, sirlar va login himoyasini kuchaytirish, audit, backend xavfsizlik testi, alohida domen va hosting zarur.
