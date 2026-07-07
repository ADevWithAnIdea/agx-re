#!/usr/bin/env python3
# render_test.py -- falsify fragment iter (varying-slot byte+5, mode byte+6) and
# frag_color_store (src byte+3, rt_index byte+5) by splicing the FRAGMENT
# _agc.main and rendering via agxrender, reading back the pixel.
import sys, os, subprocess, re
SRC="kernels/render_vary.metal"
def locate_frag(a):
    o=subprocess.check_output(["python3","agxparse.py",a,"--stage","fragment","--locate","_agc.main"],text=True)
    return int(o.split()[0])
def agxrender(archive):
    out=subprocess.check_output(["./agxrender","--archive",archive,"--source",SRC,
        "--vertex","v_main","--fragment","f_main","--width","1","--height","1","--no-fast-math"],text=True)
    for ln in out.splitlines():
        if ln.startswith("PIXEL"):
            m=re.search(r"rgba_unorm=([\d.]+),([\d.]+),([\d.]+),([\d.]+)",ln)
            return tuple(float(x) for x in m.groups())
    return None
def main():
    arch="rv.bin"
    subprocess.check_call(["./shdump","-o",arch,"--render","--no-fast-math","--vertex","v_main","--fragment","f_main",SRC])
    foff=locate_frag(arch); base=bytearray(open(arch,"rb").read())
    print(f"# fragment _agc.main abs {foff}")
    print("baseline pixel rgba:", agxrender(arch))
    def splice(name, patches):
        buf=bytearray(base)
        for rel,val in patches: buf[foff+rel]=val
        open("rvspl.bin","wb").write(buf)
        try: px=agxrender("rvspl.bin")
        except subprocess.CalledProcessError as e: px=f"FAULT"
        print(f"  {name:48s} rgba={px}")
    # iter @ +0x14 has src_slot(byte+5)@+0x19, mode(byte+6)@+0x1a. It reads vc.x (slot 0x2).
    # vc = (0.20,0.40,0.60,0.80) -> slots 0x2/0x4/0x6/0x8.
    print("-- iter varying-slot (byte+5) of iter@+0x14 (baseline reads slot 0x2 = vc.x=0.20) --")
    splice("byte+5 0x02->0x04 (vc.y=0.40)", [(0x19,0x04)])
    splice("byte+5 0x02->0x06 (vc.z=0.60)", [(0x19,0x06)])
    splice("byte+5 0x02->0x08 (vc.w=0.80)", [(0x19,0x08)])
    print("-- iter mode (byte+6) of iter@+0x14 (baseline 0x00 linear/perspective) --")
    splice("byte+6 0x00->0x04 (W-denominator)", [(0x1a,0x04)])
    splice("byte+6 0x00->0x02 (centroid/sample)", [(0x1a,0x02)])
    # frag_color_store @ +0x7c: src(byte+3)@+0x7f, rt_index(byte+5)@+0x81
    print("-- frag_color_store src (byte+3) @ +0x7f --")
    splice("byte+3 src 0x00->0x02", [(0x7f,0x02)])
    splice("byte+3 src 0x00->0x06", [(0x7f,0x06)])
    print("-- frag_color_store rt_index (byte+5) @ +0x81 (single RT: expect no-op or drop) --")
    splice("byte+5 0x00->0x02 (RT1)", [(0x81,0x02)])
if __name__=="__main__": main()
