// tvar.m — parametric OWN compute program for texture/sampler/buffer DESCRIPTOR RE.
//
// Part of EXP-0015 (Phase 3, resource descriptors). Sibling of EXP-0011's cvar.m and
// EXP-0014's dvar.m. One small compute kernel that binds a texture + sampler + buffer
// into the Metal-generated (Tier-2) argument buffer, where every texture-descriptor and
// sampler-descriptor parameter is a CLI flag. Change exactly ONE Metal descriptor
// parameter, re-capture the registered GPU buffer objects under the iotrace interposer,
// and byte-diff the appended descriptor blocks to localise each field.
//
// CLEAN-ROOM: OWN-SHADER + public Metal API only. Every kernel here is our own MSL,
// compiled at runtime; textures/samplers are built from public MTL*Descriptor APIs. We
// print the GPU virtual addresses of our own resources so the captured descriptor bytes
// can be correlated. Nothing disassembles any Apple binary. See ../../CLAUDE.md.
//
// Build (device): clang -fobjc-arc -framework Metal -framework Foundation -o tvar tvar.m
//
// The argument buffer (BO gpu_va 0x100000e0000) holds, in binding order at +0x14a0:
//   [[texture(0)]] -> 8-byte pointer to a texture descriptor appended in the same BO
//   [[sampler(0)]] -> 8-byte pointer to a sampler descriptor appended in the same BO
//   [[buffer(0)]]  -> inline 8-byte GPU VA
// (EXP-0011). This harness prints those pointers via a probe kernel is not possible, so
// the companion descx.py follows the +0x14a0 / +0x14a8 pointers to extract the blocks.

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void print_va(const char *label, uint64_t va) {
    unsigned char b[8];
    for (int i = 0; i < 8; i++) b[i] = (va >> (8 * i)) & 0xff;
    printf("VA %-12s = 0x%016llx  le=", label, (unsigned long long)va);
    for (int i = 0; i < 8; i++) printf("%02x", b[i]);
    printf("\n");
}

// ---- pixel-format table ---------------------------------------------------
typedef enum { CLS_F, CLS_U, CLS_S } Cls;   // float/normalized, uint, sint
typedef struct { const char *name; MTLPixelFormat pf; Cls cls; } Fmt;

static const Fmt FMTS[] = {
  {"r8unorm",         MTLPixelFormatR8Unorm,          CLS_F},
  {"r8snorm",         MTLPixelFormatR8Snorm,          CLS_F},
  {"a8unorm",         MTLPixelFormatA8Unorm,          CLS_F},
  {"rg8unorm",        MTLPixelFormatRG8Unorm,         CLS_F},
  {"rgba8unorm",      MTLPixelFormatRGBA8Unorm,       CLS_F},
  {"rgba8snorm",      MTLPixelFormatRGBA8Snorm,       CLS_F},
  {"bgra8unorm",      MTLPixelFormatBGRA8Unorm,       CLS_F},
  {"rgba8unorm_srgb", MTLPixelFormatRGBA8Unorm_sRGB,  CLS_F},
  {"bgra8unorm_srgb", MTLPixelFormatBGRA8Unorm_sRGB,  CLS_F},
  {"r16unorm",        MTLPixelFormatR16Unorm,         CLS_F},
  {"rgba16unorm",     MTLPixelFormatRGBA16Unorm,      CLS_F},
  {"r16float",        MTLPixelFormatR16Float,         CLS_F},
  {"rg16float",       MTLPixelFormatRG16Float,        CLS_F},
  {"rgba16float",     MTLPixelFormatRGBA16Float,      CLS_F},
  {"r32float",        MTLPixelFormatR32Float,         CLS_F},
  {"rg32float",       MTLPixelFormatRG32Float,        CLS_F},
  {"rgba32float",     MTLPixelFormatRGBA32Float,      CLS_F},
  {"rgb10a2unorm",    MTLPixelFormatRGB10A2Unorm,     CLS_F},
  {"bgr10a2unorm",    MTLPixelFormatBGR10A2Unorm,     CLS_F},
  {"rg11b10float",    MTLPixelFormatRG11B10Float,     CLS_F},
  {"rgb9e5float",     MTLPixelFormatRGB9E5Float,      CLS_F},
  {"r8uint",          MTLPixelFormatR8Uint,           CLS_U},
  {"rg8uint",         MTLPixelFormatRG8Uint,          CLS_U},
  {"rgba8uint",       MTLPixelFormatRGBA8Uint,        CLS_U},
  {"r16uint",         MTLPixelFormatR16Uint,          CLS_U},
  {"rgba16uint",      MTLPixelFormatRGBA16Uint,       CLS_U},
  {"r32uint",         MTLPixelFormatR32Uint,          CLS_U},
  {"rgba32uint",      MTLPixelFormatRGBA32Uint,       CLS_U},
  {"r8sint",          MTLPixelFormatR8Sint,           CLS_S},
  {"rgba8sint",       MTLPixelFormatRGBA8Sint,        CLS_S},
  {"r32sint",         MTLPixelFormatR32Sint,          CLS_S},
  {"depth32float",    MTLPixelFormatDepth32Float,     CLS_F},
  {"depth16unorm",    MTLPixelFormatDepth16Unorm,     CLS_F},
};
static const int NFMT = sizeof(FMTS)/sizeof(FMTS[0]);

static const Fmt *findFmt(const char *n){
  for(int i=0;i<NFMT;i++) if(!strcmp(FMTS[i].name,n)) return &FMTS[i];
  return NULL;
}

// ---- enum string parsers --------------------------------------------------
static MTLSamplerMinMagFilter pFilter(const char*s){
  if(!strcmp(s,"linear")) return MTLSamplerMinMagFilterLinear;
  return MTLSamplerMinMagFilterNearest;
}
static MTLSamplerMipFilter pMip(const char*s){
  if(!strcmp(s,"nearest")) return MTLSamplerMipFilterNearest;
  if(!strcmp(s,"linear"))  return MTLSamplerMipFilterLinear;
  return MTLSamplerMipFilterNotMipmapped;
}
static MTLSamplerAddressMode pAddr(const char*s){
  if(!strcmp(s,"repeat"))     return MTLSamplerAddressModeRepeat;
  if(!strcmp(s,"mirror"))     return MTLSamplerAddressModeMirrorRepeat;
  if(!strcmp(s,"clampzero"))  return MTLSamplerAddressModeClampToZero;
  if(!strcmp(s,"border"))     return MTLSamplerAddressModeClampToBorderColor;
  if(!strcmp(s,"mirroredge")) return MTLSamplerAddressModeMirrorClampToEdge;
  return MTLSamplerAddressModeClampToEdge;
}
static MTLCompareFunction pCmp(const char*s){
  if(!strcmp(s,"less"))     return MTLCompareFunctionLess;
  if(!strcmp(s,"lequal"))   return MTLCompareFunctionLessEqual;
  if(!strcmp(s,"greater"))  return MTLCompareFunctionGreater;
  if(!strcmp(s,"gequal"))   return MTLCompareFunctionGreaterEqual;
  if(!strcmp(s,"equal"))    return MTLCompareFunctionEqual;
  if(!strcmp(s,"nequal"))   return MTLCompareFunctionNotEqual;
  if(!strcmp(s,"always"))   return MTLCompareFunctionAlways;
  return MTLCompareFunctionNever;
}
static MTLSamplerBorderColor pBorder(const char*s){
  if(!strcmp(s,"oblack")) return MTLSamplerBorderColorOpaqueBlack;
  if(!strcmp(s,"owhite")) return MTLSamplerBorderColorOpaqueWhite;
  return MTLSamplerBorderColorTransparentBlack;
}
static MTLTextureSwizzle pSw(char c){
  switch(c){
    case '0': return MTLTextureSwizzleZero;
    case '1': return MTLTextureSwizzleOne;
    case 'r': case 'R': return MTLTextureSwizzleRed;
    case 'g': case 'G': return MTLTextureSwizzleGreen;
    case 'b': case 'B': return MTLTextureSwizzleBlue;
    case 'a': case 'A': return MTLTextureSwizzleAlpha;
  }
  return MTLTextureSwizzleRed;
}

// ---- MSL kernel generator (matches texture type + data class) -------------
static NSString *genKernel(const char *type, Cls cls, int cmp){
  const char *comp = cls==CLS_U ? "uint" : (cls==CLS_S ? "int" : "float");
  if(cmp){ // depth compare sampler path
    return @"#include <metal_stdlib>\nusing namespace metal;\n"
            "kernel void k(depth2d<float> t [[texture(0)]], sampler s [[sampler(0)]],\n"
            "  device float* o [[buffer(0)]], uint i [[thread_position_in_grid]]) {\n"
            "  o[i]=t.sample_compare(s, float2(0.5f,0.5f), 0.5f); }\n";
  }
  const char *tt, *sample;
  if(!strcmp(type,"1d")){ tt="texture1d"; sample="t.sample(s, 0.5f)"; }
  else if(!strcmp(type,"3d")){ tt="texture3d"; sample="t.sample(s, float3(0.5f))"; }
  else if(!strcmp(type,"cube")){ tt="texturecube"; sample="t.sample(s, float3(0.5f,0.5f,0.5f))"; }
  else if(!strcmp(type,"2darray")){ tt="texture2d_array"; sample="t.sample(s, float2(0.5f), 0)"; }
  else if(!strcmp(type,"2dms")){ tt="texture2d_ms"; sample=NULL; } // MS: read, no sampler
  else { tt="texture2d"; sample="t.sample(s, float2(0.5f))"; }

  if(sample==NULL){ // multisample: read(), no sampler param (keeps arg layout minimal)
    return [NSString stringWithFormat:
      @"#include <metal_stdlib>\nusing namespace metal;\n"
       "kernel void k(%s<%s> t [[texture(0)]], device float* o [[buffer(0)]],\n"
       "  uint i [[thread_position_in_grid]]) { o[i]=float(t.read(uint2(0,0),0).x); }\n",
       tt, comp];
  }
  return [NSString stringWithFormat:
    @"#include <metal_stdlib>\nusing namespace metal;\n"
     "kernel void k(%s<%s> t [[texture(0)]], sampler s [[sampler(0)]],\n"
     "  device float* o [[buffer(0)]], uint i [[thread_position_in_grid]]) {\n"
     "  o[i]=float(%s.x); }\n", tt, comp, sample];
}

int main(int argc, char **argv){
  @autoreleasepool {
    // texture params
    const char *type="2d", *fmtname="rgba8unorm", *swizzle=NULL;
    long W=4,H=4,D=1,mips=1,arraylen=1,samples=1;
    long texoff=-1; // >=0 => buffer-backed texture at this byte offset (VA probe)
    // sampler params
    const char *minf="nearest",*magf="nearest",*mipf="none";
    const char *saddr="edge",*taddr="edge",*raddr="edge";
    const char *cmpf="never",*border="tblack";
    long aniso=1; double lodmin=0.0, lodmax=-1.0 /* FLT_MAX default */; int normcoord=1;
    int cmp=0; int doDump=0;

    for(int i=1;i<argc;i++){
      const char*a=argv[i];
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
      else if(ARG("--texoff")) texoff=strtol(argv[++i],0,0);
      else if(ARG("--minf")) minf=argv[++i];
      else if(ARG("--magf")) magf=argv[++i];
      else if(ARG("--mipf")) mipf=argv[++i];
      else if(ARG("--saddr")) saddr=argv[++i];
      else if(ARG("--taddr")) taddr=argv[++i];
      else if(ARG("--raddr")) raddr=argv[++i];
      else if(ARG("--cmpf")) cmpf=argv[++i];
      else if(ARG("--border")) border=argv[++i];
      else if(ARG("--aniso")) aniso=strtol(argv[++i],0,0);
      else if(ARG("--lodmin")) lodmin=strtod(argv[++i],0);
      else if(ARG("--lodmax")) lodmax=strtod(argv[++i],0);
      else if(!strcmp(a,"--unorm")) normcoord=0;
      else if(!strcmp(a,"--cmp")) cmp=1;
      else if(!strcmp(a,"--dump")) doDump=1;
      #undef ARG
    }

    const Fmt *F = cmp ? findFmt("depth32float") : findFmt(fmtname);
    if(!F){ printf("UNKNOWN_FMT %s\n",fmtname); return 2; }

    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    printf("DEVICE %s\n",[[dev name] UTF8String]);
    printf("CONFIG type=%s fmt=%s W=%ld H=%ld D=%ld mips=%ld arraylen=%ld samples=%ld texoff=%ld cmp=%d\n",
      type,F->name,W,H,D,mips,arraylen,samples,texoff,cmp);
    printf("SMPCFG minf=%s magf=%s mipf=%s saddr=%s taddr=%s raddr=%s cmpf=%s border=%s aniso=%ld lodmin=%g lodmax=%g norm=%d\n",
      minf,magf,mipf,saddr,taddr,raddr,cmpf,border,aniso,lodmin,lodmax,normcoord);

    // ---- build texture descriptor ----
    MTLTextureDescriptor *td=[MTLTextureDescriptor new];
    td.pixelFormat=F->pf; td.width=W; td.height=H; td.depth=D;
    td.mipmapLevelCount=mips; td.arrayLength=arraylen; td.sampleCount=samples;
    td.usage=MTLTextureUsageShaderRead; td.storageMode=MTLStorageModeShared;
    if(!strcmp(type,"1d")) td.textureType=MTLTextureType1D;
    else if(!strcmp(type,"3d")) td.textureType=MTLTextureType3D;
    else if(!strcmp(type,"cube")) td.textureType=MTLTextureTypeCube;
    else if(!strcmp(type,"2darray")) td.textureType=MTLTextureType2DArray;
    else if(!strcmp(type,"2dms")){ td.textureType=MTLTextureType2DMultisample; }
    else td.textureType=MTLTextureType2D;
    if(cmp){ td.textureType=MTLTextureType2D; td.pixelFormat=MTLPixelFormatDepth32Float; }
    if(swizzle && strlen(swizzle)>=4){
      td.swizzle=MTLTextureSwizzleChannelsMake(pSw(swizzle[0]),pSw(swizzle[1]),
                                               pSw(swizzle[2]),pSw(swizzle[3]));
    }

    id<MTLTexture> tex=nil; id<MTLBuffer> texbuf=nil;
    if(texoff>=0 && !strcmp(type,"2d") && mips==1 && samples==1){
      // buffer-backed 2D texture: its base GPU VA = texbuf.gpuAddress + texoff.
      NSUInteger align=[dev minimumLinearTextureAlignmentForPixelFormat:F->pf];
      NSUInteger bpp = 4; // conservative; actual bpr computed below
      // bytes-per-row must be >= W*bytesPerPixel and aligned. Query via a scratch:
      NSUInteger bpr = W*16; // 16 covers up to rgba32; align up
      if(align){ bpr = ((bpr+align-1)/align)*align; }
      (void)bpp;
      NSUInteger total = texoff + bpr*H + 0x4000;
      texbuf=[dev newBufferWithLength:total options:MTLResourceStorageModeShared];
      memset([texbuf contents],0x80,total);
      print_va("texbuf",[texbuf gpuAddress]);
      printf("TEXBUF base+off = 0x%llx (off=0x%lx bpr=0x%lx align=0x%lx)\n",
        (unsigned long long)([texbuf gpuAddress]+texoff),(unsigned long)texoff,(unsigned long)bpr,(unsigned long)align);
      tex=[texbuf newTextureWithDescriptor:td offset:texoff bytesPerRow:bpr];
      if(!tex){ printf("TEX_BUFBACK_FAIL\n"); return 1; }
    } else {
      tex=[dev newTextureWithDescriptor:td];
      if(!tex){ printf("TEX_FAIL\n"); return 1; }
    }
    printf("TEX ok type=%s fmt=%s\n",type,F->name);

    int useSampler = !( !strcmp(type,"2dms") ); // MS kernel has no sampler
    // ---- build sampler descriptor ----
    id<MTLSamplerState> smp=nil;
    if(useSampler){
      MTLSamplerDescriptor *sd=[MTLSamplerDescriptor new];
      sd.minFilter=pFilter(minf); sd.magFilter=pFilter(magf); sd.mipFilter=pMip(mipf);
      sd.sAddressMode=pAddr(saddr); sd.tAddressMode=pAddr(taddr); sd.rAddressMode=pAddr(raddr);
      sd.maxAnisotropy=(NSUInteger)aniso;
      sd.normalizedCoordinates=normcoord?YES:NO;
      sd.lodMinClamp=(float)lodmin;
      if(lodmax>=0) sd.lodMaxClamp=(float)lodmax;
      if(cmp) sd.compareFunction=pCmp(cmpf);
      else if(strcmp(cmpf,"never")) sd.compareFunction=pCmp(cmpf);
      @try { sd.borderColor=pBorder(border); } @catch(NSException*e){ printf("BORDER_UNSUPPORTED\n"); }
      smp=[dev newSamplerStateWithDescriptor:sd];
      if(!smp){ printf("SAMPLER_FAIL\n"); return 1; }
      printf("SMP ok\n");
    }

    // ---- kernel ----
    NSString *src=genKernel(type,F->cls,cmp);
    NSError *err=nil;
    id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
    if(!lib){ printf("COMPILE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
    id<MTLFunction> fn=[lib newFunctionWithName:@"k"];
    id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:fn error:&err];
    if(!pso){ printf("PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }

    id<MTLBuffer> obuf=[dev newBufferWithLength:64*4 options:MTLResourceStorageModeShared];
    print_va("obuf",[obuf gpuAddress]);

    id<MTLCommandQueue> q=[dev newCommandQueue];
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
    [enc setComputePipelineState:pso];
    [enc setTexture:tex atIndex:0];
    if(smp) [enc setSamplerState:smp atIndex:0];
    [enc setBuffer:obuf offset:0 atIndex:0];
    [enc dispatchThreads:MTLSizeMake(64,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    printf("SUBMIT done status=%ld\n",(long)[cb status]);
    if([cb status]!=MTLCommandBufferStatusCompleted && [cb error])
      printf("CB_ERROR %s\n",[[[cb error] localizedDescription] UTF8String]);

    if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
    return 0;
  }
}
