#!/usr/bin/env python3
# Dump the __descriptor / __reflection / __compute-header bytes from the AppleGPU
# image of each pressure archive, so we can find the register-count metadata field.
# CLEAN-ROOM: OWN-SHADER -- our own compiled archive's own metadata bytes.
import os, sys, subprocess, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("agxparse", os.path.join(HERE, "agxparse.py"))
ap = importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)

def gpu_image(buf):
    for (off, size, note) in ap.iter_gpu_images(buf):
        try: mo = ap.MachO(buf, off)
        except ValueError: continue
        if mo.cputype == ap.APPLE_GPU_CPUTYPE:
            return mo
    return None

def sect_hex(buf, mo, seg, name):
    s = mo.find_section(seg, name)
    if not s: return None
    off = mo.base + s["offset"]
    return buf[off:off+s["size"]].hex()

def compile_K(K):
    kp = os.path.join(HERE, "kernels", "pf%d.metal" % K)
    arch = os.path.join(HERE, "sK_%d.bin" % K)
    subprocess.run([os.path.join(HERE,"shdump"),"-o",arch,"-f","k","--no-fast-math",kp],
                   capture_output=True, text=True)
    return arch

if __name__ == "__main__":
    Ks = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else [2,4,8,16,32,48,64,80,96,128]
    for K in Ks:
        arch = compile_K(K)
        if not os.path.exists(arch):
            print("K=%d COMPILE_FAIL" % K); continue
        buf = open(arch,"rb").read()
        mo = gpu_image(buf)
        refl = sect_hex(buf, mo, "__TEXT", "__reflection")
        desc = sect_hex(buf, mo, "__TEXT", "__descriptor")
        print("K=%d" % K)
        print("  REFL", refl)
        print("  DESC", desc)
        os.remove(arch)
        sys.stdout.flush()
