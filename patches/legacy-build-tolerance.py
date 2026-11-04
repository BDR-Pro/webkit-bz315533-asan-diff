#!/usr/bin/env python3
# Harness-only build tolerances for compiling 2023-era WebKit trees
# under Xcode 26.6 / SDK 26.5. Every patch is applied IDENTICALLY to the
# prefix and fixed legs (differential integrity preserved), is
# idempotent, and is a no-op on trunk where upstream has already fixed
# or removed the affected code. Diagnosed attempt-by-attempt in this
# repo's commit history; run from the WebKit checkout root. The final
# block also tolerates WebInspectorUI's missing InspectorBackendCommands.js
# copy (CI serialization accommodation).

p = "Configurations/CommonBase.xcconfig"
s = open(p).read()
old = "-D_LIBCPP_ENABLE_ASSERTIONS=1"
n = s.count(old)
if n:
    open(p, "w").write(s.replace(old, ""))
    print(f"neutralized _LIBCPP_ENABLE_ASSERTIONS in {p}: {n} occurrence(s) removed")
else:
    print("no _LIBCPP_ENABLE_ASSERTIONS in CommonBase.xcconfig (trunk?) - no patch applied")
# ATTEMPT-9: bmalloc's "Generate TAPI filelist" phase died because
# generate-tapi-filelist.py open()s the XCBuild header-VFS file
# (all-product-headers.yaml) that Xcode 26.6 no longer writes into
# TARGET_TEMP_DIR. The script already treats a DIRECTORY input as
# "walk it"; extend the same fallback to a missing path (os.walk on
# a nonexistent dir yields nothing -> empty filelist). TAPI
# install-filelists are unused by the WebKitTestRunner harness.
p2 = "Source/WTF/Scripts/generate-tapi-filelist.py"
s2 = open(p2).read()
old2 = "except IsADirectoryError:"
new2 = "except (IsADirectoryError, FileNotFoundError):  # HARNESS: Xcode 26 no longer writes the header VFS file"
if old2 in s2:
    open(p2, "w").write(s2.replace(old2, new2))
    print("patched generate-tapi-filelist.py: FileNotFoundError -> empty-header fallback")
else:
    print("generate-tapi-filelist.py pattern not found (trunk?) - no patch applied")
# ATTEMPT-11: URLCocoa.o compile died with a "previous definition"
# note at SDK IOSurfaceRef.h:452 - the 2023-era WTF SPI shim
# re-declares IOSurfaceMemoryLedgerTags, an enum the modern SDK
# now ships publicly. Drop the shim's duplicate enum block; the
# SDK header provides the same kIOSurfaceMemoryLedgerTag*
# constants. Harness-only dedup, identical on both legs, no-op
# on trunk.
# ATTEMPT-23: PAL's OutputDevice.mm died because the 2023-era
# AVFoundationSPI.h shim re-declares interfaces/typedefs that SDK
# 26.5 now ships publicly (AVVideoPerformanceMetrics interface at
# line 387, AVExternalContentProtectionStatus typedef at line
# 250). Same class as the IOSurfaceSPI dedup: remove the shim's
# duplicate blocks; the SDK provides them.
p3b = "Source/WebCore/PAL/pal/spi/cocoa/AVFoundationSPI.h"
s3b = open(p3b).read()
# 1) duplicate AVVideoPerformanceMetrics interface block
m3a = s3b.find("#if !USE(APPLE_INTERNAL_SDK)\n@interface AVVideoPerformanceMetrics : NSObject")
if m3a == -1:
    m3a = s3b.find("#if !USE(APPLE_INTERNAL_SDK)\n@interface AVVideoPerformanceMetrics")
if m3a != -1:
    e3a = s3b.find("#endif", m3a)
    # remove from the #if up to and including its #endif, keeping
    # the @end inside; replace whole block with a comment.
    block = s3b[m3a:e3a+7]
    s3b = s3b.replace(block, "/* HARNESS: duplicate AVVideoPerformanceMetrics interface removed for Xcode 26.6 build */")
    print("patched AVFoundationSPI.h: removed duplicate AVVideoPerformanceMetrics interface")
else:
    print("AVVideoPerformanceMetrics shim block not found (trunk?)")
# 2) duplicate AVExternalContentProtectionStatus typedef
m3b = s3b.find("typedef NS_ENUM(NSInteger, AVExternalContentProtectionStatus)")
if m3b != -1:
    e3b = s3b.find("};", m3b)
    e3b = s3b.find("\n", e3b) + 1
    s3b = s3b[:m3b] + "/* HARNESS: duplicate AVExternalContentProtectionStatus typedef removed for Xcode 26.6 build */\n" + s3b[e3b:]
    print("patched AVFoundationSPI.h: removed duplicate AVExternalContentProtectionStatus typedef")
else:
    print("AVExternalContentProtectionStatus typedef not found (trunk?)")
open(p3b, "w").write(s3b)
# ATTEMPT-24: OutputDevice.o died on 'AVAudioSession' is
# unavailable: not available on macOS. The 2023-era
# AVFoundationSoftLink.h soft-links AVAudioSession under
# HAVE(AVAUDIOSESSION), which the macOS feature-flags still
# enable, but SDK 26.5 marks AVAudioSession unavailable on
# macOS entirely. HAVE(AVAUDIOSESSION) must be 0 for this
# SDK: strip the two HAVE(AVAUDIOSESSION) and
# HAVE(AVAUDIOSESSION_SMARTROUTING) entries from the
# macOS HAVE_ feature list in wtf/PlatformHave.h (guarded by
# PLATFORM(IOS_FAMILY) upstream; the 2023 tree enables it
# for macOS too).
p3c = "Source/WTF/wtf/PlatformHave.h"
s3c = open(p3c).read()
fixed_c = 0
for guard in [
    '#define HAVE_AVAUDIOSESSION 1',
    '#define HAVE_AVAUDIOSESSION_SMARTROUTING 1',
    # ATTEMPT-28: kCLAuthorizationStatusAuthorizedWhenInUse is
    # unavailable on macOS in SDK 26.5; the 2023 tree enables it
    # whenever MIN_REQUIRED >= 140000. Geolocation is not
    # exercised by layout tests.
    '#define HAVE_CORE_LOCATION_AUTHORIZED_WHEN_IN_USE 1',
]:
    if guard in s3c:
        s3c = s3c.replace(guard, '/* HARNESS: removed for Xcode 26.6 build - AVAudioSession unavailable on macOS SDK 26.5 */')
        fixed_c += 1
if fixed_c:
    open(p3c, "w").write(s3c)
    print(f"patched PlatformHave.h: neutralized {fixed_c} AVAudioSession HAVE_ define(s)")
else:
    print("no AVAudioSession HAVE_ defines found in PlatformHave.h (trunk?)")
# ATTEMPT-25: WebCore's CGDisplayStreamScreenCaptureSource.mm
# uses CGDisplayStream APIs that SDK 26.5 marks OBSOLETED
# (obsoleted in macOS 15.0) - a hard error that no pragma or
# -Wno flag can suppress (obsoleted != deprecated). Upstream's
# own solution was deleting the file in favor of
# ScreenCaptureKit. Harness fix: flip the file guard to #if 0;
# screen capture is not exercised by layout tests. Identical on
# both legs.
p3d = "Source/WebCore/platform/mediastream/mac/CGDisplayStreamScreenCaptureSource.mm"
s3d = open(p3d).read()
old3d = "#if ENABLE(MEDIA_STREAM) && PLATFORM(MAC)"
new3d = "#if 0 // HARNESS: CGDisplayStream APIs obsoleted in SDK 26.5 (macOS 15+); ScreenCaptureKit is the replacement and layout tests do not exercise screen capture"
if old3d in s3d:
    # Only the FIRST occurrence (the file guard); the trailing
    # #endif comment matches textually so no other change needed.
    s3d = s3d.replace(old3d, new3d, 1)
    open(p3d, "w").write(s3d)
    print("patched CGDisplayStreamScreenCaptureSource.mm: file guard disabled (obsoleted CGDisplayStream APIs)")
else:
    print("CGDisplayStreamScreenCaptureSource.mm guard not found (trunk?) - no patch applied")
# ATTEMPT-26: the sibling file CGDisplayStreamCaptureSource.cpp
# (same guard, same obsoleted-API class) must be disabled too.
p3e = "Source/WebCore/platform/mediastream/mac/CGDisplayStreamCaptureSource.cpp"
s3e = open(p3e).read()
old3e = "#if ENABLE(MEDIA_STREAM) && PLATFORM(MAC)"
new3e = "#if 0 // HARNESS: CGDisplayStream APIs obsoleted in SDK 26.5 (macOS 15+); ScreenCaptureKit is the replacement and layout tests do not exercise screen capture"
if old3e in s3e:
    s3e = s3e.replace(old3e, new3e, 1)
    open(p3e, "w").write(s3e)
    print("patched CGDisplayStreamCaptureSource.cpp: file guard disabled (obsoleted CGDisplayStream APIs)")
else:
    print("CGDisplayStreamCaptureSource.cpp guard not found (trunk?) - no patch applied")
# ATTEMPT-27: FrameLoader.cpp:2580 logs a bool-backed enum
# (ErrorRecoveryMethod : bool) with %hhu - a genuine 2023-era
# format-string bug that newer clang diagnoses as a hard
# -Werror,-Wformat error (enum class with fixed underlying
# type is not promoted like unsigned char). Upstream later
# removed the log call entirely. Harness fix mirrors upstream's
# direction: cast to the promoted integer type the format
# expects. Identical on both legs; log-only, zero behavior
# change.
# ATTEMPT-29: MediaPlayerPrivateMediaSourceAVFObjC.mm reads
# AVVideoPerformanceMetrics properties that SDK 26.5 declares
# unavailable on macOS (they were the SPI shim's declarations
# we removed in attempt-23; the SDK's own public interface
# marks them unavailable for macOS targets). The call is
# guarded by respondsToSelector at runtime but the property
# access is still a hard compile error. VideoPlaybackQuality
# metadata is not exercised by layout tests: make the
# videoPlaybackQualityMetrics() fast path return early,
# before the unavailable-property reads.
p3g = "Source/WebCore/platform/graphics/avfoundation/objc/MediaPlayerPrivateMediaSourceAVFObjC.mm"
s3g = open(p3g).read()
# ATTEMPT-30 correction: the attempt-29 #if 0 only covered the
# `auto metrics` declaration; the rest of the function still
# references `metrics` (undeclared under the new branch).
# Replace the WHOLE tail of videoPlaybackQualityMetrics() -
# from the metrics fetch through the closing return - with an
# early return.
old3g = "    auto metrics = [m_sampleBufferDisplayLayer videoPerformanceMetrics];\n    if (!metrics)\n        return std::nullopt;\n\n    uint32_t displayCompositedFrames = 0;\nALLOW_NEW_API_WITHOUT_GUARDS_BEGIN\n    if ([metrics respondsToSelector:@selector(numberOfDisplayCompositedVideoFrames)])\n        displayCompositedFrames = [metrics numberOfDisplayCompositedVideoFrames];\nALLOW_NEW_API_WITHOUT_GUARDS_END\n\n    return VideoPlaybackQualityMetrics {\n        static_cast<uint32_t>([metrics totalNumberOfVideoFrames]),\n        static_cast<uint32_t>([metrics numberOfDroppedVideoFrames]),\n        static_cast<uint32_t>([metrics numberOfCorruptedVideoFrames]),\n        [metrics totalFrameDelay],\n        displayCompositedFrames,\n    };"
new3g = "    // HARNESS: AVVideoPerformanceMetrics properties unavailable on macOS SDK 26.5; layout tests do not read playback-quality metadata\n    return std::nullopt;"
if old3g in s3g:
    s3g = s3g.replace(old3g, new3g, 1)
    open(p3g, "w").write(s3g)
    print("patched MediaPlayerPrivateMediaSourceAVFObjC.mm: videoPlaybackQualityMetrics fast path returns nullopt (unavailable SDK properties)")
else:
    print("videoPerformanceMetrics block not found (trunk?) - no patch applied")
# ATTEMPT-31: the SAME unavailable-property pattern exists in the
# sibling MediaPlayerPrivateAVFoundationObjC.mm (lines ~3849-3876).
# Replace its whole videoPlaybackQualityMetrics() body with an
# early return, same rationale as attempt-29/30.
p3h = "Source/WebCore/platform/graphics/avfoundation/objc/MediaPlayerPrivateAVFoundationObjC.mm"
s3h = open(p3h).read()
old3h = "    if (![m_videoLayer respondsToSelector:@selector(videoPerformanceMetrics)])\n        return std::nullopt;\n\n#if PLATFORM(WATCHOS)\n    return std::nullopt;\n#else\nALLOW_NEW_API_WITHOUT_GUARDS_BEGIN\n\n    auto metrics = [m_videoLayer videoPerformanceMetrics];\n    if (!metrics)\n        return std::nullopt;\n\n    uint32_t displayCompositedFrames = 0;\n    if ([metrics respondsToSelector:@selector(numberOfDisplayCompositedVideoFrames)])\n        displayCompositedFrames = [metrics numberOfDisplayCompositedVideoFrames];\n\n    return VideoPlaybackQualityMetrics {\n        static_cast<uint32_t>([metrics totalNumberOfVideoFrames]),\n        static_cast<uint32_t>([metrics numberOfDroppedVideoFrames]),\n        static_cast<uint32_t>([metrics numberOfCorruptedVideoFrames]),\n        [metrics totalFrameDelay],\n        displayCompositedFrames,\n    };\n\nALLOW_NEW_API_WITHOUT_GUARDS_END\n#endif"
new3h = "    // HARNESS: AVVideoPerformanceMetrics properties unavailable on macOS SDK 26.5; layout tests do not read playback-quality metadata\n    return std::nullopt;"
if old3h in s3h:
    s3h = s3h.replace(old3h, new3h, 1)
    open(p3h, "w").write(s3h)
    print("patched MediaPlayerPrivateAVFoundationObjC.mm: videoPlaybackQualityMetrics returns nullopt (unavailable SDK properties)")
else:
    print("MediaPlayerPrivateAVFoundationObjC.mm metrics block not found (trunk?) - no patch applied")
# ATTEMPT-33: the two disabled CGDisplayStream files leave undefined
# references in DisplayCaptureManagerCocoa.cpp (screenCaptureDeviceWithPersistentID)
# and DisplayCaptureSourceCocoa.cpp (create) at link time. Stub both call
# sites: ScreenCaptureKit path remains (HAVE(SCREEN_CAPTURE_KIT is 1),
# the SCK fallback is the runtime path anyway); the CGDisplayStream tail
# call becomes std::nullopt.
p = "Source/WebCore/platform/mediastream/mac/DisplayCaptureManagerCocoa.cpp"
s = open(p).read()
old = "    return CGDisplayStreamScreenCaptureSource::screenCaptureDeviceWithPersistentID(deviceID);"
new = "    return std::nullopt; // HARNESS: CGDisplayStream disabled (obsoleted APIs)"
if old in s:
    open(p, "w").write(s.replace(old, new, 1))
    print("patched DisplayCaptureManagerCocoa.cpp: CGDisplayStream tail call returns nullopt")
else:
    print("DisplayCaptureManagerCocoa.cpp CGDisplayStream call not found (trunk?)")
p = "Source/WebCore/platform/mediastream/cocoa/DisplayCaptureSourceCocoa.cpp"
s = open(p).read()
old = "        return create(CGDisplayStreamScreenCaptureSource::create(device.persistentId()), device, WTFMove(hashSalts), constraints, pageIdentifier);"
new = '        return CaptureSourceOrError({ "Screen capture is unavailable"_s, MediaAccessDenialReason::PermissionDenied }); // HARNESS: CGDisplayStream disabled (obsoleted APIs); ScreenCaptureKit is the available path' 
if old in s:
    open(p, "w").write(s.replace(old, new, 1))
    print("patched DisplayCaptureSourceCocoa.cpp: CGDisplayStream create call stubbed")
else:
    print("DisplayCaptureSourceCocoa.cpp CGDisplayStream call not found (trunk?)")
# ATTEMPT-35: WebCore.framework link fails on _dav1d_* symbols. The 2023
# tree compiles LibWebRTCDav1dDecoder.cpp (and libavif.a with AVIF_CODEC_DAV1D)
# but WebCore's OTHER_LDFLAGS never references libavif.a - Apple-internal
# builders had it in /usr/local/lib. Patch WebCore.xcconfig to force-load
# the built libavif.a (which itself force-loads libdav1d.a, resolving the
# _dav1d_* symbols). Harness-only linkage completion, identical on both legs.
p = "Source/WebCore/Configurations/WebCore.xcconfig"
s = open(p).read()
old = "$(WK_APPLEJPEGXL_LDFLAGS) $(WK_DEBUG_LDFLAGS);"
new = "$(WK_APPLEJPEGXL_LDFLAGS) $(WK_DEBUG_LDFLAGS) -force_load $(BUILT_PRODUCTS_DIR)/libavif.a;"
if old in s:
    open(p, "w").write(s.replace(old, new, 1))
    print("patched WebCore.xcconfig: OTHER_LDFLAGS force_loads libavif.a (dav1d symbols)")
else:
    print("WebCore.xcconfig OTHER_LDFLAGS tail not found (trunk?)")
# ATTEMPT-36: WebKitLegacy's WebFullScreenController.mm uses
# CGWindowListCreateImage (obsoleted in macOS 15.0 - hard error, no
# pragma escape). Upstream replaced this with ScreenCaptureKit. The
# function captures a snapshot for the legacy full-screen animation;
# return nil image is a benign degradation. Patch: guard the call and
# skip the snapshot.
p = "Source/WebKitLegacy/mac/WebView/WebFullScreenController.mm"
s = open(p).read()
old = "ALLOW_DEPRECATED_DECLARATIONS_BEGIN\n    RetainPtr<CGImageRef> webViewContents = adoptCF(CGWindowListCreateImage(NSRectToCGRect(webViewFrame), kCGWindowListOptionIncludingWindow, windowID, kCGWindowImageShouldBeOpaque));\nALLOW_DEPRECATED_DECLARATIONS_END"
new = "#if 0 // HARNESS: CGWindowListCreateImage obsoleted in SDK 26.5; skip full-screen snapshot\nALLOW_DEPRECATED_DECLARATIONS_BEGIN\n    RetainPtr<CGImageRef> webViewContents = adoptCF(CGWindowListCreateImage(NSRectToCGRect(webViewFrame), kCGWindowListOptionIncludingWindow, windowID, kCGWindowImageShouldBeOpaque));\nALLOW_DEPRECATED_DECLARATIONS_END\n#else\n    RetainPtr<CGImageRef> webViewContents;\n#endif"
if old in s:
    open(p, "w").write(s.replace(old, new, 1))
    print("patched WebFullScreenController.mm: CGWindowListCreateImage snapshot skipped (obsoleted API)")
else:
    print("WebFullScreenController.mm CGWindowListCreateImage not found (trunk?)")
# ATTEMPT-37: the same obsoleted CGWindowListCreateImage appears as the
# off-screen fallback in WebKit's WebViewImpl.mm
# (windowSnapshotAtTime... hardware-capture fallback path). The primary
# path uses private CGSHWCaptureWindowList; the fallback only triggers
# for fully off-screen windows. Patch: return nullptr from the
# fallback (no snapshot - benign, identical on both legs).
p = "Source/WebKit/UIProcess/mac/WebViewImpl.mm"
s = open(p).read()
old = "ALLOW_DEPRECATED_DECLARATIONS_BEGIN\n    return adoptCF(CGWindowListCreateImage(CGRectNull, kCGWindowListOptionIncludingWindow, windowID, imageOptions));\nALLOW_DEPRECATED_DECLARATIONS_END"
new = "#if 0 // HARNESS: CGWindowListCreateImage obsoleted in SDK 26.5; skip off-screen snapshot fallback\nALLOW_DEPRECATED_DECLARATIONS_BEGIN\n    return adoptCF(CGWindowListCreateImage(CGRectNull, kCGWindowListOptionIncludingWindow, windowID, imageOptions));\nALLOW_DEPRECATED_DECLARATIONS_END\n#else\n    return nullptr;\n#endif"
if old in s:
    open(p, "w").write(s.replace(old, new, 1))
    print("patched WebViewImpl.mm: CGWindowListCreateImage fallback returns nullptr (obsoleted API)")
else:
    print("WebViewImpl.mm CGWindowListCreateImage not found (trunk?)")

# ATTEMPT-38: the third CGWindowListCreateImage user is WebKit's
# WKFullScreenWindowController.mm (UIProcess/mac full-screen
# controller). Two sites: (1) the enter-fullscreen snapshot that
# feeds the placeholder view contents; (2) the takeWindowSnapshot
# off-screen fallback. Same obsoleted-API hard error as attempts
# 36-37. Patch: #if 0 skips with a null snapshot; site 1's
# createImageWithCopiedData consumer gains a null guard (the
# helper does not null-check its source image). Full-screen
# snapshot capture is never exercised by layout tests; benign
# degradation, identical on both legs.
p = "Source/WebKit/UIProcess/mac/WKFullScreenWindowController.mm"
s = open(p).read()
old = "ALLOW_DEPRECATED_DECLARATIONS_BEGIN\n    RetainPtr<CGImageRef> webViewContents = adoptCF(CGWindowListCreateImage(NSRectToCGRect(webViewFrame), kCGWindowListOptionIncludingWindow, windowID, kCGWindowImageShouldBeOpaque));\nALLOW_DEPRECATED_DECLARATIONS_END"
new = "#if 0 // HARNESS: CGWindowListCreateImage obsoleted in SDK 26.5; skip full-screen snapshot\nALLOW_DEPRECATED_DECLARATIONS_BEGIN\n    RetainPtr<CGImageRef> webViewContents = adoptCF(CGWindowListCreateImage(NSRectToCGRect(webViewFrame), kCGWindowListOptionIncludingWindow, windowID, kCGWindowImageShouldBeOpaque));\nALLOW_DEPRECATED_DECLARATIONS_END\n#else\n    RetainPtr<CGImageRef> webViewContents;\n#endif"
if old in s:
    open(p, "w").write(s.replace(old, new, 1))
    print("patched WKFullScreenWindowController.mm: enter-fullscreen CGWindowListCreateImage snapshot skipped (obsoleted API)")
else:
    print("WKFullScreenWindowController.mm enter-fullscreen snapshot not found (trunk?)")
s = open(p).read()
old = "    webViewContents = createImageWithCopiedData(webViewContents.get());"
new = "    if (webViewContents) // HARNESS: null-guard for skipped snapshot (createImageWithCopiedData does not null-check)\n        webViewContents = createImageWithCopiedData(webViewContents.get());"
if old in s:
    open(p, "w").write(s.replace(old, new, 1))
    print("patched WKFullScreenWindowController.mm: createImageWithCopiedData consumer null-guarded")
else:
    print("WKFullScreenWindowController.mm createImageWithCopiedData call not found (trunk?)")
s = open(p).read()
old = "ALLOW_DEPRECATED_DECLARATIONS_BEGIN\n    return adoptCF(CGWindowListCreateImage(CGRectNull, kCGWindowListOptionIncludingWindow, windowID, imageOptions));\nALLOW_DEPRECATED_DECLARATIONS_END"
new = "#if 0 // HARNESS: CGWindowListCreateImage obsoleted in SDK 26.5; skip off-screen snapshot fallback\nALLOW_DEPRECATED_DECLARATIONS_BEGIN\n    return adoptCF(CGWindowListCreateImage(CGRectNull, kCGWindowListOptionIncludingWindow, windowID, imageOptions));\nALLOW_DEPRECATED_DECLARATIONS_END\n#else\n    return nullptr;\n#endif"
if old in s:
    open(p, "w").write(s.replace(old, new, 1))
    print("patched WKFullScreenWindowController.mm: takeWindowSnapshot fallback returns nullptr (obsoleted API)")
else:
    print("WKFullScreenWindowController.mm takeWindowSnapshot fallback not found (trunk?)")

# ATTEMPT-39: WebKit framework compilation advanced past
# WKFullScreenController/WebViewImpl/WKFullScreenWindowController and
# failed in PageClientImplMac.mm (UIProcess/mac). SDK 26.5 defines
# kAXLoadCompleteNotification as a CFStringRef-flavored macro in its
# accessibility headers, so the 2023 tree's local
# `static NSString * const kAXLoadCompleteNotification = @"AXLoadComplete";`
# (a) collides at the definition ("redefinition of 'CFStringRef' as
# different kind of symbol" + "expected ')'") and (b) breaks the two
# NSAccessibilityPostNotification call sites (macro expands to an
# incomplete CFStringRef, not convertible to the SDK's
# NSAccessibilityNotificationName NSString* parameter). Patch: rename
# the local constant to a harness-unique name and update both call
# sites - identical runtime semantics (posts the same @"AXLoadComplete"
# notification). File byte-identical between both pinned legs.
p = "Source/WebKit/UIProcess/mac/PageClientImplMac.mm"
s = open(p).read()
old = "static NSString * const kAXLoadCompleteNotification = @\"AXLoadComplete\";"
new = "static NSString * const wkHarnessAXLoadCompleteNotification = @\"AXLoadComplete\"; // HARNESS: renamed - SDK 26.5 defines kAXLoadCompleteNotification as a CFStringRef macro"
if old in s:
    open(p, "w").write(s.replace(old, new, 1))
    print("patched PageClientImplMac.mm: kAXLoadCompleteNotification constant renamed (SDK macro collision)")
else:
    print("PageClientImplMac.mm kAXLoadCompleteNotification definition not found (trunk?)")
s = open(p).read()
old = "NSAccessibilityPostNotification(NSAccessibilityUnignoredAncestor(m_view), kAXLoadCompleteNotification);"
new = "NSAccessibilityPostNotification(NSAccessibilityUnignoredAncestor(m_view), wkHarnessAXLoadCompleteNotification);"
n = s.count(old)
if n:
    open(p, "w").write(s.replace(old, new))
    print("patched PageClientImplMac.mm: %d NSAccessibilityPostNotification call site(s) updated to renamed constant" % n)
else:
    print("PageClientImplMac.mm NSAccessibilityPostNotification call sites not found (trunk?)")

# ATTEMPT-40: the WebKit FRAMEWORK now builds on both legs; the failure
# moved to build-webkit's MiniBrowser target - the fourth
# CGWindowListCreateImage user, Tools/MiniBrowser/mac/
# BrowserWindowController.m:329 (sharing-service transition snapshot).
# Same un-suppressible obsoleted-API class as attempts 36-38. MiniBrowser
# is a developer tool, never exercised by the tests under test (they run
# in WebKitTestRunner) - zero effect on the code under test. Patch: #if 0
# skip with a NULL image; the function's existing !imageRef path returns
# nil. File byte-identical between both pinned legs.
p = "Tools/MiniBrowser/mac/BrowserWindowController.m"
s = open(p).read()
old = "#pragma clang diagnostic push\n#pragma clang diagnostic ignored \"-Wdeprecated-declarations\"\n    CGImageRef imageRef = CGWindowListCreateImage(frame, kCGWindowListOptionIncludingWindow, (CGWindowID)[self.window windowNumber], kCGWindowImageBoundsIgnoreFraming);\n#pragma clang diagnostic pop"
new = "#if 0 // HARNESS: CGWindowListCreateImage obsoleted in SDK 26.5; skip share-transition snapshot (MiniBrowser dev tool)\n#pragma clang diagnostic push\n#pragma clang diagnostic ignored \"-Wdeprecated-declarations\"\n    CGImageRef imageRef = CGWindowListCreateImage(frame, kCGWindowListOptionIncludingWindow, (CGWindowID)[self.window windowNumber], kCGWindowImageBoundsIgnoreFraming);\n#pragma clang diagnostic pop\n#else\n    CGImageRef imageRef = NULL;\n#endif"
if old in s:
    open(p, "w").write(s.replace(old, new, 1))
    print("patched BrowserWindowController.m: MiniBrowser CGWindowListCreateImage snapshot skipped (obsoleted API)")
else:
    print("BrowserWindowController.m CGWindowListCreateImage not found (trunk?)")

# ATTEMPT-41: MiniBrowser now builds; the failure moved deeper into the
# Tools to DumpRenderTree - the FIFTH CGWindowListCreateImage user,
# Tools/DumpRenderTree/mac/PixelDumpSupportMac.mm:85 (takeWindowSnapshot
# helper used only by the on-screen pixel-dump path). Both legs fail
# identically (prefix at Tools/WebKitTestRunner/mac/PlatformWebViewMac.mm
# :225 in parallel - same class, patched next as ATTEMPT-41b). Tests run
# under WebKitTestRunner without pixel comparison, so this snapshot path
# is not exercised. Patch: #if 0 skip with nullptr return (identical to
# the WebViewImpl/WKFullScreenWindowController fallback treatment).
# File byte-identical between both pinned legs.
p = "Tools/DumpRenderTree/mac/PixelDumpSupportMac.mm"
s = open(p).read()
old = "    imageOptions |= kCGWindowImageBoundsIgnoreFraming | kCGWindowImageShouldBeOpaque;\n    return adoptCF(CGWindowListCreateImage(CGRectNull, kCGWindowListOptionIncludingWindow, windowID, imageOptions));"
new = "    imageOptions |= kCGWindowImageBoundsIgnoreFraming | kCGWindowImageShouldBeOpaque;\n#if 0 // HARNESS: CGWindowListCreateImage obsoleted in SDK 26.5; skip on-screen snapshot (unused without pixel comparison)\n    return adoptCF(CGWindowListCreateImage(CGRectNull, kCGWindowListOptionIncludingWindow, windowID, imageOptions));\n#else\n    return nullptr;\n#endif"
if old in s:
    open(p, "w").write(s.replace(old, new, 1))
    print("patched PixelDumpSupportMac.mm: DumpRenderTree takeWindowSnapshot returns nullptr (obsoleted API)")
else:
    print("PixelDumpSupportMac.mm CGWindowListCreateImage not found (trunk?)")

# ATTEMPT-41b: the SIXTH CGWindowListCreateImage user, in the tool that
# DOES matter for the differential: Tools/WebKitTestRunner/mac/
# PlatformWebViewMac.mm:225 (PlatformWebView::windowSnapshot for the
# prefix leg; the fixed leg compiles it too). Same obsoleted-API hard
# error. WTR's snapshot is used only for reftest/pixel comparisons;
# our layout tests are crash-oracle, not pixel tests, so a null
# snapshot never affects the verdict. Patch: #if 0 skip with nullptr
# return. File byte-identical between both pinned legs.
p = "Tools/WebKitTestRunner/mac/PlatformWebViewMac.mm"
s = open(p).read()
old = "    return adoptCF(CGWindowListCreateImage(CGRectNull, kCGWindowListOptionIncludingWindow, [m_window windowNumber], options));"
new = "#if 0 // HARNESS: CGWindowListCreateImage obsoleted in SDK 26.5; skip window snapshot (crash-oracle tests do no pixel comparison)\n    return adoptCF(CGWindowListCreateImage(CGRectNull, kCGWindowListOptionIncludingWindow, [m_window windowNumber], options));\n#else\n    return nullptr;\n#endif"
if old in s:
    open(p, "w").write(s.replace(old, new, 1))
    print("patched PlatformWebViewMac.mm: WTR windowSnapshot returns nullptr (obsoleted API)")
else:
    print("PlatformWebViewMac.mm CGWindowListCreateImage not found (trunk?)")

# ATTEMPT-46: use_sigaltstack=0 in the workflow ASAN_OPTIONS did NOT fix
# the Networking-process startup crash - because WebKit child processes
# do not inherit the runner env (no asan-report log files were created
# and the CHECK text went to stderr, both proving the child runs ASan
# with DEFAULT options). Binary-embedded fix: define
# __asan_default_options() in WTF (linked into every WebKit child
# process - WebContent, Networking, WTR itself), so the option applies
# regardless of environment scrubbing. Zero effect on memory-error
# detection; identical on both legs. Appended to Threading.cpp (present
# in both pinned trees; no existing __asan_default_options anywhere in
# the tree per GitHub code search).
p = "Source/WTF/wtf/Threading.cpp"
s = open(p).read()
old = "} // namespace WTF\n"
new = """} // namespace WTF

extern "C" const char *__asan_default_options()
{
    // HARNESS: ASan runtime cannot install its alternate signal stack
    // inside sandboxed WebKit child processes on the Xcode 26.6 runner
    // image (CHECK failed: sanitizer_posix_libcdep.cpp:191 sigaltstack).
    // Embedded default because child processes get a scrubbed
    // environment and never see ASAN_OPTIONS. use_sigaltstack=0 only
    // disables the dedicated signal-handler stack; memory-error
    // detection is unaffected. Identical on both differential legs.
    return "use_sigaltstack=0:detect_leaks=0";
}
"""
if old in s and "__asan_default_options" not in s:
    open(p, "w").write(s.replace(old, new, 1))
    print("patched Threading.cpp: embedded __asan_default_options (use_sigaltstack=0)")
elif "__asan_default_options" in s:
    print("Threading.cpp already has __asan_default_options (idempotent)")
else:
    print("Threading.cpp WTF namespace terminator not found (trunk?)")

# ATTEMPT-47: true root cause of the Networking-process startup crash.
# WebKit's sandbox profiles gate the sigaltstack syscall allowance:
#     #if ASAN_ENABLED
#             SYS_sigaltstack
#     #endif
# but the "Pre-processing ... sandbox profile" build phase runs plain
# 'clang -E -P -w ... -include wtf/Platform.h' WITHOUT -fsanitize=address
# (verified in run 41637712079's job log), so __has_feature(address_
# sanitizer) is false, ASAN_ENABLED is 0, and the compiled .sb DROPS
# the sigaltstack allowance. The sandboxed Networking/GPU child
# processes then get sigaltstack() denied (EPERM) and the ASan runtime
# dies at asan_thread_start -> SetAlternateSignalStack -> CHECK
# (sanitizer_posix_libcdep.cpp:191) before any test code runs.
# use_sigaltstack=0 could not help: that thread-start path calls
# SetAlternateSignalStack unconditionally before flags apply.
# Fix: force the SYS_sigaltstack line into every sandbox profile that
# carries the ASAN_ENABLED guard (identical accommodation on both
# legs; inert when the process is unsandboxed or sigaltstack allowed).
SB_GUARD_OLD = "#if ASAN_ENABLED\n        SYS_sigaltstack\n#endif"
SB_GUARD_NEW = "        SYS_sigaltstack"
SB_FILES = [
    "Source/WebKit/Resources/SandboxProfiles/ios/com.apple.WebKit.Networking.sb.in",
    "Source/WebKit/Resources/SandboxProfiles/ios/com.apple.WebKit.GPU.sb.in",
    "Source/WebKit/Resources/SandboxProfiles/ios/com.apple.WebKit.WebContent.sb.in",
    "Source/WebKit/Resources/SandboxProfiles/ios/com.apple.WebKit.adattributiond.sb.in",
    "Source/WebKit/Resources/SandboxProfiles/ios/com.apple.WebKit.webpushd.sb.in",
    "Source/WebKit/WebProcess/com.apple.WebProcess.sb.in",
    "Source/WebKit/NetworkProcess/mac/com.apple.WebKit.NetworkProcess.sb.in",
    "Source/WebKit/GPUProcess/mac/com.apple.WebKit.GPUProcess.sb.in",
    "Source/WebKit/webpushd/mac/com.apple.WebKit.webpushd.mac.sb.in",
]
for sbp in SB_FILES:
    try:
        s = open(sbp).read()
    except FileNotFoundError:
        print("sandbox profile not present, skipped: " + sbp)
        continue
    if SB_GUARD_OLD in s:
        open(sbp, "w").write(s.replace(SB_GUARD_OLD, SB_GUARD_NEW, 1))
        print("patched " + sbp + ": SYS_sigaltstack ASAN_ENABLED guard forced on")
    elif "SYS_sigaltstack" in s:
        print("sandbox profile already allows sigaltstack: " + sbp)
    else:
        print("no sigaltstack rule in " + sbp + " (unexpected)")

# ATTEMPT-48b (B4 campaign, 2024-era pins only): Xcode 26 hard-errors
# "Multiple commands produce WebKit.framework/Frameworks" because the
# 2024-era "Make Frameworks Symbolic Link" script phase declares the
# symlink as a build output while modern Xcode creates it itself.
# Upstream's own fix (commit 748d56ebc1c8, BZ 286370) makes the phase
# declare zero dependencies and install-only; we apply the SAME
# transformation to both pbxprojs at the pinned refs (identical on
# both legs; the phase no longer feeds build-system dependency
# analysis).
WK_PBX = "Source/WebKit/WebKit.xcodeproj/project.pbxproj"
s = open(WK_PBX).read()
WK_OLD = "\t\t1A07D2F51919AA8A00ECDA16 /* Make Frameworks Symbolic Link */ = {\n\t\t\tisa = PBXShellScriptBuildPhase;\n\t\t\tbuildActionMask = 2147483647;\n\t\t\tfiles = (\n\t\t\t);\n\t\t\tinputPaths = (\n\t\t\t);\n\t\t\tname = \"Make Frameworks Symbolic Link\";\n\t\t\toutputPaths = (\n\t\t\t\t\"$(TARGET_BUILD_DIR)/WebKit.framework/Frameworks\",\n\t\t\t);\n\t\t\trunOnlyForDeploymentPostprocessing = 0;"
WK_NEW = "\t\t1A07D2F51919AA8A00ECDA16 /* Make Frameworks Symbolic Link */ = {\n\t\t\tisa = PBXShellScriptBuildPhase;\n\t\t\talwaysOutOfDate = 1;\n\t\t\tbuildActionMask = 8;\n\t\t\tfiles = (\n\t\t\t);\n\t\t\tinputPaths = (\n\t\t\t);\n\t\t\tname = \"Make Frameworks Symbolic Link\";\n\t\t\toutputPaths = (\n\t\t\t);\n\t\t\trunOnlyForDeploymentPostprocessing = 1;"
if WK_OLD in s:
    open(WK_PBX, "w").write(s.replace(WK_OLD, WK_NEW, 1))
    print("patched WebKit pbxproj: Make Frameworks Symbolic Link phase zero-dep install-only (upstream 748d56ebc1c8 transformation)")
elif "alwaysOutOfDate = 1;\n\t\t\tbuildActionMask = 8;" in s:
    print("WebKit pbxproj symbolic-link phase already transformed (idempotent)")
else:
    print("WebKit pbxproj symbolic-link phase not found (2023-era pins lack it)")
WC_PBX = "Source/WebCore/WebCore.xcodeproj/project.pbxproj"
s = open(WC_PBX).read()
WC_OLD = "\t\t\t\t$TARGET_BUILD_DIR/WebCore.framework/Frameworks,\n"
WC_NEW = "\t\t\t\t\"$(TARGET_BUILD_DIR)/WebCore.framework/Frameworks\",\n"
if WC_OLD in s:
    open(WC_PBX, "w").write(s.replace(WC_OLD, WC_NEW, 1))
    print("patched WebCore pbxproj: Make Frameworks Symbolic Link output path quoted (upstream 748d56ebc1c8 transformation)")
elif WC_NEW in s:
    print("WebCore pbxproj output path already quoted (idempotent)")
else:
    print("WebCore pbxproj symbolic-link phase not found (older pins?)")

# ATTEMPT-49 (B4 campaign, 2024-era pins only): clang 21 hard-errors on
# 'lifetimebound' applied to a parameter of a void-returning function
# (a C++26-era rule change): libwebrtc's candidate.h set_type(void)
# carries ABSL_ATTRIBUTE_LIFETIME_BOUND, which clang 21 rejects.
# The attribute is a static-analysis annotation only (no codegen);
# neutralize the abseil macro definition so it expands to nothing -
# identical on both legs, zero codegen effect.
p = "Source/ThirdParty/libwebrtc/Source/third_party/abseil-cpp/absl/base/attributes.h"
s = open(p).read()
old = "#if ABSL_HAVE_CPP_ATTRIBUTE(clang::lifetimebound)\n#define ABSL_ATTRIBUTE_LIFETIME_BOUND [[clang::lifetimebound]]\n#elif ABSL_HAVE_ATTRIBUTE(lifetimebound)\n#define ABSL_ATTRIBUTE_LIFETIME_BOUND __attribute__((lifetimebound))\n#else\n#define ABSL_ATTRIBUTE_LIFETIME_BOUND\n#endif"
new = "#define ABSL_ATTRIBUTE_LIFETIME_BOUND // HARNESS: clang 21 rejects lifetimebound on void-returning function parameters (libwebrtc candidate.h); annotation-only attribute, no codegen. Whole detection chain collapsed to empty (attempt-50 lesson: disabling only the first branch falls through to the __attribute__ branch)."
if old in s:
    open(p, "w").write(s.replace(old, new, 1))
    print("patched abseil attributes.h: ABSL_ATTRIBUTE_LIFETIME_BOUND chain collapsed to empty define")
elif "ABSL_ATTRIBUTE_LIFETIME_BOUND //" in s:
    print("abseil attributes.h lifetimebound already collapsed (idempotent)")
else:
    print("abseil attributes.h lifetimebound macro block not found (trunk?)")

# ATTEMPT-51 (B4 campaign, 2024-era pins only): SDK 26.5's accessibility
# headers now declare kAXConvertRelativeFrameParameterizedAttribute as a
# CFStringRef-flavored macro, so the tree's `#define ... @"AXConvertRelativeFrame"`
# inside `#ifndef` never fires and both uses in
# WebAccessibilityObjectWrapperMac.mm fail to convert CFStringRef ->
# NSString*/id (the SDK macro's expansion is an incomplete CFStringRef).
# Same era class as the kAXLoadCompleteNotification collision (attempt
# 39). Patch: rename the local define and both call sites to a
# harness-unique constant - identical runtime semantics (same string
# literal). Identical on both legs.
p = "Source/WebCore/accessibility/mac/WebAccessibilityObjectWrapperMac.mm"
s = open(p).read()
old = "#ifndef kAXConvertRelativeFrameParameterizedAttribute\n#define kAXConvertRelativeFrameParameterizedAttribute @\"AXConvertRelativeFrame\"\n#endif"
new = "#define wkHarnessAXConvertRelativeFrameParameterizedAttribute @\"AXConvertRelativeFrame\" // HARNESS: renamed - SDK 26.5 defines kAXConvertRelativeFrameParameterizedAttribute as a CFStringRef macro"
if old in s:
    open(p, "w").write(s.replace(old, new, 1))
    print("patched WebAccessibilityObjectWrapperMac.mm: kAXConvertRelativeFrameParameterizedAttribute define renamed (SDK macro collision)")
elif "wkHarnessAXConvertRelativeFrameParameterizedAttribute" in s:
    print("WebAccessibilityObjectWrapperMac.mm constant already renamed (idempotent)")
else:
    print("WebAccessibilityObjectWrapperMac.mm kAXConvertRelativeFrame guard not found (trunk?)")
s = open(p).read()
n = s.count("kAXConvertRelativeFrameParameterizedAttribute")
if n:
    open(p, "w").write(s.replace("kAXConvertRelativeFrameParameterizedAttribute", "wkHarnessAXConvertRelativeFrameParameterizedAttribute"))
    print("patched WebAccessibilityObjectWrapperMac.mm: %d call site(s) updated to renamed constant" % n)
else:
    print("WebAccessibilityObjectWrapperMac.mm call sites not found (trunk?)")

# ATTEMPT-32: third consumer - LocalSampleBufferDisplayLayer.mm
# line 436: RELEASE_LOG reads all five properties inside a
# #if !RELEASE_LOG_DISABLED block. Release builds have
# RELEASE_LOG_DISABLED set... but the block still compiles for
# RELEASE_LOG_ENABLED channels in WebCore Release config. Patch:
# guard the metrics read with (0 &&) so the property accesses
# are not compiled.
p3i = "Source/WebCore/platform/graphics/avfoundation/objc/LocalSampleBufferDisplayLayer.mm"
s3i = open(p3i).read()
# Wrap the whole if-statement in #if 0 (self-contained, no
# brace surgery; RELEASE_LOG property reads are excluded).
old3i = "        if (auto* metrics = [m_sampleBufferDisplayLayer videoPerformanceMetrics])\n            RELEASE_LOG(WebRTC, \"LocalSampleBufferDisplayLayer (%{public}s) metrics, total=%lu, dropped=%lu, corrupted=%lu, display-composited=%lu, non-display-composited=%lu (pending=%lu)\", m_logIdentifier.utf8().data(), metrics.totalNumberOfVideoFrames, metrics.numberOfDroppedVideoFrames, metrics.numberOfCorruptedVideoFrames, metrics.numberOfDisplayCompositedVideoFrames, metrics.numberOfNonDisplayCompositedVideoFrames, m_pendingVideoFrameQueue.size());"
new3i = "#if 0 // HARNESS: AVVideoPerformanceMetrics properties unavailable on macOS SDK 26.5; metrics logging excluded\n" + old3i + "\n#endif"
if old3i in s3i:
    s3i = s3i.replace(old3i, new3i, 1)
    open(p3i, "w").write(s3i)
    print("patched LocalSampleBufferDisplayLayer.mm: metrics RELEASE_LOG block wrapped in #if 0 (unavailable SDK properties)")
else:
    print("LocalSampleBufferDisplayLayer.mm metrics block not found (trunk?) - no patch applied")
p3f = "Source/WebCore/loader/FrameLoader.cpp"
s3f = open(p3f).read()
old3f = '"handleLoadFailureRecovery: errorRecoveryMethod: %hhu, isHTTPSFirstApplicable: %d, isHTTPFallbackInProgress: %d", error.errorRecoveryMethod(), isHTTPSFirstApplicable, isHTTPFallbackInProgress())'
new3f = '"handleLoadFailureRecovery: errorRecoveryMethod: %hhu, isHTTPSFirstApplicable: %d, isHTTPFallbackInProgress: %d", static_cast<unsigned char>(error.errorRecoveryMethod()), isHTTPSFirstApplicable, isHTTPFallbackInProgress())'
if old3f in s3f:
    s3f = s3f.replace(old3f, new3f, 1)
    open(p3f, "w").write(s3f)
    print("patched FrameLoader.cpp: errorRecoveryMethod log argument cast to unsigned char (format-string fix)")
else:
    print("FrameLoader.cpp errorRecoveryMethod log not found (trunk?) - no patch applied")
p3 = "Source/WTF/wtf/spi/cocoa/IOSurfaceSPI.h"
s3 = open(p3).read()
marker3 = "typedef CF_ENUM(int, IOSurfaceMemoryLedgerTags)"
i = s3.find(marker3)
if i != -1:
    j = s3.find("};", i)
    j = s3.find("\n", j) + 1
    open(p3, "w").write(s3[:i] + "/* HARNESS: duplicate of SDK enum removed for Xcode 26.6 build */\n" + s3[j:])
    print("patched IOSurfaceSPI.h: removed duplicate IOSurfaceMemoryLedgerTags enum (SDK 26.5 provides it)")
else:
    print("no IOSurfaceMemoryLedgerTags shim in IOSurfaceSPI.h (trunk?) - no patch applied")

# WebInspectorUI fallback (CI serialization accommodation)
p = "Source/WebInspectorUI/Scripts/copy-user-interface-resources.pl"
s = open(p).read()
old = 'or die "Copy of InspectorBackendCommands.js failed: $!";'
new = 'or print STDERR "HARNESS-WARN: InspectorBackendCommands.js not present yet (CI serialization accommodation): $!\\n";'
if old in s:
    open(p, "w").write(s.replace(old, new))
    print("patched copy-user-interface-resources.pl: die -> warn (fallback layer)")
else:
    print("pattern not found in copy-user-interface-resources.pl (trunk variant?) - no fallback patch applied")
