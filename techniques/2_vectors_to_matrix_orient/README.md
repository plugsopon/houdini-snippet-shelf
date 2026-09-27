# 2 vectors → matrix / orient

Category: Math & orientation · Type: Sop · Latest: v002 (2026-09-25)
All versions: v001, v002 (older versions live in the shelf page)

## Notes

v002: ใช้ frame range ปัจจุบันของ scene
• หลังสร้าง node สคริปต์อ่าน start / end frame จาก playbar แล้วตั้งให้ parm ที่เป็น start frame (solver, DOP network: startframe / start_frame …) และ frame range ของ ROP / file cache (f1, f2)
• parm ที่มี expression อยู่แล้ว (เช่น $FSTART) ไม่ถูกแตะ
• ตั้ง START_FRAME / END_FRAME เองได้ หรือ LINK_TO_PLAYBAR = True ให้เขียน $FSTART / $FEND ตาม playbar ตลอด
• สคริปต์พิมพ์ออกมาว่าตั้ง parm ไหนไปบ้าง

จาก FX Template เดิม (Convert_2 Vectors_to_Mat_2_Vectors_to_Orient · Aug 30 2025 20:02:32)
Note เดิม: Convert 
2 Vectors to Mat
2 Vectors to Orient

## Files

### 2_vectors_matrix_orient_rebuild.py — Rebuild network (Sop)

- Where: Python Shell · open a Sop network first
- Tested: Houdini 21.0.671 · playbar 1001-1100 test

สร้าง orientation จากเวกเตอร์ 2 ตัว (N กับ up): ได้ทั้ง p@orient (quaternion) และ 3@xform (matrix3) พร้อมตัวอย่างแปลง orient กลับเป็น matrix ด้วย qconvert

สคริปต์นี้สร้าง node ทั้งชุดกลับมาในเครือข่ายที่ Network Editor เปิดอยู่ (หรือตั้ง TARGET ก็ได้)

แปลงมาจาก Sop.cpio ของ FX Template เดิมด้วย hou asCode(brief=True) · Brother สร้างกลับใน scene ใหม่แล้วเทียบกับของเดิม: node 2 ตัว ชนิด / สาย / ค่า parm ตรงกันทุกตัว

### attribwrangle2.vfl — attribwrangle2 (VEX)

- Where: Attribute Wrangle · Points
- Tested: Houdini 21.0.671 · rebuilt & compared

ใช้ maketransform(N, up) สร้าง matrix3 แล้วแปลงเป็น quaternion · N กับ up มาจาก spare parm แบบ chv() ของ wrangle

โค้ดตัวเดียวกับที่อยู่ในสคริปต์ rebuild · ดึงแยกออกมาให้อ่านและ copy ได้ง่าย
