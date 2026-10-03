# RBD pieces → copy root geometry

Category: RBD · Type: Sop · Latest: v007 (2026-10-03)
All versions: v001, v002, v003, v004, v005, v006, v007 (older versions live in the shelf page)

## Notes

v007: add_orient_from_cache.py ใช้กับ cache ที่เป็น packed ได้แล้ว ไม่ต้อง unpack ทุกเฟรม (สำหรับ RBD หนัก ๆ)
• สคริปต์ดูเองว่า cache เป็น packed หรือ polygon แล้วเลือกทางให้
• packed: อ่าน orient + scale จาก intrinsic packedfulltransform ของแต่ละชิ้นตรง ๆ ส่วน P ของ point ก็คือ pivot ที่ขยับแล้ว (PACKED_points)
• prototype: timeshift ไป REST_FRAME → ตั้ง transform = identity, P = 0 → unpack แค่เฟรมนั้นเฟรมเดียว ได้ชิ้นรอบ pivot (PACKED_protos_unpack ไม่ time dependent cook ครั้งเดียว)
• name อยู่บน point (แบบ cache ของพี่) หรือบน prim ก็ได้
• polygon cache ยังใช้ Extract Transform แบบ v006

กับดักที่เจอ:
1) VEX: matrix3(primintrinsic(0, "packedfulltransform", pr)) อ่านค่า 16 ตัวเป็น 3x3 ผิดช่อง scale z กลายเป็น 0 ต้องอ่านเป็น matrix (4x4) ก่อนแล้วค่อย matrix3()
2) ถ้าเขียน v@scale แค่บางจุด จุดอื่นได้ 0 instance หายหมด ต้องเขียนทุกจุด

วัดผลแล้ว (fracture 25 ชิ้น, เฟรม 1/10/25/40, เทียบกับ unpack ของ cache): polygon, packed (name บน prim), packed (name บน point), packed ที่หมุนคนละแกนผ่าน intrinsic transform → SOP ≤ 0.0000012, LOP ≤ 0.0006
ในฉากพี่ (no_unpack, ทำมือ) เฟรม 1-20: SOP ≤ 0.0000003, LOP ≤ 0.00023
ทดสอบกับ H21.0.671 ยังไม่ได้ทดสอบใน 20.5

v006: Recompute orient จาก cache (มีแค่ geometry ที่ cache ไว้ ไม่มี sim points) แล้ว instance ใน LOP
• สคริปต์ใหม่ add_orient_from_cache.py: ตั้ง CACHE_NODE (เช่น filecache1) กับ REST_FRAME แล้วรัน
• Extract Transform (Use Piece Attribute = name, Primitive) เทียบเฟรม rest กับทุกเฟรม → 1 point ต่อชิ้น มี P + orient + pivot
• prototype = ชิ้นที่เฟรม rest เลื่อนด้วย -pivot ให้อยู่ที่ origin แล้วทิ้ง pivot จาก point
• USD ห้ามมี - ในชื่อ prim (piece0-0-0 กลายเป็น piece0_0_0) instancer เลยหา prototype ไม่เจอแล้ว skip ทุกชิ้น สคริปต์ทำชื่อให้ตรงกันทั้งสองฝั่ง
• cache ที่เป็น packed จะ unpack ให้ก่อน (เก็บ name ไว้)

วัดผลแล้ว (fracture 25 ชิ้น, เฟรม 1/10/25/40): ประกอบชิ้นกลับจาก orient + P ตรงกับ cache ≤ 0.000001 · LOP (unpack กลับ) ≤ 0.0005 ทั้ง cache แบบ polygon, packed และชิ้นที่หมุนคนละแกน
ในฉากของพี่ (rbd_root_copy/filecache1) ทำมือแล้วเทียบที่เฟรม 20 ได้ 0.0000003
ทดสอบกับ H21.0.671 ยังไม่ได้ทดสอบใน 20.5

v005: ใช้กล่อง fracture เป็นชิ้น root (ตามไฟล์ emittingRBD_root ของพี่)
• ROOT_SOURCE = "fracture" (default): box → RBD Material Fracture → Clean (ลบ attrib/group) → Normal (cusp 0) → Assemble (pack) = piece0..pieceN-1
• emitter สุ่มชื่อชิ้นจากจำนวนชิ้นจริง: ต่อ root เข้า input 2 ของ demo_piece_name แล้วใช้ npoints(1) ไม่ต้องแก้ตัวเลขเมื่อเปลี่ยนจำนวนชิ้น
• ROOT_SOURCE = "colours" ได้แบบเดิม (กล่อง 3 สี) · EMIT_PER_FRAME = จำนวนชิ้นที่เกิดต่อเฟรม
• โหมด BUILD_DEMO = False ใช้กับ sim ที่มีอยู่แล้วได้เหมือนเดิม: DOPNET = dopnet ของพี่, ROOT_PIECES = node ที่ assemble ชิ้น fracture

วัดผลแล้ว (fracture 25 ชิ้น, 40 เฟรม): Copy to Points ทั้งแบบ packed และ points ตรงกับ sim ≤ 0.000001 · LOP ≤ 0.0004 (ทั้งฉากว่าง, ใน emittingRBD_root_lopfix, และต่อเข้า demo_rbd_dopnet1 ของพี่ใน geo1)
ไฟล์ตัวอย่าง: emittingRBD_fracture_v5.hipnc (geo ใหม่ rbd_root_copy1 ข้าง geo1 เดิม)

v004: เพิ่มเวอร์ชัน LOP / Solaris (USD PointInstancer)
• builder มี ADD_LOP = True (default) สร้าง LOP_instancing ต่อจาก target points ให้เลย
• มีสคริปต์แยก add_lop_instancer.py สำหรับต่อ LOP เข้ากับ setup ที่มีอยู่แล้ว (ตั้ง TARGETS_NODE กับ ROOT_NODE)

สองจุดที่ทำให้ instance ผิดถ้าปล่อยค่า default:
1) Prototype Primitives = ทั้ง sopimport (เช่น /sopimport1) → ทุก instance ได้ทุกชิ้นซ้อนกัน ต้องเป็น /<sopimport>/* ให้แต่ละชิ้นเป็น prototype ของตัวเอง และ Prototype Index = Name Attribute (name) ให้ point ชื่อ piece3 ได้ prototype piece3
2) LOP Import ที่ใช้ %type:Boundable & %visible จะดึง prototype mesh ที่ซ่อนอยู่มาด้วย ให้ import แค่ /instancer1
และ Unpack USD ต้องตั้ง Iterations = 2 (instancer → instances → mesh) ไม่งั้นได้ point เดียวต่อ instance

Instancer อ่าน 3@transform เองได้ แปลงเป็น orientation + scale ให้ ไม่ต้องแปลงก่อน
วัดผลแล้ว: LOP ตรงกับ Copy to Points ≤ 0.0007 ทุกเฟรมที่เช็ค (ส่วนต่างนี้มาจาก USD เก็บ orientations เป็น half precision) ทั้ง demo ในฉากว่าง และไฟล์ emittingRBD_root ที่ใช้ชิ้น fracture 25 ชิ้นเป็น root

v003: เพิ่มวิธีที่สอง import มาแค่ point (DOP Import → Create Points to Represent Objects)
• ไม่ต้องดึง geometry ออกจากซิมเลย เบากว่า ใช้แค่ point ละชิ้น
• ใช้ restxform ที่ Bullet เก็บไว้บน point (การหมุน + pscale ตอน emit และตำแหน่ง rest) + pivot + orient + P สร้าง transform เต็มกลับมา: world = (rest - pivot) × orient + P
• ต้องใส่ restxform ใน Transfer Attributes ของ DOP Import (สคริปต์ใส่ให้แล้ว: orient pivot restxform name v)
• METHOD = "both" (default) สร้างทั้งสองวิธีคู่กัน · "points" หรือ "packed" เลือกอันเดียว

วัดผลแล้ว: ทั้งสองวิธีตรงกับซิม max_err ≤ 0.000001 ทุก point ที่เฟรม 1, 12, 30, 48 ทั้ง demo ในฉากว่างและไฟล์ emittingRBD

v002: paste แล้วสร้างทั้งฉากใหม่หมด แบบเดียวกับ FX Template
• BUILD_DEMO = True (default): สร้างชิ้น root 3 สี, emitter ที่ปล่อยชิ้นใหม่ทุกเฟรม (pscale + N สุ่ม), Bullet RBD dopnet และ chain copy-from-root ครบในตัว
• เปิด /obj แล้วรัน = สร้าง geo ใหม่ชื่อ rbd_root_copy · เปิด Geometry network แล้วรัน = สร้างตรงนั้น ต่อลงไปใต้ node เดิม
• Start frame ของ dopnet = start ของ playbar (START_FRAME / LINK_TO_PLAYBAR ปรับได้)
• BUILD_DEMO = False: ต่อแค่ chain เข้าซิมของพี่ ตั้ง DOPNET กับ ROOT_PIECES
• OBJ_PATTERN default เป็น *rbd* เพราะ * จะดึง ground plane มาด้วย

วัดผลแล้ว: demo ที่สร้างจากศูนย์ในฉากว่าง และไฟล์ emittingRBD ตรงกับซิม max_err 0.000000 ทุก point ที่เฟรม 1, 12, 30, 48
รันซ้ำใน network เดิมได้ ไม่ชนกัน

ปัญหา: เอาชิ้นจาก RBD sim มา Copy to Points แล้วชิ้นหมุนเพี้ยนและเลื่อนผิดที่ เพราะชิ้นต้นแบบที่ใช้ copy ไม่ได้อยู่ในท่า rest (ใช้ชิ้นที่ซิมเสร็จแล้วที่เฟรมสุดท้าย) orient เลยหมุนซ้ำทับ และ pivot จากซิมเป็นตำแหน่ง world ตอน emit

วิธีหลัก: copy ชิ้น ROOT (ต้นฉบับจาก assemble) ด้วย packedfulltransform ของแต่ละชิ้นในซิม ซึ่งรวมการหมุนตอน emit + pscale + การเคลื่อนที่ของซิมไว้หมดแล้ว เปลี่ยน geo ต้นฉบับ (hi-res / โมเดลอื่น) ได้โดยไม่ต้องซิมใหม่

วัดผลกับ emittingRBD.hipnc: ตรงกับซิมจริง max_err 0.000000 ทุก point ที่เฟรม 3, 12, 20, 25, 38
ทดสอบกับ H21.0.671

## Files

### build_rbd_root_copy_v5.py — Builder: fractured box root + RBD + root copy + LOP

- Where: Python Shell
- Tested: Houdini 21.0.671 · empty scene + emittingRBD_root_lopfix

paste ใน Python Shell แล้วสร้างทุกอย่างใหม่หมด: กล่อง fracture เป็นชิ้น root → emitter ที่สุ่มชิ้น → RBD dopnet → Copy to Points (packed / points) → LOP_instancing พร้อม LOP_check_unpackusd ไว้เทียบผล

ชิ้นที่ emit เป็น packed อยู่แล้วหลัง Copy to Points ห้าม Assemble ซ้ำ ไม่งั้นชิ้นจะซ้อน packed สองชั้น แล้ว packedfulltransform จะชี้ไปที่ชั้นนอก
ชิ้นต้นฉบับต้องมี name ตรงกับชื่อชิ้นในซิม ถ้าซิมตั้งชื่อ piece0_12 (เติมเฟรมตอน emit) STRIP_SUFFIX = True จะตัด _12 ออกให้เป็น piece0
ใช้ได้เพราะ packed prim ในซิมเก็บ geo ต้นฉบับตัวเดียวกันไว้ข้างใน ต่างกันแค่ transform

### add_lop_instancer.py — Add the LOP PointInstancer to an existing setup

- Where: Python Shell
- Tested: Houdini 21.0.671 · emittingRBD_root

ต่อเวอร์ชัน LOP เข้ากับ SOP ที่มีอยู่แล้ว: ต้องมี target points (name + transform หรือ orient/pscale) กับชิ้น root ที่มี name ตั้ง TARGETS_NODE / ROOT_NODE แล้วรัน

สร้าง LOP_targets, LOP_prototypes (null), LOP_instancing (sopimport root_pieces → instancer1 → OUT_instances) และ LOP_check_import → LOP_check_unpackusd กลับมาใน SOP ไว้เช็ค
ใช้ได้กับ Copy to Points ทั่วไปด้วย ไม่จำกัดแค่ RBD

### rbd_root_targets.vfl — ROOT_targets: full transform per piece

- Where: Attribute Wrangle · Points
- Tested: Houdini 21.0.671

ต่อหลัง DOP Import แบบ Fetch Packed Geometry ได้ target หนึ่ง point ต่อชิ้น มี 3@transform กับ P ตรงกับชิ้นในซิม แล้ว Copy to Points ชิ้น root (Piece Attribute = name)

ต่อจากนี้: Attribute Delete (Delete Non Selected: name transform v) → Add (Delete Geometry But Keep the Points)
ต้องลบ orient / pivot / pscale / N ทิ้ง ไม่งั้นจะไปแย่ง transform

### rbd_point_targets.vfl — ROOT_point_targets: points-only import

- Where: Attribute Wrangle · Points
- Tested: Houdini 21.0.671

วิธีที่สอง: ต่อหลัง DOP Import แบบ Create Points to Represent Objects ได้ 3@transform กับ P ของแต่ละชิ้นจาก point ของซิมอย่างเดียว ไม่ต้อง import geometry

DOP Import ต้องใส่ Transfer Attributes = orient pivot restxform name v (restxform สำคัญที่สุด ถ้าไม่มีจะได้ชิ้นที่ไม่หมุนตอน emit และไม่มี pscale)
ต่อจากนี้: Attribute Delete (Delete Non Selected: name transform v) แล้วเข้า Copy to Points ได้เลย ไม่ต้องใช้ Add SOP เพราะไม่มี prim ติดมา

### back_to_rest_pose.vfl — back_to_rest_pose: final-frame pieces → rest

- Where: Attribute Wrangle · Points
- Tested: Houdini 21.0.671

อีกทางหนึ่ง ถ้าอยาก copy ชิ้นที่ fetch มาจากซิม (เช่นเฟรมสุดท้าย) แทนชิ้น root: ถอยการหมุนและการเลื่อนของซิมออก ให้ชิ้นกลับไปอยู่ตรงจุดที่ emit แล้วใช้ orient / pivot / P ของ RBD points ตามปกติ

วัดแล้วตรงกับซิม max_err 0.00000 ที่เฟรม 5, 15, 25, 36 · Timeshift ของสอง input ต้องเป็นเฟรมเดียวกัน

### measure_orient_diff.vfl — Measure orient difference between two copies

- Where: Attribute Wrangle · Detail
- Tested: Houdini 21.0.671

เช็คว่า geo สองชุด (ชิ้นเดียวกัน) หมุนต่างกันกี่องศา รอบแกนไหน เลื่อนไปเท่าไหร่ โดยวัดจากตำแหน่ง point จริง ไม่ต้องพึ่ง attribute orient

อ่านผล: angle ≈ 0 แต่ offset ไม่ 0 = ปัญหา pivot · angle ≈ 180 = แกนกลับด้าน · fit_rms สูง = shape ต่างด้วย (scale หรือลำดับ point ไม่ตรง)
ทางไม่ต้องเขียนโค้ด: Extract Transform SOP (input 1 = ตัวถูก, input 2 = ตัวที่เช็ค)

### add_orient_from_cache.py — Recompute orient from a cache (packed or polygons) → LOP PointInstancer

- Where: Python Shell
- Tested: Houdini 21.0.671 · empty scene (polygons / packed prim name / packed point name / packed spin) + Plug's no_unpack

มีแค่ cache ของชิ้นไม่มี sim points: สร้าง point ต่อชิ้นพร้อม orient แล้ว instance ใน LOP ถ้า cache เป็น packed จะอ่าน packedfulltransform ตรง ๆ ไม่ unpack ทุกเฟรม (unpack แค่เฟรม rest ทำ prototype) ถ้าเป็น polygon ใช้ Extract Transform ตั้ง CACHE_NODE กับ REST_FRAME แล้วรัน

packed: ORIENT_rest → PACKED_protos_origin → PACKED_protos_unpack → ORIENT_protos_path → OUT_orient_protos และ PACKED_points → OUT_orient_points
polygon: ORIENT_rest → ORIENT_extract → ORIENT_points / ORIENT_protos → OUT_*
ADD_LOP = True สร้าง LOP_orient_instancing และ LOP_orient_check_unpackusd ไว้เช็คใน SOP
ชื่อชิ้นถูกแก้ให้ USD รับ (piece0-0-0 → piece0_0_0) ทั้งฝั่ง point และ prototype
REST_FRAME ต้องเป็นเฟรมที่ชิ้นยังไม่ขยับ
