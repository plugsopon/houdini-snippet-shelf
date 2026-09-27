# Surface distance from an edge group

Category: Geometry · Type: Sop · Latest: v002 (2026-09-25)
All versions: v001, v002 (older versions live in the shelf page)

## Notes

v002: ใช้ frame range ปัจจุบันของ scene
• หลังสร้าง node สคริปต์อ่าน start / end frame จาก playbar แล้วตั้งให้ parm ที่เป็น start frame (solver, DOP network: startframe / start_frame …) และ frame range ของ ROP / file cache (f1, f2)
• parm ที่มี expression อยู่แล้ว (เช่น $FSTART) ไม่ถูกแตะ
• ตั้ง START_FRAME / END_FRAME เองได้ หรือ LINK_TO_PLAYBAR = True ให้เขียน $FSTART / $FEND ตาม playbar ตลอด
• สคริปต์พิมพ์ออกมาว่าตั้ง parm ไหนไปบ้าง

จาก FX Template เดิม (Surfacedist · Aug 30 2025 20:03:26)
Note เดิม: Surfacedist

## Files

### surface_distance_from_an_edge_group_rebuild.py — Rebuild network (Sop)

- Where: Python Shell · open a Sop network first
- Tested: Houdini 21.0.671 · playbar 1001-1100 test

วัดระยะทางไปตามผิว (surfacedist) จากทุกพอยต์ไปหา edge group แล้วเก็บเป็น f@sd ใช้ทำ gradient ตามผิวที่ไม่ตัดผ่านอากาศ

สคริปต์นี้สร้าง node ทั้งชุดกลับมาในเครือข่ายที่ Network Editor เปิดอยู่ (หรือตั้ง TARGET ก็ได้)

แปลงมาจาก Sop.cpio ของ FX Template เดิมด้วย hou asCode(brief=True) · Brother สร้างกลับใน scene ใหม่แล้วเทียบกับของเดิม: node 6 ตัว ชนิด / สาย / ค่า parm ตรงกันทุกตัว

### attribwrangle1.vfl — attribwrangle1 (VEX)

- Where: Attribute Wrangle · Points
- Tested: Houdini 21.0.671 · rebuilt & compared

surfacedist(0, 'edge', 'P', @ptnum, pt, 'edge') คืนค่าระยะตามขอบของ mesh ไปหากลุ่ม 'edge' ที่ใกล้ที่สุด

โค้ดตัวเดียวกับที่อยู่ในสคริปต์ rebuild · ดึงแยกออกมาให้อ่านและ copy ได้ง่าย
