#!/usr/bin/env python3
# census.py -- tokenize a shader's _agc.main with the DB and report coverage,
# undecoded leaders, and any resync gaps. Catches DB mis-decodes at scale.
import sys, os, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import isadb

def get_hex(archive, stage):
    o=subprocess.check_output(["python3","agxparse.py",archive,"--stage",stage,"--extract-hex"],text=True)
    return o.strip().split()[-1]

def census(buf, label):
    print(f"\n=== {label}: {len(buf)} bytes ===")
    off=0; decoded=0; named=0; total=len(buf); unknown_leaders={}
    n=0
    while off < len(buf):
        try:
            rec,length = isadb.decode_one(buf, off)
            decoded += length
            if rec.get("mnemonic") and not rec.get("error"): named += length
            off += length; n+=1
        except Exception as e:
            b0 = buf[off]
            unknown_leaders[b0] = unknown_leaders.get(b0,0)+1
            # resync: skip 2 bytes (parcel) and continue
            off += 2
    print(f"  decoded {decoded}/{total} = {100*decoded/total:.1f}% over {n} instrs")
    if unknown_leaders:
        print("  UNDECODED byte0 leaders (count):", {f'0x{k:02x}':v for k,v in sorted(unknown_leaders.items())})
    else:
        print("  CLEAN: 0 undecoded")
    return decoded,total,unknown_leaders

def main():
    jobs = [
        ("big_compute.metal","compute","bc.bin",False),
        ("big_frag.metal","fragment","bf.bin",True),
    ]
    for src,stage,arch,render in jobs:
        if render:
            subprocess.check_call(["./shdump","-o",arch,"--render","--no-fast-math","--vertex","v_main","--fragment","f_main","kernels/"+src])
        else:
            subprocess.check_call(["./shdump","-o",arch,"--no-fast-math","-f","k","kernels/"+src])
        for st in ([ "vertex","fragment"] if render else ["compute"]):
            try:
                h=get_hex(arch,st); census(bytes.fromhex(h), f"{src}:{st}")
            except Exception as e:
                print(f"  {src}:{st} extract failed: {e}")

if __name__=="__main__": main()
