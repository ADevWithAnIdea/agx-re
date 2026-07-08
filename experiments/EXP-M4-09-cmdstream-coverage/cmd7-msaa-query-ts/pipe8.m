#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
int main(void){@autoreleasepool{
  setvbuf(stdout,NULL,_IONBF,0);
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\n",[[dev name]UTF8String]);
  NSError*err=nil;
  id<MTLLibrary> gl=[dev newLibraryWithSource:@"#include <metal_stdlib>\nusing namespace metal;\nstruct VO{float4 pos [[position]];};\nvertex VO v_main(){VO o;o.pos=float4(0,0,0,1);return o;}\nfragment float4 f_main(){return float4(1);}\n" options:nil error:&err];
  MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
  pd.vertexFunction=[gl newFunctionWithName:@"v_main"];
  pd.fragmentFunction=[gl newFunctionWithName:@"f_main"];
  pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
  pd.rasterSampleCount=8;
  @try{
    NSError*e2=nil;
    id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&e2];
    printf("PIPELINE rasterSampleCount=8 -> %s err=%s\n", pso?"OK":"FAIL(nil)", e2?[[e2 localizedDescription]UTF8String]:"(none)");
  }@catch(NSException*e){ printf("PIPELINE rasterSampleCount=8 -> EXC %s\n",[[e reason]UTF8String]); }
  return 0;
}}
