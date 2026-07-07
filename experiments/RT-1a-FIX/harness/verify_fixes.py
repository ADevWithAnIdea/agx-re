#!/usr/bin/env python3
# RT-1a-FIX: verify the DB edits (decode + roundtrip) that the HW re-validation
# justified. Pure DB check (no device needed); run from anywhere.
import sys
sys.path.insert(0, "/Users/user/cleanroom_gpu/tools/agx-isa")
import isadb

fails = 0
def check(label, cond):
    global fails
    print(f"  [{'OK' if cond else 'FAIL'}] {label}")
    fails += not cond

def dec(h):
    rec, _ = isadb.decode_one(bytes.fromhex(h), 0)
    return rec

def rt(h):
    rec = dec(h)
    return isadb.assemble(rec["mnemonic"], rec["fields"]).hex() == h

print("== item 1: memory index register + inert +6 + immediate offset ==")
ld = dec("6700460a02802000510100404600")            # bank a[i0] load
check("device_load has index_reg field (was 'count')", "index_reg" in ld["fields"])
check("device_load has inert6 field", "inert6" in ld["fields"])
check("device_load has idx_off field", "idx_off" in ld["fields"])
check("device_load roundtrips", rt("6700460a02802000510100404600"))

print("== item 2: iadd2 add/sub polarity ==")
check("byte0 0x9f decodes as iadd (ADD)", dec("9f015600020800a81705").get("op_mnemonic") == "iadd")
check("byte0 0x1f decodes as isub (SUBTRACT)", dec("1f015600020010a81705").get("op_mnemonic") == "isub")

print("== item 3: float uniform source vs minifloat immediate ==")
check("a+uniform (09 0d ..) -> falu2_uni", dec("090d140180c0")["mnemonic"] == "falu2_uni")
check("a+1.0    (09 b1 ..) -> falu2i",     dec("09b1140180c0")["mnemonic"] == "falu2i")
check("falu2_uni roundtrips", rt("090d140180c0"))

print("== item 4: undecoded groups now decode ==")
check("0x60 -> spill_frame_marker (len 4)", dec("60000000")["mnemonic"] == "spill_frame_marker")
check("compact accum 0x18 -> falu_acc", dec("190b1809")["mnemonic"] == "falu_acc")
check("compact accum 0x38 -> falu_acc", dec("09013811")["mnemonic"] == "falu_acc")
# both former-halting programs tokenize with 0 leftover:
big = ("8ca09106600000009f11540a0300408910049f0154040210288c11049f0154020208288c1104"
       "9f015400021828881104")
_, lo = isadb.disassemble(bytes.fromhex(big))
check("big.bin prefix tokenizes 0 leftover (was halting at 0x60)", lo == b"")
fb = ("8ca010069f115402030040c810149f01540002080888110467005408028120005701004046006700"
      "440002802000170000404600790f3c0d00c0090f3c0100200901380329013805190b18090905180"
      "7e700540200082000110000901100e7005400010821001100009011000e000000")
_, lo2 = isadb.disassemble(bytes.fromhex(fb))
check("falubank.bin tokenizes 0 leftover (was halting at 0x18)", lo2 == b"")

print("== item 5: imm_decode guarded to e>=8 ==")
try:
    isadb.imm_decode(0x0d, 0); check("imm_decode(0x0d) raises (e<8, uniform overload)", False)
except ValueError:
    check("imm_decode(0x0d) raises (e<8, uniform overload)", True)
try:
    isadb.imm_decode(0x100, 0); check("imm_decode(0x100) raises (not a byte)", False)
except ValueError:
    check("imm_decode(0x100) raises (not a byte)", True)
check("imm_decode(0xb1)=1.0 still works", abs(isadb.imm_decode(0xb1, 0) - 1.0) < 1e-9)

print(f"\n{'ALL PASS' if fails == 0 else str(fails)+' FAILURES'}  (DB now has {len(isadb.DB)} descriptors)")
sys.exit(1 if fails else 0)
