# DONCHI Enterprise — GitHub'ga joylash

Ushbu papka GitHub'ga kodni saqlash uchun tayyorlangan. Dastur GitHub Pages'da ishlamaydi: FastAPI backend uchun alohida server kerak.

## 1. Git'ni tekshiring
PowerShell'ni DONCHI-GitHub-Ready papkasida oching:

```powershell
git --version
```

Git yo'q bo'lsa https://git-scm.com/downloads/win dan o'rnating.

## 2. GitHub'da bo'sh PRIVATE repository yarating

https://github.com/new — Repository name: `donchi-enterprise`, Visibility: **Private**.
README, .gitignore yoki license yaratish kataklarini belgilamang (bu fayllar loyiha ichida bor).

## 3. PowerShell'da yuklang

```powershell
git init -b main
git add .
git status
git commit -m "DONCHI Enterprise 1.0 initial commit"
git remote add origin https://github.com/USERNAME/donchi-enterprise.git
git push -u origin main
```

`USERNAME` o'rniga o'zingizning GitHub foydalanuvchi nomingizni kiriting. Agar `git init -b main` ishlamasa, `git init` va `git branch -M main` dan foydalaning. Birinchi commitda ism/email so'rasa, `git config --global user.name "Your Name"` va `git config --global user.email "your-github-email"` yozing.

## Xavfsizlik

- `data/`, `.env`, SQLite ma'lumotlar bazasi va maxfiy kalitlarni GitHub'ga hech qachon yubormang; `.gitignore` ularni odatda chetlab o'tadi, lekin `git status` bilan tekshiring.
- Kodda demo uchun standart loginlar mavjud. Repozitoriy **Private** tursin; real mijozlarda foydalanish yoki hammaga ochishdan oldin demo hisoblarni o'chiring, parollarni almashtiring va xavfsizlik auditini o'tkazing.
- GitHub manba kodini saqlaydi, ilovani avtomatik serverga aylantirmaydi. Deploy uchun Linux/VPS yoki FastAPI'ni qo'llaydigan hosting zarur.
- Agar GitHub'ga ilgari sir yoki mijoz ma'lumotlari yuborilgan bo'lsa, `.gitignore` qo'shish ularni avvalgi Git tarixidan o'chirmaydi.
