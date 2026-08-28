#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              device float* mem [[buffer(1)]],
              device int* imem [[buffer(2)]],
              uint tid [[thread_position_in_grid]]) {
    float acc = mem[tid + 0];
    acc = acc * 1.0000001f + mem[tid + 1u];
    acc = acc * 1.0000001f + mem[tid + 2u];
    acc = acc * 1.0000001f + mem[tid + 3u];
    acc = acc * 1.0000001f + mem[tid + 4u];
    acc = acc * 1.0000001f + mem[tid + 5u];
    acc = acc * 1.0000001f + mem[tid + 6u];
    acc = acc * 1.0000001f + mem[tid + 7u];
    acc = acc * 1.0000001f + mem[tid + 8u];
    acc = acc * 1.0000001f + mem[tid + 9u];
    acc = acc * 1.0000001f + mem[tid + 10u];
    acc = acc * 1.0000001f + mem[tid + 11u];
    acc = acc * 1.0000001f + mem[tid + 12u];
    acc = acc * 1.0000001f + mem[tid + 13u];
    acc = acc * 1.0000001f + mem[tid + 14u];
    acc = acc * 1.0000001f + mem[tid + 15u];
    acc = acc * 1.0000001f + mem[tid + 16u];
    acc = acc * 1.0000001f + mem[tid + 17u];
    acc = acc * 1.0000001f + mem[tid + 18u];
    acc = acc * 1.0000001f + mem[tid + 19u];
    acc = acc * 1.0000001f + mem[tid + 20u];
    acc = acc * 1.0000001f + mem[tid + 21u];
    acc = acc * 1.0000001f + mem[tid + 22u];
    acc = acc * 1.0000001f + mem[tid + 23u];
    acc = acc * 1.0000001f + mem[tid + 24u];
    acc = acc * 1.0000001f + mem[tid + 25u];
    acc = acc * 1.0000001f + mem[tid + 26u];
    acc = acc * 1.0000001f + mem[tid + 27u];
    acc = acc * 1.0000001f + mem[tid + 28u];
    acc = acc * 1.0000001f + mem[tid + 29u];
    acc = acc * 1.0000001f + mem[tid + 30u];
    acc = acc * 1.0000001f + mem[tid + 31u];
    acc = acc * 1.0000001f + mem[tid + 32u];
    acc = acc * 1.0000001f + mem[tid + 33u];
    acc = acc * 1.0000001f + mem[tid + 34u];
    acc = acc * 1.0000001f + mem[tid + 35u];
    acc = acc * 1.0000001f + mem[tid + 36u];
    acc = acc * 1.0000001f + mem[tid + 37u];
    acc = acc * 1.0000001f + mem[tid + 38u];
    acc = acc * 1.0000001f + mem[tid + 39u];
    acc = acc * 1.0000001f + mem[tid + 40u];
    acc = acc * 1.0000001f + mem[tid + 41u];
    acc = acc * 1.0000001f + mem[tid + 42u];
    acc = acc * 1.0000001f + mem[tid + 43u];
    acc = acc * 1.0000001f + mem[tid + 44u];
    acc = acc * 1.0000001f + mem[tid + 45u];
    acc = acc - float(imem[tid + 1u]) * 0.0000001f;
    acc = acc - float(imem[tid + 2u]) * 0.0000001f;
    acc = acc - float(imem[tid + 3u]) * 0.0000001f;
    acc = acc - float(imem[tid + 4u]) * 0.0000001f;
    acc = acc - float(imem[tid + 5u]) * 0.0000001f;
    acc = acc - float(imem[tid + 6u]) * 0.0000001f;
    acc = acc - float(imem[tid + 7u]) * 0.0000001f;
    out[tid + 0] = acc;
}
