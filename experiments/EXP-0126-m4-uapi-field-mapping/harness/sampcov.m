// sampcov.m — EXP-0126 probe A: hardware-consumer coverage test for programmable
// MSAA sample positions.
//
// PURPOSE. EXP-0021/RT-4/RT-11/EXP-M4-03 all located custom sample positions inside a
// CLIENT BO (via DATA-TRACE byte capture) and showed the captured f32 pairs equal the
// requested positions snapped to a 1/16 grid. None of them proved the RASTERIZER actually
// CONSUMES those bytes -- i.e. that the position written into the BO is the position the
// hardware places the sample at during coverage testing. This harness closes that gap with
// a genuine HW-PROBE: it renders a single-pixel MSAA surface, sweeps a rectangle's right
// edge across the pixel in fine NDC steps, and reads back the RAW per-sample stored color
// (texture2d_ms::read(coord, sample)) via a compute kernel -- not the resolved/averaged
// color. Sample K is "covered" (alpha=1) iff its true position.x < edge; else alpha=0.
// Sweeping the edge and finding the exact flip point measures where the hardware ACTUALLY
// placed sample 0, independent of any captured-BO byte interpretation.
//
// This also gives an exact-implementation boundary test: --p0x/--p0y accept values at and
// past Metal's documented valid range [0.0, 0.9375] (16 lines: 0/16 .. 15/16, plus explicit
// invalid probes) and the harness reports Metal's exact acceptance/rejection behavior via
// NSException catch, distinguishing "API-level reject" from "silent clamp" (visible in the
// coverage readback if the effective position differs from the request).
//
// CLEAN-ROOM: OWN-SHADER + public Metal API (HW-PROBE). No Apple binary introspected.
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o sampcov sampcov.m
//
// Usage: sampcov --p0x F --p0y F --edgex F [--refx F] [--samples 2|4] [--case NAME]
//   Prints: DEVICE, CONFIG, POSAPPLY (ok|exception:<reason>), SUBMIT status=N,
//           SAMPLES a0 a1 a2 a3 (raw alpha per sample, -1.0 if not applicable)

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv) {
  @autoreleasepool {
    double p0x = 0.5, p0y = 0.5, edgex = 0.5, refx = 0.99;
    long samples = 4;
    const char *casename = "unnamed";
    for (int i = 1; i < argc; i++) {
      if (!strcmp(argv[i], "--p0x") && i + 1 < argc) p0x = strtod(argv[++i], 0);
      else if (!strcmp(argv[i], "--p0y") && i + 1 < argc) p0y = strtod(argv[++i], 0);
      else if (!strcmp(argv[i], "--edgex") && i + 1 < argc) edgex = strtod(argv[++i], 0);
      else if (!strcmp(argv[i], "--refx") && i + 1 < argc) refx = strtod(argv[++i], 0);
      else if (!strcmp(argv[i], "--samples") && i + 1 < argc) samples = strtol(argv[++i], 0, 0);
      else if (!strcmp(argv[i], "--case") && i + 1 < argc) casename = argv[++i];
    }

    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if (!dev) { printf("DEVICE_FAIL\n"); return 2; }
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("CASE %s\n", casename);
    printf("CONFIG samples=%ld p0=(%.6f,%.6f) refx=%.6f edgex=%.6f\n", samples, p0x, p0y, refx, edgex);

    NSString *vs =
        @"#include <metal_stdlib>\nusing namespace metal;\n"
        "struct V{float4 p [[position]];};\n"
        "vertex V vm(uint vid [[vertex_id]], const device float2* q [[buffer(0)]]){\n"
        "  V o; o.p=float4(q[vid],0,1); return o; }\n";
    NSString *fs =
        @"#include <metal_stdlib>\nusing namespace metal;\n"
        "struct V{float4 p [[position]];};\n"
        "fragment float4 fm(V in [[stage_in]]){ return float4(1,1,1,1); }\n";
    NSString *cs =
        @"#include <metal_stdlib>\nusing namespace metal;\n"
        "kernel void readms(texture2d_ms<float, access::read> tex [[texture(0)]],\n"
        "                    device float4* out [[buffer(0)]]) {\n"
        "  uint n = tex.get_num_samples();\n"
        "  for (uint s = 0; s < n && s < 4; s++) out[s] = tex.read(uint2(0,0), s);\n"
        "}\n";

    NSError *err = nil;
    id<MTLLibrary> vl = [dev newLibraryWithSource:vs options:nil error:&err];
    id<MTLLibrary> fl = [dev newLibraryWithSource:fs options:nil error:&err];
    id<MTLLibrary> cl = [dev newLibraryWithSource:cs options:nil error:&err];
    if (!vl || !fl || !cl) { printf("SHADER_FAIL %s\n", [[err localizedDescription] UTF8String]); return 3; }

    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = [vl newFunctionWithName:@"vm"];
    pd.fragmentFunction = [fl newFunctionWithName:@"fm"];
    pd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
    pd.rasterSampleCount = (NSUInteger)samples;
    id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err];
    if (!pso) { printf("PIPELINE_FAIL %s\n", [[err localizedDescription] UTF8String]); return 4; }

    id<MTLComputePipelineState> cpso = [dev newComputePipelineStateWithFunction:[cl newFunctionWithName:@"readms"] error:&err];
    if (!cpso) { printf("COMPUTE_PIPELINE_FAIL %s\n", [[err localizedDescription] UTF8String]); return 5; }

    long W = 1, H = 1;
    MTLTextureDescriptor *md = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:W height:H mipmapped:NO];
    md.textureType = MTLTextureType2DMultisample;
    md.sampleCount = (NSUInteger)samples;
    md.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
    md.storageMode = MTLStorageModePrivate;
    id<MTLTexture> msaa = [dev newTextureWithDescriptor:md];
    if (!msaa) { printf("TEXTURE_FAIL\n"); return 6; }

    id<MTLBuffer> vb = [dev newBufferWithLength:96 options:MTLResourceStorageModeShared];
    float *vp = (float *)[vb contents];
    double leftX = -1.0, rightX = -1.0 + 2.0 * edgex;
    // two CCW triangles forming rect [leftX,rightX] x [-1,1]
    vp[0] = leftX;  vp[1] = -1;  vp[2] = rightX; vp[3] = -1;  vp[4] = rightX; vp[5] = 1;
    vp[6] = leftX;  vp[7] = -1;  vp[8] = rightX; vp[9] = 1;   vp[10] = leftX; vp[11] = 1;

    id<MTLBuffer> outb = [dev newBufferWithLength:4 * 4 * sizeof(float) options:MTLResourceStorageModeShared];
    memset([outb contents], 0, 4 * 4 * sizeof(float));

    id<MTLCommandQueue> q = [dev newCommandQueue];
    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
    rp.colorAttachments[0].texture = msaa;
    rp.colorAttachments[0].loadAction = MTLLoadActionClear;
    rp.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 0);
    rp.colorAttachments[0].storeAction = MTLStoreActionStore;

    // Build the sample-position array: sample 0 = (p0x,p0y) under test; the rest are
    // reference positions pinned near x=refx (never covered by the sweeping left-anchored
    // rect until edgex approaches 1) so only sample 0's coverage is informative.
    NSUInteger n = (NSUInteger)samples;
    MTLSamplePosition pos[4];
    pos[0] = MTLSamplePositionMake(p0x, p0y);
    for (NSUInteger i = 1; i < n; i++) pos[i] = MTLSamplePositionMake(refx, 0.5 - 0.01 * (double)i);

    BOOL applyOK = YES;
    NSString *applyErr = nil;
    @try {
      [rp setSamplePositions:pos count:n];
    } @catch (NSException *e) {
      applyOK = NO;
      applyErr = [NSString stringWithFormat:@"%@: %@", e.name, e.reason];
    }
    printf("POSAPPLY %s\n", applyOK ? "ok" : [[NSString stringWithFormat:@"exception:%@", applyErr] UTF8String]);

    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    MTLViewport v = {0, 0, (double)W, (double)H, 0, 1};
    [enc setViewport:v];
    [enc setVertexBuffer:vb offset:0 atIndex:0];
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:6];
    [enc endEncoding];

    id<MTLComputeCommandEncoder> cenc = [cb computeCommandEncoder];
    [cenc setComputePipelineState:cpso];
    [cenc setTexture:msaa atIndex:0];
    [cenc setBuffer:outb offset:0 atIndex:0];
    [cenc dispatchThreads:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(1, 1, 1)];
    [cenc endEncoding];

    [cb commit];
    [cb waitUntilCompleted];
    long status = (long)[cb status];
    printf("SUBMIT status=%ld error=%s\n", status, cb.error ? [[cb.error localizedDescription] UTF8String] : "none");

    float *op = (float *)[outb contents];
    printf("SAMPLES");
    for (NSUInteger i = 0; i < 4; i++) {
      if (i < n) printf(" a%lu=%.6f", (unsigned long)i, op[i * 4 + 3]);
      else printf(" a%lu=-1.000000", (unsigned long)i);
    }
    printf("\n");
    return 0;
  }
}
