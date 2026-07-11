// dvar_draw.m — parametric OWN draw for VDM record delta probing. Clean-room: own MSL/API.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
int main(int argc,char**argv){@autoreleasepool{
  const char*prim="tri"; long verts=3,inst=1; int doDump=0;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--prim")&&i+1<argc)prim=argv[++i];
    else if(!strcmp(argv[i],"--verts")&&i+1<argc)verts=atol(argv[++i]);
    else if(!strcmp(argv[i],"--inst")&&i+1<argc)inst=atol(argv[++i]);
    else if(!strcmp(argv[i],"--dump"))doDump=1;
  }
  MTLPrimitiveType pt=MTLPrimitiveTypeTriangle;
  if(!strcmp(prim,"point"))pt=MTLPrimitiveTypePoint;
  else if(!strcmp(prim,"line"))pt=MTLPrimitiveTypeLine;
  else if(!strcmp(prim,"linestrip"))pt=MTLPrimitiveTypeLineStrip;
  else if(!strcmp(prim,"tristrip"))pt=MTLPrimitiveTypeTriangleStrip;
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s prim=%s verts=%ld inst=%ld\n",[[dev name]UTF8String],prim,verts,inst);
  NSString*src=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "struct VO{float4 pos [[position]];float4 col;};\n"
    "vertex VO v_main(uint vid[[vertex_id]]){float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};VO o;o.pos=float4(p[vid%3],0,1);o.col=float4(0.25,0.5,0.75,1);return o;}\n"
    "fragment float4 f_main(VO in[[stage_in]]){return in.col;}\n";
  NSError*err=nil;
  id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
  if(!lib){printf("COMPILE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
  pd.vertexFunction=[lib newFunctionWithName:@"v_main"];pd.fragmentFunction=[lib newFunctionWithName:@"f_main"];
  pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
  id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
  if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:64 height:64 mipmapped:NO];
  td.usage=MTLTextureUsageRenderTarget;td.storageMode=MTLStorageModeShared;
  id<MTLTexture> target=[dev newTextureWithDescriptor:td];
  id<MTLCommandQueue> q=[dev newCommandQueue];
  MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
  rp.colorAttachments[0].texture=target;rp.colorAttachments[0].loadAction=MTLLoadActionClear;
  rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1);rp.colorAttachments[0].storeAction=MTLStoreActionStore;
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
  [enc setRenderPipelineState:pso];
  [enc drawPrimitives:pt vertexStart:0 vertexCount:verts instanceCount:inst];
  [enc endEncoding];[cb commit];[cb waitUntilCompleted];
  printf("STATUS=%ld\n",(long)[cb status]);
  if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(400000);}
  return 0;
}}
