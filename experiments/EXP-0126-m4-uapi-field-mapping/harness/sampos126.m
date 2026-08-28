// sampos126.m — EXP-0126 probe A: M4 exhaustive-grid + off-grid-rounding DATA-TRACE
// probe for programmable MSAA sample positions (feeds render.ppp_multisamplectl).
//
// PURPOSE. RT-4/RT-11/EXP-M4-03 established (via DATA-TRACE capture of the client
// sample-pattern BO, `0x100000e8000`+0x40 for 4x / `0x100000e0000`+0x40 for 2x) that
// custom sample positions are written as N (x,y) f32 pairs, each coordinate snapped to a
// 1/16 grid. All prior M4 replication (EXP-M4-03) fed ALREADY-ON-GRID inputs, so the
// SNAP/ROUNDING RULE itself (what happens for an off-grid request) is HW-VALIDATED only
// on A18 (RT-4, historical, pre-hands-off) via 4 arbitrary off-grid points, never
// independently confirmed on M4, and never swept exhaustively across all 16 grid
// codepoints or the exact half-way rounding boundary.
//
// This harness: (1) sweeps sample 0's requested x position across all 16 grid points
//0/16..15/16 (exhaustive positive boundary coverage), and (2) sweeps a fine off-grid
// ladder around the 0/16-1/16 half-way point (0.03125) and around 1/16-2/16 (0.09375) to
// locate the exact rounding rule on M4. Sample 0 is the only varied slot; the remaining
// samples are pinned at a fixed distinguishable reference position so record 0 stays
// unambiguous at offset +0x40 regardless of sample count.
//
// CLEAN-ROOM: DATA-TRACE (tools/iotrace, read-only, run unmodified) + OWN-SHADER public
// Metal API. No Apple binary introspected. Command-buffer/BO bytes are our own process's
// non-copyrightable data crossing the userspace/kernel boundary.
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o sampos126 sampos126.m
//
// Usage: IOTRACE_DUMP_DIR=<dir> DYLD_INSERT_LIBRARIES=<path>/iotrace.dylib \
//        ./sampos126 --samples 4|2 --p0x F --p0y F [--case NAME]
//   Prints: DEVICE, CASE, CONFIG, POSAPPLY ok|exception, SUBMIT status=N, then triggers a
//   SIGUSR1 BO dump (same mechanism as tools/iotrace README / RT-11 sp11.m).

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

int main(int argc, char **argv) {
  @autoreleasepool {
    long samples = 4;
    double p0x = 0.5, p0y = 0.5;
    const char *casename = "unnamed";
    for (int i = 1; i < argc; i++) {
      if (!strcmp(argv[i], "--samples") && i + 1 < argc) samples = strtol(argv[++i], 0, 0);
      else if (!strcmp(argv[i], "--p0x") && i + 1 < argc) p0x = strtod(argv[++i], 0);
      else if (!strcmp(argv[i], "--p0y") && i + 1 < argc) p0y = strtod(argv[++i], 0);
      else if (!strcmp(argv[i], "--case") && i + 1 < argc) casename = argv[++i];
    }

    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if (!dev) { printf("DEVICE_FAIL\n"); return 2; }
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("CASE %s\n", casename);
    printf("CONFIG samples=%ld p0=(%.6f,%.6f)\n", samples, p0x, p0y);

    NSString *vs =
        @"#include <metal_stdlib>\nusing namespace metal;\n"
        "struct V{float4 p [[position]];};\n"
        "vertex V vm(uint vid [[vertex_id]], const device float2* q [[buffer(0)]]){ V o; o.p=float4(q[vid],0,1); return o; }\n";
    NSString *fs =
        @"#include <metal_stdlib>\nusing namespace metal;\n"
        "struct V{float4 p [[position]];};\n"
        "fragment float4 fm(V in [[stage_in]]){ return float4(0.2,0.4,0.6,1.0); }\n";
    NSError *err = nil;
    id<MTLLibrary> vl = [dev newLibraryWithSource:vs options:nil error:&err];
    id<MTLLibrary> fl = [dev newLibraryWithSource:fs options:nil error:&err];
    if (!vl || !fl) { printf("SHADER_FAIL %s\n", [[err localizedDescription] UTF8String]); return 3; }

    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = [vl newFunctionWithName:@"vm"];
    pd.fragmentFunction = [fl newFunctionWithName:@"fm"];
    pd.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
    pd.rasterSampleCount = (NSUInteger)samples;
    id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err];
    if (!pso) { printf("PIPELINE_FAIL %s\n", [[err localizedDescription] UTF8String]); return 4; }

    long W = 64, H = 64;
    MTLTextureDescriptor *md = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:W height:H mipmapped:NO];
    md.textureType = MTLTextureType2DMultisample;
    md.sampleCount = (NSUInteger)samples;
    md.usage = MTLTextureUsageRenderTarget;
    md.storageMode = MTLStorageModePrivate;
    id<MTLTexture> msaa = [dev newTextureWithDescriptor:md];

    MTLTextureDescriptor *rd = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:W height:H mipmapped:NO];
    rd.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
    rd.storageMode = MTLStorageModeShared;
    NSUInteger bpr = ((W * 4 + 255) & ~255UL);
    id<MTLBuffer> resb = [dev newBufferWithLength:bpr * H options:MTLResourceStorageModeShared];
    id<MTLTexture> resolve = [resb newTextureWithDescriptor:rd offset:0 bytesPerRow:bpr];

    id<MTLBuffer> vb = [dev newBufferWithLength:64 options:MTLResourceStorageModeShared];
    float *vp = (float *)[vb contents];
    vp[0] = -1; vp[1] = -1; vp[2] = 3; vp[3] = -1; vp[4] = -1; vp[5] = 3;
    printf("VA vtxBuf = 0x%016llx\n", (unsigned long long)[vb gpuAddress]);
    printf("VA resBuf = 0x%016llx\n", (unsigned long long)[resb gpuAddress]);

    id<MTLCommandQueue> q = [dev newCommandQueue];
    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
    rp.colorAttachments[0].texture = msaa;
    rp.colorAttachments[0].loadAction = MTLLoadActionClear;
    rp.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 1);
    rp.colorAttachments[0].resolveTexture = resolve;
    rp.colorAttachments[0].storeAction = MTLStoreActionMultisampleResolve;

    NSUInteger n = (NSUInteger)samples;
    MTLSamplePosition pos[4];
    pos[0] = MTLSamplePositionMake(p0x, p0y);
    // fixed, previously-uncontested reference positions distinct from the tested slot
    static const double refx[3] = {0.8125, 0.1875, 0.5625};
    static const double refy[3] = {0.1875, 0.8125, 0.5625};
    for (NSUInteger i = 1; i < n; i++) pos[i] = MTLSamplePositionMake(refx[i - 1], refy[i - 1]);

    BOOL applyOK = YES;
    NSString *applyErr = nil;
    @try {
      [rp setSamplePositions:pos count:n];
    } @catch (NSException *e) {
      applyOK = NO;
      applyErr = [NSString stringWithFormat:@"%@: %@", e.name, e.reason];
    }
    printf("POSAPPLY %s\n", applyOK ? "ok" : [[NSString stringWithFormat:@"exception:%@", applyErr] UTF8String]);
    if (!applyOK) { return 0; }

    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    MTLViewport v = {0, 0, (double)W, (double)H, 0, 1};
    [enc setViewport:v];
    [enc setVertexBuffer:vb offset:0 atIndex:0];
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    printf("SUBMIT status=%ld error=%s\n", (long)[cb status], cb.error ? [[cb.error localizedDescription] UTF8String] : "none");
    fflush(stdout);
    kill(getpid(), SIGUSR1);
    usleep(400000);
    return 0;
  }
}
