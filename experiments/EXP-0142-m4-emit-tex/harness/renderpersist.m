// renderpersist.m -- EXP-0142 PERSISTENT RENDER runner.
//
// The fragment-stage analogue of harness/texpersist.m: it is to
// tools/agxtest/agxrender.m what tools/agxtest/agxrun_persist.m is to
// tools/agxtest/agxrun.m. agxrender.m is one-shot (a fresh MTLDevice per
// dispatch), which makes a multi-thousand-case fragment field sweep take
// hours; this keeps one device alive and reloads a fresh MTLLibrary from each
// spliced archive's own bytes per request (the memoization gotcha documented
// in tools/agxtest/README.md).
//
// Differences from agxrender.m that matter for EXP-0142:
//   * the colour target is RGBA32Float, so a fragment result is read back as
//     an EXACT float rather than quantized through bgra8Unorm;
//   * an input buffer is bound at [[buffer(0)]] of BOTH stages so the probe
//     can feed known values;
//   * an R32Float source texture (texel(x,y) = x + 100*y) is bound at
//     fragment [[texture(0)]] with the same content as texpersist's.
//
// CLEAN-ROOM: OWN-SHADER + HW-PROBE, public Metal API only, our own compiled
// and spliced shader bytes. No Apple binary is introspected.
//
// Build:
//   clang -fobjc-arc -framework Metal -framework Foundation -O2 \
//         -o renderpersist harness/renderpersist.m
//
// Startup:
//   renderpersist --source SRC.metal --vertex V --fragment F [--width W] [--height H]
// Prints: READY <device>
// Request:  <reqid> <archive> <nin> [<idx>:<file> ...]
// Response: REQ id / STATUS ... / PIXELS <hex RGBA32F WxH> / [ERROR ..] / DONE id

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

enum { OPT_VERTEX = 128, OPT_FRAGMENT, OPT_WIDTH, OPT_HEIGHT };
static const struct option longOpts[] = {
    {"source",   required_argument, NULL, 's'},
    {"vertex",   required_argument, NULL, OPT_VERTEX},
    {"fragment", required_argument, NULL, OPT_FRAGMENT},
    {"width",    required_argument, NULL, OPT_WIDTH},
    {"height",   required_argument, NULL, OPT_HEIGHT},
    {NULL, 0, NULL, 0}
};

static id<MTLDevice> gDev = nil;
static id<MTLCommandQueue> gQueue = nil;
static const char *gV = NULL, *gF = NULL;
static int gW = 4, gH = 4;
static id<MTLTexture> gTarget = nil, gSrcTex = nil;

static void respond_fail(const char *reqid, const char *status, const char *msg, NSError *err) {
    printf("REQ %s\nSTATUS %s\n", reqid ? reqid : "?", status);
    if (err)      printf("ERROR %s: %s\n", msg ? msg : "", [[err localizedDescription] UTF8String]);
    else if (msg) printf("ERROR %s\n", msg);
    printf("DONE %s\n", reqid ? reqid : "?");
    fflush(stdout);
}

static void print_hex(const unsigned char *p, long n) {
    static const char H[] = "0123456789abcdef";
    char *hex = (char *)malloc((size_t)n * 2 + 1);
    for (long j = 0; j < n; j++) { hex[j*2] = H[p[j] >> 4]; hex[j*2+1] = H[p[j] & 0xf]; }
    hex[n*2] = 0; fputs(hex, stdout); free(hex);
}

static void handle_request(char *line) {
    @autoreleasepool {
        char *save = NULL;
        char *reqid   = strtok_r(line, " \t\r\n", &save);
        if (!reqid) return;
        char *archive = strtok_r(NULL, " \t\r\n", &save);
        char *snin    = strtok_r(NULL, " \t\r\n", &save);
        if (!archive || !snin) { respond_fail(reqid, "BAD_REQUEST", "want: id archive nin ...", nil); return; }
        int nin = (int)strtol(snin, NULL, 0);
        id<MTLBuffer> bufs[16] = {0};
        for (int i = 0; i < nin; i++) {
            char *spec = strtok_r(NULL, " \t\r\n", &save);
            if (!spec) { respond_fail(reqid, "BAD_REQUEST", "missing input", nil); return; }
            char *colon = strchr(spec, ':');
            if (!colon) { respond_fail(reqid, "BAD_REQUEST", "want IDX:FILE", nil); return; }
            *colon = 0;
            int idx = (int)strtol(spec, NULL, 0);
            if (idx < 0 || idx >= 16) { respond_fail(reqid, "BAD_REQUEST", "idx range", nil); return; }
            NSData *d = [NSData dataWithContentsOfFile:[NSString stringWithUTF8String:colon+1]];
            if (!d) { respond_fail(reqid, "BAD_REQUEST", "cannot read input", nil); return; }
            bufs[idx] = [gDev newBufferWithBytes:[d bytes] length:[d length] options:MTLResourceStorageModeShared];
        }

        NSError *err = nil;
        NSURL *url = [NSURL fileURLWithPath:[NSString stringWithUTF8String:archive]];
        id<MTLLibrary> lib = [gDev newLibraryWithURL:url error:&err];
        if (!lib) { respond_fail(reqid, "COMPILE_FAIL", "newLibraryWithURL(archive)", err); return; }
        id<MTLFunction> vf = [lib newFunctionWithName:[NSString stringWithUTF8String:gV]];
        id<MTLFunction> ff = [lib newFunctionWithName:[NSString stringWithUTF8String:gF]];
        if (!vf || !ff) { respond_fail(reqid, "FUNCTION_MISSING", "newFunctionWithName", nil); return; }
        MTLBinaryArchiveDescriptor *adesc = [MTLBinaryArchiveDescriptor new];
        [adesc setUrl:url];
        id<MTLBinaryArchive> arc = [gDev newBinaryArchiveWithDescriptor:adesc error:&err];
        if (!arc) { respond_fail(reqid, "ARCHIVE_FAIL", "newBinaryArchive", err); return; }
        MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
        pd.vertexFunction = vf; pd.fragmentFunction = ff;
        pd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA32Float;
        [pd setBinaryArchives:@[arc]];
        id<MTLRenderPipelineState> pso =
            [gDev newRenderPipelineStateWithDescriptor:pd
                                               options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                            reflection:nil error:&err];
        if (!pso) { respond_fail(reqid, "PIPELINE_MISS", "render pipeline (FailOnBinaryArchiveMiss)", err); return; }

        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
        rp.colorAttachments[0].texture = gTarget;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(-9, -9, -9, -9);
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;
        id<MTLCommandBuffer> cb = [gQueue commandBuffer];
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        for (int i = 0; i < 16; i++) if (bufs[i]) {
            [enc setVertexBuffer:bufs[i] offset:0 atIndex:i];
            [enc setFragmentBuffer:bufs[i] offset:0 atIndex:i];
        }
        [enc setFragmentTexture:gSrcTex atIndex:0];
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        if ([cb status] == MTLCommandBufferStatusError) {
            respond_fail(reqid, "CMDBUF_ERROR", "command buffer failed", [cb error]);
            gQueue = [gDev newCommandQueue];
            return;
        }
        size_t nbytes = (size_t)gW * (size_t)gH * 16;
        unsigned char *px = (unsigned char *)malloc(nbytes);
        [gTarget getBytes:px bytesPerRow:(NSUInteger)gW * 16
               fromRegion:MTLRegionMake2D(0, 0, (NSUInteger)gW, (NSUInteger)gH) mipmapLevel:0];
        printf("REQ %s\nSTATUS OK\nPIXELS ", reqid);
        print_hex(px, (long)nbytes);
        printf("\nDONE %s\n", reqid);
        fflush(stdout);
        free(px);
    }
}

int main(int argc, char *argv[]) {
    @autoreleasepool {
        const char *sourcePath = NULL;
        int c;
        while ((c = getopt_long(argc, argv, "s:", longOpts, NULL)) > 0) {
            switch (c) {
                case 's': sourcePath = optarg; break;
                case OPT_VERTEX: gV = optarg; break;
                case OPT_FRAGMENT: gF = optarg; break;
                case OPT_WIDTH: gW = (int)strtol(optarg, NULL, 0); break;
                case OPT_HEIGHT: gH = (int)strtol(optarg, NULL, 0); break;
                default: return 2;
            }
        }
        if (!sourcePath || !gV || !gF) {
            fprintf(stderr, "usage: renderpersist --source S --vertex V --fragment F\n");
            return 2;
        }
        gDev = MTLCreateSystemDefaultDevice();
        if (!gDev) { fprintf(stderr, "no Metal device\n"); return 1; }
        gQueue = [gDev newCommandQueue];
        NSError *err = nil;
        NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:sourcePath]
                                                  encoding:NSUTF8StringEncoding error:&err];
        if (!src) { fprintf(stderr, "read source failed\n"); return 1; }
        id<MTLLibrary> lib = [gDev newLibraryWithSource:src options:[MTLCompileOptions new] error:&err];
        if (!lib) { fprintf(stderr, "compile failed: %s\n", [[err localizedDescription] UTF8String]); return 1; }
        if (![lib newFunctionWithName:[NSString stringWithUTF8String:gV]] ||
            ![lib newFunctionWithName:[NSString stringWithUTF8String:gF]]) {
            fprintf(stderr, "vertex/fragment function missing\n"); return 1;
        }
        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float
                                                                                      width:(NSUInteger)gW
                                                                                     height:(NSUInteger)gH
                                                                                  mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
        td.storageMode = MTLStorageModeShared;
        gTarget = [gDev newTextureWithDescriptor:td];

        MTLTextureDescriptor *sd = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR32Float
                                                                                      width:16 height:16 mipmapped:NO];
        sd.usage = MTLTextureUsageShaderRead; sd.storageMode = MTLStorageModeShared;
        gSrcTex = [gDev newTextureWithDescriptor:sd];
        {
            float *tmp = (float *)malloc(16*16*sizeof(float));
            for (int y = 0; y < 16; y++) for (int x = 0; x < 16; x++) tmp[y*16+x] = (float)x + 100.0f*(float)y;
            [gSrcTex replaceRegion:MTLRegionMake2D(0,0,16,16) mipmapLevel:0 withBytes:tmp bytesPerRow:16*4];
            free(tmp);
        }
        printf("READY %s\n", [[gDev name] UTF8String]);
        fflush(stdout);
        char *line = NULL; size_t cap = 0;
        while (getline(&line, &cap, stdin) > 0) {
            char *copy = strdup(line); handle_request(copy); free(copy);
        }
        free(line);
        return 0;
    }
}
