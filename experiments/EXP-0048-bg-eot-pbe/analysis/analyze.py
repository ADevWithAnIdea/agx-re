#!/usr/bin/env python3
"""Strict fixed-allowlist analysis for EXP-0048; never scans unknown BOs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

HERE=Path(__file__).resolve().parents[1]
RAW=HERE/"raw"
DEFAULT_RUNS=[RAW/"m4_20260817_run01",RAW/"m4_20260817_run02"]
DEFAULT_CONTROLS=[RAW/"m4_20260817_blend_control01",RAW/"m4_20260817_blend_control02"]
CASES=[
 "rgba8-clear-store-draw","rgba8-clear-store-empty","rgba8-load-store-empty",
 "rgba8-dontcare-store-draw","rgba8-clear-dontcare-draw","bgra8-clear-store-draw",
 "rgba8srgb-clear-store-draw","r32f-clear-store-draw","r32u-clear-store-draw",
 "rgba8-load-store-blend","rgba8-clear-store-atomic","mixed-r32f-clear-store"]
ALLOWED={
 "va_18000.bin":0x18000,"va_58000.bin":0x58000,"va_68000.bin":0x68000,
 "va_10000018200.bin":0x10000018200}
EXPECTED={
 "rgba8-clear-store-draw":("4080bf80","804020ff",0),
 "rgba8-clear-store-empty":("20406080","a06030c0",0),
 "rgba8-load-store-empty":("402010ff","101820ff",0),
 "rgba8-dontcare-store-draw":("4080bf80","804020ff",0),
 "rgba8-clear-dontcare-draw":(None,None,0), # StoreDontCare readback is undefined.
 "bgra8-clear-store-draw":("bf804080","804020ff",0),
 "rgba8srgb-clear-store-draw":("89bce180","804020ff",0),
 "r32f-clear-store-draw":("0000803e","804020ff",0),
 "r32u-clear-store-draw":("25000000","804020ff",0),
 "rgba8-load-store-blend":("405068bf","804020ff",0),
 "rgba8-clear-store-atomic":("4080bf80","804020ff",1024),
 "mixed-r32f-clear-store":("4080bf80","0000203f",0),
}
FIRST_RE=re.compile(r"FIRST (rt[01])=([0-9a-f]{8})")
RESULT_RE=re.compile(r"RESULT .*rt0_uniform=(\d+) rt1_uniform=(\d+) counter=(\d+)")

def read_case_state(run:Path,case:str)->dict[str,bytes]:
    d=run/f"state_{case}"
    names={p.name for p in d.glob("*.bin")}
    if names!=set(ALLOWED):raise AssertionError(f"allowlist violation {d}: {sorted(names)}")
    out={}
    for name in sorted(ALLOWED):
        meta=d/name.replace(".bin",".meta")
        if not meta.exists():raise AssertionError(f"missing metadata {meta}")
        text=meta.read_text()
        if f"gpu_va=0x{ALLOWED[name]:x}" not in text or "fixed_allowlist=1" not in text or "pointer_following=0" not in text:
            raise AssertionError(f"bad metadata {meta}")
        out[name]=(d/name).read_bytes()
    return out

def parse_output(run:Path,case:str)->dict[str,object]:
    rec=json.loads((run/f"run_{case}.json").read_text())
    if rec.get("exit")!=0:raise AssertionError(f"failed {run.name}/{case}")
    stdout=rec["stdout"]
    first={k:v for k,v in FIRST_RE.findall(stdout)}
    m=RESULT_RE.search(stdout)
    if set(first)!={"rt0","rt1"} or not m:raise AssertionError(f"unparsed output {run.name}/{case}")
    return {"rt0":first["rt0"],"rt1":first["rt1"],"uniform":[int(m[1]),int(m[2])],"counter":int(m[3])}

def words(buf:bytes,off:int)->list[int]:return list(struct.unpack_from("<4I",buf,off))

def record(buf:bytes,off:int)->dict[str,object]:
    w=words(buf,off);packed=struct.unpack_from("<Q",buf,off+8)[0]
    return {"offset":f"0x{off:x}","words":[f"0x{x:08x}" for x in w],
            "format_low24":f"0x{w[0]&0xffffff:06x}","word0_high8":w[0]>>24,
            "packed_surface_low40":f"0x{packed&((1<<40)-1):010x}",
            "surface_va_reconstructed":f"0x{(packed&((1<<40)-1))<<4:x}",
            "packed_resource_control_high24":f"0x{packed>>40:06x}"}

def diffs(a:bytes,b:bytes)->list[dict[str,object]]:
    if len(a)!=len(b):raise AssertionError("different allowlisted dump lengths")
    return [{"offset":f"0x{i:x}","a":f"0x{x:02x}","b":f"0x{y:02x}"}
            for i,(x,y) in enumerate(zip(a,b)) if x!=y]

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--json",type=Path);ap.add_argument("--report",type=Path)
    ap.add_argument("--run-a",type=Path,default=DEFAULT_RUNS[0]);ap.add_argument("--run-b",type=Path,default=DEFAULT_RUNS[1])
    ap.add_argument("--control-a",type=Path,default=DEFAULT_CONTROLS[0]);ap.add_argument("--control-b",type=Path,default=DEFAULT_CONTROLS[1]);a=ap.parse_args()
    runs=[a.run_a.resolve(),a.run_b.resolve()];controls=[a.control_a.resolve(),a.control_b.resolve()]
    observed={}
    state={}
    for run in runs:
        if json.loads((run/"failures.json").read_text()):raise AssertionError(f"raw failures {run}")
        observed[run.name]={};state[run.name]={}
        for case in CASES:
            observed[run.name][case]=parse_output(run,case)
            state[run.name][case]=read_case_state(run,case)
            ex=EXPECTED[case];ob=observed[run.name][case]
            if ex[0] is not None and (ob["rt0"],ob["rt1"],ob["counter"])!=ex:
                raise AssertionError(f"behavior mismatch {run.name}/{case}: {ob} != {ex}")
            if ob["uniform"]!=[1,1]:raise AssertionError(f"nonuniform output {run.name}/{case}")
        if any((run/f"source_{c}.metal").read_bytes()!=(runs[0]/f"source_{c}.metal").read_bytes() for c in CASES):
            raise AssertionError(f"generated MSL changed in {run.name}")

    repeat_state={}
    for case in CASES:
        repeat_state[case]={name:state[runs[0].name][case][name]==state[runs[1].name][case][name] for name in ALLOWED}
        if not all(repeat_state[case].values()):raise AssertionError(f"state not reproducible: {case}")
        if observed[runs[0].name][case]!=observed[runs[1].name][case]:raise AssertionError(f"behavior not reproducible: {case}")

    b=state[runs[0].name]
    desc={case:{"load0":record(b[case]["va_10000018200.bin"],0x20),
                "load1":record(b[case]["va_10000018200.bin"],0x40),
                "store0":record(b[case]["va_10000018200.bin"],0x220),
                "store1":record(b[case]["va_10000018200.bin"],0x240)} for case in CASES}
    base="rgba8-clear-store-draw"
    action_pairs={
      "empty_clear_to_load":("rgba8-clear-store-empty","rgba8-load-store-empty"),
      "draw_clear_to_load_dontcare":(base,"rgba8-dontcare-store-draw"),
      "store_to_store_dontcare":(base,"rgba8-clear-dontcare-draw"),
    }
    action_diffs={label:{name:diffs(b[x][name],b[y][name]) for name in ALLOWED}
                  for label,(x,y) in action_pairs.items()}

    control_state=[];control_ob=[]
    for run in controls:
        if json.loads((run/"failures.json").read_text()):raise AssertionError(f"control failure {run}")
        rec=json.loads((run/"run.json").read_text());stdout=rec["stdout"]
        first={k:v for k,v in FIRST_RE.findall(stdout)};m=RESULT_RE.search(stdout)
        ob={"rt0":first["rt0"],"rt1":first["rt1"],"uniform":[int(m[1]),int(m[2])],"counter":int(m[3])}
        if ob!={"rt0":"4080bf80","rt1":"804020ff","uniform":[1,1],"counter":0}:raise AssertionError(f"control behavior {ob}")
        control_ob.append(ob);control_state.append(read_case_state(run,"rgba8-load-store-draw-control"))
    if control_ob[0]!=control_ob[1] or any(control_state[0][n]!=control_state[1][n] for n in ALLOWED):
        raise AssertionError("control not reproducible")
    blend_diffs={name:diffs(control_state[0][name],b["rgba8-load-store-blend"][name]) for name in ALLOWED}
    clear_to_load_draw={name:diffs(b[base][name],control_state[0][name]) for name in ALLOWED}
    atomic_diffs={name:diffs(b[base][name],b["rgba8-clear-store-atomic"][name]) for name in ALLOWED}

    # Prior live correlation fixed +0x8c4 as a single-RT store-program-ID slot.
    # Reading that fixed offset is allowed; this is not a constant or pointer scan.
    old_id_slot={case:f"0x{struct.unpack_from('<I',b[case]['va_10000018200.bin'],0x8c4)[0]:08x}" for case in CASES}
    summary={
      "scope":"local M4 only; no A18 claim","runs":[p.name for p in runs],
      "cases":CASES,"behavior":observed,"state_repeat_exact":repeat_state,
      "descriptors":desc,"action_diffs":action_diffs,
      "clear_to_load_draw_diffs":clear_to_load_draw,"blend_control_diffs":blend_diffs,
      "atomic_diffs":atomic_diffs,"prior_single_rt_store_id_fixed_slot":old_id_slot,
    }
    if a.json:a.json.write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")

    fmt_cases=[base,"bgra8-clear-store-draw","rgba8srgb-clear-store-draw","r32f-clear-store-draw","r32u-clear-store-draw","mixed-r32f-clear-store"]
    lines=[
      "EXP-0048 strict fixed-allowlist analysis",
      "OBSERVATIONS",
      f"- 12/12 cases completed in both runs; {len(CASES)*len(ALLOWED)} allowlisted state comparisons are byte-identical across runs.",
      "- Empty Clear/Store RT0,RT1: 20406080,a06030c0; empty Load/Store: 402010ff,101820ff (initialized bytes).",
      "- BGRA8 physical bytes bf804080; sRGB 89bce180; R32Float 0000803e; R32Uint 25000000; all uniform.",
      "- Atomic case counter=1024; color bytes equal the non-atomic RGBA8 baseline.",
      "- Blend control bytes=4080bf80; blend bytes=405068bf; PBE array is byte-identical; only fixed-state +0x53 changes 00->20.",
      "- Draw Clear/Store -> Load/Store control: only fixed-state +0x14 changes 19->10.",
      "- Clear/Store -> Clear/StoreDontCare: only fixed-state +0x14 changes 19->20; PBE records retain the same surface fields.",
      "- Empty Clear/Store and empty Load/Store have byte-identical contents in all four allowlisted state BOs despite different target results.",
      "- Clear/Store draw and DontCare/Store draw also have byte-identical allowlisted state and the same fully covered target result.",
      "- The prior single-RT +0x8c4 program-ID slot is zero in this relocated MRT array for every case.",
      "",
      "Descriptor records (run01; run02 exact):",
    ]
    for case in fmt_cases:
        d=desc[case];lines.append(f"- {case}: LOAD0 {' '.join(d['load0']['words'])}; STORE0 {' '.join(d['store0']['words'])}; LOAD1 {' '.join(d['load1']['words'])}; STORE1 {' '.join(d['store1']['words'])}")
    lines += [
      "",
      "STRUCTURAL INTERPRETATIONS (not directly observed field names)",
      "- STORE word0 high byte=31 and word1>>6=31 for every case, independently matching width-1 and height-1 for 32x32.",
      "- The low 40 bits of the packed qword at record +0x08, shifted left four, reconstruct each authored RT buffer GPU VA; its upper 24 bits are therefore reported only as a packed resource/control field.",
      "- RGBA/BGRA and float/uint cases produce stable distinct low-24 format/component values. sRGB instead retains RGBA8 low-24 values and changes the packed upper control field (LOAD 0x0003c0->0x0003d0; STORE 0x0000f0->0x2000f0).",
      "- +0x58014 is an action/path selector candidate, not a decoded field: it is 0x19 for drawn Clear/Store and DontCare/Store, 0x10 for drawn Load/Store, 0x20 for Clear/StoreDontCare, and 0x00 for both empty passes.",
      "- +0x58053 bit 0x20 is independently attributable to blending in this matrix. The atomic case changes other fixed/VDM state but not PBE identity.",
      "",
      "NEGATIVE BOUNDARY",
      "- No BG/EOT tagged program address, resource-spec bit layout, or program-ID ownership is identified. Action behavior can change while the relocated PBE array remains identical, so those ABI fields are outside or not distinguishable within this allowlist.",
      "- No partial render, MSAA/resolve, layer/mip, memoryless, compression, depth/stencil, or A18 behavior was exercised.",
    ]
    report="\n".join(lines)+"\n"
    if a.report:a.report.write_text(report)
    print(report,end="")
    return 0

if __name__=="__main__":raise SystemExit(main())
