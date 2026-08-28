// Scratch: write via kernel, verify with a BLIT copy-to-buffer readback (bypasses the
// compute read-kernel entirely) to isolate whether the WRITE lands, independent of whether
// our access::read kernel can see it.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
int main() {
    @autoreleasepool {
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        NSString *src = [NSString stringWithContentsOfFile:@"/Users/user/asahi_re/public/agx-re/experiments/EXP-0122-m4-sparse-vm-conventions/kernels/sparse_access.metal" encoding:NSUTF8StringEncoding error:nil];
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:nil error:nil];
        id<MTLComputePipelineState> writePSO = [dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"sparse_write_rgba8"] error:nil];

        MTLTextureDescriptor *td = [MTLTextureDescriptor new];
        td.textureType = MTLTextureType2D;
        td.pixelFormat = MTLPixelFormatRGBA8Unorm;
        td.width = 64; td.height = 64; td.depth = 1;
        td.usage = MTLTextureUsageShaderRead | MTLTextureUsageShaderWrite;
        td.storageMode = MTLStorageModePrivate;
        MTLSizeAndAlign sa = [dev heapTextureSizeAndAlignWithDescriptor:td];
        MTLHeapDescriptor *hd = [MTLHeapDescriptor new];
        hd.type = MTLHeapTypeSparse;
        hd.storageMode = MTLStorageModePrivate;
        hd.sparsePageSize = MTLSparsePageSize16;
        hd.size = sa.size + 4*1024*1024;
        id<MTLHeap> heap = [dev newHeapWithDescriptor:hd];
        id<MTLTexture> tex = [heap newTextureWithDescriptor:td];
        [tex setPurgeableState:MTLPurgeableStateNonVolatile];
        NSLog(@"tex.isSparse=%d firstMipmapInTail=%lu tailSizeInBytes=%lu", tex.isSparse, (unsigned long)tex.firstMipmapInTail, (unsigned long)tex.tailSizeInBytes);
        if (@available(macOS 26.0, *)) { NSLog(@"sparseTextureTier=%ld", (long)tex.sparseTextureTier); }
        NSLog(@"device.sparseTileSizeInBytes=%lu", (unsigned long)dev.sparseTileSizeInBytes);


        id<MTLCommandQueue> q = [dev newCommandQueue];

        // map tile (0,0), 64x64
        id<MTLCommandBuffer> cbm = [q commandBuffer];
        id<MTLResourceStateCommandEncoder> em = [cbm resourceStateCommandEncoder];
        NSLog(@"resourceStateCommandEncoder = %@", em);
        [em updateTextureMapping:tex mode:MTLSparseTextureMappingModeMap region:MTLRegionMake2D(0,0,128,128) mipLevel:0 slice:0];
        [em endEncoding];
        [cbm commit]; [cbm waitUntilCompleted];
        NSLog(@"map status=%ld err=%@ heap.usedSize=%lu heap.currentAllocatedSize=%lu", (long)cbm.status, cbm.error, (unsigned long)heap.usedSize, (unsigned long)heap.currentAllocatedSize);
        usleep(500000); // test: does a firmware-side delay after "completed" fix visibility?

        uint32_t coord[2] = {5,5};
        id<MTLBuffer> coordBuf = [dev newBufferWithBytes:coord length:8 options:MTLResourceStorageModeShared];
        float pattern[4] = {0.25,0.5,0.75,1.0};

        id<MTLCommandBuffer> cb1 = [q commandBuffer];
        id<MTLComputeCommandEncoder> e1 = [cb1 computeCommandEncoder];
        [e1 setComputePipelineState:writePSO];
        [e1 setTexture:tex atIndex:0];
        [e1 setBuffer:coordBuf offset:0 atIndex:0];
        [e1 setBytes:pattern length:16 atIndex:1];
        [e1 useHeap:heap];
        [e1 dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
        [e1 endEncoding];
        [cb1 commit]; [cb1 waitUntilCompleted];
        NSLog(@"write status=%ld err=%@ heap.usedSize=%lu", (long)cb1.status, cb1.error, (unsigned long)heap.usedSize);

        // Blit whole texture to a shared buffer, then inspect bytes at (10,10).
        NSUInteger bpr = 64 * 4;
        id<MTLBuffer> outBuf = [dev newBufferWithLength:bpr*64 options:MTLResourceStorageModeShared];
        id<MTLCommandBuffer> cb2 = [q commandBuffer];
        id<MTLBlitCommandEncoder> be = [cb2 blitCommandEncoder];
        [be copyFromTexture:tex sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0)
                  sourceSize:MTLSizeMake(64,64,1) toBuffer:outBuf destinationOffset:0
             destinationBytesPerRow:bpr destinationBytesPerImage:bpr*64];
        [be endEncoding];
        [cb2 commit]; [cb2 waitUntilCompleted];
        NSLog(@"blit status=%ld err=%@", (long)cb2.status, cb2.error);
        unsigned char *b = (unsigned char*)outBuf.contents;
        NSUInteger idx = (5*64 + 5) * 4;
        NSLog(@"bytes at (5,5) = %02x %02x %02x %02x", b[idx],b[idx+1],b[idx+2],b[idx+3]);
        NSUInteger idx2 = (0*128 + 0) * 4;
        NSLog(@"bytes at (0,0) = %02x %02x %02x %02x", b[idx2],b[idx2+1],b[idx2+2],b[idx2+3]);
    }
    return 0;
}
