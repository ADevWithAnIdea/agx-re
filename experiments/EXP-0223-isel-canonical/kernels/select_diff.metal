#include <metal_stdlib>
using namespace metal;

kernel void select_lt(device const int *in [[buffer(0)]],
                      device int *out [[buffer(1)]],
                      uint tid [[thread_position_in_grid]])
{
    uint ii = tid * 4u;
    uint oi = tid * 5u;
    int a = in[ii + 0u];
    int b = in[ii + 1u];
    int t = in[ii + 2u];
    int f = in[ii + 3u];
    out[oi + 0u] = (a < b) ? t : f;
    out[oi + 1u] = a;
    out[oi + 2u] = b;
    out[oi + 3u] = t;
    out[oi + 4u] = f;
}

kernel void select_gt(device const int *in [[buffer(0)]],
                      device int *out [[buffer(1)]],
                      uint tid [[thread_position_in_grid]])
{
    uint ii = tid * 4u;
    uint oi = tid * 5u;
    int a = in[ii + 0u];
    int b = in[ii + 1u];
    int t = in[ii + 2u];
    int f = in[ii + 3u];
    out[oi + 0u] = (a > b) ? t : f;
    out[oi + 1u] = a;
    out[oi + 2u] = b;
    out[oi + 3u] = t;
    out[oi + 4u] = f;
}

