#include <metal_stdlib>
using namespace metal;

// EXP-0076: buffer robustness matrix kernels (Part-II MEM-06..MEM-10).
//
// One entry point per (op, width) case class; the byte offset is a runtime
// uniform (params[0]) read from device memory, so the compiler can never
// constant-fold, align, or specialize the access: every case observes the
// behavior of the frozen idiom at an address chosen by the harness.
//
// params layout (8 uint words, little-endian):
//   params[0]      = byte offset from the base of buffer(0)
//   params[1]      = reserved (0)
//   params[2..5]   = store value words (little-endian byte order); loads ignore
//   params[6..7]   = reserved (0)
//
// Frozen access idioms (these exact dereference forms are the object under
// test; they are ordinary MSL reinterpret-style pointer casts authored here):
//   8-bit   load/store : *(device uchar  *)p
//   16-bit  load/store : *(device ushort *)p
//   32-bit  load/store : *(device uint   *)p
//   64-bit  load/store : *(device ulong  *)p
//   128-bit load/store : *(device uint4  *)p
//   32-bit atomic xchg : array form abuf[params[0]/4] on device atomic_uint*
//                        (all atomic offsets are multiples of 4)
//
// The loaded/stored value is transported as raw words in the result buffer;
// no floating-point conversion ever touches an observation.

kernel void k_load_w8(device uchar *buf [[buffer(0)]],
                      device uint *params [[buffer(1)]],
                      device uint *result [[buffer(2)]])
{
    device uchar *p = buf + params[0];
    result[0] = uint(*p);
}

kernel void k_load_w16(device uchar *buf [[buffer(0)]],
                       device uint *params [[buffer(1)]],
                       device uint *result [[buffer(2)]])
{
    device uchar *p = buf + params[0];
    result[0] = uint(*(device ushort *)p);
}

kernel void k_load_w32(device uchar *buf [[buffer(0)]],
                       device uint *params [[buffer(1)]],
                       device uint *result [[buffer(2)]])
{
    device uchar *p = buf + params[0];
    result[0] = *(device uint *)p;
}

kernel void k_load_w64(device uchar *buf [[buffer(0)]],
                       device uint *params [[buffer(1)]],
                       device uint *result [[buffer(2)]])
{
    device uchar *p = buf + params[0];
    ulong v = *(device ulong *)p;
    result[0] = uint(v & 0xFFFFFFFFu);
    result[1] = uint((v >> 32) & 0xFFFFFFFFu);
}

kernel void k_load_w128(device uchar *buf [[buffer(0)]],
                        device uint *params [[buffer(1)]],
                        device uint *result [[buffer(2)]])
{
    device uchar *p = buf + params[0];
    uint4 v = *(device uint4 *)p;
    result[0] = v.x;
    result[1] = v.y;
    result[2] = v.z;
    result[3] = v.w;
}

kernel void k_store_w8(device uchar *buf [[buffer(0)]],
                       device uint *params [[buffer(1)]],
                       device uint *result [[buffer(2)]])
{
    device uchar *p = buf + params[0];
    *p = uchar(params[2] & 0xFFu);
}

kernel void k_store_w16(device uchar *buf [[buffer(0)]],
                        device uint *params [[buffer(1)]],
                        device uint *result [[buffer(2)]])
{
    device uchar *p = buf + params[0];
    *(device ushort *)p = ushort(params[2] & 0xFFFFu);
}

kernel void k_store_w32(device uchar *buf [[buffer(0)]],
                        device uint *params [[buffer(1)]],
                        device uint *result [[buffer(2)]])
{
    device uchar *p = buf + params[0];
    *(device uint *)p = params[2];
}

kernel void k_store_w64(device uchar *buf [[buffer(0)]],
                        device uint *params [[buffer(1)]],
                        device uint *result [[buffer(2)]])
{
    device uchar *p = buf + params[0];
    ulong v = (ulong(params[3]) << 32) | ulong(params[2] & 0xFFFFFFFFu);
    *(device ulong *)p = v;
}

kernel void k_store_w128(device uchar *buf [[buffer(0)]],
                         device uint *params [[buffer(1)]],
                         device uint *result [[buffer(2)]])
{
    device uchar *p = buf + params[0];
    *(device uint4 *)p = uint4(params[2], params[3], params[4], params[5]);
}

// Optional stretch class: 32-bit atomic exchange, element-index idiom on a
// buffer(0) bound directly as device atomic_uint*. Probed only in its own
// cases, never mixed with another operation in the same dispatch.
kernel void k_axch_w32(device atomic_uint *abuf [[buffer(0)]],
                       device uint *params [[buffer(1)]],
                       device uint *result [[buffer(2)]])
{
    device atomic_uint *a = abuf + (params[0] / 4u);
    result[0] = atomic_exchange_explicit(a, params[2], memory_order_relaxed);
}
