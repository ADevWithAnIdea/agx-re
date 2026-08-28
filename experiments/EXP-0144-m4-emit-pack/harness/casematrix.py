#!/usr/bin/env python3
"""EXP-0144 FROZEN case matrix. Deterministic: build_cases() must return the
identical list on every invocation (it is hashed into CAPTURE_CONTRACT.json and
re-checked by both runs).

Arms
  S  semantic     unspliced carrier over many input vectors; full host oracle.
                  Establishes each instruction's conversion semantics + rounding.
  F  field sweep  every BYTE of the instruction under test, all 256 values, one
                  fixed input vector. This is the emittability sweep.
  X  cross        the two pack/unpack bytes that the pilot showed select the
                  FORMAT, crossed with 8 semantic vectors, so a format code
                  discovered by arm F can be given semantics an emitter can use.
  W  wide         whole-field values for the >8-bit raw fields (fmt_word 40b,
                  convert_desc 32b): 0, all-ones, every single-bit value, and
                  interior samples.
  C  control      baselines, positive controls and the pre-registered FALSIFIERS.
"""
import json, struct, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
sys.path.insert(0, str(HERE))
import isadb           # noqa: E402  read-only
import oracle as O     # noqa: E402

M32 = 0xFFFFFFFF
def lo16(u): return u & 0xFFFF
def bf(x):   return O.f32_bits(x)

# --------------------------------------------------------------------------
# Frozen carrier/anchor table. `off` and `anchor` are asserted at run time
# against the freshly compiled carrier; a mismatch aborts the run.
# --------------------------------------------------------------------------
TARGETS = [
  dict(key="pack_convert",    carrier="c_pack",    mnem="pack_convert",    off=138,
       anchor="97045618020802504482", mode="B"),
  dict(key="unpack_convert",  carrier="c_unpack",  mnem="unpack_convert",  off=138,
       anchor="1704560000080eca",     mode="B"),
  dict(key="cvt_i2f",         carrier="c_i2f",     mnem="cvt_i2f",         off=138,
       anchor="a707561802008e60",     mode="B"),
  dict(key="cvt_i2f_src",     carrier="c_i2f_src", mnem="cvt_i2f_src",     off=146,
       anchor="a717541803008c60",     mode="B"),
  dict(key="cvt_f2i",         carrier="c_f2i",     mnem="cvt_f2i",         off=138,
       anchor="27075618020096480300", mode="B"),
  dict(key="cvt_f2h",         carrier="c_f2h",     mnem="cvt_f2h",         off=156,
       anchor="010114810402",         mode="B"),
  dict(key="cvt_f2h_dst",     carrier="c_f2h_dst", mnem="cvt_f2h_dst",     off=156,
       anchor="c10114810402",         mode="B"),
  dict(key="cvt_bf16",        carrier="c_f2bf",    mnem="cvt_bf16",        off=156,
       anchor="0101148105024000",     mode="B"),
  # MODE A: the carrier's own 6-byte half_alu is REPLACED by an assembled
  # packed_half2_hi (byte0 low nibble 8, byte+2 == 0x24). Same length, so the
  # instruction stream stays aligned IFF db.json's length 6 is right for this
  # family -- itself part of what this arm tests (byte0=0x18 is a length-rule
  # gap: isadb.instr_length() cannot length it at all). packed_half2_hi could
  # NOT be provoked from any MSL shape tried (work/pilot/carriers.log), so a
  # synthesised encoding is the only way to reach it at all.
  dict(key="packed_half2_hi", carrier="c_ph2",     mnem="packed_half2_hi", off=108,
       anchor="900405000020", mode="A", synth="980424000020"),
]
BY_KEY = {t["key"]: t for t in TARGETS}

# --------------------------------------------------------------------------
# Input vectors + per-carrier host oracle (index -> expected u32 output word)
# --------------------------------------------------------------------------
PAD = 4072

def _pk(fmt, vals, pad=PAD):
    return struct.pack(fmt, *vals) + b"\x00" * pad

# The FIXED vector each field sweep runs on (six mutually distinguishable values
# live across the instruction, so a src-field value that selects a different
# register produces a different, identifiable output).
FIXED = {
  "c_pack":    ("<6f", (0.25, 0.75, 0.125, 0.375, 0.625, 0.875)),
  "c_unpack":  ("<6I", (0x12345678, 0x00010002, 0x00030004, 0x00050006, 0x00070008, 0x0009000A)),
  "c_i2f":     ("<6i", (3, 5, 7, 11, 13, 17)),
  "c_i2f_src": ("<6i", (3, 5, 7, 11, 13, 17)),
  "c_f2i":     ("<6f", (3.75, -2.5, 7.25, 11.5, -13.125, 17.875)),
  "c_f2h":     ("<6f", (1.5, 2.25, 3.125, -4.75, 5.5, 0.375)),
  "c_f2h_dst": ("<6f", (1.5, 2.25, 3.125, -4.75, 5.5, 0.375)),
  "c_f2bf":    ("<6f", (1.5, 2.25, 3.125, -4.75, 5.5, 0.375)),
  "c_ph2":     ("<8e", (1.5, 2.5, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0)),
}

# Semantic vectors -- chosen for the ROUNDING and BOUNDARY questions, not for
# convenience. Each entry is the tuple fed to the carrier's own FIXED format.
SEM = {
 "c_pack": [
   (0.25, 0.75, 0, 0, 0, 0), (0.0, 1.0, 0, 0, 0, 0), (-1.0, 2.0, 0, 0, 0, 0),
   (0.5, 0.5, 0, 0, 0, 0),                                   # exact tie 32767.5
   (1.0/65535.0, 2.0/65535.0, 0, 0, 0, 0),
   (0.5/65535.0, 1.5/65535.0, 0, 0, 0, 0),                   # two more exact ties
   (2.5/65535.0, 3.5/65535.0, 0, 0, 0, 0),                   # ties at odd/even
   (float("nan"), 0.5, 0, 0, 0, 0), (float("inf"), float("-inf"), 0, 0, 0, 0),
   (1e-45, -1e-45, 0, 0, 0, 0),                              # subnormals
   (0.9999999, 1.0000001, 0, 0, 0, 0), (0.123456, 0.654321, 0, 0, 0, 0),
   (1.0/3.0, 2.0/3.0, 0, 0, 0, 0), (0.999992370605, 0.000007629395, 0, 0, 0, 0),
   (0.3333, 0.6667, 0, 0, 0, 0), (0.0625, 0.9375, 0, 0, 0, 0),
 ],
 "c_unpack": [
   (0x12345678, 0, 0, 0, 0, 0), (0x00000000, 0, 0, 0, 0, 0), (0xFFFFFFFF, 0, 0, 0, 0, 0),
   (0x00010000, 0, 0, 0, 0, 0), (0x8000FFFF, 0, 0, 0, 0, 0), (0x7FFF8000, 0, 0, 0, 0, 0),
   (0x00018000, 0, 0, 0, 0, 0), (0xFFFE0001, 0, 0, 0, 0, 0), (0x55553333, 0, 0, 0, 0, 0),
   (0xAAAACCCC, 0, 0, 0, 0, 0), (0x0001FFFE, 0, 0, 0, 0, 0), (0x40008001, 0, 0, 0, 0, 0),
 ],
 "c_i2f": [
   (3, 5, 7, 11, 13, 17), (0, 1, -1, 2, -2, 3), (2147483647, -2147483648, 0, 0, 0, 0),
   (16777216, 16777217, 16777219, -16777217, 0, 0),           # fp32 RTE boundary
   (33554432, 33554433, 33554435, 33554437, 0, 0),
   (1000000, -1000000, 123456789, -123456789, 0, 0),
   (-1, -3, -5, 65535, 65536, 65537),
 ],
 "c_i2f_src": [
   (3, 5, 7, 11, 13, 17), (0, 0, 0, 0, 0, 0), (2147483647, 1, 0, 0, 0, 0),
   (16777216, 1, 0, 0, 0, 0), (-2147483648, -1, 0, 0, 0, 0), (123456, 654321, 0, 0, 0, 0),
 ],
 "c_f2i": [
   (3.75, -2.5, 7.25, 11.5, -13.125, 17.875), (0.9, -0.9, 1.5, -1.5, 2.5, -2.5),
   (0.0, -0.0, 1.0, -1.0, 0.5, -0.5), (2147483647.0, -2147483648.0, 0, 0, 0, 0),
   (1e30, -1e30, float("inf"), float("-inf"), 0, 0), (float("nan"), 3.9, 0, 0, 0, 0),
   (16777216.5, -16777216.5, 0, 0, 0, 0), (1e-40, -1e-40, 0, 0, 0, 0),
 ],
 "c_f2h": [
   (1.5, 2.25, 3.125, -4.75, 5.5, 0.375), (65504.0, 65520.0, 65536.0, -65504.0, 0, 0),
   (6.1e-5, 6.0e-8, 2.98e-8, 2.99e-8, 0, 0),                  # subnormal + tie
   (1.0009765625, 1.00048828125, 1.00146484375, 0, 0, 0),     # fp16 RTE ties
   (float("nan"), float("inf"), float("-inf"), 0, 0, 0),
   (0.1, 0.2, 0.3, 0.7, 1.0/3.0, 1e-45),
 ],
 "c_f2h_dst": [
   (1.5, 2.25, 3.125, -4.75, 5.5, 0.375), (65504.0, 65520.0, 65536.0, -65504.0, 0, 0),
   (1.0009765625, 1.00048828125, 1.00146484375, 0, 0, 0),
   (float("nan"), float("inf"), float("-inf"), 0, 0, 0), (0.1, 0.2, 0.3, 0.7, 0.5, 0.25),
 ],
 "c_f2bf": [
   (1.5, 2.25, 3.125, -4.75, 5.5, 0.375), (3.14159265, 2.71828182, 1.41421356, 0, 0, 0),
   (1.00390625, 1.001953125, 1.005859375, 0, 0, 0),           # bf16 RNE ties
   (float("nan"), float("inf"), float("-inf"), 0, 0, 0), (1e-45, 1e38, -1e38, 0, 0, 0),
   (0.1, 0.2, 0.3, 0.7, 0.5, 0.25),
 ],
 "c_ph2": [
   (1.5, 2.5, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0), (0.5, -0.5, 2.0, -2.0, 1.0, 1.0, 1.0, 1.0),
   (65504.0, 1.0, 2.0, 1.0, 0.0, 0.0, 0.0, 0.0), (6.0e-8, 1.0, 1.0, 1.0, 0, 0, 0, 0),
 ],
}

# The 8 vectors the cross arm (X) uses.
XSEM = {"c_pack": SEM["c_pack"][:8], "c_unpack": SEM["c_unpack"][:8]}

RESULT_SLOTS = {"c_pack": [0], "c_unpack": [0, 1], "c_i2f": [0], "c_i2f_src": [0],
                "c_f2i": [0], "c_f2h": [0], "c_f2h_dst": [0], "c_f2bf": [0], "c_ph2": [0]}
NOUT_BYTES = 256


def invec_bytes(carrier, vals):
    return _pk(FIXED[carrier][0], vals)


def expect(carrier, v):
    """Host oracle: {word_index: expected u32}. NEVER consults the GPU."""
    if carrier == "c_pack":
        return {0: O.pack_unorm2x16(v[0], v[1]),
                1: bf(v[2]), 2: bf(v[3]), 3: bf(v[4]), 4: bf(v[5]), 5: bf(v[0]), 6: bf(v[1])}
    if carrier == "c_unpack":
        x, y = O.unpack_unorm2x16(v[0])
        return {0: bf(x), 1: bf(y), 2: v[1] & M32, 3: v[2] & M32, 4: v[3] & M32,
                5: v[4] & M32, 6: v[5] & M32, 7: v[0] & M32}
    if carrier == "c_i2f":
        return {0: bf(O.i2f(v[0] & M32)), 1: v[1] & M32, 2: v[2] & M32, 3: v[3] & M32,
                4: v[4] & M32, 5: v[5] & M32, 6: v[0] & M32}
    if carrier == "c_i2f_src":
        s = struct.unpack("<f", struct.pack("<f", O.i2f(v[0] & M32) + O.i2f(v[1] & M32)))[0]
        return {0: bf(s), 1: v[2] & M32, 2: v[3] & M32, 3: v[4] & M32, 4: v[5] & M32,
                5: v[0] & M32, 6: v[1] & M32}
    if carrier == "c_f2i":
        return {0: O.f2i(v[0]), 1: bf(v[1]), 2: bf(v[2]), 3: bf(v[3]), 4: bf(v[4]),
                5: bf(v[5]), 6: bf(v[0])}
    if carrier == "c_f2h":
        h = [O.f2h(v[0])] + [lo16(bf(v[i])) for i in (1, 2, 3, 4, 5)] + [lo16(bf(v[0]))]
        return {0: h[0] | (h[1] << 16), 1: h[2] | (h[3] << 16), 2: h[4] | (h[5] << 16), 3: h[6]}
    if carrier == "c_f2h_dst":
        h = [O.f2h(v[0]), O.f2h(v[1]), O.f2h(v[2])] + [lo16(bf(v[i])) for i in (3, 4, 5)] \
            + [lo16(bf(v[0]))]
        return {0: h[0] | (h[1] << 16), 1: h[2] | (h[3] << 16), 2: h[4] | (h[5] << 16), 3: h[6]}
    if carrier == "c_f2bf":
        h = [O.f2bf_rne(v[0])] + [lo16(bf(v[i])) for i in (1, 2, 3, 4, 5)] + [lo16(bf(v[0]))]
        return {0: h[0] | (h[1] << 16), 1: h[2] | (h[3] << 16), 2: h[4] | (h[5] << 16), 3: h[6]}
    if carrier == "c_ph2":
        hb = [O.f16_bits(x) for x in v]
        w = lambda a, b: (a | (b << 16)) & M32
        return {0: w(O.hmul(hb[0], hb[2]), O.hmul(hb[1], hb[3])),
                1: w(hb[4], hb[5]), 2: w(hb[6], hb[7]), 3: w(hb[0], hb[1]), 4: w(hb[2], hb[3])}
    raise KeyError(carrier)


# --------------------------------------------------------------------------
# byte index -> db.json field names covering it
# --------------------------------------------------------------------------
_DB = {i["mnemonic"]: i for i in json.loads(isadb.to_json())["instructions"]} \
    if isinstance(isadb.to_json(), str) else \
      {i["mnemonic"]: i for i in isadb.to_json()["instructions"]}

def fields_for_byte(mnem, b):
    d = _DB.get(mnem)
    if not d:
        return []
    lo, hi = 8 * b, 8 * b + 8
    out = []
    for f in d["fields"]:
        if f["start"] < hi and (f["start"] + f["width"]) > lo:
            out.append(f["name"])
    m = [f"match[{s}:{s+w}]={v}" for (s, w, v) in d["match"] if s < hi and (s + w) > lo]
    return out + m


# --------------------------------------------------------------------------
def build_cases():
    cases = []
    def add(**kw):
        kw["i"] = len(cases)
        cases.append(kw)

    # ---- arm C : baselines + falsifiers -----------------------------------
    for t in TARGETS:
        add(arm="C", name="baseline_%s" % t["key"], instr=t["mnem"], field="-",
            carrier=t["carrier"], value=None, splices={}, vec=FIXED[t["carrier"]][1],
            expect_model="anchor",
            note="POS-CTRL: unspliced carrier (MODE A targets still splice the synth "
                 "instruction) must reproduce the host oracle exactly, else the arm is void")
    for t in TARGETS:
        base = bytes.fromhex(t["synth"] if t["mode"] == "A" else t["anchor"])
        add(arm="C", name="falsifier_byte0_ff_%s" % t["key"], instr=t["mnem"],
            field="byte0", carrier=t["carrier"], value=0xFF,
            splices={t["off"] + i: b for i, b in enumerate(base)} | {t["off"]: 0xFF},
            vec=FIXED[t["carrier"]][1], expect_model="anchor",
            note="FALSIFIER (pre-registered to FAIL the anchor oracle): an illegal "
                 "leader byte must not reproduce the documented result")
    add(arm="C", name="falsifier_pack_src_02", instr="pack_convert", field="src",
        carrier="c_pack", value=0x02,
        splices={BY_KEY["pack_convert"]["off"] + 3: 0x02},
        vec=FIXED["c_pack"][1], expect_model="anchor",
        note="FALSIFIER (pre-registered to FAIL): src=0x02 selects a different register "
             "than the anchor's 0x18, so the anchor oracle must NOT be reproduced")

    # ---- arm S : semantics --------------------------------------------------
    for t in TARGETS:
        c = t["carrier"]
        for j, v in enumerate(SEM[c]):
            sp = {}
            if t["mode"] == "A":
                sp = {t["off"] + i: b for i, b in enumerate(bytes.fromhex(t["synth"]))}
            add(arm="S", name="sem_%s_%02d" % (t["key"], j), instr=t["mnem"], field="-",
                carrier=c, value=None, splices=sp, vec=v, expect_model="anchor",
                note="semantic vector %d" % j)

    # ---- arm F : dense per-byte field sweep --------------------------------
    # Byte 0 is the OPCODE LEADER, not an operand field. The smoke run showed a
    # dense byte0 sweep produces genuine GPU hangs (byte0=0xFF on cvt_bf16 raised
    # kIOGPUCommandBufferCallbackErrorHang), because changing the leader changes
    # the instruction's LENGTH and desynchronises the whole downstream stream.
    # This host has no out-of-band recovery, so byte0 gets a BOUNDED 24-value
    # probe instead of 256: all 16 values of its HIGH nibble with the match-forced
    # low nibble preserved (that high nibble IS the `dst` field in cvt_f2h_dst /
    # cvt_bf16 / packed_half2_hi), plus 8 off-match values to test whether the
    # match's low nibble is actually load-bearing. Every OPERAND byte still gets
    # the full dense 0..255. This deviation from "w<=8 -> sweep all 2^w" is
    # deliberate, safety-driven, and reported as such.
    def byte0_values(anchor0):
        lo = anchor0 & 0x0F
        vals = [(hi << 4) | lo for hi in range(16)]
        vals += [anchor0 ^ (1 << k) for k in range(4)]        # flip each low-nibble bit
        vals += [0x00, 0xFF, anchor0 ^ 0xFF, (anchor0 + 1) & 0xFF]
        seen, outv = set(), []
        for v in vals:
            if v not in seen:
                seen.add(v); outv.append(v)
        return outv

    for t in TARGETS:
        c, off = t["carrier"], t["off"]
        base = bytes.fromhex(t["synth"] if t["mode"] == "A" else t["anchor"])
        for b in range(len(base)):
            vlist = byte0_values(base[0]) if b == 0 else range(256)
            for val in vlist:
                sp = {off + i: x for i, x in enumerate(base)} if t["mode"] == "A" else {}
                sp = dict(sp)
                sp[off + b] = val
                add(arm="F", name="f_%s_b%d_%02x" % (t["key"], b, val), instr=t["mnem"],
                    field="+".join(fields_for_byte(t["mnem"], b)) or "byte%d" % b,
                    carrier=c, byte=b, value=val, splices=sp, vec=FIXED[c][1],
                    expect_model="anchor", note="")

    # ---- arm W : whole-field values for the >8-bit raw fields ---------------
    def wide(key, mnem, carrier, byte_lo, nbytes, fieldname):
        t = BY_KEY[key]
        base = bytes.fromhex(t["anchor"])
        anchor_val = int.from_bytes(base[byte_lo:byte_lo + nbytes], "little")
        vals = [0, (1 << (8 * nbytes)) - 1, anchor_val]
        vals += [1 << k for k in range(8 * nbytes)]
        vals += [((1 << (8 * nbytes)) - 1) ^ (1 << k) for k in range(0, 8 * nbytes, 3)]
        vals += [anchor_val ^ (1 << k) for k in range(8 * nbytes)]
        seen = set()
        for v in vals:
            v &= (1 << (8 * nbytes)) - 1
            if v in seen:
                continue
            seen.add(v)
            sp = {t["off"] + byte_lo + i: b for i, b in
                  enumerate(v.to_bytes(nbytes, "little"))}
            add(arm="W", name="w_%s_%s_%0*x" % (key, fieldname, nbytes * 2, v), instr=mnem,
                field=fieldname, carrier=carrier, value=v, splices=sp,
                vec=FIXED[carrier][1], expect_model="anchor",
                note="whole-field value, width %d bits" % (8 * nbytes))
    wide("pack_convert", "pack_convert", "c_pack", 5, 5, "fmt_word")
    wide("unpack_convert", "unpack_convert", "c_unpack", 3, 4, "convert_desc")

    # ---- arm X : format-selector bytes x semantic vectors -------------------
    for key, bytes_of_interest in (("pack_convert", (8, 9)), ("unpack_convert", (7,))):
        t = BY_KEY[key]
        c = t["carrier"]
        for b in bytes_of_interest:
            for val in range(256):
                for j, v in enumerate(XSEM[c]):
                    add(arm="X", name="x_%s_b%d_%02x_v%d" % (key, b, val, j), instr=t["mnem"],
                        field="+".join(fields_for_byte(t["mnem"], b)) or "byte%d" % b,
                        carrier=c, byte=b, value=val, splices={t["off"] + b: val}, vec=v,
                        expect_model="anchor",
                        note="format-code x semantic-vector cross (vector %d)" % j)
    return cases


if __name__ == "__main__":
    import collections, hashlib, json
    cs = build_cases()
    print("total cases: %d" % len(cs))
    print(collections.Counter(c["arm"] for c in cs))
    blob = json.dumps([[c["arm"], c["name"], c["instr"], c["field"], c["value"],
                        sorted(c["splices"].items()), list(c["vec"])] for c in cs],
                      sort_keys=True, default=str).encode()
    print("matrix sha256: %s" % hashlib.sha256(blob).hexdigest())
