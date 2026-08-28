// agxvdraw.m -- EXP-0092 own-shader indexed-draw ABI probe (GLIO-A03).
//
// Compiles OUR OWN vertex+fragment MSL at runtime (public newLibraryWithSource:,
// no binary-archive splice needed -- this probe validates the compiler's NATIVE
// lowering of [[vertex_id]]/[[instance_id]]/[[base_vertex]]/[[base_instance]] on
// a real, controlled indexed/instanced draw, not a spliced encoding), issues ONE
// indexed draw with caller-supplied index buffer contents / instanceCount /
// baseVertex / baseInstance, and reads back the per-invocation (vid,iid,bv,bi)
// record buffer the vertex shader wrote via an atomic-counter-indexed append.
//
// CLEAN-ROOM: public Metal API only, on our own compiled shader; no Apple
// binary is inspected. No binary-archive splice is used in this harness.
//
// Build (device, Command Line Tools only):
//   xcrun clang -fobjc-arc -o agxvdraw agxvdraw.m -framework Metal -framework Foundation
//
// Usage:
//   agxvdraw --source SRC.metal --vertex V --fragment F \
//       --indices i0,i1,i2,...     (uint32 index buffer contents; index-type uint32)
//       --instance-count N --base-vertex BV --base-instance BI \
//       --primitive point|line|triangle|linestrip|trianglestrip \
//       --max-records N            (record buffer capacity; default 4096)
//
// Stdout protocol (text; one field per line):
//   STATUS OK | COMPILE_FAIL | FUNCTION_MISSING | PIPELINE_FAIL | CMDBUF_ERROR
//   DEVICE <name>
//   COUNT <n>                  (atomic counter final value: invocations recorded)
//   REC <i> vid=<u> iid=<u> bv=<u> bi=<u>     (one line per recorded invocation)
//   (on failure) ERROR <message>
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

enum { OPT_INDICES = 128, OPT_INSTANCE_COUNT, OPT_BASE_VERTEX, OPT_BASE_INSTANCE,
       OPT_PRIMITIVE, OPT_MAX_RECORDS, OPT_INDEX_START };

static const struct option longOpts[] = {
    {"source",         required_argument, NULL, 's'},
    {"vertex",         required_argument, NULL, 'v'},
    {"fragment",       required_argument, NULL, 'f'},
    {"indices",        required_argument, NULL, OPT_INDICES},
    {"instance-count", required_argument, NULL, OPT_INSTANCE_COUNT},
    {"base-vertex",    required_argument, NULL, OPT_BASE_VERTEX},
    {"base-instance",  required_argument, NULL, OPT_BASE_INSTANCE},
    {"primitive",      required_argument, NULL, OPT_PRIMITIVE},
    {"max-records",    required_argument, NULL, OPT_MAX_RECORDS},
    {"index-start",    required_argument, NULL, OPT_INDEX_START},
    {NULL, 0, NULL, 0}
};

int main(int argc, char *argv[]) {
    @autoreleasepool {
        const char *sourcePath = NULL, *vName = NULL, *fName = NULL, *indicesStr = NULL;
        long instanceCount = 1;
        long baseVertex = 0;
        unsigned long baseInstance = 0;
        long maxRecords = 4096;
        long indexBufferStart = 0;
        const char *primStr = "point";
        int c;
        while ((c = getopt_long(argc, argv, "s:v:f:", longOpts, NULL)) > 0) {
            switch (c) {
                case 's': sourcePath = optarg; break;
                case 'v': vName = optarg; break;
                case 'f': fName = optarg; break;
                case OPT_INDICES: indicesStr = optarg; break;
                case OPT_INSTANCE_COUNT: instanceCount = strtol(optarg, NULL, 0); break;
                case OPT_BASE_VERTEX: baseVertex = strtol(optarg, NULL, 0); break;
                case OPT_BASE_INSTANCE: baseInstance = strtoul(optarg, NULL, 0); break;
                case OPT_PRIMITIVE: primStr = optarg; break;
                case OPT_MAX_RECORDS: maxRecords = strtol(optarg, NULL, 0); break;
                case OPT_INDEX_START: indexBufferStart = strtol(optarg, NULL, 0); break;
                default: fprintf(stderr, "usage: see header\n"); return 1;
            }
        }
        if (!sourcePath || !vName || !fName || !indicesStr)
            fail("PIPELINE_FAIL", "need --source --vertex --fragment --indices", nil);

        // parse index list
        uint32_t idx[65536]; int nidx = 0;
        {
            char *dup = strdup(indicesStr);
            char *tok = strtok(dup, ",");
            while (tok && nidx < 65536) {
                idx[nidx++] = (uint32_t)strtoul(tok, NULL, 0);
                tok = strtok(NULL, ",");
            }
            free(dup);
        }
        if (nidx == 0) fail("PIPELINE_FAIL", "empty --indices", nil);

        MTLPrimitiveType prim = MTLPrimitiveTypePoint;
        if (!strcmp(primStr, "point")) prim = MTLPrimitiveTypePoint;
        else if (!strcmp(primStr, "line")) prim = MTLPrimitiveTypeLine;
        else if (!strcmp(primStr, "linestrip")) prim = MTLPrimitiveTypeLineStrip;
        else if (!strcmp(primStr, "triangle")) prim = MTLPrimitiveTypeTriangle;
        else if (!strcmp(primStr, "trianglestrip")) prim = MTLPrimitiveTypeTriangleStrip;
        else fail("PIPELINE_FAIL", "bad --primitive", nil);

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
        id<MTLFunction> vfn = [lib newFunctionWithName:[NSString stringWithUTF8String:vName]];
        id<MTLFunction> ffn = [lib newFunctionWithName:[NSString stringWithUTF8String:fName]];
        if (!vfn || !ffn) fail("FUNCTION_MISSING", "newFunctionWithName", nil);

        MTLRenderPipelineDescriptor *pdesc = [MTLRenderPipelineDescriptor new];
        [pdesc setVertexFunction:vfn];
        [pdesc setFragmentFunction:ffn];
        pdesc.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
        id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:pdesc error:&err];
        if (!pso) fail("PIPELINE_FAIL", "newRenderPipelineStateWithDescriptor", err);

        // index buffer (uint32)
        id<MTLBuffer> ibuf = [dev newBufferWithBytes:idx length:(NSUInteger)(nidx * 4)
                                              options:MTLResourceStorageModeShared];
        // output record buffer: maxRecords * uint4 (16 bytes), zero-init
        id<MTLBuffer> outBuf = [dev newBufferWithLength:(NSUInteger)(maxRecords * 16)
                                                 options:MTLResourceStorageModeShared];
        memset([outBuf contents], 0, (size_t)(maxRecords * 16));
        id<MTLBuffer> counterBuf = [dev newBufferWithLength:4 options:MTLResourceStorageModeShared];
        memset([counterBuf contents], 0, 4);

        // 1x1 render target (unused pixel content; only the vertex-side effect matters)
        MTLTextureDescriptor *td =
            [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                                                               width:1 height:1 mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget;
        td.storageMode = MTLStorageModePrivate;
        id<MTLTexture> target = [dev newTextureWithDescriptor:td];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
        rp.colorAttachments[0].texture = target;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 0);
        rp.colorAttachments[0].storeAction = MTLStoreActionDontCare;

        id<MTLCommandQueue> queue = [dev newCommandQueue];
        id<MTLCommandBuffer> cb = [queue commandBuffer];
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc setVertexBuffer:outBuf offset:0 atIndex:0];
        [enc setVertexBuffer:counterBuf offset:0 atIndex:1];
        [enc drawIndexedPrimitives:prim
                         indexCount:(NSUInteger)nidx
                          indexType:MTLIndexTypeUInt32
                        indexBuffer:ibuf
                  indexBufferOffset:(NSUInteger)indexBufferStart
                      instanceCount:(NSUInteger)instanceCount
                         baseVertex:(NSInteger)baseVertex
                       baseInstance:(NSUInteger)baseInstance];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        if ([cb status] == MTLCommandBufferStatusError)
            fail("CMDBUF_ERROR", "command buffer failed", [cb error]);

        uint32_t count = *(uint32_t *)[counterBuf contents];
        printf("COUNT %u\n", count);
        uint32_t *recs = (uint32_t *)[outBuf contents];
        uint32_t nprint = count < (uint32_t)maxRecords ? count : (uint32_t)maxRecords;
        for (uint32_t i = 0; i < nprint; i++) {
            uint32_t vid = recs[i * 4 + 0], iid = recs[i * 4 + 1],
                     bv  = recs[i * 4 + 2], bi  = recs[i * 4 + 3];
            printf("REC %u vid=%u iid=%u bv=%u bi=%u\n", i, vid, iid, bv, bi);
        }
        emit_status("OK");
        fflush(stdout);
        return 0;
    }
}
