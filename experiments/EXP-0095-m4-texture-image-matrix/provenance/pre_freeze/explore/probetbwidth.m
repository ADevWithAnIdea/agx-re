#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdio.h>
int main(void) {
  @autoreleasepool {
    id<MTLDevice> d = MTLCreateSystemDefaultDevice();
    printf("device=%s maxBufferLength=%llu\n", d.name.UTF8String, (unsigned long long)d.maxBufferLength);
    // per-format: element size, try widths near candidate ceilings
    struct { const char *name; MTLPixelFormat fmt; int bytes; } formats[] = {
      {"R8Uint", MTLPixelFormatR8Uint, 1},
      {"RG8Uint", MTLPixelFormatRG8Uint, 2},
      {"RGBA8Uint", MTLPixelFormatRGBA8Uint, 4},
      {"RGBA16Uint", MTLPixelFormatRGBA16Uint, 8},
      {"RGBA32Uint", MTLPixelFormatRGBA32Uint, 16},
    };
    unsigned long long candidates[] = {
      (1ull<<24), (1ull<<25), (1ull<<26), (1ull<<27) - 1, (1ull<<27), (1ull<<27)+1,
      (1ull<<28), (1ull<<29), (1ull<<30)
    };
    for (int fi = 0; fi < 5; fi++) {
      for (int ci = 0; ci < 9; ci++) {
        unsigned long long width = candidates[ci];
        unsigned long long bytesNeeded = width * (unsigned long long)formats[fi].bytes;
        if (bytesNeeded > d.maxBufferLength) { printf("%s width=%llu -> SKIP (exceeds maxBufferLength, needs %llu bytes)\n", formats[fi].name, width, bytesNeeded); continue; }
        MTLTextureDescriptor *td = [MTLTextureDescriptor new];
        td.textureType = MTLTextureTypeTextureBuffer;
        td.pixelFormat = formats[fi].fmt;
        td.width = width; td.height = 1; td.depth = 1;
        td.usage = MTLTextureUsageShaderRead;
        td.storageMode = MTLStorageModeShared;
        // Need a buffer at least bytesNeeded; allocate lazily only if plausible
        id<MTLTexture> t = nil;
        @try {
          id<MTLBuffer> buf = [d newBufferWithLength:bytesNeeded options:MTLResourceStorageModeShared];
          if (!buf) { printf("%s width=%llu -> BUFFER_ALLOC_FAIL\n", formats[fi].name, width); continue; }
          NSUInteger align = [d minimumLinearTextureAlignmentForPixelFormat:formats[fi].fmt];
          t = [buf newTextureWithDescriptor:td offset:0 bytesPerRow:bytesNeeded];
          printf("%s width=%llu align=%lu -> texture=%s\n", formats[fi].name, width, (unsigned long)align, t ? "OK" : "NIL");
        } @catch (NSException *ex) {
          printf("%s width=%llu -> EXCEPTION %s\n", formats[fi].name, width, ex.reason.UTF8String);
        }
      }
    }
  }
  return 0;
}
