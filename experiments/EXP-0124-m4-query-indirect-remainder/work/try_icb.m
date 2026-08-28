#import <Metal/Metal.h>
#import <Foundation/Foundation.h>

static NSString *readFile(const char *path) {
    NSError *err = nil;
    NSString *s = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:path] encoding:NSUTF8StringEncoding error:&err];
    if (!s) { NSLog(@"read fail %@", err); exit(2); }
    return s;
}

int main(int argc, char *argv[]) {
    @autoreleasepool {
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        NSLog(@"device: %@", dev.name);
        NSError *err = nil;

        // Compile kernel + render pipeline.
        id<MTLLibrary> lib = [dev newLibraryWithSource:readFile("try2.metal") options:nil error:&err];
        if (!lib) { NSLog(@"compile fail %@", err); return 1; }
        // Also compile a tiny render lib.
        NSString *rsrc = @"#include <metal_stdlib>\nusing namespace metal;\n"
            "struct VOut { float4 pos [[position]]; float4 color; };\n"
            "vertex VOut v_fs(uint vid [[vertex_id]], const device float4 *colors [[buffer(1)]]) {\n"
            "  float2 p[3] = {float2(-1,-1), float2(3,-1), float2(-1,3)};\n"
            "  VOut o; o.pos = float4(p[vid],0,1); o.color = colors[0]; return o; }\n"
            "fragment float4 f_fs(VOut in [[stage_in]]) { return in.color; }\n";
        id<MTLLibrary> rlib = [dev newLibraryWithSource:rsrc options:nil error:&err];
        if (!rlib) { NSLog(@"render compile fail %@", err); return 1; }

        id<MTLFunction> encFn = [lib newFunctionWithName:@"encode_render"];
        id<MTLComputePipelineState> encPSO = [dev newComputePipelineStateWithFunction:encFn error:&err];
        if (!encPSO) { NSLog(@"enc pso fail %@", err); return 1; }

        MTLRenderPipelineDescriptor *rpd = [MTLRenderPipelineDescriptor new];
        rpd.vertexFunction = [rlib newFunctionWithName:@"v_fs"];
        rpd.fragmentFunction = [rlib newFunctionWithName:@"f_fs"];
        rpd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
        rpd.supportIndirectCommandBuffers = YES;
        id<MTLRenderPipelineState> rpso = [dev newRenderPipelineStateWithDescriptor:rpd error:&err];
        if (!rpso) { NSLog(@"render pso fail %@", err); return 1; }

        // ICB.
        MTLIndirectCommandBufferDescriptor *icd = [MTLIndirectCommandBufferDescriptor new];
        icd.commandTypes = MTLIndirectCommandTypeDraw;
        icd.inheritPipelineState = YES;
        icd.inheritBuffers = NO;
        icd.maxVertexBufferBindCount = 2;
        icd.maxFragmentBufferBindCount = 0;
        id<MTLIndirectCommandBuffer> icb = [dev newIndirectCommandBufferWithDescriptor:icd maxCommandCount:1 options:0];
        if (!icb) { NSLog(@"icb alloc fail"); return 1; }
        NSLog(@"icb size=%lu gpuResourceID=%llu", (unsigned long)icb.size, (unsigned long long)icb.gpuResourceID._impl);

        // Argument buffer for the {command_buffer icb;} struct.
        id<MTLArgumentEncoder> argEnc = [encFn newArgumentEncoderWithBufferIndex:0];
        NSLog(@"argEnc encodedLength=%lu", (unsigned long)argEnc.encodedLength);
        id<MTLBuffer> argBuf = [dev newBufferWithLength:argEnc.encodedLength options:MTLResourceStorageModeShared];
        [argEnc setArgumentBuffer:argBuf offset:0];
        [argEnc setIndirectCommandBuffer:icb atIndex:0];

        // colors buffer: single float4 red.
        float red[4] = {1,0,0,1};
        id<MTLBuffer> colorBuf = [dev newBufferWithBytes:red length:sizeof(red) options:MTLResourceStorageModeShared];

        id<MTLCommandQueue> q = [dev newCommandQueue];
        id<MTLCommandBuffer> cb = [q commandBuffer];

        // Encode pass: run encode_render kernel with 1 thread.
        id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
        [ce setComputePipelineState:encPSO];
        [ce setBuffer:argBuf offset:0 atIndex:0];
        [ce setBuffer:colorBuf offset:0 atIndex:1];
        [ce useResource:icb usage:MTLResourceUsageWrite];
        [ce dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
        [ce endEncoding];

        // Render pass executing the ICB.
        id<MTLTexture> tex;
        {
            MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:8 height:8 mipmapped:NO];
            td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
            td.storageMode = MTLStorageModeShared;
            tex = [dev newTextureWithDescriptor:td];
        }
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = tex;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(0,0,0,0);
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;
        id<MTLRenderCommandEncoder> re = [cb renderCommandEncoderWithDescriptor:rp];
        [re setRenderPipelineState:rpso];
        [re useResource:icb usage:MTLResourceUsageRead];
        [re executeCommandsInBuffer:icb withRange:NSMakeRange(0,1)];
        [re endEncoding];

        [cb commit];
        [cb waitUntilCompleted];
        if (cb.status == MTLCommandBufferStatusError) {
            NSLog(@"cb error: %@", cb.error);
            return 1;
        }
        NSLog(@"cb status ok");

        uint8_t px[8*8*4];
        [tex getBytes:px bytesPerRow:8*4 fromRegion:MTLRegionMake2D(0,0,8,8) mipmapLevel:0];
        NSLog(@"pixel(4,4) = %d %d %d %d", px[(4*8+4)*4+0], px[(4*8+4)*4+1], px[(4*8+4)*4+2], px[(4*8+4)*4+3]);
        return 0;
    }
}
