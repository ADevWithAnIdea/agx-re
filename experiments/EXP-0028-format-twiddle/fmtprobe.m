// fmtprobe.m — EXP-0028 texture FORMAT-code + TYPE-code descriptor capture.
//
// Extends EXP-0015 (tvar.m). One tiny compute kernel binds a texture into the
// Metal Tier-2 argument buffer; the appended 32-byte texture descriptor is then
// captured by the read-only tools/iotrace interposer and decoded host-side. We
// only ever call t.get_width()/get_height() so the SAME kernel binds ANY pixel
// format of a given data class (float/uint/int/depth) without needing a
// format-compatible sample/read — this lets us capture byte0/byte1 for the whole
// untested-format backlog (BC/ASTC/ETC/EAC, depth/stencil, packed 10/11-bit,
// wide-gamut XR, extra 16-norm) and the untested texture TYPES
// (1DArray/CubeArray/2DMSArray/...). Unsupported formats/types are reported, not
// fatal.
//
// CLEAN-ROOM: OWN-SHADER (our MSL) + DATA-TRACE (our own process's BOs via
// iotrace) + public Metal API only. No Apple binary is disassembled. See
// ../../CLAUDE.md.
//
// Build (device): clang -fobjc-arc -framework Metal -framework Foundation -o fmtprobe fmtprobe.m
// Usage: fmtprobe --type 2d --fmt <name> [--w N --h N --d N --arraylen N --samples N --mips N --swizzle rgba] --dump

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

// data class -> MSL texture element type + kernel selection
typedef enum { CLS_F, CLS_U, CLS_S, CLS_D } Cls;   // float/normalized, uint, sint, depth
typedef struct { const char *name; MTLPixelFormat pf; Cls cls; } Fmt;

static const Fmt FMTS[] = {
  // ---- baseline (re-confirm anchors) ----
  {"rgba8unorm",       MTLPixelFormatRGBA8Unorm,          CLS_F},
  {"r32uint",          MTLPixelFormatR32Uint,             CLS_U},
  // ---- remaining 16-bit normalized ----
  {"r16snorm",         MTLPixelFormatR16Snorm,            CLS_F},
  {"rg16unorm",        MTLPixelFormatRG16Unorm,           CLS_F},
  {"rg16snorm",        MTLPixelFormatRG16Snorm,           CLS_F},
  {"rgba16snorm",      MTLPixelFormatRGBA16Snorm,         CLS_F},
  {"rg16uint",         MTLPixelFormatRG16Uint,            CLS_U},
  {"rg16sint",         MTLPixelFormatRG16Sint,            CLS_S},
  {"rgba16sint",       MTLPixelFormatRGBA16Sint,          CLS_S},
  {"r16sint",          MTLPixelFormatR16Sint,             CLS_S},
  {"rg8snorm",         MTLPixelFormatRG8Snorm,            CLS_F},
  {"rg8sint",          MTLPixelFormatRG8Sint,             CLS_S},
  {"rg32uint",         MTLPixelFormatRG32Uint,            CLS_U},
  {"rg32sint",         MTLPixelFormatRG32Sint,            CLS_S},
  {"rgba32sint",       MTLPixelFormatRGBA32Sint,          CLS_S},
  // ---- packed 10/11-bit ----
  {"rgb10a2uint",      MTLPixelFormatRGB10A2Uint,         CLS_U},
  {"bgr10a2unorm",     MTLPixelFormatBGR10A2Unorm,        CLS_F},
  // ---- wide-gamut / extended range (XR) ----
  {"bgra10_xr",        MTLPixelFormatBGRA10_XR,           CLS_F},
  {"bgra10_xr_srgb",   MTLPixelFormatBGRA10_XR_sRGB,      CLS_F},
  {"bgr10_xr",         MTLPixelFormatBGR10_XR,            CLS_F},
  {"bgr10_xr_srgb",    MTLPixelFormatBGR10_XR_sRGB,       CLS_F},
  // ---- depth / stencil ----
  {"depth16unorm",     MTLPixelFormatDepth16Unorm,        CLS_D},
  {"depth32float",     MTLPixelFormatDepth32Float,        CLS_D},
  {"stencil8",         MTLPixelFormatStencil8,            CLS_U},
  {"depth32float_stencil8", MTLPixelFormatDepth32Float_Stencil8, CLS_D},
  {"depth24unorm_stencil8", MTLPixelFormatDepth24Unorm_Stencil8, CLS_D},
  {"x32_stencil8",     MTLPixelFormatX32_Stencil8,        CLS_U},
  {"x24_stencil8",     MTLPixelFormatX24_Stencil8,        CLS_U},
  // ---- BC (S3TC/RGTC/BPTC) ----
  {"bc1_rgba",         MTLPixelFormatBC1_RGBA,            CLS_F},
  {"bc1_rgba_srgb",    MTLPixelFormatBC1_RGBA_sRGB,       CLS_F},
  {"bc2_rgba",         MTLPixelFormatBC2_RGBA,            CLS_F},
  {"bc3_rgba",         MTLPixelFormatBC3_RGBA,            CLS_F},
  {"bc4_runorm",       MTLPixelFormatBC4_RUnorm,          CLS_F},
  {"bc4_rsnorm",       MTLPixelFormatBC4_RSnorm,          CLS_F},
  {"bc5_rgunorm",      MTLPixelFormatBC5_RGUnorm,         CLS_F},
  {"bc5_rgsnorm",      MTLPixelFormatBC5_RGSnorm,         CLS_F},
  {"bc6h_rgbfloat",    MTLPixelFormatBC6H_RGBFloat,       CLS_F},
  {"bc6h_rgbufloat",   MTLPixelFormatBC6H_RGBUfloat,      CLS_F},
  {"bc7_rgba",         MTLPixelFormatBC7_RGBAUnorm,       CLS_F},
  {"bc7_rgba_srgb",    MTLPixelFormatBC7_RGBAUnorm_sRGB,  CLS_F},
  // ---- ETC2 / EAC ----
  {"etc2_rgb8",        MTLPixelFormatETC2_RGB8,           CLS_F},
  {"etc2_rgb8_srgb",   MTLPixelFormatETC2_RGB8_sRGB,      CLS_F},
  {"etc2_rgb8a1",      MTLPixelFormatETC2_RGB8A1,         CLS_F},
  {"eac_rgba8",        MTLPixelFormatEAC_RGBA8,           CLS_F},
  {"eac_r11unorm",     MTLPixelFormatEAC_R11Unorm,        CLS_F},
  {"eac_r11snorm",     MTLPixelFormatEAC_R11Snorm,        CLS_F},
  {"eac_rg11unorm",    MTLPixelFormatEAC_RG11Unorm,       CLS_F},
  {"eac_rg11snorm",    MTLPixelFormatEAC_RG11Snorm,       CLS_F},
  // ---- ASTC LDR (block-size sweep) ----
  {"astc_4x4_ldr",     MTLPixelFormatASTC_4x4_LDR,        CLS_F},
  {"astc_5x5_ldr",     MTLPixelFormatASTC_5x5_LDR,        CLS_F},
  {"astc_6x6_ldr",     MTLPixelFormatASTC_6x6_LDR,        CLS_F},
  {"astc_8x8_ldr",     MTLPixelFormatASTC_8x8_LDR,        CLS_F},
  {"astc_10x10_ldr",   MTLPixelFormatASTC_10x10_LDR,      CLS_F},
  {"astc_12x12_ldr",   MTLPixelFormatASTC_12x12_LDR,      CLS_F},
  {"astc_4x4_srgb",    MTLPixelFormatASTC_4x4_sRGB,       CLS_F},
  {"astc_8x8_srgb",    MTLPixelFormatASTC_8x8_sRGB,       CLS_F},
  // ---- ASTC HDR ----
  {"astc_4x4_hdr",     MTLPixelFormatASTC_4x4_HDR,        CLS_F},
  {"astc_6x6_hdr",     MTLPixelFormatASTC_6x6_HDR,        CLS_F},
  {"astc_8x8_hdr",     MTLPixelFormatASTC_8x8_HDR,        CLS_F},
  // ---- PVRTC (legacy Apple) ----
  {"pvrtc_rgba_4bpp",  MTLPixelFormatPVRTC_RGBA_4BPP,     CLS_F},
  {"pvrtc_rgb_4bpp",   MTLPixelFormatPVRTC_RGB_4BPP,      CLS_F},
};
static const int NFMT = sizeof(FMTS)/sizeof(FMTS[0]);
static const Fmt *findFmt(const char *n){ for(int i=0;i<NFMT;i++) if(!strcmp(FMTS[i].name,n)) return &FMTS[i]; return NULL; }

static MTLTextureSwizzle pSw(char c){
  switch(c){ case '0':return MTLTextureSwizzleZero; case '1':return MTLTextureSwizzleOne;
    case 'r':case 'R':return MTLTextureSwizzleRed; case 'g':case 'G':return MTLTextureSwizzleGreen;
    case 'b':case 'B':return MTLTextureSwizzleBlue; case 'a':case 'A':return MTLTextureSwizzleAlpha; }
  return MTLTextureSwizzleRed;
}

// MSL texture-type string for a given --type and data class.
static const char *mslTexType(const char*type, Cls cls){
  const char *e = cls==CLS_U ? "uint" : (cls==CLS_S ? "int" : "float");
  static char buf[64];
  if(cls==CLS_D){
    if(!strcmp(type,"cube"))      { snprintf(buf,sizeof buf,"depthcube<float>"); return buf; }
    if(!strcmp(type,"cubearray")) { snprintf(buf,sizeof buf,"depthcube_array<float>"); return buf; }
    if(!strcmp(type,"2darray"))   { snprintf(buf,sizeof buf,"depth2d_array<float>"); return buf; }
    if(!strcmp(type,"2dms"))      { snprintf(buf,sizeof buf,"depth2d_ms<float>"); return buf; }
    snprintf(buf,sizeof buf,"depth2d<float>"); return buf;
  }
  const char *tt;
  if(!strcmp(type,"1d")) tt="texture1d";
  else if(!strcmp(type,"1darray")) tt="texture1d_array";
  else if(!strcmp(type,"3d")) tt="texture3d";
  else if(!strcmp(type,"cube")) tt="texturecube";
  else if(!strcmp(type,"cubearray")) tt="texturecube_array";
  else if(!strcmp(type,"2darray")) tt="texture2d_array";
  else if(!strcmp(type,"2dms")) tt="texture2d_ms";
  else if(!strcmp(type,"2dmsarray")) tt="texture2d_ms_array";
  else tt="texture2d";
  snprintf(buf,sizeof buf,"%s<%s>", tt, e);
  return buf;
}

int main(int argc, char**argv){
 @autoreleasepool{
  const char *type="2d", *fmtname="rgba8unorm", *swizzle=NULL;
  long W=32,H=32,D=1,mips=1,arraylen=1,samples=1; int doDump=0;
  for(int i=1;i<argc;i++){ const char*a=argv[i];
    #define ARG(f) (!strcmp(a,f)&&i+1<argc)
    if(ARG("--type")) type=argv[++i];
    else if(ARG("--fmt")) fmtname=argv[++i];
    else if(ARG("--w")) W=strtol(argv[++i],0,0);
    else if(ARG("--h")) H=strtol(argv[++i],0,0);
    else if(ARG("--d")) D=strtol(argv[++i],0,0);
    else if(ARG("--mips")) mips=strtol(argv[++i],0,0);
    else if(ARG("--arraylen")) arraylen=strtol(argv[++i],0,0);
    else if(ARG("--samples")) samples=strtol(argv[++i],0,0);
    else if(ARG("--swizzle")) swizzle=argv[++i];
    else if(!strcmp(a,"--dump")) doDump=1;
    #undef ARG
  }
  const Fmt *F=findFmt(fmtname);
  if(!F){ printf("UNKNOWN_FMT %s\n",fmtname); return 2; }

  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\n",[[dev name] UTF8String]);
  printf("CONFIG type=%s fmt=%s W=%ld H=%ld D=%ld arraylen=%ld samples=%ld mips=%ld\n",
    type,F->name,W,H,D,arraylen,samples,mips);

  MTLTextureDescriptor *td=[MTLTextureDescriptor new];
  td.pixelFormat=F->pf; td.width=W; td.height=H; td.depth=D;
  td.mipmapLevelCount=mips; td.arrayLength=arraylen; td.sampleCount=samples;
  td.storageMode=MTLStorageModeShared;
  td.usage=MTLTextureUsageShaderRead;
  if(!strcmp(type,"1d")) td.textureType=MTLTextureType1D;
  else if(!strcmp(type,"1darray")) td.textureType=MTLTextureType1DArray;
  else if(!strcmp(type,"3d")) td.textureType=MTLTextureType3D;
  else if(!strcmp(type,"cube")) td.textureType=MTLTextureTypeCube;
  else if(!strcmp(type,"cubearray")) td.textureType=MTLTextureTypeCubeArray;
  else if(!strcmp(type,"2darray")) td.textureType=MTLTextureType2DArray;
  else if(!strcmp(type,"2dms")){ td.textureType=MTLTextureType2DMultisample; td.usage=MTLTextureUsageRenderTarget; }
  else if(!strcmp(type,"2dmsarray")){ td.textureType=MTLTextureType2DMultisampleArray; td.usage=MTLTextureUsageRenderTarget; }
  else td.textureType=MTLTextureType2D;
  // depth/stencil + MSAA generally require Private storage; keep only descriptor.
  if(F->cls==CLS_D || samples>1){ td.storageMode=MTLStorageModePrivate;
      td.usage |= MTLTextureUsageRenderTarget; }
  if(swizzle && strlen(swizzle)>=4)
    td.swizzle=MTLTextureSwizzleChannelsMake(pSw(swizzle[0]),pSw(swizzle[1]),pSw(swizzle[2]),pSw(swizzle[3]));

  id<MTLTexture> tex=nil;
  @try { tex=[dev newTextureWithDescriptor:td]; }
  @catch(NSException*e){ printf("UNSUPPORTED_EXC fmt=%s type=%s reason=%s\n",F->name,type,[[e reason] UTF8String]); return 0; }
  if(!tex){ printf("UNSUPPORTED_CREATE fmt=%s type=%s\n",F->name,type); return 0; }
  printf("TEX ok fmt=%s type=%s\n",F->name,type);

  // tiny bind kernel: just read width/height so ANY format of this class binds.
  const char *tt = mslTexType(type,F->cls);
  NSString *src=[NSString stringWithFormat:
     @"#include <metal_stdlib>\nusing namespace metal;\n"
      "kernel void k(%s t [[texture(0)]], device uint* o [[buffer(0)]],\n"
      "  uint i [[thread_position_in_grid]]) { o[i]=t.get_width(); }\n", tt];
  NSError *err=nil;
  id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
  if(!lib){ printf("COMPILE_FAIL %s :: %s\n",tt,[[err localizedDescription] UTF8String]); return 0; }
  id<MTLFunction> fn=[lib newFunctionWithName:@"k"];
  id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:fn error:&err];
  if(!pso){ printf("PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 0; }

  id<MTLBuffer> obuf=[dev newBufferWithLength:64*4 options:MTLResourceStorageModeShared];
  print_va("obuf",[obuf gpuAddress]);

  id<MTLCommandQueue> q=[dev newCommandQueue];
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
  [enc setComputePipelineState:pso];
  @try { [enc setTexture:tex atIndex:0]; }
  @catch(NSException*e){ printf("BIND_EXC %s\n",[[e reason] UTF8String]); }
  [enc setBuffer:obuf offset:0 atIndex:0];
  [enc dispatchThreads:MTLSizeMake(64,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
  [enc endEncoding];
  [cb commit]; [cb waitUntilCompleted];
  printf("SUBMIT done status=%ld\n",(long)[cb status]);
  if([cb status]!=MTLCommandBufferStatusCompleted && [cb error])
    printf("CB_ERROR %s\n",[[[cb error] localizedDescription] UTF8String]);

  if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
  return 0;
 }
}
