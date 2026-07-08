// splice.m — DESC-4: inject raw sampler/texture descriptor codes Metal's API cannot
// express (address modes 4/6/7, swizzle codes 6/7, border code 3, anisotropy>16,
// lodMax>14) by building an EXPLICIT argument buffer in our OWN shared MTLBuffer, then
// PATCHING the appended 8-byte sampler descriptor / 32-byte texture descriptor bytes
// before dispatch, and observing the sampled result (HW-PROBE). A known 4x4 gradient
// texture is sampled at coords OUTSIDE [0,1] so the address-mode edge behavior is
// visible in the readback; swizzle/border patches are read at an in/out coord.
//
// CLEAN-ROOM: OWN-SHADER + HW-PROBE. Our MSL, our resources, our raw descriptor bytes
// (a hardware register/descriptor value is non-copyrightable data). No Apple binary read.
// Build: clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o splice splice.m
//
// Usage: splice --patch <field>=<val> [--coord X] [--dump]
//   field: saddr (byte3 bits5-7) | taddr | border (byte7 bits5-6) | swizzle=<hex12>
//          | aniso (bits20-22) | lodmax (bits13-19)
//   Prints the sampler/texture descriptor before+after patch and the sampled readback.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void hexdump(const char*l,const uint8_t*p,int n){ printf("%s",l); for(int i=0;i<n;i++)printf("%02x",p[i]); printf("\n"); }

int main(int argc,char**argv){ @autoreleasepool {
  const char* patch=NULL; double coord=1.5; int doDump=0;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--patch")&&i+1<argc) patch=argv[++i];
    else if(!strcmp(argv[i],"--coord")&&i+1<argc) coord=strtod(argv[++i],0);
    else if(!strcmp(argv[i],"--dump")) doDump=1;
  }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\nPATCH %s coord=%g\n",[[dev name] UTF8String],patch?patch:"(none)",coord);
  NSError* err=nil;
  id<MTLCommandQueue> q=[dev newCommandQueue];

  // 4x4 R32Float texture with a known gradient: texel(x,y)=x + 10*y (so R distinguishes
  // which texel the address mode fetched; border returns 0/1 presets).
  MTLTextureDescriptor* td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:4 height:4 mipmapped:NO];
  td.usage=MTLTextureUsageShaderRead; td.storageMode=MTLStorageModeShared;
  id<MTLTexture> tex=[dev newTextureWithDescriptor:td];
  uint8_t pix[4*4*4];
  for(int y=0;y<4;y++)for(int x=0;x<4;x++){ int o=(y*4+x)*4; pix[o+0]=(uint8_t)(40*x+10); pix[o+1]=(uint8_t)(40*y+10); pix[o+2]=200; pix[o+3]=255; }
  [tex replaceRegion:MTLRegionMake2D(0,0,4,4) mipmapLevel:0 withBytes:pix bytesPerRow:16];

  MTLSamplerDescriptor* sd=[MTLSamplerDescriptor new];
  sd.minFilter=MTLSamplerMinMagFilterNearest; sd.magFilter=MTLSamplerMinMagFilterNearest;
  sd.sAddressMode=MTLSamplerAddressModeClampToEdge; sd.tAddressMode=MTLSamplerAddressModeClampToEdge;
  sd.normalizedCoordinates=YES; sd.supportArgumentBuffers=YES;
  id<MTLSamplerState> smp=[dev newSamplerStateWithDescriptor:sd];

  // Explicit argument buffer via MTLArgumentEncoder over a tiny function signature.
  NSString* ksrc=[NSString stringWithFormat:
    @"#include <metal_stdlib>\nusing namespace metal;\n"
     "struct Args{ texture2d<float> t [[id(0)]]; sampler s [[id(1)]]; };\n"
     "kernel void k(device Args& args [[buffer(0)]], device float4* o [[buffer(1)]],\n"
     "  uint i [[thread_position_in_grid]]){ float2 uv=float2(%g,%g); o[i]=args.t.sample(args.s,uv); }\n", coord, coord];
  id<MTLLibrary> lib=[dev newLibraryWithSource:ksrc options:nil error:&err];
  if(!lib){ printf("COMPILE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
  id<MTLFunction> fn=[lib newFunctionWithName:@"k"];
  id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:fn error:&err];
  if(!pso){ printf("PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
  id<MTLArgumentEncoder> ae=[fn newArgumentEncoderWithBufferIndex:0];
  NSUInteger alen=[ae encodedLength];
  printf("ARGBUF encodedLength=%lu\n",(unsigned long)alen);
  id<MTLBuffer> ab=[dev newBufferWithLength:alen options:MTLResourceStorageModeShared];
  [ae setArgumentBuffer:ab offset:0];
  [ae setTexture:tex atIndex:0];
  [ae setSamplerState:smp atIndex:1];

  uint8_t* base=(uint8_t*)[ab contents];
  hexdump("ARGBUF pre-patch: ", base, (int)(alen<64?alen:64));

  // The explicit arg buffer holds: texture descriptor (32B) + sampler descriptor (8B),
  // OR gpuResourceIDs. Detect by scanning for the sampler's default bytes 00 00 0e 00 80 07.
  int samp_off=-1, tex_off=-1;
  for(int i=0;i+8<=(int)alen;i++){
    if(base[i]==0x00&&base[i+1]==0x00&&base[i+2]==0x0e&&base[i+3]==0x00&&base[i+4]==0x80&&base[i+5]==0x07){ samp_off=i; break; }
  }
  // texture descriptor byte0 low nibble=2 (2D), byte1=0x0a (rgba8): look for 0x..0a??22 word
  for(int i=0;i+4<=(int)alen;i+=1){
    if((base[i]&0x0f)==0x02 && base[i+1]==0x0a){ tex_off=i; break; }
  }
  printf("DETECT samp_off=%d tex_off=%d\n",samp_off,tex_off);

  if(samp_off>=0){
    // apply patch to sampler descriptor bytes in place
    uint64_t s; memcpy(&s,base+samp_off,8);
    if(patch){
      char f[32]; unsigned long v=0; if(sscanf(patch,"%31[^=]=%li",f,(long*)&v)==2){
        if(!strcmp(f,"saddr")){ s=(s&~(0x7ULL<<29))|((uint64_t)(v&7)<<29); }
        else if(!strcmp(f,"taddr")){ s=(s&~(0x7ULL<<32))|((uint64_t)(v&7)<<32); }
        else if(!strcmp(f,"border")){ s=(s&~(0x3ULL<<61))|((uint64_t)(v&3)<<61); }
        else if(!strcmp(f,"aniso")){ s=(s&~(0x7ULL<<20))|((uint64_t)(v&7)<<20); }
        else if(!strcmp(f,"lodmax")){ s=(s&~(0x7fULL<<13))|((uint64_t)(v&0x7f)<<13); }
      }
      memcpy(base+samp_off,&s,8);
    }
    hexdump("SAMP post-patch: ", base+samp_off, 8);
  }
  if(tex_off>=0 && patch && !strncmp(patch,"swizzle=",8)){
    uint32_t w0; memcpy(&w0,base+tex_off,4);
    unsigned long sw=strtoul(patch+8,0,16);
    w0=(w0&~(0xfffU<<16))|((uint32_t)(sw&0xfff)<<16);
    memcpy(base+tex_off,&w0,4);
    hexdump("TEX post-patch w0: ", base+tex_off, 4);
  }

  id<MTLBuffer> obuf=[dev newBufferWithLength:64*16 options:MTLResourceStorageModeShared];
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
  [enc setComputePipelineState:pso];
  [enc setBuffer:ab offset:0 atIndex:0]; [enc setBuffer:obuf offset:0 atIndex:1];
  [enc useResource:tex usage:MTLResourceUsageRead];
  [enc dispatchThreads:MTLSizeMake(4,1,1) threadsPerThreadgroup:MTLSizeMake(4,1,1)];
  [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
  printf("SUBMIT status=%ld err=%s\n",(long)[cb status],[cb error]?[[[cb error] localizedDescription] UTF8String]:"none");
  float* op=(float*)[obuf contents];
  printf("SAMPLED rgba = %.3f %.3f %.3f %.3f  (R encodes 40*x+10 /255, G=40*y+10 /255)\n",op[0],op[1],op[2],op[3]);
  if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(300000); }
  return 0;
}}
