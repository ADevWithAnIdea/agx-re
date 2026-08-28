// Scratch control (work/ only): does write-then-read via two sequential command buffers
// with waitUntilCompleted work correctly for a PLAIN (non-sparse, non-heap) private texture?
// Isolates whether the sparse_partial_map zero-readback anomaly is sparse/heap-specific.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
int main() {
    @autoreleasepool {
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        NSString *src = [NSString stringWithContentsOfFile:@"/Users/user/asahi_re/public/agx-re/experiments/EXP-0122-m4-sparse-vm-conventions/kernels/sparse_access.metal" encoding:NSUTF8StringEncoding error:nil];
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:nil error:nil];
        id<MTLComputePipelineState> readPSO = [dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"sparse_read_rgba8"] error:nil];
        id<MTLComputePipelineState> writePSO = [dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"sparse_write_rgba8"] error:nil];

        MTLTextureDescriptor *td = [MTLTextureDescriptor new];
        td.textureType = MTLTextureType2D;
        td.pixelFormat = MTLPixelFormatRGBA8Unorm;
        td.width = 128; td.height = 128; td.depth = 1;
        td.usage = MTLTextureUsageShaderRead | MTLTextureUsageShaderWrite;
        td.storageMode = MTLStorageModePrivate;
        id<MTLTexture> tex = [dev newTextureWithDescriptor:td];
        NSLog(@"tex=%@", tex);

        id<MTLCommandQueue> q = [dev newCommandQueue];

        uint32_t coord[2] = {10,10};
        id<MTLBuffer> coordBuf = [dev newBufferWithBytes:coord length:8 options:MTLResourceStorageModeShared];
        float pattern[4] = {0.25,0.5,0.75,1.0};

        id<MTLCommandBuffer> cb1 = [q commandBuffer];
        id<MTLComputeCommandEncoder> e1 = [cb1 computeCommandEncoder];
        [e1 setComputePipelineState:writePSO];
        [e1 setTexture:tex atIndex:0];
        [e1 setBuffer:coordBuf offset:0 atIndex:0];
        [e1 setBytes:pattern length:16 atIndex:1];
        [e1 dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
        [e1 endEncoding];
        [cb1 commit];
        [cb1 waitUntilCompleted];
        NSLog(@"write cb status=%ld err=%@", (long)cb1.status, cb1.error);

        id<MTLBuffer> outBuf = [dev newBufferWithLength:16 options:MTLResourceStorageModeShared];
        memset(outBuf.contents, 0xEE, 16);
        id<MTLCommandBuffer> cb2 = [q commandBuffer];
        id<MTLComputeCommandEncoder> e2 = [cb2 computeCommandEncoder];
        [e2 setComputePipelineState:readPSO];
        [e2 setTexture:tex atIndex:0];
        [e2 setBuffer:coordBuf offset:0 atIndex:0];
        [e2 setBuffer:outBuf offset:0 atIndex:1];
        [e2 dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
        [e2 endEncoding];
        [cb2 commit];
        [cb2 waitUntilCompleted];
        NSLog(@"read cb status=%ld err=%@", (long)cb2.status, cb2.error);
        float *fp = (float*)outBuf.contents;
        NSLog(@"readback = %f %f %f %f", fp[0], fp[1], fp[2], fp[3]);
    }
    return 0;
}
