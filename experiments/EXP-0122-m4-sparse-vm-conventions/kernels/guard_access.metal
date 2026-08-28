// EXP-0122 authored kernels (OWN-SHADER / clean-room): boundary-distance probes for
// device-buffer addressing. Fixed access width (32-bit); the independent variable is the
// runtime byte offset `off`, which the caller supplies as an opaque uint64 uniform so the
// compiler can never fold, align, or specialize the target address. This is a NEW
// independent variable relative to EXP-0076 (which fixed distance near the allocation and
// varied width); here width is fixed and distance is varied across many decades, including
// values engineered to test GPU virtual-address wraparound.
#include <metal_stdlib>
using namespace metal;

// Read one 32-bit little-endian word from (base + off) into out[0].
kernel void guard_load_u32(device uchar* base [[buffer(0)]],
                            constant uint64_t& off [[buffer(1)]],
                            device uint* out [[buffer(2)]]) {
    device uchar* p = base + off;
    out[0] = *(device uint*)p;
}

// Write a caller-supplied 32-bit pattern to (base + off).
kernel void guard_store_u32(device uchar* base [[buffer(0)]],
                             constant uint64_t& off [[buffer(1)]],
                             constant uint& pattern [[buffer(2)]]) {
    device uchar* p = base + off;
    *(device uint*)p = pattern;
}
