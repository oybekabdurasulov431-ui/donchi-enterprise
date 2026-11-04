# DONCHI — haqiqiy do‘konda pilot sinov

**Holat: reja.** Bu tekshiruvni do‘kon egasi yoki mas’ul xodim bilan birgalikda bajarish zarur. Hozir hech qanday haqiqiy do‘konda tekshirilgan degan da’vo yo‘q. Asl ish bazasi o‘rniga sinov bazasidan foydalaning.

## Sinov oldidan
- [ ] Sinov do‘konining roziligi va mas’ul shaxsi aniqlandi
- [ ] `data` papkasi va barcha mahsulotlarning zaxira nusxasi olindi
- [ ] Sinovda ishlatiladigan mahsulot, xodim va mijozlar ajratildi
- [ ] Kassa va qaytarish testlari uchun sinov pullari tanlandi
- [ ] Telefon, planshet, noutbuk, printer, tarmoq va internet holati qayd etildi

## 1. Kirish va rollar
- [ ] Super Admin `/platform/` orqali faqat do‘konlar va platforma boshqaruviga kira oldi
- [ ] Do‘kon Admin `/app/` orqali faqat o‘z do‘koniga kira oldi
- [ ] Sotuvchi Super Admin yoki narx o‘zgartirishga kira olmadi
- [ ] Login sessiyasi brauzer qayta ochilganda saqlandi; logoutda tugadi

## 2. Savdo va ombor
- [ ] 1 dona, 1 qop va 1,5 kg sinov mahsuloti sotildi, qoldiq to‘g‘ri kamaydi
- [ ] Barkod/tarozi ishlatilsa, ular **alohida** qo‘lda sinovdan o‘tkazildi (hozir universal qurilma integratsiyasi yo‘q)
- [ ] Kassa smenasi ochildi; naqd/karta/aralash savdo amalga oshirildi
- [ ] Smena yopilganda kassa bilan tizim summasi solishtirildi
- [ ] Qaytarishdan so‘ng ombor qoldig‘i va to‘lov summalari qayta hisoblandi

## 3. Nasiya va filiallar
- [ ] Mijozga nasiya berildi; mijoz qarziga yozildi
- [ ] Qarzning bir qismi qaytarildi; qolgan qoldiq to‘g‘ri chiqdi
- [ ] Nasiya limiti buzilganda to‘lov rad qilindi
- [ ] Ikki filialda qoldiq, transfer va sotuvlar solishtirildi

## 4. Offline
- [ ] Ilova avval internet bilan ochildi, so‘ng internet uzildi
- [ ] Offline POS savdo navbatga yozildi; mavjud mahsulot qoldig‘i tekshirildi
- [ ] Internet qayta yoqilganda sinxronlash bosildi, savdo bir marta yozildi
- [ ] Ikki qurilmada bir mahsulotga bir vaqtda savdo qilinganda konfliktni qo‘lda tekshirish boshqarildi
- [ ] Offline paytda brauzer keshini tozalash holati sinovdan o‘tkazildi

## 5. Moslashuvchanlik
- [ ] 360–390px Android/iPhone ekranida menyu, POS, nasiya va modal oynalar sig‘di
- [ ] 768px planshet ekranida jadvalni ko‘rish va tugmalarni bosish mumkin
- [ ] 1366px noutbuk va katta PC ekranida gorizontal ortiqcha scroll chiqmadi
- [ ] Tungi/kunduzgi rejimda o‘qish kontrasti yetarli

## 6. Mijozlarni jalb qilish
- [ ] `/site/` tanishtiruv sahifasini ochib ko‘rildi
- [ ] Demo so‘rovi yuborildi va Super Admin `Demo so‘rovlari`da paydo bo‘ldi
- [ ] Demo narxlari va mijozlarga beriladigan va’dalar tekshirildi
- [ ] Maxfiylik siyosati va demo hisoblari xavfsizligi ko‘rib chiqildi

## Sinov protokoli
Do‘kon: ___________________    Sana: _____________
Xodim: ____________________    Qurilma: __________
Natija: [ ] O‘tdi    [ ] Tuzatish kerak
Xatolik va takrorlash qadamlari: ____________________________

**Haqiqiy to‘lovlarni boshlashdan oldin** barcha muhim testlar bajarilishi va muammolar tuzatilishi shart.
