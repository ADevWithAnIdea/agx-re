// Scratch (work/ only): does explicit hazardTrackingMode=Tracked, or an explicit MTLFence,
// fix the write->read visibility gap observed for sparse-heap textures across two
// sequential, waited command buffers?
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>

static id<MTLTexture> makeSparseTex(id<MTLDevice> dev, BOOL tracked, id<MTLHeap> *heapOut) {
    MTLTextureDescriptor *td = [MTLTextureDescriptor new];
    td.textureType = MTLTextureType2D;
    td.pixelFormat = MTLPixelFormatRGBA8Unorm;
    td.width = 128; td.height = 128; td.depth = 1;
    td.usage = MTLTextureUsageShaderRead | MTLTextureUsageShaderWrite;
    td.storageMode = MTLStorageModePrivate;
    MTLSizeAndAlign sa = [dev heapTextureSizeAndAlignWithDescriptor:td];
    MTLHeapDescriptor *hd = [MTLHeapDescriptor new];
    hd.type = MTLHeapTypeSparse;
    hd.storageMode = MTLStorageModePrivate;
    hd.sparsePageSize = MTLSparsePageSize16;
    hd.size = sa.size + 4*1024*1024;
    if (tracked) hd.hazardTrackingMode = MTLHazardTrackingModeTracked;
    id<MTLHeap> heap = [dev newHeapWithDescriptor:hd];
    NSLog(@"heap hazardTrackingMode=%ld", (long)heap.hazardTrackingMode);
    id<MTLTexture> tex = [heap newTextureWithDescriptor:td];
    if (heapOut) *heapOut = heap;
    return tex;
}

static void mapTile(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLTexture> tex) {
    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLResourceStateCommandEncoder> enc = [cb resourceStateCommandEncoder];
    [enc updateTextureMapping:tex mode:MTLSparseTextureMappingModeMap region:MTLRegionMake2D(0,0,64,64) mipLevel:0 slice:0];
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    NSLog(@"map status=%ld err=%@", (long)cb.status, cb.error);
}

static void runTrial(id<MTLDevice> dev, id<MTLComputePipelineState> writePSO, id<MTLComputePipelineState> readPSO,
                      BOOL tracked, BOOL useFence, NSString *label) {
    id<MTLHeap> heap = nil;
    id<MTLTexture> tex = makeSparseTex(dev, tracked, &heap);
    id<MTLCommandQueue> q = [dev newCommandQueue];
    mapTile(dev, q, tex);

    uint32_t coord[2] = {10,10};
    id<MTLBuffer> coordBuf = [dev newBufferWithBytes:coord length:8 options:MTLResourceStorageModeShared];
    float pattern[4] = {0.25,0.5,0.75,1.0};
    id<MTLFence> fence = useFence ? [dev newFence] : nil;

    id<MTLCommandBuffer> cb1 = [q commandBuffer];
    id<MTLComputeCommandEncoder> e1 = [cb1 computeCommandEncoder];
    [e1 setComputePipelineState:writePSO];
    [e1 setTexture:tex atIndex:0];
    [e1 setBuffer:coordBuf offset:0 atIndex:0];
    [e1 setBytes:pattern length:16 atIndex:1];
    [e1 dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
    if (useFence) [e1 updateFence:fence];
    [e1 endEncoding];
    [cb1 commit];
    [cb1 waitUntilCompleted];

    id<MTLBuffer> outBuf = [dev newBufferWithLength:16 options:MTLResourceStorageModeShared];
    memset(outBuf.contents, 0xEE, 16);
    id<MTLCommandBuffer> cb2 = [q commandBuffer];
    id<MTLComputeCommandEncoder> e2 = [cb2 computeCommandEncoder];
    if (useFence) [e2 waitForFence:fence];
    [e2 setComputePipelineState:readPSO];
    // placeholder
    [e2 setTexture:tex atIndex:0];
    [e2 setBuffer:coordBuf offset:0 atIndex:0];
    [e2 setBuffer:outBuf offset:0 atIndex:1];
    [e2 useResource:tex usage:MTLResourceUsageRead];
    [e2 dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
    [e2 endEncoding];
    [cb2 commit];
    [cb2 waitUntilCompleted];
    float *fp = (float*)outBuf.contents;
    NSLog(@"[%@] write=%ld(%@) read=%ld(%@) readback=%f %f %f %f", label,
          (long)cb1.status, cb1.error, (long)cb2.status, cb2.error, fp[0], fp[1], fp[2], fp[3]);
}

int main() {
    @autoreleasepool {
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        NSString *src = [NSString stringWithContentsOfFile:@"/Users/user/asahi_re/public/agx-re/experiments/EXP-0122-m4-sparse-vm-conventions/kernels/sparse_access.metal" encoding:NSUTF8StringEncoding error:nil];
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:nil error:nil];
        id<MTLComputePipelineState> readPSO = [dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"sparse_read_rgba8"] error:nil];
        id<MTLComputePipelineState> writePSO = [dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"sparse_write_rgba8"] error:nil];

        runTrial(dev, writePSO, readPSO, NO, NO, @"untracked_nofence");
        runTrial(dev, writePSO, readPSO, YES, NO, @"tracked_nofence");
        runTrial(dev, writePSO, readPSO, NO, YES, @"untracked_fence");
        runTrial(dev, writePSO, readPSO, NO, NO, @"untracked_useresource");
    }
    return 0;
}
