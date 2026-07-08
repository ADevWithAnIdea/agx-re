// texprobe.m — EXP-0017 texture tiling/twiddle probe (HW-PROBE + DATA-TRACE).
//
// Creates a 2D texture in the GPU's OPTIMAL (private/twiddled) layout — a plain
// newTextureWithDescriptor: texture, StorageModeShared so its backing BO is
// CPU-mapped and thus captured by the read-only tools/iotrace interposer — then
// GPU-writes a KNOWN PATTERN where texel (x,y) holds an encoding of (x,y) (via a
// compute image store), binds the texture into the Tier-2 argument buffer (so the
// descriptor's base VA + layout flags + secondary VA are captured), dispatches,
// and SIGUSR1-dumps every registered BO. Host-side twiddle.py then maps physical
// byte offsets -> texel (x,y) to infer the tiling/twiddle order.
//
// CLEAN-ROOM: HW-PROBE (known pattern in, raw layout out) + OWN-SHADER (our MSL) +
// DATA-TRACE (our own process's BOs via iotrace). No Apple binary is disassembled.
// See ../../CLAUDE.md.
//
// Build (device): clang -fobjc-arc -framework Metal -framework Foundation -o texprobe texprobe.m
//
// Usage: texprobe --fmt r32uint --w 64 --h 64 [--linear] [--priv] [--mips N]
//                 [--render] [--nowrite] [--usage rw|read|rt] --dump

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void print_va(const char *label, uint64_t va){
  printf("VA %-12s = 0x%016llx\n", label, (unsigned long long)va);
}

typedef struct { const char *name; MTLPixelFormat pf; int bpp; int chans; } Fmt;
static const Fmt FMTS[] = {
  {"r8uint",     MTLPixelFormatR8Uint,      1, 1},
  {"r16uint",    MTLPixelFormatR16Uint,     2, 1},
  {"r32uint",    MTLPixelFormatR32Uint,     4, 1},
  {"rg32uint",   MTLPixelFormatRG32Uint,    8, 2},
  {"rgba8uint",  MTLPixelFormatRGBA8Uint,   4, 4},
  {"rgba16uint", MTLPixelFormatRGBA16Uint,  8, 4},
  {"rgba32uint", MTLPixelFormatRGBA32Uint, 16, 4},
  {"rgba8unorm", MTLPixelFormatRGBA8Unorm,  4, 4}, // for render/compression path
  {"r32float",   MTLPixelFormatR32Float,    4, 1},
};
static const int NFMT = sizeof(FMTS)/sizeof(FMTS[0]);
static const Fmt *findFmt(const char*n){ for(int i=0;i<NFMT;i++) if(!strcmp(FMTS[i].name,n)) return &FMTS[i]; return NULL; }

// Per-format compute write kernel: texel(x,y) <- encode(x,y).
static NSString *genWriteKernel(const char*fmt){
  const char *body;
  if(!strcmp(fmt,"r8uint"))        body="uint v=(y*t.get_width()+x)&0xff; t.write(uint4(v,0,0,0),gid);";
  else if(!strcmp(fmt,"r16uint"))  body="uint v=((y&0xff)<<8)|(x&0xff); t.write(uint4(v,0,0,0),gid);";
  else if(!strcmp(fmt,"r32uint"))  body="uint v=0xA5000000u|((y&0xfff)<<12)|(x&0xfff); t.write(uint4(v,0,0,0),gid);";
  else if(!strcmp(fmt,"rg32uint")) body="t.write(uint4(x,y,0,0),gid);";
  else if(!strcmp(fmt,"rgba8uint"))body="t.write(uint4(x&0xff,y&0xff,0xab,0xcd),gid);";
  else if(!strcmp(fmt,"rgba16uint"))body="t.write(uint4(x,y,0xbeef,0xf00d),gid);";
  else if(!strcmp(fmt,"rgba32uint"))body="t.write(uint4(x,y,0xcafebabe,0xdeadbeef),gid);";
  else body="t.write(uint4((y<<16)|x,0,0,0),gid);";
  return [NSString stringWithFormat:
    @"#include <metal_stdlib>\nusing namespace metal;\n"
     "kernel void wr(texture2d<uint, access::write> t [[texture(0)]],\n"
     "  uint2 gid [[thread_position_in_grid]]) {\n"
     "  uint x=gid.x, y=gid.y; %s }\n", body];
}

// Render path: fragment shader writes encode(x,y) using pixel position, for the
// COMPRESSION probe (render target -> lossless compression may engage).
// noise=0: smooth gradient (compresses well); noise=1: high-entropy hash (should
// resist compression -> per-block aux state should differ).
static NSString *genRenderSrc(int noise){
  const char *body =
    noise==2 ?
     // split: left of x=32 constant (compressible), right = noise (incompressible)
     "uint h=(x*73856093u)^(y*19349663u); h^=h>>13; h*=0x5bd1e995u; h^=h>>15;\n"
     "  if(x<32) return float4(0.5,0.5,0.5,1.0);\n"
     "  return float4(float(h&0xff)/255.0, float((h>>8)&0xff)/255.0,\n"
     "                float((h>>16)&0xff)/255.0, float((h>>24)&0xff)/255.0);" :
    noise==1 ?
     "uint h=(x*73856093u)^(y*19349663u); h^=h>>13; h*=0x5bd1e995u; h^=h>>15;\n"
     "  return float4(float(h&0xff)/255.0, float((h>>8)&0xff)/255.0,\n"
     "                float((h>>16)&0xff)/255.0, float((h>>24)&0xff)/255.0);" :
     "return float4(float(x&0xff)/255.0, float(y&0xff)/255.0, 170.0/255.0, 205.0/255.0);";
  return [NSString stringWithFormat:
     @"#include <metal_stdlib>\nusing namespace metal;\n"
      "struct VO { float4 pos [[position]]; };\n"
      "vertex VO v_main(uint vid [[vertex_id]]) {\n"
      "  float2 p[3]={float2(-1,-3),float2(-1,1),float2(3,1)};\n"
      "  VO o; o.pos=float4(p[vid],0,1); return o; }\n"
      "fragment float4 f_main(VO in [[stage_in]]) {\n"
      "  uint x=uint(in.pos.x), y=uint(in.pos.y); %s }\n", body];
}

int main(int argc, char**argv){
 @autoreleasepool{
  const char *fmtname="r32uint"; long W=64,H=64,mips=1; int linear=0, priv=0, doDump=0;
  int render=0, nowrite=0, noise=0; const char*usage="rw";
  for(int i=1;i<argc;i++){ const char*a=argv[i];
    #define ARG(f) (!strcmp(a,f)&&i+1<argc)
    if(ARG("--fmt")) fmtname=argv[++i];
    else if(ARG("--w")) W=strtol(argv[++i],0,0);
    else if(ARG("--h")) H=strtol(argv[++i],0,0);
    else if(ARG("--mips")) mips=strtol(argv[++i],0,0);
    else if(ARG("--usage")) usage=argv[++i];
    else if(!strcmp(a,"--linear")) linear=1;
    else if(!strcmp(a,"--priv")) priv=1;
    else if(!strcmp(a,"--render")) render=1;
    else if(!strcmp(a,"--noise")) noise=1;
    else if(!strcmp(a,"--split")) noise=2;
    else if(!strcmp(a,"--nowrite")) nowrite=1;
    else if(!strcmp(a,"--dump")) doDump=1;
    #undef ARG
  }
  const Fmt *F=findFmt(fmtname);
  if(!F){ printf("UNKNOWN_FMT %s\n",fmtname); return 2; }

  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\n",[[dev name] UTF8String]);
  printf("CONFIG fmt=%s W=%ld H=%ld bpp=%d mips=%ld linear=%d priv=%d render=%d usage=%s\n",
    F->name,W,H,F->bpp,mips,linear,priv,render,usage);
  (void)noise;

  MTLTextureDescriptor *td=[MTLTextureDescriptor new];
  td.pixelFormat=F->pf; td.width=W; td.height=H; td.depth=1;
  td.mipmapLevelCount=mips; td.textureType=MTLTextureType2D;
  td.storageMode = priv? MTLStorageModePrivate : MTLStorageModeShared;
  if(!strcmp(usage,"read")) td.usage=MTLTextureUsageShaderRead;
  else if(!strcmp(usage,"rt")) td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead;
  else td.usage=MTLTextureUsageShaderRead|MTLTextureUsageShaderWrite;

  id<MTLTexture> tex=nil; id<MTLBuffer> texbuf=nil;
  NSUInteger bpr=0;
  if(linear){
    NSUInteger align=[dev minimumLinearTextureAlignmentForPixelFormat:F->pf];
    bpr=W*F->bpp; if(align){ bpr=((bpr+align-1)/align)*align; }
    NSUInteger total=bpr*H+0x4000;
    texbuf=[dev newBufferWithLength:total options:MTLResourceStorageModeShared];
    memset([texbuf contents],0,total);
    print_va("texbuf",[texbuf gpuAddress]);
    printf("LINEAR bpr=0x%lx total=0x%lx\n",(unsigned long)bpr,(unsigned long)total);
    tex=[texbuf newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
  } else {
    tex=[dev newTextureWithDescriptor:td];
  }
  if(!tex){ printf("TEX_FAIL\n"); return 1; }
  printf("TEX ok\n");

  id<MTLCommandQueue> q=[dev newCommandQueue];

  if(mips>1 && !render && !nowrite){
    // ---- mip probe: write each level with a level-tagged pattern via write(...,lod) ----
    NSError *err=nil;
    NSString *mk=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "kernel void wrm(texture2d<uint, access::write> t [[texture(0)]],\n"
      "  constant uint& L [[buffer(0)]], uint2 gid [[thread_position_in_grid]]) {\n"
      "  uint x=gid.x,y=gid.y; uint v=0xB0000000u|(L<<24)|((y&0xfff)<<12)|(x&0xfff);\n"
      "  t.write(uint4(v,0,0,0), gid, L); }\n";
    id<MTLLibrary> lib=[dev newLibraryWithSource:mk options:nil error:&err];
    if(!lib){ printf("COMPILE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
    id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"wrm"] error:&err];
    if(!pso){ printf("PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
    [enc setComputePipelineState:pso];
    [enc setTexture:tex atIndex:0];
    for(long L=0;L<mips;L++){
      long lw=W>>L, lh=H>>L; if(lw<1)lw=1; if(lh<1)lh=1;
      uint32_t Lv=(uint32_t)L; id<MTLBuffer> lb=[dev newBufferWithBytes:&Lv length:4 options:MTLResourceStorageModeShared];
      [enc setBuffer:lb offset:0 atIndex:0];
      NSUInteger tgx=lw<32?lw:32, tgy=lh<32?lh:32; if(tgx*tgy>1024)tgy=1024/tgx;
      [enc dispatchThreads:MTLSizeMake(lw,lh,1) threadsPerThreadgroup:MTLSizeMake(tgx?tgx:1,tgy?tgy:1,1)];
    }
    [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
    printf("MIPWRITE done status=%ld\n",(long)[cb status]);
  } else if(render && !nowrite){
    // ---- render a known pattern into the texture (compression probe) ----
    NSError *err=nil;
    id<MTLLibrary> lib=[dev newLibraryWithSource:genRenderSrc(noise) options:nil error:&err];
    if(!lib){ printf("COMPILE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
    MTLRenderPipelineDescriptor *rpd=[MTLRenderPipelineDescriptor new];
    rpd.vertexFunction=[lib newFunctionWithName:@"v_main"];
    rpd.fragmentFunction=[lib newFunctionWithName:@"f_main"];
    rpd.colorAttachments[0].pixelFormat=F->pf;
    id<MTLRenderPipelineState> rps=[dev newRenderPipelineStateWithDescriptor:rpd error:&err];
    if(!rps){ printf("RPIPE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
    MTLRenderPassDescriptor *rp=[MTLRenderPassDescriptor renderPassDescriptor];
    rp.colorAttachments[0].texture=tex;
    rp.colorAttachments[0].loadAction=MTLLoadActionClear;
    rp.colorAttachments[0].storeAction=MTLStoreActionStore;
    rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,0);
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:rps];
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [enc endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    printf("RENDER done status=%ld\n",(long)[cb status]);
    if([cb status]!=MTLCommandBufferStatusCompleted && [cb error])
      printf("CB_ERROR %s\n",[[[cb error] localizedDescription] UTF8String]);
  } else if(!nowrite){
    // ---- compute image-store of the known (x,y) pattern ----
    NSError *err=nil;
    id<MTLLibrary> lib=[dev newLibraryWithSource:genWriteKernel(F->name) options:nil error:&err];
    if(!lib){ printf("COMPILE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
    id<MTLFunction> fn=[lib newFunctionWithName:@"wr"];
    id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:fn error:&err];
    if(!pso){ printf("PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
    [enc setComputePipelineState:pso];
    [enc setTexture:tex atIndex:0];
    NSUInteger tgx=W<32?W:32, tgy=H<32?H:32; if(tgx*tgy>1024) tgy=1024/tgx;
    [enc dispatchThreads:MTLSizeMake(W,H,1) threadsPerThreadgroup:MTLSizeMake(tgx,tgy,1)];
    [enc endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    printf("WRITE done status=%ld\n",(long)[cb status]);
    if([cb status]!=MTLCommandBufferStatusCompleted && [cb error])
      printf("CB_ERROR %s\n",[[[cb error] localizedDescription] UTF8String]);
  }

  // ---- bind the texture into a Tier-2 argument buffer via a tiny read kernel so
  //      the DESCRIPTOR (base VA, layout flags, secondary VA) is captured. ----
  {
    NSError *err=nil;
    NSString *rk=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "kernel void rd(texture2d<uint, access::read> t [[texture(0)]],\n"
      "  device uint* o [[buffer(0)]], uint i [[thread_position_in_grid]]) {\n"
      "  o[i]=t.read(uint2(i&7,(i>>3)&7)).x; }\n";
    // for float/unorm/render formats use float sampling variant
    if(!strcmp(F->name,"rgba8unorm")||!strcmp(F->name,"r32float"))
      rk=@"#include <metal_stdlib>\nusing namespace metal;\n"
        "kernel void rd(texture2d<float, access::read> t [[texture(0)]],\n"
        "  device float* o [[buffer(0)]], uint i [[thread_position_in_grid]]) {\n"
        "  o[i]=t.read(uint2(i&7,(i>>3)&7)).x; }\n";
    id<MTLLibrary> lib=[dev newLibraryWithSource:rk options:nil error:&err];
    id<MTLFunction> fn=[lib newFunctionWithName:@"rd"];
    id<MTLComputePipelineState> pso=fn?[dev newComputePipelineStateWithFunction:fn error:&err]:nil;
    if(pso){
      id<MTLBuffer> obuf=[dev newBufferWithLength:64*4 options:MTLResourceStorageModeShared];
      print_va("obuf",[obuf gpuAddress]);
      id<MTLCommandBuffer> cb=[q commandBuffer];
      id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
      [enc setComputePipelineState:pso];
      [enc setTexture:tex atIndex:0];
      [enc setBuffer:obuf offset:0 atIndex:0];
      [enc dispatchThreads:MTLSizeMake(64,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
      [enc endEncoding];
      [cb commit]; [cb waitUntilCompleted];
      printf("BIND done status=%ld\n",(long)[cb status]);
      // print first 8 read-back texels (sanity: matches pattern for linear/twiddle at (i&7,(i>>3)&7))
      uint32_t *op=(uint32_t*)[obuf contents];
      printf("READBACK");
      for(int i=0;i<8;i++) printf(" %08x",op[i]);
      printf("\n");
    } else {
      printf("BIND_SKIP %s\n", err?[[err localizedDescription] UTF8String]:"");
    }
  }

  if(linear && texbuf){
    // dump the linear reference bytes directly (ground truth) — first rows
    unsigned char *p=(unsigned char*)[texbuf contents];
    printf("LINEAR_HEAD");
    for(int i=0;i<64 && i<(int)bpr;i++) printf(" %02x",p[i]);
    printf("\n");
  }

  if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(500000); }
  return 0;
 }
}
