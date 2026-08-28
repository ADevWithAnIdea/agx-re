// texsplice.m -- EXP-0114 own compute-pipeline runner with TEXTURE binding
// support (tools/agxtest/agxrun.m only supports buffers, not textures -- see
// its README; this is a small, purpose-built sibling for this experiment's
// texture-selector-field construction tests).
//
// Loads a (possibly byte-spliced, out-of-band) serialized Metal binary
// archive built by tools/shdump from OUR OWN MSL, forces the compute
// pipeline to instantiate from the ARCHIVED machine code
// (MTLPipelineOptionFailOnBinaryArchiveMiss -- same technique as
// tools/agxtest/agxrun.m and every prior HW-splice experiment in this repo),
// binds N single-texel r32uint textures with caller-supplied constant fill
// values, dispatches 1 thread, and dumps requested output buffers as hex.
//
// CLEAN-ROOM: public Metal API only, on OUR OWN compiled+possibly-spliced
// shader bytes (the archive is built by shdump from our own MSL; splicing is
// done out-of-band by our own python before this runs). No Apple binary is
// ever disassembled or introspected.
//
// Build:
//   clang -fobjc-arc -framework Metal -framework Foundation -o texsplice texsplice.m
//
// Usage:
//   texsplice --archive A.bin --source S.metal --function NAME \
//             --tex IDX=HEXVALUE [--tex IDX=HEXVALUE ...] \
//             --out IDX=NBYTES [--out IDX=NBYTES ...] [--run-timeout unused-here]
//
// Each --tex creates a 1x1 MTLPixelFormatR32Uint texture (access read),
// fills its single texel with the given 32-bit value, and binds it at
// [[texture(IDX)]]. Each --out requests an NBYTES-long device buffer bound
// at [[buffer(IDX)]] (zero-initialized to 0xEEEEEEEE per byte before dispatch
// so an untouched output is visibly distinguishable from a written zero).
//
// Stdout protocol (text; one field per line):
//   STATUS OK | COMPILE_FAIL | FUNCTION_MISSING | ARCHIVE_FAIL | PIPELINE_MISS |
//          PIPELINE_FAIL | CMDBUF_ERROR | CMDBUF_TIMEOUT
//   DEVICE <name>
//   PIPELINE_SOURCE archive
//   CMDBUF_STATUS <n>
//   OUT <idx> <hexbytes>
//   (on failure) ERROR <message>
// Exit status: 0 on STATUS OK, 1 otherwise.
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
static void fail(const char *st, const char *msg, NSError *e) {
    emit_status(st);
    if (e) printf("ERROR %s: %s\n", msg, [[e localizedDescription] UTF8String]);
    else if (msg) printf("ERROR %s\n", msg);
    fflush(stdout);
    exit(1);
}

enum { OPT_ARCHIVE = 128, OPT_TEX, OPT_OUT, OPT_TIMEOUT };
static const struct option lo[] = {
    {"archive",  required_argument, 0, OPT_ARCHIVE},
    {"source",   required_argument, 0, 's'},
    {"function", required_argument, 0, 'f'},
    {"tex",      required_argument, 0, OPT_TEX},
    {"out",      required_argument, 0, OPT_OUT},
    {"timeout",  required_argument, 0, OPT_TIMEOUT},
    {0, 0, 0, 0}
};

#define MAXTEX 8
#define MAXOUT 8

int main(int argc, char **argv) {
  @autoreleasepool {
    const char *srcPath = NULL, *fName = NULL, *archivePath = NULL;
    int texIdx[MAXTEX], nTex = 0; uint32_t texVal[MAXTEX];
    int outIdx[MAXOUT], outLen[MAXOUT], nOut = 0;
    double timeoutSec = 20.0;
    int c;
    while ((c = getopt_long(argc, argv, "s:f:", lo, NULL)) > 0) {
      switch (c) {
        case 's': srcPath = optarg; break;
        case 'f': fName = optarg; break;
        case OPT_ARCHIVE: archivePath = optarg; break;
        case OPT_TEX: {
          int idx; unsigned val;
          if (sscanf(optarg, "%d=%x", &idx, &val) == 2 && nTex < MAXTEX) { texIdx[nTex] = idx; texVal[nTex] = (uint32_t)val; nTex++; }
          break;
        }
        case OPT_OUT: {
          int idx, len;
          if (sscanf(optarg, "%d=%d", &idx, &len) == 2 && nOut < MAXOUT) { outIdx[nOut] = idx; outLen[nOut] = len; nOut++; }
          break;
        }
        case OPT_TIMEOUT: timeoutSec = strtod(optarg, NULL); break;
        default: fprintf(stderr, "usage: see header\n"); return 1;
      }
    }
    if (!srcPath || !fName || !archivePath) fail("PIPELINE_FAIL", "need --source --function --archive", nil);

    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if (!dev) fail("PIPELINE_FAIL", "no Metal device", nil);
    printf("DEVICE %s\n", [[dev name] UTF8String]);

    NSError *err = nil;
    NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:srcPath]
                                               encoding:NSUTF8StringEncoding error:&err];
    if (!src) fail("COMPILE_FAIL", "read source", err);
    MTLCompileOptions *co = [MTLCompileOptions new];
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:co error:&err];
    if (!lib) fail("COMPILE_FAIL", "newLibraryWithSource", err);
    id<MTLFunction> fn = [lib newFunctionWithName:[NSString stringWithUTF8String:fName]];
    if (!fn) fail("FUNCTION_MISSING", "newFunctionWithName", nil);

    MTLComputePipelineDescriptor *pd = [MTLComputePipelineDescriptor new];
    pd.computeFunction = fn;

    MTLBinaryArchiveDescriptor *ad = [MTLBinaryArchiveDescriptor new];
    [ad setUrl:[NSURL fileURLWithPath:[NSString stringWithUTF8String:archivePath]]];
    id<MTLBinaryArchive> archive = [dev newBinaryArchiveWithDescriptor:ad error:&err];
    if (!archive) fail("ARCHIVE_FAIL", "newBinaryArchiveWithDescriptor", err);
    [pd setBinaryArchives:@[archive]];
    id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithDescriptor:pd
                                        options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                        reflection:nil error:&err];
    if (!pso) fail("PIPELINE_MISS", "compute pipeline (FailOnBinaryArchiveMiss)", err);
    printf("PIPELINE_SOURCE archive\n");

    id<MTLTexture> texs[MAXTEX];
    for (int i = 0; i < nTex; i++) {
      MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR32Uint
                                                                                      width:1 height:1 mipmapped:NO];
      td.usage = MTLTextureUsageShaderRead;
      td.storageMode = MTLStorageModeShared;
      id<MTLTexture> t = [dev newTextureWithDescriptor:td];
      uint32_t v = texVal[i];
      [t replaceRegion:MTLRegionMake2D(0,0,1,1) mipmapLevel:0 withBytes:&v bytesPerRow:4];
      texs[i] = t;
    }

    id<MTLBuffer> outBufs[MAXOUT];
    for (int i = 0; i < nOut; i++) {
      id<MTLBuffer> b = [dev newBufferWithLength:(NSUInteger)outLen[i] options:MTLResourceStorageModeShared];
      memset([b contents], 0xEE, (size_t)outLen[i]);
      outBufs[i] = b;
    }

    id<MTLCommandQueue> q = [dev newCommandQueue];
    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
    [enc setComputePipelineState:pso];
    for (int i = 0; i < nTex; i++) [enc setTexture:texs[i] atIndex:(NSUInteger)texIdx[i]];
    for (int i = 0; i < nOut; i++) [enc setBuffer:outBufs[i] offset:0 atIndex:(NSUInteger)outIdx[i]];
    MTLSize grid = MTLSizeMake(1,1,1), tg = MTLSizeMake(1,1,1);
    [enc dispatchThreads:grid threadsPerThreadgroup:tg];
    [enc endEncoding];
    [cb commit];

    NSDate *deadline = [NSDate dateWithTimeIntervalSinceNow:timeoutSec];
    while ([cb status] != MTLCommandBufferStatusCompleted && [cb status] != MTLCommandBufferStatusError) {
      if ([[NSDate date] compare:deadline] == NSOrderedDescending) fail("CMDBUF_TIMEOUT", "wait exceeded timeout", nil);
      [NSThread sleepForTimeInterval:0.01];
    }
    printf("CMDBUF_STATUS %ld\n", (long)[cb status]);
    if ([cb status] == MTLCommandBufferStatusError) {
      NSError *cbe = [cb error];
      emit_status("CMDBUF_ERROR");
      if (cbe) printf("ERROR %s\n", [[cbe localizedDescription] UTF8String]);
      fflush(stdout);
      return 1;
    }

    for (int i = 0; i < nOut; i++) {
      unsigned char *p = (unsigned char *)[outBufs[i] contents];
      printf("OUT %d ", outIdx[i]);
      for (int k = 0; k < outLen[i]; k++) printf("%02x", p[k]);
      printf("\n");
    }
    emit_status("OK");
    return 0;
  }
}
