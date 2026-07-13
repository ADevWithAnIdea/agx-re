#!/usr/bin/env python3
# EXP-M5-20 device-side batched splice sweep over MAC / tile-op byte positions.
# CLEAN-ROOM: our own MSL only; splice + observe numeric matrix output on real HW.
# Uses the persistent AGX runner so a big sweep is one process launch.
import sys, os, struct, argparse, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.expanduser("~/cleanroom_work/tools")
sys.path.insert(0, HERE)
from persistrun import PersistRunner

def load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
agxparse = load_mod("agxparse", os.path.join(TOOLS, "shdump", "agxparse.py"))

def ident(k):
    m=[0.0]*64
    for i in range(8): m[i*8+i]=float(k)
    return m
def writebuf(path, vals):
    with open(path,"wb") as f:
        for v in vals: f.write(struct.pack("<f", v))
def diag0(raw):
    if not raw or len(raw)<4: return None
    return struct.unpack_from("<f", raw, 0)[0]
def fullmat(raw):
    if not raw or len(raw)<256: return None
    return [struct.unpack_from("<f", raw, i*4)[0] for i in range(64)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--func", default="mad_f32")
    ap.add_argument("--src", default=os.path.join(HERE,"mac_probe.metal"))
    ap.add_argument("--bufs", default="0:2,1:3,2:5", help="idx:scale,idx:scale (scaled identities)")
    ap.add_argument("--out", type=int, default=3)
    ap.add_argument("--outn", type=int, default=256)
    ap.add_argument("--positions", required=True, help="csv of absolute byte offsets in _agc.main")
    ap.add_argument("--vals", default="coarse", help="'coarse'|'full'|csv-of-hex")
    ap.add_argument("--grid", type=int, default=32)
    ap.add_argument("--tg", type=int, default=32)
    ap.add_argument("--timeout", type=float, default=8.0)
    args = ap.parse_args()

    # compile base archive
    base = os.path.join(HERE, f"sweep_{args.func}.bin")
    import subprocess
    r = subprocess.run([os.path.join(TOOLS,"shdump","shdump"),"-o",base,"-f",args.func,args.src],
                       capture_output=True, text=True)
    if not os.path.exists(base):
        print("SHDUMP FAIL", r.stderr[-500:]); sys.exit(1)
    with open(base,"rb") as f: arch = f.read()
    loc = agxparse.locate_region(arch, "_agc.main")
    if loc is None: print("locate fail"); sys.exit(1)
    region_base, region_len = loc
    _, pieces = agxparse.extract_agx(arch)
    main_hex = pieces["_agc.main"].hex()
    print(f"MAIN_LEN {len(pieces['_agc.main'])} region_base={region_base}")

    # input buffers
    ins = {}
    for tok in args.bufs.split(","):
        idx, sc = tok.split(":")
        p = os.path.join(HERE, f"sw_in_{idx}.bin"); writebuf(p, ident(float(sc)))
        ins[int(idx)] = p

    if args.vals == "coarse":
        vals = [0x00,0x02,0x04,0x06,0x08,0x0a,0x0c,0x0e,0x10,0x18,0x20,0x30,0x40,
                0x50,0x60,0x70,0x80,0x90,0xa0,0xb0,0xc0,0xd0,0xe0,0xf0,0xff]
    elif args.vals == "full":
        vals = list(range(256))
    else:
        vals = [int(x,16) for x in args.vals.split(",")]
    positions = [int(x,0) for x in args.positions.split(",")]

    runner = PersistRunner(source=args.src, function=args.func, fast_math=True,
                           agxrun_persist=os.path.join(HERE,"agxrun_persist"))
    spliced = os.path.join(HERE, "sweep_spliced.bin")
    try:
        for off in positions:
            orig = arch[region_base+off]
            print(f"\n=== POS 0x{off:02x} (orig=0x{orig:02x}) ===")
            seen = {}
            for v in vals:
                b = bytearray(arch); b[region_base+off]=v
                with open(spliced,"wb") as f: f.write(bytes(b))
                resp = runner.request(archive=spliced, grid=args.grid, tg=args.tg,
                                      ins=ins, outs={args.out: args.outn}, timeout=args.timeout)
                d = diag0(resp["outs"].get(args.out)) if resp["status"]=="OK" else None
                key = f"{resp['status']}:{d}"
                seen.setdefault(key, []).append(v)
            for key, vlist in sorted(seen.items()):
                vs = ",".join(f"{x:02x}" for x in vlist)
                print(f"  diag0={key:20s} <- vals[{len(vlist)}]: {vs}")
    finally:
        runner.close()

if __name__ == "__main__":
    main()
