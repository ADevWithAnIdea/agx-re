// c_tiling.m -- RT-12 Part C: independent 2nd-pass re-confirm of the RT-9 tiling fix.
// DIFFERENT sizes than RT-9 (which tested 192/300/384/448x192/576): here 448x448 bpp4 and
// 704x256 bpp8 -- both are non-power-of-two NUMBERS OF TILES, chosen so tile-multiple and
// nextpow2 padding disagree strongly.
//
// Two independent evidences per texture:
//  (1) [dev heapTextureSizeAndAlign:] -> the driver's own allocation size (API, no iotrace).
//  (2) a coordinate-marker pattern written GPU-side + iotrace BO dump -> the raw byte layout,
//      so a host analyzer can locate specific texels and read cols=ceil(W/T) directly, and
//      cross-check the actual registered backing-BO size.
//
// CLEAN-ROOM: HW-PROBE (known pattern in, raw layout out) + OWN-SHADER (our MSL) + DATA-TRACE
// (our BOs via read-only iotrace). No Apple binary disassembled. See ../../CLAUDE.md.
//
// Build (device): clang -fobjc-arc -framework Metal -framework Foundation -o c_tiling c_tiling.m
// Usage: c_tiling --fmt r32uint|rg32uint --w W --h H [--dump]
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void pv(const char*l,uint64_t v){ printf("VA %-10s = 0x%016llx\n",l,(unsigned long long)v); }

int main(int argc,char**argv){ @autoreleasepool{
  const char*fmt="r32uint"; long W=448,H=448; int doDump=0;
  for(int i=1;i<argc;i++){ const char*a=argv[i];
    if(!strcmp(a,"--fmt")&&i+1<argc) fmt=argv[++i];
    else if(!strcmp(a,"--w")&&i+1<argc) W=strtol(argv[++i],0,0);
    else if(!strcmp(a,"--h")&&i+1<argc) H=strtol(argv[++i],0,0);
    else if(!strcmp(a,"--dump")) doDump=1;
  }
  int bpp; MTLPixelFormat pf; int isRG;
  if(!strcmp(fmt,"r32uint")){ pf=MTLPixelFormatR32Uint; bpp=4; isRG=0; }
  else if(!strcmp(fmt,"rg32uint")){ pf=MTLPixelFormatRG32Uint; bpp=8; isRG=1; }
  else { printf("UNKNOWN_FMT %s\n",fmt); return 2; }
  int T = (bpp<=4)?64:32;
  long cols_expect = (W + T - 1)/T;
  long padW = cols_expect*T, padH = ((H+T-1)/T)*T;
  long alloc_tilemult = padW*padH*bpp;

  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\n",[[dev name]UTF8String]);
  printf("CONFIG fmt=%s W=%ld H=%ld bpp=%d T=%d cols_expect=%ld padW=%ld padH=%ld alloc_tilemult=0x%lx\n",
    fmt,W,H,bpp,T,cols_expect,padW,padH,(unsigned long)alloc_tilemult);

  MTLTextureDescriptor*td=[MTLTextureDescriptor new];
  td.pixelFormat=pf; td.width=W; td.height=H; td.depth=1; td.mipmapLevelCount=1;
  td.textureType=MTLTextureType2D; td.storageMode=MTLStorageModeShared;
  td.usage=MTLTextureUsageShaderRead|MTLTextureUsageShaderWrite; // writable => uncompressed twiddle

  MTLSizeAndAlign sa=[dev heapTextureSizeAndAlignWithDescriptor:td];
  printf("HEAP_SIZE fmt=%s W=%ld H=%ld size=0x%llx align=0x%llx (tilemult=0x%lx nextpow2=0x%lx)\n",
    fmt,W,H,(unsigned long long)sa.size,(unsigned long long)sa.align,(unsigned long)alloc_tilemult,
    (unsigned long)( (1UL<<(64-__builtin_clzl(W-1))) * (1UL<<(64-__builtin_clzl(H-1))) * bpp ));

  id<MTLTexture> tex=[dev newTextureWithDescriptor:td];
  if(!tex){ printf("TEX_FAIL\n"); return 1; }
  id<MTLCommandQueue> q=[dev newCommandQueue];

  // marker write kernel: texel(x,y) = coordinate-encoded so a host can locate any texel uniquely.
  // r32:  v = 0xA0000000 | ((y&0x3fff)<<14) | (x&0x3fff)
  // rg32: (r,g) = (0xB0000000|x, 0xC0000000|y)
  NSError*err=nil;
  NSString*src = isRG ?
    @"#include <metal_stdlib>\nusing namespace metal;\n"
     "kernel void wr(texture2d<uint,access::write> t [[texture(0)]], uint2 gid [[thread_position_in_grid]]){"
     " t.write(uint4(0xB0000000u|gid.x, 0xC0000000u|gid.y, 0,0), gid); }\n"
    :
    @"#include <metal_stdlib>\nusing namespace metal;\n"
     "kernel void wr(texture2d<uint,access::write> t [[texture(0)]], uint2 gid [[thread_position_in_grid]]){"
     " t.write(uint4(0xA0000000u|((gid.y&0x3fff)<<14)|(gid.x&0x3fff),0,0,0), gid); }\n";
  id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
  if(!lib){ printf("COMPILE_FAIL %s\n",[[err localizedDescription]UTF8String]); return 1; }
  id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"wr"] error:&err];
  if(!pso){ printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]); return 1; }
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
  [enc setComputePipelineState:pso]; [enc setTexture:tex atIndex:0];
  NSUInteger tgx=16, tgy=16;
  [enc dispatchThreads:MTLSizeMake(W,H,1) threadsPerThreadgroup:MTLSizeMake(tgx,tgy,1)];
  [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
  printf("WRITE status=%ld\n",(long)[cb status]);

  // bind for read so the backing BO is definitely registered/resident during dump
  {
    NSString*rk=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "kernel void rd(texture2d<uint,access::read> t [[texture(0)]], device uint* o [[buffer(0)]], uint i [[thread_position_in_grid]]){ o[i]=t.read(uint2(i&7,(i>>3)&7)).x; }\n";
    id<MTLLibrary> l2=[dev newLibraryWithSource:rk options:nil error:&err];
    id<MTLComputePipelineState> p2=l2?[dev newComputePipelineStateWithFunction:[l2 newFunctionWithName:@"rd"] error:&err]:nil;
    if(p2){
      id<MTLBuffer> ob=[dev newBufferWithLength:256 options:MTLResourceStorageModeShared];
      pv("obuf",[ob gpuAddress]);
      id<MTLCommandBuffer> cb2=[q commandBuffer];
      id<MTLComputeCommandEncoder> e2=[cb2 computeCommandEncoder];
      [e2 setComputePipelineState:p2]; [e2 setTexture:tex atIndex:0]; [e2 setBuffer:ob offset:0 atIndex:0];
      [e2 dispatchThreads:MTLSizeMake(32,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
      [e2 endEncoding]; [cb2 commit]; [cb2 waitUntilCompleted];
      printf("BIND status=%ld\n",(long)[cb2 status]);
    }
  }
  if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(700000); }
  return 0;
}}
