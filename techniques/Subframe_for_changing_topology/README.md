# Subframe for changing topology

Category: Motion blur & subframes · Type: Sop · Latest: v002 (2026-09-25)
All versions: v001, v002 (older versions live in the shelf page)

## Notes

v002: ใช้ frame range ปัจจุบันของ scene
• หลังสร้าง node สคริปต์อ่าน start / end frame จาก playbar แล้วตั้งให้ parm ที่เป็น start frame (solver, DOP network: startframe / start_frame …) และ frame range ของ ROP / file cache (f1, f2)
• parm ที่มี expression อยู่แล้ว (เช่น $FSTART) ไม่ถูกแตะ
• ตั้ง START_FRAME / END_FRAME เองได้ หรือ LINK_TO_PLAYBAR = True ให้เขียน $FSTART / $FEND ตาม playbar ตลอด
• สคริปต์พิมพ์ออกมาว่าตั้ง parm ไหนไปบ้าง

จาก FX Template เดิม (Subframe for changing Topology · Aug 30 2025 20:00:27)
Note เดิม: Subframe for changing Topology

## Files

### subframe_for_changing_topology_rebuild.py — Rebuild network (Sop)

- Where: Python Shell · open a Sop network first
- Tested: Houdini 21.0.671 · playbar 1001-1100 test

ทำ subframe ให้ geometry ที่ topology เปลี่ยนทุกเฟรม (เช่น particle fluid surface) โดยเลื่อน P ตาม velocity ไปข้างหน้าหรือถอยหลังจากเฟรมเต็มที่ใกล้ที่สุด แล้วเขียน Alembic ที่มี subframe ได้

สคริปต์นี้สร้าง node ทั้งชุดกลับมาในเครือข่ายที่ Network Editor เปิดอยู่ (หรือตั้ง TARGET ก็ได้)

แปลงมาจาก Sop.cpio ของ FX Template เดิมด้วย hou asCode(brief=True) · Brother สร้างกลับใน scene ใหม่แล้วเทียบกับของเดิม: node 10 ตัว ชนิด / สาย / ค่า parm ตรงกันทุกตัว

### attribwrangle3.vfl — attribwrangle3 (VEX)

- Where: Attribute Wrangle · Points
- Tested: Houdini 21.0.671 · rebuilt & compared

ถ้าเฟรมตอนนี้อยู่ก่อนเฟรมเต็มที่ใกล้ที่สุด: ถอย P ตาม v@v · ถ้าอยู่หลัง: เดินหน้าตาม v@v2 · ระยะ = @TimeInc × เศษของเฟรม

โค้ดตัวเดียวกับที่อยู่ในสคริปต์ rebuild · ดึงแยกออกมาให้อ่านและ copy ได้ง่าย
