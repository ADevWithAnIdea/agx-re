// ppp.m — PPP vertex-output-select probe. Compiles OWN vertex shaders emitting each
// per-vertex system output ([[point_size]], [[viewport_array_index]],
// [[render_target_array_index]], [[clip_distance]]) and dumps the command-stream BOs so
// the FF-pool output-select word can be decoded by change-one-output diffing.
// Clean-room: our own MSL + public Metal API; dumps our own BOs via SIGUSR1.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <stdlib.h>

int main(int argc,char**argv){@autoreleasepool{
  const char*mode="base"; int doDump=0; int nclip=1;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--dump"))doDump=1;
    else if(!strcmp(argv[i],"--mode")&&i+1<argc)mode=argv[++i];
    else if(!strcmp(argv[i],"--nclip")&&i+1<argc)nclip=atoi(argv[++i]);
  }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s mode=%s nclip=%d\n",[[dev name]UTF8String],mode,nclip);
  id<MTLCommandQueue> q=[dev newCommandQueue];
  NSError*err=nil;

  int isPoint = !strcmp(mode,"psize");
  int isLayer = !strcmp(mode,"rtidx");
  int isVp    = !strcmp(mode,"vpidx");
  int isClip  = !strcmp(mode,"clip");

  // Build the VS output struct + body per mode.
  NSMutableString*vo=[NSMutableString stringWithString:@"struct VO{float4 pos [[position]];"];
  NSMutableString*asn=[NSMutableString string];
  if(isPoint){ [vo appendString:@"float psz [[point_size]];"]; [asn appendString:@"o.psz=4.0;"]; }
  if(isVp){    [vo appendString:@"uint vpi [[viewport_array_index]];"]; [asn appendString:@"o.vpi=vid&1u;"]; }
  if(isLayer){ [vo appendString:@"uint rti [[render_target_array_index]];"]; [asn appendString:@"o.rti=vid&1u;"]; }
  if(isClip){  [vo appendFormat:@"float cd [[clip_distance]] [%d];",nclip];
               for(int i=0;i<nclip;i++)[asn appendFormat:@"o.cd[%d]=0.5;",i]; }
  [vo appendString:@"};\n"];

  NSMutableString*src=[NSMutableString stringWithString:@"#include <metal_stdlib>\nusing namespace metal;\n"];
  [src appendString:vo];
  [src appendFormat:@"vertex VO v_main(uint vid[[vertex_id]]){float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};VO o;o.pos=float4(p[vid%%3],0,1);%s return o;}\n",[asn UTF8String]];
  // FS takes only [[position]] so the per-vertex system outputs (clip/psize/vpidx/layer),
  // which are not FS-consumed varyings, don't need to appear in stage_in.
  [src appendString:@"fragment float4 f_main(float4 pos[[position]]){return float4(0.3,0.6,0.9,1);}\n"];

  id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
  if(!lib){printf("COMPILE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
  pd.vertexFunction=[lib newFunctionWithName:@"v_main"];pd.fragmentFunction=[lib newFunctionWithName:@"f_main"];
  pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
  // render_target_array_index requires the pipeline to declare a primitive topology class.
  if(isLayer) pd.inputPrimitiveTopology=MTLPrimitiveTopologyClassTriangle;
  id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
  if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}

  // Render target: array (2 layers) when probing layer output, else plain 2D.
  MTLTextureDescriptor*td;
  if(isLayer){
    td=[MTLTextureDescriptor new];
    td.textureType=MTLTextureType2DArray;td.pixelFormat=MTLPixelFormatBGRA8Unorm;
    td.width=64;td.height=64;td.arrayLength=2;
  } else {
    td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:64 height:64 mipmapped:NO];
  }
  td.usage=MTLTextureUsageRenderTarget;td.storageMode=MTLStorageModeShared;
  id<MTLTexture> target=[dev newTextureWithDescriptor:td];

  MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
  rp.colorAttachments[0].texture=target;rp.colorAttachments[0].loadAction=MTLLoadActionClear;
  rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1);rp.colorAttachments[0].storeAction=MTLStoreActionStore;
  if(isLayer) rp.renderTargetArrayLength=2;

  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
  [enc setRenderPipelineState:pso];
  if(isVp){
    MTLViewport vs[2]={{0,0,32,64,0,1},{32,0,32,64,0,1}};
    [enc setViewports:vs count:2];
  }
  MTLPrimitiveType prim = isPoint?MTLPrimitiveTypePoint:MTLPrimitiveTypeTriangle;
  [enc drawPrimitives:prim vertexStart:0 vertexCount:3];
  [enc endEncoding];[cb commit];[cb waitUntilCompleted];
  printf("STATUS=%ld\n",(long)[cb status]);
  if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(400000);}
  return 0;
}}
