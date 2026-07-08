// sctest.m — MSAA sample-count capability probe (OWN Metal, public API only).
//
// Sub-task (a) of CMD-7. Answers: does Metal ACCEPT or REJECT 8x MSAA on this device?
//   1. [dev supportsTextureSampleCount:N] for N in {1,2,4,8,16,32}.
//   2. Try to create a 2DMultisample MTLTexture at sampleCount N (try/catch).
//   3. Try to build a render pipeline with rasterSampleCount=N (try/catch).
//   4. Print [dev maximumTextureSampleCount]-style facts we can query.
// CLEAN-ROOM: no Apple binary inspected. Our own MSL. Public API only.
// Build: clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o sctest sctest.m

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>

static NSString *gsrc(void){
  return @"#include <metal_stdlib>\nusing namespace metal;\n"
          "struct VO{float4 pos [[position]];float4 col;};\n"
          "vertex VO v_main(uint vid [[vertex_id]]){VO o;o.pos=float4(0,0,0,1);o.col=float4(1);return o;}\n"
          "fragment float4 f_main(VO in [[stage_in]]){return in.col;}\n";
}

int main(void){
 @autoreleasepool{
  setvbuf(stdout,NULL,_IONBF,0);   // unbuffered: partial output survives a HW/validation abort
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\n",[[dev name]UTF8String]);

  int Ns[]={1,2,4,8,16,32};
  for(int i=0;i<6;i++){
    int N=Ns[i];
    printf("supportsTextureSampleCount:%-2d = %d\n",N,(int)[dev supportsTextureSampleCount:N]);
  }

  NSError*err=nil;
  id<MTLLibrary> gl=[dev newLibraryWithSource:gsrc() options:nil error:&err];
  if(!gl){printf("LIB_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  id<MTLFunction> vf=[gl newFunctionWithName:@"v_main"];
  id<MTLFunction> ff=[gl newFunctionWithName:@"f_main"];

  int Nt[]={1,2,4,8};
  for(int i=0;i<4;i++){
    int N=Nt[i];
    // (2) texture creation (multisample textures require sampleCount > 1)
    if(N>1) @try{
      MTLTextureDescriptor*md=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:64 height:64 mipmapped:NO];
      md.textureType=MTLTextureType2DMultisample; md.sampleCount=(NSUInteger)N;
      md.usage=MTLTextureUsageRenderTarget; md.storageMode=MTLStorageModePrivate;
      id<MTLTexture> t=[dev newTextureWithDescriptor:md];
      printf("TEXTURE  sampleCount=%-2d -> %s (sc=%lu)\n",N, t?"OK":"nil", t?(unsigned long)[t sampleCount]:0);
    }@catch(NSException*e){ printf("TEXTURE  sampleCount=%-2d -> EXC %s\n",N,[[e reason]UTF8String]); }

    // (3) pipeline with rasterSampleCount=N
    @try{
      MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
      pd.vertexFunction=vf; pd.fragmentFunction=ff;
      pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
      pd.rasterSampleCount=(NSUInteger)N;
      NSError*e2=nil;
      id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&e2];
      printf("PIPELINE rasterSampleCount=%-2d -> %s%s%s\n",N,
             pso?"OK":"FAIL",
             pso?"":" err=", pso?"":[[e2 localizedDescription]UTF8String]);
    }@catch(NSException*e){ printf("PIPELINE rasterSampleCount=%-2d -> EXC %s\n",N,[[e reason]UTF8String]); }
  }
  return 0;
 }
}
