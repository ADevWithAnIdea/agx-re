// cmip.m — EXP-O2G part 3: compression x mipmap / NPOT probe.
//
// Creates a batch of textures (one per WxHxMIPS spec), each in the GPU OPTIMAL
// (twiddled, non-buffer-backed) layout, StorageModeShared (so the backing BO is
// CPU-mapped and captured by the read-only tools/iotrace interposer), with a usage
// that KEEPS lossless compression eligible (ShaderRead[+RenderTarget], no ShaderWrite,
// no PixelFormatView -- per docs/tiling/README.md §4.1 & EXP-O2B). It binds ALL of them
// into ONE Tier-2 argument buffer via a generated read kernel and dispatches once, then
// SIGUSR1-dumps every BO. The host analyzer (texdesc.py) reads each 32-byte texture
// descriptor (word1 bit26 mipmap / bit27 compression-aux / word3 bit31 aux-metadata /
// word4+word5 secondary aux VA) and matches each base VA to a captured BO to get the
// total backing size -> answers: does aux cover ALL mip levels? aux size vs image size?
// what is the NPOT/small-size compression threshold?
//
// CLEAN-ROOM: HW-PROBE + DATA-TRACE + OWN-SHADER. No Apple binary disassembled. See ../../CLAUDE.md.
//
// Build (device): clang -fobjc-arc -framework Metal -framework Foundation -o cmip cmip.m
// Usage: cmip --specs "16x16x1,8x8x1,128x128x8,..." [--fmt rgba8unorm] [--usage rt|read] [--render] [--dump]

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void print_va(const char *label, uint64_t va){
  printf("VA %-14s = 0x%016llx\n", label, (unsigned long long)va);
}

typedef struct { const char *name; MTLPixelFormat pf; int bpp; } Fmt;
static const Fmt FMTS[] = {
  {"rgba8unorm", MTLPixelFormatRGBA8Unorm, 4},
  {"bgra8unorm", MTLPixelFormatBGRA8Unorm, 4},
  {"r8unorm",    MTLPixelFormatR8Unorm,    1},
  {"rg8unorm",   MTLPixelFormatRG8Unorm,   2},
  {"rgba16f",    MTLPixelFormatRGBA16Float,8},
  {"rgba32f",    MTLPixelFormatRGBA32Float,16},
  {"r32f",       MTLPixelFormatR32Float,   4},
};
static const int NFMT = sizeof(FMTS)/sizeof(FMTS[0]);
static const Fmt *findFmt(const char*n){ for(int i=0;i<NFMT;i++) if(!strcmp(FMTS[i].name,n)) return &FMTS[i]; return NULL; }

int main(int argc, char**argv){
 @autoreleasepool{
  const char *specs="16x16x1"; const char *fmtname="rgba8unorm"; const char*usage="rt";
  int doDump=0, doRender=0;
  for(int i=1;i<argc;i++){ const char*a=argv[i];
    if(!strcmp(a,"--specs")&&i+1<argc) specs=argv[++i];
    else if(!strcmp(a,"--fmt")&&i+1<argc) fmtname=argv[++i];
    else if(!strcmp(a,"--usage")&&i+1<argc) usage=argv[++i];
    else if(!strcmp(a,"--render")) doRender=1;
    else if(!strcmp(a,"--dump")) doDump=1;
  }
  const Fmt *F=findFmt(fmtname);
  if(!F){ printf("UNKNOWN_FMT %s\n",fmtname); return 2; }

  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\n",[[dev name] UTF8String]);
  printf("CONFIG fmt=%s bpp=%d usage=%s specs=%s\n",F->name,F->bpp,usage,specs);

  // parse specs
  int W[64],H[64],M[64],N=0;
  char buf[1024]; strncpy(buf,specs,sizeof(buf)-1); buf[sizeof(buf)-1]=0;
  for(char*tok=strtok(buf,",");tok&&N<64;tok=strtok(NULL,",")){
    int w=0,h=0,m=1; if(sscanf(tok,"%dx%dx%d",&w,&h,&m)<2){ if(sscanf(tok,"%dx%d",&w,&h)==2)m=1; else continue; }
    W[N]=w;H[N]=h;M[N]=m;N++;
  }
  if(N==0){ printf("NO_SPECS\n"); return 2; }
  printf("NSPECS %d\n",N);

  MTLTextureUsage u = (!strcmp(usage,"read")) ? MTLTextureUsageShaderRead
                     : (MTLTextureUsageShaderRead|MTLTextureUsageRenderTarget);

  id<MTLTexture> texs[64];
  for(int k=0;k<N;k++){
    MTLTextureDescriptor *td=[MTLTextureDescriptor new];
    td.pixelFormat=F->pf; td.width=W[k]; td.height=H[k]; td.depth=1;
    td.mipmapLevelCount=M[k]; td.textureType=MTLTextureType2D;
    td.storageMode=MTLStorageModeShared; td.usage=u;
    id<MTLTexture> t=[dev newTextureWithDescriptor:td];
    if(!t){ printf("TEX_FAIL k=%d %dx%dx%d\n",k,W[k],H[k],M[k]); return 1; }
    texs[k]=t;
    // Expected padded image bytes over all mips (host cross-check).
    long total=0; for(int L=0;L<M[k];L++){ long lw=W[k]>>L; if(lw<1)lw=1; long lh=H[k]>>L; if(lh<1)lh=1;
      long pw=1; while(pw<lw)pw<<=1; long ph=1; while(ph<lh)ph<<=1; long lb=(long)pw*ph*F->bpp; if(lb<0x80)lb=0x80; total+=lb; }
    printf("SPEC k=%d %dx%dx%d expImgBytes=0x%lx expAux=0x%lx expTotal=0x%lx\n",
           k,W[k],H[k],M[k],total,total/128,total+total/128);
  }

  id<MTLCommandQueue> q=[dev newCommandQueue];

  // Optionally render a smooth gradient into level 0 of every texture (engages compression
  // codec on real content). Uses a fullscreen-tri; per-texture pass.
  if(doRender){
    NSError *err=nil;
    NSString *rs=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "struct VO{float4 pos [[position]];};\n"
      "vertex VO v_main(uint vid [[vertex_id]]){ float2 p[3]={float2(-1,-3),float2(-1,1),float2(3,1)};\n"
      "  VO o; o.pos=float4(p[vid],0,1); return o; }\n"
      "fragment float4 f_main(VO in [[stage_in]]){ uint x=uint(in.pos.x),y=uint(in.pos.y);\n"
      "  return float4(float(x&0xff)/255.0, float(y&0xff)/255.0, 0.5, 1.0); }\n";
    id<MTLLibrary> lib=[dev newLibraryWithSource:rs options:nil error:&err];
    MTLRenderPipelineDescriptor *rpd=[MTLRenderPipelineDescriptor new];
    rpd.vertexFunction=[lib newFunctionWithName:@"v_main"];
    rpd.fragmentFunction=[lib newFunctionWithName:@"f_main"];
    rpd.colorAttachments[0].pixelFormat=F->pf;
    id<MTLRenderPipelineState> rps=[dev newRenderPipelineStateWithDescriptor:rpd error:&err];
    if(rps){
      for(int k=0;k<N;k++){
        MTLRenderPassDescriptor *rp=[MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture=texs[k]; rp.colorAttachments[0].level=0;
        rp.colorAttachments[0].loadAction=MTLLoadActionClear;
        rp.colorAttachments[0].storeAction=MTLStoreActionStore;
        id<MTLCommandBuffer> cb=[q commandBuffer];
        id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:rps];
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
      }
      printf("RENDER done (%d textures)\n",N);
    } else printf("RENDER_SKIP %s\n", err?[[err localizedDescription] UTF8String]:"");
  }

  // Generate a read kernel that binds all N textures, so all N descriptors are emitted
  // into one argument buffer.
  NSMutableString *k=[NSMutableString stringWithString:
    @"#include <metal_stdlib>\nusing namespace metal;\n"];
  int isFloatSample = 1; // all listed formats are float-samplable
  [k appendString:@"kernel void rd(device float* o [[buffer(0)]]"];
  for(int i=0;i<N;i++) [k appendFormat:@", texture2d<float,access::read> t%d [[texture(%d)]]",i,i];
  [k appendString:@", uint gid [[thread_position_in_grid]]) {\n  float s=0;\n"];
  for(int i=0;i<N;i++) [k appendFormat:@"  s += t%d.read(uint2(0,0)).x;\n",i];
  [k appendString:@"  o[gid]=s; }\n"];
  (void)isFloatSample;

  NSError *err=nil;
  id<MTLLibrary> lib=[dev newLibraryWithSource:k options:nil error:&err];
  if(!lib){ printf("RKERN_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
  id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"rd"] error:&err];
  if(!pso){ printf("RPSO_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }

  id<MTLBuffer> obuf=[dev newBufferWithLength:256 options:MTLResourceStorageModeShared];
  print_va("obuf",[obuf gpuAddress]);
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
  [enc setComputePipelineState:pso];
  [enc setBuffer:obuf offset:0 atIndex:0];
  for(int i=0;i<N;i++) [enc setTexture:texs[i] atIndex:i];
  [enc dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
  [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
  printf("BIND done status=%ld\n",(long)[cb status]);
  if([cb error]) printf("CB_ERROR %s\n",[[[cb error] localizedDescription] UTF8String]);

  if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(600000); }
  return 0;
 }
}
