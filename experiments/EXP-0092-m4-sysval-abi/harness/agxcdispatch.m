// agxcdispatch.m -- EXP-0092 own-shader 3D/indirect compute dispatch ABI probe
// (GLIO-A05).
//
// Compiles OUR OWN compute MSL at runtime (public newLibraryWithSource:, no
// binary-archive splice -- this probe validates the compiler's NATIVE
// `threadgroups_per_grid` (num_workgroups) lowering under DIRECT 3D dispatch
// (dispatchThreadgroups:threadsPerThreadgroup:, explicit per-axis threadgroup
// COUNT, not thread count) and INDIRECT dispatch
// (dispatchThreadgroupsWithIndirectBuffer:), including host-crafted malformed
// indirect records (zero, overflowing-product) that Metal's own encoder API
// cannot express directly.
//
// CLEAN-ROOM: public Metal API only, on our own compiled shader; no Apple
// binary is inspected, no binary-archive splice used.
//
// Build (device, Command Line Tools only):
//   xcrun clang -fobjc-arc -o agxcdispatch agxcdispatch.m -framework Metal -framework Foundation
//
// Usage:
//   agxcdispatch --source SRC.metal --function NAME \
//       --mode direct|indirect \
//       --tg-x X --tg-y Y --tg-z Z              (direct: threadgroup COUNT per axis)
//       --local-x LX --local-y LY --local-z LZ  (threads per threadgroup, both modes)
//       --indirect-x X --indirect-y Y --indirect-z Z   (indirect: raw record fields)
//       --out-elems N                            (output buffer size, uint32 elems; default 3)
//
// Stdout protocol:
//   STATUS OK | COMPILE_FAIL | FUNCTION_MISSING | PIPELINE_FAIL | CMDBUF_ERROR
//   DEVICE <name>
//   OUT <hex bytes of the whole output buffer>
// Exit status: 0 on STATUS OK, 1 on any failure.

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void emit_status(const char *s) { printf("STATUS %s\n", s); }
static void fail(const char *status, const char *msg, NSError *err) {
    emit_status(status);
    if (err)      printf("ERROR %s: %s\n", msg, [[err localizedDescription] UTF8String]);
    else if (msg) printf("ERROR %s\n", msg);
    fflush(stdout);
    exit(1);
}

enum { OPT_MODE = 128, OPT_TGX, OPT_TGY, OPT_TGZ, OPT_LX, OPT_LY, OPT_LZ,
       OPT_IX, OPT_IY, OPT_IZ, OPT_OUTELEMS };

static const struct option longOpts[] = {
    {"source",      required_argument, NULL, 's'},
    {"function",    required_argument, NULL, 'f'},
    {"mode",        required_argument, NULL, OPT_MODE},
    {"tg-x",        required_argument, NULL, OPT_TGX},
    {"tg-y",        required_argument, NULL, OPT_TGY},
    {"tg-z",        required_argument, NULL, OPT_TGZ},
    {"local-x",     required_argument, NULL, OPT_LX},
    {"local-y",     required_argument, NULL, OPT_LY},
    {"local-z",     required_argument, NULL, OPT_LZ},
    {"indirect-x",  required_argument, NULL, OPT_IX},
    {"indirect-y",  required_argument, NULL, OPT_IY},
    {"indirect-z",  required_argument, NULL, OPT_IZ},
    {"out-elems",   required_argument, NULL, OPT_OUTELEMS},
    {NULL, 0, NULL, 0}
};

int main(int argc, char *argv[]) {
    @autoreleasepool {
        const char *sourcePath = NULL, *funcName = NULL, *mode = "direct";
        unsigned long tgx = 1, tgy = 1, tgz = 1;
        unsigned long lx = 1, ly = 1, lz = 1;
        unsigned long ix = 1, iy = 1, iz = 1;
        long outElems = 3;
        int c;
        while ((c = getopt_long(argc, argv, "s:f:", longOpts, NULL)) > 0) {
            switch (c) {
                case 's': sourcePath = optarg; break;
                case 'f': funcName = optarg; break;
                case OPT_MODE: mode = optarg; break;
                case OPT_TGX: tgx = strtoul(optarg, NULL, 0); break;
                case OPT_TGY: tgy = strtoul(optarg, NULL, 0); break;
                case OPT_TGZ: tgz = strtoul(optarg, NULL, 0); break;
                case OPT_LX: lx = strtoul(optarg, NULL, 0); break;
                case OPT_LY: ly = strtoul(optarg, NULL, 0); break;
                case OPT_LZ: lz = strtoul(optarg, NULL, 0); break;
                case OPT_IX: ix = strtoul(optarg, NULL, 0); break;
                case OPT_IY: iy = strtoul(optarg, NULL, 0); break;
                case OPT_IZ: iz = strtoul(optarg, NULL, 0); break;
                case OPT_OUTELEMS: outElems = strtol(optarg, NULL, 0); break;
                default: fprintf(stderr, "usage: see header\n"); return 1;
            }
        }
        if (!sourcePath || !funcName)
            fail("PIPELINE_FAIL", "need --source --function", nil);

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) fail("PIPELINE_FAIL", "no Metal device", nil);
        printf("DEVICE %s\n", [[dev name] UTF8String]);

        NSError *err = nil;
        NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:sourcePath]
                                                  encoding:NSUTF8StringEncoding error:&err];
        if (!src) fail("COMPILE_FAIL", "read source", err);
        MTLCompileOptions *copts = [MTLCompileOptions new];
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:copts error:&err];
        if (!lib) fail("COMPILE_FAIL", "newLibraryWithSource", err);
        id<MTLFunction> fn = [lib newFunctionWithName:[NSString stringWithUTF8String:funcName]];
        if (!fn) fail("FUNCTION_MISSING", "newFunctionWithName", nil);
        id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithFunction:fn error:&err];
        if (!pso) fail("PIPELINE_FAIL", "newComputePipelineStateWithFunction", err);

        id<MTLBuffer> outBuf = [dev newBufferWithLength:(NSUInteger)(outElems * 4)
                                                 options:MTLResourceStorageModeShared];
        memset([outBuf contents], 0, (size_t)(outElems * 4));

        id<MTLCommandQueue> queue = [dev newCommandQueue];
        id<MTLCommandBuffer> cb = [queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
        [enc setComputePipelineState:pso];
        [enc setBuffer:outBuf offset:0 atIndex:0];
        MTLSize local = MTLSizeMake((NSUInteger)lx, (NSUInteger)ly, (NSUInteger)lz);
        if (!strcmp(mode, "direct")) {
            MTLSize tg = MTLSizeMake((NSUInteger)tgx, (NSUInteger)tgy, (NSUInteger)tgz);
            [enc dispatchThreadgroups:tg threadsPerThreadgroup:local];
        } else if (!strcmp(mode, "indirect")) {
            uint32_t rec[3] = {(uint32_t)ix, (uint32_t)iy, (uint32_t)iz};
            id<MTLBuffer> indirectBuf = [dev newBufferWithBytes:rec length:12
                                                          options:MTLResourceStorageModeShared];
            [enc dispatchThreadgroupsWithIndirectBuffer:indirectBuf
                                    indirectBufferOffset:0
                                   threadsPerThreadgroup:local];
        } else {
            fail("PIPELINE_FAIL", "bad --mode", nil);
        }
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        if ([cb status] == MTLCommandBufferStatusError)
            fail("CMDBUF_ERROR", "command buffer failed", [cb error]);

        const unsigned char *p = (const unsigned char *)[outBuf contents];
        long n = outElems * 4;
        char *hex = (char *)malloc((size_t)n * 2 + 1);
        static const char H[] = "0123456789abcdef";
        for (long j = 0; j < n; j++) {
            hex[j * 2] = H[p[j] >> 4];
            hex[j * 2 + 1] = H[p[j] & 0xf];
        }
        hex[n * 2] = 0;
        printf("OUT %s\n", hex);
        free(hex);

        emit_status("OK");
        fflush(stdout);
        return 0;
    }
}
