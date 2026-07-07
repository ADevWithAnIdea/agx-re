// EXP-0035 C: calling-convention / ABI differential kernels (A18 Pro / G17P).
// CLEAN-ROOM: OUR OWN MSL. Only our own compiled bytes are inspected.
//
// Each noinline helper isolates one ABI fact:
//  - arg->register mapping: idK returns the K-th argument (moves argreg[K]->retreg)
//  - return-value register: all helpers leave the result where the caller reads it
//  - return-instruction: invariant tail across helpers with different bodies
//  - stack/spill: a helper with many args forces overflow of the arg registers
#include <metal_stdlib>
using namespace metal;

// ---- arg-register mapping: return the K-th of 6 float args ------------------
__attribute__((noinline)) static float id0(float a,float b,float c,float d,float e,float f){return a;}
__attribute__((noinline)) static float id1(float a,float b,float c,float d,float e,float f){return b;}
__attribute__((noinline)) static float id2(float a,float b,float c,float d,float e,float f){return c;}
__attribute__((noinline)) static float id3(float a,float b,float c,float d,float e,float f){return d;}
__attribute__((noinline)) static float id4(float a,float b,float c,float d,float e,float f){return e;}
__attribute__((noinline)) static float id5(float a,float b,float c,float d,float e,float f){return f;}

// one caller per idK; 6 distinct device inputs so no folding.
#define IDK(NAME,FN) \
kernel void NAME(device const float*A[[buffer(0)]],device float*O[[buffer(1)]],uint i[[thread_position_in_grid]]){ \
  O[i]=FN(A[6*i+0],A[6*i+1],A[6*i+2],A[6*i+3],A[6*i+4],A[6*i+5]); }
IDK(k_id0,id0) IDK(k_id1,id1) IDK(k_id2,id2) IDK(k_id3,id3) IDK(k_id4,id4) IDK(k_id5,id5)

// ---- return-instruction isolation: same sig, different body ----------------
__attribute__((noinline)) static float h_add(float a,float b){return a+b;}
__attribute__((noinline)) static float h_mul(float a,float b){return a*b;}
__attribute__((noinline)) static float h_sub(float a,float b){return a-b;}
#define BINK(NAME,FN) \
kernel void NAME(device const float*A[[buffer(0)]],device const float*B[[buffer(1)]],device float*O[[buffer(2)]],uint i[[thread_position_in_grid]]){ \
  O[i]=FN(A[i],B[i]); }
BINK(k_add,h_add) BINK(k_mul,h_mul) BINK(k_sub,h_sub)

// ---- two call sites to the SAME helper: pin return-address / target offset --
kernel void k_twocall(device const float*A[[buffer(0)]],device const float*B[[buffer(1)]],
                      device float*O[[buffer(2)]],uint i[[thread_position_in_grid]]){
  float x=h_add(A[i],B[i]);
  float y=h_add(x, B[i]);      // second call site, same target
  O[i]=y;
}

// ---- return-type: int and half returns -------------------------------------
__attribute__((noinline)) static int   h_iadd(int a,int b){return a+b;}
__attribute__((noinline)) static half  h_hadd(half a,half b){return a+b;}
kernel void k_iadd(device const int*A[[buffer(0)]],device const int*B[[buffer(1)]],device int*O[[buffer(2)]],uint i[[thread_position_in_grid]]){O[i]=h_iadd(A[i],B[i]);}
kernel void k_hadd(device const half*A[[buffer(0)]],device const half*B[[buffer(1)]],device half*O[[buffer(2)]],uint i[[thread_position_in_grid]]){O[i]=h_hadd(A[i],B[i]);}

// ---- many-arg helper: force arg overflow beyond the arg registers ----------
__attribute__((noinline)) static float h_many(float a,float b,float c,float d,float e,float f,
                                               float g,float h,float p,float q,float r,float s){
  return a+b+c+d+e+f+g+h+p+q+r+s;
}
kernel void k_many(device const float*A[[buffer(0)]],device float*O[[buffer(1)]],uint i[[thread_position_in_grid]]){
  O[i]=h_many(A[12*i+0],A[12*i+1],A[12*i+2],A[12*i+3],A[12*i+4],A[12*i+5],
              A[12*i+6],A[12*i+7],A[12*i+8],A[12*i+9],A[12*i+10],A[12*i+11]);
}

// ---- helper that itself spills (deep register pressure) + calls: stack frame ?
__attribute__((noinline)) static float h_pressure(float a,float b){
  float acc=a; float x=b;
  // long dependent chain to raise the callee register footprint
  for(int k=0;k<40;k++){ acc = acc*1.5f + x; x = x + acc*0.5f; }
  return acc + x;
}
kernel void k_pressure(device const float*A[[buffer(0)]],device const float*B[[buffer(1)]],device float*O[[buffer(2)]],uint i[[thread_position_in_grid]]){O[i]=h_pressure(A[i],B[i]);}
