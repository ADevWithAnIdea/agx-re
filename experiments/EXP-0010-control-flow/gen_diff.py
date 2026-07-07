#!/usr/bin/env python3
# gen_diff.py -- EXP-0010 differential kernels: vary ONE constant (compare
# bound / branch threshold / loop trip count / stored value) so byte-diffing
# our own compiled outputs localizes the compare-immediate, the select
# immediates, and the loop back-edge. CLEAN-ROOM: our own MSL only.
import os
HERE = os.path.dirname(os.path.abspath(__file__)); KDIR = os.path.join(HERE, "kernels")
SIG1 = ("device int* out [[buffer(0)]], device const int* a [[buffer(1)]], "
        "uint gid [[thread_position_in_grid]]")

K = {
    # early-return threshold sweep (branch on grid position)
    "eret2": (SIG1, "if (gid >= 2) return; out[gid] = 7;"),
    "eret4": (SIG1, "if (gid >= 4) return; out[gid] = 7;"),
    "eret6": (SIG1, "if (gid >= 6) return; out[gid] = 7;"),
    # early-return with different stored value (find the stored immediate)
    "eret4v9": (SIG1, "if (gid >= 4) return; out[gid] = 9;"),
    # grid select threshold sweep (branchless select)
    "gsel2": (SIG1, "out[gid] = (gid < 2) ? 111 : 222;"),
    "gsel4": (SIG1, "out[gid] = (gid < 4) ? 111 : 222;"),
    "gsel6": (SIG1, "out[gid] = (gid < 6) ? 111 : 222;"),
    # select value sweep (find select immediates)
    "gsel4b": (SIG1, "out[gid] = (gid < 4) ? 333 : 444;"),
    # data-compare select value sweep
    "dsel5": (SIG1, "out[gid] = (a[gid] > 5) ? 100 : 200;"),
    "dsel7": (SIG1, "out[gid] = (a[gid] > 7) ? 100 : 200;"),
    # a store-in-both-branches divergent if (forces two stores -> maybe a real
    # branch rather than a select of the stored value)
    "if2store": (SIG1, "if (gid < 4) { out[gid] = 111; } else { out[gid] = 222; }"),
    # a memory-effect loop with a data-dependent trip count that cannot be
    # closed-form eliminated (writes are loop-carried through a running product).
    "prodloop": (SIG1, "int s = 1; int n = a[gid]; for (int i = 0; i < n; i++) { s = s*3 + 1; } out[gid] = s;"),
    # loop trip-count differential (fixed small bounds, likely unrolled -> baseline)
    "sumn": (SIG1, "int s = 0; int n = a[gid]; for (int i = 0; i < n; i++) { s += i*i - i; } out[gid] = s;"),
}
TPL = "#include <metal_stdlib>\nusing namespace metal;\nkernel void k({sig}) {{\n    {body}\n}}\n"
def main():
    os.makedirs(KDIR, exist_ok=True)
    for n,(s,b) in K.items():
        open(os.path.join(KDIR,n+".metal"),"w").write(TPL.format(sig=s,body=b))
    print("wrote", len(K), "diff kernels")
if __name__=="__main__": main()
