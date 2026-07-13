// mortondraw.m — intra-tile Morton byte-order probe via a DRAW FILL (not compute).
// EXP-M5-10 wrote the pattern with a compute kernel; that texture backing was not
// snapshotted. Here we RENDER texel(x,y) = (y<<16)|x into an R32Uint render target
// (twiddled storage), store it, and snapshot the backing BO so morton_find.py can
// read the raw byte order. Clean-room: OWN MSL/API + HW-PROBE (read our own backing).
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <stdlib.h>
int main(int argc,char**argv){@autoreleasepool{
  long W=192,H=192; int doDump=0,useHeap=0,useCompute=0;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--dump"))doDump=1;
    else if(!strcmp(argv[i],"--heap"))useHeap=1;
    else if(!strcmp(argv[i],"--compute"))useCompute=1; // image-store (RAW twiddle); draw/RT-store compresses
    else if(!strcmp(argv[i],"--w")&&i+1<argc)W=atol(argv[++i]);
    else if(!strcmp(argv[i],"--h")&&i+1<argc)H=atol(argv[++i]);
  }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  MTLPixelFormat pxf=MTLPixelFormatR32Uint;
  MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:pxf width:W height:H mipmapped:NO];
  // ShaderWrite disables lossless compression so the backing holds RAW twiddled Morton
  // values (a RenderTarget|ShaderRead-only texture would be compressed = no raw curve).
  td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead|MTLTextureUsageShaderWrite; td.storageMode=MTLStorageModeShared;
  id<MTLTexture> tex=nil; id<MTLHeap> heap=nil;
  if(useHeap){
    // Place the twiddled texture inside a StorageModeShared HEAP. The heap backing is a
    // single sel-9-registered buffer, so its bytes (incl. the texture) ARE snapshotted by
    // iotrace, unlike a standalone M5 texture (whose backing escapes the sel-9 data-trace).
    MTLSizeAndAlign sa=[dev heapTextureSizeAndAlignWithDescriptor:td];
    MTLHeapDescriptor*hd=[MTLHeapDescriptor new];
    hd.storageMode=MTLStorageModeShared; hd.size=sa.size+sa.align+0x4000;
    heap=[dev newHeapWithDescriptor:hd];
    if(!heap){printf("HEAP_FAIL\n");return 1;}
    tex=[heap newTextureWithDescriptor:td];
    if(!tex){printf("HEAP_TEX_FAIL\n");return 1;}
    printf("MORTONDRAW HEAP heapSize=0x%lx texSizeInHeap=0x%lx\n",(unsigned long)[heap size],(unsigned long)sa.size);
  } else {
    tex=[dev newTextureWithDescriptor:td];
  }
  printf("DEVICE %s MORTONDRAW fmt=r32u W=%ld H=%ld heap=%d allocatedSize=0x%lx\n",
    [[dev name]UTF8String],W,H,useHeap,(unsigned long)[tex allocatedSize]);
  NSError*err=nil;
  NSString*src=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "struct VO{float4 pos [[position]];};\n"
    "vertex VO v_main(uint vid[[vertex_id]]){float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};VO o;o.pos=float4(p[vid%3],0,1);return o;}\n"
    "fragment uint4 f_main(VO in[[stage_in]]){uint x=uint(in.pos.x);uint y=uint(in.pos.y);return uint4((y<<16)|x,0,0,0);}\n";
  id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
  if(!lib){printf("COMPILE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  id<MTLCommandQueue> q=[dev newCommandQueue];
  if(useCompute){
    // RAW-twiddle path: image-store (y<<16)|x per texel. Unlike an RT store, a shader
    // image write is not lossless-compressed, so the backing holds the raw twiddled curve.
    NSString*cs=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "kernel void wr(texture2d<uint,access::write> t[[texture(0)]],uint2 g[[thread_position_in_grid]]){t.write(uint4((g.y<<16)|g.x,0,0,0),g);}\n";
    id<MTLLibrary> cl=[dev newLibraryWithSource:cs options:nil error:&err];
    if(!cl){printf("COMPILE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    id<MTLComputePipelineState> cpso=[dev newComputePipelineStateWithFunction:[cl newFunctionWithName:@"wr"] error:&err];
    if(!cpso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
    [enc setComputePipelineState:cpso];[enc setTexture:tex atIndex:0];
    [enc dispatchThreads:MTLSizeMake(W,H,1) threadsPerThreadgroup:MTLSizeMake(8,8,1)];
    [enc endEncoding];[cb commit];[cb waitUntilCompleted];
    printf("STATUS=%ld\n",(long)[cb status]);
  } else {
    MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
    pd.vertexFunction=[lib newFunctionWithName:@"v_main"];pd.fragmentFunction=[lib newFunctionWithName:@"f_main"];
    pd.colorAttachments[0].pixelFormat=pxf;
    id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
    if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
    rp.colorAttachments[0].texture=tex;rp.colorAttachments[0].loadAction=MTLLoadActionClear;rp.colorAttachments[0].storeAction=MTLStoreActionStore;
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [enc endEncoding];[cb commit];[cb waitUntilCompleted];
    printf("STATUS=%ld\n",(long)[cb status]);
  }
  // sanity: getBytes linearizes the twiddled texture; pixel (3,2) must read (2<<16)|3.
  uint32_t v=0;
  [tex getBytes:&v bytesPerRow:4 fromRegion:MTLRegionMake2D(3,2,1,1) mipmapLevel:0];
  printf("PIXEL (3,2)=0x%08x (expect 0x00020003)\n",v);
  if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(400000);}
  return 0;
}}
