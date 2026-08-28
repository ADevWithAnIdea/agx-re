// roglitmus.m -- EXP-0093 authored fragment-interlock (raster-order-group) litmus
// runner. Renders N instances of a full-screen triangle, all covering the same
// 1x1 target pixel, whose fragment shader does a non-atomic read-modify-write
// increment of a shared read_write texture OR device buffer counter -- protected
// by [[raster_order_group(0)]] in the "strong" kernels, unprotected in the "weak"
// (control) kernels. If N overlapping fragments truly serialize (mutual
// exclusion), the final counter equals exactly N; if they race, increments are
// lost and the final counter is < N.
//
// Two modes, mirroring tools/agxtest/agxrender.m and EXP-0091's fsrun.m:
//   PLAIN mode  (no --archive): Metal's own compiler picks the machine code.
//   SPLICE mode (--archive given): compile our source for function identity,
//     force the render pipeline from a (possibly byte-patched) MTLBinaryArchive
//     via MTLPipelineOptionFailOnBinaryArchiveMiss -- splicing itself is done by
//     the Python caller on a scratch copy of the archive file (agxparse.py
//     --locate offsets), exactly the tools/agxtest/agxtest.py convention. This
//     binary never patches bytes itself.
//
// CLEAN-ROOM: only the public Metal API on OUR OWN compiled shaders (OWN-SHADER
// + HW-PROBE). No Apple binary is disassembled or introspected.
//
// Build:
//   clang -fobjc-arc -framework Metal -framework Foundation -o roglitmus roglitmus.m
//
// Stdout protocol (text; one field per line):
//   STATUS OK | COMPILE_FAIL | FUNCTION_MISSING | ARCHIVE_FAIL | PIPELINE_MISS |
//          PIPELINE_FAIL | CMDBUF_ERROR
//   DEVICE <name>
//   PIPELINE_SOURCE plain|archive
//   GPUTIME_NS <n>
//   CTR_TEX <hex8>              (mode=tex: the counter texel's uint32, LE hex)
//   CTR_BUF <n> <hex8> <hex8>...  (mode=buf: n elements, each uint32 LE hex)
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
    if (fflush(NULL) != 0) { perror("fflush"); }
    if (ferror(stdout)) { fprintf(stderr, "stdout error\n"); }
    exit(1);
}

enum { OPT_INSTANCES = 256, OPT_WIDTH, OPT_HEIGHT, OPT_CTRELEMS, OPT_MODE };

static const struct option longOpts[] = {
    {"archive",    required_argument, NULL, 'a'},
    {"source",     required_argument, NULL, 's'},
    {"vertex",     required_argument, NULL, 'v'},
    {"fragment",   required_argument, NULL, 'f'},
    {"instances",  required_argument, NULL, OPT_INSTANCES},
    {"width",      required_argument, NULL, OPT_WIDTH},
    {"height",     required_argument, NULL, OPT_HEIGHT},
    {"ctr-elems",  required_argument, NULL, OPT_CTRELEMS},
    {"mode",       required_argument, NULL, OPT_MODE},
    {NULL, 0, NULL, 0}
};

int main(int argc, char *argv[]) {
    @autoreleasepool {
        const char *archivePath = NULL, *sourcePath = NULL;
        const char *vName = "v_main", *fName = "f_main";
        long W = 1, H = 1;
        long instances = 1;
        long ctrElems = 1;
        const char *mode = "tex";
        int c;
        while ((c = getopt_long(argc, argv, "a:s:v:f:", longOpts, NULL)) > 0) {
            switch (c) {
                case 'a': archivePath = optarg; break;
                case 's': sourcePath = optarg; break;
                case 'v': vName = optarg; break;
                case 'f': fName = optarg; break;
                case OPT_INSTANCES: instances = strtol(optarg, NULL, 0); break;
                case OPT_WIDTH:  W = strtol(optarg, NULL, 0); break;
                case OPT_HEIGHT: H = strtol(optarg, NULL, 0); break;
                case OPT_CTRELEMS: ctrElems = strtol(optarg, NULL, 0); break;
                case OPT_MODE: mode = optarg; break;
                default: fprintf(stderr, "usage: see header\n"); return 1;
            }
        }
        if (!sourcePath) fail("PIPELINE_FAIL", "need --source", nil);
        BOOL modeTex = (strcmp(mode, "tex") == 0);
        BOOL modeBuf = (strcmp(mode, "buf") == 0);
        if (!modeTex && !modeBuf) fail("PIPELINE_FAIL", "--mode must be tex or buf", nil);

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) fail("PIPELINE_FAIL", "no Metal device", nil);
        printf("DEVICE %s\n", [[dev name] UTF8String]);

        NSError *err = nil;

        // --- 1. Compile OUR source -> vertex+fragment functions. ---------------
        NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:sourcePath]
                                                  encoding:NSUTF8StringEncoding error:&err];
        if (!src) fail("COMPILE_FAIL", "read source", err);
        MTLCompileOptions *copts = [MTLCompileOptions new];
        // Match tools/shdump/shdump.m's default (fastMathEnabled=YES) exactly --
        // the archive's binary key is a function-content hash, and this identity
        // compile must reproduce the SAME AIR hash shdump used to build the
        // archive or FailOnBinaryArchiveMiss reports PIPELINE_MISS.
        [copts setFastMathEnabled:YES];
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:copts error:&err];
        if (!lib) fail("COMPILE_FAIL", "newLibraryWithSource", err);
        id<MTLFunction> vfn = [lib newFunctionWithName:[NSString stringWithUTF8String:vName]];
        id<MTLFunction> ffn = [lib newFunctionWithName:[NSString stringWithUTF8String:fName]];
        if (!vfn || !ffn) fail("FUNCTION_MISSING", "newFunctionWithName", nil);

        MTLRenderPipelineDescriptor *pdesc = [MTLRenderPipelineDescriptor new];
        [pdesc setVertexFunction:vfn];
        [pdesc setFragmentFunction:ffn];
        pdesc.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;

        id<MTLRenderPipelineState> pso = nil;
        const char *pipelineSource = "plain";
        if (archivePath) {
            // --- 2. SPLICE mode: force use of the (already-patched) archive. ---
            MTLBinaryArchiveDescriptor *adesc = [MTLBinaryArchiveDescriptor new];
            [adesc setUrl:[NSURL fileURLWithPath:[NSString stringWithUTF8String:archivePath]]];
            id<MTLBinaryArchive> archive = [dev newBinaryArchiveWithDescriptor:adesc error:&err];
            if (!archive) fail("ARCHIVE_FAIL", "newBinaryArchiveWithDescriptor", err);
            [pdesc setBinaryArchives:@[archive]];
            pso = [dev newRenderPipelineStateWithDescriptor:pdesc
                                                     options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                                  reflection:nil
                                                       error:&err];
            if (!pso) fail("PIPELINE_MISS",
                           "newRenderPipelineStateWithDescriptor (FailOnBinaryArchiveMiss)", err);
            pipelineSource = "archive";
        } else {
            pso = [dev newRenderPipelineStateWithDescriptor:pdesc error:&err];
            if (!pso) fail("PIPELINE_FAIL", "newRenderPipelineStateWithDescriptor (plain)", err);
        }
        printf("PIPELINE_SOURCE %s\n", pipelineSource);

        // --- 3. Render target (dummy, unwritten by these void fragment fns). ---
        MTLTextureDescriptor *td =
            [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                                                               width:(NSUInteger)W
                                                              height:(NSUInteger)H
                                                           mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget;
        td.storageMode = MTLStorageModeShared;
        id<MTLTexture> target = [dev newTextureWithDescriptor:td];

        // --- 4. The shared read_write counter resource (the litmus subject). ---
        id<MTLTexture> ctrTex = nil;
        id<MTLBuffer> ctrBuf = nil;
        if (modeTex) {
            MTLTextureDescriptor *ctd =
                [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR32Uint
                                                                   width:1 height:1 mipmapped:NO];
            ctd.usage = MTLTextureUsageShaderRead | MTLTextureUsageShaderWrite;
            ctd.storageMode = MTLStorageModeShared;
            ctrTex = [dev newTextureWithDescriptor:ctd];
            uint32_t zero = 0;
            [ctrTex replaceRegion:MTLRegionMake2D(0, 0, 1, 1) mipmapLevel:0
                         withBytes:&zero bytesPerRow:4];
        } else {
            ctrBuf = [dev newBufferWithLength:(NSUInteger)(ctrElems * 4)
                                       options:MTLResourceStorageModeShared];
            memset([ctrBuf contents], 0, (size_t)(ctrElems * 4));
        }

        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
        rp.colorAttachments[0].texture = target;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 0);
        rp.colorAttachments[0].storeAction = MTLStoreActionDontCare;

        // --- 5. Draw `instances` full-screen-triangle instances, all covering --
        //        the same pixel(s). No vertex buffer (vid-derived positions). ---
        id<MTLCommandQueue> queue = [dev newCommandQueue];
        id<MTLCommandBuffer> cb = [queue commandBuffer];
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        if (modeTex) {
            [enc setFragmentTexture:ctrTex atIndex:0];
        } else {
            [enc setFragmentBuffer:ctrBuf offset:0 atIndex:0];
        }
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3
              instanceCount:(NSUInteger)instances];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        if ([cb status] == MTLCommandBufferStatusError)
            fail("CMDBUF_ERROR", "command buffer failed", [cb error]);
        printf("GPUTIME_NS %llu\n",
               (unsigned long long)(([cb GPUEndTime] - [cb GPUStartTime]) * 1e9));

        // --- 6. Read the counter back. ------------------------------------------
        if (modeTex) {
            uint32_t val = 0;
            [ctrTex getBytes:&val bytesPerRow:4 fromRegion:MTLRegionMake2D(0, 0, 1, 1)
                  mipmapLevel:0];
            printf("CTR_TEX %08x\n", val);
        } else {
            uint32_t *vals = (uint32_t *)[ctrBuf contents];
            printf("CTR_BUF %ld", ctrElems);
            for (long i = 0; i < ctrElems; i++) printf(" %08x", vals[i]);
            printf("\n");
        }

        emit_status("OK");
        if (fflush(NULL) != 0) { perror("fflush"); return 1; }
        if (ferror(stdout)) { fprintf(stderr, "stdout error\n"); return 1; }
        return 0;
    }
}
