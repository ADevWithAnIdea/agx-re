#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
int main() {
    @autoreleasepool {
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        NSLog(@"name=%@ maxBufferLength=%llu hasUnifiedMemory=%d", dev.name,
              (unsigned long long)dev.maxBufferLength, dev.hasUnifiedMemory);
        NSLog(@"sparseTileSizeInBytes=%lu", (unsigned long)dev.sparseTileSizeInBytes);
        MTLSizeAndAlign sa = [dev heapBufferSizeAndAlignWithLength:4096 options:MTLResourceStorageModePrivate];
        NSLog(@"heapBufferSizeAndAlign(4096,private) size=%lu align=%lu", (unsigned long)sa.size, (unsigned long)sa.align);
        id<MTLBuffer> buf = [dev newBufferWithLength:4096 options:MTLResourceStorageModeShared];
        NSLog(@"buf gpuAddress=0x%llx", (unsigned long long)buf.gpuAddress);
        MTLSize tsz = [dev sparseTileSizeWithTextureType:MTLTextureType2D pixelFormat:MTLPixelFormatRGBA8Unorm sampleCount:1];
        NSLog(@"sparseTileSize 2D rgba8 = %ldx%ldx%ld", (long)tsz.width,(long)tsz.height,(long)tsz.depth);
    }
    return 0;
}
