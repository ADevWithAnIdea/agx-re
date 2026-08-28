// fsrun.m -- EXP-0111 authored render+readback harness.
//
// Derived from experiments/EXP-0091-m4-fragment-sample-discard/harness/fsrun.m (OUR OWN
// authored code from a prior experiment in this repository -- not Apple code; reusing our
// own committed tooling across experiments is explicitly encouraged by SUBAGENT_BRIEF.md).
// That file was itself "a superset of tools/agxtest's agxrender.m capabilities" (MSAA,
// depth attachment+compare, occlusion query, N device buffers, checker textures). This
// version adds ONE new capability EXP-0091 did not need: a second and third color
// attachment (multiple render targets), needed to probe whether a dynamically-selected
// fragment OUTPUT can be lowered without a hardware dynamic-RT-selector (FS-11). Everything
// else is unchanged from EXP-0091's fsrun.m (same two modes: PLAIN compile, or SPLICE via
// --archive + MTLPipelineOptionFailOnBinaryArchiveMiss, identical to tools/agxtest's
// documented technique).
//
// CLEAN-ROOM: only the public Metal API on OUR OWN compiled shaders. No Apple binary is
// disassembled or introspected.
//
// Build:
//   clang -fobjc-arc -framework Metal -framework Foundation -o fsrun fsrun.m

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void emit_status(const char *s) { printf("STATUS %s\n", s); fflush(stdout); }
static void fail(const char *status, const char *msg, NSError *err) {
    emit_status(status);
    if (err)      printf("ERROR %s: %s\n", msg, [[err localizedDescription] UTF8String]);
    else if (msg) printf("ERROR %s\n", msg);
    if (fflush(NULL) != 0) { perror("fflush"); }
    if (ferror(stdout)) { fprintf(stderr, "stdout error\n"); }
    exit(1);
}

typedef struct { int idx; size_t size; unsigned char fill; } BufSpec;
typedef struct { int idx; unsigned n; unsigned *vals; } BufU32Spec;
typedef struct { size_t off; unsigned char *bytes; size_t len; } SpliceSpec;

int main(int argc, char *argv[]) {
  @autoreleasepool {
    const char *archivePath = NULL, *sourcePath = NULL, *vName = NULL, *fName = NULL;
    long W = 4, H = 4, samples = 1;
    int colorFormat = 80; // MTLPixelFormatBGRA8Unorm
    BOOL fastMath = YES;
    BOOL wantDepth = NO, wantOcclusion = NO, wantResolve = NO, wantTex = NO;
    float clearR=0,clearG=0,clearB=0,clearA=0;
    float depthClear = 0.5f;
    int depthCompare = 3; // MTLCompareFunctionLess
    BOOL depthWrite = YES;
    int rtCount = 1; // 1..3 color attachments (NEW vs EXP-0091)
    BufSpec bufs[8]; int nbufs = 0;
    BufU32Spec bufsu32[8]; int nbufsu32 = 0;
    SpliceSpec splices[16]; int nsplices = 0;
    int texIdx = -1; long texW=4, texH=4; BOOL texMip = NO;

    enum { OPT_ARCHIVE=256, OPT_SOURCE, OPT_VERTEX, OPT_FRAGMENT, OPT_WIDTH, OPT_HEIGHT,
           OPT_SAMPLES, OPT_COLORFMT, OPT_DEPTH, OPT_DEPTHCLEAR, OPT_DEPTHCMP, OPT_DEPTHWRITE,
           OPT_OCCLUSION, OPT_BUF, OPT_BUFU32, OPT_SPLICE, OPT_CLEAR, OPT_RESOLVE,
           OPT_NOFASTMATH, OPT_TEXCHECKER, OPT_TEXW, OPT_TEXH, OPT_TEXMIP, OPT_RTCOUNT };
    static struct option longOpts[] = {
      {"archive", required_argument, NULL, OPT_ARCHIVE},
      {"source", required_argument, NULL, OPT_SOURCE},
      {"vertex", required_argument, NULL, OPT_VERTEX},
      {"fragment", required_argument, NULL, OPT_FRAGMENT},
      {"width", required_argument, NULL, OPT_WIDTH},
      {"height", required_argument, NULL, OPT_HEIGHT},
      {"samples", required_argument, NULL, OPT_SAMPLES},
      {"color-format", required_argument, NULL, OPT_COLORFMT},
      {"depth", no_argument, NULL, OPT_DEPTH},
      {"depth-clear", required_argument, NULL, OPT_DEPTHCLEAR},
      {"depth-compare", required_argument, NULL, OPT_DEPTHCMP},
      {"depth-write", required_argument, NULL, OPT_DEPTHWRITE},
      {"occlusion", no_argument, NULL, OPT_OCCLUSION},
      {"buf", required_argument, NULL, OPT_BUF},
      {"buf-u32", required_argument, NULL, OPT_BUFU32},
      {"splice", required_argument, NULL, OPT_SPLICE},
      {"clear", required_argument, NULL, OPT_CLEAR},
      {"resolve", no_argument, NULL, OPT_RESOLVE},
      {"no-fast-math", no_argument, NULL, OPT_NOFASTMATH},
      {"tex-checker", required_argument, NULL, OPT_TEXCHECKER},
      {"tex-w", required_argument, NULL, OPT_TEXW},
      {"tex-h", required_argument, NULL, OPT_TEXH},
      {"tex-mip", no_argument, NULL, OPT_TEXMIP},
      {"rt-count", required_argument, NULL, OPT_RTCOUNT},
      {NULL,0,NULL,0}
    };
    int c;
    while ((c = getopt_long(argc, argv, "", longOpts, NULL)) != -1) {
      switch (c) {
        case OPT_ARCHIVE: archivePath = optarg; break;
        case OPT_SOURCE: sourcePath = optarg; break;
        case OPT_VERTEX: vName = optarg; break;
        case OPT_FRAGMENT: fName = optarg; break;
        case OPT_WIDTH: W = strtol(optarg,NULL,0); break;
        case OPT_HEIGHT: H = strtol(optarg,NULL,0); break;
        case OPT_SAMPLES: samples = strtol(optarg,NULL,0); break;
        case OPT_COLORFMT: colorFormat = (int)strtol(optarg,NULL,0); break;
        case OPT_DEPTH: wantDepth = YES; break;
        case OPT_DEPTHCLEAR: depthClear = strtof(optarg,NULL); break;
        case OPT_DEPTHCMP: depthCompare = (int)strtol(optarg,NULL,0); break;
        case OPT_DEPTHWRITE: depthWrite = strtol(optarg,NULL,0) != 0; break;
        case OPT_OCCLUSION: wantOcclusion = YES; break;
        case OPT_RESOLVE: wantResolve = YES; break;
        case OPT_NOFASTMATH: fastMath = NO; break;
        case OPT_TEXCHECKER: wantTex = YES; texIdx = (int)strtol(optarg,NULL,0); break;
        case OPT_TEXW: texW = strtol(optarg,NULL,0); break;
        case OPT_TEXH: texH = strtol(optarg,NULL,0); break;
        case OPT_TEXMIP: texMip = YES; break;
        case OPT_RTCOUNT: rtCount = (int)strtol(optarg,NULL,0); break;
        case OPT_CLEAR: sscanf(optarg, "%f,%f,%f,%f", &clearR,&clearG,&clearB,&clearA); break;
        case OPT_BUF: {
          int idx; long size; unsigned fillv = 0xAA;
          char extra[8] = {0};
          int n = sscanf(optarg, "%d=%ld,%2s", &idx, &size, extra);
          if (n >= 3) fillv = (unsigned)strtol(extra, NULL, 16);
          bufs[nbufs].idx = idx; bufs[nbufs].size = (size_t)size; bufs[nbufs].fill = (unsigned char)fillv;
          nbufs++;
          break;
        }
        case OPT_BUFU32: {
          int idx; char *rest = strchr(optarg, '=');
          if (!rest) { fprintf(stderr, "bad --buf-u32\n"); return 2; }
          idx = (int)strtol(optarg, NULL, 0);
          rest++;
          unsigned *vals = malloc(sizeof(unsigned) * 4096);
          unsigned n = 0;
          char *tok = strtok(rest, ",");
          while (tok) { vals[n++] = (unsigned)strtoul(tok, NULL, 0); tok = strtok(NULL, ","); }
          bufsu32[nbufsu32].idx = idx; bufsu32[nbufsu32].n = n; bufsu32[nbufsu32].vals = vals;
          nbufsu32++;
          break;
        }
        case OPT_SPLICE: {
          char *eq = strchr(optarg, '=');
          if (!eq) { fprintf(stderr, "bad --splice\n"); return 2; }
          size_t off = strtoul(optarg, NULL, 0);
          const char *hex = eq + 1;
          size_t hlen = strlen(hex);
          size_t blen = hlen / 2;
          unsigned char *bytes = malloc(blen);
          for (size_t i = 0; i < blen; i++) {
            unsigned int v; sscanf(hex + i*2, "%2x", &v); bytes[i] = (unsigned char)v;
          }
          splices[nsplices].off = off; splices[nsplices].bytes = bytes; splices[nsplices].len = blen;
          nsplices++;
          break;
        }
        default: fprintf(stderr, "unknown option\n"); return 2;
      }
    }
    if (!sourcePath || !vName || !fName) fail("PIPELINE_FAIL", "need --source --vertex --fragment", nil);
    if (rtCount < 1 || rtCount > 3) fail("PIPELINE_FAIL", "--rt-count must be 1..3", nil);

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
    id<MTLFunction> vfn = [lib newFunctionWithName:[NSString stringWithUTF8String:vName]];
    id<MTLFunction> ffn = [lib newFunctionWithName:[NSString stringWithUTF8String:fName]];
    if (!vfn || !ffn) fail("FUNCTION_MISSING", "newFunctionWithName", nil);

    MTLRenderPipelineDescriptor *pdesc = [MTLRenderPipelineDescriptor new];
    [pdesc setVertexFunction:vfn];
    [pdesc setFragmentFunction:ffn];
    for (int i = 0; i < rtCount; i++)
      pdesc.colorAttachments[i].pixelFormat = (MTLPixelFormat)colorFormat;
    pdesc.rasterSampleCount = (NSUInteger)samples;
    if (wantDepth) pdesc.depthAttachmentPixelFormat = MTLPixelFormatDepth32Float;

    id<MTLBinaryArchive> archive = nil;
    NSString *scratchArchivePath = nil;
    if (archivePath) {
      // Apply splices to a SCRATCH COPY of the archive file, byte-for-byte, at the
      // exact offsets given (from agxparse.py --locate). Never read/parse the
      // archive as a structure ourselves -- only raw fixed-offset byte patch.
      NSData *orig = [NSData dataWithContentsOfFile:[NSString stringWithUTF8String:archivePath]];
      if (!orig) fail("ARCHIVE_FAIL", "read archive", nil);
      NSMutableData *patched = [orig mutableCopy];
      for (int i = 0; i < nsplices; i++) {
        if (splices[i].off + splices[i].len > [patched length]) fail("ARCHIVE_FAIL", "splice OOB", nil);
        memcpy((unsigned char*)[patched mutableBytes] + splices[i].off, splices[i].bytes, splices[i].len);
      }
      // EXP-0126 CLEAN-ROOM/SAFETY FIX (vs. upstream EXP-0091/0111 fsrun.m): never write
      // outside the repo, not even to system /tmp (SUBAGENT_BRIEF.md, standing rule).
      // The scratch-spliced archive is written as a SIBLING of the caller-supplied
      // --archive path instead of NSTemporaryDirectory() -- the caller (this
      // experiment's harness) always passes a path inside its own work/ directory, so
      // this keeps 100% of on-disk output inside the repo.
      NSString *archivePathNS = [NSString stringWithUTF8String:archivePath];
      scratchArchivePath = [[archivePathNS stringByDeletingLastPathComponent]
                             stringByAppendingPathComponent:
                             [NSString stringWithFormat:@"fsrun_scratch_%d.bin", getpid()]];
      if (![patched writeToFile:scratchArchivePath atomically:YES]) fail("ARCHIVE_FAIL", "write scratch", nil);

      MTLBinaryArchiveDescriptor *adesc = [MTLBinaryArchiveDescriptor new];
      [adesc setUrl:[NSURL fileURLWithPath:scratchArchivePath]];
      archive = [dev newBinaryArchiveWithDescriptor:adesc error:&err];
      if (!archive) fail("ARCHIVE_FAIL", "newBinaryArchiveWithDescriptor", err);
      [pdesc setBinaryArchives:@[archive]];
    }

    id<MTLRenderPipelineState> pso;
    if (archive) {
      pso = [dev newRenderPipelineStateWithDescriptor:pdesc
                                               options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                            reflection:nil
                                                 error:&err];
      if (!pso) fail("PIPELINE_MISS", "newRenderPipelineStateWithDescriptor (archive)", err);
      printf("PIPELINE_SOURCE archive\n");
    } else {
      pso = [dev newRenderPipelineStateWithDescriptor:pdesc error:&err];
      if (!pso) fail("PIPELINE_FAIL", "newRenderPipelineStateWithDescriptor", err);
      printf("PIPELINE_SOURCE compiled\n");
    }

    id<MTLDepthStencilState> dss = nil;
    if (wantDepth) {
      MTLDepthStencilDescriptor *dd = [MTLDepthStencilDescriptor new];
      dd.depthCompareFunction = (MTLCompareFunction)depthCompare;
      dd.depthWriteEnabled = depthWrite;
      dss = [dev newDepthStencilStateWithDescriptor:dd];
    }

    id<MTLTexture> targets[3]; memset(targets, 0, sizeof(targets));
    for (int i = 0; i < rtCount; i++) {
      MTLTextureDescriptor *td =
        [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:(MTLPixelFormat)colorFormat
                                                            width:(NSUInteger)W height:(NSUInteger)H
                                                        mipmapped:NO];
      td.textureType = (samples > 1) ? MTLTextureType2DMultisample : MTLTextureType2D;
      td.sampleCount = (NSUInteger)samples;
      td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
      td.storageMode = (samples > 1) ? MTLStorageModePrivate : MTLStorageModeShared;
      targets[i] = [dev newTextureWithDescriptor:td];
    }
    id<MTLTexture> target = targets[0];

    id<MTLTexture> resolveTarget = nil;
    if (samples > 1 && wantResolve) {
      MTLTextureDescriptor *rtd =
        [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:(MTLPixelFormat)colorFormat
                                                            width:(NSUInteger)W height:(NSUInteger)H
                                                        mipmapped:NO];
      rtd.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
      rtd.storageMode = MTLStorageModeShared;
      resolveTarget = [dev newTextureWithDescriptor:rtd];
    }

    id<MTLTexture> depthTarget = nil;
    if (wantDepth) {
      MTLTextureDescriptor *ddsc =
        [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatDepth32Float
                                                            width:(NSUInteger)W height:(NSUInteger)H
                                                        mipmapped:NO];
      ddsc.textureType = (samples > 1) ? MTLTextureType2DMultisample : MTLTextureType2D;
      ddsc.sampleCount = (NSUInteger)samples;
      ddsc.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
      ddsc.storageMode = (samples > 1) ? MTLStorageModePrivate : MTLStorageModeShared;
      depthTarget = [dev newTextureWithDescriptor:ddsc];
    }

    id<MTLTexture> checkerTex = nil;
    id<MTLSamplerState> checkerSmp = nil;
    if (wantTex) {
      MTLTextureDescriptor *ctd =
        [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR8Unorm
                                                            width:(NSUInteger)texW height:(NSUInteger)texH
                                                        mipmapped:texMip];
      ctd.usage = MTLTextureUsageShaderRead;
      ctd.storageMode = MTLStorageModeShared;
      checkerTex = [dev newTextureWithDescriptor:ctd];
      NSUInteger mipCount = texMip ? checkerTex.mipmapLevelCount : 1;
      for (NSUInteger m = 0; m < mipCount; m++) {
        NSUInteger mw = MAX((NSUInteger)1, (NSUInteger)texW >> m);
        NSUInteger mh = MAX((NSUInteger)1, (NSUInteger)texH >> m);
        unsigned char *px = malloc(mw*mh);
        for (NSUInteger y = 0; y < mh; y++)
          for (NSUInteger x = 0; x < mw; x++)
            px[y*mw+x] = ((x+y) & 1) ? 220 : 40;
        [checkerTex replaceRegion:MTLRegionMake2D(0,0,mw,mh) mipmapLevel:m withBytes:px bytesPerRow:mw];
        free(px);
      }
      MTLSamplerDescriptor *sd = [MTLSamplerDescriptor new];
      sd.minFilter = MTLSamplerMinMagFilterLinear;
      sd.magFilter = MTLSamplerMinMagFilterLinear;
      sd.mipFilter = texMip ? MTLSamplerMipFilterLinear : MTLSamplerMipFilterNotMipmapped;
      sd.sAddressMode = MTLSamplerAddressModeRepeat;
      sd.tAddressMode = MTLSamplerAddressModeRepeat;
      checkerSmp = [dev newSamplerStateWithDescriptor:sd];
    }

    id<MTLBuffer> mtlbufs[8]; memset(mtlbufs, 0, sizeof(mtlbufs));
    for (int i = 0; i < nbufs; i++) {
      id<MTLBuffer> b = [dev newBufferWithLength:bufs[i].size options:MTLResourceStorageModeShared];
      memset([b contents], bufs[i].fill, bufs[i].size);
      mtlbufs[i] = b;
    }
    id<MTLBuffer> mtlbufsu32[8]; memset(mtlbufsu32, 0, sizeof(mtlbufsu32));
    for (int i = 0; i < nbufsu32; i++) {
      id<MTLBuffer> b = [dev newBufferWithLength:bufsu32[i].n*4 options:MTLResourceStorageModeShared];
      memcpy([b contents], bufsu32[i].vals, bufsu32[i].n*4);
      mtlbufsu32[i] = b;
    }

    id<MTLBuffer> visBuf = nil;
    if (wantOcclusion) {
      visBuf = [dev newBufferWithLength:8 options:MTLResourceStorageModeShared];
      memset([visBuf contents], 0, 8);
    }

    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
    for (int i = 0; i < rtCount; i++) {
      rp.colorAttachments[i].texture = targets[i];
      rp.colorAttachments[i].loadAction = MTLLoadActionClear;
      rp.colorAttachments[i].clearColor = MTLClearColorMake(clearR, clearG, clearB, clearA);
      if (i == 0 && samples > 1 && wantResolve) {
        rp.colorAttachments[0].resolveTexture = resolveTarget;
        rp.colorAttachments[0].storeAction = MTLStoreActionMultisampleResolve;
      } else {
        rp.colorAttachments[i].storeAction = MTLStoreActionStore;
      }
    }
    if (wantDepth) {
      rp.depthAttachment.texture = depthTarget;
      rp.depthAttachment.loadAction = MTLLoadActionClear;
      rp.depthAttachment.clearDepth = depthClear;
      rp.depthAttachment.storeAction = MTLStoreActionStore;
    }
    if (wantOcclusion) rp.visibilityResultBuffer = visBuf;

    id<MTLCommandQueue> queue = [dev newCommandQueue];
    id<MTLCommandBuffer> cb = [queue commandBuffer];
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    if (dss) [enc setDepthStencilState:dss];
    if (wantOcclusion) [enc setVisibilityResultMode:MTLVisibilityResultModeCounting offset:0];
    for (int i = 0; i < nbufs; i++) {
      [enc setFragmentBuffer:mtlbufs[i] offset:0 atIndex:bufs[i].idx];
      [enc setVertexBuffer:mtlbufs[i] offset:0 atIndex:bufs[i].idx];
    }
    for (int i = 0; i < nbufsu32; i++) {
      [enc setFragmentBuffer:mtlbufsu32[i] offset:0 atIndex:bufsu32[i].idx];
      [enc setVertexBuffer:mtlbufsu32[i] offset:0 atIndex:bufsu32[i].idx];
    }
    if (wantTex) {
      [enc setFragmentTexture:checkerTex atIndex:texIdx];
      [enc setFragmentSamplerState:checkerSmp atIndex:texIdx];
    }
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    if ([cb status] == MTLCommandBufferStatusError)
      fail("CMDBUF_ERROR", "command buffer failed", [cb error]);
    printf("GPUTIME_NS %llu\n", (unsigned long long)(([cb GPUEndTime] - [cb GPUStartTime]) * 1e9));

    printf("SIZE %ld %ld SAMPLES %ld\n", W, H, samples);
    for (int rt = 0; rt < rtCount; rt++) {
      id<MTLTexture> readTex = (rt == 0 && samples > 1 && wantResolve) ? resolveTarget
                                : ((samples > 1) ? nil : targets[rt]);
      if (readTex) {
        unsigned char *px = (unsigned char *)malloc((size_t)W * H * 4);
        [readTex getBytes:px bytesPerRow:(NSUInteger)(W * 4)
               fromRegion:MTLRegionMake2D(0, 0, (NSUInteger)W, (NSUInteger)H) mipmapLevel:0];
        for (long y = 0; y < H; y++)
          for (long x = 0; x < W; x++) {
            unsigned char *p = px + (y * W + x) * 4;
            printf("PIXEL%d %ld %ld bgra=%02x%02x%02x%02x rgba_unorm=%.4f,%.4f,%.4f,%.4f\n",
                   rt, x, y, p[0], p[1], p[2], p[3], p[2]/255.0, p[1]/255.0, p[0]/255.0, p[3]/255.0);
          }
        free(px);
      } else {
        printf("PIXEL%d_UNAVAILABLE raw-multisample-not-resolved\n", rt);
      }
    }

    if (wantDepth && samples == 1) {
      float *dpx = (float *)malloc((size_t)W * H * 4);
      [depthTarget getBytes:dpx bytesPerRow:(NSUInteger)(W * 4)
                 fromRegion:MTLRegionMake2D(0, 0, (NSUInteger)W, (NSUInteger)H) mipmapLevel:0];
      for (long y = 0; y < H; y++)
        for (long x = 0; x < W; x++)
          printf("DEPTH %ld %ld value=%.6f\n", x, y, dpx[y*W+x]);
      free(dpx);
    }

    if (wantOcclusion) {
      unsigned long long *v = (unsigned long long *)[visBuf contents];
      printf("OCCLUSION_COUNT %llu\n", v[0]);
    }

    for (int i = 0; i < nbufs; i++) {
      unsigned char *c = (unsigned char *)[mtlbufs[i] contents];
      printf("BUFFER %d hex=", bufs[i].idx);
      for (size_t k = 0; k < bufs[i].size; k++) printf("%02x", c[k]);
      printf("\n");
    }

    if (scratchArchivePath) [[NSFileManager defaultManager] removeItemAtPath:scratchArchivePath error:nil];

    emit_status("OK");
    if (fflush(NULL) != 0) { perror("fflush"); return 1; }
    if (ferror(stdout)) { fprintf(stderr, "stdout error\n"); return 1; }
    return 0;
  }
}
