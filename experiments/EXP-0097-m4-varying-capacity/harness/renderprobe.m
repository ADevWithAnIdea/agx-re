// renderprobe.m -- EXP-0097 GLPRE-A03 (+ GLIO-A01 aliasing readback) render probe.
//
// Compiles OUR OWN MSL at runtime, builds a render pipeline, draws, and reads
// pixels back. Four modes share one binary because they share nearly all
// setup/readback code:
//
//   --mode render    plain WxH target, one draw call, full pixel-grid readback.
//                     Used for: varying/clip aliasing checksum readback,
//                     NaN/Inf/signed-zero position tests, provoking-vertex tests.
//   --mode point     point-topology draw into a WxH target, reports the
//                     rendered footprint (bbox + coverage count) of the point.
//   --mode layer     texture2d_array target (--layers N), one triangle whose
//                     [[render_target_array_index]] is baked into the shader
//                     source; reads back the center pixel of EVERY layer.
//   --mode viewport  --viewports N viewports tiling one target (quadrant grid
//                     up to 4, else stacked columns), one triangle whose
//                     [[viewport_array_index]] is baked into the shader
//                     source; reads back the WHOLE target (every tile).
//
// Clean-room: OWN-SHADER. Only our own MSL (file path arg) is compiled via
// the public Metal runtime API; only public MTLTexture/MTLCommandBuffer
// readback state is inspected. No Apple binary is introspected.
//
// Build (device, Command Line Tools only):
//   clang -fobjc-arc -framework Metal -framework Foundation -o renderprobe renderprobe.m
//
// Stdout protocol (text; one field per line), always terminated by STATUS:
//   STATUS COMPILE_FAIL|FUNCTION_MISSING|PIPELINE_FAIL|CMDBUF_ERROR|OK
//   ERROR <message>                              (on any *_FAIL)
//   GPUTIME_NS <n>
//   --mode render:   PIXEL <x> <y> rgba=<r>,<g>,<b>,<a>          (one per texel)
//   --mode point:    BBOX <xmin> <ymin> <xmax> <ymax> COUNT <n> TOTAL <w*h>
//   --mode layer:    LAYERPIX <layer> rgba=<r>,<g>,<b>,<a>       (one per layer)
//   --mode viewport: PIXEL <x> <y> rgba=<r>,<g>,<b>,<a>          (one per texel)
// Exit status: 0 iff STATUS OK, 1 otherwise.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void done_fail(const char *status, NSError *err) {
    printf("STATUS %s\n", status);
    if (err) {
        NSString *d = [[err localizedDescription] stringByReplacingOccurrencesOfString:@"\n" withString:@" | "];
        printf("ERROR %s\n", [d UTF8String]);
    }
    fflush(stdout);
    exit(1);
}

enum { OPT_MODE = 128, OPT_WIDTH, OPT_HEIGHT, OPT_LAYERS, OPT_VIEWPORTS, OPT_TOPOLOGY, OPT_VCOUNT, OPT_ICOUNT };
static const struct option longOpts[] = {
    {"source",    required_argument, NULL, 's'},
    {"vertex",    required_argument, NULL, 'v'},
    {"fragment",  required_argument, NULL, 'f'},
    {"mode",      required_argument, NULL, OPT_MODE},
    {"width",     required_argument, NULL, OPT_WIDTH},
    {"height",    required_argument, NULL, OPT_HEIGHT},
    {"layers",    required_argument, NULL, OPT_LAYERS},
    {"viewports", required_argument, NULL, OPT_VIEWPORTS},
    {"topology",  required_argument, NULL, OPT_TOPOLOGY},   // triangle|strip|point
    {"vcount",    required_argument, NULL, OPT_VCOUNT},     // vertex count for the draw
    {"icount",    required_argument, NULL, OPT_ICOUNT},     // >0: use an index buffer 0..icount-1 reversed order (provoking test)
    {NULL, 0, NULL, 0}
};

static id<MTLLibrary> compileOrDie(id<MTLDevice> dev, const char *sourcePath) {
    NSError *err = nil;
    NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:sourcePath]
                                                encoding:NSUTF8StringEncoding error:&err];
    if (!src) done_fail("COMPILE_FAIL", err);
    MTLCompileOptions *co = [MTLCompileOptions new];
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:co error:&err];
    if (!lib) done_fail("COMPILE_FAIL", err);
    return lib;
}

int main(int argc, char *argv[]) {
    @autoreleasepool {
        const char *sourcePath = NULL, *vName = NULL, *fName = NULL, *mode = "render";
        long W = 4, H = 4, layers = 1, viewports = 1;
        const char *topology = "triangle";
        long vcount = 3, icount = 0;
        int c;
        while ((c = getopt_long(argc, argv, "s:v:f:", longOpts, NULL)) > 0) {
            switch (c) {
                case 's': sourcePath = optarg; break;
                case 'v': vName = optarg; break;
                case 'f': fName = optarg; break;
                case OPT_MODE: mode = optarg; break;
                case OPT_WIDTH: W = strtol(optarg, NULL, 0); break;
                case OPT_HEIGHT: H = strtol(optarg, NULL, 0); break;
                case OPT_LAYERS: layers = strtol(optarg, NULL, 0); break;
                case OPT_VIEWPORTS: viewports = strtol(optarg, NULL, 0); break;
                case OPT_TOPOLOGY: topology = optarg; break;
                case OPT_VCOUNT: vcount = strtol(optarg, NULL, 0); break;
                case OPT_ICOUNT: icount = strtol(optarg, NULL, 0); break;
                default: fprintf(stderr, "usage: see header\n"); return 2;
            }
        }
        if (!sourcePath || !vName || !fName) { fprintf(stderr, "need --source --vertex --fragment\n"); return 2; }

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) done_fail("PIPELINE_FAIL", nil);
        id<MTLLibrary> lib = compileOrDie(dev, sourcePath);
        id<MTLFunction> vf = [lib newFunctionWithName:[NSString stringWithUTF8String:vName]];
        id<MTLFunction> ff = [lib newFunctionWithName:[NSString stringWithUTF8String:fName]];
        if (!vf || !ff) done_fail("FUNCTION_MISSING", nil);

        NSError *err = nil;
        MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
        pd.vertexFunction = vf;
        pd.fragmentFunction = ff;
        pd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA32Float; // exact float readback, no unorm quantization
        MTLPrimitiveType ptype = MTLPrimitiveTypeTriangle;
        if (strcmp(mode, "point") == 0) {
            pd.inputPrimitiveTopology = MTLPrimitiveTopologyClassPoint;
            ptype = MTLPrimitiveTypePoint;
        } else if (strcmp(topology, "strip") == 0) {
            pd.inputPrimitiveTopology = MTLPrimitiveTopologyClassTriangle;
            ptype = MTLPrimitiveTypeTriangleStrip;
        } else {
            pd.inputPrimitiveTopology = MTLPrimitiveTopologyClassTriangle;
            ptype = MTLPrimitiveTypeTriangle;
        }

        id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err];
        if (!pso) done_fail("PIPELINE_FAIL", err);

        id<MTLCommandQueue> queue = [dev newCommandQueue];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];

        id<MTLTexture> target = nil;
        if (strcmp(mode, "layer") == 0) {
            MTLTextureDescriptor *td = [MTLTextureDescriptor new];
            td.textureType = MTLTextureType2DArray;
            td.pixelFormat = MTLPixelFormatRGBA32Float;
            td.width = (NSUInteger)W; td.height = (NSUInteger)H; td.arrayLength = (NSUInteger)layers;
            td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
            td.storageMode = MTLStorageModeShared;
            target = [dev newTextureWithDescriptor:td];
            rp.renderTargetArrayLength = (NSUInteger)layers;
        } else {
            MTLTextureDescriptor *td =
                [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float
                                                                    width:(NSUInteger)W height:(NSUInteger)H
                                                                mipmapped:NO];
            td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
            td.storageMode = MTLStorageModeShared;
            target = [dev newTextureWithDescriptor:td];
        }
        rp.colorAttachments[0].texture = target;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(-1, -1, -1, -1); // sentinel, never a real fragment output
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;

        id<MTLCommandBuffer> cb = [queue commandBuffer];
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];

        if (strcmp(mode, "viewport") == 0 && viewports > 0) {
            MTLViewport *vps = (MTLViewport *)malloc(sizeof(MTLViewport) * (size_t)viewports);
            // Tile the target into `viewports` equal vertical strips so every
            // viewport index maps to a visually distinct, non-overlapping region.
            double stripW = (double)W / (double)viewports;
            for (long i = 0; i < viewports; i++) {
                vps[i] = (MTLViewport){ .originX = i * stripW, .originY = 0,
                                         .width = stripW, .height = (double)H,
                                         .znear = 0.0, .zfar = 1.0 };
            }
            [enc setViewports:vps count:(NSUInteger)viewports];
            free(vps);
        }

        if (icount > 0) {
            // Reversed-order index buffer: draws vertex slots [icount-1 .. 0]
            // in that index order, to test whether "provoking vertex" tracks
            // the fetched vertex_id or the primitive's assembly-slot order.
            uint16_t *idx = (uint16_t *)malloc(sizeof(uint16_t) * (size_t)icount);
            for (long i = 0; i < icount; i++) idx[i] = (uint16_t)(icount - 1 - i);
            id<MTLBuffer> ibuf = [dev newBufferWithBytes:idx length:sizeof(uint16_t) * (size_t)icount
                                                  options:MTLResourceStorageModeShared];
            free(idx);
            [enc drawIndexedPrimitives:ptype indexCount:(NSUInteger)icount indexType:MTLIndexTypeUInt16
                             indexBuffer:ibuf indexBufferOffset:0];
        } else {
            [enc drawPrimitives:ptype vertexStart:0 vertexCount:(NSUInteger)vcount];
        }
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        if ([cb status] == MTLCommandBufferStatusError) done_fail("CMDBUF_ERROR", [cb error]);
        printf("GPUTIME_NS %llu\n", (unsigned long long)(([cb GPUEndTime] - [cb GPUStartTime]) * 1e9));

        if (strcmp(mode, "layer") == 0) {
            float *px = (float *)malloc(sizeof(float) * 4 * (size_t)W * (size_t)H);
            for (long l = 0; l < layers; l++) {
                MTLRegion region = MTLRegionMake2D(0, 0, (NSUInteger)W, (NSUInteger)H);
                [target getBytes:px bytesPerRow:(NSUInteger)(W * 4 * sizeof(float))
                      bytesPerImage:(NSUInteger)(W * H * 4 * sizeof(float))
                         fromRegion:region mipmapLevel:0 slice:(NSUInteger)l];
                long cx = W / 2, cy = H / 2;
                float *p = px + (cy * W + cx) * 4;
                printf("LAYERPIX %ld rgba=%.6f,%.6f,%.6f,%.6f\n", l, p[0], p[1], p[2], p[3]);
            }
            free(px);
        } else if (strcmp(mode, "point") == 0) {
            float *px = (float *)malloc(sizeof(float) * 4 * (size_t)W * (size_t)H);
            [target getBytes:px bytesPerRow:(NSUInteger)(W * 4 * sizeof(float))
                  fromRegion:MTLRegionMake2D(0, 0, (NSUInteger)W, (NSUInteger)H) mipmapLevel:0];
            long xmin = W, ymin = H, xmax = -1, ymax = -1, count = 0;
            for (long y = 0; y < H; y++) {
                for (long x = 0; x < W; x++) {
                    float *p = px + (y * W + x) * 4;
                    BOOL isClear = (p[0] == -1.0f && p[1] == -1.0f && p[2] == -1.0f && p[3] == -1.0f);
                    if (!isClear) {
                        count++;
                        if (x < xmin) xmin = x; if (x > xmax) xmax = x;
                        if (y < ymin) ymin = y; if (y > ymax) ymax = y;
                    }
                }
            }
            printf("BBOX %ld %ld %ld %ld COUNT %ld TOTAL %ld\n", xmin, ymin, xmax, ymax, count, W * H);
            free(px);
        } else {
            float *px = (float *)malloc(sizeof(float) * 4 * (size_t)W * (size_t)H);
            [target getBytes:px bytesPerRow:(NSUInteger)(W * 4 * sizeof(float))
                  fromRegion:MTLRegionMake2D(0, 0, (NSUInteger)W, (NSUInteger)H) mipmapLevel:0];
            for (long y = 0; y < H; y++) {
                for (long x = 0; x < W; x++) {
                    float *p = px + (y * W + x) * 4;
                    printf("PIXEL %ld %ld rgba=%.6f,%.6f,%.6f,%.6f\n", x, y, p[0], p[1], p[2], p[3]);
                }
            }
            free(px);
        }

        printf("STATUS OK\n");
        fflush(stdout);
        return 0;
    }
}
