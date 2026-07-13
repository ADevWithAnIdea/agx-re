// indir.m — indirect dispatch / indirect draw / mesh / tessellation command-record probe.
// Clean-room: our own MSL + Metal API; dumps our own command-stream BOs.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <stdlib.h>
static void dumpNow(int d){ if(d){fflush(stdout);kill(getpid(),SIGUSR1);usleep(400000);} }

int main(int argc,char**argv){@autoreleasepool{
  const char*mode="idispatch"; int doDump=0;
  for(int i=1;i<argc;i++){ if(!strcmp(argv[i],"--dump"))doDump=1; else if(!strcmp(argv[i],"--mode")&&i+1<argc)mode=argv[++i]; }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s mode=%s\n",[[dev name]UTF8String],mode);
  id<MTLCommandQueue> q=[dev newCommandQueue];
  NSError*err=nil;

  if(!strcmp(mode,"idispatch")||!strcmp(mode,"dispatch")){
    int indirect = !strcmp(mode,"idispatch");
    NSString*src=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "kernel void k(device float*o[[buffer(0)]],uint i[[thread_position_in_grid]]){o[i]=i;}\n";
    id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
    id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"k"] error:&err];
    if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    id<MTLBuffer> o=[dev newBufferWithLength:4096 options:MTLResourceStorageModeShared];
    uint32_t args[3]={4,1,1}; id<MTLBuffer> ind=[dev newBufferWithBytes:args length:12 options:MTLResourceStorageModeShared];
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
    [enc setComputePipelineState:pso];[enc setBuffer:o offset:0 atIndex:0];
    if(indirect)[enc dispatchThreadgroupsWithIndirectBuffer:ind indirectBufferOffset:0 threadsPerThreadgroup:MTLSizeMake(32,1,1)];
    else [enc dispatchThreadgroups:MTLSizeMake(4,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
    [enc endEncoding];[cb commit];[cb waitUntilCompleted];
    printf("STATUS=%ld\n",(long)[cb status]); dumpNow(doDump); return 0;
  }

  // shared graphics setup for draw/mesh/tess
  MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:64 height:64 mipmapped:NO];
  td.usage=MTLTextureUsageRenderTarget;td.storageMode=MTLStorageModeShared;
  id<MTLTexture> target=[dev newTextureWithDescriptor:td];
  MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
  rp.colorAttachments[0].texture=target;rp.colorAttachments[0].loadAction=MTLLoadActionClear;
  rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1);rp.colorAttachments[0].storeAction=MTLStoreActionStore;

  if(!strcmp(mode,"idraw")||!strcmp(mode,"idrawidx")){
    NSString*src=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "struct VO{float4 pos [[position]];};\n"
      "vertex VO v_main(uint vid[[vertex_id]]){float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};VO o;o.pos=float4(p[vid%3],0,1);return o;}\n"
      "fragment float4 f_main(VO in[[stage_in]]){return float4(1,0.5,0.25,1);}\n";
    id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
    MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
    pd.vertexFunction=[lib newFunctionWithName:@"v_main"];pd.fragmentFunction=[lib newFunctionWithName:@"f_main"];
    pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
    id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
    if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    if(!strcmp(mode,"idraw")){
      uint32_t a[4]={3,1,0,0}; id<MTLBuffer> ind=[dev newBufferWithBytes:a length:16 options:MTLResourceStorageModeShared];
      [enc drawPrimitives:MTLPrimitiveTypeTriangle indirectBuffer:ind indirectBufferOffset:0];
    } else {
      uint16_t ix[3]={0,1,2}; id<MTLBuffer> ib=[dev newBufferWithBytes:ix length:6 options:MTLResourceStorageModeShared];
      uint32_t a[5]={3,1,0,0,0}; id<MTLBuffer> ind=[dev newBufferWithBytes:a length:20 options:MTLResourceStorageModeShared];
      [enc drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexType:MTLIndexTypeUInt16 indexBuffer:ib indexBufferOffset:0 indirectBuffer:ind indirectBufferOffset:0];
    }
    [enc endEncoding];[cb commit];[cb waitUntilCompleted];
    printf("STATUS=%ld\n",(long)[cb status]); dumpNow(doDump); return 0;
  }

  if(!strcmp(mode,"mesh")){
    NSString*src=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "struct VO{float4 pos [[position]];};\n"
      "struct Payload{uint v;};\n"
      "using MOut=metal::mesh<VO,void,3,1,metal::topology::triangle>;\n"
      "[[object]] void o_main(object_data Payload& payload [[payload]],mesh_grid_properties mgp){payload.v=0;mgp.set_threadgroups_per_grid(uint3(1,1,1));}\n"
      "[[mesh]] void m_main(MOut m, const object_data Payload& payload [[payload]]){m.set_primitive_count(1);float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};for(uint i=0;i<3;i++){VO v;v.pos=float4(p[i],0,1);m.set_vertex(i,v);m.set_index(i,i);}}\n"
      "fragment float4 f_main(VO in[[stage_in]]){return float4(0.2,0.4,0.8,1);}\n";
    id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
    if(!lib){printf("COMPILE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    MTLMeshRenderPipelineDescriptor*pd=[MTLMeshRenderPipelineDescriptor new];
    pd.objectFunction=[lib newFunctionWithName:@"o_main"];
    pd.meshFunction=[lib newFunctionWithName:@"m_main"];
    pd.fragmentFunction=[lib newFunctionWithName:@"f_main"];
    pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
    id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd options:0 reflection:nil error:&err];
    if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    [enc drawMeshThreadgroups:MTLSizeMake(1,1,1) threadsPerObjectThreadgroup:MTLSizeMake(1,1,1) threadsPerMeshThreadgroup:MTLSizeMake(3,1,1)];
    [enc endEncoding];[cb commit];[cb waitUntilCompleted];
    printf("STATUS=%ld\n",(long)[cb status]); dumpNow(doDump); return 0;
  }

  if(!strcmp(mode,"tess")){
    NSString*src=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "struct VO{float4 pos [[position]];};\n"
      "struct CP{float4 p [[attribute(0)]];};\n"
      "[[patch(triangle,3)]] vertex VO v_post(patch_control_point<CP> cp [[stage_in]],float3 bc[[position_in_patch]]){VO o;o.pos=float4(bc.x-0.5+0*cp[0].p.x,bc.y-0.5,0,1);return o;}\n"
      "fragment float4 f_main(VO in[[stage_in]]){return float4(0.7,0.3,0.1,1);}\n";
    id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
    if(!lib){printf("COMPILE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
    pd.vertexFunction=[lib newFunctionWithName:@"v_post"];pd.fragmentFunction=[lib newFunctionWithName:@"f_main"];
    pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
    pd.maxTessellationFactor=16;pd.tessellationPartitionMode=MTLTessellationPartitionModeInteger;
    pd.tessellationFactorFormat=MTLTessellationFactorFormatHalf;
    pd.tessellationOutputWindingOrder=MTLWindingClockwise;
    MTLVertexDescriptor*vd=[MTLVertexDescriptor new];
    vd.attributes[0].format=MTLVertexFormatFloat4;vd.attributes[0].offset=0;vd.attributes[0].bufferIndex=0;
    vd.layouts[0].stride=16;vd.layouts[0].stepFunction=MTLVertexStepFunctionPerPatchControlPoint;
    pd.vertexDescriptor=vd;
    id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
    if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    float cp[12]={-1,-1,0,1, 3,-1,0,1, -1,3,0,1}; id<MTLBuffer> cpb=[dev newBufferWithBytes:cp length:48 options:MTLResourceStorageModeShared];
    uint16_t tf[4]={0x4c00,0x4c00,0x4c00,0x4c00}; // half 16.0 edges+inside
    id<MTLBuffer> tfb=[dev newBufferWithBytes:tf length:8 options:MTLResourceStorageModeShared];
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];[enc setVertexBuffer:cpb offset:0 atIndex:0];
    [enc setTessellationFactorBuffer:tfb offset:0 instanceStride:0];
    [enc drawPatches:3 patchStart:0 patchCount:1 patchIndexBuffer:nil patchIndexBufferOffset:0 instanceCount:1 baseInstance:0];
    [enc endEncoding];[cb commit];[cb waitUntilCompleted];
    printf("STATUS=%ld\n",(long)[cb status]); dumpNow(doDump); return 0;
  }
  printf("UNKNOWN_MODE\n"); return 1;
}}
