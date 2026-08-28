#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdio.h>
#include <string.h>
int main(int argc, const char **argv) {
  @autoreleasepool {
    id<MTLDevice> d = MTLCreateSystemDefaultDevice();
    const char *fmtname = argv[1];
    unsigned long long width = strtoull(argv[2], NULL, 10);
    MTLPixelFormat fmt; int bytes;
    if (!strcmp(fmtname, "R8Uint")) { fmt = MTLPixelFormatR8Uint; bytes = 1; }
    else if (!strcmp(fmtname, "RG8Uint")) { fmt = MTLPixelFormatRG8Uint; bytes = 2; }
    else if (!strcmp(fmtname, "RGBA8Uint")) { fmt = MTLPixelFormatRGBA8Uint; bytes = 4; }
    else if (!strcmp(fmtname, "RGBA16Uint")) { fmt = MTLPixelFormatRGBA16Uint; bytes = 8; }
    else if (!strcmp(fmtname, "RGBA32Uint")) { fmt = MTLPixelFormatRGBA32Uint; bytes = 16; }
    else { printf("BAD_FORMAT\n"); return 2; }
    unsigned long long bytesNeeded = width * (unsigned long long)bytes;
    if (bytesNeeded > d.maxBufferLength) { printf("SKIP exceeds maxBufferLength needs=%llu max=%llu\n", bytesNeeded, (unsigned long long)d.maxBufferLength); return 0; }
    MTLTextureDescriptor *td = [MTLTextureDescriptor new];
    td.textureType = MTLTextureTypeTextureBuffer;
    td.pixelFormat = fmt;
    td.width = width; td.height = 1; td.depth = 1;
    td.usage = MTLTextureUsageShaderRead;
    td.storageMode = MTLStorageModeShared;
    id<MTLBuffer> buf = [d newBufferWithLength:bytesNeeded options:MTLResourceStorageModeShared];
    if (!buf) { printf("BUFFER_ALLOC_FAIL\n"); return 0; }
    id<MTLTexture> t = [buf newTextureWithDescriptor:td offset:0 bytesPerRow:bytesNeeded];
    printf("%s width=%llu bytesNeeded=%llu -> texture=%s\n", fmtname, width, bytesNeeded, t ? "OK" : "NIL");
    return 0;
  }
}
