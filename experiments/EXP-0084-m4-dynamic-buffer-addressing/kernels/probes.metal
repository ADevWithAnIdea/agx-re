#include <metal_stdlib>
using namespace metal;

// EXP-0084 -- MEM-20/21/22 dynamic buffer addressing kernels (own-MSL,
// compiled at runtime through the public Metal API only). Every dynamic
// device address dereferenced below is obtained through public Metal
// mechanisms: `MTLBuffer.gpuAddress` (a public property since Metal 3)
// written by our own CPU-side harness into an ordinary `device ulong*`
// buffer, or Metal's implicit-argument-buffer struct-member-pointer
// feature. No Apple binary is inspected to write or understand this file;
// these are documented public MSL/Metal language features.

// ---------------------------------------------------------------------
// Sanity control: a single directly (statically) bound buffer. Proves the
// harness buffer/dispatch/readback plumbing itself is correct before any
// dynamic-addressing claim is interpreted.
// ---------------------------------------------------------------------
kernel void ctrl_direct(device uint* a [[buffer(0)]],
                         device uint* out [[buffer(1)]],
                         uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid];
}

// ---------------------------------------------------------------------
// MEM-20 / MEM-21 core kernel family: `addrs` is a plain `device ulong*`
// buffer holding N raw 64-bit GPU virtual addresses (each obtained from a
// distinct backing MTLBuffer's public `.gpuAddress` on the CPU side and
// written into `addrs[k]` by ordinary CPU memcpy -- never passed to
// `setBuffer:offset:atIndex:` for the backing buffers themselves). No
// backing buffer is ever assigned a statically encoded [[buffer(N)]] base
// slot; the ONLY statically bound resource is `addrs` itself (and `out`).
//
// mem21_uniform: the selector is a UNIFORM scalar argument (`constant
// uint&`), identical for every thread by construction -- it cannot vary
// per lane. This is both the MEM-20 core positive test (N can be 1) and
// the MEM-21 negative control ("a uniform-program selection that picks
// only one address for the entire dispatch").
kernel void mem21_uniform(device ulong* addrs [[buffer(0)]],
                           constant uint& sel_u [[buffer(1)]],
                           device uint* out [[buffer(2)]],
                           uint gid [[thread_position_in_grid]]) {
    device uint* p = (device uint*)addrs[sel_u];
    out[gid] = p[0];
}

// mem21_perlane: the selector is computed ONLY from `thread_position_in_grid`
// (gid) and a uniform bound N -- never read back from a per-lane data
// buffer -- so per-lane divergence, if observed, cannot be attributed to
// ordinary per-element buffer indexing (which is not in question) and must
// come from the dynamic BASE ADDRESS selection itself.
kernel void mem21_perlane(device ulong* addrs [[buffer(0)]],
                           constant uint& N [[buffer(1)]],
                           device uint* out [[buffer(2)]],
                           device uint* outsel [[buffer(3)]],
                           uint gid [[thread_position_in_grid]]) {
    uint sel = gid % N;
    device uint* p = (device uint*)addrs[sel];
    out[gid] = p[0];
    outsel[gid] = sel;
}

// mem21_outlier: every lane selects addrs[0] except exactly lane gid==K,
// which selects addrs[1]. Fine-grained single-lane-divergence control,
// refuting a "coarse broadcast-group" alternative explanation.
kernel void mem21_outlier(device ulong* addrs [[buffer(0)]],
                           constant uint& K [[buffer(1)]],
                           device uint* out [[buffer(2)]],
                           uint gid [[thread_position_in_grid]]) {
    uint sel = (gid == K) ? 1u : 0u;
    device uint* p = (device uint*)addrs[sel];
    out[gid] = p[0];
}

// ---------------------------------------------------------------------
// MEM-20 second construction method: Metal's IMPLICIT argument buffer.
// `ArgBuf` is a struct with a `device uint*` member; when used as a kernel
// parameter type Metal auto-generates the argument-buffer layout and the
// member is populated on the CPU side via `MTLArgumentEncoder`
// (`newArgumentEncoderWithBufferIndex:` + `setBuffer:offset:atIndex:`),
// NOT via `setBuffer:offset:atIndex:` on the compute encoder for the
// pointee buffer itself. Independent construction from `mem21_*`'s raw
// `ulong` cast, same underlying question.
// ---------------------------------------------------------------------
struct ArgBuf { device uint *ptr; };

kernel void mem20_implicit_ab(constant ArgBuf& ab [[buffer(0)]],
                               device uint* out [[buffer(1)]],
                               uint gid [[thread_position_in_grid]]) {
    out[gid] = ab.ptr[gid];
}

// ---------------------------------------------------------------------
// MEM-20 stretch: double indirection. `addrs2[0]` holds the dynamic
// address of a small buffer (`mid`) whose own element 0 holds the dynamic
// address of the final data buffer. Neither `mid` nor the final buffer is
// ever statically bound. Tests whether the mechanism composes.
// ---------------------------------------------------------------------
kernel void mem20_chained(device ulong* addrs2 [[buffer(0)]],
                           device uint* out [[buffer(1)]],
                           uint gid [[thread_position_in_grid]]) {
    device ulong* mid = (device ulong*)addrs2[0];
    device uint* p = (device uint*)mid[0];
    out[gid] = p[gid];
}

// ---------------------------------------------------------------------
// Splice target (EXP-0084 analysis/splice_case.py): TWO independent
// dynamic pointers are loaded (pA=addrs[0], pB=addrs[1]) and BOTH results
// are kept live (both feed a store), so neither load can be dead-code
// eliminated and both destination registers survive to the two device_load
// instructions that dereference them. `out` receives pA's data, `outb`
// receives pB's data -- the frozen splice case locates the device_load
// instruction that produces `out`'s value and swaps its `index_reg` field
// to the register the OTHER (`pB`) load used, predicting `out` then reads
// pB's tag instead of pA's.
// ---------------------------------------------------------------------
kernel void splice_target(device ulong* addrs [[buffer(0)]],
                           device uint* out [[buffer(1)]],
                           device uint* outb [[buffer(2)]],
                           uint gid [[thread_position_in_grid]]) {
    device uint* pA = (device uint*)addrs[0];
    device uint* pB = (device uint*)addrs[1];
    uint vA = pA[gid];
    uint vB = pB[gid];
    out[gid] = vA;
    outb[gid] = vB;
}
