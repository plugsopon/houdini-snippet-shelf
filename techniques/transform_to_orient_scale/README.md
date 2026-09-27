# transform → orient + scale

Category: Math & orientation · Type: Sop · Latest: v001 (2026-09-26)
All versions: v001 (older versions live in the shelf page)

## Notes

แปลง 3@transform (เช่นจาก packedfulltransform หรือ restxform ของ RBD) กลับเป็น p@orient + v@scale / f@pscale

หลักการ: Houdini คูณเวกเตอร์แบบแถว (v * M) ดังนั้น M = S * R
• polardecomp(M) = rotation ล้วน (ถ้ามี shear จะได้ rotation ที่ใกล้ที่สุด)
• S = M * transpose(R) = scale ที่เหลือ อ่านค่าจากแนวทแยง
• orient = quaternion(R)

ข้อควรรู้:
• ต้องลบ transform ทิ้ง เพราะ Copy to Points / LOP Instancer ใช้ transform ก่อน orient/scale เสมอ
• Copy to Points คูณ pscale × scale ในโค้ดจึงให้ตัวหนึ่งเป็น 1 เสมอ (scale เท่ากันทุกแกน → pscale, ไม่เท่า → scale)
• transform ที่ mirror (determinant ติดลบ) quaternion เก็บไม่ได้ โค้ดพลิกแกน X ออกก่อนแล้วคืนเป็น scale.x ติดลบ
• pivot เก็บไว้ได้เลย ไม่ต้องแปลง

วัดผลแล้ว: 60 พอยต์ สุ่ม orient + scale (uniform / non-uniform / mirror) Copy to Points ก่อน-หลังแปลงตรงกัน ≤ 0.0000005 · H21.0.671

## Files

### transform_to_orient.vfl — transform → orient + scale

- Where: Attribute Wrangle · Points
- Tested: Houdini 21.0.671

วางใน Attribute Wrangle (Points) ต่อหลัง node ที่มี 3@transform ได้ p@orient, f@pscale, v@scale และลบ transform ทิ้งให้

ไม่ต้องสร้าง spare parm · ใช้กับ 4@transform ได้ด้วย ถ้าเปลี่ยนบรรทัดแรกเป็น matrix3 M = matrix3(4@transform); (ตำแหน่งอยู่ใน row 3 ของ matrix 4x4)

### transform_to_orient_insert.py — Insert the wrangle after the selected node

- Where: Python Shell · select the node first
- Tested: Houdini 21.0.671

เลือก node ที่มี 3@transform แล้ว paste ใน Python Shell จะแทรก wrangle transform_to_orient ต่อจากมัน และย้ายสายที่ต่อออกจาก node นั้นมาต่อที่ wrangle ให้

NODE = ชื่อหรือ path ถ้าไม่อยากใช้ selection · REWIRE = False ถ้าไม่อยากให้ย้ายสาย
