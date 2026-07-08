#!/usr/bin/env python3
# run_gpr.py — Sub-task (2): find the CDM cfg-word (+0x00) bit23 flip vs GPR footprint.
# For each (N,H) ladder kernel: (a) measure GPR via shdump __GPU_METADATA field-0,
# (b) dispatch the SAME MSL via cvar --srcfile under iotrace, (c) read cfg +0x00 & bit23.
# CLEAN-ROOM: OWN-SHADER (our MSL, our metadata) + DATA-TRACE (our own cmdbuf bytes).
import os, sys, subprocess, importlib.util, glob, re
HERE=os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
spec=importlib.util.spec_from_file_location("gm","gprmeas.py"); gm=importlib.util.module_from_spec(spec); spec.loader.exec_module(gm)

def cfg_of(hexpath):
    data={}
    for line in open(hexpath):
        m=re.match(r'^([0-9a-f]{8}):\s+(.*)$',line)
        if not m: continue
        off=int(m.group(1),16); b=bytes.fromhex(m.group(2).replace(' ',''))
        for k,byte in enumerate(b): data[off+k]=byte
    return data.get(0,0)|(data.get(1,0)<<8)|(data.get(2,0)<<16)|(data.get(3,0)<<24)

def dispatch_cfg(metalpath,label):
    d=os.path.join("caps_gpr",label); os.makedirs(d,exist_ok=True)
    env=dict(os.environ, IOTRACE_MAX_MAP="0x800", IOTRACE_LOG="/dev/null",
             IOTRACE_DUMP_DIR=d, DYLD_INSERT_LIBRARIES="./iotrace.dylib")
    out=open(os.path.join("caps_gpr",label+".out"),"w")
    subprocess.run(["./cvar","--srcfile",metalpath,"--gx","32","--tgx","32","--dump"],
                   stdout=out,stderr=subprocess.STDOUT,env=env)
    out.close()
    fs=glob.glob(os.path.join(d,"bo_*va100000b0000_*.hex"))
    if not fs: return None
    return cfg_of(fs[0])

# ladder: (label, N, H). Prefer pure-float (H=0); half-fills for gaps; +controls.
LADDER=[
 ("g_N1H0",1,0),("g_N1H1",1,1),("g_N1H4",1,4),
 ("g_N2H0",2,0),("g_N1H3",1,3),      # ~GPR8 pure vs half control
 ("g_N3H0",3,0),
 ("g_N2H3",2,3),                     # GPR10 fill
 ("g_N4H0",4,0),("g_N2H4",2,4),      # ~GPR11 pure vs half control
 ("g_N5H0",5,0),("g_N4H3",4,3),      # ~GPR12
 ("g_N5H4",5,4),                     # GPR13 fill
 ("g_N7H0",7,0),("g_N4H5",4,5),      # ~GPR14 pure vs half control
 ("g_N8H0",8,0),("g_N7H2",7,2),      # ~GPR15
 ("g_N7H4",7,4),("g_N9H3",9,3),      # ~GPR16
 ("g_N10H0",10,0),("g_N6H3",6,3),    # ~GPR17
 ("g_N11H0",11,0),("g_N8H5",8,5),    # ~GPR18
 ("g_N13H0",13,0),("g_N16H0",16,0),  # higher, verify saturation
]
rows=[]
os.makedirs("caps_gpr",exist_ok=True)
for label,N,H in LADDER:
    mp=os.path.join("caps_gpr",label+".metal")
    open(mp,"w").write(gm.kernel_src(N,H))
    gpr=gm.measure(mp)
    cfg=dispatch_cfg(mp,label)
    bit23=(cfg>>23)&1 if cfg is not None else None
    rows.append((label,N,H,gpr,cfg,bit23))
    print(f"{label:<8} N={N:<3} H={H:<2} GPR={gpr:<4} cfg={cfg:#010x} bit23={bit23}")

print("\n=== sorted by measured GPR ===")
for label,N,H,gpr,cfg,bit23 in sorted(rows,key=lambda r:(r[3] if r[3] else -1)):
    print(f"GPR={gpr:<4} {label:<8}(N{N},H{H}) cfg={cfg:#010x} bit23={bit23}")
