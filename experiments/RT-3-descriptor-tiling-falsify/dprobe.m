// dprobe.m — RT-3 descriptor falsification probe (extended format table).
//
// RED-TEAM re-verification of docs/descriptors. Binds ONE sampled texture into the
// Metal Tier-2 auto argument buffer with a chosen format / dims / swizzle / sRGB /
// mip count / sample count, dispatches a tiny read kernel, and SIGUSR1-dumps every
// registered BO under the read-only tools/iotrace interposer. Host-side dcheck.py
// then INDEPENDENTLY re-derives each descriptor field (it does NOT trust the doc's
// claimed bit positions).
//
// The point of this probe vs EXP-0015's tvar.m: a much larger, obscure-format table
// (16-bit snorm/sint, packed uint, XR, 64/128-bit int, ETC/EAC/ASTC/BC, depth/stencil)
// to falsify the byte0/byte1 numtype<<5|sizeclass rule on formats the originals skipped,
// and NPOT / max dims to falsify the width-1/height-1 packing.
//
// CLEAN-ROOM: OWN-SHADER + public Metal API + HW-PROBE. Our MSL, our resources.
// Nothing disassembles any Apple binary. See ../../CLAUDE.md.
//
// Build (device): clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o dprobe dprobe.m
// Usage: dprobe --fmt NAME [--type 2d|3d|cube|2darray|2dms] [--w W --h H --d D]
//               [--mips N] [--arraylen N] [--samples N] [--swizzle RGBA] [--srgb] --dump

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void print_va(const char *l,uint64_t va){ printf("VA %-10s = 0x%016llx\n",l,(unsigned long long)va); }

typedef enum { CF, CU, CS } Cls;  // float-ish, uint, sint (drives sampler comp type)
typedef struct { const char*name; MTLPixelFormat pf; Cls cls; int block; } Fmt;

// Extended, obscure-leaning table. `block`=1 marks block-compressed (needs multiple-of-block dims).
static const Fmt FMTS[] = {
  // 16-bit snorm/unorm/sint variants (format-table.md §8 flags these UNTESTED)
  {"r16snorm",    MTLPixelFormatR16Snorm,     CF,0},
  {"rg16unorm",   MTLPixelFormatRG16Unorm,    CF,0},
  {"rg16snorm",   MTLPixelFormatRG16Snorm,    CF,0},
  {"rgba16snorm", MTLPixelFormatRGBA16Snorm,  CF,0},
  {"r16sint",     MTLPixelFormatR16Sint,      CS,0},
  {"rg16sint",    MTLPixelFormatRG16Sint,     CS,0},
  {"rg16uint",    MTLPixelFormatRG16Uint,     CU,0},
  {"rgba16sint",  MTLPixelFormatRGBA16Sint,   CS,0},
  // 8-bit less-common
  {"rg8snorm",    MTLPixelFormatRG8Snorm,     CF,0},
  {"rg8sint",     MTLPixelFormatRG8Sint,      CS,0},
  {"r8unorm_srgb",MTLPixelFormatR8Unorm_sRGB, CF,0},
  {"rgba8sint",   MTLPixelFormatRGBA8Sint,    CS,0},
  // packed with non-unorm numtype
  {"rgb10a2uint", MTLPixelFormatRGB10A2Uint,  CU,0},
  {"bgr10_xr",    MTLPixelFormatBGR10_XR,     CF,0},
  {"bgra10_xr",   MTLPixelFormatBGRA10_XR,    CF,0},
  {"bgr10_xr_srgb",MTLPixelFormatBGR10_XR_sRGB,CF,0},
  // 64/128-bit integer
  {"rg32uint",    MTLPixelFormatRG32Uint,     CU,0},
  {"rg32sint",    MTLPixelFormatRG32Sint,     CS,0},
  {"rgba32sint",  MTLPixelFormatRGBA32Sint,   CS,0},
  // depth/stencil
  {"depth16unorm",MTLPixelFormatDepth16Unorm, CF,0},
  {"stencil8",    MTLPixelFormatStencil8,     CU,0},
  {"depth32float_stencil8", MTLPixelFormatDepth32Float_Stencil8, CF,0},
  // block compressed (need >=block dims)
  {"bc1_rgba",    MTLPixelFormatBC1_RGBA,     CF,1},
  {"bc3_rgba",    MTLPixelFormatBC3_RGBA,     CF,1},
  {"bc4_runorm",  MTLPixelFormatBC4_RUnorm,   CF,1},
  {"bc4_rsnorm",  MTLPixelFormatBC4_RSnorm,   CF,1},
  {"bc5_rgunorm", MTLPixelFormatBC5_RGUnorm,  CF,1},
  {"bc6h_float",  MTLPixelFormatBC6H_RGBFloat,CF,1},
  {"bc7_rgba",    MTLPixelFormatBC7_RGBAUnorm,CF,1},
  {"bc7_srgb",    MTLPixelFormatBC7_RGBAUnorm_sRGB,CF,1},
  {"astc_5x5",    MTLPixelFormatASTC_5x5_LDR, CF,1},
  {"astc_6x6",    MTLPixelFormatASTC_6x6_LDR, CF,1},
  {"astc_10x10",  MTLPixelFormatASTC_10x10_LDR,CF,1},
  {"astc_8x8_hdr",MTLPixelFormatASTC_8x8_HDR, CF,1},
  {"astc_6x6_srgb",MTLPixelFormatASTC_6x6_sRGB,CF,1},
  {"eac_r11unorm",MTLPixelFormatEAC_R11Unorm, CF,1},
  {"eac_r11snorm",MTLPixelFormatEAC_R11Snorm, CF,1},
  {"eac_rg11unorm",MTLPixelFormatEAC_RG11Unorm,CF,1},
  {"etc2_rgb8",   MTLPixelFormatETC2_RGB8,    CF,1},
  {"etc2_rgb8a1", MTLPixelFormatETC2_RGB8A1,  CF,1},
  // control / sanity + sRGB & swizzle cross-check pairs
  {"rgba8unorm",  MTLPixelFormatRGBA8Unorm,   CF,0},
  {"rgba8unorm_srgb", MTLPixelFormatRGBA8Unorm_sRGB, CF,0},
  {"bgra8unorm",  MTLPixelFormatBGRA8Unorm,   CF,0},
  {"bgra8unorm_srgb", MTLPixelFormatBGRA8Unorm_sRGB, CF,0},
  {"r8unorm",     MTLPixelFormatR8Unorm,      CF,0},
  {"r32uint",     MTLPixelFormatR32Uint,      CU,0},
};
static const int NFMT=sizeof(FMTS)/sizeof(FMTS[0]);
static const Fmt* findFmt(const char*n){ for(int i=0;i<NFMT;i++) if(!strcmp(FMTS[i].name,n)) return &FMTS[i]; return NULL; }

static MTLTextureSwizzle pSw(char c){
  switch(c){ case '0':return MTLTextureSwizzleZero; case '1':return MTLTextureSwizzleOne;
    case 'r':case 'R':return MTLTextureSwizzleRed; case 'g':case 'G':return MTLTextureSwizzleGreen;
    case 'b':case 'B':return MTLTextureSwizzleBlue; case 'a':case 'A':return MTLTextureSwizzleAlpha; }
  return MTLTextureSwizzleRed;
}

int main(int argc,char**argv){ @autoreleasepool{
  const char*fmtname="rgba8unorm",*type="2d",*swizzle=NULL;
  long W=64,H=64,D=1,mips=1,arraylen=1,samples=1; int srgb=0,doDump=0; long texoff=-1;
  for(int i=1;i<argc;i++){ const char*a=argv[i];
    #define ARG(f) (!strcmp(a,f)&&i+1<argc)
    if(ARG("--fmt")) fmtname=argv[++i];
    else if(ARG("--type")) type=argv[++i];
    else if(ARG("--w")) W=strtol(argv[++i],0,0);
    else if(ARG("--h")) H=strtol(argv[++i],0,0);
    else if(ARG("--d")) D=strtol(argv[++i],0,0);
    else if(ARG("--mips")) mips=strtol(argv[++i],0,0);
    else if(ARG("--arraylen")) arraylen=strtol(argv[++i],0,0);
    else if(ARG("--samples")) samples=strtol(argv[++i],0,0);
    else if(ARG("--swizzle")) swizzle=argv[++i];
    else if(ARG("--texoff")) texoff=strtol(argv[++i],0,0);
    else if(!strcmp(a,"--srgb")) srgb=1;
    else if(!strcmp(a,"--dump")) doDump=1;
    #undef ARG
  }
  const Fmt*F=findFmt(fmtname);
  if(!F){ printf("UNKNOWN_FMT %s\n",fmtname); return 2; }

  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\n",[[dev name] UTF8String]);
  printf("CONFIG fmt=%s type=%s W=%ld H=%ld D=%ld mips=%ld arraylen=%ld samples=%ld swizzle=%s srgb=%d texoff=%ld\n",
    F->name,type,W,H,D,mips,arraylen,samples,swizzle?swizzle:"-",srgb,texoff);

  MTLTextureDescriptor*td=[MTLTextureDescriptor new];
  td.pixelFormat=F->pf; td.width=W; td.height=H; td.depth=D;
  td.mipmapLevelCount=mips; td.arrayLength=arraylen; td.sampleCount=samples;
  td.usage=MTLTextureUsageShaderRead; td.storageMode=MTLStorageModeShared;
  if(!strcmp(type,"3d")) td.textureType=MTLTextureType3D;
  else if(!strcmp(type,"cube")) td.textureType=MTLTextureTypeCube;
  else if(!strcmp(type,"cubearray")) td.textureType=MTLTextureTypeCubeArray;
  else if(!strcmp(type,"2darray")) td.textureType=MTLTextureType2DArray;
  else if(!strcmp(type,"2dms")){ td.textureType=MTLTextureType2DMultisample; td.usage=MTLTextureUsageShaderRead|MTLTextureUsageRenderTarget; }
  else if(!strcmp(type,"1d")) td.textureType=MTLTextureType1D;
  else td.textureType=MTLTextureType2D;
  if(swizzle&&strlen(swizzle)>=4)
    td.swizzle=MTLTextureSwizzleChannelsMake(pSw(swizzle[0]),pSw(swizzle[1]),pSw(swizzle[2]),pSw(swizzle[3]));

  id<MTLTexture> tex=nil; id<MTLBuffer> texbuf=nil;
  if(texoff>=0){
    NSUInteger align=[dev minimumLinearTextureAlignmentForPixelFormat:F->pf];
    NSUInteger bpr=W*16; if(align) bpr=((bpr+align-1)/align)*align;
    NSUInteger total=texoff+bpr*H+0x4000;
    texbuf=[dev newBufferWithLength:total options:MTLResourceStorageModeShared];
    memset([texbuf contents],0x80,total);
    print_va("texbuf",[texbuf gpuAddress]);
    printf("TEXBUF base+off = 0x%llx (off=0x%lx bpr=0x%lx)\n",
      (unsigned long long)([texbuf gpuAddress]+texoff),(unsigned long)texoff,(unsigned long)bpr);
    tex=[texbuf newTextureWithDescriptor:td offset:texoff bytesPerRow:bpr];
  } else {
    tex=[dev newTextureWithDescriptor:td];
  }
  if(!tex){ printf("TEX_FAIL fmt=%s type=%s\n",F->name,type); return 1; }
  printf("TEX ok gpuResourceID=0x%llx\n",(unsigned long long)tex.gpuResourceID._impl);

  // Bind sampled texture + sampler + output buffer -> arg buffer.
  const char*comp = F->cls==CU?"uint":(F->cls==CS?"int":"float");
  const char*tt="texture2d", *coord="float2(0.5f)", *args="sampler s [[sampler(0)]], ";
  const char*call="t.sample(s,%COORD%)";
  // texture-type-specific read/sample
  NSString*sampleExpr;
  if(!strcmp(type,"3d")){ tt="texture3d"; sampleExpr=@"t.sample(s,float3(0.5f))"; }
  else if(!strcmp(type,"cube")){ tt="texturecube"; sampleExpr=@"t.sample(s,float3(0.5f,0.5f,0.5f))"; }
  else if(!strcmp(type,"2darray")){ tt="texture2d_array"; sampleExpr=@"t.sample(s,float2(0.5f),0)"; }
  else if(!strcmp(type,"2dms")){ tt="texture2d_ms"; sampleExpr=@"t.read(uint2(0,0),0)"; args=""; }
  else if(!strcmp(type,"1d")){ tt="texture1d"; sampleExpr=@"t.sample(s,0.5f)"; }
  else { sampleExpr=@"t.sample(s,float2(0.5f))"; }
  (void)coord;(void)call;
  NSString*src=[NSString stringWithFormat:
    @"#include <metal_stdlib>\nusing namespace metal;\n"
     "kernel void k(%s<%s> t [[texture(0)]], %sdevice float* o [[buffer(0)]],\n"
     "  uint i [[thread_position_in_grid]]) { o[i]=float((%@).x); }\n",
     tt,comp,args,sampleExpr];
  NSError*err=nil;
  id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
  if(!lib){ printf("COMPILE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
  id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"k"] error:&err];
  if(!pso){ printf("PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }

  id<MTLSamplerState> smp=nil;
  if(strcmp(type,"2dms")){
    MTLSamplerDescriptor*sd=[MTLSamplerDescriptor new];
    sd.minFilter=MTLSamplerMinMagFilterNearest; sd.magFilter=MTLSamplerMinMagFilterNearest;
    smp=[dev newSamplerStateWithDescriptor:sd];
  }
  id<MTLBuffer> obuf=[dev newBufferWithLength:64*4 options:MTLResourceStorageModeShared];
  print_va("obuf",obuf.gpuAddress);

  id<MTLCommandQueue> q=[dev newCommandQueue];
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
  [enc setComputePipelineState:pso];
  [enc setTexture:tex atIndex:0];
  if(smp)[enc setSamplerState:smp atIndex:0];
  [enc setBuffer:obuf offset:0 atIndex:0];
  [enc dispatchThreads:MTLSizeMake(16,1,1) threadsPerThreadgroup:MTLSizeMake(16,1,1)];
  [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
  printf("SUBMIT status=%ld\n",(long)[cb status]);
  if([cb status]!=MTLCommandBufferStatusCompleted && [cb error])
    printf("CB_ERROR %s\n",[[[cb error] localizedDescription] UTF8String]);
  (void)srgb;
  if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
  return 0;
}}
