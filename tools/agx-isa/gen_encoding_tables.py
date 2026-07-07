#!/usr/bin/env python3
# gen_encoding_tables.py -- render the machine-readable ISA DB (db.json) into the
# human-readable authoritative encoding tables at docs/isa/encoding-tables.md.
#
# This makes the encoding table live in docs/ (not just tools/): a driver author
# reads this to emit A18 Pro / G17P AGX instructions. It is generated-but-committed
# -- regenerate with `python3 gen_encoding_tables.py` after any db.json change.
#
# CLEAN-ROOM: pure rendering of our own OWN-SHADER-derived DB. No Apple binary.
import json, os, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DB_JSON = os.path.join(HERE, "db.json")
OUT = os.path.normpath(os.path.join(HERE, "..", "..", "docs", "isa", "encoding-tables.md"))

# mnemonic -> (family, one-line role). Order of FAMILIES controls document order.
FAMILY = [
    ("Float ALU", [
        ("falu2", "2-source float ALU (fadd/fmul), reg-reg"),
        ("falu2i", "2-source float ALU, srcB packed minifloat immediate"),
        ("falu2_uni", "2-source float ALU, srcB UNIFORM-register source (a + uniform)"),
        ("falu3", "3-source float ALU (fma)"),
        ("fminmax", "float min/max"),
        ("funary", "float source-modifier move (fmov/fabs/fneg)"),
        ("half_alu", "native fp16 (half) ALU (hadd/hmul); half2 packs 2 lanes"),
        ("falu_acc", "compact 4-byte float accumulate (reduction)"),
        ("cvt_f2h", "fp32 -> fp16 narrowing convert"),
        ("bf_alu", "native bfloat (brain-float16) general ALU (add/mul/fma)"),
        ("fspecial", "special-function unit: rcp/rsqrt/exp2/round/sqrt/log2"),
        ("fspecial_est", "transcendental estimate seed (rcp/rsqrt/sqrt NR seed)"),
    ]),
    ("Integer ALU", [
        ("iadd2", "integer 2-source add/sub"),
        ("imad", "integer multiply-add (imul = c=0)"),
        ("iminmax", "integer min/max (signed/unsigned)"),
        ("iminmax_chain", "chained min/max (min3/max3/clamp first op)"),
        ("iunary", "integer unary (popcount / reduce)"),
        ("ibitcount", "bit-count / bit-scan (popcount/reverse_bits/find-MSB)"),
        ("carry_gen", "u64 carry-generate (unsigned-overflow compare for 64-bit add)"),
        ("irotate", "rotate-by-immediate funnel shift"),
        ("ishift", "arithmetic shift-right immediate"),
        ("ibfe", "bitfield-extract / logical shift-right"),
        ("icmpsel", "compare -> select 0/1 (full condition codes)"),
    ]),
    ("Conversions / pack", [
        ("cvt_f2i", "float/half -> int/uint convert (round to zero)"),
        ("cvt_i2f", "int/uint -> float/half convert"),
        ("mov_zext16", "16-bit zero-extend / narrow move"),
        ("pack_convert", "pack_float_to_unorm/snorm2x16 (compute)"),
        ("unpack_convert", "unpack_unorm/snorm2x16_to_float (compute)"),
        ("half_pack", "assemble a half2's two fp16 lanes into a packed 32-bit register"),
    ]),
    ("Bitwise / logic", [
        ("ilogic", "2-input bitwise LUT (all 16 boolean functions)"),
    ]),
    ("Move / special register", [
        ("get_sr", "read a special register (thread/threadgroup/simd IDs, dims, VS/FS)"),
        ("mov_imm", "2-byte small-immediate move (constant-folded builtins)"),
        ("uniform_mov", "copy a uniform register into a GPR"),
        ("stop", "conventional program-end word"),
    ]),
    ("Memory access", [
        ("device_load", "load (device / threadgroup / constant)"),
        ("device_store", "store (device / threadgroup)"),
        ("vary_store", "vertex varying / [[position]] store to the UVS/parameter buffer"),
    ]),
    ("Atomics", [
        ("atomic_rmw", "device atomic RMW (elected-lane, op at byte+12)"),
        ("atomic_mem", "standalone atomic (exchange/cmpxchg/indexed)"),
    ]),
    ("Texture / sampler", [
        ("tex_sample", "sample/gather/read/compare/LOD-query bundle"),
        ("tex_write", "texture write (memory-family store)"),
        ("tex_deriv", "quad-difference derivative (dfdx/dfdy/fwidth)"),
        ("tex_coord_setup", "texture coordinate / LOD / gather-offset setup ALU"),
        ("coord_madf", "coordinate / interpolation fused mul-add (leader form)"),
    ]),
    ("Control flow / function ABI", [
        ("icmp_pred", "integer compare -> execution predicate"),
        ("sel", "conditional select (data operands)"),
        ("psel", "conditional select (grid/immediate variant)"),
        ("jump", "PC-relative jump (loop back-edge)"),
        ("frame_marker", "call-site / frame-setup marker (before every CALL)"),
        ("call", "direct out-of-line CALL"),
        ("ret", "function RETURN (leaf / non-leaf)"),
        ("call_indirect", "indirect CALL (visible_function_table)"),
        ("frame_prologue", "non-leaf function frame prologue (scratch frame setup)"),
        ("link_save_restore", "link-register save/restore around a nested call"),
        ("spill_frame_marker", "spill/frame-setup marker (after entry get_sr in spilling kernels)"),
    ]),
    ("SIMD-group / quad", [
        ("simd_reduce", "SIMD/quad reduce & prefix-scan"),
        ("simd_shuffle", "SIMD/quad shuffle / broadcast"),
        ("simd_ballot", "SIMD ballot / vote mask source"),
    ]),
    ("Matrix", [
        ("matrix_mac", "8x8 cooperative-matrix multiply-accumulate"),
    ]),
    ("Ray tracing", [
        ("rt_intersect", "dedicated ray-intersection primitive (motion + AS-select)"),
        ("rt_as_load", "acceleration-structure / ray-data load"),
        ("rt_ray_mem", "ray-data / traversal-stack memory op (payload copy-in/out)"),
        ("rt_transform_test", "ray-vs-node transform / AABB box-test companion"),
        ("ray_move", "ray register-marshalling move (also MPP matmul transpose)"),
    ]),
    ("Barrier / ordering", [
        ("threadgroup_barrier", "threadgroup execution barrier + memory fence"),
        ("mem_fence", "device memory fence (atomic_thread_fence, no execution barrier)"),
        ("pixel_order", "raster-order-group wait/signal (fragment)"),
    ]),
    ("Fragment stage", [
        ("iter", "varying interpolation (perspective/linear/W)"),
        ("iter_at", "interpolate-at setup (centroid / sample)"),
        ("iter_flat", "flat varying load (provoking-vertex attribute)"),
        ("frag_color_store", "colour output store to tilebuffer"),
        ("frag_color_pack", "pack/move colour into output GPR"),
        ("frag_tile_setup", "tile / render-target access setup"),
        ("tile_read", "tilebuffer read (programmable blend input)"),
        ("imageblock_store", "explicit imageblock<T>.write (tile shader; byte-offset slice addressing)"),
        ("imageblock_load", "explicit imageblock<T>.read (tile shader; byte-offset slice addressing)"),
        ("frag_depth_store", "[[depth]] output store"),
    ]),
]

TYPE_NOTE = {
    "reg": "register", "imm": "immediate", "enum": "enum", "mod": "modifier",
    "opcode": "opcode-select", "raw": "raw/unmapped",
}

def bits_str(start, width):
    return f"[{start}:{start+width}]" + (f" (byte+{start//8}" + (f" bit{start%8}" if start % 8 else "") + ")"
                                          if width <= 8 and start % 8 == 0 else "")

def render_match(match):
    parts = []
    for (s, w, v) in match:
        if w == 8 and s % 8 == 0:
            parts.append(f"byte+{s//8}==0x{v:02x}")
        else:
            parts.append(f"bits[{s}:{s+w}]==0x{v:x}")
    return ", ".join(parts) if parts else "(none)"

def enum_str(enum):
    if not enum:
        return ""
    items = []
    for k, val in enum.items():
        ki = int(k) if isinstance(k, str) else k
        items.append(f"`{ki:#x}`={val}")
    return "; ".join(items)

def main():
    db = json.load(open(DB_JSON))
    by_mnem = {d["mnemonic"]: d for d in db["instructions"]}
    placed = set()

    L = []
    def w(s=""):
        L.append(s)

    total = len(db["instructions"])
    w("# A18 Pro (G17P) AGX — Instruction Encoding Tables")
    w()
    w(f"> **Generated** from `tools/agx-isa/db.json` by `tools/agx-isa/gen_encoding_tables.py` "
      f"({datetime.date.today().isoformat()}). Regenerate after any DB change; do not hand-edit. "
      f"This is the **authoritative, self-contained encoding table** a driver author reads to emit "
      f"A18 Pro AGX instructions — {total} instruction descriptors.")
    w()
    w("**Clean-room:** every encoding here was learned from the compiled form of MSL **we wrote** "
      "(OWN-SHADER) — by byte-diffing our own shaders and by splicing bytes and running them on the "
      "real A18 Pro GPU (hardware validation). No Apple binary was disassembled. See `../../CLAUDE.md`.")
    w()
    w("## How to read this")
    w()
    w("- Bit numbering: an *N*-byte instruction is one **little-endian** integer. Bit 0 = bit 0 of "
      "byte 0; bit 16 = bit 0 of byte +2; so *byte offset +k, bit b* = bit (8·k + b).")
    w("- **Length** is a function of byte 0 (the group) plus a per-group length bit/signature — the "
      "first parcel does *not* encode length on G17P. The full length rule is the byte-0 table in "
      "the [Length rule](#length-rule-byte-0) appendix and `tools/agx-isa/isadb.py::instr_length`.")
    w("- **Match** = the constant bits that identify the instruction. **Fields** = every non-constant "
      "bit, with its bit-range, type, and enum values where known.")
    w("- Field **type**: `register` · `immediate` · `enum` · `modifier` · `opcode-select` · "
      "`raw/unmapped` (byte-diff-localized but not individually bit-decoded).")
    w()
    # table of contents
    w("## Contents")
    w()
    for fam, _ in FAMILY:
        anchor = fam.lower().replace(" / ", "--").replace(" ", "-")
        w(f"- [{fam}](#{anchor})")
    w("- [Length rule (byte 0)](#length-rule-byte-0)")
    w()

    for fam, entries in FAMILY:
        anchor = fam.lower().replace(" / ", "--").replace(" ", "-")
        w(f"## {fam}")
        w()
        for mnem, role in entries:
            d = by_mnem.get(mnem)
            if d is None:
                continue
            placed.add(mnem)
            prov = d.get("provenance", "")
            tag = "HW-validated" if prov.startswith("HW-VALIDATED") or "HW-VALIDATED" in prov[:20] else \
                  ("inferred" if prov.startswith("inferred") else "mixed")
            w(f"### `{mnem}` — {role}")
            w()
            w(f"- **Length:** {d['length']} bytes  ·  **Match:** {render_match(d['match'])}  ·  "
              f"**Provenance:** {tag}")
            w()
            w("| Field | Bits | Type | Enum / values |")
            w("|---|---|---|---|")
            for f in d["fields"]:
                bits = f"[{f['start']}:{f['start']+f['width']}]"
                if f['start'] % 8 == 0 and f['width'] in (8, 16, 24, 32, 48, 56, 40, 88):
                    bits += f" (byte+{f['start']//8})"
                elif f['start'] % 8 == 0:
                    bits += f" (byte+{f['start']//8})"
                t = TYPE_NOTE.get(f['type'], f['type'])
                es = enum_str(f.get("enum"))
                w(f"| `{f['name']}` | {bits} | {t} | {es} |")
            w()
            sem = d.get("semantics", "").strip()
            if sem:
                w(f"*{sem}*")
                w()

    # any descriptors not placed in a family -> a catch-all
    leftover = [d for d in db["instructions"] if d["mnemonic"] not in placed]
    if leftover:
        w("## Other")
        w()
        for d in leftover:
            w(f"### `{d['mnemonic']}`")
            w()
            w(f"- **Length:** {d['length']} bytes  ·  **Match:** {render_match(d['match'])}")
            w()

    # length-rule appendix
    w("## Length rule (byte 0)")
    w()
    w("Parcels are 2 bytes (all lengths even). Length is a function of byte 0 plus a per-group "
      "length bit/signature. The authoritative rule is `instr_length()` in "
      "`tools/agx-isa/isadb.py`; this table summarizes it:")
    w()
    w("| byte 0 (group / signature) | length (bytes) |")
    w("|---|---|")
    for k, v in db["length_rule"]["byte0_table"].items():
        vv = str(v).replace("|", "\\|").replace("\n", " ")
        w(f"| `{k}` | {vv} |")
    w()
    w("---")
    w()
    w(f"*Rendered from `tools/agx-isa/db.json` — {total} descriptors. The machine-readable source of "
      f"truth is `db.json` / `isadb.py`; this document is its human-readable projection.*")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"wrote {OUT}  ({total} descriptors, {len(placed)} tabulated, {len(leftover)} in Other)")

if __name__ == "__main__":
    main()
