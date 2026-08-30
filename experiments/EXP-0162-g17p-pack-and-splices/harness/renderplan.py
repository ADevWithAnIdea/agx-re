#!/usr/bin/env python3
"""EXP-0162 FROZEN render case plan (G17P).

Arm D -- `pixel_order` (the DB self-contradiction EXP-0147 found and
`work/DB-DEFECT-TRIAGE.md` failed to fix from the corpus).
Arm E -- `vary_store` (the 0x57 fragment/vertex opcode collision, EXP-0091).

Every oracle is HOST-computed from the MSL we wrote. CLEAN-ROOM: OWN-SHADER.
"""
import struct

def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]

# ---------------------------------------------------------------- Arm D
# f_rog draws INSTANCES fragments over one texel under a texture-tagged
# raster_order_group. Each fragment does texel += src and returns texel + dst.
# With ordering intact:
#     tex   = N * src
#     pixel = clear + (1+2+...+N) * src
# A lost update moves BOTH, and the gap between them says how many were lost.
ROG_SRC   = [0.0625, 0.125, 0.25, 0.5]        # exact in f32
ROG_CLEAR = [0.125, 0.25, 0.375, 0.5]         # exact in f32
ROG_N     = 8

def rog_oracle(n=ROG_N):
    tri = n * (n + 1) // 2
    return {"tex":   [f32(n * s) for s in ROG_SRC],
            "pixel": [f32(c + tri * s) for c, s in zip(ROG_CLEAR, ROG_SRC)]}

def rog_oracle_lost(kept):
    """Prediction when only `kept` of the N updates survive: every fragment reads
    the same stale texel, so tex = kept*src and pixel = clear + N*kept*src."""
    return {"tex":   [f32(kept * s) for s in ROG_SRC],
            "pixel": [f32(c + ROG_N * kept * s) for c, s in zip(ROG_CLEAR, ROG_SRC)]}

# The two members, at the offsets the locate pilot found in f_rog's fragment main.
ROG_MEMBERS = {"acquire": {"off": 248, "bytes": "071454500600"},
               "release": {"off": 254, "bytes": "070454d00600"}}

# H4c / H4d cross-form probes: substitute a WHOLE six-byte encoding from the same
# 0x07 family and ask whether raster ordering survives.
#   tgbar_tex_*  : the threadgroup_barrier(mem_texture) acquire/release pair our
#                  own MSL compiles to (EXP-M4-13 R8 own-MSL byte-diff).
#   tgbar_compute: the corpus compute threadgroup barrier (28+ own-MSL firings).
#   tgbar_frag   : the corpus fragment tile-ordering barrier (81 firings).
#   mem_fence_dev: the standalone device fence.
CROSS_FORMS = {
  "tgbar_tex_acq":  "071454510e00",
  "tgbar_tex_rel":  "070454d10e00",
  "tgbar_compute":  "070454610900",
  "tgbar_frag":     "0702540c0200",
  "mem_fence_dev":  "070454840a00",
  "self_acq":       "071454500600",   # identity control
  "self_rel":       "070454d00600",   # identity control
  # byte+3 with bit0 SET, byte+4 left at 0x06 -- isolates the
  # execution-convergence bit from the memory-class byte
  "acq_b3_bit0":    "071454510600",
  "rel_b3_bit0":    "070454d10600",
  # byte+4 swapped to the texture memory class, byte+3 left alone
  "acq_b4_0e":      "071454500e00",
  "rel_b4_0e":      "070454d00e00",
}

# ---------------------------------------------------------------- Arm E
# f_kill: [[sample_mask]] = uint(want.x). mask bit0 set -> the fragment survives
# and writes its constant colour; mask 0 -> killed, the pixel keeps the clear.
KILL_COLOR = [0.75, 0.5, 0.25, 1.0]
KILL_CLEAR = [0.0, 0.0, 0.0, 0.0]
KILL_OFF   = 54
KILL_BYTES = "571454000001"
KILL_NEXT_OFF = 60          # `07 02 54 01 00 00`, the fragment epilog (EXP-0093)

# f_vary: va = (u.x + vid, u.y, u.z, u.w). y/z/w are CONSTANT across the three
# vertices, so their interpolated values are exact and host-known whatever the
# barycentrics are; x is geometry-dependent and is recorded, never oracled.
VARY_U = [0.0, 0.25, 0.5, 0.75]
VARY_ORACLE_GBA = [0.25, 0.5, 0.75]
VARY_CLEAR = [0.0, 0.0, 0.0, 0.0]

