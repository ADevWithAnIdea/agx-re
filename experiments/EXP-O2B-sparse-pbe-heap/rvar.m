// rvar.m — parametric OWN compute program for O2-B resource-feature descriptor RE.
// Binds ONE texture (+ sampler + output buffer) into the Metal Tier-2 argument buffer and
// dispatches a tiny compute kernel that samples the texture. Every knob relevant to
// sparse / placement-heap / render-target(PBE) / 32-bit-float-filtering is a CLI flag, so a
// single Metal parameter can be changed and the appended descriptor block byte-diffed under
// the read-only tools/iotrace interposer (sibling of EXP-0015 tvar.m).
//
// CLEAN-ROOM: OWN-SHADER + public Metal API + HW-PROBE. Our MSL, our resources (whose GPU
// VAs we print for correlation). Nothing disassembles any Apple binary. See ../../CLAUDE.md.
//
// Build (device): clang -fobjc-arc -framework Metal -framework Foundation -o rvar rvar.m
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void print_va(const char*l,uint64_t va){
  printf("VA %-10s = 0x%016llx\n",l,(unsigned long long)va);
}

static MTLPixelFormat pfmt(const char*s){
  if(!strcmp(s,"r32float"))    return MTLPixelFormatR32Float;
  if(!strcmp(s,"rg32float"))   return MTLPixelFormatRG32Float;
  if(!strcmp(s,"rgba32float")) return MTLPixelFormatRGBA32Float;
  if(!strcmp(s,"r16float"))    return MTLPixelFormatR16Float;
  if(!strcmp(s,"rgba16float")) return MTLPixelFormatRGBA16Float;
  if(!strcmp(s,"r32uint"))     return MTLPixelFormatR32Uint;
  return MTLPixelFormatRGBA8Unorm;
}

int main(int argc,char**argv){ @autoreleasepool {
  const char*fmt="rgba8unorm",*usage="read",*heap="none",*storage="private",*filter="nearest";
  long W=64,H=64; int doDump=0,doMap=0,doGrad=0,unmap=0;
  for(int i=1;i<argc;i++){ const char*a=argv[i];
    #define ARG(f) (!strcmp(a,f)&&i+1<argc)
    if(ARG("--fmt")) fmt=argv[++i];
    else if(ARG("--usage")) usage=argv[++i];
    else if(ARG("--heap")) heap=argv[++i];
    else if(ARG("--storage")) storage=argv[++i];
    else if(ARG("--filter")) filter=argv[++i];
    else if(ARG("--w")) W=strtol(argv[++i],0,0);
    else if(ARG("--h")) H=strtol(argv[++i],0,0);
    else if(!strcmp(a,"--map")) doMap=1;
    else if(!strcmp(a,"--unmap")) unmap=1;
    else if(!strcmp(a,"--grad")) doGrad=1;
    else if(!strcmp(a,"--dump")) doDump=1;
    #undef ARG
  }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  MTLPixelFormat pf=pfmt(fmt);
  printf("DEVICE %s\nCONFIG fmt=%s usage=%s heap=%s storage=%s filter=%s W=%ld H=%ld map=%d grad=%d\n",
    [[dev name] UTF8String],fmt,usage,heap,storage,filter,W,H,doMap,doGrad);

  MTLTextureUsage u=MTLTextureUsageShaderRead;
  if(!strcmp(usage,"read"))        u=MTLTextureUsageShaderRead;
  else if(!strcmp(usage,"readrt")) u=MTLTextureUsageShaderRead|MTLTextureUsageRenderTarget;
  else if(!strcmp(usage,"readwrite")) u=MTLTextureUsageShaderRead|MTLTextureUsageShaderWrite;
  else if(!strcmp(usage,"readpix")) u=MTLTextureUsageShaderRead|MTLTextureUsagePixelFormatView;
  else if(!strcmp(usage,"readatom")) u=MTLTextureUsageShaderRead|MTLTextureUsageShaderAtomic;
  else if(!strcmp(usage,"rtonly")) u=MTLTextureUsageRenderTarget;

  MTLStorageMode sm = !strcmp(storage,"shared")?MTLStorageModeShared:MTLStorageModePrivate;

  MTLTextureDescriptor* td=[MTLTextureDescriptor new];
  td.pixelFormat=pf; td.width=W; td.height=H; td.textureType=MTLTextureType2D;
  td.usage=u; td.storageMode=sm; td.mipmapLevelCount=1;

  id<MTLTexture> tex=nil; id<MTLHeap> hp=nil;
  if(!strcmp(heap,"none")){
    tex=[dev newTextureWithDescriptor:td];
  } else if(!strcmp(heap,"auto")||!strcmp(heap,"placement")){
    MTLHeapDescriptor* hd=[MTLHeapDescriptor new];
    hd.type = !strcmp(heap,"placement")?MTLHeapTypePlacement:MTLHeapTypeAutomatic;
    hd.storageMode=MTLStorageModePrivate;
    MTLSizeAndAlign sa=[dev heapTextureSizeAndAlignWithDescriptor:td];
    hd.size = sa.size + sa.align + (16<<20);
    hp=[dev newHeapWithDescriptor:hd];
    if(!strcmp(heap,"placement")) tex=[hp newTextureWithDescriptor:td offset:0];
    else tex=[hp newTextureWithDescriptor:td];
    printf("HEAP %s sizeAndAlign size=%lu align=%lu\n",heap,(unsigned long)sa.size,(unsigned long)sa.align);
  } else if(!strcmp(heap,"sparse")){
    MTLHeapDescriptor* hd=[MTLHeapDescriptor new];
    hd.type=MTLHeapTypeSparse; hd.storageMode=MTLStorageModePrivate; hd.size=64<<20;
    hp=[dev newHeapWithDescriptor:hd];
    td.storageMode=MTLStorageModePrivate;
    tex=[hp newTextureWithDescriptor:td];
    MTLSize ts=[dev sparseTileSizeWithTextureType:MTLTextureType2D pixelFormat:pf sampleCount:1];
    printf("SPARSE tile=%lux%lu tileBytes=%lu\n",(unsigned long)ts.width,(unsigned long)ts.height,(unsigned long)[dev sparseTileSizeInBytes]);
  }
  if(!tex){ printf("TEX_FAIL\n"); return 1; }
  printf("TEX ok gpuResourceID=0x%llx\n",(unsigned long long)tex.gpuResourceID._impl);

  // Gradient fill (shared only) for filtering HW-validation: 2x2 r32float = 0,1,2,3
  if(doGrad && sm==MTLStorageModeShared && pf==MTLPixelFormatR32Float && W>=2 && H>=2){
    float row0[2]={0.0f,1.0f}, row1[2]={2.0f,3.0f};
    [tex replaceRegion:MTLRegionMake2D(0,0,2,1) mipmapLevel:0 withBytes:row0 bytesPerRow:8];
    [tex replaceRegion:MTLRegionMake2D(0,1,2,1) mipmapLevel:0 withBytes:row1 bytesPerRow:8];
    printf("GRAD filled 2x2 [0,1,2,3]\n");
  }

  id<MTLCommandQueue> q=[dev newCommandQueue];

  // Sparse tile residency mapping (exercise the residency path).
  if(!strcmp(heap,"sparse") && (doMap||unmap)){
    id<MTLCommandBuffer> rcb=[q commandBuffer];
    id<MTLResourceStateCommandEncoder> rs=[rcb resourceStateCommandEncoder];
    MTLSize ts=[dev sparseTileSizeWithTextureType:MTLTextureType2D pixelFormat:pf sampleCount:1];
    MTLRegion reg=MTLRegionMake2D(0,0,ts.width,ts.height); // one tile at origin
    [rs updateTextureMapping:tex mode:(unmap?MTLSparseTextureMappingModeUnmap:MTLSparseTextureMappingModeMap)
                      region:reg mipLevel:0 slice:0];
    [rs endEncoding];
    [rcb commit]; [rcb waitUntilCompleted];
    printf("SPARSE_%s status=%ld\n", unmap?"UNMAP":"MAP",(long)[rcb status]);
  }

  // Sampler
  MTLSamplerDescriptor* sd=[MTLSamplerDescriptor new];
  MTLSamplerMinMagFilter f = !strcmp(filter,"linear")?MTLSamplerMinMagFilterLinear:MTLSamplerMinMagFilterNearest;
  sd.minFilter=f; sd.magFilter=f; sd.normalizedCoordinates=YES;
  sd.sAddressMode=MTLSamplerAddressModeClampToEdge; sd.tAddressMode=MTLSamplerAddressModeClampToEdge;
  id<MTLSamplerState> smp=[dev newSamplerStateWithDescriptor:sd];

  // Kernel: sample at center, write to o[0]; also sample a grid for filtering evidence.
  const char* comp = (pf==MTLPixelFormatR32Uint)?"uint":"float";
  NSString* src=[NSString stringWithFormat:
    @"#include <metal_stdlib>\nusing namespace metal;\n"
     "kernel void k(texture2d<%s> t [[texture(0)]], sampler s [[sampler(0)]],\n"
     "  device float* o [[buffer(0)]], uint i [[thread_position_in_grid]]) {\n"
     "  float2 uv = float2((float)(i%%4)/3.0, (float)(i/4)/3.0);\n"
     "  o[i]=float(t.sample(s, uv).x); }\n", comp];
  NSError* err=nil;
  id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
  if(!lib){ printf("COMPILE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
  id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"k"] error:&err];
  if(!pso){ printf("PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }

  id<MTLBuffer> obuf=[dev newBufferWithLength:64*4 options:MTLResourceStorageModeShared];
  print_va("obuf", obuf.gpuAddress);

  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
  [enc setComputePipelineState:pso];
  if(hp) [enc useHeap:hp]; // residency for heap-backed textures
  [enc setTexture:tex atIndex:0];
  [enc setSamplerState:smp atIndex:0];
  [enc setBuffer:obuf offset:0 atIndex:0];
  [enc dispatchThreads:MTLSizeMake(16,1,1) threadsPerThreadgroup:MTLSizeMake(16,1,1)];
  [enc endEncoding];
  [cb commit]; [cb waitUntilCompleted];
  printf("SUBMIT status=%ld\n",(long)[cb status]);
  if([cb status]!=MTLCommandBufferStatusCompleted && [cb error])
    printf("CB_ERROR %s\n",[[[cb error] localizedDescription] UTF8String]);
  float* o=(float*)[obuf contents];
  printf("SAMPLES");
  for(int i=0;i<16;i++) printf(" %.4f",o[i]);
  printf("\n");

  if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
  return 0;
}}
