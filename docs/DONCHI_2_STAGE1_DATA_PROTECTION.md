# DONCHI 2.0 — 1-bosqich: Data Protection va PostgreSQL tayyorgarligi

**Holat:** kod va avtomatik sinovlar uchun tayyorlangan alohida GitHub tarmog‘i.
**Production holati:** Render Free + vaqtinchalik SQLite; ma’lumotlar doimiy saqlanishi kafolatlanmagan.
**Taqiq:** ushbu bosqichda PostgreSQL yaratilmaydi, `DATABASE_URL` o‘zgartirilmaydi,
eski bazadan hech narsa o‘chirilmaydi va avtomatik tiklash amalga oshirilmaydi.

## 1. SQLite backup

Python 3.13, internetga yoki pullik xizmatga ehtiyoj yo‘q.

```powershell
python scripts/backup_guard.py backup --source "data/yempro.sqlite3" --output "DONCHI-backup-2026-11-09.sqlite3"
python scripts/backup_guard.py verify --source "DONCHI-backup-2026-11-09.sqlite3"
python scripts/backup_guard.py restore-test --source "DONCHI-backup-2026-11-09.sqlite3" --new-target "DONCHI-restored-test.sqlite3"
```

- Faqat mavjud SQLite bazasi ochiladi; backup yaratishda bazadagi yozuvlar o‘zgartirilmaydi.
- Backup SQLite `backup()` API yordamida olinadi; boshida va oxirida butunlik, foreign key va sxema tekshiriladi.
- `.sha256` nazorat summasi backup fayli yoniga yoziladi. Restore summa mos kelmasa rad etiladi.
- Restore **faqat yangi fayl nomiga** mumkin. Mavjud ma’lumot faylining ustiga yozilmaydi.
- Backup parol xeshlari, mijozlar, savdo va shaxsiy ma’lumotlarni o‘z ichiga oladi. Uni Telegram kanalga yoki ochiq GitHub repoga yuklamang.
- Bu **avtomatik tashqi backup emas**: server o‘chsa shu konteynerdagi fayllar yo‘qolishi mumkin.
- Render Free’da ushbu buyruqlarni server ichida avtomatik ishga tushirish yo‘li berilmagan. Admin API’dagi backup yuklab olish funksiyasidan foydalanib, nusxani xavfsiz joyda saqlang. Yuklangan nusxaning to‘g‘riligini offline tekshiring.

## 2. PostgreSQL preflight

```powershell
python scripts/postgres_preflight.py --source "data/yempro.sqlite3" --output "migration-preflight.json"
```

Hisobotda jadval nomlari, har bir jadvaldagi qatorlar soni, `store_id` mavjudligi, FK soni va SQLite-spetsifik turlar bo‘ladi. Mijoz ma’lumotlari, maxfiy tokenlar, parollar chiqarilmaydi. Bu vosita **PostgreSQL’ga ko‘chirmaydi**.

Migration uchun hali zarur:
1. Doimiy DB xizmatini tanlash, imkoniyat va narxni tasdiqlash.
2. SQLite `?` parametrlari, `PRAGMA`, `INSERT OR IGNORE`, tranzaksiya va tur farqlarini server kodida moslashtirish.
3. Versiyalangan Postgres migratsiya va rollback yozish.
4. Faqat demo nusxada staging migratsiya o‘tkazish.
5. Jadval/qator sonlari, mahsulot qoldiqlari, qarz va savdo summalarini solishtirish.
6. Oldingi backupdan muvaffaqiyatli tiklash va rollback mashqini bajarish.
7. Shundan keyingina production trafikni ko‘chirish.

## 3. Xatolar monitoringi

- Server har bir API so‘rovini *faqat agregat* sifatida qayd qiladi: `2xx/4xx/5xx`, javob vaqti, so‘rov identifikatori.
- Oxirgi 40 ta server xatosi va 40 ta 2 sekunddan sekin API so‘rovi vaqtinchalik xotirada saqlanadi.
- `GET /api/platform-admin/diagnostics` faqat `superadmin` roliga ochiq.
- Super Admin → Sozlamalar → Monitoring → API diagnostikasi.
- Logda URL parametrlari, parol, so‘rov jismi, mijoz telefon raqami saqlanmaydi.
- Joriy ma’lumot **process-memory**: Render uxlaganda/restart bo‘lganda nolga tushadi. Bu hali doimiy monitoring/alerting xizmati emas.

## 4. Release gate

- [ ] Python syntax, API regressiya va Playwright Chromium testlari muvaffaqiyatli
- [ ] Backup/restore, checksum tampering, overwrite rejection testlari muvaffaqiyatli
- [ ] Admin va unauth diagnostika ruxsatsizligini isbotlash
- [ ] Staging DBga restore bilan ma’lumotlar qayta ochilishi
- [ ] Doimiy Postgres (alohida ruxsat talab qilinadi)
- [ ] Tashqi, shifrlangan avtomatik backup va recovery-drill

**Eslatma:** Mutlaq xatosiz yoki production-ready degan kafolat yo‘q. Doimiy DB tayyor bo‘lmaguncha real do‘kon ma’lumotlarini kiritmang.
