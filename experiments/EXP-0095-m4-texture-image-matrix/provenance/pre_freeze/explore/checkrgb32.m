#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdio.h>
int main(void) {
  @autoreleasepool {
    id<MTLDevice> d = MTLCreateSystemDefaultDevice();
    // MTLPixelFormatRGB32Uint / RGB32Float / RGB32Sint enum values (public constants)
    MTLPixelFormat fmts[] = {MTLPixelFormatRGB32Uint, MTLPixelFormatRGB32Sint, MTLPixelFormatRGB32Float};
    const char *names[] = {"RGB32Uint","RGB32Sint","RGB32Float"};
    for (int i=0;i<3;i++) {
      MTLTextureDescriptor *td = [MTLTextureDescriptor new];
      td.textureType = MTLTextureTypeTextureBuffer;
      td.pixelFormat = fmts[i];
      td.width = 16; td.height = 1; td.depth = 1;
      td.usage = MTLTextureUsageShaderRead;
      td.storageMode = MTLStorageModeShared;
      id<MTLBuffer> buf = [d newBufferWithLength:16*12 options:MTLResourceStorageModeShared];
      id<MTLTexture> t = nil;
      @try { t = [buf newTextureWithDescriptor:td offset:0 bytesPerRow:16*12]; }
      @catch (NSException *ex) { printf("%s -> EXCEPTION %s\n", names[i], ex.reason.UTF8String); continue; }
      printf("%s -> texture=%s\n", names[i], t ? "OK" : "NIL");
    }
  }
  return 0;
}
