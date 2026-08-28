#!/usr/bin/env python3
"""EXP-0092 shared case matrix: kernel metadata, FROZEN compiler-output
anchors, host-independent oracles, and the case generator for all four
sysval-ABI probes (GLIO-A02/A03/A05/A06). Single source of truth imported by
run.py, verify.py and analysis.py (the EXP-0073/0081/0086 lesson: one
definition, never restated).

Four independent backends, one unified gated record shape:
  srsweep       -- get_sr SR-SELECTOR (byte1) full legal-range sweep (0x00-0xFF),
                   via tools/agxtest/agxtest.py splice-and-observe on kernels/srprobe.metal.
                   GLIO-A02 (SR namespace) + GLIO-A06 (finite-resource row).
  dstsweep      -- get_sr DESTINATION-register-field boundary sweep, via a
                   register-address round trip (get_sr dst + device_store
                   index_reg spliced to the SAME candidate register) on
                   kernels/dstprobe.metal. GLIO-A02 (dest bits) + GLIO-A06.
  drawparam     -- vertex_id/instance_id/base_vertex/base_instance on a real
                   controlled indexed+instanced draw, via harness/agxvdraw (own
                   compile, no splice) on kernels/vdraw_probe.metal. GLIO-A03.
  numworkgroups -- threadgroups_per_grid (load_num_workgroups) under direct 3D
                   and indirect dispatch, via harness/agxcdispatch (own
                   compile, no splice) on kernels/numwg_probe.metal. GLIO-A05.

Splices for srsweep/dstsweep are built with tools/agx-isa's OWN assembler
(assemble(decode(bytes) + field override)) against a FROZEN pilot-compile hex
string pinned below (git rev / toolchain pinned in PRE_REGISTRATION.md /
CAPTURE_CONTRACT.json); baseline.py re-derives the SAME anchors from a fresh
compile at capture time and stops cleanly on any drift (frozen_anchor_diffs).

Later-read discipline (docs/isa/register-move-and-liveness.md, EXP-0086):
  srprobe   -- the spliced get_sr's result is read by a LATER, SEPARATE
               instruction (iadd2, "w = v + 1000"), which a THIRD, separate
               device_store then reads -- not adjacent same-instruction
               inspection.
  dstprobe  -- the spliced get_sr's result is read by device_store's OWN
               explicit index_reg field (address computation), a genuinely
               separate later instruction reading the GPR by number, not
               implicit forwarding.
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "tools" / "agx-isa"))
import isadb  # noqa: E402 (read-only use: decode_one / assemble)

# -----------------------------------------------------------------------------
# FROZEN pilot-compile _agc.main hex (this exact toolchain/git rev; see
# PRE_REGISTRATION.md). Anchors are decoded from these strings, never from a
# live compile, at import time.
# -----------------------------------------------------------------------------
SRPROBE_MAIN_HEX = "048210061ca010269f115400020010881701e7205400000121001100009011000e000000"
DSTPROBE_MAIN_HEX = "1ca010060c01e7105400000121001100009011000e000000"

KERNELS = ("srprobe", "dstprobe", "vdraw_probe", "numwg_probe")


def _decode_stream(hexstr):
    data = bytes.fromhex(hexstr)
    out = []
    off = 0
    while off < len(data):
        rec, length = isadb.decode_one(data, off)
        assert isadb.assemble(rec["mnemonic"], rec["fields"]) == data[off:off + length], \
            "round-trip failed at offset %d" % off
        out.append({"offset": off, "length": length, **rec})
        off += length
    return out


_SRPROBE_STREAM = _decode_stream(SRPROBE_MAIN_HEX)
_DSTPROBE_STREAM = _decode_stream(DSTPROBE_MAIN_HEX)

# srprobe anchor: the FIRST get_sr (v = thread_index_in_simdgroup, sr_sel 0x82)
SRPROBE_V_ANCHOR = _SRPROBE_STREAM[0]
assert SRPROBE_V_ANCHOR["mnemonic"] == "get_sr" and SRPROBE_V_ANCHOR["fields"]["sr_sel"] == 0x82
# srprobe anchor: the second get_sr (gid = thread_position_in_grid.x, sr_sel 0xa0) -- untouched
SRPROBE_GID_ANCHOR = _SRPROBE_STREAM[1]
assert SRPROBE_GID_ANCHOR["mnemonic"] == "get_sr" and SRPROBE_GID_ANCHOR["fields"]["sr_sel"] == 0xa0
SRPROBE_ADD_ANCHOR = _SRPROBE_STREAM[2]
assert SRPROBE_ADD_ANCHOR["mnemonic"] == "iadd2"
SRPROBE_STORE_ANCHOR = _SRPROBE_STREAM[3]
assert SRPROBE_STORE_ANCHOR["mnemonic"] == "device_store"

# dstprobe anchors: get_sr (v = thread_position_in_grid.x, sr_sel 0xa0), then
# mov_imm (dst=0, imm=1, UNTOUCHED -- this is the R==0 collision source), then
# device_store whose index_reg the natural compile sets equal to get_sr's dst.
DSTPROBE_GETSR_ANCHOR = _DSTPROBE_STREAM[0]
assert DSTPROBE_GETSR_ANCHOR["mnemonic"] == "get_sr" and DSTPROBE_GETSR_ANCHOR["fields"]["sr_sel"] == 0xa0
DSTPROBE_MOVIMM_ANCHOR = _DSTPROBE_STREAM[1]
assert DSTPROBE_MOVIMM_ANCHOR["mnemonic"] == "mov_imm" and DSTPROBE_MOVIMM_ANCHOR["fields"]["dst"] == 0
DSTPROBE_STORE_ANCHOR = _DSTPROBE_STREAM[2]
assert DSTPROBE_STORE_ANCHOR["mnemonic"] == "device_store"
assert DSTPROBE_STORE_ANCHOR["fields"]["index_reg"] == DSTPROBE_GETSR_ANCHOR["fields"]["dst"], \
    "natural compile invariant: device_store.index_reg == get_sr.dst"


def _splice_bytes(anchor, field_overrides):
    """(anchor, {field: value}) -> list of (abs_offset, new_byte) for every
    byte that actually changed, by decode+override+assemble+diff against the
    FROZEN anchor hex (never a live re-decode)."""
    base = bytes.fromhex(anchor["hex"])
    flds = dict(anchor["fields"])
    flds.update(field_overrides)
    new = isadb.assemble(anchor["mnemonic"], flds)
    assert len(new) == len(base)
    out = []
    for i in range(len(base)):
        if new[i] != base[i]:
            out.append((anchor["offset"] + i, new[i]))
    return out


def splice_args_from_bytes(changes):
    return ["_agc.main@%d=%02x" % (off, val) for off, val in changes]


# -----------------------------------------------------------------------------
# srsweep: known, independently-computed expected patterns for grid=64,tg=64
# (single threadgroup, threadExecutionWidth=32 on Apple9/M4 -- shdump reports
# this at pilot-compile time; frozen here, re-confirmed by baseline.py).
# -----------------------------------------------------------------------------
SRSWEEP_N = 64
SRSWEEP_SIMD_WIDTH = 32
SRSWEEP_OFFSET = 1000


def _known_sr_pattern(sr):
    t = list(range(SRSWEEP_N))
    if sr == 0xa0: return list(t)                                    # thread_position_in_grid.x
    if sr == 0xa1: return [0] * SRSWEEP_N                             # .y
    if sr == 0xa2: return [0] * SRSWEEP_N                             # .z
    if sr == 0xa4: return list(t)                                     # thread_position_in_threadgroup.x
    if sr == 0xa5: return [0] * SRSWEEP_N
    if sr == 0xa6: return [0] * SRSWEEP_N
    if sr == 0xa7: return list(t)                                     # thread_index_in_threadgroup
    if sr == 0x9c: return [0] * SRSWEEP_N                             # threadgroup_position_in_grid.x
    if sr == 0x9d: return [0] * SRSWEEP_N
    if sr == 0x9e: return [0] * SRSWEEP_N
    if sr == 0x98: return [SRSWEEP_N] * SRSWEEP_N                     # threads_per_threadgroup.x
    if sr == 0x99: return [1] * SRSWEEP_N
    if sr == 0x9a: return [1] * SRSWEEP_N
    if sr == 0x82: return [x % SRSWEEP_SIMD_WIDTH for x in t]         # simd_lane_id
    if sr == 0x85: return [x // SRSWEEP_SIMD_WIDTH for x in t]        # simd_group_id
    # RT-7 nuance (A18; re-tested here on M4): bare get_sr(0xa8) tracks
    # threads_per_threadgroup.x, NOT threadgroups_per_grid.x.
    if sr == 0xa8: return [SRSWEEP_N] * SRSWEEP_N
    return None


KNOWN_SR = {sr: _known_sr_pattern(sr) for sr in range(256) if _known_sr_pattern(sr) is not None}


def srsweep_expected(sr):
    pat = KNOWN_SR.get(sr)
    if pat is None:
        return None
    return [v + SRSWEEP_OFFSET for v in pat]


def make_srsweep_cases():
    cases = []
    for sr in range(256):
        changes = _splice_bytes(SRPROBE_V_ANCHOR, {"sr_sel": sr})
        cases.append({
            "backend": "srsweep", "kernel": "srprobe", "name": "sr_%02x" % sr,
            "item": "SRSWEEP", "params": {"sr_sel": sr},
            "splice_changes": changes,
            "expected": srsweep_expected(sr),
            "note": "sr_sel=0x%02x%s" % (sr, " (known)" if sr in KNOWN_SR else ""),
        })
    return cases


# -----------------------------------------------------------------------------
# dstsweep: register-address round trip boundary set.
# -----------------------------------------------------------------------------
DSTSWEEP_OUT_N = 256
DSTSWEEP_REGISTERS = (0, 1, 15, 16, 31, 32, 47, 48, 63, 64, 79, 80, 87, 88, 94, 95,
                      96, 97, 100, 111, 112, 120, 127)


def dstsweep_expected(reg):
    out = [0] * DSTSWEEP_OUT_N
    # R==0 collides with the fixed mov_imm dst=0 (see module docstring): the
    # get_sr write at r0 is overwritten by mov_imm's r0=1 before the store
    # reads index_reg=0, so the recorded sentinel lands at out[1], not out[0].
    idx = 1 if reg == 0 else 0
    out[idx] = 1
    return out


def make_dstsweep_cases():
    cases = []
    for reg in DSTSWEEP_REGISTERS:
        getsr_changes = _splice_bytes(DSTPROBE_GETSR_ANCHOR,
                                      {"dst": reg & 0xF, "dst_hi": (reg >> 4) & 0x7})
        store_changes = _splice_bytes(DSTPROBE_STORE_ANCHOR, {"index_reg": reg})
        cases.append({
            "backend": "dstsweep", "kernel": "dstprobe", "name": "reg_%03d" % reg,
            "item": "DSTSWEEP", "params": {"reg": reg},
            "splice_changes": getsr_changes + store_changes,
            "expected": dstsweep_expected(reg),
            "note": "dst register candidate %d (get_sr dst+dst_hi and device_store "
                    "index_reg both spliced to %d)" % (reg, reg),
        })
    return cases


# -----------------------------------------------------------------------------
# drawparam: GLIO-A03. Host-independent oracle mirrors the documented Metal
# vertex-stage builtin contract (public API behavior, not GPU-inferred): for
# an indexed draw, vertex_id = index_buffer[slot] + baseVertex (mod 2**32);
# instance_id = instance_ordinal + baseInstance (mod 2**32); base_vertex ==
# baseVertex; base_instance == baseInstance exactly.
# -----------------------------------------------------------------------------
U32 = 0xFFFFFFFF


def _u32(x):
    return x & U32


def drawparam_expected(indices, instance_count, base_vertex, base_instance):
    recs = []
    for iid_ord in range(instance_count):
        for raw_idx in indices:
            vid = _u32(raw_idx + base_vertex)
            iid = _u32(iid_ord + base_instance)
            recs.append((vid, iid, _u32(base_vertex), _u32(base_instance)))
    return sorted(recs)


DRAWPARAM_CASES = [
    {"name": "baseline_zero", "indices": [0, 1, 2], "instance_count": 1,
     "base_vertex": 0, "base_instance": 0, "primitive": "point"},
    {"name": "nonzero_base", "indices": [7, 3, 9], "instance_count": 2,
     "base_vertex": 100, "base_instance": 50, "primitive": "point"},
    {"name": "large_base", "indices": [0, 1, 2, 3], "instance_count": 1,
     "base_vertex": 1000000, "base_instance": 500000, "primitive": "point"},
    {"name": "negative_base_vertex", "indices": [10, 20, 0], "instance_count": 1,
     "base_vertex": -5, "base_instance": 0, "primitive": "point"},
    {"name": "negative_base_vertex_underflow", "indices": [0], "instance_count": 1,
     "base_vertex": -1, "base_instance": 0, "primitive": "point"},
    {"name": "repeated_index", "indices": [0, 0, 0], "instance_count": 1,
     "base_vertex": 42, "base_instance": 0, "primitive": "point"},
    {"name": "max_base_instance", "indices": [0], "instance_count": 1,
     "base_vertex": 0, "base_instance": 4294967295, "primitive": "point"},
    {"name": "instance_wrap", "indices": [0], "instance_count": 2,
     "base_vertex": 0, "base_instance": 4294967295, "primitive": "point"},
    {"name": "base_vertex_int32_max", "indices": [0], "instance_count": 1,
     "base_vertex": 2147483647, "base_instance": 0, "primitive": "point"},
]


def make_drawparam_cases():
    cases = []
    for c in DRAWPARAM_CASES:
        exp = drawparam_expected(c["indices"], c["instance_count"], c["base_vertex"],
                                 c["base_instance"])
        cases.append({
            "backend": "drawparam", "kernel": "vdraw_probe", "name": c["name"],
            "item": "DRAWPARAM",
            "params": {"indices": c["indices"], "instance_count": c["instance_count"],
                      "base_vertex": c["base_vertex"], "base_instance": c["base_instance"],
                      "primitive": c["primitive"]},
            "splice_changes": [],
            "expected": exp,
            "note": c["name"],
        })
    return cases


# -----------------------------------------------------------------------------
# numworkgroups: GLIO-A05. direct mode expected == the requested threadgroup
# COUNT exactly (the API contract under test); indirect mode expected == the
# raw record fields, EXCEPT the all-zero record, where zero threadgroups are
# dispatched and NO invocation runs -- there is no independent confirmation
# available of what threadgroups_per_grid would read, so expected is None
# (status-only verdict) for that one case.
# -----------------------------------------------------------------------------
NUMWG_CASES = [
    {"name": "direct_1x1x1", "mode": "direct", "tg": (1, 1, 1), "local": (1, 1, 1)},
    {"name": "direct_asym_5x3x2", "mode": "direct", "tg": (5, 3, 2), "local": (4, 4, 1)},
    {"name": "direct_npot_7x11x13", "mode": "direct", "tg": (7, 11, 13), "local": (2, 2, 2)},
    {"name": "direct_large_x", "mode": "direct", "tg": (1024, 1, 1), "local": (1, 1, 1)},
    {"name": "direct_local_npot", "mode": "direct", "tg": (4, 2, 1), "local": (3, 5, 1)},
    {"name": "direct_64x64", "mode": "direct", "tg": (64, 64, 1), "local": (1, 1, 1)},
    {"name": "indirect_7x1x1", "mode": "indirect", "ind": (7, 1, 1), "local": (4, 1, 1)},
    {"name": "indirect_asym_5x3x2", "mode": "indirect", "ind": (5, 3, 2), "local": (4, 4, 1)},
    {"name": "indirect_zero_x", "mode": "indirect", "ind": (0, 1, 1), "local": (4, 1, 1)},
    {"name": "indirect_all_zero", "mode": "indirect", "ind": (0, 0, 0), "local": (4, 1, 1)},
    {"name": "indirect_huge_x", "mode": "indirect", "ind": (4294967295, 1, 1), "local": (1, 1, 1)},
    {"name": "indirect_large_product", "mode": "indirect", "ind": (65535, 65535, 1), "local": (1, 1, 1)},
]


def make_numworkgroups_cases():
    cases = []
    for c in NUMWG_CASES:
        if c["mode"] == "direct":
            params = {"mode": "direct", "tg": list(c["tg"]), "local": list(c["local"])}
            expected = list(c["tg"])
        else:
            params = {"mode": "indirect", "ind": list(c["ind"]), "local": list(c["local"])}
            expected = None if c["ind"] == (0, 0, 0) else list(c["ind"])
        cases.append({
            "backend": "numworkgroups", "kernel": "numwg_probe", "name": c["name"],
            "item": "NUMWORKGROUPS", "params": params, "splice_changes": [],
            "expected": expected, "note": c["name"],
        })
    return cases


REPEAT_N = 1


def full_case_list():
    """Every case in the frozen capture order: srsweep, dstsweep, drawparam,
    numworkgroups. Deterministic order; `i` is the absolute index."""
    out = []
    i = 0
    for gen in (make_srsweep_cases, make_dstsweep_cases, make_drawparam_cases,
               make_numworkgroups_cases):
        for case in gen():
            for rep in range(REPEAT_N):
                out.append({"i": i, "rep": rep, **case})
                i += 1
    return out


if __name__ == "__main__":
    cases = full_case_list()
    print("total cases:", len(cases))
    from collections import Counter
    print(Counter(c["backend"] for c in cases))
