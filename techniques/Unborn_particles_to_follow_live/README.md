# Unborn particles → follow live

Category: Particles · Type: Sop · Latest: v003 (2026-09-25)
All versions: v001, v002, v003 (older versions live in the shelf page)

## Notes

v003: ใช้ frame range ปัจจุบันของ scene
• หลังสร้าง node สคริปต์อ่าน start / end frame จาก playbar แล้วตั้งให้ parm ที่เป็น start frame (solver, DOP network: startframe / start_frame …) และ frame range ของ ROP / file cache (f1, f2)
• parm ที่มี expression อยู่แล้ว (เช่น $FSTART) ไม่ถูกแตะ
• ตั้ง START_FRAME / END_FRAME เองได้ หรือ LINK_TO_PLAYBAR = True ให้เขียน $FSTART / $FEND ตาม playbar ตลอด
• สคริปต์พิมพ์ออกมาว่าตั้ง parm ไหนไปบ้าง
• rig builder: demo POP sim เริ่มที่ start frame · rest shape = end frame (REST_FRAME = None) · anim ของ emitter ขยับจาก start ถึง end

v002: สคริปต์ Python ทุกตัวติดตั้งลง network ที่ Network Editor เปิดอยู่ แบบเดียวกับ FX Template
• rig builder: เปิด Geometry network แล้วรัน = สร้างตรงนั้น · เปิด /obj แล้วรัน = สร้าง geo "follow_demo" ใหม่ให้ · โหมด BUILD_DEMO = False หาชื่อ node ใน network ที่เปิดอยู่ก่อน (ใส่ path เต็มก็ได้) · ไม่ย้าย node เดิมของพี่
• patch: หา Blast follow_born_only เฉพาะใน network ที่เปิดอยู่และข้างใน
• ตั้ง TARGET เป็น path ได้ถ้าจะบังคับที่ติดตั้ง

ปัญหา: เอาเฟรมสุดท้ายของ POP sim มาเป็นพอยต์ชุดคงที่ แล้ว copy P จากซิมตาม id ตัวที่ยังไม่เกิดหา id ตัวเองไม่เจอ เลยลอยค้างอยู่กลางอากาศ

วิธีแก้: ให้ตัวที่ยังไม่เกิดไปเอาตำแหน่งปัจจุบันของเพื่อนที่เกิดแล้วซึ่งอยู่ใกล้ในท่า rest (เฉลี่ยแบบ Gaussian + emitter เป็นตัวถ่วง) แล้ว blend เข้าซิมจริงตอนเกิด ใช้ขับ Point Deform ได้

เริ่มจาก build_follow_live_v2.py (BUILD_DEMO = True ใช้กับ geo ว่างได้เลย)
ทดสอบกับ H21.0.671 · ยังไม่ได้ลองกับ 20.5

## Files

### build_follow_live_v4.py — Follow-live rig builder (unborn particles)

- Where: Python Shell
- Tested: Houdini 21.0.671 · playbar 1001-1100 test

สร้าง rig ทั้งชุดให้พอยต์ที่ยังไม่เกิด (ยังไม่มี id ในซิม) ไปเอาตำแหน่งปัจจุบันของพาร์ติเคิลที่มีชีวิตซึ่งอยู่ใกล้มันที่สุดในเลย์เอาต์ของเฟรม rest แล้วค่อยๆ blend เข้าตำแหน่งซิมจริงตอนเกิด ใช้ขับ Point Deform ได้โดยไม่กระตุก

ติดตั้งลง network ที่ Network Editor เปิดอยู่: ถ้าเปิด Geometry network จะสร้างตรงนั้น ถ้าเปิด /obj จะสร้าง geo ใหม่ชื่อ follow_demo
BUILD_DEMO = True จะสร้าง grid → anim → POP sim เป็นตัวอย่าง ถ้าตั้งเป็น False จะ rig scene ของพี่เอง ใส่แค่ชื่อ node ใน network ที่เปิดอยู่ก็พอ หรือเลือก sim node ก่อนรัน

รัน paste ทั้งก้อนใน Windows → Python Shell · ผลลัพธ์อยู่ที่ OUT_follow_live (lattice) และ OUT_follow_deform · Max Neighbours: 256 นิ่งกว่า, 64 = default, 32 เร็วกว่า (วัดที่ 200k พาร์ติเคิล: ~470 / ~145 / ~95 ms ต่อเฟรม) · ทดสอบกับ H21 เท่านั้น ยังไม่ได้ลองกับ 20.5

### follow_live.vfl — follow_live — closest live position

- Where: Attribute Wrangle · Points
- Tested: Houdini 21.0.671

หัวใจของ rig: ตำแหน่งปัจจุบันเฉลี่ยแบบ Gaussian ของพาร์ติเคิลที่มีชีวิตใกล้ๆ ในเลย์เอาต์ rest + emitter เป็นตัวถ่วงช่วงต้นซีน + blend เข้าซิมจริงหลังเกิด และบังคับให้ blend ครบภายในเฟรม rest

Inputs: 0 = rest points ที่มี i@born, i@srcpt · 1 = live sim ที่มี detail v@emitpos · 2 = live-only cloud
Spare parms ที่ต้องสร้าง: blend_time, radius, anchor_weight, max_neighbours (int), rest_frame
อย่าใช้ ch("../node/parm") ใน VEX เพื่ออ่านค่าจาก node อื่น เพราะ path จะหาไม่เจอแล้วได้ 0 ให้ link ผ่าน spare parm แทน

### mark_born.vfl — mark_born — does this id exist yet?

- Where: Attribute Wrangle · Points
- Tested: Houdini 21.0.671

ต่อ input 0 = ท่า rest (timeshift ไปที่เฟรมสุดท้าย) และ input 1 = live sim แล้วจะเขียน i@born กับ i@srcpt (index ของพอยต์นั้นในซิมตอนนี้ ถ้ายังไม่เกิดจะเป็น -1)

idtopoint() ต้องใช้ i@id ที่ไม่ซ้ำกัน ซึ่ง POP สร้างให้อยู่แล้ว

### born_only.vfl — born_only — keep live points only

- Where: Attribute Wrangle · Points
- Tested: Houdini 21.0.671

ลบพอยต์ที่ยังไม่เกิดทิ้ง ใช้แทน Blast @born==0 เพราะไม่ต้องพึ่งการอ่าน group จึงใช้ได้ทุกเวอร์ชัน

### patch_born_v2.py — Patch: follow_born_only Blast → wrangle

- Where: Python Shell
- Tested: Houdini 21.0.671 · current-network tests

แก้ rig ที่สร้างไปแล้ว: หา Blast ชื่อ follow_born_only ใน network ที่ Network Editor เปิดอยู่ (รวมข้างใน) แล้วเปลี่ยนเป็น wrangle ที่ลบพอยต์ตรงๆ พร้อมต่อสายเดิมให้

ใช้เมื่อขึ้นว่าหา attribute born ไม่เจอ (เดาว่า Blast ใน 20.5 อ่าน @born==0 เป็น prim group) · ตัว v2 ใช้ wrangle อยู่แล้ว ไม่ต้อง patch ซ้ำ
