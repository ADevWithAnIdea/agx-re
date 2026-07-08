#!/usr/bin/env python3
# Fold-resistant integer register-pressure kernel (EXP-0020 pattern, our own copy).
# Runtime uniform n forces the compiler to keep K live int registers; n=1 makes the
# loop a no-op so out==in (a K-register copy) -> exact compare validates all K survived.
import sys
def kernel_src(K):
    L=["#include <metal_stdlib>","using namespace metal;",
       "kernel void k(device int* out [[buffer(0)]],",
       "              device const int* in [[buffer(1)]],",
       "              constant uint& n [[buffer(2)]],",
       "              uint gid [[thread_position_in_grid]]) {"]
    for k in range(K): L.append("  int a%d = in[gid*%d+%d];"%(k,K,k))
    L.append("  for (uint i=1;i<n;i++) {")
    L.append("    int t = in[i];")
    for k in range(K): L.append("    a%d = a%d*t + a%d;"%(k,k,(k+1)%K))
    L.append("  }")
    for k in range(K): L.append("  out[gid*%d+%d] = a%d;"%(K,k,k))
    L.append("}")
    return "\n".join(L)+"\n"
if __name__=="__main__":
    K=int(sys.argv[1]); open(sys.argv[2],"w").write(kernel_src(K))
    print("wrote",sys.argv[2],"K=",K)
