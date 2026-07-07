// typrobe.m — EXP-0028 twiddle-layout probe for the UNTESTED texture TYPES:
// 1DArray, 2DArray, Cube, CubeArray, 3D, and 2DMS (sample interleave).
//
// Method (extends EXP-0017 texprobe.m): create the texture in the GPU OPTIMAL
// (twiddled, StorageModeShared, ShaderWrite=no-compression) layout, GPU-write a
// KNOWN pattern where element (x,y,slice) stores encode(x,y,slice), bind the
// texture into the Tier-2 argument buffer, and SIGUSR1-dump every registered BO
// via the read-only iotrace interposer. Host-side tw3.py maps physical byte
// offset -> (x,y,slice) to solve the layer/slice/sample layout: linear-stacked
// planes vs interleaved Morton.
//
//  - array/3D/cube writes are done with an r32uint compute image-store; cube is
//    written through a 2D-array VIEW (shares the cube's backing memory).
//  - MSAA (2DMS) is written by RENDERING an r32uint target with a fragment shader
//    keyed on [[sample_id]] (forces per-sample shading), StoreActionStore so the
//    raw multisample samples land in DRAM.
//
// CLEAN-ROOM: HW-PROBE (known pattern in, raw layout out) + OWN-SHADER + DATA-TRACE.
// No Apple binary is disassembled. See ../../CLAUDE.md.
//
// Build (device): clang -fobjc-arc -framework Metal -framework Foundation -o typrobe typrobe.m
// Usage: typrobe --type <3d|2darray|1darray|cube|cubearray|2dms> --w N --h N
//                [--d N] [--arraylen N] [--samples N] --dump

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void print_va(const char *l, uint64_t va){ printf("VA %-10s = 0x%016llx\n",l,(unsigned long long)va); }

// value(x,y,s) = 0xA5A5<<16 | (s&0xf)<<8 | (y&0xf)<<4 | (x&0xf)   (dims/slices <=16)
static NSString *genArrayWrite(void){ return
  @"#include <metal_stdlib>\nusing namespace metal;\n"
   "kernel void wr(texture2d_array<uint, access::write> t [[texture(0)]],\n"
   "  uint3 gid [[thread_position_in_grid]]) {\n"
   "  uint v=0xA5A50000u|((gid.z&0xf)<<8)|((gid.y&0xf)<<4)|(gid.x&0xf);\n"
   "  t.write(uint4(v,0,0,0), gid.xy, gid.z); }\n"; }
static NSString *gen1DArrayWrite(void){ return
  @"#include <metal_stdlib>\nusing namespace metal;\n"
   "kernel void wr(texture1d_array<uint, access::write> t [[texture(0)]],\n"
   "  uint2 gid [[thread_position_in_grid]]) {\n"   // gid.x=x, gid.y=layer
   "  uint v=0xA5A50000u|((gid.y&0xf)<<8)|(gid.x&0xf);\n"
   "  t.write(uint4(v,0,0,0), gid.x, gid.y); }\n"; }
static NSString *gen3DWrite(void){ return
  @"#include <metal_stdlib>\nusing namespace metal;\n"
   "kernel void wr(texture3d<uint, access::write> t [[texture(0)]],\n"
   "  uint3 gid [[thread_position_in_grid]]) {\n"
   "  uint v=0xA5A50000u|((gid.z&0xf)<<8)|((gid.y&0xf)<<4)|(gid.x&0xf);\n"
   "  t.write(uint4(v,0,0,0), gid); }\n"; }
// MSAA render: per-sample fragment writing encode(x,y,sample_id) into r32uint target.
static NSString *genMSRender(void){ return
  @"#include <metal_stdlib>\nusing namespace metal;\n"
   "struct VO { float4 pos [[position]]; };\n"
   "vertex VO v_main(uint vid [[vertex_id]]) {\n"
   "  float2 p[3]={float2(-1,-3),float2(-1,1),float2(3,1)};\n"
   "  VO o; o.pos=float4(p[vid],0,1); return o; }\n"
   "fragment uint f_main(VO in [[stage_in]], uint sid [[sample_id]]) {\n"
   "  uint x=uint(in.pos.x), y=uint(in.pos.y);\n"
   "  return 0xA5A50000u|((sid&0xf)<<8)|((y&0xf)<<4)|(x&0xf); }\n"; }
// read kernel to bind the texture (capture its descriptor + base VA).
static const char *readTT(const char*type){
  if(!strcmp(type,"3d")) return "texture3d<uint>";
  if(!strcmp(type,"2darray")) return "texture2d_array<uint>";
  if(!strcmp(type,"1darray")) return "texture1d_array<uint>";
  if(!strcmp(type,"cube")) return "texturecube<uint>";
  if(!strcmp(type,"cubearray")) return "texturecube_array<uint>";
  if(!strcmp(type,"2dms")) return "texture2d_ms<uint>";
  return "texture2d<uint>";
}

int main(int argc,char**argv){
 @autoreleasepool{
  const char *type="3d"; long W=16,H=16,D=16,arraylen=1,samples=1; int doDump=0;
  for(int i=1;i<argc;i++){ const char*a=argv[i];
    #define ARG(f) (!strcmp(a,f)&&i+1<argc)
    if(ARG("--type")) type=argv[++i];
    else if(ARG("--w")) W=strtol(argv[++i],0,0);
    else if(ARG("--h")) H=strtol(argv[++i],0,0);
    else if(ARG("--d")) D=strtol(argv[++i],0,0);
    else if(ARG("--arraylen")) arraylen=strtol(argv[++i],0,0);
    else if(ARG("--samples")) samples=strtol(argv[++i],0,0);
    else if(!strcmp(a,"--dump")) doDump=1;
    #undef ARG
  }
  int isCube = !strcmp(type,"cube")||!strcmp(type,"cubearray");
  int isMS   = !strcmp(type,"2dms");
  int is1D   = !strcmp(type,"1darray");
  int is3D   = !strcmp(type,"3d");
  long layers = isCube ? 6*arraylen : arraylen;   // cube = 6 faces/cube

  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\n",[[dev name] UTF8String]);
  printf("CONFIG type=%s W=%ld H=%ld D=%ld arraylen=%ld samples=%ld layers=%ld\n",
    type,W,H,D,arraylen,samples,layers);

  MTLTextureDescriptor *td=[MTLTextureDescriptor new];
  td.pixelFormat = MTLPixelFormatR32Uint;
  td.width=W; td.height=(is1D?1:H); td.depth=(is3D?D:1);
  td.arrayLength=arraylen; td.sampleCount=samples;
  td.storageMode = MTLStorageModeShared;
  if(is3D)          td.textureType=MTLTextureType3D;
  else if(!strcmp(type,"2darray")) td.textureType=MTLTextureType2DArray;
  else if(is1D)     td.textureType=MTLTextureType1DArray;
  else if(!strcmp(type,"cube")) td.textureType=MTLTextureTypeCube;
  else if(!strcmp(type,"cubearray")) td.textureType=MTLTextureTypeCubeArray;
  else if(isMS)     td.textureType=MTLTextureType2DMultisample;
  else              td.textureType=MTLTextureType2D;
  if(isMS){ td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead; }
  else if(isCube){ td.usage=MTLTextureUsageShaderRead|MTLTextureUsageShaderWrite|MTLTextureUsagePixelFormatView; }
  else { td.usage=MTLTextureUsageShaderRead|MTLTextureUsageShaderWrite; }

  id<MTLTexture> tex=[dev newTextureWithDescriptor:td];
  if(!tex){ printf("TEX_FAIL type=%s\n",type); return 1; }
  printf("TEX ok type=%s bytesPerRow?=n/a\n",type);

  id<MTLCommandQueue> q=[dev newCommandQueue];
  NSError *err=nil;

  // ---- write the known pattern ----
  if(isMS){
    id<MTLLibrary> lib=[dev newLibraryWithSource:genMSRender() options:nil error:&err];
    if(!lib){ printf("COMPILE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
    MTLRenderPipelineDescriptor *rpd=[MTLRenderPipelineDescriptor new];
    rpd.vertexFunction=[lib newFunctionWithName:@"v_main"];
    rpd.fragmentFunction=[lib newFunctionWithName:@"f_main"];
    rpd.colorAttachments[0].pixelFormat=MTLPixelFormatR32Uint;
    rpd.rasterSampleCount=samples;
    id<MTLRenderPipelineState> rps=[dev newRenderPipelineStateWithDescriptor:rpd error:&err];
    if(!rps){ printf("RPIPE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
    MTLRenderPassDescriptor *rp=[MTLRenderPassDescriptor renderPassDescriptor];
    rp.colorAttachments[0].texture=tex;
    rp.colorAttachments[0].loadAction=MTLLoadActionClear;
    rp.colorAttachments[0].storeAction=MTLStoreActionStore;         // keep raw MS samples
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
    // choose write target: cube -> a 2D-array VIEW; else the texture itself.
    id<MTLTexture> wtex=tex;
    if(isCube){
      wtex=[tex newTextureViewWithPixelFormat:MTLPixelFormatR32Uint
               textureType:MTLTextureType2DArray levels:NSMakeRange(0,1)
               slices:NSMakeRange(0,layers)];
      if(!wtex){ printf("CUBE_VIEW_FAIL\n"); return 1; }
    }
    NSString *src = is3D?gen3DWrite() : is1D?gen1DArrayWrite() : genArrayWrite();
    id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
    if(!lib){ printf("COMPILE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
    id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"wr"] error:&err];
    if(!pso){ printf("PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
    [enc setComputePipelineState:pso];
    [enc setTexture:wtex atIndex:0];
    MTLSize grid = is3D ? MTLSizeMake(W,H,D)
                 : is1D ? MTLSizeMake(W,layers,1)
                 :        MTLSizeMake(W,H,layers);
    [enc dispatchThreads:grid threadsPerThreadgroup:MTLSizeMake(is1D?W:8, is1D?1:8, 1)];
    [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
    printf("WRITE status=%ld grid=%ldx%ldx%ld\n",(long)[cb status],(long)grid.width,(long)grid.height,(long)grid.depth);
    if([cb status]!=MTLCommandBufferStatusCompleted && [cb error])
      printf("CB_ERROR %s\n",[[[cb error] localizedDescription] UTF8String]);
  }

  // ---- bind the texture (its native type) to capture the descriptor + base VA ----
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
      [enc setComputePipelineState:pso];
      [enc setTexture:tex atIndex:0];
      [enc setBuffer:obuf offset:0 atIndex:0];
      [enc dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
      [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
      printf("BIND status=%ld\n",(long)[cb status]);
    } else printf("BIND_SKIP %s\n", err?[[err localizedDescription] UTF8String]:"");
  }

  if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(500000); }
  return 0;
 }
}
