// gradsplice.m -- EXP-0114 own render-pipeline runner for the gradient-operand
// register-isolation HW splice validation. Modeled on (independently authored
// from, not copied from) the proven splice-and-reload render technique already
// used by tools/agxtest/agxrender.m and EXP-0094/harness/texrender.m: loads a
// (possibly byte-spliced, out-of-band) serialized Metal binary archive built
// by tools/shdump from OUR OWN MSL, forces the render pipeline to instantiate
// from the ARCHIVED machine code (MTLPipelineOptionFailOnBinaryArchiveMiss),
// binds a fixed 2-level DISCRETE-color (level0=red, level1=green) mip texture
// + a nearest-mipfilter sampler + an 8-float vertex/fragment param buffer,
// draws one full-screen triangle into a 1x1 BGRA8Unorm target, and reads back
// the pixel. Used to causally confirm which byte(s) select whether the
// gradient2d() operand read reflects the "gA" or "gB" register.
//
// CLEAN-ROOM: public Metal API only, on OUR OWN compiled+spliced shader bytes.
// No Apple binary is ever disassembled or introspected.
//
// Build:
//   clang -fobjc-arc -framework Metal -framework Foundation -o gradsplice gradsplice.m
//
// Usage:
//   gradsplice --archive A.bin --source S.metal --vertex vmain --fragment fmain \
//              --params f0,f1,...,f7 [--timeout SEC]
//
// Stdout protocol:
//   STATUS OK | COMPILE_FAIL | FUNCTION_MISSING | ARCHIVE_FAIL | PIPELINE_MISS |
//          PIPELINE_FAIL | CMDBUF_ERROR | CMDBUF_TIMEOUT
//   DEVICE <name>
//   PIPELINE_SOURCE archive
//   CMDBUF_STATUS <n>
//   PIXEL r=<f> g=<f> b=<f> a=<f>
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

enum { OPT_ARCHIVE = 128, OPT_PARAMS, OPT_TIMEOUT };
static const struct option lo[] = {
    {"archive",  required_argument, 0, OPT_ARCHIVE},
    {"source",   required_argument, 0, 's'},
    {"vertex",   required_argument, 0, 'v'},
    {"fragment", required_argument, 0, 'f'},
    {"params",   required_argument, 0, OPT_PARAMS},
    {"timeout",  required_argument, 0, OPT_TIMEOUT},
    {0, 0, 0, 0}
};

int main(int argc, char **argv) {
  @autoreleasepool {
    const char *srcPath = NULL, *vName = NULL, *fName = NULL, *archivePath = NULL;
    float params[8]; int nParams = 0;
    double timeoutSec = 20.0;
    int c;
    while ((c = getopt_long(argc, argv, "s:v:f:", lo, NULL)) > 0) {
      switch (c) {
        case 's': srcPath = optarg; break;
        case 'v': vName = optarg; break;
        case 'f': fName = optarg; break;
        case OPT_ARCHIVE: archivePath = optarg; break;
        case OPT_PARAMS: {
          char *dup = strdup(optarg); char *tok = strtok(dup, ",");
          while (tok && nParams < 8) { params[nParams++] = strtof(tok, NULL); tok = strtok(NULL, ","); }
          free(dup);
          break;
        }
        case OPT_TIMEOUT: timeoutSec = strtod(optarg, NULL); break;
        default: fprintf(stderr, "usage: see header\n"); return 1;
      }
    }
    if (!srcPath || !vName || !fName || !archivePath) fail("PIPELINE_FAIL", "need --source --vertex --fragment --archive", nil);
    while (nParams < 8) params[nParams++] = 0.0f;

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
    id<MTLFunction> vf = [lib newFunctionWithName:[NSString stringWithUTF8String:vName]];
    id<MTLFunction> ff = [lib newFunctionWithName:[NSString stringWithUTF8String:fName]];
    if (!vf || !ff) fail("FUNCTION_MISSING", "newFunctionWithName", nil);

    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = vf; pd.fragmentFunction = ff;
    pd.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;

    MTLBinaryArchiveDescriptor *ad = [MTLBinaryArchiveDescriptor new];
    [ad setUrl:[NSURL fileURLWithPath:[NSString stringWithUTF8String:archivePath]]];
    id<MTLBinaryArchive> archive = [dev newBinaryArchiveWithDescriptor:ad error:&err];
    if (!archive) fail("ARCHIVE_FAIL", "newBinaryArchiveWithDescriptor", err);
    [pd setBinaryArchives:@[archive]];
    id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:pd
                                       options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                       reflection:nil error:&err];
    if (!pso) fail("PIPELINE_MISS", "render pipeline (FailOnBinaryArchiveMiss)", err);
    printf("PIPELINE_SOURCE archive\n");

    // fixed 2-level 2x2 RGBA8Unorm oracle texture: level0=red, level1=green
    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm
                                                                                    width:2 height:2 mipmapped:YES];
    td.mipmapLevelCount = 2;
    td.usage = MTLTextureUsageShaderRead;
    id<MTLTexture> tex = [dev newTextureWithDescriptor:td];
    unsigned char red4[16]  = {255,0,0,255, 255,0,0,255, 255,0,0,255, 255,0,0,255};
    unsigned char green1[4] = {0,255,0,255};
    [tex replaceRegion:MTLRegionMake2D(0,0,2,2) mipmapLevel:0 withBytes:red4 bytesPerRow:8];
    [tex replaceRegion:MTLRegionMake2D(0,0,1,1) mipmapLevel:1 withBytes:green1 bytesPerRow:4];

    MTLSamplerDescriptor *sd = [MTLSamplerDescriptor new];
    sd.minFilter = MTLSamplerMinMagFilterNearest;
    sd.magFilter = MTLSamplerMinMagFilterNearest;
    sd.mipFilter = MTLSamplerMipFilterNearest;
    sd.sAddressMode = MTLSamplerAddressModeClampToEdge;
    sd.tAddressMode = MTLSamplerAddressModeClampToEdge;
    sd.lodMinClamp = 0.0f; sd.lodMaxClamp = 1000.0f;
    id<MTLSamplerState> samp = [dev newSamplerStateWithDescriptor:sd];

    MTLTextureDescriptor *rtd = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                                                                                     width:1 height:1 mipmapped:NO];
    rtd.usage = MTLTextureUsageRenderTarget; rtd.storageMode = MTLStorageModeShared;
    id<MTLTexture> target = [dev newTextureWithDescriptor:rtd];

    id<MTLBuffer> pbuf = [dev newBufferWithBytes:params length:sizeof(params) options:MTLResourceStorageModeShared];

    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
    rp.colorAttachments[0].texture = target;
    rp.colorAttachments[0].loadAction = MTLLoadActionClear;
    rp.colorAttachments[0].clearColor = MTLClearColorMake(0,0,0,0);
    rp.colorAttachments[0].storeAction = MTLStoreActionStore;

    id<MTLCommandQueue> q = [dev newCommandQueue];
    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    [enc setVertexBuffer:pbuf offset:0 atIndex:0];
    [enc setFragmentTexture:tex atIndex:0];
    [enc setFragmentSamplerState:samp atIndex:0];
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
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

    unsigned char px[4];
    [target getBytes:px bytesPerRow:4 fromRegion:MTLRegionMake2D(0,0,1,1) mipmapLevel:0];
    // BGRA8Unorm storage order: px[0]=B px[1]=G px[2]=R px[3]=A
    printf("PIXEL r=%.9g g=%.9g b=%.9g a=%.9g\n", px[2]/255.0, px[1]/255.0, px[0]/255.0, px[3]/255.0);
    emit_status("OK");
    return 0;
  }
}
