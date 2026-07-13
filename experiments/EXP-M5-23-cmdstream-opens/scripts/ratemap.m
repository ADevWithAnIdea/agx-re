// ratemap.m — rasterization-rate-map (foveated rendering) cmdstream probe.
// --rate 0 : plain draw into RT (baseline).  --rate 1 : same draw with an
// MTLRasterizationRateMap set on the render pass (center full-rate, edges 1/4-rate).
// Diffing the two captures reveals (a) the rate-map data BO layout (zone boundaries +
// rate arrays), (b) the cmdstream field that references it + the enable, (c) the
// physical (rasterized) tile-count words. Clean-room: OWN MSL/API + DATA-TRACE.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <stdlib.h>
int main(int argc,char**argv){@autoreleasepool{
  long W=256,H=256; int doDump=0,rate=0;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--dump"))doDump=1;
    else if(!strcmp(argv[i],"--rate")&&i+1<argc)rate=atoi(argv[++i]);
    else if(!strcmp(argv[i],"--w")&&i+1<argc)W=atol(argv[++i]);
    else if(!strcmp(argv[i],"--h")&&i+1<argc)H=atol(argv[++i]);
  }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s RATEMAP rate=%d W=%ld H=%ld\n",[[dev name]UTF8String],rate,W,H);
  NSError*err=nil;
  id<MTLRasterizationRateMap> rrm=nil; id<MTLBuffer> pbuf=nil;
  if(rate){
    if(![dev respondsToSelector:@selector(supportsRasterizationRateMapWithLayerCount:)] ||
       ![dev supportsRasterizationRateMapWithLayerCount:1]){printf("RRM_UNSUPPORTED\n");return 1;}
    MTLRasterizationRateMapDescriptor*rmd=[MTLRasterizationRateMapDescriptor rasterizationRateMapDescriptorWithScreenSize:MTLSizeMake(W,H,0)];
    NSUInteger nx=8,ny=8;
    MTLRasterizationRateLayerDescriptor*layer=[[MTLRasterizationRateLayerDescriptor alloc] initWithSampleCount:MTLSizeMake(nx,ny,0)];
    for(NSUInteger i=0;i<nx;i++) layer.horizontalSampleStorage[i]=(i>=nx/4 && i<3*nx/4)?1.0f:0.25f;
    for(NSUInteger i=0;i<ny;i++) layer.verticalSampleStorage[i]=(i>=ny/4 && i<3*ny/4)?1.0f:0.25f;
    rmd.layers[0]=layer;
    rrm=[dev newRasterizationRateMapWithDescriptor:rmd];
    if(!rrm){printf("RRM_CREATE_FAIL\n");return 1;}
    MTLSize phys=[rrm physicalSizeForLayer:0];
    MTLSizeAndAlign sa=[rrm parameterBufferSizeAndAlign];
    pbuf=[dev newBufferWithLength:sa.size options:MTLResourceStorageModeShared];
    [rrm copyParameterDataToBuffer:pbuf offset:0];
    printf("RRM physical=%lux%lu paramSize=0x%lx paramAlign=0x%lx paramVA=0x%llx\n",
      (unsigned long)phys.width,(unsigned long)phys.height,(unsigned long)sa.size,(unsigned long)sa.align,
      (unsigned long long)[pbuf gpuAddress]);
  }
  NSString*src=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "struct VO{float4 pos [[position]];float2 uv;};\n"
    "vertex VO v_main(uint vid[[vertex_id]]){float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};VO o;o.pos=float4(p[vid%3],0,1);o.uv=p[vid%3];return o;}\n"
    "fragment float4 f_main(VO in[[stage_in]]){return float4(in.uv*0.5+0.5,0,1);}\n";
  id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
  if(!lib){printf("COMPILE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
  pd.vertexFunction=[lib newFunctionWithName:@"v_main"];pd.fragmentFunction=[lib newFunctionWithName:@"f_main"];
  pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
  id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
  if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  MTLTextureDescriptor*rt=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:W height:H mipmapped:NO];
  rt.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead; rt.storageMode=MTLStorageModeShared;
  id<MTLTexture> target=[dev newTextureWithDescriptor:rt];
  MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
  rp.colorAttachments[0].texture=target;rp.colorAttachments[0].loadAction=MTLLoadActionClear;
  rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1);rp.colorAttachments[0].storeAction=MTLStoreActionStore;
  if(rate) rp.rasterizationRateMap=rrm;
  id<MTLCommandQueue> q=[dev newCommandQueue];
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
  [enc setRenderPipelineState:pso];
  [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
  [enc endEncoding];[cb commit];[cb waitUntilCompleted];
  printf("STATUS=%ld\n",(long)[cb status]);
  if([cb error])printf("CB_ERROR %s\n",[[[cb error]localizedDescription]UTF8String]);
  if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(500000);}
  return 0;
}}
