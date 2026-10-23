// Exercises the real loader -> plugin -> software GPU -> headless present path.
// Build the executable as "vrcompositor" to exercise the layer's process gate.
#include <vulkan/vulkan.h>
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <thread>
#include <vector>

static void check(VkResult result, const char* operation) {
    if (result != VK_SUCCESS && result != VK_SUBOPTIMAL_KHR) {
        std::fprintf(stderr, "%s failed: %d\n", operation, result);
        std::exit(1);
    }
}
#define CHECK(call) check((call), #call)

int main() {
    VkApplicationInfo app{VK_STRUCTURE_TYPE_APPLICATION_INFO};
    app.pApplicationName = "BetterFrame XP isolated smoke test";
    app.apiVersion = VK_API_VERSION_1_2;
    const char* extensions[] = {VK_KHR_SURFACE_EXTENSION_NAME, VK_EXT_HEADLESS_SURFACE_EXTENSION_NAME};
    VkInstanceCreateInfo info{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};
    info.pApplicationInfo = &app;
    info.enabledExtensionCount = 2;
    info.ppEnabledExtensionNames = extensions;
    VkInstance instance;
    CHECK(vkCreateInstance(&info, nullptr, &instance));
    VkHeadlessSurfaceCreateInfoEXT surfaceInfo{VK_STRUCTURE_TYPE_HEADLESS_SURFACE_CREATE_INFO_EXT};
    VkSurfaceKHR surface;
    auto createSurface = reinterpret_cast<PFN_vkCreateHeadlessSurfaceEXT>(vkGetInstanceProcAddr(instance, "vkCreateHeadlessSurfaceEXT"));
    if (!createSurface) return 77;
    CHECK(createSurface(instance, &surfaceInfo, nullptr, &surface));
    uint32_t count = 0;
    CHECK(vkEnumeratePhysicalDevices(instance, &count, nullptr));
    if (!count) return 77;
    std::vector<VkPhysicalDevice> devices(count);
    CHECK(vkEnumeratePhysicalDevices(instance, &count, devices.data()));
    VkPhysicalDevice physical = devices[0];
    vkGetPhysicalDeviceQueueFamilyProperties(physical, &count, nullptr);
    std::vector<VkQueueFamilyProperties> queues(count);
    vkGetPhysicalDeviceQueueFamilyProperties(physical, &count, queues.data());
    uint32_t family = UINT32_MAX;
    for (uint32_t n = 0; n < count; ++n) {
        VkBool32 present = VK_FALSE;
        CHECK(vkGetPhysicalDeviceSurfaceSupportKHR(physical, n, surface, &present));
        if (present && (queues[n].queueFlags & VK_QUEUE_GRAPHICS_BIT)) {family=n;break;}
    }
    if (family == UINT32_MAX) return 77;
    float priority = 1;
    VkDeviceQueueCreateInfo queueInfo{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};
    queueInfo.queueFamilyIndex=family;queueInfo.queueCount=1;queueInfo.pQueuePriorities=&priority;
    const char* deviceExtensions[]={VK_KHR_SWAPCHAIN_EXTENSION_NAME};
    VkDeviceCreateInfo deviceInfo{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};
    deviceInfo.queueCreateInfoCount=1;deviceInfo.pQueueCreateInfos=&queueInfo;
    deviceInfo.enabledExtensionCount=1;deviceInfo.ppEnabledExtensionNames=deviceExtensions;
    VkDevice device;
    CHECK(vkCreateDevice(physical,&deviceInfo,nullptr,&device));
    VkQueue queue;vkGetDeviceQueue(device,family,0,&queue);
    VkSurfaceCapabilitiesKHR caps;
    CHECK(vkGetPhysicalDeviceSurfaceCapabilitiesKHR(physical,surface,&caps));
    CHECK(vkGetPhysicalDeviceSurfaceFormatsKHR(physical,surface,&count,nullptr));
    std::vector<VkSurfaceFormatKHR> formats(count);
    CHECK(vkGetPhysicalDeviceSurfaceFormatsKHR(physical,surface,&count,formats.data()));
    auto format=formats.front();
    for(auto candidate:formats) if(candidate.format==VK_FORMAT_B8G8R8A8_SRGB) format=candidate;
    VkSwapchainCreateInfoKHR swapInfo{VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR};
    swapInfo.surface=surface;swapInfo.minImageCount=std::max(2u,caps.minImageCount);
    swapInfo.imageFormat=format.format;swapInfo.imageColorSpace=format.colorSpace;
    swapInfo.imageExtent={128,64};swapInfo.imageArrayLayers=1;
    swapInfo.imageUsage=VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT|VK_IMAGE_USAGE_TRANSFER_DST_BIT;
    swapInfo.imageSharingMode=VK_SHARING_MODE_EXCLUSIVE;swapInfo.preTransform=caps.currentTransform;
    swapInfo.compositeAlpha=static_cast<VkCompositeAlphaFlagBitsKHR>(caps.supportedCompositeAlpha & -caps.supportedCompositeAlpha);
    swapInfo.presentMode=VK_PRESENT_MODE_FIFO_KHR;swapInfo.clipped=VK_TRUE;
    VkSwapchainKHR swapchain;
    CHECK(vkCreateSwapchainKHR(device,&swapInfo,nullptr,&swapchain));
    CHECK(vkGetSwapchainImagesKHR(device,swapchain,&count,nullptr));
    std::vector<VkImage> images(count);
    CHECK(vkGetSwapchainImagesKHR(device,swapchain,&count,images.data()));
    VkCommandPoolCreateInfo poolInfo{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO};
    poolInfo.queueFamilyIndex=family;poolInfo.flags=VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;
    VkCommandPool pool;CHECK(vkCreateCommandPool(device,&poolInfo,nullptr,&pool));
    VkCommandBufferAllocateInfo allocate{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};
    allocate.commandPool=pool;allocate.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY;allocate.commandBufferCount=1;
    VkCommandBuffer cb;CHECK(vkAllocateCommandBuffers(device,&allocate,&cb));
    VkSemaphoreCreateInfo semaphoreInfo{VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO};
    VkSemaphore acquired,drawn;
    CHECK(vkCreateSemaphore(device,&semaphoreInfo,nullptr,&acquired));
    CHECK(vkCreateSemaphore(device,&semaphoreInfo,nullptr,&drawn));
    auto params=[](bool enabled) {
        std::ofstream out(std::getenv("FRAMELY_BETTERFRAME_XP_PARAMS"));
        out<<"enabled = "<<enabled<<"\nstreamOnly = 0\nsharpenAmount = 1.2\nsharpness = 0.7\ncasCross = 1\ncasLuma = 1\n";
    };
    params(true);
    for (int frame=0;frame<240;++frame) {
        if(frame==80)params(false);
        if(frame==160)params(true);
        uint32_t index;
        CHECK(vkAcquireNextImageKHR(device,swapchain,UINT64_MAX,acquired,VK_NULL_HANDLE,&index));
        CHECK(vkResetCommandBuffer(cb,0));
        VkCommandBufferBeginInfo begin{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
        CHECK(vkBeginCommandBuffer(cb,&begin));
        VkImageMemoryBarrier barrier{VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER};
        barrier.srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;barrier.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;
        barrier.image=images[index];barrier.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};
        barrier.oldLayout=VK_IMAGE_LAYOUT_UNDEFINED;barrier.newLayout=VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
        barrier.dstAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;
        vkCmdPipelineBarrier(cb,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,nullptr,0,nullptr,1,&barrier);
        VkClearColorValue color{{0.2f,0.4f,0.6f,1.0f}};
        vkCmdClearColorImage(cb,images[index],VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,&color,1,&barrier.subresourceRange);
        barrier.oldLayout=VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;barrier.newLayout=VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;
        barrier.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;barrier.dstAccessMask=0;
        vkCmdPipelineBarrier(cb,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,0,0,nullptr,0,nullptr,1,&barrier);
        CHECK(vkEndCommandBuffer(cb));
        VkPipelineStageFlags stage=VK_PIPELINE_STAGE_TRANSFER_BIT;
        VkSubmitInfo submit{VK_STRUCTURE_TYPE_SUBMIT_INFO};
        submit.waitSemaphoreCount=1;submit.pWaitSemaphores=&acquired;submit.pWaitDstStageMask=&stage;
        submit.commandBufferCount=1;submit.pCommandBuffers=&cb;submit.signalSemaphoreCount=1;submit.pSignalSemaphores=&drawn;
        CHECK(vkQueueSubmit(queue,1,&submit,VK_NULL_HANDLE));
        VkPresentInfoKHR present{VK_STRUCTURE_TYPE_PRESENT_INFO_KHR};
        present.waitSemaphoreCount=1;present.pWaitSemaphores=&drawn;present.swapchainCount=1;present.pSwapchains=&swapchain;present.pImageIndices=&index;
        CHECK(vkQueuePresentKHR(queue,&present));
        CHECK(vkQueueWaitIdle(queue));
        std::this_thread::sleep_for(std::chrono::milliseconds(6));
    }
    vkDestroySemaphore(device,acquired,nullptr);vkDestroySemaphore(device,drawn,nullptr);
    vkDestroyCommandPool(device,pool,nullptr);vkDestroySwapchainKHR(device,swapchain,nullptr);
    vkDestroyDevice(device,nullptr);vkDestroySurfaceKHR(instance,surface,nullptr);vkDestroyInstance(instance,nullptr);
    std::puts("240 headless frames presented; live effect/copy/effect transitions exercised.");
}
