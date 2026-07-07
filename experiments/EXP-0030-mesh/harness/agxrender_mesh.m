// agxrender_mesh.m — EXP-0030 OWN-SHADER MESH render round-trip runner.
//
// The object+mesh+fragment analogue of tools/agxtest/agxrender.m. Loads a
// serialized Metal binary archive we produced from OUR OWN object+mesh+fragment
// MSL (and may have byte-spliced out-of-band), forces Metal to instantiate the
// MESH render pipeline FROM THE ARCHIVE'S PRECOMPILED MACHINE CODE
// (MTLPipelineOptionFailOnBinaryArchiveMiss), issues a drawMeshThreadgroups into
// a small BGRA8 target, and reads the pixels back.
//
// CLEAN-ROOM: public Metal API on OUR OWN compiled shader only. Never
// disassembles/introspects any Apple binary. Splice-and-reload mirrors the
// public MIT applegpu hwtestbed; our own implementation.
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o agxrender_mesh agxrender_mesh.m
//
// Usage:
//   agxrender_mesh --archive A.bin --source S.metal --object O --mesh M --fragment F
//                  [--width W] [--height H] [--obj-tg N] [--mesh-tg N] [--grid N]
//                  [--no-fast-math]
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
static void fail(const char *st, const char *msg, NSError *err) {
    emit_status(st);
    if (err)      printf("ERROR %s: %s\n", msg, [[err localizedDescription] UTF8String]);
    else if (msg) printf("ERROR %s\n", msg);
    fflush(stdout);
    exit(1);
}

enum { OPT_NO_FAST_MATH = 128, OPT_WIDTH, OPT_HEIGHT, OPT_OBJTG, OPT_MESHTG, OPT_GRID,
       OPT_OBJECT, OPT_MESH, OPT_FRAGMENT };
static const struct option longOpts[] = {
    {"archive",      required_argument, NULL, 'a'},
    {"source",       required_argument, NULL, 's'},
    {"object",       required_argument, NULL, OPT_OBJECT},
    {"mesh",         required_argument, NULL, OPT_MESH},
    {"fragment",     required_argument, NULL, OPT_FRAGMENT},
    {"width",        required_argument, NULL, OPT_WIDTH},
    {"height",       required_argument, NULL, OPT_HEIGHT},
    {"obj-tg",       required_argument, NULL, OPT_OBJTG},
    {"mesh-tg",      required_argument, NULL, OPT_MESHTG},
    {"grid",         required_argument, NULL, OPT_GRID},
    {"no-fast-math", no_argument,       NULL, OPT_NO_FAST_MATH},
    {NULL, 0, NULL, 0}
};

int main(int argc, char *argv[]) {
    @autoreleasepool {
        const char *archivePath=NULL, *sourcePath=NULL, *oName=NULL, *mName=NULL, *fName=NULL;
        long W=16, H=16, objTG=1, meshTG=3, grid=1;
        BOOL fastMath = YES;
        int c;
        while ((c = getopt_long(argc, argv, "a:s:", longOpts, NULL)) > 0) {
            switch (c) {
                case 'a': archivePath = optarg; break;
                case 's': sourcePath = optarg; break;
                case OPT_OBJECT: oName = optarg; break;
                case OPT_MESH: mName = optarg; break;
                case OPT_FRAGMENT: fName = optarg; break;
                case OPT_WIDTH:  W = strtol(optarg, NULL, 0); break;
                case OPT_HEIGHT: H = strtol(optarg, NULL, 0); break;
                case OPT_OBJTG:  objTG = strtol(optarg, NULL, 0); break;
                case OPT_MESHTG: meshTG = strtol(optarg, NULL, 0); break;
                case OPT_GRID:   grid = strtol(optarg, NULL, 0); break;
                case OPT_NO_FAST_MATH: fastMath = NO; break;
                default: fprintf(stderr, "usage: see header\n"); return 1;
            }
        }
        if (!archivePath || !sourcePath || !oName || !mName || !fName)
            fail("PIPELINE_FAIL", "need --archive --source --object --mesh --fragment", nil);

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) fail("PIPELINE_FAIL", "no Metal device", nil);
        printf("DEVICE %s\n", [[dev name] UTF8String]);

        NSError *err = nil;
        NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:sourcePath]
                                                  encoding:NSUTF8StringEncoding error:&err];
        if (!src) fail("COMPILE_FAIL", "read source", err);
        MTLCompileOptions *copts = [MTLCompileOptions new];
        [copts setFastMathEnabled:fastMath];
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:copts error:&err];
        if (!lib) fail("COMPILE_FAIL", "newLibraryWithSource", err);
        id<MTLFunction> ofn = [lib newFunctionWithName:[NSString stringWithUTF8String:oName]];
        id<MTLFunction> mfn = [lib newFunctionWithName:[NSString stringWithUTF8String:mName]];
        id<MTLFunction> ffn = [lib newFunctionWithName:[NSString stringWithUTF8String:fName]];
        if (!ofn || !mfn || !ffn) fail("FUNCTION_MISSING", "newFunctionWithName", nil);

        MTLBinaryArchiveDescriptor *adesc = [MTLBinaryArchiveDescriptor new];
        [adesc setUrl:[NSURL fileURLWithPath:[NSString stringWithUTF8String:archivePath]]];
        id<MTLBinaryArchive> archive = [dev newBinaryArchiveWithDescriptor:adesc error:&err];
        if (!archive) fail("ARCHIVE_FAIL", "newBinaryArchiveWithDescriptor", err);

        MTLMeshRenderPipelineDescriptor *md = [MTLMeshRenderPipelineDescriptor new];
        [md setObjectFunction:ofn];
        [md setMeshFunction:mfn];
        [md setFragmentFunction:ffn];
        md.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
        [md setBinaryArchives:@[archive]];
        id<MTLRenderPipelineState> pso =
            [dev newRenderPipelineStateWithMeshDescriptor:md
                                                  options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                               reflection:nil
                                                    error:&err];
        if (!pso) fail("PIPELINE_MISS", "newRenderPipelineStateWithMeshDescriptor (FailOnBinaryArchiveMiss)", err);
        printf("OBJECT %s\nMESH %s\nFRAGMENT %s\nPIPELINE_SOURCE archive\n", oName, mName, fName);

        MTLTextureDescriptor *td =
            [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                                                               width:(NSUInteger)W height:(NSUInteger)H mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
        td.storageMode = MTLStorageModeShared;
        id<MTLTexture> target = [dev newTextureWithDescriptor:td];

        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
        rp.colorAttachments[0].texture = target;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 1);
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;

        id<MTLCommandQueue> queue = [dev newCommandQueue];
        id<MTLCommandBuffer> cb = [queue commandBuffer];
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc drawMeshThreadgroups:MTLSizeMake((NSUInteger)grid, 1, 1)
              threadsPerObjectThreadgroup:MTLSizeMake((NSUInteger)objTG, 1, 1)
                threadsPerMeshThreadgroup:MTLSizeMake((NSUInteger)meshTG, 1, 1)];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        if ([cb status] == MTLCommandBufferStatusError)
            fail("CMDBUF_ERROR", "command buffer failed", [cb error]);
        printf("GPUTIME_NS %llu\n", (unsigned long long)(([cb GPUEndTime]-[cb GPUStartTime])*1e9));

        printf("SIZE %ld %ld\n", W, H);
        unsigned char *px = (unsigned char *)malloc((size_t)W*H*4);
        [target getBytes:px bytesPerRow:(NSUInteger)(W*4)
              fromRegion:MTLRegionMake2D(0,0,(NSUInteger)W,(NSUInteger)H) mipmapLevel:0];
        long covered = 0;
        for (long y=0;y<H;y++) for (long x=0;x<W;x++) {
            unsigned char *p = px + (y*W+x)*4;   // B,G,R,A
            if (p[0]||p[1]||p[2]) covered++;
        }
        printf("COVERED %ld of %ld\n", covered, W*H);
        // ASCII coverage map (green channel) + per-pixel dump (small targets)
        for (long y=0;y<H;y++) {
            printf("ROW %2ld ", y);
            for (long x=0;x<W;x++) { unsigned char *p=px+(y*W+x)*4; putchar(p[1]?'#':'.'); }
            putchar('\n');
        }
        // center pixel value for a precise readback check
        long cx=W/2, cy=H/2; unsigned char *cp = px+(cy*W+cx)*4;
        printf("CENTER %ld %ld bgra=%02x%02x%02x%02x rgba_unorm=%.3f,%.3f,%.3f,%.3f\n",
               cx, cy, cp[0],cp[1],cp[2],cp[3], cp[2]/255.0, cp[1]/255.0, cp[0]/255.0, cp[3]/255.0);
        free(px);

        emit_status("OK");
        fflush(stdout);
        return 0;
    }
}
