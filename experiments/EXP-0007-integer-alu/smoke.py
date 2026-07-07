#!/usr/bin/env python3
# smoke.py -- EXP-0007 sanity: run each integer kernel UNMODIFIED with known
# int inputs and check the runtime output matches the expected integer op.
# Confirms the int32 I/O path + persistent runner work before we splice.
# CLEAN-ROOM: only OUR OWN compiled shader bytes are executed.
import os, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
def lm(n, p):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
intprobe = lm("intprobe", os.path.join(HERE, "intprobe.py"))

A = [12, 20, 7, 100]
B = [3, 6, 5, 8]
EXP = {
    "iadd": [a+b for a,b in zip(A,B)],
    "isub": [a-b for a,b in zip(A,B)],
    "imul": [a*b for a,b in zip(A,B)],
    "iand": [a&b for a,b in zip(A,B)],
    "ior":  [a|b for a,b in zip(A,B)],
    "ixor": [a^b for a,b in zip(A,B)],
    "imin": [min(a,b) for a,b in zip(A,B)],
    "imax": [max(a,b) for a,b in zip(A,B)],
    "umin": [min(a,b) for a,b in zip(A,B)],
    "umax": [max(a,b) for a,b in zip(A,B)],
}

def main():
    for k, exp in EXP.items():
        p = intprobe.IntProbe(f"kernels/{k}.metal")
        r = p.run({}, {0: A, 1: B}, {2: 4}, grid=4)
        ok = r.get(2) == exp
        print(f"  [{'OK' if ok else 'FAIL'}] {k:6s} out={r.get(2)} exp={exp} st={r['_status']}")
        p.close()

if __name__ == "__main__":
    main()
