// amp.m — vertex-amplification cmdstream probe. Renders one triangle with
// setVertexAmplificationCount:N into an N-layer 2D-array RT, each amplified view
// routed to its own layer via [[render_target_array_index]]=[[amplification_id]].
// --amp 1 (baseline, count=1) vs --amp 2 isolates the amplification-count field +
// view-mapping in the VDM/PPP stream. RT is 2-layer in BOTH runs so only the
// amplification machinery differs. Clean-room: OWN MSL/API + DATA-TRACE.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <stdlib.h>
int main(int argc,char**argv){@autoreleasepool{
  long W=64,H=64; int doDump=0,amp=1;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--dump"))doDump=1;
    else if(!strcmp(argv[i],"--amp")&&i+1<argc)amp=atoi(argv[++i]);
  }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s AMP amp=%d\n",[[dev name]UTF8String],amp);
  if(![dev supportsVertexAmplificationCount:amp]){printf("AMP_UNSUPPORTED %d\n",amp);return 1;}
  NSError*err=nil;
  NSString*src=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "struct VO{float4 pos [[position]];uint layer[[render_target_array_index]];float4 col;};\n"
    "vertex VO v_main(uint vid[[vertex_id]], ushort aid[[amplification_id]]){\n"
    "  float2 p[3]={float2(-0.5,-0.5),float2(0.5,-0.5),float2(0.0,0.5)};VO o;\n"
    "  o.pos=float4(p[vid%3]+float2(aid)*0.1,0,1);o.layer=aid;o.col=float4(aid,1-aid,0,1);return o;}\n"
    "fragment float4 f_main(VO in[[stage_in]]){return in.col;}\n";
  id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
  if(!lib){printf("COMPILE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
  pd.vertexFunction=[lib newFunctionWithName:@"v_main"];pd.fragmentFunction=[lib newFunctionWithName:@"f_main"];
  pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
  pd.inputPrimitiveTopology=MTLPrimitiveTopologyClassTriangle; // required: VS writes render_target_array_index
  pd.maxVertexAmplificationCount=(amp>1?amp:1);
  id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
  if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  MTLTextureDescriptor*rt=[MTLTextureDescriptor new];
  rt.textureType=MTLTextureType2DArray;rt.pixelFormat=MTLPixelFormatBGRA8Unorm;
  rt.width=W;rt.height=H;rt.arrayLength=2;rt.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead;rt.storageMode=MTLStorageModeShared;
  id<MTLTexture> target=[dev newTextureWithDescriptor:rt];
  MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
  rp.colorAttachments[0].texture=target;rp.colorAttachments[0].loadAction=MTLLoadActionClear;
  rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1);rp.colorAttachments[0].storeAction=MTLStoreActionStore;
  rp.renderTargetArrayLength=2;
  id<MTLCommandQueue> q=[dev newCommandQueue];
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
  [enc setRenderPipelineState:pso];
  MTLVertexAmplificationViewMapping maps[2]={{0,0},{1,0}}; // renderTargetArrayIndexOffset, viewportArrayIndexOffset
  if(amp>1)[enc setVertexAmplificationCount:amp viewMappings:maps];
  else     [enc setVertexAmplificationCount:1 viewMappings:NULL];
  [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
  [enc endEncoding];[cb commit];[cb waitUntilCompleted];
  printf("STATUS=%ld\n",(long)[cb status]);
  if([cb error])printf("CB_ERROR %s\n",[[[cb error]localizedDescription]UTF8String]);
  if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(500000);}
  return 0;
}}
