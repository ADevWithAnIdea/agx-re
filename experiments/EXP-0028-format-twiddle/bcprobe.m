// bcprobe.m — EXP-0028 part 3: block-compressed twiddle confirmation.
//
// Block-compressed formats (BC/ASTC/ETC) can't be GPU-written (no ShaderWrite,
// not renderable), so we HW-PROBE them differently: CPU-upload a KNOWN per-BLOCK
// marker via -replaceRegion: into a StorageModeShared compressed texture (each
// 4x4/8x8-texel block's first bytes encode its block coord bx,by), bind it to
// capture the descriptor + base VA, and dump the raw backing bytes. bcx.py then
// maps physical block offset -> (bx,by) to confirm the Morton-over-BLOCKS layout
// hypothesised in docs/tiling §1.5.
//
// CLEAN-ROOM: HW-PROBE (known bytes in, raw layout out) + OWN data + DATA-TRACE.
// No Apple binary disassembled. See ../../CLAUDE.md.
//
// Build (device): clang -fobjc-arc -framework Metal -framework Foundation -o bcprobe bcprobe.m
// Usage: bcprobe --fmt <bc1|bc7|astc4|astc8> --w N --h N --dump

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

int main(int argc,char**argv){
 @autoreleasepool{
  const char *fmtname="bc1"; long W=32,H=32; int doDump=0;
  for(int i=1;i<argc;i++){ const char*a=argv[i];
    #define ARG(f) (!strcmp(a,f)&&i+1<argc)
    if(ARG("--fmt")) fmtname=argv[++i];
    else if(ARG("--w")) W=strtol(argv[++i],0,0);
    else if(ARG("--h")) H=strtol(argv[++i],0,0);
    else if(!strcmp(a,"--dump")) doDump=1;
    #undef ARG
  }
  MTLPixelFormat pf; int bw,bh,bb;   // block width/height (texels), block bytes
  if(!strcmp(fmtname,"bc1")){ pf=MTLPixelFormatBC1_RGBA; bw=4;bh=4;bb=8; }
  else if(!strcmp(fmtname,"bc7")){ pf=MTLPixelFormatBC7_RGBAUnorm; bw=4;bh=4;bb=16; }
  else if(!strcmp(fmtname,"astc4")){ pf=MTLPixelFormatASTC_4x4_LDR; bw=4;bh=4;bb=16; }
  else if(!strcmp(fmtname,"astc8")){ pf=MTLPixelFormatASTC_8x8_LDR; bw=8;bh=8;bb=16; }
  else { printf("UNKNOWN_FMT %s\n",fmtname); return 2; }

  long bx=(W+bw-1)/bw, by=(H+bh-1)/bh;   // blocks per row/col
  long bpr=bx*bb;                        // bytes per (block) row
  long total=bpr*by;

  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\n",[[dev name] UTF8String]);
  printf("CONFIG fmt=%s %ldx%ld block=%dx%d bb=%d blocks=%ldx%ld bpr=%ld total=%ld\n",
    fmtname,W,H,bw,bh,bb,bx,by,bpr,total);

  MTLTextureDescriptor *td=[MTLTextureDescriptor new];
  td.pixelFormat=pf; td.width=W; td.height=H; td.textureType=MTLTextureType2D;
  td.storageMode=MTLStorageModeShared; td.usage=MTLTextureUsageShaderRead;
  id<MTLTexture> tex=[dev newTextureWithDescriptor:td];
  if(!tex){ printf("TEX_FAIL\n"); return 1; }

  // per-block marker: word0 = 0xA55A<<16 | (byv<<8) | bxv ; rest 0.
  unsigned char *src=calloc(total,1);
  for(long yy=0;yy<by;yy++) for(long xx=0;xx<bx;xx++){
    unsigned char *blk=src+(yy*bx+xx)*bb;
    blk[0]=(unsigned char)xx; blk[1]=(unsigned char)yy; blk[2]=0x5a; blk[3]=0xa5;
  }
  [tex replaceRegion:MTLRegionMake2D(0,0,W,H) mipmapLevel:0 withBytes:src bytesPerRow:bpr];
  free(src);
  printf("UPLOAD ok\n");

  // bind (get_width) to capture descriptor + base VA
  NSError *err=nil;
  NSString *rk=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "kernel void k(texture2d<float> t [[texture(0)]], device uint* o [[buffer(0)]],\n"
    "  uint i [[thread_position_in_grid]]) { o[i]=t.get_width(); }\n";
  id<MTLLibrary> lib=[dev newLibraryWithSource:rk options:nil error:&err];
  id<MTLComputePipelineState> pso=lib?[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"k"] error:&err]:nil;
  id<MTLCommandQueue> q=[dev newCommandQueue];
  if(pso){
    id<MTLBuffer> obuf=[dev newBufferWithLength:256 options:MTLResourceStorageModeShared];
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
    [enc setComputePipelineState:pso]; [enc setTexture:tex atIndex:0]; [enc setBuffer:obuf offset:0 atIndex:0];
    [enc dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
    [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
    printf("BIND status=%ld\n",(long)[cb status]);
  } else printf("BIND_SKIP %s\n", err?[[err localizedDescription] UTF8String]:"");

  if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
  return 0;
 }
}
