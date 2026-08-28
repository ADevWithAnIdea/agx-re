// agxrender.m — clean-room OWN-SHADER render round-trip runner (EXP-0008).
//
// The render-pipeline analogue of agxrun.m. Takes a serialized Metal binary
// archive we produced from OUR OWN vertex+fragment MSL (and may have
// byte-spliced out-of-band), forces Metal to instantiate the RENDER pipeline
// FROM THE ARCHIVE'S PRECOMPILED MACHINE CODE
// (MTLPipelineOptionFailOnBinaryArchiveMiss), draws a full-screen triangle into
// a small BGRA8Unorm render target, and reads the pixels back.
//
// This lets future experiments splice arbitrary FRAGMENT bytes into our own
// compiled shader, run them on the real GPU, and observe the resulting pixel --
// the same "bytes -> observe" loop agxtest gives for compute, but for the
// fragment/vertex stages (interpolation, derivatives, sampling, blending, ...).
//
// CLEAN-ROOM: uses only the *public* Metal API on OUR OWN compiled shader. It
// never disassembles or introspects any Apple binary. The splice-and-reload
// technique mirrors the public MIT applegpu hwtestbed; this is our own impl.
//
// Build (device, Command Line Tools only):
//   clang -fobjc-arc -framework Metal -framework Foundation -o agxrender agxrender.m
//
// Usage:
//   agxrender --archive ARCH.bin --source SRC.metal --vertex V --fragment F \
//             [--width W] [--height H] [--no-fast-math] \
//             [--tex-fill R,G,B,A]      (bind a solid input texture+sampler at 0)
//
// Stdout protocol (text; one field per line):
//   STATUS OK | COMPILE_FAIL | FUNCTION_MISSING | ARCHIVE_FAIL | PIPELINE_MISS |
//          PIPELINE_FAIL | CMDBUF_ERROR
//   DEVICE <name> / VERTEX <n> / FRAGMENT <n> / PIPELINE_SOURCE archive
//   GPUTIME_NS <n>
//   SIZE <w> <h>
//   PIXEL <x> <y> bgra=<hex8> rgba_unorm=<r,g,b,a>
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

enum { OPT_NO_FAST_MATH = 128, OPT_WIDTH, OPT_HEIGHT, OPT_TEXFILL };

static const struct option longOpts[] = {
    {"archive",      required_argument, NULL, 'a'},
    {"source",       required_argument, NULL, 's'},
    {"vertex",       required_argument, NULL, 'v'},
    {"fragment",     required_argument, NULL, 'f'},
    {"width",        required_argument, NULL, OPT_WIDTH},
    {"height",       required_argument, NULL, OPT_HEIGHT},
    {"tex-fill",     required_argument, NULL, OPT_TEXFILL},
    {"no-fast-math", no_argument,       NULL, OPT_NO_FAST_MATH},
    {NULL, 0, NULL, 0}
};

int main(int argc, char *argv[]) {
    @autoreleasepool {
        const char *archivePath = NULL, *sourcePath = NULL, *vName = NULL, *fName = NULL;
        long W = 1, H = 1;
        BOOL fastMath = YES;
        BOOL bindTex = NO;
        unsigned char texRGBA[4] = {0, 0, 0, 0};
        int c;
        while ((c = getopt_long(argc, argv, "a:s:v:f:", longOpts, NULL)) > 0) {
            switch (c) {
                case 'a': archivePath = optarg; break;
                case 's': sourcePath = optarg; break;
                case 'v': vName = optarg; break;
                case 'f': fName = optarg; break;
                case OPT_WIDTH:  W = strtol(optarg, NULL, 0); break;
                case OPT_HEIGHT: H = strtol(optarg, NULL, 0); break;
                case OPT_NO_FAST_MATH: fastMath = NO; break;
                case OPT_TEXFILL: {
                    bindTex = YES;
                    int r=0,g=0,b=0,a=255;
                    sscanf(optarg, "%d,%d,%d,%d", &r,&g,&b,&a);
                    texRGBA[0]=(unsigned char)r; texRGBA[1]=(unsigned char)g;
                    texRGBA[2]=(unsigned char)b; texRGBA[3]=(unsigned char)a;
                    break;
                }
                default: fprintf(stderr, "usage: see header\n"); return 1;
            }
        }
        if (!archivePath || !sourcePath || !vName || !fName)
            fail("PIPELINE_FAIL", "need --archive --source --vertex --fragment", nil);

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) fail("PIPELINE_FAIL", "no Metal device", nil);
        printf("DEVICE %s\n", [[dev name] UTF8String]);

        NSError *err = nil;

        // --- 1. Compile OUR source -> vertex+fragment functions (the identity). -
        NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:sourcePath]
                                                  encoding:NSUTF8StringEncoding error:&err];
        if (!src) fail("COMPILE_FAIL", "read source", err);
        MTLCompileOptions *copts = [MTLCompileOptions new];
        [copts setFastMathEnabled:fastMath];
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:copts error:&err];
        if (!lib) fail("COMPILE_FAIL", "newLibraryWithSource", err);
        id<MTLFunction> vfn = [lib newFunctionWithName:[NSString stringWithUTF8String:vName]];
        id<MTLFunction> ffn = [lib newFunctionWithName:[NSString stringWithUTF8String:fName]];
        if (!vfn || !ffn) fail("FUNCTION_MISSING", "newFunctionWithName", nil);

        // --- 2. Load the (possibly spliced) binary archive from URL. -----------
        MTLBinaryArchiveDescriptor *adesc = [MTLBinaryArchiveDescriptor new];
        [adesc setUrl:[NSURL fileURLWithPath:[NSString stringWithUTF8String:archivePath]]];
        id<MTLBinaryArchive> archive = [dev newBinaryArchiveWithDescriptor:adesc error:&err];
        if (!archive) fail("ARCHIVE_FAIL", "newBinaryArchiveWithDescriptor", err);

        // --- 3. Build the render pipeline, FORCING use of the archived binary. --
        MTLRenderPipelineDescriptor *pdesc = [MTLRenderPipelineDescriptor new];
        [pdesc setVertexFunction:vfn];
        [pdesc setFragmentFunction:ffn];
        pdesc.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
        [pdesc setBinaryArchives:@[archive]];
        id<MTLRenderPipelineState> pso =
            [dev newRenderPipelineStateWithDescriptor:pdesc
                                              options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                           reflection:nil
                                                error:&err];
        if (!pso) fail("PIPELINE_MISS",
                       "newRenderPipelineStateWithDescriptor (FailOnBinaryArchiveMiss)", err);
        printf("VERTEX %s\nFRAGMENT %s\nPIPELINE_SOURCE archive\n", vName, fName);

        // --- 4. Render target (small BGRA8Unorm, shared so we can read it back). -
        MTLTextureDescriptor *td =
            [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                                                               width:(NSUInteger)W
                                                              height:(NSUInteger)H
                                                           mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
        td.storageMode = MTLStorageModeShared;
        id<MTLTexture> target = [dev newTextureWithDescriptor:td];

        // Optional: a solid-colour input texture + sampler for sampling shaders.
        id<MTLTexture> inTex = nil;
        id<MTLSamplerState> smp = nil;
        if (bindTex) {
            MTLTextureDescriptor *itd =
                [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm
                                                                   width:1 height:1 mipmapped:NO];
            itd.usage = MTLTextureUsageShaderRead;
            itd.storageMode = MTLStorageModeShared;
            inTex = [dev newTextureWithDescriptor:itd];
            [inTex replaceRegion:MTLRegionMake2D(0, 0, 1, 1) mipmapLevel:0
                       withBytes:texRGBA bytesPerRow:4];
            MTLSamplerDescriptor *sd = [MTLSamplerDescriptor new];
            smp = [dev newSamplerStateWithDescriptor:sd];
        }

        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
        rp.colorAttachments[0].texture = target;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 0);
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;

        // --- 5. Draw a full-screen triangle (3 vertices, no vertex buffer). ----
        id<MTLCommandQueue> queue = [dev newCommandQueue];
        id<MTLCommandBuffer> cb = [queue commandBuffer];
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        if (bindTex) {
            [enc setFragmentTexture:inTex atIndex:0];
            [enc setFragmentSamplerState:smp atIndex:0];
        }
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        if ([cb status] == MTLCommandBufferStatusError)
            fail("CMDBUF_ERROR", "command buffer failed", [cb error]);
        printf("GPUTIME_NS %llu\n",
               (unsigned long long)(([cb GPUEndTime] - [cb GPUStartTime]) * 1e9));

        // --- 6. Read the pixels back and print them. ---------------------------
        printf("SIZE %ld %ld\n", W, H);
        unsigned char *px = (unsigned char *)malloc((size_t)W * H * 4);
        [target getBytes:px bytesPerRow:(NSUInteger)(W * 4)
              fromRegion:MTLRegionMake2D(0, 0, (NSUInteger)W, (NSUInteger)H)
             mipmapLevel:0];
        for (long y = 0; y < H; y++) {
            for (long x = 0; x < W; x++) {
                unsigned char *p = px + (y * W + x) * 4;  // B,G,R,A in memory
                printf("PIXEL %ld %ld bgra=%02x%02x%02x%02x rgba_unorm=%.3f,%.3f,%.3f,%.3f\n",
                       x, y, p[0], p[1], p[2], p[3],
                       p[2] / 255.0, p[1] / 255.0, p[0] / 255.0, p[3] / 255.0);
            }
        }
        free(px);

        emit_status("OK");
        fflush(stdout);
        return 0;
    }
}
