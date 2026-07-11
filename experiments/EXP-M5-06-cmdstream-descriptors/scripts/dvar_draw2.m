// dvar_draw2.m — draw with optional depth/stencil, cull, viewport, indexed. Clean-room own MSL/API.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
int main(int argc,char**argv){@autoreleasepool{
  int doDump=0,depth=0,cull=0,vp=0,idx=0,idx32=0; long verts=3;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--dump"))doDump=1;
    else if(!strcmp(argv[i],"--depth"))depth=1;
    else if(!strcmp(argv[i],"--cull"))cull=1;
    else if(!strcmp(argv[i],"--vp"))vp=1;
    else if(!strcmp(argv[i],"--idx16")){idx=1;}
    else if(!strcmp(argv[i],"--idx32")){idx=1;idx32=1;}
    else if(!strcmp(argv[i],"--verts")&&i+1<argc)verts=atol(argv[++i]);
  }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s depth=%d cull=%d vp=%d idx=%d idx32=%d\n",[[dev name]UTF8String],depth,cull,vp,idx,idx32);
  NSString*src=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "struct VO{float4 pos [[position]];float4 col;};\n"
    "vertex VO v_main(uint vid[[vertex_id]]){float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};VO o;o.pos=float4(p[vid%3],0.5,1);o.col=float4(0.25,0.5,0.75,1);return o;}\n"
    "fragment float4 f_main(VO in[[stage_in]]){return in.col;}\n";
  NSError*err=nil;
  id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
  if(!lib){printf("COMPILE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
  pd.vertexFunction=[lib newFunctionWithName:@"v_main"];pd.fragmentFunction=[lib newFunctionWithName:@"f_main"];
  pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
  if(depth)pd.depthAttachmentPixelFormat=MTLPixelFormatDepth32Float;
  id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
  if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:64 height:64 mipmapped:NO];
  td.usage=MTLTextureUsageRenderTarget;td.storageMode=MTLStorageModeShared;
  id<MTLTexture> target=[dev newTextureWithDescriptor:td];
  id<MTLTexture> dtex=nil;
  if(depth){MTLTextureDescriptor*dd=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatDepth32Float width:64 height:64 mipmapped:NO];dd.usage=MTLTextureUsageRenderTarget;dd.storageMode=MTLStorageModePrivate;dtex=[dev newTextureWithDescriptor:dd];}
  id<MTLCommandQueue> q=[dev newCommandQueue];
  MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
  rp.colorAttachments[0].texture=target;rp.colorAttachments[0].loadAction=MTLLoadActionClear;
  rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1);rp.colorAttachments[0].storeAction=MTLStoreActionStore;
  if(depth){rp.depthAttachment.texture=dtex;rp.depthAttachment.loadAction=MTLLoadActionClear;rp.depthAttachment.clearDepth=1.0;rp.depthAttachment.storeAction=MTLStoreActionStore;}
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
  [enc setRenderPipelineState:pso];
  if(depth){MTLDepthStencilDescriptor*ds=[MTLDepthStencilDescriptor new];ds.depthCompareFunction=MTLCompareFunctionLessEqual;ds.depthWriteEnabled=YES;[enc setDepthStencilState:[dev newDepthStencilStateWithDescriptor:ds]];}
  if(cull){[enc setCullMode:MTLCullModeBack];[enc setFrontFacingWinding:MTLWindingCounterClockwise];}
  if(vp){MTLViewport v={8,16,32,48,0,1};[enc setViewport:v];}
  if(idx){
    id<MTLBuffer> ib;
    if(idx32){uint32_t ix[3]={0,1,2};ib=[dev newBufferWithBytes:ix length:12 options:MTLResourceStorageModeShared];[enc drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:3 indexType:MTLIndexTypeUInt32 indexBuffer:ib indexBufferOffset:0];}
    else{uint16_t ix[3]={0,1,2};ib=[dev newBufferWithBytes:ix length:6 options:MTLResourceStorageModeShared];[enc drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:3 indexType:MTLIndexTypeUInt16 indexBuffer:ib indexBufferOffset:0];}
  } else {
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:verts];
  }
  [enc endEncoding];[cb commit];[cb waitUntilCompleted];
  printf("STATUS=%ld\n",(long)[cb status]);
  if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(400000);}
  return 0;
}}
