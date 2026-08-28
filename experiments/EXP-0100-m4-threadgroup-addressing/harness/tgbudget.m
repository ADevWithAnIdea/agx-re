// EXP-0100 tgbudget -- public-Metal boundary probe for maximum threadgroup-
// shared bytes, allocation granularity, and the static+dynamic combination
// rule (GLCS-A02's second half). ONE case per process invocation. Builds a
// kernel source parametrized by --mode/--static-bytes/--dynamic-bytes,
// compiles with the PUBLIC Metal API (own-MSL only), creates a compute
// pipeline, and dispatches T=256 threads that COOPERATIVELY fill and then
// verify EVERY byte of every declared threadgroup region via a RUNTIME
// (thread-id-strided) loop.
//
// v2 CORRECTION (authoring stage, before any capture): a first draft touched
// only the compile-time-constant indices 0 and N-1. LLVM's SROA proved those
// were the array's only live elements and deleted the rest of the
// allocation -- `staticThreadgroupMemoryLength` read back a constant 16
// bytes for EVERY requested size including 65536, and even a 65536-byte
// request reported CANARY_OK regardless of the true hardware limit. That is
// itself a documented negative/artifact finding (PRE_REGISTRATION.md), not a
// hardware result. This version indexes every touched byte by
// `thread_position_in_threadgroup` strided across a RUNTIME loop bound (the
// declared/dynamic byte count itself, or a device-buffer-supplied M for the
// dynamic region), which the compiler cannot prove touches only a few
// elements, and reduces a per-byte pattern-mismatch count into a device
// atomic (out[0] == 0 iff every byte round-tripped correctly).
//
// CLEAN-ROOM: OWN-SHADER + PUBLIC. No Apple binary is inspected.
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o tgbudget tgbudget.m
//
// argv: --mode {static|dynamic|combined} --static-bytes N --dynamic-bytes M
// stdout line prefixes (deterministic, parsed by run.py):
//   DEVICE <name>
//   MODE <mode> STATIC_BYTES <N> DYNAMIC_BYTES <M>
//   COMPILE_STATUS <OK|FAIL> [COMPILE_ERROR <text>]
//   PIPELINE_STATUS <OK|FAIL> [PIPELINE_ERROR <text>]
//   PSO_STATIC_TGMEM <bytes>
//   DISPATCH_STATUS <OK|CMDBUF_ERROR:...|EXCEPTION:...>
//   BAD_BYTE_COUNT <n>
//   STATUS <OK|COMPILE_FAIL|PIPELINE_FAIL|CMDBUF_ERROR|EXCEPTION>
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define TPG 256   // threads per threadgroup for every dispatch in this tool

static NSString *buildSource(const char *mode, long S, long D) {
    NSMutableString *s = [NSMutableString string];
    [s appendString:@"#include <metal_stdlib>\nusing namespace metal;\n"];
    [s appendFormat:@"#define TPG %du\n", (unsigned)TPG];
    if (!strcmp(mode, "static")) {
        [s appendString:
            @"kernel void k(device atomic_uint* out [[buffer(0)]],\n"
             "              uint tid [[thread_position_in_threadgroup]]) {\n"];
        [s appendFormat:@"  threadgroup uchar tile[%ld];\n", (S > 0 ? S : 1)];
        [s appendFormat:@"  uint N = %ldu;\n", S];
        [s appendString:
            @"  for (uint k = tid; k < N; k += TPG) tile[k] = (uchar)(((k*2654435761u) >> 24) & 0xFFu);\n"
             "  threadgroup_barrier(mem_flags::mem_threadgroup);\n"
             "  for (uint k = tid; k < N; k += TPG)\n"
             "    if (tile[k] != (uchar)(((k*2654435761u) >> 24) & 0xFFu))\n"
             "      atomic_fetch_add_explicit(out, 1u, memory_order_relaxed);\n"
             "}\n"];
    } else if (!strcmp(mode, "dynamic")) {
        [s appendString:
            @"kernel void k(device atomic_uint* out [[buffer(0)]],\n"
             "              device uint* mbuf [[buffer(1)]],\n"
             "              threadgroup uchar* tile [[threadgroup(0)]],\n"
             "              uint tid [[thread_position_in_threadgroup]]) {\n"
             "  uint M = mbuf[0];\n"
             "  for (uint k = tid; k < M; k += TPG) tile[k] = (uchar)(((k*2654435761u) >> 24) & 0xFFu);\n"
             "  threadgroup_barrier(mem_flags::mem_threadgroup);\n"
             "  for (uint k = tid; k < M; k += TPG)\n"
             "    if (tile[k] != (uchar)(((k*2654435761u) >> 24) & 0xFFu))\n"
             "      atomic_fetch_add_explicit(out, 1u, memory_order_relaxed);\n"
             "}\n"];
    } else if (!strcmp(mode, "combined")) {
        [s appendString:
            @"kernel void k(device atomic_uint* out [[buffer(0)]],\n"
             "              device uint* mbuf [[buffer(1)]],\n"
             "              threadgroup uchar* dyn [[threadgroup(0)]],\n"
             "              uint tid [[thread_position_in_threadgroup]]) {\n"];
        [s appendFormat:@"  threadgroup uchar stat[%ld];\n", (S > 0 ? S : 1)];
        [s appendFormat:@"  uint N = %ldu;\n", S];
        [s appendString:
            @"  uint M = mbuf[0];\n"
             "  for (uint k = tid; k < N; k += TPG) stat[k] = (uchar)(((k*2654435761u) >> 24) & 0xFFu);\n"
             "  for (uint k = tid; k < M; k += TPG) dyn[k]  = (uchar)((((k+1u)*2246822519u) >> 24) & 0xFFu);\n"
             "  threadgroup_barrier(mem_flags::mem_threadgroup);\n"
             "  for (uint k = tid; k < N; k += TPG)\n"
             "    if (stat[k] != (uchar)(((k*2654435761u) >> 24) & 0xFFu))\n"
             "      atomic_fetch_add_explicit(out, 1u, memory_order_relaxed);\n"
             "  for (uint k = tid; k < M; k += TPG)\n"
             "    if (dyn[k] != (uchar)((((k+1u)*2246822519u) >> 24) & 0xFFu))\n"
             "      atomic_fetch_add_explicit(out, 1u, memory_order_relaxed);\n"
             "}\n"];
    }
    return s;
}

int main(int argc, char **argv) {
    @autoreleasepool {
        const char *mode = "static";
        long S = 0, D = 0;
        for (int i = 1; i < argc; i++) {
            if (!strcmp(argv[i], "--mode") && i + 1 < argc) mode = argv[++i];
            else if (!strcmp(argv[i], "--static-bytes") && i + 1 < argc) S = strtol(argv[++i], 0, 0);
            else if (!strcmp(argv[i], "--dynamic-bytes") && i + 1 < argc) D = strtol(argv[++i], 0, 0);
        }
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("MODE %s STATIC_BYTES %ld DYNAMIC_BYTES %ld\n", mode, S, D);

        NSString *src = buildSource(mode, S, D);
        NSError *err = nil;
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:nil error:&err];
        if (!lib) {
            printf("COMPILE_STATUS FAIL\n");
            printf("COMPILE_ERROR %s\n", [[err localizedDescription] UTF8String]);
            printf("STATUS COMPILE_FAIL\n");
            return 0;
        }
        printf("COMPILE_STATUS OK\n");
        id<MTLFunction> fn = [lib newFunctionWithName:@"k"];
        if (!fn) {
            printf("PIPELINE_STATUS FAIL\n");
            printf("PIPELINE_ERROR function_missing\n");
            printf("STATUS PIPELINE_FAIL\n");
            return 0;
        }
        id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithFunction:fn error:&err];
        if (!pso) {
            printf("PIPELINE_STATUS FAIL\n");
            printf("PIPELINE_ERROR %s\n", [[err localizedDescription] UTF8String]);
            printf("STATUS PIPELINE_FAIL\n");
            return 0;
        }
        printf("PIPELINE_STATUS OK\n");
        printf("PSO_STATIC_TGMEM %lu\n", (unsigned long)[pso staticThreadgroupMemoryLength]);

        __block NSString *dispatchStatus = @"OK";
        __block uint32_t badCount = 0xFFFFFFFFu;
        @try {
            id<MTLBuffer> outBuf = [dev newBufferWithLength:4 options:MTLResourceStorageModeShared];
            memset([outBuf contents], 0, 4);
            id<MTLBuffer> mBuf = [dev newBufferWithLength:4 options:MTLResourceStorageModeShared];
            ((uint32_t *)[mBuf contents])[0] = (uint32_t)D;

            id<MTLCommandQueue> q = [dev newCommandQueue];
            id<MTLCommandBuffer> cb = [q commandBuffer];
            id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
            [enc setComputePipelineState:pso];
            [enc setBuffer:outBuf offset:0 atIndex:0];
            if (!strcmp(mode, "dynamic") || !strcmp(mode, "combined")) {
                [enc setBuffer:mBuf offset:0 atIndex:1];
                [enc setThreadgroupMemoryLength:(NSUInteger)(D > 0 ? D : 1) atIndex:0];
            }
            [enc dispatchThreads:MTLSizeMake(TPG, 1, 1) threadsPerThreadgroup:MTLSizeMake(TPG, 1, 1)];
            [enc endEncoding];
            [cb commit];
            [cb waitUntilCompleted];
            if (cb.error) {
                dispatchStatus = [NSString stringWithFormat:@"CMDBUF_ERROR:%@",
                                  [cb.error localizedDescription]];
            } else {
                badCount = ((uint32_t *)[outBuf contents])[0];
            }
        } @catch (NSException *ex) {
            dispatchStatus = [NSString stringWithFormat:@"EXCEPTION:%@", [ex reason]];
        }
        BOOL ok = [dispatchStatus isEqualToString:@"OK"];
        printf("DISPATCH_STATUS %s\n", [dispatchStatus UTF8String]);
        printf("BAD_BYTE_COUNT %u\n", badCount);
        printf("STATUS %s\n", ok ? "OK" : ([dispatchStatus hasPrefix:@"CMDBUF_ERROR"] ?
                                            "CMDBUF_ERROR" : "EXCEPTION"));
        return 0;
    }
}
