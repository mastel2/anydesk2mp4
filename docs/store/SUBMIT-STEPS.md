# ส่ง Recording Converter for AnyDesk ขึ้น Microsoft Store — ทำตามทีละข้อ

ทุกค่าที่ต้องกรอกเตรียมไว้แล้ว คัดลอกวางได้เลย เนื้อหาหน้า listing 3 ภาษาอยู่ที่
[`docs/store-listing.md`](../store-listing.md)

> **Partner Center ต้องกดเองในเบราว์เซอร์ปกติ** — ยืนยันจากตอนส่ง AutoClicker (2026-09-07
> และ 2026-09-09) ว่า Akamai ตอบ *Access Denied* กับ automation browser ทั้งแบบ headless
> และ headed จึงทำแทนอัตโนมัติไม่ได้

---

## สถานะปัจจุบัน

| สิ่งที่ต้องมี | สถานะ |
|---|---|
| บัญชี Partner Center (Individual, Seller 95973210) | ✅ มีอยู่แล้ว ใช้บัญชีเดียวกับ AutoClicker |
| Privacy policy ออนไลน์ | ✅ https://www.keep-dark.com/works/recording-converter-for-anydesk/privacy/ |
| หน้าผลิตภัณฑ์ | ✅ https://www.keep-dark.com/works/recording-converter-for-anydesk/ |
| ซอร์สโค้ดสาธารณะ | ✅ https://github.com/mastel2/anydesk2mp4 |
| ภาพหน้าจอ 1616×939 (ขั้นต่ำ 1366×768) | ✅ `docs/screenshots/` 6 ภาพ |
| โลโก้ 300×300 | ✅ `docs/store-assets/StoreListing300x300.png` |
| MSIX unsigned | ✅ `dist/RecordingConverterForAnyDesk-1.0.0.0.msix` (84 MB) |
| **จองชื่อใน Partner Center** | ⬜ **ต้องทำเอง — ดูขั้น 1** |

---

## ขั้น 1 — จองชื่อ (ทำเอง, ~5 นาที)

Partner Center → Apps and games → **New product → MSIX or PWA app**

ชื่อที่จะลอง ตามลำดับ:

| ลำดับ | ชื่อ | Identity Name ที่จะได้ |
|---|---|---|
| 1 | `Recording Converter for AnyDesk` | `KEEPDARK.RecordingConverterforAnyDesk` |
| 2 | `Session Recording Converter by KEEP_DARK` | `KEEPDARK.SessionRecordingConverterbyKEEPDARK` |
| 3 | `Remote Session Recording Converter` | `KEEPDARK.RemoteSessionRecordingConverter` |

> ⚠️ **ชื่อที่ 1 มีคำว่า “AnyDesk” ซึ่งเป็นเครื่องหมายการค้าของผู้อื่น** Microsoft อาจปฏิเสธการจอง
> หรือให้แก้ระหว่าง certification แม้การใช้แบบบอกความเข้ากันได้ (“for AnyDesk”) จะเป็นการใช้โดยชอบ
> ในหลายเขตอำนาจ ถ้าถูกปฏิเสธ ให้ใช้ชื่อสำรองแล้วอธิบายความเข้ากันได้ในคำอธิบายแทน
> — ชื่อในแอปและบนเว็บไม่ต้องเปลี่ยนตาม เปลี่ยนเฉพาะชื่อที่จองใน Store

หลังจองแล้ว เข้า **Product management → Product identity** จะเห็น 3 ค่า:

- `Package/Identity/Name` — ควรตรงกับตารางข้างบน
- `Package/Identity/Publisher` — **คาดว่าเป็น `CN=4EC6DF20-F152-42DE-A29E-EDD18083DAE6`**
  (ค่านี้ผูกกับบัญชี ไม่ใช่กับแอป จึงเป็นค่าเดียวกับ AutoClicker)
- `Package/Properties/PublisherDisplayName` — `KEEP_DARK`

**ถ้าทั้งสองค่าตรงกับที่คาดไว้ MSIX ที่ build ไว้แล้วใช้ได้เลย ไม่ต้อง build ใหม่**
ถ้าไม่ตรง (เช่นใช้ชื่อสำรอง) ให้ build ใหม่ด้วยค่าจริง:

```powershell
cd D:\Docker\anydesk2mp4
.\tools\pack_msix.ps1 -Version 1.0.0.0 -NoSign -IdentityName "<ค่าจริง>" -Publisher "<ค่าจริง>"
```

จดไว้ด้วย: **Store ID** (รูปแบบ `9XXXXXXXXXXX`) และกำหนดว่าต้อง submit ภายใน 3 เดือน ไม่งั้นชื่อหลุด

---

## ขั้น 2 — Packages

ลากไฟล์ `dist\RecordingConverterForAnyDesk-1.0.0.0.msix` เข้าหน้า Packages

- Device family: ติ๊กเฉพาะ **Windows 10/11 Desktop**
- ถ้าถูกปฏิเสธเรื่องเวอร์ชัน ให้ขึ้นเป็น `1.0.1.0` (หลักสุดท้ายต้องเป็น 0 เสมอ)

---

## ขั้น 3 — Properties

| ช่อง | ค่า |
|---|---|
| Category | **Developer tools → Utilities** (สำรอง: Productivity) |
| Privacy policy URL | `https://www.keep-dark.com/works/recording-converter-for-anydesk/privacy/` |
| Website | `https://www.keep-dark.com/works/recording-converter-for-anydesk/` |
| Support contact info | `art@keep-dark.com` |
| System requirements | Windows 10 1809+ · x64 · **ต้องติดตั้ง AnyDesk แยกต่างหาก** |
| Additional declarations | **ไม่ติ๊ก third-party commerce** (แอปนี้ฟรี ไม่ขายอะไรเลย ต่างจาก AutoClicker) |
| Product declarations อื่น | ไม่ติ๊ก — ไม่มีโฆษณา ไม่ใช้กล้อง/ไมค์/ตำแหน่ง ไม่เชื่อมต่อเครือข่าย |

---

## ขั้น 4 — Age ratings (IARC)

ตอบ **No** ทุกข้อ — ไม่มีความรุนแรง เพศ ยา การพนัน ไม่มีการโต้ตอบระหว่างผู้ใช้
ไม่แชร์ข้อมูล ไม่มี in-app purchase → ได้ **IARC 3+ / ESRB Everyone**

---

## ขั้น 5 — Pricing and availability

- Markets: **All markets** (ต้องมี Thailand)
- Visibility: Public · Discoverable
- Pricing: **Free**
- Release: as soon as it passes certification

---

## ขั้น 6 — Store listings (3 ภาษา)

Add/remove languages → **Thai (Thailand)**, **English (United States)**, **Chinese (Simplified)**

เนื้อหาทุกช่องอยู่ใน [`docs/store-listing.md`](../store-listing.md) — คำอธิบายสั้น คำอธิบายเต็ม
และ search terms ครบทั้งสามภาษา

ภาพที่ต้องอัปโหลดต่อภาษา (ใช้ชุดเดียวกันได้ทุกภาษา หรือสลับภาพตามภาษา):

| ไฟล์ใน `docs/screenshots/` | ใช้กับ |
|---|---|
| `queue-en-light.png` | English |
| `queue-en-dark.png` | English (ภาพที่ 2) |
| `queue-th-light.png` | ไทย |
| `queue-zh-Hans-light.png` | จีน |
| `options-en.png`, `about-en.png` | ทุกภาษา (ภาพเสริม) |

โลโก้ 300×300: `docs/store-assets/StoreListing300x300.png`

---

## ขั้น 7 — Submission options → Notes for certification

วางข้อความจากหัวข้อ **Notes for certification** ใน [`docs/store-listing.md`](../store-listing.md)
ข้อความนั้นอธิบายล่วงหน้า 3 เรื่องที่ผู้ตรวจจะสงสัย:

1. แอปเปิด `AnyDesk.exe --play` เป็น process ลูก
2. แอปทำหน้าต่างของตัวเล่นให้โปร่งใสและคลิกทะลุ
3. แอปคลิกเมาส์เองหนึ่งครั้งต่อไฟล์

พร้อมเหตุผลของ `runFullTrust` และยืนยันว่าไม่มีการเชื่อมต่อเครือข่ายใด ๆ

---

## ขั้น 8 — กด Submit

ตรวจก่อนกด:

- [ ] เปิด privacy URL ในเบราว์เซอร์แล้วเห็นหน้าจริง (ผู้ตรวจจะเปิดลิงก์ ถ้า 404 จะถูกตีกลับ)
- [ ] Identity ใน manifest ตรงกับ Product identity
- [ ] ภาพหน้าจอไม่มีข้อมูลจริงของใคร (ชุดที่ให้มาใช้ชื่อเครื่องสมมติทั้งหมด)

ผลจะมาทางอีเมล Partner Center ภายใน 1–3 วันทำการ

เช็คสถานะเผยแพร่โดยไม่ต้องเปิดเบราว์เซอร์ (ใส่ Store ID ที่ได้จากขั้น 1):

```bash
curl "https://displaycatalog.mp.microsoft.com/v7.0/products/<STORE_ID>?market=TH&languages=th-TH&fieldsTemplate=Details"
```

---

## ความเสี่ยงที่ควรรู้ก่อนส่ง

| เรื่อง | ประเมิน |
|---|---|
| **ชื่อมีเครื่องหมายการค้าของผู้อื่น** | เสี่ยงสูงสุด มีชื่อสำรองเตรียมไว้แล้วในขั้น 1 |
| แอปสั่งโปรแกรมอื่นทำงานและคลิกเมาส์เอง | อธิบายไว้ใน notes แล้ว ทั้งสองอย่างปิดได้ในหน้าตั้งค่า |
| ลิงก์ GitHub ในหน้า About | เป็นลิงก์ซอร์สโค้ด ไม่ใช่ลิงก์ดาวน์โหลดตัวติดตั้งนอก Store จึงไม่ขัด policy เรื่อง self-update |
| ต้องติดตั้ง AnyDesk แยก | ระบุไว้ทั้งใน System requirements และคำอธิบาย เพื่อไม่ให้ผู้ตรวจคิดว่าแอปพัง |
| FFmpeg แบบ LGPL | ใช้ LGPL v3 ไม่ใช่ GPL (GPL แจกผ่าน Store ไม่ได้) พร้อมไฟล์ license ใน `bin/FFMPEG-LICENSE.txt` |
