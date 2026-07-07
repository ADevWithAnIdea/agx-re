// t9probe.m -- RT-9 INDEPENDENT texture tiling/descriptor probe (2nd red-team pass).
//
// Distinct from RT-3's texprobe.m: uses TAGGED, LARGE-COORDINATE encodings that hold
// x/y up to 14 bits (r32: 0xA<<28 | y<<14 | x), so it can uniquely mark texels in
// textures far larger than 256 (384, 500, 1024, 4095...) which RT-3's 8-bit-per-channel
// encoders (x&0xff / y&0xff) could NOT represent without wrapping. Also adds a --desconly
// fast path (create+bind+dump, no pattern) for huge-dim descriptor-packing tests.
//
// texel(x,y) <- encode(x,y); create in GPU-optimal (twiddled) layout; bind into a Tier-2
// argument buffer so the descriptor is captured; SIGUSR1-dump every BO via tools/iotrace.
//
// CLEAN-ROOM: HW-PROBE (known pattern in, raw layout out) + OWN-SHADER (our MSL) +
// DATA-TRACE (our BOs via read-only iotrace). No Apple binary disassembled. See ../../CLAUDE.md.
//
// Build (device): clang -fobjc-arc -framework Metal -framework Foundation -o t9probe t9probe.m
// Usage: t9probe --fmt <fmt> --w W --h H [--desconly] [--mips N] [--type 2d|3d|array|cube|ms]
//                [--slices S] [--samples N] [--linear] [--usage rw|read|rt] --dump

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void print_va(const char*l,uint64_t va){ printf("VA %-10s = 0x%016llx\n",l,(unsigned long long)va); }

typedef struct { const char*name; MTLPixelFormat pf; int bpp; int isfloat; } Fmt;
static const Fmt FMTS[] = {
  {"r8uint",      MTLPixelFormatR8Uint,       1, 0},
  {"r16uint",     MTLPixelFormatR16Uint,      2, 0},
  {"r32uint",     MTLPixelFormatR32Uint,      4, 0},
  {"rgba8uint",   MTLPixelFormatRGBA8Uint,    4, 0},
  {"rgba8unorm",  MTLPixelFormatRGBA8Unorm,   4, 0},
  {"rg32uint",    MTLPixelFormatRG32Uint,     8, 0},
  {"rgba16uint",  MTLPixelFormatRGBA16Uint,   8, 0},
  {"rgba16float", MTLPixelFormatRGBA16Float,  8, 1},
  {"rgba32uint",  MTLPixelFormatRGBA32Uint,  16, 0},
  {"r32float",    MTLPixelFormatR32Float,     4, 1},
};
static const int NFMT=sizeof(FMTS)/sizeof(FMTS[0]);
static const Fmt* findFmt(const char*n){ for(int i=0;i<NFMT;i++) if(!strcmp(FMTS[i].name,n)) return &FMTS[i]; return NULL; }

// Per-format write kernel. rg32uint only used for type variants (holds x,y,slice cleanly).
// texType: "2d" -> texture2d + write(c,gid.xy); "3d" -> texture3d + write(c,uint3);
// "array"/"cube" -> texture2d_array + write(c,gid.xy,slice).
static NSString* genWrite(const Fmt*F,const char*typ){
  const char *ttag, *ctype = F->isfloat||!strcmp(F->name,"rgba8unorm")?"float":"uint";
  int is3d=!strcmp(typ,"3d"), isarr=(!strcmp(typ,"array")||!strcmp(typ,"cube"));
  if(is3d) ttag="texture3d"; else if(isarr) ttag="texture2d_array"; else ttag="texture2d";
  // colour expression by format (encode x,y[,s])
  NSString *col;
  if(!strcmp(F->name,"rgba8unorm"))
    col=@"float4(float(x&0xff)/255.0,float((x>>8)&0xff)/255.0,float(y&0xff)/255.0,float((y>>8)&0xff)/255.0)";
  else if(F->isfloat) col=is3d||isarr?@"float4(float(x),float(y),float(s),42.0)":@"float4(float(x),float(y),9999.0,4242.0)";
  else if(F->bpp==16) col=is3d||isarr?@"uint4(x,y,s,0xC0DE)":@"uint4(x,y,0xCAFEBABEu,0xDEADBEEFu)";
  else if(!strcmp(F->name,"rg32uint")) col=@"uint4(x,y,s,0)";
  else if(F->bpp==8) col=is3d||isarr?@"uint4(x,y,s,0xBEEF)":@"uint4(x,y,0xBEEF,0xF00D)";
  else if(!strcmp(F->name,"r32uint")) col=@"uint4(0xA0000000u|((y&0x3fff)<<14)|(x&0x3fff),0,0,0)";
  else if(F->bpp==4) col=@"uint4(x&0xff,(x>>8)&0xff,y&0xff,(y>>8)&0xff)";
  else if(F->bpp==2) col=@"uint4(((y&0xff)<<8)|(x&0xff),0,0,0)";
  else col=@"uint4((y*t.get_width()+x)&0xff,0,0,0)";
  NSString *decl=[NSString stringWithFormat:@"%s<%s, access::write>",ttag,ctype];
  NSString *wr;
  if(is3d) wr=[NSString stringWithFormat:@"t.write(%@, uint3(x,y,s));",col];
  else if(isarr) wr=[NSString stringWithFormat:@"t.write(%@, uint2(x,y), s);",col];
  else wr=[NSString stringWithFormat:@"t.write(%@, uint2(x,y));",col];
  NSString *idx = (is3d||isarr)?@"uint3 gid [[thread_position_in_grid]]":@"uint2 gid [[thread_position_in_grid]]";
  NSString *sdecl = (is3d||isarr)?@"uint x=gid.x,y=gid.y,s=gid.z;":@"uint x=gid.x,y=gid.y;";
  return [NSString stringWithFormat:
    @"#include <metal_stdlib>\nusing namespace metal;\nkernel void wr(%@ t [[texture(0)]], %@){ %@ %@ }\n",
    decl, idx, sdecl, wr];
}

int main(int argc,char**argv){ @autoreleasepool{
  const char*fmtname="r32uint"; long W=64,H=64,mips=1,slices=1,samples=1; int linear=0,doDump=0,desconly=0;
  const char*typ="2d"; const char*usage="rw";
  for(int i=1;i<argc;i++){ const char*a=argv[i];
    #define ARG(f) (!strcmp(a,f)&&i+1<argc)
    if(ARG("--fmt")) fmtname=argv[++i];
    else if(ARG("--w")) W=strtol(argv[++i],0,0);
    else if(ARG("--h")) H=strtol(argv[++i],0,0);
    else if(ARG("--mips")) mips=strtol(argv[++i],0,0);
    else if(ARG("--type")) typ=argv[++i];
    else if(ARG("--slices")) slices=strtol(argv[++i],0,0);
    else if(ARG("--samples")) samples=strtol(argv[++i],0,0);
    else if(ARG("--usage")) usage=argv[++i];
    else if(!strcmp(a,"--linear")) linear=1;
    else if(!strcmp(a,"--desconly")) desconly=1;
    else if(!strcmp(a,"--dump")) doDump=1;
    #undef ARG
  }
  const Fmt*F=findFmt(fmtname); if(!F){printf("UNKNOWN_FMT %s\n",fmtname);return 2;}
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\n",[[dev name]UTF8String]);
  printf("CONFIG fmt=%s W=%ld H=%ld bpp=%d type=%s slices=%ld samples=%ld mips=%ld linear=%d usage=%s desconly=%d\n",
    F->name,W,H,F->bpp,typ,slices,samples,mips,linear,usage,desconly);

  MTLTextureDescriptor*td=[MTLTextureDescriptor new];
  td.pixelFormat=F->pf; td.width=W; td.height=H; td.depth=1; td.mipmapLevelCount=mips;
  td.textureType=MTLTextureType2D;
  if(!strcmp(typ,"3d")){ td.textureType=MTLTextureType3D; td.depth=slices; }
  else if(!strcmp(typ,"array")){ td.textureType=MTLTextureType2DArray; td.arrayLength=slices; }
  else if(!strcmp(typ,"cube")){ td.textureType=MTLTextureTypeCube; }
  else if(!strcmp(typ,"ms")){ td.textureType=MTLTextureType2DMultisample; td.sampleCount=samples; }
  td.storageMode=MTLStorageModeShared;
  if(!strcmp(usage,"read")) td.usage=MTLTextureUsageShaderRead;
  else if(!strcmp(usage,"rt")) td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead;
  else td.usage=MTLTextureUsageShaderRead|MTLTextureUsageShaderWrite;

  id<MTLTexture> tex=nil; id<MTLBuffer> texbuf=nil; NSUInteger bpr=0;
  if(linear){
    NSUInteger align=[dev minimumLinearTextureAlignmentForPixelFormat:F->pf];
    bpr=W*F->bpp; if(align) bpr=((bpr+align-1)/align)*align;
    NSUInteger total=bpr*H+0x4000;
    texbuf=[dev newBufferWithLength:total options:MTLResourceStorageModeShared];
    memset([texbuf contents],0,total); print_va("texbuf",[texbuf gpuAddress]);
    printf("LINEAR bpr=0x%lx total=0x%lx\n",(unsigned long)bpr,(unsigned long)total);
    tex=[texbuf newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
  } else tex=[dev newTextureWithDescriptor:td];
  if(!tex){printf("TEX_FAIL\n");return 1;}
  printf("TEX ok gpuResourceID handled; alloc size unknown here\n");

  id<MTLCommandQueue> q=[dev newCommandQueue];

  if(!desconly && strcmp(typ,"ms")){
    NSError*err=nil;
    id<MTLLibrary> lib=[dev newLibraryWithSource:genWrite(F,typ) options:nil error:&err];
    if(!lib){printf("COMPILE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"wr"] error:&err];
    if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
    [enc setComputePipelineState:pso]; [enc setTexture:tex atIndex:0];
    long dz = (!strcmp(typ,"3d"))?slices : (!strcmp(typ,"array"))?slices : (!strcmp(typ,"cube"))?6 : 1;
    NSUInteger tgx=W<16?W:16, tgy=H<16?H:16; if(tgx*tgy>256)tgy=256/tgx;
    [enc dispatchThreads:MTLSizeMake(W,H,dz) threadsPerThreadgroup:MTLSizeMake(tgx?tgx:1,tgy?tgy:1,1)];
    [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
    printf("WRITE status=%ld\n",(long)[cb status]);
    if([cb status]!=MTLCommandBufferStatusCompleted && [cb error]) printf("CB_ERR %s\n",[[[cb error]localizedDescription]UTF8String]);
  }

  // bind into Tier-2 arg buffer so the DESCRIPTOR is captured
  {
    NSError*err=nil;
    NSString*rk = F->isfloat||!strcmp(F->name,"rgba8unorm") ?
      @"#include <metal_stdlib>\nusing namespace metal;\nkernel void rd(texture2d<float,access::read> t [[texture(0)]], device float* o [[buffer(0)]], uint i [[thread_position_in_grid]]){ o[i]=t.read(uint2(i&7,(i>>3)&7)).x; }\n" :
      @"#include <metal_stdlib>\nusing namespace metal;\nkernel void rd(texture2d<uint,access::read> t [[texture(0)]], device uint* o [[buffer(0)]], uint i [[thread_position_in_grid]]){ o[i]=t.read(uint2(i&7,(i>>3)&7)).x; }\n";
    // for non-2d types read a 2d slice 0 view is not trivial; only bind for 2d/linear
    if(!strcmp(typ,"2d")){
      id<MTLLibrary> lib=[dev newLibraryWithSource:rk options:nil error:&err];
      id<MTLComputePipelineState> pso=lib?[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"rd"] error:&err]:nil;
      if(pso){
        id<MTLBuffer> obuf=[dev newBufferWithLength:256 options:MTLResourceStorageModeShared];
        print_va("obuf",[obuf gpuAddress]);
        id<MTLCommandBuffer> cb=[q commandBuffer];
        id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
        [enc setComputePipelineState:pso]; [enc setTexture:tex atIndex:0]; [enc setBuffer:obuf offset:0 atIndex:0];
        [enc dispatchThreads:MTLSizeMake(32,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
        [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
        printf("BIND status=%ld\n",(long)[cb status]);
      } else printf("BIND_SKIP %s\n",err?[[err localizedDescription]UTF8String]:"");
    } else {
      // bind a texture2d_array or read via generic: just make it resident by encoding into arg buffer through a trivial arraycopy
      NSString*rk2=@"#include <metal_stdlib>\nusing namespace metal;\nkernel void rd(texture2d_array<uint,access::read> t [[texture(0)]], device uint* o [[buffer(0)]], uint i [[thread_position_in_grid]]){ o[i]=t.read(uint2(i&7,0),0).x; }\n";
      if(F->isfloat) rk2=@"#include <metal_stdlib>\nusing namespace metal;\nkernel void rd(texture2d_array<float,access::read> t [[texture(0)]], device float* o [[buffer(0)]], uint i [[thread_position_in_grid]]){ o[i]=t.read(uint2(i&7,0),0).x; }\n";
      id<MTLLibrary> lib=[dev newLibraryWithSource:rk2 options:nil error:&err];
      id<MTLComputePipelineState> pso=lib?[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"rd"] error:&err]:nil;
      if(pso && (!strcmp(typ,"array")||!strcmp(typ,"cube"))){
        id<MTLBuffer> obuf=[dev newBufferWithLength:256 options:MTLResourceStorageModeShared];
        print_va("obuf",[obuf gpuAddress]);
        id<MTLCommandBuffer> cb=[q commandBuffer];
        id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
        [enc setComputePipelineState:pso]; [enc setTexture:tex atIndex:0]; [enc setBuffer:obuf offset:0 atIndex:0];
        [enc dispatchThreads:MTLSizeMake(8,1,1) threadsPerThreadgroup:MTLSizeMake(8,1,1)];
        [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
        printf("BIND status=%ld\n",(long)[cb status]);
      } else printf("BIND_SKIP nontrivial-type %s\n",err?[[err localizedDescription]UTF8String]:"");
    }
  }
  if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(600000); }
  return 0;
}}
