// probe.m — quick API/capability probe for O2-B (sparse / PBE / float-filter / sampler-heap).
// CLEAN-ROOM: OWN-SHADER + public Metal API + HW-PROBE. No Apple binary introspected.
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o probe probe.m
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>

int main(void){ @autoreleasepool {
  id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\n",[[dev name] UTF8String]);
  printf("CAP sparseTileSizeInBytes = %lu\n",(unsigned long)[dev sparseTileSizeInBytes]);
  printf("CAP maxArgumentBufferSamplerCount = %lu\n",(unsigned long)[dev maxArgumentBufferSamplerCount]);
  printf("CAP supports32BitFloatFiltering = %d\n",(int)[dev supports32BitFloatFiltering]);
  printf("CAP argumentBuffersSupport = %ld (2=Tier2)\n",(long)[dev argumentBuffersSupport]);

  // sparse tile size for a few formats/types
  MTLPixelFormat pfs[] = {MTLPixelFormatRGBA8Unorm, MTLPixelFormatR32Float, MTLPixelFormatRGBA32Float, MTLPixelFormatR8Unorm};
  const char* pfn[] = {"rgba8unorm","r32float","rgba32float","r8unorm"};
  for(int i=0;i<4;i++){
    MTLSize t=[dev sparseTileSizeWithTextureType:MTLTextureType2D pixelFormat:pfs[i] sampleCount:1];
    printf("SPARSE_TILE %s 2D = %lux%lux%lu\n",pfn[i],(unsigned long)t.width,(unsigned long)t.height,(unsigned long)t.depth);
  }

  // --- sparse heap ---
  MTLHeapDescriptor* hd=[MTLHeapDescriptor new];
  hd.type = MTLHeapTypeSparse;
  hd.storageMode = MTLStorageModePrivate;
  hd.size = 64*1024*1024;
  id<MTLHeap> sheap=[dev newHeapWithDescriptor:hd];
  printf("SPARSE_HEAP %s size=%lu type=%ld\n", sheap?"ok":"FAIL",(unsigned long)[sheap size],(long)[sheap type]);
  if(sheap){
    MTLTextureDescriptor* td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:256 height:256 mipmapped:NO];
    td.storageMode=MTLStorageModePrivate; td.usage=MTLTextureUsageShaderRead;
    id<MTLTexture> stex=[sheap newTextureWithDescriptor:td];
    printf("SPARSE_TEX %s\n", stex?"ok":"FAIL");
  }

  // --- placement heap ---
  MTLHeapDescriptor* pd=[MTLHeapDescriptor new];
  pd.type = MTLHeapTypePlacement;
  pd.storageMode = MTLStorageModePrivate;
  pd.size = 16*1024*1024;
  id<MTLHeap> pheap=[dev newHeapWithDescriptor:pd];
  printf("PLACEMENT_HEAP %s size=%lu type=%ld\n", pheap?"ok":"FAIL",(unsigned long)[pheap size],(long)[pheap type]);
  if(pheap){
    MTLTextureDescriptor* td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:64 height:64 mipmapped:NO];
    td.storageMode=MTLStorageModePrivate; td.usage=MTLTextureUsageShaderRead;
    MTLSizeAndAlign sa=[dev heapTextureSizeAndAlignWithDescriptor:td];
    printf("PLACEMENT sizeAndAlign size=%lu align=%lu\n",(unsigned long)sa.size,(unsigned long)sa.align);
    id<MTLTexture> ptex=[pheap newTextureWithDescriptor:td offset:0];
    printf("PLACEMENT_TEX %s\n", ptex?"ok":"FAIL");
  }

  // --- automatic heap (comparison) ---
  MTLHeapDescriptor* ad=[MTLHeapDescriptor new];
  ad.type = MTLHeapTypeAutomatic; ad.storageMode = MTLStorageModePrivate; ad.size = 16*1024*1024;
  id<MTLHeap> aheap=[dev newHeapWithDescriptor:ad];
  printf("AUTO_HEAP %s type=%ld\n", aheap?"ok":"FAIL",(long)[aheap type]);

  return 0;
}}
