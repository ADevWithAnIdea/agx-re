#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
int main() { @autoreleasepool {
    NSError *err=nil;
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    id<MTLCommandQueue> q = [dev newCommandQueue];
    NSString *src = [NSString stringWithContentsOfFile:@"work/supplementary/bary_diag4.metal" encoding:NSUTF8StringEncoding error:&err];
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:[MTLCompileOptions new] error:&err];
    if (!lib) { NSLog(@"compile fail %@", err); return 1; }
    id<MTLFunction> vf = [lib newFunctionWithName:@"v_bary"];
    id<MTLFunction> ff = [lib newFunctionWithName:@"f_bary"];
    const int W=64,H=64;
    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:W height:H mipmapped:NO];
    td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
    id<MTLTexture> rawtex = [dev newTextureWithDescriptor:td];
    id<MTLTexture> manualtex = [dev newTextureWithDescriptor:td];
    MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
    rd.vertexFunction=vf; rd.fragmentFunction=ff;
    rd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA32Float;
    rd.colorAttachments[1].pixelFormat = MTLPixelFormatRGBA32Float;
    id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:rd error:&err];
    if (!pso) { NSLog(@"pipeline fail %@", err); return 1; }
    float tags[3] = {10.0f,20.0f,30.0f};
    id<MTLBuffer> tbuf = [dev newBufferWithBytes:tags length:12 options:MTLResourceStorageModeShared];
    id<MTLCommandBuffer> cb = [q commandBuffer];
    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
    rp.colorAttachments[0].texture=rawtex; rp.colorAttachments[0].loadAction=MTLLoadActionClear;
    rp.colorAttachments[0].clearColor=MTLClearColorMake(-9,-9,-9,-9); rp.colorAttachments[0].storeAction=MTLStoreActionStore;
    rp.colorAttachments[1].texture=manualtex; rp.colorAttachments[1].loadAction=MTLLoadActionClear;
    rp.colorAttachments[1].clearColor=MTLClearColorMake(-9,-9,-9,-9); rp.colorAttachments[1].storeAction=MTLStoreActionStore;
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    [enc setFragmentBuffer:tbuf offset:0 atIndex:0];
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [enc endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    if (cb.error) { NSLog(@"cmdbuf err %@", cb.error); return 1; }
    float raw[4], man[4];
    [rawtex getBytes:raw bytesPerRow:16*W fromRegion:MTLRegionMake2D(32,32,1,1) mipmapLevel:0];
    [manualtex getBytes:man bytesPerRow:16*W fromRegion:MTLRegionMake2D(32,32,1,1) mipmapLevel:0];
    printf("b=(%.8f,%.8f,%.8f) manual=%.6f\n", raw[0],raw[1],raw[2], man[0]);
    return 0;
}}
