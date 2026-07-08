// typrobe2.m — EXP-M4-07 TIL-1: 3D/2DArray/Cube/CubeArray/2DMS twiddle probe
// across ALL bit depths (bpp1/2/4/8/16). Extends EXP-0028 typrobe.m (which only
// probed r32uint / bpp4) with a per-bpp UINT format set and an invertible+hashable
// pattern so the host model-checker (solve3d.py) can, for every candidate layout
// model (tile edge T, cols-padding rule, plane/layer stride rule, MSAA interleave),
// predict the byte offset of element (x,y,s) and count mismatches over the full grid.
//
// Method (HW-PROBE + OWN-SHADER + DATA-TRACE, no Apple binary disassembled):
//   create the texture in the GPU OPTIMAL twiddled layout (StorageModeShared so its
//   backing BO is CPU-mapped and captured by read-only tools/iotrace; ShaderWrite so
//   NO lossless compression engages -> raw Morton), GPU-write a KNOWN pattern where
//   element (x,y,slice) = hash(x,y,slice), bind it (capture descriptor + base VA),
//   and SIGUSR1-dump every registered BO. See ../../CLAUDE.md.
//
// Pattern: 32-bit FNV-1a-style hash hh(x,y,s,k); word k of the texel holds hh(..,k).
//   r8=hh&0xff  r16=hh&0xffff  r32=hh  rg32=(hh0,hh1)  rgba32=(hh0..hh3).
// A hash (not raw coords) lets us probe large non-pow2 dims at bpp1/2 where the texel
// can't hold full coordinates; the solver replicates the hash to model-check.
//
// Build: clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o typrobe2 typrobe2.m
// Usage: typrobe2 --type <2d|3d|2darray|cube|cubearray|2dms> --fmt <r8uint|r16uint|r32uint|rg32uint|rgba32uint>
//                 --w N --h N [--d N] [--arraylen N] [--samples N] --dump

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void print_va(const char *l, uint64_t va){ printf("VA %-10s = 0x%016llx\n",l,(unsigned long long)va); }

// Host-side hash matching the MSL hh()/solve3d.py exactly.
static inline uint32_t hh_c(uint32_t x,uint32_t y,uint32_t s,uint32_t k){
  uint32_t h=2166136261u;
  h=(h^x)*16777619u; h=(h^y)*16777619u; h=(h^s)*16777619u; h=(h^k)*16777619u;
  return h;
}

typedef struct { const char *name; MTLPixelFormat pf; int bpp; int words; } Fmt;
static const Fmt FMTS[] = {
  {"r8uint",     MTLPixelFormatR8Uint,      1, 1},
  {"r16uint",    MTLPixelFormatR16Uint,     2, 1},
  {"r32uint",    MTLPixelFormatR32Uint,     4, 1},
  {"rg32uint",   MTLPixelFormatRG32Uint,    8, 2},
  {"rgba32uint", MTLPixelFormatRGBA32Uint, 16, 4},
};
static const int NFMT=sizeof(FMTS)/sizeof(FMTS[0]);
static const Fmt *findFmt(const char*n){for(int i=0;i<NFMT;i++)if(!strcmp(FMTS[i].name,n))return &FMTS[i];return NULL;}

// MSL hash + per-format store helpers (must match solve3d.py exactly).
static const char *HH =
  "static inline uint hh(uint x,uint y,uint s,uint k){\n"
  "  uint h=2166136261u;\n"
  "  h=(h^x)*16777619u; h=(h^y)*16777619u; h=(h^s)*16777619u; h=(h^k)*16777619u;\n"
  "  return h; }\n";

// Compute image-store write kernel for a given texture type + format words.
static NSString *genWrite(const char*type,int words){
  const char *ttw;   // write-access texture type
  const char *coord; // write coord expression (gid.* -> pixel + slice/z)
  const char *sexpr; // slice index expression
  if(!strcmp(type,"3d")){        ttw="texture3d";          coord="gid";       sexpr="gid.z"; }
  else if(!strcmp(type,"2d")){   ttw="texture2d";          coord="gid.xy";    sexpr="0u"; }
  else {                         ttw="texture2d_array";    coord="gid.xy,gid.z"; sexpr="gid.z"; } // 2darray/cube(view)
  // value words
  char vbuf[512]; char *p=vbuf; p+=sprintf(p,"uint x=gid.x,y=gid.y,s=%s;\n  ",sexpr);
  if(words==1) p+=sprintf(p,"uint4 v=uint4(hh(x,y,s,0),0,0,0);");
  else if(words==2) p+=sprintf(p,"uint4 v=uint4(hh(x,y,s,0),hh(x,y,s,1),0,0);");
  else p+=sprintf(p,"uint4 v=uint4(hh(x,y,s,0),hh(x,y,s,1),hh(x,y,s,2),hh(x,y,s,3));");
  return [NSString stringWithFormat:
    @"#include <metal_stdlib>\nusing namespace metal;\n%s"
     "kernel void wr(%s<uint,access::write> t [[texture(0)]],\n"
     "  uint3 gid [[thread_position_in_grid]]) {\n  %s\n  t.write(v,%s); }\n",
    HH, ttw, vbuf, coord];
}

// MSAA render fragment: per-sample write of hash(x,y,sample_id).
static NSString *genMSRender(int words){
  const char *rt = words==1?"uint": words==2?"uint2":"uint4";
  char vbuf[256];
  if(words==1) sprintf(vbuf,"return hh(x,y,sid,0);");
  else if(words==2) sprintf(vbuf,"return uint2(hh(x,y,sid,0),hh(x,y,sid,1));");
  else sprintf(vbuf,"return uint4(hh(x,y,sid,0),hh(x,y,sid,1),hh(x,y,sid,2),hh(x,y,sid,3));");
  return [NSString stringWithFormat:
    @"#include <metal_stdlib>\nusing namespace metal;\n%s"
     "struct VO { float4 pos [[position]]; };\n"
     "vertex VO v_main(uint vid [[vertex_id]]) {\n"
     "  float2 p[3]={float2(-1,-3),float2(-1,1),float2(3,1)};\n"
     "  VO o; o.pos=float4(p[vid],0,1); return o; }\n"
     "fragment %s f_main(VO in [[stage_in]], uint sid [[sample_id]]) {\n"
     "  uint x=uint(in.pos.x), y=uint(in.pos.y); %s }\n", HH, rt, vbuf];
}

static const char *readTT(const char*type){
  if(!strcmp(type,"3d")) return "texture3d<uint>";
  if(!strcmp(type,"2darray")) return "texture2d_array<uint>";
  if(!strcmp(type,"cube")) return "texturecube<uint>";
  if(!strcmp(type,"cubearray")) return "texturecube_array<uint>";
  if(!strcmp(type,"2dms")) return "texture2d_ms<uint>";
  return "texture2d<uint>";
}

int main(int argc,char**argv){
 @autoreleasepool{
  const char *type="3d",*fmtname="r32uint"; long W=64,H=64,D=4,arraylen=1,samples=1,mips=1; int doDump=0, upload=0;
  for(int i=1;i<argc;i++){ const char*a=argv[i];
    #define ARG(f) (!strcmp(a,f)&&i+1<argc)
    if(ARG("--type")) type=argv[++i];
    else if(ARG("--fmt")) fmtname=argv[++i];
    else if(ARG("--w")) W=strtol(argv[++i],0,0);
    else if(ARG("--h")) H=strtol(argv[++i],0,0);
    else if(ARG("--d")) D=strtol(argv[++i],0,0);
    else if(ARG("--arraylen")) arraylen=strtol(argv[++i],0,0);
    else if(ARG("--samples")) samples=strtol(argv[++i],0,0);
    else if(ARG("--mips")) mips=strtol(argv[++i],0,0);
    else if(!strcmp(a,"--upload")) upload=1;   // CPU replaceRegion instead of GPU write (robust for narrow fmts)
    else if(!strcmp(a,"--dump")) doDump=1;
    #undef ARG
  }
  const Fmt *F=findFmt(fmtname); if(!F){ printf("UNKNOWN_FMT %s\n",fmtname); return 2; }
  int isCube=!strcmp(type,"cube")||!strcmp(type,"cubearray");
  int isMS=!strcmp(type,"2dms"); int is3D=!strcmp(type,"3d");
  int is2D=!strcmp(type,"2d");
  long layers = isCube ? 6*arraylen : arraylen;

  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\n",[[dev name] UTF8String]);
  printf("CONFIG type=%s fmt=%s bpp=%d W=%ld H=%ld D=%ld arraylen=%ld samples=%ld layers=%ld\n",
    type,F->name,F->bpp,W,H,D,arraylen,samples,layers);

  MTLTextureDescriptor *td=[MTLTextureDescriptor new];
  td.pixelFormat=F->pf; td.width=W; td.height=H; td.depth=(is3D?D:1);
  td.arrayLength=arraylen; td.sampleCount=samples; td.mipmapLevelCount=mips;
  td.storageMode=MTLStorageModeShared;
  if(is3D) td.textureType=MTLTextureType3D;
  else if(!strcmp(type,"2darray")) td.textureType=MTLTextureType2DArray;
  else if(!strcmp(type,"cube")) td.textureType=MTLTextureTypeCube;
  else if(!strcmp(type,"cubearray")) td.textureType=MTLTextureTypeCubeArray;
  else if(isMS) td.textureType=MTLTextureType2DMultisample;
  else td.textureType=MTLTextureType2D;
  if(isMS) td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead;
  else if(isCube) td.usage=MTLTextureUsageShaderRead|MTLTextureUsageShaderWrite|MTLTextureUsagePixelFormatView;
  else td.usage=MTLTextureUsageShaderRead|MTLTextureUsageShaderWrite;

  id<MTLTexture> tex=[dev newTextureWithDescriptor:td];
  if(!tex){ printf("TEX_FAIL type=%s fmt=%s\n",type,fmtname); return 1; }
  printf("TEX ok\n");
  id<MTLCommandQueue> q=[dev newCommandQueue];
  NSError *err=nil;

  if(upload){
    // CPU-upload the known pattern via replaceRegion (writes into the twiddled backing).
    // Works for ALL formats/types incl. narrow r8/r16 where compute image-store is
    // unsupported-for-3D/array or CPU-incoherent at capture.
    int bpp=F->bpp, words=F->words;
    // fill+upload one level of one slice at (lw,lh) with pattern hh(x,y,tag)
    void (^fill_upload)(long,long,long,long) = ^(long L,long slice,long lw,long lh){
      long lb=lw*lh*bpp; unsigned char *src=malloc(lb);
      long tag = (mips>1)? L : slice;   // tag by level for mip probe, else by slice
      for(long y=0;y<lh;y++) for(long x=0;x<lw;x++){
        unsigned char *e=src+(y*lw+x)*bpp;
        if(bpp==1) e[0]=hh_c(x,y,tag,0)&0xff;
        else if(bpp==2){ uint32_t v=hh_c(x,y,tag,0)&0xffff; e[0]=v&0xff; e[1]=(v>>8)&0xff; }
        else for(int k=0;k<words;k++){ uint32_t v=hh_c(x,y,tag,k);
               e[k*4]=v&0xff; e[k*4+1]=(v>>8)&0xff; e[k*4+2]=(v>>16)&0xff; e[k*4+3]=(v>>24)&0xff; }
      }
      [tex replaceRegion:MTLRegionMake2D(0,0,lw,lh) mipmapLevel:L slice:slice
              withBytes:src bytesPerRow:lw*bpp bytesPerImage:0];
      free(src);
    };
    if(mips>1){
      for(long L=0;L<mips;L++){ long lw=W>>L,lh=H>>L; if(lw<1)lw=1; if(lh<1)lh=1; fill_upload(L,0,lw,lh); }
      printf("UPLOAD ok mips=%ld\n",mips);
    } else if(is3D){
      long slbytes=W*H*bpp; unsigned char *src=malloc(slbytes*D);
      for(long s=0;s<D;s++) for(long y=0;y<H;y++) for(long x=0;x<W;x++){
        unsigned char *e=src+(s*H+y)*W*bpp+x*bpp;
        if(bpp==1) e[0]=hh_c(x,y,s,0)&0xff;
        else if(bpp==2){ uint32_t v=hh_c(x,y,s,0)&0xffff; e[0]=v&0xff; e[1]=(v>>8)&0xff; }
        else for(int k=0;k<words;k++){ uint32_t v=hh_c(x,y,s,k);
               e[k*4]=v&0xff; e[k*4+1]=(v>>8)&0xff; e[k*4+2]=(v>>16)&0xff; e[k*4+3]=(v>>24)&0xff; }
      }
      [tex replaceRegion:MTLRegionMake3D(0,0,0,W,H,D) mipmapLevel:0 slice:0
              withBytes:src bytesPerRow:W*bpp bytesPerImage:slbytes];
      free(src); printf("UPLOAD ok slices=%ld\n",D);
    } else {
      for(long s=0;s<layers;s++) fill_upload(0,s,W,H);
      printf("UPLOAD ok slices=%ld\n",layers);
    }
  } else if(isMS){
    id<MTLLibrary> lib=[dev newLibraryWithSource:genMSRender(F->words) options:nil error:&err];
    if(!lib){ printf("COMPILE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
    MTLRenderPipelineDescriptor *rpd=[MTLRenderPipelineDescriptor new];
    rpd.vertexFunction=[lib newFunctionWithName:@"v_main"];
    rpd.fragmentFunction=[lib newFunctionWithName:@"f_main"];
    rpd.colorAttachments[0].pixelFormat=F->pf;
    rpd.rasterSampleCount=samples;
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
    [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
    printf("MSRENDER status=%ld\n",(long)[cb status]);
    if([cb status]!=MTLCommandBufferStatusCompleted && [cb error])
      printf("CB_ERROR %s\n",[[[cb error] localizedDescription] UTF8String]);
  } else {
    id<MTLTexture> wtex=tex;
    if(isCube){
      wtex=[tex newTextureViewWithPixelFormat:F->pf textureType:MTLTextureType2DArray
               levels:NSMakeRange(0,1) slices:NSMakeRange(0,layers)];
      if(!wtex){ printf("CUBE_VIEW_FAIL\n"); return 1; }
    }
    const char *wtype = is3D?"3d" : is2D?"2d" : "2darray";  // cube writes via 2darray view
    id<MTLLibrary> lib=[dev newLibraryWithSource:genWrite(wtype,F->words) options:nil error:&err];
    if(!lib){ printf("COMPILE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
    id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"wr"] error:&err];
    if(!pso){ printf("PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
    [enc setComputePipelineState:pso]; [enc setTexture:wtex atIndex:0];
    MTLSize grid = is3D?MTLSizeMake(W,H,D) : is2D?MTLSizeMake(W,H,1) : MTLSizeMake(W,H,layers);
    NSUInteger tgx=W<8?W:8, tgy=H<8?H:8;
    [enc dispatchThreads:grid threadsPerThreadgroup:MTLSizeMake(tgx?tgx:1,tgy?tgy:1,1)];
    [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
    printf("WRITE status=%ld grid=%ldx%ldx%ld\n",(long)[cb status],(long)grid.width,(long)grid.height,(long)grid.depth);
    if([cb status]!=MTLCommandBufferStatusCompleted && [cb error])
      printf("CB_ERROR %s\n",[[[cb error] localizedDescription] UTF8String]);
  }

  // bind (native type) to capture the descriptor + base VA
  {
    const char *tt=readTT(type);
    NSString *rk=[NSString stringWithFormat:
      @"#include <metal_stdlib>\nusing namespace metal;\n"
       "kernel void rd(%s t [[texture(0)]], device uint* o [[buffer(0)]],\n"
       "  uint i [[thread_position_in_grid]]) { o[i]=t.get_width(); }\n", tt];
    id<MTLLibrary> lib=[dev newLibraryWithSource:rk options:nil error:&err];
    id<MTLFunction> fn=lib?[lib newFunctionWithName:@"rd"]:nil;
    id<MTLComputePipelineState> pso=fn?[dev newComputePipelineStateWithFunction:fn error:&err]:nil;
    if(pso){
      id<MTLBuffer> obuf=[dev newBufferWithLength:64*4 options:MTLResourceStorageModeShared];
      print_va("obuf",[obuf gpuAddress]);
      id<MTLCommandBuffer> cb=[q commandBuffer];
      id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
      [enc setComputePipelineState:pso]; [enc setTexture:tex atIndex:0]; [enc setBuffer:obuf offset:0 atIndex:0];
      [enc dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
      [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
      printf("BIND status=%ld\n",(long)[cb status]);
    } else printf("BIND_SKIP %s\n", err?[[err localizedDescription] UTF8String]:"");
  }

  if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(500000); }
  return 0;
 }
}
