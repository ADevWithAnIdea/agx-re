// rtfmt.m — DESC-1: capture the RENDER-TARGET attachment format word across ALL
// renderable formats. Renders a full-screen triangle into ONE buffer-backed (linear,
// shared) color RT of a chosen format, with the fragment output type matched to the
// format's data class (float/uint/sint), then SIGUSR1-dumps every BO so the 3-segment
// attachment descriptor (0x10000110000) can be located and its LOAD/RENDER/STORE
// format words byte-diffed against the sampled texture-descriptor codes.
//
// CLEAN-ROOM: OWN-SHADER + public Metal API + DATA-TRACE. Our MSL, our resources. No
// Apple binary disassembled. Build: clang -arch arm64e -fobjc-arc -framework Metal
//   -framework Foundation -o rtfmt rtfmt.m
//
// Usage: rtfmt --fmt <name> [--w W --h H] [--dump]
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void print_va(const char*l,uint64_t va){ printf("VA %-12s = 0x%016llx\n",l,(unsigned long long)va); }

typedef enum { DC_F, DC_U, DC_S } DC;
typedef struct { const char*name; MTLPixelFormat pf; int bpp; DC dc; } Fmt;
static const Fmt FMTS[] = {
  {"r8unorm",      MTLPixelFormatR8Unorm,        1, DC_F},
  {"rg8unorm",     MTLPixelFormatRG8Unorm,       2, DC_F},
  {"rgba8unorm",   MTLPixelFormatRGBA8Unorm,     4, DC_F},
  {"bgra8unorm",   MTLPixelFormatBGRA8Unorm,     4, DC_F},
  {"rgba8unorm_srgb",MTLPixelFormatRGBA8Unorm_sRGB,4,DC_F},
  {"bgra8unorm_srgb",MTLPixelFormatBGRA8Unorm_sRGB,4,DC_F},
  {"r8snorm",      MTLPixelFormatR8Snorm,        1, DC_F},
  {"rg8snorm",     MTLPixelFormatRG8Snorm,       2, DC_F},
  {"rgba8snorm",   MTLPixelFormatRGBA8Snorm,     4, DC_F},
  {"r16unorm",     MTLPixelFormatR16Unorm,       2, DC_F},
  {"rg16unorm",    MTLPixelFormatRG16Unorm,      4, DC_F},
  {"rgba16unorm",  MTLPixelFormatRGBA16Unorm,    8, DC_F},
  {"r16snorm",     MTLPixelFormatR16Snorm,       2, DC_F},
  {"rg16snorm",    MTLPixelFormatRG16Snorm,      4, DC_F},
  {"rgba16snorm",  MTLPixelFormatRGBA16Snorm,    8, DC_F},
  {"r16float",     MTLPixelFormatR16Float,       2, DC_F},
  {"rg16float",    MTLPixelFormatRG16Float,      4, DC_F},
  {"rgba16float",  MTLPixelFormatRGBA16Float,    8, DC_F},
  {"r32float",     MTLPixelFormatR32Float,       4, DC_F},
  {"rg32float",    MTLPixelFormatRG32Float,      8, DC_F},
  {"rgba32float",  MTLPixelFormatRGBA32Float,   16, DC_F},
  {"rgb10a2unorm", MTLPixelFormatRGB10A2Unorm,   4, DC_F},
  {"bgr10a2unorm", MTLPixelFormatBGR10A2Unorm,   4, DC_F},
  {"rg11b10float", MTLPixelFormatRG11B10Float,   4, DC_F},
  {"rgb9e5float",  MTLPixelFormatRGB9E5Float,    4, DC_F},
  {"bgr10_xr",     MTLPixelFormatBGR10_XR,       4, DC_F},
  {"bgra10_xr",    MTLPixelFormatBGRA10_XR,      8, DC_F},
  // integer RTs
  {"r8uint",       MTLPixelFormatR8Uint,         1, DC_U},
  {"rg8uint",      MTLPixelFormatRG8Uint,        2, DC_U},
  {"rgba8uint",    MTLPixelFormatRGBA8Uint,      4, DC_U},
  {"r16uint",      MTLPixelFormatR16Uint,        2, DC_U},
  {"rg16uint",     MTLPixelFormatRG16Uint,       4, DC_U},
  {"rgba16uint",   MTLPixelFormatRGBA16Uint,     8, DC_U},
  {"r32uint",      MTLPixelFormatR32Uint,        4, DC_U},
  {"rg32uint",     MTLPixelFormatRG32Uint,       8, DC_U},
  {"rgba32uint",   MTLPixelFormatRGBA32Uint,    16, DC_U},
  {"rgb10a2uint",  MTLPixelFormatRGB10A2Uint,    4, DC_U},
  {"r8sint",       MTLPixelFormatR8Sint,         1, DC_S},
  {"rg8sint",      MTLPixelFormatRG8Sint,        2, DC_S},
  {"rgba8sint",    MTLPixelFormatRGBA8Sint,      4, DC_S},
  {"r16sint",      MTLPixelFormatR16Sint,        2, DC_S},
  {"rg16sint",     MTLPixelFormatRG16Sint,       4, DC_S},
  {"rgba16sint",   MTLPixelFormatRGBA16Sint,     8, DC_S},
  {"r32sint",      MTLPixelFormatR32Sint,        4, DC_S},
  {"rg32sint",     MTLPixelFormatRG32Sint,       8, DC_S},
  {"rgba32sint",   MTLPixelFormatRGBA32Sint,    16, DC_S},
};
static const int NFMT=sizeof(FMTS)/sizeof(FMTS[0]);
static const Fmt* find(const char*n){ for(int i=0;i<NFMT;i++) if(!strcmp(FMTS[i].name,n)) return &FMTS[i]; return NULL; }

int main(int argc,char**argv){ @autoreleasepool {
  const char*fmtS="rgba8unorm"; long W=64,H=64; int doDump=0;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--fmt")&&i+1<argc) fmtS=argv[++i];
    else if(!strcmp(argv[i],"--w")&&i+1<argc) W=strtol(argv[++i],0,0);
    else if(!strcmp(argv[i],"--h")&&i+1<argc) H=strtol(argv[++i],0,0);
    else if(!strcmp(argv[i],"--dump")) doDump=1;
  }
  const Fmt*F=find(fmtS);
  if(!F){ printf("UNKNOWN_FMT %s\n",fmtS); return 2; }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\nCONFIG fmt=%s bpp=%d dc=%d W=%ld H=%ld\n",[[dev name] UTF8String],F->name,F->bpp,F->dc,W,H);

  const char* otype = F->dc==DC_U?"uint4":(F->dc==DC_S?"int4":"float4");
  const char* oval  = F->dc==DC_U?"uint4(1u,2u,3u,4u)":(F->dc==DC_S?"int4(1,2,3,4)":"float4(0.25,0.5,0.75,1.0)");
  NSString* vsrc=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "struct VO{float4 pos [[position]];};\n"
    "vertex VO v_main(uint vid [[vertex_id]]){ float2 p[3]={float2(-1,-3),float2(-1,1),float2(3,1)};\n"
    "  VO o; o.pos=float4(p[vid],0,1); return o; }\n";
  NSString* fsrc=[NSString stringWithFormat:
    @"#include <metal_stdlib>\nusing namespace metal;\n"
     "struct VO{float4 pos [[position]];};\n"
     "fragment %s f_main(VO in [[stage_in]]){ return %s; }\n", otype, oval];

  NSError* err=nil;
  id<MTLLibrary> vl=[dev newLibraryWithSource:vsrc options:nil error:&err];
  id<MTLLibrary> fl=[dev newLibraryWithSource:fsrc options:nil error:&err];
  if(!vl||!fl){ printf("COMPILE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
  MTLRenderPipelineDescriptor* pd=[MTLRenderPipelineDescriptor new];
  pd.vertexFunction=[vl newFunctionWithName:@"v_main"];
  pd.fragmentFunction=[fl newFunctionWithName:@"f_main"];
  pd.colorAttachments[0].pixelFormat=F->pf;
  id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
  if(!pso){ printf("RT_UNSUPPORTED fmt=%s : %s\n",F->name,[[err localizedDescription] UTF8String]); return 3; }

  NSUInteger bpr=(NSUInteger)(W*F->bpp); bpr=(bpr+255)&~255UL;
  id<MTLBuffer> rtb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
  MTLTextureDescriptor* td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:F->pf width:W height:H mipmapped:NO];
  td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead; td.storageMode=MTLStorageModeShared;
  id<MTLTexture> color=[rtb newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
  if(!color){ printf("TEX_FAIL\n"); return 1; }
  print_va("rtBuf0",[rtb gpuAddress]);

  id<MTLCommandQueue> q=[dev newCommandQueue];
  MTLRenderPassDescriptor* rp=[MTLRenderPassDescriptor new];
  rp.colorAttachments[0].texture=color;
  rp.colorAttachments[0].loadAction=MTLLoadActionClear;
  rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1);
  rp.colorAttachments[0].storeAction=MTLStoreActionStore;
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
  [enc setRenderPipelineState:pso];
  MTLViewport vp={0,0,(double)W,(double)H,0,1}; [enc setViewport:vp];
  [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
  [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
  printf("SUBMIT status=%ld err=%s\n",(long)[cb status],[cb error]?[[[cb error] localizedDescription] UTF8String]:"none");

  if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
  return 0;
}}
