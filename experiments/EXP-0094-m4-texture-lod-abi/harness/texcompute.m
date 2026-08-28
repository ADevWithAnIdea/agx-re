// texcompute.m -- EXP-0094 generic compute-pipeline texture-gradient probe harness.
//
// Compute-side sibling of texrender.m: compiles OUR OWN MSL (public
// newLibraryWithSource:), OR -- when --archive is given -- forces a possibly
// byte-spliced compute pipeline FROM OUR OWN precompiled archive
// (MTLPipelineOptionFailOnBinaryArchiveMiss, same technique as
// tools/agxtest/agxrun.m), dispatches ONE thread, and reads back an output
// float buffer. Used for every explicit-gradient backend (gradient2d/
// gradientcube do not need a rasterizer or implicit derivatives -- a single
// compute thread is the smallest possible probe).
//
//   texture(0) = a 2D or CUBE texture. 2D: --tex-levels mip levels, each
//                either --tex-lodramp (constant float(level), for the
//                LOD-recovery trick) or a per-level solid RGBA
//                (--tex-level L=R,G,B,A). CUBE: --tex-cube, level 0 only,
//                each of the 6 faces filled independently
//                (--tex-face F=R,G,B,A, F=0..5 in Metal's
//                +X,-X,+Y,-Y,+Z,-Z slice order) OR --tex-lodramp for a
//                cube LOD-recovery texture (every face/level = float(level),
//                --tex-levels mip levels).
//   sampler(0)  = configurable filter/address/lod-clamp, as texrender.m.
//   buffer(0)   = constant float* params (raw floats from --params).
//   buffer(1)   = device float* out (zero-initialized, --out-count floats);
//                 the kernel writes whatever it wants to report.
//
// CLEAN-ROOM: public Metal API on OUR OWN compiled MSL only (source path), or
// OUR OWN previously-extracted-and-spliced AGX bytes forced to run via a Metal
// binary archive (archive path). No Apple binary is disassembled either way.
//
// Build:
//   clang -fobjc-arc -framework Metal -framework Foundation -o texcompute texcompute.m
//
// Stdout protocol:
//   STATUS OK|COMPILE_FAIL|FUNCTION_MISSING|ARCHIVE_FAIL|PIPELINE_MISS|PIPELINE_FAIL|CMDBUF_ERROR
//   DEVICE <name>
//   PIPELINE_SOURCE source|archive
//   OUT <n> v0 v1 ... v(n-1)          (exact float32 out[] contents)
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

enum { OPT_ARCHIVE = 128, OPT_SPLICE, OPT_TEX_FORMAT, OPT_TEX_SIZE, OPT_TEX_LEVELS,
       OPT_TEX_LEVEL, OPT_TEX_LODRAMP, OPT_TEX_CUBE, OPT_TEX_FACE, OPT_MIN, OPT_MAG,
       OPT_MIPF, OPT_LODMIN, OPT_LODMAX, OPT_ADDR, OPT_PARAMS, OPT_VIEW_LEVELS,
       OPT_OUT_COUNT, OPT_NO_FM };

static const struct option lo[] = {
    {"source", required_argument, 0, 's'}, {"function", required_argument, 0, 'k'},
    {"archive", required_argument, 0, OPT_ARCHIVE}, {"splice", required_argument, 0, OPT_SPLICE},
    {"tex-format", required_argument, 0, OPT_TEX_FORMAT}, {"tex-size", required_argument, 0, OPT_TEX_SIZE},
    {"tex-levels", required_argument, 0, OPT_TEX_LEVELS}, {"tex-level", required_argument, 0, OPT_TEX_LEVEL},
    {"tex-lodramp", no_argument, 0, OPT_TEX_LODRAMP}, {"tex-cube", no_argument, 0, OPT_TEX_CUBE},
    {"tex-face", required_argument, 0, OPT_TEX_FACE}, {"sampler-min", required_argument, 0, OPT_MIN},
    {"sampler-mag", required_argument, 0, OPT_MAG}, {"sampler-mipfilter", required_argument, 0, OPT_MIPF},
    {"sampler-lodmin", required_argument, 0, OPT_LODMIN}, {"sampler-lodmax", required_argument, 0, OPT_LODMAX},
    {"sampler-address", required_argument, 0, OPT_ADDR}, {"params", required_argument, 0, OPT_PARAMS},
    {"view-levels", required_argument, 0, OPT_VIEW_LEVELS}, {"out-count", required_argument, 0, OPT_OUT_COUNT},
    {"no-fast-math", no_argument, 0, OPT_NO_FM}, {0, 0, 0, 0}
};

#define MAXSPLICE 32
#define MAXLEVELS 16
#define MAXPARAMS 64

int main(int argc, char **argv) {
  @autoreleasepool {
    const char *srcPath = NULL, *fnName = NULL, *archivePath = NULL;
    const char *spliceArgs[MAXSPLICE]; int nSplice = 0; (void)spliceArgs; (void)nSplice;
    const char *texFormatStr = "r32float";
    long texW = 256, texH = 256, texLevels = 9;
    int haveLevelFill[MAXLEVELS]; float levelFill[MAXLEVELS][4];
    memset(haveLevelFill, 0, sizeof(haveLevelFill));
    int haveFaceFill[6]; float faceFill[6][4];
    memset(haveFaceFill, 0, sizeof(haveFaceFill));
    BOOL lodRamp = NO, isCube = NO;
    const char *minStr = "nearest", *magStr = "nearest", *mipfStr = "linear", *addrStr = "clamp";
    float lodMin = 0.0f, lodMax = 1000.0f; BOOL haveLodMin = NO, haveLodMax = NO;
    float params[MAXPARAMS]; int nParams = 0;
    long viewLo = -1, viewHi = -1;
    long outCount = 4;
    BOOL fastMath = YES;
    int c;
    while ((c = getopt_long(argc, argv, "s:k:", lo, NULL)) > 0) {
      switch (c) {
        case 's': srcPath = optarg; break;
        case 'k': fnName = optarg; break;
        case OPT_ARCHIVE: archivePath = optarg; break;
        case OPT_SPLICE: if (nSplice < MAXSPLICE) spliceArgs[nSplice++] = optarg; break;
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
        case OPT_TEX_CUBE: isCube = YES; break;
        case OPT_TEX_FACE: {
          int F; float r,g,b,a;
          if (sscanf(optarg, "%d=%f,%f,%f,%f", &F, &r, &g, &b, &a) == 5 && F >= 0 && F < 6) {
            haveFaceFill[F] = 1; faceFill[F][0]=r; faceFill[F][1]=g; faceFill[F][2]=b; faceFill[F][3]=a;
          }
          break;
        }
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
        case OPT_OUT_COUNT: outCount = strtol(optarg, NULL, 0); break;
        case OPT_NO_FM: fastMath = NO; break;
        default: fprintf(stderr, "usage: see header\n"); return 1;
      }
    }
    if (!srcPath || !fnName) fail("PIPELINE_FAIL", "need --source --function", nil);

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
    id<MTLFunction> fn = [lib newFunctionWithName:[NSString stringWithUTF8String:fnName]];
    if (!fn) fail("FUNCTION_MISSING", "newFunctionWithName", nil);

    const char *pipelineSource = "source";
    id<MTLComputePipelineState> pso = nil;
    if (archivePath) {
      MTLBinaryArchiveDescriptor *ad = [MTLBinaryArchiveDescriptor new];
      [ad setUrl:[NSURL fileURLWithPath:[NSString stringWithUTF8String:archivePath]]];
      id<MTLBinaryArchive> archive = [dev newBinaryArchiveWithDescriptor:ad error:&err];
      if (!archive) fail("ARCHIVE_FAIL", "newBinaryArchiveWithDescriptor", err);
      MTLComputePipelineDescriptor *cpd = [MTLComputePipelineDescriptor new];
      cpd.computeFunction = fn;
      cpd.binaryArchives = @[archive];
      pso = [dev newComputePipelineStateWithDescriptor:cpd
                                                 options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                              reflection:nil error:&err];
      if (!pso) fail("PIPELINE_MISS", "compute pipeline (FailOnBinaryArchiveMiss)", err);
      pipelineSource = "archive";
    } else {
      pso = [dev newComputePipelineStateWithFunction:fn error:&err];
      if (!pso) fail("PIPELINE_FAIL", "newComputePipelineStateWithFunction", err);
    }
    printf("PIPELINE_SOURCE %s\n", pipelineSource);

    MTLPixelFormat texFormat = MTLPixelFormatR32Float;
    if (!strcmp(texFormatStr, "r32float")) texFormat = MTLPixelFormatR32Float;
    else if (!strcmp(texFormatStr, "rgba8unorm")) texFormat = MTLPixelFormatRGBA8Unorm;
    else fail("PIPELINE_FAIL", "bad --tex-format", nil);

    id<MTLTexture> tex0 = nil;
    if (isCube) {
      MTLTextureDescriptor *td = [MTLTextureDescriptor textureCubeDescriptorWithPixelFormat:texFormat
                                                                                          size:(NSUInteger)texW
                                                                                     mipmapped:(texLevels > 1)];
      td.mipmapLevelCount = (NSUInteger)texLevels;
      td.usage = MTLTextureUsageShaderRead;
      tex0 = [dev newTextureWithDescriptor:td];
      for (int F = 0; F < 6; F++) {
        for (long L = 0; L < texLevels; L++) {
          long w = texW >> L, h = texW >> L; if (w < 1) w = 1; if (h < 1) h = 1;
          if (texFormat == MTLPixelFormatR32Float) {
            float fillVal = lodRamp ? (float)L : (haveFaceFill[F] ? faceFill[F][0] : 0.0f);
            float *buf = malloc(sizeof(float) * (size_t)(w * h));
            for (long i = 0; i < w * h; i++) buf[i] = fillVal;
            [tex0 replaceRegion:MTLRegionMake2D(0,0,(NSUInteger)w,(NSUInteger)h) mipmapLevel:(NSUInteger)L
                           slice:(NSUInteger)F withBytes:buf bytesPerRow:(NSUInteger)(w*sizeof(float))
                     bytesPerImage:0];
            free(buf);
          } else {
            unsigned char rgba[4] = {0,0,0,255};
            if (haveFaceFill[F]) for (int k=0;k<4;k++) rgba[k] = (unsigned char)(faceFill[F][k]);
            unsigned char *buf = malloc(4 * (size_t)(w * h));
            for (long i = 0; i < w * h; i++) memcpy(buf + i*4, rgba, 4);
            [tex0 replaceRegion:MTLRegionMake2D(0,0,(NSUInteger)w,(NSUInteger)h) mipmapLevel:(NSUInteger)L
                           slice:(NSUInteger)F withBytes:buf bytesPerRow:(NSUInteger)(w*4) bytesPerImage:0];
            free(buf);
          }
        }
      }
    } else {
      MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:texFormat
                                                                                      width:(NSUInteger)texW
                                                                                     height:(NSUInteger)texH
                                                                                  mipmapped:YES];
      td.mipmapLevelCount = (NSUInteger)texLevels;
      td.usage = MTLTextureUsageShaderRead;
      tex0 = [dev newTextureWithDescriptor:td];
      for (long L = 0; L < texLevels; L++) {
        long w = texW >> L, h = texH >> L; if (w < 1) w = 1; if (h < 1) h = 1;
        if (texFormat == MTLPixelFormatR32Float) {
          float fillVal = lodRamp ? (float)L : (haveLevelFill[L] ? levelFill[L][0] : 0.0f);
          float *buf = malloc(sizeof(float) * (size_t)(w * h));
          for (long i = 0; i < w * h; i++) buf[i] = fillVal;
          [tex0 replaceRegion:MTLRegionMake2D(0,0,(NSUInteger)w,(NSUInteger)h) mipmapLevel:(NSUInteger)L
                     withBytes:buf bytesPerRow:(NSUInteger)(w*sizeof(float))];
          free(buf);
        } else {
          unsigned char rgba[4] = {0,0,0,255};
          if (haveLevelFill[L]) for (int k=0;k<4;k++) rgba[k] = (unsigned char)(levelFill[L][k]);
          unsigned char *buf = malloc(4 * (size_t)(w * h));
          for (long i = 0; i < w * h; i++) memcpy(buf + i*4, rgba, 4);
          [tex0 replaceRegion:MTLRegionMake2D(0,0,(NSUInteger)w,(NSUInteger)h) mipmapLevel:(NSUInteger)L
                     withBytes:buf bytesPerRow:(NSUInteger)(w*4)];
          free(buf);
        }
      }
    }
    id<MTLTexture> texUse = tex0;
    if (!isCube && viewLo >= 0 && viewHi >= viewLo) {
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

    id<MTLBuffer> pbuf = nil;
    if (nParams > 0)
      pbuf = [dev newBufferWithBytes:params length:(NSUInteger)(nParams * sizeof(float))
                              options:MTLResourceStorageModeShared];
    else { float z = 0; pbuf = [dev newBufferWithBytes:&z length:4 options:MTLResourceStorageModeShared]; }

    id<MTLBuffer> outBuf = [dev newBufferWithLength:(NSUInteger)(outCount * (long)sizeof(float))
                                             options:MTLResourceStorageModeShared];
    memset([outBuf contents], 0, (size_t)(outCount * (long)sizeof(float)));

    id<MTLCommandQueue> q = [dev newCommandQueue];
    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
    [enc setComputePipelineState:pso];
    [enc setTexture:texUse atIndex:0];
    [enc setSamplerState:samp atIndex:0];
    [enc setBuffer:pbuf offset:0 atIndex:0];
    [enc setBuffer:outBuf offset:0 atIndex:1];
    [enc dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    if ([cb status] == MTLCommandBufferStatusError) fail("CMDBUF_ERROR", "command buffer failed", [cb error]);

    float *o = (float *)[outBuf contents];
    printf("OUT %ld", outCount);
    for (long i = 0; i < outCount; i++) printf(" %.9g", o[i]);
    printf("\n");
    emit_status("OK");
    fflush(stdout);
    return 0;
  }
}
