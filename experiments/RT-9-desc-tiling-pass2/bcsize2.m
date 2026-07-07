#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
int main(int c,char**v){@autoreleasepool{
 setbuf(stdout,NULL);
 if(c<3){printf("usage w h\n");return 2;}
 id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
 if(!dev){printf("no dev\n");return 1;}
 struct{const char*n;MTLPixelFormat f;} F[]={{"bc1",MTLPixelFormatBC1_RGBA},{"bc7",MTLPixelFormatBC7_RGBAUnorm},{"astc8x8",MTLPixelFormatASTC_8x8_LDR}};
 int W=atoi(v[1]),H=atoi(v[2]);
 for(int i=0;i<3;i++){
   MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:F[i].f width:W height:H mipmapped:NO];
   td.usage=MTLTextureUsageShaderRead; td.storageMode=MTLStorageModePrivate;
   MTLSizeAndAlign sa=[dev heapTextureSizeAndAlignWithDescriptor:td];
   printf("%s %dx%d -> heapSize=0x%lx align=0x%lx\n",F[i].n,W,H,(unsigned long)sa.size,(unsigned long)sa.align);
 }
 return 0;
}}
