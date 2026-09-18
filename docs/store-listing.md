# Microsoft Store listing — Recording Converter for AnyDesk

Text for Partner Center. Everything below is ready to paste; nothing here is published
automatically.

---

## Identity

| Field | Value |
|---|---|
| Product name (reserve this first) | `Recording Converter for AnyDesk` |
| Publisher display name | `KEEP_DARK` |
| Category | Developer tools → Utilities (alt: Productivity) |
| Price | Free |
| Age rating | 3+ / Everyone (no user-generated content, no ads, no purchases) |
| Privacy policy URL | `https://www.keep-dark.com/works/recording-converter-for-anydesk/privacy/` (live) |
| Support contact | `https://www.keep-dark.com/works/recording-converter-for-anydesk/` (live) |
| Source code | `https://github.com/mastel2/anydesk2mp4` (public) |
| Package | `dist\RecordingConverterForAnyDesk-<version>.msix`, built with `-NoSign` |
| Partner Center account | Individual, Seller **95973210**, Active/Authorized (same account as AutoClicker) |
| Publisher (account-wide) | `CN=4EC6DF20-F152-42DE-A29E-EDD18083DAE6` — already in the built package |
| Identity Name (expected) | `KEEPDARK.RecordingConverterforAnyDesk` — already in the built package |

The publisher id belongs to the account, not to the app, so the package already carries the
right one. Only re-pack if the reserved name differs from the one above — step-by-step
instructions are in [`docs/store/SUBMIT-STEPS.md`](store/SUBMIT-STEPS.md):

```powershell
.\tools\pack_msix.ps1 -Version 1.0.0.0 -NoSign -IdentityName "<Identity Name>" -Publisher "<Publisher>"
```

---

## Short description (EN, ≤ 200 characters)

> Turn AnyDesk session recordings into ordinary MP4 videos you can play and share
> anywhere. Free, open source, and everything runs on your own PC.

## Description (EN)

> AnyDesk saves session recordings in its own `.anydesk` format, which only the AnyDesk
> client can open and which it cannot export. Recording Converter for AnyDesk turns those
> recordings into ordinary video files.
>
> Add the recordings you want, press Start, and leave it running. Each one is played back
> by your own AnyDesk client while the picture is recorded to MP4, MKV, MOV or WebM.
>
> **What you get**
> • A real queue — add files or a whole folder, reorder them, pause after the current
>   file, stop and keep what was recorded, retry anything that failed.
> • See who connected to whom, how long each recording is, and how big the result will be
>   — before you start.
> • Choose the format (MP4 H.264, MP4 H.265, MKV, MOV, WebM), the resolution
>   (original down to 480p) and one of three quality levels.
> • Send every file to one folder, or a different folder per recording.
> • Start at a set time, so a long queue can run overnight.
> • Stays out of your way: the AnyDesk player runs hidden, keyboard focus comes straight
>   back to you, and a new file never starts while you are in a game or a full-screen app.
> • Minimises to the notification area, with progress in the tooltip.
> • English, ไทย and 简体中文.
>
> **Good to know**
> • AnyDesk must be installed — the program uses your own client to play your own
>   recordings.
> • Conversion runs in real time: a 40-minute session takes 40 minutes. The queue tells
>   you when it will finish.
> • Recordings have no sound.
> • Everything runs on this PC. There is no account, no telemetry and no network access.
>
> Free and open source under the Apache License 2.0. Made by KEEP_DARK.
>
> Not affiliated with or endorsed by AnyDesk Software GmbH. "AnyDesk" is a trademark of
> its owner and is used here only to describe what this tool works with.

## Search terms

`anydesk`, `.anydesk`, `session recording`, `convert to mp4`, `recording converter`,
`remote support`, `screen recording`, `mp4`, `mkv`, `webm`, `it support`

---

## คำอธิบายสั้น (TH, ≤ 200 ตัวอักษร)

> แปลงไฟล์บันทึก session ของ AnyDesk เป็นวิดีโอ MP4 ธรรมดา ที่เปิดดูและส่งต่อได้ทุกที่
> ฟรี เปิดซอร์ส และทำงานในเครื่องคุณทั้งหมด

## คำอธิบาย (TH)

> AnyDesk บันทึก session เป็นไฟล์ `.anydesk` ซึ่งเปิดได้เฉพาะในโปรแกรมของ AnyDesk เอง
> และไม่มีปุ่มส่งออกเป็นวิดีโอ โปรแกรมนี้เปลี่ยนไฟล์เหล่านั้นให้เป็นไฟล์วิดีโอธรรมดา
>
> เพิ่มไฟล์ที่ต้องการ กดเริ่ม แล้วปล่อยให้ทำงาน แต่ละไฟล์จะถูกเล่นด้วย AnyDesk ของคุณเอง
> พร้อมบันทึกภาพออกมาเป็น MP4, MKV, MOV หรือ WebM
>
> **สิ่งที่ได้**
> • คิวจริง — เพิ่มทีละไฟล์หรือทั้งโฟลเดอร์ จัดลำดับ พักหลังไฟล์ปัจจุบัน
>   หยุดแล้วเก็บส่วนที่อัดไปแล้ว และลองใหม่เมื่อไม่สำเร็จ
> • เห็นว่าใครต่อกับใคร แต่ละไฟล์ยาวเท่าไร และผลลัพธ์จะใหญ่ประมาณเท่าไร ตั้งแต่ก่อนเริ่ม
> • เลือกรูปแบบ (MP4 H.264, MP4 H.265, MKV, MOV, WebM) ความละเอียด (เท่าต้นฉบับถึง 480p)
>   และคุณภาพ 3 ระดับ
> • เก็บทุกไฟล์ไว้โฟลเดอร์เดียว หรือแยกโฟลเดอร์รายไฟล์ก็ได้
> • ตั้งเวลาเริ่มได้ ให้คิวยาว ๆ ทำตอนกลางคืน
> • ไม่รบกวน: ตัวเล่นของ AnyDesk ทำงานแบบซ่อนตัว คืน focus ให้คุณทันที
>   และจะไม่เริ่มไฟล์ใหม่ขณะที่คุณเล่นเกมหรือใช้แอปเต็มจอ
> • ย่อเก็บที่ system tray พร้อมดูความคืบหน้าได้จาก tooltip
> • รองรับภาษาไทย อังกฤษ และจีนตัวย่อ
>
> **ควรรู้**
> • ต้องติดตั้ง AnyDesk ไว้ เพราะโปรแกรมใช้ client ของคุณเล่นไฟล์บันทึกของคุณเอง
> • แปลงตามเวลาจริง: session 40 นาทีใช้เวลา 40 นาที หน้าต่างคิวจะบอกเวลาที่จะเสร็จ
> • ไฟล์บันทึกไม่มีเสียง
> • ทุกอย่างทำงานในเครื่องนี้ ไม่มีบัญชีผู้ใช้ ไม่มีการเก็บสถิติ ไม่มีการเชื่อมต่อเครือข่าย
>
> ฟรีและเปิดซอร์สภายใต้ Apache License 2.0 จัดทำโดย KEEP_DARK
>
> ไม่มีส่วนเกี่ยวข้องและไม่ได้รับการรับรองจาก AnyDesk Software GmbH — "AnyDesk"
> เป็นเครื่องหมายการค้าของเจ้าของ ใช้ในที่นี้เพื่อบอกว่าโปรแกรมทำงานร่วมกับอะไรเท่านั้น

---

## 简短说明 (ZH, ≤ 200 字符)

> 将 AnyDesk 会话录像转换为普通 MP4 视频，随处可播放和分享。免费、开源，全部在本机运行。

## 说明 (ZH)

> AnyDesk 将会话录像保存为专有的 `.anydesk` 格式，只能用 AnyDesk 客户端打开，且无法导出。
> 本程序把这些录像转换成普通视频文件。
>
> 添加需要转换的录像，点击"开始"，然后让它运行。每个文件都会由你自己的 AnyDesk 客户端播放，
> 同时把画面录制为 MP4、MKV、MOV 或 WebM。
>
> **功能**
> • 真正的队列——添加文件或整个文件夹、调整顺序、当前文件完成后暂停、
>   停止并保留已录制的部分、失败后重试。
> • 转换前即可看到连接双方、每个录像的时长，以及结果文件的大致大小。
> • 可选格式（MP4 H.264、MP4 H.265、MKV、MOV、WebM）、分辨率（原始至 480p）和三档画质。
> • 所有文件保存到同一文件夹，或为每个录像单独指定文件夹。
> • 可定时开始，让长队列在夜间运行。
> • 不打扰你：AnyDesk 播放器隐藏运行，键盘焦点立即归还，
>   在你玩游戏或使用全屏应用时不会开始新文件。
> • 可最小化到通知区域，提示中显示进度。
> • 支持简体中文、English 和 ไทย。
>
> **请注意**
> • 需要安装 AnyDesk——本程序使用你自己的客户端播放你自己的录像。
> • 按实际时长转换：40 分钟的会话需要 40 分钟。队列会显示预计完成时间。
> • 录像没有声音。
> • 一切都在本机运行。没有账户、没有遥测、不联网。
>
> 免费开源，采用 Apache License 2.0。由 KEEP_DARK 制作。
>
> 与 AnyDesk Software GmbH 无关联，也未获其认可。"AnyDesk" 是其所有者的商标，
> 此处仅用于说明本工具与何种软件配合使用。

---

## Notes for certification

> The app converts AnyDesk session recordings, which are stored in a proprietary format
> that only the AnyDesk client can play and that AnyDesk offers no way to export.
>
> To do this it asks the user's own installed AnyDesk client to play a recording the user
> selected, and records the picture with a bundled LGPL build of FFmpeg. Three behaviours
> are worth explaining up front:
>
> 1. **It starts AnyDesk.exe as a child process** (`AnyDesk.exe --play <file>`). The app
>    does not contain, modify or redistribute any AnyDesk software.
> 2. **It makes that player window transparent and click-through** so it does not cover
>    the user's work. Windows stops drawing minimised or hidden windows, so there would be
>    nothing to capture otherwise. The window still exists and is never hidden from Task
>    Manager. The behaviour can be turned off in Options.
> 3. **It performs one synthetic mouse click per file** on the player's "restart" button,
>    so the video starts at the first frame; AnyDesk ignores the same command sent any
>    other way. The click is only issued when that window is verified to be under the
>    cursor position, the cursor is put back, and the whole thing can be turned off in
>    Options ("Start from the first frame").
>
> The app requires `runFullTrust` for the window handling above and for starting FFmpeg.
> It makes no network connections of any kind: no account, no telemetry, no updates.
>
> Testing: install AnyDesk, record any session (Settings → Recording), then open the app,
> add the `.anydesk` file and press Start. Conversion runs in real time, so a short
> recording is best for review.

---

## Submission checklist

- [ ] Reserve the product name in Partner Center (must be done by hand: Partner Center
      blocks automation browsers — confirmed twice while submitting AutoClicker)
- [ ] Check Product identity against the values above; re-pack only if they differ
- [x] Publish the privacy policy page and put its URL in the listing
- [ ] Upload 4–6 screenshots from `docs/screenshots/` (1616×939, above the 1366×768 minimum)
- [x] Store logo 300×300 — `docs/store-assets/StoreListing300x300.png`
- [ ] Age rating questionnaire (IARC)
- [ ] Paste the certification notes above
- [ ] Markets: all, or at least TH / US / CN
