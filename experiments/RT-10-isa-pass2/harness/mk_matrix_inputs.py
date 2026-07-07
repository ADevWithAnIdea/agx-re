#!/usr/bin/env python3
# Generate 8x8 matrix input files for the p3 matrix splice test.
# A = identity, B[i][j]=10*i+j, C = all 100. So D = A*B + C = B + 100 (elementwise).
import sys
def w(path, vals):
    open(path,"w").write(",".join(str(v) for v in vals))
A=[1.0 if i==j else 0.0 for i in range(8) for j in range(8)]
B=[float(10*i+j) for i in range(8) for j in range(8)]
C=[100.0]*64
w("A.txt",A); w("B.txt",B); w("C.txt",C)
print("wrote A.txt B.txt C.txt (64 floats each)")
