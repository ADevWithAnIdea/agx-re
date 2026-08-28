// texrender.m -- EXP-0094 generic render-pipeline texture-LOD probe harness.
//
// Extends the house pattern (tools/agxtest/agxrender.m, EXP-0016/texr.m): compiles
// OUR OWN MSL at runtime (public newLibraryWithSource:) for the public-Metal
// behavioral sweeps, OR -- when --archive is given -- forces a possibly
// byte-spliced render pipeline FROM OUR OWN precompiled archive
// (MTLPipelineOptionFailOnBinaryArchiveMiss), draws one full-screen triangle,
// and reads back the resulting pixel(s) as raw floats.
//
// Generic texture/sampler/params binding so ONE binary drives every fragment-
// stage backend (bias_probe.metal, lodquery_probe.metal, regsplice_bias.metal):
//   texture(0)  = a 2D texture, W x H, --tex-levels mip levels. Each level is
//                 either a per-level SOLID color (--tex-level L=R,G,B,A,
//                 repeatable) or, with --tex-lodramp, filled with the constant
//                 value float(level) in every texel (the "LOD-recovery" trick:
//                 with mipFilter=linear the hardware's own trilinear blend
//                 reads back the CONTINUOUS effective LOD it selected).
//   sampler(0)  = configurable min/mag/mip filter, address mode, lodMinClamp/
//                 lodMaxClamp.
//   buffer(0)   = constant float* params  (raw floats from --params, indexed
//                 params[0], params[1], ... by the kernel -- no shared struct
//                 needed between harness and kernel).
//   [[position]] is passed to the fragment function; the vertex stage is a
//   fixed "big triangle" (clip positions only, no interpolated varyings), so
//   d(window-space)/d(pixel) is exactly 1 and any kernel-side uv = position.xy
//   * uvScale has an EXACTLY known, closed-form derivative (no interpolation
//   rounding). See kernels/*.metal for the exact formula each kernel uses.
//
// CLEAN-ROOM: public Metal API on OUR OWN compiled MSL only (source path), or
// OUR OWN previously-extracted-and-spliced AGX bytes forced to run via a Metal
// binary archive (archive path, mirrors the public MIT applegpu hwtestbed
// splice-and-reload technique). No Apple binary is disassembled either way.
//
// Build:
//   clang -fobjc-arc -framework Metal -framework Foundation -o texrender texrender.m
//
// Stdout protocol:
//   STATUS OK|COMPILE_FAIL|FUNCTION_MISSING|ARCHIVE_FAIL|PIPELINE_MISS|PIPELINE_FAIL|CMDBUF_ERROR
//   DEVICE <name>
//   PIPELINE_SOURCE source|archive
//   PIXEL r=<f> g=<f> b=<f> a=<f>      (single readback pixel, exact float32)
//   (on failure) ERROR <message>
// Exit status: 0 on STATUS OK, 1 otherwise.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void emit_status(const char *s) { printf("STATUS %s\n", s); }
static void fail(const char *st, const char *msg, NSError *e) {
    emit_status(st);
    if (e) printf("ERROR %s: %s\n", msg, [[e localizedDescription] UTF8String]);
    else if (msg) printf("ERROR %s\n", msg);
    fflush(stdout);
    exit(1);
}

enum { OPT_ARCHIVE = 128, OPT_SPLICE, OPT_RT_FORMAT, OPT_TEX_FORMAT, OPT_TEX_SIZE,
       OPT_TEX_LEVELS, OPT_TEX_LEVEL, OPT_TEX_LODRAMP, OPT_MIN, OPT_MAG, OPT_MIPF,
       OPT_LODMIN, OPT_LODMAX, OPT_ADDR, OPT_PARAMS, OPT_VIEW_LEVELS, OPT_READ_XY,
       OPT_RT_SIZE, OPT_NO_FM };

static const struct option lo[] = {
    {"source", required_argument, 0, 's'}, {"vertex", required_argument, 0, 'v'},
    {"fragment", required_argument, 0, 'f'}, {"archive", required_argument, 0, OPT_ARCHIVE},
    {"splice", required_argument, 0, OPT_SPLICE}, {"rt-format", required_argument, 0, OPT_RT_FORMAT},
    {"tex-format", required_argument, 0, OPT_TEX_FORMAT}, {"tex-size", required_argument, 0, OPT_TEX_SIZE},
    {"tex-levels", required_argument, 0, OPT_TEX_LEVELS}, {"tex-level", required_argument, 0, OPT_TEX_LEVEL},
    {"tex-lodramp", no_argument, 0, OPT_TEX_LODRAMP}, {"sampler-min", required_argument, 0, OPT_MIN},
    {"sampler-mag", required_argument, 0, OPT_MAG}, {"sampler-mipfilter", required_argument, 0, OPT_MIPF},
    {"sampler-lodmin", required_argument, 0, OPT_LODMIN}, {"sampler-lodmax", required_argument, 0, OPT_LODMAX},
    {"sampler-address", required_argument, 0, OPT_ADDR}, {"params", required_argument, 0, OPT_PARAMS},
    {"view-levels", required_argument, 0, OPT_VIEW_LEVELS}, {"read-xy", required_argument, 0, OPT_READ_XY},
    {"rt-size", required_argument, 0, OPT_RT_SIZE}, {"no-fast-math", no_argument, 0, OPT_NO_FM},
    {0, 0, 0, 0}
};

#define MAXSPLICE 32
#define MAXLEVELS 16
#define MAXPARAMS 64

int main(int argc, char **argv) {
  @autoreleasepool {
    const char *srcPath = NULL, *vName = NULL, *fName = NULL, *archivePath = NULL;
    const char *spliceArgs[MAXSPLICE]; int nSplice = 0;
    const char *rtFormatStr = "r32float", *texFormatStr = "r32float";
    long texW = 256, texH = 256, texLevels = 9;
    int haveLevelFill[MAXLEVELS]; float levelFill[MAXLEVELS][4];
    memset(haveLevelFill, 0, sizeof(haveLevelFill));
    BOOL lodRamp = NO;
    const char *minStr = "nearest", *magStr = "nearest", *mipfStr = "linear", *addrStr = "clamp";
    float lodMin = 0.0f, lodMax = 1000.0f; BOOL haveLodMin = NO, haveLodMax = NO;
    float params[MAXPARAMS]; int nParams = 0;
    long viewLo = -1, viewHi = -1;
    long readX = 0, readY = 0;
    long rtW = 4, rtH = 4;
    BOOL fastMath = YES;
    int c;
    while ((c = getopt_long(argc, argv, "s:v:f:", lo, NULL)) > 0) {
      switch (c) {
        case 's': srcPath = optarg; break;
        case 'v': vName = optarg; break;
        case 'f': fName = optarg; break;
        case OPT_ARCHIVE: archivePath = optarg; break;
        case OPT_SPLICE: if (nSplice < MAXSPLICE) spliceArgs[nSplice++] = optarg; break;
        case OPT_RT_FORMAT: rtFormatStr = optarg; break;
        case OPT_TEX_FORMAT: texFormatStr = optarg; break;
        case OPT_TEX_SIZE: sscanf(optarg, "%ld,%ld", &texW, &texH); break;
        case OPT_TEX_LEVELS: texLevels = strtol(optarg, NULL, 0); break;
        case OPT_TEX_LEVEL: {
          int L; float r,g,b,a;
          if (sscanf(optarg, "%d=%f,%f,%f,%f", &L, &r, &g, &b, &a) == 5 && L >= 0 && L < MAXLEVELS) {
            haveLevelFill[L] = 1; levelFill[L][0]=r; levelFill[L][1]=g; levelFill[L][2]=b; levelFill[L][3]=a;
          }
          break;
        }
        case OPT_TEX_LODRAMP: lodRamp = YES; break;
        case OPT_MIN: minStr = optarg; break;
        case OPT_MAG: magStr = optarg; break;
        case OPT_MIPF: mipfStr = optarg; break;
        case OPT_LODMIN: lodMin = strtof(optarg, NULL); haveLodMin = YES; break;
        case OPT_LODMAX: lodMax = strtof(optarg, NULL); haveLodMax = YES; break;
        case OPT_ADDR: addrStr = optarg; break;
        case OPT_PARAMS: {
          char *dup = strdup(optarg); char *tok = strtok(dup, ",");
          while (tok && nParams < MAXPARAMS) {
            if (!strcmp(tok, "inf")) params[nParams] = INFINITY;
            else if (!strcmp(tok, "-inf")) params[nParams] = -INFINITY;
            else if (!strcmp(tok, "nan")) params[nParams] = NAN;
            else params[nParams] = strtof(tok, NULL);
            nParams++; tok = strtok(NULL, ",");
          }
          free(dup);
          break;
        }
        case OPT_VIEW_LEVELS: sscanf(optarg, "%ld,%ld", &viewLo, &viewHi); break;
        case OPT_READ_XY: sscanf(optarg, "%ld,%ld", &readX, &readY); break;
        case OPT_RT_SIZE: sscanf(optarg, "%ld,%ld", &rtW, &rtH); break;
        case OPT_NO_FM: fastMath = NO; break;
        default: fprintf(stderr, "usage: see header\n"); return 1;
      }
    }
    if (!srcPath || !vName || !fName) fail("PIPELINE_FAIL", "need --source --vertex --fragment", nil);

    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if (!dev) fail("PIPELINE_FAIL", "no Metal device", nil);
    printf("DEVICE %s\n", [[dev name] UTF8String]);

    NSError *err = nil;
    NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:srcPath]
                                               encoding:NSUTF8StringEncoding error:&err];
    if (!src) fail("COMPILE_FAIL", "read source", err);
    MTLCompileOptions *co = [MTLCompileOptions new];
    [co setFastMathEnabled:fastMath];
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:co error:&err];
    if (!lib) fail("COMPILE_FAIL", "newLibraryWithSource", err);
    id<MTLFunction> vf = [lib newFunctionWithName:[NSString stringWithUTF8String:vName]];
    id<MTLFunction> ff = [lib newFunctionWithName:[NSString stringWithUTF8String:fName]];
    if (!vf || !ff) fail("FUNCTION_MISSING", "newFunctionWithName", nil);

    MTLPixelFormat rtFormat = MTLPixelFormatR32Float;
    if (!strcmp(rtFormatStr, "rgba32float")) rtFormat = MTLPixelFormatRGBA32Float;
    else if (!strcmp(rtFormatStr, "r32float")) rtFormat = MTLPixelFormatR32Float;
    else if (!strcmp(rtFormatStr, "bgra8unorm")) rtFormat = MTLPixelFormatBGRA8Unorm;
    else fail("PIPELINE_FAIL", "bad --rt-format", nil);

    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = vf; pd.fragmentFunction = ff;
    pd.colorAttachments[0].pixelFormat = rtFormat;

    const char *pipelineSource = "source";
    id<MTLRenderPipelineState> pso = nil;
    if (archivePath) {
      MTLBinaryArchiveDescriptor *ad = [MTLBinaryArchiveDescriptor new];
      [ad setUrl:[NSURL fileURLWithPath:[NSString stringWithUTF8String:archivePath]]];
      id<MTLBinaryArchive> archive = [dev newBinaryArchiveWithDescriptor:ad error:&err];
      if (!archive) fail("ARCHIVE_FAIL", "newBinaryArchiveWithDescriptor", err);
      [pd setBinaryArchives:@[archive]];
      pso = [dev newRenderPipelineStateWithDescriptor:pd
                                               options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                            reflection:nil error:&err];
      if (!pso) fail("PIPELINE_MISS", "render pipeline (FailOnBinaryArchiveMiss)", err);
      pipelineSource = "archive";
    } else {
      pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err];
      if (!pso) fail("PIPELINE_FAIL", "newRenderPipelineStateWithDescriptor", err);
    }
    printf("PIPELINE_SOURCE %s\n", pipelineSource);

    // probe texture
    MTLPixelFormat texFormat = MTLPixelFormatR32Float;
    int texBpp = 4, texComps = 1;
    if (!strcmp(texFormatStr, "r32float")) { texFormat = MTLPixelFormatR32Float; texBpp = 4; texComps = 1; }
    else if (!strcmp(texFormatStr, "rgba8unorm")) { texFormat = MTLPixelFormatRGBA8Unorm; texBpp = 4; texComps = 4; }
    else fail("PIPELINE_FAIL", "bad --tex-format", nil);

    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:texFormat
                                                                                    width:(NSUInteger)texW
                                                                                   height:(NSUInteger)texH
                                                                                mipmapped:YES];
    td.mipmapLevelCount = (NSUInteger)texLevels;
    td.usage = MTLTextureUsageShaderRead;
    id<MTLTexture> tex0 = [dev newTextureWithDescriptor:td];
    for (long L = 0; L < texLevels; L++) {
      long w = texW >> L, h = texH >> L; if (w < 1) w = 1; if (h < 1) h = 1;
      if (texFormat == MTLPixelFormatR32Float) {
        float fillVal = lodRamp ? (float)L : (haveLevelFill[L] ? levelFill[L][0] : 0.0f);
        float *buf = malloc(sizeof(float) * (size_t)(w * h));
        for (long i = 0; i < w * h; i++) buf[i] = fillVal;
        [tex0 replaceRegion:MTLRegionMake2D(0,0,(NSUInteger)w,(NSUInteger)h) mipmapLevel:(NSUInteger)L
                   withBytes:buf bytesPerRow:(NSUInteger)(w * sizeof(float))];
        free(buf);
      } else {
        unsigned char rgba[4] = {0,0,0,255};
        if (haveLevelFill[L]) for (int k=0;k<4;k++) rgba[k] = (unsigned char)(levelFill[L][k]);
        unsigned char *buf = malloc(4 * (size_t)(w * h));
        for (long i = 0; i < w * h; i++) memcpy(buf + i*4, rgba, 4);
        [tex0 replaceRegion:MTLRegionMake2D(0,0,(NSUInteger)w,(NSUInteger)h) mipmapLevel:(NSUInteger)L
                   withBytes:buf bytesPerRow:(NSUInteger)(w * 4)];
        free(buf);
      }
    }
    id<MTLTexture> texUse = tex0;
    if (viewLo >= 0 && viewHi >= viewLo) {
      NSRange lv = NSMakeRange((NSUInteger)viewLo, (NSUInteger)(viewHi - viewLo + 1));
      NSRange sl = NSMakeRange(0, 1);
      texUse = [tex0 newTextureViewWithPixelFormat:texFormat textureType:MTLTextureType2D levels:lv slices:sl];
    }

    MTLSamplerDescriptor *sd = [MTLSamplerDescriptor new];
    sd.minFilter = !strcmp(minStr, "linear") ? MTLSamplerMinMagFilterLinear : MTLSamplerMinMagFilterNearest;
    sd.magFilter = !strcmp(magStr, "linear") ? MTLSamplerMinMagFilterLinear : MTLSamplerMinMagFilterNearest;
    if (!strcmp(mipfStr, "linear")) sd.mipFilter = MTLSamplerMipFilterLinear;
    else if (!strcmp(mipfStr, "notmipmapped")) sd.mipFilter = MTLSamplerMipFilterNotMipmapped;
    else sd.mipFilter = MTLSamplerMipFilterNearest;
    MTLSamplerAddressMode am = MTLSamplerAddressModeClampToEdge;
    if (!strcmp(addrStr, "repeat")) am = MTLSamplerAddressModeRepeat;
    else if (!strcmp(addrStr, "mirror")) am = MTLSamplerAddressModeMirrorRepeat;
    sd.sAddressMode = am; sd.tAddressMode = am; sd.rAddressMode = am;
    if (haveLodMin) sd.lodMinClamp = lodMin;
    if (haveLodMax) sd.lodMaxClamp = lodMax;
    id<MTLSamplerState> samp = [dev newSamplerStateWithDescriptor:sd];

    // render target
    MTLTextureDescriptor *rtd = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:rtFormat
                                                                                     width:(NSUInteger)rtW
                                                                                    height:(NSUInteger)rtH
                                                                                 mipmapped:NO];
    rtd.usage = MTLTextureUsageRenderTarget; rtd.storageMode = MTLStorageModeShared;
    id<MTLTexture> target = [dev newTextureWithDescriptor:rtd];

    id<MTLBuffer> pbuf = nil;
    if (nParams > 0) {
      pbuf = [dev newBufferWithBytes:params length:(NSUInteger)(nParams * sizeof(float))
                              options:MTLResourceStorageModeShared];
    } else {
      float zero = 0.0f;
      pbuf = [dev newBufferWithBytes:&zero length:4 options:MTLResourceStorageModeShared];
    }

    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
    rp.colorAttachments[0].texture = target;
    rp.colorAttachments[0].loadAction = MTLLoadActionClear;
    rp.colorAttachments[0].clearColor = MTLClearColorMake(0,0,0,0);
    rp.colorAttachments[0].storeAction = MTLStoreActionStore;

    id<MTLCommandQueue> q = [dev newCommandQueue];
    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    [enc setFragmentTexture:texUse atIndex:0];
    [enc setFragmentSamplerState:samp atIndex:0];
    [enc setFragmentBuffer:pbuf offset:0 atIndex:0];
    [enc setVertexBuffer:pbuf offset:0 atIndex:0];
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    if ([cb status] == MTLCommandBufferStatusError) fail("CMDBUF_ERROR", "command buffer failed", [cb error]);

    if (readX < 0 || readX >= rtW) readX = 0;
    if (readY < 0 || readY >= rtH) readY = 0;

    if (rtFormat == MTLPixelFormatBGRA8Unorm) {
      unsigned char *px = malloc((size_t)(rtW * rtH * 4));
      [target getBytes:px bytesPerRow:(NSUInteger)(rtW * 4)
             fromRegion:MTLRegionMake2D(0,0,(NSUInteger)rtW,(NSUInteger)rtH) mipmapLevel:0];
      unsigned char *p = px + (readY * rtW + readX) * 4;
      printf("PIXEL r=%.9g g=%.9g b=%.9g a=%.9g\n", p[2]/255.0, p[1]/255.0, p[0]/255.0, p[3]/255.0);
      free(px);
    } else {
      int nc = (rtFormat == MTLPixelFormatRGBA32Float) ? 4 : 1;
      float *px = malloc((size_t)(rtW * rtH * nc) * sizeof(float));
      [target getBytes:px bytesPerRow:(NSUInteger)(rtW * nc * sizeof(float))
             fromRegion:MTLRegionMake2D(0,0,(NSUInteger)rtW,(NSUInteger)rtH) mipmapLevel:0];
      float *p = px + (readY * rtW + readX) * nc;
      if (nc == 1) printf("PIXEL r=%.9g g=0 b=0 a=1\n", p[0]);
      else printf("PIXEL r=%.9g g=%.9g b=%.9g a=%.9g\n", p[0], p[1], p[2], p[3]);
      free(px);
    }
    emit_status("OK");
    fflush(stdout);
    return 0;
  }
}
