// sampcount.m — EXP-0126 probe B: boundary test for the render.samples UAPI leaf.
//
// PURPOSE. asahi_drm.h documents render.samples as "# of samples in the framebuffer.
// Must be 1, 2, or 4." (mesa/include/drm-uapi/asahi_drm.h:1053-1054). No prior experiment
// in this repository independently swept every boundary value (0,1,2,3,4,5,6,7,8,16) on
// M4 against BOTH the device's self-reported capability query
// (supportsTextureSampleCount:) AND actual texture/pipeline/draw construction. This
// harness does both and reports whether they agree, closing the "invalid values on M4"
// obligation in EXP-0045's field-matrix row for render.samples.
//
// CLEAN-ROOM: OWN-SHADER + public Metal API (HW-PROBE). No Apple binary introspected.
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o sampcount sampcount.m
//
// Usage: sampcount --count N
//   Prints: DEVICE, CONFIG count=N, CAPQUERY supported=0|1, TEXTURE ok|fail:<reason>,
//           PIPELINE ok|fail:<reason>, DRAW status=N|not_run, PIXEL r g b a|n/a

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv) {
  @autoreleasepool {
    long count = 4;
    for (int i = 1; i < argc; i++) {
      if (!strcmp(argv[i], "--count") && i + 1 < argc) count = strtol(argv[++i], 0, 0);
    }
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if (!dev) { printf("DEVICE_FAIL\n"); return 2; }
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("CONFIG count=%ld\n", count);

    BOOL cap = NO;
    if (count > 0) cap = [dev supportsTextureSampleCount:(NSUInteger)count];
    printf("CAPQUERY supported=%d\n", (int)cap);

    NSString *vs =
        @"#include <metal_stdlib>\nusing namespace metal;\n"
        "struct V{float4 p [[position]];};\n"
        "vertex V vm(uint vid [[vertex_id]], const device float2* q [[buffer(0)]]){\n"
        "  V o; o.p=float4(q[vid],0,1); return o; }\n";
    NSString *fs =
        @"#include <metal_stdlib>\nusing namespace metal;\n"
        "struct V{float4 p [[position]];};\n"
        "fragment float4 fm(V in [[stage_in]]){ return float4(0.2,0.4,0.6,1.0); }\n";
    NSError *err = nil;
    id<MTLLibrary> vl = [dev newLibraryWithSource:vs options:nil error:&err];
    id<MTLLibrary> fl = [dev newLibraryWithSource:fs options:nil error:&err];
    if (!vl || !fl) { printf("SHADER_FAIL %s\n", [[err localizedDescription] UTF8String]); return 3; }

    long W = 4, H = 4;
    id<MTLTexture> msaa = nil;
    BOOL texOK = NO;
    NSString *texErr = nil;
    @try {
      if (count < 1) @throw [NSException exceptionWithName:@"BadCount" reason:@"count<1, not attempted" userInfo:nil];
      MTLTextureDescriptor *md = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:W height:H mipmapped:NO];
      md.textureType = (count == 1) ? MTLTextureType2D : MTLTextureType2DMultisample;
      md.sampleCount = (NSUInteger)count;
      md.usage = MTLTextureUsageRenderTarget;
      md.storageMode = MTLStorageModePrivate;
      msaa = [dev newTextureWithDescriptor:md];
      texOK = (msaa != nil);
      if (!texOK) texErr = @"newTextureWithDescriptor returned nil";
    } @catch (NSException *e) {
      texOK = NO;
      texErr = [NSString stringWithFormat:@"%@: %@", e.name, e.reason];
    }
    printf("TEXTURE %s\n", texOK ? "ok" : [[NSString stringWithFormat:@"fail:%@", texErr] UTF8String]);

    id<MTLRenderPipelineState> pso = nil;
    BOOL pipeOK = NO;
    NSString *pipeErr = nil;
    if (texOK) {
      @try {
        MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
        pd.vertexFunction = [vl newFunctionWithName:@"vm"];
        pd.fragmentFunction = [fl newFunctionWithName:@"fm"];
        pd.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
        pd.rasterSampleCount = (NSUInteger)count;
        pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err];
        pipeOK = (pso != nil);
        if (!pipeOK) pipeErr = err ? [err localizedDescription] : @"nil, no NSError";
      } @catch (NSException *e) {
        pipeOK = NO;
        pipeErr = [NSString stringWithFormat:@"%@: %@", e.name, e.reason];
      }
    } else {
      pipeErr = @"skipped, texture creation failed";
    }
    printf("PIPELINE %s\n", pipeOK ? "ok" : [[NSString stringWithFormat:@"fail:%@", pipeErr] UTF8String]);

    if (!pipeOK) {
      printf("DRAW not_run\n");
      printf("PIXEL n/a\n");
      return 0;
    }

    NSUInteger bpr = ((W * 4 + 255) & ~255UL);
    id<MTLBuffer> resb = [dev newBufferWithLength:bpr * H options:MTLResourceStorageModeShared];
    MTLTextureDescriptor *rd = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:W height:H mipmapped:NO];
    rd.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
    rd.storageMode = MTLStorageModeShared;
    id<MTLTexture> resolve = [resb newTextureWithDescriptor:rd offset:0 bytesPerRow:bpr];

    id<MTLBuffer> vb = [dev newBufferWithLength:64 options:MTLResourceStorageModeShared];
    float *vp = (float *)[vb contents];
    vp[0] = -1; vp[1] = -1; vp[2] = 3; vp[3] = -1; vp[4] = -1; vp[5] = 3;

    id<MTLCommandQueue> q = [dev newCommandQueue];
    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
    rp.colorAttachments[0].texture = msaa;
    rp.colorAttachments[0].loadAction = MTLLoadActionClear;
    rp.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 1);
    if (count == 1) {
      rp.colorAttachments[0].storeAction = MTLStoreActionStore;
    } else {
      rp.colorAttachments[0].resolveTexture = resolve;
      rp.colorAttachments[0].storeAction = MTLStoreActionMultisampleResolve;
    }

    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    MTLViewport v = {0, 0, (double)W, (double)H, 0, 1};
    [enc setViewport:v];
    [enc setVertexBuffer:vb offset:0 atIndex:0];
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [enc endEncoding];

    if (count == 1) {
      // copy the private texture into a shared one for readback
      id<MTLBlitCommandEncoder> blit = [cb blitCommandEncoder];
      [blit copyFromTexture:msaa sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(W,H,1)
                   toTexture:resolve destinationSlice:0 destinationLevel:0 destinationOrigin:MTLOriginMake(0,0,0)];
      [blit endEncoding];
    }

    [cb commit];
    [cb waitUntilCompleted];
    long status = (long)[cb status];
    printf("DRAW status=%ld error=%s\n", status, cb.error ? [[cb.error localizedDescription] UTF8String] : "none");

    uint8_t *px = (uint8_t *)[resb contents];
    printf("PIXEL b=%u g=%u r=%u a=%u\n", px[0], px[1], px[2], px[3]);
    return 0;
  }
}
