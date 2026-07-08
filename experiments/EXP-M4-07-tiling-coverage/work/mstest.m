#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
int main(){@autoreleasepool{
 id<MTLDevice>d=MTLCreateSystemDefaultDevice();
 MTLPixelFormat pfs[]={MTLPixelFormatR8Uint,MTLPixelFormatR16Uint,MTLPixelFormatR32Uint,MTLPixelFormatRG32Uint,MTLPixelFormatRGBA32Uint};
 const char*nm[]={"r8(1)","r16(2)","r32(4)","rg32(8)","rgba32(16)"};
 int scs[]={2,4,8};
 for(int f=0;f<5;f++){printf("%-10s supportsTextureSampleCount: ",nm[f]);
  for(int s=0;s<3;s++){printf("%dx=%d ",scs[s],(int)[d supportsTextureSampleCount:scs[s]]);}
  // actually try to create each
  for(int s=0;s<3;s++){ MTLTextureDescriptor*td=[MTLTextureDescriptor new];
   td.pixelFormat=pfs[f];td.width=64;td.height=64;td.sampleCount=scs[s];
   td.textureType=MTLTextureType2DMultisample;td.usage=MTLTextureUsageRenderTarget;
   td.storageMode=MTLStorageModePrivate;
   id<MTLTexture>t=nil; @try{t=[d newTextureWithDescriptor:td];}@catch(NSException*e){}
   printf(" create%dx=%s",scs[s],t?"ok":"FAIL");
  }
  printf("\n");
 }
 return 0;}}
