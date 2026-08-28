#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
int main(void) { @autoreleasepool {
    NSError *err=nil;
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    id<MTLCommandQueue> q = [dev newCommandQueue];
    NSString *src = [NSString stringWithContentsOfFile:@"kernels/split_negctrl.metal" encoding:NSUTF8StringEncoding error:&err];
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:[MTLCompileOptions new] error:&err];
    if (!lib) { printf("compile FAIL: %s\n", [[err localizedDescription] UTF8String]); return 1; }
    id<MTLFunction> vf = [lib newFunctionWithName:@"v_negctrl"];
    id<MTLFunction> ff = [lib newFunctionWithName:@"f_negctrl_caller"];
    MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
    rd.vertexFunction = vf; rd.fragmentFunction = ff;
    rd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA32Float;
    id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:rd error:&err];
    if (!pso) { printf("pipeline FAIL: %s\n", [[err localizedDescription] UTF8String]); return 1; }
    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:4 height:4 mipmapped:NO];
    td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
    id<MTLTexture> tex = [dev newTextureWithDescriptor:td];
    id<MTLCommandBuffer> cb = [q commandBuffer];
    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
    rp.colorAttachments[0].texture = tex;
    rp.colorAttachments[0].loadAction = MTLLoadActionClear;
    rp.colorAttachments[0].clearColor = MTLClearColorMake(0.11,0.22,0.33,0.44); // distinct clear = the tile-read "dst"
    rp.colorAttachments[0].storeAction = MTLStoreActionStore;
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [enc endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    if (cb.error) { printf("cmdbuf FAIL: %s\n", [[cb.error localizedDescription] UTF8String]); return 1; }
    float px[4];
    [tex getBytes:px bytesPerRow:16*4 fromRegion:MTLRegionMake2D(2,2,1,1) mipmapLevel:0];
    printf("readback: %.4f %.4f %.4f %.4f (expect ~= clear 0.11 0.22 0.33 0.44 if dst forwards correctly)\n", px[0],px[1],px[2],px[3]);
    return 0;
}}
