#!/usr/bin/env python3
# EXP-0031 analyzer: from raw/extract.json, isolate the get_sr instruction(s) per
# built-in and tabulate SR number (byte1), dest (byte0 hi), form (byte0 lo), suffix.
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, "raw", "extract.json")))

def hx(s):
    return bytes.fromhex(s) if s else b""

def find_getsr(main):
    """Return list of (offset, 4 bytes) where a get_sr `Xc/X4 <sr> 10 06` appears.
    get_sr = byte0 low-nibble in {0xc,0x4}, byte1>=0x80 (SR), byte+2/+3 suffix."""
    b = hx(main)
    res = []
    i = 0
    while i + 4 <= len(b):
        b0 = b[i]
        lo = b0 & 0x0f
        if lo in (0x0c, 0x04) and (b[i+1] & 0x80) and b[i+2] in (0x10, 0x11, 0x09):
            res.append((i, b[i:i+4].hex()))
            i += 4
            continue
        i += 1
    return res

builtin_names = {
 "tpig_x":"thread_position_in_grid.x","tpig_y":"thread_position_in_grid.y","tpig_z":"thread_position_in_grid.z",
 "tpit_x":"thread_position_in_threadgroup.x","tpit_y":"thread_position_in_threadgroup.y","tpit_z":"thread_position_in_threadgroup.z",
 "tgpig_x":"threadgroup_position_in_grid.x","tgpig_y":"threadgroup_position_in_grid.y","tgpig_z":"threadgroup_position_in_grid.z",
 "tptg_x":"threads_per_threadgroup.x","tptg_y":"threads_per_threadgroup.y","tptg_z":"threads_per_threadgroup.z",
 "tgpg_x":"threadgroups_per_grid.x","tgpg_y":"threadgroups_per_grid.y","tgpg_z":"threadgroups_per_grid.z",
 "tidx_tg":"thread_index_in_threadgroup","lane":"thread_index_in_simdgroup(simd_lane_id)",
 "sgid":"simdgroup_index_in_threadgroup(simd_group_id)","simdw":"threads_per_simdgroup",
 "nsimd":"simdgroups_per_threadgroup","qlane":"thread_index_in_quadgroup","qgid":"quadgroup_index_in_threadgroup",
 "vid":"vertex_id","iid":"instance_id","bvtx":"base_vertex","binst":"base_instance","vid_iid":"vertex_id+instance_id",
 "pos":"position(FS)","sampid":"sample_id","facing":"front_facing","ptcoord":"point_coord","primid":"primitive_id","bary":"barycentric_coord",
}

print("=== COMPUTE get_sr table (const-addr isolation kernels) ===")
print(f"{'builtin':40s} {'SR(byte1)':9s} {'getsr-bytes':14s} {'form':5s} note")
for r in d:
    if r['kind']!='compute' or r['variant']!='const-addr': continue
    main = r.get('compute_main')
    gs = find_getsr(main) if main else []
    name = builtin_names.get(r['builtin'], r['builtin'])
    if gs:
        off,by = gs[0]
        b = bytes.fromhex(by)
        sr = b[1]; form = b[0]&0x0f; dst = b[0]>>4
        note = "" if len(gs)==1 else f"(+{len(gs)-1} more getsr)"
        print(f"{name:40s} 0x{sr:02x}      {by:14s} lo={form:x}  dst={dst} {note}")
    else:
        # constant-folded or computed
        print(f"{name:40s} {'--':9s} {'(no get_sr: folded/computed)':30s} main={main[:40]}")

print("\n=== VERTEX get_sr (main + cprog) ===")
for r in d:
    if r['kind']!='render' or r['variant'] not in ('vs','vs-baseline'): continue
    name = builtin_names.get(r['builtin'], r['builtin'])
    gm = find_getsr(r.get('vertex_main'))
    gc = find_getsr(r.get('vertex_cprog'))
    print(f"{name:25s} main_getsr={[g[1] for g in gm]}  cprog_getsr={[g[1] for g in gc]}")

print("\n=== FRAGMENT get_sr / leader (main) ===")
for r in d:
    if r['kind']!='render' or r['variant'] not in ('fs','fs-baseline'): continue
    name = builtin_names.get(r['builtin'], r['builtin'])
    main = r.get('fragment_main') or ""
    gm = find_getsr(main)
    leader = main[:8]
    print(f"{name:25s} leader={leader}  getsr={[g[1] for g in gm]}")
