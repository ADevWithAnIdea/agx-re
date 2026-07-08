// bcprobe2.m — EXP-M4-07 TIL-2: block-compressed tiling across BLOCK BYTE-SIZES.
// Extends EXP-0028 bcprobe.m (BC1/BC7/ASTC4/8 only) to BC2/3/4/5/6H, ASTC 5/6/10/12,
// ETC2, EAC. Same method: CPU-upload a per-BLOCK marker via replaceRegion into a
// StorageModeShared compressed texture (block(bx,by) first bytes = [bx,by,0x5a,0xa5]),
// bind to capture descriptor+baseVA, dump raw backing. solvebc.py model-checks the
// block-tile edge T_blk (= largest pow2 with T_blk^2*blockBytes<=16KiB?) and the
// granule cols rule (G=0x4000/(T_blk^2*blockBytes)) — mirroring the texel rule.
//
// CLEAN-ROOM: HW-PROBE (known bytes in, raw layout out) + OWN data + DATA-TRACE.
// Build: clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o bcprobe2 bcprobe2.m
// Usage: bcprobe2 --fmt <name> --w N --h N --dump

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

typedef struct { const char*name; MTLPixelFormat pf; int bw,bh,bb; } BF;
static const BF BFS[]={
  {"bc1",  MTLPixelFormatBC1_RGBA,        4,4,8},
  {"bc2",  MTLPixelFormatBC2_RGBA,        4,4,16},
  {"bc3",  MTLPixelFormatBC3_RGBA,        4,4,16},
  {"bc4",  MTLPixelFormatBC4_RUnorm,      4,4,8},
  {"bc5",  MTLPixelFormatBC5_RGUnorm,     4,4,16},
  {"bc6h", MTLPixelFormatBC6H_RGBFloat,   4,4,16},
  {"bc7",  MTLPixelFormatBC7_RGBAUnorm,   4,4,16},
  {"astc4",  MTLPixelFormatASTC_4x4_LDR,   4,4,16},
  {"astc5",  MTLPixelFormatASTC_5x5_LDR,   5,5,16},
  {"astc6",  MTLPixelFormatASTC_6x6_LDR,   6,6,16},
  {"astc8",  MTLPixelFormatASTC_8x8_LDR,   8,8,16},
  {"astc10", MTLPixelFormatASTC_10x10_LDR, 10,10,16},
  {"astc12", MTLPixelFormatASTC_12x12_LDR, 12,12,16},
  {"etc2rgb",  MTLPixelFormatETC2_RGB8,    4,4,8},
  {"etc2rgba", MTLPixelFormatEAC_RGBA8,    4,4,16},
  {"eacr11",   MTLPixelFormatEAC_R11Unorm, 4,4,8},
  {"eacrg11",  MTLPixelFormatEAC_RG11Unorm,4,4,16},
};
static const int NBF=sizeof(BFS)/sizeof(BFS[0]);

int main(int argc,char**argv){
 @autoreleasepool{
  const char*fmtname="bc1"; long W=264,H=264,blocks=0; int doDump=0;
  for(int i=1;i<argc;i++){ const char*a=argv[i];
    #define ARG(f) (!strcmp(a,f)&&i+1<argc)
    if(ARG("--fmt")) fmtname=argv[++i];
    else if(ARG("--w")) W=strtol(argv[++i],0,0);
    else if(ARG("--h")) H=strtol(argv[++i],0,0);
    else if(ARG("--blocks")) blocks=strtol(argv[++i],0,0); // set block-grid edge directly
    else if(!strcmp(a,"--dump")) doDump=1;
    #undef ARG
  }
  const BF*F=NULL; for(int i=0;i<NBF;i++) if(!strcmp(BFS[i].name,fmtname)) F=&BFS[i];
  if(!F){ printf("UNKNOWN_FMT %s\n",fmtname); return 2; }
  int bw=F->bw,bh=F->bh,bb=F->bb;

  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\n",[[dev name] UTF8String]);
  long bx,by;
  if(blocks>0){ bx=by=blocks; W=bx*bw; H=by*bh; }
  else { bx=(W+bw-1)/bw; by=(H+bh-1)/bh; W=bx*bw; H=by*bh; }
  long bpr=bx*bb, total=bpr*by;
  printf("CONFIG fmt=%s %ldx%ld block=%dx%d bb=%d blocks=%ldx%ld bpr=%ld total=%ld\n",
    fmtname,W,H,bw,bh,bb,bx,by,bpr,total);

  MTLTextureDescriptor*td=[MTLTextureDescriptor new];
  td.pixelFormat=F->pf; td.width=W; td.height=H; td.textureType=MTLTextureType2D;
  td.storageMode=MTLStorageModeShared; td.usage=MTLTextureUsageShaderRead;
  id<MTLTexture> tex=[dev newTextureWithDescriptor:td];
  if(!tex){ printf("TEX_FAIL %s (unsupported)\n",fmtname); return 1; }

  unsigned char*src=calloc(total,1);
  for(long yy=0;yy<by;yy++) for(long xx=0;xx<bx;xx++){
    unsigned char*blk=src+(yy*bx+xx)*bb;
    blk[0]=(unsigned char)xx; blk[1]=(unsigned char)yy; blk[2]=0x5a; blk[3]=0xa5;
  }
  [tex replaceRegion:MTLRegionMake2D(0,0,W,H) mipmapLevel:0 withBytes:src bytesPerRow:bpr];
  free(src);
  printf("UPLOAD ok\n");

  NSError*err=nil;
  NSString*rk=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "kernel void k(texture2d<float> t [[texture(0)]], device uint* o [[buffer(0)]],\n"
    "  uint i [[thread_position_in_grid]]) { o[i]=t.get_width(); }\n";
  id<MTLLibrary>lib=[dev newLibraryWithSource:rk options:nil error:&err];
  id<MTLComputePipelineState>pso=lib?[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"k"] error:&err]:nil;
  id<MTLCommandQueue>q=[dev newCommandQueue];
  if(pso){
    id<MTLBuffer>ob=[dev newBufferWithLength:256 options:MTLResourceStorageModeShared];
    id<MTLCommandBuffer>cb=[q commandBuffer]; id<MTLComputeCommandEncoder>en=[cb computeCommandEncoder];
    [en setComputePipelineState:pso]; [en setTexture:tex atIndex:0]; [en setBuffer:ob offset:0 atIndex:0];
    [en dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
    [en endEncoding]; [cb commit]; [cb waitUntilCompleted];
    printf("BIND status=%ld\n",(long)[cb status]);
  } else printf("BIND_SKIP %s\n", err?[[err localizedDescription]UTF8String]:"");
  if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
  return 0;
 }
}
