// EXP-0036 census corpus — COMPUTE kernels. OUR OWN MSL (OWN-SHADER).
// One .metal, many kernels; the driver compiles each by function name and
// extracts its _agc.main. Spans int/uint/float/half arithmetic, all conversions,
// control flow + loops + calls, memory/atomics/threadgroup, subgroup/quad, matrix,
// and the get_sr / mov_imm builtins. No Apple binary is inspected.
#include <metal_stdlib>
#include <metal_simdgroup_matrix>
using namespace metal;

// ---------------- integer / uint / float / half arithmetic ----------------
kernel void k_int_arith(device int* o[[buffer(0)]], device const int* a[[buffer(1)]],
                        device const int* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    int x=a[i], y=b[i];
    o[i] = (x+y) - (x*y) + (x/ (y|1)) - (x % (y|1));
}
kernel void k_uint_arith(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]],
                        device const uint* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    uint x=a[i], y=b[i];
    o[i] = (x+y)*(x-y) + (x/(y|1u)) + (x%(y|1u));
}
kernel void k_float_arith(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                        device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    float x=a[i], y=b[i];
    o[i] = fma(x,y,x) + (x/y) - (x*y) + (x+y);
}
kernel void k_half_arith(device half* o[[buffer(0)]], device const half* a[[buffer(1)]],
                        device const half* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    half x=a[i], y=b[i];
    o[i] = (x+y)*(x-y) + x*y;
}
kernel void k_half2_pack(device half2* o[[buffer(0)]], device const half2* a[[buffer(1)]],
                        device const half2* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    half2 x=a[i], y=b[i];
    o[i] = x*y + x - y;   // packed 2-lane half ALU (0x10) + pack (0x18)
}
// ---------------- integer bitwise / shift / bitcount / rotate / bitfield ----
kernel void k_int_bitwise(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]],
                        device const uint* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    uint x=a[i], y=b[i];
    o[i] = (x&y) | (x^y) | (~x) | (x & ~y);
}
kernel void k_int_shift(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]],
                        device const uint* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    uint x=a[i]; int s=a[i];
    o[i] = (x<<3) | (x>>2) | uint(s>>2) | (x<<(b[i]&31)) | (x>>(b[i]&31));
}
kernel void k_int_bitcount(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]],
                        uint i[[thread_position_in_grid]]) {
    uint x=a[i];
    o[i] = popcount(x) + clz(x) + ctz(x) + reverse_bits(x);
}
kernel void k_int_rotate(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]],
                        device const uint* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    uint x=a[i];
    o[i] = rotate(x, 5u) + rotate(x, b[i]);   // rotate by imm + by register
}
kernel void k_int_bitfield(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]],
                        device const uint* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    uint x=a[i], y=b[i];
    o[i] = extract_bits(x, 4, 8) + insert_bits(x, y, 3, 6);
}
kernel void k_int_minmax(device int* o[[buffer(0)]], device const int* a[[buffer(1)]],
                        device const int* b[[buffer(2)]], device const int* c[[buffer(3)]],
                        uint i[[thread_position_in_grid]]) {
    int x=a[i], y=b[i], z=c[i];
    o[i] = min3(x,y,z) + max3(x,y,z) + median3(x,y,z) + clamp(x, y, z);
}
kernel void k_int64(device long* o[[buffer(0)]], device const long* a[[buffer(1)]],
                        device const long* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    long x=a[i], y=b[i];
    o[i] = (x+y) - (x*y) + (x < y ? x : y) + (x >> 3);
}
// ---------------- conversions ------------------------------------------------
kernel void k_cvt_fi(device float* o[[buffer(0)]], device const float* f[[buffer(1)]],
                        device const int* n[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = float(int(f[i])) + float(uint(f[i])) + float(n[i]) + float(uint(n[i]));
}
kernel void k_cvt_half(device float* o[[buffer(0)]], device const float* f[[buffer(1)]],
                        device const int* n[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    half h = half(f[i]);
    o[i] = float(h) + float(half(n[i])) + float(int(h));
}
kernel void k_cvt_pack(device uint* o[[buffer(0)]], device const float2* a[[buffer(1)]],
                        device const uint* p[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    uint packed = pack_float_to_unorm2x16(a[i]) + pack_float_to_snorm2x16(a[i]);
    float2 u = unpack_unorm2x16_to_float(p[i]) + unpack_snorm2x16_to_float(p[i]);
    o[i] = packed + as_type<uint>(u.x + u.y);
}
// ---------------- transcendental / special functions ------------------------
kernel void k_transcend(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                        uint i[[thread_position_in_grid]]) {
    float x=a[i];
    o[i] = exp2(x)+log2(x)+sqrt(x)+rsqrt(x)+(1.0f/x)+sin(x)+cos(x)+pow(x,2.5f)+exp(x)+log(x);
}
kernel void k_transcend_round(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                        uint i[[thread_position_in_grid]]) {
    float x=a[i];
    o[i] = floor(x)+ceil(x)+trunc(x)+rint(x)+fract(x)+abs(x)+sign(x);
}
// ---------------- control flow: if / loop / switch / call -------------------
kernel void k_cf_if(device int* o[[buffer(0)]], device const int* a[[buffer(1)]],
                        uint i[[thread_position_in_grid]]) {
    int x=a[i], r;
    if (x > 10) r = x*2; else if (x < -10) r = -x; else r = x;
    o[i] = (x & 1) ? r : (r + 3);
}
kernel void k_cf_loop(device int* o[[buffer(0)]], device const int* a[[buffer(1)]],
                        uint i[[thread_position_in_grid]]) {
    int acc=0; int n = a[i] & 31;
    for (int j=0;j<n;j++) acc += a[(i+j)&255];
    int k=0; while (acc > 100) { acc -= 7; k++; }
    o[i] = acc + k;
}
kernel void k_cf_switch(device int* o[[buffer(0)]], device const int* a[[buffer(1)]],
                        uint i[[thread_position_in_grid]]) {
    int r=0;
    switch (a[i] & 7) {
        case 0: r=a[i]+1; break; case 1: r=a[i]*2; break;
        case 2: r=a[i]-3; break; case 3: r=a[i]/2; break;
        default: r=a[i];
    }
    o[i]=r;
}
static int __attribute__((noinline)) helper_add(int a, int b){ return a+b; }
static int __attribute__((noinline)) helper_mul(int a, int b){ return a*b; }
kernel void k_cf_call(device int* o[[buffer(0)]], device const int* a[[buffer(1)]],
                        device const int* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = helper_add(a[i], b[i]) + helper_mul(a[i], b[i]);
}
// ---------------- memory / threadgroup / atomics ----------------------------
kernel void k_mem(device float4* o[[buffer(0)]], device const float4* a[[buffer(1)]],
                        device const float* s[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = a[i] * s[i&255] + a[(i+1)&255];
}
kernel void k_threadgroup(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                        uint i[[thread_position_in_grid]], uint li[[thread_position_in_threadgroup]]) {
    threadgroup float tile[256];
    tile[li] = a[i];
    threadgroup_barrier(mem_flags::mem_threadgroup);
    o[i] = tile[(li+1)&255] + tile[(li+2)&255];
}
kernel void k_atomics(device atomic_uint* o[[buffer(0)]], device const uint* a[[buffer(1)]],
                        uint i[[thread_position_in_grid]]) {
    atomic_fetch_add_explicit(&o[0], a[i], memory_order_relaxed);
    atomic_fetch_max_explicit(&o[1], a[i], memory_order_relaxed);
    atomic_fetch_min_explicit(&o[2], a[i], memory_order_relaxed);
    atomic_fetch_and_explicit(&o[3], a[i], memory_order_relaxed);
    atomic_fetch_or_explicit(&o[4], a[i], memory_order_relaxed);
    atomic_fetch_xor_explicit(&o[5], a[i], memory_order_relaxed);
    atomic_exchange_explicit(&o[6], a[i], memory_order_relaxed);
    uint exp=0; atomic_compare_exchange_weak_explicit(&o[7], &exp, a[i], memory_order_relaxed, memory_order_relaxed);
}
kernel void k_atomics_float(device atomic_float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                        uint i[[thread_position_in_grid]]) {
    atomic_fetch_add_explicit(&o[0], a[i], memory_order_relaxed);
}
kernel void k_atomics_tg(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]],
                        uint i[[thread_position_in_grid]], uint li[[thread_position_in_threadgroup]]) {
    threadgroup atomic_uint c;
    if (li==0) atomic_store_explicit(&c, 0u, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    atomic_fetch_add_explicit(&c, a[i], memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    o[i] = atomic_load_explicit(&c, memory_order_relaxed);
}
// ---------------- subgroup / quad -------------------------------------------
kernel void k_subgroup_reduce(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                        uint i[[thread_position_in_grid]]) {
    float x=a[i];
    o[i] = simd_sum(x)+simd_max(x)+simd_min(x)+simd_product(x);
}
kernel void k_subgroup_int(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]],
                        uint i[[thread_position_in_grid]]) {
    uint x=a[i];
    o[i] = simd_and(x)+simd_or(x)+simd_xor(x)+simd_max(x);
}
kernel void k_subgroup_scan(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]],
                        uint i[[thread_position_in_grid]]) {
    uint x=a[i];
    o[i] = simd_prefix_inclusive_sum(x) + simd_prefix_exclusive_sum(x);
}
kernel void k_subgroup_shuffle(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]],
                        uint i[[thread_position_in_grid]]) {
    uint x=a[i];
    o[i] = simd_broadcast(x,0)+simd_broadcast_first(x)+simd_shuffle(x,3)+simd_shuffle_xor(x,1)
         + simd_shuffle_up(x,1)+simd_shuffle_down(x,1)+simd_shuffle_rotate_up(x,1);
}
kernel void k_subgroup_ballot(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]],
                        uint i[[thread_position_in_grid]]) {
    bool p = a[i] > 0;
    simd_vote v = simd_ballot(p);
    o[i] = uint((simd_vote::vote_t)v) + (simd_all(p)?1:0) + (simd_any(p)?2:0) + (simd_is_first()?4:0);
}
kernel void k_quad(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]],
                        uint i[[thread_position_in_grid]]) {
    uint x=a[i];
    o[i] = quad_broadcast(x,0)+quad_shuffle(x,2)+quad_shuffle_xor(x,1)+quad_sum(x)+quad_max(x);
}
// ---------------- matrix ----------------------------------------------------
kernel void k_matrix(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                        device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]],
                        uint li[[thread_index_in_threadgroup]]) {
    simdgroup_float8x8 A, B, C;
    simdgroup_load(A, a, 8);
    simdgroup_load(B, b, 8);
    C = simdgroup_float8x8(0);
    simdgroup_multiply_accumulate(C, A, B, C);
    simdgroup_store(C, o, 8);
}
kernel void k_matrix_half(device half* o[[buffer(0)]], device const half* a[[buffer(1)]],
                        device const half* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    simdgroup_half8x8 A, B, C;
    simdgroup_load(A, a, 8);
    simdgroup_load(B, b, 8);
    C = simdgroup_half8x8(0);
    simdgroup_multiply_accumulate(C, A, B, C);
    simdgroup_store(C, o, 8);
}
// ---------------- builtins: get_sr coverage + folded mov_imm ----------------
kernel void k_builtins_ids(device uint* o[[buffer(0)]],
                        uint  tpig [[thread_position_in_grid]],
                        uint  tpit [[thread_position_in_threadgroup]],
                        uint  tig  [[thread_index_in_threadgroup]],
                        uint  tgpg [[threadgroup_position_in_grid]],
                        uint  tptg [[threads_per_threadgroup]],
                        uint  tgpg2[[threadgroups_per_grid]],
                        uint  sli  [[thread_index_in_simdgroup]],
                        uint  sgi  [[simdgroup_index_in_threadgroup]]) {
    o[tpig] = tpit + tig + tgpg + tptg + tgpg2 + sli + sgi;
}
kernel void k_builtins_folded(device uint* o[[buffer(0)]],
                        uint i[[thread_position_in_grid]],
                        uint spt[[threads_per_simdgroup]],
                        uint sgt[[simdgroups_per_threadgroup]]) {
    o[i] = spt + sgt;   // threads_per_simdgroup folds to mov_imm 0x20 (=32)
}
