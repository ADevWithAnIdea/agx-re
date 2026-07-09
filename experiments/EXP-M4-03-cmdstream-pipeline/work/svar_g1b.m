// svar.m — parametric OWN compute program: STORAGE-IMAGE (PBE write) descriptor RE.
// EXP-G1b objective-1. Binds ONE texture into the Metal Tier-2 auto argument buffer
// with a chosen MSL *access qualifier* (sample / read / write / read_write) and
// dispatches a tiny kernel. The knob that changes the appended descriptor block is the
// access qualifier (and format/dims); everything else is held fixed, so we can byte-diff
// the appended descriptor under the read-only tools/iotrace interposer and see exactly
// how a storage-image (access::write / read_write) binding differs from the sampled 32B
// texture descriptor (EXP-0015 / EXP-O2B).
//
// CLEAN-ROOM: OWN-SHADER + public Metal API + HW-PROBE. Our MSL, our resources (whose GPU
// VAs we print for correlation). Nothing disassembles any Apple binary. See ../../CLAUDE.md.
//
// Build (device): clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o svar svar.m
//   (arm64e so the iotrace interposer arch matches — macOS 26 requirement.)
//
// Usage:
//   svar [--fmt F] [--access A] [--w W] [--h H] [--bb] [--dump]
//     --fmt    : rgba8 (default) | r32f | rgba32f | rg16f | r16f | rgba16f | r32u | rg32f
//     --access : sample (default) | read | write | readwrite
//     --bb     : buffer-backed shared texture (linear) so its surface VA is printable &
//                the written pixels are read back (HW-validate the write). Default: Private.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void print_va(const char*l,uint64_t va){ printf("VA %-10s = 0x%016llx\n",l,(unsigned long long)va); }

static MTLPixelFormat pfmt(const char*s,int*bpp,const char**comp){
  if(!strcmp(s,"r32f")){    *bpp=4;  *comp="float"; return MTLPixelFormatR32Float; }
  if(!strcmp(s,"rgba32f")){ *bpp=16; *comp="float"; return MTLPixelFormatRGBA32Float; }
  if(!strcmp(s,"rg16f")){   *bpp=4;  *comp="float"; return MTLPixelFormatRG16Float; }
  if(!strcmp(s,"r16f")){    *bpp=2;  *comp="float"; return MTLPixelFormatR16Float; }
  if(!strcmp(s,"rgba16f")){ *bpp=8;  *comp="float"; return MTLPixelFormatRGBA16Float; }
  if(!strcmp(s,"rg32f")){   *bpp=8;  *comp="float"; return MTLPixelFormatRG32Float; }
  if(!strcmp(s,"r32u")){    *bpp=4;  *comp="uint";  return MTLPixelFormatR32Uint; }
  *bpp=4; *comp="float"; return MTLPixelFormatRGBA8Unorm; // rgba8 default
}

int main(int argc,char**argv){ @autoreleasepool {
  const char*fmt="rgba8",*access="sample"; long W=64,H=64; int bb=0,doDump=0;
  for(int i=1;i<argc;i++){ const char*a=argv[i];
    #define ARG(f) (!strcmp(a,f)&&i+1<argc)
    if(ARG("--fmt")) fmt=argv[++i];
    else if(ARG("--access")) access=argv[++i];
    else if(ARG("--w")) W=strtol(argv[++i],0,0);
    else if(ARG("--h")) H=strtol(argv[++i],0,0);
    else if(!strcmp(a,"--bb")) bb=1;
    else if(!strcmp(a,"--dump")) doDump=1;
    #undef ARG
  }
  int bpp=4; const char*comp="float"; MTLPixelFormat pf=pfmt(fmt,&bpp,&comp);
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\nCONFIG fmt=%s bpp=%d access=%s W=%ld H=%ld bb=%d\n",
    [[dev name] UTF8String],fmt,bpp,access,W,H,bb);

  // usage bits implied by access qualifier
  MTLTextureUsage u=MTLTextureUsageShaderRead;
  if(!strcmp(access,"write"))          u=MTLTextureUsageShaderWrite;
  else if(!strcmp(access,"readwrite")) u=MTLTextureUsageShaderRead|MTLTextureUsageShaderWrite;
  else                                 u=MTLTextureUsageShaderRead; // sample/read

  MTLTextureDescriptor* td=[MTLTextureDescriptor new];
  td.pixelFormat=pf; td.width=W; td.height=H; td.textureType=MTLTextureType2D;
  td.usage=u; td.mipmapLevelCount=1;

  id<MTLTexture> tex=nil; id<MTLBuffer> texbuf=nil; NSUInteger bpr=(NSUInteger)(W*bpp);
  if(bb){
    bpr=(bpr+255)&~255UL; // 256B row align for buffer-backed (linear) textures
    td.storageMode=MTLStorageModeShared;
    texbuf=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
    tex=[texbuf newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
    if(tex) print_va("texBuf",[texbuf gpuAddress]);
  }
  if(!tex){ td.storageMode=MTLStorageModePrivate; tex=[dev newTextureWithDescriptor:td]; texbuf=nil; }
  if(!tex){ printf("TEX_FAIL\n"); return 1; }
  printf("TEX ok bb_effective=%d storage=%ld gpuResourceID=0x%llx\n",
    (texbuf!=nil),(long)tex.storageMode,(unsigned long long)tex.gpuResourceID._impl);

  id<MTLCommandQueue> q=[dev newCommandQueue];

  // Build the kernel for the chosen access qualifier. Output buffer(0) is always bound
  // (a data buffer, inline VA in the arg buffer) so binding order is texture(0),[sampler(0)],buffer(0).
  NSString* src=nil;
  if(!strcmp(access,"sample")){
    src=[NSString stringWithFormat:
      @"#include <metal_stdlib>\nusing namespace metal;\n"
       "kernel void k(texture2d<%s, access::sample> t [[texture(0)]], sampler s [[sampler(0)]],\n"
       "  device float* o [[buffer(0)]], uint i [[thread_position_in_grid]]) {\n"
       "  float2 uv=float2((float)(i%%4)/3.0,(float)(i/4)/3.0); o[i]=float(t.sample(s,uv).x); }\n",comp];
  } else if(!strcmp(access,"read")){
    src=[NSString stringWithFormat:
      @"#include <metal_stdlib>\nusing namespace metal;\n"
       "kernel void k(texture2d<%s, access::read> t [[texture(0)]],\n"
       "  device float* o [[buffer(0)]], uint2 gid [[thread_position_in_grid]]) {\n"
       "  o[gid.y*4+gid.x]=float(t.read(gid).x); }\n",comp];
  } else if(!strcmp(access,"write")){
    src=[NSString stringWithFormat:
      @"#include <metal_stdlib>\nusing namespace metal;\n"
       "kernel void k(texture2d<%s, access::write> t [[texture(0)]],\n"
       "  device float* o [[buffer(0)]], uint2 gid [[thread_position_in_grid]]) {\n"
       "  %s4 v=%s4(%s(gid.x),%s(gid.y),%s(2),%s(3));\n"
       "  t.write(v,gid); if(gid.x==0&&gid.y==0) o[0]=42.0; }\n",comp,comp,comp,comp,comp,comp,comp];
  } else { // readwrite
    src=[NSString stringWithFormat:
      @"#include <metal_stdlib>\nusing namespace metal;\n"
       "kernel void k(texture2d<%s, access::read_write> t [[texture(0)]],\n"
       "  device float* o [[buffer(0)]], uint2 gid [[thread_position_in_grid]]) {\n"
       "  %s4 v=t.read(gid); v.x+=%s(1); t.write(v,gid); if(gid.x==0&&gid.y==0) o[0]=42.0; }\n",comp,comp,comp];
  }
  NSError* err=nil;
  id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
  if(!lib){ printf("COMPILE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
  id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"k"] error:&err];
  if(!pso){ printf("PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }

  id<MTLSamplerState> smp=nil;
  if(!strcmp(access,"sample")){
    MTLSamplerDescriptor* sd=[MTLSamplerDescriptor new];
    sd.minFilter=MTLSamplerMinMagFilterNearest; sd.magFilter=MTLSamplerMinMagFilterNearest;
    sd.normalizedCoordinates=YES;
    smp=[dev newSamplerStateWithDescriptor:sd];
  }
  id<MTLBuffer> obuf=[dev newBufferWithLength:64*4 options:MTLResourceStorageModeShared];
  print_va("obuf", obuf.gpuAddress);

  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
  [enc setComputePipelineState:pso];
  [enc setTexture:tex atIndex:0];
  if(smp) [enc setSamplerState:smp atIndex:0];
  [enc setBuffer:obuf offset:0 atIndex:0];
  // dispatch a small 4x4 grid (in threads)
  [enc dispatchThreads:MTLSizeMake(4,4,1) threadsPerThreadgroup:MTLSizeMake(4,4,1)];
  [enc endEncoding];
  [cb commit]; [cb waitUntilCompleted];
  printf("SUBMIT status=%ld\n",(long)[cb status]);
  if([cb status]!=MTLCommandBufferStatusCompleted && [cb error])
    printf("CB_ERROR %s\n",[[[cb error] localizedDescription] UTF8String]);

  // HW-validate a write: read back the first row of a buffer-backed float texture.
  if(texbuf && (pf==MTLPixelFormatR32Float) && (!strcmp(access,"write")||!strcmp(access,"readwrite"))){
    float* p=(float*)[texbuf contents];
    printf("WROTE row0(r32f):");
    for(int x=0;x<(W<8?(int)W:8);x++) printf(" %.2f",p[x]);
    printf("\n");
  }
  if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
  return 0;
}}
