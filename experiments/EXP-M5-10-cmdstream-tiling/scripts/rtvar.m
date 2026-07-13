// rtvar.m — parametric OWN render pass: attachment format, MRT, MSAA, sample positions,
// memoryless, load/store actions, occlusion query. Clean-room: own MSL/API. Dumps own BOs.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <stdlib.h>
static MTLPixelFormat pf(const char*s){
  if(!strcmp(s,"bgra8"))return MTLPixelFormatBGRA8Unorm;
  if(!strcmp(s,"rgba8"))return MTLPixelFormatRGBA8Unorm;
  if(!strcmp(s,"rgba8i"))return MTLPixelFormatRGBA8Sint;
  if(!strcmp(s,"rgba16f"))return MTLPixelFormatRGBA16Float;
  if(!strcmp(s,"rgba32f"))return MTLPixelFormatRGBA32Float;
  if(!strcmp(s,"r8"))return MTLPixelFormatR8Unorm;
  if(!strcmp(s,"rg8"))return MTLPixelFormatRG8Unorm;
  if(!strcmp(s,"r32f"))return MTLPixelFormatR32Float;
  if(!strcmp(s,"r32u"))return MTLPixelFormatR32Uint;
  if(!strcmp(s,"r16u"))return MTLPixelFormatR16Uint;
  if(!strcmp(s,"rgb10a2"))return MTLPixelFormatRGB10A2Unorm;
  if(!strcmp(s,"rg11b10"))return MTLPixelFormatRG11B10Float;
  if(!strcmp(s,"rg16f"))return MTLPixelFormatRG16Float;
  return MTLPixelFormatBGRA8Unorm;
}
int main(int argc,char**argv){@autoreleasepool{
  const char*fmt="bgra8"; int mrt=1,msaa=1,memless=0,load=2,store=1,samplepos=0,occl=-1,W=64,H=64,doDump=0;long occloff=0;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--dump"))doDump=1;
    else if(!strcmp(argv[i],"--fmt")&&i+1<argc)fmt=argv[++i];
    else if(!strcmp(argv[i],"--mrt")&&i+1<argc)mrt=atoi(argv[++i]);
    else if(!strcmp(argv[i],"--msaa")&&i+1<argc)msaa=atoi(argv[++i]);
    else if(!strcmp(argv[i],"--memoryless"))memless=1;
    else if(!strcmp(argv[i],"--load")&&i+1<argc)load=atoi(argv[++i]);
    else if(!strcmp(argv[i],"--store")&&i+1<argc)store=atoi(argv[++i]);
    else if(!strcmp(argv[i],"--samplepos"))samplepos=1;
    else if(!strcmp(argv[i],"--occl")&&i+1<argc)occl=atoi(argv[++i]);
    else if(!strcmp(argv[i],"--occloff")&&i+1<argc)occloff=atol(argv[++i]);
    else if(!strcmp(argv[i],"--w")&&i+1<argc)W=atoi(argv[++i]);
    else if(!strcmp(argv[i],"--h")&&i+1<argc)H=atoi(argv[++i]);
  }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s fmt=%s mrt=%d msaa=%d memless=%d load=%d store=%d spos=%d occl=%d\n",
    [[dev name]UTF8String],fmt,mrt,msaa,memless,load,store,samplepos,occl);
  // FS writes to all mrt outputs
  NSMutableString*fs=[NSMutableString stringWithString:@"#include <metal_stdlib>\nusing namespace metal;\n"
    "struct VO{float4 pos [[position]];};\n"
    "vertex VO v_main(uint vid[[vertex_id]]){float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};VO o;o.pos=float4(p[vid%3],0.5,1);return o;}\n"
    "struct FO{"];
  for(int k=0;k<mrt;k++)[fs appendFormat:@"float4 c%d [[color(%d)]];",k,k];
  [fs appendString:@"};\nfragment FO f_main(VO in[[stage_in]]){FO o;"];
  for(int k=0;k<mrt;k++)[fs appendFormat:@"o.c%d=float4(0.25,0.5,0.75,1);",k];
  [fs appendString:@"return o;}\n"];
  NSError*err=nil;
  id<MTLLibrary> lib=[dev newLibraryWithSource:fs options:nil error:&err];
  if(!lib){printf("COMPILE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
  pd.vertexFunction=[lib newFunctionWithName:@"v_main"];pd.fragmentFunction=[lib newFunctionWithName:@"f_main"];
  for(int k=0;k<mrt;k++)pd.colorAttachments[k].pixelFormat=pf(fmt);
  if(msaa>1){pd.rasterSampleCount=msaa;}
  id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
  if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
  id<MTLTexture> resolveTex[8]={0};
  for(int k=0;k<mrt;k++){
    MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:pf(fmt) width:W height:H mipmapped:NO];
    td.usage=MTLTextureUsageRenderTarget;
    if(msaa>1){td.textureType=MTLTextureType2DMultisample;td.sampleCount=msaa;}
    td.storageMode=memless?MTLStorageModeMemoryless:(msaa>1?MTLStorageModePrivate:MTLStorageModeShared);
    id<MTLTexture> t=[dev newTextureWithDescriptor:td];
    rp.colorAttachments[k].texture=t;
    rp.colorAttachments[k].loadAction=(MTLLoadAction)load;
    rp.colorAttachments[k].clearColor=MTLClearColorMake(0.1,0.2,0.3,1);
    rp.colorAttachments[k].storeAction=(MTLStoreAction)store;
    if(store==2){ // multisampleResolve needs a resolve target
      MTLTextureDescriptor*rd=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:pf(fmt) width:W height:H mipmapped:NO];
      rd.usage=MTLTextureUsageRenderTarget;rd.storageMode=MTLStorageModeShared;
      resolveTex[k]=[dev newTextureWithDescriptor:rd];
      rp.colorAttachments[k].resolveTexture=resolveTex[k];
    }
  }
  if(samplepos && msaa>1){
    MTLSamplePosition sp[4]={{0.1,0.2},{0.3,0.7},{0.6,0.4},{0.9,0.8}};
    [rp setSamplePositions:sp count:msaa];
  }
  id<MTLBuffer> vis=nil;
  if(occl>=0){ vis=[dev newBufferWithLength:4096 options:MTLResourceStorageModeShared]; rp.visibilityResultBuffer=vis; }
  id<MTLCommandQueue> q=[dev newCommandQueue];
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
  [enc setRenderPipelineState:pso];
  if(occl>=0)[enc setVisibilityResultMode:(occl?MTLVisibilityResultModeCounting:MTLVisibilityResultModeBoolean) offset:occloff];
  [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
  if(occl>=0)[enc setVisibilityResultMode:MTLVisibilityResultModeDisabled offset:0];
  [enc endEncoding];[cb commit];[cb waitUntilCompleted];
  printf("STATUS=%ld\n",(long)[cb status]);
  if(occl>=0){uint64_t*p=(uint64_t*)[vis contents];printf("OCCL result[off=%ld]=%llu\n",occloff,p[occloff/8]);}
  if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(400000);}
  return 0;
}}
