# My First Shot

Category: Shots · Type: Object · Latest: v003 (2026-09-25)
All versions: v002, v003 (older versions live in the shelf page)

## Notes

v003: ใช้ frame range ปัจจุบันของ scene
• หลังสร้าง node สคริปต์อ่าน start / end frame จาก playbar แล้วตั้งให้ parm ที่เป็น start frame (solver, DOP network: startframe / start_frame …) และ frame range ของ ROP / file cache (f1, f2)
• parm ที่มี expression อยู่แล้ว (เช่น $FSTART) ไม่ถูกแตะ
• ตั้ง START_FRAME / END_FRAME เองได้ หรือ LINK_TO_PLAYBAR = True ให้เขียน $FSTART / $FEND ตาม playbar ตลอด
• สคริปต์พิมพ์ออกมาว่าตั้ง parm ไหนไปบ้าง

จาก FX Template เดิม (My First Shot · Aug 30 2025 11:41:19)
Note เดิม: Good v2

## Files

### my_first_shot_rebuild.py — Rebuild network (Object)

- Where: Python Shell · run while /obj is shown
- Tested: Houdini 21.0.671 · playbar 1001-1100 test

Setup ระดับ Object (geo1 + geo2) จาก FX Template เดิม · ใช้วางใน /obj

สคริปต์นี้สร้าง node ทั้งชุดกลับมาในเครือข่ายที่ Network Editor เปิดอยู่ (หรือตั้ง TARGET ก็ได้)

แปลงมาจาก Object.cpio ของ FX Template เดิมด้วย hou asCode(brief=True) · Brother สร้างกลับใน scene ใหม่แล้วเทียบกับของเดิม: node 2 ตัว ชนิด / สาย / ค่า parm ตรงกันทุกตัว
